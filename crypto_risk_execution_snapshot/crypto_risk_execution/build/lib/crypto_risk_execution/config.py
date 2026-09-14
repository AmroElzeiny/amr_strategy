from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
import os

def b(name:str,default:bool)->bool: return os.getenv(name,str(default)).strip().lower() in {'1','true','yes','on'}
def d(name:str,default:str|None=None)->Decimal|None:
    v=os.getenv(name,default)
    return None if v in (None,'') else Decimal(v)
def i(name:str,default:int)->int: return int(os.getenv(name,str(default)))
@dataclass(frozen=True)
class Settings:
    exchange:str=os.getenv('EXCHANGE','BYBIT').upper(); environment:str=os.getenv('TRADING_ENV','DEMO').upper(); market_mode:str=os.getenv('MARKET_MODE','DERIVATIVES').upper()
    execution_enabled:bool=b('EXECUTION_ENABLED',False); dry_run:bool=b('DRY_RUN',True); real_trading_enabled:bool=b('REAL_TRADING_ENABLED',False); real_ack:str=os.getenv('REAL_TRADING_ACK','')
    dedicated_required:bool=b('DEDICATED_TRADING_ACCOUNT_REQUIRED',True); reject_withdraw:bool=b('REJECT_KEYS_WITH_WITHDRAW_PERMISSION',True); reject_read_only:bool=b('REJECT_READ_ONLY_KEY_FOR_EXECUTION',True)
    risk_pct:Decimal|None=d('RISK_PER_TRADE_PCT'); risk_money:Decimal|None=d('RISK_PER_TRADE_MONEY'); max_risk_pct:Decimal|None=d('MAX_RISK_PER_TRADE_PCT'); max_risk_money:Decimal|None=d('MAX_RISK_PER_TRADE_MONEY')
    max_daily_pct:Decimal|None=d('MAX_DAILY_LOSS_PCT'); max_daily_money:Decimal|None=d('MAX_DAILY_LOSS_MONEY'); max_loss_pct:Decimal|None=d('MAX_LOSS_LOCK_PCT'); max_loss_money:Decimal|None=d('MAX_LOSS_LOCK_MONEY')
    leverage:Decimal=d('DERIVATIVES_LEVERAGE','1') or Decimal('1'); max_leverage:Decimal=d('MAX_ALLOWED_LEVERAGE','3') or Decimal('3'); margin_mode:str=os.getenv('DERIVATIVES_MARGIN_MODE','ISOLATED').upper()
    fee_fallback:Decimal|None=d('FEE_RATE_FALLBACK'); slippage_pct:Decimal=d('MAX_MARKET_SLIPPAGE_PCT','0.15') or Decimal('0.15')
    max_chase_pct:Decimal=d('MAX_CHASE_DISTANCE_PCT','0.50') or Decimal('0.50')
    min_free_margin_pct:Decimal=d('MIN_FREE_MARGIN_AFTER_ENTRY_PCT','10') or Decimal('10'); margin_buffer_pct:Decimal=d('MARGIN_SAFETY_BUFFER_PCT','5') or Decimal('5')
    one_symbol:bool=b('ONE_ACTIVE_POSITION_PER_SYMBOL',True); one_thesis:bool=b('ONE_ACTIVE_POSITION_PER_THESIS',True); pyramiding:bool=b('PYRAMIDING_ENABLED',False)
    state_db:str=os.getenv('STATE_DB','./data/execution_state.db')
    @property
    def real_authorized(self)->bool: return self.real_trading_enabled and self.real_ack=='I_UNDERSTAND_THIS_SENDS_REAL_ORDERS'
