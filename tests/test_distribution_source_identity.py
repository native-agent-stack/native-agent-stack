"""A marked distribution package keeps its actual source repository."""
import json
import unittest

from scripts import landscape
from scripts import catalog_decisions
from tests import test_landscape as fixtures
from tests import test_catalog_decisions as index_fixtures


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

    def selected_package(self):
        self.marked_package()
        selected = json.loads((self.root / "stack.json").read_text())
        selected["components"][0].update(
            repository="https://git.launchpad.net/ubuntu/+source/systemd",
            source_identity_kind="os_distribution_package",
            upstream_repository="https://github.com/example/selected")
        self.write("stack.json", selected)

    def test_stale_upstream_freshness_is_not_the_selected_package_source(self):
        self.selected_package()
        with self.assertRaisesRegex(ValueError, "freshness selected repository differs"):
            self.build()

    def test_another_package_with_same_upstream_is_not_a_freshness_match(self):
        self.selected_package()
        self.freshness["components"][0].update(
            selected_repository_url="https://git.launchpad.net/ubuntu/+source/other-package",
            source_identity_kind="os_distribution_package",
            upstream_repository="https://github.com/example/selected")
        self.write("freshness.json", self.freshness)
        with self.assertRaisesRegex(ValueError, "freshness selected repository differs"):
            self.build()

    def test_matching_actual_package_freshness_is_admitted_without_upstream_markers(self):
        self.selected_package()
        self.freshness["components"][0]["selected_repository_url"] = (
            "https://git.launchpad.net/ubuntu/+source/systemd.git/")
        self.write("freshness.json", self.freshness)
        self.assertEqual(self.build()["counts"]["selected_components"], 1)


class SelectedDistributionIndexTests(unittest.TestCase):
    setUp = index_fixtures.DecisionIndexTests.setUp
    write = index_fixtures.DecisionIndexTests.write
    save_index = index_fixtures.DecisionIndexTests.save_index

    def test_selected_marked_package_round_trips_through_the_real_index_producer(self):
        path = "manifests/stack.json"
        selected = self.documents[path]["components"][0]
        selected.update(repository="https://git.launchpad.net/ubuntu/+source/systemd",
                        source_identity_kind="os_distribution_package",
                        upstream_repository="https://github.com/example/core")
        self.write(path, self.documents[path])
        self.save_index()
        self.assertEqual(catalog_decisions.validate_index(self.root), self.index["counts"])
        record = next(row for row in self.index["records"] if row["repository"] == "https://github.com/example/core")
        self.assertTrue(any(ref["path"] == path for ref in record["references"]))
        self.assertEqual(json.loads((self.root / path).read_text())["components"][0]["repository"],
                         "https://git.launchpad.net/ubuntu/+source/systemd")
