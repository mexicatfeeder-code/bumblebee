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
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
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

# Kill ALL python processes to release file locks
$pyProcs = Get-Process python -ErrorAction SilentlyContinue
if ($pyProcs) {
    $pyProcs | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "  Stopped $($pyProcs.Count) Python process(es)." -ForegroundColor Green
    Start-Sleep -Seconds 2
} else {
    Write-Host "  No Python processes running." -ForegroundColor Yellow
}

# Also kill any node processes that might hold locks
$nodeProcs = Get-Process node -ErrorAction SilentlyContinue
if ($nodeProcs) {
    $nodeProcs | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "  Stopped $($nodeProcs.Count) Node process(es)." -ForegroundColor Green
    Start-Sleep -Seconds 1
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

    $removed = $false
    for ($i = 1; $i -le 3; $i++) {
        try {
            Remove-Item $bumblebeeRoot -Recurse -Force -ErrorAction Stop
            $removed = $true
            break
        } catch {
            if ($i -lt 3) {
                Write-Host "  Retry $i/3 — waiting for file locks to release..." -ForegroundColor Yellow
                Start-Sleep -Seconds 3
            }
        }
    }
    if ($removed) {
        Write-Host "  Removed $bumblebeeRoot" -ForegroundColor Green
    } else {
        Write-Host "  Could not fully remove directory. Trying robocopy cleanup..." -ForegroundColor Yellow
        # Create empty temp dir and mirror it over the target to force-delete
        $emptyDir = Join-Path $env:TEMP "bumblebee-empty-$(Get-Random)"
        New-Item -ItemType Directory -Path $emptyDir -Force | Out-Null
        robocopy $emptyDir $bumblebeeRoot /MIR /NFL /NDL /NJH /NJS /nc /ns /np 2>&1 | Out-Null
        Remove-Item $bumblebeeRoot -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item $emptyDir -Force -ErrorAction SilentlyContinue
        if (!(Test-Path $bumblebeeRoot)) {
            Write-Host "  Removed $bumblebeeRoot (via robocopy)" -ForegroundColor Green
        } else {
            Write-Host "  Some files remain. Close all terminals and delete manually: $bumblebeeRoot" -ForegroundColor Red
        }
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
