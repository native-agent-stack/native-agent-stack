# Landscape coverage ledger (step 1)

One coverage ledger over the stars, the awesome lists and the research-runtime outputs: every seed gets exactly one
disposition. It is deterministic. It makes no model calls and no keyed calls, and it reads no GitHub API metadata
(that is step 3.1).

## Files

| Path | What it is |
|---|---|
| `tools/landscape/screen_generic.py` | The retained G5 generic list screen, this project's own tool, so landing it forks no upstream. Only its path constants changed (lines 19-24 and 427-428). Its original bytes are bound by the hash at `native-agent-stack/native-agent-stack@c8a29c3ee9b4337564165d9e588b3fe81e8ba817:catalogs/landscape/grand-catalog-20261008.json:340`, the commit that added that line. The release `v2026.10.08` meant to carry the G5 archive was never published. `tests/test_landscape_screen_generic.py` shows the difference and binds the bytes. |
| `tools/landscape/coverage_ledger.py` | `build`, `check` and `seeds` (below). |
| `catalogs/landscape/coverage/awesome-lists-<date>.json` | The pinned list table: every list with its pin, its extraction counts, its files with entries, and each recorded census reconciled at its own pin. |
| `catalogs/landscape/coverage/coverage-ledger-<date>.json` | One row per seed, with its disposition, state, populations and provenance; step 2's cluster table and the reason table. |
| `evidence/artifacts/landscape-coverage-ledger-<date>/runs-index.json` | The research-runtime runs index (DeerFlow, GPT Researcher, the pi-claude researcher, DDGS exact queries) and the open-PR outputs the plan names. |
| `catalogs/landscape/coverage/*.schema.json` | The JSON Schemas `check` validates the three documents against. |

The coverage documents sit one level below `catalogs/landscape/`. Readers of the top-level `catalogs/landscape/*.json`
parse every file there. `scripts/host_receipts.py` `landscape_winners` does so once per component, for
`receipt_staleness.py` and `currency_due.py`, and the Architecture refresh refuses an ungranted top-level file.

## Commands

```sh
# On the host that holds the list clones (one <owner>__<repo> clone per list at its pin) and the retained inputs:
python3 -I tools/landscape/coverage_ledger.py build --clones CLONES [--clones CLONES2] --state-root STATE \
  --pr-files PR_FILES --scratch SCRATCH [--gptr-checkout GPTR] [--date YYYYMMDD]
python3 scripts/final_stack.py --write        # its stars and grand intake read the newest ledger
# Anywhere (committed files only):
python3 tools/landscape/coverage_ledger.py check [--strict]
python3 tools/landscape/coverage_ledger.py seeds --modality repository --out seeds-repository.json
python3 tools/landscape/coverage_ledger.py seeds --modality skills --out seeds-skills.json
```

