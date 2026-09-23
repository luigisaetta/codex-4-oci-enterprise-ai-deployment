<# .SYNOPSIS Plans or, with -Apply, creates a manifest-defined OCI Generative AI Hosted Application release. Mirrors scripts/deploy_hosted_application.sh (same options and exit codes: 0 success; 1 tool/OCI failure; 20 conflicting existing resource; 64 invalid input). Without -Apply it performs OCI reads only; with -Apply it creates a missing public no-auth application or a missing derived deployment and never updates or deletes. #>
[CmdletBinding()]
param(
  [string]$Manifest,
  [string]$Tag,
  [switch]$Plan,
  [switch]$Apply,
  [switch]$Help
)
$usage = 'Usage: .\scripts\deploy_hosted_application.ps1 [-Plan|-Apply] -Manifest PATH -Tag MAJOR.MINOR.PATCH'
if ($Help) { Write-Output $usage; exit 0 }
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if ($PSVersionTable.PSVersion -lt [version]'7.4') { [Console]::Error.WriteLine("PowerShell 7.4 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
function Invoke-Oci([string[]]$Arguments) {
  $output = & oci @Arguments
  if ($LASTEXITCODE -ne 0) { Fail 1 "OCI CLI command failed (exit $LASTEXITCODE): oci $($Arguments -join ' ')" }
  return ((@($output) | ForEach-Object { "$_" }) -join "`n").Trim()
}
function Get-SingleOcid([string]$Json, [string]$Prefix) {
  $found = @([regex]::Matches($Json, [regex]::Escape($Prefix) + '[A-Za-z0-9._-]+') | ForEach-Object { $_.Value } | Sort-Object -Unique)
  if ($found.Count -ne 1) { Fail 1 "Expected exactly one OCID with prefix $Prefix but found $($found.Count)." }
  return $found[0]
}
if ($Plan -and $Apply) { Fail 64 'Choose -Plan or -Apply, not both.' }
if (-not $Manifest -or -not $Tag) { [Console]::Error.WriteLine($usage); exit 64 }
foreach ($tool in 'oci', 'python') { if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { Fail 1 "Missing required tool: $tool" } }
foreach ($name in 'OCI_REGION', 'OCI_COMPARTMENT_NAME', 'OCIR_TENANCY_NAMESPACE') { if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue).Value) { Fail 64 "Missing required environment variable: $name" } }
$scriptDir = Split-Path -Parent $PSCommandPath
Import-Module (Join-Path $scriptDir 'lib/AgentManifest.psm1') -Force

