"""Publish bounded synthetic result summaries, never raw host trace fingerprints."""
import argparse
import hashlib
import json
from pathlib import Path
import re


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
    results=[]
    for command in private["commands"]:
        role=command["raw_output"]["role"].removesuffix("_private_log")
        raw=(args.private_run/(role+".log")).read_text()
        count=re.search(r"Ran ([0-9]+) tests? in ([0-9.]+)s",raw)
        if not count or command["exit_code"]!=0 or re.search(r"\nOK\s*$",raw) is None:
            raise SystemExit("acceptance_not_passed")
        tests=re.findall(r"^(test_[A-Za-z0-9_]+) \(([^)]+)\) \.\.\. (ok|skipped[^\n]*)",raw,re.M)
        # A7's warning/log output may break the one-line result; list every
        # actual test start separately and retain the measured runner total.
        starts=re.findall(r"^(test_[A-Za-z0-9_]+) \(([^)]+)\) \.\.\.",raw,re.M)
        if len(starts)!=int(count[1]) or "skipped" in raw:
            raise SystemExit("acceptance_skipped_or_count_mismatch")
        summary={"evidence_class":"synthetic","command":command["command"],
                 "exit_code":command["exit_code"],"tests":int(count[1]),"skipped":0,
                 "wall_seconds":count[2],"test_ids":[key for _,key in starts]}
        p=output/(role+".result.json");p.write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
        results.append({"path":p.relative_to(root).as_posix(),"sha256":digest(p)})
    mutations=json.loads((args.mutations/"summary.json").read_text())
    if any(mutations[key] for key in ("survived","not_applied","invalid_runs")):
        raise SystemExit("mutation_not_closed")
    path=output/"mutation-results.json";path.write_text(json.dumps(mutations,sort_keys=True,indent=2)+"\n")
    results.append({"path":path.relative_to(root).as_posix(),"sha256":digest(path)})
    import subprocess
    probe="import sys,importlib.metadata,json;print(json.dumps({'python':sys.version.split()[0],'lumibot':importlib.metadata.version('lumibot'),'alpaca-py':importlib.metadata.version('alpaca-py')}))"
    runtime=json.loads(subprocess.check_output([str(args.runtime_python),"-B","-c",probe],text=True))
    assert runtime=={"python":"3.12.4","lumibot":"4.6.11","alpaca-py":"0.44.0"}
    # A distribution lock projection, no host paths or identities.
    probe="import importlib.metadata,json;print(json.dumps(sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions())))"
    lock=json.loads(subprocess.check_output([str(args.runtime_python),"-B","-c",probe],text=True))
    lockpath=output/"runtime-distributions.json";lockpath.write_text(json.dumps(lock,indent=2)+"\n")
    results.append({"path":lockpath.relative_to(root).as_posix(),"sha256":digest(lockpath)})
    sources=[*root.joinpath("blueprints/us-equities/engine-lumibot").glob("*.py"),
             *output.glob("*.py"),root/"blueprints/us-equities/engine-lumibot/caps-a6-diagnostic.json",
             root/"blueprints/us-equities/engine-lumibot/write-boundaries.json",
             root/"tests/test_engine_lumibot_governor.py",root/"tests/test_engine_lumibot_native.py"]
    receipt={"schema_version":1,"evidence_class":"synthetic","status":"passed",
             "started_at":private["started_at"],"finished_at":private["finished_at"],
             "lumibot_pin":"862504052407df2586122b752a645f88ce87afa1",
             "alpaca_py_pin":"cc4cb3b7ba50ae250e621983c2779047fb16bb28",
             "runtime":runtime,"runtime_distributions":len(lock),
             "spec_sha256":"8eb20e2e1f3c38a416a364a9f87fef62fcd5bdaa515bf60d78621cde7eff2dc3",
             "addendum_sha256":"cf63eb570cc65e51c24444b6d752ad73825008a0a626e210ae061005f0544805",
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
