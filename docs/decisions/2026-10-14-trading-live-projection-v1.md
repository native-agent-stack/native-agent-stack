# Trading live projection v1

Build the frozen trading field contract as a display-neutral local stream.
The private FIELDS-v1 specification and its sealed v1.1 addendum are the
contract authority; the CC accepted its Q1-Q4 defaults on2026-10-14. Owner
conversation is not retained here. Lanes A/B and the future decision log
remain addenda v1.2/v1.3, respectively.

## Sources and adopted mechanisms

This extends the selected existing observability stack, rather than choosing
a new runtime or reopening a catalog layer. The native Collector owns file
ingestion, storage, JSON parsing, transformation and OTLP delivery. The new
projector supplies the missing trading-specific allowlists, joins and
crash-consistent sanitized-spool commit; it never exports raw source ids.

- [open-telemetry/opentelemetry-collector-contrib v0.162.0,
  receiver/filelogreceiver/README.md:27-56](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/receiver/filelogreceiver/README.md):
  supported file tails, start position and persistent offset storage;
  its copy-truncation section documents read_whole_file behavior.
- [Contrib v0.162.0, processor/transformprocessor/README.md:69-106](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/processor/transformprocessor/README.md):
  log statements and propagate error handling; the pinned
  [OTTL functions](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/pkg/ottl/ottlfuncs/README.md)
  define keep_keys and String serialization. Installed contrib0.162.0 is
  exercised by native validation, resolved-config comparison and file export.
- [grafana/loki v3.7.8, docs/sources/shared/otel.md](https://github.com/grafana/loki/blob/v3.7.8/docs/sources/shared/otel.md):
  native OTLP ingestion, resource-attribute index policy and JSON bodies.
  The installed3.7.8 executable validates the policy and receives a synthetic
  isolated OTLP record; its series endpoint verifies the exact label set.
- Private primary producer source, read as committed blobs only:
  `blueprints/us-equities/adaptive-paper/ibkr_port.py` at
  `0d13c8ea1f572aca17ef6844b360a8257e46e53b`, lines657-681,805-819,
  1412,1482,1509,1560-1566,1671,1711,2142,2191,2246-2254. The deployed
  `76856c067347f6c087f7328509297f5975aafe39` blob was separately checked.
  These are local, unpushed source-owner commits; no producer code or journal
  is copied or pushed by this PR. The deployed submit source lacks the later
  optional pricing observation, which remains omitted when unavailable.

## Data boundary

Only IBKR and C kinds named by the frozen contract can produce rows. Every
row is validated against its per-lane/per-kind field set before a write;
an extra output key refuses the whole row and increments private health.
Raw input is projected selectively, not copied. Unknown C types refuse.
Reserved kinds are not emitted. Fixtures construct synthetic journals and
synthetic balances; no live journal is read by the verification suite.

SYMBOL is a ticker-format check, including dotted tickers. Invalid/account
shapes become OTHER. REASON is a bounded, masked deterministic calc template:
path/email/quote/control-bearing text drops, digit runs and ticker tokens
are masked, and length is capped. Catalyst prose is excluded; only its
presence flag is retained. Balances are numeric values for the local stack,
never real published fixture values or PR receipts.

NUM is finite and bounded; INT remains bounded for counters and durations.
The addendum's epoch-ms TIMESTAMP interval applies separately. Source time
outside that interval refuses a row; other invalid timestamps are omitted.
Execution time accepts only the explicitly zoned Eastern shape; signed
quote age is retained. Source labels and text are never Loki index labels.

## Checkpoint and crash behavior

The projector opens producer files O_RDONLY, takes no producer lock, and
writes only its separately supplied state/spool paths. A source inode and
offset identify the last emitted complete line. A new inode starts at0;
in-place truncation refuses under v1's append-only producer contract.
Partial lines wait for a newline. Sequence resets do not deduplicate.

On process restart, reading from0 rebuilds order/round/execution joins in
memory, while previously checkpointed lines emit nothing. Source order,
client, permanent and execution identifiers never enter checkpoint/spool
state. Order keys use the contract's run/ordinal mapping. Deterministic
row_id uses the run and source byte offset, with an item ordinal for exploded
rank rows. Array indices preserve source order.

A private write-ahead record stores only sanitized output bytes and the
prospective checkpoint. Under the tailer's own lock, the pending record is
fsynced, the spool append is fsynced under flock, and the checkpoint is
atomically replaced/fsynced. Recovery restores the pending append at its
recorded spool offset before completing the checkpoint. This closes the
append/checkpoint restart gap locally, including a partial write. Rejected
line offsets are remembered separately so refusals count once without
pretending they emitted. Spool mode stays0600; a spool past8MiB is truncated
on the next append, matching the existing snapshot convention.

Exactly-once ends at this projector/spool boundary. Collector filelog retry,
restart and copy-truncation can redeliver. Future counting consumers must
deduplicate on row_id; no end-to-end exactly-once claim is made.

## Additive transport and invocation

trading-live-collector.yaml adds only file_log/trading_live,
transform/trading_live and logs/trading_live. The receiver's distinct
component id namespaces its file_storage checkpoint. The processor clears
resource/scope attributes, keeps the frozen union, serializes JSON into the
body and clears log attributes. Resource attributes are service.name and
stream only. Lane, kind, symbol, order_key and row_id remain body fields.

trading-live-loki.yaml is a source-only OTLP policy example that retains
Loki's default policy and adds stream as an indexable resource attribute.
The live resource therefore has exactly service_name and stream=live.
Existing Collector files, receivers, transforms and pipelines remain
byte-identical; native resolved-config comparison also checks equality after
composition. No display, panels, unit, timer or deployment is added.

The one-shot CLI takes explicit source roots/indexes and its own private
paths. The canonical spool selection is:

```sh
python3 observability/trading_live.py \
  --state "${NS2604_OBSERVABILITY_DATA}/trading-live-state" \
  --spool "${NS2604_OBSERVABILITY_DATA}/trading-lanes/live.jsonl" \
  --ibkr-index "$IBKR_EVENTS_INDEX" --calc-root "$CALC_RUN_ROOT"
```

The co-op owns post-landing wiring and its deployment boundary after reads.
The CLI prints only fixed status/count health, never a source path/error body.
No broker, credential or runtime-lock access is implemented.

## Verification and limits

The nine section9 tests were introduced one slice at a time, each observed
red before its satisfying code. The private build receipt retains those
signals. Additional checks cover incomplete lines, durable refusal counts,
append/checkpoint fault injection, the executable CLI and the v1.1 bounds/
row_id addendum. Native file-export and isolated Loki tests verify the
actual installed upstream mechanisms, not a simulated transformation.

Main at the branch's starting pin lacks #1106's pending snapshot projector.
Local integration separately ran that held artifact's15existing reader
fixtures and compared its native trading_projection config before/after the
live overlay. Its source stayed byte-identical to its held commit. The new
PR does not copy or mutate that pending feature, and its resolved-config
test can include the separately supplied snapshot overlay.

No native live-journal fidelity or post-deployment receipt is claimed. The
remaining acceptance is independent review, landing and co-op-owned local
deployment qualification at its named boundary.

Current-day validation at the UTC rollover returned rc1 solely for nine
weekly active-model-currency checks. A clean detached checkout of the same
origin/main pin reproduces the identical nine failures. No model record or
date override is changed in this PR; its publication/CI limitation remains
explicit pending the currency owner's sourced refresh.
