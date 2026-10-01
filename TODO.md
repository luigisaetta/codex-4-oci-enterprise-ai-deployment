# TODO

Planned work, in priority order. Each item becomes a specification in `specs/`
before implementation.

## 1. Verify runtime environment variables end to end

Manifest `runtime.env` entries are already implemented (Spec 006): literal
`value`, `from_env`, and `vault_secret_id` sources are validated, injected into
the local verification container, and passed to OCI as `environmentVariables`
when the Hosted Application is created.

Already known (2026-09-30):

* the local tests cover validation and source resolution;
* the live `hello-world` application, created by the deploy skill, carries its
  two literal (`PLAINTEXT`) variables, so the creation path works;
* the Spec 006 verification record still says "remote acceptance pending",
  and no test has checked that the running container actually receives the
  values.

To do:

* a test agent that exposes non-secret variables through an endpoint (for
  example `GET /config`), with a manifest that uses all three sources;
* live check, after a first release, that the endpoint returns the expected
  literal and `from_env` values, and that a Vault variable is present without
  printing its value;
* the IAM policy that lets the Hosted Application runtime read the Vault
  secret: document it, and record whether the deployment fails without it;
* record the results in Spec 006.

Known limit: variables belong to the Hosted Application and are set only when
it is created. Changing them on an existing application is not implemented;
the deploy stops when the manifest and the application differ. Decide whether
this needs an update workflow (a separate specification).

## 2. Live tests of JWT authentication

The `public-idcs` profile is implemented and tested offline
([Spec 010](specs/010-jwt-inbound-authentication.md)). Only the live
acceptance remains, and it needs the domain URL, audience, scope, client ID,
and client secret of a confidential application (new or reused).

Tests to do, in eu-frankfurt-1, with explicit authorization:

* release a new application (for example `text-stats-idcs`) with the
  `public-idcs` profile;
* run the verifier with `--functional`: token request, authenticated health
  and readiness, rejected unauthenticated `/health`, functional checks;
* call the endpoint with a token for another audience or scope, and record
  the status;
* confirm or correct the assumptions U1-U6 of Spec 010 (endpoint host,
  bearer header, protected probes, rejection status, token scope, HTTP Basic
  client authentication);
* check that no secret or token appears in any output, file, or command line;
* record the results in Spec 010, and delete the test application when no
  longer needed.

## 3. Scaling configuration in the manifest

Today the deploy skill does not set `scalingConfig`, so every application
gets the platform default. The live `text-stats` application reports
(2026-09-30): `minReplica` 1, `maxReplica` 3, `scalingType`
`REQUESTS_PER_SECOND`, `targetRpsThreshold` 50.

The OCI Python SDK 2.187.0 and OCI CLI 3.94.0 offer:

* `--scaling-config` on `hosted-application create` and on
  `hosted-application update`, with `minReplica`, `maxReplica`,
  `scalingType`, and one threshold per type;
* scaling types `CPU`, `MEMORY`, `CONCURRENCY`, and `REQUESTS_PER_SECOND`
  (`targetCpuThreshold`, `targetMemoryThreshold`,
  `targetConcurrencyThreshold`, `targetRpsThreshold`).

To do:

* an optional `deploy.scaling` section in `agent.yaml`, validated strictly:
  replica bounds, one scaling type, and only the matching threshold;
  without it, the platform default applies, as today;
* deploy: pass `--scaling-config` when creating the application; show the
  requested and the current scaling in the plan;
* verify against the documentation and live: the allowed ranges (for
  example whether `minReplica` 0 is accepted) and the threshold units;
* an existing application with different scaling: since `update` accepts
  `--scaling-config`, decide whether the deploy updates it after explicit
  authorization, or stops as it does for the runtime environment;
* tests with the fake `oci` for both script families, and documentation.

## Improvement roadmap

Proposed improvements from a project review (2026-10-01). The project is
dedicated to developers who work with Codex; every item keeps Codex skills as
the primary interface. Items overlapping the sections above reference them.

