# Wave 1 sweep publication: execution-broker and backtesting-engine

This publication retains the two completed 2026-10-13 landscape sweeps through
the existing README Run it steps 8-12. Both feed
catalogs/sota-convergence/manifest-20261013.json, which is final with exactly
these two lanes: both ledger records bind its bytes, so no later wave edits it
(see Corrections). The co-op supplied the completed usage records and retained
each run's raw workflow output, work directory and scope; both runs were
converted again from them with the corrected converter. The publication tree
starts at main 5bab63233ef90260bec4a8ee0cec4f5e4431776c. Line references in this
record are at that commit unless they name another revision.

Execution-broker run wf_ba4e1e02-e9e has 14 candidate-layer proposals, 6 surviving
and 8 refuted. Backtesting-engine run wf_118bc2d7-5b3 has 15, 4 surviving and
11 refuted. Both converted lane records, completeness critics and lost-worker
state are merged without replacing a lane's contribution. Each sweep has its
own retained returns, sanitized child usage, RESULT and upstream source reviews.
The shared working inputs were byte-identical across the two supplied runs.

The native manifest builder preserves candidate dispositions. Refutation
survival does not promote a repository into an installed/default arm. Source
reviews record public upstream commit/README observations; they are not upstream
install/test/E2E or broker acceptance. No selected catalog decision, runtime
pin, broker authority or FINAL claim is changed here.

The native ledger appends execution-broker and then backtesting-engine using
their separate RESULT records and common manifest reference. Original sweeps,
votes and policy are retained. Current source bindings and the derived final
stack, component matrix and new-host grand list are refreshed through the
owning tools. Every new retained file and every changed evidence path has its
native registration; completeness is checked by path and current byte hash
before publication.

Each RESULT also retains the frozen report's platform-profile reopening trigger;
backtesting-engine retains its NautilusTrader pin-movement trigger. These keep
the reset evidence after a current flag clears. The final ledger is rebuilt
from the untouched base plus these two local publication records; no published
history is rewritten.

