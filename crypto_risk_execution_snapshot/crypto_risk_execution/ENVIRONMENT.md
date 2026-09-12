# Environments

Only `DEMO` and `REAL` exist. Bybit DEMO REST is `https://api-demo.bybit.com`; real REST is `https://api.bybit.com`; private WS roots are `wss://stream-demo.bybit.com` and `wss://stream.bybit.com`. Public state uses mainnet public data when required. No Bybit Testnet fallback exists.

Binance supports REAL Spot and REAL USDⓈ-M derivatives. `BINANCE + DEMO` fails closed rather than mapping to Testnet.

`DRY_RUN=true` is an execution switch, not an environment. REAL trading additionally requires both `REAL_TRADING_ENABLED=true` and the exact acknowledgement phrase.
