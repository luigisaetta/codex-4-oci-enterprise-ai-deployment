# Windows development with Rancher Desktop and WSL2

## Purpose

This note describes the supported setup for the OCI-agent workflow on a Windows workstation where Docker Desktop is not permitted.

Use **Rancher Desktop with WSL2** and the Moby (`dockerd`) container engine. This is a Linux-on-Windows workflow, not a native PowerShell workflow.

## Scope and non-goals

The project scripts are Bash scripts. Rancher Desktop supplies the container engine; WSL2 supplies the Bash and Unix environment.

No changes are needed to agent source code, Dockerfiles, `agent.yaml` manifests, OCI CLI commands, OCIR authentication, Hosted Application endpoints, or the required `linux/amd64` target platform.

The following are not supported without further implementation work:

* Native PowerShell or CMD execution of the project scripts.
* Rancher Desktop configured only with the `containerd` engine and `nerdctl`.
* Docker Desktop.

## Why Moby is required

The project invokes Docker CLI and Docker API-compatible workflows: `docker buildx build`, `docker run`, `docker image inspect`, `docker tag`, and `docker push`.

Rancher Desktop offers mutually exclusive container engines. Moby (`dockerd`) exposes the Docker API and Docker CLI. The `containerd` engine is intended for `nerdctl` and does not expose a Docker-compatible API. Select **Moby** in Rancher Desktop before using this repository.

Changing container engine or Moby image-storage driver can make previously built images unavailable to the active engine or store. Rebuild the image, or explicitly export and import it, after such a change. Do not mistake a missing local image for a missing OCIR artifact.

## Prerequisites

1. A Windows release and hardware configuration supported by Rancher Desktop. Rancher Desktop requires WSL2 on Windows.
2. Rancher Desktop is installed and running.
3. In Rancher Desktop settings, select **Container Engine: Moby (`dockerd`)**.
4. Enable Rancher Desktop integration for the chosen WSL2 distribution.
5. Install inside that WSL2 distribution: Git, Miniconda or Conda with the `codex-4-oci-enterprise-ai-deployment` environment, OCI CLI in that environment, `curl`, and the standard Bash utilities used by the scripts.
6. Configure OCI CLI authentication in the WSL2 user account. Keep OCI config, API keys, auth tokens, and the project `.env` outside version control.

The Windows user may need administrator assistance to install WSL2 or the Rancher Desktop privileged service. The privileged service is not needed for this repository's local verification because it probes a loopback port only.

## Recommended workspace layout

Clone the repository into the WSL2 Linux filesystem:

```bash
mkdir -p ~/projects
cd ~/projects
git clone <repository-url> codex-4-oci-enterprise-ai-deployment
cd codex-4-oci-enterprise-ai-deployment
```

Avoid running the normal workflow from `/mnt/c/...` when possible. A Linux filesystem checkout provides more predictable Git permissions, executable bits, file watching, and build-context performance.

Keep text files with LF line endings. In particular, do not convert Bash scripts to CRLF:

```bash
git config --global core.autocrlf input
```

## Initial validation

From WSL2, with Rancher Desktop running, confirm that the integrated Docker socket and build tooling are visible:

```bash
docker info
docker buildx version
ls -l /var/run/docker.sock
```

The socket normally appears at `/var/run/docker.sock` when WSL integration is enabled. If it is absent, confirm that Rancher Desktop is running, Moby is selected, and the distribution is enabled in Rancher Desktop's WSL integration settings.

Create the normal tenancy-only `.env` from `.env.example`, configure OCI CLI, and use the existing macOS/Linux commands. For example:

```bash
conda run -n codex-4-oci-enterprise-ai-deployment \
  bash scripts/build_image.sh \
  --manifest demos/hello_world/agent.yaml --tag 0.4.0
```

Local image verification publishes a port and probes it through `localhost`. Rancher Desktop documents this as the Windows behavior. No port proxy is needed for a probe from the same machine; a port proxy is relevant only when another machine must reach the container.

## Workflow behavior on Windows

| Workflow | Expected behavior with Rancher Desktop Moby + WSL2 |
| --- | --- |
| Build | Runs `linux/amd64` natively on typical x86_64 Windows hardware. |
| Local verification | Runs the Linux container and probes its loopback port. |
| OCIR push | Uses the same Docker login, tag, and push steps. |
| Hosted Application deploy | Uses OCI CLI from WSL2; it is independent of the local engine after the image is pushed. |
| Deployment verification | Uses OCI CLI and public `curl` probes from WSL2. |

Keep the `linux/amd64` platform flag explicit: it verifies the OCI Hosted Application target platform rather than the host operating system.

## Troubleshooting

| Symptom | Likely cause and action |
| --- | --- |
| `docker info` cannot connect | Start Rancher Desktop; select Moby; enable WSL integration; reopen the WSL shell. |
| `docker buildx` is unavailable | Update or reconfigure Rancher Desktop, then rerun `docker buildx version`. |
| Image built earlier is absent | Check whether the engine or Moby image-storage driver changed; rebuild or migrate deliberately. |
| Local health probe cannot connect | Confirm the container is running and no local policy blocks `localhost`; external exposure is unnecessary. |
| OCI CLI cannot authenticate | Configure OCI CLI and key permissions in the WSL user account; Windows-side settings are not automatically active in WSL. |
| Bash script fails with `^M` or interpreter errors | Restore LF line endings and use a WSL Linux filesystem checkout. |

## Native Windows future option

A native PowerShell implementation would require wrappers or a cross-platform rewrite for every lifecycle operation, not only image build. It would need `.env` loading, temporary-file cleanup, process handling, Docker and OCI CLI invocation, curl behavior, and automated tests. This is intentionally out of scope for the current WSL2 support.

## References

* Rancher Desktop, [Container Engine settings](https://docs.rancherdesktop.io/ui/preferences/container-engine/general/) (reviewed 2026-09-23).
* Rancher Desktop, [Working with Containers](https://docs.rancherdesktop.io/tutorials/working-with-containers/) (reviewed 2026-09-23).
* Rancher Desktop, [Windows installation requirements](https://docs.rancherdesktop.io/1.13/getting-started/installation/) (reviewed 2026-09-23).
* Rancher Desktop, [Using Testcontainers with Rancher Desktop](https://docs.rancherdesktop.io/1.24/how-to-guides/using-testcontainers/) (reviewed 2026-09-23), for the documented WSL Docker socket behavior.
