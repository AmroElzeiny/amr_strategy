param([switch]$Quiet)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$outDir = Join-Path $repo ".amr-orchestrator\models"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function Write-Utf8NoBom([string]$Path, [string]$Text) {
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $enc)
}

if (-not (Get-Command opencode -ErrorAction SilentlyContinue)) {
    throw "OpenCode CLI not found."
}

$prev = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    & opencode models --refresh 2>&1 | Out-Null
    $verbose = @(& opencode models opencode-go --verbose 2>&1)
    $ids = @(& opencode models opencode-go 2>&1)
} finally {
    $ErrorActionPreference = $prev
}

Write-Utf8NoBom (Join-Path $outDir "LIVE_MODELS_VERBOSE.txt") (($verbose | ForEach-Object { "$_" }) -join "`r`n")
Write-Utf8NoBom (Join-Path $outDir "LIVE_MODEL_IDS.txt") (($ids | ForEach-Object { "$_" }) -join "`r`n")

$liveIds = @(
    $ids |
    Where-Object { "$_" -match '^opencode-go/' } |
    ForEach-Object { "$_".Trim() } |
    Sort-Object -Unique
)

$md = @("# Live OpenCode Go model snapshot", "", "Generated UTC: $([DateTime]::UtcNow.ToString('o'))", "", "Local OpenCode CLI is authority.", "")
foreach ($m in $liveIds) { $md += "- ``$m``" }
Write-Utf8NoBom (Join-Path $outDir "LIVE_MODELS.md") ($md -join "`r`n")

if (-not $Quiet) { Write-Host "Refreshed $($liveIds.Count) OpenCode Go models." }
