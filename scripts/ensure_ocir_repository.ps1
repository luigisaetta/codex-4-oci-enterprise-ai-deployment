<# .SYNOPSIS Checks that an OCIR repository exists; -Create creates one private, mutable repository. Mirrors scripts/ensure_ocir_repository.sh (same options and exit codes: 0 exists/created; 1 OCI failure; 20 absent; 64 invalid input). #>
[CmdletBinding()]
param(
  [string]$Repository,
  [switch]$Create,
  [switch]$Help
)
$usage = 'Usage: .\scripts\ensure_ocir_repository.ps1 -Repository NAME [-Create]'
if ($Help) { Write-Output $usage; Write-Output 'Check an OCIR repository; -Create creates it if it is absent.'; exit 0 }
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if ($PSVersionTable.PSVersion -lt [version]'7.4') { [Console]::Error.WriteLine("PowerShell 7.4 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
function Invoke-Oci([string[]]$Arguments) {
  $output = & oci @Arguments
  if ($LASTEXITCODE -ne 0) { Fail 1 "OCI CLI command failed (exit $LASTEXITCODE): oci $($Arguments -join ' ')" }
  return ((@($output) | ForEach-Object { "$_" }) -join "`n").Trim()
}
if (-not (Get-Command oci -ErrorAction SilentlyContinue)) { Fail 1 'OCI CLI is not available in PATH. Activate the project Conda environment first.' }
foreach ($name in 'OCI_REGION', 'OCI_COMPARTMENT_NAME') { if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue).Value) { Fail 64 "Missing required environment variable: $name" } }
if (-not $Repository -or $Repository -notmatch '^[a-z0-9][a-z0-9._/-]*$' -or $Repository.Contains('//')) { Fail 64 'Provide a valid OCIR repository with -Repository.' }

$region = $env:OCI_REGION
$active = 'data[?"lifecycle-state"==`ACTIVE`]'
$count = Invoke-Oci @('--region', $region, 'iam', 'compartment', 'list', '--name', $env:OCI_COMPARTMENT_NAME, '--compartment-id-in-subtree', 'true', '--all', '--query', "length($active)", '--raw-output')
if ($count -ne '1') { Fail 1 "Expected exactly one active compartment named `"$($env:OCI_COMPARTMENT_NAME)`"; found $count." }
$compartment = Invoke-Oci @('--region', $region, 'iam', 'compartment', 'list', '--name', $env:OCI_COMPARTMENT_NAME, '--compartment-id-in-subtree', 'true', '--all', '--query', "($active)[0].id", '--raw-output')

$listArgs = @('--region', $region, 'artifacts', 'container', 'repository', 'list', '--compartment-id', $compartment, '--display-name', $Repository, '--lifecycle-state', 'AVAILABLE', '--all')
$repositoryCount = Invoke-Oci ($listArgs + @('--query', 'length(data.items)', '--raw-output'))
if ($repositoryCount -eq '1') {
  $id = Invoke-Oci ($listArgs + @('--query', 'data.items[0].id', '--raw-output'))
  Write-Output "OCIR repository already exists: $id"
  exit 0
}
if ($repositoryCount -ne '0') { Fail 1 "Expected zero or one available repository named `"$Repository`"; found $repositoryCount." }
if (-not $Create) {
  [Console]::Error.WriteLine("OCIR repository `"$Repository`" is absent from compartment $compartment.")
  Fail 20 'Re-run with -Create to create one private, mutable repository.'
}
Write-Output "Creating private, mutable OCIR repository `"$Repository`" in compartment $compartment."
$id = Invoke-Oci @('--region', $region, 'artifacts', 'container', 'repository', 'create', '--compartment-id', $compartment, '--display-name', $Repository, '--is-public', 'false', '--is-immutable', 'false', '--wait-for-state', 'AVAILABLE', '--max-wait-seconds', '120', '--query', 'data.id', '--raw-output')
Write-Output "Created OCIR repository: $id"
