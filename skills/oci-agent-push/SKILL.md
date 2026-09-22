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
`OCIR_TENANCY_NAMESPACE`, `OCIR_REPOSITORY`, and `OCIR_USERNAME`. Do not put an
auth token, password, private key, or Docker credential in it, in a prompt, or
in command arguments.

## Workflow

1. Confirm the local image and its user-supplied semantic tag. Check that all
   required non-secret settings are configured; do not print unrelated `.env`
   content. Confirm OCI CLI availability and profile access.
2. For OC1, derive `OCIR_REGISTRY="${OCI_REGION}.ocir.io"` and show the exact
   target: `${OCIR_REGISTRY}/${OCIR_TENANCY_NAMESPACE}/${OCIR_REPOSITORY}:<tag>`.
   Stop if the realm is not OC1 or a setting is missing.
3. Resolve `OCI_COMPARTMENT_NAME` and inspect the target with the non-mutating
   command below. It proceeds only if exactly one active compartment OCID
   matches; exit code 20 means that the repository is absent.

   ```bash
   scripts/ensure_ocir_repository.sh
   ```

4. If the requested repository is absent, show the resolved compartment OCID
   reported by the command and obtain explicit user authorization before running:

   ```bash
   scripts/ensure_ocir_repository.sh --create
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
7. After authorization, tag the local image and push the fully qualified target.
   Report the source, target, exit code, and digest Docker reports. Stop on
   failure; do not retry a push without direction.
8. State that a push does not verify hosted deployment compatibility. Offer
   `docker logout "$OCIR_REGISTRY"` as optional local credential cleanup; token
   revocation is a separate OCI Console/IAM action.

## Limitations

This skill supports only OC1 endpoints derived from an OCI region identifier.
It does not alter IAM policies, manage auth tokens, sign images, run CI, or
deploy OCI resources. A successful push is remote registry evidence only, not
deployment evidence.
