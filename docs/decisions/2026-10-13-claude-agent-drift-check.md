# Claude agent drift check (CPA-V-10 of the Claude-family practice audit)

Date: 2026-10-13. Owner lane: cc-native-practice. Status: decided, implemented in `scripts/adoption_status.py --client-wiring`; reviewed twice (the two review sections below).

## Context

The client serves the definitions in `~/.claude/agents/` (the user scope) to every project that does not define the same name itself. `tools/adoption/install_claude_profile.py` copies the 11 definitions of
`adoption/agents/claude` there verbatim, and nothing compared them afterwards: the audit found five of 11 host copies stale at 06:27Z on 2026-10-12 (fixed since: 11 of 11 equal at `origin/main`), `scripts/adoption_status.py`
had no reference to the Claude agent paths, and the practice page still said four host copies differ (`reference/workers.md` L13). A stale copy is old text; a wider one is a different kind of risk: an omitted `tools`
field means every tool (`anthropics/claude-code@3deb87368737` `plugins/plugin-dev/skills/agent-development/SKILL.md` L152-L154), so a copy that lost the field gives its role the whole tool set in every project. This
drift class produced the incident settled in CPA-V-37.

## How the client loads the folder

Sources read for the review (the first record of this change cited none of them), each at the version named:

- **Folder, home and priority.** User definitions live in `~/.claude/agents/`; `CLAUDE_CONFIG_DIR` moves the Claude home (`anthropics/claude-code@3deb87368737` `CHANGELOG.md` L8578, release 1.0.6: "Respect CLAUDE_CONFIG_DIR
  everywhere"). When names collide the higher priority wins: managed settings, the `--agents` flag, the project, the user, then plugins (https://code.claude.com/docs/en/sub-agents.md L158-L168, fetched 2026-10-13); the installed 2.1.296 client merges its built-in, plugin, user, project, flag and managed definitions in that order into a map keyed by the
  front matter `name`, so a later definition replaces an earlier one of the same name (the function that builds the active set, read in the bundled loader, `d2`).
- **The folder is read recursively, links followed, hidden files included.** "Claude Code scans `.claude/agents/` and `~/.claude/agents/` recursively, so you can organize definitions into subfolders ... identity comes only
  from the `name` front matter field", and of two files under one `agents/` tree that declare a name, "Claude Code loads only one of them, chosen by filesystem read order rather than a documented precedence" (sub-agents
  page L176-L182). The installed 2.1.296 client's loader (`gU`, `OVn`) is either a walker that enters every folder (a visited-folder set stops circular links), follows a symbolic link with `stat`, and keeps a file whose name
  ends in `.md`, or `rg --files --hidden --follow --no-ignore --glob *.md`; a file is then parsed for its front matter and one without a `name` is skipped without a message (`pHo`; `CHANGELOG.md` L7088, release 2.1.43:
  "Fixed spurious warnings for non-agent markdown files in `.claude/agents/` directory"). The first record's claims that the client does not follow links and does not load a nested file were wrong.
- **Why a link still counts as drift.** The installer writes regular copies (`shutil.copy2`, `install_claude_profile.py`), so a link at a shipped name is not what it wrote, and what the client loads through a link is not known
  here: the check does not read through one (a link to a file named `*.md` is a definition nothing here ships, counted; a link to nothing is not loaded, so not counted; a link to a folder makes the count unknown).
- **The identity is the `name` that the client's parser reads.** The loader scan hands each file to the client's front matter parser (`oi(text, path, {normalizeKeys: true})`, read in the installed 2.1.296 bundle): a leading
  byte order mark is dropped; the block is what `/^---\s*\n([\s\S]*?)---\s*\n?/` captures, so it ends at the first `---` after the opener, wherever that stands on a line; `Bun.YAML.parse` reads it (a second attempt
  quotes values that hold YAML-special characters when the first throws); and `Iwt` takes the agent's name from the parsed mapping, which must hold a string: a file with no `name`, a non-string one or a block that does not
  parse is not loaded (`pHo`, `Iwt`, `Vk`: a file over 1 MiB is skipped). The functions are copied unchanged out of the binary by byte interval (`receipts/identity-oracle.txt`) and were run on Bun 1.4.2; the client embeds Bun 1.4.3.

## Decision

`--client-wiring` reports `claude.stack_agents_drift`, a count, and the wiring rule requires 0.

