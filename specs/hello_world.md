# Hello world agent

## Scope and assumptions

Provide a deterministic LangGraph agent in `demos/hello_world/`, wrapped by
FastAPI and served with Uvicorn on port 8080. Python 3.11+ is required. No LLM,
credentials, external API calls, persistence, or OCI resources are needed.
OCI deployment, authentication, and container packaging are outside this change.

## Behavior and acceptance criteria

* `POST /hello` accepts JSON `{"name": "Luigi"}` and returns HTTP 200 with
  `{"message": "Hello Luigi"}`. Each request executes a compiled LangGraph
  workflow: START → greet → END.
* Names must be strings, are trimmed, and must contain at least one character
  after trimming. Missing, null, non-string, or blank names produce HTTP 422.
* `GET /health` returns HTTP 200 with `{"status": "ok"}` for a running app.
* The graph is compiled during application startup and released on shutdown.
  `GET /ready` returns HTTP 200 with `{"status": "ready"}` when it is available,
  otherwise HTTP 503. Greeting requests also return 503 if not ready.
* Independent requests must not share greeting state.
* The documented launch command binds to `0.0.0.0:8080`.

## Verification approach

Use FastAPI TestClient to exercise the real graph, input validation, independent
requests, and readiness before startup and after shutdown. Run Black, Pylint,
and pytest in the project Conda environment. Perform a local HTTP smoke test on
port 8080. Record exact installed versions and results below. No remote mutation
or cleanup is required; stop the local server to release the port.

## Authoritative references

Reviewed on 2026-09-22:

* [LangGraph StateGraph](https://reference.langchain.com/python/langgraph/graph/state): graph construction, compilation, and invocation.
* [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/): startup and shutdown lifecycle.
* [FastAPI request bodies](https://fastapi.tiangolo.com/tutorial/body/): model-based JSON input validation.

## Verification results

Verified locally on 2026-09-22 using macOS arm64 and Python 3.11.0 in the
`codex-4-oci-enterprise-ai-deployment` Conda environment.

Installed versions: LangGraph 1.2.12, FastAPI 0.141.1, Pydantic 2.13.5,
Uvicorn 0.53.0, HTTPX 0.28.1, Black 26.5.1, Pylint 4.0.8, pytest 9.1.1.
OCI SDK and CLI are not used by this demo.

* `python -m black demos tests`: completed successfully.
* `python -m pylint demos tests`: passed, 10.00/10. The sandbox prevented writing
  Pylint's optional cache; analysis completed successfully.
* `python -m pytest -q`: 8 passed. A third-party Starlette/AnyIO deprecation
  warning was emitted by TestClient.
* Uvicorn bound to `0.0.0.0:8080`; real HTTP requests to `/health`, `/ready`,
  and `POST /hello` returned 200 with the expected JSON. Socket access required
  running outside the restricted sandbox. The test server was stopped afterward.

OCI Enterprise AI compatibility remains unverified until a target runtime is
selected and tested separately. No remote resources were created.
