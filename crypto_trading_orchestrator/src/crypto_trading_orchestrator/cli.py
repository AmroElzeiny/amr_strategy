from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .adapters import MarketIntelAdapter, RiskExecutionAdapter, StrategyAdapter
from .compatibility import validate_compatibility
from .config import OrchestratorConfig
from .discovery import discover_all
from .persistence import OrchestratorStore
from .runtime import TradingOrchestrator


def _print(value: Any) -> None:
    print(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, default=str))


def _load_env(path: str) -> None:
    if not path:
        return
    target = Path(path)
    if not target.is_file():
        raise ValueError(f"ENV_FILE_NOT_FOUND:{target}")
    for raw in target.read_text(encoding="utf-8-sig").splitlines():
        row = raw.strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        key, value = row.split("=", 1)
        upper = key.strip().upper()
        if any(marker in upper for marker in ("SECRET", "API_KEY", "TOKEN", "PASSWORD", "PRIVATE_KEY")):
            raise ValueError(f"SECRET_FORBIDDEN_IN_ORCHESTRATOR_ENV:{key.strip()}")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _bootstrap(config: OrchestratorConfig) -> TradingOrchestrator:
    modules, identities = discover_all(config)
    from crypto_market_intel.config import Settings as MarketSettings
    from crypto_market_intel.engine import MarketIntelEngine
    from crypto_risk_execution.config import Settings as RiskSettings

    market = MarketIntelAdapter(MarketIntelEngine(MarketSettings.from_env()))
    strategy = StrategyAdapter(modules["strategy"])
    risk = RiskExecutionAdapter(modules["risk"], settings=RiskSettings())
    return TradingOrchestrator(config, market, strategy, risk, identities=identities)


async def _start(config: OrchestratorConfig, *, once: bool, interval: float) -> int:
    runtime = _bootstrap(config)
    status = await runtime.startup()
    _print(status)
    if runtime.state.value == "BLOCKED":
        await runtime.shutdown()
        return 2
    loop = asyncio.get_running_loop()
    for name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, name, None)
        if sig is not None:
            try:
                loop.add_signal_handler(sig, runtime.request_stop)
            except (NotImplementedError, RuntimeError):
                pass
    try:
        await runtime.run(scan_interval_sec=interval, once=once)
    finally:
        _print(await runtime.shutdown())
    return 0


async def _scan_once(config: OrchestratorConfig) -> int:
    runtime = _bootstrap(config)
    status = await runtime.startup()
    if runtime.state.value == "BLOCKED":
        _print(status)
        await runtime.shutdown()
        return 2
    try:
        _print(await runtime.scan_once())
    finally:
        await runtime.shutdown()
    return 0


async def _evaluate_once(config: OrchestratorConfig, symbol: str) -> int:
    runtime = _bootstrap(config)
    status = await runtime.startup()
    if runtime.state.value == "BLOCKED":
        _print(status)
        await runtime.shutdown()
        return 2
    try:
        _print(await runtime.build_and_process(symbol, persist_strategy=False))
    finally:
        await runtime.shutdown()
    return 0


async def _reconcile(config: OrchestratorConfig) -> int:
    runtime = _bootstrap(config)
    try:
        result = await runtime.reconcile()
        _print(result)
        return 0 if result.get("reconciled") else 2
    finally:
        runtime.store.close()


async def _walkforward(config: OrchestratorConfig, source: str, output: str | None) -> int:
    runtime = _bootstrap(config)
    try:
        records = json.loads(Path(source).read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("WALKFORWARD_INPUT_MUST_BE_ARRAY")
        _print(await runtime.walkforward(records, output))
        return 0
    finally:
        runtime.store.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crypto-trading-orchestrator")
    parser.add_argument(
        "--env-file", default="", help="Load KEY=VALUE settings without overwriting process env"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--once", action="store_true")
    start.add_argument("--scan-interval", type=float, default=30.0)
    sub.add_parser("doctor")
    sub.add_parser("validate")
    sub.add_parser("status")
    sub.add_parser("health")
    sub.add_parser("reconcile")
    sub.add_parser("scan-once")
    evaluate = sub.add_parser("evaluate-once")
    evaluate.add_argument("symbol")
    sub.add_parser("shutdown")
    walk = sub.add_parser("walkforward")
    walk.add_argument("source")
    walk.add_argument("--output-dir")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _load_env(args.env_file)
        config = OrchestratorConfig.from_env()
        if args.command in {"status", "health", "shutdown"}:
            config.validate()
            with OrchestratorStore(config.state_db) as store:
                if args.command == "shutdown":
                    store.set("shutdown_requested", {"requested": True})
                    _print(
                        {
                            "accepted": True,
                            "note": "A running process must receive SIGINT/SIGTERM to stop immediately.",
                        }
                    )
                else:
                    value = store.get("runtime", {"state": "NOT_STARTED", "health": "UNKNOWN"})
                    _print(
                        value
                        if args.command == "status"
                        else {"health": value.get("health"), "state": value.get("state")}
                    )
            return 0
        if args.command in {"doctor", "validate"}:
            config.validate()
            config.ensure_directories()
            _, identities = discover_all(config)
            compatibility = validate_compatibility(config, identities)
            result = {
                "ok": compatibility.compatible,
                "config_hash": config.config_hash,
                "execution_permitted": config.execution_permitted,
                "compatibility": compatibility.to_dict(),
                "storage_writable": os.access(Path(config.state_db).parent, os.W_OK),
                "database": str(Path(config.state_db).resolve()),
                "package_health": {"market": "IMPORT_OK", "strategy": "IMPORT_OK", "risk": "IMPORT_OK"},
                "private_exchange_readiness": "NOT_PROBED_BY_OFFLINE_DOCTOR",
                "order_submission_attempted": False,
            }
            _print(result)
            return 0 if result["ok"] else 2
        if args.command == "start":
            return asyncio.run(_start(config, once=args.once, interval=args.scan_interval))
        if args.command == "scan-once":
            return asyncio.run(_scan_once(config))
        if args.command == "evaluate-once":
            return asyncio.run(_evaluate_once(config, args.symbol))
        if args.command == "reconcile":
            return asyncio.run(_reconcile(config))
        if args.command == "walkforward":
            return asyncio.run(_walkforward(config, args.source, args.output_dir))
        raise ValueError(f"UNKNOWN_COMMAND:{args.command}")
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        _print({"ok": False, "error": str(exc), "type": type(exc).__name__})
        return 2


if __name__ == "__main__":
    sys.exit(main())
