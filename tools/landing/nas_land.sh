#!/usr/bin/env bash
# CC landing for native-agent-stack (correction #118): the merge runs only after every gate passes, in this order.
# usage: [SQUASH_BODY_FILE=<file>] nas_land.sh <pr> <read-head-sha-prefix> <verdict-file> [<verdict-file> ...]
# Order (#975 round 4): the landing lock -> early refusals (the head carries the read head's change, trading-cc-read, the verdict files) ->
# slow steps (update-branch when BEHIND, ready, the Codex wait, the CI wait, the Codex gate before the validation, the merge onto the current
# origin/main validated (again while main moves), the author address) -> final_gate, fast reads only (the head and its change, the verdict
# files, trading-cc-read, the Codex gate, the check runs, origin/main) -> the squash merge pinned to the head -> its author.
# Exit codes: 2 verdict gate (a verdict file, GATES_DONE or trading-cc-read; a file, record or status that cannot be read included), or a
# SQUASH_BODY_FILE that is unreadable, empty, refused by the publication scan or not scannable (all before any gh or git call), 3 head
# moved, 4 change differs (after update-branch, or at the final gate) or update-branch refused, 5 CI failing (at the final gate also: no
# longer complete and green), 6 timeout, 7 merge failed, 8 blocked by policy, 9 the Codex gate (codex_gate.py) gave neither 0 nor 5 (a 5
# proceeds here): a review running or not finished since its latest trigger (its 3, after the 20-minute wait, before the validation or at
# the final gate), a review that ended other than Completed or a summary last edited by another account (its 4), a gate that failed or is
# missing, 10 the merge onto CURRENT origin/main fails scripts/validate.py or does not merge cleanly (2026-10-10), or fails one of
# validate.yml's shard-0 currency checks whose script it holds (CC correction #176, 2026-10-12).
# 11 the no-reply author address could not be formed (nothing merged), 12 merged, but the merge commit's author is not that address (correction #148).
# 13 origin/main moved after each of three validations, moved after the last validation (final gate) or is unreadable (nothing merged; #975).
# 14 another landing of this repository holds the landing lock, or the lock cannot be taken (nothing merged; #975 round 4).
# SQUASH_BODY_FILE (the CC, 2026-10-12): when set, the squash commit's body is that file (gh pr merge --body-file), for a PR whose commit
# messages carry a claim corrected after review (the repository's squash default is COMMIT_MESSAGES). A value that is not a readable,
# non-empty regular file stops with exit 2 before the lock and any call. The file is copied once to a private snapshot, the snapshot is
# scanned for text that must not reach main's history (lg_body_snapshot; #1027) and the merge is given that snapshot, not the file: a
# match, or a scanner or names file that is missing or fails, stops with exit 2 too (nothing printed but one fixed line).
# Correction #136 (2026-10-10): verdict/record acceptance and change identity use the lg_* functions below (land-patches-20261010).
# #975 P2-2 (2026-10-11): no text from gh or its API is printed. Every gh call drops its stderr, a failure ends in its step's fixed message and exit code, and gh api
# writes an error response's body to stdout (cli v2.102.0 pkg/cmd/api/api.go:538-539 and :546), so a value read from it is shown only as a state word or a count.
# #975 round 3 (2026-10-11, Codex P1/P2 and GPT P2 at af9d1901): the merge onto main is validated again when main moved after it, values
# from gh are used only in their typed shape, git's stderr and validate.py's output are not printed, and the gate's output is echoed only
# when it is one of its own status lines (lg_gate).
# #975 round 4 (2026-10-11, the CC's micro and Codex P1 at 761810d7): one landing per repository at a time (lg_lock), and one final_gate
# after every slow step that reads each gate again, with nothing but the merge after it; a failed trading-cc-read read stops (exit 2).
set -u
# Parsed whole before it runs: an edit while a landing runs cannot shift what the running copy executes (2026-10-09).
{
R=seathatflowsinourveins/native-agent-stack
N=${1:?pr}; E=${2:?read head}; shift 2
[ $# -ge 1 ] || { echo "#$N no verdict file given: stop"; exit 2; }
VF=("$@")  # #975 round 4: the verdict files, kept for final_gate (the CI loop's `set --` replaces the positional parameters)
# gh reads the body file when the merge call starts, and "-" would make it read standard input (cli v2.102.0 pkg/cmd/pr/merge/merge.go:146-153,
# pkg/cmdutil/file_input.go:8-15), so "-" is refused with every other value that is not a readable, non-empty regular file. The path is not printed.
[ -z "${SQUASH_BODY_FILE:-}" ] || { [ "$SQUASH_BODY_FILE" != - ] && [ -f "$SQUASH_BODY_FILE" ] && [ -r "$SQUASH_BODY_FILE" ] && [ -s "$SQUASH_BODY_FILE" ]; } \
  || { echo "#$N SQUASH_BODY_FILE is set but is not a readable, non-empty file (path withheld): stop, nothing merged"; exit 2; }
# 2026-10-10: same-change tolerance (as uet_land.sh). A head that is a pure rebase or merge-update of the read head
# (per-file changed lines identical, manifests/evidence.json excluded; CI arbitrates the registry) keeps the reads, and
# a BEHIND branch is updated server-side (gh pr update-branch, merge method) instead of waiting for a lane push.
G="git -C ${LANDING_NAS_REPO:-$HOME/code/native-agent-stack}"; COORD=${LANDING_COORD:-${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/coordination}
LG_GIT=$G; LG_EXCLUDE=':!manifests/evidence.json'
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
lg_author_email() {  # <owner/repo> : the account's no-reply address; rc 1 and nothing printed when the id is not a number
  local login=${1%%/*} id
  id=$(gh api "users/$login" --jq .id 2>/dev/null) || return 1
  case "$id" in ''|*[!0-9]*) return 1 ;; esac
  printf '%s+%s@users.noreply.github.com\n' "$id" "$login"
}
lg_author_check() {  # <owner/repo> <pr> <no-reply address> : after the merge, the merge commit's author is that address; prints text only, never the stored address
  local mc="" ok="" i
  for i in 1 2 3 4 5; do
    mc=$(gh pr view "$2" -R "$1" --json mergeCommit --jq '.mergeCommit.oid // empty' 2>/dev/null)
    [ -n "$mc" ] && break
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
lg_gate() {  # <gate> <owner/repo> <pr> <read head> : prints one line; returns 0, 3, 4 or 5
  local g gr q="'" re
  re="^(Codex review |Codex unavailable: |no Codex review |Codex gate error: )[A-Za-z0-9 :;,.()_+${q}-]*\$"
  g=$(python3 -I "$1" "$2" "$3" "$4" 2>&1); gr=$?
  case "$gr" in 0|3|4|5) ;; *) echo "Codex gate failed with exit $gr; details withheld"; return 4 ;; esac
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
# SQUASH_BODY_FILE (the CC, 2026-10-12; the scan is the P1 of #1027 at d6be1b02, Astra). The file becomes the squash commit's message in main's
# history for good, and gh sends the bytes it holds when the merge call starts (cli v2.102.0 pkg/cmd/pr/merge/merge.go:146-153 reads the file,
# :292-293 and http.go:72-75 send it as CommitBody; pkg/cmdutil/file_input.go:8-16), minutes after any check made here. So the file is copied
# once to a snapshot (mktemp under TMPDIR, mode 0600; the EXIT trap removes it on any exit, a signal included: measured, README), the snapshot is
# scanned, and the merge is given the snapshot, never the file. Two scans, both of the snapshot: squash_body_scan.py (the repository's
# PRIVATE_CONTENT table, a WSL UNC home path, an address that is no no-reply one, a name of the names file; the file is parsed there, never
# sourced) and scripts/validate.py --scan-file (PRIVATE_CONTENT and the runtime host-local names, the scan the pre-push hook runs; its answer
# counts only when it says source "host", never the synthetic override's). Both run with -E -s -B, as merge_validate runs validate.py: with -I
# the script's directory is off sys.path and validate.py cannot import host_name_scan.py (measured 2026-10-12: exit 2). Fail closed: a match,
# a copy that fails, a scanner or names file that is missing or unreadable, and any answer but a scan's own clean line stop the landing with
# exit 2 and one fixed line. No path, name, text or scanner output is printed, but one count: a name of the names file that is the host's own
# name is a warning, not a refusal (the CC's ruling of 2026-10-12); squash_body_scan.py counts it, and the count is printed as a number.
# Defaults: the scanner beside this script, validate.py in the clone of this repository (LANDING_NAS_REPO), the names file in the coordination tree.
lg_body_snapshot() {  # <file> : sets SB to the scanned snapshot and returns 0 only when both scans pass; else prints one fixed line and returns 2
  local here scan val names o r w why=cannot
  local clean_scan='^squash body scan: clean \(names_checked=[0-9]+(, warnings=([0-9]+))?\)$'
  local clean_cli='^\{"matching_locations": 0, "scanned_files": [0-9]+, "source": "host", "status": "passed"\}$'
  here=$(dirname "$(readlink -f -- "$0")")
  scan=${LANDING_BODY_SCAN:-$here/squash_body_scan.py}
  val=${LANDING_SCANNER:-${LANDING_NAS_REPO:-$HOME/code/native-agent-stack}/scripts/validate.py}
  names=${LANDING_NAMES_FILE:-$COORD/command-center/cc-tools/landing-prohibited-names.env}
  SB=$(mktemp "${TMPDIR:-/tmp}/squash-body-XXXXXX" 2>/dev/null) || SB=
  [ -n "$SB" ] || { echo "#$N SQUASH_BODY_FILE cannot be copied to a private snapshot (path withheld): stop, nothing merged"; return 2; }
  trap 'rm -f -- "$SB"' EXIT
  { cp -- "$1" "$SB" && chmod 600 -- "$SB" && [ -s "$SB" ]; } 2>/dev/null \
    || { echo "#$N SQUASH_BODY_FILE cannot be copied to a private snapshot (path withheld): stop, nothing merged"; return 2; }
  if [ -f "$scan" ] && [ -f "$val" ]; then
    o=$(python3 -E -s -B "$scan" "$SB" "$val" "$names" 2>/dev/null); r=$?
    if [ "$r" = 0 ] && [[ "$o" =~ $clean_scan ]]; then
      w=${BASH_REMATCH[2]:-0}
      o=$(python3 -E -s -B "$val" --scan-file "$SB" 2>/dev/null); r=$?
      if [ "$r" = 0 ] && [[ "$o" =~ $clean_cli ]]; then
        [ "$w" = 0 ] || echo "#$N SQUASH_BODY_FILE names this host's own name $w time(s): a warning, not a refusal (the name is not printed)"
        return 0
      fi
      [ "$r" = 1 ] && why=refused
    elif [ "$r" = 1 ] && [[ "$o" == "squash body scan: refused: "* ]]; then
      why=refused
    fi
  fi
  if [ "$why" = refused ]; then
    echo "#$N SQUASH_BODY_FILE holds text the publication scan refuses (details withheld; squash_body_scan.py names the classes and lines): stop, nothing merged"
  else
    echo "#$N SQUASH_BODY_FILE could not be scanned: a scanner or the names file is missing, unreadable or failed (details withheld): stop, nothing merged"
  fi
  return 2
}
# <<< land-gate-fns
# SQUASH_BODY_FILE: the snapshot and both scans (exit 2) come after the readability check above and before the lock and every git and gh call.
SB=
[ -z "${SQUASH_BODY_FILE:-}" ] || lg_body_snapshot "$SQUASH_BODY_FILE" || exit 2
lg_lock "${LANDING_LOCK_DIR:-$COORD/command-center/landing-locks}" || exit 14
$G fetch -q origin main "pull/$N/head" 2>/dev/null
EF=$($G rev-parse --verify -q "$E^{commit}" 2>/dev/null) || { $G fetch -q origin "$E" 2>/dev/null; EF=$($G rev-parse --verify -q "$E^{commit}" 2>/dev/null); }
[ -n "$EF" ] || { echo "#$N read head $E not resolvable: stop"; exit 3; }
# Correction #136: the identity of a change is git patch-id (verbatim, -U0, --binary) of its whole diff against its own merge base, manifests/evidence.json
# excluded (LG_EXCLUDE); an empty change is refused, and a change that is empty only because everything in it is excluded is identified by its file names.
change() { lg_change_id "$1"; }
same_change() { lg_same_change "$1" "$2"; }
# trading-cc posts a `trading-cc-read` commit status on its read head (from 2026-10-09T22:50Z), described
# "<VERDICT>: trading-cc/reads/<record>.md" (for example "PASS: …"). A failure blocks. A success counts only when that record exists and names
# the head with PASS or ACK, because a status carries no app identity (any holder of the owner token can post one).
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
# The verdict files (VF). #975 round 4 (Codex P1 at 761810d7): the files are mutable, so final_gate runs this again.
verdict_gate() {
  local v t why re='landing gate|path to pass|before landing|landing condition'
  for v in "${VF[@]}"; do
    # #975 P2-C: a verdict file is named by its file name only (its directory can be under a home directory).
    [ -f "$v" ] || { echo "#$N verdict file missing: ${v##*/}"; exit 2; }
    # #975 round 4 (GPT P2 at 761810d7): the file is read once, and its verdict and its landing-gate phrases are both decided on that text.
    t=$(lg_text "$v") || { echo "#$N verdict ${v##*/} is unreadable: stop"; exit 2; }
    # Correction #136: line 1 "...${EF:0:8}...: ACK|PASS" (the Astra layout) or a Gate line/Verdict line "PASS|ACK at ${EF:0:8}"; CHANGES_REQUESTED on either rejects,
    # and a PASS/ACK anywhere else in the file counts for nothing.
    why=$(lg_verdict_text_ok "$t" "${EF:0:8}") || { echo "#$N verdict ${v##*/} is not an accepted PASS/ACK verdict for ${EF:0:8} ($why): stop"; exit 2; }
    # Correction #121: a record that states a landing gate needs a receipt for it (GATES_DONE=<receipt naming the head>). #975 (Codex P2 at
    # af9d1901): the receipt names the RESOLVED head's eight characters, as the verdicts do; ${E:0:8} was the caller's prefix, which can be shorter.
    if [[ "${t,,}" =~ $re ]]; then
      lg_receipt_ok "${GATES_DONE:-}" "${EF:0:8}" \
        || { echo "#$N verdict ${v##*/} states a landing gate: set GATES_DONE=<receipt naming ${EF:0:8}> after running it"; exit 2; }
    fi
  done
}
# The check runs at a head as one tab-separated line: incomplete, failing, total, validate successes.
# 2026-10-10: the aggregate `validate` check must have SUCCEEDED at this head. A DIRTY PR runs only CodeQL and Socket,
# so "every check green" alone could pass on a handful of early checks (trading-cc on #940).
# #975 P2-3 (2026-10-11): a completed check fails unless its conclusion is success, neutral or skipped (fail closed). GitHub's GraphQL
# CheckConclusionState (schema.docs.graphql sha256 3ed09565…, lines 3974-4018) also has stale and startup_failure, which REST
# rest-api-description@58b1e0c0 omits from its check-run enum; the old list counted those, and action_required on uet, as passing.
# #975 round 4 (Codex P1 at 761810d7, the CC's P3-1): a check name is incomplete while ANY of its runs is not completed, and its failure
# was judged on its latest COMPLETED run until A1, below (2026-10-09 #886: superseded, concurrency-cancelled runs must not fail it).
# Before, the latest run per name was max_by(.started_at), and a queued re-run has started_at null (rest-api-description@58b1e0c0
# check-run.started_at "nullable": true), which sorts first, so an old success hid it.
# #975 final round (Astra's follow-up 1 at 5b8ba3b2, ruled FIX-NOW): max_by([.started_at // "", .id // 0]) still let a COMPLETED failing
# re-run with started_at null lose to an older success. The runs are read with filter=latest ("Filters check runs by their `completed_at`
# timestamp. `latest` returns the most recent check runs", rest-api-description@58b1e0c0 api.github.com.json:55504-55514). Both
# timestamps are nullable (:146097-146107), so a name fails closed, counted incomplete, when a completed run has no completed_at.
# #975 A1 (the CC's Claude micro at 3e6e7e46): a name judged on its newest completion alone passed when a failing run that started later
# and finished first overlapped a success that finished last (input F; start order passed the mirror, input G, at 5b8ba3b2). A name fails
# when one of its completed runs ended other than success, neutral or skipped and no run of that name both started and completed after it
# (#886's superseded cancellations still pass). A run without started_at or completed_at supersedes nothing, since jq orders null
# before every string (jq 1.8.1 docs/content/manual/v1.8/manual.yml:1544-1552, :2425-2433), and a failing run without them is
# superseded by nothing. Runs that share a completed_at pass when each passes (the micro's P3-2: success and neutral waited for the
# timeout) and fail at once when one fails (P3-1). validate counts when it is complete, not failing, and a run with its greatest
# completed_at succeeded.
# #975 (Codex P2 at nas:289): every page is read. gh api --paginate follows the Link header's rel="next" and keeps the per_page given
# (cli v2.102.0 pkg/cmd/api/pagination.go:17-24, :94-110; api.go:431-470); --slurp puts the pages in one array and refuses --jq
# (api.go:260-273, :362-371), so jq itself judges the flattened runs (the jq the tests run; gh's --jq is go-gh's gojq, go.mod:21, :141).
# gh's exit code is checked before jq reads: a failed page's body lands in the array too (api.go:546, :553-565).
# #975 P2-B (GPT micro at af9d1901): a failed call's stdout can be an error body (above), which the old line word-split into the counts:
# bash then printed a body word in "integer expected", and a one-word body ended the script on an unbound $4. Now a failed call, or a
# reply that is not exactly four counts, counts as one check still running, so the loop polls on (exit 6 at the timeout).
nas_checks() {  # <head>
  local p c
  p=$(gh api "repos/$R/commits/$1/check-runs?filter=latest&per_page=100" --paginate --slurp 2>/dev/null) \
    && c=$(printf '%s' "$p" | jq -r '[.[].check_runs[]|{name,status,conclusion,started_at,completed_at}]|group_by(.name)|map([.[]|select(.status == "completed")] as $done|($done|map(.completed_at)|max) as $t|{name: .[0].name, incomplete: (any(.[]; .status != "completed") or any($done[]; .completed_at == null)), failing: any($done[]; . as $f|((.conclusion=="success" or .conclusion=="neutral" or .conclusion=="skipped")|not) and ((.started_at != null and .completed_at != null and any($done[]; .started_at > $f.started_at and .completed_at > $f.completed_at))|not)), newest: [$done[]|select(.completed_at == $t)|.conclusion]})|[([.[]|select(.incomplete)]|length), ([.[]|select(.failing)]|length), length, ([.[]|select(.name=="validate" and (.incomplete|not) and (.failing|not) and any(.newest[]; . == "success"))]|length)]|@tsv' 2>/dev/null) \
    && [[ "$c" =~ ^[0-9]+$'\t'[0-9]+$'\t'[0-9]+$'\t'[0-9]+$ ]] || c=$'1\t0\t0\t0'
  echo "$c"
}
# Early refusals, cheap first reads: the head, the trading-cc-read gate, the verdict files.
cur=$(gh pr view "$N" -R $R --json headRefOid --jq .headRefOid 2>/dev/null); lg_hex40 "$cur" || cur=
lg_have "$cur"
if [ "$cur" != "$EF" ]; then
  same_change "$EF" "$cur" || { echo "#$N head ${cur:0:8} is neither the read head ${EF:0:8} nor the same change: stop"; exit 3; }
  echo "#$N head ${cur:0:8} carries the read head ${EF:0:8} (same change)"
fi
tcc_read_gate "$EF"
verdict_gate
# Corrections #122 and #123 (GHA audit T9): a Codex review starts when a PR opens, when a draft is marked ready (by
# anyone) and on an "@codex review" comment; uet#40 and uet#47 merged while one was pending or Running. A draft is
# marked ready first, then codex_gate.py must report the latest review finished (exit 0); running or not yet started
# is polled for up to 20 minutes (exit 9 after that, or when a review ends other than Completed). Its findings become
# threads, which BLOCK below. The gate runs again before the validation, so a review that reopened does not wait for it, and in final_gate.
GATE=${LANDING_GATE:-$(dirname "$(readlink -f -- "$0")")/codex_gate.py}
codex_wait() {
  local j g gr
  for j in $(seq 1 21); do
    g=$(lg_gate "$GATE" "$R" "$N" "$EF"); gr=$?
    { [ $gr = 0 ] || [ $gr = 5 ]; } && { echo "#$N $g"; return 0; }
    [ $gr = 3 ] && [ $j -lt 21 ] && { sleep 60; continue; }
    echo "#$N $g: stop, land after Codex finishes"; exit 9
  done
}
# #975 P3-4: a missing gate is one fixed line (python3 would print its path), before anything is marked ready.
[ -f "$GATE" ] || { echo "#$N codex_gate.py not found (path withheld): stop"; exit 9; }
# 2026-10-10 (co-op's GPT micro on #923): a PR whose CI ran before a newer main can squash-merge a stale
# manifests/evidence.json registration and turn main red (#923 after #937). Before the merge: a temporary detached
# worktree at the CURRENT origin/main, a no-commit merge of the head, and scripts/validate.py must exit 0 there (the 5f
# landing rule of 10-09). Exit 10 otherwise: a native rebase with re-registration is needed.
# #975 (Codex P2 and GPT P2-C at af9d1901, 2026-10-11): validate.py's output is free text, so it is not printed. It goes to a file that mktemp
# makes under TMPDIR (mode 0600), outside the worktree, so it outlives the worktree's removal, and exit 10 names that file and the exit code.
# VBASE is the main the validation ran on.
# CC correction #176 (2026-10-12): two PRs, each green on its own base, left main red when one changed a source of a generated artifact
# that the other had bound (#1018 after #1007: final-stack.json), and validate.py does not run that check. After validate.py, the merge
# runs validate.yml's shard-0 currency checks in the workflow's order (validate.yml:135-177), each only when its script is in the merge:
# every shard-0 step that runs a Python script with --check, the gap-wave ledger's included (the CC's ruling of 2026-10-12; #176 had
# left it out). A failing check is exit 10 as well, named by its command, its output kept as validate.py's is.
merge_validate() {
  local wt rc err chk what=validate.py
  VBASE=
  $G fetch -q origin main "pull/$N/head" 2>/dev/null || { echo "#$N fetch failed: stop"; return 1; }
  wt=$(mktemp -d /var/tmp/nas-land-$N-XXXXXX 2>/dev/null) || { echo "#$N no temporary directory for the validation worktree: stop"; return 1; }
  $G worktree add -q --detach "$wt" origin/main >/dev/null 2>&1 || { echo "#$N worktree add failed: stop"; rmdir "$wt" 2>/dev/null; return 1; }
  VBASE=$(git -C "$wt" rev-parse HEAD 2>/dev/null)
  if ! git -C "$wt" merge -q --no-commit --no-ff "$1" >/dev/null 2>&1; then
    echo "#$N does not merge cleanly onto main $(git -C "$wt" rev-parse --short HEAD 2>/dev/null): a native rebase is needed: stop"
    git -C "$wt" merge --abort >/dev/null 2>&1; $G worktree remove --force "$wt" >/dev/null 2>&1; return 1
  fi
  err=$(mktemp "${TMPDIR:-/tmp}/nas-validate-XXXXXX" 2>/dev/null) || err=/dev/null
  (cd "$wt" 2>/dev/null && python3 -E -s -B scripts/validate.py >"$err" 2>&1); rc=$?
  if [ "$rc" = 0 ]; then
    for chk in "blueprints/blind-catalog-convergence/audit_reports.py --check" "tools/sota-convergence/build_verdicts.py --check" \
               "scripts/component_matrix.py --check" "scripts/new_host_grand_list.py --check" "scripts/final_stack.py --check" \
               "tools/sota-convergence/gap_crosswalk.py build --check" \
               "tools/sota-convergence/gap_wave_ledger.py --wave gap-wave2-20260923 --wave gap-wave3-20260923 --owner gap-resolution --check" \
               "scripts/build_ecosystem.py --check"; do
      [ -f "$wt/${chk%% *}" ] || continue
      what="the currency check $chk"
      (cd "$wt" 2>/dev/null && python3 -E -s -B $chk >"$err" 2>&1); rc=$?
      [ "$rc" = 0 ] || break
    done
  fi
  git -C "$wt" merge --abort >/dev/null 2>&1; $G worktree remove --force "$wt" >/dev/null 2>&1
  if [ "$rc" != 0 ]; then
    [ "$err" = /dev/null ] && { echo "#$N $what on the merge with current main exited $rc; its output could not be kept, and is not echoed: stop"; return 1; }
    echo "#$N $what on the merge with current main exited $rc; its output is kept only in local file ${err##*/} in the temp directory (0600), never echoed: stop"; return 1
  fi
  [ "$err" = /dev/null ] || rm -f -- "$err"
  echo "#$N the merge onto current main validates (rc 0: validate.py and the shard-0 currency checks whose scripts it holds)"; return 0
}
# #975 round 4 (the CC's micro at 761810d7: each gate could change between its last read and the merge, and each round-3 fix left the next
# gap): after every slow step, final_gate reads every gate again, fast reads only and in this order, and nothing but the merge follows it:
# the head (the pinned head, carrying the read head's change), the verdict files and GATES_DONE, trading-cc-read (a failed read stops),
# the Codex gate (a 5 proceeds, as at the wait), the check runs at the head (complete, green, validate succeeded), and origin/main, which
# must still be the main the merge was validated on (git ls-remote; --match-head-commit pins only the head). Any failure stops with that
# gate's exit code. What the reads cannot close is in the README ("What the final gate can and cannot close").
final_gate() {  # <pinned head>
  local hd c g gr now
  hd=$(gh pr view "$N" -R $R --json headRefOid --jq .headRefOid 2>/dev/null); lg_hex40 "$hd" || hd=
  [ "$hd" = "$1" ] || { echo "#$N head moved to ${hd:-?} at the final gate: stop"; exit 3; }
  same_change "$EF" "$hd" || { echo "#$N CHANGE DIFFERS between read head ${EF:0:8} and head ${hd:0:8} at the final gate: stop"; exit 4; }
  verdict_gate
  tcc_read_gate "$EF"
  g=$(lg_gate "$GATE" "$R" "$N" "$EF"); gr=$?
  { [ $gr = 0 ] || [ $gr = 5 ]; } || { echo "#$N $g at the final gate: stop"; exit 9; }
  c=$(nas_checks "$hd"); set -- $c
  [ "$1" = 0 ] && [ "$2" = 0 ] && [ "$3" -gt 0 ] && [ "$4" -gt 0 ] \
    || { echo "#$N CI at ${hd:0:8} is no longer complete and green at the final gate (incomplete=$1, failing=$2 of $3, validate successes $4): stop"; exit 5; }
  now=$($G ls-remote origin refs/heads/main 2>/dev/null | cut -f1)
  # #975 P3-4 (the CC's micro at 761810d7): an unreadable main is its own stop, not "main moved".
  lg_hex40 "$now" || { echo "#$N origin/main is unreadable (git ls-remote failed) at the final gate: stop, nothing merged"; exit 13; }
  [ "$now" = "$VBASE" ] || { echo "#$N origin/main moved after the validation on ${VBASE:0:8} (final gate): stop, nothing merged"; exit 13; }
  echo "#$N final gate at ${hd:0:8}: head, change, verdict files, trading-cc-read, Codex, check runs and origin/main read again (CI $3 ok)"
}
# Slow steps: update-branch, ready, the Codex wait, the CI wait, the validations, the author address.
if [ "$(gh pr view "$N" -R $R --json mergeStateStatus --jq .mergeStateStatus 2>/dev/null)" = BEHIND ]; then
  gh pr update-branch "$N" -R $R >/dev/null 2>&1 || { echo "#$N update-branch refused (conflict?): a native rebase is needed: stop"; exit 4; }
  sleep 8; $G fetch -q origin main "pull/$N/head" 2>/dev/null
  cur=$(gh pr view "$N" -R $R --json headRefOid --jq .headRefOid 2>/dev/null); lg_hex40 "$cur" || cur=; lg_have "$cur"
  same_change "$EF" "$cur" || { echo "#$N CHANGE DIFFERS after update-branch (${cur:0:8}): stop"; exit 4; }
  echo "#$N updated to ${cur:0:8} on main (same change)"
fi
if [ "$(gh pr view "$N" -R $R --json isDraft --jq .isDraft 2>/dev/null)" = true ]; then
  gh pr ready "$N" -R $R >/dev/null 2>&1 || { echo "#$N could not be marked ready"; exit 7; }
  echo "#$N marked ready at $(date -u +%FT%TZ)"; sleep 20
fi
codex_wait
follows=0; ci=
for i in $(seq 1 25); do
  # Judge the LATEST completed check run per name at this head: superseded runs (concurrency-cancelled duplicates) must not
  # count as failures (2026-10-09 #886: 10 CANCELLED plus 1 FAILURE from a superseded run while mergeState was CLEAN).
  hd=$(gh pr view "$N" -R $R --json headRefOid --jq .headRefOid 2>/dev/null); lg_hex40 "$hd" || hd=
  ms=$(gh pr view "$N" -R $R --json mergeStateStatus --jq .mergeStateStatus 2>/dev/null); [[ "$ms" =~ ^[A-Z_]+$ ]] || ms=
  c=$(nas_checks "$hd")
  set -- "$hd" $c "$ms"
  vok=${5:-0}; ms=${6:-}; set -- "$1" "$2" "$3" "$4" "$ms"
  if [ "${1:-}" != "$cur" ]; then
    lg_follow_head "$EF" "${1:-}" "$follows" || { echo "#$N head moved to ${1:-?}: stop"; exit 3; }
    echo "#$N head moved to ${1:0:8} and carries the read head's change: following it"
    cur=$1; follows=$((follows + 1)); sleep 20; continue
  fi
  if [ "${2:-1}" = 0 ] && [ "${4:-0}" -gt 0 ] && { [ "${vok:-0}" -gt 0 ] || [ "${3:-0}" -gt 0 ]; }; then
    [ "$3" = 0 ] || { echo "#$N CI failing=$3 of $4: stop"; exit 5; }
    [ "${5:-}" = BLOCKED ] && { echo "#$N BLOCKED by policy with CI green (open threads or required review): stop"; exit 8; }
    g=$(lg_gate "$GATE" "$R" "$N" "$EF"); gr=$?; { [ $gr = 0 ] || [ $gr = 5 ]; } || { echo "#$N $g before the validation: stop"; exit 9; }
    ci=$4; break
  fi
  sleep 120
done
[ -n "$ci" ] || { echo "#$N CI timeout"; exit 6; }
# #975 (Codex P2 at af9d1901, 2026-10-11): --match-head-commit pins only the head ("Commit SHA that the pull request head must match to
# allow merge", gh pr merge manual; GraphQL MergePullRequestInput.expectedHeadOid), so a main that moved after the validation would take a
# merge validated on the old one. main is read again (git ls-remote) after each validation; a move validates again, at most three
# validations in all (exit 13 after that), and final_gate reads it once more.
for v in 1 2 3; do
  merge_validate "$cur" || exit 10
  now=$($G ls-remote origin refs/heads/main 2>/dev/null | cut -f1)
  # #975 P3-4 (the CC's micro at 761810d7): an unreadable main is its own stop, not "main moved".
  lg_hex40 "$now" || { echo "#$N origin/main is unreadable (git ls-remote failed) after the validation: stop, nothing merged"; exit 13; }
  lg_hex40 "$VBASE" && [ "$now" = "$VBASE" ] && break
  [ "$v" -lt 3 ] || { echo "#$N origin/main moved after each of 3 validations: stop, nothing merged"; exit 13; }
  echo "#$N origin/main moved after the validation on ${VBASE:0:8}: validating again on the current main"
done
ae=$(lg_author_email "$R") || { echo "#$N cannot form the no-reply author address (correction #148): stop, nothing merged"; exit 11; }
final_gate "$cur"
out=$(gh pr merge "$N" -R $R --squash --match-head-commit "$cur" -A "$ae" ${SB:+--body-file "$SB"} 2>&1) || { cls=$(printf '%s' "$out" | grep -o -i -E 'not mergeable|head branch was modified|required status check|review|draft|merge conflict|protected branch|rate limit|authentication|not found' | head -1 | tr 'A-Z ' 'a-z_'); mf=$(lg_keep merge-fail "$out") && kept="gh output kept only in local file $mf in the temp directory (0600), never echoed" || kept="gh output could not be kept, and is not echoed"; echo "#$N merge failed (class: ${cls:-other}); $kept (#975 P2-2)"; exit 7; }
sleep 4
echo "#$N $(gh pr view "$N" -R $R --json state,mergeCommit,mergedAt --jq '"\(.state) \(.mergeCommit.oid) \(.mergedAt)"' 2>/dev/null) (CI $ci ok)"
lg_author_check "$R" "$N" "$ae" || exit 12
exit 0
}
