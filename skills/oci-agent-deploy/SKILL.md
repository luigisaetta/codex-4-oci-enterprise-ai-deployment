---
name: oci-agent-deploy
description: Plan or, with explicit authorization, deploy a verified OCIR agent image to OCI Generative AI Hosted Applications using managed networking and no inbound auth config.
---

# OCI Agent Deploy

Deploy a verified, published `linux/amd64` agent image to OCI Generative AI
Hosted Applications. This skill uses `NO_AUTH_CONFIG`, a public endpoint, and
Oracle-managed networking. It does not build, push, configure container
environment variables, alter IAM, or delete resources.

## Prerequisites

Read [Hosted Application deployment rules](references/hosted-application.md).
Run from this checkout after `oci-agent-build` and `oci-agent-push` have
completed. OCI CLI must be configured and authorized for the target compartment.

The root `.env` contains the non-secret values from the earlier skills plus
`OCI_HOSTED_APPLICATION_NAME` and `OCI_HOSTED_DEPLOYMENT_NAME`. Do not add a
token, password, private key, or container environment value to it.

## Workflow

1. Require an explicit local image name and semantic tag. Confirm it has passed
   local verification and was pushed to the exact OCIR target.
2. Run the non-mutating plan:

   ```bash
   scripts/deploy_hosted_application.sh --image hello-world:0.1.0
   ```

   Stop if the configured OCI CLI profile cannot resolve the region, the image
   is not `linux/amd64`, the named compartment is ambiguous, required OCI
   permissions are unavailable, or a same-named deployment already exists.
3. Show the resolved image URI, compartment, Hosted Application name, Hosted
   Deployment name, and planned resource creation. State that the endpoint will
   be public and have `NO_AUTH_CONFIG`.
4. Obtain explicit authorization immediately before creation. Then run:

   ```bash
   scripts/deploy_hosted_application.sh --apply --image hello-world:0.1.0
   ```

5. Report resulting OCIDs and CLI work-request outcomes. Do not invoke the
   endpoint without separate user direction: it is public and unauthenticated.

## Limitations

The script deliberately omits `--environment-variables`, `--storage-configs`,
and custom networking. It never creates IAM policies or dynamic groups needed
for the Hosted Deployment runtime to pull a private image. It does not update or
replace an existing deployment and does not delete resources.
