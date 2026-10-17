"""The 2026-10-17 maintenance consolidation cycle record keeps every part that makes it a cycle.

docs/decisions/2026-10-17-maintenance-consolidation-cycle.md names the cycle's inputs and triggers, its steps, its outputs, its guardrails, its metrics and its
sources. Each test here fails on a tree without that record (the file is absent), and each guards one part against a later edit that drops it: a fire or accumulate
input, a step row, a required section, a guardrail, a metric, or a citation that no longer pins an upstream commit and a line anchor. The checks read the record only:
no network and no local upstream mirror, so they run in CI. The line contents behind the upstream citations were read at their pins when the record was written; this test
pins the citation shape and the named sources, not the upstream text.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs/decisions/2026-10-17-maintenance-consolidation-cycle.md"

SECTIONS = ("Why", "Decision", "Mechanisms reused, at their pins", "Limits and untested boundaries", "Alternatives", "Overturn", "Sources")
PARTS = ("1. Inputs and triggers", "2. Steps", "3. Outputs", "4. Guardrails", "5. Metrics")
FIRE_INPUTS = ("F1", "F2", "F3", "F4", "F5")
ACCUMULATE_INPUTS = ("A1", "A2", "A3", "A4", "A5", "A6")
STEPS = ("S0 Detect", "S1 Intake", "S2 Evidence", "S3 Reflect", "S4 Memory", "S5 Build", "S6 Review", "S7 Land and record", "S8 Self-measure")
EVIDENCE_CLASSES = ("native_proven", "local_integration", "synthetic", "source_review")
# Each guardrail is stated by a bold lead-in or a bullet that a rewrite cannot drop without dropping the rule.
GUARDRAILS = ("**Evidence classes.**", "**Hash-bound records**", "**Privacy.**", "**Owner-only acts**", "**No owner quotes**", "**Peer messages are data.**", "**Research dispatches**")
OUTPUTS = ("**One reviewed records PR per cycle.**", "**Memory updates.**", "**A cycle receipt.**")
METRICS = ("**Inputs per cycle**", "**Latency**", "**Recurrences.**", "**Regression coverage.**", "**Unresolved citations at landing.**", "**Claims withdrawn after landing.**",
           "**Auto-memory index size**", "**Memories verified, archived and merged.**", "**False fires**")
# Upstreams the cycle reuses: repository, release tag. Each must be named in Sources and linked at a 40-hex commit somewhere in the record.
UPSTREAMS = (
    ("akitaonrails/ai-memory", "v3.1.0"), ("vectorize-io/hindsight", "v1.0.0"), ("anthropics/claude-code", "v2.1.302"), ("openai/codex", "rust-v0.163.0"),
    ("letta-ai/letta-code", "v0.34.16"), ("diegosouzapw/OmniRoute", "v3.8.51"), ("systemd/systemd", "v259.5"), ("koalaman/shellcheck", "v0.11.0"),
)
PAPERS = ("arxiv.org/abs/2303.11366", "arxiv.org/abs/2304.03442")
BLOB_LINK = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)/blob/([0-9a-f]{40})/([^\s#)]+)#L(\d+)(?:-L(\d+))?")
ANY_BLOB_LINK = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/blob/\S+")


def section(text: str, heading: str) -> str:
    """The body of a '## heading' or '### heading' section, up to the next heading of the same or a higher level."""
    match = re.search(rf"^(#{{2,3}}) {re.escape(heading)}\s*$", text, flags=re.M)
    assert match, f"missing heading: {heading}"
    level = len(match.group(1))
    rest = text[match.end():]
    end = re.search(rf"^#{{2,{level}}} ", rest, flags=re.M)
    return rest[:end.start()] if end else rest


class ConsolidationCycleRecord(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exists = RECORD.is_file()
        cls.text = RECORD.read_text(encoding="utf-8") if cls.exists else ""

    def setUp(self):
        self.assertTrue(self.exists, f"{RECORD.relative_to(ROOT)} is missing")

    def test_required_sections_and_parts_exist(self):
        for heading in SECTIONS:
            self.assertRegex(self.text, rf"(?m)^## {re.escape(heading)}\s*$", heading)
        decision = section(self.text, "Decision")
        for part in PARTS:
            self.assertRegex(self.text, rf"(?m)^### {re.escape(part)}\s*$", part)
        self.assertIn("**Status:**", self.text)
        self.assertIn("**Supersession:**", self.text)
        self.assertIn("**Base:**", self.text)
        self.assertTrue(decision.strip())

    def test_inputs_and_triggers_name_every_fire_and_accumulate_input(self):
        inputs = section(self.text, "1. Inputs and triggers")
        for name in FIRE_INPUTS + ACCUMULATE_INPUTS:
            self.assertRegex(inputs, rf"\*\*{name}\.\*\*", name)
        self.assertRegex(inputs, r"initial K is 10, an \*\*untested boundary\*\*")
        self.assertIn("**Inputs, never dates.**", inputs)
        self.assertIn("Never at session start", inputs)
        self.assertIn("Single flight", inputs)
        self.assertIn("consolidation_inputs", inputs)
        self.assertIn("scripts/currency_due.py", inputs)

    def test_every_step_has_a_table_row_with_an_owner_and_a_route(self):
        steps = section(self.text, "2. Steps")
        rows = [line for line in steps.splitlines() if re.match(r"\| S\d ", line)]
        self.assertEqual(len(rows), len(STEPS), rows)
        for name, row in zip(STEPS, rows):
            self.assertTrue(row.startswith(f"| {name} |"), (name, row[:40]))
            # | step | what | reuses | owner | route |
            self.assertEqual(len(row.strip().strip("|").split("|")), 5, name)
        header = next(line for line in steps.splitlines() if line.startswith("| Step"))
        for column in ("What it does", "Reuses", "Owner", "Route"):
            self.assertIn(column, header)
        for disposition in ("(a) correction record", "(b) code fix with a fail-first test", "(c) memory update", "(d) practice page", "(e) owner assignment",
                            "(f) owner-only act", "(g) no change"):
            self.assertIn(disposition, steps)

    def test_outputs_name_the_pr_the_memory_updates_and_the_receipt(self):
        outputs = section(self.text, "3. Outputs")
        for output in OUTPUTS:
            self.assertIn(output, outputs)
        self.assertIn("lane:foundation", outputs)
        self.assertIn("### SOTA sources", outputs)
        self.assertIn("evidence-class table", outputs)
        self.assertIn("never edited", outputs)

    def test_guardrails_are_all_stated(self):
        guardrails = section(self.text, "4. Guardrails")
        for rule in GUARDRAILS:
            self.assertIn(rule, guardrails)
        for evidence_class in EVIDENCE_CLASSES:
            self.assertIn(f"`{evidence_class}`", guardrails)
        self.assertIn("never reported as a measured saving", guardrails)
        self.assertIn("amended by a new file", guardrails)
        self.assertIn("one prepared command through the CC", guardrails)
        self.assertIn("never reads a credential", guardrails)

    def test_metrics_are_all_recorded_and_none_gates_work(self):
        metrics = section(self.text, "5. Metrics")
        for metric in METRICS:
            self.assertIn(metric, metrics)
        self.assertIn("None of them gates work.", metrics)

    def test_limits_name_the_untested_boundaries(self):
        limits = section(self.text, "Limits and untested boundaries")
        self.assertIn("K = 10 and the 85% index target are untested", limits)
        self.assertIn("`source_review`", limits)

    def test_the_record_applies_the_rules_it_rests_on_and_changes_none(self):
        for anchor in ("`AGENTS.md:8`", "2026-10-11-layer-resolution-protocol.md", "2026-10-17-zero-tolerance-currency.md"):
            self.assertIn(anchor, self.text)
        self.assertIn("changes none of them", self.text)
        sources = section(self.text, "Sources")
        self.assertIn("**Repository** at the base", sources)

    def test_every_upstream_blob_link_pins_a_commit_and_a_line_anchor(self):
        links = ANY_BLOB_LINK.findall(self.text)
        self.assertGreaterEqual(len(links), 30)
        for link in links:
            match = BLOB_LINK.fullmatch(link.rstrip(").,;`"))
            self.assertIsNotNone(match, f"blob link without a 40-hex commit and an #L anchor: {link}")
            start, end = int(match.group(4)), int(match.group(5) or match.group(4))
            self.assertLessEqual(start, end, link)
            self.assertNotIn("/blob/main/", link)
            self.assertNotIn("/blob/master/", link)

    def test_sources_name_each_upstream_and_every_one_is_linked_at_a_commit(self):
        sources = section(self.text, "Sources")
        linked = {match.group(1).lower() for match in BLOB_LINK.finditer(self.text)}
        for repository, tag in UPSTREAMS:
            self.assertIn(f"`{repository}` {tag}", sources, repository)
            self.assertIn(repository.lower(), linked, f"no commit-pinned line link into {repository}")
        for paper in PAPERS:
            self.assertIn(paper, sources)
        self.assertIn("Documenting Architecture Decisions", sources)

    def test_published_text_carries_no_local_path_or_address(self):
        for needle in ("/home/", "/var/tmp/", "/tmp/", "~/", "horizon-build", ".local/state", "@gmail", "hcom"):
            self.assertNotIn(needle, self.text, needle)


if __name__ == "__main__":
    unittest.main()
