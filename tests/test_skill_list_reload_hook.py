"""The skill-list reload after a compaction (docs/decisions/2026-10-14-skill-list-reload-after-compaction.md).

Claude Code does not send the skill list again after a compaction. The settings template carries one SessionStart hook
on the `compact` source that returns `reloadSkills: true`; the client then sends the list with the next request. These
tests pin that entry, what its command prints, that it survives the settings merge once, and that the wire-level receipt
was taken with the entry the template ships.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))
import apply_claude_settings as acs  # noqa: E402

TEMPLATE = ROOT / "adoption" / "templates" / "claude.settings.template.json"
EVIDENCE = ROOT / "evidence" / "artifacts" / "skill-list-reload-after-compact-20261014"
COMMAND = "jq -cn '{hookSpecificOutput: {hookEventName: \"SessionStart\", reloadSkills: true}}'"
OUTPUT = {"hookSpecificOutput": {"hookEventName": "SessionStart", "reloadSkills": True}}
VERSIONS = ("2.1.296", "2.1.299")


def template():
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))


def compact_groups(settings):
    return [g for g in settings.get("hooks", {}).get("SessionStart", []) if g.get("matcher") == "compact"]


class TemplateEntryTests(unittest.TestCase):
    def test_the_template_has_one_session_start_group_on_the_compact_source(self):
        groups = compact_groups(template())
        self.assertEqual(len(groups), 1, groups)
        self.assertEqual(groups[0], {"matcher": "compact", "hooks": [{"type": "command", "command": COMMAND, "timeout": 5}]})

    def test_no_other_session_start_source_reloads_the_skills(self):
        # A reload on startup or resume would only repeat what the client does there by itself.
        others = [g for g in template()["hooks"]["SessionStart"] if g.get("matcher") != "compact"]
        self.assertEqual([h["command"] for g in others for h in g["hooks"] if "reloadSkills" in h.get("command", "")], [])

    def test_the_hook_fails_open(self):
        # A hook that cannot run must leave the session as it was: no onFailure, no blocking exit code, a short timeout.
        hook = compact_groups(template())[0]["hooks"][0]
        self.assertNotIn("onFailure", hook)
        self.assertNotIn("async", hook)
        self.assertLessEqual(hook["timeout"], 10)

    def test_the_command_has_nothing_the_template_renderer_substitutes(self):
        self.assertNotIn("$", COMMAND)

    @unittest.skipUnless(shutil.which("jq"), "jq is not installed")
    def test_the_command_prints_the_documented_session_start_output(self):
        done = subprocess.run(["/bin/sh", "-c", compact_groups(template())[0]["hooks"][0]["command"]], capture_output=True,
                              text=True, stdin=subprocess.DEVNULL, timeout=10)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        self.assertEqual(json.loads(done.stdout), OUTPUT)
        self.assertEqual(done.stdout.count("\n"), 1, "one line of JSON and nothing else")


class MergeTests(unittest.TestCase):
    def test_a_fresh_host_gets_the_group(self):
        merged = acs.merge_settings({}, template())
        self.assertEqual(len(compact_groups(merged)), 1)

    def test_a_second_apply_does_not_add_a_second_copy(self):
        once = acs.merge_settings({}, template())
        twice = acs.merge_settings(once, template())
        self.assertEqual([h["command"] for g in compact_groups(twice) for h in g["hooks"]].count(COMMAND), 1)

    def test_a_host_hook_on_the_same_source_is_kept_beside_it(self):
        host = {"matcher": "compact", "hooks": [{"type": "command", "command": "host-compact-hook", "timeout": 5}]}
        merged = acs.merge_settings({"hooks": {"SessionStart": [host]}}, template())
        commands = [h["command"] for g in compact_groups(merged) for h in g["hooks"]]
        self.assertEqual((commands.count("host-compact-hook"), commands.count(COMMAND)), (1, 1), commands)


class ReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = json.loads((EVIDENCE / "receipts" / "arms.json").read_text(encoding="utf-8"))
        cls.arms = {(a["version"], a["arm"], a["hook"]): a for a in cls.receipt["arms"]}

    def test_the_receipt_was_taken_with_the_entry_the_template_ships(self):
        self.assertEqual(self.receipt["hook_group"], compact_groups(template())[0])
        for name, key in (("skill_list_probe.py", "probe_sha256"), ("mock_messages_api.py", "stand_in_sha256")):
            self.assertEqual(hashlib.sha256((EVIDENCE / "probe" / name).read_bytes()).hexdigest(), self.receipt[key], name)

    def test_every_arm_ran_on_both_client_versions(self):
        self.assertEqual(sorted(self.arms), sorted((v, arm, hook) for v in VERSIONS for arm in ("manual", "auto", "auto-tool")
                                                   for hook in (False, True)))
        for key, arm in self.arms.items():
            self.assertEqual(arm["client_exit"], 0, key)
            self.assertEqual(arm["compaction_triggers"], ["manual" if key[1] == "manual" else "auto"], key)
            self.assertTrue(all(q["skill_tool_offered"] for q in arm["requests"]), key)
            self.assertFalse(any(q["skill_list_in_system"] for q in arm["requests"]), key)

    def test_the_list_is_in_every_request_before_the_compaction(self):
        for key, arm in self.arms.items():
            self.assertTrue(arm["list_in_requests_before_boundary"], key)
            self.assertTrue(all(arm["list_in_requests_before_boundary"]), key)

    def test_without_the_hook_no_request_after_a_compaction_carries_the_list(self):
        for key, arm in self.arms.items():
            if not key[2]:
                self.assertGreaterEqual(len(arm["list_in_requests_after_boundary"]), 2, key)
                self.assertFalse(any(arm["list_in_requests_after_boundary"]), key)

    def test_with_the_hook_the_list_is_back(self):
        # After /compact the next request carries it. After an automatic compaction the first request does not (the
        # client had already gathered that request's attachments) and every later one does.
        for key, arm in self.arms.items():
            if key[2]:
                after = arm["list_in_requests_after_boundary"]
                expected = [True] * len(after) if key[1] == "manual" else [False] + [True] * (len(after) - 1)
                self.assertGreaterEqual(len(after), 2, key)
                self.assertEqual(after, expected, key)

    def test_the_receipt_holds_no_prompt_text_and_no_path(self):
        text = (EVIDENCE / "receipts" / "arms.json").read_text(encoding="utf-8")
        for needle in ("/home/", "/var/tmp/", "skills are available", "probe-dummy"):
            self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
