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
- [Schema validation](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/validators.py#L307), [instance errors](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/validators.py#L348) and [validation](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/jsonschema/validators.py#L448).
- [Supported install](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/README.rst#L76) and [upstream nox tests](https://github.com/python-jsonschema/jsonschema/blob/a7277432b0f7bcd0551f6e589d30457017125df4/noxfile.py#L59).

The installed validator source matches the pinned upstream bytes. The default
unit-test interpreter lacked the package, so the existing hash-pinned CI
requirements now include the validator and its resolved dependencies. No custom
JSON Schema validator is introduced. The repository glue extends the confined
`load`/`safe_file` implementation and evidence registry at main
`9d4c00cd05d79b3fd5074df2e46bacab87ee67ff`.

Shape validation rejects unknown statuses, missing or blank reasons, boolean gap
indices and malformed hash/head lengths. The loader verifies the frozen
crosswalk hash, exact original gap text, layer/index identity, evidence
registration and actual file hashes. A settled entry requires registered passing
GPT and Claude JSON verdicts whose family/head match their references and whose
heads agree. A dissent or missing family cannot earn settlement. Proposed,
residual and blocked entries remain open; residual and blocked records explicitly
retain their category and reason.

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

Hosted CI also reproduced the existing worker gate's stale advisory inventory
expectation after the loader added input reads. The unchanged native
[GateReads implementation](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9d4c00cd05d79b3fd5074df2e46bacab87ee67ff/blueprints/runtime-workers/openhands/resolver/gate_reads.py#L913)
reports exactly eight additional `scripts/component_matrix.py` locations and one
additional dynamic shape, with no other script-count or shape changes. The
existing test now accounts for this measured source delta alongside its already
recorded test-discovery correction. The historical inventory receipt remains
unchanged, and every other script, shape, bounded coverage and enforcement
assertion remains intact. The old assertion failed before this correction.
