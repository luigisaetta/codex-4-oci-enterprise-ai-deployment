# Spec 002: Codex skill `oci-agent-push`

Status: implemented; static acceptance criteria passed; remote acceptance is pending user configuration and authorization.
Date: 2026-09-22.

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
5. Add the new skill to the repository skill index and root README catalog.

## Non-goals

* Generate, store, read, or transmit OCI auth tokens.
* Run `docker login`, `docker tag`, `docker push`, `docker logout`, create a
  repository, or change any OCI resource as part of this implementation.
* Support non-OC1 realms, CI secret integration, image signing, or deployment.
  These require separate specifications.
* Replace the local build and verification workflow in Spec 001.

## Assumptions and prerequisites

* The target is the OC1 realm. For an OCI region identifier, the registry domain
  is `<OCI_REGION>.ocir.io`; for example, `eu-frankfurt-1.ocir.io`.
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
OCIR_REPOSITORY=agents/hello-world
OCIR_USERNAME=replace-with-oci-username
```

`OCI_REGION` is an OCI region identifier, not a region key. For this OC1-only
workflow, derive the registry domain as `${OCI_REGION}.ocir.io`. The fully
qualified target image is:

```text
${OCI_REGION}.ocir.io/${OCIR_TENANCY_NAMESPACE}/${OCIR_REPOSITORY}:<tag>
```

Do not add `OCI_AUTH_TOKEN`, passwords, keys, or credential-store data to either
file. The repository ignores `.env`; `.env.example` contains placeholders only.

`OCI_COMPARTMENT_NAME` is a human-readable selection input. Before a mutation,
the skill searches active compartments with that exact name through the
configured OCI CLI profile. It proceeds only when exactly one OCID is returned;
zero or multiple matches require user direction. The resolved OCID is never
written to `.env`.

## Intended behavior

The skill directs the operator to load only the non-secret configuration, check
the intended source image and target tag, and authenticate separately using an
interactive `docker login --username "$OCIR_USERNAME" "$OCIR_REGISTRY"`.
Docker prompts for the OCI auth token, so the token is not placed on the command
line or in a file managed by the repository.

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
2. The README documents OC1 endpoint derivation, compartment-name resolution,
   OCI CLI, private repository creation, configuration loading, interactive
   auth-token handling, target image format, IAM prerequisite, and cleanup
   without exposing an actual credential.
3. `skills/oci-agent-push/SKILL.md` has valid frontmatter, is concise, and
   requires explicit authorization before remote mutation.
4. `agents/openai.yaml` has valid UI metadata and allows implicit invocation.
5. The skill catalog lists `oci-agent-push`; `.agents/skills` exposes it.
6. Static checks pass: `git diff --check`, the skill validator, referenced-file
   checks, a Bash syntax and help check for `ensure_ocir_repository.sh`, and a
   review that `.env` is ignored. No Docker login, tag, push, or OCI resource
   operation is performed for these criteria.
7. Remote acceptance remains pending until an operator supplies configuration,
   confirms OCI CLI, IAM access and credential storage, explicitly authorizes a
   repository target and creation if needed, and records sanitized creation,
   push, and cleanup results.

## Sources

Verified 2026-09-22:

* [Oracle: Pushing Images Using the Docker CLI](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrypushingimagesusingthedockercli.htm)
* [Oracle: Preparing for Container Registry](https://docs.oracle.com/en-us/iaas/Content/Registry/Concepts/registryprerequisites.htm)
* [Oracle: Container Registry IAM policy reference](https://docs.oracle.com/en-us/iaas/Content/Identity/policyreference/registrypolicyreference.htm)
* [Oracle: Creating a Repository](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrycreatingarepository.htm)
* [Oracle: Installing the CLI](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/climanualinst.htm)
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

Criterion 7 is pending explicit operator configuration and authorization.
