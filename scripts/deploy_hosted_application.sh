#!/usr/bin/env bash
#
# Plan or release a manifest-defined OCI Generative AI Hosted Application image.
#
# Prerequisites: Bash 3.2+, OCI CLI authentication, and Python with PyYAML.
# Tenancy settings are read from OCI_AGENT_ENV_FILE (default: <tool home>/.env)
# or from the environment.
# Inputs: --manifest PATH --tag MAJOR.MINOR.PATCH; --apply authorizes mutations.
# Side effects: plans read OCI only. Applies create missing resources, or add and
# activate artifacts in place. It never deletes or replaces resources.
# Exit codes: 0 success, 1 OCI or tool failure, 20 state requiring review,
# 64 invalid input, and 65 when the OCI region was not found.

set -euo pipefail

readonly EXIT_INVALID_INPUT=64
readonly EXIT_EXISTING_RESOURCE=20
readonly WAIT_SECONDS=1200
readonly ARTIFACT_LIMIT=20
apply_changes=false
manifest=""
tag=""
script_directory="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$script_directory/lib/tool_env.sh"

# Print command-line usage.
usage() {
  printf 'Usage: %s [--plan|--apply] --manifest PATH --tag MAJOR.MINOR.PATCH\n' "$0"
}

# Stop when a required setting is absent.
require_environment_variable() {
  local variable_name="$1"

  if [[ -z "${!variable_name:-}" ]]; then
    printf 'Missing required environment variable: %s\n' "$variable_name" >&2
    exit "$EXIT_INVALID_INPUT"
  fi
}

# Extract exactly one OCID with the requested prefix from OCI JSON output.
extract_expected_ocid() {
  local expected_prefix="$1"

  "$OCI_AGENT_PYTHON" -c '
import json
import sys

prefix = sys.argv[1]
matches = []

def walk(value):
    if isinstance(value, dict):
        for nested in value.values():
            walk(nested)
    elif isinstance(value, list):
        for nested in value:
            walk(nested)
    elif isinstance(value, str) and value.startswith(prefix):
        matches.append(value)

walk(json.load(sys.stdin))
matches = sorted(set(matches))
if len(matches) != 1:
    raise SystemExit("Expected exactly one matching OCID; found {}.".format(len(matches)))
print(matches[0])
' "$expected_prefix"
}

# Read lifecycle and artifact information from the selected deployment.
read_deployment_details() {
  local deployment_json

  deployment_json="$(oci --region "$OCI_REGION" --output json generative-ai \
    hosted-deployment get --hosted-deployment-id "$deployment_id")"
  deployment_details="$(printf '%s' "$deployment_json" | "$OCI_AGENT_PYTHON" -c '
import json
import sys

data = json.load(sys.stdin)["data"]
target_uri, target_tag = sys.argv[1:]
status = ""
for artifact in data.get("artifacts", []):
    if artifact.get("container-uri") == target_uri and artifact.get("tag") == target_tag:
        status = artifact.get("status", "")
        break
active = data.get("active-artifact") or {}
print(data.get("lifecycle-state", ""))
print(active.get("tag", ""))
print(len(data.get("artifacts", [])))
print(status)
' "$container_uri" "$tag")"
  deployment_state="$(printf '%s\n' "$deployment_details" | sed -n '1p')"
  active_tag="$(printf '%s\n' "$deployment_details" | sed -n '2p')"
  artifact_count="$(printf '%s\n' "$deployment_details" | sed -n '3p')"
  target_status="$(printf '%s\n' "$deployment_details" | sed -n '4p')"
}

