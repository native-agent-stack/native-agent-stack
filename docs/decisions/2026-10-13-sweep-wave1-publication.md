# Wave 1 sweep publication: execution-broker and backtesting-engine

This publication retains the two completed 2026-10-13 landscape sweeps through
the existing README Run it steps 8-12. Both feed
catalogs/sota-convergence/manifest-20261013.json, which is final with exactly
these two lanes: both ledger records bind its bytes, so no later wave edits it
(see Corrections). The co-op supplied the completed usage records and retained
each run's raw workflow output, work directory and scope; both runs were
converted again from them with the corrected converter. The publication tree
starts at main 5bab63233ef90260bec4a8ee0cec4f5e4431776c.

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
excerpt records. Each literal appears there as `<public-contact-omitted>`, and
the record's `publication_redaction` states the count. Neither
sweep_common.sanitize nor source_reviews.py produces that marker: it is a
publication-time replacement in those two records only. Reviewed commit/path
and all non-contact observations are unchanged. The original raw workflow and
private working inputs stay out of the repository.

## Primary mechanisms

- native-agent-stack/native-agent-stack at
  3f1a921dd23223e8429ecf2615e3c7242bd2cfc0, unchanged at 5bab63233:
  tools/sota-convergence/landscape-sweep/README.md, Run it steps 8-12;
  recipes/sota-convergence-practice.md, six commands and never-promote rule.
- At the same pins, tools/sota-convergence/build_manifest.py merge_lanes and
  build_manifest preserve lane status/vote/critic evidence without adoption.
- At the same pins, source_reviews.py captures public upstream provenance;
  make_result.py and scripts/saturation_ledger.py bind per-run returns,
  measured child usage, source reviews and the append-only chain.
- Step 8's convert.py carries this publication's three corrections. Each one
  rewrites keys and values through sweep_common.rewrite_strings
  (7dcbe9a58:177-191) and refuses a key collision before writing anything.
- At 5bab63233, scripts/component_matrix.py, scripts/new_host_grand_list.py
  and scripts/final_stack.py regenerate the derived views.
- Installed Git and CPython/unittest execute the native publication/ledger
  checks; no replacement research harness or new dependency is introduced.

Heavy publication and test commands use the E2 idle-class wrapper. Local checks
qualify publication integrity; the two-family PR reads, co-op Codex review and
CC completeness gate remain required before landing.

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
  same four pointers are in main's manifest-20261009.json, and they are not
  changed here.
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

## Follow-ups

- Qualify surviving role-specific candidates only through their retained
  comparison-that-would-overturn and multi-angle convergence. The selected
  NautilusTrader/broker destinations are not upgraded by this sweep.
- Preserve both lane critics, unresolved comparisons, source gaps and any
  retained failure or pin-movement reopening evidence in subsequent waves.
- Waves 2-3 publish without editing manifest-20261013.json. The current tools
  allow one manifest-YYYYMMDD.json per date (scripts/component_matrix.py:91)
  and date a completed sweep by its manifest's checked_at. How the follow-up
  names and dates its manifest is a CC decision for that PR.
