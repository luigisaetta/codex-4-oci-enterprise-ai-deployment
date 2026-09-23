<# .SYNOPSIS Builds and loads only a linux/amd64 container image; it never pushes. #>
[CmdletBinding()]
param(
  [string]$Context,
  [string]$Dockerfile,
  [string]$Name,
  [string]$Tag,
  [ValidateSet('Auto', 'Docker', 'Podman')]
  [string]$ContainerEngine = 'Auto',
  [string]$Builder,
  [switch]$NoCache,
  [switch]$Help
)
if ($Help) { Write-Output 'Usage: .\scripts\build_image.ps1 -Context DIR -Dockerfile PATH -Name IMAGE -Tag MAJOR.MINOR.PATCH [-ContainerEngine Auto|Docker|Podman] [-Builder NAME] [-NoCache]'; exit 0 }
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion -lt [version]'7.2') { [Console]::Error.WriteLine("PowerShell 7.2 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
if (-not $Context -or -not $Dockerfile -or -not $Name -or -not $Tag) { Fail 64 'Context, Dockerfile, Name, and Tag are required.' }
if ($Tag -eq 'latest' -or $Tag -notmatch '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$' -or $Tag.Length -gt 128) { Fail 3 "Invalid tag ${Tag}: use MAJOR.MINOR.PATCH with an optional -suffix; latest is forbidden." }
if (-not (Test-Path -LiteralPath $Dockerfile -PathType Leaf) -or -not (Test-Path -LiteralPath $Context -PathType Container)) { Fail 4 "Dockerfile must be a file and build context must be a directory: $Dockerfile ; $Context" }
if (-not (Test-Path -LiteralPath (Join-Path $Context '.dockerignore') -PathType Leaf)) { [Console]::Error.WriteLine("Warning: $Context/.dockerignore is missing.") }
$scriptDir = Split-Path -Parent $PSCommandPath
Import-Module (Join-Path $scriptDir 'lib/ContainerEngine.psm1') -Force
try { $engine = Resolve-ContainerEngine -ContainerEngine $ContainerEngine } catch { Fail 1 $_.Exception.Message }
if ($engine -eq 'Podman' -and $Builder) { Fail 64 '-Builder is supported only with -ContainerEngine Docker.' }
& (Join-Path $scriptDir 'check_build_env.ps1') -ContainerEngine $engine -Builder $Builder
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$timeout = if ($env:BUILD_TIMEOUT_SECONDS) { $env:BUILD_TIMEOUT_SECONDS } else { '1800' }
if ($timeout -notmatch '^[1-9][0-9]*$' -or $timeout.Length -gt 7) { Fail 64 'BUILD_TIMEOUT_SECONDS must be a positive integer of at most 7 digits.' }
$buildArgs = if ($engine -eq 'Docker') {
  @('buildx','build','--platform','linux/amd64','--load','--provenance=false','--sbom=false','-f',$Dockerfile,'-t',"${Name}:$Tag")
} else {
  @('build','--platform','linux/amd64','-f',$Dockerfile,'-t',"${Name}:$Tag")
}
if ($Builder) { $buildArgs += @('--builder', $Builder) }
if ($NoCache) { $buildArgs += '--no-cache' }
$buildArgs += $Context
Write-Output ("Command: {0} {1}" -f $engine.ToLowerInvariant(), ($buildArgs -join ' '))
$log = Join-Path ([System.IO.Path]::GetTempPath()) ("oci-agent-build-$PID.log")
$started = Get-Date
try {
  $process = Start-Process -FilePath $engine.ToLowerInvariant() -ArgumentList $buildArgs -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError "$log.err"
  if (-not $process.WaitForExit([int]$timeout * 1000)) { $process.Kill($true); Fail 6 "Build exceeded BUILD_TIMEOUT_SECONDS=$timeout." }
  $process.WaitForExit()
  $process.Refresh()
  $exitCode = $process.ExitCode
  Get-Content -LiteralPath $log; if (Test-Path "$log.err") { Get-Content -LiteralPath "$log.err" }
  if ($exitCode -ne 0) { $content = (Get-Content -Raw $log -ErrorAction SilentlyContinue) + (Get-Content -Raw "$log.err" -ErrorAction SilentlyContinue); if ($content -match 'No matching distribution found|Could not find a version that satisfies') { Fail 5 'pip resolution failed. A compatible manylinux x86_64 wheel may be unavailable; no source-build fallback was attempted.' }; Fail 6 "$engine build failed (exit $exitCode)." }
  $details = & $engine.ToLowerInvariant() image inspect --format '{{.Id}} {{.Size}}' "${Name}:$Tag"; if ($LASTEXITCODE -ne 0) { Fail 6 'Build completed but the loaded image could not be inspected.' }
  Write-Output "Build time: $([int]((Get-Date) - $started).TotalSeconds) seconds"; Write-Output "Engine=$engine Image=$Name tag=$Tag image_id/size_bytes=$details"
} finally { Remove-Item -LiteralPath $log,"$log.err" -Force -ErrorAction SilentlyContinue }
