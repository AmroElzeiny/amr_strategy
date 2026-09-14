# BUILD_REPORT — crypto_strategy_engine

Build date: 2026-09-12 (UTC)

## Overall build status

**Package implementation: COMPLETE. Functional verification: PASS. External lint/type-tool execution in this sandbox: BLOCKED BY TOOL AVAILABILITY.**

The package source, frozen contracts, strategy pipeline, AI advisory gate, persistence, trade memory,
walk-forward research, CLI, fixtures, tests, documentation, offline wheel, manifest, and ZIP release
are present. The normal pytest suite was executed twice and passed twice. A clean virtual environment
installed the prebuilt wheel with zero runtime dependencies and successfully imported the package and
read the packaged schema. `ruff` and `mypy` are declared development dependencies and release scripts
invoke both; however neither executable exists in this build container and the container cannot reach
PyPI (DNS/network egress fails). Therefore this report does **not** falsely claim those two external
tool invocations passed in this sandbox.

## Runtime / toolchain

- Python: 3.13.5
- Runtime dependencies: none (Python standard library only)
- setuptools: 82.0.1
- pytest: 9.0.2
- jsonschema: 4.26.0 (test-only)
- ruff: configured in `pyproject.toml`, unavailable in build sandbox
- mypy: configured in `pyproject.toml`, unavailable in build sandbox

Attempting `pip install 'ruff>=0.6' 'mypy>=1.11'` failed because the sandbox could not resolve/reach
PyPI (`Temporary failure in name resolution`). No lint/type result has been fabricated.

## Reference repository reconnaissance

Repository inspected: `AmroElzeiny/MT5`

Revision inspected: `25cca426e8c05bb2737da70a9b1730faf1eb3c12`

Key areas inspected and conceptually mapped include:

- `python/ai_gate.py`
- `python/ai_provider.py`
- `python/decision_pipeline.py`
- `python/decision_integrity.py`
- `python/structured_models.py`
- `python/architecture_contracts.py`
- `python/repeatability_state.py`
- `python/request_lifecycle.py`
- `python/evidence_catalog.py`
- `python/trade_memory.py`
- `python/opencode_routing.py`
- `MT5_PO3_Codex Include/Risk.mqh`
- `MT5_PO3_Codex Include/PenaltyWatcher.mqh`
- `MT5_PO3_Codex Include/PO3.mqh`
- `MT5_PO3_Codex Include/FVG.mqh`
- `MT5_PO3_Codex Include/TradeEngine.mqh`

Reused as concepts: deterministic pre-gate, immutable request/candidate identity, evidence-bound AI,
provider isolation, deadline/late-result handling, abstention/veto, repeatability, durable memory,
clean-outcome qualification, invalidation confirmation, setup structure/FVG context, and fail-closed
integrity checks.

Rejected as runtime architecture: MT5/MQL5 execution, FileBus coupling, terminal APIs, broker account
state, MQL position sizing, order submission/modification, MT5 symbol/risk authority, and any runtime
dependency on MetaTrader.

See `REFERENCE_CONCEPT_MAP.md` for the full mapping and crypto redesign rationale.

## Frozen contract

- `CONTRACT_VERSION`: `HM_CRYPTO_V1`
- `STRATEGY_VERSION`: `HM_STRATEGY_V1`
- `CONFIG_VERSION`: `HM_STRATEGY_CONFIG_V1`
- `CONTRACT_SCHEMA_SHA256`: `408b13714bd831ad2527801ef435d38681551e3b3ffee5eb7b1c96be579935e1`

The root and packaged schema copies are byte-identical. Local definitions cover `MarketSnapshot`,
`TradeIntent`, and `ExecutionReport`. Financial price/quantity/notional/PnL contract values use
Decimal-safe strings where precision is required. Time fields are UTC.

## Architecture / authority boundary

Implemented as a standalone **STRATEGY AUTHORITY**. It consumes HM_CRYPTO_V1 MarketSnapshot JSON and
emits a TradeIntent. It does not fetch exchange market/account data, read wallets, choose final quantity,
choose final leverage/margin mode, enforce financial daily/max-loss locks, place/cancel/modify orders,
or import Package 1 or Package 3.

