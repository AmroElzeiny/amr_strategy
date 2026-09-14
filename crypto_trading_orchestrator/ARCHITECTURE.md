# Architecture

## Pipeline

```text
Package 1 scanner/public data
  -> MarketSnapshot
  -> Package 2 validation/evaluation
  -> NO_TRADE | WATCH | ARMED | ENTER
  -> ENTER only: Package 3 validation/risk/execution
  -> ExecutionReport / protection events
  -> closed, reconciled, integrity-valid report
  -> Package 2 feedback memory
```

Package 4 is a control plane. Thin adapters perform invocation and transport normalization only.
The one semantic producer mismatch—Package 1 list-shaped market levels versus Package 2's native
mapping-shaped evidence—is normalized inside Package 2, where strategy interpretation belongs.
Package 3 accepts Package 2's zero-based attempts and entry-reference vocabulary.

## State and scheduling

The startup state machine is `BOOT`, `CONFIG_VALIDATE`, `PACKAGE_DISCOVERY`, `CONTRACT_VALIDATE`,
`EXCHANGE_MODE_VALIDATE`, `RISK_EXECUTION_RECONCILE`, `MARKET_DATA_START`, `SCANNER_START`, `READY`,
and `RUNNING`. Failures transition to `BLOCKED`. Shutdown moves through `STOPPING` to `STOPPED`.

The event bus has two lanes. Risk/execution/protection events at priorities 0–3 are never evicted.
Market/research events at priorities 4–6 are bounded, and replace older pending events with the
same `(event_type, symbol)` key. Per-symbol locks prevent conflicting snapshot evaluation; a global
entry lock prevents concurrent Package 3 entry calls.

## Persistence and recovery

SQLite uses WAL and `synchronous=FULL`. Package 4 stores only coordination state: sessions, event
envelopes, signal/execution lineage, active watch lifecycle, quarantine entries, and processed-ID
claims. Package-owned market, strategy-memory, and account/execution state are not duplicated.
Startup reconciliation is authoritative for account state; ambiguous positions prevent `READY`.

## Failure model

Package 1/2 failure blocks entries but cannot disable Package 3's management API. Package 3
failure, loss lock, reconciliation failure, contract mismatch, invalid integrity, stale data, or
ambiguous symbols fail closed. AI latency/failure stays within Package 2 and never blocks execution
event handling. `EMERGENCY` invokes only Package 3's public emergency method.
