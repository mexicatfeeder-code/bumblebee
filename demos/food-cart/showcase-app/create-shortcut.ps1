# Create a desktop shortcut for the Food Cart Demo App
param(
    [string]$Name = "Food Cart Demo",
    [string]$AppDir = ""
)

if ($AppDir -eq "") {
    $AppDir = Split-Path $MyInvocation.MyCommand.Path -Parent
}

$startScript = Join-Path $AppDir "start.ps1"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "$Name.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-ExecutionPolicy Bypass -NoExit -File `"$startScript`""
$shortcut.WorkingDirectory = $AppDir
$shortcut.Description = "Launch the Food Cart ordering app (built by Bumblebee)"
$shortcut.Save()

Write-Host "Created desktop shortcut: $shortcutPath" -ForegroundColor Green
