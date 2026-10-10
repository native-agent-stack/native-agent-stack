#!/usr/bin/env python3
"""Compare installed supported SDK source to the exact catalogued upstream pin."""
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path
import subprocess

from alpaca.common.rest import RESTClient
from alpaca.data.models.corporate_actions import CashDividend


PIN = "cc4cb3b7ba50ae250e621983c2779047fb16bb28"


def main():
    mirror = Path.home() / "code/upstream/alpacahq/alpaca-py"
    observations = []
    for cls, path in [(RESTClient, "alpaca/common/rest.py"), (CashDividend, "alpaca/data/models/corporate_actions.py")]:
        source = subprocess.run(["git", "-C", str(mirror), "show", PIN + ":" + path],
                                capture_output=True, check=True).stdout
        installed = Path(inspect.getfile(cls)).read_bytes()
        observations.append({"file": path, "upstream_sha256": hashlib.sha256(source).hexdigest(),
                             "installed_sha256": hashlib.sha256(installed).hexdigest(),
                             "same_bytes": source == installed})
    print(json.dumps({"repository": "https://github.com/alpacahq/alpaca-py", "source_pin": PIN,
                      "version": importlib.metadata.version("alpaca-py"), "sources": observations,
                      "cash_dividend_fields": sorted(CashDividend.model_fields),
                      "currency_field_present": "currency" in CashDividend.model_fields,
                      "source_binding": "exact catalog source commit; no local tag ref is assumed"}, indent=2))
    return 0 if all(x["same_bytes"] for x in observations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
