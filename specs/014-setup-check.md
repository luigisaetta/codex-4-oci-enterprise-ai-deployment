# Spec 014: setup check

Status: implemented (Bash executed; PowerShell twin unexecuted).
Date: 2026-10-04.

## Problem

A developer's first problems are rarely in the agent: an incomplete `.env`,
the wrong Python interpreter, Docker without Buildx, an OCI CLI that is not
authenticated, an ambiguous compartment, or skills that are not installed.
Today they surface one at a time, in the middle of a build, a push, or a
deploy. The checks already exist, but in separate scripts.

## Scope

A minimal, read-only command that runs the existing checks in sequence and
summarizes them, so a developer can confirm the setup before the first
release.

* `scripts/check_setup.sh` and its PowerShell twin `scripts/check_setup.ps1`,
  with the same options, report lines, and exit codes.
* No new check logic: the command only runs existing scripts and reads their
  exit codes.

## Non-goals

* OCI CLI version warning, IAM permission checks beyond what the existing
  scripts read, Docker registry login, and `from_env` variables. They can be
  added later.
* Running the deploy plan: it still prints `from_env` values.
* Fixing anything: the command only reports.

## Checks

| # | Report label | Runs | Pass when |
| --- | --- | --- | --- |
| 1 | Tenancy file (.env) | `new_agent.py check-env` | exit 0 |
| 2 | Docker build environment | `check_build_env.sh` (`.ps1`) | exit 0 |
| 3 | OCI CLI and region | `resolve_ocir_registry.sh` (`.ps1`) | exit 0 |
| 4 | Skills installed | `install_skills.sh --dry-run --target DIR` (`.ps1`), only when `DIR` exists | exit 0 and no `would create` line |
| 5 | Agent manifest (with `--manifest`) | `new_agent.py check-manifest --manifest PATH` | exit 0 |
| 6 | Compartment and OCIR repository (with `--manifest`) | `ensure_ocir_repository.sh --repository REPO` (`.ps1`), without `--create`; `REPO` is `publish.repository` read with `agent_manifest.py get` | exit 0 (repository exists) or 20 (absent: reported as "not created yet; the push creates it") |

Check 4 does not run the installer when the target directory is missing,
because the installer would create it; it fails with "not installed". The
default target is `~/.agents/skills`; `--skills-target DIR` selects another
one, for example `~/.claude/skills`.

## Behavior

* Usage: `check_setup.sh [--manifest PATH] [--skills-target DIR]`
  (PowerShell: `-Manifest PATH -SkillsTarget DIR`).
* Every check runs, even after a failure.
* One line per check: `[PASS] <label>` or `[FAIL] <label>`. A failed check
  is followed by the last non-empty output line of the script it ran,
  indented. The command never prints `.env` values.
* A final line: `Result: all N checks passed.` or
  `Result: K of N checks failed.`
* Exit codes: 0 when every check passes, 1 when at least one fails, 64 for
  invalid arguments.
* The command is read-only: it creates, changes, and deletes nothing, locally
  or in OCI.

## Documentation

* README, Setup: a step that runs the check.
* Quickstart, "Before you start": the same command.
* `skills/README.md`: the option mapping for `--manifest` and
  `--skills-target`.
* `CHANGELOG.md`.

## Tests (offline)

`tests/test_check_setup.py`, with fake `oci` and `docker` executables first on
`PATH`, a temporary tenancy file, and a temporary skills target:

* every check passes: exit 0, one `[PASS]` line per check;
* a failing check does not stop the others: exit 1, the failing check and the
  following checks are reported;
* a missing skills target fails check 4 and is not created;
* with `--manifest`, an absent repository passes check 6 with "not created
  yet";
* an invalid argument exits 64;
* the output contains no value from the tenancy file.

Bash only; the PowerShell twin is checked by the parity test.

## Acceptance criteria

1. The offline tests pass, and the parity test accepts the new twins.
2. On the primary workstation, `check_setup.sh` reports every check with the
   real tools, and its result matches the individual scripts.

## Verification record

### 2026-10-04, macOS, local

* Offline: `tests/test_check_setup.py` passed (7 tests); the parity test
  accepts `check_setup.sh` and `check_setup.ps1`. Full suite: 340 passed,
  132 skipped, all skips with the reason `pwsh is unavailable`. Black and
  Pylint (10.00/10) passed.
* Real workstation, Bash, project Conda environment: without options, the
  four base checks passed. With `--manifest` (an existing agent) and
  `--skills-target ~/.claude/skills` (absent), the skills check failed with
  "Not installed", the directory was not created, and the manifest and OCIR
  repository checks passed. Only read-only OCI calls were made.
* The PowerShell twin is implemented and statically checked, not executed.
