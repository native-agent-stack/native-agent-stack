"""Gap-ledger rows of 2026-10-15 for the token-efficiency page, and two rows the ledger left without a slot.

C3-0006 (context-compaction): 2.1.299 added idle compaction (anthropics/claude-code@94506ff0d3bd9185f1752da36e968775021fb48f
CHANGELOG.md:97-98). At 2.1.300 it is on by default for an interactive terminal conversation on the one-hour cache TTL
whose context has reached 200,000 tokens, about 54 minutes after its last request (https://code.claude.com/docs/en/
settings-reference.md:2964-2983, fetched 2026-10-15T11:39:24Z, sha256
8ba90434d2801f9e7b3dc44e304bea0e3ca94c25d540cdcf9763369deeb355e4). The command center's ruling of 2026-10-14 leaves
`idleCompaction` unset. The slot mapped compacting before an idle gap only to a manual /compact, and the idleCompaction
disposition still gave the 2026-10-06 reason (a rollout that `true` cannot force), which the C2 re-check found stale.
A3-0031 (settings-permissions): NativeStack2604's user settings hold enableArtifact false (exact-key read
2026-10-15T11:40:22Z) and the catalog had no row for the key. The record is a host choice, not a template default:
re-applying the template keeps keys it does not mention (tools/adoption/apply_claude_settings.py:323-329).
B2-0004 (pr-review-pre-cue): publish a PR description from a file and read it back, because GitHub answered 200 to
description updates over 262,144 bytes and kept the old description (measured 2026-10-11 on #991). The catalog-freshness
propose step's read-back runs in tests/test_catalog_freshness_propose.py.
The rows cite public pages, repository paths and commit SHAs only, never a lane record or a temporary path (the command
center's digest-custody rule of 2026-10-15).
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / ".claude/skills/claude-native-practice/reference"
DISPOSITIONS = ROOT / "catalogs/foundation/upstream-surface-dispositions.json"
TEMPLATE = ROOT / "adoption/templates/claude.settings.template.json"


def row(slot_id):
    return next(s for s in json.loads((REF / "slots.json").read_text(encoding="utf-8"))["slots"] if s["id"] == slot_id)


def disposition(key):
    (found,) = [r for r in json.loads(DISPOSITIONS.read_text(encoding="utf-8"))["rows"] if r["key"] == key]
    return found


class LedgerRowsTokenEfficiencyAndNew(unittest.TestCase):
    def test_context_compaction_names_idle_compaction_and_keeps_it_on(self):
        slot = row("context-compaction")
        for fragment in ("idle compaction", "CHANGELOG.md:97-98 at anthropics/claude-code@94506ff0d3bd9185f1752da36e968775021fb48f",
                         "settings-reference.md:2964-2983", "`idleCompaction` stays unset",
                         "the command center's ruling of 2026-10-14", "hooks.md:3251", "gap ledger C3-0006"):
            self.assertIn(fragment, slot["notes"])
        (source,) = [s for s in slot["primary_sources"] if s["practice"].startswith("Run compaction before an idle gap")]
        self.assertIn("idle compaction (2.1.299", source["native_mechanism"])

    def test_the_idle_compaction_disposition_cites_the_2_1_300_docs(self):
        found = disposition("claude:setting:idleCompaction")
        self.assertNotIn("rollout", found["reason"])
        self.assertIn("leave unset", found["reason"])
        self.assertEqual(found["source"], "https://code.claude.com/docs/en/settings-reference.md:2964-2983")
        self.assertEqual((found["disposition"], found["carrier"], found["version"]), ("declined", None, "2.1.300"))

    def test_enable_artifact_false_is_recorded_as_a_host_choice(self):
        found = disposition("claude:setting:enableArtifact")
        self.assertEqual((found["disposition"], found["value"], found["carrier"], found["scope"]),
                         ("enabled", False, "host user settings", "NativeStack2604"))
        self.assertEqual(found["source"], "https://code.claude.com/docs/en/settings-reference.md:5427-5443")
        self.assertNotIn("enableArtifact", json.loads(TEMPLATE.read_text(encoding="utf-8")))
        for fragment in ("`enableArtifact: false`", "settings-reference.md:5427-5443", "apply_claude_settings.py:323-329",
                         "gap ledger A3-0031"):
            self.assertIn(fragment, row("settings-permissions")["notes"])

    def test_pr_descriptions_are_published_from_a_file_and_read_back(self):
        for fragment in ("--body-file", "`gh pr view <pr> --json body`", "262,145", "an update of 262,144 bytes was stored",
                         "fcakyon/claude-codex-settings@216ec221fb9899dfaa5371413583b9e08ca89085:plugins/github-dev/skills/create-pr/SKILL.md:35,40",
                         "gap ledger B2-0004"):
            self.assertIn(fragment, row("pr-review-pre-cue")["notes"])

    def test_the_rows_cite_no_lane_record_or_temporary_path(self):
        texts = [row(slot_id)["notes"] for slot_id in ("context-compaction", "settings-permissions", "pr-review-pre-cue")]
        texts += [json.dumps(disposition(key)) for key in ("claude:setting:idleCompaction", "claude:setting:enableArtifact")]
        for text in texts:
            for path in ("/var/tmp", "/dev/shm", ".local/state", "coordination/", "screen-20261014"):
                self.assertNotIn(path, text)

    def test_the_pages_render_the_rows(self):
        for slot_id, page in (("context-compaction", "token-efficiency.md"), ("settings-permissions", "native-clients.md"),
                              ("pr-review-pre-cue", "git-github-automation.md")):
            with self.subTest(slot=slot_id):
                self.assertIn(f"- **Notes:** {row(slot_id)['notes']}\n", (REF / page).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
