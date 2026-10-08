# Spec 012: reliable waiting in deploy, and replacement of a failed deployment

Status: implemented in Bash and PowerShell; Windows PowerShell update of an
existing Hosted Application verified on 2026-10-08. First-application creation
with the corrected networking argument, live resume, and replacement remain
pending.
Date: 2026-10-02.

## Problem

On 2026-10-08, a PowerShell first-release attempt on Windows exited during
Hosted Application creation with `status=unknown; code=unknown; message=unknown`.
Read-only inspection found no application. The PowerShell twin discarded
unrecognized OCI CLI errors, preventing diagnosis.
Local argument inspection then found that an inline `+` expression in the
PowerShell array passed the networking JSON as two arguments. The CLI printed
usage and did not send the create request. Keep the networking JSON in one
array element and prefer an `Error:` line over `Usage:` when summarizing a
non-ServiceError CLI failure.

The Windows twin must include a bounded, redacted CLI error summary when the
response is not a parseable `ServiceError`. It must inspect both native stdout
and stderr, remove manifest runtime values from the summary, and leave remote
retry under operator control. Acceptance: a non-ServiceError CLI failure reports
an actionable line without printing runtime values; a failed create does not
trigger another create automatically. Verify with a local PowerShell failure
fixture and a read-only check of the target application after failure.

Two first releases on 2026-10-01 (`word-count` and `order_processing`)
showed that the deploy script cannot be fully trusted while OCI creates a
deployment:

* In all three observed deployment creations, `deploy_hosted_application.sh`
  stopped right after the create request with an error parsing the OCI CLI
  output, although OCI went on and created the deployment (two `SUCCEEDED`,
  one `FAILED`). The script never waited. For `order_processing`, the apply
  ended about 2 seconds after OCI accepted the creation.
* The `FAILED` creation took about 14 minutes in OCI (capacity error, see
  F4). The operator had to follow it in the Console, and the script never
  reported the cause.
* After the failure the deployment stayed `FAILED` in the application. The
  release was recovered by deleting it by hand in the Console and deploying
  again, outside the skills.

Creating an application or a deployment is an asynchronous operation that can
take 15 minutes or more. The script must wait for its outcome reliably, report
it, and support a controlled recovery.

## Scope

* A reliable wait for asynchronous creations and deletions in
  `deploy_hosted_application.sh` and its PowerShell twin, independent of the
  OCI CLI `--wait-for-state` option.
* Resuming the wait when a deploy is run again while a creation is in
  progress.
* Stopping with the OCI error when a creation fails.
* A new release case, **Replace failed deployment**: on explicit request
  only, delete a `FAILED` deployment and create a new one, after explicit
  approval.
* Realistic fake OCI CLI scenarios for the offline tests.
* Skill and documentation updates, including the narrowed "never delete"
  rule.

## Non-goals

* Retrying a failed creation automatically. On `FAILED` the script stops; a
  new attempt happens only when the user asks for it.
* Deleting anything other than a deployment in state `FAILED`: never an
  `ACTIVE`, `CREATING`, `UPDATING`, or `NEEDS_ATTENTION` deployment, never an
  application, never an artifact, never an OCIR repository or image.
* Changing artifact activation (`hosted-deployment update`), which already
  waits for `SUCCEEDED` or `FAILED` (Spec 009) and works. It moves to the
  common wait only if that is simpler; its behavior must not change.
* Recovering a `FAILED` application; it is reported, as today.

## Platform facts

### Verified on 2026-10-02 (CLI source, SDK models, read-only OCI)

