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
3. Correction #149 states the host's hook state as CC host measurements with a repo-safe, state-root-relative locator
   (coordination/lessons-20261005/cc-corrections-20261005.md; the first form, command-center/lessons-20261005/..., named
   a directory the ledger does not sit under, CC correction #180). It cites its ai-memory mechanism at the release the
   host runs (v2.6.3 = 385b81ea; the cited ranges are identical at v2.6.0 = 89bd8ded) and describes Codex hook trust as
   upstream does: re-rendering changes the computed current hash, the stored trusted_hash is unchanged, and the /hooks
   review writes the reviewed hash (docs/decisions/2026-10-04-codex-rtk-hook-qualified.md, Decision 1, read there at
   rust-v0.159.3 and re-read at rust-v0.162.1 = 092d3acd: discovery.rs hook_trust_status, hooks_rpc.rs
   write_hook_trusts). The first version said re-rendering changes trusted_hash.
4. The 2026-09-21 qualification prose that follows the corrections is dated and points at correction #149, so it cannot
   state the old host state in the present tense beside the correction. correction_149_section stops before that prose.
5. The lead that introduces the documented `install-hooks --capture-assistant` commands is dated and cites the retained
   2026-09-21 record (native-commands.json:295-393: the three installers were run with the flag, exit 0 each), so it is
   a record of that day and not the host's hook state. Correction #149 then cannot say that "the earlier hook
   applications ran without the flag", which the same record contradicts: it names the later flagless applications
   (the #144 repair and the 2.6.3 re-stage) and leaves the loss in between as host history not reconstructed here.
6. The Codex count is one profile's seven. hook-trust.json lists seven ai-memory commands in each of two profiles (native
   :35-77, Desktop :279-321), so correction #149 bounds its 0 of 7 and its Codex conclusions to the native profile and
   claims nothing about the Desktop profile, which was not measured.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "memory-landscape-maintenance.md"
ARTIFACTS = ROOT / "evidence" / "artifacts" / "memory-landscape-20260921"
INSTALLERS = ("hook-install-claude", "hook-install-codex", "hook-install-desktop")


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


def installer_lead(text):
    """The paragraph that introduces the documented `install-hooks --capture-assistant` commands."""
    block = text.find("```sh\nai-memory install-hooks --agent claude-code --capture-assistant")
    if block == -1:
        raise AssertionError("docs/memory-landscape-maintenance.md lacks the documented install-hooks commands")
    end = text.rfind("\n\n", 0, block)
    return text[text.rfind("\n\n", 0, end) + 2:end].strip()


def artifact_lines(name):
    return (ARTIFACTS / name).read_text(encoding="utf-8").splitlines()


def record_span(lines, name):
    """1-based first and last line of the pretty-printed command record `name` in native-commands.json."""
    start = next(i for i, line in enumerate(lines) if line == f'    "{name}": {{')
    end = next(i for i in range(start, len(lines)) if lines[i] in ("    },", "    }"))
    return start + 1, end + 1


def find_record(node, name):
    if isinstance(node, dict):
        if name in node:
            return node[name]
        for value in node.values():
            found = find_record(value, name)
            if found is not None:
                return found
    return None


def profile_lines(lines, block, prefix):
    """1-based lines of the hook keys that start with `prefix` in one hook-trust.json hooks/list block."""
    start = next(i for i, line in enumerate(lines) if line == f'    "{block}": {{')
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith('    "')), len(lines))
    return [i + 1 for i in range(start, end) if f'"key": "{prefix}' in lines[i]]


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
            r"`coordination/lessons-20261005/cc-corrections-20261005\.md` \(host state, not in this repository\)",
        )
        self.assertNotIn("command-center/lessons-20261005", text, "the ledger has no command-center/ parent (CC correction #180)")
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

    def test_qualification_prose_bounds_the_current_codex_state_to_the_native_profile(self):
        tail = " ".join(qualification_tail(DOC.read_text(encoding="utf-8")).split())
        self.assertIn("For the current native Codex state see correction #149", tail)
        self.assertIn("the Desktop profile was not measured", tail)
        self.assertNotIn("For the current Codex state", tail, "an unbounded Codex conclusion")


