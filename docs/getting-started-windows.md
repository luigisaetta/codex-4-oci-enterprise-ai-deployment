# Getting started on Windows

This guide takes you from an empty Windows workstation to your first agent
running on OCI Enterprise AI Hosted Applications. Follow the steps in order;
each one says what it does, the command to copy, what you should see, and what
to do if it does not work. You do not need to know Python: Codex writes the
code, and the skills run the tools for you.

All commands run in **PowerShell 7** (`pwsh`), not in the older Windows
PowerShell 5.1. If you prefer to work inside WSL2 with Bash, use
[Getting started on macOS and Linux](getting-started-macos-linux.md) in the
WSL2 shell instead.

## Before you start: what you need and who provides it

| Who | What | When |
| --- | --- | --- |
| **Your tenancy administrator** | A compartment for your agents, and the IAM policies. Send them [Setup for the administrator](iam-policies.md#setup-for-the-administrator). | Once, before step 9 |
| **You** | An OCI user account in that tenancy, able to create an API signing key and an auth token for yourself. | Before step 4 |
| **You** | A Windows workstation where you can install software. Docker Desktop and Podman need WSL2 or Hyper-V, which may need administrator rights and a restart. | Now |

Ask the administrator for:

* the **name of the compartment** to use;
* the **identity domain** of your user, if it is not `Default`;
* whether your agents will call an LLM with an **API key** (simplest) or with
  **Resource Principal** (no key; needs a Generative AI project).

## 1. Install the basic tools

You need five tools. If a tool is already installed and its check below
succeeds, keep it. Otherwise install it with its official installer, or with
your organization's approved software catalog.

| Tool | What it is for | Installer |
| --- | --- | --- |
| **PowerShell 7.4 or later** | Runs the project's Windows scripts. | [Install PowerShell on Windows](https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows) |
| **Git** | Downloads this project. | [Git](https://git-scm.com/install/) |
| **Anaconda** or **Miniconda** | Creates a dedicated Python environment, so nothing else on your machine changes. | [Conda](https://docs.conda.io/projects/conda/en/stable/user-guide/install/index.html) |
| **Docker Desktop** or **Podman** | Builds and tests the agent's container image. With Docker Desktop, use Linux containers. The scripts find the engine that is running. | [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/), [Podman Desktop for Windows](https://podman-desktop.io/docs/installation/windows-install) |
| **Codex** | The assistant that runs the skills: the desktop app, the Codex CLI, or the Codex extension for VS Code. Install it and sign in. | [Codex quickstart](https://learn.chatgpt.com/docs/quickstart) |

Open **PowerShell 7** from the Start menu (its window title says
"PowerShell 7"), then check that the tools answer:

```powershell
$PSVersionTable.PSVersion
```

```powershell
git --version
```

```powershell
conda --version
```

Expected: a PowerShell version of 7.4 or later, and a version for Git and
Conda.

Then check **your container engine**. With Docker Desktop:

```powershell
docker version
```

```powershell
docker buildx version
```

Expected: both **Client** and **Server** information, and a Buildx version.

With Podman:

```powershell
podman info
```

Expected: server information, without a connection error.

Finally, open Codex, sign in, and send a test message.

| If | What to do |
| --- | --- |
| A command is not found | Install the tool, then open a new PowerShell 7 window. |
| The version is 5.1, or below 7.4 | You are in Windows PowerShell: install PowerShell 7 and open it from the Start menu. |
| `conda` is not found | Use the **Anaconda PowerShell Prompt** once to run `conda init powershell`, then open a new PowerShell 7 window. |
| `docker version` shows Client but cannot connect to the Server | Start Docker Desktop and wait until it says the engine is running. |
| `podman info` cannot connect | Start the Podman machine: `podman machine list` shows its name, then `podman machine start <name>` (usually `podman-machine-default`), or start it in Podman Desktop. Do not create a second machine if one exists. |
| Codex cannot sign in | Follow the sign-in steps of the Codex quickstart. |

## 2. Download this project

Choose a stable folder, for example `Projects` in your user folder, and clone
the project there:

```powershell
New-Item -ItemType Directory -Path "$HOME\Projects" -Force
```

```powershell
Set-Location "$HOME\Projects"
```

```powershell
git clone https://github.com/luigisaetta/codex-4-oci-enterprise-ai-deployment.git
```

```powershell
Set-Location .\codex-4-oci-enterprise-ai-deployment
```

This folder is the **tool home**: the skills point to it. **Do not move or
rename it** after step 6. To update it later, run `git pull` inside it. If you
have already cloned the project, use that folder and skip the clone.

## 3. Create the Python environment and install the libraries

Create a dedicated environment (once; skip it if it already exists):

```powershell
conda create -n codex-4-oci-enterprise-ai-deployment python=3.11 -y
```

Activate it. Do this **in every new PowerShell window** before working with
the project:

```powershell
conda activate codex-4-oci-enterprise-ai-deployment
```

Check that the environment's Python is the active one:

```powershell
python -c "import sys; print(sys.version.split()[0], sys.executable)"
```

Expected: version 3.11 or later, and a path that contains
`codex-4-oci-enterprise-ai-deployment`.

*If `conda activate` fails, or the path is not in the environment:* Conda is
not set up for PowerShell. Run this once, close the window, open a new
PowerShell 7 window, and activate again:

```powershell
conda init powershell
```

Install the libraries, from the tool home. This also installs the OCI command
line (OCI CLI):

```powershell
python -m pip install -r requirements-dev.txt
```

Expected: the command ends without errors. Check the OCI CLI:

```powershell
oci --version
```

Then prepare the OCI CLI for PowerShell 7, once, with the environment active:

```powershell
./scripts/install_oci_powershell_hook.ps1
```

Why: the OCI CLI checks the permissions of its key files with Windows
PowerShell 5.1, which cannot load its modules when started from PowerShell 7
([OCI CLI issue 655](https://github.com/oracle/oci-cli/issues/655)). The
script installs two small scripts in the Conda environment that fix the module
path while the environment is active, and restore it when you deactivate it.
If your Windows PowerShell profile has a Conda initialization block, the
script makes it skip while this environment is active, after saving a backup
copy of the profile. It never changes OCI credentials or file permissions.
Open a new PowerShell 7 window and activate the environment again before
step 4.

*If Windows refuses to run the `.ps1` script* because of the execution policy,
follow your organization's guidance; a common per-user setting is
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## 4. Connect the OCI CLI to your tenancy

The skills use the OCI CLI to talk to OCI. It needs a profile on your
workstation.

*If the OCI CLI already works on this workstation* (for example for another
project), keep its profile in `$HOME\.oci\config` and go to the connection
check below. The skills use the `DEFAULT` profile; for another one, see
[Advanced settings](#advanced-settings).

Otherwise, create a profile with a guided command:

```powershell
oci setup config
```

It asks for a few values; accept the default for the others:

| Question | Where to find the answer |
| --- | --- |
| User OCID | OCI Console → your profile icon (top right) → **My profile** → copy the OCID. |
| Tenancy OCID | OCI Console → your profile icon → **Tenancy** → copy the OCID. |
| Region | The region your administrator uses, for example `eu-frankfurt-1`. |
| Generate a new API signing key pair? | `Y` |

At the end the command prints the path of a **public key** file
(`…_public.pem`). Upload it: OCI Console → your profile icon → **My profile** →
**API keys** (in some tenancies under **Tokens and keys**) → **Add API key** →
**Paste a public key** → paste the content of that file → **Add**.

Check the connection. It prints your tenancy's **namespace**; write it down,
you need it in step 5:

```powershell
oci os ns get
```

Expected: a small JSON document with your namespace in `data`, and no
warnings.

*If the namespace is followed by `Get-Acl` errors:* the request worked, but
the key-file check did not. Repeat the last part of step 3 and use a new
PowerShell 7 window. Do not change file permissions because of these errors.

*If it fails with `NotAuthenticated`:* the public key was not uploaded to the
same user, or the profile has a wrong user or tenancy OCID. Correct the
profile, or run `oci setup config` again.

## 5. Configure the tool (`.env`)

The tool reads your settings from one file, `.env`, in the tool home. Create
it from the example and open it:

```powershell
Copy-Item .env.example .env
```

```powershell
notepad .env
```

Replace the four values:

| Setting | Value |
| --- | --- |
| `OCI_REGION` | The region, for example `eu-frankfurt-1`. |
| `OCI_COMPARTMENT_NAME` | The compartment name given by your administrator. |
| `OCIR_TENANCY_NAMESPACE` | The namespace printed by `oci os ns get` in step 4. |
| `OCIR_USERNAME` | Your container registry user: `<namespace>/<your-username>`, or `<namespace>/<identity-domain>/<your-username>` if your user is not in the `Default` identity domain. Your username is usually your email address. |

**Optional, for agents that call an LLM with an API key:** create a Generative
AI API key in the OCI Console (Generative AI → **API keys** → **Create API
key**, in the same region as the model), copy the key when it is shown (it
appears only once), and add a line at the end of `.env`:

```dotenv
GENAI_API_KEY=<your-key>
```

From now on `.env` contains a secret: never share it, never commit it, and
never paste it into the chat. The tool reads it for you.

## 6. Install the skills

This makes the skills available to Codex in every project, as links to
the tool home:

```powershell
./scripts/install_skills.ps1
```

Expected: one `created:` line per skill (`unchanged:` if they were already
installed). Then **start a new Codex session** (close and reopen Codex, or
reload VS Code), so that Codex discovers them. To check, type `$` in Codex: the
list must include `oci-agent-new`, `oci-agent-build`, `oci-agent-push`,
`oci-agent-deploy`, `oci-agent-verify-deployment`, and `oci-agent-ui`.

## 7. Check the setup

Run the setup check from the tool home, with the environment active:

```powershell
./scripts/check_setup.ps1
```

Expected: every line says `PASS`, and the last line is
`Result: all 4 checks passed.`

## 8. Fix what fails

| `FAIL` line | What to do |
| --- | --- |
| Tenancy file (.env) | A setting is missing or still contains `replace-with-…`: complete `.env` (step 5). |
| Docker build environment | Start Docker Desktop (Linux containers) or the Podman machine (step 1). |
| OCI CLI and region | Repeat step 4. If it says the region was not found, check `OCI_REGION` in `.env` and that your tenancy is subscribed to that region. |
| Skills installed | Repeat step 6, then start a new Codex session. |
| A message about Python and PyYAML | The environment is not active: run `conda activate codex-4-oci-enterprise-ai-deployment`. |

Run `./scripts/check_setup.ps1` again until every line says `PASS`.

## 9. Test the whole chain with the example agent

Before writing your own agent, release the example agent that comes with the
project. It calls no LLM, so if it works, your workstation, OCI access, and
policies are ready.

You need an **auth token** for the container registry (OCIR): OCI Console →
your profile icon → **My profile** → **Auth tokens** (in some tenancies under
**Tokens and keys**) → **Generate token** → copy it (it appears only once).
Keep it at hand; you type it once, when Docker or Podman asks for a password.

Open the **tool home** in Codex (a new session) and ask:

```text
Release version 0.1.0 of the agent demos/hello_world/agent.yaml on OCI
Hosted Applications.
```

Codex builds and tests the image, then asks for your approval before each
change in OCI: creating the registry repository, pushing the image, and
deploying. When the registry asks you to log in, Codex shows the
`docker login` or `podman login` command: run it yourself and type the **auth
token** at the password prompt, never in the chat.

Expected: Codex reports that the deployment is active and that `/health` and
`/ready` answer. The first deployment takes a few minutes.

*If you share the compartment with colleagues,* one of them may already have
an application named `hello-world`. Ask Codex to use another application name
before you approve the deploy.

When you no longer need it, delete the `hello-world` Hosted Application from
the OCI Console.

## 10. Create your first agent

Create an empty folder for the agent, **outside the tool home**:

```powershell
New-Item -ItemType Directory -Path "$HOME\Projects\my-first-agent"
```

```powershell
git -C "$HOME\Projects\my-first-agent" init
```

Open that folder in a **new** Codex session and describe the agent: who it is
for, what it does, and what the customer expects. For example:

```text
Create a new OCI agent. It is for the support team of an online shop, which
receives many customer emails. The agent receives an email with POST /classify
and returns its category (complaint, question, order) and a short summary. The
team expects to route emails faster and to see the category of each one.
```

The `oci-agent-new` skill writes a specification, `agent-spec.md`, and stops.
Read it, change what you want (by hand or by asking Codex), then approve it,
for example with "ok, go ahead". Codex then creates the agent's code and its
`agent.yaml`.

Then release it:

```text
Release version 0.1.0 of this agent on OCI Hosted Applications.
```

For new versions, rollback, and checks, continue with the
[Quickstart](quickstart.md).

## 11. Show the agent with a demo page (optional)

A local web page lets you show the agent to its users or to management, in
business language, without JSON. It needs **Node.js 20.9 or later**: install
the LTS version from the [Node.js website](https://nodejs.org/), open a new
PowerShell 7 window, and check:

```powershell
node --version
```

In the agent's Codex session, ask:

```text
Create a demo UI for this agent, for its users.
```

The `oci-agent-ui` skill writes a short page specification, `ui/ui-spec.md`,
and stops: check that the texts speak the language of the users. After your
approval it creates the `ui` folder, asks whether the page talks to the local
container or to the deployed agent, and builds it. Then start the page:

```powershell
Set-Location ui
```

```powershell
npm run dev
```

Open <http://127.0.0.1:3000>.

## Advanced settings

You do not need these for a standard setup.

| Variable | Purpose | Default |
| --- | --- | --- |
| `OCI_CLI_PROFILE` | OCI CLI profile to use, if not `DEFAULT`; read by the OCI CLI itself. Set it in the window that starts Codex, for example `$env:OCI_CLI_PROFILE = 'MY_PROFILE'`. | `DEFAULT` |
| `OCI_AGENT_ENV_FILE` | Path of the tool's settings file. | `.env` in the tool home. |
| `OCI_AGENT_PYTHON` | Python interpreter used by the scripts; it must provide PyYAML. | `python` |
| `OCI_AGENT_ALLOWED_ROOTS` | Absolute folders that may contain manifests and build files. | The Git repository that contains the manifest, or the manifest's folder outside Git. |

* `./scripts/install_skills.ps1` accepts `-DryRun` (preview), `-Uninstall`
  (remove only this checkout's links), and `-Target DIR`.
* `./scripts/check_setup.ps1` accepts `-Manifest ./agent.yaml`, run from an
  agent folder, to also check its manifest, compartment, and OCIR repository,
  and `-SkillsTarget DIR` for skills installed elsewhere.
* `./scripts/install_oci_powershell_hook.ps1` refuses to replace a hook that
  differs from the project's; review it, then rerun with `-Update`. To remove
  the hooks, delete `codex4eai_oci_module_path.ps1` from the environment's
  `etc\conda\activate.d` and `etc\conda\deactivate.d` folders; to restore the
  Windows PowerShell profile, use the backup copy printed by the script.
* Opening the tool home itself in Codex also works without installing the
  skills: its `.agents/skills` link makes them available inside it.
* All PowerShell scripts and their options:
  [native PowerShell 7](../notes/windows-powershell-native.md).
