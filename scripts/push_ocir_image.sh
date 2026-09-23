#!/usr/bin/env bash
#
# Plan or push a manifest-defined local image to OCIR.
#
# Prerequisites: Bash 3.2+, Docker, OCI CLI authentication, Python with PyYAML,
# and exported OCI_REGION, OCIR_TENANCY_NAMESPACE, and OCIR_USERNAME values.
# Inputs: --manifest PATH --tag VERSION; --push authorizes Docker tag and push.
# Side effects: default mode is local Docker inspection only. --push creates a
# local tag and pushes it, but never creates an OCI repository.

set -euo pipefail

readonly EXIT_INVALID_INPUT=64
push_image=false
manifest=""
tag=""

usage() {
  printf '%s\n' 'Usage: scripts/push_ocir_image.sh [--plan|--push] --manifest PATH --tag MAJOR.MINOR.PATCH'
}

require_environment_variable() {
  local variable_name="$1"
  if [[ -z "${!variable_name:-}" ]]; then
    printf 'Missing required environment variable: %s\n' "$variable_name" >&2
    exit "$EXIT_INVALID_INPUT"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan) push_image=false; shift ;;
    --push) push_image=true; shift ;;
    --manifest|--tag)
      option="$1"
      shift
      if [[ $# -eq 0 || -z "$1" || "$1" == --* ]]; then usage >&2; exit "$EXIT_INVALID_INPUT"; fi
      if [[ "$option" == '--manifest' ]]; then manifest="$1"; else tag="$1"; fi
      shift
      ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit "$EXIT_INVALID_INPUT" ;;
  esac
done

if [[ -z "$manifest" || -z "$tag" ]]; then usage >&2; exit "$EXIT_INVALID_INPUT"; fi
for required_tool in docker oci python; do
  if ! command -v "$required_tool" >/dev/null 2>&1; then printf 'Missing required tool: %s\n' "$required_tool" >&2; exit 1; fi
done
for setting_name in OCI_REGION OCIR_TENANCY_NAMESPACE OCIR_USERNAME; do require_environment_variable "$setting_name"; done

script_directory="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
image_name="$(python "$script_directory/agent_manifest.py" get --manifest "$manifest" --field name)"
repository="$(python "$script_directory/agent_manifest.py" get --manifest "$manifest" --field publish.repository)"
python "$script_directory/agent_manifest.py" deployment-name --manifest "$manifest" --tag "$tag" >/dev/null
source_image="${image_name}:${tag}"
if ! image_platform="$(docker image inspect "$source_image" --format '{{.Os}}/{{.Architecture}}')"; then
  printf 'Local image is unavailable: %s\n' "$source_image" >&2; exit 10
fi
if [[ "$image_platform" != 'linux/amd64' ]]; then
  printf 'Image platform must be linux/amd64; found %s.\n' "$image_platform" >&2; exit 10
fi
ocir_registry="$("$script_directory/resolve_ocir_registry.sh")"
target_image="${ocir_registry}/${OCIR_TENANCY_NAMESPACE}/${repository}:${tag}"
printf 'Mode: %s\n' "$([[ "$push_image" == true ]] && printf push || printf plan)"
printf 'Source image: %s (%s)\n' "$source_image" "$image_platform"
printf 'OCIR target: %s\n' "$target_image"
printf 'Repository prerequisite: scripts/ensure_ocir_repository.sh --repository %s\n' "$repository"
if [[ "$push_image" == false ]]; then
  printf '%s\n' 'Plan complete. Authenticate with Docker and re-run with --push only after explicit authorization.'
  exit 0
fi
docker tag "$source_image" "$target_image"
docker push "$target_image"
printf 'Pushed OCIR artifact: %s\n' "$target_image"