| # | Fact | Evidence |
| --- | --- | --- |
| F1 | With `--wait-for-state`, the OCI CLI 3.94.0 prints the work request (`data.id`, `data.status`, `data.resources[].identifier`), not the created resource. | `generativeai_cli.py`, `create_hosted_deployment_single_docker_artifact`. |
| F2 | When the create response has no `opc-work-request-id` header, the CLI prints "Encountered error while waiting for work request…" on **stdout**, followed by the resource JSON, and does not wait. The same pattern appears 56 times in the Generative AI CLI module. | Same file; `click.echo` without `file=sys.stderr`. |
| F3 | The SDK waiter returns only on the requested states: waiting for `SUCCEEDED` alone keeps polling a `FAILED` work request until `--max-wait-seconds`. | `oci/waiter.py`, `wait_until`. |
| F4 | A creation can fail after about 14 minutes with error 500: "Generative AI application deployment could not be scheduled because node pool capacity is not currently available. Try again later." Successful creations took about 1 to 2 minutes. | Work requests of 2026-10-01 in the target compartment (`work-request list`, `work-request-error list`). |
| F5 | The real work request of a successful deployment creation contains exactly one `ocid1.generativeaihosteddeployment.` identifier; the current OCID extraction would succeed on it. | `work-request get` on the `order_processing` creation. |
| F6 | Hosted deployment and application lifecycle states: `CREATING`, `ACTIVE`, `UPDATING`, `INACTIVE`, `NEEDS_ATTENTION`, `FAILED`, `DELETING`, `DELETED`. | SDK models `HostedDeployment`, `HostedApplication`. |
| F7 | Without `--wait-for-state`, the CLI prints pure JSON with `data` and, when present, `opc-work-request-id` (a displayed header). | `oci_cli/cli_util.py`, `DISPLAY_HEADERS`. |
| F8 | `hosted-deployment delete --hosted-deployment-id … --force` exists; deletion runs as a work request (`DELETE_HOSTED_DEPLOYMENT` observed). | CLI help; work requests of 2026-10-01. |
| F9 | `work-request list` requires `--compartment-id` and accepts `--resource-id`, `--status`, and `--all`; without `--all` the CLI warns that the list may be incomplete. `work-request-error list --work-request-id` returns code and message. Both print `{"data": {"items": [...]}}`. | CLI help; observed output (read-only, 2026-10-02). |
| F10 | A failed OCI CLI request prints `ServiceError:` followed by a JSON object with `status` (integer), `code`, `message`, `opc-request-id`, `request_endpoint` (with OCIDs), and `timestamp`. A status must be read from that JSON, never searched as a substring of the whole text. A 404 has code `NotAuthorizedOrNotFound`, which also covers missing permissions. | Read-only `hosted-deployment get` on a non-existent OCID, 2026-10-02. |

### Assumptions, to confirm during implementation

| # | Assumption | Confirmed by |
| --- | --- | --- |
| U1 | The cause of the parsing error is F2 (missing header) or an immediate error of the CLI waiter; either way, the cause is the CLI wait path. | Offline reproduction of F2 output; the new design does not use that path. |
| U2 | The create response (without wait) always contains `data.id` of the new deployment, in state `CREATING`. | First live creation. |
| U3 | After a deletion, `hosted-deployment get` returns `DELETING`, then `DELETED` or HTTP 404. | Live replacement test. |
| U4 | A `FAILED` deployment has a work request with `--resource-id` equal to its OCID and status `FAILED`, from which the errors can be read. | Read-only check on an existing `FAILED` deployment, or the live test. |

## Intended behavior

### Reliable wait

A single wait routine, used for the application creation, the deployment
creation, and the deletion in the replacement case.

1. **Request without CLI wait.** Run the create or delete command without
   `--wait-for-state`. Parse its JSON (F7): `data.id` and, when present,
   `opc-work-request-id`. If the output is not valid JSON or has no id, the
   script does not give up blindly: it looks the resource up read-only (the
   application by display name; the deployment as the single non-deleted
   deployment of the application) and continues the wait from there, or
   stops with a clear message if nothing is found.
2. **Own polling** of the resource state with `get`, every 30 seconds:
   * `ACTIVE` → success;
   * `FAILED` → read the errors (F9, U4), print code and message, exit 1;
   * `DELETED` or 404 after a deletion → deletion complete;
   * `CREATING`, `UPDATING`, `DELETING` → keep waiting;
   * any other state → stop with the state reported, exit 1.

   The work request errors are read with `work-request list
   --compartment-id … --resource-id … --status FAILED --all`, then
   `work-request-error list --work-request-id … --all`, both parsed as
   `data.items` (F9).
3. **Timeout** set with `--timeout-seconds`, default **1800**. When it
   expires and the resource is still in progress, the script prints the
   resource OCID, its state, and the elapsed time, says that nothing was
   changed or deleted and that the operation continues in OCI, and exits
   **26** ("still in progress"). This is not a failure.
4. **Transient errors.** A failed `get` (for example HTTP 404 within the
   first minute after creation, 429, or 5xx) is retried, up to five
   consecutive failures, then the script stops with the last error, exit 1.
   The HTTP status is the `status` field of the CLI `ServiceError` JSON
   (F10). A failure without a readable status is not transient, and is never
   treated as a completed deletion.
