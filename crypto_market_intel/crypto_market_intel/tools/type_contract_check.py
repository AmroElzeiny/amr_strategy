from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1] / "src"
errors: list[str] = []
for path in ROOT.rglob("*.py"):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rel = path.relative_to(ROOT)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        if node.returns is None:
            errors.append(f"{rel}:{node.lineno}:{node.name}: missing return annotation")
        args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        for arg in args:
            if arg.arg in {"self", "cls"}:
                continue
            if arg.annotation is None:
                errors.append(f"{rel}:{node.lineno}:{node.name}:{arg.arg}: missing parameter annotation")
if errors:
    print("\n".join(errors))
    sys.exit(1)
print("type_contract_check: PASS (all public callables annotated)")
