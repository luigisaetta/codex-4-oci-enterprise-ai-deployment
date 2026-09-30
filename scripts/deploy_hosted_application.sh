#!/usr/bin/env bash
#
# Plan or release a manifest-defined OCI Generative AI Hosted Application image.
# Inputs: --manifest PATH --tag MAJOR.MINOR.PATCH; --apply authorizes mutations.
# Side effects: plans read OCI only; applies create missing resources or add and
# activate artifacts. It never deletes or replaces resources. Exit codes: 0
# success, 1 OCI/tool failure, 20 state requiring review, 64 invalid input, 65
# OCI CLI input validation.
set -euo pipefail
readonly EXIT_INVALID_INPUT=64 EXIT_EXISTING_RESOURCE=20 WAIT_SECONDS=1200 ARTIFACT_LIMIT=20
apply_changes=false; manifest=""; tag=""
script_directory="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$script_directory/lib/tool_env.sh"
usage() { printf 'Usage: %s [--plan|--apply] --manifest PATH --tag MAJOR.MINOR.PATCH\n' "$0"; }
need() { [[ -n "${!1:-}" ]] || { printf 'Missing required environment variable: %s\n' "$1" >&2; exit 64; }; }
ocid() { "$OCI_AGENT_PYTHON" -c 'import json,sys
p=sys.argv[1]; a=[]
def w(x):
 if isinstance(x,dict):
  for v in x.values(): w(v)
 elif isinstance(x,list):
  for v in x:w(v)
 elif isinstance(x,str) and x.startswith(p):a.append(x)
w(json.load(sys.stdin));a=sorted(set(a))
if len(a)!=1:raise SystemExit("Expected exactly one OCID with prefix {} but found {}.".format(p,len(a)))
print(a[0])' "$1"; }
field() { "$OCI_AGENT_PYTHON" -c 'import json,sys
x=json.load(sys.stdin)
for k in sys.argv[1].split("."): x=x.get(k,{}) if isinstance(x,dict) else {}
print(x if isinstance(x,str) else "")' "$1"; }
details() {
 local j
 j="$(oci --region "$OCI_REGION" --output json generative-ai hosted-deployment get --hosted-deployment-id "$deployment_id")"
 deployment_state="$(printf %s "$j"|field data.lifecycle-state)"; active_tag="$(printf %s "$j"|field data.active-artifact.tag)"
 artifact_count="$(printf %s "$j"|"$OCI_AGENT_PYTHON" -c 'import json,sys;print(len(json.load(sys.stdin).get("data",{}).get("artifacts",[])))')"
 target_status="$(printf %s "$j"|"$OCI_AGENT_PYTHON" -c 'import json,sys
u,t=sys.argv[1:]
for a in json.load(sys.stdin).get("data",{}).get("artifacts",[]):
 if a.get("container-uri")==u and a.get("tag")==t: print(a.get("status",""));break' "$container_uri" "$tag")"
}
plan() {
 printf 'Mode: %s\n' "$([[ "$apply_changes" == true ]]&&printf apply||printf plan)"
 printf 'OCIR artifact: %s:%s\nCompartment: %s\nHosted Application: %s (%s; %s)\nRelease case: %s\nCurrent active tag: %s\nTarget tag: %s\nArtifacts: %s/%s\n' "$container_uri" "$tag" "$compartment_id" "$application_name" "$profile" "$([[ -n "$application_id" ]]&&printf reuse||printf create)" "$release_case" "$active_tag" "$tag" "$artifact_count" "$ARTIFACT_LIMIT"
 [[ -z "$application_id" ]] || printf 'Endpoint: https://inference.generativeai.%s.oci.oraclecloud.com/20251112/hostedApplications/%s/actions/invoke\n' "$OCI_REGION" "$application_id"
 [[ -z "$environment_report" ]] || printf '%s\n' "$environment_report"; printf '%s\n' 'Container environment variables, managed storage, and custom networking are omitted.'
}
activate() {
 local out="" rc=0 status
 if out="$(oci --region "$OCI_REGION" --output json generative-ai hosted-deployment update --hosted-deployment-id "$deployment_id" --active-artifact "$(printf '{"artifactType":"SIMPLE_DOCKER_ARTIFACT","containerUri":"%s","tag":"%s"}' "$container_uri" "$tag")" --wait-for-state SUCCEEDED --wait-for-state FAILED --max-wait-seconds "$WAIT_SECONDS")";then :;else rc=$?;fi
 status="$(printf %s "$out"|"$OCI_AGENT_PYTHON" -c 'import json,sys
try: print(json.load(sys.stdin).get("data",{}).get("status","unknown"))
except ValueError: print("unknown")')"; details
 if [[ "$rc" -ne 0 || "$status" == FAILED || "$active_tag" != "$tag" ]];then printf 'Artifact activation failed: work-request status=%s; active tag=%s.\n' "$status" "$active_tag" >&2;exit 1;fi
}
while [[ $# -gt 0 ]];do case "$1" in --plan)apply_changes=false;;--apply)apply_changes=true;;--manifest|--tag) o="$1";shift;[[ $# -gt 0 && -n "$1" && "$1" != --* ]]||{ usage >&2;exit 64;};[[ "$o" == --manifest ]]&&manifest="$1"||tag="$1";;--help|-h)usage;exit 0;;*)usage >&2;exit 64;;esac;shift;done
resolve_python;load_tenancy_settings OCI_REGION OCI_COMPARTMENT_NAME OCIR_TENANCY_NAMESPACE
[[ -n "$manifest" && -n "$tag" ]]||{ usage >&2;exit 64;}; [[ "$tag" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$ ]]||{ printf 'Tag must be semantic (MAJOR.MINOR.PATCH).\n' >&2;exit 64;}
command -v oci >/dev/null||{ printf '%s\n' 'Missing required tool: oci' >&2;exit 1;};for x in OCI_REGION OCI_COMPARTMENT_NAME OCIR_TENANCY_NAMESPACE;do need "$x";done
repository="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" get --manifest "$manifest" --field publish.repository)";application_name="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" get --manifest "$manifest" --field deploy.application_name)";profile="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" get --manifest "$manifest" --field deploy.profile)";environment_variables_json="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" runtime-env --manifest "$manifest" --format oci-json)";environment_report="$("$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" runtime-env --manifest "$manifest" --format report)";container_uri="$("$script_directory/resolve_ocir_registry.sh")/$OCIR_TENANCY_NAMESPACE/$repository"
q='data[?"lifecycle-state"==`ACTIVE`]';c="$(oci --region "$OCI_REGION" iam compartment list --name "$OCI_COMPARTMENT_NAME" --compartment-id-in-subtree true --all --query "length($q)" --raw-output)";[[ "$c" == 1 ]]||{ printf 'Expected exactly one active compartment named "%s"; found %s.\n' "$OCI_COMPARTMENT_NAME" "$c" >&2;exit 1;};compartment_id="$(oci --region "$OCI_REGION" iam compartment list --name "$OCI_COMPARTMENT_NAME" --compartment-id-in-subtree true --all --query "($q)[0].id" --raw-output)"
q='data.items[?"lifecycle-state"!=`DELETED`]';c="$(oci --region "$OCI_REGION" generative-ai hosted-application-collection list-hosted-applications --compartment-id "$compartment_id" --display-name "$application_name" --all --query "length($q)" --raw-output)";[[ "$c" == 0 || "$c" == 1 ]]||{ printf 'Expected zero or one non-deleted Hosted Application named "%s"; found %s.\n' "$application_name" "$c" >&2;exit 20;}
application_id="";deployment_id="";active_tag=none;artifact_count=0;target_status="";release_case='First release'
if [[ "$c" == 1 ]];then
 application_id="$(oci --region "$OCI_REGION" generative-ai hosted-application-collection list-hosted-applications --compartment-id "$compartment_id" --display-name "$application_name" --all --query "($q)[0].id" --raw-output)"
 app="$(oci --region "$OCI_REGION" --output json generative-ai hosted-application get --hosted-application-id "$application_id")";[[ "$(printf %s "$app"|field data.lifecycle-state)" == ACTIVE ]]||{ printf '%s\n' 'Existing Hosted Application must be ACTIVE to reuse.' >&2;exit 20;};printf %s "$app"|"$OCI_AGENT_PYTHON" "$script_directory/agent_manifest.py" runtime-matches --manifest "$manifest"||{ printf '%s\n' 'Existing Hosted Application runtime environment differs from the manifest; update is not implemented.' >&2;exit 20;}
 c="$(oci --region "$OCI_REGION" generative-ai hosted-deployment-collection list-hosted-deployments --compartment-id "$compartment_id" --application-id "$application_id" --all --query "length($q)" --raw-output)";[[ "$c" == 0 || "$c" == 1 ]]||{ printf 'Expected zero or one non-deleted Hosted Deployment; found %s. Human review is required.\n' "$c" >&2;exit 20;}
 if [[ "$c" == 1 ]];then deployment_id="$(oci --region "$OCI_REGION" generative-ai hosted-deployment-collection list-hosted-deployments --compartment-id "$compartment_id" --application-id "$application_id" --all --query "($q)[0].id" --raw-output)";details;[[ "$deployment_state" == ACTIVE ]]||{ printf 'Hosted Deployment must be ACTIVE before release; observed: %s. Check the deployment and retry; no changes were made.\n' "$deployment_state" >&2;exit 20;};[[ "$target_status" != FAILED && "$target_status" != UPDATING ]]||{ printf 'Target artifact tag %s is %s. Check the deployment and retry; no changes were made.\n' "$tag" "$target_status" >&2;exit 20;};if [[ "$active_tag" == "$tag" ]];then release_case='Already released';elif [[ -z "$target_status" ]];then [[ "$artifact_count" -lt 20 ]]||{ printf 'Adding tag %s would exceed the artifact limit of 20 (current count: %s). Check the deployment and retry; no changes were made.\n' "$tag" "$artifact_count" >&2;exit 20;};release_case='New version';elif [[ "$target_status" == INACTIVE ]];then release_case='Return to a previous version';else printf 'Target artifact has unsupported status %s.\n' "$target_status" >&2;exit 20;fi;fi
fi
plan;[[ "$apply_changes" == true ]]||{ printf '%s\n' 'Plan complete. Re-run with --apply only after explicit authorization.';exit 0;}
case "$release_case" in 'Already released')printf 'Tag %s is already active; no changes were made.\n' "$tag";;'First release')if [[ -z "$application_id" ]];then application_id="$(oci --region "$OCI_REGION" --output json generative-ai hosted-application create --display-name "$application_name" --compartment-id "$compartment_id" --inbound-auth-config '{"inboundAuthConfigType":"NO_AUTH_CONFIG"}' --networking-config '{"inboundNetworkingConfig":{"endpointMode":"PUBLIC"},"outboundNetworkingConfig":{"networkMode":"MANAGED"}}' --environment-variables "$environment_variables_json" --wait-for-state SUCCEEDED --max-wait-seconds "$WAIT_SECONDS"|ocid ocid1.generativeaihostedapplication.)";fi;oci --region "$OCI_REGION" --output json generative-ai hosted-deployment create-hosted-deployment-single-docker-artifact --hosted-application-id "$application_id" --active-artifact-container-uri "$container_uri" --active-artifact-tag "$tag" --compartment-id "$compartment_id" --wait-for-state SUCCEEDED --max-wait-seconds "$WAIT_SECONDS"|ocid ocid1.generativeaihosteddeployment.;;'New version')oci --region "$OCI_REGION" generative-ai hosted-deployment add-artifact-create-single-docker-artifact-details --hosted-deployment-id "$deployment_id" --artifact-container-uri "$container_uri" --artifact-tag "$tag";activate;;'Return to a previous version')activate;;esac
