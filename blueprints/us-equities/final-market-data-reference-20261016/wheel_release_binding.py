"""Bind declared source tags to PyPI release wheels and the accepted lock.

Source-only deterministic audit, not an E2E receipt or a reproducible-build claim.
PyPI JSON API: https://docs.pypi.org/api/json/#get-a-release
uv supports pip install --require-hashes --no-deps (native help is captured).
"""

import argparse
import json
from pathlib import Path
import tomllib


WINNERS = [
    ("alpaca-py", "0.44.0", "cc4cb3b7ba50ae250e621983c2779047fb16bb28", "alpaca"),
    ("edgartools", "5.61.1", "7338aa335f6442c52dfa0695422cf1cd27e946e0", "edgar"),
    ("exchange-calendars", "4.13.2", "dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a", "calendar"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", required=True, type=Path)
    parser.add_argument("--runtime-lock", required=True, type=Path)
    parser.add_argument("--requirements", required=True, type=Path)
    args = parser.parse_args()
    packages = tomllib.loads(args.runtime_lock.read_text())["package"]
    bindings, requirements = [], []
    for name, version, commit, suffix in WINNERS:
        raw_record = args.release_root / ("pypi-" + suffix + ".log")
        release = json.loads(raw_record.read_bytes())
        assert release["info"]["version"] == version
        lock_package = next(p for p in packages if p["name"] == name)
        assert lock_package["version"] == version
        pure_wheels = [u for u in release["urls"]
                       if u["filename"].endswith("-py3-none-any.whl")]
        if len(pure_wheels) != 1:
            raise ValueError("expected exactly one vendor pure-Python wheel")
        wheel = pure_wheels[0]
        digest = wheel["digests"]["sha256"]
        matching_lock_wheels = [w for w in lock_package["wheels"]
                               if w["hash"] == "sha256:" + digest and w["url"] == wheel["url"]]
        assert len(matching_lock_wheels) == 1
        tag_record = args.release_root / (suffix + "-release-tag.log")
        tags = [line.split() for line in tag_record.read_text().splitlines()]
        matching_tags = [ref for oid, ref in tags if oid == commit]
        assert matching_tags, "official release tag must resolve to declared source commit"
        requirements.append(f"{name}=={version} --hash=sha256:{digest}")
        bindings.append({
            "package": name, "version": version, "source_commit": commit,
            "official_tag_refs": matching_tags, "wheel": wheel["filename"],
            "wheel_sha256": digest, "wheel_url": wheel["url"],
            "pypi_record": {"path": raw_record.name, "line": 1},
            "tag_record": {"path": tag_record.name, "line": next(
                i for i, line in enumerate(tag_record.read_text().splitlines(), 1)
                if line.split()[0] == commit)},
            "runtime_lock_wheel_match": True,
            "scope": "Official tag identity plus PyPI release-wheel hash and locked wheel; full bit-for-bit source build not performed.",
        })
    with args.requirements.open("x") as output:
        output.write("\n".join(requirements) + "\n")
    print(json.dumps({"schema": "wheel-release-binding/1", "bindings": bindings,
        "scope": "Deterministic source/lock audit; not native component E2E or comparative evidence."}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
