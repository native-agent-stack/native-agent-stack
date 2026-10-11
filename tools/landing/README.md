# Landing scripts

The command center (CC) lands pull requests with three files kept here, so the repository holds the one copy and its tests:
`uet_land.sh` (the private trading repository), `nas_land.sh` (this repository) and `codex_gate.py` (the Codex review gate that
both call). They merge pull requests. No workflow runs them: the CC runs them from a clone of this repository, and CI runs
their tests.

## What each does

**`uet_land.sh <pr> <read-head-prefix>`** lands a pull request of `seathatflowsinourveins/us-equities-trading` by squash
merge. In order: the landing lock of the repository (exit 14 when another landing holds it; below); the `trading-cc-read` commit
status and its record (below); each file in `VERDICT_FILES` (and `GATES_DONE` when such a file states a landing gate); the head is
the read head or a pure rebase of it; a draft is marked ready and `codex_gate.py` must report the latest review finished (polled for
up to 20 minutes); when Codex reports its usage limit, `GPT_VERDICT` (the co-op's verdict naming the read head) stands in for it; the
branch is updated by rebase and its change must equal the read change; CI is complete with nothing failing and `ci-gate` reported (a
head that moves during CI is followed, at most three times, only when it carries the read head's change, otherwise exit 3); open review
threads stop it (exit 8); the no-reply author address is formed; the final gate reads every gate again (below); the merge is pinned to
the head with `--match-head-commit` and names the account's no-reply address as its author (below).

**`nas_land.sh <pr> <read-head-prefix> <verdict-file>...`** does the same for `seathatflowsinourveins/native-agent-stack`,
with the verdict files as arguments (at least one) and these differences: `manifests/evidence.json` is left out of the change
identity (CI arbitrates the registry), a BEHIND branch is updated server-side (merge method), the aggregate `validate` check
must have succeeded at the head (a check name is incomplete while any of its runs is, and judged on its latest completed run), the
Codex gate is asked again before the validation, and the head is then merged into the current `origin/main` in a temporary worktree
under `/var/tmp` where `scripts/validate.py` must exit 0 (exit 10 otherwise). Its output is never printed: it goes to a file made by
`mktemp "${TMPDIR:-/tmp}/nas-validate-XXXXXX"` (mode 0600) outside the worktree, and exit 10 names that file and the exit code. `gh pr
merge --match-head-commit` pins only the head ("Commit SHA that the pull request head must match to allow merge", sources below), so
`origin/main` is read again with `git ls-remote` after each validation: when it moved, the merge onto the new main is validated again,
at most three validations in all (exit 13 when it moved after each; #975, Codex P2 at af9d1901), and the final gate reads it once more.

**`codex_gate.py <owner/repo> <pr> [<read head>]`** prints one status line about the connector's review and exits 0 (a review of the
read head or of the current head that started at or after the latest trigger finished, and none is running), 3 (running, the
connector's 👀 reaction on the pull request, none of those heads that started since the latest trigger finished, or a summary whose
newest revision is not its body: poll again), 4 (such a review ended other than Completed, a summary last edited by an account other
than the connector, or the gate itself failed: any exception, a failed `gh` call included, prints one fixed line naming only the error
class, never a traceback, which would print file paths, or `gh`'s output; #975 P2), or 5 (Codex is unavailable: a usage-limit or
account notice since the trigger, or no connector activity for 10 minutes). Both scripts stop with exit 9 on a 4 at any call, and on a 3
at any call but the wait, which polls a 3 for up to 20 minutes. A trigger is the pull request's creation, a ready-for-review event, or a comment by anyone but the connector that
starts with `@codex review` or `@codex security review`; a push is not a trigger. A Running row always gives 3.

**Which review a completion belongs to (#975, Codex P1 at af9d1901).** A review that was running when the latest trigger came and
finished after it is not the requested review, but its completion time alone passed the gate, so a landing could merge in the gap
before the new review's Running row appeared. The connector keeps one summary comment per pull request and edits it in place: a row
`Running since <start>` (with the review kind, the commit and the trigger kind in its other cells) becomes `Completed <end>`, and the
next review rewrites the row (measured 2026-10-11 on nas#974, #975, #979 and #994 through GraphQL `userContentEdits`, whose `diff`
held the whole body of each revision, newest first). So a Completed row counts only when the latest earlier revision that shows the
same row Running started at or after the trigger; the connector's +1 reaction (its all-reviews-finished signal) counts only at or
after such a start; a connector review and its no-findings comment name no request and no longer count. A Completed row with no
such revision is not attributed (fail closed: 3, or 5 without connector activity). Completion evidence after such a start wins
over a later Cancelled row, as before.

**One snapshot, the reviewed commit and the editor (#975 round 4: the CC's micro, the GPT micro and Codex at 761810d7).** The body came
from REST and the revisions from a later GraphQL call, and a completion was paired with the newest Running revision of its row, also one
that started after it: when the connector edited the summary between the two reads, a review that finished at 12:08 passed for a 12:10
trigger (exit 0). Now one GraphQL query returns each comment's author, body, `fullDatabaseId` (a `BigInt`; the ids passed 2^31, beyond
the `Int` that `databaseId` is) and 100 newest revisions with their editors; a summary whose newest revision is not its body was read
during an edit and gives 3 (the newest revision equalled the body on every summary read, nas#975's captured in
`tests/fixtures/landing/codex-summary-comment.json`, body sha256 `1236fe48…`); and a completion pairs only with a start at or before it,
so trigger <= start <= completion. Only the connector's revisions count, and a summary last edited by another account gives 4. The
attributed row's commit cell must be a prefix of the read head (the scripts pass it) or of the current head, otherwise 3 (a replay of
nas#1009 had passed on a review of the commit before a force-push). The connector's 👀 reaction on the pull request gives 3: its footer
says "Codex reacts with 👀 while any review is running". And an edit of a summary, or a row's time, at or after the trigger counts as
connector activity, so a completion that cannot be attributed stays 3 instead of turning into "no connector activity" (5) after ten
minutes (GPT P2).

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
only that file, not its path, because the directory can hold the account name (`mktemp` prints the path it made, and creates the
file exclusively with mode 0600; sources below).

**Nothing `gh` or its API returned is printed (#975 P2-2, review of 754a194f).** The failed merge was one path; two more were open.
A failing `trading-cc-read` status printed its description, which can carry an address; it now prints its state when that is
`error`, `failure` or `pending` and `unknown` for any other, and never the description (this is the line the CC's live copies took).
Every other `gh` call drops its stderr (`2>/dev/null`), and a call that fails ends in the fixed message and exit code its step already
had: an unreadable head is exit 3 or 4, an unreadable CI state exit 3 (`uet_land.sh`) or a timeout, exit 6 (`nas_land.sh` check runs),
an unreadable address id exit 11. Dropping stderr is not enough for `gh api`, because for an error response it copies the response
body to stdout, prints `gh: <message>` to stderr and exits non-zero; a captured value can therefore be raw API text. The status gate
maps the state as above, and `uet_land.sh` prints the number of unresolved review threads as a number, or `unknown` (exit 8 as before).
The tests fail each call site in turn with a synthetic address on both streams and check the exit code, that nothing was merged where
the step stops a landing, and that the address is not in the output (sources below).

**Typed values and local diagnostics (#975 round 3, GPT P2-B and P2-C at af9d1901).** Dropping stderr did not cover a value that is
parsed: `nas_land.sh` word-split a failed check-run call's stdout into its counts, so a body `0 0 <address> 1` reached bash's "integer
expected" diagnostic on every poll and a body `0` ended the script on an unbound `$4`, with its path. Every value from `gh` is now used
only in its typed shape: a head is 40 lower-case hex digits (`lg_hex40`), the CI line is a head, four counts and a state word, the
check-run reply exactly four counts (a failed call or another shape counts as one check still running, so the loop polls on to exit 6),
and `mergeStateStatus` a capitalised word. The local commands print nothing of their own: every `git` call drops its stderr (git's
`die` writes "fatal: ..." with the path it was given to stderr), `codex_gate.py`'s output is echoed only when it is one of its own
status lines with exit 0, 3, 4 or 5 (`lg_gate`; otherwise one fixed line and exit 9, which covers python3's "can't open file
'<path>'", exit 2, and a traceback, exit 1, that the gate's own handler never sees), a missing gate file is one fixed line before
anything is marked ready (exit 9), a verdict file is named by its file name only, `validate.py`'s output stays in its file (above), and
a failed merge whose diagnostic cannot be kept (an unusable `TMPDIR`) says so in a fixed line (exit 7; before, `mktemp` printed the
template's path and the message named an empty file).

**Gates read again before the merge (#975, Codex P1 at af9d1901).** The `trading-cc-read` status and its record are mutable: a newer
status for the context supersedes an older one (the statuses list is "in reverse chronological order. The first status in the list will
be the latest one"), and the record is append-only. Both scripts ran `tcc_read_gate` only at the start, before tens of minutes of Codex
and CI waits; they read it again before the merge (exit 2). In `uet_land.sh` a gate result of 5 needs `GPT_VERDICT` at both gate calls:
the wait could give 0 and the call before the merge 5 (an `@codex review` during CI that met the usage limit), and that landing merged
with neither a finished review nor the substitute. `nas_land.sh` proceeds on a 5 by its own policy, unchanged.

**One final gate after every slow step (#975 round 4, the CC's micro at 761810d7).** Each round-3 re-read closed one gap and left the
next: the verdict files and `GATES_DONE` were read only at the start, a failed `trading-cc-read` read with nothing on stdout passed as
"no status", and `nas_land.sh` asked Codex before up to three validations of 56 s each (a review started by then was never seen). The
scripts now run in this order: the landing lock; early refusals (cheap reads); the slow steps (ready, the Codex wait, update-branch,
the CI wait, nas's validations, the author-address lookup); `final_gate`, fast reads only; the merge pinned with
`--match-head-commit`; the author check. `final_gate` reads, in order:

1. the head, which must be the pinned head and carry the read head's change (exit 3, or 4);
2. every verdict file and `GATES_DONE`, through the function the early check uses (exit 2);
3. the `trading-cc-read` status and record, with `gh`'s exit code kept apart from its output: a failed call stops (exit 2), and only
   exit 0 with nothing printed is "no status";
4. the Codex gate, where a 5 needs an accepted `GPT_VERDICT` again in `uet_land.sh` (exit 9);
5. CI at the head: complete, green, with `ci-gate` (uet) or `validate` (nas) succeeded (exit 5; uet also exit 8 when BLOCKED);
6. in `nas_land.sh`, `origin/main` by `git ls-remote`, which must be the main the merge was validated on (exit 13).

Nothing slow runs between `final_gate` and the merge; the tests flip each gate between its first read and `final_gate` and check the
exit code and that no merge is called (12 of the 17 flips merged at 761810d7). A verdict file, record or receipt is read once (`lg_text`),
and each decision about it is made on that one text, so a file removed or rewritten between two reads cannot pass on half of each, and a
read that fails is a refusal with a fixed message that names no path (GPT P2 at 761810d7).

**The landing lock (#975 round 4).** Both scripts first open `<LANDING_LOCK_DIR>/<repository name>.lock` (default
`$LANDING_COORD/command-center/landing-locks`, outside every worktree) on descriptor 9 and take an exclusive `flock -n` on it, held until
the script exits; a second landing of the same repository stops at once with exit 14 before any call, as does a lock that cannot be
opened (its path is not printed). Every `git`, `gh`, `python3` and `sleep` the scripts run is called with descriptor 9 closed, so no
child keeps the lock after the script: a `git fetch` starts automatic maintenance that detaches and keeps every descriptor but 0-2
(sources below).

**What the final gate narrows but cannot close.** A read and the merge call are separate requests, and GitHub's merge takes one pin, the
expected head:

- **Server-backed:** the head pin (`expectedHeadOid`), thread resolution and the required checks (uet: `ci-gate`, strict up-to-date;
  nas: seven required checks; the rulesets as the CC's micro at 761810d7 read them), which GitHub enforces at the merge whatever the
  script read.
- **Local only, narrowed to seconds:** the verdict files, `GATES_DONE`, `trading-cc-read` (not a required check in either ruleset), the
  Codex gate, `GPT_VERDICT` and nas's base. A change in the seconds between the final gate's read and the merge call is not seen. For nas's
  base this is the GPT micro's A5: the merge is not bound to the validated main, so a main that moves after the final `git ls-remote`
  takes a merge validated on the main before it.
- **Measured windows:** a Codex review goes Running 7-18 s after its trigger (11 reviews, the CC's micro at 761810d7; 14.5 s in the
  captured nas#975 summary, trigger 10:42:50Z, Running since 10:43:04.5Z), and the gate reads no trigger it has not seen, so a trigger
  in those seconds before the final gate's call can be missed; a later call sees it.
- **The closure path:** the review App and required checks of `docs/decisions/2026-10-09-review-verdict-app-identity.md` (an owner
  item), which would move the verdicts into checks GitHub enforces at the merge.
- **What the lock closes:** concurrent landings by our tooling, so our own landings no longer move main under each other's validated
  base; a merge made out of band (the web UI, another tool) is not covered.

## Variables

| Variable | Default | Used by | Meaning |
| --- | --- | --- | --- |
| `LANDING_UET_REPO` | `$HOME/code/us-equities-trading` | `uet_land.sh` | clone of the trading repository: fetches, `rev-parse`, change identity (the path must not contain whitespace) |
| `LANDING_NAS_REPO` | `$HOME/code/native-agent-stack` | `nas_land.sh` | clone of this repository, used the same way (no whitespace) |
| `LANDING_COORD` | `${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/coordination` | both | coordination tree; a status description `PASS: trading-cc/reads/<record>.md` names `$LANDING_COORD/trading-cc/reads/<record>.md` |
| `LANDING_GATE` | `codex_gate.py` in the directory of the script, symlinks resolved (`readlink -f "$0"`) | both | the Codex gate; it works through a symlink or a wrapper that `exec`s the real path, and not when the script is read from a pipe or a process substitution (set this variable then) |
| `LANDING_LOCK_DIR` | `$LANDING_COORD/command-center/landing-locks` | both | where the landing lock of each repository is kept (`us-equities-trading.lock`, `native-agent-stack.lock`); created when missing, and outside every worktree |
| `VERDICT_FILES` | none | `uet_land.sh` | space-separated verdict files that each must name the read head |
| `GATES_DONE` | none | both | receipt naming the read head; required when a verdict file states a landing gate |
| `GPT_VERDICT` | none | `uet_land.sh` | the co-op's verdict file accepted instead of Codex when `codex_gate.py` exits 5 |
| `TMPDIR` | `/tmp` | both | where a failed merge keeps gh's output (`merge-fail-XXXXXX`, mode 0600), and `nas_land.sh` the validation's output (`nas-validate-XXXXXX`, kept when it fails) |
| `LANDING_PROHIBITED_NAMES` | none | the tests only | comma-separated identities that must not appear in any form under `tools/landing` (see Tests) |

The scripts also need `gh` 2.48.0 or later (`gh api --paginate --slurp`; authenticated for the repository), `git` 2.39.0 or
later (`git patch-id --verbatim`), `jq`, `python3` 3.7 or later, GNU `grep`, `sha256sum`, `readlink -f` and util-linux `flock` (the
landing lock; without it every landing stops with exit 14). They run under `set -u`, so `HOME` must be set whenever a default above is
used.
`nas_land.sh` also needs a git committer identity: its validation merge (`git merge --no-commit`) refuses to start without
one, and the script then reports exit 10, "does not merge cleanly".

## Exit codes

From the script headers. `uet_land.sh`: 2 verdict gate (a verdict file, `GATES_DONE` or `trading-cc-read`, also when a file, record or
status cannot be read), 3 head moved, 4 change differs, 5 CI failed (at the final gate also: no longer complete and green), 6 timeout,
7 merge failed, 8 blocked, 9 the Codex gate gave neither 0 nor 5: a review running or not finished since its latest trigger (its 3, after
the 20-minute wait or at the final gate), a review that ended other than Completed or a summary last edited by another account (its
4), a gate that failed or is missing; or a 5 without an accepted `GPT_VERDICT` (#975 P3-7 at 761810d7: the header named only some of
these). `nas_land.sh`: 2 as above, 3 head moved, 4 `update-branch` refused or the change differs after it or at the final gate, 5 CI
failing (also at the final gate), 6 timeout, 7 merge failed, 8 blocked by policy, 9 as above, but a 5 proceeds, and a 3 before the
validation stops too, 10 the merge onto current `origin/main` fails `scripts/validate.py` or does not merge cleanly, 13 origin/main moved
after each of three validations, moved after the last validation (read at the final gate) or could not be read, so nothing is merged
(#975, new in round 3). Both scripts also exit 11 when the no-reply author address cannot be formed (nothing is merged), 12 when the
merge landed but its commit's author is not that address or the commit could not be read (CC correction #148), and 14 when another
landing of the same repository holds the landing lock or the lock cannot be opened or taken (nothing has run; #975 round 4).
`codex_gate.py`: 0, 3, 4 and 5 as above; a gate that fails itself exits 4, which both scripts stop on with 9.

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
`uet_land.sh` fails a commit status unless its state is SUCCESS, PENDING or EXPECTED (#975 P3; one more comment line). The review
of 754a194f (the GPT micro, CHANGES_REQUESTED) led to a third round, also made here: the status-gate failure line is the one the
CC's live copies already carry, and the rest is new to them: every other `gh` call drops its stderr, `uet_land.sh` prints the count
of unresolved review threads as a number or `unknown`, and each script has two more header comment lines (#975 P2-2, above). The
tests also scan for every prohibited identity (#975 P2-1, below). The review of af9d1901 (six Codex threads, the GPT micro's
CHANGES_REQUESTED and four P3s of the CC's Claude micro) led to a fourth round, also made here and new to the live copies, which should
therefore be replaced whole (the repository copy with the three host paths filled in): `codex_gate.py` binds a completion to a review
that started after the latest trigger, both scripts read the trading-cc-read gate again just before the merge, run the gate through
`lg_gate`, use values from `gh` only in their typed shape, drop git's stderr and stop on a missing gate file, `uet_land.sh` requires
`GPT_VERDICT` on a 5 at either gate call, and `nas_land.sh` checks the receipt against the resolved head, keeps validate.py's output out
of its messages and validates again when main moved (exit 13). The review of 761810d7 (four Codex threads, the GPT micro's
CHANGES_REQUESTED and the CC's Claude micro) led to a fifth round, also new to the live copies, which should again be replaced whole: the
landing lock (exit 14), one `final_gate` after every slow step, a failed `trading-cc-read` read that stops, verdict files, records and
receipts read once, nas's latest completed check run per name, and the gate's one GraphQL snapshot, commit cell, editor, 👀 and
activity rules (above). The live copies were last changed at 2026-10-11T05:03:28Z (the CC's patch that took the status-gate failure
line); the "Live copy" column is their sha256 (`sha256sum`) and line count as read at 2026-10-11T13:59Z, which replace the digests of the
CC's 03:37Z patch recorded here before (`1bc1f53b…` and `287f2e7e…`, #975 P3-2). The "Here" column is each file as committed: its
sha256 and line count.

| File | Before correction #136 | Live copy, after #148 | Live copy, since 2026-10-11T05:03:28Z | Here |
| --- | --- | --- | --- | --- |
| `uet_land.sh` | `b794e3a46772c0a598dff9eee972ad449e5d63f0c81b60b9db1d5cb4944747bb` (115 lines) | `301fb5b07274b28fde0f2061356bf9682883eca352c8bcb7a3119e8934920c7d` (232 lines) | `bfe664bcc00fd99cbe2a0afe7a76c483d8d7896e44f665eac066972cdec2ed7a` (233 lines) | `9287d41e92912949cef30a0994fbe213b499becf4b0271979cdf3758bca3d5c2` (372 lines) |
| `nas_land.sh` | `2fefe070b95229de3dcad14052cf5c031b70c202bf4a34f4452e6e0cb5832936` (135 lines) | `96144670bc301036604fc39e57e3ab4e4a2e43a6b9d6b8b645ef7b02482f4017` (243 lines) | `842b85b7f53048e9df027ca537ea99b6208e616e0f239ca30bb1748a5bc1f2ad` (246 lines) | `81e9b65f3062b412bde5cdc0ff41e61d2f85b4debb4e77e90f0d0ae13cd866b9` (414 lines) |
| `codex_gate.py` | (unchanged) | `31524d2871cde79ecb2c5b9bc56b6175ce9fafab9ad4d2e2e3eb3594e1cb2422` (108 lines) | the same | `e2132ab71b6e55fea8922b9c5b0b8c17bde87b1d37f11bf384b785bef6f96b6a` (226 lines) |

Corrections the scripts carry: #118 (every gate before the merge, in order), #121 (a verdict file that states a landing gate needs
a receipt), #122 and #123 (a Codex review must have finished; uet#40 and uet#47 merged while one was running), #136
(verdict and record acceptance, change identity and the CI line: the three loose decision points the shared
`# >>> land-gate-fns` block replaced), the head-following of 2026-10-10 (uet#58: an update-branch rebase does not reach every API view at
once, so a head that moves during CI and carries the read head's change is followed, at most three times), #148 (the author address)
and #975's P2-3 (the CI allow-list), P2-2 (no text from `gh` or its API is printed: a failed merge, a failing status, every other `gh`
call), the gate error (P2: exit 4 and one fixed line, no traceback), the commit-status allow-list (P3) and P2-1 (the privacy scan
checks every prohibited identity), round 3 (above: the completion bound to the latest request, the gates read again before the merge,
typed values, no local diagnostics, the base re-read) and round 4 (above: the lock, the final gate, one read per file, the gate's
snapshot). The block is identical in both scripts, apart from `lg_ci_state`, which only `uet_land.sh` has.

## Known gaps, left as they were

The files began as the live copies with host literals replaced and now also differ from them where the provenance section above says
so (the merge-failure line, the gate's exit 4, the commit-status allow-list, the dropped stderr, the review-thread count and rounds 3
and 4). These stay until a change with its own tests fixes them:

- `U` and `G` are expanded unquoted: a clone path with whitespace breaks both scripts.
- `nas_land.sh`'s validation merge needs a git identity (above). Its header now lists exit 4.
- A call whose failure never stopped a landing still does not: an unreadable draft flag (both scripts) leaves a draft unmarked, and
  an unreadable `mergeStateStatus` (`nas_land.sh`) skips the BEHIND update and the BLOCKED stop, so the merge call itself is the check
  (exit 7 when GitHub refuses it). `nas_land.sh`'s final gate does not read `mergeStateStatus`; thread resolution is required
  server-side.
- The final gate narrows each local gate to the seconds between its read and the merge call, and does not close them (above, "What the
  final gate narrows but cannot close"): GitHub's merge takes an expected head and no expected base (`MergePullRequestInput.expectedHeadOid`
  is the only pin), so for nas's base the GPT micro's A5 remains, and the closure path is server-side.
- The completion attribution reads the connector's summary rows, which carry no review id. Correction of round 3's note that a newer
  Running row replaced by an older completion was "not observed": the gate's own two reads produced exactly that pairing (the CC's
  P2-1 at 761810d7); one query and the newest-revision check now keep the body and its revisions one state. What remains is a
  connector that wrote an older review's completion over a newer Running row within one state (not observed). It reads each comment's
  100 newest revisions (about two per review).
- The attribution is by start time and commit only, not by trigger kind (C2, the CC's P3-2 at 761810d7): a Code Review row started by a
  ready event counts for a later `@codex security review` when it starts after it. No security-review row has been seen live, so its
  row strings are not measured; matching the trigger kind waits for one.
- The privacy scan's boundary (the CC's P3-5 at af9d1901): it finds the forms listed under Tests, and not hex or base64 of a mixed-case
  spelling, look-alike Unicode, zero-width characters, names split across lines, gzip or UTF-16 files, colon, `0x`, octal, `\u` or
  HTML-entity encodings, a name glued to letters or digits (`host=<name>01`, the letter and digit boundary of
  `scripts/host_name_scan.py`), or a generic running account joined by a character outside the joiner class.
- Very short prohibited names fail on coincidences (the CC's P3-6 at af9d1901): a two-letter name matches base64 fragments in several
  files and a one-letter name matches every file. This fails closed; names under about four characters are not useful entries.

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
7 with a class and no gh output, which stays in a 0600 file), a `trading-cc-read` status whose description carries an address
(exit 2, only its state printed), each `gh` call failing in turn with an address on stderr and, for `gh api`, on stdout (the step's
own exit code, nothing printed; #975 P2-2), a check that the "Here" digests above are those of the committed files, and a scan of
every file under `tools/landing`, bytecode excepted, for home paths and for the identities that must not appear (#975 P2-1, below).
Round 3 adds, each failing at af9d1901: a review that started before the latest trigger and finished after it (exit 3, not 0), the
gate giving 0 then 5 in `uet_land.sh` without, with a wrong and with an accepted `GPT_VERDICT`, a status or record that changes during
the wait (exit 2), a main that moves after the validation (validated again; exit 13 when it keeps moving), the validation's output kept
in its file and not printed, failed or malformed CI replies, a missing, broken or chatty gate, a missing clone and a missing verdict
file under a home-like path (no path printed), an unusable `TMPDIR` on a failed merge, and a receipt naming only the caller's shorter
prefix. Round 4 adds, each failing at 761810d7 (12 of the 17 flips merged there; the other five stopped, four of them on the
`trading-cc-read` re-read of round 3): the final gate's reads as the last calls before the merge, in their order; each gate flipped
between its first read and the final gate (a verdict file that gains CHANGES_REQUESTED, a `GATES_DONE` that disappears, a
`trading-cc-read` status that turns to failure, a read of it that fails with nothing on stdout, its record that gains
CHANGES_REQUESTED, Codex giving 3 at the final call, a queued CI re-run, the head moving, nas's main moving after the validation read
it), each with its exit code and no merge; a Codex review that starts during nas's first validation or during the retry after main
moved; an unreadable `origin/main` (its own stop, exit 13, the CC's P3-4); a `trading-cc-read` read that fails with empty stdout at
the first or the final read; a held landing lock (exit 14 before any call), and a child that outlives the landing, which must not keep
it; an unreadable verdict file,
record, receipt or `GPT_VERDICT`, and a verdict file removed after its first line was read (no path printed, no merge); for the gate,
an edit between two reads, a reply whose newest revision is not its body, a review of another commit, revisions by another account,
the 👀 reaction, a comment id beyond 32 bits, an unattributable completion before and after ten minutes, and the captured nas#975
summary comment; and a queued re-run beside an old success in nas's check runs. It is offline, needs `jq`, and is Linux-only. A
script edit that moves a decision site fails the module instead of leaving it untested.

**The privacy scan (#975 P2-1).** Two kinds of identity are scanned for, each in these forms: the bare word, an identifier or path
form (joined to other text by `-`, `_`, `.`, `/`, `\`, `@`, `:`, `~` or `=`, as in `project-<name>-tools` or `<name>@host`), a
percent-encoded form (decoding that reveals the name as a new token, or as a new identifier, as `<name>%40host` does: #975 P2-D),
hex digits and base64 at each alignment. A home path counts in any letter case (#975 P3-7: the pattern was case-sensitive). An explicitly
prohibited identity is a name in
`LANDING_PROHIBITED_NAMES` (comma-separated, read when the tests run, so no real name is written into the repository; not
`NATIVE_AGENT_HOST_NAMES_JSON`, whose setting replaces the host-name scanner's own sources). It is scanned in every form, whatever its
length and even when it is an ordinary word. The account that runs the tests is scanned the same way, with one exception: in CI
(`GITHUB_ACTIONS` or `CI` is `true`), when it is a generic CI or container account (`GENERIC_ACCOUNTS` in the test module, such as
`runner` on GitHub-hosted runners), its bare word may stand in prose, because such names are ordinary words; its identifier, path and
encoded forms are still reported. Outside CI no account is excused (#975 P3-8). A home path is reported for every account. No name is
skipped for its length (before, one under four characters was, so a real account `sam` was never checked). The repository assertion
itself is run on a scratch tree with a mocked account lookup for a three-character account, for a generic account in each form, in
and outside CI, and for a prohibited name that is also a generic word, and on the files here for every generic account in CI: none is
reported (#975 P2-E: the second line of `uet_land.sh` joined `user` to the next word with a hyphen, which is its identifier form, and now
reads "owned by one account").

## Upstream sources for the #975 corrections

Each source was fetched on 2026-10-11 with `curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/<tag>/<path>` and read at the
lines given (the sha256 is that of the fetched file). Installed: `gh` 2.102.0, `mktemp` from uutils coreutils 0.10.0, Python 3.13.16,
git 2.53.0. The GNU `mktemp` of the CI runners is not cited. The round-3 rows follow the first table; the gh manual page was fetched
from `https://cli.github.com/manual/gh_pr_merge` and the GraphQL schema from `https://docs.github.com/public/fpt/schema.docs.graphql`
(the same bytes as the fixtures, sha256 `3ed09565…`).

| Mechanism | Source at the pin, sha256 | Lines read and what they say |
| --- | --- | --- |
| Where `gh` prints a command's error (P2-2) | `cli/cli@v2.102.0:internal/ghcmd/cmd.go`, `4ce5cdb31c15dad95e0a7e18e6d0f0c49a07603cea0d5f4e08bc51f530a5d7e1` | `:69` `stderr := ioStreams.ErrOut`, `:214` `printError(stderr, …)`, `:285` `fmt.Fprintln(out, err)`: the error of a failed command goes to stderr |
| `gh api` on an error response (P2-2) | `cli/cli@v2.102.0:pkg/cmd/api/api.go`, `030eda84dcfdb52e3bba2cadfc0243a7b47d3098b64f8c12c665550733d72ca1` | `:347` the body writer is `ContentOut` (stdout); `:492-497` and `:656-686` a JSON error goes through `parseErrorResponse`, which returns a copy of the raw body and `<message> (HTTP <status>)`; `:509` `--jq` runs only when `serverError == ""`, so `:546` copies the raw body to stdout, and `:538-539` copies a body that is not JSON through `iostreams.CopyGuardedContent` (the CC's P3-9 at af9d1901: both reach stdout); `:553-557` prints `gh: <message>` to stderr; `:564` returns `SilentError` (non-zero exit) |
| `mktemp` prints the path it made and creates the file with mode 0600 (P2-2) | `uutils/coreutils@0.10.0:src/uu/mktemp/src/mktemp.rs`, `04d1e28080aaa4f19f9113dfc3da97541158483a220efda9a52275fed54e3b98`; `Cargo.lock`, `0833b527913f974ace9dff19e4dd8640e73da2cab6967c8dfca5e7dc9889abc9`; `Stebalien/tempfile@v3.27.0:src/lib.rs`, `d182721b62c126916b73bb4865ced5d3637bd1a4a77d27ea9e9708973e5f9493`, `src/file/mod.rs`, `b6752b11a575021eeab87cb8b5b6914aaff86ad8d49a9678a8f4c95b5a21ef81`, `src/file/imp/unix.rs`, `cc39f94cb6cb87b36cf7603a75429d64ecc4ad1a2076a765e5aba2b11771d0f7` | `mktemp.rs:438` `println_verbatim(res?)` prints the created path to stdout, which `$(mktemp …)` captures; `:581-582` "The permissions of the file are set to `u+rw`", `:588-591` `make_temp_file` calls `Builder::tempfile_in(dir)` and sets no permissions (`:557-560` sets `0o700` for directories only); `Cargo.lock:2983-2984` pins `tempfile` 3.27.0; in `tempfile`, `lib.rs:234` the builder's `permissions` is `None`, `:555-568` `tempfile_in` passes it on, `file/mod.rs:1111-1116` to `imp::create_named`, and `imp/unix.rs:18` `create_new(true)` (exclusive create), `:23` `mode(permissions.map(\|p\| p.mode()).unwrap_or(0o600))` (mode 0600, narrowed by the umask); `lib.rs:64` "Temporary _files_ created with this library are private by default" |
| The running account's name (P2-1) | `python/cpython@v3.13.16:Doc/library/pwd.rst`, `0f4b8b370a7f0d2e8ff93f2e224b2c7e54f64bfb808e5f50242f83b725e950a8`; `Modules/pwdmodule.c`, `11841fe008240d3ffb955d0c700da1d96c07f18679ab09b93b16c3c81707a261`; `Lib/getpass.py`, `e52ea266b79f3b4a83388093f387540ff36d51ff306dcbb6ca6de081cd28e718` | `pwd.rst:52-54` `getpwuid(uid)` returns the entry for a numeric user ID and `:36-37` raises `KeyError` when it cannot be found; `pwdmodule.c:195-196` `getpwuid(): uid not found: %S`; `getpass.py:154-175` `getuser()` tries `LOGNAME`, `USER`, `LNAME` and `USERNAME` first (`:166-169`), then `pwd.getpwuid(os.getuid())[0]` (`:171-173`) and raises `OSError` when neither gives a name (`:174-175`), which is why `account_name()` asks the password database first and falls back to `getuser()` only when the uid has no entry |
| Recursive traversal and reading (P2-1) | `python/cpython@v3.13.16:Lib/pathlib/_local.py`, `0530b4186ec5845e000bedf5817ff1ac970b9a39a6891ba6789a1776abdea42b`; `Lib/pathlib/_abc.py`, `75e6bc728013d11446126d535f92b8907fb6dae7404df3d0268ac7b6865a2090` | `_local.py:611-620` `Path.rglob(pattern)` yields every existing file of any kind, directories included, anywhere in the subtree (it globs `'**' / pattern`), and `:581` `recurse_symlinks=False` is the default; `_abc.py:476-488` `is_file()` is also true for a symlink to a regular file, `:621-626` `read_bytes()` reads the whole file. The scan uses these, not `os.walk` |
| The decoded forms (P2-1) | `python/cpython@v3.13.16:Lib/urllib/parse.py`, `491b233e8d87a2ab73964afff029717177d53ad8def328ed9b00575db983da27`; `Lib/base64.py`, `a80fc2454f7a0ad644f02259184de5b52084392ddb8b41c1ce372e50a09f3993`; `Objects/bytesobject.c`, `fd5e3799c5a70a7560460badf84a1a3e14c5b8b40a40352840477e267019cf20` | `parse.py:649-651` `unquote_to_bytes('abc%20def') -> b'abc def'`, `:673-680` a `%XX` pair becomes its byte and anything else stays as written; `base64.py:51-62` `b64encode`, `:112-119` `urlsafe_b64encode` (`-` and `_` for `+` and `/`); `bytesobject.c:2583-2592` `bytes.hex()` "Create a string of hexadecimal numbers from a bytes object" |
| Lookaround assertions behind the bare-word and identifier forms (P2-1) | `python/cpython@v3.13.16:Doc/library/re.rst`, `455ed7abc1d74b6af12c9205e76af0873bbb9d4297f73c8a2d6306a7ec658042` | `:459-469` `(?=…)` and `(?!…)`, `:473-479` `(?<=…)`, whose contained pattern must match a fixed length (the joiner class is one character), `:500-504` `(?<!…)` |

Round 3 (the review of af9d1901):

| Mechanism | Source at the pin, sha256 | Lines read and what they say |
| --- | --- | --- |
| The merge pins only the head (Codex P2, nas base move) | `cli/cli@v2.102.0:pkg/cmd/pr/merge/merge.go`, `ca3849b4d224ac0384bcc90102f77bd0612e2c0ba67fc1ee44bb48abe87c5942`; the manual page `gh_pr_merge`, `b21ef4350f050611af8a268632579c019c2dcb33feea7c0abffd4ca2b2520f0b`; the GraphQL schema, `3ed09565…` | `merge.go:184` `--match-head-commit`: "Commit `SHA` that the pull request head must match to allow merge", `:294` it becomes the mutation's `expectedHeadOid`; the manual repeats the flag text; `schema.docs.graphql:26068-26103` `input MergePullRequestInput`, whose only pin is `:26090-26092` `expectedHeadOid` "OID that the pull request head ref must match to allow merge; if omitted, no check is performed" (no base) |
| Reading the current main (Codex P2) | `git/git@v2.53.0:Documentation/git-ls-remote.adoc`, `9739be01b44da924ebec94ee658d5c080627ee65a2cd7d711fd83d6a081ba4da` | `:6` "List references in a remote repository", `:93-97` only references matching the given patterns are displayed (`refs/heads/main`) |
| A review's start, from the summary comment's revisions (Codex P1, the gate) | the GraphQL schema, `3ed09565…`; `cli/cli@v2.102.0:pkg/cmd/api/api.go`, `030eda84…`; `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…` | `schema.docs.graphql:21203` `type IssueComment`, `:21380-21404` `userContentEdits(after, before, first, last): UserContentEditConnection`, "A list of edits to this content", `:21248-21250` `databaseId: Int`, "the primary key from the database"; `:74077-74101` `type UserContentEdit`: `diff: String` (`:74096`, "A summary of the changes for this edit") and `editedAt: DateTime!` (`:74101`); `api.go:121-122` fields other than `query` are GraphQL variables, `:112-115` `-F` converts integers, `:134-139` `--paginate` needs `$endCursor: String` and `pageInfo{ hasNextPage, endCursor }`, `--slurp` wraps the pages in an array; the REST `issue-comment` schema's `id` is the integer the gate matches to `databaseId`. That each `diff` held the whole body of its revision, newest first, is measured (nas#974, #975, #979, #994 on 2026-10-11), not documented |
| A newer status supersedes (Codex P1, the gate read again) | `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e417611cca9a4131dceea89d4d61c3be021b0917f32d9e4422e4fe60f1` | `:55724` `repos/list-commit-statuses-for-ref`: "Statuses are returned in reverse chronological order. The first status in the list will be the latest one" |
| A shorter prefix names the same commit (Codex P2, the receipt) | `git/git@v2.53.0:Documentation/revisions.adoc`, `3835ec561d9f4052783c79541d86d16e644f7d8d0b8fb1bd1d3067ad021c38a7` | `:14-18` a SHA-1 is "the full SHA-1 object name (40-byte hexadecimal string), or a leading substring that is unique within the repository", so the caller's prefix can be shorter than the eight characters a receipt must name |
| What python3 prints when the gate cannot run, and what the gate's handler covers (GPT P2-C and P3) | `python/cpython@v3.13.16:Modules/main.c`, `9507f8a42e30531ed11721339f32a2e2b5d02e721e4c166414fa574269fd19e7`; `Doc/library/sys.rst`, `91825c95030c506eb3840249a9f7bc12a0ff7eeb2f66b980608d5bc5d1cdb568` | `main.c:403-410` a file that cannot be opened prints "%S: can't open file %R: [Errno %d] %s" (the path) to stderr and returns 2; `:437-441` code that ends in an uncaught exception returns `pymain_exit_err_print()`, which `:118-123` exits 1 after printing the error; `sys.rst:394-399` for an uncaught exception other than `SystemExit` the interpreter calls `sys.excepthook`, which "prints out a given traceback and exception to `sys.stderr`". So `codex_gate.py`'s `except Exception` handler covers exceptions raised while `main` runs; a file that cannot be opened or compiled never reaches it, which `lg_gate` covers |
| git's diagnostics go to stderr (GPT P2-C) | `git/git@v2.53.0:usage.c`, `d878ba9b46081d1e902cafeddc35d368ad3d9eaf5cb5c5c99ab4ea692c7054f6` | `:40-43` `vreportf` writes to `stderr`, `:82` `die_builtin` reports through it ("fatal: ..."), so `2>/dev/null` drops a message such as "cannot change to '<path>'" |
| Case-insensitive home paths (Claude P3-7) | `python/cpython@v3.13.16:Doc/library/re.rst`, `455ed7ab…` | `:769-773` `re.I`/`IGNORECASE`: "Perform case-insensitive matching" |
| CI detection for the generic-account exemption (Claude P3-8) | `github/docs@be38ec5d78e24172587e61b3c6ff40ace1865c71:content/actions/reference/workflows-and-actions/variables.md`, `38a4ba0d8cbd440e1cdde96c0c6384d8ee60bf844b7c934ab1516d9206669922` | `:32` `CI` "Always set to `true`", `:36` `GITHUB_ACTIONS` "Always set to `true` when GitHub Actions is running the workflow" |

Round 4 (the review of 761810d7). Fetched on 2026-10-11 between 13:38Z and 14:03Z the same way (the gh manual and GraphQL schema rows
above still hold; the schema's bytes are unchanged, sha256 `3ed09565…`); installed: `flock` from util-linux 2.41.3, `jq` 1.8.1, git
2.53.0, `gh` 2.102.0. The connector's summary comment was read with the gate's own query on nas#975 at 13:42:44Z.

| Mechanism | Source at the pin, sha256 | Lines read and what they say |
| --- | --- | --- |
| The landing lock | `util-linux/util-linux@v2.41.3:sys-utils/flock.1.adoc`, `13befe29fb26539e05251a6352d08984f54ea82c02ba5166173909038cfb6e97`; `sys-utils/flock.c`, `f303ab0c5c14299e3d0891f5b9731317e87081546c1b0b2e2e1bf6d7613c224b` | `flock.1.adoc:124-125` `exec 4<>/var/lock/mylockfile; flock -n 4`: the shell opens the lock file as a descriptor and flock locks it "without spawning a subprocess"; `:68-69` `-n` "Fail rather than wait"; `:59-60` the exit status of a conflict is 1 by default; `:78` "a lock is automatically dropped when the file is closed", and a forked background process may otherwise hold it; `flock.c:189` the lock is exclusive by default, `:329` the descriptor form, `:167-171` `flock(2)`, `:351-363` a held lock exits with the conflict code and prints only under `-v`, `:392-399` any other failure prints the file name or, for a descriptor, its number |
| Why children run without descriptor 9 | `git/git@v2.53.0:builtin/fetch.c`, `f7dda45536864b701aa5eca8e32462e319cf068181f642b4e4a053d9556847bf`; `run-command.c`, `bc3403bcc124da68d945ab2f4306c5ca673ba317bd3852b4bbf7789966f35cb2`; `builtin/gc.c`, `9b33422c7d0c5948a470db5a340992816aedf04dabaf0da6d57e3b004471d775`; `setup.c`, `06c1942188bc86d1a1691eb97a66d0ee278c1057661a62112bf1ecbc0776b3ec`; `Documentation/config/maintenance.adoc`, `809b79c7ff781871874e92c186908cac332fc4b0fa0dff2fb9624856e2a9fa79` | `fetch.c:2725` `run_auto_maintenance(...)` after a fetch; `run-command.c:1829-1831` `maintenance.autoDetach`, then `gc.autoDetach`, default 1, `:1835-1837` `maintenance run --auto ... --detach`; `gc.c:1823-1827` a detaching run calls `daemonize()`; `setup.c:2083-2105` `daemonize` forks, the parent exits, and the child closes 0-2 only; `maintenance.adoc:6-15` detaching is the default; `run-command.c:551-555` sets close-on-exec on git's own descriptors only, so an inherited one stays open |
| The gate's one query (P2-1, P3-5, P3-6) | the GraphQL schema, `3ed09565…` | `schema.docs.graphql:21203` `type IssueComment`, `:21215` `author: Actor`, `:21225` `body: String!`, `:21240` `createdAt: DateTime!`, `:21250` `databaseId: Int`, `:21260` `fullDatabaseId: BigInt` ("the primary key from the database as a BigInt"), `:21384-21404` `userContentEdits`; `:2674-2678` `BigInt` "may exceed the size of a 32-bit integer, it's encoded as a string"; `:74077` `type UserContentEdit`, `:74096` `diff`, `:74101` `editedAt`, `:74106` `editor: Actor`; `:2876` `type Bot`, `:2905` `login`; `:48961-48970` `ReactionContent` has `EYES` |
| A queued re-run has no start (P3-1) and the reaction is `eyes` | `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…`; `jqlang/jq@jq-1.8.1:docs/content/manual/v1.8/manual.yml`, `e0eb9a084b0a8ed4f07a11dbfb0d6c31006235815481cfcd8876d48ff42b5f75` | `api.github.com.json:146097-146102` `check-run.started_at` is `"nullable": true`; `:148544-148557` a reaction's `content` enum ends with `"eyes"`; `manual.yml:1544-1552` jq sorts `null` before every other value, which is why `max_by(.started_at)` ranked a queued re-run lowest; `:1334-1347` `any(generator; condition)`, `:1596-1603` `max_by`, `:2477-2486` `//` |
| The connector's own layout and footer | `tests/fixtures/landing/codex-summary-comment.json`, `3918a25359d64ea4b2bcf31ec9ac9d92ff681270c072da6af625575eab720792` (the summary comment of nas#975 with its four revisions, masked by `mask_packet.py`'s rule with nothing to replace; the body's sha256 is `1236fe482740fa1ccdaac6d50d4e1e77f6a6e961d64e8dd5377a4923a6f8d0dc`) | a row of four cells (the review kind "📝 Code Review", the status "✅ Completed" with its time, the commit 761810d in backticks, the trigger kind "Manual request"), the Running form "🔄 Running since" with its time, the newest revision equal to the body, every editor the Bot `chatgpt-codex-connector`, and the footer "Codex reacts with 👀 while any review is running, comments if it has suggestions, and reacts with 👍 once all reviews finish with no findings" |
