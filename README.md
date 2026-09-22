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
`/ready` endpoints. Skills and OCI deployment automation will be added
incrementally. No OCI deployment workflow has been implemented or verified yet.

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

## Working on this repository

Follow [AGENTS.md](AGENTS.md) for the development workflow and conventions. Meaningful implementation changes start with a concise specification; project documentation and code comments are written in English.

Each skill will document its purpose, prerequisites, inputs, workflow, and how to make it available to Codex. Each demo will include execution steps, expected results, and cleanup instructions where applicable. Local verification and verification on OCI Enterprise AI will be recorded separately.

## License

[MIT](LICENSE).
