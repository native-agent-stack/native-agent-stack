"""Synthetic projection/metadata tests; source excerpts are never E2E output."""
import json
import unittest

from publish_capture import public_pair, release_projection


class PublicationTests(unittest.TestCase):
    def test_fail_first_synthetic_prefix_is_declared_and_masked(self):
        raw = b"AssertionError: '/var/tmp/fixture[47 chars]tail'"
        output, receipt = public_pair(raw, b'{"exit_code": 1}', [],
                                      "small-fold-v1", "masking-before")
        self.assertEqual(output, b"AssertionError: '<private-scratch-prefix>[47 chars]tail'")
        self.assertEqual(json.loads(receipt)["exit_code"], 1)

    def release(self):
        return json.dumps({"info": {"name": "alpaca-py", "version": "0.44.0",
            "description": "PRIVATE-VENDOR-README", "author_email": "omit@example.invalid"},
            "urls": [{"filename": "alpaca_py-0.44.0-py3-none-any.whl",
                "url": "https://example.invalid/wheel", "digests": {"sha256": "a" * 64},
                "packagetype": "bdist_wheel", "unrelated": "omit"}], "extra": "omit"}).encode()

    def test_release_projection_is_an_allowlist(self):
        output = release_projection(self.release())
        projected = json.loads(output)
        self.assertEqual(projected["info"], {"name": "alpaca-py", "version": "0.44.0"})
        self.assertEqual(projected["urls"][0]["digests"]["sha256"], "a" * 64)
        for omitted in [b"PRIVATE-VENDOR-README", b"author_email", b"unrelated", b"extra"]:
            self.assertNotIn(omitted, output)

    def test_source_projection_is_labelled_and_native_rc_is_preserved(self):
        raw_receipt = json.dumps({"command": ["curl", "https://example.invalid"],
            "exit_code": 7, "declared_inputs": {"alpaca-py": "WRONG"},
            "started_utc": "start", "finished_utc": "finish"}).encode()
        output, receipt = public_pair(self.release(), raw_receipt, [], "fold-v1", "pypi-calendar")
        d = json.loads(receipt)
        self.assertEqual(d["capture_class"], "projected_native_source_capture")
        self.assertEqual(d["exit_code"], 7)
        self.assertEqual(d["declared_inputs"]["exchange-calendars"], "4.13.2")
        self.assertNotIn("alpaca-py", d["declared_inputs"])
        self.assertIn("metadata_correction", d)

    def test_non_source_output_is_only_masked(self):
        raw = b"native /var/tmp/fixture-long-private[40 chars]tail\r\n  "
        rules = [{"source": "/var/tmp/fixture-long-private-root", "placeholder": "<scratch>"}]
        output, receipt = public_pair(raw, b'{"exit_code": 0}', rules, "fold-v1", "recorder-tests-before")
        self.assertEqual(output, b"native <private-scratch-prefix>[40 chars]tail\r\n  ")
        self.assertEqual(json.loads(receipt)["capture_class"], "masked_native_capture")


if __name__ == "__main__":
    unittest.main()
