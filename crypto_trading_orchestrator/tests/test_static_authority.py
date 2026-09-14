from __future__ import annotations

import json
import re
from pathlib import Path

from crypto_trading_orchestrator.config import OrchestratorConfig
from crypto_trading_orchestrator.discovery import discover_all

PACKAGE = Path(__file__).parents[1]
SOURCE = PACKAGE / "src" / "crypto_trading_orchestrator"


def _source_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in SOURCE.rglob("*.py"))


def test_no_direct_exchange_or_ai_clients() -> None:
    text = _source_text()
    forbidden_imports = (
        r"(?:from|import)\s+(?:requests|httpx|websockets?)\b",
        r"(?:from|import)\s+crypto_risk_execution\.exchanges\b",
        r"(?:from|import)\s+(?:openai|anthropic)\b",
    )
    assert not any(re.search(pattern, text) for pattern in forbidden_imports)


def test_no_technical_analysis_or_risk_business_logic() -> None:
    text = _source_text().lower()
    forbidden = (
        "calculate_position_size",
        "compute_leverage",
        "relative_strength_index",
        "moving_average_convergence",
        "bollinger_band",
        "risk_per_trade *",
    )
    assert not any(value in text for value in forbidden)
    callers = {
        path.relative_to(SOURCE).as_posix()
        for path in SOURCE.rglob("*.py")
        if "execute_trade_intent" in path.read_text(encoding="utf-8")
    }
    assert callers == {"adapters/risk_execution.py"}


def test_no_testnet_endpoint_or_secret_access() -> None:
    text = _source_text()
    assert "api-testnet" not in text.lower()
    assert "testnet." not in text.lower()
    assert not re.search(r"os\.(?:getenv|environ\[).*?(?:API_KEY|SECRET|TOKEN|PASSWORD)", text)


def test_pinned_real_packages_match_release_baseline() -> None:
    baseline = json.loads((PACKAGE / "PACKAGE_BASELINE.json").read_text(encoding="utf-8"))
    repository = PACKAGE.parent
    local_paths = {
        "MARKET_INTEL_PACKAGE_PATH": str(repository / "crypto_market_intel" / "crypto_market_intel"),
        "STRATEGY_PACKAGE_PATH": str(repository / "crypto_strategy_engine" / "crypto_strategy_engine"),
        "RISK_EXECUTION_PACKAGE_PATH": str(
            repository / "crypto_risk_execution_snapshot" / "crypto_risk_execution"
        ),
    }
    config = OrchestratorConfig.from_env(
        local_paths if all(Path(value).is_dir() for value in local_paths.values()) else {}
    )
    _, identities = discover_all(config)
    for role, identity in identities.items():
        assert identity.version == baseline[role]["version"]
        assert identity.schema_hash == baseline[role]["schema_hash"]
        assert identity.build_hash == baseline[role]["build_hash"]
