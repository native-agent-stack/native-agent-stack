"""Public record contracts required by AGENTS.md's correction rule.

These checks read only published count tables and manifest metadata. They do
not open private receipts, client configuration or native model transcripts.
CPython's unittest, json, pathlib and re APIs own execution and parsing.
"""

import json
from pathlib import Path
import re
import subprocess
import unittest

from tests.test_local_pages_policy_grants import grants


ROOT = Path(__file__).resolve().parents[1]
DECISION = Path("docs/decisions/2026-10-10-daily-skill-invoke-rate.md")


def sections(text):
    """Sections of this repository's heading-delimited public record format."""
    headings = list(re.finditer(r"(?m)^(#{1,6}) (.+)$", text))
    result = []
    for index, heading in enumerate(headings):
        end = next((other.start() for other in headings[index + 1:]
                    if len(other.group(1)) <= len(heading.group(1))), len(text))
        result.append((heading.group(2), text[heading.end():end]))
    return result


class SkillCorrectionClaimsTests(unittest.TestCase):
    def test_landing_record_matches_native_grants_and_measured_source(self):
        tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True,
                                 capture_output=True, text=True).stdout.split("\0")
        catalog = json.loads((ROOT / "catalogs/landscape/manifest.json").read_text())
        expected = set(grants.inventory_paths([path for path in tracked if path], catalog["catalogs"]))
        policy = json.loads((ROOT / "tools/local-pages/source_policy.json").read_text())
        actual = {row["path"] for row in policy["architecture"]["architecture_inventory"]
                  if row["root"] == "repo"}
        self.assertEqual(expected, actual)

        text = (ROOT / DECISION).read_text()
        table = next(body for title, body in sections(text)
                     if title == "Correction source bindings and maintained regressions")
        row = next(line for line in table.splitlines()
                   if line.startswith("| Exact reviewed inventory proposal |"))
        table_count = re.search(r"sets each contain (\d+) paths", row)
        self.assertIsNotNone(table_count)
        self.assertEqual(int(table_count.group(1)), len(expected),
                         "The correction table must report the native integrated inventory")

        landing = next(body for title, body in sections(text)
                       if title == "2026-10-11 landing integration")
        expected_count = re.search(r"returns (\d+) expected paths", landing)
        actual_count = re.search(r"(\d+) actual reviewed repository grants", landing)
        self.assertIsNotNone(expected_count)
        self.assertIsNotNone(actual_count)
        self.assertEqual(int(expected_count.group(1)), len(expected))
        self.assertEqual(int(actual_count.group(1)), len(actual))

        delta = json.loads((ROOT / "blueprints/runtime-workers/openhands/evidence/"
                            "unclassified-gate-reads-20261011-skill-use-delta.json").read_text())
        source = re.search(r"measured parent/source input is\s+`([0-9a-f]{40})`", landing)
        self.assertIsNotNone(source, "Identify the measured input separately from future correction commits")
        self.assertEqual(source.group(1), delta["source_commit"])
        # Historical integration base captured with Git at the reviewed head.
        self.assertIn("The final CC-cued main base is `bcf55c457d057c71faceeab068bdd02017c43342`.", landing)

    def test_same_head_ablation_is_the_primary_comparison(self):
        primary = [(title, body) for title, body in sections((ROOT / DECISION).read_text())
                   if re.search(r"\bprimary\b", title, re.I)]
        self.assertEqual(len(primary), 1, "Name exactly one primary evidence section")
        title, body = primary[0]
        self.assertTrue(re.search(r"same[- ](?:head|checkout)", title + body, re.I),
                        "The primary comparison must identify its same-HEAD control")
        self.assertTrue("ABLATION-TABLE.md" in body,
                        "The same-HEAD ablation artifact must be primary")
        self.assertTrue(re.search(r"\b[a-f0-9]{64}\b", body),
                        "Bind the primary public artifact to its content hash")
        rows = [line.strip().strip("|").split("|") for line in body.splitlines()
                if line.strip().startswith("|")]
        comparisons = [row for row in rows if any(re.search(r"\d+/\d+", cell) for cell in row)]
        self.assertTrue(comparisons, "Keep public count-only primary evidence")
        for row in comparisons:
            self.assertEqual(len(row), 3, "A same-HEAD comparison has two arms, not three HEADs")
            counts = [re.search(r"(\d+)/(\d+)", cell) for cell in row[1:]]
            self.assertTrue(all(counts), "Report both arms as counts")
            left, right = [tuple(map(int, count.groups())) for count in counts]
            self.assertEqual(left[1], right[1], "Compare equal-size same-HEAD arms")
            self.assertTrue(all(0 <= used <= total and total > 0 for used, total in (left, right)))

    def test_ceiling_decision_resolves_to_its_dated_rationale(self):
        manifest = json.loads((ROOT / "adoption/skills/manifest.json").read_text())
        pointer = manifest["trial"].get("on_description_char_cap_decision")
        self.assertIsInstance(pointer, str, "The ceiling correction needs a dated decision pointer")
        relative, separator, fragment = pointer.partition("#")
        self.assertEqual(separator, "#", "Point to the rationale section")
        path = Path(relative)
        self.assertFalse(path.is_absolute())
        self.assertNotIn("..", path.parts)
        self.assertEqual(path.parts[:2], ("docs", "decisions"))
        self.assertRegex(path.name, r"^\d{4}-\d{2}-\d{2}-.+\.md$")
        matching = [(title, body) for title, body in sections((ROOT / path).read_text())
                    if re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", title).lower()) == fragment]
        self.assertEqual(len(matching), 1, "The ceiling pointer must resolve to one section")
        title, body = matching[0]
        self.assertRegex(title, r"^\d{4}-\d{2}-\d{2}\b")
        normalized = body.replace(",", "").replace("`", "")
        cap = manifest["trial"]["on_description_char_cap"]
        listed = sum(skill["description_chars"] for skill in manifest["skills"]
                     if skill["claude_listing"] == "on")
        self.assertTrue(str(cap) in normalized, "The rationale must name the current ceiling")
        self.assertTrue(str(listed) in normalized, "Explain the ceiling with the derived listed sum")
        self.assertTrue(re.search(r"\b(?:rais\w*|increas\w*)\b", body, re.I),
                        "Record the policy increase explicitly")

    def test_registered_claude_api_keeps_a_supported_bundled_baseline(self):
        manifest = json.loads((ROOT / "adoption/skills/manifest.json").read_text())
        registered = [skill for skill in manifest["skills"]
                      if skill["name"] == "claude-api" and skill.get("native_plugin")]
        self.assertEqual(len(registered), 1, "Check the separately tracked native plugin")
        baselines = [entry["reason"] for entry in manifest["excluded"]
                     if re.search(r"\bbundled\s+/?claude-api\b", entry["reason"], re.I)]
        self.assertTrue(baselines, "Separate registration must retain an explicit bundled baseline")
        reference = "\n".join(baselines)
        self.assertRegex(reference, r"anthropics/claude-code@[a-f0-9]{40}\b")
        self.assertTrue("CHANGELOG.md" in reference, "Name the supported native changelog")
        for release in ("2.1.69", "2.1.290"):
            self.assertRegex(reference, r"(?<![\d.])" + re.escape(release) + r"(?![\d.])")


if __name__ == "__main__":
    unittest.main()
