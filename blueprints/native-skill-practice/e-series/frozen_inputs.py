"""Fail-closed test generator of the E-series configs whose inputs are not frozen (E2 to E5).

tests: [{path: file://../frozen_inputs.py:create_tests, config: {experiment: e2}}]

It returns test rows only from <frozen dir>/<experiment>.json (the `frozen/` folder beside this file, or the folder named by $E_SERIES_FROZEN), and only when that file says status "frozen", names every input
the design needs, and each named input is a file whose sha256 still matches. Otherwise it raises, and promptfoo stops while loading the config, before any provider call, with the list of what is missing. The
frozen file is the experiment's preregistration receipt: it holds the rows themselves, so what runs is what was frozen. Work starts when its named inputs exist, never on a date.

Frozen file: {"experiment": "e2", "status": "frozen", "inputs": {"<name>": {"path": "<file, relative to the frozen folder or absolute>", "sha256": "<64 hex digits>"}}, "tests": [<promptfoo test rows>]}
"""
import hashlib
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

# What each experiment needs before it can run (invoke-gap cause table, section 7: proposed fixes, each gated by a paired run). The arms are the provider labels of its skeleton config.
DESIGNS = {
    "e2": {"title": "records retrieval", "arms": ["grep-status-quo", "qmd-directive", "aimemory-directive"], "inputs": ["questions", "qmd_collection", "directives"]},
    "e3": {"title": "headroom parity", "arms": ["direct", "headroom-proxy"], "inputs": ["tasks", "proxy"]},
    "e4": {"title": "autonomous skills", "arms": ["baseline", "fix7-sentence"], "inputs": ["tasks", "sentence", "skills"]},
    "e5": {"title": "unresolved triggers", "arms": ["natural"], "inputs": ["trigger_cases", "variants", "skills"]},
}


class FrozenInputsError(RuntimeError):
    pass


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_dir():
    return Path(os.environ.get("E_SERIES_FROZEN") or HERE / "frozen")


def load_frozen(experiment, directory=None):
    """The frozen test rows of `experiment`, or FrozenInputsError naming what is missing."""
    design = DESIGNS.get(experiment)
    if design is None:
        raise FrozenInputsError(f"unknown experiment {experiment!r}; the E-series has {', '.join(sorted(DESIGNS))}")
    folder = Path(directory) if directory else frozen_dir()
    path = folder / f"{experiment}.json"
    needs = ", ".join(design["inputs"])
    if not path.is_file():
        raise FrozenInputsError(f"{experiment} ({design['title']}) is not frozen: {path} does not exist. Inputs it needs: {needs}")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise FrozenInputsError(f"{path} is not valid JSON: {error}") from None
    problems = []
    if not isinstance(receipt, dict) or receipt.get("experiment") != experiment:
        problems.append(f"it does not name experiment {experiment}")
    elif receipt.get("status") != "frozen":
        problems.append(f"its status is {receipt.get('status')!r}, not 'frozen'")
    else:
        inputs = receipt.get("inputs") if isinstance(receipt.get("inputs"), dict) else {}
        for name in design["inputs"]:
            entry = inputs.get(name)
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256"))):
                problems.append(f"input {name} lacks a path and a 64-digit sha256")
                continue
            target = Path(entry["path"]) if os.path.isabs(entry["path"]) else folder / entry["path"]
            if not target.is_file():
                problems.append(f"input {name} ({entry['path']}) is not a file")
            elif sha256_of(target) != entry["sha256"]:
                problems.append(f"input {name} ({entry['path']}) no longer matches its sha256")
        rows = receipt.get("tests")
        if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
            problems.append("it holds no test rows")
    if problems:
        raise FrozenInputsError(f"{experiment} ({design['title']}) cannot start: " + "; ".join(problems) + f". Inputs it needs: {needs}")
    return receipt["tests"]


def create_tests(config=None):
    return load_frozen((config or {}).get("experiment"))