# Print the release case and the OCI state that selected it.
print_plan() {
  local application_action

  application_action='create'
  if [[ -n "$application_id" ]]; then
    application_action='reuse'
  fi
  printf 'Mode: %s\n' "$(if "$apply_changes"; then printf apply; else printf plan; fi)"
  printf 'OCIR artifact: %s:%s\n' "$container_uri" "$tag"
  printf 'Compartment: %s\n' "$compartment_id"
  printf 'Hosted Application: %s (%s; %s)\n' \
    "$application_name" "$profile" "$application_action"
  if [[ "$profile" == 'public-idcs' ]]; then
    printf '%s\n' 'Access: public endpoint, identity-domain token required'
    printf 'Identity domain URL: %s\n' "$domain_url"
    printf 'Audience: %s\n' "$audience"
    printf 'Scope: %s\n' "$scope"
  else
    printf '%s\n' 'Access: public unauthenticated endpoint.'
  fi
  printf 'Release case: %s\n' "$release_case"
  printf 'Current active tag: %s\n' "$active_tag"
  printf 'Target tag: %s\n' "$tag"
  printf 'Artifacts: %s/%s\n' "$artifact_count" "$ARTIFACT_LIMIT"
  if [[ -n "$application_id" ]]; then
    printf 'Endpoint: unchanged for this application (%s).\n' "$application_id"
  fi
  if [[ -n "$environment_report" ]]; then
    printf '%s\n' "$environment_report"
  fi
  printf '%s\n' \
    'Container environment variables, managed storage, and custom networking are omitted.'
}

# Activate an existing artifact, wait for the work request, and confirm its tag.
activate_artifact() {
  local update_output
  local work_request_status

  # The skill plan and explicit --apply authorization cover this mutation.
  update_output="$(oci --region "$OCI_REGION" --output json generative-ai \
    hosted-deployment update --hosted-deployment-id "$deployment_id" \
    --active-artifact "$(printf \
      '{"artifactType":"SIMPLE_DOCKER_ARTIFACT","containerUri":"%s","tag":"%s"}' \
      "$container_uri" "$tag")" --wait-for-state SUCCEEDED --wait-for-state FAILED \
    --max-wait-seconds "$WAIT_SECONDS" --force)" || {
      printf '%s%s\n' 'Artifact activation failed: work-request status=unknown.' \
        ' See the OCI CLI error above.' >&2
      exit 1
    }
  work_request_status="$(printf '%s' "$update_output" | "$OCI_AGENT_PYTHON" -c '
import json
import sys
print(json.load(sys.stdin).get("data", {}).get("status", "unknown"))
')"
  read_deployment_details
  if [[ "$work_request_status" == 'FAILED' || "$active_tag" != "$tag" ]]; then
    printf 'Artifact activation failed: work-request status=%s; active tag=%s.\n' \
      "$work_request_status" "$active_tag" >&2
    exit 1
  fi
}

# Create the missing Hosted Application and report its identifier.
create_hosted_application() {
  local application_output

  printf 'Creating Hosted Application with %s and Oracle-managed networking.\n' \
    "$profile"
  application_output="$(oci --region "$OCI_REGION" --output json generative-ai \
    hosted-application create --display-name "$application_name" \
    --compartment-id "$compartment_id" \
    --inbound-auth-config "$inbound_auth_json" \
    --networking-config '{"inboundNetworkingConfig":{"endpointMode":"PUBLIC"},'\
'"outboundNetworkingConfig":{"networkMode":"MANAGED"}}' \
    --environment-variables "$environment_variables_json" --wait-for-state SUCCEEDED \
    --max-wait-seconds "$WAIT_SECONDS")"
  application_id="$(printf '%s' "$application_output" | \
    extract_expected_ocid 'ocid1.generativeaihostedapplication.')"
  printf 'Created Hosted Application: %s\n' "$application_id"
}

