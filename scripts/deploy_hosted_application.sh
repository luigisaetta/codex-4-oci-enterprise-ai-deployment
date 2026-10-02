#!/usr/bin/env bash
#
# Plan or release a manifest-defined OCI Generative AI Hosted Application image.
#
# Prerequisites: Bash 3.2+, OCI CLI authentication, and Python with PyYAML.
# Tenancy settings are read from OCI_AGENT_ENV_FILE (default: <tool home>/.env)
# or from the environment.
# Inputs: --manifest PATH --tag MAJOR.MINOR.PATCH; --timeout-seconds 1800 by default;
# --replace-failed selects only a FAILED deployment; --apply authorizes mutations.
# Side effects: plans read OCI only. Applies create missing resources, or add and
# activate artifacts in place, or explicitly replace a FAILED deployment.
# OCI_DEPLOY_POLL_INTERVAL sets polling seconds (default 30; intended for offline tests).
# Exit codes: 0 success, 1 OCI or tool failure, 20 state requiring review,
# 26 still in progress, 64 invalid input, 65 OCI region not found.

set -euo pipefail

readonly EXIT_INVALID_INPUT=64
readonly EXIT_EXISTING_RESOURCE=20
readonly WAIT_SECONDS=1200
timeout_seconds=1800
poll_interval="${OCI_DEPLOY_POLL_INTERVAL:-30}"
replace_failed=false
readonly ARTIFACT_LIMIT=20
apply_changes=false
manifest=""
tag=""
script_directory="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$script_directory/lib/tool_env.sh"
. "$script_directory/lib/deploy_wait.sh"

# Print command-line usage.
usage() {
  printf 'Usage: %s [--plan|--apply] --manifest PATH --tag MAJOR.MINOR.PATCH [--timeout-seconds SECONDS] [--replace-failed]\n' "$0"
}

# Stop when a required setting is absent.
require_environment_variable() {
  local variable_name="$1"

  if [[ -z "${!variable_name:-}" ]]; then
    printf 'Missing required environment variable: %s\n' "$variable_name" >&2
    exit "$EXIT_INVALID_INPUT"
  fi
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
from datetime import datetime, timezone
created = data.get("time-created", "")
try:
    age = max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(created.replace("Z", "+00:00"))).total_seconds()))
    print("{}s".format(age))
except (ValueError, TypeError):
    print("unknown")
'  "$container_uri" "$tag")"
  deployment_state="$(printf '%s\n' "$deployment_details" | sed -n '1p')"
  active_tag="$(printf '%s\n' "$deployment_details" | sed -n '2p')"
  artifact_count="$(printf '%s\n' "$deployment_details" | sed -n '3p')"
  target_status="$(printf '%s\n' "$deployment_details" | sed -n '4p')"
  deployment_age="$(printf '%s\n' "$deployment_details" | sed -n '5p')"
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
  if [[ "$release_case" == 'Creation in progress' || "$release_case" == 'Application creation in progress' ]]; then
    printf '%s: %s (CREATING; age %s).\n' "$resource_kind" "$resource_id" "$resource_age"
    if [[ "$release_case" == 'Application creation in progress' ]]; then
      printf 'Create Hosted Deployment with tag: %s\n' "$tag"
    fi
  elif [[ "$release_case" == 'Failed deployment' || "$release_case" == 'Replace failed deployment' ]]; then
    printf 'Failed Hosted Deployment: %s\n%s\n' "$deployment_id" "$failure_reason"
    if [[ "$release_case" == 'Failed deployment' ]]; then
      printf 'Request replacement with --replace-failed (Bash) or -ReplaceFailed (PowerShell).\n'
    else
      printf 'Delete FAILED Hosted Deployment: %s\nCreate Hosted Deployment with tag: %s\n' "$deployment_id" "$tag"
    fi
  fi
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

# Check that an ACTIVE application still matches the manifest before reusing it.
check_application_configuration() {
  local current_json="$1"
  if ! printf '%s' "$current_json" | "$OCI_AGENT_PYTHON" \
    "$script_directory/agent_manifest.py" inbound-auth-matches --manifest "$manifest"; then
    printf '%s%s\n' \
      'The existing Hosted Application uses a different inbound authentication; ' \
      'changing authentication is not supported.' >&2
    exit "$EXIT_EXISTING_RESOURCE"
  fi
  if ! printf '%s' "$current_json" | "$OCI_AGENT_PYTHON" \
    "$script_directory/agent_manifest.py" runtime-matches --manifest "$manifest"; then
    printf '%s\n' 'Existing Hosted Application runtime environment differs from the manifest.' >&2
    exit "$EXIT_EXISTING_RESOURCE"
  fi
}

# Resolve an accepted mutation without exposing its raw CLI output.
resolve_mutation_id() {
  local kind="$1" response="$2" resolved
  resolved="$(parse_mutation_id "$response")"
  if [[ -z "$resolved" ]]; then
    resolved="$(lookup_mutated_resource "$kind")" || {
      printf '%s create/delete response had no data.id and lookup found no unique resource. Check OCI before retrying.\n' "$kind" >&2
      exit 1
    }
  fi
  printf '%s' "$resolved"
}

