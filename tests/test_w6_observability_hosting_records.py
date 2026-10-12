"""Review regressions for the W6 observability/recovery preregistration.

These verify frozen record contracts, not backend, broker or recovery acceptance.
"""

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "evidence/artifacts/w6-observability-hosting-20261011"


def load(name):
    return json.loads((ARTIFACT / name).read_text())


class ObservabilityRecordContracts(unittest.TestCase):
    def test_corrected_citations_and_explicit_deployment_gap(self):
        sources = {s["repository"].removeprefix("https://github.com/"): s
                   for s in load("primary-sources.json")["sources"]}
        for repo, bad in (("grafana/loki", "README.md:23"),
                          ("prometheus/prometheus", "README.md:38"),
                          ("open-telemetry/opentelemetry-collector-contrib", "README.md:38")):
            self.assertNotEqual(sources[repo]["role_ref"], bad)
        signoz = sources["SigNoz/signoz"]
        self.assertIsNone(signoz["install_ref"])
        self.assertIn("Foundry", signoz["install_gap"])
        self.assertNotEqual(signoz["test_ref"], "Makefile:102")
        arm = next(a for a in load("preregistration.json")["arms"] if a["id"] == "signoz")
        self.assertIsNone(arm["transport"])
        self.assertTrue(arm["deployment_gap"])

    def test_reference_arm_covers_and_reconciles_operational_components(self):
        config = load("preregistration.json")
        arm = next(a for a in config["arms"] if a["id"] == "grafana-stack")
        components = {c.get("component_id"): c for c in arm["components"]}
        expected = {"grafana", "loki", "prometheus", "opentelemetry-collector-contrib", "alertmanager", "ntfy"}
        self.assertEqual(set(components), expected)
        for component_id, component in components.items():
            entry = config["run_pin_reconciliation"][component_id]
            self.assertEqual(entry["comparison_source_pin"], component["pin"])
            self.assertEqual(entry["comparison_release"].removeprefix("v"), entry["operational_run_pin"])
            self.assertFalse(entry["receipt_transfer_allowed"])

    def test_recovery_survivor_has_competing_mechanisms_and_separate_oracles(self):
        config = load("preregistration.json")
        self.assertIn("recovery_subrole", config)
        recovery = config["recovery_subrole"]
        self.assertEqual({a["id"] for a in recovery["arms"]},
                         {"rest-server-append-only", "restic-sftp", "rclone-append-only"})
        self.assertTrue(recovery["immutable_snapshot_disposition"]["reason"])
        self.assertTrue(recovery["oracle"]["off_host_destination_required"])
        self.assertTrue(recovery["oracle"]["append_only_client_deletion_refused"])
        self.assertTrue(recovery["oracle"]["fresh_target_restore_required"])
        self.assertFalse(recovery["failure_retires_telemetry_backend"])
        self.assertEqual(config["cumulative_survivor_disposition"]["disposition"],
                         "included_in_frozen_recovery_subrole_comparison")
        self.assertNotIn("restic/rest-server", json.dumps(config["common_recovery_dependencies"]))

    def test_wave_arms_and_each_requirement_role_have_a_disposition(self):
        config = load("preregistration.json")
        self.assertIn("wave_dispositions", config)
        self.assertEqual(set(config["wave_dispositions"]["retained_arms"]),
                         {"c14+c5+c6", "c14+c6", "c8", "c3"})
        self.assertTrue(config["wave_dispositions"]["why_plan_rule_governs"])
        roles = config["role_checks"]
        for role in ("telemetry", "dashboards", "alerting", "process_supervision", "authority", "live_state_recovery"):
            self.assertTrue(roles[role]["case_ids"])
            self.assertTrue(roles[role]["mandatory_checks"])
        for case in load("telemetry-cases.json")["cases"]:
            self.assertTrue(case["role_ids"])
            self.assertTrue(case["oracle"])

    def test_decisive_metrics_are_frozen_with_noise_tolerances(self):
        config = load("preregistration.json")
        self.assertIn("measurement_protocol", config)
        measurement = config["measurement_protocol"]
        for key in ("elapsed_start", "elapsed_stop", "rss_process_set", "rss_aggregation"):
            self.assertTrue(measurement[key])
        self.assertGreater(measurement["elapsed_tolerance_fraction"], 0)
        self.assertGreater(measurement["rss_tolerance_fraction"], 0)
        self.assertEqual(config["fixed_decision_rule"]["rank_keys"], ["median_elapsed_ns", "median_peak_rss_bytes"])
        self.assertNotIn("existing Grafana", config["fixed_decision_rule"]["tie"])

    def test_shared_facts_bind_only_to_main_and_durable_doc_has_no_review_queue(self):
        delta = load("resolution-delta.json")
        for fact in delta["foundation_shared_fact_refs"]:
            self.assertNotIn("pr", fact)
            self.assertNotIn("head", fact)
            self.assertIn("commit", fact)
            self.assertTrue(fact["commit"])
        doc = (ROOT / "docs/w6-observability-hosting-delta-20261011.md").read_text()
        self.assertNotIn("Astra and CC Opus reads remain required", doc)
        self.assertNotIn("Only the skills-lifecycle source fingerprint changes", doc)

    def test_refrozen_hashes_bind_all_terminal_copies(self):
        config = load("preregistration.json")
        delta = load("resolution-delta.json")
        digest = hashlib.sha256((ARTIFACT / "preregistration.json").read_bytes()).hexdigest()
        fixture = hashlib.sha256((ARTIFACT / "telemetry-cases.json").read_bytes()).hexdigest()
        self.assertEqual(delta["preregistration_sha256"], digest)
        self.assertEqual(delta["terminal_evidence"]["preregistration_sha256"], digest)
        self.assertEqual(config["fixture_seal"]["sha256"], fixture)
        self.assertEqual(delta["fixture_sha256"], fixture)
        self.assertEqual(delta["terminal_state"], "SCHEDULED")
        self.assertFalse(delta["terminal_evidence"]["final_claim"])


if __name__ == "__main__":
    unittest.main()
