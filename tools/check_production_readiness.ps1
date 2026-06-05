param(
    [switch]$Json,
    [switch]$AllowPaidProviders
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$checks = New-Object System.Collections.Generic.List[object]

function Add-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Message,
        [string]$Severity = "required"
    )

    $checks.Add([pscustomobject]@{
        name = $Name
        ok = $Ok
        severity = $Severity
        message = $Message
    })
}

function Test-CommandAvailable {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-EnvPresent {
    param([string]$Name)
    return -not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($Name))
}

$vercelCliOk = Test-CommandAvailable "npx.cmd"
$vercelLinked = Test-Path ".vercel\project.json"
$vercelAuth = (Test-EnvPresent "VERCEL_TOKEN") -or (Test-Path "$env:USERPROFILE\.vercel")
$dbEngine = [Environment]::GetEnvironmentVariable("AGENTE_FINO_DB_ENGINE")
$geminiConfigured = Test-EnvPresent "GEMINI_API_KEY"
$openAiExplicitlyEnabled = ([Environment]::GetEnvironmentVariable("OPENAI_ENABLED") -eq "true")
$providerConfigured = if ($AllowPaidProviders) { ((Test-EnvPresent "OPENAI_API_KEY") -or $geminiConfigured) } else { $geminiConfigured }

Add-Check "vercel_cli" $vercelCliOk "Vercel CLI via npx.cmd precisa estar disponivel."
Add-Check "vercel_auth" $vercelAuth "Autentique com 'npx.cmd vercel login' ou defina VERCEL_TOKEN."
Add-Check "vercel_project_link" $vercelLinked "Linke o projeto com 'npx.cmd vercel link --yes --project <projeto>'."
Add-Check "AGENTE_FINO_DB_ENGINE" ($dbEngine -eq "postgres") "Defina AGENTE_FINO_DB_ENGINE=postgres para producao."
Add-Check "DATABASE_URL" (Test-EnvPresent "DATABASE_URL") "Defina DATABASE_URL com a conexao Postgres gerenciada."
Add-Check "AGENTE_FINO_SESSION_SECRET" (Test-EnvPresent "AGENTE_FINO_SESSION_SECRET") "Defina AGENTE_FINO_SESSION_SECRET com segredo forte."
Add-Check "AGENTE_FINO_ADMIN_PASSWORD_HASH" (Test-EnvPresent "AGENTE_FINO_ADMIN_PASSWORD_HASH") "Defina AGENTE_FINO_ADMIN_PASSWORD_HASH com hash PBKDF2."
Add-Check "provider_api_key" $providerConfigured ($(if ($AllowPaidProviders) { "Configure OPENAI_API_KEY ou GEMINI_API_KEY para LLM real." } else { "Configure GEMINI_API_KEY free tier. OpenAI fica fora do modo sem cobranca." })) "recommended"
Add-Check "no_billing_openai_disabled" ($AllowPaidProviders -or -not $openAiExplicitlyEnabled) "No modo sem cobranca, OPENAI_ENABLED nao pode estar true." "required"

$requiredFailures = @($checks | Where-Object { $_.severity -eq "required" -and -not $_.ok })
$recommendedFailures = @($checks | Where-Object { $_.severity -ne "required" -and -not $_.ok })

$result = [pscustomobject]@{
    ready = ($requiredFailures.Count -eq 0)
    project_root = $ProjectRoot.Path
    checks = $checks
    required_missing = @($requiredFailures | Select-Object -ExpandProperty name)
    recommended_missing = @($recommendedFailures | Select-Object -ExpandProperty name)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 5
} else {
    Write-Host "Agente Fino production readiness" -ForegroundColor Cyan
    foreach ($check in $checks) {
        $status = if ($check.ok) { "OK" } else { "FALTA" }
        $color = if ($check.ok) { "Green" } elseif ($check.severity -eq "required") { "Red" } else { "Yellow" }
        Write-Host ("[{0}] {1} - {2}" -f $status, $check.name, $check.message) -ForegroundColor $color
    }

    if ($result.ready) {
        Write-Host "Pronto para configurar envs/deploy Vercel." -ForegroundColor Green
    } else {
        Write-Host "Ainda faltam requisitos obrigatorios. Nenhum segredo foi impresso." -ForegroundColor Red
    }
}

if (-not $result.ready) {
    exit 1
}
