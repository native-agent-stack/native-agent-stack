# A marked coordinator's WebSearch is denied natively at launch; the shared hook is advisory and cannot exit 2, 2026-10-13

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
| UserPromptSubmit entry, existence-checked registration, same missing file | - | the prompt runs |

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
3. **Both registrations are existence-checked**, as the secret-path guard's is: `f="${HOME}/.claude/hooks/research-routing-guard.py"; [ -f "$f" ] && exec python3 "$f"; true`. A missing file cannot exit 2, so
   it cannot block a prompt or a tool call; an advisory hook that is not there is silent. (The secret-path guard keeps its own fail-closed form: it is the one that must refuse.)
4. **The settings applier retires the replaced command.** `merge_hooks` de-duplicates by command, so the bare `python3 "<home>/.claude/hooks/research-routing-guard.py"` already on a host would have run beside
   its wrapped replacement (the fetch log counting every URL twice). `tools/adoption/apply_claude_settings.py` gains `SUPERSEDED_HOOK_COMMANDS`, a finite allowlist matched as the held-out carriers are (exact
   string, HOME as written or another spelling of the settings file's own home, nothing else parsed), retired unless the incoming template runs the same command, whether or not the host keeps its held-out carriers.
5. **Host step, the command center's act** (this change writes no host configuration): add `--settings <path to the overlay>` to the launch of each marked coordinator (the two launchers that set
   `NAS_RESEARCH_COORDINATOR_ROLE`), and re-apply the profile template (`apply_claude_settings.py`) so that the two registrations become the existence-checked ones. Until the first is made the marked
   coordinators are as they were: the hook (now advisory) no longer denies them, so the launch step is what restores enforcement; do it in the same act.

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
