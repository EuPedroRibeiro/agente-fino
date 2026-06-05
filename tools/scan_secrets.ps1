$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SelfPath = $MyInvocation.MyCommand.Path
$AllowedExtensions = @(
    ".py", ".ps1", ".js", ".css", ".html", ".md", ".txt", ".json",
    ".jsonl", ".toml", ".ini", ".cfg", ".conf", ".yml", ".yaml", ".env"
)
$ExcludedParts = @(
    "\.git\", "\__pycache__\", "\backup_", "\tools\mcp-brasil\",
    "\tools\DarkForest-Hunter-OpenAI\", "\data\logs\", "\data\security\"
)
$Findings = New-Object System.Collections.Generic.List[object]
$RawPasswordMarker = "0802" + "2004"

function Add-Finding([string]$Path, [int]$Line, [string]$Kind) {
    $Findings.Add([pscustomobject]@{ Path = $Path; Line = $Line; Kind = $Kind })
}

$files = Get-ChildItem -LiteralPath $ProjectRoot -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object {
        $_.FullName -ne $SelfPath -and
        ($AllowedExtensions -contains $_.Extension.ToLowerInvariant() -or $_.Name -like ".env*") -and
        -not (($ExcludedParts | Where-Object { $_.FullName -like "*$_*" }).Count)
    }

foreach ($file in $files) {
    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $file.FullName -ErrorAction SilentlyContinue) {
        $lineNumber++
        $trimmed = $line.Trim()
        if ($trimmed -match "^\s*#" -or $trimmed -match "^\s*$") { continue }
        if ($file.FullName -like "*\tests\*") { continue }

        if ($trimmed -match [regex]::Escape($RawPasswordMarker)) {
            Add-Finding $file.FullName $lineNumber "raw_password_marker"
        }
        if ($trimmed -match "(sk-proj-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{24,}|AIza[A-Za-z0-9_-]{20,})") {
            Add-Finding $file.FullName $lineNumber "probable_api_key"
        }
        if ($file.Name -like ".env*" -and $trimmed -match "(?i)^(OPENAI_API_KEY|GEMINI_API_KEY|DATABASE_URL|password|senha|token)\s*=\s*['`"]?([^'`"\s#]{8,})") {
            $value = $Matches[2]
            if ($value -notmatch "^(SUA_|YOUR_|CHANGE_|REPLACE_|EXAMPLE|fake|dummy|test|postgresql://user:password@)") {
                Add-Finding $file.FullName $lineNumber "nonempty_sensitive_assignment"
            }
        }
        if ($trimmed -match "(?i)(Authorization\s*:\s*Bearer\s+[A-Za-z0-9._-]{16,}|postgresql://[^:\s]+:[^@\s]+@)") {
            if ($trimmed -notmatch "(example|placeholder|user:password)") {
                Add-Finding $file.FullName $lineNumber "probable_credential"
            }
        }
    }
}

if ($Findings.Count -gt 0) {
    Write-Host "SECRET_SCAN_FAILED: $($Findings.Count) probable finding(s)"
    $Findings | Format-Table -AutoSize
    exit 1
}

Write-Host "SECRET_SCAN_OK: no probable real secrets found"
