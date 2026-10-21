#!/usr/bin/env python3
"""Measure a Claude Code launch's start-up context with the client's own /context report, at no model cost.

`claude -p "/context" --output-format json` runs the client's context report without a model turn (num_turns 0,
total_cost_usd 0 at 2.1.301): it lists the tokens each part of a session's start-up context takes, by category and per
MCP tool, custom agent, memory file and skill. This tool runs it for each variant of one role's launch (a control
without the components under test, then the control plus one component at a time), refuses any run that reached a
model, and writes one receipt per variant and a summary of each component's tokens over the control.

  measure --launch LAUNCH.json --out DIR [--claude PATH]   run every variant of a launch file and write receipts
  parse RESULT.json                                         print the parsed report of one saved /context JSON result

Receipts carry names, tokens and the variant's flags, never an absolute home path or an environment value. The token
figures are the client's own, as /context prints them (values of 1,000 and more are rounded to the nearest 100).
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA = "startup-context-receipt/1"
LAUNCH_SCHEMA = "startup-context-launch/1"
ROOT = Path(__file__).resolve().parents[2]
MCP_TEMPLATE = ROOT / "adoption" / "mcp" / "claude-user.json"
INSTALLER = ROOT / "tools" / "adoption" / "install_claude_profile.py"
TOKENS = re.compile(r"^~?\s*([0-9]+(?:\.[0-9]+)?)\s*([km]?)$", re.IGNORECASE)
TOTAL = re.compile(r"\*\*Tokens:\*\*\s*([^/]+?)\s*/\s*([^\s(]+)")
MODEL = re.compile(r"\*\*Model:\*\*\s*(\S+)")
TABLES = {"### Estimated usage by category": "categories", "### MCP Tools": "mcp_tools",
          "### Custom Agents": "custom_agents", "### Memory Files": "memory_files", "### Skills": "skills"}


def tokens(text: str) -> int | None:
    """'2.5k' -> 2500, '~200' -> 200, '689' -> 689, '1m' -> 1000000; None when the cell is not a token count."""
    match = TOKENS.match(text.strip().replace(",", ""))
    if not match:
        return None
    value, unit = float(match.group(1)), match.group(2).lower()
    return round(value * {"": 1, "k": 1_000, "m": 1_000_000}[unit])


def private_path(text: str, home: str) -> str:
    """A path as a receipt may show it: under the home directory as ~/..., never absolute, and with the home directory's
    dash-encoded form (as in ~/.claude/projects/-home-<user>-...) shortened to -~ as well."""
    root = home.rstrip("/")
    if root and (text == root or text.startswith(root + "/")):
        text = "~" + text[len(root):]
    elif text.startswith("/"):
        return "<absolute path outside home>"
    return text.replace(root.replace("/", "-") + "-", "-~-") if root else text


def private_text(text: str, home: str) -> str:
    """Any text a receipt keeps: an absolute path as private_path shows it, and the home directory inside it as ~."""
    if text.startswith("/"):
        return private_path(text, home)
    root = home.rstrip("/")
    return private_path(text.replace(root + "/", "~/"), home) if root else text


SECRET_KEY = re.compile(r"env|key|token|secret|password|credential|auth", re.IGNORECASE)


def sanitized(value, home: str, redact: bool = False):
    """A settings value as a receipt may keep it: every value under a key that can hold a credential or an environment
    value (env, apiKeyHelper, ...) is <redacted> with its key kept, and every other string goes through private_text."""
    if isinstance(value, dict):
        return {key: sanitized(item, home, redact or bool(SECRET_KEY.search(key))) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitized(item, home, redact) for item in value]
    if redact:
        return "<redacted>"
    return private_text(value, home) if isinstance(value, str) else value


def parse(result: str, home: str = "") -> dict:
    """The /context report's tables: total, model, categories, and the per-item tables with their tokens."""
    report = {"model": None, "total_tokens": None, "window_tokens": None}
    if match := MODEL.search(result):
        report["model"] = match.group(1)
    if match := TOTAL.search(result):
        report["total_tokens"], report["window_tokens"] = tokens(match.group(1)), tokens(match.group(2))
    section, header = None, None
    for line in result.splitlines():
        if line.startswith("### "):
            section, header = TABLES.get(line.strip()), None
            if section:
                report.setdefault(section, [])
            continue
        if not section or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if header is None:
            header = [cell.lower() for cell in cells]
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        row = dict(zip(header, cells))
        count = tokens(row.get("tokens", ""))
        if section == "categories":
            report[section].append({"category": row.get("category"), "tokens": count})
        elif section == "mcp_tools":
            report[section].append({"tool": row.get("tool"), "server": row.get("server"), "tokens": count})
        elif section == "memory_files":
            report[section].append({"type": row.get("type"), "path": private_path(row.get("path", ""), home),
                                    "tokens": count})
        else:
            name = row.get("skill") or row.get("agent type") or next(iter(row.values()), "")
            report[section].append({"name": name, "source": row.get("source"), "tokens": count})
    servers = {}
    for item in report.get("mcp_tools", []):
        servers[item["server"]] = servers.get(item["server"], 0) + (item["tokens"] or 0)
    report["mcp_tokens_by_server"] = dict(sorted(servers.items()))
    # With tool search on, MCP tools are deferred: listed here, loaded on demand, and outside the start-up total.
    report["mcp_tools_deferred"] = any("mcp tools (deferred)" in (c["category"] or "").lower()
                                       for c in report.get("categories", []))
    return report


