"""Harness atlas in the composer: navigation, placeholder, failure handling, --atlas-only and nonserved publication.

The full refresh with the composer's fixture (Home link, atlas.html published beside the ten refresh outputs) is
covered in tests/test_local_pages.py, which owns that fixture.
"""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "tools/local-pages"


def load(name):
    spec = importlib.util.spec_from_file_location("atlas_build_tests_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PAGES = load("build_pages")


class BuildCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="atlas-build-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)

    def failing(self, module, function, error):
        """As tests/test_local_pages_overview.py:711-713: one module's function raises; every other load is real."""
        stub, real = type("Stub", (), {function: staticmethod(lambda *args, **kwargs: (_ for _ in ()).throw(error))}), PAGES.load_local
        return unittest.mock.patch.object(PAGES, "load_local", side_effect=lambda name, *rest: stub if name == module else real(name, *rest))


class NavigationTests(BuildCase):
    def test_every_page_lists_the_atlas_and_its_footer_links_its_evidence(self):
        home = PAGES.document("index", "Home", "", "scope", "", "2099-01-01T00:00:00Z", "a" * 64, []).decode()
        self.assertIn('href="atlas.html">Atlas</a>', home)
        self.assertLess(home.index('href="overview.html"'), home.index('href="atlas.html"'))
        page = PAGES.document("atlas", "Harness atlas", "", "scope", "", "2099-01-01T00:00:00Z", "a" * 64, []).decode()
        self.assertIn('href="#atlas-evidence"', page)
        self.assertIn('href="atlas.html" aria-current="page"', page)

    def test_an_unavailable_atlas_is_an_unreported_placeholder(self):
        page = PAGES.unavailable_page("atlas", "2099-01-01T00:00:00Z", "a" * 64).decode()
        self.assertIn("UNREPORTED", page)
        self.assertIn('id="atlas-evidence"', page)
        self.assertIn("<title>Atlas unavailable", page)


class RefreshTests(BuildCase):
    def test_a_failing_atlas_keeps_the_previous_page_or_publishes_a_placeholder(self):
        for previous in (False, True):
            with self.subTest(previous=previous):
                output = self.base / f"served-{previous}"
                output.mkdir()
                if previous:
                    (output / "atlas.html").write_text("previous page\n")
                outputs, receipt_doc = {}, {"outputs": {}}
                with self.failing("atlas_data", "build_atlas_page", ValueError("bad")):
                    PAGES.refresh_atlas(ROOT, self.base / "state", output, self.base / "custody/refresh-receipt.json", "2099-01-01T00:00:00Z", "a" * 64, outputs, receipt_doc)
                status = receipt_doc["atlas"]
                self.assertEqual((status["status"], status["reason"]), ("UNREPORTED", "Atlas unavailable (ValueError)"))
                if previous:
                    self.assertEqual((status["page_status"], outputs), ("previous page retained without a new observation", {}))
                    self.assertEqual((output / "atlas.html").read_text(), "previous page\n")
                else:
                    self.assertEqual(status["page_status"], "unreported placeholder")
                    self.assertIn('id="atlas-evidence"', outputs["atlas.html"].decode())
                    self.assertIn("atlas.html", receipt_doc["outputs"])

    def test_a_refresh_records_the_atlas_block_and_keeps_its_custody_outside_the_served_root(self):
        output, receipt = self.base / "served", self.base / "custody/refresh-receipt.json"
        outputs, receipt_doc = {}, {"outputs": {}}
        PAGES.refresh_atlas(ROOT, self.base / "state", output, receipt, "2099-01-01T00:00:00Z", "a" * 64, outputs, receipt_doc)
        block = receipt_doc["atlas"]
        self.assertEqual(set(block), {"schema", "generated_utc", "commit", "page", "present", "pending", "ledger", "outputs"})
        self.assertEqual((block["schema"], block["page"], block["ledger"]["status"]), ("local-atlas/1", "atlas.html", "appended"))
        self.assertEqual(outputs, {})
        self.assertTrue((output / "atlas.html").is_file())
        for name in ("atlas-receipt.json", "atlas-ledger.json"):
            self.assertTrue((receipt.parent / "atlas" / name).is_file())
            self.assertFalse((receipt.parent / "atlas" / name).is_relative_to(output))


class AtlasOnlyTests(BuildCase):
    def test_atlas_only_never_writes_a_refresh_receipt(self):
        state, output = self.base / "state", self.base / "served"
        refresh = state / "research/fullspeed-20261008/g5-stars-gap/local-pages/refresh-receipt.json"
        refresh.parent.mkdir(parents=True)
        refresh.write_text('{"schema": "full refresh"}\n')
        named = self.base / "elsewhere/refresh-receipt.json"
        with redirect_stdout(io.StringIO()), unittest.mock.patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit) as raised:
            PAGES.main(["--atlas-only", "--output-dir", str(output), "--state-root", str(state), "--receipt", str(named)])
        self.assertEqual(raised.exception.code, 2)
        self.assertFalse(named.exists())
        self.assertFalse(output.exists())
        with redirect_stdout(io.StringIO()), unittest.mock.patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit) as raised:
            PAGES.main(["--atlas-only", "--overview-only", "--output-dir", str(output), "--state-root", str(state)])
        self.assertEqual(raised.exception.code, 2)
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = PAGES.main(["--atlas-only", "--output-dir", str(output), "--state-root", str(state)])
        self.assertEqual(code, 0)
        self.assertEqual(refresh.read_text(), '{"schema": "full refresh"}\n')
        written = refresh.parent / "atlas/atlas-receipt.json"
        summary = json.loads(stdout.getvalue())
        self.assertEqual(summary["receipt"], str(written))
        self.assertEqual(json.loads(written.read_text())["schema"], "local-atlas/1")
        self.assertFalse((refresh.parent / "architecture").exists())

    def test_atlas_only_renders_the_real_repository_with_the_projections_pending(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = PAGES.main(["--atlas-only", "--output-dir", str(self.base / "served"), "--receipt", str(self.base / "custody/atlas/atlas-receipt.json"),
                               "--state-root", str(self.base / "state")])
        self.assertEqual(code, 0)
        summary = json.loads(stdout.getvalue())
        self.assertEqual(set(summary), {"output_dir", "receipt", "generated_utc", "commit", "page", "present", "pending", "ledger"})
        self.assertIn("final_stack", summary["present"])
        self.assertIn("cc_slots", summary["present"])
        self.assertEqual(summary["pending"], ["token_rate_history", "token_rate_latest"])
        self.assertEqual(summary["ledger"]["status"], "appended")
        html = (self.base / "served/atlas.html").read_text()
        self.assertIn("Not measured yet: the daily token projection has not run.", html)
        self.assertFalse(any(path.name.startswith("architecture-") for path in (self.base / "served").iterdir()))


class PublishTests(BuildCase):
    def test_nonserved_records_are_replaced_before_the_receipt_and_never_inside_the_served_root(self):
        output, receipt, ledger = self.base / "served", self.base / "custody/atlas/receipt.json", self.base / "custody/atlas/ledger.json"
        order, real = [], os.replace

        def record(source, destination):
            order.append(Path(destination).name)
            return real(source, destination)

        with unittest.mock.patch.object(PAGES.os, "replace", side_effect=record):
            PAGES.publish(output, receipt, {"atlas.html": b"page"}, {"schema": "fixture"}, nonserved={ledger: b"ledger\n"})
        self.assertEqual(order, ["atlas.html", "ledger.json", "receipt.json"])
        self.assertEqual(ledger.read_bytes(), b"ledger\n")
        for target in (output / "ledger.json", receipt):
            with self.subTest(target=target.name), self.assertRaises(ValueError):
                PAGES.publish(output, receipt, {"atlas.html": b"other"}, {"schema": "fixture"}, nonserved={target: b"x"})
        self.assertEqual((output / "atlas.html").read_bytes(), b"page")
        self.assertEqual(json.loads(receipt.read_text()), {"schema": "fixture"})


if __name__ == "__main__":
    unittest.main()
