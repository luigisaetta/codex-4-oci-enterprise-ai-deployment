# Protecting an agent with JWT tokens: the confidential application

An agent with the `public-idcs` profile accepts only callers that present a
valid **JWT access token** issued by your OCI IAM identity domain. The tokens
come from a **confidential application** in that domain. This page explains,
step by step, how to create and configure it, how to test a token, and how to
fill in `agent.yaml`.

> [!NOTE]
> The `public-idcs` profile is implemented and tested offline; its first live
> release with this project is still pending (TODO item 6). The steps below
> follow the Oracle documentation listed at the end. Report anything that
> differs in your tenancy.

## What you get at the end

| Value | Where it goes | Secret? |
| --- | --- | --- |
| **Domain URL** | `deploy.auth.domain_url` in `agent.yaml` | No |
| **Primary audience** | `deploy.auth.audience` | No |
| **Scope** | `deploy.auth.scope` | No |
| **Client ID** | Shell variable `OCI_AGENT_IDCS_CLIENT_ID`, for verification and callers | No, but keep it private |
| **Client secret** | Shell variable `OCI_AGENT_IDCS_CLIENT_SECRET`, for verification and callers | **Yes** |

The first three values are fixed when the Hosted Application is created: to
change them later, release the agent with a new application name.

## Before you start

* You need administrator rights on an identity domain of the tenancy (to add
  integrated applications), or ask its administrator to follow this page.
* Choose the domain: usually the one of your users. One confidential
  application can protect several agents.
* Know the region of the agent, for example `eu-frankfurt-1`.

## 1. Create the confidential application

1. In the OCI Console, open the navigation menu and select **Identity &
   Security**. Under **Identity**, select **Domains**.
2. Open the identity domain.
3. Select **Integrated applications**, then **Add application**.
4. Select **Confidential Application**, then **Launch workflow**.
5. Enter a **Name**, for example `oci-agents-api`, and a **Description**.
   Leave the other fields empty, then continue (**Next** or **Submit**,
   depending on the Console version).

## 2. Configure it as a resource server (audience and scope)

The resource server part defines **what** the token gives access to.

1. Open the application's **OAuth configuration** and select **Edit OAuth
   configuration** (in the creation wizard it is the **Configure OAuth**
   page).
2. Enable **Configure this application as a resource server now**.
3. **Primary audience**: Oracle's documentation uses the Hosted Applications
   address of the region, ending with `/`:

   ```text
   https://application.generativeai.eu-frankfurt-1.oci.oraclecloud.com/20251112/hostedApplications/
   ```

   Replace `eu-frankfurt-1` with your region. Any value works, as long as the
   same value goes into `agent.yaml`; existing applications in some tenancies
   use, for example, `all`.
4. **Add scopes**: add one scope, `invoke`.

## 3. Configure it as a client (client credentials)

The client part defines **who** can ask for tokens: programs that know the
client ID and secret.

1. Enable **Configure this application as a client now**.
2. Under the grant types, select **Client credentials** only.
3. Leave the redirect URLs empty; they are for interactive sign-in, which is
   not used here.
4. Save (**Submit**, or **Next** and then **Finish** in the wizard).

## 4. Record the client ID and secret, then activate

1. The Console shows the **Client ID** and **Client secret** (in the wizard,
   in the **Application added** dialog; later, in the application's **OAuth
   configuration**). Copy the secret into your password manager. Never put it
   in `agent.yaml`, in the tool's `.env`, in a file of a repository, or in the
   Codex chat.
2. A new application is **deactivated**. From the application page select
   **Activate** (in some Console versions, under **Actions**) and confirm.

## 5. Find the domain URL

Open the identity domain's details page and copy the **Domain URL**. It has
this form:

```text
https://idcs-<id>.identity.oraclecloud.com:443
```

## 6. Test a token (optional, recommended)

Before releasing the agent, check that the domain issues a token. The token
scope is the primary audience followed by the scope, for example
`https://application.generativeai.eu-frankfurt-1.oci.oraclecloud.com/20251112/hostedApplications/invoke`.
These commands type the secret without showing it and print only whether a
token was issued, never the token.

macOS and Linux (Terminal):

```bash
read -r -p 'Client ID: ' OCI_AGENT_IDCS_CLIENT_ID
```

```bash
read -r -s -p 'Client secret: ' OCI_AGENT_IDCS_CLIENT_SECRET; echo
```

