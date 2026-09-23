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

The root `.env` contains only tenancy-wide values. The agent manifest supplies
the repository, application name, public no-auth profile, and functional checks;
the release tag is always an explicit command-line value. Do not add a token,
password, private key, or container environment value to either file.

When `runtime.env` is present, inspect its source report in the plan. Literal
and `from_env` values are plaintext; Vault references are never printed. A
missing `from_env` input stops the plan. Existing applications must already have
the same runtime environment because this skill does not update applications.

## Workflow

1. Require an agent manifest named in the current request and a semantic tag. If
   the manifest is absent, ask “Which agent manifest should I use?” before any
   Docker or OCI action. Never select a demo, scan for a manifest, or infer it
   from conversation history; an explicit “use the same agent/manifest as the
   immediately preceding step” is sufficient. Confirm its local image has passed
   local verification and was pushed to the exact OCIR target.
2. Run the non-mutating plan:

   ```bash
   scripts/deploy_hosted_application.sh --manifest demos/hello_world/agent.yaml --tag 0.1.0
   ```

   Stop if the configured OCI CLI profile cannot resolve the region, the image
   is not `linux/amd64`, the named compartment is ambiguous, required OCI
   permissions are unavailable, or an existing same-named application is not
   `ACTIVE`. An ACTIVE manifest-compatible application is reused; a `DELETED`
   application does not block a new deployment.
3. Show the resolved image URI, compartment, Hosted Application name, Hosted
   Deployment name, runtime-variable source report, and planned resource creation. State that the endpoint will
   be public and have `NO_AUTH_CONFIG`.
4. Obtain explicit authorization immediately before creation. Then run:

   ```bash
   scripts/deploy_hosted_application.sh --apply --manifest demos/hello_world/agent.yaml --tag 0.1.0
   ```

5. Report resulting OCIDs and CLI work-request outcomes. Do not invoke the
   endpoint without separate user direction: it is public and unauthenticated.

## Limitations

The script deliberately omits `--environment-variables`, `--storage-configs`,
and custom networking. It never creates IAM policies or dynamic groups needed
for the Hosted Deployment runtime to pull a private image. It does not update or
replace an existing deployment and does not delete resources.
