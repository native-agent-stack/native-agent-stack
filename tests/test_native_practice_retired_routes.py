"""The claude-native-practice skill selects none of the Claude routes that the 2026-10-10 record retired.

docs/decisions/2026-10-10-retire-in-github-claude-review.md removed the three workflows that ran anthropics/claude-code-action. Before this change the skill's `github-action` row was still the default for Claude work in GitHub and `pr-review-pre-cue` ran "in Actions through #909",
so a session that loaded the skill was told to use a route the API refuses ("credit balance is too low", the command center's correction #141).

What counts as selecting a retired route, on the three surfaces a session reads (reference/slots.json, the reference/slots.md index and the layer pages) and on every other text of the skill folder:
- a field that says what to use (`default`, `alternatives`, and `route` of a live slot; the Default, Alternatives and Route lines of a page) never names a retired route;
- every other text names one only inside a sentence (a string) or an item (a list) that itself says it is retired, so a retired word elsewhere in the field excuses nothing;
- only the dated snapshots are not read: the `retired` block of a slot, the `primary_sources` of a retired slot, and the Primary sources and Former default bullets of a page. A source's `native_mechanism` on a live slot is the
  repository's own present-tense mapping and is read.
Every parser keeps duplicates (a stale second row or section is a violation) and reads every line, not only the labelled bullets. Repository-text checks only: no workflow or client runs here.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / ".claude/skills/claude-native-practice/reference"
RECORD = "docs/decisions/2026-10-10-retire-in-github-claude-review.md"
WORKFLOWS = ("claude-pr-review.yml", "claude-pr-toolkit-review.yml", "harness-audit.yml")
# The names the record uses for the retired route (checked against the record below), then what the retired rows and notes said without naming a file: the run "in Actions", "through #909", "under WIF", and the managed app,
# which the command center's ruling of 2026-10-10 retired with them and the record does not name.
NAMES = ("claude-code-action", "claude-pr-review", "claude-pr-toolkit-review", "harness-audit", "claude-code-github-action")
PATTERNS = {name: re.compile(re.escape(name), re.I) for name in NAMES}
PATTERNS.update({
    "in Actions": re.compile(r"\bin (?:GitHub )?Actions\b", re.I),
    "through Actions": re.compile(r"\bthrough (?:GitHub )?Actions\b", re.I),
    "through #909": re.compile(r"through #909"),
    "under WIF": re.compile(r"\bunder WIF\b", re.I),
    "the managed Code Review app": re.compile(r"managed (?:Claude )?Code Review|Code Review GitHub App", re.I),
})
SELECTING = ("default", "alternatives")
SKIPPED_KEYS = ("id", "layer_id", "status", "retired", "primary_sources_total")
RETIRED_KEYS = ("on", "record", "correction", "scope", "workflows", "former_default", "revisit_when")
STATUS_CELL = {"default-scoped": "default (scoped)", "recommendation": "recommendation (owner's choice)"}
SAYS_RETIRED = re.compile(r"\bretire(?:d|ment)\b", re.I)
SENTENCE = re.compile(r"(?<=[.;])\s+(?=[A-Z`\[(\-])")
ROW = re.compile(r"^\| \[([a-z0-9-]+)\]\([^)]*\) \| (.+)$")
BULLET = re.compile(r"^- \*\*(.+?):\*\* (.*)$")


def flatten(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(flatten(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(flatten(item) for item in value)
    return ""


def units(value) -> list[str]:
    """The claims of a field: each item of a list and each sentence of a string."""
    if isinstance(value, dict):
        return [unit for item in value.values() for unit in units(item)]
    if isinstance(value, (list, tuple)):
        return [unit for item in value for unit in units(item)]
    if isinstance(value, str):
        return [part for part in SENTENCE.split(value) if part.strip()]
    return []


def judge(label: str, kind: str, value) -> list[str]:
    """`select`: the field names no retired route at all. `explain`: a retired route is named only in a unit that says it is retired."""
    found = []
    if kind == "select":
        text = flatten(value)
        found += [f"{label} selects the retired route {name!r}" for name, pattern in PATTERNS.items() if pattern.search(text)]
        return found
    for unit in units(value):
        for name, pattern in PATTERNS.items():
            if pattern.search(unit) and not SAYS_RETIRED.search(unit):
                found.append(f"{label} names the retired route {name!r} in a unit that does not say it is retired: {unit[:80]!r}")
    return found


def slot_fields(slot: dict):
    """(label, kind, value) for every judged field of a slot."""
    retired = slot["status"] == "retired"
    for key, value in slot.items():
        if key in SKIPPED_KEYS:
            continue
        if key == "primary_sources":
            if not retired:
                for index, source in enumerate(value):
                    yield f"{slot['id']}.primary_sources[{index}].native_mechanism", "explain", source.get("native_mechanism", "")
            continue
        selecting = key in SELECTING or (key == "route" and not retired)
        yield f"{slot['id']}.{key}", "select" if selecting else "explain", value


def slot_violations(slot: dict) -> list[str]:
    return [found for label, kind, value in slot_fields(slot) for found in judge(label, kind, value)]


def retired_violations(slot: dict, record_text: str) -> list[str]:
    """A retired slot carries its dated block; a block on any other slot is a stale marker."""
    block = slot.get("retired")
    if slot["status"] != "retired":
        return [f"{slot['id']} carries a retired block but has status {slot['status']!r}"] if block else []
    if not isinstance(block, dict):
        return [f"{slot['id']} is retired and has no retired block"]
    found = [f"{slot['id']}.retired lacks {key!r}" for key in RETIRED_KEYS if not block.get(key)]
    if not re.fullmatch(r"\d{4}-\d\d-\d\d", str(block.get("on"))):
        found.append(f"{slot['id']}.retired.on is not a date")
    if not (ROOT / str(block.get("record"))).is_file():
        found.append(f"{slot['id']}.retired.record is not a file of this repository")
    if not slot["default"].startswith("None"):
        found.append(f"{slot['id']} is retired but its default does not say there is none")
    found += [f"{slot['id']}.retired names {name}, which the record does not" for name in block.get("workflows", []) if name not in record_text]
    return found


def other_json_violations(data: dict) -> list[str]:
    """The top-level texts of slots.json that are not slots: the selection rule, the status vocabulary and the cross-client block."""
    return [found for key in ("selection_rule", "status_values", "cross_client") for found in judge(f"slots.json.{key}", "explain", data.get(key))]


def index_parts(text: str):
    """The table rows of slots.md as (id, status, default, overturn), duplicates kept, and every other line."""
    rows, other = [], []
    for line in text.splitlines():
        match = ROW.match(line)
        if match is None:
            other.append(line)
            continue
        status, default, overturn = match.group(2).split(" | ", 2)
        rows.append((match.group(1), status, default, overturn[:-2] if overturn.endswith(" |") else overturn))
    return rows, other


def index_violations(text: str) -> list[str]:
    rows, other = index_parts(text)
    found = []
    ids = [row[0] for row in rows]
    found += [f"slots.md has more than one row for {slot_id}" for slot_id in sorted({i for i in ids if ids.count(i) > 1})]
    for slot_id, _status, default, overturn in rows:
        found += judge(f"{slot_id} index, Default", "select", default)
        found += judge(f"{slot_id} index, Overturn when", "explain", overturn)
    found += judge("slots.md text", "explain", [line for line in other if line.strip()])
    return found


def page_sections() -> list[tuple[str, str, str]]:
    """(page, section id, section text) of every layer page, duplicates kept; cross-client.md and slots.md are not layer pages."""
    sections = []
    for page in sorted(REFERENCE.glob("*.md")):
        if page.name in ("slots.md", "cross-client.md"):
            continue
        for section in page.read_text(encoding="utf-8").split("\n## ")[1:]:
            sections.append((page.name, section.split("\n", 1)[0].strip(), section))
    return sections


def section_fields(section: str) -> dict[str, str]:
    """Status and Default of the section's first line, and the first bullet of each label."""
    head = re.search(r"\*\*Status:\*\* (.+?)\. \*\*Default:\*\* (.*)", section)
    fields = {"Status": head.group(1), "Default": head.group(2)}
    for line in section.splitlines():
        match = BULLET.match(line)
        if match:
            fields.setdefault(match.group(1), match.group(2))
    return fields


