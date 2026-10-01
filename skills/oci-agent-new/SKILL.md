---
name: oci-agent-new
description: Author a new agent repository for OCI Generative AI Hosted Applications from a prompt and an optional Markdown specification file. Runs no build, push, deploy, Docker, or OCI command. First iteration (work in progress).
---

# OCI Agent New

This skill is **work in progress (first iteration)**. Contract and verification:
[Spec 011](../../specs/011-skill-oci-agent-new.md).

## Purpose and when to use

Create a new Python agent repository from the developer's requirements, ready
for the build skill. Author the FastAPI API, agent logic, runtime requirements,
and manifest; use the helper for deterministic files and offline checks.
Run no build, push, deploy, Docker, OCI command, or network request.

## Tool home and working directory

Resolve the real path of this skill's folder, following symbolic links:

```bash
skill_real="$(cd -P -- "<this skill folder>" && pwd -P)"
TOOL_HOME="$(dirname -- "$(dirname -- "$skill_real")")"
```

In PowerShell, resolve the skill folder's link target and take its grandparent.
The current workspace must be the agent folder. Never change directory into
the tool home or write there. Read templates in
`$TOOL_HOME/skills/oci-agent-build/assets/` in place; never copy the templates
elsewhere. The helper writes their rendered output into the workspace.

Use Python from the activated Conda environment
`codex-4-oci-enterprise-ai-deployment`, or the explicit `OCI_AGENT_PYTHON`
interpreter. Without activation, prefix Python commands with
`conda run --no-capture-output -n codex-4-oci-enterprise-ai-deployment`.
The Bash examples use:

```bash
AGENT_PYTHON="${OCI_AGENT_PYTHON:-python}"
```

Do not fall back to global Python. In PowerShell invoke the same `.py` helper
with the selected interpreter and the same `--option` names; no script twin
is needed. Tenancy settings come from `OCI_AGENT_ENV_FILE`, default
`$TOOL_HOME/.env`; the helper reads it. Never source, print, or edit that file.

## Prerequisites

