# crypto_strategy_engine

Standalone **strategy authority** for the HM_CRYPTO_V1 crypto trading architecture.
It consumes a frozen `MarketSnapshot` JSON, validates and scores deterministic setup candidates,
optionally requests evidence-bound AI advisory reviews, arbitrates the result, persists lineage,
and emits one `TradeIntent`. It never connects to an exchange for market/account data and never
places, edits, or cancels orders.

## Responsibility boundary

- Package 1 answers: what is happening in the market?
- **This package answers:** is there a valid setup, what is the thesis, entry logic, invalidation,
  target viability, and strategy decision?
- Package 3 answers: is the trade financially allowed, what size/leverage is safe, and how is it executed?

`decision=ENTER` means only **forward this intent to an independent risk/execution layer**.
It is not an order-placement instruction.

## Supported strategy families

All four families are enabled by default: `PRE_BREAKOUT`, `BREAKOUT`, `CONTINUATION`, and `REVERSAL`.
`CONTINUATION` is the primary family, but arbitration is deterministic and does not blindly prefer it.
The continuation path requires a qualified impulse, comparative pullback quality, meaningful retest
location, opposing-side failure, directional re-engagement, and viable target room. Balance/chop and
failed-breakout risk can hard-block ENTER regardless of confidence.

## Install from a clean environment

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip setuptools
python -m pip install -e .
```

The ZIP also includes a prebuilt pure-Python wheel for offline/clean-environment installation:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --no-deps dist/crypto_strategy_engine-1.0.0-py3-none-any.whl
crypto-strategy-engine schema-hash
```

For development verification:

```bash
python -m pip install -e '.[dev]'
pytest
ruff check src tests
mypy src
```

Runtime dependencies are Python standard library only. `pytest`, `ruff`, `mypy`, and `jsonschema`
are development-only dependencies.

## Configuration

Copy `.env.example` values into your deployment environment. The package does not automatically read
a `.env` file; environment loading is deliberately left to the process supervisor/application so
secrets are never parsed from repository files implicitly.

AI secrets are read only at call time:

- `OPENCODE_GO_API_KEY`
- `OPENAI_API_KEY`

They are never part of the strategy config hash and are not written to decision logs.

## CLI

```bash
python -m crypto_strategy_engine validate tests/fixtures/healthy_continuation_long.json
python -m crypto_strategy_engine evaluate tests/fixtures/healthy_continuation_long.json --no-ai --no-persist
cat snapshot.json | python -m crypto_strategy_engine evaluate --stdin
python -m crypto_strategy_engine ingest-outcome execution_report.json
python -m crypto_strategy_engine walk-forward examples/historical_walkforward_records.json --output ./data/research/demo
python -m crypto_strategy_engine champion-config
python -m crypto_strategy_engine schema-hash
```

Network provider tests are mocked in the normal test suite. No real exchange order can be emitted by
this package. AI HTTP calls happen only when `AI_ENABLED=true` and routing admits a candidate.

## Python API

```python
from crypto_strategy_engine import (
    validate_market_snapshot,
    evaluate_snapshot,
    evaluate_candidates,
    ingest_execution_report,
    run_walkforward,
    get_champion_config,
)
```

`evaluate_snapshot(snapshot)` is the main public strategy API. Inputs and outputs are plain mappings
conforming to the local frozen contract so Package 1 and Package 3 do not need to be importable.

## Research and memory

The package uses SQLite for decision lineage, clean execution outcomes, quarantine, and persistent
thesis attempts. Historical analogue retrieval requires both the signal event and resolved outcome to
precede the current candidate time. Walk-forward research uses time-ordered train/validation/test
windows, supports ablation, time-aware calibration, champion/challenger comparison, and writes the
research artifacts requested in the architecture prompt without auto-promoting a challenger.

## Contract identity

- Contract: `HM_CRYPTO_V1`
- Strategy: `HM_STRATEGY_V1`
- Config: `HM_STRATEGY_CONFIG_V1`
- Schema SHA256: see `BUILD_REPORT.md` and `python -m crypto_strategy_engine schema-hash`

See `ARCHITECTURE.md`, `CONTRACT.md`, `ENVIRONMENT.md`, `REFERENCE_CONCEPT_MAP.md`, and
`LOOKAHEAD_AUDIT.md` for detailed design and safety constraints.
