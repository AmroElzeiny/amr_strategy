param([switch]$RequireBoth)

$ErrorActionPreference = "Continue"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$coreOk = $true
$claudeOk = $true
$codexOk = $true

function Mark([string]$group, [string]$name, [bool]$cond, [string]$detail="") {
    if ($cond) { Write-Host "[PASS][$group] $name $detail" }
    else {
        Write-Host "[FAIL][$group] $name $detail"
        if ($group -eq "CORE") { $script:coreOk = $false }
        elseif ($group -eq "CLAUDE") { $script:claudeOk = $false }
        elseif ($group -eq "CODEX") { $script:codexOk = $false }
    }
}

function Is-Ascii([string]$Path) {
    try {
        foreach ($b in [IO.File]::ReadAllBytes($Path)) { if ($b -gt 127) { return $false } }
        return $true
    } catch { return $false }
}

function Parses-Ps([string]$Path) {
    try {
        $tokens=$null; $errors=$null
        [Management.Automation.Language.Parser]::ParseFile($Path,[ref]$tokens,[ref]$errors) | Out-Null
        return (@($errors).Count -eq 0)
    } catch { return $false }
}

function Has-Utf8Bom([string]$Path) {
    try {
        $b = [IO.File]::ReadAllBytes($Path)
        return ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF)
    } catch { return $false }
}

Mark "CORE" "Git repository" (Test-Path (Join-Path $repo ".git"))
Mark "CORE" "OpenCode CLI" ([bool](Get-Command opencode -ErrorAction SilentlyContinue))
Mark "CLAUDE" "Claude CLI" ([bool](Get-Command claude -ErrorAction SilentlyContinue))
Mark "CODEX" "Codex CLI" ([bool](Get-Command codex -ErrorAction SilentlyContinue))

foreach ($path in @(
    "crypto_market_intel\crypto_market_intel\pyproject.toml",
    "crypto_strategy_engine\crypto_strategy_engine\pyproject.toml",
    "crypto_risk_execution_snapshot\crypto_risk_execution\pyproject.toml",
    "crypto_risk_execution_snapshot\crypto_risk_execution\SNAPSHOT_STATUS.md"
)) {
    Mark "CORE" "Repository authority file $path" (Test-Path (Join-Path $repo $path))
}

Mark "CORE" "Standard supervisor" (Test-Path (Join-Path $repo ".opencode\agents\amr-supervisor.md"))
Mark "CORE" "Deep supervisor" (Test-Path (Join-Path $repo ".opencode\agents\amr-supervisor-deep.md"))
Mark "CORE" "Routing policy" (Test-Path (Join-Path $repo ".amr-orchestrator\policy\ROUTING_POLICY.md"))
Mark "CORE" "Repo authority policy" (Test-Path (Join-Path $repo ".amr-orchestrator\policy\REPO_AUTHORITY.md"))
Mark "CORE" "Exchange safety policy" (Test-Path (Join-Path $repo ".amr-orchestrator\policy\EXCHANGE_SAFETY.md"))

$psFiles = @()
foreach ($d in @(
    (Join-Path $repo "tools\amr-orchestrator"),
    (Join-Path $repo ".claude\hooks"),
    (Join-Path $repo ".codex\hooks")
)) {
    if (Test-Path $d) { $psFiles += Get-ChildItem -Path $d -Filter "*.ps1" -File }
}
$badAscii=@(); $badParse=@()
foreach ($f in $psFiles) {
    if (-not (Is-Ascii $f.FullName)) { $badAscii += $f.Name }
    if (-not (Parses-Ps $f.FullName)) { $badParse += $f.Name }
}
Mark "CORE" "PowerShell source is PS5.1 ASCII-safe" ($badAscii.Count -eq 0) "($($psFiles.Count) files)"
Mark "CORE" "PowerShell scripts parse" ($badParse.Count -eq 0) "($($psFiles.Count) files)"

