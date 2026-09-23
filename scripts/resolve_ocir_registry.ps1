<# .SYNOPSIS Resolves OCI_REGION to its OC1 region-key OCIR registry hostname. #>
[CmdletBinding()]
param([switch]$Help)
if ($Help) { Write-Output 'Usage: .\scripts\resolve_ocir_registry.ps1'; exit 0 }
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion -lt [version]'7.2') { [Console]::Error.WriteLine("PowerShell 7.2 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
if (-not (Get-Command oci -ErrorAction SilentlyContinue)) { Fail 1 'OCI CLI is not available in PATH. Activate the project Conda environment first.' }
if (-not $env:OCI_REGION -or $env:OCI_REGION -notmatch '^[a-z0-9]+(-[a-z0-9]+)*$') { Fail 64 'OCI_REGION must be a non-empty OCI region identifier.' }
try { $key = & oci iam region list --all --query "data[?name=='$($env:OCI_REGION)'].key | [0]" --raw-output } catch { Fail 1 'Unable to list OCI regions with the configured OCI CLI profile.' }
if ($LASTEXITCODE -ne 0 -or -not $key -or $key -eq 'null' -or $key -notmatch '^[A-Za-z0-9]+$') { if (-not $key -or $key -eq 'null') { Fail 65 "OCI_REGION was not found by the configured OCI CLI profile: $($env:OCI_REGION)" }; Fail 1 'OCI CLI returned an invalid region key.' }
Write-Output "$($key.ToLowerInvariant()).ocir.io"
