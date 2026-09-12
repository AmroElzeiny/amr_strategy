# Architecture

## Authority model

`crypto_strategy_engine` is the **strategy authority**, not execution authority and not capital-risk
authority. All exchange/account authority is intentionally absent. The package accepts only a local
HM_CRYPTO_V1 `MarketSnapshot` mapping and returns a local HM_CRYPTO_V1 `TradeIntent` mapping.

## Evaluation pipeline

1. Validate contract, UTC timestamps, lineage, freshness, data quality, and Decimal-bearing fields.
2. Freeze the snapshot using canonical JSON and compute a stable snapshot hash.
3. Build a deterministic evidence catalog with Python-owned evidence paths and hashes.
4. Run enabled pattern detectors: PRE_BREAKOUT, BREAKOUT, CONTINUATION, REVERSAL.
5. Build deterministic candidate/thesis identities.
6. Apply hard blockers before AI.
7. Compute component scores and target viability.
8. Apply versioned, root-cause-deduplicated strategy penalties.
9. Compute deterministic confidence (0-100 diagnostic score, not an asserted probability).
10. Add clean, past-only analogue/calibration context when available.
11. Deterministically decide whether an AI review is worth calling.
12. Freeze the AI request identity and call protocol-specific advisory providers.
13. Strictly validate AI JSON, identity echoes, evidence references, and deadline/TTL authority.
14. Perform deterministic final arbitration with bounded positive AI adjustment and larger allowed downgrade/veto.
15. Freeze the TradeIntent integrity hash and persist decision lineage when enabled.

Hard blockers always dominate confidence and AI. Missing evidence remains missing; the engine never
turns an unavailable feature into a neutral zero market fact.

## Pattern architecture

### CONTINUATION

Primary family. Required concept chain:

`qualified impulse -> controlled corrective pullback -> meaningful retest -> opposing-side failure -> re-engagement -> target room`

The detector compares pullback depth, duration, velocity, volume, delta, displacement, overlap and
countertrend structure damage against the original move. Retest locations are scored by reliability,
freshness, structural significance, and evidence-root independence, preventing raw confluence-count
inflation. A third minor pullback without a major reset cannot recycle into a fresh continuation entry.
The theoretical target is:

`reengagement_origin + direction * abs(impulse_end - impulse_origin) * 1.60`

The projected target is retained in the intent, while the practical target may stop earlier at an
enabled, strong structural/liquidity/value obstacle.

### BREAKOUT

Supports `RANGE_BREAK`, `MAJOR_STRUCTURE_BREAK`, `KEY_LEVEL_BREAK`, `TRENDLINE_BREAK`,
`COMPRESSION_BREAK`, `LIQUIDITY_DRIVEN_BREAK`, `VALUE_AREA_ESCAPE`, `LOW_VOLUME_NODE_ESCAPE`,
`BREAK_AND_ACCEPT`, and `BREAK_RETEST_CONTINUE`.

Entry branches are `IMMEDIATE_BREAKOUT`, `FIRST_MICRO_PULLBACK`, `SECOND_MICRO_PULLBACK`, and
`MAJOR_PULLBACK_REENTRY`. Minor pullbacks beyond the configured sequence are exhausted unless a major
reset is supplied.

### PRE_BREAKOUT

Requires level strength, compression, directional pressure, directional market evidence and room.
Balance/chop evidence (POC/value stagnation, two-sided behavior, midpoint/VWAP churn) can reject a
nominal compression signal. Its ENTER threshold is intentionally stricter than normal continuation.

### REVERSAL

Strict family requiring the configured combination of liquidity event, opposite displacement and
microstructure confirmation. Traditional indicators may appear only as secondary evidence and cannot
create a reversal by themselves.

## Balance and fake-breakout killers

Strategy-level risk scores re-evaluate the MarketSnapshot even if its regime label looks favorable.
`BALANCE_HARD_BLOCK` and `FAILED_BREAKOUT_HARD_BLOCK` prevent ENTER when evidence indicates horizontal
value, POC stagnation/oscillation, two-sided failure, repeated loss of expansion, return/acceptance in
the prior range, weak follow-through, contradictory delta/value migration, or equivalent failure.

## Target and invalidation architecture

Entry plans contain entry type/reference/zone, trigger condition/price, expiry, max chase distance and
preferred execution style. Invalidation is structural and defines conditions plus confirmation modes;
it does not close positions itself. Target construction requires an entry, invalidation distance, and
a viable forward target. RR below `MIN_ACCEPTABLE_RR` hard-blocks the setup.

## AI gate

The AI layer is advisory. Routing is deterministic and never asks a model which model should be used.
Low-quality candidates make no AI call. WATCH candidates may receive one review; ARMED and potential
ENTER candidates receive stronger routing. Analyst and Critic roles are implemented, with a configurable
Adjudicator only when reviews materially disagree or the candidate is near the critical threshold.

OpenCode Go is the primary path. Official OpenCode Go documentation checked on 2026-09-12 maps
`qwen3.8-flash` to `/v1/messages` (Anthropic-compatible) and `muse-spark-1.3-contributor` to
`/v1/responses` (OpenAI Responses-compatible). OpenAI fallback uses `/v1/responses`, model
`gpt-5.6-luna`, `reasoning.effort=low`, and `service_tier=flex`.

No silent model substitution occurs: each fallback attempt records provider, requested model, failure
type, and whether fallback was used. A model cannot change candidate identity, entry, invalidation,
targets, hard blockers, quantity, leverage, or any exchange/account authority.

## Persistence

SQLite stores decisions, clean outcomes, quarantine and persistent thesis state. WAL + FULL synchronous
mode is used for durable state. JSON decision-log writes use atomic replace. Thesis identity groups
PRE_BREAKOUT/BREAKOUT/CONTINUATION around the same structural breakout event so changing the setup
family cannot bypass attempt limits.

## Walk-forward research

Research uses chronological train -> validation -> test windows and rolls forward. Random shuffle is
not used. Signal research reports theoretical R-style outcome metrics and does not label them realized
PnL. Execution feedback becomes eligible only after a reconciled ExecutionReport with valid integrity
and matching strategy identity is ingested. Ablation, calibration, failure modes, grouped metrics and
champion/challenger comparison are deterministic. `WALKFORWARD_AUTO_PROMOTE=false` by default.
