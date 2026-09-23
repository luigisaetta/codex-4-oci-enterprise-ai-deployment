# Changelog

## Unreleased

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
