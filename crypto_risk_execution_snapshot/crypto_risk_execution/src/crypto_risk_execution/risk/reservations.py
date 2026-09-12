from __future__ import annotations
from decimal import Decimal
from ..persistence.state import StateStore
from ..canonical import utc_iso
class ReservationLedger:
    def __init__(self,store:StateStore): self.store=store
    def reserve(self,rid:str,signal_id:str,symbol:str,risk:Decimal,capital:Decimal,*,available_capital:Decimal,max_total_risk:Decimal|None=None):
        with self.store.tx() as db:
            if db.execute("SELECT 1 FROM reservations WHERE signal_id=? AND state IN ('RESERVED','SUBMITTED')",(signal_id,)).fetchone(): raise ValueError('DUPLICATE_SIGNAL')
            active=db.execute("SELECT risk,capital FROM reservations WHERE state IN ('RESERVED','SUBMITTED')").fetchall(); total_cap=sum((Decimal(r['capital']) for r in active),Decimal('0')); total_risk=sum((Decimal(r['risk']) for r in active),Decimal('0'))
            if total_cap+capital>available_capital: raise ValueError('INSUFFICIENT_BALANCE')
            if max_total_risk is not None and total_risk+risk>max_total_risk: raise ValueError('TOTAL_RISK_EXCEEDED')
            db.execute('INSERT INTO reservations VALUES(?,?,?,?,?,?,?)',(rid,signal_id,symbol,str(risk),str(capital),'RESERVED',utc_iso()))
    def release(self,rid:str,state='RELEASED'):
        with self.store.tx() as db: db.execute('UPDATE reservations SET state=?,updated=? WHERE id=?',(state,utc_iso(),rid))
