# The skill list is sent again after a compaction — 2026-10-14

## Decision

The Claude settings template carries one more SessionStart hook: on the `compact` source it returns
`reloadSkills: true`.

```json
{
  "matcher": "compact",
  "hooks": [
    {
      "type": "command",
      "command": "jq -cn '{hookSpecificOutput: {hookEventName: \"SessionStart\", reloadSkills: true}}'",
      "timeout": 5
    }
  ]
}
```

It has no `onFailure`: a hook that cannot run leaves the session as it was before this change.

## Why

Claude Code tells the model which skills exist through a list in the conversation. After a compaction the client does
not send that list again, so the model keeps the Skill tool but no longer knows what it could load. A long session
compacts every few hours and then works without the list until it is restarted.

On this host on 2026-10-14, 37,476 of 41,650 main-thread tool calls in the live Claude sessions (90%) were made after
the session's first compaction and so without the list, and those sessions made 7 Skill calls in all. The counts and
their method are in the command center's diagnosis of that day, which is outside the repository; the mechanism below is
what this record proves.

## Sources

- **Hooks reference**, `https://code.claude.com/docs/en/hooks.md`, fetched 2026-10-14T04:20:16Z, 270,367 bytes, sha256
  `0ccea55b53b6b616134028b857028cf3822b89958a9c4b23806287dddeefe954`:
  - line 1214, the SessionStart matcher table: `compact` fires on "Auto or manual compaction";
  - line 1276, SessionStart decision control: `reloadSkills` is a "Boolean. When `true`, Claude Code re-scans the skill
    and command directories after the SessionStart hooks complete";
  - lines 1294-1296, "Reload skills that a hook installs".
- **CHANGELOG** of `anthropics/claude-code` at commit `db93774d73e8fdbaf315a6f4c175ae99ad3d515a`, 1,015,061 bytes,
  sha256 `7abf62a98e6739e0b51071c5e289b0a6baef4f3a2d08046a6df2b338b3d0d086`:
  - line 5008, section 2.1.152: "`SessionStart` hooks can now return `reloadSkills: true` to re-scan skill directories,
    making skills installed by the hook available in the same session";
  - line 149, section 2.1.299: "Improved `/reload-skills` to say it re-sends the full skill list to Claude, which is how
    to get skills back after compaction".
- **The installed clients**, 2.1.296 (binary sha256 `24972e3bc859fab2b46ed4c1e51f7d6130f06d3bd550811a114640de3370d0de`)
  and 2.1.299 (`2d894a4b1bfaaa9aab72aeff7803e3c73bc2510f279a171f6b8f59f72d17d077`). Both keep a set of the skill names
  already sent and attach only names outside it. The set is cleared by `/clear`, by `/reload-skills`, by a plugin or
  skill-directory reload, by a change of working directory, by the SDK's `reload_skills` request, and by a SessionStart
  hook that returns `reloadSkills`. A compaction is not among them.

The documented purpose of `reloadSkills` is a hook that installs skills. Sending the list again is the same reset seen
from the model's side, and the changelog's own remedy for a compacted session, `/reload-skills`, takes that path.

## Evidence on this host

`evidence/artifacts/skill-list-reload-after-compact-20261014/` holds the probe and its receipt. The probe runs the real
client binary in a scratch home against a loopback stand-in for the Messages API that records every request body: no
model, no credential, no network beyond 127.0.0.1, no spend. The hook under test is read from the settings template.
Each arm is one client process with four or five turns.

| Arm | Compaction | Without the hook, requests after it | With the hook, requests after it |
| --- | --- | --- | --- |
| `manual` | `/compact` typed as a turn | 2 of 2 without the list | 2 of 2 with the list |
| `auto` | automatic, before the second turn's request | 3 of 3 without | the first without, the next 2 with |
| `auto-tool` | automatic, inside a turn that calls a tool | 5 of 5 without | the first without, the next 4 with |

The result is the same on 2.1.296 and 2.1.299. In every arm the Skill tool stays offered and every request before the
compaction carries the list.

After an automatic compaction the first request goes out without the list, because the client had gathered that
request's attachments before the hook ran. The list is in the second request, also when that request belongs to the
same turn.

## Alternatives considered

- **Typing `/reload-skills` after each compaction.** It is the changelog's remedy and needs the owner at every session's
  terminal several times a day.
- **Printing the list from a hook as added context.** It would duplicate text the client already builds, drift from the
  client's budget and ordering, and still not reset the client's own set.
- **Naming every skill in CLAUDE.md.** Always-on context for every session and subagent, and a second copy to keep in
  step with the installed set.
- **A hook file under `adoption/hooks/claude/`.** A copied file, a byte pin and an interpreter start for one constant
  line. `jq` alone is a command word the client-configuration check already allows and the bootstrap already installs.
- **Restarting sessions.** A resume does send the list again, and loses the session's cached context.

## Risk

- **Cost.** One list per compaction: about 30,000 characters on this host (81 to 87 skills). A session here compacts
  near 967,000 tokens, so the list is under 1% of what a compaction cycle already carries.
- **Subagents.** The reset covers the whole client process, so a running subagent that has the Skill tool also gets the
  list again on its next request. That cost was not measured.
- **A missing `jq`.** The hook fails, nothing is reloaded, and the session behaves as it does today.
- **It is not sufficient for skill use.** With the list present the same sessions still made 2 Skill calls in 4,174 tool
  calls. Coordinator turns start from task notifications and rarely match a generic skill. Naming skills in launch
  briefs and preloading them on subagent definitions is separate work.

## Applying it to a host

`tools/adoption/apply_claude_settings.py` merges the template into `~/.claude/settings.json`; a second apply adds no
second copy, and a host's own hook on the same source is kept. Stored client configuration is the command center's to
change: it applies this at a checkpoint relaunch, one session first.

## Inverse

Remove the group from `~/.claude/settings.json` (and from the template by a pull request). No state is left behind:
the hook writes nothing.

## Tests

`tests/test_skill_list_reload_hook.py` (14 tests): the template has exactly this group and no other SessionStart source
reloads the skills; the hook has no `onFailure` and a short timeout; its command prints the documented output on one
line; the settings merge carries it once; and the receipt was taken with the entry the template ships and shows the
arms above. On main's template 7 of the 14 fail (`receipts/fail-before.txt`); 16 of 16 mutants of the entry and the
receipt are killed (`receipts/mutants-16.txt`).

`tests/test_new_wsl_client_config.py` changes in one test, declared in the addendum of 2026-10-14 to
`2026-10-02-new-wsl-client-configuration.md`: the rendered settings may carry this one command, exactly once.

## Evidence classes

| Claim | Class | Receipt |
| --- | --- | --- |
| After a manual or an automatic compaction the requests carry no skill list, on 2.1.296 and 2.1.299 | `native_proven` (real client, loopback stand-in) | `receipts/arms.json`, control arms |
| The template's hook brings the list back from the next request (manual) or the second request (automatic) | `native_proven` (same) | `receipts/arms.json`, hook arms |
| `compact` covers automatic and manual compaction; `reloadSkills` re-scans the skill directories | `source_review` | hooks reference, lines 1214 and 1276 |
| The set of sent names is cleared in six places, a compaction not among them | `source_review` | the two installed binaries |
| The hook after an idle compaction | not measured | - |
| 90% of main-thread tool calls ran without the list | measured outside the repository | the command center's diagnosis of 2026-10-14 |

## Overturn when

A client release sends the skill list again after a compaction by itself (the control arms of the probe then show the
list), or changes what `reloadSkills` does, or a measured cost of the reload outweighs it.
