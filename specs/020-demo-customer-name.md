# Spec 020: approved demo customer name

Status: implemented (amended 2026-10-12 with `AGENTS.md`); offline checks
passed; operator end-to-end test passed.
Date: 2026-10-12.
Amends [Spec 011](011-skill-oci-agent-new.md) (no network use, except the
online searches below) and [Spec 018](018-skill-oci-agent-ui.md).

## Problem

While describing an agent or a demo, a developer may give the name of the
real customer. That name helps Codex understand the business context, but it
must never appear in what is shown during a demo, nor in any file on disk.
The legal office has approved one name for demos: **Supremo**. Today nothing
in `oci-agent-new` or `oci-agent-ui` keeps the real name out of the generated
files.

### Issue found (2026-10-12)

The first version put the rule only inside the two skills. In an existing
demo repository the developer asked Codex to change the customer to the real
one and to add a language selector. Codex treated it as an edit of existing
files: no skill was loaded, and it wrote the real name into `agent-spec.md`
and `ui/ui-spec.md`. A rule that must always apply cannot live only in
skills, because Codex loads a skill only for matching requests. Codex reads
the workspace's `AGENTS.md` in every session.

## Scope

* A rule in `oci-agent-new` and `oci-agent-ui`, and in their guidelines: the
  real customer name is used only in the conversation and, when useful, in
  online searches; every file on disk uses the approved demo name.
* The approved demo name is read from the tool's `.env`
  (`DEMO_CUSTOMER_NAME`); when it is not set, the name is `Supremo`.
* A read-only helper that prints the demo name, so that Codex never reads
  `.env` itself (it can hold agent secrets).
* A final check by Codex, before the closing message, that the real name does
  not appear in the files it generated.
* `.env.example` and documentation.

## Non-goals

* Detecting a real customer name that the developer did not identify as such.
  The rule applies to the name the developer gives as the customer's.
* Anonymizing other data the developer provides (people, products, figures):
  the existing rules on private data apply.
* Codex's own conversation transcripts, which Codex stores on the local disk
  (for example under `~/.codex/sessions`): they are outside the control of
  the skills. See "Known limits".

## Intended behavior

1. **Demo name.** Before drafting, each skill runs the helper:

   ```bash
   python "$TOOL_HOME/scripts/tool_config.py" demo-customer
   ```

   It prints `DEMO_CUSTOMER_NAME` from the environment or the tool's `.env`,
   or `Supremo` when it is not set. It prints nothing else, and never another
   `.env` value.
2. **Real name in the conversation.** When the developer names the real
   customer, Codex confirms in its next message, without repeating the real
   name: "In every file and in the demo the customer is called <demo name>."
3. **Online searches.** Codex may use the real name in online searches, only
   when they help to understand the customer's business (sector, processes,
   public terminology). This sends the name to the search service: it is an
   explicit external data transfer, authorized by this specification.
   Results are summarized in business terms; product names, brands, people,
   addresses, or figures that identify the real customer are not copied into
   any file.
4. **Files on disk.** The real name never appears in any file written by the
   skills, in any form (full name, abbreviation, domain, or e-mail address):
   * `oci-agent-new`: `agent-spec.md` (the Business context says
     "Customer: <demo name>"), agent code, LLM instructions and prompts,
     packaged data and examples, functional checks, `agent.yaml` (application
     and repository names), README;
   * `oci-agent-ui`: `ui/ui-spec.md`, `app/demo-config.js` (titles, story,
     labels, example requests, messages), and every other file of `ui/`.
   The same applies to commit messages that Codex proposes.
5. **Final check.** Before its closing message, the skill searches the files
   it wrote for the real name and its obvious variants, case-insensitively,
   with a local search. If any is found, Codex replaces it with the demo name
   and reports the fix, never the name. When no real name was given, the
   check is skipped.
6. **No real name given.** The files use the demo name wherever a customer is
   named; the skill never asks for the real name.
