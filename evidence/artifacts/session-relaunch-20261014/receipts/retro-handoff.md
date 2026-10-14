# Automatic relaunch after an unplanned WSL restart (written 2026-10-14T12:49:30Z by session_relaunch.py; no session wrote it)

## For the command center (wsl-architecture-design)
- There is no outgoing command center: the earlier one died in the restart. Do not wait for one or send it READY;
  take over directly from your own last handoff and tracker.
- The sessions in the table below start after you and send you READY by name.
- Not relaunched (no launcher profile, or already running); your call:
  - librarium-course-e2 (interactive, no launcher profile): cwd ~/code/librarium-course; resume with `claude --resume 0d2e4ed6…`

## What happened (read by the tool)
- The previous boot (a84c7d5283d54dee8de81e0c792dcaa0) ended at 2026-10-14T06:41:17Z; this boot's journal starts at 2026-10-14T12:49:00Z.
- The last roster of that boot was written at 2026-10-14T06:40:30Z and lists 7 sessions. 6 are relaunched now, fresh, each with this file as its handoff.
- No session wrote a handoff for this stop. Every Claude session and every transient systemd-run unit of that boot
  died with it; persistent linger units start again by themselves.

## How each relaunched session recovers its state
1. Find your old session in the table below and its transcript.
2. Read your last handoff: your old transcript's first prompt names it.
3. Read the work since that handoff: `python3 -I ~/.local/state/native-agent-stack/coordination/command-center/cc-tools/relaunch-20261014/transcript_tail.py <old transcript> --turns 120 --chars 600`.
4. Read the command center's tracker and its rulings since your last handoff.
5. Re-arm what died: units, watchers, Monitors, Codex lanes, readers. Re-run a reader or builder killed mid-run from
   its packet; never trust a partial verdict file.
6. Send the command center (wsl-architecture-design) one line: READY, this file's sha256, what you do first. Then work.

This file authorizes nothing new: every lane keeps its own rules (trading work reads blueprints/us-equities/AGENTS.md).

## Sessions relaunched
| name | launcher | old session id | cwd | old transcript |
|---|---|---|---|---|
| wsl-architecture-design | cc | afa68669… | ~/code/native-agent-stack | ~/.claude/projects/-home-<user>-code-native-agent-stack/afa68669….jsonl |
| trading-cc | trading-cc | 5bc7f7b9… | ~/code/us-equities-trading | ~/.claude/projects/-home-<user>-code-us-equities-trading/5bc7f7b9….jsonl |
| ns2604-coop | coop | d063c490… | ~/code/native-agent-stack | ~/.claude/projects/-home-<user>-code-native-agent-stack/d063c490….jsonl |
| api-actions | api-actions | c3a33d96… | ~/code/native-agent-stack-api-actions | ~/.claude/projects/-home-<user>-code-native-agent-stack-api-actions/c3a33d96….jsonl |
| native-agent-stack-d4 | d4 | 01804618… | ~/code/native-agent-stack | ~/.claude/projects/-home-<user>-code-native-agent-stack/01804618….jsonl |
| cc-native-practice | cc-native-practice | a4f28181… | ~/code/native-agent-stack | ~/.claude/projects/-home-<user>-code-native-agent-stack/a4f28181….jsonl |
