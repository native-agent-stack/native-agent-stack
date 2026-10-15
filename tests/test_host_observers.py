"""The host observers' self-tests (synthetic data and loopback fakes only) and the PromQL test of the probe-confirmed silence expression."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "host-observers"
OBS = ROOT / "observability" / "host-observers"
SELFTESTS = ("host_observers_selftest", "alert_tools_selftest", "net_probe_selftest", "storm_snapshot_selftest", "storm_runq_selftest", "storm_snapshot_summary_selftest")


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SelfTests(unittest.TestCase):
    def test_each_selftest_passes(self):
        for name in SELFTESTS:
            with self.subTest(name):
                done = subprocess.run([sys.executable, "-I", str(TOOLS / f"{name}.py")], capture_output=True, text=True, timeout=900)
                self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-1000:])

    def test_storm_snapshot_selftest_holds_on_a_machine_without_the_sessions_cgroup(self):
        """A CI runner has no /sys/fs/cgroup/non-systemd. The selftest's live group check used to assert more than 50 processes,
        which is true only on the workstation, and failed on every runner (validate-shard-7 of PR 1115). Run the selftest against
        a copy of the tool whose default group is missing; it must pass on any machine. The mechanism it relies on is os.walk,
        which ignores a scandir error unless onerror is given and so yields nothing for a missing top (python/cpython@v3.13.16,
        tag commit cbc944f4bc59, Lib/os.py:321 and Lib/os.py:368-373)."""
        missing = "/sys/fs/cgroup/ns2604-test-missing-group"
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("storm_snapshot.py", "storm_snapshot_selftest.py"):
                text = (TOOLS / name).read_text()
                if name == "storm_snapshot.py":
                    patched = text.replace('GROUP_DEFAULT = "/sys/fs/cgroup/non-systemd"', f'GROUP_DEFAULT = "{missing}"')
                    self.assertNotEqual(patched, text, "the tool's default group line moved; update this test")
                    text = patched
                (Path(tmp) / name).write_text(text)
            self.assertFalse(Path(missing).exists())
            done = subprocess.run([sys.executable, "-I", str(Path(tmp) / "storm_snapshot_selftest.py")], capture_output=True, text=True, timeout=300)
            self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-1000:])

    def test_storm_runq_selftest_holds_on_a_machine_with_few_processes(self):
        """The run-queue selftest's live check asserted more than 50 processes, true only on a machine with a large process population: a small
        container or runner failed it with the observer working. Run the whole selftest inside a PID namespace that sees a handful of processes
        (skipped where an unprivileged namespace is not allowed; the selftest also rehearses a three-process machine on a fake tree everywhere)."""
        unshare = shutil.which("unshare")
        if not unshare:
            self.skipTest("unshare is not installed")
        wrap = [unshare, "--user", "--pid", "--fork", "--mount-proc"]
        probe = subprocess.run(wrap + ["sh", "-c", "ls /proc | grep -c '^[0-9]'"], capture_output=True, text=True, timeout=60)
        if probe.returncode != 0:
            self.skipTest("an unprivileged PID namespace is not available here: " + probe.stderr.strip()[:120])
        self.assertLess(int(probe.stdout.strip()), 20, "the namespace is meant to be a small machine")
        done = subprocess.run(wrap + [sys.executable, "-I", str(TOOLS / "storm_runq_selftest.py")], capture_output=True, text=True, timeout=300)
        self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-1000:])


class MutationRunnerTests(unittest.TestCase):
    """net_probe_selftest.py --mutate counted every non-zero exit of the suite as a caught fault, so a suite that could not run at all (a refused
    loopback socket) scored 8 of 8 (review of PR 1115). It must run the unchanged control first and refuse a score when the control does not pass."""

    def run_main(self, module, argv):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(out):
            rc = module.main()
        return rc, out.getvalue()

    def test_a_control_that_cannot_run_gives_no_score_and_a_non_zero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("net_probe_selftest.py", "net_probe.py"):
                text = (TOOLS / name).read_text()
                if name == "net_probe.py":
                    text += "\nraise RuntimeError('planted: the suite cannot run')\n"
                (Path(tmp) / name).write_text(text)
            done = subprocess.run([sys.executable, "-I", str(Path(tmp) / "net_probe_selftest.py"), "--mutate"], capture_output=True, text=True, timeout=300)
        self.assertNotEqual(done.returncode, 0, done.stdout)
        self.assertNotIn("planted faults caught", done.stdout)
        self.assertIn("control", done.stdout)

    def test_a_mutant_run_that_stops_outside_the_code_under_test_is_not_a_caught_fault(self):
        """After a passing control, a mutant run that stops in the suite's own setup (the loopback socket a fake server needs, here) says nothing about the mutant."""
        module = load("net_probe_selftest")
        calls = []

        def fake_run_suite(tools):
            calls.append(tools)
            if len(calls) == 1:
                return 0, "18 of 18 checks passed\n", ""
            return 1, "", ('Traceback (most recent call last):\n  File "/x/net_probe_selftest.py", line 41, in __init__\n    self.sock.bind(("127.0.0.1", 0))\n'
                           'PermissionError: [Errno 1] Operation not permitted\n')

        module.run_suite = fake_run_suite
        module.MUTANTS = [("a mutant", "import socket\n", "import socket\n")]
        rc, text = self.run_main(module, ["net_probe_selftest.py", "--mutate"])
        self.assertEqual(rc, 1, text)
        self.assertIn("BROKEN", text)
        self.assertIn("0 of 1 planted faults caught", text)

    def test_a_mutant_that_makes_the_code_under_test_raise_is_caught(self):
        module = load("net_probe_selftest")
        module.MUTANTS = [("a mutant that makes the module raise on import", "import socket\n", "import socket\nraise RuntimeError('planted')\n")]
        rc, text = self.run_main(module, ["net_probe_selftest.py", "--mutate"])
        self.assertEqual(rc, 0, text)
        self.assertIn("1 of 1 planted faults caught", text)

    def test_a_byte_preserving_replacement_is_reported_as_missed(self):
        module = load("net_probe_selftest")
        module.MUTANTS = [("a replacement that changes nothing", "import socket\n", "import socket\n")]
        rc, text = self.run_main(module, ["net_probe_selftest.py", "--mutate"])
        self.assertEqual(rc, 1, text)
        self.assertIn("MISSED", text)
        self.assertIn("0 of 1 planted faults caught", text)


