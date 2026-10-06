# Agent specification: {{AGENT_NAME}}

<!-- Draft created by oci-agent-new from the first request. Review and edit
every section, then ask Codex to continue. Write in any language. -->

## Business context

* Customer persona: who the agent is for (role, team, company; the customer
  can be internal).
* Use case: the situation the agent addresses.
* Expected outcomes: what the customer expects to see or obtain.
* Customer concerns (optional): for example security, scalability, cost,
  data residency; for each, how the agent addresses it.

## Purpose

What the agent does, for whom, in one paragraph.

## API

* Endpoint: `POST /<path>`
* Request (JSON): field, type, constraints, example.
* Response (JSON): fields returned on success, and on a rejected request.

## Behavior

The steps the agent follows, in order, and its business rules.

## Data and dependencies

* Files packaged with the agent (for example a catalog).
* External services (for example an LLM: model, region).

## Configuration

* LLM authentication: `api_key` (default, `GENAI_API_KEY` with `from_env`) or
  `resource_principal` (no secret; needs `GENAI_PROJECT_ID` and the runtime
  IAM policies).
* Runtime variables: name, source (`value` or `from_env`), and whether it is a
  secret.

## Errors

What the agent returns when the input is missing or invalid, or a dependency
fails.

## Functional checks

Request → expected response, for at least one deterministic case.

## Deployment

* Application name: {{AGENT_NAME}}
* Deployment region: the tool's `OCI_REGION` (`.env`)
* Access: `public-noauth`

## Open questions

Points the first request did not answer.
