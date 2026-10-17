"""The loopback-only listener census flags every listener that does not bind loopback, and never reports a broken census clean.

docs/decisions/2026-10-17-loopback-listener-census.md: loopback binds only, alert on any other listener. WSL's DNS tunnel
at 10.255.255.254:53 is the one exception.

The script:
- runs SS_ARGV (`ss -H -l -t -u -n -p`) with a timeout;
- exits 0 clean, 1 on a breach, and 2 on a census error. The tests assert those literal codes, never the script's own
  constants, so a swapped constant fails them;
- with --state-dir, keeps last.json and a breach record that holds exactly its run's violations, and names that record
  on stderr.

The unit runs it with StandardError=journal, so the alert's journal pointer leads to the record.
"""
import configparser
import contextlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/loopback_census.py"
SERVICE = ROOT / "adoption/templates/systemd/loopback-census.service"
TIMER = ROOT / "adoption/templates/systemd/loopback-census.timer"
spec = importlib.util.spec_from_file_location("loopback_census", SCRIPT)
census = importlib.util.module_from_spec(spec)
spec.loader.exec_module(census)

# [::1]%lo:632 is the shape ss 6.19.0 printed for a ::1 listener bound to device lo, sampled on 2026-10-17.
LOOPBACK_ONLY = """\
udp UNCONN 0 0 10.255.255.254:53 0.0.0.0:*
tcp LISTEN 0 1000 10.255.255.254:53 0.0.0.0:*
udp UNCONN 0 0 127.0.0.1:323 0.0.0.0:*
udp UNCONN 0 0 [::1]:323 [::]:*
tcp LISTEN 0 4096 127.0.0.53%lo:53 0.0.0.0:*
tcp LISTEN 0 4096 127.2.3.4:8080 0.0.0.0:*
tcp LISTEN 0 4096 127.0.0.1:23777 0.0.0.0:* users:(("hindsight-api",pid=2708854,fd=11))
tcp LISTEN 0 511 [::ffff:127.0.0.1]:23090 *:*
tcp LISTEN 0 128 [::1]:631 [::]:*
tcp LISTEN 0 128 [::1]%lo:632 [::]:*
"""
BREACHES = """\
tcp LISTEN 0 4096 0.0.0.0:8080 0.0.0.0:* users:(("python3",pid=4242,fd=3))
tcp LISTEN 0 4096 [::]:9090 [::]:*
udp UNCONN 0 0 *:5353 *:*
tcp LISTEN 0 128 192.168.1.20:8000 0.0.0.0:* users:(("node",pid=77,fd=19))
udp UNCONN 0 0 10.255.255.254:5353 0.0.0.0:*
tcp LISTEN 0 128 [::ffff:192.168.1.20]:8001 *:*
udp UNCONN 0 0 [fe80::1]%eth0:546 [::]:*
"""
BREACH_SET = {("tcp", "0.0.0.0:8080"), ("tcp", "[::]:9090"), ("udp", "*:5353"), ("tcp", "192.168.1.20:8000"),
              ("udp", "10.255.255.254:5353"), ("tcp", "[::ffff:192.168.1.20]:8001"), ("udp", "[fe80::1]%eth0:546")}
NON_UTF8 = b'tcp LISTEN 0 4096 0.0.0.0:8080 0.0.0.0:* users:(("py\xffthon",pid=9,fd=3))\n'
# The fake ss runs with PATH holding only its own directory (so the real ss stays unreachable), so its tools are absolute.
CAT, SLEEP = shutil.which("cat"), shutil.which("sleep")


def run(text, *extra, env=None):
    data = text if isinstance(text, bytes) else text.encode("utf-8")
    with tempfile.NamedTemporaryFile("wb", suffix=".txt", delete=False) as stream:
        stream.write(data)
    try:
        result = subprocess.run([sys.executable, str(SCRIPT), "--ss-output", stream.name, *extra], capture_output=True,
                                text=True, env=env)
    finally:
        Path(stream.name).unlink()
    return result.returncode, json.loads(result.stdout), result.stderr


