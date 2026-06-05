$ErrorActionPreference = "Continue"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot ".")
Set-Location $ProjectRoot

Write-Host "== Agente Fino security check =="
Write-Host "Projeto: $($ProjectRoot.Path)"

Write-Host "`n== pip check =="
python -m pip check

Write-Host "`n== pip outdated =="
python -m pip list --outdated

Write-Host "`n== pip-audit =="
if (Get-Command pip-audit -ErrorAction SilentlyContinue) {
  pip-audit
} else {
  Write-Host "pip-audit nao instalado; pulando."
}

Write-Host "`n== bandit =="
if (Get-Command bandit -ErrorAction SilentlyContinue) {
  bandit -q -r app
} else {
  Write-Host "bandit nao instalado; pulando."
}

Write-Host "`n== secret scan simples =="
$patterns = @("sk-proj-[A-Za-z0-9_-]{20,}", "sk-[A-Za-z0-9_-]{20,}", "AIza[A-Za-z0-9_-]{20,}", "Authorization:\s*Bearer\s+\S+")
$files = Get-ChildItem -Path app,tests,tools -File -Recurse -ErrorAction SilentlyContinue
foreach ($file in $files) {
  $content = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
  foreach ($pattern in $patterns) {
    if ($content -match $pattern) {
      Write-Host "Possivel segredo/padrao sensivel em $($file.FullName)"
      break
    }
  }
}

Write-Host "`nSecurity check concluido."
