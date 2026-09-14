param(
    [Parameter(Mandatory=$true)][ValidateSet("Claude","Codex","Both")][string]$Actor,
    [int]$Minutes = 180
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$current = Join-Path $repo ".amr-orchestrator\current"
New-Item -ItemType Directory -Force -Path $current | Out-Null
$enc = New-Object System.Text.UTF8Encoding($false)
$text = @{
    actor = $Actor
    granted_utc = [DateTime]::UtcNow.ToString("o")
    expires_utc = [DateTime]::UtcNow.AddMinutes($Minutes).ToString("o")
    granted_by = "user-command"
} | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText((Join-Path $current "DIRECT_MODE.json"), $text, $enc)
Write-Host "Direct mode enabled for $Actor for up to $Minutes minutes."
Write-Host "Protected governance, secrets, destructive git and real-money exchange actions remain blocked."
