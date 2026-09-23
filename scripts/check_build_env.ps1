<#
.SYNOPSIS
Checks whether a selected container engine can produce linux/amd64 images.
.DESCRIPTION
Requires PowerShell 7.2+ and a running Docker or Podman engine. This command is read-only.
#>
[CmdletBinding()]
param(
  [ValidateSet('Auto', 'Docker', 'Podman')]
  [string]$ContainerEngine = 'Auto',
  [string]$Builder,
  [switch]$Help
)
if ($Help) { Write-Output 'Usage: .\scripts\check_build_env.ps1 [-ContainerEngine Auto|Docker|Podman] [-Builder NAME]'; exit 0 }
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion -lt [version]'7.2') { [Console]::Error.WriteLine("PowerShell 7.2 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
Import-Module (Join-Path $PSScriptRoot 'lib/ContainerEngine.psm1') -Force
try { $engine = Resolve-ContainerEngine -ContainerEngine $ContainerEngine } catch { Fail 1 $_.Exception.Message }

if ($engine -eq 'Docker') {
  & docker buildx version *> $null
  if ($LASTEXITCODE -ne 0) { Fail 1 'Docker buildx is unavailable. Install or enable the buildx CLI plugin.' }
  $inspectArgs = @('buildx', 'inspect'); if ($Builder) { $inspectArgs += $Builder }
  $inspection = & docker @inspectArgs 2>&1
  if ($LASTEXITCODE -ne 0) { Fail 1 'Cannot inspect the selected Docker builder. Check docker buildx ls.' }
  $platformLine = $inspection | Where-Object { $_ -match '^\s*Platforms:' } | Select-Object -First 1
  $platforms = if ($platformLine) { ($platformLine -replace '^\s*Platforms:\s*', '') } else { '' }
  if ($platforms -notmatch '(^|[ ,])linux/amd64\*?([ ,]|$)') { Fail 2 "Docker builder does not advertise linux/amd64 (observed: $(if ($platforms) {$platforms} else {'none'}))." }
  Write-Output "SelectedEngine=Docker builder=$(if ($Builder) {$Builder} else {'default'}) platforms=$platforms"
  exit 0
}

$info = & podman info --format json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { Fail 1 'Podman is not usable. Start the Podman machine and try again.' }
if ($info.host.os -ne 'linux' -or $info.host.arch -notmatch '^(amd64|x86_64)$') {
  Fail 2 "Podman must provide linux/amd64; observed $($info.host.os)/$($info.host.arch)."
}
Write-Output "SelectedEngine=Podman version=$($info.version.version) host=$($info.host.os)/$($info.host.arch)"
