#!/usr/bin/env bash
#
# Resolve a supported OCI region identifier to its OCIR region-key endpoint.
#
# Prerequisites: Bash 3.2+ and OCI_REGION in the environment.
# Inputs: no positional arguments.
# Side effects: none.
# Usage: scripts/resolve_ocir_registry.sh

set -euo pipefail

readonly EXIT_INVALID_INPUT=64

if [[ $# -ne 0 ]]; then
  printf '%s\n' 'Usage: scripts/resolve_ocir_registry.sh' >&2
  exit "$EXIT_INVALID_INPUT"
fi

if [[ -z "${OCI_REGION:-}" ]]; then
  printf '%s\n' 'Missing required environment variable: OCI_REGION' >&2
  exit "$EXIT_INVALID_INPUT"
fi

case "$OCI_REGION" in
  eu-frankfurt-1)
    printf '%s\n' 'fra.ocir.io'
    ;;
  us-chicago-1)
    printf '%s\n' 'ord.ocir.io'
    ;;
  *)
    printf 'Unsupported OCI_REGION for OCIR region-key resolution: %s\n' \
      "$OCI_REGION" >&2
    printf '%s\n' 'Supported values: eu-frankfurt-1, us-chicago-1' >&2
    exit "$EXIT_INVALID_INPUT"
    ;;
esac
