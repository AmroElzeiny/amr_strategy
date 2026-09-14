from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..models import canonical_hash, dotted_get


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    path: str
    value: Any
    authority: str
    root_cause: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "path": self.path,
            "value": self.value,
            "authority": self.authority,
            "root_cause": self.root_cause,
        }


@dataclass(frozen=True)
class EvidenceCatalog:
    items: tuple[EvidenceItem, ...]
    by_id: dict[str, EvidenceItem]
    by_path: dict[str, EvidenceItem]
    catalog_hash: str

    def ids(self) -> set[str]:
        return set(self.by_id)

    def provider_view(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.items if item.authority != "internal_identity"]


def _add(
    rows: list[EvidenceItem],
    snapshot: Mapping[str, Any],
    path: str,
    *,
    root: str,
    authority: str = "deterministic",
) -> None:
    value = dotted_get(snapshot, path)
    if value is None:
        return
    evidence_id = f"E{len(rows) + 1:03d}"
    rows.append(EvidenceItem(evidence_id, path, value, authority, root))


def build_evidence_catalog(snapshot: Mapping[str, Any]) -> EvidenceCatalog:
    rows: list[EvidenceItem] = []
    paths = (
        ("regime.type", "regime"),
        ("structure.major_bias", "structure"),
        ("structure.qualified_impulse_score", "impulse"),
        ("structure.displacement_score", "impulse"),
        ("structure.expansion_score", "impulse"),
        ("structure.candle_overlap_score", "impulse"),
        ("structure.follow_through_score", "follow_through"),
        ("structure.acceptance_outside_range", "acceptance"),
        ("structure.pullback_depth_ratio", "pullback"),
        ("structure.pullback_duration_ratio", "pullback"),
        ("structure.pullback_velocity_ratio", "pullback"),
        ("structure.pullback_displacement_ratio", "pullback"),
        ("structure.pullback_overlap", "pullback"),
        ("structure.countertrend_structure_damage", "pullback"),
        ("structure.micro_bos", "reengagement"),
        ("structure.micro_choch_main_trend", "reengagement"),
        ("structure.reclaim", "reengagement"),
        ("structure.directional_displacement_restart", "reengagement"),
        ("structure.alternating_micro_bos", "balance"),
        ("structure.extension_decay", "balance"),
        ("structure.failed_expansion_count", "balance"),
        ("structure.time_without_progress_score", "balance"),
        ("structure.return_inside_prior_range", "failed_breakout"),
        ("structure.acceptance_inside_prior_range", "failed_breakout"),
        ("structure.extended_impulse_score", "reversal"),
        ("structure.exhaustion_score", "reversal"),
        ("breakout_alert.direction", "breakout"),
        ("breakout_alert.breakout_type", "breakout"),
        ("breakout_alert.level_strength", "breakout"),
        ("breakout_alert.breakout_score", "breakout"),
        ("breakout_alert.compression_score", "pre_breakout"),
        ("breakout_alert.directional_pressure", "pre_breakout"),
        ("breakout_alert.acceptance_score", "breakout"),
        ("breakout_alert.follow_through_score", "follow_through"),
        ("breakout_alert.pullback_count", "pullback_sequence"),
        ("breakout_alert.major_reset", "pullback_sequence"),
        ("breakout_alert.liquidation_burst_share", "failed_breakout"),
        ("volume_profile.value_migration_score", "value"),
        ("volume_profile.value_migration_direction", "value"),
        ("volume_profile.poc_migration_score", "value"),
        ("volume_profile.poc_stagnation_score", "balance"),
        ("volume_profile.poc_oscillation_score", "balance"),
        ("volume_profile.horizontal_value_score", "balance"),
        ("volume_profile.range_midpoint_cross_score", "balance"),
        ("orderflow.directional_delta_score", "orderflow"),
        ("orderflow.delta_flip", "reengagement"),
        ("orderflow.imbalance_score", "orderflow"),
        ("orderflow.absorption_score", "opposing_failure"),
        ("orderflow.opposing_failure_score", "opposing_failure"),
        ("orderflow.trade_velocity_score", "orderflow"),
        ("orderflow.pullback_volume_ratio", "pullback"),
        ("orderflow.pullback_delta_ratio", "pullback"),
        ("orderflow.aggression_without_progress_score", "failed_breakout"),
        ("orderflow.opposite_absorption_score", "failed_breakout"),
        ("orderbook.liquidity_wall_ahead_score", "target"),
        ("derivatives.open_interest_context_score", "derivatives"),
        ("derivatives.liquidation_context_score", "derivatives"),
        ("levels.reference_level", "identity"),
        ("levels.entry_reference", "entry"),
        ("levels.invalidation_price", "invalidation"),
        ("levels.room_to_first_obstacle", "target"),
        ("levels.retest_locations", "location"),
        ("levels.obstacles", "target"),
        ("levels.liquidity_sweep_reclaim", "reversal"),
        ("levels.major_structure_event_id", "identity"),
        ("levels.breakout_event_id", "identity"),
        ("ticker.last_price", "price"),
        ("data_quality", "quality"),
    )
    for path, root in paths:
        _add(rows, snapshot, path, root=root)
    payload = [row.to_dict() for row in rows]
    by_id = {row.evidence_id: row for row in rows}
    by_path = {row.path: row for row in rows}
    return EvidenceCatalog(tuple(rows), by_id, by_path, canonical_hash(payload))


def evidence_ref(catalog: EvidenceCatalog, path: str) -> str | None:
    item = catalog.by_path.get(path)
    return item.evidence_id if item else None


def validate_evidence_refs(catalog: EvidenceCatalog, refs: list[str] | tuple[str, ...]) -> bool:
    return bool(refs) and all(ref in catalog.by_id for ref in refs) and len(set(refs)) == len(refs)
