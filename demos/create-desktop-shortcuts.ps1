<#
.SYNOPSIS
    Create desktop shortcuts for Bumblebee demo showcase apps
#>
$desktop = [Environment]::GetFolderPath("Desktop")
$root = Split-Path $MyInvocation.MyCommand.Path -Parent

# --- Food Cart ---
$fcTarget = Join-Path $root "food-cart\showcase-app\start.ps1"
if (Test-Path $fcTarget) {
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut("$desktop\Food Cart Demo.lnk")
    $sc.TargetPath = "powershell.exe"
    $sc.Arguments = "-ExecutionPolicy Bypass -File `"$fcTarget`""
    $sc.WorkingDirectory = Split-Path $fcTarget -Parent
    $sc.Description = "Food Cart Ordering App - Built by Bumblebee"
    $sc.IconLocation = "shell32.dll,21"
    $sc.Save()
    Write-Host "Created: Food Cart Demo.lnk" -ForegroundColor Green
}

# --- Pomodoro Planner ---
$ppTarget = Join-Path $root "pomodoro-planner\showcase-app\start.ps1"
if (Test-Path $ppTarget) {
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut("$desktop\Pomodoro Planner Demo.lnk")
    $sc.TargetPath = "powershell.exe"
    $sc.Arguments = "-ExecutionPolicy Bypass -File `"$ppTarget`""
    $sc.WorkingDirectory = Split-Path $ppTarget -Parent
    $sc.Description = "Pomodoro Task Planner - Built by Bumblebee"
    $sc.IconLocation = "shell32.dll,14"
    $sc.Save()
    Write-Host "Created: Pomodoro Planner Demo.lnk" -ForegroundColor Green
}

Write-Host ""
Write-Host "Desktop shortcuts ready." -ForegroundColor Cyan
