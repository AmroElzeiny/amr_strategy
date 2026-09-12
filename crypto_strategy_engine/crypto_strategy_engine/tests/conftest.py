from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path

import pytest

from crypto_strategy_engine.config import StrategyConfig

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def event_time(snapshot: dict) -> datetime:
    return datetime.fromisoformat(snapshot["event_time_utc"].replace("Z", "+00:00"))


@pytest.fixture
def deterministic_config(tmp_path: Path) -> StrategyConfig:
    return replace(
        StrategyConfig(),
        ai_enabled=False,
        ai_required_for_enter=False,
        trade_memory_enabled=False,
        trade_memory_db=str(tmp_path / "memory.db"),
        decision_log_dir=str(tmp_path / "decisions"),
        research_dir=str(tmp_path / "research"),
        quarantine_dir=str(tmp_path / "quarantine"),
        max_snapshot_age_ms=10**9,
    )
