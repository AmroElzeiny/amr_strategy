from __future__ import annotations

import asyncio
import heapq
from collections import deque
from dataclasses import dataclass
from typing import Any

from ..models import Event, Priority


@dataclass(frozen=True)
class EventBusStats:
    critical_depth: int
    market_depth: int
    coalesced: int
    evicted: int
    published: int
    delivered: int


class PriorityEventBus:
    """Priority bus with a lossless critical lane and bounded/coalesced market lane."""

    def __init__(self, market_capacity: int = 1000, *, coalesce_market: bool = True) -> None:
        if market_capacity <= 0:
            raise ValueError("market_capacity_must_be_positive")
        self.market_capacity = market_capacity
        self.coalesce_market = coalesce_market
        self._critical: list[tuple[int, int, Event]] = []
        self._market: dict[tuple[str, str], tuple[int, Event]] = {}
        self._market_fifo: deque[tuple[str, str]] = deque()
        self._sequence = 0
        self._coalesced = 0
        self._evicted = 0
        self._published = 0
        self._delivered = 0
        self._condition = asyncio.Condition()

    @staticmethod
    def _is_critical(event: Event) -> bool:
        return event.priority <= Priority.STRATEGY_ENTER

    async def publish(self, event: Event) -> None:
        async with self._condition:
            self._sequence += 1
            self._published += 1
            if self._is_critical(event):
                heapq.heappush(self._critical, (int(event.priority), self._sequence, event))
            else:
                key = (str(event.event_type), event.symbol) if self.coalesce_market else (event.event_id, "")
                if key in self._market:
                    self._coalesced += 1
                    self._market[key] = (self._sequence, event)
                else:
                    if len(self._market) >= self.market_capacity:
                        self._evict_oldest_market()
                    self._market[key] = (self._sequence, event)
                    self._market_fifo.append(key)
            self._condition.notify()

    def _evict_oldest_market(self) -> None:
        while self._market_fifo:
            key = self._market_fifo.popleft()
            if key in self._market:
                del self._market[key]
                self._evicted += 1
                return

    async def get(self) -> Event:
        async with self._condition:
            await self._condition.wait_for(lambda: bool(self._critical or self._market))
            if self._critical:
                event = heapq.heappop(self._critical)[2]
            else:
                event = self._pop_market()
            self._delivered += 1
            return event

    def get_nowait(self) -> Event:
        if self._critical:
            self._delivered += 1
            return heapq.heappop(self._critical)[2]
        if self._market:
            self._delivered += 1
            return self._pop_market()
        raise asyncio.QueueEmpty

    def _pop_market(self) -> Event:
        while self._market_fifo:
            key = self._market_fifo.popleft()
            row = self._market.pop(key, None)
            if row is not None:
                return row[1]
        raise asyncio.QueueEmpty

    def empty(self) -> bool:
        return not self._critical and not self._market

    def qsize(self) -> int:
        return len(self._critical) + len(self._market)

    def stats(self) -> EventBusStats:
        return EventBusStats(
            critical_depth=len(self._critical),
            market_depth=len(self._market),
            coalesced=self._coalesced,
            evicted=self._evicted,
            published=self._published,
            delivered=self._delivered,
        )

    def snapshot(self) -> dict[str, Any]:
        stats = self.stats()
        return {
            "critical_depth": stats.critical_depth,
            "market_depth": stats.market_depth,
            "coalesced": stats.coalesced,
            "evicted": stats.evicted,
            "published": stats.published,
            "delivered": stats.delivered,
        }
