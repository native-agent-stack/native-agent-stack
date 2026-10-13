#!/usr/bin/env python3
"""E1 decision rule (preregistration section 6, addendum 1) over promptfoo result files: e1_decide.py RESULTS.json [RESULTS.json ...] [--baseline A0a] [--json OUT] [--ungated] [--require-after-gate]

A result file is decided only if e1_run.py produced it behind a passing pre-flight of the root's current preparation (e1_gate.py: its <name>.gate record is present and matches, and no later pre-flight failed);
otherwise the run refuses (exit 2). --ungated reads files without that record for description only: the table is printed and no verdict is, and the JSON says so. --require-after-gate also asks for
a pre-flight made after each file that stands for the arms of that file's run (passed, this preparation, those arms covered, its result file unchanged: the start gate's own check; the preregistered gate after the last run).

Reads the `question` rows of promptfoo's `-o` files (the `preflight` row is not a measurement), regrades every stored answer with e1_grade.py as it is now, and takes cost, turns and seconds from the response and
the tool names from `response.metadata.toolCalls`. Per arm, over the questions it shares with the baseline arm:
  (i)   correct answers: the number of correct runs, against the baseline's over the same questions (an arm passes (i) when it is not fewer);
  (ii)  median cost: the median response cost, against the baseline's (passes when at most 1.1 times);
  (iii) code-navigation use: the share of questions on which at least half of the arm's repeats called a tool of the code-navigation servers (passes at 70 percent or more).
An arm is adopted as the default of a worktree workflow only when (i), (ii) and (iii) all pass; otherwise the outcome is "correct non-use or no gain". A5 (no server) is a cost and correctness reference, not an
adoption candidate. Also printed: use by run, the carrying cost of the servers (A0b against A5) and each arm's median seconds and turns. The statistics are descriptive. A run that ended in a provider error, or whose response has no usable cost (missing, not a finite number or negative: a missing cost must not read as a free run), is a
fault: it is listed, left out of the figures, and the exit status is 3 so that someone reads it before the figures are used; arms that do not hold the same (question, repeat) runs over the shared questions are refused (exit 2).
Leaving a run out can remove a whole question from the compared set (an arm whose only run of a question was lost is then compared over the other questions and can still pass), so a comparison from which a run of
either of its arms was left out gets no verdict: the table is printed, the verdict line says that the comparison is incomplete, the JSON holds `adopt: null` with the reason, and the carrying figure of A0b against A5 is
withheld the same way. Only a fault that left a run out does this; a replayed run keeps its first copy.
A (arm, question, repeat) that appears twice, across files or within one, is a fault: the first is kept and the exit status is 3, so a replayed file is read before its figures are used.
Exit 0 decided, 2 a refusal, 3 faults present.
"""
import argparse
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e1_common as C  # noqa: E402
import e1_gate  # noqa: E402
import e1_grade  # noqa: E402
from e1_assert import parse_output  # noqa: E402

PROVIDER_ERROR = 2  # ResultFailureReason.ERROR (promptfoo/promptfoo@30949931ee90, src/types/index.ts L380-L386); ASSERT is 1
COST_FACTOR = 1.1
USE_SHARE = 0.7


class Fault(str):
    """A fault: a one-line text that also says which (arm, question, repeat) it concerns and whether it left that run out of the figures (`lost`), so that a comparison that lost a run can be told from one that did not."""

    def __new__(cls, text, arm=None, question=None, repeat=None, lost=False):
        self = super().__new__(cls, text)
        self.arm, self.question, self.repeat, self.lost = arm, question, repeat, lost
        return self


def lost_runs(faults):
    """The (arm, question, repeat) identities of the runs the faults left out."""
    return [(f.arm, f.question, f.repeat) for f in faults if getattr(f, "lost", False)]


