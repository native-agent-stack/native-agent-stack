"""The claude-native-practice skill selects none of the Claude routes that the 2026-10-10 record retired.

docs/decisions/2026-10-10-retire-in-github-claude-review.md removed the three workflows that ran anthropics/claude-code-action. Before this change the skill's `github-action` row was still the default for Claude work in GitHub and `pr-review-pre-cue` ran "in Actions through #909",
so a session that loaded the skill was told to use a route the API refuses ("credit balance is too low", the command center's correction #141).

What counts as selecting a retired route, on the three surfaces a session reads (reference/slots.json, the reference/slots.md index and the layer pages) and on every other text of the skill folder:
- a field that says what to use (`default`, `alternatives`, and `route` of a live slot; the Default, Alternatives and Route lines of a page) never names a retired route;
- every other text names one only inside a sentence (a string) or an item (a list) that itself says it is retired, so a retired word elsewhere in the field excuses nothing;
- only the dated snapshots are not read: the `retired` block of a slot, what a slot's `primary_sources` quote from their pages, the Primary sources bullet of a page and the Former default bullet of a retired slot's page.
  A source's `native_mechanism` is the repository's own mapping of that source, on every slot (a retired slot's too, which has to say retired), and is read.
Every parser keeps duplicates (a stale second row or section is a violation) and reads every line, not only the labelled bullets. Repository-text checks only: no workflow or client runs here.

Prose is judged one physical line at a time, a bare line break ends a unit, and a full stop or a semicolon ends one too (the command center's ruling at ef3f3e7bf, correction #160: joining wrapped lines made
"Retired 2026-10-10" followed by a line that says the current default is claude-code-action pass on four surfaces). So a physical line that names a retired route says it is retired on that same line (a retirement sentence stays on
one line, or every line of it says so); the messages of the line-judged surfaces say so. The description line of SKILL.md names the topic that invokes the skill ("Claude GitHub Actions setup"); it is pinned to
the text the routing was measured with (DESCRIPTION_SHA256) and read as a topic, not as a route.

Scope of the name patterns (the command center's adjudication of 2026-10-11, final fix round, rule 4 of its convergence ruling): the guard pins the NAMED retired artifacts and the retired slot rows, namely
claude-code-action and anthropics/claude-code-action, claude-code-base-action, install-github-app, the @claude mention, "Claude Code GitHub Action(s)" and "Claude GitHub App", with the carrier phrases it
already flags when the field or unit is about Claude ("in Actions", "through Actions", "under WIF", "in a GitHub workflow", "a GitHub Action"). Generic phrasing of a Claude run in a GitHub workflow that names
none of them ("A GitHub workflow runs Claude Code to review every pull request") cannot be enumerated and is out of this guard's scope: the retirement record governs it, and review reads what the guard
accepts. The patterns do not grow in further rounds.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".claude/skills/claude-native-practice"
REFERENCE = SKILL_DIR / "reference"
RECORD = "docs/decisions/2026-10-10-retire-in-github-claude-review.md"
# The default the command center ruled for the retired row, on all three surfaces (the co-op's GPT read at ba6ab3a5c, measured boundary `wrong-decision-date`: with the date changed on all three surfaces the
# agreement checks and the phrase check still passed, so the whole text is pinned here).
RETIRED_DEFAULT = "None: Claude review does not run inside GitHub (decision of 2026-10-10); AI review runs locally, see pr-review-pre-cue"
WORKFLOWS = ("claude-pr-review.yml", "claude-pr-toolkit-review.yml", "harness-audit.yml")
# The names the record uses for the retired route (checked against the record below), then what the retired rows and notes said without naming a file: the run "in Actions", "through #909", "under WIF", and the managed app,
# which the command center's ruling of 2026-10-10 retired with them and the record does not name.
NAMES = ("claude-code-action", "claude-pr-review", "claude-pr-toolkit-review", "harness-audit", "claude-code-github-action")
PATTERNS = {name: re.compile(re.escape(name), re.I) for name in NAMES}
PATTERNS.update({
    "in Actions": re.compile(r"\bin (?:an? |the )?(?:GitHub Actions?|Actions)\b", re.I),
    "through Actions": re.compile(r"\b(?:through|via|using|with|on|inside) (?:an? |the )?(?:GitHub Actions?|Actions)\b", re.I),
    "through #909": re.compile(r"through #909"),
    "under WIF": re.compile(r"\bunder WIF\b", re.I),
    "the managed Code Review app": re.compile(r"managed (?:Claude )?Code Review|Code Review GitHub App", re.I),
    # The Codex review in GitHub of #1001 at 6e97620cd (P2, slots.json:1616) and the CC's Claude read of the same head (P2-2, P3-1): a live source mapping said `claude -p` runs "in a GitHub workflow ... plus a nightly
    # cron", and the Claude Code GitHub Action, its /install-github-app command and its @claude mention are the same route under other names. claude-code-security-review is left out: it is a documented rejection.
    "in a GitHub workflow": re.compile(r"\b(?:in|from|via|through|using|as) (?:an? |the )?GitHub(?: Actions)? workflows?\b", re.I),
    "the Claude Code GitHub Action": re.compile(r"\bclaude(?: code)? (?:github actions?|action)\b", re.I),
    "install-github-app": re.compile(r"install-github-app", re.I),
    "an @claude mention": re.compile(r"(?<!\w)@claude\b", re.I),
    # The CC's Claude micro at ef3f3e7bf (P3-1) and Codex on the same head (:43, P2): the documentation page's own title is "Claude Code GitHub Actions", its text installs "the Claude GitHub App", the action has a mirror
    # (claude-code-base-action), and a row can describe the carrier first: "Use the GitHub Action for Claude reviews".
    "the Claude GitHub App": re.compile(r"\bclaude(?: code)? github app\b", re.I),
    "claude-code-base-action": re.compile(r"claude-code-base-action", re.I),
    "a GitHub Action": re.compile(r"\bGitHub Action\b", re.I),
})
# "in Actions", "through Actions" (also via, using, with, on, inside), "under WIF", "in a GitHub workflow" and "a GitHub Action" name the retired route only when the field or sentence is about Claude: the record keeps GitHub's required
# checks, Codex's GitHub review and the scheduled trackers, and those run in GitHub Actions (the Codex review in GitHub of #1001 at ba6ab3a5c, P2, line 33). The named workflows, "through #909" and the managed app are specific and count everywhere.
GENERIC = ("in Actions", "through Actions", "under WIF", "in a GitHub workflow", "a GitHub Action")
CLAUDE_ROUTE = re.compile(r"\bclaude\b|\banthropic\b|\bconsole\b|pr-review-toolkit|#909", re.I)
# The description line of SKILL.md ("... or Claude GitHub Actions setup.") names the topic that invokes the skill; the routing of the skill was measured with exactly this text and the retirement rows answer it. It is pinned here
# and not read as a route; a changed description is read like any other line, and the pin fails with it.
DESCRIPTION_SHA256 = "e1d990f026879244108c6cbaae9f72612ca0d5d022593b8ad6db26a2b4bf64cc"
RULE = "a physical line that names a retired route says it is retired on that same line; keep the name and the retirement on one line"
SELECTING = ("default", "alternatives")
SKIPPED_KEYS = ("id", "layer_id", "status", "retired", "primary_sources_total")
RETIRED_KEYS = ("on", "record", "correction", "scope", "workflows", "former_default", "revisit_when")
STATUS_CELL = {"default-scoped": "default (scoped)", "recommendation": "recommendation (owner's choice)"}
SAYS_RETIRED = re.compile(r"\bretire(?:d|ment)\b", re.I)
# The guard is a tripwire for stale text, not a proof of meaning. A unit passes when it says retired, except where it negates the retirement outright ("not retired", "never retired", "no longer retired", "isn't retired",
# "unretired"). It still passes when it says retired and then reverses that in the same sentence ("was retired, but is now current"): that is the boundary the command center ruled (its reads of #1001 at 6e97620cd,
# P3-3, and at ef3f3e7bf, P3-5); the other half of the answer is review, which reads the text the guard accepts. Codex's review of #1001 at ef3f3e7bf (:122) raised both forms.
NEGATED_RETIREMENT = re.compile(r"\b(?:not|never|no longer|\w+n't)\s+(?:yet\s+|been\s+|really\s+)*retire(?:d|ment)\b|\bun-?retire(?:d)?\b", re.I)


def says_retired(unit: str) -> bool:
    return SAYS_RETIRED.search(unit) is not None and NEGATED_RETIREMENT.search(unit) is None
# A unit ends at a full stop or a semicolon followed by white space, whatever follows: a lowercase clause is a clause (the Codex review in GitHub of #1001 at ba6ab3a5c, P2, line 41: the
# first version split only before a capital letter, a backtick, a bracket, a parenthesis or a hyphen, so "retired; the current default is claude-code-action" was one unit that said retired).
# A line break ends a unit too. A comma, a colon or a dash does not: "Retired 2026-10-10: the workflows that ran claude-code-action are removed" is one claim.
# "e.g." and "i.e." do not end a unit (the CC's Claude read of #1001 at 6e97620cd, P3-2): "retired (e.g. the workflows that ran claude-code-action are removed)" is one claim.
# A closing quote, parenthesis or bracket between the full stop and the white space belongs to the unit that ends (the Codex review in GitHub of #1001 at efaa077ef, P2, line 83: `The route was "retired." The
# current default is claude-code-action.` was one unit that said retired); the curly quotes are built with chr() so that this file stays ASCII.
CLOSERS = "\"')]" + chr(0x201D) + chr(0x2019)
SENTENCE = re.compile(r"(?<![Ee]\.g\.)(?<![Ii]\.e\.)(?<=[.;])[" + re.escape(CLOSERS) + r"]*\s+|\s*\n\s*")
ROW = re.compile(r"^\| \[([a-z0-9-]+)\]\(([^)]*)\) \| (.+)$")
BULLET = re.compile(r"^- \*\*(.+?):\*\* (.*)$")


def flatten(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(flatten(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(flatten(item) for item in value)
    return ""


def leaves(value) -> list[str]:
    """Every string of a field, each by itself (a list item is a claim of its own)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [leaf for item in value.values() for leaf in leaves(item)]
    if isinstance(value, (list, tuple)):
        return [leaf for item in value for leaf in leaves(item)]
    return []


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
        found += [f"{label} selects the retired route {name!r}" for name, pattern in PATTERNS.items()
                  if any(pattern.search(leaf) and (name not in GENERIC or CLAUDE_ROUTE.search(leaf)) for leaf in leaves(value))]
        return found
    for unit in units(value):
        for name, pattern in PATTERNS.items():
            if pattern.search(unit) and not says_retired(unit) and (name not in GENERIC or CLAUDE_ROUTE.search(unit)):
                found.append(f"{label} names the retired route {name!r} in a unit that does not say it is retired: {unit[:80]!r}")
    return found


