from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import sys
import tomllib
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType

from .config import OrchestratorConfig
from .models import PackageIdentity

EXPECTED_VERSIONS = {
    "crypto_market_intel": "1.0.0",
    "crypto_strategy_engine": "1.0.0",
    "crypto_risk_execution": "0.3.0.dev0",
}
DIST_NAMES = {
    "crypto_market_intel": "crypto-market-intel",
    "crypto_strategy_engine": "crypto-strategy-engine",
    "crypto_risk_execution": "crypto-risk-execution",
}


def _activate_path(raw: str) -> None:
    if not raw:
        return
    path = Path(raw).resolve()
    if not path.exists():
        raise ValueError(f"PACKAGE_PATH_NOT_FOUND:{path}")
    candidate = path / "src" if (path / "src").is_dir() else path
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)


def _schema_path(module: ModuleType) -> Path:
    module_path = Path(str(module.__file__)).resolve().parent
    candidate = module_path / "contracts" / "schema.json"
    if not candidate.is_file():
        raise ValueError(f"SCHEMA_NOT_FOUND:{module.__name__}")
    return candidate


def _fallback_version(module: ModuleType) -> str:
    module_path = Path(str(module.__file__)).resolve()
    for parent in module_path.parents:
        project = parent / "pyproject.toml"
        if project.is_file():
            with project.open("rb") as handle:
                value = tomllib.load(handle).get("project", {}).get("version")
            if isinstance(value, str):
                return value
    raise ValueError(f"PACKAGE_VERSION_UNAVAILABLE:{module.__name__}")


def _build_hash(files: Iterable[Path], root: Path) -> str:
    rows = []
    for path in sorted(files):
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": path.stat().st_size,
            }
        )
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def discover_package(role: str, import_name: str, path: str = "") -> tuple[ModuleType, PackageIdentity]:
    _activate_path(path)
    module = importlib.import_module(import_name)
    distribution = DIST_NAMES.get(import_name, import_name.replace("_", "-"))
    try:
        version = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        version = _fallback_version(module)
    expected = EXPECTED_VERSIONS.get(import_name)
    if expected is not None and version != expected:
        raise ValueError(f"PACKAGE_VERSION_MISMATCH:{import_name}:{version}:{expected}")
    contract = str(getattr(module, "CONTRACT_VERSION", ""))
    if contract != "HM_CRYPTO_V1":
        raise ValueError(f"CONTRACT_MISMATCH:{import_name}:{contract}")
    schema = _schema_path(module)
    schema_hash = hashlib.sha256(schema.read_bytes()).hexdigest()
    root = Path(str(module.__file__)).resolve().parent
    files = [item for item in root.rglob("*") if item.is_file() and "__pycache__" not in item.parts]
    identity = PackageIdentity(
        role=role,
        distribution=distribution,
        import_name=import_name,
        version=version,
        contract_version=contract,
        schema_hash=schema_hash,
        build_hash=_build_hash(files, root),
        path=str(root),
    )
    return module, identity


def discover_all(config: OrchestratorConfig) -> tuple[dict[str, ModuleType], dict[str, PackageIdentity]]:
    specs = (
        ("market", config.market_package, config.market_path),
        ("strategy", config.strategy_package, config.strategy_path),
        ("risk", config.risk_package, config.risk_path),
    )
    modules: dict[str, ModuleType] = {}
    identities: dict[str, PackageIdentity] = {}
    for role, name, path in specs:
        module, identity = discover_package(role, name, path)
        modules[role] = module
        identities[role] = identity
    if config.exchange == "BINANCE":
        raise ValueError("MARKET_PACKAGE_BINANCE_UNAVAILABLE")
    return modules, identities
