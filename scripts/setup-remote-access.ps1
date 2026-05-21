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
Write-Host "[1/7] Installing OpenSSH Server..." -ForegroundColor Yellow
$sshCapability = Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
if ($sshCapability.State -ne 'Installed') {
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-Null
    Write-Host "      Installed." -ForegroundColor Green
} else {
    Write-Host "      Already installed." -ForegroundColor Green
}

# --- Step 3: Start and enable SSH service ---
Write-Host "[2/7] Starting SSH service..." -ForegroundColor Yellow
Start-Service sshd -ErrorAction SilentlyContinue
Set-Service -Name sshd -StartupType Automatic
Write-Host "      SSH running and set to auto-start." -ForegroundColor Green

# --- Step 4: Firewall rule ---
Write-Host "[3/7] Checking firewall rule..." -ForegroundColor Yellow
$rule = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
if (-not $rule) {
    New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' `
        -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 | Out-Null
    Write-Host "      Firewall rule created." -ForegroundColor Green
} else {
    Write-Host "      Firewall rule exists." -ForegroundColor Green
}

# --- Step 5: Check prerequisites ---
Write-Host "[4/7] Checking prerequisites..." -ForegroundColor Yellow

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

# --- Step 6: Install Pixel's SSH public key ---
Write-Host "[6/7] Installing Pixel's SSH key..." -ForegroundColor Yellow

$pixelKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAMFV/IgeRN1O+ah1jh5Zv/gE0EDHsfACX1n5nolYbOL rad_t@gopo"

# Windows OpenSSH uses a special file for admin users
$isAdminUser = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$adminKeyFile = "$env:ProgramData\ssh\administrators_authorized_keys"
$userKeyFile = "$env:USERPROFILE\.ssh\authorized_keys"

# Install in admin file (used by default sshd_config for admin users)
if (!(Test-Path $adminKeyFile) -or !(Select-String -Path $adminKeyFile -SimpleMatch $pixelKey -Quiet)) {
    Add-Content -Path $adminKeyFile -Value $pixelKey -Encoding UTF8
    # Fix permissions: SYSTEM + Admins only (required by OpenSSH)
    icacls $adminKeyFile /inheritance:r /grant "SYSTEM:(R)" /grant "BUILTIN\Administrators:(R)" | Out-Null
    Write-Host "      Key installed (admin)." -ForegroundColor Green
} else {
    Write-Host "      Key already present (admin)." -ForegroundColor Green
}

# Also install in user file as fallback
if (!(Test-Path "$env:USERPROFILE\.ssh")) { New-Item -ItemType Directory -Path "$env:USERPROFILE\.ssh" -Force | Out-Null }
if (!(Test-Path $userKeyFile) -or !(Select-String -Path $userKeyFile -SimpleMatch $pixelKey -Quiet)) {
    Add-Content -Path $userKeyFile -Value $pixelKey -Encoding UTF8
    Write-Host "      Key installed (user)." -ForegroundColor Green
} else {
    Write-Host "      Key already present (user)." -ForegroundColor Green
}

# --- Step 7: Gather connection info ---
Write-Host "[7/7] Gathering connection info..." -ForegroundColor Yellow

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
Write-Host "  SSH key:  Installed (no password needed)"
Write-Host "--------------------------------------"
Write-Host ""
Write-Host "Pixel will SSH in, clone Bumblebee, and run the test project." -ForegroundColor Gray
Write-Host "Revoke access: Remove-Item $adminKeyFile; Stop-Service sshd" -ForegroundColor Gray
Write-Host ""