def load_runs(paths, tasks):
    """(runs, faults) from promptfoo result files; a run is a dict, a fault is a one-line text (a Fault, which also names the run and whether it was left out: lost_runs)."""
    questions = {q["id"]: q for q in tasks["questions"]}
    runs, faults, seen = [], [], set()
    for path in paths:
        for item in json.loads(Path(path).read_text(encoding="utf-8"))["results"]["results"]:
            if ((item.get("testCase") or {}).get("metadata") or {}).get("kind") != "question":
                continue
            arm = (item.get("provider") or {}).get("label")
            qid = (item.get("vars") or {}).get("question_id")
            response = item.get("response") or {}
            repeat = str((item.get("vars") or {}).get("repeat"))
            tag = f"{arm} {qid} r{(item.get('vars') or {}).get('repeat')}"
            if qid not in questions or arm not in C.ARMS:
                faults.append(f"{tag}: an arm or question this config does not define")
                continue
            if item.get("failureReason") == PROVIDER_ERROR or response.get("error"):  # an assertion that rejects an answer is failureReason 1 and a result; its text is also in item["error"]
                faults.append(Fault(f"{tag}: provider error ({str(response.get('error') or item.get('error'))[:80]})", arm, qid, repeat, lost=True))
                continue
            cost = response.get("cost")
            if not isinstance(cost, (int, float)) or isinstance(cost, bool) or not math.isfinite(cost) or cost < 0:
                faults.append(Fault(f"{tag}: the response has no usable cost ({type(cost).__name__}); the run is left out", arm, qid, repeat, lost=True))   # a missing cost must not read as a free run (criterion ii)
                continue
            if (arm, qid, str((item.get("vars") or {}).get("repeat"))) in seen:
                faults.append(Fault(f"{tag}: the same run appears twice (a replayed result file?); the first is kept", arm, qid, repeat))
                continue
            seen.add((arm, qid, str((item.get("vars") or {}).get("repeat"))))
            meta = response.get("metadata") or {}
            names = [c.get("name") for c in meta.get("toolCalls") or [] if isinstance(c, dict)]
            nav = [n for n in names if isinstance(n, str) and any(n.startswith(f"mcp__{s}__") for s in C.CODE_NAV_SERVERS)]
            millis = meta.get("durationMs") if isinstance(meta.get("durationMs"), (int, float)) else item.get("latencyMs")
            runs.append({"arm": arm, "q": qid, "repeat": str((item.get("vars") or {}).get("repeat")), "correct": bool(e1_grade.grade(questions[qid], parse_output(response.get("output")))["correct"]),
                         "cost": float(cost), "turns": meta.get("numTurns") or 0, "seconds": (millis or 0) / 1000.0, "nav": bool(nav)})
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


def same_samples(candidate, other, questions, names):
    """A refusal text unless both arms hold the same (question, repeat) runs over `questions`: equal counts do not make samples comparable (three repeats of one question and one of another are not one of each)."""
    def pairs(runs):
        return Counter((r["q"], r.get("repeat")) for r in runs if r["q"] in questions)
    a, b = pairs(candidate), pairs(other)
    if a == b:
        return None
    extra, missing = sorted((a - b).elements()), sorted((b - a).elements())
    return f"{names[0]} and {names[1]} do not hold the same (question, repeat) runs over their shared questions (only in {names[0]}: {extra[:3]}; only in {names[1]}: {missing[:3]}): the figures are not comparable"


def withheld(lost, arms):
    """A text when a run of one of `arms` was left out as a fault (`lost`: (arm, question, repeat) identities), else None: the comparison of those arms is then incomplete and gets no verdict."""
    gone = sorted(f"{arm} {qid} r{repeat}" for arm, qid, repeat in lost if arm in arms)
    if not gone:
        return None
    return f"{len(gone)} run(s) left out as faults ({', '.join(gone[:3])}{', ...' if len(gone) > 3 else ''}): the comparison is incomplete and no verdict is given"


