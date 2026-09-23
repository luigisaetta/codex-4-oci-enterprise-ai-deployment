# Spec 007: Windows PowerShell workflow support

Status: implemented; static parity checks pass; Windows execution of the
manifest-based scripts pending.
Date: 2026-09-23.
Supersedes the draft submitted as pull request #1; delivered by pull request #3.

## Problem

The repository's operational interfaces are Bash scripts. They run on macOS
and, on Windows, only inside WSL2 (see
[Windows with Rancher Desktop and WSL2](../notes/windows-rancher-desktop-wsl2.md)).
Windows workstations that have PowerShell 7, a container engine, Conda, and
OCI CLI installed natively had no documented path.

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

### Pending

Criteria 2 to 7 for the manifest-based scripts on a Windows workstation with
PowerShell 7.4+, using at least one of Docker Desktop or Podman. Record the
PowerShell, engine, OCI CLI, and Python versions, the release tag, and the
observed report lines here when done.
