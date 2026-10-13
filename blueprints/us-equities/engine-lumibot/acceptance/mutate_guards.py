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
 ("account", "governor.py", 'if account.reconciled is not True or account.open_orders:', 'if account.open_orders:', 'test_A2_caps_account_and_short_refusals'),
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
                   tests/"test_engine_lumibot_native.py"]
    check_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in check_sources}
    results=[]
    for name, file, old, new, test in MUTANTS:
        module = ("test_engine_lumibot_governor.ReviewerAdditions" if test.startswith("test_R")
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
            target=Path(temporary)/"code";shutil.copytree(code,target)
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
