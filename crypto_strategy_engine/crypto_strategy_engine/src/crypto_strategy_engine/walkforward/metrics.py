from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Iterable, Mapping


def _safe_div(a: float, b: float) -> float | None:
    return None if b == 0 else a / b


def compute_metrics(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    data = list(rows)
    rs = [float(row.get("r", 0.0)) for row in data if row.get("r") is not None]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    current_dd_duration = 0
    max_dd_duration = 0
    for r in rs:
        equity += r
        peak = max(peak, equity)
        dd = peak - equity
        if dd > 0:
            current_dd_duration += 1
            max_dd_duration = max(max_dd_duration, current_dd_duration)
        else:
            current_dd_duration = 0
        max_dd = max(max_dd, dd)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    target_hit = sum(bool(row.get("target_hit")) for row in data)
    stop_hit = sum(bool(row.get("stop_hit")) for row in data)
    timeout = sum(bool(row.get("timeout")) for row in data)
    return {
        "trade_count": len(data),
        "win_rate": _safe_div(len(wins), len(rs)) if rs else None,
        "loss_rate": _safe_div(len(losses), len(rs)) if rs else None,
        "average_win_r": _safe_div(sum(wins), len(wins)) if wins else None,
        "average_loss_r": _safe_div(sum(losses), len(losses)) if losses else None,
        "expectancy_r": _safe_div(sum(rs), len(rs)) if rs else None,
        "profit_factor": _safe_div(gross_profit, gross_loss) if gross_loss else None,
        "median_r": median(rs) if rs else None,
        "total_r": sum(rs),
        "max_drawdown_r": max_dd,
        "drawdown_duration": max_dd_duration,
        "mfe": _safe_div(sum(float(row.get("mfe_r", 0.0)) for row in data), len(data)) if data else None,
        "mae": _safe_div(sum(float(row.get("mae_r", 0.0)) for row in data), len(data)) if data else None,
        "target_hit_rate": _safe_div(target_hit, len(data)) if data else None,
        "stop_hit_rate": _safe_div(stop_hit, len(data)) if data else None,
        "timeout_rate": _safe_div(timeout, len(data)) if data else None,
        "false_breakout_loss_rate": _safe_div(sum(bool(row.get("false_breakout_loss")) for row in data), len(data)) if data else None,
        "balance_trap_loss_rate": _safe_div(sum(bool(row.get("balance_trap_loss")) for row in data), len(data)) if data else None,
        "reversal_failure_rate": _safe_div(sum(bool(row.get("reversal_failure")) for row in data), len(data)) if data else None,
    }


def grouped_metrics(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key, "UNKNOWN"))].append(row)
    return {name: compute_metrics(group) for name, group in sorted(groups.items())}
