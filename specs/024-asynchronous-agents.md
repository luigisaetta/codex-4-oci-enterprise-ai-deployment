# Spec 024: asynchronous agents (start a job, then read its status)

Status: implemented; offline checks passed; live acceptance pending (agent to be chosen).
Date: 2026-10-13.
Amends [Spec 011](011-skill-oci-agent-new.md) and
[Spec 017](017-oci-agent-new-llm-agents-supported.md) (supported shape),
[Spec 006](006-agent-manifest-configuration.md) (functional checks), and
[Spec 018](018-skill-oci-agent-ui.md) (demo UI).

## Problem

An agent that runs several LLM steps takes from tens of seconds to minutes
per request. The tool supports only synchronous agents: one POST that answers
with the result. The verifier allows 60 seconds per request, the UI bridge 90
seconds, and the gateway's own limits are unknown. `multimodal-extraction`
(2026-10-09) needed an asynchronous design, which Codex built outside the
skills.

## Scope

1. A standard asynchronous API contract, in the agent guidelines.
2. `oci-agent-new` accepts it as a supported shape and generates agents that
   follow it, with one replica (Spec 023).
3. A functional check that starts a job and polls its status, for the local
   and the remote verification.
4. The demo UI template starts a job, shows the steps as they complete, and
   then the result.
5. A guideline on conversation history with the OCI Responses API, found
   twice in real sessions.

## Non-goals

* Persistent jobs (Object Storage, a database), or more than one replica.
* Streaming responses.
* Cancelling a job.
* An LLM-based demo: the acceptance agent below simulates the steps.

## The contract

* **Start:** `POST /<path>` with the request body. Invalid input answers 400
  with the error schema of guideline B3, synchronously. A valid request
  answers **202**:

  ```json
  {"job_id": "<id>", "status": "queued", "steps": [{"name": "extract", "status": "pending"}]}
  ```

* **Status:** `GET /<path>/{job_id}` answers 200:

  ```json
  {"job_id": "<id>", "status": "running", "steps": [{"name": "extract", "status": "completed"}, {"name": "classify", "status": "running"}], "result": null, "error": null}
  ```

  * `status`: `queued`, `running`, `completed`, or `failed`.
  * `steps`: every step in order, each `pending`, `running`, `completed`, or
    `failed`.
  * `result`: the business result when `completed`, otherwise `null`.
  * `error`: `{"code": …, "message": …}` in business language when `failed`,
    otherwise `null`.
* An unknown or expired `job_id` answers 404; too many jobs at once answer
  429. A `job_id` has only letters, digits, `-`, and `_`.
* Jobs live in memory, at most 10 at a time, and expire 30 minutes after
  they end. The manifest sets one replica (`deploy.scaling`, Spec 023).

## Intended behavior

### Agent guidelines (`oci-agent-new`)

* **B8. Asynchronous agents.** Use the contract when the agent runs more than
  one LLM call per request, or a request can take more than about 20
  seconds. Run the job in the background (`asyncio`), with a timeout per step
  and for the whole job; run independent steps in parallel. A failed step
  fails the job with a business message; the cause goes to the log. Set
  `deploy.scaling` to one replica. The deterministic functional check (B5)
  uses the synchronous validation of the start request (400), which needs no
  LLM.
* **Q6. Conversation history.** With the OCI Responses API, replay previous
  assistant turns as assistant messages with `output_text` content, never as
  plain strings: the service rejects them ("Invalid value: 'input_text'").
* The specification template gains a **Steps** section (name and meaning of
  each step) and the asynchronous form of the API section.
* The skill's supported shape: one synchronous POST, or the asynchronous pair
  of this specification. Constraint C3 changes accordingly.

### Functional checks

A check may have a `poll` section:

```yaml
verify:
  - method: POST
    path: /analyses
    body: {text: "…"}
    expect_status: 202
    poll:
      path: /analyses/{job_id}
      until_status: completed
      timeout_seconds: 300
      interval_seconds: 3
    expect_json: {status: completed}
```

* `poll.path` must contain `{job_id}`; `until_status` is required;
  `timeout_seconds` is 1–1800 (default 300); `interval_seconds` is 1–60
  (default 3). `poll` is allowed only for POST checks.
* The runner sends the POST, checks `expect_status`, reads `job_id` from the
  response, then sends GET requests to `poll.path` until `status` equals
  `until_status`, the job ends `failed`, or the timeout expires. A `failed`
  job, a 404, or the timeout fail the check. `expect_json` applies to the
  final status response. Each request keeps the existing per-request
  timeout.
