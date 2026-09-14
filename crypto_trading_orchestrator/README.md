# Crypto Trading Orchestrator

`crypto-trading-orchestrator` 1.0.0 is the runtime coordinator for the four-package
`HM_CRYPTO_V1` system. It connects Package 1 market intelligence to Package 2 strategy and
Package 3 risk/execution without copying their business logic. Package 3 remains a development
snapshot; the default configuration is Bybit Demo, dry-run, with orchestrator execution disabled.

## Authority boundaries

- `crypto_market_intel` discovers, ranks, monitors, and produces `MarketSnapshot`.
- `crypto_strategy_engine` consumes snapshots and produces immutable `TradeIntent` values.
- `crypto_risk_execution` alone validates capital, sizes, locks, reconciles, and may execute.
- `crypto_trading_orchestrator` owns startup order, event priority, resource limits, health,
  lineage, persistence, recovery, feedback routing, and shutdown coordination.

`ENTER` is only permission to ask Package 3. The orchestrator never changes quantity, leverage,
stop, targets, or a rejection. It imports no private exchange transport and calls no AI provider.

## Installation

Use Python 3.11 or newer in a fresh virtual environment. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .\crypto_market_intel\crypto_market_intel
python -m pip install .\crypto_strategy_engine\crypto_strategy_engine
python -m pip install .\crypto_risk_execution_snapshot\crypto_risk_execution
python -m pip install .\crypto_trading_orchestrator
```

Package versions are pinned to market `1.0.0`, strategy `1.0.0`, risk `0.3.0.dev0`, and
orchestrator `1.0.0`. Manual source copying is unsupported.

## Configuration

Copy `.env.example` to a master orchestration environment file and keep secrets out of it.
Exchange credentials must be supplied directly to Package 3 through the process environment or
its normal secret mechanism. The orchestrator refuses secret-looking keys in `--env-file`.

Safe validation:

```powershell
python -m crypto_trading_orchestrator --env-file .env doctor
python -m crypto_trading_orchestrator --env-file .env validate
```

Dry-run startup still requires a successful read-only account reconciliation:

```powershell
$env:ORCHESTRATOR_EXECUTION_ENABLED="true"
$env:EXECUTION_ENABLED="true"
$env:DRY_RUN="true"
python -m crypto_trading_orchestrator start --once
```

With `ORCHESTRATOR_EXECUTION_ENABLED=false` no `ENTER` reaches Package 3 execution. With
`DRY_RUN=true`, Package 3 produces an execution plan/report but submits zero orders. Real mode
requires both orchestrator and Package 3 real-trading guards, including Package 3's explicit
acknowledgement. Testnet is rejected and Binance Demo fails closed.

## CLI

```text
start [--once] [--scan-interval SECONDS]
status
health
validate
doctor
reconcile
scan-once
evaluate-once SYMBOL
walkforward RECORDS.json [--output-dir DIR]
shutdown
```

`shutdown` writes a durable stop request; SIGINT/SIGTERM is the immediate process signal.
`doctor` is offline-safe: it validates imports, exact versions, schema/build hashes, environment,
database path, and writable storage without private exchange calls or order submission.

## Runtime guarantees

Startup is fail-closed: config → discovery → contracts → environment → Package 3 reconciliation
→ market/scanner → `READY`/`RUNNING`. Critical risk/execution/protection events use an unbounded
priority lane. Market events are bounded and latest-per-symbol snapshots coalesce. Evaluation is
serialized per symbol and Package 3 entry calls are globally serialized. Snapshot/intent TTL,
integrity, environment, instrument, lineage, and durable signal idempotency are checked before
execution routing.

States are `HEALTHY`, `DEGRADED`, `BLOCK_NEW_ENTRIES`, and `EMERGENCY`. Market or strategy failure
blocks new entries by default while Package 3 management remains available. Risk failure always
fails closed. SQLite WAL state recovers watches, signals, lineage, events, quarantine records, and
duplicate guards. Each clean shutdown emits a JSON session audit in `AUDIT_DIR`.

## Testing

```powershell
pytest crypto_market_intel/crypto_market_intel/tests
pytest crypto_strategy_engine/crypto_strategy_engine/tests
pytest crypto_risk_execution_snapshot/crypto_risk_execution/tests
pytest crypto_trading_orchestrator/tests
cd crypto_trading_orchestrator
python -m ruff check .
python -m ruff format --check .
python -m mypy src/crypto_trading_orchestrator
```

Network-free E2E tests use the real Package 1/2/3 public contracts and a deterministic offline
exchange. Optional Bybit Demo smoke remains opt-in and order submission remains separately gated.
See `BUILD_REPORT.md` for the exact verified results and limitations.
