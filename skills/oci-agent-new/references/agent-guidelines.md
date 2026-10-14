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
in the manifest), and `GENAI_AUTH_MODE`:

* `api_key` (default): `GENAI_API_KEY` with `from_env`. The developer keeps the
  key in the tool's `.env` or exports it; the agent code reads only the
  environment variable.
* `resource_principal`, when the specification asks for it (no secret; the
  recommended choice for production): `GENAI_PROJECT_ID`, the OCID of a
  Generative AI project in `GENAI_REGION`, as a literal `value`. Write in the
  specification the project and the runtime policies of
  `docs/iam-policies.md` in the tool checkout.

`GENAI_PROJECT_ID` is recommended in `api_key` mode too, and passed when set.
Never name an agent variable like a tool tenancy key (`OCI_REGION`,
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
only stable fields, such as `status`. An agent with a database (B9) also has
a remote-only check (`local: false`) of `GET /ready` with
`expect_json: {database: ready}`.
*Why:* checks that depend on the model are slow and not repeatable; without
the `/ready` check, an application created without its database would pass the
remote verification.

**B6. Packaged data.** Data files (catalogs, simulated stock) live inside the
agent package, for example `<package>/data/`, and are read relative to the
module; they are read-only. Simulated state that changes goes to the database
when the agent has one (B9); otherwise it is kept in memory and documented as
lost on restart and not shared across replicas.

**B7. Demo customer name.** The specification, code, LLM instructions,
examples, data, and checks name the customer only with the name approved for
demos (`tool_config.py demo-customer`, default `Supremo`). The real
customer's name stays in the conversation and never reaches a file (Spec 020).
*Why:* the files are shown during demos and may be shared.

**B8. Asynchronous agents.** Use the asynchronous contract of
[Spec 024](../../../specs/024-asynchronous-agents.md) when the agent runs more
than one LLM call per request, or a request can take more than about 20
seconds. Write it into the specification **in plain words** for the reader,
for example: "The request is accepted at once with a job reference; the work
continues afterwards. While a step is in progress, the status shows it as
running; when it ends, the next step starts. When all steps end, the status
shows the result." Never write implementation terms (`asyncio`, background
tasks, threads) in the specification. The contract:

* `POST /<path>` checks the input at once (400 with the B3 schema), then
  answers **202** with `{"job_id", "status": "queued", "steps"}`;
* `GET /<path>/{job_id}` answers 200 with `job_id`, `status` (`queued`,
  `running`, `completed`, `failed`), every step with its `name` and `status`,
  `result` when completed, and `error` (`code`, business `message`) when
  failed; 404 for an unknown or expired job; 429 for too many jobs;
* at most 10 jobs at a time; a finished job can be read for 30 minutes;
* a failed step ends the job with a business message;
* `deploy.scaling: {min_replicas: 1, max_replicas: 1}` in the manifest
  ([Spec 023](../../../specs/023-replica-scaling-at-creation.md)): the jobs
  are kept by one replica;
* functional checks: the deterministic one (B5) sends an invalid start
  request and expects 400; the full job is a polling check (`poll`), with
  `local: false` when the agent uses Resource Principal, which works only in
  OCI.

Write the steps in the specification's **Steps** section, with a sentence
each on what the step does for the user. Implementation: Q7.
*Why:* a request with several LLM calls exceeds the 60-second limit of the
verifier and the gateway's timeouts; one replica keeps the jobs reachable.

**B9. Saved data.** Use the managed Oracle database
([Spec 026](../../../specs/026-managed-adb-storage-at-creation.md),
[Spec 027](../../../specs/027-agents-with-a-database.md)) when the
specification says that the agent keeps data between requests: a catalog in
the database, or results that must be saved. Add `deploy.storage: {type: ADB}`
to the manifest. Write in the specification's **Data** section each table in
business terms: what it holds, who writes it (seed or agent), and whether it
changes. Defaults:

* catalogs (for example parts, plants, suppliers) are packaged files in
  `<package>/data/` (B6), loaded into the database at startup; the files are
  the source of truth, so a new version with new files updates the catalog;
* records produced by the agent (for example orders) are saved in the same
  request that produces them, and the response returns their identifier;
* the data survives new versions and restarts and is shared by all replicas;
  it is **lost when the application is deleted**, and the database cannot be
  reached from outside the agent;
