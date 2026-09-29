#!/usr/bin/env bash
# Purpose: install or remove this checkout's OCI agent skills as user-scope links.
# Prerequisites: Bash 3.2+ and permission to create links in the selected target.
# Inputs: --dry-run, --uninstall, and optional --target DIR.
# Side effects: creates or removes only links that point to this checkout's skills.
# Usage: install_skills.sh [--dry-run] [--uninstall] [--target DIR]

set -euo pipefail

dry_run=false
uninstall=false
target_dir="${HOME}/.agents/skills"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
tool_home="$(CDPATH= cd -- "$script_dir/.." && pwd -P)"
skills_dir="$tool_home/skills"
had_conflict=false

usage() {
    printf 'Usage: %s [--dry-run] [--uninstall] [--target DIR]\n' "$0"
}

report() {
    printf '%s: %s\n' "$1" "$2"
}

link_points_to_source() {
    local link_path="$1"
    local source_path="$2"
    local resolved_link

    resolved_link="$(CDPATH= cd -- "$link_path" 2>/dev/null && pwd -P)" || return 1
    [[ "$resolved_link" == "$source_path" ]]
}

ensure_target_directory() {
    if [[ -d "$target_dir" ]]; then
        return
    fi
    if [[ -e "$target_dir" || -L "$target_dir" ]]; then
        printf 'conflict: target directory is not a directory: %s\n' "$target_dir" >&2
        exit 1
    fi
    if [[ "$dry_run" == true ]]; then
        return
    fi
    mkdir -p -- "$target_dir"
}

install_skill() {
    local source_path="$1"
    local skill_name target_path

    skill_name="$(basename -- "$source_path")"
    target_path="$target_dir/$skill_name"
    if [[ -L "$target_path" ]]; then
        if link_points_to_source "$target_path" "$source_path"; then
            report unchanged "$skill_name"
        else
            report conflict "$skill_name"
            had_conflict=true
        fi
    elif [[ -e "$target_path" ]]; then
        report conflict "$skill_name"
        had_conflict=true
    elif [[ "$dry_run" == true ]]; then
        report 'would create' "$skill_name"
    else
        ln -s -- "$source_path" "$target_path"
        report created "$skill_name"
    fi
}

uninstall_skill() {
    local source_path="$1"
    local skill_name target_path

    skill_name="$(basename -- "$source_path")"
    target_path="$target_dir/$skill_name"
    if [[ ! -e "$target_path" && ! -L "$target_path" ]]; then
        report absent "$skill_name"
    elif ! [[ -L "$target_path" ]]; then
        report conflict "$skill_name"
        had_conflict=true
    elif ! link_points_to_source "$target_path" "$source_path"; then
        report conflict "$skill_name"
        had_conflict=true
    elif [[ "$dry_run" == true ]]; then
        report 'would remove' "$skill_name"
    else
        rm -- "$target_path"
        report removed "$skill_name"
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) dry_run=true ;;
        --uninstall) uninstall=true ;;
        --target)
            if [[ $# -lt 2 || -z "$2" ]]; then
                usage >&2
                exit 64
            fi
            target_dir="$2"
            shift
            ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; exit 64 ;;
    esac
    shift
done

if [[ ! -d "$skills_dir" ]]; then
    printf 'Skills source directory is unavailable: %s\n' "$skills_dir" >&2
    exit 1
fi
if [[ "$uninstall" == false ]]; then
    ensure_target_directory
elif [[ -e "$target_dir" || -L "$target_dir" ]] && [[ ! -d "$target_dir" ]]; then
    printf 'conflict: target directory is not a directory: %s\n' "$target_dir" >&2
    exit 1
fi

for source_path in "$skills_dir"/*; do
    [[ -d "$source_path" && -f "$source_path/SKILL.md" ]] || continue
    source_path="$(CDPATH= cd -- "$source_path" && pwd -P)"
    if [[ "$uninstall" == true ]]; then
        uninstall_skill "$source_path"
    else
        install_skill "$source_path"
    fi
done

printf '%s\n' 'Start a new Codex session to discover skill changes.'
if [[ "$had_conflict" == true ]]; then
    exit 1
fi
