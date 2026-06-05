$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
python -m PyInstaller --noconfirm --onedir --windowed --name "NexusTI AI" `
    --icon "app/static/favicon.ico" `
    --add-data "app/templates;app/templates" `
    --add-data "app/static;app/static" `
    --add-data "requirements.txt;." `
    desktop_app.py
Write-Host "[NexusTI AI] Build release gerado em: $PSScriptRoot\dist\NexusTI AI"
