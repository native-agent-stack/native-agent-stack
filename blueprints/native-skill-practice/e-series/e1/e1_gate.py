"""The pre-flight gate of E1: a question run starts only behind a passing pre-flight of the same prepared root, and a result file is decided only if it was produced behind one.

e1_run.py --preflight reads the result file promptfoo wrote, not promptfoo's exit status, to decide whether the pre-flight passed: the status can be set to 0 by PROMPTFOO_FAILED_TEST_EXIT_CODE or
PROMPTFOO_PASS_RATE_THRESHOLD (promptfoo/promptfoo@30949931ee90 src/node/doEval.ts L1271-L1286). It writes <root>/out/preflight-<stamp>.gate, a JSON record that says whether every requested arm's row passed, for
which preparation of the root (the sha256 of manifest.json, which holds a fresh `generation` on every prepare) and from which result file (its sha256). e1_run.py --questions starts promptfoo only when the newest
such record passed, belongs to this preparation and covers the requested arms; it then writes <root>/out/questions-<stamp>.gate, which names that record and the result file's sha256. e1_decide.py refuses a
result file without a record that still matches, so an unmet gate, an older preparation, a replayed or edited file and a run that a later failed pre-flight voids cannot become a result. Standard library only.
ASCII only.
"""
import hashlib
import json
from pathlib import Path

import e1_common as C

SCHEMA = 1
SUFFIX = ".gate"          # not .json: the documented `questions-*.json` glob selects result files only


class GateError(Exception):
    """A refusal of the gate. The message is fixed text built from names and counts, safe to print."""


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp_of(path):
    """The timestamp in a name such as preflight-20261012T184408Z.gate or questions-20261012T184816Z.json."""
    return Path(path).name.split("-", 1)[1].split(".", 1)[0]


def preflight_outcome(result_path, arms):
    """(ok, reasons) from promptfoo's result file: every requested arm has exactly one pre-flight row, and it passed (assertion passed, no error, failure reason none); no other arm has one."""
    try:
        items = json.loads(Path(result_path).read_text(encoding="utf-8"))["results"]["results"]
        if not isinstance(items, list):
            raise TypeError
    except (OSError, ValueError, KeyError, TypeError):
        return False, ["promptfoo wrote no readable result file"]
    rows = {}
    for item in items:
        if isinstance(item, dict) and ((item.get("testCase") or {}).get("metadata") or {}).get("kind") == "preflight":
            rows.setdefault((item.get("provider") or {}).get("label"), []).append(item)
    reasons = []
    for arm in arms:
        found = rows.get(arm, [])
        if len(found) != 1:
            reasons.append(f"{arm}: {len(found)} pre-flight rows, expected 1")
            continue
        item = found[0]
        failed = []
        if (item.get("gradingResult") or {}).get("pass") is not True:
            failed.append("the assertion did not pass")
        if item.get("failureReason", 0) != 0:
            failed.append(f"failure reason {item.get('failureReason')}")
        if (item.get("response") or {}).get("error"):
            failed.append("the provider answered with an error")
        if failed:
            reasons.append(f"{arm}: " + ", ".join(failed))
    extra = sorted(str(arm) for arm in rows if arm not in arms)
    if extra:
        reasons.append("pre-flight rows of arms that were not asked for: " + ", ".join(extra))
    return not reasons, reasons


def record_preflight(out_dir, stamp, manifest_path, arms, result_path, status):
    """Write <out_dir>/preflight-<stamp>.gate for a pre-flight whose promptfoo exit status was `status`; returns (path, passed, reasons). A pre-flight passes only if the status is 0 and the result file shows it."""
    ok, reasons = preflight_outcome(result_path, arms)
    if status != 0:
        reasons = [f"promptfoo exited {status}", *reasons]
    result = Path(result_path)
    record = {"schema": SCHEMA, "kind": "preflight", "harness": C.HARNESS, "passed": ok and status == 0, "arms": list(arms), "promptfoo_status": status, "manifest_sha256": sha256_file(manifest_path),
              "result": result.name, "result_sha256": sha256_file(result) if result.is_file() else None, "reasons": reasons}
    path = Path(out_dir) / f"preflight-{stamp}{SUFFIX}"
    path.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    return path, record["passed"], reasons


