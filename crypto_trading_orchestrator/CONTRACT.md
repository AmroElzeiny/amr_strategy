# Integration Contract

The shared contract identifier is `HM_CRYPTO_V1`; equal identifiers do not imply byte-identical
schemas. Runtime discovery records the exact schema and source build SHA-256 values for every
installed package and refuses unpinned versions.

Package 1 produces immutable `MarketSnapshot`. Package 2 validates and internally normalizes the
Package 1 producer variant, then emits an integrity-hashed `TradeIntent`. Package 4 verifies the
intent's contract, environment, instrument lineage, TTL, and integrity without editing it. Only an
`ENTER` with `order_intent=OPEN` may be passed to Package 3. Package 3 independently validates,
sizes, locks, reserves, reconciles, and returns an integrity-hashed `ExecutionReport`.

Feedback is accepted once per execution only when the report is reconciled, closed, has valid
integrity, and matches the original exchange/environment/market-mode/symbol lineage. Invalid or
unknown reports are quarantined. Decimal business fields stay string-encoded through transport;
timestamps are UTC `Z` values.
