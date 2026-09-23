# OCIR authentication and target rules

Reviewed 2026-09-23.

This skill supports the OC1 realm only. It dynamically resolves the configured
OCI region identifier with `oci iam region list`, selects the exact `name`,
lowercases its `key`, and constructs `<region-key>.ocir.io` (for example,
`eu-frankfurt-1` becomes `fra.ocir.io`). It stops if the configured CLI profile
does not return the region or if the CLI call fails; no maintained region map is
used.

Use this image-reference format:

```text
${OCIR_REGISTRY}/${OCIR_TENANCY_NAMESPACE}/${OCIR_REPOSITORY}:<tag>
```

Authenticate interactively. For Docker:

```bash
docker login --username "$OCIR_USERNAME" "$OCIR_REGISTRY"
```

For Podman on Windows:

```powershell
podman login --username $env:OCIR_USERNAME $OCIR_REGISTRY
```

The username is normally `<tenancy-namespace>/<username>`; identity-domain
tenancies can require `<tenancy-namespace>/<identity-domain>/<username>`. Enter
the OCI auth token only when Docker prompts for its password. OCI shows a newly
generated auth token only once. Do not use `--password`, record the token in a
file, or pass it to a repository script.

Container-runtime credentials are scoped to an exact registry hostname. Use the same
resolved `$OCIR_REGISTRY` value for login, tagging, and pushing.

Before a push, the operator needs Docker access, an OCI auth token, and IAM
access to the target repository. OCI policies use the `repos` resource type and
can restrict access with `target.repo.name`.

The root `.env` selects the target with `OCI_COMPARTMENT_NAME`. OCI repository
commands require its OCID, so list active compartments with the configured OCI
CLI profile and stop if the name has zero or multiple matches. List container
repositories using the resolved OCID. The repository script performs this check
without creation; exit code 20 means the repository is absent:

```bash
scripts/ensure_ocir_repository.sh
```

If the requested repository is absent, create it only after explicit
authorization:

```bash
scripts/ensure_ocir_repository.sh --create
```

This creates a private, mutable repository, waits for `AVAILABLE`, and reports
its OCID. Do not change an existing repository or rely on automatic creation
during `docker push`.

After a push, the matching runtime logout command (for example,
`podman logout $OCIR_REGISTRY`) removes its local registry credential. Rotate
or revoke the OCI auth token through OCI Console/IAM.

Sources:

* [Pushing Images Using the Docker CLI](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrypushingimagesusingthedockercli.htm)
* [Preparing for Container Registry](https://docs.oracle.com/en-us/iaas/Content/Registry/Concepts/registryprerequisites.htm)
* [Container Registry IAM policy reference](https://docs.oracle.com/en-us/iaas/Content/Identity/policyreference/registrypolicyreference.htm)
* [Creating a Repository](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrycreatingarepository.htm)
* [OCI CLI: Create Container Repository](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/artifacts/container/repository/create.html)
* [OCI CLI: Using queries and `oci iam region list`](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliusing.htm)
