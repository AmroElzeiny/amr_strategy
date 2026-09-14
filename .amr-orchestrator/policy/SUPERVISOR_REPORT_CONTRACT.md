# Supervisor report contract

Required run artifacts:
- `SUPERVISOR_REPORT.json`
- `SUPERVISOR_REPORT.md`

Wrapper-owned:
- `SUPERVISOR_STDOUT_RAW.txt`
- `SUPERVISOR_STDOUT.txt`

Supervisor must not write wrapper-owned transcript files.

Required report sections:
- run ID;
- front-end;
- tier;
- execution mode;
- baseline commit/branch/working tree;
- actual models used by role;
- requirement coverage;
- package-authority audit;
- work-package ledger;
- changed files;
- test commands + exit codes;
- test-integrity audit;
- contract/schema compatibility audit when relevant;
- exchange-action audit;
- independent review findings + closure;
- complete final-diff audit;
- budget/time summary;
- explicit uncertainty;
- verdict.

Allowed verdicts:
- `COMPLETE_VERIFIED`
- `COMPLETE_WITH_EXPLICIT_UNVERIFIED_ITEM`
- `ESCALATE_TO_FRONTEND`
- `BLOCKED`

Never claim risk is zero.
Never call the risk/execution snapshot release-qualified unless the relevant release criteria are actually proved.
