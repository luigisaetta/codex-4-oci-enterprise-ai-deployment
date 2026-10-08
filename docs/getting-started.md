# Getting started

This page takes you from an empty workstation to your first agent running on
OCI Enterprise AI Hosted Applications. Follow the steps in order; each one says
what it does, the command to copy, what you should see, and what to do if it
does not work. You do not need to know Python: Codex writes the code, and the
skills run the tools for you.

Start with the basic-tool checks for your operating system in step 1.
The later Bash examples use macOS/Linux Terminal; native Windows users use
PowerShell 7.4+ and the [Windows command equivalents](#windows).

## Before you start: what you need and who provides it

| Who | What | When |
| --- | --- | --- |
| **Your tenancy administrator** | A compartment for your agents, and the IAM policies listed in [For the administrator](#for-the-administrator). | Once, before step 9 |
| **You** | An OCI user account in that tenancy, able to create an API signing key and an auth token for yourself. | Before step 4 |
| **You** | A workstation where you can install software: macOS, Linux, or Windows. | Now |

Ask the administrator for:

* the **name of the compartment** to use;
* the **identity domain** of your user, if it is not `Default`;
* whether your agents will call an LLM with an **API key** (simplest) or with
  **Resource Principal** (no key; needs a Generative AI project).

## 1. Install the basic tools

Reuse tools you already have if the checks below succeed. Install missing
tools through their official installers or your organisation's approved
software route, then reopen your terminal so it finds them.

| Tool | What it is for | Installation guidance |
| --- | --- | --- |
| **Git** | Downloads this project. | [Git for your operating system](https://git-scm.com/install/). |
| **Anaconda** or **Miniconda** | Provides Conda to manage the project's Python environment. Create that environment in step 3. | [Conda installation](https://docs.conda.io/projects/conda/en/stable/user-guide/install/index.html). |
| **One container engine** | Builds and tests the agent image. macOS/Linux: Docker Desktop or Rancher Desktop with the **Moby (`dockerd`)** engine. Native Windows: Docker Desktop or Podman. | [Docker Desktop](https://docs.docker.com/desktop/), [Rancher Desktop](https://rancherdesktop.io/), or [Podman Desktop on Windows](https://podman-desktop.io/docs/installation/windows-install). |
| **Codex** | Runs the skills. Use Codex in the desktop app, the Codex CLI, or the Codex extension for VS Code; install and sign in. | [Official OpenAI quickstart](https://learn.chatgpt.com/docs/quickstart). |
| **PowerShell 7.4+** (native Windows) | Runs the project's Windows scripts. Windows PowerShell 5.1 is not supported. | [Install PowerShell on Windows](https://learn.microsoft.com/en-us/powershell/scripting/install/install-powershell-on-windows). |

On native Windows, Podman runs Linux containers in a local virtual machine.
Its installer documents the WSL2 or Hyper-V prerequisites, which can require
administrator rights and a restart. You still run the project commands in
PowerShell. See [native PowerShell guidance](../notes/windows-powershell-native.md).
If you choose to work inside WSL2 instead, follow the
[WSL2 guide](../notes/windows-rancher-desktop-wsl2.md) and use Bash throughout.

On a Mac with Apple Silicon (M1, M2, …), the container engine must be able to
build `linux/amd64` images. Docker Desktop does it by default. In Rancher
Desktop, open **Preferences → Virtual Machine → Emulation** and enable
**Rosetta** with the **VZ** virtual machine type, then restart Rancher Desktop.

### macOS and Linux: Terminal

Run these checks in your own Terminal window:

```bash
git --version
conda --version
docker version
docker buildx version
```

Expected: Git and Conda print versions, `docker version` prints both **Client**
and **Server** information, and `docker buildx version` prints a Buildx version.
On a Linux workstation with Docker Engine already installed, reuse it if these
checks succeed.

### Native Windows: PowerShell

Open **PowerShell 7**, not **Windows PowerShell**, and run:

```powershell
$PSVersionTable.PSVersion
git --version
conda --version
```

Expected: PowerShell is 7.4 or later, and Git and Conda print versions. A
successful check in Codex's execution environment does not establish that the
same tools are available in your own PowerShell window.

Then check **the container engine you chose**. With Docker Desktop, use Linux
containers and run:

```powershell
docker version
docker buildx version
```

Expected: both **Client** and **Server** information, plus a Buildx version.

With Podman, run:

```powershell
podman --version
podman info
```

Expected: a Podman version and server information without a connection error.
Podman does not require Docker or Buildx for the PowerShell scripts.

Finally, open Codex, sign in, and confirm that you can send a message.
You install this project's skills in step 6.

### If a check fails

| Result | What to do |
| --- | --- |
| A command is not found | Install the missing tool, or reopen the terminal after installation. With Conda on Windows, use the installed Anaconda PowerShell Prompt or follow the Conda instructions to initialise your PowerShell session. |
| PowerShell reports version 5.1 or a version below 7.4 | Install PowerShell 7.4+ and open it from the Start menu. |
| Docker prints Client information but cannot connect to the Server | Start Docker Desktop or Rancher Desktop and wait for its engine to be ready; check again. |
| Podman prints a version but `podman info` cannot connect | Check and start the existing machine using the commands below, or start it in Podman Desktop. If there is no machine, complete Podman Desktop's setup; do not initialise another machine when one already exists. |
| Codex cannot sign in | Follow the sign-in guidance in the official OpenAI quickstart. |

For Podman on Windows, list the existing machines:

```powershell
podman machine list
```

If `podman-machine-default` exists and is stopped, start it and check the
connection again. This starts the existing local Linux VM:

```powershell
podman machine start podman-machine-default
podman info
```

If your listed machine has a different name, substitute that name in the start
command. If it is already running, run only `podman info`. Expected: the start
command reports success and `podman info` prints server information without a
connection error.

Step 1 is complete when your own terminal finds Git and Conda, your selected
container engine is reachable, Codex is signed in, and native Windows users
have PowerShell 7.4+. Building an image and proving `linux/amd64` compatibility
come later.

## 2. Download this project

Choose a stable local folder for the project. This checkout is the
**tool home**: the skills will point to it. If you already cloned this
repository, reuse that checkout and skip the clone commands below.

### macOS and Linux: Terminal

Create a parent folder if needed, clone the project, and enter it:

```bash
mkdir -p ~/Progetti
cd ~/Progetti
git clone https://github.com/luigisaetta/codex-4-oci-enterprise-ai-deployment.git
cd codex-4-oci-enterprise-ai-deployment
```

### Native Windows: PowerShell

This example uses a `Projects` folder in your Windows user folder. You can
choose another stable local folder instead:

```powershell
New-Item -ItemType Directory -Path "$HOME\Projects" -Force
Set-Location "$HOME\Projects"
git clone https://github.com/luigisaetta/codex-4-oci-enterprise-ai-deployment.git
Set-Location .\codex-4-oci-enterprise-ai-deployment
```

### Check the checkout

From the tool home, run this in either shell:

```text
git status
```

Expected: Git recognises the working tree, and the folder contains `README.md`,
`requirements-dev.txt`, `scripts`, and `skills`. A fresh clone has a clean
working tree; an existing checkout may have local changes that should be
preserved.

If Git reports that the destination already exists and is not empty, check
whether it is the checkout you want to reuse. Do not delete it to retry the
clone. If `git status` reports that this is not a Git repository, enter the
cloned project folder before trying again.

**Do not move or rename the tool home** after installing the skills in step 6.
To update it later, run `git pull` inside it after saving your local work.

## 3. Create the Python environment and install the libraries

Use these Conda and Python commands in macOS/Linux Terminal or native Windows
PowerShell 7.4+. If the named environment already exists, reuse it and skip
creation. Otherwise, create it once:

```bash
conda create -n codex-4-oci-enterprise-ai-deployment python=3.11 -y
```

Activate it. Do this **in every new terminal** before working with the
project:

```bash
conda activate codex-4-oci-enterprise-ai-deployment
```

Before installing anything, confirm which Python is active:

```text
python --version
python -c "import sys; print(sys.executable)"
```

Expected: Python 3.11 or later, with the executable inside the named Conda
environment. If it still points to a global Python installation, activation
has not succeeded; fix that before installing the libraries.

**On Windows, if activation fails or leaves Python unchanged**, check how
PowerShell resolves Conda:

```powershell
Get-Command conda | Select-Object CommandType, Source
```

An external `conda.bat` application cannot activate an environment in the
parent PowerShell session. Configure Conda's PowerShell integration:

To preview the affected startup profiles first, run
`conda init powershell --dry-run`. This reports proposed changes without
applying them. Then apply the initialisation:

```powershell
conda init powershell
```

This updates your user shell profile. Close the terminal and open a new
PowerShell 7 session that loads its profile. Repeat the activation and Python
checks above. Conda should now resolve to a shell alias or function. If it
still resolves to `conda.bat`, or opening the terminal reports a profile error,
resolve that shell-integration problem before continuing.

**Alternative: run Python in the environment without activating your shell.**
This is useful when you want to reuse an existing setup without changing its
shell profile:

```text
conda run -n codex-4-oci-enterprise-ai-deployment python --version
conda run -n codex-4-oci-enterprise-ai-deployment python -c "import sys; print(sys.executable)"
```

The executable must be inside the named environment. When using this approach,
prefix subsequent Python commands with
`conda run -n codex-4-oci-enterprise-ai-deployment`; an unprefixed `python`
command still uses your terminal's current interpreter. For lifecycle scripts,
also configure the interpreter and command environment as described under
[Advanced settings](#advanced-settings).

If reusing an existing environment, ask Codex to compare its installed package
versions with `requirements-dev.txt` and the requirements files it includes.
Also check installed-package consistency:

```text
conda run -n codex-4-oci-enterprise-ai-deployment python -m pip check
```

Expected: `No broken requirements found.` This checks consistency, not the
presence of every project dependency. If all project packages are present,
their versions meet the requirements, and this check succeeds, skip dependency
installation. Review any required changes before updating a shared environment
used by other projects.

For a new environment, or when required packages are missing or incompatible,
install the libraries from the tool home. This also installs the OCI command
line (OCI CLI). With the environment activated:

```bash
python -m pip install -r requirements-dev.txt
```

Expected: the command ends without errors. Check the OCI CLI:

```bash
oci --version
```

### Windows: prepare OCI CLI for PowerShell 7

With the named Conda environment activated in PowerShell 7.4+, install the
project's OCI CLI activation hooks once from the repository root:

```powershell
./scripts/install_oci_powershell_hook.ps1
```

This changes only the named Conda environment, which may also be used by
other projects. On activation, the hook selects Windows PowerShell-compatible
module paths in that shell so the subprocess used by OCI CLI can load its own
modules. On deactivation, the previous path is restored. The hooks do not
change OCI credentials or file permissions. The installer also guards the
Conda initialization block in the current user's Windows PowerShell 5.1
profile, when present. It saves a backup first. Other profile content remains
in place; the guard applies only while this Conda environment is active.
Open a new PowerShell 7 window, activate the environment, and use `oci`
normally. The installer refuses to replace a different existing hook unless
you explicitly pass `-Update` after reviewing it.
Conda's documented
[activation scripts](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html)
run only when the environment is activated; `conda run` does not establish
this shell setup.

Without shell activation, use the same named environment for both commands:

```text
conda run -n codex-4-oci-enterprise-ai-deployment python -m pip install -r requirements-dev.txt
conda run -n codex-4-oci-enterprise-ai-deployment oci --version
```

*On macOS/Linux, if activation fails:* initialise your actual shell with
`conda init zsh` or `conda init bash`, close the terminal, open a new one, and
try again. See [Conda shell initialisation](https://docs.conda.io/projects/conda/en/stable/commands/init.html).

## 4. Connect the OCI CLI to your tenancy

The skills use the OCI CLI to talk to OCI. It needs an API-key authentication
profile on your workstation. Use an OCI CLI version that meets the project's
requirements checked in step 3. If your usual `oci` command already selects
that version, use it directly; a Conda prefix is not required for every OCI
command. Otherwise, select the appropriate CLI for this project session.

### Reuse an existing profile

If another project already uses OCI CLI successfully, reuse its configuration
and signing key. The default configuration file is `~/.oci/config` on
macOS/Linux or `$HOME\.oci\config` on Windows. Confirm the intended profile,
tenancy, and region before running the connection check below. Skip first-time
setup when the existing profile works; no new signing key is needed.

OCI CLI normally uses `DEFAULT`, so an explicit `--profile DEFAULT` is
unnecessary. Check for any existing `OCI_CLI_PROFILE` session override. For
another profile, pass `--profile PROFILE_NAME` and use the same profile for
subsequent commands. For lifecycle scripts, select it with `OCI_CLI_PROFILE`
as explained in [native PowerShell guidance](../notes/windows-powershell-native.md).

### First-time setup only

If you do not have a usable profile yet, create one with the guided setup.
With the project environment activated, run this in either shell:

```bash
oci setup config
```

Without shell activation, run:

```powershell
conda run -n codex-4-oci-enterprise-ai-deployment oci setup config
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

### Check the connection

This read-only OCI call prints your tenancy's **namespace**. Keep that value
for step 5. With the project environment activated, run in either shell:

```bash
oci os ns get
```

Expected: JSON containing a `data` string with your namespace. This confirms
authentication and connectivity for this call; deployment permissions are
checked later.

On Windows, a namespace response followed by `Get-Acl` module errors means
the OCI request succeeded but its local permission check failed. Follow the
[PowerShell 7 setup](#windows-prepare-oci-cli-for-powershell-7) above before
changing any file permissions. The embedded error text is not a list of users
with access to the files. This is a known
[OCI CLI issue](https://github.com/oracle/oci-cli/issues/655) caused by
PowerShell module-path inheritance described by
[Microsoft](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_psmodulepath?view=powershell-7.6).
If a warning remains after setup, inspect the actual file ACL and the
current-user Windows PowerShell profile before deciding whether permissions
need repair. The installer recognizes a standard Conda initialization block;
customized profiles may require manual review.

*If it fails with `NotAuthenticated`:* check that the profile's signing key
matches the public key uploaded for its OCI user, that its user and tenancy
OCIDs are correct, and that the private key file is present. Correct the
existing profile before deciding to generate another key.

## 5. Configure the tool (`.env`)

The tool reads your settings from one file, `.env`, in the tool home. Create
it from the example:

```bash
cp .env.example .env
```

In PowerShell 7, use `Copy-Item .env.example .env`. If you already have OCI
settings in another project, reuse their values for the four settings below
instead of creating new OCI resources or credentials. Check the target
compartment and OCIR username before continuing.

Open `.env` in a text editor and replace the four values:

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

```bash
scripts/install_skills.sh
```

On Windows in PowerShell 7.4+, run `./scripts/install_skills.ps1` from the
repository root. Existing links to this checkout are reported as `unchanged`;
they do not need reinstalling.

Expected: one `created:` line per skill. Then **start a new Codex session**
(close and reopen the Codex CLI, or reload VS Code), so that Codex discovers
them. To check, type `$` in Codex: the list must include `oci-agent-new`,
`oci-agent-build`, `oci-agent-push`, `oci-agent-deploy`,
`oci-agent-verify-deployment`, and `oci-agent-ui`.

## 7. Check the setup

Run the setup check from the tool home, with the environment active:

```bash
scripts/check_setup.sh
```

On Windows in PowerShell 7.4+, run `./scripts/check_setup.ps1` from the
repository root instead.

Expected: every line says `PASS`, and the last line is
`Result: all 4 checks passed.`

## 8. Fix what fails

| `FAIL` line | What to do |
| --- | --- |
| Tenancy file (.env) | A setting is missing or still contains `replace-with-…`: complete `.env` (step 5). |
| Docker build environment | Start Docker Desktop or Rancher Desktop. If it mentions `linux/amd64`, enable the emulation (step 1). With Rancher Desktop, check that the engine is **Moby (`dockerd`)**. |
| OCI CLI and region | Repeat step 4. If it says the region was not found, check `OCI_REGION` in `.env` and that your tenancy is subscribed to that region. |
| Skills installed | Repeat step 6, then start a new Codex session. |
| A message about Python and PyYAML | The environment is not active: run `conda activate codex-4-oci-enterprise-ai-deployment`. |

Run `scripts/check_setup.sh` again until every line says `PASS`.

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
deploying. When the container engine needs a registry login, Codex shows the
`docker login` or `podman login` command: run it yourself and type the **auth token** at the password prompt,
never in the chat.

Expected: Codex reports that the deployment is active and that `/health` and
`/ready` answer. The first deployment takes a few minutes.

*If you share the compartment with colleagues,* one of them may already have
an application named `hello-world`. Ask Codex to use another application name
before you approve the deploy.

When you no longer need it, delete the `hello-world` Hosted Application from
the OCI Console.

## 10. Create your first agent

Create an empty folder for the agent and open it in a **new** Codex session:

```bash
mkdir ~/Progetti/my-first-agent
```

```bash
git -C ~/Progetti/my-first-agent init
```

On native Windows, open PowerShell 7 and create a separate agent folder outside
this tool home. It can be beside the tool home under the same parent project
folder. This single line creates the folder and initializes Git locally;
it does not publish anything to GitHub:

```powershell
$agentDir = Join-Path $HOME 'Projects\my-first-agent'; New-Item -ItemType Directory -Path $agentDir -ErrorAction Stop | Out-Null; git -C $agentDir init
```

If you already have a dedicated empty folder, use its path with
`git -C <agent-folder> init` instead. Open the agent folder, rather than this
tool home, as the workspace in a new Codex session.

In Codex, describe the agent: who it is for, what it does, and what the
customer expects. For example:

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
business language, without JSON. It needs **Node.js 20.9 or later**. The
simplest way to get it, with the environment active:

```bash
conda install -c conda-forge nodejs -y
```

```bash
node --version
```

(On Windows, install the LTS version from the Node.js website instead.)

In the agent's Codex session, ask:

```text
Create a demo UI for this agent, for its users.
```

The `oci-agent-ui` skill writes a short page specification, `ui/ui-spec.md`,
and stops: check that the texts speak the language of the users. After your
approval it creates the `ui` folder, asks whether the page talks to the local
container or to the deployed agent, and builds it. Then start the page:

```bash
cd ui
```

```bash
npm run dev
```

Open <http://127.0.0.1:3000>.

## For the administrator

Do this once per tenancy and compartment. Replace the placeholders; the
statements are explained in [IAM policies](iam-policies.md).

1. **Compartment**: Identity & Security → Compartments → **Create compartment**.
2. **Operator group**: put the users of the skills in a group, and add a policy
   attached to the tenancy (root compartment):

   ```text
   allow group <operator-group> to inspect compartments in tenancy
   allow group <operator-group> to manage repos in compartment <compartment-name>
   allow group <operator-group> to manage generative-ai-hosted-application in compartment <compartment-name>
   allow group <operator-group> to manage generativeaihosteddeployment in compartment <compartment-name>
   allow group <operator-group> to read generative-ai-work-request in compartment <compartment-name>
   ```

3. **Runtime dynamic group**, so that Hosted Applications can pull their image:
   create a dynamic group with this matching rule, and allow it to read the
   registry:

   ```text
   any {resource.type='generativeaihostedapplication', resource.type='generativeaihostedapplicationiam', resource.type='generativeaihosteddeployment'}
   ```

   ```text
   allow dynamic-group <runtime-dynamic-group> to read repos in compartment <compartment-name>
   ```

4. **Agents that call an LLM**, depending on the choice:
   * with an **API key**:

     ```text
     allow any-user to use generative-ai-family in compartment <compartment-name> where ALL {request.principal.type='generativeaiapikey'}
     ```

   * with **Resource Principal**: create a Generative AI project in the
     compartment (in the region of the model), give its OCID to the users, and
     add:

     ```text
     allow dynamic-group <runtime-dynamic-group> to use generative-ai-family in compartment <compartment-name>
     allow dynamic-group <runtime-dynamic-group> to use generative-ai-project in compartment <compartment-name>
     ```

If a group or dynamic group is in an identity domain other than `Default`,
write its name as `'<domain-name>'/'<group-name>'`.

## Advanced settings

You do not need these for a standard setup.

| Variable | Purpose | Default |
| --- | --- | --- |
| `OCI_AGENT_ENV_FILE` | Path of the tool's settings file. | `.env` in the tool home. |
| `OCI_AGENT_PYTHON` | Python interpreter used by the scripts; it must provide PyYAML. | `python` |
| `OCI_AGENT_ALLOWED_ROOTS` | Absolute folders that may contain manifests and build files. | The Git repository that contains the manifest, or the manifest's folder outside Git. |

* `scripts/install_skills.sh` accepts `--dry-run` (preview), `--uninstall`
  (remove only this checkout's links), and `--target DIR`, for example
  `--target ~/.claude/skills` for Claude Code.
* `scripts/check_setup.sh` accepts `--manifest ./agent.yaml`, run from an
  agent folder, to also check its manifest, compartment, and OCIR repository,
  and `--skills-target DIR` for skills installed elsewhere.
* Opening the tool home itself in Codex also works without installing the
  skills: its `.agents/skills` link makes them available inside it.
* Builds on a remote Linux machine:
  [Linux build machine over SSH](../notes/linux-build-machine-over-ssh.md).

## Windows

Use **PowerShell 7.4 or later** (`pwsh`) with Docker Desktop or Podman, or
work inside **WSL2** with Rancher Desktop and use the commands above
unchanged. The details are in
[native PowerShell 7](../notes/windows-powershell-native.md) and
[Rancher Desktop with WSL2](../notes/windows-rancher-desktop-wsl2.md).

In PowerShell, the commands that differ are:

| macOS and Linux | Windows PowerShell 7.4+ |
| --- | --- |
| `cp .env.example .env` | `Copy-Item .env.example .env` |
| `scripts/install_skills.sh` | `.\scripts\install_skills.ps1` |
| `scripts/check_setup.sh` | `.\scripts\check_setup.ps1` |
| `mkdir ~/Progetti/my-first-agent` | `New-Item -ItemType Directory "$HOME\Projects\my-first-agent"` |
| `git -C ~/Progetti/my-first-agent init` | `git -C "$HOME\Projects\my-first-agent" init` |
