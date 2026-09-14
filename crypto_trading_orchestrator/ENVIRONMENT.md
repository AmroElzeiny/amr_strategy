# Environment

The master keys and defaults are documented in `.env.example`. Precedence is: explicit process
environment, master file values loaded with `--env-file`, then package defaults. `setdefault` is
used so a file cannot overwrite an explicit process setting. Package environment-file paths are
validated for existence but Package 4 does not read secrets from them.

The default is `LIVE` orchestration against `BYBIT` `DEMO` `DERIVATIVES`, with execution disabled
and dry-run enabled. `RESEARCH` has zero execution authority. `TESTNET` is invalid. `BINANCE` Demo
is invalid because the integrated market package is Bybit-only; other unsupported combinations
fail closed during discovery or alignment checks.

For Demo planning, both `ORCHESTRATOR_EXECUTION_ENABLED=true` and Package 3
`EXECUTION_ENABLED=true` are needed; keep `DRY_RUN=true` to submit zero orders. Real execution is
outside automated verification and requires `TRADING_ENV=REAL`, both real-enable guards, Package
3's exact real acknowledgement, non-dry-run settings, valid account reconciliation, and operator
control. Never place credentials in the master orchestrator file or logs.

Data paths default to `./data`, with separate audit and quarantine directories. Use absolute paths
for service deployments. Ensure only the service identity can read Package 3 credentials and write
its state database.
