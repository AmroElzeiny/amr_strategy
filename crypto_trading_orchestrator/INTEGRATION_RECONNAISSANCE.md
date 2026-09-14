# Integration Reconnaissance

Inspected artifacts: the three supplied source packages and ZIPs, their package metadata, public
entry points, schemas, architecture/environment/status documents, tests, and fixtures.

| Role | Distribution | Verified version | Public integration surface |
|---|---|---:|---|
| Market | `crypto-market-intel` | 1.0.0 | `MarketIntelEngine.scan_cycle`, `deep_watch_symbols`, `build_deep_snapshot` |
| Strategy | `crypto-strategy-engine` | 1.0.0 | `validate_market_snapshot`, `evaluate_snapshot`, `ingest_execution_report`, `run_walkforward`, `get_champion_config` |
| Risk | `crypto-risk-execution` | 0.3.0.dev0 | `validate_trade_intent`, `risk_assess`, `execute_trade_intent`, `reconcile_account`, `manage_open_positions`, `emergency_flatten` |

The initial real probe found two blocking mismatches. Package 1 emits `levels` as an array and may
emit null `breakout_alert`/`derivatives`, while Package 2 previously required objects. Package 2
also emits first attempts as `attempt_no=0` and uses `entry_reference`/`trigger_price_if_any`, while
Package 3 previously required attempt 1+ and looked only for `expected_entry`/`price`. These were
resolved at the owning consumer boundaries after the user explicitly authorized cross-package
changes. Package 3's invalid non-PEP-440 snapshot version was normalized to `0.3.0.dev0`, and its
schema was added to wheel package data.

Package 3 remains a development snapshot with limited public position-management behavior. This
build therefore qualifies the deterministic offline/dry-run integration, not unattended real-money
execution. No private exchange mutation or live AI call was performed.
