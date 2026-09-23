Set-StrictMode -Version Latest

function Test-ContainerEngine {
    param(
        [Parameter(Mandatory)]
        [ValidateSet('Docker', 'Podman')]
        [string]$Engine
    )

    $command = $Engine.ToLowerInvariant()
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        return $false
    }

    & $command info *> $null
    return ($LASTEXITCODE -eq 0)
}

function Resolve-ContainerEngine {
    param(
        [ValidateSet('Auto', 'Docker', 'Podman')]
        [string]$ContainerEngine = 'Auto'
    )

    if ($ContainerEngine -ne 'Auto') {
        if (-not (Test-ContainerEngine -Engine $ContainerEngine)) {
            throw "$ContainerEngine is not usable. Ensure its CLI is on PATH and its engine is running."
        }
        return $ContainerEngine
    }

    $usable = @(@('Docker', 'Podman') | Where-Object {
        Test-ContainerEngine -Engine $_
    })

    if ($usable.Count -eq 1) {
        return $usable[0]
    }
    if ($usable.Count -eq 0) {
        throw 'No usable container engine was found. Install or start Docker Desktop or Podman, then use -ContainerEngine Docker or Podman.'
    }
    throw 'Both Docker and Podman are usable. Choose explicitly with -ContainerEngine Docker or -ContainerEngine Podman.'
}

Export-ModuleMember -Function Resolve-ContainerEngine, Test-ContainerEngine