* A prepared workstation, the tool home in place, the project Conda environment
  with PyYAML, skills installed through
  [the user-scope installer](../README.md#install-at-user-scope), and a new Codex
  session after installation.
* An existing dedicated agent folder opened as the workspace in a new session,
  outside the tool home and its descendants. It must contain none of the files
  to create; an existing regular-file `.gitignore` is kept unchanged.
* Git is recommended. If the workspace is not inside a Git repository, explain
  that allowed build roots default to the manifest folder and ask whether to
  continue before writing.
* Put the optional Markdown specification inside the agent folder. It remains
  with the source; `.dockerignore` excludes `**/*.md` from the image.

Docker, OCI credentials, network access, and complete tenancy settings are
not prerequisites for authoring. Codex cannot change its workspace mid-session.

## Target platform check

Create agents for OCI Generative AI Hosted Applications only. Before running
commands, confirm this is the developer's target. If the request concerns
another platform or the target is unclear, stop and ask; never switch silently.

## Inputs

Read the required prompt and optional Markdown specification. The file is the
primary source and the prompt adds to it; ask when they conflict. Derive values
from those inputs or ask for every missing value in one message. Never invent
the agent behavior, endpoint, or model identifier.

| Value | Rule | Default |
| --- | --- | --- |
| Agent name | `name` and `deploy.application_name`; `^[A-Za-z0-9][A-Za-z0-9._-]*$`. | None: ask. |
| Package folder | Lowercase, non-keyword Python identifier in snake_case, respecting C8. | Agent name in snake_case; ask for an explicit package if invalid. |
| OCIR repository | `publish.repository`; `^[a-z0-9][a-z0-9._/-]*$`, without `//`. | `agents/<agent-name>` (lowercase). |
| Business endpoint | `POST` path, request and response fields and types. | None: ask for whatever is missing. |
| Agent behavior | What the endpoint computes, in plain language. | None: ask. |
| Functional check | One request body and expected status; expected JSON only for deterministic results. | Derive from behavior and endpoint; show for confirmation. |
| Runtime variables | Only those named in inputs; source `value`, `from_env`, or `vault_secret_id`. | None. |

## Requests outside the first iteration

For GET business endpoints, multiple endpoints, streaming, file uploads, OCI
service calls, or other additions outside this iteration, name the requested
parts and ask whether to proceed. If declined, stop or use the supported shape
only if requested. If approved, author those additions and identify them as
outside this specification's tests and acceptance criteria. C1, C2, C5, C6,
and C8 still apply. For OCI service calls, include
[IAM policies](../../docs/iam-policies.md) in the closing message.

## Workflow

1. Perform the target platform check.
2. Read the prompt and optional specification file.
3. Report requests outside the first iteration and obtain the decision above.
4. Collect the input table's values; ask for missing values together. Set
   `AGENT_NAME`, `PACKAGE`, and `REPOSITORY` to the selected values for the
   commands below. Resolve prerequisite issues before writing.
5. Plan from the workspace:

   ```bash
   "$AGENT_PYTHON" "$TOOL_HOME/scripts/new_agent.py" plan \
     --name "$AGENT_NAME" --package "$PACKAGE" --repository "$REPOSITORY" --target .
   ```

   Show `Target:`, `Name:`, `Package:`, `Repository:`, every `Create:`/`Keep:`
   line, and the proposed functional check. Preserve any
   `Missing .gitignore entries:` report for the closing message; it is advisory.
   On exit 30, list `Conflict:` entries and stop. Never delete or rename the
   developer's files. Wait for the developer's confirmation before rendering.
6. Render with the confirmed values:

   ```bash
   "$AGENT_PYTHON" "$TOOL_HOME/scripts/new_agent.py" render \
     --name "$AGENT_NAME" --package "$PACKAGE" --repository "$REPOSITORY" --target .
   ```

   This creates `agent.yaml`, `Dockerfile`, `.dockerignore`, and `.gitignore`
   only when absent. A regular-file `.gitignore` is kept byte-for-byte; a
   directory or symlink is a conflict. On exit 30, list conflicts and stop.
   On a failed render, report the original error and any cleanup error naming
   remaining files; do not proceed to authoring.
7. Edit only the new `agent.yaml` created in this session: replace `verify: []`
   with the confirmed functional check. Add `runtime` only for requested
   variables, using the [manifest reference](../../docs/agent-manifest-reference.md).
8. Create `requirements.txt`, `<package>/__init__.py`, `<package>/app.py`, and
   `<package>/agent.py` within C1–C8; `__init__.py` contains only the module
   header. Recheck their absence before writing. After render, edit only files
   created in this session; never modify a kept `.gitignore` or other existing
   file. Every generated Python file starts with the
   [AGENTS.md module header](../../AGENTS.md#code-script-and-notebook-conventions):
   author from the inputs or a developer placeholder, actual modification
   date, MIT license, and a brief responsibility description.
9. Check syntax with the same interpreter; stop on failure:

   ```bash
   "$AGENT_PYTHON" -m py_compile \
     "$PACKAGE/__init__.py" "$PACKAGE/app.py" "$PACKAGE/agent.py"
   ```

10. Validate the completed manifest and require at least one check:

    ```bash
    "$AGENT_PYTHON" "$TOOL_HOME/scripts/new_agent.py" check-manifest --manifest agent.yaml
    ```

11. Run the read-only tenancy check; exit 31 does not stop authoring:

    ```bash
    "$AGENT_PYTHON" "$TOOL_HOME/scripts/new_agent.py" check-env
    ```

    It checks the selected file's existence and effective values for
    `OCI_REGION`, `OCI_COMPARTMENT_NAME`, `OCIR_TENANCY_NAMESPACE`, and
    `OCIR_USERNAME`, including `replace-with-` placeholders. Non-empty
    environment settings override file settings. Report only key names and
    the file path, never values; leave corrections to the developer.
12. Print the closing message in the order below.

## Constraints on the generated agent

| # | Constraint |
| --- | --- |
| C1 | Python 3.11 package, FastAPI, Uvicorn on `0.0.0.0:8080` using the template CMD. |
| C2 | GET `/health` returns HTTP 200 with JSON; `/ready` returns JSON and HTTP 200 after initialization, non-200 before it completes. |
| C3 | Exactly one POST business endpoint, JSON requests and responses validated with Pydantic models. |
| C4 | Separate HTTP handling in `app.py` from logic in `agent.py` in the same package. Use LangGraph only when requested. |
| C5 | Stateless container, writes only under `/tmp`; no network calls or file writes at import time. |
| C6 | No credentials, tokens, or secrets in any generated file, including the manifest. |
| C7 | Runtime dependencies only, with version ranges starting from [hello_world requirements](../../demos/hello_world/requirements.txt): FastAPI, Pydantic, Uvicorn, and only needed packages. |
| C8 | Package folder must not be excluded by `.dockerignore`; the helper reads the build template's exclusions. |

## Exit codes

| Code | Meaning and action |
| --- | --- |
| 0 | Check passed; continue. Keep missing `.gitignore` entries for the closing message. |
| 30 | File conflict; list conflicts and stop without deleting, renaming, or overwriting developer files. |
| 31 | Tenancy file missing, unreadable, incomplete, or containing effective placeholders; continue authoring and report required corrections before push/deploy. |
| 64 | Invalid arguments, target, names, manifest, templates, or file operation; report the error, correct inputs, and stop until resolved. |

## Closing message

List these four items in order:

1. Files created, any `.gitignore` kept, and parts implemented outside the
   first iteration, if any; state that those additions are outside its tests
   and acceptance criteria.
2. **Review `agent.yaml`**: access profile, any needed runtime variables not
   specified, and whether the functional check matches the expected behavior.
   Recommend keeping `public-noauth` for the first release and its tests.
   Switching later to identity-domain token protection (`public-idcs`) requires
   a new application name because the access mode is fixed at creation.
3. Tenancy check result, missing/placeholder keys and file issues, plus required
   entries missing from a kept `.gitignore`; the developer adds those entries.
4. Suggest the next request, for example: "Build version 0.1.0 of this agent".

## Limitations

The first iteration supports one POST JSON endpoint, no OCI service calls,
and no generated agent tests, README, development requirements, or test UI.
Packages needing compilation fail the build because the base image has no
compiler; prefer a version or alternative with a `linux/amd64` wheel.
Files present before this session are never modified. No local syntax or
manifest check establishes runtime behavior or OCI compatibility; building
and execution belong to the next skill.
