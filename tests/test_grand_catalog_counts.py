"""Public CLI regressions for the host-only grand-catalog projection.

Fixture encoding follows test_local_pages_architecture_sources.py:61-74 at
native-agent-stack 8bffa2c41692ef483e91b68e3b15aeb331423d2c. No host asset is
needed by these tests; expectations come from the specified fixture rows.
"""

import hashlib
import io
import json
from pathlib import Path
from collections import Counter, defaultdict
import subprocess
import tarfile
import tempfile
import os
import sys
import unittest

from tests.local_pages_architecture_policy_fixture import G5


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/grand_catalog_counts.py"
SOURCE = "catalogs/landscape/grand-catalog-20261008.json"
ASSET_SOURCE = "evidence/artifacts/g5-start-closure-1-20261009/class-gates.json"
OUTPUT = "catalogs/landscape/grand-catalog-counts.json"
DISPOSITIONS = ("NO-GAP", "OUT-OF-SCOPE", "PENDING", "REJECT", "TRIAL", "WATCH")


@unittest.skipUnless(Path("/usr/bin/zstd").is_file(), "native G5 fixture encoding requires zstd")
class GrandCatalogCountsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        self.state = Path(temporary.name) / "state"
        self.root.mkdir()
        self.asset = self.state / G5
        self.asset.parent.mkdir(parents=True)
        self.output = self.root / OUTPUT
        self.rows = [
            self.row("Example/Duplicate", "PENDING", "instructions-skills"),
            self.row("https://github.com/example/duplicate.git", "WATCH", "instructions-skills"),
            self.row("example/other", "PENDING", "workers"),
        ]
        self.write_asset(self.rows)
        self.write_source({"PENDING": 2, "WATCH": 1}, {"instructions-skills": 2, "workers": 1})

    def row(self, repository, disposition, layer):
        return {"repository_or_entry": repository, "disposition": disposition, "slot": layer,
                "qualification": {"catalog": "foundation", "slot": layer}}

    def write_asset(self, rows):
        self.member_bytes = json.dumps(rows, ensure_ascii=False).encode("utf-8")
        content = io.BytesIO()
        with tarfile.open(fileobj=content, mode="w") as archive:
            member = tarfile.TarInfo("compact/rows.json")
            member.size = len(self.member_bytes)
            archive.addfile(member, io.BytesIO(self.member_bytes))
            ignored = b"PRIVATE-UNNEEDED-MEMBER\xff"
            member = tarfile.TarInfo("private/ignored.json")
            member.size = len(ignored)
            archive.addfile(member, io.BytesIO(ignored))
        encoded = subprocess.run(["/usr/bin/zstd", "-q", "-c"], input=content.getvalue(),
                                 capture_output=True, check=True, timeout=20)
        self.asset.write_bytes(encoded.stdout)

    def write_source(self, dispositions, layers):
        raw = self.asset.read_bytes()
        document = {"schema_version": 1,
                    "asset": {"name": self.asset.name, "sha256": hashlib.sha256(raw).hexdigest(),
                              "bytes": len(raw), "rows_member": "compact/rows.json",
                              "rows_sha256": hashlib.sha256(self.member_bytes).hexdigest()},
                    "counts": {"rows": sum(dispositions.values()),
                               "by_disposition": {key: dispositions.get(key, 0) for key in DISPOSITIONS},
                               "by_slot": layers}}
        path = self.root / SOURCE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")
        binding = {"schema_version": 1, "asset": document["asset"],
                   "original_rows_sha256": document["asset"]["rows_sha256"]}
        path = self.root / ASSET_SOURCE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(binding), encoding="utf-8")

    def run_exporter(self, *args):
        return subprocess.run(["python3", str(SCRIPT), "--root", str(self.root),
                               "--state-root", str(self.state), *args],
                              capture_output=True, text=True, timeout=30)

    def test_repository_index_preserves_conflicting_dispositions(self):
        result = self.run_exporter("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(document["counts"]["rows"], 3)
        self.assertEqual(document["counts"]["by_disposition"]["PENDING"], 2)
        self.assertEqual(document["by_repository"]["github.com/example/duplicate"], ["PENDING", "WATCH"])
        self.assertEqual(document["counts"]["by_layer"]["instructions-skills"]["rows"], 2)
        self.assertEqual(document["counts"]["by_layer"]["workers"]["rows"], 1)
        self.assertNotIn("file_utc", document["source"])
        self.assertNotIn(str(self.state), self.output.read_text(encoding="utf-8"))

    def test_two_export_runs_are_byte_identical_and_check_passes(self):
        first = self.run_exporter("--write")
        self.assertEqual(first.returncode, 0, first.stderr)
        original = self.output.read_bytes()
        self.asset.touch()
        second = self.run_exporter("--write")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.output.read_bytes(), original)
        checked = self.run_exporter("--check")
        self.assertEqual(checked.returncode, 0, checked.stderr)

    @unittest.skipUnless(os.name == "posix", "real partial-write injection requires POSIX RLIMIT_FSIZE")
    def test_real_partial_write_failure_preserves_previous_snapshot_and_cleans_temp_file(self):
        written = self.run_exporter("--write")
        self.assertEqual(written.returncode, 0, written.stderr)
        original = self.output.read_bytes()
        previous_entries = set(self.output.parent.iterdir())
        child = (
            "import resource,signal,runpy,sys; "
            "signal.signal(signal.SIGXFSZ, signal.SIG_IGN); "
            "resource.setrlimit(resource.RLIMIT_FSIZE,(512,512)); "
            "sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')"
        )
        result = subprocess.run([sys.executable, "-c", child, str(SCRIPT), "--root", str(self.root),
                                 "--state-root", str(self.state), "--write"],
                                capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no snapshot written", result.stderr)
        self.assertEqual(self.output.read_bytes(), original)
        self.assertEqual(set(self.output.parent.iterdir()), previous_entries)
        self.assertEqual(json.loads(self.output.read_bytes())["counts"]["rows"], 3)
        self.assertNotIn(str(self.state), result.stderr)

    def test_replace_failure_preserves_snapshot_and_cleans_completed_temporary_file(self):
        result = self.run_exporter("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        original = self.output.read_bytes()
        previous_entries = set(self.output.parent.iterdir())
        child = (
            "import runpy,sys,os; from unittest.mock import patch; "
            "sys.argv=sys.argv[1:]; "
            "guard=patch.object(os,'replace',side_effect=OSError('private-fixture-location')); "
            "guard.start(); runpy.run_path(sys.argv[0],run_name='__main__')"
        )
        result = subprocess.run([sys.executable, "-c", child, str(SCRIPT), "--root", str(self.root),
                                 "--state-root", str(self.state), "--write"],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.output.read_bytes(), original)
        self.assertEqual(set(self.output.parent.iterdir()), previous_entries)
        self.assertNotIn("private-fixture-location", result.stderr)

    def test_corrupt_decoder_error_is_redacted_and_preserves_previous_snapshot(self):
        result = self.run_exporter("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        previous = self.output.read_bytes()
        self.asset.write_bytes(b"not a zstd stream")
        result = self.run_exporter("--write")
        self.assertEqual(result.returncode, 1)
        self.assertIn("grand catalog source could not be read", result.stderr)
        self.assertNotIn(str(self.state), result.stderr)
        self.assertEqual(self.output.read_bytes(), previous)

    def test_index_keys_use_the_final_stack_repository_identity(self):
        result = self.run_exporter("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertIn("github.com/example/duplicate", document["by_repository"])

    def test_host_asset_uses_sealed_binding_not_historical_catalog_archive(self):
        path = self.root / SOURCE
        historical = json.loads(path.read_text(encoding="utf-8"))
        historical["asset"].update(sha256="d" * 64, rows_sha256="e" * 64, bytes=1)
        path.write_text(json.dumps(historical), encoding="utf-8")
        result = self.run_exporter("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(document["source"]["asset_sha256"], hashlib.sha256(self.asset.read_bytes()).hexdigest())
        self.assertEqual(document["source"]["asset_binding"], ASSET_SOURCE)

    def test_layer_counts_come_from_retained_rows_not_historical_slot_totals(self):
        path = self.root / SOURCE
        historical = json.loads(path.read_text(encoding="utf-8"))
        historical["counts"]["by_slot"] = {"instructions-skills": 1, "workers": 2}
        path.write_text(json.dumps(historical), encoding="utf-8")
        result = self.run_exporter("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(document["counts"]["by_layer"]["instructions-skills"]["rows"], 2)
        self.assertEqual(document["counts"]["by_layer"]["workers"]["rows"], 1)

    def test_fixture_reconciles_all_4606_rows_and_4058_pending(self):
        expected = {"NO-GAP": 48, "OUT-OF-SCOPE": 10, "PENDING": 4058,
                    "REJECT": 6, "TRIAL": 83, "WATCH": 401}
        rows = []
        for disposition, count in expected.items():
            for index in range(count):
                layer = "workers" if len(rows) % 2 else "instructions-skills"
                rows.append(self.row(f"example/project-{index}", disposition, layer))
        self.write_asset(rows)
        self.write_source(expected, {"instructions-skills": 2303, "workers": 2303})
        result = self.run_exporter("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(document["counts"]["rows"], 4606)
        self.assertEqual(document["counts"]["by_disposition"], expected)
        self.assertEqual(document["counts"]["by_layer"]["instructions-skills"]["rows"], 2303)
        self.assertEqual(document["counts"]["by_layer"]["workers"]["rows"], 2303)
        self.assertEqual(document["source"]["asset_sha256"], hashlib.sha256(self.asset.read_bytes()).hexdigest())

    def test_missing_asset_fails_without_creating_a_snapshot(self):
        self.asset.unlink()
        result = self.run_exporter("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing", result.stderr)
        self.assertFalse(self.output.exists())
        self.assertNotIn(str(self.state), result.stderr)

    def test_altered_valid_asset_cannot_replace_previous_snapshot(self):
        written = self.run_exporter("--write")
        self.assertEqual(written.returncode, 0, written.stderr)
        original = self.output.read_bytes()
        changed = [dict(row) for row in self.rows]
        changed[0]["repository_or_entry"] = "example/altered"
        self.write_asset(changed)
        result = self.run_exporter("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pinned sha256", result.stderr)
        self.assertEqual(self.output.read_bytes(), original)

    def test_check_detects_repository_index_drift_without_rewriting(self):
        result = self.run_exporter("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(self.output.read_text(encoding="utf-8"))
        document["by_repository"]["github.com/example/duplicate"] = ["WATCH"]
        self.output.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        drifted = self.output.read_bytes()
        checked = self.run_exporter("--check")
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("differs", checked.stderr)
        self.assertEqual(self.output.read_bytes(), drifted)

    def test_changed_expected_counts_fail_closed(self):
        path = self.root / SOURCE
        source = json.loads(path.read_text(encoding="utf-8"))
        source["counts"]["by_disposition"]["PENDING"] = 1
        path.write_text(json.dumps(source), encoding="utf-8")
        result = self.run_exporter("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("disposition counts do not reconcile", result.stderr)
        self.assertFalse(self.output.exists())

    def test_unparseable_repository_is_counted_without_a_false_index_identity(self):
        self.rows[0]["repository_or_entry"] = "A documentary entry with no repository"
        self.write_asset(self.rows)
        self.write_source({"PENDING": 2, "WATCH": 1}, {"instructions-skills": 2, "workers": 1})
        result = self.run_exporter("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(document["counts"]["rows"], 3)
        self.assertEqual(document["counts"]["rows_without_repository"], 1)
        self.assertEqual(document["by_repository"]["github.com/example/duplicate"], ["WATCH"])
        self.assertEqual(document["counts"]["repositories"], 2)

    def test_unapproved_asset_path_fails_without_disclosing_the_path(self):
        other = self.state / "unapproved-catalog.tar.zst"
        other.write_bytes(self.asset.read_bytes())
        result = self.run_exporter("--asset", str(other), "--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source-policy grant", result.stderr)
        self.assertNotIn(str(other), result.stderr)
        self.assertFalse(self.output.exists())


class CommittedSnapshotTests(unittest.TestCase):
    def test_committed_snapshot_semantics_match_historical_rows_with_the_documented_layer_delta(self):
        from scripts import grand_catalog_counts as producer
        catalog_bytes = (ROOT / SOURCE).read_bytes()
        catalog = json.loads(catalog_bytes)
        snapshot = json.loads((ROOT / OUTPUT).read_bytes())
        rows = catalog["rows"]
        totals = Counter(row["disposition"] for row in rows)
        self.assertEqual(len(rows), 4606)
        self.assertEqual(snapshot["counts"]["by_disposition"], dict(totals))
        self.assertEqual(snapshot["counts"]["rows"], len(rows))
        self.assertEqual(snapshot["source"]["catalog_sha256"], hashlib.sha256(catalog_bytes).hexdigest())
        self.assertEqual(snapshot["source"]["asset_binding_sha256"],
                         hashlib.sha256((ROOT / ASSET_SOURCE).read_bytes()).hexdigest())
        by_layer = defaultdict(Counter)
        repositories = defaultdict(set)
        missing = 0
        for row in rows:
            by_layer[row["slot"]][row["disposition"]] += 1
            pin = row.get("pin") if isinstance(row.get("pin"), dict) else {}
            repository = (producer._reader._repo(row.get("repository_or_entry"))
                          or producer._reader._repo(pin.get("repository_or_source")))
            if repository:
                repositories[producer.normalize_repository("https://github.com/" + repository)].add(row["disposition"])
            else:
                missing += 1
        self.assertEqual(snapshot["by_repository"], {key: sorted(values) for key, values in repositories.items()})
        self.assertEqual((snapshot["counts"]["repositories"], snapshot["counts"]["rows_without_repository"]),
                         (2974, missing))
        self.assertEqual(missing, 34)
        self.assertEqual(sum(len(values) > 1 for values in repositories.values()), 208)
        self.assertEqual(sum("PENDING" in values for values in repositories.values()), 2718)
        by_layer["agent-sdks"]["TRIAL"] += 1
        by_layer["instructions-skills"]["TRIAL"] -= 1
        expected_layers = {key: {"rows": sum(values.values()),
                                 "by_disposition": {d: values[d] for d in DISPOSITIONS}}
                           for key, values in by_layer.items()}
        self.assertEqual(snapshot["counts"]["by_layer"], expected_layers)
        self.assertEqual(sum(row["rows"] for row in expected_layers.values()), 4606)

    def test_snapshot_exclusion_provenance_hash_is_bound_to_committed_bytes(self):
        policy = json.loads((ROOT / "tools/local-pages/source_policy.json").read_bytes())
        entry = next(row for row in policy["architecture_derivation_sources"] if row["path"] == OUTPUT)
        self.assertEqual(entry["sha256"], hashlib.sha256((ROOT / OUTPUT).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