def section_violations(slot_id: str, section: str) -> list[str]:
    """Every line of a section except the dated snapshots (the Primary sources and Former default bullets with their indented lines)."""
    retired = section_fields(section)["Status"] == "retired"
    found, snapshot = [], False
    for line in section.splitlines()[1:]:
        if line.startswith(("- **Primary sources**", "- **Former default")):
            snapshot = True
            continue
        if snapshot and line.startswith("  "):
            continue
        snapshot = False
        if not line.strip():
            continue
        head = re.match(r"\*\*Status:\*\* .+?\. \*\*Default:\*\* (.*)", line)
        if head:
            found += judge(f"{slot_id} page, Default", "select", head.group(1))
            continue
        bullet = BULLET.match(line)
        label, text = (bullet.group(1), bullet.group(2)) if bullet else ("line", line)
        selecting = label == "Alternatives, ranked" or (label == "Route" and not retired)
        found += judge(f"{slot_id} page, {label}", "select" if selecting else "explain", text)
    return found


def prose_violations(name: str, text: str) -> list[str]:
    return judge(name, "explain", [line for line in text.splitlines() if line.strip()])


# The rows as the skill carried them on 2026-10-09, before the retirement: the control that the checks see what they are meant to see.
BEFORE_ACTION = {
    "id": "github-action", "status": "default",
    "default": "anthropics/claude-code-action at commit 2dca132ff0e0c4094ce6048b422c6915a071210b (v1.0.247)",
    "route": "Workload identity federation only; dispatch-only or variable-gated jobs; explicit `--model` and `--effort`",
    "alternatives": ["Managed Claude Code Review (GitHub App)"],
    "notes": "Converged in all three selections (both families and the owner's sweep). Main moves from v1.0.245 when #892 lands.",
}
BEFORE_CUE = {
    "id": "pr-review-pre-cue", "status": "default",
    "default": "pr-review-toolkit pre-cue (pr-test-analyzer and silent-failure-hunter): locally in J8 and in Actions through #909",
    "route": "Runs before a landing cue; findings at confidence 80 or above go to the lane",
    "primary_sources": [{"native_mechanism": "Claude Code: pr-review-toolkit subagents run as the pre-cue locally in J8 and in Actions through #909."}],
}
BEFORE_TRACKING = {
    "id": "release-tracking", "status": "default",
    "default": "Scheduled trackers: catalog-freshness.yml, plus Dependabot for action versions",
    "notes": "Adjudicated: the incumbent stands. Dependabot is claude-code-action's only release tracker. Integrity: the opt-in Monday propose job.",
}
BEFORE_USAGE = {
    "id": "usage-cost-monitoring", "status": "default", "default": "Native OpenTelemetry export",
    "notes": "Scope verified: not covered are Actions under WIF (read the Console organisation's usage), ultrareview cloud runs (usage credits) and `--bare` workers.",
}


class SlotsJsonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((REFERENCE / "slots.json").read_text(encoding="utf-8"))
        cls.status_values = cls.data["status_values"]
        cls.slots = cls.data["slots"]
        cls.by_id = {slot["id"]: slot for slot in cls.slots}
        cls.record = (ROOT / RECORD).read_text(encoding="utf-8")

    def test_the_status_vocabulary_has_retired_and_every_slot_uses_a_listed_status(self):
        self.assertIn("retired", self.status_values)
        self.assertEqual([slot["id"] for slot in self.slots if slot["status"] not in self.status_values], [])
        self.assertEqual(len(self.by_id), len(self.slots), "a slot id occurs twice")

    def test_the_markers_are_the_names_the_record_uses(self):
        self.assertEqual([name for name in NAMES + WORKFLOWS if name not in self.record], [])

    def test_no_slot_selects_a_retired_route_or_names_one_without_saying_so(self):
        self.assertEqual([found for slot in self.slots for found in slot_violations(slot)], [])
        self.assertEqual(other_json_violations(self.data), [])

    def test_github_action_is_retired_with_the_record_and_a_snapshot_of_the_former_default(self):
        slot = self.by_id["github-action"]
        self.assertEqual(slot["status"], "retired")
        self.assertEqual(retired_violations(slot, self.record), [])
        self.assertEqual(tuple(slot["retired"]["workflows"]), WORKFLOWS)
        self.assertEqual(slot["retired"]["record"], RECORD)
        self.assertIn("anthropics/claude-code-action", slot["retired"]["former_default"])
        self.assertEqual(slot["alternatives"], [])

    def test_the_retired_default_is_not_bound_to_one_repository(self):
        # The decision covers the owner's repositories; a default worded "in this repository" sent a session in another repository to conclude that the
        # action was still fine there (2 of 3 runs of the explicit-request prompt wrote the workflow in the A/B recorded in the pull request that added this test).
        slot = self.by_id["github-action"]
        self.assertIn("does not run inside GitHub", slot["default"])
        self.assertNotIn("this repository", slot["default"] + " " + slot["route"])
        self.assertIn("owner's repositories", slot["retired"]["scope"])
        self.assertIn("owner's repositories", slot["route"])

    def test_only_retired_slots_carry_a_retired_block(self):
        self.assertEqual([found for slot in self.slots for found in retired_violations(slot, self.record)], [])

    def test_the_pre_cue_keeps_the_local_toolkit_and_separates_the_open_worker_from_the_routes_available(self):
        slot = self.by_id["pr-review-pre-cue"]
        self.assertEqual(slot["status"], "default-scoped")
        self.assertIn("pr-review-toolkit pre-cue", slot["default"])
        available, _, not_yet = slot["route"].partition("Not available yet")
        self.assertTrue(not_yet, "the route must say what is not available yet")
        for route in ("GPT reads", "verdict-review-gate"):
            self.assertIn(route, available)
        self.assertNotIn("#953", available)
        self.assertIn("#953", not_yet)
        self.assertRegex(slot["notes"], r"claude-pr-toolkit-review\.yml.*retired")

    def test_the_retired_workflows_are_not_in_the_repository(self):
        # A workflow that comes back means the decision was reversed: reopen the retired row in the same change.
        self.assertEqual([name for name in WORKFLOWS if (ROOT / ".github/workflows" / name).exists()], [])


class SurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.slots = json.loads((REFERENCE / "slots.json").read_text(encoding="utf-8"))["slots"]
        cls.index_text = (REFERENCE / "slots.md").read_text(encoding="utf-8")
        cls.index_rows, _ = index_parts(cls.index_text)
        cls.index = {row[0]: list(row[1:]) for row in cls.index_rows}
        cls.sections = page_sections()
        cls.by_id = {section_id: section for _, section_id, section in cls.sections}

    def test_each_slot_has_exactly_one_row_and_one_section(self):
        ids = [slot["id"] for slot in self.slots]
        self.assertEqual(sorted(row[0] for row in self.index_rows), sorted(ids))
        self.assertEqual(sorted(section_id for _, section_id, _ in self.sections), sorted(ids))

    def test_the_index_and_the_layer_pages_show_each_slots_status_and_default(self):
        different = []
        for slot in self.slots:
            status = STATUS_CELL.get(slot["status"], slot["status"])
            fields = section_fields(self.by_id[slot["id"]])
            if self.index[slot["id"]][:2] != [status, slot["default"]]:
                different.append((slot["id"], "slots.md"))
            if (fields["Status"], fields["Default"], fields.get("Route", "")) != (status, slot["default"], slot.get("route", "")):
                different.append((slot["id"], "layer page"))
        self.assertEqual(different, [])

    def test_no_row_line_or_section_selects_a_retired_route_or_names_one_without_saying_so(self):
        found = index_violations(self.index_text)
        for _page, section_id, section in self.sections:
            found += section_violations(section_id, section)
        for page in sorted(REFERENCE.glob("*.md")):
            if page.name == "cross-client.md":
                found += prose_violations(page.name, page.read_text(encoding="utf-8"))
            elif page.name != "slots.md":
                preamble = page.read_text(encoding="utf-8").split("\n## ", 1)[0]
                found += prose_violations(f"{page.name} preamble", preamble)
        self.assertEqual(found, [])

    def test_the_index_says_what_a_retired_row_is(self):
        self.assertRegex(self.index_text, r"A \*\*retired\*\* row has no default to follow")


