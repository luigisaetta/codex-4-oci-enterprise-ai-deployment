<# .SYNOPSIS Installs or removes this checkout's OCI agent skills as user-scope links. #>
[CmdletBinding()]
param(
  [switch]$DryRun,
  [switch]$Uninstall,
  [string]$Target = (Join-Path $HOME '.agents/skills'),
  [switch]$Help
)
$usage = "Usage: $PSCommandPath [-DryRun] [-Uninstall] [-Target DIR]"
if ($Help) { Write-Output $usage; exit 0 }
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if ($PSVersionTable.PSVersion -lt [version]'7.4') { [Console]::Error.WriteLine("PowerShell 7.4 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
function Report([string]$Action, [string]$Skill) { Write-Output "${Action}: ${Skill}" }
function Link-PointsToSource([string]$Path, [string]$Source) {
  try { return ([IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).Path) -eq $Source) } catch { return $false }
}

$scriptDir = Split-Path -Parent $PSCommandPath
$toolHome = Split-Path -Parent $scriptDir
$skillsDir = Join-Path $toolHome 'skills'
$hadConflict = $false
if (-not (Test-Path -LiteralPath $skillsDir -PathType Container)) { Fail 1 "Skills source directory is unavailable: $skillsDir" }

if (-not $Uninstall) {
  if (Test-Path -LiteralPath $Target) {
    if (-not (Test-Path -LiteralPath $Target -PathType Container)) { Fail 1 "conflict: target directory is not a directory: $Target" }
  } elseif (-not $DryRun) {
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
  }
} elseif ((Test-Path -LiteralPath $Target) -and -not (Test-Path -LiteralPath $Target -PathType Container)) {
  Fail 1 "conflict: target directory is not a directory: $Target"
}

foreach ($source in Get-ChildItem -LiteralPath $skillsDir -Directory | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') -PathType Leaf }) {
  $sourcePath = [IO.Path]::GetFullPath($source.FullName)
  $targetPath = Join-Path $Target $source.Name
  $item = Get-Item -LiteralPath $targetPath -Force -ErrorAction SilentlyContinue
  if ($Uninstall) {
    if (-not $item) { Report 'absent' $source.Name; continue }
    if (-not $item.LinkType -or -not (Link-PointsToSource $targetPath $sourcePath)) { Report 'conflict' $source.Name; $hadConflict = $true; continue }
    if ($DryRun) { Report 'would remove' $source.Name; continue }
    Remove-Item -LiteralPath $targetPath -Force
    Report 'removed' $source.Name
    continue
  }
  if ($item) {
    if ($item.LinkType -and (Link-PointsToSource $targetPath $sourcePath)) { Report 'unchanged' $source.Name } else { Report 'conflict' $source.Name; $hadConflict = $true }
    continue
  }
  if ($DryRun) { Report 'would create' $source.Name; continue }
  try {
    New-Item -ItemType SymbolicLink -Path $targetPath -Target $sourcePath | Out-Null
    Report 'created' $source.Name
  } catch {
    # Codex discovery through a directory junction is unverified.
    New-Item -ItemType Junction -Path $targetPath -Target $sourcePath | Out-Null
    Report 'created junction' $source.Name
  }
}
Write-Output 'Start a new Codex session to discover skill changes.'
if ($hadConflict) { exit 1 }