* without the database (the local verification), the endpoints that need it
  answer 503 with the B3 schema and `error.code` `DATABASE_UNAVAILABLE`;
  input validation still answers 400 (B5).

Storage is set only when the application is created: an existing application
without it needs a new application name, which starts with an empty
database.
*Why:* a demo that records what it does loses it on every restart without a
database, and each replica keeps its own copy.

**B10. Reading saved records.** For each kind of saved record, add
`GET /<records>/{id}` (200 with the record, 404 when unknown) and
`GET /<records>?limit=<n>` (the most recent records, newest first; default 20,
at most 100). Identifiers have only letters, digits, `-`, and `_`; other
identifiers answer 404. The endpoints use the same access profile as the
business endpoint.
*Why:* the database is reachable only through the agent, so the developer and
the demo need a way to see what was saved.

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

Never parse JSON out of free text. Create the client with one function for
both authentication modes (`oci-genai-auth` and `httpx` in `requirements.txt`
for Resource Principal):

```python
import httpx
from oci_genai_auth import OciResourcePrincipalAuth
from openai import OpenAI


def make_client(region: str, mode: str, project: str, api_key: str = "") -> OpenAI:
    """Create the OCI Generative AI client for the selected auth mode."""
    base_url = f"https://inference.generativeai.{region}.oci.oraclecloud.com/openai/v1"
    if mode == "resource_principal":
        return OpenAI(
            base_url=base_url, api_key="not-used", project=project, max_retries=0,
            http_client=httpx.Client(auth=OciResourcePrincipalAuth(), timeout=20.0),
        )
    return OpenAI(base_url=base_url, api_key=api_key, project=project or None,
                  timeout=20.0, max_retries=0)
```

*Why:* verified live with Resource Principal on 2026-10-06 (Spec 016).

**Q2. Timeouts.** Create the LLM client with an explicit timeout (for example
20 to 30 seconds) and at most one retry, so that one request stays well below
the verifier's 60-second limit.

**Q3. Logging.** Log to stderr with `logging`: one line at startup, one line
for every error with its type and cause. Never log secrets, runtime variable
values, or the full user message. Never turn an exception into an error
response without logging it. The logs of a Hosted Application cannot be read
by the developer, so a 5xx response also carries a short technical code that
identifies the cause without sensitive data, for example the Oracle
`full_code` (`ORA-01745`, `DPY-6005`) at the end of `error.message`.
*Why:* in the live acceptance of Spec 027 the cause of a 503 was found only
when the response showed `[ORA-01745]`; the guesses before it were wrong.

**Q4. Startup checks.** Validate required variables and data files at startup;
on failure `/ready` returns 503 and the cause is logged. For agents with a
database, `/ready` also waits for the database (Q8). Never create or test
the LLM client at startup: create it at the first LLM call.
*Why:* `OciResourcePrincipalAuth()` needs the Resource Principal in its
constructor, which exists only in OCI; created at startup, it would make
`/ready` fail in the local verification. Locally, LLM calls in
`resource_principal` mode answer 502, which is expected; the deterministic
check (B5) keeps the build verification green.

**Q5. Style.** Module header on every Python file, docstrings on public
functions and classes, lines under 100 characters, and HTTP handling
(`app.py`) separate from logic (`agent.py`).

**Q6. Conversation history.** With the OCI Responses API, replay previous
assistant turns as assistant messages with `output_text` content, never as
plain strings:

```python
{"type": "message", "role": "assistant",
 "content": [{"type": "output_text", "text": previous_answer, "annotations": []}]}
```

