# Harness atlas: a local compounding page over the repository's own records

The harness atlas is `atlas.html`, a page of the repository's local page builder
(`tools/local-pages`), rebuilt from the committed catalogs and a measured daily token
projection on every refresh. It answers three questions in one pass: what each model family
runs at each of the seven harness layers, what is settled, and what measurement shows the
lanes used. It is never a hosted artifact. Each build compares its projected state with the
last row of a hash-chained ledger and appends a row only when that state changed, so the
record compounds and the next session starts from the ledger, the receipt and the daily
history.

## Direction and ruling

The owner directed that the Harness Atlas be a local, compounding page built from the
repository's own records rather than a hosted artifact, with its design synthesized through
the pinned upstream skills. This paraphrases the direction; no owner message is quoted. The
CC's build plan for this change (2026-10-17, a private record cited by name) sets the
contracts, grants, tests and validators below.

## SOTA sources

| Source and pin | Contract used |
| --- | --- |
| [anthropics/skills](https://github.com/anthropics/skills/tree/33375500bcea98d610eb30ce10ac4e59b89c390d/skills/frontend-design) `33375500bcea98d610eb30ce10ac4e59b89c390d`, tree `d79e2a5bb4df4a386c2adcdd9ab8709bba28c3f6`, `skills/frontend-design/SKILL.md` SHA-256 `d91970639e9f5c37682ac7ab60094d35f1c7c1f38d731bd56396563aee10c1d3` (`adoption/skills/manifest.json:525`) | The brief, the two-pass token plan, the review against the brief, the build and the critique pass; every visual rule in `tools/local-pages/design-plan.md` "Atlas page" cites its line |
| [mattpocock/skills](https://github.com/mattpocock/skills/tree/d81f3a183412e71a5b1e84ca21bc1a35eea03a60) `d81f3a183412e71a5b1e84ca21bc1a35eea03a60`, `skills/engineering/tdd` (SKILL.md SHA-256 `93ea419b…a1cc`) and `skills/engineering/codebase-design` (SHA-256 `2c20617f…e1d2`) | Red before green, one seam at a time; the source-map loader and reader shared behind small interfaces now that a second page uses them |
| ccusage/ccusage v20.0.24 `rust/adapters/claude/src/daily.rs:410-458`, as the unchanged kernel already cites it (`examples/claude-native/workflows/child-usage.mjs:2505-2506`) | Per-message deduplication of Claude usage |
| openai/codex rust-v0.157.1 `codex-rs/protocol/src/protocol.rs:2234-2310`, as `tools/skill-usage/skill_usage.py:1211-1212` cites it | The Codex token counters, kept apart from Claude's |
| [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching), read 2026-10-17T05:18:15Z, 3,118,775 bytes, SHA-256 `0e35580db9777497e447cb9e9cc14fd4e792d479ca137976a59c6946d7c361b3` | `usage.cache_creation.ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens`; `cache_creation_input_tokens` equals the sum of the `cache_creation` values |
| systemd 259 (259.5-0ubuntu3.4), `systemd.service(5)` `ExecStart=` (man page gzip SHA-256 `e25f4928eb2e90eb2ffead15800d49893b34344ee972471d72b7271a2f3161d8`) and `systemd.timer(5)` `OnCalendar=`, `Persistent=` (`90f5229f48bd3f2ba617225b41b4b514efa1c5a834cfc70fca0e9626ebee03f9`), read 2026-10-17T05:18:04Z | A oneshot unit's commands run in order and a failing one stops the rest; an hourly persistent timer catches up a missed run |
| Python 3.13.16 `os.replace`, `tempfile`, `fcntl.flock`, `html.escape`, `tomllib` | Atomic publication, the ledger lock, escaping and the Codex agent files |

## What changed

- **The page.** `tools/local-pages/atlas_data.py` (model, ledger, receipt, publication),
  `atlas_view.py` (nine sections), `atlas_sources.json` (`local-atlas-sources/1`, every source
  with its grant), `atlas_map.json` (`local-atlas-map/1`, reviewed joins and paraphrases, each
  citation a path, line and anchor), `assets/atlas.css` (shared tokens only).
- **Shared seams.** `overview_data.load_page_sources` and `read_declared` generalize the
  overview's loader and reader; `source_policy.AtlasReads` reuses every `OverviewReads` check
  under the `atlas` section, whose messages stay byte-identical for the overview.
- **The composer.** `build_pages.py`: the Atlas in every page's navigation and on Home,
  `refresh_atlas` in each full refresh, `--atlas-only`, an `atlas` placeholder, and
  `publish(nonserved=...)`, which replaces the ledger after the served files and before the
  receipt and refuses it inside the served root.
- **The producer.** `tools/skill-usage/daily_token_usage.py` writes `token-rate-daily/1` and
  `token-rate-history/1` outside every git worktree from the two unchanged native collectors,
  run through `daily_skill_usage.lane_commands` and `run_reports`;
  `adoption/templates/systemd/token-rate.service` and `.timer` render its hourly timer.
- **Grants.** One new top-level `atlas` role map in `tools/local-pages/source_policy.json` with
  exactly two state grants: `coordination/command-center/skills/token-rate-latest.json` and
  `token-rate-history.json`. Every other read reuses an existing exact grant.

## The compounding record

- **Producer history.** One row per closed UTC day; a complete row (both the Claude and Codex
  collectors measured) is never rewritten, and an incomplete one is superseded by a later
  measurement that records the old row's digest. Each run re-measures every missing or
  incomplete day of the last seven, then today so far, which never enters the history.
- **Atlas ledger** (`local-atlas-ledger/1`, beside the refresh receipt). Each row holds a
  timestamp-free state: layer states and winners, slot statuses, declared routing, rule
  records, skill pins and the measured extent. A row is appended only when that state's digest
  differs from the last row's, chained to it by digest; past 400 rows the oldest drops and its
  digest anchors the chain. A ledger that fails a digest, sequence or chain check is left
  byte-identical for inspection and nothing is appended. Every build writes its receipt
  (`local-atlas/1`) with the row it matched and the checks since that row.

## Measured on this host

Evidence class `local_integration`: real catalogs and one replayed real day of aggregates, in a
scratch state root outside every worktree.

- **Collectors** for the closed UTC day 2026-10-16: `child-usage.mjs --lanes-sweep` took 6.7 s
  and `skill_usage.py --lanes` 0.44 s.
- **Acceptance comparison** with `ccusage claude daily --offline --no-cost --json --since
  20261016 --until 20261016 --timezone UTC` (ccusage 20.0.34). The projection's Claude token
  columns cover the complete agents only (278 of 286): 53,901 input, 8,607,526 output,
  1,264,897,818 cache read and 27,969,541 cache write tokens. Adding the kernel's separately
  counted advisor sub-inference (19,220,190 input, 1,248,964 output) and the eight incomplete
  agents gives 19,274,619 input and 10,120,012 output tokens against ccusage's 19,274,609 and
  10,119,981. Cache reads exceed ccusage by 0.07% and cache writes by 2.6%; this one comparison
  does not attribute that residue (the kernel's per-transcript deduplication against ccusage's
  cross-file deduplication is one candidate), so whether resumed sessions inflate the sums stays
  open. Because advisor input was 19.2 million uncached tokens that day, the projection
  publishes it as its own numerator and the page states it beside, never inside, the token
  columns and the cache-read share. Not a gate.
- **Prompt-cache TTL** that day: main conversations wrote 4,207,204 tokens at the 1-hour TTL
  and 22,356 at 5 minutes; Agent-tool and Workflow agents wrote all of theirs at 5 minutes,
  matching the `prompt-caching` slot's route text.

## Alternatives

- **A hosted artifact.** Rejected by the owner: the page must be local and compound.
- **Extending the overview.** The overview reads every source its map declares, so the two
  pages' sources would be coupled and a missing projection would pend the overview.
- **Token fields in `skill-invoke-rate-daily/1`.** Its seven-day skill window differs from
  closed-day token windows, and a mixed schema would blur both.
- **A second `ExecStart` in the existing skill-invoke-rate unit.** In a oneshot unit the
  commands run in order and a failing command stops the ones after it
  (`systemd.service(5)`, `ExecStart=`, systemd 259), so a skill-report failure would silently
  drop the token projection.

## What would overturn this

- A pinned diagram-design or dataviz skill in `adoption/skills/manifest.json`, which would let
  the measured section use figures; until then it stays tables.
- A kernel counter for Workflow-tool calls (a `tool_calls_by_name` allowlist in
  `childLanes`), which would let the page show Workflow runs instead of agents spawned.
- A ccusage comparison that disagrees beyond the advisor and incomplete-agent terms above on a
  later closed day, which would reopen the projection's usage rule.

## Decisions and inputs for the CC

- Name the ruling records for the three standing rules shown as pending: Muse as a second
  family, Anthropic API keys only for highest-quality resolution with prompt caching, and the
  GPT pool's 30-point reserve. The page cites none until named, and it states that wiring the
  reserve through the quota gate is unverified. The fourth rule, zero tolerance for stale
  models, runtimes and repositories, cites its own record,
  `docs/decisions/2026-10-17-zero-tolerance-currency.md` (#1237), first.
- Keep the diagram-derived status glyphs, or switch the page to text-only state labels.
- Install `token-rate.timer` after landing; choose hourly (rendered) or daily.
- Name a `--muse-logs-root` for the service, a dedicated `/var/tmp` child as
  `tools/muse_file_fence.py` requires; until then the Muse lane reads "not configured".
- Name extra `--codex-root` values for jobs that run with a lane-local `CODEX_HOME`.
- The host's missing `jsonschema` fails the layer pages and two overview tests on main; the
  atlas never builds layer pages, so it is unaffected.
