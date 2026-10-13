# Lane B account-sized preset A/B: staged implementation contract

Status: generator and first native output slice implemented locally; deployment,
issuer integration and broker acceptance NOT_RUN. Version: acct-sized-v1.
Base: native-agent-stack df3a477c84aafed82757d120268ac58dea1fbd30.
The CONTROL source and sealed d268be92 deployment remain immutable.

## Derivation

Use the pass-start broker account `equity` in USD, never cash, buying power,
configured trial capital or a model estimate. Official alpaca-py 0.44.0,
cc4cb3b7ba50ae250e621983c2779047fb16bb28,
`alpaca/trading/models.py:532,550` exposes `currency` and `equity`.
The repository's existing `transport.normalize_account` preserves equity for
all feed configs, independently of optional margin fields. No new provider or
paid data is needed. The production acquisition remains a documented GET-only
paper-loader operation owned by the issuer/readiness path.

The generator requires a sanitized fact with exactly these fields:

```json
{
  "schema_version": 1,
  "paper_lane": "B",
  "evidence_class": "synthetic",
  "inventory_id": "alpaca-paper",
  "pass_id": "pass-2",
  "observed_at_utc": "2026-10-13T16:15:00Z",
  "currency": "USD",
  "equity_usd": "40000",
  "flat": true,
  "positions_count": 0,
  "open_orders_count": 0
}
```

The example is SYN. A native fact uses `native_paper`, the actual observation
clock and no caller clock override. Generation requires age 0–300 seconds,
finite positive equity, the requested pass and a flat zero-order observation.
These schema checks do not authenticate a broker observation or replace the
issuer's fresh per-stage GET, account binding, writer check or reconciliation.
The generator does not make a broker call or create a GO.

Capital is `floor_to_cents(0.5 * equity)`. Each stage's factor is new capital
divided by that stage's CONTROL capital. Scale the top-level capital, gross
exposure, order notional, gross loss and drawdown fields and the mover's
`max_entry_notional_usd`, when present, by that factor; floor each to cents.
Record the factor and before/after values. Currency precision can slightly
reduce a ratio. Under CC D6/D7, clamp the scaled per-order notional to
10,000 USD and record unclamped/effective values and the binding ceiling;
do not conceal the resulting ratio change.
Unknown USD fields refuse until classified. Price offsets are prices, not
capital caps. Under D7, account-sized configs use NOTIONAL quantity mode and
the existing share ceiling: 100 with canonical leverage_policy/mover, 10 for
PolicyConfig without leverage_policy (strategies_v1.py:195-221). The latter is
a stricter existing code bound, not permission to add a leverage schedule.
Every other field, including the canonical leverage schedule, symbols,
price/spread/freshness/session/exit parameters, is kept.
CONTROL copies the exact original bytes.

The native `load_config` or `load_mover_config` validates each output before
publication. Native RiskLimits remains authoritative. In particular a capital
above 1,000,000 USD refuses; orders clamp at 10,000 USD and quantity remains
within its existing code ceiling. No generic ceiling is raised.
For a CONTROL order/capital ratio of 0.1, account equity above 200,000 USD
binds the per-order clamp. NOTIONAL sizing replaces the one-share experiment.
Per-order receipts disclose quantity/notional constraints; configurable
ceilings remain reve's D6-b follow-up.

## Packet and proposed issuer contract

`adaptive-paper/preset_sets.py` accepts `--controls DIR --stages ORDER
--pass-start-receipt FILE --pass-id ID --preset-set control-v1|acct-sized-v1
--output NEW_DIR`. It writes original CONTROL configs, selected configs,
sanitized fact, generator bytes, versioned derivation manifest and a strict
SHA256SUMS inventory. Inputs and output are retained together; no digest
commits to withheld logs or private credential/account identifiers. Generated
files become read-only. An existing destination refuses. The source git pin
and complete runtime archive must be supplied by the later deployment seal;
this configuration packet alone is not an executable deployment bundle.