7. **`AGENTS.md` in the agent repository.** The same rules are written into a
   marked block of the agent repository's `AGENTS.md`, so that they apply in
   every later Codex session, with or without a skill:

   ```bash
   python "$TOOL_HOME/scripts/agent_instructions.py" ensure --target <agent-folder>
   ```

   The command creates `AGENTS.md`, appends the block to an existing file, or
   refreshes only the block (prints `created`, `appended`, `updated`, or
   `unchanged`); it never changes content outside the block and exits 64 for
   a missing folder or an unbalanced marker. The block text lives in
   `skills/oci-agent-new/assets/agent-instructions.md`. `oci-agent-new` runs
   it after render, `oci-agent-ui` after copying the template, and the
   developer runs it once for agent folders created earlier (Getting started,
   step 5). `.dockerignore` already excludes `**/*.md` from the image.

## Configuration

`.env.example` gains a commented, non-secret entry:

```dotenv
# Approved customer name for demos (default: Supremo).
# DEMO_CUSTOMER_NAME=Supremo
```

## Known limits

* Codex stores its conversations on the local disk. If the developer types the
  real name, it is in that transcript, outside the repository. To keep it off
  the disk entirely, do not type it.
* The final check finds the name only in the forms Codex searches for.
* `AGENTS.md` is an instruction, not a technical block: Codex follows it, but
  nothing prevents a write. The final search reduces the risk; it does not
  remove it.

## Tests (offline)

* `tests/test_tool_config.py`: `demo-customer` prints the value from the environment, then from `.env`,
  then `Supremo`; it never prints another `.env` entry, including a secret
  placed in the same file.
* `tests/test_agent_instructions.py`: create, append keeping existing
  content, idempotent rerun, refresh of a stale block only, and exit 64 for a
  missing folder or an unbalanced marker without writing.
* `tests/test_skills.py`: both skills state the rule, link the helper, run
  `agent_instructions.py ensure`, and include the final check; the agent specification template names the
  customer with the demo name.

## Acceptance criteria

1. The offline tests pass, with Black, Pylint, and pytest.
2. A static review confirms that both skills, their guidelines, and the
   templates agree with this specification.
3. A real session: the developer names a real customer, both when creating an
   agent and when editing an existing one without a skill; `agent-spec.md`,
   the agent files, `ui/ui-spec.md`, and the UI show only the demo name, and
   a local search of the repository for the real name finds nothing.

## Verification record

### 2026-10-12, macOS, local

* `scripts/tool_config.py demo-customer` added; `.env.example` documents
  `DEMO_CUSTOMER_NAME`. Both skills have a "Customer name" section and run
  the check before the closing message; guidelines B7 (agent) and E7 (UI);
  both specification templates carry `{{DEMO_CUSTOMER_NAME}}`; Getting
  started step 5 explains the rule.
* Offline: three new tests in `tests/test_tool_config.py` (default, `.env`
  value without printing a secret of the same file, environment precedence)
  and one in `tests/test_skills.py`. Full suite: 356 passed, 132 skipped (all
  `pwsh is unavailable`). Black and Pylint (10.00/10) passed.
* Pending: acceptance criterion 3, a real Codex session.

### 2026-10-12, issue found and amendment

* Real session in an existing demo repository: no skill was loaded and the
  real name reached `agent-spec.md` and `ui/ui-spec.md` (see "Issue found").
  Both files were corrected by hand to the demo name; a case-insensitive
  local search of the repository then found no match.
* Amendment: `scripts/agent_instructions.py`, the instruction block asset,
  the `ensure` step in both skills, Getting started step 5, and four tests in
  `tests/test_agent_instructions.py`.
* `express_order_rp` received its `AGENTS.md` with `ensure` (`created`; a
  second run printed `unchanged`).
* Offline: full suite 360 passed, 132 skipped (all `pwsh is unavailable`);
  Black and Pylint (10.00/10) passed.
* Pending: acceptance criterion 3 in both forms (new agent; edit of an
  existing agent without a skill).

### 2026-10-12, operator end-to-end test

* Criterion 3: after the amendment, the operator ran an end-to-end test and
  reported that it works: the real customer name stayed out of the files.
  The session details (which of the two forms, files checked) were not
  recorded here.
