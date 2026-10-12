"""E-series promptfoo configs (blueprints/native-skill-practice/e-series): the E1 config against its constants, the grader, the test generator, the assertions, the decision rule, the prepare and run
scripts on a scratch repository, and the fail-closed generator of E2 to E5.

Standard library only (PyYAML for the config-structure tests when installed, promptfoo 0.124.0 or newer for the integration tests when installed; each skips otherwise). No test calls a model or reads a key.
Every behaviour is paired with a negative control in the same test or in a sibling, as docs/acceptance-evidence-policy.md asks.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
ES = ROOT / "blueprints" / "native-skill-practice" / "e-series"
E1 = ES / "e1"
for folder in (ES, E1):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import e1_assert  # noqa: E402
import e1_common as C  # noqa: E402
import e1_decide  # noqa: E402
import e1_grade  # noqa: E402
import e1_prepare  # noqa: E402
import e1_run  # noqa: E402
import e1_tests  # noqa: E402
import frozen_inputs as F  # noqa: E402

try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

CREDENTIAL_RUNNER = ROOT / "tools" / "credentials" / "credential_run.py"
TASKS = json.loads((E1 / "tasks.json").read_text(encoding="utf-8"))
QUESTIONS = {q["id"]: q for q in TASKS["questions"]}
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith(("PROMPTFOO_", "E_SERIES_"))}


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def promptfoo_binary():
    found = os.environ.get("PROMPTFOO_BIN") or shutil.which("promptfoo")
    if not found:
        return None
    try:
        text = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=60, env={**CLEAN_ENV, "PROMPTFOO_DISABLE_UPDATE": "1"}).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    version = next((line.strip() for line in text.splitlines() if re.fullmatch(r"\d+\.\d+\.\d+", line.strip())), None)
    if version is None or e1_prepare.version_tuple(version) < e1_prepare.version_tuple(C.PROMPTFOO_MINIMUM):
        return None
    return found


PROMPTFOO = promptfoo_binary()


def good_output(question):
    """An answer the grader accepts for `question`."""
    gold, kind = question["gold"], question["type"]
    if kind == "def":
        return {"answer": "x", "citations": [{"file": gold["file"], "line": gold["line"]}]}
    if kind == "refs":
        return {"answer": "x", "citations": [{"file": f, "line": ln} for f, ln in gold["sites"]]}
    if kind == "explain":
        return {"answer": "x", "citations": [{"file": gold["file"], "line": ln} for ln in gold["lines"]]}
    return {"answer": "x", "citations": [], "functions": list(gold["functions"])}


def promptfoo_item(arm, qid, repeat, output, cost=0.05, calls=("Grep",), turns=3, millis=2000, kind="question", error=None):
    item = {"provider": {"id": "anthropic:claude-agent-sdk", "label": arm}, "vars": {"question_id": qid, "repeat": str(repeat)}, "testCase": {"metadata": {"kind": kind}},
            "response": {"output": output, "cost": cost, "metadata": {"toolCalls": [{"name": n} for n in calls], "numTurns": turns, "durationMs": millis}}, "latencyMs": millis + 5,
            "gradingResult": {"pass": True}, "failureReason": 0}
    if error:
        item["error"] = error
        item["response"]["error"] = error
        item["failureReason"] = 2
    return item


def write_results(path: Path, items) -> Path:
    path.write_text(json.dumps({"evalId": "eval-test", "results": {"version": 3, "results": items}}), encoding="utf-8")
    return path


class InputsTests(unittest.TestCase):
    def test_tasks_file_is_the_one_the_preregistration_froze(self):
        digest = sha256_bytes(E1 / "tasks.json")
        self.assertEqual(digest, "9d2727ad3ba5cb9f05dcfff70efcdf07aaf4908e800988a197a576bf1c1a7109")
        self.assertTrue(digest.startswith("9d2727ad3ba5cb9f"))  # the sixteen digits recorded in the preregistration before the first run

    def test_twelve_questions_three_of_each_type_with_a_gold_of_the_right_shape(self):
        self.assertRegex(TASKS["base"], r"^[0-9a-f]{40}$")
        self.assertRegex(TASKS["stale"], r"^[0-9a-f]{40}$")
        self.assertNotEqual(TASKS["base"], TASKS["stale"])
        self.assertEqual(len(TASKS["questions"]), 12)
        self.assertEqual(len(QUESTIONS), 12)
        kinds = {}
        for q in TASKS["questions"]:
            kinds.setdefault(q["type"], []).append(q["id"])
            gold = q["gold"]
            self.assertIn("`" + q["symbol"] + "`", q["prompt"])
            if q["type"] == "def":
                self.assertEqual(set(gold), {"file", "line"})
            elif q["type"] == "refs":
                self.assertTrue(gold["sites"] and all(len(s) == 2 for s in gold["sites"]))
            elif q["type"] == "explain":
                self.assertTrue(gold["file"] and gold["lines"])
            else:
                self.assertTrue(gold["functions"] and gold["sites"])
        self.assertEqual({k: len(v) for k, v in kinds.items()}, {"def": 3, "refs": 3, "explain": 3, "callers": 3})
        self.assertEqual({"p-def", "p-refs", "p-explain", "p-callers"} - set(QUESTIONS), set())

    def test_the_two_directive_files_are_the_paragraphs_the_runner_appended(self):
        expected = {"serena": "ee7e592e7ebae0d4a764f57af1916799a18d65ca82ae4c85c1d31f9084e0b149", "path": "e9b5591039d0b32a059aabd17d5db260b08995a91aeeeb272e1c1854c1a29ef6"}
        for name, digest in expected.items():
            path = E1 / "directives" / f"{name}.md"
            self.assertEqual(sha256_bytes(path), digest, name)
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("## Code navigation\n\n"))
            first = text.split("\n\n", 1)[1].split(". ", 1)[0] + "."
            self.assertEqual(first, C.DIRECTIVE_FIRST_SENTENCE[name])
        self.assertNotEqual(*expected.values())

    def test_the_repository_root_is_found_from_the_folder(self):
        self.assertEqual(C.REPO_ROOT, ROOT)
        self.assertEqual(C.find_repo_root(), ROOT)

    def test_the_constants_are_the_preregistered_ones(self):
        self.assertEqual((C.CLIENT_VERSION, C.PROMPTFOO_MINIMUM, C.SDK_VERSION), ("2.1.296", "0.124.0", "0.3.283"))
        self.assertEqual((C.MODEL, C.EFFORT, C.BUDGET_USD), ("claude-opus-5-5", "medium", 4))
        self.assertEqual(C.FENCE_TOOLS, ["Bash", "Read", "Glob", "Grep", "ToolSearch"])
        self.assertEqual(C.DENIED_TOOLS, ["Agent", "Task", "Workflow", "ScheduleWakeup", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"])
        self.assertEqual(C.CHILD_ENV, {"MCP_TIMEOUT": "120000", "CLAUDE_CODE_ENABLE_TELEMETRY": "0", "DISABLE_TELEMETRY": "1", "ENABLE_CLAUDEAI_MCP_SERVERS": "false"})
        self.assertEqual(C.SERVERS, ("serena", "semble", "codebase-memory-mcp", "jcodemunch"))
        self.assertEqual(C.SERVER_COMMANDS, {"serena": "serena", "semble": "semble", "codebase-memory-mcp": "codebase-memory-mcp", "jcodemunch": "jcodemunch-mcp"})
        self.assertEqual(C.CODE_NAV_SERVERS, C.SERVERS + ("socraticode",))
        self.assertEqual(C.BEHAVIOUR_VARS, ["CLAUDECODE", "CLAUDE_CODE_DISABLE_ADVISOR_TOOL", "CLAUDE_CODE_EFFORT_LEVEL", "MAX_THINKING_TOKENS", "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE",
                                             "ANTHROPIC_MODEL", "ANTHROPIC_SMALL_FAST_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL",
                                             "CLAUDE_CODE_MAX_OUTPUT_TOKENS", "CLAUDE_CODE_DISABLE_THINKING", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "ENABLE_TOOL_SEARCH",
                                             "CLAUDE_CONFIG_DIR"])
        self.assertEqual(C.STAGED_FILES, ["promptfooconfig.yaml", "tasks.json", "e1_common.py", "e1_grade.py", "e1_tests.py", "e1_assert.py", "directives/serena.md", "directives/path.md"])

    def test_arms_and_trees_agree(self):
        self.assertEqual(list(C.ARMS), ["A0a", "A0b", "A1", "A3", "A5"])
        for arm, spec in C.ARMS.items():
            self.assertIn(spec["tree"], C.TREES, arm)
            self.assertEqual(C.TREES[spec["tree"]][1], spec["directive"], f"{arm}: the tree carries the directive the arm names")
            if spec["add"]:
                self.assertIn(spec["add"], C.TREES)
                self.assertEqual(C.TREES[spec["add"]], ("base", None), "the tree opened with --add-dir is the plain base worktree")
            self.assertEqual(spec["add"] is not None, C.TREES[spec["tree"]][0] == "stale", f"{arm}: the stale-start arms are the ones that open the worktree separately")
        self.assertEqual({c for c, _ in C.TREES.values()}, {"base", "stale"})
        self.assertFalse(C.ARMS["A5"]["servers"])
        self.assertTrue(all(C.ARMS[a]["servers"] for a in ("A0a", "A0b", "A1", "A3")))

    def test_no_file_of_the_folder_holds_a_home_path_a_key_name_or_non_ascii_text(self):
        for path in sorted(p for p in ES.rglob("*") if p.is_file() and p.suffix in {".py", ".yaml", ".md", ".json"}):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii(), f"{path.relative_to(ROOT)} holds non-ASCII text")
            self.assertNotRegex(text, r"/(?:home|Users)/(?!example\b)", f"{path.relative_to(ROOT)} holds a personal home path")
            self.assertNotIn("sk-ant", text)
            if path.suffix == ".yaml":
                self.assertNotIn("API_KEY", text, f"{path.relative_to(ROOT)} names a key variable")


@unittest.skipUnless(HAVE_YAML, "PyYAML is not installed")
class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load((E1 / "promptfooconfig.yaml").read_text(encoding="utf-8"))
        cls.providers = {p["label"]: p for p in cls.config["providers"]}

    def test_the_providers_are_the_arms_in_order_and_use_the_agent_sdk_provider(self):
        self.assertEqual([p["label"] for p in self.config["providers"]], list(C.ARMS))
        self.assertTrue(all(p["id"] == "anthropic:claude-agent-sdk" for p in self.config["providers"]))

    def test_every_arm_carries_the_fence_of_the_runner(self):
        for arm, provider in self.providers.items():
            cfg = provider["config"]
            self.assertEqual(cfg["model"], C.MODEL, arm)
            self.assertEqual(cfg["effort"], C.EFFORT, arm)
            self.assertEqual(cfg["permission_mode"], "dontAsk", arm)
            self.assertEqual(cfg["tools"], C.FENCE_TOOLS, arm)
            self.assertEqual(cfg["custom_allowed_tools"], [], arm)
            self.assertEqual(cfg["disallowed_tools"], C.DENIED_TOOLS, arm)
            self.assertEqual(cfg["setting_sources"], ["local"], arm)
            self.assertIs(cfg["strict_mcp_config"], True, arm)
            self.assertEqual(cfg["max_budget_usd"], C.BUDGET_USD, arm)
            self.assertEqual(cfg["output_format"], {"type": "json_schema", "schema": C.SCHEMA}, arm)
            self.assertEqual(cfg["copy_working_dir"], "copy", arm)
            self.assertEqual(cfg["settings"], "{{ env.E1_ROOT }}/settings.json", arm)
            self.assertEqual(cfg["path_to_claude_code_executable"], "{{ env.E1_CLAUDE }}", arm)
            self.assertEqual(cfg["env"], {"CLAUDE_CODE_TMPDIR": "{{ env.E1_ROOT }}/claude-tmp", **C.CHILD_ENV}, arm)

    def test_each_arm_starts_in_its_tree_opens_the_worktree_when_it_starts_stale_and_carries_the_servers_or_none(self):
        for arm, spec in C.ARMS.items():
            cfg = self.providers[arm]["config"]
            self.assertEqual(cfg["working_dir"], "{{ env.E1_ROOT }}/trees/" + spec["tree"], arm)
            if spec["add"]:
                self.assertEqual(cfg["additional_directories"], ["{{ env.E1_ROOT }}/trees/" + spec["add"]], arm)
            else:
                self.assertNotIn("additional_directories", cfg, arm)
            if spec["servers"]:
                self.assertIs(cfg["mcp"]["enabled"], True, arm)
                servers = {s["name"]: s for s in cfg["mcp"]["servers"]}
                self.assertEqual(list(servers), list(C.SERVERS), arm)
                self.assertEqual({n: s["command"] for n, s in servers.items()}, C.SERVER_COMMANDS, arm)
                self.assertTrue(all(set(s) <= {"name", "command", "args", "env"} for s in servers.values()), "only what the provider's structured MCP option carries (no alwaysLoad)")
            else:
                self.assertNotIn("mcp", cfg, arm)

    def test_the_prompts_are_the_runners_and_each_arm_runs_the_one_for_its_start(self):
        prompts = {p["label"]: p["raw"] for p in self.config["prompts"]}
        self.assertEqual(prompts["worktree-start"], "The repository for this task is the current directory (a checkout of one commit). Answer the question about this checkout only.\n\nQuestion: {{ question }}")
        stale = prompts["stale-start"]
        self.assertEqual(stale.count("{{ env.E1_ROOT }}/trees/base"), 2)
        self.assertIn("older copy of the repository", stale)
        for arm, spec in C.ARMS.items():
            self.assertEqual(self.providers[arm]["prompts"], ["stale-start" if spec["add"] else "worktree-start"], arm)

    def test_the_tests_come_from_the_generator_with_three_repeats(self):
        self.assertEqual(self.config["tests"], [{"path": "file://e1_tests.py:create_tests", "config": {"repeats": 3}}])
        self.assertEqual(self.config["evaluateOptions"], {"maxConcurrency": 1, "cache": False})

    def test_every_staged_file_exists_and_the_config_references_only_staged_files(self):
        for name in C.STAGED_FILES:
            self.assertTrue((E1 / name).is_file(), name)
        text = (E1 / "promptfooconfig.yaml").read_text(encoding="utf-8")
        for ref in re.findall(r"file://([A-Za-z0-9_./-]+?)(?::|\s|$)", text):
            self.assertIn(ref, C.STAGED_FILES, f"{ref} is not copied into the staged config directory")
        for module in ("e1_tests.py", "e1_assert.py"):
            self.assertIn(module, C.STAGED_FILES)
        # e1_assert and e1_tests import these two siblings, so a staged copy needs them too
        self.assertTrue({"e1_common.py", "e1_grade.py", "tasks.json"} <= set(C.STAGED_FILES))

    def test_skeletons_are_the_designs_arms_and_take_their_rows_from_the_frozen_generator(self):
        for experiment, design in F.DESIGNS.items():
            cfg = yaml.safe_load((ES / experiment / "promptfooconfig.yaml").read_text(encoding="utf-8"))
            self.assertEqual([p["label"] for p in cfg["providers"]], design["arms"], experiment)
            self.assertEqual(cfg["tests"], [{"path": "file://../frozen_inputs.py:create_tests", "config": {"experiment": experiment}}], experiment)
            for provider in cfg["providers"]:
                c = provider["config"]
                self.assertEqual(c["permission_mode"], "dontAsk")
                self.assertEqual(c["custom_allowed_tools"], [])
                self.assertEqual(c["disallowed_tools"], C.DENIED_TOOLS)
                self.assertEqual(c["tools"], C.FENCE_TOOLS)
                self.assertIs(c["strict_mcp_config"], True)
                self.assertEqual(c["copy_working_dir"], "copy")
                self.assertEqual(c["max_budget_usd"], C.BUDGET_USD)
                self.assertEqual((c["model"], c["effort"]), (C.MODEL, C.EFFORT))

    def test_e3_sends_the_proxy_arm_through_the_base_url_and_the_direct_arm_not(self):
        cfg = yaml.safe_load((ES / "e3" / "promptfooconfig.yaml").read_text(encoding="utf-8"))
        arms = {p["label"]: p["config"] for p in cfg["providers"]}
        self.assertEqual(arms["headroom-proxy"]["env"], {"ANTHROPIC_BASE_URL": "{{ env.E3_PROXY_URL }}"})
        self.assertNotIn("env", arms["direct"])


class GraderTests(unittest.TestCase):
    def test_the_selftest_of_the_module_passes_against_the_published_tasks(self):
        done = subprocess.run([sys.executable, "-I", str(E1 / "e1_grade.py")], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("FAIL", done.stdout)
        self.assertEqual(done.stdout.count("ok   "), 12)

    def test_every_question_accepts_its_gold_and_refuses_an_empty_answer(self):
        for qid, q in QUESTIONS.items():
            self.assertTrue(e1_grade.grade(q, good_output(q))["correct"], qid)
            self.assertFalse(e1_grade.grade(q, {"answer": "x", "citations": []})["correct"], qid)
            self.assertFalse(e1_grade.grade(q, None)["correct"], qid)

    def test_def_needs_the_exact_file_and_line(self):
        q = QUESTIONS["p-def"]
        f, ln = q["gold"]["file"], q["gold"]["line"]
        self.assertTrue(e1_grade.grade(q, {"citations": [{"file": "./" + f, "line": ln}]})["correct"])
        self.assertTrue(e1_grade.grade(q, {"citations": [{"file": "/var/tmp/x/wt/" + f, "line": ln}]})["correct"])
        self.assertTrue(e1_grade.grade(q, {"citations": [{"file": "/var/tmp/x/primary/" + f, "line": ln}]})["correct"])
        for wrong in ({"file": f, "line": ln + 1}, {"file": f, "line": ln - 1}, {"file": f + "x", "line": ln}):
            self.assertFalse(e1_grade.grade(q, {"citations": [wrong]})["correct"], wrong)

    def test_a_def_answer_that_cites_the_stale_tree_is_flagged_wrong_tree(self):
        moved = next(q for q in TASKS["questions"] if q["type"] == "def" and q["defined_at_stale"])
        stale_file, stale_line = moved["defined_at_stale"][0]
        graded = e1_grade.grade(moved, {"citations": [{"file": stale_file, "line": stale_line}]})
        self.assertFalse(graded["correct"])
        self.assertTrue(graded["wrong_tree"])
        self.assertFalse(e1_grade.grade(moved, {"citations": [{"file": "elsewhere.py", "line": 1}]})["wrong_tree"])

    def test_refs_need_every_gold_site(self):
        q = QUESTIONS["p-refs"]
        sites = [{"file": f, "line": ln} for f, ln in q["gold"]["sites"]]
        self.assertTrue(e1_grade.grade(q, {"citations": sites})["correct"])
        self.assertFalse(e1_grade.grade(q, {"citations": sites[:-1]})["correct"])
        self.assertFalse(e1_grade.grade(q, {"citations": [{"file": sites[0]["file"], "line": sites[0]["line"] + 1000}]})["correct"])

    def test_the_extra_sites_allowed_in_refs_are_int_of_a_tenth_of_the_cited_sites(self):
        q = {"type": "refs", "gold": {"sites": [[f"a{i}.py", i] for i in range(1, 10)]}}
        nine = [{"file": f"a{i}.py", "line": i} for i in range(1, 10)]
        extra = lambda n: [{"file": f"z{i}.py", "line": i} for i in range(1, n + 1)]  # noqa: E731
        self.assertTrue(e1_grade.grade(q, {"citations": nine})["correct"])
        self.assertTrue(e1_grade.grade(q, {"citations": nine + extra(1)})["correct"], "1 extra of 10 cited: int(1.0) = 1 allowed")
        self.assertFalse(e1_grade.grade(q, {"citations": nine + extra(2)})["correct"], "2 extra of 11 cited: int(1.1) = 1 allowed")
        eleven = {"type": "refs", "gold": {"sites": [[f"a{i}.py", i] for i in range(1, 12)]}}
        base = [{"file": f"a{i}.py", "line": i} for i in range(1, 12)]
        self.assertTrue(e1_grade.grade(eleven, {"citations": base + extra(1)})["correct"])
        self.assertFalse(e1_grade.grade(eleven, {"citations": base + extra(3)})["correct"], "3 extra of 14 cited: int(1.4) = 1 allowed")

    def test_explain_needs_eighty_percent_of_the_raise_lines_and_at_most_two_extra(self):
        q = QUESTIONS["p-explain"]
        gold = q["gold"]["lines"]
        cite = lambda lines: {"citations": [{"file": q["gold"]["file"], "line": ln} for ln in lines]}  # noqa: E731
        need = -(-len(gold) * 8 // 10)
        self.assertTrue(e1_grade.grade(q, cite(gold[:need]))["correct"])
        self.assertFalse(e1_grade.grade(q, cite(gold[:need - 1]))["correct"])
        extras = [max(gold) + 1000 + i for i in range(3)]
        self.assertTrue(e1_grade.grade(q, cite(gold + extras[:2]))["correct"])
        self.assertFalse(e1_grade.grade(q, cite(gold + extras))["correct"])

    def test_the_eighty_percent_of_explain_is_ceil_of_point_eight_times_the_gold_lines(self):
        q = {"type": "explain", "gold": {"file": "f.py", "lines": list(range(10, 20))}}
        cite = lambda n: {"citations": [{"file": "f.py", "line": ln} for ln in range(10, 10 + n)]}  # noqa: E731
        self.assertTrue(e1_grade.grade(q, cite(8))["correct"])
        self.assertFalse(e1_grade.grade(q, cite(7))["correct"])
        q = {"type": "explain", "gold": {"file": "f.py", "lines": list(range(10, 14))}}
        self.assertTrue(e1_grade.grade(q, cite(4))["correct"])
        self.assertFalse(e1_grade.grade(q, cite(3))["correct"], "ceil(3.2) = 4 of 4 gold lines")

    def test_callers_must_equal_the_gold_set_and_name_a_method_by_its_bare_name_deviation_d1(self):
        q = QUESTIONS["p-callers"]
        gold = list(q["gold"]["functions"])
        self.assertTrue(e1_grade.grade(q, {"functions": gold})["correct"])
        self.assertFalse(e1_grade.grade(q, {"functions": gold[:-1]})["correct"])
        self.assertFalse(e1_grade.grade(q, {"functions": gold + ["extra_function"]})["correct"])
        qualified = ["SomeClass." + gold[0] + "()"] + gold[1:]
        self.assertTrue(e1_grade.grade(q, {"functions": qualified})["correct"])
        self.assertFalse(e1_grade.grade(q, {"functions": ["nested_helper"] + gold[1:]})["correct"])

    def test_deviation_d1_fails_before_the_fix_the_preregistered_exact_string_grader_refuses_a_qualified_name(self):
        q = QUESTIONS["p-callers"]
        gold = list(q["gold"]["functions"])
        qualified = {"functions": ["SomeClass." + gold[0] + "()"] + gold[1:]}

        def preregistered(question, output):  # the callers rule as first frozen: the named set equals the gold set by exact string
            return set(output.get("functions") or []) == set(question["gold"]["functions"])
        self.assertFalse(preregistered(q, qualified))
        self.assertTrue(e1_grade.grade(q, qualified)["correct"])

    def test_bare_name_and_norm(self):
        self.assertEqual(e1_grade.bare_name("A.b.c()"), "c")
        self.assertEqual(e1_grade.bare_name(" `f` "), "f")
        self.assertEqual(e1_grade.norm(" ./x/y.py "), "x/y.py")
        self.assertEqual(e1_grade.norm("/a/b/wt/tools/x.py"), "tools/x.py")
        self.assertEqual(e1_grade.norm(None), "")
        self.assertEqual(e1_grade.cites({"citations": [{"file": "a", "line": "3"}, {"file": "b", "line": "x"}, {"file": "c"}, "not a dict"]}), [("a", 3)])
        self.assertFalse(e1_grade.grade({"type": "other", "gold": {}}, {"citations": []})["correct"])


class TestGeneratorTests(unittest.TestCase):
    def test_one_preflight_row_then_every_question_for_every_repeat_in_repeat_major_order(self):
        rows = e1_tests.create_tests({"repeats": 3})
        self.assertEqual(len(rows), 1 + 12 * 3)
        self.assertEqual(rows[0]["metadata"], {"kind": "preflight"})
        self.assertEqual(rows[0]["vars"]["question_id"], "preflight")
        order = [(r["vars"]["repeat"], r["vars"]["question_id"]) for r in rows[1:]]
        ids = [q["id"] for q in TASKS["questions"]]
        self.assertEqual(order, [(n, i) for n in (1, 2, 3) for i in ids])
        self.assertEqual(len({r["description"] for r in rows}), len(rows))
        for row in rows[1:]:
            q = QUESTIONS[row["vars"]["question_id"]]
            self.assertEqual(row["description"], f"{q['id']} r{row['vars']['repeat']}")
            self.assertEqual(row["vars"]["question"], q["prompt"])
            self.assertEqual(row["metadata"], {"kind": "question", "type": q["type"], "repeat": row["vars"]["repeat"]})
            self.assertEqual(row["assert"], [{"type": "python", "value": "file://e1_assert.py:correct", "metric": "correct"}])
        self.assertEqual(rows[0]["assert"], [{"type": "python", "value": "file://e1_assert.py:preflight", "metric": "preflight"}])

    def test_the_default_is_three_repeats_and_the_bounds_are_enforced(self):
        self.assertEqual(len(e1_tests.create_tests()), 37)
        self.assertEqual(len(e1_tests.create_tests({"repeats": 1})), 13)
        self.assertEqual(len(e1_tests.create_tests({"repeats": 9})), 1 + 12 * 9)
        for bad in (0, 10, -1):
            with self.assertRaises(ValueError):
                e1_tests.create_tests({"repeats": bad})

    def test_the_assertion_functions_the_rows_name_exist(self):
        for name in ("correct", "preflight"):
            self.assertTrue(callable(getattr(e1_assert, name)))

    def test_the_preflight_prompt_allows_only_toolsearch_and_asks_for_both_lines(self):
        prompt = e1_tests.PREFLIGHT_PROMPT
        for needle in ("Do not call any tool except ToolSearch", "TOOLS:", "DIRECTIVE:", "Code navigation", "serena", "semble", "codebase-memory", "jcodemunch"):
            self.assertIn(needle, prompt)


class AssertionTests(unittest.TestCase):
    TOOLS = "mcp__serena__find_symbol mcp__semble__search mcp__codebase-memory-mcp__search_graph mcp__jcodemunch__search_symbols"

    def answer(self, tools, directive):
        return {"answer": f"TOOLS: {tools}\nDIRECTIVE: {directive}", "citations": []}

    def check(self, arm, tools, directive, calls=("StructuredOutput",)):
        return e1_assert.check_preflight(arm, self.answer(tools, directive)["answer"], list(calls))

    def test_correct_grades_a_dict_and_the_same_answer_as_json_text_and_rejects_the_rest(self):
        q = QUESTIONS["p-def"]
        ctx = {"vars": {"question_id": "p-def"}}
        good = good_output(q)
        self.assertTrue(e1_assert.correct(good, ctx)["pass"])
        self.assertTrue(e1_assert.correct(json.dumps(good), ctx)["pass"])
        self.assertEqual(e1_assert.correct(good, ctx)["score"], 1)
        self.assertFalse(e1_assert.correct({"answer": "x", "citations": []}, ctx)["pass"])
        self.assertEqual(e1_assert.correct({"answer": "x", "citations": []}, ctx)["score"], 0)
        self.assertFalse(e1_assert.correct("not json", ctx)["pass"])
        self.assertFalse(e1_assert.correct(None, ctx)["pass"])
        self.assertFalse(e1_assert.correct(good, {"vars": {"question_id": "nope"}})["pass"])
        self.assertFalse(e1_assert.correct(good, {})["pass"])
        self.assertFalse(e1_assert.correct(good, {"vars": {"question_id": "p-refs"}})["pass"], "the answer of one question does not grade another")

    def test_preflight_passes_each_arm_exactly_when_servers_and_directive_match_its_definition(self):
        serena, path = C.DIRECTIVE_FIRST_SENTENCE["serena"], C.DIRECTIVE_FIRST_SENTENCE["path"]
        for arm in ("A0a", "A0b"):
            self.assertTrue(self.check(arm, self.TOOLS, "NONE")[0], arm)
        self.assertTrue(self.check("A1", self.TOOLS, f'"{serena}"')[0])
        self.assertTrue(self.check("A3", self.TOOLS, path)[0])
        self.assertTrue(self.check("A5", "none", "NONE")[0])
        # negative controls: each arm refuses the neighbouring arm's answer
        self.assertFalse(self.check("A1", self.TOOLS, "NONE")[0], "A1 without its paragraph")
        self.assertFalse(self.check("A1", self.TOOLS, path)[0], "A1 with A3's paragraph")
        self.assertFalse(self.check("A3", self.TOOLS, serena)[0], "A3 with A1's paragraph")
        self.assertFalse(self.check("A0b", self.TOOLS, serena)[0], "a paragraph quoted by an arm that carries none")
        self.assertFalse(self.check("A5", self.TOOLS, "NONE")[0], "A5 listing servers")
        self.assertFalse(self.check("A0b", "none", "NONE")[0], "an arm with servers listing none")

    def test_every_one_of_the_four_servers_must_have_a_listed_tool(self):
        names = {"serena": "mcp__serena__find_symbol", "semble": "mcp__semble__search", "codebase-memory-mcp": "mcp__codebase-memory-mcp__search_graph", "jcodemunch": "mcp__jcodemunch__search_symbols"}
        for missing in names:
            tools = " ".join(v for k, v in names.items() if k != missing)
            ok, reason = self.check("A0b", tools, "NONE")
            self.assertFalse(ok, missing)
            self.assertIn(missing, reason)

    def test_quotes_backticks_curly_apostrophes_and_case_do_not_matter_but_the_sentence_does(self):
        sentence = C.DIRECTIVE_FIRST_SENTENCE["serena"]
        curly = sentence.replace("'", chr(0x2019))
        for quoted in (f'"{sentence}"', f"`{sentence}`", curly, sentence.upper(), f"  {sentence}  "):
            self.assertTrue(self.check("A1", self.TOOLS, quoted)[0], quoted)
        self.assertFalse(self.check("A1", self.TOOLS, "This session's code tools are bound")[0])
        self.assertTrue(self.check("A0b", self.TOOLS, "none.")[0])
        self.assertTrue(self.check("A0b", self.TOOLS, "None")[0])

    def test_a_tool_other_than_toolsearch_could_have_read_the_file_so_it_voids_the_row(self):
        sentence = C.DIRECTIVE_FIRST_SENTENCE["serena"]
        self.assertTrue(self.check("A1", self.TOOLS, sentence, calls=("ToolSearch", "StructuredOutput"))[0])
        for tool in ("Read", "Bash", "Grep", "Glob", "mcp__serena__find_symbol"):
            ok, reason = self.check("A1", self.TOOLS, sentence, calls=(tool, "StructuredOutput"))
            self.assertFalse(ok, tool)
            self.assertIn(tool, reason)

    def test_missing_lines_unknown_arms_and_unstructured_output_fail(self):
        self.assertFalse(e1_assert.check_preflight("A0b", "TOOLS: none", [])[0])
        self.assertFalse(e1_assert.check_preflight("A0b", "DIRECTIVE: NONE", [])[0])
        self.assertFalse(e1_assert.check_preflight("A9", "TOOLS: none\nDIRECTIVE: NONE", [])[0])
        self.assertFalse(e1_assert.check_preflight(None, "TOOLS: none\nDIRECTIVE: NONE", [])[0])
        ctx = {"provider": {"label": "A5"}, "providerResponse": {"metadata": {"toolCalls": [{"name": "StructuredOutput"}]}}}
        self.assertTrue(e1_assert.preflight(self.answer("none", "NONE"), ctx)["pass"])
        self.assertTrue(e1_assert.preflight(json.dumps(self.answer("none", "NONE")), ctx)["pass"])
        self.assertFalse(e1_assert.preflight("not json", ctx)["pass"])
        read = {"provider": {"label": "A5"}, "providerResponse": {"metadata": {"toolCalls": [{"name": "Read"}, {"name": "StructuredOutput"}]}}}
        self.assertFalse(e1_assert.preflight(self.answer("none", "NONE"), read)["pass"], "a Read call voids the row, through the entry point promptfoo calls")
        self.assertFalse(e1_assert.preflight(self.answer("none", "NONE"), {"providerResponse": ctx["providerResponse"]})["pass"], "no provider label")
        self.assertEqual(e1_assert.tool_names({"providerResponse": {"metadata": {"toolCalls": [{"name": "Grep"}, "junk", {"name": "Bash"}]}}}), ["Grep", "Bash"])
        self.assertEqual(e1_assert.tool_names({}), [])


class DecideTests(unittest.TestCase):
    def run_of(self, arm, q, correct=True, cost=0.05, nav=False, repeat="1", turns=3, seconds=2.0):
        return {"arm": arm, "q": q, "repeat": repeat, "correct": correct, "cost": cost, "turns": turns, "seconds": seconds, "nav": nav}

    def cells(self, arm, questions=10, repeats=1, correct=None, cost=0.05, nav_questions=0):
        """`questions` questions x `repeats` runs; `correct` = how many runs are correct (default all); the first `nav_questions` questions used a tool in every repeat."""
        runs = []
        for qi in range(questions):
            for r in range(repeats):
                runs.append(self.run_of(arm, f"q{qi}", True, cost, nav=qi < nav_questions, repeat=str(r + 1)))
        for k in range(len(runs) - (len(runs) if correct is None else correct)):
            runs[k]["correct"] = False
        return runs

    def test_load_runs_keeps_question_rows_regrades_them_and_reads_cost_turns_seconds_and_tool_use(self):
        q = QUESTIONS["p-def"]
        wrong = {"answer": "x", "citations": []}
        items = [promptfoo_item("A0b", "p-def", 1, good_output(q), cost=0.0457, calls=("Grep", "StructuredOutput"), turns=3, millis=4200),
                 promptfoo_item("A0b", "p-def", 2, wrong, calls=("mcp__serena__find_symbol", "StructuredOutput")),
                 promptfoo_item("A0b", "preflight", 1, {"answer": "TOOLS: none"}, kind="preflight")]
        items[1]["gradingResult"] = {"pass": True}  # the stored verdict says pass; the answer is wrong
        with tempfile.TemporaryDirectory() as tmp:
            runs, faults = e1_decide.load_runs([write_results(Path(tmp) / "r.json", items)], TASKS)
        self.assertEqual(faults, [])
        self.assertEqual(len(runs), 2, "the preflight row is not a measurement")
        self.assertEqual([r["correct"] for r in runs], [True, False], "regraded from the answer, not read from the stored verdict")
        self.assertEqual([r["nav"] for r in runs], [False, True])
        self.assertEqual((runs[0]["cost"], runs[0]["turns"], runs[0]["seconds"]), (0.0457, 3, 4.2))
        self.assertEqual(runs[0]["repeat"], "1")

    def test_a_provider_error_an_unknown_arm_and_an_unknown_question_are_faults_not_runs(self):
        q = QUESTIONS["p-def"]
        items = [promptfoo_item("A0b", "p-def", 1, good_output(q), error="boom"), promptfoo_item("A7", "p-def", 1, good_output(q)), promptfoo_item("A0b", "nope", 1, good_output(q)),
                 promptfoo_item("A0b", "p-def", 2, good_output(q))]
        items[3]["response"]["metadata"].pop("durationMs")
        with tempfile.TemporaryDirectory() as tmp:
            runs, faults = e1_decide.load_runs([write_results(Path(tmp) / "r.json", items)], TASKS)
        self.assertEqual(len(runs), 1)
        self.assertEqual(len(faults), 3)
        self.assertIn("provider error", faults[0])
        self.assertEqual(runs[0]["seconds"], 2.005, "falls back to the result's latency when the response has no duration")

    def test_a_wrong_answer_is_a_result_even_though_promptfoo_copies_the_assertion_text_into_error(self):
        q = QUESTIONS["p-def"]
        rejected = promptfoo_item("A0b", "p-def", 1, {"answer": "x", "citations": []})
        rejected["failureReason"] = 1  # ResultFailureReason.ASSERT
        rejected["error"] = "cited 0 location(s)"
        rejected["gradingResult"] = {"pass": False}
        with tempfile.TemporaryDirectory() as tmp:
            runs, faults = e1_decide.load_runs([write_results(Path(tmp) / "r.json", [rejected, promptfoo_item("A0b", "p-def", 2, good_output(q))])], TASKS)
        self.assertEqual(faults, [])
        self.assertEqual([r["correct"] for r in runs], [False, True])

    def test_the_server_prefixes_that_count_as_a_code_navigation_call_are_the_five_servers_only(self):
        q = QUESTIONS["p-def"]
        for name, expected in (("mcp__serena__find_symbol", True), ("mcp__semble__search", True), ("mcp__codebase-memory-mcp__search_graph", True), ("mcp__jcodemunch__route", True),
                               ("mcp__socraticode__codebase_search", True), ("mcp__qmd__query", False), ("Grep", False), ("serena", False), ("mcp__serenax__f", False)):
            with tempfile.TemporaryDirectory() as tmp:
                runs, _ = e1_decide.load_runs([write_results(Path(tmp) / "r.json", [promptfoo_item("A1", "p-def", 1, good_output(q), calls=(name,))])], TASKS)
            self.assertEqual(runs[0]["nav"], expected, name)

    def test_criterion_i_correct_answers_not_fewer_than_the_baseline(self):
        base = self.cells("A0a", 10)
        same = e1_decide.decide(base + self.cells("A1", 10, nav_questions=10), "A0a")["verdicts"]["A1"]
        fewer = e1_decide.decide(base + self.cells("A1", 10, correct=9, nav_questions=10), "A0a")["verdicts"]["A1"]
        self.assertTrue(same["i_correct_not_fewer"])
        self.assertFalse(fewer["i_correct_not_fewer"])
        self.assertFalse(fewer["adopt"])
        more = e1_decide.decide(self.cells("A0a", 10, correct=8) + self.cells("A1", 10, correct=9, nav_questions=10), "A0a")["verdicts"]["A1"]
        self.assertTrue(more["i_correct_not_fewer"])

    def test_criterion_ii_median_cost_at_most_one_point_one_times_the_baseline(self):
        base = self.cells("A0a", 5, cost=0.5)
        at = e1_decide.decide(base + self.cells("A1", 5, cost=0.55, nav_questions=5), "A0a")["verdicts"]["A1"]  # 1.1 * 0.5 == 0.55 exactly in floating point
        over = e1_decide.decide(base + self.cells("A1", 5, cost=0.5501, nav_questions=5), "A0a")["verdicts"]["A1"]
        self.assertTrue(at["ii_median_cost_at_most_1.1x"])
        self.assertFalse(over["ii_median_cost_at_most_1.1x"])
        self.assertFalse(over["adopt"])
        mixed = base + [self.run_of("A1", f"q{i}", cost=c, nav=True) for i, c in enumerate((0.05, 0.05, 0.90, 0.90, 0.90))]
        self.assertFalse(e1_decide.decide(mixed, "A0a")["verdicts"]["A1"]["ii_median_cost_at_most_1.1x"], "the median, not the mean or the minimum")

    def test_criterion_iii_use_on_at_least_seventy_percent_of_the_questions(self):
        base = self.cells("A0a", 10)
        seven = e1_decide.decide(base + self.cells("A1", 10, nav_questions=7), "A0a")["verdicts"]["A1"]
        six = e1_decide.decide(base + self.cells("A1", 10, nav_questions=6), "A0a")["verdicts"]["A1"]
        self.assertTrue(seven["iii_use_on_70_percent_of_questions"])
        self.assertEqual(seven["use_share"], 0.7)
        self.assertTrue(seven["adopt"])
        self.assertFalse(six["iii_use_on_70_percent_of_questions"])
        self.assertFalse(six["adopt"])

    def test_a_question_counts_as_used_when_at_least_half_of_its_repeats_used_a_tool(self):
        def arm(n_nav):
            runs = [self.run_of("A1", "q0", nav=i < n_nav, repeat=str(i + 1)) for i in range(3)]
            return e1_decide.decide([self.run_of("A0a", "q0", repeat=str(i + 1)) for i in range(3)] + runs, "A0a")["rows"]["A1"]["use_questions"]
        self.assertEqual([arm(n) for n in (0, 1, 2, 3)], [0, 0, 1, 1])
        two = [self.run_of("A1", "q0", nav=True, repeat="1"), self.run_of("A1", "q0", nav=False, repeat="2")]
        self.assertEqual(e1_decide.summary(two, {"q0"})["use_questions"], 1, "one of two is at least half")

    def test_adoption_needs_all_three_criteria_and_a5_and_the_baseline_are_never_candidates(self):
        base = self.cells("A0a", 10)
        result = e1_decide.decide(base + self.cells("A0b", 10, nav_questions=10) + self.cells("A5", 10, nav_questions=10), "A0a")
        self.assertEqual(set(result["verdicts"]), {"A0b"})
        self.assertTrue(result["verdicts"]["A0b"]["adopt"])
        self.assertEqual(set(result["rows"]), {"A0a", "A0b", "A5"})

    def test_questions_not_shared_with_the_baseline_are_left_out_of_the_comparison(self):
        base = self.cells("A0a", 4)
        arm = self.cells("A1", 6, nav_questions=6)
        row = e1_decide.decide(base + arm, "A0a")["rows"]["A1"]
        self.assertEqual((row["questions"], row["runs"]), (4, 4))

    def test_unequal_run_counts_over_the_shared_questions_are_refused(self):
        with self.assertRaises(ValueError):
            e1_decide.decide(self.cells("A0a", 4, repeats=3) + self.cells("A1", 4, repeats=2), "A0a")
        with self.assertRaises(ValueError):
            e1_decide.decide(self.cells("A1", 4), "A0a")

    def test_equal_run_counts_over_different_question_repeat_pairs_are_refused(self):
        """Review of #1046 at 38f4151a (P1): three repeats of q1 and one of q2 against one of q1 and three of q2 have equal counts and weight the questions differently."""
        base = [self.run_of("A0a", q, repeat=str(r)) for q, r in (("q1", 1), ("q1", 2), ("q1", 3), ("q2", 1))]
        arm = [self.run_of("A1", q, repeat=str(r)) for q, r in (("q1", 1), ("q2", 1), ("q2", 2), ("q2", 3))]
        with self.assertRaisesRegex(ValueError, "do not hold the same"):
            e1_decide.decide(base + arm, "A0a")
        same = [self.run_of("A1", q, repeat=str(r)) for q, r in (("q1", 1), ("q1", 2), ("q1", 3), ("q2", 1))]
        self.assertIn("A1", e1_decide.decide(base + same, "A0a")["verdicts"], "the same pairs in another order are comparable")
        doubled = base + [self.run_of("A0a", "q2", repeat="1")]
        with self.assertRaisesRegex(ValueError, "do not hold the same"):
            e1_decide.decide(doubled + same + [self.run_of("A1", "q2", repeat="2")], "A0a")

    def test_the_carrying_cost_needs_the_same_pairs_in_a0b_and_a5(self):
        a0b = [self.run_of("A0b", q, repeat=str(r)) for q, r in (("q1", 1), ("q1", 2), ("q2", 1))]
        a5 = [self.run_of("A5", q, repeat=str(r)) for q, r in (("q1", 1), ("q2", 1), ("q2", 2))]
        with self.assertRaisesRegex(ValueError, "A0b and A5 do not hold the same"):
            e1_decide.decide(self.cells("A0a", 2, repeats=2) + a0b + a5, "A0a")

    def test_the_carrying_cost_of_the_servers_is_a0b_against_a5(self):
        runs = self.cells("A0a", 4) + self.cells("A0b", 4, cost=0.0716) + self.cells("A5", 4, cost=0.0625)
        carrying = e1_decide.decide(runs, "A0a")["carrying"]
        self.assertEqual(carrying["questions"], 4)
        self.assertEqual(carrying["cost_change_percent"], 14.6)
        self.assertIsNone(e1_decide.decide(self.cells("A0a", 4) + self.cells("A0b", 4), "A0a")["carrying"])

    def test_the_command_line_prints_the_table_writes_json_and_exits_zero_two_or_three(self):
        q = QUESTIONS["p-def"]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            good = write_results(tmp / "good.json", [promptfoo_item(a, "p-def", 1, good_output(q)) for a in ("A0a", "A0b")])
            out = tmp / "out.json"
            done = subprocess.run([sys.executable, "-I", str(E1 / "e1_decide.py"), str(good), "--json", str(out)], capture_output=True, text=True, timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("A0b", done.stdout)
            self.assertIn("correct non-use or no gain", done.stdout)
            self.assertEqual(json.loads(out.read_text())["faults"], [])
            faulty = write_results(tmp / "faulty.json", [promptfoo_item("A0a", "p-def", 1, good_output(q)), promptfoo_item("A0b", "p-def", 1, good_output(q)), promptfoo_item("A0b", "p-def", 2, None, error="x")])
            self.assertEqual(subprocess.run([sys.executable, "-I", str(E1 / "e1_decide.py"), str(faulty)], capture_output=True, text=True, timeout=60).returncode, 3)
            no_base = write_results(tmp / "nb.json", [promptfoo_item("A0b", "p-def", 1, good_output(q))])
            refused = subprocess.run([sys.executable, "-I", str(E1 / "e1_decide.py"), str(no_base)], capture_output=True, text=True, timeout=60)
            self.assertEqual(refused.returncode, 2)
            self.assertIn("baseline", refused.stderr)


class FrozenInputsTests(unittest.TestCase):
    def freeze(self, folder: Path, experiment="e2", status="frozen", drop=None, tamper=False, rows=None):
        design = F.DESIGNS[experiment]
        inputs = {}
        for name in design["inputs"]:
            if name == drop:
                continue
            path = folder / f"{experiment}-{name}.txt"
            path.write_text(f"{experiment} {name}\n")
            inputs[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if tamper:
            (folder / f"{experiment}-{design['inputs'][0]}.txt").write_text("changed after the freeze\n")
        (folder / f"{experiment}.json").write_text(json.dumps({"experiment": experiment, "status": status, "inputs": inputs, "tests": [{"vars": {"question": "q"}}] if rows is None else rows}))

    def test_without_a_frozen_receipt_every_experiment_refuses_and_names_its_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            for experiment, design in F.DESIGNS.items():
                with self.assertRaises(F.FrozenInputsError) as ctx:
                    F.load_frozen(experiment, tmp)
                for name in design["inputs"]:
                    self.assertIn(name, str(ctx.exception))
                self.assertIn("is not frozen", str(ctx.exception))

    def test_the_repository_ships_no_frozen_receipt(self):
        self.assertFalse((ES / "frozen").exists(), "a frozen receipt is added by the preregistration of an experiment, not by this change")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("E_SERIES_FROZEN", None)
            for experiment in F.DESIGNS:
                with self.assertRaises(F.FrozenInputsError):
                    F.create_tests({"experiment": experiment})

    def test_a_complete_receipt_returns_its_rows_for_each_experiment(self):
        for experiment in F.DESIGNS:
            with tempfile.TemporaryDirectory() as tmp:
                self.freeze(Path(tmp), experiment, rows=[{"vars": {"question": "a"}}, {"vars": {"question": "b"}}])
                self.assertEqual(F.load_frozen(experiment, tmp), [{"vars": {"question": "a"}}, {"vars": {"question": "b"}}], experiment)

    def test_the_environment_variable_names_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.freeze(Path(tmp), "e3")
            with mock.patch.dict(os.environ, {"E_SERIES_FROZEN": tmp}):
                self.assertEqual(F.create_tests({"experiment": "e3"}), [{"vars": {"question": "q"}}])
            with mock.patch.dict(os.environ, {"E_SERIES_FROZEN": tmp + "-missing"}):
                with self.assertRaises(F.FrozenInputsError):
                    F.create_tests({"experiment": "e3"})

    def test_each_defect_of_a_receipt_stops_the_experiment_with_its_reason(self):
        cases = {
            "draft status": (dict(status="draft"), "not 'frozen'"),
            "an input missing": (dict(drop="tasks"), "input tasks"),
            "an input changed after the freeze": (dict(tamper=True), "no longer matches"),
            "no rows": (dict(rows=[]), "no test rows"),
            "rows that are not objects": (dict(rows=["x"]), "no test rows"),
        }
        for label, (kwargs, reason) in cases.items():
            with tempfile.TemporaryDirectory() as tmp:
                self.freeze(Path(tmp), "e3", **kwargs)
                with self.assertRaises(F.FrozenInputsError) as ctx:
                    F.load_frozen("e3", tmp)
                self.assertIn(reason, str(ctx.exception), label)
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "e3.json").write_text("{not json")
            with self.assertRaises(F.FrozenInputsError):
                F.load_frozen("e3", tmp)
            with self.assertRaises(F.FrozenInputsError):
                F.load_frozen("e9", tmp)
        with tempfile.TemporaryDirectory() as tmp:
            self.freeze(Path(tmp), "e3")
            receipt = json.loads(Path(tmp, "e3.json").read_text())
            receipt["experiment"] = "e2"  # complete for e3 in every other respect, but it names another experiment
            Path(tmp, "e3.json").write_text(json.dumps(receipt))
            with self.assertRaises(F.FrozenInputsError) as ctx:
                F.load_frozen("e3", tmp)
            self.assertIn("does not name experiment e3", str(ctx.exception))

    def test_an_input_with_a_malformed_digest_or_an_absolute_path_is_judged_like_any_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.freeze(Path(tmp), "e3")
            receipt = json.loads(Path(tmp, "e3.json").read_text())
            receipt["inputs"]["tasks"]["sha256"] = "abc"
            Path(tmp, "e3.json").write_text(json.dumps(receipt))
            with self.assertRaises(F.FrozenInputsError) as ctx:
                F.load_frozen("e3", tmp)
            self.assertIn("lacks a path and a 64-digit sha256", str(ctx.exception))
            self.freeze(Path(tmp), "e3")
            receipt = json.loads(Path(tmp, "e3.json").read_text())
            receipt["inputs"]["tasks"]["path"] = str(Path(tmp, "e3-tasks.txt").resolve())
            Path(tmp, "e3.json").write_text(json.dumps(receipt))
            self.assertEqual(len(F.load_frozen("e3", tmp)), 1)

    def test_the_designs_are_the_four_experiments_of_the_cause_table_with_their_arms_and_inputs(self):
        self.assertEqual(F.DESIGNS, {
            "e2": {"title": "records retrieval", "arms": ["grep-status-quo", "qmd-directive", "aimemory-directive"], "inputs": ["questions", "qmd_collection", "directives"]},
            "e3": {"title": "headroom parity", "arms": ["direct", "headroom-proxy"], "inputs": ["tasks", "proxy"]},
            "e4": {"title": "autonomous skills", "arms": ["baseline", "fix7-sentence"], "inputs": ["tasks", "sentence", "skills"]},
            "e5": {"title": "unresolved triggers", "arms": ["natural"], "inputs": ["trigger_cases", "variants", "skills"]},
        })

    def test_the_designs_name_the_arms_the_readme_table_lists(self):
        readme = (ES / "README.md").read_text(encoding="utf-8")
        for experiment, design in F.DESIGNS.items():
            for arm in design["arms"]:
                self.assertIn(f"`{arm}`", readme, f"{experiment}: arm {arm} is in the README table")
            for name in design["inputs"]:
                self.assertIn(f"`{name}`", readme, f"{experiment}: input {name} is in the README table")


class ScratchRepository:
    """A repository with a base and a stale commit, a copy of the E1 folder whose tasks.json names them, fake client/promptfoo/server executables and a fake home."""

    def __init__(self, tmp: Path):
        tmp = Path(os.path.realpath(tmp))
        self.tmp = tmp
        self.repo = tmp / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "AGENTS.md").write_text("rules\n")
        (self.repo / "CLAUDE.md").write_text("@AGENTS.md\n")
        (self.repo / "old.py").write_text("def old():\n    pass\n")
        self.commit("stale")
        self.stale = self.git("rev-parse", "HEAD").strip()
        (self.repo / "new.py").write_text("def new():\n    pass\n")
        self.commit("base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.e1 = tmp / "e1"
        shutil.copytree(E1, self.e1, ignore=shutil.ignore_patterns("__pycache__"))
        tasks = dict(TASKS, base=self.base, stale=self.stale)
        (self.e1 / "tasks.json").write_text(json.dumps(tasks))
        self.bin = tmp / "bin"
        self.bin.mkdir()
        (self.bin / "git").symlink_to(shutil.which("git"))
        self.claude = self.script("claude", 'echo "2.1.296 (Claude Code)"')
        self.promptfoo = self.script("promptfoo-bin", 'echo "banner"; echo "0.124.0"')
        for command in C.SERVER_COMMANDS.values():
            self.script(command, "exit 0")
        self.sdk = tmp / "sdk"
        self.sdk.mkdir()
        (self.sdk / "package.json").write_text(json.dumps({"name": "@anthropic-ai/claude-agent-sdk", "version": C.SDK_VERSION}))
        self.semble = tmp / "semble-model"
        self.semble.mkdir()
        self.home = tmp / "home"
        self.home.mkdir()
        self.work = tmp / "work"
        self.work.mkdir()
        self.root = self.work / "root"
        self.env = {**CLEAN_ENV, "HOME": str(self.home), "PATH": str(self.bin)}  # only the fake servers and git: no npm, no network
        self.env.pop("E1_ROOT", None)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, check=True).stdout

    def commit(self, message):
        self.git("add", "-A")
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=scratch", "-c", "user.email=no-address", "commit", "-q", "-m", message], check=True, capture_output=True)

    def script(self, name, body):
        path = self.bin / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def prepare(self, *extra, root=None, claude=None, promptfoo=None, sdk=True):
        cmd = [sys.executable, "-I", str(self.e1 / "e1_prepare.py"), "--root", str(root or self.root), "--claude", str(claude or self.claude), "--semble-model", str(self.semble),
               "--repo", str(self.repo), "--promptfoo", str(promptfoo or self.promptfoo)]
        if sdk:
            cmd += ["--sdk-from", str(self.sdk)]
        return subprocess.run(cmd + list(extra), capture_output=True, text=True, env=self.env, timeout=120)

    def run(self, *args, env=None):
        return subprocess.run([sys.executable, "-I", str(self.e1 / "e1_run.py"), "--root", str(self.root), *args], capture_output=True, text=True, env=env or self.env, timeout=120)


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="e-series-")
        self.addCleanup(self._tmp.cleanup)
        self.s = ScratchRepository(Path(self._tmp.name))

    def test_prepare_builds_four_trees_the_fence_the_staged_config_and_a_manifest(self):
        done = self.s.prepare()
        self.assertEqual(done.returncode, 0, done.stderr)
        root = self.s.root
        manifest = json.loads((root / "manifest.json").read_text())
        self.assertEqual(manifest["trees"], {"base": self.s.base, "base-serena": self.s.base, "stale": self.s.stale, "stale-path": self.s.stale})
        for name, (commit, directive) in C.TREES.items():
            tree = root / "trees" / name
            self.assertEqual(subprocess.run(["git", "-C", str(tree), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(), manifest["trees"][name])
            local = tree / "CLAUDE.local.md"
            if directive:
                self.assertEqual(local.read_text(), (E1 / "directives" / f"{directive}.md").read_text())
            else:
                self.assertFalse(local.exists(), name)
            self.assertTrue((tree / ("new.py" if commit == "base" else "old.py")).is_file())
            self.assertEqual(not (tree / "new.py").exists(), commit == "stale")
            self.assertTrue((tree / ".git" / "objects" / "info" / "alternates").is_file(), f"{name}: a shared clone, so that a per-call copy of the tree does not copy the object store")
        for name in C.STAGED_FILES:
            self.assertEqual(sha256_bytes(root / "config" / name), manifest["staged"][name], name)
        self.assertTrue((root / "config" / "node_modules" / "@anthropic-ai" / "claude-agent-sdk").is_symlink())
        self.assertEqual(manifest["sdk"], {"version": C.SDK_VERSION, "route": "link"})
        self.assertEqual(manifest["claude"]["version"], "2.1.296 (Claude Code)")
        self.assertEqual(manifest["promptfoo"]["version"], "0.124.0")
        self.assertEqual(set(manifest["servers"]), set(C.SERVERS))
        for name in e1_prepare.WORK_DIRS:
            self.assertEqual(stat.S_IMODE((root / name).stat().st_mode), 0o700, name)
        self.assertEqual(sha256_bytes(root / "settings.json"), manifest["settings_sha256"])

    def test_the_fence_denies_home_and_every_sibling_of_the_root_but_not_the_root(self):
        sibling = self.s.work / "another-lanes-files"
        sibling.mkdir()
        self.assertEqual(self.s.prepare().returncode, 0)
        settings = json.loads((self.s.root / "settings.json").read_text())
        deny, read = settings["permissions"]["deny"], settings["sandbox"]["filesystem"]["denyRead"]
        self.assertIn("Read(/" + str(self.s.home) + "/**)", deny)
        self.assertIn("Edit(/" + str(self.s.home) + "/**)", deny)
        self.assertIn("Read(/" + str(sibling) + "/**)", deny)
        self.assertIn("Read(//tmp/**)", deny)
        self.assertIn(str(self.s.home), read)
        self.assertIn(str(sibling), read)
        self.assertFalse([d for d in deny if str(self.s.root) in d])
        self.assertNotIn(str(self.s.root), read)
        self.assertEqual(settings["sandbox"]["enabled"], True)
        self.assertEqual(settings["sandbox"]["failIfUnavailable"], True)
        self.assertEqual(settings["sandbox"]["allowUnsandboxedCommands"], False)
        self.assertEqual(settings["sandbox"]["network"], {"allowedDomains": [], "strictAllowlist": True})
        self.assertEqual(settings["permissions"]["allow"], ["Bash", "mcp__serena", "mcp__semble", "mcp__codebase-memory-mcp", "mcp__jcodemunch", "ToolSearch"])

    def test_settings_for_is_a_function_of_the_root_its_siblings_and_the_home_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "r"
            root.mkdir()
            (Path(tmp) / "s1").mkdir()
            settings = e1_prepare.settings_for(root, Path("/home/example"))
            self.assertEqual(settings["sandbox"]["filesystem"]["denyRead"], sorted(["/home/example", str(Path(tmp) / "s1")]))
            self.assertEqual(settings["sandbox"]["filesystem"]["allowRead"], [])

    def test_prepare_refuses_each_unsafe_or_wrong_input_and_writes_nothing(self):
        s = self.s
        wrong_client = s.script("claude-old", 'echo "2.1.295 (Claude Code)"')
        old_promptfoo = s.script("promptfoo-old", 'echo "0.123.1"')
        no_version = s.script("promptfoo-none", 'echo "no version here"')
        cases = {
            "the root inside the repository": (dict(root=s.repo / "inside"), "inside the repository"),
            "the root inside HOME": (dict(root=s.home / "root"), "inside $HOME"),
            "a client of another version": (dict(claude=wrong_client), "preregistered client"),
            "a promptfoo without copy_working_dir": (dict(promptfoo=old_promptfoo), "older than 0.124.0"),
            "a promptfoo that reports no version": (dict(promptfoo=no_version), "unknown version"),
            "no SDK source and no npm": (dict(sdk=False), "npm is not on PATH"),
        }
        for label, (kwargs, reason) in cases.items():
            done = s.prepare(**kwargs)
            self.assertEqual(done.returncode, 2, label)
            self.assertIn(reason, done.stderr, label)
        self.assertFalse(s.root.exists(), "a refusal creates no root")
        self.assertFalse((s.repo / "inside").exists())
        self.assertFalse((s.home / "root").exists())

    def test_prepare_refuses_a_wrong_sdk_version_a_missing_server_and_a_missing_commit(self):
        s = self.s
        (s.sdk / "package.json").write_text(json.dumps({"name": "x", "version": "0.3.1"}))
        done = s.prepare()
        self.assertEqual(done.returncode, 2)
        self.assertIn(C.SDK_VERSION, done.stderr)
        self.assertFalse(s.root.exists(), "the SDK is checked before anything is built")
        (s.sdk / "package.json").unlink()
        self.assertIn("package.json", s.prepare().stderr)
        (s.sdk / "package.json").write_text(json.dumps({"name": "x", "version": C.SDK_VERSION}))
        (s.bin / "semble").unlink()
        done = s.prepare(root=s.work / "other")
        self.assertEqual(done.returncode, 2)
        self.assertIn("semble", done.stderr)
        self.script_restore = s.script("semble", "exit 0")
        tasks = json.loads((s.e1 / "tasks.json").read_text())
        tasks["stale"] = "0" * 40
        (s.e1 / "tasks.json").write_text(json.dumps(tasks))
        done = s.prepare(root=s.work / "third")
        self.assertEqual(done.returncode, 2)
        self.assertIn("stale commit", done.stderr)

    def test_an_existing_root_needs_rebuild_and_a_foreign_directory_is_never_touched(self):
        s = self.s
        self.assertEqual(s.prepare().returncode, 0)
        again = s.prepare()
        self.assertEqual(again.returncode, 2)
        self.assertIn("--rebuild", again.stderr)
        self.assertEqual(s.prepare("--rebuild").returncode, 0)
        foreign = s.work / "foreign"
        foreign.mkdir()
        (foreign / "keep.txt").write_text("someone else's file\n")
        done = s.prepare("--rebuild", root=foreign)
        self.assertEqual(done.returncode, 2)
        self.assertEqual((foreign / "keep.txt").read_text(), "someone else's file\n")
        self.assertEqual(sorted(p.name for p in foreign.iterdir()), ["keep.txt"])

    def test_a_dry_run_checks_and_writes_nothing(self):
        done = self.s.prepare("--dry-run")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(json.loads(done.stdout)["dry_run"])
        self.assertFalse(self.s.root.exists())
        bad = self.s.prepare("--dry-run", claude=self.s.script("claude-bad", 'echo "9.9.9"'))
        self.assertEqual(bad.returncode, 2)

    def test_a_copy_of_the_scripts_outside_a_repository_has_no_repo_root_and_asks_for_the_repo_and_the_credential_runner(self):
        s = self.s
        done = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import e1_common; print(e1_common.REPO_ROOT)", str(s.e1)], capture_output=True, text=True, env=s.env, timeout=60)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "None"), done.stderr)
        cmd = [sys.executable, "-I", str(s.e1 / "e1_prepare.py"), "--root", str(s.root), "--claude", str(s.claude), "--semble-model", str(s.semble), "--promptfoo", str(s.promptfoo), "--sdk-from", str(s.sdk)]
        done = subprocess.run(cmd, capture_output=True, text=True, env=s.env, timeout=60)
        self.assertEqual(done.returncode, 2)
        self.assertIn("--repo is required", done.stderr)
        self.assertFalse(s.root.exists())
        self.assertEqual(s.prepare().returncode, 0)
        done = s.run("--preflight", "--slot", "some-slot", "--dry-run")
        self.assertEqual(done.returncode, 2)
        self.assertIn("credential_run.py was not found", done.stderr)
        self.assertEqual(s.run("--preflight", "--slot", "some-slot", "--credential-runner", str(CREDENTIAL_RUNNER), "--dry-run").returncode, 0)

    def test_run_refuses_a_root_that_was_not_prepared_or_has_drifted(self):
        s = self.s
        self.assertEqual(s.run("--preflight", "--dry-run").returncode, 2)
        self.assertEqual(s.prepare().returncode, 0)
        self.assertEqual(s.run("--preflight", "--dry-run").returncode, 0)
        config = s.root / "config" / "promptfooconfig.yaml"
        original = config.read_text()
        config.write_text(original + "\n# edited after prepare\n")
        done = s.run("--preflight", "--dry-run")
        self.assertEqual(done.returncode, 2)
        self.assertIn("promptfooconfig.yaml", done.stderr)
        config.write_text(original)
        settings = s.root / "settings.json"
        saved = settings.read_text()
        settings.write_text(saved.replace('"enabled": true', '"enabled": false'))
        self.assertIn("settings.json", s.run("--preflight", "--dry-run").stderr)
        settings.write_text(saved)
        (s.root / "trees" / "base" / "stray.txt").write_text("written by a run\n")
        done = s.run("--preflight", "--dry-run")
        self.assertEqual(done.returncode, 2)
        self.assertIn("tree base", done.stderr)
        (s.root / "trees" / "base" / "stray.txt").unlink()
        (s.root / "trees" / "base-serena" / "CLAUDE.local.md").unlink()
        self.assertIn("tree base-serena", s.run("--preflight", "--dry-run").stderr)
        (s.root / "trees" / "base-serena" / "CLAUDE.local.md").write_text((E1 / "directives" / "serena.md").read_text())
        self.assertEqual(s.run("--preflight", "--dry-run").returncode, 0)
        subprocess.run(["git", "-C", str(s.root / "trees" / "stale"), "checkout", "-q", "--detach", s.base], check=True, capture_output=True)  # clean, but at the other commit
        done = s.run("--preflight", "--dry-run")
        self.assertEqual(done.returncode, 2)
        self.assertIn("not at the commit", done.stderr)

    def test_a_failed_preflight_row_keeps_promptfoos_exit_status_and_a_failed_question_row_does_not(self):
        """Review of #1046 at 38f4151a (P1): promptfoo exits 100 when at least one test failed (promptfoo@30949931ee90 site/docs/usage/command-line.md L171); a pre-flight row that fails is a wiring
        defect that automation must see, a question row whose answer is wrong is a measurement."""
        s = self.s
        failing = s.script("promptfoo-failing", 'if [ "$1" = "eval" ]; then exit 100; fi\necho "0.124.0"')
        self.assertEqual(s.prepare(promptfoo=failing).returncode, 0)
        pre = s.run("--preflight")
        self.assertEqual(pre.returncode, 100, pre.stderr)
        self.assertIn("promptfoo exited 100", pre.stderr)
        questions = s.run("--questions")
        self.assertEqual(questions.returncode, 0, questions.stderr)
        broken = s.script("promptfoo-broken", 'if [ "$1" = "eval" ]; then exit 1; fi\necho "0.124.0"')
        self.assertEqual(s.prepare("--rebuild", promptfoo=broken).returncode, 0)
        self.assertEqual(s.run("--preflight").returncode, 1)
        self.assertEqual(s.run("--questions").returncode, 1, "any other status is kept in both stages")

    def test_run_refuses_a_root_that_was_copied_or_moved_but_accepts_another_name_for_the_same_directory(self):
        """Review of #1046 at 38f4151a (P2): settings.json is bound to the recorded root and its siblings."""
        s = self.s
        self.assertEqual(s.prepare().returncode, 0)
        copy = s.work / "copy"
        shutil.copytree(s.root, copy, symlinks=True)

        def run_at(root):
            return subprocess.run([sys.executable, "-I", str(s.e1 / "e1_run.py"), "--root", str(root), "--preflight", "--dry-run"], capture_output=True, text=True, env=s.env, timeout=120)
        done = run_at(copy)
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("manifest recorded", done.stderr)
        self.assertIn("--rebuild", done.stderr)
        link = s.work / "link"
        link.symlink_to(s.root)
        self.assertEqual(run_at(link).returncode, 0, "a symbolic link to the prepared directory is the same directory")
        moved = s.work / "moved"
        s.root.rename(moved)
        self.assertEqual(run_at(moved).returncode, 2)

    def test_prepare_records_absolute_paths_for_tools_given_relative_to_the_working_directory(self):
        """Review of #1046 at 38f4151a (P2): e1_run.py starts promptfoo from <root>/config, so a relative spelling recorded by prepare would not resolve."""
        s = self.s
        cmd = [sys.executable, "-I", str(s.e1 / "e1_prepare.py"), "--root", "work/root", "--claude", "bin/claude", "--semble-model", "semble-model", "--repo", str(s.repo),
               "--promptfoo", "bin/promptfoo-bin", "--sdk-from", "sdk"]
        done = subprocess.run(cmd, capture_output=True, text=True, env=s.env, cwd=s.tmp, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        manifest = json.loads((s.root / "manifest.json").read_text())
        self.assertEqual((manifest["claude"]["path"], manifest["promptfoo"]["path"], manifest["semble_model"]), (str(s.claude), str(s.promptfoo), str(s.semble)))
        for path in (manifest["claude"]["path"], manifest["promptfoo"]["path"], manifest["semble_model"], *manifest["servers"].values()):
            self.assertTrue(os.path.isabs(path), path)
        plan = json.loads(s.run("--preflight", "--dry-run").stdout)
        self.assertEqual(plan["command"][0], str(s.promptfoo))

    def test_run_dry_run_prints_the_command_the_variables_it_sets_and_removes(self):
        s = self.s
        self.assertEqual(s.prepare().returncode, 0)
        env = {**s.env, "CLAUDE_CODE_EFFORT_LEVEL": "max", "ANTHROPIC_BASE_URL": "http://127.0.0.1:1"}
        done = s.run("--questions", "--arms", "A1,A5", "--ids", "p-def,p-refs", "--repeats", "2", "--slot", "some-slot", "--credential-runner", str(CREDENTIAL_RUNNER), "--dry-run", env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        plan = json.loads(done.stdout)
        cmd = plan["command"]
        self.assertEqual(cmd[1:3], ["-I", str(CREDENTIAL_RUNNER)])
        self.assertEqual(cmd[3:5], ["some-slot", "--"])
        eval_cmd = cmd[5:]
        self.assertEqual(eval_cmd[1], "eval")
        self.assertEqual(eval_cmd[eval_cmd.index("-c") + 1], str(s.root / "config" / "promptfooconfig.yaml"))
        for flag in ("--no-cache", "--no-share", "--no-write", "--no-table", "--no-progress-bar"):
            self.assertIn(flag, eval_cmd)
        self.assertEqual(eval_cmd[eval_cmd.index("--max-concurrency") + 1], "1")
        self.assertEqual(eval_cmd[eval_cmd.index("--filter-providers") + 1], "^(A1|A5)$")
        self.assertEqual(eval_cmd[eval_cmd.index("--filter-metadata") + 1], "kind=question")
        self.assertEqual(eval_cmd[eval_cmd.index("--filter-pattern") + 1], "^(?:p\\-def|p\\-refs) r[1-2]$")
        self.assertTrue(eval_cmd[eval_cmd.index("-o") + 1].startswith(str(s.root / "out" / "questions-")))
        self.assertIn("CLAUDE_CODE_EFFORT_LEVEL", plan["removes"])
        self.assertIn("ANTHROPIC_BASE_URL", plan["removes"])
        for name in ("E1_ROOT", "E1_CLAUDE", "E1_SEMBLE_MODEL", "TMPDIR", "PROMPTFOO_CONFIG_DIR", "PROMPTFOO_DISABLE_TELEMETRY", "PROMPTFOO_DISABLE_UPDATE", "PROMPTFOO_DISABLE_SHARING", "CLAUDE_CODE_TMPDIR"):
            self.assertIn(name, plan["sets"])
        pre = json.loads(s.run("--preflight", "--dry-run").stdout)["command"]
        self.assertEqual(pre[pre.index("--filter-metadata") + 1], "kind=preflight")
        self.assertNotIn("--filter-pattern", pre)
        self.assertEqual(pre[0], str(s.promptfoo), "without --slot promptfoo is started directly")

    def test_run_refuses_unknown_arms_unknown_questions_and_repeat_counts_out_of_range(self):
        s = self.s
        self.assertEqual(s.prepare().returncode, 0)
        for args, reason in ((("--questions", "--arms", "A1,A2n"), "unknown arm"), (("--questions", "--ids", "p-def,x-none"), "unknown question"), (("--questions", "--repeats", "0"), "--repeats"),
                             (("--questions", "--repeats", "10"), "--repeats")):
            done = s.run(*args, "--dry-run")
            self.assertEqual(done.returncode, 2, args)
            self.assertIn(reason, done.stderr, args)
        self.assertEqual(s.run("--preflight", "--questions").returncode, 2, "the two stages are exclusive")

    def test_run_starts_promptfoo_in_the_staged_config_with_a_clean_environment_and_treats_exit_100_of_the_questions_as_a_result(self):
        s = self.s
        self.assertEqual(s.prepare().returncode, 0)
        record = s.work / "seen.json"
        s.script("promptfoo-bin", 'if [ "$1" = "--version" ]; then echo "0.124.0"; exit 0; fi\n'
                                   f'{sys.executable} -I -c \'import json,os,sys; json.dump({{"argv": sys.argv[1:], "cwd": os.getcwd(), "env": {{k: os.environ.get(k) for k in ("E1_ROOT","TMPDIR","CLAUDE_CODE_EFFORT_LEVEL","ANTHROPIC_BASE_URL","MCP_TIMEOUT","PROMPTFOO_DISABLE_SHARING")}}}}, open("{record}", "w"))\' "$@"\n'
                                   "exit ${FAKE_STATUS:-0}")
        env = {**s.env, "CLAUDE_CODE_EFFORT_LEVEL": "max", "ANTHROPIC_BASE_URL": "http://127.0.0.1:1", "FAKE_STATUS": "100"}
        done = s.run("--questions", env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        seen = json.loads(record.read_text())
        self.assertEqual(seen["cwd"], str((s.root / "config").resolve()))
        self.assertEqual(seen["argv"][0], "eval")
        self.assertIsNone(seen["env"]["CLAUDE_CODE_EFFORT_LEVEL"])
        self.assertIsNone(seen["env"]["ANTHROPIC_BASE_URL"])
        self.assertEqual(seen["env"]["E1_ROOT"], str(s.root))
        self.assertEqual(seen["env"]["TMPDIR"], str(s.root / "tmp"))
        self.assertEqual(seen["env"]["MCP_TIMEOUT"], "120000")
        self.assertEqual(seen["env"]["PROMPTFOO_DISABLE_SHARING"], "1")
        self.assertEqual(s.run("--questions", env={**env, "FAKE_STATUS": "7"}).returncode, 7, "any other status is a fault and is passed on")
        self.assertEqual(s.run("--preflight", env=env).returncode, 100, "a failed pre-flight row keeps promptfoo's status (review of #1046, P1)")

    def test_the_test_pattern_selects_the_descriptions_of_the_asked_questions_and_repeats_only(self):
        pattern = re.compile(e1_run.test_pattern(["p-def"], 2))
        self.assertTrue(pattern.match("p-def r1") and pattern.match("p-def r2"))
        self.assertFalse(pattern.match("p-def r3"))
        self.assertFalse(pattern.match("r-def-1 r1"))
        self.assertFalse(pattern.match("p-defx r1"))
        every = re.compile(e1_run.test_pattern([], 3))
        self.assertTrue(every.match("r-callers-2 r3") and not every.match("preflight") and not every.match("p-def r4"))


@unittest.skipUnless(PROMPTFOO, "promptfoo 0.124.0 or newer is not installed")
class PromptfooIntegrationTests(unittest.TestCase):
    """The configs against the real promptfoo: they load, the skeletons refuse, and a stub provider drives the generator, the assertions and the decision script end to end."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="e-series-pf-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.env = {**CLEAN_ENV, "PROMPTFOO_CONFIG_DIR": str(self.tmp / "state"), "PROMPTFOO_DISABLE_TELEMETRY": "1", "PROMPTFOO_DISABLE_UPDATE": "1", "PROMPTFOO_DISABLE_SHARING": "1",
                    "E1_ROOT": str(self.tmp / "root"), "E1_CLAUDE": "/bin/true", "E1_SEMBLE_MODEL": str(self.tmp)}

    def validate(self, config: Path, extra_env=None):
        return subprocess.run([PROMPTFOO, "validate", "config", "-c", str(config)], capture_output=True, text=True, env={**self.env, **(extra_env or {})}, timeout=180)

    def test_the_e1_config_is_valid(self):
        done = self.validate(E1 / "promptfooconfig.yaml")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("Configuration is valid", done.stdout)

    def test_each_skeleton_refuses_without_frozen_inputs_and_is_valid_with_them(self):
        frozen = self.tmp / "frozen"
        frozen.mkdir()
        for experiment in F.DESIGNS:
            done = self.validate(ES / experiment / "promptfooconfig.yaml")
            self.assertNotEqual(done.returncode, 0, experiment)
            self.assertIn("is not frozen", done.stdout + done.stderr, experiment)
            FrozenInputsTests.freeze(self, frozen, experiment, rows=[{"vars": {"question": "q", "task": "t", "prompt": "p"}}])
            ok = self.validate(ES / experiment / "promptfooconfig.yaml", {"E_SERIES_FROZEN": str(frozen)})
            self.assertEqual(ok.returncode, 0, experiment + ok.stdout + ok.stderr)

    def test_a_stub_provider_drives_the_generator_the_assertions_and_the_decision_script(self):
        stage = self.tmp / "stage"
        shutil.copytree(E1, stage, ignore=shutil.ignore_patterns("__pycache__", "promptfooconfig.yaml"))
        (stage / "stub_provider.py").write_text(STUB_PROVIDER)
        (stage / "promptfooconfig.yaml").write_text(STUB_CONFIG)
        out = self.tmp / "out.json"
        done = subprocess.run([PROMPTFOO, "eval", "-c", str(stage / "promptfooconfig.yaml"), "--no-cache", "--no-share", "--no-write", "--no-table", "--no-progress-bar", "--max-concurrency", "1",
                               "-o", str(out)], capture_output=True, text=True, env=self.env, cwd=stage, timeout=300)
        self.assertIn(done.returncode, (0, 100), done.stdout + done.stderr)
        results = json.loads(out.read_text())["results"]["results"]
        self.assertEqual(len(results), 2 * 13)  # (1 preflight + 12 questions x 1 repeat) x 2 arms
        verdicts = {(r["provider"]["label"], r["testCase"]["description"]): r["gradingResult"]["pass"] for r in results}
        self.assertTrue(verdicts[("A0b", "preflight")])
        self.assertFalse(verdicts[("A5", "preflight")], "the stub lists servers for A5, which has none: the arm label reaches the assertion")
        self.assertTrue(verdicts[("A0b", "p-def r1")])
        self.assertFalse(verdicts[("A5", "p-def r1")], "the stub answers A5 wrongly: the question id reaches the assertion")
        runs, faults = e1_decide.load_runs([out], TASKS)
        self.assertEqual(faults, [])
        self.assertEqual(len(runs), 2 * 12)
        by = {(r["arm"], r["q"]): r for r in runs}
        self.assertTrue(by[("A0b", "p-def")]["correct"])
        self.assertFalse(by[("A5", "p-def")]["correct"])
        self.assertEqual(by[("A0b", "p-def")]["cost"], 0.05)
        self.assertEqual(by[("A0b", "p-def")]["turns"], 3)
        self.assertTrue(by[("A0b", "p-refs")]["nav"], "a tool named mcp__serena__* in toolCalls is a code-navigation call")
        self.assertFalse(by[("A0b", "p-def")]["nav"])


STUB_CONFIG = """description: stub
prompts:
  - label: worktree-start
    raw: 'Question: {{ question }}'
providers:
  - {id: file://stub_provider.py, label: A0b, prompts: [worktree-start], config: {label: A0b}}
  - {id: file://stub_provider.py, label: A5, prompts: [worktree-start], config: {label: A5}}
tests:
  - path: file://e1_tests.py:create_tests
    config: {repeats: 1}
"""

STUB_PROVIDER = '''import json
from pathlib import Path

TASKS = {q["id"]: q for q in json.loads((Path(__file__).with_name("tasks.json")).read_text())["questions"]}
FOUR = "mcp__serena__find_symbol mcp__semble__search mcp__codebase-memory-mcp__search_graph mcp__jcodemunch__search_symbols"


def call_api(prompt, options, context):
    arm = (options.get("config") or {}).get("label")
    qid = (context.get("vars") or {}).get("question_id")
    calls = ["Grep"]
    if qid == "preflight":
        output, calls = {"answer": "TOOLS: " + FOUR + "\\nDIRECTIVE: NONE", "citations": []}, ["ToolSearch"]
    elif qid not in ("p-def", "p-refs", "p-explain", "p-callers"):
        output = {"answer": "x", "citations": []}
    else:
        gold = TASKS[qid]["gold"]
        output = {"answer": "x", "citations": [{"file": gold["file"], "line": gold["line"]}]} if qid == "p-def" else {"answer": "x", "citations": []}
        if arm == "A5":
            output = {"answer": "x", "citations": []}
        if qid == "p-refs":
            calls.append("mcp__serena__find_referencing_symbols")
    return {"output": output, "cost": 0.05, "metadata": {"toolCalls": [{"name": n} for n in calls], "numTurns": 3, "durationMs": 1000}}
'''


if __name__ == "__main__":
    unittest.main()
