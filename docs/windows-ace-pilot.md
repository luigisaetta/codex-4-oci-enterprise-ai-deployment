# Windows ACE pilot findings

## Scope

A participant followed Getting Started on native Windows with PowerShell 7 and
Podman, reusing an existing workstation and OCI tenancy. The goal was to find
Windows documentation and script gaps, not to prove a fresh-install path or to
release a second agent. No private configuration, OCIDs, or auth tokens are
included here.

Observed versions: PowerShell 7.6.5, Git 2.52.0.windows.1, Conda 25.11.1,
Python 3.11.16 in the project environment, OCI CLI 3.94.0, and Podman 5.8.2.
Docker Desktop, WSL2, and a clean Windows workstation were not tested.

## Setup and skill discovery

- The existing Podman client initially could not connect to its machine.
  Starting the existing machine restored `podman info`. Getting Started now
  distinguishes a client installation from a running engine and includes this
  recovery step.
- PowerShell 7 is required by the repository's native Windows scripts.
  `conda activate` initially left the global Python selected because Conda's
  PowerShell integration was absent in that session. The documented
  `conda init powershell` route followed by a new shell restored Python 3.11.16.
- The OCI CLI namespace request succeeded but printed `Get-Acl` module-load
  warnings in PowerShell 7. The CLI launches Windows PowerShell for its file
  permission check; incompatible inherited `PSModulePath` caused that check
  to fail. Project-scoped Conda activation/deactivation hooks now select a
  Windows PowerShell-compatible module path and restore the previous value.
  The participant confirmed a direct `oci os ns get` without warnings after
  activating the environment in a new PowerShell 7 session.
- `scripts/check_setup.ps1` passed all four checks. The participant opened
  a separate agent folder in a new Codex session and confirmed that all six
  installed OCI skills appeared in the skill picker.

## Example release with native PowerShell

The supplied `hello_world` manifest was built and verified locally as a
`linux/amd64` image using Podman. The Windows push to OCIR succeeded. A
first Hosted Application creation was blocked by the tenancy's
`hosted-application-count` limit (25 of 25), not by IAM. An earlier create
attempt had also exposed a PowerShell argument bug: the networking JSON was
split into two OCI CLI arguments. The Windows script now passes one JSON
argument and reports a bounded, redacted CLI error when no structured
ServiceError is available.

With operator authorization, the same image was released as a new version of
an existing public, unauthenticated Hosted Application. Read-only OCI checks
confirmed the active tag. The PowerShell verifier observed `/health` and
`/ready` as HTTP 200, and the manifest's POST `/hello` functional check
passed. This verifies the update and verification path; it does not verify
first-application creation with the corrected argument.

## First agent authoring

A separate local Git folder beside the tool checkout was used because
`oci-agent-new` rejects targets inside the tool home. The participant
approved a specification for a deterministic webshop email classifier.
`new_agent.py plan` and `render` succeeded from that folder on Windows.
Python syntax, manifest validation, the read-only tenancy check, and local
HTTP checks for success and invalid input passed. The generated agent was not
built or deployed; that was outside this Windows-focused pilot.

The Windows run of `tests/test_new_agent.py` exposed three false failures:
Git had checked out the template with CRLF while the helper generated LF
content. The assertion now compares decoded text. Test fixtures for the
PowerShell deployment flow also needed a Windows-executable fake OCI command
that preserves JSON arguments; POSIX Bash scenarios are skipped on native
Windows.

## Verification and remaining limits

After fixture corrections, 110 agent and PowerShell baseline tests, 37
PowerShell deploy scenarios, and 82 PowerShell wait/recovery scenarios passed.
Black left the four edited Python test files unchanged; Pylint rated them
10.00/10. Pytest initially could not create temporary fixtures inside Codex's
sandbox, so these offline tests were rerun with access to the temporary folder.

The first Hosted Application create path, Docker Desktop, WSL2, and clean
workstation setup remain unverified. A tenancy-level application-count
preflight would make the quota failure clearer before an ACE attempts a first
release. The new-agent workflow could also explain earlier that the agent
folder must be outside the tool checkout.