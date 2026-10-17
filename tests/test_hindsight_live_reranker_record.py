"""The live Hindsight reranker and LLM-cap record states the host change, its evidence, its guard and its rollback.

The CC's #25997 (2026-10-17): a live host change gets its record promptly, with live p90 5,490 ms against eval
2,930 ms, the 1.5 s margin to the 7,000 ms bound, callers getting 16 results instead of 34-86, the rolling rollback
watch unit and the 7.1(b) receipt by file name. Private records are cited by name only, so the record carries no hex
run except the public Hugging Face revision of the model.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs/decisions/2026-10-17-hindsight-live-reranker-and-llm-cap.md"
REVISION = "025501c4e0f9bbeb4c5b198318e0089ff061cc14"
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
    def test_the_record_carries_the_five_env_lines_exactly(self):
        lines = set(text().splitlines())
        for line in ENV_LINES:
            with self.subTest(line=line.split("=", 1)[0]):
                self.assertIn(line, lines)

    def test_the_record_states_the_live_latency_margin_and_what_callers_receive(self):
        body = text()
        for fact in ("5,490 ms", "2,930 ms", "1.5 s under the preregistered 7,000 ms bound",
                     "16 results per recall instead of 34-86", "recall_boost.py:210-212"):
            with self.subTest(fact=fact):
                self.assertIn(fact, body)

    def test_the_record_names_the_watch_unit_and_the_rollback(self):
        body = text()
        self.assertIn("`hindsight-reranker-watch.timer` runs `hindsight-reranker-watch.service` every 5 minutes", body)
        self.assertIn("exceeds 7,000 ms", body)
        self.assertIn("Set `HINDSIGHT_API_RERANKER_PROVIDER=rrf`, remove the three other reranker lines", body)


class EvidenceCitationTests(unittest.TestCase):
    def test_the_private_receipts_are_cited_by_name(self):
        body = text()
        for name in ("RECEIPT-recall-20261017.md", "RECEIPT-fit-a2-20261017.md", "RECEIPT-live-switch-20261017.md",
                     "RECALL-PREREGISTRATION-20261017.md"):
            with self.subTest(name=name):
                self.assertIn(f"`{name}`", body)

    def test_the_only_hex_run_is_the_public_model_revision(self):
        # A digest-like run holds at least one letter a-f; all-digit runs are dates such as the receipts' 20261017.
        runs = set(re.findall(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{7,64}\b", text()))
        self.assertEqual(runs, {REVISION})


if __name__ == "__main__":
    unittest.main()
