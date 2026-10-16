#!/usr/bin/env python3
"""Build docs/layer-status.md, the owner's one-row-per-layer status page, from catalogs/landscape/final-stack.json.

Each layer gets one state: FINAL (its terminal_state is FINAL), GAP (unswept, no-winner, or no winners) or TRIAL
(recorded winners whose FINAL conditions are incomplete). The missing evidence follows the four FINAL conditions of
docs/decisions/2026-10-11-layer-resolution-protocol.md, "Terminal states and evidence", read from the same inputs as
the FINAL predicate (scripts/final_stack.py, enforce_final):
- a recorded verdict;
- per winner, a run pin whose pin_drift is "same" and whose complete identity matches the verdict pin;
- per winner, an E2E receipt bound in the layer's angle record (final_evidence) at that run pin, validated by
  final_stack.check_condition_3: the file exists, binds native_proven evidence to the repository at the complete pin,
  matches the upstream_e2e schema and records a successful install and test with pinned citations;
- per winner, invoke evidence in that same binding, validated by final_stack.check_condition_4: an invocation receipt
  with positive calls in a measured window, or a recorded not_invoked_reason.
It also lists the missing multi-angle record and the carried survivors. Rows come in the FINAL wave's order, each with
its tier: T1-trading (the layers that carry the owner's trading capabilities), then T1-harness, then the rest (T3).

--check (the default) rebuilds the page and exits 1 when the checked-in file differs; --write writes it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from . import final_stack, host_receipts
except ImportError:  # running as a plain script, not a package
    import final_stack
    import host_receipts

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "catalogs/landscape/final-stack.json"
OUTPUT = "docs/layer-status.md"
# The FINAL wave's order: the command center's sequencing ruling of 2026-10-16 on the wave order of
# docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:173-182 at 229cc7d3 (the plan's merge). T1-trading holds the
# layers that carry the owner's trading capabilities, in this order; T1-harness holds the harness layers. Every other
# layer is T3. T2's one layer, market-data-reference, moved into T1-trading.
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
        "us-equities/observability-hosting",
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
# The CC's gap-routing ROW of 2026-10-16T01:08Z (sequencing only): us-equities/observability-hosting joins T1-harness as
# god-view work (above), and TradingView automation joins T1-trading after catalysts-sentiment. Its erratum-01 (01:52Z)
# routes that work as a continuation of #1182, widened by campaign C1, not a new sweep. It has no layer row yet; the
# protocol decides which rows its candidates enter, so the page lists it below the table.
SWEEPS_WITHOUT_ROW = (
    ("T1-trading", "us-equities/catalysts-sentiment",
     "TradingView automation, continuing in #1182 and widened by campaign C1 (no duplicate sweep): its MCP servers, "
     "alerts and webhooks into the deterministic order gate, Pine strategies and the strategy tester, and strategy "
     "templates"),
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def unknown_tier_layers(stack: dict) -> set[str]:
    """TIERS keys that name no layer of final-stack.json, so a renamed layer is reported instead of falling into T3."""
    layers = {f'{item["catalog"]}/{item["layer_id"]}' for item in stack.get("layers") or []}
    return {key for _, keys in TIERS for key in keys} - layers


def _state(item: dict) -> str:
    if item.get("terminal_state") == "FINAL":
        return "FINAL"
    if item.get("status") in ("unswept", "no-winner") or not item.get("winners"):
        return "GAP"
    return "TRIAL"


def _run_pin_gap(w: dict, run: dict | None) -> str | None:
    """Condition 2 as enforce_final reads it: a run in runs[] with a pin, pin_drift "same", and a complete match."""
    name = w.get("component_id")
    if run is None or not run.get("pin"):
        return f"{name} (no run pin)"
    if w.get("pin_drift") != "same" or not final_stack.complete_final_pin(w.get("verdict_pin"), run):
        return f'{name} (verdict {w.get("verdict_pin")}, run {run.get("pin")})'
    return None


def _bound_evidence(w: dict, run: dict | None, record: dict | None) -> dict | None:
    """The angle record's final_evidence entry for the winner, bound as enforce_final binds it: exactly one candidate
    for the winner's repository at its complete run pin (final_stack.final_candidates), and an entry for that candidate
    whose run_pin is the complete run pin. None otherwise."""
    if run is None or not record:
        return None
    try:
        candidates = final_stack.final_candidates(record, host_receipts.normalize_repository(w.get("repository")), run)
    except (KeyError, TypeError):
        return None
    if len(candidates) != 1:
        return None
    bound = {e.get("candidate_id"): e for e in record.get("final_evidence") or [] if isinstance(e, dict)}
    evidence = bound.get(candidates[0].get("id"))
    if not evidence or not final_stack.complete_final_pin(evidence.get("run_pin"), run):
        return None
    return evidence


def _covered(w: dict, run: dict | None, record: dict | None) -> bool:
    """The angle record covers the winner as enforce_final requires: one qualified candidate for its repository at its
    complete run pin (final_stack.final_candidate). A record that covers only other candidates covers no winner."""
    if run is None or not record:
        return False
    try:
        final_stack.final_candidate(record, host_receipts.normalize_repository(w.get("repository")), run)
    except (final_stack.FinalStackError, KeyError, TypeError):
        return False
    return True


def _condition_holds(check, root: Path | None, w: dict, run: dict | None, record: dict | None) -> bool:
    """Run one of final_stack's condition checks (check_condition_3 or check_condition_4) on the winner's bound
    evidence, reading receipts under root. A missing, failed or wrong-pin receipt fails it."""
    evidence = _bound_evidence(w, run, record)
    if evidence is None or root is None:
        return False
    try:
        check(final_stack.Sources(root), evidence, host_receipts.normalize_repository(w.get("repository")), run)
    except final_stack.FinalStackError:
        return False
    return True


def _missing(item: dict, runs: dict, record: dict | None = None, root: Path | None = None) -> list[str]:
    if item.get("status") == "unswept":
        return ["no completed sweep"]
    if item.get("terminal_state") == "FINAL":
        return []
    missing = []
    verdict = item.get("verdict") or {}
    if not (verdict.get("status") == "recorded" and verdict.get("wave") and verdict.get("next_review")):
        missing.append("verdict")
    winners = item.get("winners") or []
    pin_gaps = [g for g in (_run_pin_gap(w, runs.get(w.get("run"))) for w in winners) if g]
    if pin_gaps:
        missing.append("run pin: " + "; ".join(pin_gaps))
    no_e2e = [w.get("component_id") for w in winners if not _condition_holds(final_stack.check_condition_3, root, w, runs.get(w.get("run")), record)]
    if no_e2e:
        missing.append("E2E at run pin: " + ", ".join(no_e2e))
    no_invoke = [w.get("component_id") for w in winners if not _condition_holds(final_stack.check_condition_4, root, w, runs.get(w.get("run")), record)]
    if not winners:
        missing.append("invoke evidence")
    elif no_invoke:
        missing.append("invoke evidence: " + ", ".join(no_invoke))
    if (item.get("angles") or {}).get("status") != "recorded":
        missing.append("multi-angle record")
    else:
        uncovered = [w.get("component_id") for w in winners if not _covered(w, runs.get(w.get("run")), record)]
        if uncovered:
            missing.append("multi-angle record: " + ", ".join(uncovered))
    survivors = {s.get("repository") if isinstance(s, dict) else str(s) for s in (item.get("survivors") or [])}
    if survivors:
        missing.append(f"{len(survivors)} carried survivor{'' if len(survivors) == 1 else 's'}")
    return missing


def angle_records(stack: dict, root: Path) -> dict:
    """The angle records final-stack.json points to (layers[].angles.path), keyed by that path."""
    records = {}
    for item in stack.get("layers") or []:
        path = (item.get("angles") or {}).get("path")
        if path and path not in records and (root / path).is_file():
            records[path] = load(root / path)
    return records


def build_rows(stack: dict, records: dict | None = None, root: Path | None = None) -> list[dict]:
    runs = {run["id"]: run for run in stack.get("runs") or []}
    records = records or {}
    rows = []
    for item in stack.get("layers") or []:
        key = f'{item["catalog"]}/{item["layer_id"]}'
        winners = []
        for w in item.get("winners") or []:
            run = runs.get(w.get("run"))
            pin = str(run.get("pin")) if run and run.get("pin") else "no run pin"
            winners.append(f'{w.get("component_id")}@{pin}')
        next_action = (item.get("research") or {}).get("next_action")
        if not next_action:
            next_action = ("initial sweep scoped to the gap" if item.get("status") == "unswept"
                           else "close the missing FINAL conditions")
        record = records.get((item.get("angles") or {}).get("path"))
        rows.append({"layer": key, "status": item.get("status"), "state": _state(item), "winners": winners,
                     "missing": _missing(item, runs, record, root), "next_action": next_action})
    rank, tier = {}, {}
    for name, keys in TIERS:
        for key in keys:
            rank[key], tier[key] = len(rank), name
    for r in rows:
        r["tier"] = tier.get(r["layer"], REST)
    rows.sort(key=lambda r: (rank.get(r["layer"], len(rank)), r["layer"]))
    return rows


# Every value the page reads or derives becomes literal text through _cell, one rule from the GFM spec and its reference
# parser, github/cmark-gfm 0.29.0.gfm.13 at 587a12bb54d95ac37241377e6ddc93ea0e45439b. A line ending (LF, CR or CRLF,
# test/spec.txt:316-318) would end the table row, so it becomes a space. Every ASCII punctuation character
# (test/spec.txt:345-350) is backslash-escaped, which renders as that character itself (test/spec.txt:5787-5795), so no
# HTML, entity, code span, emphasis or link survives. The table scanner reads such a pair as one character, so only an
# unescaped pipe ends a cell (extensions/ext_scanners.re:32-35), and it unescapes the pipe before inline parsing
# (extensions/table.c:150-169; test/spec.txt:3371-3372).
_LINE_ENDING = re.compile(r"\r\n|\r|\n")
_ASCII_PUNCTUATION = re.compile(r"([!-/:-@\[-`{-~])")


def _cell(value) -> str:
    return _ASCII_PUNCTUATION.sub(r"\\\1", _LINE_ENDING.sub(" ", str(value)))


def render(stack: dict, records: dict | None = None, root: Path | None = None) -> str:
    rows = build_rows(stack, records, root)
    counts = {state: sum(r["state"] == state for r in rows) for state in ("FINAL", "TRIAL", "GAP")}
    lines = [
        "# Layer status",
        "",
        f"Generated by `scripts/layer_status_page.py` from `{SOURCE}` (checked {_cell(stack.get('checked_at'))}); "
        "do not edit by hand. FINAL needs the four conditions of the "
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
        cells = (i, r["tier"], r["layer"], r["status"], r["state"], "; ".join(r["winners"]) or "none",
                 "; ".join(r["missing"]) or "none", r["next_action"])
        lines.append("| " + " | ".join(_cell(value) for value in cells) + " |")
    if SWEEPS_WITHOUT_ROW:
        lines += ["", "**Work with no layer row yet** (the protocol decides which rows its candidates enter):", ""]
        lines += [f"- {_cell(tier)}, after {_cell(after)}: {what}." for tier, after, what in SWEEPS_WITHOUT_ROW]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="rebuild and compare with the checked-in page (default)")
    mode.add_argument("--write", action="store_true", help="rebuild and write the page")
    args = parser.parse_args(argv)
    stack = load(args.root / SOURCE)
    built = render(stack, angle_records(stack, args.root), args.root)
    output = args.root / OUTPUT
    if args.write:
        output.write_text(built, encoding="utf-8")
        print(f"wrote {OUTPUT}")
        return 0
    if not output.exists() or output.read_text(encoding="utf-8") != built:
        print(f"{OUTPUT} is stale: run python3 scripts/layer_status_page.py --write", file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "layers": len(stack.get("layers") or [])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
