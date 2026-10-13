# Protecting an agent with JWT tokens: the confidential application

An agent with the `public-idcs` profile accepts only callers that present a
valid **JWT access token** issued by your OCI IAM identity domain. The tokens
come from a **confidential application** in that domain. This page explains,
step by step, how to create and configure it, how to test a token, and how to
fill in `agent.yaml`.

> [!NOTE]
> Verified live on 2026-10-13: release, verification with functional checks,
> and the demo UI of a `public-idcs` agent, with a confidential application
> whose audience is not a URL. The Console steps follow the Oracle
> documentation listed at the end; labels can differ between Console
> versions.

## What you get at the end

| Value | Where it goes | Secret? |
| --- | --- | --- |
| **Domain URL** | `deploy.auth.domain_url` in `agent.yaml` | No |
| **Primary audience** | `deploy.auth.audience` | No |
| **Scope** | `deploy.auth.scope` | No |
| **Client ID** | `OCI_AGENT_IDCS_CLIENT_ID` in the tool's `.env` (verification); `IDCS_CLIENT_ID` in the agent's `ui/.env.local` (demo UI) | No, but keep it private |
| **Client secret** | `OCI_AGENT_IDCS_CLIENT_SECRET` in the tool's `.env`; `IDCS_CLIENT_SECRET` in `ui/.env.local` | **Yes** |

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

   Replace `eu-frankfurt-1` with your region. You may choose another value,
   for example `all`: any value works, as long as you write the **same value,
   exactly**, in `agent.yaml` (step 7). Write down the value you enter.
4. **Add scopes**: add one scope, for example `invoke`, and write it down too.

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
   configuration**). Copy the secret into your password manager. Later you
   put it only in the files that Git ignores (sections 8 and 9); never in
   `agent.yaml`, in another file of a repository, or in the Codex chat.
2. A new application is **deactivated**. From the application page select
   **Activate** (in some Console versions, under **Actions**) and confirm.

## 5. Find the domain URL

Open the identity domain's details page and copy the **Domain URL**. It has
this form:

```text
https://idcs-<id>.identity.oraclecloud.com:443
```

## 6. Test a token (optional, recommended)

Before releasing the agent, check that the domain issues a token. Copy the
script for your system into a file, write your values at the top, and run
it. It joins the audience and the scope into the token scope, as the verifier
does: the audience immediately followed by the scope, with nothing in between
(`https://…/hostedApplications/` and `invoke` give `https://…/hostedApplications/invoke`;
`all` and `invoke` give `allinvoke`). It prints whether a token was issued
and, for debugging, the **claims** inside it: issuer (`iss`), audience (`aud`), `scope`, client, and expiry
(`exp`, in seconds since 1970). It never prints the token itself: whoever has
it can call the agent until it expires. You can keep the file and run it
again whenever you change a value.

**The client secret.** Leave `CLIENT_SECRET` empty (recommended): the script
asks for it when it runs and does not show it. If you write it in the file,
keep the file outside any repository, readable only by you, and never share
it.

### macOS and Linux: `test-idcs-token.sh`

```bash
#!/usr/bin/env bash
# Test that the identity domain issues a token for the confidential application.
# Edit the values below, then run: bash test-idcs-token.sh
# Prints whether a token was issued and its claims, never the token itself.
set -euo pipefail

DOMAIN_URL='https://idcs-<id>.identity.oraclecloud.com:443'
# Exactly the Primary audience of the confidential application (step 2).
AUDIENCE='<primary-audience>'
SCOPE='invoke'
CLIENT_ID='<client-id>'
# Leave empty to type the secret when the script runs (recommended).
CLIENT_SECRET=''
# yes: also print the claims inside the token (never the token itself).
SHOW_CLAIMS='yes'

if [[ -z "$CLIENT_SECRET" ]]; then
  read -r -s -p 'Client secret: ' CLIENT_SECRET
  echo
fi
TOKEN_SCOPE="${AUDIENCE}${SCOPE}"
response="$(curl -sS -u "${CLIENT_ID}:${CLIENT_SECRET}" \
  --data-urlencode 'grant_type=client_credentials' \
  --data-urlencode "scope=${TOKEN_SCOPE}" \
  "${DOMAIN_URL%/}/oauth2/v1/token")"
token="$(printf '%s' "$response" | sed -n 's/.*"access_token" *: *"\([^"]*\)".*/\1/p')"
if [[ -z "$token" ]]; then
  echo "No token. Response: ${response}"
  exit 1
fi
echo "Token issued for scope ${TOKEN_SCOPE}"
if [[ "$SHOW_CLAIMS" == 'yes' ]]; then
  # The second part of a JWT holds the claims, base64url-encoded (not encrypted).
  claims="$(printf '%s' "$token" | cut -d. -f2 | tr '_-' '/+')"
  while (( ${#claims} % 4 )); do claims="${claims}="; done
  echo 'Token claims (the token itself is not shown):'
  printf '%s' "$claims" | base64 --decode
  echo
fi
```

