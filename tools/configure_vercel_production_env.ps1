param(
    [string]$Project = $env:VERCEL_PROJECT,
    [string]$Scope = $env:VERCEL_SCOPE,
    [ValidateSet("production", "preview", "development")]
    [string]$Environment = "production",
    [switch]$Replace,
    [switch]$GenerateSessionSecret,
    [switch]$IncludeOpenAI
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

function Test-CommandAvailable {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-EnvOrDefault {
    param(
        [string]$Name,
        [string]$Default
    )
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value
}

function Require-Env {
    param([string]$Name)
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Variavel obrigatoria ausente: $Name"
    }
    return $value
}

function Invoke-Vercel {
    param([string[]]$Arguments)
    & npx.cmd @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Vercel CLI falhou: npx.cmd $($Arguments -join ' ')"
    }
}

function Set-VercelEnv {
    param(
        [string]$Name,
        [string]$Value,
        [bool]$Sensitive = $false
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return
    }

    if ($Replace) {
        Write-Host "Removendo valor anterior de $Name em $Environment, se existir..." -ForegroundColor DarkGray
        & npx.cmd vercel env rm $Name $Environment --yes | Out-Host
    }

    $args = @("vercel", "env", "add", $Name, $Environment)
    if ($Sensitive) {
        $args += "--sensitive"
    }

    $label = if ($Sensitive) { "[secret]" } else { $Value }
    Write-Host ("Configurando {0}={1} em {2}" -f $Name, $label, $Environment) -ForegroundColor Cyan
    $Value | & npx.cmd @args
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao configurar $Name. Se ela ja existir, rode novamente com -Replace."
    }
}

function Remove-VercelEnvIfPresent {
    param([string]$Name)

    Write-Host "Garantindo que $Name nao fique configurada no modo sem cobranca..." -ForegroundColor DarkGray
    & npx.cmd vercel env rm $Name $Environment --yes 2>$null | Out-Null
}

if (-not (Test-CommandAvailable "npx.cmd")) {
    throw "npx.cmd nao encontrado. Instale Node.js/npm ou a Vercel CLI."
}

if (-not (Test-Path ".vercel\project.json")) {
    if ([string]::IsNullOrWhiteSpace($Project)) {
        throw "Projeto Vercel nao linkado. Rode 'npx.cmd vercel link' ou passe -Project <nome-ou-id>."
    }

    $linkArgs = @("vercel", "link", "--yes", "--project", $Project)
    if (-not [string]::IsNullOrWhiteSpace($Scope)) {
        $linkArgs += @("--scope", $Scope)
    }
    Invoke-Vercel $linkArgs
}

if ($GenerateSessionSecret -and [string]::IsNullOrWhiteSpace($env:AGENTE_FINO_SESSION_SECRET)) {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    $env:AGENTE_FINO_SESSION_SECRET = [Convert]::ToBase64String($bytes)
    Write-Host "AGENTE_FINO_SESSION_SECRET gerado localmente e enviado sem impressao do valor." -ForegroundColor Green
}

$databaseUrl = Require-Env "DATABASE_URL"
$sessionSecret = Require-Env "AGENTE_FINO_SESSION_SECRET"
$adminPasswordHash = Require-Env "AGENTE_FINO_ADMIN_PASSWORD_HASH"
$geminiApiKey = Require-Env "GEMINI_API_KEY"

$allowedOrigins = Get-EnvOrDefault "AGENTE_FINO_ALLOWED_ORIGINS" ""
if ([string]::IsNullOrWhiteSpace($allowedOrigins) -and -not [string]::IsNullOrWhiteSpace($Project)) {
    $allowedOrigins = "https://$Project.vercel.app"
}

