# Spec 027: agents with a database

Status: implemented; offline checks passed (2026-10-14); live acceptance pending.
Date: 2026-10-14.
Amends [Spec 011](011-skill-oci-agent-new.md),
[Spec 017](017-oci-agent-new-llm-agents-supported.md), and
[Spec 024](024-asynchronous-agents.md) (supported shape, constraints C3 and
C5, guideline B6). Depends on
[Spec 026](026-managed-adb-storage-at-creation.md) (storage at creation).
Input: [managed ADB storage spike](../docs/managed-storage-adb-spike.md).

## Problem

`oci-agent-new` generates stateless agents: catalogs are read-only files in
the image (B6) and anything the agent produces is lost on restart. A
realistic demo needs both a catalog and a record of what the agent did, for
example an express-order agent whose parts, plants, and suppliers are in a
database and whose orders are saved there. Spec 026 gives the application a
managed Oracle database; the generated code must use it correctly, and the
developer must be able to read back what was saved.

## Scope

1. Agents that use the managed ADB storage become part of the supported
   shape when the specification asks for saved data.
2. New behavior defaults (B9, B10) and code rules (Q8, Q9) for persistent
   data: what is stored, catalog loading, saved records, reading them back,
   schema creation and changes.
3. The specification template gains a **Data** section.
4. Verification: the local verification runs without a database; checks
   that need it run only in the remote verification (`local: false`,
   Spec 024).

## Non-goals

* Persistent asynchronous jobs: the jobs of B8 stay in memory, with one
  replica.
* A local database for the build verification (for example Oracle Database
  Free). Possible later; see Open points.
* Changing the demo UI template (`oci-agent-ui`).
* Large datasets, vector search, or features of Oracle Database 23ai: the
  managed database is 19c (spike).
* Editing the catalog through the API, or deleting saved records.

## Intended behavior

### Supported shape (`oci-agent-new`)

* When the specification says that the agent keeps data between requests
  (a catalog in the database, saved results), the agent uses the managed ADB
  storage without asking whether to proceed. The draft says so in the
  Deployment section, and the manifest gets `deploy.storage` (Spec 026).
* The supported shape for these agents: the business endpoint (synchronous,
  or the asynchronous pair of B8), plus **read endpoints** for saved records
  (B10). Constraint C3 changes accordingly.
* Constraint C5 becomes: "Stateless container, writes only under `/tmp`;
  data that must survive goes to the managed database (B9). No network calls
  or file writes at import time."
* For an existing application without storage, the closing message says that
  the database needs a new application (Spec 026, item 5), which starts
  empty.

### Behavior defaults (into the specification)

* **B9. Saved data.** The Data section lists each table in business terms:
  what it holds, who writes it (seed or agent), and whether it changes.
  Defaults:
  * catalogs (for example parts, plants, suppliers) are packaged files in
    `<package>/data/` (B6) and are loaded into the database at startup; the
    files are the source of truth, so a new version with new files updates
    the catalog;
  * records produced by the agent (for example orders) are saved in the same
    request that produces them, and the response returns their identifier;
  * the data survives new versions and restarts and is shared by all
    replicas; it is **lost when the application is deleted**, and the
    database cannot be reached from outside the agent;
  * without the database (local verification), the endpoints that need it
    answer 503 with `DATABASE_UNAVAILABLE`; input validation still answers
    400 (B5).

  B6 changes accordingly: packaged files stay read-only; simulated state
  that changes goes to the database when the agent has one, otherwise it is
  kept in memory as today.
* **B10. Reading saved records.** For each kind of saved record, a
  `GET /<records>/{id}` answers 200 with the record or 404, and an optional
  `GET /<records>?limit=<n>` lists the most recent ones (default 20,
  at most 100). Identifiers have only letters, digits, `-`, and `_`. The
  endpoints are protected like the business endpoint (same profile).
* **B5** gains: a remote-only check (`local: false`) of `GET /ready` with
  `expect_json: {database: ready}`, so that a missing link to the storage
  fails the remote verification instead of passing silently.

### Code rules (into the code)

* **Q8. Database access.** In a `db.py` module, separate from `agent.py`:
  * `python-oracledb` in thin mode (no Oracle Client), version range in
    `requirements.txt`;
  * connect string from the `connect_env` variable (default
    `DB_CONNECT_STRING`); user and password read from the files in
    `/mnt/secrets/adb/` (directory overridable for tests); never logged,
    returned, or written elsewhere; the connect string is not logged either;
  * a small connection pool per replica, created at startup after the
    variable checks, never at import time; `/ready` answers 503 until the
    pool, the schema (Q9), and the seed are ready, and reports `database`:
    `ready`, `unavailable`, or `not_configured` (variable absent);
  * no blocking database calls in the event loop: use the asynchronous API
    of `python-oracledb` or run calls in a thread pool;
  * bind variables for every value; never build SQL from request text;
  * one transaction per request; a database error answers 503 with
    `DATABASE_UNAVAILABLE` and logs the error class, never the SQL values.
