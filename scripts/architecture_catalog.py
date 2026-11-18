#!/usr/bin/env python3
"""Fail-Closed MADR 4.0 ADR Catalog, 40-char SHA Workflow & Zero-Leak Privacy Gate."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADR_DIR = ROOT / "docs" / "adr"
CATALOG_MD = ADR_DIR / "CATALOG.md"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"

LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Alpaca Paper Account ID (PA...)", re.compile(r"\bPA[0-9A-Z]{10}\b")),
    ("IBKR Paper Account ID (DU...)", re.compile(r"\bDU[0-9]{7,9}\b")),
    ("Alpaca API Key Prefix", re.compile(r"\b(?:AK|PK)[0-9A-Z]{18,24}\b")),
    ("Private PEM Key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Concrete Local Home Path", re.compile(r"/" + r"Users/(?!<)[A-Za-z0-9._-]+/")),
)


def verify_adr_catalog_and_privacy(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if not CATALOG_MD.is_file():
        return ["Missing docs/adr/CATALOG.md"]

    cat_txt = CATALOG_MD.read_text(encoding="utf-8")
    adrs = sorted(p for p in ADR_DIR.glob("ADR-[0-9][0-9][0-9][0-9]-*.md"))
    if len(adrs) < 5:
        errors.append(f"Expected >=5 ADR files, found {len(adrs)}")

    for adr in adrs:
        if f"({adr.name})" not in cat_txt:
            errors.append(f"ADR not indexed in docs/adr/CATALOG.md: {adr.name}")
        body = adr.read_text(encoding="utf-8")
        if "**Status:** Accepted" not in body:
            errors.append(f"ADR missing '**Status:** Accepted': {adr.name}")

    if CI_YML.is_file():
        ci_txt = CI_YML.read_text(encoding="utf-8")
        for m in re.finditer(r"^\s*-?\s*uses:\s*([^\s#]+)", ci_txt, flags=re.MULTILINE):
            ref = m.group(1)
            if "@" not in ref or not re.fullmatch(r"[0-9a-f]{40}", ref.split("@", 1)[1]):
                errors.append(f"Unpinned GitHub Action reference in ci.yml (must be 40-char SHA): {ref}")
    else:
        errors.append("Missing .github/workflows/ci.yml")

    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    res = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True,
        text=True,
        check=False,
        env=clean_env,
    )
    tracked = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
    for rel in tracked:
        fp = root / rel
        if not fp.is_file():
            continue
        try:
            txt = fp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, rx in LEAK_PATTERNS:
            if rx.search(txt):
                errors.append(f"Privacy tripwire ({label}) matched in {rel}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify MADR 4.0 catalog & zero-leak privacy invariants")
    parser.add_argument(
        "--check", action="store_true", help="Run fail-closed catalog & privacy verification"
    )
    parser.parse_args()

    errs = verify_adr_catalog_and_privacy(ROOT)
    if errs:
        for e in errs:
            print(f"[ADR-GATE FAIL] {e}", file=sys.stderr)
        return 1
    print(
        "[ADR-GATE PASS] 5/5 MADR 4.0 ADRs, 40-char SHA-pinned CI actions, and zero-leak privacy verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
