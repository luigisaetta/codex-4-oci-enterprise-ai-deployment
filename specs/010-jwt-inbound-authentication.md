# Spec 010: JWT inbound authentication for Hosted Applications

Status: draft; not implemented.
Date: 2026-09-30.

## Problem

The only deployment profile is `public-noauth`: every agent endpoint is public
and accepts unauthenticated calls. This is acceptable for demos, not for
agents that expose business data or incur model costs. OCI Generative AI
Hosted Applications can require an OAuth 2.0 bearer token (a JWT) issued by an
OCI IAM identity domain, but the skills cannot configure it, and the verifier
cannot call a protected endpoint.

## Scope

This specification is deliberately atomic: the **first release** of an agent
with token-protected access, and the verification of that release.

* A new manifest deployment profile, `public-idcs`, whose identity-domain
  settings live in the manifest, as in the companion repository
  `oci-enterprise-ai-deployer`.
* Deploy: create the application with identity-domain inbound
  authentication. The settings are validated for format only; they are not
  tested against the identity domain at deploy time.
* Verify: obtain an access token with the operator's client credentials,
  call the endpoint with it, and check that a call without a token is
  rejected. This is where the settings are actually tested.
* Offline tests, skills, and documentation, for Bash and PowerShell.

## Non-goals

* Changing the authentication of an existing application (for example from
  `public-noauth` to `public-idcs`). `hosted-application update` accepts
  `--inbound-auth-config`, but this is a separate specification. The deploy
  keeps stopping when an existing application does not match the manifest.
* OCI IAM request-signature authentication (`hosted-application-iam`).
* Creating or configuring the identity-domain confidential application; it is
  a documented manual prerequisite.
* Checking the identity-domain settings at deploy time.
* Private endpoints and custom networking.
* Authorization inside the agent (roles, per-user data); the platform
  validates the token before the request reaches the container.

## Platform facts

### Verified in documentation and tools (2026-09-30)

Sources:

