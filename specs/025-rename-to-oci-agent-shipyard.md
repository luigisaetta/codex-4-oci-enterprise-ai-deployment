# Spec 025: rename the project to OCI Agent Shipyard

Status: implemented; primary workstation migrated (2026-10-14); other workstations pending.
Date: 2026-10-14.

## Problem

The name `codex-4-oci-enterprise-ai-deployment` is long, hard to remember,
and describes the first purpose of the project (deployment) rather than what
it does now: create, build, ship, verify, and demo agents.

## Scope

* New name **OCI Agent Shipyard**; repository, tool home folder, and Conda
  environment `oci-agent-shipyard`.
* Every active reference: `AGENTS.md`, guides, notes, skills, scripts and
  their error messages, tests, the README title, and the overview image.
* Migration steps for workstations that already use the old name.

## Non-goals

* Historical records keep the old name: released notes (v0.5.0, v0.6.0,
  v0.7.0), `CHANGELOG.md` entries, and verification records of past runs in
  the specifications.
* Skill names (`oci-agent-*`), manifest fields, and environment variables do
  not change.

## Facts (verified 2026-10-14)

| # | Fact | Evidence |
| --- | --- | --- |
| F1 | GitHub redirects the web pages and Git operations (clone, fetch, push) of a renamed repository to its new name, except project site URLs, until a new repository takes the old name; it strongly recommends updating local clones with `git remote set-url`. | [Renaming a repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository). |
| F2 | `luigisaetta/oci-agent-shipyard` did not exist. | `GET https://api.github.com/repos/luigisaetta/oci-agent-shipyard` answered 404. |
| F3 | `install_skills.sh` reports a link to another checkout as a conflict and does not replace it; `--uninstall` removes only links to the current checkout. | `scripts/install_skills.sh`. So the skills must be uninstalled before the folder is renamed. |

## Migration of a workstation

In this order, from the old tool home:

1. `git pull`, so that the checkout has this change.
2. `scripts/install_skills.sh --uninstall` (PowerShell:
   `./scripts/install_skills.ps1 -Uninstall`): remove the links that point to
   the old folder.
3. Update the remote: `git remote set-url origin
   https://github.com/luigisaetta/oci-agent-shipyard.git`.
4. Rename the folder to `oci-agent-shipyard`.
5. Create the environment `oci-agent-shipyard` (Python 3.11) and install
   `requirements-dev.txt`, as in step 3 of Getting started.
6. From the new tool home, `scripts/install_skills.sh`, then a new Codex
   session.
7. `scripts/check_setup.sh`: every line must say `PASS`.
8. Optional: remove the old environment with
   `conda env remove -n codex-4-oci-enterprise-ai-deployment`.

The tool's `.env` moves with the folder. Agent folders need no change: their
`AGENTS.md` block finds the tool home through the installed skill link.
On Windows, `install_oci_powershell_hook.ps1` must be run again in the new
environment.

## Acceptance criteria

1. No active reference to the old name remains; the offline tests, Black,
   Pylint, and pytest pass; links resolve.
2. On the primary workstation, after the migration, `check_setup.sh` passes
   and a new Codex session lists the six skills.

## Verification record

### 2026-10-14, macOS, local

* 66 lines changed in 31 files; the remaining occurrences of the old name are
  the historical records listed in the non-goals.
* README title "OCI Agent Shipyard"; the overview image header and its JPG
  regenerated.

### 2026-10-14, primary workstation migration (macOS)

* Remote `https://github.com/luigisaetta/oci-agent-shipyard.git`, `main` in
  sync with `origin/main`, tag `v0.7.0` on the remote; the old folder no
  longer exists.
* The six skill links in `~/.agents/skills` point to the new tool home; the
  tool home's `.agents/skills` link is relative and unaffected.
* New environment `oci-agent-shipyard`: Python 3.11.17, OCI CLI 3.95.0, OCI
  Python SDK 2.188.0 (newer than the 3.94.0 and 2.187.0 used for the live
  tests so far); the old environment was removed.
* `scripts/check_setup.sh`: all 4 checks passed. Full suite in the new
  environment: 410 passed, 145 skipped; Black and Pylint (10.00/10) passed.
  The OCI CLI commands and `hosted-application create` options used by the
  scripts are present in 3.95.0.
* Pending: a new Codex session listing the six skills (criterion 2), and a
  first live release with OCI CLI 3.95.0.