# Create the first deployment after creating or reusing its Hosted Application.
create_first_release() {
  local deployment_output

  if [[ -z "$application_id" ]]; then
    create_hosted_application
  else
    printf 'Reusing ACTIVE Hosted Application: %s\n' "$application_id"
  fi
  printf '%s\n' 'Creating Hosted Deployment from the selected OCIR artifact.'
  deployment_output="$(oci --region "$OCI_REGION" --output json generative-ai \
    hosted-deployment create-hosted-deployment-single-docker-artifact \
    --hosted-application-id "$application_id" \
    --active-artifact-container-uri "$container_uri" --active-artifact-tag "$tag" \
    --compartment-id "$compartment_id" --wait-for-state SUCCEEDED \
    --max-wait-seconds "$WAIT_SECONDS")"
  deployment_id="$(printf '%s' "$deployment_output" | \
    extract_expected_ocid 'ocid1.generativeaihosteddeployment.')"
  printf 'Created Hosted Deployment: %s\n' "$deployment_id"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan)
      apply_changes=false
      shift
      ;;
    --apply)
      apply_changes=true
      shift
      ;;
    --manifest|--tag)
      option="$1"
      shift
      if [[ $# -eq 0 || -z "$1" || "$1" == --* ]]; then
        usage >&2
        exit "$EXIT_INVALID_INPUT"
      fi
      if [[ "$option" == '--manifest' ]]; then
        manifest="$1"
      else
        tag="$1"
      fi
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit "$EXIT_INVALID_INPUT"
      ;;
  esac
done

resolve_python
load_tenancy_settings OCI_REGION OCI_COMPARTMENT_NAME OCIR_TENANCY_NAMESPACE
if [[ -z "$manifest" || -z "$tag" ]]; then
  usage >&2
  exit "$EXIT_INVALID_INPUT"
fi
# A SemVer core with optional Docker-compatible prerelease identifiers, no build metadata.
version_pattern='^(0|[1-9][0-9]*)\.'\
'(0|[1-9][0-9]*)\.'\
'(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$'
if ! [[ "$tag" =~ $version_pattern ]]; then
  printf 'Tag must be semantic (MAJOR.MINOR.PATCH).\n' >&2
  exit "$EXIT_INVALID_INPUT"
fi
if ! command -v oci >/dev/null 2>&1; then
  printf '%s\n' 'Missing required tool: oci' >&2
  exit 1
fi
for setting_name in OCI_REGION OCI_COMPARTMENT_NAME OCIR_TENANCY_NAMESPACE; do
  require_environment_variable "$setting_name"
done

repository="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" get \
  --manifest "$manifest" --field publish.repository)"
application_name="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" get \
  --manifest "$manifest" --field deploy.application_name)"
profile="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" get \
  --manifest "$manifest" --field deploy.profile)"
inbound_auth_json="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" \
  inbound-auth --manifest "$manifest")"
domain_url=""
audience=""
scope=""
if [[ "$profile" == 'public-idcs' ]]; then
  domain_url="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" get \
    --manifest "$manifest" --field deploy.auth.domain_url)"
  audience="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" get \
    --manifest "$manifest" --field deploy.auth.audience)"
  scope="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" get \
    --manifest "$manifest" --field deploy.auth.scope)"
fi
environment_variables_json="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" \
  runtime-env --manifest "$manifest" --format oci-json)"
environment_report="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" \
  runtime-env --manifest "$manifest" --format report)"
ocir_registry="$("$script_directory/resolve_ocir_registry.sh")"
container_uri="${ocir_registry}/${OCIR_TENANCY_NAMESPACE}/${repository}"

active_compartment_query='data[?"lifecycle-state"==`ACTIVE`]'
compartment_count="$(oci --region "$OCI_REGION" iam compartment list \
  --name "$OCI_COMPARTMENT_NAME" --compartment-id-in-subtree true --all \
  --query "length(${active_compartment_query})" --raw-output)"
if [[ "$compartment_count" != '1' ]]; then
  printf 'Expected exactly one active compartment named "%s"; found %s.\n' \
    "$OCI_COMPARTMENT_NAME" "$compartment_count" >&2
  exit 1
fi
compartment_id="$(oci --region "$OCI_REGION" iam compartment list \
  --name "$OCI_COMPARTMENT_NAME" --compartment-id-in-subtree true --all \
  --query "(${active_compartment_query})[0].id" --raw-output)"
non_deleted_query='data.items[?"lifecycle-state"!=`DELETED`]'
application_count="$(oci --region "$OCI_REGION" generative-ai \
  hosted-application-collection list-hosted-applications \
  --compartment-id "$compartment_id" --display-name "$application_name" --all \
  --query "length(${non_deleted_query})" --raw-output)"
if [[ "$application_count" != '0' && "$application_count" != '1' ]]; then
  printf 'Expected zero or one non-deleted Hosted Application named "%s"; found %s.\n' \
    "$application_name" "$application_count" >&2
  exit "$EXIT_EXISTING_RESOURCE"
fi

application_id=""
deployment_id=""
active_tag='none'
artifact_count=0
target_status=""
release_case='First release'
if [[ "$application_count" == '1' ]]; then
  application_id="$(oci --region "$OCI_REGION" generative-ai \
    hosted-application-collection list-hosted-applications \
    --compartment-id "$compartment_id" --display-name "$application_name" --all \
    --query "(${non_deleted_query})[0].id" --raw-output)"
  application_json="$(oci --region "$OCI_REGION" --output json generative-ai \
    hosted-application get --hosted-application-id "$application_id")"
  application_state="$(printf '%s' "$application_json" | "$OCI_AGENT_PYTHON" -c '
