#!/usr/bin/env bash
# Purpose: select the Python interpreter and import safe tenancy settings.
# Requires: Bash 3.2+ and scripts/tool_config.py.
# Side effects: exports requested OCI tenancy environment variables.

tool_env_directory="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
tool_env_scripts_directory="$(CDPATH= cd -- "$tool_env_directory/.." && pwd)"

resolve_python() {
    OCI_AGENT_PYTHON="${OCI_AGENT_PYTHON:-python}"
    export OCI_AGENT_PYTHON
    if ! "$OCI_AGENT_PYTHON" -c 'import yaml' >/dev/null 2>&1; then
        printf '%s\n' 'Python with PyYAML is required. Activate the Conda environment codex-4-oci-enterprise-ai-deployment or set OCI_AGENT_PYTHON.' >&2
        return 1
    fi
}

load_tenancy_settings() {
    local output
    local status
    local line
    local key
    local value

    if output=$("$OCI_AGENT_PYTHON" "$tool_env_scripts_directory/tool_config.py" env --keys "$@"); then
        status=0
    else
        status=$?
        return "$status"
    fi
    while IFS= read -r line || [ -n "$line" ]; do
        key=${line%%=*}
        value=${line#*=}
        case "$key" in
            OCI_REGION|OCI_COMPARTMENT_NAME|OCIR_TENANCY_NAMESPACE|OCIR_USERNAME)
                export "$key=$value"
                ;;
            *)
                printf 'Unsupported configuration key from tool_config.py: %s\n' "$key" >&2
                return 64
                ;;
        esac
    done <<EOF
$output
EOF
}
