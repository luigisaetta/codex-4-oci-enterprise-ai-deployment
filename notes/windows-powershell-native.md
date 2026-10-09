# Windows development with native PowerShell 7

## Purpose

This note describes how to run the OCI-agent workflow on a Windows workstation
from PowerShell 7, without WSL2, using the `scripts/*.ps1` twins of the Bash
scripts. See [Spec 007](../specs/007-windows-powershell-support.md) for the
design and the verification record.

Windows has two supported paths. Pick one per workstation and do not mix them
within a release:

| Path | Shell | Scripts | Container engine | Choose it when |
| --- | --- | --- | --- | --- |
| Native PowerShell (this note) | PowerShell 7.4+ (`pwsh`) | `scripts/*.ps1` | Docker Desktop or Podman | You already work in PowerShell and can install a Windows container engine. |
| WSL2 ([Rancher Desktop note](windows-rancher-desktop-wsl2.md)) | Bash inside WSL2 | `scripts/*.sh` | Rancher Desktop with Moby | Docker Desktop is not permitted or you prefer a Linux toolchain. |

The scripts are twins: same options apart from the `--name` versus `-Name`
prefix, same exit codes, same report lines. The only PowerShell-only parameter
is `-ContainerEngine Auto|Docker|Podman`.

## Prerequisites

1. **PowerShell 7.4 or later.** Open `pwsh`, not the legacy *Windows
   PowerShell* 5.1, and check:

   ```powershell
   $PSVersionTable.PSVersion
   ```

   If the major version is `5`, install PowerShell 7 through your
   organisation's approved route. 7.6 is the current LTS release; 7.4 is the
   minimum and is supported until 2026-11-10. Every script stops with exit
   code 64 on an older version before touching a container or OCI.
2. **One container engine.** Docker Desktop (with Buildx) or Podman with a
   running Podman machine. Confirm with `docker info` or `podman info`. If both
   are usable, pass `-ContainerEngine Docker` or `-ContainerEngine Podman`
   explicitly; `Auto` refuses to guess.
3. **The project Conda environment** named
   `codex-4-oci-enterprise-ai-deployment` with `requirements-dev.txt`
   installed. It provides `python` with PyYAML for the manifests and the OCI
   CLI (`oci`). Activate it in the same `pwsh` session before running a script,
   for example with `conda activate codex-4-oci-enterprise-ai-deployment`.
4. **OCI CLI authentication** configured in your Windows user profile, outside
   the repository.
5. **Script execution allowed.** If `pwsh` refuses to run `.ps1` files because
   of the execution policy, follow your organisation's guidance; a common
   per-user setting is `RemoteSigned`.

Clone the repository anywhere on a local NTFS drive. The PowerShell scripts do
not depend on line endings, but keep the repository's LF endings so the Bash
scripts stay usable from WSL2 or macOS.

## Tenancy file

The scripts read the tenancy file themselves: `OCI_AGENT_ENV_FILE` if set,
otherwise `.env` in the checkout folder. They read only `OCI_REGION`,
`OCI_COMPARTMENT_NAME`, `OCIR_TENANCY_NAMESPACE`, and `OCIR_USERNAME`, and a
value already set in the session takes precedence. Do not import the file into
the session yourself, and never add an auth token, password, or private key
to it.

To select a non-default OCI CLI profile, set `OCI_CLI_PROFILE` in the session
(for example `$env:OCI_CLI_PROFILE = 'MY_PROFILE'`); the scripts do not read it
from the tenancy file.

## Workflow

Run from the repository root with the Conda environment active. Replace the
tag with the release you are producing; `0.4.0` is an example.

```powershell
# Step 1: preflight, build, and local verification
.\scripts\check_build_env.ps1 -ContainerEngine Auto
.\scripts\build_image.ps1 -Manifest demos/hello_world/agent.yaml -Tag 0.4.0 -ContainerEngine Auto
.\scripts\verify_image.ps1 -Manifest demos/hello_world/agent.yaml -Tag 0.4.0 -ContainerEngine Auto

# Step 2: publish to OCIR (plan, repository check, interactive login, authorized push)
$OCIR_REGISTRY = .\scripts\resolve_ocir_registry.ps1
.\scripts\push_ocir_image.ps1 -Manifest demos/hello_world/agent.yaml -Tag 0.4.0 -ContainerEngine Auto
.\scripts\ensure_ocir_repository.ps1 -Repository agents/hello-world            # exit 20 = absent
.\scripts\ensure_ocir_repository.ps1 -Repository agents/hello-world -Create    # only after authorization
# The scripts do not export OCIR_USERNAME; read it from the session or the tenancy file.
$ocirUsername = if ($env:OCIR_USERNAME) { $env:OCIR_USERNAME } else {
  (python .\scripts\tool_config.py env --keys OCIR_USERNAME) -replace '^OCIR_USERNAME=', ''
}
docker login --username $ocirUsername $OCIR_REGISTRY                           # or: podman login ...
.\scripts\push_ocir_image.ps1 -Push -Manifest demos/hello_world/agent.yaml -Tag 0.4.0 -ContainerEngine Auto

# Step 3: plan, then create the Hosted Application release
.\scripts\deploy_hosted_application.ps1 -Manifest demos/hello_world/agent.yaml -Tag 0.4.0
.\scripts\deploy_hosted_application.ps1 -Apply -Manifest demos/hello_world/agent.yaml -Tag 0.4.0   # only after authorization

# Step 4: verify the deployed release (OCI reads and public GET probes only)
.\scripts\verify_deployment.ps1 -ApplicationId <application-ocid> -Manifest demos/hello_world/agent.yaml -Tag 0.4.0
```

