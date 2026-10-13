# Lane B account-sized preset A/B: staged implementation contract

Status: generator and first native output slice implemented locally; deployment,
issuer integration and broker acceptance NOT_RUN. Version: acct-sized-v1.
Initial review base: native-agent-stack df3a477c84aafed82757d120268ac58dea1fbd30.
Round 1 rebases on main 1b44ab61c5c1652762759d905d60660a6d1da8bf after
the CC-approved #1088 dependency landed. Generator: acct-sized-generator-v2.
The CONTROL source and sealed deployment remain immutable.

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
Record the factor and before/after values in the private packet. Currency
precision can slightly reduce a ratio. The initial implementation used the
D6/D7 10,000 USD clamp and unleveraged 10-share cap (100 with a canonical
leverage policy or mover). That was a capped-size comparison, not the claimed
account-sized experiment; at lev4 the order clamp bound above 50,000 USD equity.
The CC's round-1 ruling supersedes those order ceilings for this arm after
#1088 lands. Version 2 adopts its reviewed `risk_ceilings` interface.
Unknown USD fields refuse until classified. Price offsets are prices, not
capital caps. Account-sized configs use NOTIONAL quantity mode. The explicit
`risk_ceilings.max_order_notional_usd` equals the scaled CONTROL cap, without
the old 10,000 USD clamp. `risk_ceilings.max_order_quantity` and the configured
quantity cap use the landed parser's maximum whole-share bound, 1,000,000,000.
That is an envelope, not an order quantity: actual shares remain bounded by
the native notional-at-quote calculation, gross allocation, leverage and
freshness checks. No price or new broker input is invented by the generator.
`risk_ceilings.capital_usd` retains D7's 1,000,000 USD ceiling.
Every other field, including the canonical leverage schedule, symbols,
price/spread/freshness/session/exit parameters, is kept.
CONTROL copies the exact original bytes.

The native `load_config` or `load_mover_config` validates each output before
publication. Native RiskLimits remains authoritative. In particular a capital
above 1,000,000 USD refuses. Only the new arm opts into the landed per-config
order envelopes; CONTROL retains its original limits and bytes. Native tests
admit a 200-share/20,000 USD SYN intent through the actual Controller and
Ledger, demonstrating that the former share and order caps no longer truncate
this arm. Achieved deployment remains NOT_RUN; an envelope does not guarantee
that a signal places orders or reaches its gross cap.
Optional mover PRE retains its native tenfold exit-headroom and separate
entry cap: any equity where its scaled entry cap exceeds that bound still
refuses, rather than weakening exit safety. Re-evaluate applicability at seal.

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
nothing and establishes no order authority. Its stdout omits dollar equity;
`pass_start_equity_usd` remains only in the retained private packet. Packet
bytes and their private digests are operational records, never public evidence.

Future `issue_go.py` and `launch.py` must bind `preset_set_version`, `pass_id`,
`preset_manifest_sha256`, `pass_start_receipt_sha256` and the selected config
alongside all existing source/session/TTL/recover/scan/account bindings. The
co-op daemon chooses one set per pass; a set never changes between its stages.
The pass-start equity remains fixed during that pass, while each trial still
requires a fresh independent flat/account readiness observation. No expired
stage readiness may be relabelled with the old pass-start timestamp.

The native adaptive slice measures filled gross and pending buys for every
config, even without leverage_policy. `run_native` returns an INTERNAL result;
`publish_paper_output` saves it at mode 0600 beside the private account journal,
then publishes a strict allowlist of labels, counters and ratios. Dollar equity,
exposure, accounting, fill price/quantity, preflight, financing and full sizing
diagnostics never enter the public paper-output.json. The public receipt retains
per-order binding-ceiling names. The exporter rejects a journal inside this
repository, and a private write failure prevents public publication. The private
sidecar must never be committed or copied to a publication packet.
Missing equity is null, never replaced with capital or cash. An unbound arm
label is null, never implicitly CONTROL. Until authenticated helper wiring
exists, main supplies no arm label. Filled gross/equity is deployed exposure,
not cash utilization. Sampling is owner-loop ticks; transient maxima are not
claimed. Native SYN integration finishes flat and verifies both artifacts.

## Remaining readiness work

The account Ledger currently refuses capital transitions with
`exploratory_capital_continuity_required` in
`safety._register_exploratory_config`. Alternating current CONTROL and
account-sized capital needs a reviewed transition that preserves the original
cash baseline, immutable fills/fees, loss state, request budget and config
history. The chosen design is recorded per-arm re-basing in the SAME account
journal, not a new ledger. Versioned transition events must retain immutable
lifetime cash/fee/fill/request/loss totals and persistent per-arm loss/drawdown
attribution. Repeated switches cannot reset either arm's prior consumption.
Reve owns safety.py and the transition API/tests; zoli owns packet/receipt and
later helper integration. This record chooses the design; it does not implement
or authorize a reset. The packet explicitly marks `per-arm-rebasing-v1` as
NOT_IMPLEMENTED and activation REFUSED.

The reproduced one-way case realizes 40 USD loss in a larger arm with 100 USD
loss/drawdown limits, finishes flat, then attempts CONTROL with 25 USD limits.
Current Ledger refuses `next_trial_risk_budget_exhausted` and preserves its
accounting and config history. Changing capital additionally refuses
`exploratory_capital_continuity_required`. Merely raising the capital-change
check would not fix this. Before activation, the reviewed transition must
demonstrate CONTROL -> account-sized -> CONTROL, loss between arm caps, repeat
switches, crash/replay and unchanged global risk enforcement.

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
wrong per-pass selection, landed D6-b envelope adoption and refusal above the capital ceiling. A separate named
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
NAS #1088 head b859c0f54de9a1ec62272715bb60188f729010c2,
`safety.py:risk_ceiling_kwargs`, `RiskLimits.__post_init__`,
`RiskLimits.order_qty_cap` and `strategies_v1.py:PolicyConfig.__post_init__`
supply the explicit envelope and unchanged native notional admission.
No replacement engine, broker adapter, rate limiter or order path is added.

Follow-ups: resolve capital-transition continuity; complete issuer/launcher
selection and refusal receipts; integrate mover summary; seal/pin full runtime;
native paper A/B acceptance with achieved exposure and independent review;
test authenticated pass-start denominator binding at the helper boundary;
expand remaining refusal tests/mutation coverage without claiming exhaustive
guard coverage; classify already-present risk_ceilings in future CONTROL sets
(current inputs without them are supported); update inherited CONTROL notes in
derived configs before deployment; re-pin stale historical runner locators in
their owning record; preserve historical hostname evidence under its policy.
