# Native receipts, masked for publication

Every `.capture` file is a deterministic masked derivative of an actual
util-linux `script` capture. The recorder's native first line contains the
exact command; its last line contains `COMMAND_EXIT_CODE`. These are the
receipts. A manually written index, fixture or summary is not a run receipt.

Recorder source: util-linux/util-linux@v2.41.3,
`term-utils/script.1.adoc:54` (raw terminal log), `:69` (command), and `:79`
(native child exit status). `recorder-version.capture` observes that version.
Source-manual excerpts are retained in `../upstream/recorder-source.json`.

`../mask_capture.py` publishes the exact masking rule; its twelve synthetic mask
tests are in `tests/test_final_backtesting_capture_mask.py`, with two publication
controls in `tests/test_final_backtesting_publication.py`. The publication CLI verifies
the exact cited sanitizer/direct-import bytes at caa22414. Ordinary mask_bytes
calls do not gate on live source hashes, so unrelated main edits cannot break
required unit tests. Reuse still supplies explicit
hostname, home and username context, marked path substitutions, runtime
identifier and private raw-digest masking. Counts, timestamps, failure text,
stream order and newline bytes are preserved; it never selects a tail or
invents an outcome. The large original LEAN compilation stream remains private,
named only, and is not replaced by a published tail or a binary artifact.
`../masked-capture-metadata.records` is the masking
tool's output: it hashes only each published derivative, never private bytes.

Raw inputs stay private, named only: `recapture/<capture filename>` and
`initial/<stream filename>` in the co-op handoff. The co-op checks reproduction
privately. Marked command placeholders are `[WORKTREE]`, `[RECAPTURE]`,
`[SCRATCH]`, `[USER_ROOT]`, `[FOLD]`, `[FOLD_INPUTS]`, `[HORIZON]`; commands retain
all public arguments and native rc. CPU/OS/RAM/swap values become `[HOST_SPEC]`,
without removing lines or changing engine counters. Private context and the
ordered replacement map are named in the co-op handoff.

The Nautilus test run is a **BOUNDED SMOKE**, with simulated test inputs.
`nautilus-native-simulation-invoke.capture` is an **empty-engine simulation**,
with no market data/orders. It proves an invocation, not historical E2E,
production wiring or useful adoption. Full E2E remains a named gap. The LEAN
test host fails; its native capture and original TRX are not a passing run.

The old `../logs/` files are full masked command streams, not command/rc
receipts on their own. The old driver status object is not used as measured
evidence. `../execution-receipt.json` is explicitly a source/capture index.

The old ruled-regressions-red capture is retained privately only: it used a
pre-edit test file and its old host mask cut assertion text. It does not prove
final-file regressions. The landing RED/GREEN captures use the same final test
file; the RED runs two selected regressions against the pre-fix masker. The
current mask matches host-spec fields only at a field/log-line start, preserving
assertion diagnostics. Host-spec fixture values are synthetic.
