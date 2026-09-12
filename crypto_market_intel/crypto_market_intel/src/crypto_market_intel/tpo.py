from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .types import Bar
from .volume import bucket_price


def tpo_profile(bars: list[Bar], tick_size: Decimal, ticks_per_bin: int = 1, value_area_pct: Decimal = Decimal("0.70")) -> dict[str, object]:
    counts: dict[Decimal, int] = defaultdict(int)
    for bar in bars:
        p = bucket_price(bar.low, tick_size, ticks_per_bin)
        step = tick_size * Decimal(ticks_per_bin)
        guard = 0
        while p <= bar.high and guard < 100_000:
            counts[p] += 1
            p += step
            guard += 1
    if not counts:
        return {"poc": None, "vah": None, "val": None, "single_prints": [], "distribution": []}
    ordered = sorted(counts.items())
    poc = max(ordered, key=lambda x: (x[1], -ordered.index(x)))[0]
    total = sum(counts.values())
    target = Decimal(total) * value_area_pct
    ranked = sorted(ordered, key=lambda x: (x[1], -x[0]), reverse=True)
    selected: list[Decimal] = []
    acc = Decimal("0")
    for price, count in ranked:
        selected.append(price); acc += Decimal(count)
        if acc >= target:
            break
    single = [p for p, count in ordered if count == 1]
    return {
        "poc": poc,
        "vah": max(selected),
        "val": min(selected),
        "single_prints": single,
        "distribution": ordered,
        "balance_distribution": (max(counts.values()) / max(1, len(bars))),
        "developing_value": {"poc": poc, "vah": max(selected), "val": min(selected)},
    }


def tpo_acceptance_rejection(bars: list[Bar], val: Decimal | None, vah: Decimal | None, min_accept_closes: int = 2) -> dict[str, object]:
    if val is None or vah is None or not bars:
        return {"acceptance": "UNKNOWN", "rejection_events": []}
    closes_above = sum(1 for b in bars[-min_accept_closes:] if b.close > vah)
    closes_below = sum(1 for b in bars[-min_accept_closes:] if b.close < val)
    closes_inside = sum(1 for b in bars[-min_accept_closes:] if val <= b.close <= vah)
    if closes_above == min_accept_closes:
        acceptance = "ABOVE_VALUE"
    elif closes_below == min_accept_closes:
        acceptance = "BELOW_VALUE"
    elif closes_inside == min_accept_closes:
        acceptance = "IN_VALUE"
    else:
        acceptance = "TRANSITION"
    rejection: list[dict[str, object]] = []
    for b in bars[-10:]:
        if b.high > vah and b.close <= vah:
            rejection.append({"side":"ABOVE","time":b.end,"extreme":b.high,"close":b.close})
        if b.low < val and b.close >= val:
            rejection.append({"side":"BELOW","time":b.end,"extreme":b.low,"close":b.close})
    return {"acceptance": acceptance, "rejection_events": rejection}
