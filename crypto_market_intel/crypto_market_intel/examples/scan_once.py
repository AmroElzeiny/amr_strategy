from __future__ import annotations

from crypto_market_intel.bybit import BybitV5PublicAdapter
from crypto_market_intel.config import Settings
from crypto_market_intel.engine import MarketIntelEngine


def main() -> None:
    settings = Settings.from_env()
    adapter = BybitV5PublicAdapter(settings)
    try:
        engine = MarketIntelEngine(settings, adapter=adapter)
        scan, alerts = engine.scan_cycle()
        print("gainers", scan.gainers)
        print("losers", scan.losers)
        print("highest_turnover", scan.highest_turnover)
        print("deep_watch_symbols", engine.deep_watch_symbols())
        print("breakout_alerts", [x.model_dump(mode="json") for x in alerts])
    finally:
        adapter.close()


if __name__ == "__main__":
    main()
