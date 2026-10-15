"""The isolation and client-core rows carry the command center's 2026-10-15 rulings on the vendor sandbox's side effects.

On 2026-10-14/15 sandboxed Claude Code runs in worktrees of the shared repository left `.git/config.lock`, an empty read-only
placeholder that bwrap creates for a write-protected path that does not exist, in the shared `.git`. While it existed every
lane's git config writes failed (`could not lock config file`). The 2.1.300 binary's sandbox write-protects `.git/config`,
`.git/config.lock`, `.git/config.worktree(.lock)`, `.git/hooks`, `.git/worktrees` and more, and a worktree's common directory
is the main `.git`. The command center adopted the own-clone rule; the same runs left placeholders under
C:\\Program Files\\ClaudeCode, which the client-core row watches. CHANGELOG 2.1.98 adds a PID-namespace subprocess sandbox
when CLAUDE_CODE_SUBPROCESS_ENV_SCRUB is set, which a measured run showed independent of sandbox.enabled. These checks pin
that the rows say so, on both surfaces a session reads (slots.json and the layer page).
"""

from __future__ import annotations

import json
import re
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / ".claude/skills/claude-native-practice/reference"


def page_notes(page: str, slot_id: str) -> str:
    section = page.split(f"\n## {slot_id}\n", 1)[1].split("\n## ", 1)[0]
    notes = [line[len("- **Notes:** "):] for line in section.splitlines() if line.startswith("- **Notes:** ")]
    assert len(notes) == 1, (slot_id, len(notes))
    return notes[0]


class SandboxSideEffectRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.slots = {s["id"]: s for s in json.loads((REFERENCE / "slots.json").read_text(encoding="utf-8"))["slots"]}

    def test_the_sandbox_row_carries_the_own_clone_rule_on_both_surfaces(self):
        notes = self.slots["sandbox"]["notes"]
        self.assertEqual(notes, page_notes((REFERENCE / "isolation.md").read_text(encoding="utf-8"), "sandbox"))
        for phrase in ("own clone", "never in the shared main checkout or one of its worktrees", ".git/config.lock",
                       "removed with its stat recorded", "persists more than 10 minutes"):
            self.assertIn(phrase, notes)

    def test_the_sandbox_row_names_the_env_scrub_subprocess_sandbox(self):
        notes = self.slots["sandbox"]["notes"]
        self.assertIn("CLAUDE_CODE_SUBPROCESS_ENV_SCRUB", notes)
        self.assertIn("CHANGELOG 2.1.98", notes)
        self.assertRegex(notes, r"whatever sandbox\.enabled says")

    def test_the_client_core_row_watches_the_windows_placeholders(self):
        notes = self.slots["client-core"]["notes"] or ""
        self.assertEqual(notes, page_notes((REFERENCE / "native-clients.md").read_text(encoding="utf-8"), "client-core"))
        self.assertIn("managed-settings.d", notes)
        self.assertTrue(re.search(r"re-check when the Windows client is next upgraded", notes), notes)


    def test_the_correction_links_a_reviewable_source_record_with_pinned_locators(self):
        # Local review P2 at 6a6c3bf7 (decision :458-459): the correction cited the lane's working files for its binary
        # offsets and probes. It now links an in-repository record that pins the binary by sha256 and gives each offset.
        decision = (ROOT / "docs/decisions/2026-10-09-claude-code-native-practice.md").read_text(encoding="utf-8")
        record_path = "evidence/artifacts/sandbox-own-clone-20261015/SOURCE-RECORD.md"
        self.assertIn(record_path, decision)
        self.assertNotIn("LEAD-C-sandbox-20261015.md", decision)
        record = (ROOT / record_path).read_text(encoding="utf-8")
        self.assertIn("674deba0bba9aee479f4503c438b49303b6fdd304b9a471b14977aaec5215453", record)
        for offset in ("110513208", "216332417", "216588603"):
            self.assertIn(offset, record)
        self.assertTrue((ROOT / "evidence/artifacts/sandbox-own-clone-20261015/probe.sh").is_file())

    def test_the_signature_check_the_record_claims_is_retained_and_binds_the_binary(self):
        # GPT read of #1129 at efa0b45a (P2): the record said the GPG check was in the floor decision's 2026-10-14
        # addendum, which this tree does not contain. The check is retained beside the record, with the public manifest,
        # signature and key it verified, and the manifest's linux-x64 checksum equals the binary the offsets refer to.
        base = ROOT / "evidence/artifacts/sandbox-own-clone-20261015"
        record = (base / "SOURCE-RECORD.md").read_text(encoding="utf-8")
        self.assertIn("release-signature-2.1.300.json", record)
        for cited in set(re.findall(r"docs/decisions/[\w.-]+\.md", record)):
            self.assertIn("2.1.300", (ROOT / cited).read_text(encoding="utf-8"), cited)
        receipt = json.loads((base / "release-signature-2.1.300.json").read_text(encoding="utf-8"))
        for source in receipt["sources"].values():
            self.assertEqual(hashlib.sha256((base / source["file"]).read_bytes()).hexdigest(), source["sha256"])
        manifest = json.loads((base / "release-2.1.300/manifest.json").read_text(encoding="utf-8"))
        binary = "674deba0bba9aee479f4503c438b49303b6fdd304b9a471b14977aaec5215453"
        self.assertEqual((manifest["version"], manifest["platforms"]["linux-x64"]["checksum"]), ("2.1.300", binary))
        self.assertEqual(receipt["installed"]["sha256"], binary)
        self.assertTrue(receipt["gpg_result"].startswith("Good signature"))

if __name__ == "__main__":
    unittest.main()
