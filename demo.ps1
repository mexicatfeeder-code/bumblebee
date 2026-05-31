<#
.SYNOPSIS
    Bumblebee Conference Demo - One-click launcher
.DESCRIPTION
    Resets the demo project DB to a partial state, starts the dashboard,
    and kicks off the executor for a live coding demo.
.PARAMETER Project
    Demo project to run (default: food-cart)
.PARAMETER Reset
    Reset the project DB before starting (default: true)
.PARAMETER Port
    Dashboard port (default: 8765)
.PARAMETER SkipDashboard
    Don't start the dashboard (if already running)
.EXAMPLE
    .\demo.ps1
.EXAMPLE
    .\demo.ps1 -Project food-cart -Port 9000
.EXAMPLE
    .\demo.ps1 -SkipDashboard  # Dashboard already running, just reset + start executor
#>
param(
    [string]$Project = "food-cart",
    [switch]$NoReset,
    [int]$Port = 8765,
    [switch]$SkipDashboard,
    [switch]$ResetAll
)

$ErrorActionPreference = "Stop"
$root = Split-Path $MyInvocation.MyCommand.Path -Parent

Write-Host ""
Write-Host "  ====================================" -ForegroundColor Yellow
Write-Host "    Bumblebee - Conference Demo" -ForegroundColor Yellow
Write-Host "  ====================================" -ForegroundColor Yellow
Write-Host ""

# ---------------------------------------------------------------------------
# Step 1: Check Lemonade
# ---------------------------------------------------------------------------
Write-Host "[1/4] Checking Lemonade server..." -ForegroundColor Cyan
$lemonadeUrl = "http://[::1]:13305"
$lemonadeExe = Join-Path $env:LOCALAPPDATA "lemonade_server\bin\LemonadeServer.exe"
$requiredModel = "Qwen3.6-27B-GGUF"
$requiredContext = 32768
$lemonadeOk = $false

function Test-LemonadeHealth {
    try {
        $r = Invoke-RestMethod -Uri "$lemonadeUrl/api/v1/health" -TimeoutSec 5 -ErrorAction Stop
        return $r
    } catch {
        return $null
    }
}

$health = Test-LemonadeHealth
if (-not $health) {
    if (Test-Path $lemonadeExe) {
        Write-Host "  Lemonade not running. Starting..." -ForegroundColor Yellow
        Start-Process $lemonadeExe -WindowStyle Minimized
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            $health = Test-LemonadeHealth
            if ($health) { break }
        }
        if ($health) {
            Write-Host "  Lemonade started." -ForegroundColor Green
        } else {
            Write-Host "  WARNING: Lemonade did not start within 30s." -ForegroundColor Red
        }
    } else {
        Write-Host "  Lemonade not found. Start it manually." -ForegroundColor Red
    }
}

