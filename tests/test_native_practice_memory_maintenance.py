"""The auto-memory row carries the 2026-10-15 memory-maintenance facts on every surface a session reads.

The command center's memory-maintenance task (owner direction of 2026-10-15, paraphrased: memories should consolidate on
their own, with the harness resolved against current maintenance practice) set `autoDreamEnabled` in user settings and asked
the row to say what that setting does on this host, what the index limits are, which guard watches them and the first
consolidation, and how durable memory (ai-memory 2.6.3) is maintained. slots.json has no durable-memory row: durable-memory
is the foundation catalog's layer (catalogs/landscape/foundation.json), and the slot list is pinned to the #923 baseline
(tests/test_native_practice_snapshot_provenance.py), so the ai-memory facts sit in auto-memory's notes, beside the route that
names durable-memory (ai-memory) as the memory of record. Before this change the row had no notes, and its overturn condition
did not name the consolidation flag. Repository-text checks only: no page is fetched and no binary is read.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / ".claude/skills/claude-native-practice/reference"
MANIFEST = ROOT / "evidence/artifacts/claude-native-practice-20261009/claude-native-slot-manifest.json"
EVIDENCE = ROOT / "evidence/artifacts/memory-maintenance-20261015"
GUARD = ROOT / "tools/memory-index-guard/memory_index_guard.py"
MEMORY_DOCS_SHA256 = "1ebf1bdc299fe03a8f7566f2da60b2bfca2bd0be7ccf5aa715e75171ac1e5a46"  # memory.md, fetched 2026-10-15T04:39:50Z
BULLET = re.compile(r"^- \*\*([^*]+):\*\* (.*)$")


def section(page: str, slot_id: str) -> str:
    return (REFERENCE / page).read_text(encoding="utf-8").split(f"\n## {slot_id}\n", 1)[1].split("\n## ", 1)[0]


def bullets(text: str) -> dict[str, str]:
    found = {}
    for line in text.splitlines():
        match = BULLET.match(line)
        if match:
            found.setdefault(match.group(1), match.group(2))
    return found


class AutoMemoryRow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        slots = json.loads((REFERENCE / "slots.json").read_text(encoding="utf-8"))["slots"]
        cls.slot = next(slot for slot in slots if slot["id"] == "auto-memory")
        cls.ids = [slot["id"] for slot in slots]
        cls.notes = cls.slot.get("notes", "")

    def test_the_notes_say_what_the_consolidation_setting_does_on_this_host(self):
        for phrase in ("`autoDreamEnabled: true`", "2026-10-15 at 00:45 ET", "`tengu_onyx_plover`", "inert",
                       "`enabled` false and no `available` key", "`.consolidate-lock`"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.notes)

    def test_the_notes_give_the_index_limits_and_name_the_guard(self):
        for phrase in ("memory.md:546", "first 200 lines", "first 25KB", "UTF-16 code units", "80%", "errors.md:4275",
                       "`tools/memory-index-guard`", "every 6 h", "alert at 90%", "evidence/artifacts/memory-maintenance-20261015/"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.notes)

    def test_the_notes_carry_the_durable_memory_maintenance_facts(self):
        for phrase in ("ai-memory 2.6.3", "no `consolidate` CLI", "`memory_consolidate`", "`dry_run` first",
                       "`ai-memory lint --dry-run --no-llm`", "`ai-memory forget-sweep --dry-run`", "ARCHITECTURE.md:721-722",
                       "install.md:2457-2469", "docs/memory-landscape-maintenance.md:90-94", "no extra timer",
                       "adoption/drafts/memory-maintenance-20261008/README.md:23", "49374", "29374", "`--config`"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.notes)

    def test_the_notes_quote_no_one(self):
        self.assertNotIn('"', self.notes)
        self.assertTrue(self.notes.isascii())

    def test_the_overturn_condition_names_the_flag_and_the_paired_check(self):
        overturn = self.slot["overturn_when"]
        self.assertTrue(overturn.startswith("Paired runs show auto memory lowers quality"), "the earlier conditions stay")
        for phrase in ("`tengu_onyx_plover` flag becomes enabled or available", "paired check of the first dream run's edits",
                       "guard's snapshot", "whether consolidation stays on"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, overturn)
        self.assertNotIn(" | ", overturn, "slots.md splits its cells on ' | '")

    def test_the_repository_tracked_rejection_no_longer_calls_a_project_directory_inert(self):
        # Item 29 of the command center's 2026-10-15 guide screen: memory.md:516 reads autoMemoryDirectory from any settings
        # scope, and memory.md:526 honors a project's value under the workspace trust rule for hooks, except while
        # permissions.blockReadsOutsideWorkingDirectories is on. The rejection keeps the practice and drops the inert claim.
        (rejection,) = [text for text in self.slot["rejections"] if text.startswith("Repository-tracked auto memory")]
        self.assertNotIn("inert", rejection)
        for phrase in ("memory.md:516,526", "honored once the folder is trusted",
                       "ignored while `permissions.blockReadsOutsideWorkingDirectories` is on", "memory stays outside the repository"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rejection)
        self.assertEqual(bullets(section("native-clients.md", "auto-memory")).get("Rejected"), "; ".join(self.slot["rejections"]))

    def test_the_evidence_list_names_the_record(self):
        self.assertTrue(any(item.startswith("memory-maintenance-20261015") for item in self.slot["evidence"]))

    def test_the_layer_page_renders_the_notes_and_the_evidence(self):
        fields = bullets(section("native-clients.md", "auto-memory"))
        self.assertEqual(fields.get("Notes"), self.notes)
        self.assertEqual(fields.get("Evidence"), "; ".join(self.slot["evidence"]))
        self.assertEqual(fields.get("Overturn when"), self.slot["overturn_when"])

    def test_the_snapshot_manifest_lists_the_changed_fields(self):
        differs = json.loads(MANIFEST.read_text(encoding="utf-8"))["snapshot"]["current_decision_source"]
        for field in ("overturn_when", "evidence"):
            with self.subTest(field=field):
                self.assertIn("auto-memory", differs["differs_from_this_snapshot_in"][field])
        self.assertIn("memory-maintenance-20261015", differs["note"])

    def test_no_slot_is_named_durable_memory(self):
        self.assertNotIn("durable-memory", self.ids)
        self.assertIn("durable-memory (ai-memory)", self.slot["route"])

    def test_the_guard_the_row_names_exists(self):
        self.assertTrue(GUARD.is_file())


class CitedLines(unittest.TestCase):
    def test_the_repository_lines_the_notes_cite_hold(self):
        lines = (ROOT / "docs/memory-landscape-maintenance.md").read_text(encoding="utf-8").split("\n")
        self.assertEqual(lines[89:94], ["[maintenance]", "enabled = true", "forget_sweep_interval_secs = 0",
                                        "lint_interval_secs = 86400", "embedding_backfill_interval_secs = 3600"])
        self.assertIn("selected deviations", " ".join(lines[96:99]))
        draft = (ROOT / "adoption/drafts/memory-maintenance-20261008/README.md").read_text(encoding="utf-8").split("\n")
        self.assertIn("avoid a duplicate built-in lint job", draft[22])
        self.assertIn("`ai-memory lint --dry-run --no-llm`", draft[22])

    def test_the_evidence_quotes_the_doc_lines_the_notes_cite(self):
        sources = json.loads((EVIDENCE / "sources.json").read_text(encoding="utf-8"))
        docs = {entry["id"]: entry for entry in sources["docs"]}
        memory = docs["memory-docs"]
        self.assertEqual((memory["url"], memory["sha256"]), ("https://code.claude.com/docs/en/memory.md", MEMORY_DOCS_SHA256))
        self.assertIn("first 200 lines", memory["lines"]["546"])
        self.assertIn("first 25KB", memory["lines"]["546"])
        self.assertIn("user, project, local, policy, or `--settings`", memory["lines"]["516"])
        self.assertIn("honors it under the same", memory["lines"]["526"])
        self.assertIn("loads no auto memory from a directory", memory["lines"]["526"])
        self.assertIn("over its 200-line read limit", docs["errors-docs"]["lines"]["4275"])
        upstream = sources["ai_memory"]
        self.assertEqual(upstream["commit"], "385b81ea95f7b73ede7146d0ae606c4caa7b43c1")
        quoted = {entry["locator"]: entry["text"] for entry in upstream["lines"]}
        self.assertIn("Single-writer SQLite actor", quoted["docs/ARCHITECTURE.md:721-722"])
        self.assertIn("Scheduled maintenance is configured in `[maintenance]`", quoted["docs/install.md:2457-2469"])


if __name__ == "__main__":
    unittest.main()
