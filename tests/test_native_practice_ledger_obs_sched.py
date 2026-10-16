"""Gap-ledger rows of 2026-10-15 for the observation-inference and scheduling-supervision layer pages.

A3-0090: the client templates set OTEL_METRICS_INCLUDE_ENTRYPOINT=true (off by default; env-vars.md:510,
monitoring-usage.md:156 and :584 at client 2.1.300), so metrics carry app.entrypoint. The usage row records the switch
and where the label stops today (the collector's transform/privacy metric allowlist), the dispositions catalog records it
as adopt-pending on the template, and the host steps go to the command center as a host diff.
B2-0005: signed in with the plan, claude -p, Agent SDK and third-party app runs draw the plan's usage limits (support
article 15036540, its 2026-06-15 and 2026-10-07 updates); the Max and Team API credits cover API-key runs only (17154008).
A5-0024, a correction: --resume and --continue restore CronCreate tasks and a backgrounded session keeps them firing
(scheduled-tasks.md:11, :228, :230; measured on this host 2026-10-15), so those paths list the tasks with CronList and
cancel stale ones with CronDelete (scheduled-tasks.md:159-160).
"""
import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / ".claude/skills/claude-native-practice/reference"
CLAUDE_TEMPLATES = (ROOT / "adoption/templates/claude.settings.template.json",
                    ROOT / "observability/collector/claude-settings.json.example")
# The repository profile and the 2604 profile, which the live collector on 2604 runs byte for byte (read 2026-10-15).
COLLECTOR_PROFILES = (ROOT / "observability/collector/collector.yaml",
                      ROOT / "evidence/artifacts/new-wsl-install-plan-20261002/config/otel.yaml")
DISPOSITIONS = ROOT / "catalogs/foundation/upstream-surface-dispositions.json"
HOST_DIFF = "proposed to the command center as a host diff"
CLAUDE_METRIC_KEEP = re.compile(r'keep_keys\(attributes, \[([^\]]*)\]\) where metric\.name != "codex\.hooks\.run"')


# Scratch roots and the private findings files' name, which repository text never cites (digest custody).
SCRATCH_MARKERS = ("/var/tmp", "/dev/shm", ".local/state", "FINDINGS-")

def row(slot_id):
    return next(s for s in json.loads((REF / "slots.json").read_text(encoding="utf-8"))["slots"] if s["id"] == slot_id)


def page(name):
    return (REF / name).read_text(encoding="utf-8")


