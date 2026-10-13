# Spec 023: number of replicas at creation

Status: implemented; offline checks and live acceptance passed (2026-10-13).
Date: 2026-10-13.
Implements step A of TODO item 12 (scaling at creation), limited to the
number of replicas.

## Problem

The deploy skill does not set `scalingConfig`, so every Hosted Application
gets the platform default: between 1 and 3 replicas. An agent that keeps state
in memory, for example the jobs of an asynchronous agent (a POST starts a job,
a GET reads its status), works only when every request reaches the same
replica. With more than one replica, a status request can reach another
replica and find no job.

## Scope

* An optional `deploy.scaling` section in `agent.yaml` with the minimum and
  maximum number of replicas.
* The deploy passes it when it **creates** the Hosted Application, and shows
  it in the plan.
* On an existing application, a difference stops the deploy, as for the
  runtime environment and the authentication.
* Bash and PowerShell twins; offline tests; documentation.

## Non-goals

* Changing the scaling of an existing application (step B of TODO item 12).
* Choosing the scaling metric or its threshold.
* Zero replicas (scale to zero) and its effect on readiness.
* Changing the scaling of existing applications or of manifests without the
  section: they keep the platform default.

## Platform facts (verified 2026-10-13)

| # | Fact | Evidence |
| --- | --- | --- |
| F1 | `hosted-application create` accepts `--scaling-config` as JSON with `minReplica`, `maxReplica`, `scalingType`, and one threshold per type (`targetCpuThreshold`, `targetMemoryThreshold`, `targetConcurrencyThreshold`, `targetRpsThreshold`). | OCI CLI 3.94.0 help and `--generate-param-json-input scaling-config`. |
| F2 | `scalingType` is required; allowed values: `CPU`, `MEMORY`, `CONCURRENCY`, `REQUESTS_PER_SECOND`. | OCI Python SDK 2.187.0 model `ScalingConfig`. |
| F3 | Minimum replicas default to 1 and must not exceed the maximum; maximum replicas default to 3, at most 30; setting the maximum equal to the minimum disables autoscaling. | [Creating an application](https://docs.oracle.com/en-us/iaas/Content/generative-ai/create-application.htm). |
| F4 | An application created without `scalingConfig` reports `minReplica` 1, `maxReplica` 3, `scalingType` `REQUESTS_PER_SECOND`, `targetRpsThreshold` 50. | Read-only `hosted-application get` on `text-stats`, 2026-09-30 (TODO item 12). |

## Intended behavior

1. **Manifest.**

   ```yaml
   deploy:
     scaling:
       min_replicas: 1
       max_replicas: 1
   ```

   Both fields are required when the section is present; integers with
   1 ≤ `min_replicas` ≤ `max_replicas` ≤ 30; unknown fields are rejected.
2. **Creation.** With the section, the deploy adds:

   ```json
   {"minReplica": 1, "maxReplica": 1, "scalingType": "REQUESTS_PER_SECOND", "targetRpsThreshold": 50}
   ```

   The metric and threshold are those of the platform default (F4), so that
   only the number of replicas changes. Without the section, no
   `--scaling-config` is sent, as today.
3. **Plan.** A line `Scaling: <min>–<max> replicas` or
   `Scaling: platform default`.
4. **Existing application.** With the section, the deploy compares
   `min-replica` and `max-replica` of the application with the manifest; a
   difference stops the deploy with exit 20 and the message "Existing Hosted
   Application scaling differs from the manifest; changing it is not
   supported." Without the section, nothing is compared.
5. **Manifest helper.** `agent_manifest.py scaling-config` prints the JSON of
   item 2, or nothing when the section is absent; `scaling-matches` reads the
   application JSON on stdin and exits 0 when there is no section or the
   replicas match, 1 otherwise.

## Documentation

* `docs/agent-manifest-reference.md`: the `deploy.scaling` section, with the
  reason to use one replica for agents that keep state in memory.
* `skills/oci-agent-deploy/SKILL.md`: the plan line and the stop on a
  difference.
* `TODO.md` item 12: step A done for the number of replicas.
* `CHANGELOG.md`.

## Tests (offline)

* `tests/test_agent_manifest.py`: valid section; rejected values (0, a
  maximum below the minimum, more than 30, non-integers, unknown fields); the
  helper output with and without the section; `scaling-matches`.
* Deploy release cases (both script families): a first release with
  `scaling` sends the expected `--scaling-config`; without `scaling` none is
  sent; the plan shows the line; an existing application with different
  replicas stops with exit 20 and no mutation.

## Acceptance criteria

1. The offline tests, Black, Pylint, and pytest pass; links resolve.
2. Live: a first release with `min_replicas: 1` and `max_replicas: 1`; a
   read-only `hosted-application get` reports `min-replica` 1 and
   `max-replica` 1.

## Verification record

### 2026-10-13, macOS, local

* `scripts/agent_manifest.py`: `validate_scaling`, `scaling_config`,
  `scaling_matches`, and the `scaling-config` and `scaling-matches` commands;
  the command-line parser moved to `build_parser`.
* Both deploy scripts pass `--scaling-config` at creation only when the
  manifest has the section, print the plan line, and stop with exit 20 when
  an existing application has other replicas.
* Offline: `tests/test_scaling.py` (manifest validation, helper output,
  matching, and three release scenarios for each script family); the fake
  OCI CLI reports `scaling-config` from the scenario. Full suite: 394 passed,
  145 skipped (all `pwsh is unavailable`); Black and Pylint (10.00/10)
  passed.
* Pending: acceptance criterion 2 (live).

### 2026-10-13, live acceptance (criterion 2)

* Agent `async-order-check` (Spec 024 acceptance agent), first release with
  `deploy.scaling: {min_replicas: 1, max_replicas: 1}`, macOS, Bash, through
  the skills. A read-only `hosted-application get` reported `min-replica` 1,
  `max-replica` 1, `scaling-type` `REQUESTS_PER_SECOND`, `target-rps-threshold`
  50.
* F4 confirmed again: `express-order-demo-rp-idcs`, created the same day
  without the section, reports `min-replica` 1 and `max-replica` 3 with the
  same metric and threshold.
