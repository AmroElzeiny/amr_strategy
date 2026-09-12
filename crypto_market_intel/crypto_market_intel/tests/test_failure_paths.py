from __future__ import annotations

import pytest

from crypto_market_intel.config import Settings


def test_no_testnet_routing(monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_VERSION","HM_CRYPTO_V1")
    monkeypatch.setenv("TRADING_ENV","DEMO")
    settings = Settings.from_env()
    values = [settings.bybit_real_rest_base, settings.bybit_demo_rest_base, settings.bybit_public_ws_root, settings.bybit_demo_private_ws_root]
    assert all("testnet" not in x.lower() for x in values)


def test_contract_version_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_VERSION","WRONG")
    with pytest.raises(ValueError, match="CONTRACT_VERSION"):
        Settings.from_env()


def test_binance_is_contract_only_not_live_adapter(monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_VERSION", "HM_CRYPTO_V1")
    monkeypatch.setenv("EXCHANGE", "BINANCE")
    with pytest.raises(ValueError, match="contract-only"):
        Settings.from_env()
