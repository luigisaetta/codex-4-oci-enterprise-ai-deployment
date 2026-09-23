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
OCIR publishing, hosted deployment, and deployment-verification skills. Remote
results are recorded in the relevant specifications and apply only to the named
release and target environment.

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
`requirements.txt`, and development tools (including OCI CLI) in
`requirements-dev.txt`. Install the latter in the activated project environment:

```bash
python -m pip install -r requirements-dev.txt
```

Follow the [hello_world setup instructions](demos/hello_world/README.md) to run
the first demo.

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
OCI_COMPARTMENT_NAME=replace-with-target-compartment-name
OCIR_TENANCY_NAMESPACE=replace-with-object-storage-namespace
OCIR_USERNAME=replace-with-ocir-login-username
```

For OC1, the resolver obtains the region list from the configured OCI CLI
profile, selects the exact `OCI_REGION` name, lowercases its key, and builds the
OCIR endpoint `<region-key>.ocir.io` (for example, `eu-frankfurt-1` becomes
`fra.ocir.io`). This avoids maintaining a static region map. Load only these
non-secret variables in your shell before using the skill:

```bash
set -a
. ./.env
set +a
```

Resolve the registry hostname before login, tagging, or push:

```bash
OCIR_REGISTRY="$(scripts/resolve_ocir_registry.sh)"
```

`OCIR_USERNAME` is the complete OCIR login username, normally
`<tenancy-namespace>/<username>` (or
`<tenancy-namespace>/<identity-domain>/<username>` for applicable identity-domain
tenancies). It is not merely the OCI Console username.

Authenticate separately, after checking Docker's credential-store behavior:

```bash
docker login --username "$OCIR_USERNAME" "$OCIR_REGISTRY"
```

Enter the OCI auth token only at Docker's password prompt. Do not put it in
`.env`, commands, logs, or this repository. The push skill requires an installed
and configured OCI CLI to resolve `OCI_COMPARTMENT_NAME` to one active compartment
OCID. It lists the target repository and, only if it is absent and you explicitly
authorize the operation, creates it as private and mutable before asking for a
separate push authorization. A successful push is registry evidence, not OCI
Enterprise AI deployment verification. See [the push skill](skills/oci-agent-push/SKILL.md)
for the authorization, creation, push, verification, and cleanup workflow.

Docker credentials are scoped to the exact registry hostname. For example,
`fra.ocir.io` and `eu-frankfurt-1.ocir.io` are valid Frankfurt endpoints, but a
login to one does not authenticate Docker to the other. Use the resolved
`$OCIR_REGISTRY` consistently for login, tagging, and push.

Each agent's versioned `agent.yaml` supplies its local image name, OCIR
repository, application name, deployment profile, and functional checks. Its
paths are relative to the checkout root, so `build.context: .` is this project
root. A semantic release tag is deliberately never stored in the manifest: pass
it on every command, for example:

```bash
scripts/build_image.sh --manifest demos/hello_world/agent.yaml --tag 0.2.0
scripts/verify_image.sh --manifest demos/hello_world/agent.yaml --tag 0.2.0
```

Before any repository mutation, inspect the compartment and manifest repository with:

```bash
scripts/ensure_ocir_repository.sh --repository agents/hello-world
```

The command has no create side effect. Exit code 20 means that the repository is
absent. Only after reviewing its target and explicitly authorizing creation, run:

```bash
scripts/ensure_ocir_repository.sh --repository agents/hello-world --create
```

It creates exactly one private, mutable repository and waits up to 120 seconds
for it to become available. It never logs Docker in or pushes an image.

## OCI Hosted Application deployment

`oci-agent-deploy` deploys an image already verified locally and published to
OCIR. It uses a public OCI Generative AI Hosted Application endpoint with
`NO_AUTH_CONFIG` and Oracle-managed networking. It does not inject container
environment variables, configure managed storage, create IAM policies, or change
networking resources.

Plan first, using an agent manifest and a semantic tag:

```bash
scripts/deploy_hosted_application.sh --manifest demos/hello_world/agent.yaml --tag 0.2.0
```

The plan performs OCI read operations only. After reviewing the resolved OCIR
artifact, compartment, and public no-auth endpoint posture, run the mutating
command only with explicit authorization:

```bash
scripts/deploy_hosted_application.sh --apply --manifest demos/hello_world/agent.yaml --tag 0.2.0
```

The Hosted Deployment runtime still needs pre-existing IAM and dynamic-group
access to pull the private OCIR image. This workflow does not create or alter
those policies. A public endpoint without inbound authentication is appropriate
only for an intentionally open test deployment; do not invoke it without a
separate review and authorization.

## OCI Hosted Application verification

`oci-agent-verify-deployment` checks a specific deployed release without
changing OCI resources. It requires the Hosted Application OCID, the expected
semantic image tag, and an explicit authorization for its public `/health` and
`/ready` GET probes. It first verifies that the application and exactly one
associated deployment are `ACTIVE`, and that the active artifact has the
expected tag. See [the verification skill](skills/oci-agent-verify-deployment/SKILL.md)
for the bounded-polling command and endpoint limitations.

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
| `oci-agent-deploy` | Plan or, after explicit authorization, deploy a verified OCIR image to OCI Generative AI Hosted Applications. | [Skill instructions](skills/oci-agent-deploy/SKILL.md) |
| `oci-agent-verify-deployment` | Verify a deployed Hosted Application release with read-only OCI state checks and public `/health` and `/ready` probes. | [Skill instructions](skills/oci-agent-verify-deployment/SKILL.md) |

Add future skills to this table as they are introduced. The full catalog,
discovery details, and verification status are maintained in
[skills/README.md](skills/README.md).

## License

[MIT](LICENSE).