# Keep a mutation's JSON stdout separate from its diagnostic stderr.
invoke_mutation() {
  local error_file status
  error_file="$(mktemp)" || return 1
  mutation_output="$("$@" 2>"$error_file")" && status=0 || status=$?
  mutation_error="$(cat "$error_file")"
  rm -f "$error_file"
  return "$status"
}

create_hosted_application() {
  local application_output
  printf 'Creating Hosted Application with %s and Oracle-managed networking.\n' "$profile"
  if ! invoke_mutation oci --region "$OCI_REGION" --output json generative-ai \
    hosted-application create --display-name "$application_name" \
    --compartment-id "$compartment_id" --inbound-auth-config "$inbound_auth_json" \
    --networking-config '{"inboundNetworkingConfig":{"endpointMode":"PUBLIC"},'\
'"outboundNetworkingConfig":{"networkMode":"MANAGED"}}' \
    --environment-variables "$environment_variables_json"; then
    report_service_error 'Hosted Application create' "$mutation_error"
    exit 1
  fi
  application_output="$mutation_output"
  application_id="$(resolve_mutation_id 'Hosted Application' "$application_output")"
  application_work_request_id="$(parse_mutation_work_request "$application_output")"
  printf 'Created Hosted Application: %s\n' "$application_id"
  wait_for_resource 'Hosted Application' "$application_id" create || exit $?
}

create_first_release() {
  local deployment_output
  if [[ -z "$application_id" ]]; then
    create_hosted_application
  else
    printf 'Reusing ACTIVE Hosted Application: %s\n' "$application_id"
  fi
  printf '%s\n' 'Creating Hosted Deployment from the selected OCIR artifact.'
  if ! invoke_mutation oci --region "$OCI_REGION" --output json generative-ai \
    hosted-deployment create-hosted-deployment-single-docker-artifact \
    --hosted-application-id "$application_id" \
    --active-artifact-container-uri "$container_uri" --active-artifact-tag "$tag" \
    --compartment-id "$compartment_id"; then
    report_service_error 'Hosted Deployment create' "$mutation_error"
    exit 1
  fi
  deployment_output="$mutation_output"
  deployment_id="$(resolve_mutation_id 'Hosted Deployment' "$deployment_output")"
  deployment_work_request_id="$(parse_mutation_work_request "$deployment_output")"
  printf 'Created Hosted Deployment: %s\n' "$deployment_id"
  wait_for_resource 'Hosted Deployment' "$deployment_id" create || exit $?
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
    --replace-failed)
      replace_failed=true
      shift
      ;;
    --manifest|--tag|--timeout-seconds)
      option="$1"
      shift
      if [[ $# -eq 0 || -z "$1" || "$1" == --* ]]; then
        usage >&2
        exit "$EXIT_INVALID_INPUT"
      fi
      case "$option" in
        --manifest) manifest="$1" ;;
        --tag) tag="$1" ;;
        --timeout-seconds) timeout_seconds="$1" ;;
      esac
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

if ! [[ "$timeout_seconds" =~ ^[0-9]+$ ]] || [[ "$timeout_seconds" =~ ^0+$ ]] || \
    ! [[ "$poll_interval" =~ ^[0-9]+$ ]] || [[ "$poll_interval" =~ ^0+$ ]]; then
  printf 'Timeout and polling interval must be positive integers.\n' >&2
  exit "$EXIT_INVALID_INPUT"
fi
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
export OCI_DEPLOY_RUNTIME_JSON="$environment_variables_json"
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
  application_age="$(printf '%s' "$application_json" | "$OCI_AGENT_PYTHON" -c '
import json,sys
from datetime import datetime,timezone
created=(json.load(sys.stdin).get("data") or {}).get("time-created", "")
try:
 print("{}s".format(max(0,int((datetime.now(timezone.utc)-datetime.fromisoformat(created.replace("Z","+00:00"))).total_seconds()))))
except (ValueError,TypeError):
 print("unknown")
