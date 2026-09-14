from __future__ import annotations
from decimal import Decimal
from datetime import datetime, timezone
from ..persistence.state import StateStore
from ..canonical import utc_iso

class LossLocks:
    def __init__(self,store:StateStore): self.store=store
    def daily_status(self,equity:Decimal,balance:Decimal,*,max_pct:Decimal|None,max_money:Decimal|None):
        day=datetime.now(timezone.utc).date().isoformat(); st=self.store.get('daily_loss')
        if not st or st.get('day')!=day:
            st={'day':day,'anchor_equity':str(equity),'anchor_balance':str(balance),'locked':False,'created_at':utc_iso()}; self.store.set('daily_loss',st)
        anchor=Decimal(st['anchor_equity']); loss=max(Decimal('0'),anchor-equity); pct=(loss/anchor*100) if anchor>0 else Decimal('100')
        hit=(max_pct is not None and pct>=max_pct) or (max_money is not None and loss>=max_money)
        if hit and not st['locked']:
            st|={'locked':True,'triggered_at':utc_iso(),'loss':str(loss),'loss_pct':str(pct)}; self.store.set('daily_loss',st); self.store.audit('daily_loss_lock',reason='threshold_reached',payload=st)
        return st
    def max_status(self,equity:Decimal,*,max_pct:Decimal|None,max_money:Decimal|None):
        st=self.store.get('max_loss') or {'high_watermark':str(equity),'reference_equity':str(equity),'locked':False}
        h=max(Decimal(st['high_watermark']),equity); st['high_watermark']=str(h); loss=max(Decimal('0'),h-equity); pct=(loss/h*100) if h>0 else Decimal('100')
        hit=(max_pct is not None and pct>=max_pct) or (max_money is not None and loss>=max_money)
        if hit: st|={'locked':True,'triggered_at':st.get('triggered_at') or utc_iso(),'drawdown':str(loss),'drawdown_pct':str(pct),'reason':'MAX_LOSS'}
        self.store.set('max_loss',st); return st
    def unlock_max(self,phrase:str,reason:str,operator_timestamp:str):
        if phrase!='I_ACKNOWLEDGE_MAX_LOSS_UNLOCK': raise PermissionError('invalid_confirmation_phrase')
        st=self.store.get('max_loss') or {}
        st['locked']=False; st['unlocked_at']=utc_iso(); st['unlock_reason']=reason; st['operator_timestamp']=operator_timestamp; self.store.set('max_loss',st); self.store.audit('max_loss_unlock',reason=reason,payload={'operator_timestamp':operator_timestamp})
