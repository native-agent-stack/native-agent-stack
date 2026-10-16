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
