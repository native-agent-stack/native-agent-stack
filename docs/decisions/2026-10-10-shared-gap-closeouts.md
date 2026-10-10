# Adopt one schema and loader for retained gap closeouts

The historical component crosswalk can continue to list an executable gap after
later receipts address it. Per-layer loaders would apply different review and
evidence rules. Use one Draft 2020-12 schema and one loader in
`scripts/component_matrix.py`, with dated per-layer records under
`catalogs/landscape/gap-closeouts/`. The loader-only change credits no layer
closures and preserves main's current counts and the frozen crosswalk bytes.

The supported validator is `jsonschema==4.26.0`, already pinned in the retained
Lumibot lock at
`blueprints/us-equities/engine-trials/spy-one-zero-20260926/lumibot/lockcheck/lumibot.lock`.
The official wheel SHA-256 is
`d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce`.
The release tag resolves to source commit
`a7277432b0f7bcd0551f6e589d30457017125df4`:

- [Draft202012Validator](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/validators.py#L812).
- [Schema validation](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/validators.py#L307), [instance errors](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/validators.py#L349) and [validation](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/validators.py#L448).
- [Supported install](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/README.rst#L76) and [upstream nox tests](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/noxfile.py#L59).

The installed validator source matches the pinned upstream bytes. The default
unit-test interpreter lacked the package, so the existing hash-pinned CI
requirements now include the validator and its resolved dependencies. No custom
JSON Schema validator is introduced. The repository glue extends the confined
`load`/`safe_file` implementation and evidence registry at main
`9d4c00cd05d79b3fd5074df2e46bacab87ee67ff`.

The installed 4.26.0 distribution declares `Requires-Python: >=3.10`, also
recorded in its pinned upstream
[package metadata](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/pyproject.toml).
The broader recording-script floor remains Python 3.9 for the existing no-closeout
path; processing a recorded closeout requires Python 3.10 or later and the pinned
validator. Hosts use the selected Python line before adding such records. The
catalog-freshness suite uses Python 3.13 and installs the hash-pinned CI set before
its full discovery. The closure fixture module follows the existing sampler's
module-level SkipTest when jsonschema is absent; installed-library controls run
without that skip. The retiring validate-macos job is outside this change.

Shape validation rejects unknown statuses, missing or blank reasons, boolean gap
indices and malformed hash/head lengths. The loader verifies the frozen
crosswalk hash, exact original gap text, layer/index identity, evidence
registration and actual file hashes. A settled entry requires registered passing
GPT and Claude JSON verdicts whose family/head match their references and whose
heads agree. A dissent or missing family cannot earn settlement. Proposed,
residual and blocked entries need the same two-family credit to change category
or counts. An unreviewed residual/blocked entry records as proposed and preserves
the prior numeric disposition, including an earlier reviewed closeout. Every
entry retains its reason and requested disposition in its source file.

The hash registry consumes `manifests/evidence.json`'s `files` only. Its real
`receipts` rows hold id/kind/path/component/claim/limitation metadata without hash
or byte fields; the existing validator requires their paths to be hashed files.
The earlier synthetic hash-bearing receipt fixture did not model this contract.
The corrected real-shape fixture reproduces that failure and verifies files-only
registration. No metadata row can override a file's binding.

Four checks failed before the implementation: unregistered evidence, missing
reason and unknown status were silently ignored, and the public matrix build
still counted the fixture gap (`1 != 0`). These are fixture observations, distinct
from any vendor runtime qualification. Main's existing data has no closeout
records, so the loader must leave its counts and generated outputs unchanged.
Retained native validation receipts and the PR description record the final
touched-module, generator and FULL-validator results.

The alternatives were one loader per layer or a replacement schema validator.
Neither has evidence of a missing upstream validation feature. A demonstrated
unsupported vendor path, a native validation mismatch, or review credit that can
be earned without both retained independent reports would overturn this choice.
Runtime qualification, host acceptance, broker authority and production-data
boundaries continue to require their own evidence.

Hosted CI also reproduced a stale worker advisory inventory. Following the
maintained refresh in main commit `89e89852161d8157e464f4bd07c2b5c747ad4706`,
the dated snapshot is regenerated through the unchanged native
[GateReads derivation](https://github.com/seathatflowsinourveins/native-agent-stack/blob/03a986ed637349403658f23da694c1833527819d/blueprints/runtime-workers/openhands/resolver/gate_reads.py#L913)
for the current candidate source. The test compares directly with that snapshot;
it contains no hard-coded location/shape increments. The prior snapshot hash is
retained with the correction evidence. Worker policy, bounded coverage and
enforcement assertions remain intact, and the worker lane acknowledges the
refreshed baseline before publication.
