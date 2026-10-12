"""Offline tests of the landing scripts in tools/landing: uet_land.sh, nas_land.sh and codex_gate.py.

The scripts merge pull requests, so they are never pointed at GitHub here. Correction #136 (2026-10-10) tested their decision points
with a harness that cuts the decision text out of each script and evaluates it in bash against synthetic inputs and a fake `gh`.
This module is that harness's offline subset, kept beside the one copy of the scripts:

  * verdict files and the GPT_VERDICT block (lg_verdict_file_ok: the harness's 28 synthetic files and six more) and the GATES_DONE rule;
  * the trading-cc-read gate (tcc_read_gate): the description form, the record's last verdict line, the status states, a status behind
    100 newer statuses of other contexts and replies that cannot be read (#975, Codex P1 at nas:234: the combined status, every page);
  * change identity (lg_change_id, lg_same_change) against scratch repositories: binary bytes, mode, names, `--` and `++` lines;
  * the CI line: uet's lg_ci_state on synthetic rollups and nas's check-run line, and both against every member of GitHub's
    CheckConclusionState in a captured schema excerpt (tests/fixtures/landing/check-conclusion-state.json) and null, and uet's
    commit statuses against every member of StatusState (tests/fixtures/landing/status-state.json), a state it does not list and none;
  * codex_gate.py: its exit-code precedence on canned API data (subprocess.run and datetime.now are patched), the connector's summary
    comment of nas#975 as the gate's own query returned it (tests/fixtures/landing/codex-summary-comment.json), and the script run as
    the landing scripts run it, where a failure prints one fixed line and exits 4;
  * #975 round 4: the final gate's reads as the last calls before the merge, each gate flipped between its first read and the final
    gate (its exit code, no merge), the landing lock, and verdict files, records and receipts that cannot be read;
  * each script end to end with a fake gh, python3 and sleep: the variables and their defaults, the gate path through a symlink and
    a wrapper, the order in which the gates stop a landing, a failed merge and a failing gh call at each call site (#975 P2-2), none
    of which may print what gh or its API returned;
  * #1027: the squash body's publication scan: SQUASH_BODY_FILE is copied to a private snapshot, which squash_body_scan.py (home paths
    of every form, names, addresses, token shapes) and validate.py --scan-file scan, and which the merge is given; a match, a missing
    or failing scanner and a file that changes after the scan end as the README says, and squash_body_scan.py itself is tested; round 2
    adds quoted and prefixed local parts and addresses before a unit type, each read first by CPython's RFC 5322 parser, the oracle;
  * the files under tools/landing: no home path and no form of an identity that must not appear, which is the running account (a
    generic CI account may stand as a bare word) and every name in LANDING_PROHIBITED_NAMES, none skipped for its length (#975 P2-1),
    and the README's digests.

A decision site is cut out by the same start and end lines the harness used, so an edit that moves a site fails here loudly instead
of leaving it untested. Everything but the captured schema excerpts and summary comment is synthetic: no network, no gh, no cache files. `jq` is required
(the runners have it); when it is missing the module fails in CI and is skipped elsewhere. The scripts are Linux tools (GNU sha256sum
and readlink -f).
"""
from __future__ import annotations

import base64
import contextlib
import fnmatch
import getpass
import hashlib
import importlib.util
import io
import itertools
import json
import os
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from email import _header_value_parser, errors as email_errors
from pathlib import Path
from unittest import mock

import tests
from scripts import host_name_scan

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "tools/landing"
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI", "").lower() == "true"
HEAD = "3d8c6344a0e2150d296d84bacff48bc394180e92"
OTHER = "9f8e7d6c5b4a39281706f5e4d3c2b1a098765432"
NOREPLY = "4242424+seathatflowsinourveins@users.noreply.github.com"  # the fake gh serves id 4242424 for the repository owner
PR = str(90000000 + os.getpid())  # per process: the nas script makes /var/tmp/nas-land-<pr>-XXXXXX worktrees, which parallel runs must not share
UET_REPO = "seathatflowsinourveins/us-equities-trading"
NAS_REPO = "seathatflowsinourveins/native-agent-stack"
# #975 P2-3: GitHub's CheckConclusionState as captured from its published GraphQL schema, with the REST description's check-run enum
CONCLUSIONS = ROOT / "tests/fixtures/landing/check-conclusion-state.json"
PASSING_CONCLUSIONS = ("SUCCESS", "NEUTRAL", "SKIPPED")  # the scripts' allow-list; any other completed conclusion, null included, fails
# #975 P3: GitHub's StatusState (uet reads commit statuses), captured the same way; only SUCCESS passes, PENDING and EXPECTED are running
STATUSES = ROOT / "tests/fixtures/landing/status-state.json"
RUNNING_STATES = ("PENDING", "EXPECTED")
UNLISTED_STATE = "FUTURE_STATE"  # synthetic: a state GitHub may add to StatusState later; the script must fail closed on it
ADDRESS = "api-text-4e9b@example.invalid"  # synthetic: stands for an address that a status description or a gh or API diagnostic could carry
# CC correction #176 (2026-10-12): the currency checks of validate.yml's shard 0 that nas's validation runs after validate.py, in that
# order: every shard-0 step that runs a Python script with --check (the CC's ruling of 2026-10-12 added the gap-wave ledger's)
CURRENCY_CHECKS = ("blueprints/blind-catalog-convergence/audit_reports.py --check", "tools/sota-convergence/build_verdicts.py --check",
                   "scripts/component_matrix.py --check", "scripts/new_host_grand_list.py --check", "scripts/final_stack.py --check",
                   "tools/sota-convergence/gap_crosswalk.py build --check",
                   "tools/sota-convergence/gap_wave_ledger.py --wave gap-wave2-20260923 --wave gap-wave3-20260923 --owner gap-resolution --check",
                   "scripts/build_ecosystem.py --check")


def shard_0_python_checks(workflow):
    """The commands, without `python3 `, of the workflow's shard-0 steps that run `python3 <script>.py ... --check`, in their order. A
    step's run is one line or a folded `>-` block, whose lines YAML joins with spaces; a literal `|` block is a script, not one command."""
    commands = []
    for step in re.split(r"^      - ", Path(workflow).read_text(encoding="utf-8"), flags=re.M)[1:]:
        if not re.search(r"^        if: matrix\.shard == 0$", step, re.M):
            continue
        single = re.search(r"^        run: (?![>|])(.+)$", step, re.M)
        folded = re.search(r"^        run: >-\n((?:          \S.*\n?)+)", step, re.M)
        run = single.group(1) if single else " ".join(line.strip() for line in folded.group(1).splitlines()) if folded else ""
        found = re.fullmatch(r"python3 (\S+\.py(?: .+)? --check)", run)
        if found:
            commands.append(found.group(1))
    return tuple(commands)


def setUpModule():
    if not sys.platform.startswith("linux"):
        raise unittest.SkipTest("the landing scripts run on the CC's Linux host and need GNU sha256sum and readlink -f")
    missing = [tool for tool in ("bash", "git", "jq", "sha256sum", "readlink", "dirname", "grep", "seq", "flock")
               if shutil.which(tool) is None]
    if subprocess.run(["git", "patch-id", "--verbatim"], input="", capture_output=True, text=True).returncode != 0:
        missing.append("git patch-id --verbatim")
    if missing:
        message = f"the landing-script tests need {', '.join(missing)}"
        if IN_CI:
            raise AssertionError(message)
        raise unittest.SkipTest(message)


def q(path):
    return "'" + str(path).replace("'", "'\\''") + "'"


# ---------------------------------------------------------------------------------------------- fake commands
# GitHub-side data are JSON files named by FAKE_STATUSES, FAKE_CHECKRUNS and FAKE_PRVIEW; the scripts' own --jq programs are
# evaluated on them by jq, so the real programs run. Every call is appended to FAKE_LOG. FAKE_STATUSES lists the statuses as REST does,
# newest first (github/rest-api-description@58b1e0c0 api.github.com.json:55724); a read of that list gets its page 1, the first per_page
# (default 30, :344577-344585). #975 (Codex P1 at nas:234): the combined status (.../status, :55664-55667) is built from FAKE_STATUSES as
# GitHub gave it when measured on 2026-10-11: each context once with its newest status, in pages of per_page contexts. #975 (Codex P2 at
# nas:289): FAKE_CHECKRUNS is one page or a list of pages. `gh api --paginate --slurp` prints every page in one array (cli v2.102.0
# pkg/cmd/api/api.go:362-371), which the scripts give to jq themselves, and a call without them gets page 1, as a request without
# pagination does.
# #975 P2-2: FAKE_FAIL (a glob on the arguments) makes the matching calls fail from the FAKE_FAIL_FROM-th (default 1) on: exit 1,
# FAKE_FAIL_STDERR on stderr and FAKE_FAIL_STDOUT on stdout. As gh does (cli v2.102.0), `gh api` puts an error response's body on
# stdout and "gh: <message>" on stderr (pkg/cmd/api/api.go:546, :557), every other command prints its error only to stderr
# (internal/ghcmd/cmd.go:214, :285); a test sets FAKE_FAIL_STDOUT for `api` calls only.
# #975 round 4: FAKE_GH_HOOK runs (sh -c) before every call that matches the glob FAKE_GH_HOOK_ON, so a test can change GitHub-side or
# local data at one step (the flip suite does it at the author-address lookup, the last slow step before final_gate). `gh api graphql`
# answers only the review-thread count; any other query fails, as for a gate that runs against this fake.
# SQUASH_BODY_FILE (the CC, 2026-10-12): FAKE_MERGE_ARGV, when set, names a file that `gh pr merge` writes its arguments to, each ended
# by a NUL byte, so a test sees argument boundaries that FAKE_LOG's one line cannot show (a body file whose path has a space).
# #1027: FAKE_MERGE_BODY, when set, names a file that `gh pr merge` copies its --body-file argument to when the call starts, as gh reads
# it (cli v2.102.0 pkg/cmd/pr/merge/merge.go:146-153), and records that file's mode beside it; the scripts delete their snapshot on exit.
FAKE_GH = r'''#!/usr/bin/env bash
[ -n "${FAKE_LOG:-}" ] && printf 'gh %s\n' "$*" >> "$FAKE_LOG"
if [ -n "${FAKE_GH_HOOK:-}" ] && [[ "$*" == ${FAKE_GH_HOOK_ON:-} ]]; then sh -c "$FAKE_GH_HOOK"; fi
if [ -n "${FAKE_FAIL:-}" ] && [ -n "${FAKE_LOG:-}" ] && [[ "$*" == $FAKE_FAIL ]]; then
  failed=$(cat "$FAKE_LOG.fail" 2>/dev/null || echo 0); failed=$((failed + 1)); echo "$failed" > "$FAKE_LOG.fail"
  if [ "$failed" -ge "${FAKE_FAIL_FROM:-1}" ]; then
    [ -z "${FAKE_FAIL_STDOUT:-}" ] || printf '%s\n' "$FAKE_FAIL_STDOUT"
    [ -z "${FAKE_FAIL_STDERR:-}" ] || printf '%s\n' "$FAKE_FAIL_STDERR" >&2
    exit 1
  fi
fi
prog=
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  if [ "${args[i]}" = "--jq" ]; then prog=${args[i+1]}; fi
done
case "$1 $2" in
  "api repos/"*)
    case "$2" in
      *"/statuses"*|*"/status?"*)
        pp=$(printf '%s\n' "$2" | sed -n 's/.*[?&]per_page=\([0-9][0-9]*\).*/\1/p'); pp=${pp:-30}
        if [[ "$2" == *"/statuses"* ]]; then jq --argjson pp "$pp" '.[:$pp]' "$FAKE_STATUSES" | jq -r "$prog"; exit; fi
        # the combined status: each context once, its newest status (the first listed), in pages of per_page contexts; FAKE_COMBINED_RAW,
        # when set (empty included), is the reply instead, with exit 0
        if [ -n "${FAKE_COMBINED_RAW+set}" ]; then printf '%s' "$FAKE_COMBINED_RAW"; exit 0; fi
        pages=$(jq -c --argjson pp "$pp" '(reduce .[] as $s ([]; if any(.[]; .context == $s.context) then . else . + [$s] end)) as $c
                 | [range(0; [($c | length), 1] | max; $pp) as $i | {total_count: ($c | length), statuses: $c[$i:$i + $pp]}]' "$FAKE_STATUSES") || exit 1
        if [[ " $* " == *" --paginate "* && " $* " == *" --slurp "* ]]; then printf '%s\n' "$pages"; exit 0; fi
        printf '%s\n' "$pages" | jq '.[0]' | jq -r "$prog" ;;
      *"/check-runs"*)  # one page (an object) or a list of pages; --paginate --slurp gets them all in one array, any other call page 1
        if [[ " $* " == *" --paginate "* && " $* " == *" --slurp "* ]]; then exec jq -c 'if type == "array" then . else [.] end' "$FAKE_CHECKRUNS"; fi
        jq 'if type == "array" then .[0] else . end' "$FAKE_CHECKRUNS" | jq -r "$prog" ;;
      *"/commits/"*) printf '{"commit":{"author":{"email":"%s"}}}' "${FAKE_COMMIT_EMAIL-4242424+seathatflowsinourveins@users.noreply.github.com}" | jq -r "$prog" ;;
      *) exit 1 ;;
    esac ;;
  "api users/"*) [ "${FAKE_USER_RC:-0}" = 0 ] || exit "$FAKE_USER_RC"; echo "${FAKE_USER_ID-4242424}"; exit 0 ;;
  "api graphql") [[ "$*" == *reviewThreads* ]] || exit 1; echo "${FAKE_OPEN_THREADS:-0}"; exit 0 ;;
  "pr view")
    if [ -n "${FAKE_HEADS:-}" ] && [[ "$*" == *headRefOid* ]]; then
      heads=($FAKE_HEADS); n=$(cat "$FAKE_LOG.heads" 2>/dev/null || echo 0); echo $((n + 1)) > "$FAKE_LOG.heads"
      jq --arg h "${heads[$(( n < ${#heads[@]} ? n : ${#heads[@]} - 1 ))]}" '.headRefOid = $h' "$FAKE_PRVIEW" | jq -r "$prog"
      exit "${PIPESTATUS[1]}"
    fi
    exec jq -r "$prog" "$FAKE_PRVIEW" ;;
  "pr ready") exit 0 ;;
  "pr update-branch") exit "${FAKE_UPDATE_RC:-0}" ;;
  "pr merge") [ -z "${FAKE_MERGE_ARGV:-}" ] || printf '%s\0' "$@" > "$FAKE_MERGE_ARGV"
              if [ -n "${FAKE_MERGE_BODY:-}" ]; then  # the body file as the merge call finds it: its bytes, and its mode in "$FAKE_MERGE_BODY.mode"
                for ((i = 0; i < ${#args[@]}; i++)); do
                  [ "${args[i]}" != "--body-file" ] || { cp -- "${args[i+1]}" "$FAKE_MERGE_BODY"; stat -c %a "${args[i+1]}" > "$FAKE_MERGE_BODY.mode"; }
                done
              fi
              printf '%s\n' "${FAKE_MERGE_STDOUT-merged}"; [ -z "${FAKE_MERGE_STDERR:-}" ] || printf '%s\n' "$FAKE_MERGE_STDERR" >&2
              exit "${FAKE_MERGE_RC:-0}" ;;
  *) exit 1 ;;
esac
'''
# codex_gate.py and scripts/validate.py both run as `python3 ...` in the scripts; the log shows which path each call got.
# FAKE_REAL_PYTHON, when set, runs the real codex_gate.py with that interpreter instead of the canned answer (its gh is the fake gh).
# #975 round 3: FAKE_GATE_HOOK runs before each gate call's answer and FAKE_VALIDATE_HOOK before each validation's, so a test can change
# GitHub-side data (a status, a record, origin's main) while a landing waits; FAKE_VALIDATE_OUT is the validation's output.
# CC correction #176 (2026-10-12): a currency check that nas's validation runs after validate.py (`... <script> [build] --check`) is
# answered here and never by the gate's answers below: exit 0, or, when its arguments match the glob FAKE_CHECK_FAIL, FAKE_CHECK_OUT and
# exit FAKE_CHECK_RC (default 1). FAKE_VALIDATE_HOOK runs in the validation's worktree, so it can put a check's script in the merge.
# #1027: the squash body's scans run before the lock, and both of their command lines name scripts/validate.py, so they are answered first.
# squash_body_scan.py (whatever file of that name) runs with the interpreter FAKE_BODY_SCAN_PYTHON, and gets the gate's canned answer, which is
# no clean answer of its own, when that is unset. `validate.py --scan-file` runs with FAKE_VALIDATE_SCAN_PYTHON when that is set (the real scanner,
# which needs Betterleaks); else it answers FAKE_SCAN_OUT (a clean JSON line when unset) and exits FAKE_SCAN_RC (default 0). FAKE_REAL_PYTHON is
# not used for either: it makes the gate real too.
FAKE_PYTHON3 = r'''#!/usr/bin/env bash
printf 'python3 %s\n' "$*" >> "$FAKE_LOG"
case "$*" in
  *squash_body_scan.py*) [ -z "${FAKE_BODY_SCAN_PYTHON:-}" ] || exec "$FAKE_BODY_SCAN_PYTHON" "$@" ;;
  *--scan-file*) [ -z "${FAKE_VALIDATE_SCAN_PYTHON:-}" ] || exec "$FAKE_VALIDATE_SCAN_PYTHON" "$@"
                 if [ -n "${FAKE_SCAN_OUT+set}" ]; then printf '%s' "$FAKE_SCAN_OUT"
                 else printf '{"matching_locations": 0, "scanned_files": 1, "source": "host", "status": "passed"}\n'; fi
                 exit "${FAKE_SCAN_RC:-0}" ;;
  *scripts/validate.py*) printf 'validate-tree %s\n' "$(git ls-files | tr '\n' ' ')" >> "$FAKE_LOG"
                         [ -z "${FAKE_VALIDATE_HOOK:-}" ] || sh -c "$FAKE_VALIDATE_HOOK"
                         echo "${FAKE_VALIDATE_OUT:-validate stub}"; exit "${FAKE_VALIDATE_RC:-0}" ;;
  *codex_gate.py*) [ -z "${FAKE_GATE_HOOK:-}" ] || sh -c "$FAKE_GATE_HOOK"
                   [ -z "${FAKE_REAL_PYTHON:-}" ] || exec "$FAKE_REAL_PYTHON" "$@" ;;
  *" --check") if [ -n "${FAKE_CHECK_FAIL:-}" ] && [[ "$*" == $FAKE_CHECK_FAIL ]]; then echo "${FAKE_CHECK_OUT:-check stub}"; exit "${FAKE_CHECK_RC:-1}"; fi
               echo "check stub"; exit 0 ;;
esac
rc=${FAKE_GATE_RC:-0}
if [ -n "${FAKE_GATE_SEQ:-}" ]; then
  codes=($FAKE_GATE_SEQ); n=$(cat "$FAKE_LOG.gate" 2>/dev/null || echo 0); echo $((n + 1)) > "$FAKE_LOG.gate"
  rc=${codes[$(( n < ${#codes[@]} ? n : ${#codes[@]} - 1 ))]}
fi
echo "${FAKE_GATE_LINE:-Codex review finished at 2026-10-10T00:00:00Z after the latest trigger 2026-10-09T00:00:00Z}"
exit "$rc"
'''
# #975 round 4: sleep is logged too, so the call-order test sees that nothing slow runs between the final gate and the merge.
FAKE_SLEEP = "#!/bin/sh\n[ -z \"${FAKE_LOG:-}\" ] || printf 'sleep %s\\n' \"$*\" >> \"$FAKE_LOG\"\nexit 0\n"
# #975 round 4: git is the real git, and every call is appended to FAKE_LOG when it is set, so the call-order test sees the final gate's
# git reads (the change identity, git ls-remote) beside the gh calls. FAKE_GIT_HOOK runs (sh -c) once, right after the first call that
# matches the glob FAKE_GIT_HOOK_ON has returned, and that call's exit code is kept. {git} is the real git's path.
FAKE_GIT = r'''#!/bin/sh
[ -z "${{FAKE_LOG:-}}" ] || printf 'git %s\n' "$*" >> "$FAKE_LOG"
if [ -n "${{FAKE_GIT_FAIL:-}}" ]; then  # the FAKE_GIT_FAIL_FROM-th call (default 1) matching the glob FAKE_GIT_FAIL, and every later one, fails
  case "$*" in $FAKE_GIT_FAIL)
    n=$(cat "$FAKE_LOG.gitfail" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$FAKE_LOG.gitfail"
    [ "$n" -lt "${{FAKE_GIT_FAIL_FROM:-1}}" ] || exit 128 ;;
  esac
fi
if [ -n "${{FAKE_GIT_HOOK:-}}" ] && [ ! -e "$FAKE_LOG.githook" ]; then
  case "$*" in $FAKE_GIT_HOOK_ON) {git} "$@"; rc=$?; touch "$FAKE_LOG.githook"; sh -c "$FAKE_GIT_HOOK"; exit $rc ;; esac
fi
exec {git} "$@"
'''
# #975 round 4 (GPT P2 at 761810d7): head and grep that remove the file FAKE_VANISH when they are the second command given its path, so a
# script that reads one file twice sees it vanish between the reads. {real} is the real command's path.
FAKE_VANISH = r'''#!/bin/sh
for a in "$@"; do
  if [ -n "${{FAKE_VANISH:-}}" ] && [ "$a" = "$FAKE_VANISH" ]; then
    n=$(cat "$FAKE_VANISH.count" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$FAKE_VANISH.count"
    [ "$n" -lt 2 ] || rm -f -- "$FAKE_VANISH"
  fi
done
exec {real} "$@"
'''


def git(repo, *args):
    environment = {**tests.hermetic_git_environment(), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=environment)
    if done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {done.stderr.strip()[:300]}")
    return done.stdout.strip()


# ---------------------------------------------------------------------------------------------- the scripts' decision text
class Script:
    """One landing script, with its decision sites cut out by start and end lines (the correction #136 harness's regexes)."""

    def __init__(self, key):
        self.key = key
        self.path = LANDING / f"{key}_land.sh"
        self.text = self.path.read_text(encoding="utf-8")
        self.lines = self.text.split("\n")
        self.tcc = self.cut(r"^tcc_read_gate\(\) \{$", r"^\}$")
        # #975 round 4: the verdict loop is a function, run first and again in final_gate
        self.verdict_gate = self.cut(r"^verdict_gate\(\) \{$", r"^\}$")
        self.final = self.cut(r"^final_gate\(\) \{( |$)", r"^\}$")
        # #975 (Codex P1 at af9d1901): the GPT_VERDICT block is a function, called on a 5 at both gate calls
        self.gpt = self.cut(r"^gpt_substitute\(\) \{$", r"^\}$") if key == "uet" else None
        self.change = self.cut(r"^change\(\) \{", r"^same_change\(\) \{")
        if key == "uet":
            self.ci = self.cut(r'^  s=\$\(lg_ci_state "\$N"\)$', r'^  s=\$\(lg_ci_state "\$N"\)$')
        else:  # the check-run function: its line and, on it, the typed-shape check of #975 P2-B
            self.ci = self.cut(r"^nas_checks\(\) \{( |$)", r"^\}$")
        found = re.findall(r"^# >>> land-gate-fns$.*?^# <<< land-gate-fns$", self.text, re.S | re.M)
        if len(found) != 1:
            raise AssertionError(f"{key}_land.sh needs exactly one land-gate-fns block, it has {len(found)}")
        self.block = found[0]
        self.git_line = self.cut(r"^LG_GIT=", r"^LG_GIT=")  # how the block is told which repository to use

    def cut(self, start_re, end_re):
        start = next((i for i, line in enumerate(self.lines) if re.search(start_re, line)), None)
        if start is None:
            raise AssertionError(f"{self.key}_land.sh: no line matches {start_re}")
        end = next((i for i in range(start, len(self.lines)) if re.search(end_re, self.lines[i])), None)
        if end is None:
            raise AssertionError(f"{self.key}_land.sh: no end line matches {end_re}")
        return "\n".join(self.lines[start:end + 1])

    def line(self, prefix):
        found = [line for line in self.lines if line.startswith(prefix)]
        if len(found) != 1:
            raise AssertionError(f"{self.key}_land.sh: {len(found)} lines start with {prefix!r}")
        return found[0]


class LandingCase(unittest.TestCase):
    """A scratch directory, the fake commands on PATH, and a bash runner for the extracted text."""

    @classmethod
    def setUpClass(cls):
        scratch = tempfile.TemporaryDirectory(prefix="landing-")
        cls.addClassCleanup(scratch.cleanup)
        cls.dir = Path(scratch.name)
        cls.bin = cls.dir / "bin"
        cls.bin.mkdir()
        cls.real_git, cls.real_sleep = shutil.which("git"), shutil.which("sleep")
        for name, text in (("gh", FAKE_GH), ("python3", FAKE_PYTHON3), ("sleep", FAKE_SLEEP), ("git", FAKE_GIT.format(git=q(cls.real_git)))):
            (cls.bin / name).write_text(text, encoding="utf-8")
            (cls.bin / name).chmod(0o755)
        cls.vanish_bin = cls.dir / "vanish-bin"  # put first on PATH by a test that wants FAKE_VANISH
        cls.vanish_bin.mkdir()
        for name in ("head", "grep"):
            (cls.vanish_bin / name).write_text(FAKE_VANISH.format(real=q(shutil.which(name))), encoding="utf-8")
            (cls.vanish_bin / name).chmod(0o755)
        cls.uet, cls.nas = Script("uet"), Script("nas")
        cls.counter = itertools.count(1)

    def env(self, **extra):
        env = {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}", "HOME": "/home/example", "LC_ALL": "C.UTF-8",
               **tests.HERMETIC_GIT_ENVIRONMENT}
        env.update(extra)
        return env

    def bash(self, prelude, body, **extra):
        done = subprocess.run(["bash", "-c", f"set -u\n{prelude}\n{body}\n"], capture_output=True, text=True,
                              env=self.env(**extra), timeout=60)
        return done.returncode, (done.stdout + done.stderr).strip()

    def write(self, name, content):
        path = self.dir / f"{next(self.counter)}-{name}"
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        return path

    # -- the sites
    def verdict_files(self, script, path, head, gates_done=None):
        gates = f"GATES_DONE={q(gates_done)}" if gates_done else "unset GATES_DONE"
        prelude = f"R=x/y; N=1; E={head}; EF={head}\n{gates}\n{script.block}\n"
        prelude += f"VERDICT_FILES={q(path)}\n" if script.key == "uet" else f"VF=({q(path)})\n"
        return self.bash(prelude, f"{script.verdict_gate}\nverdict_gate")

    def receipt_loop(self, path, read, head, gates_done):
        """nas's verdict gate when the caller gave the read head as `read` (a prefix) and it resolved to `head`."""
        prelude = f"R=x/y; N=1; E={read}; EF={head}\nGATES_DONE={q(gates_done)}\n{self.nas.block}\nVF=({q(path)})\n"
        return self.bash(prelude, f"{self.nas.verdict_gate}\nverdict_gate")

    def gpt_block(self, path, head):
        prelude = f"R=x/y; N=1; E={head}; GPT_VERDICT={q(path)}\n{self.uet.block}\n"
        return self.bash(prelude, f"{self.uet.gpt}\ngpt_substitute")

    def record_gate(self, script, head, coord, statuses, **extra):
        feed = self.write("statuses.json", json.dumps(statuses))
        prelude = f"R=x/y; N=1; E={head}\nCOORD={q(coord)}\nexport FAKE_STATUSES={q(feed)}\n{script.block}\n{script.tcc}\n"
        return self.bash(prelude, 'tcc_read_gate "$E"', **extra)

    def change_prelude(self, script, repo):
        if script.key == "uet":
            return f"U={repo}\n{script.git_line}\n{script.block}\n"
        return f'G="git -C {repo}"\n{script.git_line}\n{script.block}\n'

    def change_same(self, script, repo, a, b):
        return self.bash(self.change_prelude(script, repo), f"{script.change}\nsame_change {a} {b}")

    def change_id(self, script, repo, commit):
        return self.bash(self.change_prelude(script, repo), f"lg_change_id {commit}")

    def ci_line(self, script, document):
        feed = self.write("ci.json", json.dumps(document))
        if script.key == "uet":
            return self.bash(f"R=x/y; N=1\nexport FAKE_PRVIEW={q(feed)}\n{script.block}\n", f'{script.ci}\necho "$s"')
        return self.bash(f"R=x/y; N=1\nexport FAKE_CHECKRUNS={q(feed)}\n", f'{script.ci}\nnas_checks abc')


def accept(code, reject_code=2):
    return "accept" if code == 0 else "reject" if code == reject_code else f"error:rc{code}"


# ---------------------------------------------------------------------------------------------- 1. the script text
# #975 P2-1: no file under tools/landing names the host. The scan reads every file there, bytecode excepted (a .pyc records the
# absolute path of its source; the tests importing codex_gate.py create one), for home-path syntax and for the identities that must
# not appear: the account that runs the tests, taken from the OS at test time, and every explicitly prohibited name, taken from the
# environment (LANDING_PROHIBITED_NAMES). Neither is ever written into the repository. Only (file, form) pairs are reported, never
# the matched text, so a failure cannot print a name. No name is skipped for its length (the GPT micro on 754a194f: a real account
# `sam` was never checked).
# #975 P3-7: in any letter case (an upper-case drive-letter Users path, an upper-case /home); case-insensitive file systems accept those
# spellings. legacy_findings keeps the old pattern.
HOME_PATH = re.compile(rb"/(?:home|Users)/[A-Za-z0-9_.-]|[A-Za-z]:[\\/]+Users[\\/]|/root/", re.I)
PROHIBITED_NAMES_VARIABLE = "LANDING_PROHIBITED_NAMES"  # not NATIVE_AGENT_HOST_NAMES_JSON: setting that replaces the host-name scanner's own sources
JOINERS = rb"[-_./\\@:~=]"  # what joins a name to other text in an identifier or a path: project-<name>-tools, <name>@host, /<name>/, ~<name>


# Generic CI and container accounts. Their names are ordinary words ("runner" on GitHub-hosted runners) that may stand in prose, so
# the running account, and only that account, may appear in the files as a bare word when it is one of these. Its identifier, path
# and encoded forms, home paths, and every explicitly prohibited name (whatever it is, generic or not) are still reported.
GENERIC_ACCOUNTS = frozenset({"runner", "root", "ubuntu", "user", "admin", "vscode", "codespace", "ec2-user", "node", "docker"})


def prohibited_names():
    """The explicitly prohibited identities: the comma-separated names in LANDING_PROHIBITED_NAMES, read when the test runs. Each is
    scanned in every form, whatever its length and whether or not it is a generic word."""
    return tuple(name for name in (part.strip() for part in os.environ.get(PROHIBITED_NAMES_VARIABLE, "").split(",")) if name)


def account_name():
    """The name of the account running the tests, from the password database (getpass when the uid has no entry)."""
    import pwd  # Unix only, like the scripts
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except KeyError:
        return getpass.getuser()


def betterleaks_pinned():
    """True when the native scanner behind `validate.py --scan-file` (Betterleaks at host_name_scan.py's pin) is installed, as
    host_name_scan._scan_entries checks it: `betterleaks version` prints the pin, bare or after its name."""
    binary = shutil.which("betterleaks")
    if binary is None:
        return False
    done = subprocess.run([binary, "version"], capture_output=True, text=True, env={}, timeout=60)
    return done.returncode == 0 and done.stdout.strip() in (host_name_scan.PIN, "betterleaks version " + host_name_scan.PIN)


def rfc5322(text):
    """The RFC 5322 oracle of #1027 round 2 (the CC's adjudication at e203d014: one oracle for this email class, the parser Astra ran):
    CPython's reading of an addr-spec, Lib/email/_header_value_parser.py get_addr_spec (:1682-1696 at v3.13.16, cbc944f4bc59; quoted strings
    :1235-1275 and :1315-1331, local parts :1486-1575), as installed. (local part, domain, the class names of its defects) when it reads text
    whole as one addr-spec, else None. For every text these tests give it, its answer is the same on CPython 3.12.3 (CI's), 3.13.16 and
    3.14.4 (measured 2026-10-12)."""
    try:
        spec, rest = _header_value_parser.get_addr_spec(text)
    except email_errors.HeaderParseError:
        return None
    if rest or spec.domain is None:
        return None
    return spec.local_part, spec.domain, tuple(type(defect).__name__ for defect in spec.all_defects)


def round_2_allows(local, domain):
    """The allowances of the CC's rulings of 2026-10-12 and of #1027 round 2, on an address as the oracle reads it, lower-cased: GitHub's
    no-reply domain, a local part of exactly noreply or no-reply, the one vendor trailer address, and a unit instance <name>@<instance>.<type>
    of service, timer, socket, path or mount (no longer target) whose <name>@<instance> does not have the repository's address shape
    (scripts/host_name_scan.py:164: a domain that ends in a dot and two letters or more), the whole address compared."""
    if domain == "users.noreply.github.com" or local in ("noreply", "no-reply") or (local, domain) == ("codex", "openai.com"):
        return True
    instance, _, kind = domain.rpartition(".")
    unit = re.compile(r"[A-Za-z0-9:_.-]+")
    return (kind in ("service", "timer", "socket", "path", "mount") and bool(unit.fullmatch(local)) and bool(unit.fullmatch(instance))
            and re.match(r"[\w.-]+\.[A-Za-z]{2,}", instance) is None)


