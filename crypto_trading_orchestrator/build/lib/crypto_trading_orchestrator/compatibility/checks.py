from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from ..config import OrchestratorConfig
from ..models import InstrumentIdentity, PackageIdentity


@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    mode: str
    reasons: tuple[str, ...]
    packages: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SymbolAdapter:
    """Transport normalization only; ambiguous exchange instruments are rejected."""

    @staticmethod
    def canonical(symbol: str, *, exchange: str, market_mode: str) -> InstrumentIdentity:
        cleaned = symbol.strip().upper().replace("/", "").replace("-", "")
        if not cleaned or not cleaned.isalnum():
            raise ValueError("AMBIGUOUS_SYMBOL")
        suffixes = [value for value in ("USDT", "USDC", "USD", "BTC", "ETH") if cleaned.endswith(value)]
        if len(suffixes) != 1 or len(cleaned) <= len(suffixes[0]):
            raise ValueError("AMBIGUOUS_SETTLEMENT_ASSET")
        settle = suffixes[0]
        product = "PERPETUAL" if market_mode == "DERIVATIVES" else "SPOT"
        return InstrumentIdentity(exchange.upper(), market_mode.upper(), cleaned, product, settle)


def validate_compatibility(
    config: OrchestratorConfig, identities: Mapping[str, PackageIdentity]
) -> CompatibilityResult:
    reasons: list[str] = []
    required = {"market", "strategy", "risk"}
    missing = required.difference(identities)
    if missing:
        reasons.append("PACKAGES_MISSING:" + ",".join(sorted(missing)))
    for role in sorted(required.intersection(identities)):
        identity = identities[role]
        if identity.contract_version != config.contract_version:
            reasons.append(f"CONTRACT_MISMATCH:{role}")
        if not identity.schema_hash or not identity.build_hash:
            reasons.append(f"UNVERIFIABLE_PACKAGE:{role}")
    if config.exchange != "BYBIT":
        reasons.append("MARKET_PACKAGE_EXCHANGE_UNSUPPORTED")
    package_rows = {role: asdict(identity) for role, identity in identities.items()}
    return CompatibilityResult(
        compatible=not reasons,
        mode="ADAPTER_NORMALIZED" if not reasons else "BLOCKED",
        reasons=tuple(reasons),
        packages=package_rows,
    )
