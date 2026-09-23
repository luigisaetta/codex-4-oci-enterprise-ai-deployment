# Spec 006: Windows PowerShell workflow support

Status: design revision pending implementation.
Date: 2026-09-23.

## Problem

The repository's operational interfaces are Bash scripts. They are runnable on
macOS but do not provide a native, documented Windows path, despite OCI CLI,
multiple container runtimes, and Conda being available on Windows.

## Scope

Add PowerShell 7.2+ equivalents for each Bash workflow: build environment
inspection, amd64 image build and verification, OCIR endpoint/repository
preparation, Hosted Application plan/apply, and read-only deployment
verification. Keep all existing Bash scripts unchanged for macOS. Update user
documentation and skills to select the script matching the host OS.

## Non-goals

This change does not create OCI resources, log in to a registry, push an image,
change authentication, or create a project Conda environment. It does not add
Windows PowerShell 5.1 support, because the scripts require PowerShell 7's
cross-platform process and web APIs.

## Design and safety requirements

* PowerShell scripts use the same argument names, validation, exit codes, and
  remote-mutation boundaries as their Bash counterparts where applicable.
* PowerShell 7.2+ is a visible user prerequisite. Windows PowerShell 5.1 is
  unsupported; scripts that require PowerShell 7 APIs must fail before they
  start a container or make an OCI call, with an instruction to open `pwsh`.
* Every script that needs a container runtime accepts
  `-ContainerEngine Auto|Docker|Podman`. `Auto` checks whether Docker and
  Podman are usable. It selects an engine only when exactly one is usable; if
  both or neither are usable, it stops with a clear diagnostic and asks the
  operator to choose or prepare one. It never silently prefers one engine.
* Docker Desktop is supported through the `docker` CLI. Podman on Windows/WSL
  is supported through the `podman` CLI; it does not need a Docker daemon,
  Docker API socket, or a `docker=podman` alias. Rancher Desktop may work when
  it exposes a working `docker` CLI, but is not claimed as tested until it has
  its own acceptance evidence.
* Engine-specific command construction is contained in a small shared
  PowerShell helper. Docker may use `docker buildx build`; Podman uses
  `podman build`. Both paths must build and inspect a `linux/amd64` image.
* Local HTTP verification explicitly publishes the IPv4 loopback address,
  for example `-p 127.0.0.1:8080:8080`, and probes the same `127.0.0.1`
  address. This avoids an ambiguous IPv4/IPv6 loopback mapping on
  Windows/Podman and does not expose the development server on the LAN.
* `.env` is never read automatically. Documentation shows a small parser that
  imports only non-secret `KEY=value` entries into the current process.
* OCI reads remain reads; `-Apply` and `-Create` are the only mutation switches.
  They must be used only after explicit authorization.
* Local Windows testing is recorded separately from macOS and OCI evidence.

## Acceptance criteria

1. Every `scripts/*.ps1` file parses in PowerShell 7 without executing it.
2. `-Help` works for every PowerShell script without Docker, OCI CLI, or
   credentials.
3. With `-ContainerEngine Podman`, preflight, build, and image verification
   can produce and verify `linux/amd64` `hello-world:0.1.0` using native
   Podman commands.
4. With `-ContainerEngine Docker`, the equivalent workflow can produce and
   verify the same image using Docker commands.
5. `Auto` selects a single usable engine and rejects ambiguous or unavailable
   runtime choices with an actionable message.
6. Local verification publishes explicitly to `127.0.0.1` and proves
   `/health` and `/ready` through that address.
7. OCI plan, apply, repository creation, and public deployment probes are not
   run as part of this change; their safety boundaries are reviewed statically.

## Verification record

2026-09-23 local acceptance evidence (Podman only):

* A dedicated Conda environment named `codex-4-oci-enterprise-ai-deployment`
  was created and the declared dependencies were installed without a pip
  cache. Unit tests, formatting, and linting passed.
* Native Podman 5.8.2 built `hello-world:0.1.0` for `linux/amd64`; image
  inspection reported `linux/amd64` and `uname -m` inside the container
  reported `x86_64`.
* An unqualified `-p 8080:8080` mapping was reachable only through IPv6
  loopback on this Windows host. An explicit
  `-p 127.0.0.1:8080:8080` mapping was then verified from Windows with a
  proxy-free .NET HTTP client: `/health` returned 200, `/ready` returned 200,
  and `POST /hello` returned 200.
* Temporary test containers and logs were removed; the deliberately built
  local image remains available for the next phase.
* The native verifier was run interactively in PowerShell 7.6.5 and returned
  `result=PASS` after proving `/health`, `/ready`, and `POST /hello` through
  the explicit IPv4 loopback mapping. A PowerShell 5.1 attempt was rejected
  before starting a container with a clear PowerShell 7.2+ prerequisite.
* All seven PowerShell entry scripts parsed and their `-Help` paths passed in
  PowerShell 7.6.5. The three OCI-only scripts now also reject PowerShell 5.1
  before an OCI CLI call could be made.
* The verified Windows/Podman release completed the full authorized lifecycle:
  OCIR repository creation, interactive registry login, image push, Hosted
  Application and deployment creation, and read-only public `/health` and
  `/ready` probes. The release tag was `0.1.0`; all OCI identifiers and target
  settings remain local and are intentionally absent from this repository.

No Docker Desktop or Rancher Desktop acceptance test has been run. No OCI CLI
operation, registry login, push, repository creation, deployment, or public
endpoint probe has been performed.

The OCI-adjacent deployment script was changed only by static review: its
PowerShell parser and `-Help` path passed, and it now uses the same explicit
container-engine selection for local image inspection. Its OCI plan and
`-Apply` paths were intentionally not executed.
