$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
python -m PyInstaller --noconfirm --onedir --console --name "NexusTI AI Debug" `
    --add-data "app/templates;app/templates" `
    --add-data "app/static;app/static" `
    --add-data "requirements.txt;." `
    desktop_app.py
Write-Host "[NexusTI AI] Build debug gerado em: $PSScriptRoot\dist\NexusTI AI Debug"
