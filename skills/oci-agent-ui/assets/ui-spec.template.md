# Demo UI specification: {{AGENT_NAME}}

<!-- Draft created by oci-agent-ui from agent-spec.md. Review and edit every
section, then ask Codex to continue. Write in the language of the demo. -->

## Audience

* Customer: {{DEMO_CUSTOMER_NAME}} (the name approved for demos; never write
  the real customer name in this file or in the page).
* Who uses the page (the customer persona) and who watches the demo.

## Story

* Headline: the title of the page.
* Use case: one sentence the persona recognizes.
* Outcome: what the persona must see at the end.

## Input

For each field: business label, request field of the agent, type, limits,
and whether it is required.

Example requests (two or three, from the use case), each with a short label.

## Result

* Outcome: the response field that tells whether the persona got what they
  wanted, and the label and tone (success, warning, info) of each value.
* Message: the response field with a business sentence, if any.
* Fields shown, in order: business label and response field. Lists: the
  columns to show.

Fields of the response that are not listed are not shown.

## Steps (asynchronous agents only)

The agent's steps, in order, each with the business label shown while the
job runs (for example `extract`: "Reading the document"). For an asynchronous
agent, Result describes the job's `result`.

## Messages

* Invalid input:
* Request rejected without its own message:
* Service unavailable:
* While the agent works:

## Technical view

None.

## Open questions

Points the agent specification did not answer.
