"""Regression contracts for the CC-adjudicated W6 comparison records.

The tests use Python's existing unittest path. They qualify record consistency,
not a source task, model, runtime, or comparison outcome.
"""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "evidence/artifacts/w6-layer-verdict-20261011"
BAD_REFS = (
    ("vllm-project/vllm", "test_ref", "pyproject.toml:63"),
    ("giancarloerra/socraticode", "test_ref", "README.md:1355"),
    ("vshulcz/deja-vu", "test_ref", "README.md:274"),
    ("mibayy/token-savior", "test_ref", "README.md:187"),
    ("rohitg00/agentmemory", "test_ref", "README.md:922"),
    ("openai/codex", "test_ref", "justfile:47"),
    ("anthropics/claude-plugins-official", "role_ref", "README.md:5"),
    ("microsoft/markitdown", "role_ref", "README.md:8"),
    ("tsdgeos/poppler_mirror", "role_ref", "README.md:16"),
    ("baidu/unlimited-ocr", "role_ref", "README.md:85"),
    ("openai/codex", "role_ref", "README.md:64"),
    ("giancarloerra/socraticode", "role_ref", "README.md:36"),
    ("vllm-project/vllm", "role_ref", "README.md:14"),
    ("osu-nlp-group/hipporag", "role_ref", "README.md:6"),
    ("vectorize-io/hindsight", "role_ref", "README.md:5"),
    ("opendatalab/mineru", "install_ref", "README.md:74"),
    ("alibaba/logics-parsing", "install_ref", "README.md:137"),
    ("exa-labs/exa-mcp-server", "install_ref", "package.json:41"),
    ("microsoft/markitdown", "install_ref", "README.md:51"),
)


def load(name):
    return json.loads((ARTIFACT / name).read_text(encoding="utf-8"))


class W6RecordContracts(unittest.TestCase):
    def test_known_false_citations_are_withdrawn_or_corrected(self):
        sources = load("primary-sources.json")["sources"]
        by_repo = {s["repository"].removeprefix("https://github.com/").lower(): s for s in sources}
        for repo, field, bad in BAD_REFS:
            with self.subTest(repo=repo, field=field):
                self.assertNotEqual(by_repo[repo][field], bad)

    def test_frozen_roles_define_dependency_and_check_applicability(self):
        for path in sorted((ARTIFACT / "comparisons").glob("*.json")):
            config = json.loads(path.read_text(encoding="utf-8"))
            roles = config["role_checks"]
            for arm in config["arms"]:
                with self.subTest(layer=config["layer_id"], arm=arm["repository"]):
                    self.assertIsInstance(arm["dependency"], bool)
                    self.assertTrue(arm["role_ids"])
                    for role in arm["role_ids"]:
                        self.assertIn(role, roles)
                        self.assertTrue(roles[role]["mandatory_checks"])
                        self.assertTrue(roles[role]["case_ids"])
                        self.assertTrue(set(roles[role]["case_ids"]).issubset(range(len(config["cases"]))))

    def test_casefold_identity_deduplicates_the_same_source_arm(self):
        for path in sorted((ARTIFACT / "comparisons").glob("*.json")):
            config = json.loads(path.read_text(encoding="utf-8"))
            keys = [(a["repository"].lower(), a["pin"]) for a in config["arms"]]
            self.assertEqual(len(keys), len(set(keys)), config["layer_id"])

    def test_identical_case_sets_share_competing_roles(self):
        for path in sorted((ARTIFACT / "comparisons").glob("*.json")):
            config = json.loads(path.read_text(encoding="utf-8"))
            checks = config["role_checks"]
            candidates = [arm for arm in config["arms"] if not arm["dependency"]]
            for arm in candidates:
                covered = set().union(*(set(checks[role]["case_ids"]) for role in arm["role_ids"]))
                own_sets = [set(checks[role]["case_ids"]) for role in arm["role_ids"]]
                expected = {role for role, check in checks.items() if set(check["case_ids"]) in own_sets}
                # A singleton alias must not hide a comparison spanning several
                # incumbent roles. Overlapping multi-role coverage by itself
                # does not establish another capability (for example indexing).
                if len(arm["role_ids"]) == 1:
                    for other in candidates:
                        other_cases = set().union(*(set(checks[role]["case_ids"]) for role in other["role_ids"]))
                        if covered == other_cases:
                            expected.update(other["role_ids"])
                with self.subTest(layer=config["layer_id"], arm=arm["repository"]):
                    self.assertTrue(expected.issubset(arm["role_ids"]),
                                    f"same-case roles excluded from ranking: {expected.difference(arm['role_ids'])}")

    def test_pinned_readme_roles_enter_the_same_role_comparison(self):
        expected = (
            ("semantic-rag", "lightonai/next-plaid", "semantic_code_retrieval", "README.md:22"),
            ("durable-memory", "mempalace/mempalace", "native_memory_capture", "README.md:311-316"),
        )
        for layer, repo, role, source_ref in expected:
            config = load(f"comparisons/{layer}.json")
            arm = next(a for a in config["arms"] if a["repository"].lower().endswith("/" + repo))
            with self.subTest(layer=layer, arm=repo):
                self.assertIn(role, arm["role_ids"])
                witness = arm["role_source_witnesses"][role]
                self.assertEqual(witness["ref"], source_ref)
                self.assertEqual(witness["pin"], arm["pin"])
                self.assertTrue(witness["source_file_sha256"])
                self.assertTrue(witness["lines"])

    def test_current_host_memory_candidates_are_not_dropped_by_mac_nonselection(self):
        config = load("comparisons/durable-memory.json")
        arms = {a["repository"].lower() for a in config["arms"]}
        for repo in ("langchain-ai/langmem", "rohitg00/agentmemory", "mempalace/mempalace", "vectorize-io/hindsight"):
            self.assertIn("https://github.com/" + repo, arms)
        self.assertIs(config["fixed_decision_rule"]["incumbent_protection"], False)
        self.assertIs(config["model_policy"]["use_newest_supported_from_frozen_universe"], True)

    def test_terminal_review_metadata_comes_from_landed_view(self):
        for row in load("resolution-delta.json")["layers"]:
            self.assertEqual(row["next_review"], "2026-10-22")
            self.assertEqual(row["terminal_state"], "SCHEDULED")
            evidence = row["terminal_evidence"]
            self.assertEqual(evidence["final_stack_source"]["commit"], "c2dee173")
            self.assertEqual(row["next_review"], evidence["final_stack_source"]["row"]["next_review"])
            for winner in evidence["final_stack_source"]["row"]["winners"]:
                self.assertIn(winner["component_id"], evidence["run_pin_reconciliation"])
                self.assertTrue(evidence["run_pin_reconciliation"][winner["component_id"]]["reason"])


if __name__ == "__main__":
    unittest.main()
