#!/usr/bin/env bash
# Purpose: run the existing read-only setup checks in sequence and summarize them.
# Prerequisites: Bash 3.2+. Each check needs the tools it verifies (Python with
# PyYAML, Docker, OCI CLI); a missing tool is reported as a failed check.
# Inputs: optional --manifest PATH (adds manifest and OCIR repository checks) and
# --skills-target DIR (default: ~/.agents/skills).
# Side effects: none. Only reads local files and OCI metadata; never prints .env values.
# Usage: check_setup.sh [--manifest PATH] [--skills-target DIR]
# Exit codes: 0 every check passed, 1 at least one check failed, 64 invalid input.

set -uo pipefail

readonly EXIT_INVALID_INPUT=64
readonly EXIT_MISSING_REPOSITORY=20
script_directory="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
manifest=""
skills_target="${HOME}/.agents/skills"
python="${OCI_AGENT_PYTHON:-python}"
checks=0
failures=0

usage() {
  printf 'Usage: %s [--manifest PATH] [--skills-target DIR]\n' "$0"
}

# Print the last non-empty line of a command output.
last_line() {
  printf '%s\n' "$1" | awk 'NF { line = $0 } END { print line }'
}

pass() {
  checks=$((checks + 1))
  printf '  [PASS] %s\n' "$1"
}

fail() {
  checks=$((checks + 1))
  failures=$((failures + 1))
  printf '  [FAIL] %s\n' "$1"
  if [[ -n "$2" ]]; then
    printf '         %s\n' "$2"
  fi
}

# Run one existing check script; pass when it exits 0.
run_check() {
  local label="$1" output
  shift
  if output="$("$@" 2>&1)"; then
    pass "$label"
  else
    fail "$label" "$(last_line "$output")"
  fi
}

check_skills() {
  local label='Skills installed' output status problems
  if [[ ! -d "$skills_target" ]]; then
    fail "$label" "Not installed: $skills_target does not exist. Run scripts/install_skills.sh --target $skills_target."
    return
  fi
  output="$(bash "$script_directory/install_skills.sh" --dry-run --target "$skills_target" 2>&1)"
  status=$?
  problems="$(printf '%s\n' "$output" | grep -E '^(would create|conflict):' | paste -sd ',' - | sed 's/,/, /g')"
  if [[ "$status" -eq 0 && -z "$problems" ]]; then
    pass "$label"
  else
    fail "$label" "${problems:-$(last_line "$output")}"
  fi
}

check_repository() {
  local label='Compartment and OCIR repository' repository output status
  if ! repository="$("$python" "$script_directory/agent_manifest.py" get \
    --manifest "$manifest" --field publish.repository 2>/dev/null)"; then
    fail "$label" 'Requires a valid manifest.'
    return
  fi
  output="$(bash "$script_directory/ensure_ocir_repository.sh" --repository "$repository" 2>&1)"
  status=$?
  if [[ "$status" -eq 0 ]]; then
    pass "$label"
  elif [[ "$status" -eq "$EXIT_MISSING_REPOSITORY" ]]; then
    pass "$label (repository $repository not created yet; the push creates it)"
  else
    fail "$label" "$(last_line "$output")"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest|--skills-target)
      if [[ $# -lt 2 || -z "$2" || "$2" == --* ]]; then
        usage >&2
        exit "$EXIT_INVALID_INPUT"
      fi
      if [[ "$1" == '--manifest' ]]; then manifest="$2"; else skills_target="$2"; fi
      shift 2
      ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit "$EXIT_INVALID_INPUT" ;;
  esac
done

printf '%s\n' 'OCI agent setup check'
run_check 'Tenancy file (.env)' "$python" "$script_directory/new_agent.py" check-env
run_check 'Docker build environment' bash "$script_directory/check_build_env.sh"
run_check 'OCI CLI and region' bash "$script_directory/resolve_ocir_registry.sh"
check_skills
if [[ -n "$manifest" ]]; then
  run_check 'Agent manifest' "$python" "$script_directory/new_agent.py" check-manifest \
    --manifest "$manifest"
  check_repository
fi

if [[ "$failures" -eq 0 ]]; then
  printf 'Result: all %s checks passed.\n' "$checks"
  exit 0
fi
printf 'Result: %s of %s checks failed.\n' "$failures" "$checks"
exit 1
