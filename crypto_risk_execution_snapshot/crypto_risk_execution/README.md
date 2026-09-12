# crypto_risk_execution — snapshot

Standalone Python package implementing the Prompt-3 boundary: deterministic TradeIntent validation, integrity freeze, risk sizing, persistent loss locks, transactional risk reservations, Bybit/Binance REST adapters, reconciliation primitives, execution planning, audit state and ExecutionReport generation.

## Safety warnings

This code can send **REAL orders** if execution and real-trading switches are deliberately enabled. Keep withdrawal permission disabled, use an IP whitelist when operationally possible, and use a dedicated trading subaccount. Demo is not Testnet. Spot mode has no margin, borrowing or opening shorts. Derivatives can liquidate if configured incorrectly. Risk controls do not guarantee against loss, exchange outages, gaps or slippage. Real trading is disabled and dry-run is enabled by default.

## Status

This archive is an explicitly requested **development snapshot**, not the fully-qualified Prompt-3 release. See `BUILD_REPORT.md` and `SNAPSHOT_STATUS.md` before enabling execution.

## CLI

`python -m crypto_risk_execution validate intent.json`

`python -m crypto_risk_execution assess intent.json`

`python -m crypto_risk_execution execute intent.json`

`python -m crypto_risk_execution reconcile`

`python -m crypto_risk_execution status`

`python -m crypto_risk_execution risk-status`

`python -m crypto_risk_execution flatten --reason operator_emergency`

`python -m crypto_risk_execution unlock-max-loss --acknowledge I_ACKNOWLEDGE_MAX_LOSS_UNLOCK --reason ...`