- **Compared:** every `*.md` of this checkout's `adoption/agents/claude` against the same name at the top of `<Claude home>/agents` (`CLAUDE_CONFIG_DIR` when set), byte for byte. A stale copy, a wider one and a changed one are
  the same thing here: bytes that differ. A copy that is absent, a link, a folder or another kind of file counts.
- **Also counted:** every other `*.md` in the installed folder **at any depth** (hidden files included; a regular file, or a link to one), because the client serves it: a definition nothing here ships is a definition
  nothing here checks, and a nested copy of a shipped name is a second definition of that role. Apart from the four vendor names below, the check reads no front matter of a file it does not ship, so a `*.md` with no `name`,
  which the client skips, counts too: it is one line from being a definition, and the way out is to remove or rename it. **Not counted**, because the client's walker keeps regular files only (`isFile()` after `stat`, `OVn`): a pipe, a socket, a device and a
  link to nothing. Four host-only definitions at the top of the folder (`codebase-memory`, `codebase-memory-auditor`, `codebase-memory-scout`, `semble-search`: the search roles
  `tools/local-pages/architecture_mapping.json` names) are a listed exception, installed by the tools they route to; but one whose front matter declares the `name` of a shipped definition is counted, because the client
  keys a definition by its `name` and one of two files that declare it is chosen by read order. A vendor name below the top, or as a link, is not the vendors' own. Backups (`*.md.bak.*`) and other extensions are not
  agent files.
- **Unknown, not zero:** `null` when the checkout's source folder has no `*.md` or one cannot be read, when the `agents` path is a link or not a folder, when a link below leads to a folder (what the client loads through it is
  not known here), when a folder or a shipped definition's installed copy cannot be read (or is over this tool's 1 MiB limit for a client file), when an entry vanishes between the listing and its opening, when the tree is deeper
  than 8 folders or holds more than 5,000 entries, when a vendor-named file declares its `name` in a spelling the reader below does not take (or cannot be read whole), when a shipped definition's own `name` cannot be read,
  and on a platform that cannot read without following a link. Like every `null` leaf it makes `complete` false.
- **The vendor rule reads the name as the client does, or says unknown.** `agent_identity` applies the client's block extraction (byte order mark, the first `---` after the opener, CRLF) and reads the plain spellings of a
  definition's top-level keys: `name` (exact case) with a plain, single-quoted or double-quoted value without escapes, a `|` or `>` block scalar of one line (`|` and `>` keep the final line break, `-` strips it) or the
  value on the next indented line; for the other keys, plain, quoted and one-line flow values. Anything else is unknown, never a guess: a quoted key, an escape sequence, an anchor, an alias or a tag, a value over several
  lines, an indentation or keep indicator, a tab, a name twice. It is not a YAML parser and takes none as a dependency. Measured against the client's own parser (`receipts/identity-oracle.txt`, generated texts and the real
  definitions of the host and the checkout): wherever the client reads a name, the reader returned that name or unknown, never none and never another name, in all 8,582 texts (0 misses; 4,254 texts where the client reads
  a name, 2,900 answered with it and 1,354 unknown) and again in five further seeds of 34,556 texts each. Not established: the corpus is generated and not exhaustive, the YAML engine is Bun 1.4.2 and not the 1.4.3 the
  client embeds, and a vendor that spells its front matter another way makes the count unknown until the reader is extended.
- **Read through descriptors.** The Claude home is opened, then `agents` with `O_DIRECTORY | O_NOFOLLOW`, then every entry with `O_NOFOLLOW` relative to the descriptor of its folder, and what is described is `fstat` of the
  descriptor that was opened: nothing is inspected by path and then opened by path. A replacement made after the check looked at an entry is read as the object that was opened, or refused if it was a link when opened.
  The shared reader `read_regular_bytes` and its Codex caller `stack_roles_matching` read the same way. CPython's ordinary `open` passes the path to `open(2)` as given (`python/cpython@cbc944f4bc59`
  `Modules/_io/fileio.c` L404), and `os.open` takes `O_NOFOLLOW`, `O_DIRECTORY` and `dir_fd` (`Doc/library/os.rst` L1272, L1364-L1365, L3507, L3551).
