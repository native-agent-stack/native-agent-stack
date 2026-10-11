"""Export the retained host grand catalog for repository-only consumers.

Both --write and --check use the host asset. CI consumers read the committed
snapshot; unit tests supply their own temp-root asset. No archive is extracted.
Reference: native-agent-stack@8bffa2c41692ef483e91b68e3b15aeb331423d2c,
tools/local-pages/architecture_sources.py:24-27,94-106,261-319.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from tarfile import TarError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from host_receipts import normalize_repository

SOURCE = "catalogs/landscape/grand-catalog-20261008.json"
ASSET_SOURCE = "evidence/artifacts/g5-start-closure-1-20261009/class-gates.json"
OUTPUT = "catalogs/landscape/grand-catalog-counts.json"
DISPOSITIONS = ("NO-GAP", "OUT-OF-SCOPE", "PENDING", "REJECT", "TRIAL", "WATCH")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_SPEC = importlib.util.spec_from_file_location("grand_counts_architecture_sources",
                                             ROOT / "tools/local-pages/architecture_sources.py")
_reader = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_reader)


def build(root: Path, state_root: Path, asset: Path | None = None) -> dict:
    """Derive all row counts and retain every repository's observed dispositions."""
    source_bytes = (root / SOURCE).read_bytes()
    catalog = json.loads(source_bytes)
    binding_bytes = (root / ASSET_SOURCE).read_bytes()
    binding = json.loads(binding_bytes)
    expected = binding.get("asset", {})
    if not isinstance(expected, dict) or not SHA256.fullmatch(str(expected.get("sha256", ""))):
        raise ValueError("grand catalog requires a pinned asset sha256")
    member_sha256 = binding.get("original_rows_sha256")
    if not SHA256.fullmatch(str(member_sha256)):
        raise ValueError("grand catalog requires a pinned compact member sha256")
    totals = Counter()
    by_layer = defaultdict(Counter)
    by_repository = defaultdict(set)
    rows_without_repository = 0

    def count(record):
        nonlocal rows_without_repository
        disposition, layer = record.get("disposition"), record.get("slot")
        if disposition not in DISPOSITIONS:
            raise ValueError("compact row has an unknown disposition")
        if not isinstance(layer, str) or not IDENTIFIER.fullmatch(layer):
            raise ValueError("compact row requires a bounded layer slot")
        totals[disposition] += 1
        by_layer[layer][disposition] += 1
        pin = record.get("pin") if isinstance(record.get("pin"), dict) else {}
        repository = (_reader._repo(record.get("repository_or_entry"))
                      or _reader._repo(pin.get("repository_or_source")))
        if repository:
            repository = normalize_repository("https://github.com/" + repository)
            by_repository[repository].add(disposition)
        else:
            rows_without_repository += 1

    asset = asset or state_root / _reader._FINAL_ASSET
    reads = _reader._policy.ArchitectureReads(root, state_root, policy_path=_reader.SOURCE_POLICY_PATH)
    meta, receipt = _reader._g5(asset, [], False, reads, on_record=count)
    if receipt["sha256"] != expected["sha256"] or receipt["bytes"] != expected.get("bytes"):
        raise ValueError("grand catalog asset differs from its pinned sha256 or size")
    if receipt["member_sha256"] != member_sha256:
        raise ValueError("grand catalog compact member differs from its pinned sha256")
    rows = sum(totals.values())
    dispositions = {key: totals[key] for key in DISPOSITIONS}
    layers = {key: {"rows": sum(values.values()),
                    "by_disposition": {disposition: values[disposition] for disposition in DISPOSITIONS}}
              for key, values in sorted(by_layer.items())}
    expected_counts = catalog.get("counts", {})
    if not isinstance(expected_counts, dict) or rows != expected_counts.get("rows") or rows != meta["rows"]:
        raise ValueError("grand catalog row count does not reconcile to the pinned catalog")
    if dispositions != expected_counts.get("by_disposition"):
        raise ValueError("grand catalog disposition counts do not reconcile to the pinned catalog")
    if sum(value["rows"] for value in layers.values()) != rows:
        raise ValueError("grand catalog layer counts do not reconcile to the retained rows")
    return {"schema_version": 1,
            "source": {"catalog": SOURCE, "catalog_sha256": hashlib.sha256(source_bytes).hexdigest(),
                       "asset_binding": ASSET_SOURCE, "asset_binding_sha256": hashlib.sha256(binding_bytes).hexdigest(),
                       "asset_sha256": receipt["sha256"], "asset_bytes": receipt["bytes"],
                       "rows_member": _reader._ROWS_MEMBER, "rows_sha256": receipt["member_sha256"]},
            "counts": {"rows": rows, "by_disposition": dispositions, "by_layer": layers,
                       "repositories": len(by_repository), "rows_without_repository": rows_without_repository},
            "by_repository": {key: sorted(values) for key, values in sorted(by_repository.items())}}


def serialize(document: dict) -> str:
    return json.dumps(document, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--state-root", type=Path,
                        default=Path.home() / ".local/state/native-agent-stack")
    parser.add_argument("--asset", type=Path, help="retained asset within the existing source-policy grant")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true", help="compare regenerated bytes (default; host only)")
    args = parser.parse_args(argv)
    try:
        document = build(args.root.resolve(), args.state_root.resolve(), args.asset)
        text = serialize(document)
        path = args.root / OUTPUT
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                                 prefix="." + path.name + ".", suffix=".tmp", delete=False) as temporary:
                    temporary_path = Path(temporary.name)
                    temporary.write(text)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                # CPython v3.13.16 Doc/library/os.rst, os.replace: successful
                # replacement is atomic; a sibling keeps both paths on one filesystem.
                os.replace(temporary_path, path)
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
        elif not path.is_file() or path.read_bytes() != text.encode("utf-8"):
            print(f"{OUTPUT} differs; run python3 scripts/grand_catalog_counts.py --write on the host", file=sys.stderr)
            return 1
    except FileNotFoundError:
        print("grand catalog source or retained asset is missing; no snapshot written", file=sys.stderr)
        return 1
    except _reader._policy.SourcePolicyError:
        print("grand catalog asset is outside the existing source-policy grant; no snapshot written", file=sys.stderr)
        return 1
    except (ValueError, OSError, TarError, subprocess.SubprocessError) as error:
        # Native filesystem/decoder errors can include host paths or source text.
        message = str(error) if type(error) is ValueError else "grand catalog source could not be read"
        print(f"{message}; no snapshot written", file=sys.stderr)
        return 1
    print(json.dumps({"status": "written" if args.write else "checked", "rows": document["counts"]["rows"],
                      "by_disposition": document["counts"]["by_disposition"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
