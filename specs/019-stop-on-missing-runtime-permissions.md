# Spec 019: stop with clear instructions when runtime permissions are missing

Status: implemented; offline checks and live acceptance (criterion 3) passed.
Date: 2026-10-09; updated 2026-10-13.
Origin: issue found on 2026-10-09 (TODO item 16, completed and removed).

## Problem

### Issue found (2026-10-09)

An operator released two agents (`bn-hello-world` and
`supremo-demo-kyc-onboarding`) into their own compartment, in a tenancy where
the runtime dynamic group covered only another compartment. The facts below
come from read-only OCI calls and the Audit log, run by the tenancy
administrator's profile with his authorization.

1. Creating each Hosted Application succeeded: it needs only the operator's
   permissions.
2. Creating each Hosted Deployment failed about 90 seconds later. The work
   request `CREATE_HOSTED_DEPLOYMENT` ended `FAILED` with error 500:
   "Generative AI application deployment failed because the container image
   could not be accessed or validated. Verify the OCI Container Registry image
   path and tag, required IAM policies, and vulnerability scan results, then
   try again." The deployment was left in `NEEDS_ATTENTION`, with its artifact
   `FAILED`.
3. The deploy script reported only `reached unexpected state NEEDS_ATTENTION`
   and exited 1: it reads the work request errors for `FAILED` only
   (`scripts/lib/deploy_wait.sh`, `wait_for_resource`). Neither the operator
   nor Codex saw the cause.
