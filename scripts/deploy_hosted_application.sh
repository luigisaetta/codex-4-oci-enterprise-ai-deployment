#!/usr/bin/env bash
#
# Plan or create a no-auth OCI Generative AI Hosted Application deployment.
#
# Prerequisites: Bash 3.2+, Docker, OCI CLI authentication, and the project
# Conda environment activated. Required environment variables are OCI_REGION,
# OCI_COMPARTMENT_NAME, OCIR_TENANCY_NAMESPACE, OCIR_REPOSITORY,
# OCI_HOSTED_APPLICATION_NAME, and OCI_HOSTED_DEPLOYMENT_NAME.
# Inputs: --image NAME:MAJOR.MINOR.PATCH; --apply authorizes remote creation.
# Side effects: without --apply this script performs OCI read operations only.
# With --apply, it creates a missing Hosted Application and Hosted Deployment.
# It never configures container environment variables, managed storage, custom
# networking, IAM, dynamic groups, endpoint authentication, or deletions.
# Usage: scripts/deploy_hosted_application.sh [--plan|--apply] --image NAME:TAG

set -euo pipefail

readonly EXIT_INVALID_INPUT=64
readonly EXIT_EXISTING_RESOURCE=20
readonly WAIT_SECONDS=1200

apply_changes=false
source_image=""

usage() {
  printf '%s\n' 'Usage: scripts/deploy_hosted_application.sh [--plan|--apply] --image NAME:MAJOR.MINOR.PATCH'
}

require_environment_variable() {
  local variable_name="$1"
  if [[ -z "${!variable_name:-}" ]]; then
    printf 'Missing required environment variable: %s\n' "$variable_name" >&2
    exit "$EXIT_INVALID_INPUT"
  fi
}

