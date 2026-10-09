# Spec 007: Windows PowerShell workflow support

Status: implemented; static parity checks pass; Windows build, local image
verification, OCIR push, Hosted Deployment update, HTTP health/readiness, and
the example's functional remote check executed on 2026-10-08.
Date: 2026-09-23.
Supersedes the draft submitted as pull request #1; delivered by pull request #3.

> Superseded implementation note (2026-09-29): Spec 008 removes PowerShell
> repository-root path joining and uses `scripts/lib/ToolEnvironment.psm1` for
> interpreter selection and tenancy loading.

## Problem

The repository's operational interfaces are Bash scripts. They run on macOS
and, on Windows, only inside WSL2 (see
[Windows with Rancher Desktop and WSL2](../notes/windows-rancher-desktop-wsl2.md)).
Windows workstations that have PowerShell 7, a container engine, Conda, and
OCI CLI installed natively had no documented path.

A pilot on 2026-10-08 found a second problem: on Windows, the OCI CLI starts
Windows PowerShell 5.1 to check the permissions of its key files. Started from
PowerShell 7, that child inherits PowerShell 7 module paths, fails to load
`Microsoft.PowerShell.Security`, and prints `Get-Acl` errors, although the OCI
request itself succeeds. The child also loads the user's Windows PowerShell
profile, whose Conda initialization can conflict with the active environment.

## Scope

Add a PowerShell 7 twin for every Bash lifecycle script: build environment
preflight, `linux/amd64` image build and local verification, OCIR endpoint and
repository preparation, guarded OCIR push, Hosted Application plan/apply, and
read-only deployment verification. Keep the Bash scripts unchanged. Let the
four skills document a single workflow and select the script family from the
shell in use.

## Non-goals

* Change agent source, Dockerfiles, `agent.yaml` manifests, OCI CLI usage,
  OCIR authentication, or Hosted Application endpoints.
* Support Windows PowerShell 5.1 or `cmd.exe`.
* Add a third implementation (for example a Python entry point) that would
  replace both script families.
* Create OCI resources, log in to a registry, or push an image as part of the
  change itself.

## Design

### Parity, not duplication

Every `scripts/<name>.sh` has a `scripts/<name>.ps1` twin that accepts the
same options in PowerShell form (`--timeout-seconds` becomes
`-TimeoutSeconds`, `--apply` becomes `-Apply`), prints the same report lines,
and returns the same exit codes. `tests/test_script_parity.py` parses each
Bash `usage()` function and each PowerShell `param()` block and fails when the
option sets differ. The only PowerShell-only parameter is
`-ContainerEngine Auto|Docker|Podman`; the Bash scripts remain Docker-only.

