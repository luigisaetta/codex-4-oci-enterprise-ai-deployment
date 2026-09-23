---
name: oci-agent-build
description: Build, rebuild, or verify a linux/amd64 agent container image for OCI Enterprise AI hosted deployment. Use when asked to build or verify an agent image; this skill does not push images or deploy resources.
---

# OCI Agent Build

## Purpose and when to use

Produce and verify a local `linux/amd64` image when asked to build, rebuild, or
verify an agent container for OCI Enterprise AI. The supplied manifest selects
the agent; `hello_world` is a documented example and regression fixture, not a
default workload.

## Prerequisites

Read [container requirements](references/container-requirements.md).
Locate the checkout containing this skill by resolving any discovery symlink;
repository scripts are at `../../scripts/` relative to this skill directory.
Run commands from that checkout's root, including when using a user-scope symlink.
Require Bash 3.2+, Docker with a running daemon, buildx, curl, and a free host port.
Run `scripts/check_build_env.sh` (with `--builder NAME` when supplied) before
building. It checks advertised support; image execution establishes runtime behavior.

## Required inputs

* An agent manifest path, resolved from the repository root. Its build paths are
  also repository-root-relative; `context: .` therefore means the checkout root.
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
scripts/build_image.sh --manifest demos/hello_world/agent.yaml --tag 0.1.0
scripts/verify_image.sh --manifest demos/hello_world/agent.yaml --tag 0.1.0
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
| 1 | Required tool, daemon, or selected builder unavailable; restore access. |
| 2 | Builder does not advertise amd64; follow the runtime-specific guidance. |
| 3 | Invalid or forbidden tag; request a valid semantic version. |
| 4 | Invalid context or Dockerfile path; correct the input. |
| 5 | pip resolution failed; inspect the offending package/version line. |
| 6 | Other build failure, build timeout, or loaded-image inspection failure. |
| 10 | Image is unavailable or its platform is not exactly linux/amd64. |
| 11 | Runtime architecture command failed or did not return x86_64. |
| 12 | Container startup, health/readiness timeout, or cleanup failed. |
| 13 | Functional POST failed or returned a non-200 status. |
| 64 | Invalid arguments or timeout configuration; check script usage. |

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
