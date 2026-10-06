# IAM policies for OCI Hosted Applications

The skills never create or change IAM policies or dynamic groups. A tenancy
administrator sets them up once, before the first release. This page lists
what is needed, who needs it, and how sure we are of each statement.

Two kinds of principals need permissions:

| Principal | What it is | Needs permissions to |
| --- | --- | --- |
| **Operator** | The OCI user (in an IAM group) whose OCI CLI profile runs the skills. | Find the compartment, manage the OCIR repository, create and update Hosted Applications and Deployments, read their state. |
| **Runtime** | The Hosted Application and its deployments, as members of a dynamic group. | Pull the image from OCIR; optionally read Vault secrets and call OCI services such as Generative AI. |

## How to read the status column

| Status | Meaning |
| --- | --- |
| Documented | Stated in the linked Oracle documentation. |
| Derived | Not stated for this service, but follows from documented verb and permission tables. |
| Assumption | Plausible, not confirmed. To be confirmed live. |
| Verified live (date) | Confirmed by a recorded test in a specification. |

Live verifications are recorded in the specifications; this page names them
in the status column.

In every statement, replace the placeholders:

* `<operator-group>`: the IAM group of the operators;
* `<runtime-dynamic-group>`: the dynamic group defined below;
* `<compartment-name>` and `<compartment-ocid>`: the compartment set by
  `OCI_COMPARTMENT_NAME` in `.env`;
* `<vault-compartment-name>`, `<genai-compartment-name>`: the compartments of
  the Vault secrets and of the Generative AI project, if different.

In an identity domain other than `Default`, prefix group and dynamic-group
names with the domain name, for example `'<domain-name>'/'<operator-group>'`.

## Runtime: dynamic group

Restrict the dynamic group to the target compartment (least privilege). A
dynamic group matches a resource when any of its rules matches, so use three
rules:

```text
all {resource.type='generativeaihostedapplication', resource.compartment.id='<compartment-ocid>'}
all {resource.type='generativeaihostedapplicationiam', resource.compartment.id='<compartment-ocid>'}
all {resource.type='generativeaihosteddeployment', resource.compartment.id='<compartment-ocid>'}
```

Status: Documented. The tenancy-wide variant is a single
`any {resource.type='generativeaihostedapplication', resource.type='generativeaihostedapplicationiam', resource.type='generativeaihosteddeployment'}`
rule; prefer it only for sandbox tenancies.

`generativeaihostedapplicationiam` covers applications that use OCI IAM
request signing for inbound calls. The skills do not create them (Spec 010
non-goals); keeping the rule is harmless and follows the documentation.

## Runtime: policies

| Purpose | Statement | Needed when | Status |
| --- | --- | --- | --- |
| Pull the image from OCIR | `allow dynamic-group <runtime-dynamic-group> to read repos in compartment <compartment-name>` | Always | Documented |
| Read Vault secrets passed as runtime variables | `allow dynamic-group <runtime-dynamic-group> to read secret-bundles in compartment <vault-compartment-name>` | The manifest uses `vault_secret_id` | Derived |
| Call Generative AI with Resource Principal (`GENAI_AUTH_MODE=resource_principal`) | `allow dynamic-group <runtime-dynamic-group> to use generative-ai-family in compartment <genai-compartment-name>` and `allow dynamic-group <runtime-dynamic-group> to use generative-ai-project in compartment <genai-compartment-name>` | The agent uses Resource Principal | Verified live (2026-10-06, Spec 016), through an equivalent broader statement; see the notes |
| Call Generative AI with an API key (`GENAI_AUTH_MODE=api_key`, the default) | `allow any-user to use generative-ai-family in compartment <genai-compartment-name> where ALL {request.principal.type='generativeaiapikey'}` | The agent uses `GENAI_API_KEY` | Observed (2026-10-06) in a tenancy where API-key calls work, with the `manage` verb |
| Other OCI services | One statement per service, for example `read object-family` | The agent calls them | Documented (as a pattern) |

Notes:

* **OCIR**: the repository must be in a compartment covered by the statement.
  The skills create it in `OCI_COMPARTMENT_NAME`.