def decide(runs, baseline="A0a", lost=()):
    """The table, the verdicts and the carrying figure of `runs`. `lost` names the runs that faults left out: a comparison with one of its arms' runs lost gets `adopt: None` and the reason, not a verdict."""
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
        reason = withheld(lost, (arm, baseline))
        if reason:   # before the sample check: a lost run makes the samples differ, and it can also remove a whole question from `common`
            verdicts[arm] = {"adopt": None, "withheld": reason}
            continue
        base = summary(by_arm[baseline], common)
        refusal = same_samples(by_arm[arm], by_arm[baseline], common, (arm, baseline))
        if refusal:
            raise ValueError(refusal)
        i = rows[arm]["correct"] >= base["correct"]
        ii = rows[arm]["median_cost"] <= COST_FACTOR * base["median_cost"]
        iii = rows[arm]["use_share"] >= USE_SHARE
        verdicts[arm] = {"i_correct_not_fewer": i, "ii_median_cost_at_most_1.1x": ii, "iii_use_on_70_percent_of_questions": iii, "adopt": i and ii and iii,
                         "correct_vs_baseline": f"{rows[arm]['correct']} vs {base['correct']}", "median_cost_vs_baseline": f"{rows[arm]['median_cost']:.4f} vs {base['median_cost']:.4f}",
                         "use_share": round(rows[arm]["use_share"], 3)}
    carrying = None
    if "A0b" in by_arm and "A5" in by_arm and withheld(lost, ("A0b", "A5")):
        carrying = {"withheld": withheld(lost, ("A0b", "A5"))}
    elif "A0b" in by_arm and "A5" in by_arm:
        shared = {r["q"] for r in by_arm["A0b"]} & {r["q"] for r in by_arm["A5"]}
        refusal = same_samples(by_arm["A0b"], by_arm["A5"], shared, ("A0b", "A5"))
        if refusal:
            raise ValueError(refusal)
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
        if v.get("withheld"):
            lines.append(f"{arm:4s} no verdict: {v['withheld']}")
            continue
        lines.append(f"{arm:4s} (i) {v['i_correct_not_fewer']!s:5s} {v['correct_vs_baseline']:10s} (ii) {v['ii_median_cost_at_most_1.1x']!s:5s} {v['median_cost_vs_baseline']:20s} "
                     f"(iii) {v['iii_use_on_70_percent_of_questions']!s:5s} use {v['use_share']:.2f}  {'ADOPT' if v['adopt'] else 'correct non-use or no gain'}")
    c = result["carrying"]
    if c and c.get("withheld"):
        lines.append(f"\ncarrying the four servers (A0b against A5): not given, {c['withheld']}")
    elif c:
        lines.append(f"\ncarrying the four servers (A0b against A5, {c['questions']} questions): median cost {c['median_cost_A0b']:.4f} vs {c['median_cost_A5']:.4f} ({c['cost_change_percent']:+.1f} percent), "
                     f"correct {c['correct_A0b']} vs {c['correct_A5']}, median seconds {c['median_seconds_A0b']} vs {c['median_seconds_A5']}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="E1 decision rule over promptfoo result files.")
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--baseline", default="A0a")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--ungated", action="store_true", help="read files without a gate record, for description only: no verdict is printed")
    parser.add_argument("--require-after-gate", action="store_true", help="also require a passing pre-flight made after each result file")
    args = parser.parse_args(argv)
    problems = [problem for path in args.results for problem in e1_gate.verify_result(path, require_after=args.require_after_gate)]
    if problems and not args.ungated:
        for problem in problems:
            print(f"refused: {problem}", file=sys.stderr)
        return 2
    tasks = json.loads((C.HERE / "tasks.json").read_text(encoding="utf-8"))
    runs, faults = load_runs(args.results, tasks)
    for fault in faults:
        print("fault:", fault, file=sys.stderr)
    try:
        result = decide(runs, args.baseline, lost_runs(faults))
    except ValueError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    ungated = bool(problems)
    if ungated:
        result = {**result, "verdicts": {}, "ungated": problems}
    print(render(result))
    if ungated:
        print("UNGATED: " + "; ".join(problems) + "; no verdict is given", file=sys.stderr)
    if args.json:
        args.json.write_text(json.dumps({**result, "faults": faults}, indent=1) + "\n", encoding="utf-8")
    return 3 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
