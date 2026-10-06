---
name: oci-agent-deploy
description: Plan or deploy a verified OCIR container image to OCI Generative AI Hosted Applications, not OCI AI Data Platform (AI DP) code-first agents, using managed networking and a public inbound-auth profile.
---

# OCI Agent Deploy

Deploy a verified, published `linux/amd64` agent image to OCI Generative AI
Hosted Applications. This skill uses a public endpoint and Oracle-managed
networking. It does not build, push, alter IAM, or delete
applications. It deletes a `FAILED` deployment only for an explicitly requested
replacement. It supplies container environment variables only from validated
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
scripts read it themselves. Never source it, read it into the conversation, or print its content: it may
hold agent secrets. In a
sandboxed session, request permission for Docker and network access before the
first Docker, OCI CLI, or HTTP command, instead of retrying after a failure.

## Prerequisites

Read [Hosted Application deployment rules](references/hosted-application.md).
After `oci-agent-build` and `oci-agent-push` complete, OCI CLI must be configured
and authorized for the target compartment.

A request to deploy authorizes only deployment. Creating an OCIR repository or
pushing an image requires its own explicit authorization through
`oci-agent-push`; do not treat the deploy request as authorization for either.

The tenancy file contains only tenancy-wide values. The agent manifest supplies
the repository, application name, public no-auth profile, and functional checks;
the release tag is always an explicit command-line value. Do not add a token,
password, or private key to either file. Non-secret container environment
configuration belongs only in validated manifest `runtime.env` entries.

When `runtime.env` is present, inspect its source report in the plan. Literal
values are printed; `from_env` values are shown as `value=<hidden>` with their
origin (environment or tool `.env`); Vault references are never printed. A
missing `from_env` input stops the plan. Existing applications must already have
the same runtime environment because this skill does not update applications.

## Shell selection

