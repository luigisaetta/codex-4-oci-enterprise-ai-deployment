# Spec 009: Release a new version into an existing Hosted Application

Status: implemented (Bash; PowerShell unexecuted); live acceptance pending.
Date: 2026-09-30.

For creation waits, failed-deployment replacement, and the narrowed deletion
rule, see [Spec 012](012-reliable-deploy-wait.md). Its explicit `FAILED`
deployment replacement exception supersedes the no-deletion rule below.

## Problem

The deploy skill can only perform the **first** release of an agent:

* `deploy_hosted_application.sh` always creates a new Hosted Deployment, named
  `<application_name>-<tag>` (Spec 006);
* Spec 003 excludes updating or replacing an existing deployment.

OCI does not work this way. A Hosted Application has **one** deployment, and a
new version is a new **artifact** inside that deployment. Creating a second
deployment fails, so releasing version 0.1.1 of an agent already running 0.1.0
is impossible with the current skills. The only workaround, used during the
Spec 008 end-to-end test, was to delete the application by hand and deploy
again, which changes the endpoint URL.

## Scope

* Extend `oci-agent-deploy` (script, PowerShell twin, skill) so that one
  command handles every release of an agent: first release, new version, and
  return to a previous version (rollback).
* Identify the deployment by its application, not by a display name.
* Keep plan-first behavior and explicit authorization before every mutation.
* Update `oci-agent-verify-deployment` only where the new model requires it.
* Update the guide, README, and skill catalog.

## Non-goals

* Deleting anything: applications, deployments, artifacts, or images. The
  skills never delete; cleanup stays a manual, documented operation.
* Updating application-level settings, such as `runtime.env` or networking
  (unchanged from Spec 006: a mismatch still stops the deploy).
* Blue-green traffic splitting, canary releases, or more than one deployment
  per application.
* Vulnerability-scan requirements on artifacts
  (`isVulnerabilityScanRequired` stays false, as today).

## Verified platform behavior

Sources, consulted on 2026-09-30:

* [OCI Generative AI: Artifacts](https://docs.oracle.com/en-us/iaas/Content/generative-ai/artifacts.htm);
* OCI CLI 3.94.0 help for `oci generative-ai hosted-deployment`;
* OCI Python SDK 2.187.0 models `HostedDeployment`, `Artifact`,
  `AddArtifactDetails`, `UpdateHostedDeploymentDetails`.

Live experiment on 2026-09-30, eu-frankfurt-1, on the `text-stats`
application, with a probe calling `/health` and a test-only `/version`
endpoint every 2 seconds:

| # | Fact | Evidence |
| --- | --- | --- |
| F1 | An application accepts **one** non-deleted deployment. | `create-hosted-deployment-single-docker-artifact` on an application with a deployment: HTTP 403 `NotAllowed`, "Hosted deployment cannot be created with application id … because it already exists". |
| F2 | A deployment has a list of artifacts (image and tag) and exactly one active artifact. | Documentation; `hosted-deployment get` returns `artifacts[]` with `status` `ACTIVE` or `INACTIVE`, and `active-artifact`. |
| F3 | `add-artifact-create-single-docker-artifact-details` adds an artifact in state `INACTIVE`, synchronously, without a work request. | Returned immediately; the artifact appeared as `INACTIVE`. The "isAutoDeploy" flag mentioned in the CLI help does not exist in the SDK models. |
| F4 | `hosted-deployment update --active-artifact '{"artifactType":"SIMPLE_DOCKER_ARTIFACT","containerUri":…,"tag":…}'` activates an existing artifact; the previous one becomes `INACTIVE`. | Work request `UPDATE_HOSTED_DEPLOYMENT`, `SUCCEEDED` in about 10 seconds, twice. |
| F5 | `update` accepts only a tag that was added before. | `InvalidParameter`: "Artifact not exists for hostedDeploymentId=… (containerUri=…, tag=0.1.0)". |
| F6 | No interruption was observed while switching, and the endpoint URL does not change. | `/health` returned 200 on every probe during 0.1.1 → 0.1.2 and during the rollback 0.1.2 → 0.1.1; `/version` switched between 404 and 200 when the work request ended. The URL depends on the application only. |
| F7 | Rollback is the activation of an `INACTIVE` artifact. | 0.1.2 → 0.1.1 by `update`, same timing as F4. |
| F8 | The service ignores the deployment `--display-name`. | The script passed `text-stats-0-1-0`; the deployment got a generated name (`generativeaihosteddeployment<timestamp>`). |
| F9 | At most 20 artifacts per application (increase on request). Only inactive artifacts can be deleted. | Documentation. |
| F10 | `hosted-deployment update` requires `--force` when run non-interactively. | Without it, the OCI CLI prompts before replacing `active-artifact`; a non-terminal defaults to `No`, prints `Abort`, and exits 1 without creating a work request. |

The probe interval (2 s) bounds what "no interruption" means; shorter outages
cannot be excluded.

Consequences of F8 for the current script: its check for an existing
deployment by display name never matches, so the **plan announces the creation
of a deployment even when one exists**, and the apply then fails with F1.

## Intended behavior

### Deployment identity

* The deployment of an application is the one non-deleted deployment returned
  by `list-hosted-deployments --application-id`. More than one is an error
  (exit 20) that needs human review.
* The deployment display name is no longer derived from the tag and is not
  used for identification. `agent_manifest.py deployment-name` remains only
  if another command still needs the tag validation it performs; otherwise the
  scripts validate the tag directly.

### One command, four cases

`deploy_hosted_application.sh --manifest PATH --tag X` (plan) and `--apply`
decide the case from OCI state:

| Case | Condition | Plan shows | `--apply` does |
| --- | --- | --- | --- |
| First release | No ACTIVE application with the manifest's name | Create application and deployment with artifact X (unchanged behavior) | Creates both |
| Already released | Deployment ACTIVE and active artifact tag is X | "X is already active", nothing to do | Nothing; exit 0 |
| New version | Deployment ACTIVE, X is not among its artifacts | Add artifact X, then activate it in place of the current tag | `add-artifact`, then `update`, waiting for the work request |
| Return to a previous version | Deployment ACTIVE, X is an `INACTIVE` artifact | Activate X in place of the current tag (rollback) | `update` only |

Rules shared by all cases:

* The plan always shows the current active tag and the target tag, the
  endpoint (unchanged for the last three cases), and the number of artifacts
  against the limit of 20.
* One explicit authorization covers the whole apply of the case shown in the
  plan (for a new version: add and activate). The plan is shown again before
  asking.
* The deploy stops without changes when the deployment is not `ACTIVE` (for
  example `UPDATING` or `FAILED`), when an artifact for X exists with status
  `FAILED` or `UPDATING`, or when adding would exceed the artifact limit. The
  message says what to check; it never proposes deleting.
* The existing application checks stay: `public-noauth` profile and runtime
  environment equal to the manifest.
* After `update`, the script waits for the work request (`SUCCEEDED` or
  `FAILED`, bounded by the existing timeout) and then reads the deployment
  again to confirm that X is the active artifact. A `FAILED` work request or a
  different active tag is reported with its state and exit 1.
* A new version whose tag is not in OCIR fails at `add-artifact` or at
  activation; this behavior must be observed during implementation (see open
  questions) and reported clearly.

Exit codes: unchanged (0, 1, 20, 64, 65); "already released" is 0.

### Verification

`verify_deployment.sh` already checks the active artifact tag and exactly one
`ACTIVE` deployment, which matches F1 and F2. Changes:

* the tag check keeps using the active artifact;
* when the deployment is `UPDATING`, the verifier waits within its timeout
  instead of failing immediately; otherwise its behavior is unchanged.

### Skills and documentation

* `oci-agent-deploy/SKILL.md`: describe the four cases, the authorization
  rule, rollback as "deploy the previous tag", and the manual cleanup of old
  artifacts (inactive only, from the Console or with
  `hosted-deployment delete-hosted-deployment-artifact`), stated as outside
  the skill. Add an explicit rule: never delete or recreate an application or
  deployment to release a new version.
* `references/hosted-application.md`: the facts F1–F9 in short form.
* Guide, README, and skill catalog: "release a new version" and "roll back"
  sections; remove the derived deployment name.
* PowerShell twin with the same cases, report lines, and exit codes.

## Tests (offline)

A fake `oci` executable first on `PATH`, driven by a scenario file, for Bash
(and for PowerShell when `pwsh` is available):

* first release: application absent → create commands issued;
* already released: active tag equals X → no mutating command, exit 0;
* new version: X absent → `add-artifact` then `update`, in this order, and a
  final `get` confirming X;
* rollback: X `INACTIVE` → only `update`;
* stops without mutation: deployment `UPDATING`; artifact X `FAILED`;
  20 artifacts; two non-deleted deployments; runtime environment mismatch;
* plan mode never issues a mutating command in any scenario;
* `update` work request `FAILED` → exit 1 with the state reported.

## Acceptance criteria

1. The offline tests above pass for Bash, and for PowerShell where executable.
2. On the existing `text-stats` application (currently 0.1.1 active, 0.1.2
   inactive), with explicit authorization for each apply:
   * deploy 0.1.1 → "already released", no change;
   * deploy 0.1.2 → rollback path (activation only);
   * deploy 0.1.0 (image in OCIR, not yet an artifact) → new-version path;
   * deploy 0.1.1 → rollback path;
   * `oci-agent-verify-deployment` passes after each change, with the
     expected tag.
3. The endpoint URL is the same before and after every change.
4. The plan for an existing application never announces a deployment
   creation.
5. No command of the skills deletes a resource.
6. Documentation and skills describe the four cases and the manual cleanup.

## Open questions, to settle during implementation

* What does `add-artifact` do with a tag that does not exist in OCIR: does it
  reject it, or accept it and fail at activation? The plan could check the
  tag in OCIR beforehand (`oci artifacts container image list`); decide after
  observing the platform.
* Does the deployment report `UPDATING` during the work request, and does the
  artifact status pass through `UPDATING`? Observe and document.
* Does a failed activation leave the previous artifact active? Observe if it
  can be triggered safely; otherwise document as unverified.

## Recovery and cleanup

* A failed activation: re-run the deploy with the previously active tag
  (rollback path).
* Old artifacts count against the limit of 20; delete inactive ones manually.
* The test variant `0.1.2` of `text-stats` (with a `/version` endpoint) exists
  as an inactive artifact and as an OCIR image; it is used by acceptance
  criterion 2 and can be deleted manually afterwards.

## Verification record

2026-09-30: platform facts F1–F9 above were verified before implementation.
Local checks for steps 1–4 passed: `black --check .` reported 21 files left
unchanged; `pylint scripts tests` rated the code 10.00/10; and `pytest -q`
reported 115 passed, 41 skipped, and 1 warning in 40.88 seconds. PowerShell
was not executed. Live release acceptance remains pending.

2026-09-30: Live acceptance finding 1: release activation did not activate
0.1.2; 0.1.1 remained active and OCI created no work request. The
`hosted-deployment update` command lacked `--force`, so its confirmation prompt
defaulted to `No` without a terminal, printed `Abort`, and exited 1. Offline
tests missed this because the fake OCI CLI did not model that confirmation. The
fix adds `--force` only to artifact activation updates, documents the required
non-interactive behavior, and makes the fake CLI reject unforced updates.
