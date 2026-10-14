# Agent manifest reference (`agent.yaml`)

Every agent released with the OCI agent skills has an `agent.yaml` next to its
code. This page lists every field, with its rule and an example. The rules are
those enforced by `scripts/agent_manifest.py`: a manifest that breaks one is
rejected with exit code 64 and a message naming the field.

For a new agent, `oci-agent-new` creates a first `agent.yaml` from the
approved specification; this page describes every field, for review or
editing.

## Choose the access mode first

The most important decision is who may call the agent. It is set by
`deploy.profile`, which has exactly two values:

| `deploy.profile` | Who can call the endpoint | Extra settings | Use it for |
| --- | --- | --- | --- |
| `public-noauth` | **Anyone** who knows the address. No token is required. | None; `deploy.auth` must be absent. | Demos and tests with no sensitive data. |
| `public-idcs` | Only callers presenting a valid **JWT access token** issued by your OCI IAM identity domain. | `deploy.auth` is required: `domain_url`, `audience`, `scope`. | Every agent that exposes business data, incurs model costs, or will be used by others. |

In both cases the endpoint is reachable from the internet (`public`); the
profile decides whether a token is required.

* **Unprotected agent:** `profile: public-noauth`, and no `auth` section.
* **Agent protected with JWT tokens:** `profile: public-idcs`, and an `auth`
  section with the three values given by your identity-domain administrator.
  How to create the confidential application that provides them, step by
  step: [Protecting an agent with JWT tokens](idcs-confidential-application.md).

The access mode is fixed when the Hosted Application is created. The skills do
not change it on an existing application: to switch an agent from one mode to
the other, release it as a new application (a different
`deploy.application_name`).

