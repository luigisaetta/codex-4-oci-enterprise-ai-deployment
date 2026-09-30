# codex-4-oci-enterprise-ai-deployment

![Overview of the OCI Enterprise AI agent release workflow](docs/oci-agent-skills-overview.svg)

![Code style: Black](https://img.shields.io/badge/code%20style-black-000000)
![Linting: Pylint](https://img.shields.io/badge/linting-pylint-blue)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Testing: pytest](https://img.shields.io/badge/testing-pytest-0A9EDC?logo=pytest&logoColor=white)

Codex skills and reproducible demos for deploying AI agents to **OCI Enterprise
AI Hosted Applications**. Install the skills once, then use them from the
repository of any agent.

**New here?** The [Quickstart](docs/quickstart.md) shows how to publish an
agent, release new versions, and roll back with plain-language requests.

## How an agent release works

Four skills take one agent release from source code to a running Hosted
Application, in this order:

1. **Build**: build a `linux/amd64` image and verify it locally.
2. **Push**: publish the verified image to OCIR.
3. **Deploy**: review a deployment plan, then deploy it after your approval.
4. **Verify**: check the deployed release with `/health` and `/ready`.

### New versions and rollback

The deploy skill decides from the state in OCI what a release means:

| You deploy tag X, and… | The skill… |
| --- | --- |
| the application does not exist yet | creates the application and its deployment (first release) |
| X is already the active version | changes nothing |
| X is a new version | adds X to the existing deployment and activates it |
| X is an earlier version of this deployment | activates it again (rollback) |

* The endpoint address never changes after the first release.
* In the verified test, switching versions took about 10 seconds with no
  observed interruption.
* To roll back, deploy the previous tag.
* Old versions stay in the application, up to 20; the skills never delete
  them.

Details: [oci-agent-deploy](skills/oci-agent-deploy/SKILL.md#release-cases)
and [Spec 009](specs/009-release-new-version.md).

### What every release needs

* an agent manifest (`agent.yaml`);
* a semantic version tag, for example `0.4.0`;
* for the final verification only, the Hosted Application OCID returned by
  the deployment.

The skills ask for approval before every operation that changes OCI or calls
a public endpoint. The [Quickstart](docs/quickstart.md) is the shortest path;
the [step-by-step guide](docs/using-oci-agent-skills.md) describes each step in
detail.

For a token-protected public endpoint, use the `public-idcs` profile with an
OCI IAM identity-domain domain URL, audience, and scope in the manifest. The
identity-domain confidential application's client credentials are used only by
the verifier and are never stored in project configuration.

## Skills

| Skill | Use it to | Changes state? |
| --- | --- | --- |
| [oci-agent-build](skills/oci-agent-build/SKILL.md) | Build and locally verify an agent image. | Local Docker only. |
| [oci-agent-push](skills/oci-agent-push/SKILL.md) | Publish a locally verified image to OCIR. | Creates a missing repository and pushes, each only with your approval. |
| [oci-agent-deploy](skills/oci-agent-deploy/SKILL.md) | Plan a first release, new version, or rollback in the same Hosted Application. | Creates resources or activates artifacts only with your approval. |
| [oci-agent-verify-deployment](skills/oci-agent-verify-deployment/SKILL.md) | Check a deployed release's OCI state, health, and readiness. | Read-only OCI calls and approved public GET requests. |

Every skill can be selected from a natural request. Push and deploy still ask
for approval before each remote change. The [skill catalog](skills/README.md)
has the discovery and installation details; each `SKILL.md` is the authoritative
instruction for its operation.

## Setup

Do this once per workstation. This checkout is the **tool home**: the
installed skills point to it, so keep it where it is.

### 1. Install the prerequisites

* The Conda environment `codex-4-oci-enterprise-ai-deployment`, with
  `requirements-dev.txt` installed. It provides Python, PyYAML, and OCI CLI.
* A container engine:
  * macOS, Linux, or WSL2: Docker with Buildx, plus curl;
  * Windows: Docker Desktop or Podman, with PowerShell 7.4+.
* OCI CLI authentication, configured outside this repository.

Every script exists as a Bash version (`scripts/*.sh`) and a PowerShell twin
(`scripts/*.ps1`) with the same options and exit codes. The skills use the one
that matches your shell.

### 2. Configure the tenancy

Copy `.env.example` to `.env` (ignored by Git) and set only these non-secret
values:

```dotenv
OCI_REGION=eu-frankfurt-1
OCI_COMPARTMENT_NAME=<target-compartment-name>
OCIR_TENANCY_NAMESPACE=<object-storage-namespace>
OCIR_USERNAME=<complete-ocir-login-username>
```

The scripts read this file themselves; you do not need to export anything.

### 3. Install the skills

From this checkout:

```bash
scripts/install_skills.sh
```

* It creates one link per skill in `~/.agents/skills` and never overwrites an
  existing entry.
* Use `--dry-run` to preview and `--uninstall` to remove only this checkout's
  links. On Windows, use `scripts/install_skills.ps1`.
* Start a new Codex session afterwards.

Alternatively, skip this step and open this repository in Codex: its
`.agents/skills` link makes the skills available inside it.

## Using the skills

* Open the agent's repository in Codex.
* Describe the release in plain language, for example "Release version 0.4.0
  of this agent on OCI Hosted Applications". Codex runs build, push, deploy,
  and verification in order, and asks for approval before each remote change.
* You can also select a skill in the interface or call it by name, for example
  `$oci-agent-build ./agent.yaml tag: 0.4.0`.

To create a new agent, see
[Creating a new agent repository](docs/using-oci-agent-skills.md#creating-a-new-agent-repository)
in the guide.

## The agent manifest

Each agent must have a versioned `agent.yaml` next to its code. It contains:

* the build context and Dockerfile;
* the local image name and the OCIR repository;
* the Hosted Application name;
* an optional runtime environment;
* optional functional checks.

Rules:

* use `schema_version: 2`; build paths are relative to the manifest's folder;
* the version tag is never stored in the manifest: pass a new tag for every
  release.

## Optional settings

| Variable | Purpose | Default |
| --- | --- | --- |
| `OCI_AGENT_ENV_FILE` | Path of the tenancy file. | `.env` in the tool home. |
| `OCI_AGENT_PYTHON` | Python interpreter used by the scripts; it must provide PyYAML. | `python` |
| `OCI_AGENT_ALLOWED_ROOTS` | Absolute folders that may contain manifests and build files. | The Git repository that contains the manifest, or the manifest's folder outside Git. |

## Security rules

* Never put an OCI auth token, password, API private key, or Docker
  credential in `.env`, in a manifest, or in a command argument.
* The Docker login token is typed only at Docker's password prompt.
* For `public-idcs`, ask the identity-domain administrator for the domain URL,
  audience, scope, client ID, and client secret. Store only the non-secret
  domain URL, audience, and scope in the manifest.
* Export the identity-domain client ID and secret only in the shell that runs
  verification. Never type the client secret or access token into chat, print
  it, or store it in a file.

## Example agent

[hello_world](demos/hello_world/README.md) is the reference FastAPI/LangGraph
agent.

* It provides `/hello`, `/health`, and `/ready` on port 8080.
* Its [manifest](demos/hello_world/agent.yaml) is an example, never a default:
  the skills always ask which manifest to use.

## Project layout

| Directory | Purpose |
| --- | --- |
| `skills/` | Codex skills for the lifecycle steps. |
| `scripts/` | Lifecycle automation, as Bash and PowerShell twins. |
| `demos/` | Runnable agent examples. |
| `docs/` | Operator guides and platform documentation. |
| `notes/` | Architectural and environment notes. |
| `specs/` | Specifications, acceptance criteria, and verification records. |
| `tests/` | Local unit tests and explicit integration-test support. |

Environment-specific guides:

* Windows: [native PowerShell 7](notes/windows-powershell-native.md) or
  [Rancher Desktop with WSL2](notes/windows-rancher-desktop-wsl2.md);
* remote Linux builds: [Linux build machine over SSH](notes/linux-build-machine-over-ssh.md).

## Working on this repository

* Follow [AGENTS.md](AGENTS.md) for the project conventions.
* Specify meaningful behavior changes first, in `specs/`.
* Write documentation and code comments in English.
* Record remote OCI verification separately from local tests, in the relevant
  specification.

## License

[MIT](LICENSE).
