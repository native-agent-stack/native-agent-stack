# Dated advisory gate deltas

This is monitoring accounting. A delta grants no worker permission or
execution authority. The native reader is `GitTree` and
`derive_ci_protected` in `resolver/push_gate.py`; the owning integration
test is `RepositoryWorkflowTests.test_advisory_baseline_and_explicit_categories_stay_bounded_on_this_repository`.

## Append a dated observation

`unclassified-gate-read-deltas.json` is a schema-version-1 index. Its
`entries` array is oldest to newest by UTC ISO date. Each entry names a
delta JSON file in this evidence directory:

```json
{
  "date": "2026-10-11",
  "path": "unclassified-gate-reads-20261011-skill-use-delta.json"
}
```

Append a new entry and a new delta file when a reviewed PR changes the
advisory inventory. Equal dates are permitted; append order breaks that
tie. Paths are unique evidence-directory basenames, and the entry date
must equal the delta's date. The last entry is the current observation.

Keep all earlier snapshots and delta files unchanged, including the
baseline used by the 2026-10-11 skill-use delta. A different baseline
snapshot belongs in a new dated file. Point the new delta's
`baseline_path` at that file and record its measured `baseline_sha256`.
The checker validates each historical baseline against its own recorded
hash, rather than rebinding every historical delta to the latest bytes.

## Derive the new delta

Use the existing native `patch_policy.GitTree(root, source_commit)` and
`push_gate.derive_ci_protected(tree)` at the reviewed source commit.
Compare its `advisory.unclassified` and `unclassified_shapes` with the
chosen immutable baseline:

- Record `derived_count` from the native result.
- Derive `added_by_script` and `removed_by_script` from script counters.
- Derive `added_shapes` and `removed_shapes` as shape multiplicity deltas.
- Record native location differences and their monitoring-only
  `read_classifications`, retaining `permission_change: false`.
- Bind the baseline path/hash and measured `source_commit`; do not type
  a count copied from an earlier head.

The newest delta is checked against the current native derivation with
the existing exact script, shape, total, classification and protection
assertions. Older deltas retain their dated baseline bindings. A changed
newest count or rewritten historical baseline fails the regression.

Run the owning module before publishing:

```sh
python3 -m unittest tests.test_runtime_worker_openhands_push_gate
python3 scripts/validate.py
```

During the protected paper window, multi-module suites still require the
co-op's suite release and the idle-class wrapper.

## Mechanism and correction class

The class is **dated-record/live-state coupling**. Dated grant counts use
their record's explicit Git inventory pin. Current advisory monitoring
uses the newest dated delta, while retaining earlier baseline bytes.

Primary sources: existing native gate derivation at
`native-agent-stack@8b1ef0c37e2f523aa84d2c75960540f45e74e814`,
`blueprints/runtime-workers/openhands/resolver/push_gate.py:derive_ci_protected`;
installed Git 2.53.0,
`git/git@67ad42147a7acc2af6074753ebd03d904476118f`,
`Documentation/git-ls-tree.adoc:44-61` and
`Documentation/revisions.adoc:217-220` for pinned tree/blob inputs.
The index uses the existing CPython JSON parser and `datetime.date`
ordering, with no new runtime dependency or replacement inventory policy.
Installed CPython 3.13.16 source pin:
`python/cpython@cbc944f4bc59639a444dd971c737788ba2283a91`,
`Doc/library/json.rst:356` (`loads`) and
`Doc/library/datetime.rst:555` (`date.fromisoformat`). Evidence paths are
resolved before containment checks, using the existing `pathlib` API.

