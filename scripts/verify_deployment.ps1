<# .SYNOPSIS Verifies an OCI Generative AI Hosted Application deployment through its public health and readiness endpoints; OCI and HTTP reads only. Mirrors scripts/verify_deployment.sh (same options and exit codes: 0 pass; 1 missing tool; 20 application not ACTIVE; 21 deployment not ACTIVE; 22 tag mismatch; 23 probe timeout; 64 invalid input; functional check failures propagate 13). #>
[CmdletBinding()]
param(
  [string]$ApplicationId,
  [string]$Manifest,
  [string]$Tag,
  [switch]$Functional,
  [int]$TimeoutSeconds = 300,
  [int]$PollSeconds = 5,
  [switch]$Help
)
$usage = 'Usage: .\scripts\verify_deployment.ps1 -ApplicationId OCID -Manifest PATH -Tag MAJOR.MINOR.PATCH [-Functional] [-TimeoutSeconds 300] [-PollSeconds 5]'
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
$scriptDir = Split-Path -Parent $PSCommandPath
Import-Module (Join-Path $scriptDir 'lib/AgentManifest.psm1') -Force

if ($Manifest) {
  if (-not (Test-PythonAvailable)) { Fail 1 'Python is required to read the agent manifest.' }
  if (-not $Tag) { [Console]::Error.WriteLine($usage); exit 64 }
  Get-ManifestDeploymentName -Manifest $Manifest -Tag $Tag | Out-Null; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} elseif ($Functional) {
  Fail 64 '-Functional requires -Manifest.'
}
if (-not $ApplicationId -or $ApplicationId -notmatch '^ocid1\.generativeaihostedapplication\.oc1\.') { Fail 64 'Application ID must be an OC1 Hosted Application OCID.' }
if (-not $Tag -or $Tag -notmatch '^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$') { Fail 64 "Expected tag must be semantic (MAJOR.MINOR.PATCH): $Tag" }
if ($TimeoutSeconds -lt 1) { Fail 64 "-TimeoutSeconds must be a positive integer: $TimeoutSeconds" }
if ($PollSeconds -lt 1) { Fail 64 "-PollSeconds must be a positive integer: $PollSeconds" }
if ($PollSeconds -gt $TimeoutSeconds) { Fail 64 '-PollSeconds must not exceed -TimeoutSeconds.' }
if (-not $env:OCI_REGION -or $env:OCI_REGION -notmatch '^[a-z0-9]+(-[a-z0-9]+)*$') { Fail 64 'OCI_REGION must be a non-empty OCI region identifier.' }
if (-not (Get-Command oci -ErrorAction SilentlyContinue)) { Fail 1 'Missing required tool: oci' }

$region = $env:OCI_REGION
$applicationState = Invoke-Oci @('--region', $region, 'generative-ai', 'hosted-application', 'get', '--hosted-application-id', $ApplicationId, '--query', 'data."lifecycle-state"', '--raw-output')
if ($applicationState -ne 'ACTIVE') { Fail 20 "Hosted Application must be ACTIVE; observed: $applicationState" }
$compartmentId = Invoke-Oci @('--region', $region, 'generative-ai', 'hosted-application', 'get', '--hosted-application-id', $ApplicationId, '--query', 'data."compartment-id"', '--raw-output')
$activeDeployments = 'data.items[?"lifecycle-state"==`ACTIVE`]'
$deploymentListArgs = @('--region', $region, 'generative-ai', 'hosted-deployment-collection', 'list-hosted-deployments', '--compartment-id', $compartmentId, '--application-id', $ApplicationId, '--all')
$activeCount = Invoke-Oci ($deploymentListArgs + @('--query', "length($activeDeployments)", '--raw-output'))
if ($activeCount -ne '1') { Fail 21 "Expected exactly one ACTIVE Hosted Deployment; found $activeCount." }
$deploymentId = Invoke-Oci ($deploymentListArgs + @('--query', "($activeDeployments)[0].id", '--raw-output'))
$activeTag = Invoke-Oci ($deploymentListArgs + @('--query', "($activeDeployments)[0].`"active-artifact`".tag", '--raw-output'))
if ($activeTag -ne $Tag) { Fail 22 "Active artifact tag mismatch: expected $Tag, observed $activeTag." }

$endpointHost = "inference.generativeai.$region.oci.oraclecloud.com"
$endpointBase = "https://$endpointHost/20251112/hostedApplications/$ApplicationId/actions/invoke"
# Report keys match the Bash script; the *_curl_exit fields carry 0 on transport success and 1 on transport failure.
function Invoke-Probe([string]$Url) {
  try {
    $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec $PollSeconds -SkipHttpErrorCheck -ErrorAction Stop
    return @{ Exit = '0'; Status = "$([int]$response.StatusCode)" }
  } catch {
    return @{ Exit = '1'; Status = '000' }
  }
}
function Write-Report([string]$Result, [int]$ReadinessSeconds) {
  Write-Output "Application=$ApplicationId deployment=$deploymentId expected_tag=$Tag endpoint_host=$endpointHost health_curl_exit=$($health.Exit) health_http_status=$($health.Status) ready_curl_exit=$($ready.Exit) ready_http_status=$($ready.Status) readiness_seconds=$ReadinessSeconds result=$Result"
}
$health = @{ Exit = 'unattempted'; Status = 'unattempted' }
$ready = @{ Exit = 'unattempted'; Status = 'unattempted' }
$started = Get-Date
while ($true) {
  $health = Invoke-Probe "$endpointBase/health"
  $ready = Invoke-Probe "$endpointBase/ready"
  $elapsed = [int]((Get-Date) - $started).TotalSeconds
  if ($health.Exit -eq '0' -and $health.Status -eq '200' -and $ready.Exit -eq '0' -and $ready.Status -eq '200') {
    if ($Functional) {
      Invoke-ManifestChecks -Manifest $Manifest -BaseUrl $endpointBase -TimeoutSeconds $PollSeconds
      if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    Write-Report -Result 'PASS' -ReadinessSeconds $elapsed
    exit 0
  }
  if ($elapsed -ge $TimeoutSeconds) {
    if ($health.Exit -eq '0' -and $health.Status -eq '200') { Write-Report -Result 'NOT_READY' -ReadinessSeconds $elapsed } else { Write-Report -Result 'UNHEALTHY' -ReadinessSeconds $elapsed }
    exit 23
  }
  Start-Sleep -Seconds $PollSeconds
}
