#!/usr/bin/env bash
# CC landing for us-equities-trading (private, owned by one account, no merge queue; strict up-to-date + linear + squash).
# usage: [VERDICT_FILES="…"] [GATES_DONE=<receipt>] [GPT_VERDICT=<verdict>] uet_land.sh <pr> <read-head-sha-prefix>
# Order (#975 round 4): nas_land.sh's inputs refused, before any call (#1075) -> the landing lock -> early refusals (trading-cc-read, the
# verdict files, the head carries the read head's change) ->
# slow steps (ready, the Codex wait, update-branch --rebase and the change check, the CI wait, the author address) -> final_gate, fast reads
# only (the head and its change, the verdict files, trading-cc-read, the Codex gate, CI) -> the squash merge pinned to the head -> its author.
# The PR's change must equal the read head's change (git patch-id of the whole diff; hunk offsets and context may differ after a rebase).
# The current head may already be a rebase of the read head (an earlier update-branch); the change check decides.
# Exit codes: 2 verdict gate (a verdict file, GATES_DONE or trading-cc-read; a file, record or status that cannot be read included; also,
# before any call, LOCAL_REVIEW_ADJUDICATION or SQUASH_BODY_FILE set, an empty value included: they are nas_land.sh's alone), 3 head
# moved, 4 change differs, 5 CI failed (at the final gate also: no longer complete and green), 6 timeout, 7 merge failed, 8 blocked,
# 9 the Codex gate (codex_gate.py) gave neither 0 nor 5: a review running or not finished since its latest trigger (its 3, after the
# 20-minute wait or at the final gate), a review that ended other than Completed or a summary last edited by another account (its 4), a
# gate that failed or is missing; or it gave 5 without an accepted GPT_VERDICT, 10 GitHub reports DIRTY during the CI wait (it does not
# merge cleanly; nothing merged; 2026-10-16), 11 the no-reply author address could not be formed
# (nothing merged), 12 merged, but the merge commit's author is not that address (correction #148), 14 another landing of this repository
# holds the landing lock, or the lock cannot be taken (nothing merged; #975 round 4).
# Correction #136 (2026-10-10): verdict/record acceptance, change identity and the CI state use the lg_* functions below (land-patches-20261010).
# #975 P2-2 (2026-10-11): no text from gh or its API is printed. Every gh call drops its stderr, a failure ends in its step's fixed message and exit code, and gh api
# writes an error response's body to stdout (cli v2.102.0 pkg/cmd/api/api.go:538-539 and :546), so a value read from it is shown only as a state word or a count.
# #975 round 3 (2026-10-11, Codex P1/P2 and GPT P2 at af9d1901): a gate result of 5 needs GPT_VERDICT at both gate calls, values from gh
# are used only in their typed shape, git's stderr is dropped, and the gate's output is echoed only when it is one of its own status lines (lg_gate).
# #975 round 4 (2026-10-11, the CC's micro and Codex P1 at 761810d7): one landing per repository at a time (lg_lock), and one final_gate
# after every slow step that reads each gate again, with nothing but the merge after it; a failed trading-cc-read read stops (exit 2).
# 2026-10-13 (CC correction #198 and the owner's direction for local reviews): the no-reply author comes from LG_AUTHOR_LOGIN, and when
# LOCAL_REVIEWS (or CODEX_LOCAL_REVIEW) names review files the Codex gate decides from them alone (README); this repository keeps the connector.
set -u
# Parsed whole before it runs: an edit while a landing runs cannot shift what the running copy executes (2026-10-09).
{
R=seathatflowsinourveins/us-equities-trading
# CC correction #198: the merging account, whose no-reply address authors the squash merge (lg_author_email); the same account as nas_land.sh's.
LG_AUTHOR_LOGIN=${LG_AUTHOR_LOGIN:-seathatflowsinourveins}
N=${1:?pr}; E=${2:?read head}
# #1075 (the CC's read): LOCAL_REVIEW_ADJUDICATION and SQUASH_BODY_FILE are nas_land.sh's inputs alone. codex_gate.py, which this script runs
# too, decides with LOCAL_REVIEW_ADJUDICATION wherever it is set, and nothing here would bind it to the pull request and the head or record it
# in the squash body, nor read a body file; either can be inherited, for example from a nas landing in the same shell. So a SET variable, an
# empty value included, stops here, before the lock and any call (exit 2). ${VAR+x} is empty only for an unset VAR (bash(1), Parameter
# Expansion: "Omitting the colon tests only for a parameter that is unset", bash 5.3), the test lg_gate makes (#1061 P1).
[ -z "${LOCAL_REVIEW_ADJUDICATION+x}" ] || { echo "#$N LOCAL_REVIEW_ADJUDICATION is set, but it is nas-only (a nas_land.sh input): stop, nothing merged"; exit 2; }
[ -z "${SQUASH_BODY_FILE+x}" ] || { echo "#$N SQUASH_BODY_FILE is set, but it is nas-only (a nas_land.sh input): stop, nothing merged"; exit 2; }
U=${LANDING_UET_REPO:-$HOME/code/us-equities-trading}; COORD=${LANDING_COORD:-${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/coordination}
LG_GIT="git -C $U"
# >>> land-gate-fns
# #975 round 4: the landing lock is descriptor 9 (lg_lock). Every child that waits, detaches or can outlive the script runs without it, so the
# lock ends with the script: a git fetch starts `git maintenance run --auto --detach` (git v2.53.0 builtin/fetch.c:2725, run-command.c:1829-1837;
# Documentation/config/maintenance.adoc:6-15 detaching is the default), which daemonizes (builtin/gc.c:1823-1827) keeping every descriptor
# but 0-2 (setup.c:2083-2105), and gh, python3 and sleep are waited for. The script's own $(…) subshells hold descriptor 9 while they wait
# on the gh or gate call they run, so after a signal ends the script the lock stays held until that call returns, and a landing started
# meanwhile stops with exit 14 (fail closed; measured 2026-10-11: held for the rest of a 4 s child after SIGTERM, then free).
git() { command git "$@" 9>&-; }
gh() { command gh "$@" 9>&-; }
python3() { command python3 "$@" 9>&-; }
sleep() { command sleep "$@" 9>&-; }
# One landing per repository at a time (#975 round 4, the CC's micro at 761810d7): the CC is the only lander, so serialized landings
# close the base-move window against our own tooling; a merge made out of band (the owner, in the web UI) is not covered. lg_lock opens
# <dir>/<repository name>.lock on descriptor 9 and takes an exclusive flock(1) without waiting (util-linux v2.41.3 flock.1.adoc:124-125,
# the `exec 4<>file; flock -n 4` form; :68-69 -n; flock.c:189 exclusive by default, :351-363 a held lock exits 1 and prints nothing,
# :392-399 any other failure names the descriptor, not the path; flock.1.adoc:78 the lock is dropped when the file is closed). The lock
# is held until the script exits. Prints the reason and returns 14 when the lock is held or cannot be taken; nothing has run then.
lg_lock() {  # <lock directory>
  local lr
  mkdir -p -- "$1" 2>/dev/null
  { exec 9<>"$1/${R#*/}.lock"; } 2>/dev/null || { echo "#$N the landing lock cannot be opened (path withheld): stop, nothing merged"; return 14; }
  flock -n 9 2>/dev/null; lr=$?
  case "$lr" in
    0) return 0 ;;
    1) echo "#$N another landing of ${R#*/} holds the landing lock: stop, nothing merged" ;;
    *) echo "#$N flock could not take the landing lock (exit $lr): stop, nothing merged" ;;
  esac
  return 14
}
# Correction #136 (2026-10-10), tested by trading-cc/land-patches-20261010/harness/run.py. Three decision points were loose or blind:
# (1) a verdict file or record was accepted on "the head prefix anywhere AND PASS/ACK anywhere", which accepts a CHANGES_REQUESTED
#     verdict that mentions ACK elsewhere (19 of 39 real Astra CHANGES_REQUESTED files) and a record whose PASS belongs to another head;
# (2) change() hashed only the +/- lines of each file: it was blind to binary bytes, a mode change, a file name with a space or a
#     non-ASCII character, a removed line starting "--" and an added line starting "++" (git patch-id sees all of them);
# (3) the CI wait counted a commit status (trading-cc-read) as never completed (a commit status has .state, not .status).
lg_hex8() { [[ "$1" =~ ^[0-9a-f]{8}$ ]]; }
# #975 round 4 (GPT P2 at 761810d7): a verdict file, record or receipt is read ONCE (lg_text), and every decision about it is made on that
# one text. Before, `head` read line 1 and `grep` the last verdict line, each from the file: a file removed between the two reads made grep
# fail, `|| true` took that for "no verdict line", and line 1's ACK passed over a later CHANGES_REQUESTED; and head's and grep's
# diagnostics, which name the path, were printed. A read that fails is now a refusal of its own, with a fixed reason. tr drops NUL bytes,
# which bash reports (naming the script) when they reach a command substitution.
lg_text() {  # <file> : prints the file's text; rc 1, and nothing printed, when it cannot be read
  { tr -d '\000' < "$1"; } 2>/dev/null
}
# The verdict word of the LAST line that gives a verdict for the head, or nothing. A line gives one in these layouts only:
#   "Gate line: PASS at <head>..."  /  "Verdict: ACK (by closure) at <head>..."     (CC and co-op layouts; the word is PASS|ACK|CHANGES_REQUESTED + [A-Z_0-9]*, then at most one parenthetical, then " at <head>")
#   "...Verdict ... <head>...: PASS ..."  (records, kind=records: the head stands before the first colon, the word right after it)
# Anything else (a pointer line, prose that mentions the head, a PASS elsewhere on the line) gives no verdict.
lg_last_verdict() {  # <text> <8-hex head> <files|records>
  local t=$1 h=$2 kind=$3 w r12 r3 line
  w='((PASS|ACK|CHANGES_REQUESTED)[A-Z_0-9]*)'
  r12='^(Gate line|Verdict): '$w'( \([^)]*\))? at '$h
  r3='(^|[^A-Za-z])([Vv]erdict|VERDICT)[^:]*[^0-9a-f]'$h'[^:]*: *[*_` ]*'$w
  if [ "$kind" = records ]; then
    line=$(printf '%s\n' "$t" | grep -E "$r12|$r3" | tail -n 1)
  else
    line=$(printf '%s\n' "$t" | grep -E "$r12" | tail -n 1)
  fi
  if [[ "$line" =~ $r12 ]]; then echo "${BASH_REMATCH[2]}"
  elif [ "$kind" = records ] && [[ "$line" =~ $r3 ]]; then echo "${BASH_REMATCH[3]}"
  fi
}
# A verdict file is accepted by (a) its line 1 in the Astra layout "... <head>...: ACK|PASS ..." or (b) its last Gate line/Verdict line naming
# the head with PASS|ACK[A-Z_0-9]*. CHANGES_REQUESTED anywhere on line 1, or as the word of that last line, rejects; a PASS/ACK anywhere
# else in the file counts for nothing. Prints the reason on stdout when it rejects. lg_verdict_text_ok decides on a text that was read
# once; lg_verdict_file_ok reads the file once and decides on that.
lg_verdict_text_ok() {  # <text> <8-hex head prefix>
  local t=$1 h=$2 l1 w re
  lg_hex8 "$h" || { echo "head prefix '$h' is not 8 lower-case hex characters"; return 1; }
  l1=${t%%$'\n'*}; l1=${l1//$'\r'/}
  [[ "$l1" == *CHANGES_REQUESTED* ]] && { echo "line 1 carries CHANGES_REQUESTED"; return 1; }
  w=$(lg_last_verdict "$t" "$h" files)
  [[ "$w" == CHANGES_REQUESTED* ]] && { echo "the last Gate line/Verdict line naming $h is $w"; return 1; }
  re='(^|[^0-9a-f])'$h'[0-9a-f]*[^:]*: *(ACK|PASS)([^A-Za-z0-9_]|$)'
  [[ "$l1" =~ $re ]] && return 0
  [[ "$w" == PASS* || "$w" == ACK* ]] && return 0
  echo "no accepted verdict naming $h: line 1 must read '...$h...: ACK|PASS' or a Gate line/Verdict line must read 'PASS|ACK at $h'"; return 1
}
lg_verdict_file_ok() {  # <file> <8-hex head prefix>
  local t
  lg_hex8 "$2" || { echo "head prefix '$2' is not 8 lower-case hex characters"; return 1; }
  [ -f "$1" ] || { echo "file missing"; return 1; }
  t=$(lg_text "$1") || { echo "file unreadable"; return 1; }
  lg_verdict_text_ok "$t" "$2"
}
# A receipt (GATES_DONE) is accepted when it names the head, from one read as above; rc 1, and nothing printed, otherwise.
lg_receipt_ok() {  # <receipt file> <8-hex head prefix>
  local t
  [ -n "$1" ] && [ -f "$1" ] || return 1
  t=$(lg_text "$1") || return 1
  [[ "$t" == *"$2"* ]]
}
# A record (append-only, many heads) is accepted for a head when the LAST line that gives a verdict for it carries PASS or ACK (a section that
# changes a verdict should end with "Gate line: <PASS|ACK|CHANGES_REQUESTED> at <head>"). Prints the reason on stdout when it rejects.
lg_record_ok() {  # <record file> <8-hex head prefix>
  local f=$1 h=$2 t w
  lg_hex8 "$h" || { echo "head prefix '$h' is not 8 lower-case hex characters"; return 1; }
  [ -f "$f" ] || { echo "record missing"; return 1; }
  t=$(lg_text "$f") || { echo "record unreadable"; return 1; }
  w=$(lg_last_verdict "$t" "$h" records)
  [ -n "$w" ] || { echo "no Verdict/Gate line gives a verdict for $h"; return 1; }
  [[ "$w" == PASS* || "$w" == ACK* ]] && return 0
  echo "the last verdict line for $h is $w"; return 1
}
# The identity of a change: git patch-id (verbatim: whitespace counts; hunk positions do not) of the whole diff at -U0 --binary between
# the commit and its own merge base with origin/main, so mode bits, binary bytes and every file name are in it and a rebase that only
# moves context keeps it. LG_GIT is the git command with its repository, LG_EXCLUDE an optional pathspec to leave out. An empty change
# has no identity (rc 1) and is refused; a change that is empty only because everything in it is excluded is identified by its file names.
lg_change_id() {  # <commit>
  local c=$1 b id names
  b=$(${LG_GIT:-git} merge-base "$c" origin/main 2>/dev/null) || return 1
  id=$(${LG_GIT:-git} -c core.quotePath=false -c diff.noprefix=false -c diff.mnemonicPrefix=false diff --no-color --no-ext-diff --no-textconv --no-renames -U0 --binary "$b" "$c" -- . ${LG_EXCLUDE:+"$LG_EXCLUDE"} 2>/dev/null | git patch-id --verbatim | cut -d' ' -f1)
  if [ -n "$id" ]; then echo "$id"; return 0; fi
  names=$(${LG_GIT:-git} -c core.quotePath=false diff --no-renames --name-only "$b" "$c" 2>/dev/null)
  [ -n "$names" ] || return 1
  echo "names:$(printf '%s\n' "$names" | sha256sum | cut -c1-40)"
}
lg_same_change() { local a b; a=$(lg_change_id "$1") || return 1; b=$(lg_change_id "$2") || return 1; [ "$a" = "$b" ]; }
# CC 2026-10-10 (uet#58): an update-branch rebase does not reach every API view at once (the REST update-branch endpoint
# answers 202 Accepted). 6 s after it, headRefOid still gave the read head while the CI view gave the rebased head, and the
# landing stopped on its own rebase (exit 3). A head that moves during CI is followed only when it carries the read head's
# change, at most 3 times per landing; any other move still stops, and the merge stays pinned with --match-head-commit.
lg_follow_head() {  # <read head> <new head> <follows so far>
  [ -n "${2:-}" ] && [ "${3:-0}" -lt 3 ] || return 1
  ${LG_GIT:-git} fetch -q origin main 2>/dev/null
  ${LG_GIT:-git} cat-file -e "$2^{commit}" 2>/dev/null || ${LG_GIT:-git} fetch -q origin "$2" 2>/dev/null || return 1
  lg_same_change "$1" "$2"
}
# Correction #148 (2026-10-10): GitHub authors a squash merge with the account's primary email unless the merge names one, so every landing
# published the owner's personal address. The merge names the no-reply form <id>+<login>@users.noreply.github.com (`gh pr merge -A`, gh 2.102.0);
# the id comes from the public users API, because `gh api user` is refused by the secret-path guard. No stored address is ever printed.
# CC correction #198 (2026-10-13): the login is the merging account, LG_AUTHOR_LOGIN, and R's owner only when that is unset. After the
# transfer R's owner was an organization, and the squash merge failed with GraphQL "Invalid email address": the no-reply form belongs to a
# user account, "ID+USERNAME@users.noreply.github.com" (github/docs@be38ec5d email-addresses-reference.md:47). A login of another shape than
# GitHub's (at most 39 alphanumerics and single inner dashes, username-considerations-for-external-authentication.md:94, :103, :126-127)
# is refused before any call. #1061 P3: users/<login> answers for an organization too, whose address then failed at the merge (exit 7, as
# in #198); only an account of type User gives an id (otherwise exit 11, nothing merged). GET /users/{username} returns the private or the
# public user schema (github/rest-api-description@58b1e0c0 api.github.com.json:88612-88614), whose `type` is a free string, "User" in the
# example (:126248-126250, :160055-160058), while an organization's account reads "Organization" (the example at :311038); the check
# takes the literal "User" alone, so another value or none gives no id.
lg_author_email() {  # <owner/repo> : the account's no-reply address; rc 1 and nothing printed when the login or the id is not well formed
  local login=${LG_AUTHOR_LOGIN:-${1%%/*}} id
  [[ "$login" =~ ^[A-Za-z0-9](-?[A-Za-z0-9])*$ ]] && [ "${#login}" -le 39 ] || return 1
  id=$(gh api "users/$login" --jq 'select(.type == "User") | .id' 2>/dev/null) || return 1
  case "$id" in ''|*[!0-9]*) return 1 ;; esac
  printf '%s+%s@users.noreply.github.com\n' "$id" "$login"
}
# #1194's GPT reads (P3-1 at b4489b15, 4fad2736 and 967d068a): the merge commit is taken only from a read whose call exited 0, and only as
# 40 hex digits (lg_hex40, below); a failed call's stdout, or another reply, is no merge commit, so five such reads are exit 12 with nothing
# of them printed.
lg_author_check() {  # <owner/repo> <pr> <no-reply address> : after the merge, the merge commit's author is that address; prints text only, never the stored address
  local mc="" ok="" i
  for i in 1 2 3 4 5; do
    mc=$(gh pr view "$2" -R "$1" --json mergeCommit --jq '.mergeCommit.oid // empty' 2>/dev/null) && lg_hex40 "$mc" && break
    mc=""
    sleep 3
  done
  [ -n "$mc" ] || { echo "#$2 author address NOT CHECKED: the merge commit is unreadable (correction #148)"; return 1; }
  ok=$(gh api "repos/$1/commits/$mc" --jq ".commit.author.email == \"$3\"" 2>/dev/null)
  [ "$ok" = true ] && { echo "#$2 author address on ${mc:0:8}: the no-reply form"; return 0; }
  echo "#$2 author address on ${mc:0:8} is NOT the no-reply form (correction #148)"; return 1
}
# #975 (GPT P2-B and P2-C at af9d1901, 2026-10-11): what gh, git and the gate return is used only in its typed shape, and nothing else they
# print reaches the output. A head is 40 lower-case hex digits, anything else is no head; lg_have fetches a commit the clone lacks, silently.
lg_hex40() { [[ "$1" =~ ^[0-9a-f]{40}$ ]]; }
lg_have() {  # <commit>
  lg_hex40 "$1" || return 1
  ${LG_GIT:-git} cat-file -e "$1^{commit}" 2>/dev/null || ${LG_GIT:-git} fetch -q origin "$1" 2>/dev/null
}
# codex_gate.py's output is echoed only when it is one of the gate's own status lines: one line that starts "Codex review ", "Codex
# unavailable: ", "no Codex review " or "Codex gate error: ", in the characters those lines use, with exit code 0, 3, 4 or 5. Anything
# else is one fixed line and 4: for a gate file that is missing or unreadable python3 prints "can't open file '<path>'" and exits 2
# (CPython v3.13.16 Modules/main.c:403-410), and an exception outside the gate's handler, such as a syntax error, prints a traceback
# and exits 1 (:437-441, :118-123; Doc/library/sys.rst:394-399). The read head goes to the gate, which counts only a review of it or of
# the current head (#975 round 4).
# Local reviews (2026-10-13, the owner's direction: reviews run locally, the connector cannot reach the organization's repository): when
# LOCAL_REVIEWS or its alias CODEX_LOCAL_REVIEW is set (an empty value included, #1061 P1: it fell back to the connector, which cannot
# answer; ${VAR+x} is empty only for an unset VAR, bash(1) Parameter Expansion: "Omitting the colon tests only for a parameter that is
# unset", bash 5.3), the gate decides from the normalized review files they name (colon-separated). A file whose head_sha is not the read
# head counts only when that head carries the read head's change, by this block's change identity (lg_same_change). The read head and each such head
# go to the gate after the read head as "<head>:<git merge-base <head> origin/main>" (#1061 P1: a codex-review must have been reviewed
# against that merge base; the first call fetches a head the clone lacks, lg_have). The gate's 2 (no file, a file malformed, incomplete,
# of another head or of another base) is echoed when it is one of its "Local reviews: " lines; python3's own 2 is not.
lg_gate() {  # <gate> <owner/repo> <pr> <read head> : prints one line; returns 0, 2, 3, 4 or 5
  local g gr q="'" re part f h mb files=() more=() heads=() facts=()
  re="^(Codex review |Codex unavailable: |no Codex review |Codex gate error: |Local reviews: )[A-Za-z0-9 :;,.()_+${q}-]*\$"
  if [ -n "${LOCAL_REVIEWS+x}${CODEX_LOCAL_REVIEW+x}" ]; then
    for part in "${LOCAL_REVIEWS-}" "${CODEX_LOCAL_REVIEW-}"; do
      [ -n "$part" ] || continue
      IFS=: read -r -a more <<< "$part"; files+=(${more[@]+"${more[@]}"})
    done
    heads=("$4")
    for f in ${files[@]+"${files[@]}"}; do
      [ -n "$f" ] || continue
      h=$({ jq -r 'if type == "object" and (.head_sha | type) == "string" then .head_sha else empty end' < "$f"; } 2>/dev/null)
      lg_hex40 "$h" && [[ " ${heads[*]} " != *" $h "* ]] || continue
      lg_have "$h" && lg_same_change "$4" "$h" && heads+=("$h")
    done
    for h in "${heads[@]}"; do
      lg_have "$h"; mb=$(${LG_GIT:-git} merge-base "$h" origin/main 2>/dev/null); lg_hex40 "$mb" || mb=
      facts+=("$h:$mb")
    done
  fi
  g=$(python3 -I "$1" "$2" "$3" "$4" ${facts[@]+"${facts[@]}"} 2>&1); gr=$?
  case "$gr" in
    0|3|4|5) ;;
    2) [[ "$g" == "Local reviews: "* ]] || { echo "Codex gate failed with exit 2; details withheld"; return 4; } ;;
    *) echo "Codex gate failed with exit $gr; details withheld"; return 4 ;;
  esac
  [[ "$g" =~ $re ]] || { echo "Codex gate printed no status line of its own; details withheld"; return 4; }
  echo "$g"; return "$gr"
}
# Text that must not be printed (gh's merge diagnostic) is kept in a new file that mktemp makes under TMPDIR (mode 0600, sources in the
# README), and only the file's name is printed; rc 1 and nothing printed when the file cannot be made or written (#975 P3-3: before, a
# failed mktemp printed the template's path and the message named an empty file).
lg_keep() {  # <file name prefix> <text>
  local f
  f=$(mktemp "${TMPDIR:-/tmp}/$1-XXXXXX" 2>/dev/null) || return 1
  { printf '%s\n' "$2" > "$f"; } 2>/dev/null || { rm -f -- "$f" 2>/dev/null; return 1; }
  echo "${f##*/}"
}
# The CI state of a pull request as one tab-separated line: head, incomplete, failing, total, ci-gate successes, mergeStateStatus.
# A CheckRun is complete when .status is COMPLETED and failing on any conclusion other than SUCCESS, NEUTRAL or SKIPPED (fail closed, #975 P2-3: GraphQL CheckConclusionState also has
# ACTION_REQUIRED, STALE and STARTUP_FAILURE; schema.docs.graphql sha256 3ed09565…, lines 3974-4018); a commit status (StatusContext, such as
# trading-cc-read) has .state and no .status: PENDING or EXPECTED is running, SUCCESS is complete and any other state is failing (fail closed, #975 P3:
# GraphQL StatusState has ERROR, EXPECTED, FAILURE, PENDING and SUCCESS; schema.docs.graphql sha256 3ed09565…, lines 65267-65292). A rollup
# entry of any other type counts as running (fail closed). ci-gate is matched on CheckRuns only.
lg_ci_state() {  # <pr>
  gh pr view "$1" -R "$R" --json headRefOid,statusCheckRollup,mergeStateStatus --jq '[.headRefOid, ([.statusCheckRollup[]|select((.__typename=="CheckRun" and .status!="COMPLETED") or (.__typename=="StatusContext" and (.state=="PENDING" or .state=="EXPECTED")) or (.__typename!="CheckRun" and .__typename!="StatusContext"))]|length), ([.statusCheckRollup[]|select((.__typename=="CheckRun" and .status=="COMPLETED" and ((.conclusion=="SUCCESS" or .conclusion=="NEUTRAL" or .conclusion=="SKIPPED")|not)) or (.__typename=="StatusContext" and ((.state=="SUCCESS" or .state=="PENDING" or .state=="EXPECTED")|not)))]|length), (.statusCheckRollup|length), ([.statusCheckRollup[]|select(.__typename=="CheckRun" and .name=="ci-gate" and .conclusion=="SUCCESS")]|length), .mergeStateStatus]|@tsv' 2>/dev/null
}
# <<< land-gate-fns
lg_lock "${LANDING_LOCK_DIR:-$COORD/command-center/landing-locks}" || exit 14
git -C $U fetch -q origin main "pull/$N/head" 2>/dev/null
full=$(git -C $U rev-parse --verify -q "$E^{commit}" 2>/dev/null) || { git -C $U fetch -q origin "$E" 2>/dev/null; full=$(git -C $U rev-parse --verify -q "$E^{commit}" 2>/dev/null); }
[ -n "$full" ] || { echo "#$N read head $E not resolvable"; exit 3; }
E=$full
# trading-cc posts a `trading-cc-read` commit status on its read head (from 2026-10-09T22:50Z), described
# "<VERDICT>: trading-cc/reads/<record>.md" (for example "PASS: …"). A failure blocks. A success counts only when that record exists and names
# the read head with PASS or ACK, because a status carries no app identity (any holder of the owner token can post one).
tcc_read_gate() {
  local p s sr st d rec why
  # #975 (Codex P1 at nas:234, in A1's correction): the statuses LIST is newest first across every context ("Statuses are returned in
  # reverse chronological order. The first status in the list will be the latest one", github/rest-api-description@58b1e0c0
  # api.github.com.json:55724), and its page 1 held 100, so a trading-cc-read failure behind 100 newer statuses of other contexts was not
  # on it and passed as "no status". The COMBINED status, "a combined view of commit statuses for a given ref" whose state is success "if
  # the latest status for all contexts is `success`" (:55664-55667), holds one entry per context, its newest (measured on 2026-10-11 on the
  # 12 of 80 heads of ours that have statuses and on 8 public heads of up to 35 statuses in 15 contexts: each context once, each entry the
  # list's first of its context), so which of two statuses posted in one second is the newer (#975 B1 at 5b8ba3b2) is GitHub's answer,
  # not a sort's. It is paged by context (per_page and page, :55687, :55690; a first page with more contexts than per_page carried a Link
  # rel="next", measured), so every page is read with gh api --paginate --slurp, as for nas's check runs, and jq finds the context on any.
  p=$(gh api "repos/$R/commits/$1/status?per_page=100" --paginate --slurp 2>/dev/null); sr=$?
  # #975 round 4 (Codex P1 at 761810d7, the CC's P2-3): gh's exit code is kept apart from its output. A failed call stops, whatever it
  # printed (an error response's body reaches stdout, a refused connection prints nothing there), and so does a reply that is not an array
  # of pages with statuses, an empty one included (jq -n fails at `input` when there is none); only a combined status with no
  # trading-cc-read entry on any page is "no status".
  [ "$sr" = 0 ] || { echo "#$N trading-cc-read statuses unreadable at ${1:0:8} (gh exit $sr, output withheld): stop"; exit 2; }
  s=$(printf '%s' "$p" | jq -n -r 'input|if type == "array" and length > 0 then [.[].statuses[]|select(.context=="trading-cc-read")]|first|select(.!=null)|"\(.state)\t\(.description)" else error("not a combined status") end' 2>/dev/null) \
    || { echo "#$N trading-cc-read statuses unreadable at ${1:0:8} (not a combined status, output withheld): stop"; exit 2; }
  [ -n "$s" ] || return 0
  st=${s%%$'\t'*}; d=${s#*$'\t'}
  [ "$st" = success ] || { case "$st" in error|failure|pending) ;; *) st=unknown ;; esac; echo "#$N trading-cc-read is $st at ${1:0:8} (description withheld, #975 P2-2): stop"; exit 2; }
  # Correction #136: the description's verdict word must be PASS or ACK, and the record's LAST Verdict line naming the head must carry
  # PASS or ACK (not just "the head somewhere and a PASS anywhere").
  [[ "$d" =~ ^(PASS|ACK):\ (trading-cc/reads/[A-Za-z0-9._-]+\.md)$ ]] || { echo "#$N trading-cc-read description not in the agreed form (PASS|ACK: trading-cc/reads/<record>.md): stop"; exit 2; }
  rec=$COORD/${BASH_REMATCH[2]}
  why=$(lg_record_ok "$rec" "${1:0:8}") \
    || { echo "#$N trading-cc-read success at ${1:0:8}, but ${BASH_REMATCH[2]} does not name it with a last PASS/ACK Verdict line ($why): stop"; exit 2; }
  echo "#$N trading-cc-read success at ${1:0:8}; record verified"
}
# Correction #121: VERDICT_FILES are checked; each names the read head with PASS/ACK, and a stated landing gate needs
# GATES_DONE=<receipt naming the read head>. #975 round 4 (Codex P1 at 761810d7): the files are mutable, so final_gate runs this again.
verdict_gate() {
  local v t why re='landing gate|path to pass|before landing|landing condition'
  for v in ${VERDICT_FILES:-}; do
    # #975 P2-C: a verdict file is named by its file name only (its directory can be under a home directory).
    [ -f "$v" ] || { echo "#$N verdict file missing: ${v##*/}"; exit 2; }
    # #975 round 4 (GPT P2 at 761810d7): the file is read once, and its verdict and its landing-gate phrases are both decided on that text.
    t=$(lg_text "$v") || { echo "#$N verdict ${v##*/} is unreadable: stop"; exit 2; }
    # Correction #136: line 1 "... ${E:0:8}...: ACK|PASS" (the Astra layout) or a Gate line/Verdict line "PASS|ACK at ${E:0:8}"; CHANGES_REQUESTED rejects.
    why=$(lg_verdict_text_ok "$t" "${E:0:8}") || { echo "#$N verdict ${v##*/} has no PASS/ACK naming ${E:0:8} ($why)"; exit 2; }
    if [[ "${t,,}" =~ $re ]]; then
      lg_receipt_ok "${GATES_DONE:-}" "${E:0:8}" \
        || { echo "#$N verdict ${v##*/} states a landing gate: set GATES_DONE=<receipt naming ${E:0:8}>"; exit 2; }
    fi
  done
}
# Early refusals, cheap first reads: the trading-cc-read gate, the verdict files, and the head.
tcc_read_gate "$E"
verdict_gate
# Correction #136: the identity of a change is git patch-id (verbatim, -U0, --binary) of its whole diff against its own merge base; an empty change is refused.
change() { lg_change_id "$1"; }
same_change() { lg_same_change "$1" "$2"; }
cur=$(gh pr view "$N" -R "$R" --json headRefOid --jq .headRefOid 2>/dev/null); lg_hex40 "$cur" || cur=
lg_have "$cur"
if [ "$cur" != "$E" ]; then
  same_change "$E" "$cur" || { echo "#$N head ${cur:-?} is neither the read head nor a pure rebase of it"; exit 3; }
fi
# Corrections #122 and #123 (GHA audit T9): a Codex review starts when a PR opens, when a draft is marked ready (by
# anyone) and on an "@codex review" comment. #40 merged before its review posted 2 P1 threads, and #47, marked ready by
# another session 23 s before this script ran, merged while its review was Running (4 P2 threads came after). So a
# draft is marked ready first, then codex_gate.py must report the latest review finished (exit 0); running or not yet
# started is polled for up to 20 minutes (exit 9 after that, or when a review ends other than Completed). Findings
# become threads, which BLOCK below. final_gate asks the gate again.
# 2026-10-10 (trading-cc proposal, CC ruling): while the Codex connector reports its usage limit, the cross-family pass at
# the head is the co-op's Astra GPT verdict instead. Set GPT_VERDICT=<verdict file naming the read head with ACK/PASS>.
# #975 (Codex P1 and GPT P2-A at af9d1901, 2026-10-11): the gate can first give 5 at the final gate (an "@codex review" during CI that
# meets the usage limit), so a 5 at either gate call needs the substitute; before, only the wait checked it, and "0 then 5" merged without one.
gpt_substitute() {
  local why=""
  # Correction #136: the same acceptance as VERDICT_FILES (line 1 "...${E:0:8}...: ACK|PASS", or a Gate line/Verdict line); CHANGES_REQUESTED rejects.
  [ -n "${GPT_VERDICT:-}" ] && why=$(lg_verdict_file_ok "$GPT_VERDICT" "${E:0:8}") \
    || { echo "#$N Codex unavailable: set GPT_VERDICT=<the co-op's Astra verdict naming ${E:0:8} with ACK or PASS on line 1, or a Gate line/Verdict line>${why:+ ($why)}"; exit 9; }
  echo "#$N Codex unavailable; substitute GPT verdict $(basename "$GPT_VERDICT") names ${E:0:8}"
}
codex_wait() {
  local j g gr
  for j in $(seq 1 21); do
    g=$(lg_gate "$GATE" "$R" "$N" "$E"); gr=$?
    { [ $gr = 0 ] || [ $gr = 5 ]; } && { echo "#$N $g"; [ $gr = 0 ] || gpt_substitute; return 0; }
    [ $gr = 3 ] && [ $j -lt 21 ] && { sleep 60; continue; }
    # #1061 (the probe's finding 8): a 2 is a local review file that is wrong, not a review still to come
    [ $gr = 2 ] && { echo "#$N $g: stop, correct the local review files or write them again (LOCAL_REVIEWS)"; exit 9; }
    echo "#$N $g: stop, land after Codex finishes"; exit 9
  done
}
GATE=${LANDING_GATE:-$(dirname "$(readlink -f -- "$0")")/codex_gate.py}
# #975 P3-4: a missing gate is one fixed line (python3 would print its path), before anything is marked ready.
[ -f "$GATE" ] || { echo "#$N codex_gate.py not found (path withheld): stop"; exit 9; }
# #975 round 4 (the CC's micro at 761810d7: each gate could change between its last read and the merge, and each round-3 fix left the next
# gap): after every slow step, final_gate reads every gate again, fast reads only and in this order, and nothing but the merge follows it:
# the head (the pinned head, carrying the read head's change), the verdict files and GATES_DONE, trading-cc-read (a failed read stops),
# the Codex gate (a 5 needs GPT_VERDICT), and CI at the head (complete, green, ci-gate reported, not BLOCKED). Any failure stops with
# that gate's exit code. What the reads cannot close is in the README ("What the final gate can and cannot close").
final_gate() {  # <pinned head>
  local hd s g gr open
  hd=$(gh pr view "$N" -R "$R" --json headRefOid --jq .headRefOid 2>/dev/null); lg_hex40 "$hd" || hd=
  [ "$hd" = "$1" ] || { echo "#$N head moved to ${hd:-?} at the final gate: stop"; exit 3; }
  same_change "$E" "$hd" || { echo "#$N CHANGE DIFFERS between read head ${E:0:8} and head ${hd:0:8} at the final gate: stop"; exit 4; }
  verdict_gate
  tcc_read_gate "$E"
  g=$(lg_gate "$GATE" "$R" "$N" "$E"); gr=$?
  { [ $gr = 0 ] || [ $gr = 5 ]; } || { echo "#$N $g at the final gate: stop"; exit 9; }
  [ $gr = 0 ] || { echo "#$N $g at the final gate"; gpt_substitute; }
  s=$(lg_ci_state "$N"); [[ "$s" =~ ^[0-9a-f]{40}$'\t'[0-9]+$'\t'[0-9]+$'\t'[0-9]+$'\t'[0-9]+$'\t'[A-Z_]*$ ]] || s=
  set -- $s
  [ "${1:-}" = "$hd" ] || { echo "#$N head moved to ${1:-?} in the CI read at the final gate: stop"; exit 3; }
  [ "$2" = 0 ] && [ "$3" = 0 ] && [ "$4" -gt 0 ] && [ "$5" -gt 0 ] \
    || { echo "#$N CI at ${hd:0:8} is no longer complete and green at the final gate (incomplete=$2, failing=$3 of $4, ci-gate successes $5): stop"; exit 5; }
  if [ "${6:-}" = BLOCKED ]; then
    open=$(gh api graphql -f query='query($n:Int!){repository(owner:"seathatflowsinourveins",name:"us-equities-trading"){pullRequest(number:$n){reviewThreads(first:100){nodes{isResolved}}}}}' -F n="$N" --jq '[.data.repository.pullRequest.reviewThreads.nodes[]|select(.isResolved==false)]|length' 2>/dev/null)
    case "$open" in ''|*[!0-9]*) open=unknown ;; esac
    echo "#$N BLOCKED by branch policy at the final gate; unresolved review threads: $open. Not forcing."; exit 8
  fi
  echo "#$N final gate at ${hd:0:8}: head, change, verdict files, trading-cc-read, Codex and CI read again (CI $4 ok)"
}
# Slow steps: ready, the Codex wait, update-branch, the CI wait, the author address.
if [ "$(gh pr view "$N" -R "$R" --json isDraft --jq .isDraft 2>/dev/null)" = true ]; then
  gh pr ready "$N" -R "$R" >/dev/null 2>&1 || { echo "#$N could not be marked ready"; exit 7; }
  echo "#$N marked ready at $(date -u +%FT%TZ)"; sleep 20