class LedgerRowsObservationScheduling(unittest.TestCase):
    def test_the_client_templates_label_metrics_with_the_entrypoint(self):
        for path in CLAUDE_TEMPLATES:
            with self.subTest(path=path.name):
                env = json.loads(path.read_text(encoding="utf-8"))["env"]
                self.assertEqual(env.get("OTEL_METRICS_INCLUDE_ENTRYPOINT"), "true")

    def test_the_switch_is_adopt_pending_on_the_template(self):
        rows = {r["key"]: r for r in json.loads(DISPOSITIONS.read_text(encoding="utf-8"))["rows"]}
        found = rows.get("claude:env:OTEL_METRICS_INCLUDE_ENTRYPOINT")
        self.assertIsNotNone(found, "the template sets the switch, so the catalog records the decision")
        self.assertEqual((found["disposition"], found["carrier"], found["value"], found["source"]),
                         ("adopt-pending", "adoption/templates/claude.settings.template.json", "true",
                          "https://code.claude.com/docs/en/env-vars.md#L510"))

    def test_the_usage_row_records_the_entrypoint_label_and_its_sources(self):
        notes = row("usage-cost-monitoring")["notes"]
        for text in ("Entrypoint label (gap ledger A3-0090, 2026-10-15)", "`OTEL_METRICS_INCLUDE_ENTRYPOINT=true`",
                     "env-vars.md:510", "monitoring-usage.md:156", "monitoring-usage.md:584", "sha256 54351937e4d1",
                     "sha256 72374067fb00", "docs/decisions/2026-10-13-command-center-god-view.md:43-44", HOST_DIFF):
            with self.subTest(text=text):
                self.assertIn(text, notes)
        self.assertIn(f"- **Notes:** {notes}\n", page("observation-inference.md"))

    def test_the_usage_row_and_the_collector_agree_on_where_the_label_stops(self):
        # The label reaches Prometheus only if transform/privacy keeps it. While a profile drops it, the row says so; a
        # change that adds app.entrypoint to a profile's allowlist must update the row in the same change.
        notes = row("usage-cost-monitoring")["notes"]
        for profile in COLLECTOR_PROFILES:
            lists = [re.findall(r'"([^"]+)"', m.group(1))
                     for m in CLAUDE_METRIC_KEEP.finditer(profile.read_text(encoding="utf-8"))]
            with self.subTest(profile=str(profile.relative_to(ROOT))):
                self.assertEqual(len(lists), 1)
                self.assertIn("app.version", lists[0])
                self.assertNotIn("app.entrypoint", lists[0], "the collector keeps the label now: update the usage row")
                self.assertIn(str(profile.relative_to(ROOT)), notes)
        self.assertIn("do not list `app.entrypoint`, so the collector sums it away", notes)

    def test_the_usage_row_records_that_unattended_runs_draw_the_plan_limits(self):
        notes = row("usage-cost-monitoring")["notes"]
        for text in ("Plan limits (gap ledger B2-0005, 2026-10-15)", "draw the plan's usage limits",
                     "support article 15036540", "2026-06-15 update", "2026-10-07 update", "sha256 8712a0cd32c2",
                     "support article 17154008", "sha256 17185d5773b0",
                     "docs/decisions/2026-10-09-claude-code-gap-resolution.md:179-181"):
            with self.subTest(text=text):
                self.assertIn(text, notes)
        self.assertIn(f"- **Notes:** {notes}\n", page("observation-inference.md"))

    def test_resume_and_background_paths_list_and_cancel_restored_tasks(self):
        slot = row("scheduled-tasks")
        for text in ("`--resume` or `--continue`", "backgrounded session", "CronList", "CronDelete"):
            with self.subTest(route=text):
                self.assertIn(text, slot["route"])
        for text in ("Correction (gap ledger A5-0024, 2026-10-15)", "scheduled-tasks.md:11,230", "(:228)", "(:159-160)",
                     "sha256 8cb643f43a14", "fired at 07:36:00Z", "evidence/artifacts/d4-bg-trial-20261015/scheduled-task-carry.json",
                     "docs/native-workflow-writing-recovery-20260921.md:157",
                     "docs/decisions/2026-10-14-session-relaunch-after-wsl-restart.md:40"):
            with self.subTest(notes=text):
                self.assertIn(text, slot["notes"])
        text = page("scheduling-supervision.md")
        self.assertIn(f"- **Route:** {slot['route']}\n", text)
        self.assertIn(f"- **Notes:** {slot['notes']}\n", text)


    def test_the_custody_check_catches_a_planted_scratch_reference(self):
        """A synthetic negative control: a note citing a private findings file with a digest, here a synthetic one,
        fails the check that the rows pass."""
        digest = hashlib.sha256(b"synthetic findings bytes for the custody control").hexdigest()[:12]
        planted = f"measured in FINDINGS-9.md (sha256 {digest}) under /var/tmp"
        self.assertTrue([marker for marker in SCRATCH_MARKERS if marker in planted])

    def test_the_rows_cite_no_scratch_path_or_unpublished_digest(self):
        # Digest custody (command center, 2026-10-15): repository text cites committed files and public sources only.
        # The measurement is retained in the repository, and the host diff is named without a path. The check holds
        # no private value (the GPT read of #1158 at 8c03cbe5, P1): it looks for the scratch roots and the private
        # findings files' name, never for a digest of them.
        for slot_id in ("usage-cost-monitoring", "scheduled-tasks"):
            text = json.dumps(row(slot_id))
            for scratch in SCRATCH_MARKERS:
                with self.subTest(slot=slot_id, scratch=scratch):
                    self.assertNotIn(scratch, text)
        record = json.loads((ROOT / "evidence/artifacts/d4-bg-trial-20261015/scheduled-task-carry.json").read_text())
        self.assertEqual([o["event"] for o in record["observed"]], ["CronCreate tool call", "scheduled_task_fire"])

if __name__ == "__main__":
    unittest.main()
