<#
.SYNOPSIS
Runs the existing read-only setup checks in sequence and summarizes them.
.DESCRIPTION
Mirrors scripts/check_setup.sh (same options, report lines, and exit codes: 0 every
check passed, 1 at least one check failed, 64 invalid input). Requires PowerShell 7.4+.
Each check needs the tools it verifies; a missing tool is reported as a failed check.
The command only reads local files and OCI metadata and never prints .env values.
#>
[CmdletBinding()]
param(
  [string]$Manifest,
  [string]$SkillsTarget = (Join-Path $HOME '.agents/skills'),
  [switch]$Help
)
$usage = "Usage: $PSCommandPath [-Manifest PATH] [-SkillsTarget DIR]"
if ($Help) { Write-Output $usage; exit 0 }
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if ($PSVersionTable.PSVersion -lt [version]'7.4') { [Console]::Error.WriteLine("PowerShell 7.4 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
if ($PSBoundParameters.ContainsKey('Manifest') -and -not $Manifest) { [Console]::Error.WriteLine($usage); exit 64 }
if (-not $SkillsTarget) { [Console]::Error.WriteLine($usage); exit 64 }
if (-not $env:OCI_AGENT_PYTHON) { $env:OCI_AGENT_PYTHON = 'python' }

$script:Checks = 0
$script:Failures = 0
# Child scripts run in their own pwsh process so that their stderr is captured.
$pwsh = (Get-Process -Id $PID).Path

function Get-LastLine($Output) {
  $lines = @($Output | ForEach-Object { "$_" } | Where-Object { $_.Trim() })
  if ($lines.Count -eq 0) { return '' }
  return $lines[-1]
}
function Write-Pass([string]$Label) {
  $script:Checks++
  Write-Output "  [PASS] $Label"
}
function Write-Fail([string]$Label, [string]$Detail) {
  $script:Checks++
  $script:Failures++
  Write-Output "  [FAIL] $Label"
  if ($Detail) { Write-Output "         $Detail" }
}
function Invoke-Script([string]$Name, [string[]]$Arguments) {
  $output = & $pwsh -NoProfile -File (Join-Path $PSScriptRoot $Name) @Arguments 2>&1
  return @{ Code = $LASTEXITCODE; Output = $output }
}
function Invoke-Python([string[]]$Arguments) {
  try {
    $output = & $env:OCI_AGENT_PYTHON @Arguments 2>&1
    return @{ Code = $LASTEXITCODE; Output = $output }
  } catch {
    return @{ Code = 1; Output = $_.Exception.Message }
  }
}
function Test-Result([string]$Label, $Result) {
  if ($Result.Code -eq 0) { Write-Pass $Label } else { Write-Fail $Label (Get-LastLine $Result.Output) }
}

Write-Output 'OCI agent setup check'
Test-Result 'Tenancy file (.env)' (Invoke-Python @((Join-Path $PSScriptRoot 'new_agent.py'), 'check-env'))
Test-Result 'Docker build environment' (Invoke-Script 'check_build_env.ps1' @())
Test-Result 'OCI CLI and region' (Invoke-Script 'resolve_ocir_registry.ps1' @())

if (-not (Test-Path -LiteralPath $SkillsTarget -PathType Container)) {
  Write-Fail 'Skills installed' "Not installed: $SkillsTarget does not exist. Run scripts/install_skills.ps1 -Target $SkillsTarget."
} else {
  $result = Invoke-Script 'install_skills.ps1' @('-DryRun', '-Target', $SkillsTarget)
  $problems = @($result.Output | ForEach-Object { "$_" } | Where-Object { $_ -match '^(would create|conflict):' }) -join ', '
  if ($result.Code -eq 0 -and -not $problems) { Write-Pass 'Skills installed' }
  else { Write-Fail 'Skills installed' $(if ($problems) { $problems } else { Get-LastLine $result.Output }) }
}

if ($Manifest) {
  Test-Result 'Agent manifest' (Invoke-Python @((Join-Path $PSScriptRoot 'new_agent.py'), 'check-manifest', '--manifest', $Manifest))
  $label = 'Compartment and OCIR repository'
  $lookup = Invoke-Python @((Join-Path $PSScriptRoot 'agent_manifest.py'), 'get', '--manifest', $Manifest, '--field', 'publish.repository')
  if ($lookup.Code -ne 0) {
    Write-Fail $label 'Requires a valid manifest.'
  } else {
    $repository = (Get-LastLine $lookup.Output).Trim()
    $result = Invoke-Script 'ensure_ocir_repository.ps1' @('-Repository', $repository)
    if ($result.Code -eq 0) { Write-Pass $label }
    elseif ($result.Code -eq 20) { Write-Pass "$label (repository $repository not created yet; the push creates it)" }
    else { Write-Fail $label (Get-LastLine $result.Output) }
  }
}

if ($script:Failures -eq 0) {
  Write-Output "Result: all $($script:Checks) checks passed."
  exit 0
}
Write-Output "Result: $($script:Failures) of $($script:Checks) checks failed."
exit 1
