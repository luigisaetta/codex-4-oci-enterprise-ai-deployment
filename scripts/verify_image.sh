#!/usr/bin/env bash
set -euo pipefail
# Purpose: verify local amd64 image and HTTP probes under a read-only root filesystem.
# Requires: bash 3.2+, Docker daemon, curl, standard Unix tools; a free host port.
# Usage: verify_image.sh --manifest PATH --tag VERSION [--port 8080] [--timeout-seconds 90]
#        verify_image.sh --image NAME:TAG [--port 8080] [--timeout-seconds 90]
#        [--post-path /PATH --post-body JSON]
# Side effects: temporary containers/log files; always removes owned smoke container.
# Exit: 0 pass; 1 missing tools or daemon; 10 image architecture; 11 runtime architecture;
#       12 startup/readiness/cleanup failure; 13 POST failure; 64 invalid arguments.

usage() {
    printf 'Usage: %s --manifest PATH --tag VERSION [--port 8080] [--timeout-seconds 90]\n' "$0"
    printf '   or: %s --image NAME:TAG [--port 8080] [--timeout-seconds 90] [--post-path /PATH --post-body JSON]\n' "$0"
}
image=''; port=8080; timeout_seconds=90; post_path=''; post_body=''; manifest=''; tag=''; body_given=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --image|--port|--timeout-seconds|--post-path|--post-body|--manifest|--tag)
            if [ "$#" -lt 2 ] || [ -z "$2" ] || [[ "$2" == --* ]]; then usage >&2; exit 64; fi
            case "$1" in
                --image) image=$2 ;; --port) port=$2 ;; --timeout-seconds) timeout_seconds=$2 ;;
                --post-path) post_path=$2 ;; --post-body) post_body=$2; body_given=true ;;
                --manifest) manifest=$2 ;; --tag) tag=$2 ;;
            esac
            shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; exit 64 ;;
    esac
done
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [ -n "$manifest" ]; then
    if [ -n "$image" ] || [ -n "$post_path" ] || [ "$body_given" = true ] || [ -z "$tag" ]; then
        printf '%s\n' '--manifest requires --tag and cannot be combined with --image or legacy POST options.' >&2; exit 64
    fi
    if ! command -v python >/dev/null 2>&1; then printf '%s\n' 'Python is required to read the agent manifest.' >&2; exit 1; fi
    image_name=$(python "$script_dir/agent_manifest.py" get --manifest "$manifest" --field name)
    python "$script_dir/agent_manifest.py" deployment-name --manifest "$manifest" --tag "$tag" >/dev/null
    image="${image_name}:${tag}"
elif [ -n "$tag" ]; then
    printf '%s\n' '--tag requires --manifest.' >&2; exit 64
fi
if [ -z "$image" ] || [[ "$image" == -* ]] || ! [[ "$port" =~ ^[1-9][0-9]*$ ]] || [ "${#port}" -gt 5 ] || [ "$port" -gt 65535 ]; then
    usage >&2; exit 64