A source import audit found no third-party runtime imports and no peer-package imports. Contract tests
also scan for forbidden exchange/MT5 execution dependencies.

## Pattern implementations

Implemented and enabled by default:

- PRE_BREAKOUT
- BREAKOUT
- CONTINUATION (primary family, not blind priority)
- REVERSAL

Implemented strategy controls include qualified impulse scoring, comparative pullback quality,
meaningful-location/confluence independence, opposing-side failure, re-engagement, multi-timeframe
context, balance/chop rejection, failed-breakout rejection, counter-pullback/reversal risk, target
obstacles, minimum RR, 1.60 continuation projected target, practical obstacle-limited targets,
first/second breakout pullbacks, exhausted-minor-pullback rejection, strict reversal qualification,
SPOT long-only opening authority, deterministic arbitration, and conflict-to-WATCH/NO_TRADE handling.

## Thesis / penalties / blockers

- Deterministic thesis identity and persistent attempt state implemented.
- PRE_BREAKOUT/BREAKOUT/CONTINUATION belonging to the same structural breakout-continuation event cannot
  evade attempt limits merely by switching family labels.
- Repeated touches do not create a new thesis without a material structural reset.
- Cooldown state persists.
- Versioned strategy penalty catalog implemented with root-cause deduplication.
- Hard blockers override confidence, including invalid/stale critical data, balance, failed breakout,
  target/RR failure, unsupported spot short, exhausted thesis attempts, expiry, conflicts, and missing
  required evidence.

## AI gate / providers

The deterministic engine creates a real candidate before any AI call. AI is advisory only and cannot
remove a hard blocker, mutate the frozen MarketSnapshot/candidate identity, set quantity/leverage, or
place orders.

Implemented roles:

- ANALYST
- CRITIC
- configurable ADJUDICATOR

Implemented strict structured response validation includes request/candidate identity hashes, evidence
references, semantic evidence existence, provider/model identity, veto codes, contradictions, missing
confirmations, risks, confidence band, and latency metadata. Malformed JSON, unknown evidence refs,
hash mismatch, late responses, and stale TTL responses have no live authority.

Provider routing implemented:

- OpenCode Go `muse-spark-1.3-contributor`: OpenAI Responses-compatible `/v1/responses`
- OpenCode Go `qwen3.8-flash`: Anthropic-compatible `/v1/messages`
- deterministic importance routing / optional dual review
- fallback to the other configured OpenCode model
- final OpenAI `gpt-5.6-luna` fallback via Responses API
- OpenAI `reasoning.effort=low`
- OpenAI `service_tier=flex`
- no silent model substitution

Provider protocols/model identifiers were checked against current official documentation during the
2026-09-12 build. Normal tests mock network access; no live AI credential or paid call is required.

## Trade memory / clean outcomes

SQLite persistence implements pending decision lineage, completed clean outcomes, quarantine, thesis
state, and historical analogue retrieval. ExecutionReport ingestion verifies contract identity,
signal mapping, reconciliation, and integrity hash. Dirty/unknown/corrupted outcomes are quarantined
with `learning_eligible=false` and a rejection reason.

Historical analogues require both their original event and their resolved outcome to predate the
current candidate. `INSUFFICIENT_SAMPLE` is explicit and is never converted to a fabricated win rate.

## Walk-forward / research

Implemented:

- time-ordered train -> validation -> out-of-sample test windows
- rolling windows, never random shuffle
- no-lookahead audit
- signal-quality vs execution-feedback semantics
- trade count, win/loss rate, average win/loss R, expectancy R, profit factor, median/total R,
  max drawdown R, drawdown duration, MFE, MAE, target/stop/timeout rates, failure-mode rates,
  calibration error and Brier score where eligible
- pattern, regime, confidence-band and other subgroup metrics
- feature ablation
- bounded challenger evaluation
- champion/challenger version/hash identities
- `WALKFORWARD_AUTO_PROMOTE=false` default
- deterministic promotion criteria
- time-aware Platt-style calibration with minimum sample gate
- AI research output explicitly marked research-only and unable to mutate live config

Verified walk-forward example result:

