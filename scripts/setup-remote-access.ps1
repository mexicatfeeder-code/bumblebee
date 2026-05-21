# ============================================================
# Bumblebee Remote Test — Give Pixel Access to This Machine
# ============================================================
# Run this script on any fresh Windows machine.
# It sets up SSH so Pixel can connect and test-install Bumblebee.
#
# Requirements: Windows 10/11, admin PowerShell
# Time: ~2 minutes
# ============================================================

Write-Host ""
Write-Host "=== Bumblebee Remote Access Setup ===" -ForegroundColor Cyan
Write-Host ""

# --- Step 1: Check if running as admin ---
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[!] This script needs admin. Right-click PowerShell -> Run as Administrator" -ForegroundColor Red
    Write-Host "    Then paste this command:" -ForegroundColor Yellow
    Write-Host "    irm https://raw.githubusercontent.com/mexicatfeeder-code/bumblebee/master/_local/setup-remote-access.ps1 | iex" -ForegroundColor Yellow
    exit 1
}

# --- Step 2: Install OpenSSH Server ---
Write-Host "[1/5] Installing OpenSSH Server..." -ForegroundColor Yellow
$sshCapability = Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
if ($sshCapability.State -ne 'Installed') {
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-Null
    Write-Host "      Installed." -ForegroundColor Green
} else {
    Write-Host "      Already installed." -ForegroundColor Green
}

# --- Step 3: Start and enable SSH service ---
Write-Host "[2/5] Starting SSH service..." -ForegroundColor Yellow
Start-Service sshd -ErrorAction SilentlyContinue
Set-Service -Name sshd -StartupType Automatic
Write-Host "      SSH running and set to auto-start." -ForegroundColor Green

# --- Step 4: Firewall rule ---
Write-Host "[3/5] Checking firewall rule..." -ForegroundColor Yellow
$rule = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
if (-not $rule) {
    New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' `
        -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 | Out-Null
    Write-Host "      Firewall rule created." -ForegroundColor Green
} else {
    Write-Host "      Firewall rule exists." -ForegroundColor Green
}

# --- Step 5: Check prerequisites ---
Write-Host "[4/5] Checking prerequisites..." -ForegroundColor Yellow

$pythonVer = & python --version 2>&1
$gitVer = & git --version 2>&1
$nodeVer = & node --version 2>&1

$missing = @()
if ($LASTEXITCODE -ne 0 -or $pythonVer -notmatch 'Python 3') { $missing += "Python 3.11+ (https://python.org)" }
if ($gitVer -notmatch 'git version') { $missing += "Git (https://git-scm.com)" }
if ($nodeVer -notmatch 'v\d') { $missing += "Node.js 18+ (https://nodejs.org)" }

if ($missing.Count -gt 0) {
    Write-Host "      Missing:" -ForegroundColor Red
    foreach ($m in $missing) { Write-Host "        - $m" -ForegroundColor Red }
    Write-Host ""
    Write-Host "      Install the missing tools, then re-run this script." -ForegroundColor Yellow
} else {
    Write-Host "      Python: $pythonVer" -ForegroundColor Green
    Write-Host "      Git:    $gitVer" -ForegroundColor Green
    Write-Host "      Node:   $nodeVer" -ForegroundColor Green
}

# --- Step 6: Gather connection info ---
Write-Host "[5/5] Gathering connection info..." -ForegroundColor Yellow

$username = $env:USERNAME
$hostname = $env:COMPUTERNAME
$ips = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and $_.PrefixOrigin -ne 'WellKnown'
} | Select-Object -ExpandProperty IPAddress) -join ", "

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Green
Write-Host ""
Write-Host "Send these details to Pixel:" -ForegroundColor Cyan
Write-Host "--------------------------------------"
Write-Host "  Machine:  $hostname"
Write-Host "  Username: $username"
Write-Host "  IP(s):    $ips"
Write-Host "  SSH port: 22"
Write-Host "  Password: (your Windows login password)"
Write-Host "--------------------------------------"
Write-Host ""
Write-Host "Pixel will SSH in, clone Bumblebee, and run the test project." -ForegroundColor Gray
Write-Host "You can revoke access later with: Stop-Service sshd" -ForegroundColor Gray
Write-Host ""
