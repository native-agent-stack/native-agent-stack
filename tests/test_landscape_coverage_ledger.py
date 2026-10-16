"""The step-1 coverage ledger gives every seed exactly one disposition, and its counts reconcile with their records.

test_committed_ledger_is_clean is the approved plan's step-1 test: every seed has a disposition, no UNMAPPED seed
lacks a step-2 cluster, and the counts reconcile with the grand catalog (4,606/4,058/401/45; F3 797 -> 769 rows),
with coverage-accounting (12 lists, 7,028/6,939 at their pins) and with each list's census at its pin.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ledger_tool = _load("landscape_coverage_ledger_under_test", ROOT / "tools" / "landscape" / "coverage_ledger.py")


def _committed_ledger() -> dict:
    return json.loads(ledger_tool.newest_ledger(ROOT).read_text(encoding="utf-8"))


class CommittedLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stale: list[str] = []
        cls.problems = ledger_tool.check(ROOT, cls.stale)
        cls.ledger = _committed_ledger()
        cls.lists = json.loads((ROOT / cls.ledger["inputs"]["outputs"]["lists"]).read_text(encoding="utf-8"))

    def test_committed_ledger_is_clean(self):
        self.assertEqual(self.problems, [])

    def test_every_seed_has_exactly_one_disposition_and_unmapped_seeds_have_clusters(self):
        rows = self.ledger["seeds"]
        self.assertEqual(sum(self.ledger["counts"]["by_disposition"].values()), len(rows))
        self.assertTrue(all(row["disposition"] in ledger_tool.DISPOSITIONS for row in rows))
        clusters = {cluster["id"] for cluster in self.ledger["clusters"]}
        self.assertTrue(all(row.get("cluster") in clusters for row in rows if row["disposition"] == "UNMAPPED"))

    def test_grand_catalog_and_f3_reconcile(self):
        grand = self.ledger["reconciliation"]["grand"]
        self.assertEqual((grand["rows"], grand["by_disposition"]["PENDING"], grand["by_disposition"]["WATCH"],
                          grand["backlog_slots"], grand["backlog_slugs"], grand["backlog_entries"]),
                         (4606, 4058, 401, 45, 2925, 58))
        self.assertEqual((grand["f3_occurrence_ids"], grand["f3_rows"], grand["f3_entries"],
                          grand["f3_entries_outside_backlog"]), (797, 769, 570, 0))

    def test_coverage_accounting_and_the_generic_lists_reconcile_at_their_pins(self):
        accounting = self.lists["coverage_accounting"]
        self.assertEqual((accounting["lists"], accounting["recorded_unique"], accounting["recorded_unassessed"]),
                         (12, 7028, 6939))
        generic = [entry for item in self.lists["lists"] for entry in item["census"]
                   if entry.get("recorded_parser", "").startswith("screen_generic.py@")]
        self.assertEqual(len(generic), 14)
        self.assertTrue(all(entry["delta"] == 0 for entry in generic))
        self.assertEqual(sum(entry["recorded"] for entry in generic), 25856)
        g5 = self.lists["g5_generic_ledger"]
        self.assertEqual((g5["recorded"], g5["rederived"], g5["same_disposition"]), (2952, 2952, 2952))

    def test_universe_decomposition_sums_to_the_layer_candidate_repositories(self):
        universe = self.ledger["reconciliation"]["universe"]
        self.assertEqual(universe["total"], self.ledger["counts"]["layer_candidate_repositories"])
        self.assertEqual(universe["steps"][-1]["cumulative"], universe["total"])


class CheckRowsTests(unittest.TestCase):
    def setUp(self):
        self.ledger = copy.deepcopy(CommittedLedgerTests.ledger if hasattr(CommittedLedgerTests, "ledger")
                                    else _committed_ledger())
        self.layers = ledger_tool.layer_universe(ROOT)

    def first(self, disposition):
        return next(row for row in self.ledger["seeds"] if row["disposition"] == disposition)

    def test_the_committed_rows_pass(self):
        self.assertEqual(ledger_tool.check_rows(self.ledger, self.layers), [])

    def test_a_missing_disposition_is_a_problem(self):
        self.first("LAYER-CANDIDATE").pop("disposition")
        self.assertTrue(any("is not one of" in problem for problem in ledger_tool.check_rows(self.ledger, self.layers)))

    def test_an_unmapped_seed_without_its_cluster_or_reason_is_a_problem(self):
        for field in ("cluster", "reason"):
            with self.subTest(field=field):
                ledger = copy.deepcopy(self.ledger)
                next(row for row in ledger["seeds"] if row["disposition"] == "UNMAPPED").pop(field)
                self.assertTrue(any("UNMAPPED without its reason and step-2 cluster" in problem
                                    for problem in ledger_tool.check_rows(ledger, self.layers)))

    def test_a_non_github_row_needs_layers_reason_and_a_url_seed(self):
        for change in ("layers", "reason", "seed"):
            with self.subTest(change=change):
                ledger = copy.deepcopy(self.ledger)
                row = next(row for row in ledger["seeds"] if row["disposition"] == "NON-GITHUB")
                if change == "seed":
                    row["seed"] = "owner/not-a-url"
                else:
                    row.pop(change)
                self.assertTrue(any("NON-GITHUB needs" in problem
                                    for problem in ledger_tool.check_rows(ledger, self.layers)))

    def test_a_layer_outside_the_landscape_is_a_problem(self):
        self.first("LAYER-CANDIDATE")["layers"] = ["not-a-layer"]
        self.assertTrue(any("layer ids" in problem for problem in ledger_tool.check_rows(self.ledger, self.layers)))

    def test_counts_must_equal_the_rows(self):
        self.ledger["counts"]["seeds"] += 1
        self.assertIn("ledger counts differ from the rows", ledger_tool.check_rows(self.ledger, self.layers))


class StaleAndFrozenInputTests(unittest.TestCase):
    """A changed star snapshot makes the ledger STALE (rebuilt later, with the clones); a changed frozen record fails."""

    def test_stale_and_frozen_inputs(self):
        ledger = _committed_ledger()
        needed = [str(ledger_tool.newest_ledger(ROOT).relative_to(ROOT)), *ledger["inputs"]["outputs"].values(),
                  *ledger_tool.SCHEMAS.values(), *ledger["inputs"]["committed"]]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in needed:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(ROOT / relative)
            stars = json.loads((ROOT / ledger_tool.STARS).read_text(encoding="utf-8"))
            stars["repositories"].append(dict(stars["repositories"][0], repository="fixture-owner/new-star"))
            (root / ledger_tool.STARS).unlink()
            (root / ledger_tool.STARS).write_text(json.dumps(stars), encoding="utf-8")
            accounting = json.loads((ROOT / ledger_tool.COVERAGE_ACCOUNTING).read_text(encoding="utf-8"))
            accounting["counts"]["discovery_only_unassessed"] += 1
            (root / ledger_tool.COVERAGE_ACCOUNTING).unlink()
            (root / ledger_tool.COVERAGE_ACCOUNTING).write_text(json.dumps(accounting), encoding="utf-8")
            stale: list[str] = []
            problems = ledger_tool.check(root, stale)
        self.assertEqual(stale, [f"{ledger_tool.STARS} changed since the ledger was built; rebuild it "
                                 "(coverage_ledger.py build)"])
        self.assertIn(f"{ledger_tool.COVERAGE_ACCOUNTING} changed since the ledger was built; rebuild it "
                      "(coverage_ledger.py build)", problems)
        self.assertFalse(any("public-starred" in problem for problem in problems))


class RuleTests(unittest.TestCase):
    def test_identity_rules(self):
        self.assertEqual(ledger_tool.slug("https://github.com/Owner/Repo.git"), "owner/repo")
        self.assertEqual(ledger_tool.slug("Owner/Repo@0123abc"), "owner/repo")
        self.assertIsNone(ledger_tool.slug("aannoo-hcom"))
        self.assertEqual(ledger_tool.identity_of("aannoo-hcom"), "entry:aannoo-hcom")
        rows = [{"repository_or_entry": "https://github.com/Owner/Tool"}]
        self.assertEqual(ledger_tool.master_seed_identity(
            "Owner/Tool@" + "a" * 40 + "; source=x; kind=new", rows), "owner/tool")
        self.assertEqual(ledger_tool.master_seed_identity(
            "tool-entry; source=" + ledger_tool.GRAND + "#/rows/0", rows), "owner/tool")

    def test_cited_repositories_use_the_parser_identity_rule(self):
        repo_from = _load("landscape_screen_generic_rules", ROOT / "tools/landscape/screen_generic.py").repo_from
        text = ("See https://github.com/Owner/Tool, github.com/topics/agents, https://github.com/a/b/issues/3 "
                "and http://[::1 then https://raw.githubusercontent.com/c/d/main/x.md.")
        self.assertEqual(ledger_tool.cited_repositories(text, repo_from), {"owner/tool", "a/b", "c/d"})

    def test_decide_precedence(self):
        layers = {"workers", "isolation"}
        decide = ledger_tool.decide

        def row(*mappings, cluster=None):
            return {"mappings": list(mappings), "cluster": cluster, "populations": {"runs": [1, "deer-flow/run.x"]}}

        self.assertEqual(decide("old/name", row(), {"old/name": "new/name"}, layers)["disposition"], "DUPLICATE")
        self.assertEqual(decide("a/b", row(("CARRIED", "retired", "rec#/0", "stars"),
                                           ("CARRIED", "layer", "workers", "grand")), {}, layers)["disposition"], "RETIRED")
        carried = decide("a/b", row(("PROPOSED", "layer", "isolation", "lists"),
                                    ("CARRIED", "layer", "workers", "grand")), {}, layers)
        self.assertEqual((carried["state"], carried["layers"]), ("CARRIED", ["workers"]))
        kept_out = decide("a/b", row(("CARRIED", "seed-out-of-scope", "Public star OUT-OF-SCOPE: a list", "stars"),
                                     ("CARRIED", "layer", "workers", "grand"),
                                     ("PROPOSED", "layer", "isolation", "lists")), {}, layers)
        self.assertEqual((kept_out["disposition"], kept_out["state"], kept_out["conflicts"]),
                         ("OUT-OF-SCOPE", "CARRIED", ["layer:grand"]))
        verdict = decide("a/b", row(("CARRIED", "seed-out-of-scope", "Public star OUT-OF-SCOPE: a list", "stars"),
                                    ("CARRIED", "layer", "workers", "final-stack")), {}, layers)
        self.assertEqual((verdict["disposition"], verdict["conflicts"]), ("LAYER-CANDIDATE", ["out-of-scope:stars"]))
        slot_scoped = decide("a/b", row(("CARRIED", "out-of-scope", "Grand catalog OUT-OF-SCOPE row", "grand"),
                                        ("CARRIED", "layer", "workers", "grand")), {}, layers)
        self.assertEqual(slot_scoped["disposition"], "LAYER-CANDIDATE")
        conflict = decide("a/b", row(("PROPOSED", "layer", "isolation", "lists"),
                                     ("PROPOSED", "out-of-scope", "vertical", "mcp-ledger")), {}, layers)
        self.assertEqual(conflict["conflicts"], ["out-of-scope:mcp-ledger"])
        unmapped = decide("a/b", row(cluster=("research", "deer-flow/run.x")), {}, layers)
        self.assertEqual((unmapped["disposition"], unmapped["state"], unmapped["reason_text"]),
                         ("UNMAPPED", "UNSCREENED", ledger_tool.UNMAPPED_REASONS["repository"]))
        with self.assertRaisesRegex(ledger_tool.LedgerError, "UNMAPPED without a step-2 cluster"):
            decide("a/b", row(), {}, layers)
        with self.assertRaisesRegex(ledger_tool.LedgerError, "unknown layer ids"):
            decide("a/b", row(("PROPOSED", "layer", "nowhere", "lists")), {}, layers)

    def test_pass_flag_follows_the_dispatch_assertion(self):
        passes = ledger_tool.passes_dispatch_assertion
        self.assertIsNone(passes(None, "answer"))
        self.assertTrue(passes({"integration_assertion_pass": True, "cited_retrieved_url_matches": 2}, "answer"))
        self.assertFalse(passes({"integration_assertion_pass": True, "cited_retrieved_url_matches": 0}, "answer"))
        self.assertFalse(passes({"integration_assertion_pass": True, "cited_retrieved_url_matches": True}, "answer"))
        self.assertFalse(passes({"integration_assertion_pass": "true", "cited_retrieved_url_matches": 2}, "answer"))
        self.assertFalse(passes({"integration_assertion_pass": True, "cited_retrieved_url_matches": 2}, " \n"))

    def test_research_join_buckets_each_seed_once(self):
        buckets, new = ledger_tool.research_join(
            {"a/installed", "b/catalog", "c/listed", "d/new", "e/only-pr"},
            {"a/installed": {"runs", "grand"}, "b/catalog": {"runs", "stars"}, "c/listed": {"runs", "lists"},
             "d/new": {"runs"}, "e/only-pr": {"pr-outputs"}}, {"a/installed"})
        self.assertEqual(buckets, {"catalog": 1, "installed": 1, "lists": 1, "new": 2})
        self.assertEqual(new, ["d/new", "e/only-pr"])

    def test_list_grouping_follows_the_screen_generic_run_rule(self):
        def item(disposition, layers=(), kind="github-reference", incumbent=(), lifecycle=(), reason="r"):
            return {"disposition": disposition, "layer_ids": list(layers), "kind": kind,
                    "incumbent_ids": list(incumbent), "lifecycle": list(lifecycle), "reason": reason}

        grouped = ledger_tool.group_list_occurrences([
            item("NO-GAP", ["workers"]), item("WATCH", ["isolation"], lifecycle=["skills-test"]),
            item("OUT-OF-SCOPE", reason="admin")])
        self.assertEqual((grouped["disposition"], grouped["layers"], grouped["lifecycle"]),
                         ("WATCH", ["isolation", "workers"], ["skills-test"]))
        out = ledger_tool.group_list_occurrences([item("OUT-OF-SCOPE", reason="b"), item("OUT-OF-SCOPE", reason="a"),
                                                  item("OUT-OF-SCOPE", reason="b")])
        self.assertEqual((out["relevant"], out["reason"]), (False, "b"))


class NamedCandidateTests(unittest.TestCase):
    """A named candidate whose link is not a GitHub repository gets its own row (the CC's ruling of 2026-10-16)."""

    @classmethod
    def setUpClass(cls):
        cls.ledger = _committed_ledger()
        cls.lists = json.loads((ROOT / cls.ledger["inputs"]["outputs"]["lists"]).read_text(encoding="utf-8"))
        cls.runs = json.loads((ROOT / cls.ledger["inputs"]["outputs"]["runs"]).read_text(encoding="utf-8"))
        cls.by_seed = {row["seed"]: row for row in cls.ledger["seeds"]}

    def tearDown(self):
        ledger_tool.PRIVACY["patterns"], ledger_tool.PRIVACY["redacted"] = [], {}

    def test_a_named_non_github_candidate_gets_a_row(self):
        layers = {"semantic-rag"}
        research_only = ledger_tool.decide("url:https://example.org/tool", {
            "mappings": [], "cluster": ("research", "deer-flow/run.x"), "populations": {"runs": [1, "deer-flow/run.x"]}},
            {}, layers)
        self.assertEqual((research_only["disposition"], research_only["reason_text"]),
                         ("UNMAPPED", ledger_tool.UNMAPPED_REASONS["url"]))
        listed = ledger_tool.decide("url:https://example.org/tool", {
            "mappings": [("PROPOSED", "non-github", "semantic-rag", "lists")], "cluster": None,
            "populations": {"lists": [1, "o/l:README.md:3"]}}, {}, layers)
        self.assertEqual((listed["disposition"], listed["state"], listed["layers"], listed["reason_text"]),
                         ("NON-GITHUB", "PROPOSED", ["semantic-rag"], ledger_tool.NON_GITHUB_REASON))

    def test_every_named_url_from_the_runs_and_prs_has_a_row(self):
        named = {url for item in self.runs["runs"] + self.runs["pr_outputs"] for url in item["named_urls"]}
        self.assertGreater(len(named), 1000)
        rows = [self.by_seed.get("url:" + url) for url in sorted(named)]
        self.assertEqual([url for url, row in zip(sorted(named), rows) if row is None], [])
        self.assertTrue(all(row["disposition"] in ledger_tool.DISPOSITIONS and "reason" in row for row in rows))

    def test_every_list_external_entry_is_seeded(self):
        url_rows = [row for row in self.ledger["seeds"] if row["seed"].startswith("url:")]
        self.assertEqual(sum(row["populations"]["lists"][0] for row in url_rows if "lists" in row["populations"]),
                         self.lists["seeded_occurrences"]["external"])
        non_github = [row for row in url_rows if row["disposition"] == "NON-GITHUB"]
        self.assertGreater(len(non_github), 10000)
        self.assertEqual({self.ledger["reasons"][row["reason"]] for row in non_github}, {ledger_tool.NON_GITHUB_REASON})
        self.assertFalse(any(row["disposition"] == "LAYER-CANDIDATE" for row in url_rows))
        steps = self.ledger["reconciliation"]["named_urls"]["steps"]
        self.assertEqual(sum(step["seeds"] for step in steps), len(url_rows))

    def test_cited_urls_and_their_canonical_form(self):
        ledger_tool.PRIVACY["patterns"], ledger_tool.PRIVACY["redacted"] = ledger_tool.load_private_patterns(ROOT), {}
        home_url = "https://intranet.example.org" + "/home/" + "someone" + "/x"  # assembled: no literal home path here
        text = ("See [Tool](http://www.Example.org/tool/?ref=x#top), https://gitlab.com/group/project.git/ and "
                "https://huggingface.co/Org/Model/tree/main. Not: https://github.com/a/b, "
                "https://img.shields.io/badge/x.svg, http://localhost:8080/api, http://10.1.2.3/x, "
                f"https://cdn.example.org/logo.png, https://box.local/x and {home_url}.")
        self.assertEqual(ledger_tool.cited_urls(text), {
            "https://example.org/tool", "https://gitlab.com/group/project.git",
            "https://huggingface.co/Org/Model/tree/main", "https://intranet.example.org/home/<user>/x"})
        self.assertEqual(ledger_tool.PRIVACY["redacted"], {"personal home path": {home_url}})
        self.assertEqual(ledger_tool.canonical_url("https://api.example.net/v1/badges/" + "0f9e1d2c-3b4a-5968-7a8b-"
                                                   "9c0d1e2f3a4b" + "/status"),
                         "https://api.example.net/v1/badges/<uuid>/status")

    def test_external_entries_survive_a_link_urlsplit_refuses(self):
        screen = ledger_tool.load_screen_generic()
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "fixture-owner__fixture-list"
            clone.mkdir()
            (clone / "README.md").write_text("# Fixture\n\n- http://[::1 a truncated loopback example\n"
                                             "- [vector store](https://example.org/store) - vector database.\n",
                                             encoding="utf-8")
            environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
            environment.update(GIT_AUTHOR_NAME="fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                               GIT_COMMITTER_NAME="fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid",
                               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
            for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "--no-gpg-sign", "-m", "fixture"]):
                subprocess.run(["git", "-C", str(clone), *args], check=True, env=environment, capture_output=True)
            screen.BASE, screen.REPOS = Path(tmp), ["fixture-owner/fixture-list"]
            with self.assertRaises(ValueError):  # the module alone stops at the refused link
                screen.external_resources({}, [])
            original = screen.urlsplit
            _, _, _, external, ignored = ledger_tool.extract_clone(screen, clone, {})
        self.assertEqual([row["target"] for row in external], ["https://example.org/store"])
        self.assertEqual(ignored["urlsplit-refused-targets"], 1)
        self.assertIs(screen.urlsplit, original)  # the retry puts the module's own urlsplit back


