#!/usr/bin/env bash
#
# Plan or apply the complete removal of one agent (Spec 029): its Hosted
# Application and deployment, its managed storage, its OCIR repository, and its
# local container images.
#
# Prerequisites: Bash 3.2+, Python with PyYAML, OCI CLI authentication, and the
# tool's tenancy settings (OCI_AGENT_ENV_FILE, default <tool home>/.env, or the
# environment). Docker or Podman only for the local images.
# Inputs: --manifest PATH [--plan|--apply --confirm APPLICATION_NAME]
# [--container-engine auto|docker|podman] [--timeout-seconds SECONDS].
# Side effects: --plan (default) reads OCI and lists local images only. --apply
# deletes the planned resources; it never touches IAM, Vault, identity domains,
# Generative AI projects, or the agent folder.
# Exit codes: 0 done or nothing to delete, 1 OCI or tool failure, 20 state
# requiring review, 26 still deleting, 64 invalid input, 65 region not found.
# The logic lives in teardown_agent.py, shared with teardown_agent.ps1.

set -euo pipefail

script_directory="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$script_directory/lib/tool_env.sh"

# Print command-line usage; the options are those of teardown_agent.py.
usage() {
  printf 'Usage: %s --manifest PATH [--plan|--apply --confirm APPLICATION_NAME] [--container-engine auto|docker|podman] [--timeout-seconds SECONDS]\n' "$0"
}

case "${1:-}" in
  --help|-h) usage; exit 0 ;;
esac
resolve_python || exit 1
exec "$OCI_AGENT_PYTHON" "$script_directory/teardown_agent.py" "$@"
