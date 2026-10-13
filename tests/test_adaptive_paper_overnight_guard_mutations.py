"""In-memory guard deletion oracles, derived from reve's 2026-10-13 harness.

No production file is mutated. Each changed module is compiled in its own
existing namespace and restored before the next deletion. Explicit symbol
scopes avoid accidentally removing an older unrelated guard with the same text.
The ordinary CI suite executes this stdlib-only test; the native runner remains
additional fixture evidence, never a substitute for this coverage.
"""
import ast
import importlib
import io
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))

try:
    from . import test_adaptive_paper_overnight_order_contract as contract_tests
    from . import test_adaptive_paper_overnight_arming as lifecycle_tests
except ImportError:
    import test_adaptive_paper_overnight_order_contract as contract_tests
    import test_adaptive_paper_overnight_arming as lifecycle_tests


# name, module, qualified definition, deletion, replacement, test module/class
MUTANTS = (
    ("pre_entry_refusal", "overnight", "overnight_dispatch_refusal", 'side != "sell" or reduce_only is not True', "False", "lifecycle", "OvernightArming.test_pre_entry_remains_refused"),
    ("type", "overnight", "check_overnight_order", 'order.get("type") != "limit"', "False", "contract", "OvernightBrokerOrderShape"),
    ("tif", "overnight", "check_overnight_order", 'order.get("time_in_force") not in ("day", "gtc")', "False", "contract", "OvernightBrokerOrderShape"),
    ("extended_flag", "overnight", "check_overnight_order", 'order.get("extended_hours") is not True', "False", "contract", "OvernightBrokerOrderShape"),
    ("class", "overnight", "check_overnight_order", 'order.get("order_class", "simple") != "simple"', "False", "contract", "OvernightBrokerOrderShape"),
    ("nested_fields", "overnight", "check_overnight_order", 'any(key in order for key in ("take_profit", "stop_loss", "trail_price", "trail_percent", "legs"))', "False", "contract", "OvernightBrokerOrderShape"),
    ("dispatch_policy", "overnight", "overnight_dispatch_refusal", 'session_policy.get("overnight_enabled") is not True', "False", "contract", "OvernightDispatchSeam"),
    ("dispatch_port", "overnight", "overnight_dispatch_refusal", 'getattr(port, "overnight_enabled", False) is not True', "False", "contract", "OvernightDispatchSeam"),
    ("dispatch_feed", "overnight", "overnight_dispatch_refusal", 'getattr(port, "feed", None) != "boats"', "False", "contract", "OvernightDispatchSeam"),
    ("dispatch_source", "overnight", "overnight_dispatch_refusal", 'getattr(port, "quote_source_mode", None) != "boats_rest"', "False", "contract", "OvernightDispatchSeam"),
    ("dispatch_callback", "overnight", "overnight_dispatch_refusal", 'port.overnight_check(symbol, now, side)', "None", "contract", "OvernightDispatchSeam"),
    ("dispatch_carry_pre", "overnight", "overnight_dispatch_refusal", 'if getattr(port, "overnight_enabled", False) is True:', "if False:", "contract", "OvernightDispatchSeam"),
    ("exit_qualification", "exits", "ExitPlan.evaluate", 'ctx.session == "OVERNIGHT" and ctx.overnight_qualified is not True', "False", "contract", "OvernightClientSideExitContract"),
    ("exit_quote_freshness", "exits", "ExitPlan.evaluate", 'if not ctx.quote_fresh:', "if False:", "contract", "OvernightClientSideExitContract"),
    ("mover_x1_session", "mover", "plan_timing", 'if session_at(datetime.fromtimestamp(t0, timezone.utc)).kind == SessionKind.OVERNIGHT:', "if False:", "contract", "OvernightClientSideExitContract"),
    ("carrier_age", "runner", "Controller._check_overnight_status", 'if not 0 <= age <= status_timeout:', "if False:", "contract", "OvernightCarrierAtDispatch"),
    ("carrier_eligibility", "runner", "Controller._check_overnight_status", 'if status["overnight_tradable"] is not True:', "if False:", "contract", "OvernightCarrierAtDispatch"),
    ("carrier_halt", "runner", "Controller._check_overnight_status", 'if status["overnight_halted"] is not False or self.is_halted(symbol):', "if False:", "contract", "OvernightCarrierAtDispatch"),
    ("admission_quote_age", "runner", "Controller._check_overnight_admission", 'if not 0 <= now - quote.timestamp <= max_age:', "if False:", "contract", "OvernightAdmissionReasons"),
    ("admission_cutoff", "runner", "Controller._check_overnight_admission", 'if side == "buy" and now >= bounds["flatten_at"]:', "if False:", "contract", "OvernightAdmissionReasons"),
    ("halt_entry_cancel", "runner", "Controller.overnight_tick", 'self.is_halted(intent.symbol) or now >= window["flatten_at"]', 'False or now >= window["flatten_at"]', "lifecycle", "OvernightArming.test_third_d6_cutoff_halted_and_unknown_entries_cancel_without_reprice"),
    ("cutoff_entry_cancel", "runner", "Controller.overnight_tick", 'self.is_halted(intent.symbol) or now >= window["flatten_at"]', 'self.is_halted(intent.symbol) or False', "lifecycle", "OvernightArming.test_third_d6_cutoff_halted_and_unknown_entries_cancel_without_reprice"),
    ("day_expiry", "runner", "Controller.overnight_tick", 'if now >= window["day_expiry"] and self.ledger.positions():', "if False:", "lifecycle", "OvernightArming.test_halted_exit_rests_and_day_expiry_flags_freezes_and_notifies"),
    ("boundary_handoff", "runner", "Controller.overnight_tick", 'self._overnight_freeze("overnight_boundary_handoff")', "None", "lifecycle", "OvernightArming.test_no_pre_carry_forces_handoff_without_an_unresolved_order"),
    ("reprice_status", "runner", "Controller.overnight_reprice_allowed", 'self._check_overnight_admission(symbol, now, "sell")', "None", "lifecycle", "OvernightArming.test_missing_status_preserves_exit_repricing_until_fresh"),
    ("poll_symbol_bound", "overnight", "BoatsQuoteSource.__init__", 'not 1 <= len(self.symbols) <= 5', "False", "lifecycle", "OvernightArming.test_poll_bound_and_asset_refresh_never_restamp_cached_carrier"),
    ("poll_backoff", "overnight", "BoatsQuoteSource.sweep", 'if now < self.retry_at.get(symbol, 0):', "if False:", "lifecycle", "OvernightArming.test_rest_sweep_concurrent_bounded_and_429_preserves_state"),
    ("poll_refresh", "overnight", "BoatsQuoteSource.sweep", 'if now - self.asset_at.get(symbol, float("-inf")) >= self.asset_timeout:', 'if symbol not in self.assets:', "lifecycle", "OvernightArming.test_poll_bound_and_asset_refresh_never_restamp_cached_carrier"),
    ("persist_carry", "safety", "Ledger.record_overnight_window", 'self._set(key, encoded)', "None", "lifecycle", "OvernightArming.test_persisted_carry_deadline_reopens_and_cancels_accepted_entry"),
    ("fresh_rest_feed", "feeds", "require_qualified_quote_source", 'mode != "boats_rest" or type(value) is not str or value != "boats"', "False", "lifecycle", "OvernightArming.test_explicit_rest_opt_in_preserves_stream_refusal"),
    ("config_opt_in", "overnight", "overnight_config", 'block.get("enabled") is not True', "False", "contract", "OvernightConfigurationContract"),
    ("config_no_carry", "overnight", "overnight_config", 'config.get("sessions", {}).get("overnight_holds", False) is not False', "False", "contract", "OvernightConfigurationContract"),
    ("flatten_reserve", "overnight", "overnight_bounds", 'type(flatten_minutes) is not int or not 1 <= flatten_minutes <= 60', "False", "lifecycle", "OvernightArming.test_calendar_cutoff_and_no_pre_carry"),
    ("wire_carrier", "runner", "Controller._overnight_before_wire", 'self._check_overnight_admission(order["symbol"], now, order["side"])', "None", "lifecycle", "OvernightArming.test_wire_guard_repeats_carrier_check_immediately_before_post"),
    ("sdk_gtc", "transport", "limit_order_request", 'time_in_force=intent["time_in_force"]', 'time_in_force="day"', "lifecycle", "OvernightArming.test_sdk_request_keeps_gtc_from_the_explicit_envelope"),
    ("carrier_not_rth", "runner", "Controller.is_halted", 'getattr(self.port, "overnight_enabled", False) is True', "True", "lifecycle", "OvernightArming.test_overnight_carrier_cannot_halt_a_legacy_rth_port"),
    ("fill_high_receipt", "mover", "MoverBook.on_fill", 'if leg.running_high != previous_high:', "if False:", "lifecycle", "OvernightArming.test_mover_trail_samples_initial_and_raised_fill_high_only_on_change"),
)


