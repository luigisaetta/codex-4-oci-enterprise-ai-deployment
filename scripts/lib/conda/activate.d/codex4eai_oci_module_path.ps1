# Purpose: Give OCI CLI's Windows PowerShell child compatible module paths.
# Requires: PowerShell 7.4+ and activation of the named project Conda environment.
# Inputs: Current process PSModulePath. Side effect: Replaces it until deactivation.
# Usage: Installed into the environment's etc/conda/activate.d by the installer.
if ($PSVersionTable.PSVersion -lt [version]'7.4') { return }
if ($env:CODEX4EAI_PS_MODULE_PATH_SAVED -eq '1') { return }

$priorModulePath = [Environment]::GetEnvironmentVariable('PSModulePath', 'Process')
if ($null -eq $priorModulePath) {
    $env:CODEX4EAI_PS_MODULE_PATH_PRESENT = '0'
} else {
    $env:CODEX4EAI_PS_MODULE_PATH_PRESENT = '1'
    $env:CODEX4EAI_PS_MODULE_PATH_VALUE = $priorModulePath
}
$env:CODEX4EAI_PS_MODULE_PATH_SAVED = '1'
$windowsModulePath = & powershell.exe -NoProfile -Command '(Get-Item Env:PSModulePath).Value'
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($windowsModulePath)) {
    . (Join-Path $PSScriptRoot '../deactivate.d/codex4eai_oci_module_path.ps1')
    throw 'Could not determine the Windows PowerShell module path for OCI CLI.'
}
$env:PSModulePath = $windowsModulePath.Trim()
$priorSkipFlag = [Environment]::GetEnvironmentVariable('CODEX4EAI_SKIP_WINPS_CONDA_INIT', 'Process')
if ($null -eq $priorSkipFlag) {
    $env:CODEX4EAI_SKIP_WINPS_CONDA_INIT_PRESENT = '0'
} else {
    $env:CODEX4EAI_SKIP_WINPS_CONDA_INIT_PRESENT = '1'
    $env:CODEX4EAI_SKIP_WINPS_CONDA_INIT_VALUE = $priorSkipFlag
}
$env:CODEX4EAI_SKIP_WINPS_CONDA_INIT = '1'