def installer():
    """The repository's own MCP installer module (tools/adoption/install_claude_profile.py), for its template rendering."""
    spec = importlib.util.spec_from_file_location("install_claude_profile", INSTALLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def config_dir() -> Path:
    """The configuration directory the measured client reads, settings and plugins included: CLAUDE_CONFIG_DIR when set
    (env-vars.md:435, "default: ~/.claude"), else ~/.claude. run_context passes the environment on unchanged."""
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def plugin_name(variant: dict) -> str:
    """The plugin a variant names, without its marketplace (`name@marketplace`); empty when it names none."""
    return (variant.get("plugin") or "").split("@")[0]


def plugin_server_key(plugin: str, server: str) -> str:
    """The name Claude Code gives a plugin's MCP server, `plugin:<plugin>:<server>`, from which its tools are named
    mcp__plugin_<plugin>_<server>__*; measured at 2.1.301 (the init event of a $0 /context run lists the server by it)."""
    return f"plugin:{plugin}:{server}"


def plugin_servers(plugin: str) -> dict:
    """The MCP servers an installed plugin declares, loaded as Claude Code loads them: the plugin root's .mcp.json
    first, then each shape of `mcpServers` in .claude-plugin/plugin.json in order (a .json file path or an inline map,
    or an array of either), a later name replacing an earlier one; an MCP bundle (.mcpb, .dxt) is refused. The install
    path comes from ~/.claude/plugins/installed_plugins.json and renders ${CLAUDE_PLUGIN_ROOT}. --strict-mcp-config
    loads no MCP server outside --mcp-config, a plugin's included, so a plugin variant passes its plugin's servers
    there (README, "The launch"), under their native names (plugin_server_key)."""
    installed = json.loads((config_dir() / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
    entries = (installed.get("plugins") or {}).get(plugin) or []
    if not entries:
        raise SystemExit(f"startup_context: plugin {plugin} is not installed")
    root = Path(entries[0]["installPath"])

    def from_file(relative: str) -> dict:
        if relative.endswith((".mcpb", ".dxt")):
            raise SystemExit(f"startup_context: plugin {plugin} ships an MCP bundle, which this tool does not unpack")
        source = json.loads((root / relative).read_text(encoding="utf-8"))
        return source.get("mcpServers", source)

    servers = from_file(".mcp.json") if (root / ".mcp.json").exists() else {}
    manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    declared = manifest.get("mcpServers")
    for shape in declared if isinstance(declared, list) else [declared] if declared else []:
        servers.update(from_file(shape) if isinstance(shape, str) else shape)
    name = manifest.get("name") or plugin.split("@")[0]
    rendered = json.loads(json.dumps(servers).replace("${CLAUDE_PLUGIN_ROOT}", str(root)))
    return {plugin_server_key(name, server): spec for server, spec in rendered.items()}


def mcp_config(names: list[str], directory: Path, plugin: str | None = None) -> Path:
    """An --mcp-config file holding only the named servers from the repository's template (no secrets there), with its
    ${HOME} and ${ECO_ROOT} placeholders rendered as the installer renders them (render_servers, default_eco_root),
    plus the MCP servers of `plugin` when given (plugin_servers)."""
    data = json.loads(MCP_TEMPLATE.read_text(encoding="utf-8"))
    tool, home = installer(), Path.home()
    servers = tool.render_servers(data, home, tool.default_eco_root(home))
    missing = sorted(set(names) - set(servers))
    if missing:
        raise SystemExit(f"startup_context: servers not in the MCP template {MCP_TEMPLATE.name}: {', '.join(missing)}")
    chosen = {name: servers[name] for name in names}
    extra = plugin_servers(plugin) if plugin else {}
    if set(extra) & set(chosen):
        raise SystemExit(f"startup_context: plugin {plugin} declares a server the variant already lists")
    chosen.update(extra)
    path = directory / f"mcp-{'-'.join(sorted(name.replace(':', '_') for name in chosen)) or 'none'}.json"
    path.write_text(json.dumps({"mcpServers": chosen}, indent=1), encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def variant_argv(variant: dict, scratch: Path) -> list[str]:
    """The flags of one variant: a strict MCP set from the template when `mcp_servers` is given, `--settings` from
    `settings`, then `flags` as given."""
    argv = []
    if "mcp_servers" in variant:
        argv += ["--strict-mcp-config", "--mcp-config",
                 str(mcp_config(variant["mcp_servers"], scratch, variant.get("plugin")))]
    if "settings" in variant:
        argv += ["--settings", json.dumps(variant["settings"], sort_keys=True)]
    return argv + list(variant.get("flags") or [])


def run_context(claude: str, argv: list[str], cwd: str, timeout: int = 240) -> dict:
    """One /context run as stream-json, so the session's init event reports each MCP server's status and the loaded
    plugins; refused (SystemExit) unless the client answered without a model turn and at no cost."""
    done = subprocess.run([claude, "-p", "/context", "--output-format", "stream-json", "--verbose", *argv], cwd=cwd,
                          capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    init, result = {}, None
    for line in done.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            init = event
        elif event.get("type") == "result":
            result = event
    if result is None:
        raise SystemExit(f"startup_context: no result event (rc {done.returncode})")
    result["mcp_servers"] = [{"name": s.get("name"), "status": s.get("status")} for s in init.get("mcp_servers") or []]
    result["plugins"] = sorted(p.get("name") for p in init.get("plugins") or [] if p.get("name"))
    if result.get("is_error") or result.get("num_turns") != 0 or result.get("total_cost_usd") != 0:
        raise SystemExit("startup_context: refused: the run was not a $0 report (is_error "
                         f"{result.get('is_error')}, num_turns {result.get('num_turns')}, cost {result.get('total_cost_usd')})")
    return result


def client_version(claude: str) -> str:
    done = subprocess.run([claude, "--version"], capture_output=True, text=True, timeout=60)
    return done.stdout.strip().split(" ")[0] if done.returncode == 0 else "unknown"


def split_flags(argv: list[str]) -> list[str]:
    """argv with every `--flag=value` split into `--flag value`: the one spelling shown_flags reads, so a value is
    recognized by its flag however it was written, and a repeated flag is read at each place."""
    split = []
    for item in argv:
        flag, equals, value = item.partition("=")
        split += [flag, value] if item.startswith("--") and equals else [item]
    return split


def shown_flags(argv: list[str], home: str) -> list[str]:
    """Flags as a receipt may show them, each spelling read through split_flags: a generated --mcp-config file by its
    server set, every --settings value sanitized (sanitized), every other value through private_text."""
    shown = []
    argv = split_flags(argv)
    for index, flag in enumerate(argv):
        previous = argv[index - 1] if index else None
        if previous == "--mcp-config":
            shown.append(Path(flag).name)
        elif previous == "--settings":
            try:
                shown.append(json.dumps(sanitized(json.loads(flag), home), sort_keys=True))
            except ValueError:
                shown.append(private_text(flag, home))
        else:
            shown.append(private_text(flag, home))
    return shown


def measure(launch: dict, out: Path, claude: str, home: str) -> dict:
    if launch.get("schema") != LAUNCH_SCHEMA:
        raise SystemExit(f"startup_context: the launch file is not {LAUNCH_SCHEMA}")
    variants = launch["variants"]
    if [v["id"] for v in variants][:1] != ["control"]:
        raise SystemExit("startup_context: the first variant must be the control")
    out.mkdir(parents=True, exist_ok=True)
    version = client_version(claude)
    cwd = os.path.expanduser(launch.get("cwd") or ".")
    receipts = {}
    with tempfile.TemporaryDirectory() as scratch:
        for variant in variants:
            argv = variant_argv(variant, Path(scratch))
            result = run_context(claude, argv, cwd)
            receipt = {"schema": SCHEMA, "role_id": launch["role_id"], "family": launch.get("family", "claude-code"),
                       "variant": variant["id"], "component": variant.get("component"),
                       "measured_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "client_version": version, "cwd": private_path(cwd, home), "flags": shown_flags(argv, home),
                       "num_turns": result["num_turns"], "total_cost_usd": result["total_cost_usd"],
                       "mcp_servers": result["mcp_servers"], "plugins": result["plugins"],
                       "report": parse(result.get("result") or "", home)}
            path = out / f"{launch['role_id']}.{variant['id'].replace('/', '_')}.json"
            path.write_text(json.dumps(receipt, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
            receipts[variant["id"]] = receipt
    return summary(launch, receipts, out)


def owned_servers(variant: dict, names) -> set[str]:
    """The servers among `names` that belong to the variant's component: the component's own server, and every server
    of its plugin (plugin_server_key)."""
    plugin = plugin_name(variant)
    return {name for name in names
            if name == variant.get("component") or (plugin and name.startswith(plugin_server_key(plugin, "")))}


def loaded_component(variant: dict, receipt: dict) -> bool | None:
    """Whether the variant's component loaded: every server it owns (owned_servers) connected, and its plugin (when the
    variant names one) in the init event's list; a component without a server loads when it is listed as a plugin.
    None for the control. A delta is reported only for a component that loaded."""
    component = variant.get("component")
    if component is None:
        return None
    statuses = {s["name"]: s["status"] for s in receipt["mcp_servers"]}
    plugin = plugin_name(variant)
    mine = owned_servers(variant, statuses)
    if plugin and plugin not in receipt["plugins"]:
        return False
    if mine:
        return all(statuses[name] == "connected" for name in mine)
    return (plugin or component) in receipt["plugins"]


def baseline_differs(variant: dict, receipt: dict, control: dict) -> list[str]:
    """What the variant and the control do not share in the same state, the component, its plugin and every server they
    own aside: a server connected in one run only, or a plugin listed in one run only. A delta over the control needs
    this empty."""
    base = {s["name"]: s["status"] for s in control["mcp_servers"]}
    mine = {s["name"]: s["status"] for s in receipt["mcp_servers"]}
    own = {variant.get("component"), plugin_name(variant)} | owned_servers(variant, set(base) | set(mine))
    servers = sorted(name for name in (set(base) | set(mine)) - own if base.get(name) != mine.get(name))
    plugins = sorted((set(control["plugins"]) ^ set(receipt["plugins"])) - own)
    return servers + [f"plugin {name}" for name in plugins]


def summary(launch: dict, receipts: dict, out: Path) -> dict:
    control = receipts["control"]["report"]
    kinds = {v["id"]: v for v in launch["variants"]}
    rows = []
    for variant_id, receipt in receipts.items():
        report = receipt["report"]
        failed = sorted(s["name"] for s in receipt["mcp_servers"] if s["status"] != "connected")
        loaded = loaded_component(kinds[variant_id], receipt)
        differs = baseline_differs(kinds[variant_id], receipt, receipts["control"])
        rows.append({"variant": variant_id, "component": receipt.get("component"), "total_tokens": report["total_tokens"],
                     "servers_not_connected": failed, "component_loaded": loaded, "baseline_differs": differs,
                     "over_control": None if variant_id == "control" or not loaded or differs
                     or report["total_tokens"] is None or control["total_tokens"] is None
                     else report["total_tokens"] - control["total_tokens"],
                     "mcp_tokens_by_server": report["mcp_tokens_by_server"],
                     "mcp_tools_deferred": report["mcp_tools_deferred"]})
    doc = {"schema": "startup-context-summary/1", "role_id": launch["role_id"], "family": launch.get("family", "claude-code"),
           "client_version": receipts["control"]["client_version"], "rows": rows,
           "note": ("total_tokens is the client's own start-up total; over_control is a component's start-up cost. "
                    "mcp_tokens_by_server counts each server's tool definitions, which are outside the start-up total "
                    "when mcp_tools_deferred is true (loaded on demand by tool search)")}
    (out / f"{launch['role_id']}.summary.json").write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n",
                                                           encoding="utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("measure")
    m.add_argument("--launch", required=True, type=Path)
    m.add_argument("--out", required=True, type=Path)
    m.add_argument("--claude", default=os.path.expanduser("~/.local/bin/claude"))
    p = sub.add_parser("parse")
    p.add_argument("result", type=Path)
    args = parser.parse_args(argv)
    home = os.path.expanduser("~")
    if args.command == "parse":
        result = json.loads(args.result.read_text(encoding="utf-8"))
        print(json.dumps(parse(result.get("result") or "", home), indent=1))
        return 0
    doc = measure(json.loads(args.launch.read_text(encoding="utf-8")), args.out, args.claude, home)
    for row in doc["rows"]:
        print(f"{row['variant']}: {row['total_tokens']} tokens"
              + ("" if row["over_control"] is None else f" ({row['over_control']:+d} over the control)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