- window_count: 7
- no-lookahead audit: PASS
- calibration sample_count: 210
- calibration_available: true
- challenger promotion eligibility evaluated deterministically
- auto_promoted: false

Generated artifact set:

- `walkforward_summary.json`
- `walkforward_metrics.csv`
- `pattern_metrics.csv`
- `regime_metrics.csv`
- `confidence_calibration.json`
- `feature_ablation.csv`
- `failure_mode_analysis.csv`
- `champion_config.json`
- `challenger_config.json`
- `ai_research_hypotheses.json`

## Verification executed

### Python compilation

`python -m compileall -q src tests` -> PASS

### Unit/integration-local tests

Run 1: **64 passed, 0 failed** in 9.71 s

Run 2: **64 passed, 0 failed** in 9.95 s

Integration compatibility requalification (2026-09-15): **65 passed, 0 failed** after adding
Package 1 `MarketSnapshot` adapter coverage. The two 64-test results above are retained as the
historical release runs that preceded the added compatibility test.

Normal tests perform no real exchange network calls and no real orders.

### CLI verification

`validate healthy_continuation_long.json` -> valid=true, blockers=[]

`evaluate ... --no-ai --no-persist` ->

- decision: ENTER
- pattern_type: CONTINUATION
- direction: LONG
- order_intent: OPEN
- deterministic_confidence: 90.90845
- final_confidence: 90.90845
- risk_reward: 5.0
- projected_extension_target: 69800

`ingest-outcome` clean reconciled ExecutionReport -> `learning_eligible=true`

`walk-forward` example -> 7 ordered windows and all requested research output files written.

`schema-hash` -> `408b13714bd831ad2527801ef435d38681551e3b3ffee5eb7b1c96be579935e1`

### Clean virtual environment / standalone packaging

A pure-Python wheel was built and installed into a newly created virtual environment with `--no-deps`.
The environment then successfully:

- imported `crypto_strategy_engine`
- reported `HM_CRYPTO_V1 / HM_STRATEGY_V1 / HM_STRATEGY_CONFIG_V1`
- located packaged `contracts/schema.json`
- printed the expected schema SHA256
- passed `pip check` with `No broken requirements found.`

Wheel:

- `dist/crypto_strategy_engine-1.0.0-py3-none-any.whl`
- SHA256: `70f9423b95f7f590dd8a49aa3fcb235d0fa1df5874473c4d5a1fe538f3a38618`

### Deterministic latency benchmark

Fixture: `healthy_continuation_long.json`, AI disabled, memory disabled, persistence disabled, 300 measured
runs after warm-up.

- median: 2.4654 ms
- p95: 2.7559 ms
- p99: 3.2004 ms
- max: 3.6733 ms
- configured deterministic budget: 50.0 ms
- p95 within budget: PASS

### Runtime-dependency/static source audit

AST import audit across `src/`:

- syntax errors: 0
- external runtime imports: 0

Forbidden source-boundary checks are included in the test suite. No TODO/FIXME/NotImplemented placeholder
was found in mandatory implementation paths. No committed API key or bearer-token-shaped secret was found.

## Lint / type-check result

`ruff check src tests`: **NOT EXECUTED — executable unavailable; installation blocked by sandbox DNS/network**

`mypy src`: **NOT EXECUTED — executable unavailable; installation blocked by sandbox DNS/network**

The release includes `scripts/verify_release.sh` and `scripts/verify_release.ps1`, and `pyproject.toml`
contains the exact Ruff/Mypy configuration and dev dependencies. In an environment with development
dependencies available, run:

```bash
python -m pip install -e '.[dev]'
scripts/verify_release.sh
```

Because the original success criteria explicitly require actual green Ruff and type-check invocations,
this sandbox limitation is a **verification gap**, not a claimed pass.

## Known limitations

1. Live provider integration was intentionally not exercised because no user credentials are embedded in
   the build and provider integration tests are opt-in. Provider transports are covered by mocked tests.
2. Real exchange orders are structurally outside this package and cannot be emitted by it.
3. Ruff/Mypy could not be executed in this sandbox for the external-tool availability reason documented
   above. This is the only unresolved mandatory verification item; it is not an implementation placeholder.
