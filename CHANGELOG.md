# Changelog

## Unreleased

## 0.6.0 - 2026-10-06

Spec-first agent creation and Resource Principal. See the
[release notes](docs/releases/v0.6.0.md).

* 2026-10-06: Support Resource Principal for agents that call OCI Generative
  AI (`GENAI_AUTH_MODE=resource_principal`, `GENAI_PROJECT_ID`, library
  `oci-genai-auth`), verified live; API-key mode stays the default. Update the
  `oci-agent-new` guidelines and template, and the runtime policies for
  Resource Principal and API keys in the IAM guide.

* 2026-10-06: Agent secrets such as `GENAI_API_KEY` can live in the tool's
  `.env`: `from_env` reads the operator environment first, then the tool's
  `.env`, without adding the secret to the tenancy settings exported by the
  scripts. Runtime reports now show `from_env` values as `value=<hidden>`
  with their origin.

* 2026-10-05: `oci-agent-new` now starts from a specification. Without a
  specification file, it drafts `agent-spec.md` from the request, beginning
  with a business context (customer persona, use case, expected outcomes, and
  optional concerns) and asking for the essential ones when missing; it applies
  the defaults of its agent guidelines, stops for the developer's review, and
  generates the code only from the approved specification.

* 2026-10-04: Add `scripts/check_setup.sh` and its PowerShell twin, a
  read-only setup check that runs the existing tenancy, Docker, OCI CLI,
  skill installation, and optional manifest and OCIR repository checks, and
  reports each one as `PASS` or `FAIL`.

## 0.5.0 - 2026-10-02

First tagged release. See the [release notes](docs/releases/v0.5.0.md).

* 2026-10-02: Rewrite the README around the five skills, with Mermaid
  diagrams of the workflow and the release lifecycle, example requests, and a
  documentation map; title it "Codex Skills for OCI Enterprise AI Deployment"
  and update the overview image accordingly.

* 2026-10-02: Give Hosted Application health, readiness, and optional functional
  HTTP requests an independent 60-second default timeout; keep polling at five
  seconds by default in Bash and PowerShell.

* 2026-10-02: Add bounded, resumable Hosted Application and deployment waits,
  with progress, OCI error reporting, and exit 26 while OCI remains in progress.

* 2026-10-02: Allow an explicitly requested, plan-approved replacement of a
  `FAILED` Hosted Deployment; keep its deletion and new creation ordered, and
  document the recovery path in the deploy skill and guides.

* 2026-10-01: Add the `oci-agent-new` skill and its offline helper
  `scripts/new_agent.py`: from a prompt and an optional specification file,
  create the files the lifecycle skills need (`agent.yaml`, `Dockerfile`,
  `.dockerignore`, `.gitignore`, `requirements.txt`, and a FastAPI agent
  package), check the tenancy file without printing values, and never
  overwrite existing files.

* 2026-10-01: Remove the binary-only `pip` constraint from the Dockerfile
  template and the `hello_world` image: `pip install --prefer-binary` still
  prefers wheels but also installs pure-Python source distributions.

* 2026-10-01: Add an IAM policies guide listing the operator and runtime
  (dynamic-group) permissions for the skills, with the verification status of
  each statement, and link it from the Quickstart.

* 2026-09-30: Add an agent manifest reference describing every `agent.yaml`
  field, with complete examples for the `public-noauth` and `public-idcs`
  access modes.

* 2026-09-30: Add Spec 010 `public-idcs` inbound-authentication documentation
  for deployment, verification, and protected-agent calls.

* 2026-09-30: Add a plain-language Quickstart for publishing an agent, releasing
  new versions, and rolling back, and document new versions and rollback in
  the README.

* 2026-09-30: Fix non-interactive Hosted Deployment artifact activation by
  passing `--force` only to the OCI update command.

* 2026-09-30: Add Spec 009 support for new versions and rollback in the same
  Hosted Application, remove the derived deployment name, and wait during
  `UPDATING` when verifying a deployment.

* 2026-09-29: Allow all OCI Hosted Applications lifecycle skills to be selected
  from natural requests, add a target-platform check that distinguishes AI DP
  code-first agents, and retain explicit authorization before every push or
  deployment mutation.

