<#
.SYNOPSIS
Plans or, with -Apply, releases a manifest-defined OCI Generative AI Hosted Application image.

.DESCRIPTION
Without -Apply it performs OCI reads only. With -Apply it creates missing resources, or adds and
activates artifacts in place. It never deletes or replaces resources.
#>
[CmdletBinding()]
param(
    [string]$Manifest,
    [string]$Tag,
    [switch]$Plan,
    [switch]$Apply,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$exitInvalidInput = 64
$exitExistingResource = 20
$waitSeconds = 1200
$artifactLimit = 20
$usage = "Usage: $PSCommandPath [-Plan|-Apply] -Manifest PATH -Tag MAJOR.MINOR.PATCH"

# Print command-line usage.
function Show-Usage {
    Write-Output $usage
}

# Stop with a supplied exit code and message.
function Fail {
    param([int]$Code, [string]$Message)

    [Console]::Error.WriteLine($Message)
    exit $Code
}

# Invoke OCI and stop if it exits unsuccessfully.
function Invoke-Oci {
    param([string[]]$Arguments)

    $output = & oci @Arguments
    if ($LASTEXITCODE -ne 0) {
        Fail 1 "OCI CLI command failed (exit $LASTEXITCODE): oci $($Arguments -join ' ')"
    }
    return ((@($output) | ForEach-Object { "$_" }) -join "`n").Trim()
}

# Stop when a required setting is absent.
function Require-EnvironmentVariable {
    param([string]$Name)

    $value = (Get-Item "Env:$Name" -ErrorAction SilentlyContinue).Value
    if (-not $value) {
        Fail $exitInvalidInput "Missing required environment variable: $Name"
    }
}

# Extract exactly one OCID with the requested prefix from OCI JSON output.
function Get-SingleOcid {
    param([string]$Json, [string]$Prefix)

    $matches = [System.Collections.Generic.HashSet[string]]::new()
    function Find-OcidValues {
        param($Value)

        if ($null -eq $Value) {
            return
        }
        if ($Value -is [string]) {
            if ($Value.StartsWith($Prefix)) {
                [void]$matches.Add($Value)
            }
            return
        }
        if ($Value -is [System.Collections.IEnumerable]) {
            foreach ($item in $Value) {
                Find-OcidValues $item
            }
            return
        }
        foreach ($property in $Value.PSObject.Properties) {
            Find-OcidValues $property.Value
        }
    }

    Find-OcidValues ($Json | ConvertFrom-Json)
    if ($matches.Count -ne 1) {
        Fail 1 "Expected exactly one matching OCID; found $($matches.Count)."
    }
    return ($matches | Select-Object -First 1)
}

# Read lifecycle and artifact information from the selected deployment.
function Read-DeploymentDetails {
    $deploymentJson = Invoke-Oci @(
        '--region', $region, '--output', 'json', 'generative-ai', 'hosted-deployment', 'get',
        '--hosted-deployment-id', $deploymentId
    )
    $deploymentData = ($deploymentJson | ConvertFrom-Json).data
    $script:deploymentState = $deploymentData.'lifecycle-state'
    $script:activeTag = if ($deploymentData.'active-artifact') {
        $deploymentData.'active-artifact'.tag
    } else {
        ''
    }
    $script:artifactCount = @($deploymentData.artifacts).Count
    $script:targetStatus = ''
    foreach ($artifact in @($deploymentData.artifacts)) {
        if ($artifact.'container-uri' -eq $containerUri -and $artifact.tag -eq $Tag) {
            $script:targetStatus = $artifact.status
            break
        }
    }
}

# Print the release case and the OCI state that selected it.
function Write-Plan {
    $applicationAction = if ($applicationId) { 'reuse' } else { 'create' }
    $mode = if ($Apply) { 'apply' } else { 'plan' }
    Write-Output "Mode: $mode"
    Write-Output "OCIR artifact: ${containerUri}:$Tag"
    Write-Output "Compartment: $compartmentId"
    Write-Output "Hosted Application: $applicationName ($deployProfile; $applicationAction)"
    if ($deployProfile -eq 'public-idcs') {
        Write-Output 'Access: public endpoint, identity-domain token required'
        Write-Output "Identity domain URL: $domainUrl"
        Write-Output "Audience: $audience"
        Write-Output "Scope: $scope"
    } else {
        Write-Output 'Access: public unauthenticated endpoint.'
    }
    Write-Output "Release case: $releaseCase"
    Write-Output "Current active tag: $activeTag"
    Write-Output "Target tag: $Tag"
    Write-Output "Artifacts: $artifactCount/$artifactLimit"
    if ($applicationId) {
        Write-Output "Endpoint: unchanged for this application ($applicationId)."
    }
    if ($environmentReport) {
        Write-Output $environmentReport
    }
    Write-Output 'Container environment variables, managed storage, and custom networking are omitted.'
}

# Activate an existing artifact, wait for the work request, and confirm its tag.
function Activate-Artifact {
    $activeArtifact = @{
        artifactType = 'SIMPLE_DOCKER_ARTIFACT'
        containerUri = $containerUri
        tag = $Tag
    } | ConvertTo-Json -Compress
    # The skill plan and explicit -Apply authorization cover this mutation.
    $updateOutput = & oci @(
        '--region', $region, '--output', 'json', 'generative-ai', 'hosted-deployment', 'update',
        '--hosted-deployment-id', $deploymentId, '--active-artifact', $activeArtifact,
        '--wait-for-state', 'SUCCEEDED', '--wait-for-state', 'FAILED', '--max-wait-seconds',
        $waitSeconds, '--force'
    )
    if ($LASTEXITCODE -ne 0) {
        Fail 1 'Artifact activation failed: work-request status=unknown. See the OCI CLI error above.'
    }
    $updateOutput = ((@($updateOutput) | ForEach-Object { "$_" }) -join "`n").Trim()
    $workRequestStatus = ($updateOutput | ConvertFrom-Json).data.status
    Read-DeploymentDetails
    if ($workRequestStatus -eq 'FAILED' -or $activeTag -ne $Tag) {
        Fail 1 "Artifact activation failed: work-request status=$workRequestStatus; active tag=$activeTag."
    }
}

# Create the missing Hosted Application and report its identifier.
function New-HostedApplication {
    Write-Output "Creating Hosted Application with $deployProfile and Oracle-managed networking."
    $applicationOutput = Invoke-Oci @(
        '--region', $region, '--output', 'json', 'generative-ai', 'hosted-application', 'create',
        '--display-name', $applicationName, '--compartment-id', $compartmentId, '--inbound-auth-config',
        $inboundAuthJson, '--networking-config',
        '{"inboundNetworkingConfig":{"endpointMode":"PUBLIC"},"outboundNetworkingConfig":' +
        '{"networkMode":"MANAGED"}}', '--environment-variables', $environmentJson, '--wait-for-state',
        'SUCCEEDED', '--max-wait-seconds', $waitSeconds
    )
    $script:applicationId = Get-SingleOcid $applicationOutput 'ocid1.generativeaihostedapplication.'
    Write-Output "Created Hosted Application: $applicationId"
}

# Create the first deployment after creating or reusing its Hosted Application.
function New-FirstRelease {
    if (-not $applicationId) {
        New-HostedApplication
    } else {
        Write-Output "Reusing ACTIVE Hosted Application: $applicationId"
    }
    Write-Output 'Creating Hosted Deployment from the selected OCIR artifact.'
    $deploymentOutput = Invoke-Oci @(
        '--region', $region, '--output', 'json', 'generative-ai', 'hosted-deployment',
        'create-hosted-deployment-single-docker-artifact', '--hosted-application-id', $applicationId,
        '--active-artifact-container-uri', $containerUri, '--active-artifact-tag', $Tag,
        '--compartment-id', $compartmentId, '--wait-for-state', 'SUCCEEDED', '--max-wait-seconds',
        $waitSeconds
    )
    $script:deploymentId = Get-SingleOcid $deploymentOutput 'ocid1.generativeaihosteddeployment.'
    Write-Output "Created Hosted Deployment: $deploymentId"
}

if ($Help) {
    Show-Usage
    exit 0
}
if ($PSVersionTable.PSVersion -lt [version]'7.4') {
    Fail $exitInvalidInput "PowerShell 7.4 or later is required; current version is $($PSVersionTable.PSVersion)."
}
if ($Plan -and $Apply) {
    Fail $exitInvalidInput 'Choose -Plan or -Apply, not both.'
}
if (-not $Manifest -or -not $Tag) {
    [Console]::Error.WriteLine($usage)
    exit $exitInvalidInput
}
# A SemVer core with optional Docker-compatible prerelease identifiers, no build metadata.
$versionPattern = '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$'
if ($Tag -notmatch $versionPattern) {
    Fail $exitInvalidInput 'Tag must be semantic (MAJOR.MINOR.PATCH).'
}

$scriptDir = Split-Path -Parent $PSCommandPath
Import-Module (Join-Path $scriptDir 'lib/AgentManifest.psm1') -Force
Import-Module (Join-Path $scriptDir 'lib/ToolEnvironment.psm1') -Force
if (-not (Resolve-AgentPython)) {
    Fail 1 (
        'Python with PyYAML is required. Activate the Conda environment ' +
        'codex-4-oci-enterprise-ai-deployment or set OCI_AGENT_PYTHON.'
    )
}
$settingsResult = Import-TenancySettings -Keys @(
    'OCI_REGION', 'OCI_COMPARTMENT_NAME', 'OCIR_TENANCY_NAMESPACE'
)
if ($settingsResult -ne 0) {
    Fail $settingsResult 'Unable to load OCI tenancy settings.'
}
if (-not (Get-Command oci -ErrorAction SilentlyContinue)) {
    Fail 1 'Missing required tool: oci'
}
foreach ($name in 'OCI_REGION', 'OCI_COMPARTMENT_NAME', 'OCIR_TENANCY_NAMESPACE') {
    Require-EnvironmentVariable $name
}

$repository = Get-ManifestField -Manifest $Manifest -Field publish.repository
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$applicationName = Get-ManifestField -Manifest $Manifest -Field deploy.application_name
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$deployProfile = Get-ManifestField -Manifest $Manifest -Field deploy.profile
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$inboundAuthJson = & $env:OCI_AGENT_PYTHON (Join-Path $scriptDir 'agent_manifest.py') inbound-auth --manifest $Manifest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$inboundAuthJson = ((@($inboundAuthJson) | ForEach-Object { "$_" }) -join "`n").Trim()
$domainUrl = ''
$audience = ''
$scope = ''
if ($deployProfile -eq 'public-idcs') {
    $domainUrl = Get-ManifestField -Manifest $Manifest -Field deploy.auth.domain_url
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $audience = Get-ManifestField -Manifest $Manifest -Field deploy.auth.audience
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $scope = Get-ManifestField -Manifest $Manifest -Field deploy.auth.scope
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$environmentJson = Get-ManifestRuntimeEnvironment -Manifest $Manifest -Format oci-json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$environmentReport = Get-ManifestRuntimeEnvironment -Manifest $Manifest -Format report
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$registry = (& (Join-Path $scriptDir 'resolve_ocir_registry.ps1') | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$region = $env:OCI_REGION
$containerUri = "$registry/$($env:OCIR_TENANCY_NAMESPACE)/$repository"
$activeCompartments = 'data[?"lifecycle-state"==`ACTIVE`]'
$compartmentArgs = @(
    '--region', $region, 'iam', 'compartment', 'list', '--name', $env:OCI_COMPARTMENT_NAME,
    '--compartment-id-in-subtree', 'true', '--all'
)
$compartmentCount = Invoke-Oci ($compartmentArgs + @('--query', "length($activeCompartments)", '--raw-output'))
if ($compartmentCount -ne '1') {
    Fail 1 "Expected exactly one active compartment named `"$($env:OCI_COMPARTMENT_NAME)`"; found $compartmentCount."
}
$compartmentId = Invoke-Oci ($compartmentArgs + @('--query', "($activeCompartments)[0].id", '--raw-output'))
$nonDeletedQuery = 'data.items[?"lifecycle-state"!=`DELETED`]'
$applicationListArgs = @(
    '--region', $region, 'generative-ai', 'hosted-application-collection',
    'list-hosted-applications', '--compartment-id', $compartmentId, '--display-name',
    $applicationName, '--all'
)
$applicationCount = Invoke-Oci ($applicationListArgs + @(
    '--query', "length($nonDeletedQuery)", '--raw-output'
))
if ($applicationCount -ne '0' -and $applicationCount -ne '1') {
    $message = "Expected zero or one non-deleted Hosted Application named `"$applicationName`"; "
    Fail $exitExistingResource ($message + "found $applicationCount.")
}

$applicationId = ''
$deploymentId = ''
$activeTag = 'none'
$artifactCount = 0
$targetStatus = ''
$releaseCase = 'First release'
if ($applicationCount -eq '1') {
    $applicationId = Invoke-Oci ($applicationListArgs + @(
        '--query', "($nonDeletedQuery)[0].id", '--raw-output'
    ))
    $applicationJson = Invoke-Oci @(
        '--region', $region, '--output', 'json', 'generative-ai', 'hosted-application', 'get',
        '--hosted-application-id', $applicationId
    )
    $applicationState = ($applicationJson | ConvertFrom-Json).data.'lifecycle-state'
    if ($applicationState -ne 'ACTIVE') {
        Fail $exitExistingResource "Existing Hosted Application must be ACTIVE to reuse; observed: $applicationState."
    }
    $applicationJson | & $env:OCI_AGENT_PYTHON (Join-Path $scriptDir 'agent_manifest.py') `
        inbound-auth-matches --manifest $Manifest | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail $exitExistingResource (
            'The existing Hosted Application uses a different inbound authentication; ' +
            'changing authentication is not supported.'
        )
    }
    if (-not (Test-ManifestRuntimeMatches -Manifest $Manifest -ApplicationJson $applicationJson)) {
        Fail $exitExistingResource 'Existing Hosted Application runtime environment differs from the manifest.'
    }
    $deploymentListArgs = @(
        '--region', $region, 'generative-ai', 'hosted-deployment-collection',
        'list-hosted-deployments', '--compartment-id', $compartmentId, '--application-id',
        $applicationId, '--all'
    )
    $deploymentCount = Invoke-Oci ($deploymentListArgs + @(
        '--query', "length($nonDeletedQuery)", '--raw-output'
    ))
    if ($deploymentCount -ne '0' -and $deploymentCount -ne '1') {
        Fail $exitExistingResource "Expected zero or one non-deleted Hosted Deployment; found $deploymentCount."
    }
    if ($deploymentCount -eq '1') {
        $deploymentId = Invoke-Oci ($deploymentListArgs + @(
            '--query', "($nonDeletedQuery)[0].id", '--raw-output'
        ))
        Read-DeploymentDetails
        if ($deploymentState -ne 'ACTIVE') {
            $message = "Hosted Deployment must be ACTIVE; observed: $deploymentState. "
            Fail $exitExistingResource ($message + 'Check it and retry.')
        }
        if ($targetStatus -eq 'FAILED' -or $targetStatus -eq 'UPDATING') {
            $message = "Target artifact tag $Tag is $targetStatus. Check it and retry; "
            Fail $exitExistingResource ($message + 'no changes were made.')
        }
        if ($activeTag -eq $Tag) {
            $releaseCase = 'Already released'
        } elseif (-not $targetStatus) {
            if ($artifactCount -ge $artifactLimit) {
                $message = "Adding tag $Tag exceeds the artifact limit of $artifactLimit; "
                Fail $exitExistingResource ($message + 'no changes were made.')
            }
            $releaseCase = 'New version'
        } elseif ($targetStatus -eq 'INACTIVE') {
            $releaseCase = 'Return to a previous version'
        } else {
            Fail $exitExistingResource "Target artifact tag $Tag has unsupported status: $targetStatus."
        }
    }
}

Write-Plan
if (-not $Apply) {
    Write-Output 'Plan complete. Re-run with -Apply only after explicit authorization.'
    exit 0
}

switch ($releaseCase) {
    'Already released' {
        Write-Output "Tag $Tag is already active; no changes were made."
    }
    'First release' {
        New-FirstRelease
    }
    'New version' {
        $null = Invoke-Oci @(
            '--region', $region, 'generative-ai', 'hosted-deployment',
            'add-artifact-create-single-docker-artifact-details', '--hosted-deployment-id',
            $deploymentId, '--artifact-container-uri', $containerUri, '--artifact-tag', $Tag
        )
        Activate-Artifact
    }
    'Return to a previous version' {
        Activate-Artifact
    }
}
