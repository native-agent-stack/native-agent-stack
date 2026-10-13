# Lumibot stock-only deterministic acceptance

Status: **acceptance: synthetic evidence only; no order placed; no designation**.

This implements the CC-accepted L0/L1/L2 design, spec SHA256
`8eb20e2e1f3c38a416a364a9f87fef62fcd5bdaa515bf60d78621cde7eff2dc3`
and governing Addendum01
`cf63eb570cc65e51c24444b6d752ad73825008a0a626e210ae061005f0544805`.
It is a trading-lane component in native-agent-stack. Nothing here changes a
gate, chooses a paper account, reads credentials, arms a runner or places a
broker order. CC designation and a flat-and-idle account rotation are separate.

## Mechanism and pinned sources

- [Lumiwealth/lumibot4.6.11](https://github.com/Lumiwealth/lumibot/tree/862504052407df2586122b752a645f88ce87afa1),
  `brokers/alpaca.py:370–452` paper config/property/SDK construction;
  `:1117–1202,:1261–1262` single payload, rounding and custom-parameter merge;
  `:1090,:1344,:1394` other SDK writes. `entities/order.py:170,:255` gives the
  SIMPLE default; `strategies/strategy.py:1924,:2618,:2659,:2687,:2739` and
  `strategies/strategy_executor.py:1050–1240` identify unsafe upper seams.
- [alpacahq/alpaca-py0.44.0](https://github.com/alpacahq/alpaca-py/tree/cc4cb3b7ba50ae250e621983c2779047fb16bb28),
  `alpaca/trading/client.py:53–105` chooses the actual URL and consumes
  `to_request_fields`; `alpaca/common/rest.py:127–135,:195–202` retry behavior.
- CPython3.12 Decimal.quantize, ROUND_FLOOR/ROUND_CEILING and integer arithmetic
  implement D4 direction/whole-share rules; json.dumps with sorted keys and
  allow_nan=False implements deterministic journal bytes. No numeric model
  output is consulted by admission.

L0 governor.py imports only stdlib. It loads/hashes the explicit caps file,
uses injected quotes/account/session/clock, sizes whole shares and directionally
rounds limits, checks FINAL notional/collar arguments, freshness and long-only
positions, then journals a one-use reservation. Refusals contain bounded codes,
never raw hints. At most2 names,200USD/name, spread50bps, ask5–200, quote60s,
trade120s. Unset/malformed caps refuse. Exit_all remains LIMIT/DAY and no short.

L1 guarded_api.py encapsulates the original SDK client in closure cells rather
than plain attributes. Only owned cancellations, approved reads and exact
decision-derived single submits are available. Every final payload key/type/
TIF/side/qty/price/session/token is checked. Lumibot's SIMPLE no-child marker
is removed, and its omitted extended_hours/client_order_id fields are injected
only for a previously bound Decision. Arbitrary custom_params remain refused.
Price string normalization preserves exact Decimal equality; native round()
is observed to be the identity on the governor's tick output.

The proxy reserves up to4 transport attempts per SDK call (default3retries),
counting against200requests/180submits per rolling minute, without sleeping,
retrying or implementing a transport throttler. It refuses a larger configured
retry ceiling. This is conservative admission accounting; vendor/engine
transport pacing remains authoritative. Restore preserves consumed budgets.

L2 stock_only_alpaca.py loads Lumibot only through load_classes after dotenv,
default broker, stream, orders thread and telemetry settings are explicitly
disabled. Construction refuses absent/falsePAPER, ambiguous paper aliases,
missing session, stale clock, or a resolved SDK URL other than the exact paper
host. It does not repair a missing PAPER setting. The real client's BaseURL
enum value is checked, rather than trusting config text. Single native orders
must be stock/limit/day/whole-long-only with no compound/SmartLimit/custom
parameters. Batch/multileg/modify/sell_all/close_position(s) seams refuse.
Replacement pricing requires cancellation plus a new closed-inbox intent.

IntentStrategy is a trusted fixed deterministic class. The closed inbox accepts
only symbol/side/sizing; no model prices or quantities. No Lumibot agent object
is created and its agents property refuses. Python reflection is not a sandbox:
closure extraction or a separately constructed client is blocked from network
access by the independent qualification process audit hook in this acceptance.
This does not establish a production isolation/designation by itself.

## Journal, outcome and restart

Journal files are0600, single-writer locked, append-only canonical JSONL with
previous-line hashes, caps hash and monotonically assigned local order keys.
Every decision/refusal and pre-SDK budget/submit/outcome is recorded; fsync is
observed before the SDK call. A response does not prove a fill/position snapshot.
Any unknown outcome or restored unresolved decision blocks admission until a
trusted operator provides reconciled terminal state. No automatic resubmit or
retry exists. Restart refuses changed caps and preserves request consumption.
Local tests use fabricated journals only; production journals remain private.

## Reproduce synthetic acceptance

Use the existing isolated runtime read-only; never install/sync into it.
The supplied interpreter was observed as3.12.4, Lumibot4.6.11, alpaca-py0.44.0.
The measured distribution projection has274entries, rather than the brief's
older265; runtime-distributions.json records the observed names/versions.
No environment mutation was performed. This metadata discrepancy was reported
to trading-cc, as was the inventory's currentcc07a7a0 digest versus its older
spec citation; source behavior was independently checked at the pin.

```sh
python3 -B blueprints/us-equities/engine-lumibot/acceptance/run_acceptance.py \
  --python <ISOLATED_RUNTIME_PYTHON> --offline-hook <ENGINE_QUAL_OFFLINE_HOOK> \
  --output <VAR_TMP_PRIVATE_RUN>
python3 -B blueprints/us-equities/engine-lumibot/acceptance/mutate_guards.py \
  --python <STDLIB_CI_PYTHON> --output <VAR_TMP_MUTATION_RESULTS>
```

run_acceptance uses an explicit nonsecret child environment and the existing
ENGINE_QUAL_OFFLINE audit hook: no socket connection or credential-path open.
A7 deliberately probes a second SDK client; its network attempt is denied.
The output directory must be outside the worktree. Raw logs/receipts remain
private; export_receipt publishes bounded result summaries and code/output
hashes rather than raw identity-bearing trace fingerprints. Every failure and
interim run is retained outside the tree.

## Observed evidence and limits

The current receipt records22L0/L1 cases and13native/stub seam cases passing
in the isolated runtime, zero skips, including500seeded model-hint invariance
cases (seed260413). The500case numerical test suppresses only repeated fsync
calls; the separate A6 durability test observes real fsync before the SDK.
Stdlib-only CI executes the three seam tests and explicitly skips10native
cases; those skips are not native acceptance. Tests are unittest-discovered,
not silently collected through pytest alone.

A8:42exact-site mutants killed,0survived,0not-applied,0invalid-runs; each child
must execute exactly one named test. Payload, reservation, paper verification,
numeric cap, rounding, journal/fsync/restart, constructor and each seam are
discriminated independently. Early sweep28found2masked survivors and1ambiguous
site; tests/site targeting were corrected without weakening expected reasons.
Initial native fixtures exposed the SIMPLE default and invalid compound/crypto
fixture construction; corrected pinned-source fixtures and final runs are
retained. No broker observation, strategy return or full-suite pass is claimed.

Production prerequisites remain: designation, account-exclusive credential-run
launch and OS/network isolation, trusted live snapshot/session provider,
permitted caps/config binding, and flat-and-idle rotation under the account's
single-writer lock. The acceptance does not authorize any of those actions.