* 2026-09-29: Fix `verify_image.sh` on Bash 3.2 so an empty manifest runtime
  environment cannot turn a failed container start into a false PASS; earlier
  local verifications of manifests without `runtime.env` may have reported a
  false PASS.

* 2026-09-29: **Breaking:** agent manifests must use `schema_version: 2`, whose
  build paths are relative to the manifest's folder; version 1 manifests are
  rejected. To migrate, set `schema_version: 2` and rewrite `build.context` and
  `build.dockerfile` relative to the manifest (the `hello_world` manifest is
  already migrated).

* 2026-09-29: Add user-scope skill installation and support for skills used
  from any agent repository; introduce manifest schema version 2, tenancy-file
  and interpreter selection, split tool and demo dependencies, and return exit
  code 64 for manifest errors during functional checks.

* 2026-09-24: Add an SVG overview and JPEG rendition of the four-skill OCI
  Enterprise AI agent release workflow to the project README.

* 2026-09-23: Add PowerShell 7.4+ twins of every lifecycle script with the same
  options, report lines, and exit codes, plus Docker/Podman engine selection, a
  parity test, and Windows guidance for the native PowerShell and WSL2 paths;
  the skills select the script family from the shell in use.

* 2026-09-23: Add a step-by-step guide for using the four OCI agent skills and
  link it from a simplified project README.

* 2026-09-23: Add an outline for an SSH-accessed Linux build-machine workflow.

* 2026-09-23: Add Windows workstation guidance for Rancher Desktop using the
  Moby engine and WSL2.

* 2026-09-23: Add manifest-defined Hosted Application runtime environment
  variables with literal, operator-environment, and OCI Vault sources.

* 2026-09-23: Require the caller to identify an agent manifest before any of
  the build, push, deploy, or verification skills select an agent.

* 2026-09-23: Add versioned per-agent manifests for build, publish, deployment,
  and functional verification configuration; keep tenancy settings in `.env` and
  release tags on the command line.

* 2026-09-23: Add a read-only Hosted Application deployment verification skill
  with release-tag checks and public health/readiness probes.

* 2026-09-23: Allow the Hosted Application deployer to proceed past a
  same-named OCI Hosted Application in lifecycle state `DELETED`, while safely
  stopping for non-deleted matches.

* 2026-09-23: Derive OCIR region-key endpoints dynamically from `oci iam region
  list`, removing the maintained Frankfurt/Chicago resolver map for OC1.

* 2026-09-22: Verify the OCI Hosted Application deployment workflow remotely in
  Frankfurt: the application and its single-artifact deployment reached
  `ACTIVE` using the published `hello-world:0.1.0` OCIR image.

* 2026-09-22: Add OCI Generative AI Hosted Application deployment
  workflow with `NO_AUTH_CONFIG`, public Oracle-managed networking, no container
  environment variables, and explicit creation authorization.

* 2026-09-22: Resolve OCIR login and push endpoints from `OCI_REGION` using
  supported region-key mappings for Frankfurt (`fra`) and Chicago (`ord`).

* 2026-09-22: Add OCI CLI as a development dependency and a guarded script that
  resolves a compartment and creates an absent OCIR repository only with
  `--create`.

* 2026-09-22: Extend the OCIR push workflow to resolve a configured compartment
  name and explicitly create a missing private repository before an authorized push.

* 2026-09-22: Add OCIR push preparation configuration and the `oci-agent-push`
  skill with interactive auth-token guidance and explicit-push authorization.

* 2026-09-22: Stream OCI agent image build logs to the terminal while retaining a
  temporary log for failure analysis.

* 2026-09-22: Make image verification report a Docker daemon outage with exit code 1
  before inspecting the requested image.

* 2026-09-22: Document how to discover and use repository skills, beginning with
  `oci-agent-build`, in the project README.

* 2026-09-22: Add the oci-agent-build skill, Bash 3.2 build/verification scripts,
  and container templates for hello_world, with local amd64 acceptance evidence.

* 2026-09-22: Add the hello_world LangGraph demo with a FastAPI greeting endpoint,
  health and readiness probes, local setup instructions, and API tests.
