from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal

from .types import Bar


@dataclass(frozen=True, slots=True)
class Zone:
    kind: str
    direction: str
    lower: Decimal
    upper: Decimal
    created_index: int
    midpoint: Decimal
    mitigated: bool
    invalidated: bool


def fair_value_gaps(bars: list[Bar], min_gap: Decimal = Decimal("0")) -> list[Zone]:
    """Three-bar FVG: bullish when bar[i-1].high < bar[i+1].low; bearish inverse.

    The middle candle is the displacement candle. Later penetration tracks mitigation;
    a close fully through the far edge invalidates the gap.
    """
    out: list[Zone] = []
    for i in range(1, len(bars) - 1):
        older, middle, newer = bars[i - 1], bars[i], bars[i + 1]
        if newer.low - older.high >= min_gap and newer.low > older.high:
            lower, upper, direction = older.high, newer.low, "BULL"
        elif older.low - newer.high >= min_gap and older.low > newer.high:
            lower, upper, direction = newer.high, older.low, "BEAR"
        else:
            continue
        later = bars[i + 2:]
        if direction == "BULL":
            mitigated = any(b.low <= (lower + upper) / Decimal("2") for b in later)
            invalidated = any(b.close < lower for b in later)
        else:
            mitigated = any(b.high >= (lower + upper) / Decimal("2") for b in later)
            invalidated = any(b.close > upper for b in later)
        out.append(Zone("FVG", direction, lower, upper, i, (lower + upper) / Decimal("2"), mitigated, invalidated))
    return out


def candle_imbalances(bars: list[Bar], body_fraction_min: Decimal = Decimal("0.65")) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for i, bar in enumerate(bars):
        width = bar.high - bar.low
        if width <= 0:
            continue
        body = abs(bar.close - bar.open)
        frac = body / width
        if frac >= body_fraction_min:
            out.append({"index": i, "direction": "BULL" if bar.close > bar.open else "BEAR", "body_fraction": frac, "low": min(bar.open, bar.close), "high": max(bar.open, bar.close)})
    return out


def order_blocks(bars: list[Bar], displacement_multiple: Decimal = Decimal("1.5"), lookback: int = 10) -> list[Zone]:
    """Last opposite candle immediately before a displacement/BOS-like close.

    Displacement is normalized against median recent true candle range. This is a testable
    location definition, not a claim that every zone is institutionally originated.
    """
    out: list[Zone] = []
    for i in range(2, len(bars)):
        history = bars[max(0, i - lookback):i]
        ranges = sorted((b.high - b.low for b in history if b.high > b.low))
        if not ranges:
            continue
        median = ranges[len(ranges) // 2]
        bar = bars[i]
        if median <= 0 or bar.high - bar.low < median * displacement_multiple:
            continue
        bull = bar.close > bar.open and bar.close > max(x.high for x in history)
        bear = bar.close < bar.open and bar.close < min(x.low for x in history)
        if not bull and not bear:
            continue
        prior = next((bars[j] for j in range(i - 1, max(-1, i - 5), -1) if (bars[j].close < bars[j].open) == bull), None)
        if prior is None:
            continue
        lower, upper = min(prior.open, prior.close), max(prior.open, prior.close)
        later = bars[i + 1:]
        invalidated = any(b.close < prior.low for b in later) if bull else any(b.close > prior.high for b in later)
        mitigated = any(b.low <= upper and b.high >= lower for b in later)
        out.append(Zone("ORDER_BLOCK", "BULL" if bull else "BEAR", lower, upper, i - 1, (lower + upper) / Decimal("2"), mitigated, invalidated))
    return out


def breaker_zones(order_block_zones: list[Zone]) -> list[Zone]:
    return [Zone("BREAKER_RECLAIM", "BEAR" if z.direction == "BULL" else "BULL", z.lower, z.upper, z.created_index, z.midpoint, z.mitigated, False) for z in order_block_zones if z.invalidated]


def fibonacci_locations(origin: Decimal, end: Decimal) -> dict[str, Decimal]:
    delta = end - origin
    return {
        "retracement_0_382": end - delta * Decimal("0.382"),
        "retracement_0_5": end - delta * Decimal("0.5"),
        "retracement_0_618": end - delta * Decimal("0.618"),
        "retracement_0_705": end - delta * Decimal("0.705"),
        "extension_1_272": origin + delta * Decimal("1.272"),
        "extension_1_618": origin + delta * Decimal("1.618"),
        "equilibrium_50": (origin + end) / Decimal("2"),
    }


def value_locations(
    bars: list[Bar],
    *,
    min_fvg_gap: Decimal = Decimal("0"),
    imbalance_body_fraction_min: Decimal = Decimal("0.65"),
    order_block_displacement_multiple: Decimal = Decimal("1.5"),
    order_block_lookback: int = 10,
) -> dict[str, object]:
    fvgs = fair_value_gaps(bars, min_fvg_gap)
    obs = order_blocks(bars, order_block_displacement_multiple, order_block_lookback)
    impulse = None
    if len(bars) >= 2:
        ranges = [(i, b.high - b.low) for i, b in enumerate(bars)]
        impulse_idx = max(ranges, key=lambda x: x[1])[0]
        impulse = {"index": impulse_idx, "origin": bars[impulse_idx].open, "end": bars[impulse_idx].close}
    fib = fibonacci_locations(impulse["origin"], impulse["end"]) if impulse else {}
    return {
        "fair_value_gaps": [asdict(z) for z in fvgs],
        "imbalances": candle_imbalances(bars, imbalance_body_fraction_min),
        "order_blocks": [asdict(z) for z in obs],
        "breaker_reclaim_zones": [asdict(z) for z in breaker_zones(obs)],
        "impulse_origin": impulse,
        "breakout_origin": impulse,
        "fibonacci": fib,
        "retest_zones": [asdict(z) for z in fvgs + obs if not z.invalidated],
    }
