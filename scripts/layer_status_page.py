#!/usr/bin/env python3
"""Build docs/layer-status.md, the owner's one-row-per-layer status page, from catalogs/landscape/final-stack.json.

Each layer gets one state: FINAL (its terminal_state is FINAL), GAP (unswept, no-winner, or no winners) or TRIAL
(recorded winners whose FINAL conditions are incomplete). The missing evidence follows the four FINAL conditions of
docs/decisions/2026-10-11-layer-resolution-protocol.md, "Terminal states and evidence": a recorded verdict, a run pin
per winner, an E2E receipt through the upstream's own path at that pin (the winner factors host_e2e and pin_current),
and invoke evidence, which final-stack.json does not record, so every non-FINAL layer lists it. It also lists the
missing multi-angle record and the carried survivors. Rows come in the FINAL wave's order, each with its tier:
T1-trading (the layers that carry the owner's trading capabilities), then T1-harness, then the rest (T3) by name.

--check (the default) rebuilds the page and exits 1 when the checked-in file differs; --write writes it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "catalogs/landscape/final-stack.json"
OUTPUT = "docs/layer-status.md"
# The FINAL wave's order: the command center's sequencing ruling of 2026-10-16 on the wave order of
# docs/decisions/2026-10-15-new-wsl-clean-install-plan.md. T1-trading holds the layers that carry the owner's trading
# capabilities, in this order; T1-harness holds the harness layers. Every other layer is T3. T2's one layer,
# market-data-reference, moved into T1-trading.
TIERS = (
    ("T1-trading", (
        "us-equities/execution-broker",
        "us-equities/backtesting-engine",
        "us-equities/portfolio-risk",
        "us-equities/market-data-reference",
        "us-equities/research-factors-ml",
        "us-equities/catalysts-sentiment",
    )),
    ("T1-harness", (
        "foundation/token-efficiency",
        "foundation/durable-memory",
        "foundation/code-navigation",
        "foundation/semantic-rag",
        "foundation/document-retrieval",
        "foundation/instructions-skills",
        "foundation/native-clients",
        "foundation/workers",
        "foundation/isolation",
        "foundation/observation-inference",
        "foundation/git-github-automation",
        "foundation/ci-supply-chain",
        "foundation/model-routes",
        "foundation/agent-sdks",
        "foundation/mcp-surfaces",
        "foundation/quality-evaluation",
        "foundation/scheduling-supervision",
        "foundation/web-research",
    )),
)
REST = "T3"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _state(item: dict) -> str:
    if item.get("terminal_state") == "FINAL":
        return "FINAL"
    if item.get("status") in ("unswept", "no-winner") or not item.get("winners"):
        return "GAP"
    return "TRIAL"


def _missing(item: dict, runs: dict) -> list[str]:
    if item.get("status") == "unswept":
        return ["no completed sweep"]
    if item.get("terminal_state") == "FINAL":
        return []
    missing = []
    verdict = item.get("verdict") or {}
    if not (verdict.get("status") == "recorded" and verdict.get("wave") and verdict.get("next_review")):
        missing.append("verdict")
    winners = item.get("winners") or []
    no_run = [w.get("component_id") for w in winners if w.get("run") not in runs]
    if no_run:
        missing.append("run pin: " + ", ".join(no_run))
    no_e2e = []
    for w in winners:
        factors = (w.get("factors") or [{}])[0]
        # Condition 3 is an E2E at the run pin, so a winner without a run pin cannot meet it.
        if w.get("run") not in runs or not (factors.get("host_e2e") == "true" and factors.get("pin_current") == "true"):
            no_e2e.append(w.get("component_id"))
    if no_e2e:
        missing.append("E2E at current pin: " + ", ".join(no_e2e))
    missing.append("invoke evidence")
    if (item.get("angles") or {}).get("status") != "recorded":
        missing.append("multi-angle record")
    survivors = {s.get("repository") if isinstance(s, dict) else str(s) for s in (item.get("survivors") or [])}
    if survivors:
        missing.append(f"{len(survivors)} carried survivor{'' if len(survivors) == 1 else 's'}")
    return missing


def build_rows(stack: dict) -> list[dict]:
    runs = {run["id"]: run for run in stack.get("runs") or []}
    rows = []
    for item in stack.get("layers") or []:
        key = f'{item["catalog"]}/{item["layer_id"]}'
        winners = []
        for w in item.get("winners") or []:
            run = runs.get(w.get("run"))
            pin = str(run.get("pin"))[:12] if run and run.get("pin") else "no run pin"
            winners.append(f'{w.get("component_id")}@{pin}')
        next_action = (item.get("research") or {}).get("next_action")
        if not next_action:
            next_action = ("initial sweep scoped to the gap" if item.get("status") == "unswept"
                           else "close the missing FINAL conditions")
        rows.append({"layer": key, "status": item.get("status"), "state": _state(item), "winners": winners,
                     "missing": _missing(item, runs), "next_action": next_action})
    rank, tier = {}, {}
    for name, keys in TIERS:
        for key in keys:
            rank[key], tier[key] = len(rank), name
    for r in rows:
        r["tier"] = tier.get(r["layer"], REST)
    rows.sort(key=lambda r: (rank.get(r["layer"], len(rank)), r["layer"]))
    return rows


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render(stack: dict) -> str:
    rows = build_rows(stack)
    counts = {state: sum(r["state"] == state for r in rows) for state in ("FINAL", "TRIAL", "GAP")}
    lines = [
        "# Layer status",
        "",
        f"Generated by `scripts/layer_status_page.py` from `{SOURCE}` (checked {stack.get('checked_at')}); do not edit "
        "by hand. FINAL needs the four conditions of the "
        "[layer-resolution protocol](decisions/2026-10-11-layer-resolution-protocol.md): a recorded verdict, a run pin, "
        "an upstream E2E at that pin and invoke evidence. TRIAL marks recorded winners whose FINAL conditions are "
        "incomplete; GAP marks a layer with no winner or no completed sweep. Rows are in the FINAL wave's order: "
        "T1-trading (the layers that carry the owner's trading capabilities), then T1-harness, then the rest (T3).",
        "",
        f"**{len(rows)} layers:** {counts['FINAL']} FINAL, {counts['TRIAL']} TRIAL, {counts['GAP']} GAP.",
        "",
        "| # | Tier | Layer | Status | State | Winner@run pin | Evidence still missing | Next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(rows, 1):
        lines.append(f'| {i} | {r["tier"]} | `{r["layer"]}` | {r["status"]} | {r["state"]} | '
                     f'{_cell("; ".join(r["winners"]) or "none")} | {_cell("; ".join(r["missing"]) or "none")} | '
                     f'{_cell(r["next_action"])} |')
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="rebuild and compare with the checked-in page (default)")
    mode.add_argument("--write", action="store_true", help="rebuild and write the page")
    args = parser.parse_args(argv)
    built = render(load(args.root / SOURCE))
    output = args.root / OUTPUT
    if args.write:
        output.write_text(built, encoding="utf-8")
        print(f"wrote {OUTPUT}")
        return 0
    if not output.exists() or output.read_text(encoding="utf-8") != built:
        print(f"{OUTPUT} is stale: run python3 scripts/layer_status_page.py --write", file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "layers": len(build_rows(load(args.root / SOURCE)))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
