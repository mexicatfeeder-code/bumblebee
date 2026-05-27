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
# Step 5: Ensure Lemonade is running with dual-model support
# ---------------------------------------------------------------------------

Write-Host "[5/8] Checking Lemonade (local AI server)..." -ForegroundColor Yellow

$lemonadeUrl = "http://[::1]:13305"
$lemonadeExe = Join-Path $env:LOCALAPPDATA "lemonade_server\bin\LemonadeServer.exe"
$lemonadeCli = Join-Path $env:LOCALAPPDATA "lemonade_server\bin\lemonade.exe"
$requiredModel = "Qwen3.6-27B-GGUF"
$requiredContext = 32768
$siftModel = "user.gemma-4-E4B-it-GGUF"
$siftCheckpoint = "unsloth/gemma-4-E4B-it-GGUF:UD-Q4_K_XL"
$siftContext = 32768
$lemonadeOk = $false

function Test-LemonadeHealth {
    try {
        $r = Invoke-RestMethod -Uri "$lemonadeUrl/api/v1/health" -TimeoutSec 5 -ErrorAction Stop
        return $r
    } catch {
        return $null
    }
}

function Start-LemonadeAndWait {
    if (-not (Test-Path $lemonadeExe)) {
        Write-Host "  Lemonade not found at $lemonadeExe" -ForegroundColor Red
        Write-Host "  Install Lemonade from https://lemonade-server.ai" -ForegroundColor Yellow
        return $false
    }
    Write-Host "  Starting Lemonade..." -ForegroundColor Yellow
    Start-Process $lemonadeExe -WindowStyle Minimized
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        $h = Test-LemonadeHealth
        if ($h) {
            Write-Host "  Lemonade started." -ForegroundColor Green
            return $true
        }
    }
    Write-Host "  WARNING: Lemonade did not start within 30s." -ForegroundColor Red
    return $false
}

# --- Ensure Lemonade is running ---
$health = Test-LemonadeHealth
if (-not $health) {
    if (Start-LemonadeAndWait) {
        $health = Test-LemonadeHealth
    }
}

