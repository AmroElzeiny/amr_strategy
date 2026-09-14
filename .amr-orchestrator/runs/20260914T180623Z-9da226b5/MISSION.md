# Mission — Prompt 4 integration/runtime package

Front-end: Codex
Tier: Deep
ExecutionMode: Offline

## Outcome

Build and fully verify a fourth standalone Python distribution/package named `crypto_trading_orchestrator` that coordinates the three immutable runtime-authority packages already present in this repository, without copying or changing their internal code or authority. Produce `crypto_trading_orchestrator.zip` only if every mandatory requirement and final acceptance gate is actually proved. If a semantic or public-interface mismatch cannot be solved by translation/validation/invocation inside Package 4, stop and report exactly `BUILD FAILED — PACKAGE CONTRACT INCOMPATIBILITY`, including package, interface, mismatch, and why an adapter is insufficient.

The complete user specification is authoritative and MUST be read in UTF-8 from:

`C:\Users\amroe\.codex\attachments\d02ca5c8-a397-4162-a8d9-7147b7a0c5b1\pasted-text.txt`

Do not reduce the task to this mission summary. All normative statements, examples marked as required behavior, negative constraints, acceptance scenarios, and delivery rules in that file remain in scope.

## Stable requirement IDs

- `P4-GOAL-001`: create only Package 4 and connect Market -> Intelligence -> Strategy -> Risk -> Execution -> Outcome -> Learning, plus the scanner/breakout/deep-watch loop.
- `P4-GOAL-002`: Packages 1–3 are runtime source of truth; do not rebuild, fork, patch, monkey-patch, copy, or internally alter them.
- `P4-SEC-001` through `P4-SEC-139`: correspond one-to-one to numbered sections `# 1` through `# 139` in the authoritative UTF-8 specification. Every MUST/MUST NOT, test, artifact, state, command, config key, audit, and semantic detail within a numbered section inherits that section ID. Preserve these IDs in design notes, tests, and requirement coverage.
- `P4-DEL-001` through `P4-DEL-020`: correspond one-to-one to the 20 numbered items under `# التسليم النهائي`.
- `P4-FINAL-001`: the final conditional rule under `## الشرط الأخير`, including the exact failure verdict and required mismatch explanation.
- `P4-SR-001` through `P4-SR-115`: correspond one-to-one to the 115 mandatory checklist items in section 133. The final supervisor report MUST contain an individual PASS/FAIL/UNVERIFIED disposition and evidence for every `P4-SR-*` ID. The exact checklist text in the user specification is authoritative; the compact index below is only a routing aid.

### Compact mandatory-success index

