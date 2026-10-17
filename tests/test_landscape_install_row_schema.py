"""The landscape install row schema (adoption/landscape-install-row.schema.json), a PROPOSAL of
docs/decisions/2026-10-16-landscape-install-manifest.md. Nothing here installs or runs a row: the schema checks are
structural, and the composition tests run synthetic checks under /bin/sh, as scripts/host_receipts.py record would.

The real row is the co-op's PASS screen of openai/openai-agents-python, converted to the uv-add route its README
documents. A second real conversion, anthropics/claude-agent-sdk-python, shows the stage C overlap rule: the 10-02
install plan already installs it. The other route rows are synthetic (example names, zero digests); their argv follows
the route tools' own help at the versions the record cites. Each refusal is shown against the shipped schema, and the
control removes the version and shell rules to show the refusals come from them. The functions below the fixtures
(unbound_pin, stage_c_slots, final_label_problems, model_record_problems, compose) state the generator's rules that
JSON Schema cannot express; horizon's checker carries the same rules.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

try:
    from jsonschema import Draft202012Validator
except ImportError as error:
    raise unittest.SkipTest("jsonschema is not installed; the install-row schema controls require it") from error


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "adoption/landscape-install-row.schema.json"
INSTALL_PLAN = "evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json"
FINAL_STACK = "catalogs/landscape/final-stack.json"
MODEL_CURRENCY = "catalogs/foundation/model-currency.json"
AGENTS_COMMIT = "17d994bd3045dae71acda676a4ef4762ed8ecd94"  # openai/openai-agents-python v0.24.0
SDK_COMMIT = "c10b52c674e5c709c7263544b38e8a5dad10e01d"  # anthropics/claude-agent-sdk-python v0.2.167
UV_COMMIT = "70fe1196a546e49148a73b1c592b2f74c33af80e"  # astral-sh/uv tag 0.12.22
ZERO_COMMIT = "0" * 40
ZERO_SHA256 = "0" * 64
# What each route's install argv must bind: the exact version, the commit, or the verified artifact.
VERSION_ROUTES = frozenset({"mise", "uv-tool", "uv-add", "npm-global", "claude-mcp", "codex-mcp", "vendor-installer"})
COMMIT_ROUTES = frozenset({"skills-cli", "claude-plugin", "codex-plugin"})
ARTIFACT_ROUTES = frozenset({"vendor-installer", "systemd-user"})
# The role-assignment matrix's sessions that take no framework (the install plan, Decision 9), and names that are not
# matrix rows.
REFUSED_ROLES = ("trader", "blind-judge", "blind-reviewer", "control-arm", "jev", "lane", "evidence-reviewer")
FLOATING_VERSIONS = ("latest", "stable", "main", "HEAD", "canary", "nightly", "", ">=0.24", "^0.24.0", "~0.24",
                     "0.24.*", "0.24.x", "0.24.X", "1.x", "0.24.0.x", "0.24", "v0.24.0", "==0.24.0", "~=0.24.0",
                     "!=0.24.0", "0.24.0 || 0.25.0")


def uv_source(line):
    return {"url": f"https://github.com/astral-sh/uv/blob/{UV_COMMIT}/crates/uv-cli/src/lib.rs#L{line}",
            "version": "0.12.22", "commit": UV_COMMIT, "path": "crates/uv-cli/src/lib.rs", "line": line}


def agents_row():
    """agent-sdks.openai.json PASSes this candidate at v0.24.0. Its README documents `uv add openai-agents`
    (README.md:39-45 at the pin), and pyproject.toml names no scripts, so it is a library on the uv-add route at the
    exact version. The screen documents no inverse, so the inverse is the route tool's own remove. Its OpenAI family
    profile points the client at the OmniRoute endpoint, so it dials the plan's gpt-gateway slot. The screen's prose
    roles ('runtime worker application builder', 'CC/co-op (programmed orchestration)') map to matrix rows; the role
    owner rules that mapping. The screen's start-up cost is an ESTIMATE of 0 for the library alone."""
    project = "envs/sdk-workers"
    return {
        "schema_version": 1,
        "id": "openai-agents-python",
        "candidate": {"repository": "https://github.com/openai/openai-agents-python",
                      "name": "OpenAI Agents SDK (Python)", "package_ids": ["openai-agents"]},
        "pin": {"version": "0.24.0", "tag": "v0.24.0", "commit": AGENTS_COMMIT},
        "screens": [{"layer": "foundation/agent-sdks", "family": "openai", "table": "agent-sdks.openai.json",
                     "candidate": "openai/openai-agents-python", "verdict": "PASS"}],
        "route": "uv-add",
        "install": [["uv", "add", "--project", project, "openai-agents==0.24.0"]],
        "check": [{"argv": ["uv", "tree", "--project", project, "--package", "openai-agents", "--depth", "0"],
                   "expect_exit": 0, "stdout_contains": "openai-agents v0.24.0", "absent_by": "text"}],
        "inverse": [["uv", "remove", "--project", project, "openai-agents"]],
        "sources": {
            "install": {"url": f"https://github.com/openai/openai-agents-python/blob/{AGENTS_COMMIT}/README.md#L39-L45",
                        "version": "0.24.0", "commit": AGENTS_COMMIT, "path": "README.md", "line": 45},
            "check": uv_source(1250),
            "inverse": uv_source(1165),
        },
        "dials": ["gpt-gateway"],
        "models": [{"id": "gpt-6-1-sol", "model_id": "gpt-6.1-sol",
                    "selector": {"where": "sdk-option", "key": "model"}}],
        "invoke": {"kind": "sdk", "names": ["openai-agents"]},
        "roles": ["builder", "command-center", "co-op"],
        "startup_context_cost": {"tokens": 0, "basis": "estimate",
                                 "method": "screen ESTIMATE, ceil(UTF-8 bytes / 4): the library injects no start-up "
                                           "text; the application's own instructions and tool schemas are not counted"},
        "label": "TRIAL",
    }


