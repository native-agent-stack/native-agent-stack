"""Run the closeout fixture with actual pinned, wrong and missing distributions."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from tests.test_gap_closeouts import GapCloseoutTests


CHILD = '''import importlib.metadata as metadata, json, sys
from copy import deepcopy
from pathlib import Path
from scripts import component_matrix as cm
from scripts.catalog_decisions import InvalidDecisionIndex
root=Path(sys.argv[1])
historical=json.loads((root/cm.GAP_CROSSWALK_FILE).read_text())
before=deepcopy(historical)
try:
    distribution=metadata.version("jsonschema")
except metadata.PackageNotFoundError:
    distribution="missing"
try:
    current=cm.current_gap_document(root,historical)
except InvalidDecisionIndex as error:
    print(json.dumps({"python":sys.version.split()[0],"jsonschema":distribution,"outcome":"refused","message":str(error),"historical_unchanged":historical==before,"document_returned":False}))
    sys.exit(3)
print(json.dumps({"python":sys.version.split()[0],"jsonschema":distribution,"outcome":"accepted","status":current["layers"][0]["gaps"][0]["status"],"open_count":cm.open_gap_counts_by_layer(current)[("us-equities","fixture")],"historical_unchanged":historical==before,"document_returned":True}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wrong-python", required=True)
    parser.add_argument("--missing-python", required=True)
    args = parser.parse_args()
    fixture = GapCloseoutTests()
    fixture.setUp()
    try:
        fixture.save()
        for label, interpreter, expected in (
                ("pinned", sys.executable, 0),
                ("wrong", args.wrong_python, 3),
                ("missing", args.missing_python, 3)):
            result = subprocess.run([interpreter, "-c", CHILD, str(fixture.root)],
                                    cwd=ROOT, capture_output=True, text=True)
            assert result.returncode == expected, (label, result.returncode, result.stderr)
            value = json.loads(result.stdout)
            assert value["historical_unchanged"]
            if expected:
                assert not value["document_returned"]
                assert "jsonschema==4.26.0" in value["message"] and "requirements-ci.txt" in value["message"]
            else:
                assert value["status"] == "settled_by_closeout" and value["open_count"] == 0
            print(json.dumps({"case": label, "exit_code": result.returncode, **value}, sort_keys=True))
        (fixture.root / fixture.path).unlink()
        result = subprocess.run([args.missing_python, "-c", CHILD, str(fixture.root)],
                                cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        value = json.loads(result.stdout)
        assert value["status"] == "open" and value["open_count"] == 1 and value["historical_unchanged"]
        print(json.dumps({"case": "no-record-missing-package", "exit_code": result.returncode, **value},
                         sort_keys=True))
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
