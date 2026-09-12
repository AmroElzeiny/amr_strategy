from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta
from pathlib import Path
import csv
import json
from statistics import pstdev
from typing import Any, Callable, Mapping, Sequence

from ..calibration import fit_platt
from ..config import StrategyConfig
from ..models import canonical_hash
from ..persistence import atomic_write_json
from ..research import build_ai_research_artifact
from .metrics import compute_metrics, grouped_metrics

WALKFORWARD_VERSION = "HM_WALKFORWARD_V1"
ABLATION_FEATURES = {
    "balance_detector": [
        "structure.alternating_micro_bos",
        "volume_profile.poc_stagnation_score",
        "volume_profile.horizontal_value_score",
    ],
    "value_migration": ["volume_profile.value_migration_score", "volume_profile.poc_migration_score"],
    "orderflow_confirmation": ["orderflow.directional_delta_score", "orderflow.imbalance_score", "orderflow.absorption_score"],
    "open_interest_context": ["derivatives.open_interest_context_score"],
    "liquidity_obstacle_penalty": ["orderbook.liquidity_wall_ahead_score", "levels.obstacle_score"],
}


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _delete_path(data: dict[str, Any], path: str) -> None:
    parts = path.split(".")
    cur: Any = data
    for part in parts[:-1]:
        if not isinstance(cur, dict) or part not in cur:
            return
        cur = cur[part]
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def time_ordered_windows(
    records: Sequence[Mapping[str, Any]], config: StrategyConfig
) -> list[dict[str, list[Mapping[str, Any]]]]:
    ordered = sorted(records, key=lambda row: str(row["event_time_utc"]))
    if not ordered:
        return []
    start = _parse_time(str(ordered[0]["event_time_utc"]))
    end = _parse_time(str(ordered[-1]["event_time_utc"]))
    windows: list[dict[str, list[Mapping[str, Any]]]] = []
    cursor = start
    while True:
        train_end = cursor + timedelta(days=config.walkforward_train_days)
        validation_end = train_end + timedelta(days=config.walkforward_validation_days)
        test_end = validation_end + timedelta(days=config.walkforward_test_days)
        if test_end > end + timedelta(seconds=1):
            break
        train = [row for row in ordered if cursor <= _parse_time(str(row["event_time_utc"])) < train_end]
        validation = [row for row in ordered if train_end <= _parse_time(str(row["event_time_utc"])) < validation_end]
        test = [row for row in ordered if validation_end <= _parse_time(str(row["event_time_utc"])) < test_end]
        windows.append({"train": train, "validation": validation, "test": test})
        cursor += timedelta(days=config.walkforward_step_days)
    return windows


def no_lookahead_audit(records: Sequence[Mapping[str, Any]], windows: list[dict[str, list[Mapping[str, Any]]]]) -> dict[str, Any]:
    violations: list[str] = []
    for index, row in enumerate(records):
        event = _parse_time(str(row["event_time_utc"]))
        snapshot = row.get("snapshot")
        if isinstance(snapshot, Mapping):
            for source, raw in (snapshot.get("source_timestamps") or {}).items():
                if raw is not None and _parse_time(str(raw)) > event:
                    violations.append(f"record_{index}:future_source:{source}")
        outcome = row.get("outcome")
        if isinstance(outcome, Mapping) and outcome.get("resolved_at_utc") and _parse_time(str(outcome["resolved_at_utc"])) <= event:
            violations.append(f"record_{index}:outcome_not_after_signal")
    for idx, window in enumerate(windows):
        if window["train"] and window["validation"]:
            if max(_parse_time(str(r["event_time_utc"])) for r in window["train"]) >= min(_parse_time(str(r["event_time_utc"])) for r in window["validation"]):
                violations.append(f"window_{idx}:train_validation_overlap")
        if window["validation"] and window["test"]:
            if max(_parse_time(str(r["event_time_utc"])) for r in window["validation"]) >= min(_parse_time(str(r["event_time_utc"])) for r in window["test"]):
                violations.append(f"window_{idx}:validation_test_overlap")
    return {"passed": not violations, "violations": violations}


