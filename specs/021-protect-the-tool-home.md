# Spec 021: protect the tool home from operator sessions

Status: implemented; offline checks passed; real-session check pending.
Date: 2026-10-13.

## Problem

### Issue found (2026-10-13)

During the live test of Spec 019, Codex released `demos/hello_world` from a
session opened in the tool home. It changed three files of the tool:
`demos/hello_world/agent.yaml` (the application name),
`specs/hello_world.md` (a release record), and `CHANGELOG.md`. Earlier
releases had left similar uncommitted edits in `specs/hello_world.md`.

Two causes:

* The tool home's `AGENTS.md` is written for developers of the tool ("record
  verification results in the specification", "maintain `CHANGELOG.md`").
  Codex applied it to a session whose only purpose was a release.
* Step 9 of Getting started tells the user to open the tool home in Codex and,
  if the name `hello-world` is taken, to ask Codex for another application
  name, which can only be done by editing the tool's manifest.

A modified tool home confuses the user and can block `git pull`.

## Scope

1. Getting started (both guides), step 9: the example agent is released from
   a copy outside the tool home.
2. The tool home's `AGENTS.md`: a first section for sessions that use the
   skills, distinct from the development rules.
3. The four lifecycle skills (build, push, deploy, verify): never edit files
   of the tool home.

## Non-goals

* A technical block (file permissions, Git hooks) or a setup-check warning on
  local changes in the tool home.
* Restructuring `demos/hello_world` to build from its own folder.
* `oci-agent-new` and `oci-agent-ui`: they already never write to the tool
  home.

## Facts (verified 2026-10-13)

| # | Fact | Evidence |
| --- | --- | --- |
| F1 | `demos/hello_world/agent.yaml` builds with `context: ../..`, and its Dockerfile copies `demos/hello_world/requirements.txt` and `demos/`. A copy of the `hello_world` folder alone does not build: in the Spec 019 test Codex had to edit the copy's manifest and Dockerfile. | Manifest, Dockerfile, and the Codex session of 2026-10-13. |
| F2 | A copy that keeps the layout (`<copy>/demos/__init__.py`, `<copy>/demos/hello_world/`, and the tool's `.dockerignore` at `<copy>/`) in a new Git repository builds and passes the local verification unchanged. | `build_image.sh` and `verify_image.sh` on such a copy: `Functional check passed: POST /hello HTTP 200`, `result=PASS`. |

## Intended behavior

1. **Step 9.** The user creates the copy with the commands of the guide
   (macOS/Linux and PowerShell), opens the copy in a new Codex session, and
   asks for the release of `demos/hello_world/agent.yaml`. To use another
   application name, the user (or Codex) edits the copy's manifest. Cleanup
   also mentions deleting the copy.
2. **`AGENTS.md` of the tool home.** A first section, "Using the skills, not
   developing this tool": when the request is to build, push, deploy, verify,
   or test an agent, including `demos/hello_world`, do not edit any file of
   this repository and do not record results in specs, docs, or the
   CHANGELOG; to change a manifest value, copy the demo outside the repository
   first (step 9 of Getting started); change this repository only when the
   user explicitly asks to develop the tool.
3. **Lifecycle skills.** In "Tool home and working directory": "Never edit
   files in the tool home. If the manifest is inside it, for example
   `demos/hello_world`, copy it outside the tool home before changing any
   value (step 9 of Getting started)."

## Tests (offline)

* `tests/test_skills.py`: the four lifecycle skills contain the rule; the
  tool home's `AGENTS.md` starts its rules with the operator section.

## Acceptance criteria

1. The offline tests, Black, Pylint, and pytest pass; every relative link in
   the edited files resolves.
2. A real session: releasing the example from the copy leaves `git status` of
   the tool home unchanged.

## Verification record

### 2026-10-13, macOS, local

* F2 checked before writing the guide: a layout-preserving copy in a new Git
  repository passed `build_image.sh` and `verify_image.sh` (tag `0.0.1`,
  local Docker only; the test image was removed afterwards).
* Getting started step 9 (both guides), the tool home's `AGENTS.md`, and the
  four lifecycle skills updated; one new test in `tests/test_skills.py`.
* Offline: full suite 370 passed, 141 skipped (all `pwsh is unavailable`);
  Black and Pylint (10.00/10) passed; relative links resolve.
* Pending: acceptance criterion 2 in a real session.
