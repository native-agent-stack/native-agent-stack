"""Bounded guard deletion audit, SYN tests and in-memory mutant modules only.

Adapted technique: trading-cc mutate_1042.py census described in the PR read.
Every result records source digest, guard and the exact negative test that died.
No source file, deployment state, credential or installed unit is edited.
"""
import argparse
import ast
import copy
import hashlib
import importlib
import io
import json
from pathlib import Path
import sys
import time
import types
import unittest
import signal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--mode", choices=["guards", "operands", "calls", "group", "flat"], default="guards")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    path = root / "blueprints/us-equities/adaptive-paper/paper_deployment.py"
    sys.path.insert(0, str(path.parent))
    import paper_deployment
    import tests.test_paper_deployment_guards as guards
    import tests.test_paper_deployment as lifecycle
    source = path.read_bytes()
    tree = ast.parse(source)
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.If) and not n.orelse and n.body
             and isinstance(n.body[-1], ast.Raise) and isinstance(n.body[-1].exc, ast.Call)
             and isinstance(n.body[-1].exc.func, ast.Name) and n.body[-1].exc.func.id == "Refused"]
    nodes.sort(key=lambda n: n.lineno)
    mutations = [(n, "guard", None) for n in nodes]
    if args.mode == "operands":
        mutations = []
        for n in nodes:
            for boolean in ast.walk(n.test):
                if isinstance(boolean, ast.BoolOp):
                    for index in range(len(boolean.values)):
                        mutations.append((n, "operand", (boolean.lineno, boolean.col_offset, index)))
    elif args.mode == "calls":
        protected = {"lane_a_absent", "verify", "namespace_ready", "availability", "validate_availability", "validate_sizing_and_scope"}
        mutations = [(n, "call", None) for n in ast.walk(tree) if isinstance(n, ast.Expr)
                     and isinstance(n.value, ast.Call)
                     and (getattr(n.value.func, "id", None) or getattr(n.value.func, "attr", None)) in protected]
        mutations += [(n, "lock", None) for n in ast.walk(tree) if isinstance(n, ast.With)
                      and any(isinstance(item.context_expr, ast.Call) and isinstance(item.context_expr.func, ast.Name)
                              and item.context_expr.func.id in {"exclusive", "account_writer"} for item in n.items)]
        mutations.sort(key=lambda item: item[0].lineno)
    elif args.mode == "group":
        mutations = [(nodes[0], "group", None)]
    elif args.mode == "flat":
        mutations = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "flat" for t in n.targets):
                mutations.append((n, "flat", None))
                for boolean in ast.walk(n.value):
                    if isinstance(boolean, ast.BoolOp):
                        for index in range(len(boolean.values)):
                            mutations.append((n, "flat_operand", (boolean.lineno, boolean.col_offset, index)))
    results = []
    mapping = {
        "safe_path": ["test_symlinked_exploratory_root_and_descendant_never_write_protected_target", "test_identifiers_stage_lists_and_roots_are_not_word_checks"],
        "bundle_destination": ["test_cut_destination_and_source_archive_refusals"],
        "read_bytes": ["test_private_file_size_and_growth_guards"],
        "read_private_json": ["test_private_file_size_and_growth_guards"],
        "seal_inventory": ["test_seal_includes_nested_checksum_files_and_rejects_symlinks"],
        "identifier": ["test_identifiers_stage_lists_and_roots_are_not_word_checks"],
        "trial_identifier": ["test_identifiers_stage_lists_and_roots_are_not_word_checks"],
        "exclusive": ["test_writer_contention_owner_and_replaced_inode", "test_recovery_lock_wait_is_bounded_and_can_finish_after_release"],
        "lane_a_absent": ["test_lane_a_native_inventory_and_process_guards"],
        "native_flat_observation": ["test_native_partial_flat_quote_and_clock_preflight_guards"],
        "verify_managed_runtime": ["test_managed_runtime_owner_markers_and_metadata_are_fixed_inputs"],
        "validate_sizing_and_scope": ["test_custom_pre_and_renamed_mover_rungs_are_refused", "test_session_kind_and_headroom_are_independent_guards"],
        "systemd_path": ["test_identifiers_stage_lists_and_roots_are_not_word_checks"],
        "build": ["test_identifiers_stage_lists_and_roots_are_not_word_checks", "test_custom_pre_and_renamed_mover_rungs_are_refused", "test_t22_builder_inputs_and_absent_native_capability_fail_closed", "test_manifest_inventory_label_engine_session_and_runtime_are_required"],
        "cut": ["test_cut_destination_and_source_archive_refusals"],
        "__init__": ["test_manifest_inventory_label_engine_session_and_runtime_are_required", "test_identifiers_stage_lists_and_roots_are_not_word_checks", "test_symlinked_exploratory_root_and_descendant_never_write_protected_target"],
        "stage": ["test_manifest_inventory_label_engine_session_and_runtime_are_required"],
        "config_path": ["test_config_path_escape_label_and_budget_fields_are_required", "test_bundle_config_and_state_namespace_guards"],
        "config": ["test_config_path_escape_label_and_budget_fields_are_required"],
        "verify": ["test_bundle_config_and_state_namespace_guards", "test_verify_source_inventory_label_and_native_effective_digest",
                   "test_verify_t22_capability_and_engine_kind_cannot_fall_back",
                   "test_config_path_escape_label_and_budget_fields_are_required", "test_manifest_inventory_label_engine_session_and_runtime_are_required"],
        "namespace_ready": ["test_account_last_drain_and_sql_authoritative_namespace_guards",
                            "test_old_native_state_cannot_rotate_config_before_go", "test_changed_native_account_refuses_before_namespace_or_engine_dispatch"],
        "sequence_next": ["test_two_real_passes_reject_older_flat_predecessor_and_repeated_successor", "test_sequence_cursor_rejects_older_real_pass_handoff_and_second_successor", "test_initial_sequence_stage_and_completed_pass_id_are_required"],
        "account_window": ["test_account_last_drain_and_sql_authoritative_namespace_guards"],
        "observe": ["test_observe_used_pending_partial_and_exhausted_budget_refuse",
                    "test_observe_account_change_and_active_or_stop_never_writes_ready", "test_native_observation_is_fresh_flat_budgeted_and_never_exposes_account"],
        "budget": ["test_observe_used_pending_partial_and_exhausted_budget_refuse"],
        "scan_snapshot": ["test_each_scan_commitment_config_clock_rank_and_retained_hash_is_required", "test_scan_source_cutoff_cannot_be_restamped_or_rank_prefix_changed"],
        "publish_scan": ["test_producer_replacement_never_changes_committed_trial_bytes", "test_scan_visibility_active_pending_collision_and_ready_are_guarded"],
        "scan_binding": ["test_producer_replacement_never_changes_committed_trial_bytes", "test_scan_visibility_active_pending_collision_and_ready_are_guarded"],
        "session": ["test_session_kind_and_headroom_are_independent_guards"],
        "readiness": ["test_each_readiness_binding_field_is_required", "test_readiness_account_and_each_flatness_field_is_required", "test_readiness_missing_stale_and_future_are_specific"],
        "previous": ["test_each_previous_handoff_native_proof_config_and_drain_field_is_required"],
        "issue": ["test_issue_stop_hold_and_active_are_each_required", "test_issue_requires_lane_a_check", "test_go_pending_used_and_consumed_sequence_are_not_reusable"],
        "native_call": ["test_private_capability_fields_token_age_and_go_single_use"],
        "consume_capability": ["test_private_capability_fields_token_age_and_go_single_use", "test_public_native_command_requires_consumed_go_capability"],
        "check_account": ["test_changed_native_account_refuses_before_namespace_or_engine_dispatch"],
        "run_bound": ["test_each_go_binding_field_and_expiry_blocks_dispatch", "test_run_stop_hold_active_and_ready_hash_block_dispatch", "test_go_pending_used_and_consumed_sequence_are_not_reusable", "test_run_hash_sequence_handoff_scan_and_consumed_token_are_required"],
        "recover": ["test_recover_each_flat_proof_operand_and_foreign_stop", "test_no_output_recover_is_unknown_and_never_becomes_flat_completion", "test_recover_config_and_sequence_binding_precede_native_and_stop_clear"],
        "before": ["test_flat_child_budget_refuses_before_transport"],
    }
    for owner in ["issue", "run_bound", "observe", "publish_scan", "recover"]:
        mapping[owner].append("test_issue_run_observe_scan_and_recover_require_writer_context")
        mapping[owner].append("test_admission_calls_integrity_lane_a_and_selected_availability")
    for owner in ["observe", "check_account"]:
        mapping[owner].append("test_observe_and_native_account_checks_take_account_mutex_and_namespace")
    mapping["availability"] = ["test_expired_t22_packet_does_not_block_other_stage_or_recovery"]
    mapping["native_child"] = ["test_flat_child_budget_refuses_before_transport", "test_flat_child_every_native_flatness_operand_is_required"]
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    def selected_suite(names):
        suite = unittest.TestSuite()
        for name in names:
            case = guards.Guards if hasattr(guards.Guards, name) else lifecycle.DeploymentContract
            if not hasattr(case, name):
                raise RuntimeError("unknown_census_test:" + name)
            suite.addTest(case(name))
        return suite
    # A failing unmodified baseline must never count as a killed mutant.
    baseline_names = sorted({name for names in mapping.values() for name in names})
    baseline_stream = io.StringIO()
    baseline = unittest.TextTestRunner(stream=baseline_stream, verbosity=0).run(selected_suite(baseline_names))
    if not baseline.wasSuccessful():
        print(baseline_stream.getvalue())
        return 2
    for node, mutation_kind, detail in mutations[args.start:args.start + args.count]:
        mutated = copy.deepcopy(tree)
        if mutation_kind in {"guard", "operand"}:
            target = next(n for n in ast.walk(mutated) if isinstance(n, ast.If) and n.lineno == node.lineno)
            if mutation_kind == "guard": target.test = ast.Constant(False)
            else:
                boolean = next(n for n in ast.walk(target.test) if isinstance(n, ast.BoolOp)
                               and (n.lineno, n.col_offset) == detail[:2])
                boolean.values[detail[2]] = ast.Constant(isinstance(boolean.op, ast.And))
        elif mutation_kind in {"flat", "flat_operand"}:
            target = next(n for n in ast.walk(mutated) if isinstance(n, ast.Assign) and n.lineno == node.lineno)
            if mutation_kind == "flat": target.value = ast.Constant(True)
            else:
                boolean = next(n for n in ast.walk(target.value) if isinstance(n, ast.BoolOp)
                               and (n.lineno, n.col_offset) == detail[:2])
                boolean.values[detail[2]] = ast.Constant(isinstance(boolean.op, ast.And))
        elif mutation_kind == "group":
            for n in ast.walk(mutated):
                if isinstance(n, ast.If) and n.lineno in {g.lineno for g in nodes}: n.test = ast.Constant(False)
        else:
            class Delete(ast.NodeTransformer):
                def visit_Expr(self, n):
                    return ast.copy_location(ast.Pass(), n) if mutation_kind == "call" and n.lineno == node.lineno else self.generic_visit(n)
                def visit_With(self, n):
                    return n.body if mutation_kind == "lock" and n.lineno == node.lineno else self.generic_visit(n)
            mutated = Delete().visit(mutated)
        ast.fix_missing_locations(mutated)
        module = types.ModuleType("paper_deployment")
        module.__file__ = str(path)
        exec(compile(mutated, str(path), "exec"), module.__dict__)
        original = sys.modules["paper_deployment"]
        sys.modules["paper_deployment"] = module
        guards.d = module
        owner = min((f for f in functions if f.lineno <= node.lineno <= f.end_lineno),
                    key=lambda f: f.end_lineno - f.lineno).name
        names = (["test_issue_stop_hold_and_active_are_each_required", "test_each_go_binding_field_and_expiry_blocks_dispatch",
                  "test_private_capability_fields_token_age_and_go_single_use", "test_session_kind_and_headroom_are_independent_guards",
                  "test_recover_each_flat_proof_operand_and_foreign_stop"] if mutation_kind == "group" else mapping.get(owner, []))
        guard = ast.unparse(node.body[-1].exc) if isinstance(node, ast.If) else ast.unparse(node).splitlines()[0]
        if not names:
            results.append({"line": node.lineno, "guard": guard,
                            "function": owner, "status": "UNMAPPED", "failing_tests": []})
            sys.modules["paper_deployment"] = original
            guards.d = original
            continue
        suite = selected_suite(names)
        stream = io.StringIO()
        started = time.monotonic()
        try:
            def expired(*_):
                raise TimeoutError("bounded_guard_mutant")
            prior_handler = signal.signal(signal.SIGALRM, expired)
            signal.alarm(30)
            run = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, prior_handler)
            sys.modules["paper_deployment"] = original
            guards.d = original
        failing = [str(test) for test, _ in run.failures + run.errors]
        results.append({"line": node.lineno, "guard": guard, "mutation": mutation_kind, "operand": detail,
                        "function": owner, "selected_tests": names,
                        "status": "KILLED" if not run.wasSuccessful() else "SURVIVED",
                        "failing_tests": failing, "tests": run.testsRun,
                        "seconds": round(time.monotonic() - started, 3)})
        print(json.dumps(results[-1]), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"source_sha256": hashlib.sha256(source).hexdigest(),
        "baseline_tests": baseline.testsRun, "baseline_passed": True,
        "guard_count": len(nodes), "mutation_count": len(mutations), "mode": args.mode, "start": args.start, "count": len(results),
        "results": results}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
