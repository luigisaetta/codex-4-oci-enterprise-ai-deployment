# Spec 016: Resource Principal for agents that call OCI Generative AI

Status: implemented; live experiment passed; V2, V5, and the dedicated policies in isolation unverified.
Date: 2026-10-06.

## Problem

Agents created with `oci-agent-new` call OCI Generative AI with an API key
(`GENAI_API_KEY`, Spec 015). A key is a secret to create, store, rotate, and
protect, and a rotated key cannot reach an existing Hosted Application
(runtime variables are set only at creation). Oracle recommends API keys for
testing and IAM-based authentication for production and OCI-managed
environments. A Hosted Application can authenticate as itself with Resource
Principal, so the agent needs no secret at all.

## Scope

* A second authentication mode for agents, **Resource Principal**, selected by
  a runtime variable. API-key mode stays the default for new agents; Resource
  Principal is used when the specification asks for it.
* The Generative AI project that OCI OpenAI-compatible calls require.
* The IAM policies for the runtime dynamic group.
* The code pattern, written into the `oci-agent-new` guidelines and template.
* A live experiment that confirms the open points before the guidelines are
  changed.

## Non-goals

* Any change to the tool's scripts: authentication happens inside the agent;
  the manifest only declares literal runtime variables.
* Resource Principal for anything other than OCI Generative AI calls.
* Using Resource Principal in the local verification container: OCI provides
  it only to resources running in OCI (see "Local verification").
* Creating the Generative AI project or the IAM policies: an administrator
  does it once, as for the other prerequisites in `docs/iam-policies.md`.
* Changing the default: API-key mode (Spec 015) remains the default.

## Platform facts (verified in documentation, 2026-10-06)