5. **Failed requests.** When a create or delete request itself is rejected,
   the script prints the `status`, `code`, and `message` of the
   `ServiceError`, with runtime variable values masked, and exits 1. It never
   prints the raw CLI output.
6. **Progress.** One line per poll: resource kind, state, elapsed time. The
   line never contains secrets or runtime variable values.

### Release cases

The cases of Spec 009 stay. The table adds the states that today stop the
deploy with "must be ACTIVE":

| Case | Condition | Plan shows | `--apply` does |
| --- | --- | --- | --- |
| Creation in progress | Deployment `CREATING` | The deployment, its state, how long since creation | Resumes the wait; no mutation |
| Application creation in progress | Application `CREATING` (a first release that was interrupted) | The application, its state, how long since creation; then the deployment that will be created with the target tag | Waits for the application to become `ACTIVE`, runs the existing application checks, then creates the deployment and waits for `ACTIVE` |
| Failed deployment | Deployment `FAILED`, without `--replace-failed` | The deployment OCID, the failure code and message, and how to request a replacement | Nothing; exit 20 |
| Replace failed deployment | Deployment `FAILED`, with `--replace-failed` | The deployment to delete (OCID, failure reason), then the deployment to create (target tag); the endpoint is unchanged | Deletes the `FAILED` deployment, waits until it is gone, creates the new deployment, waits for `ACTIVE` |

Rules:

* `--replace-failed` is accepted only together with a `FAILED` deployment.
  With any other state it exits 64 and changes nothing. It is never added by
  the skill on its own initiative: the user must ask for a new deploy after a
  failure.
* One explicit authorization covers the whole replacement shown in the plan
  (delete and create). The plan is shown again before asking.
* If the deletion fails or times out, the script stops without creating
  anything (exit 1 or 26).
* The application, its endpoint, its runtime environment, and its inbound
  authentication are not touched. The existing checks of Spec 009 (profile,
  runtime environment) still run before any mutation.
* A failure during a first release leaves the application `ACTIVE` with a
  `FAILED` deployment; the next deploy request reports "Failed deployment".
* "Application creation in progress" completes the first release that was
  already requested: one explicit authorization covers the wait and the
  deployment creation shown in the plan. If the application ends `FAILED`,
  or its checks (profile, runtime environment) fail once it is `ACTIVE`, the
  script stops without creating the deployment.
* The timeout applies to each wait separately (application, deletion,
  deployment).

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Unchanged. |
| 1 | Unchanged, plus: a creation or deletion ended `FAILED` (errors printed), or a resource reached an unexpected state. |
| 20 | Unchanged, plus: a `FAILED` deployment was found and `--replace-failed` was not given. |
| 26 | New: the timeout expired while the operation was still in progress; nothing was changed by the script after the request; run the deploy again to resume waiting. |
| 64 | Unchanged, plus: `--replace-failed` with a deployment that is not `FAILED`, or an invalid `--timeout-seconds`. |
| 65 | Unchanged. |

## Skills and documentation

* `oci-agent-deploy/SKILL.md`:
  * the four new cases and exit code 26;
  * on exit 26, tell the user that OCI is still working and offer to run the
    deploy again to resume waiting; never delete or recreate;
  * on "Failed deployment", report the OCI error and stop; offer the
    replacement only as an option the user may request. Use
    `--replace-failed` only after the user explicitly asks for a new deploy
    of the failed release, and only after the user approves the replacement
    plan;
  * the "never delete" rule becomes: never delete or recreate an
    application or a deployment, **except** a deployment in state `FAILED`,
    replaced on the user's explicit request through `--replace-failed`.
* `references/hosted-application.md`: facts F1–F10 in short form.
* README (release table), guide, skill catalog: the new cases, the
  replacement, and the capacity error of F4 as a known transient failure
  ("try again later").
* Spec 009: a pointer to this specification for the new cases and the
  narrowed rule.
* `tests/test_skills.py`: the assertion on the sentence "Never delete or
  recreate an application or a deployment to release a new" is updated to the
  new wording.
* `CHANGELOG.md`.

## Tests (offline)

The fake `oci` gains scenarios that match the real CLI:

* creation output without wait (F7), with and without `opc-work-request-id`;
* creation output with stdout text before the JSON (F2): the script recovers
  the resource read-only;
* deployment `CREATING` for several polls, then `ACTIVE`;
* deployment `CREATING`, then `FAILED`, with work request errors: exit 1,
  message printed, no further mutation;
