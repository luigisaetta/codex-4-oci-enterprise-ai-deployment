<# .SYNOPSIS Verifies a local linux/amd64 image using read-only container smoke tests. #>
[CmdletBinding()]
param(
  [string]$Image,
  [ValidateSet('Auto', 'Docker', 'Podman')]
  [string]$ContainerEngine = 'Auto',
  [int]$Port = 8080,
  [int]$TimeoutSeconds = 90,
  [string]$PostPath,
  [string]$PostBody,
  [switch]$Help
)
if ($Help) { Write-Output 'Usage: .\scripts\verify_image.ps1 -Image NAME:TAG [-ContainerEngine Auto|Docker|Podman] [-Port 8080] [-TimeoutSeconds 90] [-PostPath /PATH -PostBody JSON]'; exit 0 }

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion -lt [version]'7.2') {
  [Console]::Error.WriteLine("PowerShell 7.2 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again.")
  exit 64
}
$containerId = $null; $result = 'FAIL'; $architecture = 'unknown'; $runtimeArch = 'unverified'; $ready = 'unavailable'; $digest = 'unavailable'
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
if (-not $Image -or $Port -lt 1 -or $Port -gt 65535 -or $TimeoutSeconds -lt 1 -or (($PostPath -and -not $PostBody) -or ($PostBody -and -not $PostPath)) -or ($PostPath -and -not $PostPath.StartsWith('/'))) { Fail 64 'Invalid image, port, timeout, or POST path/body pair.' }

$scriptDir = Split-Path -Parent $PSCommandPath
Import-Module (Join-Path $scriptDir 'lib/ContainerEngine.psm1') -Force
try { $engine = Resolve-ContainerEngine -ContainerEngine $ContainerEngine } catch { Fail 1 $_.Exception.Message }
$engineCommand = $engine.ToLowerInvariant()

try {
  $architecture = & $engineCommand image inspect --format '{{.Os}}/{{.Architecture}}' $Image
  if ($LASTEXITCODE -ne 0 -or $architecture -ne 'linux/amd64') { Fail 10 "Expected linux/amd64, observed: $architecture" }
  $digest = & $engineCommand image inspect --format '{{if .RepoDigests}}{{index .RepoDigests 0}}{{else}}unavailable (local image; no repository digest){{end}}' $Image
  if ($LASTEXITCODE -ne 0) { $digest = 'unavailable (inspection failed)' }
  $runtimeArch = ((& $engineCommand run --rm --platform linux/amd64 $Image uname -m 2>$null) | Out-String).Trim()
  if ($LASTEXITCODE -ne 0) { Fail 11 'Runtime architecture command failed.' }
  if ($runtimeArch -ne 'x86_64') { Fail 11 "Expected x86_64, observed: $runtimeArch" }
  $containerId = & $engineCommand run -d --platform linux/amd64 --read-only --tmpfs /tmp -p "127.0.0.1:$Port`:8080" $Image
  if ($LASTEXITCODE -ne 0) { Fail 12 'Container startup failed.' }

  $handler = [System.Net.Http.HttpClientHandler]::new()
  $handler.UseProxy = $false
  $http = [System.Net.Http.HttpClient]::new($handler)
  $http.Timeout = [TimeSpan]::FromSeconds(5)
  try {
    $started = Get-Date; $base = "http://127.0.0.1:$Port"
    do {
      $health = $null; $readiness = $null
      try { $response = $http.GetAsync("$base/health").GetAwaiter().GetResult(); $health = [int]$response.StatusCode; $response.Dispose() } catch {}
      try { $response = $http.GetAsync("$base/ready").GetAwaiter().GetResult(); $readiness = [int]$response.StatusCode; $response.Dispose() } catch {}
      if ($health -eq 200 -and $readiness -eq 200) { $ready = [int]((Get-Date) - $started).TotalSeconds; break }
      Start-Sleep -Seconds 1
    } while (((Get-Date) - $started).TotalSeconds -lt $TimeoutSeconds)
    if ($ready -eq 'unavailable') { & $engineCommand logs $containerId; Fail 12 "Health/readiness timed out after $TimeoutSeconds seconds." }
    if ($PostPath) {
      try {
        $content = [System.Net.Http.StringContent]::new($PostBody, [System.Text.Encoding]::UTF8, 'application/json')
        $response = $http.PostAsync("$base$PostPath", $content).GetAwaiter().GetResult()
        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $status = [int]$response.StatusCode
        $response.Dispose()
      } catch { Fail 13 'Functional POST request failed.' }
      Write-Output $body
      if ($status -ne 200) { Fail 13 "POST returned HTTP $status, expected 200." }
    }
    $result = 'PASS'
  } finally {
    $http.Dispose()
  }
} finally {
  if ($containerId) { & $engineCommand rm -f $containerId *> $null }
  Write-Output "Engine=$engine Image=$Image digest=$digest architecture=$architecture runtime_arch=$runtimeArch readiness_seconds=$ready result=$result"
}
if ($result -ne 'PASS') { exit 12 }
