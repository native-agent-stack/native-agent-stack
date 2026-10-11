"""Broken intake joins cannot silently manufacture starred-repository convergence."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.starred_convergence import validate_convergence

MANIFEST = "catalogs/convergence-practice/starred-convergence-20261010.json"
SEEDS = "catalogs/convergence-practice/starred-seeds-20261010.json"
EVIDENCE = "catalogs/convergence-practice/source.json"
REGISTRY = "catalogs/sota-convergence/layer-verdict-waves.json"


class StarredConvergenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.write("catalogs/foundation/manifest.json", {"layers": [{"id": "quality-evaluation"}, {"id": "code-navigation"}]})
        self.write(REGISTRY, {"schema_version": 1, "waves": []})
        self.write(EVIDENCE, {"rows": [{"repository": "owner/tool"}]})
        self.seeds = {"schema_version": 1, "seeds": [{"repository": "https://github.com/Owner/Tool",
                      "layer": "quality-evaluation", "reason": "Pinned source documents the checker role.",
                      "source_refs": [EVIDENCE + "#/rows/0"], "checked_at": "2026-10-10T16:00:00Z"}]}
        self.row = {"repository": "owner/tool", "scope": "IN-SCOPE", "layer_keys": ["quality-evaluation"],
                    "reason": "Source-only checker intake; execution and selection remain unqualified.",
                    "seed_refs": [SEEDS + "#/seeds/0"], "evidence_refs": [EVIDENCE + "#/rows/0"],
                    "verdict_refs": [], "verdict_follow_up": {"status": "AWAITING-RECORDED-TIER-VERDICT",
                    "required_tiers": ["tier-1", "tier-2"], "layer_keys": ["quality-evaluation"], "registry": REGISTRY}}
        self.manifest = {"schema_version": 1, "count": 1, "seed_manifest": SEEDS, "repositories": [self.row]}
        self.snapshot = {"count": 1, "convergence_manifest": MANIFEST, "repositories": []}
        self.sync()

    def write(self, path, document):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document))

    def sync(self):
        self.snapshot["count"] = self.manifest["count"]
        self.snapshot["repositories"] = [dict(row, disposition_status=row["scope"],
            disposition=row["scope"] + ": " + row["reason"], convergence_manifest=MANIFEST,
            decision_manifest=MANIFEST) for row in self.manifest["repositories"]]
        self.write(MANIFEST, self.manifest)
        self.write(SEEDS, self.seeds)

    def reject(self, message):
        self.sync()
        with self.assertRaisesRegex(ValueError, message):
            validate_convergence(self.root, self.snapshot)

    def test_casefold_url_join_accepts_recorded_intake_without_claiming_a_verdict(self):
        self.snapshot["repositories"][0]["repository"] = "https://github.com/OWNER/TOOL"
        self.assertEqual(validate_convergence(self.root, self.snapshot),
                         {"status": "valid", "count": 1, "pending": 0, "seed_count": 1, "in_scope": 1,
                          "out_of_scope": 0, "needs_evidence": 0, "archived": 0, "superseded": 0})

    def test_legacy_fixture_without_convergence_manifest_is_preserved(self):
        self.assertEqual(validate_convergence(self.root, {"repositories": [{"repository": "owner/tool"}]}),
                         {"status": "legacy", "count": 1})

    def test_source_review_status_does_not_claim_adoption_or_acceptance(self):
        self.snapshot["repositories"][0]["disposition_status"] = "IN-SCOPE-SOURCE-REVIEW"
        self.assertEqual(validate_convergence(self.root, self.snapshot)["in_scope"], 1)

    def test_wrong_seed_repository_fails(self):
        self.seeds["seeds"][0]["repository"] = "other/tool"
        self.reject("seed reference repository")

    def test_wrong_seed_layer_fails(self):
        self.seeds["seeds"][0]["layer"] = "code-navigation"
        self.reject("seed reference layer")

    def test_missing_seed_pointer_fails(self):
        self.row["seed_refs"] = [SEEDS + "#/seeds/4"]
        self.reject("JSON pointer array index missing")

    def test_each_layer_needs_its_own_seed(self):
        self.row["layer_keys"].append("code-navigation")
        self.row["verdict_follow_up"]["layer_keys"].append("code-navigation")
        self.reject("seed for every layer")

    def test_duplicate_normalized_manifest_identity_fails(self):
        duplicate = deepcopy(self.row)
        duplicate["repository"] = "https://github.com/OWNER/TOOL"
        self.manifest["repositories"].append(duplicate)
        self.manifest["count"] = 2
        self.reject("duplicate snapshot repository identity")

    def test_snapshot_and_manifest_disagreement_fails(self):
        self.snapshot["repositories"][0]["reason"] = "Unrecorded replacement."
        with self.assertRaisesRegex(ValueError, "snapshot disposition disagrees"):
            validate_convergence(self.root, self.snapshot)

    def test_snapshot_cannot_add_an_unrecorded_verdict_claim(self):
        self.snapshot["repositories"][0]["verdict_refs"] = [EVIDENCE + "#/rows/0"]
        with self.assertRaisesRegex(ValueError, "snapshot evidence or verdict"):
            validate_convergence(self.root, self.snapshot)

    def test_canonical_skills_ids_come_from_the_supported_tasks_collection(self):
        self.write("catalogs/landscape/skills-lifecycle.json", {"tasks": [{"layer_id": "skills-review"}]})
        self.seeds["seeds"][0]["layer"] = "skills-review"
        self.row["layer_keys"] = ["skills-review"]
        self.row["verdict_follow_up"]["layer_keys"] = ["skills-review"]
        self.sync()
        self.assertEqual(validate_convergence(self.root, self.snapshot)["status"], "valid")

    def test_completed_manifest_cannot_hide_pending(self):
        self.row["scope"] = "PENDING"
        self.reject("cannot be PENDING")

    def test_invented_tier_verdict_fails(self):
        self.row["verdict_refs"] = [EVIDENCE + "#/rows/0"]
        self.reject("same repository and explicit tier")

    def test_verdict_for_another_repository_fails(self):
        self.write(EVIDENCE, {"rows": [{"repository": "other/tool", "tier": "tier-1"}]})
        self.row["verdict_refs"] = [EVIDENCE + "#/rows/0"]
        self.reject("same repository and explicit tier")

    def test_missing_follow_up_fails(self):
        self.row.pop("verdict_follow_up")
        self.reject("honest recorded-tier follow-up")

    def test_follow_up_only_for_the_remaining_recorded_tier(self):
        self.write(EVIDENCE, {"rows": [{"repository": "owner/tool", "tier": "tier-1", "verdict": "candidate"}]})
        self.row["verdict_refs"] = [EVIDENCE + "#/rows/0"]
        self.row["verdict_follow_up"]["required_tiers"] = ["tier-2"]
        self.sync()
        self.assertEqual(validate_convergence(self.root, self.snapshot)["status"], "valid")

    def test_unpinned_source_url_fails(self):
        self.seeds["seeds"][0]["source_refs"] = ["https://github.com/owner/tool/blob/main/README.md"]
        self.reject("pinned public GitHub")

    def test_pinned_public_source_url_is_supported(self):
        self.seeds["seeds"][0]["source_refs"] = ["https://github.com/owner/tool/blob/" + "a" * 40 + "/README.md#L1"]
        self.sync()
        self.assertEqual(validate_convergence(self.root, self.snapshot)["status"], "valid")

    def test_out_of_scope_requires_a_reason_and_cannot_claim_seeds(self):
        self.row["scope"] = "OUT-OF-SCOPE"
        self.reject("must not claim layer or seed coverage")
        self.row["layer_keys"], self.row["seed_refs"], self.row["reason"] = [], [], " "
        self.reject("requires a recorded reason")

    def test_source_traversal_fails_before_external_file_access(self):
        self.row["evidence_refs"] = ["../outside.json#/rows/0"]
        self.reject("canonical and confined")

    def test_account_fields_are_not_allowed(self):
        self.seeds["seeds"][0]["owner"] = {"login": "public-account"}
        self.reject("account or private fields")

    def test_referenced_documents_scan_private_fields_for_every_reference_family(self):
        for field in ("login", "email", "token", "credential"):
            for family in ("seed", "evidence", "verdict"):
                with self.subTest(field=field, family=family):
                    extra = "catalogs/convergence-practice/extra.json"
                    self.write(extra, {"rows": [{"repository": "owner/tool", "tier": "tier-1"}],
                                       "unused": {field: "synthetic-forbidden-field"}})
                    if family == "seed":
                        self.seeds["seeds"][0]["source_refs"] = [extra + "#/rows/0"]
                    elif family == "evidence":
                        self.row["evidence_refs"] = [extra + "#/rows/0"]
                    else:
                        self.row["verdict_refs"] = [extra + "#/rows/0"]
                    self.reject("account or private fields")
                    self.seeds["seeds"][0]["source_refs"] = [EVIDENCE + "#/rows/0"]
                    self.row["evidence_refs"] = [EVIDENCE + "#/rows/0"]
                    self.row["verdict_refs"] = []

    def test_complete_tier_verdicts_reject_stale_follow_up(self):
        self.write(EVIDENCE, {"rows": [{"repository": "owner/tool", "tier": tier}
                                      for tier in ("tier-1", "tier-2")]})
        self.row["verdict_refs"] = [EVIDENCE + "#/rows/0", EVIDENCE + "#/rows/1"]
        self.reject("complete tier verdicts.*follow-up")
        self.row.pop("verdict_follow_up")
        self.sync()
        self.assertEqual(validate_convergence(self.root, self.snapshot)["status"], "valid")

    def test_metadata_reference_cannot_claim_pinned_source_review(self):
        self.seeds["seeds"][0]["evidence_class"] = "source_review"
        self.reject("source_review requires pinned")

    def test_historical_catalog_rows_have_reproducible_seed_witnesses(self):
        root = Path(__file__).resolve().parents[1]
        doc = json.loads((root / SEEDS).read_text())
        historical = [seed for seed in doc["seeds"] if "recorded_seed" in seed]
        self.assertEqual(len(historical), 528)
        for seed in historical:
            self.assertEqual(seed["evidence_class"], "metadata_seed_review")
            witness = seed["recorded_seed"]
            ref = witness["source_ref"]
            self.assertIn(ref, seed["source_refs"])
        snapshot = json.loads((root / "catalogs/convergence-practice/public-starred.json").read_text())
        self.assertEqual(validate_convergence(root, snapshot)["status"], "valid")


if __name__ == "__main__":
    unittest.main()
