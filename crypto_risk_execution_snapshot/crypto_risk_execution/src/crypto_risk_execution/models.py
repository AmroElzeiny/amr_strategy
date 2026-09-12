from __future__ import annotations
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Any
from .canonical import sha256_json, utc_iso

@dataclass(frozen=True)
class FrozenTradeIntent:
    payload: dict[str, Any]
    execution_request_id: str
    execution_request_hash: str

@dataclass(frozen=True)
class InstrumentRules:
    symbol: str; tick_size: Decimal; qty_step: Decimal; min_qty: Decimal
    max_qty: Decimal|None=None; min_notional: Decimal|None=None; max_notional: Decimal|None=None
    max_leverage: Decimal|None=None; base_asset: str=''; quote_asset: str=''

@dataclass(frozen=True)
class AccountState:
    equity: Decimal; wallet_balance: Decimal; available_balance: Decimal
    used_margin: Decimal=Decimal('0'); initial_margin: Decimal=Decimal('0'); maintenance_margin: Decimal=Decimal('0')
    unrealized_pnl: Decimal=Decimal('0'); realized_pnl: Decimal=Decimal('0')
    balances: dict[str,Decimal]=field(default_factory=dict)
    raw: dict[str,Any]=field(default_factory=dict, compare=False)

@dataclass(frozen=True)
class RiskAssessment:
    approved: bool; reason_codes: tuple[str,...]; desired_risk: Decimal=Decimal('0'); final_qty: Decimal=Decimal('0'); final_notional: Decimal=Decimal('0'); leverage: Decimal=Decimal('1'); snapshot: dict[str,Any]=field(default_factory=dict)

@dataclass(frozen=True)
class ExecutionPlan:
    execution_id: str; signal_id: str; symbol: str; side: str; order_type: str; qty: Decimal; price: Decimal|None; stop: Decimal; targets: tuple[dict[str,Any],...]; leverage: Decimal; reduce_only: bool=False; client_order_id: str=''

@dataclass(frozen=True)
class ExecutionReport:
    data: dict[str,Any]
    def to_dict(self)->dict[str,Any]: return dict(self.data)

def report_with_hash(data: dict[str,Any]) -> ExecutionReport:
    body=dict(data); body.pop('integrity_hash',None); body['integrity_hash']=sha256_json(body); return ExecutionReport(body)
