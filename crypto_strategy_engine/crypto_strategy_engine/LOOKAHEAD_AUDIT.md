# No-lookahead audit

The research path enforces time ordering rather than random splits.

## Live/analogue rules

- Every `source_timestamps` value used by a snapshot must be `<= event_time_utc`.
- Historical analogue signal time must be earlier than the current candidate time.
- Historical analogue **resolved outcome time** must also be earlier than the current candidate time.
- Calibration samples use only clean outcomes resolved before the current candidate time.
- Outcome fields are never copied into the frozen live AI request or live candidate features.

## Walk-forward rules

`time_ordered_windows` produces chronological train, validation and out-of-sample test windows. The
`no_lookahead_audit` routine verifies source timestamps, outcome resolution ordering and that each
window satisfies `train < validation < test`. A violation raises before metrics/config comparison is
accepted.

The normal test suite contains explicit cases for future source timestamps and future analogue/outcome
leakage. The walk-forward summary embeds the no-lookahead audit result.
