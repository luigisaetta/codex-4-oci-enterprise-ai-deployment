# Changelog

## Unreleased

## 0.7.0 - 2026-10-13

Asynchronous agents, protected agents end to end, and safer operation. See
the [release notes](docs/releases/v0.7.0.md).

* 2026-10-13: Guideline B8 of `oci-agent-new` now asks for the asynchronous
  behavior in plain words in the specification; the implementation details
  moved to the new code rule Q7.

* 2026-10-13: Asynchronous agents (Spec 024). `oci-agent-new` supports agents
  that start a job with a POST (202, `job_id`) and report its steps and
  result with a GET (guideline B8, one replica). Functional checks can follow
  a job (`poll`) and be limited to the remote verification (`local: false`).
  The demo UI template polls the job, shows each step with its business
  label, and then the result. New guideline Q6 on conversation history with
  the OCI Responses API.

* 2026-10-13: Number of replicas at creation (Spec 023). An optional
  `deploy.scaling` section (`min_replicas`, `max_replicas`, 1 to 30) sets
  the replicas when the Hosted Application is created; the plan shows them,
  and the deploy stops if an existing application has other replicas. Use
  one replica for agents that keep state in memory.

* 2026-10-13: `public-idcs` verified live end to end (Specs 010 and 022):
  release, verification with functional checks, and the demo UI of a
  protected agent. TODO item 6 completed.

* 2026-10-13: First live `public-idcs` release (Spec 010). The service
  rejects a request without a token with 404: the verifier now accepts 401,
  403, or 404 as rejection, and the demo UI bridge refreshes its token after
  any of them. The `AGENTS.md` block states that the skills' compartment and
  region lookups are normal operation.

* 2026-10-13: Identity-domain credentials for the demo UI and the verifier
  (Spec 022). The demo UI of `oci-agent-ui` now supports agents with the
  `public-idcs` profile: its local server requests a client-credentials token
  (values in `ui/.env.local`, never sent to the browser), caches it, and adds
  it to every call. The verifier reads `OCI_AGENT_IDCS_CLIENT_ID` and
  `OCI_AGENT_IDCS_CLIENT_SECRET` from the tool's `.env` when they are not
  exported. New `tool_config.py has` command.

* 2026-10-13: New guide [Protecting an agent with JWT tokens](docs/idcs-confidential-application.md):
  create and activate the identity-domain confidential application
  (resource server with audience and scope, client credentials), test a
  token without showing it, fill in `deploy.auth`, and troubleshoot.

* 2026-10-13: Protect the tool home (Spec 021). Getting started step 9 now
  releases the example agent from a copy outside the tool home; the tool's
  `AGENTS.md` starts with rules for sessions that use the skills (no edits to
  the tool's files); the build, push, deploy, and verify skills never edit
  the tool home.

* 2026-10-13: Stop on missing runtime permissions (Spec 019). When a
  deployment ends `FAILED` or `NEEDS_ATTENTION` because its runtime cannot
  read the image from OCIR, the deploy script shows the OCI error, checks
  that the image exists, and stops with exit 27 and a message for the tenancy
  administrator; a missing image asks for the push instead. The deploy skill
  and the agent repository's `AGENTS.md` forbid IAM changes by Codex.

* 2026-10-12: New guide [Logging in to OCIR](docs/ocir-login.md): registry
  address, username built from the Console's Profile menu (with the identity
  domain when shown), auth token generation, login with Docker or Podman, and
  common errors. Linked from Getting started steps 5 and 9 and the README.

* 2026-10-12: The customer-name rule of Spec 020 now also lives in each agent
  repository's `AGENTS.md`, which Codex reads in every session, with or
  without a skill. `oci-agent-new` and `oci-agent-ui` add it; for existing
  agent folders run `scripts/agent_instructions.py ensure --target <folder>`.

* 2026-10-12: Approved demo customer name (Spec 020). `oci-agent-new` and
  `oci-agent-ui` name the customer only with the demo name, `Supremo` unless
  `DEMO_CUSTOMER_NAME` is set in the tool's `.env`; the real customer's name
  stays in the conversation, never reaches a file, and a final check looks for
  it in the generated files. New `tool_config.py demo-customer` helper.

* 2026-10-09: IAM policies: verified live that the runtime needs only
  `read repos` to pull its image; vulnerability-scanning statements are not
  needed.

* 2026-10-09: Release the existing `hello_world` image version `0.1.0` on OCI
  Hosted Applications in Frankfurt; record active resource state, successful
  creation work request, and public health/readiness verification in
  [the demo specification](specs/hello_world.md).

* 2026-10-09: Split Getting started into two complete guides,
  [macOS and Linux](docs/getting-started-macos-linux.md) and
  [Windows](docs/getting-started-windows.md); `docs/getting-started.md` now
  only links to them. The tenancy administrator's steps moved to
  [Setup for the administrator](docs/iam-policies.md#setup-for-the-administrator),
  with what a new compartment needs.

* 2026-10-08: Native Windows (PowerShell 7) pilot. The PowerShell deploy now
  passes the networking JSON as one argument (split in two, it broke every
  first Hosted Application creation) and reports a bounded, redacted OCI CLI error
  when a mutation fails without a `ServiceError`. New
  `scripts/install_oci_powershell_hook.ps1` installs reversible Conda hooks
  so that the OCI CLI's key-file check works under PowerShell 7.

* 2026-10-08: Windows guidance for Podman, PowerShell 7.4+, Conda
  initialization for PowerShell, and the first agent's folder; test fixtures
  that run on native Windows.

* 2026-10-07: Add the `oci-agent-ui` skill (Spec 018): from the agent's
  specification it drafts `ui/ui-spec.md`, then, after approval, creates a
  local Next.js demo page for the agent's users, in business language, with
  example requests and no technical data; the browser calls the agent only
  through a local server route. Agent images now exclude `ui` and
  `node_modules`, and the agent specification template has an optional
  "Demo" section.

* 2026-10-06: `oci-agent-new` treats agents that call OCI Generative AI as
  supported: it follows its guidelines without asking whether to proceed, and
  its closing message reminds the API-key or Resource Principal prerequisites
  (Spec 017).

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
