# Repository skills

The new-agent skill drafts an agent specification (`agent-spec.md`) from a
short request, starting with the business context (customer persona, use
case, expected outcomes, and optional concerns), applies the defaults in its
[agent guidelines](oci-agent-new/references/agent-guidelines.md), and, after
the developer approves the specification, writes the files the other skills
need. It changes local files only.

The deploy skill handles first releases, new versions, rollbacks, waits for
creations in progress, and explicitly requested replacement of a `FAILED`
deployment in the same Hosted Application.

The `public-idcs` profile creates a public endpoint that requires an OCI IAM
identity-domain bearer token. Its manifest contains only the domain URL,
audience, and scope. The confidential-application credentials stay in the
tool's `.env` or the operator's shell (for verification) and in the agent's
`ui/.env.local` (for its demo UI), never in the manifest.

| Skill | Purpose | Status |
| --- | --- | --- |
| [oci-agent-new](oci-agent-new/SKILL.md) | Draft an agent specification, then create the agent repository from it: `agent.yaml`, `Dockerfile`, a FastAPI agent, and functional checks. | Implemented; agents created with it were released and verified on OCI; see [Spec 011](../specs/011-skill-oci-agent-new.md). |
| [oci-agent-ui](oci-agent-ui/SKILL.md) | Draft a demo UI specification from the agent's specification, then create a local, end-user Next.js demo page in `ui/`. | Implemented; used on real agents against the deployed agent; see [Spec 018](../specs/018-skill-oci-agent-ui.md). |
| [oci-agent-build](oci-agent-build/SKILL.md) | Build and verify a `linux/amd64` agent image without pushing or deploying. | Implemented; see [Spec 001](../specs/001-skill-oci-agent-build.md) for verification evidence. |
| [oci-agent-push](oci-agent-push/SKILL.md) | Prepare and, with explicit authorization, push a verified image to OCIR in the OC1 realm. | Implemented; remote acceptance passed for Frankfurt; see [Spec 002](../specs/002-skill-oci-agent-push.md). |
| [oci-agent-deploy](oci-agent-deploy/SKILL.md) | Plan or, with explicit authorization, deploy a verified OCIR image, resume creation, or replace a `FAILED` deployment on request. | Bash and PowerShell implemented; a Podman-backed Windows release and verification passed for an existing Hosted Application. See [Spec 007](../specs/007-windows-powershell-support.md) and [Spec 012](../specs/012-reliable-deploy-wait.md). |
| [oci-agent-verify-deployment](oci-agent-verify-deployment/SKILL.md) | Verify an active Hosted Application release with OCI state checks and health/readiness probes. | Implemented; static and live Frankfurt verification passed for `hello-world:0.2.0`; see [Spec 005](../specs/005-skill-oci-agent-verify-deployment.md). |

## Choosing the platform

These skills support one platform: OCI Generative AI Hosted Applications
(also called Hosted Deployments or OCI Enterprise AI). Skills for OCI AI Data
Platform (AI DP) are planned. Codex chooses the skills in this order
([Spec 028](../specs/028-platform-dispatch.md)):

1. The "Target platform" section of the agent folder's `AGENTS.md`, written
   when the agent is created (`scripts/agent_instructions.py ensure`).
2. Without it, the files of the folder: `agent.yaml` and a `Dockerfile` mean
   Hosted Applications.
3. Otherwise, the skill asks. `oci-agent-new` asks for the platform when the
   request does not state it.

If the platform is AI DP, every skill of this repository stops and says so.

## Choosing Bash or PowerShell

The helper of `oci-agent-new`, `$TOOL_HOME/scripts/new_agent.py`, is Python
only and runs the same way in both shells.

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
| `--timeout-seconds SECONDS` | `-TimeoutSeconds SECONDS` |
| `--replace-failed` | `-ReplaceFailed` |
| `--apply`, `--push`, `--create`, `--functional`, `--no-cache` | `-Apply`, `-Push`, `-Create`, `-Functional`, `-NoCache` |
| `--application-id OCID` | `-ApplicationId OCID` |
| `--manifest PATH`, `--skills-target DIR` | `-Manifest PATH`, `-SkillsTarget DIR` |
| `OCIR_REGISTRY="$("$TOOL_HOME/scripts/resolve_ocir_registry.sh")"` | `$OCIR_REGISTRY = & "$TOOL_HOME\scripts\resolve_ocir_registry.ps1"` |
| `docker login ...` | `docker login ...` or `podman login ...`, matching the selected engine |

The decision follows the shell, not the operating system: a WSL2 session on
Windows uses the Bash scripts. Never mix the two families within one release.
The deploy timeout defaults to 1800 seconds. Replacement is accepted only for
a `FAILED` deployment after the user requests it and approves the plan.
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

Repository-scope discovery remains available. The Windows pilot confirmed
that all six installed skills appeared in the skill picker from a new Codex
session opened in the separate agent folder; see
[the pilot record](../docs/windows-ace-pilot.md).
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
