from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
SRC = ROOT / "src" / "crypto_market_intel"
FORBIDDEN_IMPORT_PREFIXES = (
    "crypto_strategy_engine",
    "crypto_risk_execution",
    "MetaTrader5",
    "mt5",
)
FORBIDDEN_RUNTIME_TEXT = ("api-testnet.bybit.com", "stream-testnet.bybit.com")

errors: list[str] = []
for path in SRC.rglob("*.py"):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [x.name for x in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for name in names:
            if any(name == prefix or name.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES):
                errors.append(f"{path.relative_to(ROOT)}: forbidden import {name}")
    text = path.read_text(encoding="utf-8")
    for token in FORBIDDEN_RUNTIME_TEXT:
        if token in text:
            errors.append(f"{path.relative_to(ROOT)}: forbidden testnet route {token}")

if errors:
    raise SystemExit("\n".join(errors))
print("dependency_boundary_check: PASS (no Package 2/3, MT5, or Testnet runtime dependency)")