Enter the OCI auth token only at the `docker login` or `podman login` password
prompt. `-Create`, `-Push`, and `-Apply` change remote state and are meant to
be run only after the explicit authorization the skills ask for. Local
verification publishes the container port on `127.0.0.1` only, so it is not
reachable from other machines.

## Behaviour differences from the Bash scripts

| Topic | Bash | PowerShell |
| --- | --- | --- |
| Container engine | Docker only. | Docker or Podman through `-ContainerEngine`; `Auto` requires exactly one usable engine. |
| Build log | Streamed while building. | Printed when the build finishes; the build still has the `BUILD_TIMEOUT_SECONDS` bound (default 1800). |
| HTTP probes | `curl`. | .NET `HttpClient` or `Invoke-WebRequest`; `curl` is not required. Report keys stay `health_curl_exit` and `ready_curl_exit` for parity. |
| Loopback | `127.0.0.1:<port>` probe, unqualified publish. | Publish and probe both on `127.0.0.1`. |
| `-Builder` | Any buildx builder. | Docker only; rejected with Podman (exit 64). |

Everything else, including exit codes and report lines, is intended to be
identical. The parity test in `tests/test_script_parity.py` keeps the option
sets aligned.

## Troubleshooting

| Symptom | Likely cause and action |
| --- | --- |
| `PowerShell 7.4 or later is required` | You are in Windows PowerShell 5.1 or an old `pwsh`. Open PowerShell 7 (`pwsh`) and rerun. |
| `Both Docker and Podman are usable` | Pass `-ContainerEngine Docker` or `-ContainerEngine Podman`. |
| `No usable container engine was found` | Start Docker Desktop or the Podman machine, then rerun `docker info` or `podman info`. |
| `Python with PyYAML is required. Activate the Conda environment codex-4-oci-enterprise-ai-deployment or set OCI_AGENT_PYTHON.` or a Microsoft Store window opens | The Conda environment is not active in this `pwsh` session; `python` resolves to the Store alias. Activate the environment, or set `OCI_AGENT_PYTHON` to its `python.exe`. |
| `Missing required tool: oci` | Same cause: OCI CLI lives in the Conda environment. |
| `Missing configuration key(s): ...` (exit 64) | A tenancy setting is neither in the session nor in the tenancy file named in the message. |
| `Manifest error: ...` (exit 64) | The manifest file is not found (paths are relative to the current folder, or absolute), a build path leaves the allowed roots, or the file fails validation; the message names the field. |
| Health probe times out but the container runs | Check that nothing else listens on the port and that a local policy does not block `127.0.0.1`. |
| OCI CLI argument or JSON errors | Confirm `$PSNativeCommandArgumentPassing` is `Windows` or `Standard` (the 7.3+ default) and that `oci` resolves to `oci.exe`, not a `.cmd` shim. |

## Status

The native PowerShell path was verified on Windows with PowerShell 7.6.5,
Podman 5.8.2, OCI CLI 3.94.0, and Python 3.11.16. The manifest-based build,
local verification, OCIR push, update of an existing Hosted Application, remote
health/readiness checks, and functional POST passed. A first Hosted Application
creation was blocked by the tenancy's application limit, so that case remains
unverified in this pilot. The `oci-agent-new` plan and render also succeeded
on Windows for a separate agent folder; its generated code passed local syntax,
manifest, and HTTP checks, but was not built or deployed. See
[Spec 007](../specs/007-windows-powershell-support.md) and the
[pilot record](../docs/windows-ace-pilot.md).

## References

* Microsoft, [PowerShell support lifecycle](https://learn.microsoft.com/en-us/powershell/scripting/install/powershell-support-lifecycle) (reviewed 2026-09-23): 7.2 and 7.3 out of support; 7.4 LTS until 2026-11-10; 7.6 current LTS.
* Microsoft, [about_Preference_Variables](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_preference_variables) (reviewed 2026-09-23): `$PSNativeCommandArgumentPassing` (7.3+, `Windows` default on Windows) and `$PSNativeCommandUseErrorActionPreference` (default `$false`).
