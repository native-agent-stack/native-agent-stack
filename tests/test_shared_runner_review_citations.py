"""Keep shared-runner review/helper citations name-only without private inputs."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEX64 = re.compile(r'\b[0-9a-fA-F]{64}\b')
REVIEW_FIELDS = (
    ('evidence/artifacts/adaptive-paper-shared-runner-corrections-20261015/receipt.json',
     'review_inputs', 'file'),
    ('evidence/artifacts/adaptive-paper-shared-runner-corrections-20261015/round3/receipt.json',
     'review_records', 'path'),
    ('evidence/artifacts/adaptive-paper-committed-exit-priority-20261015/receipt.json',
     'review_inputs', 'name'),
    ('evidence/artifacts/adaptive-paper-committed-exit-priority-20261015/fold1/receipt.json',
     'review_inputs', 'name'),
)


def name_only(records, name_key):
    return bool(records) and isinstance(records, list) and all(
        isinstance(row, dict) and set(row) == {name_key}
        and isinstance(row[name_key], str) and bool(row[name_key].strip())
        and not HEX64.search(row[name_key]) for row in records)


class SharedRunnerReviewCitations(unittest.TestCase):
    def test_published_review_records_have_only_names(self):
        for path, collection, field in REVIEW_FIELDS:
            with self.subTest(path=path, collection=collection):
                payload = json.loads((ROOT / path).read_text())
                # Never emit a rejected record's values in assertion output.
                self.assertTrue(name_only(payload[collection], field),
                                'review references must contain only nonempty names')

    def test_helper_citation_has_no_content_digest(self):
        document = (ROOT / 'docs/decisions/2026-10-13-adaptive-paper-sell-chunks.md').read_text()
        citations = re.findall(r'`cc-tools/nas_land\.sh`.*?(?=\n\s*\n|\Z)',
                               document, flags=re.S)
        self.assertGreater(len(citations), 0)
        self.assertEqual(sum(bool(HEX64.search(text)) for text in citations), 0,
                         'helper citations must stay name-only')

    def test_reintroduced_digest_fields_are_rejected(self):
        # Synthetic schema mutations only: no unpublished bytes or real digest
        # values are read, copied into a fixture, or printed on failure.
        for field in ('file', 'path', 'name'):
            for digest_key in ('sha256', 'bytes', 'transport_sha256', 'fixture_sha256',
                               'digest', 'content_hash'):
                with self.subTest(field=field, digest_key=digest_key):
                    self.assertTrue(name_only([{field: 'review.md'}], field))
                    self.assertFalse(name_only([{field: 'review.md',
                                                 digest_key: 'synthetic-value'}], field))

    def test_empty_or_digest_disguised_as_a_name_is_rejected(self):
        for field in ('file', 'path', 'name'):
            for value in ('', '   ', 'review.md sha256 ' + '0' * 64):
                with self.subTest(field=field, empty=not value.strip()):
                    self.assertFalse(name_only([{field: value}], field))
        self.assertFalse(name_only([], 'name'))


if __name__ == '__main__':
    unittest.main()
