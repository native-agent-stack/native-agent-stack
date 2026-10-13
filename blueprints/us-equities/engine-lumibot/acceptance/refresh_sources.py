"""Derive public upstream source hashes, verifying mirror and installed bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lumibot-mirror",required=True,type=Path)
    parser.add_argument("--installed-lumibot",required=True,type=Path)
    parser.add_argument("--installed-alpaca",required=True,type=Path)
    parser.add_argument("--alpaca-mirror",required=True,type=Path)
    args=parser.parse_args()
    pin="862504052407df2586122b752a645f88ce87afa1"
    head=subprocess.check_output(["git","-C",str(args.lumibot_mirror),"rev-parse","HEAD"],text=True).strip()
    if head!=pin:raise SystemExit("lumibot_pin_refused")
    files=[]
    for name in ["brokers/alpaca.py","brokers/broker.py","entities/order.py","entities/position.py",
                 "strategies/strategy.py","strategies/_strategy.py","strategies/strategy_executor.py",
                 "components/agents/manager.py","credentials.py"]:
        raw=subprocess.check_output(["git","-C",str(args.lumibot_mirror),"show",pin+":lumibot/"+name])
        if raw!=(args.installed_lumibot/name).read_bytes():raise SystemExit("installed_source_refused")
        files.append({"repository":"Lumiwealth/lumibot","pin":pin,"path":"lumibot/"+name,
                      "bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})
    for name in ["trading/client.py","common/rest.py"]:
        raw=(args.installed_alpaca/name).read_bytes()
        original=subprocess.check_output(["git","-C",str(args.alpaca_mirror),"show",
                                          "cc4cb3b7ba50ae250e621983c2779047fb16bb28:alpaca/"+name])
        if raw!=original:raise SystemExit("alpaca_installed_source_refused")
        files.append({"repository":"alpacahq/alpaca-py","pin":"cc4cb3b7ba50ae250e621983c2779047fb16bb28",
                      "path":"alpaca/"+name,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
                      "basis":"installed0.44.0 equals pinned Git object; package version independently checked"})
    output=Path(__file__).resolve().parent/"upstream-sources.json"
    output.write_text(json.dumps({"schema_version":1,"evidence_class":"source_review",
                                 "lumibot_installed_equals_git":True,"files":files},sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":"passed","source_files":len(files)}))


if __name__=="__main__":main()