def fake_ss(directory, body):
    """An executable `ss` in directory, so the census runs it from PATH instead of the real one."""
    path = Path(directory) / "ss"
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def run_with_path(directory, *extra):
    env = dict(os.environ, PATH=str(directory))
    result = subprocess.run([sys.executable, str(SCRIPT), *extra], capture_output=True, text=True, env=env)
    return result.returncode, json.loads(result.stdout), result.stderr


def records_in(state):
    return sorted((Path(state) / "breaches").glob("*.json"))


class RuleTests(unittest.TestCase):
    def test_loopback_listeners_and_the_wsl_dns_tunnel_pass(self):
        code, report, _ = run(LOOPBACK_ONLY)
        self.assertEqual((code, report["check"], report["listeners"], report["violations"]), (0, "loopback-census", 10, []))

    def test_every_non_loopback_listener_is_reported_and_fails_the_run(self):
        code, report, stderr = run(LOOPBACK_ONLY + BREACHES)
        self.assertEqual(code, 1)
        self.assertEqual({(v["proto"], v["address"]) for v in report["violations"]}, BREACH_SET)
        self.assertEqual(stderr.splitlines(), ["loopback census: 7 non-loopback listener(s)"])

    def test_the_owning_process_is_named_by_name_and_pid_only(self):
        _code, report, _ = run(BREACHES)
        processes = {v["address"]: v["process"] for v in report["violations"]}
        self.assertEqual(processes["0.0.0.0:8080"], "python3 pid=4242")
        self.assertEqual(processes["[::]:9090"], "unknown")

    def test_the_dns_tunnel_exception_is_its_address_and_port_only(self):
        for line in ("udp UNCONN 0 0 10.255.255.254:5353 0.0.0.0:*", "udp UNCONN 0 0 *:53 *:*",
                     "tcp LISTEN 0 4096 0.0.0.0:53 0.0.0.0:*", "udp UNCONN 0 0 192.168.1.20:53 0.0.0.0:*",
                     "udp UNCONN 0 0 10.255.255.253:53 0.0.0.0:*"):
            with self.subTest(line=line):
                self.assertEqual(run(line + "\n")[0], 1)
        self.assertEqual(run("tcp LISTEN 0 1000 10.255.255.254:53 0.0.0.0:*\n")[0], 0)
        # A device scope is stripped before the match, as for every address, so the scoped tunnel bind is allowed too. The
        # precursor flags this row, and the decision lists the difference.
        self.assertEqual(run("udp UNCONN 0 0 10.255.255.254%lo:53 0.0.0.0:*\n")[0], 0)

    def test_a_listener_listed_twice_is_reported_once(self):
        _code, report, _ = run(BREACHES.splitlines()[0] + "\n" + BREACHES.splitlines()[0] + "\n")
        self.assertEqual(len(report["violations"]), 1)

    def test_loopback_is_the_whole_of_127_slash_8_and_mapped_loopback_only(self):
        for host, expected in (("127.2.3.4", True), ("127.255.255.254", True), ("::1", True), ("::ffff:127.9.9.9", True),
                               ("::ffff:192.168.1.20", False), ("fe80::1", False), ("::", False), ("*", False)):
            with self.subTest(host=host):
                self.assertEqual(census.is_loopback(host), expected)

    def test_scoped_and_bracketed_addresses_parse(self):
        for address, expected in (("127.0.0.53%lo:53", ("127.0.0.53", "53")), ("[::1]%lo:631", ("::1", "631")),
                                  ("[fe80::1%eth0]:546", ("fe80::1", "546")), ("*:5353", ("*", "5353"))):
            with self.subTest(address=address):
                self.assertEqual(census.parse_address(address), expected)

    def test_a_non_utf8_listing_is_read_with_replacement_characters(self):
        code, report, _ = run(NON_UTF8)
        self.assertEqual((code, report["violations"][0]["process"]), (1, "py�thon pid=9"))


