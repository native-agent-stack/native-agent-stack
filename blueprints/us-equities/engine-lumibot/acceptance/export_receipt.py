"""Publish bounded synthetic result summaries, never raw host trace fingerprints."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from runtime_snapshot import capture, verify


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-run",required=True,type=Path)
    parser.add_argument("--mutations",required=True,type=Path)
    parser.add_argument("--runtime-python",required=True,type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[4]
    output=Path(__file__).resolve().parent
    private=json.loads((args.private_run/"receipt.private.json").read_text())
    binding=capture(args.runtime_python,private["runtime_environment"])
    verify(private["runtime_binding"],binding)
    sources=[*root.joinpath("blueprints/us-equities/engine-lumibot").glob("*.py"),
             *output.glob("*.py"),root/"blueprints/us-equities/engine-lumibot/caps-a6-diagnostic.json",
             root/"blueprints/us-equities/engine-lumibot/write-boundaries.json",
             root/"tests/test_engine_lumibot_governor.py",root/"tests/test_engine_lumibot_native.py"]
    recorded={row["role"]:row["sha256"] for row in private["input_hashes"]}
    if any(recorded.get(p.name)!=digest(p) for p in sources):
        raise SystemExit("acceptance_runtime_source_mismatch")
    mutations=json.loads((args.mutations/"summary.json").read_text())
    if any(mutations[key] for key in ("survived","not_applied","invalid_runs","baseline_failures")):
        raise SystemExit("mutation_not_closed")
    if any(recorded.get(name)!=value for name,value in mutations["source_sha256"].items()):
        raise SystemExit("mutation_runtime_source_mismatch")
    if any(recorded.get(name)!=value for name,value in mutations["check_source_sha256"].items()):
        raise SystemExit("mutation_runtime_check_mismatch")
    results=[]
    for command in private["commands"]:
        role=command["raw_output"]["role"].removesuffix("_private_log")
        raw=(args.private_run/(role+".log")).read_text()
        if digest(args.private_run/(role+".log"))!=command["raw_output"]["sha256"]:
            raise SystemExit("acceptance_log_mismatch")
        count=re.search(r"Ran ([0-9]+) tests? in ([0-9.]+)s",raw)
        if not count or command["exit_code"]!=0 or re.search(r"\nOK\s*$",raw) is None:
            raise SystemExit("acceptance_not_passed")
        tests=re.findall(r"^(test_[A-Za-z0-9_]+) \(([^)]+)\) \.\.\. (ok|skipped[^\n]*)",raw,re.M)
        # A7's warning/log output may break the one-line result; list every
        # actual test start separately and retain the measured runner total.
        starts=re.findall(r"^(test_[A-Za-z0-9_]+) \(([^)]+)\)(?: \.\.\.|$)",raw,re.M)
        if len(starts)!=int(count[1]) or "skipped" in raw:
            raise SystemExit("acceptance_skipped_or_count_mismatch")
        summary={"evidence_class":"synthetic","command":command["command"],
                 "exit_code":command["exit_code"],"tests":int(count[1]),"skipped":0,
                 "wall_seconds":count[2],"test_ids":[key for _,key in starts]}
        p=output/(role+".result.json");p.write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
        results.append({"path":p.relative_to(root).as_posix(),"sha256":digest(p)})
    public_mutations=dict(mutations)
    # Publish standard path/sha256 records rather than filename-keyed hashes.
    for key in ("source_sha256","check_source_sha256"):
        public_mutations[key.removesuffix("_sha256")+"_hashes"]=[
            {"path":name,"sha256":value} for name,value in public_mutations.pop(key).items()]
    path=output/"mutation-results.json";path.write_text(json.dumps(public_mutations,sort_keys=True,indent=2)+"\n")
    results.append({"path":path.relative_to(root).as_posix(),"sha256":digest(path)})
    runtime=binding["runtime"]
    # A distribution lock projection, no host paths or identities.
    lock=binding["distributions"]
    lockpath=output/"runtime-distributions.json";lockpath.write_text(json.dumps(lock,indent=2)+"\n")
    results.append({"path":lockpath.relative_to(root).as_posix(),"sha256":digest(lockpath)})
    receipt={"schema_version":1,"evidence_class":"synthetic","status":"passed",
             "started_at":private["started_at"],"finished_at":private["finished_at"],
             "lumibot_pin":"862504052407df2586122b752a645f88ce87afa1",
             "alpaca_py_pin":"cc4cb3b7ba50ae250e621983c2779047fb16bb28",
             "runtime":runtime,"runtime_distributions":len(lock),
             "runtime_interpreter_sha256":binding["interpreter_sha256"],
             "runtime_package_sources":binding["package_sources"],
             "strategy_version":private["strategy_version"],"config_sha256":private["config_sha256"],
             "spec_sha256":"8eb20e2e1f3c38a416a364a9f87fef62fcd5bdaa515bf60d78621cde7eff2dc3",
             "addendum_sha256":"cf63eb570cc65e51c24444b6d752ad73825008a0a626e210ae061005f0544805",
             "exit_policy_ruling_sha256":"6e2cb83ef947e05b0d640d344b92e8a093acc2b4cb0ca854efa94f1ed29fc582",
             "round2_read_and_exit_rulings_sha256":"cfe28395347bc7d69b993b7db35f4e9b1abcc6d18c93863d543b8d4171d437ea",
             "input_hashes":[{"path":p.relative_to(root).as_posix(),"sha256":digest(p)} for p in sources],
             "external_code_inputs":[row for row in private["input_hashes"] if row["role"]=="sitecustomize.py"],
             "outputs":results,"mutation_killed":mutations["killed"],"mutation_survived":0,
             "property_seed":260413,"property_cases":500,"paper_orders_placed":0,
             "designation":"none","raw_log_export":"withheld; bounded result summaries only",
             "note":"Pure/proxy fake SDK tests and native class construction; actual broker interaction unqualified"}
    path=output/"receipt.json";path.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":"passed","tests":sum(json.loads((root/x['path']).read_text())["tests"] for x in results if x['path'].endswith('.result.json')),
                      "mutants_killed":mutations["killed"],"runtime_distributions":len(lock)},sort_keys=True))


if __name__=="__main__":main()
