"""SYN public CLI tests; no credentials, account reads, orders or GO writes."""
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tests.adaptive_paper_hermetic import real_tmp_root

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "blueprints/us-equities/adaptive-paper"
SCRIPT = ENGINE / "preset_sets.py"
NOW = "2026-10-13T16:15:00+00:00"


class PresetSetCLI(unittest.TestCase):
    def test_public_record_does_not_cite_a_private_sealed_packet_digest(self):
        record = (ROOT / "docs/decisions/2026-10-13-lane-b-acct-sized-v1.md").read_text()
        self.assertNotRegex(record, r"sealed [0-9a-f]{8,64} deployment")

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(dir="/var/tmp")
        self.addCleanup(self.scratch.cleanup)
        self.root = real_tmp_root(self.scratch.name)
        self.controls = self.root / "controls"
        self.controls.mkdir()
        self.base = json.loads((ENGINE / "config-sip.json").read_text())
        (self.controls / "sip.json").write_text(json.dumps(self.base))
        self.fact = {"schema_version": 1, "paper_lane": "B", "evidence_class": "synthetic",
                     "inventory_id": "alpaca-paper", "pass_id": "pass-2",
                     "observed_at_utc": NOW, "currency": "USD", "equity_usd": "40000",
                     "flat": True, "positions_count": 0, "open_orders_count": 0}
        self.fact_path = self.root / "pass-start.json"
        self.out = self.root / "packet"

    def run_cli(self, preset="acct-sized-v1", **overrides):
        self.fact_path.write_text(json.dumps(self.fact))
        args = {"--controls": str(self.controls), "--stages": "sip",
                "--pass-start-receipt": str(self.fact_path), "--pass-id": "pass-2",
                "--preset-set": preset, "--output": str(self.out), "--now": NOW}
        args.update(overrides)
        return subprocess.run([sys.executable, "-E", "-s", "-B", str(SCRIPT),
                    *[s for k,v in args.items() for s in (k,v)]], capture_output=True, text=True)

    def test_account_equity_derives_capital_and_all_caps(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads((self.out / "configs/sip.json").read_text())
        self.assertEqual({k:config[k] for k in self.base if k.endswith("_usd")},
                         {"capital_usd": "20000.00", "max_gross_exposure_usd": "10000.00",
                          "max_order_notional_usd": "2000.00", "max_gross_loss_usd": "50.00",
                          "max_drawdown_usd": "50.00"})
        self.assertEqual(config["max_order_qty_mode"], "notional")
        self.assertEqual(config["max_order_quantity"], 1000000000)
        self.assertEqual(config["risk_ceilings"], {"capital_usd": "1000000",
            "max_order_notional_usd": "2000.00", "max_order_quantity": 1000000000})
        for key in self.base.keys() - {"capital_usd", "max_gross_exposure_usd", "max_order_notional_usd",
                                      "max_gross_loss_usd", "max_drawdown_usd", "max_order_quantity", "max_order_qty_mode"}:
            self.assertEqual(config[key], self.base[key], key)

    def test_nonobject_fact_is_a_structured_refusal(self):
        for fact in ([], None):
            with self.subTest(fact=fact):
                self.fact = fact
                result = self.run_cli()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(json.loads(result.stdout)["reason"], "pass_start_fact_schema")
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(self.out.exists())

    def test_fixture_resolves_a_platform_symlink_ancestor(self):
        alias = self.root / "platform-var-alias"
        alias.symlink_to(self.root, target_is_directory=True)
        factory = tempfile.TemporaryDirectory
        with patch.object(tempfile, "TemporaryDirectory", side_effect=lambda **_: factory(dir=alias)):
            fixture = PresetSetCLI()
            fixture.setUp()
        try:
            self.assertEqual(fixture.root, fixture.root.resolve())
            result = fixture.run_cli()
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(result.stdout)
            checked = subprocess.run([sys.executable, "-E", "-s", "-B", str(SCRIPT),
                "--check-packet", str(fixture.out), "--stage", "sip", "--pass-id", "pass-2",
                "--preset-set", "acct-sized-v1", "--preset-manifest-sha256", receipt["preset_manifest_sha256"],
                "--inventory-sha256", receipt["inventory_sha256"]], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
        finally:
            fixture.doCleanups()

    def test_public_binding_omits_private_equity(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        checked = subprocess.run([sys.executable, "-E", "-s", "-B", str(SCRIPT),
            "--check-packet", str(self.out), "--stage", "sip", "--pass-id", "pass-2",
            "--preset-set", "acct-sized-v1", "--preset-manifest-sha256", receipt["preset_manifest_sha256"],
            "--inventory-sha256", receipt["inventory_sha256"]], capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertNotIn("pass_start_equity_usd", json.loads(checked.stdout))
        # The retained private packet still binds the actual denominator.
        manifest = json.loads((self.out / "preset-manifest.json").read_text())
        self.assertEqual(manifest["pass_start_equity_usd"], "40000")

    def test_activation_contract_requires_recorded_rebasing_before_alternation(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.out / "preset-manifest.json").read_text())
        self.assertEqual(manifest["capital_transition"], {
            "version": "per-arm-rebasing-v1", "status": "NOT_IMPLEMENTED",
            "journal": "same_account", "preserve_lifetime_totals": True,
            "preserve_per_arm_loss_and_drawdown": True, "activation": "REFUSED"})

    def test_tampered_file_extra_file_and_wrong_manifest_digest_are_refused(self):
        for case, reason in (("bytes", "preset_packet_hash_mismatch"),
                             ("extra", "preset_packet_inventory_differs"),
                             ("manifest", "preset_manifest_binding_mismatch")):
            with self.subTest(case=case):
                self.out = self.root / case
                generated = self.run_cli()
                self.assertEqual(generated.returncode, 0, generated.stderr)
                receipt = json.loads(generated.stdout)
                if case == "bytes":
                    target = self.out / "configs/sip.json"
                    target.chmod(0o600)
                    target.write_bytes(target.read_bytes() + b"\n")
                elif case == "extra":
                    self.out.chmod(0o700)
                    (self.out / "uninventoried.json").write_text("{}")
                else:
                    receipt["preset_manifest_sha256"] = "0" * 64
                checked = subprocess.run([sys.executable, "-E", "-s", "-B", str(SCRIPT),
                    "--check-packet", str(self.out), "--stage", "sip", "--pass-id", "pass-2",
                    "--preset-set", "acct-sized-v1", "--preset-manifest-sha256", receipt["preset_manifest_sha256"],
                    "--inventory-sha256", receipt["inventory_sha256"]], capture_output=True, text=True)
                self.assertEqual(checked.returncode, 2, checked.stderr)
                self.assertEqual(json.loads(checked.stdout)["reason"], reason)

    def test_packet_binding_refuses_a_symlinked_parent(self):
        generated = self.run_cli()
        self.assertEqual(generated.returncode, 0, generated.stderr)
        receipt = json.loads(generated.stdout)
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        checked = subprocess.run([sys.executable, "-E", "-s", "-B", str(SCRIPT),
            "--check-packet", str(alias / "packet"), "--stage", "sip", "--pass-id", "pass-2",
            "--preset-set", "acct-sized-v1", "--preset-manifest-sha256", receipt["preset_manifest_sha256"],
            "--inventory-sha256", receipt["inventory_sha256"]], capture_output=True, text=True)
        self.assertEqual(checked.returncode, 2, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)["reason"], "preset_packet_symlink")

    def test_control_preserves_exact_bytes_and_receipts_label_version(self):
        result = self.run_cli("control-v1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.out / "configs/sip.json").read_bytes(), (self.controls / "sip.json").read_bytes())
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["preset_set_version"], "control-v1")
        self.assertEqual(receipt["runtime_acceptance"], "NOT_RUN")
        self.assertEqual(receipt["data_class"], "synthetic")

    def test_all_rungs_edges_feeds_and_optional_pre_scale_their_own_control(self):
        sources = {"sip": "config-sip.json", "iex": "config.json", "pre": "config-mover.json",
                   "lev1": "config-leverage-1x.json", "lev2": "config-leverage-2x.json",
                   "lev4": "config-leverage-4x.json", "edge2": "config-sip.json", "edge8": "config-sip.json"}
        for stage,name in sources.items():
            config = json.loads((ENGINE / name).read_text())
            if stage.startswith("edge"):
                config["minimum_edge_bps"] = int(stage[4:])
            (self.controls / (stage + ".json")).write_text(json.dumps(config))
        result = self.run_cli(**{"--stages": ",".join(sources)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for stage in sources:
            before = json.loads((self.controls / (stage + ".json")).read_text())
            after = json.loads((self.out / "configs" / (stage + ".json")).read_text())
            self.assertEqual(after["capital_usd"], "20000.00")
            self.assertEqual(after["max_order_quantity"], 1000000000)
            self.assertEqual(after["max_order_qty_mode"], "notional")
            self.assertEqual(after.get("leverage_policy"), before.get("leverage_policy"))
        pre = json.loads((self.out / "configs/pre.json").read_text())
        self.assertEqual(pre["mover"]["max_entry_notional_usd"], "400.00")
        self.assertEqual(pre["max_gross_exposure_usd"], "4000.00")
        lev4 = json.loads((self.out / "configs/lev4.json").read_text())
        self.assertEqual(lev4["max_gross_exposure_usd"], "80000.00")
        self.assertEqual(lev4["max_order_notional_usd"], "8000.00")
        self.assertEqual(lev4["max_gross_loss_usd"], "200.00")

    def test_missing_equity_refuses_without_a_packet(self):
        del self.fact["equity_usd"]
        result = self.run_cli()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["reason"], "pass_start_fact_schema")
        self.assertFalse(self.out.exists())

    def test_invalid_equity_refuses_without_echoing_input(self):
        for value in ("NaN", "Infinity", "-1", "0", True, "not-equity"):
            with self.subTest(value=value):
                self.fact["equity_usd"] = value
                result = self.run_cli()
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["reason"], "positive_decimal_required")
                self.assertFalse(self.out.exists())

    def test_wrong_pass_stale_or_unflat_fact_refuses(self):
        for field,value,reason in (("pass_id", "other-pass", "pass_start_wrong_pass"),
                ("observed_at_utc", "2026-10-13T16:09:59Z", "pass_start_fact_stale_or_future"),
                ("observed_at_utc", "2026-10-13T16:15:01Z", "pass_start_fact_stale_or_future"),
                ("flat", False, "pass_start_not_flat"), ("open_orders_count", 1, "pass_start_not_flat")):
            with self.subTest(field=field, value=value):
                before = self.fact[field]
                self.fact[field] = value
                result = self.run_cli()
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["reason"], reason)
                self.assertFalse(self.out.exists())
                self.fact[field] = before

    def test_landed_D6b_ceilings_preserve_account_sized_notional(self):
        self.fact["equity_usd"] = "400000"
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        config = json.loads((self.out / "configs/sip.json").read_text())
        self.assertEqual(config["capital_usd"], "200000.00")
        self.assertEqual(config["max_order_notional_usd"], "20000.00")
        self.assertEqual(config["risk_ceilings"]["max_order_notional_usd"], "20000.00")
        manifest = json.loads((self.out / "preset-manifest.json").read_text())
        self.assertEqual(manifest["configs"][0]["derivation"]["order_notional_ceiling"],
                         {"effective_usd": "20000.00", "basis": "scaled_control_cap",
                          "registered_risk_ceiling_usd": "20000.00", "clamped": False})

    def test_capital_over_existing_ceiling_still_refuses(self):
        self.fact["equity_usd"] = "3000000"
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["reason"], "native_config_or_code_ceiling_refused")
        self.assertFalse(self.out.exists())

    def test_scaled_capital_rounds_down_to_cents(self):
        self.fact["equity_usd"] = "40000.039"
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        config = json.loads((self.out / "configs/sip.json").read_text())
        self.assertEqual(config["capital_usd"], "20000.01")
        self.assertEqual(config["max_order_notional_usd"], "2000.00")

    def test_unknown_dollar_field_is_not_silently_left_unscaled(self):
        self.base["new_risk_cap_usd"] = "10"
        (self.controls / "sip.json").write_text(json.dumps(self.base))
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["reason"], "unregistered_dollar_field")

    def test_generated_packet_is_strict_and_cannot_be_replaced(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        checked = subprocess.run(["sha256sum", "--check", "--strict", "SHA256SUMS"],
                                 cwd=self.out, capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        before = (self.out / "SHA256SUMS").read_bytes()
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual((self.out / "SHA256SUMS").read_bytes(), before)

    def test_native_fact_disallows_caller_clock_and_private_extra_fields(self):
        self.fact["evidence_class"] = "native_paper"
        result = self.run_cli()
        self.assertEqual(json.loads(result.stdout)["reason"], "native_clock_override_refused")
        self.fact["evidence_class"] = "synthetic"
        self.fact["account_id"] = "SYN-identifier-must-not-publish"
        result = self.run_cli()
        self.assertEqual(json.loads(result.stdout)["reason"], "pass_start_fact_schema")
        self.assertNotIn(self.fact["account_id"], result.stdout + result.stderr)

    def test_per_pass_selection_binds_version_pass_and_all_packet_bytes(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        args = [sys.executable, "-E", "-s", "-B", str(SCRIPT), "--check-packet", str(self.out),
                "--stage", "sip", "--pass-id", "pass-2", "--preset-set", "acct-sized-v1",
                "--preset-manifest-sha256", hashlib.sha256((self.out / "preset-manifest.json").read_bytes()).hexdigest(),
                "--inventory-sha256", hashlib.sha256((self.out / "SHA256SUMS").read_bytes()).hexdigest()]
        checked = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        binding = json.loads(checked.stdout)
        self.assertEqual(binding["preset_set_version"], "acct-sized-v1")
        self.assertEqual(binding["pass_id"], "pass-2")
        self.assertEqual(binding["stage"], "sip")
        for option,replacement,reason in (("--pass-id", "pass-1", "preset_pass_or_version_mismatch"),
                ("--preset-set", "control-v1", "preset_pass_or_version_mismatch"),
                ("--stage", "pre", "preset_stage_not_in_pass"),
                ("--inventory-sha256", "0" * 64, "preset_inventory_binding_mismatch")):
            with self.subTest(option=option):
                changed = args.copy();changed[changed.index(option)+1] = replacement
                refused = subprocess.run(changed, capture_output=True, text=True)
                self.assertEqual(refused.returncode, 2)
                self.assertEqual(json.loads(refused.stdout)["reason"], reason)

    def test_alternating_passes_select_distinct_frozen_sets(self):
        bindings = []
        for preset,pass_id in (("control-v1", "pass-1"), ("acct-sized-v1", "pass-2")):
            self.fact["pass_id"] = pass_id
            self.out = self.root / pass_id
            generated = self.run_cli(preset, **{"--pass-id": pass_id})
            self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
            receipt = json.loads(generated.stdout)
            checked = subprocess.run([sys.executable, "-E", "-s", "-B", str(SCRIPT),
                "--check-packet", str(self.out), "--stage", "sip", "--pass-id", pass_id,
                "--preset-set", preset, "--preset-manifest-sha256", receipt["preset_manifest_sha256"],
                "--inventory-sha256", receipt["inventory_sha256"]], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            bindings.append(json.loads(checked.stdout))
        self.assertEqual([v["preset_set_version"] for v in bindings], ["control-v1", "acct-sized-v1"])
        self.assertEqual([v["pass_id"] for v in bindings], ["pass-1", "pass-2"])
        self.assertNotEqual(bindings[0]["config_sha256"], bindings[1]["config_sha256"])
        self.assertTrue(all("pass_start_equity_usd" not in v for v in bindings))


if __name__ == "__main__":
    unittest.main()