```bash
curl -s -u "$OCI_AGENT_IDCS_CLIENT_ID:$OCI_AGENT_IDCS_CLIENT_SECRET" -d grant_type=client_credentials -d 'scope=<primary-audience>invoke' 'https://idcs-<id>.identity.oraclecloud.com:443/oauth2/v1/token' | python3 -c 'import json,sys; d=json.load(sys.stdin); print("token issued" if d.get("access_token") else d)'
```

Windows (PowerShell 7):

```powershell
$env:OCI_AGENT_IDCS_CLIENT_ID = Read-Host 'Client ID'
```

```powershell
$env:OCI_AGENT_IDCS_CLIENT_SECRET = Read-Host 'Client secret' -MaskInput
```

```powershell
$pair = "$($env:OCI_AGENT_IDCS_CLIENT_ID):$($env:OCI_AGENT_IDCS_CLIENT_SECRET)"
$basic = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pair))
$response = Invoke-RestMethod -Method Post -Uri 'https://idcs-<id>.identity.oraclecloud.com:443/oauth2/v1/token' -Headers @{ Authorization = "Basic $basic" } -Body @{ grant_type = 'client_credentials'; scope = '<primary-audience>invoke' }
if ($response.access_token) { 'token issued' }
```

Expected: `token issued`. Otherwise see [Troubleshooting](#troubleshooting).

## 7. Fill in `agent.yaml`

```yaml
deploy:
  application_name: my-agent
  profile: public-idcs
  auth:
    domain_url: https://idcs-<id>.identity.oraclecloud.com:443
    audience: https://application.generativeai.eu-frankfurt-1.oci.oraclecloud.com/20251112/hostedApplications/
    scope: invoke
```

| `agent.yaml` | Confidential application |
| --- | --- |
| `domain_url` | Domain URL of step 5 |
| `audience` | Primary audience of step 2, exactly, including a final `/` |
| `scope` | Scope of step 2 |

These values are not secret and are committed with the agent. More details:
[agent manifest reference](agent-manifest-reference.md).

## 8. Release and verify

The release works as for any agent. The **verification** needs a token, so
before it, set the client ID and secret **in the terminal that starts Codex**
(steps of section 6), then start Codex from that terminal. The Codex
extension for VS Code sees only the variables of the environment that
started VS Code.

The verifier asks for a token with the scope `<audience><scope>`. If your
audience does not end with `/` and the domain expects another form, set the
exact token scope, which is not secret:

```bash
export OCI_AGENT_IDCS_TOKEN_SCOPE='<exact-token-scope>'
```

The verifier calls `/health`, `/ready`, and the functional checks with the
token, and checks that a call without a token is rejected.

Callers of the deployed agent do the same: request a token as in section 6,
then send it in the `Authorization: Bearer <token>` header.

## Troubleshooting

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| Token request: `invalid_client` | Wrong client ID or secret, or the application is not activated. | Check the values in the application's OAuth configuration; activate the application (step 4). |
| Token request: `invalid_scope` | The token scope is not `<primary audience><scope>` exactly, or the client is not allowed to request it. | Check the audience and the scope character by character. If they are right, in the application's client configuration, under **Token issuance policy**, select **Add resources** and add the application's own `invoke` scope, then save. |
| Token issued, but the agent answers 401 | The audience, scope, or domain URL of the Hosted Application differ from the confidential application. | Compare `deploy.auth` with steps 2 and 5. These values are fixed at creation: correct `agent.yaml` and release with a new application name. |
| The verifier stops before calling OCI, naming `OCI_AGENT_IDCS_CLIENT_ID` or `OCI_AGENT_IDCS_CLIENT_SECRET` | The variable is not set in the environment of Codex. | Set it in the terminal that starts Codex (section 8). |

## Sources

Verified on 2026-10-13:

* [Deploy an OpenAPI MCP Server with OCI Generative AI](https://docs.oracle.com/en-us/iaas/Content/generative-ai/deploy-openapi-mcp-server-oci-generative-ai.htm):
  confidential application, primary audience
  `https://application.generativeai.<region>.oci.oraclecloud.com/20251112/hostedApplications/`,
  scope `invoke`, client credentials, activation, token request with scope
  `<audience>invoke`, and the mapping to the Hosted Application's audience
  and scope.
* [Adding a Confidential Application](https://docs.oracle.com/en-us/iaas/Content/Identity/applications/add-confidential-application.htm):
  wizard pages, resource server and client settings, the **Token issuance
  policy** and **Add resources**, client ID and secret, activation.
* Project facts A1–A9 and assumptions U1–U6:
  [Spec 010](../specs/010-jwt-inbound-authentication.md).
