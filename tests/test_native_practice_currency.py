"""The Claude native-practice skill states the client version it was checked against on every surface it is stated on, and the delta
record (docs/decisions/2026-10-15-practice-currency-2300.md) assigns every CHANGELOG entry between 2.1.295 and 2.1.300 exactly once.
Ported from #1053 (CPA-V-09), which covered 2.1.296 alone; that record supersedes #1053's.

The version the skill must state is the upstream-surface baseline's (catalogs/foundation/upstream-surface-baseline.json,
versions.claude_code), never older than RECORD_CLIENT. On 2026-10-15 the baseline still said 2.1.296 (#1155, open, re-baselines it at
2.1.300) while `claude --version` printed 2.1.300, the client the record read the CHANGELOG for, so the check takes the newer of the two.
Once the baseline is at or past 2.1.300 it is plain equality with the baseline: a later re-baseline fails here until the skill is checked
against that release. Structural checks of repository files; no client runs and nothing is fetched.
"""

import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / ".claude" / "skills" / "claude-native-practice" / "reference"
BASELINE = ROOT / "catalogs" / "foundation" / "upstream-surface-baseline.json"
RECORD = ROOT / "docs" / "decisions" / "2026-10-15-practice-currency-2300.md"
RECORD_CLIENT = "2.1.300"  # `claude --version` on 2026-10-15, and the newest section of the CHANGELOG the record read
PIN = "anthropics/claude-code@94506ff0d3bd9185f1752da36e968775021fb48f"
PIN_SHA256 = "8c6fdbbd692bd9b2e108e9946948aa77200b6c8ffec4f807ea9c8cee92545139"
# CHANGELOG.md at PIN: the lines each section's entries sit on. 2.1.297 and 2.1.298 have no section there.
SECTIONS = {"2.1.300": (5, 92), "2.1.299": (96, 285), "2.1.296": (289, 367)}
CATEGORIES = ("touches", "adjacent", "no slot: pure bug fix", "no slot: out of scope")
STAMP = re.compile(r"^Client (\d+\.\d+\.\d+), checked (\d{4}-\d{2}-\d{2})\.", re.M)
SLOT = re.compile(r"`([a-z0-9-]+)`(?: \(overlap (#\d+(?:, #\d+)*)\))?")
EVIDENCE = "CHANGELOG@v2.1.300 L{} "


def version_key(version: str) -> tuple:
    return tuple(int(part) for part in version.split("."))


def baseline_version() -> str:
    return json.loads(BASELINE.read_text(encoding="utf-8"))["versions"]["claude_code"]


def expected_version() -> str:
    return max(baseline_version(), RECORD_CLIENT, key=version_key)


