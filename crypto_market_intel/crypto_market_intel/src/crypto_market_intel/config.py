from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .contracts.models import CONTRACT_VERSION, Exchange, MarketMode, TradingEnvironment


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw in {None, ""} else int(raw)


def _dec(name: str, default: str) -> Decimal:
    raw = os.getenv(name)
    return Decimal(default if raw in {None, ""} else raw)


def _csv(name: str, default: str = "") -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(x.strip() for x in raw.split(",") if x.strip())


def _int_csv(name: str, default: str) -> tuple[int, ...]:
    return tuple(int(x) for x in _csv(name, default))


@dataclass(frozen=True)
class Settings:
    contract_version: str
    exchange: Exchange
    trading_env: TradingEnvironment
    market_mode: MarketMode
    bybit_real_rest_base: str
    bybit_demo_rest_base: str
    bybit_public_ws_root: str
    bybit_real_private_ws_root: str
    bybit_demo_private_ws_root: str
    scanner_enabled: bool
    scanner_interval_sec: int
    universe_refresh_sec: int
    scanner_top_gainers_n: int
    scanner_top_losers_n: int
    scanner_top_volume_n: int
    scanner_max_promoted_symbols: int
    scanner_quote_coins: tuple[str, ...]
    scanner_min_turnover_24h: Decimal | None
    scanner_min_listing_age_hours: int
    scanner_exclude_symbols: tuple[str, ...]
    scanner_include_symbols: tuple[str, ...]
    scanner_allow_premarket: bool
    scanner_exclude_symbol_types: tuple[str, ...]
    bybit_http_max_rps: int
    breakout_global_alert_enabled: bool
    breakout_percent_enabled: bool
    breakout_structure_enabled: bool
    breakout_range_enabled: bool
    breakout_trendline_enabled: bool
    breakout_percent_windows_sec: tuple[int, ...]
    breakout_percent_thresholds: tuple[Decimal, ...]
    breakout_min_prelim_score: Decimal
    breakout_watch_ttl_sec: int
    breakout_max_concurrent_watches: int
    micro_bar_seconds: tuple[int, ...]
    entry_timeframes: tuple[str, ...]
    context_timeframes: tuple[str, ...]
    volume_profile_enabled: bool
    footprint_enabled: bool
    delta_enabled: bool
    cumulative_delta_enabled: bool
    orderbook_heatmap_enabled: bool
    tpo_enabled: bool
    vwap_enabled: bool
    anchored_vwap_enabled: bool
    open_interest_enabled: bool
    funding_enabled: bool
    liquidations_enabled: bool
    data_dir: Path
    orderbook_archive_enabled: bool
    trades_archive_enabled: bool
    data_stale_ms: int
    orderbook_stale_ms: int
    trade_stale_ms: int
    oi_stale_ms: int
    funding_stale_ms: int
    structure_swing_window: int
    structure_equal_tolerance_bps: Decimal
    level_merge_tolerance_bps: Decimal
    volume_profile_value_area_pct: Decimal
    volume_profile_hvn_quantile: Decimal
    volume_profile_lvn_quantile: Decimal
    profile_ticks_per_bin: int
    footprint_ticks_per_bucket: int
    footprint_imbalance_ratio: Decimal
    footprint_stacked_levels: int
    orderbook_wall_multiple: Decimal
    absorption_level_tolerance_bps: Decimal
    tpo_ticks_per_bin: int
    tpo_min_accept_closes: int
    ict_fvg_min_gap_ticks: int
    ict_imbalance_body_fraction_min: Decimal
    ict_order_block_displacement_multiple: Decimal
    ict_order_block_lookback: int
    motion_compression_ratio: Decimal
    motion_expansion_ratio: Decimal
    motion_displacement_range_multiple: Decimal
    motion_displacement_body_fraction: Decimal
    range_compression_ratio: Decimal
    liquidity_sweep_tolerance_multiple: Decimal
    absorption_min_aggressive_qty: Decimal
    absorption_max_progress_bps: Decimal
    exhaustion_velocity_ratio: Decimal
    regime_overlap_balance_threshold: Decimal
    regime_trend_progression_threshold: Decimal
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        version = os.getenv("CONTRACT_VERSION", CONTRACT_VERSION)
        if version != CONTRACT_VERSION:
            raise ValueError("CONTRACT_VERSION must equal HM_CRYPTO_V1")
        windows = _int_csv("BREAKOUT_PERCENT_WINDOWS_SEC", "30,60,300,900")
        raw_thresholds = _csv("BREAKOUT_PERCENT_THRESHOLDS", "0.35,0.55,1.2,2.2")
        thresholds = tuple(Decimal(x) for x in raw_thresholds)
        if len(windows) != len(thresholds):
            raise ValueError("BREAKOUT_PERCENT_WINDOWS_SEC and thresholds must align")
        exchange = Exchange(os.getenv("EXCHANGE", "BYBIT"))
        if exchange != Exchange.BYBIT:
            raise ValueError("BINANCE is contract-only in Package 1; live adapter is not implemented")
        return cls(
            contract_version=version,
            exchange=exchange,
            trading_env=TradingEnvironment(os.getenv("TRADING_ENV", "DEMO")),
            market_mode=MarketMode(os.getenv("MARKET_MODE", "DERIVATIVES")),
            bybit_real_rest_base=os.getenv("BYBIT_REAL_REST_BASE", "https://api.bybit.com"),
            bybit_demo_rest_base=os.getenv("BYBIT_DEMO_REST_BASE", "https://api-demo.bybit.com"),
            bybit_public_ws_root=os.getenv("BYBIT_PUBLIC_WS_ROOT", "wss://stream.bybit.com"),
            bybit_real_private_ws_root=os.getenv("BYBIT_REAL_PRIVATE_WS_ROOT", "wss://stream.bybit.com"),
            bybit_demo_private_ws_root=os.getenv("BYBIT_DEMO_PRIVATE_WS_ROOT", "wss://stream-demo.bybit.com"),
            scanner_enabled=_bool("SCANNER_ENABLED", True),
            scanner_interval_sec=_int("SCANNER_INTERVAL_SEC", 15),
            universe_refresh_sec=_int("UNIVERSE_REFRESH_SEC", 300),
            scanner_top_gainers_n=_int("SCANNER_TOP_GAINERS_N", 20),
            scanner_top_losers_n=_int("SCANNER_TOP_LOSERS_N", 20),
            scanner_top_volume_n=_int("SCANNER_TOP_VOLUME_N", 20),
            scanner_max_promoted_symbols=_int("SCANNER_MAX_PROMOTED_SYMBOLS", 60),
            scanner_quote_coins=_csv("SCANNER_QUOTE_COINS", "USDT"),
            scanner_min_turnover_24h=(None if os.getenv("SCANNER_MIN_TURNOVER_24H", "") == "" else _dec("SCANNER_MIN_TURNOVER_24H", "0")),
            scanner_min_listing_age_hours=_int("SCANNER_MIN_LISTING_AGE_HOURS", 0),
            scanner_exclude_symbols=_csv("SCANNER_EXCLUDE_SYMBOLS"),
            scanner_include_symbols=_csv("SCANNER_INCLUDE_SYMBOLS"),
            scanner_allow_premarket=_bool("SCANNER_ALLOW_PREMARKET", False),
            scanner_exclude_symbol_types=_csv("SCANNER_EXCLUDE_SYMBOL_TYPES"),
            bybit_http_max_rps=_int("BYBIT_HTTP_MAX_RPS", 20),
            breakout_global_alert_enabled=_bool("BREAKOUT_GLOBAL_ALERT_ENABLED", True),
            breakout_percent_enabled=_bool("BREAKOUT_PERCENT_ENABLED", True),
            breakout_structure_enabled=_bool("BREAKOUT_STRUCTURE_ENABLED", True),
            breakout_range_enabled=_bool("BREAKOUT_RANGE_ENABLED", True),
            breakout_trendline_enabled=_bool("BREAKOUT_TRENDLINE_ENABLED", True),
            breakout_percent_windows_sec=windows,
            breakout_percent_thresholds=thresholds,
            breakout_min_prelim_score=_dec("BREAKOUT_MIN_PRELIM_SCORE", "0.60"),
            breakout_watch_ttl_sec=_int("BREAKOUT_WATCH_TTL_SEC", 1800),
            breakout_max_concurrent_watches=_int("BREAKOUT_MAX_CONCURRENT_WATCHES", 100),
            micro_bar_seconds=_int_csv("MICRO_BAR_SECONDS", "1,5,30"),
            entry_timeframes=_csv("ENTRY_TIMEFRAMES", "1m,3m,5m,15m"),
            context_timeframes=_csv("CONTEXT_TIMEFRAMES", "1h,4h,1d"),
            volume_profile_enabled=_bool("VOLUME_PROFILE_ENABLED", True),
            footprint_enabled=_bool("FOOTPRINT_ENABLED", True),
            delta_enabled=_bool("DELTA_ENABLED", True),
            cumulative_delta_enabled=_bool("CUMULATIVE_DELTA_ENABLED", True),
            orderbook_heatmap_enabled=_bool("ORDERBOOK_HEATMAP_ENABLED", True),
            tpo_enabled=_bool("TPO_ENABLED", True),
            vwap_enabled=_bool("VWAP_ENABLED", True),
            anchored_vwap_enabled=_bool("ANCHORED_VWAP_ENABLED", True),
            open_interest_enabled=_bool("OPEN_INTEREST_ENABLED", True),
            funding_enabled=_bool("FUNDING_ENABLED", True),
            liquidations_enabled=_bool("LIQUIDATIONS_ENABLED", True),
            data_dir=Path(os.getenv("DATA_DIR", "./data")),
            orderbook_archive_enabled=_bool("ORDERBOOK_ARCHIVE_ENABLED", True),
            trades_archive_enabled=_bool("TRADES_ARCHIVE_ENABLED", True),
            data_stale_ms=_int("DATA_STALE_MS", 20_000),
            orderbook_stale_ms=_int("ORDERBOOK_STALE_MS", 3_000),
            trade_stale_ms=_int("TRADE_STALE_MS", 5_000),
            oi_stale_ms=_int("OI_STALE_MS", 120_000),
            funding_stale_ms=_int("FUNDING_STALE_MS", 900_000),
            structure_swing_window=_int("STRUCTURE_SWING_WINDOW", 3),
            structure_equal_tolerance_bps=_dec("STRUCTURE_EQUAL_TOLERANCE_BPS", "8"),
            level_merge_tolerance_bps=_dec("LEVEL_MERGE_TOLERANCE_BPS", "10"),
            volume_profile_value_area_pct=_dec("VOLUME_PROFILE_VALUE_AREA_PCT", "0.70"),
            volume_profile_hvn_quantile=_dec("VOLUME_PROFILE_HVN_QUANTILE", "0.80"),
            volume_profile_lvn_quantile=_dec("VOLUME_PROFILE_LVN_QUANTILE", "0.20"),
            profile_ticks_per_bin=_int("PROFILE_TICKS_PER_BIN", 1),
            footprint_ticks_per_bucket=_int("FOOTPRINT_TICKS_PER_BUCKET", 1),
            footprint_imbalance_ratio=_dec("FOOTPRINT_IMBALANCE_RATIO", "3"),
            footprint_stacked_levels=_int("FOOTPRINT_STACKED_LEVELS", 3),
            orderbook_wall_multiple=_dec("ORDERBOOK_WALL_MULTIPLE", "3"),
            absorption_level_tolerance_bps=_dec("ABSORPTION_LEVEL_TOLERANCE_BPS", "5"),
            tpo_ticks_per_bin=_int("TPO_TICKS_PER_BIN", 1),
            tpo_min_accept_closes=_int("TPO_MIN_ACCEPT_CLOSES", 2),
            ict_fvg_min_gap_ticks=_int("ICT_FVG_MIN_GAP_TICKS", 0),
            ict_imbalance_body_fraction_min=_dec("ICT_IMBALANCE_BODY_FRACTION_MIN", "0.65"),
            ict_order_block_displacement_multiple=_dec("ICT_ORDER_BLOCK_DISPLACEMENT_MULTIPLE", "1.5"),
            ict_order_block_lookback=_int("ICT_ORDER_BLOCK_LOOKBACK", 10),
            motion_compression_ratio=_dec("MOTION_COMPRESSION_RATIO", "0.70"),
            motion_expansion_ratio=_dec("MOTION_EXPANSION_RATIO", "1.30"),
            motion_displacement_range_multiple=_dec("MOTION_DISPLACEMENT_RANGE_MULTIPLE", "1.5"),
            motion_displacement_body_fraction=_dec("MOTION_DISPLACEMENT_BODY_FRACTION", "0.60"),
            range_compression_ratio=_dec("RANGE_COMPRESSION_RATIO", "0.65"),
            liquidity_sweep_tolerance_multiple=_dec("LIQUIDITY_SWEEP_TOLERANCE_MULTIPLE", "4"),
            absorption_min_aggressive_qty=_dec("ABSORPTION_MIN_AGGRESSIVE_QTY", "10"),
            absorption_max_progress_bps=_dec("ABSORPTION_MAX_PROGRESS_BPS", "5"),
            exhaustion_velocity_ratio=_dec("EXHAUSTION_VELOCITY_RATIO", "0.60"),
            regime_overlap_balance_threshold=_dec("REGIME_OVERLAP_BALANCE_THRESHOLD", "0.60"),
            regime_trend_progression_threshold=_dec("REGIME_TREND_PROGRESSION_THRESHOLD", "0.66"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    @property
    def bybit_public_rest_base(self) -> str:
        # Public market data is mainnet-equivalent even when trading_env=DEMO.
        return self.bybit_real_rest_base

    def bybit_public_ws_url(self) -> str:
        category = "spot" if self.market_mode == MarketMode.SPOT else "linear"
        return f"{self.bybit_public_ws_root}/v5/public/{category}"
