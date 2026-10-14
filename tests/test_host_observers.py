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
