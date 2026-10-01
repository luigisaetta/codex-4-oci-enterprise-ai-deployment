# TODO

Planned work, from the project review of 2026-10-01. The project is dedicated
to developers who work with Codex: every item keeps Codex skills as the
primary interface. Items that change behavior become a specification in
`specs/` before implementation; documentation-only items do not.

## Plan

The table is the only priority order. Work proceeds by phase; within a phase,
follow the numbers unless a dependency says otherwise.

| # | Item | Depends on | Effort | Phase |
| --- | --- | --- | --- | --- |
| 2 | [Verify PowerShell parity](#2-verify-powershell-parity) | — | Low | Now |
| 3 | [Versioned release and compatibility check](#3-versioned-release-and-compatibility-check) | 2 | Low | Now |
| 5 | [Live check of runtime environment variables](#5-live-check-of-runtime-environment-variables) | — | Low | Live session |
| 6 | [Live acceptance of `public-idcs`](#6-live-acceptance-of-public-idcs) | identity-domain credentials (external) | Low | Live session |
| 7 | [Generative AI demo with resource principal](#7-generative-ai-demo-with-resource-principal) | 5 | Medium | Short term |
| 8 | [Skill `oci-agent-new` to scaffold an agent](#8-skill-oci-agent-new-to-scaffold-an-agent) | 7, 9 (agent API) | Medium | Short term |
| 9 | [Test UI for agents](#9-test-ui-for-agents) | 7 | Medium | Short term |
| 10 | [IAM pre-flight check (advisory)](#10-iam-pre-flight-check-advisory) | 5, 7 | Medium | Short term |
| 11 | [Diagnostics for a failed deployment](#11-diagnostics-for-a-failed-deployment) | — | Medium | Short term |
| 12 | [Configuration drift and update: scaling and runtime environment](#12-configuration-drift-and-update-scaling-and-runtime-environment) | 5 | Medium-high | Medium term |
| 13 | [Artifact pruning and application teardown](#13-artifact-pruning-and-application-teardown) | — | Low-medium | Medium term |
| 14 | [Multiple environments](#14-multiple-environments) | 12 | Medium | Medium term |
| 15 | [Private endpoint and custom networking](#15-private-endpoint-and-custom-networking) | service capabilities | High | Later |

Phases:

1. **Now**: no live access needed. Cheap steps that add credibility.
2. **Live session**: one session in eu-frankfurt-1, with explicit
   authorization. Items 5 and 6 each need a new application, because runtime
   variables and authentication are set only at creation. Keep them as two
   separate applications so that a failure is easy to attribute.
3. **Short term**: the main value step. The Codex workflow covers the whole
   path, from the developer's requirements to an agent that uses Generative
   AI, with a local UI to try it.
   Write the specifications of items 8 and 9 together: the standard agent API
   belongs to both.
4. **Medium term**: needed for continuous use across versions and
   environments.
5. **Later**: depends on what the service supports.

IAM is the dependency hub: the Vault check (5), the Generative AI demo (7),
the scaffold (8), and the pre-flight check (10) all need correct policies,
described in [IAM policies](docs/iam-policies.md). Items 5 and 7 confirm its
statements live; the automated check (10) comes only after those results.

## 2. Verify PowerShell parity

Parity between `scripts/*.sh` and `scripts/*.ps1` is declared but has never
been executed on the primary workstation. CI is out of scope by design, so
verification is local:

* routine: install PowerShell 7 on macOS (`brew install powershell`) and run
  the PowerShell tests after every script change;
* before a release tag: one pass on Windows, by hand or driven by Codex, for
  what only Windows can show (paths, Docker Desktop or Podman, encodings);
* record both results in Spec 007.

## 3. Versioned release and compatibility check

* Publish a tagged release (`v0.1.0`) after item 2, with an honest
  statement of what is verified locally and remotely.
* Declare the tested OCI CLI and SDK versions (today: SDK 2.187.0, CLI 3.94.0).
* Warn at startup when the installed OCI CLI version differs from the tested
  one.
* Document a manual smoke test (release and rollback on `hello-world`) to run
  before each tag, to detect service regressions. No scheduled runs.

## 5. Live check of runtime environment variables

Manifest `runtime.env` entries are implemented (Spec 006): literal `value`,
`from_env`, and `vault_secret_id` sources are validated, injected into the
local verification container, and passed to OCI as `environmentVariables`
when the Hosted Application is created.

Already known (2026-09-30):

* the local tests cover validation and source resolution;
* the live `hello-world` application, created by the deploy skill, carries its
  two literal (`PLAINTEXT`) variables, so the creation path works;
* the Spec 006 verification record still says "remote acceptance pending",
  and no test has checked that the running container actually receives the
  values.

To do:

* a dedicated test demo (for example `demos/env_probe/`), not `hello_world`,
  with a manifest that uses all three sources;
* its endpoint (for example `GET /config`) is public under `public-noauth`, so
  it returns only literal and `from_env` values, and for the Vault variable
  only whether it is present, never its value;
* live check, after a first release, that the endpoint returns the expected
  values;
* record whether the deployment or the Vault read fails without the Vault
  policy of [IAM policies](docs/iam-policies.md), and update the status of its
  Vault statements;
* record the results in Spec 006, and delete the test application when no
  longer needed.

The known limit (variables are set only at creation) is handled by item 12.

## 6. Live acceptance of `public-idcs`

The `public-idcs` profile is implemented and tested offline
([Spec 010](specs/010-jwt-inbound-authentication.md)). Until this item is
done, the only verified profile is `public-noauth`, which is not a production
security posture.

Blocker: the test needs the domain URL, audience, scope, client ID, and client
secret of a confidential application (new or reused) from the
identity-domain administrator.

Tests to do, in eu-frankfurt-1, with explicit authorization:

* release a new application (for example `text-stats-idcs`) with the
  `public-idcs` profile;
* run the verifier with `--functional`: token request, authenticated health
  and readiness, rejected unauthenticated `/health`, functional checks;
* call the endpoint with a token for another audience or scope, and record
  the status;
* confirm or correct the assumptions U1–U6 of Spec 010 (endpoint host, bearer
  header, protected probes, rejection status, token scope, HTTP Basic client
  authentication);
* check that no secret or token appears in any output, file, or command line;
* record the results in Spec 010, and delete the test application when no
  longer needed.

## 7. Generative AI demo with resource principal

The project helps ship an agent, not write one. Add a demo (for example
`demos/genai_chat/`): a LangGraph agent that calls an OCI Generative AI model
from inside the container with resource principal, falling back to an API-key
profile locally. It extends the design of `hello_world`, which already has
`GENAI_COMPARTMENT_ID`.

* First verify, with the test application of item 5, that the container
  receives the resource-principal environment; treat it as an assumption
  until then.
* Verify the demo remotely, not only locally, and update the status of the
  Generative AI statements in [IAM policies](docs/iam-policies.md).
* This demo becomes the single template for item 8.

## 8. Skill `oci-agent-new` to scaffold an agent

Today only a guide section supports developers starting from scratch. A skill
that prepares a new agent repository from the developer's requirements. The
Codex workflow then covers the whole path: create, build, push, deploy,
verify.

Input: a plain-language request, optionally backed by a requirements file
with fixed sections (for example `agent-requirements.md`, from a template the
skill provides): purpose, input and output of the agent API, tools, model,
access profile, runtime variables, functional checks, and whether a test UI
(item 9) is wanted. The skill asks only for the missing required values.

Output: `agent.yaml` (schema 2), `Dockerfile`, the agent code with `/health`
and `/ready`, the Generative AI access code of item 7, functional checks, and,
on request, the test UI of item 9.

Rules:

* generate the files from one maintained and tested template (the demo of
  item 7), never from a second copy, so that the scaffold and the demo cannot
  drift;
* the generated agent implements the standard agent API of item 9, so that
  the test UI works without changes;
* show the list of files before writing, and never overwrite an existing file;
* never invent a model identifier: ask for it, or take it from the service;
* acceptance: a freshly generated agent passes the build skill's local
  verification and its functional checks without manual edits.

## 9. Test UI for agents

A UI that lets a developer try an agent interactively, locally against the
container and remotely against the deployed endpoint. Codex develops it
within constraints fixed in the documentation (for example
`docs/test-ui-guidelines.md`), so that every generated UI is safe and
predictable.

Constraints to document and enforce:

* **A test tool, not a product.** It runs only on the developer's machine,
  bound to `127.0.0.1`. It is never part of the agent image and is never
  deployed to the Hosted Application.
* **Separate dependencies**, for example `ui/requirements.txt`, never in the
  agent's `requirements.txt` or `Dockerfile`.
* **One stack, server-side Python** (to choose in the specification, for
  example Streamlit). The browser never receives a token or a secret.
* **HTTP only.** The UI calls the agent through its public API, as the
  functional checks do, and never imports agent code: it tests what is
  actually deployed.
* **Standard agent API.** A minimal contract defined in the specification (for
  example a chat-style `POST` with a message and a session identifier), which
  agents created by item 8 implement. Agents with a different API declare it
  in the manifest, or need a custom UI.
* **Explicit target.** The developer chooses the local container or the
  deployed endpoint; the UI shows which one is active. Calls to a deployed
  endpoint follow the project rule: Codex asks for approval before starting
  the UI against it.
* **Authentication.** For `public-idcs`, the UI obtains the token through
  `scripts/idcs_token.py`, with the client credentials exported only in the
  shell that starts it. It never shows, logs, or stores the token or the
  secret, and has no input field for them.
* **What it shows**: request, response, HTTP status, and latency, plus the
  `/health` and `/ready` state of the target.
* **No persistence and no telemetry** by default: conversations are not saved.
* **Project conventions**: English, module header, Black and Pylint, offline
  tests with a mocked HTTP layer, and Bash and PowerShell launchers in parity
  if a launcher script is added.

Decide in the specification whether the UI is one generic tool in the tool
home or a copy generated into each agent repository. The generic tool avoids
drift; a generated copy can be customized per agent. Either way, the
constraints above apply.

## 10. IAM pre-flight check (advisory)

A read-only `scripts/check_iam_prereqs.sh` (and PowerShell twin) whose
findings appear in the deploy plan. It never creates policies.

Deciding from policy text whether a permission is granted is hard: statement
parsing, dynamic-group matching rules, compartment inheritance, and the
operator may not be allowed to read policies at all. So the check is
best-effort and advisory:

* findings are warnings in the plan, never a reason to stop the deploy;
* when policies cannot be read, it reports "unable to check", not a failure;
* it checks only the patterns documented in
  [IAM policies](docs/iam-policies.md) and confirmed live in items 5 and 7.

## 11. Diagnostics for a failed deployment

After IAM, the next obstacle is a deployment whose `/ready` never answers.
Document, in the verify skill and the guide, how to find the cause: work
request state and errors, and the application or container logs if the
service exposes them. Verify in the documentation what the service offers
before relying on it; add a read-only helper only if it simplifies the steps.

## 12. Configuration drift and update: scaling and runtime environment

One decision for one problem: what the deploy does when the configuration of
an existing application differs from the manifest. Today variables are set
only at creation and the deploy stops on a difference; changing a variable
requires recreating the application manually, which contradicts the "never
delete" approach. Write a single specification for both runtime environment
and scaling.

Scaling facts. Today the deploy skill does not set `scalingConfig`, so every
application gets the platform default. The live `text-stats` application
reports (2026-09-30): `minReplica` 1, `maxReplica` 3, `scalingType`
`REQUESTS_PER_SECOND`, `targetRpsThreshold` 50. The OCI Python SDK 2.187.0 and
OCI CLI 3.94.0 offer:

* `--scaling-config` on `hosted-application create` and on
  `hosted-application update`, with `minReplica`, `maxReplica`,
  `scalingType`, and one threshold per type;
* scaling types `CPU`, `MEMORY`, `CONCURRENCY`, and `REQUESTS_PER_SECOND`
  (`targetCpuThreshold`, `targetMemoryThreshold`,
  `targetConcurrencyThreshold`, `targetRpsThreshold`).

Step A, scaling at creation:

* an optional `deploy.scaling` section in `agent.yaml`, validated strictly:
  replica bounds, one scaling type, and only the matching threshold; without
  it, the platform default applies, as today;
* deploy: pass `--scaling-config` when creating the application; show the
  requested and the current scaling in the plan;
* on an existing application with different scaling, stop, as for the runtime
  environment;
* verify against the documentation and live: the allowed ranges, the
  threshold units, and whether the observed default is documented;
* if `minReplica` 0 is accepted, define its effect on `/ready` and on the
  verifier's wait times (cold start);
* tests with the fake `oci` for both script families, and documentation.

Step B, configuration update:

* a "Configuration update" release case using `hosted-application update`,
  for both runtime environment and scaling;
* the differences shown in the plan, applied only after explicit
  authorization;
* live verification, recorded in the specification.

## 13. Artifact pruning and application teardown

The lifecycle creates resources but never removes them, and the 20-artifact
limit is handled manually.

* First write a specification that revises the "never delete" principle
  stated in the README and Spec 009, and states exactly when deletion is
  allowed.
* Verify in the documentation how artifacts are deleted and whether the
  active artifact is protected.
* A `prune` option or skill: `--keep N`, inactive artifacts only, plan then
  apply.
* A `teardown` for test environments, with double confirmation.

## 14. Multiple environments

One `.env` per checkout; no notion of environment. Introduce `--env <name>`
reading `envs/<name>.env`, or an `environments:` section in the manifest.
Skills ask for the target environment together with the manifest, and
promoting the same tag from staging to production becomes an explicit request
to Codex.

The specification must decide how `deploy.application_name` maps to each
environment (one compartment per environment, or a name suffix), so that two
environments can never resolve to the same application.

## 15. Private endpoint and custom networking

Only public endpoints with Oracle-managed networking are supported, which
blocks many enterprise uses. Verify what the service supports (VCN, subnet,
private endpoint), then write a specification and add a `private` manifest
profile. At minimum, document clearly what is unsupported and the workaround;
this documentation-only step can be done earlier.
