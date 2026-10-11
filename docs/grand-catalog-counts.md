# Grand catalog counts

`catalogs/landscape/grand-catalog-counts.json` is a deterministic projection of
the retained grand catalog for final-stack and W1b consumers. It records source
dispositions; a row's presence does not install, adopt or accept a repository.

The standalone producer is `scripts/grand_catalog_counts.py`. Both commands
are host-only, using the existing `architecture_g5_asset` source-policy grant:

```sh
python3 scripts/grand_catalog_counts.py --write
python3 scripts/grand_catalog_counts.py --check
```

The asset defaults to `_FINAL_ASSET` under
`~/.local/state/native-agent-stack`. `--state-root` and `--asset` can select an
equivalent retained location inside the existing policy; neither adds a grant.
CI reads the committed snapshot and its evidence binding. It does not need the
host archive or run either producer mode against private state. The unit tests
use temporary roots and synthetic archives.

The existing architecture supplement policy excludes this derived file before
content access. It introduces no new grant and does not treat counts as candidate
or layer source records; direct W4/W1b consumers retain their own contracts.

The native reader is `tools/local-pages/architecture_sources.py:261-319` at
`seathatflowsinourveins/native-agent-stack@8bffa2c41692ef483e91b68e3b15aeb331423d2c`.
Its optional record callback lets the exporter count every compact row, even
when the architecture page has no matching layer. Its existing bounded JSON
and tar/zstd streaming path reads only `compact/rows.json`; no archive member is
extracted to disk. The producer compares the archive size/hash, member hash,
total rows, disposition totals and layer totals before writing anything.
The named host archive is the resealed asset pinned in
`evidence/artifacts/g5-start-closure-1-20261009/class-gates.json#/asset`; its member
hash is that receipt's `original_rows_sha256`. The older archive metadata in
`catalogs/landscape/grand-catalog-20261008.json` is historical and stays intact.
That catalog still supplies the independent total-row/disposition expectations.
Its older `by_slot` values are historical: per-layer counts are recomputed from
the pinned host member and reconcile to its total, rather than copying that view.

The schema version is 1:

- `source` contains the committed source catalog and asset-binding receipt
  with their SHA256 hashes, asset SHA256
  and byte size, compact member name and its SHA256. It contains no host path
  or filesystem timestamp.
- `counts.rows` counts compact records, including repeated repository entries.
- `counts.by_disposition` includes all six source dispositions:
  `PENDING`, `WATCH`, `TRIAL`, `NO-GAP`, `OUT-OF-SCOPE`, `REJECT`.
- `counts.by_layer` keys are the source row's `slot`. Each contains its row
  count and all six disposition counts. Every source row contributes once.
- `counts.repositories` counts distinct normalized repository identifiers;
  `counts.rows_without_repository` counts documentary entries without one.
- `by_repository` maps a normalized `github.com/owner/repository` to a sorted list of
  **every** disposition observed for that repository. Duplicate rows can
  disagree; the producer preserves the disagreement instead of choosing one.
  W1b can distinguish an indexed PENDING candidate from an untracked repository
  by membership and by whether `PENDING` is in that repository's list.
  Keys use the native `host_receipts.normalize_repository` identity used by
  final-stack, after the reader has established an actual repository identifier.

Keys and disposition lists are sorted, and no generation timestamp is stored.
`--check` regenerates the projection in memory and compares exact bytes. Missing,
changed, unreadable or unapproved assets and reconciliation failures return
nonzero without replacing the previous snapshot. Re-register the snapshot and
changed owned files through `scripts/host_receipts.py::register_file` before
running FULL `python3 scripts/validate.py`.