For `public-idcs`, the verification (not the deploy) tests the values: it
needs the client ID and client secret of the confidential application,
`OCI_AGENT_IDCS_CLIENT_ID` and `OCI_AGENT_IDCS_CLIENT_SECRET`, in the tool's
`.env` or exported in your own shell. Never put them in `agent.yaml`, and never
paste them into the chat. See
[Protect an agent with identity-domain tokens](using-oci-agent-skills.md#protect-an-agent-with-identity-domain-tokens).

## Complete examples

### Unprotected agent (`public-noauth`)

```yaml
schema_version: 2
name: text-stats
build:
  context: .
  dockerfile: Dockerfile
publish:
  repository: agents/text-stats
deploy:
  application_name: text-stats
  profile: public-noauth
verify:
  - method: POST
    path: /analyze
    body:
      text: Hello world. This is a test!
    expect_status: 200
    expect_json:
      words: 6
```

### Agent protected with JWT tokens (`public-idcs`)

```yaml
schema_version: 2
name: text-stats
build:
  context: .
  dockerfile: Dockerfile
publish:
  repository: agents/text-stats
deploy:
  application_name: text-stats-protected
  profile: public-idcs
  auth:
    domain_url: <identity-domain-url>
    audience: <audience-of-the-confidential-application>
    scope: <scope-of-the-confidential-application>
runtime:
  env:
    - name: LOG_LEVEL
      value: INFO
verify:
  - method: POST
    path: /analyze
    body:
      text: Hello world. This is a test!
    expect_status: 200
    expect_json:
      words: 6
```

## Fields

Top-level fields: `schema_version`, `name`, `build`, `publish`, `deploy`,
`verify` (required) and `runtime` (optional). Any other field is rejected.

### `schema_version` (required)

Always `2`. Version 1 manifests are rejected; in version 2, build paths are
relative to the manifest's folder.

### `name` (required)

The local container image name, for example `text-stats`. It must start with
a letter or digit and contain only letters, digits, `.`, `_`, and `-`. Use
lowercase: Docker rejects uppercase image names.

### `build` (required)

| Field | Required | Rule | Example |
| --- | --- | --- | --- |
| `context` | yes | Folder sent to the container build, relative to the manifest's folder. | `.` |
| `dockerfile` | yes | Dockerfile path, relative to the manifest's folder; must be a file. | `Dockerfile` |

Both must stay inside the allowed roots: by default the Git repository that
contains the manifest (or the manifest's folder outside Git), or the folders
listed in `OCI_AGENT_ALLOWED_ROOTS`.

### `publish` (required)

| Field | Required | Rule | Example |
| --- | --- | --- | --- |
| `repository` | yes | OCIR repository below the tenancy namespace: lowercase letters, digits, `.`, `_`, `-`, and `/`; no `//`. | `agents/text-stats` |

### `deploy` (required)

| Field | Required | Rule | Example |
| --- | --- | --- | --- |
| `application_name` | yes | Hosted Application display name: starts with a letter or digit; letters, digits, `.`, `_`, `-`. | `text-stats` |
| `profile` | yes | `public-noauth` or `public-idcs` (see [Choose the access mode first](#choose-the-access-mode-first)). | `public-idcs` |
| `auth` | only with `public-idcs` | Identity-domain settings; rejected with `public-noauth`. | see below |
| `scaling` | no | Number of replicas, set when the application is created. Without it, the platform default applies (1 to 3 replicas). | `{min_replicas: 1, max_replicas: 1}` |
| `storage` | no | Managed Oracle database for the application, set when the application is created. | `{type: ADB}` |

`deploy.auth`, for `public-idcs` only; all three fields are required, and
the values must match the confidential application exactly:

| Field | Rule | Where to find it |
| --- | --- | --- |
| `domain_url` | `https://` URL with a host and an optional port; no path, query (`?`), fragment (`#`), or user info. | Identity-domain administrator (domain URL). |
| `audience` | Non-empty, no spaces; any form. | Primary audience of the confidential application. |
| `scope` | Non-empty, no spaces. | Scope of the confidential application. |

These three values are not secret: they are committed with the agent. The
deploy checks only their format; the verification checks that a token can be
obtained with them and that the endpoint accepts it.

`deploy.scaling`, optional
([Spec 023](../specs/023-replica-scaling-at-creation.md)):

| Field | Rule |
| --- | --- |
| `min_replicas` | Integer, at least 1. |
| `max_replicas` | Integer, at least `min_replicas`, at most 30. Equal to `min_replicas` disables autoscaling. |

```yaml
deploy:
  application_name: my-agent
  profile: public-noauth
  scaling:
    min_replicas: 1
    max_replicas: 1
```

Use one replica (`max_replicas: 1`) for an agent that keeps state in memory,
for example the jobs of an asynchronous agent: with more replicas, a request
can reach a replica that does not have that state. The value is set only when
the application is created; the deploy stops if an existing application has
other replicas. The scaling metric stays the platform default (requests per
second).

`deploy.storage`, optional
([Spec 026](../specs/026-managed-adb-storage-at-creation.md)):

| Field | Rule |
| --- | --- |
| `type` | Required; `ADB` (Oracle Autonomous Database, version 19c). |
| `connect_env` | Name of the variable that receives the connect string; default `DB_CONNECT_STRING`. Must match `^[A-Z][A-Z0-9_]*$`, must not be a `runtime.env` name, and must not start with `OCI_` or `OCIR_`. |

```yaml
deploy:
  application_name: my-agent
  profile: public-noauth
  storage:
    type: ADB
```

The service creates the database and connects it to the application: there is
no database, wallet, network, or credential to manage, and none goes in the
manifest. At run time the agent finds the connect string in `connect_env`,
and the database user and password in the files
`/mnt/secrets/adb/username` and `/mnt/secrets/adb/password`. The schema is
empty: the agent creates its own tables.

What to know before using it (observed on 2026-10-14, see the
[spike results](managed-storage-adb-spike.md)):

* Storage is set only when the application is **created**. The deploy stops
  if an existing application has no storage, or has one and the manifest does
  not. A new application name starts with an empty database.
* The data survives new versions and restarts, and all replicas share it.
* Deleting the application **loses the data**. The storage itself is not
  deleted with the application: delete it afterwards, as described in
  `oci-agent-deploy`.
* The database cannot be reached from outside the application.

### `runtime` (optional)

Environment variables for the container, set on the Hosted Application when it
is created and injected into the local verification container.

```yaml
runtime:
  env:
    - name: LOG_LEVEL
      value: INFO
    - name: GENAI_COMPARTMENT_ID
      from_env: OCI_COMPARTMENT_ID
    - name: EXTERNAL_API_KEY
      vault_secret_id: <ocid-of-an-oci-vault-secret>
```

Each entry has a `name` and **exactly one** source:

| Source | Value | Use it for |
| --- | --- | --- |
| `value` | A literal, committed with the manifest. Forbidden for names that look secret (containing `TOKEN`, `SECRET`, `PASSWORD`, `PASSWD`, `APIKEY`, `API_KEY`, or `PRIVATE_KEY`). | Non-secret settings, such as a log level. |
| `from_env` | The name of a variable read when the plan or deploy runs: first from the operator's environment, then from the tool's `.env`. Missing in both means the plan stops. Reports show `value=<hidden>`. | Values that differ per tenancy, and secrets such as `GENAI_API_KEY`. |
| `vault_secret_id` | The OCID of an OCI Vault secret (`ocid1.vaultsecret.oc1.…`); the value is never printed. | Secrets. The runtime needs an IAM policy to read the secret. |

Rules: names match `^[A-Z][A-Z0-9_]*$`, are unique, and cannot be `PATH`,
`HOME`, or `PYTHONPATH`; values are single-line. Local verification omits
Vault variables unless `OCI_AGENT_VAULT_<NAME>` is set in the operator's shell.
Variables are set only when the application is created; the deploy stops if
an existing application has different variables.

### `verify` (required, may be empty)

Functional checks run by local verification and, on request, after
deployment. `/health` and `/ready` are always checked by the skills and are
not listed here. Use `verify: []` for no functional check.

| Field | Required | Rule | Example |
| --- | --- | --- | --- |
| `method` | yes | `GET` or `POST`. | `POST` |
| `path` | yes | Absolute path starting with `/`; no `//` prefix and no `..`. | `/analyze` |
| `body` | no | JSON body; `POST` only. | `{text: Hello}` |
| `expect_status` | yes | HTTP status code (100–599). | `200` |
| `expect_json` | no | JSON object that the response must **contain**: every listed key must be present with that value; other keys in the response are ignored. With `poll`, it applies to the final status response. | `{words: 6}` |
| `poll` | no | For asynchronous agents, `POST` only: after the start request, read the job status until it ends (see below). | see below |
| `local` | no | `false`: the local verification of the image skips the check; the remote verification runs it. Default `true`. | `false` |

For `public-idcs` agents, the post-deployment checks send the access token
automatically.

**Asynchronous agents** ([Spec 024](../specs/024-asynchronous-agents.md)):
the start request answers with a `job_id`; `poll` reads the status at a path
that contains `{job_id}` until `status` equals `until_status`. A `failed` job,
a 404, or the timeout fail the check.

| `poll` field | Required | Rule | Default |
| --- | --- | --- | --- |
| `path` | yes | Absolute path containing `{job_id}`. | — |
| `until_status` | yes | Final status that passes the check, for example `completed`. | — |
| `timeout_seconds` | no | 1–1800. | `300` |
| `interval_seconds` | no | 1–60, between two status requests. | `3` |

```yaml
verify:
  # Deterministic: an invalid start request is rejected, no LLM needed.
  - method: POST
    path: /analyses
    body: {}
    expect_status: 400
  # The full job; with Resource Principal it can run only in OCI.
  - method: POST
    path: /analyses
    body: {text: "Example document"}
    expect_status: 202
    local: false
    poll:
      path: /analyses/{job_id}
      until_status: completed
      timeout_seconds: 300
    expect_json: {status: completed}
```

An asynchronous agent keeps its jobs in memory, so its manifest sets one
replica (`deploy.scaling`).

## Never put in `agent.yaml`

* A version tag: pass it at release time (`tag: 0.2.0`), so the manifest
  stays the same across releases.
* OCIDs of the application or deployment, or endpoint URLs.
* Client IDs, client secrets, passwords, API keys, or tokens: use
  `vault_secret_id` for runtime secrets, and the operator's shell for the
  verification credentials.

## Where to start

The template `skills/oci-agent-build/assets/agent.yaml.template` has both
profiles, commented. See
[Creating a new agent repository](using-oci-agent-skills.md#creating-a-new-agent-repository)
for the other files an agent needs.
