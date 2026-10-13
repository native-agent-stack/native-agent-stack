"""Observed interpreter/distribution/source identity; no engine import or keys."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import subprocess
import sys


def observe():
    distributions = sorted((d.metadata["Name"],d.version) for d in metadata.distributions())
    sources=[]
    for package in ("lumibot","alpaca-py"):
        dist=metadata.distribution(package)
        rows=[]
        for relative in sorted(dist.files or (),key=str):
            if relative.suffix==".py":
                path=Path(dist.locate_file(relative))
                rows.append([str(relative),hashlib.sha256(path.read_bytes()).hexdigest()])
        if not rows:raise SystemExit("runtime_sources_missing")
        sources.append({"package":package,"files":len(rows),
                        "sha256":hashlib.sha256(json.dumps(rows,separators=(",",":")).encode()).hexdigest()})
    return {"runtime":{"python":sys.version.split()[0],"lumibot":metadata.version("lumibot"),
                       "alpaca-py":metadata.version("alpaca-py")},
            "interpreter_sha256":hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            "distributions":[list(row) for row in distributions],"package_sources":sources}


def capture(python,environment):
    return json.loads(subprocess.check_output([str(python),"-B",str(Path(__file__).resolve())],
                                             env=environment,text=True))


def verify(recorded,observed):
    if recorded != observed:
        raise SystemExit("acceptance_runtime_mismatch")
    if observed["runtime"] != {"python":"3.12.4","lumibot":"4.6.11","alpaca-py":"0.44.0"}:
        raise SystemExit("acceptance_runtime_pin_mismatch")


if __name__=="__main__":print(json.dumps(observe(),sort_keys=True))
