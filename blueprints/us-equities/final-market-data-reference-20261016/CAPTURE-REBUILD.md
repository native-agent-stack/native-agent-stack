# Capture custody and native recapture

The ten earlier records lacked privately retained original output. Their
uncaptured derivatives are excluded from publication and preserved privately
as unqualified observations. New captures supersede them; none was reconstructed.

Fresh recapture-v1 has 16 command captures and 32 public masked derivatives.
Each private capture directory retains stdout.raw, exact command/environment
specification, receipt.raw.json, mask-map.json and private raw integrity metadata.
No private raw digest appears in the publication. The co-op privately confirmed
all 32 derivatives reproduce from the 16 retained captures, all 33 inventory
hashes/sizes match, and all 16 command/rc bindings match. It reran the 5 masker
tests. The 2 recorder custody tests were not independently rerun; their native
published log reproduces from raw.

The published mask_capture.py applies a private literal map once, longest-first,
with marked replacement tokens. All other bytes remain unchanged, including
non-UTF-8 bytes, line endings and trailing whitespace. It is not a secret detector.
The test_mask_capture.py cases exercise byte preservation, overlap/order
independence, nonrecursive replacement and rejection of ambiguous rules.
test_native_capture.py exercises failed-child original retention and refuses
to overwrite an earlier output before the child runs. Its child output is
explicitly synthetic regression data, not component evidence.

Native captures of the tests are recapture-v1/masking-tests.log:8 (5 cases)
and recorder-tests.log:5 (2 cases), both exit 0 in their recorder metadata.
The native_capture.py recorder streams original merged stdout/stderr bytes
directly into the private file before masking; the exact command and observed
return code are recorded. Public label.json and label.log reproduce using:

```text
python3 mask_capture.py --raw <private-capture-original> --mapping <private-mask-map> --out <fresh-derivative>
```

For a log the original is stdout.raw; for a JSON receipt it is receipt.raw.json.
Private locations and reproduction instructions are shared with the co-op
outside this public repository. Raw captures are cited publicly by name only.

Repository secret/proxy redactors at tools/claude-review-worker/worker.py:1219
and tools/sota-convergence/codex_lane.py:765 do not provide this retained-byte
capture mapping contract. The task-specific transform and extension of the
original recorder use the documented CPython 3.12 interfaces:
<https://docs.python.org/3.12/library/re.html#re.sub> and
<https://docs.python.org/3.12/library/subprocess.html#subprocess.run>.
No dependency or service is installed for the recorder.

## Combined fold and encoded literals

The original family's private PASS applies to its original 16 captures and
32 derivatives. This scope-locked fold publishes 35 more capture pairs / 70
derivatives: the present publication total is 51 / 102, with 103 inventory
outputs including the packet. Private originals total 52: the first help
capture is retained privately only after a scanner found an unmasked generic
upstream home-path example. Its separately retained native replacement uses
the declared example-home placeholder. No old original was reconstructed.
The original derivative bytes remain unchanged, but the changed masker and
all 102 current derivatives passed the new private co-op reproduction check. The sequential three-wheel digest check also passed.

Native recorder metadata is serialized before masking. Therefore the masker
matches each private literal's original UTF-8 bytes and the exact JSON-escaped
contents produced by CPython json.dumps under either ensure_ascii setting.
It substitutes those byte literals once, longest first. Conflicting encoded
aliases are rejected. No native stream is parsed, normalized or reserialized.
Reference: https://docs.python.org/3.12/library/json.html#json.dumps

Two new synthetic masking cases exercise escaped Unicode, quote/backslash
values and ambiguous aliases; the custody test also exercises an escaped cwd.
Current native results are fold-v1/masking-tests-after.log:10 (7 cases) and
recorder-tests-after.log:5 (2). Before-fix failing native runs are retained
beside them. Native network guard controls deliberately return 86; the initial
upstream helper-collection failure returns 1. These are not passing E2E
receipts. Every command retains its actual return code and original bytes.

## Small custody correction

The current public set is 57 capture pairs / 114 derivatives and 115 inventory
outputs, with 58 private originals including one retired help capture. The
former 51/102 reproduction PASS does not qualify the revised publication.
Use publish_capture.py:public_pair for the complete current reproduction:
it takes stdout.raw, receipt.raw.json, mask-map.json, family and label.

For the three PyPI records it projects only release/wheel identity fields;
complete native source JSON/README bytes move to private horizon vendor
custody. Those outputs are labelled projected_native_source_capture and
cannot substitute for E2E results. For other native output it applies the
byte masker. Public metadata is deterministically reserialized with a new
output hash, explicit source-specific declared-input corrections and the
publication-transform label; original commands/rc/times stay unchanged.
That correction is labelled and never presented as unchanged native metadata.

The masker additionally recognizes known scratch-root partial prefixes only
when followed by an explicit shortened-repr/ellipsis marker. A neutral token
avoids guessing the original root when a shared prefix is shortened. An
unrelated-path control prevents broad prefix matching. Raw output is never
reconstructed. New native checks: 9 masker, 2 custody, 4 projection cases;
the fail-first truncated-prefix run remains a real failure in custody.
The private co-op reproduction must also scan full and truncated scratch
fragments; home/user/host token checks alone missed the original repr fragment.

The small correction received co-op private PASS: 114/114 derivatives reproduce
through public_pair, all 115 output bindings and private integrity rows match,
and 9 masker / 2 custody / 4 projection cases pass. Expanded scratch-fragment,
pytest-temporary-login, UUID-shaped, user/host scans are clear. Full source
custody is horizon PR8, cited by name rather than private commit fingerprint.
