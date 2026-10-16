# model-routes: merging the Claude half with the GPT half

The CC ruled the merge on 2026-10-15 at 19:52Z, as the co-op proposed. It runs only after BOTH halves are sealed:

- this half: `returns.json`, sha256 `498651465682013d9e8c668b0f1aa0c9d936f51c3c7fed6612d80fb71292f5e6`;
- the GPT-family half, PR #1177 at its final reviewed head (the head at opening was `6ecd0e74`). Its returns use the
  harness's GPT-6 role shapes (`gpt6-discover:model-routes`, `gpt6-refute-fit:model-routes`).

## Rules

1. **The 14 carried candidates get three votes** under the harness survival rule: the Claude facts vote and the
   Claude fit vote from this half, and the GPT fit vote from #1177. A carried candidate survives only when none of the
   three votes refutes it. Candidates are matched on the angle-record `id` (`route_identity` in this half's
   `layer-input.json`), not on the shared documentation URL, because several routes share one URL.
2. **Each family's NEW proposals get ONE bounded cross-vote round.** For this half's 5 new proposals, the GPT family
   adds its fit vote. For #1177's new proposals, the Claude facts and Claude fit refuters vote, using the same frozen
   templates (`prompts_sha256` `f8263a7b7cce54784278ac909ecb1ab5e83376411891b3e4880fd134df516a7d`) and stage
   scripts as this half. A proposal both families made counts once, and the cross-vote covers only the missing
   family's votes.
3. **Missing votes count as refuted** (the convert.py rule), and a proposal refuted only by absence stays marked "not
   adjudicated".
4. **The merged result supports TRIAL labels on NativeHorizonNY only.** It is not a ledger-countable sweep and never
   FINAL. The ledger-countable sweep is the documented two-family launch after the layer is registered (PR #1179),
   with this merge and both halves as recorded PRIOR evidence, not its verdict.
5. **The critic's four missed classes** (RUN-RECORD.md) go to the registered two-family sweep as seeds, or to the
   cross-vote round if the CC widens it.

## Output

`evidence/artifacts/model-routes-sweep-merge-20261015/` holds:

- the merged returns, in the recipe's returns shape;
- the cross-vote round's usage records;
- one source review per merged survivor (`source_reviews.py`), as the recipe requires
  (`recipes/saturation-sweep.md:99`; `--append` refuses a survivor without a registered source review, `:174-175`).
  `source_reviews.py` reviews GitHub repositories, Hugging Face model repositories and skill survivors, so it cannot
  review a vendor-hosted route. PROPOSAL, not a recipe step: such a route carries its dated vendor-document capture in
  place of the review. The recipe does not provide for this, so it needs a CC ruling before the merge uses it; the
  merged result is not ledger-countable (rule 4);
- a TRIAL-label table for the NativeHorizonNY install stage.

The merge is a co-op task that starts when both halves are sealed. No date gates it.