class AlertMutationRunnerTests(unittest.TestCase):
    """alert_tools_selftest.py --mutate counted every non-zero exit of a mutant run as a caught fault once its control had passed, so a later loopback-server or socket failure unrelated to the planted fault
    scored as a detection (local review of PR 1115, 268928f0). It must tell an assertion failure, or a crash inside one of the three tools, from a run that never reached its summary or whose only
    failures are groups that crashed in the suite's own setup."""

    SUMMARY_FAIL = "7 of 9 checks passed in 7 groups, 2 FAILED\n"

    def run_with_output(self, module, rc, out):
        class Done:
            returncode, stdout, stderr = rc, out, ""

        with mock.patch.object(module.subprocess, "run", lambda *a, **k: Done):
            return module.run_mutant(module.MUTANTS[0])

    def test_failures_that_are_only_crashes_of_the_suites_own_setup_are_broken_not_caught(self):
        module = load("alert_tools_selftest")
        out = ("ok   [watch-live] a check\n"
               "FAIL [watch-live] group watch-live crashed :: PermissionError in socket.py: [Errno 1] Operation not permitted\n"
               "FAIL [replay-cli-fake-prometheus] group replay-cli-fake-prometheus crashed :: OSError in socketserver.py: [Errno 98] Address already in use\n" + self.SUMMARY_FAIL)
        name, verdict, _info = self.run_with_output(module, 1, out)
        self.assertEqual(verdict, "broken")

    def test_a_run_that_never_reaches_its_summary_is_broken(self):
        module = load("alert_tools_selftest")
        self.assertEqual(self.run_with_output(module, 1, "ok   [watch-live] a check\n")[1], "broken")
        self.assertEqual(self.run_with_output(module, -9, "")[1], "broken")

    def test_an_assertion_failure_is_caught(self):
        module = load("alert_tools_selftest")
        out = "ok   [watch-events] a\nFAIL [watch-events] the FIRING line is printed :: got nothing\n" + self.SUMMARY_FAIL
        self.assertEqual(self.run_with_output(module, 1, out)[1], "caught")

    def test_a_crash_inside_one_of_the_three_tools_is_caught(self):
        module = load("alert_tools_selftest")
        out = "FAIL [replay-sim] group replay-sim crashed :: NameError in alert_replay.py: name 'x' is not defined\n" + self.SUMMARY_FAIL
        self.assertEqual(self.run_with_output(module, 1, out)[1], "caught")

    def test_a_crash_in_the_test_code_on_an_exception_that_is_no_os_or_network_error_is_caught(self):
        """A mutant that changes the tool's output can make the test code index a list that is now empty: the group crashes, and the cause is the planted fault."""
        module = load("alert_tools_selftest")
        out = "FAIL [watch-events] group watch-events crashed :: IndexError in alert_tools_selftest.py: list index out of range\n" + self.SUMMARY_FAIL
        self.assertEqual(self.run_with_output(module, 1, out)[1], "caught")

    def test_a_crash_in_the_setup_beside_a_real_failure_is_caught_by_the_real_failure(self):
        module = load("alert_tools_selftest")
        out = ("FAIL [watch-live] group watch-live crashed :: PermissionError in socket.py: denied\n"
               "FAIL [watch-events] the label match checks the value :: got True\n" + self.SUMMARY_FAIL)
        self.assertEqual(self.run_with_output(module, 1, out)[1], "caught")

    def test_a_clean_run_is_missed(self):
        module = load("alert_tools_selftest")
        self.assertEqual(self.run_with_output(module, 0, "ok   [watch-events] a\n9 of 9 checks passed in 7 groups\n")[1], "missed")

    def test_a_suite_group_that_crashes_records_the_file_of_the_failing_frame(self):
        """The classifier reads the file name out of the crash line, so the suite must write it."""
        module = load("alert_tools_selftest")
        module.GROUPS = {"boom": lambda: (_ for _ in ()).throw(OSError("denied"))}
        module.RESULTS.clear()
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["alert_tools_selftest.py", "--only", "boom"]), contextlib.redirect_stdout(out):
            module.main()
        self.assertRegex(out.getvalue(), r"FAIL \[boom\] group boom crashed :: OSError in \S+\.py: denied")


