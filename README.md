# codex-4-oci-enterprise-ai-deployment

![Code style: Black](https://img.shields.io/badge/code%20style-black-000000)
![Linting: Pylint](https://img.shields.io/badge/linting-pylint-blue)
![Python: 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Testing: pytest](https://img.shields.io/badge/testing-pytest-0A9EDC?logo=pytest&logoColor=white)

Codex skills and reproducible demos to support the deployment of AI agents in **OCI Enterprise AI**.

The project aims to make the deployment process understandable and repeatable, from checking prerequisites and preparing an agent to configuring its deployment, verifying behavior, and cleaning up resources.

## Project status

The first demo, [hello_world](demos/hello_world/README.md), provides a LangGraph
greeting agent wrapped in FastAPI on port 8080, with `/hello`, `/health`, and
`/ready` endpoints. The repository includes local image build/verification and
OCIR-push preparation skills. No OCI deployment workflow has been implemented
or verified yet.

## Planned contents

| Directory | Purpose |
| --- | --- |
| `skills/` | Codex skills for specific steps of the agent deployment process. |
| `demos/` | Runnable examples with prerequisites, configuration, verification, and cleanup instructions. |
| `specs/` | Specifications and acceptance criteria for skills, demos, and automation. |
| `src/` | Shared Python code used by demos and scripts. |
| `scripts/` | Setup and deployment automation. |
| `tests/` | Local tests and explicit, opt-in OCI integration tests. |
| `docs/` | Guides, platform notes, and verification reports. |

Directories are created as their first contents are added.

## Local development

macOS is the initial local development environment. OCI Enterprise AI is the target deployment platform; each demo will document its specific runtime and OCI prerequisites.

Use the Conda environment named `codex-4-oci-enterprise-ai-deployment`, matching the repository folder name.

Once the environment has been created separately, activate it with:

```bash
conda activate codex-4-oci-enterprise-ai-deployment
```

The project targets Python 3.11+. Shared runtime dependencies are maintained in
`requirements.txt`, and development tools in `requirements-dev.txt`. Follow the
[hello_world setup instructions](demos/hello_world/README.md) to run the first demo.

Configuration inputs and authentication requirements will be documented alongside each workflow. Local `.env` files must be ignored by Git; versioned examples must use safe placeholders. Never commit credentials, private keys, tokens, or sensitive OCI configuration.

## OCIR push configuration

`oci-agent-push` prepares a previously verified image for OCI Container Registry
(OCIR) in the commercial OCI realm (OC1). It never stores or accepts an OCI auth
token. Copy the safe example to the ignored local configuration file, then
replace every placeholder with your target values:

```bash
cp .env.example .env
```

```dotenv
OCI_REGION=eu-frankfurt-1
OCIR_TENANCY_NAMESPACE=replace-with-object-storage-namespace
OCIR_REPOSITORY=agents/hello-world
OCIR_USERNAME=replace-with-oci-username
```

For OC1, the registry domain is derived as `${OCI_REGION}.ocir.io`; for example,
the Frankfurt target is `eu-frankfurt-1.ocir.io/<namespace>/<repository>:<tag>`.
Load only these non-secret variables in your shell before using the skill:

```bash
set -a
. ./.env
set +a
```

Authenticate separately, after checking Docker's credential-store behavior:

```bash
docker login --username "$OCIR_USERNAME" "${OCI_REGION}.ocir.io"
```

Enter the OCI auth token only at Docker's password prompt. Do not put it in
`.env`, commands, logs, or this repository. You need IAM access to the existing
target repository; a successful push is registry evidence, not OCI Enterprise AI
deployment verification. See [the push skill](skills/oci-agent-push/SKILL.md)
for the authorization, push, verification, and cleanup workflow.

## Working on this repository

Follow [AGENTS.md](AGENTS.md) for the development workflow and conventions. Meaningful implementation changes start with a concise specification; project documentation and code comments are written in English.

Each skill will document its purpose, prerequisites, inputs, workflow, and how to make it available to Codex. Each demo will include execution steps, expected results, and cleanup instructions where applicable. Local verification and verification on OCI Enterprise AI will be recorded separately.

## Using repository skills

The checkout exposes its skills to Codex through the `.agents/skills` discovery
link. Open this repository as your working folder, then select a skill from the
skills interface (or explicitly invoke it as `$skill-name` in Codex surfaces
that support that syntax). Read the linked `SKILL.md` before supplying inputs or
running its workflow.

If a skill is not shown, confirm that its `SKILL.md` exists below `skills/`,
that the `.agents/skills` link resolves to that directory, and restart Codex.
Putting a skill directory under `skills/` by itself does not expose it for
discovery. To use these skills from another repository, follow the optional
user-scope symlink instructions in [the skills index](skills/README.md); keep
this checkout in place while that link is in use.

| Skill | When to use it | Instructions |
| --- | --- | --- |
| `oci-agent-build` | Build, rebuild, or locally verify a `linux/amd64` agent container image for OCI Enterprise AI. It does not push images or deploy OCI resources. | [Skill instructions](skills/oci-agent-build/SKILL.md) |
| `oci-agent-push` | Prepare and, after explicit authorization, push a verified image to OCIR in the OC1 realm. It does not deploy OCI resources. | [Skill instructions](skills/oci-agent-push/SKILL.md) |

Add future skills to this table as they are introduced. The full catalog,
discovery details, and verification status are maintained in
[skills/README.md](skills/README.md).

## License

[MIT](LICENSE).
