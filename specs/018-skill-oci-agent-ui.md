# Spec 018: skill `oci-agent-ui`, an end-user demo UI for an agent

Status: implemented; template verified locally; acceptance on a real agent pending.
Date: 2026-10-07.

## Problem

An agent released with the skills is an HTTP endpoint that answers JSON. To
show it to a customer or to management, someone must call it with `curl` and
read the JSON: a demo that only technical people can follow. A UI was built
by hand for `express_order` (`web-ui`, Next.js) and showed that a local web
page makes the agent understandable, but nothing in the tool produces one.

## Scope

* A new skill, `oci-agent-ui`, that adds a local demo UI to an existing agent
  repository, from the agent's specification.
* The UI is **end-user oriented**: it shows business information for the
  customer persona, not technical data.
* A maintained Next.js template in the skill's assets; the skill generates
  only the agent-specific parts.
* Spec-first: the skill drafts a short UI specification, the developer
  approves it, then the UI is generated.
* An optional "Demo" section in the agent specification template.
* `ui` and `node_modules` excluded from the agent image by the Dockerfile
  template's `.dockerignore`.

## Non-goals

* Deploying the UI: it runs only on the developer's machine.
* Agents with the `public-idcs` profile: the skill stops and says so (a later
  iteration may obtain the token on the server side).
* Persistence, user accounts, analytics, or telemetry.
* Agents with more than one business endpoint, streaming, or file upload.
* Technical views (raw JSON, HTTP status, latency, request identifiers),
  unless the developer asks for them explicitly (see "End-user rules").
* Changes to the agent's code or manifest.

## Prerequisites

* An agent repository with `agent-spec.md` and `agent.yaml` (created with
  `oci-agent-new`, or written by hand with the same sections).
* **Node.js ≥ 20.9** (required by Next.js 16). Preferred installation for
  non-technical users: in the project Conda environment,
  `conda install -c conda-forge nodejs` (to be verified, U1); a system
  installation also works.
* The agent's address: the local container (`http://127.0.0.1:8080`) for a
  test before the deploy, or the deployed Hosted Application (its OCID, shown
  by the deploy and the verification).

## Platform and tool facts (verified 2026-10-07)

| # | Fact | Evidence |
| --- | --- | --- |
| F1 | Next.js 16.3.8 requires Node `>=20.9.0`. | `express_order/web-ui/node_modules/next/package.json` |
| F2 | Next.js 16 writes an `AGENTS.md` asking coding assistants to read `node_modules/next/dist/docs/` first, because its APIs changed. | `express_order/web-ui/AGENTS.md` |
| F3 | A Next.js API route that forwards the browser's request to the agent avoids calling the OCI endpoint from the browser and keeps any secret on the server; it worked for `express_order`. | `express_order/web-ui/app/api/express-orders/route.js` |
| F4 | The deployed endpoint is `https://inference.generativeai.<region>.oci.oraclecloud.com/20251112/hostedApplications/<application-ocid>/actions/invoke/<path>`. | `scripts/verify_deployment.sh` |

### Assumptions, to confirm during implementation

| # | Assumption |
| --- | --- |
| U1 | `conda-forge` provides a `nodejs` ≥ 20.9 for macOS (arm64, x86_64), Linux, and Windows. Verified 2026-10-07 for osx-arm64, osx-64, and linux-64 (24.21.0 LTS available); not verified for win-64, so Windows users install Node.js LTS from the Node.js website. |
| U2 | The deployed endpoint answers a server-side `fetch` from the API route without CORS configuration (CORS applies to browsers only). |

## End-user rules

The UI is for the **customer persona** of the agent specification, not for the
developer.

1. **Business language.** Titles, labels, help texts, and messages use the
   persona's vocabulary and the specification's language. Field names of the
   API never appear; each shown field has a business label.
2. **What matters to the persona.** The page is organized around the
   specification's **use case** and **expected outcomes**: the outcome is the
   most visible element of the result. Only fields that serve the outcome are
   shown; internal fields are omitted.
3. **No technical data by default.** No raw JSON, HTTP status codes, latency,
   OCIDs, request identifiers, model names, or stack traces. Business
   identifiers (an order number, a ticket number) are business data and are
   shown.
4. **Errors in plain words.** A rejected request explains, in business terms,
   why and what the user can do; an unavailable agent shows "The service is
   temporarily unavailable, please try again"; technical details go only to
   the server log.
5. **Ready to demo.** The input area offers two or three example requests
   taken from the use case, so a presenter can show the agent in one click.
6. **Explicit exceptions only.** A technical view (for example a collapsed
   "Technical details" panel with the raw response) is added only when the
   developer asks for it explicitly in the request or the UI specification.

## UI specification (spec-first)

Before writing any UI file, the skill drafts `ui/ui-spec.md` and stops for
review. The draft, written in the language of the agent specification,
contains:

* **Audience**: the persona, from the agent's business context.
* **Story**: the one-sentence use case shown on the page, and the outcome the
  persona should see.
* **Input**: what the user types or selects, with business labels, limits, and
  the example requests.
* **Result**: the business fields shown, in order, each with its label and
  the agent response field it comes from; the outcome first.
* **Messages**: the plain-language text for each rejection reason and for an
  unavailable service.
* **Technical view**: "none", unless requested.

