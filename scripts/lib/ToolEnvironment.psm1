Set-StrictMode -Version Latest

# PowerShell selection of the Python interpreter and safe tenancy settings import.
# The module invokes scripts/tool_config.py; it never evaluates configuration text.

function Resolve-AgentPython {
    if (-not $env:OCI_AGENT_PYTHON) {
        $env:OCI_AGENT_PYTHON = 'python'
    }
    try {
        & $env:OCI_AGENT_PYTHON -c 'import yaml' *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Import-TenancySettings {
    param(
        [Parameter(Mandatory)]
        [string[]]$Keys
    )

    $toolConfig = Join-Path (Split-Path -Parent $PSScriptRoot) 'tool_config.py'
    $output = & $env:OCI_AGENT_PYTHON $toolConfig env --keys @Keys
    if ($LASTEXITCODE -ne 0) {
        return $LASTEXITCODE
    }
    if (-not $output) {
        return 0
    }
    foreach ($line in @($output)) {
        $text = "$line"
        if (-not $text) {
            continue
        }
        $separator = $text.IndexOf('=')
        if ($separator -lt 1) {
            return 64
        }
        $key = $text.Substring(0, $separator)
        $value = $text.Substring($separator + 1)
        if ($key -notin @(
            'OCI_REGION',
            'OCI_COMPARTMENT_NAME',
            'OCIR_TENANCY_NAMESPACE',
            'OCIR_USERNAME'
        )) {
            return 64
        }
        Set-Item -Path "Env:$key" -Value $value
    }
    return 0
}

Export-ModuleMember -Function Resolve-AgentPython, Import-TenancySettings
