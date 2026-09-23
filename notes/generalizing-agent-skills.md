# Generalizing the OCI agent skills

Date: 2026-09-23

> Implemented configuration decision: this exploratory note is superseded by
> [Spec 006](../specs/006-agent-manifest-configuration.md). The implemented
> contract uses an agent-local manifest for stable agent configuration and an
> explicit `--tag` for every release.

## Changes to make the skills reusable

The build, push, and deploy skills should operate on an explicitly supplied
artifact, rather than on the `hello_world` demo. `hello_world` should remain a
documented example and a regression fixture, not a default workload or an
implicit input.

### Establish a common artifact contract

Use explicit inputs and outputs at each step:

```text
build:   context + Dockerfile + local image name + semantic tag
push:    local image NAME:TAG -> fully qualified OCIR image reference
deploy:  fully qualified OCIR image reference -> Hosted Deployment
```

The recommended commands should consequently look like this:

```bash
scripts/build_image.sh \
  --context demos/customer_support \
  --dockerfile demos/customer_support/Dockerfile \
  --name customer-support \
  --tag 1.2.0

scripts/push_ocir_image.sh --image customer-support:1.2.0

scripts/deploy_hosted_application.sh \
  --image fra.ocir.io/<namespace>/<repository>:1.2.0
```

All tags must be explicit semantic versions. No skill may infer an image name,
select the most recent local image, or accept `latest`.

### Generalize the build skill

1. Remove wording that makes `demos/hello_world` the reference workload or
   requires it as the build target.
2. Keep `--context`, `--dockerfile`, `--name`, and `--tag` as required build
   inputs. Resolve and validate them relative to the repository checkout.
3. Treat the example POST path, request body, and expected response as optional
   verification inputs supplied by the agent developer. The universal checks
   are image architecture, container start, readiness, and health.
4. Keep `hello_world` as a complete command example and a test fixture. Label
   it clearly as an example.
5. Report a stable local image reference and immutable image ID/digest after a
   successful build so that the push step can consume it without guesswork.

### Generalize the push skill

1. Add a guarded `scripts/push_ocir_image.sh` command with required
   `--image NAME:TAG`. The script must reject absent local images, non-semantic
   tags, and images whose inspected platform is not exactly `linux/amd64`.
2. Preserve the current OCIR configuration contract: region, compartment,
   tenancy namespace, repository, and login username belong in `.env`; secrets
   and Docker credentials do not.
3. Continue resolving the registry endpoint from `OCI_REGION`, rather than
   asking users to configure a registry hostname.
4. Make the destination repository independent of the local image name. For
   example, local `customer-support:1.2.0` may be pushed to the configured
   `agents/customer-support:1.2.0` repository.
5. Keep repository creation and image push as separate, explicitly authorized
   remote mutations. A preflight must show source and destination references.
6. After a successful push, print the fully qualified OCIR reference and the
   registry digest in a machine-readable, secret-free form. This is the handoff
   artifact for deployment.

### Generalize the deploy skill

1. Change the deployment input from a local image name to a fully qualified
   OCIR image reference. Deployment must not depend on the local Docker cache
   or on being run from the machine that built the image.
2. Parse and validate the OCI registry, tenancy namespace, repository, and
   semantic tag. By default, require them to match the configured OCIR target;
   supporting a different target must be an explicit future feature.
3. Retain the read-only plan as the default and require `--apply` immediately
   before creating resources.
4. Keep the present deployment posture as an explicit profile: public endpoint,
   `NO_AUTH_CONFIG`, Oracle-managed networking, no container environment
   variables, and no managed storage. Do not silently broaden this profile.
5. Record the created application OCID, deployment OCID, active artifact
   reference, lifecycle states, and endpoint availability. Endpoint invocation
   remains a separate authorization because the endpoint is public and has no
   inbound authentication.
6. Define partial-failure recovery: if an application is created but its
   deployment fails, report its OCID and stop. Never reuse, replace, or delete
   it automatically.

### Align repository documentation and verification

1. Update Specs 001, 002, and 003 before implementation so their input/output
   contracts agree.
2. Update the root README, skill catalog, `.env.example`, and each `SKILL.md`
   with generic examples and clear distinctions between local image references
   and remote OCIR references.
3. Add reusable fixture agents under `demos/` only when they exercise a distinct
   runtime behavior; do not encode their names in shared scripts.
4. Add automated shell tests for argument validation, platform validation,
   reference parsing, and safe rerun/partial-failure behavior. Keep live OCI
   tests opt-in and record their sanitized results in the relevant spec.
5. Preserve the authorization boundary: planning and inspection are read-only;
   repository creation, push, and deployment creation each need the operator's
   explicit approval.

## Constraints for agent developers

An agent submitted to this workflow must satisfy the following contract.

### Container and runtime requirements

1. Provide a Docker build context and Dockerfile that can be built from the
   repository checkout. The Dockerfile may copy only files available in its
   declared context and not excluded by `.dockerignore`.
2. Produce a `linux/amd64` image. Apple Silicon local development is supported
   through emulation, but an ARM-only image is not accepted.
3. Start the service through `CMD` or `ENTRYPOINT` in the Dockerfile. Do not
   depend on a platform-supplied custom entry command.
4. Listen on `0.0.0.0:8080` and implement `GET /ready` and `GET /health`.
   Each endpoint must return HTTP 200 when the service is ready or healthy and
   a non-200 result otherwise; probe responses must use `application/json`.
5. Treat the root filesystem as read-only. Write temporary files only under
   `/tmp`, do not require mounted volumes, and keep the application stateless.
6. Do not require container environment variables in the current deployment
   profile. Configuration needed for a demonstration must be packaged safely or
   have documented non-secret defaults. Never package credentials, private
   keys, auth tokens, or private data in an image.
7. Install Python dependencies as binary wheels under the repository policy
   (`--only-binary=:all:`). Pin or constrain dependencies sufficiently for a
   reproducible build, and document unavailable wheels as a build blocker.

### Interface, security, and operational requirements

1. Declare the agent's functional verification request explicitly: method,
   path, optional request body, expected status, and any response assertion.
   The generic verifier must not assume an agent-specific API such as `/hello`.
2. Emit useful, sanitized logs to standard output or standard error. Never log
   credentials, authorization headers, private prompts, or private payloads.
3. Document external service dependencies, outbound network requirements,
   required IAM permissions, expected costs, and recovery or cleanup steps.
   The current managed-network deployment skill does not create those IAM
   permissions or external resources.
4. Assume the current hosted endpoint is public and unauthenticated. An agent
   in this profile must not expose sensitive data or privileged operations.
   Production authentication and authorization are a separate, explicitly
   specified deployment profile.
5. Supply a semantic image tag and retain the produced OCIR reference and
   digest as deployment evidence. Do not rely on mutable tags as the only
   release identifier.
6. Provide a short agent README describing its purpose, build command,
   verification command, configuration assumptions, expected result, and known
   limitations. Document remote compatibility only after an OCI verification.
