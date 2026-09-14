from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from ..config import StrategyConfig
from ..models import decimal_from, decimal_text, dotted_get


def projected_extension_target(
    snapshot: Mapping[str, Any], direction: str, config: StrategyConfig
) -> Decimal | None:
    origin_raw = dotted_get(snapshot, "structure.reengagement_origin")
    impulse_origin_raw = dotted_get(snapshot, "structure.impulse.origin_price")
    impulse_end_raw = dotted_get(snapshot, "structure.impulse.end_price")
    if origin_raw is None or impulse_origin_raw is None or impulse_end_raw is None:
        return None
    origin = decimal_from(origin_raw, name="reengagement_origin")
    impulse_origin = decimal_from(impulse_origin_raw, name="impulse.origin_price")
    impulse_end = decimal_from(impulse_end_raw, name="impulse.end_price")
    reference_length = abs(impulse_end - impulse_origin)
    mult = Decimal(str(config.continuation_projected_extension_mult))
    if direction == "LONG":
        return origin + reference_length * mult
    if direction == "SHORT":
        return origin - reference_length * mult
    return None


def build_target_plan(
    snapshot: Mapping[str, Any], direction: str, projected: Decimal | None, config: StrategyConfig
) -> tuple[tuple[dict[str, Any], ...], float | None, float, tuple[str, ...]]:
    entry_raw = dotted_get(snapshot, "levels.entry_reference") or dotted_get(snapshot, "ticker.last_price")
    stop_raw = dotted_get(snapshot, "levels.invalidation_price")
    if entry_raw is None or stop_raw is None:
        return (), None, 0.0, ("MISSING_ENTRY_OR_INVALIDATION",)
    entry = decimal_from(entry_raw, name="entry")
    stop = decimal_from(stop_raw, name="invalidation")
    risk = abs(entry - stop)
    if risk <= 0:
        return (), None, 0.0, ("INVALID_ZERO_RISK_DISTANCE",)

    obstacles_raw = dotted_get(snapshot, "levels.obstacles", [])
    obstacles: list[tuple[Decimal, float, str]] = []
    if isinstance(obstacles_raw, list):
        for row in obstacles_raw:
            if not isinstance(row, Mapping) or row.get("price") is None:
                continue
            try:
                price = decimal_from(row["price"], name="obstacle.price")
                strength = float(row.get("strength", 0.5))
                kind = str(row.get("type") or "STRUCTURAL_OBSTACLE")
            except (ValueError, TypeError):
                continue
            if direction == "LONG" and price > entry:
                obstacles.append((price, strength, kind))
            elif direction == "SHORT" and price < entry:
                obstacles.append((price, strength, kind))

    if direction == "LONG":
        obstacles.sort(key=lambda item: item[0])
    else:
        obstacles.sort(key=lambda item: item[0], reverse=True)

    chosen: Decimal | None = projected
    chosen_kind = "PROJECTED_EXTENSION"
    blockers: list[str] = []

    def obstacle_filter_enabled(kind: str) -> bool:
        normalized = kind.upper()
        if "LIQUIDITY" in normalized and not config.liquidity_wall_target_filter_enabled:
            return False
        if any(token in normalized for token in ("HTF", "MAJOR_SWING", "PRIOR_SESSION", "SESSION_EXTREME")) and not config.htf_target_filter_enabled:
            return False
        if any(token in normalized for token in ("HVN", "LVN", "POC", "VAH", "VAL", "VOLUME_NODE")) and not config.volume_node_target_filter_enabled:
            return False
        return True

    if config.target_obstacle_filter_enabled and obstacles:
        for price, strength, kind in obstacles:
            if not obstacle_filter_enabled(kind):
                continue
            before_projected = projected is None or (
                (direction == "LONG" and price < projected)
                or (direction == "SHORT" and price > projected)
            )
            if before_projected and strength >= 0.65:
                chosen = price
                chosen_kind = kind
                break

    if chosen is None:
        return (), None, 0.0, ("NO_TARGET_ROOM",)
    reward = (chosen - entry) if direction == "LONG" else (entry - chosen)
    rr = float(reward / risk)
    if rr <= 0:
        blockers.append("NO_TARGET_ROOM")
    room_score = max(0.0, min(100.0, rr / max(config.preferred_min_rr, 0.01) * 100.0))
    target = {
        "price": decimal_text(chosen),
        "type": chosen_kind,
        "theoretical_projected": bool(projected is not None and chosen == projected),
    }
    return (target,), rr, room_score, tuple(blockers)
