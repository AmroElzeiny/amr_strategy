param(
    [string]$RunId = "",
    [int]$IntervalSeconds = 3,
    [switch]$Once
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if ($RunId) {
    $runDir = Join-Path $repo ".amr-orchestrator\runs\$RunId"
} else {
    $current = Join-Path $repo ".amr-orchestrator\current\RUN.json"
    if (-not (Test-Path $current)) { throw "No current run." }
    $j = Get-Content -Raw $current | ConvertFrom-Json
    $runDir = Join-Path $repo ($j.run_dir -replace '/', '\')
}

do {
    Clear-Host
    Write-Host "amr_strategy dual orchestrator monitor"
    Write-Host "Run: $runDir"
    Write-Host ""

    $progress = Join-Path $runDir "PROGRESS.json"
    if (Test-Path $progress) {
        try {
            $p = Get-Content -Raw $progress | ConvertFrom-Json
            Write-Host "Status:       $($p.status)"
            Write-Host "Package:      $($p.current_work_package)"
            Write-Host "Role:         $($p.active_role)"
            Write-Host "Model:        $($p.active_model)"
            Write-Host "Action:       $($p.current_action)"
            Write-Host "Calls:        $($p.material_model_invocations)"
            Write-Host "Updated UTC:  $($p.updated_at_utc)"
            Write-Host "Completed:    $(@($p.completed_work_packages) -join ', ')"
        } catch {
            Write-Host "PROGRESS.json currently incomplete."
        }
    }

    Write-Host ""
    Write-Host "Recent artifacts:"
    Get-ChildItem -LiteralPath $runDir -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 12 LastWriteTime, Length, Name |
        Format-Table -AutoSize

    $raw = Join-Path $runDir "SUPERVISOR_STDOUT_RAW.txt"
    if (Test-Path $raw) {
        Write-Host ""
        Write-Host "Latest transcript lines:"
        Get-Content -LiteralPath $raw -Tail 8
    }

    if (-not $Once) {
        Write-Host ""
        Write-Host "Ctrl+C to stop."
        Start-Sleep -Seconds $IntervalSeconds
    }
} while (-not $Once)
