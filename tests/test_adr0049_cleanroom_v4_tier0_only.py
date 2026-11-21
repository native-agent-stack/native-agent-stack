from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_adr0049_cleanroom_tier0_only_agents_md_is_lean_complete_and_zero_leak() -> None:
    draft = ROOT / "docs" / "cleanroom" / "TIER0_ONLY_AGENTS.md"
    adr = (
        ROOT
        / "docs"
        / "adr"
        / "ADR-0049-cleanroom-v4-sota-only-hosted-ecosystem-legacy-retirement-and-tier0-only-agent-md.md"
    )
    assert draft.is_file()
    assert adr.is_file()

    txt = draft.read_text(encoding="utf-8")
    lines = txt.splitlines()
    assert len(lines) <= 90, f"Tier-0-Only AGENTS.md must stay lean (<=90 lines), got {len(lines)}"

    for required in (
        "ONE RULE ONLY",
        "Never self-build ever again",
        "sota-shelf-and-harness",
        "sota-research-engine",
        "sota-trading-node",
        "sota-private-vault",
        "ALPACA_PAPER_TRADE=true",
        "ALPACA_TOOLSETS=",
        "microsoft/qlib@v0.9.8",
        "RD-Agent v1.0.0",
        "Norm-Disruption",
        "2026-10-15",
    ):
        assert required in txt, f"Missing required Tier-0 clause in TIER0_ONLY_AGENTS.md: {required}"

    leak_rx = re.compile(
        r"(C:\\U"
        + r"sers|/"
        + r"Users/|/"
        + r"home/|PA[0-9A-Z]{8,}|DU[0-9]{7,}|AK[0-9A-Z]{16,}|PK[0-9A-Z]{16,})"
    )
    assert not leak_rx.search(txt + adr.read_text(encoding="utf-8"))
