$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "vercel.json"))) {
    throw "PROJECT_ROOT_INVALID: vercel.json nao encontrado em $ProjectRoot"
}

$cacheDirs = Get-ChildItem -LiteralPath $ProjectRoot -Recurse -Directory -Filter "__pycache__" -Force -ErrorAction SilentlyContinue
$cacheFiles = Get-ChildItem -LiteralPath $ProjectRoot -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in @(".pyc", ".pyo") }

foreach ($directory in $cacheDirs) {
    $resolved = $directory.FullName
    if (-not $resolved.StartsWith($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Recusando remover caminho fora do projeto: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

foreach ($file in $cacheFiles) {
    $resolved = $file.FullName
    if (-not $resolved.StartsWith($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Recusando remover caminho fora do projeto: $resolved"
    }
    if (Test-Path -LiteralPath $resolved) {
        Remove-Item -LiteralPath $resolved -Force
    }
}

Write-Host "PYTHON_CACHE_CLEAN: dirs=$($cacheDirs.Count) files=$($cacheFiles.Count)"
