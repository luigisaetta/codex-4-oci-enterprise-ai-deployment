# Spec 004: Project README skill usage guidance

Status: implemented.
Date: 2026-09-22.

## Problem

The repository contains a usable Codex skill, but the project README does not
tell a contributor how to discover, select, or use it. The guidance must also
provide a stable place for future repository skills without duplicating each
skill's operational instructions.

## Scope

Add a concise "Using repository skills" section to the root README. It must:

* explain the repository and optional user-scope discovery mechanisms;
* state how to select a skill in a supported Codex surface and what to check if
  it is not displayed;
* maintain a growing list of the skills currently available in this repository;
* link each skill to its own instructions and to the detailed skill index.

The initial list contains `oci-agent-build`. Its own `SKILL.md` remains the
authoritative source for prerequisites, required inputs, and workflow.

## Non-goals

* Change skill discovery configuration or install a skill globally.
* Change build scripts, container files, or deployment behavior.
* Claim that a local container check verifies OCI deployment compatibility.

## Assumptions and prerequisites

The checkout contains `.agents/skills -> ../skills`, and Codex supports
repository or user-scope skill discovery as documented by OpenAI's Build skills
guide. User-scope use requires a deliberate symlink and a stable checkout path.

## Intended behavior and acceptance criteria

The README gives a contributor enough information to use `oci-agent-build` in
the current checkout, directs them to the per-skill instructions before use, and
has an obvious table row pattern for future skills. It makes clear that placing
a directory under `skills/` alone is insufficient for discovery. It does not
contain credentials, machine-specific paths, or unverified deployment claims.

## Verification

2026-09-22: Reviewed the README links and commands against
`skills/README.md`, `skills/oci-agent-build/SKILL.md`, and Spec 001. This is a
documentation-only change; no Docker build, container verification, or OCI
operation was run.
