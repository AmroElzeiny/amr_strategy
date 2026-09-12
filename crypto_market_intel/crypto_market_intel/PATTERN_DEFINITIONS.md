# Deterministic pattern definitions

All bars below are chronological. For bar `i`, use `O_i,H_i,L_i,C_i`; all comparisons use `Decimal` prices.

## Swing structure

With neighborhood `w`, bar `i` is a swing high when `H_i > max(H_{i-w..i-1})` and `H_i >= max(H_{i+1..i+w})`; swing low is the inverse using lows. A major swing repeats that test on a wider neighborhood (`3w`). Consecutive highs become HH/LH; consecutive lows become HL/LL. BOS occurs when a later close crosses the latest confirmed swing in the prevailing direction; the first opposite structural break after a known direction is CHOCH. Therefore a lone candle is never sufficient to define structure.

## Fair Value Gap (FVG)

For three chronological bars `(i-1,i,i+1)`, bullish FVG exists when `H_{i-1} < L_{i+1}` and gap width `L_{i+1}-H_{i-1}` is at least configured `ICT_FVG_MIN_GAP_TICKS * tick_size`. Its zone is `[H_{i-1},L_{i+1}]`. Bearish FVG exists when `L_{i-1} > H_{i+1}`, zone `[H_{i+1},L_{i-1}]`. The middle bar is the displacement candidate. A later penetration through the 50% midpoint marks mitigation; a close through the far edge invalidates the zone.

## Candle imbalance

For bar `i`, `body_fraction = |C_i-O_i|/(H_i-L_i)`. A candle imbalance is emitted when `body_fraction >= ICT_IMBALANCE_BODY_FRACTION_MIN`; direction follows `sign(C_i-O_i)`. This is a value-location diagnostic and is not itself a trade signal.

## Order block

For candidate displacement bar `i`, compute the median range of the prior configured lookback. The bar must have range at least `ICT_ORDER_BLOCK_DISPLACEMENT_MULTIPLE * median_range` and close beyond the maximum prior high (bullish) or minimum prior low (bearish). The zone is the real body `[min(O,C),max(O,C)]` of the most recent opposite-colour candle within the preceding four bars. A later overlap marks mitigation; a later close through that source candle's opposite extreme invalidates it.

## Breaker / reclaim zone

A breaker/reclaim zone is emitted only from an order-block zone already deterministically invalidated. The same price interval is retained and direction is inverted. The label describes a failed/reclaimed location; it is not evidence of participant identity.

## Fibonacci and equilibrium

For impulse origin `A` and end `B`, `D=B-A`. Retracement `r` is `B-rD` for `r in {0.382,0.5,0.618,0.705}`. Extension `e` is `A+eD` for `e in {1.272,1.618}`. Equilibrium is `(A+B)/2`. Ratios are mathematical definitions, not learned thresholds.

## Impulse origin and breakout origin

Within the supplied analysis bars, the deterministic impulse candidate is the bar with maximum `H_i-L_i`; its open is `origin` and close is `end`. In Package 1 the initial `breakout_origin` field deliberately aliases this objectively detected impulse origin. A strategy package may later apply stricter setup-specific qualification without changing Package 1's historical observation.

## Retest zone

Retest zones are the non-invalidated FVG and order-block intervals. Retest state is established by later bar overlap with the interval; the package does not assume the overlap will produce continuation.

## Range, acceptance and failed break

For a rolling bar set, range high/low are extrema and midpoint is `(high+low)/2`. Two consecutive closes outside a prior range/value boundary constitute acceptance outside for the current deterministic detector. A close outside followed by a close back inside is a failed-break/return event; reclaim records the crossed boundary. These counts and thresholds are versioned/configured in code/environment and are surfaced as diagnostics, not trade permission.
