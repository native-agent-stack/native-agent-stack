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
- The original native usage adapter, before the correction below, is the maintained
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
result identities/keys, a common label, and chronological order. An explicit chain must terminate at a complete
child measured at the required effort only; completed intermediate replacements remain retained. Duplicate
identities, cycles, ambiguous same-label terminals, unbound files, non-max terminals and absent
results refuse before writing. Without these inputs, completed repeated labels keep the existing refusal.
The CLI's optional required-effort value cannot weaken a contract that explicitly requires max; that guard
also has a public regression observed failing before the fix.

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

On 2026-10-11T01:33Z the CC authorized ONE targeted max-only replacement of the mixed-effort fit worker and a proof
extension. The prepared script preserves all 118 existing calls, appends only the authorized label after the old
sequence (editing an earlier prompt would also change subsequent chained keys), omits the lower-effort skill
from that call's prompt and bans loading skills declaring effort below max. Offline native-key replay proves
118 cached calls plus exactly one planned appended call. It is a simulation, not a measured repair result.

That authorization requires a completed supersession chain: the original complete max worker points to the mixed
replacement, which then points to the new max-only terminal. A new public CLI regression failed before adding
chain validation and terminal coverage; intermediate completion no longer stops traversal early. Every edge
must be explicit, bound and chronological, and all same-label edges resolve to one max-only terminal.

README step 11 explicitly waits for the catalog owner's manifest publication; step 12 writes its ledger. Those
owner actions and a clean max-only acceptance are not claimed before native repair completion and the extended
effort gate. Judge/refuter remain held for #992; the single landscape repair is the separate explicit CC exception.

Alternatives rejected: inferring completed supersession from repeated labels, hiding counters or mismatches,
redacting every UUID indiscriminately, and treating requested max as measured max-only effort. Revisit this choice
only against a future client's primary source and a reproduced run, preserving the full original evidence.

## Completed native repair and final effort acceptance

The ONE CC-authorized repair completed at 2026-10-11T02:23Z. Re-execution proves all 118 prior completed calls
replayed and only the approved fit call appended. The 245-line prefix is byte-equal; the final journal has exactly
247 lines (one new started/result pair), SHA-256
`4b34a664f56145c3a285b013f6ca2abd2f4c59d257825a49b842c580164efe47`.
The new key is `v2:56c965af13485b93c3a4c1ee72e748f7b17810161d8f9ebf8b442f9642a1077c`, new agent
`aab7e4ff6c231f5ee`, superseding mixed-effort `ab5674e67ae285517`. Its native first prompt matches the approved
prompt, and the replayed result equals the final native result. Extended proof SHA-256:
`4d28bec0326f9493fc278e07291363485582cce924f3bd814c93af5ba8f05f3d`.
The thirteen-pair contract hashes to `89faaeceb995aad15a7069a295e6b38c2d4530fca1431bd726ca662e37ffa2a5`.

The unchanged native usage tool measures the new child as claude-opus-5-5, 42 requests, efforts `[max]`.
`usage_record.py` exits **0**, preserving native raw exit **1**, with 106 active children and 21 superseded
attempts: all 127 native attempts remain. The old mixed child's 33 requests and `[max, low]` effort remain intact
and point to the new max terminal, including in converted `superseded_retained`.

An independent check against a fresh execution of the unchanged native tool exits **0**: every original child
field is preserved, aggregate model/WebSearch counters are identical to native raw output, raw output hash and
exit match, both non-max attempts are covered, and none is uncovered. This checks the input proof graph and native
measurements independently of the wrapper's traversal. Effort-gate receipt SHA-256:
`322f152f72045e454cc6abd5a15a44c2f8a7c0e206e0f7fe2007cf7eff44973a`.
The final usage receipt hashes to `bf6c257a5213960e6cf8a16019fcd6fea7d8ff9282fb1b44834650fe86edf373`.
Native workflow summary counters and full per-child usage are separate counters; they are preserved separately.

Final conversion exits **0** with thirteen layers, 151 proposals, 53 survivor pairs, all 42 GPT-6 copy checks
matching, and no effort deviations, retained failures or reopened layers. The survivor set is unchanged. The
supported manifest builder and source-review tool have produced the final external manifest and 52 refreshed
source reviews. The supported `make_result.check_usage` accepts the actual final usage/returns/layer data.
These are real retained-run integrations; the 89 focused regressions remain synthetic/local checks.