`--check-packet DIR --stage STAGE --pass-id ID --preset-set VERSION
--preset-manifest-sha256 SHA --inventory-sha256 SHA` validates the frozen
selection and every inventoried byte and returns the proposed GO-binding
fields. A wrong pass, version, stage or hash refuses. This command writes
nothing and establishes no order authority.

Future `issue_go.py` and `launch.py` must bind `preset_set_version`, `pass_id`,
`preset_manifest_sha256`, `pass_start_receipt_sha256` and the selected config
alongside all existing source/session/TTL/recover/scan/account bindings. The
co-op daemon chooses one set per pass; a set never changes between its stages.
The pass-start equity remains fixed during that pass, while each trial still
requires a fresh independent flat/account readiness observation. No expired
stage readiness may be relabelled with the old pass-start timestamp.

The native adaptive output slice now measures filled gross and pending buys
for every config, even without leverage_policy. It records broker equity and
the denominator's basis separately from trial capital; missing observations
are null, never replaced with trial capital. Filled gross divided by equity
is deployed exposure, not cash utilization. The first integration test trades
through the actual native node and SimulatedPort and finishes flat. Existing
leverage-specific output remains a separate measurement. Sampling is explicitly
owner-loop tick sampling, not a claim of every transient event's maximum.

## Remaining readiness work

The account Ledger currently refuses capital transitions with
`exploratory_capital_continuity_required` in
`safety._register_exploratory_config`. Alternating current CONTROL and
account-sized capital needs a reviewed transition that preserves the original
cash baseline, immutable fills/fees, loss state, request budget and config
history. A new journal is not a workaround. Under CC D7, reve owns safety.py
and the Ledger-focused fail-first tests; his reviewed capital-transition delta
joins zoli's ONE integrated PR. Zoli owns generator/packet/helper/receipt
integration. The transition is pending and remains an activation blocker.

After #1042/#1067 land, integrate the new packet selection into a new helper
version, authenticate its fact through the existing GET-only/readiness path,
reject SYN input for native activation and carry version/pass labels through
every success/refusal/recovery receipt. Finish mover/common-output coverage.
Then pin landed source, freeze a fresh packet at pass start, seal the complete
new bundle, run the full SYN wiring and request the issuer validity binding.
The co-op changes its daemon only after these tests and seal exist.

The CC's D7 critical-path exception explicitly authorizes opening this PR
alongside #1042/#1067/#1079. No service, current deployment, STOP/HOLD or lane A
state has been changed. The initial PR is a draft while capital-transition and
complete issuer/launcher/native receipt integration are still being built.

## Tests and source basis

Focused checks run under `systemd-run --user --scope -p CPUWeight=idle --quiet
-- env TMPDIR=/var/tmp`. The public generator tests cover known equity scaling,
unchanged non-dollar settings, exact CONTROL bytes, rounding, missing/invalid
equity, stale/future/wrong-pass/non-flat facts, strict packet hashing,
wrong per-pass selection, D6 order clamping and refusal above the capital ceiling. A separate named
native integration module requires the selected managed runtime, with no
silent runtime skip or undeclared SDK requirement in standard discovery.
The generator CLI, packet check and new native output argument each failed
before their respective implementation; logs are local and have no public
digest commitment.

Selected engine: NautilusTrader 2.0.0rc5,
1b0a49d2792a9432a3aca3fcb617ce7a630d905e. Reuse
`crates/risk/src/engine/config.rs:48-63` node limits and
`crates/trading/src/strategy/mod.rs:2346-2385` native submission. Account
currency/equity semantics come from the official pinned Alpaca model above;
NAS `safety.py:201-212` supplies the existing monetary/quantity ceilings.
No replacement engine, broker adapter, rate limiter or order path is added.

Follow-ups: resolve capital-transition continuity; complete issuer/launcher
selection and refusal receipts; integrate mover summary; seal/pin full runtime;
native paper A/B acceptance with achieved exposure and independent review.
