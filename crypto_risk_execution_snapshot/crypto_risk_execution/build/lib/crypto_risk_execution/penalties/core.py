from __future__ import annotations
from decimal import Decimal
from dataclasses import dataclass
@dataclass(frozen=True)
class PenaltyDecision: action:str; reason:str; event_id:str
class PenaltyEngine:
    def evaluate(self,*,position_id:str,current_r:Decimal,mfe_r:Decimal,seconds:int,mae_trigger:Decimal|None=None,giveback_mfe:Decimal|None=None,giveback_floor:Decimal|None=None,stuck_seconds:int|None=None,stuck_min_mfe:Decimal|None=None):
        import hashlib
        if mae_trigger is not None and current_r<=-abs(mae_trigger): reason='PENALTY_MAE'
        elif giveback_mfe is not None and giveback_floor is not None and mfe_r>=giveback_mfe and current_r<=giveback_floor: reason='PENALTY_GIVEBACK'
        elif stuck_seconds is not None and stuck_min_mfe is not None and seconds>=stuck_seconds and mfe_r<stuck_min_mfe: reason='PENALTY_STUCK'
        else: return None
        return PenaltyDecision('CLOSE',reason,hashlib.sha256(f'{position_id}|{reason}'.encode()).hexdigest())
