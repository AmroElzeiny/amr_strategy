from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path
from typing import Any

from .config import StrategyConfig
from .engine import evaluate_snapshot, get_champion_config, ingest_execution_report, run_walkforward
from .validation import schema_sha256, validate_market_snapshot


def _load_json(path: str | None, *, stdin: bool = False) -> Any:
    text = sys.stdin.read() if stdin else Path(str(path)).read_text(encoding="utf-8")
    return json.loads(text)


def _emit(value: Any) -> None:
    print(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crypto_strategy_engine")
    sub = parser.add_subparsers(dest="command", required=True)

    evaluate = sub.add_parser("evaluate", help="Validate a MarketSnapshot and produce one TradeIntent")
    evaluate.add_argument("path", nargs="?")
    evaluate.add_argument("--stdin", action="store_true")
    evaluate.add_argument("--no-ai", action="store_true", help="Deterministic/research evaluation without AI transport")
    evaluate.add_argument("--no-persist", action="store_true")

    validate = sub.add_parser("validate", help="Validate/freeze a MarketSnapshot")
    validate.add_argument("path")

    ingest = sub.add_parser("ingest-outcome", help="Ingest an independent HM_CRYPTO_V1 ExecutionReport")
    ingest.add_argument("path")

    walk = sub.add_parser("walk-forward", help="Run time-ordered research over historical snapshot/outcome records")
    walk.add_argument("path")
    walk.add_argument("--output", default="./data/research/latest")

    sub.add_parser("champion-config", help="Print current champion config identity")
    sub.add_parser("schema-hash", help="Print CONTRACT_SCHEMA_SHA256")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "evaluate":
            if not args.stdin and not args.path:
                raise ValueError("evaluate_requires_path_or_stdin")
            snapshot = _load_json(args.path, stdin=args.stdin)
            config = StrategyConfig.from_env()
            if args.no_ai:
                import os
                overridden = dict(os.environ)
                overridden.update({"AI_ENABLED": "false", "AI_REQUIRED_FOR_ENTER": "false"})
                config = StrategyConfig.from_env(overridden)
            _emit(evaluate_snapshot(snapshot, config, persist=not args.no_persist))
        elif args.command == "validate":
            snapshot = _load_json(args.path)
            result = validate_market_snapshot(snapshot)
            _emit({
                "valid": result.valid,
                "snapshot_hash": result.snapshot_hash,
                "blockers": list(result.blockers),
                "warnings": list(result.warnings),
                "stale_sources": list(result.stale_sources),
                "CONTRACT_SCHEMA_SHA256": schema_sha256(),
            })
        elif args.command == "ingest-outcome":
            _emit(ingest_execution_report(_load_json(args.path)))
        elif args.command == "walk-forward":
            records = _load_json(args.path)
            if not isinstance(records, list):
                raise ValueError("walkforward_input_must_be_array")
            _emit(run_walkforward(records, output_dir=args.output))
        elif args.command == "champion-config":
            _emit(get_champion_config())
        elif args.command == "schema-hash":
            print(schema_sha256())
        return 0
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "fail_closed": True}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