* [Use OCI IAM Authentication for Hosted Application Endpoints](https://docs.oracle.com/en-us/iaas/releasenotes/generative-ai/hosted-applications-iam.htm)
  (release note, 2026-07-15);
* [Creating an application](https://docs.oracle.com/en-us/iaas/Content/generative-ai/create-application.htm);
* [Deploy an OpenAPI MCP Server with OCI Generative AI](https://docs.oracle.com/en-us/iaas/Content/generative-ai/deploy-openapi-mcp-server-oci-generative-ai.htm),
  section on inbound authentication;
* OCI CLI 3.94.0 help and OCI Python SDK 2.187.0 models `InboundAuthConfig`
  and `IdcsAuthConfig`.

| # | Fact |
| --- | --- |
| A1 | Two authentication methods exist: identity-domain bearer token (`CreateHostedApplication` with `InboundAuthConfig`) and OCI IAM request signing (`CreateHostedApplicationIam`). |
| A2 | The bearer-token configuration is `{"inboundAuthConfigType":"IDCS_AUTH_CONFIG","idcsConfig":{"domainUrl":…,"scope":…,"audience":…}}`; `scope` is a single string. |
| A3 | The identity domain needs a confidential application that is a resource server with a primary audience and a scope, and an OAuth client with the client-credentials grant. The administrator chooses the audience and scope values; existing confidential applications are commonly reused. The Hosted Application's audience and scope must match those of the confidential application exactly. |
| A4 | A client obtains a token with `POST <domainUrl>/oauth2/v1/token`, `grant_type=client_credentials`, its client ID and secret, and `scope=<audience><scope>`. |
| A5 | `hosted-application update` accepts `--inbound-auth-config` (not used by this specification). |

### Observed in the tenancy (2026-09-30, read-only)

From the existing applications in the target compartment and from the
companion repository `oci-enterprise-ai-deployer`, which renders the same
`IDCS_AUTH_CONFIG` JSON from a YAML `security` section and, according to its
author, was tested end to end on another workstation:

| # | Fact |
| --- | --- |
| A6 | `NO_AUTH_CONFIG` is reported as `UNKNOWN_ENUM_VALUE` by OCI SDK 2.187.0 and CLI 3.94.0; the companion repository describes it as a Limited Availability type absent from the public SDK model. The CLI cannot return raw `NO_AUTH_CONFIG`: for `public-noauth`, match `NO_AUTH_CONFIG` or `UNKNOWN_ENUM_VALUE` only when `idcs-config` is null or absent; never match `IDCS_AUTH_CONFIG`. For `public-idcs`, match only `IDCS_AUTH_CONFIG` with exactly matching `domain-url`, `scope`, and `audience`; never match `UNKNOWN_ENUM_VALUE`. |
| A7 | The service accepts `IDCS_AUTH_CONFIG` at creation without validating the identity domain (an application exists with placeholder values). A wrong configuration surfaces only when the endpoint is called: the verifier's checks are the real test. |
| A8 | An application created with a real identity domain has audience `all` and scope `invoke`. The audience is not always a URL; it must equal the primary audience configured on the confidential application. |
| A9 | For the unauthenticated `text-stats` application, both `inference.generativeai.eu-frankfurt-1…` and `application.generativeai.eu-frankfurt-1…` answer `/health` with 200. |

### Assumptions, to confirm during the live acceptance

Implementation proceeds with these assumptions; each is isolated in one place
of the verifier so that it can be changed if the live test contradicts it.

| # | Assumption | Where it is used |
| --- | --- | --- |
| U1 | A protected application is served by the same endpoint host as today (`inference.generativeai.<region>…`). | Endpoint URL (unchanged) |
| U2 | Direct HTTP calls use `Authorization: Bearer <token>`. | Every authenticated request |
| U3 | `/health` and `/ready` are protected like the business paths. | Probes send the header; the negative check uses `/health` |
| U4 | A request without a token is rejected with 401 or 403. | Negative check |
| U5 | The token scope is `<audience><scope>` (A4); when that does not fit the identity domain (for example audience `all`), the operator sets the exact token scope. | Token request |

## Configuration

### Manifest

`deploy.profile` accepts `public-noauth` (unchanged) or `public-idcs`. With
`public-idcs`, the section `deploy.auth` is required:

```yaml
deploy:
  application_name: text-stats
  profile: public-idcs
  auth:
    domain_url: https://idcs-<id>.identity.oraclecloud.com:443
    audience: <primary audience of the confidential application>
    scope: <scope of the confidential application>
```

| Field | Rule |
| --- | --- |
| `domain_url` | Required; `https://` URL with host and optional port, no path, no query. |
| `audience` | Required; non-empty, no whitespace; any value, exactly as configured on the confidential application (A3, A8). |
| `scope` | Required; one scope string, no whitespace. |

* `deploy.auth` is rejected with `public-noauth`; unknown fields are rejected,
  as elsewhere in the manifest.
* These values are not secret and are committed with the agent. The person
  preparing the agent is responsible for their correctness; the deploy does
  not test them (non-goals), the verifier does.
* The manifest never contains a client ID, a client secret, or a token; the
  existing sensitive-name checks apply.
* Field names follow the OCI API (`domainUrl`, `audience`, `scope`); the
  companion repository calls the domain URL `issuer_url` and accepts a list of
  scopes, which is joined into this single string.

### Operator credentials (verification only, required)

| Variable | Meaning |
| --- | --- |
| `OCI_AGENT_IDCS_CLIENT_ID` | Client ID of the confidential application. |
| `OCI_AGENT_IDCS_CLIENT_SECRET` | Client secret. |
| `OCI_AGENT_IDCS_TOKEN_SCOPE` | Optional; exact token scope, overriding `<audience><scope>` (U5). Not secret. |

* The verifier requires the client ID and secret whenever the profile is
  `public-idcs`: without a valid token there is no verification, so a missing
  variable exits 64 before any OCI call, naming the variable and not its
  value.
* They are read only from the process environment, only by the verifier;
  never from the tenancy file or the manifest.
* The secret and the token are never printed, logged, stored in files, or
  placed in a command argument: the token request sends the form data to
  `curl` on standard input (Bash: `--data @-`), and PowerShell sends it in the
  request body. Error output shows the HTTP status and the OAuth `error`
  field only.

## Intended behavior

### Deploy (`deploy_hosted_application.sh` and `.ps1`)

* With `public-idcs`, a first release creates the application with the A2
  JSON built from `deploy.auth`. Networking stays public and Oracle-managed.
* The manifest validation above is the only check of the settings; there is
  no call to the identity domain.
* The plan shows "Access: public endpoint, identity-domain token required",
  the domain URL, the audience, and the scope, instead of the unauthenticated
  warning.
* Reusing an existing application requires the same inbound configuration
  as the manifest (type and the three values, compared on the raw JSON, A6);
  otherwise the deploy stops with exit 20 and says that changing
  authentication is not supported.
* New versions and rollback (Spec 009) are unchanged.

### Verify (`verify_deployment.sh` and `.ps1`)

For a manifest with `public-idcs`:

1. Require the operator credentials (exit 64 if absent).
2. Check OCI state as today, and that the application's inbound
   configuration matches the manifest (exit 20 otherwise).
3. Obtain a token (A4, U5). Failure: exit 24, "Could not obtain an access
   token from the identity domain", with the HTTP status and the OAuth
   `error` field.
4. Negative check: call `/health` without a token; it must be rejected (U4).
   Accepted: exit 25, "The endpoint accepted a request without a token".
5. Health and readiness probes and, with `--functional`, the manifest checks,
   with the `Authorization` header (U2, U3).
6. The report line adds `auth=idcs` and `unauthenticated_status=<code>`;
   `public-noauth` reports `auth=none`.

`run_manifest_checks.py` receives the token through an environment variable
set only for its process (`OCI_AGENT_ACCESS_TOKEN`), never as an argument, and
sends it as the `Authorization` header.

New exit codes: 24 (token request failed) and 25 (unauthenticated request
accepted). Existing codes are unchanged.

### Skills and documentation

* `oci-agent-deploy`: the two profiles, the `deploy.auth` fields, the
  statement that they are not tested at deploy time, and the new plan line.
* `oci-agent-verify-deployment`: the required operator credentials, the
  optional token scope, the negative check, exit codes 24 and 25, and the rule
  that the secret and the token are never shown or typed into the chat.
* `references/`: the facts A1–A9 and the assumptions U1–U5, updated after the
  live acceptance.
* Guide: "Protect an agent with identity-domain tokens" (which values to ask
  the identity-domain administrator for, whether the confidential application
  is new or reused; how to fill the `deploy.auth` section; no example audience
  or scope values beyond placeholders) and "Call a protected agent" (token request and header, with
  placeholders only).
* Quickstart: one short section for end users.
* `agent.yaml.template`: a commented `public-idcs` example.

## Tests (offline)

Fake `oci` and fake `curl` (Bash) first on `PATH`; PowerShell runs skipped
without `pwsh`, plus static checks.

* Manifest: `public-idcs` with a valid `deploy.auth` accepted; missing
  section or field, invalid domain URL (http, path, query), whitespace in
  audience or scope, unknown field, and `deploy.auth` with `public-noauth`
  rejected.
* Deploy with `public-idcs`: the create command carries the A2 JSON built
  from the manifest; the plan shows the access line; an existing application
  with a different inbound configuration, including `UNKNOWN_ENUM_VALUE`,
  exits 20 with no mutation; no call to the identity domain in any scenario.
* Verify with `public-idcs`:
  * missing client ID or secret → 64, with no OCI or HTTP call;
  * the token request receives the secret on standard input, never in the
    arguments of any recorded command;
  * the secret and the token never appear in stdout or stderr;
  * the token scope is `<audience><scope>`, or `OCI_AGENT_IDCS_TOKEN_SCOPE`
    when set;
  * success path: unauthenticated `/health` rejected, then authenticated
    probes and functional checks with `Authorization: Bearer`;
  * token failure → 24; unauthenticated request accepted → 25.
* `public-noauth` behavior unchanged (existing tests stay green).

## Acceptance criteria

1. Offline tests pass for Bash, and for PowerShell where executable.
2. Live, in eu-frankfurt-1, with explicit authorization and valid
   credentials: a new application (for example `text-stats-idcs`) released
   with `public-idcs`; the verifier passes, including the negative check and
   the functional checks.
3. U1–U5 confirmed or corrected from the live test and recorded here.
4. A request with a token for another audience or scope is rejected
   (recorded status).
5. No secret or token appears in any output, file, or command line during
   the live test.
6. Documentation describes the setup and how to call a protected agent.

Criteria 2–5 wait until client credentials of a confidential application are
available.

## Prerequisites for the live test (manual)

Reuse an existing confidential application, or, in the tenancy's identity
domain (for example `Default`), following A3:

1. create a confidential application;
2. configure it as a resource server with a primary audience and a scope of
   the administrator's choice;
3. configure it as a client with the client-credentials grant;
4. activate it, and record the domain URL, the primary audience, the client
   ID, and the client secret.

Put the domain URL, audience, and scope in the agent's manifest; keep the
client ID and secret out of the repository and of the chat, and export them
only in the shell that runs the verifier.

## Recovery and cleanup

* A failed first release follows Spec 006 recovery.
* The test application is deleted manually when no longer needed.
* Rotate the client secret in the identity domain if it is ever exposed.

## Verification record

* 2026-09-30 — Step 2 review finding: `hosted-application get --output json`
  uses kebab-case inbound-authentication keys and reports unauthenticated
  applications as `UNKNOWN_ENUM_VALUE` with `idcs-config: null`. The matcher
  and offline fixtures were corrected so this value matches `public-noauth`
  only; it remains a mismatch for `public-idcs`. Local checks are recorded
  after this change.
