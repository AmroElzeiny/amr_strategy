# BEGIN AMR-DUAL-OCG-ORCHESTRATION


## Dual low-cost personal orchestration

This section governs the personal engineering workflow. It does not change product runtime behavior.

### Repository authority boundaries

This repository contains three package boundaries that must remain distinct:

1. `crypto_market_intel/crypto_market_intel`
   - public market-data and deterministic market-intelligence authority;
   - produces `MarketSnapshot`;
   - must not place, approve, size, close, reduce, or manage a trade.

2. `crypto_strategy_engine/crypto_strategy_engine`
   - strategy authority;
   - consumes `MarketSnapshot`;
   - emits `TradeIntent`;
   - `decision=ENTER` means forward to independent risk/execution, not place an order;
   - must not become an exchange/account/execution client.

3. `crypto_risk_execution_snapshot/crypto_risk_execution`
   - risk/execution boundary;
   - validates `TradeIntent`, applies sizing/locks/reservations, reconciles exchange state and may execute;
   - current repository artifact is a development snapshot, not a release-qualified execution package;
   - real trading is disabled by default and must remain unavailable to automated orchestration.

Do not silently move responsibility between these packages.

### Front-end ownership

The active front-end is either Claude Code or Codex.

For every task that may change product code/tests/docs/config examples:

1. The front-end is architect, scope owner, risk classifier and final judge.
2. OpenCode Go is the default implementation/test/review workforce.
3. The front-end MUST NOT directly implement product-file changes before delegation unless:
   - the user started Direct mode; or
   - a valid file-scoped takeover exists after OpenCode escalation.
4. The front-end may read/search, inspect history/diffs, run read-only diagnostics, create orchestration mission/contract files, and review evidence.
5. Never silently fall back to front-end implementation when OpenCode is unavailable.
6. Do not use native front-end subagents as a hidden parallel implementation workforce unless the user explicitly asks.

### Required mission workflow

Before delegation:

1. Read this file, `AGENTS.md` when present, and package-local `README.md`, `ARCHITECTURE.md`, `CONTRACT.md`, `ENVIRONMENT.md`, relevant tests and build/status documents.
2. For risk/execution work, also read `SNAPSHOT_STATUS.md`.
3. Refresh OpenCode model knowledge if the snapshot is missing or older than 24 hours.
4. Read:
   - `.amr-orchestrator/policy/ROUTING_POLICY.md`
   - `.amr-orchestrator/policy/BUDGET_POLICY.md`
   - `.amr-orchestrator/policy/REPO_AUTHORITY.md`
   - `.amr-orchestrator/policy/EXCHANGE_SAFETY.md`
   - `.amr-orchestrator/models/ROLE_MODEL_MAP.md`
   - `.amr-orchestrator/models/LIVE_MODELS.md` when present
5. Create `.amr-orchestrator/current/MISSION.md`.
6. Use 1-6 outcome-based work packages. The OpenCode supervisor owns microtask decomposition.
7. Give every user requirement a stable requirement ID.
8. State package authority, forbidden boundary changes, acceptance evidence, tests and escalation triggers.
9. Preserve unrelated uncommitted working-tree changes.

Delegate:

Claude:
`powershell -ExecutionPolicy Bypass -File .\tools\amr-orchestrator\delegate.ps1 -MissionFile .\.amr-orchestrator\current\MISSION.md -FrontEnd Claude -Tier Standard -ExecutionMode Offline`

Codex:
`powershell -ExecutionPolicy Bypass -File .\tools\amr-orchestrator\delegate.ps1 -MissionFile .\.amr-orchestrator\current\MISSION.md -FrontEnd Codex -Tier Standard -ExecutionMode Offline`

Use `Deep` only for material architecture/state/concurrency/execution/security risk or repeated meaningful failure.

### Model routing

Defaults:
- Standard supervisor: `opencode-go/minimax-m3`
- Deep supervisor: `opencode-go/deepseek-v4.1-flash`
- Explorer: `opencode-go/deepseek-v4.1-flash`
- Implementation: `opencode-go/qwen3.8-flash`
- Test/debug: `opencode-go/qwen3.8-flash`
- Logic review: `opencode-go/minimax-m3`
- Adversarial review: `opencode-go/deepseek-v4.1-flash`
- Vision: `opencode-go/deepseek-v4-flash-vision-exp` only when actual visual verification is needed.

Do not use an expensive model merely because a task is large, important, cross-file or high-risk.
Do not use vision for non-visual work.
Do not run an explorer pass unless runtime/ownership is materially unclear.

### Budget discipline

Standard target:
- <= 90 minutes
- <= 8 material model invocations
- <= 2 meaningful attempts with the same model/approach
- 1 independent reviewer

Deep target:
- <= 180 minutes
- <= 12 material model invocations
- <= 2 meaningful attempts per approach
- 2 reviewers only when risk actually justifies them

If the budget is likely to be exceeded, escalate instead of looping.

### Direct mode

Direct mode must be started by the user with `tools/amr-orchestrator/start-direct.ps1`.
A prompt alone never bypasses the hooks.

Direct mode unlocks product Edit/Write/apply_patch only.
It does NOT unlock:
- `CLAUDE.md` / `AGENTS.md`;
- `.claude`, `.codex`, `.opencode`;
- orchestrator policy/tools;
- `.env` or secret files;
- destructive/publishing git;
- real-money/mainnet exchange mutation.

### Exchange execution safety

Default mode is `Offline`.

Demo mutation is permitted only when:
- the user explicitly asks for Demo testing;
- the mission contains the exact line `Demo authorization: YES`;
- delegation uses `-ExecutionMode Demo`;
- the effective Bybit private REST target is Demo;
- `REAL_TRADING_ENABLED` remains false.

Do not use Testnet as a substitute for Bybit Demo.

Real-money/mainnet mutation is outside this orchestrator's allowed execution scope.

### Evidence

Delegated completion requires:
- `.amr-orchestrator/runs/<run>/SUPERVISOR_REPORT.json`
- `.amr-orchestrator/runs/<run>/SUPERVISOR_REPORT.md`
- requirement coverage
- actual model IDs
- changed files
- focused + adjacent tests
- test-integrity audit
- complete final diff audit
- independent review closure
- explicit uncertainty
- time/model-call budget summary
- exchange-action audit

The front-end independently inspects the highest-risk evidence and final diff.
It does not replay every worker transcript.

### Escalation and takeover

A supervisor needing front-end implementation must emit a valid `ESCALATION.json`.
Then the user/front-end may grant temporary file-scoped takeover.

After takeover:
1. edit only authorized files;
2. revoke takeover;
3. re-delegate verification/review;
4. do not declare completion from front-end confidence alone.


# END AMR-DUAL-OCG-ORCHESTRATION
