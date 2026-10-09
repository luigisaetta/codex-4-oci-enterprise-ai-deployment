<#
.SYNOPSIS
Installs OCI CLI module-path hooks in the active project Conda environment.
.DESCRIPTION
Requires PowerShell 7.4+ and the activated codex-4-oci-enterprise-ai-deployment
environment. Copies the repository's activation and deactivation hooks into
that environment. Guards a Conda-generated block in the current user's Windows
PowerShell profile when present, saving a backup first. Refuses to replace
differing existing hooks unless -Update is specified. Does not call OCI or
alter credentials, file ACLs, or machine-wide PowerShell profiles.
.EXAMPLE
conda activate codex-4-oci-enterprise-ai-deployment
./scripts/install_oci_powershell_hook.ps1
#>
[CmdletBinding()]
param([switch]$Update)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion -lt [version]'7.4') {
    throw 'PowerShell 7.4 or later is required.'
}
if ($env:CONDA_DEFAULT_ENV -ne 'codex-4-oci-enterprise-ai-deployment' -or
    -not $env:CONDA_PREFIX) {
    throw 'Activate the codex-4-oci-enterprise-ai-deployment Conda environment first.'
}

$sourceRoot = Join-Path $PSScriptRoot 'lib/conda'
$targets = @(
    @{ Name = 'activate.d'; Source = Join-Path $sourceRoot 'activate.d/codex4eai_oci_module_path.ps1' },
    @{ Name = 'deactivate.d'; Source = Join-Path $sourceRoot 'deactivate.d/codex4eai_oci_module_path.ps1' }
)
foreach ($item in $targets) {
    $item.Destination = Join-Path $env:CONDA_PREFIX "etc/conda/$($item.Name)/codex4eai_oci_module_path.ps1"
    if (Test-Path -LiteralPath $item.Destination) {
        $sourceHash = (Get-FileHash -LiteralPath $item.Source -Algorithm SHA256).Hash
        $targetHash = (Get-FileHash -LiteralPath $item.Destination -Algorithm SHA256).Hash
        if ($sourceHash -ne $targetHash -and -not $Update) {
            throw "Existing activation hook differs: $($item.Destination). Review it before using -Update."
        }
    }
}

$windowsProfile = (& powershell.exe -NoProfile -Command '$PROFILE.CurrentUserAllHosts').Trim()
if ($LASTEXITCODE -ne 0 -or -not $windowsProfile) {
    throw 'Could not locate the current-user Windows PowerShell profile.'
}
if (Test-Path -LiteralPath $windowsProfile) {
    $profileText = [System.IO.File]::ReadAllText($windowsProfile)
    $condaBlock = [regex]::Matches($profileText, '(?m)^#region conda initialize\r?\n.*?^#endregion', 'Singleline')
    if ($condaBlock.Count -gt 1) {
        throw 'Multiple Conda initialization blocks found in the Windows PowerShell profile; review it manually.'
    }
    if ($condaBlock.Count -eq 1 -and
        -not $profileText.Contains('CODEX4EAI_SKIP_WINPS_CONDA_INIT')) {
        $backupPath = "$windowsProfile.codex4eai-backup-$(Get-Date -Format yyyyMMddHHmmss)-$([guid]::NewGuid().ToString('N').Substring(0, 8))"
        Copy-Item -LiteralPath $windowsProfile -Destination $backupPath
        $block = $condaBlock[0]
        $guarded = "if (`$env:CODEX4EAI_SKIP_WINPS_CONDA_INIT -ne '1') {`r`n" +
            $block.Value + "`r`n}"
        $updated = $profileText.Substring(0, $block.Index) + $guarded +
            $profileText.Substring($block.Index + $block.Length)
        [System.IO.File]::WriteAllText(
            $windowsProfile, $updated, [System.Text.UTF8Encoding]::new($false)
        )
        Write-Output "Guarded Windows PowerShell Conda initialization; backup: $backupPath"
    }
}
foreach ($item in $targets) {
    $targetDir = Split-Path -Parent $item.Destination
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    Copy-Item -LiteralPath $item.Source -Destination $item.Destination -Force
}
Write-Output 'Installed OCI CLI activation hooks in the active Conda environment.'
Write-Output 'Open a fresh PowerShell 7 window, activate the environment, then run: oci os ns get'
