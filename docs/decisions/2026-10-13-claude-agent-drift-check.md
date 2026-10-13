# Claude agent drift check (CPA-V-10 of the Claude-family practice audit)

Date: 2026-10-13. Owner lane: cc-native-practice. Status: decided, implemented in `scripts/adoption_status.py --client-wiring`.

## Context

The client serves the definitions in `~/.claude/agents/` (the user scope) to every project that does not define the same name itself. `tools/adoption/install_claude_profile.py` copies the 11 definitions of
`adoption/agents/claude` there verbatim, and nothing compared them afterwards: the audit found five of 11 host copies stale at 06:27Z on 2026-10-12 (fixed since: 11 of 11 equal at `origin/main`), `scripts/adoption_status.py`
had no reference to the Claude agent paths, and the practice page still said four host copies differ (`reference/workers.md` L13). A stale copy is old text; a wider one is a different kind of risk: an omitted `tools`
field means every tool (`anthropics/claude-code@3deb87368737` `plugins/plugin-dev/skills/agent-development/SKILL.md` L152-L154), so a copy that lost the field gives its role the whole tool set in every project. This
drift class produced the incident settled in CPA-V-37.

## Decision

`--client-wiring` reports `claude.stack_agents_drift`, a count, and the wiring rule requires 0.

- **Compared:** every `*.md` of this checkout's `adoption/agents/claude` against the same name under `<Claude home>/agents` (`CLAUDE_CONFIG_DIR` when set), byte for byte. A stale copy, a wider one and a changed one are the
  same thing here: bytes that differ. A copy that is absent, a link, a folder or another kind of file counts (the way the Codex role carriers do: a link's target is not what the client was shown).
- **Also counted:** a `*.md` at the top of the installed folder that is not shipped here and is not one of the four vendor-installed host-only definitions (`codebase-memory`, `codebase-memory-auditor`,
  `codebase-memory-scout`, `semble-search`: the search roles `tools/local-pages/architecture_mapping.json` names). Those four are a listed exception, installed by the tools they route to; an unknown definition is a
  definition the client serves and nothing here checks. Backups (`*.md.bak.*`), other extensions and anything below the top of the folder are not agent files and are not counted.
- **Unknown, not zero:** `null` when the checkout's source folder has no `*.md` or one cannot be read, when the `agents` path is a link or not a folder (what the client loads through it is not known here), or when the
  folder or a shipped definition's installed copy cannot be read. Like every `null` leaf it makes `complete` false.
- **Part of the rule:** unlike `stack_roles_matching` (information; its `null` alone blocks), a non-zero drift makes `complete` false. The reason is the fail-first of the audit item: a fixture with one stale user
  agent reported `complete: true` before this change.
- **Counts only:** no name, path or text leaves the check (the tests give every definition a text that holds a private marker and assert it never appears in the report).

## Evidence

| Claim | Evidence class | Receipt |
| --- | --- | --- |
| A fixture with one stale or wider user agent reported `complete: true` before; now `stack_agents_drift` is 1 and `complete` is false, and every other flag is as it was | local_integration | `ClientWiringTests.test_a_stale_or_wider_user_agent_makes_the_wiring_incomplete`; `receipts/fail-before.txt` (16 of the 153 tests of the module fail on the script at `c63c83a82`, constants aside) |
| The count covers changed, missing, unlisted, link and folder cases; the four vendor definitions, backups and nested files are not counted; unreadable sources and folders are `null` | local_integration | the 12 new `ClientWiringTests`; `receipts/mutants-20.txt` (20 of 20 killed) |
| The host's 11 installed definitions equal the checkout's | native_proven | `python3 scripts/adoption_status.py --client-wiring --json` on the first host, 2026-10-13: `stack_agents_drift` 0 |

## Not covered

- Project-scope definitions (`.claude/agents` of a checkout) and plugin-provided ones: the check reads the user scope, where the installer writes. The project scope is the repository's own files.
- Whether a definition is *correct* (its tools, model and effort against the role): that is review, not drift.
- The practice page note (`reference/workers.md` L13, "four host copies differ") is stale; correcting it is a re-pin of the practice skill and belongs to the next one (the skills manifest pins the page).

## Overturn conditions

- A client release that serves user-scope definitions from another folder or in another format: the path and the glob change.
- A vendor that installs more host-only definitions: add the name to `VENDOR_HOST_AGENTS` with its source, or the host shows drift until then.
