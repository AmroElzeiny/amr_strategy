# BUILD REPORT — DEVELOPMENT SNAPSHOT

- Build date: 2026-09-12
- Contract: HM_CRYPTO_V1
- Contract schema SHA256: `4e132d807d5fd6f198cde8cd8673794bbe8843dbe8850996a96385a9d8063b97`
- MT5 reference revision inspected: `25cca426e8c05bb2737da70a9b1730faf1eb3c12`
- Supported adapter code present: Bybit REAL/DEMO Spot + linear derivatives REST; Binance REAL Spot + USDⓈ-M REST; Binance DEMO fails closed.
- Runtime dependencies: Python standard library only.
- Real orders sent during this packaging run: **0**.
- Test status for this reconstructed downloadable snapshot: basic offline snapshot suite: **10 passed, 0 failed** on this archive; `compileall` passed; CLI `validate` passed. The previous transient work had reported a broader passing suite, but those transient files are not being misrepresented as this archive's verified result.
- Lint/type-check: not release-qualified in this snapshot.
- Restart/reconciliation/invariant suite: not fully requalified in this snapshot.
- Forbidden Testnet production-routing intent: no Testnet route is configured; source scan is included in offline tests.
- Release status: **NOT FULLY QUALIFIED** because the user explicitly requested the current work before remaining qualification was complete.
