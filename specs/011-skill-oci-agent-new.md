# Spec 011: skill `oci-agent-new`, author a new agent (first iteration)

Status: draft; work in progress.
Date: 2026-10-01.

## Problem

The four lifecycle skills (build, push, deploy, verify) start from an agent
repository that already has an `agent.yaml`, a `Dockerfile`, a
`.dockerignore`, a `requirements.txt`, and a container that follows the
[container requirements](../skills/oci-agent-build/references/container-requirements.md).
Today a developer prepares these files by hand, following the section
"Creating a new agent repository" of the
[step-by-step guide](../docs/using-oci-agent-skills.md#creating-a-new-agent-repository).
Mistakes surface late, during the build or the local verification, and the
tenancy file (`.env`) is discovered to be incomplete only at push time.

## Scope

This is the first iteration of a skill that authors a new agent repository
from the developer's requirements. It is documented as **work in progress**.

* A new skill, `oci-agent-new`, invoked from a plain-language request.
* Inputs: a prompt (required) and, optionally, the path of a Markdown file
  with the agent's specifications.
* Output: every file that the lifecycle skills require, in the developer's
  repository, with an agent exposed through a FastAPI HTTP API.
* A read-only check of the tenancy file used by the other skills.
* A helper script for the deterministic parts (planning, rendering the fixed
  files, checking the tenancy file), so that they can be tested offline.
* A closing message that tells the developer what to review in `agent.yaml`
  before the first build.

## Non-goals

* Calling OCI Generative AI or any other OCI service from the agent; this
  comes with the Generative AI demo (TODO item 7).
* A test UI (TODO item 9).
* The `public-idcs` profile: the generated manifest always uses
  `public-noauth`; the closing message explains how to switch later.
* Runtime environment variables, unless the inputs name them explicitly.
* Agent unit tests, a README for the agent, and a requirements file for
  development tools.
* Building, pushing, deploying, or verifying: the skill ends where the build
  skill starts. It runs no Docker or OCI CLI command and calls no network
  service.
* Editing the tenancy file, or any file in the tool home.
* Updating an existing agent repository: the skill creates files, it never
  modifies or overwrites them.
* Packages that need compilation: the base image has no compiler (Spec 001,
  decision of 2026-10-01).

## Constraints on the generated agent

These are decisions of this project, documented for developers in the guide.

| # | Constraint |
| --- | --- |
| C1 | The agent is a Python 3.11 package exposed through **FastAPI**, served by Uvicorn on `0.0.0.0:8080` (the `CMD` of the Dockerfile template). |
| C2 | `GET /health` and `GET /ready` return HTTP 200 with a JSON body. `/ready` returns non-200 until the agent is initialized. |
| C3 | Every business endpoint takes and returns JSON, validated with Pydantic models. The first iteration generates exactly one business endpoint. |
| C4 | HTTP handling (`app.py`) and agent logic (`agent.py`) are separate modules of the same package. LangGraph is used only when the inputs ask for it. |
| C5 | The container is stateless and writes only under `/tmp`. No network call and no file write at import time. |
| C6 | No credential, token, or secret in code, in `agent.yaml`, or in any generated file. |
| C7 | `requirements.txt` lists runtime dependencies only, with version ranges, starting from the ranges used by `demos/hello_world/requirements.txt`. |
| C8 | The package folder name must not be excluded by `.dockerignore` (for example it cannot be `tests`, `scripts`, `docs`, `specs`, or `skills`). |

## Inputs

### Prompt (required)

A plain-language request, for example: "Create an agent that receives a text
with POST /analyze and returns the number of words."

### Specification file (optional)

The path of a Markdown file written by the developer. When both are given,
the file is the primary source and the prompt adds to it. When they
conflict, the skill asks which one applies; it never chooses silently.

### Values the skill must obtain

The skill derives each value from the inputs, or asks for it. It never
invents a value that changes the agent's behavior.

| Value | Rule | Default |
| --- | --- | --- |
| Agent name | `name` and `deploy.application_name` in `agent.yaml`; manifest rule `^[A-Za-z0-9][A-Za-z0-9._-]*$`. | None: ask. |
| Package folder | Python identifier (snake_case), respecting C8. | The agent name in snake_case. |
| OCIR repository | `publish.repository`; manifest rule `^[a-z0-9][a-z0-9._/-]*$`. | `agents/<agent-name>` (lowercase). |
| Business endpoint | Method `POST`, a path, the request fields and their types, the response fields and their types. | None: ask for whatever is missing. |
| Agent behavior | What the endpoint computes, in plain language. | None: ask. |
| Functional check | One request body and the expected status; the expected JSON only when the result is deterministic. | Derived from the endpoint and behavior; shown for confirmation. |
| Runtime variables | Only those named in the inputs, with their source (`value`, `from_env`, or `vault_secret_id`). | None. |

## Requests outside the first iteration

When the inputs ask for something outside this iteration, for example a `GET`
business endpoint, more than one endpoint, streaming, file upload, or calls to
OCI Generative AI, the skill:

1. says which part of the request is outside the first iteration;
2. asks whether the developer wants to go ahead anyway.

If the developer declines, the skill stops, or continues with the supported
shape if the developer asks for it. If the developer goes ahead, Codex
implements the extra parts on its own judgment: they are not covered by the
tests or the acceptance criteria of this specification, and the closing
message says so. Constraints C1, C2, C5, C6, and C8 still apply, because the
build skill and the platform depend on them. For calls to OCI services, the
closing message also points to [IAM policies](../docs/iam-policies.md).

## Target folder

The current Codex workspace, which must be the root of the agent's
repository and never the tool home.

* If the folder is not inside a Git repository, the skill says so and asks
  whether to continue: without Git, the allowed build roots default to the
  manifest's folder (see `OCI_AGENT_ALLOWED_ROOTS` in the README).
* If any file to be created already exists, the skill stops before writing
  anything and lists the conflicts. It never overwrites a file.

## Generated files

| File | Source | Content |
| --- | --- | --- |
| `agent.yaml` | `skills/oci-agent-build/assets/agent.yaml.template` | `schema_version: 2`, `context: .`, `profile: public-noauth`, the values above, and one `verify` check. |
| `Dockerfile` | `skills/oci-agent-build/assets/Dockerfile.template` | `{{REQUIREMENTS_PATH}}` = `requirements.txt`, `{{PACKAGE_DIR}}` = the package folder, `{{APP_MODULE}}` = `<package>.app:app`. |
| `.dockerignore` | `skills/oci-agent-build/assets/dockerignore.template` | Copied unchanged. |
| `.gitignore` | Fixed content from the helper | At least `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.venv/`, `.env`, `.env.*`. |
| `requirements.txt` | Written by Codex within C7 | `fastapi`, `pydantic`, `uvicorn`, and only the packages the agent needs. |
| `<package>/__init__.py` | Written by Codex | Module header only. |
| `<package>/app.py` | Written by Codex within C1–C5 | FastAPI app, probes, the business endpoint, Pydantic models. |
| `<package>/agent.py` | Written by Codex within C4–C6 | The agent logic. |

The templates stay in `skills/oci-agent-build/assets/` and are the single
source: the new skill reads them, it does not copy them.

Generated Python files carry the module header of the project conventions,
with the author name taken from the inputs or left as a placeholder for the
developer.

## Tenancy file check

The lifecycle skills read the tenancy file selected by `OCI_AGENT_ENV_FILE`,
by default `.env` in the tool home. The skill checks, without changing it:

* that the file exists;
* that `OCI_REGION`, `OCI_COMPARTMENT_NAME`, `OCIR_TENANCY_NAMESPACE`, and
  `OCIR_USERNAME` are each set, either in the file or in the environment;
* that no value still starts with the placeholder prefix `replace-with-` of
  `.env.example`.

It reports only key names and the file path, never values. A failed check
does not stop the authoring: it is listed in the closing message as a
prerequisite for push and deploy.

## Helper script

`scripts/new_agent.py`, Python only: like `agent_manifest.py` and
`tool_config.py`, it runs on both macOS and Windows, so no Bash or
PowerShell twin is needed.

| Subcommand | Behavior | Writes |
| --- | --- | --- |
| `plan` | Validates the agent name, package folder, and repository; lists the files to create; reports existing files as conflicts (exit 30). | Nothing. |
| `render` | Renders `agent.yaml`, `Dockerfile`, `.dockerignore`, and `.gitignore` into the target folder from the templates. `agent.yaml` has `verify: []` and no `runtime` section. Refuses to overwrite (exit 30). | Those four files. |
| `check-manifest` | Validates the manifest with `agent_manifest.py` and requires at least one `verify` check (exit 64 otherwise). | Nothing. |
| `check-env` | Runs the tenancy file check above (exit 0 when complete, 31 otherwise). | Nothing. |

Invalid arguments exit 64, consistent with the other scripts. Exit codes 30
and 31 are not used by any other script. After `render`, Codex adds the
functional check and the optional runtime variables directly to the new
`agent.yaml`; `check-manifest` then validates the result.

The tenancy file check reuses `tool_config.py` (`configuration_file`,
`read_configuration`), with a new read-only function that returns missing
and placeholder keys without printing values.

## Workflow of the skill

1. Target platform check: confirm the request is about an agent for OCI
   Generative AI Hosted Applications; if the request is about another
   platform, stop and ask.
2. Read the prompt and the optional specification file.
3. If part of the request is outside the first iteration, say so and ask
   whether to go ahead (see above).
4. Collect the values of the table above; ask for the missing ones in one
   message.
5. Run `new_agent.py plan`. Show the developer the values and the files to
   create, and wait for confirmation. Stop on conflicts.
6. Run `new_agent.py render`.
7. Add the functional check, and the runtime variables if any, to
   `agent.yaml`.
8. Write `requirements.txt` and the package files within C1–C8.
9. Check the generated Python files with `python -m py_compile`.
10. Run `new_agent.py check-manifest`.
11. Run `new_agent.py check-env`.
12. Print the closing message.

### Closing message

The message lists, in this order:

1. The files created, and the parts implemented outside the first iteration,
   if any.
2. **Review `agent.yaml`**, in particular:
   * whether the agent must be protected with identity-domain tokens
     (`public-idcs`). Recommended: keep `public-noauth` for the first release
     and its tests, and switch later. The access mode is fixed when the
     Hosted Application is created, so switching means a new application
     name;
   * whether the agent needs runtime environment variables that were not
     specified; see the
     [agent manifest reference](../docs/agent-manifest-reference.md);
   * whether the functional check matches the expected behavior.
3. The result of the tenancy file check, with the missing keys if any.
4. The next step, for example: "Build version 0.1.0 of this agent".

## Documentation

* `skills/oci-agent-new/SKILL.md` and `agents/openai.yaml`, following the
  structure of the other skills, including the sections "Tool home and
  working directory" and "Target platform check".
* `skills/README.md` and the README skills table: a row for the skill with
  the status "Work in progress (first iteration)".
* `docs/using-oci-agent-skills.md`: the section "Creating a new agent
  repository" points to the skill, and lists the constraints C1–C8.
* `docs/quickstart.md`: the "No agent yet?" request uses the skill.
* `CHANGELOG.md`.

## Tests (offline)

* `tests/test_new_agent.py`:
  * `plan` lists the expected files and writes nothing;
  * `plan` and `render` stop with exit 30 when a target file exists, and
    leave it unchanged;
  * `render` produces a manifest that `agent_manifest.py validate` accepts,
    and a Dockerfile with no remaining `{{` placeholder;
  * `check-manifest` rejects the rendered manifest while `verify` is empty,
    and accepts it after one check is added;
  * invalid agent name, repository, or package folder (including C8) exit 64;
  * `check-env` reports a missing key and a placeholder value by name, and
    its output contains no value from the file.
* `tests/test_skills.py`: the new skill satisfies the existing structural
  checks. The check that names the other platform's skill applies to the four
  lifecycle skills only; every skill, including the new one, keeps the
  section "Target platform check".
* Black, Pylint, and pytest pass.

## Acceptance criteria

1. The skill appears in Codex after installation with
   `scripts/install_skills.sh`, which links every folder of `skills/`.
2. From a prompt only, and from a prompt plus a specification file, the skill
   asks for the missing values instead of inventing them.
3. It never writes before the developer confirms the plan, and never
   overwrites a file.
4. A request outside the first iteration is reported, and the skill goes on
   only after the developer agrees.
5. The generated `agent.yaml` passes `new_agent.py check-manifest`.
6. **End to end, on macOS:** for one sample agent, the build skill builds and
   locally verifies the generated repository, including its functional check,
   without manual edits. Record the sample prompt, the generated file list,
   and the build result here.
7. The closing message contains the items listed above, and the tenancy file
   check never prints a value.
8. The offline tests pass.

## Verification approach

Offline tests cover the helper. Criteria 2, 3, 4, 6, and 7 need a real Codex
session in an empty Git repository, recorded below. No OCI resource is
created, so no cleanup is needed beyond deleting the sample repository.

## Open points

* Whether a later iteration generates agent unit tests and a
  `requirements-dev.txt`.
* Whether the specification file should follow a template provided by the
  skill (fixed sections), or stay free-form as in this iteration.
* Whether the skill should offer to run the build at the end, or only suggest
  it as now.

## Verification record

Pending.