- **Part of the rule:** unlike `stack_roles_matching` (information; its `null` alone blocks), a non-zero drift makes `complete` false. The reason is the fail-first of the audit item: a fixture with one stale user
  agent reported `complete: true` before this change.
- **Counts only:** no name, path or text leaves the check (the tests give every definition a text that holds a private marker and assert it never appears in the report).

## Evidence

| Claim | Evidence class | Receipt |
| --- | --- | --- |
| A fixture with one stale or wider user agent reported `complete: true` before; now `stack_agents_drift` is 1 and `complete` is false, and every other flag is as it was | local_integration | `ClientWiringTests.test_a_stale_or_wider_user_agent_makes_the_wiring_incomplete`; `receipts/fail-before.txt` (16 of the 153 tests of the module fail on the script at `c63c83a82`, constants aside) |
| The count covers changed, missing, unlisted, link and folder cases; unreadable sources and folders are `null` | local_integration | the new `ClientWiringTests` of the first commit; `receipts/mutants-20.txt` (20 of 20 killed) |
| A definition below the top, a vendor-named file that declares a shipped name, a link to a file named `*.md` are counted; a pipe, a socket, a device and a link to nothing are not; a link to a folder, a vanished entry and a tree past its bound are `null`; non-markdown files are ignored | local_integration | the review tests below; `receipts/mutants-review.txt` (49 of 49 killed, the first review fix) and `receipts/mutants-round2.txt` (92 of 92 killed, the whole list on the final tests) |
| A vendor-named file that declares a shipped name is counted in every spelling the reader takes and unknown in the others, never 0 with complete wiring; the reader never returns none or another name where the client's parser reads one | local_integration; measured against the installed client's parser | the vendor tests of the second review below; `receipts/identity-oracle.txt` (0 misses); `receipts/fail-before-round2.txt` |
| The OpenHands push gate's advisory read inventory accounts for the descriptor opens | local_integration | `blueprints/runtime-workers/openhands/evidence/unclassified-gate-reads-20261013-pr1062-delta.json`; `tests.test_runtime_worker_openhands_push_gate` (127 tests: two failures at `e22358e46`, none now) |
| The mutation counts that this record and the README quote are the receipts' | local_integration | `tests/test_agent_drift_record.py` (it fails on the record of `e22358e46`, which quoted 46 of 46 for a receipt of 49) |
| A replacement of a shipped file, of the agents folder or of a folder below it, made after every step of the read, is never read through: the answer is the stale copy that was opened (1) or `null`, never 0; the Codex role count the same | local_integration | `ClientWiringTests` `test_a_replacement_of_...` (each tries the replacement at every point between two file-system calls of the read); `receipts/fail-before-review.txt` |
| The host's 11 installed definitions equal the checkout's, with the four vendor ones listed and a backup file ignored | native_proven | `python3 scripts/adoption_status.py --profile token-efficiency --client-wiring --json` on the first host, 2026-10-13, with the round-2 commit: `stack_agents_drift` 0 and `complete` true (`receipts/host-run.json`) |

## Review of `e70d2de0a`: Astra's first read and the command center's Claude read, one fix commit

