# Linux build machine over SSH

## Purpose

This note outlines an alternative to a workstation-hosted container engine: a
dedicated Ubuntu build machine reached through SSH. It is suitable for an
enterprise environment where Docker Desktop is not permitted or where image
building should be separated from developer workstations.

The current OCI-agent scripts are Bash/Linux scripts, so they can run on the
build machine without a PowerShell port or Rancher Desktop dependency.

## High-level architecture

```text
Developer workstation -- SSH --> Ubuntu build machine -- HTTPS --> OCIR
                                                    -- HTTPS --> OCI APIs
                                                    -- HTTPS --> public application endpoint
```

The workstation selects an explicit manifest and release tag. SSH executes the
requested lifecycle command in a known checkout on the build machine. The
machine builds a `linux/amd64` image, performs local container verification,
and can push the verified image to OCIR. OCI deployment and post-deployment
verification may run there as well, or may remain on an operator workstation
with separate OCI credentials.

## Responsibilities by lifecycle stage

| Stage | Minimum build-machine requirements | Recommended execution location |
| --- | --- | --- |
| Build | Docker Engine with Buildx, Bash, Conda project environment | Ubuntu build machine |
| Local image verification | Docker Engine, curl, free loopback port | Ubuntu build machine |
| OCIR push | Docker Engine, OCI CLI, authenticated OCI identity | Ubuntu build machine |
| Hosted Application deploy | OCI CLI and deployment IAM permissions | Build machine or operator workstation |
| Deployment verification | OCI CLI, curl, egress to public OCI endpoint | Build machine or operator workstation |

Image build does not need OCI credentials. OCIR push needs OCI CLI
authentication because the project resolves the OCIR registry endpoint from
the configured OCI region. Deploy requires permissions to inspect and create
the configured Hosted Application and Hosted Deployment resources.

## Prerequisites

The build machine should have:

* A supported Ubuntu release, current security updates, and outbound HTTPS
  access to required package registries, OCIR, OCI APIs, and the target public
  application endpoint.
* Docker Engine and Buildx capable of building and loading `linux/amd64`
  images.
* Git, Bash, curl, and Conda with the project environment
  `codex-4-oci-enterprise-ai-deployment`.
* OCI CLI only if the machine performs push, deploy, or remote verification.
* An SSH service limited to approved users, key-based authentication, and an
  auditable access path.

Keep the repository checkout, `.env`, OCI configuration, private keys, and
registry auth tokens on the build machine under the account that runs the
workflow. They must remain outside version control and must not be copied by
ad-hoc source transfers.

## Source and release selection

Use a Git clone on the build machine rather than `scp` or archive copies. A
commit SHA, branch, or signed release tag then identifies the exact source used
for an image. Pull or checkout the intended revision before invoking a skill.

The invocation must still pass both inputs explicitly:

* the manifest path, relative to the repository checkout; and
* the semantic release tag.

For example, a workstation can request an image build through SSH:

```bash
ssh build-host.example.internal \
  'cd ~/projects/codex-4-oci-enterprise-ai-deployment && \
   git pull --ff-only && \
   conda run -n codex-4-oci-enterprise-ai-deployment \
     bash scripts/build_image.sh \
     --manifest demos/hello_world/agent.yaml --tag 0.4.0'
```

Replace the host and checkout only with organization-approved values. Do not
place OCI secrets, registry passwords, or Vault values in the SSH command.

## Credential and authorization boundaries

Separate the technical ability to connect from authorization to change OCI
resources:

* Build and local verification require no OCI identity.
* Push credentials should be scoped to the intended OCIR repository.
* Deployment credentials should have only the Hosted Application permissions
  required by the approved compartment.
* Remote verification uses OCI reads and public probes; it does not require
  deployment mutation permissions.

Use a distinct operating-system account or a distinct CI identity when the
organization requires separation between image production and OCI deployment.
Keep SSH keys and OCI API keys separate, rotate them under the organization
policy, and enable audit logging for both systems.

## Operational considerations

The local verifier publishes a temporary container port on the build machine's
loopback interface. It does not need inbound access from the developer
workstation. Build output, image tags, repository targets, deployment OCIDs,
and sanitized verification results can be returned through the SSH session or
stored in approved build logs.

Do not run unattended `git pull` against an unspecified branch in a production
automation path. Pin the source revision and record it together with the
manifest path, image tag, OCIR digest, application OCID, deployment OCID, and
verification outcome.

Define cleanup deliberately: remove only explicitly identified temporary
containers and local images under the build-machine retention policy. Never use
broad image pruning as an implicit cleanup step.

## Non-goals

This note does not introduce an SSH orchestration script, configure an Ubuntu
VM, provision IAM policies, or change the existing skills. Such automation
should be specified separately because it introduces host selection, source
revision, credential, logging, and approval requirements.