*Why:* the service rejects an assistant turn sent as a string ("Invalid value:
'input_text'. Supported values are: 'output_text' and 'refusal'"); found in
two real agents in October 2026.

**Q7. Asynchronous implementation** (agents of B8). Keep the jobs in memory in
one place of `agent.py`, with their status and steps, and run each job as an
`asyncio` task started by the POST handler, so that the server keeps
answering the status requests. Update the step status before and after each
step. Give each step and the whole job a timeout (`asyncio.wait_for`); run
independent steps in parallel (`asyncio.gather`). Never block the event loop:
use `await asyncio.sleep`, not `time.sleep`, and the asynchronous LLM client
or `asyncio.to_thread` for blocking calls. Remove finished jobs after 30
minutes and refuse a new job beyond 10 running ones (429). Log the cause of a
failed step with the job identifier, never the input.

**Q8. Database access** (agents of B9). Put all database code in
`<package>/db.py`, separate from `agent.py`:

* `python-oracledb` in thin mode (no Oracle Client): `oracledb>=2.5,<4` in
  `requirements.txt`;
* the connect string from `DB_CONNECT_STRING` (or the manifest's
  `connect_env`); the user and password from the files `username` and
  `password` in `/mnt/secrets/adb/`, a directory overridable with
  `DB_SECRETS_DIR` for tests. Never log, return, or copy them, and never log
  the connect string;
* a small connection pool per replica (for example 1 to 4 connections),
  created in the startup event after the variable checks, never at import
  time. Without `DB_CONNECT_STRING`, create no pool and report
  `not_configured`;
* if the initialization (pool, schema, seed) fails, retry it in the
  background, for example every 30 seconds for up to 10 minutes, without
  blocking the event loop;
* `/ready` answers 503 until the pool, the schema (Q9), and the seed are
  ready, and reports `database`: `ready`, `unavailable`, or `not_configured`,
  and `database_error`: `{stage, type, code}` of the last failed attempt
  (`stage` one of `credentials`, `pool`, `schema`, `seed`; `code` the Oracle
  `full_code` only), or `null`. `not_configured` does not make `/ready` fail,
  so that the local verification runs without a database;
* short transactions: read what the request needs, close the transaction,
  call the LLM, then write in a second transaction and answer only after the
  commit. Never keep a connection during LLM calls;
* no blocking database calls in the event loop: use the asynchronous API of
  `python-oracledb` (`oracledb.create_pool_async`) or `asyncio.to_thread`;
* bind variables for every value; never build SQL text from request data.
  Never name a bind variable after an Oracle reserved word: `:number` failed
  with ORA-01745, and the same applies to other reserved words such as `DATE`
  or `LEVEL`. Use a prefix, for example `:p_order_number`;
* `python-oracledb` returns columns with an `IS JSON` constraint already
  decoded, as `dict` or `list`: accept decoded values, LOBs, and JSON text
  when reading them;
* a database error answers 503 with `DATABASE_UNAVAILABLE`, the Oracle
  `full_code` at the end of `error.message` (Q3), and logs the error class
  and code, never the values;
* an offline test runs one complete business request with a fake LLM and a
  fake database session, up to the saved record, and checks that every saved
  value is serializable. The local verification has no database, so this test
  is the only local run of that path.

```python
def read_credentials(secrets_dir: Path) -> tuple[str, str]:
    """Read the database user and password mounted by the service."""
    user = (secrets_dir / "username").read_text(encoding="utf-8").strip()
    password = (secrets_dir / "password").read_text(encoding="utf-8").strip()
    return user, password
```

*Why:* observed in the spike of 2026-10-14
([results](../../../docs/managed-storage-adb-spike.md)): the service gives
the connect string in the variable and the credentials as files, and the
connect string points to a local TLS endpoint, so no wallet is needed. The
live acceptance of [Spec 027](../../../specs/027-agents-with-a-database.md)
found the decoded `IS JSON` values, the reserved bind name, and a transient
startup failure that left `/ready` at 503 without a retry; each cost a full
release cycle in OCI.

**Q9. Schema** (agents of B9). The agent creates its schema at startup:

* SQL compatible with Oracle Database 19c, the version of the managed
  database: no `CREATE TABLE IF NOT EXISTS`, no `BOOLEAN` or `VECTOR`
  columns; identity columns or UUIDs for keys;
* each `CREATE` inside a PL/SQL block that ignores ORA-00955 (name already
  used):

  ```sql
  begin
    execute immediate 'create table orders (
      order_id varchar2(64) primary key,
      created_at timestamp default systimestamp not null,
      payload clob check (payload is json))';
  exception
    when others then
      if sqlcode != -955 then raise; end if;
  end;
  ```

* a `schema_version` table and an ordered list of changes, each applied once;
  a new version only adds tables, columns, or indexes, never drops or renames
  them, because during a release the previous version may still run against
  the same database;
* the catalog seed with `MERGE` by primary key from the packaged files, so
  that several replicas starting together give the same result.

*Why:* the service provides an empty schema, the data must survive new
versions, and all replicas start against the same database.
