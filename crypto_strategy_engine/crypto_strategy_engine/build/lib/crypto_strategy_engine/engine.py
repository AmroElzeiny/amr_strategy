from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Mapping, Sequence

from .ai import AIGate
from .arbitration import arbitrate
from .blockers import build_blockers
from .calibration import calibrate_probability, fit_platt
from .config import StrategyConfig
from .evidence import build_evidence_catalog, data_quality_score
from .memory import TradeMemoryStore
from .models import Candidate, canonical_hash, clamp, decimal_text, dotted_get
from .observability import write_decision_log
from .patterns import breakout, continuation, pre_breakout, reversal
from .penalties import build_penalties
from .scoring import decision_from_confidence, deterministic_confidence, weighted_raw_score
from .targets import build_target_plan, projected_extension_target
from .thesis import ThesisStore, build_thesis_id
from .validation import schema_sha256, validate_market_snapshot


_PATTERN_DETECTORS = {
    "PRE_BREAKOUT": pre_breakout.detect,
    "BREAKOUT": breakout.detect,
    "CONTINUATION": continuation.detect,
    "REVERSAL": reversal.detect,
}


def _pattern_enabled(config: StrategyConfig, pattern: str) -> bool:
    return bool(getattr(config, f"{pattern.lower()}_enabled"))


def _pattern_enter_threshold(config: StrategyConfig, pattern: str) -> float:
    if pattern == "PRE_BREAKOUT":
        return max(config.enter_min_confidence, config.pre_breakout_min_confidence)
    if pattern == "BREAKOUT":
        return max(config.enter_min_confidence, config.breakout_min_confidence)
    if pattern == "REVERSAL":
        return max(config.enter_min_confidence, config.reversal_min_confidence)
    return config.enter_min_confidence


