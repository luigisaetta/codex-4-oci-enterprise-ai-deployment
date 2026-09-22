# Spec 001: Codex skill `oci-agent-build`

Status: implemented; local acceptance criteria 1–7 passed; criterion 8 pending Codex UI verification.
Date: 2026-09-22.

## Problem

Deploying an agent to OCI Enterprise AI (hosted applications and hosted deployments in
OCI Generative AI) requires a container image built for `linux/amd64`. The local
development machine is an Apple Silicon Mac (arm64), so a plain `docker build` produces
an arm64 image that the target platform cannot run. Previous attempts failed because the
architecture constraint was not enforced by tooling and because pip compiled packages
from source under CPU emulation.

We need a Codex skill that makes the build step repeatable and self-checking: always
amd64, always verified, never dependent on the operator remembering flags.

## Scope

1. A Codex skill `oci-agent-build` under `skills/oci-agent-build/`, discoverable by Codex
   through a versioned symlink `.agents/skills -> ../skills`.
2. Build automation in `scripts/` that produces a `linux/amd64` image of an agent from a
   Dockerfile and a build context.
3. A verification step that proves the produced image is `linux/amd64` and that the
   container starts and answers the health endpoints required by the target platform.
4. Containerization of the existing demo `demos/hello_world/` (see `specs/hello_world.md`)
   as the reference workload for verifying the skill. The demo's Python code and tests
   are not modified.

## Non-goals (deferred to later specs)

- Pushing the image to OCI Container Registry (OCIR). Planned Spec 002.
- Creating hosted applications or hosted deployments on OCI. Spec 003.
- Provisioning a remote amd64 build VM on OCI and registering it as a buildx node. The
  build script must accept an optional `--builder <name>` so a remote builder can be
  plugged in later, but setting one up is out of scope.
- Connecting the demo agent to OCI Generative AI models. `hello_world` is offline and
  needs no credentials.
- Multi-architecture images. Only `linux/amd64` is produced.
- Creating any new demo agent.

## Target platform requirements (verified 2026-09-22)

Source: OCI documentation, "Preparing Container Images",
https://docs.oracle.com/en-us/iaas/Content/generative-ai/prepare-artifacts.htm

- Image platform must be `linux/amd64`. The documented build command is
  `docker buildx build --platform linux/amd64 -t <image>:<tag> .`
- The container must listen on host `0.0.0.0` and port `8080`.
- Readiness endpoint: `GET /ready` returns `200`. Liveness endpoint: `GET /health`
  returns `200`.
- The container file system is read-only except `/tmp`.
- Volume mapping is not supported. Containers must be stateless.
- Custom entry point commands are not supported. Define the command with `CMD` or
  `ENTRYPOINT` in the Dockerfile.

Record these in `skills/oci-agent-build/references/container-requirements.md` with the
source link and verification date. Do not paraphrase beyond what the source states.

## Existing demo: facts the implementation must respect

- Package layout: `demos/__init__.py`, `demos/hello_world/__init__.py`, `agent.py`,
  `app.py`. The app imports `demos.hello_world.agent`, so the image must contain the
  `demos` package and the application must be started from a working directory where
  `demos` is importable.
- Documented launch command: `python -m uvicorn demos.hello_world.app:app --host 0.0.0.0
  --port 8080`.
- Runtime dependencies are the root `requirements.txt` (FastAPI, LangGraph, Pydantic,
  Uvicorn, with version ranges). Development tools are in `requirements-dev.txt` and must
  not be installed in the image.
- Endpoints: `GET /health` returns 200 `{"status":"ok"}`; `GET /ready` returns 200
  `{"status":"ready"}` once the graph is compiled at startup, 503 before; `POST /hello`
  with `{"name":"Luigi"}` returns 200 `{"message":"Hello Luigi"}`.
- Existing tests: `tests/test_hello_world.py`, run with `pytest` from the repository root.

Consequence: the Docker build context is the repository root, and the Dockerfile lives in
`demos/hello_world/Dockerfile`. The build script must therefore accept the Dockerfile path
separately from the context.

## Assumptions

- Local environment: macOS on Apple Silicon, Docker CLI with buildx provided by Rancher
  Desktop or Docker Desktop. The Docker daemon runs in a Linux arm64 VM and supports
  `linux/amd64` through emulation. Scripts must detect this rather than assume it.
