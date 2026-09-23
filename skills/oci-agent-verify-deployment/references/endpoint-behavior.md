# Hosted Application endpoint rules and observed behavior

Reviewed 2026-09-23.

For the default Hosted Application type, Oracle documents this endpoint form:

```text
https://inference.generativeai.<region>.oci.oraclecloud.com/20251112/hostedApplications/<application-ocid>/actions/invoke/<custom-path>
```

The endpoint is constructed from the OCI region and Hosted Application OCID;
the `HostedApplication` and `HostedDeployment` SDK model attributes inspected
with OCI Python SDK 2.187.0 do not include an endpoint URL field. The deployed
artifact tag is available through `HostedDeployment.active_artifact.tag`.

## Frankfurt observation

On 2026-09-23, the operator-provided active Frankfurt application endpoint was
probed without authentication or a request body. Both requests returned HTTP
200:

```text
GET /20251112/hostedApplications/<application-ocid>/actions/invoke/health -> 200
GET /20251112/hostedApplications/<application-ocid>/actions/invoke/ready  -> 200
```

This verifies that `/health` and `/ready` map to `health` and `ready` without a
leading slash after `actions/invoke/` for that public `NO_AUTH_CONFIG`
application. It does not establish the same behavior for private or
authenticated applications.

The complete verifier subsequently confirmed one `ACTIVE` deployment with
active artifact tag `0.2.0` for that application. It reported HTTP 200 for both
probes and zero seconds to readiness. Resource OCIDs are reported only at run
time and are not recorded here.

Sources:

* [Oracle: Using Applications](https://docs.oracle.com/en-us/iaas/Content/generative-ai/use-applications.htm)
* [Oracle: Invoking Applications with HTTP](https://docs.oracle.com/en-us/iaas/Content/generative-ai/invoke-app-http.htm)
* [Oracle: Preparing Container Images](https://docs.oracle.com/en-us/iaas/Content/generative-ai/prepare-artifacts.htm)