* **Q9. Schema.** The agent creates its schema at startup:
  * SQL compatible with Oracle Database 19c: no `CREATE TABLE IF NOT
    EXISTS`, no `BOOLEAN` or `VECTOR` columns; identity columns or UUIDs for
    keys;
  * each statement idempotent: `CREATE` inside a PL/SQL block that ignores
    ORA-00955 (name already used), as in the spike;
  * a `schema_version` table and an ordered list of changes; a new version
    only adds tables, columns, or indexes, never drops or renames them,
    because during a release the previous version may still run against
    the same database;
  * catalog seed with `MERGE` by primary key from the packaged files, so
    that several replicas starting together give the same result.

### Specification template

A **Data** section: tables with their meaning, the seed files, the saved
records and the endpoints that read them, and the sentence on data loss when
the application is deleted.

## Documentation

* `skills/oci-agent-new` (SKILL.md, guidelines, specification template).
* `skills/oci-agent-build/SKILL.md`: local verification without a database,
  `DATABASE_UNAVAILABLE` and `not_configured` are expected.
* `skills/oci-agent-verify-deployment/SKILL.md`: the remote-only database
  checks.
* `docs/agent-manifest-reference.md`: example of an agent with storage.
* `CHANGELOG.md`.

## Tests (offline)

* `tests/test_skills.py`: the new-agent skill names the database shape and
  links B9, B10, Q8, and Q9; the template has the Data section; C3 and C5
  have the new wording.
* No database in the offline tests: the generated agents are checked by
  the acceptance run.

## Acceptance criteria

1. The offline tests, Black, Pylint, and pytest pass; links resolve.
2. Live, with the acceptance agent below, created with `oci-agent-new`:
   local verification passes without a database; remote verification passes
   with `database: ready`; an order created through the business endpoint
   is read back with `GET`; after a new version the order is still there.

## Acceptance agent

`express-order-db`, a new agent from the specification of the existing
express-order agent (Resource Principal variant, profile `public-idcs`,
customer name Supremo):

* parts, plants, and suppliers are seeded from the packaged JSON files into
  the database;
* every `ordered` or `rejected` result of `POST /express-orders` is saved
  with its request, selected offer, and other offers; the order number is
  the record identifier;
* `GET /express-orders/{order_number}` and `GET /express-orders?limit=10`
  read the saved results;
* checks: `{}` → 400 (local and remote); `GET /ready` with
  `database: ready` (remote only); a valid request, then
  `GET /express-orders?limit=1` → 200 (remote only). The check runner cannot
  pass the order number of one check to the next, so reading back a
  specific order is a manual step of the acceptance run;
* a new application name, because storage is set only at creation
  (Spec 026). The existing express-order applications are not changed.

## Open points

* A local database for the build verification (Oracle Database Free in a
  container, with the credential files mounted), to test SQL before OCI.
  Its version is 23ai, so Q9's 19c rule must still be respected.
* The privileges of the database user beyond creating tables (spike); Q9
  uses only tables and indexes.
* Connection limits of the managed database with several replicas.

## Verification record

### 2026-10-14, macOS, local

* `skills/oci-agent-new/references/agent-guidelines.md`: new B9 (saved data),
  B10 (reading saved records), Q8 (database access), Q9 (schema); B5 gains the
  remote-only `/ready` check, B6 sends changing state to the database, Q4
  waits for the database.
* `skills/oci-agent-new/SKILL.md`: the database shape in the supported shape,
  the "Saved data" input, constraints C3 and C5, workflow steps 7–9
  (`deploy.storage`, `local: false` checks, `db.py`), the closing message, and
  the limitations. The specification template gains the **Data** section.
* `skills/oci-agent-build/SKILL.md`, `skills/oci-agent-verify-deployment/SKILL.md`,
  and `docs/agent-manifest-reference.md`: local verification without a
  database, remote database checks, and an example of the checks.
* Decision: `not_configured` keeps `/ready` at 200, so that the local
  verification passes without a database; the remote-only check
  `database: ready` catches an application created without its storage.
* Decision: the guidelines name `oracledb.create_pool_async` or
  `asyncio.to_thread` for non-blocking access; the asynchronous API of
  `python-oracledb` was not exercised in the spike, which used the
  synchronous thin mode.
* Offline: `tests/test_skills.py::test_new_skill_supports_agents_with_a_database`;
  full suite 436 passed, 157 skipped (all `pwsh is unavailable`); Black and
  Pylint (10.00/10) passed; links resolve.
* Pending: acceptance criterion 2 (live, with `express-order-db`).
