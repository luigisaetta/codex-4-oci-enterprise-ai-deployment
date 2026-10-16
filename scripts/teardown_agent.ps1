<#
.SYNOPSIS
Plans or, with -Apply -Confirm NAME, removes one agent completely (Spec 029).

.DESCRIPTION
Twin of scripts/teardown_agent.sh; both run scripts/teardown_agent.py, so the
behavior, output, and exit codes are the same. Removes the Hosted Application
and its deployment, the managed storage of deploy.storage, the OCIR repository
with its images, and the local container images of the agent. Never touches IAM,
Vault, identity domains, Generative AI projects, or the agent folder.
Prerequisites: PowerShell 7.4+, Python with PyYAML, OCI CLI authentication, and
the tool's tenancy settings. Docker or Podman only for the local images.
Usage: teardown_agent.ps1 -Manifest PATH [-Plan|-Apply -Confirm APPLICATION_NAME]
  [-ContainerEngine Auto|Docker|Podman] [-TimeoutSeconds SECONDS].
Exit codes: 0 done or nothing to delete, 1 OCI or tool failure, 20 state
requiring review, 26 still deleting, 64 invalid input, 65 region not found.
#>
[CmdletBinding()]
param(
    [string]$Manifest,
    [switch]$Plan,
    [switch]$Apply,
    [string]$Confirm = '',
    [ValidateSet('Auto', 'Docker', 'Podman')]
    [string]$ContainerEngine = 'Auto',
    [string]$TimeoutSeconds = '1800',
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$usage = "Usage: $PSCommandPath -Manifest PATH [-Plan|-Apply -Confirm APPLICATION_NAME] [-ContainerEngine Auto|Docker|Podman] [-TimeoutSeconds SECONDS]"
if ($Help) { Write-Output $usage; exit 0 }
if ($PSVersionTable.PSVersion -lt [version]'7.4') {
    [Console]::Error.WriteLine("PowerShell 7.4 or later is required; current version is $($PSVersionTable.PSVersion).")
    exit 64
}
if (-not $Manifest -or ($Plan -and $Apply)) { [Console]::Error.WriteLine($usage); exit 64 }

Import-Module (Join-Path $PSScriptRoot 'lib/ToolEnvironment.psm1') -Force
if (-not (Resolve-AgentPython)) {
    [Console]::Error.WriteLine('Python with PyYAML is required. Activate the Conda environment oci-agent-shipyard or set OCI_AGENT_PYTHON.')
    exit 1
}

$arguments = @(
    (Join-Path $PSScriptRoot 'teardown_agent.py'), '--manifest', $Manifest,
    '--container-engine', $ContainerEngine.ToLowerInvariant(),
    '--timeout-seconds', $TimeoutSeconds
)
if ($Apply) { $arguments += @('--apply', '--confirm', $Confirm) } else { $arguments += '--plan' }
& $env:OCI_AGENT_PYTHON @arguments
exit $LASTEXITCODE
