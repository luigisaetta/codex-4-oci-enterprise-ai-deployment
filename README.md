# Codex Skills for OCI Enterprise AI Deployment

**Ship AI agents to OCI Enterprise AI Hosted Applications with plain-language
requests to Codex.**

![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Target: OCI Hosted Applications](https://img.shields.io/badge/target-OCI%20Hosted%20Applications-C74634)
![Platforms: macOS, Linux, Windows](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Code style: Black](https://img.shields.io/badge/code%20style-black-000000)
![Linting: Pylint](https://img.shields.io/badge/linting-pylint-blue)
![Testing: pytest](https://img.shields.io/badge/testing-pytest-0A9EDC?logo=pytest&logoColor=white)

![Overview of the OCI Enterprise AI agent release workflow](docs/oci-agent-skills-overview.svg)

Install the skills once, then use them from the repository of any agent: Codex
creates the agent, builds and publishes its image, deploys it, and verifies
the release, asking for your approval before every change in OCI.

**New here?** Start with the [Quickstart](docs/quickstart.md).

## Why use it

* **Plain language.** "Release version 0.2.0 of this agent" runs the whole
  chain: build, push, deploy, verify.
* **Plan first, then approve.** Every remote change is shown before it
  happens and runs only after your explicit approval.
* **Versions and rollback in place.** New versions and rollbacks reuse the
  same Hosted Application, so the endpoint never changes.
* **One manifest per agent.** `agent.yaml` describes build, publish, deploy,
  runtime variables, and functional checks; the version tag is always explicit.
* **Bash and PowerShell.** Every lifecycle script has twins with the same
  options and exit codes, for macOS, Linux, WSL2, and Windows.

## From a prompt to a running agent

```mermaid
flowchart LR
    You(["You describe the agent"]) --> New["<b>oci-agent-new</b><br/>create the repository"]
    New --> Build["<b>oci-agent-build</b><br/>build and verify locally"]
    Build -- "your approval" --> Push["<b>oci-agent-push</b><br/>publish to OCIR"]
    Push -- "your approval" --> Deploy["<b>oci-agent-deploy</b><br/>plan, then deploy"]
    Deploy --> Verify["<b>oci-agent-verify-deployment</b><br/>check the release"]
    Verify --> Live(["Agent live on OCI"])
```

| Skill | What it does | Changes |
| --- | --- | --- |
| [oci-agent-new](skills/oci-agent-new/SKILL.md) | Creates an agent repository from a prompt or a specification file: `agent.yaml`, `Dockerfile`, a FastAPI app, and functional checks. | Local files only. |
| [oci-agent-build](skills/oci-agent-build/SKILL.md) | Builds a `linux/amd64` image and verifies it locally, read-only, with its functional checks. | Local Docker only. |
| [oci-agent-push](skills/oci-agent-push/SKILL.md) | Publishes the verified image to OCIR. | Creates a missing repository and pushes, each only with your approval. |
| [oci-agent-deploy](skills/oci-agent-deploy/SKILL.md) | Plans the release from the state in OCI, then deploys it and waits for the outcome. | Creates or updates OCI resources only with your approval. |
| [oci-agent-verify-deployment](skills/oci-agent-verify-deployment/SKILL.md) | Checks the deployed release: OCI state, `/health`, `/ready`, and optional functional checks. | Read-only OCI calls and approved endpoint calls. |

The [skill catalog](skills/README.md) explains discovery, installation, and the
Bash/PowerShell mapping; each `SKILL.md` is the authoritative instruction.

## Talk to Codex

Open your agent's repository in Codex and ask:

| You say | What happens |
| --- | --- |
| "Create a new OCI agent: POST /analyze receives a text and returns the number of words." | `oci-agent-new` asks for anything missing, shows the files it will create, then writes them. |
| "Release version 0.1.0 of this agent on OCI Hosted Applications." | Build, push, deploy, and verify, with an approval before each change in OCI. |
| "Release version 0.2.0 of this agent on OCI Hosted Applications." | The new version replaces the old one in the same application; the endpoint stays the same. |
| "Deploy version 0.1.0 of this agent again. Deploy only: do not build or push." | Rollback: the earlier version becomes active again. |
| "Verify the deployment of this agent, version 0.2.0, and also run its functional checks." | Read-only checks of OCI state, probes, and functional checks. |

You can also call a skill by name, for example
`$oci-agent-build ./agent.yaml tag: 0.4.0`.

## Release lifecycle

The deploy skill decides from the state in OCI what each release means:

```mermaid
stateDiagram-v2
    direction LR
    [*] --> Creating: First release
    Creating --> Active: creation completes
    Creating --> Failed: OCI reports FAILED
    Active --> Active: new version, or rollback to an earlier tag
    Failed --> Creating: you ask for a new deploy and approve the replacement
```

* **Already released**: deploying the active tag changes nothing.
* **Waiting**: the deploy waits for OCI and shows progress; if its timeout
  expires (exit 26), OCI is still working and running the deploy again
  resumes the wait.
* **Failed deployment**: the deploy reports the OCI error and stops. Only if
  you ask for a new deploy, and approve the plan, does it replace the failed
  deployment.
* Old versions stay in the application, up to 20, ready for rollback.

All cases and their exact names:
[release cases](skills/oci-agent-deploy/SKILL.md#release-cases).

## Setup

Do this once per workstation. This checkout is the **tool home**: the
installed skills point to it, so keep it where it is.

**1. Install the prerequisites**

* The Conda environment `codex-4-oci-enterprise-ai-deployment`, with
  `requirements-dev.txt` installed. It provides Python, PyYAML, and OCI CLI.
* A container engine: Docker with Buildx and curl on macOS, Linux, or WSL2;
  Docker Desktop or Podman with PowerShell 7.4+ on Windows.
* OCI CLI authentication, configured outside this repository.
* IAM policies for your group and for the Hosted Applications, set up once by
  a tenancy administrator: see [IAM policies](docs/iam-policies.md).

**2. Configure the tenancy**

Copy `.env.example` to `.env` (ignored by Git) and set the tenancy values; the
scripts read the file themselves:

```dotenv
OCI_REGION=eu-frankfurt-1
OCI_COMPARTMENT_NAME=<target-compartment-name>
OCIR_TENANCY_NAMESPACE=<object-storage-namespace>
OCIR_USERNAME=<complete-ocir-login-username>
```

The same file can hold the secrets your agents need, for example
`GENAI_API_KEY=<your-key>` for an agent that calls an LLM. The tool uses it
only to fill `from_env` entries of agent manifests, and during a deploy to mask
it in error messages; it never adds it to your shell or prints it. Once a secret is in `.env`, never share or commit the file.

**3. Install the skills**

```bash
scripts/install_skills.sh
```

It links each skill into `~/.agents/skills` and never overwrites an existing
entry; `--dry-run` previews and `--uninstall` removes only this checkout's
links. On Windows, use `scripts/install_skills.ps1`. Start a new Codex session
afterwards.

**4. Check the setup**

```bash
scripts/check_setup.sh
```

It runs the existing read-only checks (tenancy file, Docker build environment,
OCI CLI and region, installed skills) and reports each one as `PASS` or
`FAIL`. Add `--manifest ./agent.yaml` from an agent folder to also check its
manifest, compartment, and OCIR repository, and `--skills-target DIR` for
skills installed elsewhere, for example `~/.claude/skills`. On Windows, use
`scripts/check_setup.ps1`.

<details>
<summary>Optional settings</summary>

| Variable | Purpose | Default |
| --- | --- | --- |
| `OCI_AGENT_ENV_FILE` | Path of the tenancy file. | `.env` in the tool home. |
| `OCI_AGENT_PYTHON` | Python interpreter used by the scripts; it must provide PyYAML. | `python` |
| `OCI_AGENT_ALLOWED_ROOTS` | Absolute folders that may contain manifests and build files. | The Git repository that contains the manifest, or the manifest's folder outside Git. |

Opening this repository itself in Codex also works without installation: its
`.agents/skills` link makes the skills available inside it.

</details>

<details>
<summary>Windows and remote Linux builds</summary>

* Windows: [native PowerShell 7](notes/windows-powershell-native.md) or
  [Rancher Desktop with WSL2](notes/windows-rancher-desktop-wsl2.md).
* Remote Linux builds: [Linux build machine over SSH](notes/linux-build-machine-over-ssh.md).

</details>

## The agent manifest

Every agent has a versioned `agent.yaml` next to its code:

```yaml
schema_version: 2
name: hello-world
build:
  context: .
  dockerfile: Dockerfile
publish:
  repository: agents/hello-world
deploy:
  application_name: hello-world
  profile: public-noauth        # or public-idcs: callers need a JWT token
runtime:
  env:
    - name: LOG_LEVEL
      value: INFO
    - name: GENAI_API_KEY
      from_env: GENAI_API_KEY   # from your shell, or from the tool's .env
verify:
  - method: POST
    path: /hello
    body: {name: Luigi}
    expect_status: 200
```

The version tag is never stored in the manifest: pass a new one for every
release. Every field, with complete examples for both access modes, is in the
[agent manifest reference](docs/agent-manifest-reference.md).

## Security

> [!IMPORTANT]
> Nothing changes in OCI without your explicit approval. The skills show a
> plan first, and a request to deploy never authorizes a push on its own.

> [!WARNING]
> Never put a secret in `agent.yaml`, in a command argument, or in the chat.
> Agent secrets such as `GENAI_API_KEY` go only in your shell or in the tool's
> `.env`, which is never shared or committed. Never put an OCI auth token, OCI
> API private key, or Docker credential in `.env`: type the Docker login token
> only at Docker's password prompt.

* For `public-idcs`, store only the non-secret domain URL, audience, and scope
  in the manifest; export the client ID and secret only in the shell that runs
  the verification.
* A variable passed with `from_env` stays out of your repository and is shown
  as `value=<hidden>` in every report, but it is stored in the Hosted
  Application configuration in OCI.

## Documentation

| Read | To |
| --- | --- |
| [Quickstart](docs/quickstart.md) | Publish, update, and roll back an agent with plain-language requests. |
| [Step-by-step guide](docs/using-oci-agent-skills.md) | Understand each step, its inputs, and its outputs. |
| [Agent manifest reference](docs/agent-manifest-reference.md) | Write `agent.yaml`. |
| [IAM policies](docs/iam-policies.md) | Prepare the permissions for operators and Hosted Applications. |
| [hello_world demo](demos/hello_world/README.md) | Run the reference FastAPI/LangGraph agent. |
| [Specifications](specs/) | See design decisions, acceptance criteria, and verification records. |

<details>
<summary>Project layout</summary>

| Directory | Purpose |
| --- | --- |
| `skills/` | Codex skills for the lifecycle steps. |
| `scripts/` | Lifecycle automation, as Bash and PowerShell twins, and shared Python modules. |
| `demos/` | Runnable agent examples. |
| `docs/` | Operator guides and platform documentation. |
| `notes/` | Architectural and environment notes. |
| `specs/` | Specifications, acceptance criteria, and verification records. |
| `tests/` | Local unit tests and explicit integration-test support. |

</details>

## Contributing

Follow [AGENTS.md](AGENTS.md): specify meaningful changes first in `specs/`,
write documentation and comments in English, and record remote OCI
verification in the relevant specification.

## License

[MIT](LICENSE).
