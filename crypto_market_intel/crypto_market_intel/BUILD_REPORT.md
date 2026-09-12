# Build report — crypto_market_intel

Build date: 2026-09-12 (UTC contract; build host Python 3.13.5)  
Contract: `HM_CRYPTO_V1`  
Reference repo reviewed: `AmroElzeiny/MT5` at observed current `main` commit `25cca426e8c05bb2737da70a9b1730faf1eb3c12` (2026-09-11)  
Live source implemented: Bybit V5 public market data only  
Trading/order authority: none

## Contract identity

`CONTRACT_SCHEMA_SHA256=dbdcf779916a02cfac97698979f1201ee463d3de38e9bb27139895fe5b47945f`

The root `contracts/schema.json` and package-local `src/crypto_market_intel/contracts/schema.json` were byte-identical at the final gate. `contract_version` is a required JSON-Schema `const` for `MarketSnapshot`, `TradeIntent` and `ExecutionReport`. `BreakoutAlert` fields are required while semantically unavailable measurements remain explicitly nullable.

## Actual final commands and results

```text
PYTHONPATH=src python tools/build_schema.py
build_schema: PASS

PYTHONPATH=src python -m compileall -q src tests examples tools
compileall: PASS

PYTHONPATH=src pytest -q -rA
27 passed; 1 skipped
SKIPPED tests/test_live_smoke.py: opt-in only: set RUN_LIVE_BYBIT_SMOKE=1

python tools/lint_check.py
lint_check: PASS (20 Python files)

python tools/type_contract_check.py
type_contract_check: PASS (all public callables annotated)

python tools/dependency_boundary_check.py
dependency_boundary_check: PASS (no Package 2/3, MT5, or Testnet runtime dependency)

python tools/secret_scan.py
secret_scan: PASS (no credential/private-key patterns found)

installed editable package import
installed_import: PASS contract=HM_CRYPTO_V1 exchange=BYBIT env=DEMO mode=DERIVATIVES
```

The lint and type gates above are repository-local deterministic build gates. `pyproject.toml` additionally declares Ruff and Mypy in the `dev` extra for downstream CI/clean environments. Default tests make no network calls; the one real-public-data smoke test is intentionally opt-in and contains no private/authenticated/order call.

Build dependency versions used for the executed test suite: Python 3.13.5, pytest 9.0.2, pydantic 2.13.4, httpx 0.28.1, websockets 16.0, jsonschema 4.26.0.

## Success requirements evidence

1. **Standalone package:** editable installation/import passed; all runtime dependencies are declared in `pyproject.toml`.
2. **No Package 2/3 dependency:** static boundary gate passed.
3. **No MT5 runtime dependency:** static boundary gate passed; MT5 exists only in reference documentation.
4. **Full Bybit instrument pagination:** tested with cursor fixtures for linear instruments; spot follows current Bybit non-cursor behavior.
5. **Scanner ranking:** fixture verifies gainers, losers, turnover and deduplication.
6. **Global breakout:** fixtures verify percentage acceleration and major-structure break; range/key-level/trendline are also tested.
7. **Promotion without all-market deep subscriptions:** test verifies deep topics are generated only for promoted/watch symbols.
8. **L2 reconstruction:** snapshot + delta + fresh snapshot reset tested.
9. **Gap/resync:** regression/reconnect fail closed; fresh snapshot resync and `resync_count` tested.
10. **Footprint source:** uses actual Bybit public-trade taker side.
11. **Delta math:** manually checkable fixture test passed.
12. **Volume profile:** POC/VAH/VAL fixture test passed; HVN/LVN/developing/value migration are implemented.
13. **Balance detector:** explicit trend vs range/balance test passed.
14. **Spot derivatives data:** test verifies `None`/availability metadata, not fabricated zero values.
15. **Freshness:** GOOD/STALE/INVALID source tests passed; reconnect/resync/source-age reasons are surfaced.
16. **Replay:** archive restart and ordered replay tests passed; actual L2 delta archival is tested.
17. **No committed secrets:** secret gate passed; Package 1 requires no API credential.
18. **Network-free unit tests:** default suite uses fixtures/mocks; live smoke skips unless explicitly enabled.
19. **Opt-in public-data smoke:** `tests/test_live_smoke.py` exists and calls only public ticker data.
20. **Pytest green:** 27 passed, 1 intentional opt-in skip.
21. **Schema SHA:** recorded above and in `MANIFEST.json`.
22. **Final ZIP:** generated as `crypto_market_intel.zip` after this report and manifest are finalized.

## Bybit V5 documentation checked for this build

Current official V5 documentation was reviewed for instruments info/pagination, tickers, klines, recent public trades, REST/WS order book behavior and sequence fields, open interest, funding, all-liquidation stream, demo environment routing and rate limits. In particular: Demo public market data uses mainnet public endpoints; Demo private WS is separate; Testnet is not a supported mode in this package; Bybit public-trade `S` is used as the aggressor/taker side; orderbook state is reconstructed from snapshot + delta and resets on a new snapshot; a reconnect/lost-frame observation forces local resync rather than assuming an intact book.

Official references are listed in `ENVIRONMENT.md`.

## Scope intentionally not present

There is no Binance live adapter, LLM, strategy decision, Buy/Sell trade authorization, private account state, API credential handling, final quantity, leverage/margin mutation, daily/max-loss logic, or order placement. Those are outside Package 1 by design, while their frozen cross-package contract vocabulary remains defined for later independent packages.