- Shell scripts run under bash. macOS ships bash 3.2, so scripts must avoid bash 4+
  features (no associative arrays, no `${var,,}`) and must start with
  `#!/usr/bin/env bash` and `set -euo pipefail`.
- Emulated builds are slow. Timeouts must be generous and configurable.
- Python 3.11+ inside the image. Conda is not available in the target runtime.

## Intended behavior

### Repository layout to create or modify

```
.agents/skills -> ../skills                (symlink, committed)
.dockerignore                              (repository root, since the root is the build context)
skills/README.md                           (index; how to make skills available to Codex)
skills/oci-agent-build/SKILL.md
skills/oci-agent-build/agents/openai.yaml
skills/oci-agent-build/references/container-requirements.md
skills/oci-agent-build/assets/Dockerfile.template
skills/oci-agent-build/assets/dockerignore.template
scripts/check_build_env.sh
scripts/build_image.sh
scripts/verify_image.sh
demos/hello_world/Dockerfile               (new; derived from the template)
demos/hello_world/README.md                (add a "Container build" section only)
CHANGELOG.md                               (entry under Unreleased, dated)
```

Do not modify `demos/hello_world/agent.py`, `app.py`, `__init__.py`, `tests/`,
`requirements.txt`, or `specs/hello_world.md`.

### `scripts/check_build_env.sh`

Purpose: fail fast with an actionable message before any build starts.

Checks, in order:
1. `docker` is on PATH and the daemon answers `docker info`.
2. `docker buildx version` succeeds.
3. The selected builder (default builder, or `--builder <name>` if given) lists
   `linux/amd64` among its platforms in `docker buildx inspect`. If missing, print how to
   enable emulation for the detected runtime and exit non-zero.
4. Print a one-line summary: Docker version, builder name, daemon architecture, whether
   amd64 is native or emulated.

Exit codes: 0 ok, 1 missing tool, 2 amd64 platform unavailable.

### `scripts/build_image.sh`

Usage:
`build_image.sh --context <dir> --dockerfile <path> --name <image-name> --tag <tag> [--builder <name>] [--no-cache]`

Behavior:
- Refuse the tag `latest` and any tag that is not `MAJOR.MINOR.PATCH` with an optional
  `-suffix`. Print the reason and exit 3.
- Refuse to run if `<path>` does not exist or `<dir>` is not a directory. Exit 4.
- Warn (do not fail) if `<dir>/.dockerignore` is missing.
- Run `check_build_env.sh` with the same `--builder` argument; propagate its exit code.
- Run exactly:
  `docker buildx build --platform linux/amd64 --load --provenance=false --sbom=false -f <path> -t <name>:<tag> [--builder <name>] [--no-cache] <dir>`
  The attestation flags apply the manifest-list exception documented below.
  Print the full command before running it.
- On success print image name, tag, image ID, and size.
- On failure, if the build log contains pip's "No matching distribution found" or
  "Could not find a version that satisfies", print the offending package line and a hint:
  the package has no `manylinux x86_64` wheel; use a remote amd64 builder or a base image
  with build tools. Exit 5. Any other build failure exits 6.

Never modify the Dockerfile. Never fall back to another platform.

### `scripts/verify_image.sh`

Usage:
`verify_image.sh --image <name>:<tag> [--port 8080] [--timeout-seconds 90] [--post-path <path> --post-body <json>]`

Steps, all mandatory unless marked optional, stop at first failure:
1. Confirm that the Docker daemon answers `docker info`; otherwise exit 1.
2. Static check: `docker image inspect --format '{{.Os}}/{{.Architecture}}'` must print
   exactly `linux/amd64`. Otherwise exit 10 with the observed value.
3. Runtime architecture check: `docker run --rm --platform linux/amd64 <image> uname -m`
   must print `x86_64`. Otherwise exit 11. If the image has no `uname`, report it as
   skipped with a warning, not as a failure.
4. Smoke test: start the container detached with `--read-only --tmpfs /tmp
   -p <host-port>:8080`, so the run mirrors the target read-only filesystem. Poll
   `GET http://127.0.0.1:<host-port>/health` and `/ready` until both return 200 or the
   timeout expires. A 503 from `/ready` during startup is expected and must be retried,
   not treated as failure. Print the container logs on failure. Exit 12 on timeout.
