from __future__ import annotations

from crypto_trading_orchestrator.models import SymbolState, WatchRecord
from crypto_trading_orchestrator.persistence import OrchestratorStore


def test_claim_lineage_watch_and_restart(tmp_path) -> None:
    path = tmp_path / "state.db"
    with OrchestratorStore(str(path)) as store:
        assert store.claim_once("signal", "one")
        assert not store.claim_once("signal", "one")
        store.upsert_lineage("sig", {"snapshot_id": "snap", "thesis_id": "t", "execution_id": ""})
        store.save_watch(WatchRecord("BTCUSDT", SymbolState.ARMED, 0.9))
    with OrchestratorStore(str(path)) as restored:
        assert restored.get_lineage("sig")["snapshot_id"] == "snap"
        assert restored.load_watches()["BTCUSDT"].state == SymbolState.ARMED
        assert restored.counts()["processed"] == 1
