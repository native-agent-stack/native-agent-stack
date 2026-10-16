# Landing scripts

The command center (CC) lands pull requests with the files kept here, so the repository holds the one copy and its tests: three
landers, `uet_land.sh` (the private trading repository), `nas_land.sh` (this repository) and `horizon_land.sh` (the private horizon
repository, since 2026-10-15), and `codex_gate.py` (the Codex review gate that the first two call). They merge pull requests. No
workflow runs them: the CC runs them from a clone of this repository, and CI runs their tests.

## What each does

**`uet_land.sh <pr> <read-head-prefix>`** lands a pull request of `seathatflowsinourveins/us-equities-trading` by squash
merge. In order: `nas_land.sh`'s two inputs refused when either is set (exit 2 before any call; "A nas input in a uet landing", below);
the landing lock of the repository (exit 14 when another landing holds it; below); the `trading-cc-read` commit
status and its record (below); each file in `VERDICT_FILES` (and `GATES_DONE` when such a file states a landing gate); the head is
the read head or a pure rebase of it; a draft is marked ready and `codex_gate.py` must report the latest review finished (polled for
up to 20 minutes); when Codex reports its usage limit, `GPT_VERDICT` (the co-op's verdict naming the read head) stands in for it; the
branch is updated by rebase and its change must equal the read change; CI is complete with nothing failing and `ci-gate` reported (a
head that moves during CI is followed, at most three times, only when it carries the read head's change, otherwise exit 3); open review
threads stop it (exit 8); the no-reply author address is formed; the final gate reads every gate again (below); the merge is pinned to
the head with `--match-head-commit` and names the account's no-reply address as its author (below).

**`nas_land.sh <pr> <read-head-prefix> <verdict-file>...`** does the same for this repository, `native-agent-stack/native-agent-stack`
since its transfer to the organization on 2026-10-12 (`LANDING_REPO` overrides it; "The repository", below),
with the verdict files as arguments (at least one) and these differences: local reviews are required (`LOCAL_REVIEWS`, or a waiver
bound to the pull request and the read head, `LOCAL_REVIEW_WAIVER`; exit 2 before any call otherwise; "Local reviews", below; #1061
round 2), a local review that says `patch is incorrect` with only P2 and P3 findings passes only on the CC's adjudication
(`LOCAL_REVIEW_ADJUDICATION`, the CC's ruling of 2026-10-13; "Local reviews", below), the squash body can be a file (`SQUASH_BODY_FILE`;
"The squash body", below), `manifests/evidence.json` is left out of the change
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
newest revision is not its body: poll again), 4 (the latest such review ended other than Completed, a summary last edited by an account other
than the connector, or the gate itself failed: any exception, a failed `gh` call included, prints one fixed line naming only the error
class, never a traceback, which would print file paths, or `gh`'s output; #975 P2), or 5 (Codex is unavailable: a usage-limit or
account notice since the trigger, no connector activity for 10 minutes, or a review shown running with no connector activity for 90
minutes, below). Both scripts stop with exit 9 on a 4 at any call, and on a 3
at any call but the wait, which polls a 3 for up to 20 minutes. A trigger is the pull request's creation, a ready-for-review event, or a comment by anyone but the connector that
starts with `@codex review` or `@codex security review`; a push is not a trigger. A Running row gives 3 until it is stale (below). When
`LOCAL_REVIEWS` names review files, the gate reads no connector data and decides from the files alone, and from the CC's adjudication
record when `LOCAL_REVIEW_ADJUDICATION` names one ("Local reviews", below).

**A stale running review (CC correction #200, 2026-10-13).** The transfer of this repository to the organization cut the connector's
access in the middle of a review, and its summary row stayed Running, so the gate gave 3 for as long as it stayed so (a landing stopped
with exit 9 after its 20-minute wait). A row shown running with no connector activity after its start for `STALE_RUNNING_MINUTES` (90)
now gives 5, "Codex unavailable", never 0. Activity is a connector comment other than a summary, a connector reaction, or an edit of a
summary; the start itself writes a summary edit and the 👀 reaction within seconds, so the age runs from the last activity. `nas_land.sh`
proceeds on a 5 only under a waiver (local reviews are required there, "Local reviews", below) and `uet_land.sh` needs `GPT_VERDICT`, as
for every 5. The block is the CC's operational patch of 2026-10-13T00:47Z, ported alone and byte for byte. #1061 (the Claude read and
the CC's `/code-review` probe at c999eee5) refined it:

- the age runs from the later of the last activity and the latest trigger, and a trigger that came after the review had already gone
  stale gets `NOSTART_MINUTES` (10), the grace a first trigger gets (before, an `@codex review` after a stall gave 5 at once);
- the latest review of the read head or the current head since the trigger decides (#1061 round 2, Astra's P2 at 974090cf): when it
  ended other than Completed, the gate gives 4, before the stale 5 and before a 0. At 974090cf only a failure with no completion at all
  gave 4, so a completion hid a later Cancelled review of the same head: beside a stale row of another commit the gate gave 5 (nas
  proceeded), and with no row running it gave 0, as the base did ("any completion evidence passes"). A completion, or the connector's
  👍 after one of those reviews started, that comes after the failure still supersedes it.

The connector's 👀 with no Running row is a review running with no bound (3), as at c999eee5. 974090cf bounded it too, and that 5 was a
new opening that `nas_land.sh` proceeded on, so the CC's delta read at 974090cf had the 3 back (#1061 round 2): a waived nas landing or
a uet landing waits on it, and stops with exit 9 after its 20 minutes.

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

**The squash body (`nas_land.sh`; #1061 round 2 and 2026-10-13).** A landing names a body only to record a waiver or an adjudication, or
when `SQUASH_BODY_FILE` is set; otherwise GitHub's default stands (the repository's squash default is the pull request's commit messages).
The waiver's line or the adjudication's ("Local reviews", below) follows a blank line after the body GitHub offers the merging account
(`viewerMergeBodyText(mergeType: SQUASH)`, read once before the author lookup; exit 7 when the read fails). `SQUASH_BODY_FILE` is the CC's
(2026-10-12: for a pull request whose commit messages carry a claim corrected after review), ported from its live copy on 2026-10-13. When
set, it must name a readable, non-empty regular file other than `-`, or the landing stops with exit 2 before the lock and any call, the path
not printed: `gh` reads a body file when the merge call starts, and reads standard input for `-` (`cli/cli@v2.102.0`
`pkg/cmd/pr/merge/merge.go:146-153`, `:177`, "Read body text from `file` (use "-" to read from standard input)";
`pkg/cmdutil/file_input.go:8-15`). A set but empty value stops too: the live copy took it for unset, and the merge fell back to the
default body, which is what the file is there to prevent (#1061 P1 was the same fallback, an empty `LOCAL_REVIEWS` taken for unset).

The file's content is checked, not only its metadata (#1075: Astra's P2-1 and the co-op's codex review, P2 at `nas_land.sh:585-586`, at
ca6f880b, where bytes that are not UTF-8, 1 MiB, a NUL byte alone beside the waiver and a file emptied after the start all merged). One
bounded reader (`SB_READER`, `nas_land.sh:89-113`) reads at most 64 KiB and one byte, and refuses a NUL byte, more than 64 KiB, anything but
strict UTF-8 (Python's decoder; glibc's iconv 2.43 took code points above U+10FFFF, measured) and a file that holds no text; it writes the
file's bytes, their trailing CR and LF bytes dropped, through `sys.stdout.buffer`, so the locale's encoding never touches them (#1075, the
co-op's re-review at f3f1cabe, P2 at `nas_land.sh:95`: it wrote the decoded text through `sys.stdout`, whose encoding is the locale's,
`python/cpython@v3.13.16` `Doc/library/sys.rst:1838-1839`, and under an ISO-8859-1 locale "é" came out as one byte and "€" ended it with
nothing written; under `LC_ALL=C` Python turns on its UTF-8 Mode, `Doc/library/os.rst:142-144`, so the test compiles an ISO-8859-1 locale
into a scratch `LOCPATH`, which glibc reads, `locale(7)`). It reads the file three times: before the lock and any call (exit 2), when the squash body is built
(exit 7, nothing merged), and at the final gate (`nas_land.sh:581-586`; exit 7, also when the text changed after the body was built). The
merge takes the text of the second read as `--body`, whether the file is the whole body or comes before a waiver's or an adjudication's line,
because `--body-file` would read the file again when the merge call starts (`merge.go:146-153`), after the final gate. This differs from
the live copy, which passes `--body-file`. The bound: the body is one argument to `gh`, and Linux bounds one argument at `MAX_ARG_STRLEN`,
"(PAGE_SIZE * 32)" (`torvalds/linux@v6.18` `include/uapi/linux/binfmts.h:15`), 131072 bytes on this host's 4 KiB pages with the
terminating NUL (measured: 131071 bytes passed, 131072 did not); 64 KiB leaves room for the line.

Beside a waiver or an adjudication the body is the file's text, a blank line and that line, and the offered body is not read, because `gh`
takes `--body` or `--body-file`, never both ("specify only one of `--body` or `--body-file`", `merge.go:138-143`). The waiver and the
adjudication never meet: the waiver is read only without a local review set, the adjudication only with one (`nas_land.sh` refuses an
adjudication set without one, below). When the body is built, the waiver or the adjudication is read and checked again too (`waiver_check`,
`adjudication_check`; the CC on the co-op's codex review), so the line is never taken from an earlier read (`nas_land.sh:660-682`).

**A nas input in a uet landing (#1075, the CC's read).** `LOCAL_REVIEW_ADJUDICATION` and `SQUASH_BODY_FILE` are `nas_land.sh`'s inputs
alone. `codex_gate.py`, which `uet_land.sh` runs too, decides with the adjudication wherever it is set, while `uet_land.sh` would neither
bind it to the pull request and the head nor record it in a squash body, nor read a body file; and either variable can be inherited, for
example from a nas landing in the same shell. So `uet_land.sh` stops with exit 2 when either is set, an empty value included (`${VAR+x}`,
the #1061 P1 test), before the lock and any call, and prints one line that names the variable as nas-only (`uet_land.sh:34-40`).

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
- **`horizon_land.sh` (below):** GitHub enforces its three required statuses at the merge: "all required status checks must pass", and
  "Any person or integration with write permissions to a repository can set the state of any status check", unless an app is selected as
  the expected source (`github/docs@be38ec5d`
  `content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets.md:176`, `:178`).
  So it checks the contexts' states, not who posted them; that it weighs nothing of what a status describes is not stated there
  (PROPOSAL). Its local reads are narrowed to seconds in the same way, and the closure path is the same App identity.

**`horizon_land.sh <pr> <read-head-prefix>`** (2026-10-15) lands a pull request of `seathatflowsinourveins/horizon`, a private repository
with no hosted CI, no `scripts/validate.py`, no `manifests/evidence.json` and no Codex connector. Its main carries an active ruleset: a pull
request (squash merges only, no approval, review threads resolved), no deletion or force push, a linear history, and three required commit
statuses, `lander/local-ci`, `lander/verdict-claude` and `lander/verdict-gpt`, strict ("The topic branch **must** be up to date with the base
branch before merging", `available-rules-for-rulesets.md:188-193`, above) and with no app selected as their source (`:178`). The ruleset is the
owner's; the lander does not read it, and these are its settings as the CC records them. The lander is **the required local workflow**, as
#1195's decision record decides (`docs/decisions/2026-10-15-horizon-runtime-ecosystem-repository.md`, Decision 4): it checks the local
evidence, posts those statuses at the exact head and merges pinned to it, while GitHub enforces the three status contexts and freshness, not
the local gates. The residual, plainly: GitHub checks only the three contexts' states, and any account with write access can set one
(`:178`), so a merge made in the web UI after the lander's posts is not refused (Known gaps); finding such a merge is the job of the
PROPOSAL self-audit of that Decision 4. `R` is
fixed (no `LANDING_REPO`), and the merging account is the other landers' (`LG_AUTHOR_LOGIN`). Its inputs are variables, each a file named by
its path, as `nas_land.sh`'s verdict files are named (its arguments): `HORIZON_CLAUDE_VERDICT` and `HORIZON_GPT_VERDICT` (required),
`HORIZON_MUSE_VERDICT` (optional, a TRIAL) and `LOCAL_CI_RECEIPTS` (required, colon-separated, so a path cannot hold `:` or a newline). Only the
file name is published (in the statuses and the trailers) and printed, never the path, and it must be 1 to 60 of `A-Z a-z 0-9 . _ -`; the
files' digests are not published at all ("The statuses", below). In order:

1. before any call (exit 2): the two arguments (the pull request a number, the read head prefix 7 to 40 lower-case hex digits), the inputs,
   and the inputs of the other two landers refused when set, an empty value included (`uet_land.sh`'s `${VAR+x}` form, "A nas input in a uet
   landing", above): `SQUASH_BODY_FILE`, `LOCAL_REVIEW_ADJUDICATION`, `LOCAL_REVIEW_WAIVER`, `LOCAL_REVIEWS`, `CODEX_LOCAL_REVIEW`,
   `GPT_VERDICT` and `VERDICT_FILES`, each named in one line as the input of the lander it belongs to;
2. the landing lock, its own `horizon.lock` (exit 14, nothing run; "The landing lock", above), the fetch and the read head (exit 3);
3. the pull request's head must be the read head: there is no head-following, and any move stops with exit 3; and its base, read with the
   head, must be main (exit 13, the base's name not printed; #1194's GPT read, P2): CODEOWNERS and the ancestry are read at main, a pull
   request uses "the version of `CODEOWNERS` from the base branch of the pull request" (`about-code-owners.md:44`, "CODEOWNERS", below), and the
   merge pins the head alone (gh builds `MergePullRequestInput` from the pull request's id and sets `expectedHeadOid`, with no base:
   `cli/cli@v2.102.0` `pkg/cmd/pr/merge/http.go:47-50`, `:77-80`), so a pull request retargeted to another branch is refused, here and at the
   final gate;
4. strict, and never `update-branch`: `origin/main`, read with `git ls-remote`, must be an ancestor of the head (`git merge-base
   --is-ancestor`) and GitHub must report neither BEHIND nor DIRTY, otherwise exit 13 and "rebase onto main, rerun the local CI at the new
   head, and get both verdicts for it" (an unreadable main is exit 13 too). The branch is never updated here (no `gh pr update-branch`): an
   update is a new head that no receipt and no verdict names;
5. the verdicts (and `GATES_DONE` when one states a landing gate), the receipts and main's CODEOWNERS (below), local reads and GitHub's
   CODEOWNERS errors, and the place of the landing receipt (below; exit 7);
6. a draft marked ready (exit 7 when it cannot be). This comes after the local refusals and not before them, where the design pass of
   2026-10-15 had it: a refused landing then changes nothing on GitHub, the order of cheap reads before slow steps ("One final gate after every
   slow step", above), and no Codex review waits on a ready event here;
7. the three statuses posted (below; exit 15 when a POST fails), the EXIT trap set right before the first;
8. the merge state polled until CLEAN (below), the squash body and its trailers (below), the no-reply author address (exit 11), the final
   gate (below), the squash merge pinned with `--match-head-commit` (a failed call reconciled first: below; exit 7 or 17), the merge commit read (exit 12; nothing of the reply printed but
   its typed id), the landing receipt written (exit 16) and the author check (exit 12).

**The statuses (`horizon_land.sh`).** Each is posted at the head as `gh api repos/<owner>/<name>/statuses/<head> --method POST -f
state=success -f context=<context> -f description=<description>`, its output dropped (nothing `gh` or its API returned is printed, #975 P2-2).
Each description is a NAME: a verdict's is its file name, and `lander/local-ci`'s the receipt files' names in their order, one space apart
(a name holds no space). No digest is published, in a status or in a trailer (#1194's GPT read, P1): the verdicts, `GATES_DONE` and the
receipts are private files, one can hold a home path, and a digest of private bytes is an offline oracle for them (correction #161; at
34add438 the descriptions were `<file name> sha256 <its sha256>` and `receipts sha256 <x>`). A digest is published only beside its complete
preimage, which none of these is, so their sha256 stay local: the final gate compares them, and the landing receipt keeps them (below).
The REST description gives a commit status's description no maximum ("A short description of the status.", `github/rest-api-description@58b1e0c0`
`api.github.com.json:79201-79205`, and the docs' REST data at `be38ec5d` say the same, `commits.json:10906`); the one maximum the docs state,
140 characters, is a deployment status's (`deployments.json:6234`). The lander borrows it as its own ceiling and refuses a longer description
before any POST (exit 2): a verdict's name has 60 characters at most, and two receipt names of 60 fit, three do not. The live limit is not
measured (no POST was made here), and a server that cut a description short would fail the final gate's exact read (exit 5). A context is
case-insensitive ("This field is case-insensitive", `:79208`), so the lander compares contexts in lower case.

The EXIT trap is set right before the first POST: unless the merge succeeded, it posts `state=failure` for each of the three contexts, so no
success the lander posted outlives a landing that stopped, whatever stopped it. bash runs the trap on every exit ("Any trap on EXIT is
executed before the shell terminates", the installed `bash(1)`, `exit`), keeping the exit status (measured), and HUP, INT and TERM are trapped
to exit 129, 130 and 143, so a signal revokes too, once the command bash waits for completes ("it will not execute the trap until the
command completes", `bash(1)`, SIGNALS; measured: a SIGTERM during the author lookup exits 143 and posts the three failures). A `$(...)`
subshell does not run it (measured). The revocation's first statement is `trap '' HUP INT TERM` (#1194's CC read, P3; "If *action* is the
null string the signal specified by each *sigspec* is ignored by the shell and by the commands it invokes", the installed `bash(1)`, SHELL
BUILTIN COMMANDS, `trap`): a second signal during it would otherwise run its `exit` trap after the POST it waits for and cut the POSTs still
to come (measured: with it, a TERM sent during the first revocation POST leaves all three posted and the exit code the stop's; a copy of
the script without the line failed that test). The merge is finalised whole (#1194's delta reads: the CC's P3-3 and the local review's P2): from right before
the merge call, after the final gate, until the landing receipt is written and the merge reported, HUP, INT and TERM are ignored the same
way, so a merge that completed always records its success (`HZ_MERGED`) and writes its receipt; before, a signal pending as the merge call
finished exited before that record and revoked a merged head's statuses, and one during the sleep after the merge exited with no receipt
(both measured at b4489b15, exit 143). The exit traps are then set again, for the author check. So exit 12 and 16, and 129, 130 or 143
during the author check, leave a merged head's statuses alone. A revocation that fails says which context to
revoke by hand. A landing posts one status for each context and a stopped one a second; GitHub allows 1000 for a head and a context
(`api.github.com.json:79153`).

**The landing receipt (`horizon_land.sh`; #1194's GPT read, P1).** The digests the statuses and the trailers no longer publish are kept in
one LOCAL file, `$LANDING_COORD/horizon-landings/<pr>-<the head's first 12 digits>.json`, written once after the merge, mode 0400, never
printed (the messages name the file, never its path) and never published. It holds the repository, the pull request, the head, the base
(`main`) and main's commit, the merge commit (`null` when it could not be read), the time, the three descriptions posted, each file's name
and sha256 (the Claude, GPT and Muse verdicts, the Muse word, `GATES_DONE`, each CI receipt), the receipts' combined sha256 (that of the
lines `<sha256>  <file name>` of the files in their order, sha256sum's form) and CODEOWNERS' path and sha256. The PROPOSAL self-audit
(#1195's Decision 4) would bind main's trailers, which hold the names and the head, to it. Its place is checked with the other local reads,
before `ready` and the posts: the directory made (mode 0700) and writable, and no receipt there yet for this pull request and head,
otherwise exit 7 and nothing posted. The file is written under bash's noclobber (`set -C`): "the redirection fails if the file whose name
results from the expansion of *word* exists and is a regular file" (the installed `bash(1)`, REDIRECTION, Redirecting Output), which is all
the manual says of it. Measured with bash 5.3.9: a second write to that regular file was refused, and so was a write through a dangling
symlink; the mode was 0400 under `umask 0277`. A write that fails after the merge is exit 16 (merged, the statuses kept). The landing that
stops before its merge writes none.

**The CI receipts (`LOCAL_CI_RECEIPTS`).** Each file is read once, as `nas_land.sh` reads a record (`nas_read`; a NUL byte refused, exit 2, as
a missing or unreadable file), and only its lines `CI: exit <code> at <40 hex digits>: <command>` count, a trailing CR dropped; a line for
another head counts for nothing. For each command the last line counts, across the files in their order. The required command is `sh
tests/hooks_test.sh`, fixed in the script: it must have a line at the head, and every command that has one must end at `exit 0` (`00` is not
0), otherwise exit 5. The commands are never printed (one can hold a path), only counts. The receipts are claims: the lander runs nothing
(Known gaps).

**The verdicts and their families.** `HORIZON_CLAUDE_VERDICT` and `HORIZON_GPT_VERDICT` each name one family's verdict, read once (a NUL byte,
a missing or an unreadable file: exit 2), and the digest the lander keeps (locally: the final gate, the landing receipt) is that of the bytes
it judged in that read. Each must be accepted as `nas_land.sh` accepts a verdict file (correction #136, `lg_verdict_text_ok`:
CHANGES_REQUESTED on line 1 or as the last Gate line/Verdict line naming the head refuses) and, stricter, that last line must name the full
head as a whole word, as `Verdict: PASS at <40 hex digits>` (or ACK, or a `Gate line:`), the head followed by the end of the line or by a
character that is no letter, digit or `_` (#1194's GPT read, P3: at 34add438 only a lower-case hex digit was excluded, so the head and an
`A` passed): an 8-digit prefix alone, which `nas_land.sh` accepts, is refused here, as is line 1's Astra layout alone. The last line that
starts with `Family:` must read exactly `Family: claude` or `Family: gpt`, and the two files must differ in their sha256 (one file in both
slots is one read, not two). `HORIZON_MUSE_VERDICT` is a TRIAL: when it is set, its file must be there, readable and of `Family: muse`
(exit 2 otherwise; a set but empty value names no file), and its word, that of its last Gate line/Verdict line for the full head (`none`
without one), is recorded in the squash body and never decides. Muse has no status.

**A stated landing gate (correction #121; the CC's ruling of 2026-10-15).** As in `nas_land.sh` (`verdict_gate`, `nas_land.sh:452`,
`:461-466`), a verdict whose text states a landing gate, one of the phrases `landing gate`, `path to pass`, `before landing` or `landing
condition` in any letter case, needs `GATES_DONE`, a receipt written once the gate was run. Here the receipt must name the FULL head: the
shared block's `lg_receipt_ok` decides, given the 40 digits (the receipt's text must hold them), so one that names the 8-digit prefix alone,
which `nas_land.sh` takes, is refused. A verdict of any of the three families counts, Muse's TRIAL one included (fail closed). Without a
receipt, or with one that does not name the full head, is missing or unreadable, holds a NUL byte or has a file name of another form, the
landing stops with exit 2 before anything changes on GitHub (before `ready` and the posts). The receipt is then read once more (a NUL byte
stops), and those bytes must name the full head as a whole word too (the verdicts' rule, above, so `<head>A` is refused); their sha256 stays
local, compared at the final gate, where the whole check runs again (exit 7 when the bytes changed, 2 when the receipt no longer passes),
and kept in the landing receipt, while `Lander-gates-done` names the file alone. Without a stated gate `GATES_DONE` is not read, as in
`nas_land.sh`.

**CODEOWNERS (`horizon_land.sh`).** GitHub takes the file from `.github/`, the top level or `docs/`, "in that order", the first it finds, and a
pull request uses "the version of `CODEOWNERS` from the base branch" (`github/docs@be38ec5d`
`content/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners.md:36`, `:44`), so the
lander reads it at the main that `git ls-remote` gave, never at the head, and requires the pull request's base to be main, before the posts
and at the final gate (step 3, above): a pull request's own edit of it counts for nothing, and one retargeted to a branch of another
CODEOWNERS is refused (13). v1 accepts only
a file each of whose rules is owned by the merging account alone (`@<LG_AUTHOR_LOGIN>`, in any letter case; the repository is an account's,
with no teams): a comment line starts with `#` and an inline comment with a word that does (`:99`), and a rule with another owner, a team, an
address or no owner (`:140-146`), a file with no rule, none in the three places, one that is not a regular file, holds a NUL byte or has 3 MB
or more ("will not be loaded", `:52`) stops with exit 8, the line named by its number, never its text. GitHub skips a line it cannot parse
(`:79`), so the lander also asks for GitHub's CODEOWNERS errors at that main, `GET /repos/{owner}/{repo}/codeowners/errors?ref=<main>`
(`github/rest-api-description@58b1e0c0` `api.github.com.json:53272-53329`; the reply's `errors` list, `:147909-147969`, is required,
`:147966-147968`): their count must be 0, or exit 8, as when the reply cannot be read; nothing of an error is printed. The endpoint is used as
the description documents it; it was not called live here.

**The lander's trailers (the squash body).** The body is the one GitHub offers the merging account (`viewerMergeBodyText(mergeType: SQUASH)`,
read as `nas_land.sh` reads it, "The squash body", above; exit 7 when the read fails), a blank line, and one paragraph of git trailers, last:

```
Lander-head: <the head>
Lander-local-ci: <receipt file name> [<receipt file name> ...]      (in their order, one space apart)
Lander-verdict-claude: <file name>
Lander-verdict-gpt: <file name>
Lander-verdict-muse: TRIAL <word> <file name>                       (only when HORIZON_MUSE_VERDICT is set)
Lander-gates-done: <file name>                                      (only when a verdict states a landing gate)
Lander-codeowners: <path> sha256 <sha256 of main's CODEOWNERS> satisfied
```

Names only, and the head (#1194's GPT read, P1): no private file's digest. CODEOWNERS keeps its sha256, its preimage being main's own file,
published where the trailer is. Each `Lander-<context>` line holds the description posted for `lander/<context>`, so the PROPOSAL
self-audit (#1195's Decision 4) would compare the trailers with the statuses at `Lander-head`, and bind the names to their digests in the
landing receipt (above), which is local. At
34add438 these lines carried each file's sha256 and one `Lander-local-ci-receipt` line for each receipt. The merge takes the body as
`--body`, as `nas_land.sh` does (`--body-file` would be read again when the merge call starts,
`merge.go:146-153`). Read the trailers with `git log -1 --format='%(trailers)' <merge>` or `git interpret-trailers --parse --no-divider`: a
`---` line in the offered body ends the message for a plain `--parse` (`--no-divider`: "Do not treat `---` as the end of the commit
message", `git/git@v2.53.0` `Documentation/git-interpret-trailers.adoc:181-184`; measured with git 2.53.0: a plain `--parse` printed none of
them, the other two all). The paragraph is all trailers after a blank line (`:88-92`).

**Its final gate.** Right before the merge, fast reads only, in this order: the head and the base, in one read (the read head, exit 3, and
main, exit 13); the verdicts, `GATES_DONE` and the receipts (their acceptance, exit 2 and 5, then each sha256 equal to the one kept when the
statuses were posted, exit 7); the combined status at the head, read as `tcc_read_gate` reads it (every page, `gh`'s exit code kept apart):
each of the three contexts listed once, success, with exactly the description the lander posted, and no other `lander/` context (exit 5,
and nothing of the reply printed); main's CODEOWNERS (exit 8); `origin/main` by `git ls-remote`, which must be the main read at the start
and an ancestor of the head (exit 13); the merge state, which must be CLEAN (BLOCKED exit 8, BEHIND or DIRTY exit 13, any other exit 6).
The states are those of GraphQL's `MergeStateStatus` (`github/docs@be38ec5d` `src/graphql/data/fpt/schema.docs.graphql:26511-26554`, the
bytes of the schema cited above, sha256 `3ed09565…`): BEHIND "The head ref is out of date." (`:26513-26515`), BLOCKED "The merge is
blocked." (`:26518-26520`), CLEAN "Mergeable and passing commit status." (`:26523-26525`), DIRTY "The merge commit cannot be cleanly
created." (`:26528-26530`), UNKNOWN "The state cannot currently be determined." (`:26546-26548`) and UNSTABLE "Mergeable with non-passing
commit status." (`:26551-26553`), which GitHub would merge and the lander refuses (6, fail closed). Before it, after the POSTs, the merge
state is polled for up to two minutes (12 reads, 10 s apart) until CLEAN. The two-minute poll rests on a lag measured on
us-equities-trading #58, not documented by GitHub (there an update-branch's head reached the API views 6 s apart, `nas_land.sh:242-245`);
how long GitHub takes to recompute the merge state after the statuses is neither measured here nor documented. So a BLOCKED or UNKNOWN right
after the posts is read again, while BEHIND or DIRTY stops at once (13); a block that lasts is exit 8, with the
count of unresolved review threads (the query as `nas_land.sh` builds it, owner and name from `R`), and any other state exit 6.

## Variables

| Variable | Default | Used by | Meaning |
| --- | --- | --- | --- |
| `LANDING_UET_REPO` | `$HOME/code/us-equities-trading` | `uet_land.sh` | clone of the trading repository: fetches, `rev-parse`, change identity (the path must not contain whitespace) |
| `LANDING_NAS_REPO` | `$HOME/code/native-agent-stack` | `nas_land.sh` | clone of this repository, used the same way (no whitespace) |
| `LANDING_HORIZON_REPO` | `$HOME/code/horizon` | `horizon_land.sh` | clone of the horizon repository: fetches, `rev-parse`, `ls-remote`, the ancestry check and main's CODEOWNERS (no whitespace) |
| `LANDING_REPO` | `native-agent-stack/native-agent-stack` | `nas_land.sh` | the repository's `owner/name` on GitHub, of that shape or exit 2 (2026-10-13; "The repository", above) |
| `LG_AUTHOR_LOGIN` | `seathatflowsinourveins` | all three | the merging account, whose no-reply address authors the squash merge (CC correction #198); `horizon_land.sh`'s CODEOWNERS must name it alone |
| `HORIZON_CLAUDE_VERDICT` | none | `horizon_land.sh` | required: the Claude family's verdict file, whose last `Family:` line reads `Family: claude` and whose last Gate line/Verdict line gives PASS or ACK at the full head ("The verdicts and their families", above) |
| `HORIZON_GPT_VERDICT` | none | `horizon_land.sh` | required: the GPT family's, the same with `Family: gpt`; its bytes must differ from the Claude file's |
| `HORIZON_MUSE_VERDICT` | none | `horizon_land.sh` | optional, a TRIAL: when set, a readable file of `Family: muse`, whose word the squash body records (`Lander-verdict-muse`) and which never decides; a set but empty value stops (exit 2) |
| `LOCAL_CI_RECEIPTS` | none | `horizon_land.sh` | required: colon-separated receipt files of `CI: exit <code> at <head>: <command>` lines; `sh tests/hooks_test.sh` must have one at the head and every command's last one must be `exit 0` ("The CI receipts", above) |
| `LOCAL_REVIEWS` | none | `uet_land.sh` and `nas_land.sh`, through `codex_gate.py`; refused by `horizon_land.sh` | colon-separated normalized review files; when set (an empty value included), the Codex gate decides from them alone ("Local reviews"); `nas_land.sh` requires it or the waiver |
| `CODEX_LOCAL_REVIEW` | none | `uet_land.sh` and `nas_land.sh`, through `codex_gate.py`; refused by `horizon_land.sh` | an alias of `LOCAL_REVIEWS`: its files are added to the set |
| `LOCAL_REVIEW_WAIVER` | none | `nas_land.sh`; refused by `horizon_land.sh` | with neither variable above set, a waiver file whose last `Waiver:` line reads `Waiver: local reviews for #<pr> at <head8>` (the read head); the landing then asks the connector, and its squash body records the waiver (#1061 round 2) |
| `LOCAL_REVIEW_ADJUDICATION` | none | `nas_land.sh`, through `codex_gate.py`; refused by `uet_land.sh` and `horizon_land.sh` | with a local review set, the CC's adjudication record: it decides a `codex-review` that says `patch is incorrect` with only P2 and P3 findings, at least one, its last `Adjudication:` line bound to that file's sha256, the pull request and the read head, each finding listed after it with its disposition ("Local reviews"); set where no review says `patch is incorrect`, the gate gives 4; the squash body records it (the CC's ruling of 2026-10-13); in `nas_land.sh` an empty value is none with a local review set, and with none set (the waiver path) it stops with exit 2 before any call, an empty value included; `uet_land.sh` and `horizon_land.sh` stop with exit 2 before any call when it is set, an empty value included ("A nas input in a uet landing", above) |
| `LG_ADJUDICATION_SHA256` | unset when `nas_land.sh` starts | `nas_land.sh`, for `codex_gate.py` | not an input: `nas_land.sh` sets it to the review file's sha256 that the record named at its first read, and the gate then adjudicates only the file whose bytes have it (#1075; "Local reviews") |
| `SQUASH_BODY_FILE` | none | `nas_land.sh`; refused by `uet_land.sh` and `horizon_land.sh` | the squash commit's body; when set, a readable, non-empty regular file other than `-` whose content is UTF-8 text of at most 64 KiB without a NUL byte, or exit 2 before any call; read again when the body is built and at the final gate (exit 7); passed as `--body`, alone or before a waiver's or an adjudication's line ("The squash body"); `uet_land.sh` and `horizon_land.sh` stop with exit 2 before any call when it is set, an empty value included |
| `LANDING_COORD` | `${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/coordination` | all three | coordination tree; a status description `PASS: trading-cc/reads/<record>.md` names `$LANDING_COORD/trading-cc/reads/<record>.md`; `horizon_land.sh` keeps its landing receipts, local and 0400, in `$LANDING_COORD/horizon-landings/<pr>-<head12>.json` ("The landing receipt", above) |
| `LANDING_GATE` | `codex_gate.py` in the directory of the script, symlinks resolved (`readlink -f "$0"`) | `uet_land.sh` and `nas_land.sh` | the Codex gate; it works through a symlink or a wrapper that `exec`s the real path, and not when the script is read from a pipe or a process substitution (set this variable then) |
| `LANDING_LOCK_DIR` | `$LANDING_COORD/command-center/landing-locks` | all three | where the landing lock of each repository is kept (`us-equities-trading.lock`, `native-agent-stack.lock`, `horizon.lock`); created when missing, and outside every worktree |
| `VERDICT_FILES` | none | `uet_land.sh`; refused by `horizon_land.sh` | space-separated verdict files that each must name the read head |
| `GATES_DONE` | none | all three | receipt naming the read head; required when a verdict file states a landing gate (correction #121); `horizon_land.sh` requires it to name the full head as a whole word, reads it again at the final gate (exit 7 when its bytes changed), names it in `Lander-gates-done` and keeps its sha256 in the landing receipt |
| `GPT_VERDICT` | none | `uet_land.sh`; refused by `horizon_land.sh` | the co-op's verdict file accepted instead of Codex when `codex_gate.py` exits 5 |
| `TMPDIR` | `/tmp` | all three | where a failed merge keeps gh's output (`merge-fail-XXXXXX`, mode 0600), and `nas_land.sh` the validation's output (`nas-validate-XXXXXX`, kept when it fails) |
| `LANDING_PROHIBITED_NAMES` | none | the tests only | comma-separated identities that must not appear in any form under `tools/landing` (see Tests) |

The scripts also need `gh` 2.48.0 or later (`gh api --paginate --slurp`; authenticated for the repository), `git` 2.39.0 or
later (`git patch-id --verbatim`), `jq`, `python3` 3.7 or later, GNU `grep`, `sha256sum`, `readlink -f` and util-linux `flock` (the
landing lock; without it every landing stops with exit 14). They run under `set -u`, so `HOME` must be set whenever a default above is
used.
`nas_land.sh` also needs a git committer identity: its validation merge (`git merge --no-commit`) refuses to start without
one, and the script then reports exit 10, "does not merge cleanly". `horizon_land.sh` needs neither `python3` (it runs no gate and no
validation) nor a committer identity, and bash 4.1 or later (an associative array and `{fd}` redirections; bash 5.3 here).

## Exit codes

From the script headers. `uet_land.sh`: 2 verdict gate (a verdict file, `GATES_DONE` or `trading-cc-read`, also when a file, record or
status cannot be read; and, before any call, `LOCAL_REVIEW_ADJUDICATION` or `SQUASH_BODY_FILE` set, an empty value included, since both
are `nas_land.sh`'s alone; #1075), 3 head moved, 4 change differs, 5 CI failed (at the final gate also: no longer complete and green), 6 timeout,
7 merge failed, 8 blocked, 9 the Codex gate gave neither 0 nor 5: a review running or not finished since its latest trigger (its 3, after
the 20-minute wait or at the final gate), a review that ended other than Completed or a summary last edited by another account (its
4), a gate that failed or is missing; or a 5 without an accepted `GPT_VERDICT` (#975 P3-7 at 761810d7: the header named only some of
these). `nas_land.sh`: 2 as above, and a `LANDING_REPO` that is not of the owner/name shape (before any call; #1061 P3), neither local
review variable nor `LOCAL_REVIEW_WAIVER` set (before any call), `LOCAL_REVIEW_ADJUDICATION` set, an empty value included, with neither
local review variable set (before any call; #1075 P3-4), a `SQUASH_BODY_FILE` that is not a readable, non-empty regular file other than
`-`, an empty value included, or whose content holds a NUL byte, is not UTF-8, is longer than 64 KiB or holds no text (before any call;
"The squash body"), a waiver that is missing, unreadable or does not name the pull request at the read head (after the lock, before
`update-branch` and `ready`, when the squash body is built and again at the final gate; #1061 round 2), and, with a local review set, a
`LOCAL_REVIEW_ADJUDICATION` that is missing, unreadable or holds a NUL byte, does not name the pull request at the read head and the
sha256 of a listed review file, or after its first read names another file (read as the waiver is; the CC's ruling of 2026-10-13), 3 head
moved, 4 `update-branch` refused or the change differs after it or at the final gate, 5 CI
failing (also at the final gate), 6 timeout, 7 merge failed, or the squash body of a waived or an adjudicated landing could not be read
(the body GitHub offers), or `SQUASH_BODY_FILE`'s content, read when the squash body is built and again at the final gate, cannot be read,
holds a NUL byte, is not UTF-8, is longer than 64 KiB or holds no text, or changed after the body was built (nothing merged), 8
blocked by policy, 9 as above (an adjudication that the gate does not accept is its 4), but a 5 proceeds (it is reachable only under a
waiver), and a 3 before the validation stops too, 10 the merge onto current `origin/main` fails `scripts/validate.py` or does not merge cleanly, 13 origin/main moved
after each of three validations, moved after the last validation (read at the final gate) or could not be read, so nothing is merged
(#975, new in round 3). The three scripts also exit 11 when the no-reply author address cannot be formed (nothing is merged), 12 when the
merge landed but its commit's author is not that address or the commit could not be read (CC correction #148), and 14 when another
landing of the same repository holds the landing lock or the lock cannot be opened or taken (nothing has run; #975 round 4).
`horizon_land.sh` (2026-10-15; nothing is merged on any code but 0, 12 and 16, and 129, 130 or 143 when the signal came during the author
check after the merge): 2 an argument or an input, before any call (the usage, a pull
request that is not a number, a read head prefix that is not 7 to 40 lower-case hex digits, `HORIZON_CLAUDE_VERDICT`, `HORIZON_GPT_VERDICT`
or `LOCAL_CI_RECEIPTS` unset or empty, `HORIZON_MUSE_VERDICT` set but empty, a file name of another form, a newline or an empty name in
`LOCAL_CI_RECEIPTS`, a leading, trailing or doubled `:` in it, any input of `nas_land.sh` or `uet_land.sh` set, an empty value included),
and after the lock a verdict or a receipt
missing, unreadable or holding a NUL byte, the same bytes in both verdict slots, a verdict of another family, one that `nas_land.sh`'s
acceptance refuses or whose last Gate line/Verdict line does not name the full head, as a whole word, with PASS or ACK, a verdict that states
a landing gate without a `GATES_DONE` naming the full head as a whole word (a receipt missing, unreadable, holding a NUL byte or of another
file name form included; correction #121), each also at the final gate, or a status description over 140 characters; 3 the read head not
resolvable, or not the pull request's head (also at the final gate); 5 the receipts
(the required command with no line at the head, or a command whose last line there is not `exit 0`, also at the final gate) or, at the final
gate, the statuses (unreadable, a context missing, of another state or description or listed twice, or another `lander/` context); 6 the
merge state not settled, neither CLEAN, BLOCKED, BEHIND nor DIRTY after the two-minute poll or at the final gate; 7 ready, the squash body
or the merge failed, the landing receipt's place not writable or taken (before any post), or a verdict, a receipt or `GATES_DONE` changed
after the statuses were posted (the Muse verdict after the body recorded it); 8 BLOCKED
(after the poll or at the final gate) or main's CODEOWNERS (none in the three places, not a regular file, a NUL byte, 3 MB or more, no rule,
a rule with another owner, a team, an address or none, a lookup or a read of it that fails, GitHub's errors not 0 or unreadable, or read
otherwise at the final gate); 12 merged, but the merge commit could not be read (the landing receipt then records none) or its author is not
the no-reply address; 13 not up to date
(origin/main not an ancestor of the head, or GitHub BEHIND or DIRTY), origin/main unreadable, or moved (final gate), or a base other than
main (before any post and at the final gate; #1194's GPT read, P2); 15 a status POST failed; 16 merged, but the landing receipt could not be
written (its place was free and writable before the posts; the statuses are kept), and when 12 applies too, 12 is the exit (the receipt's
line is printed either way; #1194's delta reads); 17 the merge call failed and the pull request's state could not be read as merged or
unmerged at the read head on three reads two seconds apart: the statuses are kept, nothing is revoked, and the pull request is checked by
hand (a failed call whose pull request reads MERGED at the head continues as a landing; one that reads OPEN or CLOSED there on all three
reads is 7; #1194's local review at 4fad2736, P2); 129 a hangup, 130 an interrupt and 143 a termination signal (128 and the signal's number):
before the merge call nothing is merged and the statuses posted are revoked, from the merge call until the receipt is written and the merge
reported the three are ignored, and during the author check after that the pull request is merged and its receipt and statuses are kept;
11 and 14 as above. Every code after the first POST, but 0, 12, 16, 17 and a signal during the author check, revokes the three statuses (the
EXIT trap, "The statuses", above).
`codex_gate.py`: 0, 3, 4 and 5 as above; a gate that fails itself exits 4, which both scripts stop on with 9. With a local review set
("Local reviews"): 0 (every file a review of the read head or of a head with its change, every `codex-review` completed with `patch is
correct` and no P0 or P1 finding, or one that says `patch is incorrect` with only P2 and P3 findings, at least one, and that the CC's
adjudication decides), 2 (no file named; a file unreadable, malformed or of another head; a `codex-review` against another base than its
head's merge base with `origin/main`, not completed or with another verdict; or no completed `codex-review`) and 4 (a P0 or P1 finding of a
`codex-review`, `patch is incorrect` that no adjudication decides (one with no finding never is), or an adjudication set where no
`codex-review` says `patch is incorrect`); the advisory plugin arm never stops it; both scripts stop with 9 on its 2 and its 4.
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
on its 5). Unset, the gate reads the connector as before: `uet_land.sh` (`us-equities-trading`) uses that path, and `nas_land.sh` takes
it only under a waiver (below). A file name cannot hold `:` or a newline.

**Required on `nas_land.sh` (#1061 round 2, the CC's ruling on its Claude delta at 974090cf).** With `LOCAL_REVIEWS` and
`CODEX_LOCAL_REVIEW` both unset, nas asked the connector, which cannot reach the organization's repository, and merged on its 5
("unavailable") with no Codex verdict (P1-1: no connector activity in 10 minutes, a usage notice, a stale Running row, or the 👀 that
974090cf bounded). In local mode the gate gives only 0, 2 or 4, so a landing passes only on a completed `codex-review` of the head at its
merge base with no P0 or P1 finding (and, when it says `patch is incorrect`, the CC's adjudication; below). So `nas_land.sh` stops with exit 2 before any call (before the lock, `update-branch` and `ready`)
when neither variable is set, unless `LOCAL_REVIEW_WAIVER` names a waiver file. The file is read once at each check (`lg_text`), in
`verdict_gate` after the verdict files and again at the final gate, and its last line that starts with `Waiver:` must read exactly:

```
Waiver: local reviews for #<pr> at <the read head's first 8 hex digits>
```

So it is bound to the pull request and the head, as `uet_land.sh` binds `GPT_VERDICT`; a waiver for another pull request or head, a
revoked one (a later `Waiver:` line), a missing or an unreadable one stops with exit 2, and an empty value is no waiver. A waived landing
asks the connector as before (a 5 proceeds; a 👀 with no Running row waits, exit 9 after 20 minutes), and its squash merge records the
waiver: its body is the body GitHub offers the merging account for the squash (`viewerMergeBodyText(mergeType: SQUASH)`, here the pull
request's commit messages, read once before the author lookup; exit 7 when the read fails), then a blank line and `Waiver: local reviews
for #<pr> at <head8> (LOCAL_REVIEW_WAIVER)`. That is how gh's own "edit the commit message" step starts (cli v2.102.0
`pkg/cmd/pr/merge/merge.go:721-735`, `http.go:121-158`), and `--body` sets the body in place of the default (`merge.go:146-147`, `:176`;
`http.go:72-75`). With either variable set the waiver is not read, and the merge names a body only for an adjudication (below) or
`SQUASH_BODY_FILE` ("The squash body", above). `uet_land.sh` keeps the connector path and refuses the adjudication and `SQUASH_BODY_FILE`
("A nas input in a uet landing", above); the requirement and the waiver are in neither the shared block nor `codex_gate.py`, which uet
uses too.

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
`codex-review` has a finding of priority 0 or 1, or says `patch is incorrect`, whatever its findings' priorities, and the CC's
adjudication does not decide it ("a person decides": the CC adjudicates, below); otherwise 0. The P2 and P3 findings are printed as
counts, for the pull request's Follow-ups. The plugin's arm never stops the gate: its issues are printed as a count, each scored 80 or more
by the plugin's filter (its comment carries no score), and a run without a comment (`completed` false) is counted with the citation above,
both marked advisory. The pure-rebase check is the scripts' own: `lg_gate` runs `lg_same_change` (the change
identity above) on each file's `head_sha` that is not the read head, fetching a commit the clone lacks (`lg_have`, at the first call), and
passes the heads that carry the read head's change to the gate after the read head; the gate accepts those and no other. Its lines start
with `Local reviews: `, which `lg_gate` echoes for a 2 as well (python3's own exit 2 keeps its fixed line), and name a file by its place
in the list, never by its path, and no finding's text. Both scripts stop with exit 9 on a 2 or a 4, and read the files at every gate call,
so they must stay in place for the whole landing.

**The CC's adjudication (`LOCAL_REVIEW_ADJUDICATION`; the CC's ruling of 2026-10-13).** After a pull request's bounded rounds, a local
re-review that says `patch is incorrect` with only P2 and P3 findings is decided by the CC, not looped; a P0 or P1 still blocks. Until this
input the gate gave 4 for `patch is incorrect` whatever the priorities (`codex_gate.py:52` and `:327-329` at 993cc890), and no input
carried the CC's decision, so such a review could block a landing for good. `LOCAL_REVIEW_ADJUDICATION=<file>` names the CC's record (an
empty value names none):

```
Adjudication: local review <sha256 of the normalized review file> for #<pr> at <the read head's first 8 hex digits>
Finding: P<priority> at <location>: <title> (fixed|follow-ups|rejected)
```

with, after that line, one `Finding:` line for each finding of that review (an identical finding twice needs two lines), its priority,
location and title as the file holds them, and one disposition: `fixed` (fixed in this landing), `follow-ups` (the pull request's
Follow-ups) or `rejected` (with its evidence in the record, which the CC reviews: the gate checks no evidence text; Astra's P3 at ca6f880b,
Known gaps). Only lines that start with `Adjudication:` or `Finding:` count, and of the `Finding:` lines only those after the last
`Adjudication:` line, the section it opens; a line may end in CR, and the rest of the record is free. The gate (`codex_gate.py:412-435`;
the record is read and matched by `adjudication`, `:281-337`) turns the 4 into 0 only when all of these hold:

- no `codex-review` has a P0 or P1 finding, and exactly one says `patch is incorrect` and has at least one finding: one with no finding has
  nothing to dispose of, so a person decides (the CC's ruling on the Claude read's P3-5 at ca6f880b);
- the record holds no NUL byte (`lg_text` would drop it in `nas_land.sh`, and the two would read different lines: P3-1);
- its last `Adjudication:` line names that file's sha256 (of the bytes the gate parsed, `:360-362`, `:391-395`; "The sha256 forms",
  below), the pull request and the read head, and that sha256 is the one `nas_land.sh` recorded at the record's first read, when it set
  `LG_ADJUDICATION_SHA256` (#1075, the co-op's codex review and Astra's P2-2: both files replaced between `nas_land.sh`'s final read and the
  gate's could pass on review B while the squash body recorded review A);
- the `Finding:` lines after it are that review's findings, one line each: the gate renders each finding's three possible lines and
  compares whole lines, so nothing of the free text is parsed, and two findings that would render alike (a location that holds `: `) stop
  it; a stale section's lines do not count (P3-2), and an identical finding counts once for each time the review holds it (P3-3).

Anything else stays 4 and says why in fixed words, never the record's text or path: a P0 or P1, two reviews that say `patch is incorrect`,
a review with no finding, a record that cannot be read, holds a NUL byte or has no `Adjudication:` line, another file, pull request or
head, another file than `nas_land.sh` recorded, a later `Adjudication:` line (it revokes), a finding unlisted, a line that names no finding
or another disposition, a finding named more often than the review holds it (so two dispositions for one finding too). A record set where
no `codex-review` says `patch is incorrect` decides nothing and gives 4 too, so a landing that carries one passes only where it decided, and
no squash body records a record that no gate checked. The gate reads the record once per call, and only for an incorrect review with a
finding; the dispositions it prints are counted a line each.

`nas_land.sh` reads it as it reads the waiver (`verdict_gate` and `adjudication_check`, `nas_land.sh:415-450`): once at each check
(`nas_read`, `:392-404`, which also tells a NUL byte: exit 2), after the lock and before `update-branch` and `ready`, when the squash body is
built, and again at the final gate. Its last `Adjudication:` line must read exactly as above for the pull request and the read head, with
the sha256 of a file that `LOCAL_REVIEWS` or `CODEX_LOCAL_REVIEW` names (each hashed once), and after the first read the sha256 that read
named, which it gives the gate as `LG_ADJUDICATION_SHA256` (unset at the start, `:114-118`, so never the caller's); otherwise exit 2, the
record named by its file name only. The squash body then records it as it records a waiver: the body GitHub offers, a blank line and
`Adjudication: local review <sha256> for #<pr> at <head8> (LOCAL_REVIEW_ADJUDICATION)` ("The squash body", above). With no local review set
(the waiver path), a set `LOCAL_REVIEW_ADJUDICATION`, an empty value included, stops with exit 2 before any call (`:77-80`; the Claude read's
P3-4: nothing would read it). The record of one review is written from its normalized file, each disposition then set by the CC (the
commands below).

**The sha256 forms (#1075, the Claude read's P2-1).** The binding compares one digest in three places, so each is 64 lowercase hex digits,
and `nas_land.sh` refuses any other form in the record. The gate's is `hashlib.sha256(raw).hexdigest()`; Python's docs say only that it
contains "only hexadecimal digits" (`python/cpython@v3.13.16` `Doc/library/hashlib.rst:217-220`), and the case comes from the code:
`Modules/_hashopenssl.c:652` returns `_Py_strhex`, which (`Python/pystrhex.c:145-148`) writes each byte as two of `Py_hexdigits`
(`:88-89`), the digits 0 to 9 and the letters a to f in lower case (`Python/codecs.c:20`); this host's `hashlib.sha256` is that OpenSSL type (`openssl_sha256`, measured with
Python 3.13.16). `nas_land.sh` takes the first field of `sha256sum < <file>`, here uutils coreutils 0.10.0 (`/usr/bin/sha256sum`, measured):
`sha256sum` is a standalone checksum (`src/uu/sha256sum/src/sha256sum.rs:6`), whose `standalone_main` (`src/uu/checksum_common/src/lib.rs:39-43`)
takes the Text mode unless `--binary` (`:91-93`) and the untagged hexadecimal line (`src/uucore/src/lib/features/checksum/compute.rs:119-131`):
the digest, a space, the mode's character, `' '` for Text (`checksum/mod.rs:509-512`), and the name (`compute.rs:203-220`), so the first
field is the digest. The digest is `to_hex`, `hex::encode` (`src/uucore/src/lib/features/sum.rs:46-48`), lowercase in the crate the lock
file pins, `hex` 0.4.3 (`Cargo.lock:1295-1298`): `encode` calls `encode_hex` (`KokaKiwi/rust-hex@v0.4.3` `src/lib.rs:259-261`), which uses
`HEX_CHARS_LOWER`, the same sixteen lowercase characters (`:137-140`, `:83`; "Encodes `data` as hex string using lowercase characters", `:244`), the same
bytes as the published crate whose checksum the lock file names. Measured on this host: `printf x | sha256sum` printed 64 lowercase hex
digits, two spaces and `-`, the digits those of `hashlib.sha256(b"x").hexdigest()`.

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

# only when the CC waives the local reviews for this pull request at this head (#1061 round 2)
printf 'Waiver: local reviews for #%s at %s\n' <pr> <head8> > <waiver file>
LOCAL_REVIEW_WAIVER=<waiver file> nas_land.sh <pr> <read head prefix> <verdict file>

# only when the CC adjudicates a codex-review that says "patch is incorrect" with only P2 and P3 findings (the CC's ruling of 2026-10-13):
# the record's two kinds of line, written from the normalized file, then each disposition set to fixed, follow-ups or rejected
{ printf 'Adjudication: local review %s for #%s at %s\n' "$(sha256sum < <codex file> | cut -d' ' -f1)" <pr> <head8>
  jq -r '.findings[] | "Finding: P\(.priority) at \(.location): \(.title) (fixed)"' <codex file>; } > <adjudication file>
LOCAL_REVIEWS=<codex file> LOCAL_REVIEW_ADJUDICATION=<adjudication file> nas_land.sh <pr> <read head prefix> <verdict file>

# SQUASH_BODY_FILE: the squash commit's body, here beside the adjudication's line (alone, it is the whole body)
SQUASH_BODY_FILE=<body file> LOCAL_REVIEWS=<codex file> LOCAL_REVIEW_ADJUDICATION=<adjudication file> nas_land.sh <pr> <read head prefix> <verdict file>
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
removed (P1-3), and `tests/test_landing_scripts.py` now refuses any sha256, digest prefix or commit id in this README and in the
scripts that is neither a tracked file's, a named public artifact's nor a named public commit's (Tests, below).

| File | As committed |
| --- | --- |
| `uet_land.sh` | `95a4e1634b6a53b14d7736d2d40a3f0058a15aec9c9178e528ca44cfb74324ce` (441 lines) |
| `nas_land.sh` | `1ca0dabc6c535a08fb45f6956cf4549cc956ca6b25e798bb60c6a95cd398f511` (690 lines) |
| `horizon_land.sh` | `21c635cea5bc06d4dfa0b0e4a069a21af9d56b357246fc273915e67f8b67591c` (798 lines) |
| `codex_gate.py` | `7afaa831c0763dd14c584d76b17465fa50993656cd63eec9fd0c4412fddb74b2` (559 lines) |
| `review_normalize.py` | `b553d9cb67ca196bd587e980e01295e28e8ea0e2bcb3d0015fc5d040735a1594` (348 lines) |

On 2026-10-13 three fixes the CC had made in its live copies were ported here alone: the repository slug and the merging account in
`nas_land.sh` (CC correction #198; here also `LANDING_REPO`, the login check, and `uet_land.sh`, whose block is shared), and the stale
running review in `codex_gate.py` (CC correction #200, its block and constant byte for byte). The live copies' other local differences
(`SQUASH_BODY_FILE`, correction #176's currency checks, the host paths) were not taken. Read at 2026-10-13T01:50Z, the live copies were
`nas_land.sh` (474 lines, changed 2026-10-12T23:07:56Z) and `codex_gate.py` (241 lines, changed 2026-10-13T00:47:19Z); no digest of
them is published. The local review set, `lg_gate`'s heads with the read head's change and `review_normalize.py` are new here. Later on
2026-10-13 (the CC's ruling on local reviews that say `patch is incorrect` with only P2 and P3 findings, which asked for both in one change)
`SQUASH_BODY_FILE` was taken from the live `nas_land.sh` too, its five references (the usage line, the header at `:18-20`, the check at
`:38-41` and the merge call), with the changes in "The squash body" (above: an empty value refused, and since #1075's third commit the
content checked and passed as `--body`); the adjudication is new here. Correction #176's currency
checks and the host paths were still not taken.

Corrections the scripts carry: #118 (every gate before the merge, in order), #121 (a verdict file that states a landing gate needs
a receipt), #122 and #123 (a Codex review must have finished; uet#40 and uet#47 merged while one was running), #136
(verdict and record acceptance, change identity and the CI line: the three loose decision points the shared
`# >>> land-gate-fns` block replaced), the head-following of 2026-10-10 (uet#58: an update-branch rebase does not reach every API view at
once, so a head that moves during CI and carries the read head's change is followed, at most three times), #148 (the author address)
and #975's P2-3 (the CI allow-list), P2-2 (no text from `gh` or its API is printed: a failed merge, a failing status, every other `gh`
call), the gate error (P2: exit 4 and one fixed line, no traceback), the commit-status allow-list (P3) and P2-1 (the privacy scan
checks every prohibited identity), round 3 (above: the completion bound to the latest request, the gates read again before the merge,
typed values, no local diagnostics, the base re-read) and round 4 (above: the lock, the final gate, one read per file, the gate's
snapshot), and since 2026-10-13 #198 (the merging account), #200 (a stale running review) and the CC's ruling on local reviews that
say `patch is incorrect` with only P2 and P3 findings (the adjudication, and `SQUASH_BODY_FILE` from the CC's copy, both of which
`uet_land.sh` refuses: #1075). The block is
identical in the three scripts, apart from `lg_ci_state`, which only `uet_land.sh` has: `horizon_land.sh` took it from `nas_land.sh` byte
for byte on 2026-10-15, and its own functions follow the block.

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
    and never stop a landing. Its head is the caller's two reads and its links: a head that moved away and back during the run is not seen,
    and a clean comment ("No issues found") has no link at all (the pinned example, `code-review.md:80-84`, has none), so nothing in it
    binds the head the plugin read (Astra's follow-up 2 at 974090cf). Before the arm is required, bind the run and its head outside the
    comment.
  - The files are read at every gate call, each once, so a file rewritten between two calls is decided on its new text at the later one.
  - A Legacy rollout is refused (fail closed, above), so a review whose `codex exec` fell back to Legacy history gives no file; it has to
    be run again where the server serves paginated threads.
  - The record is matched a line at a time, so a finding whose location or title holds a newline cannot be listed, and its review stays 4
    (fail closed).
  - A `rejected` disposition is "rejected with evidence" in the CC's ruling, but the gate checks no evidence text: the record is free beside
    its `Adjudication:` and `Finding:` lines, so the evidence is the CC's to write and to review in the record (Astra's P3 at ca6f880b). No
    evidence field is defined; one would need a format and a presence check of its own.
  - The record has no size bound of its own (`nas_read` and the gate read it whole); the body file's bound is the merge argument's.
- The digest guard (Tests, below; #1061 round 2): a bare hex word of digits alone or of letters alone is not checked, since dates,
  counts and words are such words, so a digest prefix written bare that happens to have no letter (or no digit) passes; written with `…`
  it is checked whatever its digits. A pull request's body is checked only when `LANDING_PR_BODY` names it (below).
- `horizon_land.sh` (2026-10-15):
  - The lander is the required local workflow (#1195's decision record, `docs/decisions/2026-10-15-horizon-runtime-ecosystem-repository.md`,
    Decision 4), and GitHub enforces the three status contexts and freshness, not the local gates. A commit status carries no app identity: "Any person or integration
    with write permissions to a repository can set the state of any status check" (`available-rules-for-rulesets.md:178`; "Users with push
    access in a repository can create commit statuses", `api.github.com.json:79153`), and the ruleset then admits a merge whoever made it.
    GitHub checks only the three contexts' states, so a merge made in the web UI after the lander's posts, or after anyone posted the three,
    is not refused. The ruleset is the backstop and the lander's local checks are the gate; the final gate's exact-description read narrows
    a forged status to a landing by the lander. The closure path is the review App of `docs/decisions/2026-10-09-review-verdict-app-identity.md`,
    whose app can be selected as the statuses' expected source (`:178`), as for the other landers.
  - The digests of the private files are local only (the landing receipt), so the PROPOSAL self-audit (#1195's Decision 4), which would
    bind main's trailers to them, needs the host's `LANDING_COORD`: a host lost with its coordination tree loses them, and the trailers alone
    then bind names and the head, not bytes. Finding a merge made in the web UI after the posts is that self-audit's job too.
  - From the merge call until the receipt is written and the merge reported, HUP, INT and TERM are ignored, so an operator's interrupt then
    waits for the landing to finish its merge; a SIGKILL there leaves a merged pull request whose receipt may be unwritten.
  - The receipts are claims the lander does not re-run: a `CI:` line says what ran and how it ended, and nothing binds it to a run.
  - A SIGKILL, or the host lost, between the first POST and the merge leaves the posted successes standing (no trap runs): post `failure`
    for each `lander/` context at that head by hand before anything else merges.
  - Unmeasured: the live limit of a status description (the 140-character ceiling is borrowed from deployment statuses) and the
    `codeowners/errors` endpoint, which no landing has called yet (its use follows the REST description at `58b1e0c0`).
  - A merge state other than CLEAN stops the landing (6, 8 or 13), UNSTABLE ("Mergeable with non-passing commit status.",
    `schema.docs.graphql:26551-26553`: a status outside the ruleset that is failing) included, which GitHub would merge: fail closed. The
    two-minute poll rests on a lag measured on us-equities-trading #58, not documented by GitHub; a recomputation slower than it stops the
    landing too, and the next run posts the statuses again.
  - A revocation POST that fails (the API refusing, the network lost) leaves that context's success standing; the line says which, to post
    `failure` for it by hand.
  - CODEOWNERS v1 takes the merging account alone: a team, an address or another account stops the landing (8), and the patterns are not
    matched against the change (every rule must be the account's). GitHub's errors count is the only check of how GitHub reads the file.
  - `G`, the clone path, is expanded unquoted, as `U` and `G` are in the other two (above).
  - The squash body is one argument to `gh`, bounded at `MAX_ARG_STRLEN` ("The squash body", above): an offered body of the pull request's
    commit messages near 128 KiB would fail the merge call (exit 7, the statuses revoked). No bound of its own is checked.

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
  - the connector's 👀 without a Running row gave 5 after 90 minutes (round 2 had the 3 back, below);
  - a `LANDING_REPO` of another shape stops before any call (exit 2); every `-R "$R"` is quoted;
  - an account of type Organization, Bot or none gives no address (exit 11);
  - a Legacy rollout is refused with its own reason;
  - a local 2 tells the operator to correct the review files, not to wait for Codex;
  - a plugin comment whose links name another commit, or whose issues link only to another repository, is refused;
  - Astra's P1-3: every sha256 and every digest prefix in this README is a tracked file's or a named public artifact's (at c999eee5,
    seven full digests and four prefixes of host-only files were not); a planted one is found;
  - Astra's follow-ups 1 and 2: a refused retry removes the earlier file at `--out`, and a confidence that overflows to infinity
    (`1e999`) stops the gate (2).
- #1061 round 2 (the CC's Claude delta and Astra's read at 974090cf) adds, each failing at 974090cf unless it says otherwise (measured
  as above against that commit's `tools/landing`; the count is in the pull request):
  - local reviews required on nas: with neither variable set, `nas_land.sh` stops with 2 before any call, a held lock included (it landed
    on the connector's 5); a waiver for another pull request or another head, with a longer head prefix, revoked by a later `Waiver:`
    line, indented or missing stops with 2 before `update-branch` and `ready`, the waiver named by its file name only; a head-bound waiver
    lands, with CRLF line ends too, and its squash body is the default body and the waiver line (the waiver line alone for an empty
    default; exit 7 when the read fails, nothing of gh's printed); the final gate reads the waiver again; the requirement stands before the
    shared block and the lock, and nowhere in the shared block, `uet_land.sh` or `codex_gate.py`; and two controls, which pass at 974090cf
    too: with a local review set the waiver is not read and the merge names no body, and `uet_land.sh` is unchanged and ignores a waiver;
  - the connector's 👀 without a Running row waits (3) after 90 minutes and after ten hours (it gave 5 at 974090cf);
  - Astra's P2: a completion, a later Cancelled review of the same head and a stale row of another commit give 4 (5 at 974090cf), and the
    two reviews with no row running give 4 (0 at 974090cf, and at the base, whose test pinned "any completion evidence passes"); a later
    completion still gives 0, or the stale 5 beside such a row;
  - the cited sources of the users API's `type`, the repository name and the set-or-unset tests;
  - the digest guard (test-side; its probes measured against 974090cf's guard, which finds none of them): every hex value in this
    README and in the four scripts binds published bytes, in any letter case and written bare too, a commit id being one of the named
    public commits (`PUBLIC_COMMITS`, each read on GitHub); an upper-case digest or prefix, a bare prefix, one followed by ASCII dots, a
    digest in a comment and a longer run are found; the digest of a file git does not track under `tools/landing` is not published (a
    tree that is not a work tree lists its files); and with `LANDING_PR_BODY=<file>` the pull request's body is checked the same way.
    CI does not set it: every pull request's CI runs this module, a body edit does not run validate again (its `pull_request` types are
    opened, synchronize and reopened), and a body may cite an earlier head's files, whose bytes this tree does not hold.
- The CC's ruling of 2026-10-13 (a local re-review that says `patch is incorrect` with only P2 and P3 findings) and the CC's
  `SQUASH_BODY_FILE` add, each failing at 993cc890 (measured as above against that commit's `tools/landing`: 51 failures and 1 error, all
  in the 9 new tests; each case's result is in the pull request):
  - the gate on canned files: the record accepted for such a review when it lists every finding (fixed and follow-ups; rejected, with CRLF
    line ends; beside a correct review; the binding line last and no finding at all were accepted too until #1075's third commit, below,
    which refuses both), and 4 with its reason for an unlisted P2, an indented
    `Finding:` line, the sha256 of other bytes, another pull request or head, a later `Adjudication:` line, none or an indented one, a
    missing or a non-UTF-8 file, another disposition, a finding the review does not have, two dispositions, two findings on one line, two
    incorrect reviews, a P1 or a P0, and a record where no review says `patch is incorrect`; the record read once, and only for an
    incorrect review; and a control that gives 993cc890's line there too, an empty value;
  - `nas_land.sh` end to end through the real gate: an adjudicated landing, whose squash body records the record's line after the offered
    body; the README's commands writing a record that lands; a record for another pull request or head, with a longer head prefix,
    revoked, indented, cut short, of no listed file or missing stopping with 2 before `update-branch` and `ready`; an unlisted finding, a
    P1, another disposition and a record where no review says `patch is incorrect` stopping at the wait (the gate's 4, exit 9); the final
    gate reading the record again (revoked: 2; its `Finding:` line removed: the gate's 4, exit 9; bound to another listed file: 2);
  - `SQUASH_BODY_FILE`: alone as the whole body (`--body-file` until #1075's third commit, `--body` since); beside the waiver and beside an
    adjudication as the file's text and the line, the offered
    body not read; a file gone when the body is built (exit 7); `-`, a missing file, an empty file, a directory and an empty value
    stopping with 2 before any call, a held lock included; the check before the shared block and the lock, both variables outside the
    shared block, and the `gh` sources cited.
- The CC's read of #1075 adds, each failing at 25a9b48e (#1075's first commit; measured as above against its `tools/landing`: 7 failures,
  all in these 2 tests):
  - `uet_land.sh` with `LOCAL_REVIEW_ADJUDICATION` set, to a valid record beside the local review it decides and to an empty value, and
    with `SQUASH_BODY_FILE` set, to a body file and to an empty value: one line naming the variable as nas-only and exit 2, with no call
    of any kind, a held lock included (each landing merged at 25a9b48e, the valid record on the gate's adjudicated 0); and a control, the
    same landing with neither set, which merges;
  - the script text: each refusal once, after the arguments and before the shared block and the lock, and neither variable read anywhere
    else in `uet_land.sh` (this replaced the check that `uet_land.sh` did not mention them).
- #1075's third commit, for the three reads at ca6f880b (the Claude read, the co-op's local codex review and Astra's read), adds, each
  failing at ca6f880b unless it says otherwise (measured as above against its `tools/landing`: 30 failures and 1 error, all in the 13 new or
  changed tests; each case's result is in the pull request):
  - the record (the Claude read): a NUL-prefixed second `Adjudication:` line, in the gate (4) and in `nas_land.sh` (exit 2 before any
    gate call; it merged, its squash body naming the other file); a stale section's `(fixed)` that no longer disposes of a recurring
    finding; two identical findings that need a line each, and a `Finding:` line repeated beyond the review's count of it, with the
    counts printed a line each; an adjudication on the waiver path, set and empty, stopping with 2 before any call, a held lock included;
    a review that says `patch is incorrect` with no finding, refused in the gate and end to end (it merged); and the binding line last,
    whose earlier `Finding:` lines no longer count;
  - the digest the gate decides on (the co-op's codex review, Astra's P2-2): the gate adjudicating only the file `nas_land.sh` recorded
    (`LG_ADJUDICATION_SHA256`), and end to end, the review and its record replaced together on the final gate's statuses call, after its
    `verdict_gate`: exit 9 at the final gate (it merged, its squash body recording the earlier review);
  - the body (the co-op's codex review, Astra's P2-1): bytes that are not UTF-8, a code point above U+10FFFF, 1 MiB, a NUL byte alone beside
    the waiver and white space alone stopping with 2 before any call; a file emptied while the merge is validated, alone and beside the
    waiver, stopping with 7 when the body is built; emptied, or rewritten to other valid text, at the author lookup stopping with 7 at the
    final gate (each merged); the standalone file passed as `--body`; and the waiver or the adjudication revoked while the merge is
    validated, stopping with 2 when the body is built, before the author lookup (the final gate stopped it, after the author lookup);
  - coverage the Claude read asked for, the same at ca6f880b: a record bound from the start to another listed file, which stops at the
    wait (exit 9) on the gate's binding check (measured against a mutant whose binding check returns nothing: the gate's case gave 0, and
    end to end the recorded-digest check stopped it with another reason, so both cases fail), an adjudicated landing through
    `CODEX_LOCAL_REVIEW`, a title holding `(` and `)`, and a record and a body file of mode 000.
- #1075's fourth commit (the co-op's re-review at f3f1cabe, its one P2, adjudicated fix in this landing) adds, failing at f3f1cabe (measured
  as above against its `tools/landing`: 3 failures, all in this test): the body reader under an ISO-8859-1 locale compiled into a scratch
  `LOCPATH`, whose output must be the file's bytes, its trailing line ends dropped ("é" came out as the one byte `e9`, and "€" ended the
  reader with nothing written, exit 1), the same under `C.UTF-8` as the control (it passed at f3f1cabe too), and a landing under that
  locale whose merge call carries the body's UTF-8 bytes (it stopped with 2 at f3f1cabe). Where no ISO-8859-1 locale can be compiled, the
  test is skipped and says why.
- 2026-10-15, `horizon_land.sh`, end to end in `HorizonEndToEndTests` against a scratch repository of its own, whose main carries CODEOWNERS
  (the fake `gh` records a status POST at the front of `FAKE_STATUSES`, so the combined-status read serves it back, and answers
  `codeowners/errors` from `FAKE_CODEOWNERS_ERRORS`). Each fails at this change's base, where the script does not exist (every class that
  cuts the scripts errors in `setUpClass`), and the rules were also measured against copies of the script with one rule taken out (the counts
  are in the pull request):
  - a landing: the three POSTs at the head after every check, with their descriptions, then the combined-status read, then the squash merge
    pinned to the head with `-R seathatflowsinourveins/horizon`, and no Codex gate, validation, check-run read, `update-branch` or `ready`;
    two receipt files named in their order and bound locally by one digest (in the landing receipt since #1194's reads, published in the
    description before), the later line for a command winning; the trailers read back by `git interpret-trailers --parse
    --no-divider`, and by a plain `--parse` unless the offered body holds a `---` line;
  - refusals with no status posted and nothing merged: each argument and input of another form, and each input of the other landers set, an
    empty value included, before any call; a verdict missing, unreadable, holding a NUL byte, of another family, of the 8-digit prefix alone
    (which `nas_land.sh`'s acceptance takes: the control), of line 1's layout alone, of a head that shares the 8 digits, CHANGES_REQUESTED last
    or on line 1, or the same file in both slots, each before `ready`; the required command missing, a last line not `exit 0`, `exit 00`,
    receipts of another head or of the prefix; and the lines that land (a later exit 0, CRLF, another head's failure, shell characters);
  - a pure rebase of the read head (3), BEHIND, DIRTY, a main that is not an ancestor and an unreadable main (13), with no `update-branch`;
  - CODEOWNERS: another owner, a team, an address, a rule with no owner, no rule, no file, the top level's when `.github/` has none, the
    head's own fix of a foreign main, GitHub's errors, an unreadable or malformed errors reply (8); the pull request's own edit, an inline
    comment with CRLF and the login in capitals, and `.github/`'s file read before `docs/`'s (they land);
  - a POST that fails (15), the first or the second, printing nothing `gh` returned, and the trap's three failures; revocations that fail say so;
  - each gate flipped at the author lookup, after the POSTs: a verdict that turns CHANGES_REQUESTED (2); a verdict, the Muse verdict or a
    receipt whose bytes change (7); a receipt that gains an exit 1 (5); a failure or another description posted for a lander context, the
    context in other letters, another `lander/` context, an unreadable combined status (5); GitHub's errors unreadable (8); main moving or
    unreadable (13); the head moving (3); BLOCKED (8); UNKNOWN (6). Each merges nothing and posts the three failures;
  - the merge state polled 12 times after the POSTs (BLOCKED 8 with the thread count, UNKNOWN and UNSTABLE 6; BLOCKED then CLEAN lands); the
    final gate's reads as the last calls before the merge, in their order; a draft marked ready after the local checks and before the POSTs;
    a SIGTERM during the author lookup (exit 143 and the three failures); `horizon.lock` held (14, no call), the other two locks not its own;
    a Muse verdict that says CHANGES_REQUESTED, PASS or nothing for the full head, which lands and is recorded; the author lookup failing (11)
    and a failed merge (7), which revoke, and exit 12, which does not;
  - the script's text: the shared block equal to `nas_land.sh`'s, the refusals before the block and the lock and read nowhere else, no Codex
    gate, validation, check runs or update-branch in its own part, the trap lines right before the first POST and the merge mark right after
    the merge, the local refusals before `ready`, and its cited sources. It joins the existing checks of the parse and mode, the one group,
    the lock descriptor, the final gate's place, the README's variables, exit codes and digest row, the digest custody, the citations, the
    defaults and the author address;
  - correction #121 (the CC's ruling of 2026-10-15), each failing against the script as it stood before the ruling, which read no
    `GATES_DONE` (16 failures in these 3 tests): a verdict of each family that states a landing gate stops with 2 without `GATES_DONE`
    (before `ready` and the posts) and with one that names the 8-digit prefix alone (which `nas_land.sh`'s `lg_receipt_ok` takes: the
    control), and lands with one that names the full head, named in `Lander-gates-done`; a receipt missing, empty, holding a NUL byte or
    of another file name form stops with 2; without a stated gate `GATES_DONE` is not read (the control); `GATES_DONE` flipped after the
    posts stops with 7 when its bytes changed and with 2 when it is gone, each with the three failures; and the text: nas's four phrases,
    `lg_receipt_ok` given the full head, the check inside `verdict_gate` and the final gate's comparison;
  - #1194's two reads (the GPT read and the CC's, 2026-10-16), each failing against `horizon_land.sh` at 34add438 unless it says otherwise
    (measured with the module of this change against that script; the counts are in the pull request): no digest of a verdict, Muse's,
    `GATES_DONE` or a receipt, all holding a synthetic home path, nor a 7-digit prefix of one, in a status description or the squash body, and
    no hex there but the head and CODEOWNERS' sha256, while the landing receipt (0400) keeps every one; the receipt's place taken or not
    makeable (7, nothing posted) and its write failing after the merge (16, the statuses kept); a pull request based on another branch or of
    no base (13, before `ready` and the posts, its name not printed) and one retargeted after the posts (13, a final-gate flip with the three
    failures; a main-based control lands); the full head followed by `A`, `G`, `0` or `_` refused in a verdict and `A` in `GATES_DONE`, and a
    full stop, a space, a CR or a comma after it landing; the view after the merge failing with a sentinel on stdout, or of another state (12,
    the sentinel not printed, the receipt written with no merge commit); a TERM during the first revocation POST (the three failures, the exit
    the stop's 8); and the text: the trap's first line, the PROPOSAL label and the new citations;
  - #1194's delta reads at b4489b15 (the CC's micro and the local review), each failing against `horizon_land.sh` at b4489b15 unless it says
    otherwise (measured with the module of this change against that script; the counts are in the pull request): a TERM pending as the merge
    call finishes and one during the sleep after it (exit 0, the receipt written, nothing revoked; at b4489b15 both exited 143, the first
    revoking a merged head's statuses and the second leaving no receipt), with two controls that pass at b4489b15 too, a TERM before the merge
    call (143, the three failures, no receipt) and one during the author check (143, merged, the receipt and the statuses kept); 12 and 16 at
    once (12, the receipt's line printed; this pins b4489b15's behaviour, and passes there); a failed lookup of `.github/CODEOWNERS` beside the
    account's own top-level file (8; it landed at b4489b15), with the control that `.github/`'s file decides, and a failed read of the blob (8,
    its own reason); a leading, trailing or doubled `:` in `LOCAL_CI_RECEIPTS` (2 before any call; the trailing one landed at b4489b15); and
    the text: "the required local workflow", "the PROPOSAL self-audit", the bash(1) texts for `trap ''` and noclobber, the lag's wording, the
    signal hold right before the merge call and the exit traps set again after the report.

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

#1061 round 2 (the CC's Claude delta and Astra's read at 974090cf). Read on 2026-10-13 in the local upstream mirrors (`cli/cli` at
`v2.102.0`, the commit `fc4b137c`; `python/cpython` at `v3.13.16`; `github/docs` at `be38ec5d`; `github/rest-api-description` at
`58b1e0c00b39`), clean at those commits, and in the installed bash 5.3 (Ubuntu's 5.3-2ubuntu1):

| Mechanism | Source at the pin, sha256 | Lines read and what they say |
| --- | --- | --- |
| The users API's `type` (the CC's P3) | `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…` | `:88612-88614` `GET /users/{username}`, "Get a user", whose reply is the private or the public user schema; the public schema's `type` is `{"type": "string"}` (`:126248-126250`) and the private one's a string with the example "User" (`:160055-160058`), with no enum; an organization's account reads `"type": "Organization"` in the description's examples (the first at `:311038`). So `lg_author_email` takes the literal `User` alone |
| The repository name (the CC's P3) | the same file; `github/docs@be38ec5d:data/reusables/repositories/repo-name.md`, `5a1343a0acb89ef1811e5fa93202ac452a0cbeef97656ead236f87910bb2a08d` | `:344898-344906` the path parameter `owner`, "The account owner of the repository. The name is not case sensitive.", and `:344907-344915` `repo`, "The name of the repository without the `.git` extension. The name is not case sensitive."; `repo-name.md:1` "The repository name must not exceed 100 characters, and can only contain ASCII letters, digits, and the characters `.`, `-`, and `_`" |
| A set or an unset variable (Astra's follow-up 4) | the installed `bash(1)`; `python/cpython@v3.13.16`: `Doc/library/os.rst`, `1d54f83bb3f583e37bae07d820d16206cf02f4fb2ef281338635b4b7fd01ebe4`, `Lib/os.py`, `18560b0a37dfb90b4712fba97668d44a1328c5566b10deffaee292ba12cc21ff`, `Lib/_collections_abc.py`, `87601195497fde3b7cea03bce396e1b713c17af3d273298d99d3bc0147f745b9` | `bash(1)`, Parameter Expansion: "When not performing substring expansion, using the forms documented below (e.g., `:-`), bash tests for a parameter that is unset or null. Omitting the colon tests only for a parameter that is unset.", so `${VAR+x}` is empty only for an unset `VAR`; `os.rst:184-186` `os.environ` is "A mapping object", `os.py:704` `class _Environ(MutableMapping)`, and `_collections_abc.py:808-813` its `get` gives `None` only for a missing key |
| A waived landing's squash body | `cli/cli@v2.102.0`: `pkg/cmd/pr/merge/merge.go`, `ca3849b4…`, `pkg/cmd/pr/merge/http.go`, `17eb5418a1771692864b8f7476947f088252ccde0037d089c9faf441ff7c8877`; the GraphQL schema, `3ed09565…` | `merge.go:146-147` `--body` or `--body-file` sets `BodySet`, `:176` "Body `text` for the merge commit"; `http.go:72-75` only a set body becomes the mutation's `CommitBody`; `merge.go:721-735` the "edit the commit message" step starts from `getMergeText` (`http.go:121-158`, the query `viewerMergeBodyText(mergeType: $method)` at `:136`) and then sets the body; `schema.docs.graphql:45597-45605` `viewerMergeBodyText(mergeType: PullRequestMergeMethod): String!`, "The merge body text for the viewer and method", and `:26079-26082` `MergePullRequestInput.commitBody`, "if omitted, a default message will be used". Measured on 2026-10-13 with the script's query on #1061: the reply is the pull request's commit messages (the repository's `squashMergeCommitMessage` is `COMMIT_MESSAGES`), and `--jq` prints the string raw |
| Replacing and removing a file, and a finite confidence (Astra's follow-up 4) | `python/cpython@v3.13.16`: `Doc/library/os.rst`, `1d54f83b…`; `Doc/library/json.rst`, `1dabdd646bfbf961c3ffcf79dd41bd81dc6a2e1ed59428b32662ed16acff08df`; `Doc/library/math.rst`, `5a46b6cc199fd025f914f39a39199745bad9fbbf540246abcb658671899be77e` | `os.rst:2754-2760` `os.replace` replaces an existing file "silently", and "the renaming will be an atomic operation (this is a POSIX requirement)"; `:3671-3676` `unlink` is `remove`, which `:2661-2665` raises `FileNotFoundError` for a file that does not exist; `json.rst:308-311` a JSON number is parsed with `float(num_str)` by default, so `1e999` gives `inf` (measured with Python 3.13.16); `math.rst:370-373` `isfinite` is false for an infinity or a NaN |

2026-10-13, `SQUASH_BODY_FILE` (the CC's ruling on local reviews that say `patch is incorrect` with only P2 and P3 findings). Read in the
local upstream mirror of `cli/cli` at `v2.102.0` (the commit `fc4b137c`, clean), and each file fetched on 2026-10-13 between 12:45Z and
12:48Z with `curl -fsSL https://raw.githubusercontent.com/cli/cli/v2.102.0/<path>`: the same bytes (installed: `gh` 2.102.0):

| Mechanism | Source at the pin, sha256 | Lines read and what they say |
| --- | --- | --- |
| A body file, `-`, and one body flag (`SQUASH_BODY_FILE`) | `cli/cli@v2.102.0`: `pkg/cmd/pr/merge/merge.go`, `ca3849b4…`; `pkg/cmdutil/file_input.go`, `94076f6234180f85f2a555a5733e024146ea2c0cac54af19c86c72b015252828`; `pkg/cmd/pr/merge/http.go`, `17eb5418…` | `merge.go:177` `--body-file`, "Read body text from `file` (use "-" to read from standard input)"; `:138-143` "specify only one of `--body` or `--body-file`" (`cmdutil.MutuallyExclusive`), which is why a waiver's or an adjudication's line goes with the file's text in one `--body`; `:146-153` either flag sets `BodySet`, and a body file is read with `cmdutil.ReadFile` when the command runs, its bytes the body (`opts.Body = string(b)`); `file_input.go:8-15` `ReadFile` reads standard input for `-` and the named file otherwise (`os.ReadFile`); `http.go:72-75` a set body becomes the mutation's `CommitBody` |

#1075's third commit (the three reads at ca6f880b). Each file was fetched on 2026-10-13 between 13:50Z and 14:09Z with `curl -fsSL
https://raw.githubusercontent.com/<owner>/<repo>/<tag>/<path>` and read at the lines given; the cpython files are the same bytes in the local
upstream mirror at `v3.13.16` (the commit `cbc944f4`, clean). Installed: Python 3.13.16, uutils coreutils 0.10.0 (`sha256sum --version`),
bash 5.3.9 (Ubuntu's `bash` 5.3-2ubuntu1, whose `bash.1.gz` is the manual quoted), glibc 2.43's `iconv`, Linux 6.18 (WSL2).

| Mechanism | Source at the pin, sha256 | Lines read and what they say |
| --- | --- | --- |
| hexdigest's case (the Claude read's P2-1) | `python/cpython@v3.13.16`: `Doc/library/hashlib.rst`, `bf23b9b1e5dc9ff5b0b86a7c88637d73e2c8496681dca125aa3df1da631ee106`; `Modules/_hashopenssl.c`, `3805805cbb3153bf89e785c6e861b51a09a5a4c3d8747e4e3086c6c9befbf648`; `Python/pystrhex.c`, `7842f6d7d9b58bcbf10cbb24d29f6d1f36668e20f935689e197bbe0abdccd4ed`; `Python/codecs.c`, `244f9bebae318b08bc062d20c00b945a7f11fac55599a2b32a0d25944bcc3c6f` | `hashlib.rst:217-220` `hexdigest()` returns a string "containing only hexadecimal digits" (no case); `_hashopenssl.c:652` `EVP_hexdigest_impl` returns `_Py_strhex((const char *)digest, (Py_ssize_t)digest_size)`; `pystrhex.c:145-148` `_Py_strhex` calls `_Py_strhex_impl` with no separator, whose `:88-89` write `Py_hexdigits[c >> 4]` and `Py_hexdigits[c & 0x0f]`; `codecs.c:20` `const char *Py_hexdigits` is the string of the digits 0 to 9 and the letters a to f, in lower case |
| `sha256sum`'s line and case (the Claude read's P2-1) | `uutils/coreutils@0.10.0`: `src/uu/sha256sum/src/sha256sum.rs`, `48254a0adf102ceaa5ab91c1146fb3a7d21f79de3396b89be6f9480025ae6d6e`; `src/uu/checksum_common/src/lib.rs`, `ad05144f9d1663e79fa2f579a3fdbbef4820373ab6bcb4028d897e891d3e37d3`; `src/uucore/src/lib/features/checksum/compute.rs`, `077a6b11783d23f507ccc5f94d39916ce8d1caf5993e75e87218ac7576c7b932`; `src/uucore/src/lib/features/checksum/mod.rs`, `362f62dd0ceb60b5b2c107ae078d276c33b727354fd2d8576aab2ef1780c27f7`; `src/uucore/src/lib/features/sum.rs`, `f03de154b8899af73adbc7fa866a77113aef1e500df24b77f59802e4c1ebea8b`; `Cargo.lock`, `0833b527…` (above); `KokaKiwi/rust-hex@v0.4.3`: `src/lib.rs`, `bc16c851822629225d2d2653ea080f131b0f2c4704d3ff27fed955c9b8b42f71`, the same bytes as `src/lib.rs` of `https://static.crates.io/crates/hex/hex-0.4.3.crate`, `7f24254aa9a54b5c858eaee2f5bccdb46aaf0e486a595ed5fd8f86ba55232a70` | `sha256sum.rs:6` `declare_standalone!("sha256sum", …Sha256)`; `lib.rs:39-43` the macro calls `standalone_main`, `:91-93` `text = !BINARY` and `OutputFormat::from_standalone(text, tag)`; `compute.rs:119-131` without `--tag`, `Untagged(DigestFormat::Hexadecimal, Text or Binary)`, `:203-220` `write!(w, "{prefix}{sum} {}", reading_mode.as_char())` then the name; `mod.rs:509-512` `Binary => '*'`, `Text => ' '`; `compute.rs:294-299` a hexadecimal digest is `sum.to_hex()`, `sum.rs:46-48` `Self::Vec(buf) => Ok(hex::encode(buf))`; `Cargo.lock:1295-1298` `hex` 0.4.3 with that crate's checksum; `rust-hex` `lib.rs:259-261` `encode` is `data.encode_hex()`, `:137-140` `encode_to_iter(HEX_CHARS_LOWER, …)`, `:83` `HEX_CHARS_LOWER: &[u8; 16]`, the same sixteen characters in lower case, `:244` "Encodes `data` as hex string using lowercase characters" |
| One argument's bound (Astra's P2-1, the body's ceiling) | `torvalds/linux@v6.18:include/uapi/linux/binfmts.h`, `6f435af082f135d9171035ffe88fe826a81c0c7880f2ec3b4e048644fe7c704d` | `:15` `#define MAX_ARG_STRLEN (PAGE_SIZE * 32)`; `getconf PAGESIZE` printed 4096, and `/bin/true` took an argument of 131071 bytes and refused one of 131072 (rc 126), measured |
| A NUL byte read in bash (the Claude read's P3-1) | the installed `bash(1)`, Ubuntu's `bash` 5.3-2ubuntu1, `read` (UNMIRRORED: the installed manual, not a pinned upstream file) | "If *delim* is the empty string, **read** will terminate a line when it reads a NUL character", and "Other than the case where *delim* is the empty string, **read** ignores any NUL characters in the input"; `help read`: "The return code is zero, unless end-of-file is encountered", so `nas_read`'s zero is a NUL and a non-zero the end of the file |
| Strict UTF-8 (Astra's P2-1) | `python/cpython@v3.13.16`, measured with Python 3.13.16 and glibc 2.43's `iconv -f UTF-8 -t UTF-8` | of 13 probes Python's strict decoder and `iconv` agreed on 11; `iconv` took a code point above U+10FFFF (`f4 90 80 80`) and an `f5` lead byte that Python refuses, so `SB_READER` decodes with Python, as `codex_gate.py` decodes a record |

2026-10-15, `horizon_land.sh`. Read on 2026-10-15, and for #1194's reads on 2026-10-16, in the local upstream mirrors, clean at their
commits: `github/rest-api-description` at `58b1e0c00b39`, `github/docs` at `be38ec5d`, `git/git` at `v2.53.0` (the commit `67ad4214`), and
`cli/cli`, whose `pkg/cmd/api/api.go` is the bytes cited above for `v2.102.0` and whose `v2.102.0` mirror (`fc4b137c`) holds
`pkg/cmd/pr/merge/http.go`; and in the installed bash 5.3 (Ubuntu's `bash` 5.3-2ubuntu1, bash 5.3.9) and git 2.53.0, where it says measured:

| Mechanism | Source at the pin, sha256 | Lines read and what they say |
| --- | --- | --- |
| A commit status's POST, its fields and the context's case | `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…` | `:79150-79157` `POST /repos/{owner}/{repo}/statuses/{sha}`, "Create a commit status": "Users with push access in a repository can create commit statuses for a given SHA", and "there is a limit of 1000 statuses per `sha` and `context`" (`:79153`); `:79179-79214` its body: `state` (`error`, `failure`, `pending` or `success`; the one required field), `target_url`, `description` (`:79201-79205`: a nullable string, "A short description of the status.", with no maximum) and `context`, "This field is case-insensitive" (`:79208`) |
| No maximum for a commit status's description; 140 for a deployment status's | `github/docs@be38ec5d78e24172587e61b3c6ff40ace1865c71:src/rest/data/fpt-2022-11-28/commits.json`, `57f0a021…`; `src/rest/data/fpt-2022-11-28/deployments.json`, `b5451303e7dab0894f4d7eaa51cb3dc71694586f7ac1304206f36ef456b988cf` | `commits.json:10906` "A short description of the status." and no maximum; `deployments.json:6234` a deployment status's: "A short description of the status. The maximum description length is 140 characters." This is the ceiling the lander borrows (no other bound is stated) |
| `gh api -f` posts | `cli/cli@v2.102.0:pkg/cmd/api/api.go`, `030eda84…` | `:104-110` "Pass one or more `-f/--raw-field` values in `key=value` format to add static string parameters to the request payload", and adding them "will automatically switch the request method to `POST`"; `:293` `--method` (`-X`), "GET" by default; `:295` `--raw-field` (`-f`); `:329-331` with parameters and no `--method`, the method is POST |
| Where GitHub reads CODEOWNERS, and how | `github/docs@be38ec5d:content/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners.md`, `700caf36acb0755221f0eddf85bbf5dd9096e1c7965eb1daa126937e09c653e9` | `:36` the file in `.github/`, the root or `docs/`; GitHub "will search for them in that order and use the first one it finds"; `:44` "pull requests use the version of `CODEOWNERS` from the base branch of the pull request"; `:52` a file of 3 MB or more "will not be loaded"; `:79` "If any line in your CODEOWNERS file contains invalid syntax, that line will be skipped", and the errors are "accessible via the API"; `:99` an inline comment after the owners; `:140-146` a pattern whose owners are left empty: "Without an owner, changes to `apps/github` can be made with the approval of any user who has write access" |
| GitHub's CODEOWNERS errors | `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…` | `:53272-53329` `GET /repos/{owner}/{repo}/codeowners/errors`, "List CODEOWNERS errors" (`repos/codeowners-errors`), with `ref`, "A branch, tag or commit name used to determine which version of the CODEOWNERS file to use", and a 404 "Resource not found"; `:147909-147969` the `codeowners-errors` schema, an `errors` list required at `:147966-147968`, each error's `line`, `column`, `source`, `kind`, `suggestion`, `message` and `path`. The lander reads the count alone |
| The trailers, and a `---` line | `git/git@v2.53.0:Documentation/git-interpret-trailers.adoc`, `6d62454c79ea8c3527fe78cee53dc0d5919f094d35176986207950cbd80c96e2` | `:44-49` a "---" divider line, and what follows it, is not part of the message "unless `--no-divider` is specified"; `:88-92` trailers are a group of lines that is all trailers (or holds at least 25%) and is "preceded by one or more empty (or whitespace-only) lines"; `:181-184` `--no-divider`: "Do not treat `---` as the end of the commit message". Measured with git 2.53.0: a body with a `---` line gave a plain `--parse` no trailer, and `--parse --no-divider` and `git log --format='%(trailers)'` every one |
| A ruleset's required status checks (#1194's CC read) | `github/docs@be38ec5d:content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets.md`, `1d1dad8bfbc0cc3ec1905193b12292d4e6e780c6ec9d3db7ee0f4b154d24f00b` | `:172` "Required status checks can be checks or statuses"; `:174` "You can use the commit status API to allow external services to mark commits with an appropriate status"; `:176` "all required status checks must pass before collaborators can merge changes into the branch or tag"; `:178` "Any person or integration with write permissions to a repository can set the state of any status check in the repository", unless an app is selected "as the expected source of status updates" ("If the status is set by any other person or integration, merging won't be allowed"); `:188-193` "loose" or "strict": strict is "The **Require branches to be up to date before merging** checkbox is checked", "The topic branch **must** be up to date with the base branch before merging", and "This is the default behavior for required status checks". Nothing there says a status's description counts for nothing (PROPOSAL) |
| The merge pins the head, not the base (#1194's GPT read, P2) | `cli/cli@v2.102.0:pkg/cmd/pr/merge/http.go`, `17eb5418…` (the local upstream mirror at `fc4b137c`, clean) | `:47-50` `mergePullRequest` builds `MergePullRequestInput` from `PullRequestID`, `:52-75` the method, author, headline and body, `:77-80` `ExpectedHeadOid` when given; no base field |
| The merge states (#1194's CC read) | `github/docs@be38ec5d:src/graphql/data/fpt/schema.docs.graphql`, `3ed09565…` (the bytes of the schema cited above) | `:26511-26554` `enum MergeStateStatus`: BEHIND "The head ref is out of date." (`:26513-26515`), BLOCKED "The merge is blocked." (`:26518-26520`), CLEAN "Mergeable and passing commit status." (`:26523-26525`), DIRTY "The merge commit cannot be cleanly created." (`:26528-26530`), DRAFT deprecated (`:26533-26538`), HAS_HOOKS (`:26541-26543`), UNKNOWN "The state cannot currently be determined." (`:26546-26548`), UNSTABLE "Mergeable with non-passing commit status." (`:26551-26553`) |
| The EXIT trap and the signals | the installed `bash(1)`, Ubuntu's `bash` 5.3-2ubuntu1 (UNMIRRORED: the installed manual, not a pinned upstream file) | `exit`: "Any trap on EXIT is executed before the shell terminates"; SIGNALS: "If bash is waiting for a command to complete and receives a signal for which a trap has been set, it will not execute the trap until the command completes"; `trap`: for EXIT (0) the action "is executed on exit from the shell". Measured with bash 5.3.9: the EXIT trap keeps the exit status (an `exit 7` stayed 7); a `$(...)` subshell's exit does not run it; a SIGTERM while a child runs exits 143 and runs it, with a TERM trap and without one; `read -r -d ''` keeps a file's bytes exactly (a CR, bytes that are not UTF-8, trailing newlines) under C.UTF-8 and under C |
