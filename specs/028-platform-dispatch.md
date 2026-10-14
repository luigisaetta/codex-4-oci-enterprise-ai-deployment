# Spec 028: platform dispatch, to prepare OCI AI Data Platform skills

Status: implemented; offline checks passed (2026-10-14); live acceptance pending.
Date: 2026-10-14.
Amends [Spec 011](011-skill-oci-agent-new.md) and
[Spec 018](018-skill-oci-agent-ui.md) (target platform check),
[Spec 020](020-demo-customer-name.md) (the `AGENTS.md` block), and the
target platform checks of the build, push, deploy, and verify skills
([Spec 001](001-skill-oci-agent-build.md),
[Spec 002](002-skill-oci-agent-push.md),
[Spec 003](003-skill-oci-agent-deploy.md),
[Spec 005](005-skill-oci-agent-verify-deployment.md)).

## Problem

The tool will gain skills for a second platform, OCI AI Data Platform
(AI DP): creating the code of an agent, deploying it, and verifying it. Codex
must then use the right family of skills for each agent, without risk for the
existing skills of OCI Generative AI Hosted Applications.

Today the platform is **inferred**: each skill reads its description and, in
its "Target platform check", looks at the files of the repository
(`agent.yaml` and `Dockerfile` for Hosted Applications; an entry class with a
synchronous `setup()` and an asynchronous `invoke()` for AI DP). This has two
gaps:

* An empty folder, before an agent exists, gives no signal. `oci-agent-new`
  assumes Hosted Applications and only asks when the request is unclear.
* The lifecycle skills name one AI DP skill (`aidp-agent-deploy`), installed
  from another repository. The names of the future AI DP skills are not
  decided, and may conflict with it.

## Scope

1. The platform of an agent is **declared** once, when the agent is created,
   in a "Target platform" section of the `AGENTS.md` block that
   `scripts/agent_instructions.py` writes. Codex reads `AGENTS.md` in every
   session, before it chooses a skill.
2. The target platform check of every `oci-agent-*` skill reads that
   declaration first, and the repository files only when it is absent.
3. `oci-agent-new` asks for the platform when the request does not state it,
   offering the two options.
4. Descriptions and checks name the platforms with the agreed names and
   synonyms, and refer to "the skills for OCI AI DP" without naming them.
5. A test keeps the dispatch rules consistent across all skills.

## Non-goals

* Any AI DP skill, script, template, or guideline. Their names, their
  location, and the `AGENTS.md` block they write belong to the specification
  of the first AI DP skill.
* Changes to the build, push, deploy, verify, or UI scripts, or to any
  Python module. Only skill instructions, the `AGENTS.md` block, tests, and
  documentation change.
* A router skill: Codex chooses skills from their descriptions; the
  declaration in `AGENTS.md` and precise descriptions do the dispatch.
* Writing the declaration automatically from the build, deploy, or verify
  skills: they only read it, so that a release never writes files in the
  agent repository.

## Platform names

| Platform | Name in the files | Synonyms that a request may use |
| --- | --- | --- |
| Hosted Applications | OCI Generative AI Hosted Applications | Hosted Applications, Hosted Deployments, OCI Enterprise AI |
| AI DP | OCI AI Data Platform (AI DP) | AI Data Platform, AI DP |

## Intended behavior

1. **Declaration.** The `AGENTS.md` block gains a section, inside the
   existing markers so that `ensure` updates repositories in place:

   ```markdown
   ## Target platform

   * This agent targets OCI Generative AI Hosted Applications (also called
     Hosted Deployments or OCI Enterprise AI).
   * Use the `oci-agent-*` skills of the OCI agent skills to create, build,
     push, deploy, verify, and demo it. Never use the skills for OCI AI Data
     Platform (AI DP) on this repository.
   ```

   The markers and the other sections are unchanged.
2. **Lifecycle skills** (`oci-agent-build`, `oci-agent-push`,
   `oci-agent-deploy`, `oci-agent-verify-deployment`) and **`oci-agent-ui`**.
   Before any command, in this order:
   1. If the repository's `AGENTS.md` has a "Target platform" section, follow
      it. If it names AI DP, stop: "This agent targets OCI AI Data Platform
      (AI DP); these skills support only OCI Generative AI Hosted
      Applications. Use the skills for OCI AI DP."
   2. Otherwise, infer from the files as today (`agent.yaml` with
      `schema_version` and a `Dockerfile`: Hosted Applications; an entry class
      with a synchronous `setup()` and an asynchronous `invoke()` without
      `agent.yaml`: AI DP, stop with the message above).
   3. If the signals are mixed or absent, ask which platform the user means.
   4. Never switch platform silently.
