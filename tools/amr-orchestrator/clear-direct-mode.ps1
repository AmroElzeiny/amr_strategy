$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$p = Join-Path $repo ".amr-orchestrator\current\DIRECT_MODE.json"
if (Test-Path $p) { Remove-Item -LiteralPath $p -Force }
Write-Host "Direct mode cleared."
