# Spec 008: User-scope skills usable from any agent repository

Status: draft; not implemented.
Date: 2026-09-29.

## Problem

The four lifecycle skills (`oci-agent-build`, `oci-agent-push`,
`oci-agent-deploy`, `oci-agent-verify-deployment`) work only when Codex runs in
this repository:

* **Discovery.** The skills are exposed only by the repository link
  `.agents/skills -> ../skills`. No `oci-agent-*` skill is installed in the
  user scope (`$HOME/.agents/skills`), and no installer exists.
* **Manifest location.** `scripts/agent_manifest.py` anchors every path to this
  checkout (`Path(__file__).resolve().parent.parent`). It rejects:
  * an absolute manifest path;
  * a manifest outside this checkout;
  * a `build.context` or `build.dockerfile` that escapes this checkout.

  An agent kept in another repository therefore cannot be built, pushed,
  deployed, or verified, even if the skills were visible.
* **Current directory.** Two operations assume the working directory is this
  checkout:
  * `python -m scripts.run_manifest_checks` in `verify_image.sh`,
    `verify_deployment.sh`, and `AgentManifest.psm1`;
  * the `. ./.env` step in the verification skill.

  The Bash build script also uses the context and Dockerfile paths as given,
  relative to the working directory.
* **Configuration.** The tenancy values live in this checkout's `.env`, which
  the operator must export by hand before running the OCI scripts.
* **Interpreter.** The scripts call whichever `python` is first on `PATH`.
  PyYAML is declared only in `requirements-dev.txt`, and the root
  `requirements.txt` is also the dependency list of the `hello_world` image.
* **Documentation.** `docs/using-oci-agent-skills.md` says an absolute manifest
  path is suitable, but the code rejects it.

## Scope

Make the skills installable at user scope and usable from a Codex session whose
workspace is any agent repository, with these parts:

* A manifest contract whose paths are independent of this checkout.
* Scripts independent of the current directory.
* Explicit tenancy configuration and interpreter selection.
* An installer and uninstaller for the user scope.
* Updated skill instructions, templates, reference agent, guide, and tests.

Keep the Bash and PowerShell families at parity throughout, as required by
Spec 007.

## Non-goals

* Replacing the scripts with an MCP server. The work is done by Docker and the
  OCI CLI, and streams long logs; an installable command-line tool may be
  specified separately later.
* Changing the release workflow, the approval boundaries, the
  `public-noauth` profile, or any OCI resource behavior.
* Supporting several tenancy configurations in one invocation.
* Copying scripts into agent repositories. Agent repositories contain only
  their code, Dockerfile, `.dockerignore`, and `agent.yaml`.
* Creating IAM policies, auth tokens, or Docker credentials.

## Assumptions and prerequisites

* One stable checkout of this repository is the **tool home**. User-scope
  skills are symlinks into its `skills/` folder, so the tool home must stay at
  its installed location.
* Development of this spec happens in a separate Git worktree on the branch
  `user-scope-skills`, so that skills installed from the stable checkout do not
  change while the branch is checked out.
* Codex discovers user-scope skills in `$HOME/.agents/skills` and follows
  symlinks. This was verified empirically on 2026-09-27 with codex-cli
  0.155.0-alpha.16.3 in the companion repository `codex-4-oci-aidp`; the
  OpenAI "Build skills" documentation was reviewed on 2026-09-22.
* The project Conda environment `codex-4-oci-enterprise-ai-deployment`
  provides Python, PyYAML, and OCI CLI. Docker, Buildx, and curl (Bash) or
  Docker Desktop/Podman (PowerShell) are installed as today.

## Intended behavior

### 1. Manifest contract: `schema_version: 2`

* **Manifest path.** Scripts accept an absolute path, or a path relative to
  the **current working directory**. They no longer resolve it against the tool
  home.
* **Build paths.** `build.context` and `build.dockerfile` are resolved relative
  to the **manifest's directory**.
* **Allowed roots.** After resolution, the manifest and both build paths must
  lie inside an allowed root:
  * if `OCI_AGENT_ALLOWED_ROOTS` is set, it is a list of absolute directories
    separated by the platform path separator (`:` on macOS/Linux, `;` on
    Windows), and every path must be inside one of them;
  * otherwise the allowed root is the Git work tree that contains the manifest,
    found by walking up the parents until one contains `.git` (a directory or a
    file, so that worktrees work), without running Git;
  * if no parent contains `.git`, the allowed root is the manifest's directory.

  Symlinks are resolved before the containment check. A path that escapes the
  allowed root is rejected with exit code 64 and a message naming the root.
* **Script output.** `agent_manifest.py get` returns **absolute** resolved
  paths for `build.context` and `build.dockerfile`, so no caller depends on the
  working directory.
* **Version 1.** A `schema_version: 1` manifest is rejected with an actionable
  message: build paths are now relative to the manifest directory, and the
  version must become 2. The only version 1 manifest is
  `demos/hello_world/agent.yaml`, which this spec migrates.