$publicVars = @(
    @{ Name = "NEXUSTI_APP_NAME"; Value = "Agente Fino" },
    @{ Name = "AGENTE_FINO_RUNTIME"; Value = "cloud" },
    @{ Name = "AGENTE_FINO_ENV"; Value = "production" },
    @{ Name = "AGENTE_FINO_PUBLIC_MODE"; Value = "true" },
    @{ Name = "AGENTE_FINO_SECURITY_ENABLED"; Value = "true" },
    @{ Name = "AGENTE_FINO_REQUIRE_LOGIN"; Value = "true" },
    @{ Name = "AGENTE_FINO_DB_ENGINE"; Value = "postgres" },
    @{ Name = "AGENTE_FINO_ALLOWED_ORIGINS"; Value = $allowedOrigins },
    @{ Name = "AGENTE_FINO_ADMIN_USER"; Value = (Get-EnvOrDefault "AGENTE_FINO_ADMIN_USER" "Pedro") },
    @{ Name = "DEFAULT_PROVIDER"; Value = (Get-EnvOrDefault "DEFAULT_PROVIDER" "gemini") },
    @{ Name = "OPENAI_ENABLED"; Value = ($(if ($IncludeOpenAI) { Get-EnvOrDefault "OPENAI_ENABLED" "true" } else { "false" })) },
    @{ Name = "OPENAI_MODEL"; Value = (Get-EnvOrDefault "OPENAI_MODEL" "gpt-5.4-mini") },
    @{ Name = "OPENAI_FALLBACK_MODEL"; Value = (Get-EnvOrDefault "OPENAI_FALLBACK_MODEL" "gpt-5.4-mini") },
    @{ Name = "OPENAI_VERIFIER_MODEL"; Value = (Get-EnvOrDefault "OPENAI_VERIFIER_MODEL" "gpt-5.4-mini") },
    @{ Name = "OPENAI_USE_FOR_VERIFICATION"; Value = ($(if ($IncludeOpenAI) { Get-EnvOrDefault "OPENAI_USE_FOR_VERIFICATION" "true" } else { "false" })) },
    @{ Name = "OPENAI_TIMEOUT_SECONDS"; Value = (Get-EnvOrDefault "OPENAI_TIMEOUT_SECONDS" "12") },
    @{ Name = "OPENAI_FAST_ENABLED"; Value = ($(if ($IncludeOpenAI) { Get-EnvOrDefault "OPENAI_FAST_ENABLED" "true" } else { "false" })) },
    @{ Name = "OPENAI_WEB_SEARCH_ENABLED"; Value = (Get-EnvOrDefault "OPENAI_WEB_SEARCH_ENABLED" "false") },
    @{ Name = "GEMINI_MODEL"; Value = (Get-EnvOrDefault "GEMINI_MODEL" "gemini-2.5-flash") },
    @{ Name = "GEMINI_TIMEOUT_SECONDS"; Value = (Get-EnvOrDefault "GEMINI_TIMEOUT_SECONDS" "35") },
    @{ Name = "LOCAL_RULES_ONLY_FALLBACK"; Value = "true" },
    @{ Name = "NEXUSTI_OLLAMA_ENABLED"; Value = "false" },
    @{ Name = "AGENTE_FINO_MEMORY_ENABLED"; Value = (Get-EnvOrDefault "AGENTE_FINO_MEMORY_ENABLED" "true") },
    @{ Name = "AGENTE_FINO_RAG_ENABLED"; Value = (Get-EnvOrDefault "AGENTE_FINO_RAG_ENABLED" "false") },
    @{ Name = "VECTOR_STORE"; Value = (Get-EnvOrDefault "VECTOR_STORE" "disabled") },
    @{ Name = "AGENTE_FINO_RATE_LIMIT_ENABLED"; Value = "true" },
    @{ Name = "AGENTE_FINO_CSRF_ENABLED"; Value = "true" },
    @{ Name = "AGENTE_FINO_SECURITY_HEADERS_ENABLED"; Value = "true" },
    @{ Name = "AGENTE_FINO_AUDIT_LOG_ENABLED"; Value = "true" }
)

$secretVars = @(
    @{ Name = "DATABASE_URL"; Value = $databaseUrl },
    @{ Name = "AGENTE_FINO_SESSION_SECRET"; Value = $sessionSecret },
    @{ Name = "AGENTE_FINO_ADMIN_PASSWORD_HASH"; Value = $adminPasswordHash },
    @{ Name = "GEMINI_API_KEY"; Value = $geminiApiKey }
)

if ($IncludeOpenAI) {
    $secretVars += @{ Name = "OPENAI_API_KEY"; Value = (Require-Env "OPENAI_API_KEY") }
} else {
    Remove-VercelEnvIfPresent "OPENAI_API_KEY"
}

foreach ($item in $publicVars) {
    Set-VercelEnv -Name $item.Name -Value $item.Value -Sensitive $false
}

foreach ($item in $secretVars) {
    Set-VercelEnv -Name $item.Name -Value $item.Value -Sensitive $true
}

if ($IncludeOpenAI) {
    Write-Host "Env vars de producao enviadas para Vercel sem imprimir segredos. OpenAI foi incluido por opcao explicita." -ForegroundColor Green
} else {
    Write-Host "Env vars de producao enviadas para Vercel em modo sem cobranca: OpenAI desativado e Gemini como provider gratuito." -ForegroundColor Green
}
