# SPDX-License-Identifier: AGPL-3.0-only
# Development launcher. Keeps the companion and slicer profiles in this project.
param([Parameter(Mandatory)][ValidateSet('orca','bambu')][string]$Slicer, [string]$Project)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$state = Join-Path $root 'artifacts\onshape'
$connection = Join-Path $state 'bridge.json'
$portable = Join-Path $root "artifacts\$Slicer\portable"
$executable = if ($Slicer -eq 'orca') { 'orca-slicer.exe' } else { 'bambu-studio.exe' }
$binary = Join-Path $portable $executable
if (!(Test-Path -LiteralPath $binary)) { throw 'Build and stage the experimental slicer first. See docs/build.md.' }
$projectArgument = ''
if ($Project) {
    $resolved = (Resolve-Path -LiteralPath $Project).Path
    if ([IO.Path]::GetExtension($resolved) -ne '.3mf') { throw 'Open a saved 3MF slicer project.' }
    $projectArgument = ' "' + $resolved + '"'
}
function Get-CompanionStatus {
    try { Invoke-RestMethod -Uri 'http://127.0.0.1:8766/v1/status' -Headers @{Host='localhost:8766'} -TimeoutSec 2 } catch { $null }
}
$status = Get-CompanionStatus
if (!$status) {
    $python = (Get-Command python.exe -ErrorAction Stop).Source
    $process = Start-Process -FilePath $python -ArgumentList '-m companion.server' -WorkingDirectory $root `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $state 'companion-stdout.log') `
        -RedirectStandardError (Join-Path $state 'companion-stderr.log')
    @{process_id=$process.Id; binary=$python; module='companion.server'} | ConvertTo-Json |
        Set-Content -LiteralPath (Join-Path $state 'bridge-process.json')
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 200
        $process.Refresh()
        if ($process.HasExited) { throw 'Companion could not start. Close the old authentication probe if it still owns port 8766.' }
        $status = Get-CompanionStatus
        if ($status) { break }
    }
}
if (!$status -or $status.schema -ne 1 -or $status.application -ne 'Onshape Slicer Link' -or !(Test-Path -LiteralPath $connection)) {
    throw 'The Onshape Slicer Link companion is unavailable. See artifacts/onshape/companion-stdout.log.'
}
$key = (Get-Content -Raw -LiteralPath $connection | ConvertFrom-Json).key
$hasher = [Security.Cryptography.SHA256]::Create()
try { $instance = -join ($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($key)) | ForEach-Object { $_.ToString('x2') }) }
finally { $hasher.Dispose() }
if ($status.instance -ne $instance) { throw 'A companion from a different project is using port 8766.' }
$env:OSL_COMPANION_FILE = $connection
$env:OSL_EXPERIMENT_DIR = Join-Path $portable 'experiment'
$profile = Join-Path $portable 'profile'
$slicerProcess = Start-Process -FilePath $binary -ArgumentList ('--datadir "' + $profile + '"' + $projectArgument) -WindowStyle Hidden -PassThru
@{process_id=$slicerProcess.Id; binary=$binary; profile=$profile} | ConvertTo-Json |
    Set-Content -LiteralPath (Join-Path $root "artifacts\$Slicer\launch-process.json")
Write-Output 'Click Update linked parts in the top toolbar for a manual CAD refresh.'
