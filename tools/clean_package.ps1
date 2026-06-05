param(
  [switch]$IncludeBackups,
  [switch]$IncludeLocalData
)

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

function Remove-SafePath {
  param([Parameter(Mandatory = $true)][string]$Path)
  $resolved = Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue
  if (-not $resolved) { return }
  foreach ($item in $resolved) {
    if (-not $item.Path.StartsWith($ProjectRoot.Path, [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "Caminho fora do projeto bloqueado: $($item.Path)"
    }
    Remove-Item -LiteralPath $item.Path -Recurse -Force -ErrorAction SilentlyContinue
  }
}

Get-ChildItem -Path $ProjectRoot -Directory -Recurse -Force -Filter "__pycache__" | ForEach-Object {
  Remove-SafePath $_.FullName
}

Get-ChildItem -Path $ProjectRoot -File -Recurse -Force -Include "*.pyc","*.pyo" | ForEach-Object {
  Remove-SafePath $_.FullName
}

foreach ($dir in @("build", "dist")) {
  Remove-SafePath (Join-Path $ProjectRoot $dir)
}

if ($IncludeBackups) {
  Get-ChildItem -Path $ProjectRoot -Directory -Force -Filter "backup_*" | ForEach-Object {
    Remove-SafePath $_.FullName
  }
}

if ($IncludeLocalData) {
  foreach ($pattern in @("data\*.db", "data\*.db-*", "data\*.log", "data\server*.log")) {
    $targetDir = Join-Path $ProjectRoot (Split-Path $pattern -Parent)
    $targetFilter = Split-Path $pattern -Leaf
    Get-ChildItem -Path $targetDir -File -Force -ErrorAction SilentlyContinue -Filter $targetFilter | ForEach-Object {
      Remove-SafePath $_.FullName
    }
  }
}

Write-Host "Limpeza concluida dentro de $($ProjectRoot.Path)."
Write-Host "Use -IncludeBackups e/ou -IncludeLocalData apenas ao preparar pacote final."
