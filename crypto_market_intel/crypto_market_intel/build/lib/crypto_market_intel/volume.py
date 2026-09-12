from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
from typing import Iterable

from .types import Bar, Trade


@dataclass(frozen=True, slots=True)
class VolumeProfile:
    poc: Decimal | None
    vah: Decimal | None
    val: Decimal | None
    value_area_pct: Decimal
    total_volume: Decimal
    bins: tuple[tuple[Decimal, Decimal], ...]
    hvn: tuple[Decimal, ...]
    lvn: tuple[Decimal, ...]


def bucket_price(price: Decimal, tick_size: Decimal, ticks_per_bin: int = 1) -> Decimal:
    if tick_size <= 0 or ticks_per_bin <= 0:
        raise ValueError("invalid_profile_bin_size")
    step = tick_size * Decimal(ticks_per_bin)
    return (price / step).to_integral_value(rounding=ROUND_FLOOR) * step


def volume_profile(trades: Iterable[Trade], tick_size: Decimal, ticks_per_bin: int = 1, value_area_pct: Decimal = Decimal("0.70"), hvn_quantile: Decimal = Decimal("0.80"), lvn_quantile: Decimal = Decimal("0.20")) -> VolumeProfile:
    bins: dict[Decimal, Decimal] = defaultdict(lambda: Decimal("0"))
    for trade in trades:
        bins[bucket_price(trade.price, tick_size, ticks_per_bin)] += trade.qty
    if not bins:
        return VolumeProfile(None, None, None, value_area_pct, Decimal("0"), (), (), ())
    ordered = sorted(bins.items())
    total = sum((v for _, v in ordered), Decimal("0"))
    poc_idx = max(range(len(ordered)), key=lambda i: (ordered[i][1], -i))
    target = total * value_area_pct
    included = {poc_idx}
    current = ordered[poc_idx][1]
    left, right = poc_idx - 1, poc_idx + 1
    while current < target and (left >= 0 or right < len(ordered)):
        lv = ordered[left][1] if left >= 0 else Decimal("-1")
        rv = ordered[right][1] if right < len(ordered) else Decimal("-1")
        if rv > lv:
            included.add(right); current += rv; right += 1
        else:
            included.add(left); current += lv; left -= 1
    value_prices = [ordered[i][0] for i in included]
    volumes = sorted(v for _, v in ordered)
    def q(frac: Decimal) -> Decimal:
        idx = min(len(volumes) - 1, max(0, int((Decimal(len(volumes) - 1) * frac).to_integral_value(rounding=ROUND_FLOOR))))
        return volumes[idx]
    hvn_cut, lvn_cut = q(hvn_quantile), q(lvn_quantile)
    return VolumeProfile(
        poc=ordered[poc_idx][0], vah=max(value_prices), val=min(value_prices), value_area_pct=value_area_pct,
        total_volume=total, bins=tuple(ordered),
        hvn=tuple(p for p, v in ordered if v >= hvn_cut),
        lvn=tuple(p for p, v in ordered if v <= lvn_cut),
    )


