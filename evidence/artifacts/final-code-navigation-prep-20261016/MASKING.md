# Masked native capture custody

The measured outputs in `outputs/` are literal masks of real native exec tool captures. The companion `captures/` files retain the command, cwd, native result metadata, complete output chunks and return code under the same mask. These are exports of results retained by the session after the runs; no separate original OS stdout/stderr streams are reconstructed.

`masked-captures.json` labels each derivative, names its private source and binds only published bytes. The raw-capture set is named `code-navigation-native-capture-20261016`; its location is supplied to the co-op privately. `RAW-SHA256SUMS` remains private. No digest of unpublished bytes belongs in a public receipt.

`mask_capture.py` replaces only explicit private path prefixes with marked placeholders, longest prefix first. Its private binding file supplies the actual values for `$SCRATCH`, `$REPO`, `$USERHOME`, `$PYTHON`, `$UV_BIN` and `$NODE_BIN`. Every other byte is preserved, including whitespace, non-UTF-8 bytes and line endings. The published-byte hash contract is the existing recorder contract at `scripts/host_receipts.py:1012` on base `30542e70560147c19049016d19aa3f264515c92f`.

The co-op can check a derivative without changing it:

```sh
python3 mask_capture.py \
  --raw "$PRIVATE_CAPTURE_DIR/health-check.raw.txt" \
  --bindings "$PRIVATE_CAPTURE_DIR/alias-bindings.json" \
  --published outputs/health-check.log --check

python3 mask_capture.py \
  --raw "$PRIVATE_CAPTURE_DIR/health-check.capture.json" \
  --bindings "$PRIVATE_CAPTURE_DIR/alias-bindings.json" \
  --published captures/health-check.json --check
```

The exact command is retained in the private capture. The command in each published `captures/` record is its marked-placeholder derivative. Native return codes remain unchanged. The JSON pin/E2E/invoke indexes are curated metadata pointing to these captures; their summaries do not replace native output.

The earlier first-failure excerpt has been removed. `outputs/core-first.log` now preserves the complete masked native failure output. The source-pin and version files have real read-only native captures; they are not stand-in strings. The previous broad preparation timestamps were not a captured invocation window and have been removed from `invocation.json`. Original acquisition, fixture-copy, git-diff, primary API date, independent uv/node version and platform captures remain named gaps.

`test_mask_capture.py` contains six synthetic unit fixtures for privacy replacement, longest-prefix ordering, byte preservation, line endings, determinism and invalid bindings. These fixtures are tests of the masking rule, not candidate E2E measurements. The local check is:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s evidence/artifacts/final-code-navigation-prep-20261016 \
  -p test_mask_capture.py -v
```

The co-op's private reproduction check passed on 2026-10-16. The lane has resumed. Publication still requires evidence registration and repository validation; the measured derivatives and masking rule remain unchanged.
