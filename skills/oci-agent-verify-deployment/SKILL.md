---
name: oci-agent-verify-deployment
description: Verify a published container image release for OCI Generative AI Hosted Applications, not OCI AI Data Platform (AI DP) code-first agents, using read-only checks and public probes.
---

# OCI Agent Verify Deployment

Verify that a specific Hosted Application release is active and reachable.
This skill performs OCI reads and unauthenticated GET requests only; it never
creates, updates, deletes, restarts, or invokes agent business paths.

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

Read [endpoint rules and observed behavior](references/endpoint-behavior.md).
After `oci-agent-build`, `oci-agent-push`, and `oci-agent-deploy`, OCI CLI must
be available in the project Conda environment,
and the workstation must be able to reach the public endpoint (the Bash verifier
uses `curl`; the PowerShell verifier uses the built-in .NET HTTP client).

The tenancy file provides only tenancy-wide values including `OCI_REGION`. Do not
add an auth token, password, private key, endpoint override, or other secret to
it. The operator supplies the Hosted Application OCID, agent manifest, and
expected semantic image tag explicitly.

## Shell selection

The example below is Bash. From PowerShell 7.4+ run
`& "$TOOL_HOME\scripts\verify_deployment.ps1"` with the same option names in `-Option` form
(`--application-id` becomes `-ApplicationId`, `--functional` becomes
`-Functional`); the report line and exit codes are identical. Follow the shell
in use, never the operating system, and do not mix the two families in one
release. Rule and mapping table:
[Choosing Bash or PowerShell](../README.md#choosing-bash-or-powershell).

## Workflow

1. Require an agent manifest named in the current request. If it is absent, ask
   “Which agent manifest should I use?” before OCI reads or public probes. Never
   select a demo, scan for a manifest, or infer it from conversation history; an
   explicit “use the same agent/manifest as the immediately preceding step” is
   sufficient. Confirm the image tag was locally verified and pushed, then obtain explicit
   authorization before making the public probe requests.
2. Run the verifier from the project Conda environment. It first checks that the
   application is `ACTIVE`, that exactly one associated deployment is `ACTIVE`,
   and that its active artifact tag is the requested release.

   ```bash
   conda run --no-capture-output -n codex-4-oci-enterprise-ai-deployment \
     "$TOOL_HOME/scripts/verify_deployment.sh" \
     --application-id <application-ocid> \
     --manifest /path/to/agent/agent.yaml --tag 0.2.0
   ```

3. Only after the resource checks pass, the script polls the verified URL form
   ending in `/actions/invoke/health` and `/actions/invoke/ready`. A 200 health
   response with a non-200 readiness response means the container is running but
   not ready; polling continues within the configured timeout.
4. Report the application and deployment OCIDs, release tag, endpoint host, both
   HTTP statuses, readiness seconds, and result. A pass is evidence for this
   release's two probes only, not a production-security or general functional
   certification.

Use `--timeout-seconds` (default 300) and `--poll-seconds` (default 5) to bound
the probe. Do not add Authorization headers or try alternate endpoint hosts or
path encodings when a probe fails; report the observed result.

Functional checks defined in the manifest are not part of this default read-only
workflow. Only after separately obtaining authorization to invoke business paths
may you append `--functional`; report each request and response result.

Runtime environment validation belongs to build and deploy. This verifier does
not print or resolve Vault values.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Application, deployment, tag, health, and readiness checks passed. |
| 1 | Python with PyYAML, required OCI CLI (or, in Bash, curl) executable, or OCI operation is unavailable or failed. |
| 20 | Hosted Application is not `ACTIVE`. |
| 21 | The application does not have exactly one `ACTIVE` Hosted Deployment. |
| 22 | The active artifact tag differs from the expected tag. |
| 23 | The bounded probe ended without both endpoints returning HTTP 200. |
| 13 | A functional check failed (only with `--functional`). |
| 64 | Invalid arguments, `OCI_REGION`, missing tenancy settings, manifest errors (including paths outside allowed roots), or invalid checks input. |

## Limitations

This initial skill supports the verified OC1 public endpoint form only. It does
not support private endpoints, OCI IAM-authenticated applications, bearer-token
authentication, redirects, custom business probes, or endpoint invocation with
request bodies.
