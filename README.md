# codex-4-oci-enterprise-ai-deployment

![Code style: Black](https://img.shields.io/badge/code%20style-black-000000)
![Linting: Pylint](https://img.shields.io/badge/linting-pylint-blue)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Testing: pytest](https://img.shields.io/badge/testing-pytest-0A9EDC?logo=pytest&logoColor=white)

Codex skills and reproducible demos for deploying AI agents to **OCI Enterprise
AI Hosted Applications**.

## Start here: release an agent with the four skills

Use the [step-by-step skill guide](docs/using-oci-agent-skills.md). It explains
the complete operator workflow:

1. Build and locally verify a `linux/amd64` agent image.
2. Publish that verified image to OCIR.
3. Review a deployment plan and, with explicit approval, deploy it.
4. Verify the active OCI release using `/health` and `/ready`.

Every release needs an explicit agent manifest and semantic tag. The final
verification also needs the Hosted Application OCID produced at deployment.
The guide identifies the approval boundary for every operation that changes OCI
or makes public endpoint requests.

## Before using a skill

Open this repository as the Codex workspace. Its `.agents/skills` link makes
the four skills discoverable in compatible Codex surfaces. Select a skill from
the interface, or invoke it explicitly as `$oci-agent-build`,
`$oci-agent-push`, `$oci-agent-deploy`, or
`$oci-agent-verify-deployment`.

Prepare the project Conda environment, a container engine, and OCI CLI: Docker
with Buildx and curl on macOS, Linux, or WSL2; Docker Desktop or Podman with
PowerShell 7.4+ on Windows. Every lifecycle script exists as `scripts/*.sh` and
as a `scripts/*.ps1` twin with the same options and exit codes; the skills use
whichever matches your shell.
Copy `.env.example` to the ignored `.env` and configure only these tenancy-wide,
non-secret values:

```dotenv
OCI_REGION=eu-frankfurt-1
OCI_COMPARTMENT_NAME=<target-compartment-name>
OCIR_TENANCY_NAMESPACE=<object-storage-namespace>
OCIR_USERNAME=<complete-ocir-login-username>
```

Configure OCI authentication outside the repository. Never commit or pass an
OCI auth token, password, API private key, or Docker credential in `.env`, an
agent manifest, or a command argument.

Each agent has a versioned `agent.yaml` next to its code. It holds stable
agent-specific configuration: build context, Dockerfile, local image name,
OCIR repository, Hosted Application name, optional runtime environment, and
functional checks. The version is deliberately not stored there: pass a new
semantic tag for every release.

## Skills

| Skill | Use it when | Changes state? |
| --- | --- | --- |
| [oci-agent-build](skills/oci-agent-build/SKILL.md) | Building and locally verifying an agent image. | Local Docker only. |
| [oci-agent-push](skills/oci-agent-push/SKILL.md) | Publishing a locally verified image to OCIR. | Creates a missing repository and pushes only with explicit authorization. |
| [oci-agent-deploy](skills/oci-agent-deploy/SKILL.md) | Planning or creating a Hosted Application deployment. | OCI creation only with explicit authorization. |
| [oci-agent-verify-deployment](skills/oci-agent-verify-deployment/SKILL.md) | Checking a deployed release's OCI state, health, and readiness. | Read-only OCI calls and authorized public GET probes. |

The [skill catalog](skills/README.md) contains discovery details and links to
the associated specifications. The individual `SKILL.md` files remain the
authoritative instructions for each operation.

## Example agent

[hello_world](demos/hello_world/README.md) is the reference FastAPI/LangGraph
agent. Its [manifest](demos/hello_world/agent.yaml) is an example only, not a
default selection. It provides `/hello`, `/health`, and `/ready` on port 8080.

## Project layout

| Directory | Purpose |
| --- | --- |
| `skills/` | Codex skills for lifecycle steps. |
| `demos/` | Runnable agent examples. |
| `docs/` | Operator guides and platform documentation. |
| `notes/` | Architectural and environment notes. |
| `specs/` | Specifications, acceptance criteria, and verification records. |
| `scripts/` | Shared lifecycle automation, as Bash and PowerShell twins. |
| `tests/` | Local unit tests and explicit integration-test support. |

For Windows workstations, see [native PowerShell 7](notes/windows-powershell-native.md) or [Rancher Desktop with WSL2](notes/windows-rancher-desktop-wsl2.md). For remote Linux builds, see [Linux build machine over SSH](notes/linux-build-machine-over-ssh.md).

## Working on this repository

Follow [AGENTS.md](AGENTS.md) for project conventions. Meaningful behavior
changes are specified first; documentation and code comments are written in
English. Remote OCI verification is distinct from local testing and is recorded
in the relevant specification.

## License

[MIT](LICENSE).
