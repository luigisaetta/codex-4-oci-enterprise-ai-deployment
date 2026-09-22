#!/usr/bin/env bash
#
# Ensure that an OCIR container repository exists.
#
# Prerequisites: Bash 3.2+, OCI CLI authentication, and the non-secret
# OCI_REGION, OCI_COMPARTMENT_NAME, and OCIR_REPOSITORY environment variables.
# Inputs: --create authorizes creation when the repository is absent.
# Side effects: without --create this script only reads OCI metadata. With
# --create it creates one private, mutable OCIR repository in the resolved
# compartment. It never performs a Docker login or push.
# Usage: scripts/ensure_ocir_repository.sh [--create]

set -euo pipefail

readonly EXIT_MISSING_REPOSITORY=20
readonly EXIT_INVALID_INPUT=64

create_repository=false

usage() {
  printf '%s\n' 'Usage: scripts/ensure_ocir_repository.sh [--create]'
  printf '%s\n' 'Check an OCIR repository; --create creates it if it is absent.'
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
    --create)
      create_repository=true
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit "$EXIT_INVALID_INPUT"
      ;;
  esac
  shift
done

if ! command -v oci >/dev/null 2>&1; then
  printf '%s\n' 'OCI CLI is not available in PATH. Activate the project Conda environment first.' >&2
  exit 1
fi

require_environment_variable 'OCI_REGION'
require_environment_variable 'OCI_COMPARTMENT_NAME'
require_environment_variable 'OCIR_REPOSITORY'

active_compartment_query='data[?"lifecycle-state"==`ACTIVE`]'
compartment_count="$(oci --region "$OCI_REGION" iam compartment list \
  --name "$OCI_COMPARTMENT_NAME" \
  --compartment-id-in-subtree true \
  --all \
  --query "length(${active_compartment_query})" \
  --raw-output)"

if [[ "$compartment_count" != '1' ]]; then
  printf 'Expected exactly one active compartment named "%s"; found %s.\n' \
    "$OCI_COMPARTMENT_NAME" "$compartment_count" >&2
  exit 1
fi

compartment_id="$(oci --region "$OCI_REGION" iam compartment list \
  --name "$OCI_COMPARTMENT_NAME" \
  --compartment-id-in-subtree true \
  --all \
  --query "${active_compartment_query}[0].id" \
  --raw-output)"

repository_count="$(oci --region "$OCI_REGION" artifacts container repository list \
  --compartment-id "$compartment_id" \
  --display-name "$OCIR_REPOSITORY" \
  --lifecycle-state AVAILABLE \
  --all \
  --query 'length(data)' \
  --raw-output)"

if [[ "$repository_count" == '1' ]]; then
  repository_id="$(oci --region "$OCI_REGION" artifacts container repository list \
    --compartment-id "$compartment_id" \
    --display-name "$OCIR_REPOSITORY" \
    --lifecycle-state AVAILABLE \
    --all \
    --query 'data[0].id' \
    --raw-output)"
  printf 'OCIR repository already exists: %s\n' "$repository_id"
  exit 0
fi

if [[ "$repository_count" != '0' ]]; then
  printf 'Expected zero or one available repository named "%s"; found %s.\n' \
    "$OCIR_REPOSITORY" "$repository_count" >&2
  exit 1
fi

if [[ "$create_repository" == false ]]; then
  printf 'OCIR repository "%s" is absent from compartment %s.\n' \
    "$OCIR_REPOSITORY" "$compartment_id" >&2
  printf 'Re-run with --create to create one private, mutable repository.\n' >&2
  exit "$EXIT_MISSING_REPOSITORY"
fi

printf 'Creating private, mutable OCIR repository "%s" in compartment %s.\n' \
  "$OCIR_REPOSITORY" "$compartment_id"
repository_id="$(oci --region "$OCI_REGION" artifacts container repository create \
  --compartment-id "$compartment_id" \
  --display-name "$OCIR_REPOSITORY" \
  --is-public false \
  --is-immutable false \
  --wait-for-state AVAILABLE \
  --max-wait-seconds 120 \
  --query 'data.id' \
  --raw-output)"
printf 'Created OCIR repository: %s\n' "$repository_id"