def name_patterns(name):
    """Bytes patterns for the name in its usual spellings: as a token (a run that touches no letter or digit), told apart as the bare
    word ("the runner reports") and the identifier or path form (joined to other text by one of JOINERS, as in project-<name>-tools),
    as hex digits and inside base64 at each of the three byte alignments, cut to the characters that do not depend on the bytes
    around the name. "bare" and "identifier" split "token": every token is one or both."""
    spellings = [spelling.encode("utf-8") for spelling in sorted({name, name.lower(), name.upper(), name.capitalize()})]
    encoded = set()
    for value in spellings:
        for offset, skip in ((0, 0), (1, 2), (2, 3)):
            for encode in (base64.b64encode, base64.urlsafe_b64encode):
                encoded.add(encode(b"\0" * offset + value)[skip:8 * (offset + len(value)) // 6])

    def either(values):
        return b"|".join(re.escape(value) for value in sorted(values))

    word = either(spellings)
    return {"token": re.compile(rb"(?<![A-Za-z0-9])(?:" + word + rb")(?![A-Za-z0-9])", re.I),
            "bare": re.compile(rb"(?<![A-Za-z0-9])(?<!" + JOINERS + rb")(?:" + word + rb")(?![A-Za-z0-9])(?!" + JOINERS + rb"[A-Za-z0-9])", re.I),
            "identifier": re.compile(rb"(?<=" + JOINERS + rb")(?:" + word + rb")(?![A-Za-z0-9])|(?<![A-Za-z0-9])(?:" + word + rb")(?=" + JOINERS + rb"[A-Za-z0-9])", re.I),
            "hex": re.compile(either(value.hex().encode() for value in spellings), re.I),
            "base64": re.compile(either(encoded))}


def privacy_findings(root, name, bare_word_ok=False):
    """(path under root, form) for every file under root, __pycache__ and *.pyc excepted, that holds a home path or a form of name: the
    bare word, an identifier or path form, a percent-encoded form, hex digits or base64. bare_word_ok leaves out the bare word alone.
    Hex counts with or without \\x escapes; a percent-encoded form counts where decoding the %XX escapes reveals more matches, as a
    token or as an identifier (#975 P2-D: `runner%40example.invalid` decodes to an address while its token count stays the same)."""
    patterns = name_patterns(name)
    found = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        data = path.read_bytes()
        decoded = urllib.parse.unquote_to_bytes(data)
        hits = {
            "home path": bool(HOME_PATH.search(data)),
            "home path, percent-encoded": len(HOME_PATH.findall(decoded)) > len(HOME_PATH.findall(data)),
            "name": not bare_word_ok and bool(patterns["bare"].search(data)),
            "name, identifier": bool(patterns["identifier"].search(data)),
            "name, percent-encoded": len(patterns["token"].findall(decoded)) > len(patterns["token"].findall(data))
                                     or len(patterns["identifier"].findall(decoded)) > len(patterns["identifier"].findall(data)),
            "name, hex": bool(patterns["hex"].search(data.replace(b"\\x", b""))),
            "name, base64": bool(patterns["base64"].search(data)),
        }
        found += [(relative.as_posix(), form) for form, hit in hits.items() if hit]
    return found


def identity_findings(root, account, prohibited=()):
    """The sorted (path, form) pairs for every home path and every form of an identity under root. Each prohibited name is scanned in
    full. So is the running account, except that in CI a generic one (GENERIC_ACCOUNTS, whatever its case) may stand as a bare word
    (#975 P3-8: outside CI no account is excused). An empty name would match everything and is refused."""
    if any(not name.strip() for name in (account, *prohibited)):
        raise ValueError("an empty identity matches everything")
    found = set(privacy_findings(root, account, bare_word_ok=IN_CI and account.lower() in GENERIC_ACCOUNTS))
    for name in prohibited:
        found.update(privacy_findings(root, name))
    return sorted(found)


def legacy_findings(root):
    """The check before #975 P2-1, kept as the planted-tree test's fail-before witness: home-path syntax in top-level files only."""
    pattern = re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]|[A-Za-z]:[\\/]+Users[\\/]|/root/")
    return [path.name for path in sorted(root.iterdir()) if path.is_file() and pattern.findall(path.read_text(encoding="utf-8"))]


class ScriptTextTests(LandingCase):
    def test_no_home_literal_or_user_name_in_tools_landing(self):
        self.assertEqual(identity_findings(LANDING, account_name(), prohibited_names()), [],
                         "a home path, or a form of an identity that must not appear (the account running these tests, or a name in "
                         f"{PROHIBITED_NAMES_VARIABLE}), in tools/landing")

    def assertion_fails(self, files, *, account, prohibited="", in_ci=True, root=None):
        """Run test_no_home_literal_or_user_name_in_tools_landing itself, as the account `account`, with `prohibited` in
        LANDING_PROHIBITED_NAMES and IN_CI as given, on a scratch tools/landing holding `files` ({relative path: text}), or on `root`;
        True when it raises."""
        if root is None:
            root = self.dir / f"assertion-{next(self.counter)}"
            for relative, text in files.items():
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                (root / relative).write_text(text, encoding="utf-8")
        case = type(self)("test_no_home_literal_or_user_name_in_tools_landing")
        with mock.patch.multiple(sys.modules[__name__], LANDING=root, account_name=lambda: account, IN_CI=in_ci), \
                mock.patch.dict(os.environ, {"LANDING_PROHIBITED_NAMES": prohibited}):
            try:
                case.test_no_home_literal_or_user_name_in_tools_landing()
            except AssertionError:
                return True
        return False

    def test_the_repository_assertion_checks_an_account_name_of_any_length(self):
        # #975 P2-1 (GPT micro on 754a194f): scan_name() put a sentinel in place of every name under four characters, so a real account
        # `sam` was never checked, not even in an unambiguous project-sam-tools. These run the repository assertion on a real nested
        # file with a mocked account lookup, as the review's probe did.
        for account in ("zqxsynth", "sam", "ab"):
            for form, text in (("an identifier", f"dir=project-{account}-tools\n"), ("a bare word", f"the {account} reports\n")):
                with self.subTest(account=account, form=form):
                    self.assertTrue(self.assertion_fails({"nested/sample.txt": text}, account=account))
            with self.subTest(account=account, form="nothing to report"):
                self.assertFalse(self.assertion_fails({"nested/sample.txt": "nothing to report\n"}, account=account))

    def test_a_generic_running_account_may_stand_as_a_bare_word_and_in_no_other_form(self):
        # #975 P2-1: the exception for generic CI accounts is the running account's alone and covers its bare word only: its identifier,
        # path and encoded forms, and any home path, are still reported.
        for account, text in (("runner", "the runner reports\n"), ("runner", "a hosted runner.\n"), ("Runner", "the runner reports\n"),
                              ("ec2-user", "the `ec2-user` account\n"), ("node", 'c["node"]\n')):
            with self.subTest(account=account, allowed=text):
                self.assertFalse(self.assertion_fails({"a/prose.md": text}, account=account))
        raw = b"runner"
        refused = {"an identifier": "dir=project-runner-tools\n", "a suffix": "runner-1\n", "a prefix": "ci-runner\n", "a field name": "runner_id\n",
                   "an underscore": "runner_home\n", "a dotted name": "runner.example\n", "an address": "runner@example.invalid\n",
                   "a path": "/srv/runner/work\n", "a home directory": "~runner\n", "a flag": "--runner\n",
                   "a home path": "cd /home/example/work\n", "percent-encoded": "u=" + "".join(f"%{byte:02X}" for byte in raw) + "\n",
                   "hex": "blob " + raw.hex() + "\n", "base64": base64.b64encode(raw).decode() + "\n"}
        for form, text in refused.items():
            with self.subTest(account="runner", refused=form):
                self.assertTrue(self.assertion_fails({"a/b/c.txt": text}, account="runner"))

    def test_a_percent_encoded_joiner_is_an_identifier_form_too(self):
        # #975 P2-D (GPT micro at af9d1901): the encoded form counted only new tokens, so `runner%40example.invalid` (the bare token
        # `runner` before and after decoding, an address once decoded) passed for a generic running account.
        for joiner in "@-/_.:~=\\":
            text = f"contact runner%{ord(joiner):02X}example\n"
            with self.subTest(joiner=joiner):
                self.assertTrue(self.assertion_fails({"a/b.md": text}, account="runner"))
                self.assertIn(("b.md", "name, percent-encoded"), privacy_findings(self.write_tree({"b.md": text}), "runner", bare_word_ok=True))
        for text in ("the runner reports\n", "a runner%20reports\n", "runner%2C and more\n"):  # the bare word, also after decoding
            with self.subTest(allowed=text):
                self.assertFalse(self.assertion_fails({"a/b.md": text}, account="runner"))

    def write_tree(self, files):
        root = self.dir / f"tree-{next(self.counter)}"
        for relative, text in files.items():
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / relative).write_text(text, encoding="utf-8")
        return root

    def test_a_generic_account_is_excused_its_bare_word_in_ci_only(self):
        # #975 P3-8 (Claude micro at af9d1901): the exemption applied on any machine; an account named `runner` outside CI was never
        # checked for its bare word.
        for in_ci, expected in ((True, False), (False, True)):
            with self.subTest(in_ci=in_ci):
                self.assertEqual(self.assertion_fails({"a/prose.md": "the runner reports\n"}, account="runner", in_ci=in_ci), expected)

    def test_a_clean_checkout_passes_for_every_generic_account_in_ci(self):
        # #975 P2-E (GPT micro at af9d1901): the hyphenated adjective "user-owned" in uet_land.sh line 2 is the identifier form of the
        # supported generic account `user`, so the production assertion failed a clean checkout run by `user` in CI.
        for account in sorted(GENERIC_ACCOUNTS):
            with self.subTest(account=account):
                self.assertFalse(self.assertion_fails({}, account=account, prohibited=os.environ.get(PROHIBITED_NAMES_VARIABLE, ""), root=LANDING))

    def test_a_home_path_is_found_in_any_case(self):
        # #975 P3-7 (Claude micro at af9d1901): the pattern was case-sensitive, so these spellings were not reported.
        for text in ("C:/USERS/example\n", "c:\\users\\example\n", "/HOME/example\n", "/Root/example\n"):
            with self.subTest(text=text):
                self.assertIn(("p.txt", "home path"), privacy_findings(self.write_tree({"p.txt": text}), "zqxsynth"))

    def test_an_explicitly_prohibited_name_is_scanned_in_every_form_whatever_it_is(self):
        # #975 P2-1: a prohibited identity is never replaced by a sentinel, however short, and never excused as a generic word.
        for prohibited in ("runner", "user", "ab", "zqxsynth"):
            for form, text in (("a bare word", f"the {prohibited} reports\n"), ("an identifier", f"dir=project-{prohibited}-tools\n")):
                with self.subTest(prohibited=prohibited, form=form):
                    self.assertTrue(self.assertion_fails({"nested/sample.txt": text}, account="unrelated", prohibited=prohibited))
        word = {"x.md": "the runner reports\n"}
        with self.subTest("one of several names, with spaces"):
            self.assertTrue(self.assertion_fails(word, account="unrelated", prohibited=" other , runner "))
        with self.subTest("the running account is that name too"):
            self.assertTrue(self.assertion_fails(word, account="runner", prohibited="runner"))
        with self.subTest("a generic word that is neither prohibited nor the running account"):
            self.assertFalse(self.assertion_fails(word, account="unrelated", prohibited="other"))

    def test_an_empty_identity_is_refused_and_empty_prohibited_entries_are_dropped(self):
        with mock.patch.dict(os.environ, {"LANDING_PROHIBITED_NAMES": " , a ,, b "}):
            self.assertEqual(prohibited_names(), ("a", "b"))
        with mock.patch.dict(os.environ, {"LANDING_PROHIBITED_NAMES": ""}):
            self.assertEqual(prohibited_names(), ())
        for account, prohibited in (("", ()), (" ", ()), ("unrelated", ("",))):
            with self.subTest(account=account, prohibited=prohibited), self.assertRaises(ValueError):
                identity_findings(self.dir, account, prohibited)

    def test_the_privacy_scan_finds_each_form_of_the_name_planted_in_subdirectories(self):
        # The fail-before of #975 P2-1: the old check (legacy_findings) passes every plant below. The account's own name and a
        # synthetic one; neither is ever a subTest parameter or part of a message.
        for label, name in (("the account's name", account_name()), ("a synthetic name", "zqxsynth")):
            raw = name.encode("utf-8")
            plants = {
                "a/bare.txt": (raw + b"\n", ["name"]),
                "a/b/hyphenated.sh": (b"dir=project-" + raw + b"-tools\n", ["name, identifier"]),
                "a/b/c/url-encoded.md": (b"<https://example.invalid/?u=" + "".join(f"%{byte:02X}" for byte in raw).encode() + b">\n",
                                         ["name, percent-encoded"]),
                "d/hex.txt": (b"blob " + raw.hex().encode() + b"\n", ["name, hex"]),
                "d/e/escaped-hex.py": (b"s = '" + "".join(f"\\x{byte:02x}" for byte in raw).encode() + b"'\n", ["name, hex"]),
                "f/base64-at-0.txt": (base64.b64encode(raw) + b"\n", ["name, base64"]),
                "f/base64-at-1.txt": (base64.b64encode(b"u" + raw + b";") + b"\n", ["name, base64"]),
                "f/g/base64-url-at-2.txt": (base64.urlsafe_b64encode(b"u=" + raw + b";") + b"\n", ["name, base64"]),
                "h/home.txt": (b"cd /home/example/project\n", ["home path"]),
                "h/home-url-encoded.txt": (b"file=%2Fhome%2Fexample%2Fproject\n", ["home path, percent-encoded"]),
                "clean.txt": (b"nothing to report\n", []),
                "__pycache__/gate.cpython-313.pyc": (raw, []),
                "i/__pycache__/notes.txt": (raw, []),
                "i/stale.pyc": (raw, []),
            }
            root = self.dir / f"privacy-{next(self.counter)}"
            for relative, (content, _) in plants.items():
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                (root / relative).write_bytes(content)
            with self.subTest(case=label):
                expected = sorted((relative, form) for relative, (_, forms) in plants.items() for form in forms)
                self.assertEqual(privacy_findings(root, name), expected)
                self.assertEqual(legacy_findings(root), [], "the old check finds none of the plants")

    def test_scripts_parse_and_have_the_expected_modes(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                done = subprocess.run(["bash", "-n", str(script.path)], capture_output=True, text=True)
                self.assertEqual((done.returncode, done.stderr), (0, ""))
                self.assertTrue(script.path.stat().st_mode & stat.S_IXUSR, "the shell scripts are run by path")
                self.assertTrue(script.text.startswith("#!/usr/bin/env bash\n"))
        source = (LANDING / "codex_gate.py").read_text(encoding="utf-8")
        compile(source, "codex_gate.py", "exec")

    def test_body_runs_inside_one_group_parsed_before_it_runs(self):
        # "Parsed whole before it runs: an edit while a landing runs cannot shift what the running copy executes" (2026-10-09).
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                lines = script.lines
                self.assertEqual(lines[lines.index("set -u") + 2], "{", "the group opens after set -u and its comment")
                self.assertEqual([line for line in lines if line][-1], "}")
                self.assertEqual(sum(1 for line in lines if line == "{"), 1)

    def test_shared_block_is_identical_in_both_scripts_apart_from_the_ci_function(self):
        marker = "# The CI state of a pull request as one tab-separated line"
        self.assertEqual(self.uet.block.count(marker), 1)
        self.assertNotIn("lg_ci_state", self.nas.block)
        uet_without_ci = self.uet.block[:self.uet.block.index(marker)] + "# <<< land-gate-fns"
        self.assertEqual(uet_without_ci, self.nas.block)

    def test_scripts_run_the_gate_isolated_and_through_the_variable(self):
        # #975 P2-C: every call goes through lg_gate, which runs `python3 -I` and echoes only the gate's own status lines. #975 round 4:
        # the read head is the gate's third argument; uet asks at the wait and in final_gate, nas also before the validation.
        for script, read, calls in ((self.uet, "$E", 2), (self.nas, "$EF", 3)):
            with self.subTest(script=script.key):
                self.assertEqual(script.text.count(f'lg_gate "$GATE" "$R" "$N" "{read}"'), calls)
                self.assertEqual(script.text.count("lg_gate \"$GATE\""), calls)
                self.assertIn(f'g=$(lg_gate "$GATE" "$R" "$N" "{read}"); gr=$?', script.final)
                self.assertEqual(script.text.count("python3 -I"), 1)
                self.assertIn('g=$(python3 -I "$1" "$2" "$3" "$4" 2>&1)', script.block)
                self.assertEqual(len(re.findall(r"^GATE=", script.text, re.M)), 1)

    def test_every_child_that_waits_or_detaches_runs_without_the_lock_descriptor(self):
        # #975 round 4: the landing lock is descriptor 9; git (whose maintenance detaches keeping every descriptor but 0-2), gh, python3
        # and sleep run with it closed, so the lock ends with the script. The wrappers are in the shared block, before any call.
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                for command in ("git", "gh", "python3", "sleep"):
                    self.assertIn(f'{command}() {{ command {command} "$@" 9>&-; }}', script.block)
                lock = script.lines.index('lg_lock "${LANDING_LOCK_DIR:-$COORD/command-center/landing-locks}" || exit 14')
                first = min(i for i, line in enumerate(script.lines) if re.match(r"^(git|gh|\$G) ", line))
                self.assertLess(lock, first, "the lock is taken before the first git or gh call")
                self.assertLess(script.lines.index("# <<< land-gate-fns"), lock)

    def test_the_final_gate_runs_after_the_last_slow_step_and_right_before_the_merge(self):
        # #975 round 4: the author lookup is the last slow step, final_gate the only thing between it and the pinned merge.
        for script, pinned in ((self.uet, '"$H"'), (self.nas, '"$cur"')):
            with self.subTest(script=script.key):
                merge = next(i for i, line in enumerate(script.lines) if line.startswith("out=$(gh pr merge "))
                self.assertEqual(script.lines[merge - 1], f"final_gate {pinned}")
                self.assertTrue(script.lines[merge - 2].startswith('ae=$(lg_author_email "$R")'))
                self.assertIn(f"--match-head-commit {pinned}", script.lines[merge])
                self.assertEqual(script.text.count("\nfinal_gate "), 1)

    def test_the_squash_body_is_scanned_before_the_lock_and_the_merge_is_given_only_the_snapshot(self):
        # #1027: the check of the variable, then the snapshot and its scans, then the lock. The merge line names the snapshot; the only lines
        # outside the comments that read the caller's file are the check and the call that copies it.
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                lines = script.lines
                call = lines.index('[ -z "${SQUASH_BODY_FILE:-}" ] || lg_body_snapshot "$SQUASH_BODY_FILE" || exit 2')
                lock = lines.index('lg_lock "${LANDING_LOCK_DIR:-$COORD/command-center/landing-locks}" || exit 14')
                check = next(i for i, line in enumerate(lines) if line.startswith('[ -z "${SQUASH_BODY_FILE:-}" ] || { [ "$SQUASH_BODY_FILE" != - ]'))
                self.assertLess(check, call)
                self.assertLess(call, lock)
                reads = [i for i, line in enumerate(lines) if "$SQUASH_BODY_FILE" in line and not line.lstrip().startswith("#")]
                self.assertEqual(reads, [check, call])
                merge = next(line for line in lines if line.startswith("out=$(gh pr merge "))
                self.assertIn('${SB:+--body-file "$SB"}', merge)
                self.assertNotIn("SQUASH_BODY_FILE", merge)

    def test_nas_runs_the_currency_checks_of_validate_ymls_shard_0_in_the_workflows_order(self):
        # CC correction #176 (2026-10-12): merge_validate ran validate.py alone, and #1018 landed on #1007 with final_stack.py --check
        # failing. It runs every shard-0 step of .github/workflows/validate.yml that runs a Python script with --check, as that step runs
        # it and in its order; the CC's ruling of 2026-10-12 added the gap-wave ledger's, a folded `run: >-` step #176's list left out.
        body = self.nas.cut(r"^merge_validate\(\) \{$", r"^\}$")
        self.assertEqual(tuple(re.findall(r'"([^"]+ --check)"', body)), CURRENCY_CHECKS)
        self.assertEqual(shard_0_python_checks(ROOT / ".github/workflows/validate.yml"), CURRENCY_CHECKS)

    def test_the_workflow_reader_takes_one_line_and_folded_runs_and_nothing_else(self):
        # The reader behind the test above, on a synthetic workflow: a one-line and a folded --check step of shard 0 count, in order; a
        # step of another shard, a literal block, a report-only run that does not end with --check and a non-Python check do not.
        workflow = self.write("validate.yml", "jobs:\n  validate:\n    steps:\n"
                              "      - name: a\n        if: matrix.shard == 0\n        run: python3 a/one.py --check\n"
                              "      - name: b\n        if: matrix.shard == 1\n        run: python3 b/other.py --check\n"
                              "      - name: c\n        if: matrix.shard == 0\n        # a comment\n        run: >-\n"
                              "          python3 c/folded.py\n          --wave w --check\n"
                              "      - name: d\n        if: matrix.shard == 0\n        run: |\n          python3 d/script.py --check\n"
                              "      - name: e\n        if: matrix.shard == 0\n        run: python3 e/report.py --check --today x | tee s\n"
                              "      - name: f\n        if: matrix.shard == 0\n        run: sha256sum --check --strict SHA256SUMS\n")
        self.assertEqual(shard_0_python_checks(workflow), ("a/one.py --check", "c/folded.py --wave w --check"))

    def test_the_provenance_section_carries_a_digest_only_for_the_repository_copies(self):
        # CC correction #161 and the CC's ruling of 2026-10-12: a digest of a file whose only non-public bytes are host paths confirms a
        # guessed path offline. The live copies hold the CC host's paths, so the section gives their line counts and no digest; a 64-hex
        # digest stands only in the "Here" column, the repository copies as committed. At 86fa3844 seven stood in the live-copy columns.
        readme = (LANDING / "README.md").read_text(encoding="utf-8")
        section = readme.split("## Provenance and digests", 1)[1].split("\n## ", 1)[0]
        digest = r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])"
        here = []
        for line in section.splitlines():
            if re.match(r"\| `(uet_land\.sh|nas_land\.sh|codex_gate\.py)` \|", line):
                here += re.findall(digest, line.rstrip(" |").rsplit("|", 1)[1])
        self.assertEqual(len(here), 3, "each row's last cell holds its file's digest as committed")
        self.assertEqual(sorted(re.findall(digest, section)), sorted(here))

    def test_readme_names_every_variable_and_exit_code_the_scripts_use(self):
        readme = (LANDING / "README.md").read_text(encoding="utf-8")
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                for name in sorted(set(re.findall(r"\bLANDING_[A-Z_]+\b", script.text))):
                    self.assertIn(f"`{name}`", readme)
                for name in ("VERDICT_FILES", "GATES_DONE", "GPT_VERDICT", "SQUASH_BODY_FILE"):
                    if name in script.text:
                        self.assertIn(f"`{name}`", readme)
                section = readme.split("## Exit codes", 1)[1].split("\n## ", 1)[0]
                codes = sorted(set(re.findall(r"\bexit (\d+)\b", script.text)) - {"0", "1"}, key=int)
                self.assertTrue(codes)
                for code in codes:
                    self.assertRegex(section, rf"(?<![0-9]){code} [A-Za-z]", f"exit {code} is not described")

    def test_the_readme_digests_each_file_as_committed(self):
        # #975 (review of the P2 fix commit): the "Here" column held the bytes from before the review's edits. The last cell of each row is the file's
        # sha256 and line count as committed, so an edit that leaves it behind fails here.
        readme = (LANDING / "README.md").read_text(encoding="utf-8")
        for name in ("uet_land.sh", "nas_land.sh", "codex_gate.py"):
            with self.subTest(file=name):
                row = next(line for line in readme.splitlines() if line.startswith(f"| `{name}` |"))
                cell = re.fullmatch(r"`([0-9a-f]{64})` \((\d+) lines\)", row.rstrip(" |").rsplit("|", 1)[1].strip())
                self.assertIsNotNone(cell, "the last cell of the row reads `<sha256>` (<n> lines)")
                data = (LANDING / name).read_bytes()
                self.assertEqual((cell.group(1), int(cell.group(2))), (hashlib.sha256(data).hexdigest(), data.count(b"\n")))

    def test_readme_states_the_failed_merge_message_the_gate_error_the_gh_rule_and_the_privacy_scan(self):
        # #975 (review of the P2 fix commit): the README said the failed-merge message names the file's path (it names the file only), listed
        # no exit 4 for a failing gate, and did not say which accounts skip the name scan or why. #975 (GPT micro on 754a194f): it stated
        # an exemption for names under four characters and for generic accounts, which the scan no longer has; it states the rule now.
        flat = " ".join((LANDING / "README.md").read_text(encoding="utf-8").split())
        self.assertIn("names only that file, not its path", flat)
        self.assertNotIn("whose path the message names", flat)
        self.assertIn("one fixed line naming only the error class", flat)
        self.assertIn("Nothing `gh` or its API returned is printed", flat)
        self.assertIn("and never the description", flat)
        self.assertIn("An explicitly prohibited identity is a name in `LANDING_PROHIBITED_NAMES`", flat)
        self.assertIn("It is scanned in every form, whatever its length and even when it is an ordinary word", flat)
        self.assertIn("its bare word may stand in prose", flat)
        self.assertIn("its identifier, path and encoded forms are still reported", flat)
        self.assertIn("No name is skipped for its length", flat)
        self.assertNotIn("fewer than 4 characters", flat)
        self.assertNotIn("The account-name scan is skipped", flat)
        self.assertIn("`GENERIC_ACCOUNTS`", flat)

    def evaluate(self, lines, names, arg0="landing.sh", **extra):
        script = "set -u\n" + "\n".join(lines) + "\n" + "".join(f'printf "%s\\n" "${name}"\n' for name in names)
        done = subprocess.run(["bash", "-c", script, arg0], capture_output=True, text=True, env=self.env(**extra), timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.split("\n")[:len(names)]

    def test_variables_default_to_the_documented_paths_and_can_be_overridden(self):
        uet = [self.uet.line("U=")]
        nas_g = self.nas.line("G=")
        base = {"HOME": "/home/example"}
        state = "/home/example/.local/state/native-agent-stack/coordination"
        cases = [
            ("defaults", {}, ["/home/example/code/us-equities-trading", state]),
            ("XDG_STATE_HOME", {"XDG_STATE_HOME": "/xdg"}, ["/home/example/code/us-equities-trading", "/xdg/native-agent-stack/coordination"]),
            ("LANDING_COORD wins over XDG", {"XDG_STATE_HOME": "/xdg", "LANDING_COORD": "/c"}, ["/home/example/code/us-equities-trading", "/c"]),
            ("LANDING_UET_REPO", {"LANDING_UET_REPO": "/r"}, ["/r", state]),
            ("empty overrides fall back", {"LANDING_UET_REPO": "", "LANDING_COORD": ""}, ["/home/example/code/us-equities-trading", state]),
        ]
        for name, extra, expected in cases:
            with self.subTest(script="uet", case=name):
                self.assertEqual(self.evaluate(uet, ["U", "COORD"], **{**base, **extra}), expected)
        nas_cases = [
            ("defaults", {}, ["git -C /home/example/code/native-agent-stack", state]),
            ("LANDING_NAS_REPO", {"LANDING_NAS_REPO": "/n"}, ["git -C /n", state]),
            ("LANDING_COORD", {"LANDING_COORD": "/c"}, ["git -C /home/example/code/native-agent-stack", "/c"]),
            ("XDG_STATE_HOME", {"XDG_STATE_HOME": "/xdg"}, ["git -C /home/example/code/native-agent-stack", "/xdg/native-agent-stack/coordination"]),
            ("empty overrides fall back", {"LANDING_NAS_REPO": "", "LANDING_COORD": ""}, ["git -C /home/example/code/native-agent-stack", state]),
        ]
        for name, extra, expected in nas_cases:
            with self.subTest(script="nas", case=name):
                self.assertEqual(self.evaluate([nas_g], ["G", "COORD"], **{**base, **extra}), expected)

    def test_gate_defaults_to_the_directory_of_the_script_with_symlinks_resolved(self):
        gate_line = self.uet.line("GATE=")
        self.assertEqual(gate_line, self.nas.line("GATE="), "both scripts compute the gate path the same way")
        link_dir = self.dir / f"links-{next(self.counter)}"
        link_dir.mkdir()
        (link_dir / "land").symlink_to(self.uet.path)
        real = os.path.realpath(LANDING)
        cases = [("direct", str(self.uet.path), {}, f"{real}/codex_gate.py"),
                 ("through a symlink", str(link_dir / "land"), {}, f"{real}/codex_gate.py"),
                 ("LANDING_GATE", str(link_dir / "land"), {"LANDING_GATE": "/g/gate.py"}, "/g/gate.py")]
        for name, arg0, extra, expected in cases:
            with self.subTest(case=name):
                self.assertEqual(self.evaluate([gate_line], ["GATE"], arg0=arg0, **extra), [expected])


# ---------------------------------------------------------------------------------------------- 2. verdict files
def synthetic_verdict_files():
    h, w = HEAD, OTHER
    u = "seathatflowsinourveins/us-equities-trading#44"
    return {
        "astra-ack": (f"# GPT verdict on PR {u} at {h}: ACK\n\nbody\n", "accept"),
        "astra-pass-dash": (f"# GPT verdict on PR {u} at {h}: PASS — with notes\n", "accept"),
        "astra-ack-link": (f"# GPT verdict on PR {u} at {h}: ACK — [Codex limit reply 6097595105](https://example.invalid/x)\n", "accept"),
        "astra-ack-crlf": (f"# GPT verdict on PR {u} at {h}: ACK\r\n\r\nbody\r\n", "accept"),
        "astra-cr": (f"# GPT verdict on PR {u} at {h}: CHANGES_REQUESTED\n\nthe reader says ACK elsewhere and PASS here\n", "reject"),
        "astra-cr-with-ack-line": (f"# GPT verdict on PR {u} at {h}: CHANGES_REQUESTED\n\n{h[:8]} ACK\n", "reject"),
        "astra-ack-after": (f"# GPT verdict on PR {u} at {h}: ACK_AFTER\n", "reject"),
        "astra-ackish-word": (f"# GPT verdict on PR {u} at {h}: ACKNOWLEDGED\n", "reject"),
        "astra-bypass": (f"# GPT verdict on PR {u} at {h}: BYPASS\n", "reject"),
        "astra-wrong-head": (f"# GPT verdict on PR {u} at {w}: ACK\n\nmentions {h[:8]} here\n", "reject"),
        "head-only-in-body": (f"# notes\n\nACK at {h[:8]}\n", "reject"),
        "head-inside-longer-hex": (f"# GPT verdict on PR {u} at 00{h}: ACK\n", "reject"),
        "ack-anywhere-no-head-line1": (f"# verdict\n\n{h[:8]} was read; PASS\n", "reject"),
        "empty": ("", "reject"),
        "gate-line": (f"# Read of PR {u}\n\nGate line: PASS at {h[:8]}\n", "accept"),
        "gate-line-note": (f"# Read\n\nGate line: PASS at {h[:8]} (P3s non-blocking; landing still needs the rebase).\n", "accept"),
        "verdict-co-op-40hex": (f"# Adjudication\n\nVerdict: PASS at {h} (co-op ns2604-coop, 2026-10-10).\n", "accept"),
        "verdict-by-closure": (f"# Closure\n\nVerdict: ACK (by closure) at {h}.\n", "accept"),
        "verdict-cr": (f"# Read\n\nVerdict: CHANGES_REQUESTED at {h[:8]}\n", "reject"),
        "gate-line-cr-after-ack-title": (f"# GPT verdict on PR {u} at {h}: ACK\n\nVerdict: CHANGES_REQUESTED at {h[:8]} after the rebase\n", "reject"),
        "gate-line-then-cr-later": (f"# Read\n\nGate line: PASS at {h[:8]}\n\nVerdict: CHANGES_REQUESTED at {h[:8]}\n", "reject"),
        "cr-then-gate-line-later": (f"# Read\n\nVerdict: CHANGES_REQUESTED at {h[:8]}\n\nGate line: PASS at {h[:8]}\n", "accept"),
        "title-cr-then-gate-line": (f"# GPT verdict on PR {u} at {h}: CHANGES_REQUESTED\n\nGate line: PASS at {h[:8]}\n", "reject"),
        "gate-line-other-head": (f"# Read\n\nGate line: PASS at {w[:8]}\n\nmentions {h[:8]} in prose, PASS\n", "reject"),
        "gate-line-lowercase-pass": (f"# Read\n\nGate line: pass at {h[:8]}\n", "reject"),
        "gate-line-word-between": (f"# Read\n\nGate line: PASS maybe at {h[:8]}\n", "reject"),
        "verdict-pointer": (f"# Handoff\n\nVerdict: coordination/cc-reads-{h[:8]}/pr1/GPT-VERDICT-{h[:8]}.md (read it in full)\n", "reject"),
        "brief-template": (f"# Brief for {h[:8]}\n\nVERDICT: ACK when items 1-7 hold, else CHANGES_REQUESTED with P-levels.\n", "reject"),
    }


def extra_verdict_files():
    """Beyond the harness's 28: one case for each guard of lg_last_verdict and lg_verdict_file_ok that none of them reached."""
    h = HEAD
    return {
        "gate-line-pass-with-p3": (f"# Read\n\nGate line: PASS_WITH_P3 at {h[:8]}\n", "accept"),
        "gate-line-quoted-in-prose": (f"# Read\n\nThe template says \"Gate line: PASS at {h[:8]}\" and this file has no such line.\n", "reject"),
        "record-style-line-in-a-verdict-file": (f"# Notes\n\n- Verdict at {h[:8]}: PASS\n", "reject"),
        "cr-word-only-on-line-two": (f"# GPT verdict on PR x#44 at {h}: ACK\nThe previous round was CHANGES_REQUESTED.\n", "accept"),
        "another-colon-between-head-and-word": (f"# GPT verdict on PR x#44 at {h}: note: ACK\n", "reject"),
        "gate-line-then-record-style-line": (f"# Read\n\nGate line: PASS at {h[:8]}\n\n- Verdict at {h[:8]}: CHANGES_REQUESTED\n", "accept"),
    }


class VerdictFileTests(LandingCase):
    def test_synthetic_verdict_files_through_both_loops_and_the_gpt_block(self):
        cases = synthetic_verdict_files()
        self.assertEqual(len(cases), 28)
        self.assertEqual(len(extra_verdict_files()), 6)
        for name, (content, expected) in {**cases, **extra_verdict_files()}.items():
            path = self.write(f"{name}.md", content)
            for script in (self.uet, self.nas):
                with self.subTest(file=name, site=f"{script.key}.verdict_files"):
                    self.assertEqual(accept(self.verdict_files(script, path, HEAD)[0]), expected)
            with self.subTest(file=name, site="uet.gpt_verdict"):
                self.assertEqual(accept(self.gpt_block(path, HEAD)[0], 9), expected)

    def test_an_accepted_file_is_rejected_for_another_head(self):
        for name, (content, expected) in {**synthetic_verdict_files(), **extra_verdict_files()}.items():
            if expected != "accept":
                continue
            path = self.write(f"{name}.md", content)
            for script in (self.uet, self.nas):
                with self.subTest(file=name, site=script.key):
                    self.assertEqual(accept(self.verdict_files(script, path, "1234abcd" + "0" * 32)[0]), "reject")
            with self.subTest(file=name, site="uet.gpt_verdict"):
                self.assertEqual(accept(self.gpt_block(path, "1234abcd" + "0" * 32)[0], 9), "reject")

    def test_head_prefix_must_be_eight_lower_case_hex_characters(self):
        path = self.write("ack.md", f"# GPT verdict on PR x#1 at {HEAD}: ACK\n")
        for script in (self.uet, self.nas):
            for prefix in ("3d8c634", "3D8C6344", "3d8c634g", "3d8c63444"):
                with self.subTest(site=script.key, prefix=prefix):
                    prelude = f"R=x/y; N=1\n{script.block}\n"
                    code, out = self.bash(prelude, f'lg_verdict_file_ok {q(path)} {prefix}')
                    self.assertEqual(code, 1, out)
                    self.assertIn("not 8 lower-case hex", out)

    def test_a_missing_file_is_rejected_with_its_reason(self):
        absent = self.dir / "absent.md"
        for script in (self.uet, self.nas):
            with self.subTest(site=script.key, where="the loop"):
                code, out = self.verdict_files(script, absent, HEAD)
                self.assertEqual(code, 2)
                self.assertIn("verdict file missing", out)
            with self.subTest(site=script.key, where="lg_verdict_file_ok"):
                code, out = self.bash(f"R=x/y; N=1\n{script.block}\n", f"lg_verdict_file_ok {q(absent)} {HEAD[:8]}")
                self.assertEqual((code, out), (1, "file missing"))

    def test_landing_gate_rule_needs_a_receipt_naming_the_head(self):
        phrases = ("The path to PASS is the rebase.", "This is a landing gate.", "Do this before landing.",
                   "A landing condition applies.", "THE PATH TO PASS IS HERE")
        receipt = self.write("receipt.txt", f"gates done at {HEAD[:8]}\n")
        wrong = self.write("wrong-receipt.txt", f"gates done at {OTHER[:8]}\n")
        near = self.write("near-receipt.txt", f"gates done at {HEAD[:7]}g\n")  # seven of the eight characters
        for phrase in phrases:
            path = self.write("gate.md", f"# GPT verdict on PR x#44 at {HEAD}: ACK\n\n{phrase}\n")
            for script in (self.uet, self.nas):
                with self.subTest(site=script.key, phrase=phrase):
                    self.assertEqual(self.verdict_files(script, path, HEAD)[0], 2)
                    self.assertEqual(self.verdict_files(script, path, HEAD, gates_done=wrong)[0], 2)
                    self.assertEqual(self.verdict_files(script, path, HEAD, gates_done=near)[0], 2)
                    self.assertEqual(self.verdict_files(script, path, HEAD, gates_done=self.dir / "absent.txt")[0], 2)
                    self.assertEqual(self.verdict_files(script, path, HEAD, gates_done=receipt)[0], 0)
        plain = self.write("plain.md", f"# GPT verdict on PR x#44 at {HEAD}: ACK\n\nnothing about gates\n")
        for script in (self.uet, self.nas):
            with self.subTest(site=script.key, phrase="none"):
                self.assertEqual(self.verdict_files(script, plain, HEAD)[0], 0)

    def test_nas_binds_the_receipt_to_the_resolved_head_not_the_callers_shorter_prefix(self):
        # #975 (Codex P2 at af9d1901): nas checked the receipt for ${E:0:8}, the caller's prefix, while the verdicts are checked for the
        # resolved ${EF:0:8}; given a seven-character prefix, a receipt naming only those seven characters passed (exit 0 at af9d1901).
        path = self.write("gate.md", f"# GPT verdict on PR x#44 at {HEAD}: ACK\n\nThis is a landing gate.\n")
        short = self.write("short-receipt.txt", f"gates done at {HEAD[:7]}g\n")
        full = self.write("receipt.txt", f"gates done at {HEAD[:8]}\n")
        for name, receipt, expected in (("a receipt naming only the caller's seven characters", short, 2), ("a receipt naming the resolved head", full, 0)):
            with self.subTest(case=name):
                code, out = self.receipt_loop(path, HEAD[:7], HEAD, receipt)
                self.assertEqual(code, expected, out)
                if expected:
                    self.assertIn(f"set GATES_DONE=<receipt naming {HEAD[:8]}>", out)


# ---------------------------------------------------------------------------------------------- 3. the trading-cc-read gate
def synthetic_records():
    h, o = "aabbccdd11223344556677889900aabbccddeeff", "11223344ffeeddccbbaa00998877665544332211"
    return h, {
        "last-verdict-pass": (f"# r\n\n- **Verdict at `{o[:8]}`: CHANGES_REQUESTED**\n\n- **Verdict at `{h[:8]}`: PASS at micro scope**\n", "accept"),
        "last-verdict-cr-earlier-pass": (f"# r\n\n- **Verdict at `{h[:8]}`: PASS**\n\nlater: **Verdict at `{h[:8]}`: CHANGES_REQUESTED** (Astra)\n", "reject"),
        "pass-belongs-to-another-head": (f"# r\n\n- **Verdict at `{o[:8]}`: PASS**\n\n- Verdict at {h[:8]}: CHANGES_REQUESTED\n", "reject"),
        "head-only-in-prose": (f"# r\n\n{h[:8]} was read and everything passed: PASS\n", "reject"),
        "heading-then-next-line": (f"# r\n\n### Verdict at `{h[:8]}`\nPASS at micro scope\n", "reject"),
        "gate-line-last": (f"# r\n\n### Verdict at `{h[:8]}`\nCHANGES_REQUESTED\n\nGate line: PASS at {h[:8]}\n", "accept"),
        "gate-line-before-cr": (f"# r\n\nGate line: PASS at {h[:8]}\n\n**Verdict at {h[:8]}: CHANGES_REQUESTED**\n", "reject"),
        "both-words-one-line": (f"# r\n\n**Verdict at {h[:8]}: CHANGES_REQUESTED, my PASS is withdrawn**\n", "reject"),
        "ack-verdict": (f"# r\n\nVerdict: ACK at {h[:8]}\n", "accept"),
        "no-verdict-line": (f"# r\n\nread {h[:8]}; all good, PASS\n", "reject"),
        "upper-verdict": (f"# r\n\nVERDICT {h[:8]}: PASS\n", "accept"),
        "empty": ("", "reject"),
        "head-inside-longer-hex": (f"# r\n\n**Verdict at 00{h[:8]}: PASS**\n", "reject"),
        "head-after-the-first-colon": (f"# r\n\nVerdict: the read of {h[:8]}: PASS\n", "reject"),
        "verdict-inside-a-word": (f"# r\n\nMyverdict at {h[:8]}: PASS\n", "reject"),
        "another-colon-between-head-and-word": (f"# r\n\nVerdict at {h[:8]}: note: PASS\n", "reject"),
        "decorated-word": (f"# r\n\n- Verdict at {h[:8]}: **PASS**\n", "accept"),
    }


class TccReadGateTests(LandingCase):
    def status(self, state, description, updated="2026-10-10T00:00:00Z", context="trading-cc-read"):
        return {"context": context, "state": state, "description": description, "updated_at": updated}

    def test_the_synthetic_records_decide_by_their_last_verdict_line(self):
        head, records = synthetic_records()
        self.assertEqual(len(records), 17, "the harness's 12 and five more")
        coord = self.dir / f"coord-{next(self.counter)}"
        (coord / "trading-cc/reads").mkdir(parents=True)
        reasons = {"no-verdict-line": "no Verdict/Gate line gives a verdict for aabbccdd",
                   "last-verdict-cr-earlier-pass": "the last verdict line for aabbccdd is CHANGES_REQUESTED"}
        for name, (content, expected) in records.items():
            (coord / f"trading-cc/reads/{name}.md").write_text(content, encoding="utf-8")
            for script in (self.uet, self.nas):
                with self.subTest(record=name, site=script.key):
                    status = [self.status("success", f"PASS: trading-cc/reads/{name}.md")]
                    code, out = self.record_gate(script, head, coord, status)
                    self.assertEqual(accept(code), expected, out)
                    if name in reasons:
                        self.assertIn(reasons[name], out)

    def test_description_forms(self):
        head = "aabbccdd11223344556677889900aabbccddeeff"
        coord = self.dir / f"coord-{next(self.counter)}"
        (coord / "trading-cc/reads").mkdir(parents=True)
        for relative in ("trading-cc/reads/x.md", "trading-cc/reads/xamd", "trading-cc/reads/x.txt", "trading-cc/x.md"):
            (coord / relative).write_text("# r\n\nVerdict at aabbccdd: PASS\n", encoding="utf-8")
        forms = [("PASS: trading-cc/reads/x.md", "accept"), ("ACK: trading-cc/reads/x.md", "accept"),
                 ("CHANGES_REQUESTED: trading-cc/reads/x.md", "reject"), ("PASS (micro) pending: trading-cc/reads/x.md", "reject"),
                 ("PASSED: trading-cc/reads/x.md", "reject"), ("FAIL: trading-cc/reads/x.md", "reject"),
                 ("PASS: trading-cc/reads/x.txt", "reject"), ("PASS: trading-cc/reads/../x.md", "reject"),
                 ("PASS: trading-cc/reads/x.md and more", "reject"), ("pass: trading-cc/reads/x.md", "reject"),
                 ("xPASS: trading-cc/reads/x.md", "reject"), ("PASS: trading-cc/reads/xamd", "reject"),
                 ("PASS: trading-cc/reads/x.md\nmore", "reject"), ("PASS:  trading-cc/reads/x.md", "reject")]
        for description, expected in forms:
            for script in (self.uet, self.nas):
                with self.subTest(description=description, site=script.key):
                    code = self.record_gate(script, head, coord, [self.status("success", description)])[0]
                    self.assertEqual(accept(code), expected)

    def test_failure_pending_and_other_states_stop_and_no_status_is_no_gate(self):
        head, records = synthetic_records()
        coord = self.dir / f"coord-{next(self.counter)}"
        (coord / "trading-cc/reads").mkdir(parents=True)
        (coord / "trading-cc/reads/good.md").write_text(records["ack-verdict"][0], encoding="utf-8")
        good = "PASS: trading-cc/reads/good.md"
        cases = [("failure with a good description", [self.status("failure", good)], 2),
                 ("pending", [self.status("pending", good)], 2),
                 ("error", [self.status("error", good)], 2),
                 ("no status at all", [], 0),
                 ("another context failing is not this gate", [self.status("failure", good, context="other")], 0),
                 # REST lists a ref's statuses newest first (github/rest-api-description@58b1e0c0 api.github.com.json:55724), as these do
                 ("newer success replaces an older failure", [self.status("success", good, "2026-10-10T01:00:00Z"),
                                                              self.status("failure", good, "2026-10-10T00:00:00Z")], 0),
                 ("newer failure replaces an older success", [self.status("failure", good, "2026-10-10T01:00:00Z"),
                                                              self.status("success", good, "2026-10-10T00:00:00Z")], 2),
                 # #975 B1 (the CC's micro at 5b8ba3b2): two statuses posted in the same second; the first listed is the newest. The
                 # stable sort_by(.updated_at)|last took the older success over the newer failure (exit 0 at 5b8ba3b2).
                 ("a failure in the same second as an older success, listed first", [self.status("failure", good, "2026-10-10T01:00:00Z"),
                                                                                   self.status("success", good, "2026-10-10T01:00:00Z")], 2),
                 ("a success in the same second as an older failure, listed first", [self.status("success", good, "2026-10-10T01:00:00Z"),
                                                                                   self.status("failure", good, "2026-10-10T01:00:00Z")], 0)]
        for name, statuses, expected in cases:
            for script in (self.uet, self.nas):
                with self.subTest(case=name, site=script.key):
                    self.assertEqual(self.record_gate(script, head, coord, statuses)[0], expected)

    def test_a_status_behind_100_newer_statuses_of_other_contexts_still_gates(self):
        # #975 (Codex P1 at nas:234): the statuses list is newest first across every context and its page 1 held 100, so a trading-cc-read
        # status behind 100 newer statuses of other contexts was not on it and gave "no status" (exit 0, nothing printed, at 3e6e7e46). The
        # combined status holds each context once, and every page of it is read (here the 101st context is on page 2).
        head, records = synthetic_records()
        coord = self.dir / f"coord-{next(self.counter)}"
        (coord / "trading-cc/reads").mkdir(parents=True)
        (coord / "trading-cc/reads/good.md").write_text(records["ack-verdict"][0], encoding="utf-8")
        good = "PASS: trading-cc/reads/good.md"

        def behind(state, contexts):
            newer = [self.status("success", "ok", "2026-10-10T02:00:00Z", context=context) for context in contexts]
            return newer + [self.status(state, good, "2026-10-10T01:00:00Z")]

        others = [f"ci/check-{n:03}" for n in range(1, 101)]
        cases = [("a failure behind 100 newer statuses of 100 other contexts", behind("failure", others), 2, "trading-cc-read is failure at"),
                 ("a failure behind 100 newer statuses of one other context", behind("failure", ["ci/other"] * 100), 2, "trading-cc-read is failure at"),
                 ("a pending status behind them", behind("pending", others), 2, "trading-cc-read is pending at"),
                 ("a success behind them is read and its record checked", behind("success", others), 0, "record verified")]
        for name, statuses, expected, phrase in cases:
            for script in (self.uet, self.nas):
                with self.subTest(case=name, site=script.key):
                    code, out = self.record_gate(script, head, coord, statuses)
                    self.assertEqual(code, expected, out)
                    self.assertIn(phrase, out)

    def test_a_combined_status_reply_that_cannot_be_read_stops(self):
        # #975 (Codex P1 at nas:234): with gh exit 0, a reply that is not an array of pages with statuses stops (exit 2) and prints nothing
        # of it; "no status" is only a combined status without the context. jq -n fails at `input` on an empty reply.
        head = "aabbccdd11223344556677889900aabbccddeeff"
        coord = self.dir / f"coord-{next(self.counter)}"
        (coord / "trading-cc/reads").mkdir(parents=True)
        replies = [("an empty reply", ""), ("whitespace", " \n"), ("no page", "[]"), ("an object", json.dumps({"message": ADDRESS})),
                   ("a page without statuses", json.dumps([{"message": ADDRESS}])), ("not JSON", f"<{ADDRESS}>")]
        for name, reply in replies:
            for script in (self.uet, self.nas):
                with self.subTest(case=name, site=script.key):
                    code, out = self.record_gate(script, head, coord, [], FAKE_COMBINED_RAW=reply)
                    self.assertEqual(code, 2, out)
                    self.assertIn("trading-cc-read statuses unreadable at aabbccdd (not a combined status, output withheld): stop", out)
                    self.assertNotIn(ADDRESS[:8], out)
        for name, pages in (("one page without the context", [{"total_count": 1, "statuses": [self.status("failure", "x", context="other")]}]),
                            ("one page without statuses", [{"total_count": 0, "statuses": []}])):
            for script in (self.uet, self.nas):
                with self.subTest(case=name, site=script.key):
                    self.assertEqual(self.record_gate(script, head, coord, [], FAKE_COMBINED_RAW=json.dumps(pages)), (0, ""))

    def test_a_head_that_is_not_hexadecimal_is_refused_with_its_reason(self):
        coord = self.dir / f"coord-{next(self.counter)}"
        (coord / "trading-cc/reads").mkdir(parents=True)
        (coord / "trading-cc/reads/x.md").write_text("# r\n\nVerdict: PASS at GGGGGGGG\n", encoding="utf-8")
        for script in (self.uet, self.nas):
            with self.subTest(site=script.key):
                code, out = self.record_gate(script, "G" * 40, coord, [self.status("success", "PASS: trading-cc/reads/x.md")])
                self.assertEqual(code, 2)
                self.assertIn("not 8 lower-case hex", out)

    def test_a_missing_record_is_rejected(self):
        head = "aabbccdd11223344556677889900aabbccddeeff"
        coord = self.dir / f"coord-{next(self.counter)}"
        (coord / "trading-cc/reads").mkdir(parents=True)
        for script in (self.uet, self.nas):
            with self.subTest(site=script.key):
                code, out = self.record_gate(script, head, coord, [self.status("success", "PASS: trading-cc/reads/none.md")])
                self.assertEqual(code, 2)
                self.assertIn("record missing", out)


# ---------------------------------------------------------------------------------------------- 4. change identity
class ChangeIdentityTests(LandingCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.repo, cls.refs = cls.build_repo(cls.dir)

    @staticmethod
    def build_repo(tmp):
        repo = Path(tmp) / "repo"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        (repo / "manifests").mkdir()
        (repo / "a.txt").write_text("line one\nline two\n")
        (repo / "run.sh").write_text("#!/bin/sh\necho hi\n")
        (repo / "blob.bin").write_bytes(bytes(64))
        (repo / "dash.txt").write_text("alpha\n-- gone\nomega\n")
        (repo / "naïve file.txt").write_text("x\n")
        (repo / "sp ace.txt").write_text("s\n")
        (repo / "ctx.txt").write_text("".join(f"c{i}\n" for i in range(1, 11)))
        (repo / "manifests/evidence.json").write_text('{"rows": 1}\n')
        (repo / "target.txt").write_text("t\n")
        os.symlink("target.txt", repo / "link")

        def commit_all(message):
            git(repo, "add", "-A", "--", ".")
            git(repo, "commit", "-q", "--allow-empty", "-m", message)
            return git(repo, "rev-parse", "HEAD")

        base = commit_all("base")
        git(repo, "update-ref", "refs/remotes/origin/main", base)
        refs = {"base": base}

        def branch(name, start, edit, message):
            git(repo, "checkout", "-q", "-f", "-B", name, start)
            edit()
            refs[name] = commit_all(message)

        def read_edit():
            (repo / "a.txt").write_text("line one\nline two\nline three\n")
            (repo / "run.sh").write_text("#!/bin/sh\necho hi\necho more\n")
            (repo / "blob.bin").write_bytes(bytes([1]) * 64)
            (repo / "dash.txt").write_text("alpha\n-- gone\nomega\nextra\n")
            (repo / "naïve file.txt").write_text("x\ny\n")
            (repo / "sp ace.txt").write_text("s\nt\n")
            (repo / "ctx.txt").write_text("".join(f"c{i}\n" if i != 5 else "c5 edited\n" for i in range(1, 11)))
            (repo / "manifests/evidence.json").write_text('{"rows": 2}\n')

        branch("read", "main", read_edit, "read head")
        branch("same-again", "read", lambda: None, "same content, new commit")
        branch("v-ordinary", "read", lambda: (repo / "a.txt").write_text("line one\nline two\nline three\nline four\n"), "ordinary line")
        branch("v-binary", "read", lambda: (repo / "blob.bin").write_bytes(bytes([2]) * 64), "other bytes of a binary file")
        branch("v-execbit", "read", lambda: os.chmod(repo / "a.txt", 0o755), "executable bit")
        branch("v-space-name", "read", lambda: (repo / "sp ace.txt").write_text("s\nu\n"), "text change in a file name with a space")
        branch("v-nonascii-name", "read", lambda: (repo / "naïve file.txt").write_text("x\nz\n"), "text change in a non-ASCII file name")
        branch("v-removed-dashdash", "read", lambda: (repo / "dash.txt").write_text("alpha\nomega\nextra\n"), "removed base line starting --")
        branch("v-added-plusplus", "read", lambda: (repo / "a.txt").write_text("line one\nline two\nline three\n++ tampered\n"), "added line starting ++")
        branch("v-trailing-space", "read", lambda: (repo / "a.txt").write_text("line one\nline two\nline three \n"), "trailing space on an added line")
        branch("v-extra-file", "read", lambda: (repo / "new.txt").write_text("n\n"), "extra file")
        branch("v-evidence-only", "read", lambda: (repo / "manifests/evidence.json").write_text('{"rows": 3}\n'), "evidence.json differs only")
        branch("v-symlink", "read", lambda: (os.remove(repo / "link"), os.symlink("run.sh", repo / "link")), "retargeted symlink")
        branch("v-moved-line", "read", lambda: (repo / "a.txt").write_text("line three\nline one\nline two\n"), "same added line at another position")
        branch("v-copy", "read", lambda: ((repo / "a.txt").write_text("line one\nline two\nline three\nline four\n"),
                                          (repo / "a-copy.txt").write_text("line one\nline two\nline three\n")), "a copy of a modified file")
        # a main that moved: an edit two lines away from the PR's edit of ctx.txt, and a new file
        branch("main2", "main", lambda: ((repo / "ctx.txt").write_text("".join(f"c{i}\n" if i != 2 else "c2 main\n" for i in range(1, 11))),
                                         (repo / "extra-main.txt").write_text("m\n")), "main moves")
        git(repo, "checkout", "-q", "-f", "-B", "rebased", "main2")
        git(repo, "cherry-pick", refs["read"])
        refs["rebased"] = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-q", "-f", "-B", "merged", "read")
        git(repo, "merge", "-q", "--no-ff", "-m", "merge main2", "main2")
        refs["merged"] = git(repo, "rev-parse", "HEAD")
        return repo, refs

    def cases(self):
        r = self.refs
        return [
            ("identical head", r["read"], r["read"], "same", "base"),
            ("same content in a new commit", r["read"], r["same-again"], "same", "base"),
            ("pure rebase onto a main that moved (hunk context shifts)", r["read"], r["rebased"], "same", "main2"),
            ("merge-update with the moved main", r["read"], r["merged"], "same", "main2"),
            ("control: an ordinary added line", r["read"], r["v-ordinary"], "differ", "base"),
            ("control: a retargeted symlink", r["read"], r["v-symlink"], "differ", "base"),
            ("control: an extra file", r["read"], r["v-extra-file"], "differ", "base"),
            ("blind spot: other bytes of a binary file the PR already edits", r["read"], r["v-binary"], "differ", "base"),
            ("blind spot: only the executable bit of a file the PR already edits", r["read"], r["v-execbit"], "differ", "base"),
            ("blind spot: text change in a file name with a space", r["read"], r["v-space-name"], "differ", "base"),
            ("blind spot: text change in a non-ASCII file name", r["read"], r["v-nonascii-name"], "differ", "base"),
            ("blind spot: a removed base line that starts with --", r["read"], r["v-removed-dashdash"], "differ", "base"),
            ("blind spot: an added line that starts with ++ at column 0", r["read"], r["v-added-plusplus"], "differ", "base"),
            ("blind spot: a trailing space on an added line", r["read"], r["v-trailing-space"], "differ", "base"),
            ("empty change on both sides is refused", r["base"], r["base"], "refuse", "base"),
            ("read head against an empty change differs", r["read"], r["base"], "differ", "base"),
            ("known limitation: the same added line at another position of the same file", r["read"], r["v-moved-line"], "same", "base"),
        ]

    def set_main(self, which):
        git(self.repo, "update-ref", "refs/remotes/origin/main", self.refs["main2"] if which == "main2" else self.refs["base"])

    def test_seventeen_scratch_repository_cases_for_both_scripts(self):
        cases = self.cases()
        self.assertEqual(len(cases), 17)
        for name, a, b, expected, main in cases:
            for script in (self.uet, self.nas):
                with self.subTest(case=name, site=script.key):
                    self.set_main(main)
                    code, out = self.change_same(script, self.repo, a, b)
                    self.assertEqual(code, 0 if expected == "same" else 1, out)

    def test_a_moved_head_is_followed_only_when_it_carries_the_read_heads_change_and_at_most_three_times(self):
        r = self.refs
        cases = [
            ("the same change in a new commit, no follow yet", r["read"], r["same-again"], 0, "base", 0),
            ("the same change, two follows so far", r["read"], r["same-again"], 2, "base", 0),
            ("the same change as the fourth move", r["read"], r["same-again"], 3, "base", 1),
            ("a pure rebase onto a main that moved", r["read"], r["rebased"], 1, "main2", 0),
            ("a different change", r["read"], r["v-ordinary"], 0, "base", 1),
            ("an empty new head", r["read"], "", 0, "base", 1),
            ("a commit the clone does not have", r["read"], "0" * 40, 0, "base", 1),
        ]
        for script in (self.uet, self.nas):
            for name, read, new, follows, main, expected in cases:
                with self.subTest(script=script.key, case=name):
                    self.set_main(main)
                    code, out = self.bash(self.change_prelude(script, self.repo), f"{script.change}\nlg_follow_head {read} {q(new)} {follows}")
                    self.assertEqual(code, expected, out)

    def reference_id(self, commit, exclude=None):
        """patch-id of the neutral diff between the commit and its merge base, spelled out here with every neutralizing flag."""
        env = tests.hermetic_git_environment()
        base = git(self.repo, "merge-base", commit, "origin/main")
        command = ["git", "-C", str(self.repo), "-c", "core.quotePath=false", "-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false",
                   "diff", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames", "-U0", "--binary", base, commit, "--", "."]
        if exclude:
            command.append(exclude)
        patch = subprocess.run(command, capture_output=True, env=env, check=True).stdout
        out = subprocess.run(["git", "patch-id", "--verbatim"], input=patch, capture_output=True, env=env, check=True).stdout
        return out.split()[0].decode()

    def test_identity_is_the_patch_id_of_the_neutral_diff_whatever_the_users_diff_configuration(self):
        self.set_main("base")
        config, attributes = self.repo / ".git/config", self.repo / ".git/info/attributes"
        saved = {config: config.read_bytes(), attributes: attributes.read_bytes() if attributes.exists() else None}
        try:
            for key, value in (("diff.noprefix", "true"), ("diff.mnemonicPrefix", "true"), ("color.ui", "always"),
                               ("color.diff", "always"), ("diff.external", "false"), ("diff.renames", "copies"),
                               ("diff.up.textconv", "sed -e s/line/LINE/")):
                git(self.repo, "config", key, value)
            attributes.parent.mkdir(exist_ok=True)
            attributes.write_text("a.txt diff=up\n", encoding="utf-8")
            # the configuration is effective: a plain `git diff` is no longer the neutral one
            hostile = subprocess.run(["git", "-C", str(self.repo), "diff", "--no-ext-diff", self.refs["base"], self.refs["read"], "--", "a.txt"],
                                     capture_output=True, text=True, env=tests.hermetic_git_environment())
            self.assertNotEqual(hostile.stdout.count("\x1b["), 0, hostile.stderr)
            for commit in ("read", "same-again", "v-ordinary", "v-binary", "v-nonascii-name", "v-execbit", "v-copy"):
                for script in (self.uet, self.nas):
                    with self.subTest(commit=commit, site=script.key):
                        exclude = ":!manifests/evidence.json" if script.key == "nas" else None
                        code, out = self.change_id(script, self.repo, self.refs[commit])
                        self.assertEqual((code, out), (0, self.reference_id(self.refs[commit], exclude)))
        finally:
            config.write_bytes(saved[config])
            if saved[attributes] is None:
                attributes.unlink(missing_ok=True)
            else:
                attributes.write_bytes(saved[attributes])

    def test_evidence_json_is_excluded_in_nas_only(self):
        self.set_main("base")
        read, evidence = self.refs["read"], self.refs["v-evidence-only"]
        self.assertEqual(self.change_same(self.uet, self.repo, read, evidence)[0], 1)
        self.assertEqual(self.change_same(self.nas, self.repo, read, evidence)[0], 0)

    def test_a_change_that_is_empty_only_by_exclusion_is_identified_by_its_file_names(self):
        self.set_main("base")
        repo = self.repo
        git(repo, "checkout", "-q", "-f", "-B", "only-evidence-a", "main")
        (repo / "manifests/evidence.json").write_text('{"rows": 10}\n')
        git(repo, "add", "-A", "--", ".")
        git(repo, "commit", "-q", "-m", "evidence only a")
        a = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "-q", "-f", "-B", "only-evidence-b", "main")
        (repo / "manifests/evidence.json").write_text('{"rows": 11}\n')
        git(repo, "add", "-A", "--", ".")
        git(repo, "commit", "-q", "-m", "evidence only b")
        b = git(repo, "rev-parse", "HEAD")
        # nas leaves evidence.json out, so both changes are empty: they are identified by their file names (the same file)
        self.assertEqual(self.change_same(self.nas, self.repo, a, b)[0], 0)
        self.assertEqual(self.change_same(self.uet, self.repo, a, b)[0], 1)


# ---------------------------------------------------------------------------------------------- 5. the CI line
def check_run(name, status="COMPLETED", conclusion="SUCCESS"):
    return {"__typename": "CheckRun", "name": name, "status": status, "conclusion": conclusion}


def status_context(context, state):
    return {"__typename": "StatusContext", "context": context, "state": state}


def conclusion_states():
    """Every member of GitHub's GraphQL CheckConclusionState, parsed from the schema excerpt in the fixture."""
    excerpt = json.loads(CONCLUSIONS.read_text(encoding="utf-8"))["graphql"]["excerpt"]
    return [line.strip() for line in excerpt if re.fullmatch(r"  [A-Z_]+", line)]


def status_states():
    """Every member of GitHub's GraphQL StatusState, parsed from the schema excerpt in its fixture."""
    excerpt = json.loads(STATUSES.read_text(encoding="utf-8"))["graphql"]["excerpt"]
    return [line.strip() for line in excerpt if re.fullmatch(r"  [A-Z_]+", line)]


def ci_reference_uet(entries):
    """What the CI line must say: incomplete, failing, total and ci-gate successes (the rule, in Python)."""
    incomplete = failing = 0
    for entry in entries:
        kind = entry.get("__typename")
        if kind == "CheckRun":
            if entry.get("status") != "COMPLETED":
                incomplete += 1
            elif entry.get("conclusion") not in PASSING_CONCLUSIONS:
                failing += 1
        elif kind == "StatusContext":
            if entry.get("state") in RUNNING_STATES:
                incomplete += 1
            elif entry.get("state") != "SUCCESS":  # #975 P3: an allow-list, so a state GitHub adds later fails too
                failing += 1
        else:
            incomplete += 1
    gate = sum(1 for e in entries if e.get("__typename") == "CheckRun" and e.get("name") == "ci-gate" and e.get("conclusion") == "SUCCESS")
    return incomplete, failing, len(entries), gate


RUN_IDS = itertools.count(1)  # REST check-run ids: a re-run gets a larger one


def nas_run(name, started, status="completed", conclusion="success", completed=...):
    """A REST check run. completed_at defaults to the start for a completed run and to null for any other (both are nullable)."""
    if completed is ...:
        completed = started if status == "completed" else None
    return {"name": name, "status": status, "conclusion": conclusion, "started_at": started, "completed_at": completed, "id": next(RUN_IDS)}


def ci_reference_nas(runs):
    """#975 round 4 (the CC's P3-1), final round (Astra's follow-up 1 at 5b8ba3b2) and A1 (the CC's Claude micro at 3e6e7e46): a name is
    incomplete while any of its runs is not completed or a completed run has no completed_at; it is failing while one of its completed runs
    ended other than success, neutral or skipped and no run of the name both started and completed after it (a run without either time
    supersedes nothing and is superseded by nothing); validate counts when it is complete, not failing, and a run with its greatest
    completed_at succeeded."""
    names = {}
    for run in runs:
        names.setdefault(run["name"], []).append(run)
    passing = [conclusion.lower() for conclusion in PASSING_CONCLUSIONS]  # REST spells the conclusions in lower case

    def superseded(run, done):
        if run["started_at"] is None or run["completed_at"] is None:
            return False
        return any(other["started_at"] is not None and other["completed_at"] is not None and other["started_at"] > run["started_at"]
                   and other["completed_at"] > run["completed_at"] for other in done)

    incomplete = failing = validated = 0
    for name, group in names.items():
        done = [r for r in group if r["status"] == "completed"]
        stamps = [r["completed_at"] for r in done if r["completed_at"] is not None]
        newest = [r for r in done if r["completed_at"] == (max(stamps) if stamps else None)]
        busy = any(r["status"] != "completed" for r in group) or any(r["completed_at"] is None for r in done)
        fails = any(r["conclusion"] not in passing and not superseded(r, done) for r in done)
        incomplete += busy
        failing += fails
        validated += name == "validate" and not busy and not fails and any(r["conclusion"] == "success" for r in newest)
    return incomplete, failing, len(names), validated


def nas_dominance_cases():
    """#975 A1 (the CC's Claude micro at 3e6e7e46): (case, runs, the counts) for overlapping runs of one name, ties and missing times.
    F passed at 3e6e7e46 (its newest completion is the success) and G at 5b8ba3b2 (its newest start is the success)."""
    def run(name, started, completed, conclusion="success"):
        return nas_run(name, started and f"2026-10-10T{started}Z", conclusion=conclusion, completed=completed and f"2026-10-10T{completed}Z")

    v = run("validate", "09:00:00", "09:05:00")
    return [
        ("F: a failure that started later and finished first, inside a success of its name that finished last",
         [v, run("x", "10:00:00", "10:30:00"), run("x", "10:05:00", "10:06:00", "failure")], (0, 1, 2, 1)),
        ("G: a failure that started first and finished last, around a success of its name",
         [v, run("x", "10:00:00", "10:30:00", "failure"), run("x", "10:05:00", "10:06:00")], (0, 1, 2, 1)),
        ("#886: a cancelled run is superseded by a run that started and completed after it",
         [v, run("x", "10:00:00", "10:02:05", "cancelled"), run("x", "10:02:00", "10:30:00")], (0, 0, 2, 1)),
        ("a failure re-run to success", [v, run("x", "10:00:00", "10:01:00", "failure"), run("x", "10:10:00", "10:12:00")], (0, 0, 2, 1)),
        ("a failure re-run to another failure",
         [v, run("x", "10:00:00", "10:01:00", "failure"), run("x", "10:10:00", "10:12:00", "failure")], (0, 1, 2, 1)),
        ("a failing run with no start is superseded by nothing",
         [v, run("x", None, "10:06:00", "failure"), run("x", "10:10:00", "10:12:00")], (0, 1, 2, 1)),
        ("a run with no start supersedes nothing", [v, run("x", "10:00:00", "10:01:00", "failure"), run("x", None, "10:12:00")], (0, 1, 2, 1)),
        ("a success and a failure at one completed_at fail (P3-1: incomplete, exit 6 after the timeout)",
         [v, run("x", "10:00:00", "10:07:00"), run("x", "10:01:00", "10:07:00", "failure")], (0, 1, 2, 1)),
        ("a success and a neutral at one completed_at pass (P3-2: incomplete, exit 6 after the timeout)",
         [v, run("x", "10:00:00", "10:07:00"), run("x", "10:01:00", "10:07:00", "neutral")], (0, 0, 2, 1)),
        ("validate's neutral and success at one completed_at, the neutral listed first, validate it",
         [run("validate", "10:01:00", "10:07:00", "neutral"), run("validate", "10:00:00", "10:07:00")], (0, 0, 1, 1)),
        ("validate's failure inside its success that finished last does not validate",
         [run("validate", "10:00:00", "10:30:00"), run("validate", "10:05:00", "10:06:00", "failure")], (0, 1, 1, 0)),
        ("the live overlap: a success and a skipped run that completed a second before it started",
         [v, run("x", "02:34:14", "02:34:34"), run("x", "02:34:33", "02:34:32", "skipped")], (0, 0, 2, 1)),
    ]


def nas_page_cases():
    """#975 (Codex P2 at nas:289): (case, pages, the counts). Page 1 holds 100 runs, as with per_page=100, and nas_checks read only it."""
    t = "2026-10-10T10:00:00Z"
    full = [nas_run("validate", t)] + [nas_run(f"check-{n:03}", t) for n in range(1, 100)]
    rerun = [nas_run("validate", t)] + [nas_run(f"check-{n:03}", t) for n in range(1, 99)] + [nas_run("flaky", "2026-10-10T10:10:00Z")]
    return [
        ("a failing run on page 2", [full, [nas_run("late", t, conclusion="failure")]], (0, 1, 101, 1)),
        ("a run still in progress on page 2", [full, [nas_run("late", t, status="in_progress", conclusion=None)]], (1, 0, 101, 1)),
        ("a failure on page 2 superseded by its re-run on page 1", [rerun, [nas_run("flaky", t, conclusion="failure")]], (0, 0, 100, 1)),
    ]


def check_run_pages(pages):
    """The pages as REST serves them: each an object whose total_count is the count over every page."""
    total = sum(len(page) for page in pages)
    return [{"total_count": total, "check_runs": page} for page in pages]


class CiLineTests(LandingCase):
    def test_uet_ci_state_reads_check_runs_by_status_and_commit_statuses_by_state(self):
        green = [check_run("a"), check_run("b"), check_run("ci-gate")]
        cases = [
            ("all green, no commit status", green),
            ("all green plus a SUCCESS trading-cc-read", green + [status_context("trading-cc-read", "SUCCESS")]),
            ("all green plus a PENDING status", green + [status_context("trading-cc-read", "PENDING")]),
            ("all green plus an EXPECTED status", green + [status_context("other", "EXPECTED")]),
            ("all green plus a FAILURE status", green + [status_context("other", "FAILURE")]),
            ("all green plus an ERROR status", green + [status_context("other", "ERROR")]),
            ("all green plus a status in a state GitHub does not list fails closed (synthetic)", green + [status_context("other", UNLISTED_STATE)]),
            ("all green plus a status with no state fails closed", green + [{"__typename": "StatusContext", "context": "other"}]),
            ("an incomplete CheckRun", green + [check_run("slow", "IN_PROGRESS", "")]),
            ("a failing CheckRun", green + [check_run("bad", "COMPLETED", "FAILURE")]),
            ("a cancelled and a timed-out CheckRun", green + [check_run("c", "COMPLETED", "CANCELLED"), check_run("t", "COMPLETED", "TIMED_OUT")]),
            ("a NEUTRAL and a SKIPPED CheckRun do not fail", green + [check_run("n", "COMPLETED", "NEUTRAL"), check_run("s", "COMPLETED", "SKIPPED")]),
            ("ci-gate absent", [check_run("a"), check_run("b")]),
            ("ci-gate failed", [check_run("a"), check_run("ci-gate", "COMPLETED", "FAILURE")]),
            ("a status named ci-gate is not the CheckRun", [check_run("a"), status_context("ci-gate", "SUCCESS")]),
            ("a status that also carries name and conclusion is still not the CheckRun",
             [check_run("a"), {**status_context("ci-gate", "SUCCESS"), "name": "ci-gate", "conclusion": "SUCCESS"}]),
            ("zero entries", []),
            ("an entry of an unknown type counts as running", green + [{"__typename": "Surprise", "name": "x"}]),
        ]
        for name, entries in cases:
            with self.subTest(case=name):
                head = "H" * 40
                code, out = self.ci_line(self.uet, {"headRefOid": head, "statusCheckRollup": entries, "mergeStateStatus": "CLEAN"})
                incomplete, failing, total, gate = ci_reference_uet(entries)
                self.assertEqual((code, out.replace("\t", " ")), (0, f"{head} {incomplete} {failing} {total} {gate} CLEAN"))

    def test_nas_check_run_line_judges_the_latest_run_per_name(self):
        t = "2026-10-10T10:00:00Z"
        cases = [
            ("all green", [nas_run("validate", t), nas_run("lint", t)]),
            ("superseded cancelled run does not count", [nas_run("validate", t, conclusion="cancelled"), nas_run("validate", "2026-10-10T10:05:00Z")]),
            ("latest run failed", [nas_run("validate", t), nas_run("validate", "2026-10-10T10:05:00Z", conclusion="failure")]),
            ("an incomplete check", [nas_run("validate", t), nas_run("slow", "2026-10-10T10:01:00Z", status="in_progress", conclusion="")]),
            ("validate absent", [nas_run("lint", t)]),
            ("action_required counts as failing", [nas_run("validate", t), nas_run("x", t, conclusion="action_required")]),
            ("a latest cancelled run counts as failing", [nas_run("validate", t), nas_run("x", t, conclusion="cancelled")]),
            ("a latest timed_out run counts as failing", [nas_run("validate", t), nas_run("x", t, conclusion="timed_out")]),
            # #975 round 4 (Codex P1 at 761810d7, the CC's P3-1): max_by(.started_at) sorted a queued re-run's null first, so the old success
            # stood for the name (0 incomplete, validate counted: the landing went on while the re-run had not started)
            ("an old success and a queued re-run with no start", [nas_run("validate", t), nas_run("validate", None, status="queued", conclusion=None)]),
            ("an old success and a re-run in progress", [nas_run("validate", t), nas_run("lint", t), nas_run("lint", "2026-10-10T10:06:00Z", status="in_progress", conclusion=None)]),
            ("a superseded run still queued keeps its name incomplete", [nas_run("validate", "2026-10-10T10:05:00Z"), nas_run("validate", None, status="queued", conclusion=None),
                                                                         nas_run("lint", t)]),
            ("the latest completed run decides a failure", [nas_run("validate", t), nas_run("x", t, conclusion="failure"), nas_run("x", "2026-10-10T10:09:00Z")]),
            # #975 final round (Astra's follow-up 1 at 5b8ba3b2, ruled FIX-NOW): max_by([.started_at // "", .id // 0]) let a completed
            # failing re-run with no start lose to an older success (0 failing at 5b8ba3b2); completion decides which run is the latest
            ("a completed failing re-run with no start, newer by completion", [nas_run("validate", "2026-10-10T12:00:00Z"),
                                                                              nas_run("audit", "2026-10-10T12:00:00Z"),
                                                                              nas_run("audit", None, conclusion="failure", completed="2026-10-10T12:10:00Z")]),
            ("a completed run with no completed_at is incomplete", [nas_run("validate", t), nas_run("lint", t, completed=None)]),
            # #975 A1 (the CC's Claude micro at 3e6e7e46): a tie with a failing run was incomplete (exit 6 after the timeout, P3-1); it fails
            ("two completed runs at one completed_at, one failing, fail",
             [nas_run("validate", t), nas_run("lint", t, completed="2026-10-10T10:07:00Z"), nas_run("lint", "2026-10-10T10:01:00Z", conclusion="failure", completed="2026-10-10T10:07:00Z")]),
            ("two completed runs at one completed_at with one conclusion", [nas_run("validate", t), nas_run("validate", "2026-10-10T10:01:00Z", completed=t)]),
            *[(name, runs) for name, runs, _ in nas_dominance_cases()],
        ]
        for name, runs in cases:
            with self.subTest(case=name):
                code, out = self.ci_line(self.nas, {"check_runs": runs})
                incomplete, failing, total, validated = ci_reference_nas(runs)
                self.assertEqual((code, out.replace("\t", " ")), (0, f"{incomplete} {failing} {total} {validated}"))

    def test_nas_a_failing_run_stands_unless_a_run_of_its_name_started_and_completed_after_it(self):
        # #975 A1 (the CC's Claude micro at 3e6e7e46): the counts are written out, and the reference model must agree with them
        for name, runs, counts in nas_dominance_cases():
            with self.subTest(case=name):
                self.assertEqual(ci_reference_nas(runs), counts)
                code, out = self.ci_line(self.nas, {"check_runs": runs})
                self.assertEqual((code, out.split("\t")), (0, [str(n) for n in counts]))

    def test_nas_reads_every_page_of_check_runs(self):
        # #975 (Codex P2 at nas:289): the call read page 1 only, so a check failing or running on page 2 was not seen (the most on 70 live
        # heads on 2026-10-11 was 43 runs, one page); a name with runs on both pages is judged on all of them
        for name, pages, counts in nas_page_cases():
            with self.subTest(case=name):
                self.assertEqual(ci_reference_nas([run for page in pages for run in page]), counts)
                code, out = self.ci_line(self.nas, check_run_pages(pages))
                self.assertEqual((code, out.split("\t")), (0, [str(n) for n in counts]))

    def test_the_conclusion_fixture_is_the_schema_excerpt_it_names(self):
        fixture = json.loads(CONCLUSIONS.read_text(encoding="utf-8"))
        graphql, rest = fixture["graphql"], fixture["rest"]
        first, last = graphql["lines"]
        self.assertEqual(len(graphql["excerpt"]), last - first + 1)
        self.assertTrue(graphql["excerpt"][0].startswith("enum CheckConclusionState "))
        text = "\n".join(graphql["excerpt"]) + "\n"  # the bytes of `sed -n '3974,4018p' schema.docs.graphql`
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), graphql["excerpt_sha256"])
        states = conclusion_states()
        self.assertEqual(len(states), 9)
        self.assertLess(set(PASSING_CONCLUSIONS), set(states))
        # REST's check-run enum is nullable and leaves out two members that its check-suite enum has, so only an allow-list is complete
        self.assertTrue(rest["check_run_conclusion"]["nullable"])
        self.assertEqual(set(states) - {value.upper() for value in rest["check_run_conclusion"]["enum"]}, {"STALE", "STARTUP_FAILURE"})
        self.assertLessEqual({"stale", "startup_failure"}, set(rest["check_suite_conclusion"]["enum"]))

    def test_every_conclusion_but_success_neutral_and_skipped_fails_both_ci_lines(self):
        # #975 P2-3, next to a passing aggregate check: every member of the captured CheckConclusionState, and null. The old lists let
        # ACTION_REQUIRED, STALE, STARTUP_FAILURE and null pass in uet, and stale, startup_failure and null in nas.
        t = "2026-10-10T10:00:00Z"
        for conclusion in [*conclusion_states(), None]:
            failing = "0" if conclusion in PASSING_CONCLUSIONS else "1"
            with self.subTest(script="uet", conclusion=conclusion):
                rollup = [check_run("ci-gate"), check_run("other", "COMPLETED", conclusion)]
                code, out = self.ci_line(self.uet, {"headRefOid": "H" * 40, "statusCheckRollup": rollup, "mergeStateStatus": "CLEAN"})
                self.assertEqual((code, out.split("\t")[1:5]), (0, ["0", failing, "2", "1"]))
            rest = None if conclusion is None else conclusion.lower()
            with self.subTest(script="nas", conclusion=rest):
                code, out = self.ci_line(self.nas, {"check_runs": [nas_run("validate", t), nas_run("other", t, conclusion=rest)]})
                self.assertEqual((code, out.split("\t")), (0, ["0", failing, "2", "1"]))

    def test_the_status_fixture_is_the_schema_excerpt_it_names(self):
        graphql = json.loads(STATUSES.read_text(encoding="utf-8"))["graphql"]
        first, last = graphql["lines"]
        self.assertEqual(len(graphql["excerpt"]), last - first + 1)
        self.assertTrue(graphql["excerpt"][0].startswith("enum StatusState "))
        self.assertEqual(graphql["excerpt"][-1], "}")
        text = "\n".join(graphql["excerpt"]) + "\n"  # the bytes of `sed -n '65267,65292p' schema.docs.graphql`
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), graphql["excerpt_sha256"])
        self.assertEqual(sorted(status_states()), ["ERROR", "EXPECTED", "FAILURE", "PENDING", "SUCCESS"])
        # one schema file for both excerpts: the same address, digest and size
        conclusions = json.loads(CONCLUSIONS.read_text(encoding="utf-8"))["graphql"]
        self.assertEqual({key: graphql[key] for key in ("url", "sha256", "bytes")}, {key: conclusions[key] for key in ("url", "sha256", "bytes")})

    def test_every_commit_status_state_but_success_pending_and_expected_fails_the_uet_ci_line(self):
        # #975 P3, next to a passing ci-gate: every member of the captured StatusState, a state it does not list (synthetic) and none.
        # The old rule counted only FAILURE and ERROR as failing, so a state GitHub adds later passed.
        for state in [*status_states(), UNLISTED_STATE, None]:
            incomplete = "1" if state in RUNNING_STATES else "0"
            failing = "0" if state == "SUCCESS" or state in RUNNING_STATES else "1"
            with self.subTest(state=state):
                rollup = [check_run("ci-gate"), status_context("other", state)]
                code, out = self.ci_line(self.uet, {"headRefOid": "H" * 40, "statusCheckRollup": rollup, "mergeStateStatus": "CLEAN"})
                self.assertEqual((code, out.split("\t")[1:5]), (0, [incomplete, failing, "2", "1"]))


