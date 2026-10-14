---
name: oci-agent-ui
description: Create a local, end-user demo web UI (Next.js) for an existing agent of OCI Generative AI Hosted Applications (Hosted Deployments, OCI Enterprise AI), from its agent-spec.md; not for OCI AI Data Platform (AI DP) agents. Use when asked to build a UI, a demo page, or a front end to show an OCI agent to customers or management. Drafts ui/ui-spec.md first, then, after approval, generates the ui/ folder. The UI runs only on this computer; it never deploys anything.
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

Create demo UIs only for agents of OCI Generative AI Hosted Applications
(also called Hosted Deployments or OCI Enterprise AI)
([Spec 028](../../specs/028-platform-dispatch.md)). Before any command, decide
the platform in this order:

1. If the repository's `AGENTS.md` has a "Target platform" section, follow it.
   If it names OCI AI Data Platform (AI DP), stop with this message:
   "This agent targets OCI AI Data Platform (AI DP); these skills support only
   OCI Generative AI Hosted Applications. Use the skills for OCI AI DP."
2. Otherwise, infer it from the files: an `agent.yaml` with `schema_version`
   and a `Dockerfile` indicate Hosted Applications; an entry file whose class
   has a synchronous `setup()` and an asynchronous `invoke()`, without
   `agent.yaml`, indicates an AI DP code-first agent: stop with the message
   above.
3. If the signals are mixed or absent, ask the user which platform they mean.

Never switch platform silently.

## Customer name

Contract: [Spec 020](../../specs/020-demo-customer-name.md). Before drafting,
read the customer name approved for demos (`Supremo` unless the tool's `.env`
sets `DEMO_CUSTOMER_NAME`); the helper prints only that value:

```bash
python "$TOOL_HOME/scripts/tool_config.py" demo-customer
```

* The page and every file of `ui/` (`ui-spec.md`, `app/demo-config.js`:
  titles, story, labels, example requests, messages) name the customer only
  with the demo name.
* If the developer names the real customer, keep that name only in the
  conversation. Reply once, without repeating it: "In every file and in the
  demo the customer is called <demo name>." Never ask for the real name.
* If `agent-spec.md` names a customer other than the demo name, ask whether it
  is the real customer; if so, never copy it, and suggest replacing it in
  `agent-spec.md` too.
* Never write the real name to disk in any form: full name, abbreviation,
  domain, or e-mail address. It may be used in online searches only when they
  help to understand the customer's business; never copy from the results
  product names, brands, people, addresses, or figures that identify the real
  customer.
* Before the closing message, search the files you wrote for the real name
  and its obvious variants, case-insensitively, with a local search (for
  example `grep -ril`). Replace every match with the demo name and report the
  fix without the name. Skip this check when no real name was given.
* Make sure the agent repository's `AGENTS.md` carries the same rules, which
  Codex reads in every later session, with or without a skill (workflow
  step 4).

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
   exists (never overwrite), or if the agent has no single JSON business
   endpoint (or the asynchronous pair of [Spec 024](../../specs/024-asynchronous-agents.md):
   a POST that starts a job and a GET for its status). Both profiles are supported: `public-noauth`, and `public-idcs`
   through a token obtained by the local server ([Spec 022](../../specs/022-idcs-credentials-for-ui-and-verifier.md)).
3. Read the [UI guidelines](references/ui-guidelines.md). Copy
   [the UI specification template](assets/ui-spec.template.md) to
   `ui/ui-spec.md`, replace `{{AGENT_NAME}}` and `{{DEMO_CUSTOMER_NAME}}`, and
   fill it from the agent
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
   For an asynchronous agent, set `mode: "async"` and list in `steps` each
   step `name` of the agent with its business label (guideline T6).
   Do not change `ui/app/api/agent/route.js` (T2). Then add or refresh the
   customer-name rules in the agent repository's `AGENTS.md`; it never changes
   other content:

   ```bash
   python "$TOOL_HOME/scripts/agent_instructions.py" ensure --target .
   ```
5. Ask whether the UI must talk to the local container or to the deployed
   agent (and, for the deployed agent, the Hosted Application OCID and the
   region). Copy `ui/.env.local.example` to `ui/.env.local` and set
   `AGENT_BASE_URL` and `AGENT_PATH`. Never write the address anywhere else.
   For `public-idcs`, also set in `ui/.env.local` `IDCS_DOMAIN_URL` (from
   `deploy.auth.domain_url`) and `IDCS_TOKEN_SCOPE` (`deploy.auth.audience`
   immediately followed by `deploy.auth.scope`), and add the two empty lines
   `IDCS_CLIENT_ID=` and `IDCS_CLIENT_SECRET=`. Never write, read, or print the
   client ID or secret, and never read `ui/.env.local` after asking the
   developer to fill them in.
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
8. Run the customer-name check of [Customer name](#customer-name), then print
   the closing message.

## Constraints on the generated UI

The end-user rules E1–E7 and the template rules T1–T5 of the
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
5. For `public-idcs`: fill in `IDCS_CLIENT_ID` and `IDCS_CLIENT_SECRET` in
   `ui/.env.local` by hand (Git ignores the file), never in the chat; the
   values come from the confidential application
   ([Protecting an agent with JWT tokens](../../docs/idcs-confidential-application.md)).
   The local server uses them to request a token; the browser never sees
   them.

## Limitations

One JSON business endpoint; no sign-in of end users (the page runs only on
this computer); no streaming or file upload; no deployment of the UI; no persistence. The build
checks that the page compiles, not that it convinces a viewer: review it in the
browser before a demo.
