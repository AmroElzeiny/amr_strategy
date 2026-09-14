from __future__ import annotations
from typing import Any
from .canonical import sha256_json
from .models import FrozenTradeIntent

def freeze_trade_intent(payload:dict[str,Any])->FrozenTradeIntent:
    frozen=dict(payload); identity={k:frozen.get(k) for k in ('signal_id','snapshot_id','symbol','environment','market_mode','direction','thesis_id','entry_plan','invalidation','targets')}; h=sha256_json(identity)
    rid='XR-'+h[:32]
    return FrozenTradeIntent(payload=frozen,execution_request_id=rid,execution_request_hash=h)