* timeout while `CREATING`: exit 26, no mutation after the create;
* a rerun with a deployment `CREATING`: "Creation in progress", no create
  command issued, the wait resumes;
* `get` failing transiently (404 once, then 200): the wait continues; five
  consecutive failures: exit 1;
* a `get` error whose text contains "404" or "5xx" only inside an OCID or
  request id, with another real status (for example 401): not transient,
  and never a completed deletion;
* a rejected create or delete request: `status`, `code`, and `message`
  printed, exit 1;
* work request errors with the real shapes of F9; the fake `oci` rejects
  `work-request list` without `--compartment-id`;
* application `CREATING` on rerun: wait, checks, then deployment creation,
  in this order; application ending `FAILED`: no deployment creation;
* deployment `FAILED` without `--replace-failed`: exit 20, no mutation;
* `--replace-failed` with `FAILED`: delete, wait for `DELETED`/404, create,
  wait for `ACTIVE`, in this order;
* `--replace-failed` with `ACTIVE` or `CREATING`: exit 64, no mutation;
* deletion `FAILED` or timed out: no create command issued;
* plan mode never issues a mutating command in any scenario;
* the polling interval is configurable for tests, so that they run in
  seconds.

Bash and PowerShell, with the same report lines and exit codes.

## Acceptance criteria

1. The offline tests pass for Bash, and for PowerShell where executable.
2. Live first release of a new test application: the script waits, reports
   progress, and exits 0 with the deployment `ACTIVE`, without any manual
   step. Record the creation time.
3. Live resume: interrupt the wait (or use a short `--timeout-seconds`),
   observe exit 26, run the deploy again, and observe "Creation in progress"
   and a successful end.
4. Live replacement, when a `FAILED` deployment is available (a capacity
   failure cannot be provoked on purpose): without `--replace-failed` the
   deploy stops with the OCI error; with it, after approval, the failed
   deployment is replaced and the endpoint is unchanged. If no `FAILED`
   deployment occurs during the verification period, this criterion stays
   pending and is recorded as such.
5. `oci-agent-verify-deployment` passes after criteria 2 and 4.
6. No secret or runtime variable value appears in any progress or error line.

## Recovery and cleanup

* The test applications of the live criteria are deleted by hand in the
  Console when no longer needed; the script never deletes them.
* If a replacement stops after the deletion and before the creation, the
  application is left without deployment; the next deploy request is a
  normal "First release" reuse of the application (Spec 009).

## Open points

* Whether the application creation should also offer a replacement when it
  ends `FAILED`. Out of scope here.
* Whether the verifier should wait for `CREATING` the way it waits for
  `UPDATING` (Spec 009).

## Verification record

### Step 1 local checks — 2026-10-02

* Implemented the shared resource polling flow in the Bash and PowerShell deploy scripts, with separate helpers under `scripts/lib/`. Create and delete requests no longer use the CLI waiter; artifact activation still uses its Spec 009 path.
* The fake OCI CLI now covers creation output with and without `opc-work-request-id`, F2 text before JSON, missing IDs with read-only recovery or a clear stop, multi-poll states, work request errors, transient `get` errors, timeout, resume, and deletion before replacement. Offline scenarios assert no plan mutation and no runtime value in progress or error lines. The existing plan report still prints runtime values; masking it is outside Step 1.
* `black --check .`: passed. `pylint scripts tests`: passed (10.00/10). `pytest -q -rs`: 293 passed, 99 skipped (PowerShell unavailable), one unrelated Starlette deprecation warning. After that full run, the PowerShell helper local variable and a shared plan-report sentence were clarified; the affected static, parity, and failed-deployment plan tests passed again (26 passed, 3 PowerShell skips). Bash syntax and `git diff --check`: passed. No live OCI command was run.
* The PowerShell twin is implemented and statically checked for options and the guarded delete path. It could not be executed on this workstation because `pwsh` is unavailable. Remote acceptance criteria remain pending.
* U1: F2-shaped stdout is reproduced offline and the new create path avoids `--wait-for-state`; the actual cause of the 2026-10-01 failure is not proven offline. U2: only fake responses confirm `data.id`; the first live creation remains necessary. U3: only fake `DELETING` → `DELETED`/404 is covered; live deletion remains necessary. U4: fake work request errors are covered; the resource-ID association needs the specified read-only or live check.
* Interpretation: a resumed `CREATING` application waits without creating a deployment in that invocation, following the release-case rule that resume makes no mutation. The timeout applies separately to each create or delete wait. These details are not explicit in the acceptance text and need confirmation before Step 2 guidance.

