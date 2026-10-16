"""Check downloaded bytes against the captured vendor release-API asset digest.

This is a local integrity check over native inputs, not an upstream test suite
or signature verification. Both actual and published values are computed/read
at execution time; a mismatch fails after printing the two public values.
"""

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-json", type=Path, required=True)
    parser.add_argument("--asset", type=Path, required=True)
    args = parser.parse_args()
    release = json.loads(args.release_json.read_text())
    asset = next(row for row in release["assets"] if row["name"] == args.asset.name)
    published = asset["digest"]
    if not isinstance(published, str) or not published.startswith("sha256:"):
        raise ValueError("Publisher did not supply a SHA-256 asset digest")
    actual = hashlib.sha256(args.asset.read_bytes()).hexdigest()
    expected = published.removeprefix("sha256:")
    print("published_sha256=" + expected)
    print("actual_sha256=" + actual)
    print("actual_equals_published=" + str(actual == expected).lower())
    return 0 if actual == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
