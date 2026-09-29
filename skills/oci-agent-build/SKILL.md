---
name: oci-agent-build
description: Build or verify a linux/amd64 container image for OCI Generative AI Hosted Applications, not OCI AI Data Platform (AI DP) code-first agents. It does not push images or deploy resources.
---

# OCI Agent Build

## Purpose and when to use

Produce and verify a local `linux/amd64` image when asked to build, rebuild, or
verify an agent container for OCI Enterprise AI. The supplied manifest selects
the agent; `hello_world` is a documented example and regression fixture, not a
default workload.

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

Read [container requirements](references/container-requirements.md).
In Bash require Bash 3.2+, Docker with a running daemon, buildx, curl, and a free
host port. In PowerShell 7.4+ require Docker Desktop or Podman, selected with
`-ContainerEngine Auto|Docker|Podman`; `-Builder` is Docker-only.
Run `"$TOOL_HOME/scripts/check_build_env.sh"` (with `--builder NAME` when supplied) before
building. It checks advertised support; image execution establishes runtime behavior.

## Shell selection

The examples below are Bash. From PowerShell 7.4+ run the matching PowerShell twin
with the same option names in `-Option` form (`--timeout-seconds` becomes
`-TimeoutSeconds`); outputs and exit codes are identical. Follow the shell in
use, never the operating system, and do not mix the two families in one release.
Rule and mapping table: [Choosing Bash or PowerShell](../README.md#choosing-bash-or-powershell).

## Required inputs

* An agent manifest path. Its build paths are relative to the manifest folder;
  `context: .` therefore means that folder.
  If the current request does not name it, ask: “Which agent manifest should I
  use?” before inspecting Docker or running any command. Never choose a demo,
  scan for a manifest, or infer one from conversation history. “Use the same
  agent/manifest as the immediately preceding step” is an explicit selection.
* A semantic version tag (`MAJOR.MINOR.PATCH`, optional `-suffix`).
  Ask the user if the tag is missing; never invent one or use `latest`.
* Optional builder name and `--no-cache` for builds.
* Optional host port, readiness timeout, and a POST path/body pair for verification.

## Workflow

1. Confirm the context, Dockerfile, image name, and user-supplied tag. Inspect the
   context's `.dockerignore` and Dockerfile. Explain any required correction before
   making it; scripts never modify the Dockerfile.
2. Run the build script, then the verify script, in that order. Stop on build
   failure. For a verify-only request, verify the already-existing local image.
3. Report build and verification results, exit codes, architecture, readiness time,
   and any missing registry digest or skipped runtime check. Do not claim OCI
   compatibility from a local smoke test alone.

Example with a user-supplied tag of `0.1.0`:

```bash
"$TOOL_HOME/scripts/build_image.sh" --manifest /path/to/agent/agent.yaml --tag 0.1.0
"$TOOL_HOME/scripts/verify_image.sh" --manifest /path/to/agent/agent.yaml --tag 0.1.0
```

The manifest verifier checks the configured response status and JSON subset.
It also injects `runtime.env` literal and `from_env` variables into the local
container. A Vault entry is skipped unless `OCI_AGENT_VAULT_<VARIABLE_NAME>` is
set in the operator environment; the override is never displayed.
Pass `--builder NAME` to the build script to use an existing selected builder;
provisioning a builder is outside this skill. `BUILD_TIMEOUT_SECONDS` controls build
time (default 1800). Verification accepts `--port` (8080) and
`--timeout-seconds` (90); increase the latter explicitly for slow startup.

## Exit codes

| Code | Meaning and action |
| --- | --- |
| 0 | Operation passed; inspect the report for warnings or skipped checks. |
| 1 | Python with PyYAML, a required tool, daemon, or selected builder is unavailable; restore access. |
| 2 | Builder does not advertise amd64; follow the runtime-specific guidance. |
| 3 | Invalid or forbidden tag; request a valid semantic version. |
| 4 | Invalid context or Dockerfile path; correct the input. |
| 5 | pip resolution failed; inspect the offending package/version line. |
| 6 | Other build failure, build timeout, or loaded-image inspection failure. |
| 10 | Image is unavailable or its platform is not exactly linux/amd64. |
| 11 | Runtime architecture command failed or did not return x86_64. |
| 12 | Container startup, health/readiness timeout, or cleanup failed. |
| 13 | Functional POST failed or returned a non-200 status. |
| 64 | Invalid arguments, timeout configuration, manifest errors (including paths outside allowed roots), or invalid checks input; correct the input. |

Signals return 130 (interrupt) or 143 (termination) after cleanup.

## Expected outputs

Build: full command, build log streamed as produced, elapsed seconds, image name/tag,
ID and size.
Builds disable provenance and SBOM attestations as required by the observed local
manifest-index behavior recorded in Spec 001.
Verify: optional POST body and final report with image, digest availability,
static/runtime architecture, readiness seconds, and PASS/FAIL. Failed smoke tests
print container logs. The verifier removes its container; the image stays local.

## Limitations

Never remove `--only-binary` or change the platform to work around a failure.
Report the failure. Missing-wheel messages may also indicate unavailable versions;
a remote builder cannot compile source under this binary-only policy.
The preflight mode is inferred from the current daemon architecture; a remote
builder can use a different host, so do not treat that inference as remote evidence.
If `uname` is demonstrably absent, verification warns and skips that check.
Local images may have no registry digest; report it as unavailable.
Dependency ranges resolve at build time. Templates in `assets/` are starting points;
the hello_world Dockerfile must remain their exact rendered form.
No pushes, registry login, OCI mutations, platform fallback, or remote provisioning.
