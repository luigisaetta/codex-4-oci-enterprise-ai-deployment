# Spec 013: Independent verifier HTTP request timeout

Status: implemented; offline checks and live Frankfurt verification passed.
Date: 2026-10-02.

## Problem

The verifier previously used the polling interval as the HTTP timeout for
`/health`, `/ready`, and manifest functional checks. The five-second default
caused a deployed agent's functional POST to time out while waiting for its
response, although the same check passed with a 60-second limit.

## Scope and intended behavior

* Keep the overall verification budget at 300 seconds by default and the
  polling interval at five seconds by default.
* Add `--request-timeout-seconds` / `-RequestTimeoutSeconds` with a default of
  60 seconds. Apply it to every health, readiness, unauthenticated-health, and
  authorized functional HTTP request.
* Use the polling interval only between deployment-state and endpoint probes.
* Validate the new option as a positive integer. Preserve existing exit codes,
  endpoint construction, authentication, and authorization behavior.
* Keep Bash and PowerShell command behavior and documentation aligned.

## Non-goals and prerequisites

No OCI resource changes, endpoint changes, retry policy changes, or new
authentication methods. The operator still supplies an application OCID,
manifest, and release tag and separately authorizes functional invocation.

## Acceptance criteria and verification

1. Default health/readiness and functional requests receive a 60-second HTTP
   timeout even when the polling interval is five seconds or overridden.
2. An explicit request timeout overrides the default for all HTTP paths.
3. Bash and PowerShell reject nonpositive request timeouts before OCI or HTTP.
4. Offline mocked tests cover the default and override; Bash syntax, PowerShell
   static checks, skill references, and `git diff --check` pass.
5. Record local results here. A live OCI check is optional and requires
   separate endpoint-probe authorization.

## Evidence

On 2026-10-02 the operator-authorized `order_processing:0.1.1` verifier's
functional POST twice raised `TimeoutError: The read operation timed out`
with the five-second default. It then passed with `--poll-seconds 60`; health
and readiness both returned HTTP 200. Inspection showed the verifier passes
`poll_seconds` to curl and the functional-check helper as their request timeout.
This is release-specific evidence, not a general service latency guarantee.

## Verification record

2026-10-02: Bash syntax and `git diff --check` passed. Targeted offline tests
passed (47 passed, 7 skipped); the skipped cases require PowerShell, which
was unavailable on this host. Black and Pylint passed for changed Python tests.
The Bash verifier's mocked authenticated probes and functional helper received
the 60-second default and an explicit nine-second override independently of
the one-second polling interval. PowerShell option parity and static timeout
checks passed.

2026-10-02: The operator-authorized live Frankfurt verification of
`order_processing:0.1.1` ran with `--functional` and no timeout override.
Health and readiness returned HTTP 200, the manifest POST returned HTTP 200
with its expected JSON subset, and the verifier reported `result=PASS`. No
OCI resource was changed.