Run it with `bash`, also on macOS where the default shell is zsh:

```bash
bash test-idcs-token.sh
```

If you wrote the secret in the file, make it readable only by you:

```bash
chmod 600 test-idcs-token.sh
```

### Windows: `test-idcs-token.ps1`

```powershell
# Test that the identity domain issues a token for the confidential application.
# Edit the values below, then run in PowerShell 7: ./test-idcs-token.ps1
# Prints whether a token was issued and its claims, never the token itself.

$DomainUrl = 'https://idcs-<id>.identity.oraclecloud.com:443'
# Exactly the Primary audience of the confidential application (step 2).
$Audience = '<primary-audience>'
$Scope = 'invoke'
$ClientId = '<client-id>'
# Leave empty to type the secret when the script runs (recommended).
$ClientSecret = ''
# $true: also print the claims inside the token (never the token itself).
$ShowClaims = $true

if (-not $ClientSecret) { $ClientSecret = Read-Host 'Client secret' -MaskInput }
$tokenScope = "$Audience$Scope"
$basic = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("${ClientId}:${ClientSecret}"))
try {
    $response = Invoke-RestMethod -Method Post -Uri "$($DomainUrl.TrimEnd('/'))/oauth2/v1/token" `
        -Headers @{ Authorization = "Basic $basic" } `
        -Body @{ grant_type = 'client_credentials'; scope = $tokenScope }
} catch {
    Write-Output "No token. Response: $($_.ErrorDetails.Message)"
    exit 1
}
if (-not $response.access_token) { 'No token in the response.'; exit 1 }
"Token issued for scope $tokenScope"
if ($ShowClaims) {
    # The second part of a JWT holds the claims, base64url-encoded (not encrypted).
    $claims = $response.access_token.Split('.')[1].Replace('-', '+').Replace('_', '/')
    while ($claims.Length % 4) { $claims += '=' }
    'Token claims (the token itself is not shown):'
    [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($claims)) | ConvertFrom-Json | ConvertTo-Json -Depth 5
}
```

Run it from the folder where you saved it:

```powershell
./test-idcs-token.ps1
```