```text
P4-SR-001 package created
P4-SR-002 immutable Package 1–3 sources
P4-SR-003 before/after hashes identical
P4-SR-004 actual Package 1–3 imports/use
P4-SR-005 actual contract review
P4-SR-006 schema mismatches documented
P4-SR-007 adapters for adaptable mismatches
P4-SR-008 no business logic in adapters
P4-SR-009 no technical analysis in Package 4
P4-SR-010 no strategy scoring in Package 4
P4-SR-011 no position sizing in Package 4
P4-SR-012 no leverage calculation authority
P4-SR-013 no direct private exchange execution
P4-SR-014 no direct AI decision call
P4-SR-015 reconciliation before READY
P4-SR-016 risk health/reconciliation gates execution startup
P4-SR-017 scanner flow connected
P4-SR-018 top gainers routing
P4-SR-019 top losers routing
P4-SR-020 highest-volume routing
P4-SR-021 global breakout alerts
P4-SR-022 breakout promotion
P4-SR-023 deep-watch routing
P4-SR-024 MarketSnapshot reaches Package 2 without mutation
P4-SR-025 snapshot lineage
P4-SR-026 PRE_BREAKOUT E2E
P4-SR-027 BREAKOUT E2E
P4-SR-028 CONTINUATION E2E
P4-SR-029 REVERSAL E2E
P4-SR-030 NO_TRADE never OPEN
P4-SR-031 WATCH never OPEN
P4-SR-032 ARMED never OPEN
P4-SR-033 only ENTER forwarded
P4-SR-034 ENTER still needs Package 3 approval
P4-SR-035 final risk rejection
P4-SR-036 no size mutation after rejection
P4-SR-037 no leverage mutation
P4-SR-038 no stop mutation to evade risk
P4-SR-039 daily-loss-lock E2E
P4-SR-040 max-loss-lock E2E
P4-SR-041 risk lock in overall health
P4-SR-042 spot integration
P4-SR-043 spot OPEN short impossible E2E
P4-SR-044 derivatives integration
P4-SR-045 market/product identity validation
P4-SR-046 Demo/Real alignment
P4-SR-047 Bybit Demo routing
P4-SR-048 Bybit Real guard
P4-SR-049 no Testnet mode
P4-SR-050 Binance alignment if actually supported
P4-SR-051 Binance Demo fails closed
P4-SR-052 stale snapshot not fresh
P4-SR-053 expired intent not executed
P4-SR-054 duplicate signal at-most-once
P4-SR-055 per-symbol race control
P4-SR-056 bounded backpressure
P4-SR-057 safe snapshot coalescing
P4-SR-058 execution events never dropped
P4-SR-059 package failure isolation
P4-SR-060 strategy crash blocks new entries
P4-SR-061 market crash blocks new entries
P4-SR-062 unhealthy risk blocks new entries
P4-SR-063 Package 3 position management remains available
P4-SR-064 graceful shutdown
P4-SR-065 crash recovery tested
P4-SR-066 restart with open position
P4-SR-067 no duplicate after restart
P4-SR-068 ExecutionReport -> strategy memory
P4-SR-069 duplicate report ingested once
P4-SR-070 invalid report quarantined
P4-SR-071 walk-forward orchestration
P4-SR-072 no walk-forward logic duplication
P4-SR-073 champion/challenger remains Package 2 authority
P4-SR-074 AI routing remains Package 2 authority
P4-SR-075 risk remains Package 3 authority
P4-SR-076 market intelligence remains Package 1 authority
P4-SR-077 system health model
P4-SR-078 HEALTHY
P4-SR-079 DEGRADED
P4-SR-080 BLOCK_NEW_ENTRIES
P4-SR-081 EMERGENCY
P4-SR-082 status CLI
P4-SR-083 health CLI
P4-SR-084 doctor CLI
P4-SR-085 reconcile CLI
P4-SR-086 scan-once CLI
P4-SR-087 evaluate-once CLI
P4-SR-088 walkforward CLI
P4-SR-089 dry-run E2E zero orders
P4-SR-090 disabled execution zero orders
P4-SR-091 real double guard
P4-SR-092 no Package 4 secret read/log
P4-SR-093 package versions pinned/reported
P4-SR-094 integration manifest
P4-SR-095 end-to-end lineage
P4-SR-096 scanner/breakout/continuation/execution test
P4-SR-097 false-breakout promotion/demotion
P4-SR-098 immutable hashes
P4-SR-099 no-business-logic audit
P4-SR-100 no-direct-exchange-call audit
P4-SR-101 no-direct-AI-call audit
P4-SR-102 no-Testnet audit
P4-SR-103 all unit tests
P4-SR-104 all integration tests
P4-SR-105 all E2E fixtures
P4-SR-106 restart tests
P4-SR-107 feedback tests
P4-SR-108 walk-forward integration tests
P4-SR-109 lint green
P4-SR-110 type checking green
P4-SR-111 complete README
P4-SR-112 complete ENVIRONMENT.md
P4-SR-113 factual BUILD_REPORT
P4-SR-114 no mandatory TODO
P4-SR-115 verified final ZIP
```

## Package authority and immutable inputs

Affected product scope:

- allowed: new `crypto_trading_orchestrator/**` only;
- allowed on verified success: root artifact `crypto_trading_orchestrator.zip`;
- run evidence under the wrapper-owned `.amr-orchestrator/runs/<run>/**`;
- forbidden: every file under `crypto_market_intel/**`, `crypto_strategy_engine/**`, and `crypto_risk_execution_snapshot/**`;
- forbidden: modification/replacement of `crypto_market_intel.zip`, `crypto_strategy_engine.zip`, or `crypto_risk_execution_snapshot.zip`;
- forbidden: `.env`, secrets, credentials, governance files, destructive/publishing git, or any authenticated exchange mutation.

