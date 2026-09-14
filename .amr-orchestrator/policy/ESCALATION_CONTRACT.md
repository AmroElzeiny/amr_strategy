# Escalation contract

A valid `ESCALATION.json` contains:

```json
{
  "run_id": "...",
  "status": "ESCALATE_TO_FRONTEND",
  "reason": "...",
  "needs_frontend_implementation": true,
  "allowed_files": ["relative/path"],
  "evidence": ["..."],
  "decision_needed": "..."
}
```

Rules:
- keep allowed files minimal;
- `.env`, secrets and orchestrator governance cannot be unlocked;
- real-money/mainnet actions cannot be unlocked;
- if a user decision is needed, do not pretend implementation is authorized.
