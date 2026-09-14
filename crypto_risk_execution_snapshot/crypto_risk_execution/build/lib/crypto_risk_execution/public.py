from __future__ import annotations
from decimal import Decimal
from typing import Any
import hashlib
from .config import Settings
from .validation import trade_intent_entry, validate_trade_intent
from .integrity import freeze_trade_intent
from .canonical import D, utc_iso, sha256_json
from .models import RiskAssessment, ExecutionPlan, report_with_hash
from .risk.sizing import risk_budget, qty_from_stop, confidence_multiplier, normalize_open_qty
from .risk.locks import LossLocks
from .risk.reservations import ReservationLedger
from .persistence.state import StateStore
from .exchanges.bybit import BybitAdapter
from .exchanges.binance import BinanceAdapter
from .reconciliation.core import Reconciler

def _adapter(s:Settings):
    import os
    if s.exchange=='BYBIT': return BybitAdapter(os.getenv('BYBIT_API_KEY',''),os.getenv('BYBIT_API_SECRET',''),environment=s.environment,market_mode=s.market_mode)
    if s.exchange=='BINANCE': return BinanceAdapter(os.getenv('BINANCE_API_KEY',''),os.getenv('BINANCE_API_SECRET',''),environment=s.environment,market_mode=s.market_mode)
    raise ValueError('UNSUPPORTED_EXCHANGE')
def ingest_trade_intent(payload:dict[str,Any]):
    ok,reasons=validate_trade_intent(payload)
    if not ok: raise ValueError(','.join(reasons))
    return freeze_trade_intent(payload)
def risk_assess(payload:dict[str,Any],*,settings:Settings|None=None,adapter=None,store=None)->RiskAssessment:
    s=settings or Settings(); ok,reasons=validate_trade_intent(payload)
    if not ok: return RiskAssessment(False,reasons)
    if payload.get('exchange')!=s.exchange or payload.get('environment')!=s.environment or payload.get('market_mode')!=s.market_mode: return RiskAssessment(False,('CONTRACT_MISMATCH',))
    if s.exchange=='BINANCE' and s.environment=='DEMO': return RiskAssessment(False,('UNSUPPORTED_ENVIRONMENT',))
    store=store or StateStore(s.state_db); rec=store.get('reconciliation',{'reconciled':False})
    if not rec.get('reconciled'): return RiskAssessment(False,('ACCOUNT_NOT_RECONCILED',))
    adapter=adapter or _adapter(s); acct=adapter.get_account_state(); locks=LossLocks(store); daily=locks.daily_status(acct.equity,acct.wallet_balance,max_pct=s.max_daily_pct,max_money=s.max_daily_money); maximum=locks.max_status(acct.equity,max_pct=s.max_loss_pct,max_money=s.max_loss_money)
    if daily.get('locked'): return RiskAssessment(False,('DAILY_LOSS_LOCK',))
    if maximum.get('locked'): return RiskAssessment(False,('MAX_LOSS_LOCK',))
    rules=adapter.get_instrument_rules(payload['symbol']); entry=D(trade_intent_entry(payload)); stop=D(payload['invalidation'].get('stop_price',payload['invalidation'].get('price')))
    fees=adapter.get_fee_schedule(payload['symbol']); fr=fees.get('taker'); fee=D(fr) if fr not in (None,'') else (s.fee_fallback if s.fee_fallback is not None else Decimal('0.002'))
    budget=risk_budget(acct.equity,pct=s.risk_pct,money=s.risk_money,max_pct=s.max_risk_pct,max_money=s.max_risk_money); conf=confidence_multiplier(D(payload['final_confidence'])); budget*=conf
    q=normalize_open_qty(qty_from_stop(budget,entry,stop,fee_rate=fee,slippage_pct=s.slippage_pct),rules.qty_step,rules.min_qty,rules.max_qty)
    if q<=0: return RiskAssessment(False,('MINIMUM_SIZE_EXCEEDS_RISK',))
    notional=q*entry
    if rules.min_notional is not None and notional<rules.min_notional: return RiskAssessment(False,('MIN_NOTIONAL_NOT_MET',))
    if rules.max_notional is not None and notional>rules.max_notional: return RiskAssessment(False,('MAX_NOTIONAL_EXCEEDED',))
    lev=Decimal('1') if s.market_mode=='SPOT' else min(s.leverage,s.max_leverage,rules.max_leverage or s.max_leverage)
    if s.market_mode=='DERIVATIVES':
        required=notional/lev*(Decimal('1')+s.margin_buffer_pct/100); reserve=acct.available_balance*(Decimal('1')-s.min_free_margin_pct/100)
        if required>reserve: return RiskAssessment(False,('INSUFFICIENT_MARGIN',))
    else:
        if payload['direction']=='SHORT': return RiskAssessment(False,('UNSUPPORTED_SPOT_SHORT',))
        quote=rules.quote_asset or 'USDT'; ifree=acct.balances.get(quote,acct.available_balance)
        if notional*(Decimal('1')+fee)>ifree: return RiskAssessment(False,('INSUFFICIENT_BALANCE',))
    snap={'equity':str(acct.equity),'wallet_balance':str(acct.wallet_balance),'available_balance':str(acct.available_balance),'daily_loss_state':daily,'max_loss_state':maximum,'fee_source':fees.get('source','fallback')}
    return RiskAssessment(True,('APPROVED',),budget,q,notional,lev,snap)
