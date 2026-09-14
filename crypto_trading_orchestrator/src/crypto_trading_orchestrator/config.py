from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from .canonical import canonical_hash


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or not str(raw).strip():
        return default
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name}:invalid_boolean")


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    return default if raw is None or not str(raw).strip() else int(str(raw).strip())


def _float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    return default if raw is None or not str(raw).strip() else float(str(raw).strip())


@dataclass(frozen=True)
class OrchestratorConfig:
    orchestrator_version: str = "HM_ORCHESTRATOR_V1"
    contract_version: str = "HM_CRYPTO_V1"
    runtime_mode: str = "LIVE"
    exchange: str = "BYBIT"
    trading_env: str = "DEMO"
    market_mode: str = "DERIVATIVES"
    market_package: str = "crypto_market_intel"
    strategy_package: str = "crypto_strategy_engine"
    risk_package: str = "crypto_risk_execution"
    market_path: str = ""
    strategy_path: str = ""
    risk_path: str = ""
    market_env_file: str = ""
    strategy_env_file: str = ""
    risk_env_file: str = ""
    execution_enabled: bool = False
    real_trading_enabled: bool = False
    dry_run: bool = True
    scanner_enabled: bool = True
    breakout_promotion_enabled: bool = True
    max_active_symbols: int = 60
    max_deep_watch_symbols: int = 30
    max_strategy_evaluations: int = 10
    promotion_min_score: float = 0.60
    watch_priority_decay_sec: int = 60
    market_queue_max: int = 1000
    strategy_queue_max: int = 250
    execution_queue_max: int = 0
    coalesce_snapshots: bool = True
    max_snapshot_to_strategy_ms: int = 5000
    max_strategy_to_risk_ms: int = 2000
    health_interval_sec: int = 5
    block_on_market_unhealthy: bool = True
    block_on_strategy_unhealthy: bool = True
    block_on_risk_unhealthy: bool = True
    require_reconciliation: bool = True
    recover_active_watches: bool = True
    shutdown_settle_timeout_sec: int = 30
    walkforward_enabled: bool = True
    walkforward_schedule: str = ""
    data_dir: str = "./data"
    state_db: str = "./data/orchestrator_state.db"
    audit_dir: str = "./data/audit"
    quarantine_dir: str = "./data/quarantine"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> OrchestratorConfig:
        source = os.environ if env is None else env
        return cls(
            orchestrator_version=source.get("ORCHESTRATOR_VERSION", "HM_ORCHESTRATOR_V1"),
            contract_version=source.get("CONTRACT_VERSION", "HM_CRYPTO_V1"),
            runtime_mode=source.get("RUNTIME_MODE", "LIVE").upper(),
            exchange=source.get("EXCHANGE", "BYBIT").upper(),
            trading_env=source.get("TRADING_ENV", "DEMO").upper(),
            market_mode=source.get("MARKET_MODE", "DERIVATIVES").upper(),
            market_package=source.get("MARKET_INTEL_PACKAGE", "crypto_market_intel"),
            strategy_package=source.get("STRATEGY_PACKAGE", "crypto_strategy_engine"),
            risk_package=source.get("RISK_EXECUTION_PACKAGE", "crypto_risk_execution"),
            market_path=source.get("MARKET_INTEL_PACKAGE_PATH", ""),
            strategy_path=source.get("STRATEGY_PACKAGE_PATH", ""),
            risk_path=source.get("RISK_EXECUTION_PACKAGE_PATH", ""),
            market_env_file=source.get("MARKET_INTEL_ENV_FILE", ""),
            strategy_env_file=source.get("STRATEGY_ENV_FILE", ""),
            risk_env_file=source.get("RISK_EXECUTION_ENV_FILE", ""),
            execution_enabled=_bool(source, "ORCHESTRATOR_EXECUTION_ENABLED", False),
            real_trading_enabled=_bool(source, "ORCHESTRATOR_REAL_TRADING_ENABLED", False),
            dry_run=_bool(source, "DRY_RUN", True),
            scanner_enabled=_bool(source, "SCANNER_ORCHESTRATION_ENABLED", True),
            breakout_promotion_enabled=_bool(source, "BREAKOUT_PROMOTION_ENABLED", True),
            max_active_symbols=_int(source, "MAX_ACTIVE_SYMBOLS", 60),
            max_deep_watch_symbols=_int(source, "MAX_DEEP_WATCH_SYMBOLS", 30),
            max_strategy_evaluations=_int(source, "MAX_SIMULTANEOUS_STRATEGY_EVALUATIONS", 10),
            promotion_min_score=_float(source, "PROMOTION_MIN_PRELIMINARY_SCORE", 0.60),
            watch_priority_decay_sec=_int(source, "WATCH_PRIORITY_DECAY_SEC", 60),
            market_queue_max=_int(source, "MARKET_EVENT_QUEUE_MAX", 1000),
            strategy_queue_max=_int(source, "STRATEGY_EVENT_QUEUE_MAX", 250),
            execution_queue_max=_int(source, "EXECUTION_EVENT_QUEUE_MAX", 0),
            coalesce_snapshots=_bool(source, "MARKET_SNAPSHOT_COALESCE", True),
            max_snapshot_to_strategy_ms=_int(source, "MAX_SNAPSHOT_TO_STRATEGY_MS", 5000),
            max_strategy_to_risk_ms=_int(source, "MAX_STRATEGY_TO_RISK_MS", 2000),
            health_interval_sec=_int(source, "HEALTH_CHECK_INTERVAL_SEC", 5),
            block_on_market_unhealthy=_bool(source, "BLOCK_ON_MARKET_PACKAGE_UNHEALTHY", True),
            block_on_strategy_unhealthy=_bool(source, "BLOCK_ON_STRATEGY_PACKAGE_UNHEALTHY", True),
            block_on_risk_unhealthy=_bool(source, "BLOCK_ON_RISK_PACKAGE_UNHEALTHY", True),
            require_reconciliation=_bool(source, "REQUIRE_RECONCILIATION_BEFORE_READY", True),
            recover_active_watches=_bool(source, "RECOVER_ACTIVE_WATCHES", True),
            shutdown_settle_timeout_sec=_int(source, "SHUTDOWN_SETTLE_TIMEOUT_SEC", 30),
            walkforward_enabled=_bool(source, "WALKFORWARD_ORCHESTRATION_ENABLED", True),
            walkforward_schedule=source.get("WALKFORWARD_SCHEDULE", ""),
            data_dir=source.get("DATA_DIR", "./data"),
            state_db=source.get("ORCHESTRATOR_STATE_DB", "./data/orchestrator_state.db"),
            audit_dir=source.get("AUDIT_DIR", "./data/audit"),
            quarantine_dir=source.get("QUARANTINE_DIR", "./data/quarantine"),
            log_level=source.get("LOG_LEVEL", "INFO").upper(),
        )

    def validate(self) -> None:
        if self.orchestrator_version != "HM_ORCHESTRATOR_V1":
            raise ValueError("ORCHESTRATOR_VERSION_MISMATCH")
        if self.contract_version != "HM_CRYPTO_V1":
            raise ValueError("CONTRACT_MISMATCH")
        if self.exchange not in {"BYBIT", "BINANCE"}:
            raise ValueError("UNSUPPORTED_EXCHANGE")
        if self.trading_env not in {"DEMO", "REAL"}:
            raise ValueError("UNSUPPORTED_TRADING_ENV")
        if "TEST" in self.trading_env:
            raise ValueError("TESTNET_FORBIDDEN")
        if self.market_mode not in {"SPOT", "DERIVATIVES"}:
            raise ValueError("UNSUPPORTED_MARKET_MODE")
        if self.runtime_mode not in {"LIVE", "RESEARCH"}:
            raise ValueError("UNSUPPORTED_RUNTIME_MODE")
        if self.exchange == "BINANCE" and self.trading_env == "DEMO":
            raise ValueError("BINANCE_DEMO_UNSUPPORTED")
        if self.runtime_mode == "RESEARCH" and self.execution_enabled:
            raise ValueError("RESEARCH_MODE_HAS_ZERO_EXECUTION_AUTHORITY")
        if self.trading_env == "REAL" and self.execution_enabled and not self.real_trading_enabled:
            raise ValueError("ORCHESTRATOR_REAL_TRADING_GUARD")
        for numeric_value, label in (
            (self.max_active_symbols, "MAX_ACTIVE_SYMBOLS"),
            (self.max_deep_watch_symbols, "MAX_DEEP_WATCH_SYMBOLS"),
            (self.max_strategy_evaluations, "MAX_SIMULTANEOUS_STRATEGY_EVALUATIONS"),
            (self.market_queue_max, "MARKET_EVENT_QUEUE_MAX"),
            (self.strategy_queue_max, "STRATEGY_EVENT_QUEUE_MAX"),
        ):
            if numeric_value <= 0:
                raise ValueError(f"{label}:must_be_positive")
        if self.max_deep_watch_symbols > self.max_active_symbols:
            raise ValueError("DEEP_WATCH_EXCEEDS_ACTIVE_CAPACITY")
        if self.execution_queue_max != 0:
            raise ValueError("EXECUTION_EVENT_QUEUE_MUST_BE_UNBOUNDED")
        for file_value, label in (
            (self.market_env_file, "MARKET_INTEL_ENV_FILE"),
            (self.strategy_env_file, "STRATEGY_ENV_FILE"),
            (self.risk_env_file, "RISK_EXECUTION_ENV_FILE"),
        ):
            if file_value and not Path(file_value).is_file():
                raise ValueError(f"{label}:not_found")

    @property
    def execution_permitted(self) -> bool:
        return (
            self.runtime_mode == "LIVE"
            and self.execution_enabled
            and (self.trading_env != "REAL" or self.real_trading_enabled)
        )

    @property
    def config_hash(self) -> str:
        return canonical_hash(asdict(self))

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.audit_dir, self.quarantine_dir, str(Path(self.state_db).parent)):
            Path(path).mkdir(parents=True, exist_ok=True)
