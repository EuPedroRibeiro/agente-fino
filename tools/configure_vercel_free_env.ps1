param(
    [string]$Project = $env:VERCEL_PROJECT,
    [string]$Scope = $env:VERCEL_SCOPE,
    [ValidateSet("production", "preview", "development")]
    [string]$Environment = "production",
    [switch]$Replace,
    [switch]$GenerateSessionSecret
)

$ErrorActionPreference = "Stop"

$argsList = @("-Environment", $Environment)
if (-not [string]::IsNullOrWhiteSpace($Project)) {
    $argsList += @("-Project", $Project)
}
if (-not [string]::IsNullOrWhiteSpace($Scope)) {
    $argsList += @("-Scope", $Scope)
}
if ($Replace) {
    $argsList += "-Replace"
}
if ($GenerateSessionSecret) {
    $argsList += "-GenerateSessionSecret"
}

Write-Host "Configurando Vercel em modo gratuito: Vercel Hobby + Postgres Free + Gemini Free. OpenAI nao sera enviado." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "configure_vercel_production_env.ps1") @argsList