| # | Fact | Source |
| --- | --- | --- |
| F1 | IAM-based authentication is recommended for production workloads and OCI-managed environments; API keys for testing and early development. | [OCI OpenAI-Compatible Endpoints](https://docs.oracle.com/en-us/iaas/Content/generative-ai/openai-compatible-api.htm) |
| F2 | The library is `oci-genai-auth` (`pip install oci-genai-auth`). It signs OpenAI SDK requests through an `httpx` auth handler; `OciResourcePrincipalAuth` uses the credentials that OCI injects into managed services. The client uses `api_key="not-used"`. | [Generative AI IAM-Based Authentication](https://docs.oracle.com/en-us/iaas/Content/generative-ai/oci-genai-auth.htm), [oci-genai-auth-python](https://github.com/oracle-samples/oci-genai-auth-python) |
| F3 | "OCI OpenAI-compatible API calls require a project"; the project OCID is passed as `project=` to the OpenAI client. A project holds data-retention and memory settings. | [OCI Responses API](https://docs.oracle.com/en-us/iaas/Content/generative-ai/responses-api.htm), [Projects](https://docs.oracle.com/en-us/iaas/Content/generative-ai/projects.htm) |
| F4 | Users need `use generative-ai-project` on the project's compartment. | [Projects](https://docs.oracle.com/en-us/iaas/Content/generative-ai/projects.htm) |
| F5 | Resources authenticate through a dynamic group and policies granting it access to Generative AI; the example statement is `use generative-ai-chat`. | [IAM Policies for OCI Generative AI](https://docs.oracle.com/en-us/iaas/Content/generative-ai/iam-policies.htm) |

Observed, not documented: three agents (`order_processing`,
`order_processing2`, `express_order`) called the Responses API with an API key
and **without** a project, successfully (2026-10-01 to 2026-10-06). This
contradicts F3; the specification follows F3.

## Open points, to confirm in the live experiment

| # | Question |
| --- | --- |
| V1 | Answered offline (2026-10-06): the `oci-genai-auth` 1.1.1 wheel exports `OciResourcePrincipalAuth`, `OciUserPrincipalAuth`, `OciSessionAuth`, and `OciInstancePrincipalAuth` from the module `oci_genai_auth`; it depends on `httpx` and `oci>=2.150.1`. `OciResourcePrincipalAuth()` creates its signer in the constructor (`oci.auth.signers.get_resource_principals_signer`), so it fails where no Resource Principal exists. |
| V2 | With Resource Principal, does a call without `project` fail, and with which error? |
| V3 | Which resource type covers the Responses API in a policy? `generative-ai-family` is the safe start; can it be narrowed? |
| V4 | Does the Hosted Deployment container receive the Resource Principal environment, and as which resource type of the dynamic group? |
| V5 | Can a deployment in one region call the Generative AI endpoint of another region with Resource Principal? |

## Intended behavior

### Runtime variables of the agent

| Variable | Source | Mode |
| --- | --- | --- |
| `GENAI_AUTH_MODE` | `value`: `api_key` (default) or `resource_principal` | both |
| `GENAI_PROJECT_ID` | `value`: the project OCID (not a secret) | required for `resource_principal`; recommended for `api_key` (F3), passed when set |
| `GENAI_MODEL`, `GENAI_REGION` | `value` (guideline B1, B2) | both |
| `GENAI_API_KEY` | `from_env` (Spec 015) | `api_key` only |

### Code pattern

```python
import httpx
from openai import OpenAI
from oci_genai_auth import OciResourcePrincipalAuth


def make_client(region: str, project: str, mode: str, api_key: str = "") -> OpenAI:
    """Create the OCI Generative AI client for the selected auth mode."""
    base_url = f"https://inference.generativeai.{region}.oci.oraclecloud.com/openai/v1"
    if mode == "resource_principal":
        return OpenAI(
            base_url=base_url,
            api_key="not-used",
            project=project,
            http_client=httpx.Client(auth=OciResourcePrincipalAuth(), timeout=30.0),
        )
    return OpenAI(base_url=base_url, api_key=api_key, project=project or None, timeout=30.0)
```

* The client is created **at the first LLM call**, not at startup, because
  `OciResourcePrincipalAuth()` needs the Resource Principal already in its
  constructor (V1).
* At startup the agent validates only that the variables are present and
  `GENAI_AUTH_MODE` is a supported value; `/ready` never depends on the
  Resource Principal.
* A failed authentication is logged on stderr (type and cause, no secret) and
  answered with HTTP 502, as for any LLM failure (guidelines B3, Q3).
* `oci-genai-auth` is added to the agent's `requirements.txt`.

### Local verification

The local container has no Resource Principal. With `resource_principal`
mode, the build verification passes on the deterministic functional check
(guideline B5); LLM calls answer 502 locally, which is expected. The LLM path
is verified after the deploy with `oci-agent-verify-deployment --functional`.

### IAM

Added to `docs/iam-policies.md`, for the existing runtime dynamic group:

```text
allow dynamic-group <runtime-dynamic-group> to use generative-ai-project in compartment <compartment-name>
allow dynamic-group <runtime-dynamic-group> to use generative-ai-family in compartment <compartment-name>
```

`<compartment-name>` is the compartment of the Generative AI project. The
second statement is narrowed after V3, if possible.

## Steps

1. **Live experiment** (with explicit authorization): an administrator
   creates a project and the policies; a copy of an existing LLM agent with
   `GENAI_AUTH_MODE=resource_principal` and `GENAI_PROJECT_ID` is built,
   deployed, and verified with `--functional`; V1–V5 are answered and
   recorded here, including the error of a call without project (V2).
2. **Tool update**, with the confirmed facts only:
   * `oci-agent-new` guidelines: B2 (auth modes, project), Q1 (code pattern),
     Q4 (no credentials at startup), and the local-verification note;
   * the specification template, Configuration section: auth mode and
     project;
   * `docs/iam-policies.md`: the two statements, with their verified status;
   * README manifest example and `CHANGELOG.md`.

## Acceptance criteria

1. A Hosted Application with `GENAI_AUTH_MODE=resource_principal`, no
   `GENAI_API_KEY`, and a project answers a functional request that calls the
   LLM, verified with `oci-agent-verify-deployment --functional`.
2. Its local build verification passes without any OCI credential.
3. V1–V5 are answered in the verification record.
4. A new agent created with `oci-agent-new` uses API-key mode by default, and
   Resource Principal when its specification asks for it, stating the project
   and the policies.

## Verification record

### 2026-10-06, offline (test agent prepared)

* Test agent `~/Progetti/express_order_rp`: a copy of `express_order` without
  its local key file, UI, or Git history; application `express-order-demo-rp`;
  `GENAI_AUTH_MODE=resource_principal` and `GENAI_PROJECT_ID` (placeholder,
  rejected at startup until replaced); `oci-genai-auth` and `httpx` added; the
  client is created through `make_client` at the first LLM call.
* In an isolated virtual environment with the agent's requirements
  (`oci-genai-auth` 1.1.1, `oci` 2.187.2), without any OCI credential:
  `/ready` 200; the deterministic check (`POST /express-orders` with `{}`) 400;
  an LLM request 502 with the stderr log "LLM call failed: OSError:
  OCI_RESOURCE_PRINCIPAL_VERSION is not defined", as expected outside OCI. An
  invalid project OCID is rejected at startup. The manifest passes
  `new_agent.py check-manifest`.
* V4 detail: the signer needs `OCI_RESOURCE_PRINCIPAL_VERSION` (and the other
  Resource Principal variables) in the container; the live test confirms
  whether the Hosted Deployment injects them.

### 2026-10-06, live experiment, eu-frankfurt-1

* Read-only inspection before the test: the runtime dynamic group already
  exists as `'OracleIdentityCloudService'/'dg-hosted-deployments'` (rule: every
  `generativeaihostedapplication` and `generativeaihosteddeployment` in the
  tenancy), used for the OCIR pull (`read repos` on the deployment
  compartment). The compartment's policies already contain, without
  conditions, `allow any-user to manage generative-ai-family` and `allow
  any-user to manage generative-ai-project`. An ACTIVE project `proj01`
  exists in the compartment (eu-frankfurt-1); the test agent uses it. No
  policy was created.
* The operator released `express-order-demo-rp` with Codex (build, push,
  deploy, verification) and called the deployed endpoint with a request that
  needs the LLM: the agent answered correctly with Resource Principal and no
  API key. Acceptance criteria 1 and 2 passed (local verification had already
  passed without credentials).
* V4: answered — the Hosted Deployment provides the Resource Principal to the
  container, and `OciResourcePrincipalAuth` works there.
* V3: partly answered — the call is authorized by the existing broad
  `any-user` statements; the dedicated dynamic-group statements of this
  specification were not created, so their sufficiency and a narrower
  resource type remain unverified.
* V2 (call without project) and V5 (cross-region call) were not tested: the
  project was set and the LLM is in the deployment region.

### 2026-10-06, step 2 (tool update)

* `oci-agent-new` guidelines: B2 (the two authentication modes, project, API
  key as default), Q1 (`make_client` for both modes), Q4 (no LLM client at
  startup; local 502 in Resource Principal mode is expected).
* Specification template: LLM authentication in the Configuration section.
* `docs/iam-policies.md`: Resource Principal and API-key statements with their
  status, notes on the project, the broad statements that authorized the live
  test, and dynamic groups in a secondary identity domain.
* README (Security) and `CHANGELOG.md`.

