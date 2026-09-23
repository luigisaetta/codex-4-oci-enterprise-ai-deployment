# Using the OCI agent skills

## Purpose

This guide is the operator workflow for taking one agent release from source to
an OCI Generative AI Hosted Application. It explains when to invoke each of the
four Codex skills, which inputs to give them, and where an explicit approval is
required.

The skills are sequential:

```text
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

Manifest paths are relative to the repository root when commands are run
directly. An absolute path is also suitable when providing it to Codex.

## One-time workstation preparation

1. Open this repository as the Codex workspace, so its `.agents/skills` link
   makes the four skills discoverable.
2. Create the Conda environment named
   `codex-4-oci-enterprise-ai-deployment` and install the project development
   requirements.
3. Ensure Docker, Docker Buildx, curl, and OCI CLI are available. Docker must
   run Linux containers and support the required `linux/amd64` platform.
4. Copy `.env.example` to the ignored `.env` and set only tenancy-wide,
   non-secret values:

   ```dotenv
   OCI_REGION=eu-frankfurt-1
   OCI_COMPARTMENT_NAME=<target-compartment-name>
   OCIR_TENANCY_NAMESPACE=<object-storage-namespace>
   OCIR_USERNAME=<complete-ocir-login-username>
   ```

5. Configure OCI CLI authentication outside the repository. Do not put an OCI
   API key, private key, auth token, Docker password, or endpoint override in
   `.env` or `agent.yaml`.

The target Hosted Application runtime needs pre-existing IAM permission to pull
the private OCIR image. If the manifest uses a Vault secret, its runtime also
needs permission to read that secret. The skills declare neither policy.

## Step 0: inspect the agent manifest

Before creating a release, inspect the selected `agent.yaml`. It provides:

* `build`: build context and Dockerfile;
* `publish.repository`: OCIR repository below the tenancy namespace;
* `deploy`: Hosted Application name and the current `public-noauth` profile;
* optional `runtime.env`: safe runtime configuration; and
* `verify`: agent-specific functional checks.

`/health` and `/ready` are platform probes and are not placed in `verify`.
Use a literal `runtime.env.value` only for non-secret committed data,
`from_env` for tenancy-specific non-secret data, and `vault_secret_id` for
secrets. Updating runtime variables on an existing Hosted Application is not
implemented; a changed value requires an explicitly designed update workflow.

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
step changes only local Docker state; it does not contact OCIR or OCI.

Stop and correct the agent or its manifest if this step fails. Do not push an
unverified image.

## Step 2: publish the verified image to OCIR

Invoke **`oci-agent-push`** with the same manifest and tag:

```text
$oci-agent-push
<absolute path>/demos/hello_world/agent.yaml tag: 0.4.0
```

The skill reads the OCI region from `.env`, resolves its OCIR hostname through
`oci iam region list`, and presents the exact source and destination image
references. It then inspects the target repository.

If the repository is missing, the skill asks for authorization to create the
one private, mutable repository. Separately, the operator must run interactive
Docker login and enter the OCI auth token only at the password prompt. The
skill then asks again for authorization before tagging and pushing the image.

Expected outcome: the fully qualified OCIR image reference and registry digest.
Save the tag and digest as release evidence. A push does not create a Hosted
Application.

## Step 3: plan and deploy the Hosted Application release

Invoke **`oci-agent-deploy`** with the same manifest and tag:

```text
$oci-agent-deploy
<absolute path>/demos/hello_world/agent.yaml tag: 0.4.0
```

The first action is a read-only plan. Review these items before approving
creation:

* the resolved OCIR image URI and release tag;
* target compartment, application name, and derived deployment name;
* the public `NO_AUTH_CONFIG` endpoint posture and managed networking;
* every runtime-variable name and source; Vault values and references are not
  displayed; and
* any existing same-named application or deployment state.

If the plan is correct, explicitly authorize apply when the skill asks. It can
create a missing Hosted Application and the derived Hosted Deployment, or reuse
only a compatible `ACTIVE` application. It does not delete, replace, or update
an existing deployment. OCI creation is asynchronous: `CREATING` is a normal
intermediate state, not proof of failure.

Expected outcome: application and deployment OCIDs. Retain the application OCID
for the next step. Do not infer that a deployment is ready merely because the
create request was accepted.

## Step 4: verify the deployed release

Invoke **`oci-agent-verify-deployment`** with the same manifest and tag plus
the application OCID reported by deployment:

```text
$oci-agent-verify-deployment
<absolute path>/demos/hello_world/agent.yaml tag: 0.4.0
ocid1.generativeaihostedapplication.oc1.<region>.<unique-id>
```

The skill asks for explicit authorization to perform OCI reads and public,
unauthenticated GET probes. With approval, it checks that the application is
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
observed state and correct the specific issue before deciding whether to retry;
do not delete OCI resources or overwrite a deployment as an automatic recovery
action.

## Related documents

* [Skill catalog](../skills/README.md)
* [Agent manifest configuration](../specs/006-agent-manifest-configuration.md)
* [Windows with Rancher Desktop and WSL2](../notes/windows-rancher-desktop-wsl2.md)
* [Linux build machine over SSH](../notes/linux-build-machine-over-ssh.md)
