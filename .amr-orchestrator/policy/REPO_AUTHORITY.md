# Repository authority map

## Package 1 — crypto_market_intel

Path:
`crypto_market_intel/crypto_market_intel`

Authority:
- public Bybit market data;
- market structure;
- breakout scouting;
- orderbook/public-trade intelligence;
- `MarketSnapshot`.

Forbidden authority:
- trade approval;
- risk sizing;
- order placement;
- order management;
- position management.

Key local sources:
- `README.md`
- `ARCHITECTURE.md`
- `CONTRACT.md`
- `PATTERN_DEFINITIONS.md`
- `ALGORITHM_POLICY.md`
- `ENVIRONMENT.md`
- `REFERENCE_CONCEPT_MAP.md`
- `BUILD_REPORT.md`

Normal verification:
- `pytest -q`
- `python tools/lint_check.py`
- `python tools/type_contract_check.py`
- `python tools/dependency_boundary_check.py`
- `python tools/secret_scan.py`

Live public-data smoke is opt-in and order-free.

## Package 2 — crypto_strategy_engine

Path:
`crypto_strategy_engine/crypto_strategy_engine`

Authority:
- deterministic strategy candidate evaluation;
- setup family arbitration;
- optional evidence-bound AI advisory;
- thesis/entry/invalidation/target viability;
- `TradeIntent`.

Critical rule:
`decision=ENTER` is NOT an order instruction. It means forward the intent to the independent risk/execution layer.

Forbidden authority:
- exchange market/account client;
- sizing/leverage authority;
- placing/editing/canceling orders.

Key local sources:
- `README.md`
- `ARCHITECTURE.md`
- `CONTRACT.md`
- `ENVIRONMENT.md`
- `REFERENCE_CONCEPT_MAP.md`
- `LOOKAHEAD_AUDIT.md`
- `BUILD_REPORT.md`

Normal verification:
- `pytest`
- `ruff check src tests`
- `mypy src`

## Package 3 — crypto_risk_execution_snapshot

Path:
`crypto_risk_execution_snapshot/crypto_risk_execution`

Authority:
- TradeIntent validation;
- integrity freeze;
- risk sizing;
- daily/max-loss locks;
- transactional reservations;
- execution planning;
- exchange reconciliation primitives;
- execution report generation.

Status:
Development snapshot, explicitly not fully release-qualified.

Mandatory source:
`SNAPSHOT_STATUS.md`

The snapshot itself documents incomplete/unqualified areas such as private-WebSocket authority, account-mode permission checks, startup reconstruction, spot TP/OCO coordination, conditional-order lifecycle, partial-fill races, some leverage/margin/position-mode flows, liquidation precheck, portfolio correlation, emergency managed-close paths, protection deadlines, error/rate-limit/time-sync coverage, crash recovery and full static qualification.

Therefore:
- never treat a green narrow test as release qualification;
- never silently enable real execution;
- never claim the snapshot satisfies all Prompt-3 requirements without proving them.

Normal verification:
- `pytest -q`

## Cross-package invariants

- Package 1 may describe market state only.
- Package 2 owns strategy intent only.
- Package 3 owns financial permission, sizing and execution.
- Frozen contract/schema changes require producer + consumer + fixture/test review.
- Duplicated authority across packages is a defect unless explicitly documented as immutable contract duplication.
- ZIP copies at repo root are artifacts; do not treat them as runtime authority unless a mission explicitly concerns packaging/release parity.
