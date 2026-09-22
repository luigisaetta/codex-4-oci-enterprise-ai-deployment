#!/usr/bin/env bash
set -euo pipefail
# Purpose: build/load only linux/amd64; never push or modify the Dockerfile.
# Requires: bash 3.2+, Docker/buildx, check_build_env.sh, standard Unix tools.
# Usage: build_image.sh --context DIR --dockerfile PATH --name NAME --tag VERSION
#        [--builder NAME] [--no-cache]
# Environment: BUILD_TIMEOUT_SECONDS (positive integer, default 1800).
# Side effects: base/package downloads, build cache and local image; temporary log removed.
# Exit: 0 success; 1/2 preflight; 3 tag; 4 paths; 5 pip resolution; 6 build/timeout; 64 usage.

usage() {
    printf 'Usage: %s --context DIR --dockerfile PATH --name NAME --tag VERSION [--builder NAME] [--no-cache]\n' "$0"
}
context=''; dockerfile=''; image_name=''; tag=''; builder=''; no_cache=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --context|--dockerfile|--name|--tag|--builder)
            if [ "$#" -lt 2 ] || [ -z "$2" ] || [[ "$2" == -* ]]; then usage >&2; exit 64; fi
            case "$1" in
                --context) context=$2 ;; --dockerfile) dockerfile=$2 ;;
                --name) image_name=$2 ;; --tag) tag=$2 ;; --builder) builder=$2 ;;
            esac
            shift 2 ;;
        --no-cache) no_cache=true; shift ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; exit 64 ;;
    esac
done
if [ -z "$context" ] || [ -z "$dockerfile" ] || [ -z "$image_name" ] || [ -z "$tag" ]; then
    usage >&2; exit 64
fi
# A SemVer core with optional Docker-compatible prerelease identifiers, no build metadata.
version_pattern='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$'
if [ "$tag" = latest ] || ! [[ "$tag" =~ $version_pattern ]] || [ "${#tag}" -gt 128 ]; then
    printf 'Invalid tag %s: use MAJOR.MINOR.PATCH with an optional -suffix; latest is forbidden.\n' "$tag" >&2
    exit 3
fi
if [ ! -f "$dockerfile" ] || [ ! -d "$context" ]; then
    printf 'Dockerfile must be a file and build context must be a directory: %s ; %s\n' "$dockerfile" "$context" >&2
    exit 4
fi
if [ ! -f "$context/.dockerignore" ]; then
    printf 'Warning: %s/.dockerignore is missing.\n' "$context" >&2
fi
build_timeout=${BUILD_TIMEOUT_SECONDS:-1800}
if ! [[ "$build_timeout" =~ ^[1-9][0-9]*$ ]] || [ "${#build_timeout}" -gt 7 ]; then
    printf 'BUILD_TIMEOUT_SECONDS must be a positive integer of at most 7 digits.\n' >&2; exit 64
fi
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [ -n "$builder" ]; then
    "$script_dir/check_build_env.sh" --builder "$builder"
else
    "$script_dir/check_build_env.sh"
fi
# Spec 001: local containerd storage produced an attestation index without these flags.
command=(docker buildx build --platform linux/amd64 --load --provenance=false --sbom=false -f "$dockerfile" -t "$image_name:$tag")
if [ -n "$builder" ]; then command+=(--builder "$builder"); fi
if [ "$no_cache" = true ]; then command+=(--no-cache); fi
command+=("$context")
printf 'Command:'; printf ' %q' "${command[@]}"; printf '\n'
log_file=$(mktemp "${TMPDIR:-/tmp}/oci-agent-build.XXXXXX")
build_pid=''
cleanup() {
    if [ -n "$build_pid" ] && kill -0 "$build_pid" 2>/dev/null; then
        kill -TERM "$build_pid" 2>/dev/null || true
        sleep 2
        kill -KILL "$build_pid" 2>/dev/null || true
        wait "$build_pid" 2>/dev/null || true
    fi
    rm -f "$log_file"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
started=$SECONDS
"${command[@]}" >"$log_file" 2>&1 &
build_pid=$!
timed_out=false
while kill -0 "$build_pid" 2>/dev/null; do
    if [ "$((SECONDS - started))" -ge "$build_timeout" ]; then
        timed_out=true
        kill -TERM "$build_pid" 2>/dev/null || true
        sleep 2
        kill -KILL "$build_pid" 2>/dev/null || true
        break
    fi
    sleep 1
done
build_status=0
wait "$build_pid" || build_status=$?
build_pid=''
cat "$log_file"
printf 'Build time: %s seconds\n' "$((SECONDS - started))"
if [ "$timed_out" = true ]; then
    printf 'Build exceeded BUILD_TIMEOUT_SECONDS=%s.\n' "$build_timeout" >&2; exit 6
fi
if [ "$build_status" -ne 0 ]; then
    if grep -E 'No matching distribution found|Could not find a version that satisfies' "$log_file" >&2; then
        printf '%s\n' 'A compatible manylinux x86_64 wheel may be unavailable, or the version may not exist. A remote amd64 builder or build tools would require a separately approved source-build policy; --only-binary remains mandatory here. No fallback was attempted.' >&2
        exit 5
    fi
    printf 'Docker build failed (exit %s).\n' "$build_status" >&2; exit 6
fi
if ! details=$(docker image inspect --format '{{.Id}} {{.Size}}' "$image_name:$tag"); then
    printf 'Build completed but the loaded image could not be inspected.\n' >&2; exit 6
fi
printf 'Image=%s tag=%s image_id/size_bytes=%s\n' "$image_name" "$tag" "$details"
