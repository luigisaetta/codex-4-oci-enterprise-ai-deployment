<# .SYNOPSIS Verifies a local linux/amd64 image using read-only container smoke tests. Mirrors scripts/verify_image.sh (same options and exit codes: 0 pass; 1 missing tools or daemon; 10 image architecture; 11 runtime architecture; 12 startup/readiness/cleanup failure; 13 functional check failure; 64 invalid arguments). Windows-only extra: -ContainerEngine. #>
[CmdletBinding()]
param(
  [string]$Manifest,
  [string]$Tag,
  [string]$Image,
  [int]$Port = 8080,
  [int]$TimeoutSeconds = 90,
  [string]$PostPath,
  [string]$PostBody,
  [ValidateSet('Auto', 'Docker', 'Podman')]
  [string]$ContainerEngine = 'Auto',
  [switch]$Help
)
$usage = @'
Usage: .\scripts\verify_image.ps1 -Manifest PATH -Tag VERSION [-Port 8080] [-TimeoutSeconds 90] [-ContainerEngine Auto|Docker|Podman]
   or: .\scripts\verify_image.ps1 -Image NAME:TAG [-Port 8080] [-TimeoutSeconds 90] [-PostPath /PATH -PostBody JSON] [-ContainerEngine Auto|Docker|Podman]