def footprint(trades: Iterable[Trade], tick_size: Decimal, ticks_per_bucket: int = 1, imbalance_ratio: Decimal = Decimal("3"), stacked_levels: int = 3) -> dict[str, object]:
    rows = list(trades)
    buckets: dict[Decimal, dict[str, Decimal]] = defaultdict(lambda: {"buy": Decimal("0"), "sell": Decimal("0")})
    buy = sell = Decimal("0")
    first_time: datetime | None = None
    last_time: datetime | None = None
    for trade in rows:
        p = bucket_price(trade.price, tick_size, ticks_per_bucket)
        if trade.taker_side == "Buy":
            buy += trade.qty; buckets[p]["buy"] += trade.qty
        elif trade.taker_side == "Sell":
            sell += trade.qty; buckets[p]["sell"] += trade.qty
        else:
            raise ValueError(f"unknown_taker_side:{trade.taker_side}")
        first_time = trade.time if first_time is None else min(first_time, trade.time)
        last_time = trade.time if last_time is None else max(last_time, trade.time)
    total_delta = buy - sell
    cumulative: list[tuple[datetime, Decimal]] = []
    running = Decimal("0")
    for trade in sorted(rows, key=lambda x: x.time):
        running += trade.signed_qty
        cumulative.append((trade.time, running))
    duration = Decimal(str(max((last_time - first_time).total_seconds(), 0.001))) if first_time and last_time else Decimal("0")
    velocity = Decimal(len(rows)) / duration if duration > 0 else Decimal("0")
    per_price = []
    imbalances = []
    for price in sorted(buckets):
        b, s = buckets[price]["buy"], buckets[price]["sell"]
        delta = b - s
        ratio = (b / s if s > 0 else None) if b >= s else (s / b if b > 0 else None)
        side = "BUY" if b > s else "SELL" if s > b else "BALANCED"
        row = {"price": price, "buy": b, "sell": s, "delta": delta, "dominant_side": side, "imbalance_ratio": ratio}
        per_price.append(row)
        if ratio is not None and ratio >= imbalance_ratio:
            imbalances.append(row)
    stacked: list[dict[str, object]] = []
    streak: list[dict[str, object]] = []
    last_side = None
    for row in imbalances:
        side = row["dominant_side"]
        if last_side == side:
            streak.append(row)
        else:
            if len(streak) >= stacked_levels:
                stacked.append({"side": last_side, "levels": streak.copy()})
            streak = [row]
        last_side = side
    if len(streak) >= stacked_levels:
        stacked.append({"side": last_side, "levels": streak.copy()})
    return {
        "aggressive_buy_volume": buy,
        "aggressive_sell_volume": sell,
        "delta": total_delta,
        "cumulative_delta": cumulative,
        "delta_per_price_bucket": per_price,
        "buy_sell_imbalance": imbalances,
        "stacked_imbalance": stacked,
        "trade_velocity_per_sec": velocity,
    }


