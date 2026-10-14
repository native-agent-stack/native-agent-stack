# GET-only pre-skip flat proof and recovery

An interrupted GET-only skip may leave `active/pre-skip.json` before its
native observer creates a proof. The original observer omitted the frozen
transport's required `before_request` keyword, so both skip and the no-owned
trial recovery fallback raised TypeError before any request.

`observe_flat.py` reuses the frozen `mover_runner._preflight_observer` and
requires zero positions, zero open orders and a complete order enumeration.
It cannot create a ledger, adopt a position, cancel or submit an order.

The new launcher adds exactly `recover pre-skip`. It authenticates the original
predecessor seal and its native strict manifest, the unchanged PRE config, the
original active record, used GO digest and original GO payload. It runs the
native observer through the existing credential runner. A successful native
flat proof produces the standard handoff/recovery receipts, naming both seals,
then renames the ORIGINAL active bytes to `active.finished.json`. A non-flat
proof writes `needs_attention` receipts and retains the marker. No recovery
path reads, creates, deletes or clears STOP.

The source packet is immutable. `recut.py` takes its externally supplied
SHA256SUMS hash, captures every authenticated runtime member, transforms only
the launcher dispatch, observer and unit locations, and adds the recovery
helper/origin binding. Runtime and CONFIG bytes remain exact. The new unit
suffix is `-seq2-flat`, so the old and new generation must never be armed
together. Historical source proofs are retained outside the new runtime
inventory and are not presented as new acceptance.

## Sources and variant inventory

The fixed call follows native-agent-stack main
`8c95a50d10bd2db0b59058c6827275917ce35aa3`:

- `blueprints/us-equities/adaptive-paper/transport.py:1009-1018` makes
  `before_request` mandatory and installs it on GET-only clients;
  `:928-974` checks the method/path and synchronously invokes that hook.
- `mover_runner.py:620-625` provides the existing 50-request observer;
  `:695-697` and `:908-914` pass it to preflight.
- `runner.py:2345-2357` uses the same bound and keyword contract.
- alpaca-py **0.44.0**, commit
  `cc4cb3b7ba50ae250e621983c2779047fb16bb28`, remains the native SDK.
  Tests with `PAPER_FLAT_REAL_SDK=1` execute that SDK and the frozen guarded
  transport, stubbing only `requests.Session.request`; any non-GET fails.
- CPython 3.12's supported `ast`, `hashlib`, `pathlib` and `subprocess`
  APIs and GNU `sha256sum --strict --check` implement parsing/sealing; no
  new transport, broker client or checksum implementation is introduced.

The bounded variant check parses every top-level deployment script and every
frozen adaptive-paper Python file. It resolves direct `from transport import`
and `import transport` calls, including class constructors, and compares their
keyword arguments with required keyword-only arguments in the frozen AST.
Dynamic kwargs cannot satisfy a missing explicit required keyword. It does not claim to resolve
dynamic object method dispatch. The original source has these 15 direct calls:

| Caller | Function | Required keyword-only arguments |
| --- | --- | --- |
| observe_flat.py:29 | preflight | before_request (missing before fix) |
| frozen/blueprints/us-equities/adaptive-paper/mover_runner.py:695 | preflight | before_request |
| frozen/blueprints/us-equities/adaptive-paper/mover_runner.py:908 | preflight | before_request |
| frozen/blueprints/us-equities/adaptive-paper/mover_runner.py:913 | preflight | before_request |
| frozen/blueprints/us-equities/adaptive-paper/mover_runner.py:763 | fee_checkpoint | after, before_request |
| frozen/blueprints/us-equities/adaptive-paper/mover_runner.py:818 | halt_statuses_supported | none |
| frozen/blueprints/us-equities/adaptive-paper/mover_runner.py:829 | AlpacaPaperTransport | before_request, before_submit, sink_observation |
| frozen/blueprints/us-equities/adaptive-paper/mover_runner.py:945 | AlpacaPaperTransport | before_request, before_submit, sink_observation |
| frozen/blueprints/us-equities/adaptive-paper/mover_simulation.py:86 | normalize_intent | none |
| frozen/blueprints/us-equities/adaptive-paper/runner.py:653 | order_contract_status | none |
| frozen/blueprints/us-equities/adaptive-paper/runner.py:2355 | preflight | before_request |
| frozen/blueprints/us-equities/adaptive-paper/runner.py:2479 | halt_statuses_supported | none |
| frozen/blueprints/us-equities/adaptive-paper/runner.py:2501 | fee_checkpoint | after, before_request |
| frozen/blueprints/us-equities/adaptive-paper/runner.py:2528 | fee_activities | after, before_request |
| frozen/blueprints/us-equities/adaptive-paper/runner.py:2558 | AlpacaPaperTransport | before_request, before_submit, sink_observation |

The new observer's line number is recorded in the generated recut receipt.

## Review, build and changeover

1. Execute the fail-first path tests against the original sealed bundle using
   `PAPER_FLAT_BASELINE`, then the fixed tests using `PAPER_FLAT_FROZEN` to
   select the same original frozen tree. Both execute real observer/preflight.
2. Run the named tests and repository validator, commit/push normally, and cut
   a NEW destination using `recut.py --source ORIGINAL --output NEW
   --predecessor-sha256 EXPECTED --source-commit FULL_FIX_HEAD`.
3. Verify the new native strict seal, unchanged frozen/config bytes, all 22
   unit files with `systemd-analyze --user verify --man=no`, and the path tests
   using the sealed NEW helper/launcher bytes. Keep failed evidence.
4. Co-op obtains Astra and CC Opus micro PASS with no P1, then the explicit CC
   authorization naming the new bundle and its full manifest hash. The issuer
   remains paused while the original active skip remains.
5. The authorized operator uses the NEW sealed launcher via the existing
   credential-run boundary, `launch.py recover pre-skip`. No hand-written
   proof or active-record edit. Verify native rc0, flat/complete GET proof,
   both seal hashes in receipts and original active bytes retired.
6. Co-op performs the separately authorized retirement/install changeover:
   old 11 path units disabled/inactive, all services inactive, no pending GO,
   new 22 unit files installed/verified and new 11 paths armed. Never arm both
   generations. Co-op rebinds its sole issuer to the new manifest and new CC
   validity record, reruns its SYN end-to-end drill, then issues at readiness.
   Existing 60-second same-boot request-window drain still applies.

This coding lane does not run real recovery, place orders, edit STOP, or arm
and start units. The separate seq3 inventory PR remains unchanged.