Authorities:

- Package 1 `crypto_market_intel/crypto_market_intel`: public market data and deterministic market intelligence; produces `MarketSnapshot`; no trade authority.
- Package 2 `crypto_strategy_engine/crypto_strategy_engine`: strategy authority; consumes snapshot and emits `TradeIntent`; `ENTER` means forward only.
- Package 3 `crypto_risk_execution_snapshot/crypto_risk_execution`: financial risk/execution/position-safety authority; development snapshot, not release-qualified; real trading remains disabled.
- Package 4: translation, validation, invocation, routing, scheduling, lifecycle, state, health, feedback, reconciliation coordination, and observability only.

Never hide unsupported Package 3 behavior behind orchestrator-owned execution/position logic. `SNAPSHOT_STATUS.md` is a mandatory source and its unqualified areas must remain explicit.

## Front-end reconnaissance supplied to the supervisor

Observed package identities:

| Authority | Distribution | Version | Contract | Recorded schema SHA-256 |
|---|---|---:|---|---|
| Market | `crypto-market-intel` | `1.0.0` | `HM_CRYPTO_V1` | `dbdcf779916a02cfac97698979f1201ee463d3de38e9bb27139895fe5b47945f` |
| Strategy | `crypto-strategy-engine` | `1.0.0` | `HM_CRYPTO_V1` | `d8e275f847c12dffea7313d67ea61ba59df59b434952ba3faa0ef310391f9cd7` |
| Risk/execution | `crypto-risk-execution` | `0.3.0-snapshot` | `HM_CRYPTO_V1` | `4e132d807d5fd6f198cde8cd8673794bbe8843dbe8850996a96385a9d8063b97` |

Baseline immutable-source tree hashes use SHA-256 over canonical JSON rows of sorted relative path, file SHA-256, and size, excluding cache directories:

```text
crypto_market_intel/crypto_market_intel/src = cf87aaea29008ba69cdff18634bf356e4ac632eb73608d02ff0c23b0c3d584b8 (22 files)
crypto_strategy_engine/crypto_strategy_engine/src = 9c7fdcbb95063bbfacba9774a86d049ff1ede07bf919a5ffe2ea26a9fb41457b (59 files)
crypto_risk_execution_snapshot/crypto_risk_execution/src = 8803be863f20be53ec05fc5bd010154c38969b748a2bba3ff204497dce2eaeaf (31 files)
```

Input ZIP SHA-256:

```text
crypto_market_intel.zip = de0aa98428f9332038736aa746cb5df23337cb09eaea224996e5360d975acdeb
crypto_strategy_engine.zip = fd76d9f0220e40334f8edd6d49f49187de32a87a51e3c8ad90d63044dd5fdc36
crypto_risk_execution_snapshot.zip = f87bd065c52de2771df1ff58e91f8598224680b30ce35b9161c3d9298cfb8fe0
```

Initial compatibility observations requiring independent semantic proof:

- all raw schema hashes differ and schema document structures/names differ;
- Package 1 models `MarketSnapshot.levels` as an array and allows `breakout_alert`/spot `derivatives` to be null; Package 2 runtime validation requires `levels`, `breakout_alert`, and `derivatives` to be mappings;
- Package 2 requires canonical decimal strings on selected paths while Package 1's Pydantic JSON output normally serializes `Decimal` safely; verify every transported path and never round-trip through float;
- Package 2 emits a superset `TradeIntent`; Package 3 validates a smaller required subset plus Package 2's whole-payload canonical integrity hash. Verify real output acceptance, attempt numbering, TTL, timestamp, identity, and mutation detection;
- Package 3 exposes `validate_trade_intent`, `risk_assess`, `execute_trade_intent`, `reconcile_account`, `manage_open_positions`, `emergency_flatten`, and `apply_management_directive`, but its snapshot status explicitly lists incomplete/unqualified private-event, protection, fill-race, recovery, and management areas. Determine whether Package 4 can coordinate the requested lifecycle using public interfaces without implementing Package 3 business logic. If not, invoke `P4-FINAL-001`.

Required package sources already identified but MUST be rechecked against runtime code, not assumed from prompts: package-local `README.md`, `ARCHITECTURE.md`, `CONTRACT.md`, `ENVIRONMENT.md`, build/status docs, `pyproject.toml`, schemas, public `__init__`/CLI/API/config modules, and relevant tests/fixtures.