def read_record(path, kind):
    try:
        record = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise GateError(f"{Path(path).name} is not readable JSON") from None
    if not isinstance(record, dict) or record.get("schema") != SCHEMA or record.get("kind") != kind or record.get("harness") != C.HARNESS:
        raise GateError(f"{Path(path).name} is not a {kind} gate record of this harness")
    return record


def preflight_records(out_dir):
    return sorted(Path(out_dir).glob("preflight-*" + SUFFIX))


def require_preflight(root, arms):
    """The newest pre-flight record of the root, or GateError: it must have passed, belong to the root's current preparation, cover every arm asked for and still match the result file it was made from."""
    root = Path(root)
    records = preflight_records(root / "out")
    if not records:
        raise GateError("no pre-flight has run in this root: run e1_run.py --preflight first")
    newest = records[-1]
    record = read_record(newest, "preflight")
    if not record.get("passed"):
        raise GateError(f"the newest pre-flight ({newest.name}) did not pass ({'; '.join(record.get('reasons') or ['no reason recorded'])}): fix the cause and run it again")
    if record.get("manifest_sha256") != sha256_file(root / "manifest.json"):
        raise GateError(f"the newest pre-flight ({newest.name}) was made for another preparation of this root: run it again")
    missing = [arm for arm in arms if arm not in (record.get("arms") or [])]
    if missing:
        raise GateError(f"the newest pre-flight ({newest.name}) did not cover arm(s) {', '.join(missing)}: run it for them")
    result = root / "out" / str(record.get("result"))
    if not result.is_file() or sha256_file(result) != record.get("result_sha256"):
        raise GateError(f"the result file of the newest pre-flight ({newest.name}) is gone or has changed")
    return newest


def write_questions_record(result_path, gate_path, manifest_path, arms, ids, repeats, status):
    """Write <result stem>.gate beside a question result file: the pre-flight it ran behind, the preparation, what was asked for, and the result file's sha256."""
    result = Path(result_path)
    record = {"schema": SCHEMA, "kind": "questions", "harness": C.HARNESS, "manifest_sha256": sha256_file(manifest_path), "preflight": Path(gate_path).name, "preflight_sha256": sha256_file(gate_path),
              "arms": list(arms), "ids": list(ids), "repeats": repeats, "promptfoo_status": status, "result": result.name, "result_sha256": sha256_file(result)}
    path = result.with_name(result.stem + SUFFIX)
    path.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    return path


def verify_result(result_path, require_after=False):
    """Problems (texts; none means the file was produced behind a passing pre-flight of this root's current preparation, is unchanged, and no pre-flight after it failed). With `require_after`, a passing
    pre-flight made after the run is also needed (the preregistered gate after the last run)."""
    path = Path(result_path).resolve()
    root = path.parent.parent
    if path.parent.name != "out" or not (root / "manifest.json").is_file():
        return [f"{path.name} is not in the out directory of a prepared root"]
    sidecar = path.with_name(path.stem + SUFFIX)
    if not sidecar.is_file():
        return [f"{path.name} has no gate record ({sidecar.name}): it was not produced by e1_run.py behind a passing pre-flight"]
    try:
        record = read_record(sidecar, "questions")
        if record.get("result") != path.name or record.get("result_sha256") != sha256_file(path):
            return [f"{path.name} is not the file its gate record describes (it has changed)"]
        if record.get("manifest_sha256") != sha256_file(root / "manifest.json"):
            return [f"{path.name} was produced in an earlier preparation of this root"]
        gate = root / "out" / str(record.get("preflight"))
        if not gate.is_file() or sha256_file(gate) != record.get("preflight_sha256"):
            return [f"the pre-flight record that {path.name} ran behind ({record.get('preflight')}) is gone or has changed"]
        if not read_record(gate, "preflight").get("passed"):
            return [f"{path.name} ran behind a pre-flight that did not pass"]
        later = [p for p in preflight_records(root / "out") if stamp_of(p) > stamp_of(path)]
        failed = [p.name for p in later if not read_record(p, "preflight").get("passed")]
        if failed:
            return [f"a pre-flight after {path.name} did not pass ({failed[0]}): the runs since the last passing pre-flight are void"]
        if require_after and not later:
            return [f"no pre-flight after {path.name}: the gate after the last run is part of the protocol"]
    except GateError as error:
        return [str(error)]
    return []
