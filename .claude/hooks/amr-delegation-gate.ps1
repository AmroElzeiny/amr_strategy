$ErrorActionPreference = "Stop"
$raw = [Console]::In.ReadToEnd()
try { $evt = $raw | ConvertFrom-Json } catch { exit 0 }

$actor = "Claude"
$repo = if ($evt.cwd) { [string]$evt.cwd } elseif ($env:CLAUDE_PROJECT_DIR) { $env:CLAUDE_PROJECT_DIR } else { (Get-Location).Path }
try { $repo = [System.IO.Path]::GetFullPath($repo) } catch { exit 0 }

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

function Read-Marker([string]$Name) {
    $p = Join-Path $repo ".amr-orchestrator\current\$Name"
    if (-not (Test-Path $p)) { return $null }
    try {
        $j = Get-Content -Raw -LiteralPath $p | ConvertFrom-Json
        $expires = [DateTime]::Parse([string]$j.expires_utc).ToUniversalTime()
        if ([DateTime]::UtcNow -gt $expires) { return $null }
        if (($j.actor -eq $actor) -or ($j.actor -eq "Both")) { return $j }
    } catch {}
    return $null
}

function Normalize-Rel([string]$path) {
    if (-not $path) { return $null }
    try {
        $full = if ([System.IO.Path]::IsPathRooted($path)) {
            [System.IO.Path]::GetFullPath($path)
        } else {
            [System.IO.Path]::GetFullPath((Join-Path $repo $path))
        }
        if (-not $full.StartsWith($repo, [System.StringComparison]::OrdinalIgnoreCase)) {
            return "__OUTSIDE__"
        }
        return $full.Substring($repo.Length).TrimStart('\','/')
    } catch { return $null }
}

function Extract-Paths {
    $paths = @()
    foreach ($k in @("file_path","path","filename")) {
        if ($evt.tool_input.$k) { $paths += [string]$evt.tool_input.$k }
    }
    $patch = $null
    foreach ($k in @("patch","input","diff")) {
        if ($evt.tool_input.$k) { $patch = [string]$evt.tool_input.$k; break }
    }
    if ($patch) {
        foreach ($m in [regex]::Matches($patch, '(?m)^\*\*\*\s+(?:Update|Add|Delete)\s+File:\s+(.+?)\s*$')) {
            $paths += $m.Groups[1].Value.Trim()
        }
        foreach ($m in [regex]::Matches($patch, '(?m)^\+\+\+\s+b/(.+?)\s*$')) {
            $paths += $m.Groups[1].Value.Trim()
        }
    }
    return @($paths | Where-Object { $_ } | Select-Object -Unique)
}

$toolName = [string]$evt.tool_name
if ($toolName -notmatch '^(Edit|Write|apply_patch)$') { exit 0 }

$paths = @(Extract-Paths)
$direct = Read-Marker "DIRECT_MODE.json"
$takeover = Read-Marker "TAKEOVER.json"

if ($paths.Count -eq 0) {
    if ($direct) { exit 0 }
    Deny "$actor delegation gate: target file scope cannot be proven."
}

$architectAllowed = @(
    ".amr-orchestrator\current\MISSION.md",
    ".amr-orchestrator\current\VISUAL_CONTRACT.md",
    ".amr-orchestrator\current\ARCHITECT_DECISION.md"
)

$protected = @(
    "CLAUDE.md",
    "AGENTS.md",
    ".claude\*",
    ".codex\*",
    ".opencode\*",
    ".amr-orchestrator\policy\*",
    ".amr-orchestrator\models\*",
    "tools\amr-orchestrator\*",
    ".env",
    ".env.*",
    "*\.env",
    "*\.env.*"
)

foreach ($rawPath in $paths) {
    $rel = Normalize-Rel $rawPath
    if ($rel -eq "__OUTSIDE__") { Deny "$actor delegation gate: writing outside repository is blocked." }
    if (-not $rel) { Deny "$actor delegation gate: target path cannot be normalized." }

    foreach ($pat in $protected) {
        if ($rel -like $pat) { Deny "$actor delegation gate: protected file '$rel' cannot be edited by this mode." }
    }

    $architect = $false
    foreach ($a in $architectAllowed) {
        if ($rel -ieq $a) { $architect = $true; break }
    }
    if ($architect) { continue }

    if ($direct) { continue }

    if ($takeover) {
        $ok = $false
        foreach ($pat in @($takeover.allowed_files)) {
            $n = ([string]$pat -replace '/', '\')
            if ($rel -like $n) { $ok = $true; break }
        }
        if ($ok) { continue }
    }

    Deny "$actor delegation gate: product edits belong to OpenCode Go unless user-started Direct mode or a valid takeover is active."
}

exit 0