def delete_in_definition(source, qualified, old, new):
    parts = qualified.split(".")
    node = ast.parse(source)
    for name in parts:
        node = next(child for child in node.body if getattr(child, "name", None) == name)
    lines = source.splitlines(keepends=True)
    body = "".join(lines[node.lineno - 1:node.end_lineno])
    if body.count(old) != 1:
        raise AssertionError(f"ambiguous/absent mutation operand in {qualified}: {old!r}")
    return "".join(lines[:node.lineno - 1]) + body.replace(old, new, 1) + "".join(lines[node.end_lineno:])


class OvernightGuardDeletionOracles(unittest.TestCase):
    def test_every_targeted_guard_deletion_fails_a_ci_test(self):
        modules = {name: importlib.import_module(name) for name in {m[1] for m in MUTANTS}}
        sources = {name: Path(module.__file__).read_text() for name, module in modules.items()}
        namespaces = {name: dict(module.__dict__) for name, module in modules.items()}
        results = []
        for name, module_name, qualified, old, new, test_module, test_name in MUTANTS:
            with self.subTest(guard=name):
                module = modules[module_name]
                mutated = delete_in_definition(sources[module_name], qualified, old, new)
                try:
                    exec(compile(mutated, f"in-memory-guard:{name}", "exec"), module.__dict__)
                    suite = unittest.defaultTestLoader.loadTestsFromName(test_name,
                        contract_tests if test_module == "contract" else lifecycle_tests)
                    output = io.StringIO()
                    result = unittest.TextTestRunner(stream=output).run(suite)
                    results.append((name, len(result.failures), len(result.errors)))
                    self.assertFalse(result.wasSuccessful(), f"guard deletion survived: {name}")
                    # Credit an assertion failure, never an import/compile error.
                    # Two peer assertRaises/subTest cases also access an absent
                    # context.exception after the primary failure; retain the count.
                    self.assertGreater(len(result.failures), 0, output.getvalue())
                finally:
                    # Restore exact class/function identities, including SafetyError.
                    # Recompiling baseline would break consumers' imported exceptions.
                    module.__dict__.clear()
                    module.__dict__.update(namespaces[module_name])
        self.assertEqual(len(results), len(MUTANTS))
        print("overnight_guard_mutations", len(results), "killed_by_assertions",
              sum(failures for _, failures, _ in results), "secondary_errors",
              sum(errors for _, _, errors in results))


if __name__ == "__main__":
    unittest.main(verbosity=2)
