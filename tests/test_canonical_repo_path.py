"""Guard: functional files name the repository's canonical path, never the path it had before it moved.

The repository moved from the personal account to the native-agent-stack organization. GitHub keeps the old path alive
only as a redirect: REST, git and web links follow it, the search API does not, and `github.repository`,
`pull.head.repo.full_name` and `gh run list` urls already report the new name. Code that builds a request or compares a
name against the old path therefore breaks quietly (publish-catalog never ran; the review worker read every pull request
as foreign). The old name must never be reused for a new repository: creating one drops the redirect (GitHub Docs,
"Transferring a repository", content/repositories/creating-and-managing-repositories/transferring-a-repository.md at
github/docs c008b66a92206bee5fbbad54ffbbde60451fb1f5).

The scan walks the file system (not git), so it also runs on a `git archive` tree. Historical records stay as they
are: evidence/, docs/decisions/, receipts and catalogs re-verify by hash, and a commit-pinned permalink still resolves
through the redirect. Each exception below names its reason; the test fails when an exception no longer applies.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = "native-agent-stack/native-agent-stack"
# The old path, in its plain, percent-encoded and JSON-escaped forms, in any case.
OLD_PATH = re.compile(r"seathatflowsinourveins(?:/|%2f|\\/)native-agent-stack", re.IGNORECASE)

# Directories and files the guard covers: where code, workflows, templates and units that call GitHub live.
SCAN_ROOTS = ("tools", "scripts", ".github/workflows", "adoption/templates")
SKIPPED_PARTS = {"__pycache__", ".git", "node_modules"}

# A documented historical file may keep the old path. The reason says why editing it would be wrong.
ALLOWED = {
    "tools/sota-convergence/landscape-sweep/README.md":
        "dated prose whose links are pinned to commit SHAs and pull request comments of the time",
    "tools/sota-convergence/landscape-sweep/templates.json":
        "prompt text only (no request); its bytes are bound by the frozen prompts_sha256 pins of "
        "tests.test_landscape_sweep_harness and by evidence/artifacts/model-routes-sweep-20261015/protocol.json",
    "tools/sota-convergence/reconciliations-20260922.json":
        "a dated reconciliation record of 2026-09-22 citing the repository by its URL then",
    "tools/runtime-worker-evidence/checks.json":
        "a blob link pinned to a commit SHA; evidence/receipts/omniroute-sdk-worker-0160-20261003.json records its sha256",
    "tools/local-pages/design-plan.md":
        "a dated design note whose source link is pinned to a commit SHA",
    "tools/sota-convergence/schemas/compact-coverage.json":
        "a JSON Schema $id is an identifier, not a fetch; compact manifests bind the schema bytes",
    "tools/sota-convergence/schemas/compact-coverage-start-closure-1.json":
        "a JSON Schema $id is an identifier, not a fetch; compact manifests bind the schema bytes",
    "tools/sota-convergence/schemas/compact-decision.json":
        "a JSON Schema $id is an identifier, not a fetch; compact manifests bind the schema bytes",
    "tools/sota-convergence/schemas/compact-decision-start-closure-1.json":
        "a JSON Schema $id is an identifier, not a fetch; compact manifests bind the schema bytes",
    "blueprints/runtime-workers/skills/manifest.json":
        "its claude-native-practice exclusion must equal main's adoption/skills/manifest.json row (source and "
        "commit-pinned tree url); tests.test_runtime_worker_skills enforces it, so both move together as one follow-up",
    "adoption/templates/wsl/stage1-receipt.example.json":
        "its clone step mirrors the install guides under adoption/platforms, which still name the old path "
        "and move together as one follow-up",
}


def scanned_files():
    seen = set()
    for top in SCAN_ROOTS:
        base = ROOT / top
        if base.is_dir():
            seen.update(path for path in base.rglob("*") if path.is_file())
    seen.update(path for path in (ROOT / "blueprints").rglob("manifest.json") if path.is_file())
    seen.update(path for path in ROOT.rglob("*.service")
                if path.is_file() and path.relative_to(ROOT).parts[0] not in ("evidence", "docs"))
    return sorted(path for path in seen if not SKIPPED_PARTS & set(path.relative_to(ROOT).parts))


def text_of(path: Path):
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


class CanonicalRepoPathTest(unittest.TestCase):
    def test_the_scan_covers_the_functional_files(self):
        names = {path.relative_to(ROOT).as_posix() for path in scanned_files()}
        for expected in (".github/workflows/publish-catalog.yml", "tools/claude-review-worker/worker.py",
                         "tools/claude-review-worker/essential-paths.json", "tools/local-pages/fleet_data.py",
                         "blueprints/runtime-workers/skills/manifest.json",
                         "tools/claude-review-worker/systemd/claude-review-worker.service"):
            self.assertIn(expected, names)
        self.assertGreater(len(names), 100)

    def test_no_functional_file_names_the_old_path(self):
        offenders = {}
        for path in scanned_files():
            name = path.relative_to(ROOT).as_posix()
            text = text_of(path)
            if text is None or name in ALLOWED:
                continue
            lines = [number for number, line in enumerate(text.splitlines(), 1) if OLD_PATH.search(line)]
            if lines:
                offenders[name] = lines
        self.assertEqual(offenders, {}, "name the canonical path " + CANONICAL + " (never recreate the old one)")

    def test_every_allowed_exception_still_exists_and_still_names_the_old_path(self):
        for name, reason in ALLOWED.items():
            with self.subTest(name=name):
                self.assertTrue(reason.strip())
                path = ROOT / name
                self.assertTrue(path.is_file(), f"{name} is gone: drop its exception")
                self.assertIn(path, scanned_files(), f"{name} is outside the scan: drop its exception")
                self.assertRegex(text_of(path) or "", OLD_PATH, f"{name} no longer names the old path: drop its exception")

    def test_workflow_repository_guards_name_the_canonical_repository(self):
        guards = {}
        for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for literal in re.findall(r"github\.repository\s*==\s*'([^']+)'", line):
                    guards[f"{path.name}:{number}"] = literal
        self.assertTrue(guards, "publish-catalog.yml guards on github.repository")
        self.assertEqual({where: literal for where, literal in guards.items() if literal != CANONICAL}, {})
        self.assertEqual(len([where for where in guards if where.startswith("publish-catalog.yml:")]), 2)

    def test_review_worker_configuration_names_the_canonical_repository(self):
        config = json.loads((ROOT / "tools/claude-review-worker/essential-paths.json").read_text(encoding="utf-8"))
        names = [item["repo"] for item in config["repositories"]]
        self.assertIn(CANONICAL, names)
        self.assertIn("seathatflowsinourveins/us-equities-trading", names)  # not moved: its path is unchanged

    def test_the_old_path_pattern_matches_its_forms(self):
        for sample in ("seathatflowsinourveins/native-agent-stack", "SeaThatFlowsInOurVeins/Native-Agent-Stack",
                       "repo%3Aseathatflowsinourveins%2Fnative-agent-stack",
                       "seathatflowsinourveins\\/native-agent-stack"):
            self.assertRegex(sample, OLD_PATH)
        for sample in (CANONICAL, "seathatflowsinourveins/us-equities-trading", "seathatflowsinourveins-native-agent-stack"):
            self.assertNotRegex(sample, OLD_PATH)


if __name__ == "__main__":
    unittest.main()