# ---------------------------------------------------------------------------------------------- 6. codex_gate.py
BOT = "chatgpt-codex-connector[bot]"
CREATED = "2026-10-10T12:00:00Z"


COMMENT_IDS = itertools.count(6100000000)  # REST comment ids; GraphQL calls the same number databaseId


def comment(login, when, body=""):
    return {"id": next(COMMENT_IDS), "user": {"login": login}, "created_at": when, "body": body}


STARTED = "2026-10-10T12:00:10Z"  # when the review a summary row reports went Running, unless a test says otherwise


GATE_HEAD = "5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f"  # the pull request's head that the fake serves (pulls/<pr> head.sha)
SUMMARY_FIXTURE = ROOT / "tests/fixtures/landing/codex-summary-comment.json"  # #975 round 4: nas#975's summary comment, captured live


def summary_body(*rows):
    return "<!-- codex-pull-request-review-summary -->\n| # | Status | Commit | Review trigger |\n| --- | --- | --- | --- |\n" + "\n".join(rows)


def graphql_node(c, int32=False):
    """A test comment (REST shape) as the GraphQL IssueComment node the gate reads: the author as an Actor (the connector a Bot whose
    login has no [bot] suffix), each revision's editor (the author unless the test names one), and the id as fullDatabaseId (BigInt, a
    string) and databaseId (Int). int32 serves databaseId as the schema's Int can hold it: null above 2^31 - 1."""
    login = c["user"]["login"]
    author = {"__typename": "Bot", "login": login[:-5]} if login.endswith("[bot]") else {"__typename": "User", "login": login}
    edits = [{"editedAt": e["editedAt"], "diff": e["diff"], "editor": e.get("editor", author)} for e in c.get("edits", [])]
    return {"databaseId": None if int32 and c["id"] >= 2 ** 31 else c["id"], "fullDatabaseId": str(c["id"]), "author": author,
            "createdAt": c["created_at"], "body": c["body"], "userContentEdits": {"nodes": edits}}


