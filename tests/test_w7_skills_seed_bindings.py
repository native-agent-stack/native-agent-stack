"""Frozen provenance guards for the source-only W7 intake; no research is run."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKET = "docs/decisions/w7-skills-seeds-20261012/"
MASTER = "catalogs/convergence-practice/sources/master-seeds-20261010.json"
GRAND = "catalogs/landscape/grand-catalog-20261008.json"


@lru_cache(maxsize=None)
def frozen_bytes(root, commit, path):
    return subprocess.check_output(["git", "-C", str(root), "show", commit + ":" + path])


def pointer(value, fragment):
    for segment in fragment.removeprefix("/").split("/"):
        value = value[int(segment)] if isinstance(value, list) else value[segment]
    return value


class W7SkillsSeedBindingTests(unittest.TestCase):
    def setUp(self):
        self.intake = json.loads((ROOT / (PACKET + "intake.json")).read_text())
        self.master = json.loads(frozen_bytes(ROOT, self.intake["base_commit"], MASTER))

    def test_gsd_is_one_existing_master_seed_not_an_added_seed(self):
        seed = self.intake["gsd_seed"]
        subject = self.master["instructions-skills"][151].split(";", 1)[0].strip()
        repository, commit = subject.split("@")
        self.assertEqual(seed.get("master_ref"), MASTER + "#/instructions-skills/151")
        self.assertEqual(seed["repository"], "https://github.com/" + repository)
        self.assertEqual(seed["commit"], commit)
        self.assertEqual(seed.get("primary_metadata_state"), "UNMIRRORED")
        self.assertEqual(self.intake["instructions_skills_master_scope"]["count"],
                         len(self.master["instructions-skills"]))
        self.assertEqual(sum(row.split(";", 1)[0].strip() == subject
                             for row in self.master["instructions-skills"]), 1)
        observations = seed.get("observations", [])
        self.assertTrue(observations)
        self.assertTrue(all(row["state"] == "OBSERVATION_ONLY; NOT_RETAINED_PIN"
                            and row["commit"] != commit for row in observations))
        readme = (ROOT / (PACKET + "README.md")).read_text()
        self.assertIn("#/instructions-skills/151", readme)
        self.assertIn(commit, readme)

    def test_every_seed_explicitly_binds_primary_and_secondary_catalog_rows(self):
        bound = set()
        for slot in self.intake["slots"]:
            for seed in slot["master_seeds"]:
                with self.subTest(seed=seed["master_ref"]):
                    self.assertTrue("grand_refs" in seed, "seed lacks explicit primary/secondary catalog refs")
                    entry = pointer(self.master, seed["master_ref"].split("#", 1)[1])
                    primary = re.search(r"source=(catalogs/landscape/grand-catalog-20261008.json#/rows/[0-9]+)", entry)
                    expected = [primary.group(1)] if primary else []
                    secondary = re.search(r"also_rows=([0-9,]+)", entry)
                    if secondary:
                        expected.extend(GRAND + "#/rows/" + n for n in secondary.group(1).split(","))
                    self.assertEqual(seed["grand_refs"], list(dict.fromkeys(expected)))
                    bound.update(seed["grand_refs"])
            self.assertEqual({ref for seed in slot["master_seeds"] for ref in seed.get("grand_refs", [])},
                             set(slot["grand_row_refs"]))
        self.assertEqual(len(bound), self.intake["counts"]["skills_grand_rows"])

    def test_resolution_snapshot_records_each_slot_gap_and_retained_parent_state(self):
        self.assertTrue("layer_resolution" in self.intake, "per-layer resolution snapshot is absent")
        binding = self.intake["layer_resolution"]
        raw = (ROOT / binding["path"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), binding["sha256"])
        state = json.loads(raw)
        for path, digest in state["source_bindings"].items():
            self.assertEqual(hashlib.sha256(frozen_bytes(ROOT, state["source_commit"], path)).hexdigest(),
                             digest["sha256"], path)
        self.assertEqual({row["layer_id"] for row in state["slots"]},
                         {row["layer_id"] for row in self.intake["slots"]})
        for row in state["slots"]:
            self.assertEqual(row["verdict"]["state"], "ABSENT")
            self.assertEqual(row["wave"]["state"], "ABSENT")
            self.assertEqual(row["latest_covering_sweep"]["state"], "ABSENT")
            self.assertIsNone(row["cumulative_survivors"]["items"])
            self.assertTrue(row["next_delta"])
        parent = state["instructions_skills"]
        closeout = json.loads(frozen_bytes(ROOT, state["source_commit"], parent["closeout_path"]))
        retained = next(row for row in closeout["layers"] if row["layer_id"] == "instructions-skills")
        self.assertEqual(parent["latest_sweep"], retained["latest_sweep"])
        self.assertEqual(parent["unresolved"], retained["unresolved"])
        self.assertEqual(parent["terminal_state"], "SCHEDULED")
        ledger = json.loads(frozen_bytes(ROOT, state["source_commit"], "catalogs/saturation/ledger.json"))
        for row in state["slots"]:
            self.assertFalse(any(layer.get("layer_id") == row["layer_id"]
                                 for sweep in ledger["sweeps"] for layer in sweep.get("layers", [])))

    def test_handoff_binds_comparison_scope_readiness_and_oracle_references(self):
        self.assertTrue("comparison" in self.intake, "immutable comparison binding is absent")
        binding = self.intake["comparison"]
        raw = frozen_bytes(ROOT, binding["source_commit"], binding["path"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), binding["sha256"])
        comparison = json.loads(raw)
        self.assertEqual(binding["comparison_id"], comparison["comparison_id"])
        self.assertEqual(binding["frozen_scope"], comparison["scope_status"])
        for ref in [binding["scope_ref"], binding["readiness_ref"], *binding["task_oracle_refs"]]:
            path, fragment = ref.split("#", 1)
            value = json.loads(frozen_bytes(ROOT, binding["source_commit"], path))
            self.assertTrue(pointer(value, fragment))
        self.assertEqual(binding["task_oracle_state"], "SPECIFICATION_ONLY; OWNER_PACKET_UNSEALED")

    def test_unretained_registry_execution_is_explicitly_unverified(self):
        probe = self.intake["gsd_seed"]["registry_probe"]
        self.assertEqual(probe.get("state"), "UNVERIFIED_HISTORICAL_RESULT")
        self.assertIsNone(probe.get("exit_code"))
        self.assertIsNone(probe.get("stdout_ref"))
        self.assertIsNone(probe.get("stderr_ref"))
        self.assertEqual(probe["reported_exit_code"], 0)
        self.assertTrue(probe["reported_third_party_leads"])
        self.assertIn("unverified", self.intake["vendor_discovery"]["probe_result"].lower())


if __name__ == "__main__":
    unittest.main()
