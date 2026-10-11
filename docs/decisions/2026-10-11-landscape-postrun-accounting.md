# Explicit completed-attempt accounting and native scratchpad citations

The completed October 10 foundation sweep replayed 106 cached calls and executed twelve approved replacements.
The shipped usage wrapper intentionally cannot choose between two completed children sharing a label. Its actual
run returned exit 1 with two uncovered effort mismatches. Conversion separately refused three worker notes whose
native scratchpad paths included the local session identifier. These are separate boundaries: accounting must
retain every measured attempt, and publication must redact structural local path segments without deleting
unrelated evidence identifiers.

## Primary sources

- Installed [anthropics/claude-code v2.1.296](https://github.com/anthropics/claude-code/releases/tag/v2.1.296),
  verified by `claude --version`, executable SHA-256
  `24972e3bc859fab2b46ed4c1e51f7d6130f06d3bd550811a114640de3370d0de`.
  Embedded source around zero-based byte 228286338 declares the `v2` journal format, `Fo()` indexes results by
  key, `Hr()` canonically serializes cache-relevant options (including model and effort), and `No()` hashes
  previous key, prompt and those options with NUL separators. This is the supported native Workflow resume
  mechanism; this change consumes its independently proved identities rather than implementing a runner.
- The retained, CC-accepted post-run proof has SHA-256
  `07182245d40b737437ec1ee5d433c502f6e750f12166f85720f3647d00fc454d`; its contract has SHA-256
  `b363af4cf1ba6a6070f5d8d64c36c52062444a4c99af84e816c0deba312c4e4e`.
  The proof establishes a byte-equal 221-line original prefix, 106 replays, twelve reruns, nine approved equal
  keys and three dynamic keys recomputed from actual replacement discovery, with result equality. Its limitation
  explicitly delegates actual request effort to `usage_record.py`. The proof is trusted caller input, bound to
  its contract and native journal; the CLI does not establish an independent authority's acceptance by itself.
- The unchanged native usage adapter is the maintained
  [native-agent-stack child-usage.mjs at 8c32a84b246da66e43a6188c973741b09329e223](https://github.com/seathatflowsinourveins/native-agent-stack/blob/8c32a84b246da66e43a6188c973741b09329e223/examples/claude-native/workflows/child-usage.mjs),
  SHA-256 `3e5189342734135e88a2295c1c2152275d9e26c0c7731ed5cbc8905bbccd98a4`.
  Its measured children, effort mismatches, usage and native same-key supersession remain the source data.
- The converter follows the selected checkout's `scripts/validate.py` PRIVATE_CONTENT grammar for a local
  session identifier, `[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}` (case-insensitive). Three actual notes
  (`first/6`, `followups/0`, `followups/6`) cite native `/tmp/claude-*/<project>/<session>/scratchpad/...` paths.
  Existing encoded-project redaction removed the project identifier but left this private session segment.

## Changes and limits

`usage_record.py` accepts all three explicit inputs: `--supersession-proof`, `--supersession-contract` and
`--supersession-journal`. Every supplied pair must match a contract call, a proved rerun, exact native started and
result identities/keys, a common label, and chronological order. The replacement must be complete and measured
at the required effort only. Duplicate identities, chains/cycles, unbound files, non-max replacements and absent
results refuse before writing. Without these inputs, completed repeated labels keep the existing refusal.

Validated originals move intact into `superseded_attempts`, with only `superseded_by` and an explicit reason added.
Aggregate model usage and WebSearch counters are unchanged. Raw tool exit code and raw output hash are preserved.
Transformation provenance retains the proof, contract, journal and processor hashes, exact pair list, covered
findings and original status/reason. Dynamic keys require the proof's `dynamic-recomputed` classification.

The converter redacts the UUID only in a native session scratchpad path under `.claude/projects` or
`/tmp/claude-*`, replacing it with `<session-id>` while preserving the scratch file suffix. It handles strings,
keys and printed summaries through the existing recursive redactor. A bare UUID still refuses publication.
Existing collision and decoded/serialized privacy checks remain enforced before writes.

## Failure-first evidence and current native gate

- A synthetic public CLI fixture reproduces the actual run's shape: 118 complete children, eight previously
  superseded no-result attempts, twelve explicit completed pairs and two mismatches. The old CLI returned exit 1
  with both mismatches, and rejected the proposed explicit operation. After the change the valid fixture exits 0,
  retains 106 children plus twenty superseded attempts, and keeps every aggregate counter and original record.
- The session-path CLI regression initially refused with exit 3 for UUIDs in a key, value and limit. It now passes
  for both native path forms; a bare identifier still refuses with no artifacts.
- Negative fixtures refuse altered proof/contract/journal binding, wrong run/key/label, duplicate pairs, missing
  result evidence, and a replacement measured at `[max, low]` or `[low]`. A dynamic key without recomputation
  evidence refuses without overwriting an existing receipt. These are synthetic checks, not new model runs.

Actual remeasurement corrected a material assumption in the handoff: eleven replacements are max-only, but
`refute-fit:quality-evaluation:followup` replacement **ab5674e67ae285517** has 33 requests at `[max, low]`.
Its original **af1c37c58587a048b** was complete at `[max]`. The replacement loaded property-based-testing;
the installed skill's frontmatter explicitly declares `effort: low`. Requested max opts do not prove that every
subsequent request stayed max. Native transcript SHA-256:
`62261ed5732764aadc3b233b7ba66408005fa643cf033d25827187aab8752325`.

The actual supplied twelve-pair operation therefore **refuses with exit 2, before writing**. No pair, effort,
native journal, source transcript, vote or counter was waived or edited. The complete actual journal hashes to
`849ee99442d1158a33303c68640ffffd8575779c9e16c86f1874c2f024dc824b`. The measured gate and owner ruling request
are retained privately at `tier1/postrun-20261011/effort-gate.json` within the wave's working state.

The repaired converter's actual preview succeeds: thirteen layers, 151 proposals, 53 surviving layer/repository
pairs (52 unique repositories), and all 42 GPT-6 copy comparisons match. It explicitly retains both measured
effort deviations and reopens quality-evaluation. All 52 source reviews and an external merged preview manifest
are prepared. This is evidence processing over retained native results, with no paid calls or new model runs.

README step 11 explicitly waits for the catalog owner's manifest publication; step 12 writes its ledger. Those
owner actions and a clean max-only acceptance are not claimed. A CC ruling is required to choose between retaining
the observed failure and a separately authorized targeted repair plus fresh proof. Judge/refuter remain held.

Alternatives rejected: inferring completed supersession from repeated labels, hiding counters or mismatches,
redacting every UUID indiscriminately, and treating requested max as measured max-only effort. Revisit this choice
only against a future client's primary source and a reproduced run, preserving the full original evidence.
