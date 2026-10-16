"""Byte/JSON masking regressions using explicitly synthetic private literals."""

import json
import unittest

from mask_capture import mask_bytes


class MaskCaptureTests(unittest.TestCase):
    def test_truncated_scratch_prefixes_are_masked(self):
        root = "/var/tmp/fixture-private-workspace-20261016"
        rules = [{"source": root, "placeholder": "<scratch>"}]
        for size in range(len("/var/tmp/") + 1, len(root)):
            with self.subTest(prefix_length=size):
                partial = root[:size].encode()
                raw = b"AssertionError: '" + partial + b"[47 chars]tail'"
                self.assertEqual(mask_bytes(raw, rules),
                    b"AssertionError: '<private-scratch-prefix>[47 chars]tail'")

    def test_partial_root_does_not_eat_unrelated_path(self):
        rules = [{"source": "/var/tmp/fixture-private-workspace",
                  "placeholder": "<scratch>"}]
        raw = b"/var/tmp/fixture-unrelated-file"
        self.assertEqual(mask_bytes(raw, rules), raw)

    def test_json_encoded_private_literals_are_masked(self):
        literals = ["caf\u00e9", 'quoted"path', "back\\slash"]
        tokens = ["<unicode>", "<quote>", "<backslash>"]
        rules = [{"source": source, "placeholder": token}
                 for source, token in zip(literals, tokens)]
        raw = json.dumps({"command": literals}, indent=2, sort_keys=True).encode()
        expected = json.dumps({"command": tokens}, indent=2, sort_keys=True).encode()
        self.assertEqual(mask_bytes(raw, rules), expected)

    def test_conflicting_json_escape_aliases_are_rejected(self):
        rules = [
            {"source": "caf\u00e9", "placeholder": "<unicode>"},
            {"source": "caf\\u00e9", "placeholder": "<literal>"},
        ]
        with self.assertRaises(ValueError):
            mask_bytes(b"caf\\u00e9", rules)

    def test_preserves_all_unmapped_bytes_and_line_endings(self):
        raw = b"\xff\x00 /private/scratch/file\r\npass  \n"
        rules = [{"source": "/private/scratch", "placeholder": "<scratch>"}]
        self.assertEqual(
            mask_bytes(raw, rules), b"\xff\x00 <scratch>/file\r\npass  \n"
        )

    def test_longest_match_wins_independent_of_rule_order(self):
        rules = [
            {"source": "/private", "placeholder": "<private>"},
            {"source": "/private/scratch", "placeholder": "<scratch>"},
        ]
        expected = b"<scratch>/f <private>/other"
        raw = b"/private/scratch/f /private/other"
        self.assertEqual(mask_bytes(raw, rules), expected)
        self.assertEqual(mask_bytes(raw, list(reversed(rules))), expected)

    def test_replacements_are_not_reprocessed(self):
        rules = [
            {"source": "original", "placeholder": "<scratch>"},
            {"source": "scratch", "placeholder": "<other>"},
        ]
        self.assertEqual(mask_bytes(b"original scratch", rules), b"<scratch> <other>")

    def test_no_rules_or_no_matches_leave_bytes_exact(self):
        raw = b"unmatched\r\n\x80\t "
        self.assertEqual(mask_bytes(raw, []), raw)
        self.assertEqual(
            mask_bytes(raw, [{"source": "elsewhere", "placeholder": "<private>"}]),
            raw,
        )

    def test_rejects_ambiguous_or_unmarked_rules(self):
        rule = {"source": "literal", "placeholder": "<private>"}
        invalid = [
            [rule, rule],
            [{"source": "", "placeholder": "<private>"}],
            [{"source": "literal", "placeholder": "unmarked"}],
            [{"source": "literal", "placeholder": "<Private>"}],
            [{"source": "literal", "placeholder": "<private>", "extra": "value"}],
        ]
        for rules in invalid:
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                mask_bytes(b"literal", rules)


if __name__ == "__main__":
    unittest.main()
