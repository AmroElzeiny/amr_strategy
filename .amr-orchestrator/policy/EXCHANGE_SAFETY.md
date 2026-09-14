# Exchange safety

## Offline — default

No authenticated exchange mutation.

Allowed:
- repository analysis;
- deterministic tests;
- mocked provider tests;
- public market-data calls where the package explicitly supports them;
- schema/contract validation;
- dry-run execution planning.

Forbidden:
- create/amend/cancel live orders;
- changing live leverage/margin/position mode;
- transfers/withdrawals;
- flattening real accounts;
- unlocking real account loss controls.

## Demo

Demo is allowed only with explicit user authorization.

Mission must contain:
`Demo authorization: YES`

Delegation must use:
`-ExecutionMode Demo`

Bybit Demo private REST must resolve to:
`https://api-demo.bybit.com`

Required safe state:
- `TRADING_ENV=DEMO`
- `REAL_TRADING_ENABLED=false`
- Demo keys only
- no withdrawal permission

Testnet is not a substitute for Demo.

## Real money

Automated real-money/mainnet mutation is prohibited by this orchestration layer.

The repository may contain real endpoint support for product completeness, but agents must not exercise it.

## Package-specific safety

Market-intel:
- public data only;
- never add authenticated/order authority to make a test easier.

Strategy-engine:
- AI is advisory inside the package's own architecture;
- `ENTER` remains an intent, not an order;
- never add exchange execution to the strategy layer.

Risk/execution snapshot:
- read `SNAPSHOT_STATUS.md`;
- keep real trading disabled;
- do not claim release qualification from a subset of tests;
- fail closed on unknown account/order state.

## Secrets

Never print secret values.
Never read `.env` secret values just to inspect configuration.
Key names, existence state and redacted metadata are acceptable when needed.
Never modify `.env` or credential stores from agent sessions.
