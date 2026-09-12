from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from .contracts.models import KeyLevel
from .types import Bar


@dataclass(frozen=True, slots=True)
class Swing:
    index: int
    time: datetime
    price: Decimal
    kind: str
    major: bool


@dataclass(frozen=True, slots=True)
class StructureEvent:
    index: int
    time: datetime
    type: str
    direction: str
    price: Decimal
    reference_price: Decimal | None


def _bps_distance(a: Decimal, b: Decimal) -> Decimal:
    if b == 0:
        return Decimal("999999")
    return abs(a - b) / abs(b) * Decimal("10000")


def detect_swings(bars: list[Bar], window: int = 3, major_window: int | None = None) -> list[Swing]:
    if window < 1:
        raise ValueError("window_must_be_positive")
    major_window = major_window or window * 3
    swings: list[Swing] = []
    for i in range(window, len(bars) - window):
        left = bars[i - window:i]
        right = bars[i + 1:i + 1 + window]
        high = bars[i].high
        low = bars[i].low
        is_high = high > max(x.high for x in left) and high >= max(x.high for x in right)
        is_low = low < min(x.low for x in left) and low <= min(x.low for x in right)
        if is_high:
            swings.append(Swing(i, bars[i].end, high, "HIGH", _is_major_high(bars, i, major_window)))
        if is_low:
            swings.append(Swing(i, bars[i].end, low, "LOW", _is_major_low(bars, i, major_window)))
    return sorted(swings, key=lambda x: (x.index, x.kind))


def _is_major_high(bars: list[Bar], i: int, window: int) -> bool:
    left = bars[max(0, i - window):i]
    right = bars[i + 1:min(len(bars), i + window + 1)]
    return bool(left and right and bars[i].high >= max(x.high for x in left + right))


def _is_major_low(bars: list[Bar], i: int, window: int) -> bool:
    left = bars[max(0, i - window):i]
    right = bars[i + 1:min(len(bars), i + window + 1)]
    return bool(left and right and bars[i].low <= min(x.low for x in left + right))


def classify_swing_progression(swings: list[Swing]) -> list[dict[str, object]]:
    last_high: Decimal | None = None
    last_low: Decimal | None = None
    out: list[dict[str, object]] = []
    for swing in swings:
        label = swing.kind
        if swing.kind == "HIGH":
            if last_high is not None:
                label = "HH" if swing.price > last_high else "LH"
            last_high = swing.price
        else:
            if last_low is not None:
                label = "HL" if swing.price > last_low else "LL"
            last_low = swing.price
        out.append({"index": swing.index, "time": swing.time, "price": swing.price, "kind": swing.kind, "label": label, "major": swing.major})
    return out


def detect_bos_choch(bars: list[Bar], swings: list[Swing]) -> list[StructureEvent]:
    events: list[StructureEvent] = []
    confirmed_highs: list[Swing] = []
    confirmed_lows: list[Swing] = []
    trend = "UNKNOWN"
    swing_by_index: dict[int, list[Swing]] = {}
    for swing in swings:
        swing_by_index.setdefault(swing.index, []).append(swing)
    for i, bar in enumerate(bars):
        for swing in swing_by_index.get(i, []):
            (confirmed_highs if swing.kind == "HIGH" else confirmed_lows).append(swing)
        high_ref = confirmed_highs[-1] if confirmed_highs else None
        low_ref = confirmed_lows[-1] if confirmed_lows else None
        if high_ref and high_ref.index < i and bar.close > high_ref.price:
            event_type = "CHOCH" if trend == "BEAR" else "BOS"
            events.append(StructureEvent(i, bar.end, event_type, "BULL", bar.close, high_ref.price))
            trend = "BULL"
            confirmed_highs = []
        elif low_ref and low_ref.index < i and bar.close < low_ref.price:
            event_type = "CHOCH" if trend == "BULL" else "BOS"
            events.append(StructureEvent(i, bar.end, event_type, "BEAR", bar.close, low_ref.price))
            trend = "BEAR"
            confirmed_lows = []
    return events


