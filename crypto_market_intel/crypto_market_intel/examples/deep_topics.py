from __future__ import annotations

from datetime import datetime, timedelta, timezone

from crypto_market_intel.config import Settings
from crypto_market_intel.engine import MarketIntelEngine


def main() -> None:
    settings = Settings.from_env()
    engine = MarketIntelEngine(settings)
    engine.scout.watch_registry.promote(
        "BTCUSDT",
        datetime.now(timezone.utc) + timedelta(minutes=30),
        "example_breakout_watch",
    )
    print(engine.deep_public_topics())
    engine.adapter.close()


if __name__ == "__main__":
    main()
