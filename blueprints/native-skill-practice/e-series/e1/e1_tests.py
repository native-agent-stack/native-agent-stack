"""promptfoo test generator of E1: tests: [{path: file://e1_tests.py:create_tests, config: {repeats: 3}}]

Rows: one `preflight` row (graded by e1_assert.py:preflight: what a session has before any question: the four servers, or none for A5, and the directive, or none), then for each repeat and each frozen
question one `question` row (graded by e1_assert.py:correct). Repeats are explicit rows, as in the P1 harness, so a result carries its (question, repeat) pair; the order is repeat-major like the private
runner's. The vars hold the question text and its id; the gold stays in tasks.json and is read by the grader.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAX_REPEATS = 9

PREFLIGHT_PROMPT = (
    "Do not call any tool except ToolSearch, and do not read any file. Look only at the instructions and tools you were given at the start of this session. "
    "In the answer field write exactly two lines. Line 1 begins with `TOOLS:` and lists, separated by single spaces, the exact names of the MCP tools whose names contain `serena`, `semble`, "
    "`codebase-memory` or `jcodemunch` that you can see or find with ToolSearch, or reads `TOOLS: none`. Line 2 begins with `DIRECTIVE:` and gives the first sentence of the section titled "
    "`Code navigation` in your instructions, quoted verbatim, or reads `DIRECTIVE: NONE`. Leave citations empty.")


def load_tasks(path=None):
    return json.loads(Path(path or HERE / "tasks.json").read_text(encoding="utf-8"))


def create_tests(config=None):
    config = config or {}
    repeats = int(config.get("repeats", 3))
    if not 1 <= repeats <= MAX_REPEATS:
        raise ValueError(f"repeats must be 1 to {MAX_REPEATS}, got {repeats}")
    rows = [{"description": "preflight", "vars": {"question_id": "preflight", "question": PREFLIGHT_PROMPT, "repeat": 1},
             "assert": [{"type": "python", "value": "file://e1_assert.py:preflight", "metric": "preflight"}], "metadata": {"kind": "preflight"}}]
    for repeat in range(1, repeats + 1):
        for question in load_tasks()["questions"]:
            rows.append({"description": f"{question['id']} r{repeat}", "vars": {"question_id": question["id"], "question": question["prompt"], "repeat": repeat},
                         "assert": [{"type": "python", "value": "file://e1_assert.py:correct", "metric": "correct"}],
                         "metadata": {"kind": "question", "type": question["type"], "repeat": repeat}})
    return rows
