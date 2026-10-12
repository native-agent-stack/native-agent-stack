"""Runtime note receipts may digest only output whose exact bytes are published.

Publication correction from #1033's d475ef81 delta: raw failed-test logs can
contain home paths even when the receipt itself passes the text scanner.
No original private log is read, copied or hashed by this regression.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = Path("notes/runtime-profiles-20261012/receipts")


def unresolved_output_digests(value, *, root, directory):
    """Fail closed on output hashes lacking their exact public-file preimage."""
    if isinstance(value, list):
        return sum(unresolved_output_digests(item, root=root, directory=directory) for item in value)
    if not isinstance(value, dict):
        return 0
    missing = 0
    for key, digest in value.items():
        if not (key == "output_sha256" or key.endswith("_output_sha256")):
            continue
        reference = value.get("red_log" if key.startswith("red_") else "log")
        resolved = False
        if isinstance(reference, str) and not Path(reference).is_absolute():
            for base in (directory, root):
                path = base / reference
                # Resolve only caller-owned published paths. Never follow a
                # pointer out of the checkout to an unpublished/native log.
                if path.resolve().is_relative_to(root.resolve()) and path.is_file():
                    resolved |= hashlib.sha256(path.read_bytes()).hexdigest() == digest
        missing += not resolved
    return missing + sum(unresolved_output_digests(item, root=root, directory=directory)
                         for item in value.values())


class RuntimePublicationTests(unittest.TestCase):
    def test_output_hashes_in_published_runtime_notes_bind_published_log_bytes(self):
        checked = 0
        for path in (ROOT / RECEIPTS).rglob("*.json"):
            checked += 1
            with self.subTest(receipt=path.relative_to(ROOT).as_posix()):
                self.assertEqual(unresolved_output_digests(json.loads(path.read_text()),
                    root=ROOT, directory=path.parent), 0,
                    "unpublished or mismatched log preimage; omit the hash or publish sanitized exact bytes")
        self.assertGreater(checked, 0)

    def test_absent_log_is_refused_and_exact_published_sanitized_bytes_are_accepted(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as temporary:
            root = Path(temporary)
            directory = root / RECEIPTS
            directory.mkdir(parents=True)
            published = b"Sanitized fixture output.\n"
            entry = {"log": "safe.log", "output_sha256": hashlib.sha256(published).hexdigest()}
            self.assertEqual(unresolved_output_digests(entry, root=root, directory=directory), 1)
            (directory / "safe.log").write_bytes(published)
            self.assertEqual(unresolved_output_digests(entry, root=root, directory=directory), 0)
            (directory / "safe.log").write_bytes(b"Different published bytes.\n")
            self.assertEqual(unresolved_output_digests(entry, root=root, directory=directory), 1)

    def test_lifecycle_git_fixture_uses_only_no_reply_email(self):
        source = (ROOT / "tests/test_runtime_profiles.py").read_text()
        import re
        emails = re.findall(r"user\.email=([^\s\"']+)", source)
        self.assertTrue(emails)
        for email in emails:
            self.assertTrue(email.endswith("@users.noreply.github.com"),
                            "the literal publication rule has no synthetic-email exception")

    def test_profile_module_scope_claim_names_shared_services_and_launch_locations(self):
        import ast
        import os
        source = Path(os.environ.get("NS_RUNTIME_SCOPE_BASELINE_SOURCE",
                                    ROOT / "tools/adoption/runtime_profiles.py"))
        text = ast.get_docstring(ast.parse(source.read_text()))
        self.assertNotIn("Generated files and persistent MCP stores are scoped to private profile roots", text)
        for boundary in ("Context Mode", "launchers/Terminal fragments", "shared stores", "project cache"):
            self.assertIn(boundary, text)

    def test_fixture_claimed_native_functions_match_the_pinned_vendor_bytes(self):
        import os
        import subprocess
        mirror = os.environ.get("NS_OPENCODE_TEST_SOURCE")
        if not mirror:
            self.skipTest("explicit public vendor source mirror required for byte-provenance check")
        pin = "53d1eabb61e21162157817bf677da0a4ad3332e3"
        fixture = (ROOT / "tests/fixtures/opencode-permission-53d1eabb.ts").read_text()
        for path, first, last in (
            ("packages/opencode/src/util/wildcard.ts", 3, 19),
            ("packages/opencode/src/permission/index.ts", 28, 38),
            ("packages/opencode/src/permission/index.ts", 178, 214),
            ("packages/core/src/npm.ts", 45, 50),
        ):
            source = subprocess.check_output(["git", "-C", mirror, "show", pin + ":" + path], text=True)
            excerpt = "\n".join(source.splitlines()[first - 1:last]) + "\n"
            with self.subTest(path=path, first=first):
                self.assertIn(excerpt, fixture, "claimed unchanged native function differs from its pinned bytes")


if __name__ == "__main__":
    unittest.main()
