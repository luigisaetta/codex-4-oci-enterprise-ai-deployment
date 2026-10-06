# Spec 017: `oci-agent-new` supports agents that call OCI Generative AI

Status: implemented; offline checks passed; real-session check pending.
Date: 2026-10-06.
Amends: [Spec 011](011-skill-oci-agent-new.md).

## Problem

Spec 011 created `oci-agent-new` as a first iteration in which calling OCI
Generative AI was a non-goal. Since then, the skill's guidelines (B1, B2,
Q1–Q4), Spec 015 (API keys in the tool's `.env`), and Spec 016 (Resource
Principal) define and verify how an agent calls OCI Generative AI, and every
real agent created with the skill does it. The skill instructions were not
updated:

* `SKILL.md` still opens with "work in progress (first iteration)";
* it lists "OCI service calls" among the requests outside the iteration, so
  the skill asks whether to proceed with an LLM agent, and the closing message
  says that the LLM part is outside the tests and acceptance criteria;
* its Limitations say "no OCI service calls";
* Spec 011 still lists the call as a non-goal and has the status "draft; work
  in progress".

A developer who follows the v0.6.0 release notes meets these warnings on the
main use case.

## Scope

Text changes only: `skills/oci-agent-new/SKILL.md`, Spec 011, and the
corresponding assertion in `tests/test_skills.py`.

## Non-goals

* Any change to scripts, the helper, exit codes, the templates, or the
  guidelines.
* Supporting the shapes that stay outside: `GET` business endpoints, more
  than one business endpoint, streaming, file upload. Their handling is
  unchanged.
* Shortening or restructuring `SKILL.md` beyond the passages below.
* A reference demo agent.

## Intended behavior

1. **Status.** `SKILL.md` no longer says "work in progress" or "first
   iteration"; it keeps the link to Spec 011 (and this specification) for the
   contract.
2. **Supported shape.** The section "Requests outside the first iteration"
   becomes "Requests outside the supported shape". Calls to OCI Generative AI
   are part of the supported shape: the skill follows the guidelines (B1, B2,
   Q1–Q4) without asking whether to proceed. The remaining outside shapes are
   `GET` business endpoints, more than one business endpoint, streaming, and
   file upload, handled as today (say so, ask, and mark them in the closing
   message). Calls to OCI services other than Generative AI also stay outside.
3. **Workflow step 3** refers to "outside the supported shape".
4. **Closing message, item 1**: "parts implemented outside the supported
   shape, if any". For an agent that calls OCI Generative AI, the message adds:
   * `api_key` mode: put `GENAI_API_KEY` in the tool's `.env` (or export it)
     before the build;
   * `resource_principal` mode: the Generative AI project and the runtime
     policies of [IAM policies](../docs/iam-policies.md) must exist before the
     deploy; LLM calls answer 502 in the local verification, as expected.
5. **Limitations**: remove "no OCI service calls" and the reference to the
   first iteration; keep the other limits (one POST JSON endpoint, no
   generated tests, README, development requirements, or test UI;
   compilation; existing files never modified).
6. **Spec 011**: status "implemented; amended by Spec 017"; the non-goal
   "Calling OCI Generative AI or any other OCI service" becomes "Calling OCI
   services other than OCI Generative AI (supported since Spec 017)"; a
   pointer to this specification in its "Requests outside the first
   iteration" section.
7. **Test**: `tests/test_skills.py` no longer requires "work in progress" in
   the skill; it requires the link to Spec 011 and to the agent guidelines.

## Acceptance criteria

1. `SKILL.md` contains no "work in progress", "first iteration", or "no OCI
   service calls", and names OCI Generative AI calls as supported through the
   guidelines.
2. The outside shapes and their handling are unchanged.
3. Spec 011 reflects the amendment; the skill tests, Black, Pylint, and pytest
   pass, and every relative Markdown link resolves.
4. In a real session, a request for an agent that calls an LLM is drafted and
   generated without the "outside the first iteration" question, and the
   closing message contains the item 4 reminders. (Recorded when next used.)

## Verification record

### 2026-10-06, local

* `SKILL.md`: banner replaced by the links to Spec 011 and this
  specification; section renamed "Requests outside the supported shape", with
  OCI Generative AI calls supported through the guidelines and calls to other
  OCI services kept outside; workflow step 3, closing message item 1 (API-key
  and Resource Principal reminders), and Limitations updated. No occurrence of
  "work in progress", "first iteration", or "no OCI service calls" remains.
* Spec 011: status, non-goal, and a pointer in its out-of-iteration section.
* `tests/test_skills.py`: the new-skill test requires the links to Spec 011 and
  to the guidelines, and the absence of the three phrases.
* Black, Pylint (10.00/10), and pytest passed (344 passed, 132 skipped, all
  skips with the reason `pwsh is unavailable`); every relative link in the
  edited files resolves.
* Pending: acceptance criterion 4 in a real session.
