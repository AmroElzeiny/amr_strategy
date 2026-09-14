$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$path = Join-Path $repo ".codex\hooks.json"

if (-not (Test-Path $path)) {
    throw "Codex hooks file not found: $path"
}

$backup = $path + ".bak-before-utf8-repair"
Copy-Item -LiteralPath $path -Destination $backup -Force

$text = [System.IO.File]::ReadAllText($path)
try {
    $null = $text | ConvertFrom-Json
} catch {
    throw "hooks.json is invalid JSON before encoding repair: $($_.Exception.Message)"
}

$enc = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $text, $enc)

$bytes = [System.IO.File]::ReadAllBytes($path)
$hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
if ($hasBom) { throw "UTF-8 BOM remains after repair." }

Write-Host "Codex hooks repaired: valid UTF-8 without BOM."
Write-Host "Backup: $backup"