## Work packages

### WP1 — Reconnaissance, semantic contract verdict, immutable baseline

Objective: produce factual `INTEGRATION_RECONNAISSANCE.md` and `CONTRACT_COMPATIBILITY_REPORT.md`; discover/import the actual local packages; document name/version/build/schema hashes, APIs, CLIs, environment, dependencies, entry points, modes, and limitations; perform semantic diff across `MarketSnapshot`, `TradeIntent`, and `ExecutionReport` including type/enums/nullability/Decimal/timestamp/required/identity/meaning; classify each mismatch `EXACT_MATCH`, `COMPATIBLE_VARIANT`, `ADAPTER_REQUIRED`, or `INCOMPATIBLE`.

Allowed scope: Package 4 docs/tests/tools only. Read-only inspection of Packages 1–3.

Acceptance evidence: real-package import/contract tests without network; immutable source/ZIP baseline captured; explicit adapter mapping for every adaptable difference; exact failure verdict if any mismatch is not a transport-only adaptation.

Escalation triggers: any need to change Package 1–3; ambiguous meaning requiring invented trading logic; missing execution/feedback/recovery interface that cannot be bridged by invocation/translation alone.

### WP2 — Package skeleton, discovery/config/compatibility/adapters and safety guards

Objective: create the standalone installable Package 4 structure and all required docs/manifests/config. Implement strict package discovery/pinning, config precedence/alignment, canonical instrument/symbol mapping, immutable envelopes/hashes, and three thin adapters that only validate, translate, and invoke. Default to Demo + dry run + orchestrator execution disabled, while this delegated run remains Offline. Research mode has zero execution authority. No Testnet, hybrid-exchange, secret access/logging, direct exchange transport, or direct AI transport.

Acceptance evidence: clean-install imports of all four distributions; missing/version/schema/method/exception adapter tests; no mutation of incoming snapshot/intent; static authority audits.

### WP3 — Evented lifecycle, concurrency, persistence, health, recovery, observability, CLI

Objective: implement the required state machines, startup/reconciliation gate, typed local priority event bus, bounded/coalescing market queues with non-droppable critical events, per-symbol serialization, symbol watch lifecycle, idempotency, Package 4 SQLite correlation state, runtime session/lineage/audit indexes, workers, failure isolation, health states, shutdown/restart coordination, metrics/latencies, local status API, and all required CLI commands. Package 3 remains sole risk/reservation/execution/position authority.

Acceptance evidence: deterministic unit/concurrency/backpressure/shutdown/restart/crash tests; no giant blocking loop; no AI blocking safety events; actual `doctor` output; no direct private calls.

### WP4 — Scanner/strategy/risk/feedback/walk-forward integration

Objective: connect Package 1 scanner/ranking/breakout/deep-watch APIs to Package 2 evaluation for all four patterns, route only fresh `ENTER` intents to Package 3 after non-financial checks, accept risk rejection as final, correlate execution lifecycle, integrity-gate/quarantine/once-only feedback, and coordinate Package 2 walk-forward in a separate worker/process without duplicating optimizer or champion/challenger authority. Post-entry strategy directives may be routed only if Package 2 exposes a real public API; otherwise document the limitation and rely only on Package 3 public deterministic management.

Acceptance evidence: actual-package offline integration where interfaces exist; fixture/mocked provider tests for lifecycle states; no orchestrator-owned scoring/sizing/stops/leverage/outcome analysis.

### WP5 — Full acceptance suite and static audits

Objective: implement and run every test/audit required by sections 81–103, 109–121, 128–130, and 132–138, including all named E2E fixtures, all four patterns, happy/negative/risk override/integrity tests, restart/crash/feedback/walk-forward/no-lookahead, dry-run/disabled/real-guard/Demo routing configuration tests, package failure/backpressure/concurrency, and Package 1–3 immutability. Demo behavior must be fully mocked/configuration-only in this Offline mission; do not perform Demo account mutation or orders.

Acceptance evidence: command, exit code, counts, and focused proof for each test class; test-integrity audit proving assertions are meaningful and do not bypass real package public APIs where actual-package compatibility is claimed.

