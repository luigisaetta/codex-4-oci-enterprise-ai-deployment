---
name: oci-agent-push
description: Create an OCIR repository and push a verified container image for OCI Generative AI Hosted Applications, not OCI AI Data Platform (AI DP) code-first agents.
---

# OCI Agent Push

Prepare a verified local `linux/amd64` agent image for OCIR, create its missing
private repository only after explicit authorization, then push only after a
separate push authorization. This skill does not deploy hosted applications.

## Tool home and working directory

Resolve the real path of this skill's folder, following symbolic links:

```bash
skill_real="$(cd -P -- "<this skill folder>" && pwd -P)"
TOOL_HOME="$(dirname -- "$(dirname -- "$skill_real")")"
```

In PowerShell, resolve the link target of the skill folder and take its
grandparent. Run every script as `"$TOOL_HOME/scripts/<name>.sh"` (PowerShell:
`& "$TOOL_HOME\scripts\<name>.ps1"`) from the user's current folder. Never
change directory into the tool home. Pass the manifest path as the user gives it
(relative to the current folder) or as an absolute path. Its build paths are
relative to the manifest's own folder.

Run inside the Conda environment `codex-4-oci-enterprise-ai-deployment`
(activated, or `conda run --no-capture-output -n
codex-4-oci-enterprise-ai-deployment ...`), or set `OCI_AGENT_PYTHON`. Tenancy
settings come from `OCI_AGENT_ENV_FILE`, default `"$TOOL_HOME/.env"`; the
scripts read it themselves. Never source it, read it into the conversation, or print its content: it may
hold agent secrets. In a
sandboxed session, request permission for Docker and network access before the
first Docker, OCI CLI, or HTTP command, instead of retrying after a failure.

## Prerequisites

Read [OCIR authentication and target rules](references/ocir-authentication.md).
The image must already have passed
`oci-agent-build` verification. Docker and OCI CLI must be available and the
configured OCI CLI profile must have IAM access to the target compartment.

The tenancy file holds only `OCI_REGION`, `OCI_COMPARTMENT_NAME`,
`OCIR_TENANCY_NAMESPACE`, and `OCIR_USERNAME`. The agent manifest supplies the
repository and local image name. Do not put an
auth token, password, private key, or Docker credential in it, in a prompt, or
in command arguments.

`OCIR_USERNAME` must be the complete OCIR login username, normally
`<tenancy-namespace>/<username>` (or
`<tenancy-namespace>/<identity-domain>/<username>` for applicable identity-domain
tenancies), rather than only the OCI Console username.

## Shell selection

