<# .SYNOPSIS Inspects or, with -Create, creates one private mutable OCIR repository. #>
[CmdletBinding()]
param([switch]$Create, [switch]$Help)
if ($Help) { Write-Output 'Usage: .\scripts\ensure_ocir_repository.ps1 [-Create]'; exit 0 }
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion -lt [version]'7.2') { [Console]::Error.WriteLine("PowerShell 7.2 or later is required; current version is $($PSVersionTable.PSVersion). Open PowerShell 7 (pwsh), then run this command again."); exit 64 }
function Fail([int]$Code, [string]$Message) { [Console]::Error.WriteLine($Message); exit $Code }
foreach ($name in 'OCI_REGION','OCI_COMPARTMENT_NAME','OCIR_REPOSITORY') { if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue).Value) { Fail 64 "Missing required environment variable: $name" } }
if (-not (Get-Command oci -ErrorAction SilentlyContinue)) { Fail 1 'OCI CLI is not available in PATH. Activate the project Conda environment first.' }
$active = 'data[?"lifecycle-state"==`ACTIVE`]'
$count = & oci --region $env:OCI_REGION iam compartment list --name $env:OCI_COMPARTMENT_NAME --compartment-id-in-subtree true --all --query "length($active)" --raw-output
if ($LASTEXITCODE -ne 0 -or $count -ne '1') { Fail 1 "Expected exactly one active compartment named `"$($env:OCI_COMPARTMENT_NAME)`"; found $count." }
$compartment = & oci --region $env:OCI_REGION iam compartment list --name $env:OCI_COMPARTMENT_NAME --compartment-id-in-subtree true --all --query "($active)[0].id" --raw-output
$repoCount = & oci --region $env:OCI_REGION artifacts container repository list --compartment-id $compartment --display-name $env:OCIR_REPOSITORY --lifecycle-state AVAILABLE --all --query 'length(data.items)' --raw-output
if ($repoCount -eq '1') { $id = & oci --region $env:OCI_REGION artifacts container repository list --compartment-id $compartment --display-name $env:OCIR_REPOSITORY --lifecycle-state AVAILABLE --all --query 'data.items[0].id' --raw-output; Write-Output "OCIR repository already exists: $id"; exit 0 }
if ($repoCount -ne '0') { Fail 1 "Expected zero or one available repository named `"$($env:OCIR_REPOSITORY)`"; found $repoCount." }
if (-not $Create) { Fail 20 "OCIR repository `"$($env:OCIR_REPOSITORY)`" is absent from compartment $compartment. Re-run with -Create to create one private, mutable repository." }
Write-Output "Creating private, mutable OCIR repository `"$($env:OCIR_REPOSITORY)`" in compartment $compartment"
$id = & oci --region $env:OCI_REGION artifacts container repository create --compartment-id $compartment --display-name $env:OCIR_REPOSITORY --is-public false --is-immutable false --wait-for-state AVAILABLE --max-wait-seconds 120 --query 'data.id' --raw-output
if ($LASTEXITCODE -ne 0) { Fail 1 'OCI repository creation failed.' }; Write-Output "Created OCIR repository: $id"