4. Codex then investigated outside the skills. It tried three times to create
   a dynamic group (rejected by the tenancy's dynamic-group limit), added the
   operator's compartment to an existing dynamic group shared with another
   compartment, created a policy, and wrote its own release wrapper. The
   operator's legacy IAM permissions allowed these changes.

The changes were technically correct, but IAM changes belong to the tenancy
administrator. The skills already say that their scripts never create IAM
policies or dynamic groups (`oci-agent-deploy/SKILL.md`, Limitations), but
they gave Codex neither the cause nor an instruction to stop.

## Scope

* When a deployment ends `FAILED` or `NEEDS_ATTENTION`, the deploy script
  reports the work request errors, in the wait after a create and in the plan
  of an existing deployment.
* When the error says that the container image could not be accessed, the
  script checks, read-only, whether the image tag exists in OCIR, and prints
  one fixed message:
  * image found: missing runtime permissions, with the exact request for the
    tenancy administrator;
  * image not found: missing image or tag, with the push to run.
* A dedicated exit code for the runtime permissions case.
* An instruction in `oci-agent-deploy` to report that message and stop,
  without any IAM change.
* The rule against IAM changes also in the agent repository's `AGENTS.md`,
  because Codex investigates failures outside the skills (the lesson of
  Spec 020).
* Bash and PowerShell twins in parity; offline tests; documentation.

## Non-goals

* Recovering a `NEEDS_ATTENTION` deployment (deleting or replacing it). The
  message states the current limit; recovery is a separate change.
* Checking IAM before the deploy, or in the setup check: the runtime principal
  exists only in OCI, and reading dynamic groups and policies needs IAM
  permissions that an operator should not have (see TODO item 10).
* Interpreting any other OCI error. Other errors are printed as today, with
  their code and message.
* Removing IAM permissions from operators: an administrator decision.

## Platform facts (verified 2026-10-09, read-only OCI)

| # | Fact | Evidence |
| --- | --- | --- |
| F1 | A failed deployment creation can leave the deployment in `NEEDS_ATTENTION`, not `FAILED`, with the artifact `FAILED`. | `hosted-deployment get` on both deployments. |
| F2 | `work-request list --compartment-id … --resource-id <deployment-ocid> --status FAILED --all` returns the `CREATE_HOSTED_DEPLOYMENT` work request of a `NEEDS_ATTENTION` deployment. | Read-only call. |
| F3 | Its `work-request-error list` returns code `500` and the message quoted in the Problem. | Read-only call. |
| F4 | The failing artifact reports `is-vulnerability-scan-required: false`; image scanning was not required. The message's mention of scan results is generic. Confirmed live the same day: a first release succeeded after the vulnerability-scanning statements were removed from the administrator's compartment, with only the runtime `read repos` statement. | `hosted-deployment get`; first release of `hello-world`, 2026-10-09. |
| F5 | `artifacts container image list` accepts `--compartment-id`, `--repository-name`, `--image-version`, and `--all`; the operator's `manage repos` permission covers it. | CLI 3.94.0 help; `docs/iam-policies.md`. |
| F6 | Exit codes in use by the deploy script: 0, 1, 20, 26, 64, 65. | `oci-agent-deploy/SKILL.md`, Exit codes. |

### Assumption

| # | Assumption | Confirmed by |
| --- | --- | --- |
| U1 | The phrase "container image could not be accessed" identifies this case in the error message. The match is case-insensitive on that phrase only; if OCI changes the text, the script falls back to printing the error as it is. | The live test of the acceptance criteria. |

## Intended behavior

1. **Errors for every failed outcome.** In the wait after a deployment
   create, `FAILED` and `NEEDS_ATTENTION` are both treated as failed: the
   script reports the work request errors, as it does today for `FAILED`. In
   the plan, an existing deployment in `NEEDS_ATTENTION` is reported with the
   same errors before the script stops: exit 20, unchanged, or exit 27 when
   the errors match the runtime permissions case below. An existing `FAILED`
   deployment whose errors match also stops with exit 27, in plan and apply,
   unless the user requested its replacement (`--replace-failed`). In the
   plan, the image check uses the requested tag.
2. **Image check.** If an error message contains "container image could not
   be accessed", the script lists the image with `--repository-name` and
   `--image-version` set to the release's repository and tag, read-only.
3. **Runtime permissions message** (image found), exit **27**, on stderr:

   ```text
   Release stopped: the Hosted Deployment cannot read its image from OCIR.
   The image exists: <registry>/<namespace>/<repository>:<tag>
   Cause: the runtime permissions for compartment <compartment-name> are missing.
   This is tenancy IAM setup, done by your tenancy administrator.
   Do not create or change dynamic groups or policies.

   Send this to your tenancy administrator:
     1. A dynamic group whose rules include Hosted Applications and Hosted
        Deployments in compartment <compartment-name> (<compartment-ocid>).
     2. allow dynamic-group <runtime-dynamic-group> to read repos in compartment <compartment-name>
     See <tool-home>/docs/iam-policies.md, "Runtime: dynamic group" and
     "Runtime: policies".

   Deployment <deployment-ocid> is <state>.
   ```

   It ends with the next step for the observed state: for `FAILED`, "When the
   administrator confirms, ask for a new deploy: the plan offers to replace
   the failed deployment"; for `NEEDS_ATTENTION`, "The skills cannot yet
   replace a deployment in this state: after the administrator confirms,
   delete it in the OCI Console, then ask for a new deploy."
4. **Missing image message** (image not found), exit 1. The image is searched
   in the deploy compartment, because that is where the runtime's `read repos`
   applies. The message says that the image is not in an OCIR repository of
   that compartment; that a repository of another compartment may not be
   readable by this runtime; and to push it with `oci-agent-push` to a
   repository of this compartment (image paths do not include the
   compartment, so `publish.repository` must not be used by another
   compartment), then deploy again. No IAM text.
5. **Values in the message** come from validated inputs and read-only OCI
   calls: compartment name and OCID, image reference, deployment OCID and
   state. The message contains no runtime variable value; the existing
   masking of error messages still applies.
6. **Skill instruction.** `oci-agent-deploy/SKILL.md` adds exit 27 to its
   table: "Report the message verbatim and stop. Never create or modify
   dynamic groups, policies, groups, or identity domains, never retry in
   another compartment, and never write scripts or commands that bypass this
   skill, even if the user asks to fix the problem." The same rule is added
   to the skill's Limitations.
7. **`AGENTS.md`.** The instruction block written by
   `scripts/agent_instructions.py ensure` (Spec 020) gains a section "IAM
   changes": never create, change, or delete dynamic groups, policies, groups,
   users, or identity domains, even when asked to fix a problem; read-only
   inspection only on request; report what is missing and hand it to the
   tenancy administrator. Existing agent folders receive it by running
   `ensure` again.

## Relation to the merged Windows changes

Pull request #4 changed `Write-HostedServiceError`, which summarizes a
failed **CLI call** (create or update) that is not a `ServiceError`. The case
of this specification is different: the create call succeeds, and the error
arrives later, in the failed **work request**. The changes therefore extend
the work request functions (`report_work_request_errors` and
`wait_for_resource` in Bash; `Get-HostedWorkRequestErrors` and
`Wait-HostedResource` in PowerShell) and reuse only their existing masking of
runtime values.

## Documentation

* `oci-agent-deploy/SKILL.md`: exit 27 and the rule above.
* `docs/iam-policies.md`: a note in "Runtime: policies" on the symptom
  (deployment `FAILED` or `NEEDS_ATTENTION`, "container image could not be
  accessed") and on F4 (scanning not required).
* `docs/quickstart.md`: one troubleshooting row for the message.
* `CHANGELOG.md`.

## Tests (offline)

With the fake `oci` of `tests/test_deploy_release_cases.py`, for both script
families:

1. A create that ends `NEEDS_ATTENTION` with the image-access error and an
   existing image: exit 27, the message with compartment, image, and
   deployment state, and no further mutation.
2. The same with state `FAILED`: exit 27 and the `FAILED` next step.
3. Image-access error and no image: exit 1 and the missing-image message.
4. A different error (for example the capacity error of Spec 012): exit 1,
   the error printed as today, and no runtime permissions message.
5. Plan on an existing `NEEDS_ATTENTION` deployment: the work request errors
   are printed, exit 27 for the image-access error (exit 20 for any other
   error), and no mutation.
6. A runtime variable value in the error text is masked.
7. `tests/test_agent_instructions.py`: the block contains the IAM section.

## Acceptance criteria

1. The offline tests pass for Bash and PowerShell, with Black, Pylint, and
   the parity test.
2. A static review confirms that the skill instruction and the script
   messages match.
3. Live (with authorization): a first release into a compartment that the
   runtime dynamic group does not cover ends with exit 27 and the message,
   and Codex reports it and stops without any IAM call. This confirms U1.

## Verification record

### 2026-10-13, macOS, local

* Implemented in `scripts/lib/deploy_wait.sh`, `scripts/deploy_hosted_application.sh`,
  `scripts/lib/DeployWait.psm1`, and `scripts/deploy_hosted_application.ps1`;
  exit 27 and the IAM rule in `oci-agent-deploy/SKILL.md`; the "IAM changes"
  section in `skills/oci-agent-new/assets/agent-instructions.md`; notes in
  `docs/iam-policies.md` and `docs/quickstart.md`.
* The fake OCI CLI gained configurable work request errors and
  `artifacts container image list`; the scenarios live in
  `tests/test_deploy_runtime_permissions.py` (registered through
  `EXTRA_SCENARIOS`).
* The real `artifacts container image list` output was checked read-only:
  `{"data": {"items": [...], "remaining-items-count": 0}}`, with an empty list
  for a missing tag.
* Offline: full suite 369 passed, 141 skipped (all `pwsh is unavailable`);
  Black and Pylint (10.00/10) passed. The PowerShell twin is statically
  reviewed only. In one of three runs of the deploy test modules a single test
  failed and passed on rerun; it was not identified.
* Pending: acceptance criterion 3 (live, in a compartment without runtime
  `read repos`).

### 2026-10-13, first live attempt (not valid for criterion 3)

* Compartment `lsa-spec019` under `specialists-shared`, without runtime
  policies; application `helloworld-spec019` created and `ACTIVE`.
* The deployment succeeded because Codex reused the existing image
  `agents/hello-world:0.1.0`, whose repository is in the administrator's
  compartment, where the runtime has `read repos`. No repository was created
  in `lsa-spec019`. OCIR image paths do not include the compartment.
* Consequences: the missing-image message now says that the image is not in
  a repository of the deploy compartment and why a repository of another
  compartment may not be readable; the test must use a repository name of its
  own (a copy of `hello_world` outside the tool home). In the tool home Codex
  also edited `demos/hello_world/agent.yaml`, `specs/hello_world.md`, and
  `CHANGELOG.md`; those edits were not part of this specification.

### 2026-10-13, live acceptance (criterion 3)

* Agent: a copy of `hello_world` outside the tool home, `publish.repository:
  agents/hello-spec019`, `deploy.application_name: hello-spec019`; tag
  `0.1.0`; compartment `lsa-spec019` under `specialists-shared`, without
  runtime `read repos`; macOS, Bash, a new Codex session in the agent folder.
* The push created the repository in `lsa-spec019`; the application became
  `ACTIVE`; the deployment ended `NEEDS_ATTENTION`. The deploy script exited
  27 with the runtime permissions message ("The image exists: …/agents/
  hello-spec019:0.1.0", "Cause: the runtime permissions for compartment
  lsa-spec019 are missing").
* Codex reported the message and stopped, citing the skill rule. Its session
  log contains no IAM call (26 tool calls).
* U1 confirmed: the phrase "container image could not be accessed" matched
  the real error.
* Observation: the root policy `ANY-USER … read repos in tenancy WHERE
  request.principal.type='computecontainerinstance'` does not cover the Hosted
  Deployment runtime, otherwise the pull would have succeeded.
* Deviation: Codex reported the first five lines verbatim but summarized the
  request for the administrator (the compartment OCID and the exact statement
  were not repeated). The script output was complete.
