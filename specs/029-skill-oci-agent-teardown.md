# Spec 029: skill `oci-agent-teardown`, remove an agent completely

Status: implemented; offline checks passed and live acceptance reported passed (2026-10-16).
Date: 2026-10-16.
Implements the teardown part of TODO item 13. Revises the rule of
[Spec 009](009-release-new-version.md) "No command of the skills deletes a
resource" (acceptance criterion 5 and non-goals), which stays true for every
other skill. Platform facts come from the
[managed ADB storage spike](../docs/managed-storage-adb-spike.md) and
[Spec 026](026-managed-adb-storage-at-creation.md).

## Problem

The skills create a Hosted Application, its deployment, an OCIR repository
with its images, optionally a managed storage, and local container images,
but they never remove them. Removing an agent today is a sequence of manual
steps in the right order: the active deployment cannot be deleted alone, the
storage survives the application, and forgotten resources keep costing.

## Scope

1. A new skill `oci-agent-teardown`, with Bash and PowerShell scripts
   (`scripts/teardown_agent.sh`, `scripts/teardown_agent.ps1`), that removes
   everything one agent manifest created:
   * the Hosted Application and its deployment;
   * the managed storage of `deploy.storage`, when present;
   * the OCIR repository `publish.repository` and all its images;
   * the local container images of the agent.
2. Plan first, apply only with explicit authorization and a typed
   confirmation of the application name.
3. Safe reruns: resources already deleted are skipped.

## Non-goals

* Pruning old artifacts of a live application (the other part of TODO
  item 13): a later specification.
* IAM policies and dynamic groups (administrator only, Spec 019), the
  identity-domain confidential application, OCI Vault secrets, the
  Generative AI project, and the agent folder: they are never touched, and
  the plan lists them as kept.
* Deleting resources found by a name pattern, or resources in another
  compartment. Every target comes from the manifest and the tool's tenancy
  settings.
* Restoring data: deleting the application loses its storage data, and
  deleting the repository loses its images.

## Platform facts

| # | Fact | Evidence |
| --- | --- | --- |
| F1 | The active deployment cannot be deleted alone: `409 Conflict`, "Hosted deployment cannot be deleted … because it is not active". | Spike, 2026-10-14. |
| F2 | `hosted-application delete` deletes the application and its deployments; it ended `SUCCEEDED` in about 1 minute, both `DELETED`. | Spike. |
| F3 | The managed storage survives the deletion of its application (`ACTIVE`, empty `application-ids`); `hosted-application-storage delete` takes about 2.5 minutes and ends `DELETED`. | Spike; Spec 026 F6, F8. |
| F4 | `artifacts container repository delete --repository-id … --force` deletes the repository with its images; a later `get` answers 404. `artifacts container repository list --compartment-id … --display-name …` finds it by name. | Spike; OCI CLI 3.95.0 help. |
| F5 | OCIR repository names are unique per tenancy namespace and region, and image paths do not include the compartment, so another compartment's application may pull images of this repository. | Spec 019. |
| F6 | The build tags the local image `<name>:<tag>`; the push adds `<registry>/<namespace>/<repository>:<tag>`. | `scripts/build_image.sh`, `scripts/push_ocir_image.sh`. |

## Intended behavior

1. **Inputs.** `--manifest PATH`, `--plan` (default) or `--apply`, and with
   `--apply` the mandatory `--confirm <application_name>`, which must equal
   `deploy.application_name` exactly. PowerShell: `-Manifest`, `-Plan`,
   `-Apply`, `-Confirm`. Tenancy settings come from the tool's `.env`, as for
   the other skills.
2. **Targets**, resolved read-only in the deployment compartment:
   * the non-deleted Hosted Application named `deploy.application_name` and
     its deployment, with their OCIDs, states, and active tag;
   * with `deploy.storage`: the storage named `<application_name>-storage`,
     only if its `application-ids` contain this application or are empty;
     a storage linked to another application is reported and kept;
   * the repository named `publish.repository` in the compartment, with its
     number of images;
   * the local images of the repositories `<name>` and
     `<registry>/<namespace>/<repository>`, all tags, for the selected
     container engine (Docker or Podman, as for build).
3. **Repository protection.** Before planning the repository deletion, list
   the other Hosted Applications of the compartment and their deployments; if
   any artifact uses `<registry>/<namespace>/<repository>`, keep the
   repository and say which application uses it. Applications in other
   compartments cannot be checked (F5): the plan says so.
4. **Plan.** One line per target with its action (`delete`, `already
   deleted`, `keep` with the reason), the warnings "the data of the managed
   storage is lost" and "the images of the repository are lost", the list of
   resources that are kept (non-goals), and the expected time (several
   minutes with storage).
5. **Apply**, in this order, each step only if planned:
   1. delete the Hosted Application (this deletes its deployment, F1, F2)
      and wait for `DELETED` with the bounded wait of
      [Spec 012](012-reliable-deploy-wait.md);
   2. delete the storage and wait for `DELETED`;
   3. delete the repository;
   4. remove the local images; an image used by a container is kept and
      reported.
   A failure stops the remaining steps, reports what was deleted and what is
   left, and exits; a rerun continues from there.
6. **States that stop before any deletion** (exit 20): the application is
   `CREATING` or `UPDATING`, or its deployment is `CREATING` or `UPDATING`;
   more than one non-deleted application or storage with the name.
7. **Nothing to delete:** every target already deleted or absent; exit 0
   with a clear message.
8. **Container engine not available:** the OCI steps run; the local images
   are reported as not removed, with the command to remove them by hand;
   exit 0 with a warning.