The examples below are Bash. From PowerShell 7.4+ run
`& "$TOOL_HOME\scripts\deploy_hosted_application.ps1"` with the same option names in
`-Option` form (`--apply` becomes `-Apply`); outputs and exit codes are
identical, and no container engine is needed. Follow the shell in use, never the
operating system, and do not mix the two families in one release. Rule and
mapping table: [Choosing Bash or PowerShell](../README.md#choosing-bash-or-powershell).

## Target platform check

These skills release container images to OCI Generative AI Hosted Applications.
Before any command, check the current repository: an `agent.yaml` with
`schema_version` and a `Dockerfile` indicate Hosted Applications; an entry file
whose class has a synchronous `setup()` and an async `invoke()`, without
`agent.yaml`, indicates an OCI AI Data Platform (AI DP) code-first agent. If the
signals indicate AI DP, stop and tell the user to use the `aidp-agent-deploy`
skill instead. If the signals are mixed or absent, ask the user which platform
they mean. Never switch platform silently.

## Workflow

### Inbound authentication profiles

`public-noauth` creates `NO_AUTH_CONFIG` and the plan states `Access: public
unauthenticated endpoint.` `public-idcs` requires `deploy.auth.domain_url`,
`deploy.auth.audience`, and `deploy.auth.scope`. The domain URL must be an
HTTPS host URL with no path or query; audience and scope must be non-empty and
contain no whitespace. Its plan states `Access: public endpoint,
identity-domain token required` and reports identity domain URL, audience, and
scope.

Get these non-secret values from the identity-domain administrator; its
confidential application may be new or reused. Use only
`<identity-domain-url>`, `<audience-of-the-confidential-application>`, and
`<scope-of-the-confidential-application>` in examples. Deploy validates their
syntax but does not test them or call the identity domain. Never put a client
ID, client secret, or access token in configuration. The client secret and
access token must never be typed into chat, printed, or stored; the operator
exports the client ID and secret only in the shell that runs the verifier.

1. Require an agent manifest named in the current request and a semantic tag. If
   the manifest is absent, ask “Which agent manifest should I use?” before any
   Docker or OCI action. Never select a demo, scan for a manifest, or infer it
   from conversation history; an explicit “use the same agent/manifest as the
   immediately preceding step” is sufficient. Confirm its local image has passed
   local verification and was pushed to the exact OCIR target. If the image is
   not published, stop and offer the push skill with its separate authorization.
2. Run the non-mutating plan:

   ```bash
   "$TOOL_HOME/scripts/deploy_hosted_application.sh" --manifest /path/to/agent/agent.yaml --tag 0.1.0
   ```

   Stop if the configured OCI CLI profile cannot resolve the region, the named
   compartment is ambiguous, required OCI permissions are unavailable, or an
   existing same-named application is neither `ACTIVE` nor `CREATING`. An
   `ACTIVE` manifest-compatible application is reused; a `CREATING` application
   can finish its first release. A `DELETED` application does not block a new
   deployment. The deploy wait timeout is `--timeout-seconds SECONDS`
   (`-TimeoutSeconds` in PowerShell), default 1800 seconds.
3. Show the plan again before asking for authorization. The plan reports the
   resolved image URI, compartment, Hosted Application name, release case,
   current and target tags, artifact count, endpoint status, runtime-variable
   source report, inbound-auth access lines, and planned action. If the plan
   says `Failed deployment`, report its OCI error and stop. Mention replacement
   only as an option the user may request. After an explicit request for a new
   deploy of that failed release, rerun the plan with `--replace-failed`
   (`-ReplaceFailed` in PowerShell), and show the replacement plan for approval.
4. Obtain one explicit authorization for the apply of the case shown in the
   plan. For a new version, that authorization covers both adding and
   activating the artifact. For `Application creation in progress`, it covers
   waiting, checking the application, and creating the deployment shown in the
   plan. Then run:

   ```bash
   "$TOOL_HOME/scripts/deploy_hosted_application.sh" --apply --manifest /path/to/agent/agent.yaml --tag 0.1.0
   ```

   For an approved `Replace failed deployment` plan, add `--replace-failed`
   (`-ReplaceFailed` in PowerShell) to the apply command.

5. Report resulting OCIDs and CLI work-request outcomes. Do not invoke the
   endpoint without separate user direction: it is public and unauthenticated.

### Release cases

The script identifies the deployment as the application's single non-deleted
deployment.

| Script case | Plan shows | Apply does |
| --- | --- | --- |
| `First release` | The application and deployment will be created with the target artifact. | Creates the Hosted Application and its first Hosted Deployment. |
| `Already released` | The target tag is already active and no change is needed. | Makes no mutation and exits 0. |
| `New version` | The target tag will be added and activated in place of the current tag. | Adds the artifact, then activates it and waits for the work request. |
| `Return to a previous version` | The inactive target artifact will be activated. | Activates that artifact only. This is rollback: deploy the previous tag. |
| `Creation in progress` | The `CREATING` deployment, its OCID, state, and age. | Resumes waiting for `ACTIVE` without another create. |
| `Application creation in progress` | The `CREATING` application, its OCID, state, and age, then the deployment to create with the target tag. | Waits for `ACTIVE`, checks inbound authentication and runtime environment, then creates the deployment and waits for `ACTIVE`. If the wait or either check fails, it does not create a deployment. |
| `Failed deployment` | The `FAILED` deployment OCID, OCI failure code and message, and how to request replacement. | Makes no mutation and exits 20. Report the OCI error and stop. Offer replacement only as an option the user may request. |
| `Replace failed deployment` | The `FAILED` deployment OCID and failure reason, then its deletion and creation of a new deployment with the target tag; the endpoint stays unchanged. | Deletes that deployment with `--force`, waits for deletion, then creates and waits for the replacement. Stops without creating if deletion fails or times out. |

Stop with exit 20 and make no change if application or deployment state cannot
be reused, the runtime environment differs, there is not exactly one applicable
resource, the target artifact is `FAILED` or `UPDATING`, or adding it would
exceed the 20-artifact limit. A `FAILED` deployment also exits 20 unless the
user requested replacement. Exit 20 also applies when an existing application
uses different inbound authentication; changing authentication is not
supported. Report the observed state and ask the operator to check it.

Never delete or recreate an application or a deployment, except a deployment in
state `FAILED`, replaced on the user's explicit request through
`--replace-failed` (`-ReplaceFailed` in PowerShell). Use this option only after
the user explicitly asks for a new deploy of the failed release. Show the
`Replace failed deployment` plan again and obtain approval for that plan before
applying it. The option with any other deployment state exits 64 and changes
nothing. Manual cleanup of old artifacts is outside this skill: only inactive
artifacts may be removed, using the Console or `oci generative-ai
hosted-deployment delete-hosted-deployment-artifact`.

## Exit codes

| Code | Meaning and action |
| --- | --- |
| 0 | Plan completed, an authorized release completed, or the tag was already active. |
| 1 | Python with PyYAML, OCI CLI, or an OCI operation is unavailable or failed. Report any OCI error printed by the script and stop. |
| 20 | An existing resource cannot be reused, including a `FAILED` deployment without a replacement request; inspect the reported state and OCI error. |
| 26 | OCI is still working after the wait timeout. Report the resource OCID, state, and elapsed time: nothing else was changed or deleted by the script after the request, and OCI continues. Offer to run deploy again to resume waiting. Never delete or recreate in response to a timeout. |
| 64 | Invalid arguments, missing tenancy settings, manifest errors (including paths outside allowed roots), or `--replace-failed` without a `FAILED` deployment; correct the input. |
| 65 | The configured OCI region is not available to the OCI CLI profile. |

## Limitations

The script deliberately omits `--storage-configs` and custom networking. It
supplies `--environment-variables` only from validated manifest `runtime.env`
data. It never creates IAM policies or dynamic groups needed for the Hosted
Deployment runtime to pull a private image. It activates or adds artifacts in
an existing deployment. It deletes only a `FAILED` deployment on an explicitly
requested and approved replacement plan.