class WithheldTests(unittest.TestCase):
    def test_withheld_fields_are_counted_with_a_privacy_reason(self):
        ledger = _committed_ledger()
        runs = json.loads((ROOT / ledger["inputs"]["outputs"]["runs"]).read_text(encoding="utf-8"))
        items = {(item["field"], item["runtime"]): item for item in runs["withheld"]["items"]}
        pi = [run for run in runs["runs"] if run["runtime"] == "pi-claude-researcher"]
        self.assertEqual(items[("topic", "pi-claude-researcher")]["withheld"],
                         sum(1 for run in pi if run["topic_withheld"]))
        self.assertTrue(all(run["topic"] is None for run in pi))
        self.assertEqual({item["reason"] for item in items.values()}, {"privacy"})
        self.assertEqual(runs["withheld"]["withheld_for_licence"], 0)


class TopLevelReaderTests(unittest.TestCase):
    """The coverage documents stay out of the top-level catalogs/landscape/*.json glob, whose readers parse every
    file it matches: scripts/host_receipts.py:449-462 (landscape_winners, run once per component through winner_pins
    at :537-539, which scripts/receipt_staleness.py:75 calls for each one) and the Architecture refresh
    (tools/local-pages/architecture_sources.py:378), at 1b633d861518fa0d299279b1cfaec11d0fb47f82."""

    def coverage_documents(self) -> set[Path]:
        ledger = _committed_ledger()
        return {ledger_tool.newest_ledger(ROOT).resolve(), (ROOT / ledger["inputs"]["outputs"]["lists"]).resolve(),
                *((ROOT / relative).resolve() for relative in ledger_tool.SCHEMAS.values())}

    def test_no_coverage_document_is_a_top_level_landscape_file(self):
        top_level = {path.resolve() for path in (ROOT / "catalogs" / "landscape").glob("*.json")}
        self.assertEqual(sorted(map(str, self.coverage_documents() & top_level)), [])

    def test_landscape_winners_opens_no_coverage_document(self):
        from scripts import host_receipts

        opened, original = set(), Path.read_text

        def read_text(path, *args, **kwargs):
            opened.add(Path(path).resolve())
            return original(path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", read_text):
            winners = host_receipts.landscape_winners(ROOT)
        self.assertTrue(winners)
        self.assertIn((ROOT / "catalogs/landscape/foundation.json").resolve(), opened)
        self.assertEqual(sorted(map(str, self.coverage_documents() & opened)), [])


class MasterSeedsTests(unittest.TestCase):
    """The master seeds reach a sweep through build_inputs.py --seeds, one modality at a time."""

    def test_each_modality_passes_build_inputs_seed_check(self):
        sys.path.insert(0, str(ROOT / "tools/sota-convergence/landscape-sweep"))
        try:
            import build_inputs
        finally:
            sys.path.remove(str(ROOT / "tools/sota-convergence/landscape-sweep"))
        catalogs = [json.loads((ROOT / "catalogs/landscape" / name).read_text(encoding="utf-8"))
                    for name in ("foundation.json", "us-equities.json")]
        repository_ids = [layer["layer_id"] for catalog in catalogs for layer in catalog["layers"]]
        skills_ids = [task["layer_id"] for task in json.loads(
            (ROOT / "catalogs/landscape/skills-lifecycle.json").read_text(encoding="utf-8"))["tasks"]]
        repository = ledger_tool.master_seeds(ROOT, "repository")
        skills = ledger_tool.master_seeds(ROOT, "skills")
        self.assertEqual(build_inputs.check_seeds(repository, repository_ids), repository)
        self.assertEqual(build_inputs.check_seeds(skills, skills_ids), skills)
        master = json.loads((ROOT / ledger_tool.MASTER_SEEDS).read_text(encoding="utf-8"))
        self.assertEqual(set(repository) | set(skills), set(master))
        self.assertEqual((len(repository), len(skills)), (20, 13))
        self.assertEqual(sum(map(len, repository.values())) + sum(map(len, skills.values())), 3554)


if __name__ == "__main__":
    unittest.main()
