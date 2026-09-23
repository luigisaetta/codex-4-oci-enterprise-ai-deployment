<# .SYNOPSIS Performs read-only OCI release checks and public health/readiness GET probes. #>
[CmdletBinding()]
param([string]$ApplicationId, [string]$ExpectedTag,
      [int]$TimeoutSeconds = 300, [int]$PollSeconds = 5, [switch]$Help)
if ($Help) { Write-Output 'Usage: .\scripts\verify_deployment.ps1 -ApplicationId OCID -ExpectedTag MAJOR.MINOR.PATCH [-TimeoutSeconds 300] [-PollSeconds 5]'; exit 0 }
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion -lt [version]'7.2') { [Console]::Error.WriteLine("PowerShell 7.2 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
if (-not $ApplicationId -or -not $ExpectedTag -or $ApplicationId -notmatch '^ocid1\.generativeaihostedapplication\.oc1\.' -or $ExpectedTag -notmatch '^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$' -or $TimeoutSeconds -lt 1 -or $PollSeconds -lt 1 -or $PollSeconds -gt $TimeoutSeconds -or -not $env:OCI_REGION) { Fail 64 'Invalid application ID, tag, timeout, poll interval, or OCI_REGION.' }
foreach ($tool in 'oci','curl') { if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { Fail 1 "Missing required tool: $tool" } }
$state = & oci --region $env:OCI_REGION generative-ai hosted-application get --hosted-application-id $ApplicationId --query 'data."lifecycle-state"' --raw-output; if ($state -ne 'ACTIVE') { Fail 20 "Hosted Application must be ACTIVE; observed: $state" }
$compartment = & oci --region $env:OCI_REGION generative-ai hosted-application get --hosted-application-id $ApplicationId --query 'data."compartment-id"' --raw-output
$active = 'data.items[?"lifecycle-state"==`ACTIVE`]'; $count = & oci --region $env:OCI_REGION generative-ai hosted-deployment-collection list-hosted-deployments --compartment-id $compartment --application-id $ApplicationId --all --query "length($active)" --raw-output; if ($count -ne '1') { Fail 21 "Expected exactly one ACTIVE Hosted Deployment; found $count." }
$deployment = & oci --region $env:OCI_REGION generative-ai hosted-deployment-collection list-hosted-deployments --compartment-id $compartment --application-id $ApplicationId --all --query "($active)[0].id" --raw-output
$tagQuery = "($active)[0].`"active-artifact`".tag"
$tag = & oci --region $env:OCI_REGION generative-ai hosted-deployment-collection list-hosted-deployments --compartment-id $compartment --application-id $ApplicationId --all --query $tagQuery --raw-output; if ($tag -ne $ExpectedTag) { Fail 22 "Active artifact tag mismatch: expected $ExpectedTag, observed $tag." }
$endpointHost = "inference.generativeai.$($env:OCI_REGION).oci.oraclecloud.com"; $base = "https://$endpointHost/20251112/hostedApplications/$ApplicationId/actions/invoke"; $started = Get-Date; $health = 'unattempted'; $ready = 'unattempted'
do { try { $health = (Invoke-WebRequest "$base/health" -TimeoutSec $PollSeconds -UseBasicParsing).StatusCode } catch { $health = '000' }; try { $ready = (Invoke-WebRequest "$base/ready" -TimeoutSec $PollSeconds -UseBasicParsing).StatusCode } catch { $ready = '000' }; $elapsed = [int]((Get-Date) - $started).TotalSeconds; if ($health -eq 200 -and $ready -eq 200) { Write-Output "Application=$ApplicationId deployment=$deployment expected_tag=$ExpectedTag endpoint_host=$endpointHost health_http_status=$health ready_http_status=$ready readiness_seconds=$elapsed result=PASS"; exit 0 }; Start-Sleep -Seconds $PollSeconds } while ($elapsed -lt $TimeoutSeconds)
Write-Output "Application=$ApplicationId deployment=$deployment expected_tag=$ExpectedTag endpoint_host=$endpointHost health_http_status=$health ready_http_status=$ready readiness_seconds=$elapsed result=NOT_READY"; exit 23
