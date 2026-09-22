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

## Troubleshooting and cleanup

If imports fail, check that the project environment is active and dependencies
are installed. Run Uvicorn from the repository root. If port 8080 is occupied,
stop the existing server or explicitly select another port with `--port`.

Stop the server with Ctrl+C. The demo creates no cloud resources or persistent
state. See the [specification](../../specs/hello_world.md) for verification details.