extract_expected_ocid() {
  local expected_prefix="$1"

  python -c '
import json
import sys

expected_prefix = sys.argv[1]
payload = json.load(sys.stdin)
matches = []

def walk(value):
    if isinstance(value, dict):
        for nested_value in value.values():
            walk(nested_value)
    elif isinstance(value, list):
        for nested_value in value:
            walk(nested_value)
    elif isinstance(value, str) and value.startswith(expected_prefix):
        matches.append(value)

walk(payload)
unique_matches = sorted(set(matches))
if len(unique_matches) != 1:
    raise SystemExit(
        "Expected exactly one OCID with prefix {} but found {}.".format(
            expected_prefix, len(unique_matches)
        )
    )
print(unique_matches[0])
' "$expected_prefix"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan)
      apply_changes=false
      ;;
    --apply)
      apply_changes=true
      ;;
    --image)
      shift
      if [[ $# -eq 0 ]]; then
        printf '%s\n' 'Missing image value after --image.' >&2
        exit "$EXIT_INVALID_INPUT"
      fi
      source_image="$1"
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

if [[ -z "$source_image" || "$source_image" != *:* ]]; then
  printf '%s\n' 'Provide --image NAME:MAJOR.MINOR.PATCH.' >&2
  exit "$EXIT_INVALID_INPUT"
fi

image_tag="${source_image##*:}"
if [[ ! "$image_tag" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]]; then
  printf 'Image tag must be semantic (MAJOR.MINOR.PATCH): %s\n' "$image_tag" >&2
  exit "$EXIT_INVALID_INPUT"
fi

if ! command -v oci >/dev/null 2>&1; then
  printf '%s\n' 'OCI CLI is not available in PATH. Activate the project Conda environment first.' >&2
  exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  printf '%s\n' 'Docker is not available in PATH.' >&2
  exit 1
fi
if ! command -v python >/dev/null 2>&1; then
  printf '%s\n' 'Python is not available in PATH. Activate the project Conda environment first.' >&2
  exit 1
fi

for setting_name in OCI_REGION OCI_COMPARTMENT_NAME OCIR_TENANCY_NAMESPACE OCIR_REPOSITORY OCI_HOSTED_APPLICATION_NAME OCI_HOSTED_DEPLOYMENT_NAME; do
  require_environment_variable "$setting_name"
done

script_directory="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
registry_resolver="${script_directory}/resolve_ocir_registry.sh"
if [[ ! -x "$registry_resolver" ]]; then
  printf 'Registry resolver is unavailable: %s\n' "$registry_resolver" >&2
  exit 1
fi
ocir_registry="$("$registry_resolver")"

image_platform="$(docker image inspect "$source_image" --format '{{.Os}}/{{.Architecture}}')"
if [[ "$image_platform" != 'linux/amd64' ]]; then
  printf 'Image platform must be linux/amd64; found %s.\n' "$image_platform" >&2
  exit 10
fi

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
  --query "(${active_compartment_query})[0].id" \
  --raw-output)"

non_deleted_application_query='data.items[?"lifecycle-state"!=`DELETED`]'
application_count="$(oci --region "$OCI_REGION" generative-ai hosted-application-collection list-hosted-applications \
  --compartment-id "$compartment_id" \
  --display-name "$OCI_HOSTED_APPLICATION_NAME" \
  --all \
  --query "length(${non_deleted_application_query})" \
  --raw-output)"

container_uri="${ocir_registry}/${OCIR_TENANCY_NAMESPACE}/${OCIR_REPOSITORY}"
printf 'Mode: %s\n' "$([[ "$apply_changes" == true ]] && printf 'apply' || printf 'plan')"
printf 'Source image: %s (%s)\n' "$source_image" "$image_platform"
printf 'OCIR artifact: %s:%s\n' "$container_uri" "$image_tag"
printf 'Compartment: %s\n' "$compartment_id"
printf 'Hosted Application: %s (NO_AUTH_CONFIG; PUBLIC; MANAGED)\n' "$OCI_HOSTED_APPLICATION_NAME"
printf 'Hosted Deployment: %s\n' "$OCI_HOSTED_DEPLOYMENT_NAME"
printf '%s\n' 'Container environment variables, managed storage, and custom networking are omitted.'
printf '%s\n' 'Prerequisite: the Hosted Deployment runtime must already be allowed to pull the private OCIR image.'

if [[ "$application_count" != '0' ]]; then
  printf 'Found %s non-deleted Hosted Application(s) named "%s".\n' \
    "$application_count" "$OCI_HOSTED_APPLICATION_NAME" >&2
  printf '%s\n' 'For safety, this script will not reuse or alter an existing application.' >&2
  exit "$EXIT_EXISTING_RESOURCE"
fi

if [[ "$apply_changes" == false ]]; then
  printf '%s\n' 'Plan complete. Re-run with --apply only after explicit authorization.'
  exit 0
fi

printf '%s\n' 'Creating Hosted Application with NO_AUTH_CONFIG and Oracle-managed networking.'
application_output="$(oci --region "$OCI_REGION" --output json generative-ai hosted-application create \
  --display-name "$OCI_HOSTED_APPLICATION_NAME" \
  --compartment-id "$compartment_id" \
  --inbound-auth-config '{"inboundAuthConfigType":"NO_AUTH_CONFIG"}' \
  --networking-config '{"inboundNetworkingConfig":{"endpointMode":"PUBLIC"},"outboundNetworkingConfig":{"networkMode":"MANAGED"}}' \
  --wait-for-state SUCCEEDED \
  --max-wait-seconds "$WAIT_SECONDS")"
application_id="$(printf '%s' "$application_output" | extract_expected_ocid 'ocid1.generativeaihostedapplication.')"
printf 'Created Hosted Application: %s\n' "$application_id"

printf '%s\n' 'Creating Hosted Deployment from the selected OCIR artifact.'
deployment_output="$(oci --region "$OCI_REGION" --output json generative-ai hosted-deployment create-hosted-deployment-single-docker-artifact \
  --hosted-application-id "$application_id" \
  --active-artifact-container-uri "$container_uri" \
  --active-artifact-tag "$image_tag" \
  --display-name "$OCI_HOSTED_DEPLOYMENT_NAME" \
  --compartment-id "$compartment_id" \
  --wait-for-state SUCCEEDED \
  --max-wait-seconds "$WAIT_SECONDS")"
deployment_id="$(printf '%s' "$deployment_output" | extract_expected_ocid 'ocid1.generativeaihosteddeployment.')"
printf 'Created Hosted Deployment: %s\n' "$deployment_id"
