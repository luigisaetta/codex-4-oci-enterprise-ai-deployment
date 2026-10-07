# {{UI_TITLE}}: demo interface

A local web page to show the agent to its users. It runs only on this
computer and calls the agent through a small local server, so no address or
secret reaches the browser.

## Start

Once, inside this `ui` folder:

```bash
npm install
```

Every time:

```bash
npm run dev
```

Open <http://127.0.0.1:3000>.

## Choose which agent it talks to

Edit `.env.local` (copy it from `.env.local.example` the first time):

* `AGENT_BASE_URL=http://127.0.0.1:8080` for the local container, before the
  deploy;
* the Hosted Application address for the deployed agent; the line to use is
  in `.env.local.example`.

Restart `npm run dev` after a change. With the deployed agent, every request
is a real call to OCI.

## What it shows

Business information for the agent's users, as described in `ui-spec.md`.
Technical problems are written to the terminal where `npm run dev` runs.
