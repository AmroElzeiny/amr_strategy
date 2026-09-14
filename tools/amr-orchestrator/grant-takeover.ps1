param(
    [Parameter(Mandatory=$true)][ValidateSet("Claude","Codex","Both")][string]$Actor,
    [int]$Minutes = 120
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$currentRun = Join-Path $repo ".amr-orchestrator\current\RUN.json"
if (-not (Test-Path $currentRun)) { throw "No current delegated run." }

$run = Get-Content -Raw $currentRun | ConvertFrom-Json
$runDir = Join-Path $repo ($run.run_dir -replace '/', '\')
$esc = Join-Path $runDir "ESCALATION.json"
if (-not (Test-Path $esc)) { throw "No ESCALATION.json." }

$j = Get-Content -Raw $esc | ConvertFrom-Json
if ($j.status -ne "ESCALATE_TO_FRONTEND") { throw "Invalid escalation status." }
if ($j.run_id -ne $run.run_id) { throw "Run ID mismatch." }
if (-not $j.needs_frontend_implementation) { throw "Escalation does not authorize implementation." }

$allowed = @($j.allowed_files)
if ($allowed.Count -eq 0) { throw "No files authorized." }

$protected = @(
    "CLAUDE.md","AGENTS.md",".claude\*",".codex\*",".opencode\*",
    ".amr-orchestrator\*","tools\amr-orchestrator\*",".env",".env.*","*\.env","*\.env.*"
)
foreach ($file in $allowed) {
    $f = ([string]$file -replace '/', '\')
    foreach ($pat in $protected) {
        if ($f -like $pat) { throw "Protected file cannot be unlocked: $file" }
    }
}

$enc = New-Object System.Text.UTF8Encoding($false)
$text = @{
    actor = $Actor
    run_id = $run.run_id
    granted_utc = [DateTime]::UtcNow.ToString("o")
    expires_utc = [DateTime]::UtcNow.AddMinutes($Minutes).ToString("o")
    allowed_files = $allowed
} | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText((Join-Path $repo ".amr-orchestrator\current\TAKEOVER.json"), $text, $enc)

Write-Host "Takeover granted to $Actor."
$allowed | ForEach-Object { Write-Host "  $_" }
