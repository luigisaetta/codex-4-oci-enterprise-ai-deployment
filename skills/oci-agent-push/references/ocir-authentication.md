# OCIR authentication and target rules

Reviewed 2026-09-22.

This skill supports the OC1 realm only. Given `OCI_REGION=eu-frankfurt-1`, use
the Container Registry domain `eu-frankfurt-1.ocir.io`. The Frankfurt region-key
alias `fra.ocir.io` is also valid, but this workflow uses the region identifier
to avoid a separate region-key mapping.

Use this image-reference format:

```text
${OCI_REGION}.ocir.io/${OCIR_TENANCY_NAMESPACE}/${OCIR_REPOSITORY}:<tag>
```

Authenticate interactively:

```bash
docker login --username "$OCIR_USERNAME" "$OCIR_REGISTRY"
```

The username is normally `<tenancy-namespace>/<username>`; identity-domain
tenancies can require `<tenancy-namespace>/<identity-domain>/<username>`. Enter
the OCI auth token only when Docker prompts for its password. OCI shows a newly
generated auth token only once. Do not use `--password`, record the token in a
file, or pass it to a repository script.

Before a push, the operator needs Docker access, an OCI auth token, and IAM
access to the target repository. OCI policies use the `repos` resource type and
can restrict access with `target.repo.name`. The target repository should exist
unless its creation has been separately approved.

After a push, `docker logout "$OCIR_REGISTRY"` removes Docker's local registry
credential. Rotate or revoke the OCI auth token through OCI Console/IAM.

Sources:

* [Pushing Images Using the Docker CLI](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrypushingimagesusingthedockercli.htm)
* [Preparing for Container Registry](https://docs.oracle.com/en-us/iaas/Content/Registry/Concepts/registryprerequisites.htm)
* [Container Registry IAM policy reference](https://docs.oracle.com/en-us/iaas/Content/Identity/policyreference/registrypolicyreference.htm)
