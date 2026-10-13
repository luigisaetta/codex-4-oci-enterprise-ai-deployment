# Spec 022: identity-domain credentials for the demo UI and the verifier

Status: implemented; offline checks passed; live acceptance pending (with TODO item 6).
Date: 2026-10-13.
Amends [Spec 010](010-jwt-inbound-authentication.md) (credentials source) and
[Spec 018](018-skill-oci-agent-ui.md) (`public-idcs` agents).

## Problem

Agents with the `public-idcs` profile accept only callers with a JWT access
token issued by an identity domain (Spec 010). Two parts of the tool make
them hard to use:

* **The demo UI does not support them.** `oci-agent-ui` stops when the
  profile is `public-idcs` (a non-goal of Spec 018), and the UI's server
  bridge sends no token.
* **The verifier needs exported variables.** `OCI_AGENT_IDCS_CLIENT_ID` and
  `OCI_AGENT_IDCS_CLIENT_SECRET` must be exported in the terminal that starts
  Codex. The Codex extension for VS Code sees only the environment that
  started VS Code, and the export must be repeated in every new terminal.

## Scope

1. **UI bridge with a token.** When `ui/.env.local` sets the identity-domain
   values, the server route `/api/agent` obtains a client-credentials token,
   caches it until shortly before it expires, and sends it to the agent as
   `Authorization: Bearer`. The browser never receives the token or the
   credentials.
2. **`oci-agent-ui` accepts `public-idcs`.** It writes the non-secret values
   in `ui/.env.local` and leaves the client ID and secret for the developer.
3. **The verifier reads the credentials from the tool's `.env` too**, after
   the environment, as `from_env` does since Spec 015.
4. Offline tests and documentation: everywhere that says `public-idcs` is
   unsupported by the UI, or that the credentials must be exported.

## Non-goals

* Sign-in of end users in the UI (OIDC with redirect): the UI still runs only
  on `127.0.0.1` for the developer (Spec 018).
* Deploying the UI.
* Reading the tool's `.env` from the UI: the UI lives in the agent
  repository, which must not depend on the tool home's path.
* The live acceptance of `public-idcs` itself (TODO item 6); this
  specification is accepted together with it.

## Intended behavior

### UI configuration (`ui/.env.local`)

Next.js reads `ui/.env.local`, which the template already excludes from Git.
New entries, all optional; without them the UI behaves as today:

| Entry | Meaning | Secret |
| --- | --- | --- |
| `IDCS_DOMAIN_URL` | Domain URL, from `deploy.auth.domain_url`. | No |
| `IDCS_TOKEN_SCOPE` | `deploy.auth.audience` immediately followed by `deploy.auth.scope`, as the verifier requests (Spec 010, U5). | No |
| `IDCS_CLIENT_ID` | Client ID of the confidential application. | No, but private |
| `IDCS_CLIENT_SECRET` | Client secret. | **Yes** |

No entry has the `NEXT_PUBLIC_` prefix, so none reaches the browser.

### UI bridge

1. If `IDCS_CLIENT_ID` is empty, the bridge sends no token (as today).
2. If it is set, all four entries are required; a missing one is logged by
   name and the page shows "unavailable".
3. Token request: `POST <IDCS_DOMAIN_URL>/oauth2/v1/token` with HTTP Basic
   client credentials, `grant_type=client_credentials`, and
   `scope=<IDCS_TOKEN_SCOPE>`; timeout 30 seconds.
4. The token is kept in memory and reused until 60 seconds before
   `expires_in` (default 3600 seconds when absent).
5. If the agent answers 401, the cached token is discarded, and the page
   shows "unavailable"; the next request obtains a new token.
6. Logs never contain the secret, the token, or the `Authorization` header;
   a token failure logs the HTTP status and the OAuth `error` code only.

The token logic lives in its own module of the template
(`app/api/agent/idcs-token.js`), so that it can be tested without Next.js.

### `oci-agent-ui`

