<#
.SYNOPSIS
Verifies an OCI Generative AI Hosted Application deployment through public endpoints.

.DESCRIPTION
OCI and HTTP reads only. The overall timeout budget starts before deployment-state
polling; health, readiness, and optional functional requests use a separate timeout.
#>
[CmdletBinding()]
param(
  [string]$ApplicationId,
  [string]$Manifest,
  [string]$Tag,
  [switch]$Functional,
  [int]$TimeoutSeconds = 300,
  [int]$PollSeconds = 5,
  [int]$RequestTimeoutSeconds = 60,
  [switch]$Help
)
$usage = (
  "Usage: $PSCommandPath -ApplicationId OCID -Manifest PATH -Tag MAJOR.MINOR.PATCH" +
  ' [-Functional] [-TimeoutSeconds 300] [-PollSeconds 5]' +
  ' [-RequestTimeoutSeconds 60]'
)
if ($Help) { Write-Output $usage; exit 0 }
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if ($PSVersionTable.PSVersion -lt [version]'7.4') {
  [Console]::Error.WriteLine(
    "PowerShell 7.4 or later is required; current version is $($PSVersionTable.PSVersion). " +
    'Open PowerShell 7 (pwsh), then run this command again.'
  )
  exit 64
}
function Fail([int]$Code, [string]$Message) {
  [Console]::Error.WriteLine($Message)
  exit $Code
}
function Invoke-Oci([string[]]$Arguments) {
  $output = & oci @Arguments
  if ($LASTEXITCODE -ne 0) { Fail 1 "OCI CLI command failed (exit $LASTEXITCODE): oci $($Arguments -join ' ')" }
  return ((@($output) | ForEach-Object { "$_" }) -join "`n").Trim()
}
$scriptDir = Split-Path -Parent $PSCommandPath
Import-Module (Join-Path $scriptDir 'lib/AgentManifest.psm1') -Force
Import-Module (Join-Path $scriptDir 'lib/ToolEnvironment.psm1') -Force
if (-not (Resolve-AgentPython)) {
  Fail 1 (
    'Python with PyYAML is required. Activate the Conda environment ' +
    'codex-4-oci-enterprise-ai-deployment or set OCI_AGENT_PYTHON.'
  )
}

if ($Manifest) {
  if (-not $Tag) { [Console]::Error.WriteLine($usage); exit 64 }
  Get-ManifestDeploymentName -Manifest $Manifest -Tag $Tag | Out-Null; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} elseif ($Functional) {
  Fail 64 '-Functional requires -Manifest.'
}
$deployProfile = 'public-noauth'
$authMode = 'none'
$domainUrl = ''
$audience = ''
$scope = ''
$accessToken = ''
$unauthenticatedStatus = 'not_applicable'
if ($Manifest) {
  $deployProfile = Get-ManifestField -Manifest $Manifest -Field deploy.profile
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  if ($deployProfile -eq 'public-idcs') {
    foreach ($name in 'OCI_AGENT_IDCS_CLIENT_ID', 'OCI_AGENT_IDCS_CLIENT_SECRET') {
      if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue).Value) {
        Fail 64 "Missing required environment variable: $name"
      }
    }
    $authMode = 'idcs'
    $domainUrl = Get-ManifestField -Manifest $Manifest -Field deploy.auth.domain_url
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $audience = Get-ManifestField -Manifest $Manifest -Field deploy.auth.audience
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $scope = Get-ManifestField -Manifest $Manifest -Field deploy.auth.scope
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  }
}
$settingsResult = Import-TenancySettings -Keys @('OCI_REGION')
if ($settingsResult -ne 0) { Fail $settingsResult 'Unable to load OCI tenancy settings.' }
if (-not $ApplicationId -or $ApplicationId -notmatch '^ocid1\.generativeaihostedapplication\.oc1\.') {
  Fail 64 'Application ID must be an OC1 Hosted Application OCID.'
}
if (-not $Tag -or $Tag -notmatch '^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$') {
  Fail 64 "Expected tag must be semantic (MAJOR.MINOR.PATCH): $Tag"
}
if ($TimeoutSeconds -lt 1) { Fail 64 "-TimeoutSeconds must be a positive integer: $TimeoutSeconds" }
if ($PollSeconds -lt 1) { Fail 64 "-PollSeconds must be a positive integer: $PollSeconds" }
if ($RequestTimeoutSeconds -lt 1) { Fail 64 "-RequestTimeoutSeconds must be a positive integer: $RequestTimeoutSeconds" }
if ($PollSeconds -gt $TimeoutSeconds) { Fail 64 '-PollSeconds must not exceed -TimeoutSeconds.' }
if (-not $env:OCI_REGION -or $env:OCI_REGION -notmatch '^[a-z0-9]+(-[a-z0-9]+)*$') {
  Fail 64 'OCI_REGION must be a non-empty OCI region identifier.'
}
if (-not (Get-Command oci -ErrorAction SilentlyContinue)) { Fail 1 'Missing required tool: oci' }

