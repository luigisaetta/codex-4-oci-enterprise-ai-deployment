#!/usr/bin/env bash
#
# Plan or create a manifest-defined OCI Generative AI Hosted Application release.
#
# Prerequisites: Bash 3.2+, OCI CLI authentication, Python with PyYAML,
# and OCI_REGION, OCI_COMPARTMENT_NAME, and OCIR_TENANCY_NAMESPACE exported.
# Inputs: --manifest PATH --tag MAJOR.MINOR.PATCH; --apply authorizes creation.
# Side effects: without --apply, OCI reads only. With --apply, creates a missing
# public no-auth application or a missing derived deployment; it never updates or deletes.

set -euo pipefail

readonly EXIT_INVALID_INPUT=64
readonly EXIT_EXISTING_RESOURCE=20
readonly WAIT_SECONDS=1200
apply_changes=false
manifest=""
tag=""

usage() { printf '%s\n' 'Usage: scripts/deploy_hosted_application.sh [--plan|--apply] --manifest PATH --tag MAJOR.MINOR.PATCH'; }

require_environment_variable() {
  local variable_name="$1"
  if [[ -z "${!variable_name:-}" ]]; then printf 'Missing required environment variable: %s\n' "$variable_name" >&2; exit "$EXIT_INVALID_INPUT"; fi
}

