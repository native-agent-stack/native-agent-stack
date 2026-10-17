"""Harness atlas data: exact grants, bounded reads, the projection whitelist, catalog joins, citations and the ledger.

Fixtures are synthetic records in temporary repo, state and user roots, shaped like the overview suite's catalogs
(tests/test_local_pages_overview.py:38-63), which architecture_manifest.layer_manifest() accepts. The committed
source_policy.json grants paths relative to a root, so the same grants bind the fixture roots. Real-repository cases
read the committed catalogs only. Private-looking strings are assembled at run time; the module under test loads
inside each test, so a run before it exists fails test by test.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_pages_atlas_fixture import (HERE, HISTORY, LATEST, ROOT, SKILL_BYTES, SKILL_SHA, Fixture, atlas, lane, latest,  # noqa: E402
                                       source_policy)


class AtlasCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="atlas-data-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)


class GrantTests(AtlasCase):
    def test_atlas_grants_equal_the_atlas_declarations(self):
        document, readers, receipt = atlas().load_sources(ROOT, self.base)
        self.assertEqual(receipt["path"], "tools/local-pages/atlas_sources.json")
        granted = json.loads((HERE / "source_policy.json").read_text())["atlas"]
        declared = {(entry["role"], entry["root"], entry["path"]) for entry in document["sources"].values() if entry["role"].startswith("atlas_")}
        self.assertEqual(declared, {(role, record["root"], record["path"]) for role, records in granted.items() for record in records})
        self.assertEqual(set(readers), {"architecture_", "overview_", "atlas_"})

    def test_atlas_reads_refuse_each_mutation_before_any_read(self):
        source = json.loads((HERE / "source_policy.json").read_text())
        changes = {"final-stack": lambda doc: doc["atlas"]["atlas_token_rate_latest"].append({"root": "repo", "path": "catalogs/landscape/final-stack.json"}),
                   "families": lambda doc: doc.update(atlas_families={"atlas_x": {"root": "state", "directory": "x", "filename": "y"}}),
                   "role": lambda doc: doc["atlas"].update(overview_x=[]),
                   "extra-key": lambda doc: doc["atlas"]["atlas_token_rate_latest"][0].update(glob="*.json"),
                   "protected": lambda doc: doc["atlas"]["atlas_token_rate_latest"].append({"root": "state", "path": "coordination/auth.json"})}
        for name, change in changes.items():
            document = copy.deepcopy(source)
            change(document)
            path = self.base / f"{name}.json"
            path.write_text(json.dumps(document))
            with self.subTest(change=name), self.assertRaises(source_policy().SourcePolicyError):
                source_policy().AtlasReads(ROOT, self.base, policy_path=path)
        reads = source_policy().AtlasReads(ROOT, self.base)
        with self.assertRaises(source_policy().SourcePolicyError):
            reads.validate("atlas_token_rate_latest", "state", glob="coordination/command-center/skills/*.json")
        with self.assertRaises(source_policy().SourcePolicyError):
            reads.validate("atlas_token_rate_latest", "state", path="coordination/command-center/skills/token-rate-other.json")

    def test_symlinked_or_oversized_projections_are_refused(self):
        state = self.base / "state"
        target = self.base / "outside.json"
        target.write_text("{}")
        (state / "coordination/command-center/skills").mkdir(parents=True)
        (state / LATEST).symlink_to(target)
        reads = source_policy().AtlasReads(ROOT, state)
        with self.assertRaises(source_policy().SourcePolicyError):
            reads.read("atlas_token_rate_latest", state / LATEST)
        linked = self.base / "linked-state"
        (self.base / "real/command-center/skills").mkdir(parents=True)
        (linked / "coordination").mkdir(parents=True)
        (linked / "coordination/command-center").symlink_to(self.base / "real/command-center")
        (self.base / "real/command-center/skills/token-rate-history.json").write_text("{}")
        with self.assertRaises(source_policy().SourcePolicyError):
            source_policy().AtlasReads(ROOT, linked).read("atlas_token_rate_history", linked / HISTORY)
        big = self.base / "big-state"
        Fixture.write(big / LATEST, " " * (1024 * 1024 + 1))
        with self.assertRaises(source_policy().SourceReadLimitError):
            source_policy().AtlasReads(ROOT, big).read("atlas_token_rate_latest", big / LATEST)
        # The role's own bound holds even when the caller passes a larger one.
        with self.assertRaises(source_policy().SourceReadLimitError):
            source_policy().AtlasReads(ROOT, big).read("atlas_token_rate_latest", big / LATEST, max_bytes=2 * 1024 * 1024)
        Fixture.write(big / HISTORY, " " * (1024 * 1024 + 1))
        raw, record = source_policy().AtlasReads(ROOT, big).read("atlas_token_rate_history", big / HISTORY)
        self.assertEqual(record["bytes"], 1024 * 1024 + 1)

    def test_overview_reads_are_unchanged_by_the_atlas_subclass(self):
        source = json.loads((HERE / "source_policy.json").read_text())
        expected = {"families": "overview reads are exact-path grants only; overview_families is not accepted",
                    "role": "invalid overview exact-path role",
                    "record": "overview permission requires exactly a known root and a path"}
        changes = {"families": lambda doc: doc.update(overview_families={}),
                   "role": lambda doc: doc["overview"].update(atlas_x=[]),
                   "record": lambda doc: doc["overview"]["overview_cc_now"][0].update(extra=1)}
        for name, change in changes.items():
            document = copy.deepcopy(source)
            change(document)
            path = self.base / f"{name}.json"
            path.write_text(json.dumps(document))
            with self.subTest(change=name), self.assertRaises(source_policy().SourcePolicyError) as raised:
                source_policy().OverviewReads(ROOT, self.base, policy_path=path)
            self.assertEqual(str(raised.exception), expected[name])
        reads = source_policy().OverviewReads(ROOT, self.base)
        with self.assertRaises(source_policy().SourcePolicyError) as raised:
            reads.validate("overview_cc_now", "state", glob="x/*.json")
        self.assertEqual(str(raised.exception), "an overview source names exactly one path; a glob is not a grant")
        with self.assertRaises(source_policy().SourcePolicyError) as raised:
            reads.read("overview_cc_now", self.base / "coordination/command-center/pages/cc-now.json", max_bytes=0)
        self.assertEqual(str(raised.exception), "overview read bound must be a positive integer")


class ModelTests(AtlasCase):
    def test_a_missing_projection_is_pending_never_zero(self):
        fixture = Fixture(self.base, projections=False)
        data = fixture.model()
        self.assertEqual(data["measured"]["status"], "pending")
        self.assertEqual(data["measured"]["source"]["trigger"], "the CC installs token-rate.timer (tools/skill-usage/README.md) and its first run publishes the projection")
        _, html, _ = fixture.build(self.base)
        section = html[html.index('id="atlas-measured"'):html.index('id="atlas-routing"')]
        self.assertIn("Not measured yet: the daily token projection has not run.", section)
        self.assertIn("the CC installs token-rate.timer", section)
        self.assertNotRegex(section, r"<td>0</td>")

    def test_the_projection_whitelist_rejects_garbled_values(self):
        module = atlas()
        self.assertIsNone(module.projection({**latest(), "schema": "token-rate-daily/2"}))
        raw = latest()
        raw["rollup"]["lanes"]["claude:workflow"].update(actors=True, tool_calls=-1, actors_complete=float("inf"), prompt="PRIVATE-" + "prompt",
                                                         mcp={"memory-server": 4, "unlisted-server": 9, "bad name": 2}, models={"claude-opus-5-5": 1, "mystery": 3})
        raw["rollup"]["lanes"]["unknown:lane"] = lane()
        raw["servers"].append({"name": "bad name", "repository": "https://github.com/fixture/bad"})
        projected = module.projection(raw)
        workflow = projected["rollup"]["lanes"]["claude:workflow"]
        self.assertEqual((workflow["actors"], workflow["tool_calls"], workflow["actors_complete"]), (None, None, None))
        self.assertEqual(workflow["mcp"], {"memory-server": 4})
        self.assertEqual(workflow["models"], {"claude-opus-5-5": 1})
        self.assertNotIn("unknown:lane", projected["rollup"]["lanes"])
        self.assertNotIn("PRIVATE", json.dumps(projected))
        # An unknown other count keeps the other class unknown; it never becomes zero.
        unknown_other = {"mcp": {"memory-server": 4, "loose-server": 2}, "mcp_other": None}
        self.assertEqual(module.mcp_classes(unknown_other, {"memory-server": {"stack": "memory_rag"}})["other"], None)
        self.assertEqual(module.mcp_classes({"mcp": {"loose-server": 2}, "mcp_other": 1}, {})["other"], 3)
        fixture = Fixture(self.base)
        data = fixture.model()
        self.assertEqual(data["measured"]["classes"]["loose-server"], {"named": False, "stack": None, "layer": None, "role": None})
        _, html, _ = fixture.build(self.base)
        self.assertNotIn("loose-server", html)
        self.assertIn("memory-server", html)

    def test_layer_states_equal_overview_data_on_the_real_repository(self):
        data = atlas().model(ROOT, self.base / "state", user_root=self.base / "user")
        overview = atlas().load("overview_data")
        glance = overview.architecture(data["sources"], ROOT, data["commit"])
        self.assertEqual({key: data["architecture"][key] for key in ("total", "finalized", "states")}, {key: glance[key] for key in ("total", "finalized", "states")})
        expected = {f'{band["catalog"]}/{layer["layer_id"]}': layer["state"] for band in glance["bands"] for layer in band["layers"]}
        self.assertEqual({key: row["state"] for key, row in data["layers"].items() if row["in_catalog"]}, expected)
        final_stack_doc = json.loads((ROOT / "catalogs/landscape/final-stack.json").read_text())
        runs = {run["id"]: run.get("pin") for run in final_stack_doc["runs"]}
        record = next(layer for layer in final_stack_doc["layers"] if layer["catalog"] == "foundation" and layer["layer_id"] == "token-efficiency")
        self.assertEqual([(winner["component"], winner["run_pin"]) for winner in data["layers"]["foundation/token-efficiency"]["winners"]],
                         [(winner["component_id"], runs.get(winner.get("run"))) for winner in record["winners"]])
        if final_stack_doc["summary"]["final_layers"] == 0:
            html, _ = atlas().load("atlas_view").render({**data, "ledger": {}})
            self.assertIn("No layer is final yet", html)
        self.assertEqual(data["measured"]["status"], "pending")


class JoinTests(unittest.TestCase):
    def test_every_catalog_layer_and_slot_the_map_names_exists(self):
        joins, _ = atlas().load_map()
        stack_keys = {f'{layer["catalog"]}/{layer["layer_id"]}' for layer in json.loads((ROOT / "catalogs/landscape/final-stack.json").read_text())["layers"]}
        slot_ids = {slot["id"] for slot in json.loads((ROOT / ".claude/skills/claude-native-practice/reference/slots.json").read_text())["slots"]}
        foundation = {"foundation/" + layer["layer_id"] for layer in json.loads((ROOT / "catalogs/landscape/foundation.json").read_text())["layers"]}
        for row in joins["harness_layers"] + joins["stacks"]:
            for key in row["catalog_layers"]:
                self.assertIn(key, stack_keys, row["id"])
            for slot in row["slots"]:
                self.assertIn(slot, slot_ids, row["id"])
        for stack in joins["stacks"]:
            for key in stack["catalog_layers"]:
                self.assertIn(key, foundation, stack["id"])

    def test_every_citation_resolves_to_its_anchor(self):
        joins, _ = atlas().load_map()
        cites = atlas().cites(joins)
        self.assertGreater(len(cites), 40)
        for cite in cites:
            lines = (ROOT / cite["path"]).read_text().splitlines()
            with self.subTest(cite=f'{cite["path"]}:{cite["line"]}'):
                self.assertLessEqual(cite["line"], len(lines))
                self.assertIn(cite["anchor"], lines[cite["line"] - 1])
        for rule in joins["standing_rules"]:
            if not rule["recorded_in"]:
                self.assertTrue(rule["trigger"].strip(), rule["id"])

    def test_server_join_matches_host_receipts_normalization_and_the_observed_classes(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import host_receipts
        view = atlas().load("architecture_view")
        tools = json.loads((ROOT / "docs/role-tool-sets.json").read_text())["tools"]
        servers = []
        for tool in tools:
            if str(tool.get("repository", "")).startswith("https://github.com/"):
                self.assertEqual("github.com/" + view.repo_key(tool["repository"]), host_receipts.normalize_repository(tool["repository"]))
                servers.append({"name": tool["tool_id"], "repository_key": "github.com/" + view.repo_key(tool["repository"])})
        joins, _ = atlas().load_map()
        classes = atlas()._server_classes(servers, json.loads((ROOT / "catalogs/landscape/final-stack.json").read_text()), joins["stacks"])
        expected = {"context-mode": ("token_efficiency", "alternate"), "headroom": ("token_efficiency", "winner"), "ai-memory": ("memory_rag", "winner"),
                    "hindsight": ("memory_rag", "alternate"), "qmd": ("memory_rag", "winner"), "serena": ("code_intel", "winner"),
                    "jcodemunch": ("code_intel", "alternate"), "codebase-memory-mcp": ("code_intel", "alternate"), "socraticode": ("code_intel", "winner"),
                    "semble": ("code_intel", "survivor")}
        for name, (stack, role) in expected.items():
            self.assertEqual((classes[name]["stack"], classes[name]["role"]), (stack, role), name)
        self.assertFalse(classes["chrome-devtools"]["named"])
        self.assertEqual((classes["promptfoo"]["named"], classes["promptfoo"]["stack"]), (True, None))


class RoutingAndShareTests(AtlasCase):
    def test_agent_parsing_reads_only_whitelisted_model_and_effort(self):
        parse = atlas().parse_agent
        home = "/".join(("", "home", "x"))
        self.assertEqual(parse("---\nname: a\nmodel: " + home + "\neffort: ultra\ntools: Bash\n---\nmodel: opus\n", ".md"), ("UNREPORTED", "UNREPORTED"))
        self.assertEqual(parse("---\nmodel: sonnet\neffort: medium\n---\n", ".md"), ("sonnet", "medium"))
        self.assertEqual(parse('name = "x"\nmodel = "gpt-6-astra"\nmodel_reasoning_effort = "max"\n[mcp_servers.y]\nmodel = "other"\n', ".toml"), ("gpt-6-astra", "max"))
        self.assertEqual(parse('name = "x"\nmodel_reasoning_effort = "max"\n', ".toml"), (None, "max"))
        self.assertEqual(parse('model = 7\n', ".toml"), ("UNREPORTED", None))
        # Efforts are whitelisted per client: Codex has minimal and none, Claude Code does not.
        self.assertEqual(parse('model_reasoning_effort = "minimal"\n', ".toml"), (None, "minimal"))
        self.assertEqual(parse("---\neffort: minimal\n---\n", ".md"), (None, "UNREPORTED"))
        fixture = Fixture(self.base, agents=("stack-verifier",))
        data = fixture.model()
        verifier = next(row for row in data["routing"]["rows"] if row["role"] == "stack-verifier" and row["family"] == "claude")
        self.assertEqual((verifier["model"], verifier["effort"]), ("sonnet", "medium"))
        pending = [row for row in data["routing"]["rows"] if row["status"] != "present"]
        self.assertEqual(len(pending), 15)
        muse = next(row for row in data["routing"]["rows"] if row["family"] == "muse")
        self.assertEqual((muse["model"], muse["role"]), ("muse-wonder-full-1.0", "reader"))

    def test_shares_come_from_numerators_and_are_never_averaged(self):
        module = atlas()
        self.assertIsNone(module.ratio(5, 0))
        self.assertIsNone(module.ratio(None, 5))
        self.assertEqual(module.cache_read_share({"usage": {"input": 10, "cache_creation": 0, "cache_read": 990}}), 0.99)
        self.assertEqual(module.cache_read_share({"usage": None, "codex_usage": {"input": 100, "cached_input": 25}}), 0.25)
        self.assertIsNone(module.cache_read_share({"usage": {"input": 0, "cache_creation": 0, "cache_read": 0}}))
        days = [{"usage": {"input": 90, "cache_creation": 0, "cache_read": 10}}, {"usage": {"input": 1, "cache_creation": 0, "cache_read": 9}}]
        summed = {"usage": {key: sum(day["usage"][key] for day in days) for key in ("input", "cache_creation", "cache_read")}}
        self.assertAlmostEqual(module.cache_read_share(summed), 19 / 110)
        self.assertNotAlmostEqual(module.cache_read_share(summed), sum(module.cache_read_share(day) for day in days) / 2)

    def test_installed_skill_digests_match_differ_or_are_absent(self):
        fixture = Fixture(self.base)
        Fixture.write(fixture.user / ".agents/skills/frontend-design/SKILL.md", SKILL_BYTES.decode())
        Fixture.write(fixture.user / ".agents/skills/tdd/SKILL.md", SKILL_BYTES.decode() + "x")
        rows = {row["name"]: row for row in fixture.model()["skills"]["rows"]}
        self.assertEqual((rows["frontend-design"]["installed_sha256"], rows["frontend-design"]["match"]), (SKILL_SHA, True))
        self.assertIs(rows["tdd"]["match"], False)
        self.assertEqual((rows["codebase-design"]["installed_sha256"], rows["codebase-design"]["match"]), (None, None))
        self.assertIs(rows["claude-native-practice"]["match"], True)


class LedgerTests(AtlasCase):
    def test_a_row_is_appended_only_when_the_state_changes_and_rows_chain(self):
        fixture = Fixture(self.base)
        first, _, receipt = fixture.build(self.base)
        self.assertEqual((first["ledger"]["status"], first["ledger"]["rows"], first["ledger"]["checks_since_row"]), ("appended", 1, 0))
        ledger = receipt.with_name("atlas-ledger.json")
        before = ledger.read_bytes()
        second, html, _ = fixture.build(self.base)
        self.assertEqual((second["ledger"]["status"], second["ledger"]["checks_since_row"]), ("unchanged", 1))
        self.assertEqual(ledger.read_bytes(), before)
        third, _, _ = fixture.build(self.base)
        self.assertEqual(third["ledger"]["checks_since_row"], 2)
        Fixture.write(fixture.state / LATEST, json.dumps(latest(days=2, last="2026-10-17")))
        fourth, html, _ = fixture.build(self.base)
        self.assertEqual((fourth["ledger"]["status"], fourth["ledger"]["rows"], fourth["ledger"]["previous_row_sha256"]), ("appended", 2, first["ledger"]["row_sha256"]))
        rows = json.loads(ledger.read_text())["rows"]
        self.assertEqual({(change["kind"], change["key"]) for change in rows[1]["changes"]}, {("measured", "last_closed_day"), ("measured", "history_rows")})
        self.assertIn("This build appended row 2 with 2 changes.", html)
        self.assertNotIn("generated_utc", json.dumps(rows[1]["state"]))

    def test_a_tampered_or_unparsable_ledger_is_left_byte_identical_and_reported(self):
        fixture = Fixture(self.base)
        _, _, receipt = fixture.build(self.base)
        ledger = receipt.with_name("atlas-ledger.json")
        good = json.loads(ledger.read_text())
        tampered = copy.deepcopy(good)
        tampered["rows"][0]["state"]["rules"]["zero-stale"] = "pending"
        broken = copy.deepcopy(good)
        broken["rows"][0]["previous_row_sha256"] = "d" * 64
        for name, text in (("tampered", json.dumps(tampered)), ("broken-chain", json.dumps(broken)), ("unparsable", "{rows")):
            with self.subTest(case=name):
                ledger.write_text(text)
                Fixture.write(fixture.state / LATEST, json.dumps(latest(days=3, last="2026-10-18")))
                result, html, _ = fixture.build(self.base)
                self.assertEqual(ledger.read_text(), text)
                self.assertEqual(result["ledger"]["status"], "unreported")
                self.assertIn("History unavailable: the ledger failed its check; it is kept for inspection.", html)

    def test_past_the_cap_the_oldest_row_drops_and_its_digest_anchors_the_chain(self):
        module = atlas()
        ledger, receipt = self.base / "atlas/atlas-ledger.json", self.base / "atlas/atlas-receipt.json"
        ledger.parent.mkdir(parents=True)
        digests = []
        for index in range(3):
            step = module.advance(ledger, receipt, {"measured": {"history_rows": index}}, generated=f"2099-01-0{index + 1}T00:00:00Z", commit=None, sources={}, cap=2)
            ledger.write_bytes(step["raw"])
            digests.append(step["row_sha256"])
        document = module.verify_ledger(ledger.read_bytes())
        self.assertEqual(document["dropped"], {"rows": 1, "last_row_sha256": digests[0]})
        self.assertEqual([row["seq"] for row in document["rows"]], [2, 3])
        self.assertEqual(document["rows"][0]["previous_row_sha256"], digests[0])

    def test_the_receipt_stays_outside_the_served_root_and_lists_its_custody(self):
        fixture = Fixture(self.base, projections=False)
        result, html, receipt = fixture.build(self.base)
        self.assertFalse(receipt.is_relative_to(self.base / "served"))
        self.assertEqual(json.loads(receipt.read_text()), result)
        self.assertIn("token_rate_latest", result["pending"])
        self.assertIn("final_stack", result["present"])
        self.assertEqual({Path(row["path"]).name for row in result["modules"]}, {name + ".py" for name in atlas().MODULES})
        self.assertEqual([Path(row["path"]).name for row in result["style"]], ["architecture-manifest.css", "overview.css", "atlas.css"])
        self.assertEqual(set(result["outputs"]), {"atlas.html", "assets/site.css", "assets/site.js"})
        self.assertEqual(result["outputs"]["atlas.html"]["sha256"], hashlib.sha256(html.encode()).hexdigest())
        with self.assertRaises(ValueError):
            atlas().build_atlas_page(fixture.root, fixture.state, self.base / "served", self.base / "served/receipt.json", commit="0" * 40, user_root=fixture.user)


if __name__ == "__main__":
    unittest.main()
