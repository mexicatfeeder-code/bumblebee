<#
.SYNOPSIS
    Bumblebee Installer - From zero to running dashboard
.DESCRIPTION
    Installs Python, Node.js, clones the repo (if needed), builds the
    dashboard, and optionally registers it as a Windows scheduled task.
.PARAMETER Port
    Dashboard port (default 8765)
.PARAMETER SkipService
    Do not register as a scheduled task
.PARAMETER NoLaunch
    Do not open browser after install
.EXAMPLE
    irm https://raw.githubusercontent.com/mexicatfeeder-code/bumblebee/master/install.ps1 | iex
.EXAMPLE
    .\install.ps1 -Port 9000 -SkipService
#>
param(
    [int]$Port = 8765,
    [switch]$SkipService,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  Bumblebee Installer" -ForegroundColor Yellow
Write-Host "  Automated coding engine - PRD to working app" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Step 1: Locate or clone the repo
# ---------------------------------------------------------------------------

$bumblebeeRoot = $null

$scriptDir = $PSScriptRoot
if ($scriptDir -and (Test-Path (Join-Path $scriptDir "engine\executor.py"))) {
    $bumblebeeRoot = $scriptDir
    Write-Host "[1/6] Using existing repo at $bumblebeeRoot" -ForegroundColor Green
}
elseif (Test-Path ".\engine\executor.py") {
    $bumblebeeRoot = (Resolve-Path ".").Path
    Write-Host "[1/6] Using existing repo at $bumblebeeRoot" -ForegroundColor Green
}
else {
    $installDir = Join-Path $env:USERPROFILE "bumblebee"
    Write-Host "[1/6] Cloning Bumblebee to $installDir..." -ForegroundColor Yellow

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host "  Git not found. Installing via winget..." -ForegroundColor Yellow
        winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
        $env:PATH = "$env:PATH;C:\Program Files\Git\cmd"
    }

    if (Test-Path $installDir) {
        Write-Host "  Directory exists, pulling latest..." -ForegroundColor Yellow
        Set-Location $installDir
        git pull --ff-only 2>&1 | Out-Null
    }
    else {
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
        try {
            $ver = & $cmd --version 2>&1
            if ($ver -match "3\.(1[1-9]|[2-9]\d)") {
                $python = $cmd
                break
            }
        }
        catch {
            # Windows Store alias or broken install, skip
        }
    }
}

if (-not $python) {
    Write-Host "  Python 3.11+ not found. Installing via winget..." -ForegroundColor Yellow
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    $env:PATH = "$env:PATH;$env:LOCALAPPDATA\Programs\Python\Python312;$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
    $python = "python"
    $ver = & $python --version 2>&1
    Write-Host "  Installed: $ver" -ForegroundColor Green
}
else {
    $ver = & $python --version 2>&1
    Write-Host "  Found: $ver" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Step 3: Check Node.js
# ---------------------------------------------------------------------------

Write-Host "[3/6] Checking Node.js..." -ForegroundColor Yellow

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Host "  Node.js not found. Installing via winget..." -ForegroundColor Yellow
    winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements
    $env:PATH = "$env:PATH;C:\Program Files\nodejs"
}

try { $nodeVer = node --version 2>&1 } catch { $nodeVer = "unknown" }
Write-Host "  Found: Node.js $nodeVer" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 4: Install dependencies
# ---------------------------------------------------------------------------

Write-Host "[4/6] Installing dependencies..." -ForegroundColor Yellow

Write-Host "  Python packages..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
& $python -m pip install -q --upgrade pip 2>&1 | Out-Null
& $python -m pip install -q -r (Join-Path $bumblebeeRoot "requirements.txt") 2>&1 | Out-Null
& $python -m pip install -q -r (Join-Path $bumblebeeRoot "dashboard\api\requirements.txt") 2>&1 | Out-Null
$ErrorActionPreference = "Stop"

Write-Host "  Dashboard frontend..." -ForegroundColor Yellow
$uiDir = Join-Path $bumblebeeRoot "dashboard\ui"
Set-Location $uiDir
$ErrorActionPreference = "Continue"
npm install --silent 2>&1 | Out-Null
npm run build 2>&1 | Out-Null
$ErrorActionPreference = "Stop"

$buildDir = Join-Path $uiDir "build"
if (-not (Test-Path $buildDir)) {
    Write-Host "  WARNING: Frontend build failed. Dashboard will run in API-only mode." -ForegroundColor Red
    Write-Host "  Run 'cd $uiDir && npm run build' manually to fix." -ForegroundColor Red
}
else {
    Write-Host "  Frontend built successfully." -ForegroundColor Green
}

Set-Location $bumblebeeRoot

# ---------------------------------------------------------------------------
# Step 5: Create config
# ---------------------------------------------------------------------------

Write-Host "[5/6] Configuring..." -ForegroundColor Yellow