### WP6 — Clean install, factual reports, final diff audit, conditional ZIP

Objective: verify installation of all four packages in a fresh temporary virtual environment outside Packages 1–3; run pytest, Ruff, Mypy or Pyright, doctor, full fixture E2E, restart, feedback, walk-forward, authority audits, and before/after immutable hashes. Finish all requested docs/manifests and factual `BUILD_REPORT.md`. Create root `crypto_trading_orchestrator.zip` only after every `P4-SR-*` item is PASS and the archive contents/hashes are verified. Run an independent logic review and an adversarial boundary/safety review.

Acceptance evidence: required supervisor reports; complete requirement matrix; final diff limited to allowed product scope; final ZIP SHA-256 and archive listing; no mandatory TODO; explicit limitations/uncertainty. If any mandatory requirement remains failed or unverified, do not claim success and do not publish a misleading success ZIP.

## Required runtime states and non-negotiable safety

- Startup: `BOOT -> CONFIG_VALIDATE -> PACKAGE_DISCOVERY -> CONTRACT_VALIDATE -> EXCHANGE_MODE_VALIDATE -> RISK_EXECUTION_RECONCILE -> MARKET_DATA_START -> SCANNER_START -> READY -> RUNNING`; safety-critical failure becomes `DEGRADED` or `BLOCKED`, never silent continuation.
- Overall health: `HEALTHY`, `DEGRADED`, `BLOCK_NEW_ENTRIES`, `EMERGENCY`; Package 3 locks dominate new-entry health.
- Symbol lifecycle: `DISCOVERED`, `SCANNED`, `PROMOTED`, `DEEP_WATCH`, `ARMED`, `IN_TRADE`, `COOLDOWN`, `DEMOTED`; never demote an open-position symbol.
- Events and priority classes must cover every event listed in sections 34 and 72.
- `NO_TRADE`, `WATCH`, and `ARMED` never reach OPEN execution. `ENTER` is not execution. Package 3 rejection is final.
- Market/snapshot events may coalesce; execution/risk/protection events may not be dropped.
- Do not directly read or log secret values. Environment key names/redacted presence checks only when required.
- Do not access authenticated exchange endpoints. Do not send Demo or Real orders. Do not use Testnet. Do not make live AI calls. Tests must use fixtures/mocks/fakes.
- `REAL_TRADING_ENABLED` must remain false for all automation. Real-money/mainnet mutation is prohibited.
- Demo authorization: NO

## Verification expectations

- Use a clean temporary venv and ordinary package installation; no manual source copying and no editable operation that mutates immutable package roots.
- Run actual local package test suites proportionately when safe, plus Package 4 pytest/ruff/type checks. The market live smoke, Demo smoke, paid AI providers, and all private exchange actions remain off.
- Recompute the exact immutable hashes using the same canonical method at the final gate; also audit `git diff`/status for every Package 1–3 path and input ZIP.
- Static audits must detect prohibited business logic, direct exchange/AI dependencies/calls, Testnet runtime routes, secrets access/logging, mandatory TODOs, and internal patches.
- The final report must distinguish mocked lifecycle proof from real-package public-interface proof and must not call Package 3 release-qualified.

## Budget

- Deep target: 180 minutes wall clock.
- Material model invocations: <= 12.
- Meaningful repair attempts per approach: <= 2.
- Explorer only if the initial supplied authority map is invalidated by runtime evidence.
- Two independent reviewers are justified: logic/integration reviewer and adversarial execution/boundary reviewer.
- Escalate rather than loop or weaken evidence.

## Final proof

- all `P4-GOAL-*`, `P4-SEC-*`, `P4-DEL-*`, `P4-FINAL-*`, and `P4-SR-*` covered;
- exact contract/schema classification and adapter rationale;
- package-boundary and exchange-action audits;
- changed-file list and complete final diff audit;
- focused, adjacent, integration, E2E, restart, feedback, walk-forward, clean-install, lint/type, doctor, and static-audit commands with exit codes;
- test-integrity audit;
- independent review findings and closure;
- identical Package 1–3 source/ZIP hashes before and after;
- time/model-call budget summary and actual model IDs;
- explicit uncertainty and factual verdict.
