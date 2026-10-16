# Masked native preparation captures — custody, not summaries

Every file under `masked/` is labelled by this document as a **deterministic
masked derivative of native capture**. Streams are byte-preserving except
for declared literal private-path replacement. No result, error, count or
line is added, omitted, decoded or summarized. Empty streams stay empty.
Files are not authored observations.json or packet-receipt.json substitutes.

| Native capture name (private reference by name only) | Published set | Narrow observation and exact source |
| --- | --- | --- |
| `runtime-python-version` | `masked/runtime-python-version/` | Native existing interpreter version only, `stdout.txt:1`; command in `argv.json:2-3`, cwd in `cwd.txt:1`, rc in `rc.txt:1`. Not broker-package version or role invoke |
| `recorder-python-version` | `masked/recorder-python-version/` | Native recorder/test interpreter version only, `stdout.txt:1`; command in `argv.json:2-3`, cwd in `cwd.txt:1`, rc in `rc.txt:1` |
| `packets` | `masked/packets/` | Native supported packet-builder command, `argv.json:2-15`, cwd in `cwd.txt:1`, rc in `rc.txt:1`, complete native JSON stdout at `stdout.txt:1`. Packet preparation is not E2E or broker invoke |
| `masker-tests-final` | `masked/masker-tests/` | Native unittest execution of **synthetic publication-boundary controls**; command in `argv.json:2-7`, result/counts in `stderr.txt:1-8`, cwd/rc in their own files at line1. Not upstream suite or broker acceptance |

Each set also preserves the recorder's own native `started.txt:1` and
`ended.txt:1`. Those are actual invocation timestamps, not a later report
clock. Original native stdout/stderr, exact argv, cwd, rc and raw file hashes
remain private with the co-op; raw hash manifests are never copied here.
Published hashes are listed separately in `PUBLIC-SHA256SUMS` and the
repository registry, and bind only bytes published in this tree.

## Published masking rule

Implementation: `tools/sota-convergence/mask_execution_broker_capture.py`.
Tests: `tests/test_execution_broker_capture_mask.py`.

The co-op supplies the private map used for reproduction. It contains only
three literal absolute paths and their marked replacements:

- `<WORKTREE>`: this owned scratch checkout root.
- `<PACKET_SCRATCH>`: this invocation's packet-output scratch root.
- `<EXISTING_PYTHON>`: the read-only existing interpreter executable.

The rule compiles escaped byte literals, longest-first with a lexical tie
break, and substitutes in a single pass. All other bytes remain unchanged.
No recursive replacement, newline normalization, decoding, digest masking or
general secret scanning occurs. Inputs are path/cwd/command/stream records,
not credential data. The private map and exact raw command stay private.
Failure to match a path does not certify privacy: native publication scanning
is a separate check. Files with no matching private path are byte-identical
derivatives and are still labelled masked, not newly authored output.

Reproduction command, with **marked placeholders** (not literal host paths):

```text
python3 tools/sota-convergence/mask_execution_broker_capture.py --mapping <PRIVATE_MAP> --input <RAW_CAPTURE_FILE> --output <NEW_DERIVATIVE_FILE>
```

The output must not exist: the CLI writes exclusively and refuses to overwrite.
The public test uses only synthetic path literals and arbitrary byte controls;
it verifies exact byte preservation, longest overlapping path selection,
invalid-map refusal and nonrecursive transformation. It never reads credentials.

The recorder's raw native files cannot be reconstructed from this public tree,
and no such reconstruction is claimed. The co-op must privately verify that
every derivative equals the published masker applied to the named raw file
and private map before this preparation opens a new PR. Missing capture is a
named GAP, not a synthesized stand-in. The rejected old PR's transcripts are
not reused by any of these capture sets.
