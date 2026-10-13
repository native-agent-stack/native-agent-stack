# Lumibot stock-only deterministic acceptance

Status: **acceptance: synthetic evidence only; no order placed; no designation**.

This implements the CC-accepted L0/L1/L2 design, spec SHA256
`8eb20e2e1f3c38a416a364a9f87fef62fcd5bdaa515bf60d78621cde7eff2dc3`
and governing Addendum01
`cf63eb570cc65e51c24444b6d752ad73825008a0a626e210ae061005f0544805`.
The CC's exit-policy ruling, carried in the pre-push read Addendum01, is
`6e2cb83ef947e05b0d640d344b92e8a093acc2b4cb0ca854efa94f1ed29fc582`.
The round-2 read carries the CC's 12:30Z quote-age, quantity and restart rulings,
sha256 `cfe28395347bc7d69b993b7db35f4e9b1abcc6d18c93863d543b8d4171d437ea`.
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
  `brokers/broker.py:511` retains `_config`; `strategies/_strategy.py:339,992`
  installs a lazy component during real construction; the executor's
  `:100–106,1379–1390` binds named initialize parameters.
  `_strategy.py:418–426,1010–1014` applies environment parameter overrides;
  `:766,783,3981` consumes webhook/cloud/listener settings. The corresponding
  `credentials.py:217–242,278,606` loads the five refused environment variables.
