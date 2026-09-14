param(
    [Parameter(Mandatory=$true)][string]$MissionFile,
    [ValidateSet("Claude","Codex")][string]$FrontEnd,
    [ValidateSet("Standard","Deep")][string]$Tier = "Standard",
    [ValidateSet("Offline","Demo")][string]$ExecutionMode = "Offline"
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$mission = (Resolve-Path $MissionFile).Path

function Write-Utf8NoBom([string]$Path, [string]$Text) {
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $enc)
}

if (-not (Get-Command opencode -ErrorAction SilentlyContinue)) {
    throw "OpenCode CLI not found."
}

$missionText = Get-Content -Raw $mission
if ($ExecutionMode -eq "Demo" -and $missionText -notmatch '(?m)^\s*Demo authorization:\s*YES\s*$') {
    throw "Demo mode requires the exact mission line: Demo authorization: YES"
}

$live = Join-Path $repo ".amr-orchestrator\models\LIVE_MODELS.md"
$refresh = $true
if (Test-Path $live) {
    $age = (Get-Date) - (Get-Item $live).LastWriteTime
    if ($age.TotalHours -lt 24) { $refresh = $false }
}
if ($refresh) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "refresh-models.ps1") -Quiet
}

$runId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ") + "-" + ([guid]::NewGuid().ToString("N").Substring(0,8))
$runDir = Join-Path $repo ".amr-orchestrator\runs\$runId"
$currentDir = Join-Path $repo ".amr-orchestrator\current"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
New-Item -ItemType Directory -Force -Path $currentDir | Out-Null

Write-Utf8NoBom (Join-Path $currentDir "RUN.json") (@{
    run_id = $runId
    run_dir = ".amr-orchestrator/runs/$runId"
    started_utc = [DateTime]::UtcNow.ToString("o")
    front_end = $FrontEnd
    tier = $Tier
    execution_mode = $ExecutionMode
} | ConvertTo-Json -Depth 6)

Write-Utf8NoBom (Join-Path $runDir "PROGRESS.json") (@{
    run_id = $runId
    status = "starting"
    current_work_package = ""
    active_role = "supervisor"
    active_model = ""
    completed_work_packages = @()
    current_action = "Starting delegated run"
    material_model_invocations = 0
    updated_at_utc = [DateTime]::UtcNow.ToString("o")
} | ConvertTo-Json -Depth 6)

Copy-Item -LiteralPath $mission -Destination (Join-Path $runDir "MISSION.md")
foreach ($name in @("VISUAL_CONTRACT.md","ARCHITECT_DECISION.md")) {
    $p = Join-Path $currentDir $name
    if (Test-Path $p) { Copy-Item -LiteralPath $p -Destination (Join-Path $runDir $name) }
}

Push-Location $repo
try {
    Write-Utf8NoBom (Join-Path $runDir "BASELINE_COMMIT.txt") ((git rev-parse HEAD) -join "`r`n")
    Write-Utf8NoBom (Join-Path $runDir "BASELINE_BRANCH.txt") ((git rev-parse --abbrev-ref HEAD) -join "`r`n")
    Write-Utf8NoBom (Join-Path $runDir "BASELINE_STATUS.txt") ((git status --porcelain=v1) -join "`r`n")
    Write-Utf8NoBom (Join-Path $runDir "BASELINE_DIFF.patch") ((git diff --) -join "`r`n")
} finally { Pop-Location }

$prev = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    $usage = @(& opencode stats --models 20 --project "" 2>&1)
    Write-Utf8NoBom (Join-Path $runDir "USAGE_BEFORE.txt") (($usage | ForEach-Object { "$_" }) -join "`r`n")
} finally { $ErrorActionPreference = $prev }

$agent = if ($Tier -eq "Deep") { "amr-supervisor-deep" } else { "amr-supervisor" }
$budgetMinutes = if ($Tier -eq "Deep") { 180 } else { 90 }
$budgetCalls = if ($Tier -eq "Deep") { 12 } else { 8 }

$launch = @"
RUN_ID: $runId
RUN_DIR: .amr-orchestrator/runs/$runId
FRONT_END: $FrontEnd
TIER: $Tier
EXECUTION_MODE: $ExecutionMode
TARGET_WALL_CLOCK_MINUTES: $budgetMinutes
TARGET_MATERIAL_MODEL_INVOCATIONS: $budgetCalls

Execute the attached mission under repository/orchestration policy.

Read:
- CLAUDE.md
- AGENTS.md
- .amr-orchestrator/policy/REPO_AUTHORITY.md
- .amr-orchestrator/policy/EXCHANGE_SAFETY.md
- .amr-orchestrator/policy/ROUTING_POLICY.md
- .amr-orchestrator/policy/BUDGET_POLICY.md
- .amr-orchestrator/policy/SUPERVISOR_REPORT_CONTRACT.md
- .amr-orchestrator/models/ROLE_MODEL_MAP.md
- .amr-orchestrator/models/LIVE_MODELS.md
- .amr-orchestrator/models/LIVE_MODELS_VERBOSE.txt

