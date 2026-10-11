# Optional sell-only quote freshness, 2026-10-11

The paper exit path may explicitly configure `exit_quote_max_age_seconds` as an
integer from 1 through 30. When absent or null, its effective bound is the existing
entry bound. `quote_max_age_seconds` still has its code ceiling of 3 seconds;
entry pricing, held-position admission marks and mark-to-market keep that bound.
The future-quote tolerance remains 0.25 seconds for both sides.

This adopts the CC's 2026-10-11 measured-pull decision for the Monday paper path.
The existing deterministic ledger, mover and official paper transport retain
ownership, quantity, notional, session, halt, request-budget and replay checks.
No entry, account, credential, broker execution or data-acquisition authority is
expanded by this PR.

## Measured basis for the ceiling

The released diagnostic aggregates cover ten sessions and a fixed 37-name union,
with a separate view using each day's recorded candidates. They are not an
original point-in-time universe or evidence of paper execution/fills.

| Aggregate | SHA-256 |
| --- | --- |
| minute-aggregates.csv | b7223642951bda11cbfe725e9ee69a4e6b1ef8477fd42e951b1db7093b9a96b1 |
| pooled-minute-aggregates.csv | c093f0ec70eee8fd527fce2e05f78669b67a4b61bcd0e482992cbf771d99b016 |
| recorded-date-minute-aggregates.csv | 31ffe1595ae4c2ee38227d111ecd406ed0f0816eb6d0af10519e25dc75c94ead |
| pull-summary.json | f43fda7829f1ac47392f5bc922f785806404b09a083fe8d5b353ee88b3ee5b68 |

The local aggregate input manifest is
`8812730b70e8bb1f82ff5a4b08409bd36275f1491fa540ac800f0fee15eb3b50`.
Only these aggregates were read; raw pages remain private.

Between 04:00 and 07:00 ET, 58,253 of 66,234 known fixed-union candidate-minutes
had a latest quote older than 3 seconds (87.9503%). For recorded-date candidates,
the count is 4,526 of 7,740 (58.4755%). Unknown first quotes are counted separately,
not treated as fresh or stale.

At the pooled 04:00 interval, spread <=100 bps admits 39/370 candidate-minutes
at age <=3 seconds, 55/370 at <=10 seconds, and 59/370 at <=30 seconds. Thirty
seconds is the largest age threshold measured in this pull. It therefore sets
the optional code ceiling; the extra four qualifying minutes relative to 10
seconds are an aggregate admission observation, not a fill-quality claim.
No threshold above 30 seconds was measured or authorized.

`tests/fixtures/adaptive_paper_exit_quote_age/aggregate-selection.json` retains
the input hashes, counts and three recorded-date minute medians used as synthetic
age controls. Their prices, holdings and order state are synthetic. They do not
reconstruct original vendor quote rows or associate a median age with a particular
candidate's spread.

## Implementation and compatibility

At native-agent-stack main `99e72aeff932fce30069092b1763736cb9e64c1b`, the reference
paths are:

- `blueprints/us-equities/adaptive-paper/safety.py:158-291,692-704,819-940`:
  bounded RiskLimits, frozen JSON, reservation and pre-submit revalidation.
- `blueprints/us-equities/adaptive-paper/mover.py:343-357,1154-1156,1223-1248`:
  config-to-limits derivation and the separate entry/exit pricing paths.
- `blueprints/us-equities/adaptive-paper/transport.py:1203-1235,1401-1407`:
  validated constructor and final pre-POST check, including delayed budget waits.
- `blueprints/us-equities/adaptive-paper/recovery.py:171-174`: quote freshness for
  deterministic owned-position recovery.

The sell-specific bound is propagated to the ledger and the final wire check;
a ledger-approved old quote cannot bypass the final nanosecond check after a
budget delay. Default transport kwargs omit the optional value, and
`RiskLimits.frozen_json()` omits it when absent, using the existing optional
leverage-field pattern. Existing default ledgers therefore retain identical
limit bytes. An explicit changed exit bound is frozen and intentionally refuses
reopening a ledger with different limits.

Existing example configs continue to omit the new field and keep the 3-second
default. An owning deployment can opt into 30 with
`"exit_quote_max_age_seconds": 30` in its config and a matching fresh ledger.
No deployed config or existing ledger is rewritten here.

The entry ceiling also agrees with the private trading decision
`docs/decisions/2026-10-10-paper-caps-and-leverage.md:201` at
us-equities-trading `2f953241f9a4db7a482b65c78acd24827db6e4de`.

## PRE trigger

The PR's landing is zoli's readiness trigger. If it lands before the PRE run is
ready, PRE starts at the earliest slot supported by the measured pull. Otherwise
PRE starts at 07:00 ET, the earliest slot with recorded exit evidence. A clock
time alone does not release deployment. The CC and owning deployment lane order
that operation; this PR neither deploys nor places orders.
