# ============================================================
# Bumblebee Remote Setup — One-liner to get Pixel access
# ============================================================
# Run on any fresh Windows 10/11 machine in admin PowerShell.
# Installs all prerequisites, sets up SSH, and prints connection info.
#
# Usage (admin PowerShell):
#   irm https://raw.githubusercontent.com/mexicatfeeder-code/bumblebee/master/scripts/setup-remote-access.ps1 | iex
# ============================================================

Write-Host ""
Write-Host "=== Bumblebee Remote Access Setup ===" -ForegroundColor Cyan
Write-Host ""

# --- Check admin ---
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[!] This script needs admin. Right-click PowerShell -> Run as Administrator" -ForegroundColor Red
    exit 1
}

# --- Step 1: Install OpenSSH Server ---
Write-Host "[1/6] Installing OpenSSH Server..." -ForegroundColor Yellow
$sshCapability = Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
if ($sshCapability.State -ne 'Installed') {
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-Null
    Write-Host "      Installed." -ForegroundColor Green
} else {
    Write-Host "      Already installed." -ForegroundColor Green
}

# --- Step 2: Start and enable SSH service ---
Write-Host "[2/6] Starting SSH service..." -ForegroundColor Yellow
Start-Service sshd -ErrorAction SilentlyContinue
Set-Service -Name sshd -StartupType Automatic
Write-Host "      SSH running and set to auto-start." -ForegroundColor Green

# --- Step 3: Firewall rule ---
Write-Host "[3/6] Checking firewall..." -ForegroundColor Yellow
$rule = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
if (-not $rule) {
    New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' `
        -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 | Out-Null
    Write-Host "      Firewall rule created." -ForegroundColor Green
} else {
    Write-Host "      Firewall rule exists." -ForegroundColor Green
}

# --- Step 4: Install prerequisites via winget ---
Write-Host "[4/6] Installing prerequisites..." -ForegroundColor Yellow

# Check winget availability
$winget = Get-Command winget -ErrorAction SilentlyContinue
if (-not $winget) {
    Write-Host "      [!] winget not found. Install App Installer from the Microsoft Store," -ForegroundColor Red
    Write-Host "          then re-run this script." -ForegroundColor Red
    exit 1
}

function Install-IfMissing {
    param([string]$TestCmd, [string]$WingetId, [string]$Label)
    $ver = $null
    try { $ver = & $TestCmd --version 2>&1 | Out-String } catch {}
    if ($ver -and $ver -match '\d') {
        Write-Host "      $Label already installed: $($ver.Trim())" -ForegroundColor Green
        return
    }
    Write-Host "      Installing $Label..." -ForegroundColor Yellow
    winget install --id $WingetId --accept-source-agreements --accept-package-agreements --silent 2>&1 | Out-Null
    # Refresh PATH so the new tool is available immediately
    $machPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machPath;$userPath"
    try { $ver = & $TestCmd --version 2>&1 | Out-String } catch {}
    if ($ver -and $ver -match '\d') {
        Write-Host "      $Label installed: $($ver.Trim())" -ForegroundColor Green
    } else {
        Write-Host "      $Label installed (may need a new terminal to verify)." -ForegroundColor Yellow
    }
}

Install-IfMissing -TestCmd "python" -WingetId "Python.Python.3.11" -Label "Python 3.11"
Install-IfMissing -TestCmd "git"    -WingetId "Git.Git"            -Label "Git"
Install-IfMissing -TestCmd "node"   -WingetId "OpenJS.NodeJS.LTS"  -Label "Node.js LTS"

# --- Step 5: Install Pixel's SSH public key ---
Write-Host "[5/6] Installing Pixel's SSH key..." -ForegroundColor Yellow

$pixelKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAMFV/IgeRN1O+ah1jh5Zv/gE0EDHsfACX1n5nolYbOL rad_t@gopo"
$adminKeyFile = "$env:ProgramData\ssh\administrators_authorized_keys"
$userKeyFile = "$env:USERPROFILE\.ssh\authorized_keys"

# Admin authorized_keys (used by default sshd_config for admin accounts)
if (!(Test-Path $adminKeyFile) -or !(Select-String -Path $adminKeyFile -SimpleMatch $pixelKey -Quiet)) {
    Add-Content -Path $adminKeyFile -Value $pixelKey -Encoding UTF8
    icacls $adminKeyFile /inheritance:r /grant "SYSTEM:(R)" /grant "BUILTIN\Administrators:(R)" | Out-Null
    Write-Host "      Key installed (admin)." -ForegroundColor Green
} else {
    Write-Host "      Key already present (admin)." -ForegroundColor Green
}

# User authorized_keys (fallback)
if (!(Test-Path "$env:USERPROFILE\.ssh")) { New-Item -ItemType Directory -Path "$env:USERPROFILE\.ssh" -Force | Out-Null }
if (!(Test-Path $userKeyFile) -or !(Select-String -Path $userKeyFile -SimpleMatch $pixelKey -Quiet)) {
    Add-Content -Path $userKeyFile -Value $pixelKey -Encoding UTF8
    Write-Host "      Key installed (user)." -ForegroundColor Green
} else {
    Write-Host "      Key already present (user)." -ForegroundColor Green
}

# --- Step 6: Gather connection info ---
Write-Host "[6/6] Gathering connection info..." -ForegroundColor Yellow

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
