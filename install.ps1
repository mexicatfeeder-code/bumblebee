# ============================================================
# Bumblebee Installer — From zero to running dashboard
# ============================================================
# Usage (admin PowerShell):
#   irm https://raw.githubusercontent.com/mexicatfeeder-code/bumblebee/master/install.ps1 | iex
#
# Or from a local clone:
#   .\install.ps1
#
# Options:
#   -Port 8765           Dashboard port (default 8765)
#   -SkipService         Don't register as scheduled task
#   -NoLaunch            Don't open browser after install
# ============================================================

param(
    [int]$Port = 8765,
    [switch]$SkipService,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  ____                  _     _       _                " -ForegroundColor Yellow
Write-Host " | __ ) _   _ _ __ ___ | |__ | | ___ | |__   ___  ___ " -ForegroundColor Yellow
Write-Host " |  _ \| | | | '_ ` _ \| '_ \| |/ _ \| '_ \ / _ \/ _ \" -ForegroundColor Yellow
Write-Host " | |_) | |_| | | | | | | |_) | |  __/| |_) |  __/  __/" -ForegroundColor Yellow
Write-Host " |____/ \__,_|_| |_| |_|_.__/|_|\___||_.__/ \___|\___|" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Automated coding engine — PRD to working app" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Step 1: Check if running from repo or needs to clone
# ---------------------------------------------------------------------------

$bumblebeeRoot = $null

# Are we inside the repo already?
if (Test-Path (Join-Path $PSScriptRoot "engine\executor.py")) {
    $bumblebeeRoot = $PSScriptRoot
    Write-Host "[1/6] Using existing repo at $bumblebeeRoot" -ForegroundColor Green
} elseif (Test-Path ".\engine\executor.py") {
    $bumblebeeRoot = (Resolve-Path ".").Path
    Write-Host "[1/6] Using existing repo at $bumblebeeRoot" -ForegroundColor Green
} else {
    # Clone the repo
    $installDir = Join-Path $env:USERPROFILE "bumblebee"
    Write-Host "[1/6] Cloning Bumblebee to $installDir..." -ForegroundColor Yellow

    if (!(Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host "  Git not found. Installing via winget..." -ForegroundColor Yellow
        winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
        $env:PATH = "$env:PATH;C:\Program Files\Git\cmd"
    }

    if (Test-Path $installDir) {
        Write-Host "  Directory exists — pulling latest..." -ForegroundColor Yellow
        Set-Location $installDir
        git pull --ff-only 2>&1 | Out-Null
    } else {
        git clone https://github.com/mexicatfeeder-code/bumblebee.git $installDir 2>&1 | Out-Null
    }
    $bumblebeeRoot = $installDir
    Write-Host "  Done." -ForegroundColor Green
}

Set-Location $bumblebeeRoot

# ---------------------------------------------------------------------------
# Step 2: Check Python
# ---------------------------------------------------------------------------

Write-Host "[2/6] Checking Python..." -ForegroundColor Yellow

$python = $null
foreach ($cmd in @("python3", "python")) {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($found) {
        $ver = & $cmd --version 2>&1
        if ($ver -match "3\.(1[1-9]|[2-9]\d)") {
            $python = $cmd
            break
        }
    }
}

if (!$python) {
    Write-Host "  Python 3.11+ not found. Installing via winget..." -ForegroundColor Yellow
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    # Refresh PATH
    $env:PATH = "$env:PATH;$env:LOCALAPPDATA\Programs\Python\Python312;$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
    $python = "python"
    $ver = & $python --version 2>&1
    Write-Host "  Installed: $ver" -ForegroundColor Green
} else {
    $ver = & $python --version 2>&1
    Write-Host "  Found: $ver" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Step 3: Check Node.js
# ---------------------------------------------------------------------------

Write-Host "[3/6] Checking Node.js..." -ForegroundColor Yellow

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (!$nodeCmd) {
    Write-Host "  Node.js not found. Installing via winget..." -ForegroundColor Yellow
    winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements
    $env:PATH = "$env:PATH;C:\Program Files\nodejs"
}

$nodeVer = & node --version 2>&1
Write-Host "  Found: Node.js $nodeVer" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 4: Install dependencies
# ---------------------------------------------------------------------------

Write-Host "[4/6] Installing dependencies..." -ForegroundColor Yellow

# Python deps for the engine and dashboard API
Write-Host "  Python packages..." -ForegroundColor Yellow
& $python -m pip install -q --upgrade pip 2>&1 | Out-Null
& $python -m pip install -q -r (Join-Path $bumblebeeRoot "requirements.txt") 2>&1 | Out-Null
& $python -m pip install -q -r (Join-Path $bumblebeeRoot "dashboard\api\requirements.txt") 2>&1 | Out-Null

# Node deps + build frontend
Write-Host "  Dashboard frontend..." -ForegroundColor Yellow
$uiDir = Join-Path $bumblebeeRoot "dashboard\ui"
Set-Location $uiDir
npm install --silent 2>&1 | Out-Null
npm run build 2>&1 | Out-Null

$buildDir = Join-Path $uiDir "build"
if (!(Test-Path $buildDir)) {
    Write-Host "  WARNING: Frontend build failed. Dashboard will run in API-only mode." -ForegroundColor Red
    Write-Host "  Run 'cd $uiDir && npm run build' manually to fix." -ForegroundColor Red
} else {
    Write-Host "  Frontend built successfully." -ForegroundColor Green
}

Set-Location $bumblebeeRoot

# ---------------------------------------------------------------------------
# Step 5: Create config
# ---------------------------------------------------------------------------

Write-Host "[5/6] Configuring..." -ForegroundColor Yellow

$configPath = Join-Path $bumblebeeRoot "dashboard\dashboard.config.json"
if (!(Test-Path $configPath)) {
    $config = @{
        ticketDbPaths = @{}
        apiPort = $Port
        healthChecks = @()
        workspaceRoot = $bumblebeeRoot
        ai = @{
            lemonade_url = "http://[::1]:13305"
            qa_model_source = "lemonade"
            decomp_model_source = "lemonade"
            forge_model_source = "custom"
            vision_model_source = "custom"
        }
    }
    $config | ConvertTo-Json -Depth 4 | Set-Content $configPath -Encoding UTF8
    Write-Host "  Created dashboard.config.json" -ForegroundColor Green
} else {
    Write-Host "  Config already exists — keeping current settings." -ForegroundColor Green
}

# Ensure projects directory exists
$projectsDir = Join-Path $bumblebeeRoot "projects"
if (!(Test-Path $projectsDir)) {
    New-Item -ItemType Directory -Path $projectsDir -Force | Out-Null
}

# ---------------------------------------------------------------------------
# Step 6: Register service (optional)
# ---------------------------------------------------------------------------

if (!$SkipService) {
    Write-Host "[6/6] Registering dashboard service..." -ForegroundColor Yellow

    $taskName = "Bumblebee-Dashboard"
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

    if ($existing) {
        Write-Host "  Task '$taskName' already exists. Restarting..." -ForegroundColor Yellow
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }

    # Create a startup script
    $startScript = Join-Path $bumblebeeRoot "dashboard\start-service.ps1"
    $startContent = @()
    $startContent += '# Auto-generated by install.ps1'
    $startContent += "`$env:DASHBOARD_CONFIG = `"$configPath`""
    $startContent += "Set-Location `"$bumblebeeRoot\dashboard`""
    $startContent += "& $python -m uvicorn api.main:app --host 0.0.0.0 --port $Port"
    $startContent -join "`r`n" | Set-Content $startScript -Encoding UTF8

    # Create VBS wrapper for hidden window
    $vbsWrapper = Join-Path $bumblebeeRoot "dashboard\start-hidden.vbs"
    $vbsContent = @()
    $vbsContent += 'Set objShell = CreateObject("WScript.Shell")'
    $vbsContent += "objShell.Run `"powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File `""$startScript`""`", 0, False"
    $vbsContent -join "`r`n" | Set-Content $vbsWrapper -Encoding UTF8

    try {
        $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument """$vbsWrapper"""
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)
        $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

        if ($existing) {
            Set-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
        } else {
            Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
        }

        Start-ScheduledTask -TaskName $taskName
        Write-Host "  Dashboard registered as '$taskName' (starts at logon, auto-restart)." -ForegroundColor Green
    } catch {
        Write-Host "  WARNING: Could not register scheduled task (might need admin)." -ForegroundColor Red
        Write-Host "  You can start the dashboard manually: cd dashboard; .\start.ps1" -ForegroundColor Yellow
    }
} else {
    Write-Host "[6/6] Skipping service registration (-SkipService)." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Done!
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "=== Bumblebee installed! ===" -ForegroundColor Green
Write-Host ""
Write-Host "  Dashboard: http://localhost:$Port" -ForegroundColor Cyan
Write-Host "  Config:    $configPath" -ForegroundColor Cyan
Write-Host "  Projects:  $projectsDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Yellow
Write-Host "    1. Open the dashboard in your browser"
Write-Host "    2. Create a new project (name + PRD)"
Write-Host "    3. Configure your AI provider (API key)"
Write-Host "    4. Chat with the AI to refine your requirements"
Write-Host "    5. Decompose into tickets and start coding!"
Write-Host ""

if (!$NoLaunch) {
    Write-Host "Opening dashboard..." -ForegroundColor Cyan
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:$Port"
}
