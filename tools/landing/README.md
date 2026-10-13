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

**`nas_land.sh <pr> <read-head-prefix> <verdict-file>...`** does the same for this repository, `native-agent-stack/native-agent-stack`
since its transfer to the organization on 2026-10-12 (`LANDING_REPO` overrides it; "The repository", below),
with the verdict files as arguments (at least one) and these differences: `manifests/evidence.json` is left out of the change
identity (CI arbitrates the registry), a BEHIND branch is updated server-side (merge method), the aggregate `validate` check
must have succeeded at the head (every page of check runs is read; the rule is below), the Codex gate is asked again before the
validation, and the head is then merged into the current `origin/main` in a temporary worktree
under `/var/tmp` where `scripts/validate.py` must exit 0 (exit 10 otherwise). Its output is never printed: it goes to a file made by
`mktemp "${TMPDIR:-/tmp}/nas-validate-XXXXXX"` (mode 0600) outside the worktree, and exit 10 names that file and the exit code. `gh pr
merge --match-head-commit` pins only the head ("Commit SHA that the pull request head must match to allow merge", sources below), so
`origin/main` is read again with `git ls-remote` after each validation: when it moved, the merge onto the new main is validated again,
at most three validations in all (exit 13 when it moved after each; #975, Codex P2 at af9d1901), and the final gate reads it once more.

**The check runs (`nas_land.sh`).** Every page is read (#975, Codex P2 at nas:289: page 1 was all that was read). The runs are asked
for with `filter=latest`, which "Filters check runs by their `completed_at` timestamp", and `per_page=100`, the most a page holds;
`gh api --paginate --slurp` follows each `rel="next"` link and writes every page into one array, which jq judges whole
(`github/rest-api-description@58b1e0c0` `api.github.com.json:55504-55514`, `:55518`, `:55521`, `:344577-344585`; `cli/cli@v2.102.0`
`pkg/cmd/api/api.go:260-273`, `:358-371`, `:431-470`, `pagination.go:17-24`; sources below). A check name is incomplete while any of
its runs is, or while a completed run has no `completed_at`. It fails when one of its completed runs ended other than success, neutral
or skipped and no run of that name both started and completed after it (#975 A1, the CC's Claude micro at 3e6e7e46: while a name was
judged on its newest completion alone, a failure that started later and finished first passed beside an overlapping success that
finished last). So a cancelled run followed by a run of its name that started and completed after it does not fail the name (#886);
runs that share a `completed_at` pass when each passes and fail when one fails; and a run without `started_at` or `completed_at`
supersedes nothing, since jq orders null before every string (`jqlang/jq@jq-1.8.1` `docs/content/manual/v1.8/manual.yml:1544-1552`,
`:2425-2433`; both times are nullable, `api.github.com.json:146097-146107`), while a failing run without them is superseded by
nothing. `validate` counts when it is complete, not failing, and a run with its greatest `completed_at` succeeded.

**`codex_gate.py <owner/repo> <pr> [<read head>]`** prints one status line about the connector's review and exits 0 (a review of the
read head or of the current head that started at or after the latest trigger finished, and none is running), 3 (running, the
connector's 👀 reaction on the pull request, none of those heads that started since the latest trigger finished, or a summary whose
newest revision is not its body: poll again), 4 (such a review ended other than Completed, a summary last edited by an account other
than the connector, or the gate itself failed: any exception, a failed `gh` call included, prints one fixed line naming only the error
class, never a traceback, which would print file paths, or `gh`'s output; #975 P2), or 5 (Codex is unavailable: a usage-limit or
account notice since the trigger, no connector activity for 10 minutes, or a review shown running with no connector activity for 90
minutes, below). Both scripts stop with exit 9 on a 4 at any call, and on a 3
at any call but the wait, which polls a 3 for up to 20 minutes. A trigger is the pull request's creation, a ready-for-review event, or a comment by anyone but the connector that
starts with `@codex review` or `@codex security review`; a push is not a trigger. A Running row gives 3 until it is stale (below). When
`LOCAL_REVIEWS` names review files, the gate reads no connector data and decides from the files alone ("Local reviews", below).

**A stale running review (CC correction #200, 2026-10-13).** The transfer of this repository to the organization cut the connector's
access in the middle of a review, and its summary row stayed Running, so the gate gave 3 for as long as it stayed so (a landing stopped
with exit 9 after its 20-minute wait). A row shown running with no connector activity after its start for `STALE_RUNNING_MINUTES` (90)
now gives 5, "Codex unavailable", never 0. Activity is a connector comment other than a summary, a connector reaction, or an edit of a
summary; the start itself writes a summary edit and the 👀 reaction within seconds, so the age runs from the last activity. `nas_land.sh`
proceeds on a 5 and `uet_land.sh` needs `GPT_VERDICT`, as for every 5. The block is the CC's operational patch of 2026-10-13T00:47Z,
ported alone and byte for byte. #1061 (the Claude read and the CC's `/code-review` probe at c999eee5) refined it:

- the age runs from the later of the last activity and the latest trigger, and a trigger that came after the review had already gone
  stale gets `NOSTART_MINUTES` (10), the grace a first trigger gets (before, an `@codex review` after a stall gave 5 at once);
- the connector's 👀 with no Running row is the same running review, under the same rule (before, 3 for ever);
- when the running review is stale, a review of the read head or the current head that ended other than Completed since the trigger gives
  4 before the 5 (before, the stale 5 hid it, and nas proceeded).

The value is a measured bound, not an upstream one: OpenAI's Codex docs state no review time limit and no behaviour for a stalled
review. Their index (`developers.openai.com/codex/llms.txt`, sha256 `72459eb4…`) points code review to `learn.chatgpt.com/docs/code-review.md`
(sha256 `c18b2fe1…`: "Use the review chat to stop a running review", :129) and `docs/third-party/github.md` (sha256 `1ab50213…`: "Wait for
Codex to react (👀) and post a review", :52; "Codex reacts while the review is running", :170; for "If Codex doesn't react or post a
review", :196, only settings to check, among them "Confirm the pull request belongs to a GitHub repository connected to Codex", :199),
all read on 2026-10-13. The basis is nas#1056: its row went Running at 2026-10-12T22:56:31Z, the connector's last activity was its 👀 at
22:56:34Z, and it was still silent 250 minutes later (read 2026-10-13T03:06Z); the CC set 90 when the silence had lasted 111 minutes. The
value is the one constant `STALE_RUNNING_MINUTES`.

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

**The merging account (CC correction #198, 2026-10-13).** After the transfer the repository's owner is an organization, and the address
formed from its name was refused at the merge (GraphQL "Invalid email address"): the no-reply form belongs to a user account, "your
`noreply` email address is an ID number and your username in the form of ID+USERNAME@users.noreply.github.com" (`github/docs@be38ec5d`
`content/account-and-profile/reference/email-addresses-reference.md:47`). `lg_author_email` now takes the login from `LG_AUTHOR_LOGIN`,
the merging account (default `seathatflowsinourveins` in both scripts), and from the repository's owner only when that is unset (the
shared block on its own). A login of another shape than GitHub's, at most 39 alphanumerics and single inner dashes, is refused before any
call (exit 11). `users/<login>` answers for an organization too, so only a reply of `type` `User` gives the id (#1061 P3: an organization's
address failed only at the merge, exit 7); otherwise exit 11. The address form and the check after the merge are unchanged.

**The repository (2026-10-13).** This repository moved to the organization on 2026-10-12, and `nas_land.sh` takes `R` from
`LANDING_REPO`, default `native-agent-stack/native-agent-stack` (before, a literal of the old slug). GitHub redirects the old slug ("All
links to the previous repository location are automatically redirected to the new location", `transferring-a-repository.md:62`; the CC
measured REST, GraphQL and `gh -R` on the moved repository), but a repository created at the old location deletes those redirects for good
(`:68-69`), so the default is the new slug. The landing lock keeps its name (`native-agent-stack.lock`). The trading repository did not move.
`R` must have GitHub's owner/name shape (an owner of at most 39 alphanumerics and single inner dashes, a name of letters, digits, `.`, `_`
and `-` other than `.` and `..`), or the landing stops with exit 2 before any call, and every `-R "$R"` is quoted (#1061 P3: a value with
whitespace was split into extra `gh` arguments).

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
`die` writes "fatal: ..." with the path it was given to stderr), so does the `jq` that judges nas's check runs (jq 1.8.1's error
quotes the start of the value it failed on, measured: `Cannot iterate over string ("a-long-rep...)`), `codex_gate.py`'s output is
echoed only when it is one of its own
status lines with exit 0, 3, 4 or 5 (`lg_gate`; otherwise one fixed line and exit 9, which covers python3's "can't open file
'<path>'", exit 2, and a traceback, exit 1, that the gate's own handler never sees), a missing gate file is one fixed line before
anything is marked ready (exit 9), a verdict file is named by its file name only, `validate.py`'s output stays in its file (above), and
a failed merge whose diagnostic cannot be kept (an unusable `TMPDIR`) says so in a fixed line (exit 7; before, `mktemp` printed the
template's path and the message named an empty file).

**Gates read again before the merge (#975, Codex P1 at af9d1901).** The `trading-cc-read` status and its record are mutable: a newer
status for the context supersedes an older one (the statuses list is "in reverse chronological order. The first status in the list will
be the latest one"), and the record is append-only. `tcc_read_gate` reads the combined status, "a combined view of commit statuses" that
holds the newest status of each context once (measured), on every page (`gh api --paginate --slurp`; it is paged by context), and takes
the `trading-cc-read` entry (#975, Codex P1 at nas:234: it read page 1 of the list, the 100 newest statuses of every context, so a
`trading-cc-read` failure behind 100 newer statuses of other contexts was not on it and passed as "no status"; before that, #975 B1, the
CC's micro at 5b8ba3b2: it took the last after `sort_by(.updated_at)`, and jq's sort keeps equal keys in input order, so of two
statuses posted in the same second it kept the older one, a success over a newer failure; sources below). Both scripts ran
`tcc_read_gate` only at the start, before tens of minutes of Codex and CI waits; they read it again before the merge (exit 2). In
`uet_land.sh` a gate result of 5 needs `GPT_VERDICT` at both gate calls: the wait could give 0 and the call before the merge 5 (an
`@codex review` during CI that met the usage limit), and that landing merged with neither a finished review nor the substitute.
`nas_land.sh` proceeds on a 5 by its own policy, unchanged.

**One final gate after every slow step (#975 round 4, the CC's micro at 761810d7).** Each round-3 re-read closed one gap and left the
next: the verdict files and `GATES_DONE` were read only at the start, a failed `trading-cc-read` read with nothing on stdout passed as
"no status", and `nas_land.sh` asked Codex before up to three validations of 56 s each (a review started by then was never seen). The
scripts now run in this order: the landing lock; early refusals (cheap reads); the slow steps (ready, the Codex wait, update-branch,
the CI wait, nas's validations, the author-address lookup); `final_gate`, fast reads only; the merge pinned with
`--match-head-commit`; the author check. `final_gate` reads, in order:

1. the head, which must be the pinned head and carry the read head's change (exit 3, or 4);
2. every verdict file and `GATES_DONE`, through the function the early check uses (exit 2);
3. the `trading-cc-read` status and record, with `gh`'s exit code kept apart from its output: a failed call stops (exit 2), as does a
   reply that is not an array of pages with statuses, an empty one included, and only a combined status with no `trading-cc-read` entry
   on any page is "no status";
4. the Codex gate, where a 5 needs an accepted `GPT_VERDICT` again in `uet_land.sh` (exit 9);
5. CI at the head: complete, green, with `ci-gate` (uet) or `validate` (nas) succeeded (exit 5; uet also exit 8 when BLOCKED);
6. in `nas_land.sh`, `origin/main` by `git ls-remote`, which must be the main the merge was validated on (exit 13).

Nothing slow runs between `final_gate` and the merge; the tests flip each gate between its first read and `final_gate` and check the
exit code and that no merge is called (15 of the 20 flips merged at 761810d7, and at 5b8ba3b2 three still merged: the two in which
`trading-cc-read` gains a failure in the same second as its success, #975 B1, and nas's completed failing re-run with no start, Astra's
follow-up 1). #975 A1 adds two nas flips, the overlapping runs F and G: of the 22 flips, F merged at 3e6e7e46, four (the three above and
G) at 5b8ba3b2, and none merges now. A verdict file, record or receipt is read once (`lg_text`),
and each decision about it is made on that one text, so a file removed or rewritten between two reads cannot pass on half of each, and a
read that fails is a refusal with a fixed message that names no path (GPT P2 at 761810d7).

**The landing lock (#975 round 4).** Both scripts first open `<LANDING_LOCK_DIR>/<repository name>.lock` (default
`$LANDING_COORD/command-center/landing-locks`, outside every worktree) on descriptor 9 and take an exclusive `flock -n` on it, held until
the script exits; a second landing of the same repository stops at once with exit 14 before any call, as does a lock that cannot be
opened (its path is not printed). Every `git`, `gh`, `python3` and `sleep` the scripts run is called with descriptor 9 closed, so no
child keeps the lock after the script: a `git fetch` starts automatic maintenance that detaches and keeps every descriptor but 0-2
(sources below). The script's own `$(…)` subshells do hold descriptor 9 while they wait on the `gh` or gate call they run, so after a
signal ends the script the lock stays held until that call returns, and a landing started meanwhile stops with exit 14: it fails closed
(the CC's P3-a at 5b8ba3b2; measured on 2026-10-11, the lock stayed held for the rest of a 4 s child after SIGTERM, then was free).

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
  captured nas#975 summary, trigger 10:42:50Z, Running since 10:43:04.5Z). A trigger made before the final gate's call is in its
  snapshot, so the gate waits for that review (3, then exit 9) even before its Running row appears; what it can miss is a trigger made
  after its snapshot, in the seconds before the merge call, or one the API has not served yet (the CC's P3-d at 5b8ba3b2).
- **The closure path:** the review App and required checks of `docs/decisions/2026-10-09-review-verdict-app-identity.md` (an owner
  item), which would move the verdicts into checks GitHub enforces at the merge.
- **What the lock closes:** concurrent landings by our tooling, so our own landings no longer move main under each other's validated
  base; a merge made out of band (the web UI, another tool) is not covered.

## Variables

| Variable | Default | Used by | Meaning |
| --- | --- | --- | --- |
| `LANDING_UET_REPO` | `$HOME/code/us-equities-trading` | `uet_land.sh` | clone of the trading repository: fetches, `rev-parse`, change identity (the path must not contain whitespace) |
| `LANDING_NAS_REPO` | `$HOME/code/native-agent-stack` | `nas_land.sh` | clone of this repository, used the same way (no whitespace) |
| `LANDING_REPO` | `native-agent-stack/native-agent-stack` | `nas_land.sh` | the repository's `owner/name` on GitHub, of that shape or exit 2 (2026-10-13; "The repository", above) |
| `LG_AUTHOR_LOGIN` | `seathatflowsinourveins` | both | the merging account, whose no-reply address authors the squash merge (CC correction #198) |
| `LOCAL_REVIEWS` | none | both, through `codex_gate.py` | colon-separated normalized review files; when set (an empty value included), the Codex gate decides from them alone ("Local reviews") |
| `CODEX_LOCAL_REVIEW` | none | both, through `codex_gate.py` | an alias of `LOCAL_REVIEWS`: its files are added to the set |
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
these). `nas_land.sh`: 2 as above, and a `LANDING_REPO` that is not of the owner/name shape (before any call; #1061 P3), 3 head moved,
4 `update-branch` refused or the change differs after it or at the final gate, 5 CI
failing (also at the final gate), 6 timeout, 7 merge failed, 8 blocked by policy, 9 as above, but a 5 proceeds, and a 3 before the
validation stops too, 10 the merge onto current `origin/main` fails `scripts/validate.py` or does not merge cleanly, 13 origin/main moved
after each of three validations, moved after the last validation (read at the final gate) or could not be read, so nothing is merged
(#975, new in round 3). Both scripts also exit 11 when the no-reply author address cannot be formed (nothing is merged), 12 when the
merge landed but its commit's author is not that address or the commit could not be read (CC correction #148), and 14 when another
landing of the same repository holds the landing lock or the lock cannot be opened or taken (nothing has run; #975 round 4).
`codex_gate.py`: 0, 3, 4 and 5 as above; a gate that fails itself exits 4, which both scripts stop on with 9. With a local review set
("Local reviews"): 0 (every file a review of the read head or of a head with its change, every `codex-review` completed with `patch is
correct` and no P0 or P1 finding), 2 (no file named; a file unreadable, malformed or of another head; a `codex-review` against another
base than its head's merge base with `origin/main`, not completed or with another verdict; or no completed `codex-review`) and 4 (`patch is
incorrect`, or a P0 or P1 finding of a `codex-review`); the advisory plugin arm never stops it; both scripts stop with 9 on its 2 and its 4.
`review_normalize.py`: 0 the file was written, 1 the input was refused (nothing written), 2 usage.

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

## Local reviews

The owner's direction of 2026-10-13: Codex reviews run locally, through the OmniRoute gateway on the subscription pool, not through the
ChatGPT connector, which cannot reach the organization's repository; the review set also takes Anthropic's official `/code-review`
plugin. `LOCAL_REVIEWS=<file>[:<file>...]`, and its alias `CODEX_LOCAL_REVIEW` (its files are added to the set), name normalized review
files. When either is set, an empty value included, `codex_gate.py` decides from the files and calls nothing; a set variable that names no
file stops (2: #1061 P1, an empty value fell back to the connector, which cannot answer for the organization's repository, and nas proceeds
on its 5). Unset, the connector path is as before (`us-equities-trading` still uses it). A file name cannot hold `:` or a newline.

**The normalized review** is one JSON object with exactly these fields; a finding carries no prose body, and another field, a repeated
key or `NaN` is refused:

```json
{"reviewer": "codex-review", "reviewer_version": "codex-cli 0.162.1", "head_sha": "<40 lower-case hex digits>",
 "base_sha": "<40 lower-case hex digits>", "completed": true, "overall_correctness": "patch is correct", "overall_confidence_score": 0.8,
 "findings": [{"priority": 2, "location": "tools/landing/nas_land.sh:40-44", "title": "[P2] ..."}]}
```

`reviewer` is `codex-review` or `claude-code-review`, `reviewer_version` non-empty text, `head_sha` the commit reviewed, and `completed`
true only for a structured result (below); each finding has an integer `priority` from 0 to 3, a `location` (`<path>:<start>-<end>`, or
empty) and a `title`. A `codex-review` also carries Codex's verdict, `overall_correctness`, as Codex wrote it (null when the review was
interrupted), and `overall_confidence_score` when the result has one. The rubric fixes the verdict, `"overall_correctness": "patch is
correct" | "patch is incorrect"` (`codex-rs/prompts/templates/review/rubric.md:85`), while its wire type is a free `String`
(`codex-rs/protocol/src/protocol.rs:3507`; the score is `f32`, `:3509`): both files are the same bytes at `rust-v0.162.1`, the installed
version, and in the upstream mirror at `092d3acd6` (2026-10-09). A `codex-review` also carries `base_sha`, the merge base its review
request named (#1061 P1, below). A `claude-code-review` carries none of these fields.

**The required arm and the advisory arm (the CC, 2026-10-13).** `codex review` is the required local arm. The `/code-review` plugin's arm
is ADVISORY until the CC's review-replay addendum measures it (arms E and F): below a score of 80 the plugin does not proceed to its comment
(`code-review.md:26`, "If there are no issues that meet this criteria, do not proceed"), and it skips a pull request it already reviewed
(`:11`), so a missing comment says nothing about the head.

**The base (#1061 P1, the Claude read and the probe's finding 3 at c999eee5).** Codex reviews HEAD against the merge base of its base
branch: the request's prompt reads "The merge base commit for this comparison is <sha>" (`codex-rs/prompts/src/review_request.rs:21`,
used when `merge_base_with_head` finds one, `:62-70`; that function "mirrors `git merge-base HEAD <branch>`",
`codex-rs/git-utils/src/branch.rs:13-15`). So a review run with its base at the head reviews nothing, and one with its base at a commit of
the pull request's own branch reviews part of the change, and either completed as "patch is correct". The normalizer records that SHA as
`base_sha`; `lg_gate` passes the gate, for the read head and each head that carries its change, `<head>:<git merge-base <head>
origin/main>`, and the gate requires each `codex-review`'s `base_sha` to be its head's. Measured on the 6 local `baseBranch` reviews
(read only): 3 named the merge base of their head with `origin/main`; the other 3 were delta reviews against a commit of the pull
request's own branch (not on `main`), each covering 1, 1 and 2 commits and leaving out 1, 5 and 1, which the gate now refuses.

**The gate** requires every listed file to be such a review, of the read head or of a head that carries the read head's change. It gives
2 for the first file that cannot be read, is not a normalized review or names another head, whatever its reviewer; for a `codex-review`
reviewed against another base than its head's merge base with `origin/main`, or that did not complete, or whose `overall_correctness` is not
exactly `patch is correct` or `patch is incorrect` (fail closed); and when no completed `codex-review` is listed. In `codex_wait`, a 2
says to correct or write again the local review files, not to wait for Codex (the probe's finding 8). Otherwise it gives 4 when a
`codex-review` says `patch is incorrect`, whatever its findings'
priorities, or has a finding of priority 0 or 1 ("a person decides": the CC adjudicates); otherwise 0. The P2 and P3 findings are printed as
counts, for the pull request's Follow-ups. The plugin's arm never stops the gate: its issues are printed as a count, each scored 80 or more
by the plugin's filter (its comment carries no score), and a run without a comment (`completed` false) is counted with the citation above,
both marked advisory. The pure-rebase check is the scripts' own: `lg_gate` runs `lg_same_change` (the change
identity above) on each file's `head_sha` that is not the read head, fetching a commit the clone lacks (`lg_have`, at the first call), and
passes the heads that carry the read head's change to the gate after the read head; the gate accepts those and no other. Its lines start
with `Local reviews: `, which `lg_gate` echoes for a 2 as well (python3's own exit 2 keeps its fixed line), and name a file by its place
in the list, never by its path, and no finding's text. Both scripts stop with exit 9 on a 2 or a 4, and read the files at every gate call,
so they must stay in place for the whole landing.

**`review_normalize.py`** (stdlib only) writes the file from each reviewer's own output and changes neither reviewer; it writes the file
whole (a new 0600 file, renamed over the target) and prints one line, never a path, a body or a title. A refused run writes nothing and
removes an older file at `--out` (Astra's follow-up 1 at c999eee5: a failed retry left the previous run's review for the gate).

- `codex-review --rollout <rollout.jsonl> [--head <sha>] --out <file>` reads the session rollout of one `codex review` (codex-cli
  0.162.1). Its lines are `{"timestamp", "type", "payload"}` (`openai/codex@rust-v0.162.1` `codex-rs/history/src/rollout_payload.rs:32-33`);
  the first `session_meta` names the worktree (`cwd`), its commit (`git.commit_hash`) and `cli_version`; the request is an
  `EnteredReviewMode` item and the result an `ExitedReviewMode` item at `payload.item` of an `event_msg` `item_completed` line
  (`codex-rs/protocol/src/items.rs:173-183`), whose `review_output` holds the findings, each with `priority` and `code_location`, and
  `overall_correctness` (`protocol.rs:3503-3545`). The rollout must hold exactly one review, of target `baseBranch`: the pull request's
  change against its base, the wrapper's default. A `--commit` review covers one commit and is refused, as are `uncommittedChanges` and
  `custom`. `base_sha` comes from the one request prompt between the request and the result (an `item_completed` `UserMessage`, measured
  on the 6 local `baseBranch` rollouts), whose base branch must be the target's; a prompt without a merge base (`:20`), none or two is
  refused. A Legacy rollout is refused too, fail closed: `codex exec` writes one only when the server refuses paginated threads
  (`codex-rs/exec/src/lib.rs:1425-1432`; paginated is the default, `:1461`), and only Legacy rollouts persist the
  `entered_review_mode` and `exited_review_mode` events (`codex-rs/rollout/src/policy.rs:141-155`).
  `head_sha` is the rollout's commit (`--head` must agree), `reviewer_version` is `codex-cli <cli_version>`, each location is
  relative to the worktree, the bodies are dropped, and `overall_correctness` is carried verbatim, with `overall_confidence_score` when
  present (a finite number, or the input is refused). `completed` is false when `review_output` is null (an interrupted review,
  `review.rs:94-95`) or `overall_correctness` is empty: when the reviewer's JSON does not parse, Codex keeps the text in
  `overall_explanation` and leaves `findings` empty (`codex-rs/core/src/tasks/review.rs:188-208`). One way there: the rubric lets a finding
  omit its priority or set it null (`codex-rs/prompts/templates/review/rubric.md:58`, `:78`), while `ReviewFinding.priority` is a required
  `i32` (`protocol.rs:3525-3531`), so one such finding drops every finding of its review, which would otherwise pass as "no finding". A
  priority outside 0 to 3 is refused.
- `claude-code-review --repo <owner/repo> --pr <n> --head <sha> --since <UTC time> --author <login> --reviewer-version <text> --out
  <file>` reads the plugin's ONE comment on the pull request, in its fixed format (`anthropics/claude-plugins-official@f359d43b`
  `plugins/code-review/commands/code-review.md:50-92`): "### Code review", then "Found N issues:" with N numbered issues, each followed by
  a link to the code at a full SHA, or "No issues found. ...". Every issue it posts passed its own confidence filter of 80 or more
  (`:20-26`), so each becomes priority 1 and none gets a finer priority; its location is the issue's first link. One GraphQL snapshot reads
  the pull request's `headRefOid` and every comment. "The PR head at the time of the comment" is defined as the head the caller read before
  the run (`--head`), which must still be the head when the comment is read, the comment bound to the run by `--since`: exactly one comment
  by `--author` (the account that ran the plugin; anyone can post the format) created at or after `--since`, whose first line is the
  heading and which was never edited (`lastEditedAt` null). No such comment gives `completed` false, which the gate notes as advisory: the
  plugin posts nothing for a closed, draft, trivial or already reviewed pull request, nor when no issue scored 80 (its `README.md:157-167`;
  `code-review.md:11`, `:26`). Two such comments, an edit, a head that moved or a count that does not match the list is refused. Every
  link to the code of `--repo` must name `--head`'s full SHA, and a list of issues must have one (#1061, the probe's finding 9: the
  comment of a run that read an earlier head is not taken for this head's; links to other repositories do not count).

Running each reviewer headless (commands only; neither was run by this change, and running the plugin posts a comment on the pull request):

```
# codex review, through the co-op's wrapper codex_review_read.sh (a detached worktree at the head), against the head's merge base with
# origin/main, the base the gate requires (#1061 P1)
codex_review_read.sh <clone> <pr> <head sha> "$(git -C <clone> merge-base <head sha> origin/main)" <out dir>
python3 -I tools/landing/review_normalize.py codex-review --head <head sha> --out <codex file> \
  --rollout "$(find ~/.codex/sessions -name "*$(jq -r .session <out dir>/run.json).jsonl")"

# Claude Code's official /code-review plugin, as shipped; its allowed-tools line (code-review.md:2):
#   Bash(gh issue view:*), Bash(gh search:*), Bash(gh issue list:*), Bash(gh pr comment:*), Bash(gh pr diff:*), Bash(gh pr view:*), Bash(gh pr list:*)
claude plugin install code-review@claude-plugins-official
head=$(gh pr view <pr> -R <owner/repo> --json headRefOid --jq .headRefOid); since=$(date -u +%FT%TZ)
claude -p "/code-review https://github.com/<owner/repo>/pull/<pr>"
python3 -I tools/landing/review_normalize.py claude-code-review --repo <owner/repo> --pr <pr> --head "$head" --since "$since" \
  --author <login> --reviewer-version "code-review@claude-plugins-official@<marketplace commit>; Claude Code <version>" --out <claude file>

LOCAL_REVIEWS=<codex file>:<claude file> nas_land.sh <pr> <read head prefix> <verdict file>
```

Measured on 2026-10-13 (read only): of the 15 local rollouts with an `ExitedReviewMode` item (codex-cli 0.160.0 to 0.162.1), every one had
it and its `EnteredReviewMode` at `payload.item` of `event_msg` `item_completed` lines; their targets were `baseBranch` 6, `commit` 4,
`uncommittedChanges` 3 and `custom` 2; one `review_output` was null; and one completed review said "patch is incorrect" with a single P2
finding (a `custom` review); a `baseBranch` review like it passed the gate at a6c8bf7c and is now blocked by its verdict (4). `review_normalize.py` gave,
on the first `baseBranch` review, "codex-review of 8eb4b532: completed; overall_correctness 'patch is
correct'; findings P0 0, P1 0, P2 0, P3 0" (exit 0, mode 0600), and refused the "patch is incorrect" review and the null one on their
targets (`custom`, `uncommittedChanges`; exit 1). `python3 -I` keeps the environment, so the variables reach the gate (measured with
Python 3.13.16). The plugin's run, the headless commands and a landing on local reviews are untested here.

## Provenance and digests

The files were moved from the CC's tools directory on 2026-10-10 and synced on 2026-10-11 to the live copies the CC installed at
00:02Z (the head-following function of uet#58 and correction #148); #975's fix commit then took the CC's live patch of
2026-10-11T03:37Z (P2-3 and P2-2, above). At the sync the shell scripts were the live copies with only host paths changed: the three
lines of the move (the repository default and `COORD` on one line, the record path, the gate path), the same line counts, and
`codex_gate.py` byte for byte. The live copies carry the CC host's paths in those expressions, so no digest of a live copy is
published here (#1061 P1-3, Astra at c999eee5: a digest of a host-specific file is an offline oracle for a guessed path, correction #161).
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
activity rules (above). The CC's adjudication of 5b8ba3b2 added the final fix: the newest `trading-cc-read` status was the first listed
(B1), nas's latest completed check run was decided by `completed_at` (Astra's follow-up 1, ruled fix-now), with the lock-hold and
trigger-window wording (P3-a, P3-d); Codex's change-identity finding is a declared gap (below) and its sandboxing of the validation a
follow-up. The CC's Claude micro at 3e6e7e46 (A1) and Codex's P2 at nas:289 added one more correction to nas's check runs: a failing
run stands unless a run of its name started and completed after it, and every page is read (above); in the same commit, for Codex's P1
at nas:234, both scripts read `trading-cc-read` from the combined status, every page of it (above). The live copies were then last
changed at 2026-10-11T05:03:28Z (the CC's patch that took the status-gate failure line). The table gives each file as committed: its
sha256 and line count. Before correction #136 the live scripts had 115 (uet) and 135 (nas) lines; after #148, 232 and 243; since
2026-10-11T05:03:28Z, 233 and 246; the live `codex_gate.py` had 108 lines after #148. Their digests, published here until #1061, were
removed (P1-3), and `tests/test_landing_scripts.py` now refuses any sha256 or digest prefix in this README that is neither a tracked
file's nor a named public artifact's.

| File | As committed |
| --- | --- |
| `uet_land.sh` | `887084a91e86168b7b908e997a455c092a7e1886a80dd22ebb0c3de70daa110d` (428 lines) |
| `nas_land.sh` | `1f817b196a07ffe7ee181c23a2b4969a616b36e9ed9fc165104409581dc2a70c` (498 lines) |
| `codex_gate.py` | `d5db338ec272d91f16fdca216b0504f56c595258c0b371fe84baa16452758ed7` (446 lines) |
| `review_normalize.py` | `003a82cd87ccb76b0955d6077a8504c2234d53fec3fddc278616b17c9df7a373` (345 lines) |

On 2026-10-13 three fixes the CC had made in its live copies were ported here alone: the repository slug and the merging account in
`nas_land.sh` (CC correction #198; here also `LANDING_REPO`, the login check, and `uet_land.sh`, whose block is shared), and the stale
running review in `codex_gate.py` (CC correction #200, its block and constant byte for byte). The live copies' other local differences
(`SQUASH_BODY_FILE`, correction #176's currency checks, the host paths) were not taken. Read at 2026-10-13T01:50Z, the live copies were
`nas_land.sh` (474 lines, changed 2026-10-12T23:07:56Z) and `codex_gate.py` (241 lines, changed 2026-10-13T00:47:19Z); no digest of
them is published. The local review set, `lg_gate`'s heads with the read head's change and `review_normalize.py` are new here.

Corrections the scripts carry: #118 (every gate before the merge, in order), #121 (a verdict file that states a landing gate needs
a receipt), #122 and #123 (a Codex review must have finished; uet#40 and uet#47 merged while one was running), #136
(verdict and record acceptance, change identity and the CI line: the three loose decision points the shared
`# >>> land-gate-fns` block replaced), the head-following of 2026-10-10 (uet#58: an update-branch rebase does not reach every API view at
once, so a head that moves during CI and carries the read head's change is followed, at most three times), #148 (the author address)
and #975's P2-3 (the CI allow-list), P2-2 (no text from `gh` or its API is printed: a failed merge, a failing status, every other `gh`
call), the gate error (P2: exit 4 and one fixed line, no traceback), the commit-status allow-list (P3) and P2-1 (the privacy scan
checks every prohibited identity), round 3 (above: the completion bound to the latest request, the gates read again before the merge,
typed values, no local diagnostics, the base re-read) and round 4 (above: the lock, the final gate, one read per file, the gate's
snapshot), and since 2026-10-13 #198 (the merging account) and #200 (a stale running review). The block is identical in both scripts,
apart from `lg_ci_state`, which only `uet_land.sh` has.

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
- The change identity ignores where an edit is (Codex F1 at 5b8ba3b2, pre-existing since #136): `lg_change_id` takes `git patch-id` of a
  diff at `-U0`, and a patch ID is "a sum of SHA-1 of the file diffs associated with a patch, with line numbers ignored" (git v2.53.0
  `Documentation/git-patch-id.adoc:17-18`), so the same changed lines at another place in the same file give the same identity, and a
  head that carries them there counts as the read change. No real landing has shown it, only a synthetic collision. Changing the anchor
  (`-U3` context, or another) changes which rebases keep their verdicts, a recorded practice, so the choice is a research-queue item
  (layer "landing gate change identity": `-U3` against the `-U0` status quo, measured over the last 30 landings' rebases), with no code
  change here.
- The attribution is by start time and commit only, not by trigger kind (C2, the CC's P3-2 at 761810d7): a Code Review row started by a
  ready event counts for a later `@codex security review` when it starts after it. No security-review row has been seen live, so its
  row strings are not measured; matching the trigger kind waits for one.
- The privacy scan's boundary (the CC's P3-5 at af9d1901): it finds the forms listed under Tests, and not hex or base64 of a mixed-case
  spelling, look-alike Unicode, zero-width characters, names split across lines, gzip or UTF-16 files, colon, `0x`, octal, `\u` or
  HTML-entity encodings, a name glued to letters or digits (`host=<name>01`, the letter and digit boundary of
  `scripts/host_name_scan.py`), or a generic running account joined by a character outside the joiner class.
- Very short prohibited names fail on coincidences (the CC's P3-6 at af9d1901): a two-letter name matches base64 fragments in several
  files and a one-letter name matches every file. This fails closed; names under about four characters are not useful entries.
- Local reviews (2026-10-13):
  - The normalizer accepts only a `baseBranch` review, the pull request's whole change against its base: a review the wrapper runs with
    `--commit` covers one commit and is refused, so the required arm must be run in the wrapper's default mode.
  - The plugin's arm is advisory (above): until the review-replay addendum measures it, its issues and a run without a comment are noted
    and never stop a landing. Its head is the caller's two reads and its links: a head that moved away and back during the run is not seen.
  - The files are read at every gate call, each once, so a file rewritten between two calls is decided on its new text at the later one.
  - A Legacy rollout is refused (fail closed, above), so a review whose `codex exec` fell back to Legacy history gives no file; it has to
    be run again where the server serves paginated threads.

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
own exit code, nothing printed; #975 P2-2), a check that the digests in the table above are those of the committed files, and a scan of
every file under `tools/landing`, bytecode excepted, for home paths and for the identities that must not appear (#975 P2-1, below).
Round 3 adds, each failing at af9d1901: a review that started before the latest trigger and finished after it (exit 3, not 0), the
gate giving 0 then 5 in `uet_land.sh` without, with a wrong and with an accepted `GPT_VERDICT`, a status or record that changes during
the wait (exit 2), a main that moves after the validation (validated again; exit 13 when it keeps moving), the validation's output kept
in its file and not printed, failed or malformed CI replies, a missing, broken or chatty gate, a missing clone and a missing verdict
file under a home-like path (no path printed), an unusable `TMPDIR` on a failed merge, and a receipt naming only the caller's shorter
prefix. Round 4 adds, each failing at 761810d7 (15 of the 20 flips merged there; the other five stopped, four of them on the
`trading-cc-read` re-read of round 3): the final gate's reads as the last calls before the merge, in their order; each gate flipped
between its first read and the final gate (a verdict file that gains CHANGES_REQUESTED, a `GATES_DONE` that disappears, a
`trading-cc-read` status that turns to failure, a failure posted in the same second as its success and listed first (#975 B1, which
also merged at 5b8ba3b2, as did the same pair at the first read), a read of it that fails with nothing on stdout, its record that gains
CHANGES_REQUESTED, Codex giving 3 at the final call, a queued CI re-run, nas's completed failing re-run with no start (Astra's follow-up
1: at 5b8ba3b2 this flip merged, and so did a landing whose CI wait met that run or a completed run without `completed_at`), the head
moving, nas's main moving after the validation read it), each with its exit code and no merge; a Codex review that starts during nas's first validation or during the retry after main
moved; an unreadable `origin/main` (its own stop, exit 13, the CC's P3-4); a `trading-cc-read` read that fails with empty stdout at
the first or the final read; a held landing lock (exit 14 before any call), and a child that outlives the landing, which must not keep
it; an unreadable verdict file,
record, receipt or `GPT_VERDICT`, and a verdict file removed after its first line was read (no path printed, no merge); for the gate,
an edit between two reads, a reply whose newest revision is not its body, a review of another commit, revisions by another account,
the 👀 reaction, a comment id beyond 32 bits, an unattributable completion before and after ten minutes, and the captured nas#975
summary comment; and a queued re-run beside an old success in nas's check runs. #975 A1 and Codex's P2 at nas:289 add, each failing at
3e6e7e46 or at 5b8ba3b2, as check-run lines with their counts written out and as whole landings, and for F and G also as final-gate
flips: the overlap F (a failure that started later and finished first, inside a success of its name; it merged at 3e6e7e46) and its
mirror G (it merged at 5b8ba3b2); a failing run with no start, and a failure beside a success with no start (both merged at 3e6e7e46),
which no run supersedes; a success tied with a failure (exit 5 at once; 3e6e7e46 waited for the timeout, exit 6) and with a neutral (it
merges; exit 6 at 3e6e7e46); validate's own tie, the neutral listed first, and its own overlap F (exit 6 and a merge at 3e6e7e46); and
two pages of check runs, page 1 holding 100 runs, with a failing or a running check on page 2 (each merged at 3e6e7e46 and at
5b8ba3b2). Their controls give the same answer at all three commits: a failure re-run to another failure stops, and the #886
cancellation, a failure re-run to success, the live overlap of a success and a skipped run, and a page-2 failure that its re-run on
page 1 supersedes land; check runs that jq cannot judge print neither jq's error nor the value (exit 6). For Codex's P1 at nas:234,
in both scripts: a `trading-cc-read` failure or pending status behind 100 newer statuses of 100 other contexts, or of one, stops with 2
(at 3e6e7e46 the gate gave "no status", exit 0 with nothing printed, and both scripts landed: exit 0, one merge), a success behind them
has its record checked, and a reply that is not an array of pages with statuses, an empty one included, stops with 2 and prints nothing
of it. The fake `gh` serves page 1 of the statuses list as the first `per_page` statuses and builds the combined status from it as
GitHub gave it when measured: each context once with its newest status, in pages of `per_page` contexts. It is offline, needs `jq`,
and is Linux-only. A script edit that moves a decision site fails the module instead of leaving it untested.

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

**2026-10-13 adds**, each failing at c63c83a8 (measured: this module run against that commit's `tools/landing` gave 104 failures and 7
errors):

- the repository: `nas_land.sh`'s default, `LANDING_REPO` and its empty fallback, and every repository-scoped `gh` call of a landing
  naming it (the literal named the old slug);
- the merging account: `LG_AUTHOR_LOGIN` in both scripts; `lg_author_email` asking for `users/<account>` with the organization's slug
  (it asked for `users/native-agent-stack`) and for the owner when the variable is unset; a login of another shape refused before any
  call (exit 11);
- correction #200: a running review 89:59 and 90 minutes after its start, after the start's own 👀, a connector note, a summary edit and a
  connector reaction, while a person's comment or reaction does not count (each 5 gave 3);
- local reviews:
  - the gate on canned files: 0 with P2 and P3 counted; 4 for a P0 or a P1; 2 for each malformed form, another head, an incomplete
    review, a missing file, no read head, and through the alias and both variables together;
  - the command line with heads after the read head;
  - both scripts end to end through the real gate: a landing, a stop that echoes the gate's own line, a review of a pure rebase that
    `lg_gate` passes on (once, even when two files name it, while a third of another change stops the landing), the landing lock held at
    every gate call, and the final gate's reads unchanged.
- `review_normalize.py`, on synthetic rollouts in codex-cli 0.162.1's shape and on plugin comments in the plugin's format:
  - relative locations without bodies;
  - an interrupted review and the parse fallback written as not completed;
  - each refused rollout: another target, two reviews or none, a line that is not JSON, no commit, another `--head`, a priority outside
    0 to 3 or null;
  - the plugin's issues as P1 with their links;
  - its no-issues line;
  - no comment of the run, as not completed;
  - a head that moved, an edited comment, two comments, a count that does not match, another format and a failed `gh`, each refused;
  - its usage errors (exit 2) and the script run isolated.
  - Each written file is read back by the gate.
- The CC's follow-up of 2026-10-13 (the verdict and the advisory arm) adds, each failing at a6c8bf7c (measured as above against that
  commit's `tools/landing`; the count is under "Local commands run" in the pull request):
  - `patch is incorrect` with only P2 and P3 findings, and with none, blocked (4), in the gate and end to end;
  - a verdict that is not exactly one of the two stopping (2): unknown text, a trailing space, other capitals, null on a completed review;
  - `patch is correct` with P2 and P3 passing, counted; the verdict and the confidence carried by the normalizer, a confidence that is
    not a finite number refused;
  - the plugin's issues and a run without a comment noted as advisory, never stopping the gate or a landing; the plugin's arm alone is
    no review (2); a plugin file of another head still stops (2).
- #1061 (the Claude read and the CC's `/code-review` probe at c999eee5) adds, each failing at c999eee5 (measured as above against that
  commit's `tools/landing`; the count is in the pull request):
  - the base: a review against its own head or against `head^` of a two-commit change stops both scripts (2, then exit 9), and one
    against the merge base lands; in the gate, another base, an unknown one, no fact at all and a fact of another shape stop; the
    normalizer takes the base from the one request prompt and refuses none, two, the fallback prompt, another branch and a prompt
    after the result;
  - a set but empty variable, either of them, stops (2, then exit 9) without asking the connector (it replaced the test that pinned an
    empty value as unset);
  - a stale row of another commit beside our head's review that ended Cancelled gives 4, not 5;
  - a trigger after a stall waits 10 minutes (3) and then gives 5, and a trigger while the review was live gets the full window;
  - the connector's 👀 without a Running row gives 5 after 90 minutes;
  - a `LANDING_REPO` of another shape stops before any call (exit 2); every `-R "$R"` is quoted;
  - an account of type Organization, Bot or none gives no address (exit 11);
  - a Legacy rollout is refused with its own reason;
  - a local 2 tells the operator to correct the review files, not to wait for Codex;
  - a plugin comment whose links name another commit, or whose issues link only to another repository, is refused;
  - Astra's P1-3: every sha256 and every digest prefix in this README is a tracked file's or a named public artifact's (at c999eee5,
    seven full digests and four prefixes of host-only files were not); a planted one is found;
  - Astra's follow-ups 1 and 2: a refused retry removes the earlier file at `--out`, and a confidence that overflows to infinity
    (`1e999`) stops the gate (2).

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
| The newest `trading-cc-read` status (B1 at 5b8ba3b2) | `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…` (the local upstream mirror at that commit, the same bytes); `jqlang/jq@jq-1.8.1:src/jv_aux.c`, `9b510dff29fede9f5e9d6a61d59b5d0d69419fc74a2bf684331295d0200829e8` | `api.github.com.json:55724` "Statuses are returned in reverse chronological order. The first status in the list will be the latest one", so `tcc_read_gate` took `first` (until Codex's P1 at nas:234, below); `jv_aux.c:669-674` `sort_cmp` breaks ties by input index, so `sort_by(.updated_at)\|last` kept the older of two statuses with the same `updated_at` (measured with jq 1.8.1) |
| A check run's recency is its completion (Astra's follow-up 1 at 5b8ba3b2) | `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…` (the local upstream mirror at that commit) | `:55504-55514` the list-for-ref `filter` parameter: "Filters check runs by their `completed_at` timestamp. `latest` returns the most recent check runs" (default `latest`), so `nas_checks` asks for `filter=latest`, and until A1 (below) it judged a name on the completed run with the greatest `completed_at`; `:146097-146107` `check-run.started_at` and `completed_at` are both `"nullable": true`, so a completed run without `completed_at` counts as incomplete (a tie with two conclusions did too until A1) |
| Where an edit is, which the change identity ignores (Codex F1 at 5b8ba3b2, declared) | `git/git@v2.53.0:Documentation/git-patch-id.adoc`, `e835ca2a7a11b54e3db93221466928c887ef9529a9b34b475d746888e43af410` (the local upstream mirror at `67ad4214`) | `:17-18` a patch ID is "a sum of SHA-1 of the file diffs associated with a patch, with line numbers ignored" |
| A failing run stands unless a run of its name started and completed after it (A1, the CC's Claude micro at 3e6e7e46) | `jqlang/jq@jq-1.8.1:docs/content/manual/v1.8/manual.yml`, `e0eb9a08…` (the local upstream mirror at `jq-1.8.1`, read on 2026-10-11) | `:1544-1552` jq orders `null` before every other value and strings by code point, and `:2425-2433` `>` uses that order, so a run whose `started_at` or `completed_at` is null is never later than another run (the program also gives such a failing run no superseder); `:1334-1347` `any(generator; condition)`, `:1579-1590` `group_by`. The times REST gives order as strings: all 2,072 runs on the 70 heads replayed on 2026-10-11 have both in the form `YYYY-MM-DDTHH:MM:SSZ`, none with a fraction or a null (112 of them, all skipped, completed before they started; the rule compares a run's times only with another run's) |
| Every page of check runs (Codex P2 at nas:289) | `cli/cli@v2.102.0` (the local upstream mirror at `fc4b137c`): `pkg/cmd/api/api.go`, `030eda84…`; `pkg/cmd/api/pagination.go`, `0565f3040ed1843875732e5df5dbc50fdbc90bb3b45685eabfd83c133b4c79b0`; `go.mod`, `115bc54638dc4fa5a72da79d9f87fca699ee5b1fc7e21ea9314a517fb18fb40b`; `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…`; `github/docs@be38ec5d78e24172587e61b3c6ff40ace1865c71:content/rest/using-the-rest-api/using-pagination-in-the-rest-api.md`, `418bdf281d74a89c7dabedc4af53a6f7b286f2416e7670d9cc71453db08d8640` (the local upstream mirrors, read on 2026-10-11) | `api.github.com.json:55518`, `:55521` the list-for-ref endpoint takes `per_page` and `page`, `:344577-344585` `per_page` is "(max 100)", `:344616-344624` `page`, `:55563-55564` its reply carries a `Link` header, `:347322-347327` whose example names the next page with `rel="next"`; the docs, `:22` "You can use the `link` header from the response to request additional pages of data", `:28` the header is omitted "if all results fit on a single page", `:49` "The URL for the next page is followed by `rel="next"`"; `api.go:358-360` `--paginate` keeps a `per_page` the path has (`pagination.go:94-110`), `:431-470` asks for page after page while `pagination.go:17-24` finds `rel="next"`, `:362-371` with `--slurp` writes every page into one JSON array, `:260-273` `--slurp` needs `--paginate` and refuses `--jq`, so `nas_checks` runs jq itself on the array (gh's own `--jq` is go-gh's, `api.go:28`, on gojq, `go.mod:21`, `:141`), and `:546`, `:553-565` the body of a failed page is still written and gh exits non-zero, so its exit code is checked before jq reads. Measured on 2026-10-11 at `26f551b1` (43 runs): `per_page=10` gave 5 pages of 10, 10, 10, 10 and 3 runs, `total_count` 43 on each, the same 43 ids as one `per_page=100` page, the next link `filter=latest&per_page=10&page=2`, and the same four counts |
| The newest status of each context, on every page (Codex P1 at nas:234) | `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…`; `github/docs@be38ec5d78e24172587e61b3c6ff40ace1865c71:src/rest/data/fpt-2022-11-28/commits.json`, `57f0a021883f869390a022e41bdbe77267d5ebbdbf59849d2891380f5e363247` (the local upstream mirrors, read on 2026-10-11) | `api.github.com.json:55664-55667` `GET /repos/{owner}/{repo}/commits/{ref}/status`, "a combined view of commit statuses for a given ref", whose `state` is success "if the latest status for all contexts is `success`"; `:55687`, `:55690` it takes `per_page` and `page`; `:55694-55699` its reply is a `combined-commit-status`, `:148666-148707`, with `statuses` of `simple-commit-status` (`:148606`: `context`, `state` and a nullable `description`) and `total_count`; the docs' REST data, `commits.json:9530`, give the same text and parameters. Neither says the entries are one per context. Measured on 2026-10-11, read only: on 8 public heads (`kubernetes/kubernetes`, 2 to 35 statuses in 2 to 15 contexts) and on the 12 of our 80 heads that have statuses, every context appeared once, as the list's first (newest) status of it, and `total_count` was the number of contexts; with `per_page=5`, the first page of each of the 5 heads with 13 to 15 contexts carried a `Link` `rel="next"`, and `--paginate --slurp` gave the same entries as one page of 100 on all 8; on our 80 heads the combined read and the 3e6e7e46 read gave the same `trading-cc-read` state and description |
| The connector's own layout and footer | `tests/fixtures/landing/codex-summary-comment.json`, `3918a25359d64ea4b2bcf31ec9ac9d92ff681270c072da6af625575eab720792` (the summary comment of nas#975 with its four revisions, masked by `mask_packet.py`'s rule with nothing to replace; the body's sha256 is `1236fe482740fa1ccdaac6d50d4e1e77f6a6e961d64e8dd5377a4923a6f8d0dc`) | a row of four cells (the review kind "📝 Code Review", the status "✅ Completed" with its time, the commit 761810d in backticks, the trigger kind "Manual request"), the Running form "🔄 Running since" with its time, the newest revision equal to the body, every editor the Bot `chatgpt-codex-connector`, and the footer "Codex reacts with 👀 while any review is running, comments if it has suggestions, and reacts with 👍 once all reviews finish with no findings" |

2026-10-13: the transfer, CC corrections #198 and #200, and local reviews. Read on 2026-10-13 from these sources:

- the `github/docs` mirror at `be38ec5d`, as above;
- `openai/codex` at the tag `rust-v0.162.1`, fetched with `curl -fsSL https://raw.githubusercontent.com/openai/codex/rust-v0.162.1/<path>`
  (installed: codex-cli 0.162.1);
- `anthropics/claude-plugins-official` at `f359d43b`, fetched the same way; its bytes equal the local marketplace snapshot, whose `.gcs-sha`
  names that commit (installed: Claude Code 2.1.296);
- the GraphQL schema, fetched again: the same bytes, sha256 `3ed09565…`.

| Mechanism | Source at the pin, sha256 | Lines read and what they say |
| --- | --- | --- |
| The redirect of a transferred repository | `github/docs@be38ec5d78e24172587e61b3c6ff40ace1865c71:content/repositories/creating-and-managing-repositories/transferring-a-repository.md`, `ed316b3fff6ecc09247826cb872df41beeab9088eeeaccbdb73703fedbfcf8ae` | `:62` "All links to the previous repository location are automatically redirected to the new location. When you use `git clone`, `git fetch`, or `git push` on a transferred repository, these commands will redirect to the new repository location or URL"; `:68-69` "If you create a new repository or fork at the previous repository location, the redirects to the transferred repository will be permanently deleted" |
| The no-reply address is a user account's (#198) | `github/docs@be38ec5d:content/account-and-profile/reference/email-addresses-reference.md`, `fbbf1c5f700d977f8672462859621f9412e65531a57790fa779e191a4d1c0949` | `:47` "your `noreply` email address is an ID number and your username in the form of ID+USERNAME@users.noreply.github.com" |
| A login's shape (#198, the login check) | `github/docs@be38ec5d`, the IAM configuration reference's `username-considerations-for-external-authentication.md`, `591df6bd88afa6f28a4f0d030331821dfbef256187da3834cece6d13b4468ef4` | `:94` usernames "must not exceed 39 characters"; `:103` they "can only contain alphanumeric characters and dashes (`-`)"; `:126-127` a name that starts with a dash or holds two consecutive dashes is not created |
| `codex review`'s result and its rollout | `openai/codex@rust-v0.162.1`: `codex-rs/protocol/src/protocol.rs` `499bd1fd429418778d26998c48da2a5a22fe2965f4684e69fdf99e6b4c7e4330`, `codex-rs/protocol/src/items.rs` `5ca7f804a77dc8f132bb1eda4045e693d2d9b595cf70fc0877ca0cc98c5b621c`, `codex-rs/core/src/tasks/review.rs` `4961b4deff8f665501b3bd5ad9fd386c9651999df8a7cf757bf8567b380eab52`, `codex-rs/history/src/rollout_payload.rs` `ac6c17fda98ecc6377132ac9a34fb4771e902632b943decc94261961891a3598`, `codex-rs/prompts/templates/review/rubric.md` `ec60e7f36a1d1c2679ce095c0205ecc56f7dd8fb57707a13ef362072390f219f` | `protocol.rs:3503-3545` `ReviewOutputEvent` (`findings`, `overall_correctness`, `overall_explanation`, `overall_confidence_score`), `ReviewFinding` (`title`, `body`, `confidence_score`, `priority: i32`, `code_location`), `ReviewCodeLocation` (`absolute_file_path`, `line_range`), `ReviewLineRange` (`start`, `end`); `items.rs:44-46` `TurnItem` is tagged by `type`, `:173-183` `EnteredReviewModeItem` (`target`) and `ExitedReviewModeItem` (`review_output: Option<ReviewOutputEvent>`); `review.rs:94-95` an abort exits review mode with no output, `:188-208` a text that does not parse becomes `overall_explanation`, every other field at its default; `rollout_payload.rs:32-33` a rollout line's item is tagged by `type`, in snake case; `rubric.md:58`, `:78` a finding's priority may be omitted or null, `:85` `overall_correctness` is "patch is correct" or "patch is incorrect" |
| The `/code-review` plugin | `anthropics/claude-plugins-official@f359d43b406057f1a8cdbc4ea93b827642c162e6` (committed 2026-10-11T02:41:21Z): `plugins/code-review/commands/code-review.md` `7d5a0bc9a41babad32a387152f9680316997bc4ad376928827d670b1760cc890`, `plugins/code-review/README.md` `1fca74bab6969b609519927ae49112760e15d8113eef6bbcf9b9a96c49d73c89` | `code-review.md:2` its `allowed-tools`; `:11` it does not proceed on a closed, draft or trivial pull request or one that "already has a code review from you from earlier"; `:20-26` each issue is scored from 0 to 100 and those under 80 are filtered out, `:26` "If there are no issues that meet this criteria, do not proceed" (why its arm is advisory and a missing comment does not stop the gate); `:28` it comments with `gh`; `:50-84` the comment's two forms; `:86-92` a link names the full SHA and `#L<start>-L<end>`; `README.md:157-167` "No review comment posted", among its causes "No issues scored ≥80 (no comment needed)" |
| The comment's fields | the GraphQL schema, `3ed09565…` | `:21203` `type IssueComment`, `:21215` `author: Actor` (nullable), `:21225` `body: String!`, `:21240` `createdAt: DateTime!`, `:21260` `fullDatabaseId: BigInt`, `:21287-21290` "The moment the editor made the last edit", `lastEditedAt: DateTime` (nullable); `:44787` `PullRequest.headRefOid: GitObjectID!` |
| Codex's verdict (the CC's follow-up) | `openai/codex@rust-v0.162.1` (installed: codex-cli 0.162.1) `codex-rs/prompts/templates/review/rubric.md` `ec60e7f3…` and `codex-rs/protocol/src/protocol.rs` `499bd1fd…`; the upstream mirror at `092d3acd6bec3e3a14bdc7e7a2810ab628ab759d` (2026-10-09) holds the same bytes of both | `rubric.md:85` `"overall_correctness": "patch is correct" \| "patch is incorrect"`; `protocol.rs:3507` `pub overall_correctness: String` (free text on the wire, so the gate stops on any other value), `:3509` `pub overall_confidence_score: f32` |
| The review's base (#1061 P1) | `openai/codex@rust-v0.162.1`: `codex-rs/prompts/src/review_request.rs` `f4896d6746c3508aa08b72ce15ce143f9041015da9da37b044cdaf4f6f838fc0`, `codex-rs/git-utils/src/branch.rs` `86774c34df2bcb4b55ff5340bc2ef644bf64a94d14b122dbb29004ef01b370c5` (the mirror at `092d3acd6` holds the same bytes of `branch.rs`) | `review_request.rs:21` the base-branch prompt, "The merge base commit for this comparison is {{merge_base_sha}}. Run `git diff {{merge_base_sha}}` to inspect the changes relative to {{base_branch}}", `:20` the fallback prompt that names no SHA, `:62-70` the merge base from `merge_base_with_head(cwd, branch)`, else the fallback; `branch.rs:13` it "mirrors `git merge-base HEAD <branch>`", `:15` its definition. Measured on 2026-10-13, read only: on the 6 local `baseBranch` rollouts the prompt is an `item_completed` `UserMessage` after the request, and 3 named the merge base of the head with `origin/main`, while 3 named a commit of the pull request's own branch |
| A Legacy rollout (#1061 P3) | `openai/codex@rust-v0.162.1`: `codex-rs/exec/src/lib.rs` `51b62cef4893c6d07b51753fc2716fc05985cdc9de6673f2fa2d974779454d4b`, `codex-rs/rollout/src/policy.rs` `65ce50e843547719295fd884b651552c1227085e8d0acfef2161b4ec3111dcbc` | `lib.rs:1425-1432` on the server's error "paginated threads require thread/turns/list and thread/items/list support" the thread starts again with `history_mode = None` (`:1431`), `:1461` paginated by default unless ephemeral; `policy.rs:141-142` "Only persist these legacy events when the thread's history mode is Legacy. New, paginated rollouts persist ItemCompleted events with TurnItems.", `:143-155` among them `EnteredReviewMode` and `ExitedReviewMode`, `:228-282` the paginated `ItemCompleted` path |
| No upstream review time limit (#200's value) | `developers.openai.com/codex/llms.txt` `72459eb4e2e6d3b1a143f3c40860b7dd65fb061cdec3b18470ed8867382d8552`; `learn.chatgpt.com/docs/code-review.md` `c18b2fe184104facf5d044631ee151b2394baab1c44218be8b9d60c7dbd33020`; `learn.chatgpt.com/docs/third-party/github.md` `1ab502138a121ac571faa37f161bf79224e1e23cdc0e70f7a0be835f2c2d3c9f` (fetched 2026-10-13) | the index's "Code review" entry points to `code-review.md`, which has "Use the review chat to stop a running review" (:129) and no time; `github.md:52` "Wait for Codex to react (👀) and post a review", `:170` "Codex reacts while the review is running", `:196-205` for "If Codex doesn't react or post a review" settings only (`:199` "Confirm the pull request belongs to a GitHub repository connected to Codex"); no page states a limit |
| #200's measured basis | the gate's own query, read only, on nas#1056 at 2026-10-13T03:06Z | the summary's row Running since 2026-10-12T22:56:31Z, its last edit 22:56:32Z, the connector's 👀 at 22:56:34Z, and no connector activity after it (250 minutes); the CC set 90 at 111 minutes |
| The variables reach the gate under `-I` | measured with Python 3.13.16 | `LOCAL_REVIEWS=x python3 -I -c 'import os; print(os.environ.get("LOCAL_REVIEWS"))'` printed `x`: isolated mode ignores the `PYTHON*` variables, not the environment |