Expected: `Token issued for scope …`, then the claims. When the agent later
rejects your calls, compare `aud` and `scope` in the claims with `deploy.auth` in
`agent.yaml`. Otherwise the script prints the domain's error, for example `invalid_client` or `invalid_scope`: see
[Troubleshooting](#troubleshooting).

## 7. Fill in `agent.yaml`

Copy the three values **exactly as they are configured in the confidential
application**, character by character. The audience in particular is
whatever you entered as **Primary audience** in step 2: the URL suggested in
step 2, or any other value you chose, for example `all`. A different value,
or a missing or extra final `/`, makes every call to the agent fail: the
service answers 404 to a request it does not accept, as if the agent did not
exist.

```yaml
deploy:
  application_name: my-agent
  profile: public-idcs
  auth:
    domain_url: https://idcs-<id>.identity.oraclecloud.com:443
    audience: <primary-audience>
    scope: <scope>
```

| `agent.yaml` | Copy it from |
| --- | --- |
| `domain_url` | The **Domain URL** of the identity domain (step 5). |
| `audience` | The **Primary audience** of the confidential application (step 2), exactly. |
| `scope` | The **scope** of the confidential application (step 2), for example `invoke`. |

To check the values before releasing, run the script of section 6 with the
same audience and scope: if it issues a token, the claims show the `aud` and
`scope` the agent will expect.

These values are not secret and are committed with the agent. More details:
[agent manifest reference](agent-manifest-reference.md).

## 8. Release and verify

The release works as for any agent. The **verification** needs a token, so it
needs the client ID and secret. Put them in the tool's `.env`, in the tool
home, which Git ignores (the verifier reads them from there when they are not
in the environment):

```dotenv
OCI_AGENT_IDCS_CLIENT_ID=<client-id>
OCI_AGENT_IDCS_CLIENT_SECRET=<client-secret>
```

Edit the file yourself; never paste the values into the Codex chat. From then
on `.env` contains a secret: never share or commit it.

*Alternative, without writing the secret to a file:* set the two variables in
the terminal that starts Codex, then start Codex from it, for example with
`codex`. The Codex extension for VS Code sees only the environment that
started VS Code. In macOS or Linux (zsh or bash), each command shows a prompt
and waits for the value; the secret is not shown while you paste it:

```bash
printf 'Client ID: '; read -r OCI_AGENT_IDCS_CLIENT_ID; export OCI_AGENT_IDCS_CLIENT_ID
```

```bash
printf 'Client secret: '; stty -echo; read -r OCI_AGENT_IDCS_CLIENT_SECRET; stty echo; echo; export OCI_AGENT_IDCS_CLIENT_SECRET
```

In PowerShell 7:

```powershell
$env:OCI_AGENT_IDCS_CLIENT_ID = Read-Host 'Client ID'
```

```powershell
$env:OCI_AGENT_IDCS_CLIENT_SECRET = Read-Host 'Client secret' -MaskInput
```

The verifier asks for a token with the scope `<audience><scope>`. If the
domain expects another form, set the exact token scope, which is not secret,
in the same way (`OCI_AGENT_IDCS_TOKEN_SCOPE`, in the environment).

The verifier calls `/health`, `/ready`, and the functional checks with the
token, and checks that a call without a token is rejected (the service answers
404).

Callers of the deployed agent do the same: request a token from the domain as
the script of section 6 does, then send it in the `Authorization: Bearer
<token>` header.

## 9. The demo UI of a protected agent

The demo page created by `oci-agent-ui` works with `public-idcs` agents: its
local server requests the token and adds it to every call; the browser never
sees the token or the credentials. The skill writes `IDCS_DOMAIN_URL` and
`IDCS_TOKEN_SCOPE` in the agent's `ui/.env.local`, and leaves two empty lines
for you to fill in:

```dotenv
IDCS_DOMAIN_URL=https://idcs-<id>.identity.oraclecloud.com:443
IDCS_TOKEN_SCOPE=<primary-audience><scope>
IDCS_CLIENT_ID=<client-id>
IDCS_CLIENT_SECRET=<client-secret>
```

Git ignores `ui/.env.local`. Restart `npm run dev` after editing it. If the
page shows "service unavailable", the terminal that runs `npm run dev` shows
the cause, for example `token request: HTTP 401, OAuth error invalid_client`.

## Troubleshooting

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| Token request: `invalid_client` | Wrong client ID or secret, or the application is not activated. | Check the values in the application's OAuth configuration; activate the application (step 4). |
| Token request: `invalid_scope` | The token scope is not `<primary audience><scope>` exactly, or the client is not allowed to request it. | Check the audience and the scope character by character. If they are right, in the application's client configuration, under **Token issuance policy**, select **Add resources** and add the application's own `invoke` scope, then save. |
| Token issued, but the agent answers 401 or 404 | The audience, scope, or domain URL of the Hosted Application differ from the confidential application. | Compare `deploy.auth` with steps 2 and 5. These values are fixed at creation: correct `agent.yaml` and release with a new application name. |
| The verifier stops before calling OCI, naming `OCI_AGENT_IDCS_CLIENT_ID` or `OCI_AGENT_IDCS_CLIENT_SECRET` | The variable is neither in the tool's `.env` nor in the environment of Codex. | Add it to the tool's `.env` (section 8). |
| The demo page shows "service unavailable" | The `IDCS_*` values in `ui/.env.local` are missing or wrong. | Read the cause in the terminal that runs `npm run dev`; compare with sections 5–7 (section 9). |

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
  [Spec 010](../specs/010-jwt-inbound-authentication.md); credentials in the
  tool's `.env` and the demo UI:
  [Spec 022](../specs/022-idcs-credentials-for-ui-and-verifier.md).
