# Environment and configuration

`StrategyConfig` is immutable and contributes its full canonical representation to the config hash.
Changing any configured threshold, weight, penalty, routing option or research policy therefore changes
strategy identity. Environment variables are read explicitly; no `.env` file is auto-loaded.

Use `.env.example` as the complete deployment template. Secret values must be injected by the runtime
secret manager/process environment and must never be committed.

## Modes

`TRADING_ENV` accepts `DEMO` or `REAL`. `MARKET_MODE` accepts `SPOT` or `DERIVATIVES`. This package
performs no exchange routing; the mode only constrains strategy semantics. In SPOT, an opening SHORT
can never produce ENTER. In DERIVATIVES, LONG and SHORT candidates are allowed strategically, while
leverage and margin authority remain outside this package.

## Fail-closed defaults

- Contract mismatch or malformed required input raises/fails closed.
- `INVALID` data cannot ENTER.
- Critical stale data cannot ENTER by default.
- `DEGRADED` data cannot ENTER by default.
- AI-required ENTER downgrades when all configured AI providers fail.
- Unknown/duplicate AI evidence references or identity mismatch invalidate the AI response.
- Late AI results are ignored.

## AI provider endpoints

OpenCode Go base URL defaults to `https://opencode.ai/zen/go`. The provider performs protocol selection
by exact configured model ID; it never silently sends an unknown model to an arbitrary endpoint.
`/v1/models` can be queried by the optional provider health/discovery path when an API key is available.

OpenAI fallback base URL defaults to `https://api.openai.com` and uses `/v1/responses`.

## Local persistence

Default paths are under `./data`. They are runtime state and should normally be mounted on durable local
storage. The ZIP ships no production trade database and no secrets.
