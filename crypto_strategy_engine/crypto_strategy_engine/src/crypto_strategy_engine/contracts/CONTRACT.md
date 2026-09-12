# HM_CRYPTO_V1 Contract

This package carries a local independent copy of the frozen inter-package contract. It never imports
Package 1 or Package 3. The authoritative machine-readable schema is duplicated at:

- `contracts/schema.json`
- `src/crypto_strategy_engine/contracts/schema.json`

The two files must be byte-identical. `CONTRACT_SCHEMA_SHA256` is reported in `BUILD_REPORT.md` and by
`python -m crypto_strategy_engine schema-hash`.

## Enumerations

Exchange: `BYBIT`, `BINANCE`  
TradingEnvironment: `DEMO`, `REAL`  
MarketMode: `SPOT`, `DERIVATIVES`  
PatternType: `PRE_BREAKOUT`, `BREAKOUT`, `CONTINUATION`, `REVERSAL`  
Direction: `LONG`, `SHORT`, `NONE`  
OrderIntent: `OPEN`, `CLOSE`, `REDUCE`, `NONE`  
DecisionState: `NO_TRADE`, `WATCH`, `ARMED`, `ENTER`  
RegimeType: `TREND_EXPANSION`, `HEALTHY_PULLBACK`, `BALANCE`, `FAILED_BREAKOUT`, `REVERSAL_RISK`, `RANGE`, `UNKNOWN`  
DataQuality: `GOOD`, `DEGRADED`, `STALE`, `INVALID`

## MarketSnapshot

Required top-level fields: `contract_version`, `snapshot_id`, `created_at_utc`, `event_time_utc`,
`exchange`, `environment`, `market_mode`, `symbol`, `instrument`, `ticker`, `timeframes`, `structure`,
`levels`, `volume_profile`, `orderflow`, `orderbook`, `derivatives`, `regime`, `breakout_alert`,
`data_quality`, `quality_reasons`, `feature_versions`, `source_timestamps`.

Package 2 may consume additional snapshot fields when present, but it never fetches missing market data.
Missing evidence reduces authority or blocks an evidence-dependent setup.

## TradeIntent

Required fields: `contract_version`, `signal_id`, `snapshot_id`, `created_at_utc`, `exchange`,
`environment`, `market_mode`, `symbol`, `pattern_type`, `direction`, `order_intent`, `decision`,
`thesis_id`, `attempt_no`, `deterministic_confidence`, `ai_confidence`, `final_confidence`, `entry_plan`,
`invalidation`, `targets`, `projected_extension_target`, `risk_reward`, `penalties`, `blockers`,
`evidence`, `ttl_ms`, `config_version`, `strategy_version`, `ai_metadata`, `integrity_hash`.

`ENTER` is strategy approval to forward the intent; it is not exchange execution.

## ExecutionReport

The local schema defines the future feedback interface including execution identity, final quantity and
notional, leverage/margin mode, order/fill state, prices/fees/PnL, stop/TP state, before/after risk
snapshots, financial locks, reconciliation and integrity hash. Package 2 never creates these execution
authority fields; it only validates/ingests a report for learning after integration.

## Precision and time

All contract timestamps use UTC with `Z`. Financial precision-bearing contract values such as prices,
quantities, notionals and PnL are represented as decimal strings and parsed with `Decimal`; floats are
used only for normalized/scoring diagnostics where financial precision is not authoritative.
