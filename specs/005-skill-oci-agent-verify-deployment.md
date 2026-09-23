# Spec 005: Codex skill `oci-agent-verify-deployment`

Status: implemented; static checks, mocked scenarios, and live Frankfurt
verification passed for the `hello-world:0.2.0` release.
Date: 2026-09-23.

## Problem

An active OCI Generative AI Hosted Deployment does not by itself prove that its
container is reachable or ready to serve traffic. Operators need a read-only,
release-specific verification step that checks the application and deployment
states and then probes the container's `/health` and `/ready` paths through the
Hosted Application data-plane endpoint.

The OCI SDK models do not provide a documented endpoint URL field for this
workflow. Oracle documentation shows an application invocation URL composed from
a regional host, API version, application OCID, `actions/invoke`, and the
container's custom path. The operator has verified that the existing Frankfurt
application uses the `inference.generativeai` host; the custom-path mapping still
requires a live observation before this repository treats it as verified.

## Scope

1. Add a discoverable `oci-agent-verify-deployment` skill, its UI metadata, and
   a guarded `scripts/verify_deployment.sh` helper.
2. Require an explicit application OCID and an expected semantic image tag.
   Read `OCI_REGION` from the non-secret project configuration.
3. Use OCI CLI read operations to require an `ACTIVE` Hosted Application and
   exactly one `ACTIVE` Hosted Deployment for that application whose active
   artifact tag equals the expected tag.
4. Construct the endpoint from the validated region and application OCID, then
   poll `GET /health` and `GET /ready` through `actions/invoke` with bounded
   timeout and interval settings.
5. Report application and deployment OCIDs, expected tag, endpoint host, HTTP
   statuses, readiness time, and pass/fail without printing tokens or unrelated
   local configuration.
6. Perform the initial Frankfurt endpoint discovery with the known active
   application by issuing only the user-authorized unauthenticated `GET`
   requests. Record the observed host, paths, status codes, and date in a skill
   reference. Do not infer an unobserved mapping.

## Non-goals

* Create, update, delete, restart, or otherwise mutate OCI resources.
* Invoke agent business paths, submit request bodies, or make authenticated
  endpoint calls.
* Generate, store, accept, or print bearer tokens, OCI credentials, or secrets.
* Treat a successful probe as evidence of production security, scaling, or
  application-level correctness beyond the two probe endpoints.
* Support private endpoints or OCI IAM-authenticated Hosted Applications in this
  initial version.

## Assumptions and prerequisites

* The target is an OC1 public Hosted Application configured with
  `NO_AUTH_CONFIG`; the operator explicitly authorizes the two probe GETs.
* OCI CLI is available in the project Conda environment and can read Hosted
  Applications and Hosted Deployments in the target compartment.
* `curl` is available and the caller can reach the public data-plane endpoint.
* The container implements the OCI-required `/health` and `/ready` paths.
* The app is associated with exactly one active deployment for the release being
  verified. Ambiguity is a safe failure, not a selection heuristic.

## Endpoint discovery and contract

The verified endpoint base is:

```text
https://inference.generativeai.<region>.oci.oraclecloud.com/20251112/hostedApplications/<application-ocid>/actions/invoke/<custom-path>
```

The first authorized probes must test the paths `health` and `ready`, without a
leading slash after `invoke`. The observed result determines whether this exact
path construction becomes the default implementation contract. If the requests
fail, record the result and stop; do not automatically try alternate path
encodings.

## Intended behavior

`scripts/verify_deployment.sh --application-id OCID --expected-tag X.Y.Z` uses
only read operations and exits nonzero before any endpoint request when an input
is invalid, an OCI state is unsuitable, or the active deployment/tag check is
ambiguous or fails. Its exact exit-code contract will be defined with the
implementation.

Once resource state is verified, it probes the derived `/health` and `/ready`
URLs until both return HTTP 200 or the configured timeout expires. A 200 health
response with a non-200 readiness response is reported as running but not ready
and continues polling. It does not follow redirects, send credentials, or call
paths other than the two probes.

## Acceptance criteria

1. The skill and metadata are discoverable through `.agents/skills` and explain
   the read-only boundary, required inputs, endpoint-discovery limitation, and
   separate endpoint-probe authorization.
2. The helper validates inputs and checks application state, deployment state,
   and active artifact tag before issuing curl.
3. The helper reports a distinct not-ready condition when health is 200 and
   readiness is non-200, with bounded polling and actionable failure output.
4. Static Bash checks and mocked OCI/curl scenarios cover active success,
   deleted or inactive application, absent/ambiguous deployment, tag mismatch,
   readiness retry, timeout, and curl failure. No mocks make live OCI calls.
5. The initial live Frankfurt observation is recorded separately from mocked
   tests, including whether the proposed host/path mapping worked. No endpoint
   is invoked beyond `/health` and `/ready`.
6. `git diff --check`, skill validation, linked-file checks, and documentation
   consistency checks pass. No credentials or generated artifacts are tracked.

## Sources

Verified 2026-09-23:

* [Oracle: Invoking Applications with HTTP](https://docs.oracle.com/en-us/iaas/Content/generative-ai/invoke-app-http.htm)
* [Oracle: Using Applications](https://docs.oracle.com/en-us/iaas/Content/generative-ai/use-applications.htm)
* [Oracle: Preparing Container Images](https://docs.oracle.com/en-us/iaas/Content/generative-ai/prepare-artifacts.htm)
* [Oracle CLI: List Hosted Applications](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/generative-ai/hosted-application-collection/list-hosted-applications.html)
* [Oracle CLI: List Hosted Deployments](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/generative-ai/hosted-deployment-collection/list-hosted-deployments.html)

## Verification record

2026-09-23: the operator verified the Frankfurt endpoint host as
`inference.generativeai.eu-frankfurt-1.oci.oraclecloud.com`. User-authorized,
unauthenticated GET requests to the derived `health` and `ready` paths both
returned HTTP 200. This is recorded in the skill reference as an observation,
not a general claim for private or authenticated applications.

2026-09-23: OCI Python SDK 2.187.0 model inspection confirmed that
`HostedApplication` and `HostedDeployment` expose lifecycle-state and artifact
attributes but no endpoint URL field. The live deployment list reported one
`ACTIVE` deployment with `active-artifact.tag` equal to `0.2.0`.

2026-09-23: `scripts/verify_deployment.sh` passed Bash syntax validation and
the skill validator. Mocked OCI/curl scenarios verified pass, application-not-
active (exit 20), absent or ambiguous active deployment (exit 21), tag mismatch
(exit 22), health-200/ready-503 timeout with `NOT_READY`, and curl failure
timeout with `UNHEALTHY` (exit 23). No mock contacted OCI or an endpoint.

2026-09-23: the complete verifier ran against the active Frankfurt
`hello-world:0.2.0` release with a 60-second timeout and 5-second poll interval.
It verified an `ACTIVE` Hosted Application, exactly one `ACTIVE` Hosted
Deployment, active tag `0.2.0`, and HTTP 200 from both probes; it reported
`result=PASS` with zero seconds to readiness. No business path was invoked and
no OCI resource was changed.
