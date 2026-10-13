#!/usr/bin/env python3
"""The routing README states the measurement that the decision record retains (CPA-V-12): the AFTER measurement is complete (the same-checkout hermetic ablation), a lifetime count of zero is zero observed calls and
not absence of demand, and the vendor suite is an optional re-run. The numbers it quotes are the record's and the baseline file's, read from them, so a number changed in one place fails here."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "adoption/skills/claude-routing/README.md"
RECORD = ROOT / "docs/decisions/2026-10-10-daily-skill-invoke-rate.md"
BASELINE = ROOT / "adoption/skills/claude-routing/trigger-baseline.json"


class RoutingReadmeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = " ".join(README.read_text(encoding="utf-8").split())
        cls.record = RECORD.read_text(encoding="utf-8")

    def test_the_readme_does_not_call_the_after_measurement_outstanding_or_the_demand_absent(self):
        """The audit's fail-first check: the README said that the native AFTER measurement remained to be done and that the six skills had no baseline demand; the record holds a completed ablation and says that zero
        observed calls do not establish absence of demand."""
        for phrase in ("AFTER measurement remains", "remains cc-native-practice-owned", "no baseline demand", "AFTER measurement is outstanding"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, self.readme)
        self.assertIn("does not establish absence of demand", self.readme)
        self.assertIn("does not establish absence of demand", " ".join(self.record.split()), "the record says it")

    def test_the_readme_quotes_the_retained_ablation_as_the_record_holds_it(self):
        """Every count of the record's same-HEAD table that the README quotes is read from the record's rows; the sessions and the arms are the record's sentence."""
        record = " ".join(self.record.split())
        self.assertRegex(record, r"128\s+sessions,\s+64\s+per\s+arm")
        self.assertIn("128 sessions, 64 per arm", self.readme)
        rows = {
            "security-audit, five phrasings, turn one": r"\| security-audit, five phrasings, turn one \| (\d+/\d+) \| (\d+/\d+) \|",
            "security-audit, five phrasings, invoked within three turns": r"\| security-audit, five phrasings, invoked within three turns \| (\d+/\d+) \| (\d+/\d+) \|",
            "security-best-practices indirect, turn one": r"\| security-best-practices indirect, turn one \| (\d+/\d+) \| (\d+/\d+) \|",
            "near-miss negatives": r"\| Near-miss negatives, any skill invoked \| (\d+/\d+) \| (\d+/\d+) \|",
        }
        for label, pattern in rows.items():
            with self.subTest(row=label):
                found = re.search(pattern, self.record)
                self.assertIsNotNone(found, f"the record's table has the row: {label}")
                hidden, listed = found.groups()
                phrase = f"{hidden} in both arms" if hidden == listed else f"{hidden} against {listed}"
                self.assertIn(phrase, self.readme, "the README states the row's counts as the pair the record holds")
        self.assertIn("p=0.008", self.readme)
        self.assertIn("Fisher two-sided p=0.008", self.record.replace("\n", " "))

    def test_the_readme_quotes_the_baseline_snapshot_as_the_file_holds_it(self):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        audit = next(row for row in baseline["skills"] if row["name"] == "security-audit")
        self.assertIn(f"{audit['invoked']}/{audit['runs']} with {audit['invoked_in_first_turn']}/{audit['runs']} in turn one", self.readme)
        for row in baseline["skills"]:
            if row["name"] != "security-audit":
                self.assertEqual((row["invoked"], row["runs"], row["status"]), (3, 3, "wired"), row["name"])
        self.assertIn("six targets at 3/3", self.readme)

    def test_the_vendor_suite_is_kept_as_an_optional_rerun(self):
        self.assertIn("## Optional re-run with the vendor harness", README.read_text(encoding="utf-8"))
        self.assertIn("The ablation above is the retained measurement", self.readme)
        self.assertIn("This is 21 model runs. The lane prepares the suite and never launches it.", self.readme)
        self.assertIn("stage_routing_eval.py", self.readme, "the staging command is kept")

    def test_the_readme_links_the_section_of_the_record_that_exists(self):
        link = re.search(r"\(\.\./\.\./\.\./docs/decisions/2026-10-10-daily-skill-invoke-rate\.md#([a-z0-9-]+)\)", README.read_text(encoding="utf-8").replace("\n", " "))
        self.assertIsNotNone(link)
        headings = [re.sub(r"[^a-z0-9 -]", "", line[3:].lower()).replace(" ", "-") for line in self.record.splitlines() if line.startswith("## ")]
        self.assertIn(link.group(1), headings, "the anchor is a heading of the record")


if __name__ == "__main__":
    unittest.main()