The template proposal records the lower-effort skill exclusion rule for the next sweep without editing this
run's frozen inputs or upstream skill declarations. Catalog-owner publication, evidence retention/registration
and the final ledger append remain separate README11–12 owner actions. Old blind Claude finals remain excluded
from recording until their post-#993 rerun, and adjudication still waits for #992.

## Review correction: request effort and encoded identifiers

The first GPT read identified three P2 boundaries at `a3d79fd0`: the effort set drops missing request
measurements, percent-encoded session identifiers can survive scratchpad redaction, and two refusal tests
accept an unsupported-option parser error. The correction is one direct-child commit, with no history rewrite.

Primary-source comparison on 2026-10-11 found the maintained repository's `main` and pinned
`8c32a84b246da66e43a6188c973741b09329e223` adapter identical (Git blob
`be2c895785bc543104778a366ecc414f57d1b171`, SHA-256 above). `summarizeChild` at that pin, lines 3304–3322,
deduplicates usage-bearing assistant messages, then computes `efforts` with `filter(Boolean)`. Its offline
fixture interface at `test-child-usage.mjs:14` uses assistant rows with top-level effort and provider counters.
The correction extends that maintained adapter directly: `unknown_effort_requests` counts absent, blank or
non-string effort on the same deduplicated requests. Existing usage counters and request totals do not change.
The wrapper, converter and result builder require zero affirmatively measured unknown requests and a positive
terminal request count. Completed originals with missing effort measurements refuse; interrupted zero-request
attempts retain their separate zero-request treatment. Native raw bytes/hash and counters remain retained.

For URL representations, installed CPython **3.13.16** supplies
[`urllib.parse.unquote`](https://docs.python.org/3.13/library/urllib.parse.html#urllib.parse.unquote), whose
[pinned source](https://github.com/python/cpython/blob/v3.13.16/Lib/urllib/parse.py) decodes percent escapes.
The converter applies it until stable to a separate validation view of every string and key, including
summaries and limits. Any remaining decoded private identifier refuses before writes or stdout. The emitted
citations remain unchanged by decoding; ordinary literal native scratchpad citations still retain their suffix.
Both redaction collisions and collisions in decoded validation keys refuse.

Failure-first evidence is retained in the private `pr995-review-fix-20261011` packet. Final tests transplanted
onto genuine detached `a3d79fd0` production run four public runtime tests with **25 failing subtests**, including
both actual adapter-produced unknown-effort cases and fifteen encoded-publication cases. The two strengthened
refusal tests transplanted onto pre-feature `eb31d233` run two tests with **10 failing subtests**: diagnostics
must name the actual bound-max or identity/hash/effort refusal, so unsupported options no longer pass. A valid
max-input control also succeeds at the correction. These are offline synthetic/local integration results.

### Actual retained-run correction: publication held

Read-only remeasurement of the retained native run, using the supported updated adapter and the unchanged
thirteen-pair proof/contract/journal, preserves all **127** attempt identities, **106 active +21 superseded**,
all original child fields, and identical aggregate model/WebSearch counters. It newly exposes **8 unknown
request efforts in 8 interrupted superseded attempts**. None of the covering terminals has unknown effort;
the two mixed-effort completed attempts remain covered. The wrapper now correctly returns **1**, preserving
native raw **1**, and the eight unknown attempts remain uncovered. This supersedes the earlier clean-effort
acceptance in this decision for publication purposes; the historical receipts remain intact.

The new private raw output is SHA-256 `9c63e6f2cd1d2d4969659922b8672647bc24d86a69d9f21bb104adac951b76e2`;
the final corrected usage receipt is SHA-256 `c07326d18ac7a9758ff5c21b729aacd05a2ecac8b566eb68a7a97011c1698dcd`.
README11–12 publication and ledger registration must account for these uncovered attempts before using a
clean-effort claim. No additional model call, native journal change, manual measurement fill, catalog edit or
ledger append was performed. The frozen owner handoff remains historical, not silently replaced.

Final correction validation: all **304** tests in `tests.test_landscape_postrun`,
`tests.test_landscape_sweep_harness`, and `tests.test_evidence_manifest` pass (three optional skips: context-mode
JavaScript security integration, shellcheck, Bash 3.2). The maintained adapter's supported
`node examples/claude-native/workflows/test-child-usage.mjs` command passes **222/222** offline checks.
The correction adapter SHA-256 is `8e37a032b189467c7f8ddba81adb3b6fe06e7064ca4b61123852533d1d711caa`.
