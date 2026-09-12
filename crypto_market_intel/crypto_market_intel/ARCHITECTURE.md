# Architecture

## Boundary

`crypto_market_intel` is a standalone, public-market-data intelligence package. It imports neither `crypto_strategy_engine` nor `crypto_risk_execution`; it exposes a frozen `MarketSnapshot` contract for a later independent consumer. There is no authenticated/order API path.

## Two-tier market architecture

**Tier 1 — Global Scout:** refreshes the full eligible Bybit instrument universe with full cursor pagination for linear products, applies configurable eligibility filters, ranks top gainers/losers/turnover with deduplication, and feeds lightweight ticker-derived rolling observations into percentage, major-structure, range, key-level, and trendline breakout detectors. It does not open trades/orderbook subscriptions for every symbol.

**Tier 2 — Promoted Watch:** only symbols promoted by scanner ranking or a qualified breakout alert are eligible for `publicTrade`, orderbook and (derivatives) liquidation topics. `DeepMarketStreamState` reconstructs L2 from snapshot + delta, archives the real messages, invalidates on reconnect/gap evidence and requires a new snapshot before deltas are accepted. Deep snapshots calculate market structure, ICT/value locations, real-trade volume profile, taker-side footprint/delta, VWAPs, TPO, absorption/exhaustion, L2 diagnostics, derivatives context, regime and data quality.

## Data flow

`Bybit V5 public REST/WS -> normalized Decimal domain objects -> Tier-1 scanner/scout -> watch registry -> Tier-2 stream state -> deterministic features -> data-quality gate -> HM_CRYPTO_V1 MarketSnapshot -> local archive/replay`

## Timeframes

Entry defaults: `1m,3m,5m,15m`; context defaults: `1h,4h,1d`; micro bars: `1s,5s,30s`. Bybit does not provide those sub-minute candles, so micro bars are constructed exclusively from actual public trades, never ticker snapshots.

## L2 semantics

A fresh Bybit `snapshot` replaces the local book. A `delta` applies absolute sizes: size zero deletes a level, new price inserts, existing price replaces. `u=1`, missing sequence metadata, update/sequence regression, or an observed websocket reconnect/lost-frame condition invalidates the book and requires resync. Forward `u` increments are not assumed to be `+1` because the official V5 contract does not provide that guarantee. The package never describes public L2 as all market liquidity; diagnostics explicitly note omitted liquidity classes such as RPI.

## Feature definitions

- Swing high/low requires a configurable neighborhood, not a one-candle directional heuristic. HH/HL/LH/LL progression feeds BOS/CHOCH and regime context.
- FVG bullish: in chronological bars `(i-2,i-1,i)`, `high[i-2] < low[i]`; bearish: `low[i-2] > high[i]`. Zones retain mitigation/invalidation state.
- Fibonacci retracement levels are calculated from a detected impulse range; 50% is equilibrium; extension levels project beyond the impulse.
- Volume profile bins executed trade price by instrument tick size. POC is max-volume bin; value area expands deterministically from POC until configured volume percentage is covered; VAH/VAL are outer selected bins.
- Footprint buy/sell aggressor is the actual Bybit public-trade taker side. Delta = aggressive buy quantity − aggressive sell quantity. Candle colour is never used as aggressor proxy.
- Absorption combines aggressive volume near a level, limited price progress, repeated interaction and orderbook imbalance/response. Exhaustion combines falling trade velocity/aggressive participation with diminishing price extension. Thresholds are environment-configurable.
- TPO is an optional, enabled-by-default time-at-price distribution used for balance/acceptance/rejection context.
- Regime uses price overlap, swing progression, expansion/extension, value migration, directional delta, breakout follow-through and return-to-range. Volatility is normalization/context, not the sole decision source.

## Persistence

Always-on storage uses zero-dependency SQLite/WAL so capture cannot silently disappear when optional analytics libraries are missing. The archive stores public trades, bars, real orderbook snapshots/deltas, generated features and breakout alerts and is restart-readable. An explicit DuckDB/Parquet exporter is provided under the `storage` extra; it fails loudly if the optional dependency is not installed rather than writing fake parquet.
