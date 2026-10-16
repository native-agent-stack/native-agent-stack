# Masked native preparation captures — custody, not summaries

Every file under `masked/` is labelled by this document as a **deterministic
masked derivative of native capture**. Streams are byte-preserving except
for declared literal private-path, build-digest and private-source cache-key
replacement. No result, error, count or
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
clock, and those timestamp values are public in their derivative files.
Original custody files and their separate raw hash manifests remain private
with the co-op. For a path-free file the derivative is byte-identical, so
its public-byte hash necessarily also equals its raw-byte hash. This is not
a claim that public timestamps/trivial fields or their identity hashes are
secret. Separate private raw-manifest hashes are never copied here.
Published hashes are listed separately in `PUBLIC-SHA256SUMS` and the
repository registry, and bind only bytes published in this tree.

## Published masking rule

Implementation: `tools/sota-convergence/mask_execution_broker_capture.py`.
Tests: `tests/test_execution_broker_capture_mask.py`.

The initial co-op-checked map uses three literal absolute paths and marked
replacements; its original four capture sets remain byte-identical:

- `<WORKTREE>`: this owned scratch checkout root.
- `<PACKET_SCRATCH>`: this invocation's packet-output scratch root.
- `<EXISTING_PYTHON>`: the read-only existing interpreter executable.

The fold's separate private map adds the literal scratch root/executable
paths `<FOLD_SCRATCH>`, `<RECORDER_PYTHON>` and `<UV_BIN>`, plus the explicit
unpublished ephemeral build digest replaced by `<UNPUBLISHED_BUILD_SHA256>`.
The failed setup's absent executable is marked `<UNAVAILABLE_UV_PATH>`.
The digest value itself stays private; it is not a wildcard/summary operation.
The published test uses only a synthetic repeated-digit value to exercise it.

