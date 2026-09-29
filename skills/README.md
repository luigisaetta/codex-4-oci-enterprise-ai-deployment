# Repository skills

| Skill | Purpose | Status |
| --- | --- | --- |
| [oci-agent-build](oci-agent-build/SKILL.md) | Build and verify a `linux/amd64` agent image without pushing or deploying. | Implemented; see [Spec 001](../specs/001-skill-oci-agent-build.md) for verification evidence. |
| [oci-agent-push](oci-agent-push/SKILL.md) | Prepare and, with explicit authorization, push a verified image to OCIR in the OC1 realm. | Implemented; remote acceptance passed for Frankfurt; see [Spec 002](../specs/002-skill-oci-agent-push.md). |
| [oci-agent-deploy](oci-agent-deploy/SKILL.md) | Plan or, with explicit authorization, deploy a verified OCIR image to OCI Generative AI Hosted Applications. | Implemented; remote creation acceptance passed for Frankfurt; endpoint invocation not performed; see [Spec 003](../specs/003-skill-oci-agent-deploy.md). |
| [oci-agent-verify-deployment](oci-agent-verify-deployment/SKILL.md) | Verify an active Hosted Application release with OCI state checks and health/readiness probes. | Implemented; static and live Frankfurt verification passed for `hello-world:0.2.0`; see [Spec 005](../specs/005-skill-oci-agent-verify-deployment.md). |

## Choosing Bash or PowerShell

Every lifecycle script exists twice, as `$TOOL_HOME/scripts/<name>.sh` and
`$TOOL_HOME\scripts\<name>.ps1`, with the same options, report lines, and exit codes.
The `SKILL.md` files show Bash examples only; translate them with this rule:

* **Bash or zsh** (macOS, Linux, WSL2 on Windows): run `scripts/*.sh` with
  `--option` names, exactly as shown.
* **PowerShell 7.4+** (`pwsh` on Windows): run the `scripts/*.ps1` twin with the
  same names in `-Option` form. Legacy Windows PowerShell 5.1 is rejected.

| Bash | PowerShell |
| --- | --- |
| `$TOOL_HOME/scripts/build_image.sh --manifest PATH --tag TAG` | `& "$TOOL_HOME\scripts\build_image.ps1" -Manifest PATH -Tag TAG` |
| `$TOOL_HOME/scripts/install_skills.sh [--dry-run] [--uninstall] [--target DIR]` | `& "$TOOL_HOME\scripts\install_skills.ps1" [-DryRun] [-Uninstall] [-Target DIR]` |
| `--timeout-seconds 120` | `-TimeoutSeconds 120` |
| `--apply`, `--push`, `--create`, `--functional`, `--no-cache` | `-Apply`, `-Push`, `-Create`, `-Functional`, `-NoCache` |
| `--application-id OCID` | `-ApplicationId OCID` |
| `OCIR_REGISTRY="$("$TOOL_HOME/scripts/resolve_ocir_registry.sh")"` | `$OCIR_REGISTRY = & "$TOOL_HOME\scripts\resolve_ocir_registry.ps1"` |
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

Opening this repository exposes the skills through `.agents/skills -> ../skills`.
Alternatively, the installer links each skill into `$HOME/.agents/skills`, so a
separate agent repository can be the Codex workspace. Each skill needs a
directory containing `SKILL.md`.

Repository-scope discovery remains available. User-scope discovery from another
repository is pending step 8 verification in [Spec 008](../specs/008-user-scope-skills.md).
Every skill can be selected from a natural request. Push and deploy still ask
for approval before each remote change.

## Install at user scope

Run the installer from the folder of this checkout (the tool home):

```bash
scripts/install_skills.sh
scripts/install_skills.sh --dry-run
scripts/install_skills.sh --uninstall
scripts/install_skills.sh --target /path/to/skills
```

An existing link to the same source is unchanged. Any other file, folder, or
link is a conflict, remains untouched, and makes the installer exit non-zero.
Uninstall removes only links resolving to this checkout's skills. If the tool
home moves, old links are conflicts and must be removed by hand. Keep the tool
home at its installed location and start a new Codex session after changes.

Codex scans `$HOME/.agents/skills/` across repositories. Use `$` or `/skills` in
supported Codex surfaces to select a completed skill. Restart Codex if it does not
appear after changes.

Source: [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills), reviewed
2026-09-22 for repository scanning, user scope, and symlink support.
