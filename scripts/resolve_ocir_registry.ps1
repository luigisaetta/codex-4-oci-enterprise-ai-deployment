<# .SYNOPSIS Resolves OCI_REGION to its OCIR region-key endpoint. Mirrors scripts/resolve_ocir_registry.sh (no inputs; exit 64 invalid input, 65 region not found, 1 OCI CLI failure). #>
[CmdletBinding()]
param(
  [switch]$Help
)
if ($Help) { Write-Output 'Usage: .\scripts\resolve_ocir_registry.ps1'; exit 0 }
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if ($PSVersionTable.PSVersion -lt [version]'7.4') { [Console]::Error.WriteLine("PowerShell 7.4 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
if (-not $env:OCI_REGION) { Fail 64 'Missing required environment variable: OCI_REGION' }
if ($env:OCI_REGION -notmatch '^[a-z0-9]+(-[a-z0-9]+)*$') { Fail 64 "Invalid OCI_REGION value: $($env:OCI_REGION)" }
if (-not (Get-Command oci -ErrorAction SilentlyContinue)) { Fail 1 'OCI CLI is not available in PATH. Activate the project Conda environment first.' }
$key = (& oci iam region list --all --query "data[?name=='$($env:OCI_REGION)'].key | [0]" --raw-output | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { Fail 1 'Unable to list OCI regions with the configured OCI CLI profile.' }
if (-not $key -or $key -eq 'null') { Fail 65 "OCI_REGION was not found by the configured OCI CLI profile: $($env:OCI_REGION)" }
if ($key -notmatch '^[A-Za-z0-9]+$') { Fail 1 "OCI CLI returned an invalid region key for OCI_REGION $($env:OCI_REGION)." }
Write-Output "$($key.ToLowerInvariant()).ocir.io"
