# Migrating to OCI Agent Shipyard

On 2026-10-14 the project `codex-4-oci-enterprise-ai-deployment` was renamed
**OCI Agent Shipyard** ([Spec 025](../specs/025-rename-to-oci-agent-shipyard.md)).
The repository, the recommended folder of the tool home, and the Conda
environment are now all called `oci-agent-shipyard`.

Follow this page once on each workstation where you installed the project
with the old name. It takes about ten minutes. New users follow Getting
started instead.

## What changes and what does not

| Item | Before | After |
| --- | --- | --- |
| GitHub repository | `luigisaetta/codex-4-oci-enterprise-ai-deployment` | `luigisaetta/oci-agent-shipyard` |
| Tool home folder | `…/codex-4-oci-enterprise-ai-deployment` | `…/oci-agent-shipyard` |
| Conda environment | `codex-4-oci-enterprise-ai-deployment` | `oci-agent-shipyard` |

These do **not** change: the skill names (`oci-agent-*`), the tool's `.env`
(it moves with the folder), your agent folders and their `agent.yaml`, and
your Hosted Applications in OCI.

GitHub redirects the old address to the new one, so nothing breaks at once.
The steps below align your workstation with the new name.

## Why the order matters

The installed skills are links to the tool home folder. Remove them **before**
renaming the folder: after the rename, the old links point to a folder that no
longer exists, and the installer does not replace a link that points
elsewhere. If you renamed the folder first, see
[Troubleshooting](#troubleshooting).

## macOS and Linux (Terminal)

Run the commands from the **old** tool home, with the old environment active
if you use it. Replace `~/Progetti` with the folder that contains your tool
home.

1. Get the latest version, which uses the new name:

   ```bash
   cd ~/Progetti/codex-4-oci-enterprise-ai-deployment
   ```

   ```bash
   git pull
   ```

2. Remove the skill links of the old folder:

   ```bash
   scripts/install_skills.sh --uninstall
   ```

   Expected: one `removed:` line per skill. If you also installed the skills
   for Claude Code, repeat with `--target ~/.claude/skills`.

3. Point Git to the new repository address:

   ```bash
   git remote set-url origin https://github.com/luigisaetta/oci-agent-shipyard.git
   ```

4. Rename the folder:

   ```bash
   cd ~/Progetti && mv codex-4-oci-enterprise-ai-deployment oci-agent-shipyard
   ```

5. Create the new environment and install the libraries:

   ```bash
   conda create -n oci-agent-shipyard python=3.11 -y
   ```

   ```bash
   conda activate oci-agent-shipyard
   ```

   ```bash
   cd ~/Progetti/oci-agent-shipyard && python -m pip install -r requirements-dev.txt
   ```

   If you use venv or pyenv instead of Conda, create a new environment in the
   same way and install `requirements-dev.txt`.

6. Install the skills again, from the new folder:

   ```bash
   scripts/install_skills.sh
   ```

   Expected: one `created:` line per skill. Add `--target ~/.claude/skills` if
   you use Claude Code too.

7. Check the setup:

   ```bash
   scripts/check_setup.sh
   ```

   Expected: every line says `PASS`.

8. Start a **new** Codex session and type `$`: the list must include the six
   `oci-agent-*` skills.

9. Optional, when everything works, remove the old environment:

   ```bash
   conda env remove -n codex-4-oci-enterprise-ai-deployment
   ```

## Windows (PowerShell 7)

Run the commands from the **old** tool home. Replace `$HOME\Projects` with the
folder that contains your tool home.

1. Get the latest version:

   ```powershell
   Set-Location "$HOME\Projects\codex-4-oci-enterprise-ai-deployment"
   ```

   ```powershell
   git pull
   ```

2. Remove the skill links of the old folder:

   ```powershell
   ./scripts/install_skills.ps1 -Uninstall
   ```

3. Point Git to the new repository address:

   ```powershell
   git remote set-url origin https://github.com/luigisaetta/oci-agent-shipyard.git
   ```

4. Rename the folder. Close any editor or terminal that has it open first:

   ```powershell
   Set-Location "$HOME\Projects"
   ```

   ```powershell
   Rename-Item codex-4-oci-enterprise-ai-deployment oci-agent-shipyard
   ```

5. Create the new environment and install the libraries:

   ```powershell
   conda create -n oci-agent-shipyard python=3.11 -y
   ```

   ```powershell
   conda activate oci-agent-shipyard
   ```

   ```powershell
   Set-Location "$HOME\Projects\oci-agent-shipyard"; python -m pip install -r requirements-dev.txt
   ```

6. Install the OCI CLI hooks in the new environment (step 3 of
   [Getting started on Windows](getting-started-windows.md)), then open a new
   PowerShell 7 window and activate the environment again:

   ```powershell
   ./scripts/install_oci_powershell_hook.ps1
   ```

7. Install the skills again and check the setup, from the new folder:

   ```powershell
   ./scripts/install_skills.ps1
   ```

   ```powershell
   ./scripts/check_setup.ps1
   ```

   Expected: every line says `PASS`.

8. Start a **new** Codex session and type `$`: the six `oci-agent-*` skills
   must be listed.

9. Optional, when everything works:

   ```powershell
   conda env remove -n codex-4-oci-enterprise-ai-deployment
   ```

## Other places that may use the old name

* **`OCI_AGENT_PYTHON`**: if you set it to the Python of the old environment,
  set it to the new one, or remove it and activate `oci-agent-shipyard`.
* **Shortcuts, editor workspaces, and scripts of your own** that open the old
  folder: update the path.
* **Agent folders**: nothing to do. Their `AGENTS.md` block finds the tool
  home through the installed skill links.

## Troubleshooting

| Symptom | Cause | What to do |
| --- | --- | --- |
| `install_skills` reports `conflict:` for the skills | The folder was renamed before step 2: the old links still exist and point to the old path. | Remove only the links to the old path (commands below), then run `install_skills` again. |
| `check_setup` reports a message about Python and PyYAML | The new environment is not active, or `OCI_AGENT_PYTHON` points to the old one. | `conda activate oci-agent-shipyard`; check `OCI_AGENT_PYTHON`. |
| `conda activate oci-agent-shipyard` fails | The environment was not created, or the shell is not initialized for Conda. | Repeat step 5; see step 3 of Getting started. |
| Codex does not list the skills | The Codex session started before step 6. | Start a new Codex session. |
| On Windows, `oci os ns get` prints `Get-Acl` errors | The OCI CLI hooks are not installed in the new environment. | Repeat step 6 of the Windows section. |

Remove only the skill links that point to the old folder, on macOS and Linux:

```bash
find ~/.agents/skills -maxdepth 1 -type l -lname '*codex-4-oci-enterprise-ai-deployment*' -print -delete
```

On Windows, in PowerShell 7:

```powershell
Get-ChildItem "$HOME\.agents\skills" | Where-Object { $_.LinkTarget -like '*codex-4-oci-enterprise-ai-deployment*' } | Remove-Item -Verbose
```

Both commands print each link they remove and touch nothing else.
