---
name: oci-agent-verify-deployment
description: Verify a published OCI Generative AI Hosted Application release with read-only OCI state checks and public health/readiness probes. Use after deployment; it never changes resources or invokes business paths.
---

# OCI Agent Verify Deployment

Verify that a specific Hosted Application release is active and reachable.
This skill performs OCI reads and unauthenticated GET requests only; it never
creates, updates, deletes, restarts, or invokes agent business paths.

## Prerequisites

Read [endpoint rules and observed behavior](references/endpoint-behavior.md).
Run from this checkout after `oci-agent-build`, `oci-agent-push`, and
`oci-agent-deploy`. OCI CLI must be available in the project Conda environment,
and `curl` must be able to reach the public endpoint.

The root `.env` provides only tenancy-wide values including `OCI_REGION`. Do not
add an auth token, password, private key, endpoint override, or other secret to
it. The operator supplies the Hosted Application OCID, agent manifest, and
expected semantic image tag explicitly.

## Workflow

1. Confirm the image tag was locally verified and pushed, then obtain explicit
   authorization before making the public probe requests.
2. Run the verifier from the project Conda environment. It first checks that the
   application is `ACTIVE`, that exactly one associated deployment is `ACTIVE`,
   and that its active artifact tag is the requested release.

   ```bash
   conda run -n codex-4-oci-enterprise-ai-deployment \
     bash -c 'set -a; . ./.env; set +a; \
       scripts/verify_deployment.sh \
       --application-id <application-ocid> \
       --manifest demos/hello_world/agent.yaml --tag 0.2.0'
   ```

3. Only after the resource checks pass, the script polls the verified URL form
   ending in `/actions/invoke/health` and `/actions/invoke/ready`. A 200 health
   response with a non-200 readiness response means the container is running but
   not ready; polling continues within the configured timeout.
4. Report the application and deployment OCIDs, release tag, endpoint host, both
   HTTP statuses, readiness seconds, and result. A pass is evidence for this
   release's two probes only, not a production-security or general functional
   certification.

Use `--timeout-seconds` (default 300) and `--poll-seconds` (default 5) to bound
the probe. Do not add Authorization headers or try alternate endpoint hosts or
path encodings when a probe fails; report the observed result.

Functional checks defined in the manifest are not part of this default read-only
workflow. Only after separately obtaining authorization to invoke business paths
may you append `--functional`; report each request and response result.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Application, deployment, tag, health, and readiness checks passed. |
| 1 | Required OCI CLI or curl executable is unavailable. |
| 20 | Hosted Application is not `ACTIVE`. |
| 21 | The application does not have exactly one `ACTIVE` Hosted Deployment. |
| 22 | The active artifact tag differs from the expected tag. |
| 23 | The bounded probe ended without both endpoints returning HTTP 200. |
| 64 | Invalid arguments or `OCI_REGION`. |

## Limitations

This initial skill supports the verified OC1 public endpoint form only. It does
not support private endpoints, OCI IAM-authenticated applications, bearer-token
authentication, redirects, custom business probes, or endpoint invocation with
request bodies.
