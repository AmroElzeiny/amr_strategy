# crypto_market_intel

Standalone Bybit V5 public market-data and deterministic market-intelligence package for `HM_CRYPTO_V1`. It is Package 1 only: it sees and describes the market; it **cannot** place, approve, size, close, reduce or manage a trade.

## What is implemented

- Bybit V5 public REST + public WebSocket adapter; no authenticated/order client.
- Full cursor pagination for Bybit linear instruments; spot follows Bybit's non-cursor endpoint behavior.
- Eligibility filters and deduplicated top gainers / losers / turnover scanner.
- Two-tier breakout architecture: global lightweight scout over the eligible universe, then deep watch only for promoted symbols.
- Percentage acceleration, major-structure, range, key-level and trendline breakout alerts with TTL promotion.
- Multi-timeframe bars; 1s/5s/30s micro-bars are built only from real public trades.
- Swings, HH/HL/LH/LL, BOS/CHOCH, major/minor structure, ranges, support/resistance, repeated tests, compression/expansion/displacement/pullback, HTF/context levels, sessions, equal highs/lows, liquidity pools/sweeps, failed breaks, reclaim and acceptance states.
- Python-native FVG/imbalance/order-block/breaker/reclaim/Fibonacci/equilibrium/origin/retest definitions.
- Executed-trade volume profile (POC/VAH/VAL/HVN/LVN/value area, developing POC/value migration, session/impulse/pullback profiles).
- Session and anchored VWAP (session, impulse, breakout event and major swing anchors).
- Taker-side footprint, aggressive buy/sell volume, delta/cumulative delta, per-price/per-bar delta, impulse/pullback delta, imbalance/stacked imbalance and velocity.
- Absorption and exhaustion features combining participation, progress and L2 response.
- Local L2 reconstruction from snapshot + delta, snapshot reset, reconnect/gap fail-closed resync, staleness, walls/persistence, add/pull, wall distance, imbalance, liquidity migration and diagnostic ephemeral/spoof-like behavior.
- Enabled-by-default TPO/market profile for balance/acceptance/rejection/single prints.
- Derivatives mark/index/basis, OI + change, funding + timing, and public liquidation intensity when available. Spot uses `None` + availability metadata, never fake zeros.
- Regime/balance classification: trend expansion, healthy pullback, balance, failed breakout, reversal risk, range and unknown.
- Per-source freshness/data-quality state with sequence/reconnect/stale/missing reasons.
- Restart-safe local capture/replay of actual trades, bars, orderbook snapshot/deltas, features and breakout alerts using SQLite/WAL; optional DuckDB/Parquet export.
- Frozen `MarketSnapshot`, `TradeIntent` and `ExecutionReport` schema for future independent packages. Only `MarketSnapshot` is produced here.

## Install

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e .
```

Optional Parquet export and development tools:

```bash
pip install -e '.[storage,dev]'
```

Copy `.env.example` to your runtime environment and adjust thresholds. No API key or secret is required.

## Quick public scan

```bash
python examples/scan_once.py
```

This performs public market-data calls only. `TRADING_ENV=DEMO` still uses Bybit mainnet **public** market data, as required by Bybit Demo Trading documentation. There is no Testnet routing in this package.

## Tests

Default unit/schema/failure/restart tests are network-free:

```bash
pytest -q
python tools/lint_check.py
python tools/type_contract_check.py
python tools/dependency_boundary_check.py
python tools/secret_scan.py
```

The real-public-data smoke is deliberately opt-in and contains no order/private call:

```bash
RUN_LIVE_BYBIT_SMOKE=1 pytest -q -m live tests/test_live_smoke.py
```

## Package boundaries

There are no imports from `crypto_strategy_engine`, `crypto_risk_execution`, MT5, MQL5 or MetaTrader. `BINANCE` is retained in the frozen contract vocabulary but Package 1 refuses `EXCHANGE=BINANCE` at runtime because no complete Binance live adapter is implemented. This prevents a contract enum from being misrepresented as a supported live source.

## Contracts and provenance

Read `CONTRACT.md`, `ARCHITECTURE.md`, `PATTERN_DEFINITIONS.md`, `ALGORITHM_POLICY.md`, `ENVIRONMENT.md`, `REFERENCE_CONCEPT_MAP.md` and `BUILD_REPORT.md`. `MANIFEST.json` contains file hashes. The machine-readable schema is duplicated at `contracts/schema.json` and `src/crypto_market_intel/contracts/schema.json`; their SHA-256 is reported in `BUILD_REPORT.md`.