| # | Action | Limitation addressed | What to do and why | Effort | When |
| --- | --- | --- | --- | --- | --- |
| R1 | **Realistic demo: an agent that calls OCI Generative AI with resource principal** | The project helps ship an agent, not write one. | Add a demo (for example `demos/genai_chat/`): a LangGraph agent that calls an OCI Generative AI model from inside the container with resource principal, falling back to an API-key profile locally. This is the first thing an OCI developer needs, and it is missing today. Verify it remotely, not only locally. | Medium | Short term (after R2) |
| R2 | **Document IAM policies and add a pre-flight check** | IAM is out of scope and is the likely first cause of failure. | Write `docs/iam-policies.md` with the dynamic group and minimal policies for OCIR image pull, Vault secret read, and Generative AI calls. Add a read-only `scripts/check_iam_prereqs.sh` (and PowerShell twin) whose findings appear in the deploy plan. It never creates policies, so the current design holds, but it avoids discovering the failure after a long deployment. | Medium | Now |
| R3 | **New Codex skill `oci-agent-new` to scaffold an agent** | No support for developers starting from scratch. | A skill that, from a request such as "create a new OCI agent", prepares the repository: `agent.yaml` (schema 2), `Dockerfile`, `/health` and `/ready`, the Generative AI access code from R1, and functional checks. Today only a guide section exists. The Codex workflow then covers the whole path: create, build, push, deploy, verify. | Medium | Short term (after R1) |
| R4 | **Live acceptance of `public-idcs`** (section 2) | Authentication is tested only offline; assumptions U1–U6 are open. | Run the planned test in eu-frankfurt-1, confirm or correct U1–U6, and record the results in Spec 010. Until then, the only verified profile is `public-noauth`, which is not a production security posture. | Low | Now |
| R5 | **Multiple environments (dev / staging / prod)** | One `.env` per checkout; no notion of environment. | Introduce `--env <name>` reading `envs/<name>.env`, or an `environments:` section in the manifest. Skills ask for the target environment together with the manifest, and promoting the same tag from staging to production becomes an explicit request to Codex. | Medium | Medium term |
| R6 | **Update runtime environment and scaling on existing applications** (sections 1 and 3) | Applications are effectively immutable after creation. | Implement `deploy.scaling` and a "Configuration update" release case using `hosted-application update`, with the differences shown in the plan and explicit authorization. Today changing a variable requires recreating the application manually, which contradicts the "never delete" approach. | Medium-high | Medium term |
| R7 | **Private endpoint and custom networking** | Only public endpoints with Oracle-managed networking; a blocker for enterprise use. | Verify what the service supports (VCN, subnet, private endpoint), write a specification, and add a `private` manifest profile. At minimum, document clearly what is unsupported and the workaround. | High | Later (first confirm service capabilities) |
| R8 | **Artifact pruning and application teardown** | No cleanup; the 20-artifact limit is handled manually. | A skill or `prune` option (`--keep N`, inactive artifacts only, plan/apply) and a `teardown` with double confirmation for test environments. Today the lifecycle creates resources but never closes them. | Low-medium | Medium term |
| R9 | **Versioned tool release and compatibility check** | Maturity, single author, risk of service drift. | Publish a tagged release (`v0.1.0`) and declare the tested OCI CLI and SDK versions. Warn at startup when the CLI version differs, and run a periodic release-and-rollback test on `hello-world` to detect service regressions early. | Low | Now |
| R10 | **Fix inconsistencies and verify PowerShell parity** | Small inconsistencies; 49 tests skipped locally. | In the demo manifest, replace the compartment name in `GENAI_COMPARTMENT_ID` with an OCID placeholder and the personal name in the functional check with a generic one. Align `AGENTS.md`, which refers to a `src/` folder that does not exist. Run the PowerShell tests on a machine with `pwsh`: parity is declared but not verified on the primary workstation. | Low | Now |

Suggested order:

1. **Now:** R10, R9, R4, R2. Low cost, immediate credibility, and they remove
   the first real obstacle (IAM).
2. **Short term:** R1, then R3. The main value step: the Codex workflow covers
   the whole path, from an empty repository to an agent that uses Generative AI.
3. **Medium term:** R5, R6, R8. Needed for continuous use across environments.
4. **Later:** R7, which depends on service capabilities.
