"""Structural qualification controls for the complete ledger-history call path."""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATHS = {"fs": "scripts/final_stack.py", "sl": "scripts/saturation_ledger.py",
         "host": "scripts/host_receipts.py", "catalog": "scripts/catalog_decisions.py"}
ALIASES = {"saturation_ledger": "sl", "host_receipts": "host"}
FIELDS = {"date", "day", "days", "today", "checked_at", "verdict_day"}


def ordering_scope(trees):
    functions = {}
    for module, tree in trees.items():
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                functions[module, node.name] = node
            elif isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef):
                        functions[module, node.name + "." + method.name] = method
    seed = ("fs", "qualify_final_history")
    assert seed in functions, "the reviewed qualification entry point must exist"
    pending, seen = [seed], set()
    while pending:
        key = pending.pop()
        if key in seen:
            continue
        seen.add(key)
        function = functions[key]
        for call in ast.walk(function):
            reference = call.func if isinstance(call, ast.Call) else call
            target = None
            if isinstance(reference, ast.Name):
                local = (key[0], reference.id)
                target = local if local in functions else None
                if key[0] == "fs" and reference.id in ("safe_file", "unique_json"):
                    target = ("catalog", reference.id)
            elif isinstance(reference, ast.Attribute) and isinstance(reference.value, ast.Name):
                owner = reference.value.id
                if owner in ALIASES:
                    target = (ALIASES[owner], reference.attr)
                elif owner == "sources":
                    target = ("fs", "Sources." + reference.attr)
            # Native integrity is a prerequisite over the whole ledger, not
            # an ordering policy or a filtered source of eligible events.
            if target == ("sl", "check_ledger"):
                continue
            if target in functions and target not in seen:
                pending.append(target)
    assert len(seen) > 10, "the qualification scope cannot pass vacuously"
    return {key: functions[key] for key in seen}


def event_date_violations(trees):
    scopes = ordering_scope(trees)
    date_functions = set()

    def analyze(key, function):
        failures = []
        tainted = set()

        def date_value(node):
            for child in ast.walk(node):
                if isinstance(child, ast.Name) and (child.id in tainted or child.id in date_functions
                                                   or set(child.id.split("_")) & FIELDS):
                    return True
                if isinstance(child, ast.Attribute) and (child.attr in FIELDS or child.attr in date_functions):
                    return True
                if isinstance(child, ast.Constant) and isinstance(child.value, str) and child.value in FIELDS:
                    return True
            return False

        for _ in range(len(list(ast.walk(function)))):
            previous = set(tainted)
            for node in ast.walk(function):
                if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None and date_value(node.value):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    tainted.update(target.id for target in targets if isinstance(target, ast.Name)
                                   and not isinstance(node.value, (ast.Dict, ast.List, ast.Tuple, ast.Set)))
            if previous == tainted:
                break
        for node in ast.walk(function):
            if isinstance(node, ast.Compare) and date_value(node):
                failures.append((key, node.lineno))
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ("sorted", "min", "max")):
                keys = [keyword.value for keyword in node.keywords if keyword.arg == "key"]
                values = keys or node.args
                if any(date_value(value) for value in values):
                    failures.append((key, node.lineno))
        returns_date = any(isinstance(node, ast.Return) and node.value is not None
                           and not isinstance(node.value, (ast.Dict, ast.List, ast.Tuple, ast.Set))
                           and date_value(node.value) for node in ast.walk(function))
        return failures, returns_date

    for _ in range(len(scopes) + 1):
        previous = set(date_functions)
        for key, function in scopes.items():
            if analyze(key, function)[1]:
                date_functions.add(key[1].split(".")[-1])
        if previous == date_functions:
            break
    return [failure for key, function in scopes.items() for failure in analyze(key, function)[0]]


def source_trees():
    return {name: ast.parse((ROOT / path).read_text()) for name, path in PATHS.items()}


class QualificationOrderingOracleTests(unittest.TestCase):
    def test_complete_history_qualification_scope_uses_no_calendar_ordering(self):
        trees = source_trees()
        scope = ordering_scope(trees)
        for required in (("fs", "retained_final_reference"), ("sl", "material_pending"),
                         ("host", "normalize_repository"), ("fs", "Sources.json")):
            self.assertIn(required, scope)
        self.assertEqual(event_date_violations(trees), [])

    def test_oracle_rejects_getters_aliases_sort_min_max_and_delegated_helpers(self):
        mutations = (
            'ignored = sweep.get("date") <= baseline.get("date")',
            'ignored = sorted(later, key=lambda sweep: sweep.get("date"))',
            'ignored = min(later, key=lambda sweep: sweep["checked_at"])',
            'ignored = max(later, key=lambda sweep: sweep.day)',
            'event_time = sweep.get("date")\nignored = event_time > baseline.get("date")',
        )
        for statement in mutations:
            with self.subTest(statement=statement):
                trees = source_trees()
                target = next(n for n in trees["fs"].body if isinstance(n, ast.FunctionDef)
                              and n.name == "final_reopened_by")
                target.body.extend(ast.parse(statement).body)
                self.assertTrue(event_date_violations(trees))
        trees = source_trees()
        helper = ast.parse('def delegated_ordering(sweep):\n return sweep.get("date") > sweep.get("checked_at")').body[0]
        trees["fs"].body.append(helper)
        target = next(n for n in trees["fs"].body if isinstance(n, ast.FunctionDef)
                      and n.name == "qualify_final_history")
        target.body.append(ast.parse('delegated_ordering(ledger)').body[0])
        self.assertTrue(event_date_violations(trees))
        trees = source_trees()
        trees["fs"].body.extend(ast.parse('def history_key(sweep):\n return sweep.get("date")').body)
        target = next(n for n in trees["fs"].body if isinstance(n, ast.FunctionDef)
                      and n.name == "qualify_final_history")
        target.body.append(ast.parse('sorted(covering, key=history_key)').body[0])
        self.assertTrue(event_date_violations(trees))

    def test_missing_qualification_scope_cannot_pass(self):
        trees = source_trees()
        trees["fs"].body = [node for node in trees["fs"].body
                             if not isinstance(node, ast.FunctionDef) or node.name != "qualify_final_history"]
        with self.assertRaisesRegex(AssertionError, "entry point must exist"):
            event_date_violations(trees)
