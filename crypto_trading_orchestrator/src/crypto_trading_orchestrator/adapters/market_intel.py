from __future__ import annotations

from typing import Any

from ..canonical import primitive_dict


class MarketIntelAdapter:
    """Thin invocation adapter; all scanning and intelligence remain in Package 1."""

    def __init__(self, engine: Any) -> None:
        for method in ("scan_cycle", "deep_watch_symbols", "build_deep_snapshot"):
            if not callable(getattr(engine, method, None)):
                raise ValueError(f"MARKET_METHOD_MISSING:{method}")
        self.engine = engine

    @classmethod
    def from_runtime(cls) -> MarketIntelAdapter:
        from crypto_market_intel.config import Settings
        from crypto_market_intel.engine import MarketIntelEngine

        return cls(MarketIntelEngine(Settings.from_env()))

    def scan_once(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        scan, alerts = self.engine.scan_cycle()
        return primitive_dict(scan), [primitive_dict(alert) for alert in alerts]

    def deep_watch_symbols(self) -> tuple[str, ...]:
        return tuple(str(value) for value in self.engine.deep_watch_symbols())

    def build_snapshot(self, symbol: str, alert: Any = None) -> dict[str, Any]:
        return primitive_dict(self.engine.build_deep_snapshot(symbol, breakout_alert=alert))
