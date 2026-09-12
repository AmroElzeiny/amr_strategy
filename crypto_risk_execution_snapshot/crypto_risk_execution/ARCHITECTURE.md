# Architecture

Boundary: **RISK AUTHORITY + EXECUTION AUTHORITY + POSITION SAFETY AUTHORITY**. It is not a market-intelligence, technical-direction or AI authority. The only upstream object is frozen JSON `TradeIntent`; the downstream artifact is `ExecutionReport`.

Flow: validate → freeze identity → reconcile account → hard locks → current exchange rules → risk-by-stop sizing → floor quantity → balance/margin checks → atomic reservation → deterministic order identity → submit or dry-run → reconcile fills → exchange-native protection → managed lifecycle → post-entry penalties → final report.

Adapters isolate exchange JSON. SQLite owns durable signals, reservations, managed orders/positions, locks and append-style audit records. Unknown ownership is fail-closed; account-wide flatten is disabled by default.