`seeds` gives the committed master seeds a consumer: it emits `build_inputs.py --seeds` JSON for one modality (the
landscape catalogs' layers, or the skills-lifecycle tasks). Write the file into the sweep's work directory, not
under `tools/sota-convergence/landscape-sweep/`, where `final_stack.py` reads the newest `seeds-<date>.json` as a
record.

A rebuild under a new date also names its two new catalog files in two exact-path entries:
- the `sourcegraph-access-token` allowlist for the list table's `"commit"` lines in `.gitleaks.toml`;
- the size-bound exemption in `scripts/active_model_currency.py` (both files exceed its 2,000,000-byte check bound).

`check` fails on an internal inconsistency or when a frozen record (the grand catalog, coverage-accounting) changed.
A change to any other recorded input (the stars, the starred and master seeds, the stack manifest, the aliases, or
the part of `final-stack.json` the ledger reads) makes the ledger STALE. `check` prints that and still passes, and
`--strict` makes it fail. Rebuilding needs the clones and the retained inputs, so a star refresh need not block on it.

## Dispositions

A seed is an owner/repo slug, an `entry:` (a committed entry that names no GitHub repository), or a `url:`: the
canonical URL of a named candidate whose link is not a GitHub repository. Canonical means https, a lowercase host
without `www.`, no userinfo, port, query, fragment or trailing slash, and a public host. A path segment that matches
the repository's private-content patterns (`scripts/validate.py` `PRIVATE_CONTENT`) is replaced by a placeholder,
and the ledger counts each such URL.

Each seed gets exactly one of LAYER-CANDIDATE (with its layer ids), OUT-OF-SCOPE (with its reason), DUPLICATE (of
an identity), RETIRED, UNMAPPED (with its reason) or NON-GITHUB (with its layers and reason), in this precedence:

1. DUPLICATE: a verified alias (`catalogs/us-equities/coverage.json#/aliases`). The canonical identity decides with
   the alias's mappings.
2. RETIRED: only where an existing record shows the upstream archived (coverage-accounting's `archived`, a star's
   `archived`, the MCP ledger's archived REJECT rows). Step 3.1 adds the rest.
3. CARRIED mappings, from committed records: grand-catalog rows, master seeds, public stars, starred seeds and the
   final-stack index. A public star's OUT-OF-SCOPE is a repository-level decision. It outranks unassessed backlog
   slots and yields only to a final-stack role. A grand-catalog OUT-OF-SCOPE row is slot-scoped. Existing verdicts
   stay under `existing`, and overridden mappings under `conflicts`.
4. PROPOSED mappings: G5's one-family list screens are proposed dispositions, never final (the CC's Q1-3 ruling).
   They come from the re-extracted lists, the MCP ledger's `catalog_layers` and the generic ledger's `layer_ids`.
   Step 3's two-family screen confirms or overturns each one. A list's external entries (`external_resources`) are
   grouped by canonical URL by the same rule. One the screen matches to layers is NON-GITHUB: step 3's readers rank
   GitHub repositories, so it stays outside LAYER-CANDIDATE with its layers kept (the CC's ruling of 2026-10-16 on
   named candidates).
5. UNMAPPED: research-run and PR seeds that nothing else maps, slugs and `url:` seeds alike, each with its reason
   and a step-2 cluster. So does each OUT-OF-SCOPE seed whose reason is screen_generic's "No committed layer
   capability matched" (step 2's second input).

screen_generic's lifecycle matches are hints (`lifecycle`), not layer mappings: the module keeps them separate and
never lets them alone promote an entry (`screen_generic.py:160-161`).

## Boundaries

- Lists: unauthenticated depth-1 partial clones. Each list is read at its newest recorded pin (the plan's Q1-2
  default). An older recorded census is re-read at its own pin as provenance. A list with no recorded pin is read at
  the default-branch head fetched for the build. screen_generic reads `.md`, `.mdx` and `.rst` only.
- A list whose `external_resources` pass stops on a link `urlsplit` refuses (`screen_generic.py:311`, a truncated
  bracketed host such as `http://[::1`) is read again with only those links skipped, through the path the module
  already takes for a non-http(s) scheme (`:312`). The module's bytes are unchanged, and `extraction.ignored` counts
  the skipped links.
- screen_generic's `run()` and `artifacts()` also need a caller-set `OUT`, `GAP`, `AMEND` and `REFERENCE`. The
  ledger uses `extract()` and `external_resources()` only, and sets `BASE` and `REPOS` per list.
- DeerFlow databases: each is copied together with its `-wal` and `-shm` files and each copy's sha256 is verified.
  Only `sqlite_master` names and named `runs` columns are read, then the copy is deleted. No user, password, token,
  session or credential table is read, and no `SELECT *` is issued. The 81 run databases hold only `checkpoints` and
  `writes`.
- Pass flags: the record a DeerFlow run writes (`native-retrieval-metadata.json`), judged by the predicate the
  dispatch adapter asserts (`tools/research/dispatch:247` and `:277-283`). Every other run is UNVERIFIED (the CC's
  Q1-4 ruling). A pass flag is metadata and never replaces primary-source review.
- Question and query text is not published. The topic is a model-written heading or title. The runs index's
  `withheld` record counts each withheld field with its reason, all privacy: the pi-claude topic, because a briefed
  role run's heading can restate its brief; the pi-claude first user turns, which were not read; and the DDGS
  frozen queries.
- Seeds from runs and PRs are cited GitHub owner/repo identities (under screen_generic's `repo_from` rules) and the
  canonical URL of every other cited public http(s) link, without screen_generic's badge, image and sponsor links.
  A name with no link at all is not extracted.
- Retained inputs (the MCP and generic list ledgers) are named, with their row counts, never hashed.
