"""A marked distribution package keeps its actual source repository."""
import unittest

from scripts import landscape
from tests import test_landscape as fixtures


class DistributionSourceTests(unittest.TestCase):
    setUp = fixtures.LandscapeTests.setUp
    write = fixtures.LandscapeTests.write
    build = fixtures.LandscapeTests.build

    def marked_package(self):
        self.layer["candidates"][0].update(
            repository="https://git.launchpad.net/ubuntu/+source/systemd",
            source_identity_kind="os_distribution_package",
            upstream_repository="https://github.com/example/selected")
        self.write("foundation.json", self.foundation)

    def test_marked_launchpad_package_is_admitted_without_rewriting_source(self):
        self.marked_package()
        result = self.build()
        row = next(row for row in result["layers"] if row["catalog"] == "foundation")
        self.assertEqual(row["candidates"][0]["repository"],
                         "https://git.launchpad.net/ubuntu/+source/systemd")
        self.assertEqual(row["candidates"][0]["repository_id"], "example/selected")

    def test_unmarked_and_foreign_packages_are_refused(self):
        for case in ("unmarked", "foreign"):
            with self.subTest(case=case):
                self.marked_package()
                if case == "unmarked":
                    del self.layer["candidates"][0]["source_identity_kind"]
                else:
                    self.layer["candidates"][0]["repository"] = "https://example.org/ubuntu/+source/systemd"
                self.write("foundation.json", self.foundation)
                with self.assertRaisesRegex(ValueError, "candidate needs a canonical public repository URL"):
                    self.build()