* The skill no longer stops for `public-idcs`.
* Step 5 (address of the agent): for `public-idcs`, the skill also writes
  `IDCS_DOMAIN_URL` and `IDCS_TOKEN_SCOPE` from `deploy.auth`, and empty
  `IDCS_CLIENT_ID=` and `IDCS_CLIENT_SECRET=` lines. The closing message asks
  the developer to fill in the two lines by hand.
* Codex never writes, reads, or prints the client ID or secret, and never
  reads `ui/.env.local` after telling the developer to fill it in.

### Verifier

For `public-idcs`, `OCI_AGENT_IDCS_CLIENT_ID` and
`OCI_AGENT_IDCS_CLIENT_SECRET` are taken from the environment or, when unset
there, from the tool's `.env` (`OCI_AGENT_ENV_FILE`, default the tool home's
`.env`). A new read-only command, `tool_config.py has <KEY>`, exits 0 when the
key has a value in either place and 1 otherwise, printing nothing; the
verifiers use it for their preflight, and `idcs_token.py` reads the values
the same way. The missing-variable message names the variable and both
places. The values are never exported, printed, or written.

## Documentation

* `docs/idcs-confidential-application.md`: the credentials in the tool's
  `.env` or exported (section 8), and a new section for the demo UI.
* `docs/agent-manifest-reference.md`, `docs/using-oci-agent-skills.md`,
  README (Security), `skills/README.md`, the verify and UI skills,
  `.env.example`, and the UI template's `.env.local.example` and README.
* Spec 018: the `public-idcs` non-goal replaced by a pointer to this
  specification.
* `CHANGELOG.md`.

## Tests (offline)

* `tests/test_tool_config.py`: `has` with the value in the environment, in
  `.env`, and absent; it prints nothing.
* `tests/test_verify_deployment_idcs.py`: the preflight passes with the
  credentials only in the tool's `.env`; the missing-variable test isolates
  the tool's `.env`.
* `tests/test_idcs_token.py`: the token helper reads the tool's `.env` when
  the environment is empty.
* `tests/test_ui_template.py`: the bridge reads the four entries, uses no
  `NEXT_PUBLIC_` variable, and `.env.local.example` documents them as
  commented placeholders; a Node.js test of `idcs-token.js` against a fake
  token endpoint (request form, Basic authentication, caching, refresh after
  a discarded token), skipped when `node` is unavailable.

## Acceptance criteria

1. The offline tests, Black, Pylint, and pytest pass; links resolve.
2. Live, with TODO item 6: a `public-idcs` agent is verified with the
   credentials only in the tool's `.env`, and its demo UI answers through the
   bridge with the credentials in `ui/.env.local`.

## Verification record

### 2026-10-13, macOS, local

* `scripts/tool_config.py` (`credential_value`, `has`), `scripts/idcs_token.py`,
  and both verifiers read the credentials from the environment, then from the
  tool's `.env`.
* UI template: new `app/api/agent/idcs-token.js`; `route.js` adds the bearer
  token, discards it after a 401, and logs only categories; `.env.local.example`
  and the template README document the `IDCS_*` entries. `node --check`
  passed on both files. A `next build` of the changed template was not run.
* `oci-agent-ui` accepts `public-idcs`; guideline T3 updated.
* Documentation aligned: the JWT guide (table, sections 4, 8, new 9,
  troubleshooting), manifest reference, step-by-step guide, README (Security),
  skill catalog, verify skill, `.env.example`, Spec 018.
* Offline: new tests in `tests/test_tool_config.py`, `tests/test_idcs_token.py`
  (a local fake token endpoint), `tests/test_verify_deployment_idcs.py`, and
  `tests/test_ui_template.py` (a Node.js test of `idcs-token.js`: Basic
  credentials, form body, caching, refresh after expiry and after a discarded
  token, errors). Full suite: 376 passed, 142 skipped (all `pwsh is
  unavailable`); Black and Pylint (10.00/10) passed; links resolve.
* Pending: acceptance criterion 2 (live).
