"""The native-practice documentation corrections stay aligned with the sources they rest on.

Each check pins one claim that was wrong before the correction, so a later edit cannot silently restore it:

- examples/claude-native/workflows/README.md, `## Adopt`: the installer flags the step tells a reader to run exist in
  tools/adoption/install_claude_profile.py (`--only workflows`, and `--remove-workflows`, which that parser accepts
  only with `--only workflows`), and the directory the first manual step tells the reader to copy resolves from the
  README (it said `agents/`, which is not beside the README).
- docs/native-dashboards.md, the live-archive bullet: it cites the upstream v0.44.0 source line that makes
  `AGENTSVIEW_DATA_DIR` override the default directory, and its session count and date match the dated probe artifact.
  The launcher file itself is a host file, so the repository cannot read it; the probe artifact is the retained reading.

The Layer 12 F4 checks also keep release boundaries, adopted inputs and source availability
distinct from runtime qualification. These are repository-text checks, not runtime acceptance.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import install_claude_profile as icp  # noqa: E402

README = ROOT / "examples/claude-native/workflows/README.md"
DASHBOARDS = ROOT / "docs/native-dashboards.md"
PROBES = ROOT / "evidence/artifacts/claude-native-practice-20261009/probes-20261009.json"
REF = ROOT / ".claude/skills/claude-native-practice/reference"
UPSTREAM_DATA_DIR = ("https://github.com/kenn-io/agentsview/blob/413a87f7bfbd67b2815b1119ac51abc1efbeeaba/"
                     "internal/config/config.go#L2051-L2053")


def adopt_section() -> str:
    return README.read_text(encoding="utf-8").split("\n## Adopt\n", 1)[1].split("\n## ", 1)[0]


def live_archive_bullet() -> str:
    text = DASHBOARDS.read_text(encoding="utf-8")
    return text.split("- On the workstation the unit serves the directory its launcher sets,", 1)[1].split("\n- ", 1)[0]


class PracticeReferenceSourceTests(unittest.TestCase):
    """Layer 12 F4: source locators and release boundaries, not client-runtime acceptance.

    The npm locator is valid in its explicitly cited v2.1.295 source at
    602df92bf481ed904533e95c09f740f40aab5aed:CHANGELOG.md (sha256
    c0b1f9aa313a8021d863ec0053c047b0acc792d74e04af9c7741d3ecd23c3d1a).
    Other release lines were independently checked in anthropics/claude-code at
    c017428c8c27e604840435048d5bce6a9a22c040:CHANGELOG.md (sha256
    57fde96b3318543cfe7ba6622950620a81d4d40e3e0e196ae1de49ccd1fd00da).
    The hooks reference fetched 2026-10-18 (sha256 bc2ab6b0362a88086c62b7cb4bc3b539a552b37d5958e325882b2e1c3d94ac4a)
    documents onFailure and excludes completion events. Adoption and worker availability
    are checked against repository inputs, rather than inferred from this prose.
    """

    def setUp(self):
        self.rows = {row["id"]: row for row in json.loads((REF / "slots.json").read_text())["slots"]}

    def page_section(self, page: str, slot_id: str) -> str:
        return (REF / page).read_text().split(f"\n## {slot_id}\n", 1)[1].split("\n## ", 1)[0]

    def test_npm_deprecation_cites_the_line_in_the_named_changelog(self):
        evidence = self.rows["client-core"]["evidence"]
        self.assertIn("CHANGELOG@v2.1.295 L7262 (npm deprecation, 2.1.15)", evidence)

    def test_instruction_rule_triggers_keep_their_separate_release_boundaries(self):
        evidence = "; ".join(self.rows["instruction-files"]["evidence"])
        self.assertIn("CHANGELOG@v2.1.302 L1076 (2.1.288, Write and Edit)", evidence)
        self.assertIn("L670 (2.1.293, single-file Bash views)", evidence)

    def test_interactive_auto_mode_is_not_dated_to_the_headless_change(self):
        row = self.rows["settings-permissions"]
        self.assertIn("`auto` mode (unconfigured interactive sessions start in it since 2.1.284)", row["alternatives"])
        self.assertIn("CHANGELOG@v2.1.302 L1516 (2.1.284, interactive auto-mode start)", row["evidence"])
        self.assertNotIn("M46 evidence sentence (auto start mode, 2.1.285)", row["supersedes"])

    def test_hooks_note_matches_the_adopted_floor(self):
        pins = json.loads((ROOT / "adoption/pins-linux-x86_64.json").read_text())
        floor = next(tool["version"] for tool in pins["tools"] if tool["id"] == "claude-code")
        note = self.rows["hooks"]["notes"]
        self.assertIn(f"The repository's pinned floor is {floor} (adoption/pins-linux-x86_64.json)", note)
        self.assertNotIn("which ignores `onFailure`", note)
        template = json.loads((ROOT / "adoption/templates/claude.settings.template.json").read_text())
        guard = next(hook for group in template["hooks"]["PreToolUse"] for hook in group["hooks"]
                     if "secret_path_guard.py" in hook.get("command", ""))
        self.assertEqual(guard["onFailure"], "block")
        self.assertIn("halt_error(2)", guard["command"])
        self.assertIn("secret-path wrapper also refuses a missing script", note)
        route = self.rows["hooks"]["route"]
        self.assertIn("adoption/templates/claude.settings.template.json", route)
        self.assertNotIn("proposal with the command center", route)

    def test_completion_note_cites_documented_failure_scope(self):
        note = self.rows["loops-completion"]["notes"]
        self.assertNotIn("not yet in hooks.md", note)
        self.assertIn("https://code.claude.com/docs/en/hooks#block-the-action-when-a-hook-fails", note)
        self.assertIn("no effect on Stop, SubagentStop, TaskCompleted or TeammateIdle", note)

    def test_review_worker_availability_does_not_claim_host_qualification(self):
        for name in ("README.md", "worker.py", "probes.py"):
            self.assertTrue((ROOT / "tools/claude-review-worker" / name).is_file())
        route = self.rows["pr-review-pre-cue"]["route"]
        self.assertNotIn("Not available yet", route)
        self.assertNotIn("#953, open", route)
        self.assertIn("implemented in this repository", route)
        self.assertIn("host qualification", route)
        self.assertIn("tools/claude-review-worker/README.md", route)

    def test_corrected_fields_are_carried_on_the_layer_pages(self):
        for page, slot_id, fields in (
            ("native-clients.md", "client-core", ("evidence",)),
            ("native-clients.md", "instruction-files", ("evidence",)),
            ("native-clients.md", "settings-permissions", ("alternatives", "evidence", "supersedes")),
            ("native-clients.md", "hooks", ("route", "notes")),
            ("workers.md", "loops-completion", ("notes",)),
            ("git-github-automation.md", "pr-review-pre-cue", ("route",)),
        ):
            section = self.page_section(page, slot_id)
            for field in fields:
                values = self.rows[slot_id][field]
                for value in values if isinstance(values, list) else [values]:
                    with self.subTest(slot=slot_id, field=field):
                        self.assertIn(value, section)


class PracticeAdoptionCoherenceTests(unittest.TestCase):
    """Bindings at NAS 4f827e637f256fee4f0534f395431b722aabc43c:

    docs/decisions/2026-10-10-skills-claude-native-practice-row.md:82-86 explicitly
    ties this first-party lifecycle pin to the selected manifest row. Correction #161
    (tests/test_provenance_digest_custody.py:1-12) excludes unpublished home-state
    digests from public receipts. These checks do not inspect the private lock.
    """

    def test_the_first_party_lifecycle_source_follows_the_selected_skill_pin(self):
        manifest = json.loads((ROOT / "adoption/skills/manifest.json").read_text())
        selected = next(row for row in manifest["skills"] if row["name"] == "claude-native-practice")
        lifecycle = json.loads((ROOT / "catalogs/landscape/skills-lifecycle.json").read_text())
        source = next(row for row in lifecycle["sources"]
                      if row["source_id"] == "seathatflowsinourveins-native-agent-stack")
        self.assertEqual(source["pin"], selected["ref"])

    def test_the_public_install_receipt_withholds_private_lock_digests(self):
        receipt = json.loads((ROOT / "evidence/artifacts/claude-native-practice-refresh-20261018-final/receipt.json").read_text())
        preservation = receipt["preservation"]
        private_fields = {key: value for key, value in preservation.items() if key.startswith("other_")}
        self.assertFalse(any(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                             for value in private_fields.values()),
                         "A public receipt cannot bind unpublished private lock bytes with a digest")
        self.assertGreaterEqual(preservation["other_global_skill_lock_entries"], 0)
        self.assertIn("not publicly reproducible", preservation["other_entries_verification"])

    def test_the_snapshot_note_dates_the_current_source_correction(self):
        snapshot = json.loads((ROOT / "evidence/artifacts/claude-native-practice-20261009/claude-native-slot-manifest.json").read_text())
        self.assertIn("2026-10-18", snapshot["snapshot"]["current_decision_source"]["note"])

    def test_the_platform_install_guide_uses_the_adopted_floor(self):
        pins = json.loads((ROOT / "adoption/pins-linux-x86_64.json").read_text())
        floor = next(tool["version"] for tool in pins["tools"] if tool["id"] == "claude-code")
        text = (ROOT / "adoption/platforms/linux-wsl2.md").read_text()
        current = re.search(r"On main the pin is ([0-9.]+) and a floor", text)
        self.assertIsNotNone(current)
        self.assertEqual(current.group(1), floor)
        self.assertIn(f"whose `--version` reports {floor} or newer", text)


class WorkflowsReadmeAdoptTests(unittest.TestCase):
    def test_the_installer_accepts_the_flags_the_step_names(self):
        args = icp.build_parser().parse_args(["--only", "workflows", "--remove-workflows"])
        self.assertEqual(args.only, ["workflows"])
        self.assertTrue(args.remove_workflows)

    def test_the_step_names_those_flags(self):
        section = adopt_section()
        self.assertIn("tools/adoption/install_claude_profile.py --only workflows", section)
        self.assertIn("`--only workflows --remove-workflows`", section)

    def test_the_first_manual_step_names_a_directory_beside_the_readme_tree(self):
        step = adopt_section().split("\n1. ", 1)[1].split("\n2. ", 1)[0]
        match = re.match(r"Copy (?:\[`([^`]+)`\]\([^)]*\)|`([^`]+)`) into", step)
        self.assertIsNotNone(match, step[:80])
        target = match.group(1) or match.group(2)
        self.assertTrue((README.parent / target).is_dir(), f"{target} does not resolve from {README.parent}")


class DashboardsLiveArchiveTests(unittest.TestCase):
    def test_the_bullet_cites_the_upstream_source_for_the_data_directory(self):
        bullet = live_archive_bullet()
        self.assertIn(UPSTREAM_DATA_DIR, bullet)
        self.assertIn("AGENTSVIEW_DATA_DIR", bullet)

    def test_the_bullet_matches_the_probe_artifact(self):
        bullet = live_archive_bullet()
        probes = json.loads(PROBES.read_text(encoding="utf-8"))
        coverage = probes["old_archive_coverage"]
        self.assertEqual(coverage["old_sessions_missing_from_live"], 0)
        self.assertIn(f"every one of its {coverage['old_sessions']:,} sessions", " ".join(bullet.split()))
        self.assertIn(f"deleted on {coverage['run_utc'][:10]}", " ".join(bullet.split()))
        self.assertIn(PROBES.relative_to(ROOT).as_posix(), bullet)


if __name__ == "__main__":
    unittest.main()
