#!/usr/bin/env bash
# Shared polling and response parsing for Hosted Application and Deployment mutations.
# Requires: Bash 3.2+, OCI CLI, OCI_AGENT_PYTHON, OCI_REGION, compartment_id,
# application_name, application_id, non_deleted_query, timeout_seconds, poll_interval.
# Inputs: resource kind, OCID and operation; reads OCI only after the initial mutation.
# Side effects: OCI read requests and bounded sleeps. Source from deploy_hosted_application.sh.

parse_mutation_id() {
  printf '%s' "$1" | "$OCI_AGENT_PYTHON" -c '
import json
import sys
try:
    value = json.load(sys.stdin)
    print((value.get("data") or {}).get("id") or "")
except (ValueError, AttributeError, TypeError):
    print("")
'
}

parse_mutation_work_request() {
  printf '%s' "$1" | "$OCI_AGENT_PYTHON" -c '
import json
import sys
try:
    print(json.load(sys.stdin).get("opc-work-request-id") or "")
except (ValueError, TypeError, AttributeError):
    print("")
'
}

lookup_mutated_resource() {
  local kind="$1" count result
  if [[ "$kind" == 'Hosted Application' ]]; then
    count="$(oci --region "$OCI_REGION" generative-ai hosted-application-collection \
      list-hosted-applications --compartment-id "$compartment_id" \
      --display-name "$application_name" --all \
      --query "length(${non_deleted_query})" --raw-output)" || return 1
    [[ "$count" == '1' ]] || return 1
    result="$(oci --region "$OCI_REGION" generative-ai hosted-application-collection \
      list-hosted-applications --compartment-id "$compartment_id" \
      --display-name "$application_name" --all \
      --query "(${non_deleted_query})[0].id" --raw-output)" || return 1
  else
    count="$(oci --region "$OCI_REGION" generative-ai hosted-deployment-collection \
      list-hosted-deployments --compartment-id "$compartment_id" \
      --application-id "$application_id" --all \
      --query "length(${non_deleted_query})" --raw-output)" || return 1
    [[ "$count" == '1' ]] || return 1
    result="$(oci --region "$OCI_REGION" generative-ai hosted-deployment-collection \
      list-hosted-deployments --compartment-id "$compartment_id" \
      --application-id "$application_id" --all \
      --query "(${non_deleted_query})[0].id" --raw-output)" || return 1
  fi
  [[ "$result" == ocid1.* ]] || return 1
  printf '%s' "$result"
}

# Read only the structured ServiceError object, never incidental digits in CLI text.
parse_service_error() {
  "$OCI_AGENT_PYTHON" -c '
import json
import sys

output = sys.stdin.read()
marker = "ServiceError:"
try:
    payload = output.split(marker, 1)[1].lstrip()
    error, _ = json.JSONDecoder().raw_decode(payload)
    if not isinstance(error, dict) or type(error.get("status")) is not int:
        raise ValueError("Missing integer status")
    print(json.dumps({key: error.get(key) for key in ("status", "code", "message")}))
except (IndexError, TypeError, ValueError):
    print("{}")
'
}

service_error_status() {
  printf '%s' "$1" | parse_service_error | "$OCI_AGENT_PYTHON" -c '
import json
import sys
print(json.load(sys.stdin).get("status", ""))
'
}

# Print only selected ServiceError fields after masking configured runtime values.
report_service_error() {
  local kind="$1" response="$2"
  printf '%s' "$response" | parse_service_error | "$OCI_AGENT_PYTHON" -c '
import json
import os
import sys

kind = sys.argv[1]
error = json.load(sys.stdin)
try:
    runtime = json.loads(os.environ.get("OCI_DEPLOY_RUNTIME_JSON", "[]"))
    values = sorted((str(item.get("value")) for item in runtime
                     if isinstance(item, dict) and item.get("value")), key=len, reverse=True)
except (ValueError, TypeError, AttributeError):
    values = []
fields = [str(error.get(key) if error.get(key) is not None else "unknown")
          for key in ("status", "code", "message")]
for value in values:
    fields = [field.replace(value, "[REDACTED]") for field in fields]
print("{} request failed: status={}; code={}; message={}.".format(kind, *fields), file=sys.stderr)
' "$kind"
}

