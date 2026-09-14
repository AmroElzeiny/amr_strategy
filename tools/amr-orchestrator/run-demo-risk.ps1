param(
    [Parameter(Mandatory=$true)][string]$IntentFile
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$pkg = Join-Path $repo "crypto_risk_execution_snapshot\crypto_risk_execution"
$intent = (Resolve-Path $IntentFile).Path

if (-not (Test-Path (Join-Path $pkg "pyproject.toml"))) {
    throw "Risk/execution package not found."
}

# Force safe routing values for this child process.
$env:TRADING_ENV = "DEMO"
$env:EXECUTION_ENABLED = "true"
$env:DRY_RUN = "false"
$env:REAL_TRADING_ENABLED = "false"
$env:DEMO_TRADING_ENABLED = "true"
$env:BYBIT_DEMO_REST_BASE = "https://api-demo.bybit.com"

if ($env:BYBIT_REAL_REST_BASE -and $env:BYBIT_DEMO_REST_BASE -eq $env:BYBIT_REAL_REST_BASE) {
    throw "Demo and real REST bases must not be equal."
}

Push-Location $pkg
try {
    $py = Join-Path $pkg ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) { $py = "python" }
    & $py -m crypto_risk_execution execute $intent
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