- [alpacahq/alpaca-py0.44.0](https://github.com/alpacahq/alpaca-py/tree/cc4cb3b7ba50ae250e621983c2779047fb16bb28),
  `alpaca/trading/client.py:53–105` chooses the actual URL and consumes
  `to_request_fields`; `alpaca/common/rest.py:127–135,:195–202` retry behavior.
- CPython3.12 Decimal.quantize, ROUND_FLOOR/ROUND_CEILING and integer arithmetic
  implement D4 direction/whole-share rules; json.dumps with sorted keys and
  allow_nan=False implements deterministic journal bytes. No numeric model
  output is consulted by admission.

L0 governor.py imports only stdlib. It loads/hashes the explicit caps file,
uses injected quotes/account/session/clock, sizes whole shares and directionally
rounds limits, checks entry FINAL notional/collar arguments, freshness and long-only
positions, then journals a one-use reservation. Refusals contain bounded codes,
never raw hints. At most 2 names, 200 USD/name, spread 50 bps, ask 5–200,
quote 60 s, entry trade 120 s. Unset/malformed caps refuse. Notional, ask band, spread and collar
apply only to buys. Exit_all sells the held whole quantity at the directionally
rounded bid in every session; it still needs fresh valid two-sided quotes,
reconciled long positions and LIMIT/DAY. An exit keeps quote freshness only;
its reservation deadline is quote_ns plus the quote limit. Integrality and
nonnegative quantity are checked for the exited symbol; entries retain the
account-wide position check.

L1 guarded_api.py encapsulates the original SDK client in closure cells rather
than plain attributes. Only owned cancellations, approved reads and exact
decision-derived single submits are available. Every final payload key/type/
TIF/side/qty/price/session/token is checked. Lumibot's SIMPLE no-child marker
is removed, and its omitted extended_hours/client_order_id fields are injected
only for a previously bound Decision. Arbitrary custom_params remain refused.
Price string normalization preserves exact Decimal equality; native round()
is observed to be the identity on the governor's tick output.
The SDK and journal receive a copy of the reservation's own values and token,
through a proxy-owned serializer. Caller classes and lying str subclasses cannot
replace those values; the vendor's legitimate str-valued Enums remain compatible.
A refused native consume
clears its bridge, and binding discards bridges whose reservation no longer exists.

The proxy reserves up to4 transport attempts per SDK call (default3retries),
counting against200requests/180submits per rolling minute, without sleeping,
retrying or implementing a transport throttler. It refuses a larger configured
retry ceiling. This is conservative admission accounting; vendor/engine
transport pacing remains authoritative. Restore preserves consumed budgets.

L2 stock_only_alpaca.py loads Lumibot only through load_classes after dotenv,
default broker, stream, orders thread and telemetry settings are explicitly
disabled. Nonempty LUMIBOT_STRATEGY_PARAMETERS, BACKTESTING_PARAMETERS,
LUMIWEALTH_API_KEY, DISCORD_WEBHOOK_URL and LISTENER_WRITE_URL refuse before
vendor import; they could redirect the inbox or enable third-party output.
Construction refuses absent/false PAPER, ambiguous paper aliases,
missing session, stale clock, or a resolved SDK URL other than the exact paper
host. It does not repair a missing PAPER setting. The real client's BaseURL
enum value is checked, rather than trusting config text.
The vendor-retained `_config` and other broker dicts have credential fields
removed after construction, as do its plaintext credential attributes.
Single native orders
must be stock/limit/day/whole-long-only with no compound/SmartLimit/custom
parameters. Batch/multileg/modify/sell_all/close_position(s) seams refuse.
Replacement pricing requires cancellation plus a new closed-inbox intent.

IntentStrategy is a trusted fixed deterministic class. The closed inbox accepts
only symbol/side/sizing; no model prices or quantities. No Lumibot agent object
is created and its agents property refuses. The constructor's lazy-component
assignment is accepted and discarded without resolving an agent manager. Native
acceptance uses the real Strategy constructor and executor initialization.
Python reflection is not a sandbox:
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
At proxy construction, cancellation ownership is re-derived from journal submit
rows joined with the broker's open orders: the client id must carry the arm's
a6- prefix and appear in the journal. An unreadable restart order list refuses.
Unknown open orders refuse entries but do not block a held-position exit or
reconciliation. Our unresolved orders still require reconciliation. A failed
cancel sets recovery only while its order is outstanding; after cancellation
and a reconciled terminal snapshot, the restart test's exit proceeds. Acceptance
uses a fabricated order-list SDK; this is not an observed broker restart.
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

run_acceptance uses an explicit nonsecret child environment, retains the actual
HOME and supplies the existing ENGINE_QUAL_OFFLINE audit hook. Under the actual
HOME, A7 checks that the hook denies ~/.aws/credentials before any read. The
hook's protected store is ~/.config/new-wsl-native-stack. The default broker-key
store ~/.config/native-agent-stack is not covered by this hook; nothing in the
run opens it. No protected bytes are read. Socket connections are denied. A second SDK client
is denied on its credential-file or network path before any broker interaction.
The output directory must be outside the worktree. Raw logs/receipts remain
private; export_receipt publishes bounded result summaries and code/output
hashes rather than raw identity-bearing trace fingerprints. Every failure and
interim run is retained outside the tree.
The runner snapshots code, caps, inventory, harness and test hashes before the
run and rechecks them afterward. Export refuses changed run-time inputs or logs,
and mismatched mutation source/test hashes, before publishing results.

## Observed evidence and limits

The current receipt records 48 L0/L1 cases and 13 native/stub seam cases passing
in the isolated runtime, zero skips, including 500 seeded model-hint invariance
cases (seed 260413). The 500-case numerical test suppresses only repeated fsync
calls; the separate A6 durability test observes real fsync before the SDK.
Stdlib-only CI executes the three seam tests and explicitly skips10native
cases; those skips are not native acceptance. Tests are unittest-discovered,
not silently collected through pytest alone.

A8: 74 selected exact-site mutants killed, 0 survived, 0 not-applied, 0 invalid-runs,
0 baseline-failures, including a paired removal of both final-payload equality
checks. Each probe first runs its unmutated named case successfully, then must
execute that same case with AssertionError and that test's id in the output.
The harness does not match an individual assertion's text. Import errors or
exception-only failures do not count as kills. This is a targeted sweep of the
listed sites, not an exhaustive census of all refusal statements or inventory
behaviors. Native constructor, credential scrub and actual-HOME fixes also
have retained fail-before runs against tree0a0e96e3. The exit policy has24
session/scenario subtests that fail before the fix and pass after it.
The round-2 R13/R14/E5–E8 cases fail against tree 18f35a8a (R13b is a positive
control that passes both). Their guard mutants cover canonical values/tokens,
each override variable, quote-only deadline, own-symbol integrality and the
journal/prefix ownership and recovery operands, including an independent
synthetic legacy-client-id test. No broker observation is credited.
Early sweep28found2masked survivors and1ambiguous site; tests/site targeting
were corrected without weakening expected reasons.
Initial native fixtures exposed the SIMPLE default and invalid compound/crypto
fixture construction; corrected pinned-source fixtures and final runs are
retained. No broker observation, strategy return or full-suite pass is claimed.

Production prerequisites remain: designation, account-exclusive credential-run
launch and OS/network isolation, trusted live snapshot/session provider,
permitted caps/config binding, and flat-and-idle rotation under the account's
single-writer lock. The acceptance does not authorize any of those actions.
