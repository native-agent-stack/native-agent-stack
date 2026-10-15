"""Adapted review-port-probes.py for complete host files and transactional publication.

Keeps all three GPT behavioral assertions and the CC distro-identity regression. No installer, acceptance script,
native service, or live listener census is executed. Pass a pinned Grafana
v13.2.3 source directory for the original source-backed gRPC assertion.
"""
import argparse
import configparser
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

parser = argparse.ArgumentParser()
parser.add_argument("root", type=Path)
parser.add_argument("--grafana-source", type=Path, required=True)
args, unittest_args = parser.parse_known_args()
ROOT = args.root.resolve()
PLAN = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002"
sys.path.insert(0, str(ROOT))


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


class PortAllocationRegressions(unittest.TestCase):
    def client_fixture(self):
        config = module(ROOT / "tools/adoption/new_wsl_client_config.py", "review_distro_clients")
        values = json.loads((ROOT / "adoption/hosts/example.json").read_text())
        return config, values, config.load_plan(ROOT)

    def test_codex_shell_distro_identity_comes_from_the_host_file(self):
        config, values, plan = self.client_fixture()
        values["WSL_DISTRO_NAME"] = "NativeHorizonNY"
        with mock.patch.object(config.render_config, "load_host_values", return_value=values):
            resolved = config.host_values("fixture", plan, None, [])
        results, manifest, _, errors, _ = config.analyse(ROOT)
        self.assertEqual(errors, [])
        files = config.render(ROOT, results, plan, resolved, manifest)
        self.assertEqual(tomllib.loads(files["codex.config.toml"])["shell_environment_policy"]["set"]["WSL_DISTRO_NAME"],
                         "NativeHorizonNY")

    def test_missing_codex_shell_distro_identity_is_refused(self):
        config, values, plan = self.client_fixture()
        values.pop("WSL_DISTRO_NAME", None)
        with mock.patch.object(config.render_config, "load_host_values", return_value=values):
            with self.assertRaisesRegex(config.ConfigError, "WSL_DISTRO_NAME"):
                config.host_values("fixture", plan, None, [])

    def test_explicit_install_host_controls_staging_publication_and_dispatch(self):
        checker = module(PLAN / "check_plan.py", "review_check_plan")
        source = (PLAN / "install.sh").read_text()
        functions = checker.functions(source)
        # Complete fixtures for the reviewed tree's public host schema. Memory
        # remains explicit through AI_MEMORY_URL, as in the real example file.
        host = json.loads((ROOT / "adoption/hosts/example.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "ambient.json").write_text(json.dumps(dict(host, NS_PORT_GATEWAY="31128")))
            (path / "explicit.json").write_text(json.dumps(dict(host, NS_PORT_GATEWAY="41128")))
            settings = {"PATH": "/usr/bin:/bin", "HOME": str(path), "PYTHONDONTWRITEBYTECODE": "1",
                        "NS2604_HOST_FILE": str(path / "ambient.json"), "host_file": str(path / "explicit.json"),
                        "plan_dir": str(PLAN), "config_root": str(path / "config"),
                        "config_source_root": str(path / "rendered")}
            definitions = "\n".join(name + "() {\n" + functions[name] + "\n}" for name in
                                     ("run_command", "stage_plan_sources", "commit_allocation") if name in functions)
            if "stage_plan_sources" in functions:
                staging = "stage_plan_sources\n"
            else:
                # Exact old staging block: baseline still publishes early. The
                # current implementation uses its extracted transaction helper.
                staging = source[source.index('config_source_root="$(mktemp -d)"'):
                                 source.index("# Planned. Package prerequisites")]
            script = definitions + "\n" + staging + "\n" + (
                "run_command 'printf \"%s\\n\" http://127.0.0.1:21128/v1'\n"
                "python3 -c 'import json,os;from pathlib import Path;print(json.loads((Path(os.environ[\"config_source_root\"])/\"gpt-gateway-topology.json\").read_text())[\"gateway\"][\"endpoint\"])'\n"
                "failed=0; needs_execution=true\n"
                "if declare -F commit_allocation >/dev/null; then commit_allocation; fi\n"
                "python3 -c 'import json,os;from pathlib import Path;print(json.loads((Path(os.environ[\"config_root\"])/\".service-ports.json\").read_text())[\"NS_PORT_GATEWAY\"])'\n"
            )
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], env=settings,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(),
                             ["http://127.0.0.1:41128/v1", "http://127.0.0.1:41128/v1", "41128"])

    def test_optional_grafana_grpc_is_not_a_required_listener(self):
        upstream = args.grafana_source
        settings = (upstream / "pkg/setting/setting_grpc.go").read_text()
        service = (upstream / "pkg/services/grpcserver/service.go").read_text()
        manager = (upstream / "pkg/registry/backgroundsvcs/adapter/manager.go").read_text()
        self.assertIn('cfg.GRPCServer.Enabled = server.Key("enabled").MustBool(false)', settings)
        self.assertIn("return !s.enabled", service)
        self.assertIn("s.IsDisabled()", manager)
        renderer = module(PLAN / "config/observability_config.py", "review_grafana_ports")
        ports = renderer.service_ports()
        config = configparser.ConfigParser(interpolation=None, strict=False)
        config.read_string(re.search(r"(?ms)^\[grpc_server\]\n.*?(?=^\[)",
                                     (upstream / "conf/defaults.ini").read_text())[0])
        config.read_string(renderer.render_ports((PLAN / "config/grafana.ini").read_text(), ports))
        self.assertFalse(config.getboolean("grpc_server", "enabled", fallback=False))
        plan = json.loads((PLAN / "install-plan.json").read_text())
        snapshot = 'LISTEN 0 128 127.0.0.1:21301 0.0.0.0:* users:(("grafana",pid=42,fd=3))\n'
        self.assertEqual(renderer.listener_ownership(plan, ports, snapshot, slot="grafana"), [])

    def test_clients_accept_the_same_memory_allocation_as_the_plan(self):
        renderer = module(PLAN / "config/observability_config.py", "review_ports")
        config = module(ROOT / "tools/adoption/new_wsl_client_config.py", "review_clients")
        values = json.loads((ROOT / "adoption/hosts/example.json").read_text())
        values.update(AI_MEMORY_URL="127.0.0.1:39374", NS_PORT_GATEWAY="29374")
        allocation = renderer.service_ports(values)
        self.assertEqual((allocation["MEMORY"], allocation["GATEWAY"]), (39374, 29374))
        plan = config.load_plan(ROOT)
        with mock.patch.object(config.render_config, "load_host_values", return_value=values):
            resolved = config.host_values("fixture", plan, None, [])
        results, manifest, _, errors, _ = config.analyse(ROOT)
        self.assertEqual(errors, [])
        files = config.render(ROOT, results, plan, resolved, manifest)
        self.assertEqual(json.loads(files["mcp-servers.json"])["mcpServers"]["ai-memory"]["url"],
                         "http://127.0.0.1:39374/mcp")
        self.assertEqual(tomllib.loads(files["codex.config.toml"])["mcp_servers"]["ai-memory"]["url"],
                         "http://127.0.0.1:39374/mcp")
        self.assertEqual(tomllib.loads(files["codex.omniroute.config.toml"])["model_providers"]["omniroute"]["base_url"],
                         "http://127.0.0.1:29374/v1")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *unittest_args])
