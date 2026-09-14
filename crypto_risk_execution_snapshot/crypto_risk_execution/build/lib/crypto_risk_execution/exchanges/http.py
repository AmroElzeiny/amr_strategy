from __future__ import annotations
import json,time,urllib.request,urllib.parse,urllib.error
from typing import Any
class HttpClient:
    def __init__(self,base:str,timeout:float=10): self.base=base.rstrip('/'); self.timeout=timeout
    def request(self,method:str,path:str,*,params=None,headers=None,body=None)->dict[str,Any]:
        q=('?'+urllib.parse.urlencode(params)) if params else ''; data=None if body is None else json.dumps(body,separators=(',',':')).encode(); h={'Content-Type':'application/json'}; h.update(headers or {})
        req=urllib.request.Request(self.base+path+q,data=data,headers=h,method=method)
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as r: raw=r.read().decode(); return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e: raise RuntimeError(f'http_{e.code}:{e.read().decode(errors="replace")[:500]}')