Because of this parity, each `SKILL.md` documents one workflow with Bash
examples and a short shell-selection rule. The rule is defined once in
[the skill catalog](../skills/README.md#choosing-bash-or-powershell): Bash or
zsh run `scripts/*.sh`; PowerShell 7.4+ runs `scripts/*.ps1`. The decision is
made on the shell, not the operating system, so a WSL2 session on Windows
correctly uses the Bash scripts.

### Manifest access

The PowerShell scripts do not reimplement manifest handling. A small module,
`scripts/lib/AgentManifest.psm1`, calls `scripts/agent_manifest.py` and
`scripts/run_manifest_checks.py` through the same `python` that the Bash
scripts use, and propagates their exit codes (64 for manifest errors) exactly
as `set -e` does in Bash. Manifest paths stay repository-root-relative; the
build script resolves them against the checkout root so the current directory
does not matter.

### Container engine selection

`scripts/lib/ContainerEngine.psm1` resolves the engine. `Auto` selects Docker
or Podman only when exactly one of them is usable (`<engine> info` succeeds);
when both or neither are usable it stops with an actionable message and never
silently prefers one. Docker uses `docker buildx build --load`; Podman uses
`podman build`. Both build and inspect `linux/amd64` images. `-Builder` is
accepted only with Docker.

### Local verification on Windows

Local verification publishes the container port on the IPv4 loopback only
(`-p 127.0.0.1:<port>:8080`) and probes `http://127.0.0.1:<port>` with a
proxy-free .NET HTTP client. An unqualified `-p 8080:8080` mapping was
reachable only through IPv6 loopback on the Windows/Podman host used for the
original acceptance; the explicit address avoids the ambiguity and keeps the
development server off the LAN.

### Minimum PowerShell version

The scripts require PowerShell 7.4 or later and stop with exit code 64 before
any container or OCI action otherwise. Reasons, verified against Microsoft
documentation on 2026-09-23:

* PowerShell 7.2 reached end of support on 2024-11-08 and 7.3 on 2024-05-08;
  7.4 is the LTS release supported until 2026-11-10 and 7.6 is the current
  LTS release
  ([support lifecycle](https://learn.microsoft.com/en-us/powershell/scripting/install/powershell-support-lifecycle)).
* PowerShell 7.3 introduced `$PSNativeCommandArgumentPassing`, which on
  Windows defaults to `Windows` mode and quotes arguments for native
  executables correctly. The scripts pass JSON documents and JMESPath queries
  containing double quotes to the OCI CLI; under the earlier `Legacy`
  behaviour those quotes could be lost
  ([about_Preference_Variables](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_preference_variables)).
* The scripts set `$PSNativeCommandUseErrorActionPreference = $false` and
  check `$LASTEXITCODE` explicitly, so their behaviour does not depend on a
  user profile changing that 7.4 preference.

### OCI CLI under PowerShell 7 (added 2026-10-08)

An explicit installer, `scripts/install_oci_powershell_hook.ps1`, copies an
activation and a deactivation hook into the named Conda environment. The
environment can be shared with other projects, so every change is reversible:

* activation sets a Windows PowerShell-compatible module path in the current
  shell only, and deactivation restores the previous value;
* the installer rejects any other environment and refuses to replace a hook
  that differs from the project's unless `-Update` is passed;
* if the user's Windows PowerShell profile contains exactly one standard
  Conda initialization block, the installer saves a backup and guards the
  block so that it is skipped while this environment is active; customized
  profiles need manual review;
* it never changes OCI credentials, file ACLs, machine-wide profiles, or Bash
  behavior.

Acceptance: from a fresh PowerShell 7.4+ shell, activate the environment, run
`oci os ns get` without `Get-Acl` errors, deactivate, and confirm the original
module path is restored.

References verified on 2026-10-08:
[Microsoft module-path inheritance](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_psmodulepath?view=powershell-7.6),
[Conda activation scripts](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html),
and [OCI CLI issue #655](https://github.com/oracle/oci-cli/issues/655).

### Safety boundaries

Unchanged from the Bash scripts. `-Create`, `-Push`, and `-Apply` are the
only remote-mutation switches and are meant to be used after explicit
authorization. `.env` is never read automatically; the documentation shows a
small importer for non-secret `KEY=value` lines. No credential is accepted as
a parameter; registry login is an interactive `docker login` or
`podman login` performed by the operator.

## Acceptance criteria

1. `tests/test_script_parity.py` passes: every `scripts/*.sh` has a `.ps1`
   twin and the option sets match apart from `-ContainerEngine` and `-Help`.
2. Every `scripts/*.ps1` parses in PowerShell 7.4+ and its `-Help` path works
   without Docker, Podman, OCI CLI, or credentials.
3. Every script rejects PowerShell 5.1 with exit code 64 before starting a
   container or calling OCI.
4. With `-ContainerEngine Podman`, and separately with `-ContainerEngine
   Docker`, `build_image.ps1` and `verify_image.ps1` build and verify
   `hello-world:<tag>` from `demos/hello_world/agent.yaml`, including the
   manifest functional check and `runtime.env` injection.
5. `Auto` selects a single usable engine and rejects ambiguous or unavailable
   choices with an actionable message.
6. Local verification publishes to `127.0.0.1` only and proves `/health` and
   `/ready` through that address.
7. `push_ocir_image.ps1`, `ensure_ocir_repository.ps1`,
   `deploy_hosted_application.ps1`, and `verify_deployment.ps1` produce the
   same plan output, mutation prompts, and exit codes as their Bash twins for
   one authorized release.

## Verification record

### 2026-10-01, macOS, skipped tests

* `pytest -q -rs` in the project Conda environment reports 164 passed and 49
  skipped. All 49 skips have the reason `pwsh is unavailable`:
  `test_deploy_release_cases.py` 38, `test_powershell_tool_env.py` 5,
  `test_verify_deployment_updating.py` 3, `test_verify_deployment_idcs.py` 3,
  `test_install_skills.py` 1. No test is skipped for another reason, so
  installing PowerShell 7 on macOS would run all of them.

### 2026-09-23, macOS, static

* Criterion 1 passes: `pytest tests` reports 32 passed in the project Conda
  environment, including the parity tests.
* Every `.ps1` was reviewed line by line against its `.sh` twin for option
  handling, exit codes, report format, and mutation boundaries.
* No PowerShell interpreter, Podman, or OCI CLI was available on the
  authoring machine; criteria 2 to 7 could not be executed there.

### 2026-09-23, Windows, pre-manifest draft (pull request #1)

Recorded from the original contribution, which targeted the environment-driven
scripts that preceded the agent manifests. It establishes that the engine
selection, the PowerShell version guard, the loopback mapping, and the
end-to-end OCI flow work on Windows; it does not cover the manifest-based
parameters delivered here.

* PowerShell 7.6.5 and native Podman 5.8.2 built `hello-world:0.1.0` for
  `linux/amd64`; `uname -m` inside the container reported `x86_64`.
* An unqualified `-p 8080:8080` mapping was reachable only through IPv6
  loopback; `-p 127.0.0.1:8080:8080` was verified with `/health` 200,
  `/ready` 200, and `POST /hello` 200.
* A Windows PowerShell 5.1 attempt was rejected before any container started.
* The release completed the authorized lifecycle: OCIR repository creation,
  interactive registry login, push, Hosted Application and deployment
  creation, and public `/health` and `/ready` probes. Identifiers remain
  local and are intentionally absent from this repository.
* Docker Desktop and Rancher Desktop through the `docker` CLI were not
  acceptance-tested.

### Pending as of 2026-09-23

Criteria 2 to 7 for the manifest-based scripts on a Windows workstation with
PowerShell 7.4+, using at least one of Docker Desktop or Podman. Record the
PowerShell, engine, OCI CLI, and Python versions, the release tag, and the
observed report lines here when done.

### 2026-10-08, Windows, OCI CLI activation hooks

All three PowerShell scripts parsed. A
direct hook round trip removed and restored the process module path, including
repeated activation. That initial implementation did not pass the participant's
OCI check and has been revised to set a compatible module path. The installer
copied both hooks into the already existing
named environment without replacing other activation scripts. An isolated
PowerShell 7 session then activated the environment, selected its Python
executable, and resolved `Get-Acl`. A participant run of `oci os ns get` after
fresh activation remains the final acceptance check.

2026-10-08 verification update: the participant's fresh activation still
produced Get-Acl warnings after the module path revision. The remaining cause
was the Conda initialization block in the Windows PowerShell 5.1 user profile.
The original profile was backed up and the block was guarded using the hook's
temporary marker. With the installed hooks and guarded profile, an isolated
PowerShell 7 activation and full read-only `oci os ns get` returned namespace
JSON without warnings. Deactivation restored the previous module path and
removed the marker. The installer was rerun with `-Update` and did not create
another profile backup. The participant's own terminal has not yet rerun the
final combination.

### 2026-10-08, manifest-based Podman release

PowerShell 7.6.5 with Podman 5.8.2 built and locally verified the manifest
example as `linux/amd64`; the Windows OCIR push, Hosted Deployment update,
read-only state verification, public health/readiness checks, and the
manifest's functional POST all passed. OCI CLI was 3.94.0 and the named Conda
environment used Python 3.11.16. See the sanitized
  [pilot record](../docs/windows-ace-pilot.md) for the quota obstacle and
PowerShell CLI-argument fix. Docker Desktop, WSL2, a first Hosted Application
creation, and a fresh workstation
remain untested; the Bash twins were not rerun on Windows.

The subsequent local Windows handoff run confirmed skill discovery from a
separate agent workspace. Test fixtures were adjusted so the PowerShell
scenarios use a Windows-executable fake OCI command that preserves JSON
arguments, while POSIX Bash scenarios are skipped on native Windows. The
focused PowerShell deploy tests passed (37), the PowerShell wait/recovery
tests passed (82), and the agent/PowerShell baseline suite passed (110).
Black and Pylint passed for the edited Python tests. See the pilot record
for the test environment qualification.

### 2026-10-08, beginner setup documentation scope

Superseded on 2026-10-09: Getting started is now split into one complete guide
per operating system (`docs/getting-started-macos-linux.md` and
`docs/getting-started-windows.md`); the Windows guide carries the content
below.

The Windows usability pilot starts at Getting Started, step 1. That step
currently assumes Docker and defers Windows instructions to the end of the
guide. Update only the basic-tools section and its introductory navigation:
show macOS/Linux and native Windows shell choices, PowerShell 7.4+, Docker or
Podman checks, reuse of existing installations, expected results, and recovery
from an unavailable container engine. Keep later setup steps for subsequent
pilot sessions. No lifecycle script or remote resource changes are included.

Acceptance: both shell paths have actionable basic-tool checks; Podman users
are not required to install Docker; an installed client is distinguished from
a reachable engine; checks in Codex's shell do not prove that the user's own
terminal has the same tools. Review links, Markdown, and consistency with the
current scripts. Record local observations in
[the Windows pilot log](../docs/windows-ace-pilot.md); manifest-based build and
deployment acceptance remains pending.

Authoritative references reviewed on 2026-10-08:

* [Git installation](https://git-scm.com/install/).
* [Conda installation](https://docs.conda.io/projects/conda/en/stable/user-guide/install/index.html).
* [PowerShell installation on Windows](https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows).
* [Docker Desktop](https://docs.docker.com/desktop/) and
  [Windows installation](https://docs.docker.com/desktop/setup/install/windows-install/).
* [Podman Desktop on Windows](https://podman-desktop.io/docs/installation/windows-install),
  [Podman info](https://docs.podman.io/en/latest/markdown/podman-info.1.html),
  [machine listing](https://docs.podman.io/en/latest/markdown/podman-machine-list.1.html),
  and [machine start](https://docs.podman.io/en/latest/markdown/podman-machine-start.1.html).
* [Official OpenAI quickstart](https://learn.chatgpt.com/docs/quickstart)
  for desktop installation and sign-in.

Documentation verification: `git diff --check` passed; Markdown code fences
are balanced and relative file links resolve in the edited guide, this
specification, and the pilot log. The instructions were reviewed against the
existing shell-selection rules. No lifecycle scripts changed. Step 1 local
acceptance passed: the participant confirmed PowerShell, Git, Conda, and
Podman engine connectivity in their own terminal. See the pilot log for
versions and the resolved engine connection failure. This does not establish
manifest-based build or deployment acceptance.

2026-10-08 follow-up: ordinary Conda activation selected Python 3.11.16.
The participant verified a namespace read without warnings through directly
started Windows PowerShell. Getting Started now documents this connection
workaround and the module-path inheritance cause described by
[Microsoft](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_psmodulepath?view=powershell-7.6),
reviewed on 2026-10-08. Later in the pilot, the participant confirmed that
direct `oci os ns get` worked without warnings after the Conda activation
hook and profile adjustment described in
[Getting started on Windows](../docs/getting-started-windows.md#3-create-the-python-environment-and-install-the-libraries).
See the pilot log for observed paste issues and the limits of offline
permission-check diagnostics.
