"""The host observers' self-tests (synthetic data and loopback fakes only) and the PromQL test of the probe-confirmed silence expression."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

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

    def test_promql_test_with_promtool(self):
        promtool = os.environ.get("PROMTOOL") or shutil.which("promtool")
        if not promtool:
            self.skipTest("promtool is not installed")
        done = subprocess.run([promtool, "test", "rules", str(OBS / "promtool" / "net-silent-confirmed.test.yaml")], capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