5. Optional functional check: if `--post-path` is given, send `--post-body` as JSON to
   that path and require HTTP 200. Print the response body. Exit 13 on any other status.
6. Always stop and remove the container, also on failure (use `trap`).
7. Print a final report: image, digest, architecture, readiness time in seconds, result.

Exit 0 only when all steps pass.

### `demos/hello_world/Dockerfile` and `assets/Dockerfile.template`

The template has placeholders for the application module (for example
`{{APP_MODULE}}`, value `demos.hello_world.app:app`) and the package directory to copy
(`{{PACKAGE_DIR}}`, value `demos`). The hello_world Dockerfile is the template with the
placeholders filled in, plus nothing else. Both must:

- use the official `python:3.11-slim` base with no platform hard-coded in `FROM`
  (platform comes from the build flag);
- set `PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1`, so a read-only filesystem
  does not trigger bytecode write attempts;
- copy the root `requirements.txt` and run
  `pip install --no-cache-dir --only-binary=:all: -r requirements.txt`, so that no
  package is compiled from source under emulation;
- copy only the `{{PACKAGE_DIR}}` package into `/app`, set `WORKDIR /app`, so that
  `demos` is importable;
- create and switch to a non-root user;
- `EXPOSE 8080` and set `CMD ["python", "-m", "uvicorn", "{{APP_MODULE}}", "--host",
  "0.0.0.0", "--port", "8080"]`.

The root `.dockerignore`, derived from `assets/dockerignore.template`, must exclude at
least `.git`, `.agents`, `__pycache__`, `*.py[cod]`, `.pytest_cache`, `.venv`, `.env`,
`.env.*`, `tests`, `specs`, `skills`, `scripts`, `docs`, `*.md`, `LICENSE`,
`requirements-dev.txt`, `pyproject.toml`.

Add a "Container build" section to `demos/hello_world/README.md` showing the two script
invocations from the acceptance criteria and pointing to the skill. Keep the rest of the
README unchanged.

### `skills/oci-agent-build/SKILL.md`

Frontmatter: `name: oci-agent-build`; `description` states that the skill builds and
verifies a `linux/amd64` container image of an agent for OCI Enterprise AI hosted
deployment, to be used when asked to build, rebuild, or verify an agent image, and that it
does not push or deploy.

Body sections: purpose, when to use, prerequisites (pointing to `check_build_env.sh`),
required inputs (build context, Dockerfile path, image name, semantic version tag; ask
the user if the tag is missing, never invent one), workflow (run build script, then verify
script, in that order), how to interpret the documented exit codes, expected outputs,
limitations, and a link to `references/container-requirements.md`. Use `hello_world` as
the worked example. Keep it under roughly 120 lines. Instruct Codex never to remove the
`--only-binary` constraint or change the platform to work around a failure; it must
report the failure instead.

`agents/openai.yaml`: `interface.display_name: "OCI Agent Build"`, a short description,
`policy.allow_implicit_invocation: true`.

### `skills/README.md`

Explain the two verified mechanisms to make skills available to Codex: the repository
symlink `.agents/skills -> ../skills` (Codex scans `.agents/skills` from the working
directory up to the repository root and follows symlinks) and per-skill symlinks into
`$HOME/.agents/skills/` for use from other repositories. Source:
https://learn.chatgpt.com/docs/build-skills (verified 2026-09-22). State that placing a
skill under `skills/` alone does not make it visible without one of these mechanisms.

## Acceptance criteria

All commands run from the repository root.

1. `scripts/check_build_env.sh` exits 0 on the local Mac and reports amd64 as emulated.
2. `scripts/build_image.sh --context . --dockerfile demos/hello_world/Dockerfile --name hello-world --tag 0.1.0`
   exits 0 and produces an image.
3. The same command with `--tag latest` exits 3 without invoking docker build.
4. `scripts/verify_image.sh --image hello-world:0.1.0 --post-path /hello --post-body '{"name":"Luigi"}'`
   exits 0; its report shows `linux/amd64` and `x86_64`, and the functional check
   returns `{"message":"Hello Luigi"}`.
5. Building the same Dockerfile for `linux/arm64` by hand (for example with tag
   `0.1.0-arm64test`) and running `verify_image.sh` on it exits 10. This proves the check
   is real. Remove the test image afterwards.
