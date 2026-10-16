"""Synthetic controls for the published native-capture masking boundary."""
import importlib.util
import hashlib
import json
import datetime
import re
import sys
from unittest.mock import patch
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "evidence/artifacts/final-prep-semantic-rag-20261016/mask_capture.py"
SPEC = importlib.util.spec_from_file_location("semantic_rag_capture_mask", MODULE)
MASK = importlib.util.module_from_spec(SPEC)
_prior_bytecode = sys.dont_write_bytecode
try:
    sys.dont_write_bytecode = True
    SPEC.loader.exec_module(MASK)
finally:
    sys.dont_write_bytecode = _prior_bytecode


class CaptureMaskTests(unittest.TestCase):
    def test_preserves_non_private_bytes_and_native_failure(self):
        raw = b"\x1b[31mFAIL\x1b[0m\r\n2 failed; 3 passed\n\x00\xff"
        self.assertEqual(MASK.mask_capture(raw), raw)

    def test_masks_paths_without_dropping_failure_or_line(self):
        raw = b'error at "/home/example/private/file.py:12"\npath=/Users/example/file\n'
        expected = b'error at "<PRIVATE_HOME_PATH>"\npath=<PRIVATE_HOME_PATH>\n'
        masked = MASK.mask_capture(raw)
        self.assertEqual(masked, expected)
        self.assertEqual(masked.count(b"\n"), raw.count(b"\n"))

    def test_is_deterministic_and_idempotent(self):
        raw = b"/home/example/file\nresult: 107 files; 2517 tests\n"
        first = MASK.mask_capture(raw)
        self.assertEqual(first, MASK.mask_capture(raw))
        self.assertEqual(first, MASK.mask_capture(first))

    def test_preserves_public_paths_and_empty_stream(self):
        raw = b"/work/socraticode/tests/unit/example.test.ts\n/runtime/vllm/module.py\n"
        self.assertEqual(MASK.mask_capture(raw), raw)
        self.assertEqual(MASK.mask_capture(b""), b"")

    def test_masks_uuid_tokens_without_hiding_error_counts(self):
        uuid = b"22222222" + b"-2222-4222-8222-222222222222"
        raw = b'Bad Request pointId=' + uuid + b'; 2 failed\n'
        self.assertEqual(MASK.mask_capture(raw), b'Bad Request pointId=<UUID>; 2 failed\n')

    def test_masks_explicit_scratch_root_and_preserves_native_result(self):
        scratch = b"/var/tmp/synthetic-private-root"
        raw = b'{"status":"written","out_dir":"' + scratch + b'/packets","packet_count":20}\n'
        expected = b'{"status":"written","out_dir":"<PRIVATE_SCRATCH_ROOT>/packets","packet_count":20}\n'
        masked = MASK.mask_capture(raw, scratch_root=scratch)
        self.assertEqual(masked, expected)
        self.assertEqual(MASK.mask_capture(masked, scratch_root=scratch), expected)
        self.assertEqual(MASK.mask_capture(b"/work/packets\n", scratch_root=scratch), b"/work/packets\n")


class PublishedCaptureContractTests(unittest.TestCase):
    def test_http_outcome_index_preserves_every_native_status(self):
        root = Path(__file__).resolve().parents[1]
        outcome = json.loads((MODULE.parent / "qdrant-http-outcomes.json").read_text())
        lines = (root / outcome["source"]).read_text().splitlines()
        pattern = re.compile(r'"(\S+) (\S+) HTTP/[^\"]+" (\d{3}) ')
        native = []
        for line_number, line in enumerate(lines, 1):
            if "actix_web::middleware::logger" in line:
                match = pattern.search(line)
                self.assertIsNotNone(match)
                native.append({"line": line_number, "method": match[1], "target": match[2], "status": int(match[3])})
        self.assertEqual(outcome["requests"], native)
        self.assertEqual(len(native), outcome["request_count"])
        for status, count in outcome["counts"].items():
            self.assertEqual(sum(row["status"] == int(status) for row in native), count)

    def test_download_hashes_match_published_sources_and_follow_completion(self):
        root = Path(__file__).resolve().parents[1]
        verification = json.loads((MODULE.parent / "artifact-verification.json").read_text())
        native = json.loads((MODULE.parent / "native-checks.json").read_text())
        commands = {row["name"]: row for row in native["commands"]}
        for binding in verification["bindings"]:
            download = commands[binding["download_command"]]
            hashed = commands[binding["hash_command"]]
            self.assertEqual(download["return_code"], 0)
            self.assertEqual(hashed["return_code"], 0)
            self.assertEqual(binding["download_finished_at"], download["finished_at"])
            self.assertEqual(binding["hash_started_at"], hashed["started_at"])
            self.assertLess(datetime.datetime.fromisoformat(download["finished_at"]), datetime.datetime.fromisoformat(hashed["started_at"]))
            self.assertEqual(binding["actual_sha256"], binding["expected_sha256"])
            for key, expected in [("actual_source", binding["actual_sha256"]), ("expected_source", binding["expected_sha256"])]:
                path, number = binding[key].rsplit(":", 1)
                line = (root / path).read_text().splitlines()[int(number) - 1]
                self.assertIn(expected, line)

    def test_corrupt_supporting_stream_hash_is_rejected(self):
        record = json.loads((MODULE.parent / "native-checks.json").read_text())
        record["supporting_service_streams"][0]["sha256"] = "0" * 64
        with patch.object(json, "loads", return_value=record):
            with self.assertRaises(AssertionError):
                self.test_complete_published_streams_match_recorded_hashes()

    def test_uncaptured_child_status_is_not_parent_success(self):
        native = json.loads((MODULE.parent / "native-checks.json").read_text())
        invoke = json.loads((MODULE.parent / "invoke-evidence.json").read_text())
        qdrant = next(row for row in invoke["components"] if row["id"] == "qdrant")
        self.assertTrue(all(row["return_code"] is None for row in native["supporting_service_streams"]))
        self.assertIsNone(qdrant["return_codes"][2])

    def test_complete_published_streams_match_recorded_hashes(self):
        root = Path(__file__).resolve().parents[1]
        record = json.loads((MODULE.parent / "native-checks.json").read_text())
        self.assertGreaterEqual(len(record["commands"]), 11)
        for command in record["commands"]:
            self.assertIsInstance(command["return_code"], int)
            self.assertTrue(command["command"])
            self.assertNotIn("output_excerpt", command)
            for stream in command["streams"].values():
                raw = (root / stream["path"]).read_bytes()
                self.assertEqual(len(raw), stream["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), stream["sha256"])
                self.assertFalse(stream["raw_digest_published"])
        for stream in record["supporting_service_streams"]:
            raw = (root / stream["path"]).read_bytes()
            self.assertEqual(len(raw), stream["bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), stream["sha256"])
            self.assertFalse(stream["raw_digest_published"])
            self.assertIsNone(stream["return_code"])
            self.assertTrue(stream["return_code_gap"])

    def test_reported_counts_have_exact_native_line_witnesses(self):
        root = Path(__file__).resolve().parents[1]
        record = json.loads((MODULE.parent / "native-checks.json").read_text())
        for value in record["values"]:
            lines = (root / value["path"]).read_text().splitlines()
            self.assertEqual(lines[value["line"] - 1], value["text"])


if __name__ == "__main__":
    unittest.main()
