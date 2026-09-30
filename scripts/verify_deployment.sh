#!/usr/bin/env bash
#
# Verify an OCI Generative AI Hosted Application deployment through its public
# health and readiness endpoints. The script performs OCI and HTTP reads only.
#
# Prerequisites: Bash 3.2+, OCI CLI authentication, curl, OCI_REGION, an ACTIVE
# Hosted Application, and an ACTIVE Hosted Deployment with the expected tag.
# Inputs: --application-id OCID --manifest PATH --tag MAJOR.MINOR.PATCH, optional
# --timeout-seconds and --poll-seconds.
# Side effects: OCI CLI reads and unauthenticated GET requests to /health and
# /ready only. --functional additionally invokes manifest business paths.
# The timeout budget starts before deployment-state polling and is shared with
# subsequent health, readiness, and optional functional probes.
# Usage: scripts/verify_deployment.sh --application-id OCID --manifest PATH --tag TAG

set -euo pipefail

readonly EXIT_INVALID_INPUT=64
readonly EXIT_APPLICATION_NOT_ACTIVE=20
readonly EXIT_DEPLOYMENT_NOT_ACTIVE=21
readonly EXIT_TAG_MISMATCH=22
readonly EXIT_PROBE_TIMEOUT=23
readonly ENDPOINT_API_VERSION=20251112

application_id=""
expected_tag=""
manifest=""
functional=false
timeout_seconds=300
poll_seconds=5
script_directory="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$script_directory/lib/tool_env.sh"

usage() {
  printf '%s\n' "Usage: $0 --application-id OCID --manifest PATH --tag MAJOR.MINOR.PATCH"\
' [--functional] [--timeout-seconds SECONDS] [--poll-seconds SECONDS]'
}

require_positive_integer() {
  local value="$1"
  local option_name="$2"

  if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
    printf '%s must be a positive integer: %s\n' "$option_name" "$value" >&2
    exit "$EXIT_INVALID_INPUT"
  fi
}

probe_endpoint() {
  local probe_path="$1"
  local probe_url="${endpoint_base}/${probe_path}"
  local code=""
  local curl_exit=0

  if code="$(curl --silent --show-error --output /dev/null \
    --write-out '%{http_code}' \
    --connect-timeout "$poll_seconds" \
    --max-time "$poll_seconds" \
    "$probe_url")"; then
    curl_exit=0
  else
    curl_exit=$?
  fi

  if [[ -z "$code" ]]; then
    code=000
  fi

  case "$probe_path" in
    health)
      health_curl_exit="$curl_exit"
      health_http_status="$code"
      ;;
    ready)
      ready_curl_exit="$curl_exit"
      ready_http_status="$code"
      ;;
  esac
}

report() {
  local result="$1"
  local readiness_seconds="$2"

  printf 'Application=%s deployment=%s expected_tag=%s endpoint_host=%s ' \
    "$application_id" "$deployment_id" "$expected_tag" "$endpoint_host"
  printf 'health_curl_exit=%s health_http_status=%s ready_curl_exit=%s ' \
    "$health_curl_exit" "$health_http_status" "$ready_curl_exit"
  printf 'ready_http_status=%s readiness_seconds=%s result=%s\n' \
    "$ready_http_status" "$readiness_seconds" "$result"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --application-id|--expected-tag|--manifest|--tag|--timeout-seconds|--poll-seconds)
      if [[ $# -lt 2 || -z "$2" || "$2" == --* ]]; then
        usage >&2
        exit "$EXIT_INVALID_INPUT"
      fi
      case "$1" in
        --application-id) application_id="$2" ;;
        --expected-tag) expected_tag="$2" ;;
        --manifest) manifest="$2" ;;
        --tag) expected_tag="$2" ;;
        --timeout-seconds) timeout_seconds="$2" ;;
        --poll-seconds) poll_seconds="$2" ;;
      esac
      shift 2
      ;;
    --functional)
      functional=true
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
load_tenancy_settings OCI_REGION
if [[ -n "$manifest" ]]; then
  "$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" deployment-name \
    --manifest "$manifest" --tag "$expected_tag" >/dev/null
