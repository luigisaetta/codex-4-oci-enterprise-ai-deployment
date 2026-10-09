# Spec 019: stop with clear instructions when runtime permissions are missing

Status: draft.
Date: 2026-10-09.
Origin: issue found on 2026-10-09 (TODO item 16).

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
| F4 | The failing artifact reports `is-vulnerability-scan-required: false`; image scanning was not required. The message's mention of scan results is generic. | `hosted-deployment get`. |
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
   the errors match the runtime permissions case below.
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
4. **Missing image message** (image not found), exit 1: "The image
   `<registry>/<namespace>/<repository>:<tag>` is not in OCIR. Push it with
   oci-agent-push, then deploy again." No IAM text.
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

## Acceptance criteria

1. The offline tests pass for Bash and PowerShell, with Black, Pylint, and
   the parity test.
2. A static review confirms that the skill instruction and the script
   messages match.
3. Live (with authorization): a first release into a compartment that the
   runtime dynamic group does not cover ends with exit 27 and the message,
   and Codex reports it and stops without any IAM call. This confirms U1.

## Verification record

Pending.
