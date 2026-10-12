"""Doc-contract regressions for the ai-memory capture corrections (CC corrections #144 and #149) in
docs/memory-landscape-maintenance.md.

The corrected statements are pinned, each to its upstream mechanism:

1. The documented capture check must be runnable. ai-memory's `hook` subcommand requires `--event`, `--agent` and
   `--server-url` (HookArgs, crates/ai-memory-cli/src/cli.rs:2957-2966 at v2.6.0 = 89bd8ded, :2961-2970 at v2.6.3 = 385b81ea), so a
   bare `ai-memory hook --check-capture` exits 2. The PR's first version (8690d10f5) prescribed that bare form.
2. Enrollment follows the documented design (recipes/README.md, "Worktrees and the capture marker"). The marker walk
   climbs to $HOME (marker.rs:938-1025 at v2.6.0), so a worktree below the enrolled checkout inherits the marker, and
   `.worktreeinclude` copies it into Claude Code and Worktrunk worktrees. The first version's blanket claim that lane
   worktrees "carry none and are not captured" was false.
3. Correction #149 states the host's hook state as CC host measurements with a repo-safe locator, cites its ai-memory
   mechanism at the release the host runs (v2.6.3 = 385b81ea; the cited ranges are identical at v2.6.0 = 89bd8ded), and
   describes Codex hook trust as upstream does: re-rendering changes the computed current hash, the stored trusted_hash
   is unchanged, and the /hooks review writes the reviewed hash (docs/decisions/2026-10-04-codex-rtk-hook-qualified.md,
   Decision 1, read there at rust-v0.159.3 and re-read at rust-v0.162.1 = 092d3acd: discovery.rs hook_trust_status,
   hooks_rpc.rs write_hook_trusts). The first version said re-rendering changes trusted_hash.
4. The 2026-09-21 qualification prose that follows the corrections is dated and points at correction #149, so it cannot
   state the old host state in the present tense beside the correction. correction_149_section stops before that prose.
"""
import re
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "memory-landscape-maintenance.md"


def section_from(text, heading):
    start = text.find(heading)
    if start == -1:
        raise AssertionError(f"docs/memory-landscape-maintenance.md lacks the correction heading {heading}")
    ends = [i for i in (text.find("\n\n**Correction, ", start + len(heading)), text.find("\n\n`CLAUDE_SETTINGS`", start)) if i != -1]
    return text[start:min(ends) if ends else len(text)]


def correction_section(text):
    return section_from(text, "**Correction, 2026-10-10 (CC correction #144).**")


def correction_149_section(text):
    return section_from(text, "**Correction, 2026-10-11 (CC correction #149).**")


def cited_together(section, *needles):
    """Whether one parenthetical of the section carries every needle, so a cite keeps its pin."""
    return any(all(n in group for n in needles) for group in re.findall(r"\(([^)]*)\)", section))


def qualification_tail(text):
    """The 2026-09-21 qualification prose after the corrections, up to the next section."""
    start = text.find("\n\n`CLAUDE_SETTINGS`")
    end = text.find("\n## ", start)
    if start == -1 or end == -1:
        raise AssertionError("docs/memory-landscape-maintenance.md lacks the qualification prose after the corrections")
    return text[start:end]


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

    def test_correction_149_pins_its_mechanism_to_the_release_the_host_runs(self):
        section = correction_149_section(DOC.read_text(encoding="utf-8"))
        self.assertTrue(
            cited_together(section, "existing_capture_assistant_opt_in", "install_hooks.rs:689-701", ":1104-1109",
                           "v2.6.3 = 385b81ea", "v2.6.0 = 89bd8ded"),
            "the preserve-on-re-apply cite must carry the v2.6.3 pin beside the unchanged v2.6.0 one",
        )
        self.assertTrue(
            cited_together(section, "render_shared.rs:1425-1427", "install_hooks.rs:1142",
                           "v2.6.3 = 385b81ea", "v2.6.0 = 89bd8ded"),
            "the Stop-only render cite must carry the v2.6.3 pin beside the unchanged v2.6.0 one",
        )

    def test_correction_149_labels_the_host_state_as_cc_measurements_with_a_repo_safe_locator(self):
        text = DOC.read_text(encoding="utf-8")
        section = correction_149_section(text)
        self.assertRegex(
            section,
            r"CC host measurements, recorded as correction #149 in "
            r"`command-center/lessons-20261005/cc-corrections-20261005\.md` \(host state, not in this repository\)",
        )
        self.assertRegex(section, r"not re-read by this change")
        self.assertNotRegex(text, r"/(?:home|Users)/\w|/\.local/|(?<![\w$])[~]/", "a locator must not be a home or state path")

    def test_correction_149_describes_the_codex_trust_transition_as_the_decision_record_does(self):
        section = correction_149_section(DOC.read_text(encoding="utf-8"))
        self.assertNotRegex(
            section,
            r"re-render\w*[^.;:,]*\bchanges\b[^.;:,]*`trusted_hash`",
            "re-rendering changes the computed current hash, not the stored trusted_hash",
        )
        self.assertRegex(section, r"computed current hash")
        self.assertRegex(section, r"stored `trusted_hash` is unchanged")
        self.assertRegex(section, r"writes the reviewed current hash into `trusted_hash`")
        self.assertIn("docs/decisions/2026-10-04-codex-rtk-hook-qualified.md", section)
        self.assertTrue(
            cited_together(section, "hook_trust_status", "write_hook_trusts", "rust-v0.162.1 = 092d3acd"),
            "the trust mechanism must be cited at the installed Codex release",
        )


class OlderQualificationStatementTests(unittest.TestCase):
    def test_qualification_prose_after_the_corrections_is_dated_and_points_at_correction_149(self):
        tail = qualification_tail(DOC.read_text(encoding="utf-8"))
        claims = [p for p in tail.split("\n\n") if re.search(r"opted in|trusted|captured outcome", p)]
        self.assertGreaterEqual(len(claims), 2, "the Stop-excerpt and Codex-trust paragraphs must stay")
        for paragraph in claims:
            self.assertIn("At the 2026-09-21 qualification", paragraph, "an undated present-tense host claim")
            self.assertIn("correction #149", paragraph, "the current host state lives in the correction")
        self.assertNotRegex(tail, r"excerpts are separately opted in")
        self.assertNotRegex(tail, r"\bIn this qualification\b")


if __name__ == "__main__":
    unittest.main()
