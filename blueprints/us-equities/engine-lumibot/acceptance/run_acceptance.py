"""Run the pinned native acceptance with a sanitized offline environment.

The retained qualification sitecustomize hook is supplied by path; do not
install, copy, modify or activate credentials. Output paths are caller-set.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from runtime_snapshot import capture, verify


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python",required=True,type=Path)
    parser.add_argument("--offline-hook",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[4]
    output=args.output
    output.mkdir(mode=0o700,parents=True,exist_ok=True)
    if output.is_symlink() or output.resolve().is_relative_to(root):
        raise SystemExit("acceptance_output_must_be_outside_worktree")
    environment={"PATH":os.defpath,"HOME":str(Path.home()),"TMPDIR":"/var/tmp",
                 "ENGINE_QUAL_EXPECTED_HOME":str(Path.home()),
                 "PYTHONPATH":str(args.offline_hook),"PYTHONDONTWRITEBYTECODE":"1",
                 "LUMIBOT_DISABLE_DOTENV":"1","LUMIBOT_DISABLE_DOTENV_LOCAL":"1",
                 "PYTHON_DOTENV_DISABLED":"1","LUMIBOT_LAZY_CREDENTIALS":"1",
                 "LUMIBOT_CONNECT_STREAM":"false","LUMIBOT_START_ORDERS_THREAD":"false",
                 "LUMIBOT_TELEMETRY":"0","ENGINE_QUAL_OFFLINE":"1",
                 "BACKTESTING_DATA_SOURCE":"none"}
    start=datetime.now(timezone.utc).isoformat()
    runtime_binding=capture(args.python,environment)
    verify(runtime_binding,runtime_binding)
    sources=[*root.joinpath("blueprints/us-equities/engine-lumibot").glob("*.py"),
             *Path(__file__).resolve().parent.glob("*.py"),
             root/"blueprints/us-equities/engine-lumibot/caps-a6-diagnostic.json",
             root/"blueprints/us-equities/engine-lumibot/write-boundaries.json",
             root/"tests/test_engine_lumibot_governor.py",root/"tests/test_engine_lumibot_native.py",
             args.offline_hook/"sitecustomize.py"]
    input_hashes=[{"role":p.name,"sha256":sha(p)} for p in sources]
    commands=[]
    for module in ("test_engine_lumibot_governor","test_engine_lumibot_native"):
        log=output/(module+".log")
        command=[str(args.python),"-B","-m","unittest","discover","-s","tests","-p",module+".py","-v"]
        with log.open("xb") as stream:
            os.chmod(log,0o600)
            result=subprocess.run(command,cwd=root,env=environment,stdout=stream,
                                  stderr=subprocess.STDOUT,check=False)
        # Raw host/interpreter metadata remains private outside the worktree;
        # publish only the bounded check-result summary separately.
        commands.append({"command":["<ISOLATED_PYTHON>",*command[1:]],
                         "exit_code":result.returncode,
                         "raw_output":{"role":module+"_private_log","sha256":sha(log)}})
    if input_hashes!=[{"role":p.name,"sha256":sha(p)} for p in sources]:
        raise SystemExit("acceptance_sources_changed_during_run")
    verify(runtime_binding,capture(args.python,environment))
    receipt={"evidence_class":"synthetic","started_at":start,
             "finished_at":datetime.now(timezone.utc).isoformat(),
             "commands":commands,"input_hashes":input_hashes,
             "runtime_binding":runtime_binding,"runtime_environment":environment,
             "strategy_version":"stock-only-acceptance-v1-review6",
             "config_sha256":sha(root/"blueprints/us-equities/engine-lumibot/caps-a6-diagnostic.json"),
             "paper_orders":0,"designation":"none","property_seed":260413,
             "note":"Raw receipt is private; exported result must omit identity-bearing raw-log fingerprints"}
    path=output/"receipt.private.json"
    with path.open("x") as stream:
        os.chmod(path,0o600);json.dump(receipt,stream,sort_keys=True,indent=2);stream.write("\n")
    print(json.dumps({"status":"passed" if all(c["exit_code"]==0 for c in commands) else "failed",
                      "evidence_class":"synthetic","commands":len(commands)},sort_keys=True))
    return 0 if all(c["exit_code"]==0 for c in commands) else 1


if __name__=="__main__":raise SystemExit(main())