def claude_sdk_row():
    """agent-sdks.anthropic.json and native-clients.anthropic.json PASS this candidate at v0.2.167, converted the same
    way; the 10-02 install plan's claude-agent-sdk slot already installs it in stage C."""
    project = "envs/sdk-workers"
    return {**agents_row(),
            "id": "claude-agent-sdk-python",
            "candidate": {"repository": "https://github.com/anthropics/claude-agent-sdk-python",
                          "name": "Claude Agent SDK (Python)", "package_ids": ["claude-agent-sdk"]},
            "pin": {"version": "0.2.167", "tag": "v0.2.167", "commit": SDK_COMMIT},
            "screens": [{"layer": "foundation/agent-sdks", "family": "anthropic", "table": "agent-sdks.anthropic.json",
                         "candidate": "anthropics/claude-agent-sdk-python", "verdict": "PASS"},
                        {"layer": "foundation/native-clients", "family": "anthropic",
                         "table": "native-clients.anthropic.json", "candidate": "anthropics/claude-agent-sdk-python",
                         "verdict": "PASS"}],
            "install": [["uv", "add", "--project", project, "claude-agent-sdk==0.2.167"]],
            "check": [{"argv": ["uv", "tree", "--project", project, "--package", "claude-agent-sdk", "--depth", "0"],
                       "stdout_contains": "claude-agent-sdk v0.2.167", "absent_by": "text"}],
            "inverse": [["uv", "remove", "--project", project, "claude-agent-sdk"]],
            "sources": {
                "install": {"url": f"https://github.com/anthropics/claude-agent-sdk-python/blob/{SDK_COMMIT}/README.md"
                                   "#L5-L11", "version": "0.2.167", "commit": SDK_COMMIT, "path": "README.md",
                            "line": 8},
                "check": uv_source(1250),
                "inverse": uv_source(1165),
            },
            "dials": [],
            "models": [{"id": "claude-opus-5-5", "model_id": "claude-opus-5-5",
                        "selector": {"where": "sdk-option", "key": "model"}}],
            "invoke": {"kind": "sdk", "names": ["claude-agent-sdk"]},
            "roles": ["builder", "reviewer"],
            "startup_context_cost": {"tokens": None, "basis": "estimate",
                                     "method": "screen ESTIMATE with no total: the bundled client's start-up text is "
                                               "opaque"}}


def synthetic(route, install, check, inverse, invoke, models=(), **pin):
    return {
        "schema_version": 1,
        "id": "example-" + route,
        "candidate": {"repository": "https://github.com/example/" + route, "name": "Example " + route},
        "pin": {"version": "1.2.3", "commit": ZERO_COMMIT, **pin},
        "screens": [{"layer": "foundation/example-layer", "family": "openai", "table": "example-layer.openai.json",
                     "candidate": "example/" + route, "verdict": "PASS"}],
        "route": route,
        "install": install,
        "check": check,
        "inverse": inverse,
        "sources": {key: {"url": "https://github.com/example/" + route, "version": "1.2.3", "commit": ZERO_COMMIT}
                    for key in ("install", "check", "inverse")},
        "models": list(models),
        "invoke": invoke,
        "roles": ["builder"],
        "startup_context_cost": {"tokens": 0, "basis": "estimate", "method": "no start-up text"},
        "label": "TRIAL",
    }


