# Environment and routing

## Supported live source

`EXCHANGE=BYBIT` is the implemented live market-data source. `BINANCE` exists only in the frozen cross-package enum and is not advertised as a live adapter.

`TRADING_ENV` accepts only `DEMO` or `REAL`; there is no Testnet mode and no Testnet URL. Bybit public market data uses mainnet public REST/WS in both environments. The configured demo REST/private WS roots are retained for frozen environment interoperability with later packages, but this package never authenticates or performs a private/order call.

- Real public REST: `https://api.bybit.com`
- Demo public REST used by Package 1: mainnet public `https://api.bybit.com`
- Public WS root: `wss://stream.bybit.com`
- Demo private root (not used here): `wss://stream-demo.bybit.com`

`MARKET_MODE=SPOT` selects Bybit spot public category and explicitly marks derivatives-only context unavailable with `None` fields. This package has no margin, borrowing, short-opening, leverage or asset-selling path. `MARKET_MODE=DERIVATIVES` defaults to Bybit linear USDT-style market data; execution leverage/margin capability belongs to the later risk/execution package.

All configurable thresholds and feature toggles are represented in `.env.example`. Blank optional values mean “not configured”, not numeric zero. No secret/API-key variable is required by Package 1.

## Official Bybit documentation reviewed

- Instruments Info: https://bybit-exchange.github.io/docs/v5/market/instrument
- Tickers: https://bybit-exchange.github.io/docs/v5/market/tickers
- Kline: https://bybit-exchange.github.io/docs/v5/market/kline
- Recent Public Trades: https://bybit-exchange.github.io/docs/v5/market/recent-trade
- Orderbook REST: https://bybit-exchange.github.io/docs/v5/market/orderbook
- Open Interest: https://bybit-exchange.github.io/docs/v5/market/open-interest
- Funding History: https://bybit-exchange.github.io/docs/v5/market/history-fund-rate
- Public Trade WS: https://bybit-exchange.github.io/docs/v5/websocket/public/trade
- Orderbook WS: https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook
- All Liquidation WS: https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation
- Demo Trading: https://bybit-exchange.github.io/docs/v5/demo
- Rate Limits: https://bybit-exchange.github.io/docs/v5/rate-limit
