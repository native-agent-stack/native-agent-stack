"""The claude.ai plugin sync row agrees with the template and names its exception record.

docs/decisions/2026-10-15-claudeai-synced-plugins-exception.md: the 2026-10-04 row said the sync was "off on both
hosts", but the template never set syncClaudeAiPlugins, and Claude Code honours only false (settings reference,
syncClaudeAiPlugins), so the sync was on and four plugins loaded. The row must say what the template does.
"""
import importlib.util
import json
import os
import re
import string
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPOSITIONS = ROOT / "catalogs/foundation/upstream-surface-dispositions.json"
TEMPLATE = ROOT / "adoption/templates/claude.settings.template.json"
DECISION = "docs/decisions/2026-10-15-claudeai-synced-plugins-exception.md"
INVENTORY = ROOT / "evidence/artifacts/claudeai-synced-plugins-20261015/inventory.json"
LISTING_COST = INVENTORY.parent / "listing_cost.py"
GRAND = ROOT / "catalogs/landscape/grand-catalog-20261008.json"
SAMPLE = ROOT / "tests/fixtures/skill_usage/skill-doctor-sample.json"


class SyncedPluginsRowTests(unittest.TestCase):
    def row(self):
        rows = json.loads(DISPOSITIONS.read_text(encoding="utf-8"))["rows"]
        (row,) = [r for r in rows if r["key"] == "claude:setting:syncClaudeAiPlugins"]
        return row

    def template_sets_off(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        # Placeholder values do not matter here; safe_substitute leaves the JSON shape intact.
        settings = json.loads(string.Template(text).safe_substitute())
        return settings.get("syncClaudeAiPlugins") is False

    def test_the_row_says_off_only_when_the_template_sets_false(self):
        row = self.row()
        claims_off = row["disposition"] == "declined" or "off on both hosts" in row["reason"]
        self.assertEqual(claims_off, self.template_sets_off(), row)

    def test_an_unset_key_is_the_recorded_owner_synced_exception(self):
        if self.template_sets_off():
            self.skipTest("the template turns the sync off; the exception no longer applies")
        row = self.row()
        # 2026-10-15T05:07Z: the keep decision was superseded; the sync stays on by default and each plugin is disabled.
        self.assertEqual(row["disposition"], "default-on")
        self.assertIn("superseded in part on 2026-10-15T05:07Z", (ROOT / DECISION).read_text(encoding="utf-8"))
        self.assertIn("claude plugin disable <id> --scope user", (ROOT / DECISION).read_text(encoding="utf-8"))
        self.assertEqual(row["source"].rsplit(":", 1)[0], DECISION)
        decision = (ROOT / DECISION).read_text(encoding="utf-8")
        for plugin in json.loads(INVENTORY.read_text(encoding="utf-8"))["plugins"]:
            self.assertIn(f"`{plugin['name']}`", decision)
        self.assertIn("**Trigger:**", decision)


    def test_the_decision_states_the_measured_listing_cost(self):
        # Correction (2026-10-15T04:52Z, /skill-doctor at 2.1.300): the four synced plugins add about 8,450 tokens of skill
        # listing to every turn with 0 uses, so "nothing measurable" was wrong.
        decision = (ROOT / DECISION).read_text(encoding="utf-8")
        self.assertNotIn("cost nothing measurable", decision)
        cost = json.loads((INVENTORY.parent / "listing-cost.json").read_text(encoding="utf-8"))
        synced = sum(cost["by_source"][p]["listing_tokens"] for p in ("bigdata-com", "lseg", "daloopa", "cowork-plugin-management"))
        self.assertEqual(synced, cost["synced_total_tokens"])
        self.assertIn(f"{synced:,}", decision)


class RecordConsistencyTests(unittest.TestCase):
    """GPT read of #1138 at 9f63fc31 (P2 4 and 5): the record's current-state sentences must match what they describe."""

    def test_the_decision_names_the_rows_current_disposition(self):
        decision = (ROOT / DECISION).read_text(encoding="utf-8")
        named = re.findall(r"The row is now `([a-z-]+)`", decision)
        self.assertEqual(named, [SyncedPluginsRowTests.row(self)["disposition"]])

    def test_the_grand_catalog_rows_are_described_one_by_one(self):
        rows = json.loads(GRAND.read_text(encoding="utf-8"))["rows"]
        catalog = json.loads(INVENTORY.read_text(encoding="utf-8"))["catalog"]
        self.assertNotIn("all PROPOSED", catalog)
        for index in (447, 448, 449, 450):
            row = rows[index]
            self.assertIn("knowledge-work-plugins", json.dumps(row))
            described = f"{index} {row['slot']}"
            self.assertIn(described, catalog)
            if row["pin"]:
                self.assertIn(f"{described}: {row['disposition']}", catalog)
                self.assertIn(row["pin"]["version_or_commit"][:8], catalog)
            else:
                self.assertIn(f"{described}: {row['disposition']}, PROPOSED provisional "
                              f"{row['pending']['provisional_disposition']}, no pin", catalog)


class ListingCostScriptTests(unittest.TestCase):
    """GPT read of #1138 at 9f63fc31 (P2 1-3) and the local review (P2, listing_cost.py:30-32): the measurement script
    reads both output shapes, refuses failed or unmeasured runs without touching earlier evidence, and builds its probe
    with skill_usage.skill_doctor_argv()."""

    def run_script(self, stdout, code=0):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / "out.txt").write_text(stdout)
            fake = base / "claude"
            fake.write_text(f"#!{sys.executable}\nimport sys\n"
                            "if sys.argv[1:] == ['--version']:\n    print('2.1.300 (Claude Code)'); sys.exit(0)\n"
                            f"sys.stdout.write(open({str(base / 'out.txt')!r}).read()); sys.exit({code})\n")
            fake.chmod(0o755)
            out = base / "listing.json"
            out.write_text('{"sentinel": true}\n')
            env = dict(os.environ, PATH=f"{base}{os.pathsep}{os.environ.get('PATH', '')}")
            done = subprocess.run([sys.executable, str(LISTING_COST), str(out)], cwd=ROOT, env=env, capture_output=True,
                                  text=True, timeout=60)
            return done, out.read_text()

    def test_a_verbose_event_array_and_a_result_object_measure_the_same(self):
        events = json.loads(SAMPLE.read_text(encoding="utf-8"))
        result = [event for event in events if isinstance(event, dict) and event.get("type") == "result"][-1]
        array, array_out = self.run_script(json.dumps(events))
        single, single_out = self.run_script(json.dumps(result))
        self.assertEqual((array.returncode, single.returncode), (0, 0), (array.stderr, single.stderr))
        measured = json.loads(array_out)
        self.assertEqual(measured["kind"], "measurement")
        self.assertGreater(measured["all_total_tokens"], 0)
        self.assertEqual(measured["by_source"], json.loads(single_out)["by_source"])

    def test_a_failed_or_unmeasured_run_leaves_earlier_evidence(self):
        events = json.loads(SAMPLE.read_text(encoding="utf-8"))
        result = [event for event in events if isinstance(event, dict) and event.get("type") == "result"][-1]
        cases = {
            "api error, exit 1": (dict(result, subtype="success", is_error=True, result="API Error: 500"), 1),
            "error result, exit 0": (dict(result, is_error=True), 0),
            "no table": (dict(result, result="Unknown skill: skill-doctor"), 0),
            "a model turn": (dict(result, num_turns=1, total_cost_usd=0.004), 0),
        }
        for label, (event, code) in cases.items():
            with self.subTest(case=label):
                done, out = self.run_script(json.dumps(event), code=code)
                self.assertNotEqual(done.returncode, 0)
                self.assertEqual(out, '{"sentinel": true}\n')

    def test_the_probe_is_skill_usages_managed_mcp_compatible_argv(self):
        spec = importlib.util.spec_from_file_location("listing_cost", LISTING_COST)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        calls = []

        def runner(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 1, "", "")

        with tempfile.NamedTemporaryFile() as managed:
            self.assertEqual(module.main(["unused.json"], runner=runner, managed_paths=[managed.name]), 2)
            self.assertNotIn("--strict-mcp-config", calls[0])
            self.assertIn("--tools", calls[0])
            module.main(["unused.json"], runner=runner, managed_paths=["/nonexistent/managed-mcp.json"])
            self.assertIn("--strict-mcp-config", calls[1])

if __name__ == "__main__":
    unittest.main()
