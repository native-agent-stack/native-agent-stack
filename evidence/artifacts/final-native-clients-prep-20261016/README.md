# Native-client preparation evidence

This folder records **installation and offline CLI readiness only**. It is not
authenticated model-task E2E, a comparative A6 run, or FINAL admission.

- `native/index.json` is the recorder-derived index of **masked native captures**.
  Each command has marked path placeholders, its native return code, capture
  timestamps and hashes of the exact **published derivative bytes**.
- `native/*.stdout.txt` and `native/*.stderr.txt` are actual process streams.
  Empty streams remain empty. The masker does not decode, reflow, strip ANSI,
  remove errors, append text or add a final newline.
- `record_native.py` redirects native stdout/stderr directly into private binary
  files and records exact argv/cwd/rc. The private originals are cited by capture
  name only; raw digests are never copied into the public index.
- `mask_native.py` replaces only the explicit private-map literals in one pass,
  longest match first. All other bytes remain unchanged. Placeholder names are
  listed in the index; their private values are not published.
- `capture-summary.json`, `pin-reconciliation.json` and `multi-angle-draft.json`
  are **derived analysis**, not substitutes for native output. Their factual
  claims cite the native streams/index or public repository sources at path:line.
- `upstream/claude-2.1.301-manifest.json` is the vendor's public release manifest,
  retained byte-for-byte. Signature and binary verification execution is captured
  separately under `native/`.

The private capture group is named `native-clients-recapture-20261016`. Its
exact directory and masking map are supplied privately to the co-op. The co-op
reproduces the public directory with this command; placeholders below are
explicitly marked and are not asserted as the original native argv:

```sh
python3 evidence/artifacts/final-native-clients-prep-20261016/mask_native.py \
  --raw-dir '<RAW_CAPTURE_DIR>' \
  --map-file '<PRIVATE_MASK_MAP>' \
  --out '<NEW_EMPTY_DERIVATIVE_DIR>'
```

The reproduction must be byte-identical, including `index.json`. Existing output
directories and existing raw capture IDs cannot be overwritten. The script
refuses absent raw streams or a mismatch against the privately recorded raw
byte count/digest; it never invents substitute content.

`tests/test_native_client_capture_custody.py` supplies **synthetic custody
controls**, not simulated client outcomes: raw invalid-UTF8/ANSI/CRLF preservation,
nonzero native exit retention, explicit path masking, repeated byte-identical
reproduction, missing/tampered raw refusal, and capture overwrite refusal.
The fail-first streams are `native/red-recorder-control.stderr.txt` and
`native/red-mask-control.stderr.txt`; the six-test green result is
`native/green-capture-controls.stderr.txt:9` and `:11`.

The first preparation attempt retained transformed streams without raw custody.
Those older logs are not included as qualifying captures. Their three namespace
setup failures remain a named historical capture gap in `capture-summary.json`.
Fresh native captures here are separate observations. No inverse masking is
used to reconstruct missing originals.

The installed native binaries remain inside isolated scratch profiles. Native
installation commands use a read-only host root, masked homes/runtime sockets
and a cleared environment; the caller-home pathname is bound to scratch, not
reassigned to another host location. Version/help commands also disable network
access. Existing-host probes are read-only `--version` commands. No credential
store, live paper unit, broker or host runtime lock is involved.

Primary mechanisms: CPython `v3.13.16` `Lib/subprocess.py` (`run` with binary
file descriptors), `Lib/re/__init__.py` (bytes-pattern substitution), and
`Lib/hashlib.py` (`file_digest`/SHA-256). Recorded interpreter versions are in
`native/python-version.stdout.txt:1` and `native/system-python-version.stdout.txt:1`.
The vendor install sources and exact pins are in the dated decision record.
