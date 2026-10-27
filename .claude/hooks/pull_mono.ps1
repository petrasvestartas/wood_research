param(
    [switch]$AllSources,
    [switch]$NestedOnly,
    [switch]$Hook,
    [switch]$Force,
    [switch]$Help,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Options
)

$ErrorActionPreference = 'Stop'
foreach ($option in $Options) {
    switch -Exact ($option) {
        '--help' { $Help = $true }
        '-h' { $Help = $true }
        '--all-sources' { $AllSources = $true }
        '--nested-only' { $NestedOnly = $true }
        '--hook' { $Hook = $true }
        '--force' { $Force = $true }
        default { throw "Unknown option: $option" }
    }
}
if ($Help) {
    Write-Output 'Usage: pull_mono.cmd [--all-sources | --nested-only] [--hook] [--force]'
    Write-Output 'Sync remote branches. Local changes or unpublished commits block syncing unless --force explicitly discards them.'
    exit 0
}
$gitPath = (Get-Command git -CommandType Application | Select-Object -First 1).Source
$gitDirectory = Split-Path -Parent $gitPath
$candidates = @(
    (Join-Path $gitDirectory '../bin/bash.exe'),
    (Join-Path $gitDirectory '../../bin/bash.exe')
)
$bashPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $bashPath) {
    throw 'Git for Windows Bash was not found beside git.exe. Install Git for Windows or run pull_mono.sh with Bash on Linux/macOS.'
}

$scriptPath = (Join-Path $PSScriptRoot 'pull_mono.sh').Replace('\', '/')
$arguments = @($scriptPath)
if ($AllSources) { $arguments += '--all-sources' }
if ($NestedOnly) { $arguments += '--nested-only' }
if ($Hook) { $arguments += '--hook' }
if ($Force) { $arguments += '--force' }
if ($Hook) {
    $payload = [Console]::In.ReadToEnd()
    $payload | & $bashPath @arguments
} else {
    & $bashPath @arguments
}
exit $LASTEXITCODE
