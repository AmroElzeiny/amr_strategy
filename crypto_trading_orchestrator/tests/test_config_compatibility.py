from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_trading_orchestrator.compatibility import SymbolAdapter
from crypto_trading_orchestrator.config import OrchestratorConfig


def test_execution_defaults_off() -> None:
    config = OrchestratorConfig()
    assert not config.execution_enabled
    assert not config.real_trading_enabled
    assert config.dry_run
    assert not config.execution_permitted


def test_research_and_real_guards() -> None:
    with pytest.raises(ValueError, match="RESEARCH_MODE"):
        replace(OrchestratorConfig(), runtime_mode="RESEARCH", execution_enabled=True).validate()
    with pytest.raises(ValueError, match="REAL_TRADING_GUARD"):
        replace(
            OrchestratorConfig(), trading_env="REAL", execution_enabled=True, real_trading_enabled=False
        ).validate()


def test_testnet_and_binance_demo_rejected() -> None:
    with pytest.raises(ValueError):
        replace(OrchestratorConfig(), trading_env="TESTNET").validate()
    with pytest.raises(ValueError, match="BINANCE_DEMO"):
        replace(OrchestratorConfig(), exchange="BINANCE").validate()
    with pytest.raises(ValueError, match="MUST_BE_UNBOUNDED"):
        replace(OrchestratorConfig(), execution_queue_max=1).validate()


def test_symbol_identity_is_deterministic_and_ambiguity_fails() -> None:
    identity = SymbolAdapter.canonical("btc/usdt", exchange="BYBIT", market_mode="DERIVATIVES")
    assert identity.key == "BYBIT:DERIVATIVES:PERPETUAL:BTCUSDT:USDT"
    with pytest.raises(ValueError):
        SymbolAdapter.canonical("BTC", exchange="BYBIT", market_mode="SPOT")