'@
if ($Help) { Write-Output $usage; exit 0 }
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if ($PSVersionTable.PSVersion -lt [version]'7.4') { [Console]::Error.WriteLine("PowerShell 7.4 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
$scriptDir = Split-Path -Parent $PSCommandPath
Import-Module (Join-Path $scriptDir 'lib/ContainerEngine.psm1') -Force
Import-Module (Join-Path $scriptDir 'lib/AgentManifest.psm1') -Force

$bodyGiven = $PSBoundParameters.ContainsKey('PostBody')
if ($Manifest) {
  if ($Image -or $PostPath -or $bodyGiven -or -not $Tag) { Fail 64 '-Manifest requires -Tag and cannot be combined with -Image or legacy POST options.' }
  if (-not (Test-PythonAvailable)) { Fail 1 'Python is required to read the agent manifest.' }
  $imageName = Get-ManifestField -Manifest $Manifest -Field name; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  Get-ManifestDeploymentName -Manifest $Manifest -Tag $Tag | Out-Null; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  $Image = "${imageName}:$Tag"
} elseif ($Tag) {
  Fail 64 '-Tag requires -Manifest.'
}
if (-not $Image -or $Image.StartsWith('-') -or $Port -lt 1 -or $Port -gt 65535 -or $TimeoutSeconds -lt 1) { [Console]::Error.WriteLine($usage); exit 64 }
if (($PostPath -and (-not $PostPath.StartsWith('/') -or -not $bodyGiven)) -or (-not $PostPath -and $bodyGiven)) { Fail 64 'Supply -PostPath /PATH and -PostBody JSON together.' }
try { $engine = Resolve-ContainerEngine -ContainerEngine $ContainerEngine } catch { Fail 1 $_.Exception.Message }
$engineCommand = $engine.ToLowerInvariant()

$workDir = Join-Path ([System.IO.Path]::GetTempPath()) ('oci-agent-verify-' + [System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $workDir | Out-Null
$containerId = $null; $http = $null; $result = 'FAIL'; $exitCode = 0
$architecture = 'unknown'; $runtimeArch = 'unverified'; $readiness = 'unavailable'; $digest = 'unavailable'
# Stop-Verification records the exit code and unwinds to the cleanup block below; it never calls exit.
function Stop-Verification([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); $script:exitCode = $Code; throw 'verification-stopped' }
try {
  $architecture = (& $engineCommand image inspect --format '{{.Os}}/{{.Architecture}}' $Image 2>$null | Out-String).Trim()
  if ($LASTEXITCODE -ne 0) { $architecture = 'unknown'; Stop-Verification 10 'Could not inspect image platform.' }
  if ($architecture -ne 'linux/amd64') { Stop-Verification 10 "Expected linux/amd64, observed: $architecture" }
  # Locally built images need not have a registry manifest digest. Do not invent one.
  $digest = (& $engineCommand image inspect --format '{{if .RepoDigests}}{{index .RepoDigests 0}}{{else}}unavailable (local image; no repository digest){{end}}' $Image | Out-String).Trim()
  if ($LASTEXITCODE -ne 0) { $digest = 'unavailable'; Stop-Verification 10 'Could not inspect image digest.' }

  $unameOutput = & $engineCommand run --rm --platform linux/amd64 $Image uname -m 2>&1
  $unameStatus = $LASTEXITCODE
  $runtimeArch = ((@($unameOutput) | ForEach-Object { "$_" }) -join ' ').Trim()
  if ($unameStatus -ne 0) {
    if ($unameStatus -eq 127 -and $runtimeArch -match 'uname.*(not found|no such file)') {
      $runtimeArch = 'skipped'
      [Console]::Error.WriteLine('Warning: uname is absent; runtime architecture check skipped.')
    } else {
      Stop-Verification 11 "Runtime architecture command failed (exit $unameStatus): $runtimeArch"
    }
  } elseif ($runtimeArch -ne 'x86_64') {
    Stop-Verification 11 "Expected x86_64, observed: $runtimeArch"
  }

  $started = Get-Date
  $runArgs = @('run', '-d', '--platform', 'linux/amd64', '--read-only', '--tmpfs', '/tmp')
  if ($Manifest) {
    $runtimeReport = Get-ManifestRuntimeEnvironment -Manifest $Manifest -Format local-report
    if ($LASTEXITCODE -ne 0) { Stop-Verification $LASTEXITCODE 'Could not resolve the manifest runtime environment.' }
    if ($runtimeReport) { Write-Output $runtimeReport }
    $runtimeJson = Get-ManifestRuntimeEnvironment -Manifest $Manifest -Format local-json
    if ($LASTEXITCODE -ne 0) { Stop-Verification $LASTEXITCODE 'Could not resolve the manifest runtime environment.' }
    if ($runtimeJson -ne '[]') {
      $envFile = Join-Path $workDir 'runtime.env'
      $envLines = [string[]]@($runtimeJson | ConvertFrom-Json | ForEach-Object { "$($_.name)=$($_.value)" })
      [System.IO.File]::WriteAllLines($envFile, $envLines, [System.Text.UTF8Encoding]::new($false))
      $runArgs += @('--env-file', $envFile)
    }
  }
  # Publish on the IPv4 loopback only: avoids IPv4/IPv6 localhost ambiguity and keeps the port off the LAN.
  $runArgs += @('-p', "127.0.0.1:${Port}:8080", $Image)
  $startOutput = ((@(& $engineCommand @runArgs 2>&1) | ForEach-Object { "$_" }) -join "`n").Trim()
  if ($LASTEXITCODE -ne 0) { Stop-Verification 12 "Container startup failed: $startOutput" }
  $containerId = $startOutput

  $handler = [System.Net.Http.HttpClientHandler]::new()
  $handler.UseProxy = $false
  $http = [System.Net.Http.HttpClient]::new($handler)
  $http.Timeout = [TimeSpan]::FromSeconds(5)
  $base = "http://127.0.0.1:$Port"
  do {
    $health = $null; $ready = $null
    try { $response = $http.GetAsync("$base/health").GetAwaiter().GetResult(); $health = [int]$response.StatusCode; $response.Dispose() } catch { }
    try { $response = $http.GetAsync("$base/ready").GetAwaiter().GetResult(); $ready = [int]$response.StatusCode; $response.Dispose() } catch { }
    if ($health -eq 200 -and $ready -eq 200) { $readiness = [int]((Get-Date) - $started).TotalSeconds; break }
    Start-Sleep -Seconds 1
  } while (((Get-Date) - $started).TotalSeconds -lt $TimeoutSeconds)
  if ("$readiness" -eq 'unavailable') { Stop-Verification 12 "Health/readiness timed out after $TimeoutSeconds seconds." }

  if ($Manifest) {
    Invoke-ManifestChecks -Manifest $Manifest -BaseUrl $base -TimeoutSeconds $TimeoutSeconds
    if ($LASTEXITCODE -ne 0) { Stop-Verification $LASTEXITCODE 'Manifest functional checks failed.' }
  } elseif ($PostPath) {
    try {
      $content = [System.Net.Http.StringContent]::new($PostBody, [System.Text.Encoding]::UTF8, 'application/json')
      $response = $http.PostAsync("$base$PostPath", $content).GetAwaiter().GetResult()
      $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
      $status = [int]$response.StatusCode
      $response.Dispose()
    } catch { Stop-Verification 13 'Functional POST request failed.' }
    Write-Output $body
    if ($status -ne 200) { Stop-Verification 13 "POST returned HTTP $status, expected 200." }
  }
  $result = 'PASS'
} catch {
  if ($_.Exception.Message -ne 'verification-stopped') { [Console]::Error.WriteLine($_.Exception.Message); $exitCode = 12 }
} finally {
  if ($http) { $http.Dispose() }
  if ($containerId) {
    if ($result -ne 'PASS') { & $engineCommand logs $containerId 2>&1 | ForEach-Object { [Console]::Error.WriteLine("$_") } }
    & $engineCommand rm -f $containerId *> $null
    if ($LASTEXITCODE -ne 0) {
      [Console]::Error.WriteLine("Could not remove owned container $containerId. Remove it manually.")
      if ($exitCode -eq 0) { $exitCode = 12 }
    }
  }
  Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue
  if ($exitCode -ne 0) { $result = 'FAIL' }
  Write-Output "Engine=$engine Image=$Image digest=$digest architecture=$architecture runtime_arch=$runtimeArch readiness_seconds=$readiness result=$result"
}
exit $exitCode
