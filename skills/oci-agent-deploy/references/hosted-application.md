# Hosted Application deployment rules

Reviewed 2026-09-22.

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

Do not provide `--environment-variables`, `--storage-configs`, or a custom
networking configuration. A public no-auth endpoint must not be treated as a
production security posture.

Create deployments with the OCI CLI single-Docker-artifact command. Set the
container URI to `${OCIR_REGISTRY}/${OCIR_TENANCY_NAMESPACE}/${OCIR_REPOSITORY}`
and the tag separately. The Hosted Deployment runtime still needs OCI IAM and
dynamic-group permissions to pull the private OCIR image; do not create or
modify those policies in this skill.

Sources:

* [Creating an Application](https://docs.oracle.com/en-us/iaas/Content/generative-ai/create-application.htm)
* [Hosted Applications](https://docs.oracle.com/en-us/iaas/Content/generative-ai/applications.htm)
* [Hosted Deployments](https://docs.oracle.com/en-us/iaas/Content/generative-ai/deployments.htm)