* All other schema rules of Spec 006 are unchanged.

`demos/hello_world/agent.yaml` becomes:

```yaml
schema_version: 2
build:
  context: ../..
  dockerfile: Dockerfile
```

The other fields are unchanged. The allowed root is this checkout, found through
`.git`.

### 2. Scripts independent of the current directory

* Every script locates the tool home from its own path, as today, and never
  requires the working directory to be the tool home.
* `run_manifest_checks.py` runs by path, for example
  `"$OCI_AGENT_PYTHON" "$script_dir/run_manifest_checks.py"`, instead of
  `python -m scripts.run_manifest_checks`. Its import of `agent_manifest` must
  work in that mode. `Invoke-ManifestChecks` no longer needs `Push-Location`.
* Manifest paths given by the operator are passed through unchanged and
  resolved by `agent_manifest.py` as described above. The PowerShell scripts no
  longer join build paths with the repository root.
* Temporary files remain in the system temporary directory. Scripts never write
  into the tool home or the agent repository, except for Docker's own state.

### 3. Tenancy configuration file

* `OCI_AGENT_ENV_FILE` selects the tenancy configuration file. The default is
  `<tool home>/.env`.
* The scripts that need tenancy values (resolve, ensure repository, push,
  deploy, verify deployment) load them themselves:
  * only the keys `OCI_REGION`, `OCI_COMPARTMENT_NAME`,
    `OCIR_TENANCY_NAMESPACE`, and `OCIR_USERNAME` are read;
  * the file is parsed as `KEY=VALUE` lines; blank lines and `#` comments are
    ignored;
  * the file is **never sourced or evaluated** as shell code;
  * a value already present in the process environment takes precedence, so
    the current workflow of exporting values keeps working;
  * a missing file is not an error when every required value is already in the
    environment; otherwise the error names the file and the missing keys and
    exits with the script's existing configuration error code.
* The parser is implemented once in Python and used by both script families.
  Scripts never print the file's content.
* `.env.example` documents `OCI_AGENT_ENV_FILE` in a comment only; the four
  keys stay unchanged.

### 4. Interpreter and dependencies

* `OCI_AGENT_PYTHON` selects the interpreter used by the scripts. The default
  is `python` from `PATH`.
* Before reading a manifest, each script checks that the interpreter can import
  `yaml`. If not, it exits with code 1 and asks the operator to activate the
  Conda environment `codex-4-oci-enterprise-ai-deployment` or to set
  `OCI_AGENT_PYTHON`.
* Dependency files are split by purpose:
  * the root `requirements.txt` holds the **tool** runtime dependencies (PyYAML;
    OCI CLI if it is installed with pip);
  * `demos/hello_world/requirements.txt` holds the `hello_world` image
    dependencies (FastAPI, LangGraph, Pydantic, Uvicorn);
  * `requirements-dev.txt` includes both, plus the development tools.

  The `hello_world` Dockerfile copies its own requirements file. The image
  contents are otherwise unchanged.
* The skills run the scripts inside the Conda environment, either activated or
  through `conda run --no-capture-output -n codex-4-oci-enterprise-ai-deployment`,
  so that build logs still stream.

### 5. Templates for external agents

* `skills/oci-agent-build/assets/Dockerfile.template` assumes a build context
  that is the **agent's own folder or repository**, with its own
  `requirements.txt`. The binary-only `pip` policy and the non-root user are
  unchanged.
* `assets/dockerignore.template` excludes `.env`, `.git`, caches, virtual
  environments, and tests.
* A new `assets/agent.yaml.template` shows a version 2 manifest for an agent
  whose context is its own folder (`context: .`, `dockerfile: Dockerfile`).
* The rule that the `hello_world` Dockerfile is the exact rendered form of the
  template is kept or explicitly relaxed; the implementation records which.

### 6. Installation at user scope

* `scripts/install_skills.sh` and its twin `scripts/install_skills.ps1`:
  * options `--dry-run`, `--uninstall`, `--target DIR` (default
    `$HOME/.agents/skills`), mirrored in PowerShell;
  * create one symlink per folder under `skills/` that contains `SKILL.md`;
  * never overwrite an existing path; a link that already points to the same
    source is reported as already installed; any other existing path is a
    conflict and the script exits non-zero;
  * `--uninstall` removes only links that point into this checkout's
    `skills/` folder;
  * modeled on `codex-4-oci-aidp/scripts/install_skills.sh`.
* On Windows the PowerShell twin creates a directory junction when a symbolic
  link needs administrator rights or Developer Mode. Codex discovery through a
  junction is **unverified** and is part of the acceptance.
* The README section "Use from other repositories" is replaced by the installer
  usage. It states that the tool home must not be moved and that a new Codex
  session is needed after installing.

### 7. Skill instructions

Every `SKILL.md` is updated as follows:

* **Tool home.** Resolve the real path of the skill folder (following the
  symlink), and take the tool home two levels above it. Run
  `"<tool home>/scripts/<name>.sh"` from the **user's current folder**. Do not
  change directory into the tool home.