def _record_result(row: Mapping[str, Any], config: StrategyConfig, *, ablate: list[str] | None = None) -> dict[str, Any]:
    from ..engine import evaluate_snapshot

    snapshot = json.loads(json.dumps(row["snapshot"]))
    for path in ablate or []:
        _delete_path(snapshot, path)
    research_config = replace(
        config,
        ai_enabled=False,
        ai_required_for_enter=False,
        trade_memory_enabled=False,
        fail_on_stale_critical_data=False,
        max_snapshot_age_ms=10**12,
    )
    result = evaluate_snapshot(snapshot, config=research_config, persist=False, now_utc=_parse_time(str(row["event_time_utc"])))
    intent = result["trade_intent"] if isinstance(result, Mapping) and "trade_intent" in result else result
    outcome = row.get("outcome") if isinstance(row.get("outcome"), Mapping) else {}
    r = outcome.get("theoretical_r")
    if r is None:
        if outcome.get("target_hit"):
            r = intent.get("risk_reward") or 1.0
        elif outcome.get("stop_hit"):
            r = -1.0
        else:
            r = 0.0
    return {
        "event_time_utc": row["event_time_utc"],
        "pattern": intent.get("pattern_type"),
        "pattern_branch": intent.get("evidence", {}).get("branch", "UNKNOWN"),
        "regime": snapshot.get("regime", {}).get("type", "UNKNOWN"),
        "direction": intent.get("direction"),
        "symbol": snapshot.get("symbol"),
        "liquidity_bucket": snapshot.get("instrument", {}).get("liquidity_bucket", "UNKNOWN"),
        "session_bucket": snapshot.get("instrument", {}).get("session_bucket", "UNKNOWN"),
        "market_mode": snapshot.get("market_mode"),
        "confidence_band": "HIGH" if float(intent.get("final_confidence", 0)) >= 78 else "MEDIUM" if float(intent.get("final_confidence", 0)) >= 65 else "LOW",
        "score_band": int(float(intent.get("final_confidence", 0)) // 10 * 10),
        "breakout_type": snapshot.get("breakout_alert", {}).get("breakout_type", "UNKNOWN"),
        "retest_type": snapshot.get("levels", {}).get("primary_retest_type", "UNKNOWN"),
        "confidence": float(intent.get("final_confidence", 0)),
        "decision": intent.get("decision"),
        "trade_eligible": intent.get("decision") == "ENTER",
        "r": float(r),
        "mfe_r": float(outcome.get("mfe_r", 0.0)),
        "mae_r": float(outcome.get("mae_r", 0.0)),
        "target_hit": bool(outcome.get("target_hit")),
        "stop_hit": bool(outcome.get("stop_hit")),
        "timeout": bool(outcome.get("timeout")),
        "false_breakout_loss": bool(outcome.get("false_breakout_loss")),
        "balance_trap_loss": bool(outcome.get("balance_trap_loss")),
        "reversal_failure": bool(outcome.get("reversal_failure")),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_walkforward(
    records: Sequence[Mapping[str, Any]],
    *,
    config: StrategyConfig | None = None,
    output_dir: str | Path | None = None,
    ai_research_interpreter: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    cfg = config or StrategyConfig.from_env()
    ordered = sorted(records, key=lambda row: str(row["event_time_utc"]))
    windows = time_ordered_windows(ordered, cfg)
    audit = no_lookahead_audit(ordered, windows)
    if not audit["passed"]:
        raise ValueError("walkforward_lookahead_violation:" + ";".join(audit["violations"]))
    all_test_rows: list[dict[str, Any]] = []
    window_reports: list[dict[str, Any]] = []
    train_scores: list[float] = []
    train_outcomes: list[int] = []
    for idx, window in enumerate(windows):
        train_all = [_record_result(row, cfg) for row in window["train"]]
        validation_all = [_record_result(row, cfg) for row in window["validation"]]
        test_all = [_record_result(row, cfg) for row in window["test"]]
        train_rows = [row for row in train_all if row["trade_eligible"]]
        validation_rows = [row for row in validation_all if row["trade_eligible"]]
        test_rows = [row for row in test_all if row["trade_eligible"]]
        all_test_rows.extend(test_rows)
        train_scores.extend(float(row["confidence"]) for row in train_rows)
        train_outcomes.extend(1 if float(row["r"]) > 0 else 0 for row in train_rows)
        window_reports.append(
            {
                "window": idx,
                "train": compute_metrics(train_rows),
                "validation": compute_metrics(validation_rows),
                "test": compute_metrics(test_rows),
                "signal_counts": {
                    "train": len(train_rows),
                    "validation": len(validation_rows),
                    "test": len(test_rows),
                },
                "eligible_sample": len(test_rows) >= cfg.walkforward_min_trades,
            }
        )
    metrics = compute_metrics(all_test_rows)
    pattern_metrics = grouped_metrics(all_test_rows, "pattern")
    regime_metrics = grouped_metrics(all_test_rows, "regime")
    confidence_metrics = grouped_metrics(all_test_rows, "confidence_band")
    calibration = fit_platt(train_scores, train_outcomes, min_sample=cfg.calibration_min_sample)

    ablations: list[dict[str, Any]] = []
    if cfg.walkforward_ablation_enabled and ordered:
        baseline_all = [_record_result(row, cfg) for row in ordered]
        baseline = [row for row in baseline_all if row["trade_eligible"]]
        baseline_expectancy = compute_metrics(baseline).get("expectancy_r")
        for name, paths in ABLATION_FEATURES.items():
            ablated_all = [_record_result(row, cfg, ablate=paths) for row in ordered]
            ablated = [row for row in ablated_all if row["trade_eligible"]]
            ablated_metrics = compute_metrics(ablated)
            expectancy = ablated_metrics.get("expectancy_r")
            impact = None if baseline_expectancy is None or expectancy is None else float(baseline_expectancy) - float(expectancy)
            ablations.append(
                {
                    "feature": name,
                    "sample_size": len(ablated),
                    "baseline_expectancy_r": baseline_expectancy,
                    "ablated_expectancy_r": expectancy,
                    "oos_impact_r": impact,
                    "stability": "INSUFFICIENT_SAMPLE" if len(ablated) < cfg.walkforward_min_trades else "MEASURED",
                }
            )

    champion = {
        "version": cfg.config_version,
        "config_hash": cfg.config_hash,
        "config": asdict(cfg),
        "source": "current_live_configuration",
    }
    challenger_config = asdict(cfg)
    # Bounded one-dimensional research proposal; no blind combinatorial optimization.
    if metrics.get("expectancy_r") is not None and float(metrics["expectancy_r"]) < 0:
        challenger_config["enter_min_confidence"] = min(95.0, cfg.enter_min_confidence + 3.0)
        challenger_reason = "raise_enter_threshold_by_3_due_negative_oos_expectancy"
    else:
        challenger_config["enter_min_confidence"] = cfg.enter_min_confidence
        challenger_reason = "retain_enter_threshold_no_oos_evidence_for_change"
    challenger_cfg = replace(cfg, enter_min_confidence=float(challenger_config["enter_min_confidence"]))
    oos_records = [row for window in windows for row in window["test"]]
    challenger_all = [_record_result(row, challenger_cfg) for row in oos_records]
    challenger_rows = [row for row in challenger_all if row["trade_eligible"]]
    challenger_metrics = compute_metrics(challenger_rows)
    challenger_pattern_metrics = grouped_metrics(challenger_rows, "pattern")
    challenger_regime_metrics = grouped_metrics(challenger_rows, "regime")

    baseline_window_expectancies = [
        float(report["test"]["expectancy_r"])
        for report in window_reports
        if report["test"].get("expectancy_r") is not None
    ]
    challenger_window_metrics: list[dict[str, Any]] = []
    challenger_window_expectancies: list[float] = []
    for idx, window in enumerate(windows):
        rows_all = [_record_result(row, challenger_cfg) for row in window["test"]]
        active = [row for row in rows_all if row["trade_eligible"]]
        wm = compute_metrics(active)
        challenger_window_metrics.append({"window": idx, "test": wm, "signal_count": len(active)})
        if wm.get("expectancy_r") is not None:
            challenger_window_expectancies.append(float(wm["expectancy_r"]))

    baseline_stability = (
        pstdev(baseline_window_expectancies) if len(baseline_window_expectancies) >= 2 else 0.0
    )
    challenger_stability = (
        pstdev(challenger_window_expectancies) if len(challenger_window_expectancies) >= 2 else 0.0
    )

    subgroup_regressions: list[dict[str, Any]] = []
    for group_name, baseline_groups, challenger_groups in (
        ("pattern", pattern_metrics, challenger_pattern_metrics),
        ("regime", regime_metrics, challenger_regime_metrics),
    ):
        for subgroup, base_metrics in baseline_groups.items():
            chall_metrics = challenger_groups.get(subgroup)
            if chall_metrics is None:
                continue
            base_exp = base_metrics.get("expectancy_r")
            chall_exp = chall_metrics.get("expectancy_r")
            if base_exp is None or chall_exp is None:
                continue
            regression = float(base_exp) - float(chall_exp)
            subgroup_regressions.append(
                {
                    "group": group_name,
                    "subgroup": subgroup,
                    "baseline_expectancy_r": base_exp,
                    "challenger_expectancy_r": chall_exp,
                    "regression_r": regression,
                }
            )
    max_subgroup_regression = max(
        (float(row["regression_r"]) for row in subgroup_regressions),
        default=0.0,
    )
    window_consistency = bool(challenger_window_expectancies) and all(
        value >= cfg.walkforward_min_window_expectancy_r for value in challenger_window_expectancies
    )

    challenger = {
        "version": cfg.config_version + "_CHALLENGER_1",
        "config_hash": canonical_hash(challenger_config),
        "config": challenger_config,
        "reason": challenger_reason,
        "oos_metrics": challenger_metrics,
        "oos_pattern_metrics": challenger_pattern_metrics,
        "oos_regime_metrics": challenger_regime_metrics,
        "window_metrics": challenger_window_metrics,
    }
    criteria = {
        "minimum_oos_sample": int(challenger_metrics.get("trade_count") or 0) >= cfg.walkforward_min_trades,
        "positive_expectancy": challenger_metrics.get("expectancy_r") is not None
        and float(challenger_metrics["expectancy_r"]) > 0,
        "acceptable_drawdown": challenger_metrics.get("max_drawdown_r") is not None
        and float(challenger_metrics["max_drawdown_r"]) <= cfg.walkforward_max_drawdown_r,
        "improved_or_non_inferior_stability": challenger_stability <= baseline_stability,
        "no_catastrophic_subgroup_regression": max_subgroup_regression
        <= cfg.walkforward_max_subgroup_regression_r,
        "consistency_across_windows": window_consistency and len(challenger_window_expectancies) >= 2,
        "no_integrity_failures": audit["passed"],
        "auto_promotion_enabled": cfg.walkforward_auto_promote,
    }
    promotion_eligible = all(
        value for key, value in criteria.items() if key != "auto_promotion_enabled"
    )
    summary = {
        "walkforward_version": WALKFORWARD_VERSION,
        "window_count": len(windows),
        "no_lookahead_audit": audit,
        "metrics": metrics,
        "pattern_metrics": pattern_metrics,
        "regime_metrics": regime_metrics,
        "confidence_band_metrics": confidence_metrics,
        "calibration": calibration.to_dict(),
        "feature_ablation": ablations,
        "champion_config": champion,
        "challenger_config": challenger,
        "challenger_promotion_criteria": criteria,
        "challenger_promotion_eligible": promotion_eligible,
        "challenger_stability": challenger_stability,
        "champion_stability": baseline_stability,
        "subgroup_regressions": subgroup_regressions,
        "max_subgroup_regression_r": max_subgroup_regression,
        "auto_promoted": False,
        "window_reports": window_reports,
        "metric_semantics": "signal_walkforward_theoretical_R_not_realized_PnL_without_execution_feedback",
    }
    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        atomic_write_json(out / "walkforward_summary.json", summary)
        _write_csv(out / "walkforward_metrics.csv", [metrics])
        _write_csv(out / "pattern_metrics.csv", [{"pattern": key, **value} for key, value in pattern_metrics.items()])
        _write_csv(out / "regime_metrics.csv", [{"regime": key, **value} for key, value in regime_metrics.items()])
        atomic_write_json(out / "confidence_calibration.json", calibration.to_dict())
        _write_csv(out / "feature_ablation.csv", ablations)
        _write_csv(out / "failure_mode_analysis.csv", [
            {
                "false_breakout_loss_rate": metrics.get("false_breakout_loss_rate"),
                "balance_trap_loss_rate": metrics.get("balance_trap_loss_rate"),
                "reversal_failure_rate": metrics.get("reversal_failure_rate"),
            }
        ])
        atomic_write_json(out / "champion_config.json", champion)
        atomic_write_json(out / "challenger_config.json", challenger)
        research_artifact = build_ai_research_artifact(
            summary,
            ai_interpreter=ai_research_interpreter if cfg.walkforward_ai_research_enabled else None,
        )
        atomic_write_json(out / "ai_research_hypotheses.json", research_artifact)
    return summary
