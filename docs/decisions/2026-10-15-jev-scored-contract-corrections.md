# Jev scored-content, ECE and partial-receipt corrections

The three adjudicated local P2s from #1150 affect the meaning of a SCORED
receipt. This follow-up corrects them together on main. Trading-cc retains
acceptance; its research run waits for this PR and both CC/GPT delta reads.
This build performs no scored, paid, model or network-provider invocation.

## Changes and source contract

1. SCORED preregistration compares exact ordered id/text/label content for
   original training, excluded-final training and scored rows against the nine
   dataset-derived pins already published in
   `evidence/artifacts/jev-trading-build-20261015/frozen-source-check.json`.
   Source pins and ID hashes remain necessary, but ID equality cannot authorize
   a relabelled or preprocessed benchmark. All comparisons precede dispatch.
2. Point and bootstrapped ECE again use sorted-label argmax correctness, with
   maximum probability as confidence. The returned choice still supplies the
   prediction for other statistics. The authoritative private citation is
   `us-equities-trading@a91a4cdd29e8aedab9f0b9784252bdb2bb60ae62:docs/decisions/2026-10-11-jev-harness-case-sets.md:233–235`.
   This restores the decision; it does not amend it. ADDENDUM-01 A4 preserves
   the original metrics. The earlier accepted-choice ECE change is superseded.
3. The Haiku budget reference exists before protected execution and is
   configured after workload validation, before dispatch. Its single snapshot
   implementation now feeds both complete reports and every final receipt.
   Partial receipts retain known spend, reservations, upper bound, workload,
   cap, uncertain calls and an open interrupted-call reservation. An early
   refusal with no configured workload records `NOT_RUN`. Unknown charges stay
   held for the owning workload ledger to reconcile.

The existing numeric implementations remain NumPy 2.5.3, SciPy 1.18.1 and
scikit-learn 1.9.1 under P1's scoring lock. NumPy argmax selects the first maximum
in the explicitly sorted columns; the existing 10,000-draw paired bootstrap
uses the same correctness contributions. No estimator, transport, spending cap,
library selection or trading admission rule changes.

The sealed sources are cited by name and path only:

- `coordination/trading-cc/specs/jev-trading-20261015/JEV-FEATURE-LIST-v1.md`:
  research seed questions and separate admission; no J-set execution here.
- `coordination/trading-cc/specs/jev-trading-20261015/JEV-HARNESS-ADDENDUM-01.md`:
  A2 parity, A3 comparison and A4 unchanged case/metric/receipt contract.

No unpublished source-file verification digest is exported. The content pins
are existing published public-dataset derivations, reproduced from the retained
source bytes; they are not hashes of the private authority documents.

## Evidence and supersession

The new evidence is
`evidence/artifacts/jev-trading-scored-contract-20261015/`. RED tests ran before
production changes: unchanged-ID content mutations were accepted, tied ECE
returned 0.6 instead of 0.4, its paired interval returned 0.4 instead of 0.2,
and interrupted/early-failure receipts omitted Haiku state. The real frozen
TFN source witness also reproduced acceptance of a changed scored label, with
zero transport calls. GREEN repeats the valid frozen build and rejects the
mutation; synthetic interruption preserves two completed charges and the third
call's open reservation. Named mutations cover every new guard and the reversed
ECE behavior.

The original build and its receipts remain historical evidence at their stated
source revisions. This correction supersedes their ECE tie interpretation and
partial-receipt/content-binding behavior; it does not rewrite those measurements.
The separate trading-question draft remains unsealed in lane state and supplies
no new scored cases or admission in this PR.
