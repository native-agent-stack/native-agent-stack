#!/usr/bin/env python3
"""Check archive identity and capture ordering independently of byte reproduction.

Sources: Python 3.13 hashlib.sha256 and datetime.fromisoformat, official docs
read 2026-10-16; public vendor release digests are in native captures C01-C03.
This check compares those independent expected digests with native sha256sum
output. It never treats an exit-zero checksum command as a successful match.
https://docs.python.org/3.13/library/hashlib.html
https://docs.python.org/3.13/library/datetime.html#datetime.datetime.fromisoformat
"""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re


ARCHIVES = (
    ("01-collector-release", "04-download-collector", "otelcol-contrib_0.162.0_linux_amd64.tar.gz"),
    ("02-prometheus-release", "05-download-prometheus", "prometheus-3.15.0.linux-amd64.tar.gz"),
    ("03-loki-release", "06-download-loki", "loki-linux-amd64.zip"),
)


def capture(directory, identity):
    metadata = json.loads((directory / (identity + ".json")).read_text())
    streams = {}
    for name in ("stdout", "stderr"):
        info = metadata["streams"][name]
        data = (directory / info["path"]).read_bytes()
        if len(data) != info["bytes"] or hashlib.sha256(data).hexdigest() != info["sha256"]:
            raise ValueError("published capture bytes do not match envelope")
        streams[name] = data
    return metadata, streams


def verify_archives(directory, checksum_id):
    metadata, streams = capture(Path(directory), checksum_id)
    problems = []
    if metadata["exit_code"] != 0 or metadata["timed_out"]:
        problems.append("checksum command did not complete successfully")
    hashes = {}
    for line in streams["stdout"].decode("ascii").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        if match is None or match[2] in hashes:
            problems.append("malformed or duplicate checksum record")
            continue
        hashes[match[2]] = match[1]
    if set(hashes) != {row[2] for row in ARCHIVES}:
        problems.append("checksum record must cover exactly the three archives")
    started = datetime.fromisoformat(metadata["started_at"])
    for release_id, download_id, filename in ARCHIVES:
        release_metadata, release_streams = capture(Path(directory), release_id)
        assets = json.loads(release_streams["stdout"])["assets"]
        expected = next(asset["digest"] for asset in assets if asset["name"] == filename)
        if release_metadata["exit_code"] != 0 or "sha256:" + hashes.get(filename, "") != expected:
            problems.append(filename + ": actual checksum differs from published release digest")
        download, _ = capture(Path(directory), download_id)
        if download["exit_code"] != 0 or download["timed_out"]:
            problems.append(filename + ": download did not complete successfully")
        if datetime.fromisoformat(download["finished_at"]) >= started:
            problems.append(filename + ": checksum started before download completed")
    return problems


def verify_fixtures(directory, bindings):
    """Check captured file bytes against sources and bracketed native uses."""
    directory = Path(directory)
    problems = []
    for binding in bindings:
        source_meta, source = capture(directory, binding["source_capture"])
        read_meta, actual = capture(directory, binding["read_capture"])
        smoke, _ = capture(directory, binding["smoke_capture"])
        after, _ = capture(directory, binding["after_cmp_capture"])
        name = binding["fixture_path"]
        if source["stdout"] != actual["stdout"]:
            problems.append(name + ": actual fixture differs from captured source")
        for metadata in (source_meta, read_meta, smoke, after):
            if metadata["exit_code"] != 0 or metadata["timed_out"]:
                problems.append(name + ": failed source/read/smoke/post-compare command")
        if not (datetime.fromisoformat(source_meta["finished_at"]) < datetime.fromisoformat(read_meta["started_at"])
                and datetime.fromisoformat(read_meta["finished_at"]) < datetime.fromisoformat(smoke["started_at"])
                and datetime.fromisoformat(smoke["finished_at"]) < datetime.fromisoformat(after["started_at"])):
            problems.append(name + ": source/read/smoke/post-compare ordering violated")
        expected = ["cmp", "--silent", name, "<SCRATCH>/raw/" + binding["read_capture"] + "/stdout.bin"]
        if read_meta["argv"] != ["cat", name] or after["argv"] != expected:
            problems.append(name + ": native fixture command does not bind the named file")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--checksum-id", required=True)
    args = parser.parse_args()
    problems = verify_archives(args.captures, args.checksum_id)
    print(json.dumps({"check": "archive_digest_equality_and_sequential_timing", "archives": 3, "result": "FAIL" if problems else "PASS", "problems": problems}))
    return bool(problems)


if __name__ == "__main__":
    raise SystemExit(main())