Respect package boundaries.
Use the normal low-cost model set only.
Update PROGRESS.json at material handoffs.
Do not exceed the mission budget to avoid escalation.
Offline means zero authenticated exchange mutation.
Real-money/mainnet mutation is never allowed.

Required final evidence:
- .amr-orchestrator/runs/$runId/SUPERVISOR_REPORT.json
- .amr-orchestrator/runs/$runId/SUPERVISOR_REPORT.md

If front-end help is required:
- .amr-orchestrator/runs/$runId/ESCALATION.json
"@

$launchPath = Join-Path $runDir "LAUNCH_PROMPT.txt"
Write-Utf8NoBom $launchPath $launch

$rawTranscript = Join-Path $runDir "SUPERVISOR_STDOUT_RAW.txt"
$cleanTranscript = Join-Path $runDir "SUPERVISOR_STDOUT.txt"

$args = @(
    "run",$launch,
    "--agent",$agent,
    "--auto",
    "--dir",$repo,
    "--title","amr-$runId",
    "--file",$launchPath,
    "--file",(Join-Path $runDir "MISSION.md")
)

foreach ($name in @("VISUAL_CONTRACT.md","ARCHITECT_DECISION.md")) {
    $p = Join-Path $runDir $name
    if (Test-Path $p) { $args += @("--file",$p) }
}

Push-Location $repo
$prev = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    & opencode @args 2>&1 |
        Tee-Object -FilePath $rawTranscript |
        ForEach-Object { Write-Host "$_" }
    $ocExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $prev
    Write-Utf8NoBom (Join-Path $runDir "FINAL_STATUS.txt") ((git status --porcelain=v1) -join "`r`n")
    Write-Utf8NoBom (Join-Path $runDir "FINAL_DIFF.patch") ((git diff --) -join "`r`n")
    Pop-Location
}

if (Test-Path $rawTranscript) {
    $rawText = [System.IO.File]::ReadAllText($rawTranscript)
    $cleanText = [regex]::Replace($rawText, ([char]27).ToString() + '\[[0-?]*[ -/]*[@-~]', '')
    Write-Utf8NoBom $cleanTranscript $cleanText
} else {
    Write-Utf8NoBom $rawTranscript ""
    Write-Utf8NoBom $cleanTranscript ""
}

$prev = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    $usage = @(& opencode stats --models 20 --project "" 2>&1)
    Write-Utf8NoBom (Join-Path $runDir "USAGE_AFTER.txt") (($usage | ForEach-Object { "$_" }) -join "`r`n")
} finally { $ErrorActionPreference = $prev }

if ($ocExit -ne 0) {
    Write-Error "OpenCode exited with code $ocExit. Evidence: $runDir"
    exit $ocExit
}

$report = Join-Path $runDir "SUPERVISOR_REPORT.json"
$reportMd = Join-Path $runDir "SUPERVISOR_REPORT.md"
if (-not (Test-Path $report) -or -not (Test-Path $reportMd)) {
    Write-Error "Supervisor did not produce both required report files."
    exit 20
}

$py = "python"
foreach ($candidate in @(
    (Join-Path $repo ".venv\Scripts\python.exe"),
    (Join-Path $repo "crypto_strategy_engine\crypto_strategy_engine\.venv\Scripts\python.exe"),
    (Join-Path $repo "crypto_market_intel\crypto_market_intel\.venv\Scripts\python.exe"),
    (Join-Path $repo "crypto_risk_execution_snapshot\crypto_risk_execution\.venv\Scripts\python.exe")
)) {
    if (Test-Path $candidate) { $py = $candidate; break }
}

& $py (Join-Path $PSScriptRoot "validate-report.py") $report (Join-Path $repo ".amr-orchestrator\policy\supervisor-report.schema.json")
if ($LASTEXITCODE -ne 0) {
    Write-Error "Supervisor report failed validation."
    exit 21
}

$r = Get-Content -Raw $report | ConvertFrom-Json
Write-Utf8NoBom (Join-Path $currentDir "FRONTEND_READ_THIS.md") @"
# Front-end review pointer

Run: $runId
Front-end: $FrontEnd
Report: .amr-orchestrator/runs/$runId/SUPERVISOR_REPORT.md
JSON: .amr-orchestrator/runs/$runId/SUPERVISOR_REPORT.json
Diff: .amr-orchestrator/runs/$runId/FINAL_DIFF.patch
Progress: .amr-orchestrator/runs/$runId/PROGRESS.json
Verdict: $($r.final_verdict)
"@

if ($r.final_verdict -eq "ESCALATE_TO_FRONTEND") {
    if (-not (Test-Path (Join-Path $runDir "ESCALATION.json"))) {
        Write-Error "Escalation verdict without ESCALATION.json."
        exit 22
    }
    Write-Host "ESCALATE_TO_FRONTEND - see $runDir"
    exit 10
}

Write-Host "Delegated run complete. Review: $runDir"
exit 0