The skill takes this information from `agent-spec.md` (business context, API,
errors, and the optional "Demo" section) and lists what it cannot derive under
"Open questions". After explicit approval it re-reads `ui/ui-spec.md` and
generates the UI from it.

## Generated files

In the agent repository, a `ui/` folder:

| File | Source |
| --- | --- |
| `package.json`, `next.config.mjs`, `app/layout.jsx`, `app/globals.css`, `.gitignore`, `.env.local.example`, `README.md` | Template, unchanged except the agent name |
| `app/api/agent/route.js` | Template: forwards the request to `AGENT_BASE_URL` + the business path, with a bounded timeout (90 s), and maps failures to plain-language messages |
| `app/page.jsx` | Template: a generic page that renders `app/demo-config.js` (title, story, input fields, example requests, outcome, business fields, messages), with an optional technical panel off by default |
| `app/demo-config.js` | Generated from `ui/ui-spec.md` within the end-user rules; small extra components only when the configuration cannot express the result |
| `ui-spec.md` | Drafted by the skill, approved by the developer |

Rules:

* `AGENT_BASE_URL` is read only from `ui/.env.local` (ignored by Git; the
  example file holds placeholders). The address is never written in the code.
* The browser calls only the local API route.
* The server listens on `127.0.0.1` only.
* The template pins Next.js 16 and React 19, the versions verified with
  `express_order`.
* Existing files are never overwritten. If the agent's `.dockerignore` does not
  exclude `ui`, the skill shows the line to add and adds it only after the
  developer's confirmation.

## Workflow of the skill

1. Target platform check: an agent for OCI Generative AI Hosted Applications.
2. Read `agent-spec.md` and `agent.yaml`; stop if the profile is `public-idcs`,
   if the agent has no business endpoint, or if `ui/` already exists.
3. Draft `ui/ui-spec.md`; stop for review (changes by hand or in the chat; only
   that file is changed until approval).
4. After approval, create the `ui/` files from the template and the approved
   UI specification.
5. Ask for the agent address (local container or Hosted Application OCID) and
   write `ui/.env.local`.
6. With the developer's approval (it downloads packages from the Internet),
   run `npm install`; then `npm run build`, which must pass.
7. Closing message: how to start the UI (`npm run dev -- --hostname 127.0.0.1`),
   the address to open, how to switch between the local container and the
   deployed agent, and that calling a deployed public endpoint is a real call.

The skill reads the Next.js documentation shipped in `node_modules` before
generating code (F2).

## Documentation

* `skills/oci-agent-ui/SKILL.md`, `agents/openai.yaml`, the template in
  `assets/`, and `references/ui-guidelines.md` (the end-user rules, with
  examples of good and bad labels).
* The agent specification template: an optional "Demo" section (audience of
  the demo, story, example requests, what to show).
* `dockerignore.template`: `ui` and `**/node_modules`.
* Getting started: Node.js in the Conda environment; a step "Show the agent"
  after the first agent. README, skill catalog, and `CHANGELOG.md`.

## Tests (offline)

* `tests/test_skills.py`: the new skill passes the structural checks.
* A new test: the template contains no OCID, no `https://` agent address, and
  no secret; `.env.local.example` holds only placeholders; the API route reads
  `AGENT_BASE_URL` from the environment; the server binds to `127.0.0.1`;
  `dockerignore.template` excludes `ui` and `node_modules`.

## Acceptance criteria

1. For `express_order_rp`, the skill drafts a UI specification from its
   agent specification, and after approval generates a UI whose
   `npm run build` passes without manual edits.
2. The UI works against the local container and against the deployed agent,
   switching only `ui/.env.local`.
3. The page shows business information only: no JSON, status codes, latency,
   or OCIDs; a rejected request and an unavailable agent show plain-language
   messages.
4. A non-technical viewer can follow a demo with the example requests.
5. The offline tests, Black, Pylint, and pytest pass.


## Implementation decisions

* **Generic page plus configuration.** The template page renders
  `app/demo-config.js`; the skill generates mostly that file. This keeps the
  generated code small and away from Next.js 16 API changes (F2), and gives
  every demo a consistent look; custom components remain possible.
* **Bridge responses.** The route returns only a category to the page: `ok`
  (with the agent's JSON, rendered through the configuration), `rejected`
  (agent HTTP 400 or 422, its business validation, guideline B3), `invalid`
  (the page sent a non-JSON or oversized body), or `unavailable` (any other
  status, including platform 401, 403, and 404, a non-JSON body, a timeout, or
  a network error). Causes are logged by the local server only.

## Verification record

### 2026-10-07, local

* Template copied to a temporary folder: `npm install` (22 packages) and
  `npm run build` passed with Next.js 16.4.0 (Turbopack) on Node 24.18.0;
  routes `/` (static) and `/api/agent` (dynamic).
* `next start` against a fake local agent: a 200 answer returned `ok` with the
  data; 400 returned `rejected` with the agent's message; 500, a stopped
  agent, and a non-JSON request returned `unavailable` or `invalid`, with the
  cause only in the server log; the server listened on `127.0.0.1:3091` only.
* Offline tests: `tests/test_ui_template.py` (template files, no address,
  OCID, or secret, bridge reading `.env.local` values, loopback binding,
  placeholders, technical view off, `ui` and `node_modules` excluded from
  agent images, skill links and rules) and the structural skill tests.
* Pending: acceptance criteria 1–4 on a real agent (`express_order_rp`).

