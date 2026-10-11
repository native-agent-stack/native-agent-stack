"""Doc-contract regressions for the ai-memory capture correction (CC correction #144) in
docs/memory-landscape-maintenance.md.

Two corrected statements are pinned, each to its upstream mechanism:

1. The documented capture check must be runnable. ai-memory's `hook` subcommand requires `--event`, `--agent` and
   `--server-url` (HookArgs, crates/ai-memory-cli/src/cli.rs:2957-2966 at v2.6.0 = 89bd8ded, unchanged at v2.6.3), so a
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


def correction_section(text):
    start = text.index("**Correction, 2026-10-10 (CC correction #144).**")
    end = text.find("\n\n`CLAUDE_SETTINGS`", start)
    return text[start:end if end != -1 else len(text)]


class CaptureCheckCommandTests(unittest.TestCase):
    def test_documented_check_capture_command_carries_the_required_hook_arguments(self):
        section = correction_section(DOC.read_text(encoding="utf-8"))
        blocks = re.findall(r"```sh\n(.*?)```", section, re.S)
        commands = [b for b in blocks if "--check-capture" in b]
        self.assertTrue(commands, "the correction must give the check as a runnable sh block")
        command = " ".join(commands[0].split())
        for argument in ("hook", "--event", "--agent", "--server-url", "--check-capture", "--data-dir"):
            self.assertIn(argument, command, f"the documented check lacks {argument}")
        self.assertNotIn("`ai-memory hook --check-capture`", section, "the bare form exits 2")


class EnrollmentStatementTests(unittest.TestCase):
    def test_enrollment_statement_matches_the_documented_worktree_design(self):
        section = correction_section(DOC.read_text(encoding="utf-8"))
        self.assertIn("Worktrees and the capture marker", section)
        self.assertIn(".worktreeinclude", section)
        self.assertRegex(section, r"a worktree below it .* is enrolled too")
        self.assertIn("must never carry or inherit it", section)
        self.assertNotRegex(section, r"lane worktrees[^.;]*carry none", "worktrees under the checkout inherit the marker")


if __name__ == "__main__":
    unittest.main()
