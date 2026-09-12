from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .config import Settings
from .contracts.models import BreakoutAlert, Direction
from .structure import market_structure
from .types import Bar


@dataclass(frozen=True, slots=True)
class ScoutPoint:
    time: datetime
    price: Decimal
    volume: Decimal


class WatchRegistry:
    def __init__(self, max_watches: int) -> None:
        self.max_watches = max_watches
        self._until: dict[str, datetime] = {}
        self._reason: dict[str, str] = {}

    def promote(self, symbol: str, until: datetime, reason: str) -> bool:
        self.expire(datetime.now(timezone.utc))
        if symbol not in self._until and len(self._until) >= self.max_watches:
            return False
        self._until[symbol] = until
        self._reason[symbol] = reason
        return True

    def expire(self, now: datetime) -> None:
        for symbol in [s for s, until in self._until.items() if until <= now]:
            self._until.pop(symbol, None)
            self._reason.pop(symbol, None)

    def is_watched(self, symbol: str, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        self.expire(now)
        return symbol in self._until

    def active(self, now: datetime | None = None) -> tuple[str, ...]:
        self.expire(now or datetime.now(timezone.utc))
        return tuple(sorted(self._until))


class GlobalBreakoutScout:
    def __init__(self, settings: Settings, watch_registry: WatchRegistry | None = None) -> None:
        self.settings = settings
        self.watch_registry = watch_registry or WatchRegistry(settings.breakout_max_concurrent_watches)
        horizon = max(settings.breakout_percent_windows_sec) * 2
        self.points: dict[str, deque[ScoutPoint]] = defaultdict(lambda: deque(maxlen=max(128, horizon)))
        self.major_levels: dict[str, tuple[Decimal | None, Decimal | None, Decimal]] = {}
        self.range_levels: dict[str, tuple[Decimal | None, Decimal | None]] = {}
        self.key_levels: dict[str, tuple[Decimal, ...]] = {}
        self.trendlines: dict[str, tuple[tuple[Decimal, Decimal], ...]] = {}

    def update_structure(self, symbol: str, major_high: Decimal | None, major_low: Decimal | None, strength: Decimal = Decimal("1")) -> None:
        self.major_levels[symbol] = (major_high, major_low, strength)

    def seed_cached_bars(self, symbol: str, bars: list[Bar], timeframe: str = "1m") -> None:
        """Seed Tier-1 structural context from real cached bars when available."""
        if len(bars) < max(7, self.settings.structure_swing_window * 2 + 1):
            return
        structure = market_structure(
            bars,
            timeframe,
            self.settings.structure_swing_window,
            self.settings.level_merge_tolerance_bps,
        )
        self.update_structure(
            symbol,
            structure.get("major_high") if isinstance(structure.get("major_high"), Decimal) else None,
            structure.get("major_low") if isinstance(structure.get("major_low"), Decimal) else None,
            Decimal("0.9"),
        )
        raw_range = structure.get("range")
        range_high = raw_range.get("high") if isinstance(raw_range, dict) else None
        range_low = raw_range.get("low") if isinstance(raw_range, dict) else None
        raw_levels = structure.get("levels")
        key_levels = tuple(Decimal(str(x["price"])) for x in raw_levels if isinstance(x, dict) and x.get("price") is not None) if isinstance(raw_levels, list) else ()
        raw_lines = structure.get("trendline_candidates")
        trendlines = tuple(
            (Decimal(str(x["slope_per_second"])), Decimal(str(x["intercept"])))
            for x in raw_lines
            if isinstance(x, dict) and x.get("slope_per_second") is not None and x.get("intercept") is not None
        ) if isinstance(raw_lines, list) else ()
        self.update_breakout_context(
            symbol,
            range_high=range_high if isinstance(range_high, Decimal) else None,
            range_low=range_low if isinstance(range_low, Decimal) else None,
            key_levels=key_levels,
            trendlines=trendlines,
        )

    def update_breakout_context(
        self,
        symbol: str,
        *,
        range_high: Decimal | None = None,
        range_low: Decimal | None = None,
        key_levels: tuple[Decimal, ...] = (),
        trendlines: tuple[tuple[Decimal, Decimal], ...] = (),
    ) -> None:
        """Register lightweight deterministic context.

        `trendlines` are `(slope_per_second, intercept_at_epoch_zero)` so expected price
        at a unix timestamp `t` is `slope*t + intercept`.
        """
        self.range_levels[symbol] = (range_high, range_low)
        self.key_levels[symbol] = key_levels
        self.trendlines[symbol] = trendlines

    def ingest(self, symbol: str, price: Decimal, volume: Decimal, event_time: datetime) -> list[BreakoutAlert]:
        history = self.points[symbol]
        history.append(ScoutPoint(event_time, price, volume))
        max_age = max(self.settings.breakout_percent_windows_sec) * 2
        cutoff = event_time - timedelta(seconds=max_age)
        while history and history[0].time < cutoff:
            history.popleft()
        alerts: list[BreakoutAlert] = []
        if not self.settings.breakout_global_alert_enabled:
            return alerts
        if self.settings.breakout_percent_enabled:
            alerts.extend(self._percent_alerts(symbol, history, event_time))
        if self.settings.breakout_structure_enabled:
            alert = self._structure_alert(symbol, price, volume, event_time)
            if alert is not None:
                alerts.append(alert)
            key_alert = self._key_level_alert(symbol, price, event_time)
            if key_alert is not None:
                alerts.append(key_alert)
        if self.settings.breakout_range_enabled:
            range_alert = self._range_alert(symbol, price, event_time)
            if range_alert is not None:
                alerts.append(range_alert)
        if self.settings.breakout_trendline_enabled:
            trend_alert = self._trendline_alert(symbol, price, event_time)
            if trend_alert is not None:
                alerts.append(trend_alert)
        for alert in alerts:
            if alert.preliminary_score >= self.settings.breakout_min_prelim_score:
                self.watch_registry.promote(symbol, alert.watch_until_utc, alert.promotion_reason)
        return alerts

    def _percent_alerts(self, symbol: str, history: deque[ScoutPoint], now: datetime) -> list[BreakoutAlert]:
        if len(history) < 2:
            return []
        current = history[-1]
        alerts: list[BreakoutAlert] = []
        for window, threshold in zip(self.settings.breakout_percent_windows_sec, self.settings.breakout_percent_thresholds, strict=True):
            target_time = now - timedelta(seconds=window)
            eligible_prior = [point for point in history if point.time <= target_time]
            if not eligible_prior:
                continue
            prior = eligible_prior[-1]
            if prior.price <= 0 or prior.time == current.time:
                continue
            move = (current.price - prior.price) / prior.price * Decimal("100")
            if abs(move) < threshold:
                continue
            volumes = [p.volume for p in history if p.time >= target_time]
            base_volumes = [p.volume for p in history if p.time < target_time]
            vol_acc = None
            if volumes and base_volumes:
                recent = sum(volumes, Decimal("0")) / Decimal(len(volumes))
                base = sum(base_volumes[-len(volumes):], Decimal("0")) / Decimal(min(len(base_volumes), len(volumes)))
                vol_acc = recent / base if base > 0 else None
            score = min(Decimal("1"), abs(move) / max(threshold, Decimal("0.0001")) * Decimal("0.55") + min(vol_acc or Decimal("1"), Decimal("3")) / Decimal("3") * Decimal("0.45"))
            alerts.append(self._make_alert(symbol, "PERCENT_ACCELERATION", Direction.LONG if move > 0 else Direction.SHORT, now, prior.price, current.price, move, window, vol_acc, None, score))
        return alerts

    def _structure_alert(self, symbol: str, price: Decimal, volume: Decimal, now: datetime) -> BreakoutAlert | None:
        levels = self.major_levels.get(symbol)
        if levels is None:
            return None
        high, low, strength = levels
        if high is not None and price > high:
            move = (price - high) / high * Decimal("100") if high else None
            score = min(Decimal("1"), Decimal("0.65") + strength * Decimal("0.2"))
            return self._make_alert(symbol, "MAJOR_STRUCTURE_BREAK", Direction.LONG, now, high, price, move, None, None, strength, score)
        if low is not None and price < low:
            move = (price - low) / low * Decimal("100") if low else None
            score = min(Decimal("1"), Decimal("0.65") + strength * Decimal("0.2"))
            return self._make_alert(symbol, "MAJOR_STRUCTURE_BREAK", Direction.SHORT, now, low, price, move, None, None, strength, score)
        return None


    def _range_alert(self, symbol: str, price: Decimal, now: datetime) -> BreakoutAlert | None:
        high, low = self.range_levels.get(symbol, (None, None))
        if high is not None and price > high:
            move = (price - high) / high * Decimal("100") if high else None
            return self._make_alert(symbol, "RANGE_BREAK", Direction.LONG, now, high, price, move, None, None, Decimal("0.7"), Decimal("0.78"))
        if low is not None and price < low:
            move = (price - low) / low * Decimal("100") if low else None
            return self._make_alert(symbol, "RANGE_BREAK", Direction.SHORT, now, low, price, move, None, None, Decimal("0.7"), Decimal("0.78"))
        return None

    def _key_level_alert(self, symbol: str, price: Decimal, now: datetime) -> BreakoutAlert | None:
        history = self.points[symbol]
        if len(history) < 2:
            return None
        prior_price = history[-2].price
        for level in self.key_levels.get(symbol, ()):
            if prior_price <= level < price:
                return self._make_alert(symbol, "KEY_LEVEL_BREAK", Direction.LONG, now, level, price, (price-level)/level*Decimal("100") if level else None, None, None, Decimal("0.65"), Decimal("0.74"))
            if prior_price >= level > price:
                return self._make_alert(symbol, "KEY_LEVEL_BREAK", Direction.SHORT, now, level, price, (price-level)/level*Decimal("100") if level else None, None, None, Decimal("0.65"), Decimal("0.74"))
        return None

    def _trendline_alert(self, symbol: str, price: Decimal, now: datetime) -> BreakoutAlert | None:
        history = self.points[symbol]
        if len(history) < 2:
            return None
        prior = history[-2]
        for slope, intercept in self.trendlines.get(symbol, ()):
            prior_line = slope * Decimal(str(prior.time.timestamp())) + intercept
            now_line = slope * Decimal(str(now.timestamp())) + intercept
            if prior.price <= prior_line and price > now_line:
                return self._make_alert(symbol, "TRENDLINE_BREAK", Direction.LONG, now, now_line, price, (price-now_line)/now_line*Decimal("100") if now_line else None, None, None, Decimal("0.6"), Decimal("0.72"))
            if prior.price >= prior_line and price < now_line:
                return self._make_alert(symbol, "TRENDLINE_BREAK", Direction.SHORT, now, now_line, price, (price-now_line)/now_line*Decimal("100") if now_line else None, None, None, Decimal("0.6"), Decimal("0.72"))
        return None

    def _make_alert(self, symbol: str, detector: str, direction: Direction, now: datetime, reference: Decimal | None, price: Decimal, move: Decimal | None, window: int | None, vol_acc: Decimal | None, strength: Decimal | None, score: Decimal) -> BreakoutAlert:
        material = f"{symbol}|{detector}|{now.isoformat()}|{price}"
        snapshot_material = f"HM_CRYPTO_V1|{symbol}|{now.astimezone(timezone.utc).isoformat()}"
        return BreakoutAlert(
            alert_id=hashlib.sha256(material.encode()).hexdigest()[:24],
            snapshot_id=hashlib.sha256(snapshot_material.encode()).hexdigest()[:24],
            symbol=symbol,
            direction=direction,
            detector_type=detector,
            event_time_utc=now,
            reference_level=reference,
            break_price=price,
            move_pct=move,
            window_sec=window,
            volume_acceleration=vol_acc,
            structure_strength=strength,
            preliminary_score=score,
            promotion_reason=f"tier1:{detector}",
            watch_until_utc=now + timedelta(seconds=self.settings.breakout_watch_ttl_sec),
        )
