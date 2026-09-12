from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1] / "src"
errors: list[str] = []
for path in ROOT.rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT)
    if "\t" in text:
        errors.append(f"{rel}: tab character")
    for number, line in enumerate(text.splitlines(), 1):
        if line.rstrip() != line:
            errors.append(f"{rel}:{number}: trailing whitespace")
        upper = line.upper()
        if "TODO" in upper or "FIXME" in upper or "PLACEHOLDER" in upper:
            errors.append(f"{rel}:{number}: forbidden unfinished marker")
    try:
        tree = ast.parse(text, filename=str(rel))
    except SyntaxError as exc:
        errors.append(f"{rel}: syntax: {exc}")
        continue
    for node in ast.walk(tree):
        if isinstance(node, (ast.ImportFrom,)) and any(alias.name == "*" for alias in node.names):
            errors.append(f"{rel}:{node.lineno}: wildcard import")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
            errors.append(f"{rel}:{node.lineno}: dynamic eval/exec forbidden")
if errors:
    print("\n".join(errors))
    sys.exit(1)
print(f"lint_check: PASS ({len(list(ROOT.rglob('*.py')))} Python files)")
