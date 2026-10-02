<#
.SYNOPSIS
Plans or, with -Apply, releases a manifest-defined OCI Generative AI Hosted Application image.

.DESCRIPTION
Prerequisites: PowerShell 7.4+, OCI CLI authentication, and Python with PyYAML.
Inputs: -Manifest PATH -Tag MAJOR.MINOR.PATCH; -TimeoutSeconds defaults to 1800.
-ReplaceFailed selects only a FAILED deployment; -Apply authorizes mutations.
Without -Apply it performs OCI reads only. With -Apply it creates missing resources, adds and
activates artifacts in place, or explicitly replaces a FAILED deployment.
OCI_DEPLOY_POLL_INTERVAL sets polling seconds (default 30; intended for offline tests).
Usage: deploy_hosted_application.ps1 [-Plan|-Apply] -Manifest PATH -Tag TAG
  [-TimeoutSeconds SECONDS] [-ReplaceFailed].
#>
[CmdletBinding()]
param(
    [string]$Manifest,
    [string]$Tag,
    [switch]$Plan,
    [switch]$Apply,
    [string]$TimeoutSeconds = "1800",
    [switch]$ReplaceFailed,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$exitInvalidInput = 64
$exitExistingResource = 20
$waitSeconds = 1200
$artifactLimit = 20
$pollInterval = if ($env:OCI_DEPLOY_POLL_INTERVAL) { $env:OCI_DEPLOY_POLL_INTERVAL } else { "30" }
$usage = "Usage: $PSCommandPath [-Plan|-Apply] -Manifest PATH -Tag MAJOR.MINOR.PATCH [-TimeoutSeconds SECONDS] [-ReplaceFailed]"

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

    $output = & oci @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) {
        Fail 1 "OCI CLI command failed (exit $LASTEXITCODE). Check the OCI operation before retrying."
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

# Read lifecycle and artifact information from the selected deployment.
function Read-DeploymentDetails {
    $deploymentJson = Invoke-Oci @(
        '--region', $region, '--output', 'json', 'generative-ai', 'hosted-deployment', 'get',
        '--hosted-deployment-id', $deploymentId
    )
    $deploymentData = ($deploymentJson | ConvertFrom-Json).data
    $script:deploymentState = $deploymentData.'lifecycle-state'
    $script:deploymentAge = Get-ResourceAge $deploymentData
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
function Get-ResourceAge {
    param($Data)
    try {
        if (-not $Data.'time-created') { return 'unknown' }
        $created = [DateTimeOffset]::Parse([string]$Data.'time-created')
        return "$([Math]::Max(0, [int]([DateTimeOffset]::UtcNow - $created).TotalSeconds))s"
    } catch { return 'unknown' }
}

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
    if ($releaseCase -eq 'Creation in progress') {
        Write-Output "${resourceKind}: $resourceId (CREATING; age $resourceAge)."
    } elseif ($releaseCase -in @('Failed deployment', 'Replace failed deployment')) {
        Write-Output "Failed Hosted Deployment: $deploymentId"
        foreach ($line in $failureReason) { Write-Output $line }
        if ($releaseCase -eq 'Failed deployment') {
            Write-Output 'Request replacement with --replace-failed (Bash) or -ReplaceFailed (PowerShell).'
        } else {
            Write-Output "Delete FAILED Hosted Deployment: $deploymentId"
            Write-Output "Create Hosted Deployment with tag: $Tag"
        }
    }
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

function Resolve-MutationId {
    param([string]$Kind, [string]$Response)
    $id = Get-MutationId -Response $Response
    if (-not $id) {
        $id = Find-MutatedResource -Kind $Kind -Region $region -CompartmentId $compartmentId `
            -ApplicationName $applicationName -ApplicationId $applicationId
        if (-not $id) {
            Fail 1 "$Kind create/delete response had no data.id and lookup found no unique resource. Check OCI before retrying."
        }
    }
    return $id
}

function New-HostedApplication {
    Write-Output "Creating Hosted Application with $deployProfile and Oracle-managed networking."
    $applicationOutput = Invoke-Oci @(
        '--region', $region, '--output', 'json', 'generative-ai', 'hosted-application', 'create',
        '--display-name', $applicationName, '--compartment-id', $compartmentId, '--inbound-auth-config',
        $inboundAuthJson, '--networking-config',
        '{"inboundNetworkingConfig":{"endpointMode":"PUBLIC"},"outboundNetworkingConfig":' +
        '{"networkMode":"MANAGED"}}', '--environment-variables', $environmentJson
    )
    $script:applicationId = Resolve-MutationId 'Hosted Application' $applicationOutput
    $script:applicationWorkRequestId = Get-MutationWorkRequestId -Response $applicationOutput
    Write-Output "Created Hosted Application: $applicationId"
    $result = Wait-HostedResource -Kind 'Hosted Application' -ResourceId $applicationId `
        -Operation create -Region $region -TimeoutSeconds $TimeoutSeconds -PollInterval $pollInterval
    if ($result -ne 0) { exit $result }
}

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
        '--compartment-id', $compartmentId
    )
    $script:deploymentId = Resolve-MutationId 'Hosted Deployment' $deploymentOutput
    $script:deploymentWorkRequestId = Get-MutationWorkRequestId -Response $deploymentOutput
    Write-Output "Created Hosted Deployment: $deploymentId"
    $result = Wait-HostedResource -Kind 'Hosted Deployment' -ResourceId $deploymentId `
        -Operation create -Region $region -TimeoutSeconds $TimeoutSeconds -PollInterval $pollInterval
    if ($result -ne 0) { exit $result }
}

if ($Help) {
    Show-Usage
    exit 0
}
if ($PSVersionTable.PSVersion -lt [version]'7.4') {
    Fail $exitInvalidInput "PowerShell 7.4 or later is required; current version is $($PSVersionTable.PSVersion)."
}
if ($TimeoutSeconds -notmatch '^[0-9]+$' -or $TimeoutSeconds -match '^0+$' -or `
    $pollInterval -notmatch '^[0-9]+$' -or $pollInterval -match '^0+$') {
    Fail $exitInvalidInput 'Timeout and polling interval must be positive integers.'
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
Import-Module (Join-Path $scriptDir 'lib/DeployWait.psm1') -Force
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
$env:OCI_DEPLOY_RUNTIME_JSON = $environmentJson
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
    $applicationData = ($applicationJson | ConvertFrom-Json).data
    $applicationState = $applicationData.'lifecycle-state'
    $applicationAge = Get-ResourceAge $applicationData
    if ($ReplaceFailed -and $applicationState -ne 'ACTIVE') {
        Fail $exitInvalidInput '--replace-failed requires a FAILED deployment.'
    }
    if ($applicationState -notin @('ACTIVE', 'CREATING')) {
        Fail $exitExistingResource "Existing Hosted Application must be ACTIVE to reuse; observed: $applicationState."
    }
    if ($applicationState -eq 'ACTIVE') { $applicationJson | & $env:OCI_AGENT_PYTHON (Join-Path $scriptDir 'agent_manifest.py') `
        inbound-auth-matches --manifest $Manifest | Out-Null }
    if ($applicationState -eq 'ACTIVE' -and $LASTEXITCODE -ne 0) {
        Fail $exitExistingResource (
            'The existing Hosted Application uses a different inbound authentication; ' +
            'changing authentication is not supported.'
        )
    }
    if ($applicationState -eq 'ACTIVE' -and -not (Test-ManifestRuntimeMatches -Manifest $Manifest -ApplicationJson $applicationJson)) {
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
        if ($ReplaceFailed -and $deploymentState -ne 'FAILED') {
            Fail $exitInvalidInput '--replace-failed requires a FAILED deployment.'
        }
        if ($deploymentState -notin @('ACTIVE', 'CREATING', 'FAILED')) {
            $message = "Hosted Deployment must be ACTIVE; observed: $deploymentState. "
            Fail $exitExistingResource ($message + 'Check it and retry.')
        }
        if ($deploymentState -eq 'CREATING') {
            $releaseCase = 'Creation in progress'
        } elseif ($deploymentState -eq 'FAILED') {
            $releaseCase = if ($ReplaceFailed) { 'Replace failed deployment' } else { 'Failed deployment' }
            $failureReason = @(Get-HostedWorkRequestErrors -Region $region -ResourceId $deploymentId)
        } elseif ($targetStatus -eq 'FAILED' -or $targetStatus -eq 'UPDATING') {
            $message = "Target artifact tag $Tag is $targetStatus. Check it and retry; "
            Fail $exitExistingResource ($message + 'no changes were made.')
        }
        if ($deploymentState -eq 'ACTIVE' -and $activeTag -eq $Tag) {
            $releaseCase = 'Already released'
        } elseif ($deploymentState -eq 'ACTIVE' -and -not $targetStatus) {
            if ($artifactCount -ge $artifactLimit) {
                $message = "Adding tag $Tag exceeds the artifact limit of $artifactLimit; "
                Fail $exitExistingResource ($message + 'no changes were made.')
            }
            $releaseCase = 'New version'
        } elseif ($deploymentState -eq 'ACTIVE' -and $targetStatus -eq 'INACTIVE') {
            $releaseCase = 'Return to a previous version'
        } elseif ($deploymentState -eq 'ACTIVE') {
            Fail $exitExistingResource "Target artifact tag $Tag has unsupported status: $targetStatus."
        }
    }
}

if ($ReplaceFailed -and $releaseCase -ne 'Replace failed deployment') {
    Fail $exitInvalidInput '--replace-failed requires a FAILED deployment.'
}
if ($applicationState -eq 'CREATING') {
    $releaseCase = 'Creation in progress'
    $resourceKind = 'Hosted Application'
    $resourceId = $applicationId
    $resourceAge = $applicationAge
} elseif ($releaseCase -eq 'Creation in progress') {
    $resourceKind = 'Hosted Deployment'
    $resourceId = $deploymentId
    $resourceAge = $deploymentAge
}
Write-Plan
if (-not $Apply) {
    Write-Output 'Plan complete. Re-run with -Apply only after explicit authorization.'
    exit 0
}

switch ($releaseCase) {
    'Creation in progress' {
        $result = Wait-HostedResource -Kind $resourceKind -ResourceId $resourceId `
            -Operation create -Region $region -TimeoutSeconds $TimeoutSeconds -PollInterval $pollInterval
        if ($result -ne 0) { exit $result }
    }
    'Failed deployment' { exit $exitExistingResource }
    'Replace failed deployment' {
        $deleteOutput = Invoke-Oci @(
            '--region', $region, '--output', 'json', 'generative-ai', 'hosted-deployment',
            'delete', '--hosted-deployment-id', $deploymentId, '--force'
        )
        $deletedId = Get-MutationId -Response $deleteOutput
        $deletionWorkRequestId = Get-MutationWorkRequestId -Response $deleteOutput
        if (-not $deletedId) {
            $deletedId = Find-MutatedResource -Kind 'Hosted Deployment' -Region $region `
                -CompartmentId $compartmentId -ApplicationName $applicationName `
                -ApplicationId $applicationId
        }
        if ($deletedId -and $deletedId -ne $deploymentId) {
            Fail 1 'Delete response identifies a different deployment.'
        }
        $result = Wait-HostedResource -Kind 'Hosted Deployment' -ResourceId $deploymentId `
            -Operation delete -Region $region -TimeoutSeconds $TimeoutSeconds -PollInterval $pollInterval
        if ($result -ne 0) { exit $result }
        New-FirstRelease
    }
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
