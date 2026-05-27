<#
.SYNOPSIS
    Bumblebee Uninstaller - Clean removal
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

# Kill only bumblebee-related python processes (uvicorn dashboard, executor, research)
# Do NOT kill all python/node - other services (OpenClaw node, Lemonade) may be running
$killed = 0
Get-CimInstance Win32_Process -Filter "name='python.exe' OR name='python3.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    $cmd = $_.CommandLine
    if ($cmd -and ($cmd -match 'bumblebee|uvicorn|executor|research_executor')) {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        $killed++
    }
}
if ($killed -gt 0) {
    Write-Host "  Stopped $killed bumblebee Python process(es)." -ForegroundColor Green
    Start-Sleep -Seconds 2
} else {
    Write-Host "  No bumblebee Python processes running." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 3: Remove files (optional)
# ---------------------------------------------------------------------------

# Remove desktop shortcuts
Write-Host "[3/4] Removing desktop shortcuts..." -ForegroundColor Cyan
$desktop = [Environment]::GetFolderPath("Desktop")
$removed = 0
foreach ($name in @("Bumblebee Dashboard.lnk", "Food Cart Demo.lnk")) {
    $lnk = Join-Path $desktop $name
    if (Test-Path $lnk) {
        Remove-Item $lnk -Force -ErrorAction SilentlyContinue
        $removed++
    }
}
if ($removed -gt 0) {
    Write-Host "  Removed $removed shortcut(s)." -ForegroundColor Green
} else {
    Write-Host "  No shortcuts found." -ForegroundColor Yellow
}

if (-not $KeepFiles) {
    Write-Host "[4/4] Removing files..." -ForegroundColor Cyan

    # If running from inside the bumblebee dir, move out first
    $currentDir = (Get-Location).Path
    if ($currentDir.StartsWith($bumblebeeRoot)) {
        Set-Location $env:USERPROFILE
    }

    # First, nuke node_modules separately (Windows long-path problem)
    $nmDir = Join-Path $bumblebeeRoot "dashboard\ui\node_modules"
    if (Test-Path $nmDir) {
        Write-Host "  Cleaning node_modules (long paths)..." -ForegroundColor Yellow
        $emptyNm = Join-Path $env:TEMP "bb-empty-nm-$(Get-Random)"
        New-Item -ItemType Directory -Path $emptyNm -Force | Out-Null
        robocopy $emptyNm $nmDir /MIR /NFL /NDL /NJH /NJS /nc /ns /np 2>&1 | Out-Null
        Remove-Item $nmDir -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item $emptyNm -Force -ErrorAction SilentlyContinue
    }

    # Close any git lock files
    $gitLock = Join-Path $bumblebeeRoot ".git\index.lock"
    if (Test-Path $gitLock) {
        Remove-Item $gitLock -Force -ErrorAction SilentlyContinue
    }

    $removed = $false
    for ($i = 1; $i -le 3; $i++) {
        try {
            Remove-Item $bumblebeeRoot -Recurse -Force -ErrorAction Stop
            $removed = $true
            break
        } catch {
            if ($i -lt 3) {
                Write-Host "  Retry $i/3 - waiting for file locks to release..." -ForegroundColor Yellow
                Start-Sleep -Seconds 3
            }
        }
    }
    if ($removed) {
        Write-Host "  Removed $bumblebeeRoot" -ForegroundColor Green
    } else {
        Write-Host "  Trying robocopy cleanup..." -ForegroundColor Yellow
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
    Write-Host '[3/3] Keeping files (-KeepFiles).' -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "  Bumblebee uninstalled." -ForegroundColor Green
Write-Host ""
