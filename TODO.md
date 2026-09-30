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

## 2. Authentication with JWT tokens

Implemented; live acceptance pending (needs confidential-application
credentials). See [Spec 010](specs/010-jwt-inbound-authentication.md).

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