def slot_fields(slot: dict):
    """(label, kind, value) for every judged field of a slot."""
    retired = slot["status"] == "retired"
    for key, value in slot.items():
        if key in SKIPPED_KEYS:
            continue
        if key == "primary_sources":
            for index, source in enumerate(value):  # what the page said is a snapshot; the mapping of it onto this repository is read, on a retired slot too (P3-5)
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
        status, default, overturn = match.group(3).split(" | ", 2)
        rows.append((match.group(1), status, default, overturn[:-2] if overturn.endswith(" |") else overturn))
    return rows, other


def index_links(text: str) -> list[tuple[str, str]]:
    """(slot id, link target) of every table row of slots.md, duplicates kept (the CC's Claude micro at ef3f3e7bf, P3-4, and Codex on the same head, :63: the target was dropped, so a row could link to another page and anchor)."""
    return [(match.group(1), match.group(2)) for match in map(ROW.match, text.splitlines()) if match]


def index_link_violations(text: str, pages: dict[str, str]) -> list[str]:
    """`pages` maps a section id to the layer page that holds it; every row has to link to <page>#<id>."""
    return [f"slots.md links {slot_id} to {href!r}, not to {pages[slot_id]}#{slot_id}" for slot_id, href in index_links(text) if slot_id in pages and href != f"{pages[slot_id]}#{slot_id}"]