9. **Permissions.** A `NotAuthorizedOrNotFound` on a delete stops with the OCI
   message and the IAM rule of Spec 019: report and stop, never change IAM.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Plan completed, teardown completed, or nothing to delete. |
| 1 | An OCI or tool operation failed; the report says what is left. |
| 20 | A state requires review before any deletion (item 6). |
| 26 | OCI is still deleting after the wait timeout; rerun to continue waiting. |
| 64 | Invalid arguments, manifest errors, missing tenancy settings, or a missing or different `--confirm`. |
| 65 | The configured OCI region is not available to the OCI CLI profile. |

## Skill (`skills/oci-agent-teardown/SKILL.md`)

* Use when the user asks to delete, remove, tear down, or clean up an agent
  and its resources. Target platform check of Spec 028.
* Workflow: run the plan, show it in full, ask the user to authorize it and
  to type the application name; run `--apply --confirm <name>` only after
  both, in the same conversation. Never apply on a summary of the plan, and
  never infer the confirmation from earlier messages.
* Never run teardown as a fix for a failed release; for a `FAILED`
  deployment the deploy skill offers the replacement.

## Documentation

* `skills/README.md`, the main README skill table, and both Getting started
  guides: the new skill.
* `skills/oci-agent-deploy/SKILL.md`: the manual cleanup paragraph of
  Spec 026 points to the new skill.
* [Spec 009](009-release-new-version.md): a note that criterion 5 is revised
  by this specification for `oci-agent-teardown` only.
* `TODO.md` item 13: teardown done; pruning remains.
* `CHANGELOG.md`.

## Tests (offline)

* Fake OCI CLI scenarios, both script families: plan never mutates; full
  teardown with and without storage; rerun after a partial failure; nothing
  to delete; repository kept when another application uses it; storage kept
  when linked to another application; stop states (exit 20); missing or
  wrong `--confirm` (exit 64) before any OCI call; permission error on a
  delete (exit 1, IAM message).
* Fake container engine: images of both names removed; an image in use is
  kept; engine unavailable gives a warning and exit 0.
* `tests/test_skills.py`: the skill has the platform check, the confirmation
  rule, and the kept-resources list.

## Acceptance criteria

1. The offline tests, Black, Pylint, and pytest pass; links resolve.
2. Live: an agent released with `deploy.storage` (for example a copy of
   `hello_world`) is torn down; read-only checks show the application,
   deployment, and storage `DELETED`, the repository gone (404), and no local
   image of the agent; a second run reports nothing to delete.
3. Live: the plan of an application whose repository is used by another
   application keeps the repository.

## Open points

* Permissions of an operator who is not an administrator for the storage
  delete (Spec 026 criterion 3).
* Whether a repository can be deleted while an application of another
  compartment still uses its images (F5).

## Verification record

### 2026-10-16, macOS, local

* Decision: the teardown logic is one Python module,
  `scripts/teardown_agent.py`, and `teardown_agent.sh` and `teardown_agent.ps1`
  are thin wrappers that select the Python interpreter and pass the options
  (the pattern of `new_agent.py`). The two shells therefore cannot diverge in
  behavior, output, or exit codes. The module reads the tenancy settings
  through `tool_config.py` (environment first, then the tool's `.env`) and
  calls the OCI CLI and the container engine as subprocesses.
* Decision: with `--container-engine auto`, every usable engine (Docker and
  Podman, CLI on PATH and `info` succeeding) is cleaned; an image that a
  container uses, or any image that the engine refuses to remove, is kept and
  reported, and the teardown still ends with exit 0.
* Skill `skills/oci-agent-teardown` (`SKILL.md`, `agents/openai.yaml`) with
  the target platform check of Spec 028, the full-plan and typed-name rules,
  and the table of deleted and kept resources.
* Documentation: README (flow diagram, skill table, "Talk to Codex"),
  `skills/README.md`, both Getting started guides, the quickstart, the usage
  guide, the deploy skill's cleanup paragraph, the migration note (skill
  count), Spec 009 criterion 5, `TODO.md` item 13, `CHANGELOG.md`. The
  overview image is unchanged (decided by the user).
* Read-only plan against OCI (eu-frankfurt-1, OCI CLI 3.95.0) for
  `demos/hello_world`: compartment resolved; `hello-world` application not
  found; repository `agents/hello-world` found with 3 images and planned for
  deletion; no other application of the compartment uses it; the container
  engine (Rancher Desktop) was not running, so the local images were
  reported as not removable. Nothing was deleted.
* Offline: `tests/test_teardown.py` (plan without mutations; exact
  confirmation before any OCI call; full teardown in order; rerun with
  nothing to delete; manifest without storage; repository and storage kept
  when used by another application; busy states, exit 20; permission error
  with the IAM rule; partial failure and rerun; wait timeout, exit 26; image
  in use; engine unavailable; Bash wrapper; PowerShell wrapper, skipped
  without `pwsh`) and `tests/test_skills.py` (the teardown workflow rules).
* `tests/test_script_parity.py`: `--container-engine` is excluded from the
  Bash/PowerShell comparison, because the teardown offers it in both shells.
* Full suite: 459 passed, 158 skipped (all `pwsh is unavailable`); Black and
  Pylint (10.00/10) passed; links resolve.
* Not verified: Windows execution of the module through `teardown_agent.ps1`
  (the OCI CLI is called from Python, not from PowerShell, so the PowerShell
  hooks of the OCI CLI are not involved).
* Pending: acceptance criteria 2 and 3 (live).

### 2026-10-16, live acceptance (operator-reported)

* The operator ran the teardown live after the commit and reported that
  everything worked. No detailed output was recorded in this specification;
  criterion 3 (repository kept because another application uses it) and the
  Windows execution are not confirmed separately.
