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
| 1 | [Fix inconsistencies](#1-fix-inconsistencies) | — | Low | Now |
| 2 | [Verify PowerShell parity](#2-verify-powershell-parity) | — | Low | Now |
| 3 | [Versioned release and compatibility check](#3-versioned-release-and-compatibility-check) | 1, 2 | Low | Now |
| 4 | [Document IAM policies](#4-document-iam-policies) | — | Low-medium | Now |
| 5 | [Live check of runtime environment variables](#5-live-check-of-runtime-environment-variables) | 4 | Low | Live session |
| 6 | [Live acceptance of `public-idcs`](#6-live-acceptance-of-public-idcs) | identity-domain credentials (external) | Low | Live session |
| 7 | [Generative AI demo with resource principal](#7-generative-ai-demo-with-resource-principal) | 4, 5 | Medium | Short term |
| 8 | [Skill `oci-agent-new` to scaffold an agent](#8-skill-oci-agent-new-to-scaffold-an-agent) | 7 | Medium | Short term |
| 9 | [IAM pre-flight check (advisory)](#9-iam-pre-flight-check-advisory) | 4, 5, 7 | Medium | Short term |
| 10 | [Diagnostics for a failed deployment](#10-diagnostics-for-a-failed-deployment) | — | Medium | Short term |
| 11 | [Configuration drift and update: scaling and runtime environment](#11-configuration-drift-and-update-scaling-and-runtime-environment) | 5 | Medium-high | Medium term |
| 12 | [Artifact pruning and application teardown](#12-artifact-pruning-and-application-teardown) | — | Low-medium | Medium term |
| 13 | [Multiple environments](#13-multiple-environments) | 11 | Medium | Medium term |
| 14 | [Private endpoint and custom networking](#14-private-endpoint-and-custom-networking) | service capabilities | High | Later |

Phases:

1. **Now**: no live access needed. Cheap fixes that add credibility, plus the
   IAM documentation that items 5, 7, and 9 rely on.
2. **Live session**: one session in eu-frankfurt-1, with explicit
   authorization. Items 5 and 6 each need a new application, because runtime
   variables and authentication are set only at creation. Keep them as two
   separate applications so that a failure is easy to attribute.
3. **Short term**: the main value step. The Codex workflow covers the whole
   path, from an empty repository to an agent that uses Generative AI.
4. **Medium term**: needed for continuous use across versions and
   environments.
5. **Later**: depends on what the service supports.

IAM is the dependency hub: the Vault check (5), the Generative AI demo (7),
the scaffold (8), and the pre-flight check (9) all need correct policies. That
is why the documentation (4) comes first and the automated check (9) comes
only after live results.

## 1. Fix inconsistencies

* In `demos/hello_world/agent.yaml`, replace the compartment name in
  `GENAI_COMPARTMENT_ID` with an OCID placeholder, and the personal name in the
  functional check with a generic one. Update the copies of the example in
  Spec 006 and `docs/agent-manifest-reference.md`.
* Align `AGENTS.md` with the repository: it refers to a `src/` folder that does
  not exist, and says that reusable logic goes there, while it lives in
  `scripts/*.py`.
* Spec 010 still refers to "U1–U5" in the skills section and in acceptance
  criterion 3; the assumptions are now U1–U6.
* Confirm that the 49 tests skipped locally are all PowerShell tests, and
  record the result.

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

* Publish a tagged release (`v0.1.0`) after items 1 and 2, with an honest
  statement of what is verified locally and remotely.
* Declare the tested OCI CLI and SDK versions (today: SDK 2.187.0, CLI 3.94.0).
* Warn at startup when the installed OCI CLI version differs from the tested
  one.
* Document a manual smoke test (release and rollback on `hello-world`) to run
  before each tag, to detect service regressions. No scheduled runs.

## 4. Document IAM policies

IAM is out of scope for automation and is the likely first cause of failure.
Write `docs/iam-policies.md` with the dynamic group and the minimal policies
for:

* OCIR image pull by the Hosted Application;
* Vault secret read by the application runtime (needed by item 5);
* Generative AI calls with resource principal (needed by item 7).

Before writing the policies, verify in the documentation which
`resource.type` identifies the Hosted Application runtime in a dynamic-group
matching rule. Mark every statement not yet confirmed live as an assumption,
and confirm it in items 5 and 7.

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
* record whether the deployment or the Vault read fails without the IAM policy
  of item 4;
* record the results in Spec 006, and delete the test application when no
  longer needed.

The known limit (variables are set only at creation) is handled by item 11.

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
* Verify the demo remotely, not only locally.
* This demo becomes the single template for item 8.

## 8. Skill `oci-agent-new` to scaffold an agent

Today only a guide section supports developers starting from scratch. A skill
that, from a request such as "create a new OCI agent", prepares the
repository: `agent.yaml` (schema 2), `Dockerfile`, `/health` and `/ready`, the
Generative AI access code of item 7, and functional checks. The Codex workflow
then covers the whole path: create, build, push, deploy, verify.

Generate the files from one maintained and tested template (the demo of item
7), never from a second copy, so that the scaffold and the demo cannot drift.

## 9. IAM pre-flight check (advisory)

A read-only `scripts/check_iam_prereqs.sh` (and PowerShell twin) whose
findings appear in the deploy plan. It never creates policies.

Deciding from policy text whether a permission is granted is hard: statement
parsing, dynamic-group matching rules, compartment inheritance, and the
operator may not be allowed to read policies at all. So the check is
best-effort and advisory:

* findings are warnings in the plan, never a reason to stop the deploy;
* when policies cannot be read, it reports "unable to check", not a failure;
* it checks only the patterns documented in item 4 and confirmed live in items
  5 and 7.

## 10. Diagnostics for a failed deployment

After IAM, the next obstacle is a deployment whose `/ready` never answers.
Document, in the verify skill and the guide, how to find the cause: work
request state and errors, and the application or container logs if the
service exposes them. Verify in the documentation what the service offers
before relying on it; add a read-only helper only if it simplifies the steps.

## 11. Configuration drift and update: scaling and runtime environment

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

## 12. Artifact pruning and application teardown

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

## 13. Multiple environments

One `.env` per checkout; no notion of environment. Introduce `--env <name>`
reading `envs/<name>.env`, or an `environments:` section in the manifest.
Skills ask for the target environment together with the manifest, and
promoting the same tag from staging to production becomes an explicit request
to Codex.

The specification must decide how `deploy.application_name` maps to each
environment (one compartment per environment, or a name suffix), so that two
environments can never resolve to the same application.

## 14. Private endpoint and custom networking

Only public endpoints with Oracle-managed networking are supported, which
blocks many enterprise uses. Verify what the service supports (VCN, subnet,
private endpoint), then write a specification and add a `private` manifest
profile. At minimum, document clearly what is unsupported and the workaround;
this documentation-only step can be done earlier, with item 4.
