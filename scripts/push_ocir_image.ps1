<# .SYNOPSIS Plans or, with -Push, pushes a manifest-defined local image to OCIR. Mirrors scripts/push_ocir_image.sh (same options and exit codes: 0 success; 1 missing tool; 10 local image unavailable or wrong platform; 64 invalid input). Windows-only extra: -ContainerEngine. It never creates an OCI repository and never logs in. #>
[CmdletBinding()]
param(
  [string]$Manifest,
  [string]$Tag,
  [switch]$Plan,
  [switch]$Push,
  [ValidateSet('Auto', 'Docker', 'Podman')]
  [string]$ContainerEngine = 'Auto',
  [switch]$Help
)
$usage = 'Usage: .\scripts\push_ocir_image.ps1 [-Plan|-Push] -Manifest PATH -Tag MAJOR.MINOR.PATCH [-ContainerEngine Auto|Docker|Podman]'
if ($Help) { Write-Output $usage; exit 0 }
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if ($PSVersionTable.PSVersion -lt [version]'7.4') { [Console]::Error.WriteLine("PowerShell 7.4 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
if ($Plan -and $Push) { Fail 64 'Choose -Plan or -Push, not both.' }
if (-not $Manifest -or -not $Tag) { [Console]::Error.WriteLine($usage); exit 64 }
foreach ($tool in 'oci', 'python') { if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { Fail 1 "Missing required tool: $tool" } }
foreach ($name in 'OCI_REGION', 'OCIR_TENANCY_NAMESPACE', 'OCIR_USERNAME') { if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue).Value) { Fail 64 "Missing required environment variable: $name" } }
$scriptDir = Split-Path -Parent $PSCommandPath
Import-Module (Join-Path $scriptDir 'lib/ContainerEngine.psm1') -Force
Import-Module (Join-Path $scriptDir 'lib/AgentManifest.psm1') -Force
try { $engine = Resolve-ContainerEngine -ContainerEngine $ContainerEngine } catch { Fail 1 $_.Exception.Message }
$engineCommand = $engine.ToLowerInvariant()

$imageName = Get-ManifestField -Manifest $Manifest -Field name; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$repository = Get-ManifestField -Manifest $Manifest -Field publish.repository; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Get-ManifestDeploymentName -Manifest $Manifest -Tag $Tag | Out-Null; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$sourceImage = "${imageName}:$Tag"
$platform = (& $engineCommand image inspect $sourceImage --format '{{.Os}}/{{.Architecture}}' 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { Fail 10 "Local image is unavailable: $sourceImage" }
if ($platform -ne 'linux/amd64') { Fail 10 "Image platform must be linux/amd64; found $platform." }
$registry = (& (Join-Path $scriptDir 'resolve_ocir_registry.ps1') | Out-String).Trim(); if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$targetImage = "$registry/$($env:OCIR_TENANCY_NAMESPACE)/${repository}:$Tag"

Write-Output "Mode: $(if ($Push) { 'push' } else { 'plan' })"
Write-Output "Container engine: $engine"
Write-Output "Source image: $sourceImage ($platform)"
Write-Output "OCIR target: $targetImage"
Write-Output "Repository prerequisite: .\scripts\ensure_ocir_repository.ps1 -Repository $repository"
if (-not $Push) {
  Write-Output "Plan complete. Authenticate with '$engineCommand login' and re-run with -Push only after explicit authorization."
  exit 0
}
& $engineCommand tag $sourceImage $targetImage
if ($LASTEXITCODE -ne 0) { Fail $LASTEXITCODE "$engine tag failed." }
& $engineCommand push $targetImage
if ($LASTEXITCODE -ne 0) { Fail $LASTEXITCODE "$engine push failed." }
Write-Output "Pushed OCIR artifact: $targetImage"
