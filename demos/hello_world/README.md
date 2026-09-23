# hello_world

A deterministic LangGraph agent served by FastAPI. The graph follows
`START → greet → END` and produces `Hello <name>` without an LLM or credentials.

## Setup and execution

Prerequisites: Python 3.11+, the project Conda environment, and a free port 8080.
Run these commands from the repository root:

```bash
conda activate codex-4-oci-enterprise-ai-deployment
python -m pip install -r requirements.txt
python -m uvicorn demos.hello_world.app:app --host 0.0.0.0 --port 8080
```

The server listens on all interfaces on port 8080. No `.env` settings are required.
Outside Conda, use a Python 3.11+ environment and the same installation and server
commands. OCI Enterprise AI runtime compatibility still needs remote verification.

## API

```bash
curl -sS -X POST http://localhost:8080/hello \
  -H 'Content-Type: application/json' \
  -d '{"name": "Luigi"}'
```

Expected response: `{"message":"Hello Luigi"}` (HTTP 200).
Surrounding whitespace is removed from the name. Missing, blank, or non-string
names return HTTP 422.

```bash
curl -sS http://localhost:8080/health
curl -sS http://localhost:8080/ready
```

`/health` returns `{"status":"ok"}` (HTTP 200). `/ready` returns
`{"status":"ready"}` (HTTP 200) once the graph has been initialized; if the graph
is unavailable it returns HTTP 503. Greeting requests also require readiness.
Interactive API documentation is available at `http://localhost:8080/docs`.

## Development

From the repository root, install the development tools and run:

```bash
python -m pip install -r requirements-dev.txt
python -m black demos tests
python -m pylint demos tests
python -m pytest
```

## Container build

Run from the repository root with Docker, a running daemon, buildx, and a builder
supporting `linux/amd64`. The root is the build context so the image can install
the root `requirements.txt` and import the complete `demos` package.

Build and verify using the scripts defined in
[Spec 001](../../specs/001-skill-oci-agent-build.md):

```bash
scripts/build_image.sh --context . --dockerfile demos/hello_world/Dockerfile --name hello-world --tag 0.1.0
scripts/verify_image.sh --image hello-world:0.1.0 --post-path /hello --post-body '{"name":"Luigi"}'
```

On Windows, first open **PowerShell 7.2+** (`pwsh`), rather than legacy Windows
PowerShell 5.1, and check the version with `$PSVersionTable.PSVersion`. Choose
Docker Desktop or Podman; `Auto` selects an engine only when exactly one usable
engine is found. (Rancher Desktop may work through its `docker` CLI but is not
yet acceptance-tested.) Then use the matching native commands:

```powershell
.\scripts\build_image.ps1 -Context . -Dockerfile demos/hello_world/Dockerfile -Name hello-world -Tag 0.1.0 -ContainerEngine Auto
.\scripts\verify_image.ps1 -Image hello-world:0.1.0 -ContainerEngine Auto -PostPath /hello -PostBody '{"name":"Luigi"}'
```

The result is a local `hello-world:0.1.0` image for `linux/amd64`, followed
by architecture and HTTP verification on port 8080. On Windows, verification
publishes only to `127.0.0.1:8080` to avoid IPv4/IPv6 loopback ambiguity and
does not expose the development server on the LAN. Verification runs with a
read-only filesystem and writable `/tmp`, requires HTTP 200 from the functional
request, and prints its response body. OCI deployment is outside this workflow.

The image uses Python 3.11, binary wheels only, and a non-root user. Its command
starts Uvicorn on `0.0.0.0:8080`. Dependency versions are resolved from the existing
root requirements at build time. Builds download the base image and Python packages;
no registry push or OCI deployment is performed.

See [oci-agent-build](../../skills/oci-agent-build/SKILL.md) for the workflow and
the [skill index](../../skills/README.md) for discovery instructions. Set
`BUILD_TIMEOUT_SECONDS` to override the 1800-second build timeout; pass
`--timeout-seconds` to override the verifier's 90-second readiness timeout.
The verification script removes its test container; the built image remains local. To remove the
image when no longer needed, run `docker image rm hello-world:0.1.0`. On
Windows/Podman, use `podman image rm hello-world:0.1.0`.

## Troubleshooting and cleanup

If imports fail, check that the project environment is active and dependencies
are installed. Run Uvicorn from the repository root. If port 8080 is occupied,
stop the existing server or explicitly select another port with `--port`.

Stop the server with Ctrl+C. The demo creates no cloud resources or persistent
state. See the [specification](../../specs/hello_world.md) for verification details.
