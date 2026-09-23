# Repository skills

| Skill | Purpose | Status |
| --- | --- | --- |
| [oci-agent-build](oci-agent-build/SKILL.md) | Build and verify a `linux/amd64` agent image without pushing or deploying. | Implemented; see [Spec 001](../specs/001-skill-oci-agent-build.md) for verification evidence. |
| [oci-agent-push](oci-agent-push/SKILL.md) | Prepare and, with explicit authorization, push a verified image to OCIR in the OC1 realm. | Implemented; remote acceptance passed for Frankfurt; see [Spec 002](../specs/002-skill-oci-agent-push.md). |
| [oci-agent-deploy](oci-agent-deploy/SKILL.md) | Plan or, with explicit authorization, deploy a verified OCIR image to OCI Generative AI Hosted Applications. | Implemented; remote creation acceptance passed for Frankfurt; endpoint invocation not performed; see [Spec 003](../specs/003-skill-oci-agent-deploy.md). |
| [oci-agent-verify-deployment](oci-agent-verify-deployment/SKILL.md) | Verify an active Hosted Application release with OCI state checks and health/readiness probes. | Implemented; static and live Frankfurt verification passed for `hello-world:0.2.0`; see [Spec 005](../specs/005-skill-oci-agent-verify-deployment.md). |

## Discovery in this repository

The repository link `.agents/skills -> ../skills` exposes the skill directory to
Codex. Codex scans `.agents/skills` from the working directory up to the repository
root and follows symlinks. Each skill needs a directory containing `SKILL.md`.
Placing it under `skills/` alone does not make it visible without a discovery link.

The link, `SKILL.md`, and supporting scripts are present. Actual discovery in the
Codex skill selector remains to be verified under criterion 8 of Spec 001.

## Use from other repositories

Optionally run these commands from this repository's root
to expose the skill at user scope:

```bash
mkdir -p "$HOME/.agents/skills"
ln -s "$PWD/skills/oci-agent-build" "$HOME/.agents/skills/oci-agent-build"
```

The destination must not already exist. Keep this checkout at its linked location;
the skill depends on this repository's scripts. Remove only the user symlink to
uninstall it. These commands are instructions, not part of repository setup.

Codex scans `$HOME/.agents/skills/` across repositories. Use `$` or `/skills` in
supported Codex surfaces to select a completed skill. Restart Codex if it does not
appear after changes.

Source: [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills), reviewed
2026-09-22 for repository scanning, user scope, and symlink support.