def delta_per_bar(trades: list[Trade], bars: list[Bar]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for bar in bars:
        rows = [t for t in trades if bar.start <= t.time < bar.end]
        buy = sum((t.qty for t in rows if t.taker_side == "Buy"), Decimal("0"))
        sell = sum((t.qty for t in rows if t.taker_side == "Sell"), Decimal("0"))
        out.append({"start": bar.start, "end": bar.end, "buy": buy, "sell": sell, "delta": buy - sell})
    return out


def vwap(trades: Iterable[Trade], anchor: datetime | None = None) -> Decimal | None:
    rows = [t for t in trades if anchor is None or t.time >= anchor]
    qty = sum((t.qty for t in rows), Decimal("0"))
    if qty <= 0:
        return None
    return sum((t.price * t.qty for t in rows), Decimal("0")) / qty


def absorption_features(trades: list[Trade], level: Decimal, side: str, tolerance_bps: Decimal, min_aggressive_qty: Decimal, max_progress_bps: Decimal, book_imbalance: Decimal | None = None) -> dict[str, object]:
    if level <= 0:
        raise ValueError("level_must_be_positive")
    near = [t for t in trades if abs(t.price - level) / level * Decimal("10000") <= tolerance_bps]
    wanted = "Buy" if side.upper() == "ASK" else "Sell"
    aggressive = sum((t.qty for t in near if t.taker_side == wanted), Decimal("0"))
    if not near:
        return {"detected": False, "aggressive_qty": Decimal("0"), "progress_bps": None, "repeated_hits": 0, "book_response": book_imbalance}
    prices = [t.price for t in near]
    progress_bps = (max(prices) - min(prices)) / level * Decimal("10000")
    detected = aggressive >= min_aggressive_qty and progress_bps <= max_progress_bps and len(near) >= 3
    return {"detected": detected, "aggressive_qty": aggressive, "progress_bps": progress_bps, "repeated_hits": len(near), "book_response": book_imbalance}


def exhaustion_features(recent_trade_counts: list[int], recent_extensions: list[Decimal], velocity_ratio_threshold: Decimal) -> dict[str, object]:
    if len(recent_trade_counts) < 4 or len(recent_extensions) < 4:
        return {"detected": False, "reason": "insufficient_samples"}
    half = len(recent_trade_counts) // 2
    first_velocity = Decimal(sum(recent_trade_counts[:half])) / Decimal(half)
    second_velocity = Decimal(sum(recent_trade_counts[half:])) / Decimal(len(recent_trade_counts) - half)
    first_ext = sum(recent_extensions[:half], Decimal("0")) / Decimal(half)
    second_ext = sum(recent_extensions[half:], Decimal("0")) / Decimal(len(recent_extensions) - half)
    ratio = second_velocity / first_velocity if first_velocity > 0 else Decimal("0")
    return {"detected": ratio <= velocity_ratio_threshold and second_ext < first_ext, "velocity_ratio": ratio, "extension_decay": first_ext - second_ext}


def segmented_delta(trades: Iterable[Trade]) -> Decimal:
    return sum((t.signed_qty for t in trades), Decimal("0"))


def volume_profile_suite(
    trades: list[Trade],
    tick_size: Decimal,
    *,
    session_start: datetime | None = None,
    impulse_start: datetime | None = None,
    pullback_start: datetime | None = None,
    previous_poc: Decimal | None = None,
    ticks_per_bin: int = 1,
    value_area_pct: Decimal = Decimal("0.70"),
    hvn_quantile: Decimal = Decimal("0.80"),
    lvn_quantile: Decimal = Decimal("0.20"),
) -> dict[str, object]:
    session_rows = [t for t in trades if session_start is None or t.time >= session_start]
    impulse_rows = [t for t in trades if impulse_start is not None and t.time >= impulse_start]
    pullback_rows = [t for t in trades if pullback_start is not None and t.time >= pullback_start]
    session = volume_profile(session_rows, tick_size, ticks_per_bin, value_area_pct, hvn_quantile, lvn_quantile)
    impulse = volume_profile(impulse_rows, tick_size, ticks_per_bin, value_area_pct, hvn_quantile, lvn_quantile) if impulse_start is not None else None
    pullback = volume_profile(pullback_rows, tick_size, ticks_per_bin, value_area_pct, hvn_quantile, lvn_quantile) if pullback_start is not None else None
    developing: list[dict[str, object]] = []
    if session_rows:
        checkpoints = sorted(set(max(1, int(len(session_rows) * frac)) for frac in (0.25, 0.50, 0.75, 1.0)))
        for count in checkpoints:
            profile = volume_profile(session_rows[:count], tick_size, ticks_per_bin, value_area_pct, hvn_quantile, lvn_quantile)
            developing.append({"trade_count": count, "event_time": session_rows[count-1].time, "poc": profile.poc, "vah": profile.vah, "val": profile.val})
    inferred_previous = previous_poc
    if inferred_previous is None and len(developing) >= 2:
        inferred_previous = developing[max(0, len(developing)//2 - 1)]["poc"]  # type: ignore[assignment]
    migration = session.poc - inferred_previous if session.poc is not None and isinstance(inferred_previous, Decimal) else None
    return {
        "session_profile": session,
        "developing_poc": developing,
        "value_migration": migration,
        "impulse_specific_profile": impulse,
        "pullback_specific_profile": pullback,
        "impulse_delta": segmented_delta(impulse_rows) if impulse_start is not None else None,
        "pullback_delta": segmented_delta(pullback_rows) if pullback_start is not None else None,
    }


def anchored_vwaps(trades: Iterable[Trade], anchors: dict[str, datetime]) -> dict[str, Decimal | None]:
    rows = list(trades)
    return {name: vwap(rows, anchor) for name, anchor in anchors.items()}
