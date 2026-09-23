# Spec 002: Codex skill `oci-agent-push`

Status: implemented; static acceptance criteria and remote repository-creation
and push acceptance passed for the configured Frankfurt target. Dynamic
region-key resolution has local mocked-CLI verification only; optional local
Docker credential cleanup remains an operator decision.
Date: 2026-09-23.

> Superseded configuration note (2026-09-23): Spec 006 moves the OCIR repository
> from `.env` into the per-agent manifest and adds `push_ocir_image.sh`. Existing
> historical evidence below used the former environment variable contract.

## Problem

After a local `linux/amd64` agent image has passed the workflow in Spec 001, an
operator needs a safe, repeatable way to create an OCI Container Registry (OCIR)
repository when it is absent and push the image. The workflow needs
region-derived registry addressing and explicit authentication guidance without
placing an OCI auth token in the repository, process arguments, logs, or
versioned configuration.

## Scope

1. Provide root `.env.example` and ignored root `.env` files containing only
   non-secret OCIR configuration placeholders.
2. Document configuration, compartment-name resolution, interactive Docker
   login, repository creation, target-tag construction, IAM prerequisites, push
   authorization, verification, and cleanup in the project README.
3. Add a discoverable `oci-agent-push` skill under `skills/` with the same
   operational boundaries.
4. Provide a Bash script that resolves the named compartment, detects the
   requested repository, and creates it only when invoked with `--create`.
5. Provide a Bash script that resolves an OC1 OCI region identifier to the OCIR
   region-key hostname used consistently for Docker login and push, without a
   maintained region mapping.
6. Add the new skill to the repository skill index and root README catalog.

## Non-goals

* Generate, store, read, or transmit OCI auth tokens.
* Run `docker login`, `docker tag`, `docker push`, `docker logout`, create a
  repository, or change any OCI resource as part of this implementation.
* Support non-OC1 realms, CI secret integration, image signing, or deployment.
  These require separate specifications.
* Replace the local build and verification workflow in Spec 001.

## Assumptions and prerequisites

* The target is the OC1 realm. The configured OCI CLI profile is authenticated
  and can run `oci iam region list`; the command returns region `name` and
  `key` values for the profile's realm.
* The local image has already passed Spec 001 and uses a user-supplied semantic
  version tag.
* OCI CLI is installed and configured with a profile that can inspect the target
  compartment and manage its Container Registry repositories. The CLI requires
  a compartment OCID; the skill resolves it from the configured name.
* The operator has a Docker credential helper configured, or understands Docker
  credential storage before logging in.
* The operator belongs to an OCI group with the required access to the target
  repository in the target compartment. OCI `repos` policies can be constrained
  by `target.repo.name`.

## Configuration contract

The root `.env.example` and ignored root `.env` use these non-secret values:

```dotenv
OCI_REGION=eu-frankfurt-1
OCI_COMPARTMENT_NAME=replace-with-target-compartment-name
OCIR_TENANCY_NAMESPACE=replace-with-object-storage-namespace
OCIR_USERNAME=replace-with-ocir-login-username
```

`OCI_REGION` is an OCI region identifier, not a region key. For this OC1-only
workflow, `scripts/resolve_ocir_registry.sh` runs `oci iam region list --all`,
selects the exact matching region `name`, lowercases its `key`, and emits
`<key>.ocir.io`. For example, `eu-frankfurt-1` resolves through `FRA` to
`fra.ocir.io`. This supports every region returned by the configured profile
without a maintained list. It exits with code 64 for a missing or malformed
`OCI_REGION`, code 65 when the exact region is absent from CLI output, and code
1 when the CLI request or its response validation fails. The fully qualified
target image is:

```text
${OCIR_REGISTRY}/${OCIR_TENANCY_NAMESPACE}/<manifest publish.repository>:<tag>
```

Do not add `OCI_AUTH_TOKEN`, passwords, keys, or credential-store data to either
file. The repository ignores `.env`; `.env.example` contains placeholders only.

`OCI_COMPARTMENT_NAME` is a human-readable selection input. Before a mutation,
the skill searches active compartments with that exact name through the
configured OCI CLI profile. It proceeds only when exactly one OCID is returned;
zero or multiple matches require user direction. The resolved OCID is never
written to `.env`.

