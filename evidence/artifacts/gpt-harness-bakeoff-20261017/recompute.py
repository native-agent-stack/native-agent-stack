"""Offline publication check; this never launches a model or writes to the raw runs.

Reference: python/cpython@v3.13.16 Lib/statistics.py (median), Lib/json and
Lib/unittest. Usage selectors follow the retained events at the harness pins
listed in the decision. Only completed usage events are summed, once each.
"""

import argparse
import json
import math
from pathlib import Path
import re
from statistics import median

ORDER = ("codex-exec", "pi", "opencode", "kilo", "oh-my-pi", "goose", "openhands", "deerflow")
INCLUSIVE = {"codex-exec", "deerflow", "goose", "openhands"}
HERE = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def two_runs(record):
    runs = record["per_run"]
    require(len(runs) == 2 and sorted(r["rep"] for r in runs) == [1, 2],
            "exactly two uniquely numbered runs (1 and 2) are required")
    return runs


def validate_scores(scores):
    """Derive every aggregate from complete runs, then reject stale summaries."""
    require(set(scores["harnesses"]) == set(ORDER), "eight named harnesses are required")
    derived = {}
    for harness in ORDER:
        derived[harness] = {}
        for task in ("T1", "T2"):
            stored = scores["harnesses"][harness][task]
            runs = two_runs(stored)
            for run in runs:
                require(type(run["reply_correct"]) is bool, "reply score must be boolean")
                require(type(run["state_and_tests_ok"]) is bool if task == "T2"
                        else run["state_and_tests_ok"] is None, "invalid state score")
                for key in ("wall_s", "tokens_in", "tokens_out"):
                    require(isinstance(run[key], (int, float)) and math.isfinite(run[key]) and run[key] >= 0,
                            "invalid measurement")
            row = {
                "of": len(runs),
                "correct": sum(r["reply_correct"] and (task == "T1" or r["state_and_tests_ok"]) for r in runs),
                "t2_file_and_tests_ok": sum(r["state_and_tests_ok"] for r in runs) if task == "T2" else None,
                "median_wall_s": round(median(r["wall_s"] for r in runs), 2),
                "median_tokens_in_plus_out": median(r["tokens_in"] + r["tokens_out"] for r in runs),
            }
            require(all(stored[key] == value for key, value in row.items()),
                    f"{harness} {task}: aggregate disagrees with per_run")
            derived[harness][task] = row
    return derived


def validate_usage(scores, usage):
    """Cache-normalize input, preserving each runtime's reported output counter."""
    validate_scores(scores)
    require(set(usage["harnesses"]) == set(ORDER), "usage must cover eight harnesses")
    medians = {}
    for harness in ORDER:
        record = usage["harnesses"][harness]
        require(record["input_includes_cached"] == (harness in INCLUSIVE), "wrong accounting class")
        normalized = []
        scored = {r["rep"]: r for r in scores["harnesses"][harness]["T2"]["per_run"]}
        for run in two_runs(record):
            require(all(run[k] >= 0 for k in ("tokens_in", "tokens_out", "tokens_cached")), "negative usage")
            require(all(run[k] == scored[run["rep"]][k] for k in ("tokens_in", "tokens_out")), "usage disagrees with scores")
            reply_correct = run["reply"] == {"changed_line": 77, "tests_ok": True}
            require(reply_correct == scored[run["rep"]]["reply_correct"], "reply disagrees with scores")
            uncached = run["tokens_in"] - (run["tokens_cached"] if harness in INCLUSIVE else 0)
            require(uncached >= 0, "cached input exceeds inclusive input")
            normalized.append(uncached + run["tokens_out"])
        medians[harness] = median(normalized)
    return medians


def final_object(text, task):
    keys = {"cited", "actual"} if task == "T1" else {"changed_line", "tests_ok"}
    for candidate in reversed(re.findall(r"\{[^{}]*\}", text)):
        try:
            obj = json.loads(candidate)
        except ValueError:
            continue
        if set(obj) == keys:
            return obj
    return None