def _candidate_from_draft(
    snapshot: Mapping[str, Any],
    draft: Any,
    validation_blockers: tuple[str, ...],
    config: StrategyConfig,
    *,
    persist: bool,
) -> Candidate:
    thesis_id = build_thesis_id(snapshot, draft.pattern_type, draft.direction)
    attempt_no = 0
    if persist:
        thesis_store = ThesisStore(config.trade_memory_db + ".thesis")
        structural_identity = canonical_hash(
            {
                "major_structure_event": dotted_get(snapshot, "levels.major_structure_event_id"),
                "breakout_event_id": dotted_get(snapshot, "levels.breakout_event_id"),
                "reference_level": dotted_get(snapshot, "levels.reference_level"),
            }
        )
        thesis_store.record_seen(thesis_id, structural_identity)
        attempt_no = thesis_store.peek(thesis_id, max_attempts=config.max_strategy_attempts_per_thesis).attempt_no

    projected = None
    if draft.pattern_type == "CONTINUATION":
        projected = projected_extension_target(snapshot, draft.direction, config)
    elif dotted_get(snapshot, "levels.projected_target") is not None:
        from .models import decimal_from
        projected = decimal_from(dotted_get(snapshot, "levels.projected_target"), name="levels.projected_target")

    targets, rr, target_room, target_flags = build_target_plan(snapshot, draft.direction, projected, config)
    component_scores = dict(draft.component_scores)
    component_scores["data_quality_score"] = data_quality_score(snapshot)
    component_scores["target_quality"] = max(component_scores.get("target_quality", 0.0), target_room)

    penalties = build_penalties(
        snapshot,
        pattern_type=draft.pattern_type,
        direction=draft.direction,
        risk_reward=rr,
        missing_critical=list(draft.missing_critical),
        attempt_no=attempt_no,
        config=config,
    )
    blockers = list(build_blockers(
        snapshot,
        pattern_type=draft.pattern_type,
        direction=draft.direction,
        missing_critical=list(draft.missing_critical),
        risk_reward=rr,
        attempt_no=attempt_no,
        validation_blockers=validation_blockers,
        config=config,
    ))
    if not draft.eligible and not draft.missing_critical:
        from .models import Blocker
        blockers.append(Blocker("MISSING_REQUIRED_SETUP_EVIDENCE", "pattern_qualification_threshold_not_met"))
    if target_flags:
        from .models import Blocker
        if "NO_TARGET_ROOM" in target_flags and not any(b.code == "NO_TARGET_ROOM" for b in blockers):
            blockers.append(Blocker("NO_TARGET_ROOM", "target_engine_no_viable_target"))
    if (
        draft.pattern_type == "CONTINUATION"
        and target_room < config.continuation_min_target_score
        and not any(b.code == "NO_TARGET_ROOM" for b in blockers)
    ):
        from .models import Blocker
        blockers.append(Blocker("NO_TARGET_ROOM", "continuation_target_quality_below_minimum"))
    # Deduplicate blocker codes.
    blockers = list({b.code: b for b in blockers}.values())
    raw = weighted_raw_score(component_scores, config)
    det = deterministic_confidence(raw, penalties)
    identity_payload = {
        "snapshot_id": snapshot["snapshot_id"],
        "pattern_type": draft.pattern_type,
        "direction": draft.direction,
        "branch": draft.branch,
        "thesis_id": thesis_id,
        "entry_plan": draft.entry_plan,
        "invalidation": draft.invalidation,
        "targets": list(targets),
        "projected_extension_target": decimal_text(projected) if projected is not None else None,
        "config_hash": config.config_hash,
        "strategy_version": config.strategy_version,
    }
    candidate_hash = canonical_hash(identity_payload)
    candidate_id = "cand_" + candidate_hash[:24]
    strategic_risk_hint = "VERY_REDUCED" if det < 65 or blockers else "REDUCED" if det < 82 else "NORMAL"
    evidence = dict(draft.evidence)
    regime_type = str(dotted_get(snapshot, "regime.type", "UNKNOWN"))
    regime_compatibility = {
        "CONTINUATION": 100.0 if regime_type == "HEALTHY_PULLBACK" else 90.0 if regime_type == "TREND_EXPANSION" else 35.0 if regime_type in {"BALANCE", "RANGE"} else 50.0,
        "BREAKOUT": 100.0 if regime_type == "TREND_EXPANSION" else 72.0 if regime_type == "HEALTHY_PULLBACK" else 30.0 if regime_type in {"BALANCE", "RANGE"} else 50.0,
        "PRE_BREAKOUT": 88.0 if regime_type in {"TREND_EXPANSION", "HEALTHY_PULLBACK"} else 25.0 if regime_type in {"BALANCE", "RANGE"} else 50.0,
        "REVERSAL": 100.0 if regime_type == "REVERSAL_RISK" else 82.0 if regime_type == "FAILED_BREAKOUT" else 35.0,
    }.get(draft.pattern_type, 50.0)
    evidence.update({
        "pattern_eligible": draft.eligible,
        "branch": draft.branch,
        "regime_compatibility": regime_compatibility,
        "freshness_score": 100.0 if snapshot.get("data_quality") == "GOOD" else 60.0 if snapshot.get("data_quality") == "DEGRADED" else 20.0,
        "target_flags": list(target_flags),
        "config_hash": config.config_hash,
        "strategy_version": config.strategy_version,
        "feature_versions": snapshot.get("feature_versions", {}),
    })
    return Candidate(
        candidate_id=candidate_id,
        candidate_hash=candidate_hash,
        pattern_type=draft.pattern_type,
        direction=draft.direction,
        branch=draft.branch,
        thesis_id=thesis_id,
        attempt_no=attempt_no,
        component_scores=component_scores,
        raw_score=raw,
        penalties=penalties,
        blockers=tuple(blockers),
        deterministic_confidence=det,
        evidence=evidence,
        entry_plan=draft.entry_plan,
        invalidation=draft.invalidation,
        targets=targets,
        projected_extension_target=decimal_text(projected) if projected is not None else None,
        risk_reward=rr,
        pattern_maturity=draft.maturity,
        target_room=target_room,
        strategic_risk_hint=strategic_risk_hint,
    )


def evaluate_candidates(
    snapshot: Mapping[str, Any],
    config: StrategyConfig | None = None,
    *,
    persist: bool = False,
    now_utc: datetime | None = None,
) -> tuple[Candidate, ...]:
    cfg = config or StrategyConfig.from_env()
    validation = validate_market_snapshot(snapshot, cfg, now_utc=now_utc)
    frozen = validation.frozen
    candidates: list[Candidate] = []
    for pattern, detector in _PATTERN_DETECTORS.items():
        if not _pattern_enabled(cfg, pattern):
            continue
        draft = detector(frozen, cfg)
        # Keep meaningful detected drafts for diagnostics even when they are blocked.
        if draft.direction == "NONE" and not draft.evidence:
            continue
        candidates.append(_candidate_from_draft(frozen, draft, validation.blockers, cfg, persist=persist))
    return tuple(candidates)


def _tentative_decision(candidate: Candidate, config: StrategyConfig) -> str:
    decision = decision_from_confidence(candidate.deterministic_confidence, config, hard_blocked=bool(candidate.blockers))
    if decision == "ENTER" and candidate.deterministic_confidence < _pattern_enter_threshold(config, candidate.pattern_type):
        return "ARMED"
    return decision