$region = $env:OCI_REGION
$applicationState = Invoke-Oci @(
  '--region', $region, 'generative-ai', 'hosted-application', 'get',
  '--hosted-application-id', $ApplicationId, '--query', 'data."lifecycle-state"',
  '--raw-output'
)
if ($applicationState -ne 'ACTIVE') { Fail 20 "Hosted Application must be ACTIVE; observed: $applicationState" }
$compartmentId = Invoke-Oci @(
  '--region', $region, 'generative-ai', 'hosted-application', 'get',
  '--hosted-application-id', $ApplicationId, '--query', 'data."compartment-id"',
  '--raw-output'
)
$activeDeployments = 'data.items[?"lifecycle-state"==`ACTIVE`]'
$nonDeletedDeployments = 'data.items[?"lifecycle-state"!=`DELETED`]'
$deploymentListArgs = @(
  '--region', $region, 'generative-ai', 'hosted-deployment-collection',
  'list-hosted-deployments', '--compartment-id', $compartmentId, '--application-id',
  $ApplicationId, '--all'
)
$started = Get-Date
$activeCount = Invoke-Oci ($deploymentListArgs + @('--query', "length($activeDeployments)", '--raw-output'))
if ($activeCount -ne '1') {
  $nonDeletedCount = Invoke-Oci ($deploymentListArgs + @(
    '--query', "length($nonDeletedDeployments)", '--raw-output'
  ))
  if ($nonDeletedCount -ne '1') {
    Fail 21 "Expected exactly one ACTIVE Hosted Deployment; found $activeCount."
  }
  $deploymentId = Invoke-Oci ($deploymentListArgs + @(
    '--query', "($nonDeletedDeployments)[0].id", '--raw-output'
  ))
  $deploymentState = Invoke-Oci @(
    '--region', $region, 'generative-ai', 'hosted-deployment', 'get',
    '--hosted-deployment-id', $deploymentId, '--query', 'data."lifecycle-state"',
    '--raw-output'
  )
  if ($deploymentState -ne 'UPDATING') {
    Fail 21 "Expected exactly one ACTIVE Hosted Deployment; found $activeCount."
  }
  while ($deploymentState -eq 'UPDATING') {
    $elapsed = [int]((Get-Date) - $started).TotalSeconds
    if ($elapsed -ge $TimeoutSeconds) {
      Fail 21 "Hosted Deployment was still UPDATING after $TimeoutSeconds seconds."
    }
    Start-Sleep -Seconds $PollSeconds
    $deploymentState = Invoke-Oci @(
      '--region', $region, 'generative-ai', 'hosted-deployment', 'get',
      '--hosted-deployment-id', $deploymentId, '--query', 'data."lifecycle-state"',
      '--raw-output'
    )
  }
  if ($deploymentState -ne 'ACTIVE') {
    Fail 21 "Expected exactly one ACTIVE Hosted Deployment; found $activeCount."
  }
  $activeTag = Invoke-Oci @(
    '--region', $region, 'generative-ai', 'hosted-deployment', 'get',
    '--hosted-deployment-id', $deploymentId, '--query', 'data."active-artifact".tag',
    '--raw-output'
  )
} else {
  $deploymentId = Invoke-Oci ($deploymentListArgs + @(
    '--query', "($activeDeployments)[0].id", '--raw-output'
  ))
  $activeTag = Invoke-Oci ($deploymentListArgs + @(
    '--query', "($activeDeployments)[0].`"active-artifact`".tag", '--raw-output'
  ))
}
if ($activeTag -ne $Tag) { Fail 22 "Active artifact tag mismatch: expected $Tag, observed $activeTag." }

if ($authMode -eq 'idcs') {
  $applicationJson = Invoke-Oci @(
    '--region', $region, '--output', 'json', 'generative-ai', 'hosted-application', 'get',
    '--hosted-application-id', $ApplicationId
  )
  $applicationJson | & $env:OCI_AGENT_PYTHON (Join-Path $scriptDir 'agent_manifest.py') `
    inbound-auth-matches --manifest $Manifest | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Fail 20 'Hosted Application inbound authentication differs from the manifest.'
  }
  $accessToken = & $env:OCI_AGENT_PYTHON (Join-Path $scriptDir 'idcs_token.py') `
    --domain-url $domainUrl --audience $audience --scope $scope
  if ($LASTEXITCODE -ne 0) {
    Fail 24 'Could not obtain an access token from the identity domain.'
  }
  $accessToken = ((@($accessToken) | ForEach-Object { "$_" }) -join "`n").Trim()
}

$endpointHost = "inference.generativeai.$region.oci.oraclecloud.com"
$endpointBase = "https://$endpointHost/20251112/hostedApplications/$ApplicationId/actions/invoke"
# Report keys match the Bash script; the *_curl_exit fields carry 0 on transport success and 1 on transport failure.
function Invoke-Probe([string]$Url, [hashtable]$Headers) {
  try {
    $response = Invoke-WebRequest -Uri $Url -Method Get -Headers $Headers -TimeoutSec $RequestTimeoutSeconds `
      -SkipHttpErrorCheck -ErrorAction Stop
    return @{ Exit = '0'; Status = "$([int]$response.StatusCode)" }
  } catch {
    return @{ Exit = '1'; Status = '000' }
  }
}
function Write-Report([string]$Result, [int]$ReadinessSeconds) {
  $authentication = "auth=$authMode"
  if ($authMode -eq 'idcs') {
    $authentication += " unauthenticated_status=$unauthenticatedStatus"
  }
  Write-Output (
    "Application=$ApplicationId deployment=$deploymentId expected_tag=$Tag " +
    "endpoint_host=$endpointHost health_curl_exit=$($health.Exit) " +
    "health_http_status=$($health.Status) ready_curl_exit=$($ready.Exit) " +
    "ready_http_status=$($ready.Status) readiness_seconds=$ReadinessSeconds $authentication result=$Result"
  )
}
$authenticatedHeaders = @{}
if ($authMode -eq 'idcs') {
  $authenticatedHeaders.Authorization = "Bearer $accessToken"
}
$health = @{ Exit = 'unattempted'; Status = 'unattempted' }
$ready = @{ Exit = 'unattempted'; Status = 'unattempted' }
while ($true) {
  $health = Invoke-Probe "$endpointBase/health" $authenticatedHeaders
  $ready = Invoke-Probe "$endpointBase/ready" $authenticatedHeaders
  $elapsed = [int]((Get-Date) - $started).TotalSeconds
  if ($health.Exit -eq '0' -and $health.Status -eq '200' -and $ready.Exit -eq '0' -and $ready.Status -eq '200') {
    if ($authMode -eq 'idcs') {
      $unauthenticated = Invoke-Probe "$endpointBase/health" @{}
      $unauthenticatedStatus = $unauthenticated.Status
      if ($unauthenticatedStatus -match '^2[0-9][0-9]$') {
        Fail 25 'The endpoint accepted a request without a token'
      }
      if ($unauthenticatedStatus -ne '401' -and $unauthenticatedStatus -ne '403') {
        Fail 23 "Unauthenticated health request returned HTTP $unauthenticatedStatus; expected 401 or 403."
      }
    }
    if ($Functional) {
      $checks = & $env:OCI_AGENT_PYTHON (Join-Path $scriptDir 'agent_manifest.py') checks --manifest $Manifest
      if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
      $checks = ((@($checks) | ForEach-Object { "$_" }) -join "`n")
      $checksScript = Join-Path $scriptDir 'run_manifest_checks.py'
      $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
      $startInfo.FileName = $env:OCI_AGENT_PYTHON
      $startInfo.UseShellExecute = $false
      $startInfo.RedirectStandardInput = $true
      $startInfo.Environment['OCI_AGENT_ACCESS_TOKEN'] = $accessToken
      [void]$startInfo.ArgumentList.Add($checksScript)
      [void]$startInfo.ArgumentList.Add('--base-url')
      [void]$startInfo.ArgumentList.Add($endpointBase)
      [void]$startInfo.ArgumentList.Add('--timeout-seconds')
      [void]$startInfo.ArgumentList.Add("$RequestTimeoutSeconds")
      $checksProcess = [System.Diagnostics.Process]::Start($startInfo)
      $checksProcess.StandardInput.Write($checks)
      $checksProcess.StandardInput.Close()
      $checksProcess.WaitForExit()
      if ($checksProcess.ExitCode -ne 0) { exit $checksProcess.ExitCode }
    }
    Write-Report -Result 'PASS' -ReadinessSeconds $elapsed
    exit 0
  }
  if ($elapsed -ge $TimeoutSeconds) {
    if ($health.Exit -eq '0' -and $health.Status -eq '200') {
      Write-Report -Result 'NOT_READY' -ReadinessSeconds $elapsed
    } else {
      Write-Report -Result 'UNHEALTHY' -ReadinessSeconds $elapsed
    }
    exit 23
  }
  Start-Sleep -Seconds $PollSeconds
}
