"""Gap-ledger rows for the isolation layer (2026-10-15): B2-0003, B4-0003 and C1-0022.

B2-0003: every worktree of a repository shares one refs/stash (git/git@67ad42147a7a, tag v2.53.0, the host's git:
Documentation/git-worktree.adoc:298-302, all refs under refs/ are shared except refs/bisect, refs/worktree and
refs/rewritten), so a lane parks unfinished work as a WIP commit on its own branch. The scratch-repository test repeats
the 2026-10-15 measurement; it passes before and after this change and fails if git stops sharing the stack, which
reopens the row.
B4-0003: background sessions (claude --bg, agent view) move into a worktree before editing, and worktree.bgIsolation
defaults to "worktree", blocking Edit and Write in the main checkout until EnterWorktree (agent-view.md:551,
settings-reference.md:5275-5281, fetched 2026-10-15T11:41:33Z). The route said the checks applied only to --worktree
and EnterWorktree sessions.
C1-0022: under sandbox.network.strictAllowlist the allowlist is allowedDomains plus WebFetch(domain:...) allow rules
(sandboxing.md:575, same fetch), so the strict route names its allowedDomains, taken from M1's network arm
(evidence/artifacts/claude-native-practice-20261009/probes-20261009.json:382-383). The host change is a proposal for the
command center as a host diff, not applied.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import hermetic_git_environment

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / ".claude/skills/claude-native-practice/reference"
PAGE = REF / "isolation.md"
PROBES = ROOT / "evidence/artifacts/claude-native-practice-20261009/probes-20261009.json"
STASH_RECORD = ROOT / "docs/decisions/2026-10-11-final-stack-review-corrections.md"


def row(slot_id):
    return next(s for s in json.loads((REF / "slots.json").read_text(encoding="utf-8"))["slots"] if s["id"] == slot_id)


def line(path, number):
    return path.read_text(encoding="utf-8").split("\n")[number - 1]


class StashRow(unittest.TestCase):
    """B2-0003."""

    def test_the_worktrees_route_parks_work_as_a_wip_commit_not_a_stash(self):
        route = row("worktrees")["route"]
        self.assertIn("parks unfinished work as a WIP commit on its own branch, not with `git stash`", route)
        self.assertIn("git-worktree.adoc:298-302, git v2.53.0", route)

    def test_the_notes_record_the_measurement_and_the_record_that_used_stash(self):
        notes = row("worktrees")["notes"]
        self.assertIn("Measured 2026-10-15 on git 2.53.0", notes)
        self.assertIn("docs/decisions/2026-10-11-final-stack-review-corrections.md:559", notes)
        self.assertIn("the WIP commit is the default, not a ban", notes)
        self.assertIn("native Git stash", line(STASH_RECORD, 559))

    def test_a_stash_pushed_in_one_worktree_is_popped_in_its_sibling(self):
        env = {**hermetic_git_environment(), "GIT_AUTHOR_NAME": "Synthetic Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
               "GIT_COMMITTER_NAME": "Synthetic Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}

        def git(cwd, *args):
            return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True).stdout

        with tempfile.TemporaryDirectory() as tmp:
            main, lane_a, lane_b = Path(tmp, "main"), Path(tmp, "lane-a"), Path(tmp, "lane-b")
            git(tmp, "init", "-q", "-b", "main", str(main))
            (main / "f.txt").write_text("base\n", encoding="utf-8")
            git(main, "add", "f.txt")
            git(main, "commit", "-q", "-m", "base")
            git(main, "worktree", "add", "-q", str(lane_a), "-b", "lane-a")
            git(main, "worktree", "add", "-q", str(lane_b), "-b", "lane-b")
            (lane_a / "f.txt").write_text("base\nlane-a work\n", encoding="utf-8")
            git(lane_a, "stash", "push", "-q", "-m", "lane-a wip")
            self.assertIn("lane-a wip", git(lane_b, "stash", "list"))
            git(lane_b, "stash", "pop", "-q")
            self.assertEqual((lane_b / "f.txt").read_text(encoding="utf-8"), "base\nlane-a work\n")
            self.assertEqual(git(lane_a, "stash", "list"), "")
            self.assertEqual((lane_a / "f.txt").read_text(encoding="utf-8"), "base\n")


class BackgroundIsolationRow(unittest.TestCase):
    """B4-0003."""

    def test_the_worktrees_route_covers_background_sessions(self):
        route = row("worktrees")["route"]
        for phrase in ("`claude --bg`", "`worktree.bgIsolation`, default `\"worktree\"`", "blocked until the session calls EnterWorktree",
                       "agent-view.md:551", "settings-reference.md:5275-5281"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, route)
        self.assertNotIn("apply only to `--worktree` and EnterWorktree sessions", route)

    def test_the_notes_carry_the_exceptions_the_versions_and_the_d4_measurement(self):
        notes = row("worktrees")["notes"]
        for phrase in ("agent-view.md:553-559", "`/background`", "for a write outside the working directory", "worktrees.md:95",
                       "since 2.1.154 (anthropics/claude-code@94506ff0 CHANGELOG.md:5037", "from 2.1.288",
                       "Piebald-AI/claude-code-system-prompts@0b7ce11f CHANGELOG.md:216", "(33888fe1)",
                       "Whether the key blocks a main-checkout edit was not measured"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, notes)

    def test_no_repository_settings_or_template_sets_background_isolation(self):
        # The route relies on the documented default; a tracked settings file or template that sets worktree.bgIsolation
        # (for example to "none") changes what the route says and has to change the row with it.
        paths = [ROOT / ".claude/settings.json", ROOT / "adoption/new-wsl-profile.json", *sorted((ROOT / "adoption/templates").glob("*.json"))]
        self.assertGreaterEqual(len(paths), 5)
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn("bgIsolation", path.read_text(encoding="utf-8"))


class SandboxAllowlistRow(unittest.TestCase):
    """C1-0022."""

    def test_the_sandbox_route_names_the_allowlist_and_its_source(self):
        route = row("sandbox")["route"]
        for phrase in ("`network.strictAllowlist` with an explicit `network.allowedDomains`", "sandboxing.md:575",
                       "frozen through M1 before rollout", "Host change proposed to the command center as a host diff, not applied"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, route)

    def test_the_route_list_is_m1s_network_arm(self):
        arms = json.loads(PROBES.read_text(encoding="utf-8"))["m1_sandbox"]["arms"]
        self.assertIn("network.allowedDomains [api.github.com, github.com]", arms["strict"])
        self.assertIn("allowedDomains 127.0.0.1, localhost", arms["remedy (round 2)"])
        route = row("sandbox")["route"]
        for domain in ("api.github.com", "github.com", "127.0.0.1", "localhost"):
            with self.subTest(domain=domain):
                self.assertIn(f"`{domain}`", route)
        self.assertIn("probes-20261009.json:382-383, :393, :399", route)

    def test_the_cited_m1_lines_say_what_the_route_takes_from_them(self):
        self.assertIn('"strict": "base + network.allowedDomains [api.github.com, github.com]', line(PROBES, 382))
        self.assertIn('"remedy (round 2)": "strict + allowedDomains 127.0.0.1, localhost', line(PROBES, 383))
        self.assertIn("they answer 200 in base and in strict when 127.0.0.1 is allowlisted", line(PROBES, 393))
        self.assertIn("strictAllowlist in user scope denies a host outside the allowlist", line(PROBES, 399))


class PageRendersTheRows(unittest.TestCase):
    def test_the_layer_page_renders_the_changed_fields(self):
        text = PAGE.read_text(encoding="utf-8")
        for slot_id in ("sandbox", "worktrees"):
            with self.subTest(slot=slot_id):
                self.assertIn(f"- **Route:** {row(slot_id)['route']}\n", text)
        self.assertIn(f"- **Notes:** {row('worktrees')['notes']}\n", text)


if __name__ == "__main__":
    unittest.main()
