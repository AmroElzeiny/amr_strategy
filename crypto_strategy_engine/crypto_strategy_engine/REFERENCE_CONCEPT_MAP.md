# Reference concept map

Reconnaissance source: `https://github.com/AmroElzeiny/MT5`  
Repository revision inspected: `25cca426e8c05bb2737da70a9b1730faf1eb3c12` (current main observed during build on 2026-09-12).
The repository was used as an architectural/trading-concept reference only. No MetaTrader/MQL runtime
dependency is present in this package.

| Reference area | Concept understood | Python/crypto redesign | Rejected/changed |
|---|---|---|---|
| `python/ai_gate.py` | deterministic pre-gate before LLM, advisory veto, deadlines, repeatability/memory integration | candidate must exist deterministically before AI; AI is evidence-bound and bounded | MT5 Common-folder/FileBus orchestration rejected |
| `python/ai_provider.py` | provider-neutral transport, strict structured responses, explicit provider identity/failure handling | small HTTP provider adapters for OpenCode Go and OpenAI fallback | provider switching is deterministic; no broker/file-bus coupling |
| `python/decision_pipeline.py` | analyst/critic/adjudication roles and qualitative consensus | ANALYST + CRITIC, optional ADJUDICATOR only on disagreement/critical threshold | LLM consensus never replaces deterministic authority |
| `python/decision_integrity.py` | frozen request, candidate hash, canonical identity echo validation | canonical JSON + SHA256 request/candidate/integrity hashes | execution fingerprint tied to MT5 order plumbing rejected |
| `python/structured_models.py` | strict provider output vocabulary/schema | local JSON Schema with semantic checks and provider-owned metadata | free-form model output has zero authority |
| `python/architecture_contracts.py` | versioned contracts and deterministic authority boundaries | independent local HM_CRYPTO_V1 schemas + config/strategy versions | MT5-specific compatibility/file lifecycle removed |
| `python/repeatability_state.py` | measure repeated AI stability without granting authority | research-only decision/veto/ranking/confidence/reason stability metrics | live consensus voting rejected |
| `python/request_lifecycle.py` | idempotency/exactly-once and atomic state principles | immutable request identity, SQLite transactions, atomic JSON decision logs | file claim/heartbeat bus not needed for local synchronous API |
| `python/evidence_catalog.py` | Python-owned bounded evidence IDs/paths instead of invented model references | deterministic evidence catalog and strict evidence reference validation | model-authored market facts/paths rejected |
| `python/trade_memory.py` | durable clean-outcome memory, quarantine, analogue retrieval | SQLite decisions/outcomes/quarantine; both event and resolution must precede candidate time | MT5 ledger encoding/bootstrap specifics removed |
| `python/opencode_routing.py` | deterministic model importance routing | deterministic WATCH/ARMED/ENTER route policy | asking an AI which model to call rejected |
| `MT5_PO3_Codex Include/PenaltyWatcher.mqh` | strategy degradation/invalidation confirmation ideas; stateful penalty philosophy | versioned strategy penalty catalog, root-cause dedup, structural invalidation definition | actual position cuts/closes belong to Package 3 and are excluded |
| `MT5_PO3_Codex Include/PO3.mqh` | qualified displacement/structure sequence, follow-through and context quality | impulse/breakout qualification components adapted to crypto snapshot evidence | broker/session assumptions not blindly ported; crypto runs 24/7 |
| `MT5_PO3_Codex Include/FVG.mqh` | FVG is contextual location with freshness/mitigation/quality, not a standalone trigger | FVG 0/25/50/75/100 can contribute as retest location; independence avoids duplicate confluence | `FVG touched -> trade` explicitly rejected |
| `MT5_PO3_Codex Include/Risk.mqh` | strict authority separation for financial risk | used only to reinforce that strategy may emit advisory risk hint | sizing, account risk, leverage and financial locks excluded |
| `MT5_PO3_Codex Include/TradeEngine.mqh` | verified execution identity and reconciled outcomes before learning | ExecutionReport integrity/reconciliation/mapping gates learning | all order placement/management logic excluded |

## Crypto-specific additions

The new implementation adds balance/chop and failed-breakout killers, adaptive multi-timeframe evidence,
value/POC migration, orderflow/orderbook/derivatives context when supplied, spot long-only opening
semantics, deterministic breakout branch exhaustion, 1.60 continuation projection with obstacle-aware
practical targets, persistent thesis attempt identity, time-aware analogue/calibration gating, feature
ablation, and champion/challenger walk-forward research.

## Provider documentation checked during build

- OpenCode Go: `https://opencode.ai/docs/go/` — confirmed Qwen3.8 Flash on `/v1/messages`, Muse Spark 1.3 Contributor on `/v1/responses`, and `/v1/models` discovery.
- OpenAI Models/API: `https://platform.openai.com/docs/models/` and Responses API reference — confirmed `gpt-5.6-luna`, Responses API availability, low reasoning effort, structured-output format support, and `service_tier=flex` parameter availability.
