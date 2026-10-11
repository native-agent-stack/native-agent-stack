"""Exercise retained SPY data with the existing fixture and native venue models.

Reference implementation: spy-parity/run.py:544 and fixture_strategy.py:245;
Nautilus rc5 BacktestEngine.add_venue and execution.FixedFeeModel. This is a
diagnostic of configured mechanics, not the frozen stress/adaptive parity gate.
No distribution/fill/fee is patched after the native run.
"""

import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
PARITY = ROOT / "blueprints/us-equities/engine-nautilus/spy-parity"


def expected_economics(target, commission):
    """Recompute the fixed diagnostic from independently accepted fixture inputs.

    Source: spy-parity/fixture_strategy.py:118-122 and historical-simulation/plan.json
    at 8bffa2c41692ef483e91b68e3b15aeb331423d2c; the accepted LEAN comparator's
    expected prices/dividend cash are pinned below, never taken from this run.
    This is the configured zero-slippage diagnostic, not the frozen stress case.
    """
    reference_path = ROOT / ("evidence/artifacts/backtesting-gap-burndown-20261010/"
                             "us-equities__backtesting-engine/raw/accepted-v2-lean-data.verdict.json")
    reference_bytes = reference_path.read_bytes()
    plan_bytes = (ROOT / "blueprints/us-equities/historical-simulation/plan.json").read_bytes()
    if (hashlib.sha256(reference_bytes).hexdigest() !=
            "8d6b96cc44f333c7f7d1216b23b5eb654100439566bcda0344034d4b215760f4" or
            hashlib.sha256(plan_bytes).hexdigest() !=
            "60959a050a3b004abf5346d376930b3b2f563096c725dc96e5427703ea203632"):
        raise ValueError("mechanics_reference_inputs_changed")
    reference = json.loads(reference_bytes)
    plan = json.loads(plan_bytes)
    def expected(identifier, field):
        rows = [row for row in reference["checks"] if row["id"] == identifier and row["field"] == field]
        if len(rows) != 1 or rows[0]["status"] != "PASS":
            raise ValueError("mechanics_reference_check_missing")
        return Decimal(rows[0]["expected"])
    spec = importlib.util.spec_from_file_location("mechanics_fixture", PARITY / "fixture_strategy.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    initial = Decimal(plan["initial_cash_usd"])
    quantity = fixture.target_quantity(initial, Decimal(target),
        Decimal(plan["requested_target_sizing_multiplier"]), expected("entry_oco", "reference_close"))
    entry = expected("entry_fill", "fill_price_usd")
    exit_price = expected("exit_fill", "fill_price_usd")
    dividend_per_share = (expected("distributions_total", "dividend_cash_usd") /
                          expected("entry_fill", "signed_quantity"))
    end_cash = initial + quantity * (exit_price - entry + dividend_per_share) - commission * 2
    return quantity, entry, exit_price, end_cash


def project_result(name, target, account, result):
    denied = [event for event in result["order_events"] if event["event"] == "OrderDenied"]
    status = "completed"
    if name == "four-cash-refusal":
        if (len(denied) != 2 or result["fills"] or
                any(not event.get("reason", "").startswith("NOTIONAL_EXCEEDS_FREE_BALANCE:") for event in denied)):
            raise ValueError("expected_refusal_requires_native_denial_events")
        status = "expected_refusal"
    elif denied:
        raise ValueError("unexpected_native_denial")
    if result["engine_log_scan"].get("error_lines") != 0:
        raise ValueError("native_engine_errors")
    if status == "completed":
        # The unchanged fixture is a two-fill round trip. Empty/flat runs do not
        # exercise venue models (spy-parity/fixture_strategy.py:245 and run.py:544).
        commission = {"one-fixed-fee": Decimal("1"), "two-margin-zero": Decimal("0"),
                      "two-margin-fixed-fee": Decimal("1")}.get(name)
        if commission is None:
            raise ValueError("unknown_mechanics_case")
        fills = result["fills"]
        if (len(fills) != 2 or [f["side"] for f in fills] != ["BUY", "SELL"] or
                Decimal(str(fills[0]["quantity"])) <= 0 or
                Decimal(str(fills[0]["quantity"])) + Decimal(str(fills[1]["quantity"])) != 0):
            raise ValueError("expected_native_fills_not_exercised")
        if (Decimal(result["fees_usd"]) != commission * len(fills) or
                any(Decimal(f["fee"]) != commission for f in fills)):
            raise ValueError("expected_native_fees_not_charged")
        if (not result["cash_ledger"] or
                Decimal(result["cash_ledger"][-1]["cash"]) != Decimal(result["native_end_cash_usd"]) or
                Decimal(result["native_end_cash_usd"]) == Decimal("100000")):
            raise ValueError("native_economic_transition_missing")
        configuration = {"one-fixed-fee": ("1", "CASH"), "two-margin-zero": ("2", "MARGIN"),
                         "two-margin-fixed-fee": ("2", "MARGIN")}
        if (target, account) != configuration[name]:
            raise ValueError("mechanics_case_configuration_changed")
        quantity, entry_price, exit_price, end_cash = expected_economics(target, commission)
        if [Decimal(str(fill["quantity"])) for fill in fills] != [quantity, -quantity]:
            raise ValueError("mechanics_target_quantity_mismatch")
        if [Decimal(fill["price"]) for fill in fills] != [entry_price, exit_price]:
            raise ValueError("mechanics_fill_price_mismatch")
        if Decimal(result["native_end_cash_usd"]) != end_cash:
            raise ValueError("mechanics_expected_end_cash_mismatch")
    return {"id": name, "status": status, "target": target, "account_type": account,
            "native_fills": result["fills"], "native_account_events": result["native_account_event_rows"],
            "native_end_cash": result["native_end_cash_usd"], "native_fees": result["fees_usd"],
            "module_emissions": result["distribution_module"]["emissions"],
            "native_order_events": result["order_events"], "cash_ledger": result["cash_ledger"],
            "engine_error_lines": result["engine_log_scan"].get("error_lines"),
            "qualifies_frozen_stress_case": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("existing_spy_parity", PARITY / "run.py")
    replay = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = replay
    spec.loader.exec_module(replay)
    from nautilus_trader.execution import FixedFeeModel
    from nautilus_trader.model import Currency, Money

    usd = Currency.from_str("USD")
    manifest_v2, manifest = replay.load_bound_manifests()
    replay.check_engine_binary(manifest_v2)
    conversion = replay.CONVERT.convert(args.data, "SPY", "2019-12-02", "2020-04-30",
                                        replay.known_short_sessions(manifest))
    events = replay.distribution_events(args.data)
    results = []
    for name, target, account, commission in [
        ("one-fixed-fee", "1", "CASH", "1"),
        ("two-margin-zero", "2", "MARGIN", "0"),
        ("two-margin-fixed-fee", "2", "MARGIN", "1"),
        ("four-cash-refusal", "4", "CASH", "1"),
    ]:
        case = dict(replay.CASE)
        case.update(id=name, target=target, fee_usd=commission)
        replay.CASE = case
        replay.VENUE = {**replay.VENUE, "account_type": account,
                        "fee_model": FixedFeeModel(Money(Decimal(commission), usd), charge_commission_once=True)}
        # Unexpected runner/projection failures propagate to the command exit.
        # A designed refusal is a completed native run with OrderDenied events,
        # never an arbitrary Python exception (spy-parity/run.py:630-698).
        result = replay.run_once(conversion["rows"], events, args.output / name, name)
        results.append(project_result(name, target, account, result))
    output = {"schema_version": 1, "scope": "native configured fee/margin/refusal diagnostics on retained bundled SPY",
              "results": results, "engine_pin": "1b0a49d2792a9432a3aca3fcb617ce7a630d905e",
              "slippage_fraction_mapped": False, "adaptive_state_implemented": False,
              "calibrated_liquidity": False,
              "limitations": ["The frozen 0.002 fractional-slippage and adaptive state cases are not implemented by this fixture.",
                              "Configured native MARGIN defaults are not a claim of equality with LEAN's buying-power model.",
                              "No gate, strategy, universe, paper or profitability acceptance."]}
    path = args.output / "results.json"
    path.write_text(json.dumps(output, indent=2, default=str) + "\n")
    print(json.dumps({"receipt": str(path), "cases": len(results),
                      "completed": sum(x["status"] == "completed" for x in results),
                      "expected_refusals": sum(x["status"] == "expected_refusal" for x in results),
                      "qualifies_frozen_stress_case": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
