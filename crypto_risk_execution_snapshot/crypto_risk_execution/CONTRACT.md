# Frozen contract — HM_CRYPTO_V1

This package owns a local independent copy of the Prompt 1–3 frozen JSON contract. It imports neither `crypto_market_intel` nor `crypto_strategy_engine`.

`CONTRACT_VERSION=HM_CRYPTO_V1`

`CONTRACT_SCHEMA_SHA256=7dc9bf3c2753d77c08345d8d5121b4ea864b42109373c070e0214771e051d92b`

Financial prices, quantities, notionals and PnL are converted to Python `Decimal` before authoritative calculations. Canonical identity hashes use sorted compact JSON and SHA-256. UTC is the only accepted clock basis for persisted trading events.
