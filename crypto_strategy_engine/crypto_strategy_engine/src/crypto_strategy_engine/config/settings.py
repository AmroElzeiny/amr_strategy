from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from typing import Mapping

from ..models import CONFIG_VERSION, STRATEGY_VERSION, canonical_hash


def _bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{key}:invalid_boolean")


def _float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(str(raw).strip())
    except ValueError as exc:
        raise ValueError(f"{key}:invalid_float") from exc


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(str(raw).strip())
    except ValueError as exc:
        raise ValueError(f"{key}:invalid_integer") from exc


def _text(env: Mapping[str, str], key: str, default: str) -> str:
    raw = env.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip()


def _csv_floats(env: Mapping[str, str], key: str, default: tuple[float, ...]) -> tuple[float, ...]:
    raw = env.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    values: list[float] = []
    for item in str(raw).split(","):
        text = item.strip()
        if not text:
            continue
        try:
            values.append(float(text))
        except ValueError as exc:
            raise ValueError(f"{key}:invalid_csv_float") from exc
    if not values:
        raise ValueError(f"{key}:empty_csv_float")
    return tuple(values)


@dataclass(frozen=True)
class StrategyConfig:
    contract_version: str = "HM_CRYPTO_V1"
    exchange: str = "BYBIT"
    trading_env: str = "DEMO"
    market_mode: str = "DERIVATIVES"
    strategy_version: str = STRATEGY_VERSION
    config_version: str = CONFIG_VERSION
    strategy_timeframe_policy: str = "AUTO_MULTI_TF"

    pre_breakout_enabled: bool = True
    breakout_enabled: bool = True
    continuation_enabled: bool = True
    reversal_enabled: bool = True
    primary_pattern: str = "CONTINUATION"

    watch_min_confidence: float = 45.0
    armed_min_confidence: float = 65.0
    enter_min_confidence: float = 78.0
    pre_breakout_min_confidence: float = 84.0
    breakout_min_confidence: float = 78.0
    reversal_min_confidence: float = 80.0
    min_acceptable_rr: float = 0.80
    preferred_min_rr: float = 1.00
    trade_intent_ttl_ms: int = 45_000

    continuation_require_reengagement: bool = True
    continuation_projected_extension_mult: float = 1.60
    continuation_fib_levels: tuple[float, ...] = (0.50, 0.618, 0.786)
    continuation_fvg_levels: tuple[float, ...] = (0.0, 0.25, 0.50, 0.75, 1.0)
    continuation_max_minor_pullback_entries: int = 2
    continuation_min_breakout_score: float = 62.0
    continuation_min_pullback_score: float = 55.0
    continuation_min_location_score: float = 45.0
    continuation_min_reengagement_score: float = 55.0
    continuation_min_target_score: float = 45.0

    pre_breakout_min_level_strength: float = 62.0
    pre_breakout_min_compression_score: float = 62.0
    pre_breakout_min_directional_pressure: float = 58.0

    breakout_require_acceptance: bool = True
    breakout_require_followthrough: bool = True
    breakout_immediate_entry_enabled: bool = True
    breakout_first_pullback_enabled: bool = True
    breakout_second_pullback_enabled: bool = True
    breakout_major_pullback_reentry_enabled: bool = True

    reversal_require_liquidity_event: bool = True
    reversal_require_opposite_displacement: bool = True
    reversal_require_micro_confirmation: bool = True

    balance_hard_block_enabled: bool = True
    balance_hard_block_score: float = 76.0
    chop_hard_block_score: float = 75.0
    failed_breakout_hard_block_enabled: bool = True
    failed_breakout_hard_block_score: float = 76.0
    reversal_risk_block_score: float = 78.0

    max_strategy_attempts_per_thesis: int = 2
    thesis_cooldown_sec: int = 900
    thesis_reset_require_major_event: bool = True

    target_obstacle_filter_enabled: bool = True
    liquidity_wall_target_filter_enabled: bool = True
    htf_target_filter_enabled: bool = True
    volume_node_target_filter_enabled: bool = True

    ai_enabled: bool = True
    ai_provider_select: str = "opencode"
    ai_required_for_enter: bool = True
    ai_max_positive_adjustment: float = 5.0
    ai_max_negative_adjustment: float = 20.0
    ai_call_min_deterministic_confidence: float = 45.0
    ai_total_deadline_ms: int = 6_000
    ai_provider_timeout_ms: int = 2_500
    ai_max_retries: int = 1
    ai_late_response_policy: str = "IGNORE"
    opencode_routing_enabled: bool = True
    opencode_dual_review_enabled: bool = True
    ai_adjudicator_enabled: bool = True
    opencode_go_base_url: str = "https://opencode.ai/zen/go"
    opencode_qwen_model: str = "qwen3.8-flash"
    opencode_muse_model: str = "muse-spark-1.3-contributor"
    ai_analyst_model: str = "muse-spark-1.3-contributor"
    ai_critic_model: str = "qwen3.8-flash"
    ai_adjudicator_model: str = "qwen3.8-flash"
    openai_base_url: str = "https://api.openai.com"
    openai_fallback_enabled: bool = True
    openai_fallback_model: str = "gpt-5.6-luna"
    openai_reasoning_effort: str = "low"
    openai_service_tier: str = "flex"
    openai_timeout_sec: float = 4.0
    openai_max_output_tokens: int = 1_500

    calibration_enabled: bool = True
    calibration_min_sample: int = 100
    calibration_max_adjustment: float = 5.0
    historical_analogue_enabled: bool = True
    historical_analogue_min_sample: int = 20
    historical_analogue_max_results: int = 12

    walkforward_enabled: bool = True
    walkforward_train_days: int = 30
    walkforward_validation_days: int = 7
    walkforward_test_days: int = 7
    walkforward_step_days: int = 7
    walkforward_min_trades: int = 20
    walkforward_max_drawdown_r: float = 12.0
    walkforward_max_subgroup_regression_r: float = 0.75
    walkforward_min_window_expectancy_r: float = -0.25
    walkforward_auto_promote: bool = False
    walkforward_ai_research_enabled: bool = True
    walkforward_ablation_enabled: bool = True
    walkforward_calibration_enabled: bool = True

    trade_memory_enabled: bool = True
    trade_memory_db: str = "./data/trade_memory.db"
    data_dir: str = "./data"
    decision_log_dir: str = "./data/decisions"
    research_dir: str = "./data/research"
    quarantine_dir: str = "./data/quarantine"
    log_level: str = "INFO"
    strategy_deterministic_latency_budget_ms: float = 50.0

    fail_on_invalid_contract: bool = True
    fail_on_invalid_data: bool = True
    fail_on_stale_critical_data: bool = True
    degraded_enter_allowed: bool = False
    max_snapshot_age_ms: int = 15_000
    max_source_age_ms: int = 20_000

    weight_structure_quality: float = 0.12
    weight_breakout_quality: float = 0.11
    weight_location_quality: float = 0.09
    weight_pullback_quality: float = 0.10
    weight_reengagement_quality: float = 0.10
    weight_orderflow_quality: float = 0.09
    weight_volume_quality: float = 0.07
    weight_value_quality: float = 0.07
    weight_liquidity_quality: float = 0.06
    weight_htf_context_quality: float = 0.06
    weight_target_quality: float = 0.07
    weight_timing_quality: float = 0.04
    weight_data_quality_score: float = 0.02

    penalty_balance_risk: float = 24.0
    penalty_chop_risk: float = 20.0
    penalty_failed_breakout_risk: float = 26.0
    penalty_reversal_risk: float = 24.0
    penalty_late_entry: float = 10.0
    penalty_overextended_entry: float = 12.0
    penalty_weak_breakout: float = 12.0
    penalty_weak_retest: float = 10.0
    penalty_countertrend_pullback: float = 20.0
    penalty_orderflow_contradiction: float = 14.0
    penalty_value_not_migrating: float = 12.0
    penalty_poc_stagnation: float = 12.0
    penalty_htf_counter_structure: float = 12.0
    penalty_target_obstruction: float = 16.0
    penalty_insufficient_rr: float = 20.0
    penalty_liquidity_wall: float = 14.0
    penalty_stale_signal: float = 25.0
    penalty_degraded_data: float = 12.0
    penalty_missing_critical_evidence: float = 18.0
    penalty_thesis_repeat: float = 8.0
    penalty_attempt_exhaustion: float = 100.0
    penalty_directional_exhaustion: float = 14.0
    penalty_low_follow_through: float = 14.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "StrategyConfig":
        e = dict(os.environ if env is None else env)
        base = cls()
        return cls(
            contract_version=_text(e, "CONTRACT_VERSION", base.contract_version),
            exchange=_text(e, "EXCHANGE", base.exchange),
            trading_env=_text(e, "TRADING_ENV", base.trading_env),
            market_mode=_text(e, "MARKET_MODE", base.market_mode),
            strategy_version=_text(e, "STRATEGY_VERSION", base.strategy_version),
            config_version=_text(e, "CONFIG_VERSION", base.config_version),
            strategy_timeframe_policy=_text(e, "STRATEGY_TIMEFRAME_POLICY", base.strategy_timeframe_policy),
            pre_breakout_enabled=_bool(e, "PRE_BREAKOUT_ENABLED", base.pre_breakout_enabled),
            breakout_enabled=_bool(e, "BREAKOUT_ENABLED", base.breakout_enabled),
            continuation_enabled=_bool(e, "CONTINUATION_ENABLED", base.continuation_enabled),
            reversal_enabled=_bool(e, "REVERSAL_ENABLED", base.reversal_enabled),
            primary_pattern=_text(e, "PRIMARY_PATTERN", base.primary_pattern),
            watch_min_confidence=_float(e, "WATCH_MIN_CONFIDENCE", base.watch_min_confidence),
            armed_min_confidence=_float(e, "ARMED_MIN_CONFIDENCE", base.armed_min_confidence),
            enter_min_confidence=_float(e, "ENTER_MIN_CONFIDENCE", base.enter_min_confidence),
            pre_breakout_min_confidence=_float(e, "PRE_BREAKOUT_MIN_CONFIDENCE", base.pre_breakout_min_confidence),
            breakout_min_confidence=_float(e, "BREAKOUT_MIN_CONFIDENCE", base.breakout_min_confidence),
            reversal_min_confidence=_float(e, "REVERSAL_MIN_CONFIDENCE", base.reversal_min_confidence),
            min_acceptable_rr=_float(e, "MIN_ACCEPTABLE_RR", base.min_acceptable_rr),
            preferred_min_rr=_float(e, "PREFERRED_MIN_RR", base.preferred_min_rr),
            trade_intent_ttl_ms=_int(e, "TRADE_INTENT_TTL_MS", base.trade_intent_ttl_ms),
            continuation_require_reengagement=_bool(e, "CONTINUATION_REQUIRE_REENGAGEMENT", base.continuation_require_reengagement),
            continuation_projected_extension_mult=_float(e, "CONTINUATION_PROJECTED_EXTENSION_MULT", base.continuation_projected_extension_mult),
            continuation_fib_levels=_csv_floats(e, "CONTINUATION_FIB_LEVELS", base.continuation_fib_levels),
            continuation_fvg_levels=_csv_floats(e, "CONTINUATION_FVG_LEVELS", base.continuation_fvg_levels),
            continuation_max_minor_pullback_entries=_int(e, "CONTINUATION_MAX_MINOR_PULLBACK_ENTRIES", base.continuation_max_minor_pullback_entries),
            continuation_min_breakout_score=_float(e, "CONTINUATION_MIN_BREAKOUT_SCORE", base.continuation_min_breakout_score),
            continuation_min_pullback_score=_float(e, "CONTINUATION_MIN_PULLBACK_SCORE", base.continuation_min_pullback_score),
            continuation_min_location_score=_float(e, "CONTINUATION_MIN_LOCATION_SCORE", base.continuation_min_location_score),
            continuation_min_reengagement_score=_float(e, "CONTINUATION_MIN_REENGAGEMENT_SCORE", base.continuation_min_reengagement_score),
            continuation_min_target_score=_float(e, "CONTINUATION_MIN_TARGET_SCORE", base.continuation_min_target_score),
            pre_breakout_min_level_strength=_float(e, "PRE_BREAKOUT_MIN_LEVEL_STRENGTH", base.pre_breakout_min_level_strength),
            pre_breakout_min_compression_score=_float(e, "PRE_BREAKOUT_MIN_COMPRESSION_SCORE", base.pre_breakout_min_compression_score),
            pre_breakout_min_directional_pressure=_float(e, "PRE_BREAKOUT_MIN_DIRECTIONAL_PRESSURE", base.pre_breakout_min_directional_pressure),
            breakout_require_acceptance=_bool(e, "BREAKOUT_REQUIRE_ACCEPTANCE", base.breakout_require_acceptance),
            breakout_require_followthrough=_bool(e, "BREAKOUT_REQUIRE_FOLLOWTHROUGH", base.breakout_require_followthrough),
            breakout_immediate_entry_enabled=_bool(e, "BREAKOUT_IMMEDIATE_ENTRY_ENABLED", base.breakout_immediate_entry_enabled),
            breakout_first_pullback_enabled=_bool(e, "BREAKOUT_FIRST_PULLBACK_ENABLED", base.breakout_first_pullback_enabled),
            breakout_second_pullback_enabled=_bool(e, "BREAKOUT_SECOND_PULLBACK_ENABLED", base.breakout_second_pullback_enabled),
            breakout_major_pullback_reentry_enabled=_bool(e, "BREAKOUT_MAJOR_PULLBACK_REENTRY_ENABLED", base.breakout_major_pullback_reentry_enabled),
            reversal_require_liquidity_event=_bool(e, "REVERSAL_REQUIRE_LIQUIDITY_EVENT", base.reversal_require_liquidity_event),
            reversal_require_opposite_displacement=_bool(e, "REVERSAL_REQUIRE_OPPOSITE_DISPLACEMENT", base.reversal_require_opposite_displacement),
            reversal_require_micro_confirmation=_bool(e, "REVERSAL_REQUIRE_MICRO_CONFIRMATION", base.reversal_require_micro_confirmation),
            balance_hard_block_enabled=_bool(e, "BALANCE_HARD_BLOCK_ENABLED", base.balance_hard_block_enabled),
            balance_hard_block_score=_float(e, "BALANCE_HARD_BLOCK_SCORE", base.balance_hard_block_score),
            chop_hard_block_score=_float(e, "CHOP_HARD_BLOCK_SCORE", base.chop_hard_block_score),
            failed_breakout_hard_block_enabled=_bool(e, "FAILED_BREAKOUT_HARD_BLOCK_ENABLED", base.failed_breakout_hard_block_enabled),
            failed_breakout_hard_block_score=_float(e, "FAILED_BREAKOUT_HARD_BLOCK_SCORE", base.failed_breakout_hard_block_score),
            reversal_risk_block_score=_float(e, "REVERSAL_RISK_BLOCK_SCORE", base.reversal_risk_block_score),
            max_strategy_attempts_per_thesis=_int(e, "MAX_STRATEGY_ATTEMPTS_PER_THESIS", base.max_strategy_attempts_per_thesis),
            thesis_cooldown_sec=_int(e, "THESIS_COOLDOWN_SEC", base.thesis_cooldown_sec),
            thesis_reset_require_major_event=_bool(e, "THESIS_RESET_REQUIRE_MAJOR_EVENT", base.thesis_reset_require_major_event),
            target_obstacle_filter_enabled=_bool(e, "TARGET_OBSTACLE_FILTER_ENABLED", base.target_obstacle_filter_enabled),
            liquidity_wall_target_filter_enabled=_bool(e, "LIQUIDITY_WALL_TARGET_FILTER_ENABLED", base.liquidity_wall_target_filter_enabled),
            htf_target_filter_enabled=_bool(e, "HTF_TARGET_FILTER_ENABLED", base.htf_target_filter_enabled),
            volume_node_target_filter_enabled=_bool(e, "VOLUME_NODE_TARGET_FILTER_ENABLED", base.volume_node_target_filter_enabled),
            ai_enabled=_bool(e, "AI_ENABLED", base.ai_enabled),
            ai_provider_select=_text(e, "AI_PROVIDER_SELECT", base.ai_provider_select),
            ai_required_for_enter=_bool(e, "AI_REQUIRED_FOR_ENTER", base.ai_required_for_enter),
            ai_max_positive_adjustment=_float(e, "AI_MAX_POSITIVE_ADJUSTMENT", base.ai_max_positive_adjustment),
            ai_max_negative_adjustment=_float(e, "AI_MAX_NEGATIVE_ADJUSTMENT", base.ai_max_negative_adjustment),
            ai_call_min_deterministic_confidence=_float(e, "AI_CALL_MIN_DETERMINISTIC_CONFIDENCE", base.ai_call_min_deterministic_confidence),
            ai_total_deadline_ms=_int(e, "AI_TOTAL_DEADLINE_MS", base.ai_total_deadline_ms),
            ai_provider_timeout_ms=_int(e, "AI_PROVIDER_TIMEOUT_MS", base.ai_provider_timeout_ms),
            ai_max_retries=_int(e, "AI_MAX_RETRIES", base.ai_max_retries),
            ai_late_response_policy=_text(e, "AI_LATE_RESPONSE_POLICY", base.ai_late_response_policy),
            opencode_routing_enabled=_bool(e, "OPENCODE_ROUTING_ENABLED", base.opencode_routing_enabled),
            opencode_dual_review_enabled=_bool(e, "OPENCODE_DUAL_REVIEW_ENABLED", base.opencode_dual_review_enabled),
            ai_adjudicator_enabled=_bool(e, "AI_ADJUDICATOR_ENABLED", base.ai_adjudicator_enabled),
            opencode_go_base_url=_text(e, "OPENCODE_GO_BASE_URL", base.opencode_go_base_url),
            opencode_qwen_model=_text(e, "OPENCODE_QWEN_MODEL", base.opencode_qwen_model),
            opencode_muse_model=_text(e, "OPENCODE_MUSE_MODEL", base.opencode_muse_model),
            ai_analyst_model=_text(e, "AI_ANALYST_MODEL", base.ai_analyst_model),
            ai_critic_model=_text(e, "AI_CRITIC_MODEL", base.ai_critic_model),
            ai_adjudicator_model=_text(e, "AI_ADJUDICATOR_MODEL", base.ai_adjudicator_model),
            openai_base_url=_text(e, "OPENAI_BASE_URL", base.openai_base_url),
            openai_fallback_enabled=_bool(e, "OPENAI_FALLBACK_ENABLED", base.openai_fallback_enabled),
            openai_fallback_model=_text(e, "OPENAI_FALLBACK_MODEL", base.openai_fallback_model),
            openai_reasoning_effort=_text(e, "OPENAI_REASONING_EFFORT", base.openai_reasoning_effort),
            openai_service_tier=_text(e, "OPENAI_SERVICE_TIER", base.openai_service_tier),
            openai_timeout_sec=_float(e, "OPENAI_TIMEOUT_SEC", base.openai_timeout_sec),
            openai_max_output_tokens=_int(e, "OPENAI_MAX_OUTPUT_TOKENS", base.openai_max_output_tokens),
            calibration_enabled=_bool(e, "CALIBRATION_ENABLED", base.calibration_enabled),
            calibration_min_sample=_int(e, "CALIBRATION_MIN_SAMPLE", base.calibration_min_sample),
            calibration_max_adjustment=_float(e, "CALIBRATION_MAX_ADJUSTMENT", base.calibration_max_adjustment),
            historical_analogue_enabled=_bool(e, "HISTORICAL_ANALOGUE_ENABLED", base.historical_analogue_enabled),
            historical_analogue_min_sample=_int(e, "HISTORICAL_ANALOGUE_MIN_SAMPLE", base.historical_analogue_min_sample),
            historical_analogue_max_results=_int(e, "HISTORICAL_ANALOGUE_MAX_RESULTS", base.historical_analogue_max_results),
            walkforward_enabled=_bool(e, "WALKFORWARD_ENABLED", base.walkforward_enabled),
            walkforward_train_days=_int(e, "WALKFORWARD_TRAIN_DAYS", base.walkforward_train_days),
            walkforward_validation_days=_int(e, "WALKFORWARD_VALIDATION_DAYS", base.walkforward_validation_days),
            walkforward_test_days=_int(e, "WALKFORWARD_TEST_DAYS", base.walkforward_test_days),
            walkforward_step_days=_int(e, "WALKFORWARD_STEP_DAYS", base.walkforward_step_days),
            walkforward_min_trades=_int(e, "WALKFORWARD_MIN_TRADES", base.walkforward_min_trades),
            walkforward_max_drawdown_r=_float(e, "WALKFORWARD_MAX_DRAWDOWN_R", base.walkforward_max_drawdown_r),
            walkforward_max_subgroup_regression_r=_float(e, "WALKFORWARD_MAX_SUBGROUP_REGRESSION_R", base.walkforward_max_subgroup_regression_r),
            walkforward_min_window_expectancy_r=_float(e, "WALKFORWARD_MIN_WINDOW_EXPECTANCY_R", base.walkforward_min_window_expectancy_r),
            walkforward_auto_promote=_bool(e, "WALKFORWARD_AUTO_PROMOTE", base.walkforward_auto_promote),
            walkforward_ai_research_enabled=_bool(e, "WALKFORWARD_AI_RESEARCH_ENABLED", base.walkforward_ai_research_enabled),
            walkforward_ablation_enabled=_bool(e, "WALKFORWARD_ABLATION_ENABLED", base.walkforward_ablation_enabled),
            walkforward_calibration_enabled=_bool(e, "WALKFORWARD_CALIBRATION_ENABLED", base.walkforward_calibration_enabled),
            trade_memory_enabled=_bool(e, "TRADE_MEMORY_ENABLED", base.trade_memory_enabled),
            trade_memory_db=_text(e, "TRADE_MEMORY_DB", base.trade_memory_db),
            data_dir=_text(e, "DATA_DIR", base.data_dir),
            decision_log_dir=_text(e, "DECISION_LOG_DIR", base.decision_log_dir),
            research_dir=_text(e, "RESEARCH_DIR", base.research_dir),
            quarantine_dir=_text(e, "QUARANTINE_DIR", base.quarantine_dir),
            log_level=_text(e, "LOG_LEVEL", base.log_level),
            strategy_deterministic_latency_budget_ms=_float(e, "STRATEGY_DETERMINISTIC_LATENCY_BUDGET_MS", base.strategy_deterministic_latency_budget_ms),
            fail_on_invalid_contract=_bool(e, "FAIL_ON_INVALID_CONTRACT", base.fail_on_invalid_contract),
            fail_on_invalid_data=_bool(e, "FAIL_ON_INVALID_DATA", base.fail_on_invalid_data),
            fail_on_stale_critical_data=_bool(e, "FAIL_ON_STALE_CRITICAL_DATA", base.fail_on_stale_critical_data),
            degraded_enter_allowed=_bool(e, "DEGRADED_ENTER_ALLOWED", base.degraded_enter_allowed),
            max_snapshot_age_ms=_int(e, "MAX_SNAPSHOT_AGE_MS", base.max_snapshot_age_ms),
            max_source_age_ms=_int(e, "MAX_SOURCE_AGE_MS", base.max_source_age_ms),
            **{
                key: _float(e, key.upper(), getattr(base, key))
                for key in asdict(base)
                if key.startswith("weight_") or key.startswith("penalty_")
            },
        )

    @property
    def config_hash(self) -> str:
        return canonical_hash(asdict(self))

    @property
    def component_weights(self) -> dict[str, float]:
        return {
            key.removeprefix("weight_"): value
            for key, value in asdict(self).items()
            if key.startswith("weight_")
        }
