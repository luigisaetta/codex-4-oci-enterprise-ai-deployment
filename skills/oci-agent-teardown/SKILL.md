---
name: oci-agent-teardown
description: Remove an agent of OCI Generative AI Hosted Applications (Hosted Deployments, OCI Enterprise AI) completely, not for OCI AI Data Platform (AI DP) agents. Use when asked to delete, tear down, or clean up an agent. Plans first; with explicit authorization and the typed application name, deletes the Hosted Application and its deployment, its managed storage, its OCIR repository with the images, and its local container images.
---

# OCI Agent Teardown

Contract and verification: [Spec 029](../../specs/029-skill-oci-agent-teardown.md).

Remove everything that one agent manifest created, in a safe order: the Hosted
Application (which deletes its deployment), the managed storage of
`deploy.storage`, the OCIR repository of `publish.repository` with all its
images, and the local container images of the agent. This is the only skill
that deletes resources; deleting is permanent.

## Tool home and working directory

Resolve the real path of this skill's folder, following symbolic links:

```bash
skill_real="$(cd -P -- "<this skill folder>" && pwd -P)"
TOOL_HOME="$(dirname -- "$(dirname -- "$skill_real")")"
```

In PowerShell, resolve the link target of the skill folder and take its
grandparent. Run the script as `"$TOOL_HOME/scripts/teardown_agent.sh"`
(PowerShell: `& "$TOOL_HOME\scripts\teardown_agent.ps1"`) from the user's
current folder. Never change directory into the tool home. Pass the manifest
path as the user gives it or as an absolute path.

Run inside the Conda environment `oci-agent-shipyard` (activated, or `conda run
--no-capture-output -n oci-agent-shipyard ...`), or set `OCI_AGENT_PYTHON`.
Tenancy settings come from `OCI_AGENT_ENV_FILE`, default `"$TOOL_HOME/.env"`;
the script reads it itself. Never source it, read it into the conversation, or
print its content: it may hold agent secrets. In a sandboxed session, request
permission for network and container engine access before the first command.

Never edit files in the tool home.

## Prerequisites

* The agent's `agent.yaml`, the tool's tenancy settings (`OCI_REGION`,
  `OCI_COMPARTMENT_NAME`, `OCIR_TENANCY_NAMESPACE`), and an OCI CLI profile
  allowed to delete Hosted Applications, storages, and OCIR repositories in the
  compartment.
* Docker or Podman, running, only to remove the local images. Without one, the
  OCI resources are still removed and the local images are reported.

## Shell selection

The examples are Bash. From PowerShell 7.4+ run the twin with the same options
in `-Option` form (`--apply` becomes `-Apply`, `--confirm` becomes `-Confirm`,
`--container-engine` becomes `-ContainerEngine`); both run the same
`teardown_agent.py`, so outputs and exit codes are identical. Follow the shell
in use: [Choosing Bash or PowerShell](../README.md#choosing-bash-or-powershell).

## Target platform check

This skill removes agents of OCI Generative AI Hosted Applications (also called
Hosted Deployments or OCI Enterprise AI)
([Spec 028](../../specs/028-platform-dispatch.md)). Before any command, decide
the platform in this order:

1. If the repository's `AGENTS.md` has a "Target platform" section, follow it.
   If it names OCI AI Data Platform (AI DP), stop with this message:
   "This agent targets OCI AI Data Platform (AI DP); these skills support only
   OCI Generative AI Hosted Applications. Use the skills for OCI AI DP."
2. Otherwise, infer it from the files: an `agent.yaml` with `schema_version`
   and a `Dockerfile` indicate Hosted Applications; an entry file whose class
   has a synchronous `setup()` and an asynchronous `invoke()`, without
   `agent.yaml`, indicates an AI DP code-first agent: stop with the message
   above.
3. If the signals are mixed or absent, ask the user which platform they mean.

Never switch platform silently.

## Workflow

1. Perform the target platform check and identify the manifest (ask for its
   path if it is not `./agent.yaml`).
2. Run the plan, which reads OCI and lists local images only:

   ```bash
   "$TOOL_HOME/scripts/teardown_agent.sh" --plan --manifest agent.yaml
   ```

3. Show the **complete** plan output to the user, never a summary: every
   resource with its OCID and action (`delete`, `keep` with the reason, `not
   found`), the warnings that the storage data and the repository images are
   lost permanently, and the list of resources that are kept.
4. Ask for explicit authorization of that plan **and** ask the user to type
   the application name. Never infer the name or the authorization from
   earlier messages, from another plan, or from a request to "clean up".
5. Only after both, in the same conversation, run:

   ```bash
   "$TOOL_HOME/scripts/teardown_agent.sh" --apply --confirm <application-name> --manifest agent.yaml
   ```

   `--confirm` must be the name the user typed; the script refuses any other
   value before calling OCI.
6. Report what was deleted, what was kept and why, and any local image left.
   After a failure (exit 1 or 26), report the message and offer to run the
   plan again: a rerun skips what is already deleted and continues.

Never run teardown to fix a failed release: for a `FAILED` deployment, the
deploy skill offers the replacement. Never run it on an agent the user did not
name, and never delete resources by hand or with other commands instead.

## What is deleted and what is kept

| Resource | Action |
| --- | --- |
| Hosted Application and its deployment | Deleted; the endpoint stops working. |
| Managed storage (`deploy.storage`) | Deleted with its data, unless it is linked to another application. |
| OCIR repository (`publish.repository`) | Deleted with all its images, unless another application of the compartment uses them. Applications of other compartments cannot be checked. |
| Local images `<name>:<tag>` and `<registry>/<namespace>/<repository>:<tag>` | Removed; an image used by a container is kept and reported. |
| IAM policies and dynamic groups, the identity-domain confidential application, OCI Vault secrets, the Generative AI project, the agent folder | Never touched. |

## Exit codes

| Code | Meaning and action |
| --- | --- |
| 0 | Plan completed, teardown completed, or nothing to delete. |
| 1 | An OCI or tool operation failed; the message says what was deleted and what is left. A `NotAuthorizedOrNotFound` is a missing permission: report it and stop; never create, modify, or delete dynamic groups, policies, groups, users, or identity domains. |
| 20 | A resource is still `CREATING` or `UPDATING`, or a name matches more than one resource; nothing was deleted. Wait, then plan again. |
| 26 | OCI is still deleting after the wait timeout; nothing else was changed. Offer to run the teardown again to resume waiting. |
| 64 | Invalid arguments, manifest errors, missing tenancy settings, or a missing or different `--confirm`. |
| 65 | The configured OCI region is not available to the OCI CLI profile. |

## Limitations

Only the resources named by the manifest, in the tool's compartment, are
considered; nothing is found by a name pattern. Deletion is permanent: the
data of the managed storage and the images of the repository cannot be
recovered. Old artifacts of a live application are not pruned (TODO item 13).
