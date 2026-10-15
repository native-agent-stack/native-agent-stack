# Follow-up to the October 15 model-currency incident

Base: `929bc3c3f3b6d1f890279ff14d3f500e2d4db592`, the landed #1124.
Read date: 2026-10-15 UTC. Scope: correct the public regression receipt,
retain primary-source review material and fix adjacent test portability.
No selector, model pin, package selection, schema, production behavior or age
policy changes. This record supersedes the inaccurate receipt explanation in
the original decision; its source-review judgments and measured results remain
separate from unperformed model-quality or runtime acceptance.

## Regression record correction

The [corrected receipt](2026-10-15-model-currency-landscape-check.md#haiku-correction-regression-receipt-2026-10-15)
now distinguishes the original successor-only test from the shipped extended
test. The latter **fails on f691e5ce**, at its owner assertion, and passes the
final cc271846 row. A fresh offline reproduction loads the shipped test while
substituting exact f691e5ce inventory bytes in memory; the file and clock remain
unchanged. The receipt enumerates the added owner, record, paired check, legacy,
retirement floor and notice assertions. This is a correction to the report,
not a test weakening or a claim that f691 passed the final test.

## Primary-source packet and pins

[Capture index](model-currency-20261015-sources/captures.json) records all 44
distinct primary source URLs cited by the nine final landscape checks, plus
three supplemental exact source locations: **47 retained HTTP responses**.
Each entry binds the read date, public URL, retrieval representation, exact
raw-byte SHA256 and byte count. Selected exact line/JSON-pointer excerpts are
included for review. The unmodified complete responses are retained outside Git
at `/var/tmp/currency-pr1124-source-captures-20261015/source-NN.raw`; `INDEX.json`
beside them repeats their bindings for co-op review-packet attachment. These
are newly acquired October 15 captures, not a claim to reconstruct the bytes of
an earlier unretained page read. HTML pages may use a vendor Markdown endpoint,
publisher searches use the public API, and package pages use official PyPI JSON;
the index preserves both cited and retrieved URLs explicitly.

Exact qmd source `93d211f9ef4a869a9aed0d075ca767dda552627f`, MinerU registry
`b7f3dd0c5f6e6d66a298239ffd02b328b873918e` and Magika changelog
`b1909890d4477d34381ce12b31882e9a197706d8` are captured at their immutable
raw GitHub locators (capture6/19/34). No other lane's mirror inventory was edited;
the source packet supplies the previously missing exact bytes for review.

CC FULL P3-3/P3-4 are documented here under the requested docs/tests-only scope:

| Role | Exact primary source read | Disposition |
| --- | --- | --- |
| Smaller maintainer query-expansion candidate | [tobil/qmd-query-expansion-0.6B-gguf at edddacb0ae2c1f70524b6af7c3849826897177a9](https://huggingface.co/tobil/qmd-query-expansion-0.6B-gguf/blob/edddacb0ae2c1f70524b6af7c3849826897177a9/README.md) | Explicit newer candidate in this source supplement: GGUF, lex/vec/hyde task, Qwen3-0.6B base. No same-query-set comparison to the selected 1.7B was run; retain it as a quality/latency comparison lead. A future catalog refresh should join this record into newer_candidates rather than infer it was already in that array. |
| Official MinerU base card | [OpenDataLab card at 08aaea840498d49ce16247b6263196cf02814885](https://huggingface.co/opendatalab/MinerU2.5-Pro-2605-1.2B/blob/08aaea840498d49ce16247b6263196cf02814885/README.md) | Immutable replacement for the earlier raw/main locator in source review. No selected GGUF/mmproj change. |

Captures45/46 retain those exact cards. The old inventory raw/main URLs remain
historical discovery links; this supplement is the exact-pin citation for this
review. Complete capture availability does not qualify a candidate's measured
performance or establish all-world landscape completeness.

## Headroom correction regression

[Vendor assignment fixture](model-currency-20261015-sources/headroom-pins.json)
retains exact code and line locators from both 0.40.0 and 0.41.0 source tags.
Its source-body hashes join capture29/30/31/47. The offline test
`ModelCurrencyTests.test_headroom_041_correction_keeps_vendor_weight_and_tokenizer_pins`
parses those assignments using Python AST, compares the whole HF_MODEL_ID and
_PINNED_REVISIONS values between the two releases, then joins the independent
vendor mappings to the actual selected Kompress and tokenizer rows. It also
guards the new release observation and explicit stale-package follow-up.
It imports no vendor code and performs no download, install or model call.

## Notice-test path length

The adjacent collector test now exercises ordinary and deliberately long
permitted checkout paths. It asserts the actual 160-character summary from the
durable due-file, its runnable details command, the exact durable stale count,
and the collector's nonzero result. It does not require an untruncated human
count label when space is reserved for a long command. Production
`scripts/currency_due.py` remains unchanged. The terminal's optional
`(wrote ...)` suffix is outside summary_line and is not mistaken for a violation
of the notice limit.

## Historical locator correction

The retained [cross-family review](../../evidence/artifacts/eval-install-repairs-20260926/gpt6-cross-family-review.md)
was run in an unmerged worktree, as its original README records. Its original
`manifests/evidence.json:29554` is **not** a valid locator for the receipt/matrix
claim at the archived final PR head. Checked exact PR317 head
`4c7314fc946018bdb041edb8d263cf077382ad7c` (fetched explicitly): line29554 is an
unrelated mcporter npm-install entry. At merged publication commit
`bfa87b911c39808df0d9b086cb336741638a0ebc`, line29554 is a closing delimiter.
Therefore do not relabel either as the original pre-repair location.

The reproducible historical receipt-registration locators at exact PR317 head
are [inspect-ai path at30689](https://github.com/native-agent-stack/native-agent-stack/blob/4c7314fc946018bdb041edb8d263cf077382ad7c/manifests/evidence.json#L30689)
and [promptfoo path at30829](https://github.com/native-agent-stack/native-agent-stack/blob/4c7314fc946018bdb041edb8d263cf077382ad7c/manifests/evidence.json#L30829).
Those stable paths identify the original receipts; the final PR body separately
records repaired `-2` receipts and regenerated matrices. The original ephemeral
pre-repair commit is not identified in the retained review, so its matrix-failure
claim remains historical report evidence, not a newly reproduced failure at the
repaired head. This correction resolves use of the misleading numerical locator
without changing the immutable historical review or inventing its missing pin.

## Lifecycle assertions and parity failure

The Haiku test's retirement-floor/notice strings bind a dated observed fact,
not an eternal vendor promise. On the next sourced refresh, update that row and
its observation-specific regression deliberately if the primary source changes;
never retain false lifecycle text merely to pass a test. The migration record
now says explicitly that failed parity blocks application, is recorded for CC
review and reopens the comparison. A later Haiku successor also reopens it;
neither case silently routes a heavier line.

## Headroom package review

Owner: currency lane prepares the package source/compatibility review; CC reviews
and applies. Track the stale `packages` row0.40.0 against published0.41.0 separately
from model currency. The model pin correction is verified by source equality;
no package install, selected package update or runtime-extra qualification is
claimed here. The source packet includes official release metadata and both
versions' source assignments. Reopen on changed mappings or failed compatibility.

## Check-age-triggered currency sweep

Owner: currency lane proposes the separate scheduling PR after this follow-up;
CC reviews the workflow and resulting landscape decisions. Reuse the existing
freshness proposer and its per-row max-landscape-age minus refresh-lead calculation
(7 minus2 = day5), with supported sourced review, rather than resetting dates
from a metadata-only timer. The separate PR must be ready and its due trigger
must fire **before 2026-10-22**, the first invalid-date boundary; October23 is
the next group. The October15 rows are due October20 and first invalid October23.
Do not wait for a fixed calendar date to begin: landed inputs and check age are
the work trigger. No unit, timer or scheduled workflow is installed by this PR.
