from __future__ import annotations
from decimal import Decimal, ROUND_FLOOR
from ..canonical import D

def floor_step(value:Decimal, step:Decimal)->Decimal:
    if value<=0 or step<=0: return Decimal('0')
    return (value/step).to_integral_value(rounding=ROUND_FLOOR)*step

def normalize_open_qty(desired:Decimal,step:Decimal,min_qty:Decimal,max_qty:Decimal|None=None)->Decimal:
    q=floor_step(desired,step)
    if max_qty is not None: q=min(q,floor_step(max_qty,step))
    return q if q>=min_qty else Decimal('0')

def normalize_close_qty(desired:Decimal,current:Decimal,step:Decimal,min_qty:Decimal,*,close_all_dust:bool=True)->Decimal:
    q=floor_step(min(desired,current),step)
    if q<=0: return Decimal('0')
    residual=current-q
    if residual>0 and residual<min_qty:
        return current if close_all_dust else Decimal('0')
    return min(q,current)

def risk_budget(equity:Decimal,*,pct:Decimal|None,money:Decimal|None,max_pct:Decimal|None,max_money:Decimal|None)->Decimal:
    vals=[]
    if pct is not None: vals.append(equity*pct/Decimal('100'))
    if money is not None: vals.append(money)
    if max_pct is not None: vals.append(equity*max_pct/Decimal('100'))
    if max_money is not None: vals.append(max_money)
    if not vals: raise ValueError('risk_budget_unconfigured')
    out=min(vals)
    if out<=0: raise ValueError('risk_budget_nonpositive')
    return out

def qty_from_stop(risk:Decimal,entry:Decimal,stop:Decimal,*,fee_rate:Decimal,slippage_pct:Decimal)->Decimal:
    dist=abs(entry-stop)
    if dist<=0: raise ValueError('invalid_stop_distance')
    per_unit=dist+(entry*fee_rate*Decimal('2'))+(entry*slippage_pct/Decimal('100'))
    return risk/per_unit

def confidence_multiplier(conf:Decimal,bands=((Decimal('78'),Decimal('84'),Decimal('0.50')),(Decimal('85'),Decimal('91'),Decimal('0.75')),(Decimal('92'),Decimal('100'),Decimal('1.00'))))->Decimal:
    for lo,hi,m in bands:
        if lo<=conf<=hi: return min(Decimal('1'),m)
    return Decimal('0')
