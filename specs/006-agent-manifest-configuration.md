# Spec 006: Agent manifest configuration

Status: implemented; local validation passed; live OCI workflow observed for
`hello_world:0.2.2`.
Date: 2026-09-23.

## Problem

The previous workflow mixed tenancy-wide values, agent identity, and release
version in `.env`. Maintaining more than one agent required editing shared
configuration for every operation, and a release could accidentally use stale
application, repository, or deployment names.

## Scope

Introduce a versioned `agent.yaml` beside each agent and make the build, OCIR
push, Hosted Application deployment, local verification, and optional remote
functional verification consume it. Add a guarded push helper. Update the
reference `hello_world` agent and all four skill instructions.

## Non-goals

* Put release tags, credentials, OCIDs, or endpoint URLs in a manifest.
* Change OCI IAM, networking, artifact permissions, or application profiles.
* Automatically invoke an agent business endpoint during normal remote
  health/readiness verification.
* Support arbitrary YAML features, multiple deployment profiles, CI secrets, or
  deployment rollback.

## Configuration contract

There are three configuration lifecycles:

| Level | Location | Changes when |
| --- | --- | --- |
| Tenancy | ignored root `.env` | tenancy, region, or compartment changes |
| Agent | versioned `agent.yaml` next to the agent | agent code or its deployment contract changes |
| Release | required `--tag` option | every release |

`.env` contains only `OCI_REGION`, `OCI_COMPARTMENT_NAME`,
`OCIR_TENANCY_NAMESPACE`, and `OCIR_USERNAME`. It contains no agent-specific
names, repository, OCID, URL, version, token, or password.

Manifest paths are relative to the repository checkout root, not to the
manifest directory. This allows `build.context: .` to include root
`requirements.txt` while selecting an agent Dockerfile below `demos/`.

The supported schema is strict and versioned:

```yaml
schema_version: 1
name: hello-world
build:
  context: .
  dockerfile: demos/hello_world/Dockerfile
publish:
  repository: agents/hello-world
deploy:
  application_name: hello-world
  profile: public-noauth
verify:
  - method: POST
    path: /hello
    body: {name: Luigi}
    expect_status: 200
    expect_json:
      message: Hello Luigi
```

`name` is the local image name. `publish.repository` combines with the tenancy
namespace and dynamically resolved OCIR hostname. `deploy.profile` is presently
only `public-noauth`, meaning `NO_AUTH_CONFIG`, public inbound endpoint, and
Oracle-managed outbound networking. `verify` holds only agent-specific
functional checks; `/health` and `/ready` are mandatory platform probes and are
not represented there. Each check permits `GET` or `POST`, requires an absolute
path and an expected HTTP status, and can use a JSON request body and a JSON
object subset assertion. Unknown fields and unsafe or checkout-escaping paths
are rejected. A release tag field is therefore rejected by schema validation.

The tag must be semantic (`MAJOR.MINOR.PATCH` with an optional prerelease) and
is passed to every lifecycle command. The deployment display name is derived as
`<application_name>-<tag-with-dots-replaced-by-hyphens>`; for example,
`hello-world` and `0.2.0` become `hello-world-0-2-0`.

### Agent selection rule

The invoking user must name a manifest path in the current request. A skill
must ask which manifest to use before performing Docker, OCI CLI, or HTTP work
when that path is absent. It must not select `hello_world`, scan for a manifest,
or infer a manifest from prior conversation. The user may explicitly say to use
the same agent or manifest as an immediately identified earlier step; that is a
valid selection. The release tag remains a separate required input.

## Intended behavior

`scripts/agent_manifest.py` validates the schema and exposes only validated
values to the Bash wrappers. It relies on `PyYAML`, declared explicitly in
`requirements-dev.txt`; it never evaluates YAML tags or shell code.

The standard commands are:

```bash
scripts/build_image.sh --manifest demos/hello_world/agent.yaml --tag 0.2.0
scripts/verify_image.sh --manifest demos/hello_world/agent.yaml --tag 0.2.0
scripts/push_ocir_image.sh --manifest demos/hello_world/agent.yaml --tag 0.2.0
scripts/deploy_hosted_application.sh --manifest demos/hello_world/agent.yaml --tag 0.2.0
```

The first two use local Docker only. Push plans the exact source and OCIR target
and requires `--push`; repository creation remains separately guarded by
`ensure_ocir_repository.sh --repository <manifest repository> --create`.
Deployment plans OCI reads only and does not require the local Docker image. It creates a missing application, or reuses
one exact-name ACTIVE application having the `public-noauth` contract; it never
alters an existing application. It creates at most one exact derived deployment
name and stops safely for an existing non-deleted deployment. Creation remains
behind `--apply`.

`verify_deployment.sh` accepts `--manifest` and `--tag` in place of the expected
tag. It continues to perform only `/health` and `/ready` by default. Its optional
`--functional` switch runs manifest checks only after separate explicit user
authorization, because those requests invoke application business paths.

## Assumptions and prerequisites

The project Conda environment has `PyYAML`, OCI CLI, Docker, and curl as needed.
OCI CLI authentication and current OC1 region discovery remain prerequisites.
The operator exports non-secret tenancy values from `.env` before OCI scripts.
The Hosted Deployment runtime's pull IAM access is still externally managed.

## Acceptance criteria and verification

1. `agent_manifest.py validate` accepts the `hello_world` manifest and rejects
   unknown fields, a manifest tag, unsafe paths, and invalid functional checks.
2. Build and local verification derive context, Dockerfile, name, and functional
   checks solely from the manifest plus `--tag`.
3. Push and repository inspection derive the repository from the manifest;
   `.env.example` has no agent-specific keys.
4. Deployment derives the artifact URI, application name, and deployment name
   from the manifest plus `--tag`, and remains plan-first and idempotent for an
   existing deployment name.
5. Default remote verification keeps its read-only OCI calls and GET-only
   platform probes; functional invocation is opt-in.
6. Shell syntax checks and Python unit tests run without OCI credentials or
   remote mutations. Docker and OCI live acceptance remain explicit and pending.

## Recovery

If deployment creates an application but deployment creation fails, it prints
the application OCID and does not delete it. A later run may reuse only that
ACTIVE application after validating its profile; otherwise it stops for human
review. A failed or creating deployment with the derived name is never replaced
automatically. Cleanup is a separate, explicitly authorized OCI operation.

## Authoritative interfaces

The OCI CLI command names and Hosted Application lifecycle behavior continue to
use the official CLI and Generative AI documentation referenced by Specs 002,
003, and 005. Their verification date is 2026-09-23. The endpoint base used by
Spec 005 remains observed live evidence; the manifest does not introduce a new
endpoint format.