def route_rows():
    market = "markets/example-market"
    return [
        agents_row(),
        synthetic("mise", [["mise", "use", "--global", "aqua:example/tool@1.2.3"]],
                  [{"argv": ["mise", "where", "aqua:example/tool@1.2.3"], "absent_by": "exit", "absent_exit": 1}],
                  [["mise", "unuse", "--global", "aqua:example/tool@1.2.3"]],
                  {"kind": "cli", "names": ["tool"]}),
        synthetic("uv-tool", [["uv", "tool", "install", "example-cli==1.2.3"]],
                  [{"argv": ["uv", "tool", "list"], "stdout_contains": "example-cli v1.2.3", "absent_by": "text"}],
                  [["uv", "tool", "uninstall", "example-cli"]],
                  {"kind": "cli", "names": ["example-cli"]}),
        synthetic("npm-global", [["npm", "install", "--global", "--ignore-scripts", "@example/cli@1.2.3"]],
                  [{"argv": ["npm", "ls", "--global", "@example/cli"], "stdout_contains": "@example/cli@1.2.3",
                    "absent_by": "exit", "absent_exit": 1}],
                  [["npm", "uninstall", "--global", "@example/cli"]],
                  {"kind": "cli", "names": ["example"]}),
        synthetic("claude-plugin",
                  [["git", "clone", "--no-checkout", "https://github.com/example/claude-plugin", market],
                   ["git", "-C", market, "checkout", "--detach", ZERO_COMMIT],
                   ["claude", "plugin", "marketplace", "add", "--scope", "local", market],
                   ["claude", "plugin", "install", "--scope", "local", "example@example-market"]],
                  [{"argv": ["claude", "plugin", "list"], "stdout_contains": "example@example-market",
                    "absent_by": "text"}],
                  [["claude", "plugin", "uninstall", "--scope", "local", "example@example-market"],
                   ["claude", "plugin", "marketplace", "remove", "example-market"]],
                  {"kind": "plugin", "names": ["example@example-market"]}),
        synthetic("claude-mcp", [["claude", "mcp", "add", "--scope", "local", "example", "--", "npx", "-y",
                                  "@example/mcp@1.2.3", "--model", "claude-sonnet-5-5"]],
                  [{"argv": ["claude", "mcp", "list"], "stdout_contains": "example", "absent_by": "text"}],
                  [["claude", "mcp", "remove", "--scope", "local", "example"]],
                  {"kind": "mcp-server", "names": ["example"]},
                  models=[{"id": "claude-sonnet-5-5", "model_id": "claude-sonnet-5-5",
                           "selector": {"where": "argv", "key": "--model"}}]),
        synthetic("codex-plugin", [["codex", "plugin", "marketplace", "add", "example/codex-plugin", "--ref",
                                    ZERO_COMMIT],
                                   ["codex", "plugin", "add", "example@example-market"]],
                  [{"argv": ["codex", "plugin", "list"], "stdout_contains": "example", "absent_by": "text"}],
                  [["codex", "plugin", "remove", "example@example-market"],
                   ["codex", "plugin", "marketplace", "remove", "example-market"]],
                  {"kind": "plugin", "names": ["example@example-market"]}),
        synthetic("codex-mcp", [["codex", "mcp", "add", "example", "--", "npx", "-y", "@example/mcp@1.2.3"]],
                  [{"argv": ["codex", "mcp", "list"], "stdout_contains": "example", "absent_by": "text"}],
                  [["codex", "mcp", "remove", "example"]],
                  {"kind": "mcp-server", "names": ["example"]}),
        synthetic("skills-cli", [["npx", "--yes", "skills@1.7.0", "add",
                                  f"https://github.com/example/skills/tree/{ZERO_COMMIT}/skills/example", "-a",
                                  "claude-code", "-y"]],
                  [{"argv": ["npx", "--yes", "skills@1.7.0", "list"], "stdout_contains": "example",
                    "absent_by": "text"}],
                  [["npx", "--yes", "skills@1.7.0", "remove", "example", "-y"]],
                  {"kind": "skill", "names": ["example"]}),
        synthetic("systemd-user", [["systemctl", "--user", "link", "{artifact}"],
                                   ["systemctl", "--user", "enable", "--now", "example.service"]],
                  [{"argv": ["systemctl", "--user", "show", "--property=ActiveState", "example.service"],
                    "stdout_contains": "ActiveState=active", "absent_by": "text"}],
                  [["systemctl", "--user", "disable", "--now", "example.service"]],
                  {"kind": "service", "names": ["example.service"]},
                  artifact={"url": f"https://github.com/example/systemd-user/raw/{ZERO_COMMIT}/example.service",
                            "sha256": ZERO_SHA256}),
        synthetic("vendor-installer", [["{artifact}", "1.2.3"]],
                  [{"argv": ["example", "--version"], "stdout_contains": "1.2.3", "absent_by": "exit",
                    "absent_exit": 127}],
                  [["example", "uninstall"]],
                  {"kind": "cli", "names": ["example"]},
                  artifact={"url": "https://example.com/install.sh", "sha256": ZERO_SHA256}),
    ]


