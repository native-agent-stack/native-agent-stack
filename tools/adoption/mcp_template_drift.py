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

No value of a registration is printed, in either format or on either stream, error messages included. Values are compared in memory and withheld from every description: environment variable and header NAMES are shown,
never their values; a URL is shown as scheme://host (no userinfo, port, path, query or fragment) and withheld whole when it holds an `@`; a command as its file name (no directory); the transport from a fixed set
(stdio, http, sse); arguments by count only, because a token that looks like an option can be the value of the option before it. The host label and the command's file name are printed as names, not as values: they are
the two places where text of a registration still reaches a description. A description is built from those names, counts and fixed words, so a value cannot reach it by taking a shape the report did not foresee; a field
of an unexpected shape (a non-numeric timeout, a list that is a string, a table that is a list) ends the run with exit 2 and a message that names the server, never the value. Paths are printed relative to the home.
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
COMMAND = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]{0,63}\Z")               # the file name of a program
HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?\Z")     # a host name or an IPv4 address
TRANSPORTS = ("stdio", "http", "sse")                                      # the transports of a Claude Code registration: any other type is withheld
LIST_FIELDS = ("args", "env_vars", "enabled_tools", "disabled_tools")
TABLE_FIELDS = ("env", "headers", "http_headers")
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


def shown_path(path: Path, home: Path | None = None) -> str:
    """A path as printed: relative to the account's home when it is below it (the home holds the account's name), else the file name alone."""
    try:
        return "~/" + path.resolve().relative_to((home or Path.home()).resolve()).as_posix()
    except (OSError, ValueError):
        return path.name


def read_claude(path: Path, home: Path | None = None) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DriftError(f"cannot read {shown_path(path, home)}: {type(error).__name__}") from None
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        raise DriftError(f"{shown_path(path, home)} has no `mcpServers` object (the user scope of Claude Code)")
    return servers


def read_codex(path: Path, home: Path | None = None) -> dict:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DriftError(f"cannot read {shown_path(path, home)}: {type(error).__name__}") from None
    servers = data.get("mcp_servers", {})
    if not isinstance(servers, dict):
        raise DriftError(f"{shown_path(path, home)}: `mcp_servers` is not a table")
    return servers


def check_shape(spec) -> None:
    """Raise TypeError (compare turns it into a value-free DriftError) when a registration is not a table, a list field is not a list, a table field is not a table or an argument is not a string."""
    if not isinstance(spec, dict):
        raise TypeError
    for key in LIST_FIELDS:
        if spec.get(key) is not None and not isinstance(spec[key], list):
            raise TypeError
    for key in TABLE_FIELDS:
        if spec.get(key) is not None and not isinstance(spec[key], dict):
            raise TypeError
    if any(not isinstance(argument, str) for argument in spec.get("args") or []):
        raise TypeError


def normalise_claude(spec: dict) -> dict:
    """The fields that decide what Claude Code starts. A registration made as `env NAME=value ... command args` carries its environment in args; it compares equal to the same server with an env object."""
    check_shape(spec)
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
    check_shape(spec)
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


# Mechanisms the description helpers rest on, read in python/cpython@v3.13.16 (the interpreter that runs this tool): urlsplit and SplitResult.hostname (Lib/urllib/parse.py L472, L165: the userinfo is split off
# before the host, and the host is lower-cased); Path.resolve and Path.is_relative_to (Lib/pathlib/_local.py L664, L393: resolve follows symlinks, is_relative_to compares path parts); and why an argument cannot be
# classified by its spelling: Lib/argparse.py (end-of-options handling, L1964 and L2503 at v3.12.3) and Lib/getopt.py return `--x` as the operand of `-k` and as a positional value after `--`.
def safe_name(name) -> str:
    """A name (variable, header, field or server) as printed: itself when it has the shape of one, else the placeholder."""
    return name if isinstance(name, str) and NAME.fullmatch(name) else WITHHELD


