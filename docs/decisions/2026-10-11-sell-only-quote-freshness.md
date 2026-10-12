# Optional sell-only quote freshness, 2026-10-11

The paper exit path may explicitly configure `exit_quote_max_age_seconds` as an
integer from 1 through 30. When absent or null, its effective bound is the existing
entry bound. `quote_max_age_seconds` still has its code ceiling of 3 seconds;
Entry pricing and held-position admission marks retain that bound; the
`mark_to_market()` method also uses it.
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
- `blueprints/us-equities/adaptive-paper/transport.py:1203-1235,1401-1407`:
  validated constructor and final pre-POST check, including delayed budget waits.
- `blueprints/us-equities/adaptive-paper/recovery.py:171-174`: quote freshness for
  deterministic owned-position recovery.

The mover reference is re-anchored after the exit-chain merge to
native-agent-stack main `569bbc59db2b5f7c8a932357726efb7acca90b91`:
`blueprints/us-equities/adaptive-paper/mover.py:366-380,1201-1203,1261-1299`
contains config-to-limits derivation, the quote-freshness primitive and the
exit-chain management/pricing path. These ranges were checked against the
pinned main bytes; the PR adds its sell-specific bound on top of that source.

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

### Ordinary adaptive sell propagation correction

At this PR's first head `c90efda95b1cce6d97dce8f0a77cfbf6436502c8`, the
ordinary runner accepted the optional sell age but still constructed
`PolicyConfig` with only the entry age. Policy exit decisions, native forced
exits, the action guard and cancel-ack replacement therefore rejected bounded
older sells before reaching the ledger or transport. The correction passes
`RiskLimits.effective_exit_quote_max_age_seconds` into the policy's optional
`exit_quote_age_seconds` and shares its effective sell-age selection with those
native sell guards. Entry features/orders and held-entry admission marks retain
the entry age. The `mark_to_market()` method and gap-reference sampling also
use the entry age. The sell override
does not authorize older stop-arming or prior-close reference prices.

A sell quote within the sell age may refresh the ledger's mark when it is newer
than the stored mark. It keeps its own timestamp, so it never makes a mark fresh
for an entry, and entry admission is unchanged. It may move unrealized P&L, the
peak and drawdown, and latch a risk halt (which sets force_exit,
runner.py:1776-1778) on a quote up to the sell age old.

The CC's B1 ruling switches the armed RTH gap-risk stop trigger from the entry
age to `sell_quote_age_seconds(self.policy.config)`: **SWITCHED**. This closes
the remaining sell-decision carve-out at the preceding head
`1bb44890efaacd4c87b650e204c32282a7dec5ec`. Stop arming and prior-close capture
remain on the entry age; the future tolerance and fire-once-on-submit behavior
are unchanged. Three SYN workflow regressions first fail at that head with ten
assertion failures and zero errors. They admit armed-trigger ages 4/10/20/30
seconds with exit age 30, refuse 31 seconds, retain entry-fresh arming, and keep
absent/null defaults on 3 seconds. The arming/default assertions already pass
there; each workflow's configured bounded-sell assertion discriminates the fix.

The native interface is NautilusTrader `v2.0.0rc5`, upstream
`nautechsystems/nautilus_trader` at
`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`, inspected in its registered mirror:

- `crates/trading/src/python/strategy.rs:1901-1920,2001-2018` exposes the
  supported `submit_order` and `cancel_order` boundaries.
- `crates/trading/src/python/strategy.rs:567-574,1029-1031` dispatches the native
  cancellation event to Python `on_order_canceled`; the callback matrix at
  `:5694-5804` covers that dispatch. The local replacement checks the current
  injected clock when this acknowledgment arrives, rather than reusing the
  cancellation request's timestamp.

`tests/test_adaptive_paper_adaptive_sell_age.py` uses the real configuration
loader, deterministic policy and installed native Strategy with synthetic
order I/O. Four regression methods fail at the first head with 39 assertion
failures and zero errors: ordinary policy/native stop exits, RTH/PRE/POST forced
sells and cancel-ack replacements. They admit the retained recorded-date
minute's synthetic age and the exact configured 10/30-second ceilings, and
refuse ages just above each ceiling. Separate absent/null, entry-feature,
entry-order and held-admission controls preserve the entry bound. These are
SYN integration checks, not observed broker fills or qualification evidence.

The entry ceiling also agrees with the private trading decision
`docs/decisions/2026-10-10-paper-caps-and-leverage.md:201` at
us-equities-trading `2f953241f9a4db7a482b65c78acd24827db6e4de`.

## PRE trigger

The PR's landing is zoli's readiness trigger. If it lands before the PRE run is
ready, PRE starts at the earliest slot supported by the measured pull. Otherwise
PRE starts at 07:00 ET, the earliest slot with recorded exit evidence. A clock
time alone does not release deployment. The CC and owning deployment lane order
that operation; this PR neither deploys nor places orders.
