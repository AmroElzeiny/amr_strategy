# Budget and latency policy

## Standard target
- 90 minutes wall clock
- 8 or fewer material model invocations
- 2 meaningful repair attempts per approach
- 1 independent reviewer

## Deep target
- 180 minutes wall clock
- 12 or fewer material model invocations
- 2 meaningful repair attempts per approach
- 2 reviewers only for genuinely high-risk work

## Stop conditions

Escalate instead of looping when:
- the same defect survives two meaningful attempts;
- repository/runtime authority cannot be established;
- tests and executable evidence conflict;
- a product/risk decision belongs to the user;
- required access is unavailable;
- the remaining proof would exceed the mission budget without a clear value gain.

## Context controls
- one broad authority map maximum unless new evidence invalidates it;
- no periodic progress polling by the front-end;
- no duplicate full-suite runs without a code/evidence change;
- no duplicate independent reviewers on low-risk work;
- no vision calls without visual acceptance requirements.