fi
if ! [[ "$timeout_seconds" =~ ^[1-9][0-9]*$ ]] || [ "${#timeout_seconds}" -gt 7 ]; then usage >&2; exit 64; fi
if { [ -n "$post_path" ] && { [[ "$post_path" != /* ]] || [ "$body_given" = false ]; }; } || { [ -z "$post_path" ] && [ "$body_given" = true ]; }; then
    printf 'Supply --post-path /PATH and --post-body JSON together.\n' >&2; exit 64
fi
for tool in docker curl; do
    if ! command -v "$tool" >/dev/null 2>&1; then printf 'Missing tool: %s\n' "$tool" >&2; exit 1; fi
done
if ! docker info >/dev/null 2>&1; then
    printf 'Docker daemon unavailable. Start your runtime and check the Docker context.\n' >&2
    exit 1
fi
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/oci-agent-verify.XXXXXX")
architecture=unknown; runtime_arch=unverified; digest=unavailable; readiness_time=unavailable
cleanup() {
    status=$?
    trap - EXIT INT TERM
    if [ -s "$work_dir/container.cid" ]; then
        container_id=$(cat "$work_dir/container.cid")
        if [ "$status" -ne 0 ]; then docker logs "$container_id" >&2 || true; fi
        if ! docker rm -f "$container_id" >/dev/null; then
            printf 'Could not remove owned container %s. Remove it manually.\n' "$container_id" >&2
            if [ "$status" -eq 0 ]; then status=12; fi
        fi
    fi
    result=FAIL
    if [ "$status" -eq 0 ]; then result=PASS; fi
    printf 'Image=%s digest=%s architecture=%s runtime_arch=%s readiness_seconds=%s result=%s\n' "$image" "$digest" "$architecture" "$runtime_arch" "$readiness_time" "$result"
    rm -rf "$work_dir"
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if ! architecture=$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$image"); then
    printf 'Could not inspect image platform.\n' >&2; exit 10
fi
if [ "$architecture" != linux/amd64 ]; then
    printf 'Expected linux/amd64, observed: %s\n' "$architecture" >&2; exit 10
fi
# Locally built images need not have a registry manifest digest. Do not invent one.
if ! digest=$(docker image inspect --format '{{if .RepoDigests}}{{index .RepoDigests 0}}{{else}}unavailable (local image; no repository digest){{end}}' "$image"); then
    exit 10
fi
uname_status=0
runtime_arch=$(docker run --rm --platform linux/amd64 "$image" uname -m 2>"$work_dir/uname.err") || uname_status=$?
if [ "$uname_status" -ne 0 ]; then
    if [ "$uname_status" -eq 127 ] && grep -Eq '(exec: "uname": executable file not found|exec: "uname": stat uname: no such file|uname: (not found|No such file))' "$work_dir/uname.err"; then
        runtime_arch=skipped
        printf 'Warning: uname is absent; runtime architecture check skipped.\n' >&2
    else
        cat "$work_dir/uname.err" >&2
        printf 'Runtime architecture command failed (exit %s).\n' "$uname_status" >&2; exit 11
    fi
elif [ "$runtime_arch" != x86_64 ]; then
    printf 'Expected x86_64, observed: %s\n' "$runtime_arch" >&2; exit 11
fi
started=$SECONDS
if ! docker run -d --platform linux/amd64 --read-only --tmpfs /tmp --cidfile "$work_dir/container.cid" -p "$port:8080" "$image" >"$work_dir/start.out" 2>"$work_dir/start.err"; then
    cat "$work_dir/start.err" >&2; exit 12
fi
base_url="http://127.0.0.1:$port"
while :; do
    all_ready=true
    for path in /health /ready; do
        remaining=$((timeout_seconds - (SECONDS - started)))
        if [ "$remaining" -le 0 ]; then all_ready=false; break; fi
        code=''
        if ! code=$(curl --silent --noproxy '*' --connect-timeout "$remaining" --max-time "$remaining" --output /dev/null --write-out '%{http_code}' "$base_url$path"); then
            all_ready=false
        elif [ "$code" != 200 ]; then
            all_ready=false
        fi
    done
    if [ "$all_ready" = true ]; then readiness_time=$((SECONDS - started)); break; fi
    if [ "$((SECONDS - started))" -ge "$timeout_seconds" ]; then
        printf 'Health/readiness timed out after %s seconds.\n' "$timeout_seconds" >&2; exit 12
    fi
    sleep 1
done
if [ -n "$manifest" ]; then
    python -m scripts.run_manifest_checks --manifest "$manifest" --base-url "$base_url" --timeout-seconds "$timeout_seconds"
elif [ -n "$post_path" ]; then
    if ! code=$(curl --silent --show-error --noproxy '*' --connect-timeout "$timeout_seconds" --max-time "$timeout_seconds" --output "$work_dir/post.body" --write-out '%{http_code}' --request POST --header 'Content-Type: application/json' --data-raw "$post_body" "$base_url$post_path"); then
        if [ -f "$work_dir/post.body" ]; then cat "$work_dir/post.body"; fi
        printf 'Functional POST request failed.\n' >&2; exit 13
    fi
    cat "$work_dir/post.body"; printf '\n'
    if [ "$code" != 200 ]; then printf 'POST returned HTTP %s, expected 200.\n' "$code" >&2; exit 13; fi
fi
