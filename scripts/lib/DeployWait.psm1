# Shared OCI resource wait and response helpers for deploy_hosted_application.ps1.
# Requires PowerShell 7.4+, OCI CLI and a validated region. Performs read-only OCI calls.
function Get-MutationId {
    param([string]$Response)
    try {
        return ([string](($Response | ConvertFrom-Json -ErrorAction Stop).data.id))
    } catch {
        return ''
    }
}

function Get-MutationWorkRequestId {
    param([string]$Response)
    try {
        return ([string](($Response | ConvertFrom-Json -ErrorAction Stop).'opc-work-request-id'))
    } catch {
        return ''
    }
}

function Find-MutatedResource {
    param([string]$Kind, [string]$Region, [string]$CompartmentId,
          [string]$ApplicationName, [string]$ApplicationId)
    $query = 'data.items[?"lifecycle-state"!=`DELETED`]'
    if ($Kind -eq 'Hosted Application') {
        $lookupArgs = @('--region', $Region, 'generative-ai', 'hosted-application-collection',
            'list-hosted-applications', '--compartment-id', $CompartmentId,
            '--display-name', $ApplicationName, '--all')
    } else {
        $lookupArgs = @('--region', $Region, 'generative-ai', 'hosted-deployment-collection',
            'list-hosted-deployments', '--compartment-id', $CompartmentId,
            '--application-id', $ApplicationId, '--all')
    }
    $count = & oci @args --query "length($query)" --raw-output
    if ($LASTEXITCODE -ne 0 -or "$count" -ne '1') { return '' }
    $id = & oci @args --query "($query)[0].id" --raw-output
    if ($LASTEXITCODE -ne 0 -or -not "$id".StartsWith('ocid1.')) { return '' }
    return "$id"
}

function Get-HostedWorkRequestErrors {
    param([string]$Region, [string]$ResourceId)
    $response = & oci --region $Region --output json generative-ai work-request list `
        --resource-id $ResourceId --status FAILED 2>$null
    if ($LASTEXITCODE -ne 0) { return "No FAILED work request found for $ResourceId." }
    try { $requests = @((($response | ConvertFrom-Json -ErrorAction Stop).data)) }
    catch { return "No FAILED work request found for $ResourceId." }
    if (-not $requests -or -not $requests[0].id) {
        return "No FAILED work request found for $ResourceId."
    }
    $response = & oci --region $Region --output json generative-ai work-request-error list `
        --work-request-id $requests[0].id 2>$null
    if ($LASTEXITCODE -ne 0) { return 'No work request errors available.' }
    try { $errors = @((($response | ConvertFrom-Json -ErrorAction Stop).data)) }
    catch { return 'No work request errors available.' }
    if (-not $errors -or -not $errors[0]) { return 'No work request errors available.' }
    try { $runtime = @((($env:OCI_DEPLOY_RUNTIME_JSON | ConvertFrom-Json -ErrorAction Stop))) }
    catch { $runtime = @() }
    $lines = @()
    foreach ($item in $errors) {
        $code = [string]$item.code
        $message = [string]$item.message
        foreach ($variable in $runtime) {
            if ($variable.value) {
                $code = $code.Replace([string]$variable.value, '[REDACTED]')
                $message = $message.Replace([string]$variable.value, '[REDACTED]')
            }
        }
        $lines += "OCI work request error: code=$code; message=$message"
    }
    return $lines
}

function Wait-HostedResource {
    param([string]$Kind, [string]$ResourceId, [string]$Operation,
          [string]$Region, [int]$TimeoutSeconds, [int]$PollInterval)
    $started = [DateTimeOffset]::UtcNow
    $failures = 0
    while ($true) {
        $elapsed = [int]([DateTimeOffset]::UtcNow - $started).TotalSeconds
        if ($Kind -eq 'Hosted Application') {
            $getArgs = @('--region', $Region, '--output', 'json', 'generative-ai',
                'hosted-application', 'get', '--hosted-application-id', $ResourceId)
        } else {
            $getArgs = @('--region', $Region, '--output', 'json', 'generative-ai',
                'hosted-deployment', 'get', '--hosted-deployment-id', $ResourceId)
        }
        $response = & oci @args 2>&1
        if ($LASTEXITCODE -ne 0) {
            $errorText = ((@($response) | ForEach-Object { "$_" }) -join "`n")
            if ($Operation -eq 'delete' -and $errorText -match '\b404\b') {
                Write-Host "${Kind}: DELETED (elapsed ${elapsed}s)"
                return 0
            }
            if (($elapsed -lt 60 -and $errorText -match '\b404\b') -or
                $errorText -match '\b(429|5[0-9][0-9])\b') {
                $null = $errorText -match '\b(404|429|5[0-9][0-9])\b'
                $failures++
                $httpCode = $Matches[1]
                $state = 'GET_RETRY'
                Write-Host "${Kind}: $state (elapsed ${elapsed}s)"
                if ($failures -ge 5) {
                    [Console]::Error.WriteLine("$Kind get failed after 5 consecutive attempts (last error: HTTP $httpCode).")
                    return 1
                }
            } else {
                $lastHttp = if ($errorText -match '\b([45][0-9][0-9])\b') { $Matches[1] } else { 'unknown' }
                [Console]::Error.WriteLine("$Kind get failed for $ResourceId (last error: HTTP $lastHttp).")
                return 1
            }
        } else {
            $failures = 0
            try { $state = (($response | ConvertFrom-Json -ErrorAction Stop).data.'lifecycle-state') }
            catch { $state = 'UNKNOWN' }
            if (-not $state) { $state = 'UNKNOWN' }
            Write-Host "${Kind}: $state (elapsed ${elapsed}s)"
            if ($Operation -eq 'delete' -and $state -eq 'DELETED') { return 0 }
            if ($Operation -ne 'delete' -and $state -eq 'ACTIVE') { return 0 }
            if ($state -eq 'FAILED') {
                [Console]::Error.WriteLine("$Kind $ResourceId is FAILED.")
                foreach ($line in @(Get-HostedWorkRequestErrors -Region $Region -ResourceId $ResourceId)) {
                    [Console]::Error.WriteLine($line)
                }
                return 1
            }
            if ($state -notin @('CREATING', 'UPDATING', 'DELETING')) {
                [Console]::Error.WriteLine("$Kind $ResourceId reached unexpected state $state.")
                return 1
            }
        }
        if ($elapsed -ge $TimeoutSeconds) {
            [Console]::Error.WriteLine("$Kind $ResourceId is still $state after ${elapsed}s; nothing else was changed or deleted by this script; OCI continues the operation.")
            return 26
        }
        Start-Sleep -Seconds $PollInterval
    }
}
Export-ModuleMember -Function Get-MutationId, Get-MutationWorkRequestId, Find-MutatedResource, Get-HostedWorkRequestErrors, Wait-HostedResource
