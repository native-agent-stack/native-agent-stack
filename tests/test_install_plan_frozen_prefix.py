"""Frozen decision prefixes survive appends without permitting rewrites.

Fixture lengths come from native-agent-stack@8053f14e7. The real guard runs
against an exported tree, so neither the guard nor these tests needs Git.
"""
from contextlib import contextmanager
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests import test_install_plan_review_wave3 as wave3


FROZEN_LENGTHS = {
    "2026-10-01-new-wsl-distro-recipe.md": 151947,
    "2026-10-02-new-wsl-client-configuration.md": 149798,
}
ADDENDUM = "2026-10-16-new-wsl-host-allocation-addendum.md"


class FrozenDecisionPrefixTests(unittest.TestCase):
    @contextmanager
    def exported_decisions(self, *, current=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            decisions = root / "docs/decisions"
            decisions.mkdir(parents=True)
            for name, length in FROZEN_LENGTHS.items():
                data = (wave3.ROOT / "docs/decisions" / name).read_bytes()
                (decisions / name).write_bytes(data if current else data[:length])
            (decisions / ADDENDUM).write_bytes((wave3.ROOT / "docs/decisions" / ADDENDUM).read_bytes())
            yield root

    def guard_failures(self, root):
        case = wave3.ReviewWave4DocumentationTests(
            "test_addendum_supersedes_both_decisions_without_rewriting_them")
        result = unittest.TestResult()
        with mock.patch.object(wave3, "ROOT", root):
            case.run(result)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.skipped), 0)
        return len(result.failures)

    def test_append_to_either_frozen_decision_is_allowed(self):
        for name in FROZEN_LENGTHS:
            with self.subTest(path=name), self.exported_decisions() as root:
                path = root / "docs/decisions" / name
                path.write_bytes(path.read_bytes() + b"\nDated follow-up appended after the frozen decision.\n")
                self.assertEqual(self.guard_failures(root), 0)

    def test_change_inside_either_frozen_prefix_is_rejected(self):
        for name, length in FROZEN_LENGTHS.items():
            for offset in (0, length // 2, length - 1):
                with self.subTest(path=name, offset=offset), self.exported_decisions() as root:
                    path = root / "docs/decisions" / name
                    data = bytearray(path.read_bytes())
                    data[offset] ^= 1
                    path.write_bytes(data)
                    self.assertEqual(self.guard_failures(root), 1)

    def test_current_decisions_pass_without_a_git_database(self):
        with self.exported_decisions(current=True) as root:
            self.assertFalse((root / ".git").exists())
            self.assertEqual(self.guard_failures(root), 0)


if __name__ == "__main__":
    unittest.main()
