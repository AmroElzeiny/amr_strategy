# Model metadata rules

Local `opencode models opencode-go` output is the availability authority.

Never invent:
- model IDs;
- variants;
- context sizes;
- image support.

`run-model.ps1` deliberately allows only the normal cost-controlled set.

If a preferred model is absent:
1. use another available normal-set model with the required capability;
2. preserve independent reviewer family when practical;
3. record the substitution;
4. escalate if the normal set cannot prove the task.
