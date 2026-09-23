<# .SYNOPSIS Plans or, with -Apply, creates a no-auth OCI Hosted Application deployment. #>
[CmdletBinding()]
param(
  [string]$Image,
  [ValidateSet('Auto', 'Docker', 'Podman')]
  [string]$ContainerEngine = 'Auto',
  [switch]$Apply,
  [switch]$Plan,
  [switch]$Help
)
if ($Help) { Write-Output 'Usage: .\scripts\deploy_hosted_application.ps1 [-Plan|-Apply] -Image NAME:MAJOR.MINOR.PATCH [-ContainerEngine Auto|Docker|Podman]'; exit 0 }
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion -lt [version]'7.2') { [Console]::Error.WriteLine("PowerShell 7.2 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
if ($Plan -and $Apply) { Fail 64 'Choose -Plan or -Apply, not both.' }
if (-not $Image -or $Image -notmatch ':(?<tag>[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?)$') { Fail 64 "Image tag must be semantic (MAJOR.MINOR.PATCH): $Image" }
foreach ($name in 'OCI_REGION','OCI_COMPARTMENT_NAME','OCIR_TENANCY_NAMESPACE','OCIR_REPOSITORY','OCI_HOSTED_APPLICATION_NAME','OCI_HOSTED_DEPLOYMENT_NAME') { if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue).Value) { Fail 64 "Missing required environment variable: $name" } }
foreach ($tool in 'oci','python') { if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { Fail 1 "Missing required tool: $tool" } }
$scriptDir = Split-Path -Parent $PSCommandPath
Import-Module (Join-Path $scriptDir 'lib/ContainerEngine.psm1') -Force
try { $engine = Resolve-ContainerEngine -ContainerEngine $ContainerEngine } catch { Fail 1 $_.Exception.Message }
$engineCommand = $engine.ToLowerInvariant()
$platform = & $engineCommand image inspect $Image --format '{{.Os}}/{{.Architecture}}'; if ($LASTEXITCODE -ne 0 -or $platform -ne 'linux/amd64') { Fail 10 "Image platform must be linux/amd64; found $platform." }
$registry = & (Join-Path (Split-Path -Parent $PSCommandPath) 'resolve_ocir_registry.ps1'); if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$active = 'data[?"lifecycle-state"==`ACTIVE`]'; $count = & oci --region $env:OCI_REGION iam compartment list --name $env:OCI_COMPARTMENT_NAME --compartment-id-in-subtree true --all --query "length($active)" --raw-output
if ($LASTEXITCODE -ne 0 -or $count -ne '1') { Fail 1 "Expected exactly one active compartment named `"$($env:OCI_COMPARTMENT_NAME)`"; found $count." }
$compartment = & oci --region $env:OCI_REGION iam compartment list --name $env:OCI_COMPARTMENT_NAME --compartment-id-in-subtree true --all --query "($active)[0].id" --raw-output
$existing = & oci --region $env:OCI_REGION generative-ai hosted-application-collection list-hosted-applications --compartment-id $compartment --display-name $env:OCI_HOSTED_APPLICATION_NAME --all --query 'length(data.items[?"lifecycle-state"!=`DELETED`])' --raw-output
$tag = $Matches.tag; $uri = "$registry/$($env:OCIR_TENANCY_NAMESPACE)/$($env:OCIR_REPOSITORY)"
Write-Output "Mode: $(if ($Apply) {'apply'} else {'plan'})"; Write-Output "Container engine: $engine"; Write-Output "Source image: $Image ($platform)"; Write-Output "OCIR artifact: $uri`:$tag"; Write-Output "Compartment: $compartment"; Write-Output "Hosted Application: $($env:OCI_HOSTED_APPLICATION_NAME) (NO_AUTH_CONFIG; PUBLIC; MANAGED)"; Write-Output "Hosted Deployment: $($env:OCI_HOSTED_DEPLOYMENT_NAME)"; Write-Output 'Container environment variables, managed storage, and custom networking are omitted.'
if ($existing -ne '0') { Fail 20 "Found $existing non-deleted Hosted Application(s) named `"$($env:OCI_HOSTED_APPLICATION_NAME)`". For safety, this script will not reuse or alter an existing application." }
if (-not $Apply) { Write-Output 'Plan complete. Re-run with -Apply only after explicit authorization.'; exit 0 }
$appJson = & oci --region $env:OCI_REGION --output json generative-ai hosted-application create --display-name $env:OCI_HOSTED_APPLICATION_NAME --compartment-id $compartment --inbound-auth-config '{"inboundAuthConfigType":"NO_AUTH_CONFIG"}' --networking-config '{"inboundNetworkingConfig":{"endpointMode":"PUBLIC"},"outboundNetworkingConfig":{"networkMode":"MANAGED"}}' --wait-for-state SUCCEEDED --max-wait-seconds 1200
if ($LASTEXITCODE -ne 0) { Fail 1 'Hosted Application creation failed.' }; $appId = ([regex]::Match(($appJson -join "`n"), 'ocid1\.generativeaihostedapplication\.oc1\.[A-Za-z0-9._-]+')).Value; if (-not $appId) { Fail 1 'Could not extract the Hosted Application OCID.' }; Write-Output "Created Hosted Application: $appId"
$deployJson = & oci --region $env:OCI_REGION --output json generative-ai hosted-deployment create-hosted-deployment-single-docker-artifact --hosted-application-id $appId --active-artifact-container-uri $uri --active-artifact-tag $tag --display-name $env:OCI_HOSTED_DEPLOYMENT_NAME --compartment-id $compartment --wait-for-state SUCCEEDED --max-wait-seconds 1200
if ($LASTEXITCODE -ne 0) { Fail 1 'Hosted Deployment creation failed.' }; $deployId = ([regex]::Match(($deployJson -join "`n"), 'ocid1\.generativeaihosteddeployment\.oc1\.[A-Za-z0-9._-]+')).Value; if (-not $deployId) { Fail 1 'Could not extract the Hosted Deployment OCID.' }; Write-Output "Created Hosted Deployment: $deployId"