if ($health) {
    $loadedModel = $health.model_loaded
    if ($loadedModel -eq $requiredModel) {
        Write-Host "  Lemonade OK - $requiredModel loaded." -ForegroundColor Green
        $lemonadeOk = $true
    } else {
        if ($loadedModel) {
            Write-Host "  Unloading $loadedModel..." -ForegroundColor Yellow
            try {
                Invoke-RestMethod -Uri "$lemonadeUrl/v1/unload" -Method POST `
                    -ContentType "application/json" `
                    -Body (@{model_name=$loadedModel} | ConvertTo-Json) `
                    -TimeoutSec 30 -ErrorAction Stop | Out-Null
            } catch {
                Write-Host "  Could not unload, trying load anyway..." -ForegroundColor Yellow
            }
        }
        Write-Host "  Loading $requiredModel (ctx_size: $requiredContext)... this may take 1-3 minutes." -ForegroundColor Yellow
        try {
            $loadResp = Invoke-RestMethod -Uri "$lemonadeUrl/v1/load" -Method POST `
                -ContentType "application/json" `
                -Body (@{
                    model_name = $requiredModel
                    ctx_size = $requiredContext
                    save_options = $true
                } | ConvertTo-Json) `
                -TimeoutSec 300 -ErrorAction Stop
            Write-Host "  $requiredModel loaded (ctx_size: $requiredContext). $($loadResp.message)" -ForegroundColor Green
            $lemonadeOk = $true
        } catch {
            Write-Host "  Failed to load model: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "  Load $requiredModel manually in Lemonade with ctx_size $requiredContext." -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  Lemonade not available. Dashboard will work, but executor won't code." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 2: Reset demo project (optional)
# ---------------------------------------------------------------------------
# Look in demos/ first, then projects/
$projectDir = Join-Path $root "demos\$Project"
if (!(Test-Path $projectDir)) {
    $projectDir = Join-Path $root "projects\$Project"
}
if (!(Test-Path $projectDir)) {
    Write-Host "  ERROR: Project '$Project' not found in demos/ or projects/" -ForegroundColor Red
    exit 1
}

if (-not $NoReset) {
    Write-Host "[2/4] Resetting demo project(s)..." -ForegroundColor Cyan
    
    $resetAllScript = Join-Path $root "demos\reset_all_demos.py"
    if ($ResetAll) {
        # Reset ALL demo projects
        python $resetAllScript
        Write-Host "  All demos reset." -ForegroundColor Green
    } else {
        # Reset just the selected project
        python $resetAllScript $Project
        Write-Host "  Demo '$Project' reset." -ForegroundColor Green
    }
} else {
    Write-Host "[2/4] Skipping reset (--NoReset)." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 3: Start dashboard
# ---------------------------------------------------------------------------
if (-not $SkipDashboard) {
    Write-Host "[3/4] Starting dashboard on port $Port..." -ForegroundColor Cyan
    
    # Kill existing dashboard on this port
    $existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | 
        Where-Object { $_.State -eq 'Listen' }
    if ($existing) {
        Write-Host "  Port $Port already in use - dashboard may be running." -ForegroundColor Yellow
        Write-Host "  Skipping dashboard start. Kill it first if you want a fresh one." -ForegroundColor Yellow
    } else {
        $dashStart = Join-Path $root "dashboard\start.ps1"
        Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$dashStart`" -Port $Port" -WindowStyle Minimized
        Write-Host "  Dashboard starting in background..." -ForegroundColor Green
        Start-Sleep -Seconds 3
    }
} else {
    Write-Host "[3/4] Skipping dashboard start." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 3b: Start research executor
# ---------------------------------------------------------------------------
if ($lemonadeOk) {
    $researchDb = Join-Path $root "research\research.db"
    $reportsDir = Join-Path $root "research\reports"
    # Also check demo-local research DB
    $demoResearchDb = Join-Path $projectDir "research\research.db"
    $demoReportsDir = Join-Path $projectDir "research\reports"
    $activeResearchDb = $null
    $activeReportsDir = $null
    if (Test-Path $demoResearchDb) {
        $activeResearchDb = $demoResearchDb
        $activeReportsDir = $demoReportsDir
    } elseif (Test-Path $researchDb) {
        $activeResearchDb = $researchDb
        $activeReportsDir = $reportsDir
    }
    if ($activeResearchDb) {
        Write-Host "  Starting research executor (Sift)..." -ForegroundColor Cyan
        Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -Command `"cd '$root'; python engine/research_executor.py --db-path '$activeResearchDb' --reports-dir '$activeReportsDir'`"" -WindowStyle Normal
        Write-Host "  Sift running in new window." -ForegroundColor Green
    }
}

# ---------------------------------------------------------------------------
# Step 4: Start executor (live coding)
# ---------------------------------------------------------------------------
if ($lemonadeOk) {
    Write-Host "[4/4] Starting executor for '$Project'..." -ForegroundColor Cyan
    
    $executorScript = Join-Path $projectDir "run_executor.py"
    if (Test-Path $executorScript) {
        Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -Command `"cd '$projectDir'; python run_executor.py`"" -WindowStyle Normal
        Write-Host "  Executor running in new window." -ForegroundColor Green
    } else {
        Write-Host "  No run_executor.py found in $projectDir" -ForegroundColor Red
    }
} else {
    Write-Host "[4/4] Skipping executor (Lemonade not available)." -ForegroundColor Yellow
    Write-Host "  Start Lemonade, then run: cd $projectDir && python run_executor.py" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  ====================================" -ForegroundColor Green
Write-Host "    Demo Ready!" -ForegroundColor Green
Write-Host "  ====================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Dashboard:  http://localhost:$Port" -ForegroundColor Cyan
Write-Host "  Project:    $Project" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Tip: Select '$Project' in the sidebar, then click 'Dashboard'" -ForegroundColor Yellow
Write-Host "  Tip: Click 'Cost Comparison' tab to show cloud vs local savings" -ForegroundColor Yellow
Write-Host ""

# Open browser
Start-Process "http://localhost:$Port"
