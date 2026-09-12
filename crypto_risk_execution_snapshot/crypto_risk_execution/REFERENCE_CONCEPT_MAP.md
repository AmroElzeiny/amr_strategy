# Reference concept map

Repository inspected: `AmroElzeiny/MT5`, current main revision observed during the build: `25cca426e8c05bb2737da70a9b1730faf1eb3c12` (2026-09-11).

| MT5 area | Concept retained | Crypto-native redesign |
|---|---|---|
| `MT5_PO3_Codex Include/Risk.mqh` | risk-by-stop, floor-to-step, daily anchors, behavior stops | Decimal sizing, exchange metadata, SQLite locks/reservations, UTC anchors |
| `PenaltyWatcher.mqh` | MAE/giveback/stuck penalties, cooldown/strike identity | exchange-neutral deterministic position metrics; never increases exposure |
| `TradeEngine.mqh` | trade identity, ownership, close/fill reconciliation | client IDs + signal/execution lineage + managed registry |
| `python/decision_integrity.py` | canonical identity/integrity and frozen authority boundaries | canonical TradeIntent hash + FrozenTradeIntent request hash |
| `python/request_lifecycle.py` | durable exactly-once semantics | transactional signal/reservation/order lifecycle |
| `python/trade_memory.py` | SQLite durability and quarantine philosophy | local execution-state ledger and audit trail |

Rejected: MQL/MetaTrader runtime dependencies, terminal globals/files as primary durable state, MT5 symbol precision authority, MQL technical-structure inference inside execution, and any LLM authority over quantity/leverage/orders.
