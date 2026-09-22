# codex-4-oci-enterprise-ai-deployment

Codex skills and reproducible demos to support the deployment of AI agents in **OCI Enterprise AI**.

The project aims to make the deployment process understandable and repeatable, from checking prerequisites and preparing an agent to configuring its deployment, verifying behavior, and cleaning up resources.

## Project status

This repository is in its initial setup phase. It currently contains the project guidelines, this README, and the MIT license. Skills, demos, deployment automation, and dependency files will be added incrementally. No deployment workflow has been implemented or verified yet.

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

These directories will be created as their first contents are added.

## Local development

macOS is the initial local development environment. OCI Enterprise AI is the target deployment platform; each demo will document its specific runtime and OCI prerequisites.

Use the Conda environment named `codex-4-oci-enterprise-ai-deployment`, matching the repository folder name.

Once the environment has been created separately, activate it with:

```bash
conda activate codex-4-oci-enterprise-ai-deployment
```

The Python version and dependencies will be defined with the first implementation. Shared runtime dependencies will be maintained in `requirements.txt`, and development tools in `requirements-dev.txt`.

Configuration inputs and authentication requirements will be documented alongside each workflow. Local `.env` files must be ignored by Git; versioned examples must use safe placeholders. Never commit credentials, private keys, tokens, or sensitive OCI configuration.

## Working on this repository

Follow [AGENTS.md](AGENTS.md) for the development workflow and conventions. Meaningful implementation changes start with a concise specification; project documentation and code comments are written in English.

Each skill will document its purpose, prerequisites, inputs, workflow, and how to make it available to Codex. Each demo will include execution steps, expected results, and cleanup instructions where applicable. Local verification and verification on OCI Enterprise AI will be recorded separately.

## License

[MIT](LICENSE).
