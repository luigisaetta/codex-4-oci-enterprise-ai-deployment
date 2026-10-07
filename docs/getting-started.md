# Getting started

This page takes you from an empty workstation to your first agent running on
OCI Enterprise AI Hosted Applications. Follow the steps in order; each one says
what it does, the command to copy, what you should see, and what to do if it
does not work. You do not need to know Python: Codex writes the code, and the
skills run the tools for you.

The commands are for macOS and Linux (Terminal). On Windows, see
[Windows](#windows) at the end.

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

You need four tools. Install each one with its official installer.

| Tool | What it is for |
| --- | --- |
| **Git** | Downloads this project. |
| **Anaconda** (or Miniconda) | Creates a dedicated Python environment, so nothing else on your machine changes. |
| **Docker Desktop** | Builds and tests the agent's container image. Where Docker Desktop is not acceptable, use **Rancher Desktop** instead, with the **Moby (`dockerd`)** engine. Other container engines are possible, but you must verify them yourself. |
| **Codex** | The assistant that runs the skills: the Codex CLI, or the Codex extension for VS Code. Install it and sign in, following the official Codex documentation. |

On a Mac with Apple Silicon (M1, M2, …), the container engine must be able to
build `linux/amd64` images. Docker Desktop does it by default. In Rancher
Desktop, open **Preferences → Virtual Machine → Emulation** and enable
**Rosetta** with the **VZ** virtual machine type, then restart Rancher Desktop.

Check that the tools answer (each command prints a version):

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

*If `docker version` reports that it cannot connect:* start Docker Desktop (or
Rancher Desktop) and wait until it says it is running.

## 2. Download this project

Choose a stable folder, for example `~/Progetti`, and clone the project there:

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
rename it** after step 6. To update it later, run `git pull` inside it.

## 3. Create the Python environment and install the libraries

Create a dedicated environment (once):

```bash
conda create -n codex-4-oci-enterprise-ai-deployment python=3.11 -y
```

Activate it. Do this **in every new terminal** before working with the
project:

```bash
conda activate codex-4-oci-enterprise-ai-deployment
```

Install the libraries, from the tool home. This also installs the OCI command
line (OCI CLI):

```bash
pip install -r requirements-dev.txt
```

Expected: the command ends without errors. Check the OCI CLI:

```bash
oci --version
```

*If `conda activate` fails:* run `conda init`, close the terminal, open a new
one, and try again.

## 4. Connect the OCI CLI to your tenancy

The skills use the OCI CLI to talk to OCI. It needs a profile on your
workstation, created once with a guided command:

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

*If it fails with `NotAuthenticated`:* the public key was not uploaded to the
same user, or the profile has a wrong user or tenancy OCID. Run
`oci setup config` again.

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

This makes the five skills available to Codex in every project, as links to
the tool home:

```bash
scripts/install_skills.sh
```

Expected: one `created:` line per skill. Then **start a new Codex session**
(close and reopen the Codex CLI, or reload VS Code), so that Codex discovers
them. To check, type `$` in Codex: the list must include `oci-agent-new`,
`oci-agent-build`, `oci-agent-push`, `oci-agent-deploy`, and
`oci-agent-verify-deployment`.

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

Create an empty folder for the agent and open it in a **new** Codex session:

```bash
mkdir ~/Progetti/my-first-agent
```

```bash
git -C ~/Progetti/my-first-agent init
```

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

## Windows

Use **PowerShell 7.4 or later** (`pwsh`) with Docker Desktop or Podman, or
work inside **WSL2** with Rancher Desktop and use the commands above
unchanged. The details are in
[native PowerShell 7](../notes/windows-powershell-native.md) and
[Rancher Desktop with WSL2](../notes/windows-rancher-desktop-wsl2.md).

In PowerShell, the commands that differ are:

| macOS and Linux | Windows PowerShell |
| --- | --- |
| `cp .env.example .env` | `Copy-Item .env.example .env` |
| `scripts/install_skills.sh` | `.\scripts\install_skills.ps1` |
| `scripts/check_setup.sh` | `.\scripts\check_setup.ps1` |
| `mkdir ~/Progetti/my-first-agent` | `New-Item -ItemType Directory $HOME\Progetti\my-first-agent` |