* A check may set `local: false`: the local verification of the image
  (`oci-agent-build`) skips it, the remote verification runs it. Use it for
  checks that need the LLM when the agent uses Resource Principal, which
  works only in OCI.
* The runner is shared by the local and the remote verification, so no Bash
  or PowerShell script changes, except the local verification asking only for
  the local checks.

### Demo UI template (`oci-agent-ui`)

* `demo-config.js` gains `mode: "sync"` (default) or `"async"`, a `steps`
  list (the `name` of each step and its business label), and the message
  shown while working.
* The bridge forwards `GET /api/agent?job=<id>` to
  `AGENT_BASE_URL + AGENT_PATH + "/" + <id>`, with the token for
  `public-idcs` agents; it accepts only safe job identifiers, and returns the
  same categories as today.
* In `async` mode the page sends the POST, then polls every 2 seconds, up to
  15 minutes; it shows each step with its business label and status, then
  the result through the existing configuration. A `failed` job shows its
  business message; a timeout shows the unavailable message.

## Documentation

* `docs/agent-manifest-reference.md`: `poll` and `local`.
* `skills/oci-agent-new` (SKILL.md, guidelines, specification template),
  `skills/oci-agent-ui` (SKILL.md, guidelines, UI specification template),
  the verify and build skills (the new check).
* `CHANGELOG.md`.

## Tests (offline)

* `tests/test_agent_manifest.py` or a new module: `poll` and `local`
  validation (missing `{job_id}`, `poll` on GET, ranges, unknown fields); the
  `checks --local` filter.
* `run_manifest_checks.py` against a local fake asynchronous agent: a job
  that completes after a few polls passes; `failed`, a 404, a missing
  `job_id`, and the timeout fail with clear messages.
* `tests/test_ui_template.py`: the bridge has a GET handler that validates
  the job identifier; the page has the asynchronous mode; the configuration
  documents `mode` and `steps`.
* `tests/test_skills.py`: the new-agent skill names the asynchronous shape and
  links guideline B8.

## Acceptance criteria

1. The offline tests, Black, Pylint, and pytest pass; links resolve.
2. Live, with the acceptance agent below: created with `oci-agent-new`, it
   passes the local verification and the remote verification with a polling
   check, its Hosted Application has one replica (Spec 023), and its demo UI
   shows the steps and the result, and the business message of a failed job.

## Acceptance agent

A minimal asynchronous agent without LLM calls, so that a failure points to
the asynchronous mechanics, the gateway, or the UI, not to a model:

* Order check for Supremo's order desk: `POST /order-checks` with a customer
  reference and order lines (part code, quantity) starts a job with three
  steps, `validate`, `availability`, and `confirmation`.
* Each step waits `STEP_DELAY_SECONDS` seconds (runtime variable, value 10),
  so a job takes about 30 seconds.
* The result reports the number of lines, the total quantity, and a
  confirmation sentence, all deterministic, so the polling check can use
  `expect_json`. A line with quantity 0 makes `availability` fail with a
  business message.
* Profile **`public-idcs`**, with the confidential application already used
  for Specs 010 and 022: the polling check and the UI's status requests then
  also exercise the bearer token on repeated GET requests.
* `deploy.scaling` with one replica.

## Verification record

### 2026-10-13, macOS, local

* `scripts/agent_manifest.py`: `poll` and `local` validation, defaults
  (300 and 3 seconds), and `checks --local`; `verify_image.sh` and
  `AgentManifest.psm1` ask only for the local checks.
* `scripts/run_manifest_checks.py`: `send`, `poll_job`; `expect_json` applies
  to the final status response.
* `oci-agent-new`: guidelines B8 (contract, one replica, checks) and Q6
  (conversation history); a Steps section in the specification template; the
  asynchronous shape in the skill and constraint C3.
* UI template: the bridge forwards `GET ?job=<id>` with a safe-identifier
  check; the page has the `async` mode with steps; `demo-config.js` has
  `mode`, `steps`, and `messages.failed`; guideline T6; a Steps section in the
  UI specification template.
* `next build` of the changed template passed (Next.js 16, 22 packages). With
  `next start` against a local fake asynchronous agent, the bridge returned
  the start answer, then `running` and `completed`; an invalid identifier gave
  `invalid`, an unknown job `unavailable` with the cause in the server log.
* Offline: `tests/test_async_checks.py` (validation, the local filter, and the
  runner against a fake job API: completion, failed job, lost job, missing
  `job_id`, timeout), plus new tests in `tests/test_ui_template.py` and
  `tests/test_skills.py`. Full suite: 410 passed, 145 skipped (all `pwsh is
  unavailable`); Black and Pylint (10.00/10) passed.
* Pending: acceptance criterion 2, with an agent chosen later.
