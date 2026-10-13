"""A8 exact-site mutation probes; original worktree remains byte-identical."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import re
import subprocess
import tempfile


# name, file, exact old site, replacement, focused unittest method
MUTANTS = [
 ("asset", "governor.py", 'intent.asset_type != "stock"', 'False', 'test_A2_assets_and_closed_intent'),
 ("intent", "governor.py", 'intent.side not in ("buy", "sell")', 'False', 'test_A2_assets_and_closed_intent'),
 ("session", "governor.py", 'quote.session not in self.caps["sessions"]', 'False', 'test_A2_quote_clocks_and_session'),
 ("clock_age", "governor.py", 'not 0 <= now - value <= age', 'False', 'test_A2_quote_clocks_and_session'),
 ("account", "governor.py", 'if account.reconciled is not True or (intent.side == "buy" and account.open_orders):', 'if intent.side == "buy" and account.open_orders:', 'test_A2_caps_account_and_short_refusals'),
 ("ask_band", "governor.py", 'not dec(self.caps["ask_min_usd"]) <= ask <= dec(self.caps["ask_max_usd"])', 'False', 'test_A2_caps_account_and_short_refusals'),
 ("spread", "governor.py", 'spread > dec(self.caps["max_spread_bps"])', 'False', 'test_A2_caps_account_and_short_refusals'),
 ("name_cap", "governor.py", 'len(names) >= self.caps["max_names"]', 'False', 'test_A2_caps_account_and_short_refusals'),
 ("notional", "governor.py", 'qty * price > limit', 'False', 'test_A2_caps_account_and_short_refusals'),
 ("collar", "governor.py", 'abs(price - mid) / mid * 10000 > collar', 'False', 'test_A2_collar_uses_rounded_final_price'),
 ("request_budget", "governor.py", 'len(self.requests) + units > self.caps["max_requests_per_minute"]', 'False', 'test_A2_rate_budget_request_and_submit'),
 ("submit_budget", "governor.py", 'len(self.submits) + units > self.caps["max_submits_per_minute"]', 'False', 'test_A2_rate_budget_request_and_submit'),
 ("round_buy", "governor.py", 'ROUND_FLOOR if side == "buy" else ROUND_CEILING', 'ROUND_CEILING', 'test_A4_directional_rounding_boundary_and_whole_floor'),
 ("round_sell", "governor.py", 'ROUND_FLOOR if side == "buy" else ROUND_CEILING', 'ROUND_FLOOR', 'test_A4_directional_rounding_boundary_and_whole_floor'),
 ("journal", "governor.py", 'self.journal.append(dict(event=event, caps_sha256=self.caps_hash, **fields))', 'pass', 'test_A6_journal_before_sdk_and_all_decisions_refusals'),
 ("recovery", "governor.py", 'if self.recovery_required:', 'if False:', 'test_A6_hash_chain_unknown_restart_and_no_retry'),
 ("one_use", "governor.py", 'del self.reservations[token]', 'pass', 'test_A1_payload_equals_decision_and_one_use'),
 ("api_allowlist", "guarded_api.py", 'governor.reject("api_capability")', 'return None', 'test_A2_proxy_capabilities_and_cancel_ownership'),
 ("payload_keys", "guarded_api.py", 'if set(payload) != PAYLOAD_KEYS:', 'if False:', 'test_A2_payload_refusals_exact'),
 ("type", "guarded_api.py", 'if payload["type"] != "limit":', 'if False:', 'test_A2_payload_refusals_exact'),
 ("tif", "guarded_api.py", 'if payload["time_in_force"] != "day":', 'if False:', 'test_A2_payload_refusals_exact'),
 ("side", "guarded_api.py", 'if payload["side"] not in ("buy", "sell"):', 'if False:', 'test_A2_payload_refusals_exact'),
 ("qty", "guarded_api.py", 'if not isinstance(payload["qty"], str) or not re.fullmatch(r"[1-9][0-9]*", payload["qty"]):', 'if False:', 'test_A2_payload_refusals_exact'),
 ("price", "guarded_api.py", 'if dec(payload["limit_price"]) != dec(expected["limit_price"]):', 'if False:', 'test_A2_payload_refusals_exact'),
 ("flag", "guarded_api.py", 'if payload["extended_hours"] != expected["extended_hours"]:', 'if False:', 'test_A2_payload_refusals_exact'),
 ("cancel", "guarded_api.py", 'str(args[0]) not in owned', 'False', 'test_A2_proxy_capabilities_and_cancel_ownership'),
 ("paper_config", "stock_only_alpaca.py", 'config.get("PAPER") is not True', 'False', 'test_A5_stub_constructor_no_paper_and_wrong_url'),
 ("paper_url", "stock_only_alpaca.py", 'if getattr(base, "value", base) != "https://paper-api.alpaca.markets":', 'if False:', 'test_A5_stub_constructor_no_paper_and_wrong_url'),
 ("proxy_paper", "guarded_api.py", 'if getattr(base, "value", base) != "https://paper-api.alpaca.markets":', 'if False:', 'test_A5_proxy_paper_url_and_retry_cap_independently'),
 ("retry_ceiling", "guarded_api.py", 'not 0 <= retries <= 3', 'False', 'test_A5_proxy_paper_url_and_retry_cap_independently'),
 ("reservation_expiry", "governor.py", 'if type(now) is not int or now > self.deadlines.get(token, -1):', 'if False:', 'test_A2_decision_reservation_expires_before_transport'),
 ("construction_session", "stock_only_alpaca.py", 'if session not in governor.caps["sessions"]:', 'if False:', 'test_A5_stub_constructor_no_paper_and_wrong_url'),
 ("construction_clock", "stock_only_alpaca.py", 'if type(now) is not int or type(clock_ns) is not int or not 0 <= now-clock_ns <= 250_000_000:', 'if False:', 'test_A5_stub_constructor_no_paper_and_wrong_url'),
 ("fsync", "governor.py", 'os.fsync(self.fd)', 'pass', 'test_A6_journal_before_sdk_and_all_decisions_refusals'),
 ("caps_chain", "governor.py", 'if row.get("caps_sha256") != self.caps_hash:', 'if False:', 'test_A6_restart_caps_binding_and_budget_not_reset'),
 ("caps_bool", "governor.py", 'or any(type(value) is not bool for value in c["sessions"].values())', '', 'test_A5_caps_and_journal_fail_closed'),
]
# After the exit correction, the final buy-notional refusal is redundant
# with floor(limit/price); do not relabel an equivalent survivor as a kill.
MUTANTS = [row for row in MUTANTS if row[0] != "notional"]
MUTANTS += [
 ("dec_type", "governor.py", 'if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):', 'if False:', 'test_R4_dec_refuses_float_bool_none_text_and_non_finite'),
 ("dec_finite", "governor.py", 'if not result.is_finite():', 'if False:', 'test_R4_dec_refuses_float_bool_none_text_and_non_finite'),
 ("journal_mode", "governor.py", 'if os.fstat(self.fd).st_mode & 0o077:', 'if False:', 'test_R5_journal_group_world_permissions_refuse'),
 ("journal_write", "governor.py", 'raise GuardRefusal("journal_write") from None', 'pass', 'test_R1_journal_write_failure_refuses_and_nothing_is_admitted'),
 ("pending_outcome", "governor.py", 'if self.outstanding:', 'if False:', 'test_R2_second_decision_waits_for_the_first_outcome_to_be_reconciled'),
 ("reconcile", "governor.py", 'self.reject("reconciliation_required")', 'pass', 'test_R3_reconcile_needs_terminal_reconciled_account_and_known_order'),
 ("flag_bool", "guarded_api.py", 'if type(payload["extended_hours"]) is not bool:', 'if False:', 'test_R8_session_flag_is_actual_bool'),
 ("cancel_unknown", "guarded_api.py", 'raise GuardRefusal("unknown_outcome") from None\n                    governor.record("cancel",', 'pass\n                    governor.record("cancel",', 'test_R7_failed_cancel_unknown_outcome_blocks_admission'),
 ("inbox_symlink", "stock_only_alpaca.py", 'if path.is_symlink():', 'if False:', 'test_R11_symlinked_inbox_refused'),
 ("environment", "stock_only_alpaca.py", 'if any(os.environ.get(key) != value for key, value in required.items()):', 'if False:', 'test_R12_nonhermetic_environment_refused'),
 ("payload_pair", "governor.py", 'if expected is None or payload != expected:', 'if expected is None:', 'test_A2_payload_refusals_exact'),
 ("payload_serializer", "guarded_api.py", 'safe_order = ReservedOrderData(payload)', 'safe_order = type(order)(**payload)', 'test_R10_sdk_serialization_cannot_add_foreign_class_fields'),
]
EXTRA_SITES = {"payload_pair":[("guarded_api.py",'if payload != expected:', 'if False:')]}
MUTANTS += [
 ("reserved_values", "guarded_api.py", 'payload = dict(expected)', 'pass', 'test_R13_str_subclass_values_never_reach_the_sdk_or_the_journal'),
 ("reserved_token", "guarded_api.py", 'token = payload["client_order_id"]      # the reservation\'s key', 'pass      # the reservation\'s key', 'test_R13_str_subclass_values_never_reach_the_sdk_or_the_journal'),
 ("exit_trade_age", "governor.py", 'if intent.side == "buy":      # CC ruling', 'if True:      # CC ruling', 'test_E5_an_exit_needs_a_fresh_quote_not_a_recent_trade'),
 ("exit_quote_deadline", "governor.py", 'quote_deadline if intent.side == "sell" else min(', 'min(', 'test_E5b_an_exits_reservation_deadline_comes_from_the_quote'),
 ("exit_equity", "governor.py", '(intent.side == "buy" and equity <= 0)', '(equity <= 0)', 'test_E4b_exit_does_not_depend_on_account_equity_in_any_session'),
 ("entry_equity", "governor.py", '(intent.side == "buy" and equity <= 0)', 'False', 'test_E4b_exit_does_not_depend_on_account_equity_in_any_session'),
 ("exit_own_quantity", "governor.py", 'held = positions if intent.side == "buy" else {intent.symbol: positions.get(intent.symbol, D(0))}', 'held = positions', 'test_E6_an_exit_needs_an_integral_quantity_only_for_its_own_symbol'),
 ("restart_orders_unreadable", "guarded_api.py", 'listed = real_client.get_orders()\n                except Exception:\n                    governor.reject("restart_orders_unreadable")', 'listed = real_client.get_orders()\n                except Exception:\n                    pass', 'test_E7b_an_unreadable_order_list_after_a_restart_fails_closed'),
 ("is_ours_prefix", "governor.py", 'cid.startswith(CLIENT_ID_PREFIX)', 'True', 'test_E7c_open_order_ownership_requires_both_prefix_and_journal_submission'),
 ("is_ours_submission", "governor.py", 'cid in self.submitted', 'True', 'test_E7c_open_order_ownership_requires_both_prefix_and_journal_submission'),
 ("owned_prefix", "guarded_api.py", 'isinstance(cid, str) and cid.startswith(CLIENT_ID_PREFIX) and cid in submitted', 'isinstance(cid, str) and cid in submitted', 'test_E7c_open_order_ownership_requires_both_prefix_and_journal_submission'),
 ("owned_submission", "guarded_api.py", 'cid in submitted', 'True', 'test_E7c_open_order_ownership_requires_both_prefix_and_journal_submission'),
 ("restored_submissions", "governor.py", 'self.submitted.add(key)', 'pass', 'test_E7_after_a_restart_the_old_working_order_can_be_cancelled_and_the_exit_proceeds'),
 ("current_submissions", "governor.py", 'self.submitted.add(token)', 'pass', 'test_E7c_open_order_ownership_requires_both_prefix_and_journal_submission'),
 ("cancel_terminal_recovery", "guarded_api.py", 'if owned.get(str(args[0])) in governor.outstanding:', 'if True:', 'test_E8_a_failed_cancel_wedges_the_arm_only_while_its_order_is_outstanding'),
 ("cancel_outstanding_recovery", "guarded_api.py", 'if owned.get(str(args[0])) in governor.outstanding:', 'if False:', 'test_E8_a_failed_cancel_wedges_the_arm_only_while_its_order_is_outstanding'),
 ("unknown_orders_entry", "governor.py", '(intent.side == "buy" and account.open_orders)', 'False', 'test_E7_after_a_restart_the_old_working_order_can_be_cancelled_and_the_exit_proceeds'),
 ("unknown_orders_reconcile", "governor.py", 'any(self.is_ours(entry) for entry in account.open_orders)', 'bool(account.open_orders)', 'test_E7_after_a_restart_the_old_working_order_can_be_cancelled_and_the_exit_proceeds'),
]
OVERRIDE_NAMES = ("LUMIBOT_STRATEGY_PARAMETERS", "BACKTESTING_PARAMETERS", "LUMIWEALTH_API_KEY",
                  "DISCORD_WEBHOOK_URL", "LISTENER_WRITE_URL")
override_tuple = '(' + ', '.join('"'+name+'"' for name in OVERRIDE_NAMES) + ')'
MUTANTS += [("override_"+name.lower(), "stock_only_alpaca.py", override_tuple,
             '(' + ', '.join('"'+other+'"' for other in OVERRIDE_NAMES if other != name) + ')',
             'test_R14_environment_overrides_of_the_real_constructor_refuse') for name in OVERRIDE_NAMES]
MUTANTS += [
 ("journal_latch_set", "governor.py", 'self.unusable = True', 'pass', 'test_J1_journal_failure_latches_and_prevents_later_submit'),
 ("journal_latch_check", "governor.py", 'if self.unusable:', 'if False:', 'test_J1_journal_failure_latches_and_prevents_later_submit'),
 ("consume_monotonic", "governor.py", 'def consume(self, payload, token, now):\n        self._time(now)', 'def consume(self, payload, token, now):\n        pass', 'test_J2_consume_refuses_clock_rollback_before_sdk'),
 ("restore_direct_coverage", "guarded_api.py", 'sorted(submitted.intersection(governor.outstanding)-set(owned.values()))', '[]', 'test_J3_restart_finds_owned_order_beyond_default_page'),
 ("restore_direct_identity", "guarded_api.py", 'if actual != cid or not cid.startswith(CLIENT_ID_PREFIX) or oid is None:', 'if False:', 'test_J4_restart_direct_lookup_fails_closed'),
 ("restore_direct_failure", "guarded_api.py", 'item = real_client.get_order_by_client_id(cid)\n                    except Exception:\n                        governor.reject("restart_orders_unreadable")', 'item = real_client.get_order_by_client_id(cid)\n                    except Exception:\n                        pass', 'test_J4_restart_direct_lookup_fails_closed'),
 ("runtime_export_binding", "acceptance/export_receipt.py", 'verify(private["runtime_binding"],binding)', 'pass', 'test_J5_export_refuses_a_different_acceptance_runtime'),
 ("runtime_identity", "acceptance/runtime_snapshot.py", 'if recorded != observed:', 'if False:', 'test_J5_export_refuses_a_different_acceptance_runtime'),
 ("runtime_pin", "acceptance/runtime_snapshot.py", 'if observed["runtime"] != {"python":"3.12.4","lumibot":"4.6.11","alpaca-py":"0.44.0"}:', 'if False:', 'test_J6_runtime_pins_and_package_sources_are_required'),
 ("runtime_sources", "acceptance/runtime_snapshot.py", 'if not rows:raise SystemExit("runtime_sources_missing")', 'pass', 'test_J6_runtime_pins_and_package_sources_are_required'),
]
MUTANTS += [("seam_"+name,"stock_only_alpaca.py",name+" = _deny",
             name+" = lambda self, *a, **k: None","test_A2_each_committed_seam_override_independently")
            for name in ("_submit_orders","_submit_multileg_order","_modify_order",
                         "sell_all","close_position","close_positions")]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python",required=True)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[4]
    code=root/"blueprints/us-equities/engine-lumibot"
    tests=root/"tests"
    args.output.mkdir(parents=True,exist_ok=True,mode=0o700)
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in code.glob("*.py")}
    check_sources=[Path(__file__).resolve(),tests/"test_engine_lumibot_governor.py",
                   tests/"test_engine_lumibot_native.py",code/"acceptance/export_receipt.py",
                   code/"acceptance/runtime_snapshot.py",code/"acceptance/run_acceptance.py"]
    check_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in check_sources}
    results=[]
    for name, file, old, new, test in MUTANTS:
        module = ("test_engine_lumibot_governor.ReviewRecovery" if test.startswith("test_J")
                  else "test_engine_lumibot_governor.ExitPolicyMatrix" if test.startswith("test_E4b")
                  else "test_engine_lumibot_governor.RestageAdditions" if test.startswith(("test_R13", "test_R14", "test_E"))
                  else "test_engine_lumibot_governor.ReviewerAdditions" if test.startswith("test_R")
                  else "test_engine_lumibot_native.SeamCI" if file=="stock_only_alpaca.py"
                  else "test_engine_lumibot_governor.CoreCase")
        command=[args.python,"-B","-m","unittest",module+"."+test,"-q"]
        baseline_env=dict(os.environ,ENGINE_LUMIBOT_ROOT=str(code),PYTHONDONTWRITEBYTECODE="1",TMPDIR="/var/tmp")
        baseline=subprocess.run(command,cwd=tests,env=baseline_env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=False)
        ran_baseline = re.search(rb"Ran 1 test\b",baseline.stdout) is not None
        if baseline.returncode or not ran_baseline:
            results.append({"name":name,"status":"BASELINE_FAILED","exit_code":baseline.returncode,"test":module+"."+test})
            continue
        with tempfile.TemporaryDirectory(prefix="lumibot-mutant-",dir="/var/tmp") as temporary:
            scratch_root=Path(temporary)/"repo"
            target=scratch_root/"blueprints/us-equities/engine-lumibot";shutil.copytree(code,target)
            (scratch_root/"tests").mkdir()
            for filename in ("test_engine_lumibot_governor.py","test_engine_lumibot_native.py"):
                shutil.copyfile(tests/filename,scratch_root/"tests"/filename)
            source=(target/file).read_text()
            if source.count(old)!=1:
                results.append({"name":name,"status":"NOT_APPLIED","site_count":source.count(old)})
                continue
            (target/file).write_text(source.replace(old,new,1))
            for extra_file,old_extra,new_extra in EXTRA_SITES.get(name,[]):
                content=(target/extra_file).read_text()
                if content.count(old_extra)!=1:raise RuntimeError("paired_site_not_unique")
                (target/extra_file).write_text(content.replace(old_extra,new_extra,1))
            environment=dict(os.environ,ENGINE_LUMIBOT_ROOT=str(target),PYTHONDONTWRITEBYTECODE="1",TMPDIR="/var/tmp")
            result=subprocess.run(command,cwd=tests,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=False)
            log=args.output/(name+".private.log");log.write_bytes(result.stdout);os.chmod(log,0o600)
            ran = re.search(rb"Ran 1 test\b",result.stdout) is not None
            asserted = b"AssertionError" in result.stdout and (module+"."+test).encode() in result.stdout
            status = "KILLED" if result.returncode and ran and asserted else "SURVIVED" if not result.returncode and ran else "INVALID_RUN"
            results.append({"name":name,"status":status,"baseline_exit_code":0,
                            "matching_assertion_failed":asserted,"exit_code":result.returncode,"test":module+"."+test})
    after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in code.glob("*.py")}
    assert before==after
    assert check_hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in check_sources}
    summary={"evidence_class":"synthetic","source_unchanged":True,"source_sha256":before,
             "check_source_sha256":check_hashes,
             "coverage":"listed exact-site probes and one layered payload-equality pair; not an exhaustive every-refusal census",
             "mutants":results,
             "killed":sum(x["status"]=="KILLED" for x in results),
             "survived":sum(x["status"]=="SURVIVED" for x in results),
             "not_applied":sum(x["status"]=="NOT_APPLIED" for x in results)}
    summary["invalid_runs"] = sum(x["status"]=="INVALID_RUN" for x in results)
    summary["baseline_failures"] = sum(x["status"]=="BASELINE_FAILED" for x in results)
    (args.output/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
    print(json.dumps({k:summary[k] for k in ("killed","survived","not_applied","source_unchanged")},sort_keys=True))
    return int(any(summary[key] for key in ("survived","not_applied","invalid_runs","baseline_failures")))


if __name__=="__main__":raise SystemExit(main())
