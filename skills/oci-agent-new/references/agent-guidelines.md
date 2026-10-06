# Agent guidelines

Defaults for new agents created with `oci-agent-new`, learned from real
releases. They support a spec-driven workflow:

* **Behavior defaults** (B rules) are written into the specification draft,
  each marked "(default)", so the developer sees and can change them. Code
  follows the approved specification only; never apply a B rule that the
  specification overrides or omits after review.
* **Code-quality rules** (Q rules) apply to the generated code directly,
  because they do not change what the agent does.

## Behavior defaults (into the specification)

**B1. Region.** The Hosted Application is deployed in the tool's `OCI_REGION`
(from the tool's `.env`). By default the agent calls OCI Generative AI in the
same region. Write both regions explicitly in the Deployment section, for
example "Deployment region: eu-frankfurt-1 (tool `.env`); LLM region:
eu-frankfurt-1 (default)". A different LLM region must be a deliberate choice
in the specification.
*Why:* a deployment in one region calling an LLM in another caused confusion.

**B2. Runtime variables.** Use `GENAI_MODEL`, `GENAI_REGION` (literal `value`
in the manifest), and `GENAI_API_KEY` (`from_env`). The developer keeps the key
in the tool's `.env` or exports it; the agent code reads only the environment
variable. Never name an agent variable like a tool tenancy key (`OCI_REGION`,
`OCI_COMPARTMENT_NAME`, `OCIR_*`).
*Why:* the tool exports its own `OCI_REGION`; `from_env: OCI_REGION` silently
took the tool's value.

**B3. HTTP status codes.** 200 for a completed request, including a business
rejection with its reason; 400 for invalid or missing input; 502 when an
external service (for example the LLM) fails or returns unusable data. Every
response uses the same JSON schema.

**B4. Ambiguous requests.** When a request matches several items (for
example "iPhone" in a catalog with many iPhone models), reply that the request
is ambiguous and list a few candidates; never answer "not found".
*Why:* exact-name matching answered "not in the catalog" for products that
were in it.

**B5. Functional checks.** At least one check is deterministic and does not
call the LLM (for example empty input → 400). Checks that call the LLM assert
only stable fields, such as `status`.
*Why:* checks that depend on the model are slow and not repeatable.

**B6. Packaged data.** Data files (catalogs, simulated stock) live inside the
agent package, for example `<package>/data/`, and are read relative to the
module; they are read-only. Simulated state that changes is kept in memory and
documented as lost on restart and not shared across replicas.

## Code-quality rules (into the code)

**Q1. LLM calls.** Use the OCI OpenAI-compatible endpoint
`https://inference.generativeai.<region>.oci.oraclecloud.com/openai/v1` with
the Responses API, and structured output with a Pydantic schema:

```python
result = client.responses.parse(
    model=model, input=message, instructions=instructions,
    text_format=Extraction, store=False,
)
```

Never parse JSON out of free text.

**Q2. Timeouts.** Create the LLM client with an explicit timeout (for example
20 to 30 seconds) and at most one retry, so that one request stays well below
the verifier's 60-second limit.

**Q3. Logging.** Log to stderr with `logging`: one line at startup, one line
for every error with its type and cause. Never log secrets, runtime variable
values, or the full user message. Never turn an exception into an error
response without logging it.

**Q4. Startup checks.** Validate required variables and data files at startup;
on failure `/ready` returns 503 and the cause is logged.

**Q5. Style.** Module header on every Python file, docstrings on public
functions and classes, lines under 100 characters, and HTTP handling
(`app.py`) separate from logic (`agent.py`).