class RuleAndUnitTests(unittest.TestCase):
    def test_silence_rule_uses_the_expression_the_promql_test_checks(self):
        expr = (OBS / "promtool" / "net-silent-confirmed.expr").read_text().strip()
        spec = json.loads((OBS / "grafana-rules" / "ns2604-net-silent-crit.json").read_text())
        query = next(d for d in spec["data"] if d["refId"] == "A")
        self.assertEqual(query["model"]["expr"], expr)
        self.assertIn(expr, (OBS / "promtool" / "net-silent-confirmed.test.yaml").read_text().replace("''", "'"))

    def test_rule_specs_keep_the_shape_the_rule_tool_requires(self):
        tool = load("grafana_rule_add")
        rules = [json.loads(p.read_text()) for p in sorted((OBS / "grafana-rules").glob("*.json"))]
        self.assertEqual(len(rules), 3)
        document = {"apiVersion": 1, "groups": [{"orgId": 1, "name": "g", "folder": "f", "interval": "1m", "rules": rules}]}
        self.assertEqual(tool.problems(document), [])
        for rule in rules:
            self.assertIn(rule["labels"]["severity"], ("CRIT", "WARN"))
            if rule["labels"]["severity"] == "CRIT":
                self.assertEqual(rule["labels"].get("notify"), "cc")

    def test_every_unit_runs_a_tool_that_exists_here(self):
        seen = set()
        for unit in sorted((OBS / "units").iterdir()):
            for tool in re.findall(r"host-observers/([A-Za-z0-9_]+\.py)", unit.read_text()):
                seen.add(tool)
                self.assertTrue((TOOLS / tool).is_file(), f"{unit.name} runs {tool}")
        self.assertEqual(seen, {"fsync_canary.py", "engine_delay_prom.py", "io_attribution_daemon.py", "net_probe.py", "alert_watch.py"})

    def test_units_are_idle_class_and_hold_no_credential(self):
        for unit in sorted((OBS / "units").glob("*.service")):
            text = unit.read_text()
            self.assertIn("CPUWeight=idle", text, unit.name)
            self.assertNotRegex(text, r"(?i)(password|token|secret|api[_-]?key)\s*=", unit.name)

    def test_probe_rule_is_gated_on_the_probe_being_fresh(self):
        """A probe that stopped after writing a failure leaves that gauge in the textfile, and node exporter keeps serving it. The rule that
        fires on a failing probe must read it only while the probe is fresh and leave a stale measurement to the stale-probe warning."""
        crit = json.loads((OBS / "grafana-rules" / "ns2604-net-probe-crit.json").read_text())
        stale = json.loads((OBS / "grafana-rules" / "ns2604-net-probe-stale-warn.json").read_text())
        expr = next(d for d in crit["data"] if d["refId"] == "A")["model"]["expr"]
        self.assertEqual(expr, (OBS / "promtool" / "net-probe-crit.expr").read_text().strip())
        self.assertIn(expr, (OBS / "promtool" / "net-probe-crit.test.yaml").read_text().replace("''", "'"))
        age_limit = next(d for d in stale["data"] if d["refId"] == "B")["model"]["conditions"][0]["evaluator"]["params"][0]
        # one definition of stale for the pair: the warning fires above the limit, the critical rule reads the measurement at or below it
        self.assertIn(f"time() - max(net_probe_last_run_timestamp_seconds) <= {age_limit}", expr)
        self.assertEqual(next(d for d in stale["data"] if d["refId"] == "B")["model"]["conditions"][0]["evaluator"]["type"], "gt")
        self.assertEqual(crit["noDataState"], "OK", "no data (a stale or absent probe) leaves the critical rule normal; the warning owns that case")

    def test_the_ci_correction_cites_its_pinned_source(self):
        """AGENTS.md, Code Review Rules, Corrections: a fix cites the upstream source, at the pinned version, for the mechanism it changes."""
        pin = "python/cpython@v3.13.16"
        for path in (TOOLS / "storm_snapshot_selftest.py", TOOLS / "README.md"):
            self.assertIn(pin, path.read_text(), path.name)
            self.assertIn("Lib/os.py:368-373", path.read_text(), path.name)

    def test_the_permission_fix_cites_its_pinned_source(self):
        """AGENTS.md, Code Review Rules, Corrections: the fchmod that keeps a rule file's mode under a restrictive umask cites the documentation of os.open (the umask is masked out of its mode) and os.fchmod, at
        their pin, next to the call (local review of PR 1115, 268928f0)."""
        text = (TOOLS / "grafana_rule_add.py").read_text()
        call = text.index("os.fchmod(fd, mode)")
        before = text[max(0, call - 1100):call]
        self.assertIn("python/cpython@v3.13.16", before)
        self.assertIn("Doc/library/os.rst:1272-1275", before)
        self.assertIn(":1027-1030", before)

    def test_the_mutation_runner_citations_name_their_reference_and_their_first_hand_measurement(self):
        for name in ("net_probe_selftest.py", "alert_tools_selftest.py"):
            text = (TOOLS / name).read_text()
            self.assertIn("trailofbits/skills", text, name)
            self.assertIn("configuration.md:134-141", text, name)
            self.assertIn("MutationRunnerTests", text, name)

    def test_promql_test_with_promtool(self):
        promtool = os.environ.get("PROMTOOL") or shutil.which("promtool")
        if not promtool:
            self.skipTest("promtool is not installed")
        files = sorted((OBS / "promtool").glob("*.test.yaml"))
        self.assertEqual([f.name for f in files], ["net-probe-crit.test.yaml", "net-silent-confirmed.test.yaml"])
        for path in files:
            with self.subTest(path.name):
                done = subprocess.run([promtool, "test", "rules", str(path)], capture_output=True, text=True, timeout=120)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
