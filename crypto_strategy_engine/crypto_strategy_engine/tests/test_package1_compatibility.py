from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from crypto_strategy_engine.compatibility import normalize_market_snapshot


def test_package1_list_levels_and_null_optionals_are_normalized_without_mutation() -> None:
    fixture = Path(__file__).parent / "fixtures" / "healthy_continuation_long.json"
    snapshot = json.loads(fixture.read_text(encoding="utf-8"))
    snapshot["levels"] = [
        {"price": "99", "type": "SUPPORT", "strength": "0.8"},
        {"price": "103", "type": "RESISTANCE", "strength": "0.7"},
    ]
    snapshot["derivatives"] = None
    before = deepcopy(snapshot)
    normalized = normalize_market_snapshot(snapshot)
    assert snapshot == before
    assert normalized["levels"]["raw_levels"] == snapshot["levels"]
    assert normalized["levels"]["entry_reference"] == snapshot["ticker"]["last_price"]
    assert normalized["derivatives"]["availability"] == "UNAVAILABLE"