| Finding | Fix | Test (fails before the fix) |
| --- | --- | --- |
| P1 (Astra): inspection and opening were two steps, so a shipped file, or the whole agents folder, replaced by a link after the check was read through it (outside bytes equal to the source: 0 and `complete: true`; the reproducer schedules the replacement between the real `lstat` and the real `open`) | the descriptor-bound reads above, with no fallback to a path check; the shared reader and its Codex caller changed with it, as the read asked | `test_a_replacement_of_a_shipped_file_at_any_point_is_never_read_through`, `test_a_replacement_of_the_agents_folder_at_any_point_is_never_read_through`, `test_a_replacement_of_a_folder_below_the_top_at_any_point_is_never_read_through`, `test_the_codex_role_count_is_never_read_through_a_replacement_either` (file and folder), `test_the_folders_are_opened_below_a_descriptor_without_following_a_link`, `test_a_platform_that_cannot_refuse_links_reads_nothing`, `test_read_regular_bytes_answers_for_every_kind_of_entry_without_following_a_link` |
| P1 (Claude read): the client loads the folder recursively, so a nested definition reads as "no drift" (`agents/old/stack-verifier.md`: 0 and `complete: true`) | every `*.md` at any depth is counted; the test that expected a nested file to be ignored is reversed | `test_a_definition_below_the_top_is_drift_at_any_depth`, `test_the_walk_is_bounded_and_a_tree_past_the_bound_is_unknown_not_a_count`, `test_links_and_other_kinds_below_the_top_are_counted_or_unknown_never_followed` |
| P2 (Astra): the inserted lines moved the source the catalog cites for `codex:host:RTK.md`, and two citation assertions failed | `catalogs/foundation/upstream-surface-dispositions.json` cites `scripts/adoption_status.py:532-553` (`codex_instructions` and `rtk_instructions_inline` whole; a range that holds the instruction names whether lines are counted by `splitlines()` or by LF, which differ by two because of Unicode separators in `RUST_WHITESPACE`); the registry binding is refreshed | `tests.test_upstream_surface_watch` (116 tests, two failures at `e70d2de0a`) |
| P2 (Claude read): no source for how the client loads the folder, and two claims were wrong (links are not followed, a nested file is not loaded) | the section "How the client loads the folder" above; the lines on links are corrected | (the record; the sources were re-read, see below) |
| P3 (Claude read): the four vendor names were exempt whatever they contain | a vendor-named file at the top whose front matter declares a shipped name is counted (in the plain spelling only: the second review below widened it to the spellings the client reads, and made the rest unknown); below the top, or a link, it is not exempt | `test_a_vendor_file_that_declares_the_name_of_a_shipped_definition_is_drift`, `test_a_vendor_name_below_the_top_or_as_a_link_is_not_the_vendors_own`, `test_a_vendor_file_that_cannot_be_read_is_not_drift_for_what_it_might_declare` |
| P3 (Claude read): the record had no registry row; its host command omitted `--profile token-efficiency`; (Astra P3) the changelog paraphrase overstated its line | a row is registered; the command is as the receipt records it; the paraphrase is narrowed to the entry's words (spurious warnings were fixed) and the loading rules rest on the loader and the documentation instead | `scripts/validate.py`; the registry check |

Two corrections to what the review relayed, both from the primary sources: the changelog line cited for the merge order (L8578) is the `CLAUDE_CONFIG_DIR` entry, and the priority is documented on the sub-agents page and
implemented in the loader (above); and the installer is not a clean recovery path (next section).

## Review of `e22358e46`: Astra's second read and the command center's Claude read, one round-2 commit

Sources read for this round: the installed 2.1.296 client's bundled front matter parser and agent loader (`WS`, `BL`, `oi`, `W9t`, `C`, `I`, `Iwt`, `pHo`, `d2`, `Vk`; byte intervals in `receipts/identity-oracle.txt`), run on Bun
1.4.2; `blueprints/runtime-workers/openhands/evidence/advisory-gate-deltas.md` and `resolver/push_gate.py` `derive_ci_protected` for the delta.

