from __future__ import annotations

import asyncio

from crypto_trading_orchestrator.events import PriorityEventBus
from crypto_trading_orchestrator.models import Event, EventType, Priority


def _event(kind: EventType, priority: Priority, symbol: str, marker: int) -> Event:
    return Event(kind, priority, "run", "test", symbol=symbol, payload={"marker": marker})


def test_critical_lane_preempts_and_never_evicts() -> None:
    async def scenario() -> None:
        bus = PriorityEventBus(1)
        await bus.publish(_event(EventType.MARKET_SNAPSHOT_READY, Priority.MARKET_DEEP_WATCH, "BTCUSDT", 1))
        await bus.publish(_event(EventType.MARKET_SNAPSHOT_READY, Priority.MARKET_DEEP_WATCH, "ETHUSDT", 2))
        await bus.publish(_event(EventType.POSITION_CLOSED, Priority.EXECUTION_PROTECTION, "BTCUSDT", 3))
        assert (await bus.get()).payload["marker"] == 3
        assert (await bus.get()).payload["marker"] == 2
        assert bus.stats().evicted == 1

    asyncio.run(scenario())


def test_market_snapshots_coalesce_by_symbol() -> None:
    async def scenario() -> None:
        bus = PriorityEventBus(2)
        await bus.publish(_event(EventType.MARKET_SNAPSHOT_READY, Priority.MARKET_DEEP_WATCH, "BTCUSDT", 1))
        await bus.publish(_event(EventType.MARKET_SNAPSHOT_READY, Priority.MARKET_DEEP_WATCH, "BTCUSDT", 2))
        assert bus.qsize() == 1
        assert (await bus.get()).payload["marker"] == 2
        assert bus.stats().coalesced == 1

    asyncio.run(scenario())
