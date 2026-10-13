"""Freeze a lane B preset packet from a sanitized pass-start fact.

No broker calls, credential loader, GO writer or deployment action. Existing
native config validators retain every ceiling. A generated packet needs separate
helper integration, review, runtime dry run and issuer validity binding.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

VERSION = "acct-sized-generator-v2"
STAGES = {"sip", "lev1", "lev2", "lev4", "edge2", "edge8", "iex", "pre"}
DOLLAR_CAPS = {"capital_usd", "max_gross_exposure_usd", "max_order_notional_usd",
               "max_gross_loss_usd", "max_drawdown_usd"}
OTHER_CAPS = {"mover.max_entry_notional_usd"}
PRICE_FIELDS = {"limit_offset_usd", "strategy.limit_offset_usd", "mover.limit_offset_usd"}
FACT_KEYS = {"schema_version", "paper_lane", "evidence_class", "inventory_id", "pass_id",
             "observed_at_utc", "currency", "equity_usd", "flat", "positions_count", "open_orders_count"}


class Refused(ValueError):
    pass


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def positive(value):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise Refused("positive_decimal_required")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise Refused("positive_decimal_required") from None
    if not result.is_finite() or result <= 0 or result > Decimal("1000000000"):
        raise Refused("positive_decimal_required")
    return result


def instant(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        raise Refused("invalid_observation_clock") from None


def regular_bytes(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1048576:
        raise Refused("regular_bounded_input_required")
    return path.read_bytes()


def fact_check(fact, pass_id, now):
    if not isinstance(fact, dict) or set(fact) != FACT_KEYS:
        raise Refused("pass_start_fact_schema")
    if (fact["schema_version"] != 1 or fact["paper_lane"] != "B"
            or fact["inventory_id"] != "alpaca-paper" or fact["currency"] != "USD"
            or fact["evidence_class"] not in ("native_paper", "synthetic")):
        raise Refused("pass_start_fact_binding")
    if fact["pass_id"] != pass_id:
        raise Refused("pass_start_wrong_pass")
    if (fact["flat"] is not True or type(fact["positions_count"]) is not int
            or type(fact["open_orders_count"]) is not int or fact["positions_count"] != 0
            or fact["open_orders_count"] != 0):
        raise Refused("pass_start_not_flat")
    age = (now - instant(fact["observed_at_utc"])).total_seconds()
    if not 0 <= age <= 300:
        raise Refused("pass_start_fact_stale_or_future")
    return positive(fact["equity_usd"])


def scaled_config(control, equity):
    capital = (equity * Decimal("0.5")).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    if capital <= 0 or not DOLLAR_CAPS.issubset(control):
        raise Refused("control_cap_schema")
    factor = capital / positive(control["capital_usd"])
    config = deepcopy(control)
    scaled = {}
    def visit(node, prefix=""):
        for key, value in list(node.items()):
            field = prefix + key
            if isinstance(value, dict):
                visit(value, field + ".")
            elif field in DOLLAR_CAPS | OTHER_CAPS:
                result = (positive(value) * factor).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                if result <= 0:
                    raise Refused("scaled_cap_rounds_to_zero")
                node[key] = format(result, ".2f")
                scaled[field] = {"control": str(value), "derived": node[key]}
            elif key.endswith("_usd") and field not in PRICE_FIELDS:
                raise Refused("unregistered_dollar_field")
    visit(config)
    config["capital_usd"] = format(capital, ".2f")
    # CC r1: adopt the landed #1088 explicit lane envelope. The parser's
    # largest whole-share ceiling removes the old 10/100-share truncation;
    # NOTIONAL sizing and the scaled dollar cap determine the actual order.
    # Capital retains D7's 1M bound. CONTROL gets no overrides or byte edits.
    quantity_ceiling = 1000000000
    config["risk_ceilings"] = {"capital_usd": "1000000",
        "max_order_notional_usd": config["max_order_notional_usd"],
        "max_order_quantity": quantity_ceiling}
    config["max_order_quantity"] = quantity_ceiling
    config["max_order_qty_mode"] = "notional"
    return config, {"factor": str(factor), "rounding": "ROUND_DOWN cents",
                    "order_notional_ceiling": {"effective_usd": config["max_order_notional_usd"],
                        "registered_risk_ceiling_usd": config["max_order_notional_usd"],
                        "basis": "scaled_control_cap", "clamped": False},
                    "quantity_ceiling": {"effective": quantity_ceiling, "code_maximum": 1000000000,
                        "basis": "D6b_explicit_lane_envelope_parser_bound"},
                    "sizing_mode": "notional", "fields": scaled}


def native_validate(path, stage):
    from safety import SafetyError
    try:
        if stage == "pre":
            from mover import load_mover_config
            load_mover_config(path)
        else:
            from runner import load_config
            load_config(path)
    except (ValueError, SafetyError):
        raise Refused("native_config_or_code_ceiling_refused") from None


def freeze(*, controls, stages, fact, pass_id, preset_set, output, now):
    if preset_set not in ("control-v1", "acct-sized-v1"):
        raise Refused("unknown_preset_set")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", pass_id):
        raise Refused("invalid_pass_id")
    if not stages or len(set(stages)) != len(stages) or not set(stages) <= STAGES:
        raise Refused("invalid_stage_order")
    equity = fact_check(fact, pass_id, now)
    controls, output = Path(controls), Path(output)
    if controls.is_symlink() or not controls.is_dir() or output.exists() or output.is_symlink():
        raise Refused("packet_input_or_destination_refused")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise Refused("packet_parent_refused")
    scratch = Path(tempfile.mkdtemp(prefix="preset-packet-", dir=output.parent))
    try:
        (scratch / "configs").mkdir(mode=0o700)
        (scratch / "control").mkdir(mode=0o700)
        rows = []
        for stage in stages:
            raw = regular_bytes(controls / (stage + ".json"))
            control = json.loads(raw)
            if preset_set == "acct-sized-v1":
                config, derivation = scaled_config(control, equity)
                derived = canonical(config)
            else:
                derived, derivation = raw, {"factor": "1", "control_bytes_unchanged": True}
            (scratch / "control" / (stage + ".json")).write_bytes(raw)
            target = scratch / "configs" / (stage + ".json")
            target.write_bytes(derived)
            native_validate(target, stage)
            rows.append({"stage": stage, "control_sha256": sha(raw), "config_sha256": sha(derived),
                         "derivation": derivation})
        fact_bytes = canonical(fact)
        (scratch / "pass-start.json").write_bytes(fact_bytes)
        generator = regular_bytes(Path(__file__))
        (scratch / "generator.py").write_bytes(generator)
        manifest = {"schema_version": 1, "paper_lane": "B", "evidence_class": "exploratory",
                    "helper_version": "preset-helpers-v2",
                    "data_class": fact["evidence_class"], "preset_set_version": preset_set,
                    "generator_version": VERSION, "generator_sha256": sha(generator),
                    "pass_id": pass_id, "pass_start_receipt_sha256": sha(fact_bytes),
                    "pass_start_equity_usd": str(equity), "equity_observed_at_utc": fact["observed_at_utc"],
                    "stage_order": stages, "configs": rows,
                    "capital_transition": {"version": "per-arm-rebasing-v1", "status": "NOT_IMPLEMENTED",
                        "journal": "same_account", "preserve_lifetime_totals": True,
                        "preserve_per_arm_loss_and_drawdown": True, "activation": "REFUSED"},
                    "runtime_acceptance": "NOT_RUN", "activation": "requires_new_helpers_and_validity_binding"}
        (scratch / "preset-manifest.json").write_bytes(canonical(manifest))
        # Strict inventory of all packet bytes except the inventory itself.
        entries = []
        for path in sorted(p for p in scratch.rglob("*") if p.is_file()):
            entries.append(sha(path.read_bytes()) + "  " + path.relative_to(scratch).as_posix())
            os.chmod(path, 0o400)
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
        (scratch / "SHA256SUMS").write_text("\n".join(entries) + "\n")
        os.chmod(scratch / "SHA256SUMS", 0o400)
        for directory in (scratch / "configs", scratch / "control", scratch):
            os.chmod(directory, 0o500)
        os.rename(scratch, output)
        return {"status": "packet_generated", "paper_lane": "B", "evidence_class": "exploratory",
                "data_class": fact["evidence_class"], "preset_set_version": preset_set, "pass_id": pass_id,
                "preset_manifest_sha256": sha((output / "preset-manifest.json").read_bytes()),
                "inventory_sha256": sha((output / "SHA256SUMS").read_bytes()), "runtime_acceptance": "NOT_RUN"}
    finally:
        if scratch.exists():
            os.chmod(scratch, 0o700)
            for path in scratch.rglob("*"):
                os.chmod(path, 0o700 if path.is_dir() else 0o600)
            shutil.rmtree(scratch)


def binding(packet, *, stage, pass_id, preset_set, manifest_sha256, inventory_sha256):
    """Return GO-binding fields, never write a GO or establish broker readiness."""
    root = Path(packet)
    if root.is_symlink() or not root.is_dir():
        raise Refused("preset_packet_directory_refused")
    if any(parent.is_symlink() for parent in root.parents):
        raise Refused("preset_packet_symlink")
    inventory = regular_bytes(root / "SHA256SUMS")
    if sha(inventory) != inventory_sha256:
        raise Refused("preset_inventory_binding_mismatch")
    listed = set()
    for line in inventory.decode("ascii").splitlines():
        if not re.fullmatch(r"[0-9a-f]{64}  [A-Za-z0-9_.\-/]+", line):
            raise Refused("preset_inventory_schema")
        expected, name = line.split("  ", 1)
        path = Path(name)
        if path.is_absolute() or any(p in (".", "..") for p in path.parts) or name in listed:
            raise Refused("preset_inventory_schema")
        listed.add(name)
        if any(parent.is_symlink() for parent in (root / path).parents):
            raise Refused("preset_packet_symlink")
        if sha(regular_bytes(root / path)) != expected:
            raise Refused("preset_packet_hash_mismatch")
    present = {p.relative_to(root).as_posix() for p in root.rglob("*") if not p.is_dir()}
    if present != listed | {"SHA256SUMS"}:
        raise Refused("preset_packet_inventory_differs")
    raw_manifest = regular_bytes(root / "preset-manifest.json")
    if sha(raw_manifest) != manifest_sha256:
        raise Refused("preset_manifest_binding_mismatch")
    manifest = json.loads(raw_manifest)
    if manifest["preset_set_version"] != preset_set or manifest["pass_id"] != pass_id:
        raise Refused("preset_pass_or_version_mismatch")
    if stage not in manifest["stage_order"]:
        raise Refused("preset_stage_not_in_pass")
    rows = [r for r in manifest["configs"] if r["stage"] == stage]
    if len(rows) != 1 or rows[0]["config_sha256"] != sha(regular_bytes(root / "configs" / (stage + ".json"))):
        raise Refused("preset_stage_config_mismatch")
    if manifest["pass_start_receipt_sha256"] != sha(regular_bytes(root / "pass-start.json")):
        raise Refused("preset_equity_fact_binding_mismatch")
    return {"paper_lane": "B", "evidence_class": "exploratory", "data_class": manifest["data_class"],
            "preset_set_version": preset_set, "pass_id": pass_id, "stage": stage,
            "preset_manifest_sha256": manifest_sha256, "inventory_sha256": inventory_sha256,
            "pass_start_receipt_sha256": manifest["pass_start_receipt_sha256"],
            "config_sha256": rows[0]["config_sha256"],
            "equity_observed_at_utc": manifest["equity_observed_at_utc"], "runtime_acceptance": "NOT_RUN"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("pass-id", "preset-set"):
        parser.add_argument("--" + argument, required=True)
    for argument in ("controls", "stages", "pass-start-receipt", "output", "check-packet", "stage",
                     "preset-manifest-sha256", "inventory-sha256"):
        parser.add_argument("--" + argument)
    parser.add_argument("--now", help="SYN test clock only; native facts require the actual clock")
    args = parser.parse_args()
    try:
        if args.check_packet:
            if any((args.controls, args.stages, args.pass_start_receipt, args.output, args.now)):
                raise Refused("ambiguous_preset_command")
            result = binding(args.check_packet, stage=args.stage, pass_id=args.pass_id,
                preset_set=args.preset_set, manifest_sha256=args.preset_manifest_sha256,
                inventory_sha256=args.inventory_sha256)
        else:
            if not all((args.controls, args.stages, args.pass_start_receipt, args.output)):
                raise Refused("missing_preset_generation_argument")
            fact = json.loads(regular_bytes(args.pass_start_receipt))
            if not isinstance(fact, dict):
                raise Refused("pass_start_fact_schema")
            if args.now and fact.get("evidence_class") != "synthetic":
                raise Refused("native_clock_override_refused")
            result = freeze(controls=args.controls, stages=args.stages.split(","), fact=fact,
                            pass_id=args.pass_id, preset_set=args.preset_set, output=args.output,
                            now=instant(args.now) if args.now else datetime.now(timezone.utc))
    except (Refused, OSError, ValueError, TypeError, KeyError):
        # No input bytes, account identifiers, filesystem paths or exception repr.
        import sys
        error = sys.exc_info()[1]
        reason = str(error) if isinstance(error, Refused) else "invalid_input_or_packet_io"
        print(json.dumps({"status": "refused", "reason": reason, "paper_lane": "B",
                          "evidence_class": "exploratory", "preset_set_version": args.preset_set,
                          "generator_version": VERSION}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