if (Get-Command opencode -ErrorAction SilentlyContinue) {
    $prev=$ErrorActionPreference
    try {
        $ErrorActionPreference="Continue"
        $go=@(& opencode models opencode-go 2>&1 | Where-Object { "$_" -match '^opencode-go/' } | ForEach-Object { "$_".Trim() })
    } finally { $ErrorActionPreference=$prev }

    Mark "CORE" "OpenCode Go model catalog visible" ($go.Count -gt 0) "($($go.Count) models)"
    foreach ($m in @(
        "opencode-go/minimax-m3",
        "opencode-go/qwen3.8-flash",
        "opencode-go/deepseek-v4.1-flash",
        "opencode-go/deepseek-v4-flash-vision-exp"
    )) {
        Mark "CORE" "Normal model $m" ($go -contains $m)
    }
}

$badModels=@()
$agentDir=Join-Path $repo ".opencode\agents"
if (Test-Path $agentDir) {
    foreach ($f in Get-ChildItem $agentDir -Filter "amr-*.md" -File) {
        $s=[IO.File]::ReadAllText($f.FullName)
        if ($s -match '(?i)model:\s*opencode-go/(kimi-k2\.7-code|deepseek-v4-pro|qwen3\.8-max|glm-5\.3)$') {
            $badModels += $f.Name
        }
    }
}
Mark "CORE" "No expensive default agent models" ($badModels.Count -eq 0)

$settings=Join-Path $repo ".claude\settings.local.json"
if (Test-Path $settings) {
    try {
        $j=Get-Content -Raw $settings | ConvertFrom-Json
        $t=$j.hooks.PreToolUse | ConvertTo-Json -Depth 12
        Mark "CLAUDE" "Edit/Write gate registered" ($t -match "amr-delegation-gate")
        Mark "CLAUDE" "Shell gate registered" ($t -match "amr-shell-gate")
    } catch {
        Mark "CLAUDE" "settings.local.json parses" $false
    }
} else {
    Mark "CLAUDE" "settings.local.json exists" $false
}

$hooks=Join-Path $repo ".codex\hooks.json"
if (Test-Path $hooks) {
    Mark "CODEX" "hooks.json has no UTF-8 BOM" (-not (Has-Utf8Bom $hooks))
    try {
        $j=Get-Content -Raw $hooks | ConvertFrom-Json
        $t=$j.hooks.PreToolUse | ConvertTo-Json -Depth 12
        Mark "CODEX" "hooks.json valid JSON" $true
        Mark "CODEX" "Edit/apply_patch gate registered" ($t -match "amr-delegation-gate")
        Mark "CODEX" "Shell gate registered" ($t -match "amr-shell-gate")
    } catch {
        Mark "CODEX" "hooks.json valid JSON" $false
    }
} else {
    Mark "CODEX" "hooks.json exists" $false
}

# Global MCPs, including node_repl, are intentionally not part of readiness.

Write-Host ""
if ($coreOk) { Write-Host "OPENCODE WORKFORCE READY" } else { Write-Host "OPENCODE WORKFORCE NOT READY" }
if ($claudeOk) { Write-Host "CLAUDE FRONT-END READY" } else { Write-Host "CLAUDE FRONT-END NOT READY" }
if ($codexOk) { Write-Host "CODEX FRONT-END READY" } else { Write-Host "CODEX FRONT-END NOT READY" }

if ($coreOk -and $claudeOk -and $codexOk) {
    Write-Host "SYSTEM READY FOR BOTH"
    exit 0
}
if ($RequireBoth) {
    Write-Host "SYSTEM NOT READY FOR BOTH"
    exit 1
}
if ($coreOk -and ($claudeOk -or $codexOk)) {
    Write-Host "SYSTEM READY FOR AT LEAST ONE FRONT-END"
    exit 0
}
Write-Host "SYSTEM NOT READY"
exit 1
