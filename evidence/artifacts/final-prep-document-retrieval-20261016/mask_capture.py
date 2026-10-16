"""Publish a deterministic masked derivative of a real util-linux script capture.

Privacy implementation reuses scripts/host_receipts.py:sanitize. This adapter only
adds explicit scratch/repository placeholders and terminal control normalization.
It neither selects output lines nor invents commands, exit codes or test results.
Raw captures remain private; hashes must be computed from the published output.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from host_receipts import sanitize  # noqa: E402

ANSI_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ANSI_OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def mask(raw: bytes, scratch: str, repository: str, *, container_create: bool = False) -> bytes:
    text = raw.decode("utf-8", errors="strict")
    for source, replacement in sorted(
        ((scratch, "<SCRATCH>"), (repository, "<REPO>")), key=lambda pair: -len(pair[0])
    ):
        if not source or source == "/":
            raise ValueError("A non-root explicit path is required")
        text = text.replace(source.rstrip("/"), replacement)
    text = sanitize(text)
    text = ANSI_OSC.sub("", ANSI_CSI.sub("", text)).replace("\r\n", "\n").replace("\r", "\n")
    if container_create:
        # Applied only to docker run's capture, never to digest/provenance logs.
        text = re.sub(r"(?m)^[0-9a-f]{64}$", "<CONTAINER_ID>", text)
    return text.encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--repository", default=str(ROOT))
    parser.add_argument("--container-create", action="store_true")
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("Raw capture and published derivative must be different files")
    result = mask(args.input.read_bytes(), args.scratch, args.repository,
                  container_create=args.container_create)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)


if __name__ == "__main__":
    main()
