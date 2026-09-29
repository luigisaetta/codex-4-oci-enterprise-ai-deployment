---
name: oci-agent-deploy
description: Plan or deploy a verified OCIR container image to OCI Generative AI Hosted Applications, not OCI AI Data Platform (AI DP) code-first agents, using managed networking and no inbound auth config.
---

# OCI Agent Deploy

Deploy a verified, published `linux/amd64` agent image to OCI Generative AI
Hosted Applications. This skill uses `NO_AUTH_CONFIG`, a public endpoint, and
Oracle-managed networking. It does not build, push, alter IAM, or delete
resources. It supplies container environment variables only from validated
manifest `runtime.env` data.

## Tool home and working directory

Resolve the real path of this skill's folder, following symbolic links:

```bash
skill_real="$(cd -P -- "<this skill folder>" && pwd -P)"
TOOL_HOME="$(dirname -- "$(dirname -- "$skill_real")")"
```

In PowerShell, resolve the link target of the skill folder and take its
grandparent. Run every script as `"$TOOL_HOME/scripts/<name>.sh"` (PowerShell:
`& "$TOOL_HOME\scripts\<name>.ps1"`) from the user's current folder. Never
change directory into the tool home. Pass the manifest path as the user gives it
(relative to the current folder) or as an absolute path. Its build paths are
relative to the manifest's own folder.

Run inside the Conda environment `codex-4-oci-enterprise-ai-deployment`
(activated, or `conda run --no-capture-output -n
codex-4-oci-enterprise-ai-deployment ...`), or set `OCI_AGENT_PYTHON`. Tenancy
settings come from `OCI_AGENT_ENV_FILE`, default `"$TOOL_HOME/.env"`; the
scripts read it themselves. Never source it, and never print its content. In a
sandboxed session, request permission for Docker and network access before the
first Docker, OCI CLI, or HTTP command, instead of retrying after a failure.

## Prerequisites

Read [Hosted Application deployment rules](references/hosted-application.md).
After `oci-agent-build` and `oci-agent-push` complete, OCI CLI must be configured
and authorized for the target compartment.

The tenancy file contains only tenancy-wide values. The agent manifest supplies
the repository, application name, public no-auth profile, and functional checks;
the release tag is always an explicit command-line value. Do not add a token,
password, or private key to either file. Non-secret container environment
configuration belongs only in validated manifest `runtime.env` entries.

When `runtime.env` is present, inspect its source report in the plan. Literal
and `from_env` values are plaintext; Vault references are never printed. A
missing `from_env` input stops the plan. Existing applications must already have
the same runtime environment because this skill does not update applications.

## Shell selection

The examples below are Bash. From PowerShell 7.4+ run
`& "$TOOL_HOME\scripts\deploy_hosted_application.ps1"` with the same option names in
`-Option` form (`--apply` becomes `-Apply`); outputs and exit codes are
identical, and no container engine is needed. Follow the shell in use, never the
operating system, and do not mix the two families in one release. Rule and
mapping table: [Choosing Bash or PowerShell](../README.md#choosing-bash-or-powershell).

## Workflow

1. Require an agent manifest named in the current request and a semantic tag. If
   the manifest is absent, ask “Which agent manifest should I use?” before any
   Docker or OCI action. Never select a demo, scan for a manifest, or infer it
   from conversation history; an explicit “use the same agent/manifest as the
   immediately preceding step” is sufficient. Confirm its local image has passed
   local verification and was pushed to the exact OCIR target.
2. Run the non-mutating plan:

   ```bash
   "$TOOL_HOME/scripts/deploy_hosted_application.sh" --manifest /path/to/agent/agent.yaml --tag 0.1.0
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
   "$TOOL_HOME/scripts/deploy_hosted_application.sh" --apply --manifest /path/to/agent/agent.yaml --tag 0.1.0
   ```

5. Report resulting OCIDs and CLI work-request outcomes. Do not invoke the
   endpoint without separate user direction: it is public and unauthenticated.

## Exit codes

| Code | Meaning and action |
| --- | --- |
| 0 | Plan completed, or authorized creation completed. |
| 1 | Python with PyYAML, OCI CLI, or an OCI operation is unavailable or failed. |
| 20 | An existing resource cannot be reused; inspect the reported state. |
| 64 | Invalid arguments, missing tenancy settings, or manifest errors (including paths outside allowed roots); correct the input. |
| 65 | The configured OCI region is not available to the OCI CLI profile. |

## Limitations

The script deliberately omits `--storage-configs` and custom networking. It
supplies `--environment-variables` only from validated manifest `runtime.env`
data. It never creates IAM policies or dynamic groups needed for the Hosted
Deployment runtime to pull a private image. It does not update or replace an
existing deployment and does not delete resources.