def exact_spec(arg, version):
    """True when arg pins exactly this version: the version alone, PEP 440 `name==version` (extras allowed), or an npm
    or mise `[@scope/]name@version` / `backend:tool@version`. A comparator, a range or a channel never matches."""
    exact = re.escape(version)
    return bool(arg == version or re.fullmatch(rf"[A-Za-z0-9._\[\],-]+=={exact}", arg)
                or re.fullmatch(rf"(?:@[A-Za-z0-9._-]+/)?[A-Za-z0-9._:/-]+@{exact}", arg))


def unbound_pin(row):
    """True when the install argv binds nothing the route fetches: a version route names no exact pin.version, a
    commit route never names pin.commit (an immutable tree URL, a --ref, a detached checkout or an @commit source), or
    an artifact route never uses the verified {artifact}."""
    route, pin = row["route"], row["pin"]
    args = [arg for argv in row["install"] for arg in argv]
    if route in VERSION_ROUTES and not any(
            exact_spec(arg, pin["version"]) or (route == "vendor-installer" and arg == "v" + pin["version"])
            for arg in args):
        return True
    commit = pin.get("commit")
    if route in COMMIT_ROUTES and not (commit and any(
            arg == commit or arg.endswith("@" + commit) or f"/tree/{commit}/" in arg or arg.endswith(f"/tree/{commit}")
            for arg in args)):
        return True
    return route in ARTIFACT_ROUTES and not ("artifact" in pin and "{artifact}" in args)


def norm(url):
    return re.sub(r"^https?://", "", (url or "").lower()).rstrip("/").removesuffix(".git")


def stage_c_slots(row, plan):
    """The install plan's stage C slots that already install this row's repository; the generator refuses such a row
    until the plan's own row is retired through the plan."""
    return sorted(owner["slot"] for owner in plan["owners"]
                  if owner.get("installed") and norm(owner.get("repository")) == norm(row["candidate"]["repository"]))


def final_label_problems(row, stack):
    """A FINAL row needs every layer it screens in to be FINAL in final-stack.json with a winner from this repository
    whose run pin is this pin; anything else is TRIAL. Plan 6b makes FINAL rows defaults, so this fails closed."""
    if row["label"] != "FINAL":
        return []
    layers = {f'{item["catalog"]}/{item["layer_id"]}': item for item in stack.get("layers") or []}
    runs = {run["id"]: run for run in stack.get("runs") or []}
    pins = {row["pin"]["version"], row["pin"].get("commit")} - {None}
    problems = []
    for screen in row["screens"]:
        item = layers.get(screen["layer"])
        if item is None or item.get("terminal_state") != "FINAL":
            problems.append(f"{screen['layer']}: the layer is not FINAL")
        elif not any(norm(winner.get("repository")) == norm(row["candidate"]["repository"])
                     and str((runs.get(winner.get("run")) or {}).get("pin", "")).removeprefix("v") in pins
                     for winner in item.get("winners") or []):
            problems.append(f"{screen['layer']}: no winner from this repository at this pin")
    return problems


def model_record_problems(row, currency):
    """Each recorded selection joins the inventory: its slug exists and maps to the selected model id. A record, never
    a gate (the owner's addendum-19): age and status are the currency notice's business, not a refusal."""
    inventory = {model["id"]: model["model_id"] for model in currency.get("models") or []}
    return [f"{model['id']}: not in the inventory" if model["id"] not in inventory else
            f"{model['id']}: selects {inventory[model['id']]}, not {model['model_id']}"
            for model in row["models"]
            if model["id"] not in inventory or inventory[model["id"]] != model["model_id"]]