if (-not $health) {
    Write-Host "  Lemonade is not available. Skipping model setup." -ForegroundColor Red
    Write-Host "  Start Lemonade manually, then run install.ps1 again." -ForegroundColor Yellow
} else {
    # --- Ensure max_loaded_models >= 2 (required for Forge + Sift) ---
    $maxLlm = $health.max_models.llm
    if ($maxLlm -lt 2) {
        Write-Host "  Lemonade max_loaded_models is $maxLlm - updating to 2..." -ForegroundColor Yellow

        if (Test-Path $lemonadeCli) {
            & $lemonadeCli config set max_loaded_models=2 2>&1 | Out-Null
            Write-Host "  Config updated. Restarting Lemonade..." -ForegroundColor Yellow
        } else {
            Write-Host "  WARNING: lemonade CLI not found, cannot set config." -ForegroundColor Red
            Write-Host "  Open Lemonade settings and set max loaded models to 2." -ForegroundColor Yellow
        }

        # Stop Lemonade
        Get-Process LemonadeServer -ErrorAction SilentlyContinue | Stop-Process -Force
        Get-Process lemonade-app -ErrorAction SilentlyContinue | Stop-Process -Force
        Start-Sleep -Seconds 3

        # Restart
        if (-not (Start-LemonadeAndWait)) {
            Write-Host "  Could not restart Lemonade after config change." -ForegroundColor Red
        }
        $health = Test-LemonadeHealth
    } else {
        Write-Host "  Lemonade max_loaded_models already $maxLlm (good)." -ForegroundColor Green
    }

    if ($health) {
        # --- Forge model (Qwen3.6-27B) ---
        $loadedIds = @()
        if ($health.all_models_loaded) {
            $loadedIds = @($health.all_models_loaded | ForEach-Object { $_.id })
        }

        if ($loadedIds -contains $requiredModel) {
            Write-Host "  Forge: $requiredModel already loaded." -ForegroundColor Green
            $lemonadeOk = $true
        } else {
            Write-Host "  Loading Forge model: $requiredModel (ctx_size: $requiredContext)..." -ForegroundColor Yellow
            try {
                $loadResp = Invoke-RestMethod -Uri "$lemonadeUrl/v1/load" -Method POST `
                    -ContentType "application/json" `
                    -Body (@{
                        model_name = $requiredModel
                        ctx_size = $requiredContext
                        save_options = $true
                    } | ConvertTo-Json) `
                    -TimeoutSec 300 -ErrorAction Stop
                Write-Host "  Forge model loaded. $($loadResp.message)" -ForegroundColor Green
                $lemonadeOk = $true
            } catch {
                Write-Host "  WARNING: Failed to load Forge model - $($_.Exception.Message)" -ForegroundColor Red
            }
        }

        # --- Sift model (Gemma 4 E4B) ---
        # Check if Sift model is registered (may need download)
        $models = (Invoke-RestMethod -Uri "$lemonadeUrl/api/v1/models" -TimeoutSec 5).data
        $siftRegistered = $models | Where-Object { $_.id -eq $siftModel }

        if (-not $siftRegistered) {
            Write-Host "  Downloading Sift model ($siftModel)... this may take a few minutes." -ForegroundColor Yellow
            try {
                Invoke-RestMethod -Uri "$lemonadeUrl/v1/pull" -Method POST `
                    -ContentType "application/json" `
                    -Body (@{
                        model_name = $siftModel
                        checkpoint = $siftCheckpoint
                        recipe = "llamacpp"
                    } | ConvertTo-Json) `
                    -TimeoutSec 600 -ErrorAction Stop | Out-Null
                Write-Host "  Sift model downloaded." -ForegroundColor Green
            } catch {
                Write-Host "  WARNING: Failed to download Sift model - $($_.Exception.Message)" -ForegroundColor Red
            }
        }

        # Refresh loaded list
        $health2 = Test-LemonadeHealth
        $loadedIds2 = @()
        if ($health2 -and $health2.all_models_loaded) {
            $loadedIds2 = @($health2.all_models_loaded | ForEach-Object { $_.id })
        }

        if ($loadedIds2 -contains $siftModel) {
            Write-Host "  Sift: $siftModel already loaded." -ForegroundColor Green
        } else {
            Write-Host "  Loading Sift model: $siftModel (ctx_size: $siftContext)..." -ForegroundColor Yellow
            try {
                Invoke-RestMethod -Uri "$lemonadeUrl/v1/load" -Method POST `
                    -ContentType "application/json" `
                    -Body (@{
                        model_name = $siftModel
                        ctx_size = $siftContext
                        save_options = $true
                    } | ConvertTo-Json) `
                    -TimeoutSec 120 -ErrorAction Stop | Out-Null
                Write-Host "  Sift model loaded." -ForegroundColor Green
            } catch {
                Write-Host "  WARNING: Failed to load Sift model - $($_.Exception.Message)" -ForegroundColor Red
                Write-Host "  Sift will fall back to sharing the Forge model." -ForegroundColor Yellow
            }
        }

        # Final check - verify both models are loaded
        $finalHealth = Test-LemonadeHealth
        if ($finalHealth -and $finalHealth.all_models_loaded) {
            $finalLoaded = @($finalHealth.all_models_loaded | ForEach-Object { $_.id })
            $forgeUp = $finalLoaded -contains $requiredModel
            $siftUp = $finalLoaded -contains $siftModel
            if ($forgeUp -and $siftUp) {
                Write-Host "  Both models active: Forge ($requiredModel) + Sift ($siftModel)" -ForegroundColor Green
            } elseif ($forgeUp) {
                Write-Host "  Forge loaded, Sift not loaded (research will share Forge model)." -ForegroundColor Yellow
            } elseif ($siftUp) {
                Write-Host "  WARNING: Only Sift loaded - Forge model missing. Coding will use wrong model." -ForegroundColor Red
            }
        }
    }
}

# ---------------------------------------------------------------------------
# Step 6: Create config
# ---------------------------------------------------------------------------

Write-Host "[6/8] Configuring..." -ForegroundColor Yellow

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
    $researchDir = Join-Path $bumblebeeRoot "research"
    $researchDb = Join-Path $researchDir "research.db"
    $reportsDir = Join-Path $researchDir "reports"
    # Prefer the food-cart demo's pre-seeded research DB if present
    $demoResearchDb = Join-Path $bumblebeeRoot "demos\food-cart\research\research.db"
    $demoResearchDir = Join-Path $bumblebeeRoot "demos\food-cart\research"
    if (Test-Path $demoResearchDb) {
        $activeResearchDb = $demoResearchDb
        $activeResearchRoot = $demoResearchDir
        Write-Host "  Using food-cart demo research DB." -ForegroundColor Green
    } else {
        $activeResearchDb = $researchDb
        $activeResearchRoot = $researchDir
    }
    $config = @{
        ticketDbPaths = $demoPaths
        apiPort = $Port
        healthChecks = @()
        lemonadeUrl = "http://[::1]:13305"
        researchDbPath = $activeResearchDb
        researchRoot = $activeResearchRoot
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

# Initialize research DB
$researchDir = Join-Path $bumblebeeRoot "research"
$researchDb = Join-Path $researchDir "research.db"
$reportsDir = Join-Path $researchDir "reports"
if (-not (Test-Path $researchDb)) {
    Write-Host "  Initializing research DB..." -ForegroundColor Yellow
    & $python (Join-Path $bumblebeeRoot "scripts\init_research.py") --db-path $researchDb --reports-dir $reportsDir --seed-demo
    Write-Host "  Research DB initialized." -ForegroundColor Green
} else {
    Write-Host "  Research DB already exists." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Step 6: Register service (optional)
# ---------------------------------------------------------------------------

if (-not $SkipService) {
    Write-Host "[7/8] Registering dashboard service..." -ForegroundColor Yellow

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
    Write-Host "[7/8] Skipping service registration." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 8: Set up demo apps and desktop shortcuts
# ---------------------------------------------------------------------------

Write-Host "[8/8] Setting up demo apps..." -ForegroundColor Yellow

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

# Check for Brave Search API key (used by Sift research agent)
$braveKeyPath = Join-Path $env:USERPROFILE ".bumblebee\brave-api-key.txt"
if (Test-Path $braveKeyPath) {
    Write-Host "  Brave Search API key found - Sift web search enabled." -ForegroundColor Green
} else {
    Write-Host "" 
    Write-Host "  NOTE: Sift research agent works best with web search." -ForegroundColor Yellow
    Write-Host "  Get a free Brave Search API key from: https://brave.com/search/api/" -ForegroundColor Yellow
    Write-Host "  Save it to: $braveKeyPath" -ForegroundColor Yellow
}

if (-not $NoLaunch) {
    Write-Host "Opening dashboard..." -ForegroundColor Cyan
    Start-Sleep -Seconds 3
    $dashUrl = "http://localhost:$Port"
    Start-Process $dashUrl
}