The second fold also declares pip's exact private-source SHA224 cache key as
`<PRIVATE_SOURCE_CACHE_KEY>`. pip26.2.1 hashes the source URL and interpreter
inputs and shards the key as two/two/two/remaining hex characters:
[pypa/pip@634a6ec cache.py:27-30,50-73](https://github.com/pypa/pip/blob/634a6ec/src/pip/_internal/cache.py#L27-L73)
and [wheel_builder.py:49-50,88,196](https://github.com/pypa/pip/blob/634a6ec/src/pip/_internal/wheel_builder.py#L49-L50).
The private map declares the full56-hex literal; the masker replaces both its
plain spelling and that exact sharded spelling. It does not match arbitrary
hex strings. `masked/fold1/ibflex-install/stdout.txt:73` is re-masked from its
unchanged raw capture; the source key itself is never published here.

The rule compiles escaped byte literals, longest-first with a lexical tie
break, and substitutes in a single pass. All other bytes remain unchanged.
No recursive replacement, newline normalization, decoding or general secret
scanning occurs. Only declared path, build-digest or cache-key literals change. Inputs are path/cwd/command/stream records,
not credential data. The private map and exact raw command stay private.
Failure to match a path does not certify privacy: native publication scanning
is a separate check. Files with no matching private path are byte-identical
derivatives and are still labelled masked, not newly authored output.

Reproduction command, with **marked placeholders** (not literal host paths):

```text
python3 tools/sota-convergence/mask_execution_broker_capture.py --mapping <PRIVATE_MAP> --input <RAW_CAPTURE_FILE> --output <NEW_DERIVATIVE_FILE>
```

The output must not exist: the CLI writes exclusively and refuses to overwrite.
The public test uses synthetic path/digest literals and arbitrary byte controls;
it verifies exact byte preservation, longest overlapping path selection and
invalid-map refusal. The literal-engine control deliberately replaces `/a`
with `/b` while `/b` is another key: expected `/b <B>` differs from a
sequential rescanning implementation's `<B> <B>`. A separately retained
sequential-mutant run fails that assertion; the original disjoint-placeholder
test did not establish it. No credential is read by these controls.
The stronger second-fold control uses the swap map `{/a: /b, /b: /a}` in
both insertion orders, expecting `/b /a` from original `/a /b`. Synthetic
sequential replacers fail for both forward and reverse traversal. This proves
simultaneous replacement independently of either sequential ordering.

The recorder's raw native files cannot be reconstructed from this public tree,
and no such reconstruction is claimed. The co-op must privately verify that
every derivative equals the published masker applied to the named raw file
and private map before publication. New fold captures require a fresh private
reproduction PASS before pushing. Missing capture is a
named GAP, not a synthesized stand-in. The rejected old PR's transcripts are
not reused by any of these capture sets.

## Fold1 native captures — additional custody scope

All files under `masked/fold1/` are also labelled **deterministic masked
derivatives of native capture** under the rule above. Each has the same seven
native recorder files. A name in this table refers only to a private capture
directory by name; it does not publish that directory's raw fingerprints.

| Raw name / public subdirectory in `masked/fold1/` | Purpose / scope |
| --- | --- |
| `checkout-ibflex`, `checkout-kumo` | Native exact detached source checkouts; setup/source identity, not tests |
| `checkout-rust-ibapi` | Native detached source checkout for the client-pin reconciliation; no build or test is inferred |
| `ibflex-source-pin`, `kumo-source-pin` | Native Git HEAD at the suite source; published upstream commit, not raw-log hash |
| `ibflex-venv`, `kumo-sync` | Preserved failed setup (rc1 and127 respectively), neither a test result nor pass |
| `ibflex-venv-corrected`, `kumo-sync-corrected` | Native successful scratch environment/install setup |
| `ibflex-install` | Native vendor editable package/dev-tool install; ephemeral unpublished wheel hash is explicitly masked |
| `ibflex-offline-tests`, `kumo-offline-tests` | Unchanged upstream offline synthetic suites with network denied; counts/rc in native stream and rc files, scoped by `OFFLINE.md` |
| `ibflex-python-version`, `kumo-python-version`, `scratch-uv-version` | Native tool/interpreter version outputs only |
| `uv-sync-help`, `uv-run-help` | Native installed CLI primary-source help at the separately captured uv version; supports the used flags, not E2E |
| `masker-one-pass-red`, `masker-build-digest-red` | Native fail-first controls before their corresponding implementation changes |
| `masker-sequential-mutant-red` | Explicit synthetic sequential-replacement mutation; failing output is a test of the publication rule, not a production failure |
| `masker-fold-green`, `masker-tested-source` | Native final four-test run and native SHA256 of the two published tested source files; those source-file hashes bind public code, not private logs |

The private sequential-mutant source is a copy of the published masker with
only the `replace_literals` body replaced by the explicit synthetic fault:

```python
for key, value in values.items():
    raw = raw.replace(key, value)
return raw
```

Its captured native failure distinguishes inserted `/b` being rescanned from
the supported single `Pattern.sub` call. It is labelled a mutation control,
not a reproduction of a production defect or an upstream broker test.

Only these named sets have supplied publication custody. Repository validator,
registry/view, privacy and staged-leak checks are supporting release work, not
additional published PASS receipts or execution-broker evidence. The PR body
must not claim a supplied custody result for checks outside this table.

## Fold2 publication-boundary correction

`masked/fold2/` adds six seven-file native capture sets under the same rule:

| Raw name / public subdirectory | Purpose / scope |
| --- | --- |
| `fold2-cache-key-red` | Five-test run with the new synthetic install-line regression on the prior masker: rc1, SHA224 map rejected |
| `fold2-cache-key-green` | Same five-test run after the cache-key correction: rc0 |
| `fold2-swap-forward-mutant-red`, `fold2-swap-reverse-mutant-red` | Explicit synthetic sequential faults, each failing both swap-map insertion orders; rc1, not production failures |
| `fold2-masker-green` | Final six synthetic publication-boundary tests: rc0 |
| `fold2-masker-tested-source` | Native SHA256 of the two final published code files; public-source binding only |

The prior `masker-tested-source` and four-test `masker-fold-green` captures
remain historical. The new six-test/source captures bind the corrected code.
The raw fold1 streams stay unchanged. Only the newly declared cache-key
replacement changes a previously supplied derivative. Supporting private
sweep/validation work is not supplied layer qualification evidence.
