<#
.SYNOPSIS
    Bumblebee Uninstaller — Clean removal
.DESCRIPTION
    Stops the dashboard, removes the scheduled task, and optionally
    deletes the bumblebee directory.
.PARAMETER KeepFiles
    Don't delete the bumblebee directory (just remove the service)
.EXAMPLE
    .\uninstall.ps1
.EXAMPLE
    .\uninstall.ps1 -KeepFiles
#>
param(
    [switch]$KeepFiles
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "  Bumblebee Uninstaller" -ForegroundColor Yellow
Write-Host ""

# ---------------------------------------------------------------------------
# Step 1: Stop and remove scheduled task
# ---------------------------------------------------------------------------

Write-Host "[1/3] Removing scheduled task..." -ForegroundColor Cyan

$taskName = "Bumblebee-Dashboard"
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($task) {
    if ($task.State -eq "Running") {
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Write-Host "  Stopped task." -ForegroundColor Green
    }
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "  Removed scheduled task '$taskName'." -ForegroundColor Green
} else {
    Write-Host "  No scheduled task found." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 2: Kill any running dashboard processes
# ---------------------------------------------------------------------------

Write-Host "[2/3] Stopping dashboard processes..." -ForegroundColor Cyan

# Find python processes running uvicorn from the bumblebee directory
$bumblebeeRoot = $PSScriptRoot
if (-not $bumblebeeRoot) {
    $bumblebeeRoot = (Get-Location).Path
}

$killed = 0
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmdline -and $cmdline -match "uvicorn" -and $cmdline -match "api\.main") {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            $killed++
        }
    } catch {}
}

if ($killed -gt 0) {
    Write-Host "  Stopped $killed dashboard process(es)." -ForegroundColor Green
} else {
    Write-Host "  No dashboard processes running." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 3: Remove files (optional)
# ---------------------------------------------------------------------------

if (-not $KeepFiles) {
    Write-Host "[3/3] Removing files..." -ForegroundColor Cyan

    # If running from inside the bumblebee dir, move out first
    $currentDir = (Get-Location).Path
    if ($currentDir.StartsWith($bumblebeeRoot)) {
        Set-Location $env:USERPROFILE
    }

    try {
        Remove-Item $bumblebeeRoot -Recurse -Force -ErrorAction Stop
        Write-Host "  Removed $bumblebeeRoot" -ForegroundColor Green
    } catch {
        Write-Host "  Could not fully remove directory (files may be in use)." -ForegroundColor Red
        Write-Host "  Try closing all terminals and deleting manually: $bumblebeeRoot" -ForegroundColor Yellow
    }
} else {
    Write-Host "[3/3] Keeping files (--KeepFiles)." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "  Bumblebee uninstalled." -ForegroundColor Green
Write-Host ""
