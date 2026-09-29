Set-StrictMode -Version Latest

# PowerShell access to scripts/agent_manifest.py and scripts/run_manifest_checks.py.
# Every function leaves $LASTEXITCODE set by the Python process so callers can
# propagate the exact exit code (64 for manifest errors) exactly like the Bash
# scripts do under `set -e`. Functions return $null when Python fails.

function Get-AgentManifestScript {
    Join-Path (Split-Path -Parent $PSScriptRoot) 'agent_manifest.py'
}

function Invoke-AgentManifestCommand {
    param(
        [Parameter(Mandatory)]
        [string[]]$Arguments
    )

    $output = & $env:OCI_AGENT_PYTHON (Get-AgentManifestScript) @Arguments
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return ((@($output) | ForEach-Object { "$_" }) -join "`n").Trim()
}

function Get-ManifestField {
    param(
        [Parameter(Mandatory)] [string]$Manifest,
        [Parameter(Mandatory)] [string]$Field
    )
    Invoke-AgentManifestCommand -Arguments @('get', '--manifest', $Manifest, '--field', $Field)
}

function Get-ManifestDeploymentName {
    param(
        [Parameter(Mandatory)] [string]$Manifest,
        [Parameter(Mandatory)] [string]$Tag
    )
    Invoke-AgentManifestCommand -Arguments @('deployment-name', '--manifest', $Manifest, '--tag', $Tag)
}

function Get-ManifestRuntimeEnvironment {
    param(
        [Parameter(Mandatory)] [string]$Manifest,
        [Parameter(Mandatory)]
        [ValidateSet('oci-json', 'report', 'local-json', 'local-report')]
        [string]$Format
    )
    Invoke-AgentManifestCommand -Arguments @('runtime-env', '--manifest', $Manifest, '--format', $Format)
}

function Test-ManifestRuntimeMatches {
    param(
        [Parameter(Mandatory)] [string]$Manifest,
        [Parameter(Mandatory)] [string]$ApplicationJson
    )
    $ApplicationJson | & $env:OCI_AGENT_PYTHON (Get-AgentManifestScript) runtime-matches --manifest $Manifest | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Invoke-ManifestChecks {
    # Obtain validated checks before piping them to the checks script by path.
    param(
        [Parameter(Mandatory)] [string]$Manifest,
        [Parameter(Mandatory)] [string]$BaseUrl,
        [Parameter(Mandatory)] [int]$TimeoutSeconds
    )
    $checks = Invoke-AgentManifestCommand -Arguments @('checks', '--manifest', $Manifest)
    if ($LASTEXITCODE -ne 0) {
        return
    }
    $checksScript = Join-Path (Split-Path -Parent $PSScriptRoot) 'run_manifest_checks.py'
    $checks | & $env:OCI_AGENT_PYTHON $checksScript --base-url $BaseUrl --timeout-seconds $TimeoutSeconds
}

Export-ModuleMember -Function Get-ManifestField, Get-ManifestDeploymentName, Get-ManifestRuntimeEnvironment, Test-ManifestRuntimeMatches, Invoke-ManifestChecks
