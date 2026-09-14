$ErrorActionPreference = "Stop"
$raw = [Console]::In.ReadToEnd()
try { $evt = $raw | ConvertFrom-Json } catch { exit 0 }

$actor = "Claude"
$cmd = ""
if ($evt.tool_input.command) { $cmd = [string]$evt.tool_input.command }
elseif ($evt.tool_input.cmd) { $cmd = [string]$evt.tool_input.cmd }
elseif ($evt.tool_input.script) { $cmd = [string]$evt.tool_input.script }
if (-not $cmd) { exit 0 }

function Deny([string]$reason) {
    @{
        hookSpecificOutput = @{
            hookEventName = "PreToolUse"
            permissionDecision = "deny"
            permissionDecisionReason = $reason
        }
    } | ConvertTo-Json -Depth 8 -Compress
    exit 0
}

if ($cmd -match '(?i)(start-direct|set-direct-mode)\.ps1') {
    Deny "$actor safety gate: Direct mode must be started by the user from a separate terminal."
}

$alwaysBlocked = @(
    '(?i)\bgit\s+push\b',
    '(?i)\bgit\s+commit\b',
    '(?i)\bgit\s+reset\s+--hard\b',
    '(?i)\bgit\s+clean\s+-[a-z]*f',
    '(?i)\bgit\s+rebase\b',
    '(?i)\bgit\s+merge\b',
    '(?i)\bgh\s+pr\s+(merge|create)\b',
    '(?i)\bREAL_TRADING_ENABLED\s*=\s*true\b',
    '(?i)\bEXECUTION_ENABLED\s*=\s*true\b.*\bTRADING_ENV\s*=\s*REAL\b',
    '(?i)api\.bybit\.com.*/v5/(order|position|account|asset|spot-margin-trade)',
    '(?i)api\.binance\.com.*/api/.*/order',
    '(?i)fapi\.binance\.com.*/fapi/.*/order',
    '(?i)\b(unlock-max-loss|flatten)\b'
)
foreach ($pat in $alwaysBlocked) {
    if ($cmd -match $pat) { Deny "$actor safety gate: command is blocked by repository trading/publishing safety." }
}

$approved = @(
    "tools\amr-orchestrator\delegate.ps1",
    "tools/amr-orchestrator/delegate.ps1",
    "tools\amr-orchestrator\refresh-models.ps1",
    "tools/amr-orchestrator/refresh-models.ps1",
    "tools\amr-orchestrator\verify-system.ps1",
    "tools/amr-orchestrator/verify-system.ps1",
    "tools\amr-orchestrator\watch-run.ps1",
    "tools/amr-orchestrator/watch-run.ps1",
    "tools\amr-orchestrator\run-model.ps1",
    "tools/amr-orchestrator/run-model.ps1",
    "tools\amr-orchestrator\grant-takeover.ps1",
    "tools/amr-orchestrator/grant-takeover.ps1",
    "tools\amr-orchestrator\revoke-takeover.ps1",
    "tools/amr-orchestrator/revoke-takeover.ps1",
    "tools\amr-orchestrator\run-demo-risk.ps1",
    "tools/amr-orchestrator/run-demo-risk.ps1"
)
foreach ($a in $approved) {
    if ($cmd -like "*$a*") { exit 0 }
}

$mutations = @(
    '(?i)\bSet-Content\b',
    '(?i)\bAdd-Content\b',
    '(?i)\bOut-File\b',
    '(?i)\bRemove-Item\b',
    '(?i)\bCopy-Item\b',
    '(?i)\bMove-Item\b',
    '(?i)\bRename-Item\b',
    '(?i)\bNew-Item\b',
    '(?i)(^|[;&|]\s*)rm(\s|$)',
    '(?i)(^|[;&|]\s*)del(\s|$)',
    '(?i)(^|[;&|]\s*)cp(\s|$)',
    '(?i)(^|[;&|]\s*)mv(\s|$)',
    '(?i)(^|[;&|]\s*)touch(\s|$)',
    '(?i)(^|[;&|]\s*)tee(\s|$)',
    '(?i)\bsed\s+-i\b',
    '(?i)\bperl\s+-pi\b',
    '(?i)\bgit\s+(apply|checkout|restore)\b',
    '(?i)\b(pip|pip3)\s+install\b',
    '(?i)\bpython\s+-m\s+pip\s+install\b',
    '(?i)\bwrite_text\s*\(',
    '(?i)\bwrite_bytes\s*\('
)
foreach ($pat in $mutations) {
    if ($cmd -match $pat) { Deny "$actor safety gate: shell mutation is blocked; use Edit/Write/apply_patch in Direct mode or delegate." }
}

$normalized = $cmd -replace '\d+>&\d+', ''
if ($normalized -match '(?<![<>=])>>?\s*["'']?[^&\s]') {
    Deny "$actor safety gate: shell file redirection is blocked."
}

exit 0