Public upstream contact strings are omitted from two NautilusTrader README
excerpt records. source_reviews.py writes each one as `<public-contact-omitted>`
under the sweep publication email rule: the private-email rule that convert.py's
native publication scan applies (scripts/host_name_scan.py:159-167, with that
scanner's boundary filter at :144-150). Each record's `publication_redaction`
states the count and names the rule. Run over the NautilusTrader README at the
reviewed commit, the producer reproduces both records byte for byte; the other
eight reviews contain no contact address and are unchanged. Reviewed commit/path
and all non-contact observations are unchanged. The original raw workflow and
private working inputs stay out of the repository.

## Primary mechanisms

- native-agent-stack/native-agent-stack at
  3f1a921dd23223e8429ecf2615e3c7242bd2cfc0, unchanged at 5bab63233:
  tools/sota-convergence/landscape-sweep/README.md, Run it steps 8-12;
  recipes/sota-convergence-practice.md, six commands and never-promote rule.
- At the same pins, tools/sota-convergence/build_manifest.py merge_lanes and
  build_manifest preserve lane status/vote/critic evidence without adoption.
- At the same pins, make_result.py and scripts/saturation_ledger.py bind per-run
  returns, measured child usage, source reviews and the append-only chain.
  source_reviews.py captures public upstream provenance; this publication adds
  its contact omission (above).
- Step 8's convert.py carries this publication's corrections. Each one rewrites
  keys and values through sweep_common.rewrite_strings (7dcbe9a58:177-191) and
  refuses a key collision before writing anything.
- At 5bab63233, scripts/component_matrix.py, scripts/new_host_grand_list.py
  and scripts/final_stack.py regenerate the derived views.
- Installed Git and CPython/unittest execute the native publication/ledger
  checks; no replacement research harness or new dependency is introduced.

Local checks qualify publication integrity; the two-family PR reads, co-op Codex
review and CC completeness gate remain required before landing.

## Corrections after the 2026-10-13 reads (2026-10-16)

- **Dated-manifest binding (the CC's P2-1 and the local review's P2).** Each
  completed record binds manifest_sha256 to the whole manifest file
  (scripts/saturation_ledger.py:945), a completed sweep's date must equal the
  manifest's checked_at (:950), and the ledger is append-only (:1320). The CC's
  2026-10-16 ruling narrows this publication to wave 1, so this manifest was
  finished before both appends and stays final. The earlier plan for later
  waves to add lanes to it is withdrawn. Waves 2-3 follow in one later PR,
  which cannot edit this manifest (see Follow-ups).
- **Host installation label (the CC's P2-2).** The converter writes the label
  as `<host-installation>` (convert.py host_installation_names,
  redact_host_installation). The two execution-broker returns lines carry the
  marker now, and no label remains in the publication.
- **Former-owner repository URL (the CC's P2-3).** The converter rewrites this
  repository's former-owner GitHub, API and pinned-locator spellings to
  native-agent-stack/native-agent-stack (normalize_repository_urls). That
  fixes the four lines in the two returns files. The manifest's four
  occurrences are baseline rows that build_manifest copies from
  catalogs/us-equities/engines-strategies.json:1787 and
  tools/sota-convergence/reconciliations-20260922.json:56, :96 and :104. The
  same four pointers are in main's manifest-20261009.json. They are left to
  #1202, the follow-up catalog PR the CC ruled on 2026-10-16, which changes
  main's catalog rows; this dated manifest keeps its historical bytes.
- **Per-call prompt commitments (GPT read P1).** The converter drops every
  per-call `prompt_sha256` field and any copy or 7+-hex prefix of one before
  writing (omit_private_prompt_commitments). The eight published values are
  gone. The frozen-template `prompts_sha256` and the schema digests remain:
  both authenticate public preimages.
- **New-host grand list (GPT read P2).** `scripts/new_host_grand_list.py
  --write` regenerated both outputs after the matrix refresh.
- **Critic merge rule (CC P3).** The merged lanes input concatenates lanes and
  lost in execution-broker, backtesting-engine order. It keeps each lane's
  critic whole under critic.by_lane and concatenates their followup_layers and
  general lists, so the merged lists can be recomputed from critic.by_lane.
  method.review's "one completeness critic" is the builder's fixed wording;
  this manifest carries one critic per lane.

## Corrections after the 2026-10-16 reads (round 2)

The CC's full read and the co-op's local review at
1e5ceb9155207e91bca1bb443a943baea97bff43 found the round-1 rewrites could still
damage data no wave-1 file contains. Converting both runs again with the round-2
converter gives the same four documents per lane, byte for byte.

- **Bounded installation labels (local review P2, CC-confirmed).** A label is
  rewritten only where scripts/host_name_scan.py's native boundary filter
  (:144-150) would report it: no Unicode letter or number on either side. A
  "dev" label no longer rewrites `effort_deviations` or `developit`. A label
  inside a URL refuses publication, because rewriting it can corrupt a public
  reference and keeping it can publish a private one. The scanner's synthetic
  override (:50-56) replaces both label sources, as it replaces every host
  source in host_names.
- **V2 identity bindings (local review P2, CC-confirmed).** convert_v2 binds
  candidate_key and repository by field_sha256 before publication. The
  repository-transfer rewrite now applies to V1 publications only. After every
  rewrite, each V2 discovery, source field, layer, lane copy and survivor must
  still recompute with saturation_ledger.v2_field_sha256, or publication refuses.
- **Contact omission in the producer (CC P2-C).** source_reviews.py now emits the
  omission and `publication_redaction` itself (above); before, both records were
  edited by hand after the producer ran.
- **Bounded prompt-commitment rewrite (CC P3).** Only a whole hex run that is a
  copy of a private value is rewritten. A public digest that shares a 7-hex
  prefix is kept. A copy glued inside another hex run refuses publication.
- **Reference endings (CC P3).** The transfer rewrite also matches before a
  sentence-ending period (URL and plain forms), and before "#", "/", a backtick
  or a quote after the plain slug.

## Follow-ups

- Qualify surviving role-specific candidates only through their retained
  comparison-that-would-overturn and multi-angle convergence. The selected
  NautilusTrader/broker destinations are not upgraded by this sweep.
- Preserve both lane critics, unresolved comparisons, source gaps and any
  retained failure or pin-movement reopening evidence in subsequent waves.
- Waves 2-3 publish under a new dated manifest, as the CC ruled on 2026-10-16
  (03:09Z, D2), and do not edit manifest-20261013.json.
- A V2 sweep can only canonicalize this repository's former-owner alias where
  its field is frozen (build_inputs.py), before field_sha256 binds it.

## Limitations

- The repository holds no capture of upstream README bytes, release binaries,
  attestation responses, repository metadata or the 2026-10-13 transfer API
  response. Claims that rest on them are source observations, not verified
  captures. The round-2 reproduction re-read the NautilusTrader README at its
  reviewed commit through the GitHub API; that read is not retained here.
- Earlier records that cite lines of files this publication regenerates or
  edits, such as the component matrix, the new-host grand list and convert.py,
  keep their meaning at their own revisions and are not edited here.
