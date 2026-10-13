# A marked coordinator's WebSearch is denied natively at launch; the shared hook is advisory and its registrations cannot end in status 2, 2026-10-13

CPA-V-03 of the Claude-family practice audit (`claude-practice-audit-converged-20261012`, P2, source-only in the audit, measured here). The research-routing guard that denied WebSearch for marked coordinators
([2026-10-08-coordinator-research-routing.md](2026-10-08-coordinator-research-routing.md), correction #76) was a PreToolUse hook with a 5 s timeout and no `onFailure`, run as a bare `python3 <file>`. The audit's
proposal was `onFailure: "block"` on that entry; the command center ruled on 2026-10-13 that the denial is enforced natively at launch instead, because failing the shared entry closed would block WebSearch in
every session on a runner failure. This record states what the client does (measured), what changes, and the one step that is the command center's: the launchers of the two marked coordinators.

## Context

- The registration (`adoption/templates/claude.settings.template.json` at `ba6afd8d7`): one PreToolUse entry for `^(WebSearch|WebFetch|<context-mode fetch tools>)$` and one UserPromptSubmit entry, both
  `python3 "${HOME}/.claude/hooks/research-routing-guard.py"`, timeout 5, no `onFailure`. The hook denied WebSearch only for a session whose launcher set `NAS_RESEARCH_COORDINATOR_ROLE` and the exact native
  session id; every other session and every other tool passed through it silently.
- The scope of #76 is a routing rule: a coordinator's research goes through `tools/research/dispatch`. It holds for marked coordinators and must not touch unmarked sessions.

## Measurement

Claude Code 2.1.296, headless sessions in an empty directory, the host's profile (default mode `bypassPermissions`) unchanged (`receipts/`):

| Arm | WebSearch listed to the model | WebSearch call |
| --- | --- | --- |
| no settings (control) | yes | runs |
| `--disallowedTools WebSearch` | no | none made |
| `--settings` overlay with `permissions.deny: ["WebSearch"]`, under `bypassPermissions` | no | none made |
| the PreToolUse hook entry alone, runner exits 1 (a crash, or a timeout) | yes | **runs: let through** |
| the PreToolUse hook entry alone, runner file missing (`python3` exits 2) | yes | **blocked, in every session** (a hook error and a permission denial) |
| the overlay and a missing runner, or the overlay and a crashing runner | no | none made |
| UserPromptSubmit entry, runner file missing | - | **the prompt itself is blocked** (0 turns) |
| UserPromptSubmit entry, existence-checked registration, same missing file | - | the prompt runs (an unreadable file and a runner that exits 2 are shell-level cases, below) |

So the hook cannot be the enforcement: a runner that fails with any status but 2 lets a marked coordinator's search through, and one that is missing blocks everyone's prompt and WebSearch (the exit-2 trap that the
audit's Claude read named). The native deny needs no runner and holds under `bypassPermissions` (`docs/en/permissions.md` L62-L66: a bare tool name in a deny rule "removes the tool from Claude's context
entirely"; `docs/en/cli-reference.md` L87; `permissions.md` "Settings precedence" L699-L703: a tool denied at any level cannot be allowed at another and deny rules of every scope are evaluated before allow rules;
`settings-reference.md` `permissions.deny`: scope "Any file", and `--disallowedTools` "adds deny rules for one session alongside this key").

## Decision

1. **The denial is the launch's.** `adoption/templates/claude.coordinator.settings.template.json` is the overlay of a marked coordinator: `{"permissions": {"deny": ["WebSearch"]}}`, passed as `--settings <file>`
   (or `--disallowedTools WebSearch`). Only WebSearch: WebFetch and context-mode's fetch-and-index keep their normal permission checks and their URL log, as #76 specifies. The shared profile template does not
   carry it, so an unmarked session keeps WebSearch.
2. **The hook is advisory.** For a marked session `research-routing-guard.py` keeps the redirect hint to `tools/research/dispatch --question '<question>'` (now `additionalContext`, never a permission decision) and
   the bounded fetch-URL log; both may fail open. A WebSearch call that reaches it came from a session launched without the overlay, and is not blocked there.
3. **Both registrations keep the shell in control**: `f="${HOME}/.claude/hooks/research-routing-guard.py"; [ -f "$f" ] && python3 "$f"; true`. The existence check makes an absent file silent, and the
   closing `true` makes every other failure of the runner (an existing file that cannot be read, a runner that exits 2 or raises, a file that disappears after the check) end the command with status 0, never the
   2 that blocks a prompt or a tool call; the runner's own output still passes through. Round 1 of the review found that the first form, `... && exec python3 "$f"; true`, kept the shell out of the way: with
   `exec` the closing `true` never ran, so an unreadable file (Python cannot open it) and a runner that exits 2 both ended in 2 on both events (the verdict file of the read of `74afed4eb`, blocker 1). An
   additional `-r` test alone would not cover the race between the check and the open or a runner that exits 2. (The secret-path guard keeps its own fail-closed form: it is the one that must refuse.)
4. **The settings applier retires the replaced command.** `merge_hooks` de-duplicates by command, so the bare `python3 "<home>/.claude/hooks/research-routing-guard.py"` already on a host would have run beside
   its wrapped replacement (the fetch log counting every URL twice). `tools/adoption/apply_claude_settings.py` gains `SUPERSEDED_HOOK_COMMANDS`, a finite allowlist matched as the held-out carriers are (exact
   string, HOME as written or another spelling of the settings file's own home, nothing else parsed), retired unless the incoming template runs the same command, whether or not the host keeps its held-out carriers.
5. **Host step, the command center's act** (this change writes no host configuration): add `--settings <path to the overlay>` to the launch of each marked coordinator (the two launchers that set
   `NAS_RESEARCH_COORDINATOR_ROLE`), and re-apply the profile template (`apply_claude_settings.py`, or the new-WSL tool's apply) so that the two registrations become the wrapped ones. Until the first is made the marked
   coordinators are as they were: the hook (now advisory) no longer denies them, so the launch step is what restores enforcement; do it in the same act.

## Review round 1 (Astra's read of `74afed4eb`: two P1 and three P3; the local review: one P2; one commit)

The verdict file is `full1-pr1089-74afed4eb/GPT-VERDICT-74afed4eb.md` (sha256 `ba0552fa13909e25f1796a000de914fd0e393064c9c5862db65460f2bd9241d2`). Each fix has a test that fails on `74afed4eb` (`receipts/fail-before-round1.txt`).

| Finding | Fix | Test (fails before the fix) |
| --- | --- | --- |
| Blocker 1, `claude.settings.template.json:179` and `:206`: an existing but unreadable runner, or a runner that exits 2, ended the command with status 2 on both events (`exec` replaced the shell, so the closing `true` never ran); the record's "cannot exit 2" was contradicted | the registrations drop `exec`: `[ -f "$f" ] && python3 "$f"; true` (decision 3); the hook's docstring, the hooks README and the record say what is true | `RegistrationTests.test_an_unreadable_guard_file_and_a_runner_that_exits_2_never_end_in_status_2_on_either_event` (absent, unreadable, exit 2, raises, empty; both events) |
| Blocker 2, `new_wsl_client_config.py:2243-2244`: the recovery step's preflight merge passed no home, so the retirement removed nothing, a settings file that held both the replaced bare command and its replacement was reported current and the applier never ran (four registrations, one fetch logged twice) | the preflight merge passes the settings file's home, as the applier's own merge does (`home=file_io.host_home(target)`); the only other product caller of `merge_settings`, the one that builds `wanted` in the same step, merges the stage's template with the overlay (no host file, nothing to retire) | `ResearchSupersessionRecoveryTests` in `tests/test_new_wsl_client_config.py`: through `--apply` with the legacy and the current registrations already installed: a real apply, one registration per event, one fetch-log record, then a no-op apply |
| P3 4 (and the local review's P2), `test_coordinator_search_native_deny.py:189`: the opt-in probe's 90 s deadline did not bound a client that stays silent (`for line in process.stdout` blocks before the check); and a failure message said the call "goes through" where the receipt records it listed and blocked | the read has a deadline of its own (a reader thread and a timed queue read) and the process group is ended and reaped on every path; the message names what the assertion checks | `InitRecordReaderTests` (a silent child, a child that stalls in the middle of a line, a child that answers after other records, a child that ignores SIGTERM, a grandchild of the child's process group, and the former loop as the control that stays blocked past its own deadline) |

Follow-ups of the read (none changing code): the four documentation pages cited in `receipts/docs-excerpts.txt` (`permissions.md`, `settings-reference.md`, `cli-reference.md`, `hooks.md`) were not in
the review's mirror. The author's captures of the exact bytes are held in the private research record (their sizes and sha256 are those of the receipt; they are not added here, about 0.8 MB of vendor text),
and a live fetch no longer has to return the same bytes: attach the captures to the next read's packet, or record a supersession with new hashes and locators; three historical hostname substrings of `manifests/evidence.json` (inherited, none added) wait for the registry cleanup. The verdict's research item 6 is queued, not decided here: which supported native launch and resume contract preserves the coordinator overlay while separately authorized research sessions keep their intended tool policy; the record's "What is not covered" (a resume through a route that omits `--settings`; a subagent that shares the marked session's tool list) is its starting point, and a different candidate waits for that measurement.

## Alternatives

- **`onFailure: "block"` on the shared entry** (the audit's proposal): rejected by the ruling. It would block WebSearch in every session, marked or not, whenever the runner fails.
- **Keep the hook's denial and add the overlay:** two enforcement points, one of which fails open. The hook's job is routing advice and the URL log; it is advisory so that no failure of it has a consequence.
- **Put the deny in the shared profile:** would deny unmarked lane and research sessions their WebSearch (#76's scope forbids it).
- **A project-level `.claude/settings.json` deny:** applies to every session in the checkout, marked or not.

## What is not covered

- The marked coordinators' launcher files are private to their owners and outside the repository; the overlay is the reviewed diff the command center applies (step 5).
- `--settings` is a per-launch overlay: a coordinator that is resumed through another route without it is not denied. The advisory hint is the only trace in that case.
- An in-process research subagent that shares a marked session shares its tool list and so its denial; the earlier recorded boundary (the hook's exemption of a nonempty `agent_id`) no longer applies to WebSearch.
- The native probe (`NativeClientProbeTests`) is opt-in (`NAS_NATIVE_CLAUDE_PROBE=1`): it starts the client. The receipts are the measurement; the continuous integration holds the overlay, the registrations and the applier.

## Overturn conditions

- A client release that lets a `permissions.deny` rule of a `--settings` overlay be bypassed by a hook or a mode (`receipts/tool-lists.json` and the opt-in probe are the re-measurement).
- A client release that changes the exit-2 or non-blocking semantics of hooks (`docs/en/hooks.md` L786-L800): the wrapper's reason and the measurement table are re-read.
- The research runtime's own denial of WebSearch moving into a managed policy: the overlay is then the managed one.
