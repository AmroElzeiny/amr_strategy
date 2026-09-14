from __future__ import annotations
from ..persistence.state import StateStore
class Reconciler:
    def __init__(self,store,adapter): self.store=store; self.adapter=adapter
    def run(self):
        orders=self.adapter.get_open_orders(); positions=self.adapter.get_positions(); managed_prefix=('XR-','HM-'); foreign_orders=[o for o in orders if not str(o.get('orderLinkId') or o.get('clientOrderId') or o.get('origClientOrderId') or '').startswith(managed_prefix)]; ambiguous_positions=[]
        for p in positions:
            qty=p.get('size',p.get('positionAmt','0'))
            try: nonzero=abs(float(qty))>0
            except: nonzero=False
            if nonzero:
                # ownership cannot be proven from exchange position alone unless local lineage exists
                symbol=p.get('symbol','');
                with self.store.tx() as db: known=db.execute('SELECT 1 FROM managed_positions WHERE symbol=?',(symbol,)).fetchone()
                if not known: ambiguous_positions.append(p)
        ok=not ambiguous_positions
        state={'reconciled':ok,'foreign_orders':len(foreign_orders),'ambiguous_positions':len(ambiguous_positions)}; self.store.set('reconciliation',state); self.store.audit('reconciliation',reason='ok' if ok else 'ambiguous_position',payload=state); return state