The examples below are Bash. From PowerShell 7.4+ run the matching PowerShell twin
with the same option names in `-Option` form (`--push` becomes `-Push`,
`--repository` becomes `-Repository`); outputs and exit codes are identical, and
`docker login`/`docker logout` become `podman login`/`podman logout` when the
selected engine is Podman. Follow the shell in use, never the operating system,
and do not mix the two families in one release. Rule and mapping table:
[Choosing Bash or PowerShell](../README.md#choosing-bash-or-powershell).

## Target platform check

These skills release container images to OCI Generative AI Hosted Applications.
Before any command, check the current repository: an `agent.yaml` with
`schema_version` and a `Dockerfile` indicate Hosted Applications; an entry file
whose class has a synchronous `setup()` and an async `invoke()`, without
`agent.yaml`, indicates an OCI AI Data Platform (AI DP) code-first agent. If the
signals indicate AI DP, stop and tell the user to use the `aidp-agent-deploy`
skill instead. If the signals are mixed or absent, ask the user which platform
they mean. Never switch platform silently.

## Workflow

1. Require an agent manifest named in the current request. If it is absent, ask
   “Which agent manifest should I use?” before inspecting Docker or OCI.
   Never select a demo, scan for a manifest, or infer one from conversation
   history; an explicit “use the same agent/manifest as the immediately preceding
   step” is sufficient. Confirm the local image and its user-supplied semantic tag. Check that all
   required non-secret settings are configured; do not print unrelated tenancy-file
   content. Confirm OCI CLI availability and profile access.
2. Resolve `OCI_REGION` dynamically to its OCIR region-key endpoint and show
   the exact target. The resolver runs `oci iam region list`, selects the exact
   region name, lowercases its key, and constructs `<region-key>.ocir.io`. It
   stops if the region is not returned or the CLI request fails.

   ```bash
   OCIR_REGISTRY="$("$TOOL_HOME/scripts/resolve_ocir_registry.sh")"
   ```

   The target is
   `${OCIR_REGISTRY}/${OCIR_TENANCY_NAMESPACE}/<manifest repository>:<tag>`.
3. Resolve `OCI_COMPARTMENT_NAME` and inspect the target with the non-mutating
   command below. It proceeds only if exactly one active compartment OCID
   matches; exit code 20 means that the repository is absent.

   ```bash
   "$TOOL_HOME/scripts/ensure_ocir_repository.sh" --repository <manifest repository>
   ```

4. If the requested repository is absent, show the resolved compartment OCID
   reported by the command and obtain explicit user authorization before running:

   ```bash
   "$TOOL_HOME/scripts/ensure_ocir_repository.sh" --repository <manifest repository> --create
   ```

   This creates a private, mutable repository, waits up to 120 seconds for
   `AVAILABLE`, records the new repository OCID, and stops on failure. Do not
   change an existing repository.
5. Before `docker login`, resolve the registry and username. Use the exported
   `OCIR_USERNAME` when available; otherwise obtain it from the tenancy file:

   ```bash
   OCI_AGENT_PYTHON="${OCI_AGENT_PYTHON:-python}"
   OCIR_REGISTRY="$("$TOOL_HOME/scripts/resolve_ocir_registry.sh")"
   OCIR_USERNAME="${OCIR_USERNAME:-$("$OCI_AGENT_PYTHON" "$TOOL_HOME/scripts/tool_config.py" env --keys OCIR_USERNAME | sed -n 's/^OCIR_USERNAME=//p')}"
   printf 'docker login --username %q %q\n' "$OCIR_USERNAME" "$OCIR_REGISTRY"
   ```

   Show the printed complete command with the resolved registry and username
   filled in, then let the operator run it. The username is not secret. The
   operator enters an OCI auth token only at Docker's password prompt. Check
   that a Docker credential helper is configured or warn that Docker may store
   credentials in its config file.
6. Before `docker tag` or `docker push`, identify the target repository and IAM
   prerequisite, show the planned remote mutation, and obtain explicit user
   authorization. Do not infer permission from configured credentials.
7. After authorization, run the guarded helper, which tags the local image and
   pushes the fully qualified target:

   ```bash
   "$TOOL_HOME/scripts/push_ocir_image.sh" --push --manifest /path/to/agent/agent.yaml --tag 0.1.0
   ```
   Report the source, target, exit code, and digest the container engine
   reports. Stop on failure; do not retry a push without direction.
8. State that a push does not verify hosted deployment compatibility. Offer
   `docker logout "$OCIR_REGISTRY"` as optional local credential cleanup; token
   revocation is a separate OCI Console/IAM action.

## Limitations

This skill supports only OC1 endpoints derived from an OCI region identifier.
It does not alter IAM policies, manage auth tokens, sign images, run CI, or
deploy OCI resources. A successful push is remote registry evidence only, not
deployment evidence.

## Exit codes

| Code | Meaning and action |
| --- | --- |
| 0 | Plan completed, or the authorized push completed. |
| 1 | Python with PyYAML, Docker, OCI CLI, or an OCI operation is unavailable or failed. |
| 10 | The local image is unavailable or is not `linux/amd64`. |
| 64 | Invalid arguments, missing tenancy settings, or manifest errors (including paths outside allowed roots); correct the input. |
| 65 | The configured OCI region is not available to the OCI CLI profile. |
