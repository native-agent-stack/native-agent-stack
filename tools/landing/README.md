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
| `LANDING_PROHIBITED_NAMES` | none | the tests only | comma-separated identities that must not appear in any form under `tools/landing` (see Tests) |

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
`uet_land.sh` fails a commit status unless its state is SUCCESS, PENDING or EXPECTED (#975 P3; one more comment line). The review
of 754a194f (the GPT micro, CHANGES_REQUESTED) led to a third round, also made here: the status-gate failure line is the one the
CC's live copies already carry, and the rest is new to them: every other `gh` call drops its stderr, `uet_land.sh` prints the count
of unresolved review threads as a number or `unknown`, and each script has two more header comment lines (#975 P2-2, above). The
tests also scan for every prohibited identity (#975 P2-1, below). The "Here" column is each file as committed: its sha256 and line
count.

| File | Before correction #136 | Live copy, after #148 | Live copy, after #975 P2 | Here |
| --- | --- | --- | --- | --- |
| `uet_land.sh` | `b794e3a46772c0a598dff9eee972ad449e5d63f0c81b60b9db1d5cb4944747bb` (115 lines) | `301fb5b07274b28fde0f2061356bf9682883eca352c8bcb7a3119e8934920c7d` (232 lines) | `1bc1f53b3ddd7563a6d3a0ea1a4db296767df64197c00b1bc0ff6e23c528476c` (233 lines) | `acfadc93870babd1e9fa3f4d6b6733e701ea8a6d3d5ce52059b9fad71105501e` (237 lines) |
| `nas_land.sh` | `2fefe070b95229de3dcad14052cf5c031b70c202bf4a34f4452e6e0cb5832936` (135 lines) | `96144670bc301036604fc39e57e3ab4e4a2e43a6b9d6b8b645ef7b02482f4017` (243 lines) | `287f2e7e162a0dd8df28803c72eeb96591a2d936c513d981bcac24512139e0bd` (246 lines) | `3d119f50b2bb063fce23e1e81438458e1c3538f87874d7f4346549a1cbed6b4f` (248 lines) |
| `codex_gate.py` | (unchanged) | `31524d2871cde79ecb2c5b9bc56b6175ce9fafab9ad4d2e2e3eb3594e1cb2422` (108 lines) | the same | `cc96f69b411b76652b1d024988d3bb374444a40dca6f175dd6559aa4de9e7a33` (114 lines) |

Corrections the scripts carry: #118 (every gate before the merge, in order), #121 (a verdict file that states a landing gate needs
a receipt), #122 and #123 (a Codex review must have finished; uet#40 and uet#47 merged while one was running), #136
(verdict and record acceptance, change identity and the CI line: the three loose decision points the shared
`# >>> land-gate-fns` block replaced), the head-following of 2026-10-10 (uet#58: an update-branch rebase does not reach every API view at
once, so a head that moves during CI and carries the read head's change is followed, at most three times), #148 (the author address)
and #975's P2-3 (the CI allow-list), P2-2 (no text from `gh` or its API is printed: a failed merge, a failing status, every other `gh`
call), the gate error (P2: exit 4 and one fixed line, no traceback), the commit-status allow-list (P3) and P2-1 (the privacy scan
checks every prohibited identity). The block is identical in both scripts, apart from `lg_ci_state`, which only `uet_land.sh` has.

## Known gaps, left as they were

The files began as the live copies with host literals replaced and now also differ from them where the provenance section above says
so (the merge-failure line, the gate's exit 4, the commit-status allow-list, the dropped stderr and the review-thread count). These
stay until a change with its own tests fixes them:

- `U` and `G` are expanded unquoted: a clone path with whitespace breaks both scripts.
- `nas_land.sh`'s header leaves out exit code 4, and its validation merge needs a git identity (above).
- Only `gh` is covered by the rule that nothing it returned is printed: the `git` commands (`fetch`, `cat-file`, `worktree`) still
  inherit stderr, and `scripts/validate.py`'s last 300 bytes are printed when the validation merge fails (exit 10).
- A call whose failure never stopped a landing still does not: an unreadable draft flag (both scripts) leaves a draft unmarked, and
  an unreadable `mergeStateStatus` (`nas_land.sh`) skips the BEHIND update and the BLOCKED stop, so the merge call itself is the check
  (exit 7 when GitHub refuses it).
- A running account named `user` fails the privacy scan on the hyphenated adjective in the second line of `uet_land.sh`: a generic
  name may stand as a bare word only, and joined to other text by a hyphen it is an identifier form (below). No other generic name
  is reported on these files.

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
It is offline, needs `jq`, and is Linux-only. A script edit that moves a decision site fails the module instead of leaving it
untested.

**The privacy scan (#975 P2-1).** Two kinds of identity are scanned for, each in these forms: the bare word, an identifier or path
form (joined to other text by `-`, `_`, `.`, `/`, `\`, `@`, `:`, `~` or `=`, as in `project-<name>-tools` or `<name>@host`), a
percent-encoded form, hex digits and base64 at each alignment. An explicitly prohibited identity is a name in
`LANDING_PROHIBITED_NAMES` (comma-separated, read when the tests run, so no real name is written into the repository; not
`NATIVE_AGENT_HOST_NAMES_JSON`, whose setting replaces the host-name scanner's own sources). It is scanned in every form, whatever its
length and even when it is an ordinary word. The account that runs the tests is scanned the same way, with one exception: when it is a
generic CI or container account (`GENERIC_ACCOUNTS` in the test module, such as `runner` on GitHub-hosted runners), its bare word may
stand in prose, because such names are ordinary words; its identifier, path and encoded forms are still reported. A home path is
reported for every account. No name is skipped for its length (before, one under four characters was, so a real account `sam` was
never checked). The repository assertion itself is run on a scratch tree with a mocked account lookup for a three-character account,
for a generic account in each form, and for a prohibited name that is also a generic word.

## Upstream sources for the #975 corrections

Each source was fetched on 2026-10-11 with `curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/<tag>/<path>` and read at the
lines given (the sha256 is that of the fetched file). Installed: `gh` 2.102.0, `mktemp` from uutils coreutils 0.10.0, Python 3.13.16.
The GNU `mktemp` of the CI runners is not cited.

| Mechanism | Source at the pin, sha256 | Lines read and what they say |
| --- | --- | --- |
| Where `gh` prints a command's error (P2-2) | `cli/cli@v2.102.0:internal/ghcmd/cmd.go`, `4ce5cdb31c15dad95e0a7e18e6d0f0c49a07603cea0d5f4e08bc51f530a5d7e1` | `:69` `stderr := ioStreams.ErrOut`, `:214` `printError(stderr, …)`, `:285` `fmt.Fprintln(out, err)`: the error of a failed command goes to stderr |
| `gh api` on an error response (P2-2) | `cli/cli@v2.102.0:pkg/cmd/api/api.go`, `030eda84dcfdb52e3bba2cadfc0243a7b47d3098b64f8c12c665550733d72ca1` | `:347` the body writer is `ContentOut` (stdout); `:492-497` and `:656-686` a JSON error goes through `parseErrorResponse`, which returns a copy of the raw body and `<message> (HTTP <status>)`; `:509` `--jq` runs only when `serverError == ""`, so `:546` copies the raw body to stdout; `:553-557` prints `gh: <message>` to stderr; `:564` returns `SilentError` (non-zero exit) |
| `mktemp` prints the path it made and creates the file with mode 0600 (P2-2) | `uutils/coreutils@0.10.0:src/uu/mktemp/src/mktemp.rs`, `04d1e28080aaa4f19f9113dfc3da97541158483a220efda9a52275fed54e3b98`; `Cargo.lock`, `0833b527913f974ace9dff19e4dd8640e73da2cab6967c8dfca5e7dc9889abc9`; `Stebalien/tempfile@v3.27.0:src/lib.rs`, `d182721b62c126916b73bb4865ced5d3637bd1a4a77d27ea9e9708973e5f9493`, `src/file/mod.rs`, `b6752b11a575021eeab87cb8b5b6914aaff86ad8d49a9678a8f4c95b5a21ef81`, `src/file/imp/unix.rs`, `cc39f94cb6cb87b36cf7603a75429d64ecc4ad1a2076a765e5aba2b11771d0f7` | `mktemp.rs:438` `println_verbatim(res?)` prints the created path to stdout, which `$(mktemp …)` captures; `:581-582` "The permissions of the file are set to `u+rw`", `:588-591` `make_temp_file` calls `Builder::tempfile_in(dir)` and sets no permissions (`:557-560` sets `0o700` for directories only); `Cargo.lock:2983-2984` pins `tempfile` 3.27.0; in `tempfile`, `lib.rs:234` the builder's `permissions` is `None`, `:555-568` `tempfile_in` passes it on, `file/mod.rs:1111-1116` to `imp::create_named`, and `imp/unix.rs:18` `create_new(true)` (exclusive create), `:23` `mode(permissions.map(\|p\| p.mode()).unwrap_or(0o600))` (mode 0600, narrowed by the umask); `lib.rs:64` "Temporary _files_ created with this library are private by default" |
| The running account's name (P2-1) | `python/cpython@v3.13.16:Doc/library/pwd.rst`, `0f4b8b370a7f0d2e8ff93f2e224b2c7e54f64bfb808e5f50242f83b725e950a8`; `Modules/pwdmodule.c`, `11841fe008240d3ffb955d0c700da1d96c07f18679ab09b93b16c3c81707a261`; `Lib/getpass.py`, `e52ea266b79f3b4a83388093f387540ff36d51ff306dcbb6ca6de081cd28e718` | `pwd.rst:52-54` `getpwuid(uid)` returns the entry for a numeric user ID and `:36-37` raises `KeyError` when it cannot be found; `pwdmodule.c:195-196` `getpwuid(): uid not found: %S`; `getpass.py:154-175` `getuser()` tries `LOGNAME`, `USER`, `LNAME` and `USERNAME` first (`:166-169`), then `pwd.getpwuid(os.getuid())[0]` (`:171-173`) and raises `OSError` when neither gives a name (`:174-175`), which is why `account_name()` asks the password database first and falls back to `getuser()` only when the uid has no entry |
| Recursive traversal and reading (P2-1) | `python/cpython@v3.13.16:Lib/pathlib/_local.py`, `0530b4186ec5845e000bedf5817ff1ac970b9a39a6891ba6789a1776abdea42b`; `Lib/pathlib/_abc.py`, `75e6bc728013d11446126d535f92b8907fb6dae7404df3d0268ac7b6865a2090` | `_local.py:611-620` `Path.rglob(pattern)` yields every existing file of any kind, directories included, anywhere in the subtree (it globs `'**' / pattern`), and `:581` `recurse_symlinks=False` is the default; `_abc.py:476-488` `is_file()` is also true for a symlink to a regular file, `:621-626` `read_bytes()` reads the whole file. The scan uses these, not `os.walk` |
| The decoded forms (P2-1) | `python/cpython@v3.13.16:Lib/urllib/parse.py`, `491b233e8d87a2ab73964afff029717177d53ad8def328ed9b00575db983da27`; `Lib/base64.py`, `a80fc2454f7a0ad644f02259184de5b52084392ddb8b41c1ce372e50a09f3993`; `Objects/bytesobject.c`, `fd5e3799c5a70a7560460badf84a1a3e14c5b8b40a40352840477e267019cf20` | `parse.py:649-651` `unquote_to_bytes('abc%20def') -> b'abc def'`, `:673-680` a `%XX` pair becomes its byte and anything else stays as written; `base64.py:51-62` `b64encode`, `:112-119` `urlsafe_b64encode` (`-` and `_` for `+` and `/`); `bytesobject.c:2583-2592` `bytes.hex()` "Create a string of hexadecimal numbers from a bytes object" |
| Lookaround assertions behind the bare-word and identifier forms (P2-1) | `python/cpython@v3.13.16:Doc/library/re.rst`, `455ed7abc1d74b6af12c9205e76af0873bbb9d4297f73c8a2d6306a7ec658042` | `:459-469` `(?=…)` and `(?!…)`, `:473-479` `(?<=…)`, whose contained pattern must match a fixed length (the joiner class is one character), `:500-504` `(?<!…)` |
