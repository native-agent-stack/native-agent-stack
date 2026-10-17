"""Record pins for the live Hindsight reranker and LLM-cap record: its host change, evidence, guard and rollback.

These tests pin the record's text, not the live host or upstream. They cover:
- the five host lines, with the home directory shown as `~`;
- the live latency table;
- what the candidate cap sets: at most 16 results per recall (recall_boost.py:208-212);
- the FP16 precondition of the GPU failure;
- the preregistered rule and every arm's figures;
- the LLM-cap evidence files, windows and counts;
- the watch, its triggers and its rollback;
- the private receipts, by file name.

The record carries no hex run except the public upstream pins, and no home-directory path.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs/decisions/2026-10-17-hindsight-live-reranker-and-llm-cap.md"
REVISION = "025501c4e0f9bbeb4c5b198318e0089ff061cc14"
PUBLIC_PINS = {
    REVISION,  # cross-encoder/ettin-reranker-150m-v1 on Hugging Face
    "3af1f97945392da8ef46217640641355928aeb59",  # nlpai-lab/LAMAR-600m on Hugging Face
    "39c65ffe2f140d0c84cee58566cad8900c5b9908",  # vectorize-io/hindsight v1.0.0
    "b0bf39968ba461c34b29372144794eff1be06f6d",  # UKPLab/sentence-transformers v6.1.0
}
# A digest-like run holds at least one letter a-f, in either case, at any length; all-digit runs are dates such as 20261017.
HEX_RUN = re.compile(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{7,}\b", re.I)
ENV_LINES = (
    "HINDSIGHT_API_RERANKER_PROVIDER=local",
    "HINDSIGHT_API_RERANKER_LOCAL_MODEL=~/.cache/huggingface/hub/models--cross-encoder--ettin-reranker-150m-v1/"
    f"snapshots/{REVISION}",
    "HINDSIGHT_API_RERANKER_MAX_CANDIDATES=16",
    "HINDSIGHT_API_RERANKER_LOCAL_FORCE_CPU=true",
    "HINDSIGHT_API_LLM_MAX_CONCURRENT=1",
)


def text():
    return RECORD.read_text(encoding="utf-8")


class HostChangeTests(unittest.TestCase):
    def test_the_record_carries_the_five_host_lines_with_home_shown_as_tilde(self):
        body = text()
        lines = set(body.splitlines())
        for line in ENV_LINES:
            with self.subTest(line=line.split("=", 1)[0]):
                self.assertIn(line, lines)
        self.assertIn("host lines with the home directory written as `~`", body)

    def test_the_record_states_the_live_latency_table_and_margin(self):
        body = text()
        for fact in ("| RRF, 09:22:18-09:22:22Z | 126 ms | 176 ms | 241 ms | 31-68 |",
                     "| ettin-150m, 09:23:46-09:26:03Z | 5,114 ms | 5,490 ms | 6,169 ms | 16 |",
                     "1.5 s under the preregistered 7,000 ms bound", "budget mid and max_tokens 4096"):
            with self.subTest(fact=fact):
                self.assertIn(fact, body)

    def test_the_record_says_what_the_candidate_cap_sets(self):
        body = text()
        for fact in ("**At most 16 results per recall.**", "`engine/search/recall_boost.py:208-212`",
                     "a pool of 16 or fewer passes unchanged",
                     "unless\n    `HINDSIGHT_API_RECALL_STRATEGY_BOOSTS` is set (empty by default, `config.py:1347`)"):
            with self.subTest(fact=fact):
                self.assertIn(fact, body)
        self.assertNotIn("instead of 34-86", body)

    def test_the_gpu_failure_states_its_fp16_precondition(self):
        body = text()
        for fact in ("`HINDSIGHT_API_RERANKER_LOCAL_FP16` defaults to false (`config.py:1292`, `engine/cross_encoder.py:221`)",
                     "`engine/cross_encoder.py:344-345`", "`engine/local_device.py:117`",
                     "A float32 placement on the GPU was not measured."):
            with self.subTest(fact=fact):
                self.assertIn(fact, body)

    def test_the_record_names_the_watch_its_triggers_its_host_paths_and_the_rollback(self):
        body = text()
        for fact in ("`hindsight-reranker-watch.timer` runs `hindsight-reranker-watch.service` every 5 minutes",
                     "exceeds 7,000 ms (decided once at least 10 recalls exist)",
                     "ends in `_failed` and names recall or observations",
                     "`~/.local/share/native-agent-stack/hindsight-reranker-watch/watch.py`",
                     "Set `HINDSIGHT_API_RERANKER_PROVIDER=rrf`, remove the three other reranker lines"):
            with self.subTest(fact=fact):
                self.assertIn(fact, body)


class EvidenceTests(unittest.TestCase):
    def test_the_recall_table_and_the_preregistered_rule(self):
        body = text()
        for fact in ("| 40/60 | 0.4394 | 2,930.0 ms |", "| 39/60 | 0.4529 | 7,416.0 ms, above the 7,000 ms bound |",
                     "| 34/60 | 0.4408 | 5,976.9 ms |", "| RRF | 19/60 | 0.2749 | 121.6 ms |",
                     "Pick the non-RRF arm with the highest in_top3, with ties broken by MRR."):
            with self.subTest(fact=fact):
                self.assertIn(fact, body)

    def test_the_llm_cap_evidence_names_its_files_windows_and_counts(self):
        body = text()
        for fact in ("`hindsight-llm-cap/before.jsonl`, `after.jsonl` and `after-cap1.jsonl`",
                     "4 of 16 chat calls succeeded in 06:46Z-07:00Z", "12 of 15 succeeded in 07:03Z-07:17Z",
                     "live at 07:02:17Z", "`n_slots = 1`", "#22797 (07:03:54Z)"):
            with self.subTest(fact=fact):
                self.assertIn(fact, body)
        self.assertNotIn("22-101.5 s", body)

    def test_the_private_receipts_are_cited_by_name(self):
        body = text()
        for name in ("RECEIPT-recall-20261017.md", "RECEIPT-fit-a2-20261017.md", "RECEIPT-live-switch-20261017.md",
                     "RECALL-PREREGISTRATION-20261017.md"):
            with self.subTest(name=name):
                self.assertIn(f"`{name}`", body)

    def test_the_only_hex_runs_are_the_public_pins(self):
        self.assertEqual({run.lower() for run in HEX_RUN.findall(text())}, PUBLIC_PINS)

    def test_the_hex_guard_catches_either_case_and_any_length(self):
        self.assertTrue(HEX_RUN.search("sha256 DEADBEEF1234"))
        self.assertTrue(HEX_RUN.fullmatch("a" * 80))
        self.assertIsNone(HEX_RUN.search("receipt 20261017"))

    def test_the_record_holds_no_home_directory_path(self):
        self.assertNotIn("/home/", text())


if __name__ == "__main__":
    unittest.main()