elif [[ "$functional" == true ]]; then
  printf '%s\n' '--functional requires --manifest.' >&2
  exit "$EXIT_INVALID_INPUT"
fi

if [[ ! "$application_id" =~ ^ocid1\.generativeaihostedapplication\.oc1\. ]]; then
  printf 'Application ID must be an OC1 Hosted Application OCID.\n' >&2
  exit "$EXIT_INVALID_INPUT"
fi
if [[ ! "$expected_tag" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]]; then
  printf 'Expected tag must be semantic (MAJOR.MINOR.PATCH): %s\n' "$expected_tag" >&2
  exit "$EXIT_INVALID_INPUT"
fi
require_positive_integer "$timeout_seconds" '--timeout-seconds'
require_positive_integer "$poll_seconds" '--poll-seconds'
if (( poll_seconds > timeout_seconds )); then
  printf '%s\n' '--poll-seconds must not exceed --timeout-seconds.' >&2
  exit "$EXIT_INVALID_INPUT"
fi
if [[ -z "${OCI_REGION:-}" || ! "$OCI_REGION" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
  printf '%s\n' 'OCI_REGION must be a non-empty OCI region identifier.' >&2
  exit "$EXIT_INVALID_INPUT"
fi
for required_tool in oci curl; do
  if ! command -v "$required_tool" >/dev/null 2>&1; then
    printf 'Missing required tool: %s\n' "$required_tool" >&2
    exit 1
  fi
done

application_state="$(oci --region "$OCI_REGION" generative-ai hosted-application get \
  --hosted-application-id "$application_id" \
  --query 'data."lifecycle-state"' \
  --raw-output)"
if [[ "$application_state" != 'ACTIVE' ]]; then
  printf 'Hosted Application must be ACTIVE; observed: %s\n' "$application_state" >&2
  exit "$EXIT_APPLICATION_NOT_ACTIVE"
fi

compartment_id="$(oci --region "$OCI_REGION" generative-ai hosted-application get \
  --hosted-application-id "$application_id" \
  --query 'data."compartment-id"' \
  --raw-output)"
active_deployment_query='data.items[?"lifecycle-state"==`ACTIVE`]'
non_deleted_deployment_query='data.items[?"lifecycle-state"!=`DELETED`]'
started_seconds="$(date +%s)"
active_deployment_count="$(oci --region "$OCI_REGION" generative-ai \
  hosted-deployment-collection list-hosted-deployments \
  --compartment-id "$compartment_id" \
  --application-id "$application_id" \
  --all \
  --query "length(${active_deployment_query})" \
  --raw-output)"
if [[ "$active_deployment_count" != '1' ]]; then
  non_deleted_deployment_count="$(oci --region "$OCI_REGION" generative-ai \
    hosted-deployment-collection list-hosted-deployments \
    --compartment-id "$compartment_id" \
    --application-id "$application_id" \
    --all \
    --query "length(${non_deleted_deployment_query})" \
    --raw-output)"
  if [[ "$non_deleted_deployment_count" != '1' ]]; then
    printf 'Expected exactly one ACTIVE Hosted Deployment; found %s.\n' \
      "$active_deployment_count" >&2
    exit "$EXIT_DEPLOYMENT_NOT_ACTIVE"
  fi
  deployment_id="$(oci --region "$OCI_REGION" generative-ai \
    hosted-deployment-collection list-hosted-deployments \
    --compartment-id "$compartment_id" \
    --application-id "$application_id" \
    --all \
    --query "(${non_deleted_deployment_query})[0].id" \
    --raw-output)"
  deployment_state="$(oci --region "$OCI_REGION" generative-ai hosted-deployment get \
    --hosted-deployment-id "$deployment_id" \
    --query 'data."lifecycle-state"' \
    --raw-output)"
  if [[ "$deployment_state" != 'UPDATING' ]]; then
    printf 'Expected exactly one ACTIVE Hosted Deployment; found %s.\n' \
      "$active_deployment_count" >&2
    exit "$EXIT_DEPLOYMENT_NOT_ACTIVE"
  fi
  while [[ "$deployment_state" == 'UPDATING' ]]; do
    elapsed_seconds=$(( $(date +%s) - started_seconds ))
    if (( elapsed_seconds >= timeout_seconds )); then
      printf 'Hosted Deployment was still UPDATING after %s seconds.\n' \
        "$timeout_seconds" >&2
      exit "$EXIT_DEPLOYMENT_NOT_ACTIVE"
    fi
    sleep "$poll_seconds"
    deployment_state="$(oci --region "$OCI_REGION" generative-ai hosted-deployment get \
      --hosted-deployment-id "$deployment_id" \
      --query 'data."lifecycle-state"' \
      --raw-output)"
  done
  if [[ "$deployment_state" != 'ACTIVE' ]]; then
    printf 'Expected exactly one ACTIVE Hosted Deployment; found %s.\n' \
      "$active_deployment_count" >&2
    exit "$EXIT_DEPLOYMENT_NOT_ACTIVE"
  fi
  active_artifact_tag="$(oci --region "$OCI_REGION" generative-ai hosted-deployment get \
    --hosted-deployment-id "$deployment_id" \
    --query 'data."active-artifact".tag' \
    --raw-output)"
else
  deployment_id="$(oci --region "$OCI_REGION" generative-ai \
    hosted-deployment-collection list-hosted-deployments \
    --compartment-id "$compartment_id" \
    --application-id "$application_id" \
    --all \
    --query "(${active_deployment_query})[0].id" \
    --raw-output)"
  active_artifact_tag="$(oci --region "$OCI_REGION" generative-ai \
    hosted-deployment-collection list-hosted-deployments \
    --compartment-id "$compartment_id" \
    --application-id "$application_id" \
    --all \
    --query "(${active_deployment_query})[0].\"active-artifact\".tag" \
    --raw-output)"
fi
if [[ "$active_artifact_tag" != "$expected_tag" ]]; then
  printf 'Active artifact tag mismatch: expected %s, observed %s.\n' \
    "$expected_tag" "$active_artifact_tag" >&2
  exit "$EXIT_TAG_MISMATCH"
fi

endpoint_host="inference.generativeai.${OCI_REGION}.oci.oraclecloud.com"
endpoint_base="https://${endpoint_host}/${ENDPOINT_API_VERSION}/hostedApplications/"
endpoint_base+="${application_id}/actions/invoke"
health_curl_exit=unattempted
health_http_status=unattempted
ready_curl_exit=unattempted
ready_http_status=unattempted
while :; do
  probe_endpoint health
  probe_endpoint ready
  elapsed_seconds=$(( $(date +%s) - started_seconds ))

  if [[ "$health_curl_exit" == '0' && "$health_http_status" == '200' && \
    "$ready_curl_exit" == '0' && "$ready_http_status" == '200' ]]; then
    if [[ "$functional" == true ]]; then
      checks_json=$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" checks \
        --manifest "$manifest")
      printf '%s' "$checks_json" | "$OCI_AGENT_PYTHON" \
        "$script_directory/run_manifest_checks.py" --base-url "$endpoint_base" \
        --timeout-seconds "$poll_seconds"
    fi
    report PASS "$elapsed_seconds"
    exit 0
  fi
  if (( elapsed_seconds >= timeout_seconds )); then
    if [[ "$health_curl_exit" == '0' && "$health_http_status" == '200' ]]; then
      report NOT_READY "$elapsed_seconds"
    else
      report UNHEALTHY "$elapsed_seconds"
    fi
    exit "$EXIT_PROBE_TIMEOUT"
  fi
  sleep "$poll_seconds"
done
