# Native isolation capture and deterministic publication

This recorder supports the bounded foundation/isolation preparation window.
It does not install on the host, activate a sandbox policy for other work, or
decide a catalog winner. `run.py` uses owned scratch prefixes and upstream
commands at Worktrunk 0.80.0 and sandbox-runtime 0.0.79.

`capture.py:record` opens private stdout/stderr files in binary mode and gives
the file handles directly to `subprocess.Popen`. It records exact argv, cwd,
the explicitly constructed environment, native return code, timestamps, and
private raw-byte hashes. Existing capture names cannot be reused. No decoding,
substitution, summarization or synthetic output precedes that recording.
Private capture files are mode 0600 within mode-0700 capture directories.

The upstream mechanism is CPython **v3.13.16**,
[`Doc/library/subprocess.rst`](https://github.com/python/cpython/blob/v3.13.16/Doc/library/subprocess.rst):
the `Popen` constructor accepts existing standard-stream file objects,
`wait()` supplies the process return code, and binary streams preserve bytes.
The recorder uses those supported interfaces without a shell interpreter.
The checked-in tests exercise non-UTF-8 bytes, CRLF, NUL, a nonzero return code,
missing or modified raw files, literal masks, reproducibility and immutable
capture names. Test inputs are synthetic controls, not product E2E receipts.

## Private originals and public derivatives

The private run directory is named **isolation-native-recapture-20261016**.
Each capture name identifies `invocation.json`, `record.json`, `stdout.bin`
and `stderr.bin` in its private subdirectory. The co-op receives the location
privately. No private raw hash is published as a source citation.

Every published capture is labeled `masked_native_capture`. Its two `.txt`
files are byte derivatives of the native streams; the extension does not imply
text decoding. Its JSON metadata carries marked command placeholders, native
rc/time fields and hashes of the **published stream bytes**. The repository
evidence manifest additionally binds each complete published file.

Masking is one simultaneous, longest-match literal byte replacement. The
private `mask-rules.json` maps exact strings to the following placeholders:

| Placeholder | Source of exact private replacement |
| --- | --- |
| `<SCRATCH>` | Owned run directory supplied to `run.py` |
| `<REPO>` | The preparation worktree supplied to `run.py` |
| `<USER_HOME>` | User path used only to mask tool paths in the selected PATH |
| `<FIXTURE_OBJECT>` | Full disposable Git object from `fixture-object/stdout.bin` |
| `<FIXTURE_SHORT_OBJECT>` | Its seven-character short form, as used by native Worktrunk output |
| `<UPSTREAM_BUILD_PATH>` | The `_resolved` path in the captured public npm metadata; added after the public path scan |
| `<UPSTREAM_PUBLISHER_ID>` | The `_npmUser.trustedPublisher.oidcConfigId` field in the same public npm response; added after publication validation |

The last two rules remove a vendor CI build path and publisher configuration
identifier from the public npm response. They do not alter the private original.
Hash-like strings outside these exact
matches, including public upstream commit pins, are preserved. No blanket
hexadecimal or line filter is applied. Output bytes outside the matches are
identical, including invalid UTF-8, newlines and control bytes. Raw bytes must
match the private recorder hashes before publication. A missing or changed
raw file fails; it is never replaced with a reconstructed summary.

To reproduce, using paths supplied privately by the co-op:

```sh
python3 blueprints/convergence-practice/isolation-capture-20261016/capture.py \
  --raw-dir <PRIVATE_RAW_DIRECTORY> \
  --rules <PRIVATE_RAW_DIRECTORY>/mask-rules.json \
  --out <NEW_EMPTY_DERIVATIVE_DIRECTORY>
python3 -m unittest tests.test_isolation_native_capture -q
```

Compare every resulting file with
`evidence/artifacts/isolation-native-captures-20261016/masked/`. The masker
refuses to replace an existing different derivative. Neither the native run
nor the tests are needed to replay publication from the retained originals.
The raw directory also retains the native generator's isolation packet by
name, as an input for authored analysis, not as E2E or invoke evidence.

## Native scope

- Worktrunk uses the official [v0.80.0 release installer](https://github.com/max-sixty/worktrunk/releases/download/v0.80.0/worktrunk-installer.sh)
  with `WORKTRUNK_UNMANAGED_INSTALL`: owned prefix, no PATH edit or updater.
  Its [pinned README](https://github.com/max-sixty/worktrunk/blob/b49ca7eea9b03145791a5b94eccaf9c59412ed37/README.md#L159)
  supplies native create/list/remove. The Git repository is a synthetic fixture,
  with hooks disabled and no remote; commands execute the real installed binary.
- sandbox-runtime uses the [pinned npm installation](https://github.com/anthropics/sandbox-runtime/blob/d9aac2098351ca17f3743fbaf6ecbd0051b7e00e/README.md#L14)
  in an owned prefix/cache with separate scratch npm config paths. Its
  [documented echo](https://github.com/anthropics/sandbox-runtime/blob/d9aac2098351ca17f3743fbaf6ecbd0051b7e00e/README.md#L168)
  uses explicit settings. The additional allow/deny-write operations are
  synthetic one-file controls through the real CLI, not upstream test suites.
- `lane_packets.py` runs through its existing CLI. Its stdout is captured as
  generator output. The packet and six-angle draft are research inputs and
  authored analysis, not measured product performance.

Access date for the sources above: 2026-10-16. No full upstream suite, network
policy, VM/resource enforcement, general escape resistance, cross-platform
acceptance or continuing operational usage is claimed by these smokes.