* **Vault**: reading the value of a secret (`GetSecretBundle`) requires
  `SECRET_BUNDLE_READ`, which the `read` verb grants on `secret-bundles`.
  The Generative AI documentation does not state this policy for Hosted
  Applications. The live check of runtime variables must record whether the
  deployment, or only the agent, fails without it.
* **Generative AI with Resource Principal** (Spec 016): the Hosted Deployment
  receives a Resource Principal and the agent signs its calls with the
  `oci-genai-auth` library. OCI OpenAI-compatible calls require a Generative
  AI project (`GENAI_PROJECT_ID`), hence the `generative-ai-project`
  statement; `<genai-compartment-name>` is the project's compartment. In the
  verified tenancy the call was authorized by existing broader statements
  (`allow any-user to manage generative-ai-family` and `… generative-ai-project`
  on the compartment, without conditions); the dedicated dynamic-group
  statements above are the recommended least-privilege form, not yet tested in
  isolation. Which narrower resource type covers the Responses API is not
  documented; `generative-ai-family` is the safe choice.
* **Generative AI with an API key** (Spec 015): the request principal is the
  API key, so the statement uses `any-user` with a
  `request.principal.type='generativeaiapikey'` condition, as in
  [Adding Key Permissions](https://docs.oracle.com/en-us/iaas/Content/generative-ai/add-api-permission.htm).
* **Dynamic group in another identity domain**: in the verified tenancy the
  runtime dynamic group lives in a secondary identity domain; the policy names
  it as `'<domain-name>'/'<dynamic-group-name>'`. A tenancy-wide rule on
  `generativeaihostedapplication` and `generativeaihosteddeployment` works; the
  policies limit access to the compartment.

## Operator: policies

The statements cover exactly the OCI operations that the scripts run. Build
needs no OCI permission.

| Skill | OCI operations used by the scripts | Statement | Status |
| --- | --- | --- | --- |
| Push, deploy | `iam region list` (OCIR endpoint) | `allow group <operator-group> to inspect tenancies in tenancy` | Assumption |
| Push, deploy | `iam compartment list` on the tenancy subtree, to resolve `OCI_COMPARTMENT_NAME` | `allow group <operator-group> to inspect compartments in tenancy` | Documented |
| Push | `artifacts container repository list` and `create`, `docker push` | `allow group <operator-group> to manage repos in compartment <compartment-name>` | Documented |
| Deploy | `hosted-application list`, `get`, `create` | `allow group <operator-group> to manage generative-ai-hosted-application in compartment <compartment-name>` | Documented |
| Deploy | `hosted-deployment list`, `get`, `create`, `update` (activate), add artifact | `allow group <operator-group> to manage generativeaihosteddeployment in compartment <compartment-name>` | Documented (see the naming note) |
| Deploy | waits on `create` and `update` (`--wait-for-state`) | `allow group <operator-group> to read generative-ai-work-request in compartment <compartment-name>` | Derived |
| Verify | `hosted-application get`, `hosted-deployment list` and `get` | covered by the deploy statements; a verify-only group needs `read` on the two hosted resource types | Derived |

Notes:

* **Region list**: `ListRegions` requires `TENANCY_INSPECT`. Whether an
  operator needs an explicit statement for it is not confirmed; add the
  statement only if `oci iam region list` fails.
* **Compartment lookup**: the scripts search the whole tenancy subtree by
  name, so `inspect compartments` is needed at the tenancy level.
* **Push, least privilege**: pushing requires `REPOSITORY_READ` and
  `REPOSITORY_UPDATE`; creating the repository requires `REPOSITORY_CREATE`;
  the existence check requires `REPOSITORY_INSPECT`. Instead of plain `manage
  repos`, you can use:

  ```text
  allow group <operator-group> to manage repos in compartment <compartment-name> where any {request.permission='REPOSITORY_INSPECT', request.permission='REPOSITORY_READ', request.permission='REPOSITORY_UPDATE', request.permission='REPOSITORY_CREATE'}
  ```

  Status: Derived from the documented example, which also uses
  `target.repo.name` to restrict access to named repositories.
* **Hosted Applications**: `CreateHostedApplication` requires `manage`; `use`
  allows only list, get, and update.
* **Naming of the deployment resource type**: the deployment-permissions page
  uses `generativeaihosteddeployment` in its policy examples, while the list
  of Generative AI resource types names it `generative-ai-hosted-deployment`.
  Confirm live which spelling the policy engine accepts, and record it here.
* **Vault variables**: whether creating an application with `VAULT` runtime
  variables also requires the operator to read the secret is not documented.
  The live check of runtime variables must record it.
* **Broad alternative**: `allow group <operator-group> to manage
  generative-ai-family in compartment <compartment-name>` covers the hosted
  resource types and work requests, but also every other Generative AI
  resource. Oracle recommends it only for administrators or sandbox groups.
* **Docker login**: pushing also needs the operator's OCI auth token, typed
  only at Docker's password prompt; see the
  [OCIR authentication reference](../skills/oci-agent-push/references/ocir-authentication.md).
  It is a credential, not a policy.

## Minimal setup, in one place

For an operator group and a runtime dynamic group in one compartment, with an
agent that calls Generative AI with Resource Principal:

```text
allow group <operator-group> to inspect compartments in tenancy
allow group <operator-group> to manage repos in compartment <compartment-name>
allow group <operator-group> to manage generative-ai-hosted-application in compartment <compartment-name>
allow group <operator-group> to manage generativeaihosteddeployment in compartment <compartment-name>
allow group <operator-group> to read generative-ai-work-request in compartment <compartment-name>

allow dynamic-group <runtime-dynamic-group> to read repos in compartment <compartment-name>
allow dynamic-group <runtime-dynamic-group> to use generative-ai-family in compartment <genai-compartment-name>
allow dynamic-group <runtime-dynamic-group> to use generative-ai-project in compartment <genai-compartment-name>
```

Drop the last two statements if the agent does not call Generative AI with
Resource Principal. With an API key, use the `any-user … generativeaiapikey`
statement of the table instead. Add `read secret-bundles` only for Vault
variables. Statements on the tenancy (`in tenancy`) must be in a policy attached to
the root compartment.

## Sources

Verified on 2026-10-01:

* [Permissions for Deploying Applications](https://docs.oracle.com/en-us/iaas/Content/generative-ai/deploy-permissions.htm):
  dynamic-group rules, OCIR pull, operator policies for applications and
  deployments.
* [IAM Policies for OCI Generative AI](https://docs.oracle.com/en-us/iaas/Content/generative-ai/iam-policies.htm):
  resource types of `generative-ai-family`.
* [API-Level Permissions for Applications](https://docs.oracle.com/en-us/iaas/Content/generative-ai/application-permissions.htm):
  verbs of `generative-ai-hosted-application`.
* [Models, Clusters, and Keys: API Permissions](https://docs.oracle.com/en-us/iaas/Content/generative-ai/model-permissions.htm):
  `generative-ai-chat` and `generative-ai-work-request`.
* [Container Registry policy reference](https://docs.oracle.com/en-us/iaas/Content/Identity/policyreference/registrypolicyreference.htm)
  and [Policies to control repository access](https://docs.oracle.com/en-us/iaas/Content/Registry/Concepts/registrypolicyrepoaccess.htm):
  `repos` verbs and push permissions.
* Verified on 2026-10-06:
  [Projects](https://docs.oracle.com/en-us/iaas/Content/generative-ai/projects.htm)
  (`generative-ai-project`, project required for OpenAI-compatible calls) and
  [Generative AI IAM-Based Authentication](https://docs.oracle.com/en-us/iaas/Content/generative-ai/oci-genai-auth.htm)
  (`oci-genai-auth`, Resource Principal).
* [Vault policy reference](https://docs.oracle.com/en-us/iaas/Content/Identity/Reference/keypolicyreference.htm):
  `secret-bundles` and `GetSecretBundle`.
* [IAM policy reference](https://docs.oracle.com/en-us/iaas/Content/Identity/Reference/iampolicyreference.htm):
  `compartments` verbs and the `ListRegions` permission.

No API-level permission table for Hosted Deployments was found; the deploy
statements follow the documented examples.