* **Manifest.** Pass the manifest path exactly as the user gives it, or as an
  absolute path. The "Which agent manifest should I use?" rule of Spec 006 is
  unchanged.
* **Configuration.** Name `OCI_AGENT_ENV_FILE` and the default tenancy file.
  Remove `set -a; . ./.env` from the verification skill.
* **Permissions.** In a sandboxed session, request permission for Docker and
  network access **before** the first Docker, OCI CLI, or HTTP command, instead
  of retrying after a failure.
* **Disambiguation.** Descriptions state "container image" and "OCI Generative
  AI Hosted Applications", so that they are clearly distinct from the
  `aidp-*` skills (OCI AI Data Platform code-first agents) installed in the
  same user scope.
* **Implicit invocation.** Open decision, see below.

### 8. Tests

New or updated offline tests:

* `tests/test_agent_manifest.py`:
  * absolute and working-directory-relative manifest paths;
  * build paths relative to the manifest directory;
  * allowed root discovery through a `.git` directory and a `.git` file;
  * `OCI_AGENT_ALLOWED_ROOTS` with one and with several roots;
  * rejection of escaping paths, including through a symlink;
  * rejection of `schema_version: 1` with the migration message;
  * absolute paths returned by `get`.
* Tenancy file parsing: comments, blank lines, precedence of the process
  environment, missing keys, and no shell evaluation (a value such as
  `$(echo x)` stays literal).
* `tests/test_skills.py`:
  * every `scripts/...` path named in a `SKILL.md` exists;
  * every relative link in skills and references resolves;
  * skill names are unique and start with `oci-agent-`;
  * no `SKILL.md` tells the operator to run from the checkout root or to source
    `./.env`.
* Installer tests on a temporary target: install, repeated install, conflict,
  dry run, and uninstall that keeps foreign entries.
* `tests/test_script_parity.py` stays green, including the installer twins.
* A test runs `agent_manifest.py` and `run_manifest_checks.py` from a working
  directory outside the tool home.

## Acceptance criteria

1. The four skills can be installed and uninstalled at user scope with either
   installer, and repeated installation is idempotent.
2. From a Codex session whose workspace is a separate repository containing a
   sample agent and a version 2 manifest, the user-scope `oci-agent-build`
   skill is discovered and builds and verifies the image locally, without
   changing directory into the tool home.
3. The same session produces a push plan and a deployment plan (read-only)
   using the tenancy file of the tool home, with no exported variables.
4. With separate explicit authorizations, the sample agent is pushed, deployed,
   and verified in Frankfurt. This criterion is remote and is recorded
   separately.
5. `hello_world` still builds and verifies from this repository with its
   version 2 manifest (regression).
6. A manifest or build path outside the allowed roots is rejected with exit
   code 64 and a message naming the root.
7. No script sources or evaluates the tenancy file, and none prints its
   content.
8. Black, Pylint, pytest, Bash syntax checks, and the parity test pass. The
   PowerShell scripts are checked on Windows or recorded as unverified.
9. The README, the skill catalog, the guide, the skills, `CHANGELOG.md`, and
   Specs 001, 006, and 007 are consistent with this spec. Specs 001 and 006
   receive a note that Spec 008 supersedes their path rules.

## Implementation plan (one reviewable step each)

1. `agent_manifest.py`: version 2 path contract, allowed roots, absolute
   output, and its tests. Migrate `demos/hello_world/agent.yaml`.
2. Bash scripts: working-directory independence and `run_manifest_checks.py`
   by path.
3. Tenancy file loader and `OCI_AGENT_PYTHON` check, used by the Bash scripts.
4. PowerShell twins of steps 2 and 3.
5. Dependency split, templates, and the `hello_world` Dockerfile.
6. Installers and `tests/test_skills.py`.
7. `SKILL.md` files, references, README, catalog, guide, CHANGELOG, and the
   notes on Specs 001, 006, and 007.
8. Verification from an external repository (criteria 1–3 and 5), then the
   authorized remote run (criterion 4). Evidence goes in the verification
   record below.

## Open decisions

* **Implicit invocation of mutating skills.** Proposed:
  `allow_implicit_invocation: false` for `oci-agent-push` and
  `oci-agent-deploy`, `true` for build and verify. Once installed at user scope,
  a generic request such as "deploy the agent" could otherwise select the wrong
  family.
* **Exact-template rule** for the `hello_world` Dockerfile (section 5).

## Recovery and cleanup

* Uninstall with `scripts/install_skills.sh --uninstall` (or its twin); it
  removes only the links pointing into this checkout.
* Before merge, the stable checkout on `main` is unaffected. After merge,
  re-run the installer from the stable checkout so that the links point to it,
  then remove the development worktree.
* OCI resources created during criterion 4 follow the recovery rules of
  Specs 003 and 006; cleanup is a separate, explicitly authorized operation.

## Verification record

Pending.
