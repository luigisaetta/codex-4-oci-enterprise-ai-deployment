# Using the OCI agent skills

## Purpose

This guide is the operator workflow for taking one agent release from source to
an OCI Generative AI Hosted Application. It explains when to invoke each of the
Codex skills, which inputs to give them, and where an explicit approval is
required. The first skill, `oci-agent-new`, creates a new agent from an
approved specification (see
[Creating a new agent repository](#creating-a-new-agent-repository)); four
skills release it; `oci-agent-ui` optionally adds a local demo page for its
users.

Every skill can be selected from a natural request. Push and deploy still ask
for approval before each remote change.

The skills are sequential:

```text
create the agent from an approved specification (new agents only)
          |
          v
agent manifest + release tag
          |
          v
build and local verification --> push to OCIR --> plan and deploy --> verify deployed release
```

Do not skip a step. A successful local build is not evidence that an image was
pushed; a successful push is not evidence that OCI can run it.

## Concepts to provide every time

Each operation is defined by three distinct pieces of information:

| Item | Example | Purpose |
| --- | --- | --- |
| Agent manifest | `demos/hello_world/agent.yaml` | Stable agent-specific build, publish, deployment, runtime, and functional-check configuration. |
| Release tag | `0.4.0` | One explicit semantic version for the release. It is never stored in the manifest. |
| Application OCID | `ocid1.generativeaihostedapplication...` | Required only by the final remote verification step. |

Name the manifest and tag in the current request for every skill. Do not expect a
skill to infer them from a previous conversation, scan the repository, or choose
`hello_world` by default. The only shorthand allowed is an explicit instruction
to use the manifest from the immediately preceding step.

Manifest paths are relative to the current folder or absolute; build paths are
relative to the manifest folder. They must be inside `OCI_AGENT_ALLOWED_ROOTS`
when it is set, otherwise inside the nearest parent containing `.git` or the
manifest folder.

## One-time workstation preparation

Prepare the workstation once with [Getting started](getting-started.md):
tools, Conda environment, OCI CLI profile, the tool's `.env`, the skills, and
the setup check. The tenancy prerequisites are in
[For the administrator](getting-started.md#for-the-administrator) and
[IAM policies](iam-policies.md).

The scripts run inside the Conda environment
`codex-4-oci-enterprise-ai-deployment` (activated, or `conda run
--no-capture-output -n codex-4-oci-enterprise-ai-deployment ...`), or with the
interpreter set in `OCI_AGENT_PYTHON`.

## Creating a new agent repository

The recommended way is the `oci-agent-new` skill: open an empty folder outside
the tool home in a new Codex session and describe the agent. The folder may
sit beside the tool home under one parent project folder. On native Windows,
create it with the PowerShell command in
[Getting Started step 10](getting-started.md#10-create-your-first-agent).
The skill drafts a specification
(`agent-spec.md`, starting with the customer persona, use case, and expected
outcomes), stops for your review, and after your approval creates the files
below from it. See the [skill](../skills/oci-agent-new/SKILL.md) and the
[Quickstart](quickstart.md#1-open-your-agent-in-codex). The rest of this
section describes those files, for review or for writing them by hand.

An agent kept in its own repository needs four files in the agent's folder,
which is also the build context (`context: .` in the manifest):

Its `.gitignore` must exclude `__pycache__/`, `.pytest_cache/`, and `.env`.

| File | Source | What to fill in |
| --- | --- | --- |
| `Dockerfile` | `skills/oci-agent-build/assets/Dockerfile.template` | `{{REQUIREMENTS_PATH}}` = `requirements.txt`; `{{PACKAGE_DIR}}` = the folder with the agent's Python package; `{{APP_MODULE}}` = `<module>:<app>`, for example `my_agent.app:app`. |
| `requirements.txt` | Written by hand; there is no template. | The agent's runtime dependencies only. Prefer packages with `linux/amd64` wheels: the base image has no compiler, so a package that must be compiled fails the build. |
| `.dockerignore` | `skills/oci-agent-build/assets/dockerignore.template` | Nothing; copy it as is. |
| `agent.yaml` | `skills/oci-agent-build/assets/agent.yaml.template` | `{{AGENT_NAME}}`, `{{OCIR_REPOSITORY}}`, `{{APPLICATION_NAME}}`, and any `verify` checks. |

The container must follow the
[container requirements](../skills/oci-agent-build/references/container-requirements.md):
listen on `0.0.0.0:8080` and answer `GET /health` and `GET /ready` with HTTP
200. Local verification fails otherwise.

The target Hosted Application runtime needs pre-existing IAM permission to pull
the private OCIR image. If the manifest uses a Vault secret, its runtime also
needs permission to read that secret. The skills declare neither policy.

## Step 0: inspect the agent manifest

Before creating a release, inspect the selected `agent.yaml`; the
[agent manifest reference](agent-manifest-reference.md) describes every field.
It provides:

* `build`: build context and Dockerfile;
* `publish.repository`: OCIR repository below the tenancy namespace;
* `deploy`: Hosted Application name, an access profile, and (for `public-idcs`)
  identity-domain authentication settings;
* optional `runtime.env`: safe runtime configuration; and
* `verify`: agent-specific functional checks.

`/health` and `/ready` are platform probes and are not placed in `verify`.
Use a literal `runtime.env.value` only for non-secret committed data,
`from_env` for tenancy-specific data and for secrets such as API keys (from the
operator's shell, or from the tool's `.env`), and `vault_secret_id` for secrets
kept in OCI Vault. Updating runtime variables on an existing Hosted Application is not
implemented; a changed value requires an explicitly designed update workflow.

## Protect an agent with identity-domain tokens

For an endpoint that must require an OCI IAM identity-domain token, ask the
identity-domain administrator for the domain URL, primary audience, scope,
client ID, and client secret. Confirm whether the confidential application is
new or an existing application that will be reused. The primary audience and
scope must match that confidential application exactly.

Put only the three non-secret values in the manifest:

```yaml
deploy:
  profile: public-idcs
  auth:
    domain_url: <identity-domain-url>
    audience: <audience-of-the-confidential-application>
    scope: <scope-of-the-confidential-application>
```

The deploy checks the format of these values, but does not contact the identity
domain or test that they work. Verification is the step that tests them. Never
put the client ID, client secret, or an access token in `agent.yaml`, the
tenancy file, or the chat. The client secret and access token must never be
printed or stored.

## Step 1: build and verify the local image

Invoke **`oci-agent-build`** with the manifest and a new semantic release tag.
For example, in a Codex request:

```text
$oci-agent-build
<absolute path>/demos/hello_world/agent.yaml tag: 0.4.0
```

The skill checks the selected builder, builds a `linux/amd64` image, and runs a
local container verification. The verification checks image architecture,
startup, `/health`, `/ready`, and the functional check configured in the
manifest. It also injects applicable `runtime.env` values. Vault variables are
omitted locally unless the operator explicitly supplies the documented local
override; the override is never displayed.

Expected outcome: a locally verified image named `<manifest name>:<tag>`. This
step changes only local container-engine state; it does not contact OCIR or OCI.

Stop and correct the agent or its manifest if this step fails. Do not push an
unverified image.

## Step 2: publish the verified image to OCIR

Invoke **`oci-agent-push`** with the same manifest and tag:

```text
$oci-agent-push
<absolute path>/demos/hello_world/agent.yaml tag: 0.4.0
```

The skill reads the OCI region from the tenancy file, resolves its OCIR hostname through
`oci iam region list`, and presents the exact source and destination image
references. It then inspects the target repository.

If the repository is missing, the skill asks for authorization to create the
one private, mutable repository. Separately, the operator must run interactive
`docker login` or `podman login`, matching the selected engine, and enter
the OCI auth token only at the password prompt. The
skill then asks again for authorization before tagging and pushing the image.

Expected outcome: the fully qualified OCIR image reference and registry digest.
Save the tag and digest as release evidence. A push does not create a Hosted
Application.

## Step 3: plan and deploy the Hosted Application release

A deploy request authorizes only deployment. Creating an OCIR repository or
pushing an image requires a separate explicit request and authorization through
`oci-agent-push`.

Invoke **`oci-agent-deploy`** with the same manifest and tag:

```text
$oci-agent-deploy
<absolute path>/demos/hello_world/agent.yaml tag: 0.4.0
```

The first action is a read-only plan. Review these items before approving the
release:

* the resolved OCIR image URI and release tag;
* target compartment and application name;
* the public `NO_AUTH_CONFIG` endpoint posture and managed networking;
* every runtime-variable name and source; Vault values and references are not
  displayed; and
* any existing same-named application or deployment state.

If the plan is correct, explicitly authorize apply when the skill asks. The
deploy skill handles `First release`, `Already released`, `New version`, and
`Return to a previous version` (rollback). It also reports
`Creation in progress` for a deployment that needs more waiting and
`Application creation in progress` for an application whose first deployment
will be created after it becomes `ACTIVE` and passes configuration checks.
`Failed deployment` reports the OCI error and stops. Only after you request
a new deploy of that failed release and approve its replacement plan does
`Replace failed deployment` delete the `FAILED` deployment and create a new
one. See [oci-agent-deploy](../skills/oci-agent-deploy/SKILL.md#release-cases) for the
full release rules. OCI creation is asynchronous: `CREATING` is a normal
intermediate state, not proof of failure.

The deploy wait timeout is 1800 seconds by default; use `--timeout-seconds`
(`-TimeoutSeconds` in PowerShell) to set it. Exit 26 means OCI is still
working: the script reports the OCID, state, and elapsed time, and did not
change or delete anything else after the request. Ask to run deploy again to
resume waiting. Do not delete or recreate because of a timeout. If creation
fails with a node-pool capacity error, try again later, then request a new
deploy. Replacement requires `--replace-failed` (`-ReplaceFailed` in
PowerShell), an existing `FAILED` deployment, your request, and your approval
of the plan.

Expected outcome: application and deployment OCIDs. Retain the application OCID
for the next step. Do not infer that a deployment is ready merely because the
create request was accepted.

## Release a new version or roll back

Build and push the new tag as usual, then deploy that tag to the same
application. To roll back, deploy the previous tag. The endpoint does not
change; the verifier waits within its timeout while the deployment is
`UPDATING`.

## Clean up old artifacts

Cleanup is manual and outside the skills: only inactive artifacts may be
removed. An application has a limit of 20 artifacts.

## Step 4: verify the deployed release

Invoke **`oci-agent-verify-deployment`** with the same manifest and tag plus
the application OCID reported by deployment:

```text
$oci-agent-verify-deployment
<absolute path>/demos/hello_world/agent.yaml tag: 0.4.0
ocid1.generativeaihostedapplication.oc1.<region>.<unique-id>
```

For `public-idcs`, export `OCI_AGENT_IDCS_CLIENT_ID` and
`OCI_AGENT_IDCS_CLIENT_SECRET` in your own shell before requesting verification.
Do not paste either value into chat. The client secret and the access token are
never printed or stored. `OCI_AGENT_IDCS_TOKEN_SCOPE` is optional when the
identity domain requires an exact token scope other than the manifest-derived
one. The verifier exits 24 if it cannot obtain an access token, and 25 if a
protected endpoint accepts an unauthenticated request.

The skill asks for explicit authorization to perform OCI reads and public GET
probes. With approval, it checks that the application is
`ACTIVE`, exactly one associated deployment is `ACTIVE`, and that the active
artifact tag equals the requested release. Only then does it poll:

```text
/actions/invoke/health
/actions/invoke/ready
```

Both must return HTTP 200 for success. A healthy response with a non-200 ready
response means the container is running but has not completed initialization;
the verifier continues polling within its bounded timeout.

Expected outcome: application and deployment OCIDs, expected tag, endpoint host,
health and ready HTTP statuses, readiness duration, and `PASS` or a precise
failure result. The default verifier never invokes the agent's business API.

## Call a protected agent

For a `public-idcs` agent, obtain an access token through the OAuth 2.0 client
credentials grant from `<identity-domain-url>/oauth2/v1/token`, using the
confidential application's client ID and client secret, then send
`Authorization: Bearer <token>` with the request. Keep the client secret and
access token out of chat, output, and files.

The exact endpoint host, bearer-header behavior, protection of health and
readiness, unauthenticated rejection status, token scope construction, and
HTTP Basic client authentication are assumptions U1–U6 in
[Spec 010](../specs/010-jwt-inbound-authentication.md#assumptions-to-confirm-during-the-live-acceptance).
They remain pending the live acceptance; do not treat this guidance as a
completed production-security acceptance.

## Optional functional check after deployment

The manifest's `verify` entries are business requests, such as `POST /hello`.
They are intentionally excluded from the default remote verifier. Ask for a
separate, explicit authorization to invoke them, then use the verifier's
`--functional` mode. A successful health/readiness verification is not a
functional or security certification.

## Normal release transcript

For a new release of one selected agent, the conversation follows this shape:

```text
1. $oci-agent-build
   <manifest path> tag: <new-version>

2. $oci-agent-push
   <same manifest path> tag: <same-version>
   -> authorize repository creation if needed
   -> authenticate with docker login
   -> authorize push

3. $oci-agent-deploy
   <same manifest path> tag: <same-version>
   -> review plan
   -> authorize apply

4. $oci-agent-verify-deployment
   <same manifest path> tag: <same-version>
   <application OCID from step 3>
   -> authorize OCI reads and public GET probes
```

Never reuse a release tag for a different image. If any step fails, report the
observed state and correct the specific issue before deciding whether to retry.
Never delete or recreate an application or a deployment, except a `FAILED`
deployment on the user's explicit replacement request and approval of its plan.

## Windows workstations

The skills run the repository scripts, and every script exists as a Bash file
(`scripts/*.sh`) and a PowerShell 7.4+ twin (`scripts/*.ps1`) with the same
options, report lines, and exit codes. The shell in use decides which family
runs, so the skill workflow above is the same on every platform. Windows offers
two paths; choose one per workstation:

| Path | You work in | The skills run | Engine | Setup note |
| --- | --- | --- | --- | --- |
| Native PowerShell | `pwsh` 7.4+ | `.\scripts\*.ps1 -Manifest ... -Tag ...` | Docker Desktop or Podman, via `-ContainerEngine` | [Native PowerShell 7](../notes/windows-powershell-native.md) |
| WSL2 | Bash inside WSL2 | `scripts/*.sh --manifest ... --tag ...` | Rancher Desktop with Moby | [Rancher Desktop with WSL2](../notes/windows-rancher-desktop-wsl2.md) |

On the native path, the scripts read the tenancy file themselves; set
`OCI_AGENT_ENV_FILE` only when it is not `<tool home>/.env`.

Registry login is `docker login` or `podman login`, matching the engine that
built the image. Local verification binds to `127.0.0.1` only. The mapping
between Bash options and PowerShell parameters is in the
[skill catalog](../skills/README.md#choosing-bash-or-powershell).

## Related documents

* [Quickstart](quickstart.md), the plain-language path for end users
* [Agent manifest reference](agent-manifest-reference.md), every `agent.yaml` field
* [Skill catalog](../skills/README.md), including the Bash/PowerShell rule
* [Agent manifest configuration](../specs/006-agent-manifest-configuration.md)
* [Windows PowerShell workflow support](../specs/007-windows-powershell-support.md)
* [Windows with native PowerShell 7](../notes/windows-powershell-native.md)
* [Windows with Rancher Desktop and WSL2](../notes/windows-rancher-desktop-wsl2.md)
* [Linux build machine over SSH](../notes/linux-build-machine-over-ssh.md)
