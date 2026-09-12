from __future__ import annotations

from decimal import Decimal

from .contracts.models import RegimeType
from .types import Bar


def _bar_overlap(a: Bar, b: Bar) -> Decimal:
    overlap = max(Decimal("0"), min(a.high, b.high) - max(a.low, b.low))
    span = max(a.high, b.high) - min(a.low, b.low)
    return overlap / span if span > 0 else Decimal("1")


def classify_regime(
    bars: list[Bar],
    structure: dict[str, object] | None = None,
    value_migration: Decimal | None = None,
    directional_delta: Decimal | None = None,
    breakout_follow_through: Decimal | None = None,
    return_to_prior_range: bool = False,
    overlap_balance_threshold: Decimal = Decimal("0.60"),
    trend_progression_threshold: Decimal = Decimal("0.66"),
) -> dict[str, object]:
    """Deterministic regime classifier using price, structure, value and orderflow.

    Volatility/range expansion is a secondary normalizer. It cannot by itself create a
    trend state. Price overlap, swing-like bar progression, pullback/failed-break state,
    value migration, directional delta and breakout follow-through are combined.
    """
    if len(bars) < 6:
        return {"type": RegimeType.UNKNOWN, "confidence": Decimal("0"), "metrics": {"reason": "insufficient_bars"}}
    recent = bars[-20:]
    overlaps = [_bar_overlap(recent[i - 1], recent[i]) for i in range(1, len(recent))]
    avg_overlap = sum(overlaps, Decimal("0")) / Decimal(len(overlaps))
    up = sum(1 for i in range(1, len(recent)) if recent[i].high > recent[i - 1].high and recent[i].low >= recent[i - 1].low)
    down = sum(1 for i in range(1, len(recent)) if recent[i].low < recent[i - 1].low and recent[i].high <= recent[i - 1].high)
    progression = Decimal(max(up, down)) / Decimal(len(recent) - 1)
    ranges = [b.high - b.low for b in recent]
    split = len(ranges) // 2
    first = sum(ranges[:split], Decimal("0")) / Decimal(split)
    second = sum(ranges[split:], Decimal("0")) / Decimal(len(ranges) - split)
    expansion = second / first if first > 0 else Decimal("1")
    net_move = recent[-1].close - recent[0].close
    price_direction = Decimal("1") if net_move > 0 else Decimal("-1") if net_move < 0 else Decimal("0")
    delta_alignment = None if directional_delta is None or price_direction == 0 else directional_delta * price_direction >= 0
    value_alignment = None if value_migration is None or price_direction == 0 else value_migration * price_direction >= 0
    structure = structure or {}
    structure_expansion = bool(structure.get("expansion"))
    pullback = bool(structure.get("pullback"))
    failed_breaks = structure.get("failed_breaks")
    failed_break = return_to_prior_range or (isinstance(failed_breaks, list) and bool(failed_breaks))
    displacement = structure.get("displacement")
    impulse_strength = Decimal(len(displacement)) / Decimal(max(1, len(recent))) if isinstance(displacement, list) else Decimal("0")
    contradictory_flow = delta_alignment is False and value_alignment is False

    if failed_break and (breakout_follow_through is None or breakout_follow_through < Decimal("0.50")):
        regime = RegimeType.FAILED_BREAKOUT
        confidence = Decimal("0.85")
    elif contradictory_flow and progression >= Decimal("0.35"):
        regime = RegimeType.REVERSAL_RISK
        confidence = Decimal("0.72")
    elif avg_overlap >= overlap_balance_threshold and progression < trend_progression_threshold:
        regime = RegimeType.BALANCE if expansion <= Decimal("1.15") else RegimeType.RANGE
        confidence = min(Decimal("1"), avg_overlap)
    elif pullback and progression >= Decimal("0.45") and expansion <= Decimal("1.05"):
        regime = RegimeType.HEALTHY_PULLBACK
        confidence = min(Decimal("0.85"), Decimal("0.55") + progression * Decimal("0.25"))
    elif progression >= trend_progression_threshold and (expansion >= Decimal("0.85") or structure_expansion):
        flow_bonus = Decimal("0.08") if delta_alignment is True else Decimal("0")
        value_bonus = Decimal("0.07") if value_alignment is True else Decimal("0")
        follow_bonus = (min(breakout_follow_through, Decimal("1")) * Decimal("0.08")) if breakout_follow_through is not None else Decimal("0")
        confidence = min(Decimal("1"), progression * Decimal("0.62") + min(expansion, Decimal("2")) / Decimal("2") * Decimal("0.15") + impulse_strength + flow_bonus + value_bonus + follow_bonus)
        regime = RegimeType.TREND_EXPANSION
    elif directional_delta is not None and value_migration is not None and directional_delta * value_migration < 0:
        regime = RegimeType.REVERSAL_RISK
        confidence = Decimal("0.65")
    else:
        regime = RegimeType.RANGE
        confidence = Decimal("0.50")
    return {
        "type": regime,
        "confidence": confidence,
        "metrics": {
            "average_overlap": avg_overlap,
            "swing_progression": progression,
            "range_expansion_ratio": expansion,
            "extension_decay": max(Decimal("0"), Decimal("1") - expansion),
            "impulse_strength": impulse_strength,
            "pullback": pullback,
            "value_migration": value_migration,
            "value_alignment": value_alignment,
            "directional_delta": directional_delta,
            "delta_alignment": delta_alignment,
            "breakout_follow_through": breakout_follow_through,
            "returned_to_prior_range": failed_break,
        },
    }
