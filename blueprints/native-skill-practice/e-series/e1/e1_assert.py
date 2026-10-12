"""promptfoo Python assertions of E1 (assert: type python, value file://e1_assert.py:<function>): each takes (output, context) and returns a GradingResult dict.

correct    the answer of a `question` row graded by e1_grade.grade against the gold in tasks.json (rules fixed in the preregistration).
preflight  what the session had before any question, per arm (the label of the provider that answered): the four servers connected (A5: none) and the directive delivered (the arms that carry one) or absent.
           The client's init record is not part of the provider's response, so this row is how a silent server failure or an undelivered directive is told apart from a real null.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e1_grade  # noqa: E402
from e1_common import ARMS, DIRECTIVE_FIRST_SENTENCE, HERE, SERVERS  # noqa: E402

MCP_NAME = re.compile(r"mcp__([A-Za-z0-9_-]+?)__[A-Za-z0-9_-]+")
QUIET_TOOLS = {"ToolSearch", "StructuredOutput"}  # any other tool call could have supplied the answer from a file instead of the session's context


def questions():
    return {q["id"]: q for q in json.loads((HERE / "tasks.json").read_text(encoding="utf-8"))["questions"]}


def parse_output(output):
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except ValueError:
            return None
    return output if isinstance(output, dict) else None


def result(ok, reason):
    return {"pass": bool(ok), "score": 1 if ok else 0, "reason": reason}


def correct(output, context):
    question_id = (context.get("vars") or {}).get("question_id")
    question = questions().get(question_id)
    if question is None:
        return result(False, f"unknown question id {question_id!r}")
    graded = e1_grade.grade(question, parse_output(output))
    return result(graded["correct"], graded["reason"])


def tool_names(context):
    calls = ((context.get("providerResponse") or {}).get("metadata") or {}).get("toolCalls") or []
    return [c.get("name") for c in calls if isinstance(c, dict)]


def lines_of(answer):
    found = {}
    for line in str(answer).splitlines():
        for key in ("TOOLS", "DIRECTIVE"):
            if key not in found and line.strip().startswith(key + ":"):
                found[key] = line.strip()[len(key) + 1:].strip()
    return found


def squash(text):
    return re.sub(r"\s+", " ", str(text).replace(chr(0x2019), "'").strip().strip("`\"' ")).lower()


def check_preflight(arm, answer, calls):
    """(ok, reason) for one arm's answer to the preflight prompt and the tool names it called."""
    spec = ARMS.get(arm)
    if spec is None:
        return False, f"unknown arm {arm!r}"
    problems = []
    other = sorted({c for c in calls if c not in QUIET_TOOLS})
    if other:
        problems.append("tools other than ToolSearch were called (" + ", ".join(str(c) for c in other) + "), so the answer may come from a file")
    found = lines_of(answer)
    if "TOOLS" not in found or "DIRECTIVE" not in found:
        return False, "the answer lacks a TOOLS: line or a DIRECTIVE: line"
    seen = {m.group(1) for m in MCP_NAME.finditer(found["TOOLS"])}
    if spec["servers"]:
        missing = [s for s in SERVERS if s not in seen]
        if missing:
            problems.append("servers without a listed tool: " + ", ".join(missing))
    elif seen:
        problems.append("servers listed for an arm with none: " + ", ".join(sorted(seen)))
    expected = DIRECTIVE_FIRST_SENTENCE.get(spec["directive"]) if spec["directive"] else None
    quoted = squash(found["DIRECTIVE"])
    if expected:
        if squash(expected) not in quoted:
            problems.append("the directive's first sentence was not quoted")
    elif quoted.rstrip(".") != "none":
        problems.append("a directive was quoted for an arm that carries none")
    return (not problems), ("; ".join(problems) if problems else "servers and directive as the arm defines")


def preflight(output, context):
    arm = (context.get("provider") or {}).get("label")
    parsed = parse_output(output)
    if parsed is None:
        return result(False, "no structured output")
    return result(*check_preflight(arm, parsed.get("answer", ""), tool_names(context)))
