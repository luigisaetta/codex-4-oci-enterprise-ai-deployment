# Repository skills

| Skill | Purpose | Status |
| --- | --- | --- |
| [oci-agent-build](oci-agent-build/SKILL.md) | Build and verify a `linux/amd64` agent image without pushing or deploying. | Implemented; see [Spec 001](../specs/001-skill-oci-agent-build.md) for verification evidence. |
| [oci-agent-push](oci-agent-push/SKILL.md) | Prepare and, with explicit authorization, push a verified image to OCIR in the OC1 realm. | Implemented; remote acceptance passed for Frankfurt; see [Spec 002](../specs/002-skill-oci-agent-push.md). |
| [oci-agent-deploy](oci-agent-deploy/SKILL.md) | Plan or, with explicit authorization, deploy a verified OCIR image to OCI Generative AI Hosted Applications. | Implemented; remote creation acceptance passed for Frankfurt; endpoint invocation not performed; see [Spec 003](../specs/003-skill-oci-agent-deploy.md). |
| [oci-agent-verify-deployment](oci-agent-verify-deployment/SKILL.md) | Verify an active Hosted Application release with OCI state checks and health/readiness probes. | Implemented; static and live Frankfurt verification passed for `hello-world:0.2.0`; see [Spec 005](../specs/005-skill-oci-agent-verify-deployment.md). |

## Choosing Bash or PowerShell

Every lifecycle script exists twice, as `scripts/<name>.sh` and
`scripts/<name>.ps1`, with the same options, report lines, and exit codes.
The `SKILL.md` files show Bash examples only; translate them with this rule:

* **Bash or zsh** (macOS, Linux, WSL2 on Windows): run `scripts/*.sh` with
  `--option` names, exactly as shown.
* **PowerShell 7.4+** (`pwsh` on Windows): run the `scripts/*.ps1` twin with the
  same names in `-Option` form. Legacy Windows PowerShell 5.1 is rejected.

| Bash | PowerShell |
| --- | --- |
| `scripts/build_image.sh --manifest PATH --tag TAG` | `.\scripts\build_image.ps1 -Manifest PATH -Tag TAG` |
| `--timeout-seconds 120` | `-TimeoutSeconds 120` |
| `--apply`, `--push`, `--create`, `--functional`, `--no-cache` | `-Apply`, `-Push`, `-Create`, `-Functional`, `-NoCache` |
| `--application-id OCID` | `-ApplicationId OCID` |
| `OCIR_REGISTRY="$(scripts/resolve_ocir_registry.sh)"` | `$OCIR_REGISTRY = .\scripts\resolve_ocir_registry.ps1` |
| `docker login ...` | `docker login ...` or `podman login ...`, matching the selected engine |

The decision follows the shell, not the operating system: a WSL2 session on
Windows uses the Bash scripts. Never mix the two families within one release.
The only PowerShell-only parameter is `-ContainerEngine Auto|Docker|Podman`
(default `Auto`, which requires exactly one usable engine). Exit-code tables in
the skills apply to both families. `tests/test_script_parity.py` keeps the
option sets aligned. Windows setup: [native PowerShell 7](../notes/windows-powershell-native.md)
or [Rancher Desktop with WSL2](../notes/windows-rancher-desktop-wsl2.md);
design in [Spec 007](../specs/007-windows-powershell-support.md).

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
