# Getting started on macOS and Linux

This guide takes you from an empty workstation to your first agent running on
OCI Enterprise AI Hosted Applications. Follow the steps in order; each one says
what it does, the command to copy, what you should see, and what to do if it
does not work. You do not need to know Python: Codex writes the code, and the
skills run the tools for you.

All commands run in **Terminal**. On Windows inside WSL2, use this guide too,
in the WSL2 shell. For Windows with PowerShell, use
[Getting started on Windows](getting-started-windows.md).

## Before you start: what you need and who provides it

| Who | What | When |
| --- | --- | --- |
| **Your tenancy administrator** | A compartment for your agents, and the IAM policies. Send them [Setup for the administrator](iam-policies.md#setup-for-the-administrator). | Once, before step 9 |
| **You** | An OCI user account in that tenancy, able to create an API signing key and an auth token for yourself. | Before step 4 |
| **You** | A workstation where you can install software. | Now |

Ask the administrator for:

* the **name of the compartment** to use;
* the **identity domain** of your user, if it is not `Default`;
* whether your agents will call an LLM with an **API key** (simplest) or with
  **Resource Principal** (no key; needs a Generative AI project).

## 1. Install the basic tools

You need four tools. If a tool is already installed and its check below
succeeds, keep it. Otherwise install it with its official installer, or with
your organization's approved software catalog.

| Tool | What it is for | Installer |
| --- | --- | --- |
| **Git** | Downloads this project. | [Git](https://git-scm.com/install/) |
| **Anaconda** or **Miniconda** | Creates a dedicated Python environment, so nothing else on your machine changes. | [Conda](https://docs.conda.io/projects/conda/en/stable/user-guide/install/index.html) |
| **Docker Desktop** | Builds and tests the agent's container image. Where Docker Desktop is not acceptable, use **Rancher Desktop** with the **Moby (`dockerd`)** engine. On Linux, an existing Docker Engine with Buildx also works. | [Docker Desktop](https://docs.docker.com/desktop/), [Rancher Desktop](https://rancherdesktop.io/) |
| **Codex** | The assistant that runs the skills: the desktop app, the Codex CLI, or the Codex extension for VS Code. Install it and sign in. | [Codex quickstart](https://learn.chatgpt.com/docs/quickstart) |

On a Mac with Apple Silicon (M1, M2, …), the container engine must be able to
build `linux/amd64` images. Docker Desktop does it by default. In Rancher
Desktop, open **Preferences → Virtual Machine → Emulation** and enable
**Rosetta** with the **VZ** virtual machine type, then restart Rancher Desktop.

Close and reopen Terminal after installing, then check that the tools answer:

```bash
git --version
```

```bash
conda --version
```

```bash
docker version
```

```bash
docker buildx version
```

Expected: Git and Conda print a version; `docker version` prints both
**Client** and **Server** information; `docker buildx version` prints a
version. Finally, open Codex, sign in, and send a test message.

| If | What to do |
| --- | --- |
| A command is not found | Install the tool, then open a new Terminal window. |
| `docker version` shows Client but cannot connect to the Server | Start Docker Desktop (or Rancher Desktop) and wait until it says it is running. |
| Codex cannot sign in | Follow the sign-in steps of the Codex quickstart. |

## 2. Download this project

Choose a stable folder, for example `~/Progetti`, and clone the project there:

```bash
mkdir -p ~/Progetti
```

```bash
cd ~/Progetti
```

```bash
git clone https://github.com/luigisaetta/codex-4-oci-enterprise-ai-deployment.git
```

```bash
cd codex-4-oci-enterprise-ai-deployment
```

This folder is the **tool home**: the skills point to it. **Do not move or
rename it** after step 6. To update it later, run `git pull` inside it. If you
have already cloned the project, use that folder and skip the clone.

## 3. Create the Python environment and install the libraries

Create a dedicated environment (once; skip it if it already exists):

```bash
conda create -n codex-4-oci-enterprise-ai-deployment python=3.11 -y
```

Activate it. Do this **in every new terminal** before working with the
project:

```bash
conda activate codex-4-oci-enterprise-ai-deployment
```

Check that the environment's Python is the active one:

```bash
python -c "import sys; print(sys.version.split()[0], sys.executable)"
```

Expected: version 3.11 or later, and a path that contains
`codex-4-oci-enterprise-ai-deployment`.

*If `conda activate` fails, or the path is not in the environment:* run
`conda init zsh` (macOS) or `conda init bash` (most Linux systems), close
Terminal, open a new one, and try again.

Install the libraries, from the tool home. This also installs the OCI command
line (OCI CLI):

```bash
python -m pip install -r requirements-dev.txt
```

Expected: the command ends without errors. Check the OCI CLI:

```bash
oci --version
```

## 4. Connect the OCI CLI to your tenancy

The skills use the OCI CLI to talk to OCI. It needs a profile on your
workstation.

*If the OCI CLI already works on this workstation* (for example for another
project), keep its profile in `~/.oci/config` and go to the connection check
below. The skills use the `DEFAULT` profile; for another one, see
[Advanced settings](#advanced-settings).

Otherwise, create a profile with a guided command:

```bash
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

```bash
oci os ns get
```

Expected: a small JSON document with your namespace in `data`.

*If it fails with `NotAuthenticated`:* the public key was not uploaded to the
same user, or the profile has a wrong user or tenancy OCID. Correct the
profile, or run `oci setup config` again.

## 5. Configure the tool (`.env`)

The tool reads your settings from one file, `.env`, in the tool home. Create
it from the example:

```bash
cp .env.example .env
```

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

Expected: one `created:` line per skill (`unchanged:` if they were already
installed). Then **start a new Codex session** (close and reopen Codex, or
reload VS Code), so that Codex discovers them. To check, type `$` in Codex: the
list must include `oci-agent-new`, `oci-agent-build`, `oci-agent-push`,
`oci-agent-deploy`, `oci-agent-verify-deployment`, and `oci-agent-ui`.

## 7. Check the setup

Run the setup check from the tool home, with the environment active:

```bash
scripts/check_setup.sh
```

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
Keep it at hand; you type it once, when Docker asks for a password.

Open the **tool home** in Codex (a new session) and ask:

```text
Release version 0.1.0 of the agent demos/hello_world/agent.yaml on OCI
Hosted Applications.
```

Codex builds and tests the image, then asks for your approval before each
change in OCI: creating the registry repository, pushing the image, and
deploying. When Docker asks you to log in, Codex shows the `docker login`
command: run it yourself and type the **auth token** at the password prompt,
never in the chat.

Expected: Codex reports that the deployment is active and that `/health` and
`/ready` answer. The first deployment takes a few minutes.

*If you share the compartment with colleagues,* one of them may already have
an application named `hello-world`. Ask Codex to use another application name
before you approve the deploy.

When you no longer need it, delete the `hello-world` Hosted Application from
the OCI Console.

## 10. Create your first agent

Create an empty folder for the agent, **outside the tool home**:

```bash
mkdir ~/Progetti/my-first-agent
```

```bash
git -C ~/Progetti/my-first-agent init
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
business language, without JSON. It needs **Node.js 20.9 or later**. The
simplest way to get it, with the environment active:

```bash
conda install -c conda-forge nodejs -y
```

```bash
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

```bash
cd ui
```

```bash
npm run dev
```

Open <http://127.0.0.1:3000>.

## Advanced settings

You do not need these for a standard setup.

| Variable | Purpose | Default |
| --- | --- | --- |
| `OCI_CLI_PROFILE` | OCI CLI profile to use, if not `DEFAULT`; read by the OCI CLI itself. Export it in the shell that starts Codex. | `DEFAULT` |
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
* Windows with WSL2 and Rancher Desktop:
  [Rancher Desktop with WSL2](../notes/windows-rancher-desktop-wsl2.md).
* Builds on a remote Linux machine:
  [Linux build machine over SSH](../notes/linux-build-machine-over-ssh.md).
