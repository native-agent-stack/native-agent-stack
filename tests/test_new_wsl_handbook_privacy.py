"""Public handbook privacy: inspect source values in memory; report counts only."""
import json
from pathlib import Path
import unittest

from scripts import build_new_wsl_handbook as handbook


ROOT = Path(__file__).resolve().parents[1]


def source_quotations(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"owner_verbatim", "verbatim"} and isinstance(child, str):
                yield child
            yield from source_quotations(child)
    elif isinstance(value, list):
        for child in value:
            yield from source_quotations(child)


def all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from all_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_strings(child)


def verbatim_fields(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"owner_verbatim", "verbatim"}:
                yield key
            yield from verbatim_fields(child)
    elif isinstance(value, list):
        for child in value:
            yield from verbatim_fields(child)


class HandbookPrivacyTests(unittest.TestCase):
    def test_nested_source_fields_become_attributed_summaries_without_mutating_inputs(self):
        synthetic = {
            "slot_id": "context-supply", "date_utc": "2026-10-03",
            "history": [{"authority": {"owner_verbatim": "synthetic private fixture A",
                                       "verbatim": "synthetic private fixture B"}}],
        }
        before = json.dumps(synthetic)
        public = handbook.public_handbook_data(synthetic)
        self.assertEqual(json.dumps(synthetic), before)
        self.assertEqual(len(list(verbatim_fields(public))), 0)
        self.assertEqual(handbook.public_handbook_data(public), public)
        summary = public["history"][0]["authority"]["owner_paraphrase"]
        self.assertEqual(summary["date"], "2026-10-03")
        self.assertIn("they/them", summary["attribution"])
        self.assertTrue(summary["summary"].startswith("They "))

    def test_rendered_handbook_omits_source_quotes_and_copied_authority_prose(self):
        # Source records stay where they already exist. No copy, digest or quote
        # of their text is retained in a fixture, assertion message or test log.
        source = json.loads((ROOT / handbook.DEFAULTS_MANIFEST).read_text())
        protected = list(source_quotations(source))
        row = next(row for row in source["slots"] if row["slot_id"] == "agent-messaging")
        protected += [row["resolution"][key] for key in ("posture", "reason")]
        variants = {variant for text in protected for variant in
                    (text, json.dumps(text, ensure_ascii=False)[1:-1], handbook.cell(text)) if variant}
        for filename, raw in handbook.render(ROOT).items():
            rendered = raw.decode()
            count = sum(variant in rendered for variant in variants)
            self.assertEqual(count, 0, filename + ": protected source-text matches (count only)")
        data = json.loads(handbook.render(ROOT)[handbook.OUTPUTS[1]])
        self.assertEqual(len(list(verbatim_fields(data))), 0,
                         "Public data must not retain verbatim source fields")

    def test_attributed_public_paraphrases_contain_no_quotation_marks(self):
        # #1116 PublicationSurfaces at39b3fcaf, tests/test_session_relaunch.py:660-693.
        # Check the attributed publication fields, not quoted shell commands in
        # unrelated Markdown tables; retain no private phrase in the test itself.
        data = json.loads(handbook.render(ROOT)[handbook.OUTPUTS[1]])
        prose = []
        def walk(value):
            if isinstance(value, dict):
                if "owner_paraphrase" in value:
                    prose.extend(all_strings(value["owner_paraphrase"]))
                if value.get("slot_id") == "agent-messaging":
                    prose.extend(value["resolution"][key] for key in ("posture", "reason"))
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(data)
        self.assertGreater(len(prose), 0)
        self.assertEqual(sum(any(q in text for q in ('"', "\u201c", "\u201d")) for text in prose), 0,
                         "Quoted attributed prose in public decision summaries (count only)")

    def test_public_authority_explanation_is_a_dated_paraphrase(self):
        data = json.loads(handbook.render(ROOT)[handbook.OUTPUTS[1]])
        record = next(slot["record"] for layer in data["layers"] for slot in layer.get("default_slots", [])
                      if slot["record"]["slot_id"] == "agent-messaging")
        for field in ("posture", "reason"):
            self.assertTrue(record["resolution"][field].startswith("Paraphrased 2026-10-16:"),
                            "Public authority prose must identify its paraphrase date")


if __name__ == "__main__":
    unittest.main()
