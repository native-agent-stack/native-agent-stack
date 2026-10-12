#!/usr/bin/env python3
"""Read-only drift report between the MCP servers the committed templates render for the new WSL distribution and the servers this account's clients have registered:

  python3 tools/adoption/mcp_template_drift.py [--home DIR] [--eco-root DIR] [--claude-json FILE] [--codex-config FILE]
                                               [--acknowledged FILE] [--with-authorization-settings] [--json]

The template side is what `new_wsl_client_config.py --render` writes (mcp-servers.json for Claude Code, the mcp_servers tables of codex.config.toml for Codex), computed in process by the same functions from the host values of
adoption/templates/wsl/host.new-distro.json.template moved to --home; the ${HOME} and ${ECO_ROOT} placeholders of the Claude file are rendered the way install_claude_profile.py renders them when it registers a server.
The live side is the user scope of Claude Code (`mcpServers` in ~/.claude.json, where `claude mcp add --scope user` writes) and `[mcp_servers.*]` of ~/.codex/config.toml. Project scope (.mcp.json), local scope and servers
that a plugin provides are not read. Nothing is written.

One row per client and server name: SAME; DIFFERS (the differing fields named); TEMPLATE-ONLY (rendered, not registered); LIVE-ONLY (registered, not rendered). --acknowledged names a JSON file of the differences a decision record
accepts (client, name, row, for DIFFERS the exact fields, a reason and a source: a regular file beneath this repository, named by a relative path and optionally followed by #heading): such a row is reported `ack <row>`
and does not fail the run, and an entry that matches no current row is reported STALE-ACK and does fail it, so an exception cannot outlive its cause. There is no default file: the entries describe one host.

No value of a registration is printed, in either format or on either stream. Values are compared in memory and withheld from every description: environment variable and header NAMES are shown, never their values; a URL
is shown as scheme://host (no userinfo, port, path, query or fragment); a command as its file name (no directory); an argument only when it is an option name (`--port`, `-y`, or the name in `--port=VALUE`), every other
argument as <withheld>. A description is built from those names, counts and fixed words, so a value cannot reach it by taking a shape the report did not foresee.
Exit 0: every difference is acknowledged; 1: an unacknowledged difference or a stale acknowledgement; 2: an input cannot be read.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
import install_claude_profile as icp  # noqa: E402
import new_wsl_client_config as new_wsl  # noqa: E402
import render_config  # noqa: E402

ACK_SCHEMA = "native-agent-stack/mcp-template-drift-acknowledged/v1"
CLIENTS = ("claude", "codex")
ROWS = ("DIFFERS", "TEMPLATE-ONLY", "LIVE-ONLY")
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")
WITHHELD = "<withheld>"
NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,63}\Z")                  # a variable, header, field or server name
OPTION = re.compile(r"(?:--[a-z][a-z0-9_]*(?:-[a-z0-9_]+)*|-[A-Za-z])\Z")   # an option name: --kebab-case or one letter
COMMAND = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]{0,63}\Z")               # the file name of a program
HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?\Z")     # a host name or an IPv4 address
CLAUDE_FIELDS = ("type", "url", "command", "args", "env", "headers")


class DriftError(ValueError):
    """An input cannot be read or does not have the expected shape."""


def render_files(home: Path, authorization: bool = False, eco_root: Path | None = None) -> dict:
    """{file name: text} of `new_wsl_client_config.py --render` for an account whose home is `home` (the host values of the distribution's template, moved to that home, with ECO_ROOT set to `eco_root` when given)."""
    template = (ROOT / new_wsl.HOST_TEMPLATE_REL).read_text(encoding="utf-8")
    values = json.loads(template.replace("${WSL_USER}", "example"))
    original = render_config.load_host_values
    render_config.load_host_values = lambda host: dict(values)
    try:
        results, manifest, plan, errors, _ = new_wsl.analyse(ROOT, check_blocks=False, authorization=authorization)
        if errors:
            raise DriftError("the new-WSL client configuration check fails, so nothing can be rendered: " + "; ".join(errors[:3]))
        values = new_wsl.host_values("drift", plan, home, new_wsl.wired_path_dirs(results))
        if eco_root is not None:
            values["ECO_ROOT"] = str(eco_root)
        return new_wsl.render(ROOT, results, plan, values, manifest)
    except DriftError:
        raise
    except (new_wsl.ConfigError, render_config.RenderError, OSError, KeyError, ValueError) as error:
        raise DriftError(f"the render failed: {error}") from error
    finally:
        render_config.load_host_values = original


def render_templates(home: Path, eco_root: Path, authorization: bool = False) -> tuple[dict, dict]:
    """(Claude servers, Codex servers) as the render writes them under the ecosystem prefix `eco_root`; the Claude file keeps ${HOME} and ${ECO_ROOT}, which `claude mcp add` receives rendered."""
    files = render_files(home, authorization, eco_root)
    claude = icp.render_servers(json.loads(files["mcp-servers.json"]), home, eco_root)
    codex = tomllib.loads(files["codex.config.toml"]).get("mcp_servers", {})
    return claude, codex


def read_claude(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DriftError(f"cannot read {path}: {error}") from error
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        raise DriftError(f"{path} has no `mcpServers` object (the user scope of Claude Code)")
    return servers


def read_codex(path: Path) -> dict:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DriftError(f"cannot read {path}: {error}") from error
    return data.get("mcp_servers", {})


def normalise_claude(spec: dict) -> dict:
    """The fields that decide what Claude Code starts. A registration made as `env NAME=value ... command args` carries its environment in args; it compares equal to the same server with an env object."""
    args, env, command = list(spec.get("args") or []), dict(spec.get("env") or {}), spec.get("command")
    if command == "env" and args:
        while args and ENV_ASSIGNMENT.match(args[0]):
            name, _, value = args.pop(0).partition("=")
            env[name] = value
        if args:
            command, args = args[0], args[1:]
    kind = spec.get("type") or ("http" if spec.get("url") else "stdio")
    out = {"type": kind, "url": spec.get("url"), "command": command, "args": args, "env": env, "headers": dict(spec.get("headers") or {})}
    out.update({key: value for key, value in spec.items() if key not in CLAUDE_FIELDS})
    return out


def normalise_codex(spec: dict) -> dict:
    """The fields that decide what Codex starts; `enabled` defaults to true and the timeouts compare as numbers (60 and 60.0 are the same)."""
    rest = dict(spec)
    out = {"url": rest.pop("url", None), "command": rest.pop("command", None), "args": list(rest.pop("args", None) or []), "env": dict(rest.pop("env", None) or {}),
           "env_vars": sorted(rest.pop("env_vars", None) or [], key=lambda item: json.dumps(item, sort_keys=True)), "enabled": rest.pop("enabled", True)}
    for key in ("startup_timeout_sec", "tool_timeout_sec"):
        if key in rest:
            out[key] = float(rest.pop(key))
    for key in ("enabled_tools", "disabled_tools"):
        if key in rest:
            out[key] = sorted(rest.pop(key))
    out.update(rest)
    return out


def differing_fields(template: dict, live: dict) -> list[str]:
    return sorted(key for key in template.keys() | live.keys() if template.get(key) != live.get(key))


def safe_name(name) -> str:
    """A name (variable, header, field or server) as printed: itself when it has the shape of one, else the placeholder."""
    return name if isinstance(name, str) and NAME.fullmatch(name) else WITHHELD


def shown_url(url) -> str:
    """scheme://host of a URL; userinfo, port, path, query and fragment are withheld, and a URL that does not parse is withheld whole."""
    try:
        parts = urlsplit(str(url))
        scheme, host = parts.scheme.lower(), parts.hostname or ""
    except ValueError:
        return WITHHELD
    return f"{scheme}://{host}" if scheme in ("http", "https", "ws", "wss") and HOST.fullmatch(host) else WITHHELD


def shown_command(command) -> str:
    """The file name of the program; the directory (which holds the account's home) is not printed."""
    if not command:
        return "(no command)"
    name = os.path.basename(str(command).rstrip("/"))
    return name if COMMAND.fullmatch(name) else WITHHELD


def shown_arg(arg) -> str:
    """An option name (`--port`, `-y`, and the name in `--port=VALUE`, which keeps `=<withheld>`); every other argument is the placeholder, whatever it looks like."""
    name, equals, _ = str(arg).partition("=")
    if len(name) <= 48 and OPTION.fullmatch(name):
        return name + (f"={WITHHELD}" if equals else "")
    return WITHHELD


def describe(spec: dict) -> str:
    """One line for a normalised spec, built from names, counts and fixed words: its type, how it starts (scheme://host, or the command's file name), its arguments (option names; the rest withheld) and the NAMES
    of its env and headers."""
    names = sorted(safe_name(name) for name in spec.get("env") or {}) + sorted(f"header:{safe_name(name)}" for name in spec.get("headers") or {})
    start = shown_url(spec["url"]) if spec.get("url") else shown_command(spec.get("command"))
    args = [shown_arg(a) for a in spec.get("args") or []]
    shown_args = " ".join(args) if len(" ".join(args)) <= 90 else f"[{len(args)} args]"
    kind = spec.get("type") or ("http" if spec.get("url") else "stdio")
    return " ".join(part for part in (safe_name(kind), start, shown_args, f"env/headers: {','.join(names)}" if names else "") if part)


def compare(client: str, template: dict, live: dict) -> list[dict]:
    normalise = normalise_claude if client == "claude" else normalise_codex
    rows = []
    for name in sorted(template.keys() | live.keys()):
        if name not in live:
            rows.append({"client": client, "name": name, "row": "TEMPLATE-ONLY", "fields": [], "template": describe(normalise(template[name])), "live": None})
        elif name not in template:
            rows.append({"client": client, "name": name, "row": "LIVE-ONLY", "fields": [], "template": None, "live": describe(normalise(live[name]))})
        else:
            a, b = normalise(template[name]), normalise(live[name])
            fields = differing_fields(a, b)
            rows.append({"client": client, "name": name, "row": "DIFFERS" if fields else "SAME", "fields": fields, "template": describe(a), "live": describe(b)})
    return rows


def repository_file(source: str) -> bool:
    """Whether `source` (a relative path, optionally followed by #heading) names a regular file beneath this repository: absolute paths and `..` are refused and symlinks are resolved first."""
    name = source.split("#", 1)[0]
    if not name or Path(name).is_absolute() or ".." in Path(name).parts:
        return False
    try:
        resolved = (ROOT / name).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return False
    return resolved.is_file() and resolved.is_relative_to(ROOT.resolve())


def load_acknowledged(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DriftError(f"cannot read {path}: {error}") from error
    if not isinstance(data, dict) or data.get("schema") != ACK_SCHEMA or not isinstance(data.get("acknowledged"), list):
        raise DriftError(f"{path}: expected schema {ACK_SCHEMA} and an `acknowledged` list")
    problems = []
    for index, entry in enumerate(data["acknowledged"]):
        where = f"acknowledged[{index}]"
        if not isinstance(entry, dict):
            problems.append(f"{where} is not an object")
            continue
        if entry.get("client") not in CLIENTS:
            problems.append(f"{where}: client must be one of {CLIENTS}")
        if not isinstance(entry.get("name"), str) or not entry.get("name"):
            problems.append(f"{where}: name is missing")
        if entry.get("row") not in ROWS:
            problems.append(f"{where}: row must be one of {ROWS}")
        if entry.get("row") == "DIFFERS" and not (isinstance(entry.get("fields"), list) and entry["fields"]):
            problems.append(f"{where}: a DIFFERS entry names the differing fields")
        if not str(entry.get("reason") or "").strip():
            problems.append(f"{where}: reason is missing")
        if not repository_file(str(entry.get("source") or "")):
            problems.append(f"{where}: source must be a relative path to a regular file beneath this repository (got {entry.get('source')!r})")
    if problems:
        raise DriftError(f"{path}: " + "; ".join(problems))
    return data["acknowledged"]


def apply_acknowledged(rows: list[dict], entries: list[dict], clients: tuple) -> list[dict]:
    """Mark the rows an entry accepts; return the entries that match no current row (for a client that was compared)."""
    used, stale = set(), []
    for row in rows:
        if row["row"] == "SAME":
            continue
        for index, entry in enumerate(entries):
            if (entry["client"], entry["name"], entry["row"]) == (row["client"], row["name"], row["row"]) and (row["row"] != "DIFFERS" or sorted(entry["fields"]) == row["fields"]):
                row["acknowledged"] = {"reason": entry["reason"], "source": entry["source"]}
                used.add(index)
    for index, entry in enumerate(entries):
        if index not in used and entry["client"] in clients:
            stale.append(entry)
    return stale


def report(rows: list[dict], stale: list[dict], notes: list[str]) -> str:
    lines = list(notes)
    for row in rows:
        status = ("ack " if row.get("acknowledged") else "") + row["row"]
        detail = ""
        if row["row"] == "DIFFERS":
            detail = f"  fields: {', '.join(row['fields'])} | template: {row['template']} | live: {row['live']}"
        elif row["row"] == "TEMPLATE-ONLY":
            detail = f"  template: {row['template']}"
        elif row["row"] == "LIVE-ONLY":
            detail = f"  live: {row['live']}"
        if row.get("acknowledged"):
            detail += f"  [{row['acknowledged']['reason']} ({row['acknowledged']['source']})]"
        lines.append(f"{row['client']:6s} {status:20s} {row['name']}{detail}")
    for entry in stale:
        lines.append(f"{entry['client']:6s} {'STALE-ACK':20s} {entry['name']}  acknowledges {entry['row']}{' ' + ','.join(entry.get('fields') or []) if entry.get('fields') else ''}, which no longer occurs ({entry['source']})")
    open_rows = [r for r in rows if r["row"] != "SAME" and not r.get("acknowledged")]
    counts = ", ".join(f"{label} {sum(1 for r in rows if r['row'] == label)}" for label in ("SAME", *ROWS))
    lines.append(f"summary: {counts}; acknowledged {sum(1 for r in rows if r.get('acknowledged'))}; unacknowledged {len(open_rows)}; stale acknowledgements {len(stale)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--home", type=Path, default=Path.home(), help="the account's home (default: the current user's)")
    parser.add_argument("--eco-root", type=Path, help="the ecosystem prefix (default: install_claude_profile.default_eco_root)")
    parser.add_argument("--claude-json", type=Path, help="default: <home>/.claude.json")
    parser.add_argument("--codex-config", type=Path, help="default: <home>/.codex/config.toml")
    parser.add_argument("--acknowledged", type=Path, help="JSON file of accepted differences (schema " + ACK_SCHEMA + ")")
    parser.add_argument("--with-authorization-settings", action="store_true", help="render the authorization settings too (tool approval modes), as new_wsl_client_config.py --render does with the same option")
    parser.add_argument("--json", action="store_true", help="print the rows as JSON")
    args = parser.parse_args(argv)
    home = args.home.resolve()
    eco_root = args.eco_root or icp.default_eco_root(home)
    try:
        claude_template, codex_template = render_templates(home, eco_root, args.with_authorization_settings)
        entries = load_acknowledged(args.acknowledged) if args.acknowledged else []
        sources = {"claude": args.claude_json or home / ".claude.json", "codex": args.codex_config or home / ".codex" / "config.toml"}
        rows, notes, compared = [], [], []
        for client, template, reader in (("claude", claude_template, read_claude), ("codex", codex_template, read_codex)):
            explicit = (args.claude_json if client == "claude" else args.codex_config) is not None
            if not sources[client].is_file() and not explicit:
                notes.append(f"{client}: no {sources[client]}, not compared")
                continue
            live = reader(sources[client])
            notes.append(f"{client}: {len(template)} rendered, {len(live)} registered ({sources[client]})")
            rows += compare(client, template, live)
            compared.append(client)
        stale = apply_acknowledged(rows, entries, tuple(compared))
    except DriftError as error:
        print(f"mcp_template_drift: {error}", file=sys.stderr)
        return 2
    failed = any(r["row"] != "SAME" and not r.get("acknowledged") for r in rows) or bool(stale)
    shown_rows = [{**r, "name": safe_name(r["name"]), "fields": [safe_name(f) for f in r["fields"]]} for r in rows]
    shown_stale = [{**e, "name": safe_name(e["name"]), "fields": [safe_name(f) for f in e.get("fields") or []]} for e in stale]
    if args.json:
        print(json.dumps({"ok": not failed, "notes": notes, "rows": shown_rows, "stale": shown_stale}, indent=1, sort_keys=True))
    else:
        print(report(shown_rows, shown_stale, notes))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
