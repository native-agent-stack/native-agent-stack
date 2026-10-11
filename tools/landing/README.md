# Landing scripts

The command center (CC) lands pull requests with three files kept here, so the repository holds the one copy and its tests:
`uet_land.sh` (the private trading repository), `nas_land.sh` (this repository) and `codex_gate.py` (the Codex review gate that
both call). They merge pull requests. No workflow runs them: the CC runs them from a clone of this repository, and CI runs
their tests.

## What each does

**`uet_land.sh <pr> <read-head-prefix>`** lands a pull request of `seathatflowsinourveins/us-equities-trading` by squash
merge. In order: the `trading-cc-read` commit status and its record (below); each file in `VERDICT_FILES` (and `GATES_DONE`
when such a file states a landing gate); the head is the read head or a pure rebase of it; a draft is marked ready and
`codex_gate.py` must report the latest review finished (polled for up to 20 minutes); when Codex reports its usage limit,
`GPT_VERDICT` (the co-op's verdict naming the read head) stands in for it; the branch is updated by rebase and its change must
equal the read change; CI is complete with nothing failing and `ci-gate` reported (a head that moves during CI is followed, at
most three times, only when it carries the read head's change, otherwise exit 3); open review threads stop it (exit 8); the merge
is pinned to the head with `--match-head-commit` and names the account's no-reply address as its author (below).

**`nas_land.sh <pr> <read-head-prefix> <verdict-file>...`** does the same for `seathatflowsinourveins/native-agent-stack`,
with the verdict files as arguments (at least one) and these differences: `manifests/evidence.json` is left out of the change
identity (CI arbitrates the registry), a BEHIND branch is updated server-side (merge method), the aggregate `validate` check
must have succeeded at the head (the latest run per check name counts), and just before the merge the head is merged into the
current `origin/main` in a temporary worktree under `/var/tmp` where `scripts/validate.py` must exit 0 (exit 10 otherwise).

**`codex_gate.py <owner/repo> <pr>`** prints one status line about the connector's review and exits 0 (a review finished at or
after the latest trigger and none is running), 3 (running, or none finished since the latest trigger: poll again), 4 (the latest
review ended other than Completed, or the gate itself failed: any exception, a failed `gh` call included, prints one fixed line
naming only the error class, never a traceback, which would print file paths, or `gh`'s output; #975 P2), or 5 (Codex is
unavailable: a usage-limit or account notice since the trigger, or no connector activity for 10 minutes). Both scripts stop with
exit 9 on a 4, at the wait and just before the merge. A trigger is the pull request's creation, a ready-for-review event, or a
comment by anyone but the connector that starts with `@codex review` or `@codex security review`; a push is not a trigger. Any
completion evidence since the trigger (a Completed row, a connector review, a +1 reaction, its no-findings comment) gives 0 even
when a later row says Cancelled; a Running row always gives 3.

**The author address (CC correction #148).** GitHub authors a squash merge with the account's primary email unless the merge names
one, which published the owner's personal address on every landing. Both scripts form the no-reply address
`<id>+<login>@users.noreply.github.com` (`lg_author_email`: the login is the repository owner, the id comes from the public
`gh api users/<login> --jq .id`, and `gh api user` is never called; a non-numeric id is a failure), pass it to the squash merge with
`gh pr merge -A`, and afterwards compare the merge commit's author with it (`lg_author_check`, inside `jq`; it prints text only and
never an address, and reads the merge commit up to five times). The owner's setting "Keep my email addresses private" fixes the
source and also covers merges made in the web UI; this is the script-side guarantee.

**The CI gate (#975 P2-3).** A completed check fails unless its conclusion is success, neutral or skipped; any other conclusion, null
included, stops a landing with exit 5 even when the aggregate check (`ci-gate` in `uet_land.sh`, `validate` in `nas_land.sh`)
succeeded. The rule is an allow-list, which fails closed on a conclusion it does not know, because the sources disagree on the list:
GitHub's GraphQL enum `CheckConclusionState` has nine members, ACTION_REQUIRED, CANCELLED, FAILURE, NEUTRAL, SKIPPED, STALE,
STARTUP_FAILURE, SUCCESS and TIMED_OUT (https://docs.github.com/public/fpt/schema.docs.graphql, sha256 `3ed09565…`, lines
3974-4018, captured 2026-10-11), while the REST description's check-run conclusion (`github/rest-api-description@58b1e0c00b39`,
`descriptions/api.github.com/api.github.com.json`, `components.schemas.check-run.properties.conclusion`) lists seven values and is
nullable: it leaves out `stale` and `startup_failure`, which its check-suite conclusion lists. Before this rule `uet_land.sh` counted
FAILURE, CANCELLED and TIMED_OUT as failing and `nas_land.sh` also `action_required`, so a check that ended any other way did not
stop a landing by itself. `tests/fixtures/landing/check-conclusion-state.json` holds the captured excerpt, and the tests run each of
its members, and null, through both scripts.

`uet_land.sh` also reads the commit statuses in the rollup (`StatusContext`, such as `trading-cc-read`), by the same rule: SUCCESS
passes, PENDING and EXPECTED count as running, and any other state, null included, fails with exit 5 (#975 P3). GraphQL's
`StatusState` has five members, ERROR, EXPECTED, FAILURE, PENDING and SUCCESS (the same schema file, sha256 `3ed09565…`, lines
65267-65292; `StatusContext.state` is `StatusState!` at line 65236), and the rule used to fail only FAILURE and ERROR, so a member
added later would have passed. `tests/fixtures/landing/status-state.json` holds that excerpt; the tests run each member, a state
outside it and none through `uet_land.sh`. `nas_land.sh` judges check runs only.

**A failed merge (#975 P2-2).** `gh pr merge` can print an address in its diagnostic, so neither script echoes it: exit 7 prints a
fixed message with a class taken from a fixed list of phrases (for example `not_mergeable` or `head_branch_was_modified`, otherwise
`other`), and the raw output goes only to a file made by `mktemp "${TMPDIR:-/tmp}/merge-fail-XXXXXX"` (mode 0600). The message names
only that file, not its path, because the directory can hold the account name.

## Variables

| Variable | Default | Used by | Meaning |
| --- | --- | --- | --- |
| `LANDING_UET_REPO` | `$HOME/code/us-equities-trading` | `uet_land.sh` | clone of the trading repository: fetches, `rev-parse`, change identity (the path must not contain whitespace) |
| `LANDING_NAS_REPO` | `$HOME/code/native-agent-stack` | `nas_land.sh` | clone of this repository, used the same way (no whitespace) |
| `LANDING_COORD` | `${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/coordination` | both | coordination tree; a status description `PASS: trading-cc/reads/<record>.md` names `$LANDING_COORD/trading-cc/reads/<record>.md` |
| `LANDING_GATE` | `codex_gate.py` in the directory of the script, symlinks resolved (`readlink -f "$0"`) | both | the Codex gate; it works through a symlink or a wrapper that `exec`s the real path, and not when the script is read from a pipe or a process substitution (set this variable then) |
| `VERDICT_FILES` | none | `uet_land.sh` | space-separated verdict files that each must name the read head |
| `GATES_DONE` | none | both | receipt naming the read head; required when a verdict file states a landing gate |
| `GPT_VERDICT` | none | `uet_land.sh` | the co-op's verdict file accepted instead of Codex when `codex_gate.py` exits 5 |
| `TMPDIR` | `/tmp` | both | where a failed merge keeps gh's output (`merge-fail-XXXXXX`, mode 0600) |

The scripts also need `gh` 2.48.0 or later (`gh api --paginate --slurp`; authenticated for the repository), `git` 2.39.0 or
later (`git patch-id --verbatim`), `jq`, `python3` 3.7 or later, GNU `grep`, `sha256sum` and `readlink -f`. They run under
`set -u`, so `HOME` must be set whenever a default above is used.
`nas_land.sh` also needs a git committer identity: its validation merge (`git merge --no-commit`) refuses to start without
one, and the script then reports exit 10, "does not merge cleanly".

## Exit codes

From the script headers. `uet_land.sh`: 2 verdict gate, 3 head moved, 4 change differs, 5 CI failed, 6 timeout, 7 merge failed,
8 blocked, 9 Codex review running, not finished since its latest trigger, or ended other than Completed (`codex_gate.py`).
`nas_land.sh`: 2 verdict gate, 3 head moved, 5 CI failing, 6 timeout, 7 merge failed, 8 blocked by policy, 9 as above, 10 the
merge onto current `origin/main` fails `scripts/validate.py` or does not merge cleanly. Its header omits one code it also uses:
4 when `update-branch` is refused or the change differs after it. Both scripts also exit 11 when the no-reply author address cannot
be formed (nothing is merged) and 12 when the merge landed but its commit's author is not that address or the commit could not be
read (CC correction #148). `codex_gate.py`: 0, 3, 4 and 5 as above; a gate that fails itself exits 4, which both scripts stop on
with 9.

## The record convention

A record (append-only, many heads) is accepted for a head when the last line that gives a verdict for it carries PASS or ACK. End
every section that gives or changes a verdict with a line of its own:

```
Verdict: PASS at <head8>
```

(or `ACK`, or `CHANGES_REQUESTED`; `Gate line: PASS at <head8>` is the same). A verdict file is accepted by its line 1 in the Astra
layout `... <head>...: ACK|PASS`, or by its last `Gate line:`/`Verdict:` line naming the head with PASS or ACK;
CHANGES_REQUESTED on line 1 or as that last word rejects, and a PASS or ACK anywhere else counts for nothing. The
`trading-cc-read` description must be exactly `PASS: trading-cc/reads/<record>.md` or `ACK: trading-cc/reads/<record>.md`.

## Provenance and digests

The files were moved from the CC's tools directory on 2026-10-10 and synced on 2026-10-11 to the live copies the CC installed at
00:02Z (the head-following function of uet#58 and correction #148); #975's fix commit then took the CC's live patch of
2026-10-11T03:37Z (P2-3 and P2-2, above). At the sync the shell scripts were the live copies with only host paths changed: the three
lines of the move (the repository default and `COORD` on one line, the record path, the gate path), the same line counts, and
`codex_gate.py` byte for byte. Expanding the three expressions to the CC host's paths gave the digests of the "after #148" column.
The patched live copies also differ in the merge-failure line, whose file the CC keeps in its own tools directory until it takes
this line's `${TMPDIR:-/tmp}` after review (2026-10-11). The review of that fix commit then led to two more changes, made here and
not yet in the live copies: `codex_gate.py` catches any exception and exits 4 with one fixed line (#975 P2), and `lg_ci_state` in
`uet_land.sh` fails a commit status unless its state is SUCCESS, PENDING or EXPECTED (#975 P3; one more comment line). The "Here"
column is each file as committed: its sha256 and line count.

| File | Before correction #136 | Live copy, after #148 | Live copy, after #975 P2 | Here |
| --- | --- | --- | --- | --- |
| `uet_land.sh` | `b794e3a46772c0a598dff9eee972ad449e5d63f0c81b60b9db1d5cb4944747bb` (115 lines) | `301fb5b07274b28fde0f2061356bf9682883eca352c8bcb7a3119e8934920c7d` (232 lines) | `1bc1f53b3ddd7563a6d3a0ea1a4db296767df64197c00b1bc0ff6e23c528476c` (233 lines) | `9518ca6c0464054a40cbec8bcccdb577294a75d941c773e4461ff8f31db79b09` (234 lines) |
| `nas_land.sh` | `2fefe070b95229de3dcad14052cf5c031b70c202bf4a34f4452e6e0cb5832936` (135 lines) | `96144670bc301036604fc39e57e3ab4e4a2e43a6b9d6b8b645ef7b02482f4017` (243 lines) | `287f2e7e162a0dd8df28803c72eeb96591a2d936c513d981bcac24512139e0bd` (246 lines) | `bd6aa8c78c86070123c260868ffe7e5cbb857a2a8b58eb41606573bfdba6400e` (246 lines) |
| `codex_gate.py` | (unchanged) | `31524d2871cde79ecb2c5b9bc56b6175ce9fafab9ad4d2e2e3eb3594e1cb2422` (108 lines) | the same | `cc96f69b411b76652b1d024988d3bb374444a40dca6f175dd6559aa4de9e7a33` (114 lines) |

Corrections the scripts carry: #118 (every gate before the merge, in order), #121 (a verdict file that states a landing gate needs
a receipt), #122 and #123 (a Codex review must have finished; uet#40 and uet#47 merged while one was running), #136
(verdict and record acceptance, change identity and the CI line: the three loose decision points the shared
`# >>> land-gate-fns` block replaced), the head-following of 2026-10-10 (uet#58: an update-branch rebase does not reach every API view at
once, so a head that moves during CI and carries the read head's change is followed, at most three times), #148 (the author address)
and #975's P2-3 (the CI allow-list), P2-2 (a failed merge prints no gh output), the gate error (P2: exit 4 and one fixed line, no
traceback) and the commit-status allow-list (P3). The block is identical in both scripts, apart from `lg_ci_state`, which only
`uet_land.sh` has.

## Known gaps, left as they were

The files began as the live copies with host literals replaced and now also differ from them where the provenance section above says
so (the merge-failure line, the gate's exit 4, the commit-status allow-list). These stay until a change with its own tests fixes them:

- `U` and `G` are expanded unquoted: a clone path with whitespace breaks both scripts.
- `nas_land.sh`'s header leaves out exit code 4, and its validation merge needs a git identity (above).

## Tests

`tests/test_landing_scripts.py` is correction #136's regression: it cuts each decision site out of the script text (the same
start and end lines the correction's harness used) and runs it in bash with a fake `gh`, against synthetic verdict files,
records, scratch repositories and rollups; it runs `codex_gate.py` on canned API data and, as the scripts run it, against a failing
fake `gh` (one fixed line naming the error class, exit 4, no traceback); and it runs both scripts end to end with a fake `gh`,
`python3` and `sleep`, including the gate path through a symlink and a wrapper, a head that moves during CI (followed three times,
then exit 3), a gate that fails (exit 9 at the wait, through the real gate, and before the merge) and the author address (the
merge argv, exits 11 and 12, no address in the output). It also runs every `CheckConclusionState` member of the fixture, and null,
through both CI gates (exit 5 before any merge unless success, neutral or skipped), every `StatusState` member of its fixture, a
state outside it and none through `uet_land.sh` (SUCCESS merges, PENDING and EXPECTED wait, the rest exit 5), a failed merge (exit
7 with a class and no gh output, which stays in a 0600 file), a check that the "Here" digests above are those of the committed
files, and a scan of every file under `tools/landing`, bytecode excepted, for home paths and for the running account's name, bare,
hyphenated, percent-encoded, hex or base64 (#975 P2-1). It is offline, needs `jq`, and is Linux-only. A script edit that moves a
decision site fails the module instead of leaving it untested.

The account-name scan is skipped for a generic CI or container account name (`runner`, `root`, `ubuntu`, `user`, `admin`, `vscode`,
`codespace`, `ec2-user`, `node`, `docker`) and for a name of fewer than 4 characters, and the home-path scan still runs: such names
are ordinary words, or short enough to occur in unrelated text, so scanning for them would fail the module on prose rather than on
a leak.