def _empty_intent(snapshot: Mapping[str, Any], config: StrategyConfig, *, reason: str, blockers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    seed = {
        "snapshot_id": snapshot.get("snapshot_id"),
        "reason": reason,
        "config_hash": config.config_hash,
    }
    signal_id = "sig_" + canonical_hash(seed)[:24]
    intent: dict[str, Any] = {
        "contract_version": config.contract_version,
        "signal_id": signal_id,
        "snapshot_id": str(snapshot.get("snapshot_id") or ""),
        "created_at_utc": str(snapshot.get("created_at_utc") or snapshot.get("event_time_utc") or "1970-01-01T00:00:00Z"),
        "exchange": str(snapshot.get("exchange") or config.exchange),
        "environment": str(snapshot.get("environment") or config.trading_env),
        "market_mode": str(snapshot.get("market_mode") or config.market_mode),
        "symbol": str(snapshot.get("symbol") or ""),
        "pattern_type": "CONTINUATION",
        "direction": "NONE",
        "order_intent": "NONE",
        "decision": "NO_TRADE",
        "thesis_id": "",
        "attempt_no": 0,
        "deterministic_confidence": 0.0,
        "ai_confidence": None,
        "final_confidence": 0.0,
        "entry_plan": {},
        "invalidation": {},
        "targets": [],
        "projected_extension_target": None,
        "risk_reward": None,
        "penalties": [],
        "blockers": blockers or [{"code": reason, "reason": reason, "evidence_refs": []}],
        "evidence": {"reason": reason},
        "ttl_ms": config.trade_intent_ttl_ms,
        "config_version": config.config_version,
        "strategy_version": config.strategy_version,
        "ai_metadata": {"called": False, "route": [], "results": [], "failures": []},
        "integrity_hash": "",
    }
    intent["integrity_hash"] = canonical_hash({k: v for k, v in intent.items() if k != "integrity_hash"})
    return intent


def evaluate_snapshot(
    snapshot: Mapping[str, Any],
    config: StrategyConfig | None = None,
    *,
    ai_gate: AIGate | None = None,
    persist: bool = True,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    cfg = config or StrategyConfig.from_env()
    total_started = time.perf_counter()
    validation_started = time.perf_counter()
    validation = validate_market_snapshot(snapshot, cfg, now_utc=now_utc)
    frozen = validation.frozen
    validation_latency = (time.perf_counter() - validation_started) * 1000.0

    candidate_started = time.perf_counter()
    candidates = evaluate_candidates(frozen, cfg, persist=persist, now_utc=now_utc)
    candidate_latency = (time.perf_counter() - candidate_started) * 1000.0
    arbitration = arbitrate(candidates)
    selected = arbitration.selected
    if selected is None:
        intent = _empty_intent(frozen, cfg, reason="CONFLICTING_AUTHORITATIVE_EVIDENCE" if arbitration.conflict else "NO_VALID_CANDIDATE")
        if persist:
            write_decision_log(cfg.decision_log_dir, intent["signal_id"], {"intent": intent, "candidates": [c.to_dict() for c in candidates], "arbitration": arbitration.__dict__})
        return intent

    tentative = _tentative_decision(selected, cfg)
    catalog = build_evidence_catalog(frozen)

    # Historical evidence is strictly pre-candidate and advisory; insufficient sample is explicit.
    historical: dict[str, Any] = {"state": "DISABLED", "sample_count": 0}
    historical_adjustment = 0.0
    calibration_adjustment = 0.0
    calibration_context: dict[str, Any] = {"calibration_available": False, "sample_count": 0}
    memory: TradeMemoryStore | None = None
    if cfg.trade_memory_enabled and persist:
        memory = TradeMemoryStore(cfg.trade_memory_db)
        if cfg.historical_analogue_enabled:
            analogue_features = {
                "branch": selected.branch,
                "breakout_quality_band": f"{int(selected.component_scores.get('breakout_quality', 0.0) // 10) * 10}-{int(selected.component_scores.get('breakout_quality', 0.0) // 10) * 10 + 10}",
                "pullback_quality_band": f"{int(selected.component_scores.get('pullback_quality', 0.0) // 10) * 10}-{int(selected.component_scores.get('pullback_quality', 0.0) // 10) * 10 + 10}",
                "balance_risk_band": f"{int(float(selected.evidence.get('balance_risk_score', 0.0)) // 10) * 10}-{int(float(selected.evidence.get('balance_risk_score', 0.0)) // 10) * 10 + 10}",
                "value_migration": dotted_get(frozen, "volume_profile.value_migration", "UNAVAILABLE"),
                "orderflow_state": dotted_get(frozen, "orderflow.state", dotted_get(frozen, "orderflow.directional_state", "UNAVAILABLE")),
                "volatility_regime": dotted_get(frozen, "regime.volatility", dotted_get(frozen, "regime.volatility_regime", "UNAVAILABLE")),
                "liquidity_bucket": dotted_get(frozen, "instrument.liquidity_bucket", "UNKNOWN"),
                "session_bucket": dotted_get(frozen, "instrument.session_bucket", "UNKNOWN"),
                "symbol": frozen.get("symbol"),
            }
            historical = memory.historical_analogues(
                candidate_time_utc=str(frozen["event_time_utc"]),
                pattern=selected.pattern_type,
                direction=selected.direction,
                market_mode=str(frozen["market_mode"]),
                regime=str(dotted_get(frozen, "regime.type", "UNKNOWN")),
                min_sample=cfg.historical_analogue_min_sample,
                max_results=cfg.historical_analogue_max_results,
                candidate_features=analogue_features,
            )
            if historical.get("state") == "AVAILABLE":
                hit_rate = float(historical.get("empirical_target_hit_rate", 0.5))
                # Bounded empirical context; still not claimed as a calibrated probability.
                historical_adjustment = max(-5.0, min(5.0, (hit_rate - 0.5) * 10.0))
        if cfg.calibration_enabled:
            calibration_scores, calibration_outcomes = memory.calibration_samples(
                before_utc=str(frozen["event_time_utc"])
            )
            calibration_artifact = fit_platt(
                calibration_scores,
                calibration_outcomes,
                min_sample=cfg.calibration_min_sample,
            )
            calibrated_probability = calibrate_probability(
                selected.deterministic_confidence, calibration_artifact
            )
            calibration_context = calibration_artifact.to_dict()
            calibration_context["empirical_probability"] = calibrated_probability
            if calibrated_probability is not None:
                delta = calibrated_probability * 100.0 - selected.deterministic_confidence
                calibration_adjustment = max(
                    -cfg.calibration_max_adjustment,
                    min(cfg.calibration_max_adjustment, delta * 0.10),
                )

    ai_started = time.perf_counter()
    if selected.blockers or tentative == "NO_TRADE":
        from .ai.gate import AIGateOutcome
        ai_outcome = AIGateOutcome((), None, 0.0, False, (), (), False)
    else:
        gate = ai_gate or AIGate(cfg)
        ai_outcome = gate.assess(
            selected,
            tentative_decision=tentative,
            snapshot_id=str(frozen["snapshot_id"]),
            schema_hash=schema_sha256(),
            catalog=catalog,
            ttl_ms=cfg.trade_intent_ttl_ms,
            ambiguous=arbitration.ambiguous,
        )
    ai_latency = (time.perf_counter() - ai_started) * 1000.0

    final_conf = clamp(
        selected.deterministic_confidence
        + historical_adjustment
        + calibration_adjustment
        + ai_outcome.adjustment
    )
    final_decision = decision_from_confidence(final_conf, cfg, hard_blocked=bool(selected.blockers) or ai_outcome.veto)
    if final_decision == "ENTER" and final_conf < _pattern_enter_threshold(cfg, selected.pattern_type):
        final_decision = "ARMED"
    if ai_outcome.required_failed and final_decision == "ENTER":
        final_decision = "ARMED"
    if frozen["data_quality"] in {"INVALID", "STALE"} and final_decision == "ENTER":
        final_decision = "NO_TRADE"
    if frozen["data_quality"] == "DEGRADED" and not cfg.degraded_enter_allowed and final_decision == "ENTER":
        final_decision = "ARMED"
    if frozen["market_mode"] == "SPOT" and selected.direction == "SHORT" and final_decision == "ENTER":
        final_decision = "NO_TRADE"

    signal_seed = {
        "snapshot_id": frozen["snapshot_id"],
        "candidate_hash": selected.candidate_hash,
        "config_hash": cfg.config_hash,
        "strategy_version": cfg.strategy_version,
    }
    signal_id = "sig_" + canonical_hash(signal_seed)[:24]
    ai_metadata = {
        "called": bool(ai_outcome.route),
        "route": list(ai_outcome.route),
        "results": [r.to_dict() for r in ai_outcome.results],
        "failures": list(ai_outcome.failure_log),
        "required_failed": ai_outcome.required_failed,
        "routing_policy": "HM_AI_ROUTING_V1",
    }
    evidence = dict(selected.evidence)
    evidence.update({
        "historical_analogue": historical,
        "historical_adjustment": historical_adjustment,
        "calibration_context": calibration_context,
        "calibration_adjustment": calibration_adjustment,
        "arbitration_reason": arbitration.reason,
        "arbitration_ranking": list(arbitration.ranking),
        "strategic_risk_hint": selected.strategic_risk_hint,
        "evidence_catalog_hash": catalog.catalog_hash,
    })
    order_intent = "OPEN" if final_decision == "ENTER" else "NONE"
    intent = {
        "contract_version": cfg.contract_version,
        "signal_id": signal_id,
        "snapshot_id": str(frozen["snapshot_id"]),
        "created_at_utc": str(frozen["created_at_utc"]),
        "exchange": str(frozen["exchange"]),
        "environment": str(frozen["environment"]),
        "market_mode": str(frozen["market_mode"]),
        "symbol": str(frozen["symbol"]),
        "pattern_type": selected.pattern_type,
        "direction": selected.direction,
        "order_intent": order_intent,
        "decision": final_decision,
        "thesis_id": selected.thesis_id,
        "attempt_no": selected.attempt_no,
        "deterministic_confidence": round(selected.deterministic_confidence, 6),
        "ai_confidence": round(ai_outcome.ai_confidence, 6) if ai_outcome.ai_confidence is not None else None,
        "final_confidence": round(final_conf, 6),
        "entry_plan": selected.entry_plan,
        "invalidation": selected.invalidation,
        "targets": list(selected.targets),
        "projected_extension_target": selected.projected_extension_target,
        "risk_reward": round(selected.risk_reward, 8) if selected.risk_reward is not None else None,
        "penalties": [p.to_dict() for p in selected.penalties],
        "blockers": [b.to_dict() for b in selected.blockers],
        "evidence": evidence,
        "ttl_ms": cfg.trade_intent_ttl_ms,
        "config_version": cfg.config_version,
        "strategy_version": cfg.strategy_version,
        "ai_metadata": ai_metadata,
        "integrity_hash": "",
    }
    intent["integrity_hash"] = canonical_hash({k: v for k, v in intent.items() if k != "integrity_hash"})

    if persist:
        if final_decision == "ENTER":
            thesis_store = ThesisStore(cfg.trade_memory_db + ".thesis")
            thesis_store.record_attempt(selected.thesis_id, cooldown_sec=cfg.thesis_cooldown_sec)
        if memory is None and cfg.trade_memory_enabled:
            memory = TradeMemoryStore(cfg.trade_memory_db)
        if memory is not None:
            memory.record_decision(intent, selected.to_dict(), frozen)
        total_latency = (time.perf_counter() - total_started) * 1000.0
        write_decision_log(cfg.decision_log_dir, signal_id, {
            "snapshot_id": frozen["snapshot_id"],
            "signal_id": signal_id,
            "thesis_id": selected.thesis_id,
            "candidate_ids": [c.candidate_id for c in candidates],
            "pattern_candidates": [c.pattern_type for c in candidates],
            "blockers": intent["blockers"],
            "penalties": intent["penalties"],
            "component_scores": selected.component_scores,
            "deterministic_confidence": selected.deterministic_confidence,
            "ai_route": ai_metadata["route"],
            "ai_result": ai_metadata["results"],
            "final_confidence": final_conf,
            "final_decision": final_decision,
            "latency_ms": {
                "validation_latency": validation_latency,
                "candidate_generation_latency": candidate_latency,
                "ai_latency": ai_latency,
                "total_latency": total_latency,
            },
            "config_hash": cfg.config_hash,
            "integrity_hash": intent["integrity_hash"],
        })
    return intent


def ingest_execution_report(report: Mapping[str, Any], config: StrategyConfig | None = None) -> dict[str, Any]:
    cfg = config or StrategyConfig.from_env()
    return TradeMemoryStore(cfg.trade_memory_db).ingest_execution_report(report)


def run_walkforward(records: Sequence[Mapping[str, Any]], config: StrategyConfig | None = None, *, output_dir: str | None = None) -> dict[str, Any]:
    from .walkforward import run_walkforward as _run
    cfg = config or StrategyConfig.from_env()
    return _run(records, config=cfg, output_dir=output_dir)


def get_champion_config(config: StrategyConfig | None = None) -> dict[str, Any]:
    cfg = config or StrategyConfig.from_env()
    return {
        "config_version": cfg.config_version,
        "strategy_version": cfg.strategy_version,
        "config_hash": cfg.config_hash,
        "auto_promote": cfg.walkforward_auto_promote,
    }