def build_key_levels(bars: list[Bar], swings: list[Swing], timeframe: str, tolerance_bps: Decimal = Decimal("10")) -> list[KeyLevel]:
    clusters: list[list[Swing]] = []
    for swing in swings:
        matched = next((cluster for cluster in clusters if _bps_distance(swing.price, sum((x.price for x in cluster), Decimal("0")) / Decimal(len(cluster))) <= tolerance_bps), None)
        if matched is None:
            clusters.append([swing])
        else:
            matched.append(swing)
    levels: list[KeyLevel] = []
    final_close = bars[-1].close if bars else Decimal("0")
    for cluster in clusters:
        price = sum((x.price for x in cluster), Decimal("0")) / Decimal(len(cluster))
        kinds = [x.kind for x in cluster]
        level_type = "RESISTANCE" if kinds.count("HIGH") >= kinds.count("LOW") else "SUPPORT"
        broken = final_close > price if level_type == "RESISTANCE" else final_close < price
        reclaimed = False
        if broken and bars:
            later = [b for b in bars if b.end > cluster[-1].time]
            if level_type == "RESISTANCE":
                reclaimed = any(b.close < price for b in later)
            else:
                reclaimed = any(b.close > price for b in later)
        strength = min(Decimal("1"), Decimal(len(cluster)) / Decimal("4") + (Decimal("0.25") if any(x.major for x in cluster) else Decimal("0")))
        levels.append(KeyLevel(
            price=price,
            type=level_type,
            timeframe=timeframe,
            strength=strength,
            touch_count=len(cluster),
            first_seen=cluster[0].time,
            last_seen=cluster[-1].time,
            broken=broken,
            reclaimed=reclaimed,
        ))
    return sorted(levels, key=lambda x: x.price)