')"
  if "$replace_failed" && [[ "$application_state" != 'ACTIVE' ]]; then
    printf '%s\n' '--replace-failed requires a FAILED deployment.' >&2
    exit "$EXIT_INVALID_INPUT"
  fi
  if [[ "$application_state" != 'ACTIVE' && "$application_state" != 'CREATING' ]]; then
    printf 'Existing Hosted Application must be ACTIVE to reuse; observed: %s.\n' \
      "$application_state" >&2
    exit "$EXIT_EXISTING_RESOURCE"
  fi
  if [[ "$application_state" == 'ACTIVE' ]]; then
    check_application_configuration "$application_json"
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
  if [[ "$application_state" == 'CREATING' && "$deployment_count" != '0' ]]; then
    printf '%s\n' 'A CREATING Hosted Application already has a deployment; check it before completing the first release.' >&2
    exit "$EXIT_EXISTING_RESOURCE"
  fi
  if [[ "$deployment_count" == '1' ]]; then
    deployment_id="$(oci --region "$OCI_REGION" generative-ai \
      hosted-deployment-collection list-hosted-deployments \
      --compartment-id "$compartment_id" --application-id "$application_id" --all \
      --query "(${non_deleted_query})[0].id" --raw-output)"
    read_deployment_details
    if "$replace_failed" && [[ "$deployment_state" != 'FAILED' ]]; then
      printf '%s\n' '--replace-failed requires a FAILED deployment.' >&2
      exit "$EXIT_INVALID_INPUT"
    fi
    if [[ "$deployment_state" != 'ACTIVE' && "$deployment_state" != 'CREATING' && "$deployment_state" != 'FAILED' ]]; then
      printf 'Hosted Deployment must be ACTIVE; observed: %s. Check it and retry.\n' \
        "$deployment_state" >&2
      exit "$EXIT_EXISTING_RESOURCE"
    fi
    if [[ "$deployment_state" == 'CREATING' ]]; then
      release_case='Creation in progress'
    elif [[ "$deployment_state" == 'FAILED' ]]; then
      release_case='Failed deployment'
      if "$replace_failed"; then release_case='Replace failed deployment'; fi
      failure_reason="$(report_work_request_errors "$deployment_id" 2>&1)"
    elif [[ "$target_status" == 'FAILED'  || "$target_status" == 'UPDATING' ]]; then
      printf 'Target artifact tag %s is %s. Check it and retry; no changes were made.\n' \
        "$tag" "$target_status" >&2
      exit "$EXIT_EXISTING_RESOURCE"
    fi
    if [[ "$deployment_state" == 'ACTIVE' && "$active_tag" == "$tag" ]]; then
      release_case='Already released'
    elif [[ "$deployment_state" == 'ACTIVE' && -z "$target_status" ]]; then
      if [[ "$artifact_count" -ge "$ARTIFACT_LIMIT" ]]; then
        printf 'Adding tag %s exceeds the artifact limit of %s; no changes were made.\n' \
          "$tag" "$ARTIFACT_LIMIT" >&2
        exit "$EXIT_EXISTING_RESOURCE"
      fi
      release_case='New version'
    elif [[ "$deployment_state" == 'ACTIVE' && "$target_status" == 'INACTIVE' ]]; then
      release_case='Return to a previous version'
    elif [[ "$deployment_state" == 'ACTIVE' ]]; then
      printf 'Target artifact tag %s has unsupported status: %s.\n' \
        "$tag" "$target_status" >&2
      exit "$EXIT_EXISTING_RESOURCE"
    fi
  fi
fi
if "$replace_failed" && [[ "$release_case" != 'Replace failed deployment' ]]; then
  printf '%s\n' '--replace-failed requires a FAILED deployment.' >&2
  exit "$EXIT_INVALID_INPUT"
fi
if [[ "${application_state:-}" == 'CREATING' ]]; then
  release_case='Application creation in progress'
  resource_kind='Hosted Application'
  resource_id="$application_id"
  resource_age="$application_age"
elif [[ "$release_case" == 'Creation in progress' ]]; then
  resource_kind='Hosted Deployment'
  resource_id="$deployment_id"
  resource_age="$deployment_age"
fi

print_plan
if [[ "$apply_changes" == false ]]; then
  printf '%s\n' 'Plan complete. Re-run with --apply only after explicit authorization.'
  exit 0
fi

case "$release_case" in
  'Application creation in progress')
    wait_for_resource 'Hosted Application' "$application_id" create || exit $?
    application_json="$(oci --region "$OCI_REGION" --output json generative-ai \
      hosted-application get --hosted-application-id "$application_id")"
    check_application_configuration "$application_json"
    create_first_release
    ;;
  'Creation in progress')
    wait_for_resource "$resource_kind" "$resource_id" create || exit $?
    ;;
  'Failed deployment')
    exit "$EXIT_EXISTING_RESOURCE"
    ;;
  'Replace failed deployment')
    if ! invoke_mutation oci --region "$OCI_REGION" --output json generative-ai \
      hosted-deployment delete --hosted-deployment-id "$deployment_id" --force; then
      report_service_error 'Hosted Deployment delete' "$mutation_error"
      exit 1
    fi
    delete_output="$mutation_output"
    deleted_id="$(parse_mutation_id "$delete_output")"
    deletion_work_request_id="$(parse_mutation_work_request "$delete_output")"
    if [[ -z "$deleted_id" ]]; then
      deleted_id="$(lookup_mutated_resource 'Hosted Deployment')" || deleted_id=""
    fi
    if [[ -n "$deleted_id" && "$deleted_id" != "$deployment_id" ]]; then
      printf '%s\n' 'Delete response identifies a different deployment.' >&2; exit 1
    fi
    wait_for_resource 'Hosted Deployment' "$deployment_id" delete || exit $?
    create_first_release
    ;;
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
