#!/usr/bin/env bash
#
# Resolve an OC1 OCI region identifier to its OCIR region-key endpoint.
#
# Prerequisites: Bash 3.2+, OCI CLI authentication, and OCI_REGION in the
# environment. The configured OCI CLI profile must be able to list regions.
# Inputs: no positional arguments.
# Side effects: none.
# Usage: scripts/resolve_ocir_registry.sh

set -euo pipefail

readonly EXIT_INVALID_INPUT=64
readonly EXIT_REGION_NOT_FOUND=65

if [[ $# -ne 0 ]]; then
  printf '%s\n' 'Usage: scripts/resolve_ocir_registry.sh' >&2
  exit "$EXIT_INVALID_INPUT"
fi

if [[ -z "${OCI_REGION:-}" ]]; then
  printf '%s\n' 'Missing required environment variable: OCI_REGION' >&2
  exit "$EXIT_INVALID_INPUT"
fi

if [[ ! "$OCI_REGION" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
  printf 'Invalid OCI_REGION value: %s\n' "$OCI_REGION" >&2
  exit "$EXIT_INVALID_INPUT"
fi

if ! region_key="$(oci iam region list --all \
  --query "data[?name=='${OCI_REGION}'].key | [0]" \
  --raw-output)"; then
  printf '%s\n' 'Unable to list OCI regions with the configured OCI CLI profile.' >&2
  exit 1
fi

if [[ -z "$region_key" || "$region_key" == "null" ]]; then
  printf 'OCI_REGION was not found by the configured OCI CLI profile: %s\n' \
    "$OCI_REGION" >&2
  exit "$EXIT_REGION_NOT_FOUND"
fi

if [[ ! "$region_key" =~ ^[A-Za-z0-9]+$ ]]; then
  printf 'OCI CLI returned an invalid region key for OCI_REGION %s.\n' \
    "$OCI_REGION" >&2
  exit 1
fi

printf '%s.ocir.io\n' "$(printf '%s' "$region_key" | tr '[:upper:]' '[:lower:]')"