fi
codex_wait
gh pr update-branch "$N" -R "$R" --rebase >/dev/null 2>&1 || true
sleep 6
git -C $U fetch -q origin main "pull/$N/head" 2>/dev/null
H=$(gh pr view "$N" -R "$R" --json headRefOid --jq .headRefOid 2>/dev/null); lg_hex40 "$H" || H=
lg_have "$H"
same_change "$E" "$H" || { echo "#$N CHANGE DIFFERS between read head ${E:0:8} and head ${H:0:8}: stop"; exit 4; }
echo "#$N read ${E:0:12} -> head ${H:0:12}: same change (file set and per-file changed lines)"
follows=0; ci=
for i in $(seq 1 25); do
  # The required check (ci-gate) must have reported for this head: early-registering checks alone are not "CI done"
  # (2026-10-09 #26: a merge was attempted while only fast checks had registered).
  # Correction #136: lg_ci_state counts a commit status by .state (a PENDING trading-cc-read is running, a SUCCESS one is complete), CheckRuns by .status.
  s=$(lg_ci_state "$N")
  # #975 P2-B: the line is used only in its typed shape (a head, four counts, a state word); anything else is no state (exit 3 below).
  [[ "$s" =~ ^[0-9a-f]{40}$'\t'[0-9]+$'\t'[0-9]+$'\t'[0-9]+$'\t'[0-9]+$'\t'[A-Z_]*$ ]] || s=
  set -- $s
  if [ "${1:-}" != "$H" ]; then
    lg_follow_head "$E" "${1:-}" "$follows" || { echo "#$N head moved to ${1:-?} during CI: stop"; exit 3; }
    echo "#$N head moved to ${1:0:8} during CI and carries the read head's change: following it"
    H=$1; follows=$((follows + 1)); sleep 20; continue
  fi
  # The CC's ruling of 2026-10-16 on #1229, as nas_land.sh's CI wait: DIRTY is "The merge commit cannot be cleanly created."
  # (github/docs@be38ec5d schema.docs.graphql:26528-26530), a merge conflict that waiting does not resolve, and "Workflows will not run on
  # `pull_request` activity if the pull request has a merge conflict" (only pull_request_target workflows do;
  # events-that-trigger-workflows.md:466). So the wait stops at once with 10 (does not merge cleanly) instead of holding the landing lock
  # until the timeout (6).
  [ "${6:-}" = DIRTY ] && { echo "#$N GitHub reports DIRTY during the CI wait: the merge commit cannot be created cleanly; a native rebase is needed: stop, nothing merged"; exit 10; }
  if [ "${2:-1}" = 0 ] && [ "${4:-0}" -gt 0 ] && { [ "${5:-0}" -gt 0 ] || [ "${3:-0}" -gt 0 ]; }; then
    [ "$3" = 0 ] || { echo "#$N CI failing=$3 of $4: stop"; exit 5; }
    if [ "${6:-}" = BLOCKED ]; then
      open=$(gh api graphql -f query='query($n:Int!){repository(owner:"seathatflowsinourveins",name:"us-equities-trading"){pullRequest(number:$n){reviewThreads(first:100){nodes{isResolved}}}}}' -F n="$N" --jq '[.data.repository.pullRequest.reviewThreads.nodes[]|select(.isResolved==false)]|length' 2>/dev/null)
      case "$open" in ''|*[!0-9]*) open=unknown ;; esac
      echo "#$N BLOCKED by branch policy with CI green; unresolved review threads: $open. Not forcing."; exit 8
    fi
    ci=$4; break
  fi
  sleep 120
done
[ -n "$ci" ] || { echo "#$N CI timeout"; exit 6; }
ae=$(lg_author_email "$R") || { echo "#$N cannot form the no-reply author address (correction #148): stop, nothing merged"; exit 11; }
final_gate "$H"
out=$(gh pr merge "$N" -R "$R" --squash --match-head-commit "$H" -A "$ae" 2>&1) || { cls=$(printf '%s' "$out" | grep -o -i -E 'not mergeable|head branch was modified|required status check|review|draft|merge conflict|protected branch|rate limit|authentication|not found' | head -1 | tr 'A-Z ' 'a-z_'); mf=$(lg_keep merge-fail "$out") && kept="gh output kept only in local file $mf in the temp directory (0600), never echoed" || kept="gh output could not be kept, and is not echoed"; echo "#$N merge failed (class: ${cls:-other}); $kept (#975 P2-2)"; exit 7; }
sleep 4
echo "#$N $(gh pr view "$N" -R "$R" --json state,mergeCommit,mergedAt --jq '"\(.state) \(.mergeCommit.oid) \(.mergedAt)"' 2>/dev/null) (CI $ci ok)"
lg_author_check "$R" "$N" "$ae" || exit 12
exit 0
}