def range_state(bars: list[Bar], lookback: int = 30, compression_ratio: Decimal = Decimal("0.65")) -> dict[str, Decimal | bool | None]:
    rows = bars[-lookback:] if len(bars) >= lookback else bars
    if not rows:
        return {"high": None, "low": None, "midpoint": None, "width_pct": None, "compressed": False}
    high = max(x.high for x in rows)
    low = min(x.low for x in rows)
    mid = (high + low) / Decimal("2")
    width_pct = ((high - low) / mid * Decimal("100")) if mid else None
    first_half = rows[: max(1, len(rows)//2)]
    second_half = rows[max(1, len(rows)//2):]
    first_range = max(x.high for x in first_half) - min(x.low for x in first_half)
    second_range = max(x.high for x in second_half) - min(x.low for x in second_half) if second_half else first_range
    return {"high": high, "low": low, "midpoint": mid, "width_pct": width_pct, "compressed": second_range < first_range * compression_ratio}


def liquidity_events(bars: list[Bar], levels: Iterable[KeyLevel], tolerance_bps: Decimal = Decimal("8"), sweep_tolerance_multiple: Decimal = Decimal("4")) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for level in levels:
        for bar in bars:
            distance_high = _bps_distance(bar.high, level.price)
            distance_low = _bps_distance(bar.low, level.price)
            if level.type == "RESISTANCE" and bar.high > level.price and bar.close < level.price and distance_high <= tolerance_bps * sweep_tolerance_multiple:
                events.append({"type": "LIQUIDITY_SWEEP", "side": "ABOVE", "level": level.price, "time": bar.end, "close": bar.close})
            if level.type == "SUPPORT" and bar.low < level.price and bar.close > level.price and distance_low <= tolerance_bps * sweep_tolerance_multiple:
                events.append({"type": "LIQUIDITY_SWEEP", "side": "BELOW", "level": level.price, "time": bar.end, "close": bar.close})
    return events


def market_structure(
    bars: list[Bar],
    timeframe: str,
    swing_window: int,
    tolerance_bps: Decimal,
    *,
    range_compression_ratio: Decimal = Decimal("0.65"),
    liquidity_sweep_tolerance_multiple: Decimal = Decimal("4"),
    motion_compression_ratio: Decimal = Decimal("0.70"),
    motion_expansion_ratio: Decimal = Decimal("1.30"),
    motion_displacement_range_multiple: Decimal = Decimal("1.5"),
    motion_displacement_body_fraction: Decimal = Decimal("0.60"),
) -> dict[str, object]:
    swings = detect_swings(bars, swing_window)
    progression = classify_swing_progression(swings)
    events = detect_bos_choch(bars, swings)
    levels = build_key_levels(bars, swings, timeframe, tolerance_bps)
    r = range_state(bars, compression_ratio=range_compression_ratio)
    liq = liquidity_events(bars, levels, tolerance_bps, liquidity_sweep_tolerance_multiple)
    major_high = max((s.price for s in swings if s.kind == "HIGH" and s.major), default=None)
    major_low = min((s.price for s in swings if s.kind == "LOW" and s.major), default=None)
    equal_highs = _equal_groups([s for s in swings if s.kind == "HIGH"], tolerance_bps)
    equal_lows = _equal_groups([s for s in swings if s.kind == "LOW"], tolerance_bps)
    context = contextual_levels(bars)
    trendlines = trendline_candidates(swings)
    motion = motion_features(
        bars,
        compression_ratio=motion_compression_ratio,
        expansion_ratio=motion_expansion_ratio,
        displacement_range_multiple=motion_displacement_range_multiple,
        displacement_body_fraction=motion_displacement_body_fraction,
    )
    return {
        "swings": progression,
        "events": [asdict(e) for e in events],
        "major_high": major_high,
        "major_low": major_low,
        "range": r,
        "equal_highs": equal_highs,
        "equal_lows": equal_lows,
        "liquidity_pools": equal_highs + equal_lows,
        "liquidity_events": liq,
        "levels": [x.model_dump() for x in levels],
        "previous_day_high": context["previous_day_high"],
        "previous_day_low": context["previous_day_low"],
        "session_highs_lows": context["session_highs_lows"],
        "higher_timeframe_high": context["higher_timeframe_high"],
        "higher_timeframe_low": context["higher_timeframe_low"],
        "trendline_candidates": trendlines,
        "trendline_breaks": trendline_breaks(bars, trendlines),
        "compression": motion["compression"],
        "expansion": motion["expansion"],
        "displacement": motion["displacement"],
        "pullback": motion["pullback"],
        "acceptance_outside_range": motion["acceptance_outside_range"],
        "acceptance_back_inside_range": motion["acceptance_back_inside_range"],
        "failed_breaks": motion["failed_breaks"],
        "reclaims": motion["reclaims"],
    }


def _equal_groups(swings: list[Swing], tolerance_bps: Decimal) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    used: set[int] = set()
    for i, swing in enumerate(swings):
        if i in used:
            continue
        group = [swing]
        for j in range(i + 1, len(swings)):
            if _bps_distance(swings[j].price, swing.price) <= tolerance_bps:
                group.append(swings[j]); used.add(j)
        if len(group) >= 2:
            avg = sum((x.price for x in group), Decimal("0")) / Decimal(len(group))
            out.append({"price": avg, "count": len(group), "kind": swing.kind, "first_seen": group[0].time, "last_seen": group[-1].time})
    return out



def contextual_levels(bars: list[Bar]) -> dict[str, object]:
    if not bars:
        return {"previous_day_high": None, "previous_day_low": None, "session_highs_lows": {}, "higher_timeframe_high": None, "higher_timeframe_low": None}
    by_day: dict[object, list[Bar]] = {}
    for bar in bars:
        by_day.setdefault(bar.start.date(), []).append(bar)
    days = sorted(by_day)
    previous = by_day[days[-2]] if len(days) >= 2 else []
    prev_high = max((b.high for b in previous), default=None)
    prev_low = min((b.low for b in previous), default=None)
    # UTC crypto sessions are deterministic reference windows, not FX open/close assumptions.
    sessions = {"ASIA_UTC_00_08": (0, 8), "EUROPE_UTC_08_16": (8, 16), "US_UTC_16_24": (16, 24)}
    session_levels: dict[str, dict[str, Decimal | None]] = {}
    current_day = days[-1]
    today_rows = by_day[current_day]
    for name, (start_h, end_h) in sessions.items():
        rows = [b for b in today_rows if start_h <= b.start.hour < end_h]
        session_levels[name] = {"high": max((b.high for b in rows), default=None), "low": min((b.low for b in rows), default=None)}
    return {
        "previous_day_high": prev_high,
        "previous_day_low": prev_low,
        "session_highs_lows": session_levels,
        "higher_timeframe_high": max((b.high for b in bars), default=None),
        "higher_timeframe_low": min((b.low for b in bars), default=None),
    }


def trendline_candidates(swings: list[Swing]) -> list[dict[str, object]]:
    lines: list[dict[str, object]] = []
    for kind, direction in (("LOW", "SUPPORT"), ("HIGH", "RESISTANCE")):
        points = [s for s in swings if s.kind == kind]
        if len(points) < 2:
            continue
        a, b = points[-2], points[-1]
        dt = Decimal(str((b.time - a.time).total_seconds()))
        if dt <= 0:
            continue
        slope = (b.price - a.price) / dt
        intercept = a.price - slope * Decimal(str(a.time.timestamp()))
        lines.append({"type": direction, "slope_per_second": slope, "intercept": intercept, "anchor1": a.time, "anchor2": b.time, "touch_count": 2})
    return lines


def trendline_breaks(bars: list[Bar], lines: list[dict[str, object]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    if len(bars) < 2:
        return out
    prev, cur = bars[-2], bars[-1]
    for line in lines:
        slope = Decimal(str(line["slope_per_second"]))
        intercept = Decimal(str(line["intercept"]))
        prev_line = slope * Decimal(str(prev.end.timestamp())) + intercept
        cur_line = slope * Decimal(str(cur.end.timestamp())) + intercept
        if line["type"] == "RESISTANCE" and prev.close <= prev_line and cur.close > cur_line:
            out.append({"direction": "BULL", "line_type": line["type"], "price": cur.close, "reference": cur_line, "time": cur.end})
        if line["type"] == "SUPPORT" and prev.close >= prev_line and cur.close < cur_line:
            out.append({"direction": "BEAR", "line_type": line["type"], "price": cur.close, "reference": cur_line, "time": cur.end})
    return out


def motion_features(
    bars: list[Bar],
    lookback: int = 20,
    compression_ratio: Decimal = Decimal("0.70"),
    expansion_ratio: Decimal = Decimal("1.30"),
    displacement_range_multiple: Decimal = Decimal("1.5"),
    displacement_body_fraction: Decimal = Decimal("0.60"),
) -> dict[str, object]:
    rows = bars[-lookback:]
    if len(rows) < 4:
        return {"compression": False, "expansion": False, "displacement": [], "pullback": False, "acceptance_outside_range": False, "acceptance_back_inside_range": False, "failed_breaks": [], "reclaims": []}
    ranges = [b.high - b.low for b in rows]
    half = len(ranges) // 2
    first_avg = sum(ranges[:half], Decimal("0")) / Decimal(max(1, half))
    second_avg = sum(ranges[half:], Decimal("0")) / Decimal(max(1, len(ranges)-half))
    compression = second_avg < first_avg * compression_ratio if first_avg > 0 else False
    expansion = second_avg > first_avg * expansion_ratio if first_avg > 0 else False
    median = sorted(ranges)[len(ranges)//2]
    displacement = []
    for i, b in enumerate(rows):
        width = b.high - b.low
        body = abs(b.close - b.open)
        body_frac = body / width if width > 0 else Decimal("0")
        if median > 0 and width >= median * displacement_range_multiple and body_frac >= displacement_body_fraction:
            displacement.append({"index": len(bars)-len(rows)+i, "direction": "BULL" if b.close > b.open else "BEAR", "range_ratio": width/median, "body_fraction": body_frac})
    recent_high = max(b.high for b in rows[:-2]); recent_low = min(b.low for b in rows[:-2])
    outside_up = [b for b in rows[-2:] if b.close > recent_high]
    outside_down = [b for b in rows[-2:] if b.close < recent_low]
    acceptance_outside = len(outside_up) == 2 or len(outside_down) == 2
    back_inside = (rows[-2].close > recent_high and rows[-1].close <= recent_high) or (rows[-2].close < recent_low and rows[-1].close >= recent_low)
    failed: list[dict[str, object]] = []
    reclaims: list[dict[str, object]] = []
    if back_inside:
        direction = "BULL_FAIL" if rows[-2].close > recent_high else "BEAR_FAIL"
        failed.append({"type": direction, "time": rows[-1].end})
        reclaims.append({"time": rows[-1].end, "level": recent_high if direction == "BULL_FAIL" else recent_low})
    direction = Decimal("1") if rows[-1].close > rows[-4].close else Decimal("-1")
    pullback = (direction > 0 and rows[-1].close < rows[-2].close and rows[-1].low > recent_low) or (direction < 0 and rows[-1].close > rows[-2].close and rows[-1].high < recent_high)
    return {"compression": compression, "expansion": expansion, "displacement": displacement, "pullback": pullback, "acceptance_outside_range": acceptance_outside, "acceptance_back_inside_range": back_inside, "failed_breaks": failed, "reclaims": reclaims}