6. `pytest` still passes with no changes to `tests/` or to the demo's Python files, and
   without Docker, network, or credentials.
7. Black and Pylint pass on any Python files touched or added (none are expected).
   `bash -n` passes on all scripts.
8. From Codex, with the repository open, `$oci-agent-build` is listed and, when asked to
   "build and verify the hello_world image with tag 0.1.0", Codex runs the two scripts in
   order and reports the verify summary without editing the Dockerfile.

## Verification record

All results below are local to this Mac on 2026-09-22. Nothing was run on OCI.

Step 1 static checks on 2026-09-22: the `.agents/skills` symlink resolves to
`../skills`; the Dockerfile's build inputs exist; all protected Python files, tests,
root `requirements.txt`, and `specs/hello_world.md` match HEAD. Removing only the
new "Container build" section reproduces the previous demo README exactly.
`git diff --check` passed. No Python files were changed, so Python checks are
deferred to the acceptance run. No images were built or containers started.
These were the observations at step 1; subsequent results follow.

| Criterion | Result | Date | Notes |
| --- | --- | --- | --- |
| 1 | PASS | 2026-09-22 | Exit 0; Docker server 29.5.2, builder rancher-desktop, daemon aarch64, amd64=emulated. |
| 2 | PASS | 2026-09-22 | Exit 0. First build: 48 s under emulation. Final build with attestation flags and cached layers: 1 s. Python 3.11.16; FastAPI 0.141.1, LangGraph 1.2.12, Pydantic 2.13.5, Uvicorn 0.53.0. Full package inventory below. |
| 3 | PASS | 2026-09-22 | Exact acceptance command with latest exited 3. A temporary Docker fixture also proved no build invocation occurs for that tag. |
| 4 | PASS | 2026-09-22 | Exit 0; linux/amd64, x86_64; readiness 5 s; POST returned {"message":"Hello Luigi"}. Container ran read-only with /tmp tmpfs and was removed. |
| 5 | PASS | 2026-09-22 | Built hello-world:0.1.0-arm64test with linux/arm64; verifier exited 10 before runtime checks. Removed the test image successfully. |
| 6 | PASS | 2026-09-22 | 8 pytest tests passed in the project Conda environment, without Docker/network/credentials. One existing Starlette/AnyIO deprecation warning. Python, tests, requirements.txt, and specs/hello_world.md unchanged. |
| 7 | PASS | 2026-09-22 | /bin/bash 3.2.57 -n passed for all three scripts. No Python files were touched or added, so Black/Pylint applicability is N/A for this change. |
| 8 | pending | | The symlink and skill metadata validate statically, but selection and invocation through the Codex UI have not been observed. |

### Local image and environment

* Docker client 29.5.3-rd; buildx v0.34.1; BuildKit v0.30.0; Rancher Desktop
  context; server 29.5.2 on Alpine Linux v3.23/aarch64. Host is macOS arm64.
* Final image `hello-world:0.1.0`, ID/digest
  `sha256:45533f02a491be15c28d8be4446bef7e65db057c5be482e1b9de1a1fa5fdf363`.
  Docker reports repository digest
  `hello-world@sha256:45533f02a491be15c28d8be4446bef7e65db057c5be482e1b9de1a1fa5fdf363`;
  this is local metadata, not evidence of a registry push.
* Descriptor media type: `application/vnd.docker.distribution.manifest.v2+json`.
  Reported size: 65,620,316 bytes. Runtime UID: 10001. Python: 3.11.16.
* Base image used: `python:3.11-slim` resolving to
  `sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9`.
* Local tests used Python 3.11.0 in `codex-4-oci-enterprise-ai-deployment`.
  OCI SDK/CLI were not needed or used.

The ARM64 negative-control build used:

```bash
docker buildx build --platform linux/arm64 --load --provenance=false --sbom=false -f demos/hello_world/Dockerfile -t hello-world:0.1.0-arm64test .
scripts/verify_image.sh --image hello-world:0.1.0-arm64test
docker image rm hello-world:0.1.0-arm64test
```

