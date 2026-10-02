# Hosted Application deployment rules

Platform facts below were verified on 2026-09-30 against OCI Generative AI
Hosted Applications.

## Observed artifact and deployment behavior

* F1: An application accepts one non-deleted Hosted Deployment; attempting a
  second deployment is rejected.
* F2: A deployment has an artifact list and one active artifact. Artifacts have
  `ACTIVE` or `INACTIVE` status.
* F3: `add-artifact-create-single-docker-artifact-details` adds an inactive
  artifact synchronously and does not return a work request.
* F4: `hosted-deployment update --active-artifact` activates an existing
  artifact. The preceding active artifact becomes inactive, and OCI returns an
  `UPDATE_HOSTED_DEPLOYMENT` work request.
* F5: Activation accepts only an artifact that already belongs to that
  deployment.
* F6: During the observed artifact switches, the endpoint URL did not change
  and two-second health probes did not observe an interruption.
* F7: Rollback is activation of an inactive artifact; deploy the previous tag.
* F8: OCI ignores the deployment display name supplied at creation. Do not use
  a name derived from an image tag to identify a deployment.
* F9: An application can have at most 20 artifacts. Only inactive artifacts can
  be deleted.

## Reliable wait facts

The following Spec 012 facts were verified on **2026-10-02**. They describe
the CLI and read-only OCI evidence; live acceptance of the new wait and
replacement flows remains pending. See [Spec 012](../../../specs/012-reliable-deploy-wait.md).

* F1: CLI 3.94.0 creation with `--wait-for-state` prints the work request,
  rather than the created resource.
* F2: If the create response lacks `opc-work-request-id`, that CLI wait path
  prints a warning on stdout before resource JSON and returns without waiting.
* F3: The SDK waiter for `SUCCEEDED` does not return on a `FAILED` work
  request; it continues until its timeout.
* F4: A creation failed after about 14 minutes with a capacity error 500 and
  advice to try again later; observed successful creations took 1–2 minutes.
* F5: The observed successful deployment work request held one Hosted
  Deployment OCID.
* F6: Application and deployment states include `CREATING`, `ACTIVE`,
  `UPDATING`, `INACTIVE`, `NEEDS_ATTENTION`, `FAILED`, `DELETING`, and `DELETED`.
* F7: Without the CLI waiter, create returns JSON with `data` and, when
  available, the displayed `opc-work-request-id` header.
* F8: Deployment delete accepts `--hosted-deployment-id` and `--force` and
  runs as a `DELETE_HOSTED_DEPLOYMENT` work request.
* F9: `work-request list` requires `--compartment-id`; use `--resource-id`,
  `--status FAILED`, and `--all`. `work-request-error list` accepts
  `--work-request-id` and `--all`. Both return `data.items`; errors contain
  code and message.
* F10: A failed CLI request prints `ServiceError:` then JSON with integer
  `status`, `code`, and `message`. Read status from that JSON. A 404 can also
  mean insufficient permission because its code is `NotAuthorizedOrNotFound`.

This skill uses public `NO_AUTH_CONFIG` applications with Oracle-managed
networking:

## JWT inbound-authentication facts

Facts A1–A9 and assumptions U1–U6 below are **to confirm during the live
acceptance**.

| # | Fact |
| --- | --- |
| A1 | Hosted Applications support identity-domain bearer tokens and OCI IAM request signing. |
| A2 | `IDCS_AUTH_CONFIG` carries one domain URL, scope, and audience. |
| A3 | The confidential application supplies matching primary audience and scope. |
| A4 | Client credentials obtain a token from `/oauth2/v1/token`. |
| A5 | OCI supports inbound-auth updates, but this workflow does not change authentication. |
| A6 | CLI may report no-auth as `UNKNOWN_ENUM_VALUE`; null or absent IDCS config identifies it. |
| A7 | Creation can accept IDCS settings that fail only during endpoint verification. |
| A8 | Audience is the configured primary audience and need not be a URL. |
| A9 | Public no-auth health endpoints can be called without a token. |

| # | Assumption |
| --- | --- |
| U1 | Protected applications use the current inference endpoint host. |
| U2 | Authenticated HTTP calls use `Authorization: Bearer <token>`. |
| U3 | Health and readiness are protected like business paths. |
| U4 | Requests without a token return 401 or 403. |
| U5 | Scope defaults to audience followed by scope unless overridden by the operator. |
| U6 | Client credentials use HTTP Basic authentication. |

Client secrets and access tokens must never be typed into chat, printed, or
stored. The operator exports the client ID and secret only in the shell that
runs the verifier.

```json
{"inboundAuthConfigType":"NO_AUTH_CONFIG"}
```

```json
{
  "inboundNetworkingConfig":{"endpointMode":"PUBLIC"},
  "outboundNetworkingConfig":{"networkMode":"MANAGED"}
}
```

Use `--environment-variables` only from validated manifest `runtime.env` data.
OCI expects `EnvironmentVariable` objects with `name`, `type`, and `value`.
Supported types are `PLAINTEXT` and `VAULT`. Do not provide `--storage-configs`
or custom networking. A public no-auth endpoint is not a production security
posture.

The Hosted Deployment runtime needs OCI IAM and dynamic-group permissions to
pull a private OCIR image. Vault-backed runtime variables additionally need
permission to read their referenced secrets. This skill does not create,
modify, or validate these policies.

Sources:

* [Artifacts](https://docs.oracle.com/en-us/iaas/Content/generative-ai/artifacts.htm)
* [Hosted Applications](https://docs.oracle.com/en-us/iaas/Content/generative-ai/applications.htm)
* [Hosted Deployments](https://docs.oracle.com/en-us/iaas/Content/generative-ai/deployments.htm)