import json
import sys
print(json.load(sys.stdin)["data"].get("lifecycle-state", ""))
')"
  if [[ "$application_state" != 'ACTIVE' ]]; then
    printf 'Existing Hosted Application must be ACTIVE to reuse; observed: %s.\n' \
      "$application_state" >&2
    exit "$EXIT_EXISTING_RESOURCE"
  fi
  if ! printf '%s' "$application_json" | "$OCI_AGENT_PYTHON" \
    "$script_directory/agent_manifest.py" inbound-auth-matches --manifest "$manifest"; then
    printf '%s%s\n' \
      'The existing Hosted Application uses a different inbound authentication; ' \
      'changing authentication is not supported.' >&2
    exit "$EXIT_EXISTING_RESOURCE"
  fi
  if ! printf '%s' "$application_json" | "$OCI_AGENT_PYTHON" \
    "$script_directory/agent_manifest.py" runtime-matches --manifest "$manifest"; then
    printf '%s\n' 'Existing Hosted Application runtime environment differs from the manifest.' >&2
    exit "$EXIT_EXISTING_RESOURCE"
  fi
  deployment_count="$(oci --region "$OCI_REGION" generative-ai \
    hosted-deployment-collection list-hosted-deployments \
    --compartment-id "$compartment_id" --application-id "$application_id" --all \
    --query "length(${non_deleted_query})" --raw-output)"
  if [[ "$deployment_count" != '0' && "$deployment_count" != '1' ]]; then
    printf 'Expected zero or one non-deleted Hosted Deployment; found %s.\n' \
      "$deployment_count" >&2
    exit "$EXIT_EXISTING_RESOURCE"
  fi
  if [[ "$deployment_count" == '1' ]]; then
    deployment_id="$(oci --region "$OCI_REGION" generative-ai \
      hosted-deployment-collection list-hosted-deployments \
      --compartment-id "$compartment_id" --application-id "$application_id" --all \
      --query "(${non_deleted_query})[0].id" --raw-output)"
    read_deployment_details
    if [[ "$deployment_state" != 'ACTIVE' ]]; then
      printf 'Hosted Deployment must be ACTIVE; observed: %s. Check it and retry.\n' \
        "$deployment_state" >&2
      exit "$EXIT_EXISTING_RESOURCE"
    fi
    if [[ "$target_status" == 'FAILED' || "$target_status" == 'UPDATING' ]]; then
      printf 'Target artifact tag %s is %s. Check it and retry; no changes were made.\n' \
        "$tag" "$target_status" >&2
      exit "$EXIT_EXISTING_RESOURCE"
    fi
    if [[ "$active_tag" == "$tag" ]]; then
      release_case='Already released'
    elif [[ -z "$target_status" ]]; then
      if [[ "$artifact_count" -ge "$ARTIFACT_LIMIT" ]]; then
        printf 'Adding tag %s exceeds the artifact limit of %s; no changes were made.\n' \
          "$tag" "$ARTIFACT_LIMIT" >&2
        exit "$EXIT_EXISTING_RESOURCE"
      fi
      release_case='New version'
    elif [[ "$target_status" == 'INACTIVE' ]]; then
      release_case='Return to a previous version'
    else
      printf 'Target artifact tag %s has unsupported status: %s.\n' \
        "$tag" "$target_status" >&2
      exit "$EXIT_EXISTING_RESOURCE"
    fi
  fi
fi

print_plan
if [[ "$apply_changes" == false ]]; then
  printf '%s\n' 'Plan complete. Re-run with --apply only after explicit authorization.'
  exit 0
fi

case "$release_case" in
  'Already released')
    printf 'Tag %s is already active; no changes were made.\n' "$tag"
    ;;
  'First release')
    create_first_release
    ;;
  'New version')
    oci --region "$OCI_REGION" generative-ai hosted-deployment \
      add-artifact-create-single-docker-artifact-details \
      --hosted-deployment-id "$deployment_id" --artifact-container-uri "$container_uri" \
      --artifact-tag "$tag"
    activate_artifact
    ;;
  'Return to a previous version')
    activate_artifact
    ;;
esac
