from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from .canonical import sha256_json
from .contracts import CONTRACT_VERSION
REQUIRED=('contract_version','signal_id','snapshot_id','created_at_utc','exchange','environment','market_mode','symbol','pattern_type','direction','order_intent','decision','thesis_id','attempt_no','final_confidence','entry_plan','invalidation','targets','risk_reward','ttl_ms','config_version','strategy_version','integrity_hash')

def trade_intent_entry(payload:dict[str,Any])->Any:
    """Read the producer-owned HM_CRYPTO_V1 entry vocabulary without mutating it."""
    plan=payload.get('entry_plan') or {}
    for field in ('expected_entry','price','entry_reference','trigger_price_if_any'):
        value=plan.get(field)
        if value not in (None,''):
            return value
    return None

def intent_hash(payload:dict[str,Any])->str:
    body=dict(payload); body.pop('integrity_hash',None); return sha256_json(body)
def validate_trade_intent(payload:dict[str,Any], *, now:datetime|None=None)->tuple[bool,tuple[str,...]]:
    reasons=[]
    if any(k not in payload for k in REQUIRED): reasons.append('CONTRACT_MISMATCH')
    if payload.get('contract_version')!=CONTRACT_VERSION: reasons.append('CONTRACT_MISMATCH')
    if payload.get('integrity_hash')!=intent_hash(payload): reasons.append('INTENT_INTEGRITY_FAILURE')
    if payload.get('order_intent')=='NONE': reasons.append('ORDER_INTENT_NONE')
    if payload.get('order_intent')=='OPEN' and payload.get('decision')!='ENTER': reasons.append('DECISION_NOT_ENTER')
    if payload.get('market_mode')=='SPOT' and payload.get('direction')=='SHORT' and payload.get('order_intent')=='OPEN': reasons.append('UNSUPPORTED_SPOT_SHORT')
    try:
        created=datetime.fromisoformat(str(payload['created_at_utc']).replace('Z','+00:00')).astimezone(timezone.utc)
        now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if (now-created).total_seconds()*1000 > int(payload['ttl_ms']): reasons.append('SIGNAL_EXPIRED')
    except Exception: reasons.append('CONTRACT_MISMATCH')
    inv=payload.get('invalidation') or {}; ep=payload.get('entry_plan') or {}
    if payload.get('order_intent')=='OPEN':
        try:
            entry=float(trade_intent_entry(payload)); stop=float(inv.get('stop_price',inv.get('price')))
            if not (entry>0 and stop>0 and entry!=stop): reasons.append('INVALID_STOP')
            elif payload.get('direction')=='LONG' and not stop<entry: reasons.append('INVALID_STOP')
            elif payload.get('direction')=='SHORT' and not stop>entry: reasons.append('INVALID_STOP')
        except Exception: reasons.append('INVALID_STOP')
    return (not reasons,tuple(dict.fromkeys(reasons)))
