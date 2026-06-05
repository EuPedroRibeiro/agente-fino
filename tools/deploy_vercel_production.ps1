param(
    [switch]$SkipTests,
    [switch]$ConfigureEnv,
    [switch]$AllowPaidProviders,
    [string]$Project = $env:VERCEL_PROJECT,
    [string]$Scope = $env:VERCEL_SCOPE
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

if (-not $AllowPaidProviders) {
    $env:OPENAI_ENABLED = "false"
    $env:OPENAI_USE_FOR_VERIFICATION = "false"
    $env:OPENAI_FAST_ENABLED = "false"
}

if ($ConfigureEnv) {
    $configArgs = @()
    if (-not [string]::IsNullOrWhiteSpace($Project)) {
        $configArgs += @("-Project", $Project)
    }
    if (-not [string]::IsNullOrWhiteSpace($Scope)) {
        $configArgs += @("-Scope", $Scope)
    }
    if ($AllowPaidProviders) {
        $configArgs += "-IncludeOpenAI"
    }
    & (Join-Path $PSScriptRoot "configure_vercel_production_env.ps1") @configArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Configuracao de envs da Vercel falhou."
    }
}

$readinessArgs = @()
if ($AllowPaidProviders) {
    $readinessArgs += "-AllowPaidProviders"
}
& (Join-Path $PSScriptRoot "check_production_readiness.ps1") @readinessArgs
if ($LASTEXITCODE -ne 0) {
    throw "Prontidao de producao falhou. Corrija os itens acima antes do deploy."
}

if (-not $SkipTests) {
    Write-Host "Rodando testes antes do deploy..." -ForegroundColor Cyan
    python -B -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) {
        throw "Testes falharam. Deploy cancelado."
    }
}

if ($AllowPaidProviders) {
    Write-Host "Iniciando deploy de producao na Vercel com providers pagos permitidos por opcao explicita..." -ForegroundColor Cyan
} else {
    Write-Host "Iniciando deploy de producao na Vercel em modo sem cobranca: OpenAI desativado." -ForegroundColor Cyan
}
$deployOutput = & npx.cmd vercel deploy --prod 2>&1
$exitCode = $LASTEXITCODE
$deployOutput | ForEach-Object { Write-Host $_ }

if ($exitCode -ne 0) {
    throw "Deploy Vercel falhou."
}

$deploymentUrl = ($deployOutput | Select-String -Pattern "https://[^\s]+" -AllMatches | ForEach-Object {
    $_.Matches | ForEach-Object { $_.Value }
} | Select-Object -Last 1)

if ($deploymentUrl) {
    $healthUrl = "$deploymentUrl/api/health"
    Write-Host "Validando $healthUrl" -ForegroundColor Cyan
    try {
        $health = Invoke-RestMethod $healthUrl -TimeoutSec 30
        $health | Format-List
    } catch {
        Write-Host "Deploy concluido, mas /api/health nao respondeu no teste automatico: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}