def index_violations(text: str) -> list[str]:
    rows, other = index_parts(text)
    found = []
    ids = [row[0] for row in rows]
    found += [f"slots.md has more than one row for {slot_id}" for slot_id in sorted({i for i in ids if ids.count(i) > 1})]
    for slot_id, _status, default, overturn in rows:
        found += judge(f"{slot_id} index, Default", "select", default)
        found += with_rule(judge(f"{slot_id} index, Overturn when", "explain", overturn))  # a row is one physical line: its Overturn when cell states the rule too
    found += with_rule(judge("slots.md text", "explain", [line for line in other if line.strip()]))
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


def with_rule(messages: list[str]) -> list[str]:
    return [f"{message} ({RULE})" for message in messages]


def section_violations(slot_id: str, section: str) -> list[str]:
    """Every line of a section except the dated snapshots (the Primary sources and Former default bullets with their indented lines). A label that occurs twice is a violation: section_fields keeps the first bullet
    of a label, so a conflicting second Route or Overturn when bullet was never compared (the Codex review of #1001 at ef3f3e7bf, :211, and the CC's micro, P3-3)."""
    retired = section_fields(section)["Status"] == "retired"
    labels = [match.group(1) for match in map(BULLET.match, section.splitlines()) if match]
    found = [f"{slot_id} page has more than one {label!r} bullet" for label in dict.fromkeys(labels) if labels.count(label) > 1]
    snapshot = False
    for line in section.splitlines()[1:]:
        if line.startswith("- **Primary sources**") or (retired and line.startswith("- **Former default")):  # only a retired slot's page keeps a dated snapshot of its former default (P3-4)
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
        judged = judge(f"{slot_id} page, {label}", "select" if selecting else "explain", text)
        found += judged if selecting else with_rule(judged)  # every explaining unit states the rule; a selecting field does not name a unit (the command center's micro at efaa077ef, B2)
    return found


def prose_violations(name: str, text: str) -> list[str]:
    """One physical line at a time (the command center's ruling at ef3f3e7bf, correction #160): the lines of a wrapped sentence are judged separately and the message names the rule."""
    return with_rule(judge(name, "explain", [line for line in text.splitlines() if line.strip()]))


def entry_point_violations(text: str) -> list[str]:
    """SKILL.md: the description line is the pinned topic text and is not read as a route; every other line is."""
    lines = text.splitlines()
    return prose_violations("SKILL.md", "\n".join(line for line in lines if not (line.startswith("description:") and hashlib.sha256(line.encode("utf-8")).hexdigest() == DESCRIPTION_SHA256)))


