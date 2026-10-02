# Quickstart: publish an agent with one request

This page is for people who want to put an agent online without learning the
tooling. You describe what you want to Codex in plain language; Codex uses the
OCI agent skills, shows you what it is about to do, and asks for your approval
before anything changes in OCI.

For the details behind each step, see the
[step-by-step guide](using-oci-agent-skills.md).

## Before you start

Someone must have prepared your workstation once, following the
[Setup section of the README](../README.md#setup):

* the tools are installed (Conda environment, Docker, OCI CLI);
* the tenancy file (`.env`) is configured;
* the skills are installed with `scripts/install_skills.sh`.

A tenancy administrator must also have set up the IAM policies once: your
group needs permission to publish images and create Hosted Applications, and
the applications need permission to pull the image. See
[IAM policies](iam-policies.md).

To check, open Codex and type `$`: the list must include `oci-agent-build`,
`oci-agent-push`, `oci-agent-deploy`, and `oci-agent-verify-deployment`. If
they are missing, start a new Codex session; if they are still missing, ask
whoever prepared the workstation.

## 1. Open your agent in Codex

Open the folder of your agent as the Codex workspace, in a new session. The
folder must contain the agent's code and four files: `Dockerfile`,
`requirements.txt`, `.dockerignore`, and `agent.yaml`.

No agent yet? Ask Codex to create one in an empty Git repository, for example:

```text
Create a small agent in this repository, to be released with the oci-agent
skills. Follow the section "Creating a new agent repository" of
~/Progetti/codex-4-oci-enterprise-ai-deployment/docs/using-oci-agent-skills.md.
The agent receives a text with POST /analyze and returns the number of words.
Add tests, and do not build or deploy anything yet.
```

Replace the path with the location of the tool checkout on your workstation.

## 2. Publish the first version

Ask for the release in one sentence, with a version number:

```text
Release version 0.1.0 of this agent on OCI Hosted Applications.
```

Codex then works through the whole chain:

1. builds the container image and tests it on your machine;
2. publishes the image to the OCI container registry (OCIR);
3. shows the deployment plan and deploys it;
4. checks that the deployed agent answers.

Codex stops and asks for your approval before each change in OCI: creating
the registry repository (first time only), publishing the image, and
deploying. Read what it shows before you say yes:

* the version (tag) is the one you asked for;
* the application name is your agent's;
* the endpoint is **public and without authentication**: anyone who knows the
  address can call it.

If Docker asks you to log in to the registry, Codex shows the complete
`docker login` command. Run it yourself and type your OCI auth token only at
Docker's password prompt, never in the chat.

At the end, Codex reports that the agent is healthy and ready. Keep the
**application OCID** it prints: it identifies your agent in OCI.

## Protect your agent with a token

An agent is unprotected with `deploy.profile: public-noauth` (anyone can call
it) and protected with `deploy.profile: public-idcs` (callers need a JWT
token). The [agent manifest reference](agent-manifest-reference.md) explains
both, and every other field of `agent.yaml`.

Ask the identity-domain administrator for the domain URL, primary audience,
scope, client ID, and client secret, and confirm whether the confidential
application is new or reused. Put only the three non-secret values in
`agent.yaml` under `deploy.auth` and set `deploy.profile: public-idcs`:

```yaml
deploy:
  profile: public-idcs
  auth:
    domain_url: <identity-domain-url>
    audience: <audience-of-the-confidential-application>
    scope: <scope-of-the-confidential-application>
```

Before asking Codex to verify the protected agent, export the client ID and
client secret in your own shell. Never paste either value, or an access token,
into the chat. The deployment checks only the format of the three manifest
values; verification tests them against the identity domain.

## 3. Publish a new version

Change the code, then ask for a release with a **new** version number:

```text
Release version 0.2.0 of this agent on OCI Hosted Applications.
```

The new version replaces the old one in the same application. The endpoint
address does not change, so the users of your agent do not need to update
anything.

Always use a new version number for new code. Publishing different code
with a version number that already exists overwrites the old image in the
registry.

## 4. Go back to a previous version

If the new version misbehaves, return to the previous one:

```text
Deploy version 0.1.0 of this agent again. Deploy only: the image is already
in OCIR, do not build or push.
```

"Deploy only" matters: it tells Codex to reuse the image that was already
published and tested, instead of rebuilding it from the current code. The
switch takes about 10 seconds, and the endpoint stays the same.

A request to deploy authorizes only deployment. Creating an OCIR repository or
pushing an image needs its own request and explicit authorization through the
push skill.

## 5. Check that it works

To check the agent at any time:

```text
Verify the deployment of this agent, version 0.2.0, and also run its
functional checks.
```

Codex checks that OCI runs the expected version, and that the agent answers
its health, readiness, and functional checks.

## Cleaning up

The deploy skill deletes only a `FAILED` deployment, after you request a new
deploy of that failed release and approve its replacement plan. When you no
longer need an agent online, remove its Hosted Application from the OCI
Console, or ask an administrator. Old versions stay stored inside the
application (up to 20); only inactive ones can be removed, from the Console.

## If something goes wrong

| What you see | What to do |
| --- | --- |
| Codex asks "Which agent manifest should I use?" | Answer `./agent.yaml`, or the path of your agent's manifest. |
| Codex talks about "AI Data Platform" or "AI DP" | Say "OCI Hosted Applications" explicitly in your request; those are different skills. |
| The registry refuses the push, or asks to log in | Your Docker login expired: run the `docker login` command that Codex shows. |
| An OCI command fails with `NotAuthorizedOrNotFound` | The resource may be missing or permission may be missing; send the message and [IAM policies](iam-policies.md) to your administrator. |
| `Creation in progress` | The deployment already exists; approve its plan to resume waiting without another create. |
| `Application creation in progress` | Approve its plan to wait for the application, check its configuration, and create the first deployment when ready. |
| Exit 26, with an OCID, state, and elapsed time | OCI is still working. Nothing else was changed or deleted after the request. Ask Codex to run deploy again to resume waiting; do not delete or recreate. |
| `Failed deployment` with an OCI error | Read the reported code and message. The deploy stops without another mutation. You may ask for a new deploy of that failed release. |
| `Replace failed deployment` | After requesting a new deploy, review and approve the replacement plan. The script deletes only the `FAILED` deployment, waits for deletion, then creates and waits for its replacement. |
| A node-pool capacity error during creation | This is a known transient failure. Try again later, then ask for a new deploy. If the deployment is `FAILED`, replacement requires your request and approval of its plan. |
| The deployment stops with another application or deployment state | Read the reported state. If it persists, send the message to your administrator. |
| The check says "not ready" | The agent may still be starting: wait a minute and ask Codex to verify again. |