$repository = Get-ManifestField -Manifest $Manifest -Field publish.repository; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$applicationName = Get-ManifestField -Manifest $Manifest -Field deploy.application_name; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$deployProfile = Get-ManifestField -Manifest $Manifest -Field deploy.profile; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$deploymentName = Get-ManifestDeploymentName -Manifest $Manifest -Tag $Tag; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$environmentJson = Get-ManifestRuntimeEnvironment -Manifest $Manifest -Format oci-json; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$environmentReport = Get-ManifestRuntimeEnvironment -Manifest $Manifest -Format report; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$registry = (& (Join-Path $scriptDir 'resolve_ocir_registry.ps1') | Out-String).Trim(); if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$region = $env:OCI_REGION
$activeCompartments = 'data[?"lifecycle-state"==`ACTIVE`]'
$compartmentArgs = @('--region', $region, 'iam', 'compartment', 'list', '--name', $env:OCI_COMPARTMENT_NAME, '--compartment-id-in-subtree', 'true', '--all')
$compartmentCount = Invoke-Oci ($compartmentArgs + @('--query', "length($activeCompartments)", '--raw-output'))
if ($compartmentCount -ne '1') { Fail 1 "Expected exactly one active compartment named `"$($env:OCI_COMPARTMENT_NAME)`"; found $compartmentCount." }
$compartmentId = Invoke-Oci ($compartmentArgs + @('--query', "($activeCompartments)[0].id", '--raw-output'))

$nonDeletedApplications = 'data.items[?"lifecycle-state"!=`DELETED`]'
$applicationListArgs = @('--region', $region, 'generative-ai', 'hosted-application-collection', 'list-hosted-applications', '--compartment-id', $compartmentId, '--display-name', $applicationName, '--all')
$applicationCount = Invoke-Oci ($applicationListArgs + @('--query', "length($nonDeletedApplications)", '--raw-output'))
if ($applicationCount -ne '0' -and $applicationCount -ne '1') { Fail 20 "Expected zero or one non-deleted Hosted Application named `"$applicationName`"; found $applicationCount." }
$containerUri = "$registry/$($env:OCIR_TENANCY_NAMESPACE)/$repository"
$applicationId = ''
if ($applicationCount -eq '1') {
  $applicationId = Invoke-Oci ($applicationListArgs + @('--query', "($nonDeletedApplications)[0].id", '--raw-output'))
  $applicationState = Invoke-Oci @('--region', $region, 'generative-ai', 'hosted-application', 'get', '--hosted-application-id', $applicationId, '--query', 'data."lifecycle-state"', '--raw-output')
  if ($applicationState -ne 'ACTIVE') { Fail 20 "Existing Hosted Application must be ACTIVE to reuse; observed: $applicationState." }
  $applicationJson = Invoke-Oci @('--region', $region, '--output', 'json', 'generative-ai', 'hosted-application', 'get', '--hosted-application-id', $applicationId)
  if (-not (Test-ManifestRuntimeMatches -Manifest $Manifest -ApplicationJson $applicationJson)) {
    Fail 20 'Existing Hosted Application runtime environment differs from the manifest; update is not implemented.'
  }
}
$deploymentCount = '0'
if ($applicationId) {
  $deploymentQuery = 'data.items[?"display-name"==`' + $deploymentName + '` && "lifecycle-state"!=`DELETED`]'
  $deploymentCount = Invoke-Oci @('--region', $region, 'generative-ai', 'hosted-deployment-collection', 'list-hosted-deployments', '--compartment-id', $compartmentId, '--application-id', $applicationId, '--all', '--query', "length($deploymentQuery)", '--raw-output')
}

Write-Output "Mode: $(if ($Apply) { 'apply' } else { 'plan' })"
Write-Output "OCIR artifact: ${containerUri}:$Tag"
Write-Output "Compartment: $compartmentId"
Write-Output "Hosted Application: $applicationName ($deployProfile; $(if ($applicationId) { 'reuse' } else { 'create' }))"
Write-Output "Hosted Deployment: $deploymentName"
if ($environmentReport) { Write-Output $environmentReport }
Write-Output 'Container environment variables, managed storage, and custom networking are omitted.'
if ($deploymentCount -ne '0') { Fail 20 "A non-deleted Hosted Deployment named `"$deploymentName`" already exists; it will not be replaced." }
if (-not $Apply) { Write-Output 'Plan complete. Re-run with -Apply only after explicit authorization.'; exit 0 }

$waitSeconds = '1200'
if (-not $applicationId) {
  Write-Output 'Creating Hosted Application with NO_AUTH_CONFIG and Oracle-managed networking.'
  $applicationOutput = Invoke-Oci @('--region', $region, '--output', 'json', 'generative-ai', 'hosted-application', 'create', '--display-name', $applicationName, '--compartment-id', $compartmentId, '--inbound-auth-config', '{"inboundAuthConfigType":"NO_AUTH_CONFIG"}', '--networking-config', '{"inboundNetworkingConfig":{"endpointMode":"PUBLIC"},"outboundNetworkingConfig":{"networkMode":"MANAGED"}}', '--environment-variables', $environmentJson, '--wait-for-state', 'SUCCEEDED', '--max-wait-seconds', $waitSeconds)
  $applicationId = Get-SingleOcid -Json $applicationOutput -Prefix 'ocid1.generativeaihostedapplication.'
  Write-Output "Created Hosted Application: $applicationId"
} else {
  Write-Output "Reusing ACTIVE Hosted Application: $applicationId"
}
Write-Output 'Creating Hosted Deployment from the selected OCIR artifact.'
$deploymentOutput = Invoke-Oci @('--region', $region, '--output', 'json', 'generative-ai', 'hosted-deployment', 'create-hosted-deployment-single-docker-artifact', '--hosted-application-id', $applicationId, '--active-artifact-container-uri', $containerUri, '--active-artifact-tag', $Tag, '--display-name', $deploymentName, '--compartment-id', $compartmentId, '--wait-for-state', 'SUCCEEDED', '--max-wait-seconds', $waitSeconds)
$deploymentId = Get-SingleOcid -Json $deploymentOutput -Prefix 'ocid1.generativeaihosteddeployment.'
Write-Output "Created Hosted Deployment: $deploymentId"