class CensusErrorTests(unittest.TestCase):
    def test_an_empty_listing_is_an_error_not_a_clean_pass(self):
        for text in ("", "\n\n", "   \n"):
            with self.subTest(text=repr(text)):
                code, report, stderr = run(text)
                self.assertEqual((code, report["error"]), (2, "ss listed no listener"))
                self.assertEqual(stderr.splitlines(), ["loopback census error: ss listed no listener"])

    def test_a_short_or_unparseable_line_is_an_error(self):
        for line in ("tcp LISTEN 0 4096", "tcp LISTEN 0 4096 127.0.0.1 0.0.0.0:*", "raw UNCONN 0 0 0.0.0.0:255 0.0.0.0:*"):
            with self.subTest(line=line):
                self.assertEqual(run(LOOPBACK_ONLY + line + "\n")[0], 2)

    def test_a_listing_of_only_bad_lines_reports_the_parse_error(self):
        code, report, _ = run("tcp LISTEN 0 4096\nraw UNCONN 0 0 0.0.0.0:255 0.0.0.0:*\n")
        self.assertEqual((code, report["error"]), (2, "unparseable ss line 'tcp LISTEN 0 4096' and 1 more"))

    def test_a_parse_error_still_reports_and_keeps_the_breaches_in_the_other_lines(self):
        breach, bad = BREACHES.splitlines()[0], "tcp LISTEN 0 4096 garbage 0.0.0.0:*"
        for text in (f"{breach}\n{bad}\n", f"{bad}\n{breach}\n"):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as directory:
                code, report, stderr = run(text, "--state-dir", directory)
                records = records_in(directory)
                self.assertEqual((code, report["error"]), (2, "unparseable local address 'garbage'"))
                self.assertEqual([v["address"] for v in report["violations"]], ["0.0.0.0:8080"])
                self.assertEqual(len(records), 1)
                self.assertEqual(json.loads(records[0].read_text())["violations"], report["violations"])
                self.assertEqual(stderr.splitlines(), [
                    "loopback census error: unparseable local address 'garbage'; 1 non-loopback listener(s) in the other lines",
                    f"loopback census: breach record {records[0]}"])

    def test_an_unreadable_saved_listing_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(SCRIPT), "--ss-output", str(Path(directory) / "missing")],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(json.loads(result.stdout)["error"].startswith("cannot read "))


class RealInvocationTests(unittest.TestCase):
    def test_the_census_runs_the_exact_ss_argv_from_path(self):
        self.assertEqual(census.SS_ARGV, ("ss", "-H", "-l", "-t", "-u", "-n", "-p"))
        with tempfile.TemporaryDirectory() as directory:
            argv = Path(directory) / "argv"
            fixture = Path(directory) / "fixture"
            fixture.write_text(LOOPBACK_ONLY, encoding="utf-8")
            fake_ss(directory, f'printf "%s\\n" "$0" "$@" > "{argv}"\n"{CAT}" "{fixture}"\n')
            code, report, _ = run_with_path(directory)
            recorded = argv.read_text(encoding="utf-8").split()
        self.assertEqual((code, report["listeners"]), (0, 10))
        self.assertEqual([Path(recorded[0]).name, *recorded[1:]], list(census.SS_ARGV))

    def test_a_failing_missing_unstartable_or_hung_ss_is_an_error(self):
        for body, mode, extra, error in (("exit 3\n", None, (), "ss exited 3"),
                                         (None, None, (), "ss is not installed"),
                                         ("exit 0\n", 0o644, (), "ss could not start: Permission denied"),
                                         (f'exec "{SLEEP}" 10\n', None, ("--ss-timeout", "1"), "ss did not finish within 1 s")):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as directory:
                if body is not None:
                    path = fake_ss(directory, body)
                    if mode is not None:
                        path.chmod(mode)
                code, report, _ = run_with_path(directory, *extra)
                self.assertEqual((code, report["error"]), (2, error))

    def test_a_diagnostic_on_stderr_is_an_error_even_when_ss_exits_0(self):
        # iproute2 6.19.0 exits 0 after a failed socket-table dump and reports it only on stderr (misc/ss.c:6276-6291,
        # :6302 at v6.19.0), so valid stdout from the other tables must not read as a clean census.
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture"
            fixture.write_text(LOOPBACK_ONLY, encoding="utf-8")
            fake_ss(directory, f'"{CAT}" "{fixture}"\necho "fopen(TCPDIAG_FILE): Permission denied" >&2\nexit 0\n')
            code, report, _ = run_with_path(directory)
        self.assertEqual(code, 2)
        self.assertEqual(report["error"],
                         "ss reported an error on stderr: 'fopen(TCPDIAG_FILE): Permission denied'")

    def test_a_non_utf8_ss_output_is_read_with_replacement_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture"
            fixture.write_bytes(NON_UTF8)
            fake_ss(directory, f'"{CAT}" "{fixture}"\n')
            code, report, _ = run_with_path(directory)
        self.assertEqual((code, report["violations"][0]["process"]), (1, "py�thon pid=9"))


