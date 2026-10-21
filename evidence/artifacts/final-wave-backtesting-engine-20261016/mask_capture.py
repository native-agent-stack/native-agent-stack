"""Deterministic publication mask; never creates or summarizes run output.

Uses the existing repository sanitizer at native-agent-stack/native-agent-stack
@caa224140a2d04ba5f3d0ca320c487a75f9c9ea1:scripts/host_receipts.py:273.
Native recorder: util-linux/util-linux@v2.41.3:term-utils/script.1.adoc:54,79.
Compression: python/cpython@v3.13.16:Lib/gzip.py, compress(mtime=0).
The input is private. Only the masked output's digest is ever emitted.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import types

ROOT = Path(__file__).resolve().parents[3]
SANITIZER_PIN = "caa224140a2d04ba5f3d0ca320c487a75f9c9ea1"
SANITIZER_SHA256 = "c3dc47cdab33e2ed2f1473700774a006a34c6218d6cd7ceb36f33d7f71f0fd6f"


SANITIZER_DEPENDENCIES = {"scripts/validate.py":"a68c189c56bef41b0d3d8a5069920e15db45249818054c444988abad1e8f8477","scripts/catalog_decisions.py":"98ca164a332baf46b0429ac93e4272af4dedd26a2647dcf493f321bb1169d65e"}


def verify_sanitizer_sources():
    """Guard publication through the CLI, without gating ordinary mask unit calls."""
    source = (ROOT / "scripts/host_receipts.py").read_bytes()
    if hashlib.sha256(source).hexdigest() != SANITIZER_SHA256:
        raise ValueError("sanitizer source differs from cited pin " + SANITIZER_PIN)
    for relative, expected in SANITIZER_DEPENDENCIES.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("sanitizer source dependency differs from cited pin: " + relative)


def load_sanitizer(*, home, username):
    """Reuse the repository helper with explicit identity; CLI checks provenance."""
    source_path = ROOT / "scripts/host_receipts.py"
    source = source_path.read_bytes()
    namespace = {"__name__": "backtesting_pinned_sanitizer", "__file__": str(source_path),
                 "__package__": "scripts"}
    sys.path.insert(0, str(ROOT))
    try:
        exec(compile(source, str(source_path), "exec"), namespace)
    finally:
        sys.path.pop(0)
    # The pinned helper uses these globals only to obtain identity. Supplying
    # them here avoids any ambient HOME/USER/LOGNAME/getpass lookup.
    namespace["Path"] = types.SimpleNamespace(home=lambda: home)
    namespace["os"] = types.SimpleNamespace(environ={"USER": username})
    namespace["getpass"] = types.SimpleNamespace(getuser=lambda: username)
    return namespace["sanitize"]

HEX64 = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", re.I)
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
HOST_SPEC = re.compile(
    r"(?m)^((?:[^\r\n]*?\bBacktestEngine:[ \t]+)?"
    r"(?:CPU architecture|CPU\(s\)|OS|RAM-(?:Total|Used|Avail)|"
    r"Swap-(?:Total|Used|Avail)):[ \t]*)[^\r\n\x1b]*"
)


def mask_bytes(raw: bytes, replacements=(), *, hostname, home="", username="") -> bytes:
    """Mask identity, paths, raw fingerprints and incidental host metadata.

    Native result counts, return codes, failure text, timestamps, whitespace and stream
    order are retained. No tail selection, fabricated status, or newline rewrite.
    """
    text = raw.decode("utf-8")
    for old, new in replacements:
        if not old:
            raise ValueError("empty replacement refused")
        text = text.replace(old, new)
    if not hostname:
        raise ValueError("explicit hostname is required")
    text = load_sanitizer(home=home, username=username)(text)
    # Bracket markers also remain legal within native XML attribute values.
    text = text.replace("<user>", "[USER]")
    text = text.replace(hostname, "[HOST]")
    text = HOST_SPEC.sub(r"\1[HOST_SPEC]", text)
    text = UUID.sub("[RUNTIME_UUID]", text)
    text = HEX64.sub("[PRIVATE_RAW_DIGEST]", text)
    text = re.sub(r"(?m)(\bPID:\s*)[0-9]+", r"\1[PROCESS_ID]", text)
    return text.encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--raw-name", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--replace", nargs=2, action="append", default=[])
    parser.add_argument("--context", type=Path, required=True,
                        help="Private JSON with explicit hostname, home and username")
    args = parser.parse_args(argv)
    verify_sanitizer_sources()
    context = json.loads(args.context.read_text())
    masked = mask_bytes(args.raw.read_bytes(), args.replace, **context)
    output = gzip.compress(masked, mtime=0) if args.out.suffix == ".gz" else masked
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(output)
    print(json.dumps({
        "representation": "masked_derivative_of_native_capture",
        "raw_capture_name_only": args.raw_name,
        "masking_rule": "mask_capture.py",
        "compression": "gzip,mtime=0" if args.out.suffix == ".gz" else "none",
        "published_file": (args.out.relative_to(Path(__file__).parent).as_posix()
                           if args.out.is_relative_to(Path(__file__).parent) else args.out.name),
        "published_sha256": hashlib.sha256(output).hexdigest(),
        "published_bytes": len(output),
        "not_an_engine_result": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
