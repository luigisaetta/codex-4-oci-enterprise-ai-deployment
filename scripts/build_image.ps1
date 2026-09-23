<# .SYNOPSIS Builds and loads only a linux/amd64 container image; it never pushes. Mirrors scripts/build_image.sh (same options and exit codes: 0 success; 1/2 preflight; 3 tag; 4 paths; 5 pip resolution; 6 build/timeout; 64 usage). Windows-only extra: -ContainerEngine. #>
[CmdletBinding()]
param(
  [string]$Manifest,
  [string]$Tag,
  [string]$Context,
  [string]$Dockerfile,
  [string]$Name,
  [string]$Builder,
  [switch]$NoCache,
  [ValidateSet('Auto', 'Docker', 'Podman')]
  [string]$ContainerEngine = 'Auto',
  [switch]$Help
)
$usage = @'
Usage: .\scripts\build_image.ps1 -Manifest PATH -Tag VERSION [-Builder NAME] [-NoCache] [-ContainerEngine Auto|Docker|Podman]
   or: .\scripts\build_image.ps1 -Context DIR -Dockerfile PATH -Name NAME -Tag VERSION [-Builder NAME] [-NoCache] [-ContainerEngine Auto|Docker|Podman]
'@
if ($Help) { Write-Output $usage; exit 0 }
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if ($PSVersionTable.PSVersion -lt [version]'7.4') { [Console]::Error.WriteLine("PowerShell 7.4 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = Split-Path -Parent $scriptDir
Import-Module (Join-Path $scriptDir 'lib/ContainerEngine.psm1') -Force
Import-Module (Join-Path $scriptDir 'lib/AgentManifest.psm1') -Force

if ($Manifest) {
  if ($Context -or $Dockerfile -or $Name) { Fail 64 '-Manifest cannot be combined with -Context, -Dockerfile, or -Name.' }
  if (-not (Test-PythonAvailable)) { Fail 1 'Python is required to read the agent manifest.' }
  $Context = Get-ManifestField -Manifest $Manifest -Field build.context; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  $Dockerfile = Get-ManifestField -Manifest $Manifest -Field build.dockerfile; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  $Name = Get-ManifestField -Manifest $Manifest -Field name; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  # Manifest paths are repository-root-relative regardless of the current directory.
  $Context = Join-Path $repoRoot $Context
  $Dockerfile = Join-Path $repoRoot $Dockerfile
}
if (-not $Context -or -not $Dockerfile -or -not $Name -or -not $Tag) { [Console]::Error.WriteLine($usage); exit 64 }
# A SemVer core with optional Docker-compatible prerelease identifiers, no build metadata.
if ($Tag -eq 'latest' -or $Tag -notmatch '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$' -or $Tag.Length -gt 128) { Fail 3 "Invalid tag ${Tag}: use MAJOR.MINOR.PATCH with an optional -suffix; latest is forbidden." }
if (-not (Test-Path -LiteralPath $Dockerfile -PathType Leaf) -or -not (Test-Path -LiteralPath $Context -PathType Container)) { Fail 4 "Dockerfile must be a file and build context must be a directory: $Dockerfile ; $Context" }
if (-not (Test-Path -LiteralPath (Join-Path $Context '.dockerignore') -PathType Leaf)) { [Console]::Error.WriteLine("Warning: $Context/.dockerignore is missing.") }
$timeout = if ($env:BUILD_TIMEOUT_SECONDS) { $env:BUILD_TIMEOUT_SECONDS } else { '1800' }
if ($timeout -notmatch '^[1-9][0-9]*$' -or $timeout.Length -gt 7) { Fail 64 'BUILD_TIMEOUT_SECONDS must be a positive integer of at most 7 digits.' }

try { $engine = Resolve-ContainerEngine -ContainerEngine $ContainerEngine } catch { Fail 1 $_.Exception.Message }
$engineCommand = $engine.ToLowerInvariant()
if ($engine -eq 'Podman' -and $Builder) { Fail 64 '-Builder is supported only with -ContainerEngine Docker.' }
& (Join-Path $scriptDir 'check_build_env.ps1') -ContainerEngine $engine -Builder $Builder
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Spec 001: local containerd storage produced an attestation index without these flags.
$buildArgs = if ($engine -eq 'Docker') {
  @('buildx', 'build', '--platform', 'linux/amd64', '--load', '--provenance=false', '--sbom=false', '-f', $Dockerfile, '-t', "${Name}:$Tag")
} else {
  @('build', '--platform', 'linux/amd64', '-f', $Dockerfile, '-t', "${Name}:$Tag")
}
if ($Builder) { $buildArgs += @('--builder', $Builder) }
if ($NoCache) { $buildArgs += '--no-cache' }
$buildArgs += $Context
Write-Output ("Command: {0} {1}" -f $engineCommand, ($buildArgs -join ' '))

# ProcessStartInfo.ArgumentList quotes each argument correctly (paths with spaces), unlike Start-Process -ArgumentList.
$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $engineCommand
foreach ($argument in $buildArgs) { $startInfo.ArgumentList.Add($argument) }
$startInfo.UseShellExecute = $false
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$started = Get-Date
$process = [System.Diagnostics.Process]::Start($startInfo)
$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()
$waitMilliseconds = [int][math]::Min([long]$timeout * 1000, [int]::MaxValue)
if (-not $process.WaitForExit($waitMilliseconds)) {
  try { $process.Kill($true) } catch { }
  $process.WaitForExit()
  Write-Output "Build time: $([int]((Get-Date) - $started).TotalSeconds) seconds"
  Fail 6 "Build exceeded BUILD_TIMEOUT_SECONDS=$timeout."
}
$process.WaitForExit()
$buildOutput = $stdoutTask.GetAwaiter().GetResult() + $stderrTask.GetAwaiter().GetResult()
if ($buildOutput) { Write-Output $buildOutput.TrimEnd() }
Write-Output "Build time: $([int]((Get-Date) - $started).TotalSeconds) seconds"
if ($process.ExitCode -ne 0) {
  if ($buildOutput -match 'No matching distribution found|Could not find a version that satisfies') {
    Fail 5 'A compatible manylinux x86_64 wheel may be unavailable, or the version may not exist. A remote amd64 builder or build tools would require a separately approved source-build policy; --only-binary remains mandatory here. No fallback was attempted.'
  }
  Fail 6 "$engine build failed (exit $($process.ExitCode))."
}
$details = (& $engineCommand image inspect --format '{{.Id}} {{.Size}}' "${Name}:$Tag" | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { Fail 6 'Build completed but the loaded image could not be inspected.' }
Write-Output "Engine=$engine Image=$Name tag=$Tag image_id/size_bytes=$details"
