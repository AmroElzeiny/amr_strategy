from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
SKIP = {".git", "__pycache__", ".pytest_cache"}
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "bybit_key_assignment": re.compile(r"(?i)\b(?:BYBIT_)?API_(?:KEY|SECRET)\s*=\s*[^\s#]{8,}"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}
errors: list[str] = []
for path in ROOT.rglob("*"):
    if not path.is_file() or any(part in SKIP for part in path.parts):
        continue
    if path.suffix.lower() in {".pyc", ".sqlite3", ".zip"}:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for name, pattern in PATTERNS.items():
        if pattern.search(text):
            errors.append(f"{path.relative_to(ROOT)}:{name}")
if errors:
    raise SystemExit("secret_scan failed:\n" + "\n".join(errors))
print("secret_scan: PASS (no credential/private-key patterns found)")