extract_expected_ocid() {
  local expected_prefix="$1"
  python -c '
import json
import sys
prefix = sys.argv[1]
matches = []
def walk(value):
    if isinstance(value, dict):
        for nested in value.values(): walk(nested)
    elif isinstance(value, list):
        for nested in value: walk(nested)
    elif isinstance(value, str) and value.startswith(prefix): matches.append(value)
walk(json.load(sys.stdin))
matches = sorted(set(matches))
if len(matches) != 1: raise SystemExit("Expected exactly one OCID with prefix {} but found {}.".format(prefix, len(matches)))
print(matches[0])
' "$expected_prefix"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan) apply_changes=false; shift ;;
    --apply) apply_changes=true; shift ;;
    --manifest|--tag)
      option="$1"; shift
      if [[ $# -eq 0 || -z "$1" || "$1" == --* ]]; then usage >&2; exit "$EXIT_INVALID_INPUT"; fi
      if [[ "$option" == '--manifest' ]]; then manifest="$1"; else tag="$1"; fi
      shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit "$EXIT_INVALID_INPUT" ;;
  esac
done
if [[ -z "$manifest" || -z "$tag" ]]; then usage >&2; exit "$EXIT_INVALID_INPUT"; fi
for required_tool in oci python; do
  if ! command -v "$required_tool" >/dev/null 2>&1; then printf 'Missing required tool: %s\n' "$required_tool" >&2; exit 1; fi
done
for setting_name in OCI_REGION OCI_COMPARTMENT_NAME OCIR_TENANCY_NAMESPACE; do require_environment_variable "$setting_name"; done

script_directory="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repository="$(python "$script_directory/agent_manifest.py" get --manifest "$manifest" --field publish.repository)"
application_name="$(python "$script_directory/agent_manifest.py" get --manifest "$manifest" --field deploy.application_name)"
profile="$(python "$script_directory/agent_manifest.py" get --manifest "$manifest" --field deploy.profile)"
deployment_name="$(python "$script_directory/agent_manifest.py" deployment-name --manifest "$manifest" --tag "$tag")"
ocir_registry="$("$script_directory/resolve_ocir_registry.sh")"
active_compartment_query='data[?"lifecycle-state"==`ACTIVE`]'
compartment_count="$(oci --region "$OCI_REGION" iam compartment list --name "$OCI_COMPARTMENT_NAME" --compartment-id-in-subtree true --all --query "length(${active_compartment_query})" --raw-output)"
if [[ "$compartment_count" != '1' ]]; then printf 'Expected exactly one active compartment named "%s"; found %s.\n' "$OCI_COMPARTMENT_NAME" "$compartment_count" >&2; exit 1; fi
compartment_id="$(oci --region "$OCI_REGION" iam compartment list --name "$OCI_COMPARTMENT_NAME" --compartment-id-in-subtree true --all --query "(${active_compartment_query})[0].id" --raw-output)"
non_deleted_application_query='data.items[?"lifecycle-state"!=`DELETED`]'
application_count="$(oci --region "$OCI_REGION" generative-ai hosted-application-collection list-hosted-applications --compartment-id "$compartment_id" --display-name "$application_name" --all --query "length(${non_deleted_application_query})" --raw-output)"
if [[ "$application_count" != '0' && "$application_count" != '1' ]]; then printf 'Expected zero or one non-deleted Hosted Application named "%s"; found %s.\n' "$application_name" "$application_count" >&2; exit "$EXIT_EXISTING_RESOURCE"; fi
container_uri="${ocir_registry}/${OCIR_TENANCY_NAMESPACE}/${repository}"
application_id=""
if [[ "$application_count" == '1' ]]; then
  application_id="$(oci --region "$OCI_REGION" generative-ai hosted-application-collection list-hosted-applications --compartment-id "$compartment_id" --display-name "$application_name" --all --query "(${non_deleted_application_query})[0].id" --raw-output)"
  application_state="$(oci --region "$OCI_REGION" generative-ai hosted-application get --hosted-application-id "$application_id" --query 'data."lifecycle-state"' --raw-output)"
  if [[ "$application_state" != 'ACTIVE' ]]; then printf 'Existing Hosted Application must be ACTIVE to reuse; observed: %s.\n' "$application_state" >&2; exit "$EXIT_EXISTING_RESOURCE"; fi
fi
deployment_count="0"
if [[ -n "$application_id" ]]; then
  deployment_query="data.items[?\"display-name\"==\`${deployment_name}\` && \"lifecycle-state\"!=\`DELETED\`]"
  deployment_count="$(oci --region "$OCI_REGION" generative-ai hosted-deployment-collection list-hosted-deployments --compartment-id "$compartment_id" --application-id "$application_id" --all --query "length(${deployment_query})" --raw-output)"
fi
printf 'Mode: %s\n' "$([[ "$apply_changes" == true ]] && printf apply || printf plan)"
printf 'OCIR artifact: %s:%s\n' "$container_uri" "$tag"
printf 'Compartment: %s\n' "$compartment_id"
printf 'Hosted Application: %s (%s; %s)\n' "$application_name" "$profile" "$([[ -n "$application_id" ]] && printf reuse || printf create)"
printf 'Hosted Deployment: %s\n' "$deployment_name"
printf '%s\n' 'Container environment variables, managed storage, and custom networking are omitted.'
if [[ "$deployment_count" != '0' ]]; then printf 'A non-deleted Hosted Deployment named "%s" already exists; it will not be replaced.\n' "$deployment_name" >&2; exit "$EXIT_EXISTING_RESOURCE"; fi
if [[ "$apply_changes" == false ]]; then printf '%s\n' 'Plan complete. Re-run with --apply only after explicit authorization.'; exit 0; fi
if [[ -z "$application_id" ]]; then
  printf '%s\n' 'Creating Hosted Application with NO_AUTH_CONFIG and Oracle-managed networking.'
  application_output="$(oci --region "$OCI_REGION" --output json generative-ai hosted-application create --display-name "$application_name" --compartment-id "$compartment_id" --inbound-auth-config '{"inboundAuthConfigType":"NO_AUTH_CONFIG"}' --networking-config '{"inboundNetworkingConfig":{"endpointMode":"PUBLIC"},"outboundNetworkingConfig":{"networkMode":"MANAGED"}}' --wait-for-state SUCCEEDED --max-wait-seconds "$WAIT_SECONDS")"
  application_id="$(printf '%s' "$application_output" | extract_expected_ocid 'ocid1.generativeaihostedapplication.')"
  printf 'Created Hosted Application: %s\n' "$application_id"
else
  printf 'Reusing ACTIVE Hosted Application: %s\n' "$application_id"
fi
printf '%s\n' 'Creating Hosted Deployment from the selected OCIR artifact.'
deployment_output="$(oci --region "$OCI_REGION" --output json generative-ai hosted-deployment create-hosted-deployment-single-docker-artifact --hosted-application-id "$application_id" --active-artifact-container-uri "$container_uri" --active-artifact-tag "$tag" --display-name "$deployment_name" --compartment-id "$compartment_id" --wait-for-state SUCCEEDED --max-wait-seconds "$WAIT_SECONDS")"
deployment_id="$(printf '%s' "$deployment_output" | extract_expected_ocid 'ocid1.generativeaihosteddeployment.')"
printf 'Created Hosted Deployment: %s\n' "$deployment_id"
