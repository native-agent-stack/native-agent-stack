"""The workers slot rows state the agent lifecycle the official docs give (command center owner item, 2026-10-15).

With agent teams on, a subagent spawned from the main conversation with a `name` launches as a teammate, and an idle
teammate stays running and addressable until it is shut down (agent-teams.md and sub-agents.md, fetched 2026-10-15 for
client 2.1.300). The command center found 48 idle teammates, each a one-shot read spawned with a name. The rows must say
how to spawn and end workers, cite the docs lines, and agree with the rendered page.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / ".claude/skills/claude-native-practice/reference"
SOURCES = ROOT / "evidence/artifacts/agent-lifecycle-20261015/sources.json"


class AgentLifecycleRows(unittest.TestCase):
    def setUp(self):
        slots = json.loads((REF / "slots.json").read_text(encoding="utf-8"))["slots"]
        self.rows = {s["id"]: s for s in slots if s["id"] in ("subagent-definitions", "agent-teams")}
        self.page = (REF / "workers.md").read_text(encoding="utf-8")

    def test_one_shot_workers_spawn_without_a_name(self):
        for slot_id in ("subagent-definitions", "agent-teams"):
            with self.subTest(slot=slot_id):
                self.assertIn("without a `name`", self.rows[slot_id]["route"])

    def test_teammates_are_shut_down_when_their_result_is_sealed(self):
        route = self.rows["agent-teams"]["route"]
        self.assertIn("shut", route)
        self.assertIn("stays running and addressable", route)

    def test_the_notes_cite_the_docs_lines_and_the_measurement(self):
        notes = self.rows["agent-teams"]["notes"]
        for cite in ("agent-teams.md:60", "agent-teams.md:86", "agent-teams.md:202-210", "sub-agents.md:937-939",
                     "hooks.md:2853-2858", "CHANGELOG 2.1.178", "48 idle"):
            with self.subTest(cite=cite):
                self.assertIn(cite, notes)

    def test_the_owner_decision_and_the_idle_hook_measurement_are_recorded(self):
        # Owner direction 2026-10-15 (paraphrased via the command center): teams stay on host-wide. Measured the same
        # day: TeammateIdle's continue false ends the turn but leaves the teammate listed and answering; a shutdown
        # request removes it (evidence/artifacts/agent-lifecycle-20261015/measurement.json).
        notes = self.rows["agent-teams"]["notes"]
        self.assertIn("direction, 2026-10-15 (paraphrased via the command center)", notes)
        self.assertIn("does not shut it down", notes)
        self.assertNotIn("a TeammateIdle hook can stop it at idle", notes)
        measured = json.loads((SOURCES.parent / "measurement.json").read_text(encoding="utf-8"))
        self.assertEqual((measured["continue_false_shuts_down"], measured["shutdown_request_removes"],
                          measured["final_answer_reaches_lead"]), (False, True, True))

    def test_no_digest_commits_to_the_unpublished_transcript(self):
        # GPT read of #1142 at b4c4bba3 (P1): the lead's transcript is not committed, so no digest of it, full or
        # abbreviated (7 or more hex characters), may be published beside it.
        measured = json.loads((SOURCES.parent / "measurement.json").read_text(encoding="utf-8"))

        def objects(node):
            if isinstance(node, dict):
                yield node
                for value in node.values():
                    yield from objects(value)
            elif isinstance(node, list):
                for value in node:
                    yield from objects(value)

        unpublished = [o for o in objects(measured) if any("not committed" in v for v in o.values() if isinstance(v, str))]
        self.assertTrue(unpublished)
        for obj in unpublished:
            for key, value in obj.items():
                self.assertNotIn("sha", key.lower())
                self.assertNotIn("digest", key.lower())
                self.assertFalse(isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{7,}", value), key)

    def test_the_page_renders_the_same_route_and_notes(self):
        for slot_id, row in self.rows.items():
            section = self.page[self.page.index(f"\n## {slot_id}\n"):]
            section = section[:section.index("\n## ", 1)] if "\n## " in section[1:] else section
            with self.subTest(slot=slot_id):
                self.assertIn(f"- **Route:** {row['route']}\n", section)
                self.assertIn(f"- **Notes:** {row['notes']}\n", section)

    def test_the_cited_docs_lines_are_recorded_with_the_page_digests(self):
        sources = {s["url"].rsplit("/", 1)[-1]: s for s in json.loads(SOURCES.read_text(encoding="utf-8"))["sources"]}
        for page in ("agent-teams.md", "sub-agents.md", "hooks.md", "CHANGELOG.md"):
            with self.subTest(page=page):
                self.assertRegex(sources[page]["sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("the teammate stays running and addressable while hidden",
                      sources["agent-teams.md"]["quoted_lines"]["86"])
        self.assertIn("a subagent that Claude names launches as a teammate", sources["agent-teams.md"]["quoted_lines"]["60"])
        self.assertIn('{"continue": false, "stopReason": "..."}', sources["hooks.md"]["quoted_lines"]["2858"])


if __name__ == "__main__":
    unittest.main()
