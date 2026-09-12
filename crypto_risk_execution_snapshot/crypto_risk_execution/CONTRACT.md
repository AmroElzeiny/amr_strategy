# Frozen contract — HM_CRYPTO_V1

This package owns a local independent copy of the Prompt 1–3 frozen JSON contract. It imports neither `crypto_market_intel` nor `crypto_strategy_engine`.

`CONTRACT_VERSION=HM_CRYPTO_V1`

`CONTRACT_SCHEMA_SHA256=4e132d807d5fd6f198cde8cd8673794bbe8843dbe8850996a96385a9d8063b97`

Financial prices, quantities, notionals and PnL are converted to Python `Decimal` before authoritative calculations. Canonical identity hashes use sorted compact JSON and SHA-256. UTC is the only accepted clock basis for persisted trading events.