3. **`oci-agent-new`.** Before drafting the specification:
   * If the request names a platform (or a synonym), use it.
   * Otherwise ask, in one message, with the two options: "OCI Generative AI
     Hosted Applications (Hosted Deployments, OCI Enterprise AI)" or "OCI AI
     Data Platform (AI DP)".
   * If the developer chooses AI DP, stop: this skill creates agents only for
     Hosted Applications; use the skills for OCI AI DP.
   * Write the chosen platform in the Deployment section of the draft. The
     declaration is written by `agent_instructions.py ensure` in workflow
     step 6, as today.
4. **Descriptions.** The description of each `oci-agent-*` skill names
   OCI Generative AI Hosted Applications and its synonyms, and states that it
   is not for OCI AI Data Platform (AI DP) agents. None names an AI DP skill.
5. **Existing agents.** An agent repository without the "Target platform"
   section keeps working through the inference of item 2. The Getting started
   guides and the changelog tell the developer to run `ensure` once to add
   the declaration.

## Documentation

* `skills/README.md`: how Codex chooses a family of skills (declaration
  first, then inference, then a question).
* `docs/quickstart.md`: the troubleshooting row about "AI Data Platform".
* `docs/getting-started-macos-linux.md` and
  `docs/getting-started-windows.md`: run `ensure` once on existing agent
  folders to add the declaration.
* `CHANGELOG.md`.

## Tests (offline)

* `tests/test_skills.py`: every skill has a target platform check that
  mentions the "Target platform" section of `AGENTS.md`, names OCI
  Generative AI Hosted Applications, and refers to "the skills for OCI AI DP";
  no skill names `aidp-agent-deploy` or another AI DP skill; every
  description says that the skill is not for AI DP agents; `oci-agent-new`
  offers both platforms.
* `tests/test_agent_instructions.py`: the block contains the "Target
  platform" section; `ensure` on a repository with the previous block
  replaces only the block.

## Acceptance criteria

1. The offline tests, Black, Pylint, and pytest pass; links resolve.
2. No script or Python module changes; the release case tests pass
   unchanged.
3. Live, in a new Codex session:
   * in an empty folder, "create a new agent" without a platform makes
     `oci-agent-new` ask with the two options;
   * in an agent folder refreshed with `ensure`, a release request uses the
     `oci-agent-*` skills as before;
   * in a folder whose `AGENTS.md` declares AI DP, the `oci-agent-*` skills
     stop with the message of item 2.

## Open points

* Names of the AI DP skills, and the conflict with the `aidp-agent-deploy`
  skill already installed at user scope from another repository.
* Where the AI DP skills live (this repository or another), and how
  `agent_instructions.py` writes the AI DP declaration (for example a
  `--platform` option).
* When the AI DP skills exist, whether `oci-agent-new` keeps asking or the AI
  DP creation skill becomes a separate entry point with its own question.

## Verification record

### 2026-10-14, macOS, local

* `skills/oci-agent-new/assets/agent-instructions.md`: the "Target platform"
  section, first in the block, inside the existing markers.
* The six `SKILL.md` files: the ordered target platform check (declaration,
  then files, then a question), the fixed stop message for AI DP, and the
  descriptions with the synonyms and "not for OCI AI Data Platform (AI DP)
  agents". The reference to `aidp-agent-deploy` was removed from the four
  lifecycle skills.
* `oci-agent-new`: the question with the two options; the specification
  template gains "Platform: OCI Generative AI Hosted Applications" in its
  Deployment section.
* Documentation: `skills/README.md` (section "Choosing the platform"),
  `docs/quickstart.md`, both Getting started guides.
* Decision: the stop message is the same text in every skill, so that the
  test can check it and the user sees one wording.
* Offline: `tests/test_skills.py` (platform check of every skill, compared on
  single-spaced text; no AI DP skill named in any skill file; descriptions;
  the two options of `oci-agent-new`; the template), and
  `tests/test_agent_instructions.py` (the new section). Full suite: 439
  passed, 157 skipped (all `pwsh is unavailable`); Black and Pylint
  (10.00/10) passed; links resolve. `git diff` shows no change under
  `scripts/` or `demos/` (acceptance criterion 2).
* Pending: acceptance criterion 3 (live, new Codex sessions).