### Step 1 review fixes — 2026-10-02

* Corrected F9 reads in both wait helpers: `work-request list` includes the compartment and `--all`; both list outputs use `data.items`. Missing, malformed, and empty payloads produce the documented fallback messages without a traceback or an early shell abort. The fake OCI CLI enforces the required compartment input and uses the observed response shape.
* Both script families now read HTTP status only from the JSON following `ServiceError:`. Offline 401 cases with `404` and `5xx` in other error fields do not retry and cannot complete a deletion. Rejected application creates, deployment creates, and deployment deletes report only status, code, and a runtime-value-masked message.
* A resumed `CREATING` application now follows the updated release case: wait for `ACTIVE`, read the application again, check inbound authentication and runtime environment, then create and wait for its deployment. This supersedes the earlier Step 1 interpretation above. An application ending `FAILED` or failing either check does not cause a deployment create.
* Local checks in the named Conda environment: `black --check .` passed; `pylint scripts tests` passed (10.00/10); `pytest -q -rs` passed (325 passed, 129 skipped, one Starlette deprecation warning). After the full run, PowerShell `data.items` parsing was tightened to reject non-array shapes; focused PowerShell static and script-parity checks passed (24 passed). Bash syntax and `git diff --check` passed. No live OCI command was run. PowerShell is implemented but remains unexecuted because `pwsh` is unavailable here; remote acceptance remains pending.
* The updated specification does not define a `CREATING` application that already has a non-deleted deployment. The scripts stop for review with exit 20 to avoid a duplicate create. F10 also says a 404 can mean missing permissions; as specified, a structured 404 after deletion counts as completion, so that distinction remains unresolved without live evidence.

### Step 2 local checks — 2026-10-02

* Updated the deploy skill, its Hosted Application reference, the skill catalog, README, operator guide, Quickstart, Spec 009 pointer, and changelog for all eight script release-case names, exit 26, explicit failed-deployment replacement, and separate push authorization. The reference summarizes Spec 012 F1–F10. Corrected the older three-case/F1–F9 wording in this specification's documentation checklist to match the updated release-case table and Step 2 request.
* Bash and PowerShell mutation helpers now keep stderr separate from stdout JSON. The fake OCI delete can emit a successful stderr warning; the Bash replacement test confirms the JSON ID is parsed directly, without a read-only fallback lookup. The PowerShell twin uses the same separation but could not be executed on this workstation because `pwsh` is unavailable.
* In the named Conda environment, `black --check .` passed; `pylint scripts tests` passed (10.00/10, with `PYLINTHOME` directed to `/private/tmp` because the default macOS cache path is sandbox-blocked); `pytest -q -rs` passed (327 passed, 131 skipped for unavailable `pwsh`, one unrelated Starlette deprecation warning). All 57 relative Markdown links in the edited Markdown files resolved. Bash syntax and `git diff --check` passed. No live OCI command was run; remote acceptance remains pending.
* The existing F10 ambiguity remains: a structured 404 during deletion can mean either deleted or unauthorized. The scripts treat it as completed deletion under Spec 012; no offline test can establish which happened remotely.

### Live first release — 2026-10-02, eu-frankfurt-1

* Agent `order_processing` 0.1.1 (an LLM agent created with `oci-agent-new`),
  after the previous application was deleted, so the case was `First release`.
  Run from macOS with the Bash scripts, through a Codex session, with separate
  approvals for push and deploy.
* `deploy_hosted_application.sh --apply`: exit 0 in 166 seconds, no manual
  step and no parsing error. Progress lines: Hosted Application `CREATING` at
  0 s and 31 s, `ACTIVE` at 62 s; Hosted Deployment `CREATING` at 0 s, 30 s,
  and 61 s, `ACTIVE` at 92 s. No progress line contained a runtime variable
  value.
* `oci-agent-verify-deployment`: OCI state, release tag, `/health`, `/ready`,
  and the functional check passed; readiness in 3 seconds. The first two
  functional attempts timed out at the then 5-second request timeout, fixed by
  Spec 013.
* Criteria 2 and 5 passed. Criterion 3 (resume after exit 26) and criterion 4
  (replacement of a `FAILED` deployment) remain pending.

