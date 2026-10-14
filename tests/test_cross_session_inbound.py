"""Cross-session inbound is accepted per launcher, not in user settings (docs/decisions/2026-10-14-cross-session-inbound-per-launcher.md)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))
import new_wsl_client_config as cfg  # noqa: E402

EVIDENCE = ROOT / "evidence" / "artifacts" / "cross-session-inbound-20261014" / "receipts"
TEMPLATES = (ROOT / "adoption" / "templates" / "claude.settings.template.json",
             ROOT / "adoption" / "new-wsl" / "templates" / "claude.settings.additions.json")
FLAG = """--settings '{"crossSessionInbound":"accept"}'"""


class TemplateTests(unittest.TestCase):
    def test_no_settings_template_sets_the_inbound_value(self):
        for path in TEMPLATES:
            self.assertNotIn("crossSessionInbound", json.loads(path.read_text(encoding="utf-8")), path.name)

    def test_the_map_has_no_entry_for_it_and_the_tool_still_classes_it_authorization(self):
        data = json.loads((ROOT / cfg.MAP_REL).read_text(encoding="utf-8"))   # its `about` still lists the authorization class
        self.assertEqual([e["match"] for e in data["entries"] if any("crossSessionInbound" in m for m in e["match"])], [])
        self.assertNotIn("crossSessionInbound", json.dumps(data["slot_configs"]))
        self.assertTrue(cfg.is_authorization_piece("claude/settings/setting/crossSessionInbound"))

    def test_the_headless_recipes_name_the_per_launcher_value(self):
        for name in ("claude-native-profile.md", "claude-native-ultracode.md"):
            self.assertIn(FLAG, (ROOT / "recipes" / name).read_text(encoding="utf-8"), name)


class ReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arms = {a["arm"][:3].rstrip("-"): a for a in json.loads((EVIDENCE / "probe-2.1.299.json").read_text())["arms"]}
        cls.reload = {a["arm"][:2]: a for a in json.loads((EVIDENCE / "live-reload-2.1.299.json").read_text())["arms"]}

    def test_the_default_delivers_within_a_class_and_holds_across_classes(self):
        self.assertEqual({k: a["delivered"] for k, a in self.arms.items()},
                         {"A1": False, "A2": True, "A3": True, "A3c": False, "A4": True, "A5": False, "A6": True, "A6c": False})

    def test_every_held_message_was_reported_held_by_the_receiver(self):
        for key in ("A1", "A3c", "A5", "A6c"):
            self.assertIn("system:peer_message_hold", self.arms[key]["receiver_events_after_send"], key)

    def test_the_flag_is_what_delivers_to_a_worker(self):
        for flagged, plain in (("A3", "A3c"), ("A6", "A6c")):
            self.assertEqual(self.arms[flagged]["receiver_settings_flag"], '{"crossSessionInbound":"accept"}')
            self.assertIsNone(self.arms[plain]["receiver_settings_flag"])
            self.assertEqual((self.arms[flagged]["delivered"], self.arms[plain]["delivered"]), (True, False))

    def test_a_running_worker_follows_a_change_to_its_user_settings(self):
        self.assertEqual({k: a["delivered"] for k, a in self.reload.items()}, {"L1": False, "L2": True, "L3": True})
        self.assertIn("system:peer_message_hold", self.reload["L3"]["receiver_events"], "L3 was held before it was released")

    def test_the_receipts_hold_no_message_id_path_or_key(self):
        for path in EVIDENCE.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            for needle in ("/home/", "/var/tmp", "/run/user", "probe-dummy", '"msg_id":"0', '"msg_id":"9'):
                self.assertNotIn(needle, text, path.name)


if __name__ == "__main__":
    unittest.main()