| Finding | Fix | Test (fails before the fix) |
| --- | --- | --- |
| P2 (Astra): the descriptor opens added three reads to the OpenHands push gate's advisory inventory (9 to 12 for `scripts/adoption_status.py`) and `tests.test_runtime_worker_openhands_push_gate` failed two tests at `e22358e46` | a new dated monitoring delta, derived with the native `GitTree` and `derive_ci_protected`: 347 reads against the 344 of the baseline it names; the three added reads are the opens in `open_below`, `stack_roles_matching` and `stack_agents_drift`, the 24 location changes are line moves (9 in this script, shifted by its insertions; 15 in `scripts/skills_status.py` and `tools/adoption/install_skills.py`, which other pull requests moved since the baseline); its index entry is appended, every earlier snapshot and delta is unchanged, both files are registered. `source_commit` is null: the tree it was derived from is a local commit of this round's content before the delta existed, and the published head holds the same scripts | `tests.test_runtime_worker_openhands_push_gate` (127 tests; `RepositoryWorkflowTests.test_advisory_baseline_and_explicit_categories_stay_bounded_on_this_repository` and `test_baseline_refresh_regression_accepts_a_committed_outer_observation` fail at `e22358e46`) |
| P2 (Astra): the vendor-name rule read the plain `name:` line only, so a vendor-named file declaring a shipped name through a quoted key, a block scalar, an escape or a byte order mark gave 0 and `complete: true` | `agent_identity` replaces the regex: the client's block extraction and a strict reader of the plain spellings; any other spelling is unknown (the count `null`, `complete` false); the shipped definitions' names are read the same way; the claim of the first review's vendor row is narrowed above | `test_a_vendor_file_that_declares_the_name_of_a_shipped_definition_is_drift` (every row asserts the count and `complete`), `test_a_vendor_file_whose_name_is_spelt_in_a_way_the_reader_does_not_take_is_unknown_and_incomplete` (27 spellings, among them the reviewer's quoted key and escape), `test_the_name_reader_gives_what_the_clients_parser_reads_or_says_unknown`, `test_every_shipped_definition_declares_a_name_the_reader_takes`, `test_a_shipped_definition_whose_name_cannot_be_read_makes_the_count_unknown`, `test_a_vendor_file_over_the_clients_size_limit_is_unknown` |
| P2 (the command center, the only blocker): the record quoted 46 of 46 for `mutants-review.txt`, whose receipt and README hold 49 | the row cites each receipt with its own count, the final head's receipt included; a test holds every quoted count to its receipt | `tests/test_agent_drift_record.py` |
| P3 (the command center): a pipe or socket named `*.md`, or a `*.md` with no `name`, counted although the walker skips it | a pipe, a socket, a device and a link to nothing are not counted (the kind comes from the descriptor that was opened, or from `stat` for a link); a `*.md` with no `name` stays counted and the record and the function's docstring say why | `test_a_link_to_a_file_is_counted_and_what_the_clients_walker_skips_is_not` |
| P3 (the command center): a vendor-named link swapped for a regular file between the open and a later look was classified by the later look | a link is told by the open's own refusal (`ELOOP`, measured on the first host's Linux 6.18; `EMLINK` is accepted too) | `test_a_link_is_told_by_the_answer_of_the_open_and_not_by_a_later_look` |
| P3 (the command center): `name:` with the value on the next line | read, with the other forms the client reads at the top level, by `agent_identity` | `test_the_name_reader_gives_what_the_clients_parser_reads_or_says_unknown` |
| P3 (Astra): `tools/adoption/host-baseline.md` cites `adoption_status.py:1124-1134` for the default launcher root, which moved | the guide cites `:1521-1531` (`launcher_resolution`) and keeps the old range as the one at its reference commit | (the lines were read) |
| P3 (Astra): the installer; existing hostname text in two touched files; the upstream captures were not in the packet | the installer recovery is its own pull request (see Not covered); the hostname lines are existing text (none is added) for a hygiene pull request; the next brief attaches the captures of the cited upstream files | the body's Follow-ups |

## Not covered

- Project-scope definitions (`.claude/agents` of a checkout) and plugin-provided ones: the check reads the user scope, where the installer writes. The project scope is the repository's own files.
- Whether a definition is *correct* (its tools, model and effort against the role): that is review, not drift.
- The practice page note (`reference/workers.md` L13, "four host copies differ") is stale; correcting it is a re-pin of the practice skill and belongs to the next one (the skills manifest pins the page).
- The installer is not the recovery for every drift (separately authorized installer work, a follow-up): `install_agents` writes under `~/.claude/agents` and not under `CLAUDE_CONFIG_DIR`; its equality test
  (`install_claude_profile.py` L178-L179) follows a link, so a linked copy with equal bytes is skipped and its drift does not clear; and `shutil.copy2` over a link writes through it (`python/cpython@cbc944f4bc59`
  `Lib/shutil.py` L262). Recovery by hand: remove the stale, linked or unlisted file, then rerun the installer.
- The check is a snapshot of one pass over the folder: a change made after it read an entry is not seen until the next run, and it is no boundary against one.
- `agent_identity` is not a YAML parser: it takes the spellings above and says unknown for the rest, so a vendor-installed definition spelled another way makes the count unknown until the reader is extended or the
  file is rewritten. The oracle's corpus is generated, and its engine is Bun 1.4.2 (the client embeds 1.4.3).

## Overturn conditions

- A client release that serves user-scope definitions from another folder or in another format: the path and the glob change.
- A client release that stops loading nested definitions, or that keys a definition by something other than the front matter `name`: the depth and the vendor rule change.
- A vendor that installs more host-only definitions: add the name to `VENDOR_HOST_AGENTS` with its source, or the host shows drift until then.
- A client release that changes its front matter parser (the YAML engine, the block rule, the keys it takes): rerun the differential measurement against the new binary before relying on the reader.