def folder_prose_violations(skill_dir: Path) -> list[str]:
    """The prose no slot parser reads: cross-client.md, the preamble of every layer page and the entry point SKILL.md (the Codex review in GitHub of #1001 at ba6ab3a5c, P2, line 312:
    the first version scanned only reference/, so a stale route in the first instruction a session reads passed every check)."""
    found = []
    for page in sorted((skill_dir / "reference").glob("*.md")):
        if page.name == "cross-client.md":
            found += prose_violations(page.name, page.read_text(encoding="utf-8"))
        elif page.name != "slots.md":
            preamble = page.read_text(encoding="utf-8").split("\n## ", 1)[0]
            found += prose_violations(f"{page.name} preamble", preamble)
    return found + entry_point_violations((skill_dir / "SKILL.md").read_text(encoding="utf-8"))


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

    def test_the_one_default_rule_names_the_retired_exception_wherever_it_is_stated(self):
        # The Codex review in GitHub of #1001 at ba6ab3a5c, P2, slots.json:13: the rule said one default per slot and the entry point said to follow every slot's default, while a retired row
        # has none (its default begins with "None"), so a consumer of the declared invariant could take that prose for a selected default or reject the document.
        rule = self.data["selection_rule"]
        self.assertIn("A retired slot is the exception: it has no default", rule)
        self.assertIn("Selection rule: " + rule, (REFERENCE / "slots.md").read_text(encoding="utf-8"))
        entry = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        step = re.search(r"\*\*Follow the default\.\*\*(.*?)(?=\n\d+\. \*\*|\Z)", entry, re.S)
        self.assertIsNotNone(step, "SKILL.md has no step 'Follow the default'")
        self.assertIn("a retired row has no default, so follow the replacement it names", re.sub(r"\s+", " ", step.group(1)))

    def test_the_markers_are_the_names_the_record_uses(self):
        self.assertEqual([name for name in NAMES + WORKFLOWS if name not in self.record], [])

    def test_no_slot_selects_a_retired_route_or_names_one_without_saying_so(self):
        self.assertEqual([found for slot in self.slots for found in slot_violations(slot)], [])
        self.assertEqual(other_json_violations(self.data), [])

    def test_github_action_is_retired_with_the_record_and_a_snapshot_of_the_former_default(self):
        slot = self.by_id["github-action"]
        self.assertEqual(slot["status"], "retired")
        self.assertEqual(retired_violations(slot, self.record), [])
        self.assertEqual(slot["default"], RETIRED_DEFAULT)
        self.assertEqual(tuple(slot["retired"]["workflows"]), WORKFLOWS)
        self.assertEqual(slot["retired"]["record"], RECORD)
        self.assertIn("anthropics/claude-code-action", slot["retired"]["former_default"])
        self.assertEqual(slot["alternatives"], [])

    def test_the_scheduled_tasks_route_retires_the_claude_routes_and_not_every_model_backed_job(self):
        # Codex on #1005 at 425240f6e (P2, scheduling-supervision.md:9) and the command center's ruling: the record retires Claude review inside GitHub and keeps Codex's GitHub review, so a GitHub schedule is not
        # limited to jobs that run no model; a scheduled Claude task runs locally.
        slot = self.by_id["scheduled-tasks"]
        self.assertNotIn("no model", slot["route"] + " ".join(slot["alternatives"]))
        self.assertIn("GitHub Actions schedules repository jobs (Claude runs inside GitHub are retired, 2026-10-10, so a scheduled Claude task runs locally: see github-action)", slot["route"])
        self.assertIn("GitHub Actions schedule (repository jobs; a scheduled Claude task runs locally)", slot["alternatives"])
        page = (REFERENCE / "scheduling-supervision.md").read_text(encoding="utf-8")
        self.assertIn(slot["route"], page)
        self.assertIn("GitHub Actions schedule (repository jobs; a scheduled Claude task runs locally)", page)
        # Codex on #1001 at efaa077ef (P2, claude-native-slot-manifest.json:47): the manifest's note on the differences from its snapshot still said the route was narrowed to jobs that run no model, which
        # the shipped route does not say; the note and the route agree.
        manifest = json.loads((ROOT / "evidence/artifacts/claude-native-practice-20261009/claude-native-slot-manifest.json").read_text(encoding="utf-8"))
        note = manifest["snapshot"]["current_decision_source"]["note"]
        self.assertNotIn("jobs that run no model", note)
        self.assertIn("GitHub Actions schedules repository jobs, Claude runs inside GitHub are retired (2026-10-10), so a scheduled Claude task runs locally", note)

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

    def test_the_index_and_the_layer_pages_show_each_slots_overturn_condition(self):
        # One step wider than the Codex review of #1005 (C1): a row's Overturn when was edited in slots.json and on its layer page and the index cell of slots.md kept the old text.
        different = []
        for slot in self.slots:
            if self.index[slot["id"]][2] != slot["overturn_when"]:
                different.append((slot["id"], "slots.md"))
            if section_fields(self.by_id[slot["id"]]).get("Overturn when") != slot["overturn_when"]:
                different.append((slot["id"], "layer page"))
        self.assertEqual(different, [])

    def test_no_row_line_or_section_selects_a_retired_route_or_names_one_without_saying_so(self):
        found = index_violations(self.index_text)
        for _page, section_id, section in self.sections:
            found += section_violations(section_id, section)
        found += folder_prose_violations(SKILL_DIR)
        self.assertEqual(found, [])

    def test_every_file_of_the_skill_folder_is_read_by_a_check(self):
        read = {SKILL_DIR / "SKILL.md", REFERENCE / "slots.json"} | set(REFERENCE.glob("*.md"))
        self.assertEqual(sorted(str(path.relative_to(SKILL_DIR)) for path in SKILL_DIR.rglob("*") if path.is_file() and path not in read), [],
                         "a file of the skill folder that no check reads can name a retired route unseen")

    def test_the_entry_point_naming_a_retired_route_as_current_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp)
            (skill / "reference").mkdir()
            (skill / "reference" / "cross-client.md").write_text("Codex lanes follow the same practice.\n", encoding="utf-8")
            (skill / "SKILL.md").write_text("---\nname: x\n---\n3. **Follow the default.** Set up anthropics/claude-code-action for review.\n", encoding="utf-8")
            self.assertEqual(len(folder_prose_violations(skill)), 1)
            (skill / "SKILL.md").write_text("---\nname: x\n---\n3. **Follow the default.** The anthropics/claude-code-action route was retired on 2026-10-10.\n", encoding="utf-8")
            self.assertEqual(folder_prose_violations(skill), [])

    def test_each_index_row_links_to_the_layer_page_section_of_its_slot(self):
        # Codex on #1001 at ef3f3e7bf (:63): the link target was dropped, so a row could point at another existing page and anchor.
        pages = {section_id: page for page, section_id, _ in self.sections}
        self.assertEqual(index_link_violations(self.index_text, pages), [])
        self.assertEqual(sorted(slot_id for slot_id, _ in index_links(self.index_text)), sorted(slot["id"] for slot in self.slots))
        row = "| [github-action](git-github-automation.md#github-action) | retired |"
        for wrong in ("ci-supply-chain.md#github-action", "git-github-automation.md#release-tracking", "git-github-automation.md", "#github-action", "git-github-automation.md#github-action "):
            with self.subTest(href=wrong):
                self.assertEqual(len(index_link_violations(row.replace("git-github-automation.md#github-action", wrong), {"github-action": "git-github-automation.md"})), 1)
        self.assertEqual(index_link_violations(row, {"github-action": "git-github-automation.md"}), [])

    def test_the_index_says_what_a_retired_row_is(self):
        self.assertRegex(self.index_text, r"A \*\*retired\*\* row has no default to follow")
        self.assertIn(RULE, self.index_text, "the one-line rule is stated where a maintainer of the rows reads")


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
        for default in ("Claude review locally in J8 and in GitHub Actions", "Claude review locally in J8 and as a job through Actions", "the weekly harness-audit dispatch",
                        "the managed Claude Code Review app", "Claude Code Review GitHub App", "Claude with Actions under WIF"):
            with self.subTest(default=default):
                self.assertNotEqual(judge("x", "select", default), [])

    def test_the_generic_deployment_phrases_are_flagged_only_when_the_field_is_about_claude(self):
        # The record keeps GitHub's required checks, Codex's GitHub review and the scheduled trackers, which run in GitHub Actions (the Codex review in GitHub of #1001, P2, line 33).
        for text in ("The required checks and the scheduled trackers run in GitHub Actions.", "Federated cloud access is issued through Actions under WIF.", "The weekly job runs through Actions.",
                     "Catalog freshness runs in GitHub Actions.", "The non-model artifact gate runs under WIF.",
                     "The required checks (`validate`, `sota-sources`, `verdict-review-gate`) and the landing scripts run in GitHub Actions.", "Codex's GitHub review is not affected and its gates run in GitHub Actions."):
            with self.subTest(allowed=text):
                self.assertEqual(judge("x.default", "select", text), [])
                self.assertEqual(judge("x.notes", "explain", text), [])
        for text in ("Claude review runs in GitHub Actions.", "The Claude job runs through Actions.", "Anthropic access under WIF.", "pr-review-toolkit runs in Actions.", "Console usage of Actions under WIF."):
            with self.subTest(flagged=text):
                self.assertEqual(len(judge("x.default", "select", text)), 1)
                self.assertEqual(len(judge("x.notes", "explain", text)), 1)
        # a specific marker counts everywhere
        self.assertEqual(len(judge("x.notes", "explain", "The run through #909 stays.")), 1)
        # the former route in the same words, and the local Claude worker put back into GitHub Actions, are the regressions the guard exists for
        for text in ("The Claude review runs in GitHub Actions under WIF.", "The local Claude review worker runs in GitHub Actions."):
            with self.subTest(flagged=text):
                self.assertNotEqual(judge("x.default", "select", text), [])
        # each list item is judged by itself: a Claude item does not turn the next item's generic phrase into the retired route
        self.assertEqual(judge("x.alternatives", "select", ["Claude plugin review", "A scheduled job that runs in GitHub Actions"]), [])
        self.assertEqual(len(judge("x.alternatives", "select", ["Claude plugin review", "Claude job that runs in GitHub Actions"])), 1)

    def test_every_route_the_decision_retains_is_accepted(self):
        # The co-op's GPT read at ba6ab3a5c (P2, generic phrases): the decision keeps the local AI reads, Codex's GitHub review and GitHub's gates. Every bullet of its "What remains" section,
        # with its continuation lines joined, is accepted as explanatory text and as a field, and the gates are accepted when they are described with the generic deployment phrases.
        remains = (ROOT / RECORD).read_text(encoding="utf-8").split("\n## What remains", 1)[1].split("\n## ", 1)[0]
        bullets, current = [], None
        for line in remains.splitlines():
            if line.startswith("- "):
                current = [line]
                bullets.append(current)
            elif current is not None and line.startswith("  ") and line.strip():
                current.append(line.strip())
        bullets = [" ".join(parts) for parts in bullets]
        self.assertGreaterEqual(len(bullets), 3)
        for bullet in bullets:
            with self.subTest(bullet=bullet[:60]):
                self.assertEqual(judge("record.what_remains", "explain", bullet), [])
                self.assertEqual(judge("record.what_remains", "select", bullet), [])

    def test_a_lowercase_clause_after_a_full_stop_or_a_semicolon_is_its_own_unit(self):
        # The Codex review in GitHub of #1001 at ba6ab3a5c, P2, line 41: the first splitter needed a capital letter, so these were one unit that said "retired".
        for text in ("This route was retired; the current default is claude-code-action.", "It was retired. the current default is claude-code-action.",
                     "Retired 2026-10-10.\nthe current default is claude-code-action.", "retired;\tthe current default is claude-code-action.",
                     "Retired 2026-10-10\nthe current default is claude-code-action."):
            with self.subTest(text=text):
                self.assertEqual(len(judge("x.notes", "explain", text)), 1)
                self.assertEqual(len(units(text)), 2)
        for text in ("claude-code-action was retired; the workflows that ran it are removed.", "Retired 2026-10-10: the workflows that ran claude-code-action are removed.",
                     "The claude-code-action route was retired, and the workflows that ran it are removed."):
            with self.subTest(text=text):
                self.assertEqual(judge("x.notes", "explain", text), [])

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

    def test_what_a_primary_source_quoted_and_the_retired_block_of_a_retired_slot_are_not_read_but_its_source_mapping_is(self):
        # The CC's Claude read of #1001 at 6e97620cd (P3-5): the guard skipped a retired slot's primary_sources, so the mapping of its source stayed in the present tense ("claude-code-action triggered by an @claude mention").
        slot = dict(BEFORE_ACTION, status="retired", default="None: retired 2026-10-10", alternatives=[], route="Retired: do not add one", notes="Retired.",
                    primary_sources=[{"practice": "Run claude-code-action on an @claude mention", "native_mechanism": "Retired here (2026-10-10): claude-code-action triggered by an @claude mention."}],
                    retired={"former_default": BEFORE_ACTION["default"]})
        self.assertEqual(slot_violations(slot), [])
        stale = dict(slot, primary_sources=[{"practice": "Run claude-code-action", "native_mechanism": "Claude Code: claude-code-action triggered by an @claude mention on a PR review comment, with write tools."}])
        self.assertEqual(len(slot_violations(stale)), 2)  # the action by name and the mention

    def test_a_layer_page_route_or_continuation_line_that_names_a_retired_route_is_flagged(self):
        section = ("github-action\n\n**Status:** default. **Default:** Use `claude-pr-review.yml`\n\n- **Route:** dispatch it\n"
                   "- **Notes:** Names claude-code-action.\n  continued: and harness-audit again\n- **Former default (snapshot):** claude-code-action\n"
                   "- **Primary sources** (read)\n  - a source naming claude-code-action\n")
        self.assertEqual(section_violations("x", section), [
            "x page, Default selects the retired route 'claude-pr-review'",
            f"x page, Notes names the retired route 'claude-code-action' in a unit that does not say it is retired: 'Names claude-code-action.' ({RULE})",
            f"x page, line names the retired route 'harness-audit' in a unit that does not say it is retired: '  continued: and harness-audit again' ({RULE})",
            f"x page, Former default (snapshot) names the retired route 'claude-code-action' in a unit that does not say it is retired: 'claude-code-action' ({RULE})"])
        retired = section.replace("**Status:** default.", "**Status:** retired.")
        self.assertEqual(len(section_violations("x", retired)), 3, "a retired slot's page keeps its dated snapshot of the former default")

    def test_the_managed_app_as_an_alternative_on_a_page_is_flagged_and_in_a_retired_route_it_is_not(self):
        section = "github-action\n\n**Status:** retired. **Default:** None\n\n- **Alternatives, ranked:** 1. Managed Claude Code Review (GitHub App)\n"
        self.assertEqual(len(section_violations("github-action", section)), 1)
        retired_route = "github-action\n\n**Status:** retired. **Default:** None\n\n- **Route:** Retired: do not add the managed Claude Code Review GitHub App.\n"
        self.assertEqual(section_violations("github-action", retired_route), [])
        live_route = retired_route.replace("retired. **Default", "default. **Default")
        self.assertEqual(len(section_violations("x", live_route)), 1)

    def test_a_live_source_mapping_that_runs_claude_in_a_github_workflow_is_flagged_and_the_reworded_mapping_is_not(self):
        # The Codex review in GitHub of #1001 at 6e97620cd (P2, slots.json:1616) and the CC's Claude read of it (P2-2): skills-library.primary_sources[5].native_mechanism, as it stood.
        before = ("Claude Code (page example): `claude -p` with --allowedTools and --output-format json per eval, in a GitHub workflow triggered on paths CLAUDE.md and .claude/** plus a nightly cron. "
                  "Under our selection rule, promptfoo 0.124.0 or the skill-creator benchmark would carry the checks.")
        self.assertEqual(len(judge("skills-library.primary_sources[5].native_mechanism", "explain", before)), 1)
        for text in ("The Claude review runs in a GitHub workflow.", "Claude Code runs from a GitHub workflow.", "The Claude job is run via a GitHub Actions workflow.", "Claude, using the GitHub workflow of the repository, reviews it.",
                     "Claude runs as a GitHub workflow."):
            with self.subTest(flagged=text):
                self.assertNotEqual(judge("x.notes", "explain", text), [])
                self.assertNotEqual(judge("x.default", "select", text), [])
        for text in ("Catalog freshness runs in a GitHub workflow.", "The non-model artifact gate is a GitHub workflow.", "Codex's review is requested from a GitHub workflow comment trigger and no model of ours runs."):
            with self.subTest(allowed=text):
                self.assertEqual(judge("x.notes", "explain", text), [])
        after = ("Claude Code (page example): `claude -p` with --allowedTools and --output-format json per eval, triggered on paths CLAUDE.md and .claude/** plus a nightly cron. "
                 "The page runs it in a GitHub workflow, a Claude run that is retired here (decision of 2026-10-10), so the checks run locally. "
                 "Under our selection rule, promptfoo 0.124.0 or the skill-creator benchmark would carry the checks.")
        self.assertEqual(judge("skills-library.primary_sources[5].native_mechanism", "explain", after), [])

    def test_the_other_names_of_the_retired_route_are_flagged_and_the_documented_rejection_is_not(self):
        # The CC's Claude read of #1001 at 6e97620cd (P3-1): four forms passed with the edit applied on every surface.
        for text in ("Set up the Claude Code GitHub Action for review.", "Run /install-github-app to add it.", "Ask for a fix with an @claude mention on the review comment.", "The Claude GitHub action reviews each PR.",
                     "claude code action is the default."):
            with self.subTest(flagged=text):
                self.assertNotEqual(judge("x.notes", "explain", text), [])
                self.assertNotEqual(judge("x.default", "select", text), [])
                self.assertEqual(judge("x.notes", "explain", text.rstrip(".") + ", retired on 2026-10-10."), [])
        # anthropics/claude-code-security-review is a documented rejection and appears in the Rejected rows of the pages; it is not the retired route
        self.assertEqual(judge("x.rejections", "explain", "anthropics/claude-code-security-review is rejected: it needs the same GitHub workflow."), [])
        self.assertEqual(judge("x.notes", "explain", "Write to the maintainers at name@claude.example."), [], "an address is not a mention")

    def test_an_abbreviation_does_not_end_a_claim(self):
        # The CC's Claude read of #1001 at 6e97620cd (P3-2): "e.g." and "i.e." do not end a unit.
        for text in ("The route was retired (e.g. the workflows that ran claude-code-action are removed).", "claude-code-action was retired, i.e. its workflows are removed."):
            with self.subTest(text=text):
                self.assertEqual(len(units(text)), 1)
                self.assertEqual(judge("x.notes", "explain", text), [])
        self.assertEqual(len(judge("x.notes", "explain", "It was retired e.g. last week. The default is claude-code-action.")), 1, "the sentence after an abbreviation still ends where it ends")

    def test_a_closing_quote_parenthesis_or_bracket_after_the_full_stop_does_not_join_two_claims(self):
        # The Codex review in GitHub of #1001 at efaa077ef (P2, line 83): the pattern demanded white space right after the full stop, so a closing delimiter kept the sentence that said retired
        # and the sentence that reintroduces the route in one unit.
        left, right = chr(0x201C), chr(0x201D)
        for text in ('The route was "retired." The current default is claude-code-action.', "The route was (retired.) The current default is claude-code-action.",
                     "The route was [retired.] The current default is claude-code-action.", f"The route was {left}retired.{right} The current default is claude-code-action.",
                     "The route was 'retired.' The current default is claude-code-action.", 'The route was "retired;" the current default is claude-code-action.'):
            with self.subTest(text=text):
                self.assertEqual(len(units(text)), 2)
                found = judge("x.notes", "explain", text)
                self.assertEqual(len(found), 1, found)
                self.assertIn("claude-code-action", found[0])
        for text in ('The claude-code-action route was "retired." It is not selected by any row.', "claude-code-action was retired (see the record.) No row selects it."):
            with self.subTest(accepted=text):
                self.assertEqual(judge("x.notes", "explain", text), [])
        self.assertEqual(len(units('retired (e.g. "the workflows that ran claude-code-action are removed.") Nothing else.')), 2)

    def test_every_explaining_unit_of_a_layer_page_and_of_the_index_states_the_rule_and_a_selecting_field_does_not(self):
        # The command center's Claude micro of #1001 at efaa077ef (B2): the module claims that the message of every line-judged surface states the rule, and the labelled bullets of a layer page and the Overturn when cell of an
        # index row did not. A selecting field (Default, Alternatives, a live slot's Route) names no unit and states nothing.
        section = "x\n\n**Status:** default. **Default:** d\n\n- **Notes:** Names claude-code-action.\n- **Route:** Use claude-code-action.\n"
        found = section_violations("x", section)
        self.assertEqual(found, [f"x page, Notes names the retired route 'claude-code-action' in a unit that does not say it is retired: 'Names claude-code-action.' ({RULE})",
                                 "x page, Route selects the retired route 'claude-code-action'"])
        row = "| [github-action](git-github-automation.md#github-action) | default | d | Use claude-code-action again |"
        found = index_violations(row)
        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0].endswith(f"({RULE})"), found)

    def test_generic_workflow_phrasing_is_out_of_scope_and_the_module_says_so(self):
        # The command center's adjudication of 2026-10-11 on the Codex review in GitHub of #1001 at efaa077ef (P2, line 48): workflow-first phrasing that names none of the retired artifacts is a follow-up
        # and the class closes (rule 4 of its convergence ruling). The boundary is pinned so that a later pattern round has to reopen it deliberately, with new primary evidence.
        for text in ("A GitHub workflow runs Claude Code to review every pull request.", "The GitHub Actions workflow invokes Claude for PR review"):
            with self.subTest(text=text):
                self.assertEqual(judge("x.default", "select", text), [])
                self.assertEqual(judge("x.notes", "explain", text), [])
        self.assertIn("is out of this guard's scope", " ".join(__doc__.split()))
        self.assertIn("The patterns do not grow in further rounds.", " ".join(__doc__.split()))

    def test_a_bare_line_break_ends_a_unit_on_every_surface_and_the_rule_is_in_the_message(self):
        # The command center's ruling at ef3f3e7bf (correction #160) and its micro (P2-1): the run-on below passed on four prose surfaces when wrapped lines were joined. It fails on all of them again, as do the "." and ";" forms;
        # a retirement sentence on one line passes, and one wrapped without punctuation fails with a message that names the one-line rule.
        run_on = "Retired 2026-10-10\nthe current default is claude-code-action."
        for form in (run_on, "Retired 2026-10-10.\nthe current default is claude-code-action.", "Retired 2026-10-10;\nthe current default is claude-code-action."):
            with self.subTest(form=form):
                self.assertEqual(len(prose_violations("x.md", form)), 1)
                self.assertEqual(len(index_violations(form)), 1, "slots.md prose")
                self.assertEqual(len(section_violations("x", "x\n\n**Status:** default. **Default:** d\n\n- **Notes:** n\n" + form.replace("\n", "\n  "))), 1, "a continuation line of a layer-page bullet")
                with tempfile.TemporaryDirectory() as tmp:
                    skill = Path(tmp)
                    (skill / "reference").mkdir()
                    (skill / "reference" / "cross-client.md").write_text(form + "\n", encoding="utf-8")
                    (skill / "reference" / "x.md").write_text(form + "\n\n## x\n", encoding="utf-8")
                    (skill / "SKILL.md").write_text("---\nname: x\n---\n" + form + "\n", encoding="utf-8")
                    names = [message.split(" names ")[0] for message in folder_prose_violations(skill)]
                    self.assertEqual(sorted(names), ["SKILL.md", "cross-client.md", "x.md preamble"])
        self.assertEqual(prose_violations("x.md", "The claude-code-action route was retired on 2026-10-10 and no row selects it.\n"), [])
        wrapped = prose_violations("x.md", "The claude-code-action route\nwas retired on 2026-10-10 and no row selects it.\n")
        self.assertEqual(len(wrapped), 1)
        self.assertIn("says it is retired on that same line", wrapped[0])
        self.assertEqual(prose_violations("x.md", "The claude-code-action route was\nretired on 2026-10-10 and no row selects it.\n").__len__(), 1)
        self.assertEqual(prose_violations("x.md", "The claude-code-action route was retired on 2026-10-10,\nand no row selects it.\n"), [], "every line that names the route says retired")

    def test_the_description_line_is_the_measured_topic_text_and_is_not_read_as_a_route(self):
        entry = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        description = next(line for line in entry.splitlines() if line.startswith("description:"))
        self.assertEqual(hashlib.sha256(description.encode("utf-8")).hexdigest(), DESCRIPTION_SHA256, "the description is the text the routing was measured with; a change needs a new measurement")
        self.assertIn("Claude GitHub Actions setup", description)
        self.assertEqual(entry_point_violations(entry), [])
        changed = entry.replace("Claude GitHub Actions setup", "Claude GitHub Actions setup with the claude-code-action workflow")
        self.assertNotEqual(entry_point_violations(changed), [], "a changed description is read like any other line")

    def test_the_other_names_the_documentation_page_uses_are_flagged(self):
        # Lines of the page the guard's names come from (https://code.claude.com/docs/en/github-actions.md, sha256 87b99aefc0a9f438…, retained): its title, line 9, line 33 and line 63, and the carrier named first.
        for text in ("Claude Code GitHub Actions", "Claude Code GitHub Actions is a GitHub Action that runs Claude Code inside your repository's workflows.", "Claude Code installs the Claude GitHub App, then sets up an authentication secret.",
                     "Install the Claude GitHub App", "Use the GitHub Action for Claude reviews", "Use anthropics/claude-code-base-action for Claude reviews.", "Claude reviews run in a GitHub Action.",
                     "Claude reviews run on GitHub Actions.", "Claude reviews run with GitHub Actions.", "The Claude review is a GitHub Action."):
            with self.subTest(flagged=text):
                self.assertNotEqual(judge("x.notes", "explain", text), [])
                self.assertNotEqual(judge("x.default", "select", text), [])
        for text in ("Pin every GitHub Action to a full commit SHA.", "The catalog check runs on GitHub Actions."):
            with self.subTest(allowed=text):
                self.assertEqual(judge("x.notes", "explain", text), [])
        # the wording of the scheduled-tasks row (the command center's ruling, from Codex's thread on scheduling-supervision.md:9: the record retires Claude routes, not every model-backed job)
        self.assertEqual(judge("x.alternatives", "select", ["GitHub Actions schedule (repository jobs; a scheduled Claude task runs locally)"]), [])
        self.assertEqual(judge("scheduled-tasks.route", "select", "GitHub Actions schedules repository jobs (Claude runs inside GitHub are retired, 2026-10-10, so a scheduled Claude task runs locally: see github-action)"), [])

    def test_explicit_negations_of_the_retirement_do_not_count_as_saying_retired_and_the_reversal_boundary_is_pinned(self):
        # Codex on #1001 at ef3f3e7bf (:122). Explicit negations fail; the reversal ("retired, but now current") is the boundary the command center ruled and stays accepted, as the comment at SAYS_RETIRED says.
        for text in ("The claude-code-action is not retired and handles PRs.", "claude-code-action was never retired.", "claude-code-action is no longer retired.", "claude-code-action isn't retired.", "claude-code-action is unretired."):
            with self.subTest(negated=text):
                self.assertEqual(len(judge("x.notes", "explain", text)), 1)
        for text in ("claude-code-action was retired on 2026-10-10.", "The retirement of claude-code-action is recorded.", "claude-code-action was retired, not removed from the history."):
            with self.subTest(affirmed=text):
                self.assertEqual(judge("x.notes", "explain", text), [])
        self.assertEqual(judge("x.notes", "explain", "The claude-code-action was retired, but is now current."), [], "the ruled boundary: a reversal in the same sentence passes")

    def test_a_second_bullet_with_the_same_label_in_a_layer_page_section_is_flagged(self):
        section = "x\n\n**Status:** default. **Default:** d\n\n- **Route:** one\n- **Notes:** n\n- **Route:** two, which contradicts the first\n- **Overturn when:** a\n- **Overturn when:** b\n"
        self.assertEqual(section_violations("x", section), ["x page has more than one 'Route' bullet", "x page has more than one 'Overturn when' bullet"])
        self.assertEqual(section_violations("x", section.replace("- **Route:** two, which contradicts the first\n", "").replace("- **Overturn when:** b\n", "")), [])

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
