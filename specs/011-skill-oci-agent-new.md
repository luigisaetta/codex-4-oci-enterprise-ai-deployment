# Spec 011: skill `oci-agent-new`, author a new agent (first iteration)

Status: draft; work in progress.
Date: 2026-10-01.

## Problem

The four lifecycle skills (build, push, deploy, verify) start from an agent
repository that already has an `agent.yaml`, a `Dockerfile`, a
`.dockerignore`, a `requirements.txt`, and a container that follows the
[container requirements](../skills/oci-agent-build/references/container-requirements.md).
Today a developer prepares these files by hand, following the section
"Creating a new agent repository" of the
[step-by-step guide](../docs/using-oci-agent-skills.md#creating-a-new-agent-repository).
Mistakes surface late, during the build or the local verification, and the
tenancy file (`.env`) is discovered to be incomplete only at push time.

## Scope

This is the first iteration of a skill that authors a new agent repository
from the developer's requirements. It is documented as **work in progress**.

* A new skill, `oci-agent-new`, invoked from a plain-language request.
* Inputs: a prompt (required) and, optionally, the path of a Markdown file
  with the agent's specifications.
* Output: every file that the lifecycle skills require, in the developer's
  repository, with an agent exposed through a FastAPI HTTP API.
* A read-only check of the tenancy file used by the other skills.
* A helper script for the deterministic parts (planning, rendering the fixed
  files, checking the tenancy file), so that they can be tested offline.
* A closing message that tells the developer what to review in `agent.yaml`
  before the first build.

## Non-goals

* Calling OCI Generative AI or any other OCI service from the agent; this
  comes with the Generative AI demo (TODO item 7).
* A test UI (TODO item 9).
* The `public-idcs` profile: the generated manifest always uses
  `public-noauth`; the closing message explains how to switch later.
* Runtime environment variables, unless the inputs name them explicitly.
* Agent unit tests, a README for the agent, and a requirements file for
  development tools.
* Building, pushing, deploying, or verifying: the skill ends where the build
  skill starts. It runs no Docker or OCI CLI command and calls no network
  service.
* Editing the tenancy file, or any file in the tool home.
* Updating an existing agent repository: the skill creates files, it never
  modifies or overwrites them.
* Packages that need compilation: the base image has no compiler (Spec 001,
  decision of 2026-10-01).

## Constraints on the generated agent

These are decisions of this project, documented for developers in the guide.

| # | Constraint |
| --- | --- |
| C1 | The agent is a Python 3.11 package exposed through **FastAPI**, served by Uvicorn on `0.0.0.0:8080` (the `CMD` of the Dockerfile template). |
| C2 | `GET /health` and `GET /ready` return HTTP 200 with a JSON body. `/ready` returns non-200 until the agent is initialized. |
| C3 | Every business endpoint takes and returns JSON, validated with Pydantic models. The first iteration generates exactly one business endpoint. |
| C4 | HTTP handling (`app.py`) and agent logic (`agent.py`) are separate modules of the same package. LangGraph is used only when the inputs ask for it. |
| C5 | The container is stateless and writes only under `/tmp`. No network call and no file write at import time. |
| C6 | No credential, token, or secret in code, in `agent.yaml`, or in any generated file. |
| C7 | `requirements.txt` lists runtime dependencies only, with version ranges, starting from the ranges used by `demos/hello_world/requirements.txt`. |
| C8 | The package folder name must not be excluded by `.dockerignore` (for example it cannot be `tests`, `scripts`, `docs`, `specs`, or `skills`). |

## Prerequisites

Before starting the skill, the developer needs:

1. **A prepared workstation**, as for the other skills: the tool home in its
   place, the Conda environment `codex-4-oci-enterprise-ai-deployment`, the
   skills installed with `scripts/install_skills.sh`, and a Codex session
   started after the installation. The skill runs `new_agent.py` from the tool
   home with the Conda environment's Python.
2. **A folder dedicated to the agent, opened in Codex as the workspace**, in
   a new session. It must exist before the skill starts: Codex cannot change
   its workspace during a session, and its sandbox usually allows writes only
   inside the workspace.
3. The folder:
   * is empty, or at least contains none of the files to generate;
   * is neither the tool home nor inside it (for example not a subfolder of
     `demos/`), otherwise the agent would belong to the tool's Git repository;
   * should be a Git repository (`git init`). This is recommended, not
     required: without Git, the allowed build roots default to the manifest's
     folder.
4. **The optional specification file inside the agent folder**, so that it is
   versioned with the code and readable without extra permissions. It is not
   copied into the image: `.dockerignore` excludes `**/*.md`.

Not needed: Docker (needed by the next step, the build), OCI credentials,
network access, and a complete tenancy file (its check does not block the
authoring).

Typical preparation:

```bash
mkdir ~/Progetti/my-agent
git -C ~/Progetti/my-agent init
```

Then open `~/Progetti/my-agent` in a new Codex session and describe the agent.

## Inputs

### Prompt (required)

A plain-language request, for example: "Create an agent that receives a text
with POST /analyze and returns the number of words."

### Specification file (optional)

The path of a Markdown file written by the developer. When both are given,
the file is the primary source and the prompt adds to it. When they
conflict, the skill asks which one applies; it never chooses silently.

### Values the skill must obtain

The skill derives each value from the inputs, or asks for it. It never
invents a value that changes the agent's behavior.

| Value | Rule | Default |
| --- | --- | --- |
| Agent name | `name` and `deploy.application_name` in `agent.yaml`; manifest rule `^[A-Za-z0-9][A-Za-z0-9._-]*$`. | None: ask. |
| Package folder | Python identifier (snake_case), respecting C8. | The agent name in snake_case. |
| OCIR repository | `publish.repository`; manifest rule `^[a-z0-9][a-z0-9._/-]*$`. | `agents/<agent-name>` (lowercase). |
| Business endpoint | Method `POST`, a path, the request fields and their types, the response fields and their types. | None: ask for whatever is missing. |
| Agent behavior | What the endpoint computes, in plain language. | None: ask. |
| Functional check | One request body and the expected status; the expected JSON only when the result is deterministic. | Derived from the endpoint and behavior; shown for confirmation. |
| Runtime variables | Only those named in the inputs, with their source (`value`, `from_env`, or `vault_secret_id`). | None. |

## Requests outside the first iteration

When the inputs ask for something outside this iteration, for example a `GET`
business endpoint, more than one endpoint, streaming, file upload, or calls to
OCI Generative AI, the skill:

1. says which part of the request is outside the first iteration;
2. asks whether the developer wants to go ahead anyway.

If the developer declines, the skill stops, or continues with the supported
shape if the developer asks for it. If the developer goes ahead, Codex
implements the extra parts on its own judgment: they are not covered by the
tests or the acceptance criteria of this specification, and the closing
message says so. Constraints C1, C2, C5, C6, and C8 still apply, because the
build skill and the platform depend on them. For calls to OCI services, the
closing message also points to [IAM policies](../docs/iam-policies.md).

## Target folder

The current Codex workspace, which must be the root of the agent's
repository (see Prerequisites).

* If the folder is the tool home or inside it, `plan` rejects it (exit 64)
  and the skill stops.
* If the folder is not inside a Git repository, the skill says so and asks
  whether to continue: without Git, the allowed build roots default to the
  manifest's folder (see `OCI_AGENT_ALLOWED_ROOTS` in the README).
* If any file to be created already exists, the skill stops before writing
  anything and lists the conflicts. It never overwrites a file.
* Exception: an existing `.gitignore` (common in repositories created on a
  Git hosting service) is not a conflict. It is kept unchanged and checked
  for the required entries; the missing ones are listed in the closing
  message, and the developer adds them.

## Generated files

| File | Source | Content |
| --- | --- | --- |
| `agent.yaml` | `skills/oci-agent-build/assets/agent.yaml.template` | `schema_version: 2`, `context: .`, `profile: public-noauth`, the values above, and one `verify` check. |
| `Dockerfile` | `skills/oci-agent-build/assets/Dockerfile.template` | `{{REQUIREMENTS_PATH}}` = `requirements.txt`, `{{PACKAGE_DIR}}` = the package folder, `{{APP_MODULE}}` = `<package>.app:app`. |
| `.dockerignore` | `skills/oci-agent-build/assets/dockerignore.template` | Copied unchanged. |
| `.gitignore` | Fixed content from the helper, only when the file does not exist | The required entries: `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.venv/`, `.env`, `.env.*`. An existing file is kept and checked (see Target folder). |
| `requirements.txt` | Written by Codex within C7 | `fastapi`, `pydantic`, `uvicorn`, and only the packages the agent needs. |
| `<package>/__init__.py` | Written by Codex | Module header only. |
| `<package>/app.py` | Written by Codex within C1–C5 | FastAPI app, probes, the business endpoint, Pydantic models. |
| `<package>/agent.py` | Written by Codex within C4–C6 | The agent logic. |

The templates stay in `skills/oci-agent-build/assets/` and are the single
source: the new skill reads them, it does not copy them.

Generated Python files carry the module header of the project conventions,
with the author name taken from the inputs or left as a placeholder for the
developer.

## Tenancy file check

The lifecycle skills read the tenancy file selected by `OCI_AGENT_ENV_FILE`,
by default `.env` in the tool home. The skill checks, without changing it:

* that the file exists;
* that `OCI_REGION`, `OCI_COMPARTMENT_NAME`, `OCIR_TENANCY_NAMESPACE`, and
  `OCIR_USERNAME` are each set, either in the file or in the environment;
* that no value still starts with the placeholder prefix `replace-with-` of
  `.env.example`.

It reports only key names and the file path, never values. A failed check
does not stop the authoring: it is listed in the closing message as a
prerequisite for push and deploy.

## Helper script

`scripts/new_agent.py`, Python only: like `agent_manifest.py` and
`tool_config.py`, it runs on both macOS and Windows, so no Bash or
PowerShell twin is needed.

| Subcommand | Behavior | Writes |
| --- | --- | --- |
| `plan` | Validates the target folder (not the tool home or inside it), the agent name, package folder, and repository; lists the files to create; reports existing files as conflicts (exit 30), except an existing `.gitignore`, reported as kept, with its missing required entries. | Nothing. |
| `render` | Same checks as `plan`. Renders `agent.yaml`, `Dockerfile`, `.dockerignore`, and, when absent, `.gitignore` into the target folder from the templates. `agent.yaml` has `verify: []` and no `runtime` section. Refuses to overwrite (exit 30). If writing or the final manifest validation fails, it removes only the files created by that run. | Those files. |
| `check-manifest` | Validates the manifest with `agent_manifest.py` and requires at least one `verify` check (exit 64 otherwise). | Nothing. |
| `check-env` | Runs the tenancy file check above (exit 0 when complete, 31 otherwise). | Nothing. |

An entry of an existing `.gitignore` counts as present when a non-comment
line, with surrounding whitespace removed, equals it; `name` and `name/` are
treated as equal. The helper does not evaluate other Git ignore patterns that
might cover an entry: it reports the entry as missing, and the developer
decides.

Invalid arguments exit 64, consistent with the other scripts. Exit codes 30
and 31 are not used by any other script. After `render`, Codex adds the
functional check and the optional runtime variables directly to the new
`agent.yaml`; `check-manifest` then validates the result.

The tenancy file check reuses `tool_config.py` (`configuration_file`,
`read_configuration`), with a new read-only function that returns missing
and placeholder keys without printing values.

## Workflow of the skill

1. Target platform check: confirm the request is about an agent for OCI
   Generative AI Hosted Applications; if the request is about another
   platform, stop and ask.
2. Read the prompt and the optional specification file.
3. If part of the request is outside the first iteration, say so and ask
   whether to go ahead (see above).
4. Collect the values of the table above; ask for the missing ones in one
   message.
5. Run `new_agent.py plan`. Show the developer the values and the files to
   create, and wait for confirmation. Stop on conflicts.
6. Run `new_agent.py render`.
7. Add the functional check, and the runtime variables if any, to
   `agent.yaml`.
8. Write `requirements.txt` and the package files within C1–C8.
9. Check the generated Python files with `python -m py_compile`.
10. Run `new_agent.py check-manifest`.
11. Run `new_agent.py check-env`.
12. Print the closing message.

### Closing message

The message lists, in this order:

1. The files created, and the parts implemented outside the first iteration,
   if any.
2. **Review `agent.yaml`**, in particular:
   * whether the agent must be protected with identity-domain tokens
     (`public-idcs`). Recommended: keep `public-noauth` for the first release
     and its tests, and switch later. The access mode is fixed when the
     Hosted Application is created, so switching means a new application
     name;
   * whether the agent needs runtime environment variables that were not
     specified; see the
     [agent manifest reference](../docs/agent-manifest-reference.md);
   * whether the functional check matches the expected behavior.
3. The result of the tenancy file check, with the missing keys if any, and
   the required entries missing from an existing `.gitignore`, if any.
4. The next step, for example: "Build version 0.1.0 of this agent".

## Documentation

* `skills/oci-agent-new/SKILL.md` and `agents/openai.yaml`, following the
  structure of the other skills, including the sections "Tool home and
  working directory", "Prerequisites", and "Target platform check".
* `skills/README.md` and the README skills table: a row for the skill with
  the status "Work in progress (first iteration)".
* `docs/using-oci-agent-skills.md`: the section "Creating a new agent
  repository" points to the skill, and lists the constraints C1–C8.
* `docs/quickstart.md`: the "No agent yet?" part shows the preparation of
  the folder and a request that uses the skill.
* `CHANGELOG.md`.

## Tests (offline)

* `tests/test_new_agent.py`:
  * `plan` lists the expected files and writes nothing;
  * `plan` and `render` stop with exit 30 when a target file other than
    `.gitignore` exists, and leave it unchanged;
  * with an existing `.gitignore`, `plan` and `render` succeed, leave it
    byte-for-byte unchanged, and report its missing required entries;
  * when the final validation of `render` fails, no file created by that run
    remains, and files that existed before are untouched;
  * `render` produces a manifest that `agent_manifest.py validate` accepts,
    and a Dockerfile with no remaining `{{` placeholder;
  * `check-manifest` rejects the rendered manifest while `verify` is empty,
    and accepts it after one check is added;
  * invalid agent name, repository, or package folder (including C8) exit 64;
  * a target folder equal to the tool home, or inside it, exits 64;
  * `check-env` reports a missing key and a placeholder value by name, and
    its output contains no value from the file.
* `tests/test_skills.py`: the new skill satisfies the existing structural
  checks. The check that names the other platform's skill applies to the four
  lifecycle skills only; every skill, including the new one, keeps the
  section "Target platform check".
* Black, Pylint, and pytest pass.

## Acceptance criteria

1. The skill appears in Codex after installation with
   `scripts/install_skills.sh`, which links every folder of `skills/`.
2. From a prompt only, and from a prompt plus a specification file, the skill
   asks for the missing values instead of inventing them.
3. It never writes before the developer confirms the plan, and never
   overwrites a file.
4. A request outside the first iteration is reported, and the skill goes on
   only after the developer agrees.
5. The generated `agent.yaml` passes `new_agent.py check-manifest`.
6. **End to end, on macOS:** for one sample agent, the build skill builds and
   locally verifies the generated repository, including its functional check,
   without manual edits. Record the sample prompt, the generated file list,
   and the build result here.
7. The closing message contains the items listed above, and the tenancy file
   check never prints a value.
8. The offline tests pass.

## Verification approach

Offline tests cover the helper. Criteria 2, 3, 4, 6, and 7 need a real Codex
session in an empty Git repository, recorded below. No OCI resource is
created, so no cleanup is needed beyond deleting the sample repository.

## Open points

* Whether a later iteration generates agent unit tests and a
  `requirements-dev.txt`.
* Whether the specification file should follow a template provided by the
  skill (fixed sections), or stay free-form as in this iteration.
* Whether the skill should offer to run the build at the end, or only suggest
  it as now.

## Verification record

### 2026-10-01 — Step 1 local checks

Implemented only `scripts/new_agent.py`, the read-only
`tool_config.configuration_issues` function, and `tests/test_new_agent.py`.
The helper reads the build assets in place and performs no network calls or
remote operations. The skill and end-to-end authoring criteria remain pending.

Environment: macOS (Darwin), arm64, Conda environment
`codex-4-oci-enterprise-ai-deployment`, Python 3.11.0; Black 26.5.1,
Pylint 4.0.8, pytest 9.1.1, PyYAML 6.0.2, OCI SDK 2.187.0, OCI CLI
3.94.0. OCI SDK/CLI were not invoked. No target runtime execution or remote
compatibility is claimed.

Commands used `conda run -n codex-4-oci-enterprise-ai-deployment`:

* `black --check .`: passed; 26 files unchanged.
* `pylint scripts tests`: passed, 10.00/10. The initial run reported import,
  line-length, and duplicate-code findings, which were corrected. Its default
  cache path was not writable in the sandbox; the successful run set a
  writable `PYLINTHOME` without changing lint rules.
* `pytest -q`: passed; 224 passed, 49 skipped, one existing Starlette/AnyIO
  deprecation warning. All 49 skips have the reason `pwsh is unavailable`,
  as recorded in [Spec 007](007-windows-powershell-support.md) on 2026-10-01
  and confirmed by the review-fixes run of `pytest -q -rs` below.
* Focused `pytest -q tests/test_new_agent.py`: 60 passed. All new tests are
  offline, use temporary directories, select a temporary tenancy file, and
  clear the four tenancy environment keys before each test.

Coverage includes all eight planned files, conflict prevention for both
commands, rendering only the four fixed files, manifest-loader and CLI
validation, required functional checks, invalid arguments and names,
template-derived C8 exclusions, resolved symlink targets, missing/placeholder
tenancy keys, environment precedence, empty values, invalid UTF-8, and
configuration output without values. No generated agent artifacts were added
to the repository.

Interpretations of unspecified details (no scope deviations):

* Snake-case conversion splits CamelCase/acronym boundaries, replaces runs
  of dots, underscores, or hyphens with an underscore, and lowercases the
  result. Invalid derived identifiers (for example a name starting with a
  digit) require an explicit valid `--package`; no prefix is invented.
* The tenancy check requires the selected file to exist even when all keys
  are exported, following this specification's explicit file-existence
  requirement. Non-empty environment settings override file settings as in
  the existing scripts; placeholder detection checks those effective values.
* Manifest substitutions are quoted YAML strings so valid names such as
  `true` or `123` remain strings. The rendered manifest retains `verify: []`
  and omits `runtime`, as required for the helper rather than the completed
  agent.

### 2026-10-01 — Step 1 review fixes

Updated only `scripts/new_agent.py`, `tests/test_new_agent.py`, and this
verification record, preserving the preceding user edits to the specification.
Existing regular-file `.gitignore` files are kept byte-for-byte unchanged and
reported as `Keep`; missing exact entries are advisory. One required-entry
list supplies both the rendered content and the check. Directories and
symlinks remain conflicts. Failed writes and final validation remove only
files successfully opened exclusively by that run, including partial writes.
Removal failures identify remaining files while preserving the original error.
Invalid derived package names now explicitly recommend `--package`.

Checks ran in the same project Conda environment and local runtime recorded
above, with no OCI or network operations:

* `black --check .`: passed; 26 files unchanged.
* `pylint scripts tests`: passed, 10.00/10. A writable `PYLINTHOME` was set
  because the default cache path was not writable in the sandbox.
* `pytest -q -rs`: passed; 240 passed, 49 skipped, one existing
  Starlette/AnyIO deprecation warning. Every skip has the actual reason
  `pwsh is unavailable.` The observed breakdown is 37 in
  `test_deploy_release_cases.py`, five in `test_powershell_tool_env.py`,
  three each in `test_verify_deployment_idcs.py` and
  `test_verify_deployment_updating.py`, and one in `test_install_skills.py`.
  Spec 007 agrees on the total and reason but lists 38 deployment-case skips;
  its breakdown differs from this observed run and was not edited.
* Focused `pytest -q tests/test_new_agent.py`: 76 passed. Coverage added for
  kept ignore files with missing or complete entries, optional trailing
  slashes, comments and whitespace, directory and symlink conflicts, final
  validation rollback with and without a kept ignore file, open/write
  failures, late conflicts, cleanup failures, and explicit-package guidance.
* `git diff --check`: passed.

No new implementation ambiguities or scope deviations were identified. Remote
and end-to-end skill verification remain pending; this entry records offline
helper behavior only.

### 2026-10-01 — Step 2 local checks

Added `skills/oci-agent-new/SKILL.md` and `agents/openai.yaml`, updated
`tests/test_skills.py`, and added this record. The skill documents the twelve
authoring steps, input collection and confirmation, C1–C8, the reviewed helper
commands and exit codes, kept `.gitignore` reports, and the closing message.
Metadata uses `OCI Agent New` and enables implicit invocation. The platform
section check remains universal; only the four lifecycle skills require the
existing routing assertion. No helper, README, guide, or changelog was changed.

Checks used the same local runtime and project Conda environment recorded
above (`conda run -n codex-4-oci-enterprise-ai-deployment`):

* `black --check .`: passed; 26 files unchanged.
* `pylint scripts tests`: passed, 10.00/10. A writable `PYLINTHOME` was set
  because the default cache path is not writable in the sandbox.
* `pytest -q -rs`: passed; 241 passed, 49 skipped, one existing Starlette/AnyIO
  deprecation warning. All 49 skips report `pwsh is unavailable.`
* Skill Creator `quick_validate.py skills/oci-agent-new`: passed. Static review
  and the repository tests checked metadata, helper commands, referenced
  prerequisites and files, Markdown links, required sections, and status.
  An additional local check confirmed section order and invocation metadata.
* `scripts/install_skills.sh --dry-run`: exit 0, reports
  `would create: oci-agent-new`; the four existing lifecycle links are
  unchanged. No installation or link mutation was performed.
* `git diff --check`: passed.

No new disagreement between Spec 011 and `new_agent.py`, ambiguity, or scope
deviation was identified. These are static and offline results: actual skill
discovery after installation, real-session authoring from a prompt/specification,
and end-to-end build execution remain pending. No generated agent, Docker,
OCI, or network operation was run.
