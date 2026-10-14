"""Local integration checks for NativeStack2604's ported dashboards and research emitter (no host, no network)."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002"
SPEC = importlib.util.spec_from_file_location("ns2604_dashboards", ROOT / "observability/ns2604_dashboards.py")
G = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G)


def exprs(board):
    return [t["expr"] for panel in board["panels"] for t in panel.get("targets", []) if "expr" in t]


class Ns2604DashboardTests(unittest.TestCase):
    def test_trading_lanes_board_has_each_receipt_lane_and_broker_wire_thresholds(self):
        board = G.dashboards().get("grafana-trading-lanes.json")
        self.assertIsNotNone(board, "The provisioned dashboard set must contain Trading lanes")
        self.assertEqual(("trading-lanes", "Trading lanes"), (board["uid"], board["title"]))
        self.assertFalse(board["editable"])
        rows = [p["title"] for p in board["panels"] if p["type"] == "row"]
        self.assertEqual(["A", "B", "C", "lanea", "laneb", "IBKR", "I-llm"], rows)
        expressions = exprs(board)
        for lane in rows:
            for metric in ("orders_per_min", "fills_per_min", "cancels_per_min", "cash_use_ratio",
                           "open_positions", "realized_pnl_usd", "status_code", "ended_by_code"):
                self.assertTrue(any(f'lane="{lane}"' in expression and f"unwrap {metric} " in expression
                                    for expression in expressions), (lane, metric))
        self.assertTrue(all("[10m]" in expression for expression in expressions))
        wire = next(p for p in board["panels"] if p["title"] == "IBKR wire messages/s")
        self.assertEqual([45, 50], [x["value"] for x in wire["fieldConfig"]["defaults"]["thresholds"]["steps"]
                                    if x["value"] is not None])
        self.assertNotRegex(json.dumps(board), r"/home/|account_id|client_order_id|events\\.jsonl")

    def test_committed_plan_dashboards_match_a_fresh_render(self):
        result = subprocess.run([sys.executable, str(ROOT / "observability/ns2604_dashboards.py"), "--check"],
                                capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_trading_rates_name_their_minute_basis_and_missing_pnl_has_a_bounded_mapping(self):
        board = G.dashboards()["grafana-trading-lanes.json"]
        rates = [p for p in board["panels"] if p.get("type") == "stat" and "/min" in p["title"]]
        self.assertEqual(21, len(rates))
        with self.subTest(note="minute units"):
            self.assertTrue(all(p["fieldConfig"]["defaults"]["unit"].startswith("suffix:") for p in rates))
        with self.subTest(note="historical stage basis"):
            self.assertTrue(all("(last stage)" in p["title"] for p in rates if p["title"].startswith(("A ·", "B ·"))))
        pnl = next(p for p in board["panels"] if p["title"] == "I-llm · Realized P&L")
        defaults = pnl["fieldConfig"]["defaults"]
        key, value = next(iter(defaults["mappings"][0]["options"].items()))
        with self.subTest(note="empty value fallback"):
            self.assertEqual("Not recorded", defaults.get("noValue"))
        with self.subTest(note="missing mapping transport"):
            self.assertNotIn("e", key.lower(), "Missing-value mapping must survive native decimal LogQL output")
            self.assertEqual("Not recorded", value["text"])

    def test_unstarted_lane_last_receipt_stat_has_explicit_not_recorded_fallback(self):
        board = G.dashboards()["grafana-trading-lanes.json"]
        panel = next(p for p in board["panels"] if p["title"] == "I-llm · Last receipt time")
        defaults = panel["fieldConfig"]["defaults"]
        self.assertEqual("Not recorded", defaults.get("noValue"))
        self.assertEqual("Not recorded", defaults["mappings"][0]["options"]["-1000"]["text"])

    def test_retarget_changes_only_datasources_and_prometheus_metric_names(self):
        board = {"panels": [
            {"id": 1, "datasource": {"type": "prometheus", "uid": "ecosystem-prometheus"}, "targets": [
                {"refId": "A", "expr": 'sum by (ecosystem_lane) (rate(ecosystem_codex_tool_call_total[5m]))'},
                {"refId": "B", "expr": '{__name__=~"ecosystem_a_total|ecosystem_b_total"}'}]},
            {"id": 2, "datasource": {"type": "loki", "uid": "ecosystem-loki"}, "targets": [
                {"refId": "A", "expr": '{service_name="ecosystem_logs"} | json'}]},
            {"id": 3, "type": "row", "panels": [
                {"id": 4, "targets": [{"refId": "A", "datasource": {"uid": "ecosystem-prometheus"},
                                       "expr": "ecosystem_system_memory_usage_bytes"}]}]},
        ]}
        G.retarget(board)
        self.assertEqual(["sum by (ecosystem_lane) (rate(codex_tool_call_total[5m]))", '{__name__=~"a_total|b_total"}',
                          '{service_name="ecosystem_logs"} | json'], exprs(board))
        self.assertEqual("system_memory_usage_bytes", board["panels"][2]["panels"][0]["targets"][0]["expr"])
        self.assertEqual(["ns2604-prometheus", "ns2604-loki"], [p["datasource"]["uid"] for p in board["panels"][:2]])
        self.assertEqual("ns2604-prometheus", board["panels"][2]["panels"][0]["targets"][0]["datasource"]["uid"])

    def test_plan_dashboards_target_this_host_only(self):
        for name, uid in (("grafana-research-grand.json", "research-grand"),
                          ("grafana-ecosystem-native.json", "ecosystem-native"),
                          ("grafana-native-foundation-data.json", "native-foundation-data"),
                          ("grafana-command-center.json", "cc-god-view")):
            with self.subTest(name=name):
                text = (PLAN / "config" / name).read_text()
                board = json.loads(text)
                self.assertEqual(uid, board["uid"])
                self.assertFalse(board["editable"])
                self.assertEqual({"ns2604-loki", "ns2604-prometheus"},
                                 set(re.findall(r'"uid": "(ns2604-[a-z]+)"', text)))
                self.assertNotRegex(text, r'ecosystem-(?:loki|prometheus)|(?<![\w:])ecosystem_(?!lane\b)|:1[0-9]{4}\b')
        research = json.loads((PLAN / "config/grafana-research-grand.json").read_text())
        table = next(p for p in research["panels"] if p["id"] == 15)
        self.assertEqual("Native workflow history · " + ", ".join(G.DAGS), table["title"])
        unit = (PLAN / "config/ns2604-research-progress.service").read_text()
        self.assertEqual(list(G.DAGS), re.findall(r"--dagu-dag (\S+)", unit))

    def test_command_center_reuses_source_panels_with_identical_queries(self):
        """Reused panels keep their source queries byte for byte; the board is a view, not a fork."""
        board = json.loads((PLAN / "config/grafana-command-center.json").read_text())
        sources = {"ecosystem-native": json.loads((PLAN / "config/grafana-ecosystem-native.json").read_text()),
                   "cc-lanes": json.loads((PLAN / "config/grafana-lanes.json").read_text())}
        reused = 0
        for panel in board["panels"]:
            match = re.search(r"Reused unchanged from the (ecosystem-native|cc-lanes) dashboard", panel.get("description", ""))
            if not match:
                continue
            source = next(p for p in sources[match.group(1)]["panels"] if p["title"] == panel["title"])
            self.assertEqual([t.get("expr") for t in source["targets"]], [t.get("expr") for t in panel["targets"]])
            self.assertEqual(source.get("datasource"), panel.get("datasource"))
            reused += 1
        self.assertGreaterEqual(reused, 13)

    def test_command_center_covers_the_six_rows_links_agentsview_and_keeps_input_text_out(self):
        text = (PLAN / "config/grafana-command-center.json").read_text()
        board = json.loads(text)
        self.assertEqual(("cc-god-view", "Command center"), (board["uid"], board["title"]))
        self.assertEqual(["Lane roster", "Progress", "Invoke rates", "Errors", "Gateway", "Coverage"],
                         [p["title"].split(" · ")[0] for p in board["panels"] if p["type"] == "row"])
        self.assertIn("http://127.0.0.1:21808", [link["url"] for link in board["links"]])
        self.assertEqual(len(board["panels"]), len({p["id"] for p in board["panels"]}))
        coverage = next(p for p in board["panels"] if p["title"].startswith("Runtime coverage"))
        for runtime in ("Codex", "Claude Code", "pi", "OpenCode", "goose", "Qwen Code", "oh-my-pi", "Hermes",
                        "Cline", "Muse Code"):
            self.assertIn(f"| {runtime} ", coverage["options"]["content"])
        stuck = next(p for p in board["panels"] if p["title"].startswith("STUCK"))
        self.assertTrue(any("unread_count" in t["expr"] and "prompt_has_text" in t["expr"] for t in stuck["targets"]))
        self.assertNotIn("input_text", json.dumps([t["expr"] for p in board["panels"] for t in p.get("targets", [])]))
        roster = next(p for p in board["panels"] if p["type"] == "table" and p["title"].startswith("Lane roster"))
        self.assertIn('"unattributed"', "\n".join(t["expr"] for t in roster["targets"]))
        self.assertNotRegex(text, r"input_text|\$__range|:1[0-9]{4}\b")

    def command_center(self):
        return json.loads((PLAN / "config/grafana-command-center.json").read_text())

    def test_command_center_unknown_prompt_state_leaves_no_value(self):
        """Regression: a null prompt_has_text reached Loki as "" and the STUCK table showed it as 0, "empty"."""
        stuck = next(p for p in self.command_center()["panels"] if p["title"].startswith("STUCK"))
        expr = next(t["expr"] for t in stuck["targets"] if t["legendFormat"] == "Prompt has text")
        known = re.search(r'\| prompt_has_text=~"([^"]+)" or status_context="([^"]+)" \| label_format', expr)
        self.assertIsNotNone(known, expr)
        self.assertLess(known.start(), expr.index("prompt_flag="))

        def kept(prompt, context=""):
            # Loki label filters use Prometheus matchers, anchored to the whole value (grafana/loki v3.7.8
            # pkg/logql/log/label_filter.go:360-377; vendor/.../prometheus/model/labels/regexp.go:76).
            return bool(re.fullmatch(known.group(1), prompt)) or context == known.group(2)
        self.assertEqual([True, True, False, False, True],
                         [kept("true"), kept("false"), kept(""), kept("unknown"), kept("", "tui:prompt-has-text")])

    def test_command_center_gateway_share_is_zero_for_an_hour_without_errors(self):
        stat = next(p for p in self.command_center()["panels"] if p["title"].startswith("Gateway 4xx and 5xx share"))
        for target in stat["targets"]:
            self.assertRegex(target["expr"], r'^\(sum\(increase\(.+\)\) or vector\(0\)\) / sum\(increase\(')

    def test_command_center_runtime_selector_covers_the_trial_profiles(self):
        panel = next(p for p in self.command_center()["panels"] if p["title"].startswith("Runtime worker tool calls"))
        selector = re.search(r'service_name=~"([^"]+)"', panel["targets"][0]["expr"]).group(1)
        for service in ("pi", "opencode", "goose", "qwen-code", "oh-my-pi", "ns-opencode-gpt", "ns-pi-claude"):
            self.assertRegex(service, f"^(?:{selector})$")

    def test_install_plan_registers_the_command_center(self):
        plan = json.loads((PLAN / "install-plan.json").read_text())
        row = next(r for r in plan["owners"] if r.get("slot") == "grafana")
        self.assertIn("$plan_dir/config/grafana-command-center.json", row["config_paths"])
        self.assertIn("$config_root/ecosystem-grafana-dashboards/command-center.json", row["config_paths"])
        record = row["command_center_dashboard_provisioning"]
        self.assertEqual(("cc-god-view", "nativestack2604-ecosystem", "Ecosystem"),
                         (record["uid"], record["provider"], record["folder"]))
        loop = "for uid in research-grand ecosystem-native native-foundation-data cc-lanes cc-god-view; do"
        self.assertIn(loop, json.dumps(row["acceptance"]))
        self.assertIn(loop, (PLAN / "accept.sh").read_text())

    def grafana_health_lines(self):
        plan = json.loads((PLAN / "install-plan.json").read_text())
        owner = next(row for row in plan["owners"] if row["slot"] == "grafana")
        return owner["acceptance"]["service_health"]["command"].splitlines()

    @unittest.skipUnless(shutil.which("jq"), "the native acceptance predicate needs jq")
    def test_acceptance_reads_each_dag_and_rejects_failed_native_history(self):
        # Execute the plan's real, non-pushing check against synthetic native history.
        checks = [line for line in self.grafana_health_lines() if "progress.py" in line]
        self.assertEqual(1, len(checks), "service acceptance must independently read Dagu history")
        check = checks[0]
        self.assertNotIn("--cache", check)
        self.assertEqual(list(G.DAGS), re.findall(r"--dagu-dag (\S+)", check))
        with tempfile.TemporaryDirectory() as d:
            history_home = Path(d)
            (history_home / ".local/bin").mkdir(parents=True)
            (history_home / ".dagu").mkdir()
            dagu = history_home / ".local/bin/dagu"
            fixture_check = check.replace("$HOME/.local/bin/dagu", str(dagu)).replace(
                "$HOME/.dagu", str(history_home / ".dagu"))
            env = dict(os.environ, repo_root=str(ROOT))
            for fail in (False, True):
                with self.subTest(native_history_failed=fail):
                    dagu.write_text("#!/usr/bin/python3\nimport sys\n" +
                                    ("sys.exit(1)\n" if fail else "print('[]')\n"))
                    dagu.chmod(0o700)
                    result = subprocess.run(["bash", "-o", "pipefail", "-c", fixture_check],
                                            capture_output=True, text=True, env=env)
                    self.assertEqual(1 if fail else 0, result.returncode, result.stderr)

    def test_acceptance_rejects_a_service_that_never_ran(self):
        checks = [line for line in self.grafana_health_lines() if "ExecMainExitTimestampMonotonic" in line]
        self.assertEqual(1, len(checks), "Result=success alone accepts a never-run oneshot")
        with tempfile.TemporaryDirectory() as d:
            binary = Path(d) / "systemctl"
            fixture_check = checks[0].replace("systemctl --user show", shlex.quote(str(binary)) + " --user show")
            for stamp, expected in (("0", 1), ("1000000", 0)):
                with self.subTest(exit_timestamp=stamp):
                    binary.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(stamp) + "\n")
                    binary.chmod(0o700)
                    result = subprocess.run(["bash", "-c", fixture_check], capture_output=True, text=True)
                    self.assertEqual(expected, result.returncode, result.stderr)

    def render(self, root):
        env = dict(os.environ, NS2604_OBSERVABILITY_DATA=str(root / "data"), XDG_CONFIG_HOME=str(root / "xdg"))
        def run(*args):
            return subprocess.run([sys.executable, str(PLAN / "config/observability_config.py"), *args,
                                   "--config-root", str(root / "config")], capture_output=True, text=True, env=env)
        return run

    def test_grafana_action_publishes_dashboards_units_and_news_setting(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = self.render(root)
            result = run("grafana", "--source-root", str(PLAN / "config"))
            self.assertEqual(0, result.returncode, result.stderr)
            config = root / "config"
            for uid in ("research-grand", "ecosystem-native", "native-foundation-data"):
                self.assertEqual(uid, json.loads((config / f"ecosystem-grafana-dashboards/{uid}.json").read_text())["uid"])
            command_center = config / "ecosystem-grafana-dashboards/command-center.json"
            self.assertEqual("cc-god-view", json.loads(command_center.read_text())["uid"])
            lanes = config / "grafana-dashboards/lanes.json"
            self.assertEqual("cc-lanes", json.loads(lanes.read_text())["uid"])
            self.assertFalse((config / "ecosystem-grafana-dashboards/lanes.json").exists())
            providers = (config / "grafana-provisioning/dashboards/native-stack.yaml").read_text()
            self.assertIn(f'path: {json.dumps(str(config / "ecosystem-grafana-dashboards"))}', providers)
            self.assertIn(f'path: {json.dumps(str(config / "grafana-dashboards"))}', providers)
            self.assertRegex((config / "grafana.ini").read_text(), r"(?m)^\[news\]\nnews_feed_enabled = false$")
            service = (config / "systemd/ns2604-research-progress.service").read_text()
            self.assertIn(f"ExecStart=/usr/bin/python3 {ROOT}/observability/grand-dashboard/progress.py --repo {ROOT} "
                          f"--cache {root / 'data'}/grand-dashboard/progress-cache.json "
                          "--loki-url http://127.0.0.1:21300/loki/api/v1/push", service)
            self.assertNotRegex(service, r"@[A-Z_]+@")
            ledger = json.loads((config / ".g4-source-digests.json").read_text())
            self.assertIn("systemd/ns2604-research-progress.timer", ledger)
            # Render validation remains isolated; install acceptance explicitly
            # opts into the unit byte comparison where install.sh puts them.
            result = run("grafana-check")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(1, run("grafana-check", "--installed-units").returncode)
            units = root / "xdg/systemd/user"
            units.mkdir(parents=True)
            for name in ("ns2604-research-progress.service", "ns2604-research-progress.timer"):
                shutil.copy(config / "systemd" / name, units / name)
            result = run("grafana-check", "--installed-units")
            self.assertEqual(0, result.returncode, result.stderr)
            installed_service = units / "ns2604-research-progress.service"
            correct_service = installed_service.read_text()
            installed_service.write_text(correct_service.replace("TimeoutStartSec=60", "TimeoutStartSec=61"))
            result = run("grafana-check", "--installed-units")
            self.assertEqual(1, result.returncode)
            self.assertIn("not installed as rendered", result.stderr)
            installed_service.write_text(correct_service)
            # A filename stem is not a provisioned UID: reject the exact earlier checker mismatch.
            correct_lanes = lanes.read_text()
            wrong_uid = json.loads(correct_lanes)
            wrong_uid["uid"] = "lanes"
            lanes.write_text(json.dumps(wrong_uid))
            result = run("grafana-check")
            self.assertEqual(1, result.returncode)
            self.assertIn("missing cc-lanes dashboard", result.stderr)
            lanes.write_text(correct_lanes)
            # A dashboard that still points at the workstation fails the check.
            stale = config / "ecosystem-grafana-dashboards/ecosystem-native.json"
            stale.write_text(stale.read_text().replace("ns2604-prometheus", "ecosystem-prometheus"))
            self.assertEqual(1, run("grafana-check").returncode)

    def test_all_provisioned_codex_token_panels_have_lower_bound_qualification(self):
        """Exercise the actual template-copy publisher, including token-layer."""
        config_module = G.GRAFANA_POLICY

        def panels(items):
            for panel in items:
                yield panel
                yield from panels(panel.get("panels", []))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.render(root)("grafana", "--source-root", str(PLAN / "config"))
            self.assertEqual(0, result.returncode, result.stderr)
            provisioned, matched, unqualified = set(), {}, []
            for _, output in config_module.GRAFANA_FILES:
                if not output.endswith(".json"):
                    continue
                board = json.loads((root / "config" / output).read_text())
                provisioned.add(board["uid"])
                for panel in panels(board["panels"]):
                    if not any(re.search(r"\b(?:ecosystem_)?codex_turn_token_usage_sum\b", target.get("expr", ""))
                               for target in panel.get("targets", [])):
                        continue
                    matched.setdefault(board["uid"], set()).add(panel["id"])
                    if "lower bound" not in panel.get("title", "").lower() or "lower bound" not in panel.get("description", "").lower():
                        unqualified.append((board["uid"], panel["id"]))
                    elif "newly born single-turn" not in panel["description"]:
                        unqualified.append((board["uid"], panel["id"], "missing reconciliation gate"))
            # Non-vacuous and exhaustive: enumerate every provisioned JSON asset,
            # and require all previously missed token-layer panels explicitly.
            self.assertEqual(set(config_module.DASHBOARD_UIDS.values()) | {"token-layer"}, provisioned)
            self.assertTrue({"token-layer", "ecosystem-native", "native-foundation-data", "cc-lanes"} <= set(matched))
            self.assertTrue({6, 21, 22} <= matched["token-layer"])
            self.assertGreaterEqual(sum(map(len, matched.values())), 7)
            self.assertEqual([], unqualified)

    def test_native_renderer_generates_qualified_token_layer(self):
        board = G.dashboards()["grafana-token-layer.json"]
        token_panels = {panel["id"]: panel for panel in board["panels"] if panel["id"] in (6, 21, 22)}
        self.assertEqual({6, 21, 22}, set(token_panels))
        for panel in token_panels.values():
            self.assertIn("lower bound", panel["title"].lower())
            self.assertIn("lower bound", panel["description"].lower())
            self.assertIn("newly born single-turn", panel["description"])

    def test_standalone_grafana_publisher_needs_no_repository_policy_module(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "installed-observability-config.py"
            shutil.copy(PLAN / "config/observability_config.py", script)
            # Synthetic emitter-only checkout: no ns2604_dashboards.py or other
            # helper module is present. The progress script is never executed.
            emitter = root / "checkout/observability/grand-dashboard/progress.py"
            emitter.parent.mkdir(parents=True)
            emitter.write_text("# local synthetic packaging fixture; never executed\n")
            env = dict(os.environ, NS2604_OBSERVABILITY_DATA=str(root / "data"), XDG_CONFIG_HOME=str(root / "xdg"))
            result = subprocess.run([
                sys.executable, str(script), "grafana", "--config-root", str(root / "config"),
                "--source-root", str(PLAN / "config"), "--repo-root", str(root / "checkout"),
            ], capture_output=True, text=True, env=env)
            self.assertEqual(0, result.returncode, result.stderr)
            board = json.loads((root / "config/grafana-dashboards/token-layer.json").read_text())
            for panel in board["panels"]:
                if panel["id"] in (6, 21, 22):
                    self.assertIn("lower bound", panel["title"].lower())
                    self.assertIn("lower bound", panel["description"].lower())

    def test_grafana_render_preserves_the_operator_private_lane_registry(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "config/lanes-registry.json"
            registry.parent.mkdir(parents=True)
            private = '{"canonical_roots":[{"lane":"fixture-lane","session_id":"fixture-native-root"}]}\n'
            registry.write_text(private)
            result = self.render(root)("grafana", "--source-root", str(PLAN / "config"))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(private, registry.read_text())
            ledger = json.loads((registry.parent / ".g4-source-digests.json").read_text())
            self.assertNotIn("lanes-registry.json", ledger)
            self.assertEqual({"canonical_roots": []}, json.loads((PLAN / "config/lanes-registry.json").read_text()))

    def test_grafana_action_refuses_a_source_outside_a_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source"
            shutil.copytree(PLAN / "config", source)
            result = self.render(root)("grafana", "--source-root", str(source))
            self.assertEqual(1, result.returncode)
            self.assertIn("--repo-root", result.stderr)

    def test_emitter_unit_arguments_run_against_a_synthetic_dagu(self):
        # Synthetic fixture: the rendered ExecStart, with %h at a temporary home and without --cache (no push).
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(0, self.render(root)("grafana", "--source-root", str(PLAN / "config")).returncode)
            line = next(l for l in (root / "config/systemd/ns2604-research-progress.service").read_text().splitlines()
                        if l.startswith("ExecStart="))
            home = root / "home"
            (home / ".local/bin").mkdir(parents=True)
            (home / ".dagu").mkdir()
            dagu = home / ".local/bin/dagu"
            dagu.write_text('#!/usr/bin/python3\nimport sys,json\nprint(json.dumps([dict(name=sys.argv[2], status="succeeded", '
                            'startedAt="2026-10-05T07:30:00Z", finishedAt="2026-10-05T07:31:00Z")]))\n')
            dagu.chmod(0o700)
            argv = shlex.split(line.removeprefix("ExecStart=").replace("%h", str(home)))
            cache = argv.index("--cache")
            del argv[cache:cache + 2]
            argv[0] = sys.executable
            result = subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            workflow = [r for r in json.loads(result.stdout) if r["record_kind"] == "workflow"]
            self.assertEqual([f"workflow/{dag}/history" for dag in G.DAGS],
                             [r["entity_id"] for r in workflow if r["entity_id"].endswith("/history")])
            self.assertTrue(all(r["state"] in ("observed / bounded local history", "succeeded") for r in workflow))


if __name__ == "__main__":
    unittest.main()