`OCIR_USERNAME` is the complete OCIR login username. It is normally
`<tenancy-namespace>/<username>`, or
`<tenancy-namespace>/<identity-domain>/<username>` for applicable identity-domain
tenancies; it is not just the OCI Console username.

## Intended behavior

The skill directs the operator to load only the non-secret configuration, check
the intended source image and target tag, and authenticate separately using an
interactive `docker login --username "$OCIR_USERNAME" "$OCIR_REGISTRY"`.
Docker prompts for the OCI auth token, so the token is not placed on the command
line or in a file managed by the repository.

Docker credentials are scoped to an exact registry hostname. The Frankfurt
aliases `fra.ocir.io` and `eu-frankfurt-1.ocir.io` are both valid, but a Docker
login to one does not authenticate the other. This workflow dynamically resolves
one region-key hostname from `OCI_REGION` and uses it consistently for login,
tagging, and push.

Before a remote mutation, the skill must show the exact source image, resolved
compartment OCID, and fully qualified OCIR target. The operator first runs:

```bash
scripts/ensure_ocir_repository.sh
```

The script resolves the active exact-name compartment, lists available
repositories with the configured OCI CLI profile, and exits with code 20 when
the requested repository is absent. It does not create a resource unless invoked
with `--create`. If the repository is absent, the skill obtains explicit user
authorization before the operator runs:

```bash
scripts/ensure_ocir_repository.sh --create
```

The script creates a deliberately private, mutable repository, waits up to 120
seconds for `AVAILABLE`, and reports its OCID. If it already exists, it does not
change it. Before `docker tag` or `docker push`, show the planned remote mutation
and obtain explicit user authorization. On approval it may tag the local image
and push the fully qualified target, then report the pushed image reference and
any digest Docker reports. It must stop on a create, tag, or push failure and
must never claim deployment compatibility from a successful push.

The operator can run `docker logout "$OCIR_REGISTRY"` to remove local registry
credentials. Revoking or rotating the OCI auth token is a Console/IAM action and
is not automated by the skill.

## Acceptance criteria

1. `.env.example` contains exactly the documented non-secret settings, including
   `OCI_COMPARTMENT_NAME`, and no secrets; root `.env` exists and is ignored by Git.
2. The README documents dynamic OC1 region-key endpoint derivation from OCI CLI,
   compartment-name resolution, OCI CLI, private repository creation,
   configuration loading, interactive auth-token handling, target image format,
   IAM prerequisite, and cleanup without exposing an actual credential.
3. `skills/oci-agent-push/SKILL.md` has valid frontmatter, is concise, and
   requires explicit authorization before remote mutation.
4. `agents/openai.yaml` has valid UI metadata and allows implicit invocation.
5. The skill catalog lists `oci-agent-push`; `.agents/skills` exposes it.
6. Static checks pass: `git diff --check`, the skill validator, referenced-file
   checks, Bash syntax and behavior checks for both OCIR scripts, and a review
   that `.env` is ignored. No Docker login, tag, push, or OCI resource operation
   is performed for these criteria.
7. Remote acceptance remains pending until an operator supplies configuration,
   confirms OCI CLI, IAM access and credential storage, explicitly authorizes a
   repository target and creation if needed, and records sanitized creation,
   push, and cleanup results.

## Sources

Verified 2026-09-23:

* [Oracle: Pushing Images Using the Docker CLI](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrypushingimagesusingthedockercli.htm)
* [Oracle: Preparing for Container Registry](https://docs.oracle.com/en-us/iaas/Content/Registry/Concepts/registryprerequisites.htm)
* [Oracle: Container Registry IAM policy reference](https://docs.oracle.com/en-us/iaas/Content/Identity/policyreference/registrypolicyreference.htm)
* [Oracle: Creating a Repository](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrycreatingarepository.htm)
* [Oracle: Container Registry concepts](https://docs.oracle.com/en-us/iaas/Content/Registry/Concepts/registryconcepts.htm)
* [Oracle: Installing the CLI](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/climanualinst.htm)
* [Oracle CLI: Listing regions and filtering with queries](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliusing.htm)
* [Oracle CLI: List Compartments](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/iam/compartment/list.html)
* [Oracle CLI: List Container Repositories](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/artifacts/container/repository/list.html)
* [Oracle CLI: Create Container Repository](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/artifacts/container/repository/create.html)
* [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills)

## Verification record

2026-09-22: static acceptance criteria 1–6 passed. OCI CLI 3.94.0 was installed
in the `codex-4-oci-enterprise-ai-deployment` Conda environment from
`requirements-dev.txt`; its version check passed. The root `.env` is ignored and
contains only non-secret configuration keys. The example, README, skill,
metadata, and catalog reference the same OC1 region-derived endpoint format and
compartment-name resolution. The skill validator, Bash syntax check, and
`--help` check for `ensure_ocir_repository.sh` passed; its missing-configuration
path exited with code 64 before any OCI CLI call. Authenticated OCI CLI operations
remain untested: no Docker registry login or OCI resource inspection, creation,
change, or push was attempted.

Criterion 7 is satisfied for repository creation and image push. The optional
local Docker credential-cleanup decision remains with the operator.

2026-09-22: remote repository-creation verification passed after explicit
operator authorization. With the configured OC1 region and compartment, the
script resolved one active compartment, detected that `agents/hello-world` was
absent, and created a private, mutable repository. OCI CLI waited for
`AVAILABLE` and reported a container-repository OCID; the full OCID is retained
only in the operator's command output. No Docker login, tag, or push was
performed. OCI CLI warned that the local OCI configuration and private-key file
permissions are too open; this warning did not prevent the operation and has not
been changed by this workflow.

2026-09-22: after separate explicit push authorization, Docker tagged
`hello-world:0.1.0` for the configured OCIR target and attempted a push. OCIR
returned `403 Forbidden` while Docker checked an image-layer blob, so no image
digest was reported and remote push acceptance remains pending. The local target
tag was retained. No retry, credential change, or cleanup action was performed.

2026-09-22: diagnostic inspection of Docker configuration showed a credential
entry for `fra.ocir.io`, while the workflow pushed to
`eu-frankfurt-1.ocir.io`. Because Docker credentials are host-specific, this is
the identified cause of the failed push. No credential content was inspected.

2026-09-22: the operator explicitly selected the valid Frankfurt alias
`fra.ocir.io`, confirmed Docker login there using existing credentials, and
authorized a retry. The push of `hello-world:0.1.0` to
`fra.ocir.io/<tenancy-namespace>/agents/hello-world:0.1.0` succeeded. Docker
reported all layers as pushed and the manifest digest
`sha256:45533f02a491be15c28d8be4446bef7e65db057c5be482e1b9de1a1fa5fdf363`.
This verifies OCIR publication only; OCI Enterprise AI deployment compatibility
has not been verified.

2026-09-22: after a subsequent local rebuild and separate explicit push
authorization, Docker retagged and pushed the same image to the same Frankfurt
region-key target. All image layers were already present, and Docker again
reported digest
`sha256:45533f02a491be15c28d8be4446bef7e65db057c5be482e1b9de1a1fa5fdf363`.

2026-09-22: based on the successful Frankfurt region-key endpoint verification,
the supported registry resolution changed from region-identifier endpoints to
explicit region-key mappings. Bash syntax checks passed for both OCIR scripts;
the resolver returned `fra.ocir.io` for Frankfurt and `ord.ocir.io` for Chicago,
and rejected an unsupported region with exit code 64. Chicago remote verification
remains pending.

2026-09-23: the resolver changed from a maintained two-region map to dynamic
derivation through `oci iam region list --all`. Static Bash syntax and
mocked-CLI behavior checks verified `eu-frankfurt-1` / `FRA` resolves to
`fra.ocir.io`, an additional mocked region resolves from its returned key, an
absent region exits 65, and a CLI failure exits 1. No authenticated OCI CLI
request, Docker operation, or OCI resource mutation was performed. Remote
verification of the dynamic resolver remains pending.

2026-09-23: after the `hello-world:0.2.0` local build and verification passed,
the configured OC1 repository was inspected without mutation and found to
exist. Following separate explicit authorization, Docker tagged and pushed
`hello-world:0.2.0` to the resolved `fra.ocir.io` target. All layers were
already present and Docker reported manifest digest
`sha256:45533f02a491be15c28d8be4446bef7e65db057c5be482e1b9de1a1fa5fdf363`.
This verifies OCIR publication only; Hosted Application deployment compatibility
was not tested.
