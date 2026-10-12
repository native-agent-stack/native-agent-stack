#!/usr/bin/env python3
"""Grader for the E1 questions (a pure function, tested offline): grade(question, output) -> dict

`output` is the run's structured result: {"answer": str, "citations": [{"file": str, "line": int}], "functions": [str]}. A citation path is normalised by dropping a leading "./" and everything up to and including the
run's worktree or primary directory name ("/wt/" or "/primary/"). Rules, fixed in the preregistration:
  def      correct iff some citation equals the gold (file, line) exactly.
  refs     correct iff every gold call site is cited (recall 1.0) and at most 10% of the cited sites are not gold.
  explain  correct iff at least ceil(0.8 * |gold lines|) gold lines of the gold file are cited and at most 2 cited lines are not gold.
  callers  correct iff the set of named functions equals the gold set.
`wrong_tree` is True when a def or explain answer cites only locations that exist in the stale tree and not at the base (a stale-tree answer).

grade, norm, bare_name and cites are the grader of addendum 1 of the preregistration (deviation D1: bare_name); only this docstring and the self-test's default path differ from the private runner's copy.
"""
import math
import re


def norm(path):
    path = str(path or "").strip()
    path = re.sub(r"^.*?/(?:wt|primary)/", "", path)
    return re.sub(r"^\./", "", path)


def bare_name(name):
    """A caller named as `Class.method`, `module.function` or `function()` is the function the gold names by its bare AST name (deviation D1 of the pilot, 2026-10-12)."""
    name = str(name).strip().strip("`").strip()
    name = name[:-2] if name.endswith("()") else name
    return name.rsplit(".", 1)[-1]


def cites(output):
    out = []
    for c in (output or {}).get("citations") or []:
        try:
            out.append((norm(c.get("file")), int(c.get("line"))))
        except (TypeError, ValueError, AttributeError):
            continue
    return out


def grade(q, output):
    if not isinstance(output, dict):
        return {"correct": False, "reason": "no structured output", "wrong_tree": False}
    got = set(cites(output))
    gold = q["gold"]
    kind = q["type"]
    stale = {(f, ln) for f, ln in q.get("defined_at_stale", [])}
    if kind == "def":
        want = (gold["file"], gold["line"])
        return {"correct": want in got, "reason": f"cited {len(got)} location(s)", "wrong_tree": bool(got) and want not in got and bool(got & stale)}
    if kind == "refs":
        want = {(f, ln) for f, ln in gold["sites"]}
        hit = want & got
        extra = got - want
        ok = len(hit) == len(want) and len(extra) <= max(0, int(0.1 * len(got)))
        return {"correct": ok, "reason": f"recall {len(hit)}/{len(want)}, {len(extra)} extra of {len(got)}", "wrong_tree": False}
    if kind == "explain":
        want = {(gold["file"], ln) for ln in gold["lines"]}
        hit = want & got
        extra = got - want
        need = math.ceil(0.8 * len(want))
        return {"correct": len(hit) >= need and len(extra) <= 2, "reason": f"{len(hit)}/{len(want)} gold raise lines (need {need}), {len(extra)} extra", "wrong_tree": bool(got) and not hit and bool(got & stale)}
    if kind == "callers":
        want = set(gold["functions"])
        named = {bare_name(x) for x in (output.get("functions") or [])}
        return {"correct": named == want, "reason": f"named {len(named)}, gold {len(want)}, missing {sorted(want - named)}, extra {sorted(named - want)}", "wrong_tree": False}
    return {"correct": False, "reason": "unknown question type", "wrong_tree": False}


if __name__ == "__main__":  # offline self-test: python3 e1_grade.py [tasks json]
    import json
    import sys
    from pathlib import Path
    qs = {q["id"]: q for q in json.load(open(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("tasks.json")))["questions"]}
    bad = 0

    def check(cond, text):
        global bad
        bad += not cond
        print(("ok   " if cond else "FAIL ") + text)

    q = qs["p-def"]
    f, ln = q["gold"]["file"], q["gold"]["line"]
    check(grade(q, {"citations": [{"file": f"/var/tmp/x/wt/{f}", "line": ln}]})["correct"], "def: the gold location, with a worktree prefix, is correct")
    check(not grade(q, {"citations": [{"file": f, "line": ln + 1}]})["correct"], "def: an off-by-one line is wrong")
    check(not grade(q, None)["correct"], "def: no output is wrong")
    q = qs["p-refs"]
    sites = q["gold"]["sites"]
    check(grade(q, {"citations": [{"file": a, "line": b} for a, b in sites]})["correct"], "refs: all gold sites is correct")
    check(not grade(q, {"citations": [{"file": a, "line": b} for a, b in sites[:-1]]})["correct"], "refs: one missing site is wrong")
    check(not grade(q, {"citations": [{"file": a, "line": b} for a, b in sites] + [{"file": "x.py", "line": 1}] * 1 + [{"file": "y.py", "line": 2}]})["correct"], "refs: extra sites beyond 10% are wrong")
    q = qs["p-explain"]
    lines = q["gold"]["lines"]
    check(grade(q, {"citations": [{"file": q["gold"]["file"], "line": ln} for ln in lines]})["correct"], "explain: all raise lines is correct")
    check(not grade(q, {"citations": [{"file": q["gold"]["file"], "line": ln} for ln in lines[:2]]})["correct"], "explain: fewer than 80% is wrong")
    q = qs["p-callers"]
    check(grade(q, {"functions": q["gold"]["functions"]})["correct"], "callers: the gold set is correct")
    check(not grade(q, {"functions": q["gold"]["functions"][:-1]})["correct"], "callers: a missing function is wrong")
    qualified = ["SandboxLauncher.command" if x == "command" else x + "()" if x == "sandboxed" else x for x in q["gold"]["functions"]]
    check(grade(q, {"functions": qualified})["correct"], "callers: a method named with its class qualifier, or a function named with (), is the gold function (deviation D1)")
    nested = ["accept" if x == "boundary_self_check" else x for x in q["gold"]["functions"]]
    check(not grade(q, {"functions": nested})["correct"], "callers: a nested helper named in place of the enclosing function is wrong")
    raise SystemExit(1 if bad else 0)
