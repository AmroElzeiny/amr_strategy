from decimal import Decimal
from pathlib import Path
import json
from crypto_risk_execution.canonical import sha256_json
from crypto_risk_execution.validation import validate_trade_intent,intent_hash
from crypto_risk_execution.risk.sizing import floor_step,normalize_open_qty,normalize_close_qty,risk_budget,qty_from_stop,confidence_multiplier
from crypto_risk_execution.persistence.state import StateStore
from crypto_risk_execution.risk.locks import LossLocks

def intent():
    x={'contract_version':'HM_CRYPTO_V1','signal_id':'S1','snapshot_id':'P1','created_at_utc':'2099-01-01T00:00:00Z','exchange':'BYBIT','environment':'DEMO','market_mode':'DERIVATIVES','symbol':'BTCUSDT','pattern_type':'BREAKOUT','direction':'LONG','order_intent':'OPEN','decision':'ENTER','thesis_id':'T1','attempt_no':1,'deterministic_confidence':90,'ai_confidence':90,'final_confidence':90,'entry_plan':{'expected_entry':'100'},'invalidation':{'stop_price':'99'},'targets':[{'price':'102'}],'projected_extension_target':'103','risk_reward':'2','penalties':[],'blockers':[],'evidence':[],'ttl_ms':9999999999999,'config_version':'c1','strategy_version':'s1','ai_metadata':{}}
    x['integrity_hash']=intent_hash(x); return x

def test_contract_integrity_valid(): assert validate_trade_intent(intent())[0]
def test_bad_hash_rejected():
    x=intent(); x['integrity_hash']='0'*64; assert 'INTENT_INTEGRITY_FAILURE' in validate_trade_intent(x)[1]
def test_spot_short_rejected():
    x=intent(); x['market_mode']='SPOT'; x['direction']='SHORT'; x['integrity_hash']=intent_hash(x); assert 'UNSUPPORTED_SPOT_SHORT' in validate_trade_intent(x)[1]
def test_floor_never_rounds_up(): assert floor_step(Decimal('1.239'),Decimal('0.01'))==Decimal('1.23')
def test_open_minimum_does_not_raise(): assert normalize_open_qty(Decimal('0.009'),Decimal('0.001'),Decimal('0.01'))==0
def test_close_dust_can_close_all_only_reducing(): assert normalize_close_qty(Decimal('0.095'),Decimal('0.10'),Decimal('0.01'),Decimal('0.01'))==Decimal('0.09')
def test_budget_tighter_cap(): assert risk_budget(Decimal('1000'),pct=Decimal('2'),money=None,max_pct=Decimal('1'),max_money=Decimal('8'))==Decimal('8')
def test_conf_never_exceeds_one(): assert confidence_multiplier(Decimal('100'))<=1
def test_daily_and_max_lock_persist(tmp_path):
    st=StateStore(str(tmp_path/'x.db')); l=LossLocks(st); l.daily_status(Decimal('100'),Decimal('100'),max_pct=Decimal('5'),max_money=None); assert l.daily_status(Decimal('94'),Decimal('94'),max_pct=Decimal('5'),max_money=None)['locked']; l.max_status(Decimal('100'),max_pct=Decimal('5'),max_money=None); assert l.max_status(Decimal('94'),max_pct=Decimal('5'),max_money=None)['locked']; st2=StateStore(str(tmp_path/'x.db')); assert st2.get('daily_loss')['locked'] and st2.get('max_loss')['locked']
def test_no_testnet_runtime_urls():
    src='\n'.join(p.read_text(errors='ignore') for p in (Path(__file__).parents[1]/'src').rglob('*.py'))
    assert 'api-testnet.bybit.com' not in src and 'stream-testnet.bybit.com' not in src and 'testnet.binance' not in src
