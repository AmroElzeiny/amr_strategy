from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .bars import build_trade_bars
from .breakout import GlobalBreakoutScout
from .bybit import BybitV5PublicAdapter
from .config import Settings
from .contracts.models import BreakoutAlert, MarketMode
from .ict import value_locations
from .orderbook import LocalOrderBook
from .quality import SourceFreshness, assess_data_quality
from .regime import classify_regime
from .scanner import ScanResult, rank_universe
from .snapshot import assemble_snapshot, derivatives_context
from .storage import LocalArchive
from .stream_state import DeepMarketStreamState
from .structure import market_structure
from .tpo import tpo_acceptance_rejection, tpo_profile
from .types import Instrument, Ticker
from .volume import (
    absorption_features,
    anchored_vwaps,
    exhaustion_features,
    footprint,
    delta_per_bar,
    volume_profile_suite,
)


class MarketIntelEngine:
    """Operational coordinator for market intelligence only.

    There is deliberately no authenticated exchange client and no order method in this class.
    Tier 1 scans the full eligible universe with lightweight ticker-derived observations. Tier 2
    deep methods are invoked only for promoted symbols.
    """

    def __init__(
        self,
        settings: Settings,
        adapter: BybitV5PublicAdapter | None = None,
        archive: LocalArchive | None = None,
    ) -> None:
        self.settings = settings
        self.adapter = adapter or BybitV5PublicAdapter(settings)
        self.archive = archive
        self.scout = GlobalBreakoutScout(settings)
        self._instruments: list[Instrument] = []
        self._instrument_by_symbol: dict[str, Instrument] = {}
        self._universe_refreshed_at: datetime | None = None
        self._previous_turnover: dict[str, Decimal] = {}
        self._latest_scan: ScanResult | None = None

    def refresh_universe(self, now: datetime | None = None, force: bool = False) -> list[Instrument]:
        now = now or datetime.now(timezone.utc)
        if not force and self._universe_refreshed_at is not None:
            age = (now - self._universe_refreshed_at).total_seconds()
            if age < self.settings.universe_refresh_sec:
                return self._instruments
        self._instruments = self.adapter.instruments()
        self._instrument_by_symbol = {x.symbol: x for x in self._instruments}
        self._universe_refreshed_at = now
        return self._instruments

    def scan_cycle(self, now: datetime | None = None) -> tuple[ScanResult, list[BreakoutAlert]]:
        now = now or datetime.now(timezone.utc)
        instruments = self.refresh_universe(now)
        tickers = self.adapter.tickers()
        scan = rank_universe(instruments, tickers, self.settings, now)
        self._latest_scan = scan
        eligible = set(scan.eligible_symbols)
        alerts: list[BreakoutAlert] = []
        source_time = self.adapter.source_timestamps.get("/v5/market/tickers", now)
        for ticker in tickers:
            if ticker.symbol not in eligible:
                continue
            prior_turnover = self._previous_turnover.get(ticker.symbol)
            volume_increment = max(Decimal("0"), ticker.turnover_24h - prior_turnover) if prior_turnover is not None else Decimal("0")
            self._previous_turnover[ticker.symbol] = ticker.turnover_24h
            history = self.scout.points[ticker.symbol]
            if len(history) >= 5:
                recent = list(history)[-40:]
                high = max(x.price for x in recent)
                low = min(x.price for x in recent)
                span = high - low
                strength = min(Decimal("1"), Decimal(len(recent)) / Decimal("20"))
                self.scout.update_structure(ticker.symbol, high, low, strength)
                key_levels = (high, low)
                trendlines: tuple[tuple[Decimal, Decimal], ...] = ()
                if len(recent) >= 3:
                    first, last = recent[0], recent[-1]
                    dt = Decimal(str((last.time - first.time).total_seconds()))
                    if dt > 0:
                        slope = (last.price - first.price) / dt
                        intercept = first.price - slope * Decimal(str(first.time.timestamp()))
                        trendlines = ((slope, intercept),)
                self.scout.update_breakout_context(
                    ticker.symbol,
                    range_high=high if span > 0 else None,
                    range_low=low if span > 0 else None,
                    key_levels=key_levels,
                    trendlines=trendlines,
                )
            alerts.extend(self.scout.ingest(ticker.symbol, ticker.last_price, volume_increment, source_time))
        if self.archive is not None:
            for alert in alerts:
                self.archive.append("breakout_alerts", alert.event_time_utc, alert.symbol, alert.model_dump(mode="json"))
        return scan, alerts

    def deep_watch_symbols(self, now: datetime | None = None) -> tuple[str, ...]:
        """Only this list is eligible for trades/orderbook/footprint deep subscriptions."""
        watch = list(self.scout.watch_registry.active(now))
        promoted = list(self._latest_scan.promoted if self._latest_scan and self.settings.scanner_enabled else ())
        out: list[str] = []
        for symbol in watch + promoted:
            if symbol not in out:
                out.append(symbol)
            if len(out) >= self.settings.scanner_max_promoted_symbols:
                break
        return tuple(out)

    def deep_public_topics(self, now: datetime | None = None, orderbook_depth: int = 50) -> tuple[str, ...]:
        topics: list[str] = []
        for symbol in self.deep_watch_symbols(now):
            topics.extend((f"publicTrade.{symbol}", f"orderbook.{orderbook_depth}.{symbol}"))
            if self.settings.market_mode == MarketMode.DERIVATIVES and self.settings.liquidations_enabled:
                topics.append(f"allLiquidation.{symbol}")
        return tuple(topics)

    def build_deep_snapshot(self, symbol: str, breakout_alert: BreakoutAlert | None = None, stream_state: DeepMarketStreamState | None = None) -> Any:
        if symbol not in self.deep_watch_symbols() and self._latest_scan is not None:
            raise ValueError("symbol_not_promoted_for_deep_watch")
        instrument = self._instrument_by_symbol.get(symbol)
        if instrument is None:
            self.refresh_universe(force=True)
            instrument = self._instrument_by_symbol.get(symbol)
        if instrument is None:
            raise ValueError("instrument_not_in_current_universe")

        tickers = {x.symbol: x for x in self.adapter.tickers()}
        ticker = tickers.get(symbol)
        if ticker is None:
            raise ValueError("ticker_missing_for_symbol")
        stream_trades = stream_state.recent_trades() if stream_state is not None else []
        trades = stream_trades or self.adapter.recent_trades(symbol, limit=1000)
        if not trades:
            raise ValueError("recent_trades_missing")

        timeframe_bars: dict[str, Any] = {}
        for tf in (*self.settings.entry_timeframes, *self.settings.context_timeframes):
            interval = _bybit_tf(tf)
            timeframe_bars[tf] = self.adapter.klines(symbol, interval, limit=300)
        for seconds in self.settings.micro_bar_seconds:
            timeframe_bars[f"{seconds}s"] = build_trade_bars(trades, seconds)

        structure_tf = "5m" if "5m" in timeframe_bars else self.settings.entry_timeframes[0]
        bars = timeframe_bars[structure_tf]
        structure = market_structure(
            bars, structure_tf, self.settings.structure_swing_window, self.settings.level_merge_tolerance_bps,
            range_compression_ratio=self.settings.range_compression_ratio,
            liquidity_sweep_tolerance_multiple=self.settings.liquidity_sweep_tolerance_multiple,
            motion_compression_ratio=self.settings.motion_compression_ratio,
            motion_expansion_ratio=self.settings.motion_expansion_ratio,
            motion_displacement_range_multiple=self.settings.motion_displacement_range_multiple,
            motion_displacement_body_fraction=self.settings.motion_displacement_body_fraction,
        )
        self.scout.seed_cached_bars(symbol, bars, structure_tf)
        structure["higher_timeframe_levels"] = {
            tf: {
                "high": max((b.high for b in timeframe_bars.get(tf, [])), default=None),
                "low": min((b.low for b in timeframe_bars.get(tf, [])), default=None),
            }
            for tf in self.settings.context_timeframes
        }
        locations = value_locations(
            bars,
            min_fvg_gap=instrument.tick_size * Decimal(self.settings.ict_fvg_min_gap_ticks),
            imbalance_body_fraction_min=self.settings.ict_imbalance_body_fraction_min,
            order_block_displacement_multiple=self.settings.ict_order_block_displacement_multiple,
            order_block_lookback=self.settings.ict_order_block_lookback,
        )
        structure["value_locations"] = locations

        profile_suite = volume_profile_suite(
            trades,
            instrument.tick_size,
            ticks_per_bin=self.settings.profile_ticks_per_bin,
            session_start=_utc_day_start(trades[-1].time),
            impulse_start=_largest_bar_start(bars),
            pullback_start=(bars[-3].start if len(bars) >= 3 else None),
            value_area_pct=self.settings.volume_profile_value_area_pct,
            hvn_quantile=self.settings.volume_profile_hvn_quantile,
            lvn_quantile=self.settings.volume_profile_lvn_quantile,
        )
        session_profile = profile_suite["session_profile"]
        fp = footprint(
            trades,
            instrument.tick_size,
            self.settings.footprint_ticks_per_bucket,
            self.settings.footprint_imbalance_ratio,
            self.settings.footprint_stacked_levels,
        )
        fp["delta_per_bar"] = delta_per_bar(trades, bars)

        book_result: dict[str, Any] | None = None
        if stream_state is not None:
            book = stream_state.orderbook
            if not book.valid or book.needs_resync:
                book_result = self.adapter.orderbook_snapshot(symbol, limit=200)
                event_ms = int(book_result.get("cts") or book_result.get("ts") or int(datetime.now(timezone.utc).timestamp() * 1000))
                book.apply_snapshot(book_result, event_ms)
            else:
                event_ms = book.last_event_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
        else:
            book_result = self.adapter.orderbook_snapshot(symbol, limit=200)
            book = LocalOrderBook(self.settings.orderbook_stale_ms, self.settings.orderbook_wall_multiple)
            event_ms = int(book_result.get("cts") or book_result.get("ts") or int(datetime.now(timezone.utc).timestamp() * 1000))
            book.apply_snapshot(book_result, event_ms)
        book_diag = book.diagnostic()
        if stream_state is not None:
            book_diag["websocket_reconnects"] = stream_state.websocket_reconnects
        absorption = absorption_features(
            trades,
            level=(book.metrics().best_ask or trades[-1].price),
            side="ASK",
            tolerance_bps=self.settings.absorption_level_tolerance_bps,
            min_aggressive_qty=self.settings.absorption_min_aggressive_qty,
            max_progress_bps=self.settings.absorption_max_progress_bps,
            book_imbalance=book.metrics().imbalance,
        )
        recent_counts = _trade_counts(trades, 8)
        extensions = _bar_extensions(bars, 8)
        exhaustion = exhaustion_features(recent_counts, extensions, self.settings.exhaustion_velocity_ratio)

        tpo = tpo_profile(
            bars, instrument.tick_size, self.settings.tpo_ticks_per_bin,
            value_area_pct=self.settings.volume_profile_value_area_pct,
        )
        tpo.update(tpo_acceptance_rejection(
            bars, tpo.get("val"), tpo.get("vah"), self.settings.tpo_min_accept_closes
        ))
        anchors: dict[str, datetime] = {"session_start": _utc_day_start(trades[-1].time)}
        impulse_start = _largest_bar_start(bars)
        if impulse_start is not None:
            anchors["impulse_origin"] = impulse_start
        if breakout_alert is not None:
            anchors["breakout_event"] = breakout_alert.event_time_utc
        swings = structure.get("swings")
        if isinstance(swings, list) and swings:
            last = swings[-1]
            if isinstance(last, dict) and isinstance(last.get("time"), datetime):
                anchors["major_swing"] = last["time"]
        vwaps = anchored_vwaps(trades, anchors)

        oi = self.adapter.open_interest(symbol) if self.settings.open_interest_enabled else None
        funding = self.adapter.funding_history(symbol) if self.settings.funding_enabled else None
        liquidation_rows = stream_state.liquidation_rows() if stream_state is not None and self.settings.liquidations_enabled else None
        deriv = derivatives_context(self.settings.market_mode, ticker.raw, oi, funding, liquidation_rows)
        directional_delta = Decimal(str(fp["delta"]))
        value_migration = profile_suite.get("value_migration")
        failed_breaks = structure.get("failed_breaks")
        returned_to_prior_range = bool(failed_breaks) if isinstance(failed_breaks, list) else False
        follow_through = None
        if breakout_alert is not None and breakout_alert.reference_level not in {None, Decimal("0")}:
            distance = abs(trades[-1].price - breakout_alert.reference_level)
            initial = abs(breakout_alert.break_price - breakout_alert.reference_level)
            follow_through = min(Decimal("1"), distance / initial) if initial > 0 else Decimal("0")
        regime = classify_regime(
            bars,
            structure,
            value_migration=value_migration if isinstance(value_migration, Decimal) else None,
            directional_delta=directional_delta,
            breakout_follow_through=follow_through,
            return_to_prior_range=returned_to_prior_range,
            overlap_balance_threshold=self.settings.regime_overlap_balance_threshold,
            trend_progression_threshold=self.settings.regime_trend_progression_threshold,
        )

        source_times = {
            "ticker": self.adapter.source_timestamps.get("/v5/market/tickers"),
            "trades": trades[-1].time,
            "orderbook": datetime.fromtimestamp(event_ms / 1000, tz=timezone.utc),
            "klines": bars[-1].end if bars else None,
            "open_interest": _row_timestamp(oi[0] if oi else None, "timestamp"),
            "funding": self.adapter.source_timestamps.get("/v5/market/funding/history") if funding is not None else None,
        }
        sources = [
            SourceFreshness("ticker", source_times["ticker"], self.settings.data_stale_ms, True),
            SourceFreshness("trades", source_times["trades"], self.settings.trade_stale_ms, True),
            SourceFreshness("orderbook", source_times["orderbook"], self.settings.orderbook_stale_ms, True),
            SourceFreshness("klines", source_times["klines"], max(self.settings.data_stale_ms, 120_000), True),
        ]
        if self.settings.market_mode == MarketMode.DERIVATIVES:
            if self.settings.open_interest_enabled:
                sources.append(SourceFreshness("open_interest", source_times["open_interest"], self.settings.oi_stale_ms, False))
            if self.settings.funding_enabled:
                sources.append(SourceFreshness("funding", source_times["funding"], self.settings.funding_stale_ms, False))
        unresolved_gap = bool(stream_state is not None and stream_state.orderbook.needs_resync)
        resync_reasons = []
        if stream_state is not None and stream_state.orderbook.resync_count > 0:
            resync_reasons.append(f"orderbook_resyncs:{stream_state.orderbook.resync_count}")
        quality, reasons = assess_data_quality(
            sources,
            orderbook_valid=book.valid,
            sequence_gap=unresolved_gap,
            degraded_reasons=resync_reasons,
            reconnects=(stream_state.websocket_reconnects if stream_state is not None else 0),
        )

        volume_payload = {
            "enabled": self.settings.volume_profile_enabled,
            "poc": session_profile.poc if self.settings.volume_profile_enabled else None,
            "vah": session_profile.vah if self.settings.volume_profile_enabled else None,
            "val": session_profile.val if self.settings.volume_profile_enabled else None,
            "hvn": list(session_profile.hvn) if self.settings.volume_profile_enabled else [],
            "lvn": list(session_profile.lvn) if self.settings.volume_profile_enabled else [],
            "value_area_pct": session_profile.value_area_pct,
            "developing_poc": profile_suite["developing_poc"],
            "value_migration": profile_suite["value_migration"],
            "impulse_specific_profile": asdict(profile_suite["impulse_specific_profile"]) if profile_suite["impulse_specific_profile"] else None,
            "pullback_specific_profile": asdict(profile_suite["pullback_specific_profile"]) if profile_suite["pullback_specific_profile"] else None,
            "session_profile": asdict(session_profile),
            "tpo": tpo if self.settings.tpo_enabled else {"enabled": False},
            "vwap": vwaps if self.settings.vwap_enabled or self.settings.anchored_vwap_enabled else {"enabled": False},
        }
        orderflow_payload = {
            **(fp if self.settings.footprint_enabled or self.settings.delta_enabled or self.settings.cumulative_delta_enabled else {"enabled": False}),
            "impulse_delta": profile_suite["impulse_delta"],
            "pullback_delta": profile_suite["pullback_delta"],
            "absorption": absorption,
            "exhaustion": exhaustion,
        }
        snapshot = assemble_snapshot(
            symbol=symbol,
            environment=self.settings.trading_env,
            market_mode=self.settings.market_mode,
            event_time=trades[-1].time,
            instrument=asdict(instrument),
            ticker=asdict(ticker),
            timeframes={k: [_bar_dict(b) for b in v] for k, v in timeframe_bars.items()},
            structure=structure,
            levels=structure.get("levels", []) if isinstance(structure.get("levels"), list) else [],
            volume_profile=volume_payload,
            orderflow=orderflow_payload,
            orderbook=book_diag,
            derivatives=deriv,
            regime=regime,
            breakout_alert=breakout_alert.model_dump(mode="json") if breakout_alert else None,
            data_quality=quality,
            quality_reasons=reasons,
            source_timestamps=source_times,
        )
        if self.archive is not None:
            for trade in trades:
                self.archive.append("public_trades", trade.time, symbol, asdict(trade))
            for tf, rows in timeframe_bars.items():
                for bar in rows[-50:]:
                    self.archive.append("bars", bar.end, symbol, {"timeframe": tf, **_bar_dict(bar)})
            if book_result is not None:
                self.archive.append("orderbook", datetime.fromtimestamp(event_ms/1000, tz=timezone.utc), symbol, book_result)
            self.archive.append("features", snapshot.event_time_utc, symbol, snapshot.model_dump(mode="json"))
        return snapshot


def _bybit_tf(tf: str) -> str:
    mapping = {"1m":"1", "3m":"3", "5m":"5", "15m":"15", "30m":"30", "1h":"60", "2h":"120", "4h":"240", "6h":"360", "12h":"720", "1d":"D", "1w":"W"}
    if tf not in mapping:
        raise ValueError(f"unsupported_bybit_timeframe:{tf}")
    return mapping[tf]


def _bar_dict(bar: Any) -> dict[str, Any]:
    return asdict(bar)


def _utc_day_start(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _largest_bar_start(bars: list[Any]) -> datetime | None:
    if not bars:
        return None
    return max(bars, key=lambda x: x.high - x.low).start


def _trade_counts(trades: list[Any], buckets: int) -> list[int]:
    if not trades:
        return []
    chunks = max(1, len(trades) // buckets)
    return [len(trades[i:i+chunks]) for i in range(0, len(trades), chunks)][-buckets:]


def _bar_extensions(bars: list[Any], count: int) -> list[Decimal]:
    return [abs(b.close - b.open) for b in bars[-count:]]


def _row_timestamp(row: dict[str, Any] | None, field: str) -> datetime | None:
    if not row:
        return None
    value = row.get(field) or row.get("timestamp")
    if value in {None, ""}:
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
