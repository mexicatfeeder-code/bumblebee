<#
.SYNOPSIS
    Launch the Pomodoro Planner Demo App
.DESCRIPTION
    Starts the Pomodoro Task Planner (backend API + frontend)
    on http://localhost:4200
.EXAMPLE
    .\start.ps1
    .\start.ps1 -Port 4200
#>
param(
    [int]$Port = 4200
)

$root = Split-Path $MyInvocation.MyCommand.Path -Parent
$backendDir = Join-Path $root "backend"

Write-Host ""
Write-Host "  Pomodoro Task Planner" -ForegroundColor Yellow
Write-Host "  Built by Bumblebee (local AI)" -ForegroundColor Cyan
Write-Host ""

# Install backend deps
Write-Host "Checking dependencies..." -ForegroundColor Yellow
pip install -q -r (Join-Path $backendDir "requirements.txt") 2>&1 | Out-Null

# Seed database if it doesn't exist
$dbPath = Join-Path $backendDir "pomodoro.db"
if (!(Test-Path $dbPath)) {
    Write-Host "Seeding demo data..." -ForegroundColor Yellow
    Set-Location $backendDir
    python seed.py
    Write-Host "  Done." -ForegroundColor Green
}

# Start the server
Set-Location $backendDir
Write-Host "Starting on http://localhost:$Port ..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

# Open browser after a short delay
Start-Job -ScriptBlock { Start-Sleep 2; Start-Process "http://localhost:$using:Port" } | Out-Null

python -m uvicorn main:app --host 0.0.0.0 --port $Port
