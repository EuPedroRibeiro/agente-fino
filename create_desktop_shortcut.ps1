$ErrorActionPreference = "Stop"
$ProjectPath = $PSScriptRoot
$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Iniciar NexusTI AI.lnk"
$Target = "powershell.exe"
$Arguments = "-ExecutionPolicy Bypass -NoExit -File `"$ProjectPath\start_nexus.ps1`""
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Target
$Shortcut.Arguments = $Arguments
$Shortcut.WorkingDirectory = $ProjectPath
$Shortcut.IconLocation = Join-Path $ProjectPath "app\static\favicon.ico"
$Shortcut.Save()
Write-Host "Atalho criado: $ShortcutPath"
