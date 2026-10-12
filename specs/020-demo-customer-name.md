# Spec 020: approved demo customer name

Status: implemented; offline checks passed; real-session acceptance pending.
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
* Existing repositories: the rule applies to files generated from now on.

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

## Tests (offline)

* `tests/test_tool_config.py`: `demo-customer` prints the value from the environment, then from `.env`,
  then `Supremo`; it never prints another `.env` entry, including a secret
  placed in the same file.
* `tests/test_skills.py`: both skills state the rule, link the helper, and
  include the final check; the agent specification template names the
  customer with the demo name.

## Acceptance criteria

1. The offline tests pass, with Black, Pylint, and pytest.
2. A static review confirms that both skills, their guidelines, and the
   templates agree with this specification.
3. A real session: the developer names a real customer; `agent-spec.md`,
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
