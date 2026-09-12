from __future__ import annotations

from decimal import Decimal

from crypto_market_intel.bars import build_trade_bars
from crypto_market_intel.volume import delta_per_bar, footprint, volume_profile, vwap
from conftest import trade


def test_footprint_uses_actual_taker_side_and_manual_delta() -> None:
    trades = [trade(1000,"100","2","Buy"), trade(1001,"100","1","Sell"), trade(1002,"101","3","Buy"), trade(1003,"101","4","Sell")]
    result = footprint(trades, Decimal("1"))
    assert result["aggressive_buy_volume"] == Decimal("5")
    assert result["aggressive_sell_volume"] == Decimal("5")
    assert result["delta"] == Decimal("0")
    assert result["cumulative_delta"][-1][1] == Decimal("0")


def test_volume_profile_poc_vah_val_manual_fixture() -> None:
    trades = [trade(1000,"100","5","Buy"), trade(1001,"101","10","Sell"), trade(1002,"102","5","Buy")]
    profile = volume_profile(trades, Decimal("1"), value_area_pct=Decimal("0.70"))
    assert profile.poc == Decimal("101")
    assert profile.val == Decimal("100")
    assert profile.vah == Decimal("101")
    assert profile.total_volume == Decimal("20")


def test_microbars_and_delta_per_bar_from_trades() -> None:
    trades = [trade(1000,"100","2","Buy"), trade(1001,"101","1","Sell"), trade(1006,"102","3","Buy")]
    bars = build_trade_bars(trades, 5)
    assert len(bars) == 2
    assert bars[0].open == Decimal("100") and bars[0].close == Decimal("101")
    assert bars[0].delta == Decimal("1")
    rows = delta_per_bar(trades, bars)
    assert rows[0]["delta"] == Decimal("1")
    assert vwap(trades) == Decimal("101.1666666666666666666666667")
