---
name: oci-agent-new
description: Create a new AI agent for OCI Generative AI Hosted Applications (Hosted Deployments). Use when asked to design, specify, or create a new OCI agent, including a request for a first draft of its specification. Drafts agent-spec.md from a short request, then, after approval, writes agent.yaml, Dockerfile, and a FastAPI agent. Runs no build, push, deploy, Docker, or OCI command.
---

# OCI Agent New

Contract and verification: [Spec 011](../../specs/011-skill-oci-agent-new.md),
amended by [Spec 017](../../specs/017-oci-agent-new-llm-agents-supported.md),
[Spec 024](../../specs/024-asynchronous-agents.md), and
[Spec 027](../../specs/027-agents-with-a-database.md).

## Purpose and when to use

Create a new Python agent repository from the developer's requirements, ready
for the build skill. Author the FastAPI API, agent logic, runtime requirements,
and manifest; use the helper for deterministic files and offline checks.
Run no build, push, deploy, Docker, OCI command, or network request, except
the online searches allowed in [Customer name](#customer-name).

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
`oci-agent-shipyard`, or the explicit `OCI_AGENT_PYTHON`
interpreter. Without activation, prefix Python commands with
`conda run --no-capture-output -n oci-agent-shipyard`.
The Bash examples use:

```bash
AGENT_PYTHON="${OCI_AGENT_PYTHON:-python}"
```

When the selected interpreter lacks PyYAML, the helper exits 64 with:
"Python with PyYAML is required. Activate the Conda environment
oci-agent-shipyard or set OCI_AGENT_PYTHON."
Activate that environment or set `OCI_AGENT_PYTHON`, then retry.
In PowerShell invoke the same `.py` helper
with the selected interpreter and the same `--option` names; no script twin
is needed. Tenancy settings come from `OCI_AGENT_ENV_FILE`, default
`$TOOL_HOME/.env`; the helper reads it. Never source, read into the conversation, print, or edit that file: it may
hold agent secrets.

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

## Customer name

Contract: [Spec 020](../../specs/020-demo-customer-name.md). Before drafting,
read the customer name approved for demos (`Supremo` unless the tool's `.env`
sets `DEMO_CUSTOMER_NAME`):

```bash
"$AGENT_PYTHON" "$TOOL_HOME/scripts/tool_config.py" demo-customer
```

* Every file uses only the demo name: `agent-spec.md` (replace
  `{{DEMO_CUSTOMER_NAME}}` in the template), code, LLM instructions and
  prompts, packaged data and examples, functional checks, `agent.yaml`
  (application and repository names), and any proposed commit message.
* If the developer names the real customer, keep that name only in the
  conversation. Reply once, without repeating it: "In every file and in the
  demo the customer is called <demo name>." Never ask for the real name.
* Never write the real name to disk in any form: full name, abbreviation,
  domain, or e-mail address.
* The real name may be used in online searches only when they help to
  understand the customer's business; these searches are the only network use
  allowed. Never copy from the results product names, brands, people,
  addresses, or figures that identify the real customer.
* Before the closing message, search the files you wrote for the real name
  and its obvious variants, case-insensitively, with a local search (for
  example `grep -ril`). Replace every match with the demo name and report the
  fix without the name. Skip this check when no real name was given.
* The same rules go into the agent repository's `AGENTS.md` (workflow step 6),
  so that they also apply when the files are changed later without a skill.

## Inputs

Read the required prompt and optional Markdown specification. The file is the
primary source and the prompt adds to it; ask when they conflict. Derive values
from those inputs or ask for every missing value in one message. Never invent
the agent behavior, endpoint, or model identifier.

| Value | Rule | Default |
| --- | --- | --- |
| Agent name | `name` and `deploy.application_name`; `^[A-Za-z0-9][A-Za-z0-9._-]*$`. | None: ask. |
| Package folder | Lowercase, non-keyword Python identifier in snake_case, respecting C8. | Helper derives snake_case from the agent name; ask for an explicit package if invalid. |
| OCIR repository | `publish.repository`; `^[a-z0-9][a-z0-9._/-]*$`, without `//`. | Helper supplies `agents/<agent-name>` (lowercase). |
| Business endpoint | `POST` path, request and response fields and types. | None: ask for whatever is missing. |
| Agent behavior | What the endpoint computes, in plain language. | None: ask. |
| Functional check | One request body and expected status; expected JSON only for deterministic results. For an asynchronous agent, also a `poll` check (guideline B8); for an agent with a database, also the remote-only `/ready` check (guideline B5). | Derive from behavior and endpoint; show for confirmation. |
| Saved data | Whether the agent keeps data between requests: catalogs in the database, saved records (guideline B9). | None: no database. |
| Runtime variables | Only those named in inputs; source `value`, `from_env`, or `vault_secret_id`. | None. |

## Specification draft

Before drafting, read the [agent guidelines](references/agent-guidelines.md).
If the request does not give the customer persona, the use case, or the
expected outcomes, ask for the missing ones in one message before drafting.
Customer concerns are optional: include them when given, and do not ask for
them.
When the developer gives no specification file, copy
[the specification template](assets/agent-spec.template.md) to `agent-spec.md`
in the workspace, replace `{{AGENT_NAME}}` and `{{DEMO_CUSTOMER_NAME}}`, and
fill in only what the prompt
states. Write each applicable behavior default (B rules of the guidelines)
into the draft, marked "(default)". List everything else under "Open
questions"; never invent behavior.
Draft the specification in the language of the developer's request; keep the
section titles of the template in English.
Stop and ask the developer to review the file. The developer may edit it by
hand or ask for changes in the chat; until approval, change only
`agent-spec.md` and generate no other file. After explicit approval, read
`agent-spec.md` again and use it as the specification file. Generate the
code from the approved specification only, applying the code-quality rules
(Q rules) of the guidelines.

## Requests outside the supported shape

Calls to OCI Generative AI are part of the supported shape: follow the
[agent guidelines](references/agent-guidelines.md) (B1, B2, Q1–Q4, Q6, Q7)
without asking whether to proceed. So is the **asynchronous** shape of
guideline B8 (a POST that starts a job, a GET that reads its status), for
agents with several LLM steps or long requests
([Spec 024](../../specs/024-asynchronous-agents.md)); use it without asking,
and say in the draft that the agent is asynchronous.

Agents that keep data between requests are supported too
([Spec 027](../../specs/027-agents-with-a-database.md)): when the
specification asks for saved data or a catalog in a database, use the managed
Oracle database of guideline B9 and the read endpoints of guideline B10
without asking, and say so in the Deployment section of the draft. If the
agent replaces an existing application without storage, say in the draft that
it needs a new application name, which starts with an empty database.

For other GET business endpoints, more endpoints, streaming, file uploads, calls
to OCI services other than Generative AI, or other additions outside the
supported shape, name the requested parts and ask whether to proceed. If
declined, stop or use the supported shape only if requested. If approved,
author those additions and identify them as outside this specification's tests
and acceptance criteria. C1, C2, C5, C6, and C8 still apply. For calls to other
OCI services, include [IAM policies](../../docs/iam-policies.md) in the closing
message.

## Workflow

1. Perform the target platform check.
2. Read the prompt and optional specification file. Without a specification
   file, first write the specification draft below and continue only after
   the developer approves it.
3. Report requests outside the supported shape and obtain the decision above.
4. Collect the input table's values; ask for missing values together. Set
   `AGENT_NAME` from the inputs. Do not compute the default package or
   repository; the helper supplies them. Initialize the Bash option array:

   ```bash
   PLAN_OPTIONS=()
   ```

   Append `--package` and its value only if the developer supplied a package
   explicitly; likewise append `--repository` and its explicit value. Leave
   the array empty when neither was supplied. Resolve prerequisite issues
   before writing.
5. Plan from the workspace:

   ```bash
   "$AGENT_PYTHON" "$TOOL_HOME/scripts/new_agent.py" plan \
     --name "$AGENT_NAME" "${PLAN_OPTIONS[@]}"
   ```

   Show `Target:`, `Name:`, `Package:`, `Repository:`, every `Create:`/`Keep:`
   line, and the proposed functional check. Preserve any
   `Missing .gitignore entries:` report for the closing message; it is advisory.
   On exit 30, list `Conflict:` entries and stop. Never delete or rename the
   developer's files. If plan exits 64 because the derived package is invalid,
   ask the developer for an explicit `--package`, add it to the options, and
   run plan again. After a successful plan, take `PACKAGE` and `REPOSITORY`
   exactly from its `Package:` and `Repository:` lines. Use these values for
   render, package file paths, syntax checks, and the closing message. Wait
   for the developer's confirmation before rendering.
6. Render with the confirmed values printed by plan:

   ```bash
   "$AGENT_PYTHON" "$TOOL_HOME/scripts/new_agent.py" render \
     --name "$AGENT_NAME" --package "$PACKAGE" --repository "$REPOSITORY" --target .
   ```

   This creates `agent.yaml`, `Dockerfile`, `.dockerignore`, and `.gitignore`
   only when absent. A regular-file `.gitignore` is kept byte-for-byte; a
   directory or symlink is a conflict. On exit 30, list conflicts and stop.
   On a failed render, report the original error and any cleanup error naming
   remaining files; do not proceed to authoring. Then add the customer-name
   rules to the repository's `AGENTS.md`, which Codex reads in every later
   session, with or without a skill:

   ```bash
   "$AGENT_PYTHON" "$TOOL_HOME/scripts/agent_instructions.py" ensure --target .
   ```

   It creates the file, appends the marked block to an existing file, or
   refreshes only that block; it never changes other content.
7. Edit only the new `agent.yaml` created in this session: replace `verify: []`
   with the confirmed functional check. Add `runtime` only for requested
   variables, using the [manifest reference](../../docs/agent-manifest-reference.md).
   For an asynchronous agent, also add `deploy.scaling` with one replica and
   the `poll` check of guideline B8. For an agent with a database, add
   `deploy.storage: {type: ADB}` and the remote-only `/ready` check of
   guideline B5; mark `local: false` every other check that needs the
   database.
8. Create `requirements.txt`, `<package>/__init__.py`, `<package>/app.py`, and
   `<package>/agent.py` (and `<package>/db.py` for an agent with a database,
   guideline Q8) within C1–C8; `__init__.py` contains only the module
   header. Recheck their absence before writing. After render, edit only files
   created in this session; never modify a kept `.gitignore` or other existing
   file. Every generated Python file starts with this header:

   ```python
   """
   Author: <author>
   Date last modified: YYYY-MM-DD
   License: MIT
   Description: <one-line responsibility of this file>.
   """
   ```

   Use the actual modification date and file responsibility. `<author>` comes
   from the inputs; otherwise leave it as a placeholder for the developer.
   Never take an author name from the tool repository. Apply no other tool
   repository convention to the agent repository: do not add `specs/`,
   `CHANGELOG`, `AGENTS.md`, or a Conda environment in the agent.
9. Check syntax with the same interpreter; stop on failure:

   ```bash
   "$AGENT_PYTHON" -m py_compile \
     "$PACKAGE/__init__.py" "$PACKAGE/app.py" "$PACKAGE/agent.py"
   ```

   Add `"$PACKAGE/db.py"` when it exists.

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
12. Run the customer-name check of [Customer name](#customer-name), then print
    the closing message in the order below.

## Constraints on the generated agent

| # | Constraint |
| --- | --- |
| C1 | Python 3.11 package, FastAPI, Uvicorn on `0.0.0.0:8080` using the template CMD. |
| C2 | GET `/health` returns HTTP 200 with JSON; `/ready` returns JSON and HTTP 200 after initialization, non-200 before it completes. |
| C3 | Exactly one POST business endpoint, or the asynchronous pair of guideline B8 (POST to start, GET for the status); for an agent with a database, also the read endpoints of guideline B10. JSON requests and responses validated with Pydantic models. |
| C4 | Separate HTTP handling in `app.py` from logic in `agent.py` in the same package. Use LangGraph only when requested. |
| C5 | Stateless container, writes only under `/tmp`; data that must survive goes to the managed database (guideline B9). No network calls or file writes at import time. |
| C6 | No credentials, tokens, or secrets in any generated file, including the manifest. |
| C7 | Runtime dependencies only, with version ranges starting from [hello_world requirements](../../demos/hello_world/requirements.txt): FastAPI, Pydantic, Uvicorn, and only needed packages. |
| C8 | Package folder must not be excluded by `.dockerignore`; the helper reads the build template's exclusions. |

## Exit codes

| Code | Meaning and action |
| --- | --- |
| 0 | Check passed; continue. Keep missing `.gitignore` entries for the closing message. |
| 30 | File conflict; list conflicts and stop without deleting, renaming, or overwriting developer files. |
| 31 | Tenancy file missing, unreadable, incomplete, or containing effective placeholders; continue authoring and report required corrections before push/deploy. |
| 64 | Missing PyYAML or helper import: activate the project Conda environment or set `OCI_AGENT_PYTHON`. Otherwise invalid arguments, target, names, manifest, templates, or file operation: report and correct the input; ask for an explicit `--package` if its derived name is invalid. Stop until resolved. |

## Closing message

List these four items in order:

1. Files created, any `.gitignore` kept, and parts implemented outside the
   supported shape, if any; state that those additions are outside its tests
   and acceptance criteria. For an agent that calls OCI Generative AI, add:
   in `api_key` mode, put `GENAI_API_KEY` in the tool's `.env` (or export it)
   before the build; in `resource_principal` mode, the Generative AI project
   and the runtime policies of [IAM policies](../../docs/iam-policies.md) must
   exist before the deploy, and LLM calls answer 502 in the local
   verification, as expected. For an agent with a database: the local
   verification runs without it (`database: not_configured`, and 503
   `DATABASE_UNAVAILABLE` for the endpoints that need it), the database
   checks run in the remote verification, creating the application takes
   several minutes, and deleting the application loses the data.
2. **Review `agent.yaml`**: access profile, any needed runtime variables not
   specified (link to the [manifest reference](../../docs/agent-manifest-reference.md)),
   and whether the functional check matches the expected behavior.
   Recommend keeping `public-noauth` for the first release and its tests.
   Switching later to identity-domain token protection (`public-idcs`) requires
   a new application name because the access mode is fixed at creation.
3. Tenancy check result, missing/placeholder keys and file issues, plus required
   entries missing from a kept `.gitignore`; the developer adds those entries.
4. Suggest the next request, for example: "Build version 0.1.0 of this agent".

## Limitations

The skill generates one POST JSON business endpoint (with the read endpoints
of guideline B10 for an agent with a database) and no agent tests, README,
development requirements, or test UI. The local verification has no database:
the SQL of an agent with a database runs for the first time in OCI.
Packages needing compilation fail the build because the base image has no
compiler; prefer a version or alternative with a `linux/amd64` wheel.
Files present before this session are never modified. No local syntax or
manifest check establishes runtime behavior or OCI compatibility; building
and execution belong to the next skill.