def compose(check, stage, project=None, codex_home=None):
    """The generator's composition of one check for scripts/host_receipts.py record, which runs each command with
    /bin/sh in the repository root and passes a receipt only when every exit is 0. A pipeline's status is its last
    command's, so the check's own exit gates any text match; the cleanup stage proves absence by the check's own rule.
    A Codex role location is the lane's CODEX_HOME, set on the argv; a Claude Code one is the role's project, entered
    before a braced body, so a failed cd can never read as a pass."""
    argv = list(check["argv"])
    if codex_home is not None:
        argv = ["env", f"CODEX_HOME={codex_home}", *argv]
    cmd = shlex.join(argv)
    want = check.get("expect_exit", 0)
    text = shlex.quote(check["stdout_contains"]) if "stdout_contains" in check else None
    if stage == "install":
        body = (f"{cmd}; test $? -eq {want}" if text is None else
                f"out=$({cmd}); test $? -eq {want} && printf '%s\\n' \"$out\" | grep -F -e {text}")
    elif check["absent_by"] == "exit":
        body = f"{cmd}; test $? -eq {check['absent_exit']}"
    else:
        body = f"out=$({cmd}); test $? -eq {want} && ! printf '%s\\n' \"$out\" | grep -q -F -e {text}"
    return body if project is None else f"cd {shlex.quote(project)} && {{ {body}; }}"


def sh(command):
    """Run a composed command the way scripts/host_receipts.py run_command does: shell=True, so /bin/sh."""
    return subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120).returncode