report_work_request_errors() {
  local resource_id="$1" requests request_id errors
  requests="$(oci --region "$OCI_REGION" --output json generative-ai work-request list \
    --compartment-id "$compartment_id" --resource-id "$resource_id" \
    --status FAILED --all 2>/dev/null)" || requests=''
  request_id="$(printf '%s' "$requests" | "$OCI_AGENT_PYTHON" -c '
import json
import sys
try:
    items = json.load(sys.stdin)["data"]["items"]
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise ValueError("Missing work requests")
    print(items[0].get("id") or "")
except (ValueError, TypeError, AttributeError, KeyError, IndexError):
    print("")
')"
  if [[ -z "$request_id" ]]; then
    printf 'No FAILED work request found for %s.\n' "$resource_id" >&2
    return 0
  fi
  errors="$(oci --region "$OCI_REGION" --output json generative-ai work-request-error list \
    --work-request-id "$request_id" --all 2>/dev/null)" || errors=''
  printf '%s' "$errors" | "$OCI_AGENT_PYTHON" -c '
import json
import os
import sys
try:
    entries = json.load(sys.stdin)["data"]["items"]
    if not isinstance(entries, list):
        raise ValueError("Missing work request errors")
except (ValueError, TypeError, AttributeError, KeyError):
    entries = []
try:
    runtime = json.loads(os.environ.get("OCI_DEPLOY_RUNTIME_JSON", "[]"))
    values = sorted((str(item.get("value")) for item in runtime
                     if isinstance(item, dict) and item.get("value")), key=len, reverse=True)
except (ValueError, TypeError, AttributeError):
    values = []
printed = False
for entry in entries:
    if not isinstance(entry, dict):
        continue
    code = str(entry.get("code", "unknown"))
    message = str(entry.get("message", "unknown"))
    for value in values:
        code = code.replace(value, "[REDACTED]")
        message = message.replace(value, "[REDACTED]")
    print("OCI work request error: code={}; message={}".format(code, message), file=sys.stderr)
    printed = True
if not printed:
    print("No work request errors available.", file=sys.stderr)
'
}

wait_for_resource() {
  local kind="$1" resource_id="$2" operation="$3" start elapsed state response error status failures=0
  start="$(date +%s)"
  while true; do
    elapsed=$(( $(date +%s) - start ))
    if [[ "$kind" == 'Hosted Application' ]]; then
      response="$(oci --region "$OCI_REGION" --output json generative-ai hosted-application get \
        --hosted-application-id "$resource_id" 2>&1)" && error=0 || error=$?
    else
      response="$(oci --region "$OCI_REGION" --output json generative-ai hosted-deployment get \
        --hosted-deployment-id "$resource_id" 2>&1)" && error=0 || error=$?
    fi
    if (( error != 0 )); then
      status="$(service_error_status "$response")"
      if [[ "$operation" == 'delete' && "$status" == '404' ]]; then
        printf '%s: DELETED (elapsed %ss)\n' "$kind" "$elapsed"
        return 0
      fi
      if { [[ "$status" == '404' ]] && (( elapsed < 60 )); } || \
        [[ "$status" == '429' || "$status" == 5?? ]]; then
        failures=$((failures + 1))
        state='GET_RETRY'
        printf '%s: %s (elapsed %ss)\n' "$kind" "$state" "$elapsed"
        if (( failures >= 5 )); then
          printf '%s get failed after 5 consecutive attempts (last error: HTTP %s).\n' \
            "$kind" "$status" >&2
          return 1
        fi
      else
        printf '%s get failed for %s (last error: HTTP %s).\n' \
          "$kind" "$resource_id" "${status:-unknown}" >&2
        return 1
      fi
    else
      failures=0
      state="$(printf '%s' "$response" | "$OCI_AGENT_PYTHON" -c '
import json
import sys
try:
    print((json.load(sys.stdin).get("data") or {}).get("lifecycle-state") or "UNKNOWN")
except (ValueError, TypeError, AttributeError):
    print("UNKNOWN")
')"
      printf '%s: %s (elapsed %ss)\n' "$kind" "$state" "$elapsed"
      if [[ "$operation" == 'delete' ]]; then
        [[ "$state" == 'DELETED' ]] && return 0
      elif [[ "$state" == 'ACTIVE' ]]; then
        return 0
      fi
      if [[ "$state" == 'FAILED' ]]; then
        printf '%s %s is FAILED.\n' "$kind" "$resource_id" >&2
        report_work_request_errors "$resource_id"
        return 1
      fi
      if [[ "$state" != 'CREATING' && "$state" != 'UPDATING' && "$state" != 'DELETING' ]]; then
        printf '%s %s reached unexpected state %s.\n' "$kind" "$resource_id" "$state" >&2
        return 1
      fi
    fi
    if (( elapsed >= timeout_seconds )); then
      printf '%s %s is still %s after %ss; nothing else was changed or deleted by this script; OCI continues the operation.\n' \
        "$kind" "$resource_id" "$state" "$elapsed" >&2
      return 26
    fi
    sleep "$poll_interval"
  done
}