class CheckSeesTheRowsOfBeforeTests(unittest.TestCase):
    """The checks fail on the rows as they stood before the retirement, and pass on the same rows once they say it."""

    def test_the_action_as_the_default_is_flagged_on_default_and_alternatives_only_while_it_is_not_retired(self):
        self.assertEqual(slot_violations(BEFORE_ACTION), ["github-action.default selects the retired route 'claude-code-action'",
                                                          "github-action.alternatives selects the retired route 'the managed Code Review app'"])
        retired = dict(BEFORE_ACTION, status="retired", default="None: retired 2026-10-10; AI review runs locally, see pr-review-pre-cue", alternatives=[],
                       route="Retired: do not add the managed Claude Code Review GitHub App or anthropics/claude-code-action without a decision that reverses the record.",
                       notes="Retired 2026-10-10: the workflows that ran anthropics/claude-code-action are removed.")
        self.assertEqual(slot_violations(retired), [])

    def test_the_run_in_actions_is_flagged_in_the_default_and_in_the_source_mapping_and_the_run_in_github_that_is_retired_is_not(self):
        mapping = "Claude Code: pr-review-toolkit subagents run as the pre-cue locally in J8 and in Actions through #909."
        flagged = slot_violations(BEFORE_CUE)
        self.assertEqual(flagged, ["pr-review-pre-cue.default selects the retired route 'in Actions'", "pr-review-pre-cue.default selects the retired route 'through #909'",
                                   f"pr-review-pre-cue.primary_sources[0].native_mechanism names the retired route 'in Actions' in a unit that does not say it is retired: {mapping[:80]!r}",
                                   f"pr-review-pre-cue.primary_sources[0].native_mechanism names the retired route 'through #909' in a unit that does not say it is retired: {mapping[:80]!r}"])
        after = dict(BEFORE_CUE, status="default-scoped", default="pr-review-toolkit pre-cue: locally in J8; its run in GitHub is retired (2026-10-10)",
                     primary_sources=[{"native_mechanism": "Claude Code: the pre-cue runs locally in J8; its run in Actions through #909 was retired on 2026-10-10."}])
        self.assertEqual(slot_violations(after), [])

    def test_variants_of_the_old_phrases_are_flagged(self):
        for default in ("locally in J8 and in GitHub Actions", "locally in J8 and as a job through Actions", "the weekly harness-audit dispatch",
                        "the managed Claude Code Review app", "Claude Code Review GitHub App", "with Actions under WIF"):
            with self.subTest(default=default):
                self.assertNotEqual(judge("x", "select", default), [])

    def test_the_dependabot_note_and_the_usage_note_that_still_name_the_route_as_current_are_flagged(self):
        self.assertEqual(len(slot_violations(BEFORE_TRACKING)), 1)
        fixed = dict(BEFORE_TRACKING, notes=BEFORE_TRACKING["notes"].replace(
            "is claude-code-action's only release tracker", "was claude-code-action's only release tracker until its workflows were retired"))
        self.assertEqual(slot_violations(fixed), [])
        self.assertEqual(len(slot_violations(BEFORE_USAGE)), 1)
        self.assertEqual(slot_violations(dict(BEFORE_USAGE, notes=BEFORE_USAGE["notes"].replace("Actions under WIF (", "Actions under WIF (retired 2026-10-10; "))), [])

    def test_a_retired_word_elsewhere_in_the_field_does_not_excuse_a_marker(self):
        items = ["Retirement record docs/decisions/x.md", "anthropics/claude-code-action is the current default"]
        self.assertEqual(len(judge("x.evidence", "explain", items)), 1)
        sentences = "Retired 2026-10-10 for the owner's repositories. The default is claude-code-action."
        self.assertEqual(len(judge("x.notes", "explain", sentences)), 1)
        self.assertEqual(judge("x.notes", "explain", "Retired 2026-10-10: the workflows that ran claude-code-action are removed."), [])

    def test_a_primary_source_snapshot_and_a_retired_block_of_a_retired_slot_are_not_read(self):
        slot = dict(BEFORE_ACTION, status="retired", default="None: retired 2026-10-10", alternatives=[], route="Retired: do not add one", notes="Retired.",
                    primary_sources=[{"native_mechanism": "Claude Code: claude-code-action triggered by an @claude mention"}],
                    retired={"former_default": BEFORE_ACTION["default"]})
        self.assertEqual(slot_violations(slot), [])

    def test_a_layer_page_route_or_continuation_line_that_names_a_retired_route_is_flagged(self):
        section = ("github-action\n\n**Status:** default. **Default:** Use `claude-pr-review.yml`\n\n- **Route:** dispatch it\n"
                   "- **Notes:** Names claude-code-action.\n  continued: and harness-audit again\n- **Former default (snapshot):** claude-code-action\n"
                   "- **Primary sources** (read)\n  - a source naming claude-code-action\n")
        self.assertEqual(section_violations("x", section), [
            "x page, Default selects the retired route 'claude-pr-review'",
            "x page, Notes names the retired route 'claude-code-action' in a unit that does not say it is retired: 'Names claude-code-action.'",
            "x page, line names the retired route 'harness-audit' in a unit that does not say it is retired: '  continued: and harness-audit again'"])

    def test_the_managed_app_as_an_alternative_on_a_page_is_flagged_and_in_a_retired_route_it_is_not(self):
        section = "github-action\n\n**Status:** retired. **Default:** None\n\n- **Alternatives, ranked:** 1. Managed Claude Code Review (GitHub App)\n"
        self.assertEqual(len(section_violations("github-action", section)), 1)
        retired_route = "github-action\n\n**Status:** retired. **Default:** None\n\n- **Route:** Retired: do not add the managed Claude Code Review GitHub App.\n"
        self.assertEqual(section_violations("github-action", retired_route), [])
        live_route = retired_route.replace("retired. **Default", "default. **Default")
        self.assertEqual(len(section_violations("x", live_route)), 1)

    def test_a_duplicate_row_and_an_overturn_cell_that_names_the_action_are_flagged(self):
        row = "| [github-action](git-github-automation.md#github-action) | retired | None | {} |"
        text = "\n".join([row.format("a trigger"), row.format("anthropics/claude-code-action is the way back")])
        found = index_violations(text)
        self.assertIn("slots.md has more than one row for github-action", found)
        self.assertEqual(len(found), 2)

    def test_a_retired_block_on_a_live_slot_or_a_retired_slot_without_one_is_flagged(self):
        record_text = " ".join(WORKFLOWS)
        live = {"id": "x", "status": "default", "default": "d", "retired": {"on": "2026-10-10"}}
        self.assertEqual(retired_violations(live, record_text), ["x carries a retired block but has status 'default'"])
        bare = {"id": "x", "status": "retired", "default": "None"}
        self.assertEqual(retired_violations(bare, record_text), ["x is retired and has no retired block"])
        block = {"on": "2026-10-10", "record": RECORD, "correction": "#141", "scope": "s", "workflows": ["not-in-the-record.yml"],
                 "former_default": "d", "revisit_when": ["w"]}
        self.assertEqual(retired_violations({"id": "x", "status": "retired", "default": "Use it", "retired": block}, record_text),
                         ["x is retired but its default does not say there is none",
                          "x.retired names not-in-the-record.yml, which the record does not"])
        unscoped = {key: value for key, value in block.items() if key != "scope"}
        self.assertEqual(retired_violations({"id": "x", "status": "retired", "default": "None", "retired": dict(unscoped, workflows=list(WORKFLOWS))},
                                            record_text), ["x.retired lacks 'scope'"])


if __name__ == "__main__":
    unittest.main()
