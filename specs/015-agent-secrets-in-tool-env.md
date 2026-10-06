# Spec 015: agent secrets in the tool's `.env`

Status: implemented; offline checks and operator end-to-end test passed.
Date: 2026-10-06.

## Problem

Agents that call an LLM need an API key at runtime (`GENAI_API_KEY`, passed
with `runtime.env` `from_env`). Today:

* `from_env` reads only the environment of the process that runs the
  scripts. With Codex as a VS Code extension, the key must be exported before
  VS Code starts, or Codex reads a local file and the key enters the chat.
* Every agent folder ends up with its own copy of the key (`.env.local`).
* The runtime source report prints the resolved `from_env` value, so the key
  appears in the build verification and in the deploy plan.

## Decision

The tool's `.env` (in the tool home, or the file selected by
`OCI_AGENT_ENV_FILE`) may also hold the secrets that agents need, such as
`GENAI_API_KEY`. The file is already ignored by Git and read by the tool;
one file serves every agent and every client (Codex CLI, VS Code extension,
Claude Code), because the tool reads it, not the session. Vault remains
available but is not required.

## Scope

* `from_env` resolves its source from the process environment first, then
  from the tool's `.env`.
* The runtime source report never prints a `from_env` value.
* Documentation of the new role of `.env`, and an example entry in
  `.env.example`.

## Non-goals

* Exporting secrets as tenancy settings: the four tenancy keys stay the only
  keys exported by `load_tenancy_settings`. Note: during a deploy, the resolved
  runtime variables are also held in `OCI_DEPLOY_RUNTIME_JSON` (Spec 012) so
  that error messages can be masked; the deploy's child commands can therefore
  see them, as they already could when the key was exported in the shell.
* Updating the runtime variables of an existing Hosted Application after a
  key rotation (TODO item 12).
* Encryption of the file; it is a local, owner-readable file, like
  `~/.oci/config`.

## Intended behavior

1. **Resolution.** For `from_env: NAME`, the value is taken from the
   environment variable `NAME` when it is set and non-empty; otherwise from a
   `NAME=VALUE` line of the tool's `.env`, parsed by `tool_config.py` with the
   same rules as the tenancy keys (comments, blank lines, one pair of
   surrounding quotes). Line breaks in the value are rejected, as today.
2. **Missing value.** The error names the variable and both places:
   "Runtime environment source is undefined: NAME. Export it, or add it to
   the tool .env file (PATH)." Exit codes are unchanged.
3. **Report.** `Runtime environment: NAME source=from_env origin=<environment
   | tool .env> value=<hidden>`. Literal `value` entries are still printed:
   they are committed, non-secret data. Vault lines are unchanged.
4. **No other change.** The OCI request and the local verification container
   receive the resolved value exactly as today.

## Documentation

* `.env.example`: header comments describing the two kinds of entries
  (tenancy settings; agent secrets, never shared or committed), and a
  commented `# GENAI_API_KEY=` example, so a placeholder is never deployed.
* README (Setup step 2 and Security), `docs/agent-manifest-reference.md`
  (`from_env` row), `docs/using-oci-agent-skills.md` (tenancy file and
  runtime variables), the deploy skill (plan report), the `oci-agent-new`
  guidelines (B2), Spec 006 (resolution and report), `AGENTS.md` (the file may
  hold secrets: never print, copy, or commit it).
* `CHANGELOG.md`.

## Tests (offline)

`tests/test_agent_manifest.py`:

* the environment value wins over the `.env` value;
* without an environment value, the `.env` value is used;
* missing in both: the error names the variable and the file;
* the report shows `origin=environment` or `origin=tool .env` and
  `value=<hidden>`, and never the value;
* the tenancy keys exported by `load_tenancy_settings` are unchanged.

## Acceptance criteria

1. The offline tests pass, with Black and Pylint.
2. With `GENAI_API_KEY` only in the tool's `.env` and not exported, the build
   verification of an agent that uses it passes, and neither its output nor
   the deploy plan contains the key.

## Verification record

### 2026-10-06, macOS, local

* Offline: four new tests in `tests/test_agent_manifest.py` (tool `.env`
  fallback, environment precedence, missing value, no export of agent
  secrets). Full suite: 344 passed, 132 skipped, all skips with the reason
  `pwsh is unavailable`. Black and Pylint (10.00/10) passed.
* Real manifest (`express_order`), `GENAI_API_KEY` not exported and present
  only in a temporary tool `.env` with a dummy value: the report printed
  `GENAI_API_KEY source=from_env origin=tool .env value=<hidden>`, while the
  OCI JSON payload contained the value, as intended.

### 2026-10-06, operator test

* Criterion 2: the operator ran a real test with `GENAI_API_KEY` only in the
  tool's `.env` and reported that it works. Details of the run (agent, build
  and deploy output) were not recorded here.
