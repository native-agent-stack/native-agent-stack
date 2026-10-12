#!/usr/bin/env python3
"""E1 decision rule (preregistration section 6, addendum 1) over promptfoo result files: e1_decide.py RESULTS.json [RESULTS.json ...] [--baseline A0a] [--json OUT]

Reads the `question` rows of promptfoo's `-o` files (the `preflight` row is not a measurement), regrades every stored answer with e1_grade.py as it is now, and takes cost, turns and seconds from the response and
the tool names from `response.metadata.toolCalls`. Per arm, over the questions it shares with the baseline arm:
  (i)   correct answers: the number of correct runs, against the baseline's over the same questions (an arm passes (i) when it is not fewer);
  (ii)  median cost: the median response cost, against the baseline's (passes when at most 1.1 times);
  (iii) code-navigation use: the share of questions on which at least half of the arm's repeats called a tool of the code-navigation servers (passes at 70 percent or more).
An arm is adopted as the default of a worktree workflow only when (i), (ii) and (iii) all pass; otherwise the outcome is "correct non-use or no gain". A5 (no server) is a cost and correctness reference, not an
adoption candidate. Also printed: use by run, the carrying cost of the servers (A0b against A5) and each arm's median seconds and turns. The statistics are descriptive. A run that ended in a provider error is a
fault: it is listed, left out of the figures, and the exit status is 3 so that someone reads it before the figures are used; arms with unequal numbers of runs over the shared questions are refused (exit 2).
Exit 0 decided, 2 a refusal, 3 faults present.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e1_common as C  # noqa: E402
import e1_grade  # noqa: E402
from e1_assert import parse_output  # noqa: E402

PROVIDER_ERROR = 2  # ResultFailureReason.ERROR (promptfoo/promptfoo@30949931ee90, src/types/index.ts L380-L386); ASSERT is 1
COST_FACTOR = 1.1
USE_SHARE = 0.7


def load_runs(paths, tasks):
    """(runs, faults) from promptfoo result files; a run is a dict, a fault is a one-line text."""
    questions = {q["id"]: q for q in tasks["questions"]}
    runs, faults = [], []
    for path in paths:
        for item in json.loads(Path(path).read_text(encoding="utf-8"))["results"]["results"]:
            if ((item.get("testCase") or {}).get("metadata") or {}).get("kind") != "question":
                continue
            arm = (item.get("provider") or {}).get("label")
            qid = (item.get("vars") or {}).get("question_id")
            response = item.get("response") or {}
            tag = f"{arm} {qid} r{(item.get('vars') or {}).get('repeat')}"
            if qid not in questions or arm not in C.ARMS:
                faults.append(f"{tag}: an arm or question this config does not define")
                continue
            if item.get("failureReason") == PROVIDER_ERROR or response.get("error"):  # an assertion that rejects an answer is failureReason 1 and a result; its text is also in item["error"]
                faults.append(f"{tag}: provider error ({str(response.get('error') or item.get('error'))[:80]})")
                continue
            meta = response.get("metadata") or {}
            names = [c.get("name") for c in meta.get("toolCalls") or [] if isinstance(c, dict)]
            nav = [n for n in names if isinstance(n, str) and any(n.startswith(f"mcp__{s}__") for s in C.CODE_NAV_SERVERS)]
            millis = meta.get("durationMs") if isinstance(meta.get("durationMs"), (int, float)) else item.get("latencyMs")
            runs.append({"arm": arm, "q": qid, "repeat": str((item.get("vars") or {}).get("repeat")), "correct": bool(e1_grade.grade(questions[qid], parse_output(response.get("output")))["correct"]),
                         "cost": float(response.get("cost") or 0.0), "turns": meta.get("numTurns") or 0, "seconds": (millis or 0) / 1000.0, "nav": bool(nav)})
    return runs, faults


def summary(runs, questions):
    runs = [r for r in runs if r["q"] in questions]
    by_question = {}
    for r in runs:
        by_question.setdefault(r["q"], []).append(r)
    used = sum(1 for v in by_question.values() if sum(x["nav"] for x in v) * 2 >= len(v))
    return {"runs": len(runs), "questions": len(by_question), "correct": sum(r["correct"] for r in runs), "median_cost": statistics.median(r["cost"] for r in runs) if runs else None,
            "use_runs": sum(r["nav"] for r in runs), "use_questions": used, "use_share": used / len(by_question) if by_question else 0.0,
            "median_seconds": statistics.median(r["seconds"] for r in runs) if runs else None, "median_turns": statistics.median(r["turns"] for r in runs) if runs else None}


def decide(runs, baseline="A0a"):
    by_arm = {}
    for r in runs:
        by_arm.setdefault(r["arm"], []).append(r)
    arms = [a for a in C.ARMS if a in by_arm]
    if baseline not in by_arm:
        raise ValueError(f"the baseline arm {baseline} has no runs in these files")
    base_questions = {r["q"] for r in by_arm[baseline]}
    rows, verdicts = {}, {}
    for arm in arms:
        common = {r["q"] for r in by_arm[arm]} & base_questions if arm != baseline else base_questions
        rows[arm] = summary(by_arm[arm], common)
        if arm in (baseline, "A5"):
            continue
        base = summary(by_arm[baseline], common)
        if rows[arm]["runs"] != base["runs"]:
            raise ValueError(f"{arm} has {rows[arm]['runs']} runs and {baseline} {base['runs']} over their shared questions: the correct-answer counts are not comparable")
        i = rows[arm]["correct"] >= base["correct"]
        ii = rows[arm]["median_cost"] <= COST_FACTOR * base["median_cost"]
        iii = rows[arm]["use_share"] >= USE_SHARE
        verdicts[arm] = {"i_correct_not_fewer": i, "ii_median_cost_at_most_1.1x": ii, "iii_use_on_70_percent_of_questions": iii, "adopt": i and ii and iii,
                         "correct_vs_baseline": f"{rows[arm]['correct']} vs {base['correct']}", "median_cost_vs_baseline": f"{rows[arm]['median_cost']:.4f} vs {base['median_cost']:.4f}",
                         "use_share": round(rows[arm]["use_share"], 3)}
    carrying = None
    if "A0b" in by_arm and "A5" in by_arm:
        shared = {r["q"] for r in by_arm["A0b"]} & {r["q"] for r in by_arm["A5"]}
        a, b = summary(by_arm["A0b"], shared), summary(by_arm["A5"], shared)
        carrying = {"questions": len(shared), "median_cost_A0b": a["median_cost"], "median_cost_A5": b["median_cost"], "cost_change_percent": round((a["median_cost"] / b["median_cost"] - 1) * 100, 1),
                    "correct_A0b": a["correct"], "correct_A5": b["correct"], "median_seconds_A0b": a["median_seconds"], "median_seconds_A5": b["median_seconds"]}
    return {"baseline": baseline, "rows": rows, "verdicts": verdicts, "carrying": carrying}


def render(result):
    lines = [f"{'arm':4s} {'runs':>4s} {'qs':>3s} {'correct':>7s} {'med cost':>9s} {'use runs':>8s} {'use qs':>6s} {'med s':>6s} {'turns':>5s}"]
    for arm, s in result["rows"].items():
        lines.append(f"{arm:4s} {s['runs']:4d} {s['questions']:3d} {s['correct']:7d} {s['median_cost']:9.4f} {s['use_runs']:8d} {s['use_questions']:6d} {s['median_seconds']:6.1f} {s['median_turns']:5.1f}")
    lines.append("")
    for arm, v in result["verdicts"].items():
        lines.append(f"{arm:4s} (i) {v['i_correct_not_fewer']!s:5s} {v['correct_vs_baseline']:10s} (ii) {v['ii_median_cost_at_most_1.1x']!s:5s} {v['median_cost_vs_baseline']:20s} "
                     f"(iii) {v['iii_use_on_70_percent_of_questions']!s:5s} use {v['use_share']:.2f}  {'ADOPT' if v['adopt'] else 'correct non-use or no gain'}")
    c = result["carrying"]
    if c:
        lines.append(f"\ncarrying the four servers (A0b against A5, {c['questions']} questions): median cost {c['median_cost_A0b']:.4f} vs {c['median_cost_A5']:.4f} ({c['cost_change_percent']:+.1f} percent), "
                     f"correct {c['correct_A0b']} vs {c['correct_A5']}, median seconds {c['median_seconds_A0b']} vs {c['median_seconds_A5']}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="E1 decision rule over promptfoo result files.")
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--baseline", default="A0a")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    tasks = json.loads((C.HERE / "tasks.json").read_text(encoding="utf-8"))
    runs, faults = load_runs(args.results, tasks)
    for fault in faults:
        print("fault:", fault, file=sys.stderr)
    try:
        result = decide(runs, args.baseline)
    except ValueError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(render(result))
    if args.json:
        args.json.write_text(json.dumps({**result, "faults": faults}, indent=1) + "\n", encoding="utf-8")
    return 3 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