def stamps() -> dict:
    """page name -> (version, date) for the stamp each page states."""
    found = {}
    for path in sorted(REFERENCE.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if path.name == "slots.md":
            match = re.search(r"Client version: \*\*(\d+\.\d+\.\d+)\*\*\. Checked: (\d{4}-\d{2}-\d{2})\.", text)
        elif path.name == "cross-client.md":
            header = re.search(r"\| Need \| Claude Code (\d+\.\d+\.\d+) \|", text)
            found[path.name] = (header.group(1), None) if header else None
            continue
        else:
            match = STAMP.search(text)
        found[path.name] = match.groups() if match else None
    return found


def lines(cell: str) -> list:
    numbers = []
    for part in re.split(r",\s*", cell.strip()):
        low, _, high = part.partition("-")
        numbers += list(range(int(low), int(high or low) + 1))
    return numbers


def table(record: str, header: str) -> list:
    """The cells of each body row of the first table whose header line starts with `header`."""
    rows, inside = [], False
    for line in record.splitlines():
        if line.startswith(header):
            inside = True
            continue
        if inside:
            if not line.startswith("|"):
                break
            if set(line) <= set("|- "):
                continue
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def page_section(slot_id: str) -> str:
    """The section of the layer page that holds the slot's row."""
    page = next(path for path in REFERENCE.glob("*.md") if path.name != "slots.md" and f"\n## {slot_id}\n" in path.read_text(encoding="utf-8"))
    text = page.read_text(encoding="utf-8")
    start = text.index(f"\n## {slot_id}\n")
    end = text.find("\n## ", start + 1)
    return text[start:end if end > 0 else len(text)]


class VersionTests(unittest.TestCase):
    def test_slots_json_states_the_baseline_version_and_never_one_older_than_the_record_read(self):
        data = json.loads((REFERENCE / "slots.json").read_text(encoding="utf-8"))
        self.assertEqual(data["client_version"], expected_version())

    def test_every_page_states_that_version_and_one_checked_date(self):
        data = json.loads((REFERENCE / "slots.json").read_text(encoding="utf-8"))
        found = stamps()
        self.assertEqual(len(found), 13, sorted(found))
        for name, stamp in found.items():
            with self.subTest(page=name):
                self.assertIsNotNone(stamp, "no stamp found")
                self.assertEqual(stamp[0], expected_version())
                if stamp[1] is not None:
                    self.assertEqual(stamp[1], data["checked_at"])

    def test_the_new_host_install_pin_is_a_minimum_and_is_not_the_stamp(self):
        """A guard ported from #1053, true before and after: the install pin is a separate minimum and is not moved here."""
        pins = json.loads((ROOT / "adoption" / "pins-linux-x86_64.json").read_text(encoding="utf-8"))
        self.assertIn("Minimum version", json.dumps(pins))


class DeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A missing record reads as empty, so each check below fails on its own assertion rather than all at once in setup.
        cls.record = RECORD.read_text(encoding="utf-8") if RECORD.is_file() else ""
        cls.rows = table(cls.record, "| Lines |")
        cls.slots = {slot["id"]: slot for slot in json.loads((REFERENCE / "slots.json").read_text(encoding="utf-8"))["slots"]}

    def test_the_record_names_its_source_at_the_pin_and_the_record_it_supersedes(self):
        self.assertIn(PIN, self.record)
        self.assertIn(PIN_SHA256, self.record)
        self.assertIn("It supersedes the unmerged record of #1053", self.record)

    def test_the_table_assigns_every_entry_of_each_section_once_under_its_version(self):
        assigned = Counter()
        for cells in self.rows:
            self.assertIn(cells[1], SECTIONS, cells)
            low, high = SECTIONS[cells[1]]
            for number in lines(cells[0]):
                with self.subTest(line=number):
                    self.assertTrue(low <= number <= high, f"L{number} is not an entry of the {cells[1]} section")
                assigned[number] += 1
        expected = {number for low, high in SECTIONS.values() for number in range(low, high + 1)}
        self.assertEqual(set(assigned), expected, "each entry line appears in the table")
        self.assertEqual(sorted(number for number, count in assigned.items() if count > 1), [], "no entry line appears twice")

    def test_each_row_has_one_category_and_names_known_slots_unless_it_has_none(self):
        self.assertTrue(self.rows, "the record has a delta table")
        for cells in self.rows:
            with self.subTest(lines=cells[0]):
                self.assertIn(cells[2], CATEGORIES)
                if cells[2].startswith("no slot"):
                    self.assertEqual(cells[3], "none")
                    continue
                named = SLOT.findall(cells[3])
                self.assertTrue(named, "a touching or adjacent entry names its slot")
                for slot_id, _ in named:
                    self.assertIn(slot_id, self.slots)

    def test_the_counts_table_matches_the_assignments(self):
        counted = Counter()
        for cells in self.rows:
            counted[(cells[1], cells[2])] += len(lines(cells[0]))
        stated = {row[0]: row for row in table(self.record, "| Version | Section |")}
        self.assertEqual(sorted(stated), sorted([*SECTIONS, "2.1.297", "2.1.298", "All"]), "the counts table has a row per version and a total")
        for version, (low, high) in SECTIONS.items():
            with self.subTest(version=version):
                self.assertEqual(int(stated[version][2]), high - low + 1)
                self.assertEqual([int(cell) for cell in stated[version][3:7]], [counted[(version, category)] for category in CATEGORIES])
        for version in ("2.1.297", "2.1.298"):
            with self.subTest(version=version):
                self.assertEqual(stated[version][1:7], ["none", "0", "0", "0", "0", "0"])
        self.assertEqual(int(stated["All"][2]), sum(high - low + 1 for low, high in SECTIONS.values()))
        self.assertEqual([int(cell) for cell in stated["All"][3:7]], [sum(counted[(version, category)] for version in SECTIONS) for category in CATEGORIES])

    def test_each_entry_applied_here_is_evidence_on_its_row_and_on_its_page(self):
        applied = 0
        for cells in self.rows:
            if cells[2] != "touches":
                continue
            for slot_id, overlap in SLOT.findall(cells[3]):
                if overlap:
                    continue
                for number in lines(cells[0]):
                    applied += 1
                    with self.subTest(slot=slot_id, line=number):
                        on_json = [item for item in self.slots[slot_id]["evidence"] if EVIDENCE.format(number) in item]
                        self.assertEqual(len(on_json), 1)
                        self.assertIn(on_json[0], page_section(slot_id), "the row on the layer page says what slots.json says")
        self.assertEqual(applied, 13)

    def test_no_row_carries_evidence_from_this_delta_that_the_record_does_not_assign_to_it(self):
        """An overlap row may carry its entries once the open change that owns it lands; any other row may not."""
        allowed = {}
        for cells in self.rows:
            if cells[2] == "touches":
                for number in lines(cells[0]):
                    allowed.setdefault(number, set()).update(slot_id for slot_id, _ in SLOT.findall(cells[3]))
        self.assertTrue(allowed, "the record assigns the entries that touch slots")
        delta = {number for low, high in SECTIONS.values() for number in range(low, high + 1)}
        for slot_id, slot in self.slots.items():
            for item in slot.get("evidence") or []:
                for number in map(int, re.findall(r"CHANGELOG@v2\.1\.300 L(\d+) ", item)):
                    if number in delta:
                        with self.subTest(slot=slot_id, line=number):
                            self.assertIn(slot_id, allowed.get(number, set()))

    def test_no_default_changed_and_the_overturn_conditions_the_record_says_were_met_are_the_rows_own(self):
        """The record changes no default; route additions are proposed to the command center, not applied."""
        self.assertIn("this record changes no default", self.record)
        defaults = {
            "context-compaction": "Native auto-compaction at the model's default window",
            "background-workflows": "Dynamic Workflows (Workflow tool;",
            "mcp-config-tool-search": "Native MCP configuration with tool search at its default (tools deferred)",
            "hooks": 'Settings command hooks, with `onFailure: "block"` on each guard hook entry',
            "settings-permissions": "Native layered settings (managed > `--settings` > local > project > user) with deny-first rules",
            "checkpoints-rewind": "Native checkpointing (`/rewind`, Esc Esc) with Git as the permanent history",
        }
        for slot_id, text in defaults.items():
            with self.subTest(slot=slot_id):
                self.assertIn(text, self.slots[slot_id]["default"])
        met = {"context-compaction": "a release changes compaction", "background-workflows": "A release changes Workflow resume or limits",
               "settings-permissions": "a release changes precedence or rule evaluation"}
        for slot_id, condition in met.items():
            with self.subTest(slot=slot_id):
                self.assertIn(condition, self.slots[slot_id]["overturn_when"])
                self.assertIn("overturn condition", self.slots[slot_id]["notes"])


if __name__ == "__main__":
    unittest.main()
