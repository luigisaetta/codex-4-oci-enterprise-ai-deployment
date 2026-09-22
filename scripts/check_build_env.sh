#!/usr/bin/env bash
set -euo pipefail
# Purpose: validate Docker/buildx and advertised amd64 support without changing resources.
# Requires: bash 3.2+, Docker CLI/daemon, buildx, awk, grep.
# Usage: check_build_env.sh [--builder NAME]
# Exit: 0 ready; 1 unavailable tool/daemon/builder; 2 no amd64; 64 invalid arguments.

usage() { printf 'Usage: %s [--builder NAME]\n' "$0"; }
builder=''
while [ "$#" -gt 0 ]; do
    case "$1" in
        --builder)
            if [ "$#" -lt 2 ] || [ -z "$2" ] || [[ "$2" == -* ]]; then
                usage >&2; exit 64
            fi
            builder=$2; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; exit 64 ;;
    esac
done
if ! command -v docker >/dev/null 2>&1; then
    printf 'Docker CLI is missing. Install Rancher Desktop or Docker Desktop.\n' >&2
    exit 1
fi
if ! info=$(docker info --format '{{.ServerVersion}}|{{.Architecture}}|{{.OperatingSystem}}'); then
    printf 'Docker daemon unavailable. Start your runtime and check the Docker context.\n' >&2
    exit 1
fi
if ! docker buildx version >/dev/null 2>&1; then
    printf 'Docker buildx is unavailable. Install or enable the buildx CLI plugin.\n' >&2
    exit 1
fi
if [ -n "$builder" ]; then
    if ! inspection=$(docker buildx inspect "$builder"); then
        printf 'Cannot inspect builder: %s\n' "$builder" >&2; exit 1
    fi
else
    if ! inspection=$(docker buildx inspect); then
        printf 'Cannot inspect the selected builder. Check docker buildx ls.\n' >&2; exit 1
    fi
fi
builder_name=$(printf '%s\n' "$inspection" | awk '/^Name:/ {print $2; exit}')
platforms=$(printf '%s\n' "$inspection" | awk '/^[[:space:]]*Platforms:/ {sub(/^[[:space:]]*Platforms:[[:space:]]*/, ""); print}')
if ! printf '%s\n' "$platforms" | grep -Eq '(^|[ ,])linux/amd64\*?([ ,]|$)'; then
    printf 'Builder %s does not advertise linux/amd64 (observed: %s).\n' "$builder_name" "${platforms:-none}" >&2
    context=$(docker context show 2>/dev/null || true)
    case "$context $info" in
        *rancher*) printf 'Rancher Desktop: Preferences > Virtual Machine > Emulation; enable Rosetta with VZ on Apple Silicon, or use QEMU. Restart and inspect the builder again.\n' >&2 ;;
        *desktop*|*Docker\ Desktop*) printf 'Docker Desktop: enable supported x86_64 emulation in Settings; check the VMM/Rosetta settings and restart.\n' >&2 ;;
        *) printf 'Configure amd64 emulation for your Docker runtime, or select an amd64-capable builder with --builder NAME.\n' >&2 ;;
    esac
    exit 2
fi
IFS='|' read -r docker_version daemon_arch runtime <<< "$info"
case "$daemon_arch" in
    amd64|x86_64) mode=native ;;
    arm64|aarch64) mode=emulated ;;
    *) mode="emulated (inferred from daemon architecture $daemon_arch)" ;;
esac
printf 'Docker=%s builder=%s daemon_arch=%s amd64=%s\n' "$docker_version" "$builder_name" "$daemon_arch" "$mode"
