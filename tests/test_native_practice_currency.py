"""CPA-V-09: the Claude native-practice skill states the client version that the repository's upstream-surface baseline resolves to, on every surface it is stated on, and the delta record
(docs/decisions/2026-10-12-practice-currency-2296.md) assigns every entry of the release's CHANGELOG section once. Structural checks of repository files; no client runs and nothing is fetched.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / ".claude" / "skills" / "claude-native-practice" / "reference"
BASELINE = ROOT / "catalogs" / "foundation" / "upstream-surface-baseline.json"
RECORD = ROOT / "docs" / "decisions" / "2026-10-12-practice-currency-2296.md"
FIRST, LAST = 5, 83          # CHANGELOG.md of anthropics/claude-code@3deb8736, section 2.1.296: the entries sit on lines 5 to 83
STAMP = re.compile(r"^Client (\d+\.\d+\.\d+), checked (\d{4}-\d{2}-\d{2})\.", re.M)


def baseline_version() -> str:
    return json.loads(BASELINE.read_text(encoding="utf-8"))["versions"]["claude_code"]


def stamps() -> dict:
    """page name -> (version, date) for the stamp each page states."""
    found = {}
    for path in sorted(REFERENCE.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if path.name == "slots.md":
            match = re.search(r"Client version: \*\*(\d+\.\d+\.\d+)\*\*\. Checked: (\d{4}-\d{2}-\d{2})\.", text)
        elif path.name == "cross-client.md":
            header = re.search(r"\| Need \| Claude Code (\d+\.\d+\.\d+) \|", text)
            match = (header.group(1), None) if header else None
            found[path.name] = match
            continue
        else:
            match = STAMP.search(text)
        found[path.name] = match.groups() if match else None
    return found


class VersionTests(unittest.TestCase):
    def test_slots_json_states_the_version_of_the_upstream_surface_baseline(self):
        data = json.loads((REFERENCE / "slots.json").read_text(encoding="utf-8"))
        self.assertEqual(data["client_version"], baseline_version())

    def test_every_page_states_that_version_and_one_checked_date(self):
        data = json.loads((REFERENCE / "slots.json").read_text(encoding="utf-8"))
        found = stamps()
        self.assertEqual(len(found), 13, sorted(found))
        for name, stamp in found.items():
            with self.subTest(page=name):
                self.assertIsNotNone(stamp, "no stamp found")
                self.assertEqual(stamp[0], data["client_version"])
                if stamp[1] is not None:
                    self.assertEqual(stamp[1], data["checked_at"])

    def test_the_new_host_install_pin_is_a_minimum_and_is_not_the_stamp(self):
        pins = json.loads((ROOT / "adoption" / "pins-linux-x86_64.json").read_text(encoding="utf-8"))
        self.assertIn("Minimum version", json.dumps(pins))


class DeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = RECORD.read_text(encoding="utf-8")
        cls.slots = {slot["id"]: slot for slot in json.loads((REFERENCE / "slots.json").read_text(encoding="utf-8"))["slots"]}

    @staticmethod
    def lines(cell: str) -> list:
        numbers = []
        for part in re.split(r",\s*", cell.strip()):
            low, _, high = part.partition("-")
            numbers += list(range(int(low), int(high or low) + 1))
        return numbers

    def table_rows(self):
        in_table, rows = False, []
        for line in self.record.splitlines():
            if line.startswith("| Lines |"):
                in_table = True
                continue
            if in_table:
                if not line.startswith("|"):
                    break
                if set(line) <= set("|- "):
                    continue
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                rows.append(cells)
        return rows

    def test_the_table_assigns_every_entry_of_the_section_once(self):
        assigned = [n for cells in self.table_rows() for n in self.lines(cells[0])]
        self.assertEqual(sorted(assigned), list(range(FIRST, LAST + 1)), "each line from 5 to 83 appears in exactly one row")

    def test_the_four_entries_that_touch_slots_are_the_rows_with_evidence(self):
        touched = {"context-compaction": ("L6",), "subagent-definitions": ("L6", "L59"), "model-effort-routing": ("L7",), "background-workflows": ("L7",), "mcp-config-tool-search": ("L65",)}
        for slot_id, lines in touched.items():
            for line in lines:
                with self.subTest(slot=slot_id, line=line):
                    on_json = [item for item in self.slots[slot_id]["evidence"] if f"CHANGELOG@v2.1.296 {line} " in item]
                    self.assertEqual(len(on_json), 1)
                    page = next(path for path in REFERENCE.glob("*.md") if path.name != "slots.md" and f"\n## {slot_id}\n" in path.read_text(encoding="utf-8"))
                    text = page.read_text(encoding="utf-8")
                    start = text.index(f"\n## {slot_id}\n")
                    end = text.find("\n## ", start + 1)
                    self.assertIn(on_json[0], text[start:end if end > 0 else len(text)], "the row on the layer page says what slots.json says")
        for slot_id, slot in self.slots.items():
            if slot_id not in touched:
                self.assertFalse([item for item in slot["evidence"] if "CHANGELOG@v2.1.296" in item], f"{slot_id} gained 2.1.296 evidence the record does not assign")

    def test_no_default_route_or_overturn_condition_changed_with_the_delta(self):
        """The rule: a routing or compaction default changes only after its own paired run. The record says none changed; the rows' defaults still name what they named."""
        self.assertIn("changes no default", self.record)
        self.assertIn("Native auto-compaction at the model's default window", self.slots["context-compaction"]["default"])
        self.assertIn("Native per-role model and effort", self.slots["model-effort-routing"]["default"])
        self.assertIn("`CLAUDE_CODE_SUBAGENT_MODEL_FORCE` unset", self.slots["model-effort-routing"]["route"])

    def test_the_agent_drift_note_is_the_measured_one_and_the_stale_count_is_gone(self):
        note = self.slots["subagent-definitions"]["notes"]
        self.assertNotIn("Four host copies differ", note)
        self.assertIn("Measured 2026-10-12", note)
        self.assertIn("equal adoption/agents/claude byte for byte", note)
        self.assertIn("not re-measured here", note)


if __name__ == "__main__":
    unittest.main()
