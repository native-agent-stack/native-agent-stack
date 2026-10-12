# Landing scripts

The command center (CC) lands pull requests with four files kept here, so the repository holds the one copy and its tests:
`uet_land.sh` (the private trading repository), `nas_land.sh` (this repository), `codex_gate.py` (the Codex review gate that
both call) and `squash_body_scan.py` (the publication scan of a squash body, which both call when `SQUASH_BODY_FILE` is set; new in
#1027, with no live copy). The scripts merge pull requests. No workflow runs them: the CC runs them from a clone of this repository,
and CI runs their tests.

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
must have succeeded at the head (every page of check runs is read; the rule is below), the Codex gate is asked again before the
validation, and the head is then merged into the current `origin/main` in a temporary worktree
under `/var/tmp` where `scripts/validate.py` must exit 0, and after it each currency check of `validate.yml`'s shard 0 whose script the
merge holds (exit 10 otherwise; CC correction #176, below). Their output is never printed: it goes to a file made by
`mktemp "${TMPDIR:-/tmp}/nas-validate-XXXXXX"` (mode 0600) outside the worktree, and exit 10 names that file, the exit code and, for a
currency check, its command. `gh pr
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

**The currency checks (`nas_land.sh`, CC correction #176).** #1007 bound the sha256 of a catalog file in `final-stack.json` and #1018
changed that file. Each was green on its own base and `validate.py` passed on the merge, so #1018 landed, and `main`'s
`validate-shard-0` failed on `scripts/final_stack.py --check`, which `validate.py` does not run. After `validate.py` the merge now runs
the currency checks of shard 0 of `.github/workflows/validate.yml` as those steps run them, with `-E -s -B` as for `validate.py`, in the
workflow's order (`validate.yml:135-177`). They are every shard-0 step that runs a Python script with `--check`:
`blueprints/blind-catalog-convergence/audit_reports.py`, `tools/sota-convergence/build_verdicts.py`, `scripts/component_matrix.py`,
`scripts/new_host_grand_list.py`, `scripts/final_stack.py`, `tools/sota-convergence/gap_crosswalk.py build`,
`tools/sota-convergence/gap_wave_ledger.py` with its step's `--wave` and `--owner` arguments (`validate.yml:166-174`, a folded `run: >-`)
and `scripts/build_ecosystem.py`, each with `--check`. #176 named seven; the CC's ruling of 2026-10-12 added the ledger check, and a
test keeps the list equal to the workflow's steps. A check runs only when its script is in the merge; the first that fails stops the
landing with exit 10, named by its command, and its output stays in the validation's file. On `main` at `86fa3844` the eight exit 0 in
about 8 s, 6.3 s of it `build_ecosystem.py` (measured 2026-10-12T02:18Z with `python3 -E -s -B`). `uet_land.sh` needs no such step: the trading repository's `main` rules count `ci-gate` only on a head that is up
to date with `main` (`strict_required_status_checks_policy: true`), so its CI, `uv lock --check` included (`ci.yml` at `0e987311`), ran
on the tree the squash merge makes. This repository's rules do not require that (`false`; both read from `GET
/repos/{owner}/{repo}/rules/branches/main` at 2026-10-12T02:23:46Z), which is why `nas_land.sh` validates the merge itself. A merge
queue would test each merge with the pull requests ahead of it on GitHub's side, and needs an organization-owned repository (sources below).

**The squash body (`SQUASH_BODY_FILE`, the CC, 2026-10-12).** Both repositories' squash setting is `COMMIT_MESSAGES`, "default to the
branch's commit messages" (`squash_merge_commit_message`, read from `GET /repos/{owner}/{repo}` at 2026-10-12T02:23:46Z), and the scripts
named no body, so a squash merge carried the branch's commit messages into `main`, a claim that review corrected later included. When
`SQUASH_BODY_FILE` is set, the merge passes a scanned snapshot of it with `--body-file`; `gh` reads the file when the merge call starts and
sends it as `MergePullRequestInput.commitBody`, "Commit body to use for the merge commit; if omitted, a default message will be used"
(sources below). The file is checked before the lock and any call: a value that is not a readable, non-empty regular file stops the
landing with exit 2, `-` included (`gh` reads `-` as standard input), and the path is never printed. An empty value is none.

**The squash body is scanned (#1027, Astra's P1 at d6be1b02).** The body becomes the commit message in `main`'s history for good, and the
check above read no byte of it: a body holding a home path, an account name, an address that is not a no-reply one or a token shape
landed (four synthetic payloads, each exit 0 with one merge call). `gh` reads the file when the merge call starts, over an hour after
any check made on it in the worst case (the Codex wait takes up to 20 minutes, the CI wait up to 50), so the scanned bytes must be the
bytes `gh` reads. A set `SQUASH_BODY_FILE` is therefore copied once to a snapshot (`mktemp "${TMPDIR:-/tmp}/squash-body-XXXXXX"`, mode 0600),
the snapshot is scanned twice, and the merge is given the snapshot, never the file; the final gate has nothing of the caller's file to read
again. An `EXIT` trap removes the snapshot on every exit, a terminating signal included (measured 2026-10-12 with bash 5.3.9: after
SIGTERM and SIGHUP sent to a script holding a snapshot, none was left). Both scans run before the lock and before any `gh` or `git` call,
with `-E -s -B` as `merge_validate` runs `validate.py` (with `-I` the script's directory is off `sys.path`, `validate.py` cannot import its
sibling `host_name_scan.py` and exits 2: measured 2026-10-12, and CPython's documentation of `-I`, sources below):

1. `squash_body_scan.py <snapshot> <validate.py> <names file>`, in this directory. It reads the text, and its percent-decoded form, for
   every pattern of `PRIVATE_CONTENT` in the given `validate.py` (the repository's table for published text: home paths, the dash-encoded
   and graph-id forms, Windows user paths, tokens and session identifiers); for a WSL UNC home path, `\\wsl.localhost\<distro>\home\<user>`
   or `\\wsl$\<distro>\home\<user>`, which that table does not match (it knows the forward-slash forms), any run of backslashes counting
   for one because JSON and Markdown double them; for an email address that is not a no-reply one (GitHub's `ID+USERNAME` and `USERNAME`
   forms at `users.noreply.github.com`, or a local part of exactly `noreply` or `no-reply`, pass; the shape is the native private-email
   rule of `scripts/host_name_scan.py`, with a lookbehind so that a long run costs one pass, and a local part with no letter or digit,
   such as the backticked `@AGENTS.md` import, is no mailbox; two shapes that are not addresses pass, by the CC's ruling of 2026-10-12: a
   systemd unit instance, `<name>@<instance>.<type>` with a type of `service`, `timer`, `socket`, `target`, `path` or `mount` and only the
   characters a unit name has, as in `getty@tty1.service`, and an address of the short list `VENDOR_TRAILER_ADDRESSES`, each entry with the
   vendor source it comes from, now `codex@openai.com`, the Codex co-author address in the vendor's own history, which #1002's email registry
   will replace); and for each name of the names file as a whole token in any letter case (not inside a longer run of letters or digits,
   the boundary rule of `host_name_scan.py`). A name equal to the running host's own name (`hostname`, as `socket.gethostname()` returns it,
   compared when the scan runs without regard to case, and never printed) is a warning and not a refusal, by the CC's ruling that the host
   name is hygiene and never a blocker: its occurrences are counted. Every other name still refuses. The names file is
   `$LANDING_COORD/command-center/cc-tools/landing-prohibited-names.env`: one `LANDING_PROHIBITED_NAMES=<name>,<name>,...` assignment, the
   list the tests read from the environment under that name. It is parsed, never sourced: no line of it runs, and no name reaches a shell
   variable, an argument or the output. It prints one line and nothing of the body: `squash body scan: clean (names_checked=<n>[,
   warnings=<k>])`, or `squash body scan: refused: <class> (line <n>)[; ...][ (warnings=<k>)]` with the classes of the list above, or
   `squash body scan: could not run`. For a count above 0 the landing prints one line of its own, `SQUASH_BODY_FILE names this host's own
   name <k> time(s): a warning, not a refusal (the name is not printed)`, and goes on.
2. `scripts/validate.py --scan-file <snapshot>`, the scan the pre-push hook runs: `PRIVATE_CONTENT` and the runtime host-local names
   (the account, the host, the Windows profiles) through Betterleaks at `host_name_scan.py`'s pin. Its answer counts only as the exact
   line `{"matching_locations": 0, "scanned_files": <n>, "source": "host", "status": "passed"}`; the synthetic sources of
   `NATIVE_AGENT_HOST_NAMES_JSON` (`"source": "synthetic"`) never pass. It leaves the host's own name alone on a WSL host whose hostname is
   its `WSL_DISTRO_NAME`: `scripts/host_name_scan.py:65-68` drops the hostname source then, and on the CC's host it does (measured
   2026-10-12: a body naming the host passed both scans). Where the two differ, this scan would refuse a mention.

A match stops the landing with exit 2 and the line `SQUASH_BODY_FILE holds text the publication scan refuses (details withheld;
squash_body_scan.py names the classes and lines): stop, nothing merged`. A snapshot that cannot be made or copied, a scanner or names file
that is missing or unreadable, a scan that fails and any answer that is not a scan's own clean line (an empty one included) stop it with
exit 2 and `SQUASH_BODY_FILE could not be scanned: a scanner or the names file is missing, unreadable or failed (details withheld): stop,
nothing merged`: the scan fails closed. No path, name, text or scanner output is printed, but one count: how often the body names the
host's own name. To see why a body is refused, run
`python3 -E -s -B squash_body_scan.py <body> <validate.py> <names file>` by hand. The defaults are the scanner beside the script (as
`codex_gate.py` is), `scripts/validate.py` in the clone `LANDING_NAS_REPO` names (the CC's checkout by default, for both scripts), and the
names file above.

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
| `LANDING_NAS_REPO` | `$HOME/code/native-agent-stack` | both | clone of this repository, used the same way by `nas_land.sh` (no whitespace); both scripts take the squash body scan's `scripts/validate.py` from it (#1027) |
| `LANDING_COORD` | `${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/coordination` | both | coordination tree; a status description `PASS: trading-cc/reads/<record>.md` names `$LANDING_COORD/trading-cc/reads/<record>.md` |
| `LANDING_GATE` | `codex_gate.py` in the directory of the script, symlinks resolved (`readlink -f "$0"`) | both | the Codex gate; it works through a symlink or a wrapper that `exec`s the real path, and not when the script is read from a pipe or a process substitution (set this variable then) |
| `LANDING_LOCK_DIR` | `$LANDING_COORD/command-center/landing-locks` | both | where the landing lock of each repository is kept (`us-equities-trading.lock`, `native-agent-stack.lock`); created when missing, and outside every worktree |
| `VERDICT_FILES` | none | `uet_land.sh` | space-separated verdict files that each must name the read head |
| `GATES_DONE` | none | both | receipt naming the read head; required when a verdict file states a landing gate |
| `GPT_VERDICT` | none | `uet_land.sh` | the co-op's verdict file accepted instead of Codex when `codex_gate.py` exits 5 |
| `SQUASH_BODY_FILE` | none | both | the squash commit's body (`gh pr merge --body-file`), for a pull request whose commit messages carry a claim corrected after review; it must be a readable, non-empty regular file, not `-`, and its text must pass the publication scan (a snapshot of it is scanned and is the file the merge is given; #1027), or the landing stops with exit 2 before any call; an empty value is none |
| `LANDING_BODY_SCAN` | `squash_body_scan.py` in the directory of the script, symlinks resolved | both | the squash body's scanner (only when `SQUASH_BODY_FILE` is set); set it when the script is read from a pipe or a process substitution; a missing file stops the landing with exit 2 |
| `LANDING_SCANNER` | `$LANDING_NAS_REPO/scripts/validate.py` | both | the repository's `validate.py`, which the squash body scan loads for `PRIVATE_CONTENT` and runs as `validate.py --scan-file`; a missing file stops the landing with exit 2 |
| `LANDING_NAMES_FILE` | `$LANDING_COORD/command-center/cc-tools/landing-prohibited-names.env` | both | the names the squash body scan refuses: one `LANDING_PROHIBITED_NAMES=<name>,<name>,...` assignment, parsed and never sourced; missing, unreadable or naming nobody stops the landing with exit 2 |
| `TMPDIR` | `/tmp` | both | where a failed merge keeps gh's output (`merge-fail-XXXXXX`, mode 0600), and `nas_land.sh` the output of the validation or of the currency check that failed (`nas-validate-XXXXXX`, kept when it fails), and both scripts the squash body's snapshot (`squash-body-XXXXXX`, mode 0600, removed when the script exits) |
| `LANDING_PROHIBITED_NAMES` | none | the tests only | comma-separated identities that must not appear in any form under `tools/landing` (see Tests) |

The scripts also need `gh` 2.48.0 or later (`gh api --paginate --slurp`; authenticated for the repository), `git` 2.39.0 or
later (`git patch-id --verbatim`), `jq`, `python3` 3.7 or later, GNU `grep`, `sha256sum`, `readlink -f` and util-linux `flock` (the
landing lock; without it every landing stops with exit 14). They run under `set -u`, so `HOME` must be set whenever a default above is
used.
`nas_land.sh` also needs a git committer identity: its validation merge (`git merge --no-commit`) refuses to start without
one, and the script then reports exit 10, "does not merge cleanly".

## Exit codes

From the script headers. `uet_land.sh`: 2 verdict gate (a verdict file, `GATES_DONE` or `trading-cc-read`, also when a file, record or
status cannot be read) or a `SQUASH_BODY_FILE` that is not a readable, non-empty file, that the publication scan refuses or that cannot be scanned (before any call), 3 head moved, 4 change differs, 5 CI failed (at the final gate also: no longer complete and green), 6 timeout,
7 merge failed, 8 blocked, 9 the Codex gate gave neither 0 nor 5: a review running or not finished since its latest trigger (its 3, after
the 20-minute wait or at the final gate), a review that ended other than Completed or a summary last edited by another account (its
4), a gate that failed or is missing; or a 5 without an accepted `GPT_VERDICT` (#975 P3-7 at 761810d7: the header named only some of
these). `nas_land.sh`: 2 as above, 3 head moved, 4 `update-branch` refused or the change differs after it or at the final gate, 5 CI
failing (also at the final gate), 6 timeout, 7 merge failed, 8 blocked by policy, 9 as above, but a 5 proceeds, and a 3 before the
validation stops too, 10 the merge onto current `origin/main` does not merge cleanly, fails `scripts/validate.py` or fails one of the
shard-0 currency checks whose script it holds (CC correction #176), 13 origin/main moved
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
`codex_gate.py` byte for byte. Expanding the three expressions to the CC host's paths gave the live copies byte for byte (their
digests are withheld, below).
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
at nas:234, both scripts read `trading-cc-read` from the combined status, every page of it (above). The live copies were
changed at 2026-10-11T05:03:28Z (the CC's patch that took the status-gate failure line); the "Live copy" columns give their line
counts as read at 2026-10-11T13:59Z, which replaced the record of the CC's 03:37Z patch (#975 P3-2). The "Here" column is each file
as committed: its sha256 and line count.

On 2026-10-12 the CC patched the live copies twice more, and both patches are ported here (file times 00:10:46Z and 00:37:48Z; the
copies they replaced are the ones of the "Live copy" column): CC correction #176 in `nas_land.sh` (the currency checks, above) and
`SQUASH_BODY_FILE` in both scripts (above). The port follows this copy's structure in three ways. The live copies print the last 300
bytes of a failing check's output; here it stays in the validation's 0600 file, as `validate.py`'s does (#975 P2-C). The live copies
check `SQUASH_BODY_FILE` before the group that is parsed whole and accept any non-empty path; here the check is the group's first
statement after the arguments, still before the lock and any call, and also refuses a directory, an unreadable file and `-`. The live
copies keep the validation's output beside the worktree and a failed merge's under the CC's tools directory; here both go to
`${TMPDIR:-/tmp}`, as before. The CC's regression for #176 (`test_merge_validate_currency.sh` in its tools directory, which cuts
`merge_validate` out of a script and runs it on a scratch repository whose merge fails `final_stack.py --check`) passes on this
`merge_validate`. The live copies should again be replaced whole.

#1027 (Astra's P1 at d6be1b02) adds to both scripts the squash body's snapshot and publication scan (above) and one file the live copies
do not have, `squash_body_scan.py`, which goes beside them in the CC's tools directory as `codex_gate.py` does. The scan finds
`scripts/validate.py` in the clone `LANDING_NAS_REPO` names (the CC's checkout by default) and the names list at its default path under
the coordination tree, so the replaced copies need no further host path; a copy run from another place sets `LANDING_BODY_SCAN`,
`LANDING_SCANNER` or `LANDING_NAMES_FILE`. The table below gives the digests of the three files that have live copies; the scanner's
is not recorded.

No digest of a live copy is recorded here (CC correction #161; the CC's ruling of 2026-10-12 withheld the ones the table held before):
the live copies hold the CC host's paths, and since everything else in them is public, a digest of their bytes would let anyone
confirm a guessed path. The live `codex_gate.py` holds no host path; its digest is withheld by the same rule, so the only digests in
this section are the repository copies' (a test checks that).

| File | Before correction #136 | Live copy, after #148 | Live copy, since 2026-10-11T05:03:28Z | Here |
| --- | --- | --- | --- | --- |
| `uet_land.sh` | withheld (CC #161: a digest of a file whose only non-public bytes are host paths confirms a guessed path) (115 lines) | withheld (CC #161: a digest of a file whose only non-public bytes are host paths confirms a guessed path) (232 lines) | withheld (CC #161: a digest of a file whose only non-public bytes are host paths confirms a guessed path) (233 lines) | `74c570a82c15c5f987528ff7b36f1d0f53d93475b113e6c0922bb0ff928fdfba` (447 lines) |
| `nas_land.sh` | withheld (CC #161: a digest of a file whose only non-public bytes are host paths confirms a guessed path) (135 lines) | withheld (CC #161: a digest of a file whose only non-public bytes are host paths confirms a guessed path) (243 lines) | withheld (CC #161: a digest of a file whose only non-public bytes are host paths confirms a guessed path) (246 lines) | `9dc4fd51c4b31d08a2cd7507197651076ed3c02671c4254d3191fa0a795e4808` (525 lines) |
| `codex_gate.py` | (unchanged) | withheld (CC #161: a digest of a file whose only non-public bytes are host paths confirms a guessed path) (108 lines) | the same | `e2132ab71b6e55fea8922b9c5b0b8c17bde87b1d37f11bf384b785bef6f96b6a` (226 lines) |

Corrections the scripts carry: #118 (every gate before the merge, in order), #121 (a verdict file that states a landing gate needs
a receipt), #122 and #123 (a Codex review must have finished; uet#40 and uet#47 merged while one was running), #136
(verdict and record acceptance, change identity and the CI line: the three loose decision points the shared
`# >>> land-gate-fns` block replaced), the head-following of 2026-10-10 (uet#58: an update-branch rebase does not reach every API view at
once, so a head that moves during CI and carries the read head's change is followed, at most three times), #148 (the author address)
and #975's P2-3 (the CI allow-list), P2-2 (no text from `gh` or its API is printed: a failed merge, a failing status, every other `gh`
call), the gate error (P2: exit 4 and one fixed line, no traceback), the commit-status allow-list (P3) and P2-1 (the privacy scan
checks every prohibited identity), round 3 (above: the completion bound to the latest request, the gates read again before the merge,
typed values, no local diagnostics, the base re-read) and round 4 (above: the lock, the final gate, one read per file, the gate's
snapshot), and the CC's patches of 2026-10-12: #176 (the merge's shard-0 currency checks, `nas_land.sh`) and the squash body
(`SQUASH_BODY_FILE`, both), whose publication scan is #1027's. The block is identical in both scripts, apart from `lg_ci_state`, which only `uet_land.sh` has.

## Known gaps, left as they were

The files began as the live copies with host literals replaced and now also differ from them where the provenance section above says
so (the merge-failure line, the gate's exit 4, the commit-status allow-list, the dropped stderr, the review-thread count and rounds 3
and 4). These stay until a change with its own tests fixes them:

- `U` and `G` are expanded unquoted: a clone path with whitespace breaks both scripts.
- `nas_land.sh`'s validation merge needs a git identity (above). Its header now lists exit 4.
- The merge runs shard 0's Python `--check` steps, not all of shard 0: the shard's validators before them (such as
  `scripts/validate_catalogs.py` and `scripts/validate_convergence.py`) and its checks that are not one Python command (the example
  workflows' `sha256sum --check`, the contract suites, zizmor and actionlint) do not run on the merge, so a merge that fails only one of
  them still lands. Each check runs on the merge as the worktree holds it, uncommitted, so a check that read the committed tree would
  read `main`; none of the eight does (they read files, and `gap_crosswalk.py` a fixed revision).
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
- The squash body scan is conservative (#1027), and fails closed where it is unsure. Run on the last 600 commit messages of `main` at
  3a8a8461ee60 (2026-10-12; counts only), it refuses 8: 0 names, 5 addresses, 3 home paths. The 5 addresses are 3 at a mail provider and 2
  at a reserved test domain. It warns, without refusing, about 26 messages (66 occurrences) that name the host's own name; it passes the
  2 that carry a systemd unit instance, the 1 that carries the vendor co-author address and the 402 that carry the vendor `noreply`
  trailer. (Before the CC's three allowances of 2026-10-12 it refused 37: 26 names, 8 addresses, 3 home paths.) A refused body is rewritten,
  or the names file edited; the scan has no other allow-list. It decodes percent-escapes and not hex, base64, `\u`, HTML entities or
  doubly encoded text, finds a WSL UNC home path but not other UNC shares, and reads the names file's last `LANDING_PROHIBITED_NAMES`
  assignment only (the tests' scan, by contrast, also finds a name's hex and base64 spellings).
- The history residual (#1027): the 3 messages with a home path and the 3 with an address at a mail provider counted above already sit in
  `main`'s commit history (the whole history at that base, 1229 messages, holds 5 and 4). History is immutable, as for CC correction #177,
  and this change rewrites none of it. Whether any of them is identity-bearing is a follow-up.
- `validate.py --scan-file` runs only where Betterleaks is installed at `host_name_scan.py`'s pin and `powershell.exe` answers on WSL; the
  CC's host has both. Elsewhere, and in CI, the landing with a `SQUASH_BODY_FILE` stops with exit 2 (the tests for the real scan skip
  there). `NATIVE_AGENT_HOST_NAMES_JSON` set in the CC's shell makes `validate.py` report synthetic sources, which the scripts refuse.
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
of it. The CC's patches of 2026-10-12 add, each failing at 86fa3844: the checks `merge_validate` names are exactly the shard-0 steps of
`validate.yml` that run a Python script with `--check`, as those steps run them and in their order, a folded `run: >-` step included
(at 86fa3844 it named none; the reader is also run on a synthetic workflow); the provenance section carries a 64-hex digest only in
its "Here" column (CC #161; at 86fa3844 seven digests of live copies stood beside them); a merge that passes `validate.py` and fails
`scripts/final_stack.py --check` stops with 10 naming that check, the checks after it not run and its output only in the 0600 file (it
merged at 86fa3844); a check runs only when its script is in the merge, and a landing whose checks pass merges; a `SQUASH_BODY_FILE`
that is missing, empty, a directory, `-` or unreadable stops both scripts with 2 before any call, printing no path (each landed at
86fa3844); and a body file reaches the merge as one `--body-file` argument (the merge had none at 86fa3844; since #1027 it is the snapshot, in a
`TMPDIR` whose name may have a space), while an empty value adds none. The fake `python3` answers a currency check itself, so it never takes one of the gate's answers, and
the fake `gh` can write the merge's arguments NUL-separated. The fake `gh` serves page 1 of the statuses list as the first `per_page`
statuses and builds the combined status from it as GitHub gave it when measured: each context once with its newest status, in pages of
`per_page` contexts. It is offline, needs `jq`, and is Linux-only. A script edit that moves a decision site fails the module instead of
leaving it untested.

**The squash body scan's tests (#1027).** Each fails at d6be1b02, where a body with a home path, a name, an address or a token shape landed
(exit 0, one merge call). Both scripts refuse, with exit 2 and the fixed line, before any `gh` or `git` call and with no merge: a body
holding a home path of each form (`/home/<user>`, `/Users/<user>`, a Windows profile path with either slash, the WSL mount,
`\\wsl.localhost\<distro>\home\<user>` and the older `\\wsl$\...` with one or doubled backslashes, the dash-encoded and graph-id forms, and a
percent-encoded one), a name of a synthetic names file (bare, upper case, as an identifier, in a path, percent-encoded), an address that
is not a no-reply one (plain, mixed case, in a trailer, percent-encoded, and four look-alikes) or a token shape (seven kinds). They stop
the same way when `validate.py`, the scanner or the names file is missing, unreadable or naming nobody, when the scanner exits 2, prints
nothing or another line, has a syntax error or refuses, and for every answer of `validate.py --scan-file` but its clean line. The
valid-body control (GitHub's no-reply form, the vendor `noreply` trailer, a synthetic name inside a longer word, the placeholder account's
home path) lands with exit 0 and one merge call; the merge reads the body's bytes from a mode-0600 snapshot in a `TMPDIR` whose name has a
space, not from the caller's file, both scans having run on that one snapshot first. A file rewritten after the scan does not reach the
merge; the snapshot exists during the run and is gone after exits 0, 3 and 7 and after SIGTERM and SIGHUP; and the defaults of
`LANDING_SCANNER` and `LANDING_NAMES_FILE` are the clone's `validate.py` and the file under the coordination tree. Where Betterleaks is
installed at the pin, the real `validate.py --scan-file` passes the clean body and refuses one that names the account running the tests.
The CC's three allowances of 2026-10-12 have their own tests: a body that names the host lands with the count printed and the name not,
while a body that also holds another listed name is refused; systemd unit instances land, and their look-alikes (a domain, a type outside
the ruling, a local part no unit has) and a provider address, the control, are refused; the vendor co-author address lands, in any letter
case and with the vendor's `noreply` form, while another local part at the vendor's domain, the vendor's local part at another domain and
a provider address are refused; and a scanner that prints a warning count that is not a number stops the landing.
`squash_body_scan.py` is also tested by itself: the names file's formats and that no line of it runs, the address rule's controls, the
unit and vendor rules, the host name, a name as a whole token, and its one output line.

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
| The newest `trading-cc-read` status (B1 at 5b8ba3b2) | `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…` (the local upstream mirror at that commit, the same bytes); `jqlang/jq@jq-1.8.1:src/jv_aux.c`, `9b510dff29fede9f5e9d6a61d59b5d0d69419fc74a2bf684331295d0200829e8` | `api.github.com.json:55724` "Statuses are returned in reverse chronological order. The first status in the list will be the latest one", so `tcc_read_gate` took `first` (until Codex's P1 at nas:234, below); `jv_aux.c:669-674` `sort_cmp` breaks ties by input index, so `sort_by(.updated_at)\|last` kept the older of two statuses with the same `updated_at` (measured with jq 1.8.1) |
| A check run's recency is its completion (Astra's follow-up 1 at 5b8ba3b2) | `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…` (the local upstream mirror at that commit) | `:55504-55514` the list-for-ref `filter` parameter: "Filters check runs by their `completed_at` timestamp. `latest` returns the most recent check runs" (default `latest`), so `nas_checks` asks for `filter=latest`, and until A1 (below) it judged a name on the completed run with the greatest `completed_at`; `:146097-146107` `check-run.started_at` and `completed_at` are both `"nullable": true`, so a completed run without `completed_at` counts as incomplete (a tie with two conclusions did too until A1) |
| Where an edit is, which the change identity ignores (Codex F1 at 5b8ba3b2, declared) | `git/git@v2.53.0:Documentation/git-patch-id.adoc`, `e835ca2a7a11b54e3db93221466928c887ef9529a9b34b475d746888e43af410` (the local upstream mirror at `67ad4214`) | `:17-18` a patch ID is "a sum of SHA-1 of the file diffs associated with a patch, with line numbers ignored" |
| A failing run stands unless a run of its name started and completed after it (A1, the CC's Claude micro at 3e6e7e46) | `jqlang/jq@jq-1.8.1:docs/content/manual/v1.8/manual.yml`, `e0eb9a08…` (the local upstream mirror at `jq-1.8.1`, read on 2026-10-11) | `:1544-1552` jq orders `null` before every other value and strings by code point, and `:2425-2433` `>` uses that order, so a run whose `started_at` or `completed_at` is null is never later than another run (the program also gives such a failing run no superseder); `:1334-1347` `any(generator; condition)`, `:1579-1590` `group_by`. The times REST gives order as strings: all 2,072 runs on the 70 heads replayed on 2026-10-11 have both in the form `YYYY-MM-DDTHH:MM:SSZ`, none with a fraction or a null (112 of them, all skipped, completed before they started; the rule compares a run's times only with another run's) |
| Every page of check runs (Codex P2 at nas:289) | `cli/cli@v2.102.0` (the local upstream mirror at `fc4b137c`): `pkg/cmd/api/api.go`, `030eda84…`; `pkg/cmd/api/pagination.go`, `0565f3040ed1843875732e5df5dbc50fdbc90bb3b45685eabfd83c133b4c79b0`; `go.mod`, `115bc54638dc4fa5a72da79d9f87fca699ee5b1fc7e21ea9314a517fb18fb40b`; `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…`; `github/docs@be38ec5d78e24172587e61b3c6ff40ace1865c71:content/rest/using-the-rest-api/using-pagination-in-the-rest-api.md`, `418bdf281d74a89c7dabedc4af53a6f7b286f2416e7670d9cc71453db08d8640` (the local upstream mirrors, read on 2026-10-11) | `api.github.com.json:55518`, `:55521` the list-for-ref endpoint takes `per_page` and `page`, `:344577-344585` `per_page` is "(max 100)", `:344616-344624` `page`, `:55563-55564` its reply carries a `Link` header, `:347322-347327` whose example names the next page with `rel="next"`; the docs, `:22` "You can use the `link` header from the response to request additional pages of data", `:28` the header is omitted "if all results fit on a single page", `:49` "The URL for the next page is followed by `rel="next"`"; `api.go:358-360` `--paginate` keeps a `per_page` the path has (`pagination.go:94-110`), `:431-470` asks for page after page while `pagination.go:17-24` finds `rel="next"`, `:362-371` with `--slurp` writes every page into one JSON array, `:260-273` `--slurp` needs `--paginate` and refuses `--jq`, so `nas_checks` runs jq itself on the array (gh's own `--jq` is go-gh's, `api.go:28`, on gojq, `go.mod:21`, `:141`), and `:546`, `:553-565` the body of a failed page is still written and gh exits non-zero, so its exit code is checked before jq reads. Measured on 2026-10-11 at `26f551b1` (43 runs): `per_page=10` gave 5 pages of 10, 10, 10, 10 and 3 runs, `total_count` 43 on each, the same 43 ids as one `per_page=100` page, the next link `filter=latest&per_page=10&page=2`, and the same four counts |
| The newest status of each context, on every page (Codex P1 at nas:234) | `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…`; `github/docs@be38ec5d78e24172587e61b3c6ff40ace1865c71:src/rest/data/fpt-2022-11-28/commits.json`, `57f0a021883f869390a022e41bdbe77267d5ebbdbf59849d2891380f5e363247` (the local upstream mirrors, read on 2026-10-11) | `api.github.com.json:55664-55667` `GET /repos/{owner}/{repo}/commits/{ref}/status`, "a combined view of commit statuses for a given ref", whose `state` is success "if the latest status for all contexts is `success`"; `:55687`, `:55690` it takes `per_page` and `page`; `:55694-55699` its reply is a `combined-commit-status`, `:148666-148707`, with `statuses` of `simple-commit-status` (`:148606`: `context`, `state` and a nullable `description`) and `total_count`; the docs' REST data, `commits.json:9530`, give the same text and parameters. Neither says the entries are one per context. Measured on 2026-10-11, read only: on 8 public heads (`kubernetes/kubernetes`, 2 to 35 statuses in 2 to 15 contexts) and on the 12 of our 80 heads that have statuses, every context appeared once, as the list's first (newest) status of it, and `total_count` was the number of contexts; with `per_page=5`, the first page of each of the 5 heads with 13 to 15 contexts carried a `Link` `rel="next"`, and `--paginate --slurp` gave the same entries as one page of 100 on all 8; on our 80 heads the combined read and the 3e6e7e46 read gave the same `trading-cc-read` state and description |
| The connector's own layout and footer | `tests/fixtures/landing/codex-summary-comment.json`, `3918a25359d64ea4b2bcf31ec9ac9d92ff681270c072da6af625575eab720792` (the summary comment of nas#975 with its four revisions, masked by `mask_packet.py`'s rule with nothing to replace; the body's sha256 is `1236fe482740fa1ccdaac6d50d4e1e77f6a6e961d64e8dd5377a4923a6f8d0dc`) | a row of four cells (the review kind "📝 Code Review", the status "✅ Completed" with its time, the commit 761810d in backticks, the trigger kind "Manual request"), the Running form "🔄 Running since" with its time, the newest revision equal to the body, every editor the Bot `chatgpt-codex-connector`, and the footer "Codex reacts with 👀 while any review is running, comments if it has suggestions, and reacts with 👍 once all reviews finish with no findings" |

The CC's patches of 2026-10-12 (#176 and the squash body). Read on 2026-10-12 from the local upstream mirrors at the pins given;
installed: `gh` 2.102.0.

| Mechanism | Source at the pin, sha256 | Lines read and what they say |
| --- | --- | --- |
| How `gh` takes the body file | `cli/cli@v2.102.0` (the local upstream mirror at `fc4b137c`): `pkg/cmd/pr/merge/merge.go`, `ca3849b4…`; `pkg/cmd/pr/merge/http.go`, `17eb5418a1771692864b8f7476947f088252ccde0037d089c9faf441ff7c8877`; `pkg/cmdutil/file_input.go`, `94076f6234180f85f2a555a5733e024146ea2c0cac54af19c86c72b015252828` | `merge.go:177` `--body-file` (`-F`), "Read body text from `file` (use "-" to read from standard input)", `:176` `--body`; `:138-144` the two are mutually exclusive; `:146-153` the file is read when the command starts and sets `BodySet`; `:292-293` the body goes into the merge payload; `http.go:72-75` a set body becomes the mutation's `CommitBody`, an empty one included; `file_input.go:8-16` `-` reads standard input, any other name the file |
| The merge's body field | the GraphQL schema, `3ed09565…` | `schema.docs.graphql:26080-26082` `MergePullRequestInput.commitBody: String`, "Commit body to use for the merge commit; if omitted, a default message will be used" |
| The squash default of both repositories | `github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json`, `da3d22e4…`; `github/docs@be38ec5d78e24172587e61b3c6ff40ace1865c71`: `content/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/configuring-commit-squashing-for-pull-requests.md`, `de95ca812994fdf9276ab499209bff15fc11e80d6740c78bdf96a30148ebb0ce`; `content/pull-requests/reference/pull-request-merges.md`, `731e80f541245c27b499b28de6760b3228d1bb7e924c4f8047a01a42aa238d81` | `api.github.com.json:138199-138208` `full-repository.squash_merge_commit_message`, one of `PR_BODY`, `COMMIT_MESSAGES` and `BLANK`, "`COMMIT_MESSAGES` - default to the branch's commit messages" (`:40076` the same setting in `repos/update`); `configuring-commit-squashing-for-pull-requests.md:23-26` the default message and its formats; `pull-request-merges.md:45-49` the default squash message comes from the repository settings and can be edited at the merge. Both repositories read `COMMIT_MESSAGES` at 2026-10-12T02:23:46Z |
| Why the merge is validated here, and what would do it on GitHub's side | `github/docs@be38ec5d78e24172587e61b3c6ff40ace1865c71`: `data/reusables/pull_requests/merge-queue-overview.md`, `00008b55054578c947f05f8b17a6fdfdb809f826f511346c53c804038b5023da`; `content/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue.md`, `3ccb7ceb787e04077634c15ff7b5cf63641f20b0245341dcf31d6ac3511e382e`; `data/reusables/gated-features/merge-queue.md`, `a2e204a6f2c4f6bbc91fbc08a96d5c9f71485ba073dc1119a41e8efbc35a7290` | `merge-queue-overview.md:1` a merge queue ensures "the branch is never broken by incompatible changes", `:3` the same benefits as **Require branches to be up to date before merging**, `:7` it checks a pull request's changes "applied to the latest version of the target branch and any pull requests already in the queue"; `managing-a-merge-queue.md:84` the queue's temporary branches group a pull request with the latest base and the pull requests ahead of it; `gated-features/merge-queue.md:2` merge queues are available in organization-owned repositories only. The rules of both `main` branches (`strict_required_status_checks_policy`: `true` for the trading repository, `false` here) were read at 2026-10-12T02:23:46Z |
| How `gh` takes the body file, for the snapshot (#1027) | the three `cli/cli` files above, read on 2026-10-12 through the GitHub contents API at `fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd` (the commit of `v2.102.0`): the local mirror, a blobless clone at `ec5b5120`, holds no tag and not that commit; the digests equal the ones above | `merge.go:146-153` is in the command's `RunE`, so `gh` reads the file when `gh pr merge` starts, however long before that the landing checked it; `:292-293` and `http.go:72-75` send what it read. A scan of the caller's file is therefore a scan of other bytes than `gh` may read, which is why the scripts scan a snapshot and give `gh` the snapshot |
| A WSL UNC home path (#1027) | `MicrosoftDocs/WSL@a1473a69d10c` (HEAD on 2026-10-12, read through the contents API): `WSL/release-notes.md`, `7c8890227146c81681f8d743ad9ff8a1675310c52c22d7e54f4b4c08c89a57dd`; `WSL/wsl-config.md`, `2f84606529d3486b0b62dadea3afcbcb26cbccdd20ceb6cc0e4470b1520eee74` | `release-notes.md:24` "Switch the \\wsl prefix to \\wsl.localhost to avoid issues when there is a machine on the network named "wsl". \\wsl$ will continue to work."; `wsl-config.md:162` the path of a distribution's file is `\\wsl.localhost\<distro>\etc\wsl.conf` (the page's example names a stock distribution). So a home directory is `\\wsl.localhost\<distro>\home\<user>` or `\\wsl$\<distro>\home\<user>`. `scripts/validate.py:38-61` (`PRIVATE_CONTENT`) matches neither (measured 2026-10-12: no finding for either, one for the same path with forward slashes) |
| The no-reply addresses (#1027) | `github/docs@be38ec5d78e24172587e61b3c6ff40ace1865c71:content/account-and-profile/reference/email-addresses-reference.md`, `fbbf1c5f700d977f8672462859621f9412e65531a57790fa779e191a4d1c0949` | `:47` an account created after July 18, 2017 has `ID+USERNAME@users.noreply.github.com`, `:48` an older one that kept its address private `USERNAME@users.noreply.github.com`. The vendor trailer `Co-Authored-By: ... <noreply@anthropic.com>` is this repository's convention, not GitHub's: 402 of the last 600 commit messages of `main` at 3a8a8461ee60 carry it (measured 2026-10-12) |
| The address shape and a name's boundary (#1027) | this repository, `scripts/host_name_scan.py` at the base | `:164` the native `private-email` rule (RFC 5322 atext characters, `@`, letters, digits, dots and hyphens, a TLD of two letters or more) that the scanner's email check uses; `:144-150` `boundary_filter` drops a match with a letter or digit just before or after it, which is the whole-token rule of the name check; `scripts/validate.py:316-345` `scan_file_for_private_content` reads a file as UTF-8, else Latin-1, as `squash_body_scan.py` does, and `:737-780` is the `--scan-file` mode (exit 0 clean, 1 findings, 2 unavailable) |
| An `EXIT` trap on a terminating signal (#1027) | `bash.git@bash-5.3:doc/bashref.texi` (git.savannah.gnu.org, `plain/doc/bashref.texi?h=bash-5.3`, read 2026-10-12), `f3d37d57a1061e24d266051de9bd47ffa43dc86584afea11576c535ad2be32d5`; installed: bash 5.3.9 | `:4777-4778` "If a sigspec is 0 or EXIT, action is executed when the shell exits", `:4358` "Any trap on EXIT is executed before the shell terminates". The manual does not say a signal counts, so it was measured: a script that made a file and set the trap, killed with SIGTERM and with SIGHUP while it waited on a child, ran the trap each time (the file was gone) and then died of the signal (a Python parent sees `-15` and `-1`); `test_the_snapshot_is_removed_when_a_signal_ends_the_landing` repeats it on both scripts |
| Isolated mode (#1027) | `python/cpython@v3.13.16:Doc/using/cmdline.rst`, `ef999234d959b0a1d9a96a7f1f047170a77cd89fee9ffaa2a3db1af412a8ef0b` (the local upstream mirror at `cbc944f4bc59`) | `:308-316` `-I` "also implies -E, -P and -s", and "sys.path contains neither the script's directory nor the user's site-packages directory"; `:254-257` `-B`; `:392-395` `-s`. Measured 2026-10-12: `python3 -I scripts/validate.py --scan-file <file>` exits 2 (`"status": "error"`: `host_name_scan` is not importable), `python3 -E -s -B` exits 0 |
| A systemd unit instance is no address (#1027) | `systemd/systemd@c7a8e871de3427cf654d9a608dc58663874197bb` (the local upstream mirror, HEAD on 2026-10-12): `man/systemd.unit.xml`, `520150b19c123762db6405bd68442bb72c8a5ea6e56cd383b99e9774e1c874b4` | `:121-124` the unit name prefix is ASCII letters, digits, `:`, `-`, `_`, `.` and `\`; `:125-128` the type suffix is one of `.service`, `.socket`, `.device`, `.mount`, `.automount`, `.swap`, `.target`, `.path`, `.timer`, `.slice` or `.scope` (the CC's ruling names six); `:130-135` an instance name is inserted between the `@` and the type suffix. So `getty@tty1.service` has the shape of an address (an `@`, a dot, a suffix of two letters or more) and is a unit; 2 of the last 600 commit messages of `main` carry one (measured 2026-10-12) |
| Vendor co-author trailer addresses (#1027) | `openai/codex` (the local upstream mirror): the commit `db22c91e61cc80defa5bbafc22bd8a8c7672e5e1` (2026-05-05); `openai/codex@092d3acd6bec`, `codex-rs/ext/git-attribution/src/world_state.rs`, `5d202fa01fcc99d301dd5e330065b2100168819ef5d4c625e7a3b963940f7490` | the message of `db22c91e61`, line 38, is `Co-authored-by: Codex <codex@openai.com>`: the vendor's own repository carries that form, which is why it is on the list. The vendor's current attribution code writes `Co-authored-by: Codex <noreply@openai.com>` (`world_state.rs:11` and `:19`), which passes as a no-reply address. No other primary source holds the older form: the five `openai/*` mirrors at their HEADs and the 36 Codex pages of developers.openai.com hold no `codex@openai.com` (measured 2026-10-12). GitHub code search finds the exact trailer in 988 files (a count, not a source). `main`'s history holds it once, in four lines of one commit message |
| The host's own name (#1027) | `python/cpython@v3.13.16:Doc/library/socket.rst`, `fa1ad5f48c9a9d9317a9502aacb068b73dbbdefb5894e61a59ae19838cf07bfe` (the local upstream mirror); this repository, `scripts/host_name_scan.py` at the base | `socket.rst:988-991` `socket.gethostname()` returns "the hostname of the machine where the Python interpreter is currently executing" (measured equal to `uname -n` on the CC's host); `host_name_scan.py:65-68` the repository's own scan drops the hostname source when it equals `WSL_DISTRO_NAME`: "WSL can expose its public distro/project label as the Linux hostname. Exclude that hostname source only; coincident private sources remain." |
