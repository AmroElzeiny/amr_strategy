from __future__ import annotations

from decimal import Decimal

from crypto_market_intel.ict import fair_value_gaps, fibonacci_locations, order_blocks
from crypto_market_intel.structure import detect_swings, market_structure
from conftest import bar


def test_fvg_definition_and_fibonacci() -> None:
    bars = [bar(1000,"100","101","99","100"), bar(1060,"100","105","100","104"), bar(1120,"103","106","102","105"), bar(1180,"104","107","103","106")]
    gaps = fair_value_gaps(bars)
    assert gaps and gaps[0].direction == "BULL"
    assert gaps[0].lower == Decimal("101") and gaps[0].upper == Decimal("102")
    fib = fibonacci_locations(Decimal("100"), Decimal("110"))
    assert fib["equilibrium_50"] == Decimal("105")
    assert fib["extension_1_618"] == Decimal("116.180")


def test_structure_contains_required_context_fields() -> None:
    bars = [
        bar(1000,"100","101","99","100"), bar(1060,"100","103","99.5","102"), bar(1120,"102","102.5","100","101"),
        bar(1180,"101","104","100.5","103"), bar(1240,"103","103.5","101","102"), bar(1300,"102","105","101.5","104"),
        bar(1360,"104","104.5","102","103"), bar(1420,"103","106","102.5","105"), bar(1480,"105","105.5","103","104"),
    ]
    result = market_structure(bars, "5m", 1, Decimal("10"))
    for key in ["swings","events","range","levels","trendline_candidates","compression","expansion","displacement","pullback","liquidity_pools","failed_breaks","reclaims"]:
        assert key in result
