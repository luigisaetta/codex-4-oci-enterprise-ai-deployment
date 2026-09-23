---
name: oci-agent-push
description: Create a missing OCIR repository and, with explicit authorization, push a verified agent image in the OC1 realm. Use after a local image has passed verification; do not deploy OCI resources.
---

# OCI Agent Push

Prepare a verified local `linux/amd64` agent image for OCIR, create its missing
private repository only after explicit authorization, then push only after a
separate push authorization. This skill does not deploy hosted applications.

## Prerequisites

Read [OCIR authentication and target rules](references/ocir-authentication.md).
Run from the checkout containing this skill. The image must already have passed
`oci-agent-build` verification. Docker and OCI CLI must be available and the
configured OCI CLI profile must have IAM access to the target compartment.

The root `.env` holds only `OCI_REGION`, `OCI_COMPARTMENT_NAME`,
`OCIR_TENANCY_NAMESPACE`, and `OCIR_USERNAME`. The agent manifest supplies the
repository and local image name. Do not put an
auth token, password, private key, or Docker credential in it, in a prompt, or
in command arguments.

`OCIR_USERNAME` must be the complete OCIR login username, normally
`<tenancy-namespace>/<username>` (or
`<tenancy-namespace>/<identity-domain>/<username>` for applicable identity-domain
tenancies), rather than only the OCI Console username.

## Shell selection

The examples below are Bash. From PowerShell 7.4+ run the `scripts/*.ps1` twin
with the same option names in `-Option` form (`--push` becomes `-Push`,
`--repository` becomes `-Repository`); outputs and exit codes are identical, and
`docker login`/`docker logout` become `podman login`/`podman logout` when the
selected engine is Podman. Follow the shell in use, never the operating system,
and do not mix the two families in one release. Rule and mapping table:
[Choosing Bash or PowerShell](../README.md#choosing-bash-or-powershell).

## Workflow

1. Require an agent manifest named in the current request. If it is absent, ask
   “Which agent manifest should I use?” before inspecting Docker, OCI, or `.env`.
   Never select a demo, scan for a manifest, or infer one from conversation
   history; an explicit “use the same agent/manifest as the immediately preceding
   step” is sufficient. Confirm the local image and its user-supplied semantic tag. Check that all
   required non-secret settings are configured; do not print unrelated `.env`
   content. Confirm OCI CLI availability and profile access.
2. Resolve `OCI_REGION` dynamically to its OCIR region-key endpoint and show
   the exact target. The resolver runs `oci iam region list`, selects the exact
   region name, lowercases its key, and constructs `<region-key>.ocir.io`. It
   stops if the region is not returned or the CLI request fails.

   ```bash
   OCIR_REGISTRY="$(scripts/resolve_ocir_registry.sh)"
   ```

   The target is
   `${OCIR_REGISTRY}/${OCIR_TENANCY_NAMESPACE}/<manifest repository>:<tag>`.
3. Resolve `OCI_COMPARTMENT_NAME` and inspect the target with the non-mutating
   command below. It proceeds only if exactly one active compartment OCID
   matches; exit code 20 means that the repository is absent.

   ```bash
   scripts/ensure_ocir_repository.sh --repository <manifest repository>
   ```

4. If the requested repository is absent, show the resolved compartment OCID
   reported by the command and obtain explicit user authorization before running:

   ```bash
   scripts/ensure_ocir_repository.sh --repository <manifest repository> --create
   ```

   This creates a private, mutable repository, waits up to 120 seconds for
   `AVAILABLE`, records the new repository OCID, and stops on failure. Do not
   change an existing repository.
5. Ask the operator to authenticate separately with interactive Docker login:

   ```bash
   docker login --username "$OCIR_USERNAME" "$OCIR_REGISTRY"
   ```

   The operator enters an OCI auth token only at Docker's password prompt. Check
   that a Docker credential helper is configured or warn that Docker may store
   credentials in its config file.
6. Before `docker tag` or `docker push`, identify the target repository and IAM
   prerequisite, show the planned remote mutation, and obtain explicit user
   authorization. Do not infer permission from configured credentials.
7. After authorization, run the guarded helper, which tags the local image and
   pushes the fully qualified target:

   ```bash
   scripts/push_ocir_image.sh --push --manifest demos/hello_world/agent.yaml --tag 0.1.0
   ```
   Report the source, target, exit code, and digest the container engine
   reports. Stop on failure; do not retry a push without direction.
8. State that a push does not verify hosted deployment compatibility. Offer
   `docker logout "$OCIR_REGISTRY"` as optional local credential cleanup; token
   revocation is a separate OCI Console/IAM action.

## Limitations

This skill supports only OC1 endpoints derived from an OCI region identifier.
It does not alter IAM policies, manage auth tokens, sign images, run CI, or
deploy OCI resources. A successful push is remote registry evidence only, not
deployment evidence.
