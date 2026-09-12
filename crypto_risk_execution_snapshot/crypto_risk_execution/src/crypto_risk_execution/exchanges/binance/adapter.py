from __future__ import annotations
from decimal import Decimal
import hashlib,hmac,time,urllib.parse
from ..base import ExecutionExchangeAdapter, ExchangeError
from ..http import HttpClient
from ...models import AccountState, InstrumentRules
from ...canonical import D
class BinanceAdapter(ExecutionExchangeAdapter):
    def __init__(self,api_key:str,api_secret:str,*,environment='REAL',market_mode='SPOT'):
        if environment!='REAL': raise ExchangeError('UNSUPPORTED_ENVIRONMENT','Binance DEMO is intentionally not mapped to Testnet')
        self.market_mode=market_mode; self.key=api_key; self.secret=api_secret.encode(); self.base='https://api.binance.com' if market_mode=='SPOT' else 'https://fapi.binance.com'; self.http=HttpClient(self.base)
    def _signed(self,method,path,params=None):
        p=dict(params or {}); p['timestamp']=int(time.time()*1000); q=urllib.parse.urlencode(p); p['signature']=hmac.new(self.secret,q.encode(),hashlib.sha256).hexdigest(); return self.http.request(method,path,params=p,headers={'X-MBX-APIKEY':self.key})
    def get_account_state(self):
        if self.market_mode=='SPOT':
            r=self._signed('GET','/api/v3/account'); balances={b['asset']:D(b['free']) for b in r.get('balances',[])}; # exact cross-asset equity needs valuation; use quote free balance conservatively for sizing authority
            q=balances.get('USDT',Decimal('0')); return AccountState(q,q,q,balances=balances,raw=r)
        r=self._signed('GET','/fapi/v3/account'); return AccountState(D(r.get('totalMarginBalance','0')),D(r.get('totalWalletBalance','0')),D(r.get('availableBalance','0')),D(r.get('totalInitialMargin','0')),D(r.get('totalInitialMargin','0')),D(r.get('totalMaintMargin','0')),D(r.get('totalUnrealizedProfit','0')),balances={'USDT':D(r.get('availableBalance','0'))},raw=r)
    def get_instrument_rules(self,symbol):
        path='/api/v3/exchangeInfo' if self.market_mode=='SPOT' else '/fapi/v1/exchangeInfo'; r=self.http.request('GET',path,params={'symbol':symbol}); x=(r.get('symbols') or [{}])[0]; fs={f['filterType']:f for f in x.get('filters',[])}; lot=fs.get('LOT_SIZE',{}); mlot=fs.get('MARKET_LOT_SIZE',lot); price=fs.get('PRICE_FILTER',{}); notion=fs.get('NOTIONAL') or fs.get('MIN_NOTIONAL') or {}; return InstrumentRules(symbol,D(price.get('tickSize')),D(mlot.get('stepSize') or lot.get('stepSize')),D(mlot.get('minQty') or lot.get('minQty')),D(mlot.get('maxQty') or lot.get('maxQty')),D(notion.get('minNotional')) if notion.get('minNotional') else None,D(notion.get('maxNotional')) if notion.get('maxNotional') else None,None,x.get('baseAsset',''),x.get('quoteAsset',''))
    def get_fee_schedule(self,symbol):
        if self.market_mode=='SPOT': r=self._signed('GET','/api/v3/account/commission',{'symbol':symbol}); return {'maker':r.get('standardCommission',{}).get('maker'),'taker':r.get('standardCommission',{}).get('taker'),'source':'exchange'}
        # account-specific futures commission endpoint
        r=self._signed('GET','/fapi/v1/commissionRate',{'symbol':symbol}); return {'maker':r.get('makerCommissionRate'),'taker':r.get('takerCommissionRate'),'source':'exchange'}
    def get_open_orders(self,symbol=None): return self._signed('GET','/api/v3/openOrders' if self.market_mode=='SPOT' else '/fapi/v1/openOrders',{'symbol':symbol} if symbol else {})
    def get_positions(self,symbol=None):
        if self.market_mode=='SPOT': return []
        r=self._signed('GET','/fapi/v3/positionRisk',{'symbol':symbol} if symbol else {}); return r if isinstance(r,list) else [r]
    def place_order(self,order):
        path='/api/v3/order' if self.market_mode=='SPOT' else '/fapi/v1/order'; return self._signed('POST',path,order)
    def cancel_order(self,symbol,client_id): return self._signed('DELETE','/api/v3/order' if self.market_mode=='SPOT' else '/fapi/v1/order',{'symbol':symbol,'origClientOrderId':client_id})
    def get_executions(self,symbol=None):
        if not symbol: return []
        return self._signed('GET','/api/v3/myTrades' if self.market_mode=='SPOT' else '/fapi/v1/userTrades',{'symbol':symbol})
    def set_protection(self,position,stop,targets):
        symbol=position['symbol']; qty=str(position['qty']); side='SELL' if position.get('side','LONG')=='LONG' else 'BUY'
        if self.market_mode=='DERIVATIVES':
            # Current USD-M conditional algo endpoint; close/reduce semantics remain exchange-authoritative.
            params={'symbol':symbol,'side':side,'type':'STOP_MARKET','triggerPrice':str(stop),'quantity':qty,'reduceOnly':'true'}; return self._signed('POST','/fapi/v1/algoOrder',params)
        # Spot stop-limit/stop-loss order. A paired OCO target may be layered by the manager when both legs can share locked inventory safely.
        params={'symbol':symbol,'side':'SELL','type':'STOP_LOSS','quantity':qty,'stopPrice':str(stop)}; return self._signed('POST','/api/v3/order',params)
