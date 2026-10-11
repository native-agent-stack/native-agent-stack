"""Doc-contract regressions for the ai-memory capture corrections (CC corrections #144 and #149) in
docs/memory-landscape-maintenance.md.

Three corrected statements are pinned, each to its upstream mechanism:

1. The documented capture check must be runnable. ai-memory's `hook` subcommand requires `--event`, `--agent` and
   `--server-url` (HookArgs, crates/ai-memory-cli/src/cli.rs:2957-2966 at v2.6.0 = 89bd8ded, :2961-2970 at v2.6.3 = 385b81ea), so a
   bare `ai-memory hook --check-capture` exits 2. The PR's first version (8690d10f5) prescribed that bare form.
2. Enrollment follows the documented design (recipes/README.md, "Worktrees and the capture marker"). The marker walk
   climbs to $HOME (marker.rs:938-1025 at v2.6.0), so a worktree below the enrolled checkout inherits the marker, and
   `.worktreeinclude` copies it into Claude Code and Worktrunk worktrees. The first version's blanket claim that lane
   worktrees "carry none and are not captured" was false.
"""
import re
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "memory-landscape-maintenance.md"


def section_from(text, heading):
    start = text.index(heading)
    ends = [i for i in (text.find("\n\n**Correction, ", start + len(heading)), text.find("\n\n`CLAUDE_SETTINGS`", start)) if i != -1]
    return text[start:min(ends) if ends else len(text)]


def correction_section(text):
    return section_from(text, "**Correction, 2026-10-10 (CC correction #144).**")


def correction_149_section(text):
    return section_from(text, "**Correction, 2026-10-11 (CC correction #149).**")


class CaptureCheckCommandTests(unittest.TestCase):
    def test_documented_check_capture_command_carries_the_required_hook_arguments(self):
        section = correction_section(DOC.read_text(encoding="utf-8"))
        blocks = re.findall(r"```sh\n(.*?)```", section, re.S)
        commands = [b for b in blocks if "--check-capture" in b]
        self.assertTrue(commands, "the correction must give the check as a runnable sh block")
        for block in commands:
            command = " ".join(block.split())
            for argument in ("hook", "--event", "--agent", "--server-url", "--check-capture", "--data-dir"):
                self.assertIn(argument, command, f"a documented check lacks {argument}")
        self.assertNotIn("`ai-memory hook --check-capture`", section, "the bare form exits 2")


class EnrollmentStatementTests(unittest.TestCase):
    def test_enrollment_statement_matches_the_documented_worktree_design(self):
        section = correction_section(DOC.read_text(encoding="utf-8"))
        self.assertIn("Worktrees and the capture marker", section)
        self.assertIn(".worktreeinclude", section)
        self.assertRegex(section, r"a worktree below it .* is enrolled too")
        self.assertIn("must never carry or inherit it", section)
        self.assertNotRegex(section, r"lane worktrees[^.;]*carry none", "worktrees under the checkout inherit the marker")


class CaptureAssistantCorrectionTests(unittest.TestCase):
    def test_correction_149_states_the_opt_in_was_not_in_force_and_its_current_state(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("(CC correction #149)", text, "the doc must carry the dated #149 correction")
        section = correction_149_section(text)
        self.assertIn("2026-10-11", section)
        self.assertIn("--capture-assistant", section)
        self.assertRegex(section, r"not in force")
        self.assertRegex(section, r"0 of 9 Claude")
        self.assertRegex(section, r"0 of 7 Codex")

    def test_correction_149_says_only_the_stop_hook_carries_the_flag_and_codex_is_pending_trust(self):
        section = correction_149_section(DOC.read_text(encoding="utf-8"))
        self.assertRegex(section, r"Only the Stop hook carries")
        self.assertIn("trusted_hash", section)
        self.assertRegex(section, r"Codex is pending a trust refresh")

    def test_correction_149_cites_the_pinned_upstream_lines(self):
        section = correction_149_section(DOC.read_text(encoding="utf-8"))
        self.assertIn("89bd8ded", section)
        self.assertIn("install_hooks.rs:689-701", section)
        self.assertIn(":1104-1109", section)
        self.assertIn("render_shared.rs:1425-1427", section)

    def test_read_kit_marker_note_is_a_host_note_citing_gitignore(self):
        section = correction_149_section(DOC.read_text(encoding="utf-8"))
        self.assertIn("repositories commit the marker", section)
        self.assertIn(".gitignore:73", section)
        self.assertRegex(section, r"lives in the co-op's host state directory, not in this repository")


if __name__ == "__main__":
    unittest.main()
