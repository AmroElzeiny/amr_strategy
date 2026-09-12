from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from .config import Settings
from .types import Instrument, Ticker


@dataclass(frozen=True, slots=True)
class ScanResult:
    eligible_symbols: tuple[str, ...]
    gainers: tuple[str, ...]
    losers: tuple[str, ...]
    highest_turnover: tuple[str, ...]
    promoted: tuple[str, ...]


def filter_universe(instruments: list[Instrument], tickers: list[Ticker], settings: Settings, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    ticker_by_symbol = {x.symbol: x for x in tickers}
    include = set(settings.scanner_include_symbols)
    exclude = set(settings.scanner_exclude_symbols)
    eligible: list[str] = []
    for inst in instruments:
        if inst.status != "Trading" or inst.symbol in exclude:
            continue
        if include and inst.symbol not in include:
            continue
        if inst.quote_coin not in settings.scanner_quote_coins:
            continue
        if inst.is_pre_listing and not settings.scanner_allow_premarket:
            continue
        if inst.symbol_type is not None and inst.symbol_type in settings.scanner_exclude_symbol_types:
            continue
        if inst.launch_time is not None:
            age_h = (now - inst.launch_time).total_seconds() / 3600
            if age_h < settings.scanner_min_listing_age_hours:
                continue
        ticker = ticker_by_symbol.get(inst.symbol)
        if ticker is None:
            continue
        minimum = settings.scanner_min_turnover_24h
        if minimum is not None and ticker.turnover_24h < minimum:
            continue
        eligible.append(inst.symbol)
    return sorted(set(eligible))


def rank_universe(instruments: list[Instrument], tickers: list[Ticker], settings: Settings, now: datetime | None = None) -> ScanResult:
    eligible = filter_universe(instruments, tickers, settings, now)
    allowed = set(eligible)
    rows = [x for x in tickers if x.symbol in allowed]
    gainers = sorted(rows, key=lambda x: (x.price_24h_pct, x.turnover_24h, x.symbol), reverse=True)[: settings.scanner_top_gainers_n]
    losers = sorted(rows, key=lambda x: (x.price_24h_pct, -x.turnover_24h, x.symbol))[: settings.scanner_top_losers_n]
    volume = sorted(rows, key=lambda x: (x.turnover_24h, x.volume_24h, x.symbol), reverse=True)[: settings.scanner_top_volume_n]
    promoted: list[str] = []
    for group in (gainers, losers, volume):
        for ticker in group:
            if ticker.symbol not in promoted:
                promoted.append(ticker.symbol)
                if len(promoted) >= settings.scanner_max_promoted_symbols:
                    break
    return ScanResult(
        eligible_symbols=tuple(eligible),
        gainers=tuple(x.symbol for x in gainers),
        losers=tuple(x.symbol for x in losers),
        highest_turnover=tuple(x.symbol for x in volume),
        promoted=tuple(promoted),
    )