Additional checks: 24 temporary fixture scenarios were manually executed under Bash
3.2 on 2026-09-22, covering preflight failures, invalid arguments/tags/paths, builder
flag forwarding, missing wheels, build failure/timeout, runtime architecture errors,
missing `uname`, startup failure, readiness retries/timeouts, POST failure, and cleanup
failure. The fixtures were temporary and were not retained in the repository; this
evidence is therefore not reproducible. No files under `tests/` were changed. Rendered
templates match the Dockerfile and root `.dockerignore`
byte-for-byte. No smoke containers remained after verification.

### Installed image packages

Observed using `importlib.metadata.distributions()` in the final image under a
read-only filesystem with writable `/tmp`. This inventory includes base-image
packaging tools; no development requirements were installed.

```text
PyYAML==6.0.3
annotated-doc==0.0.5
annotated-types==0.8.0
anyio==4.15.1
certifi==2026.7.22
charset-normalizer==3.5.1
click==8.5.0
distro==1.9.0
fastapi==0.141.1
h11==0.16.0
httpcore2==2.13.0
httpcore==1.0.9
httpx2==2.13.0
httpx==0.28.1
idna==3.20
jsonpatch==1.33
jsonpointer==3.1.1
langchain-core==1.6.4
langchain-protocol==0.0.19
langgraph-checkpoint==4.2.0
langgraph-prebuilt==1.1.0
langgraph-sdk==0.4.5
langgraph==1.2.12
langsmith==0.14.0
orjson==3.12.0
ormsgpack==1.12.2
packaging==26.3
pip==24.0
pydantic==2.13.5
pydantic_core==2.46.5
requests-toolbelt==1.0.0
requests==2.34.2
setuptools==79.0.1
sniffio==1.3.1
starlette==1.6.0
tenacity==9.1.4
truststore==0.10.4
typing-inspection==0.4.4
typing_extensions==4.16.0
urllib3==2.8.0
uuid_utils==0.17.1
uvicorn==0.53.0
websockets==16.1.1
wheel==0.46.3
xxhash==4.0.1
zstandard==0.25.0
```

## Decisions and open points

- Step 1 ordering: the requested Dockerfile and root `.dockerignore` precede the
  templates scheduled for step 3. They are authored from this spec's explicit
  requirements at step 1. Resolved at step 3: the Dockerfile matches substitution
  of `{{APP_MODULE}}` with `demos.hello_world.app:app` and `{{PACKAGE_DIR}}` with
  `demos`, and `.dockerignore` matches its template exactly.
- Step 1 discovery: the repository symlink can be checked as a filesystem link,
  but discovery of an invocable skill requires a Codex skill-selector check.
  The official discovery documentation was reviewed in this session on 2026-09-22:
  https://learn.chatgpt.com/docs/build-skills.
- User-approved clarification (2026-09-22): malformed arguments exit 64;
  unavailable tools, daemon, or builder exit 1; smoke container startup or timeout
  failures exit 12. Build timeout is `BUILD_TIMEOUT_SECONDS`, default 1800 seconds;
  expiration is a build failure (6). A cleanup failure must not report success (12).
- User-approved clarification (2026-09-22): phrase the missing-wheel explanation
  as a possible cause, because pip's messages may instead indicate unavailable
  versions. Keep `--only-binary` mandatory. Remote builders/build tools cannot
  compile source under this policy; any source-build policy needs a separate decision.
- A local `--load` image may not have a repository digest. Report it as unavailable
  rather than relabeling the image configuration ID as a registry manifest digest.
- The preflight native/emulated label is inferred from the current daemon's
  architecture, not proof of the architecture of an optional remote builder host.

- Pip is restricted to binary wheels by design. A missing x86_64 wheel is reported
  without a fallback. The user-approved clarification above supersedes the earlier
  suggestion that a remote builder alone would fix a source-only dependency.
- The image is tagged with a local name only. The OCIR repository path will be added in
  planned Spec 002, where tagging and pushing are defined together.
- The root `requirements.txt` uses version ranges. The image therefore resolves versions
  at build time. Record the versions actually installed in the verification table. A
  lock file for reproducible images is a candidate for a later spec.
- Resolved on 2026-09-22: the initial 48-second build produced
  `Descriptor.mediaType=application/vnd.oci.image.index.v1+json`, observed with
  `docker image inspect hello-world:0.1.0`. Following the exception already allowed
  by this spec, the build command now includes `--provenance=false --sbom=false`.
  The initial image ID was `sha256:547666f7369cad7fd9e16a4868815305d1f384194ee0d26cb4bf9863784c8514`.
