Set-StrictMode -Version Latest

# PowerShell access to scripts/agent_manifest.py and scripts/run_manifest_checks.py.
# Every function leaves $LASTEXITCODE set by the Python process so callers can
# propagate the exact exit code (64 for manifest errors) exactly like the Bash
# scripts do under `set -e`. Functions return $null when Python fails.

function Get-RepositoryRoot {
    Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}

function Get-AgentManifestScript {
    Join-Path (Split-Path -Parent $PSScriptRoot) 'agent_manifest.py'
}

function Test-PythonAvailable {
    [bool](Get-Command python -ErrorAction SilentlyContinue)
}

function Invoke-AgentManifestCommand {
    param(
        [Parameter(Mandatory)]
        [string[]]$Arguments
    )

    $output = & python (Get-AgentManifestScript) @Arguments
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
    $ApplicationJson | & python (Get-AgentManifestScript) runtime-matches --manifest $Manifest | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Invoke-ManifestChecks {
    # run_manifest_checks uses a package-relative import, so it must run as a
    # module from the repository root, as the Bash scripts do.
    param(
        [Parameter(Mandatory)] [string]$Manifest,
        [Parameter(Mandatory)] [string]$BaseUrl,
        [Parameter(Mandatory)] [int]$TimeoutSeconds
    )
    Push-Location (Get-RepositoryRoot)
    try {
        & python -m scripts.run_manifest_checks --manifest $Manifest --base-url $BaseUrl --timeout-seconds $TimeoutSeconds
    }
    finally {
        Pop-Location
    }
}

Export-ModuleMember -Function Get-RepositoryRoot, Test-PythonAvailable, Get-ManifestField, Get-ManifestDeploymentName, Get-ManifestRuntimeEnvironment, Test-ManifestRuntimeMatches, Invoke-ManifestChecks
