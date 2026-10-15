"""Architecture manifest views: source-bound projection, rendering and custody."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.local_pages_architecture_policy_fixture import G5, policy_fixture

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "tools/local-pages"


def load(name):
    spec = importlib.util.spec_from_file_location("manifest_test_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MANIFEST, DIAGRAMS, BUILDER, POLICY, PAGES = (load(name) for name in (
    "architecture_manifest", "architecture_diagrams", "architecture_builder", "source_policy", "build_pages"))
SOURCES = BUILDER.MANIFEST_SOURCES
PATHS = {name: relative for name, relative, _ in SOURCES}
HOST_LABEL = "fixturehost7781"
# Network references; url(#id) is an in-document marker reference.
URL = re.compile(r"(?i)(?:https?:)?//[a-z0-9]|\burl\((?!#)|@import")


def svg_text(svg):
    """Concatenate text nodes in order, so a wrapped identifier reads whole."""
    return "".join(re.findall(r"<text[^>]*>([^<]*)</text>", svg))


def fixture_records(rows=4):
    matrix = {"checked_at": "2026-09-27", "rows": [
        {"catalog": "foundation", "layer_id": "native-clients", "title": "Native clients", "verdict_status": "recorded",
         "independent_review": "dual_lane_same_winner",
         "winners": [{"component_id": "codex", "pin": "0.155.1", "platforms": {"linux-wsl2-x86_64": {"e2e_state": "host_verified"}}},
                     {"component_id": "claude-code", "pin": "2.1.278", "platforms": {"linux-wsl2-x86_64": {"e2e_state": "conditional"}}}]},
        {"catalog": "us-equities", "layer_id": "market-data-reference", "title": "Market data and reference", "verdict_status": "recorded",
         "winners": [{"component_id": "data-alpaca-py", "pin": "v0.44.0", "platforms": {"linux-wsl2-x86_64": {"e2e_state": "accepted"}}}]},
        {"catalog": "us-equities", "layer_id": "portfolio-risk", "title": "Portfolio and risk", "verdict_status": "recorded",
         "winners": [{"component_id": "skfolio", "pin": "1.2.9", "platforms": {"linux-wsl2-x86_64": {"e2e_state": "host_verified"}}}]},
        {"catalog": "us-equities", "layer_id": "execution-broker", "title": "Execution and broker adapters", "verdict_status": "pending_lanes", "winners": []},
    ][:rows]}
    plan = {"base": "Ubuntu 26.04.1 WSL 2", "revised_at_utc": "2026-10-04T23:58:00Z", "owners": [
        {"slot": "gpt-gateway", "owner": "OmniRoute", "layer": "cross:gpt6-harnesses", "release": "3.8.51", "installed": True,
         "service": {"port": 21128, "port_setting": f"PORT=21128 on {HOST_LABEL}"}, "notes": f"measured on {HOST_LABEL} at /home/example"},
        {"slot": "loki", "owner": "Loki", "layer": "observation-inference", "release": "v3.7.8", "installed": False, "service": {"port": 21300}},
        {"slot": "container-engine", "owner": "Docker Engine / Moby", "layer": "hosting-services", "release": "docker-v29.8.2", "installed": True,
         "service": {"port": None, "port_setting": "Unix socket; no TCP listener"}},
        {"slot": "no-service", "owner": "Skill row", "layer": "instructions-skills", "installed": True, "service": {}},
    ]}
    handbook = {"as_of": "2026-10-01", "profile": {"host_prerequisites": [
        {"id": "wsl-release-target", "title": "WSL release for a second systemd distribution",
         "requirement": "This launch adopts stable WSL 3.0.1 or later for a second systemd distribution."}]},
        "layers": [{"layer_id": "cross:gpt6-harnesses", "title": "GPT-6 harnesses: the Codex lane and the gateway"}]}
    ruleset = {"name": "Native foundation required checks", "enforcement": "active",
               "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
               "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}, {"type": "required_linear_history"},
                         {"type": "pull_request", "parameters": {"required_approving_review_count": 0, "required_review_thread_resolution": True, "allowed_merge_methods": ["squash"]}},
                         {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "validate"}, {"context": "verdict-review-gate"}]}},
                         {"type": "code_scanning", "parameters": {"code_scanning_tools": [{"tool": "CodeQL", "security_alerts_threshold": "high_or_higher"}]}}]}
    gates = {"checked_at": "2026-09-24", "gates": [
        {"id": "alpaca-paper-smoke", "rung": "paper", "layer": "execution-broker", "title": "One SPY paper round trip", "status": "established", "required": True},
        {"id": "ibkr-local-acceptance", "rung": "live", "layer": "execution-broker", "title": "IBKR socket adapter accepted locally", "status": "not_established", "required": True},
        {"id": "leverage-ladder-1x", "rung": "live", "layer": "portfolio-risk", "title": "Paper leverage ladder rung 1x", "status": "not_established", "required": True},
        {"id": "live-go", "rung": "live", "layer": "cross-layer", "title": "Explicit live go", "status": "user_decision", "required": True},
    ]}
    runtime = {"reviewed_at": "2026-09-24", "engine": {"repository": "https://github.com/nautechsystems/nautilus_trader", "requested_version": "2.0.0rc5", "decision": "selected_destination"},
               "adaptive_practice": {"policies": ["trend_momentum", "defensive_cash"]},
               "broker_boundaries": [{"id": "ibkr"}, {"id": "alpaca"}],
               "offline_runtime_followup_20261004": {"host": HOST_LABEL}}
    return {"matrix": matrix, "plan": plan, "handbook": handbook, "ruleset": ruleset, "gates": gates, "runtime": runtime}


def model_for(records):
    layers = [{"key": f"{row['catalog']}:{row['layer_id']}", "group": "engines-strategies" if row["catalog"] == "us-equities" else None}
              for row in records["matrix"]["rows"]]
    observation = {"verified": True, "generated_utc": "2026-10-09T06:17:14Z", "window_hours": 24, "roles": [
        {"name": "lane-a", "client": "Codex", "conversations": 3}, {"name": "lane-b", "client": "Codex", "conversations": 4},
        {"name": "role-a", "client": "Claude", "sessions": 2}]}
    roles = {"keys": ["co_op", "foundation_cc", "lanes", "trading_command_center"], "lane_count": 4, "updated_utc": "2026-10-10T16:02:32Z"}
    return {"layers": layers, "adoption_observation": observation, "command_roles": roles}


class ManifestFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root, self.state = self.base / "repo", self.base / "state"
        self.state.mkdir(parents=True)
        self.records = fixture_records()
        self.write_records(self.records)
        document = json.loads(policy_fixture(self.base / "base-policy.json").read_text())
        for _, relative, role in SOURCES:
            document["architecture"].setdefault(role, []).append({"root": "repo", "path": relative})
        self.policy_path = self.base / "independent-policy.json"
        self.policy_path.write_text(json.dumps(document))

    def write_records(self, records):
        for name, document in records.items():
            path = self.root / PATHS[name]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(document), encoding="utf-8")

    def reads(self):
        return POLICY.ArchitectureReads(self.root, self.state, policy_path=self.policy_path, user_root=self.base / "user")

    def build(self, model=None):
        return MANIFEST.build(self.root, model or model_for(self.records), self.reads(), SOURCES,
                              pages=PAGES.PAGES, refresh_utc="2026-10-10T17:00:00Z")


class ManifestProjectionTests(ManifestFixture):
    def test_each_view_projects_only_from_its_record(self):
        manifest = self.build()
        views = manifest["views"]
        self.assertEqual(manifest["unreported"], {})
        self.assertEqual([row["path"] for row in manifest["sources"]], [relative for _, relative, _ in SOURCES])
        for receipt in manifest["sources"]:
            raw = (self.root / receipt["path"]).read_bytes()
            self.assertEqual(receipt["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(receipt["bytes"], len(raw))
        self.assertEqual([row["layer_id"] for row in views["matrix"]["rows"]], [row["layer_id"] for row in self.records["matrix"]["rows"]])
        self.assertEqual(views["matrix"]["verdicts"], {"pending_lanes": 1, "recorded": 3})
        self.assertEqual(views["plan"]["base"], "Ubuntu 26.04.1 WSL 2")
        self.assertEqual([(row["slot"], row["port"], row["status"]) for row in views["plan"]["services"]],
                         [("gpt-gateway", 21128, "adopted"), ("loki", 21300, "planned"), ("container-engine", None, "adopted")])
        self.assertEqual(views["handbook"]["wsl_minimum"], "3.0.1")
        self.assertEqual(views["ruleset"]["checks"], ["validate", "verdict-review-gate"])
        self.assertEqual(views["gates"]["established"], 1)
        self.assertEqual(views["runtime"]["policies"], ["trend_momentum", "defensive_cash"])
        self.assertEqual(views["orchestration"]["codex_lanes"], 2)
        self.assertEqual(views["orchestration"]["codex_conversations"], 7)
        self.assertEqual([tier["key"] for tier in views["orchestration"]["tiers"]], ["foundation_cc", "trading_command_center", "co_op"])

    def test_status_rules_follow_the_recorded_fields(self):
        self.assertEqual([MANIFEST.layer_status(value) for value in ("recorded", "pending_lanes", "no_selection", "other")],
                         ["adopted", "candidate", "planned", "unreported"])
        self.assertEqual([MANIFEST.winner_status(value) for value in ("accepted", "host_verified", "conditional", None)],
                         ["built", "built", "adopted", "adopted"])
        self.assertEqual([MANIFEST.gate_status(value) for value in ("established", "not_established", "paid_entitlement", "user_decision", "other")],
                         ["built", "planned", "planned", "planned", "unreported"])
        self.assertEqual([MANIFEST.plan_status(value) for value in (True, False, None)], ["adopted", "planned", "unreported"])

    def test_final_alias_is_unreported_without_current_admission(self):
        before = self.build()
        self.records["matrix"]["rows"][1]["verdict_status"] = "FINAL"
        self.write_records(self.records)
        after = self.build()
        self.assertEqual(MANIFEST.layer_status("FINAL"), "unreported")
        self.assertEqual(after["views"]["matrix"]["rows"][1]["status"], "unreported")
        self.assertEqual(after["views"]["matrix"]["rows"][0], before["views"]["matrix"]["rows"][0])

    def test_absent_records_leave_views_unreported_without_reading(self):
        for relative in PATHS.values():
            (self.root / relative).unlink()
        manifest = self.build()
        self.assertEqual(manifest["sources"], [])
        self.assertEqual(sorted(manifest["unreported"]), sorted(PATHS))
        html = DIAGRAMS.render(manifest)
        self.assertEqual(html.count('class="mf-unreported"'), 3)
        self.assertIn("record absent from this checkout", html)

    def test_malformed_record_reports_its_view_and_keeps_custody(self):
        broken = copy.deepcopy(self.records)
        broken["matrix"]["rows"] = {"not": "a list"}
        broken["gates"] = ["not an object"]
        self.write_records(broken)
        manifest = self.build()
        self.assertIn("matrix", manifest["unreported"])
        self.assertIn("gates", manifest["unreported"])
        self.assertNotIn("matrix", manifest["views"])
        self.assertIn(PATHS["matrix"], [row["path"] for row in manifest["sources"]])
        self.assertIn("plan", manifest["views"])

    def test_present_record_without_a_grant_fails_closed(self):
        document = json.loads(self.policy_path.read_text())
        document["architecture"]["architecture_receipt"] = [row for row in document["architecture"]["architecture_receipt"] if row["path"] != PATHS["plan"]]
        self.policy_path.write_text(json.dumps(document))
        with self.assertRaises(POLICY.SourcePolicyError):
            self.build()

    def test_host_labels_notes_and_paths_never_reach_the_projection_or_page(self):
        manifest = self.build()
        html = DIAGRAMS.render(manifest)
        published = json.dumps(manifest["views"]) + html
        for forbidden in (HOST_LABEL, "/home/", "PORT=21128", "measured on", "Unix socket"):
            self.assertNotIn(forbidden, published)
        poisoned = copy.deepcopy(self.records)
        poisoned["plan"]["owners"][0]["owner"] = "OmniRoute on " + HOST_LABEL
        poisoned["gates"]["gates"][0]["title"] = "Contact ops@example.org"
        self.write_records(poisoned)
        views = self.build()["views"]
        self.assertEqual(views["plan"]["services"][0]["name"], "gpt-gateway")
        self.assertIsNone(views["gates"]["gates"][0]["title"])

    def test_desk_stage_map_covers_the_trading_catalog_exactly(self):
        catalog = json.loads((ROOT / "catalogs/landscape/us-equities.json").read_text())
        placed = [layer for _, _, layers in MANIFEST.DESK_STAGES for layer in layers] + list(MANIFEST.DESK_CROSS)
        self.assertEqual(len(placed), len(set(placed)))
        self.assertEqual(set(placed), {layer["layer_id"] for layer in catalog["layers"]})
        self.assertEqual([label for _, label, _ in MANIFEST.DESK_STAGES],
                         ["Data sources", "Ingestion", "Research layers", "Strategy families", "Risk", "Paper execution"])

    def test_unplaced_gates_join_the_paper_step_and_statuses_follow_the_ladder(self):
        desk = self.build()["views"]["desk"]
        paper = next(stage for stage in desk["stages"] if stage["key"] == "paper")
        self.assertEqual([(item["name"], item["status"]) for item in paper["items"]],
                         [("Execution and broker adapters", "candidate"), ("alpaca-paper-smoke", "built"),
                          ("ibkr-local-acceptance", "planned"), ("live-go", "planned")])
        risk = next(stage for stage in desk["stages"] if stage["key"] == "risk")
        self.assertEqual([(item["name"], item["status"]) for item in risk["items"]], [("skfolio", "built"), ("leverage-ladder-1x", "planned")])


class ManifestRenderTests(ManifestFixture):
    def test_every_view_renders_its_recorded_values_in_every_variant(self):
        html = DIAGRAMS.render(self.build())
        for slug in ("stack", "layers", "host", "desk"):
            figure = re.search(rf'<figure class="mf-figure" id="mf-{slug}-figure">(.*?)</figure>', html, re.S).group(1)
            svgs = re.findall(r"<svg .*?</svg>", figure, re.S)
            self.assertEqual([re.search(r'viewBox="0 0 (\d+) ', svg).group(1) for svg in svgs], ["1200", "720", "400"])
            for svg in svgs:
                text = svg_text(svg)
                if slug == "layers":
                    for row in self.records["matrix"]["rows"]:
                        self.assertIn(row["title"].replace(" ", ""), text.replace(" ", ""))
                if slug == "host":
                    self.assertIn(":21128", text)
                    self.assertIn("no TCP port", text)
                    self.assertIn("WSL 3.0.1 or later", text)
                if slug == "desk":
                    for gate in self.records["gates"]["gates"]:
                        self.assertIn(gate["id"], text)
                if slug == "stack":
                    self.assertEqual(svg.count('class="mf-cell-mini'), len(self.records["matrix"]["rows"]))
                    self.assertIn("1 of 4 established", text)
                    self.assertIn("2 on main", text)

    def test_accessible_svg_contract_and_unique_ids(self):
        html = DIAGRAMS.render(self.build())
        svgs = re.findall(r"<svg class=\"mf-svg[^>]*>.*?</svg>", html, re.S)
        self.assertEqual(len(svgs), 12)
        identifiers = re.findall(r'\bid="([^"]+)"', html)
        self.assertEqual(len(identifiers), len(set(identifiers)))
        for svg in svgs:
            opening = re.match(r"<svg ([^>]*)>", svg).group(1)
            self.assertIn('role="img"', opening)
            self.assertNotRegex(opening, r'\b(?:width|height)="')
            title_id, desc_id = re.search(r'aria-labelledby="([^" ]+) ([^" ]+)"', opening).groups()
            self.assertRegex(svg, rf'^<svg [^>]*><title id="{re.escape(title_id)}">[^<]+</title><desc id="{re.escape(desc_id)}">[^<]+</desc>')
            for marker in re.findall(r"url\(#([^)]+)\)", svg):
                self.assertIn(f'id="{marker}"', svg)

    def test_zone_label_masks_cover_their_tracked_eyebrow_text(self):
        # Regression: masks sized by the mono advance alone (0.62em) let the
        # dashed zone border cross the tracked uppercase label (0.14em more).
        html = DIAGRAMS.render(self.build())
        host = re.search(r'id="mf-host-figure">(.*?)</figure>', html, re.S).group(1)
        pairs = re.findall(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="14" rx="2" class="mf-mask"/>'
                           r'<text x="([\d.]+)" y="[\d.]+" font-size="([\d.]+)" class="mf-brow">([^<]+)</text>', host)
        self.assertEqual(len(pairs), 6)
        for mask_x, mask_w, text_x, size, text in pairs:
            text_right = float(text_x) + len(text) * float(size) * 0.76
            self.assertGreaterEqual(float(mask_x) + float(mask_w), text_right, text)

    def test_rendering_is_deterministic(self):
        self.assertEqual(DIAGRAMS.render(self.build()), DIAGRAMS.render(self.build()))

    def test_manifest_and_its_style_load_nothing_external(self):
        html = DIAGRAMS.render(self.build())
        style = (HERE / "assets/architecture-manifest.css").read_text()
        for text in (html, style):
            self.assertIsNone(URL.search(text))
        self.assertNotIn("<script", html)
        self.assertNotIn("<link", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("<foreignObject", html)
        self.assertIn("@container", style)
        self.assertIn('[data-theme="dark"]', style)
        self.assertIn("prefers-color-scheme: dark", style)

    def test_source_text_is_escaped_inside_svg(self):
        poisoned = copy.deepcopy(self.records)
        poisoned["matrix"]["rows"][0]["title"] = '<script>alert(1)</script> "x" & y'
        self.write_records(poisoned)
        html = DIAGRAMS.render(self.build())
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_view_without_a_manifest_renders_only_the_ledger(self):
        view = load("architecture_view")
        layer = {"key": "foundation:fixture", "catalog": "foundation", "layer_id": "fixture", "title": "Fixture", "candidates": [], "winners": [], "alternatives": [], "rejected": [], "source_quality": [], "g5_candidates": []}
        html, _ = view.render({"layers": [layer], "layer_count": 1, "sources": []}, {"items": []})
        self.assertNotIn("architecture-manifest", html)
        self.assertNotIn("architecture-ledger", html)
        html, _ = view.render({"layers": [layer], "layer_count": 1, "sources": [], "manifest": self.build()}, {"items": []})
        self.assertLess(html.index('id="architecture-manifest"'), html.index('id="architecture-ledger"'))
        self.assertLess(html.index('id="architecture-ledger"'), html.index('class="architecture-summary"'))


class ManifestRepositoryRecordTests(unittest.TestCase):
    """The committed records, through the committed policy, as the timer reads them."""

    @classmethod
    def setUpClass(cls):
        cls.state = tempfile.TemporaryDirectory()
        reads = POLICY.ArchitectureReads(ROOT, Path(cls.state.name), policy_path=HERE / "source_policy.json")
        layers = []
        for catalog, relative in json.loads((ROOT / "catalogs/landscape/manifest.json").read_text())["catalogs"].items():
            layers += [{"key": f"{catalog}:{layer['layer_id']}", "group": layer.get("group")} for layer in json.loads((ROOT / relative).read_text())["layers"]]
        cls.layers = layers
        cls.manifest = MANIFEST.build(ROOT, {"layers": layers}, reads, SOURCES, pages=PAGES.PAGES)
        cls.html = DIAGRAMS.render(cls.manifest)

    @classmethod
    def tearDownClass(cls):
        cls.state.cleanup()

    def test_every_manifest_source_has_an_exact_committed_grant(self):
        policy = json.loads((HERE / "source_policy.json").read_text())
        for _, relative, role in SOURCES:
            self.assertIn({"root": "repo", "path": relative}, policy["architecture"][role])
        self.assertEqual(self.manifest["unreported"], {})

    def test_layer_count_matches_the_component_evidence_matrix(self):
        matrix = json.loads((ROOT / PATHS["matrix"]).read_text())
        rows = self.manifest["views"]["matrix"]["rows"]
        self.assertEqual(len(rows), len(matrix["rows"]))
        self.assertEqual(len(rows), len(self.layers))
        self.assertEqual({row["key"] for row in rows}, {layer["key"] for layer in self.layers})
        verdicts = {}
        for row in matrix["rows"]:
            verdicts[row["verdict_status"]] = verdicts.get(row["verdict_status"], 0) + 1
        self.assertEqual(self.manifest["views"]["matrix"]["verdicts"], verdicts)
        self.assertEqual(self.manifest["receipt"]["layer_cells"], len(matrix["rows"]))
        stack = re.search(r'id="mf-stack-figure">(.*?)</figure>', self.html, re.S).group(1)
        for svg in re.findall(r"<svg .*?</svg>", stack, re.S):
            self.assertEqual(svg.count('class="mf-cell-mini'), len(matrix["rows"]))
        layers = re.search(r'id="mf-layers".*?</section>', self.html, re.S).group(0)
        self.assertEqual(layers.count("<tr><td>"), len(matrix["rows"]))
        pending = [row["layer_id"] for row in matrix["rows"] if row["verdict_status"] == "pending_lanes"]
        self.assertEqual(self.manifest["views"]["matrix"]["pending"], pending)

    def test_services_ports_and_gates_match_their_records(self):
        plan = json.loads((ROOT / PATHS["plan"]).read_text())
        services = [owner for owner in plan["owners"] if isinstance(owner.get("service"), dict) and owner["service"]]
        ports = sorted(owner["service"]["port"] for owner in services if isinstance(owner["service"].get("port"), int))
        projected = self.manifest["views"]["plan"]["services"]
        self.assertEqual(len(projected), len(services))
        self.assertEqual(sorted(row["port"] for row in projected if row["port"]), ports)
        host = re.search(r'id="mf-host".*?</section>', self.html, re.S).group(0)
        for port in ports:
            self.assertIn(f"127.0.0.1:{port}", host)
        gates = json.loads((ROOT / PATHS["gates"]).read_text())["gates"]
        desk = re.search(r'id="mf-desk".*?</section>', self.html, re.S).group(0)
        for gate in gates:
            self.assertIn(gate["id"], desk)
        established = sum(1 for gate in gates if gate["status"] == "established")
        self.assertIn(f"{established} of {len(gates)} gates established", desk)

    def test_rendered_manifest_has_no_external_url_or_record_host_label(self):
        self.assertIsNone(URL.search(self.html))
        hosts = set()

        def collect(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "host" and isinstance(child, str):
                        hosts.add(child.casefold())
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        for relative in PATHS.values():
            collect(json.loads((ROOT / relative).read_text()))
        folded = self.html.casefold()
        for host in hosts:
            if len(host) >= 3 and host != "localhost":
                self.assertNotIn(host, folded)
        self.assertNotRegex(self.html, r"/(?:home|Users)/")


class ManifestBuilderWiringTests(unittest.TestCase):
    def test_document_head_extension_is_opt_in(self):
        plain = PAGES.document("index", "T", "L", "S", "<p>b</p>", "now", "0" * 64, [])
        styled = PAGES.document("index", "T", "L", "S", "<p>b</p>", "now", "0" * 64, [], head="\n  <style>p{}</style>")
        self.assertNotIn(b"<style>", plain)
        self.assertLess(styled.index(b'href="assets/site.css"'), styled.index(b"<style>p{}</style>"))
        self.assertLess(styled.index(b"<style>p{}</style>"), styled.index(b"</head>"))

    def test_builder_custody_lists_manifest_modules_and_style(self):
        self.assertIn("architecture_manifest", BUILDER.MODULES)
        self.assertIn("architecture_diagrams", BUILDER.MODULES)
        self.assertTrue(BUILDER.MANIFEST_STYLE.is_file())

    def test_refresh_signature_rebuilds_when_a_manifest_record_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, state, output = base / "repo", base / "state", base / "served"
            receipt = base / "nonserved/receipt.json"
            for relative in ("catalogs/landscape/manifest.json", "catalogs/north-star/readiness.json", "adoption/skills/manifest.json",
                             "manifests/stack.json", "manifests/evidence.json", "adoption/manifest.json"):
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                (root / relative).write_text("{}")
            (state / "coordination/command-center/pages").mkdir(parents=True)
            (state / "coordination/command-center/pages/cc-now.json").write_text("{}")
            for name, document in fixture_records().items():
                (root / PATHS[name]).parent.mkdir(parents=True, exist_ok=True)
                (root / PATHS[name]).write_text(json.dumps(document))
            document = json.loads(policy_fixture(base / "base-policy.json").read_text())
            for _, relative, role in SOURCES:
                document["architecture"].setdefault(role, []).append({"root": "repo", "path": relative})
            # As in the committed policy, the matrix is also a landscape supplement.
            document["architecture"]["architecture_supplement"].append({"root": "repo", "path": PATHS["matrix"]})
            policy_path = base / "independent-policy.json"
            policy_path.write_text(json.dumps(document))
            original = BUILDER.load
            modules = {"build_pages": SimpleNamespace(no_symlinks=lambda path: path.absolute(), prune_architecture_details=lambda *unused: None),
                       "architecture_evidence": SimpleNamespace(invocation_source=lambda unused, reads=None: {"sha256": "a" * 64}),
                       "source_policy": original("source_policy"), "architecture_inventory": original("architecture_inventory"),
                       "architecture_sources": SimpleNamespace(_FINAL_ASSET=G5)}
            calls = []

            def generate(*unused):
                calls.append(1)
                output.mkdir(exist_ok=True)
                (output / "architecture.html").write_text("page")
                receipt.parent.mkdir(parents=True, exist_ok=True)
                receipt.write_text(json.dumps({"generated_utc": "2026-01-01T00:00:00Z"}))
                return {"generated_utc": "2026-01-01T00:00:00Z"}

            with patch.object(modules["architecture_inventory"], "USER_ROOT", base / "user"), \
                    patch.object(BUILDER, "SOURCE_POLICY_PATH", policy_path), \
                    patch.object(BUILDER, "load", side_effect=lambda name: modules[name]), \
                    patch.object(BUILDER, "build", side_effect=generate):
                BUILDER.refresh_if_changed(root, state, output, receipt)
                BUILDER.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 1)
                gates = fixture_records()["gates"]
                gates["gates"][1]["status"] = "established"
                (root / PATHS["gates"]).write_text(json.dumps(gates))
                BUILDER.refresh_if_changed(root, state, output, receipt)
                self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
