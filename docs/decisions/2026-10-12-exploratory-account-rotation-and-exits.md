# Exploratory account continuity and exit selection

The CC's paper-plan ruling and addendum 01 release exploratory lane B wiring
while lane A's qualification state and proof path stay frozen. The first target
is mover trials from the exploratory ranked scan; this change supplies no scan,
GO, deployment, account permission or order execution. Paper acceptance is
**NOT_RUN**. Tests are synthetic CLI/ledger fixtures, not broker acceptance or
historical exit selection.

## Configuration and account state

Both runners require the explicit pair `paper_lane: "B"` and
`evidence_class: "exploratory"`. Missing labels preserve lane A's old behavior;
partial or inconsistent labels refuse. B cannot supply qualification proofs.
Writable state, output and diagnostic paths require an `exploratory` component
and may not contain `trials`, `qualification` or `evidence` components after
resolution. Existing unmarked account journals cannot be adopted as B.

Use one stable `--state-root`, such as `<state>/exploratory/account-state`, for
all deployments on the same account. Both exploratory runners use the existing
account fingerprint's `adaptive/ledger.sqlite3`; qualification mover runs keep
their existing `mover/` state. Do not give each config a new account journal.
No output receipt includes the fingerprint or these absolute paths.

Check (c) is satisfied by config-specific registrations in that SAME journal:
`exploratory_config:<effective-config-sha256>` binds the limits and
`exploratory_config_history` retains the namespace order. The effective digest
binds public config values, resolved preset values and registry digest, and the
effective RiskLimits, rather than just the config's input bytes. Raw deployment
hashes remain separately checkable: mover `check` reports `raw_config_sha256`
beside the effective `config_sha256`, and paper preflight also records it.
Recovery requires the active effective config and engine (`engine_kind`); it
never rotates. Default reopening requires exactly the stored limits; only an
explicit paper-rotation open may retain the old bounds pending reconciliation.

A completed trial must be flat and terminal. Fresh broker preflight and the
account writer lock still apply. The next trial books fee activities over the
original fee window and compares broker cash against the original baseline plus
cumulative ledger cash delta. Only then does trial admission atomically register
the new config, install its limits and persist the active trial's config digest,
engine, identity, cash baseline and fee lineage in SQLite. `trial.json` is a
recoverable projection. Every exploratory startup/recovery reads and validates
the committed active record before accepting a config, and completed/recovered
phase updates commit there before the JSON write. A failed JSON publication
cannot authorize the prior config or engine; recovery with the committed new
config repairs the projection. Unbound pre-change projections fail closed.
The standalone registration API is restricted to bootstrap before any trial;
rotation callers must use atomic admission. Empty files without tables can
bootstrap, but existing unmarked account journals still refuse adoption.
Duplicate identities, backward clocks,
unfinished/held state, unresolved orders, cash drift, changed capital, exhausted
risk budgets and latched halts refuse. A refusal cannot publish new limits or
clear the old trial. Fills, fee identities, cash deltas, risk history and request
budgets are never reset. STOP is checked before new B startup and under its
account lock, and is never written or cleared by this change.

## Selectable exits and ceilings

`exploratory_exit_preset` selects `{ "version": "paper-exits-v1-20261012",
"name": "X3" }` on a mover config. The versioned registry supplies X1, X2, X3,
X4 and their existing chain, using the engine's existing constants. Session,
flattening-window and range validation still run; an X1/chain preset is refused
when its close exit cannot actually occur in that trial. These are selectable
candidate mechanics, not a historically selected optimum.

The generic runner also resolves baseline, volatility and time-decay candidates
using the pre-existing tested exit fields. Partial take-profit is unregistered:
the existing stateless half-fraction mechanics sell 2, 1 and 1 shares from a
four-share position on successive profitable ticks. A one-shot partial preset
needs a persisted consumed-state design and repeat/restart tests before its
registration. Volatility and time-decay use the exact
numeric fixture parameters cited below; deterministic code selects every value.
The registry's full effective parameters and digest appear in B receipts. T22's
family-specific ATR/preset definitions remain with its dispatch owner.

Check (d) stays fail-closed: all RiskLimits ceilings are unchanged. Selecting a
registered candidate does not widen them. A config whose account loss or other
limit exceeds a code ceiling still refuses; a future wider ceiling needs its
own registered version and review. Unknown preset/version names and lane-A
selection refuse. Stops stay client-side exit decisions followed by the existing
marketable LIMIT/DAY path; no broker stop, market or multi-leg order is added.

## Sources at the pins

- NAS main `d8f7e2051b61bde6361a85b64f41413798015353`:
  `runner.py:2520` config-hash barrier; `safety.py:476-481` frozen limits;
  `safety.py:631-638` same-journal trial transition; `mover_runner.py:730-812`
  separate mover journal and fee/cash checks; `exits.py` existing rule chain.
- The same pin's `config.json:30-34`, `mover.py:77-81` and
  `tests/test_adaptive_paper_exits.py:147-161,234-250` supply the retained
  deterministic numeric candidates. No empirical fit was inferred from them.
- Official `alpacahq/alpaca-py` v0.44.0 at
  `cc4cb3b7ba50ae250e621983c2779047fb16bb28`,
  `alpaca/trading/requests.py:509-547`: LimitOrderRequest, explicit time-in-force
  and LIMIT type. Existing paper-only endpoint/stock boundary remains upstream
  request construction plus the engine's preflight/transport gate.
- Official `nautechsystems/nautilus_trader` v2.0.0rc5 at
  `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`,
  `crates/common/src/factories/order.rs`: existing native limit factory and
  time-in-force inputs. No adapter is rebuilt or replaced.

The old ledger and config mismatch remain the default. Returning to lane A
requires its own untouched root/journal; changing B labels cannot reopen an A
journal. A changed landscape or a reproduced continuity failure reopens this
decision through a cited regression, not through silent state replacement.

## Follow-ups

- Registered wider stop/risk ceilings, if a future exploratory plan needs them,
  require a separate version; none is granted here.
- Historical comparison and empirical preset selection remain with their
  owning studies; exploratory results are not qualification evidence.
- Relative, privacy-safe live diagnostics need a supported manifest reader;
  the first exploratory caller does not require them.
- A partial take-profit candidate requires persisted consumed state before
  registration; the removed half-fraction selector is refused explicitly.
- Historical bare locators in the strategy/native-fault READMEs need source
  pins in their own update; inherited manifest hostname labels are separate
  hygiene (18 matching lines), never an identity printed here.