def prints(text, code=0):
    return [sys.executable, "-c", f"print({text!r}); raise SystemExit({code})"]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class LandscapeInstallRowSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load(SCHEMA)
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def errors(self, row, validator=None):
        return [error.message for error in (validator or self.validator).iter_errors(row)]

    def refused(self, row):
        self.assertNotEqual(self.errors(row), [], json.dumps(row)[:300])

    def test_every_route_has_a_valid_bound_row(self):
        rows = route_rows() + [claude_sdk_row()]
        routes = set(self.schema["properties"]["route"]["enum"])
        self.assertEqual({row["route"] for row in rows}, routes)
        self.assertEqual(VERSION_ROUTES | COMMIT_ROUTES | ARTIFACT_ROUTES, routes)
        for row in rows:
            with self.subTest(row=row["id"]):
                self.assertEqual(self.errors(row), [])
                self.assertFalse(unbound_pin(row))

    def test_prose_and_shell_strings_are_refused(self):
        for install in ([["pip install openai-agents"]], [["bash", "-c", "pip install openai-agents"]],
                        [["/usr/bin/sh", "-c", "uv add openai-agents"]],
                        [["env", "bash", "-c", "uv add openai-agents"]], [["uv", "add", "x", "&&", "zsh"]],
                        [["uv;", "add", "x"]], [[]], []):
            with self.subTest(install=install):
                row = agents_row()
                row["install"] = install
                self.refused(row)
        row = agents_row()
        row["check"][0]["argv"] = ["sh", "-c", "uv tree | grep openai-agents"]
        self.refused(row)

    def test_floating_or_unidentified_pins_are_refused(self):
        for version in FLOATING_VERSIONS:
            with self.subTest(version=version):
                row = agents_row()
                row["pin"]["version"] = version
                self.refused(row)
        for version in ("0.24.0", "2.0.0rc5", "2.0.0.dev0", "16.0.0-canary.5", "2026.10.3", "1.2.3+build.7"):
            with self.subTest(exact=version):
                row = agents_row()
                row["pin"]["version"] = version
                row["install"] = [["uv", "add", "--project", "envs/sdk-workers", f"openai-agents=={version}"]]
                self.assertEqual(self.errors(row), [])
                self.assertFalse(unbound_pin(row))
        row = agents_row()
        del row["pin"]["commit"]
        self.refused(row)
        row["pin"]["commit"] = AGENTS_COMMIT[:12]
        self.refused(row)
        rows = {row["route"]: row for row in route_rows()}
        for route, field in (("vendor-installer", "artifact"), ("systemd-user", "artifact"), ("skills-cli", "commit"),
                             ("claude-plugin", "commit"), ("codex-plugin", "commit")):
            with self.subTest(route=route, missing=field):
                row = deepcopy(rows[route])
                del row["pin"][field]
                if field == "commit":
                    row["pin"]["artifact"] = {"url": "https://example.com/a.tgz", "sha256": ZERO_SHA256}
                self.refused(row)

    def test_comparators_ranges_and_unpinned_routes_never_bind(self):
        for spec in ("openai-agents", "openai-agents>=0.24.0", "openai-agents~=0.24.0", "openai-agents!=0.24.0",
                     "openai-agents<=0.24.0", "openai-agents===0.24.0", "openai-agents>0.24.0",
                     "openai-agents==0.24.01", "openai-agents==0.24.0.post1"):
            with self.subTest(spec=spec):
                row = agents_row()
                row["install"] = [["uv", "add", "--project", "envs/sdk-workers", spec]]
                self.assertTrue(unbound_pin(row))
        rows = {row["route"]: row for row in route_rows()}
        for spec in ("@example/cli", "@example/cli@^1.2.3", "@example/cli@~1.2.3", "@example/cli@1.2",
                     "@example/cli@1.2.x", "@example/cli@latest", "@example/cli@>=1.2.3"):
            with self.subTest(npm=spec):
                row = deepcopy(rows["npm-global"])
                row["install"] = [["npm", "install", "--global", spec]]
                self.assertTrue(unbound_pin(row))
        unbound = {
            "claude-mcp": [["claude", "mcp", "add", "--scope", "local", "example", "--", "npx", "-y", "@example/mcp"]],
            "codex-mcp": [["codex", "mcp", "add", "example", "--", "npx", "-y", "@example/mcp@latest"]],
            "claude-plugin": [["claude", "plugin", "install", "--scope", "local", "example@example-market"]],
            "codex-plugin": [["codex", "plugin", "marketplace", "add", "example/codex-plugin"],
                             ["codex", "plugin", "add", "example@example-market"]],
            "skills-cli": [["npx", "--yes", "skills@1.7.0", "add",
                            "https://github.com/example/skills/tree/main/skills/x"]],
            "systemd-user": [["systemctl", "--user", "enable", "--now", "example.service"]],
            "vendor-installer": [["{artifact}"]],
            "mise": [["mise", "use", "--global", "aqua:example/tool@1.2"]],
        }
        for route, install in unbound.items():
            with self.subTest(route=route):
                row = deepcopy(rows[route])
                row["install"] = install
                self.assertTrue(unbound_pin(row))
        vendor = deepcopy(rows["vendor-installer"])
        vendor["install"] = [["{artifact}", "--version", "v1.2.3"]]
        self.assertFalse(unbound_pin(vendor))

    def test_the_overlap_rule_finds_a_stage_c_row(self):
        plan = load(INSTALL_PLAN)
        self.assertEqual(stage_c_slots(claude_sdk_row(), plan), ["claude-agent-sdk"])
        self.assertEqual(stage_c_slots(agents_row(), plan), [])

    def test_a_final_label_needs_final_layers_with_this_winner_at_this_pin(self):
        row = claude_sdk_row()
        row["label"] = "FINAL"
        row["startup_context_cost"] = {"tokens": 1834, "basis": "measured", "method": "count_tokens",
                                       "receipt": "claude-agent-sdk-python.startup.json"}
        self.assertEqual(self.errors(row), [])
        self.assertEqual(len(final_label_problems(row, load(FINAL_STACK))), 2)
        stack = {"runs": [{"id": "r", "pin": "v0.2.167"}, {"id": "old", "pin": "0.2.163"}],
                 "layers": [{"catalog": "foundation", "layer_id": layer, "terminal_state": "FINAL",
                             "winners": [{"repository": "https://github.com/anthropics/claude-agent-sdk-python.git",
                                          "run": "r"}]}
                            for layer in ("agent-sdks", "native-clients")]}
        self.assertEqual(final_label_problems(row, stack), [])
        stack["layers"][1]["winners"][0]["run"] = "old"
        self.assertEqual(final_label_problems(row, stack), ["foundation/native-clients: no winner from this "
                                                             "repository at this pin"])
        self.assertEqual(final_label_problems(claude_sdk_row(), stack), [])

    def test_models_are_a_record_joined_to_the_inventory(self):
        currency = load(MODEL_CURRENCY)
        for row in route_rows() + [claude_sdk_row()]:
            with self.subTest(row=row["id"]):
                self.assertEqual(model_record_problems(row, currency), [])
        row = agents_row()
        row["models"][0]["model_id"] = "gpt-6-1-sol"
        self.assertEqual(model_record_problems(row, currency), ["gpt-6-1-sol: selects gpt-6.1-sol, not gpt-6-1-sol"])
        row["models"][0]["id"] = "gpt-0-unknown"
        self.assertEqual(model_record_problems(row, currency), ["gpt-0-unknown: not in the inventory"])

    def test_a_missing_inverse_check_invoke_or_source_is_refused(self):
        for field in ("inverse", "check", "sources", "screens", "models", "invoke", "roles", "startup_context_cost",
                      "label"):
            with self.subTest(field=field):
                row = agents_row()
                del row[field]
                self.refused(row)
        for field in ("install", "check", "inverse"):
            with self.subTest(source=field):
                row = agents_row()
                del row["sources"][field]
                self.refused(row)
        for invoke in ({"kind": "sdk", "names": []}, {"kind": "library", "names": ["x"]}, {"kind": "sdk"},
                       {"kind": "sdk", "names": ["openai agents"]}):
            with self.subTest(invoke=invoke):
                row = agents_row()
                row["invoke"] = invoke
                self.refused(row)
        row = agents_row()
        row["dials"] = ["GPT Gateway"]
        self.refused(row)
        unpinned = agents_row()
        unpinned["sources"]["install"] = {"url": "https://www.npmjs.com/package/@openai/agents"}
        self.refused(unpinned)
        unpinned["sources"]["install"]["version"] = "0.24.0"
        self.refused(unpinned)
        unpinned["sources"]["install"]["read_at_utc"] = "2026-10-16T02:39:34Z"
        self.assertEqual(self.errors(unpinned), [])

    def test_fenced_or_unknown_roles_and_unscreened_rows_are_refused(self):
        for role in REFUSED_ROLES:
            with self.subTest(role=role):
                row = agents_row()
                row["roles"] = ["builder", role]
                self.refused(row)
        for verdict in ("INCOMPLETE", "FAIL", "pass"):
            with self.subTest(verdict=verdict):
                row = claude_sdk_row()
                row["screens"][1]["verdict"] = verdict
                self.refused(row)
        row = agents_row()
        row["screens"] = []
        self.refused(row)

    def test_final_needs_a_measured_cost_with_a_receipt(self):
        row = agents_row()
        row["label"] = "FINAL"
        self.refused(row)
        row["startup_context_cost"] = {"tokens": 1834, "basis": "measured",
                                       "method": "count_tokens on the role's start-up text"}
        self.refused(row)
        row["startup_context_cost"]["receipt"] = "openai-agents-python.startup.json"
        self.assertEqual(self.errors(row), [])
        row["startup_context_cost"]["tokens"] = None
        self.refused(row)
        row["startup_context_cost"].update(tokens=1834, basis="estimate")
        self.refused(row)

    def test_credentials_digests_paths_and_extra_fields_are_refused(self):
        row = agents_row()
        row["candidate"]["repository"] = "https://user:token@github.com/openai/openai-agents-python"
        self.refused(row)
        for receipt in ("/var/tmp/receipt.json", "../receipt.json", "a" * 64):
            with self.subTest(receipt=receipt):
                row = agents_row()
                row["startup_context_cost"]["receipt"] = receipt
                self.refused(row)
        for field, value in (("port", 21808), ("service", "example.service"), ("family", "openai")):
            with self.subTest(field=field):
                row = agents_row()
                row[field] = value
                self.refused(row)
        row = agents_row()
        row["route"] = "pip"
        self.refused(row)

    def test_model_selection_and_absence_rules_are_enforced(self):
        for models in ([{"id": "Claude Opus 5.5", "model_id": "x", "selector": {"where": "argv", "key": "--model"}}],
                       [{"id": "claude-opus-5-5", "selector": {"where": "argv", "key": "--model"}}],
                       [{"id": "claude-opus-5-5", "model_id": "claude-opus-5-5", "selector": "the worker's option"}],
                       [{"id": "claude-opus-5-5", "model_id": "claude-opus-5-5",
                         "selector": {"where": "env", "key": "MODEL"}}],
                       [{"id": "claude-opus-5-5", "model_id": "claude opus",
                         "selector": {"where": "argv", "key": "--model"}}]):
            with self.subTest(models=models):
                row = agents_row()
                row["models"] = models
                self.refused(row)
        for change in ({"absent_by": "exit"}, {"absent_by": "negation"}, {"absent_by": "gone"},
                       {"absent_by": "exit", "absent_exit": 256}):
            with self.subTest(change=change):
                row = agents_row()
                row["check"][0].update(change)
                self.refused(row)
        for field in ("absent_by", "stdout_contains"):
            with self.subTest(missing=field):
                row = agents_row()
                del row["check"][0][field]
                self.refused(row)

    def test_the_control_shows_the_refusals_come_from_the_rules(self):
        loose = deepcopy(self.schema)
        loose["properties"]["pin"]["properties"]["version"] = {"type": "string"}
        argv = loose["$defs"]["argv"]
        del argv["prefixItems"][0]["not"]
        del argv["items"]["not"]
        validator = Draft202012Validator(loose)
        rows = []
        for version in ("latest", "0.24.x", "canary"):
            row = agents_row()
            row["pin"]["version"] = version
            rows.append(row)
        shell = agents_row()
        shell["install"] = [["bash", "-c", "pip install openai-agents"]]
        for row in rows + [shell]:
            self.assertNotEqual(self.errors(row), [])
            self.assertEqual(self.errors(row, validator), [])


