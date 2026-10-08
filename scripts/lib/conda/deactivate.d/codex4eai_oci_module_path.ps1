# Purpose: Restore the PowerShell module path saved during Conda activation.
# Requires: PowerShell 7.4+ and the matching project activation hook.
# Inputs: Saved process environment values. Side effect: Restores PSModulePath.
# Usage: Installed into the environment's etc/conda/deactivate.d by the installer.
if ($env:CODEX4EAI_PS_MODULE_PATH_SAVED -ne '1') { return }

if ($env:CODEX4EAI_PS_MODULE_PATH_PRESENT -eq '1') {
    $env:PSModulePath = $env:CODEX4EAI_PS_MODULE_PATH_VALUE
} else {
    Remove-Item Env:PSModulePath -ErrorAction SilentlyContinue
}
Remove-Item Env:CODEX4EAI_PS_MODULE_PATH_VALUE -ErrorAction SilentlyContinue
Remove-Item Env:CODEX4EAI_PS_MODULE_PATH_PRESENT -ErrorAction SilentlyContinue
Remove-Item Env:CODEX4EAI_PS_MODULE_PATH_SAVED -ErrorAction SilentlyContinue
if ($env:CODEX4EAI_SKIP_WINPS_CONDA_INIT_PRESENT -eq '1') {
    $env:CODEX4EAI_SKIP_WINPS_CONDA_INIT = $env:CODEX4EAI_SKIP_WINPS_CONDA_INIT_VALUE
} else {
    Remove-Item Env:CODEX4EAI_SKIP_WINPS_CONDA_INIT -ErrorAction SilentlyContinue
}
Remove-Item Env:CODEX4EAI_SKIP_WINPS_CONDA_INIT_VALUE -ErrorAction SilentlyContinue
Remove-Item Env:CODEX4EAI_SKIP_WINPS_CONDA_INIT_PRESENT -ErrorAction SilentlyContinue