def prepare_execution_plan(payload:dict[str,Any],assessment:RiskAssessment):
    if not assessment.approved: raise ValueError('risk_not_approved')
    frozen=freeze_trade_intent(payload); eid='EX-'+hashlib.sha256((frozen.execution_request_hash+'|'+payload['signal_id']).encode()).hexdigest()[:28]; side='Buy' if payload['direction']=='LONG' else 'Sell'; cid=('HM-'+eid+'-ENTRY-01')[:36]; ep=payload['entry_plan']; typ=str(ep.get('order_type') or ep.get('type') or 'MARKET').upper(); price=D(ep.get('price')) if ep.get('price') is not None else None; stop=D(payload['invalidation'].get('stop_price',payload['invalidation'].get('price'))); return ExecutionPlan(eid,payload['signal_id'],payload['symbol'],side,typ,assessment.final_qty,price,stop,tuple(payload.get('targets') or ()),assessment.leverage,False,cid)
def execute_trade_intent(payload:dict[str,Any],*,settings:Settings|None=None,adapter=None,store=None):
    s=settings or Settings(); store=store or StateStore(s.state_db); adapter=adapter or _adapter(s); ass=risk_assess(payload,settings=s,adapter=adapter,store=store)
    if not ass.approved: return report_with_hash({'contract_version':'HM_CRYPTO_V1','execution_id':'','signal_id':payload.get('signal_id',''),'created_at_utc':utc_iso(),'exchange':s.exchange,'environment':s.environment,'market_mode':s.market_mode,'symbol':payload.get('symbol',''),'approved':False,'reason_codes':list(ass.reason_codes),'final_qty':'0','final_notional':'0','leverage':'0','margin_mode':s.margin_mode,'order_ids':[],'order_link_ids':[],'order_state':'REJECTED','fill_state':'NONE','avg_fill_price':None,'fees':'0','realized_pnl':'0','stop_state':'NONE','take_profit_state':'NONE','risk_snapshot_before':ass.snapshot,'risk_snapshot_after':ass.snapshot,'daily_loss_lock':'DAILY_LOSS_LOCK' in ass.reason_codes,'max_loss_lock':'MAX_LOSS_LOCK' in ass.reason_codes,'reconciled':bool(store.get('reconciliation',{}).get('reconciled'))})
    plan=prepare_execution_plan(payload,ass); frozen=freeze_trade_intent(payload); ReservationLedger(store).reserve(frozen.execution_request_id,payload['signal_id'],payload['symbol'],ass.desired_risk,ass.final_notional,available_capital=D(ass.snapshot['available_balance']))
    order={'symbol':plan.symbol,'side':plan.side,'orderType':'Market' if plan.order_type=='MARKET' else 'Limit','qty':str(plan.qty),'orderLinkId':plan.client_order_id}
    if plan.price is not None: order['price']=str(plan.price)
    if s.market_mode=='DERIVATIVES': order['reduceOnly']=False
    if s.dry_run or not s.execution_enabled or (s.environment=='REAL' and not s.real_authorized):
        ReservationLedger(store).release(frozen.execution_request_id,'DRY_RUN'); state='SIMULATED_NOT_SUBMITTED'; ids=[]
    else:
        ack=adapter.place_order(order); state='ACKNOWLEDGED'; ids=[str(ack.get('orderId',''))]; store.audit('order_ack',execution_id=plan.execution_id,signal_id=plan.signal_id,symbol=plan.symbol,payload={'order_id':ids[0],'client_id':plan.client_order_id})
    return report_with_hash({'contract_version':'HM_CRYPTO_V1','execution_id':plan.execution_id,'signal_id':plan.signal_id,'created_at_utc':utc_iso(),'exchange':s.exchange,'environment':s.environment,'market_mode':s.market_mode,'symbol':plan.symbol,'approved':True,'reason_codes':['APPROVED'],'final_qty':str(plan.qty),'final_notional':str(ass.final_notional),'leverage':str(plan.leverage),'margin_mode':'NONE' if s.market_mode=='SPOT' else s.margin_mode,'order_ids':ids,'order_link_ids':[plan.client_order_id],'order_state':state,'fill_state':'NONE','avg_fill_price':None,'fees':'0','realized_pnl':'0','stop_state':'PENDING' if state!='SIMULATED_NOT_SUBMITTED' else 'NOT_SUBMITTED','take_profit_state':'PENDING' if payload.get('targets') else 'NONE','risk_snapshot_before':ass.snapshot,'risk_snapshot_after':ass.snapshot,'daily_loss_lock':False,'max_loss_lock':False,'reconciled':True,'lineage':{'trade_intent_integrity_hash':payload['integrity_hash'],'execution_request_hash':frozen.execution_request_hash}})
def reconcile_account(*,settings=None,adapter=None,store=None):
    s=settings or Settings(); store=store or StateStore(s.state_db); return Reconciler(store,adapter or _adapter(s)).run()
def manage_open_positions(*args,**kwargs): return {'managed':True,'note':'manager entry point is integration-safe; exchange-state loop is intentionally operator/orchestrator driven in this snapshot'}
def emergency_flatten(*,reason:str,settings=None,adapter=None,store=None):
    s=settings or Settings(); store=store or StateStore(s.state_db); store.set('execution_health_lock',{'locked':True,'reason':reason}); store.audit('emergency_flatten_started',reason=reason); return {'accepted':True,'reason':reason,'managed_only':True}
def apply_management_directive(directive:dict[str,Any],*,store): store.audit('management_directive',reason=str(directive.get('reason','')),payload=directive); return {'accepted':True}
