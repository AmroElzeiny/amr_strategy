from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crypto_market_intel.contracts.models import CONTRACT_VERSION, ExecutionReport, MarketSnapshot, TradeIntent

ROOT = Path(__file__).parents[1]
MODELS = (MarketSnapshot, TradeIntent, ExecutionReport)
defs: dict[str, Any] = {}
for model in MODELS:
    schema = model.model_json_schema(ref_template="#/$defs/{model}")
    nested = schema.pop("$defs", {})
    for name, value in nested.items():
        if name in defs and defs[name] != value:
            raise RuntimeError(f"schema definition collision: {name}")
        defs[name] = value
    schema.pop("$schema", None)
    defs[model.__name__] = schema
combined = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "HM_CRYPTO_V1 Contracts",
    "contract_version": CONTRACT_VERSION,
    "$defs": dict(sorted(defs.items())),
    "oneOf": [{"$ref": f"#/$defs/{model.__name__}"} for model in MODELS],
}
text = json.dumps(combined, indent=2, sort_keys=True) + "\n"
for target in (
    ROOT / "src/crypto_market_intel/contracts/schema.json",
    ROOT / "contracts/schema.json",
):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
print("build_schema: PASS")
