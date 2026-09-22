# Changelog

## Unreleased

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
