# Build Report

Generated 2026-09-14 on Python 3.11.0 for the `HM_CRYPTO_V1` four-package runtime.

## Package identities

| Package | Version | Schema SHA-256 | Source build SHA-256 |
|---|---:|---|---|
| crypto-market-intel | 1.0.0 | `dbdcf779916a02cfac97698979f1201ee463d3de38e9bb27139895fe5b47945f` | `125d4f6153743204264d204822eab588f70277468e33f9a578a0b9a13901d2fd` |
| crypto-strategy-engine | 1.0.0 | `408b13714bd831ad2527801ef435d38681551e3b3ffee5eb7b1c96be579935e1` | `2abe0f63976507502472c6c00417b50f4ba67805c11f7f9d6d04d66fc030ef7f` |
| crypto-risk-execution | 0.3.0.dev0 | `7dc9bf3c2753d77c08345d8d5121b4ea864b42109373c070e0214771e051d92b` | `07ffa664c4189ffdcb3c783ff0f1160611bb14c2276fd684a60d32086e7cf28a` |
| crypto-trading-orchestrator | 1.0.0 | HM_CRYPTO_V1 aggregate | `efd45ef2f81c24a455aaf84b4a499cd8d469a9233da34306071cb77bcaacd285` |

The default master config hash is
`ce65d53566ee4154f2e793054f51b51f111f518f22792576ea9648b9005d627c`.

## Verification results

| Check | Result |
|---|---|
| Package 1 tests | 27 passed, 1 optional live smoke skipped |
| Package 2 tests | 65 passed |
| Package 3 tests | 11 passed |
| Package 4 unit/integration/E2E/static tests | 37 passed |
| Total | 140 passed, 1 skipped, 0 failed |
| Ruff lint | passed |
| Ruff format check | passed |
| MyPy strict, Package 4 source | passed, 27 source files |
| Four wheel builds | passed |
| Clean four-wheel install | passed |
| Installed-package `doctor` | passed |
| Contract compatibility against real local packages | passed |
| Real Package 1 snapshot → Package 2 | passed |
| Real Package 2 ENTER → Package 3 validation | passed |
| Real Package 2 → Package 3 offline dry-run | passed, zero orders |
| Scanner → breakout → continuation → Package 3 dry-run | passed, zero orders |
| Restart/idempotency | passed |
| Feedback/quarantine | passed |
| Walk-forward delegation/no-lookahead package regressions | passed |
| Static authority/exchange/AI/Testnet audits | passed |

The final orchestrator wheel SHA-256 is
`71c1215d6c8685f109e4a0d9f3dc6c0af024feca40cb139294da19ebcc2097bd`; hashes for all four wheels
are in `INTEGRATION_MANIFEST.json`.

The real integration harness used Package 1/2/3 APIs and a deterministic offline exchange account.
No network, private exchange mutation, Demo order, real order, or live AI request was used. Bybit
Demo smoke remains opt-in and was not run because credentials/explicit order authorization were not
provided.

## Authorized compatibility changes

The original Prompt 4 immutability rule was explicitly overridden by the user. The original ZIPs
were not modified and their hashes are retained in `INTEGRATION_MANIFEST.json`, but the extracted
Package 2 and Package 3 sources were deliberately updated:

- Package 2 now accepts Package 1's list-shaped `levels` and nullable optional evidence, then
  normalizes only that producer variant inside strategy authority. Native Package 2 evidence is
  unchanged.
- Package 3 now accepts zero-based strategy attempts and reads `entry_reference` /
  `trigger_price_if_any` without mutating the intent.
- Package 3's invalid `0.3.0-snapshot` packaging version became PEP-440-valid `0.3.0.dev0`, and its
  contract schema is included in the wheel.

`PACKAGE_BASELINE.json` freezes the final authorized Package 1–3 source/schema identities and is
checked by the test suite to catch later unreviewed changes.

## Limitations and qualification

Package 3 is still a development snapshot and its public position-manager entry point explicitly
describes limited operator/orchestrator-driven behavior. This artifact is release-qualified for
deterministic offline orchestration, dry-run planning, compatibility, recovery, and guard behavior;
it is not qualification for unattended real-money execution. Real mode remains double-gated and
was not mutated or smoke-tested.
