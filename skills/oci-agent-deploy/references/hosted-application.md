# Hosted Application deployment rules

Reviewed 2026-09-23.

This skill creates a public OCI Generative AI Hosted Application with Oracle-
managed outbound networking and no inbound endpoint authentication:

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
OCI expects a list of `EnvironmentVariable` objects with `name`, `type`, and
`value`; the supported types are `PLAINTEXT` and `VAULT`. Do not provide
`--storage-configs` or a custom networking configuration. A public no-auth
endpoint must not be treated as a production security posture.

Create deployments with the OCI CLI single-Docker-artifact command. Set the
container URI to `${OCIR_REGISTRY}/${OCIR_TENANCY_NAMESPACE}/<manifest publish.repository>`
and the tag separately. The Hosted Deployment runtime still needs OCI IAM and
dynamic-group permissions to pull the private OCIR image; do not create or
modify those policies in this skill.

Vault-backed runtime variables require a separate IAM policy allowing the
Hosted Application runtime to read the referenced secret. The deployer neither
creates nor validates that policy. Runtime variables are application settings:
changing them requires `hosted-application update`, which is intentionally not
implemented by the create-only deployment workflow.

Sources:

* [Creating an Application](https://docs.oracle.com/en-us/iaas/Content/generative-ai/create-application.htm)
* [Hosted Applications](https://docs.oracle.com/en-us/iaas/Content/generative-ai/applications.htm)
* [Hosted Deployments](https://docs.oracle.com/en-us/iaas/Content/generative-ai/deployments.htm)
* [OCI CLI: list Hosted Applications](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/generative-ai/hosted-application-collection/list-hosted-applications.html)
* [OCI SDK: EnvironmentVariable](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/generative_ai/models/oci.generative_ai.models.EnvironmentVariable.html)