$configPath = Join-Path $bumblebeeRoot "dashboard\dashboard.config.json"
if (-not (Test-Path $configPath)) {
    # Auto-discover demo projects
    $demoPaths = @{}
    $demosDir = Join-Path $bumblebeeRoot "demos"
    if (Test-Path $demosDir) {
        Get-ChildItem $demosDir -Directory | ForEach-Object {
            $dbFile = Join-Path $_.FullName "tickets.db"
            if (Test-Path $dbFile) {
                $relPath = "../demos/$($_.Name)/tickets.db"
                $demoPaths[$_.Name] = $relPath
                Write-Host "  Found demo project: $($_.Name)" -ForegroundColor Green
            }
        }
    }
    $config = @{
        ticketDbPaths = $demoPaths
        apiPort = $Port
        healthChecks = @()
        lemonadeUrl = "http://[::1]:13305"
    }
    $jsonText = $config | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText($configPath, $jsonText, [System.Text.UTF8Encoding]::new($false))
    Write-Host "  Created dashboard.config.json" -ForegroundColor Green
}
else {
    Write-Host "  Config already exists, keeping current settings." -ForegroundColor Green
}

$projectsDir = Join-Path $bumblebeeRoot "projects"
if (-not (Test-Path $projectsDir)) {
    New-Item -ItemType Directory -Path $projectsDir -Force | Out-Null
}

# ---------------------------------------------------------------------------
# Step 6: Register service (optional)
# ---------------------------------------------------------------------------

if (-not $SkipService) {
    Write-Host "[6/6] Registering dashboard service..." -ForegroundColor Yellow

    $taskName = "Bumblebee-Dashboard"
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

    if ($existing) {
        Write-Host "  Task '$taskName' already exists. Restarting..." -ForegroundColor Yellow
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }

    # Create startup script (PowerShell)
    $startScript = Join-Path $bumblebeeRoot "dashboard\start-service.ps1"
    $dashDir = Join-Path $bumblebeeRoot "dashboard"
    $lines = @(
        '# Auto-generated by install.ps1',
        ('$env:DASHBOARD_CONFIG = Join-Path $PSScriptRoot "dashboard.config.json"'),
        'Set-Location $PSScriptRoot',
        ('python -m uvicorn api.main:app --host 0.0.0.0 --port ' + $Port + ' 2>&1 | Tee-Object -FilePath (Join-Path $PSScriptRoot "uvicorn.log")')
    )
    $lines -join "`r`n" | Set-Content $startScript -Encoding UTF8

    # Create bat wrapper (reliable with scheduled tasks)
    $batWrapper = Join-Path $bumblebeeRoot "dashboard\start-dashboard.bat"
    $batLines = @(
        '@echo off',
        ('powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $startScript + '"')
    )
    $batLines -join "`r`n" | Set-Content $batWrapper -Encoding ASCII

    try {
        $action = New-ScheduledTaskAction -Execute $batWrapper
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)
        $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

        if ($existing) {
            Set-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
        }
        else {
            Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null
        }

        Start-ScheduledTask -TaskName $taskName
        Write-Host "  Dashboard registered as '$taskName' (starts at logon, auto-restart)." -ForegroundColor Green
    }
    catch {
        Write-Host "  WARNING: Could not register scheduled task (might need admin)." -ForegroundColor Red
        Write-Host "  You can start the dashboard manually: cd dashboard; .\start.ps1" -ForegroundColor Yellow
    }
}
else {
    Write-Host "[6/6] Skipping service registration." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Step 7: Set up demo apps and desktop shortcuts
# ---------------------------------------------------------------------------

Write-Host "[7/7] Setting up demo apps..." -ForegroundColor Yellow

$demosDir = Join-Path $bumblebeeRoot "demos"
if (Test-Path $demosDir) {
    # Install showcase app deps
    $showcaseApp = Join-Path $demosDir "food-cart\showcase-app"
    if (Test-Path $showcaseApp) {
        $showcaseReqs = Join-Path $showcaseApp "backend\requirements.txt"
        if (Test-Path $showcaseReqs) {
            & $python -m pip install -q -r $showcaseReqs 2>&1 | Out-Null
        }
        # Seed the demo database
        $seedScript = Join-Path $showcaseApp "backend\seed.py"
        $dbFile = Join-Path $showcaseApp "backend\food-cart.db"
        if ((Test-Path $seedScript) -and !(Test-Path $dbFile)) {
            Set-Location (Join-Path $showcaseApp "backend")
            & $python seed.py 2>&1 | Out-Null
            Write-Host "  Seeded Food Cart demo data." -ForegroundColor Green
        }
        # Create desktop shortcut
        $shortcutScript = Join-Path $showcaseApp "create-shortcut.ps1"
        if (Test-Path $shortcutScript) {
            & powershell -ExecutionPolicy Bypass -File $shortcutScript -AppDir $showcaseApp 2>&1 | Out-Null
        }
    }
}

# Create Bumblebee Dashboard desktop shortcut
$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$dashShortcut = $shell.CreateShortcut((Join-Path $desktop "Bumblebee Dashboard.lnk"))
$dashShortcut.TargetPath = "powershell.exe"
$dashShortcut.Arguments = "-ExecutionPolicy Bypass -File `"$(Join-Path $bumblebeeRoot 'dashboard\start.ps1')`""
$dashShortcut.WorkingDirectory = Join-Path $bumblebeeRoot "dashboard"
$dashShortcut.Description = "Launch the Bumblebee coding dashboard"
$dashShortcut.Save()
Write-Host "  Created desktop shortcuts." -ForegroundColor Green

Set-Location $bumblebeeRoot

# Done
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

if (-not $NoLaunch) {
    Write-Host "Opening dashboard..." -ForegroundColor Cyan
    Start-Sleep -Seconds 3
    $dashUrl = "http://localhost:$Port"
    Start-Process $dashUrl
}