def summary(*rows, started=STARTED, history=None):
    """The connector's summary comment with these rows, and its revisions (GraphQL userContentEdits, newest first, as GitHub returns
    them). By default each row that is not Running was Running since `started` in an earlier revision (#975: the connector edits
    one comment in place, measured on nas#974, #975, #979 and #994); `history` gives the earlier revisions' bodies instead."""
    body = summary_body(*rows)
    if history is None:  # #975 round 4: each row Running with its own other cells (kind, commit, trigger kind), as the connector writes it
        history = [summary_body(*(re.sub(r"\*\*[^*]+\*\* <relative-time datetime=\"[^\"]+\">at [^<]+</relative-time>",
                                         f'**Running since** <relative-time datetime="{started}">at {started}</relative-time>', r) for r in rows))] if started else []
    edits = [{"editedAt": f"2026-10-10T12:00:{index:02d}Z", "diff": text} for index, text in enumerate([*history, body])]
    return {**comment(BOT, "2026-10-10T12:00:30Z", body), "edits": edits[::-1] if history else []}


def row(status, when, review=1, commit=GATE_HEAD[:7]):
    """A summary-table row in the connector's layout (tests/fixtures/landing/codex-summary-comment.json): kind, status, commit, trigger."""
    return f'| {review} | **{status}** <relative-time datetime="{when}">at {when}</relative-time> | `{commit}` | Manual request |'


def pending_review():
    return {"user": {"login": BOT}, "submitted_at": None}


def limit_notice(when):
    return comment(BOT, when, "You have reached your Codex usage limits for code reviews. You can see your limits in the Codex usage dashboard.")


class CodexGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("landing_codex_gate", LANDING / "codex_gate.py")
        cls.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gate)

    def run_gate(self, comments=(), timeline=(), reviews=(), reactions=(), created=CREATED, now="2026-10-10T12:05:00Z", fail=None,
                 graphql=None, read=None, head=GATE_HEAD, int32=False, nodes=None):
        """The gate on canned API data. GraphQL serves `graphql` (default: `comments`) as IssueComment nodes, or `nodes` as given; REST
        serves `comments` (the gate read them there before #975 round 4), so two different lists model an edit between two reads."""
        real = self.gate.datetime
        frozen = real.fromisoformat(now.replace("Z", "+00:00"))

        class Frozen(real):
            @classmethod
            def now(cls, tz=None):
                return frozen if tz is None else frozen.astimezone(tz)

        def fake_run(cmd, capture_output=False, text=False, check=False):
            self.assertEqual(cmd[:2], ["gh", "api"], "codex_gate.py reaches GitHub only through gh api")
            if fail == "all" or (fail == "head" and "--paginate" not in cmd) or (fail == "lists" and "--paginate" in cmd and cmd[2] != "graphql") \
                    or (fail == "graphql" and cmd[2] == "graphql"):
                if check:
                    raise subprocess.CalledProcessError(1, cmd, "", "HTTP 502")
                return subprocess.CompletedProcess(cmd, 1, "", "HTTP 502")
            if cmd[2] == "graphql":  # the comments with their revisions, as `gh api graphql --paginate --slurp` gives them: a list of pages
                self.assertEqual(cmd[3:5], ["--paginate", "--slurp"])
                self.assertIn("$endCursor: String", cmd[6])
                self.assertEqual(cmd[7:], ["-f", "owner=o", "-f", "repo=r", "-F", "pr=7"])
                served = nodes if nodes is not None else [graphql_node(c, int32) for c in (comments if graphql is None else graphql)]
                page = {"data": {"repository": {"pullRequest": {"comments": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": served}}}}}
                return subprocess.CompletedProcess(cmd, 0, json.dumps([page]), "")
            path = cmd[-1]
            if "--paginate" not in cmd:
                self.assertTrue(path.endswith("/pulls/7"), path)
                return subprocess.CompletedProcess(cmd, 0, json.dumps({"created_at": created, "head": {"sha": head}}), "")
            self.assertIn("--slurp", cmd)
            lists = {"/issues/7/comments": comments, "/issues/7/timeline": timeline, "/pulls/7/reviews": reviews,
                     "/issues/7/reactions": reactions}
            key = next(k for k in lists if path.split("?")[0].endswith(k))
            return subprocess.CompletedProcess(cmd, 0, json.dumps([list(lists[key])]), "")

        out = io.StringIO()
        with mock.patch.object(self.gate.subprocess, "run", fake_run), mock.patch.object(self.gate, "datetime", Frozen), \
                contextlib.redirect_stdout(out):
            code = self.gate.main("o/r", "7", *([read] if read else []))
        return code, out.getvalue().strip()

    def test_exit_code_precedence_on_canned_api_data(self):
        completed = summary(row("Completed", "2026-10-10T12:01:00Z"))
        cases = [
            # (name, kwargs, expected exit code, text the status line must contain)
            ("a Completed row after the trigger", dict(comments=[completed]), 0, "finished at 2026-10-10T12:01:00Z"),
            ("Completed at 12:01 then Cancelled at 12:02 after the same trigger: any completion evidence passes",
             dict(comments=[summary(row("Completed", "2026-10-10T12:01:00Z"), row("Cancelled", "2026-10-10T12:02:00Z"))]), 0, "finished at 2026-10-10T12:01:00Z"),
            ("a lone Cancelled row", dict(comments=[summary(row("Cancelled", "2026-10-10T12:02:00Z"))]), 4, "ended 'Cancelled'"),
            ("Completed then Running: a running row always blocks",
             dict(comments=[summary(row("Completed", "2026-10-10T12:01:00Z"), row("Running since", "2026-10-10T12:03:00Z"))]), 3, "running since 2026-10-10T12:03:00Z"),
            ("a Running row blocks even with a +1 reaction", dict(comments=[summary(row("Running since", "2026-10-10T12:03:00Z"))],
                                                                    reactions=[{"user": {"login": BOT}, "content": "+1", "created_at": "2026-10-10T12:04:00Z"}]), 3, "running"),
            ("a usage-limit notice after the trigger", dict(comments=[limit_notice("2026-10-10T12:01:00Z")]), 5, "usage-limit"),
            ("an account notice after the trigger", dict(comments=[comment(BOT, "2026-10-10T12:01:00Z", "Please create a Codex account to use reviews.")]), 5, "usage-limit or account notice"),
            ("a notice before the trigger does not count", dict(comments=[limit_notice("2026-10-10T11:00:00Z")], now="2026-10-10T12:05:00Z"), 3, "no Codex review finished"),
            ("completion evidence wins over a later notice", dict(comments=[completed, limit_notice("2026-10-10T12:02:00Z")]), 0, "finished"),
            ("no bot activity for 10 minutes", dict(now="2026-10-10T12:10:00Z"), 5, "no connector activity in 10 min"),
            ("no bot activity for 9 minutes 59 seconds", dict(now="2026-10-10T12:09:59Z"), 3, "no Codex review finished"),
            ("some bot activity (not a notice) keeps waiting past 10 minutes", dict(comments=[comment(BOT, "2026-10-10T12:02:00Z", "Looking into it.")], now="2026-10-10T12:30:00Z"), 3, "no Codex review finished"),
            # #975 (Codex P1 at af9d1901): a +1, a connector review or the no-findings comment names no request, so alone it is no
            # completion (before, each gave 0); a +1 counts once a review has started since the trigger (test_completion_is_bound...).
            ("a +1 reaction alone is no completion", dict(reactions=[{"user": {"login": BOT}, "content": "+1", "created_at": "2026-10-10T12:03:00Z"}]), 3, "no Codex review finished"),
            ("a +1 reaction by a person does not count", dict(reactions=[{"user": {"login": "someone"}, "content": "+1", "created_at": "2026-10-10T12:03:00Z"}]), 3, "no Codex review"),
            ("a different reaction by the bot is activity, not completion", dict(reactions=[{"user": {"login": BOT}, "content": "rocket", "created_at": "2026-10-10T12:03:00Z"}], now="2026-10-10T12:30:00Z"), 3, "no Codex review"),
            # #975 round 4: "Codex reacts with 👀 while any review is running" (the connector's footer, tests/fixtures/landing/codex-summary-comment.json)
            ("the connector's eyes reaction is a review running", dict(reactions=[{"user": {"login": BOT}, "content": "eyes", "created_at": "2026-10-10T12:03:00Z"}], now="2026-10-10T12:30:00Z"), 3, "eyes reaction"),
            ("a connector review alone is no completion", dict(reviews=[{"user": {"login": BOT}, "submitted_at": "2026-10-10T12:04:00Z"}]), 3, "no Codex review finished"),
            ("a review by a person does not count", dict(reviews=[{"user": {"login": "someone"}, "submitted_at": "2026-10-10T12:04:00Z"}]), 3, "no Codex review"),
            ("the no-findings comment alone is no completion", dict(comments=[comment(BOT, "2026-10-10T12:04:00Z", "Codex Review: Didn't find any major issues. Nice work!")]), 3, "no Codex review finished"),
            ("a Completed row whose review started at exactly the trigger time", dict(comments=[summary(row("Completed", "2026-10-10T12:01:00Z"), started=CREATED)]), 0, "finished"),
            ("an account notice in other capitals", dict(comments=[comment(BOT, "2026-10-10T12:01:00Z", "Create a Codex Account first.")]), 5, "usage-limit or account notice"),
            ("a bot comment without the summary marker is not a summary", dict(comments=[comment(BOT, "2026-10-10T12:01:00Z", row("Completed", "2026-10-10T12:01:00Z"))]), 3, "no Codex review"),
            ("a pending connector review (no submission time) is not a finish", dict(reviews=[pending_review()]), 3, "no Codex review"),
            ("a person quoting the no-findings sentence is not the connector", dict(comments=[comment("someone", "2026-10-10T12:04:00Z", "Didn't find any major issues, they said.")]), 3, "no Codex review"),
            ("a person quoting the usage-limit notice is not the connector", dict(comments=[comment("someone", "2026-10-10T12:01:00Z", "You have reached your Codex usage limits, says the bot.")]), 3, "no Codex review"),
            ("a person's reaction is not connector activity",
             dict(reactions=[{"user": {"login": "someone"}, "content": "eyes", "created_at": "2026-10-10T12:02:00Z"}], now="2026-10-10T12:12:00Z"), 5, "no connector activity"),
        ]
        for name, kwargs, code, text in cases:
            with self.subTest(case=name):
                got, line = self.run_gate(**kwargs)
                self.assertEqual((got, text in line), (code, True), line)

    def test_triggers(self):
        done = summary(row("Completed", "2026-10-10T12:05:00Z"))
        later = "2026-10-10T12:10:00Z"
        cases = [
            ("a push after a finished review is not a trigger",
             dict(comments=[done], timeline=[{"event": "head_ref_force_pushed", "created_at": later}, {"event": "committed", "created_at": later}]), 0, "finished"),
            ("a comment from a person asking @codex review is a trigger", dict(comments=[done, comment("someone", later, "@codex review")]), 3, f"latest trigger {later}"),
            ("@codex security review is a trigger", dict(comments=[done, comment("someone", later, "@codex security review")]), 3, f"latest trigger {later}"),
            ("a trigger comment may be indented", dict(comments=[done, comment("someone", later, "  @codex review please")]), 3, f"latest trigger {later}"),
            ("the mention in the middle of a sentence is not a trigger", dict(comments=[done, comment("someone", later, "please ask @codex review later")]), 0, "finished"),
            ("another command is not a trigger", dict(comments=[done, comment("someone", later, "@codex summarize")]), 0, "finished"),
            ("the connector's own mention is not a trigger", dict(comments=[done, comment(BOT, later, "@codex review")]), 0, "finished"),
            ("a ready_for_review event is a trigger", dict(comments=[done], timeline=[{"event": "ready_for_review", "created_at": later}]), 3, f"latest trigger {later}"),
            ("another timeline event is not", dict(comments=[done], timeline=[{"event": "labeled", "created_at": later}]), 0, "finished"),
            ("@codex reviews is not the command", dict(comments=[done, comment("someone", later, "@codex reviews are slow")]), 0, "finished"),
            ("a Cancelled row from before the latest trigger is not this review's end",
             dict(comments=[summary(row("Cancelled", "2026-10-10T12:05:00Z")), comment("someone", later, "@codex review")]), 3, f"latest trigger {later}"),
            ("a connector review from before the latest trigger does not count",
             dict(reviews=[{"user": {"login": BOT}, "submitted_at": "2026-10-10T12:05:00Z"}], comments=[comment("someone", later, "@codex review")]), 3, "no Codex review"),
            ("a +1 reaction from before the latest trigger does not count",
             dict(reactions=[{"user": {"login": BOT}, "content": "+1", "created_at": "2026-10-10T12:05:00Z"}], comments=[comment("someone", later, "@codex review")]), 3, "no Codex review"),
            ("the no-findings comment from before the latest trigger does not count",
             dict(comments=[comment(BOT, "2026-10-10T12:05:00Z", "Didn't find any major issues."), comment("someone", later, "@codex review")]), 3, "no Codex review"),
            ("connector activity from before the latest trigger does not postpone the unavailable verdict",
             dict(comments=[comment(BOT, "2026-10-10T12:01:00Z", "Looking into it."), comment("someone", "2026-10-10T12:02:00Z", "@codex review")],
                  now="2026-10-10T12:13:00Z"), 5, "no connector activity"),
            ("a reaction from before the latest trigger is not activity either",
             dict(reactions=[{"user": {"login": BOT}, "content": "rocket", "created_at": "2026-10-10T12:01:00Z"}],
                  comments=[comment("someone", "2026-10-10T12:02:00Z", "@codex review")], now="2026-10-10T12:13:00Z"), 5, "no connector activity"),
            ("an eyes reaction from before the latest trigger is still a review running",
             dict(reactions=[{"user": {"login": BOT}, "content": "eyes", "created_at": "2026-10-10T12:01:00Z"}],
                  comments=[comment("someone", "2026-10-10T12:02:00Z", "@codex review")], now="2026-10-10T12:13:00Z"), 3, "eyes reaction"),
            ("a summary comment by a person is ignored", dict(comments=[comment("someone", "2026-10-10T12:05:00Z", "<!-- codex-pull-request-review-summary -->\n" + row("Completed", "2026-10-10T12:05:00Z"))],
                                                         now="2026-10-10T12:06:00Z"), 3, "no Codex review"),
        ]
        for name, kwargs, code, text in cases:
            with self.subTest(case=name):
                got, line = self.run_gate(**{"now": "2026-10-10T12:12:00Z", **kwargs})
                self.assertEqual((got, text in line), (code, True), line)

    def test_completion_is_bound_to_a_review_that_started_after_the_latest_trigger(self):
        # #975 (Codex P1 at af9d1901, 2026-10-11): a review running when the latest trigger came (12:10) and finishing after it is not the
        # requested review. Its completion time alone passed the gate (exit 0 at af9d1901), in the gap before the new review's Running row
        # appeared. The start is read from the summary comment's own revisions: the latest earlier one that shows the same row Running.
        trigger = comment("someone", "2026-10-10T12:10:00Z", "@codex security review")
        plus_one = {"user": {"login": BOT}, "content": "+1", "created_at": "2026-10-10T12:12:05Z"}
        later = "2026-10-10T12:13:00Z"
        first_review = [summary_body(row("Running since", "2026-10-10T12:05:00Z"))]
        cases = [
            ("a review that started before the trigger and finished after it (the overlap)",
             dict(comments=[summary(row("Completed", "2026-10-10T12:12:00Z"), started="2026-10-10T12:05:00Z"), trigger]), 3, "did not start after it"),
            ("the same, with the connector's +1 after it", dict(comments=[summary(row("Completed", "2026-10-10T12:12:00Z"), started="2026-10-10T12:05:00Z"), trigger],
                                                             reactions=[plus_one]), 3, "did not start after it"),
            ("a review that started after the trigger and finished", dict(comments=[summary(row("Completed", "2026-10-10T12:12:00Z"), started="2026-10-10T12:10:20Z"), trigger]), 0, "finished at 2026-10-10T12:12:00Z"),
            ("two reviews of one row: the second started after the trigger",
             dict(comments=[summary(row("Completed", "2026-10-10T12:12:00Z"), history=[*first_review, summary_body(row("Completed", "2026-10-10T12:08:00Z")),
                                                                                      summary_body(row("Running since", "2026-10-10T12:10:20Z"))]), trigger]), 0, "finished at 2026-10-10T12:12:00Z"),
            ("two reviews of one row: the row went Running only before the trigger",
             dict(comments=[summary(row("Completed", "2026-10-10T12:12:00Z"), history=first_review), trigger]), 3, "did not start after it"),
            ("another row went Running after the trigger, this one only before it",
             dict(comments=[summary(row("Completed", "2026-10-10T12:12:00Z"), history=[*first_review, summary_body(row("Running since", "2026-10-10T12:10:20Z", review=2))]), trigger]),
             3, "did not start after it"),
            ("a Completed row with no recorded revision is not attributed", dict(comments=[summary(row("Completed", "2026-10-10T12:12:00Z"), started=None), trigger]), 3, "did not start after it"),
            ("the +1 after a review that started since the trigger is the all-reviews-finished signal",
             dict(comments=[summary(row("Cancelled", "2026-10-10T12:12:00Z"), started="2026-10-10T12:10:20Z"), trigger], reactions=[plus_one]), 0, "finished at 2026-10-10T12:12:05Z"),
            ("a review that started after the trigger and ended Cancelled", dict(comments=[summary(row("Cancelled", "2026-10-10T12:12:00Z"), started="2026-10-10T12:10:20Z"), trigger]), 4, "ended 'Cancelled'"),
            ("the new review's Running row", dict(comments=[summary(row("Running since", "2026-10-10T12:10:20Z")), trigger]), 3, "running since 2026-10-10T12:10:20Z"),
        ]
        for name, kwargs, code, text in cases:
            with self.subTest(case=name):
                got, line = self.run_gate(**{"now": later, **kwargs})
                self.assertEqual((got, text in line), (code, True), line)

    # ------------------------------------------------------------------------------------------ #975 round 4 (findings at 761810d7)
    def test_a_completion_and_a_start_from_two_reads_are_never_paired(self):
        # The CC's P2-1 and GPT P1: the body came from REST and the revisions from a later GraphQL call, and a completion was paired with the
        # newest Running revision of its row, also one that started after it. The connector edits the summary between the two reads: exit 0 at
        # 761810d7 for a review that finished at 12:08 against a 12:10 trigger. The gate now reads body and revisions in one query and
        # gives 3 when the newest revision is not the body, so no timestamp order alone can pair two generations (the second case: a
        # completion at 12:12 is later than the newer start at 12:11).
        trigger = comment("someone", "2026-10-10T12:10:00Z", "@codex review")
        before = summary(row("Completed", "2026-10-10T12:08:00Z"), started="2026-10-10T12:05:00Z")
        after = {**before, "body": summary_body(row("Running since", "2026-10-10T12:10:20Z")),
                 "edits": [{"editedAt": "2026-10-10T12:10:20Z", "diff": summary_body(row("Running since", "2026-10-10T12:10:20Z"))}, *before["edits"]]}
        completed = summary_body(row("Completed", "2026-10-10T12:12:00Z"))
        stale = {**comment(BOT, "2026-10-10T12:00:30Z", completed),
                 "edits": [{"editedAt": "2026-10-10T12:11:01Z", "diff": summary_body(row("Running since", "2026-10-10T12:11:00Z"))},
                           {"editedAt": "2026-10-10T12:05:01Z", "diff": summary_body(row("Running since", "2026-10-10T12:05:00Z"))}]}
        cases = [("an edit between the REST and GraphQL reads", dict(comments=[before, trigger], graphql=[after, trigger], now="2026-10-10T12:10:21Z"), 3, "running since 2026-10-10T12:10:20Z"),
                 ("one reply whose newest revision is not its body", dict(comments=[stale, trigger], now="2026-10-10T12:12:30Z"), 3, "is not its body"),
                 ("the same summary once its body caught up", dict(comments=[{**stale, "edits": [{"editedAt": "2026-10-10T12:12:01Z", "diff": completed}, *stale["edits"]]}, trigger],
                                                                   now="2026-10-10T12:12:30Z"), 0, "finished at 2026-10-10T12:12:00Z")]
        for name, kwargs, code, text in cases:
            with self.subTest(case=name):
                got, line = self.run_gate(**kwargs)
                self.assertEqual((got, text in line), (code, True), line)

    def test_the_attributed_review_must_be_of_the_read_head_or_the_current_head(self):
        # The CC's P3-3 (R1): the row's commit cell was unused, so a review of bfbcdcb counted after a force-push to another head (a
        # replay of nas#1009 gave 0 at 761810d7). Now the cell must be a prefix of the read head (the third argument) or the current head.
        trigger = comment("someone", "2026-10-10T12:10:00Z", "@codex review")
        other = "bfbcdcb" + "1" * 33
        done = summary(row("Completed", "2026-10-10T12:12:00Z", commit=other[:7]), started="2026-10-10T12:10:20Z")
        cases = [("a review of another commit", dict(comments=[done, trigger]), 3, f"was of commit {other[:7]}"),
                 ("the same review when it is of the read head", dict(comments=[done, trigger], read=other), 0, "finished at 2026-10-10T12:12:00Z"),
                 ("the same review when it is of the current head", dict(comments=[done, trigger], head=other), 0, "finished at 2026-10-10T12:12:00Z"),
                 ("a +1 after a review of another commit is no completion either", dict(comments=[done, trigger],
                  reactions=[{"user": {"login": BOT}, "content": "+1", "created_at": "2026-10-10T12:12:05Z"}]), 3, f"was of commit {other[:7]}")]
        for name, kwargs, code, text in cases:
            with self.subTest(case=name):
                got, line = self.run_gate(now="2026-10-10T12:13:00Z", **kwargs)
                self.assertEqual((got, text in line), (code, True), line)

    def test_only_the_connectors_revisions_count_and_a_summary_another_account_edited_stops(self):
        # The CC's P3-6: UserContentEdit.editor was never read, so a Running revision a person wrote counted as a start, and a summary a
        # person edited last was believed (both 0 at 761810d7).
        trigger = comment("someone", "2026-10-10T12:10:00Z", "@codex review")
        person = {"__typename": "User", "login": "someone"}
        done = summary_body(row("Completed", "2026-10-10T12:12:00Z"))
        planted = {**comment(BOT, "2026-10-10T12:00:30Z", done),
                   "edits": [{"editedAt": "2026-10-10T12:12:01Z", "diff": done},
                             {"editedAt": "2026-10-10T12:10:21Z", "diff": summary_body(row("Running since", "2026-10-10T12:10:20Z")), "editor": person},
                             {"editedAt": "2026-10-10T12:05:01Z", "diff": summary_body(row("Running since", "2026-10-10T12:05:00Z"))}]}
        edited = {**comment(BOT, "2026-10-10T12:00:30Z", done),
                  "edits": [{"editedAt": "2026-10-10T12:12:30Z", "diff": done, "editor": person},
                            {"editedAt": "2026-10-10T12:10:21Z", "diff": summary_body(row("Running since", "2026-10-10T12:10:20Z"))}]}
        cases = [("a Running revision written by a person is no start", planted, 3, "did not start after it"),
                 ("a summary last edited by a person", edited, 4, "by an account other than the connector")]
        for name, summary_comment, code, text in cases:
            with self.subTest(case=name):
                got, line = self.run_gate(comments=[summary_comment, trigger], now="2026-10-10T12:13:00Z")
                self.assertEqual((got, text in line), (code, True), line)

    def test_the_connectors_eyes_reaction_holds_a_finished_review(self):
        # "Codex reacts with 👀 while any review is running" (the footer): a finished review and a second one running that has no row yet
        # (exit 0 at 761810d7, which counted eyes as activity only).
        trigger = comment("someone", "2026-10-10T12:10:00Z", "@codex review")
        done = summary(row("Completed", "2026-10-10T12:12:00Z"), started="2026-10-10T12:10:20Z")
        got, line = self.run_gate(comments=[done, trigger], reactions=[{"user": {"login": BOT}, "content": "eyes", "created_at": "2026-10-10T12:12:30Z"}],
                                  now="2026-10-10T12:13:00Z")
        self.assertEqual((got, "eyes reaction is on the pull request since 2026-10-10T12:12:30Z" in line), (3, True), line)

    def test_a_comment_id_beyond_32_bits_still_finds_its_revisions(self):
        # The CC's P3-5: the gate keyed revisions by databaseId, an Int (32 bits) in the schema, and the ids are about 6.1e9; GitHub serves
        # them today, a server that keeps to the schema's Int would not (null here), and no revision matched (3 at 761810d7).
        done = summary(row("Completed", "2026-10-10T12:01:00Z"))
        self.assertGreaterEqual(done["id"], 2 ** 31)
        got, line = self.run_gate(comments=[done], int32=True)
        self.assertEqual((got, "finished at 2026-10-10T12:01:00Z" in line), (0, True), line)

    def test_visible_connector_activity_is_never_unavailable(self):
        # GPT P2 at 761810d7: activity counted only comment and reaction creation, so the same unattributable completion was refused (3) at
        # 12:13 and passed as "no connector activity" (5) at 12:21. An edit of a summary, or a row's time, after the trigger is activity too.
        trigger = comment("someone", "2026-10-10T12:10:00Z", "@codex review")
        unattributed = summary(row("Completed", "2026-10-10T12:12:00Z"), started=None)
        late_edit = {**comment(BOT, "2026-10-10T12:00:30Z", summary_body(row("Cancelled", "2026-10-10T12:09:00Z"))),
                     "edits": [{"editedAt": "2026-10-10T12:11:00Z", "diff": summary_body(row("Cancelled", "2026-10-10T12:09:00Z"))},
                               {"editedAt": "2026-10-10T12:05:01Z", "diff": summary_body(row("Running since", "2026-10-10T12:05:00Z"))}]}
        for name, summary_comment in (("a completion with no attributable start", unattributed), ("an edit after the trigger, of an older row", late_edit)):
            for now in ("2026-10-10T12:13:00Z", "2026-10-10T12:21:00Z"):
                with self.subTest(case=name, now=now):
                    got, line = self.run_gate(comments=[summary_comment, trigger], now=now)
                    self.assertEqual((got, "Codex unavailable" in line), (3, False), line)
        with self.subTest(case="no connector activity at all is still unavailable"):
            self.assertEqual(self.run_gate(comments=[trigger], now="2026-10-10T12:21:00Z")[0], 5)

    def test_the_captured_summary_comment_of_nas975(self):
        # The connector's real layout and revisions, as the gate's own query returned them on 2026-10-11 (masked; nothing needed it): the
        # 10:42:50Z "@codex review" on nas#975 started a review of 761810d at 10:43:04Z that completed at 10:55:31Z.
        capture = json.loads(SUMMARY_FIXTURE.read_text(encoding="utf-8"))["graphql"]
        node = capture["node"]
        self.assertEqual(hashlib.sha256(node["body"].encode("utf-8")).hexdigest(), capture["body_sha256"])
        self.assertIn(capture["footer"], node["body"])
        self.assertEqual(node["userContentEdits"]["nodes"][0]["diff"], node["body"], "the newest revision is the body")
        head = "761810d703bae174331d03ffc922316dd92d1712"
        rest = {"id": int(node["fullDatabaseId"]), "user": {"login": BOT}, "created_at": node["createdAt"], "body": node["body"]}
        trigger = comment("someone", "2026-10-11T10:42:50Z", "@codex review")

        def gate(trigger, now, **kwargs):
            served = [{**node, "databaseId": rest["id"]}, graphql_node(trigger)]
            return self.run_gate(comments=[rest, trigger], nodes=served, created="2026-10-10T16:59:48Z", now=now, **kwargs)

        cases = [("the completed review of the head", trigger, "2026-10-11T10:56:00Z", dict(head=head), 0,
                  "finished at 2026-10-11T10:55:31Z after the latest trigger 2026-10-11T10:42:50Z"),
                 ("the same after a newer trigger", comment("someone", "2026-10-11T10:56:10Z", "@codex review"), "2026-10-11T10:56:30Z", dict(head=head), 3,
                  "no Codex review finished since the latest trigger 2026-10-11T10:56:10Z"),
                 ("the same once the head moved on, without the read head", trigger, "2026-10-11T10:56:00Z", dict(head="0" * 40), 3, "was of commit 761810d"),
                 ("the same once the head moved on, given the read head", trigger, "2026-10-11T10:56:00Z", dict(head="0" * 40, read=head), 0, "finished")]
        for name, request, now, kwargs, code, text in cases:
            with self.subTest(case=name):
                got, line = gate(request, now, **kwargs)
                self.assertEqual((got, text in line), (code, True), line)

    def test_a_failing_gh_call_is_an_error_not_a_verdict(self):
        for fail in ("all", "head", "lists"):
            with self.subTest(failing=fail), self.assertRaises(subprocess.CalledProcessError):
                self.run_gate(fail=fail)
        with self.subTest(failing="the summary's revisions"), self.assertRaises(subprocess.CalledProcessError):
            self.run_gate(comments=[summary(row("Completed", "2026-10-10T12:01:00Z"))], fail="graphql")

    def test_a_failing_gate_prints_one_fixed_line_naming_the_error_class_and_exits_4(self):
        # #975 P2: the landing scripts run `python3 -I codex_gate.py <repo> <pr> 2>&1` and echo the output, and an uncaught exception
        # printed its whole traceback: every frame names a file (an install under a home directory, the interpreter's library), and an
        # exception message can carry what gh returned. Run as the scripts run it, from a path with home-path syntax, against a fake gh
        # that fails in three ways, the gate must print one fixed line with the class alone and exit 4.
        address = "gate-leak-4e1b@example.invalid"
        fakes = (("gh exits 1 and writes to stderr", f"#!/bin/sh\necho 'HTTP 502 {address}' >&2\nexit 1\n", "CalledProcessError"),
                 # the comments and lists read fine; the pull request's time is the address (#975 round 4: GraphQL is read first)
                 ("gh answers with a value the gate cannot read (its message names the value)",
                  '#!/bin/sh\ncase "$2" in\n  graphql) echo \'[{"data":{"repository":{"pullRequest":{"comments":{"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[]}}}}}]\' ;;\n'
                  f'  --paginate) echo \'[[]]\' ;;\n  *) echo \'{{"created_at": "{address}", "head": {{"sha": "abc"}}}}\' ;;\nesac\n', "ValueError"),
                 ("there is no gh", None, "FileNotFoundError"))
        for name, script, error in fakes:
            with self.subTest(case=name), tempfile.TemporaryDirectory(prefix="gate-") as scratch:
                scratch = Path(scratch)
                installed = scratch / "home/example/tools"  # home-path syntax, as an install under a home directory has
                installed.mkdir(parents=True)
                shutil.copy(LANDING / "codex_gate.py", installed / "codex_gate.py")
                bin_dir = scratch / "bin"
                bin_dir.mkdir()
                if script is not None:
                    (bin_dir / "gh").write_text(script, encoding="utf-8")
                    (bin_dir / "gh").chmod(0o755)
                done = subprocess.run([sys.executable, "-I", str(installed / "codex_gate.py"), "o/r", "7"], capture_output=True, text=True,
                                      env={"PATH": str(bin_dir), "LC_ALL": "C.UTF-8"}, timeout=30)
                output = done.stdout + done.stderr
                # the problems are named, never quoted: a failure here must not print a path or an address either
                problems = [label for label, found in (
                    ("the exit code is not 4", done.returncode != 4),
                    ("stdout is not the one fixed line", done.stdout != f"Codex gate error: {error}; details withheld\n"),
                    ("something is on stderr", done.stderr != ""),
                    ("a traceback", "Traceback" in output),
                    ("a home path", bool(HOME_PATH.search(output.encode()))),
                    ("what gh returned", address in output),
                ) if found]
                self.assertEqual(problems, [])

    def test_command_line_needs_two_or_three_arguments(self):
        # #975 round 4: the third is the read head (the scripts pass it), whose review counts as well as the current head's.
        for argv in ([], ["o/r"], ["o/r", "7", "abc", "extra"]):
            with self.subTest(argv=argv):
                done = subprocess.run([sys.executable, "-I", str(LANDING / "codex_gate.py"), *argv], capture_output=True, text=True, timeout=30)
                self.assertEqual(done.returncode, 1)
                self.assertIn("usage: codex_gate.py <owner/repo> <pr> [<read head>]", done.stderr)


# ---------------------------------------------------------------------------------------------- 7. the scripts end to end
class EndToEndTests(LandingCase):
    """Each script runs whole against a scratch repository and a fake gh, python3 and sleep (no network, nothing merged)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        git(cls.dir, "init", "-q", "--bare", "-b", "main", "origin.git")
        cls.repo = cls.dir / "work"
        git(cls.dir, "init", "-q", "-b", "main", "work")
        git(cls.repo, "remote", "add", "origin", str(cls.dir / "origin.git"))
        (cls.repo / "base.txt").write_text("base\n")
        git(cls.repo, "add", "--", "base.txt")
        git(cls.repo, "commit", "-q", "-m", "base")
        cls.base = git(cls.repo, "rev-parse", "HEAD")
        git(cls.repo, "push", "-q", "origin", "main")
        git(cls.repo, "checkout", "-q", "-b", "pr")
        (cls.repo / "change.txt").write_text("change\n")
        git(cls.repo, "add", "--", "change.txt")
        git(cls.repo, "commit", "-q", "-m", "the change")
        cls.head = git(cls.repo, "rev-parse", "HEAD")
        git(cls.repo, "push", "-q", "origin", f"pr:refs/pull/{PR}/head")
        git(cls.repo, "checkout", "-q", "-b", "other", "main")
        (cls.repo / "other.txt").write_text("another change\n")
        git(cls.repo, "add", "--", "other.txt")
        git(cls.repo, "commit", "-q", "-m", "another change")
        cls.other = git(cls.repo, "rev-parse", "HEAD")
        git(cls.repo, "checkout", "-q", "main")
        (cls.repo / "moved.txt").write_text("main moved\n")  # main moves; the PR is then rebased onto it
        git(cls.repo, "add", "--", "moved.txt")
        git(cls.repo, "commit", "-q", "-m", "main moves")
        git(cls.repo, "push", "-q", "origin", "main")
        cls.main = git(cls.repo, "rev-parse", "HEAD")
        git(cls.repo, "checkout", "-q", "-b", "main-moves-again", "main")  # #975: a main that moves during the validation (origin has the commit)
        (cls.repo / "moved-again.txt").write_text("main moved again\n")
        git(cls.repo, "add", "--", "moved-again.txt")
        git(cls.repo, "commit", "-q", "-m", "main moves again")
        cls.main_again = git(cls.repo, "rev-parse", "HEAD")
        git(cls.repo, "push", "-q", "origin", "main-moves-again")
        git(cls.repo, "checkout", "-q", "-b", "rebased", "main")
        git(cls.repo, "cherry-pick", cls.head)
        cls.rebased = git(cls.repo, "rev-parse", "HEAD")
        cls.variants = []  # the same change in four more commits: a head that keeps moving by pure rebases
        for number in range(1, 5):
            git(cls.repo, "checkout", "-q", "-B", f"variant{number}", cls.rebased)
            git(cls.repo, "commit", "-q", "--amend", "--allow-empty", "-m", f"the change, variant {number}")
            cls.variants.append(git(cls.repo, "rev-parse", "HEAD"))
        git(cls.repo, "checkout", "-q", "--detach", cls.base)  # the clone's HEAD is not the current main: the scripts must not use it
        cls.home = cls.dir / "home"
        cls.home.mkdir()

    def land(self, script, *, args=None, via=None, head=None, merge_state="CLEAN", rollup=None, checkruns=None, pages=None, statuses=None,
             verdict=None, draft=False, merge_commit="f" * 40, **extra):
        """Run a landing; returns (exit code, stdout+stderr, the fake commands' log lines). pages, a list of lists of check runs, stands
        for checkruns (one page)."""
        run = self.dir / f"run-{next(self.counter)}"
        run.mkdir()
        gate = [check_run("ci-gate")] if rollup is None else rollup
        (run / "prview.json").write_text(json.dumps({
            "headRefOid": head or self.head, "isDraft": draft, "mergeStateStatus": merge_state, "statusCheckRollup": gate,
            "state": "MERGED", "mergeCommit": None if merge_commit is None else {"oid": merge_commit}, "mergedAt": "2026-10-10T00:00:00Z"}))
        (run / "statuses.json").write_text(json.dumps(statuses or []))
        (run / "checkruns.json").write_text(json.dumps(check_run_pages(pages) if pages is not None else
                                                       {"check_runs": checkruns if checkruns is not None else [nas_run("validate", "2026-10-10T10:00:00Z")]}))
        verdict_file = run / "verdict.md"
        verdict_file.write_text(verdict if verdict is not None else f"# Read\n\nVerdict: PASS at {self.head[:8]}\n", encoding="utf-8")
        extra.setdefault("TMPDIR", str(run))  # a failed merge leaves its merge-fail-XXXXXX file here, not in /tmp
        environment = self.env(**{"HOME": str(self.home), "FAKE_LOG": str(run / "log"), "FAKE_PRVIEW": str(run / "prview.json"),
                                  "FAKE_STATUSES": str(run / "statuses.json"), "FAKE_CHECKRUNS": str(run / "checkruns.json"),
                                  "LANDING_UET_REPO": str(self.repo), "LANDING_NAS_REPO": str(self.repo),
                                  "LANDING_COORD": str(self.dir / "coord"), "GIT_AUTHOR_NAME": "landing-test",
                                  "GIT_AUTHOR_EMAIL": "landing@example.invalid", "GIT_COMMITTER_NAME": "landing-test",
                                  "GIT_COMMITTER_EMAIL": "landing@example.invalid", **extra})
        if args is None:
            args = [PR, self.head[:12]] + ([str(verdict_file)] if script.key == "nas" else [])
        done = subprocess.run([str(via or script.path), *args], capture_output=True, text=True, env=environment, cwd=self.dir, timeout=240)
        log = (run / "log").read_text(encoding="utf-8").splitlines() if (run / "log").exists() else []
        return done.returncode, (done.stdout + done.stderr).strip(), log

    def gate_calls(self, log):
        return [line for line in log if line.startswith("python3 -I ") and "validate.py" not in line]

    def merge_calls(self, log):
        return [line for line in log if line.startswith("gh pr merge")]

    def test_uet_lands_when_every_gate_passes_pinned_to_the_head(self):
        code, out, log = self.land(self.uet)
        self.assertEqual(code, 0, out)
        self.assertIn("same change", out)
        self.assertEqual(self.merge_calls(log), [f"gh pr merge {PR} -R {UET_REPO} --squash --match-head-commit {self.head} -A {NOREPLY}"])
        gate = f"{os.path.realpath(LANDING)}/codex_gate.py"
        self.assertEqual(self.gate_calls(log), [f"python3 -I {gate} {UET_REPO} {PR} {self.head}"] * 2, "at the wait and in the final gate")

    def test_nas_lands_when_every_gate_passes_after_validating_the_merge(self):
        code, out, log = self.land(self.nas)
        self.assertEqual(code, 0, out)
        self.assertIn("the merge onto current main validates", out)
        self.assertEqual(self.merge_calls(log), [f"gh pr merge {PR} -R {NAS_REPO} --squash --match-head-commit {self.head} -A {NOREPLY}"])
        gate = f"{os.path.realpath(LANDING)}/codex_gate.py"
        self.assertEqual(self.gate_calls(log), [f"python3 -I {gate} {NAS_REPO} {PR} {self.head}"] * 3, "at the wait, before the validation and in the final gate")
        self.assertEqual([line for line in log if "validate.py" in line], ["python3 -E -s -B scripts/validate.py"])
        trees = [line for line in log if line.startswith("validate-tree ")]
        self.assertEqual(len(trees), 1)
        # the head's change (change.txt) merged onto the CURRENT main (moved.txt), not onto the clone's HEAD
        self.assertEqual(sorted(trees[0].split()[1:]), ["base.txt", "change.txt", "moved.txt"])
        self.assertEqual(sorted(Path("/var/tmp").glob(f"nas-land-{PR}-*")), [], "the temporary worktree is removed")

    def test_gate_path_follows_the_real_script_through_a_symlink_and_a_wrapper(self):
        for script in (self.uet, self.nas):
            link_dir = self.dir / f"link-{next(self.counter)}"
            link_dir.mkdir()
            link = link_dir / f"{script.key}-land"
            link.symlink_to(script.path)
            wrapper = link_dir / f"{script.key}-wrapper"
            wrapper.write_text(f'#!/bin/sh\nexec {q(script.path)} "$@"\n', encoding="utf-8")
            wrapper.chmod(0o755)
            expected = f"{os.path.realpath(LANDING)}/codex_gate.py"
            elsewhere = link_dir / "elsewhere/gate.py"  # #975 P3-4: the scripts stop on a gate file that does not exist
            elsewhere.parent.mkdir()
            elsewhere.write_text("# a gate the fake python3 answers for\n", encoding="utf-8")
            for name, via, extra, gate in (("symlink", link, {}, expected), ("wrapper", wrapper, {}, expected),
                                           ("LANDING_GATE", link, {"LANDING_GATE": str(elsewhere)}, str(elsewhere))):
                with self.subTest(script=script.key, via=name):
                    code, out, log = self.land(script, via=via, **extra)
                    self.assertEqual(code, 0, out)
                    repo, calls = (UET_REPO, 2) if script.key == "uet" else (NAS_REPO, 3)
                    self.assertEqual(self.gate_calls(log), [f"python3 -I {gate} {repo} {PR} {self.head}"] * calls)

    def test_arguments_and_the_read_head_are_checked_first(self):
        code, out, log = self.land(self.nas, args=[PR, self.head[:12]])
        self.assertEqual((code, "no verdict file given" in out), (2, True), out)
        for script, text in ((self.uet, "not resolvable"), (self.nas, "not resolvable")):
            with self.subTest(script=script.key):
                args = [PR, "deadbeefdeadbeef"] + ([str(self.dir / "v.md")] if script.key == "nas" else [])
                code, out, log = self.land(script, args=args)
                self.assertEqual((code, text in out), (3, True), out)
                self.assertEqual((self.gate_calls(log), self.merge_calls(log)), ([], []))

    def test_a_success_status_is_checked_against_its_record_under_landing_coord(self):
        record_dir = self.dir / "coord/trading-cc/reads"
        record_dir.mkdir(parents=True, exist_ok=True)
        name = f"landing-{next(self.counter)}.md"
        status = [{"context": "trading-cc-read", "state": "success", "description": f"PASS: trading-cc/reads/{name}",
                   "updated_at": "2026-10-10T00:00:00Z"}]
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, record="missing"):
                code, out, log = self.land(script, statuses=status)
                self.assertEqual((code, "record missing" in out), (2, True), out)
        (record_dir / name).write_text(f"# r\n\nVerdict: CHANGES_REQUESTED at {self.head[:8]}\n", encoding="utf-8")
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, record="changes requested"):
                code, out, log = self.land(script, statuses=status)
                self.assertEqual((code, self.merge_calls(log)), (2, []), out)
        (record_dir / name).write_text(f"# r\n\nVerdict: CHANGES_REQUESTED at {self.head[:8]}\n\nVerdict: PASS at {self.head[:8]}\n", encoding="utf-8")
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, record="pass"):
                code, out, log = self.land(script, statuses=status)
                self.assertEqual(code, 0, out)
                self.assertIn("record verified", out)

    def test_verdict_gate_stops_before_codex_and_before_any_merge(self):
        refused = f"# Read\n\nVerdict: CHANGES_REQUESTED at {self.head[:8]}\n"
        code, out, log = self.land(self.nas, verdict=refused)
        self.assertEqual(code, 2, out)
        self.assertEqual((self.gate_calls(log), self.merge_calls(log)), ([], []))
        uet_file = self.dir / f"uet-verdict-{next(self.counter)}.md"
        uet_file.write_text(refused, encoding="utf-8")
        code, out, log = self.land(self.uet, VERDICT_FILES=str(uet_file))
        self.assertEqual(code, 2, out)
        self.assertEqual((self.gate_calls(log), self.merge_calls(log)), ([], []))

    def test_a_failing_trading_cc_read_status_stops_both_scripts(self):
        status = [{"context": "trading-cc-read", "state": "failure", "description": "CHANGES_REQUESTED: trading-cc/reads/x.md",
                   "updated_at": "2026-10-10T00:00:00Z"}]
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, statuses=status)
                self.assertEqual(code, 2, out)
                self.assertIn("trading-cc-read is failure", out)
                self.assertEqual((self.gate_calls(log), self.merge_calls(log)), ([], []))

    def test_a_failing_trading_cc_read_status_prints_its_state_never_its_description(self):
        # #975 P2-2 (GPT micro on 754a194f): the failure line interpolated the status description, which can carry an address. It names the
        # state when that is error, failure or pending, anything else as unknown, and never the description.
        for case, state, shown in (("failure", "failure", "failure"), ("error", "error", "error"), ("pending", "pending", "pending"),
                                   ("a state GraphQL has and REST has not", "expected", "unknown"),
                                   ("a state that is text from the API", f"odd {ADDRESS}", "unknown")):
            status = [{"context": "trading-cc-read", "state": state, "description": f"contact {ADDRESS}", "updated_at": "2026-10-10T00:00:00Z"}]
            for script in (self.uet, self.nas):
                with self.subTest(script=script.key, state=case):
                    code, out, log = self.land(script, statuses=status)
                    self.assertEqual((code, self.merge_calls(log), self.gate_calls(log)), (2, [], []), out)
                    self.assertIn(f"trading-cc-read is {shown} at {self.head[:8]} (description withheld", out)
                    self.assertNotIn("example.invalid", out)

    def test_a_failing_gh_call_prints_nothing_it_returned_and_ends_in_its_steps_own_code(self):
        # #975 P2-2 (GPT micro on 754a194f): several gh calls left stderr inherited (nas_land.sh 128, 215, 216, 222; uet_land.sh 162, 199,
        # 218 at that head), and a value read from `gh api` can be an error response's body, which gh writes to stdout. Each call fails in
        # turn with the synthetic address on stderr and, for `gh api`, on stdout too (pkg/cmd/api/api.go:546, :557 of cli v2.102.0):
        # the landing ends in the code its step always had and prints nothing of it. Calls whose failure never stopped a landing (the
        # draft flag, nas's mergeStateStatus, the merged state) still do not.
        body = f'{{"message":"Server Error: contact {ADDRESS}"}}'
        stderr = f"gh: Server Error: contact {ADDRESS} (HTTP 500)"
        head = "pr view * --json headRefOid --jq .headRefOid"
        # site, the failing call (a glob on gh's arguments), the first failing call, land() options, exit code, merge calls, a phrase
        # #975 round 4: a failed statuses call stops as unreadable (it was read as "no status" when its stdout was empty, and as an unknown
        # state when it was a body); the final gate's reads are sites of their own.
        sites = {
            "uet": [
                ("the statuses API", "api repos/*/status*", 1, {}, 2, 0, "trading-cc-read statuses unreadable at"),
                ("the statuses API at the final gate", "api repos/*/status*", 2, {}, 2, 0, "trading-cc-read statuses unreadable at"),
                ("the head, first read", head, 1, {}, 3, 0, "is neither the read head nor a pure rebase"),
                ("the head, read after update-branch", head, 2, {}, 4, 0, "CHANGE DIFFERS"),
                ("the head at the final gate", head, 3, {}, 3, 0, "head moved to ? at the final gate"),
                ("the draft flag", "pr view * --json isDraft *", 1, {}, 0, 1, " ok)"),
                ("the CI state", "pr view * --json headRefOid,statusCheckRollup,mergeStateStatus *", 1, {}, 3, 0, "head moved to ? during CI"),
                ("the CI state at the final gate", "pr view * --json headRefOid,statusCheckRollup,mergeStateStatus *", 2, {}, 3, 0,
                 "head moved to ? in the CI read at the final gate"),
                ("the open review threads", "api graphql*", 1, {"merge_state": "BLOCKED"}, 8, 0, "unresolved review threads: unknown"),
                ("the merged state", "pr view * --json state,mergeCommit,mergedAt *", 1, {}, 0, 1, " ok)"),
                ("the author id", "api users/*", 1, {}, 11, 0, "cannot form the no-reply author address"),
                ("the merge commit", "pr view * --json mergeCommit *", 1, {}, 12, 1, "author address NOT CHECKED"),
                ("the merge commit's author", "api repos/*/commits/ffffffff*", 1, {}, 12, 1, "is NOT the no-reply form"),
            ],
            "nas": [
                ("the statuses API", "api repos/*/status*", 1, {}, 2, 0, "trading-cc-read statuses unreadable at"),
                ("the statuses API at the final gate", "api repos/*/status*", 2, {}, 2, 0, "trading-cc-read statuses unreadable at"),
                ("the head, first read", head, 1, {}, 3, 0, "is neither the read head"),
                ("the head, read after update-branch", head, 2, {"merge_state": "BEHIND"}, 4, 0, "CHANGE DIFFERS after update-branch"),
                ("the head, read in the CI loop", head, 2, {}, 3, 0, "head moved to ?"),
                ("the head at the final gate", head, 3, {}, 3, 0, "head moved to ? at the final gate"),
                ("the merge state", "pr view * --json mergeStateStatus *", 1, {}, 0, 1, " ok)"),
                ("the draft flag", "pr view * --json isDraft *", 1, {}, 0, 1, " ok)"),
                ("the check runs", "api repos/*/check-runs*", 1, {}, 6, 0, "CI timeout"),
                ("the check runs at the final gate", "api repos/*/check-runs*", 2, {}, 5, 0, "is no longer complete and green at the final gate"),
                ("the merged state", "pr view * --json state,mergeCommit,mergedAt *", 1, {}, 0, 1, " ok)"),
                ("the author id", "api users/*", 1, {}, 11, 0, "cannot form the no-reply author address"),
                ("the merge commit", "pr view * --json mergeCommit *", 1, {}, 12, 1, "author address NOT CHECKED"),
                ("the merge commit's author", "api repos/*/commits/ffffffff*", 1, {}, 12, 1, "is NOT the no-reply form"),
            ],
        }
        for script in (self.uet, self.nas):
            for site, call, first, options, code, merges, phrase in sites[script.key]:
                with self.subTest(script=script.key, call=site):
                    got, out, log = self.land(script, FAKE_FAIL=call, FAKE_FAIL_FROM=str(first), FAKE_FAIL_STDERR=stderr,
                                              FAKE_FAIL_STDOUT=body if call.startswith("api ") else "", **options)
                    self.assertEqual((got, len(self.merge_calls(log))), (code, merges), out)
                    self.assertGreaterEqual(sum(fnmatch.fnmatchcase(line[3:], call) for line in log), first, "the failing call was made")
                    self.assertIn(phrase, out)
                    self.assertNotIn("example.invalid", out)
                    self.assertNotIn("Server Error", out)

    def test_a_pure_rebase_of_the_read_head_lands_pinned_to_the_new_head(self):
        for script, repo in ((self.uet, UET_REPO), (self.nas, NAS_REPO)):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, head=self.rebased)
                self.assertEqual(code, 0, out)
                self.assertNotEqual(self.rebased, self.head)
                self.assertEqual(self.merge_calls(log), [f"gh pr merge {PR} -R {repo} --squash --match-head-commit {self.rebased} -A {NOREPLY}"])

    def test_a_failed_address_lookup_stops_before_the_merge_with_11(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                for env in ({"FAKE_USER_RC": "1"}, {"FAKE_USER_ID": "null"}):
                    code, out, log = self.land(script, **env)
                    self.assertEqual((code, self.merge_calls(log)), (11, []), out)
                    self.assertIn("cannot form the no-reply author address", out)

    def test_a_merge_commit_with_another_author_address_exits_12_without_printing_it(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, FAKE_COMMIT_EMAIL="someone.else@example.invalid")
                self.assertEqual(code, 12, out)
                self.assertEqual(len(self.merge_calls(log)), 1, "the landing happened; the exit code reports the check")
                self.assertIn("is NOT the no-reply form", out)
                self.assertNotIn("example.invalid", out)
                self.assertNotIn("someone.else", " ".join(log))

    def test_a_landing_whose_merge_commit_is_unreadable_exits_12(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, merge_commit=None)
                self.assertEqual(code, 12, out)
                self.assertIn("author address NOT CHECKED", out)

    def test_a_draft_is_marked_ready_before_codex_is_asked(self):
        for script, repo in ((self.uet, UET_REPO), (self.nas, NAS_REPO)):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, draft=True)
                self.assertEqual(code, 0, out)
                self.assertIn("marked ready", out)
                ready = log.index(f"gh pr ready {PR} -R {repo}")
                self.assertLess(ready, min(i for i, line in enumerate(log) if line.startswith("python3 -I ")))

    def test_the_head_moving_after_the_read_stops_the_landing(self):
        # headRefOid answers in sequence: the first read of the head, then the later ones
        code, out, log = self.land(self.uet, FAKE_HEADS=f"{self.head} {self.other}")
        self.assertEqual(code, 4, out)
        self.assertIn("CHANGE DIFFERS", out)
        self.assertEqual(self.merge_calls(log), [])
        code, out, log = self.land(self.uet, FAKE_HEADS=f"{self.head} {self.head} {self.other}")
        self.assertEqual(code, 3, out)
        self.assertIn("head moved to", out)
        self.assertEqual(self.merge_calls(log), [])
        code, out, log = self.land(self.nas, FAKE_HEADS=f"{self.head} {self.other}")
        self.assertEqual(code, 3, out)
        self.assertIn("head moved to", out)
        self.assertEqual(self.merge_calls(log), [])

    def test_a_head_that_moves_to_a_pure_rebase_during_ci_is_followed_and_the_merge_is_pinned_to_it(self):
        for script, repo, heads in ((self.uet, UET_REPO, f"{self.head} {self.head} {self.rebased}"), (self.nas, NAS_REPO, f"{self.head} {self.rebased}")):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, FAKE_HEADS=heads)
                self.assertEqual(code, 0, out)
                self.assertIn("carries the read head's change: following it", out)
                self.assertEqual(self.merge_calls(log), [f"gh pr merge {PR} -R {repo} --squash --match-head-commit {self.rebased} -A {NOREPLY}"])

    def test_a_head_that_keeps_moving_is_followed_three_times_and_then_stops_with_3(self):
        v = self.variants
        for script, heads in ((self.uet, [self.head, self.head, *v]), (self.nas, [self.head, *v])):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, FAKE_HEADS=" ".join(heads))
                self.assertEqual(code, 3, out)
                self.assertEqual(out.count("carries the read head's change: following it"), 3, out)
                self.assertIn(f"head moved to {v[3]}", out)
                self.assertEqual(self.merge_calls(log), [])

    def test_codex_reopening_between_the_wait_and_the_merge_stops_with_9(self):
        # #975 round 4: the second call is the final gate in uet_land.sh and the call before the validation in nas_land.sh
        for script, where in ((self.uet, "at the final gate"), (self.nas, "before the validation")):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, FAKE_GATE_SEQ="0 3", FAKE_GATE_LINE="Codex review running since 2026-10-10T00:00:00Z")
                self.assertEqual(code, 9, out)
                self.assertIn(where, out)
                self.assertEqual((len(self.gate_calls(log)), self.merge_calls(log)), (2, []))

    def test_a_gate_that_fails_stops_both_scripts_with_9_at_the_wait_and_before_the_merge(self):
        # #975 P2: codex_gate.py exits 4 with one fixed line when it fails; both scripts treat a 4 as a stop. At the wait, through the
        # real gate (the fake gh has no answer for the pull request, so its first call fails); before the merge, with a canned 4.
        line = "Codex gate error: CalledProcessError; details withheld"
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, at="the wait, through the real gate"):
                code, out, log = self.land(script, FAKE_REAL_PYTHON=sys.executable)
                self.assertEqual(code, 9, out)
                self.assertIn(f"#{PR} {line}: stop, land after Codex finishes", out)
                self.assertNotIn("Traceback", out)
                self.assertEqual((len(self.gate_calls(log)), self.merge_calls(log)), (1, []))
            with self.subTest(script=script.key, at="the second call"):
                code, out, log = self.land(script, FAKE_GATE_SEQ="0 4", FAKE_GATE_LINE=line)
                self.assertEqual(code, 9, out)
                where = "at the final gate" if script.key == "uet" else "before the validation"
                self.assertIn(f"#{PR} {line} {where}: stop", out)
                self.assertEqual((len(self.gate_calls(log)), self.merge_calls(log)), (2, []))

    def test_codex_gate_codes_map_to_continue_poll_or_stop(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, gate="running forever (3)"):
                code, out, log = self.land(script, FAKE_GATE_RC="3", FAKE_GATE_LINE="Codex review running since 2026-10-10T00:00:00Z")
                self.assertEqual(code, 9, out)
                self.assertEqual((len(self.gate_calls(log)), self.merge_calls(log)), (21, []))
            with self.subTest(script=script.key, gate="ended other than Completed (4)"):
                code, out, log = self.land(script, FAKE_GATE_RC="4", FAKE_GATE_LINE="Codex review ended 'Cancelled' at 2026-10-10T00:00:00Z; not Completed")
                self.assertEqual(code, 9, out)
                self.assertEqual((len(self.gate_calls(log)), self.merge_calls(log)), (1, []))

    def test_codex_unavailable_needs_the_gpt_verdict_in_uet_and_proceeds_in_nas(self):
        unavailable = {"FAKE_GATE_RC": "5", "FAKE_GATE_LINE": "Codex unavailable: usage-limit or account notice"}
        code, out, log = self.land(self.uet, **unavailable)
        self.assertEqual(code, 9, out)
        self.assertIn("Codex unavailable: set GPT_VERDICT", out)
        self.assertEqual(self.merge_calls(log), [])
        accepted = self.dir / f"gpt-{next(self.counter)}.md"
        accepted.write_text(f"# GPT verdict on PR x#1 at {self.head}: ACK\n", encoding="utf-8")
        code, out, log = self.land(self.uet, GPT_VERDICT=str(accepted), **unavailable)
        self.assertEqual(code, 0, out)
        self.assertIn("substitute GPT verdict", out)
        self.assertEqual(len(self.merge_calls(log)), 1)
        refused = self.dir / f"gpt-{next(self.counter)}.md"
        refused.write_text(f"# GPT verdict on PR x#1 at {self.head}: CHANGES_REQUESTED\n\nACK elsewhere\n", encoding="utf-8")
        code, out, log = self.land(self.uet, GPT_VERDICT=str(refused), **unavailable)
        self.assertEqual(code, 9, out)
        self.assertEqual(self.merge_calls(log), [])
        code, out, log = self.land(self.nas, **unavailable)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.merge_calls(log)), 1)

    def test_head_that_is_not_the_read_head_nor_its_rebase_stops_with_3(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, head=self.other)
                self.assertEqual(code, 3, out)
                self.assertEqual((self.gate_calls(log), self.merge_calls(log)), ([], []))

    def test_ci_failing_incomplete_and_blocked_stop_before_the_merge(self):
        failing = [check_run("ci-gate"), check_run("bad", "COMPLETED", "FAILURE")]
        running = [check_run("ci-gate"), check_run("slow", "IN_PROGRESS", "")]
        code, out, log = self.land(self.uet, rollup=failing)
        self.assertEqual(code, 5, out)
        self.assertEqual(self.merge_calls(log), [])
        code, out, log = self.land(self.uet, rollup=running)
        self.assertEqual((code, "CI timeout" in out, self.merge_calls(log)), (6, True, []), out)
        code, out, log = self.land(self.uet, merge_state="BLOCKED", FAKE_OPEN_THREADS="3")
        self.assertEqual(code, 8, out)
        self.assertIn("unresolved review threads: 3", out)
        self.assertEqual(self.merge_calls(log), [])
        code, out, log = self.land(self.nas, checkruns=[nas_run("validate", "2026-10-10T10:00:00Z", conclusion="failure")])
        self.assertEqual(code, 5, out)
        code, out, log = self.land(self.nas, merge_state="BLOCKED")
        self.assertEqual(code, 8, out)
        self.assertEqual(self.merge_calls(log), [])

    def test_a_check_ending_other_than_success_neutral_or_skipped_stops_with_5_before_any_merge(self):
        # #975 P2-3: the aggregate check passes (uet ci-gate SUCCESS, nas validate success) and a second check completes with each
        # member of the captured CheckConclusionState, or null; only SUCCESS, NEUTRAL and SKIPPED reach the merge.
        t = "2026-10-10T10:00:00Z"
        for conclusion in [*conclusion_states(), None]:
            rest = None if conclusion is None else conclusion.lower()
            for script, checks in ((self.uet, {"rollup": [check_run("ci-gate"), check_run("other", "COMPLETED", conclusion)]}),
                                   (self.nas, {"checkruns": [nas_run("validate", t), nas_run("other", t, conclusion=rest)]})):
                with self.subTest(script=script.key, conclusion=conclusion):
                    code, out, log = self.land(script, **checks)
                    if conclusion in PASSING_CONCLUSIONS:
                        self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
                    else:
                        self.assertEqual((code, self.merge_calls(log)), (5, []), out)
                        self.assertIn("CI failing=1 of 2", out)

    def test_a_commit_status_other_than_success_stops_uet_before_any_merge_unless_it_is_still_running(self):
        # #975 P3: ci-gate passes and a commit status joins it. SUCCESS merges; PENDING and EXPECTED are running, so the wait ends at its
        # timeout (6); every other state, one GitHub does not list (synthetic) and none included, stops with 5. The old rule let
        # a state outside FAILURE and ERROR through to the merge.
        for state in [*status_states(), UNLISTED_STATE, None]:
            with self.subTest(state=state):
                code, out, log = self.land(self.uet, rollup=[check_run("ci-gate"), status_context("other", state)])
                if state == "SUCCESS":
                    self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
                elif state in RUNNING_STATES:
                    self.assertEqual((code, "CI timeout" in out, self.merge_calls(log)), (6, True, []), out)
                else:
                    self.assertEqual((code, self.merge_calls(log)), (5, []), out)
                    self.assertIn("CI failing=1 of 2", out)

    def test_a_failed_merge_prints_a_class_not_the_gh_output_which_stays_in_a_0600_file(self):
        # #975 P2-2: gh's merge diagnostic can carry an address. The script prints a fixed message with a class from a fixed list and
        # keeps the raw output only in a mktemp file under TMPDIR.
        out_address, err_address = "merge-out-7f3a@example.invalid", "merge-err-91c2@example.invalid"
        stderr = f"GraphQL: refused; contact {err_address}"
        cases = (("a known phrase", f"X Pull request is not mergeable; ask {out_address}", "not_mergeable"),
                 ("no known phrase", f"X failed; ask {out_address}", "other"))
        for script in (self.uet, self.nas):
            for name, stdout, expected in cases:
                with self.subTest(script=script.key, case=name):
                    tmp = self.dir / f"tmp-{next(self.counter)}"
                    tmp.mkdir()
                    code, out, log = self.land(script, FAKE_MERGE_RC="1", FAKE_MERGE_STDOUT=stdout, FAKE_MERGE_STDERR=stderr, TMPDIR=str(tmp))
                    self.assertEqual((code, len(self.merge_calls(log))), (7, 1), out)
                    self.assertNotIn(out_address, out)
                    self.assertNotIn(err_address, out)
                    kept = sorted(tmp.glob("merge-fail-*"))
                    self.assertEqual(len(kept), 1, out)
                    self.assertEqual(stat.S_IMODE(kept[0].stat().st_mode), 0o600)
                    self.assertEqual(kept[0].read_text(encoding="utf-8"), f"{stdout}\n{stderr}\n")
                    self.assertIn(f"#{PR} merge failed (class: {expected}); gh output kept only in local file {kept[0].name} in the temp directory (0600)", out)
                    self.assertNotIn(str(kept[0].parent), out, "the temp directory may hold the account name; print only the file name")

    def test_nas_stops_with_10_when_the_merge_with_current_main_fails_validation(self):
        code, out, log = self.land(self.nas, FAKE_VALIDATE_RC="1")
        self.assertEqual(code, 10, out)
        self.assertIn("validate.py on the merge with current main exited 1", out)
        self.assertEqual(self.merge_calls(log), [])
        self.assertEqual(sorted(Path("/var/tmp").glob(f"nas-land-{PR}-*")), [])

    def test_a_failed_merge_call_is_exit_7_and_a_behind_branch_is_updated_first(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, case="merge refused"):
                code, out, log = self.land(script, FAKE_MERGE_RC="1")
                self.assertEqual(code, 7, out)
        code, out, log = self.land(self.nas, merge_state="BEHIND")
        self.assertEqual(code, 0, out)
        self.assertIn("same change", out)
        self.assertTrue(any(line.startswith(f"gh pr update-branch {PR} -R {NAS_REPO}") for line in log))
        code, out, log = self.land(self.nas, merge_state="BEHIND", FAKE_UPDATE_RC="1")
        self.assertEqual(code, 4, out)  # a code the script's header does not list
        self.assertIn("update-branch refused", out)
        self.assertEqual((self.gate_calls(log), self.merge_calls(log)), ([], []))

    # ------------------------------------------------------------------------------------------ #975 round 3 (findings at af9d1901)
    def test_a_gate_that_turns_unavailable_just_before_the_merge_needs_the_gpt_verdict_in_uet(self):
        # Codex P1 and GPT P2-A: the wait gives 0, an "@codex review" during CI meets the usage limit, and the gate gives 5 just before
        # the merge. uet merged without GPT_VERDICT (exit 0, one merge at af9d1901); nas proceeds on a 5 by its documented policy.
        late = {"FAKE_GATE_SEQ": "0 5", "FAKE_GATE_LINE": "Codex unavailable: usage-limit or account notice"}
        accepted = self.dir / f"gpt-{next(self.counter)}.md"
        accepted.write_text(f"# GPT verdict on PR x#1 at {self.head}: ACK\n", encoding="utf-8")
        wrong = self.dir / f"gpt-{next(self.counter)}.md"
        wrong.write_text(f"# GPT verdict on PR x#1 at {self.other}: ACK\n", encoding="utf-8")
        for name, verdict, expected, merges in (("no GPT_VERDICT", None, 9, 0), ("a GPT_VERDICT naming another head", wrong, 9, 0),
                                                ("an accepted GPT_VERDICT", accepted, 0, 1)):
            with self.subTest(script="uet", case=name):
                code, out, log = self.land(self.uet, **late, **({} if verdict is None else {"GPT_VERDICT": str(verdict)}))
                self.assertEqual((code, len(self.merge_calls(log)), len(self.gate_calls(log))), (expected, merges, 2), out)
                self.assertIn("at the final gate", out)
                self.assertIn("Codex unavailable: set GPT_VERDICT" if expected else "substitute GPT verdict", out)
        with self.subTest(script="nas", case="no GPT_VERDICT"):
            code, out, log = self.land(self.nas, **late)
            self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)

    def test_a_trading_cc_read_verdict_that_changes_during_the_wait_stops_the_merge_with_2(self):
        # Codex P1: tcc_read_gate ran only at the start. A status that turns from success to failure, or a record that gains a later
        # CHANGES_REQUESTED, while the landing waits (here: at the first Codex gate call) merged at af9d1901 (exit 0).
        record_dir = self.dir / "coord/trading-cc/reads"
        record_dir.mkdir(parents=True, exist_ok=True)
        for script in (self.uet, self.nas):
            for change in ("the status turns to failure", "the record gains a later CHANGES_REQUESTED"):
                with self.subTest(script=script.key, change=change):
                    name = f"changing-{next(self.counter)}.md"
                    record = record_dir / name
                    record.write_text(f"# r\n\nVerdict: PASS at {self.head[:8]}\n", encoding="utf-8")
                    status = {"context": "trading-cc-read", "description": f"PASS: trading-cc/reads/{name}", "updated_at": "2026-10-10T00:00:00Z"}
                    if change.startswith("the status"):
                        later = json.dumps([{**status, "state": "failure", "updated_at": "2026-10-10T01:00:00Z"}, {**status, "state": "success"}])
                        hook = f'printf "%s" {q(later)} > "$FAKE_STATUSES"'
                        phrase = f"trading-cc-read is failure at {self.head[:8]}"
                    else:
                        hook = f"printf '\\nVerdict: CHANGES_REQUESTED at {self.head[:8]}\\n' >> {q(record)}"
                        phrase = "does not name it with a last PASS/ACK Verdict line"
                    code, out, log = self.land(script, statuses=[{**status, "state": "success"}], FAKE_GATE_HOOK=hook)
                    # #975 round 4: the final gate reads trading-cc-read before it asks the Codex gate, which nas also asks before the validation
                    self.assertEqual((code, self.merge_calls(log), len(self.gate_calls(log))), (2, [], 1 if script.key == "uet" else 2), out)
                    self.assertIn("record verified", out, "the first read passed")
                    self.assertIn(phrase, out)

    def test_nas_validates_again_when_main_moves_after_the_validation_and_stops_with_13_when_it_keeps_moving(self):
        # Codex P2: --match-head-commit pins only the head, so a main that moved after merge_validate took a merge validated on the old
        # main (one validation, then the merge, at af9d1901). The hook moves origin's main while validate.py runs.
        origin = self.dir / "origin.git"
        once = f'[ -e "$FAKE_LOG.moved" ] || {{ touch "$FAKE_LOG.moved"; git --git-dir={q(origin)} update-ref refs/heads/main {self.main_again}; }}'
        every = (f'if [ "$(git --git-dir={q(origin)} rev-parse refs/heads/main)" = {self.main} ]; then git --git-dir={q(origin)} update-ref refs/heads/main {self.main_again}; '
                 f'else git --git-dir={q(origin)} update-ref refs/heads/main {self.main}; fi')
        try:
            with self.subTest(case="main moves once"):
                code, out, log = self.land(self.nas, FAKE_VALIDATE_HOOK=once)
                self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
                trees = [sorted(line.split()[1:]) for line in log if line.startswith("validate-tree ")]
                self.assertEqual(len(trees), 2, out)
                self.assertNotIn("moved-again.txt", trees[0])
                self.assertIn("moved-again.txt", trees[1], "the second validation ran on the main that moved")
                self.assertIn(f"origin/main moved after the validation on {self.main[:8]}: validating again", out)
            git(origin, "update-ref", "refs/heads/main", self.main)
            with self.subTest(case="main moves after every validation"):
                code, out, log = self.land(self.nas, FAKE_VALIDATE_HOOK=every)
                self.assertEqual((code, self.merge_calls(log)), (13, []), out)
                self.assertEqual(sum(1 for line in log if line.startswith("validate-tree ")), 3)
                self.assertIn("origin/main moved after each of 3 validations: stop, nothing merged", out)
        finally:
            git(origin, "update-ref", "refs/heads/main", self.main)
            git(self.repo, "update-ref", "refs/remotes/origin/main", self.main)

    def test_nas_keeps_validate_output_outside_the_worktree_in_a_0600_file_and_never_prints_it(self):
        # Codex P2 and GPT P2-C: validate.py's output went to $wt.validate.err and its last 300 bytes into the exit-10 line (free text: the
        # stub's address and home path were printed at af9d1901). It is kept in a mktemp file under TMPDIR that outlives the worktree.
        tmp = self.dir / f"tmp-{next(self.counter)}"
        tmp.mkdir()
        text = f"Publication validation failed: {ADDRESS} /home/example/secret"
        code, out, log = self.land(self.nas, FAKE_VALIDATE_RC="1", FAKE_VALIDATE_OUT=text, TMPDIR=str(tmp))
        self.assertEqual((code, self.merge_calls(log)), (10, []), out)
        kept = sorted(tmp.glob("nas-validate-*"))
        self.assertEqual(len(kept), 1, out)
        self.assertEqual(stat.S_IMODE(kept[0].stat().st_mode), 0o600)
        self.assertEqual(kept[0].read_text(encoding="utf-8"), f"{text}\n")
        self.assertIn(f"validate.py on the merge with current main exited 1; its output is kept only in local file {kept[0].name} in the temp directory (0600)", out)
        self.assertNotIn("example.invalid", out)
        self.assertNotIn("/home/example", out)
        self.assertEqual(sorted(Path("/var/tmp").glob(f"nas-land-{PR}-*")), [], "the worktree is removed; the kept file is not in it")

    def test_a_failed_or_malformed_ci_reply_is_never_parsed_into_the_output(self):
        # GPT P2-B: nas word-split a failed check-run call's stdout into its counts. At af9d1901 a body "0 0 <address> 1" printed the address
        # in bash's "integer expected" on every poll, and a body "0" ended the script with an unbound $4 and its path (exit 1). uet printed a
        # CI line's head field, so a reply "<address> 0 0 1 1 CLEAN" printed the address as the head that moved.
        cases = [(self.nas, "api repos/*/check-runs*", f"0 0 {ADDRESS} 1", 6, "CI timeout"),
                 (self.nas, "api repos/*/check-runs*", "0", 6, "CI timeout"),
                 (self.nas, "api repos/*/check-runs*", "", 6, "CI timeout"),
                 (self.uet, "pr view * --json headRefOid,statusCheckRollup,mergeStateStatus *", f"{ADDRESS}\t0\t0\t1\t1\tCLEAN", 3, "head moved to ? during CI")]
        for script, call, stdout, expected, phrase in cases:
            with self.subTest(script=script.key, reply=stdout.replace(ADDRESS, "<address>")):
                code, out, log = self.land(script, FAKE_FAIL=call, FAKE_FAIL_STDOUT=stdout, FAKE_FAIL_STDERR="gh: HTTP 500")
                self.assertEqual((code, self.merge_calls(log)), (expected, []), out)
                self.assertIn(phrase, out)
                for text in ("example.invalid", "integer expected", "unbound variable", str(script.path)):
                    self.assertNotIn(text, out)
        with self.subTest(script="nas", reply="check runs that jq cannot judge, an address in them"):
            # #975 (Codex P2 at nas:289): nas_checks runs jq on the pages itself, and jq's error quotes the start of the value it failed on
            code, out, log = self.land(self.nas, checkruns=ADDRESS)
            self.assertEqual((code, self.merge_calls(log)), (6, []), out)
            self.assertIn("CI timeout", out)
            for text in (ADDRESS[:8], "jq:", "Cannot iterate", "integer expected"):
                self.assertNotIn(text, out)

    def test_local_failures_print_no_path_and_no_diagnostic(self):
        # GPT P2-C and Claude P3-4: a missing gate, a gate that fails before its handler runs or prints something else, a clone that does
        # not exist and a missing verdict file printed their paths at af9d1901 (python3's or git's diagnostic, or the file's full path).
        home = self.dir / f"home-{next(self.counter)}/home/example"
        (home / "tools").mkdir(parents=True)
        broken = home / "tools/codex_gate.py"
        broken.write_text("def (:\n", encoding="utf-8")  # a syntax error: python3 prints a traceback naming the file and exits 1
        chatty = home / "chatty/codex_gate.py"
        chatty.parent.mkdir()
        chatty.write_text(f"print('see {home}/log')\n", encoding="utf-8")  # exit 0, but not one of the gate's status lines
        missing_verdict = home / "verdicts/missing.md"
        for script in (self.uet, self.nas):
            cases = [("a missing gate", {"LANDING_GATE": str(home / "absent/codex_gate.py")}, 9, "codex_gate.py not found (path withheld)", 0),
                     ("a gate with a syntax error", {"LANDING_GATE": str(broken), "FAKE_REAL_PYTHON": sys.executable}, 9, "Codex gate failed with exit 1; details withheld", 1),
                     ("a gate that prints another line", {"LANDING_GATE": str(chatty), "FAKE_REAL_PYTHON": sys.executable}, 9, "Codex gate printed no status line of its own", 1),
                     ("a clone that does not exist", {"LANDING_UET_REPO": str(home / "absent-clone"), "LANDING_NAS_REPO": str(home / "absent-clone")}, 3, "not resolvable", 0)]
            if script.key == "uet":
                cases.append(("a missing verdict file", {"VERDICT_FILES": str(missing_verdict)}, 2, "verdict file missing: missing.md", 0))
            for name, extra, expected, phrase, gate_calls in cases:
                with self.subTest(script=script.key, case=name):
                    code, out, log = self.land(script, **extra)
                    self.assertEqual((code, self.merge_calls(log), len(self.gate_calls(log))), (expected, [], gate_calls), out)
                    self.assertIn(phrase, out)
                    self.assertNotIn("/home/example", out)
                    self.assertNotIn("Traceback", out)
        with self.subTest(script="nas", case="a missing verdict file"):
            code, out, log = self.land(self.nas, args=[PR, self.head[:12], str(missing_verdict)])
            self.assertEqual((code, self.merge_calls(log)), (2, []), out)
            self.assertIn("verdict file missing: missing.md", out)
            self.assertNotIn("/home/example", out)

    def test_a_failed_merge_with_an_unusable_temp_directory_prints_a_fixed_line_and_no_path(self):
        # Claude P3-3: mktemp failed on a TMPDIR that does not exist, printed the template's path (under a home directory here), and the
        # message named an empty file (at af9d1901). Exit 7 is kept, with a fixed message.
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                tmp = self.dir / f"home-{next(self.counter)}/home/example/no-such-dir"
                code, out, log = self.land(script, FAKE_MERGE_RC="1", FAKE_MERGE_STDOUT=f"X failed; ask {ADDRESS}", TMPDIR=str(tmp))
                self.assertEqual((code, len(self.merge_calls(log))), (7, 1), out)
                self.assertIn(f"#{PR} merge failed (class: other); gh output could not be kept, and is not echoed", out)
                for text in ("/home/example", "merge-fail-", "example.invalid", "mktemp"):
                    self.assertNotIn(text, out)

    # ------------------------------------------------------------------------------------------ #975 round 4 (findings at 761810d7)
    def final_reads(self, script, log):
        """The calls between the author-address lookup (the last slow step) and the merge, each named by its kind; the git calls of one
        change-identity check count as one."""
        repo = UET_REPO if script.key == "uet" else NAS_REPO
        start = max(i for i, line in enumerate(log) if line.startswith("gh api users/"))
        end = log.index(self.merge_calls(log)[0])
        kinds = []
        for line in log[start + 1:end]:
            if re.fullmatch(r"gh pr view \S+ -R \S+ --json headRefOid --jq \.headRefOid", line):
                kind = "head"
            elif re.match(r"git (-C \S+ )?(-c \S+ )*(merge-base|diff|patch-id) ", line):
                kind = "change"
            elif re.fullmatch(rf"gh api repos/{repo}/commits/[0-9a-f]{{40}}/status\?per_page=100 --paginate --slurp", line):
                kind = "trading-cc-read"  # #975 (Codex P1 at nas:234): the combined status, every page
            elif line.startswith("python3 -I ") and line.endswith(f"/codex_gate.py {repo} {PR} {self.head}"):
                kind = "codex"
            elif script.key == "uet" and re.match(r"gh pr view \S+ -R \S+ --json headRefOid,statusCheckRollup,mergeStateStatus ", line):
                kind = "ci"
            elif script.key == "nas" and re.fullmatch(rf"gh api repos/{repo}/commits/[0-9a-f]{{40}}/check-runs\?filter=latest&per_page=100 --paginate --slurp", line):
                kind = "ci"  # #975 (Codex P2 at nas:289): every page
            elif re.fullmatch(r"git -C \S+ ls-remote origin refs/heads/main", line):
                kind = "main"
            else:
                kind = line
            if not (kinds and kind == "change" and kinds[-1] == "change"):
                kinds.append(kind)
        return kinds

    def test_the_final_gates_reads_are_the_last_calls_before_the_merge(self):
        # The CC's micro at 761810d7: the gates were read at different points, and slow steps (nas: up to three validations, 56 s each) ran
        # after the last read of some of them. Between the author lookup, the last slow step, and the merge there are now only the final
        # gate's reads, in its order. At 761810d7 uet read only trading-cc-read there and nas nothing (its validations followed the lookup).
        expected = {"uet": ["head", "change", "trading-cc-read", "codex", "ci"], "nas": ["head", "change", "trading-cc-read", "codex", "ci", "main"]}
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                code, out, log = self.land(script)
                self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
                self.assertEqual(self.final_reads(script, log), expected[script.key])
                lookup = max(i for i, line in enumerate(log) if line.startswith("gh api users/"))
                merge = log.index(self.merge_calls(log)[0])
                slow = [i for i, line in enumerate(log[:merge]) if line.startswith(("sleep ", "validate-tree ", "gh pr update-branch ", "gh pr ready "))]
                self.assertLess(max(slow), lookup, "every slow step runs before the author lookup")

    def flips(self, script):
        """(name, land() options, exit code, a phrase of the stop): each gate flipped after its first read and before the final gate, at the
        author-address lookup (the last slow step), or for origin/main right after the validation's read of it."""
        h8 = self.head[:8]
        n = next(self.counter)
        reads = self.dir / "coord/trading-cc/reads"
        reads.mkdir(parents=True, exist_ok=True)
        record = reads / f"flip-{n}.md"
        record.write_text(f"# r\n\nVerdict: PASS at {h8}\n", encoding="utf-8")
        status = {"context": "trading-cc-read", "description": f"PASS: trading-cc/reads/{record.name}", "updated_at": "2026-10-10T00:00:00Z"}
        ok_status = [{**status, "state": "success"}]
        failed = json.dumps([{**status, "state": "failure", "updated_at": "2026-10-10T01:00:00Z"}, {**status, "state": "success"}])
        same_second = json.dumps([{**status, "state": "failure"}, {**status, "state": "success"}])  # one updated_at; the newer listed first
        verdict = self.dir / f"flip-{n}-verdict.md"
        verdict.write_text(f"# Read\n\nVerdict: PASS at {h8}\n", encoding="utf-8")
        gated = self.dir / f"flip-{n}-gated.md"
        gated.write_text(f"# Read\n\nThis is a landing gate.\n\nVerdict: PASS at {h8}\n", encoding="utf-8")
        receipt = self.dir / f"flip-{n}-receipt.txt"
        receipt.write_text(f"gates done at {h8}\n", encoding="utf-8")

        def files(path):
            return {"VERDICT_FILES": str(path)} if script.key == "uet" else {"args": [PR, self.head[:12], str(path)]}

        def at_lookup(hook):
            return {"FAKE_GH_HOOK_ON": "api users/*", "FAKE_GH_HOOK": hook}

        def rewrite(feed, program):
            return at_lookup(f'jq {q(program)} "${feed}" > "${feed}.new" && mv "${feed}.new" "${feed}"')

        queued = (rewrite("FAKE_PRVIEW", f".statusCheckRollup = {json.dumps([check_run('ci-gate', 'QUEUED', None)])}") if script.key == "uet"
                  else rewrite("FAKE_CHECKRUNS", f".check_runs += {json.dumps([nas_run('validate', None, status='queued', conclusion=None)])}"))
        # #975 final round (Astra's follow-up 1 at 5b8ba3b2): a completed failing re-run with no start, newer than the success by completion
        rerun = rewrite("FAKE_CHECKRUNS", f".check_runs += {json.dumps([nas_run('validate', None, conclusion='failure', completed='2026-10-10T10:10:00Z')])}")

        def overlap(first, second):  # #975 A1 (the CC's Claude micro at 3e6e7e46): two runs of one name, 10:00 to 10:30 and 10:05 to 10:06
            runs = [nas_run("x", "2026-10-10T10:00:00Z", conclusion=first, completed="2026-10-10T10:30:00Z"),
                    nas_run("x", "2026-10-10T10:05:00Z", conclusion=second, completed="2026-10-10T10:06:00Z")]
            return rewrite("FAKE_CHECKRUNS", f".check_runs += {json.dumps(runs)}")
        cases = [
            ("a verdict file gains CHANGES_REQUESTED", {**files(verdict), **at_lookup(f"printf '\\nVerdict: CHANGES_REQUESTED at {h8}\\n' >> {q(verdict)}")}, 2,
             f"is CHANGES_REQUESTED"),
            ("GATES_DONE disappears", {**files(gated), "GATES_DONE": str(receipt), **at_lookup(f"rm -f {q(receipt)}")}, 2, "states a landing gate"),
            ("trading-cc-read turns from success to failure", {"statuses": ok_status, **at_lookup(f'printf "%s" {q(failed)} > "$FAKE_STATUSES"')}, 2,
             f"trading-cc-read is failure at {h8}"),
            # #975 B1 (the CC's micro at 5b8ba3b2): the failure has the success's updated_at; sort_by(.updated_at)|last kept the success
            ("trading-cc-read gains a failure in the same second, listed first", {"statuses": ok_status,
             **at_lookup(f'printf "%s" {q(same_second)} > "$FAKE_STATUSES"')}, 2, f"trading-cc-read is failure at {h8}"),
            ("the trading-cc-read read fails with empty stdout", {"statuses": ok_status, "FAKE_FAIL": "api repos/*/status*", "FAKE_FAIL_FROM": "2",
                                                                 "FAKE_FAIL_STDOUT": "", "FAKE_FAIL_STDERR": "HTTP 502"}, 2, "statuses unreadable"),
            ("the trading-cc-read record gains CHANGES_REQUESTED", {"statuses": ok_status, **at_lookup(f"printf '\\nVerdict: CHANGES_REQUESTED at {h8}\\n' >> {q(record)}")}, 2,
             "does not name it with a last PASS/ACK Verdict line"),
            ("Codex gives 3 at the final call", {"FAKE_GATE_SEQ": "0 3" if script.key == "uet" else "0 0 3",
                                                 "FAKE_GATE_LINE": "Codex review running since 2026-10-10T00:00:00Z"}, 9, "at the final gate: stop"),
            ("a CI re-run is queued (started_at null)", queued, 5, "is no longer complete and green at the final gate"),
            ("the head moves (to a pure rebase)", rewrite("FAKE_PRVIEW", f'.headRefOid = "{self.rebased}"'), 3, f"head moved to {self.rebased} at the final gate"),
        ]
        if script.key == "nas":
            cases.append(("a completed failing re-run with no start, newer by completion", rerun, 5, "is no longer complete and green at the final gate"))
            cases.append(("F: a failure that started later and finished first, inside a success of its name", overlap("success", "failure"), 5,
                          "is no longer complete and green at the final gate"))
            cases.append(("G: a failure that started first and finished last, around a success of its name", overlap("failure", "success"), 5,
                          "is no longer complete and green at the final gate"))
            cases.append(("origin/main moves after the validation read it", {"FAKE_GIT_HOOK_ON": "*ls-remote origin refs/heads/main*",
                          "FAKE_GIT_HOOK": f"git --git-dir={q(self.dir / 'origin.git')} update-ref refs/heads/main {self.main_again}"}, 13,
                          f"origin/main moved after the validation on {self.main[:8]} (final gate)"))
        return cases

    def test_each_gate_flipped_before_the_final_gate_stops_the_landing_with_no_merge(self):
        # The CC's micro at 761810d7 (P2-2, P2-3, P2-4, P3-1), the GPT micro (P1, P2) and Codex's four P1 threads: each gate is flipped after
        # its first read; the final gate reads it again and stops with that gate's code, and nothing is merged. At 761810d7 the verdict file,
        # GATES_DONE, the failed read, nas's Codex, the queued re-run, the head and nas's main reached the merge (exit 0, one merge). #975 A1
        # (the CC's Claude micro at 3e6e7e46): the overlap F merged at 3e6e7e46 and its mirror G at 5b8ba3b2.
        origin = self.dir / "origin.git"
        for script in (self.uet, self.nas):
            for name, options, code, phrase in self.flips(script):
                with self.subTest(script=script.key, flip=name):
                    try:
                        got, out, log = self.land(script, **options)
                    finally:
                        git(origin, "update-ref", "refs/heads/main", self.main)
                        git(self.repo, "update-ref", "refs/remotes/origin/main", self.main)
                    self.assertEqual((got, self.merge_calls(log)), (code, []), out)
                    self.assertIn(phrase, out)
                    if "statuses" in options:
                        self.assertIn("record verified", out, "the first read passed")

    def test_a_codex_review_that_starts_during_a_validation_or_its_retry_stops_nas_with_9(self):
        # Codex P1 (nas:290), the CC's P2-4 and GPT P1 at 761810d7: nas asked Codex before one to three validations and never after, so a
        # review that started during them was not seen (exit 0, one merge). The validation hook makes the gate's next answer 3: during
        # the first validation, and during the retry that a main which moved during the first one starts.
        origin = self.dir / "origin.git"
        later = 'printf 3 > "$FAKE_LOG.gate"'
        retry = (f'if [ -e "$FAKE_LOG.moved" ]; then {later}; else touch "$FAKE_LOG.moved"; '
                 f'git --git-dir={q(origin)} update-ref refs/heads/main {self.main_again}; fi')
        for name, hook, validations in (("during the first validation", later, 1), ("during the retry after main moved", retry, 2)):
            with self.subTest(case=name):
                try:
                    code, out, log = self.land(self.nas, FAKE_GATE_SEQ="0 0 0 3", FAKE_VALIDATE_HOOK=hook,
                                               FAKE_GATE_LINE="Codex review running since 2026-10-10T00:00:00Z")
                finally:
                    git(origin, "update-ref", "refs/heads/main", self.main)
                    git(self.repo, "update-ref", "refs/remotes/origin/main", self.main)
                self.assertEqual((code, self.merge_calls(log)), (9, []), out)
                self.assertEqual(sum(1 for line in log if line.startswith("validate-tree ")), validations)
                self.assertIn("at the final gate: stop", out)
        with self.subTest(case="the same answers without a review starting: the landing merges"):
            code, out, log = self.land(self.nas, FAKE_GATE_SEQ="0 0 0 3")
            self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)

    def test_an_unreadable_origin_main_stops_nas_with_its_own_message(self):
        # The CC's P3-4 at 761810d7: a failed git ls-remote was reported as "main moved" and validated again three times (exit 13 with the
        # wrong reason). It is its own stop now, after the validation and at the final gate.
        for first, phrase, validations in (("1", "origin/main is unreadable (git ls-remote failed) after the validation: stop", 1),
                                           ("2", "origin/main is unreadable (git ls-remote failed) at the final gate: stop", 1)):
            with self.subTest(failing_read=first):
                code, out, log = self.land(self.nas, FAKE_GIT_FAIL="*ls-remote origin refs/heads/main*", FAKE_GIT_FAIL_FROM=first)
                self.assertEqual((code, self.merge_calls(log)), (13, []), out)
                self.assertIn(phrase, out)
                self.assertEqual(sum(1 for line in log if line.startswith("validate-tree ")), validations)

    def test_a_completed_failing_rerun_with_no_start_or_a_run_with_no_completion_time_stops_nas(self):
        # #975 final round (Astra's follow-up 1 at 5b8ba3b2, ruled FIX-NOW): audit run 100, a success started at 12:00, and run 101, a
        # completed failure with started_at null that completed at 12:10. max_by([.started_at // "", .id // 0]) kept the success (exit 0,
        # one merge at 5b8ba3b2 and at 761810d7). Completion decides now, and a completed run without completed_at fails closed.
        old = nas_run("audit", "2026-10-10T12:00:00Z")
        new = nas_run("audit", None, conclusion="failure", completed="2026-10-10T12:10:00Z")
        old["id"], new["id"] = 100, 101
        cases = [("Astra's replay: a completed failing re-run with no start", [nas_run("validate", "2026-10-10T12:00:00Z"), old, new], 5,
                  "CI failing=1 of 2"),
                 ("a completed run with no completed_at counts as incomplete", [nas_run("validate", "2026-10-10T12:00:00Z", completed=None)], 6,
                  "CI timeout")]
        for name, runs, code, phrase in cases:
            with self.subTest(case=name):
                got, out, log = self.land(self.nas, checkruns=runs)
                self.assertEqual((got, self.merge_calls(log)), (code, []), out)
                self.assertIn(phrase, out)

    def test_a_failing_run_no_run_of_its_name_supersedes_stops_nas_and_every_page_of_check_runs_is_read(self):
        # #975 A1 (the CC's Claude micro at 3e6e7e46): F merged at 3e6e7e46 (exit 0, one merge) and G at 5b8ba3b2; a success and a failure
        # at one completed_at (P3-1), and a success and a neutral (P3-2), waited for the timeout (exit 6). #975 (Codex P2 at nas:289): a
        # failure on page 2 merged, because page 1 was all that was read. The CI wait polls on while a check is incomplete (exit 6), stops
        # with 5 on a failing one, and goes on to the merge once validate succeeded.
        cases = [(name, {"checkruns": runs}, counts) for name, runs, counts in nas_dominance_cases()]
        cases += [(name, {"pages": pages}, counts) for name, pages, counts in nas_page_cases()]
        for name, options, (incomplete, failing, total, validated) in cases:
            with self.subTest(case=name):
                got, out, log = self.land(self.nas, **options)
                if failing and not incomplete:
                    self.assertEqual((got, self.merge_calls(log)), (5, []), out)
                    self.assertIn(f"CI failing={failing} of {total}", out)
                elif validated and not incomplete:
                    self.assertEqual((got, len(self.merge_calls(log))), (0, 1), out)
                else:
                    self.assertEqual((got, "CI timeout" in out, self.merge_calls(log)), (6, True, []), out)

    def test_a_trading_cc_read_failure_in_the_same_second_as_a_success_stops_at_the_first_read(self):
        # #975 B1 (the CC's micro at 5b8ba3b2): REST lists the newest status first; tcc_read_gate took sort_by(.updated_at)|last, and the
        # stable sort kept the older success of two posted in the same second (record verified, exit 0 and one merge at 5b8ba3b2).
        reads = self.dir / "coord/trading-cc/reads"
        reads.mkdir(parents=True, exist_ok=True)
        record = reads / f"same-second-{next(self.counter)}.md"
        record.write_text(f"# r\n\nVerdict: PASS at {self.head[:8]}\n", encoding="utf-8")
        status = {"context": "trading-cc-read", "description": f"PASS: trading-cc/reads/{record.name}", "updated_at": "2026-10-10T00:00:00Z"}
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, statuses=[{**status, "state": "failure"}, {**status, "state": "success"}])
                self.assertEqual((code, self.merge_calls(log), self.gate_calls(log)), (2, [], []), out)
                self.assertIn(f"trading-cc-read is failure at {self.head[:8]}", out)

    def test_a_trading_cc_read_failure_behind_100_newer_statuses_of_other_contexts_stops_both_scripts(self):
        # #975 (Codex P1 at nas:234): page 1 of the newest-first statuses list held only the 100 newer statuses of other contexts, so the
        # failure was never read and both scripts landed (exit 0, one merge at 3e6e7e46). The combined status is read, every page of it.
        newer = [{"context": f"ci/check-{n:03}", "state": "success", "description": "ok", "updated_at": "2026-10-10T02:00:00Z"} for n in range(1, 101)]
        failed = {"context": "trading-cc-read", "state": "failure", "description": "PASS: trading-cc/reads/none.md", "updated_at": "2026-10-10T01:00:00Z"}
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, statuses=newer + [failed])
                self.assertEqual((code, self.merge_calls(log), self.gate_calls(log)), (2, [], []), out)
                self.assertIn(f"trading-cc-read is failure at {self.head[:8]}", out)

    def test_a_trading_cc_read_lookup_that_fails_with_empty_stdout_stops_with_2(self):
        # Codex P1 (uet:171), the CC's P2-3 and GPT P2 at 761810d7: `[ -n "$s" ] || return 0` took a failed call with nothing on stdout (a
        # refused connection) for "no status", at the first read and at the final one (exit 0, one merge). gh's exit code is kept apart now.
        for script in (self.uet, self.nas):
            for first, where in (("1", "the first read and every later one"), ("2", "the final gate's read only")):
                with self.subTest(script=script.key, failing=where):
                    code, out, log = self.land(script, FAKE_FAIL="api repos/*/status*", FAKE_FAIL_FROM=first, FAKE_FAIL_STDOUT="",
                                               FAKE_FAIL_STDERR="gh: connection refused")
                    self.assertEqual((code, self.merge_calls(log)), (2, []), out)
                    self.assertIn("trading-cc-read statuses unreadable at", out)
                    self.assertNotIn("connection refused", out)

    def lock_path(self, script):
        return self.dir / "coord/command-center/landing-locks" / ("us-equities-trading.lock" if script.key == "uet" else "native-agent-stack.lock")

    def test_a_second_landing_of_the_same_repository_stops_at_once_with_14(self):
        # The CC's brief for round 4: one landing per repository at a time, so our own landings cannot move main under each other's
        # validated base. A held lock stops the second at once, before any call (at 761810d7 there was no lock: it merged).
        import fcntl
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, lock="held"):
                path = self.lock_path(script)
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "a", encoding="utf-8") as held:
                    fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    code, out, log = self.land(script)
                self.assertEqual((code, log), (14, []), out)
                self.assertIn(f"another landing of {path.stem} holds the landing lock: stop, nothing merged", out)
            with self.subTest(script=script.key, lock="released"):
                code, out, log = self.land(script)
                self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
            with self.subTest(script=script.key, lock="cannot be opened"):
                blocker = self.dir / f"home-{next(self.counter)}/home/example/file"
                blocker.parent.mkdir(parents=True)
                blocker.write_text("not a directory\n", encoding="utf-8")
                code, out, log = self.land(script, LANDING_LOCK_DIR=str(blocker / "locks"))
                self.assertEqual((code, log), (14, []), out)
                self.assertIn("the landing lock cannot be opened (path withheld): stop, nothing merged", out)
                self.assertNotIn("/home/example", out)

    def test_a_child_that_outlives_the_landing_does_not_keep_the_lock(self):
        # The lock is descriptor 9, and every child that can outlive the script runs with it closed (git's detached maintenance keeps
        # every other descriptor). Here gh starts a child that is still running when the landing ends; the lock must be free then.
        import fcntl
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                pid = self.dir / f"child-{next(self.counter)}.pid"
                code, out, log = self.land(script, FAKE_GH_HOOK_ON="api users/*",
                                           FAKE_GH_HOOK=f"{q(self.real_sleep)} 30 >/dev/null 2>&1 & echo $! > {q(pid)}")
                try:
                    self.assertEqual(code, 0, out)
                    with open(self.lock_path(script), "a", encoding="utf-8") as lock:
                        try:
                            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError:
                            self.fail("a child of the landing still holds the landing lock")
                finally:
                    with contextlib.suppress(ProcessLookupError, ValueError, FileNotFoundError):
                        os.kill(int(pid.read_text(encoding="utf-8")), signal.SIGTERM)

    def test_a_verdict_record_or_receipt_that_cannot_be_read_stops_and_prints_no_path(self):
        # GPT P2 at 761810d7: head and grep read a verdict file one after the other and printed their diagnostics, which name the path, and
        # a grep that failed was taken as "no verdict line". Unreadable: each consumer refused but printed the path. Removed after its
        # first line was read: line 1's ACK passed over the later CHANGES_REQUESTED (exit 0, one merge). Each file is now read once.
        h8 = self.head[:8]
        reads = self.dir / "coord/trading-cc/reads"
        reads.mkdir(parents=True, exist_ok=True)
        two_verdicts = f"# GPT verdict on PR x#1 at {self.head}: ACK\n\nVerdict: CHANGES_REQUESTED at {h8}\n"
        unavailable = {"FAKE_GATE_RC": "5", "FAKE_GATE_LINE": "Codex unavailable: usage-limit or account notice"}

        def consumer(name, script, path):
            n = next(self.counter)
            if name == "verdict file":
                return ({"VERDICT_FILES": str(path)} if script.key == "uet" else {"args": [PR, self.head[:12], str(path)]}), 2
            if name == "GPT_VERDICT":
                return {"GPT_VERDICT": str(path), **unavailable}, 9
            if name == "trading-cc-read record":
                status = {"context": "trading-cc-read", "state": "success", "description": f"PASS: trading-cc/reads/{path.name}",
                          "updated_at": "2026-10-10T00:00:00Z"}
                return {"statuses": [status]}, 2
            gated = self.dir / f"gated-{n}.md"  # GATES_DONE
            gated.write_text(f"# Read\n\nThis is a landing gate.\n\nVerdict: PASS at {h8}\n", encoding="utf-8")
            return {**({"VERDICT_FILES": str(gated)} if script.key == "uet" else {"args": [PR, self.head[:12], str(gated)]}), "GATES_DONE": str(path)}, 2

        def place(name):
            n = next(self.counter)
            if name == "trading-cc-read record":
                return reads / f"unreadable-{n}.md"
            path = self.dir / f"home-{n}/home/example/reads/{name.replace(' ', '-')}.md"
            path.parent.mkdir(parents=True)
            return path

        cases = []
        for script in (self.uet, self.nas):
            for name in ("verdict file", "trading-cc-read record", "GATES_DONE") + (("GPT_VERDICT",) if script.key == "uet" else ()):
                cases.append((script, name, "unreadable"))
                if name in ("verdict file", "GPT_VERDICT"):
                    cases.append((script, name, "removed after its first line is read"))
        for script, name, mode in cases:
            with self.subTest(script=script.key, file=name, mode=mode):
                if mode == "unreadable" and os.geteuid() == 0:
                    self.skipTest("root reads a file with mode 000")
                path = place(name)
                content = f"gates done at {h8}\n" if name == "GATES_DONE" else (
                    f"# r\n\nVerdict: PASS at {h8}\n" if name == "trading-cc-read record" else
                    two_verdicts if mode != "unreadable" else f"# GPT verdict on PR x#1 at {self.head}: ACK\n")
                path.write_text(content, encoding="utf-8")
                options, expected = consumer(name, script, path)
                if mode == "unreadable":
                    path.chmod(0)
                else:
                    options.update(FAKE_VANISH=str(path), PATH=f"{self.vanish_bin}{os.pathsep}{self.bin}{os.pathsep}{os.environ['PATH']}")
                try:
                    code, out, log = self.land(script, **options)
                finally:
                    with contextlib.suppress(FileNotFoundError):
                        path.chmod(0o600)
                self.assertEqual((code, self.merge_calls(log)), (expected, []), out)
                self.assertNotIn(str(self.dir), out, "no path is printed")
                self.assertNotIn("/home/example", out)

    # ------------------------------------------------------------------------------------------ the CC's live patches of 2026-10-12
    def plant(self, checks):
        """A FAKE_VALIDATE_HOOK that puts each check's script into the validation's worktree, where the hook runs, as a merge holds it."""
        scripts = [check.split(" ", 1)[0] for check in checks]
        return " && ".join(f"mkdir -p {q(Path(script).parent)} && : > {q(script)}" for script in scripts)

    def check_calls(self, log):
        prefix = "python3 -E -s -B "
        return [line[len(prefix):] for line in log if line.startswith(prefix) and line.endswith(" --check")]

    def test_nas_stops_with_10_when_the_merge_passes_validate_py_but_fails_a_currency_check(self):
        # CC correction #176: #1007 bound a file's sha256 in final-stack.json and #1018 changed the file; each was green on its own base,
        # validate.py passed on the merge, #1018 landed and main's shard 0 failed on final_stack.py --check. At 86fa3844 this landing merged
        # (exit 0, one merge) and ran no check. The checks before the failing one run, the rest do not, and its output stays in the 0600 file.
        tmp = self.dir / f"tmp-{next(self.counter)}"
        tmp.mkdir()
        output = f"final-stack.json is stale: {ADDRESS} /home/example/secret"
        code, out, log = self.land(self.nas, FAKE_VALIDATE_HOOK=self.plant(CURRENCY_CHECKS), FAKE_CHECK_FAIL="*scripts/final_stack.py --check",
                                   FAKE_CHECK_OUT=output, TMPDIR=str(tmp))
        self.assertEqual((code, self.merge_calls(log)), (10, []), out)
        self.assertEqual([line for line in log if "validate.py" in line], ["python3 -E -s -B scripts/validate.py"], "validate.py ran and passed")
        self.assertEqual(self.check_calls(log), list(CURRENCY_CHECKS[:5]), "in validate.yml's order, up to the failing check")
        kept = sorted(tmp.glob("nas-validate-*"))
        self.assertEqual(len(kept), 1, out)
        self.assertEqual(stat.S_IMODE(kept[0].stat().st_mode), 0o600)
        self.assertEqual(kept[0].read_text(encoding="utf-8"), f"{output}\n")
        self.assertIn(f"#{PR} the currency check scripts/final_stack.py --check on the merge with current main exited 1; its output is kept only "
                      f"in local file {kept[0].name} in the temp directory (0600), never echoed: stop", out)
        for text in ("example.invalid", "/home/example", "stale"):
            self.assertNotIn(text, out)
        self.assertEqual(sorted(Path("/var/tmp").glob(f"nas-land-{PR}-*")), [], "the worktree is removed")

    def test_nas_runs_each_currency_check_whose_script_the_merge_holds_and_then_lands(self):
        # CC correction #176, the other side: a check runs only when its script is in the merge (the fixture's tree holds none, and none
        # runs), once per validation, and a landing whose checks all pass merges.
        code, out, log = self.land(self.nas)
        self.assertEqual((code, len(self.merge_calls(log)), self.check_calls(log)), (0, 1, []), out)
        held = [check for check in CURRENCY_CHECKS if "gap_crosswalk" not in check]
        code, out, log = self.land(self.nas, FAKE_VALIDATE_HOOK=self.plant(held))
        self.assertEqual((code, len(self.merge_calls(log)), self.check_calls(log)), (0, 1, held), out)
        self.assertIn(f"#{PR} the merge onto current main validates (rc 0: validate.py and the shard-0 currency checks whose scripts it holds)", out)

    def test_a_squash_body_file_that_is_not_a_readable_non_empty_file_stops_both_scripts_with_2_before_any_call(self):
        # SQUASH_BODY_FILE (the CC, 2026-10-12): the CC's live copies check the file before any gate. At 86fa3844 the scripts did not read
        # the variable, and each of these landed (exit 0, one merge, with the default body). "-" would make gh read standard input.
        home = self.dir / f"home-{next(self.counter)}/home/example"
        home.mkdir(parents=True)
        empty = home / "empty.md"
        empty.write_bytes(b"")
        unreadable = home / "unreadable.md"
        unreadable.write_text("The squash body.\n", encoding="utf-8")
        cases = [("missing", home / "missing.md"), ("empty", empty), ("a directory", home), ("standard input", "-")]
        if os.geteuid() != 0:  # root reads a file with mode 000
            cases.append(("unreadable", unreadable))
        unreadable.chmod(0)
        try:
            for script in (self.uet, self.nas):
                for name, path in cases:
                    with self.subTest(script=script.key, body=name):
                        code, out, log = self.land(script, SQUASH_BODY_FILE=str(path))
                        self.assertEqual((code, log), (2, []), out)
                        self.assertIn(f"#{PR} SQUASH_BODY_FILE is set but is not a readable, non-empty file (path withheld): stop, nothing merged", out)
                        self.assertNotIn("/home/example", out)
        finally:
            unreadable.chmod(0o600)

    # ------------------------------------------------------------------------------------------ the squash body's publication scan (#1027)
    # Astra's P1 at d6be1b02: the scripts checked that SQUASH_BODY_FILE was a readable, non-empty regular file and nothing more, so a body
    # holding a home path, an account name, an address that is not a no-reply one or a token shape went into main's permanent history (her
    # four synthetic payloads each gave exit 0 and one merge call). The file is now copied to a private snapshot, which squash_body_scan.py
    # and `validate.py --scan-file` scan and which the merge is given. Every payload here is built from parts: this module is a published
    # file itself, and validate.py's scan reads it.
    SQUASH_NAMES = "LANDING_PROHIBITED_NAMES=zqxsynth,qvortex\n"  # a synthetic names file: two identities that no account has
    SQUASH_REFUSED = ("SQUASH_BODY_FILE holds text the publication scan refuses (details withheld; squash_body_scan.py names the classes and "
                      "lines): stop, nothing merged")
    SQUASH_UNSCANNABLE = ("SQUASH_BODY_FILE could not be scanned: a scanner or the names file is missing, unreadable or failed "
                          "(details withheld): stop, nothing merged")
    SQUASH_CLI_CLEAN = '{"matching_locations": 0, "scanned_files": 1, "source": "host", "status": "passed"}\n'
    # a body that passes: the no-reply addresses that squash bodies carry (GitHub's, and the vendor trailer), a synthetic name inside a
    # longer word, and the placeholder account's home path, which PRIVATE_CONTENT exempts
    SQUASH_CLEAN = ("The corrected claim, which review changed.\n\nThe zqxsynthesis step is unchanged, as is /" + "home" + "/example/work.\n\n"
                    "Signed-off-by: A Person <4242424+seathatflowsinourveins@users.noreply.github.com>\n"
                    "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>\n")

    def squash_body(self, content):
        """A new body file holding content, text or bytes."""
        path = self.dir / f"squash-{next(self.counter)}.md"
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        return path

    def squash_names(self, text=SQUASH_NAMES):
        path = self.dir / f"names-{next(self.counter)}.env"
        path.write_text(text, encoding="utf-8")
        return path

    def land_squash(self, script, body, *, tmp=None, names=None, **extra):
        """A landing with SQUASH_BODY_FILE set to the body file, the real squash_body_scan.py and scripts/validate.py (loaded for its
        PRIVATE_CONTENT table), a synthetic names file, and a canned clean answer from `validate.py --scan-file` (FAKE_SCAN_RC and
        FAKE_SCAN_OUT change it, FAKE_VALIDATE_SCAN_PYTHON makes it real). Returns (exit code, output, log, TMPDIR)."""
        if tmp is None:
            tmp = self.dir / f"tmp-{next(self.counter)}"
            tmp.mkdir()
        settings = {"SQUASH_BODY_FILE": str(body), "TMPDIR": str(tmp), "FAKE_BODY_SCAN_PYTHON": sys.executable,
                    "LANDING_SCANNER": str(ROOT / "scripts/validate.py"), "LANDING_NAMES_FILE": str(names if names is not None else self.squash_names()),
                    **extra}
        code, out, log = self.land(script, **settings)
        return code, out, log, tmp

    def assert_squash_stopped(self, message, code, out, log, tmp, secrets=(), tolerated=()):
        """The landing stopped with exit 2 and the fixed line, before any gh or git call (so before the lock), with no merge, no snapshot
        left, no path and nothing of the body printed. A failure message never holds a secret."""
        self.assertEqual(code, 2, out)
        self.assertIn(f"#{PR} {message}", out)
        calls = [line for line in log if line.startswith(("gh ", "git ")) and not line.startswith(tolerated)]
        self.assertEqual(calls, [], "the scans come before the lock and every gh and git call")
        self.assertEqual(self.merge_calls(log), [])
        self.assertEqual(sorted(tmp.glob("squash-body-*")), [], "the snapshot is removed when the script exits")
        self.assertNotIn(str(self.dir), out, "no path is printed")
        self.assertFalse([secret for secret in secrets if secret in out], "the output holds text of the body")

    def refused_forms(self, forms):
        """Each form, {label: (text, the part of it that must not be printed)}, is refused by both scripts with the fixed line."""
        for script in (self.uet, self.nas):
            for label, (text, secret) in forms.items():
                with self.subTest(script=script.key, form=label):
                    code, out, log, tmp = self.land_squash(script, self.squash_body(text))
                    self.assert_squash_stopped(self.SQUASH_REFUSED, code, out, log, tmp, secrets=(secret,))

    def test_a_squash_body_with_a_home_path_is_refused_by_both_scripts_before_any_call(self):
        # #1027: a home path in the body would be published in main's history. At d6be1b02 each of these landed (exit 0, one merge call).
        # PRIVATE_CONTENT knows the forward-slash forms; it does not match the UNC form of a WSL path (squash_body_scan.py does).
        user, bs = "zqx" + "other", "\\"  # not `example`, the placeholder account, which PRIVATE_CONTENT exempts
        self.refused_forms({label: (text, user) for label, text in {
            "a Linux home path": "see /" + "home" + f"/{user}/project\n",
            "a macOS home path": "see /" + "Users" + f"/{user}/project\n",
            "a Windows profile path": "opened C:" + bs + "Users" + bs + user + bs + "repo\n",
            "a Windows profile path with forward slashes": "opened C:/" + "Users" + f"/{user}/repo\n",
            "a Windows profile through the WSL mount": "cd /mnt/c/" + "Users" + f"/{user}/repo\n",
            "a WSL UNC path": "opened " + bs * 2 + "wsl.localhost" + bs + "Ubuntu" + bs + "home" + bs + user + bs + "repo\n",
            "a WSL UNC path of the older form": "opened " + bs * 2 + "wsl$" + bs + "Ubuntu" + bs + "home" + bs + user + "\n",
            "a WSL UNC path with doubled backslashes (JSON, Markdown)":
                "opened " + bs * 4 + "wsl.localhost" + bs * 2 + "Ubuntu" + bs * 2 + "home" + bs * 2 + user + "\n",
            "the dash-encoded home path": "dir -" + "home" + f"-{user}-code-repo\n",
            "the graph project id": "project=" + "-".join(("home", user, "code", "repo")) + " indexed\n",
            "a percent-encoded home path": "file=%2F" + "home" + f"%2F{user}%2Fproject\n",
        }.items()})

    def test_a_squash_body_with_a_name_of_the_names_file_is_refused_by_both_scripts_before_any_call(self):
        # #1027: the names file (the list the tests read as LANDING_PROHIBITED_NAMES) holds identities that must not reach main. At d6be1b02
        # each of these landed. A name is refused as a whole token, in any letter case, and percent-encoded.
        self.refused_forms({label: (text, secret) for label, (text, secret) in {
            "a bare word": ("the account zqxsynth ran it\n", "zqxsynth"),
            "the second name of the file": ("ask qvortex about it\n", "qvortex"),
            "upper case": ("ZQXSYNTH did\n", "ZQXSYNTH"),
            "an identifier": ("dir=project-zqxsynth-tools\n", "zqxsynth"),
            "a path": ("cd work/zqxsynth/src\n", "zqxsynth"),
            "percent-encoded": ("u=zqx%73ynth\n", "zqx%73ynth"),
        }.items()})

    def test_a_squash_body_with_an_address_that_is_not_a_no_reply_one_is_refused_by_both_scripts_before_any_call(self):
        # #1027 (the non-no-reply email of Astra's payloads, and the point of correction #148: no personal address in public history). At
        # d6be1b02 each of these landed. GitHub's no-reply forms and a noreply or no-reply local part pass (the control test below).
        self.refused_forms({label: (text, "example.invalid") for label, text in {
            "a plain address": "ask person@example.invalid\n",
            "mixed case": "ask Person.Name@Example.Invalid\n",
            "an address in a trailer": "Signed-off-by: A Person <person@example.invalid>\n",
            "percent-encoded": "ask person%40example.invalid\n",
            "a look-alike: noreply is not the whole local part": "ask noreply.person@example.invalid\n",
            "a look-alike: a no-reply local part after a quote": "ask x'noreply@example.invalid\n",
            "a look-alike: the plus form of another domain": "ask 4242424+noreply@example.invalid\n",
            "a look-alike: the GitHub no-reply domain as the start of another": "ask person@users.noreply.github.com.example.invalid\n",
        }.items()})

    def test_a_squash_body_with_a_token_shape_is_refused_by_both_scripts_before_any_call(self):
        # #1027: a credential in the body would be published. At d6be1b02 each of these landed. Built from parts, as the existing
        # PRIVATE_CONTENT tests do.
        self.refused_forms({label: (text, secret) for label, (text, secret) in {
            "a GitHub token": ("token " + "gh" + "p_" + "a" * 36 + "\n", "a" * 36),
            "a fine-grained GitHub token": ("token " + "github" + "_pat_" + "A" * 40 + "\n", "A" * 40),
            "an API secret": ("key " + "sk-" + "ant-" + "b" * 30 + "\n", "b" * 30),
            "a Hugging Face token": ("key " + "hf" + "_" + "c" * 24 + "\n", "c" * 24),
            "a bearer credential": ("Authorization: " + "Bearer " + "d" * 40 + "\n", "d" * 40),
            "a private key header": ("-----BEGIN " + "PRIVATE KEY-----\n", "PRIVATE KEY"),
            "a session identifier": ("session " + "-".join(("123e4567", "e89b", "12d3", "a456", "426614174000")) + "\n", "426614174000"),
        }.items()})

    def test_a_squash_body_that_names_this_host_lands_with_a_count_and_the_other_names_still_refuse(self):
        # #1027, the CC's ruling of 2026-10-12: a names-list entry equal to the running host's own name is a warning and never a refusal
        # (the host name is hygiene, not a blocker); the count is printed, the name is not. Every other identity still refuses. The name is
        # the live `hostname`, read here as the scan reads it; no message of this test can hold it.
        host = socket.gethostname()
        names = self.squash_names(f"LANDING_PROHIBITED_NAMES=zqxsynth,{host},qvortex\n")
        whole = re.compile(r"(?<![^\W_])" + re.escape(host) + r"(?![^\W_])", re.IGNORECASE)
        named = f"{self.SQUASH_CLEAN}\nThe host {host} ran it, and {host.upper()} again.\n"
        count = len(whole.findall(named))
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, body="names the host"):
                code, out, log, tmp = self.land_squash(script, self.squash_body(named), names=names)
                self.assertEqual((code, len(self.merge_calls(log))), (0, 1), "a body that names the host did not land")
                self.assertIn(f"#{PR} SQUASH_BODY_FILE names this host's own name {count} time(s): a warning, not a refusal (the name is not printed)", out)
                self.assertFalse(len(host) >= 6 and whole.search(out.replace("this host's own name", "")), "the output holds the host's name")
            with self.subTest(script=script.key, body="does not name it"):
                code, out, log, tmp = self.land_squash(script, self.squash_body(self.SQUASH_CLEAN), names=names)
                self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
                self.assertNotIn("own name", out)
            with self.subTest(script=script.key, body="names the host and another listed name"):
                code, out, log, tmp = self.land_squash(script, self.squash_body(named + "and zqxsynth, too\n"), names=names)
                self.assert_squash_stopped(self.SQUASH_REFUSED, code, out, log, tmp, secrets=("zqxsynth",))
                self.assertFalse(len(host) >= 6 and whole.search(out), "the output holds the host's name")
            with self.subTest(script=script.key, body="names the host, and the list does not"):
                code, out, log, tmp = self.land_squash(script, self.squash_body(named), names=self.squash_names())
                self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
                self.assertNotIn("own name", out)

    def test_a_squash_body_with_a_systemd_unit_instance_lands_and_a_look_alike_does_not(self):
        # #1027, the CC's ruling of 2026-10-12: <name>@<instance>.<type> with a type of service, timer, socket, path or mount is a unit
        # instance (systemd/systemd man/systemd.unit.xml:121-136), not an address; the ruling named target too, which round 2 dropped (a
        # top-level domain). At d6be1b02 the scripts read no body at all; the first scan of this change refused these. The look-alikes are
        # still addresses, and a provider address is the control.
        units = ("getty@tty1.service", "serial-getty@ttyS0.service", "user@1000.service", "app@one.socket", "app@dev-sda1.timer",
                 "watch" + "@some.path", "mnt" + "@data.mount")
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, body="unit instances"):
                text = self.SQUASH_CLEAN + "\nThe units " + ", ".join(units) + " were restarted.\n"
                code, out, log, tmp = self.land_squash(script, self.squash_body(text))
                self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
        self.refused_forms({label: (text, "tty1") for label, text in {
            "a provider address, the control": "ask " + "fictional.person" + "@gmail.com\n",
            "a service name that is a domain": "ask person@service.com\n",
            "a unit type that is not in the ruling": "ask person@host.device\n",
            "a local part that no unit name has": "ask jane+x@host.service\n",
            "a unit suffix inside a longer domain": "ask person@tty1.service.example.invalid\n",
            "a target instance, which round 2 no longer keeps": "ask fsck" + "@dev.target\n",
        }.items()})

    def test_a_squash_body_with_a_vendor_co_author_trailer_lands_and_a_provider_address_does_not(self):
        # #1027, the CC's ruling of 2026-10-12: a short cited list of vendor co-author trailer addresses that are not no-reply ones. Codex's is
        # codex@openai.com, as the vendor's own repository carries it (openai/codex@db22c91e61cc80defa5bbafc22bd8a8c7672e5e1, message line 38);
        # the vendor's current trailer, Codex <noreply@openai.com>, passes as a no-reply address. Only the exact address passes.
        trailers = ("Co-authored-by: Codex <codex@openai.com>\n", "Co-Authored-By: OpenAI Codex <Codex@OpenAI.com>\n",
                    "Co-authored-by: Codex <noreply@openai.com>\n")
        for script in (self.uet, self.nas):
            for trailer in trailers:
                with self.subTest(script=script.key, trailer=trailer.strip()):
                    code, out, log, tmp = self.land_squash(script, self.squash_body(self.SQUASH_CLEAN + trailer))
                    self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
        self.refused_forms({label: (text, "openai") for label, text in {
            "a provider address, the control": "Co-authored-by: Fictional Person <" + "fictional.person" + "@gmail.com>\n",
            "another local part at the vendor's domain": "Co-authored-by: Someone <someone@openai.com>\n",
            "the vendor's local part at another domain": "Co-authored-by: Codex <codex@openai.com.example.invalid>\n",
            "a longer local part": "Co-authored-by: Codex <xcodex@openai.com>\n",
        }.items()})

    # #1027 round 2 (the CC's adjudication at e203d014): both families landed an address through both real scanners, and each refusal below
    # landed at e203d014 (exit 0, one merge call) but the percent-encoded quoted form, whose raw text was refused. Astra's P1s: a quoted
    # local part ("x"@<provider>, RFC 5322 3.4.1) matched no address shape, and the vendor allowance stripped every leading non-word
    # character, so +codex@<vendor> was compared as the vendor's address. Claude's B1: <local>@<provider>.com followed by a unit type had a
    # unit instance's shape, for all six types, and .target is a top-level domain. Each case runs through both scripts with the canned
    # `validate.py --scan-file` answer and, where Betterleaks is at its pin, with the real scan as well: validate.py has no address rule, so
    # the refusal is squash_body_scan.py's. The oracle (rfc5322) reads every address first. Addresses other than no-reply ones are built
    # from parts when the test runs, as the module's payloads are, unit names included.
    ROUND_2_PERSON, ROUND_2_PROVIDER, ROUND_2_VENDOR = "zq" + "probe", "gm" + "ail.com", "codex" + "@" + "openai.com"

    def scan_modes(self):
        """How `validate.py --scan-file` answers: its canned clean line, and the real scan where Betterleaks is at host_name_scan.py's pin."""
        modes = [("the canned validate.py answer", {})]
        if betterleaks_pinned():
            modes.append(("the real validate.py --scan-file", {"FAKE_VALIDATE_SCAN_PYTHON": sys.executable, "HOME": os.environ["HOME"]}))
        return modes

    def refused_by_both_scans(self, forms):
        """Each form, {label: (text, the part of it that must not be printed)}, is refused by both scripts in each scan mode: exit 2, the
        fixed line, no gh or git call and no snapshot left."""
        for mode, real in self.scan_modes():
            for script in (self.uet, self.nas):
                for label, (text, secret) in forms.items():
                    with self.subTest(script=script.key, form=label, scan=mode):
                        code, out, log, tmp = self.land_squash(script, self.squash_body(self.SQUASH_CLEAN + text), **real)
                        self.assert_squash_stopped(self.SQUASH_REFUSED, code, out, log, tmp, secrets=(secret,))

    def test_a_quoted_local_part_is_refused_by_both_scripts_as_its_unquoted_form_is(self):
        # Astra's P1 1 at e203d014: `Contact "x"@<provider>` landed through both real scanners in both scripts. The oracle reads the quoted
        # form as the same address as the unquoted one, with no defect (RFC 5322 3.2.4: "quoted-string is identical to atom, semantically").
        person, provider = self.ROUND_2_PERSON, self.ROUND_2_PROVIDER
        quoted = {"a quoted local part": f'"{person}"@{provider}', "one with a space": f'"zq {person}"@{provider}',
                  "one with a quoted pair": '"zq\\"' + person + f'"@{provider}', "an empty one": f'""@{provider}'}
        self.assertEqual(rfc5322(quoted["a quoted local part"]), (person, provider, ()))
        self.assertEqual(rfc5322(quoted["a quoted local part"])[:2], rfc5322(f"{person}@{provider}")[:2])
        for label, spec in quoted.items():
            with self.subTest(oracle=label):
                self.assertEqual(rfc5322(spec)[1:], (provider, ()), "the oracle reads an address at the provider, with no defect")
        self.assertEqual(rfc5322(f'zq."{person}"@{provider}'), (f"zq.{person}", provider, ("ObsoleteHeaderDefect",)))
        self.refused_by_both_scans({
            **{label: (f"Contact {spec}\n", provider) for label, spec in quoted.items()},
            "in a trailer": (f'Signed-off-by: A Person <"{person}"@{provider}>\n', person),
            "in a code span": (f'see `"{person}"@{provider}`\n', person),
            "an obsolete local part, a quoted word after a dot": (f'ask zq."{person}"@{provider}\n', person),
            "percent-encoded": (f"ask %22{person}%22@{provider}\n", person),
        })

    def test_a_vendor_or_no_reply_local_part_behind_a_prefix_is_refused_by_both_scripts(self):
        # Astra's P1 2 at e203d014: the vendor's trailer with `+codex` for its local part landed through both real scanners in both scripts.
        # The allowances compare the whole address; markup is outside it only when it wraps it. The oracle keeps the prefix in the local part.
        vendor = self.ROUND_2_VENDOR
        self.assertEqual(rfc5322("+" + vendor), ("+codex", "openai.com", ()))
        self.assertEqual(rfc5322("!" + vendor), ("!codex", "openai.com", ()))
        self.assertEqual(rfc5322("`" + vendor), ("`codex", "openai.com", ()), "a backtick that does not close is part of the local part")
        self.assertEqual(rfc5322('"+codex"@openai.com'), ("+codex", "openai.com", ()))
        self.assertEqual(rfc5322("+noreply@" + "example.invalid"), ("+noreply", "example.invalid", ()))
        self.refused_by_both_scans({
            "a plus in front of the vendor's local part": (f"Co-authored-by: Codex <+{vendor}>\n", "+codex"),
            "a bang in front of it": (f"Co-authored-by: Codex <!{vendor}>\n", "!codex"),
            "in prose": (f"ask +{vendor} today\n", "+codex"),
            "inside a code span": (f"see `+{vendor}`\n", "+codex"),
            "a quoted vendor local part with a plus": ('Co-authored-by: Codex <"+codex"@openai.com>\n', "+codex"),
            "a backtick that does not close": (f"see `{vendor} today\n", "openai"),
            "a plus in front of noreply": ("ask +noreply@" + "example.invalid\n", "example.invalid"),
            "a bang in front of no-reply": ("ask !no-reply@" + "example.invalid\n", "example.invalid"),
        })

    def test_an_address_before_a_unit_type_and_an_address_at_target_are_refused_by_both_scripts(self):
        # Claude's B1 at e203d014: `Restarted <address>.<type> after the merge.` landed in both scripts for each of the six types (12 of 12
        # runs), and an address at <x>.target passed as a target instance. A unit is kept only when <name>@<instance> is no address, and
        # target is no longer a kept type. The oracle reads each as an address, and <name>@<instance> too.
        person, provider = self.ROUND_2_PERSON, self.ROUND_2_PROVIDER
        target = "person" + "@" + "corp" + ".target"
        self.assertEqual(rfc5322(f"{person}@{provider}"), (person, provider, ()))
        self.assertEqual(rfc5322(target), ("person", "corp.target", ()))
        forms = {f"an address before .{kind}": f"Restarted {person}@{provider}.{kind} after the merge.\n"
                 for kind in ("service", "timer", "socket", "target", "path", "mount")}
        for kind in ("service", "timer", "socket", "target", "path", "mount"):
            with self.subTest(oracle=kind):
                self.assertEqual(rfc5322(f"{person}@{provider}.{kind}"), (person, f"{provider}.{kind}", ()))
        self.refused_by_both_scans({
            **{label: (text, person) for label, text in forms.items()},
            "an address before a unit type, in a code span": (f"see `{person}@{provider}.service`\n", person),
            "an address with more after its domain, before a unit type": (f"Restarted {person}@{provider}-x.service\n", person),
            "a quoted local part before a unit type": (f'Restarted "{person}"@{provider}.service\n', person),
            "an address at .target": (f"ask {target}\n", "corp"),
            "a target instance": ("ask fsck" + "@dev.target\n", "fsck"),
        })

    def test_the_vendor_trailer_the_no_reply_forms_and_unit_instances_still_land_through_both_scripts(self):
        # #1027 round 2's controls: the exact vendor trailer, the no-reply forms, real unit instances and markup that wraps an allowed address
        # land, with exit 0 and one merge call, in each scan mode. A rule that refused every address would fail here.
        controls = {
            "the exact vendor trailer": f"Co-authored-by: Codex <{self.ROUND_2_VENDOR}>",
            "the vendor's no-reply trailer": "Co-authored-by: Codex <noreply@openai.com>",
            "GitHub's ID+USERNAME no-reply form": f"Signed-off-by: A Person <{NOREPLY}>",
            "GitHub's USERNAME no-reply form": "Signed-off-by: A Person <seathatflowsinourveins@users.noreply.github.com>",
            "a no-reply local part": "Reply to no-reply@example.invalid.",
            "unit instances": "Restarted getty" + "@tty1.service and user" + "@1000.service after the merge.",
            "the vendor address in a code span, a no-reply one in bold": f"see `{self.ROUND_2_VENDOR}` and **noreply@anthropic.com**",
        }
        for spec, expected in ((self.ROUND_2_VENDOR, ("codex", "openai.com", ())), ("getty" + "@tty1.service", ("getty", "tty1.service", ())),
                               ("user" + "@1000.service", ("user", "1000.service", ())), (NOREPLY, (NOREPLY.split("@")[0], "users.noreply.github.com", ()))):
            with self.subTest(oracle=spec):
                self.assertEqual(rfc5322(spec), expected)
                self.assertTrue(round_2_allows(*expected[:2]))
        for mode, real in self.scan_modes():
            for script in (self.uet, self.nas):
                for label, text in controls.items():
                    with self.subTest(script=script.key, control=label, scan=mode):
                        code, out, log, tmp = self.land_squash(script, self.squash_body(f"{self.SQUASH_CLEAN}{text}\n"), **real)
                        self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
                        self.assertEqual(sorted(tmp.glob("squash-body-*")), [], "the snapshot is removed when the script exits")

    def test_a_squash_body_is_not_landed_when_a_scanner_or_the_names_file_is_missing_or_fails(self):
        # #1027, fail closed: a missing or failing scanner, an answer that is not a scan's own clean line (a scanner that exits 0 and prints
        # nothing, as an emptied file would) and a names file that names nobody all stop the landing, the body being clean. At d6be1b02
        # each of these landed.
        def stub(text):  # a stand-in for squash_body_scan.py, named as the real one so that the fake python3 runs it
            directory = self.dir / f"stub-{next(self.counter)}"
            directory.mkdir()
            (directory / "squash_body_scan.py").write_text(text, encoding="utf-8")
            return str(directory / "squash_body_scan.py")
        missing, passed = self.dir / "does-not-exist", self.SQUASH_CLI_CLEAN
        cases = [
            ("validate.py is missing", {"LANDING_SCANNER": str(missing)}, self.SQUASH_UNSCANNABLE),
            ("squash_body_scan.py is missing", {"LANDING_BODY_SCAN": str(missing)}, self.SQUASH_UNSCANNABLE),
            ("the names file is missing", {"names": missing}, self.SQUASH_UNSCANNABLE),
            ("the names file names nobody", {"names": self.squash_names("LANDING_PROHIBITED_NAMES= , ,\n")}, self.SQUASH_UNSCANNABLE),
            ("the names file has no assignment", {"names": self.squash_names("# nothing\n")}, self.SQUASH_UNSCANNABLE),
            ("squash_body_scan.py exits 2", {"LANDING_BODY_SCAN": stub('print("squash body scan: could not run")\nraise SystemExit(2)\n')},
             self.SQUASH_UNSCANNABLE),
            ("squash_body_scan.py exits 0 and prints nothing", {"LANDING_BODY_SCAN": stub("")}, self.SQUASH_UNSCANNABLE),
            ("squash_body_scan.py exits 0 and prints another line", {"LANDING_BODY_SCAN": stub('print("all good")\n')}, self.SQUASH_UNSCANNABLE),
            ("squash_body_scan.py prints a warning count that is not a number",
             {"LANDING_BODY_SCAN": stub('print("squash body scan: clean (names_checked=3, warnings=x)")\n')}, self.SQUASH_UNSCANNABLE),
            ("squash_body_scan.py has a syntax error (exit 1, a traceback, no status line)", {"LANDING_BODY_SCAN": stub("def broken(:\n")},
             self.SQUASH_UNSCANNABLE),
            ("squash_body_scan.py refuses", {"LANDING_BODY_SCAN": stub('print("squash body scan: refused: x (line 1)")\nraise SystemExit(1)\n')},
             self.SQUASH_REFUSED),
            ("validate.py --scan-file exits 1", {"FAKE_SCAN_RC": "1", "FAKE_SCAN_OUT": passed.replace("0,", "1,").replace("passed", "failed") + "body:1\n"},
             self.SQUASH_REFUSED),
            ("validate.py --scan-file exits 2", {"FAKE_SCAN_RC": "2", "FAKE_SCAN_OUT": '{"scanned_files": 1, "source": "host", "status": "error"}\n'},
             self.SQUASH_UNSCANNABLE),
            ("validate.py --scan-file exits 0 and prints nothing", {"FAKE_SCAN_OUT": ""}, self.SQUASH_UNSCANNABLE),
            ("validate.py --scan-file exits 0 on the synthetic override's sources", {"FAKE_SCAN_OUT": passed.replace('"host"', '"synthetic"')},
             self.SQUASH_UNSCANNABLE),
            ("validate.py --scan-file exits 0 and reports a match", {"FAKE_SCAN_OUT": passed.replace("0,", "1,")}, self.SQUASH_UNSCANNABLE),
            ("validate.py --scan-file exits 0 and adds a line", {"FAKE_SCAN_OUT": passed + "body:1\n"}, self.SQUASH_UNSCANNABLE),
        ]
        if os.geteuid() != 0:  # root reads a file with mode 000
            unreadable = self.squash_names()
            unreadable.chmod(0)
            self.addCleanup(unreadable.chmod, 0o600)
            cases.append(("the names file is unreadable", {"names": unreadable}, self.SQUASH_UNSCANNABLE))
        for script in (self.uet, self.nas):
            for label, settings, message in cases:
                with self.subTest(script=script.key, case=label):
                    code, out, log, tmp = self.land_squash(script, self.squash_body(self.SQUASH_CLEAN), **settings)
                    self.assert_squash_stopped(message, code, out, log, tmp)
                    self.assertNotIn("Traceback", out)

    def test_a_squash_body_file_is_passed_to_the_merge_as_one_body_file_argument(self):
        # SQUASH_BODY_FILE (the CC, 2026-10-12): both repositories' squash default is COMMIT_MESSAGES, so a commit message that carries a
        # claim corrected after review would land; the merge takes its body from the file instead. At 86fa3844 the merge call had no
        # --body-file. An empty value is the same as none, and no path is printed.
        # #1027 (this test is the valid-body control, changed at d6be1b02, where the merge was given the caller's file itself): the merge is
        # given a private snapshot of a clean body, which both scanners read before any gh or git call. It is a new file that mktemp made in
        # TMPDIR (here a directory whose name has a space: still one --body-file argument), mode 0600, holding the body's bytes, and it is
        # removed when the script exits. The body tells a correct address rule from one that refuses every address: it carries GitHub's
        # no-reply form and the vendor's noreply trailer, a synthetic name inside a longer word and the placeholder account's home path.
        body = self.squash_body(self.SQUASH_CLEAN)
        spaced = self.dir / f"tmp {next(self.counter)}"
        spaced.mkdir()
        real_landing, validate = os.path.realpath(LANDING), ROOT / "scripts/validate.py"
        for script, repo in ((self.uet, UET_REPO), (self.nas, NAS_REPO)):
            merge = f"gh pr merge {PR} -R {repo} --squash --match-head-commit {self.head} -A {NOREPLY}"
            with self.subTest(script=script.key, body="a clean body, a snapshot in a directory whose name has a space"):
                names, argv, copy = self.squash_names(), self.dir / f"argv-{next(self.counter)}", self.dir / f"copy-{next(self.counter)}"
                code, out, log, _ = self.land_squash(script, body, tmp=spaced, names=names, FAKE_MERGE_ARGV=str(argv), FAKE_MERGE_BODY=str(copy))
                self.assertEqual(code, 0, out)
                arguments = [os.fsdecode(part) for part in argv.read_bytes().split(b"\0")[:-1]]
                self.assertEqual(arguments[:-1], ["pr", "merge", PR, "-R", repo, "--squash", "--match-head-commit", self.head, "-A", NOREPLY,
                                                  "--body-file"])
                snapshot = Path(arguments[-1])
                self.assertEqual(self.merge_calls(log), [f"{merge} --body-file {snapshot}"])
                self.assertEqual(snapshot.parent, spaced)
                self.assertRegex(snapshot.name, r"^squash-body-[A-Za-z0-9]{6}$")
                self.assertNotEqual(snapshot, body, "the merge is not given the caller's file")
                self.assertEqual(copy.read_bytes(), body.read_bytes(), "the bytes the merge reads are the body's, byte for byte")
                self.assertEqual(Path(f"{copy}.mode").read_text(encoding="utf-8").strip(), "600")
                self.assertFalse(snapshot.exists(), "the snapshot is removed when the script exits")
                self.assertEqual(sorted(spaced.glob("squash-body-*")), [])
                self.assertNotIn(str(body), out)
                self.assertNotIn(str(snapshot), out)
                scans = [(index, line) for index, line in enumerate(log) if line.startswith("python3 -E -s -B ")
                         and ("squash_body_scan.py" in line or "--scan-file" in line)]
                self.assertEqual([line for _, line in scans], [
                    f"python3 -E -s -B {real_landing}/squash_body_scan.py {snapshot} {validate} {names}",
                    f"python3 -E -s -B {validate} --scan-file {snapshot}"], "both scans, of the one snapshot")
                first_call = min(index for index, line in enumerate(log) if line.startswith(("gh ", "git ")))
                self.assertLess(max(index for index, _ in scans), first_call, "the scans come before the lock and every gh and git call")
            with self.subTest(script=script.key, body="an empty value"):
                code, out, log = self.land(script, SQUASH_BODY_FILE="")
                self.assertEqual((code, self.merge_calls(log)), (0, [merge]), out)
                self.assertEqual([line for line in log if "squash_body_scan.py" in line or "--scan-file" in line], [], "no scan, no snapshot")

    def test_the_merge_reads_the_scanned_bytes_even_when_the_file_changes_after_the_scan(self):
        # #1027: gh reads the body file when the merge call starts (cli v2.102.0 pkg/cmd/pr/merge/merge.go:146-153), minutes after the
        # scan (the CI wait takes up to 50). A file rewritten in between is not what was scanned; the snapshot is. At d6be1b02 the merge
        # was given the caller's file, and this rewrite, made as the merge call starts, reached main.
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                body = self.squash_body(self.SQUASH_CLEAN)
                clean, copy = body.read_bytes(), self.dir / f"copy-{next(self.counter)}"
                code, out, log, _ = self.land_squash(script, body, FAKE_MERGE_BODY=str(copy), FAKE_GH_HOOK_ON="pr merge*",
                                                     FAKE_GH_HOOK=f"printf '%s' 'rewritten after the scan' > {q(body)}")
                self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
                self.assertEqual(body.read_bytes(), b"rewritten after the scan", "the hook ran")
                self.assertEqual(copy.read_bytes(), clean, "the merge read the scanned bytes")

    def test_the_snapshot_exists_while_the_landing_runs_and_is_removed_wherever_it_stops(self):
        # #1027: the snapshot is removed on every exit (an EXIT trap), not only after the merge. A gh call lists TMPDIR while the landing
        # runs. At d6be1b02 there was no snapshot.
        cases = (("the head moved, exit 3", {"head": self.other}, 3, 0), ("the merge failed, exit 7", {"FAKE_MERGE_RC": "1"}, 7, 1))
        for script in (self.uet, self.nas):
            for label, settings, expected, merges in cases:
                with self.subTest(script=script.key, stop=label):
                    tmp, seen, argv = (self.dir / f"{name}-{next(self.counter)}" for name in ("tmp", "seen", "argv"))
                    tmp.mkdir()
                    code, out, log, _ = self.land_squash(script, self.squash_body(self.SQUASH_CLEAN), tmp=tmp, FAKE_GH_HOOK_ON="pr view*",
                                                         FAKE_GH_HOOK=f"ls -1 {q(tmp)} >> {q(seen)}", FAKE_MERGE_ARGV=str(argv), **settings)
                    self.assertEqual((code, len(self.merge_calls(log))), (expected, merges), out)
                    self.assertRegex(seen.read_text(encoding="utf-8"), r"(?m)^squash-body-[A-Za-z0-9]{6}$", "the snapshot existed during the run")
                    self.assertEqual(sorted(tmp.glob("squash-body-*")), [], "and is gone")
                    if merges:
                        self.assertFalse(Path(os.fsdecode(argv.read_bytes().split(b"\0")[:-1][-1])).exists(), "the file the merge was given")

    def test_the_snapshot_is_removed_when_a_signal_ends_the_landing(self):
        # #1027: bash runs an EXIT trap when SIGTERM or SIGHUP ends the shell, once the call it waits for returns (measured 2026-10-12, bash
        # 5.3.9). The wrapper execs the script, so the PID it records is the script's; a gh call signals it.
        for script in (self.uet, self.nas):
            for name in ("TERM", "HUP"):
                with self.subTest(script=script.key, signal=name):
                    pidfile, wrapper, seen = (self.dir / f"{kind}-{next(self.counter)}" for kind in ("pid", "wrapper", "seen"))
                    wrapper.write_text(f'#!/bin/sh\necho $$ > {q(pidfile)}\nexec {q(script.path)} "$@"\n', encoding="utf-8")
                    wrapper.chmod(0o755)
                    tmp = self.dir / f"tmp-{next(self.counter)}"
                    tmp.mkdir()
                    code, out, log, _ = self.land_squash(script, self.squash_body(self.SQUASH_CLEAN), tmp=tmp, via=wrapper, FAKE_GH_HOOK_ON="pr view*",
                                                         FAKE_GH_HOOK=f'ls -1 {q(tmp)} >> {q(seen)}; kill -{name} "$(cat {q(pidfile)})"')
                    self.assertRegex(seen.read_text(encoding="utf-8"), r"(?m)^squash-body-[A-Za-z0-9]{6}$", "the snapshot existed when the signal came")
                    self.assertEqual((code, self.merge_calls(log)), (-getattr(signal, f"SIG{name}"), []), out)  # bash runs the trap, then dies of the signal
                    self.assertEqual(sorted(tmp.glob("squash-body-*")), [], "the snapshot is gone")

    def test_the_scanner_and_the_names_default_to_the_clone_and_the_coordination_tree(self):
        # #1027: without LANDING_SCANNER the scan loads scripts/validate.py of the clone of this repository (LANDING_NAS_REPO, the CC's
        # checkout, which the live copies in the CC's tools directory share), and without LANDING_NAMES_FILE it reads
        # command-center/cc-tools/landing-prohibited-names.env under LANDING_COORD, the file the CC keeps there. Absent, the scan fails closed.
        scripts = self.repo / "scripts"
        scripts.mkdir(exist_ok=True)
        link = scripts / "validate.py"
        link.symlink_to(ROOT / "scripts/validate.py")
        self.addCleanup(scripts.rmdir)
        self.addCleanup(link.unlink)
        for script in (self.uet, self.nas):
            coord = self.dir / f"coord-{next(self.counter)}"
            listed = coord / "command-center/cc-tools/landing-prohibited-names.env"
            settings = {"LANDING_COORD": str(coord), "FAKE_BODY_SCAN_PYTHON": sys.executable}
            with self.subTest(script=script.key, names="absent"):
                code, out, log = self.land(script, SQUASH_BODY_FILE=str(self.squash_body(self.SQUASH_CLEAN)), **settings)
                self.assertEqual((code, self.merge_calls(log)), (2, []), out)
                self.assertIn(f"#{PR} {self.SQUASH_UNSCANNABLE}", out)
            listed.parent.mkdir(parents=True)
            listed.write_text(self.SQUASH_NAMES, encoding="utf-8")
            with self.subTest(script=script.key, names="present"):
                code, out, log = self.land(script, SQUASH_BODY_FILE=str(self.squash_body(self.SQUASH_CLEAN)), **settings)
                self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
                scan = next(line for line in log if "squash_body_scan.py" in line)
                self.assertTrue(scan.endswith(f" {link} {listed}"), "the clone's validate.py and the coordination tree's names file")
            with self.subTest(script=script.key, names="present, and the body holds one"):
                code, out, log = self.land(script, SQUASH_BODY_FILE=str(self.squash_body("the account zqxsynth ran it\n")), **settings)
                self.assertEqual((code, self.merge_calls(log)), (2, []), out)
                self.assertIn(f"#{PR} {self.SQUASH_REFUSED}", out)

    def test_the_repository_scanner_runs_on_the_snapshot_with_the_hosts_own_sources(self):
        # #1027: `validate.py --scan-file` is the scan the pre-push hook runs: PRIVATE_CONTENT and the runtime host-local names, here the
        # account that runs this test, which the synthetic names file does not list. It needs Betterleaks at host_name_scan.py's pin, which
        # CI does not install for this module, so the other tests answer it with a canned line. Run with -I it cannot import its sibling
        # and exits 2 (measured 2026-10-12), which is why the scripts run it with -E -s -B.
        if not betterleaks_pinned():
            self.skipTest("native Betterleaks at host_name_scan.py's pin is unavailable")
        account, real = account_name(), {"FAKE_VALIDATE_SCAN_PYTHON": sys.executable, "HOME": os.environ["HOME"]}  # the shim finds its install under HOME
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key, body="clean"):
                code, out, log, tmp = self.land_squash(script, self.squash_body(self.SQUASH_CLEAN), **real)
                self.assertEqual((code, len(self.merge_calls(log))), (0, 1), "the real scan refused or failed a clean body")
            with self.subTest(script=script.key, body="holds the running account's name"):
                code, out, log, tmp = self.land_squash(script, self.squash_body(f"the account {account} ran it\n"), **real)
                self.assertEqual(code, 2, "the real scan let a body with the running account's name through")
                self.assertIn(f"#{PR} {self.SQUASH_REFUSED}", out)
                self.assertEqual(self.merge_calls(log), [])
                self.assertFalse(account in out, "the output holds the account's name")
                self.assertEqual(sorted(tmp.glob("squash-body-*")), [])


