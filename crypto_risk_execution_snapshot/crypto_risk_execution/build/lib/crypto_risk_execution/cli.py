from __future__ import annotations
import argparse,json
from datetime import datetime,timezone
from .validation import validate_trade_intent
from .public import risk_assess, execute_trade_intent, reconcile_account, emergency_flatten
from .config import Settings
from .persistence.state import StateStore
from .risk.locks import LossLocks

def load(path):
    with open(path,encoding='utf-8') as f:return json.load(f)
def main(argv=None):
    p=argparse.ArgumentParser(prog='crypto_risk_execution'); sub=p.add_subparsers(dest='cmd',required=True)
    for c in ('validate','assess','execute'): q=sub.add_parser(c); q.add_argument('intent')
    sub.add_parser('reconcile'); sub.add_parser('status'); sub.add_parser('risk-status'); f=sub.add_parser('flatten'); f.add_argument('--reason',required=True); sub.add_parser('cancel-managed-orders'); u=sub.add_parser('unlock-max-loss'); u.add_argument('--acknowledge',required=True); u.add_argument('--reason',required=True); u.add_argument('--operator-timestamp',default=datetime.now(timezone.utc).isoformat())
    a=p.parse_args(argv); s=Settings(); store=StateStore(s.state_db)
    if a.cmd=='validate': ok,reasons=validate_trade_intent(load(a.intent)); out={'valid':ok,'reason_codes':reasons}
    elif a.cmd=='assess': out=risk_assess(load(a.intent),settings=s,store=store).__dict__
    elif a.cmd=='execute': out=execute_trade_intent(load(a.intent),settings=s,store=store).to_dict()
    elif a.cmd=='reconcile': out=reconcile_account(settings=s,store=store)
    elif a.cmd in ('status','risk-status'): out={'reconciliation':store.get('reconciliation'),'daily_loss':store.get('daily_loss'),'max_loss':store.get('max_loss'),'execution_health_lock':store.get('execution_health_lock')}
    elif a.cmd=='flatten': out=emergency_flatten(reason=a.reason,settings=s,store=store)
    elif a.cmd=='cancel-managed-orders': out={'accepted':True,'scope':'managed_only','note':'requires live adapter to enumerate and cancel registry-owned orders'}
    elif a.cmd=='unlock-max-loss': LossLocks(store).unlock_max(a.acknowledge,a.reason,a.operator_timestamp); out={'unlocked':True}
    print(json.dumps(out,default=str,indent=2))
if __name__=='__main__': main()