def shown_url(url) -> str:
    """scheme://host of a URL; userinfo, port, path, query and fragment are withheld. A URL that holds an `@` anywhere is withheld whole: a credential whose own `/`, `?` or `#` ends the authority early parses as the
    host (CPython Lib/urllib/parse.py urlsplit), so what the parser calls userinfo cannot be trusted to be all of it. So is a URL that does not parse, a port that is not a number and a scheme or host of another shape."""
    text = str(url)
    if "@" in text:
        return WITHHELD
    try:
        parts = urlsplit(text)
        scheme, host = parts.scheme.lower(), parts.hostname or ""
        parts.port   # raises ValueError for a port that is not a number in range
    except ValueError:
        return WITHHELD
    return f"{scheme}://{host}" if scheme in ("http", "https", "ws", "wss") and HOST.fullmatch(host) else WITHHELD


def shown_command(command) -> str:
    """The file name of the program; the directory (which holds the account's home) is not printed."""
    if not command:
        return "(no command)"
    name = os.path.basename(str(command).rstrip("/"))
    return name if COMMAND.fullmatch(name) else WITHHELD


def describe(spec: dict) -> str:
    """One line for a normalised spec, built from names, counts and fixed words: its type, how it starts (scheme://host, or the command's file name), how many arguments it has (never which: a token that looks
    like an option can be the value of the option before it) and the NAMES of its env and headers."""
    names = sorted(safe_name(name) for name in spec.get("env") or {}) + sorted(f"header:{safe_name(name)}" for name in spec.get("headers") or {})
    start = shown_url(spec["url"]) if spec.get("url") else shown_command(spec.get("command"))
    count = len(spec.get("args") or [])
    shown_args = f"{count} arg{'' if count == 1 else 's'}" if count else ""
    kind = spec.get("type") or ("http" if spec.get("url") else "stdio")
    return " ".join(part for part in (kind if kind in TRANSPORTS else WITHHELD, start, shown_args, f"env/headers: {','.join(names)}" if names else "") if part)


def compare(client: str, template: dict, live: dict) -> list[dict]:
    def normalise(name: str, spec) -> dict:
        try:
            return (normalise_claude if client == "claude" else normalise_codex)(spec)
        except (TypeError, ValueError, AttributeError, OverflowError):
            # The message of float() quotes the value it could not convert (CPython Objects/floatobject.c, float_from_string_inner, "%R" of the input: v3.12.3 L190-193, v3.13.16 L183-186): it is dropped, not chained.
            raise DriftError(f"{client}: the registration of server {safe_name(name)} has a field of an unexpected shape") from None
    rows = []
    for name in sorted(template.keys() | live.keys()):
        if name not in live:
            rows.append({"client": client, "name": name, "row": "TEMPLATE-ONLY", "fields": [], "template": describe(normalise(name, template[name])), "live": None})
        elif name not in template:
            rows.append({"client": client, "name": name, "row": "LIVE-ONLY", "fields": [], "template": None, "live": describe(normalise(name, live[name]))})
        else:
            a, b = normalise(name, template[name]), normalise(name, live[name])
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


def load_acknowledged(path: Path, home: Path | None = None) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DriftError(f"cannot read {shown_path(path, home)}: {type(error).__name__}") from None
    if not isinstance(data, dict) or data.get("schema") != ACK_SCHEMA or not isinstance(data.get("acknowledged"), list):
        raise DriftError(f"{shown_path(path, home)}: expected schema {ACK_SCHEMA} and an `acknowledged` list")
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
        raise DriftError(f"{shown_path(path, home)}: " + "; ".join(problems))
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
        entries = load_acknowledged(args.acknowledged, home) if args.acknowledged else []
        sources = {"claude": args.claude_json or home / ".claude.json", "codex": args.codex_config or home / ".codex" / "config.toml"}
        rows, notes, compared = [], [], []
        for client, template, reader in (("claude", claude_template, read_claude), ("codex", codex_template, read_codex)):
            explicit = (args.claude_json if client == "claude" else args.codex_config) is not None
            if not sources[client].is_file() and not explicit:
                notes.append(f"{client}: no {shown_path(sources[client], home)}, not compared")
                continue
            live = reader(sources[client], home)
            notes.append(f"{client}: {len(template)} rendered, {len(live)} registered ({shown_path(sources[client], home)})")
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