class SquashBodyScanTests(unittest.TestCase):
    """squash_body_scan.py by itself (#1027): the names file's format, the address rule's controls, a name as a whole token and the output."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("squash_body_scan", LANDING / "squash_body_scan.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.table = cls.module.read_table(ROOT / "scripts/validate.py")
        scratch = tempfile.TemporaryDirectory(prefix="squash-scan-")
        cls.addClassCleanup(scratch.cleanup)
        cls.dir = Path(scratch.name)

    def refusal(self, text, names=("zqxsynth",), host=""):
        return self.module.scan(text, self.table, list(names), host)[0]

    def test_the_names_file_is_parsed_and_never_executed(self):
        marker = self.dir / "executed"
        for index, (label, content, expected) in enumerate((
                ("a plain assignment", "LANDING_PROHIBITED_NAMES=alpha,Beta,gamma\n", ["alpha", "Beta", "gamma"]),
                ("an export, quotes and spaces", "export LANDING_PROHIBITED_NAMES=' alpha , Beta ,,gamma '\n", ["alpha", "Beta", "gamma"]),
                ("double quotes and CRLF", 'LANDING_PROHIBITED_NAMES="alpha,Beta"\r\n', ["alpha", "Beta"]),
                ("the last assignment wins", "LANDING_PROHIBITED_NAMES=alpha\n# a comment\nLANDING_PROHIBITED_NAMES=Beta\n", ["Beta"]),
                ("lines that would run if the file were sourced",
                 f"LANDING_PROHIBITED_NAMES=alpha\ntouch {q(marker)}\n$(touch {q(marker)})\nLANDING_X=`touch {q(marker)}`\n", ["alpha"]))):
            with self.subTest(label):
                path = self.dir / f"names-parsed-{index}.env"
                path.write_text(content, encoding="utf-8")
                self.assertEqual(self.module.read_names(path), expected)
        self.assertFalse(marker.exists(), "no line of the names file ran")
        for index, (label, content) in enumerate((("no assignment", "# nothing\n"), ("an empty value", "LANDING_PROHIBITED_NAMES=\n"),
                                                  ("only commas and spaces", "LANDING_PROHIBITED_NAMES= , ,\n"), ("an empty file", ""))):
            with self.subTest(label):
                path = self.dir / f"names-refused-{index}.env"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.module.read_names(path)

    def test_the_address_rule_passes_no_reply_addresses_and_refuses_every_other(self):
        # the pairs are the control: a rule that refused every address would fail the first list, one that passed every address the second
        passing = ("Co-Authored-By: Claude <noreply@anthropic.com>", "Co-authored-by: GitHub <NoReply@GitHub.com>", "<no-reply@example.invalid>",
                   "4242424+seathatflowsinourveins@users.noreply.github.com", "seathatflowsinourveins@users.noreply.github.com.",
                   "ssh user@localhost", "an import of `@AGENTS.md`", "a mention @someone", "foo@bar",
                   "`noreply@anthropic.com`", "**no-reply@example.invalid**", "\"NoReply@GitHub.com\"", "`getty@tty1.service`",
                   "`codex@openai.com`", "'4242424+seathatflowsinourveins@users.noreply.github.com'")
        refused = ("person@example.invalid", "(person@example.invalid)", "mailto:person@example.invalid.", "<Person.Name+tag@Example.Invalid>",
                   "noreply.person@example.invalid", "x'noreply@example.invalid", "person@users.noreply.github.com.example.invalid",
                   "pérson@exämple.invalid", "`person@example.invalid`", "**person@example.invalid**", "'person@example.invalid'",
                   "`xnoreply@anthropic.com`", "`x'noreply@example.invalid`")
        # #1027 round 2 (Astra's P1s at e203d014): a quoted local part is the address its unquoted form is (RFC 5322 3.2.4), alone, with a
        # space, a quoted pair or nothing in it, or mixed with atoms; markup that wraps an address is no part of it, and any other character
        # in front of a no-reply local part is
        passing += ("\"noreply\"@anthropic.com", "<\"no-reply\"@example.invalid>", "`**noreply@anthropic.com**`", "see `@AGENTS.md`.")
        refused += ("\"person\"@example.invalid", "\"pers on\"@example.invalid", "\"per\\\"son\"@example.invalid", "\"\"@example.invalid",
                    "zq.\"person\"@example.invalid", "\"zq\".person@example.invalid", "x\"person\"@example.invalid", "\"no reply\"@example.invalid",
                    "+noreply@example.invalid", "!no-reply@example.invalid", "`noreply@example.invalid x", "`+noreply@example.invalid`",
                    "noreply.@example.invalid", "\"x\"noreply@example.invalid")
        for text in passing:
            with self.subTest(passing=text):
                self.assertIsNone(self.refusal(text))
        for text in refused:
            with self.subTest(refused=text):
                self.assertEqual(self.refusal(text), "email other than a no-reply address (line 1)")

    def test_systemd_unit_instances_are_not_addresses_and_their_look_alikes_are(self):
        # the CC's ruling of 2026-10-12: <name>@<instance>.<type>, the type one of six, with the characters a unit name has; since #1027
        # round 2 (Claude's B1 at e203d014) one of five, target dropped, and only when <name>@<instance> is no address
        passing = ("getty@tty1.service", "serial-getty@ttyS0.service", "user@1000.service", "app@one.socket", "app@dev-sda1.timer",
                   "watch" + "@some.path", "mnt" + "@data.mount", "a.b-c_d" + "@e.f-g.service", "GETTY" + "@TTY1.SERVICE", "(getty" + "@tty1.service)",
                   "`getty" + "@tty1.service`.", "app" + "@one.c.socket")  # a dotted instance whose last label is one letter is no domain
        refused = ("person@service.com", "person@host.device", "person@host.automount", "person@host.swap", "person@host.slice", "person@host.scope",
                   "jane+x@host.service", "jane'x@host.service", "pérson@tty1.service", "person@tty1.service.example.invalid",
                   "person@tty1.servic", "person@tty1.services")
        # Claude's B1 at e203d014: an address before each of the six types, quoted, wrapped or with more after its domain, and the target
        # instances, now refused (each built from parts, as the module's payloads are)
        refused += ("fsck" + "@dev.target", "person" + "@corp.target",
                    *(f"person@example.invalid.{kind}" for kind in ("service", "timer", "socket", "target", "path", "mount")),
                    "person" + "@example.invalid-x.service", "\"person\"@example.invalid.service", "`person" + "@example.invalid.mount`",
                    "a:b" + "@example.invalid.service", "\"a:b\"@example.invalid.service")
        for text in passing:
            with self.subTest(passing=text):
                self.assertIsNone(self.refusal(text))
        for text in refused:
            with self.subTest(refused=text):
                self.assertEqual(self.refusal(text), "email other than a no-reply address (line 1)")

    def test_a_vendor_trailer_address_passes_only_as_the_exact_address(self):
        # the CC's ruling of 2026-10-12; every entry names the vendor source it comes from, and the list is short
        table = self.module.VENDOR_TRAILER_ADDRESSES
        self.assertEqual(sorted(table), ["codex@openai.com"])
        self.assertTrue(all(source.startswith("openai/codex@") for source in table.values()))
        # #1027 round 2 (Astra's P1 2 at e203d014): the whole address is compared. Markup that wraps it is no part of it, and a quoted local
        # part is its unquoted form; a character in front that does not wrap it (+, !, a backtick that does not close) makes another
        # address, as do more characters after the domain, and so does a quoted word glued to an atom (the oracle reads it with a defect).
        vendor = "codex" + "@openai.com"
        round_2_passing = (f"**{vendor}**", f"'{vendor}'", f"`{vendor}`.", '"codex"' + "@openai.com")
        round_2_refused = (f"+{vendor}", f"!{vendor}", f"<+{vendor}>", f"`+{vendor}`", f"**!{vendor}**", '"+codex"' + "@openai.com", f"`{vendor} x",
                           f"{vendor}-x", f"{vendor}`s", f'"x"{vendor}', '"code"x' + "@openai.com", "codex." + "@openai.com")
        for text in ("Co-authored-by: Codex <codex@openai.com>", "co-authored-by: codex <CODEX@OPENAI.COM>", "Co-authored-by: Codex <noreply@openai.com>"):
            with self.subTest(passing=text):
                self.assertIsNone(self.refusal(text))
        for text in round_2_passing:
            with self.subTest(passing=text):
                self.assertIsNone(self.refusal(text))
        for text in ("someone@openai.com", "xcodex@openai.com", "codex@openai.com.example.invalid", "codex@mail.openai.com", "codex@openai.org",
                     "fictional.person" + "@gmail.com", "codex+1@openai.com"):
            with self.subTest(refused=text):
                self.assertEqual(self.refusal(text), "email other than a no-reply address (line 1)")
        for text in round_2_refused:
            with self.subTest(refused=text):
                self.assertEqual(self.refusal(text), "email other than a no-reply address (line 1)")

    def test_each_address_is_judged_as_the_rfc_5322_oracle_reads_it_and_markup_counts_only_when_it_wraps_it(self):
        # #1027 round 2 (the CC's adjudication at e203d014, rule 4: one RFC 5322 oracle for this email class): every local part here, quoted,
        # obsolete or with a prefix, at every domain, in prose, in a trailer's brackets and wrapped in markup. The oracle (rfc5322) reads the
        # address; the scan must pass it exactly when the allowances pass the whole address as the oracle reads it, with no defect
        # (round_2_allows). Markup that wraps the address is outside it; a mark in front that does not close is part of the local part, as
        # the oracle reads it. At e203d014 the quoted forms, the prefixed vendor and no-reply forms and the provider addresses before a unit
        # type passed, and so did each target instance.
        person, provider = "zq" + "probe", "gm" + "ail.com"
        local_parts = ("codex", "CODEX", "+codex", "!codex", '"codex"', '"+codex"', '"co\\dex"', "noreply", "+noreply", '"noreply"', '"no reply"',
                       "no-reply", "x.noreply", person, f'"{person}"', f'"zq {person}"', '"zq\\"q"', '""', f'zq."{person}"', f'"zq".{person}',
                       "getty", "user", "fsck", "a.b-c_d")
        domains = ("openai.com", "OpenAI.com", "anthropic.com", provider, "users.noreply.github.com", "tty1.service", "1000.service", "e.f-g.timer",
                   "dev.target", "corp.target", "host.device", *(f"{provider}.{kind}" for kind in ("service", "timer", "socket", "target", "path", "mount")))
        wrapped = ("see {} today", "Co-authored-by: Someone <{}>", "see `{}` today", "see **{}** today", "see '{}' today", "see `**{}**`.")
        unclosed = ("see `{} today", "see *{} today", "see '{} today")  # the mark is part of the local part, as the oracle reads it
        refused = "email other than a no-reply address (line 1)"
        for local in local_parts:
            for domain in domains:
                spec = f"{local}@{domain}"
                shown = spec.replace(provider, "<provider>").replace(person, "<person>")
                for form in wrapped + unclosed:
                    read = rfc5322(form[form.index("{") - 1] + spec if form in unclosed else spec)
                    with self.subTest(address=shown, form=form):
                        self.assertIsNotNone(read, "the oracle reads the address whole")
                        allowed = not read[2] and round_2_allows(read[0].lower(), read[1].lower())
                        self.assertEqual(self.refusal(form.format(spec)), None if allowed else refused)

    def test_a_name_equal_to_the_hosts_own_name_is_counted_and_never_refused(self):
        # the CC's ruling of 2026-10-12: compared when the scan runs, without regard to case; every other name still refuses
        names = ["zqxsynth", "zqxhost", "qvortex"]
        for label, text, host, expected in (
                ("the host twice, in two cases", "the host zqxhost ran it, ZQXHOST again", "ZqxHost", (None, 2)),
                ("the host percent-encoded", "the host zqx%68ost ran it", "zqxhost", (None, 1)),
                ("the host inside a longer word", "zqxhosting", "zqxhost", (None, 0)),
                ("the host and another name", "zqxhost and zqxsynth", "zqxhost", ("prohibited name (line 1)", 1)),
                ("another name only", "qvortex", "zqxhost", ("prohibited name (line 1)", 0)),
                ("no host name known", "zqxhost", "", ("prohibited name (line 1)", 0)),
                ("a host name that is not on the list", "zqxhost", "another-host", ("prohibited name (line 1)", 0))):
            with self.subTest(label):
                self.assertEqual(self.module.scan(text, self.table, names, host), expected)

    def test_a_name_is_refused_as_a_whole_token_in_any_case(self):
        for text in ("zqxsynth", "the ZqxSynth did", "project-zqxsynth-tools", "zqxsynth_id", "~zqxsynth/src", "u=zqx%73ynth"):
            with self.subTest(refused=text):
                self.assertIn("prohibited name", self.refusal(text) or "")
        for text in ("zqxsynthesis", "myzqxsynth", "zqxsynth2", "éqzqxsynth", "zqxsyn th"):
            with self.subTest(passing=text):
                self.assertIsNone(self.refusal(text))

    def test_the_output_is_a_class_and_a_line_never_the_text(self):
        names = self.dir / "names-output.env"
        names.write_text("LANDING_PROHIBITED_NAMES=zqxsynth,zqxhost\n", encoding="utf-8")
        validate = str(ROOT / "scripts/validate.py")
        body = self.dir / "body-output.md"
        for text, code, line in (
                ("clean\n", 0, "squash body scan: clean (names_checked=1)"),
                ("the host zqxhost ran it, ZQXHOST again\n", 0, "squash body scan: clean (names_checked=1, warnings=2)"),
                ("zqxhost and ask person@example.invalid\n", 1,
                 "squash body scan: refused: email other than a no-reply address (line 1) (warnings=1)"),
                ("clean\nsee /" + "home" + "/zqx" + "other/x\n", 1, "squash body scan: refused: personal home path (line 2)"),
                ("zqxsynth\nzqxsynth\nask person@example.invalid\n", 1,
                 "squash body scan: refused: email other than a no-reply address (line 3); prohibited name (line 1); prohibited name (line 2)"),
                ("file=%2F" + "home" + "%2Fzqx" + "other\n", 1, "squash body scan: refused: personal home path (percent-encoded)")):
            with self.subTest(text=text[:12]):
                body.write_text(text, encoding="utf-8")
                shown = io.StringIO()
                with contextlib.redirect_stdout(shown), mock.patch.object(self.module.socket, "gethostname", return_value="zqxhost"):
                    result = self.module.run(["squash_body_scan.py", str(body), validate, str(names)])
                self.assertEqual((result, shown.getvalue()), (code, line.replace("names_checked=1", "names_checked=2") + "\n"))
        for label, arguments in (("a missing body", [str(self.dir / "missing.md"), validate, str(names)]),
                                 ("a missing names file", [str(body), validate, str(self.dir / "missing.env")]),
                                 ("a missing validate.py", [str(body), str(self.dir / "missing.py"), str(names)]),
                                 ("a validate.py with no table", [str(body), str(names), str(names)]),
                                 ("too few arguments", [str(body)])):
            with self.subTest(label):
                shown = io.StringIO()
                with contextlib.redirect_stdout(shown):
                    result = self.module.run(["squash_body_scan.py", *arguments])
                self.assertEqual((result, shown.getvalue()), (2, "squash body scan: could not run\n"))


if __name__ == "__main__":
    unittest.main()
