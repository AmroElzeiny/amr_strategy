# HM_CRYPTO_V1 frozen contract

`CONTRACT_VERSION=HM_CRYPTO_V1` is immutable for this package version. The authoritative machine-readable schema is `contracts/schema.json`, with an identical package-local copy at `src/crypto_market_intel/contracts/schema.json`.

## Closed vocabularies

- Exchange: `BYBIT`, `BINANCE`. **Only Bybit has a live adapter in this package.** Binance is contract vocabulary only.
- TradingEnvironment: `DEMO`, `REAL`.
- MarketMode: `SPOT`, `DERIVATIVES`.
- PatternType: `PRE_BREAKOUT`, `BREAKOUT`, `CONTINUATION`, `REVERSAL`.
- Direction: `LONG`, `SHORT`, `NONE`.
- OrderIntent: `OPEN`, `CLOSE`, `REDUCE`, `NONE`.
- DecisionState: `NO_TRADE`, `WATCH`, `ARMED`, `ENTER`.
- RegimeType: `TREND_EXPANSION`, `HEALTHY_PULLBACK`, `BALANCE`, `FAILED_BREAKOUT`, `REVERSAL_RISK`, `RANGE`, `UNKNOWN`.
- DataQuality: `GOOD`, `DEGRADED`, `STALE`, `INVALID`.

## Contracts

`MarketSnapshot` includes contract/snapshot identity, UTC creation/event timestamps, exchange/environment/mode/symbol, instrument/ticker, multi-timeframe bars, structure/levels, volume profile, orderflow, orderbook, derivatives context, regime, breakout alert, data-quality state/reasons, feature versions, and source timestamps.

`TradeIntent` and `ExecutionReport` are defined locally for cross-package interoperability but are **not produced or executed** by this package. Their full fields are frozen in `schema.json`.

All money/price/quantity/notional/PnL fields that need financial precision are represented by Python `Decimal` before JSON serialization. UTC is the only time basis.

## Authority boundaries

This package owns market-data normalization, freshness, feature calculation, and snapshot identity. It has no API credentials, private account adapter, order placement, leverage setting, quantity authority, margin authority, daily-loss authority, or trade-decision authority. Missing or corrupt safety-relevant market data is surfaced as unavailable/degraded/stale/invalid rather than synthesized as zero.