class StateTests(unittest.TestCase):
    def test_a_breach_is_kept_in_a_dated_record_that_stderr_names(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            code, report, stderr = run(BREACHES, "--state-dir", str(state))
            records = records_in(state)
            self.assertEqual((code, len(records)), (1, 1))
            self.assertEqual(stderr.splitlines(), ["loopback census: 7 non-loopback listener(s)",
                                                   f"loopback census: breach record {records[0]}"])
            self.assertEqual(json.loads(records[0].read_text())["violations"], report["violations"])
            self.assertEqual(json.loads((state / "last.json").read_text()), dict(report, record=records[0].name))
            # The same breach again keeps the record and names it; a clean run replaces last.json and keeps the record.
            _code, _report, stderr = run(BREACHES, "--state-dir", str(state))
            self.assertEqual(records_in(state), records)
            self.assertIn(f"breach record {records[0]}", stderr)
            self.assertEqual(run(LOOPBACK_ONLY, "--state-dir", str(state))[0], 0)
            self.assertNotIn("record", json.loads((state / "last.json").read_text()))
            self.assertEqual(records_in(state), records)

    def test_a_different_set_of_violations_gets_its_own_record_and_stderr_names_it(self):
        with tempfile.TemporaryDirectory() as directory:
            run(BREACHES, "--state-dir", directory)
            first = records_in(directory)
            code, _report, stderr = run(BREACHES + "tcp LISTEN 0 4096 0.0.0.0:7070 0.0.0.0:*\n", "--state-dir", directory)
            records = records_in(directory)
            self.assertEqual((code, len(first), len(records)), (1, 1, 2))
            (new,) = set(records) - set(first)
            self.assertIn("0.0.0.0:7070", [v["address"] for v in json.loads(new.read_text())["violations"]])
            self.assertIn(f"breach record {new}", stderr)

    def test_the_named_record_holds_its_runs_violations_when_two_sets_share_a_stamp(self):
        # Two sets kept within one second are named <stamp>.json and <stamp>-2.json, and "-2" sorts first, so the record
        # to reuse cannot be found by sorting names.
        first = [{"proto": "tcp", "address": "0.0.0.0:8080", "process": "unknown"}]
        second = [{"proto": "tcp", "address": "0.0.0.0:9090", "process": "unknown"}]
        with tempfile.TemporaryDirectory() as directory:
            for step, violations in enumerate((first, second, second, first)):
                report = {"check": "loopback-census", "at": "2026-10-17T18:00:00Z", "listeners": 1, "violations": violations}
                record = census.keep(Path(directory), report)
                with self.subTest(step=step):
                    self.assertEqual(json.loads(record.read_text())["violations"], violations)
            self.assertEqual(len(records_in(directory)), 3)

    def test_an_error_is_written_to_last_json(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(run("", "--state-dir", directory)[0], 2)
            self.assertEqual(json.loads((Path(directory) / "last.json").read_text())["error"], "ss listed no listener")

    def test_a_state_dir_that_cannot_be_written_is_an_error_and_the_report_reaches_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            blocker = Path(directory) / "file"
            blocker.write_text("", encoding="utf-8")
            state = str(blocker / "state")
            code, report, stderr = run(BREACHES, "--state-dir", state)
            self.assertEqual(code, 2)
            self.assertEqual(set(report), {"check", "at", "listeners", "violations"})  # stdout keeps the normal report
            count, kept = stderr.splitlines()
            self.assertEqual(count, "loopback census: 7 non-loopback listener(s)")
            self.assertTrue(kept.startswith(f"loopback census error: state not kept in {state}: Not a directory; report "))
            self.assertIn('"0.0.0.0:8080"', kept)
            code, _report, stderr = run("", "--state-dir", state)
            self.assertEqual(code, 2)
            self.assertEqual(stderr.splitlines()[0], "loopback census error: ss listed no listener")
            self.assertIn("state not kept", stderr.splitlines()[1])


class FinalHandlerTests(unittest.TestCase):
    def test_an_unexpected_exception_exits_2_never_the_breach_code(self):
        with tempfile.TemporaryDirectory() as directory:
            listing = Path(directory) / "listing"
            listing.write_text(BREACHES, encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(census, "keep", side_effect=RuntimeError("boom")), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = census.main(["--ss-output", str(listing), "--state-dir", str(Path(directory) / "state")])
        self.assertEqual(code, 2)
        self.assertIn("loopback census error: unexpected RuntimeError: boom", err.getvalue())


def unit(path):
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    parser.read_string(path.read_text(encoding="utf-8"))
    return parser


class UnitTemplateTests(unittest.TestCase):
    def test_the_service_runs_the_script_with_a_state_dir_a_timeout_and_the_journal(self):
        service = unit(SERVICE)
        self.assertEqual(service["Unit"]["OnFailure"], "stack-alert@%n.service")
        expected = {"Type": "oneshot", "TimeoutStartSec": "60", "StateDirectory": "loopback-census",
                    "StandardOutput": "null", "StandardError": "journal", "UMask": "0077", "NoNewPrivileges": "true",
                    "ExecStart": "/usr/bin/python3 @REPOSITORY@/scripts/loopback_census.py --state-dir %S/loopback-census"}
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(service["Service"][key], value)
        # Timer-triggered oneshots in this directory carry no [Install] section; the timer carries it.
        self.assertNotIn("Install", service.sections())

    def test_the_timer_starts_the_census_every_five_minutes_and_installs_into_timers_target(self):
        timer = unit(TIMER)
        for key, value in {"OnBootSec": "2min", "OnUnitActiveSec": "5min", "AccuracySec": "30s",
                           "Unit": "loopback-census.service"}.items():
            with self.subTest(key=key):
                self.assertEqual(timer["Timer"][key], value)
        self.assertEqual(timer["Install"]["WantedBy"], "timers.target")

    def test_the_header_ships_the_check_cutover_and_activation_steps(self):
        header = SERVICE.read_text(encoding="utf-8")
        for step in ("systemctl --user show -p LoadState --value stack-alert@loopback-census.service.service",
                     "systemctl --user daemon-reload", "systemctl --user disable --now nhny-loopback-census.timer",
                     "systemctl --user enable --now loopback-census.timer", "systemctl --user list-timers loopback-census.timer"):
            with self.subTest(step=step):
                self.assertIn(step, header)


if __name__ == "__main__":
    unittest.main()
