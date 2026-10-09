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
    $count = & oci @lookupArgs --query "length($query)" --raw-output
    if ($LASTEXITCODE -ne 0 -or "$count" -ne '1') { return '' }
    $id = & oci @lookupArgs --query "($query)[0].id" --raw-output
    if ($LASTEXITCODE -ne 0 -or -not "$id".StartsWith('ocid1.')) { return '' }
    return "$id"
}

# Decode the JSON following ServiceError, never digits elsewhere in the CLI text.
function Get-HostedServiceError {
    param([string]$OutputText)
    $marker = 'ServiceError:'
    $index = $OutputText.IndexOf($marker, [StringComparison]::Ordinal)
    if ($index -lt 0) { return $null }
    $payload = $OutputText.Substring($index + $marker.Length).Trim()
    try { $errorObject = $payload | ConvertFrom-Json -ErrorAction Stop }
    catch { return $null }
    if ($errorObject.status -isnot [int] -and $errorObject.status -isnot [long]) {
        return $null
    }
    return $errorObject
}

function Write-HostedServiceError {
    param([string]$Kind, [string]$OutputText)
    $errorObject = Get-HostedServiceError -OutputText $OutputText
    $status = if ($null -ne $errorObject) { [string]$errorObject.status } else { 'unknown' }
    $code = if ($errorObject.code) { [string]$errorObject.code } else { 'unknown' }
    $message = if ($errorObject.message) { [string]$errorObject.message } else { 'unknown' }
    if ($null -eq $errorObject) {
        $lines = @($OutputText -split "`r?`n" | Where-Object { $_.Trim() })
        $cliError = @($lines | Where-Object { $_ -match '^\s*(Error:|Exception:|Invalid value)' } | Select-Object -First 1)
        if ($cliError.Count -eq 0) {
            $cliError = @($lines | Where-Object { $_ -match '^\s*Usage:' } | Select-Object -First 1)
        }
        if ($cliError.Count -eq 0) { $cliError = @($lines | Select-Object -First 1) }
        if ($cliError.Count -gt 0) { $message = [string]$cliError[0] }
    }
    try { $runtime = @((($env:OCI_DEPLOY_RUNTIME_JSON | ConvertFrom-Json -ErrorAction Stop))) }
    catch { $runtime = @() }
    foreach ($variable in $runtime) {
        if ($variable.value) {
            $status = $status.Replace([string]$variable.value, '[REDACTED]')
            $code = $code.Replace([string]$variable.value, '[REDACTED]')
            $message = $message.Replace([string]$variable.value, '[REDACTED]')
        }
    }
    if ($message.Length -gt 500) { $message = $message.Substring(0, 500) + '…' }
    [Console]::Error.WriteLine("$Kind request failed: status=$status; code=$code; message=$message.")
}

function Get-HostedWorkRequestErrors {
    param([string]$Region, [string]$CompartmentId, [string]$ResourceId)
    $response = & oci --region $Region --output json generative-ai work-request list `
        --compartment-id $CompartmentId --resource-id $ResourceId --status FAILED --all 2>$null
    if ($LASTEXITCODE -ne 0) { return "No FAILED work request found for $ResourceId." }
    try {
        $payload = (@($response) -join "`n") | ConvertFrom-Json -ErrorAction Stop
        if ($payload.data.items -isnot [array]) {
            return "No FAILED work request found for $ResourceId."
        }
        $items = @($payload.data.items)
    } catch { return "No FAILED work request found for $ResourceId." }
    if (-not $items -or -not $items[0] -or -not $items[0].id) {
        return "No FAILED work request found for $ResourceId."
    }
    $response = & oci --region $Region --output json generative-ai work-request-error list `
        --work-request-id $items[0].id --all 2>$null
    if ($LASTEXITCODE -ne 0) { return 'No work request errors available.' }
    try {
        $payload = (@($response) -join "`n") | ConvertFrom-Json -ErrorAction Stop
        if ($payload.data.items -isnot [array]) {
            return 'No work request errors available.'
        }
        $errors = @($payload.data.items)
    } catch { return 'No work request errors available.' }
    if (-not $errors -or -not $errors[0] -or $errors[0] -isnot [pscustomobject]) {
        return 'No work request errors available.'
    }
    try { $runtime = @((($env:OCI_DEPLOY_RUNTIME_JSON | ConvertFrom-Json -ErrorAction Stop))) }
    catch { $runtime = @() }
    $lines = @()
    foreach ($item in $errors) {
        if ($item -isnot [pscustomobject]) { continue }
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
    if (-not $lines) { return 'No work request errors available.' }
    return $lines
}

function Wait-HostedResource {
    param([string]$Kind, [string]$ResourceId, [string]$Operation,
          [string]$Region, [string]$CompartmentId, [int]$TimeoutSeconds, [int]$PollInterval)
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
        $response = & oci @getArgs 2>&1
        if ($LASTEXITCODE -ne 0) {
            $errorText = ((@($response) | ForEach-Object { "$_" }) -join "`n")
            $serviceError = Get-HostedServiceError -OutputText $errorText
            $httpCode = if ($null -ne $serviceError) { [string]$serviceError.status } else { '' }
            if ($Operation -eq 'delete' -and $httpCode -eq '404') {
                Write-Host "${Kind}: DELETED (elapsed ${elapsed}s)"
                return 0
            }
            if (($elapsed -lt 60 -and $httpCode -eq '404') -or
                $httpCode -eq '429' -or $httpCode -match '^5[0-9][0-9]$') {
                $failures++
                $state = 'GET_RETRY'
                Write-Host "${Kind}: $state (elapsed ${elapsed}s)"
                if ($failures -ge 5) {
                    [Console]::Error.WriteLine("$Kind get failed after 5 consecutive attempts (last error: HTTP $httpCode).")
                    return 1
                }
            } else {
                $lastHttp = if ($httpCode) { $httpCode } else { 'unknown' }
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
                foreach ($line in @(Get-HostedWorkRequestErrors -Region $Region -CompartmentId $CompartmentId -ResourceId $ResourceId)) {
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
Export-ModuleMember -Function Get-MutationId, Get-MutationWorkRequestId, Find-MutatedResource, Get-HostedServiceError, Write-HostedServiceError, Get-HostedWorkRequestErrors, Wait-HostedResource
