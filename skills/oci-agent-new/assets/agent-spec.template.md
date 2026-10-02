# Agent specification: {{AGENT_NAME}}

<!-- Draft created by oci-agent-new from the first request. Review and edit
every section, then ask Codex to continue. Write in any language. -->

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

Runtime variables: name, source (`value` or `from_env`), and whether it is a
secret.

## Errors

What the agent returns when the input is missing or invalid, or a dependency
fails.

## Functional checks

Request → expected response, for at least one deterministic case.

## Deployment

* Application name: {{AGENT_NAME}}
* Access: `public-noauth`

## Open questions

Points the first request did not answer.