def extract_run(root, harness, task, rep):
    """Return a small numeric/text extract, never a raw transcript or locator."""
    name = f"{task}-{rep}"
    base = root / harness
    text = ""
    if harness == "openhands":
        relative = f"{harness}/{name}/out.log"
        raw = (root / relative).read_text(encoding="utf-8")
        fields = json.loads(re.search(r"^USAGE: (.*)$", raw, re.M)[1])
        i, o, c = fields["in"], fields["out"], fields["cached"]
        text = json.loads(re.search(r"^FINAL_REPLY: (.*)$", raw, re.M)[1])
    elif harness == "goose":
        relative = f"{harness}/{name}/out.json"
        data = json.loads((root / relative).read_text(encoding="utf-8"))
        fields = data["metadata"]
        i, o, c = (fields.get(k, 0) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens"))
        text = "\n".join(p.get("text", "") for m in data["messages"] if m["role"] == "assistant" for p in m["content"])
    else:
        relative = f"{harness}/{name}" + (".events.jsonl" if harness == "codex-exec" else ".jsonl")
        rows = [json.loads(line) for line in (root / relative).read_text(encoding="utf-8").splitlines() if line.strip()]
        if harness == "codex-exec":
            fields = next(r["usage"] for r in reversed(rows) if r["type"] == "turn.completed")
            i, o, c = (fields[k] for k in ("input_tokens", "output_tokens", "cached_input_tokens"))
            text = "\n".join(r["item"]["text"] for r in rows if r.get("type") == "item.completed"
                             and r["item"].get("type") == "agent_message")
        elif harness in ("pi", "oh-my-pi"):
            messages = [r["message"] for r in rows if r.get("type") == "message_end" and r["message"].get("role") == "assistant"]
            i, o, c = (sum(m["usage"][k] for m in messages) for k in ("input", "output", "cacheRead"))
            text = "\n".join(p["text"] for m in messages for p in m["content"] if p.get("type") == "text")
        elif harness in ("opencode", "kilo"):
            fields = [r["part"]["tokens"] for r in rows if r.get("type") == "step_finish"]
            i, o = (sum(f[k] for f in fields) for k in ("input", "output"))
            c = sum(f["cache"]["read"] for f in fields)
            text = "\n".join(r["part"]["text"] for r in rows if r.get("type") == "text")
        else:
            # Each values event repeats the history: use the final snapshot only.
            messages = next(r["data"]["messages"] for r in reversed(rows) if r["type"] == "values")
            fields = [m["usage_metadata"] for m in messages if m.get("usage_metadata")]
            i, o = (sum(f[k] for f in fields) for k in ("input_tokens", "output_tokens"))
            c = sum(f.get("input_token_details", {}).get("cache_read", 0) for f in fields)
            text = next(m["content"] for m in reversed(messages) if m.get("type") == "ai")
    return {"rep": rep, "source": relative, "tokens_in": i, "tokens_out": o,
            "tokens_cached": c, "reply": final_object(text, task)}


def extract_t2(root):
    return {"task": "T2", "harnesses": {
        h: {"input_includes_cached": h in INCLUSIVE,
            "per_run": [extract_run(root, h, "T2", rep) for rep in (1, 2)]} for h in ORDER}}


def check_raw(root, scores, usage):
    require(extract_t2(root) == usage, "published T2 usage differs from retained logs")
    usage_count = timing_count = 0
    for harness in ORDER:
        for task in ("T1", "T2"):
            if harness == "codex-exec" and task == "T1":
                continue  # These event logs were not retained; do not reconstruct them.
            for run in scores["harnesses"][harness][task]["per_run"]:
                rep = run["rep"]
                actual = extract_run(root, harness, task, rep)
                require(all(actual[k] == run[k] for k in ("tokens_in", "tokens_out")), "raw usage mismatch")
                expected = {"cited": 76, "actual": 77} if task == "T1" else {"changed_line": 77, "tests_ok": True}
                require((actual["reply"] == expected) == run["reply_correct"], "raw reply mismatch")
                usage_count += 1
                base = root / harness
                name = f"{task}-{rep}"
                timing = None
                if harness in ("opencode", "deerflow", "kilo"):
                    timing = (base / (name + ".meta")).read_text(encoding="utf-8")
                elif harness == "goose":
                    timing = (base / name / "exit_wall.txt").read_text(encoding="utf-8")
                elif harness == "openhands":
                    timing = (base / name / "out.log").read_text(encoding="utf-8").split("\nexit=", 1)[1]
                if timing is not None:
                    exit_code, wall = re.findall(r"\d+(?:\.\d+)?", timing)
                    require(int(exit_code) == run["exit"] and round(float(wall), 2) == run["wall_s"], "raw timing mismatch")
                    timing_count += 1
    return {"usage_and_reply_runs_checked": usage_count, "timing_runs_checked": timing_count,
            "unretained": "Codex T1 events; Codex, pi and oh-my-pi independent timing receipts"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, help="read-only directory containing the original runs")
    parser.add_argument("--emit-t2-usage", action="store_true")
    args = parser.parse_args()
    if args.emit_t2_usage:
        require(args.raw_root is not None, "raw root required for extraction")
        print(json.dumps(extract_t2(args.raw_root), indent=2))
        return
    scores = json.loads((HERE / "SCORES.json").read_text(encoding="utf-8"))
    usage = json.loads((HERE / "T2-USAGE.json").read_text(encoding="utf-8"))
    derived = validate_scores(scores)
    result = {"status": "passed", "runs": sum(row["of"] for h in derived.values() for row in h.values()),
              "t2_uncached_in_plus_out_medians": validate_usage(scores, usage)}
    if args.raw_root:
        result["raw_checks"] = check_raw(args.raw_root, scores, usage)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
