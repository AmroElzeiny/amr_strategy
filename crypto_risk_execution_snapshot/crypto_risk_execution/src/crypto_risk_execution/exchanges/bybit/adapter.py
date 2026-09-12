from __future__ import annotations
from decimal import Decimal
import hashlib,hmac,time,json,urllib.parse
from ..base import ExecutionExchangeAdapter, ExchangeError
from ..http import HttpClient
from ...models import AccountState, InstrumentRules
from ...canonical import D
class BybitAdapter(ExecutionExchangeAdapter):
    def __init__(self,api_key:str,api_secret:str,*,environment:str='DEMO',market_mode:str='DERIVATIVES',account_type:str='UNIFIED'):
        if environment not in {'DEMO','REAL'}: raise ExchangeError('UNSUPPORTED_ENVIRONMENT')
        self.environment=environment; self.market_mode=market_mode; self.api_key=api_key; self.secret=api_secret.encode(); self.account_type=account_type
        self.base='https://api-demo.bybit.com' if environment=='DEMO' else 'https://api.bybit.com'; self.http=HttpClient(self.base)
        self.private_ws='wss://stream-demo.bybit.com/v5/private' if environment=='DEMO' else 'wss://stream.bybit.com/v5/private'
    def _private(self,method,path,params=None,body=None):
        ts=str(int(time.time()*1000)); recv='5000'; payload=urllib.parse.urlencode(params or {}) if method=='GET' else json.dumps(body or {},separators=(',',':')); sig=hmac.new(self.secret,(ts+self.api_key+recv+payload).encode(),hashlib.sha256).hexdigest(); h={'X-BAPI-API-KEY':self.api_key,'X-BAPI-TIMESTAMP':ts,'X-BAPI-RECV-WINDOW':recv,'X-BAPI-SIGN':sig}; out=self.http.request(method,path,params=params if method=='GET' else None,body=body if method!='GET' else None,headers=h)
        if out.get('retCode') not in (0,None): raise ExchangeError('EXCHANGE_REJECTION',str(out.get('retMsg')))
        return out.get('result',out)
    def _cat(self): return 'spot' if self.market_mode=='SPOT' else 'linear'
    def get_account_state(self):
        r=self._private('GET','/v5/account/wallet-balance',{'accountType':self.account_type}); coins=((r.get('list') or [{}])[0].get('coin') or []); balances={c.get('coin',''):D(c.get('walletBalance','0')) for c in coins}; top=(r.get('list') or [{}])[0]; return AccountState(D(top.get('totalEquity','0')),D(top.get('totalWalletBalance','0')),D(top.get('totalAvailableBalance','0') or '0'),D(top.get('totalInitialMargin','0') or '0'),D(top.get('totalInitialMargin','0') or '0'),D(top.get('totalMaintenanceMargin','0') or '0'),D(top.get('totalPerpUPL','0') or '0'),balances=balances,raw=top)
    def get_instrument_rules(self,symbol):
        r=self.http.request('GET','/v5/market/instruments-info',params={'category':self._cat(),'symbol':symbol}); x=(r.get('result',{}).get('list') or [{}])[0]; pf=x.get('priceFilter',{}); lf=x.get('lotSizeFilter',{}); lev=x.get('leverageFilter',{})
        min_notional=lf.get('minNotionalValue') or lf.get('minOrderAmt'); max_qty=lf.get('maxMktOrderQty') or lf.get('maxOrderQty') or lf.get('maxLimitOrderQty')
        return InstrumentRules(symbol,D(pf.get('tickSize')),D(lf.get('qtyStep') or lf.get('basePrecision')),D(lf.get('minOrderQty') or '0'),D(max_qty) if max_qty else None,D(min_notional) if min_notional else None,None,D(lev.get('maxLeverage')) if lev.get('maxLeverage') else None,x.get('baseCoin',''),x.get('quoteCoin',''))
    def get_fee_schedule(self,symbol):
        r=self._private('GET','/v5/account/fee-rate',{'category':self._cat(),'symbol':symbol}); x=(r.get('list') or [{}])[0]; return {'maker':x.get('makerFeeRate'),'taker':x.get('takerFeeRate'),'source':'exchange'}
    def get_open_orders(self,symbol=None):
        p={'category':self._cat(),'openOnly':0};
        if symbol:p['symbol']=symbol
        return self._private('GET','/v5/order/realtime',p).get('list',[])
    def get_positions(self,symbol=None):
        if self.market_mode=='SPOT': return []
        p={'category':'linear','settleCoin':'USDT'}; 
        if symbol:p['symbol']=symbol
        return self._private('GET','/v5/position/list',p).get('list',[])
    def place_order(self,order):
        body=dict(order); body['category']=self._cat()
        if self.market_mode=='SPOT': body['isLeverage']=0
        return self._private('POST','/v5/order/create',body=body)
    def cancel_order(self,symbol,client_id): return self._private('POST','/v5/order/cancel',body={'category':self._cat(),'symbol':symbol,'orderLinkId':client_id})
    def get_executions(self,symbol=None):
        p={'category':self._cat()};
        if symbol:p['symbol']=symbol
        return self._private('GET','/v5/execution/list',p).get('list',[])
    def set_protection(self,position,stop,targets):
        symbol=position['symbol']
        if self.market_mode=='DERIVATIVES':
            body={'category':'linear','symbol':symbol,'tpslMode':'Full','stopLoss':str(stop),'positionIdx':int(position.get('positionIdx',0))};
            if targets: body['takeProfit']=str(targets[0]['price'])
            return self._private('POST','/v5/position/trading-stop',body=body)
        # Spot: create exchange-native conditional stop. Targets are managed separately to avoid reserving the same base inventory twice.
        side='Sell'; qty=str(position['qty']); body={'category':'spot','symbol':symbol,'side':side,'orderType':'Market','qty':qty,'triggerPrice':str(stop),'orderFilter':'StopOrder','isLeverage':0,'orderLinkId':position.get('stop_client_id','')}; return self._private('POST','/v5/order/create',body=body)
