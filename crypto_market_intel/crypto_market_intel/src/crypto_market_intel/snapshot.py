from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .contracts.models import DataQuality, Exchange, MarketMode, MarketSnapshot, TradingEnvironment

FEATURE_VERSIONS = {
    "algorithm_policy": "HM_CRYPTO_FEATURE_POLICY_V1",
    "market_structure": "1.0.0",
    "ict_value_locations": "1.0.0",
    "volume_profile": "1.0.0",
    "footprint_delta": "1.0.0",
    "orderbook_heatmap": "1.0.0",
    "tpo": "1.0.0",
    "regime": "1.0.0",
    "breakout_scout": "1.0.0",
}


def make_snapshot_id(symbol: str, event_time: datetime) -> str:
    material = f"HM_CRYPTO_V1|{symbol}|{event_time.astimezone(timezone.utc).isoformat()}"
    return hashlib.sha256(material.encode()).hexdigest()[:32]


def assemble_snapshot(*, symbol: str, environment: TradingEnvironment, market_mode: MarketMode, event_time: datetime, instrument: dict[str, Any], ticker: dict[str, Any], timeframes: dict[str, Any], structure: dict[str, Any], levels: list[dict[str, Any]], volume_profile: dict[str, Any], orderflow: dict[str, Any], orderbook: dict[str, Any], derivatives: dict[str, Any] | None, regime: dict[str, Any], breakout_alert: dict[str, Any] | None, data_quality: DataQuality, quality_reasons: list[str], source_timestamps: dict[str, datetime | None]) -> MarketSnapshot:
    if market_mode == MarketMode.SPOT and derivatives is not None:
        forbidden_non_null = {k: v for k, v in derivatives.items() if v is not None and k not in {"availability"}}
        if forbidden_non_null:
            raise ValueError("spot_snapshot_cannot_fabricate_derivatives_context")
    now = datetime.now(timezone.utc)
    snapshot_id = make_snapshot_id(symbol, event_time)
    alert_payload = None
    if breakout_alert is not None:
        alert_payload = dict(breakout_alert)
        alert_payload["snapshot_id"] = snapshot_id
    return MarketSnapshot(
        contract_version="HM_CRYPTO_V1", snapshot_id=snapshot_id, created_at_utc=now, event_time_utc=event_time,
        exchange=Exchange.BYBIT, environment=environment, market_mode=market_mode, symbol=symbol,
        instrument=instrument, ticker=ticker, timeframes=timeframes, structure=structure, levels=levels,
        volume_profile=volume_profile, orderflow=orderflow, orderbook=orderbook, derivatives=derivatives,
        regime=regime, breakout_alert=alert_payload, data_quality=data_quality, quality_reasons=quality_reasons,
        feature_versions=FEATURE_VERSIONS.copy(), source_timestamps=source_timestamps,
    )


def derivatives_context(market_mode: MarketMode, ticker: dict[str, Any], oi_rows: list[dict[str, Any]] | None, funding_rows: list[dict[str, Any]] | None, liquidations: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    if market_mode == MarketMode.SPOT:
        return {
            "mark_price": None, "index_price": None, "premium_basis": None, "open_interest": None,
            "oi_change": None, "funding_rate": None, "funding_time": None, "liquidations": None,
            "liquidation_intensity": None,
            "availability": {"derivatives_context": False, "reason": "SPOT_MODE"},
        }
    mark = ticker.get("markPrice") or ticker.get("mark_price")
    index = ticker.get("indexPrice") or ticker.get("index_price")
    mark_d = Decimal(str(mark)) if mark not in {None, ""} else None
    index_d = Decimal(str(index)) if index not in {None, ""} else None
    basis = ((mark_d - index_d) / index_d if mark_d is not None and index_d not in {None, Decimal("0")} else None)
    oi = None; oi_change = None
    if oi_rows:
        oi = Decimal(str(oi_rows[0].get("openInterest"))) if oi_rows[0].get("openInterest") is not None else None
        if len(oi_rows) > 1 and oi is not None and oi_rows[1].get("openInterest") is not None:
            prior = Decimal(str(oi_rows[1]["openInterest"]))
            oi_change = oi - prior
    funding_rate = Decimal(str(ticker["fundingRate"])) if ticker.get("fundingRate") not in {None, ""} else None
    funding_time = ticker.get("nextFundingTime")
    funding_history_latest = None
    if funding_rows:
        row = funding_rows[0]
        funding_history_latest = {
            "funding_rate": Decimal(str(row["fundingRate"])) if row.get("fundingRate") is not None else None,
            "funding_rate_timestamp": row.get("fundingRateTimestamp"),
        }
        if funding_rate is None:
            funding_rate = funding_history_latest["funding_rate"]
    intensity = None
    if liquidations is not None:
        intensity = sum((Decimal(str(x.get("v") or x.get("qty") or "0")) for x in liquidations), Decimal("0"))
    return {
        "mark_price": mark_d, "index_price": index_d, "premium_basis": basis, "open_interest": oi,
        "oi_change": oi_change, "funding_rate": funding_rate, "funding_time": funding_time,
        "funding_history_latest": funding_history_latest,
        "liquidations": liquidations, "liquidation_intensity": intensity,
        "availability": {
            "derivatives_context": True,
            "mark_index": mark_d is not None or index_d is not None,
            "open_interest": oi_rows is not None,
            "funding": funding_rows is not None,
            "liquidations": liquidations is not None,
        },
    }
