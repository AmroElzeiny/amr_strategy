# Routing policy

## Principle

Use the cheapest normal model with the capability to finish correctly.
Use the live local OpenCode Go catalog as availability authority.

## Standard

Supervisor:
`opencode-go/minimax-m3`

Use for:
- normal implementation;
- localized bugs;
- routine multi-file work;
- tests;
- docs coupled to code;
- read-only audits;
- bounded refactors.

Preferred path:

```text
Supervisor
-> one worker
-> focused tests
-> one logic reviewer
-> done
```

Do not automatically invoke explorer, dedicated test worker, adversarial reviewer or vision.

## Deep

Supervisor:
`opencode-go/deepseek-v4.1-flash`

Use for:
- cross-package contract changes;
- strategy/risk authority changes;
- order lifecycle;
- loss locks;
- persistent state;
- retry/idempotency;
- concurrency/race conditions;
- crash recovery;
- security/secrets;
- repeated meaningful Standard failure.

Deep means more reasoning, not a longer default chain.

## Roles

- Explorer: DeepSeek V4.1 Flash
- Fast worker: Qwen3.8 Flash
- Strong-role worker: Qwen3.8 Flash
- Test/debug: Qwen3.8 Flash
- Logic reviewer: MiniMax M3
- Adversarial reviewer: DeepSeek V4.1 Flash
- Vision: DeepSeek V4 Flash Vision Exp only when actual media is part of acceptance

## Expensive-model rule

Do not automatically route to:
- Kimi K2.7 Code
- DeepSeek V4 Pro
- Qwen Max
- GLM full
- any other higher-cost model outside the normal set

After two meaningful failures:
1. change approach or normal model family;
2. if still unproved, escalate to the front-end;
3. do not burn allowance to avoid escalation.

## Explorer rule

Invoke explorer only when ownership/call-path/runtime authority is materially unclear.

Reuse an authority map already produced in the same mission.

## Review

Normal:
- one independent logic reviewer.

High risk:
- logic reviewer + adversarial reviewer.

Visual:
- vision reviewer only when visual evidence exists.

## Context

Pass the smallest relevant context:
- exact files;
- symbols;
- contracts;
- failing tests;
- compact prior findings.

Do not attach full transcripts to every worker.
Do not remap the entire repo on every work package.
