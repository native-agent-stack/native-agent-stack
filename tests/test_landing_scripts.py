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
import stat
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

import tests

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "tools/landing"
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI", "").lower() == "true"
HEAD = "3d8c6344a0e2150d296d84bacff48bc394180e92"
OTHER = "9f8e7d6c5b4a39281706f5e4d3c2b1a098765432"
NOREPLY = "4242424+seathatflowsinourveins@users.noreply.github.com"  # the fake gh serves id 4242424 for the repository owner
PR = str(90000000 + os.getpid())  # per process: the nas script makes /var/tmp/nas-land-<pr>-XXXXXX worktrees, which parallel runs must not share
UET_REPO = "seathatflowsinourveins/us-equities-trading"
NAS_REPO = "native-agent-stack/native-agent-stack"  # 2026-10-13: the repository moved to the organization; nas_land.sh's default R
MERGING_ACCOUNT = "seathatflowsinourveins"  # CC correction #198: LG_AUTHOR_LOGIN's default, whose no-reply address authors both scripts' merges
USER_JQ = '--jq select(.type == "User") | .id'  # #1061 P3: the author lookup as the fake gh logs it (an organization gives no id)
# #975 P2-3: GitHub's CheckConclusionState as captured from its published GraphQL schema, with the REST description's check-run enum
CONCLUSIONS = ROOT / "tests/fixtures/landing/check-conclusion-state.json"
PASSING_CONCLUSIONS = ("SUCCESS", "NEUTRAL", "SKIPPED")  # the scripts' allow-list; any other completed conclusion, null included, fails
# #975 P3: GitHub's StatusState (uet reads commit statuses), captured the same way; only SUCCESS passes, PENDING and EXPECTED are running
STATUSES = ROOT / "tests/fixtures/landing/status-state.json"
RUNNING_STATES = ("PENDING", "EXPECTED")
UNLISTED_STATE = "FUTURE_STATE"  # synthetic: a state GitHub may add to StatusState later; the script must fail closed on it
ADDRESS = "api-text-4e9b@example.invalid"  # synthetic: stands for an address that a status description or a gh or API diagnostic could carry


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
# answers the review-thread count and, #1061 round 2, the squash body GitHub offers (viewerMergeBodyText: FAKE_SQUASH_BODY, default
# "* the change"); any other query fails, as for a gate that runs against this fake. A newline in an argument (a waived landing's merge
# body) is logged as \n, so each call stays one line of the log.
FAKE_GH = r'''#!/usr/bin/env bash
[ -n "${FAKE_LOG:-}" ] && printf 'gh %s\n' "${*//$'\n'/\\n}" >> "$FAKE_LOG"
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
  "api users/"*) [ "${FAKE_USER_RC:-0}" = 0 ] || exit "$FAKE_USER_RC"  # #1061: the users API answers for organizations too (type)
                 printf '{"id": %s, "type": "%s"}\n' "${FAKE_USER_ID-4242424}" "${FAKE_USER_TYPE-User}" | jq -r "$prog"; exit 0 ;;
  "api graphql")
    if [[ "$*" == *viewerMergeBodyText* ]]; then
      jq -n --arg b "${FAKE_SQUASH_BODY-* the change}" '{data: {repository: {pullRequest: {viewerMergeBodyText: $b}}}}' | jq -r "$prog"; exit 0
    fi
    [[ "$*" == *reviewThreads* ]] || exit 1; echo "${FAKE_OPEN_THREADS:-0}"; exit 0 ;;
  "pr view")
    if [ -n "${FAKE_HEADS:-}" ] && [[ "$*" == *headRefOid* ]]; then
      heads=($FAKE_HEADS); n=$(cat "$FAKE_LOG.heads" 2>/dev/null || echo 0); echo $((n + 1)) > "$FAKE_LOG.heads"
      jq --arg h "${heads[$(( n < ${#heads[@]} ? n : ${#heads[@]} - 1 ))]}" '.headRefOid = $h' "$FAKE_PRVIEW" | jq -r "$prog"
      exit "${PIPESTATUS[1]}"
    fi
    exec jq -r "$prog" "$FAKE_PRVIEW" ;;
  "pr ready") exit 0 ;;
  "pr update-branch") exit "${FAKE_UPDATE_RC:-0}" ;;
  "pr merge") printf '%s\n' "${FAKE_MERGE_STDOUT-merged}"; [ -z "${FAKE_MERGE_STDERR:-}" ] || printf '%s\n' "$FAKE_MERGE_STDERR" >&2
              exit "${FAKE_MERGE_RC:-0}" ;;
  *) exit 1 ;;
esac
'''
# codex_gate.py and scripts/validate.py both run as `python3 ...` in the scripts; the log shows which path each call got.
# FAKE_REAL_PYTHON, when set, runs the real codex_gate.py with that interpreter instead of the canned answer (its gh is the fake gh).
# #975 round 3: FAKE_GATE_HOOK runs before each gate call's answer and FAKE_VALIDATE_HOOK before each validation's, so a test can change
# GitHub-side data (a status, a record, origin's main) while a landing waits; FAKE_VALIDATE_OUT is the validation's output.
# #1075: the lander's own helper (nas_land.sh's SB_READER, `python3 -I -c <one line> <file> <ceiling>`) runs on the real interpreter,
# FAKE_PYTHON_BIN (LandingCase.env sets it), as the lander would run it.
FAKE_PYTHON3 = r'''#!/usr/bin/env bash
printf 'python3 %s\n' "$*" >> "$FAKE_LOG"
case "$*" in
  "-I -c "*) exec "$FAKE_PYTHON_BIN" "$@" ;;
  *scripts/validate.py*) printf 'validate-tree %s\n' "$(git ls-files | tr '\n' ' ')" >> "$FAKE_LOG"
                         [ -z "${FAKE_VALIDATE_HOOK:-}" ] || sh -c "$FAKE_VALIDATE_HOOK"
                         echo "${FAKE_VALIDATE_OUT:-validate stub}"; exit "${FAKE_VALIDATE_RC:-0}" ;;
  *codex_gate.py*) [ -z "${FAKE_GATE_HOOK:-}" ] || sh -c "$FAKE_GATE_HOOK"
                   [ -z "${FAKE_REAL_PYTHON:-}" ] || exec "$FAKE_REAL_PYTHON" "$@" ;;
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
               "FAKE_PYTHON_BIN": sys.executable, **tests.HERMETIC_GIT_ENVIRONMENT}
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
    # #1061 round 2: nas's verdict_gate also reads the local review waiver when neither local review variable is set; these sites test
    # the verdict files alone, so they set LOCAL_REVIEWS (empty), and the waiver has its own end-to-end tests.
    def verdict_files(self, script, path, head, gates_done=None):
        gates = f"GATES_DONE={q(gates_done)}" if gates_done else "unset GATES_DONE"
        prelude = f"R=x/y; N=1; E={head}; EF={head}\n{gates}\n{script.block}\n"
        prelude += f"VERDICT_FILES={q(path)}\n" if script.key == "uet" else f"VF=({q(path)}); LOCAL_REVIEWS=\n"
        return self.bash(prelude, f"{script.verdict_gate}\nverdict_gate")

    def receipt_loop(self, path, read, head, gates_done):
        """nas's verdict gate when the caller gave the read head as `read` (a prefix) and it resolved to `head`."""
        prelude = f"R=x/y; N=1; E={read}; EF={head}\nGATES_DONE={q(gates_done)}\n{self.nas.block}\nVF=({q(path)}); LOCAL_REVIEWS=\n"
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


# #1061 P1-3 (Astra at c999eee5; correction #161's custody rule): a published digest binds published bytes. Each digest the README cites is
# a tracked file's (a file under tools/landing or tests/fixtures/landing that git tracks, the files the README documents, hashed here as
# they are now, so the guard needs no registry and no earlier check), the captured summary comment's body, or one of these named public
# artifacts; a digest of a host-only file, such as the CC's live copies, is an offline oracle for a guessed path and may not be published,
# in full or as a prefix. #1061 round 2 (the CC's Claude delta at 974090cf): an untracked file there is host-only, so it is not known.
PUBLIC_DIGESTS = {
    "4ce5cdb31c15dad95e0a7e18e6d0f0c49a07603cea0d5f4e08bc51f530a5d7e1": "cli/cli@v2.102.0:internal/ghcmd/cmd.go",
    "030eda84dcfdb52e3bba2cadfc0243a7b47d3098b64f8c12c665550733d72ca1": "cli/cli@v2.102.0:pkg/cmd/api/api.go",
    "04d1e28080aaa4f19f9113dfc3da97541158483a220efda9a52275fed54e3b98": "uutils/coreutils@0.10.0:src/uu/mktemp/src/mktemp.rs",
    "0833b527913f974ace9dff19e4dd8640e73da2cab6967c8dfca5e7dc9889abc9": "uutils/coreutils@0.10.0:Cargo.lock",
    "d182721b62c126916b73bb4865ced5d3637bd1a4a77d27ea9e9708973e5f9493": "Stebalien/tempfile@v3.27.0:src/lib.rs",
    "b6752b11a575021eeab87cb8b5b6914aaff86ad8d49a9678a8f4c95b5a21ef81": "Stebalien/tempfile@v3.27.0:src/file/mod.rs",
    "cc39f94cb6cb87b36cf7603a75429d64ecc4ad1a2076a765e5aba2b11771d0f7": "Stebalien/tempfile@v3.27.0:src/file/imp/unix.rs",
    "0f4b8b370a7f0d2e8ff93f2e224b2c7e54f64bfb808e5f50242f83b725e950a8": "python/cpython@v3.13.16:Doc/library/pwd.rst",
    "11841fe008240d3ffb955d0c700da1d96c07f18679ab09b93b16c3c81707a261": "python/cpython@v3.13.16:Modules/pwdmodule.c",
    "e52ea266b79f3b4a83388093f387540ff36d51ff306dcbb6ca6de081cd28e718": "python/cpython@v3.13.16:Lib/getpass.py",
    "0530b4186ec5845e000bedf5817ff1ac970b9a39a6891ba6789a1776abdea42b": "python/cpython@v3.13.16:Lib/pathlib/_local.py",
    "75e6bc728013d11446126d535f92b8907fb6dae7404df3d0268ac7b6865a2090": "python/cpython@v3.13.16:Lib/pathlib/_abc.py",
    "491b233e8d87a2ab73964afff029717177d53ad8def328ed9b00575db983da27": "python/cpython@v3.13.16:Lib/urllib/parse.py",
    "a80fc2454f7a0ad644f02259184de5b52084392ddb8b41c1ce372e50a09f3993": "python/cpython@v3.13.16:Lib/base64.py",
    "fd5e3799c5a70a7560460badf84a1a3e14c5b8b40a40352840477e267019cf20": "python/cpython@v3.13.16:Objects/bytesobject.c",
    "455ed7abc1d74b6af12c9205e76af0873bbb9d4297f73c8a2d6306a7ec658042": "python/cpython@v3.13.16:Doc/library/re.rst",
    "ca3849b4d224ac0384bcc90102f77bd0612e2c0ba67fc1ee44bb48abe87c5942": "cli/cli@v2.102.0:pkg/cmd/pr/merge/merge.go",
    "b21ef4350f050611af8a268632579c019c2dcb33feea7c0abffd4ca2b2520f0b": "https://cli.github.com/manual/gh_pr_merge (fetched 2026-10-11)",
    "9739be01b44da924ebec94ee658d5c080627ee65a2cd7d711fd83d6a081ba4da": "git/git@v2.53.0:Documentation/git-ls-remote.adoc",
    "da3d22e417611cca9a4131dceea89d4d61c3be021b0917f32d9e4422e4fe60f1": "github/rest-api-description@58b1e0c00b39:descriptions/api.github.com/api.github.com.json",
    "3835ec561d9f4052783c79541d86d16e644f7d8d0b8fb1bd1d3067ad021c38a7": "git/git@v2.53.0:Documentation/revisions.adoc",
    "9507f8a42e30531ed11721339f32a2e2b5d02e721e4c166414fa574269fd19e7": "python/cpython@v3.13.16:Modules/main.c",
    "91825c95030c506eb3840249a9f7bc12a0ff7eeb2f66b980608d5bc5d1cdb568": "python/cpython@v3.13.16:Doc/library/sys.rst",
    "d878ba9b46081d1e902cafeddc35d368ad3d9eaf5cb5c5c99ab4ea692c7054f6": "git/git@v2.53.0:usage.c",
    "38a4ba0d8cbd440e1cdde96c0c6384d8ee60bf844b7c934ab1516d9206669922": "github/docs@be38ec5d:content/actions/reference/workflows-and-actions/variables.md",
    "13befe29fb26539e05251a6352d08984f54ea82c02ba5166173909038cfb6e97": "util-linux/util-linux@v2.41.3:sys-utils/flock.1.adoc",
    "f303ab0c5c14299e3d0891f5b9731317e87081546c1b0b2e2e1bf6d7613c224b": "util-linux/util-linux@v2.41.3:sys-utils/flock.c",
    "f7dda45536864b701aa5eca8e32462e319cf068181f642b4e4a053d9556847bf": "git/git@v2.53.0:builtin/fetch.c",
    "bc3403bcc124da68d945ab2f4306c5ca673ba317bd3852b4bbf7789966f35cb2": "git/git@v2.53.0:run-command.c",
    "9b33422c7d0c5948a470db5a340992816aedf04dabaf0da6d57e3b004471d775": "git/git@v2.53.0:builtin/gc.c",
    "06c1942188bc86d1a1691eb97a66d0ee278c1057661a62112bf1ecbc0776b3ec": "git/git@v2.53.0:setup.c",
    "809b79c7ff781871874e92c186908cac332fc4b0fa0dff2fb9624856e2a9fa79": "git/git@v2.53.0:Documentation/config/maintenance.adoc",
    "e0eb9a084b0a8ed4f07a11dbfb0d6c31006235815481cfcd8876d48ff42b5f75": "jqlang/jq@jq-1.8.1:docs/content/manual/v1.8/manual.yml",
    "9b510dff29fede9f5e9d6a61d59b5d0d69419fc74a2bf684331295d0200829e8": "jqlang/jq@jq-1.8.1:src/jv_aux.c",
    "e835ca2a7a11b54e3db93221466928c887ef9529a9b34b475d746888e43af410": "git/git@v2.53.0:Documentation/git-patch-id.adoc",
    "0565f3040ed1843875732e5df5dbc50fdbc90bb3b45685eabfd83c133b4c79b0": "cli/cli@v2.102.0:pkg/cmd/api/pagination.go",
    "115bc54638dc4fa5a72da79d9f87fca699ee5b1fc7e21ea9314a517fb18fb40b": "cli/cli@v2.102.0:go.mod",
    "418bdf281d74a89c7dabedc4af53a6f7b286f2416e7670d9cc71453db08d8640": "github/docs@be38ec5d:content/rest/using-the-rest-api/using-pagination-in-the-rest-api.md",
    "57f0a021883f869390a022e41bdbe77267d5ebbdbf59849d2891380f5e363247": "github/docs@be38ec5d:src/rest/data/fpt-2022-11-28/commits.json",
    "3ed095654b22b1a8e7a88af36af2b28cb6d9613da332e9c57303e30476958d42": "https://docs.github.com/public/fpt/schema.docs.graphql (fetched 2026-10-11 and 2026-10-13)",
    "ed316b3fff6ecc09247826cb872df41beeab9088eeeaccbdb73703fedbfcf8ae": "github/docs@be38ec5d:content/repositories/creating-and-managing-repositories/transferring-a-repository.md",
    "fbbf1c5f700d977f8672462859621f9412e65531a57790fa779e191a4d1c0949": "github/docs@be38ec5d:content/account-and-profile/reference/email-addresses-reference.md",
    "591df6bd88afa6f28a4f0d030331821dfbef256187da3834cece6d13b4468ef4": "github/docs@be38ec5d: the IAM configuration reference's username-considerations-for-external-authentication.md",
    "499bd1fd429418778d26998c48da2a5a22fe2965f4684e69fdf99e6b4c7e4330": "openai/codex@rust-v0.162.1:codex-rs/protocol/src/protocol.rs",
    "5ca7f804a77dc8f132bb1eda4045e693d2d9b595cf70fc0877ca0cc98c5b621c": "openai/codex@rust-v0.162.1:codex-rs/protocol/src/items.rs",
    "4961b4deff8f665501b3bd5ad9fd386c9651999df8a7cf757bf8567b380eab52": "openai/codex@rust-v0.162.1:codex-rs/core/src/tasks/review.rs",
    "ac6c17fda98ecc6377132ac9a34fb4771e902632b943decc94261961891a3598": "openai/codex@rust-v0.162.1:codex-rs/history/src/rollout_payload.rs",
    "ec60e7f36a1d1c2679ce095c0205ecc56f7dd8fb57707a13ef362072390f219f": "openai/codex@rust-v0.162.1:codex-rs/prompts/templates/review/rubric.md",
    "f4896d6746c3508aa08b72ce15ce143f9041015da9da37b044cdaf4f6f838fc0": "openai/codex@rust-v0.162.1:codex-rs/prompts/src/review_request.rs",
    "86774c34df2bcb4b55ff5340bc2ef644bf64a94d14b122dbb29004ef01b370c5": "openai/codex@rust-v0.162.1:codex-rs/git-utils/src/branch.rs",
    "51b62cef4893c6d07b51753fc2716fc05985cdc9de6673f2fa2d974779454d4b": "openai/codex@rust-v0.162.1:codex-rs/exec/src/lib.rs",
    "65ce50e843547719295fd884b651552c1227085e8d0acfef2161b4ec3111dcbc": "openai/codex@rust-v0.162.1:codex-rs/rollout/src/policy.rs",
    "7d5a0bc9a41babad32a387152f9680316997bc4ad376928827d670b1760cc890": "anthropics/claude-plugins-official@f359d43b:plugins/code-review/commands/code-review.md",
    "1fca74bab6969b609519927ae49112760e15d8113eef6bbcf9b9a96c49d73c89": "anthropics/claude-plugins-official@f359d43b:plugins/code-review/README.md",
    "72459eb4e2e6d3b1a143f3c40860b7dd65fb061cdec3b18470ed8867382d8552": "https://developers.openai.com/codex/llms.txt (fetched 2026-10-13)",
    "c18b2fe184104facf5d044631ee151b2394baab1c44218be8b9d60c7dbd33020": "https://learn.chatgpt.com/docs/code-review.md (fetched 2026-10-13)",
    "1ab502138a121ac571faa37f161bf79224e1e23cdc0e70f7a0be835f2c2d3c9f": "https://learn.chatgpt.com/docs/third-party/github.md (fetched 2026-10-13)",
    # #1061 round 2: the waiver's squash body, the repository name, and the mechanisms of Astra's follow-up 4 (the local upstream mirrors)
    "17eb5418a1771692864b8f7476947f088252ccde0037d089c9faf441ff7c8877": "cli/cli@v2.102.0:pkg/cmd/pr/merge/http.go",
    "5a1343a0acb89ef1811e5fa93202ac452a0cbeef97656ead236f87910bb2a08d": "github/docs@be38ec5d:data/reusables/repositories/repo-name.md",
    "1d54f83bb3f583e37bae07d820d16206cf02f4fb2ef281338635b4b7fd01ebe4": "python/cpython@v3.13.16:Doc/library/os.rst",
    "1dabdd646bfbf961c3ffcf79dd41bd81dc6a2e1ed59428b32662ed16acff08df": "python/cpython@v3.13.16:Doc/library/json.rst",
    "5a46b6cc199fd025f914f39a39199745bad9fbbf540246abcb658671899be77e": "python/cpython@v3.13.16:Doc/library/math.rst",
    "18560b0a37dfb90b4712fba97668d44a1328c5566b10deffaee292ba12cc21ff": "python/cpython@v3.13.16:Lib/os.py",
    "87601195497fde3b7cea03bce396e1b713c17af3d273298d99d3bc0147f745b9": "python/cpython@v3.13.16:Lib/_collections_abc.py",
    # 2026-10-13, SQUASH_BODY_FILE: what gh does with --body-file "-" (the local upstream mirror at v2.102.0)
    "94076f6234180f85f2a555a5733e024146ea2c0cac54af19c86c72b015252828": "cli/cli@v2.102.0:pkg/cmdutil/file_input.go",
    # #1075 at ca6f880b (the Claude read's P2-1, Astra's P2-1): the sha256 forms the binding compares, and the body's bound; each fetched
    # with curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/<tag>/<path> on 2026-10-13
    "244f9bebae318b08bc062d20c00b945a7f11fac55599a2b32a0d25944bcc3c6f": "python/cpython@v3.13.16:Python/codecs.c",
    "3805805cbb3153bf89e785c6e861b51a09a5a4c3d8747e4e3086c6c9befbf648": "python/cpython@v3.13.16:Modules/_hashopenssl.c",
    "bf23b9b1e5dc9ff5b0b86a7c88637d73e2c8496681dca125aa3df1da631ee106": "python/cpython@v3.13.16:Doc/library/hashlib.rst",
    "7842f6d7d9b58bcbf10cbb24d29f6d1f36668e20f935689e197bbe0abdccd4ed": "python/cpython@v3.13.16:Python/pystrhex.c",
    "48254a0adf102ceaa5ab91c1146fb3a7d21f79de3396b89be6f9480025ae6d6e": "uutils/coreutils@0.10.0:src/uu/sha256sum/src/sha256sum.rs",
    "ad05144f9d1663e79fa2f579a3fdbbef4820373ab6bcb4028d897e891d3e37d3": "uutils/coreutils@0.10.0:src/uu/checksum_common/src/lib.rs",
    "077a6b11783d23f507ccc5f94d39916ce8d1caf5993e75e87218ac7576c7b932": "uutils/coreutils@0.10.0:src/uucore/src/lib/features/checksum/compute.rs",
    "362f62dd0ceb60b5b2c107ae078d276c33b727354fd2d8576aab2ef1780c27f7": "uutils/coreutils@0.10.0:src/uucore/src/lib/features/checksum/mod.rs",
    "f03de154b8899af73adbc7fa866a77113aef1e500df24b77f59802e4c1ebea8b": "uutils/coreutils@0.10.0:src/uucore/src/lib/features/sum.rs",
    "bc16c851822629225d2d2653ea080f131b0f2c4704d3ff27fed955c9b8b42f71": "KokaKiwi/rust-hex@v0.4.3:src/lib.rs (also crates.io hex-0.4.3.crate's src/lib.rs)",
    "7f24254aa9a54b5c858eaee2f5bccdb46aaf0e486a595ed5fd8f86ba55232a70": "https://static.crates.io/crates/hex/hex-0.4.3.crate (fetched 2026-10-13; uutils 0.10.0 Cargo.lock's checksum)",
    "6f435af082f135d9171035ffe88fe826a81c0c7880f2ec3b4e048644fe7c704d": "torvalds/linux@v6.18:include/uapi/linux/binfmts.h",
}


# #1061 round 2 (the CC's Claude delta at 974090cf, P3): a hex word is a digest, a digest's prefix or a commit id, so a bare prefix is
# checked too, and a commit id must be one of these named public commits (each read on GitHub on 2026-10-13 with
# `gh api repos/<repository>/commits/<id>`; a commit that only a host holds would be an unpublished hash as well).
PUBLIC_COMMITS = {
    "af9d190113e1046f2ce51d008fc161f6265cc73b": "native-agent-stack/native-agent-stack: #975 round 3's head",
    "754a194f0c37483b017bf31ba2fa9ed417a58634": "native-agent-stack/native-agent-stack: #975, the head of the GPT micro",
    "761810d703bae174331d03ffc922316dd92d1712": "native-agent-stack/native-agent-stack: #975 round 4's head",
    "5b8ba3b20ef446c1ed36ebc103f6256afcacb8e0": "native-agent-stack/native-agent-stack: #975 round 4's fix",
    "3e6e7e46663c3b9af06dd018c96e916dbb32873d": "native-agent-stack/native-agent-stack: #975's final round",
    "26f551b1b1b62eb1843604c8af3fefab5822bb40": "native-agent-stack/native-agent-stack: the head of the 43-run check-run measurement",
    "8eb4b532780661dfbe9c654a275c437445a977af": "native-agent-stack/native-agent-stack: the head of the first local baseBranch review",
    "c63c83a822f2687c3e7aed2d3b3ede0413119c9b": "native-agent-stack/native-agent-stack: #1061's base",
    "a6c8bf7cfd90f3dd76d6314355e434fa6afb9ae3": "native-agent-stack/native-agent-stack: #1061's first commit",
    "c999eee50e7ef1a4be45cee3f90e417e72868148": "native-agent-stack/native-agent-stack: #1061's second commit",
    "974090cfdccc284741a26147d306ef4a0e1debdd": "native-agent-stack/native-agent-stack: #1061's third commit",
    "993cc890b3ff3fc95fa7cdba51edd726565f9ace": "native-agent-stack/native-agent-stack: the base of the adjudication change (#1068's merge)",
    "25a9b48efc6be09b9447a8265b8379191ec2b81d": "native-agent-stack/native-agent-stack: #1075's first commit",
    "ca6f880b57f3011d799260161c6b4580ecf7b4d8": "native-agent-stack/native-agent-stack: #1075's second commit",
    "f3f1cabe8235d082c39d817db452378598dc55de": "native-agent-stack/native-agent-stack: #1075's third commit",
    "cbc944f4bc59639a444dd971c737788ba2283a91": "python/cpython: v3.13.16, the upstream mirror",
    "b2b4370b5bf021b98ee7adc92233e8de3f2de792": "KokaKiwi/rust-hex: v0.4.3",
    "58b1e0c00b39b9e46c24dc4a0ba6a2669c90e9c1": "github/rest-api-description",
    "be38ec5d78e24172587e61b3c6ff40ace1865c71": "github/docs",
    "092d3acd6bec3e3a14bdc7e7a2810ab628ab759d": "openai/codex: the upstream mirror of 2026-10-09",
    "67ad42147a7acc2af6074753ebd03d904476118f": "git/git: the upstream mirror",
    "fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd": "cli/cli: the upstream mirror",
    "f359d43b406057f1a8cdbc4ea93b827642c162e6": "anthropics/claude-plugins-official",
}
HEX_FULL = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{64}(?![0-9A-Fa-f])")
HEX_MARKED = re.compile(r"(?<![0-9A-Fa-f])([0-9A-Fa-f]{6,})…")  # a prefix written `<hex>…`
HEX_BARE = re.compile(r"(?<![0-9A-Za-z])([0-9A-Fa-f]{7,})(?![0-9A-Za-z])")  # a hex word of 7 digits or more


def published_digests(root=ROOT):
    """sha256 -> what, for each digest a landing text may cite: every file git tracks under tools/landing and tests/fixtures/landing as it
    is now (#1061 round 2: an untracked file there is host-only; a tree that is not a git work tree, such as a `git archive` extraction,
    has its files listed), the captured summary comment's body, and PUBLIC_DIGESTS."""
    root, known = Path(root), dict(PUBLIC_DIGESTS)
    directories = ("tools/landing", "tests/fixtures/landing")
    top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode == 0 and Path(top.stdout.strip()).resolve() == root.resolve():
        listed = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", *directories], capture_output=True, check=True).stdout
        names = sorted(name for name in listed.decode("utf-8").split("\0") if name)
    else:
        names = sorted(str(path.relative_to(root)) for directory in directories if (root / directory).is_dir()
                       for path in (root / directory).iterdir() if path.is_file())
    for name in names:
        known[hashlib.sha256((root / name).read_bytes()).hexdigest()] = name
    fixture = root / "tests/fixtures/landing/codex-summary-comment.json"
    if fixture.is_file():
        body = json.loads(fixture.read_text(encoding="utf-8"))["graphql"]["node"]["body"]
        known[hashlib.sha256(body.encode("utf-8")).hexdigest()] = "the captured summary comment's body"
    return known


def digest_custody(text, known, commits=PUBLIC_COMMITS):
    """The hex values in text that bind no published bytes, as (full digests, prefixes), each by its first 8 hex digits in lower case, so a
    failure prints no full digest. Case-insensitive (#1061 round 2): a value of 64 hex digits must be a known digest (a longer run binds
    nothing); a prefix written `<hex>…` (6 digits or more) and a bare hex word of 7 digits or more with a letter and a digit, a prefix
    written without "…" included, must start a known digest or a named public commit. A bare word of digits alone or of letters alone (a
    date such as 20261010, a count, a word) is not checked."""
    tokens = set(HEX_FULL.findall(text)) | set(HEX_MARKED.findall(text))
    tokens |= {word for word in HEX_BARE.findall(text) if len(word) >= 64 or (re.search("[A-Fa-f]", word) and re.search("[0-9]", word))}
    full, prefixes = set(), set()
    for token in {token.lower() for token in tokens}:
        if len(token) >= 64:
            if token not in known:
                full.add(token[:8])
        elif not any(value.startswith(token) for value in (*known, *commits)):
            prefixes.add(token[:8])
    return sorted(full), sorted(prefixes)


def readme_digest_custody(readme, root=ROOT):
    """The README's unpublished hex values (digest_custody on the digests published_digests gives)."""
    return digest_custody(readme, published_digests(root))


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
                # #1075: nas also runs its body file's reader isolated (python3 -I -c "$SB_READER"), outside the shared block
                reader = 'python3 -I -c "$SB_READER"'
                self.assertEqual(script.text.count("python3 -I") - script.text.count(reader), 1)
                self.assertEqual(script.text.count(reader), 1 if script.key == "nas" else 0)
                self.assertNotIn("SB_READER", script.block)
                # 2026-10-13: with a local review set, "<head>:<merge base>" for the read head and each head with its change follow it
                # (#1061 P1); none otherwise
                self.assertIn('g=$(python3 -I "$1" "$2" "$3" "$4" ${facts[@]+"${facts[@]}"} 2>&1)', script.block)
                # #1061 P1: a SET variable selects local mode, an empty one included
                self.assertIn('if [ -n "${LOCAL_REVIEWS+x}${CODEX_LOCAL_REVIEW+x}" ]; then', script.block)
                # #1061 P3: every -R is quoted, and the quoted word ends where the next argument begins
                self.assertNotIn("-R $R ", script.text)
                self.assertEqual(re.findall(r'-R "\$R"(?! )', script.text), [])
                self.assertGreater(script.text.count('-R "$R" '), 5)
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

    def test_nas_alone_requires_local_reviews_before_the_lock_and_outside_the_shared_block(self):
        # #1061 round 2: the CC kept the requirement and the waiver out of the shared block and out of codex_gate.py, which uet uses too; the
        # requirement is the first thing after the arguments, before the shared block and the lock.
        presence = '[ -n "${LOCAL_REVIEWS+x}${CODEX_LOCAL_REVIEW+x}" ] || [ -n "${LOCAL_REVIEW_WAIVER:-}" ] \\'
        lines = self.nas.lines
        self.assertEqual(lines.count(presence), 1)
        self.assertLess(lines.index(presence), lines.index("# >>> land-gate-fns"))
        self.assertLess(lines.index(presence), lines.index('lg_lock "${LANDING_LOCK_DIR:-$COORD/command-center/landing-locks}" || exit 14'))
        # #1075: the waiver's check is waiver_check, which verdict_gate and the squash body run
        self.assertIn('[ "$w" = "Waiver: local reviews for #$N at ${EF:0:8}" ]', self.nas.text[self.nas.text.index("waiver_check() {"):])
        self.assertIn("  waiver_check\n", self.nas.verdict_gate)
        for name, text in (("the shared block", self.nas.block), ("uet_land.sh", self.uet.text),
                           ("codex_gate.py", (LANDING / "codex_gate.py").read_text(encoding="utf-8"))):
            with self.subTest(text=name):
                self.assertNotIn("LOCAL_REVIEW_WAIVER", text)

    def test_squash_body_file_and_the_adjudication_are_nas_inputs_that_uet_refuses_before_the_lock(self):
        # The CC's ruling of 2026-10-13 and the CC's copy's SQUASH_BODY_FILE: nas_land.sh reads both outside the shared block, which uet_land.sh
        # carries too; the body file is checked before the shared block and the lock; codex_gate.py alone decides with the adjudication.
        # At 993cc890 neither variable was read anywhere. The CC's read of #1075: codex_gate.py decides with the adjudication wherever it is
        # set, so uet_land.sh refuses both when they are SET, before the shared block, the lock and any call, and reads them nowhere else
        # (at 25a9b48e it did not mention them, and a uet landing merged on an inherited record).
        lock = 'lg_lock "${LANDING_LOCK_DIR:-$COORD/command-center/landing-locks}" || exit 14'
        lines, nas = self.nas.lines, self.nas.text
        check = ('[ -z "${SQUASH_BODY_FILE+x}" ] || { [ "$SQUASH_BODY_FILE" != - ] && [ -f "$SQUASH_BODY_FILE" ] && [ -r "$SQUASH_BODY_FILE" ] '
                 '&& [ -s "$SQUASH_BODY_FILE" ]; } \\')
        self.assertEqual(lines.count(check), 1)
        self.assertLess(lines.index(check), lines.index("# >>> land-gate-fns"))
        self.assertLess(lines.index(check), lines.index(lock))
        self.assertIn("LOCAL_REVIEW_ADJUDICATION", nas[nas.index("verdict_gate() {"):])
        self.assertIn('ADJUDICATION = "LOCAL_REVIEW_ADJUDICATION"', (LANDING / "codex_gate.py").read_text(encoding="utf-8"))
        uet = self.uet.lines
        for variable in ("LOCAL_REVIEW_ADJUDICATION", "SQUASH_BODY_FILE"):
            refusal = (f'[ -z "${{{variable}+x}}" ] || {{ echo "#$N {variable} is set, but it is nas-only (a nas_land.sh input): stop, nothing '
                       'merged"; exit 2; }')
            with self.subTest(script="uet", variable=variable):
                self.assertEqual(uet.count(refusal), 1)
                self.assertLess(uet.index("N=${1:?pr}; E=${2:?read head}"), uet.index(refusal), "the refusal names the pull request")
                self.assertLess(uet.index(refusal), uet.index("# >>> land-gate-fns"))
                self.assertLess(uet.index(refusal), uet.index(lock))
                self.assertEqual([line for line in uet if variable in line and not line.lstrip().startswith("#")], [refusal],
                                 "uet_land.sh reads the variable nowhere else")
            with self.subTest(text="the shared block", variable=variable):
                self.assertNotIn(variable, self.nas.block)
        for cited in ("cli v2.102.0 pkg/cmd/pr/merge/merge.go:146-153", "pkg/cmdutil/file_input.go:8-15", "merge.go:138-143"):
            with self.subTest(cited=cited):
                self.assertIn(cited, nas)

    def test_the_users_type_the_repository_name_and_the_environment_tests_cite_their_sources(self):
        # #1061 round 2 (the CC's P3s and Astra's follow-up 4 at 974090cf): the type filter, the repository-name rule and the set-or-unset
        # tests cited no source for the mechanism; nor did the file replacement and the finiteness check.
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                self.assertIn("github/rest-api-description@58b1e0c0 api.github.com.json:88612-88614", script.block)
                self.assertIn('reads "Organization" (the example at :311038)', script.block)
                self.assertIn('bash(1) Parameter Expansion: "Omitting the colon tests only for a parameter that is', script.block)
        self.assertIn("api.github.com.json:344898-344915", self.nas.text)
        self.assertIn("github/docs@be38ec5d data/reusables/repositories/repo-name.md:1", self.nas.text)
        gate = (LANDING / "codex_gate.py").read_text(encoding="utf-8")
        self.assertIn("Lib/_collections_abc.py:808-813", gate)
        self.assertIn("Doc/library/json.rst:308-311", gate)
        self.assertIn("Doc/library/os.rst:2754-2760", (LANDING / "review_normalize.py").read_text(encoding="utf-8"))

    def test_the_final_gate_runs_after_the_last_slow_step_and_right_before_the_merge(self):
        # #975 round 4: the author lookup is the last slow step, final_gate the only thing between it and the pinned merge.
        for script, pinned in ((self.uet, '"$H"'), (self.nas, '"$cur"')):
            with self.subTest(script=script.key):
                merge = next(i for i, line in enumerate(script.lines) if line.startswith("out=$(gh pr merge "))
                self.assertEqual(script.lines[merge - 1], f"final_gate {pinned}")
                self.assertTrue(script.lines[merge - 2].startswith('ae=$(lg_author_email "$R")'))
                self.assertIn(f"--match-head-commit {pinned}", script.lines[merge])
                self.assertEqual(script.text.count("\nfinal_gate "), 1)

    def test_readme_names_every_variable_and_exit_code_the_scripts_use(self):
        readme = (LANDING / "README.md").read_text(encoding="utf-8")
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                for name in sorted(set(re.findall(r"\bLANDING_[A-Z_]+\b", script.text))):
                    self.assertIn(f"`{name}`", readme)
                for name in ("VERDICT_FILES", "GATES_DONE", "GPT_VERDICT", "LG_AUTHOR_LOGIN", "LOCAL_REVIEWS", "CODEX_LOCAL_REVIEW", "LOCAL_REVIEW_WAIVER",
                             "LOCAL_REVIEW_ADJUDICATION", "SQUASH_BODY_FILE"):
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
        for name in ("uet_land.sh", "nas_land.sh", "codex_gate.py", "review_normalize.py"):
            with self.subTest(file=name):
                row = next(line for line in readme.splitlines() if line.startswith(f"| `{name}` |"))
                cell = re.fullmatch(r"`([0-9a-f]{64})` \((\d+) lines\)", row.rstrip(" |").rsplit("|", 1)[1].strip())
                self.assertIsNotNone(cell, "the last cell of the row reads `<sha256>` (<n> lines)")
                data = (LANDING / name).read_bytes()
                self.assertEqual((cell.group(1), int(cell.group(2))), (hashlib.sha256(data).hexdigest(), data.count(b"\n")))

    def test_every_digest_in_the_readme_binds_published_bytes(self):
        # #1061 P1-3 (Astra at c999eee5): the README published the sha256 of the CC's live copies, which carry the host's paths, in six full
        # digests of the provenance table (and a seventh of the live gate) and in four prefixes; a digest of a host-only file is an offline
        # oracle for a guessed path (correction #161). At c999eee5 this found 7 full digests and 4 prefixes. #1061 round 2 (the CC's Claude
        # delta at 974090cf): the scripts' own text is published too, and their comments cite digests and commits.
        known = published_digests()
        for name in ("README.md", "uet_land.sh", "nas_land.sh", "codex_gate.py", "review_normalize.py"):
            with self.subTest(file=name):
                self.assertEqual(digest_custody((LANDING / name).read_text(encoding="utf-8"), known), ([], []))
        planted = (f"a live copy `{hashlib.sha256(b'host-only bytes').hexdigest()}`, a prefix `{hashlib.sha256(b'more').hexdigest()[:8]}…`, "
                   f"a tracked file's prefix `{next(iter(PUBLIC_DIGESTS))[:8]}…`")
        found = readme_digest_custody(planted)
        self.assertEqual((len(found[0]), len(found[1])), (1, 1), "the rule finds a planted digest and prefix, and passes a public one")

    def test_the_custody_guard_reads_upper_case_bare_prefixes_and_comments(self):
        # #1061 round 2 (the CC's Claude delta at 974090cf, P3; Astra's follow-up 5): the guard read lower-case hex only, a prefix only when
        # written with "…", and the README only. Each probe is found now; the guard at 974090cf (readme_digest_custody there) finds none.
        host = hashlib.sha256(b"host-only bytes").hexdigest()
        known = published_digests()
        tracked = next(digest for digest, what in known.items() if what == "tools/landing/nas_land.sh")
        commit = next(iter(PUBLIC_COMMITS))
        probes = [
            ("an upper-case digest", f"sha256 `{host.upper()}`", ([host[:8]], [])),
            ("an upper-case prefix written with an ellipsis", f"`{host[:8].upper()}…`", ([], [host[:8]])),
            ("a bare prefix", f"the live copy {host[:8]} differs", ([], [host[:8]])),
            ("a prefix written with ASCII dots", f"({host[:10]}...)", ([], [host[:8]])),
            ("a digest in a shell comment", f"# the live copy's sha256: {host}\n", ([host[:8]], [])),
            ("a run longer than a digest", f"{host}{host[:4]}", ([host[:8]], [])),
        ]
        for name, text, expected in probes:
            with self.subTest(probe=name):
                self.assertEqual(digest_custody(text, known), expected)
        for name, text in (("a tracked file's digest in upper case", tracked.upper()), ("its bare prefix", f"at {tracked[:8]}"),
                           ("a named public commit, short and in full", f"at {commit[:8]} and {commit.upper()}"),
                           ("dates, counts and words", "20261010, 1234567 and defaced")):
            with self.subTest(passes=name):
                self.assertEqual(digest_custody(text, known), ([], []))

    def test_an_untracked_file_under_tools_landing_is_not_published(self):
        # #1061 round 2 (the CC's Claude delta at 974090cf): the known digests took every file in tools/landing, so a host-only file left
        # there untracked (a live copy, say) passed the guard. A work tree's known files are the ones git tracks; a tree that is not one
        # lists its files.
        root = self.dir / f"custody-{next(self.counter)}"
        (root / "tools/landing").mkdir(parents=True)
        (root / "tools/landing/tracked.md").write_text("tracked\n", encoding="utf-8")
        (root / "tools/landing/live-copy.sh").write_text("host-only\n", encoding="utf-8")
        tracked, live = hashlib.sha256(b"tracked\n").hexdigest(), hashlib.sha256(b"host-only\n").hexdigest()
        plain = published_digests(root)
        self.assertTrue({tracked, live} <= set(plain), "outside a work tree every file is listed")
        git(root, "init", "-q")
        git(root, "add", "--", "tools/landing/tracked.md")
        known = published_digests(root)
        self.assertIn(tracked, known)
        self.assertNotIn(live, known)
        self.assertEqual(digest_custody(f"`{tracked}` and `{live[:8]}…`", known), ([], [live[:8]]))

    def test_the_pull_request_body_binds_published_bytes(self):
        # #1061 round 2 (the CC's Claude delta at 974090cf): the body is published too. LANDING_PR_BODY names its file. CI does not set it:
        # every pull request's CI runs this module (validate.yml runs the whole suite), an edit of a body does not run it again (its
        # pull_request types are opened, synchronize and reopened), and a body may cite an earlier head's files, which this tree does not hold.
        path = os.environ.get("LANDING_PR_BODY")
        if not path:
            self.skipTest("LANDING_PR_BODY names no body file")
        self.assertEqual(digest_custody(Path(path).read_text(encoding="utf-8"), published_digests()), ([], []))

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

    def test_the_stale_value_is_one_constant_and_the_readme_states_its_basis(self):
        # #1061 (the probe's finding 4): #200's 90 minutes cited no source. OpenAI's Codex docs state no review time limit, so the README says
        # so and records the measured basis (nas#1056), and the value is the one constant STALE_RUNNING_MINUTES.
        import ast
        tree = ast.parse((LANDING / "codex_gate.py").read_text(encoding="utf-8"))
        nineties = [node for node in ast.walk(tree) if isinstance(node, ast.Constant) and node.value == 90 and type(node.value) is int]
        self.assertEqual(len(nineties), 1)
        assigned = [node for node in ast.walk(tree) if isinstance(node, ast.Assign) and node.value in nineties]
        self.assertEqual([target.id for node in assigned for target in node.targets], ["STALE_RUNNING_MINUTES"])
        flat = " ".join((LANDING / "README.md").read_text(encoding="utf-8").split())
        self.assertIn("OpenAI's Codex docs state no review time limit and no behaviour for a stalled review", flat)
        self.assertIn("The basis is nas#1056", flat)
        self.assertIn("The value is the one constant `STALE_RUNNING_MINUTES`", flat)

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

    def test_the_repository_defaults_to_the_organizations_slug_and_the_author_to_the_merging_account(self):
        # 2026-10-13: native-agent-stack moved to the organization; R was a literal of the old slug (c63c83a8 nas_land.sh:28). GitHub redirects
        # the old one (github/docs@be38ec5d transferring-a-repository.md:62) until a new repository takes the old location (:68-69).
        nas_r = [self.nas.line("R=")]
        for name, extra, expected in (("default", {}, NAS_REPO), ("LANDING_REPO", {"LANDING_REPO": "o/r"}, "o/r"),
                                      ("empty falls back", {"LANDING_REPO": ""}, NAS_REPO)):
            with self.subTest(script="nas", case=name):
                self.assertEqual(self.evaluate(nas_r, ["R"], **extra), [expected])
        self.assertEqual(self.uet.line("R="), f"R={UET_REPO}", "the trading repository did not move")
        for script in (self.uet, self.nas):  # CC correction #198: the merging account is one variable in both scripts
            line = [script.line("LG_AUTHOR_LOGIN=")]
            for name, extra, expected in (("default", {}, MERGING_ACCOUNT), ("override", {"LG_AUTHOR_LOGIN": "another-lander"}, "another-lander"),
                                          ("empty falls back", {"LG_AUTHOR_LOGIN": ""}, MERGING_ACCOUNT)):
                with self.subTest(script=script.key, case=name):
                    self.assertEqual(self.evaluate(line, ["LG_AUTHOR_LOGIN"], **extra), [expected])

    def test_the_no_reply_author_is_the_merging_account_not_the_repository_owner(self):
        # CC correction #198 (2026-10-13): lg_author_email took the login from R's owner, an organization since the transfer, and GitHub refused
        # the squash merge (GraphQL "Invalid email address"): the no-reply form is a user account's, "ID+USERNAME@users.noreply.github.com"
        # (github/docs@be38ec5d email-addresses-reference.md:47). At c63c83a8 the first case asked users/native-agent-stack for the id.
        cases = [
            ("the merging account, with the organization's slug", f"R={NAS_REPO}; LG_AUTHOR_LOGIN={MERGING_ACCOUNT}", MERGING_ACCOUNT),
            ("R's owner when LG_AUTHOR_LOGIN is unset (the block on its own)", "R=owner-example/r; unset LG_AUTHOR_LOGIN", "owner-example"),
            ("R's owner when LG_AUTHOR_LOGIN is empty", "R=owner-example/r; LG_AUTHOR_LOGIN=", "owner-example"),
            ("a login of 39 characters, the longest", f"R={NAS_REPO}; LG_AUTHOR_LOGIN={'a' * 38}b", "a" * 38 + "b"),
        ]
        refused = ["a/b", "-lead", "trail-", "two--dashes", "a" * 40, "with space", "semi;colon", 'quote"d', "dot.ted"]
        for script in (self.uet, self.nas):
            for name, prelude, login in cases + [(f"a login of another shape: {bad!r}", f"R={NAS_REPO}; LG_AUTHOR_LOGIN={q(bad)}", None) for bad in refused]:
                with self.subTest(script=script.key, case=name):
                    log = self.write("author.log", "")
                    code, out = self.bash(f"{prelude}\nN=1\n{script.block}\n", 'lg_author_email "$R"', FAKE_LOG=str(log))
                    calls = log.read_text(encoding="utf-8").splitlines()
                    if login is None:
                        self.assertEqual((code, out, calls), (1, "", []), "refused before any call, nothing printed")
                    else:
                        self.assertEqual((code, out, calls), (0, f"4242424+{login}@users.noreply.github.com", [f"gh api users/{login} {USER_JQ}"]))
            # #1061 P3 (the Claude read): users/<login> answers for an organization too, whose address then failed at the merge (exit 7, as in
            # #198); only an account of type User gives an id now (at c999eee5 this printed an address)
            for kind in ("Organization", "Bot", ""):
                with self.subTest(script=script.key, case=f"an account of type {kind or 'none'}"):
                    log = self.write("author.log", "")
                    code, out = self.bash(f"R={NAS_REPO}; LG_AUTHOR_LOGIN=native-agent-stack\nN=1\n{script.block}\n", 'lg_author_email "$R"',
                                          FAKE_LOG=str(log), FAKE_USER_TYPE=kind)
                    self.assertEqual((code, out), (1, ""))
                    self.assertEqual(log.read_text(encoding="utf-8").splitlines(), [f"gh api users/native-agent-stack {USER_JQ}"])


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


LOCAL_VARIABLES = ("LOCAL_REVIEWS", "CODEX_LOCAL_REVIEW")  # 2026-10-13: the gate's local review set and its alias
ADJUDICATION_VARIABLE = "LOCAL_REVIEW_ADJUDICATION"  # the CC's ruling of 2026-10-13: the CC's adjudication record (codex_gate.py, nas_land.sh)
RECORDED_VARIABLE = "LG_ADJUDICATION_SHA256"  # #1075: the review file's sha256 nas_land.sh recorded, which the gate then requires
SHA_RE = re.compile(r"[0-9a-f]{40}")
LOCAL_LINE = re.compile(r"Local reviews: [A-Za-z0-9 :;,.()_+'-]*")  # what lg_gate echoes (its status-line characters)


@contextlib.contextmanager
def local_reviews_env(values=None):
    """os.environ with the local review variables (and the adjudication's) as given and otherwise unset: the gate reads them, and the shell
    that runs the tests may have set them. patch.dict restores the environment afterwards."""
    with mock.patch.dict(os.environ):
        for name in (*LOCAL_VARIABLES, ADJUDICATION_VARIABLE, RECORDED_VARIABLE):
            os.environ.pop(name, None)
        os.environ.update(values or {})
        yield


VERDICT_DEFAULT = object()  # normalized(): "patch is correct" for a completed codex-review, null for one that did not complete
GATE_BASE = "0a1b2c3d4e5f60718293a4b5c6d7e8f901234567"  # synthetic: the merge base of the gate tests' heads with origin/main (#1061 P1)


def normalized(head, findings=(), completed=True, reviewer="codex-review", version="codex-cli 0.162.1", correctness=VERDICT_DEFAULT,
               confidence=None, base=GATE_BASE):
    """A normalized review (README "Local reviews"; review_normalize.py writes them). A codex-review carries Codex's verdict
    (rubric.md:85), the merge base its request named (#1061 P1) and, when given, its confidence; a claude-code-review carries none."""
    review = {"reviewer": reviewer, "reviewer_version": version, "head_sha": head, "completed": completed, "findings": list(findings)}
    if reviewer == "codex-review":
        review["base_sha"] = base
        review["overall_correctness"] = (("patch is correct" if completed else None) if correctness is VERDICT_DEFAULT else correctness)
        if confidence is not None:
            review["overall_confidence_score"] = confidence
    return review


def finding(priority, title="A finding", location="tools/landing/x.py:3-5"):
    return {"priority": priority, "location": location, "title": title}


def adjudication_text(digest, pr, head, findings=(), words="fixed", extra=()):
    """The CC's adjudication record (README "Local reviews", the CC's ruling of 2026-10-13): a heading, the line that binds the review file's
    sha256, the pull request and the read head's first 8 hex digits, one Finding line per finding with its disposition (`words`, one word
    for all or one per finding), then `extra` lines. Line 3 is the binding line, line 4 the first Finding line."""
    words = [words] * len(findings) if isinstance(words, str) else list(words)
    lines = ["# Adjudication", "", f"Adjudication: local review {digest} for #{pr} at {head[:8]}"]
    lines += [f"Finding: P{item['priority']} at {item['location']}: {item['title']} ({word})" for item, word in zip(findings, words)]
    return "\n".join([*lines, *extra]) + "\n"


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
        with local_reviews_env(), mock.patch.object(self.gate.subprocess, "run", fake_run), mock.patch.object(self.gate, "datetime", Frozen), \
                contextlib.redirect_stdout(out):
            code = self.gate.main("o/r", "7", *([read] if read else []))
        return code, out.getvalue().strip()

    def run_local(self, *reviews, read=GATE_HEAD, same=(), variables=None, names=None, facts=None, adjudication=None, recorded=None):
        """The gate with a local review set: each review (a dict, or the file's bytes) in a file of its own, LOCAL_REVIEWS naming them in
        order unless `variables` maps the variables to lists of review numbers (or `names` gives the value as is). After the read head come
        the facts lg_gate passes, "<head>:<merge base>": by default the read head's and each head of `same`, all with GATE_BASE (or
        `facts` as given). `adjudication`, a function of the files' sha256 in order, gives the text (or bytes) of the CC's record, a file
        that LOCAL_REVIEW_ADJUDICATION names; a string is that variable's value as is ({dir} the scratch directory). No command may run."""
        if facts is None:
            facts = [f"{head}:{GATE_BASE}" for head in ([read] if read and SHA_RE.fullmatch(read) else []) + list(same)]
        with tempfile.TemporaryDirectory(prefix="local-reviews-") as scratch:
            paths = []
            for number, review in enumerate(reviews):
                path = Path(scratch) / f"review-{number}.json"
                path.write_bytes(review if isinstance(review, bytes) else json.dumps(review).encode("utf-8"))
                paths.append(str(path))
            values = {"LOCAL_REVIEWS": ":".join(paths)} if variables is None else {k: ":".join(paths[i] for i in v) for k, v in variables.items()}
            if names is not None:
                values = {"LOCAL_REVIEWS": names.replace("{dir}", scratch)}
            if callable(adjudication):
                record = Path(scratch) / "adjudication.md"
                text = adjudication([hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in paths])
                record.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
                values[ADJUDICATION_VARIABLE] = str(record)
            elif adjudication is not None:
                values[ADJUDICATION_VARIABLE] = adjudication.replace("{dir}", scratch)
            if recorded is not None:  # #1075: LG_ADJUDICATION_SHA256, as nas_land.sh sets it (a function of the files' sha256, or a value)
                values[RECORDED_VARIABLE] = recorded([hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in paths]) if callable(recorded) else recorded

            def no_command(*args, **kwargs):
                raise AssertionError("the gate ran a command although a local review set was given")

            out = io.StringIO()
            with local_reviews_env(values), mock.patch.object(self.gate.subprocess, "run", no_command), contextlib.redirect_stdout(out):
                code = self.gate.main("o/r", "7", *([read] if read else []), *facts)
            line = out.getvalue().strip()
            self.assertNotIn(scratch, line, "a file is named by its place, never by its path")
            return code, line

    def test_exit_code_precedence_on_canned_api_data(self):
        completed = summary(row("Completed", "2026-10-10T12:01:00Z"))
        cases = [
            # (name, kwargs, expected exit code, text the status line must contain)
            ("a Completed row after the trigger", dict(comments=[completed]), 0, "finished at 2026-10-10T12:01:00Z"),
            # #1061 round 2 (Astra's P2 at 974090cf, the CC's ruling: the latest review decides): "any completion evidence passes" gave 0
            # here; the later Cancelled review is for a person now
            ("Completed at 12:01 then Cancelled at 12:02 after the same trigger: the later Cancelled review decides",
             dict(comments=[summary(row("Completed", "2026-10-10T12:01:00Z"), row("Cancelled", "2026-10-10T12:02:00Z"))]), 4,
             "Codex review ended 'Cancelled' at 2026-10-10T12:02:00Z; not Completed"),
            ("Cancelled at 12:01 then Completed at 12:02: the later completion decides",
             dict(comments=[summary(row("Cancelled", "2026-10-10T12:01:00Z"), row("Completed", "2026-10-10T12:02:00Z"))]), 0, "finished at 2026-10-10T12:02:00Z"),
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

    # ------------------------------------------------------------------------------------------ CC correction #200 (2026-10-13)
    def test_a_running_review_without_connector_activity_for_90_minutes_is_unavailable(self):
        # The transfer of native-agent-stack to an organization cut the connector's access mid-review, and its row stayed Running: a Running
        # row gave 3 for ever (at c63c83a8 each case below that expects 5 gave 3). Activity after the start resets the age: a connector
        # note other than a summary, a connector reaction, or an edit of a summary; the start's own edit and eyes come seconds after it.
        start = "2026-10-10T12:03:00Z"
        running_row = row("Running since", start)
        stalled = summary(running_row)
        note = comment(BOT, "2026-10-10T13:03:00Z", "Still reviewing.")
        edited = {**stalled, "edits": [{"editedAt": "2026-10-10T13:03:00Z", "diff": summary_body(running_row)}, *stalled["edits"]]}

        def reaction(content, at, login=BOT):
            return {"user": {"login": login}, "content": content, "created_at": at}

        cases = [
            ("89:59 after the start", dict(comments=[stalled], now="2026-10-10T13:32:59Z"), 3, f"running since {start}"),
            ("90 minutes after the start", dict(comments=[stalled], now="2026-10-10T13:33:00Z"), 5,
             f"Codex unavailable: a review shown running since {start} has had no connector activity since {start} (90 min; stale)"),
            ("the start's own eyes reaction, 5 s later, is the last activity", dict(comments=[stalled], reactions=[reaction("eyes", "2026-10-10T12:03:05Z")],
                                                                                 now="2026-10-10T13:33:04Z"), 3, "running since"),
            ("90 minutes after that reaction", dict(comments=[stalled], reactions=[reaction("eyes", "2026-10-10T12:03:05Z")], now="2026-10-10T13:33:05Z"), 5,
             "since 2026-10-10T12:03:05Z (90 min; stale)"),
            ("a connector note an hour in", dict(comments=[stalled, note], now="2026-10-10T14:32:59Z"), 3, "running since"),
            ("90 minutes after that note", dict(comments=[stalled, note], now="2026-10-10T14:33:00Z"), 5, "since 2026-10-10T13:03:00Z (90 min; stale)"),
            ("an edit of the summary an hour in", dict(comments=[edited], now="2026-10-10T14:32:59Z"), 3, "running since"),
            ("a connector reaction an hour in", dict(comments=[stalled], reactions=[reaction("rocket", "2026-10-10T13:03:00Z")], now="2026-10-10T14:32:59Z"), 3,
             "running since"),
            ("a person's comment is no connector activity", dict(comments=[stalled, comment("someone", "2026-10-10T13:03:00Z", "Any news?")],
                                                                 now="2026-10-10T13:33:00Z"), 5, "stale"),
            ("a person's reaction is none either", dict(comments=[stalled], reactions=[reaction("eyes", "2026-10-10T13:03:00Z", "someone")],
                                                        now="2026-10-10T13:33:00Z"), 5, "stale"),
        ]
        for name, kwargs, code, text in cases:
            with self.subTest(case=name):
                got, line = self.run_gate(**kwargs)
                self.assertEqual((got, text in line), (code, True), line)

    def test_a_trigger_after_a_stall_gets_the_start_grace_and_a_failed_review_of_our_head_outranks_the_stale_5(self):
        # #1061 (the CC's /code-review probe, finding 1): the age ran from the last activity only, so an "@codex review" posted after a stalled
        # row gave 5 at once (14:00:30 below gave 5 at c999eee5); now the age runs from the later of the last activity and the latest trigger,
        # and a trigger that comes after the review had already gone stale gets NOSTART_MINUTES, the grace a first trigger gets.
        start = "2026-10-10T12:03:00Z"
        stalled = summary(row("Running since", start))
        retrigger = comment("someone", "2026-10-10T14:00:00Z", "@codex review")
        live = comment("someone", "2026-10-10T12:30:00Z", "@codex review")  # a trigger while the review was not yet stale

        def eyes(at):
            return {"user": {"login": BOT}, "content": "eyes", "created_at": at}

        # #1061 P2 (the Claude read): a stale row of another commit beside a review of the read head that ended other than Completed after the
        # trigger gave 5 (nas proceeds); the 4 ("a person decides") comes first now. Row 2 is our head's review: Running since 12:10:20, then
        # Cancelled at 12:20; row 1, of another commit, has been Running since 12:03.
        other_row = row("Running since", start, review=1, commit=OTHER[:7])
        ours_cancelled = row("Cancelled", "2026-10-10T12:20:00Z", review=2)
        mixed = summary(other_row, ours_cancelled, history=[summary_body(other_row, row("Running since", "2026-10-10T12:10:20Z", review=2))])
        trigger = comment("someone", "2026-10-10T12:10:00Z", "@codex review")
        ours_completed = summary(other_row, row("Completed", "2026-10-10T12:20:00Z", review=2),
                                 history=[summary_body(other_row, row("Running since", "2026-10-10T12:10:20Z", review=2))])
        cases = [
            ("a new trigger after the stall, 30 s later", dict(comments=[stalled, retrigger], now="2026-10-10T14:00:30Z"), 3, f"running since {start}"),
            ("the same, 9:59 later", dict(comments=[stalled, retrigger], now="2026-10-10T14:09:59Z"), 3, "running since"),
            ("the same, 10 minutes later: unavailable, as NOSTART", dict(comments=[stalled, retrigger], now="2026-10-10T14:10:00Z"), 5,
             "has had no connector activity since the latest trigger 2026-10-10T14:00:00Z (10 min; stale)"),
            ("a trigger while the review was live gets the full window from the trigger", dict(comments=[stalled, live], now="2026-10-10T13:59:59Z"),
             3, "running since"),
            ("the same, 90 minutes after that trigger", dict(comments=[stalled, live], now="2026-10-10T14:00:00Z"), 5,
             "since the latest trigger 2026-10-10T12:30:00Z (90 min; stale)"),
            # #1061 round 2 (the CC's delta read at 974090cf): the connector's eyes reaction with no Running row waits (3) with no bound, as at
            # c999eee5; 974090cf bounded it, and its 5 after 90 minutes was a new opening, which nas proceeded on (5 at 974090cf, 3 now)
            ("an eyes reaction with no Running row, 89:59", dict(reactions=[eyes(start)], now="2026-10-10T13:32:59Z"), 3, "eyes reaction is on the pull request"),
            ("an eyes reaction with no Running row, 90 minutes", dict(reactions=[eyes(start)], now="2026-10-10T13:33:00Z"), 3,
             f"Codex review running: the connector's eyes reaction is on the pull request since {start}"),
            ("an eyes reaction with no Running row, ten hours", dict(reactions=[eyes(start)], now="2026-10-10T22:03:00Z"), 3,
             f"Codex review running: the connector's eyes reaction is on the pull request since {start}"),
            ("a stale row of another commit and our head's review Cancelled", dict(comments=[mixed, trigger], now="2026-10-10T13:45:00Z"), 4,
             "Codex review ended 'Cancelled' at 2026-10-10T12:20:00Z; not Completed"),
            ("the same before it is stale still waits", dict(comments=[mixed, trigger], now="2026-10-10T13:00:00Z"), 3, f"running since {start}"),
            ("the same with our head's review Completed is the stale 5 (as before)", dict(comments=[ours_completed, trigger], now="2026-10-10T13:45:00Z"),
             5, "stale"),
        ]
        for name, kwargs, code, text in cases:
            with self.subTest(case=name):
                got, line = self.run_gate(**kwargs)
                self.assertEqual((got, text in line), (code, True), line)

    def test_the_latest_review_of_our_head_decides_so_an_earlier_completion_hides_no_later_failure(self):
        # #1061 round 2 (Astra's P2 at 974090cf): "if failed and not done" let any completion of our head since the trigger hide a later
        # Cancelled review of it. Astra's sequence: a row of another commit Running since 12:03, the trigger at 12:10, review 2 of our head
        # Running from 12:10:20 and Completed at 12:20, review 3 Running from 12:21 and Cancelled at 12:30; at 14:05 the connector's last
        # edit is 95 minutes old. The gate gave 5 there at 974090cf (nas proceeds), and with no row running the completion gave 0. The
        # latest review of our head decides: 4 for both. A later completion still supersedes an earlier failure (0, or the stale 5).
        stale = row("Running since", "2026-10-10T12:03:00Z", review=1, commit=OTHER[:7])
        trigger = comment("someone", "2026-10-10T12:10:00Z", "@codex review")

        def summarized(first, second, *others):
            """The summary comment of review 2 (`first`, then `second`) and review 3 (`second`), each first shown Running, beside the
            rows `others`; its revisions oldest first, the last its body, each by the connector."""
            steps = [("2026-10-10T12:10:20Z", (*others, row("Running since", "2026-10-10T12:10:20Z", review=2))),
                     ("2026-10-10T12:21:00Z", (*others, row(first, "2026-10-10T12:20:00Z", review=2), row("Running since", "2026-10-10T12:21:00Z", review=3))),
                     ("2026-10-10T12:30:00Z", (*others, row(first, "2026-10-10T12:20:00Z", review=2), row(second, "2026-10-10T12:30:00Z", review=3)))]
            bodies = [(at, summary_body(*cells)) for at, cells in steps]
            return {**comment(BOT, "2026-10-10T12:03:00Z", bodies[-1][1]), "edits": [{"editedAt": at, "diff": body} for at, body in reversed(bodies)]}

        cancelled = "Codex review ended 'Cancelled' at 2026-10-10T12:30:00Z; not Completed"
        cases = [
            ("a completion, a later Cancelled review and a stale row of another commit (Astra's sequence)",
             summarized("Completed", "Cancelled", stale), "2026-10-10T14:05:00Z", 4, cancelled),
            ("the same before the row is stale waits", summarized("Completed", "Cancelled", stale), "2026-10-10T13:00:00Z", 3,
             "Codex review running since 2026-10-10T12:03:00Z"),
            ("a completion and a later Cancelled review, no row running", summarized("Completed", "Cancelled"), "2026-10-10T12:35:00Z", 4, cancelled),
            ("a Cancelled review and a later completion: the completion decides", summarized("Cancelled", "Completed"), "2026-10-10T12:35:00Z", 0,
             "Codex review finished at 2026-10-10T12:30:00Z"),
            ("the same beside a stale row of another commit is the stale 5", summarized("Cancelled", "Completed", stale), "2026-10-10T14:05:00Z", 5,
             "Codex unavailable: a review shown running since 2026-10-10T12:03:00Z has had no connector activity since 2026-10-10T12:30:00Z"),
        ]
        for name, note, now, code, text in cases:
            with self.subTest(case=name):
                got, line = self.run_gate(comments=[note, trigger], now=now)
                self.assertEqual((got, text in line), (code, True), line)

    # ------------------------------------------------------------------------------------------ local reviews (2026-10-13)
    def test_a_local_review_set_decides_from_the_files_alone(self):
        # The owner's direction of 2026-10-13: reviews run locally (the connector cannot reach the organization's repository). The gate reads the files and
        # nothing else: 2 for a file that is not a normalized review of the read head, a codex-review that did not complete or whose verdict is
        # not exactly one of the rubric's two, or no codex-review at all; else 4 for "patch is incorrect" or a P0 or P1 codex finding; else 0.
        # The CC, 2026-10-13: the /code-review plugin arm is advisory (its issues and a missing comment never block).
        clean, follow_ups = normalized(GATE_HEAD), normalized(GATE_HEAD, [finding(2), finding(2), finding(3)])
        claude = normalized(GATE_HEAD, [finding(1, "The plugin's issue")], reviewer="claude-code-review", version="code-review@f359d43b")
        no_comment = normalized(GATE_HEAD, completed=False, reviewer="claude-code-review", version="code-review@f359d43b")
        cases = [
            ("one completed review", (clean,), {}, 0, f"Local reviews: codex-review of {GATE_HEAD[:8]}: patch is correct, no P0 or P1 finding; "
                                                    "P2 findings 0, P3 findings 0 (for the Follow-ups)"),
            ("P2 and P3 findings with patch is correct pass, counted", (follow_ups,), {}, 0, "patch is correct, no P0 or P1 finding; P2 findings 2, P3 findings 1"),
            ("a P1 finding", (normalized(GATE_HEAD, [finding(1), finding(2)]),), {}, 4, "P0 findings 0, P1 findings 1; a person decides; P2 findings 1"),
            ("a P0 finding", (normalized(GATE_HEAD, [finding(0)]),), {}, 4, "P0 findings 1, P1 findings 0; a person decides"),
            # the CC, 2026-10-13: "patch is incorrect" blocks whatever the findings' priorities (a6c8bf7c refused the verdict field: 2)
            ("patch is incorrect with only P2 and P3 findings is blocked", (normalized(GATE_HEAD, [finding(2), finding(3)], correctness="patch is incorrect"),),
             {}, 4, "patch is incorrect, P0 findings 0, P1 findings 0; a person decides; P2 findings 1, P3 findings 1"),
            ("patch is incorrect with no finding is blocked", (normalized(GATE_HEAD, correctness="patch is incorrect"),), {}, 4, "patch is incorrect"),
            ("two codex reviews, one incorrect", (clean, normalized(GATE_HEAD, correctness="patch is incorrect")), {}, 4,
             "codex-review, codex-review of 5e6f7a8b: patch is incorrect in 1 of 2"),
            ("an unknown verdict stops", (normalized(GATE_HEAD, [finding(3)], correctness="patch is mostly correct"),), {}, 2,
             "review file 1 of 1 (codex-review) of 5e6f7a8b has an overall_correctness that is not exactly patch is correct or patch is incorrect"),
            ("a verdict with a trailing space stops", (normalized(GATE_HEAD, correctness="patch is correct "),), {}, 2, "is not exactly patch is correct"),
            ("a verdict in other capitals stops", (normalized(GATE_HEAD, correctness="Patch is correct"),), {}, 2, "is not exactly patch is correct"),
            ("a completed review with a null verdict stops", (normalized(GATE_HEAD, correctness=None),), {}, 2, "is not exactly patch is correct"),
            ("the plugin's P1 is advisory", (clean, claude), {}, 0, "patch is correct, no P0 or P1 finding; P2 findings 0, P3 findings 0 (for the Follow-ups); "
             "advisory, not blocking: claude-code-review issues 1 (each scored 80 or more, code-review.md:26), runs without a comment 0"),
            ("a missing plugin comment does not stop the gate", (clean, no_comment), {}, 0, "runs without a comment 1 (code-review.md:26, :11)"),
            ("the advisory arm alone is no review", (claude,), {}, 2, "no completed codex-review is listed (the required arm"),
            ("a plugin file of another head still stops", (clean, normalized(OTHER, reviewer="claude-code-review")), {}, 2,
             f"review file 2 of 2 (claude-code-review) names commit {OTHER[:8]}"),
            ("a review of another head", (normalized(OTHER),), {}, 2, f"review file 1 of 1 (codex-review) names commit {OTHER[:8]}, which is neither "
                                                                       f"the read head {GATE_HEAD[:8]} nor a head carrying its change"),
            ("the same review, its head passed as carrying the read head's change", (normalized(OTHER),), {"same": (OTHER,)}, 0, "no P0 or P1 finding"),
            ("a codex-review without a base", ({k: v for k, v in normalized(GATE_HEAD).items() if k != "base_sha"},), {}, 2,
             "its fields are not those of a codex-review"),
            ("a base that is not a commit", (normalized(GATE_HEAD, base=GATE_BASE[:12]),), {}, 2, "its base_sha is not 40 lower-case hex digits"),
            ("a review that did not complete", (clean, normalized(GATE_HEAD, completed=False)), {}, 2,
             f"review file 2 of 2 (codex-review) of {GATE_HEAD[:8]} did not complete"),
            ("a malformed file is refused before any finding counts", (normalized(GATE_HEAD, [finding(1)]), b"{"), {}, 2, "review file 2 of 2 cannot be read as JSON"),
            ("no read head", (clean,), {"read": None}, 2, "the read head must be 40 lower-case hex digits"),
            ("a short read head", (clean,), {"read": GATE_HEAD[:8]}, 2, "must be 40 lower-case hex digits"),
            ("a head after it that is not a commit", (clean,), {"same": ("abc",)}, 2, "must be 40 lower-case hex digits"),
            ("the alias alone", (follow_ups,), {"variables": {"CODEX_LOCAL_REVIEW": [0]}}, 0, "P2 findings 2, P3 findings 1"),
            ("both variables: every file of both counts", (clean, normalized(GATE_HEAD, [finding(1)])),
             {"variables": {"LOCAL_REVIEWS": [0], "CODEX_LOCAL_REVIEW": [1]}}, 4, "codex-review, codex-review of 5e6f7a8b: patch is correct, P0 findings 0, P1 findings 1"),
            ("a file that does not exist", (), {"names": "{dir}/absent.json"}, 2, "review file 1 of 1 cannot be read as JSON"),
            ("separators and no name", (), {"names": "::"}, 2, "Local reviews: LOCAL_REVIEWS or CODEX_LOCAL_REVIEW is set but names no file"),
            # #1061 P1: a codex-review must have been reviewed against its head's merge base with origin/main, which lg_gate passes
            ("a review against another base", (normalized(GATE_HEAD, base=OTHER),), {}, 2,
             f"review file 1 of 1 (codex-review) was reviewed against {OTHER[:8]}, not {GATE_BASE[:8]}, the merge base of its head "
             f"{GATE_HEAD[:8]} with main"),
            ("a review against its own head", (normalized(GATE_HEAD, base=GATE_HEAD),), {}, 2, f"was reviewed against {GATE_HEAD[:8]}, not"),
            ("a merge base lg_gate could not compute", (clean,), {"facts": [f"{GATE_HEAD}:"]}, 2,
             f"the merge base of its head {GATE_HEAD[:8]} with main is unknown"),
            ("no merge base given at all (the gate run by hand)", (clean,), {"facts": []}, 2, "is unknown (lg_gate gives it)"),
            ("a rebased head's own merge base", (normalized(OTHER, base=GATE_HEAD),), {"facts": [f"{GATE_HEAD}:{GATE_BASE}", f"{OTHER}:{GATE_HEAD}"]}, 0,
             "no P0 or P1 finding"),
            ("a fact that is not head:base", (clean,), {"facts": [f"{GATE_HEAD}:{GATE_BASE}", "head:base"]}, 2, "each argument after it a head and its merge base"),
            ("the advisory arm has no base to check", (clean, normalized(GATE_HEAD, reviewer="claude-code-review")), {}, 0, "advisory, not blocking"),
        ]
        for name, reviews, kwargs, code, text in cases:
            with self.subTest(case=name):
                got, line = self.run_local(*reviews, **kwargs)
                self.assertEqual((got, text in line), (code, True), line)
                self.assertTrue(LOCAL_LINE.fullmatch(line), f"every local line is one lg_gate echoes: {line}")
                self.assertNotIn("The plugin's issue", line, "no finding's text is printed")

    def test_a_file_that_is_not_a_normalized_review_is_refused_with_2(self):
        good = normalized(GATE_HEAD, [finding(2)])
        variants = [
            ("a finding with a prose body", {**good, "findings": [{**finding(2), "body": "prose"}]}, "its finding 1 is not a priority 0 to 3"),
            ("a finding without a location", {**good, "findings": [{"priority": 2, "title": "t"}]}, "its finding 1"),
            ("priority 4", {**good, "findings": [finding(4)]}, "its finding 1"),
            ("priority -1", {**good, "findings": [finding(-1)]}, "its finding 1"),
            ("priority as text", {**good, "findings": [finding("1")]}, "its finding 1"),
            ("priority true", {**good, "findings": [finding(True)]}, "its finding 1"),
            ("priority 1.0", {**good, "findings": [finding(1.0)]}, "its finding 1"),
            ("priority null (Codex's rubric allows it, the struct does not)", {**good, "findings": [finding(None)]}, "its finding 1"),
            ("an extra field", {**good, "overall_explanation": "prose"}, "its fields are not those of a codex-review"),
            ("a missing field", {k: v for k, v in good.items() if k != "completed"}, "its fields are not reviewer"),
            ("a codex-review without its verdict", {k: v for k, v in good.items() if k != "overall_correctness"}, "its fields are not those of a codex-review"),
            ("a claude-code-review with a verdict", {**good, "reviewer": "claude-code-review"}, "its fields are not those of a claude-code-review"),
            ("a verdict that is a number", {**good, "overall_correctness": 1}, "its overall_correctness is not text or null"),
            ("a confidence as text", {**good, "overall_confidence_score": "high"}, "its overall_confidence_score is not a finite number"),
            ("a confidence of true", {**good, "overall_confidence_score": True}, "its overall_confidence_score is not a finite number"),
            ("another reviewer", {**good, "reviewer": "someone-else"}, "its reviewer is not codex-review or claude-code-review"),
            ("an empty version", {**good, "reviewer_version": " "}, "its reviewer_version is empty"),
            ("a short head", {**good, "head_sha": GATE_HEAD[:12]}, "its head_sha is not 40 lower-case hex digits"),
            ("an upper-case head", {**good, "head_sha": GATE_HEAD.upper()}, "its head_sha is not 40"),
            ("completed as text", {**good, "completed": "true"}, "its completed is not true or false"),
            ("findings as an object", {**good, "findings": {}}, "its findings are not a list"),
            ("a list, not an object", [good], "its fields are not reviewer"),
        ]
        raw = [("a repeated key (the later completed would win)", b'{"reviewer": "codex-review", "reviewer_version": "v", "head_sha": "' + GATE_HEAD.encode()
                + b'", "completed": false, "completed": true, "findings": []}', "cannot be read as JSON"),
               ("NaN", json.dumps(good).replace('"findings": [', '"findings": [NaN, ').encode(), "cannot be read as JSON"),
               # #1061 (Astra's follow-up 2): an exponent that overflows parses as inf, which passed the type check at c999eee5
               ("a confidence of 1e999", json.dumps({**good, "overall_confidence_score": 0.5}).replace("0.5", "1e999").encode(),
                "its overall_confidence_score is not a finite number"),
               ("not UTF-8", b"\xff\xfe{}", "cannot be read as JSON")]
        for name, review, text in [(n, json.dumps(r).encode("utf-8"), t) for n, r, t in variants] + raw:
            with self.subTest(case=name):
                got, line = self.run_local(review)
                self.assertEqual((got, text in line), (2, True), line)
                self.assertTrue(LOCAL_LINE.fullmatch(line), line)

    def test_unset_variables_leave_the_connector_and_a_set_empty_one_stops(self):
        # Unset variables leave the connector path as it was (us-equities-trading still uses it): the gate reads GitHub. #1061 P1 (the
        # Claude read at c999eee5): an EMPTY variable was taken for unset, so LOCAL_REVIEWS="$f" with f unset fell back to the connector,
        # which cannot reach the organization's repository, and nas proceeds on its 5 (no review at all). A set variable now selects
        # local mode, and naming no file stops (2).
        completed = summary(row("Completed", "2026-10-10T12:01:00Z"))
        with local_reviews_env({}):
            self.assertIsNone(self.gate.local_review_files())
        self.assertEqual(self.run_gate(comments=[completed])[0], 0)
        for values in ({"LOCAL_REVIEWS": ""}, {"CODEX_LOCAL_REVIEW": ""}, {"LOCAL_REVIEWS": "", "CODEX_LOCAL_REVIEW": ""}, {"LOCAL_REVIEWS": ":"}):
            with self.subTest(values=values):
                with local_reviews_env(values):
                    self.assertEqual(self.gate.local_review_files(), [])
                    out = io.StringIO()
                    with mock.patch.object(self.gate.subprocess, "run", side_effect=AssertionError("no command")), contextlib.redirect_stdout(out):
                        self.assertEqual(self.gate.main("o/r", "7", GATE_HEAD, f"{GATE_HEAD}:{GATE_BASE}"), 2)
                self.assertEqual(out.getvalue().strip(), "Local reviews: LOCAL_REVIEWS or CODEX_LOCAL_REVIEW is set but names no file; stop")

    def test_the_ccs_adjudication_decides_a_review_that_says_incorrect_with_only_p2_and_p3_findings(self):
        # The CC's ruling of 2026-10-13: after a pull request's bounded rounds, a local re-review that says "patch is incorrect" with only P2
        # and P3 findings is decided by the CC, through a record (LOCAL_REVIEW_ADJUDICATION) bound to the review file's bytes, the pull
        # request and the read head, that gives each finding a disposition. At 993cc890 the gate read no record: each case gave 4, "a person
        # decides", with none of these reasons (the empty value, the control, gave the same line there).
        p2, p3 = finding(2, "[P2] Cite the source", "tools/landing/x.py:3-5"), finding(3, "[P3] Name the variable", "tools/landing/y.sh:9-9")
        wrong, h8 = normalized(GATE_HEAD, [p2, p3], correctness="patch is incorrect"), GATE_HEAD[:8]

        def record(findings=(p2, p3), words=("fixed", "follow-ups"), pr="7", head=GATE_HEAD, extra=(), file=0, edit=None):
            def text(digests):
                written = adjudication_text(digests[file], pr, head, findings, words, extra)
                return edit(written) if edit else written
            return text
        accepted = "no P0 or P1 finding; adjudicated (LOCAL_REVIEW_ADJUDICATION): review file 1, one disposition for each P2 and P3 finding, "
        refused = "patch is incorrect, P0 findings 0, P1 findings 0; a person decides; LOCAL_REVIEW_ADJUDICATION does not decide it: "
        unbound = refused + f"its last Adjudication line does not name the sha256 of review file 1, this pull request and the read head {h8}"
        binding_last = lambda written: "\n".join(sorted(written.splitlines(), key=lambda line: line.startswith("Adjudication:"))) + "\n"
        cases = [
            ("every finding listed, fixed and follow-ups", (wrong,), record(), 0, accepted + "fixed 1, follow-ups 1, rejected 0; P2 findings 1, P3 findings 1"),
            ("rejected, with CRLF line ends", (wrong,), record(words="rejected", edit=lambda t: t.replace("\n", "\r\n")), 0,
             accepted + "fixed 0, follow-ups 0, rejected 2"),
            # #1075 (the Claude read's P3-2): only the Finding lines after the last Adjudication line count (0 at ca6f880b)
            ("the binding line last: the Finding lines before it do not count", (wrong,), record(edit=binding_last), 4,
             refused + "2 of the 2 P2 and P3 findings of review file 1 have no disposition"),
            # #1075 (the CC's ruling on the Claude read's P3-5): a review with no finding has nothing to dispose of (0 at ca6f880b)
            ("no finding at all, the binding line alone: not adjudicable", (normalized(GATE_HEAD, correctness="patch is incorrect"),), record(findings=()), 4,
             refused + "review file 1 says patch is incorrect with no finding, so there is nothing to dispose of"),
            ("the incorrect review beside a correct one", (normalized(GATE_HEAD), wrong), record(file=1), 0,
             "patch is incorrect in 1 of 2, no P0 or P1 finding; adjudicated (LOCAL_REVIEW_ADJUDICATION): review file 2,"),
            ("one P2 unlisted", (wrong,), record(findings=(p3,), words="follow-ups"), 4, refused + "1 of the 2 P2 and P3 findings of review file 1 have no disposition"),
            ("an indented Finding line, which does not count", (wrong,), record(edit=lambda t: t.replace("Finding: P3", " Finding: P3")), 4,
             refused + "1 of the 2 P2 and P3 findings of review file 1 have no disposition"),
            ("the sha256 of other bytes", (wrong,), lambda digests: adjudication_text(hashlib.sha256(b"other bytes").hexdigest(), "7", GATE_HEAD, [p2, p3]), 4, unbound),
            ("another pull request", (wrong,), record(pr="8"), 4, unbound),
            ("another head", (wrong,), record(head=OTHER), 4, unbound),
            ("revoked by a later Adjudication line", (wrong,), record(extra=("Adjudication: revoked",)), 4, unbound),
            ("no Adjudication line", (wrong,), record(edit=lambda t: t.replace("Adjudication: local", "Adjudicated: local")), 4, refused + "it has no Adjudication line"),
            ("an indented Adjudication line", (wrong,), record(edit=lambda t: t.replace("Adjudication: local", "  Adjudication: local")), 4,
             refused + "it has no Adjudication line"),
            ("a file that does not exist", (wrong,), "{dir}/absent.md", 4, refused + "it cannot be read"),
            ("a file that is not UTF-8", (wrong,), lambda digests: b"\xff" + record()(digests).encode("utf-8"), 4, refused + "it cannot be read"),
            ("a disposition other than the three", (wrong,), record(words=("fixed", "wontfix")), 4,
             refused + "its line 5 names no finding of review file 1, or a disposition other than fixed, follow-ups or rejected"),
            ("a finding the review does not have", (wrong,), record(extra=("Finding: P2 at tools/landing/z.py:1-1: [P2] Another (fixed)",)), 4,
             refused + "its line 6 names no finding of review file 1"),
            ("a finding with two dispositions", (wrong,), record(extra=(f"Finding: P2 at {p2['location']}: {p2['title']} (rejected)",)), 4,
             refused + "its Finding lines name a finding of review file 1 more times than the review holds it"),
            ("two findings that render as one line", (normalized(GATE_HEAD, [finding(2, "b: c", "a"), finding(2, "c", "a: b")], correctness="patch is incorrect"),),
             record(findings=()), 4, refused + "two findings of review file 1 render as one Finding line"),
            ("two reviews say patch is incorrect", (wrong, wrong), record(), 4, "patch is incorrect in 2 of 2, P0 findings 0, P1 findings 0; a person decides; "
             "LOCAL_REVIEW_ADJUDICATION does not decide it: 2 codex-reviews say patch is incorrect, and an adjudication decides one"),
            ("a P1 beside them", (normalized(GATE_HEAD, [p2, p3, finding(1)], correctness="patch is incorrect"),), record(), 4,
             "P1 findings 1; a person decides; LOCAL_REVIEW_ADJUDICATION decides no P0 or P1 finding"),
            ("a P0 with patch is correct", (normalized(GATE_HEAD, [finding(0)]),), record(findings=()), 4, "P0 findings 1, P1 findings 0; a person decides; "
             "LOCAL_REVIEW_ADJUDICATION decides no P0 or P1 finding"),
            ("a record where no review says patch is incorrect (it is not read)", (normalized(GATE_HEAD, [p2]),), "{dir}/absent.md", 4,
             "patch is correct, no P0 or P1 finding; a person decides; LOCAL_REVIEW_ADJUDICATION is set, but no codex-review says patch is "
             "incorrect, so it decides nothing (unset it)"),
            ("the control: an empty value is no record", (wrong,), "", 4,
             "patch is incorrect, P0 findings 0, P1 findings 0; a person decides; P2 findings 1, P3 findings 1 (for the Follow-ups)"),
        ]
        for name, reviews, adjudication, code, text in cases:
            with self.subTest(case=name):
                got, line = self.run_local(*reviews, adjudication=adjudication)
                self.assertEqual((got, text in line), (code, True), line)
                self.assertTrue(LOCAL_LINE.fullmatch(line), f"every local line is one lg_gate echoes: {line}")
                for item in (p2, p3):
                    self.assertNotIn(item["title"], line, "no finding's text is printed")
        with self.subTest(case="the record is read once in a call, and only for an incorrect review"):
            real_open, opened = open, []

            def counting_open(path, *args, **kwargs):
                opened.append(Path(path).name)
                return real_open(path, *args, **kwargs)
            with mock.patch("builtins.open", counting_open):
                self.assertEqual(self.run_local(wrong, adjudication=record())[0], 0)
                self.assertEqual(self.run_local(normalized(GATE_HEAD, [finding(1)], correctness="patch is incorrect"), adjudication=record(findings=()))[0], 4)
            self.assertEqual(opened.count("adjudication.md"), 1, opened)

    def test_the_record_counts_its_last_section_one_line_for_each_finding_and_holds_no_nul_byte(self):
        # #1075 (the Claude read at ca6f880b): P3-1, a NUL byte made the two layers read different lines (lg_text drops it, the gate saw a line
        # that does not start with "Adjudication:"); P3-2, a stale section's lines disposed of a recurring finding; P3-3, identical findings
        # and repeated Finding lines collapsed into one, and the counts said so. Each case gave 0 at ca6f880b.
        p2, p3 = finding(2, "[P2] Cite the source", "tools/landing/x.py:3-5"), finding(3, "[P3] Name the variable", "tools/landing/y.sh:9-9")
        wrong, twice = normalized(GATE_HEAD, [p2, p3], correctness="patch is incorrect"), normalized(GATE_HEAD, [p2, p2, p3], correctness="patch is incorrect")
        advisory, h8 = normalized(GATE_HEAD, reviewer="claude-code-review", version="code-review@f359d43b"), GATE_HEAD[:8]
        refused = "a person decides; LOCAL_REVIEW_ADJUDICATION does not decide it: "
        line = lambda item, word: f"Finding: P{item['priority']} at {item['location']}: {item['title']} ({word})"
        cases = [
            ("a NUL-prefixed second Adjudication line, naming the other listed file", (wrong, advisory),
             lambda d: (adjudication_text(d[0], "7", GATE_HEAD, [p2, p3]) + "\0" + f"Adjudication: local review {d[1]} for #7 at {h8}\n").encode("utf-8"), 4,
             refused + "it holds a NUL byte"),
            ("a stale section's (fixed) does not dispose of a recurring finding", (wrong,),
             lambda d: (f"Adjudication: local review {hashlib.sha256(b'the earlier review').hexdigest()} for #7 at {h8}\n{line(p2, 'fixed')}\n"
                        f"Adjudication: local review {d[0]} for #7 at {h8}\n{line(p3, 'follow-ups')}\n"), 4,
             refused + "1 of the 2 P2 and P3 findings of review file 1 have no disposition"),
            ("two identical findings and one line for them", (twice,), lambda d: adjudication_text(d[0], "7", GATE_HEAD, [p2, p3], ("fixed", "follow-ups")), 4,
             refused + "1 of the 3 P2 and P3 findings of review file 1 have no disposition"),
            ("two identical findings, a line each: each counted", (twice,), lambda d: adjudication_text(d[0], "7", GATE_HEAD, [p2, p2, p3], ("fixed", "fixed", "follow-ups")),
             0, "one disposition for each P2 and P3 finding, fixed 2, follow-ups 1, rejected 0; P2 findings 2, P3 findings 1"),
            ("a Finding line repeated beyond the review's count of it", (wrong,), lambda d: adjudication_text(d[0], "7", GATE_HEAD, [p2, p2, p3]), 4,
             refused + "its Finding lines name a finding of review file 1 more times than the review holds it"),
        ]
        for name, reviews, adjudication, code, text in cases:
            with self.subTest(case=name):
                got, out = self.run_local(*reviews, adjudication=adjudication)
                self.assertEqual((got, text in out), (code, True), out)
                self.assertTrue(LOCAL_LINE.fullmatch(out), out)

    def test_the_gate_adjudicates_only_the_review_file_nas_land_sh_recorded(self):
        # #1075 (the co-op's codex review, P2 at codex_gate.py:391-392; Astra's P2-2): nas_land.sh pins the review file's sha256 from the
        # record's first read (LG_ADJUDICATION_SHA256), and the gate adjudicates only the file whose bytes have it, so files rewritten between
        # nas's final read and the gate's cannot pass on another review while the squash body records the first. At ca6f880b the variable was
        # not read, and the other digests gave 0.
        p2 = finding(2, "[P2] Cite the source", "tools/landing/x.py:3-5")
        wrong = normalized(GATE_HEAD, [p2], correctness="patch is incorrect")
        advisory = normalized(GATE_HEAD, reviewer="claude-code-review", version="code-review@f359d43b")
        record = lambda d: adjudication_text(d[0], "7", GATE_HEAD, [p2])
        refused = "a person decides; LOCAL_REVIEW_ADJUDICATION does not decide it: review file 1 is not the file nas_land.sh recorded at the record's first read"
        for name, recorded, code, text in (("the recorded digest", lambda d: d[0], 0, "adjudicated (LOCAL_REVIEW_ADJUDICATION): review file 1,"),
                                           ("another digest", hashlib.sha256(b"the review nas recorded").hexdigest(), 4, refused),
                                           ("the other listed file's digest", lambda d: d[1], 4, refused),
                                           ("the control: none recorded (the gate run by hand)", None, 0, "adjudicated (LOCAL_REVIEW_ADJUDICATION)")):
            with self.subTest(case=name):
                got, out = self.run_local(wrong, advisory, adjudication=record, recorded=recorded)
                self.assertEqual((got, text in out), (code, True), out)
                self.assertTrue(LOCAL_LINE.fullmatch(out), out)

    def test_the_adjudication_coverage_the_claude_read_asked_for(self):
        # #1075 (the Claude read at ca6f880b): a record bound from the start to another LISTED file (the case that must kill a mutant of the
        # gate's binding check at codex_gate.py:290-291 that accepts any listed file), a title holding "(" and ")", and a record of mode 000.
        # Coverage: each gave the same answer at ca6f880b.
        p2 = finding(2, "[P2] Call f(x) (twice) in g()", "tools/landing/x.py:3-5")
        wrong = normalized(GATE_HEAD, [p2], correctness="patch is incorrect")
        advisory = normalized(GATE_HEAD, reviewer="claude-code-review", version="code-review@f359d43b")
        with self.subTest(case="bound from the start to another listed file"):
            got, out = self.run_local(wrong, advisory, adjudication=lambda d: adjudication_text(d[1], "7", GATE_HEAD, [p2]))
            self.assertEqual(got, 4, out)
            self.assertIn(f"its last Adjudication line does not name the sha256 of review file 1, this pull request and the read head {GATE_HEAD[:8]}", out)
        with self.subTest(case="a title holding ( and )"):
            got, out = self.run_local(wrong, adjudication=lambda d: adjudication_text(d[0], "7", GATE_HEAD, [p2]))
            self.assertEqual(got, 0, out)
            self.assertNotIn("f(x)", out, "no finding's text is printed")
        with self.subTest(case="a record of mode 000"):
            if os.geteuid() == 0:
                self.skipTest("root reads a file of mode 000")
            with tempfile.TemporaryDirectory(prefix="adjudication-") as scratch:
                path = Path(scratch) / "adjudication.md"
                path.write_text("Adjudication: local review x for #7 at y\n", encoding="utf-8")
                path.chmod(0)
                got, out = self.run_local(wrong, adjudication=str(path))
            self.assertEqual(got, 4, out)
            self.assertIn("LOCAL_REVIEW_ADJUDICATION does not decide it: it cannot be read", out)

    def test_command_line_needs_two_or_three_arguments(self):
        # #975 round 4: the third is the read head (the scripts pass it), whose review counts as well as the current head's. 2026-10-13: with
        # a local review set, the heads lg_gate found to carry the read head's change may follow it. The environment is given whole.
        environment = {"PATH": os.environ["PATH"], "LC_ALL": "C.UTF-8"}
        for argv in ([], ["o/r"], ["o/r", "7", "abc", "extra"]):
            with self.subTest(argv=argv):
                done = subprocess.run([sys.executable, "-I", str(LANDING / "codex_gate.py"), *argv], capture_output=True, text=True, timeout=30,
                                      env=environment)
                self.assertEqual(done.returncode, 1)
                self.assertIn("usage: codex_gate.py <owner/repo> <pr> [<read head>]", done.stderr)
        with tempfile.TemporaryDirectory(prefix="local-reviews-") as scratch:
            review = Path(scratch) / "review.json"
            review.write_text(json.dumps(normalized(OTHER)), encoding="utf-8")
            for argv, code in ((["o/r", "7", GATE_HEAD, f"{GATE_HEAD}:{GATE_BASE}", f"{OTHER}:{GATE_BASE}"], 0),
                               (["o/r", "7", GATE_HEAD, OTHER], 2), (["o/r", "7", GATE_HEAD], 2), (["o/r", "7"], 2), (["o/r"], 1)):
                with self.subTest(argv=argv, local=True):
                    done = subprocess.run([sys.executable, "-I", str(LANDING / "codex_gate.py"), *argv], capture_output=True, text=True, timeout=30,
                                          env={**environment, "LOCAL_REVIEWS": str(review)})
                    self.assertEqual((done.returncode, done.stderr if code != 1 else ""), (code, ""), done.stdout)


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
        git(cls.repo, "checkout", "-q", "-b", "two-commits", "pr")  # #1061 P1: a change of two commits, whose head^ is not the merge base
        (cls.repo / "change-2.txt").write_text("the second commit\n")
        git(cls.repo, "add", "--", "change-2.txt")
        git(cls.repo, "commit", "-q", "-m", "the change, second commit")
        cls.two = git(cls.repo, "rev-parse", "HEAD")
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
             verdict=None, draft=False, merge_commit="f" * 40, waiver=True, **extra):
        """Run a landing; returns (exit code, stdout+stderr, the fake commands' log lines). pages, a list of lists of check runs, stands
        for checkruns (one page). #1061 round 2: nas requires local reviews, so a nas landing with neither local review variable nor
        LOCAL_REVIEW_WAIVER given gets a waiver bound to the read head (waiver=True; a string is the waiver's text; False gives none),
        and the connector-path tests keep their meaning."""
        run = self.dir / f"run-{next(self.counter)}"
        run.mkdir()
        if script.key == "nas" and waiver is not False and not {"LOCAL_REVIEWS", "CODEX_LOCAL_REVIEW", "LOCAL_REVIEW_WAIVER"} & set(extra):
            read = (args[1] if args and len(args) > 1 else self.head)[:8]
            (run / "waiver.md").write_text(waiver if isinstance(waiver, str) else f"# Waiver\n\nWaiver: local reviews for #{PR} at {read}\n",
                                           encoding="utf-8")
            extra["LOCAL_REVIEW_WAIVER"] = str(run / "waiver.md")
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

    def gate_calls(self, log):  # #1075: the body file's reader (python3 -I -c) is not a gate call
        return [line for line in log if line.startswith("python3 -I ") and "validate.py" not in line and not line.startswith("python3 -I -c ")]

    def merge_calls(self, log):
        return [line for line in log if line.startswith("gh pr merge")]

    def merge_line(self, script, head, *, repo=None, waived=True, read=None):
        """The merge call as the fake gh logs it. #1061 round 2: a waived nas landing names its squash body, the body GitHub offers (the
        fake's "* the change") and then the waiver line, before --match-head-commit; every other landing names none."""
        repo = repo or (UET_REPO if script.key == "uet" else NAS_REPO)
        body = (f"--body * the change\\n\\nWaiver: local reviews for #{PR} at {(read or self.head)[:8]} (LOCAL_REVIEW_WAIVER) "
                if script.key == "nas" and waived else "")
        return f"gh pr merge {PR} -R {repo} --squash {body}--match-head-commit {head} -A {NOREPLY}"

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
        self.assertEqual(self.merge_calls(log), [self.merge_line(self.nas, self.head)])
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
                self.assertEqual(self.merge_calls(log), [self.merge_line(script, self.rebased, repo=repo)])

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
                self.assertEqual(self.merge_calls(log), [self.merge_line(script, self.rebased, repo=repo)])

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

    def test_codex_unavailable_needs_the_gpt_verdict_in_uet_and_a_head_bound_waiver_in_nas(self):
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
        # #1061 round 2 (the CC's ruling on its Claude delta at 974090cf): nas proceeded on the 5 with no local review set (exit 0 and one
        # merge at 974090cf). Local reviews are required there now: it stops with 2 before any call, and only a waiver bound to the read
        # head lets it proceed on the connector's 5, recorded in the squash body.
        code, out, log = self.land(self.nas, waiver=False, **unavailable)
        self.assertEqual((code, log), (2, []), out)
        self.assertIn(f"#{PR} local reviews are required: set LOCAL_REVIEWS=", out)
        code, out, log = self.land(self.nas, **unavailable)
        self.assertEqual((code, self.merge_calls(log)), (0, [self.merge_line(self.nas, self.head)]), out)

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
            elif line.startswith("python3 -I ") and re.search(rf"/codex_gate\.py {re.escape(repo)} {PR} {self.head}( [0-9a-f]{{40}}:[0-9a-f]{{0,40}})*$", line):
                kind = "codex"  # #1061 P1: with a local review set, the facts "<head>:<merge base>" follow the read head
            elif re.fullmatch(r"git -C \S+ cat-file -e [0-9a-f]{40}\^\{commit\}", line):
                kind = "have"  # lg_have: a local read (it fetches only a commit the clone lacks)
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

    # ------------------------------------------------------------------------------------------ 2026-10-13: the transfer, #198, local reviews
    def test_nas_lands_on_the_organizations_repository_with_the_merging_accounts_address(self):
        # Every repository-scoped gh call names the new slug (or LANDING_REPO), and the author address is the merging account's, never the
        # organization's (CC correction #198). At c63c83a8 every call named the old slug.
        for extra, repo in (({}, NAS_REPO), ({"LANDING_REPO": "example-org/native-agent-stack"}, "example-org/native-agent-stack")):
            with self.subTest(repo=repo):
                code, out, log = self.land(self.nas, **extra)
                self.assertEqual(code, 0, out)
                self.assertEqual(self.merge_calls(log), [self.merge_line(self.nas, self.head, repo=repo)])
                self.assertEqual([line for line in log if line.startswith("gh api users/")], [f"gh api users/{MERGING_ACCOUNT} {USER_JQ}"])
                scoped = [line for line in log if line.startswith("gh ") and (" -R " in line or " repos/" in line)]
                self.assertTrue(scoped)
                self.assertEqual([line for line in scoped if f" -R {repo}" not in line and f" repos/{repo}/" not in line], [])
                self.assertFalse(any(f"{MERGING_ACCOUNT}/native-agent-stack" in line for line in log), "the old slug is never used")
                self.assertTrue((self.dir / "coord/command-center/landing-locks/native-agent-stack.lock").exists())

    def test_the_merging_account_names_the_author_in_both_scripts(self):
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                address = "4242424+another-lander@users.noreply.github.com"
                code, out, log = self.land(script, LG_AUTHOR_LOGIN="another-lander", FAKE_COMMIT_EMAIL=address)
                self.assertEqual(code, 0, out)
                self.assertEqual([line for line in log if line.startswith("gh api users/")], [f"gh api users/another-lander {USER_JQ}"])
                self.assertTrue(self.merge_calls(log)[0].endswith(f" -A {address}"))
                code, out, log = self.land(script, LG_AUTHOR_LOGIN="not/a/login")
                self.assertEqual((code, self.merge_calls(log)), (11, []), out)
                self.assertEqual([line for line in log if line.startswith("gh api users/")], [], "refused before any call")

    # ------------------------------------------------------------------------------------------ #1061 round 2: local reviews required on nas
    def test_nas_without_local_reviews_or_a_waiver_stops_with_2_before_any_call(self):
        # The CC's ruling on its Claude delta at 974090cf: with LOCAL_REVIEWS and CODEX_LOCAL_REVIEW both unset, nas asked the connector and
        # proceeded on its 5 (exit 0 and one merge at 974090cf). It stops now, before any call: before the lock (held, it still gives 2, not
        # 14), update-branch and ready. An empty waiver is no waiver.
        import fcntl
        stop = (f"#{PR} local reviews are required: set LOCAL_REVIEWS=<review file>[:<review file>...], or LOCAL_REVIEW_WAIVER=<waiver file> "
                "(README, Local reviews): stop, nothing merged")
        for extra in ({}, {"LOCAL_REVIEW_WAIVER": ""}, {"FAKE_GATE_RC": "5", "FAKE_GATE_LINE": "Codex unavailable: usage-limit or account notice"}):
            with self.subTest(extra=extra):
                code, out, log = self.land(self.nas, waiver=False, draft=True, merge_state="BEHIND", **extra)
                self.assertEqual((code, out, log), (2, stop, []))
        path = self.lock_path(self.nas)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, out, log = self.land(self.nas, waiver=False)
        self.assertEqual((code, out, log), (2, stop, []), "the requirement comes before the lock")

    def test_a_waiver_not_bound_to_the_pull_request_and_the_read_head_stops_with_2_before_github_state_changes(self):
        # The waiver binds the pull request and the read head's first 8 hex digits, as uet_land.sh binds GPT_VERDICT. verdict_gate reads it
        # after the lock and before update-branch and ready, so a draft that is BEHIND gets neither, no gate runs, and nothing is merged.
        h8 = self.head[:8]
        cases = [
            ("another pull request", f"Waiver: local reviews for #{int(PR) + 1} at {h8}\n"),
            ("another head", f"Waiver: local reviews for #{PR} at {self.other[:8]}\n"),
            ("a longer head prefix than the agreed line's", f"Waiver: local reviews for #{PR} at {self.head[:12]}\n"),
            ("revoked by a later Waiver line", f"Waiver: local reviews for #{PR} at {h8}\nWaiver: revoked\n"),
            ("an indented line", f"  Waiver: local reviews for #{PR} at {h8}\n"),
            ("no Waiver line, a PASS verdict", f"Verdict: PASS at {h8}\n"),
        ]
        for name, text in cases:
            with self.subTest(case=name):
                code, out, log = self.land(self.nas, waiver=text, draft=True, merge_state="BEHIND")
                self.assertEqual((code, self.merge_calls(log), self.gate_calls(log)), (2, [], []), out)
                self.assertIn(f"#{PR} local review waiver waiver.md does not waive #{PR} at {h8} (its last Waiver line must read "
                              f"'Waiver: local reviews for #{PR} at {h8}'): stop", out)
                self.assertEqual([line for line in log if line.startswith(("gh pr ready", "gh pr update-branch"))], [])
                self.assertNotIn(str(self.dir), out, "the waiver is named by its file name only")
        with self.subTest(case="missing"):
            code, out, log = self.land(self.nas, LOCAL_REVIEW_WAIVER=str(self.dir / "absent-waiver.md"), draft=True, merge_state="BEHIND")
            self.assertEqual((code, self.merge_calls(log), self.gate_calls(log)), (2, [], []), out)
            self.assertIn(f"#{PR} local review waiver missing: absent-waiver.md", out)
            self.assertNotIn(str(self.dir), out)

    def test_a_head_bound_waiver_lands_on_the_connector_and_the_squash_body_records_it(self):
        # The squash body is the body GitHub offers for the squash (viewerMergeBodyText, read once, before the author lookup), then the
        # waiver line; the merge is otherwise the one before. CRLF line ends count; an empty default leaves the waiver line alone; a failed
        # read stops with 7, nothing merged and nothing of gh's printed.
        crlf = f"# Waiver\r\n\r\nWaiver: local reviews for #{PR} at {self.head[:8]}\r\n"
        for name, waiver in (("LF", True), ("CRLF", crlf)):
            with self.subTest(case=name):
                code, out, log = self.land(self.nas, waiver=waiver)
                self.assertEqual((code, self.merge_calls(log)), (0, [self.merge_line(self.nas, self.head)]), out)
                self.assertEqual(out.count(f"#{PR} local reviews waived at {self.head[:8]} by waiver.md: the Codex gate reads the connector"), 2,
                                 "at the early refusals and at the final gate")
                reads = [i for i, line in enumerate(log) if line.startswith("gh api graphql") and "viewerMergeBodyText(mergeType: SQUASH)" in line]
                self.assertEqual(len(reads), 1)
                self.assertLess(reads[0], max(i for i, line in enumerate(log) if line.startswith("gh api users/")))
        with self.subTest(case="an empty default body"):
            code, out, log = self.land(self.nas, FAKE_SQUASH_BODY="")
            self.assertEqual((code, self.merge_calls(log)), (0, [f"gh pr merge {PR} -R {NAS_REPO} --squash --body Waiver: local reviews for #{PR} at "
                                                                 f"{self.head[:8]} (LOCAL_REVIEW_WAIVER) --match-head-commit {self.head} -A {NOREPLY}"]), out)
        with self.subTest(case="the read fails"):
            code, out, log = self.land(self.nas, FAKE_FAIL="api graphql*", FAKE_FAIL_STDOUT='{"message": "a detail of the reply"}',
                                       FAKE_FAIL_STDERR="gh: a detail of the reply")
            self.assertEqual((code, self.merge_calls(log)), (7, []), out)
            self.assertIn(f"#{PR} the squash body for the local review waiver could not be read (output withheld): stop, nothing merged", out)
            self.assertNotIn("a detail of the reply", out)

    def test_the_final_gate_reads_the_waiver_again(self):
        # A waiver rebound to another head after the slow steps (here at the author lookup, the last of them) stops at the final gate.
        waiver = self.dir / f"waiver-{next(self.counter)}.md"
        waiver.write_text(f"Waiver: local reviews for #{PR} at {self.head[:8]}\n", encoding="utf-8")
        hook = f"printf 'Waiver: local reviews for #{PR} at {self.other[:8]}\\n' > {q(str(waiver))}"
        code, out, log = self.land(self.nas, LOCAL_REVIEW_WAIVER=str(waiver), FAKE_GH_HOOK_ON="api users/*", FAKE_GH_HOOK=hook)
        self.assertEqual((code, self.merge_calls(log)), (2, []), out)
        self.assertIn(f"#{PR} local reviews waived at {self.head[:8]} by {waiver.name}", out, "the early check passed")
        self.assertIn(f"#{PR} local review waiver {waiver.name} does not waive #{PR} at {self.head[:8]}", out)

    def test_with_a_local_review_set_the_waiver_is_not_read_and_the_merge_names_no_body(self):
        # Local mode decides from the review files alone: a waiver that would stop is not read, and nothing is added to the merge.
        waiver = self.dir / f"waiver-{next(self.counter)}.md"
        waiver.write_text(f"Waiver: local reviews for #{int(PR) + 1} at {self.other[:8]}\n", encoding="utf-8")
        code, out, log = self.land(self.nas, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=self.local_review(self.head), LOCAL_REVIEW_WAIVER=str(waiver))
        self.assertEqual((code, self.merge_calls(log)), (0, [self.merge_line(self.nas, self.head, waived=False)]), out)
        self.assertNotIn("waive", out)
        self.assertFalse([line for line in log if "viewerMergeBodyText" in line])

    def test_uet_with_the_local_review_variables_unset_is_unchanged_and_ignores_a_waiver(self):
        # The CC: uet keeps the connector path; the requirement and the waiver are nas_land.sh's alone.
        waiver = self.dir / f"waiver-{next(self.counter)}.md"
        waiver.write_text(f"Waiver: local reviews for #{int(PR) + 1} at {self.other[:8]}\n", encoding="utf-8")
        for extra in ({}, {"LOCAL_REVIEW_WAIVER": str(waiver)}):
            with self.subTest(extra=sorted(extra)):
                code, out, log = self.land(self.uet, **extra)
                self.assertEqual((code, self.merge_calls(log)), (0, [f"gh pr merge {PR} -R {UET_REPO} --squash --match-head-commit {self.head} -A {NOREPLY}"]), out)
                self.assertNotIn("waive", out)
                self.assertFalse([line for line in log if "viewerMergeBodyText" in line])

    def merge_base(self, head):
        return git(self.repo, "merge-base", head, "origin/main")

    def local_review(self, head, findings=(), base=None, **kwargs):
        """A normalized review file of `head`; a codex-review names the merge base of `head` with origin/main unless `base` is given."""
        path = self.dir / f"review-{next(self.counter)}.json"
        path.write_text(json.dumps(normalized(head, findings, base=base or self.merge_base(head), **kwargs)), encoding="utf-8")
        return str(path)

    def test_a_local_review_set_decides_the_codex_gate_through_the_real_gate_in_both_scripts(self):
        # The owner's direction of 2026-10-13. With LOCAL_REVIEWS set, the real codex_gate.py runs (FAKE_REAL_PYTHON) and decides from the files:
        # it calls nothing (the fake gh fails every connector read, so a call would give exit 9). lg_gate echoes its 2 as well as its 0 and 4.
        p1 = finding(1, "A blocking finding", "change.txt:1-1")
        p2 = finding(2, "A follow-up", "change.txt:1-1")
        malformed = self.dir / f"review-{next(self.counter)}.json"
        malformed.write_text(json.dumps({**normalized(self.head), "body": "prose"}), encoding="utf-8")
        for script in (self.uet, self.nas):
            repo, calls = (UET_REPO, 2) if script.key == "uet" else (NAS_REPO, 3)
            cases = [
                ("a completed review of the read head", {"LOCAL_REVIEWS": self.local_review(self.head, [p2])}, 0,
                 f"Local reviews: codex-review of {self.head[:8]}: patch is correct, no P0 or P1 finding; P2 findings 1, P3 findings 0 (for the Follow-ups)", calls),
                ("the advisory plugin arm through the alias", {"LOCAL_REVIEWS": self.local_review(self.head),
                                                               "CODEX_LOCAL_REVIEW": self.local_review(self.head, [p1], reviewer="claude-code-review")}, 0,
                 "advisory, not blocking: claude-code-review issues 1 (each scored 80 or more, code-review.md:26)", calls),
                ("a missing plugin comment does not stop the landing",
                 {"LOCAL_REVIEWS": ":".join([self.local_review(self.head), self.local_review(self.head, completed=False, reviewer="claude-code-review")])}, 0,
                 "runs without a comment 1 (code-review.md:26, :11)", calls),
                ("a P1 finding", {"LOCAL_REVIEWS": self.local_review(self.head, [p1, p2])}, 9, "P1 findings 1; a person decides", 1),
                ("patch is incorrect with only a P2 finding", {"LOCAL_REVIEWS": self.local_review(self.head, [p2], correctness="patch is incorrect")}, 9,
                 "patch is incorrect, P0 findings 0, P1 findings 0; a person decides", 1),
                ("an unknown verdict", {"LOCAL_REVIEWS": self.local_review(self.head, correctness="looks fine")}, 9, "is not exactly patch is correct", 1),
                ("a review of another change", {"LOCAL_REVIEWS": self.local_review(self.other)}, 9, f"names commit {self.other[:8]}", 1),
                ("a review that did not complete", {"LOCAL_REVIEWS": self.local_review(self.head, completed=False)}, 9, "did not complete", 1),
                ("a malformed file", {"LOCAL_REVIEWS": str(malformed)}, 9, "is not a normalized review: its fields are not", 1),
                ("a missing file", {"LOCAL_REVIEWS": str(self.dir / "absent-review.json")}, 9, "review file 1 of 1 cannot be read as JSON", 1),
            ]
            for name, extra, expected, text, gate_calls in cases:
                with self.subTest(script=script.key, case=name):
                    code, out, log = self.land(script, FAKE_REAL_PYTHON=sys.executable, **extra)
                    self.assertEqual(code, expected, out)
                    self.assertIn(text, out)
                    self.assertEqual(len(self.gate_calls(log)), gate_calls)
                    self.assertEqual(len(self.merge_calls(log)), 1 if expected == 0 else 0)
                    self.assertEqual([line for line in log if line.startswith("gh api graphql") or "/issues/" in line or "/pulls/" in line], [],
                                     "no connector read")
                    self.assertNotIn(str(self.dir), out, "no path is printed")
                    if expected == 9:
                        self.assertNotIn("details withheld", out, "the gate's own line is echoed")

    def test_a_local_review_of_a_pure_rebase_counts_by_the_scripts_change_identity(self):
        # "or a pure rebase of it, using the scripts' existing change check": lg_gate runs lg_same_change on each file's head and passes the
        # heads that carry the read head's change after it; any other head is refused by the gate (above).
        gate = f"{os.path.realpath(LANDING)}/codex_gate.py"
        for script in (self.uet, self.nas):
            repo, calls = (UET_REPO, 2) if script.key == "uet" else (NAS_REPO, 3)
            # #1061 P1: each head goes to the gate with its merge base with origin/main, the read head's first
            facts = f"{self.head}:{self.merge_base(self.head)} {self.rebased}:{self.merge_base(self.rebased)}"
            with self.subTest(script=script.key):
                code, out, log = self.land(script, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=self.local_review(self.rebased))
                self.assertEqual(code, 0, out)
                self.assertEqual(self.gate_calls(log), [f"python3 -I {gate} {repo} {PR} {self.head} {facts}"] * calls)
            with self.subTest(script=script.key, case="the same rebase in two files, and another change"):
                files = ":".join([self.local_review(self.rebased), self.local_review(self.rebased, reviewer="claude-code-review"),
                                  self.local_review(self.other)])
                code, out, log = self.land(script, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=files)
                self.assertEqual((code, self.merge_calls(log)), (9, []), out)
                self.assertEqual(self.gate_calls(log), [f"python3 -I {gate} {repo} {PR} {self.head} {facts}"],
                                 "the rebase is passed once, the other change not at all")
                self.assertIn(f"review file 3 of 3 (codex-review) names commit {self.other[:8]}", out)

    def test_the_landing_lock_is_held_through_every_local_review_gate_call(self):
        # The advisor's check: lg_gate's new reads (a here-string read, jq, the change identity) must leave the lock held. At each gate call a
        # second flock -n on the lock file fails while the landing runs, and the lock is free once it ends.
        import fcntl
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                probe, lock = self.dir / f"lock-probe-{next(self.counter)}.txt", self.lock_path(script)
                # -E 75: a conflict exits 75 (util-linux flock.1.adoc), so any other failure is "error", never taken for "held"
                hook = (f"flock -n -E 75 {q(lock)} true; rc=$?; case $rc in 0) echo free ;; 75) echo held ;; *) echo error-$rc ;; esac >> {q(probe)}")
                code, out, log = self.land(script, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=self.local_review(self.rebased), FAKE_GATE_HOOK=hook)
                self.assertEqual(code, 0, out)
                self.assertEqual(probe.read_text(encoding="utf-8").split(), ["held"] * (2 if script.key == "uet" else 3))
                subprocess.run(["sh", "-c", hook], check=True, timeout=30)  # the control: the same probe once the landing has ended
                self.assertEqual(probe.read_text(encoding="utf-8").split()[-1], "free")
                with open(lock, "a", encoding="utf-8") as handle:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)  # BlockingIOError if the lock outlived the landing

    def test_with_a_local_review_of_the_read_head_the_final_gate_also_reads_its_merge_base(self):
        # The advisor's pin of the local path's call shape: lg_gate reads the file with jq (not logged) and, #1061 P1, reads the read head's
        # merge base with origin/main (lg_have's cat-file, then git merge-base: local reads, no fetch) before the gate, which calls nothing.
        expected = {"uet": ["head", "change", "trading-cc-read", "have", "change", "codex", "ci"],
                    "nas": ["head", "change", "trading-cc-read", "have", "change", "codex", "ci", "main"]}
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=self.local_review(self.head))
                self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
                self.assertEqual(self.final_reads(script, log), expected[script.key])

    # ------------------------------------------------------------------------------------------ #1061 at c999eee5 (the Claude read, the probe)
    def land_two(self, script, **extra):
        """A landing of the two-commit change (self.two), its verdict naming it."""
        verdict = self.dir / f"verdict-two-{next(self.counter)}.md"
        verdict.write_text(f"# Read\n\nVerdict: PASS at {self.two[:8]}\n", encoding="utf-8")
        return self.land(script, head=self.two, args=[PR, self.two[:12]] + ([str(verdict)] if script.key == "nas" else []), **extra)

    def test_a_codex_review_against_another_base_stops_both_scripts(self):
        # P1: Codex reviews HEAD against the merge base of its base branch (codex-rs/prompts/src/review_request.rs:21, :62-70), so a review run
        # with its base at the head reviews nothing and one at head^ only the last commit; at c999eee5 the file carried no base and both landed.
        merge_base, parent = self.merge_base(self.two), git(self.repo, "rev-parse", f"{self.two}^")
        self.assertNotEqual(parent, merge_base, "a change of two commits: head^ is a commit of the branch")
        for script in (self.uet, self.nas):
            for name, base, code, text in (("base = head", self.two, 9, f"was reviewed against {self.two[:8]}, not {merge_base[:8]}, the merge base"),
                                           ("base = head^", parent, 9, f"was reviewed against {parent[:8]}, not {merge_base[:8]}, the merge base"),
                                           ("base = the merge base with origin/main", merge_base, 0, "no P0 or P1 finding")):
                with self.subTest(script=script.key, case=name):
                    code_, out, log = self.land_two(script, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=self.local_review(self.two, base=base))
                    self.assertEqual((code_, len(self.merge_calls(log))), (code, 1 if code == 0 else 0), out)
                    self.assertIn(text, out)

    def test_a_set_but_empty_local_review_variable_stops_instead_of_asking_the_connector(self):
        # P1: at c999eee5 an empty value was taken for unset and the connector was asked; here the fake gh cannot answer it (exit 9 through the
        # gate's error), and on the organization's repository the connector gives 5, on which nas proceeds without any review.
        for script in (self.uet, self.nas):
            for variable in LOCAL_VARIABLES:
                with self.subTest(script=script.key, variable=variable):
                    code, out, log = self.land(script, FAKE_REAL_PYTHON=sys.executable, **{variable: ""})
                    self.assertEqual((code, self.merge_calls(log)), (9, []), out)
                    self.assertIn("Local reviews: LOCAL_REVIEWS or CODEX_LOCAL_REVIEW is set but names no file; stop", out)
                    self.assertEqual([line for line in log if line.startswith("gh api graphql") or "/issues/" in line], [], "the connector is not asked")

    def test_codex_wait_says_what_to_do_on_a_local_2(self):
        # The probe's finding 8: codex_wait answered a wrong local review file with "land after Codex finishes"
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=self.local_review(self.other))
                self.assertEqual(code, 9, out)
                self.assertIn(": stop, correct the local review files or write them again (LOCAL_REVIEWS)", out)
                self.assertNotIn("land after Codex finishes", out)

    def test_landing_repo_must_have_the_owner_name_shape(self):
        # P3: R came from LANDING_REPO unchecked and was expanded unquoted (-R $R), so whitespace split it into extra gh arguments
        for value in ("o/r x", "a b/c", "owner", "o/", "/r", "-o/r", "o--x/r", "o/..", "o/.", "o/r/x", "x" * 40 + "/r", "o/r;x"):
            with self.subTest(value=value):
                code, out, log = self.land(self.nas, LANDING_REPO=value)
                self.assertEqual((code, log), (2, []), out)
                self.assertIn("LANDING_REPO is not of the owner/name shape: stop, nothing merged", out)
        code, out, log = self.land(self.nas, LANDING_REPO="o-x/" + "r" * 100)
        self.assertEqual(code, 0, out)

    def test_an_organization_login_stops_before_the_merge_with_11(self):
        # P3: users/<login> answers for an organization too; its address failed only at the merge (exit 7, as in #198)
        for script in (self.uet, self.nas):
            with self.subTest(script=script.key):
                code, out, log = self.land(script, FAKE_USER_TYPE="Organization")
                self.assertEqual((code, self.merge_calls(log)), (11, []), out)
                self.assertIn("cannot form the no-reply author address", out)

    # ------------------------------------------------------------------------------------------ the CC's ruling of 2026-10-13, SQUASH_BODY_FILE
    def adjudication(self, review, text=None, *, name=None, pr=PR, head=None, findings=(), words="fixed", extra=()):
        """The CC's adjudication record of the review file `review` (bound to its sha256 as written), in a new file named `name` (default
        adjudication.md) of its own directory, or `text` as given; returns the record's path and the review file's sha256."""
        digest = hashlib.sha256(Path(review).read_bytes()).hexdigest()
        path = self.dir / f"adjudication-{next(self.counter)}" / (name or "adjudication.md")
        path.parent.mkdir()
        path.write_text(adjudication_text(digest, pr, head or self.head, findings, words, extra) if text is None else text, encoding="utf-8")
        return str(path), digest

    def body_merge(self, body, head=None):
        """The merge call as the fake gh logs it, with `body` (its newlines as \\n) as the squash body."""
        return f"gh pr merge {PR} -R {NAS_REPO} --squash --body {body} --match-head-commit {head or self.head} -A {NOREPLY}"

    def test_an_adjudicated_review_that_says_incorrect_with_only_p2_and_p3_findings_lands_and_the_squash_body_records_it(self):
        # The CC's ruling of 2026-10-13: the record decides the review, and the squash body records it after the body GitHub offers, as it
        # records a waiver (viewerMergeBodyText, read once). At 993cc890 the gate gave 4 whatever the record said (exit 9, no merge).
        p2, p3 = finding(2, "[P2] Cite the source", "change.txt:1-1"), finding(3, "[P3] Name it", "change.txt:1-1")
        review = self.local_review(self.head, [p2, p3], correctness="patch is incorrect")
        record, digest = self.adjudication(review, findings=[p2, p3], words=("fixed", "follow-ups"))
        code, out, log = self.land(self.nas, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=review, LOCAL_REVIEW_ADJUDICATION=record)
        h8 = self.head[:8]
        self.assertEqual((code, self.merge_calls(log)), (0, [self.body_merge(
            f"* the change\\n\\nAdjudication: local review {digest} for #{PR} at {h8} (LOCAL_REVIEW_ADJUDICATION)")]), out)
        self.assertEqual(out.count(f"#{PR} local review adjudication adjudication.md names #{PR} at {h8} and a listed review file: the Codex gate "
                                   "decides with it"), 2, "at the early refusals and at the final gate")
        self.assertIn(f"Local reviews: codex-review of {h8}: patch is incorrect, no P0 or P1 finding; adjudicated (LOCAL_REVIEW_ADJUDICATION): review "
                      "file 1, one disposition for each P2 and P3 finding, fixed 1, follow-ups 1, rejected 0", out)
        self.assertEqual(len(self.gate_calls(log)), 3, "at the wait, before the validation and in the final gate")
        self.assertEqual(len([line for line in log if "viewerMergeBodyText" in line]), 1)
        self.assertNotIn(digest, out, "nothing of the record is printed")
        self.assertNotIn(str(self.dir), out, "no path is printed")
        with self.subTest(case="the offered body's read fails"):
            code, out, log = self.land(self.nas, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=review, LOCAL_REVIEW_ADJUDICATION=record,
                                       FAKE_FAIL="api graphql*", FAKE_FAIL_STDOUT='{"message": "a detail of the reply"}', FAKE_FAIL_STDERR="gh: a detail")
            self.assertEqual((code, self.merge_calls(log)), (7, []), out)
            self.assertIn(f"#{PR} the squash body for the local review adjudication could not be read (output withheld): stop, nothing merged", out)
            self.assertNotIn("a detail", out)

    def test_the_readmes_commands_write_a_record_that_the_adjudication_accepts(self):
        # The README's two lines write the record from the normalized file (jq renders each finding as the gate does), so the CC sets only
        # the dispositions; they run here with their placeholders filled in. At 993cc890 the README had no such lines.
        readme = (LANDING / "README.md").read_text(encoding="utf-8").splitlines()
        first = next(i for i, line in enumerate(readme) if line.startswith("{ printf 'Adjudication: local review %s for #%s at %s\\n' "))
        p2, p3 = finding(2, '[P2] Cite "the" source `x`', "change.txt:1-1"), finding(3, "[P3] Name it", "change.txt:2-2")
        review = self.local_review(self.head, [p2, p3], correctness="patch is incorrect")
        record = self.dir / f"adjudication-{next(self.counter)}.md"
        script = "\n".join(readme[first:first + 2])
        for placeholder, value in (("<codex file>", q(review)), ("<pr>", PR), ("<head8>", self.head[:8]), ("<adjudication file>", q(record))):
            script = script.replace(placeholder, value)
        subprocess.run(["bash", "-c", script], check=True, timeout=30, env=self.env())
        code, out, log = self.land(self.nas, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=review, LOCAL_REVIEW_ADJUDICATION=str(record))
        self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)
        self.assertIn("one disposition for each P2 and P3 finding, fixed 2, follow-ups 0, rejected 0", out)

    def test_an_adjudication_not_bound_to_the_pull_request_the_read_head_and_a_listed_review_stops_with_2_before_github_state_changes(self):
        # verdict_gate reads the record after the lock and before update-branch and ready, as it reads a waiver, so a draft that is BEHIND
        # gets neither, no gate runs and nothing is merged. At 993cc890 the record was not read: each landing was updated, marked ready and
        # stopped by the gate's 4 (exit 9).
        p2 = finding(2, "[P2] Cite the source", "change.txt:1-1")
        review = self.local_review(self.head, [p2], correctness="patch is incorrect")
        digest, h8 = hashlib.sha256(Path(review).read_bytes()).hexdigest(), self.head[:8]
        bound = (f"#{PR} local review adjudication adjudication.md does not adjudicate #{PR} at {h8} (its last Adjudication line must read "
                 f"'Adjudication: local review <sha256 of the review file> for #{PR} at {h8}'): stop")
        cases = [
            ("another pull request", adjudication_text(digest, str(int(PR) + 1), self.head, [p2]), bound),
            ("another head", adjudication_text(digest, PR, self.other, [p2]), bound),
            ("a longer head prefix than the agreed line's", f"Adjudication: local review {digest} for #{PR} at {self.head[:12]}\n", bound),
            ("revoked by a later Adjudication line", adjudication_text(digest, PR, self.head, [p2], extra=("Adjudication: revoked",)), bound),
            ("an indented Adjudication line", "  " + adjudication_text(digest, PR, self.head, [p2]).split("\n", 2)[2], bound),
            ("a sha256 cut short", adjudication_text(digest[:40], PR, self.head, [p2]), bound),
            ("the sha256 of no listed file", adjudication_text(hashlib.sha256(b"other bytes").hexdigest(), PR, self.head, [p2]),
             f"#{PR} local review adjudication adjudication.md names the sha256 of no file of LOCAL_REVIEWS or CODEX_LOCAL_REVIEW: stop"),
        ]
        for name, text, phrase in cases:
            with self.subTest(case=name):
                record, _ = self.adjudication(review, text)
                code, out, log = self.land(self.nas, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=review, LOCAL_REVIEW_ADJUDICATION=record,
                                           draft=True, merge_state="BEHIND")
                self.assertEqual((code, self.merge_calls(log), self.gate_calls(log)), (2, [], []), out)
                self.assertIn(phrase, out)
                self.assertEqual([line for line in log if line.startswith(("gh pr ready", "gh pr update-branch"))], [])
                self.assertNotIn(str(self.dir), out, "the record is named by its file name only")
        with self.subTest(case="missing"):
            code, out, log = self.land(self.nas, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=review,
                                       LOCAL_REVIEW_ADJUDICATION=str(self.dir / "absent-adjudication.md"), draft=True, merge_state="BEHIND")
            self.assertEqual((code, self.merge_calls(log), self.gate_calls(log)), (2, [], []), out)
            self.assertIn(f"#{PR} local review adjudication missing: absent-adjudication.md", out)
            self.assertNotIn(str(self.dir), out)

    def test_an_adjudication_that_does_not_decide_the_review_keeps_the_gates_4(self):
        # The gate decides whether the record decides the review: an unlisted finding, a P1, a disposition other than the three, or a record
        # where no review says "patch is incorrect" stop the landing at the wait (the gate's 4, exit 9), its own line echoed. At 993cc890
        # the gate gave its 4 without these reasons, and the last landing merged.
        p1, p2, p3 = (finding(n, f"[P{n}] A finding", "change.txt:1-1") for n in (1, 2, 3))
        incorrect = dict(correctness="patch is incorrect")
        cases = [
            ("one P2 unlisted", [p2, p3], incorrect, dict(findings=[p3], words="follow-ups"), "1 of the 2 P2 and P3 findings of review file 1 have no disposition"),
            ("a P1 beside a listed P2", [p1, p2], incorrect, dict(findings=[p2]), "P1 findings 1; a person decides; LOCAL_REVIEW_ADJUDICATION decides no P0 or P1 finding"),
            ("a disposition other than the three", [p2], incorrect, dict(findings=[p2], words="later"),
             "its line 4 names no finding of review file 1, or a disposition other than fixed, follow-ups or rejected"),
            ("no review says patch is incorrect", [p2], {}, dict(findings=[p2]), "LOCAL_REVIEW_ADJUDICATION is set, but no codex-review says patch is "
             "incorrect, so it decides nothing (unset it)"),
            # #1075 (the CC's ruling on the Claude read's P3-5): nothing to dispose of, so a person decides (it merged at ca6f880b)
            ("patch is incorrect with no finding at all", [], incorrect, dict(findings=[]),
             "review file 1 says patch is incorrect with no finding, so there is nothing to dispose of"),
        ]
        for name, findings, kwargs, options, phrase in cases:
            with self.subTest(case=name):
                review = self.local_review(self.head, findings, **kwargs)
                record, _ = self.adjudication(review, **options)
                code, out, log = self.land(self.nas, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=review, LOCAL_REVIEW_ADJUDICATION=record)
                self.assertEqual((code, self.merge_calls(log), len(self.gate_calls(log))), (9, [], 1), out)
                self.assertIn(phrase, out)
                self.assertNotIn("details withheld", out, "the gate's own line is echoed")
                self.assertNotIn("[P2] A finding", out, "no finding's text is printed")

    def test_the_final_gate_reads_the_adjudication_again(self):
        # As the waiver: the record is read again at the final gate, by verdict_gate and by the gate. Each change is made after the slow
        # steps (at the author lookup, the last of them). At 993cc890 none of these landings got past the wait (the gate's 4, exit 9).
        p2 = finding(2, "[P2] Cite the source", "change.txt:1-1")
        review = self.local_review(self.head, [p2], correctness="patch is incorrect")
        advisory = self.local_review(self.head, reviewer="claude-code-review")
        h8 = self.head[:8]
        other = hashlib.sha256(Path(advisory).read_bytes()).hexdigest()
        for name, rewrite, code, phrase in (
                ("revoked", lambda record, digest: f"printf 'Adjudication: revoked\\n' >> {q(record)}", 2,
                 f"#{PR} local review adjudication adjudication.md does not adjudicate #{PR} at {h8}"),
                ("its Finding line removed", lambda record, digest: f"printf 'Adjudication: local review %s for #%s at %s\\n' {digest} {PR} {h8} > {q(record)}", 9,
                 "1 of the 1 P2 and P3 findings of review file 1 have no disposition"),
                ("bound to another listed file", lambda record, digest: f"printf 'Adjudication: local review %s for #%s at %s\\n' {other} {PR} {h8} > {q(record)}", 2,
                 f"#{PR} local review adjudication adjudication.md names another review file than at its first read: stop")):
            with self.subTest(case=name):
                record, digest = self.adjudication(review, findings=[p2])
                code_, out, log = self.land(self.nas, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=f"{review}:{advisory}",
                                            LOCAL_REVIEW_ADJUDICATION=record, FAKE_GH_HOOK_ON="api users/*", FAKE_GH_HOOK=rewrite(record, digest))
                self.assertEqual((code_, self.merge_calls(log)), (code, []), out)
                self.assertIn(phrase, out)
                self.assertIn(f"#{PR} local review adjudication adjudication.md names #{PR} at {h8} and a listed review file", out, "the early check passed")
                if code == 9:
                    self.assertIn("at the final gate: stop", out)
                    self.assertEqual(len(self.gate_calls(log)), 3, "the wait and the call before the validation passed")

    def test_squash_body_file_is_the_body_and_its_text_comes_first_beside_a_waiver_or_an_adjudication(self):
        # SQUASH_BODY_FILE, ported from the CC's copy: alone it is passed as --body-file (cli v2.102.0 pkg/cmd/pr/merge/merge.go:177), and
        # nothing is read for the body. gh takes --body or --body-file, never both (merge.go:138-143), so beside a waiver or an adjudication
        # the body is the file's text, read once, a blank line and that line, and the body GitHub offers is not read. At 993cc890 the
        # variable was not read: the merges named no body, or the offered body and the waiver line.
        body = self.dir / f"squash-body-{next(self.counter)}.md"
        body.write_text("Land the change.\n\nThe corrected claim.\n", encoding="utf-8")
        h8, text = self.head[:8], "Land the change.\\n\\nThe corrected claim.\\n\\n"
        p2 = finding(2, "[P2] Cite the source", "change.txt:1-1")
        review = self.local_review(self.head, [p2], correctness="patch is incorrect")
        record, digest = self.adjudication(review, findings=[p2])
        real = {"FAKE_REAL_PYTHON": sys.executable}  # the real gate decides a local review set; the waiver's landing asks the canned one
        cases = [
            # #1075 (the co-op's codex review and Astra's P2-1): alone too, the merge takes the snapshot checked when the body is built
            # (--body-file at ca6f880b, which gh reads again when the merge call starts)
            ("alone, with a local review", {**real, "LOCAL_REVIEWS": self.local_review(self.head)},
             self.body_merge("Land the change.\\n\\nThe corrected claim.")),
            ("with the waiver", {}, self.body_merge(f"{text}Waiver: local reviews for #{PR} at {h8} (LOCAL_REVIEW_WAIVER)")),
            ("with an adjudication", {**real, "LOCAL_REVIEWS": review, "LOCAL_REVIEW_ADJUDICATION": record},
             self.body_merge(f"{text}Adjudication: local review {digest} for #{PR} at {h8} (LOCAL_REVIEW_ADJUDICATION)")),
        ]
        for name, extra, merge in cases:
            with self.subTest(case=name):
                code, out, log = self.land(self.nas, SQUASH_BODY_FILE=str(body), **extra)
                self.assertEqual((code, self.merge_calls(log)), (0, [merge]), out)
                self.assertFalse([line for line in log if "viewerMergeBodyText" in line], "the file takes the offered body's place")
                self.assertNotIn(str(self.dir), out)
        with self.subTest(case="the file is gone when the body is built"):
            gone = self.dir / f"squash-body-{next(self.counter)}.md"
            gone.write_text("Land the change.\n", encoding="utf-8")
            code, out, log = self.land(self.nas, SQUASH_BODY_FILE=str(gone), FAKE_VALIDATE_HOOK=f"rm -f {q(gone)}")
            self.assertEqual((code, self.merge_calls(log)), (7, []), out)
            self.assertIn(f"#{PR} SQUASH_BODY_FILE could not be read when the squash body is built (path withheld): stop, nothing merged", out)
            self.assertNotIn(str(self.dir), out)

    def test_squash_body_file_that_is_not_a_readable_non_empty_regular_file_stops_with_2_before_any_call(self):
        # The CC's copy :40-41: "-" would make gh read standard input (pkg/cmdutil/file_input.go:8-15), and every value that is not a
        # readable, non-empty regular file stops before the lock and any call; a set but empty value too (the CC's copy took it for unset,
        # and the merge fell back to the default body). At 993cc890 the variable was not read and each landing merged.
        import fcntl
        empty = self.dir / f"squash-body-{next(self.counter)}.md"
        empty.write_text("", encoding="utf-8")
        stop = f"#{PR} SQUASH_BODY_FILE is set but is not a readable, non-empty file (path withheld): stop, nothing merged"
        for name, value in (("-", "-"), ("a missing file", str(self.dir / "absent-body.md")), ("an empty file", str(empty)),
                            ("a directory", str(self.dir)), ("a set but empty value", "")):
            with self.subTest(case=name):
                code, out, log = self.land(self.nas, SQUASH_BODY_FILE=value, draft=True, merge_state="BEHIND")
                self.assertEqual((code, out, log), (2, stop, []))
        path = self.lock_path(self.nas)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, out, log = self.land(self.nas, SQUASH_BODY_FILE="-")
        self.assertEqual((code, out, log), (2, stop, []), "the check comes before the lock")

    def test_uet_refuses_the_nas_only_variables_when_set_before_the_lock_and_any_call(self):
        # The CC's read of #1075: codex_gate.py decides with LOCAL_REVIEW_ADJUDICATION wherever it is set, and uet_land.sh runs it too, without
        # nas's binding check or a squash body that records it; either variable can be inherited, for example from a nas landing in the same
        # shell. uet_land.sh stops on each when it is SET, an empty value included (${VAR+x}), before the lock and any call. At 25a9b48e each
        # of these landings merged: the valid record on the gate's adjudicated 0, the others with the variable unread.
        import fcntl
        p2 = finding(2, "[P2] Cite the source", "change.txt:1-1")
        review = self.local_review(self.head, [p2], correctness="patch is incorrect")
        record, _ = self.adjudication(review, findings=[p2])
        body = self.dir / f"squash-body-{next(self.counter)}.md"
        body.write_text("Land the change.\n", encoding="utf-8")

        def stop(variable):
            return f"#{PR} {variable} is set, but it is nas-only (a nas_land.sh input): stop, nothing merged"
        cases = [
            ("a valid adjudication record, with the local review it decides", "LOCAL_REVIEW_ADJUDICATION",
             {"LOCAL_REVIEWS": review, "LOCAL_REVIEW_ADJUDICATION": record, "FAKE_REAL_PYTHON": sys.executable}),
            ("an empty adjudication value", "LOCAL_REVIEW_ADJUDICATION", {"LOCAL_REVIEW_ADJUDICATION": ""}),
            ("a valid body file", "SQUASH_BODY_FILE", {"SQUASH_BODY_FILE": str(body)}),
            ("an empty body file value", "SQUASH_BODY_FILE", {"SQUASH_BODY_FILE": ""}),
        ]
        for name, variable, extra in cases:
            with self.subTest(case=name):
                code, out, log = self.land(self.uet, draft=True, merge_state="BEHIND", **extra)
                self.assertEqual((code, out, log), (2, stop(variable), []), "one line, and no call of any kind")
        with self.subTest(case="the landing lock held"):
            path = self.lock_path(self.uet)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as held:
                fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                code, out, log = self.land(self.uet, SQUASH_BODY_FILE="")
            self.assertEqual((code, out, log), (2, stop("SQUASH_BODY_FILE"), []), "the refusal comes before the lock")
        with self.subTest(case="the control: neither set, the same uet landing merges"):
            code, out, log = self.land(self.uet)
            self.assertEqual((code, len(self.merge_calls(log))), (0, 1), out)

    # ------------------------------------------------------------------------------------------ #1075 at ca6f880b: the Claude read, the local review, Astra
    def test_a_record_holding_a_nul_byte_stops_nas_before_any_gate_call(self):
        # The Claude read's P3-1: lg_text dropped the NUL byte and the gate did not, so the two read different last Adjudication lines. Here
        # the NUL-prefixed line names the other listed file: at ca6f880b verdict_gate took it, the gate took the line before it, and the landing
        # merged with a squash body that names the other file.
        p2 = finding(2, "[P2] Cite the source", "change.txt:1-1")
        review = self.local_review(self.head, [p2], correctness="patch is incorrect")
        advisory = self.local_review(self.head, reviewer="claude-code-review")
        digest, other = (hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in (review, advisory))
        record, _ = self.adjudication(review, adjudication_text(digest, PR, self.head, [p2]) + chr(0)
                                      + f"Adjudication: local review {other} for #{PR} at {self.head[:8]}\n")
        code, out, log = self.land(self.nas, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=f"{review}:{advisory}", LOCAL_REVIEW_ADJUDICATION=record)
        self.assertEqual((code, self.merge_calls(log), self.gate_calls(log)), (2, [], []), out)
        self.assertIn(f"#{PR} local review adjudication adjudication.md holds a NUL byte, which this script and the gate would read apart: stop", out)
        self.assertNotIn(other, out)

    def test_nas_refuses_an_adjudication_on_the_waiver_path_before_any_call(self):
        # The Claude read's P3-4: with no local review set nothing reads the record, so a SET LOCAL_REVIEW_ADJUDICATION, an empty value
        # included (as uet_land.sh refuses it), stops before any call. At ca6f880b the waived landing merged and never read it.
        import fcntl
        p2 = finding(2, "[P2] Cite the source", "change.txt:1-1")
        record, _ = self.adjudication(self.local_review(self.head, [p2], correctness="patch is incorrect"), findings=[p2])
        stop = (f"#{PR} LOCAL_REVIEW_ADJUDICATION is set, but no local review is: an adjudication decides a local review (LOCAL_REVIEWS), "
                "never a waived landing: stop, nothing merged")
        for name, value in (("a valid record", record), ("an empty value", "")):
            with self.subTest(case=name):
                code, out, log = self.land(self.nas, LOCAL_REVIEW_ADJUDICATION=value, draft=True, merge_state="BEHIND")
                self.assertEqual((code, out, log), (2, stop, []))
        with self.subTest(case="the landing lock held"):
            path = self.lock_path(self.nas)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as held:
                fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                code, out, log = self.land(self.nas, LOCAL_REVIEW_ADJUDICATION="")
            self.assertEqual((code, out, log), (2, stop, []), "the refusal comes before the lock")

    def test_the_gate_takes_only_the_recorded_review_when_both_files_change_before_its_final_call(self):
        # The co-op's codex review (P2 at codex_gate.py:391-392) and Astra's P2-2: the review file and the record are replaced together on the
        # final gate's statuses call, after its verdict_gate read the record and before its lg_gate. At ca6f880b the gate accepted review B,
        # and the landing merged with a squash body that records review A.
        p2 = finding(2, "[P2] Cite the source", "change.txt:1-1")
        review = self.local_review(self.head, [p2], correctness="patch is incorrect")
        record, first = self.adjudication(review, findings=[p2])
        replaced = self.dir / f"review-{next(self.counter)}.json"  # the same review in other bytes
        replaced.write_text(json.dumps(json.loads(Path(review).read_text(encoding="utf-8")), indent=1), encoding="utf-8")
        rebound = self.dir / f"adjudication-{next(self.counter)}.md"
        rebound.write_text(adjudication_text(hashlib.sha256(replaced.read_bytes()).hexdigest(), PR, self.head, [p2]), encoding="utf-8")
        count = self.dir / f"statuses-{next(self.counter)}.count"
        hook = (f'n=$(cat {q(count)} 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > {q(count)}; '
                f'[ "$n" -ne 2 ] || {{ cp {q(replaced)} {q(review)}; cp {q(rebound)} {q(record)}; }}')
        code, out, log = self.land(self.nas, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=review, LOCAL_REVIEW_ADJUDICATION=record,
                                   FAKE_GH_HOOK_ON="api repos/*/status*", FAKE_GH_HOOK=hook)
        self.assertEqual((code, self.merge_calls(log)), (9, []), out)
        self.assertEqual(count.read_text(encoding="utf-8").strip(), "2", "replaced on the final gate's statuses call")
        self.assertIn("review file 1 is not the file nas_land.sh recorded at the record's first read (LG_ADJUDICATION_SHA256)", out)
        self.assertIn("at the final gate: stop", out)
        self.assertNotIn(first, out)

    def test_squash_body_file_content_is_checked_before_any_call_when_the_body_is_built_and_at_the_final_gate(self):
        # The co-op's codex review (P2 at nas_land.sh:585-586) and Astra's P2-1: the start checked metadata alone, the standalone body went to
        # the merge as --body-file and the combined one through lg_text, so content that is not UTF-8, oversized, holds a NUL byte or was
        # emptied later reached the merge. One bounded reader takes the content before any call, when the body is built and at the final
        # gate. At ca6f880b each of these landings merged.
        real = {"FAKE_REAL_PYTHON": sys.executable, "LOCAL_REVIEWS": self.local_review(self.head)}

        def body(content):
            path = self.dir / f"squash-body-{next(self.counter)}.md"
            path.write_bytes(content)
            return path
        start = [
            ("bytes that are not UTF-8", bytes([0xff, 0x0a]), "is not UTF-8"),
            ("a code point above U+10FFFF", b"x" + bytes([0xf4, 0x90, 0x80, 0x80]), "is not UTF-8"),
            ("1 MiB", b"a" * (1 << 20), "is longer than 65536 bytes"),
            ("a NUL byte alone, beside the waiver", bytes(1), "holds a NUL byte"),
            ("white space alone", b" \n\t\n", "holds no text"),
        ]
        for name, content, why in start:
            with self.subTest(at="the start", case=name):
                extra = {} if "waiver" in name else real
                code, out, log = self.land(self.nas, SQUASH_BODY_FILE=str(body(content)), draft=True, merge_state="BEHIND", **extra)
                self.assertEqual((code, out), (2, f"#{PR} SQUASH_BODY_FILE {why} (path withheld): stop, nothing merged"))
                self.assertEqual([line for line in log if not line.startswith("python3 -I -c ")], [], "no call but the reader's own")
        later = [
            ("emptied while the merge is validated, alone", real, None, ": > {path}", "holds no text when the squash body is built"),
            ("emptied while the merge is validated, beside the waiver", {}, None, ": > {path}", "holds no text when the squash body is built"),
            ("emptied at the author lookup, after the body is built", real, "api users/*", ": > {path}", "holds no text at the final gate"),
            ("rewritten at the author lookup, still valid", real, "api users/*", "printf 'Another claim.' > {path}", "changed after the squash body was built"),
        ]
        for name, extra, on, action, why in later:
            with self.subTest(at="later", case=name):
                path = body(b"Land the change.\n")
                hooks = {"FAKE_VALIDATE_HOOK": action.format(path=q(path))} if on is None else {"FAKE_GH_HOOK_ON": on, "FAKE_GH_HOOK": action.format(path=q(path))}
                code, out, log = self.land(self.nas, SQUASH_BODY_FILE=str(path), **extra, **hooks)
                self.assertEqual((code, self.merge_calls(log)), (7, []), out)
                self.assertIn(f"#{PR} SQUASH_BODY_FILE {why} (path withheld): stop, nothing merged", out)
                self.assertNotIn(str(self.dir), out)

    def latin1_locale(self):
        """An ISO-8859-1 locale compiled with localedef into a scratch directory, as {"LOCPATH": …, "LC_ALL": …} (glibc reads locale data from
        LOCPATH, locale(7)), or None when it cannot be built here or Python does not take it as its stdout encoding."""
        localedef = shutil.which("localedef")
        if localedef is None:
            return None
        root = self.dir / f"locale-{next(self.counter)}"
        root.mkdir()
        subprocess.run([localedef, "-i", "en_US", "-f", "ISO-8859-1", str(root / "en_US.ISO-8859-1")], capture_output=True, timeout=120)
        settings = {"LOCPATH": str(root), "LC_ALL": "en_US.ISO-8859-1"}
        probe = subprocess.run([sys.executable, "-I", "-c", "import sys; print(sys.stdout.encoding)"], capture_output=True, text=True, timeout=30,
                               env={"PATH": os.environ["PATH"], **settings})
        return settings if probe.returncode == 0 and probe.stdout.strip() == "iso8859-1" else None

    def test_the_body_reader_writes_the_files_bytes_under_a_non_utf8_locale(self):
        # The co-op's re-review at f3f1cabe (P2 at nas_land.sh:95, the CC's adjudication: fix in this landing): the reader wrote the decoded
        # text through sys.stdout, whose encoding is the locale's (cpython v3.13.16 Doc/library/sys.rst:1838-1839), so under an ISO-8859-1
        # locale "é" came out as the one byte e9, and a character outside it ("€") ended the reader with nothing written (UnicodeEncodeError,
        # exit 1), while every check passed. LC_ALL=C does not show it: Python turns on its UTF-8 Mode for the C or POSIX locale
        # (Doc/library/os.rst:142-144; measured: utf8_mode 1, stdout utf-8), so the test compiles an ISO-8859-1 locale into a scratch
        # LOCPATH. At f3f1cabe the locale's cases and the landing failed; the C.UTF-8 cases are the control.
        settings = self.latin1_locale()
        if settings is None:
            self.skipTest("no ISO-8859-1 locale can be compiled here (localedef, the en_US source and the ISO-8859-1 charmap)")
        reader = re.search(r"^SB_READER='(.*)'$", self.nas.text, re.M).group(1)
        files = {"é": "Café claim.\r\n\n".encode("utf-8"), "€": "Euro € sign.\n".encode("utf-8")}
        for (name, content), (where, locale) in itertools.product(files.items(), (("ISO-8859-1", settings), ("C.UTF-8", {"LC_ALL": "C.UTF-8"}))):
            with self.subTest(text=name, locale=where):
                path = self.write("body.md", content)
                done = subprocess.run([sys.executable, "-I", "-c", reader, str(path), "65536"], capture_output=True, timeout=30,
                                      env={"PATH": os.environ["PATH"], **locale})
                self.assertEqual((done.returncode, done.stdout), (0, content.rstrip(b"\r\n")), "the file's bytes, its trailing line ends dropped")
        with self.subTest(case="a landing under the ISO-8859-1 locale, beside the waiver"):
            path = self.write("body.md", files["€"])
            code, out, log = self.land(self.nas, SQUASH_BODY_FILE=str(path), **settings)
            self.assertEqual((code, self.merge_calls(log)), (0, [self.body_merge(
                f"Euro € sign.\\n\\nWaiver: local reviews for #{PR} at {self.head[:8]} (LOCAL_REVIEW_WAIVER)")]), out)

    def test_the_squash_body_reads_the_waiver_or_the_adjudication_again_when_it_is_built(self):
        # The CC on the co-op's codex review: the line the squash body records is read and checked again when the body is built, not taken
        # from an earlier read; revoked while the merge is validated, the landing stops there, before the author lookup. At ca6f880b the final
        # gate stopped it, after the author lookup.
        p2 = finding(2, "[P2] Cite the source", "change.txt:1-1")
        review = self.local_review(self.head, [p2], correctness="patch is incorrect")
        record, _ = self.adjudication(review, findings=[p2])
        waiver = self.dir / f"waiver-{next(self.counter)}.md"
        waiver.write_text(f"Waiver: local reviews for #{PR} at {self.head[:8]}\n", encoding="utf-8")
        for name, extra, path, phrase in (
                ("the adjudication revoked", {"FAKE_REAL_PYTHON": sys.executable, "LOCAL_REVIEWS": review, "LOCAL_REVIEW_ADJUDICATION": record}, record,
                 f"#{PR} local review adjudication adjudication.md does not adjudicate #{PR} at {self.head[:8]}"),
                ("the waiver revoked", {"LOCAL_REVIEW_WAIVER": str(waiver)}, str(waiver), f"#{PR} local review waiver {waiver.name} does not waive #{PR}")):
            with self.subTest(case=name):
                code, out, log = self.land(self.nas, FAKE_VALIDATE_HOOK=f"printf 'Adjudication: revoked\\nWaiver: revoked\\n' >> {q(path)}", **extra)
                self.assertEqual((code, self.merge_calls(log)), (2, []), out)
                self.assertIn(phrase, out)
                self.assertEqual([line for line in log if line.startswith("gh api users/")], [], "it stopped before the author lookup")

    def test_the_adjudication_coverage_end_to_end_the_claude_read_asked_for(self):
        # The Claude read at ca6f880b: a record bound from the start to another LISTED file (verdict_gate takes it, the gate's binding check at
        # codex_gate.py:290-291 must stop it), an adjudicated landing through CODEX_LOCAL_REVIEW, and a record or a body file of mode 000.
        # Coverage: each gave the same answer at ca6f880b.
        p2 = finding(2, "[P2] Cite the source", "change.txt:1-1")
        review = self.local_review(self.head, [p2], correctness="patch is incorrect")
        advisory = self.local_review(self.head, reviewer="claude-code-review")
        h8 = self.head[:8]
        with self.subTest(case="bound from the start to another listed file"):
            record, _ = self.adjudication(review, adjudication_text(hashlib.sha256(Path(advisory).read_bytes()).hexdigest(), PR, self.head, [p2]))
            code, out, log = self.land(self.nas, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=f"{review}:{advisory}", LOCAL_REVIEW_ADJUDICATION=record)
            self.assertEqual((code, self.merge_calls(log), len(self.gate_calls(log))), (9, [], 1), out)
            self.assertIn(f"#{PR} local review adjudication adjudication.md names #{PR} at {h8} and a listed review file", out, "verdict_gate took it")
            self.assertIn(f"its last Adjudication line does not name the sha256 of review file 1, this pull request and the read head {h8}", out)
        with self.subTest(case="an adjudicated landing through CODEX_LOCAL_REVIEW"):
            record, digest = self.adjudication(review, findings=[p2])
            code, out, log = self.land(self.nas, FAKE_REAL_PYTHON=sys.executable, CODEX_LOCAL_REVIEW=review, LOCAL_REVIEW_ADJUDICATION=record)
            self.assertEqual((code, self.merge_calls(log)), (0, [self.body_merge(
                f"* the change\\n\\nAdjudication: local review {digest} for #{PR} at {h8} (LOCAL_REVIEW_ADJUDICATION)")]), out)
        for name, kind in (("a record of mode 000", "record"), ("a body file of mode 000", "body")):
            with self.subTest(case=name):
                if os.geteuid() == 0:
                    self.skipTest("root reads a file of mode 000")
                if kind == "record":
                    record, _ = self.adjudication(review, findings=[p2])
                    Path(record).chmod(0)
                    code, out, log = self.land(self.nas, FAKE_REAL_PYTHON=sys.executable, LOCAL_REVIEWS=review, LOCAL_REVIEW_ADJUDICATION=record)
                    self.assertEqual((code, self.merge_calls(log), self.gate_calls(log)), (2, [], []), out)
                    self.assertIn(f"#{PR} local review adjudication adjudication.md is unreadable: stop", out)
                else:
                    path = self.dir / f"squash-body-{next(self.counter)}.md"
                    path.write_text("Land the change.\n", encoding="utf-8")
                    path.chmod(0)
                    code, out, log = self.land(self.nas, SQUASH_BODY_FILE=str(path))
                    self.assertEqual((code, out, log), (2, f"#{PR} SQUASH_BODY_FILE is set but is not a readable, non-empty file (path withheld): stop, nothing merged", []))


# ---------------------------------------------------------------------------------------------- 8. review_normalize.py
ROLLOUT_ROOT = "/srv/review-example/cr-1/wt"  # synthetic: the worktree a codex review ran in (session_meta cwd)


ROLLOUT_BASE = "7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f"  # synthetic: the merge base the review request names (#1061 P1)


def review_prompt(branch="vendor-review/base-1", base=ROLLOUT_BASE):
    """The base-branch review request's prompt (openai/codex@rust-v0.162.1 codex-rs/prompts/src/review_request.rs:21)."""
    return (f"Review the code changes against the base branch '{branch}'. The merge base commit for this comparison is {base}. "
            f"Run `git diff {base}` to inspect the changes relative to {branch}. Provide prioritized, actionable findings.")


def prompt_line(text):
    """The prompt as the rollout holds it: an item_completed UserMessage (measured on the 6 local baseBranch rollouts on 2026-10-13)."""
    return {"timestamp": "2026-10-13T01:00:01Z", "type": "event_msg", "payload": {"type": "item_completed", "thread_id": "t-1", "turn_id": "1",
            "item": {"type": "UserMessage", "id": "u-1", "content": [{"type": "text", "text": text, "text_elements": []}]}}}


def rollout(*, output, target=None, commit=HEAD, version="0.162.1", cwd=ROLLOUT_ROOT, reviews=1, git=True, before=(), after=(), prompts=None):
    """A `codex review` session rollout as codex-cli 0.162.1 writes it (measured on 15 local rollouts on 2026-10-13: the first line is
    session_meta, the request, its prompt and the result are event_msg item_completed lines; openai/codex@rust-v0.162.1
    codex-rs/history/src/rollout_payload.rs:32-33, codex-rs/protocol/src/items.rs:173-183). `prompts` are the prompt texts between the
    request and the result (by default the one base-branch prompt)."""
    meta = {"id": "t-1", "timestamp": "2026-10-13T01:00:00Z", "cwd": cwd, "originator": "codex_exec", "cli_version": version}
    if git:
        meta["git"] = {"commit_hash": commit, "branch": None}
    lines = [{"timestamp": "2026-10-13T01:00:00Z", "type": "session_meta", "payload": meta}, *before]
    for _ in range(reviews):
        lines.append({"timestamp": "2026-10-13T01:00:00Z", "type": "event_msg", "payload": {"type": "item_completed", "thread_id": "t-1",
                      "turn_id": "1", "item": {"type": "EnteredReviewMode", "id": "e-1", "target": target or {"type": "baseBranch",
                      "branch": "vendor-review/base-1"}, "user_facing_hint": "changes against vendor-review/base-1"}}})
        lines += [prompt_line(text) for text in ([review_prompt()] if prompts is None else prompts)]
        lines.append({"timestamp": "2026-10-13T01:05:00Z", "type": "event_msg", "payload": {"type": "item_completed", "thread_id": "t-1",
                      "turn_id": "1", "item": {"type": "ExitedReviewMode", "id": "x-1", "review_output": output}}})
    return "".join(json.dumps(line) + "\n" for line in [*lines, *after])


def codex_finding(path, priority, start=10, end=12, title="[P1] A finding"):
    """A finding as ReviewFinding serializes it (protocol.rs:3525-3531), body included: the normalized file must drop it."""
    return {"title": title, "body": "A prose body the normalized file does not carry.", "confidence_score": 0.8, "priority": priority,
            "code_location": {"absolute_file_path": path, "line_range": {"start": start, "end": end}}}


def codex_output(findings=(), correctness="patch is incorrect"):
    return {"findings": list(findings), "overall_correctness": correctness, "overall_explanation": "Prose.", "overall_confidence_score": 0.7}


PLUGIN_AUTHOR = "lander-example"  # synthetic: the account that ran /code-review
PLUGIN_SINCE = "2026-10-13T01:00:00Z"


def plugin_comment(body, author=PLUGIN_AUTHOR, created="2026-10-13T01:10:00Z", edited=None, ident="6200000001"):
    """An IssueComment node as the normalizer's query reads it (schema.docs.graphql sha256 3ed09565…: author :21215, body :21225,
    createdAt :21240, fullDatabaseId :21260, lastEditedAt :21290)."""
    return {"fullDatabaseId": ident, "author": None if author is None else {"login": author}, "createdAt": created, "lastEditedAt": edited,
            "body": body}


def plugin_found(head, repo=NAS_REPO):
    """The plugin's found-issues comment in its format (anthropics/claude-plugins-official@f359d43b plugins/code-review/commands/code-review.md:52-72)."""
    return (f"### Code review\n\nFound 2 issues:\n\n1. The lock is released before the merge (bug due to `exec 9>&-` in lg_lock)\n\n"
            f"https://github.com/{repo}/blob/{head}/tools/landing/nas_land.sh#L56-L60\n\n"
            f"2. The README names the old slug (CLAUDE.md says \"keep the docs current\")\n\n"
            f"https://github.com/{repo}/blob/{head}/tools/landing/READ%20ME.md#L20\n\n"
            "\U0001f916 Generated with [Claude Code](https://claude.ai/code)\n\n"
            "<sub>- If this code review was useful, please react with \U0001f44d. Otherwise, react with \U0001f44e.</sub>\n")


PLUGIN_CLEAN = ("### Code review\n\nNo issues found. Checked for bugs and CLAUDE.md compliance.\n\n"
                "\U0001f916 Generated with [Claude Code](https://claude.ai/code)\n")


class ReviewNormalizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("landing_review_normalize", LANDING / "review_normalize.py")
        cls.normalize = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.normalize)
        gate = importlib.util.spec_from_file_location("landing_codex_gate_for_normalize", LANDING / "codex_gate.py")
        cls.gate = importlib.util.module_from_spec(gate)
        gate.loader.exec_module(cls.gate)

    def run_cli(self, argv, graphql=None, gh_rc=0):
        """The normalizer's main() with the out file in a scratch directory; `graphql` is what gh api graphql prints (a list of pages)."""
        calls = []

        def fake_run(cmd, capture_output=False, text=False, check=False):
            calls.append(cmd)
            self.assertEqual(cmd[:5], ["gh", "api", "graphql", "--paginate", "--slurp"])
            return subprocess.CompletedProcess(cmd, gh_rc, json.dumps(graphql) if gh_rc == 0 else f"gh: HTTP 502 {ADDRESS}", "")

        with tempfile.TemporaryDirectory(prefix="normalize-") as scratch:
            out_file = Path(scratch) / "review.json"
            argv = [part.replace("{dir}", scratch) for part in argv] + ["--out", str(out_file)]
            out = io.StringIO()
            with mock.patch.object(self.normalize.subprocess, "run", fake_run), contextlib.redirect_stdout(out):
                code = self.normalize.main(argv)
            written = json.loads(out_file.read_text(encoding="utf-8")) if out_file.exists() else None
            mode = stat.S_IMODE(out_file.stat().st_mode) if out_file.exists() else None
            leftovers = sorted(p.name for p in Path(scratch).iterdir() if p.name not in ("review.json", "rollout.jsonl"))
            line = out.getvalue().strip()
            self.assertNotIn(scratch, line, "no path is printed")
            self.assertEqual(leftovers, [], "nothing but the file is left")
            return code, line, written, mode, calls

    def codex(self, text, *extra):
        with tempfile.TemporaryDirectory(prefix="rollout-") as scratch:
            path = Path(scratch) / "rollout.jsonl"
            path.write_text(text, encoding="utf-8")
            return self.run_cli(["codex-review", "--rollout", str(path), *extra])

    def assert_gate(self, review, code):
        """The written file is a normalized review the gate reads with this outcome; a plugin file (the advisory arm) is read beside a
        clean codex-review of its head, the required arm. Returns the gate's line."""
        self.assertIsNone(self.gate.review_problem(review))
        files = [review] if review["reviewer"] == "codex-review" else [normalized(review["head_sha"], base=GATE_BASE), review]
        fact = f"{review['head_sha']}:{files[0]['base_sha']}"  # what lg_gate passes: the head's merge base (#1061 P1), here the file's own
        with tempfile.TemporaryDirectory(prefix="local-reviews-") as scratch:
            paths = []
            for number, item in enumerate(files):
                paths.append(Path(scratch) / f"review-{number}.json")
                paths[-1].write_text(json.dumps(item), encoding="utf-8")
            out = io.StringIO()
            with local_reviews_env({"LOCAL_REVIEWS": ":".join(map(str, paths))}), contextlib.redirect_stdout(out):
                self.assertEqual(self.gate.main("o/r", "7", review["head_sha"], fact), code)
            return out.getvalue().strip()

    # -- codex-review
    def test_a_codex_review_becomes_its_findings_without_bodies_relative_to_the_worktree(self):
        output = codex_output([codex_finding(f"{ROLLOUT_ROOT}/tools/landing/nas_land.sh", 1, 40, 44),
                               codex_finding(f"{ROLLOUT_ROOT}/README.md", 2, 3, 3, "[P2] Docs"), codex_finding(f"{ROLLOUT_ROOT}/x.py", 3, 1, 2, "[P3] Nit")])
        code, line, written, mode, calls = self.codex(rollout(output=output))
        self.assertEqual((code, mode, calls), (0, 0o600, []))
        self.assertEqual(written, {"reviewer": "codex-review", "reviewer_version": "codex-cli 0.162.1", "head_sha": HEAD, "base_sha": ROLLOUT_BASE,
                                   "completed": True, "overall_correctness": "patch is incorrect", "overall_confidence_score": 0.7,
                                   "findings": [{"priority": 1, "location": "tools/landing/nas_land.sh:40-44", "title": "[P1] A finding"},
                                                {"priority": 2, "location": "README.md:3-3", "title": "[P2] Docs"},
                                                {"priority": 3, "location": "x.py:1-2", "title": "[P3] Nit"}]})
        self.assertEqual(line, f"review_normalize: codex-review of {HEAD[:8]}: completed; overall_correctness 'patch is incorrect'; "
                               "findings P0 0, P1 1, P2 1, P3 1; written to review.json")
        self.assertNotIn("prose body", json.dumps(written))
        self.assert_gate(written, 4)

    def test_a_clean_codex_review_passes_the_gate_and_another_verdict_is_named_only_by_its_form(self):
        code, line, written, _, _ = self.codex(rollout(output=codex_output(correctness="patch is correct")), "--head", HEAD)
        self.assertEqual((code, written["completed"], written["findings"]), (0, True, []), line)
        self.assertIn("overall_correctness 'patch is correct'; findings P0 0, P1 0, P2 0, P3 0", line)
        self.assert_gate(written, 0)
        code, line, written, _, _ = self.codex(rollout(output=codex_output([codex_finding(f"{ROLLOUT_ROOT}/a.py", 2)], correctness="see /srv/x")))
        self.assertEqual((code, written["completed"], written["overall_correctness"]), (0, True, "see /srv/x"), "carried as Codex wrote it")
        self.assertIn("overall_correctness of another form (the gate stops on it)", line)
        self.assertNotIn("/srv/x", line)
        self.assertNotIn("/srv/x", self.assert_gate(written, 2), "the gate stops on it and prints no part of it")

    def test_codex_s_verdict_blocks_whatever_the_findings_and_its_confidence_is_carried_when_present(self):
        # The CC, 2026-10-13: rubric.md:85 fixes "patch is correct" | "patch is incorrect", the wire type is a free String (protocol.rs:3507).
        # A review that calls the patch incorrect with only P2 and P3 findings passed the gate at a6c8bf7c (the verdict was not carried).
        output = codex_output([codex_finding(f"{ROLLOUT_ROOT}/a.py", 2), codex_finding(f"{ROLLOUT_ROOT}/b.py", 3)], correctness="patch is incorrect")
        code, line, written, _, _ = self.codex(rollout(output=output))
        self.assertEqual((code, written["overall_correctness"], written["overall_confidence_score"]), (0, "patch is incorrect", 0.7), line)
        self.assertIn("patch is incorrect, P0 findings 0, P1 findings 0; a person decides; P2 findings 1, P3 findings 1", self.assert_gate(written, 4))
        without = {k: v for k, v in codex_output(correctness="patch is correct").items() if k != "overall_confidence_score"}
        code, line, written, _, _ = self.codex(rollout(output=without))
        self.assertEqual((code, "overall_confidence_score" in written), (0, False), line)
        self.assert_gate(written, 0)
        for score in ("high", True, None, [0.5]):
            with self.subTest(score=score):
                code, line, written, _, _ = self.codex(rollout(output={**codex_output(), "overall_confidence_score": score}))
                self.assertEqual((code, written), (1, None), line)
                self.assertIn("overall_confidence_score is not a finite number", line)

    def test_a_codex_review_without_a_structured_result_is_not_completed(self):
        # review_output null: interrupted (review.rs exit_review_mode(None)). Empty overall_correctness and no findings: the reviewer's JSON did
        # not parse, which review.rs:188-208 turns into findings [] (a finding without a priority does it: the rubric allows omitting it,
        # rubric.md:58 and :78, the struct requires it, protocol.rs:3525-3531). Either would pass as "no finding" if counted as completed.
        base = {"reviewer": "codex-review", "reviewer_version": "codex-cli 0.162.1", "head_sha": HEAD, "base_sha": ROLLOUT_BASE, "completed": False,
                "findings": []}
        for name, output, note, carried in (("interrupted", None, "the review was interrupted (review_output null)", {"overall_correctness": None}),
                                            ("the parse fallback", {"findings": [], "overall_correctness": "", "overall_explanation": "{\"findings\": [...]}",
                                                                    "overall_confidence_score": 0.0}, "the reviewer's JSON did not parse",
                                             {"overall_correctness": "", "overall_confidence_score": 0.0})):
            with self.subTest(case=name):
                code, line, written, _, _ = self.codex(rollout(output=output))
                self.assertEqual((code, written), (0, {**base, **carried}), line)
                self.assertIn(f"NOT completed (the gate stops on it); {note}", line)
                self.assertIsNone(self.gate.review_problem(written))
                with tempfile.TemporaryDirectory(prefix="local-reviews-") as scratch:
                    path = Path(scratch) / "r.json"
                    path.write_text(json.dumps(written), encoding="utf-8")
                    out = io.StringIO()
                    with local_reviews_env({"LOCAL_REVIEWS": str(path)}), contextlib.redirect_stdout(out):
                        self.assertEqual(self.gate.main("o/r", "7", HEAD, f"{HEAD}:{ROLLOUT_BASE}"), 2)
                    self.assertIn("did not complete", out.getvalue())

    def test_a_codex_rollout_that_cannot_give_one_review_of_the_pull_requests_change_is_refused(self):
        good = codex_output([codex_finding(f"{ROLLOUT_ROOT}/a.py", 1)])
        cases = [
            ("a commit review (one commit, not the pull request's change)", rollout(output=good, target={"type": "commit", "sha": HEAD, "title": "t"}),
             "the review's target is commit, not baseBranch"),
            ("uncommitted changes", rollout(output=good, target={"type": "uncommittedChanges"}), "the review's target is uncommittedChanges"),
            ("custom instructions", rollout(output=good, target={"type": "custom", "instructions": "x"}), "the review's target is custom"),
            ("a target of another form", rollout(output=good, target={"type": "a/../b"}), "the review's target is of another form"),
            ("two reviews in one rollout", rollout(output=good, reviews=2), "2 review requests and 2 review results"),
            ("no review", rollout(output=good, reviews=0), "0 review requests and 0 review results"),
            ("a line that is not JSON", rollout(output=good) + "{\"truncated\n", "line 5 of the rollout is not JSON"),
            # #1061 P1: the base the review compared HEAD with comes from the one request prompt between the request and the result
            ("no prompt", rollout(output=good, prompts=[]), "the review request names 0 merge bases, not one"),
            ("the fallback prompt, which names no merge base (review_request.rs:20)",
             rollout(output=good, prompts=["Review the code changes against the base branch 'vendor-review/base-1'. Start by finding the merge diff "
                                           "between the current branch and vendor-review/base-1's upstream"]), "names 0 merge bases"),
            ("two prompts", rollout(output=good, prompts=[review_prompt(), review_prompt(base=OTHER)]), "names 2 merge bases"),
            ("a prompt of another base branch", rollout(output=good, prompts=[review_prompt(branch="main")]),
             "the review request's base branch is not the one its target names"),
            ("a target without its branch (Astra's P1-2 regressions)", rollout(output=good, target={"type": "baseBranch"}),
             "the review request's base branch is not the one its target names"),
            ("a prompt after the result", rollout(output=good, prompts=[], after=[prompt_line(review_prompt())]), "names 0 merge bases"),
            # #1061 P3: a Legacy rollout (codex exec without paginated history) holds exited_review_mode events; it is refused, fail closed
            ("a Legacy rollout", rollout(output=good, reviews=0, after=[
                {"timestamp": "2026-10-13T01:00:00Z", "type": "event_msg", "payload": {"type": "entered_review_mode", "target": {"type": "baseBranch"}}},
                {"timestamp": "2026-10-13T01:05:00Z", "type": "event_msg", "payload": {"type": "exited_review_mode", "review_output": good}}]),
             "it is a Legacy rollout (entered_review_mode and exited_review_mode events, policy.rs:141-155)"),
            ("no session_meta", rollout(output=good).split("\n", 1)[1], "no session_meta line"),
            ("no commit in session_meta", rollout(output=good, git=False), "names no commit"),
            ("a short commit", rollout(output=good, commit=HEAD[:12]), "names no commit"),
            ("another --head", (rollout(output=good), "--head", OTHER), f"reviewed {HEAD[:8]}, not --head {OTHER[:8]}"),
            ("a version of another form", rollout(output=good, version="0.162.1 /srv/x"), "no cli_version of the usual form"),
            ("a priority of 4", rollout(output=codex_output([codex_finding("/a.py", 4)])), "finding 1 has no priority from 0 to 3"),
            ("a priority of null", rollout(output=codex_output([codex_finding("/a.py", None)])), "finding 1 has no priority from 0 to 3"),
            ("a priority of true", rollout(output=codex_output([codex_finding("/a.py", True)])), "finding 1"),
            ("no code_location", rollout(output=codex_output([{**codex_finding("/a.py", 1), "code_location": None}])), "finding 1"),
            ("a result that is not an object", rollout(output=["x"]), "the review result is not a review_output object"),
        ]
        for name, text, phrase in cases:
            with self.subTest(case=name):
                text, extra = (text[0], text[1:]) if isinstance(text, tuple) else (text, ())
                code, line, written, _, calls = self.codex(text, *extra)
                self.assertEqual((code, written, calls), (1, None, []), line)
                self.assertEqual(line, f"review_normalize: codex-review: refused: {line.split(': refused: ', 1)[1]}")
                self.assertIn(phrase, line)
                self.assertTrue(line.endswith("; nothing written"))
                self.assertNotIn("/srv/x", line)

    def test_a_codex_path_outside_the_worktree_keeps_its_form_with_the_home_directory_as_a_tilde(self):
        with mock.patch.dict(os.environ, {"HOME": "/srv/reviewer"}):
            self.assertEqual(self.normalize.where("/srv/reviewer/elsewhere/x.py", ROLLOUT_ROOT), "~/elsewhere/x.py")
            self.assertEqual(self.normalize.where("/opt/x.py", ROLLOUT_ROOT), "/opt/x.py")
            self.assertEqual(self.normalize.where(f"{ROLLOUT_ROOT}/a/b.py", ROLLOUT_ROOT + "/"), "a/b.py")
            self.assertEqual(self.normalize.where(f"{ROLLOUT_ROOT}-other/b.py", ROLLOUT_ROOT), f"{ROLLOUT_ROOT}-other/b.py")
            self.assertEqual(self.normalize.where("/a.py", "relative/cwd"), "/a.py")

    # -- claude-code-review
    def plugin(self, comments, head=HEAD, *, heads=None, since=PLUGIN_SINCE, author=PLUGIN_AUTHOR, gh_rc=0):
        pages = [{"data": {"repository": {"pullRequest": {"headRefOid": page_head, "comments": {
            "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": nodes}}}}} for page_head, nodes in zip(heads or [head], [comments] + [[]] * 9)]
        return self.run_cli(["claude-code-review", "--repo", NAS_REPO, "--pr", "1018", "--head", head, "--since", since, "--author", author,
                             "--reviewer-version", "code-review@claude-plugins-official@f359d43b; Claude Code 2.1.296"], graphql=pages, gh_rc=gh_rc)

    def test_the_plugins_issues_become_priority_1_findings_located_by_their_links(self):
        code, line, written, mode, calls = self.plugin([plugin_comment(plugin_found(HEAD))])
        self.assertEqual((code, mode), (0, 0o600), line)
        self.assertEqual(written, {"reviewer": "claude-code-review", "reviewer_version": "code-review@claude-plugins-official@f359d43b; Claude Code 2.1.296",
                                   "head_sha": HEAD, "completed": True, "findings": [
                                       {"priority": 1, "location": "tools/landing/nas_land.sh:56-60",
                                        "title": "The lock is released before the merge (bug due to `exec 9>&-` in lg_lock)"},
                                       {"priority": 1, "location": "tools/landing/READ ME.md:20",
                                        "title": "The README names the old slug (CLAUDE.md says \"keep the docs current\")"}]})
        self.assertEqual(line, f"review_normalize: claude-code-review of {HEAD[:8]}: completed; comment 6200000001; findings P0 0, P1 2, P2 0, P3 0; "
                               "written to review.json")
        self.assertEqual(calls[0][5:], ["-f", f"query={self.normalize.COMMENTS}", "-f", "owner=native-agent-stack", "-f", "repo=native-agent-stack",
                                        "-F", "pr=1018"])
        # the CC, 2026-10-13: the plugin arm is advisory until the review-replay addendum measures it: its two P1s are noted, not blocking
        self.assertIn("advisory, not blocking: claude-code-review issues 2 (each scored 80 or more, code-review.md:26)", self.assert_gate(written, 0))

    def test_the_plugins_no_issues_comment_is_a_completed_review_without_findings(self):
        code, line, written, _, _ = self.plugin([plugin_comment(PLUGIN_CLEAN.replace("\n", "\r\n"))])
        self.assertEqual((code, written["completed"], written["findings"]), (0, True, []), line)
        self.assertIn("claude-code-review issues 0", self.assert_gate(written, 0))

    def test_no_comment_of_this_run_is_a_review_that_did_not_complete(self):
        # The plugin posts nothing for a closed, draft, trivial or already reviewed pull request, nor when no issue scored 80
        # (plugins/code-review/README.md:157-167; code-review.md:11, :26): such a run gives completed false, which the gate notes as advisory
        # and does not stop on (the CC, 2026-10-13; at a6c8bf7c the gate stopped with 2).
        cases = [("no comment", []),
                 ("only a comment from before the run", [plugin_comment(PLUGIN_CLEAN, created="2026-10-13T00:59:59Z")]),
                 ("a comment by another account (anyone can post the format)", [plugin_comment(PLUGIN_CLEAN, author="someone-else")]),
                 ("a comment of a deleted account", [plugin_comment(PLUGIN_CLEAN, author=None)]),
                 ("a comment that only quotes the heading", [plugin_comment("As said:\n### Code review\nNo issues found.")])]
        for name, comments in cases:
            with self.subTest(case=name):
                code, line, written, _, _ = self.plugin(comments)
                self.assertEqual((code, written), (0, {"reviewer": "claude-code-review", "reviewer_version": written["reviewer_version"], "head_sha": HEAD,
                                                         "completed": False, "findings": []}), line)
                self.assertIn("NOT completed (advisory: the gate notes it); no code-review comment by --author since --since", line)
                self.assertIn("runs without a comment 1 (code-review.md:26, :11)", self.assert_gate(written, 0))

    def test_links_to_another_repository_do_not_bind_and_the_repository_matches_in_any_case(self):
        # Only links to the code of --repo bind the comment (a citation of another repository's file at its own commit does not count against
        # it), and GitHub's owner and repository names match in any case.
        body = plugin_found(HEAD, repo="Native-Agent-Stack/Native-Agent-Stack").replace(
            "\U0001f916", f"See also https://github.com/other-org/other/blob/{OTHER}/doc.md#L1-L2\n\n\U0001f916")
        code, line, written, _, _ = self.plugin([plugin_comment(body)])
        self.assertEqual((code, written["completed"], len(written["findings"])), (0, True, 2), line)

    def test_the_author_is_matched_without_regard_to_case_and_at_the_start_time(self):
        code, line, written, _, _ = self.plugin([plugin_comment(PLUGIN_CLEAN, author=PLUGIN_AUTHOR.upper(), created=PLUGIN_SINCE)])
        self.assertEqual((code, written["completed"]), (0, True), line)

    def test_a_plugin_comment_that_cannot_be_bound_to_the_head_or_read_is_refused(self):
        found = plugin_found(HEAD)
        cases = [
            ("the head moved during the review", dict(comments=[plugin_comment(found)], heads=[OTHER]), f"head is not --head {HEAD[:8]} now"),
            ("the head moved between pages", dict(comments=[plugin_comment(found)], heads=[HEAD, OTHER]), "head is not --head"),
            ("an edited comment", dict(comments=[plugin_comment(found, edited="2026-10-13T01:20:00Z")]), "was edited after it was posted"),
            ("two comments of the run", dict(comments=[plugin_comment(found), plugin_comment(PLUGIN_CLEAN, ident="6200000002")]),
             "2 code-review comments by --author since --since"),
            ("a count that does not match its list", dict(comments=[plugin_comment(found.replace("Found 2 issues", "Found 3 issues"))]),
             "announces 3 issues and lists 2"),
            ("a list out of order", dict(comments=[plugin_comment(found.replace("\n2. ", "\n3. "))]), "announces 2 issues and lists 1"),
            ("found no issues by count", dict(comments=[plugin_comment("### Code review\n\nFound 0 issues:\n")]), "announces 0 issues and lists 0"),
            ("another format", dict(comments=[plugin_comment("### Code review\n\nLooks fine to me.")]), "neither the plugin's found-issues list"),
            ("only the heading", dict(comments=[plugin_comment("### Code review")]), "neither the plugin's found-issues list"),
            ("gh fails", dict(comments=[], gh_rc=1), "gh api graphql exited 1 (its output withheld)"),
            # #1061 (the probe's finding 9): the comment is bound to --head by its full-SHA links, not by time alone
            ("links at another commit (a run that read an earlier head)", dict(comments=[plugin_comment(plugin_found(OTHER))]),
             f"the comment links to commit {OTHER[:8]}, not --head {HEAD[:8]}"),
            ("issues that link only to another repository", dict(comments=[plugin_comment(plugin_found(HEAD, repo="other-org/other"))]),
             "the comment's issues link to no commit of --repo"),
        ]
        for name, kwargs, phrase in cases:
            with self.subTest(case=name):
                code, line, written, _, _ = self.plugin(**kwargs)
                self.assertEqual((code, written), (1, None), line)
                self.assertIn(phrase, line)
                self.assertNotIn(ADDRESS, line, "nothing gh printed is shown")
                self.assertNotIn("lock is released", line, "no title is printed")

    def test_a_reply_that_is_not_the_pull_request_is_refused(self):
        for name, reply in (("no data", [{"errors": [{"message": ADDRESS}]}]), ("not pages", {"data": None}), ("a bad time", None)):
            with self.subTest(case=name):
                if reply is None:
                    code, line, written, _, _ = self.plugin([plugin_comment(PLUGIN_CLEAN, created="yesterday")])
                else:
                    code, line, written, _, _ = self.run_cli(["claude-code-review", "--repo", NAS_REPO, "--pr", "1", "--head", HEAD, "--since",
                                                              PLUGIN_SINCE, "--author", PLUGIN_AUTHOR, "--reviewer-version", "v"], graphql=reply)
                self.assertEqual((code, written), (1, None), line)
                self.assertIn("the GraphQL reply is not the pull request with its comments", line)
                self.assertNotIn(ADDRESS, line)

    def test_usage_errors_exit_2_and_write_nothing(self):
        base = ["claude-code-review", "--repo", NAS_REPO, "--pr", "1", "--head", HEAD, "--since", PLUGIN_SINCE, "--author", PLUGIN_AUTHOR,
                "--reviewer-version", "v"]
        bad = [("a short head", {"--head": HEAD[:8]}), ("a repository without its owner", {"--repo": "native-agent-stack"}),
               ("pr 0", {"--pr": "0"}), ("a login of another shape", {"--author": "a/b"}), ("a time without its offset", {"--since": "2026-10-13T01:00:00"}),
               ("an empty version", {"--reviewer-version": " "}), ("a version of two lines", {"--reviewer-version": "a\nb"})]
        for name, change in bad:
            with self.subTest(case=name):
                argv = list(base)
                for flag, value in change.items():
                    argv[argv.index(flag) + 1] = value
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                    self.run_cli(argv, graphql=[])
                self.assertEqual(raised.exception.code, 2)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            self.run_cli(["codex-review", "--rollout", "{dir}/r.jsonl", "--head", "abc"])
        self.assertEqual(raised.exception.code, 2)

    def test_a_refused_retry_removes_the_earlier_file_at_out(self):
        # #1061 (Astra's follow-up 1): at c999eee5 a refused run left an earlier run's completed review at --out, which the gate then read (0)
        with tempfile.TemporaryDirectory(prefix="normalize-retry-") as scratch:
            rollout_file, out_file = Path(scratch) / "rollout.jsonl", Path(scratch) / "review.json"
            for name, text, code in (("a good review", rollout(output=codex_output(correctness="patch is correct")), 0),
                                     ("a retry with a commit target", rollout(output=codex_output(), target={"type": "commit", "sha": HEAD}), 1)):
                with self.subTest(case=name):
                    rollout_file.write_text(text, encoding="utf-8")
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        got = self.normalize.main(["codex-review", "--rollout", str(rollout_file), "--out", str(out_file)])
                    self.assertEqual((got, out_file.exists()), (code, code == 0), out.getvalue())
            self.assertTrue(out.getvalue().strip().endswith("; nothing written; the older file at --out was removed"), out.getvalue())
            self.assertNotIn(scratch, out.getvalue())

    def test_an_unreadable_rollout_prints_one_line_with_the_error_class_and_no_path(self):
        code, line, written, _, _ = self.run_cli(["codex-review", "--rollout", "{dir}/absent.jsonl"])
        self.assertEqual((code, written), (1, None))
        self.assertEqual(line, "review_normalize: codex-review: refused: FileNotFoundError, details withheld; nothing written")

    def test_the_script_runs_isolated_as_the_readme_shows(self):
        with tempfile.TemporaryDirectory(prefix="normalize-") as scratch:
            path, out = Path(scratch) / "rollout.jsonl", Path(scratch) / "review.json"
            path.write_text(rollout(output=codex_output(correctness="patch is correct")), encoding="utf-8")
            done = subprocess.run([sys.executable, "-I", str(LANDING / "review_normalize.py"), "codex-review", "--rollout", str(path), "--out", str(out)],
                                  capture_output=True, text=True, timeout=30, env={"PATH": os.environ["PATH"], "LC_ALL": "C.UTF-8"})
            self.assertEqual((done.returncode, done.stderr), (0, ""), done.stdout)
            self.assertIn("completed; overall_correctness 'patch is correct'", done.stdout)
            self.assertNotIn(scratch, done.stdout)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["head_sha"], HEAD)


if __name__ == "__main__":
    unittest.main()
