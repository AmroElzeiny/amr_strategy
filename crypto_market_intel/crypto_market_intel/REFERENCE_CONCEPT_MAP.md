# Reference concept map

Reference repository reviewed at build time: `AmroElzeiny/MT5`, branch `main`, observed latest commit `25cca426e8c05bb2737da70a9b1730faf1eb3c12` (2026-09-11). The old repository is a conceptual reference only. No MQL/MetaTrader runtime dependency exists in this package, and implementation was redesigned for Python + exchange APIs.

| Reference area | Concept understood | Applied here | Crypto/Python redesign or rejection |
|---|---|---|---|
| `python/architecture_contracts.py` | versioned contracts, canonical identity, strict serialization, atomic state | Yes | Frozen JSON schema, deterministic snapshot/hash semantics; no file-bus dependency |
| `python/decision_integrity.py` | deterministic identity, Decimal-aware integrity, fail-closed validation | Yes | Market-data/schema integrity only; no trading decision authority |
| `python/structured_models.py` | closed vocabularies and strict schemas | Yes | Pydantic frozen models + JSON Schema; no LLM transport dependency |
| `python/decision_pipeline.py` | evidence must be validated before authority | Concept only | Market features expose provenance/quality; no analyst/critic/adjudicator layer in Package 1 |
| `python/evidence_catalog.py` | Python-owned evidence identity, no invented evidence | Yes in spirit | Source timestamps, feature versions, quality reasons are deterministic Python-owned fields |
| `python/request_lifecycle.py` | durable state, atomic/restart-safe behavior | Yes | Local SQLite/WAL archive and replay; websocket reconnect explicitly invalidates L2 until snapshot resync |
| `python/repeatability_state.py` | explicit unavailable/stale/incompatible states; never fabricate observations | Yes in spirit | Missing derivatives/orderflow sources remain `None`; data quality is explicit and fail-closed |
| `python/trade_memory.py` | durable history + integrity-gated replay | Yes | Real observed trades/bars/L2/features/alerts are archived for replay; no trade outcome memory here |
| `python/ai_provider.py`, `python/opencode_routing.py`, `python/ai_gate.py` | advisory components cannot own deterministic authority; routing should be deterministic | Boundary concept only | No LLM is used in this package. Scanner/promotion are deterministic. MT5 file-bus/provider machinery rejected |
| `MT5_PO3_Codex Include/FVG.mqh` | three-candle FVG, mitigation/invalidation, normalized thresholds | Yes, redefined | Decimal Python FVG/imbalance/value-location definitions with documented formulas and testable output; no CopyRates/MQL |
| `MT5_PO3_Codex Include/PO3.mqh` | dealing range, sweep → displacement → BOS, session context | Yes, redesigned | Generic crypto structure: swings, BOS/CHOCH, sweeps, displacement, acceptance/reclaim/ranges; 24/7 UTC crypto sessions/context |
| `MT5_PO3_Codex Include/Risk.mqh` | fail-closed normalization/circuit-breaker discipline | Boundary only | Trading sizing, risk money, volume normalization, loss locks rejected from Package 1; they belong in execution/risk package |
| `MT5_PO3_Codex Include/PenaltyWatcher.mqh` | explicit degradation state and configurable invalidation | Limited | Used only for data-quality/degradation design; position cuts/closes/cooldowns rejected |
| `MT5_PO3_Codex Include/TradeEngine.mqh` | current path was inspected | No | File is empty in the reviewed revision; there is no implementation to port |

## Important non-ports

MT5 symbols, magic numbers, terminal/global variables, MQL indicators, broker order APIs, position management, risk sizing, order placement, and provider/LLM orchestration are intentionally absent. The package takes concepts, not implementations.