class InstallerLeadTests(unittest.TestCase):
    def test_lead_is_dated_cites_the_retained_installer_record_and_points_at_correction_149(self):
        text = DOC.read_text(encoding="utf-8")
        lead = " ".join(installer_lead(text).split())
        self.assertNotIn("The actual upstream installers were run", text, "an undated claim beside correction #149")
        self.assertIn("At the 2026-09-21 qualification the upstream installers were run with `--capture-assistant`", lead)
        self.assertIn("not the hook state now", lead)
        self.assertIn("correction #149", lead)
        lines = artifact_lines("native-commands.json")
        first = record_span(lines, INSTALLERS[0])[0]
        last = record_span(lines, INSTALLERS[-1])[1]
        self.assertIn(f"evidence/artifacts/memory-landscape-20260921/native-commands.json:{first}-{last}", lead)

    def test_the_cited_installer_record_carries_the_flag_and_exit_zero(self):
        data = json.loads((ARTIFACTS / "native-commands.json").read_text(encoding="utf-8"))
        for name in INSTALLERS:
            record = find_record(data, name)
            self.assertIsNotNone(record, f"native-commands.json lacks {name}")
            self.assertIn("--capture-assistant", record["argv"], f"{name} was run without the flag")
            self.assertEqual(record["exit_code"], 0, name)

    def test_correction_149_dates_the_flagless_applications_instead_of_contradicting_the_record(self):
        section = " ".join(correction_149_section(DOC.read_text(encoding="utf-8")).split())
        self.assertNotRegex(section, r"[Tt]he earlier hook applications", "the 2026-09-21 installers carried the flag")
        self.assertIn("The qualification's own installers carried the flag (`native-commands.json:295-393`", section)
        self.assertIn(
            "so the flag was lost between then and 2026-10-11; the loss path is host history not reconstructed here", section
        )
        self.assertIn(
            "Two later applications, the #144 repair (a bare re-apply) and the 2.6.3 re-stage of 2026-10-10, ran without the flag",
            section,
        )
        self.assertIn("was not in force on this host on 2026-10-11", section)


class CodexProfileScopeTests(unittest.TestCase):
    def test_correction_149_counts_both_codex_profiles_and_bounds_its_count_to_the_native_one(self):
        section = " ".join(correction_149_section(DOC.read_text(encoding="utf-8")).split())
        trust = artifact_lines("hook-trust.json")
        native = profile_lines(trust, "hook-trust-before", "$HOME/.codex/hooks.json:")
        desktop = profile_lines(trust, "hook-trust-desktop-before", "$DESKTOP_HOME_PARENT/.codex/hooks.json:")
        self.assertEqual((len(native), len(desktop)), (7, 7), "seven ai-memory Codex commands in each profile")
        self.assertIn(f"native (`$HOME/.codex/hooks.json`, `hook-trust.json:{native[0]}-{native[-1]}`)", section)
        self.assertIn(
            f"Desktop (`$DESKTOP_HOME_PARENT/.codex/hooks.json`, `hook-trust.json:{desktop[0]}-{desktop[-1]}`)", section
        )
        self.assertIn(f"{len(native) + len(desktop)} in all", section)
        self.assertIn("The 0 of 7 is the native profile's", section)
        self.assertIn("the Desktop profile's seven were not measured", section)
        self.assertIn("claims nothing about their flag or trust state", section)

    def test_correction_149_bounds_its_codex_conclusions_to_the_native_profile(self):
        section = " ".join(correction_149_section(DOC.read_text(encoding="utf-8")).split())
        self.assertIn("Native Codex is pending a trust refresh", section)
        self.assertIn("so native Codex assistant capture stays off until then", section)
        self.assertNotRegex(section, r"so Codex assistant capture stays off until then", "an unbounded Codex conclusion")


if __name__ == "__main__":
    unittest.main()
