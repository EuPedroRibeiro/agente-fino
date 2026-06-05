$ErrorActionPreference = "Stop"
$ProjectPath = $PSScriptRoot
$Url = "http://127.0.0.1:8765/login"
Set-Location -LiteralPath $ProjectPath
if (-not (Test-Path ".\main.py")) { throw "main.py nao encontrado." }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python nao encontrado no PATH." }
$listening = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Host "NexusTI AI ja esta rodando em $Url"
    Start-Process $Url
    return
}
Start-Job -ScriptBlock { Start-Sleep -Seconds 2; Start-Process "http://127.0.0.1:8765/login" } | Out-Null
python main.py
