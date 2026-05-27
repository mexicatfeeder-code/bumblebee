<#
.SYNOPSIS
    Launch the Food Cart Demo App
.DESCRIPTION
    Starts the Food Cart ordering app (backend API + frontend)
    on http://localhost:8000
.EXAMPLE
    .\start.ps1
    .\start.ps1 -Port 8000
#>
param(
    [int]$Port = 8000
)

$root = Split-Path $MyInvocation.MyCommand.Path -Parent
$backendDir = Join-Path $root "backend"

Write-Host ""
Write-Host "  Food Cart Demo App" -ForegroundColor Yellow
Write-Host "  Built by Bumblebee (local AI)" -ForegroundColor Cyan
Write-Host ""

# Install backend deps
Write-Host "Checking dependencies..." -ForegroundColor Yellow
pip install -q -r (Join-Path $backendDir "requirements.txt") 2>&1 | Out-Null

# Seed database if it doesn't exist
$dbPath = Join-Path $backendDir "food-cart.db"
if (!(Test-Path $dbPath)) {
    Write-Host "Seeding demo data..." -ForegroundColor Yellow
    Set-Location $backendDir
    python seed.py
    Write-Host "  Done." -ForegroundColor Green
}

# Start the server
Set-Location $backendDir
Write-Host "Starting on http://localhost:$Port ..." -ForegroundColor Cyan
Write-Host ""
python -m uvicorn main:app --host 0.0.0.0 --port $Port