class CompositionTests(unittest.TestCase):
    """api-actions' review of 2bb57790: the check's own exit gates its text, and absence is proved, not assumed."""

    def test_a_check_that_prints_its_text_but_fails_fails_the_install_receipt(self):
        check = {"argv": prints("example v1.2.3", 1), "stdout_contains": "example v1.2.3", "absent_by": "text"}
        self.assertNotEqual(sh(compose(check, "install")), 0)
        self.assertEqual(sh(compose({**check, "argv": prints("example v1.2.3", 0)}, "install")), 0)
        self.assertNotEqual(sh(compose({**check, "argv": prints("other", 0)}, "install")), 0)
        plain = {"argv": prints("x", 2), "expect_exit": 2, "absent_by": "exit", "absent_exit": 127}
        self.assertEqual(sh(compose(plain, "install")), 0)
        self.assertNotEqual(sh(compose({**plain, "argv": prints("x", 0)}, "install")), 0)
        # Control: the plain pipeline the review refused takes grep's status and passes the failed check.
        self.assertEqual(sh(f"{shlex.join(prints('example v1.2.3', 1))} | grep -F -e 'example v1.2.3'"), 0)

    def test_cleanup_reads_only_the_documented_absence(self):
        gone = {"argv": ["example-gone-binary-xyz", "--version"], "absent_by": "exit", "absent_exit": 127}
        self.assertEqual(sh(compose(gone, "cleanup")), 0)
        self.assertNotEqual(sh(compose({**gone, "argv": prints("crashed", 2)}, "cleanup")), 0)
        text = {"argv": prints("other", 0), "stdout_contains": "example v1.2.3", "absent_by": "text"}
        self.assertEqual(sh(compose(text, "cleanup")), 0)
        self.assertNotEqual(sh(compose({**text, "argv": prints("example v1.2.3", 0)}, "cleanup")), 0)
        self.assertNotEqual(sh(compose({**text, "argv": prints("", 1)}, "cleanup")), 0)
        # Control: a bare negation would read the crash as a removal; the schema has no such fallback.
        self.assertEqual(sh(f"! {shlex.join(prints('crashed', 2))}"), 0)

    def test_a_failed_cd_into_a_role_location_never_reads_as_a_pass(self):
        with tempfile.TemporaryDirectory() as scratch:
            missing = str(Path(scratch) / "no-such-project")
            cd_exit = sh(f"cd {shlex.quote(missing)}")
            self.assertNotEqual(cd_exit, 0)
            check = {"argv": prints("x", 0), "absent_by": "exit", "absent_exit": cd_exit}
            self.assertNotEqual(sh(compose(check, "cleanup", project=missing)), 0)
            # Control: without the braces, the cd failure's own status satisfies the absent exit.
            self.assertEqual(sh(f"cd {shlex.quote(missing)} && {compose(check, 'cleanup')}"), 0)
            self.assertEqual(sh(compose({**check, "absent_by": "text", "stdout_contains": "x"}, "install",
                                        project=scratch)), 0)

    def test_a_codex_role_location_sets_the_lane_home_on_the_argv(self):
        command = compose({"argv": ["codex", "plugin", "list"], "stdout_contains": "example", "absent_by": "text"},
                          "install", codex_home="/srv/lanes/a b")
        self.assertTrue(command.startswith("out=$(env 'CODEX_HOME=/srv/lanes/a b' codex plugin list); "))


if __name__ == "__main__":
    unittest.main()
