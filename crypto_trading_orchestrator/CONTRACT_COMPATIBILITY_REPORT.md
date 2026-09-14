# Contract Compatibility Report

Result: compatible through explicit owner-side normalization, with exact version and hash pinning.

| Boundary | Finding | Resolution | Business authority |
|---|---|---|---|
| Package 1 → 2 | Market `levels` array; null optional evidence | Package 2 recognizes the producer variant and builds a strategy-internal copy | Package 2 |
| Package 2 → 3 | zero-based attempt number | Package 3 schema accepts 0 | Package 3 validation |
| Package 2 → 3 | `entry_reference` / `trigger_price_if_any` | Package 3 reads the producer vocabulary without mutation | Package 3 risk |
| Package 3 → 4 | immutable `ExecutionReport` wrapper | Package 4 adapter calls its public `to_dict` transport method | Transport only |
| Packaging | Package 3 version was not PEP 440; schema absent from wheel | version `0.3.0.dev0`; schema included as package data | Packaging only |

All packages retain `HM_CRYPTO_V1`. Current schema hashes are recorded in
`INTEGRATION_MANIFEST.json`; Package 1's schema is unchanged. Compatibility is checked on startup,
and unsupported versions, missing schemas, environment mismatch, Binance Demo, Testnet, stale
payloads, or invalid integrity all fail closed.
