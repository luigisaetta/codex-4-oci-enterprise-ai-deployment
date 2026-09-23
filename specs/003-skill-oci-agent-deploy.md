# Spec 003: Codex skill `oci-agent-deploy`

Status: implemented; static and remote creation acceptance criteria passed;
endpoint invocation intentionally not performed.
Date: 2026-09-23.

## Problem

After an agent image has been verified locally and published to OCIR, an operator
needs a repeatable OCI CLI workflow to create a Generative AI Hosted Application
and Hosted Deployment without custom networking, container environment variables,
or inbound endpoint authentication.

## Scope

1. Add an `oci-agent-deploy` skill and guarded Bash deployer.
2. Use Oracle-managed networking with a public endpoint and
   `NO_AUTH_CONFIG` inbound authentication.
3. Omit `--environment-variables`, managed storage, and custom networking.
4. Resolve the named compartment and use a verified, already-published OCIR image.
5. Provide non-mutating planning by default and require `--apply` for resource
   creation.
6. Record local static checks and remote deployment evidence separately.

## Non-goals

* Create or change IAM policies, dynamic groups, identity domains, VCNs, private
  endpoints, managed storage, or container environment variables.
* Build, tag, log in to a registry, or push images.
* Add application-level authentication, invoke endpoint paths, or claim that an
  unauthenticated deployment is safe for production.
* Delete hosted applications or deployments.

## Assumptions and prerequisites

* The target is OC1. The shared resolver derives the OCIR region-key endpoint
  from the exact `OCI_REGION` match returned by `oci iam region list`.
* OCI CLI is installed, configured, and authorized to list and create Generative
  AI Hosted Applications and Hosted Deployments in the target compartment.
* The platform runtime has the prerequisite dynamic-group and IAM permissions to
  pull the private OCIR image. This workflow only reports that prerequisite; it
  does not manage it.
* The image has already passed Spec 001 and has been published through Spec 002.
* The operator accepts that `NO_AUTH_CONFIG` exposes the public endpoint without
  inbound identity-domain authentication.

## Configuration contract

The root `.env.example` and ignored root `.env` add only non-secret values:

```dotenv
OCI_HOSTED_APPLICATION_NAME=hello-world
OCI_HOSTED_DEPLOYMENT_NAME=hello-world-0-1-0
```

They are used with `OCI_REGION`, `OCI_COMPARTMENT_NAME`,
`OCIR_TENANCY_NAMESPACE`, and `OCIR_REPOSITORY` from Spec 002. The local image
is supplied explicitly as `--image NAME:MAJOR.MINOR.PATCH`; no floating tag is
accepted.

## Intended behavior

`scripts/deploy_hosted_application.sh --image NAME:TAG` is a read-only plan. It
validates the local image platform, resolves the OCIR region-key endpoint and
the single active compartment, then reports the exact Hosted Application and
Hosted Deployment targets. It counts only non-`DELETED` Hosted Applications
with the configured name and stops if one exists, rather than silently replacing
it. A deleted application does not block a new deployment.

With `--apply`, after explicit operator authorization, the script creates a
missing Hosted Application with:

```json
{"inboundAuthConfigType":"NO_AUTH_CONFIG"}
```

and:

```json
{
  "inboundNetworkingConfig":{"endpointMode":"PUBLIC"},
  "outboundNetworkingConfig":{"networkMode":"MANAGED"}
}
```

It deliberately omits `--environment-variables`. It then creates a Hosted
Deployment using `create-hosted-deployment-single-docker-artifact`, with the
resolved OCIR repository URI and supplied semantic tag, and waits for the CLI
work request to succeed. It records OCIDs and states but never prints
credentials.

## Acceptance criteria

1. The skill has valid frontmatter and requires explicit authorization before
   `--apply`.
2. The deployer supports `--plan` and `--apply`, checks required configuration,
   requires a local `linux/amd64` semantic-tagged image, and rejects other input.
3. The planned and applied Hosted Application settings use `NO_AUTH_CONFIG`, a
   public endpoint, and Oracle-managed outbound networking, with no container
   environment variables.
4. A matching non-`DELETED` Hosted Application causes a safe stop; it is never
   reused, updated, or replaced automatically. A matching `DELETED` application
   does not block a new deployment.
5. README, skill catalog, `.env.example`, and changelog document the workflow.
6. Bash syntax and local safe-path checks pass. Remote creation and deployment
   readiness require explicit authorization; endpoint invocation remains a
   separate, explicitly authorized action.

## Sources

Verified 2026-09-23:

* [Oracle: Creating an Application](https://docs.oracle.com/en-us/iaas/Content/generative-ai/create-application.htm)
* [Oracle: Hosted Applications](https://docs.oracle.com/en-us/iaas/Content/generative-ai/applications.htm)
* [Oracle: Hosted Deployments](https://docs.oracle.com/en-us/iaas/Content/generative-ai/deployments.htm)
* [Oracle CLI: create a single Docker artifact deployment](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/generative-ai/hosted-deployment/create-hosted-deployment-single-docker-artifact.html)
* [Oracle CLI: list Hosted Applications](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/generative-ai/hosted-application-collection/list-hosted-applications.html)
* [Oracle CLI: Listing regions and filtering with queries](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliusing.htm)

The local `oci-rag-agent-blueprint` was inspected on 2026-09-22. Its deployer
uses `NO_AUTH_CONFIG` for a no-auth Hosted Application, public endpoint mode,
and managed outbound networking. Its local tests assert those generated JSON
artifacts; it is supporting implementation evidence, not a substitute for OCI
documentation or this repository's remote verification.

## Verification record

2026-09-22: static acceptance criteria 1–6 passed. The deployer passed Bash
syntax validation; `--help` passed; a floating `latest` tag and incomplete
configuration both exited with code 64 before Docker or OCI operations. The
skill validator, YAML parse, and `git diff --check` passed.

2026-09-22: with explicit operator authorization, the workflow created Hosted
Application `hello-world-app` and its Hosted Deployment in the configured
Frankfurt compartment. The application and deployment reached `ACTIVE`; the
deployment's active artifact was
`fra.ocir.io/frpj5kvxryk1/agents/hello-world:0.1.0`. OCI returned no endpoint
value at the recorded read, and no endpoint was invoked. No IAM policy, dynamic
group, custom network, managed storage, or container environment variable was
created or changed by this workflow.

2026-09-23: the shared OCIR registry resolver was changed to derive the OC1
region-key hostname from `oci iam region list --all`. Mocked-CLI checks verified
the resolver for Frankfurt and an additional region, and covered an absent
region and CLI failure. No authenticated OCI CLI call or deployment operation
was performed; dynamic resolution has no additional remote verification.

2026-09-23: a read-only plan was run for the verified and published
`hello-world:0.2.0` image. It resolved the `fra.ocir.io` artifact target and a
single active configured compartment, then found one Hosted Application with
the configured name `hello-world-app`. The deployer stopped before `--apply`.
Subsequent inspection established that the application was `DELETED`, exposing
that the deployer counted all name matches without checking lifecycle state.
No Hosted Application or Hosted Deployment was created, updated, reused, or
deleted, and no endpoint was invoked.

2026-09-23: the deployer was corrected to count only matching Hosted
Applications whose lifecycle state is not `DELETED`. Mocked-CLI tests cover a
deleted match allowing the read-only plan to complete and a non-deleted match
causing the safe exit. A subsequent authenticated read-only plan for
`hello-world:0.2.0` completed successfully against the configured OC1
compartment, confirming that the existing deleted application no longer blocks
the workflow. No deployment operation was performed.
