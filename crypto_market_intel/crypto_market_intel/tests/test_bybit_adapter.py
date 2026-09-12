from __future__ import annotations

import json

import httpx

from crypto_market_intel.bybit import BybitV5PublicAdapter


def test_linear_instruments_full_cursor_pagination(settings) -> None:
    calls: list[str] = []
    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor", "")
        calls.append(cursor)
        if not cursor:
            result = {"list": [{"symbol":"AAAUSDT","baseCoin":"AAA","quoteCoin":"USDT","status":"Trading","launchTime":"1000","priceFilter":{"tickSize":"0.01"},"lotSizeFilter":{"qtyStep":"1","minOrderQty":"1"}}], "nextPageCursor":"page2"}
        else:
            result = {"list": [{"symbol":"BBBUSDT","baseCoin":"BBB","quoteCoin":"USDT","status":"Trading","launchTime":"1000","priceFilter":{"tickSize":"0.001"},"lotSizeFilter":{"qtyStep":"1","minOrderQty":"1"}}], "nextPageCursor":""}
        return httpx.Response(200, json={"retCode":0,"retMsg":"OK","result":result})
    client = httpx.Client(base_url="https://api.bybit.com", transport=httpx.MockTransport(handler))
    adapter = BybitV5PublicAdapter(settings, client=client)
    rows = adapter.instruments()
    assert [x.symbol for x in rows] == ["AAAUSDT", "BBBUSDT"]
    assert calls == ["", "page2"]


def test_demo_public_market_data_still_routes_mainnet_public(settings) -> None:
    assert settings.trading_env.value == "DEMO"
    assert settings.bybit_public_rest_base == "https://api.bybit.com"
    assert settings.bybit_public_ws_url().startswith("wss://stream.bybit.com/")
    assert "testnet" not in settings.bybit_public_ws_url().lower()
