---
name: oci-agent-ui
description: Create a local, end-user demo web UI (Next.js) for an existing agent of OCI Generative AI Hosted Applications, from its agent-spec.md. Use when asked to build a UI, a demo page, or a front end to show an OCI agent to customers or management. Drafts ui/ui-spec.md first, then, after approval, generates the ui/ folder. The UI runs only on this computer; it never deploys anything.
---

# OCI Agent UI

Contract and verification: [Spec 018](../../specs/018-skill-oci-agent-ui.md).

## Purpose and when to use

Add a `ui/` folder to an agent repository: a local web page that shows the
agent to its **customer persona**, in business language, with one-click
example requests. Use it to demo an agent created with `oci-agent-new` (or
with the same specification sections), against the local container or the
deployed Hosted Application.

## Tool home and working directory

Resolve the real path of this skill's folder, following symbolic links:

```bash
skill_real="$(cd -P -- "<this skill folder>" && pwd -P)"
TOOL_HOME="$(dirname -- "$(dirname -- "$skill_real")")"
```

In PowerShell, resolve the skill folder's link target and take its grandparent.
The current workspace must be the agent folder. Never change directory into
the tool home or write there. The tool's `.env` (`OCI_AGENT_ENV_FILE`, default
`$TOOL_HOME/.env`) is not needed here: never source, read into the
conversation, print, or edit it, because it may hold agent secrets.

## Prerequisites

* An agent folder with `agent-spec.md` and `agent.yaml`, opened as the
  workspace.
* **Node.js 20.9 or later** and `npm`. Check with `node --version`. If it is
  missing, the simplest installation is in the project Conda environment:
  `conda install -c conda-forge nodejs` (verified for macOS and Linux); on
  Windows, install the LTS version from the Node.js website.
* Network access for `npm install`, which downloads the UI packages.
* The agent's address: the local container (`http://127.0.0.1:8080`, while
  `oci-agent-build` verification or `docker run` is up) or the deployed Hosted
  Application OCID (shown by the deploy and the verification).

## Target platform check

Create demo UIs only for agents of OCI Generative AI Hosted Applications.
Before running commands, confirm this is the developer's target. If the request
concerns another platform or the target is unclear, stop and ask; never switch
silently.

## Inputs

* The developer's request, which may add wishes for the page.
* `agent-spec.md`: business context (persona, use case, expected outcomes,
  concerns), API, errors, and the optional "Demo" section.
* `agent.yaml`: `deploy.profile` and the business path of the functional
  checks.

Never invent business content: what the specification does not say goes under
"Open questions" of the UI specification.

## Workflow

1. Perform the target platform check.
2. Read `agent-spec.md` and `agent.yaml`. Stop and explain if `ui/` already
   exists (never overwrite), if `deploy.profile` is `public-idcs` (not
   supported yet), or if the agent has no single JSON business endpoint.
3. Read the [UI guidelines](references/ui-guidelines.md). Copy
   [the UI specification template](assets/ui-spec.template.md) to
   `ui/ui-spec.md`, replace `{{AGENT_NAME}}`, and fill it from the agent
   specification, in its language, following the end-user rules. Stop and ask
   the developer to review it. Until approval, change only `ui/ui-spec.md`
   (the developer may edit it by hand or ask for changes in the chat).
4. After explicit approval, read `ui/ui-spec.md` again, then copy the template
   into `ui/` without overwriting any file:

   ```bash
   cp -R -n "$TOOL_HOME/skills/oci-agent-ui/assets/ui-template/." ui/
   ```

   Replace `{{UI_NAME}}` in `ui/package.json` (the agent name, lowercase,
   hyphens only) and `{{UI_TITLE}}` in `ui/README.md`. Write
   `ui/app/demo-config.js` from the approved UI specification (guideline T1).
   Do not change `ui/app/api/agent/route.js` (T2).
5. Ask whether the UI must talk to the local container or to the deployed
   agent (and, for the deployed agent, the Hosted Application OCID and the
   region). Copy `ui/.env.local.example` to `ui/.env.local` and set
   `AGENT_BASE_URL` and `AGENT_PATH`. Never write the address anywhere else.
6. Check `node --version` (20.9 or later). With the developer's approval,
   because it downloads packages, run in `ui/`:

   ```bash
   npm install
   ```

   Then build; it must pass:

   ```bash
   npm run build
   ```

   On a build error, read `ui/node_modules/next/dist/docs/` (T5), fix only
   the files generated in this session, and build again.
7. If the agent's `.dockerignore` does not exclude `ui` and
   `**/node_modules`, show the two lines to add and add them only after the
   developer's confirmation; the UI must never be sent to the image build.
8. Print the closing message.

## Constraints on the generated UI

The end-user rules E1–E6 and the template rules T1–T5 of the
[UI guidelines](references/ui-guidelines.md) apply. In short: business
language for the persona; outcome first; no JSON, HTTP status, latency, OCIDs,
or model names unless explicitly requested; plain-language errors; example
requests; the browser calls only the local `/api/agent` route; the address
lives only in `ui/.env.local`; the server listens only on `127.0.0.1`.

## Closing message

1. The files created, and the `.dockerignore` lines added or still to add.
2. How to start the UI, from the `ui` folder: `npm run dev`, then open
   `http://127.0.0.1:3000`.
3. How to switch between the local container and the deployed agent: edit
   `AGENT_BASE_URL` in `ui/.env.local` and restart `npm run dev`. With the
   deployed agent, every request is a real call to a public endpoint.
4. Where technical problems appear: in the terminal that runs `npm run dev`.

## Limitations

One JSON business endpoint; agents with the `public-noauth` profile only; no
streaming or file upload; no deployment of the UI; no persistence. The build
checks that the page compiles, not that it convinces a viewer: review it in the
browser before a demo.
