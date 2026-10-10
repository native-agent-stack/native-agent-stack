#!/usr/bin/env python3
"""Run the Codex lane of the layer-verdict convergence.

For each packet under ``<work-dir>/packets/`` (written by ``lane_packets.py``)
without a valid ``<work-dir>/codex/<catalog>__<layer_id>.json`` already on
disk, fill the shared lane prompt (``lane-prompt.md``) with that packet's
absolute path, the repository root and ``LANE=codex``, then run

    codex exec --sandbox read-only --skip-git-repo-check --ephemeral \
        -C <repo> --output-schema <schema> -o <out.tmp> --json \
        -c model_reasoning_effort=<effort> \
        --ignore-user-config -c features.hooks=false -c features.plugin_hooks=false \
        -c 'web_search="disabled"' -c 'cli_auth_credentials_store="file"' <prompt>

capturing the JSON event stream to
``<work-dir>/codex/events/<catalog>__<layer_id>.jsonl`` and a usage row per
attempt to ``<work-dir>/codex/usage.jsonl``. The event stream shape is not
assumed beyond "a sequence of JSON objects, one per line" -- extraction of a
model name or usage/token fields tolerates unknown shapes and never fails a
layer merely because neither was found in a given run.

``out.tmp`` (the agent's last message, written by ``-o``) is parsed as one
JSON object: ``lane`` is always forced to ``"codex"``; ``packet_sha256`` is
filled from the packet file's own sha256 when the model did not set it;
``model`` is runner-owned and never taken from the model's response text
(2026-09-23 peer audit): ``model.name`` is the runner's own observation -- the
``--model`` it passed to ``codex exec -m``, else the model name the event stream
carried, else ``"unknown"`` (which then fails record_verdicts.py's family
pattern) -- ``model.effort`` is ``--effort``, and ``model.family`` is
``"openai"`` (``codex exec`` is OpenAI's CLI; a non-OpenAI model name then fails
record_verdicts.py's family pattern). ``provenance`` is also runner-owned:
``{codex_lane_py_sha256, prompt_sha256}`` -- the sha256 of this script file and
of the prompt template it filled. The strict schema copy passed to ``codex
exec`` omits ``provenance``, ``model.family`` and the Claude lane's
``refutation``, since Codex strict output requires every listed property;
whatever ``model`` the response carries is replaced. A failing attempt
(non-zero exit, timeout, missing or unparseable ``out.tmp``) is retried
exactly once before the layer is recorded as failed (with its last reason in
``<work-dir>/codex/failures.json``, which record_verdicts.py turns into a
``failed`` run-manifest outcome) and left for the next run (resumable). Nothing here validates the full lane-return JSON Schema --
that is ``record_verdicts.py``'s job; this runner only fills the three
fields the contract assigns to it.

``--dry-run`` prints the exact command it would run for every pending layer,
one per line, and writes nothing -- no directories, no events, no usage rows,
no output files. The Python runner uses the standard library; its host-side command audit uses the existing
verified Node/tree-sitter Bash parser. It is not a landscape-schema validator and does not import scripts/landscape.py.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import errno
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
DEFAULT_PROMPT = HERE / "lane-prompt.md"
DEFAULT_SCHEMA = HERE / "lane-return.schema.json"
# Codex structured output runs in strict mode, which rejects some JSON Schema keywords
# (observed 2026-09-22 with codex-cli 0.155.1: "In context=('properties', 'winner_keys'),
# 'uniqueItems' is not permitted", HTTP 400 invalid_json_schema). The strict copy drops
# them; record_verdicts.py still enforces every dropped rule when it validates a return.
STRICT_UNSUPPORTED_KEYWORDS = frozenset({"uniqueItems", "$schema", "$id", "title", "description"})
# Keywords whose value maps property names to subschemas or to name arrays: the names are
# data (a property may be called "title"), so only the subschemas are filtered and name
# arrays pass through unchanged.
SCHEMA_MAP_KEYWORDS = frozenset({"properties", "patternProperties", "$defs", "definitions", "dependentSchemas",
                                 "dependentRequired", "dependencies"})
# Keywords whose value is instance data, never a schema, so it is kept verbatim.
DATA_KEYWORDS = frozenset({"const", "enum", "default", "examples"})


def _top_level_lane_schema(schema) -> bool:
    properties = schema.get("properties") if isinstance(schema, dict) else None
    return isinstance(properties, dict) and "provenance" in properties and "lane" in properties


def strict_output_schema(schema):
    """Return a copy of ``schema`` without keywords Codex strict output rejects."""
    if isinstance(schema, list):
        return [strict_output_schema(value) for value in schema]
    if not isinstance(schema, dict):
        return schema
    if _top_level_lane_schema(schema):
        schema = without_runner_owned(json.loads(json.dumps(schema)))
    strict = {}
    for key, value in schema.items():
        if key in STRICT_UNSUPPORTED_KEYWORDS:
            continue
        if key in DATA_KEYWORDS:
            strict[key] = value
        elif key in SCHEMA_MAP_KEYWORDS and isinstance(value, dict):
            strict[key] = {name: strict_output_schema(subschema) for name, subschema in value.items()}
        else:
            strict[key] = strict_output_schema(value)
    return strict


# Written by a runner, never asked of the model: (object path, property). refutation is the Claude
# lane's refutation summary (written by claude_lane.py), never a Codex field.
RUNNER_OWNED_PROPERTIES = ((), "provenance"), (("model",), "family"), ((), "refutation")
# The layers this run tried and could not produce a return for, with the reason, for
# record_verdicts.py's run manifest (outcome "failed" instead of a bare "missing").
FAILURES_NAME = "failures.json"


def without_runner_owned(schema):
    """Drop the runner-owned properties (and their ``required`` entries) from a lane schema copy."""
    for path, name in RUNNER_OWNED_PROPERTIES:
        node = schema
        for step in path:
            node = (node.get("properties") or {}).get(step) if isinstance(node, dict) else None
        if isinstance(node, dict):
            (node.get("properties") or {}).pop(name, None)
            if isinstance(node.get("required"), list):
                node["required"] = [item for item in node["required"] if item != name]
    return schema


def write_strict_schema(schema_path: Path, codex_dir: Path) -> Path:
    codex_dir.mkdir(parents=True, exist_ok=True)
    strict_path = codex_dir / "lane-return.codex-strict.schema.json"
    strict = strict_output_schema(json.loads(schema_path.read_text(encoding="utf-8")))
    strict_path.write_text(json.dumps(strict, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return strict_path
DEFAULT_TIMEOUT = 900.0
DEFAULT_EFFORT = "max"
LANE = "codex"
OMNIROUTE_BASE_URL_ENV = "OMNIROUTE_BASE_URL"
DEFAULT_OMNIROUTE_BASE_URL = "http://127.0.0.1:21128/v1"
# OmniRoute@0585aba5589d5a1f49243a13a8db249558e7c9e3
# open-sse/config/providers/registry/codex/index.ts:9-17,71-74 (cx Responses route).
DEFAULT_OMNIROUTE_MODEL = "gpt-6.1-sol"
# CC 2026-10-10T07:51Z disclosure ruling; verified against the pinned primary sources.
OMNIROUTE_PASS_THROUGH = (
    "not_attested (deployed settings unreadable by policy; OmniRoute@c1e30b76 chatCore.ts:3156, "
    "systemPrompt.ts:210-217/278-283, strategySelector.ts:234-249)")


def omniroute_endpoint(value: str) -> str:
    """A keyless loopback /v1 endpoint; never echo a rejected URL, which may contain a credential."""
    if not isinstance(value, str):
        raise ValueError("OmniRoute requires a keyless loopback http(s) /v1 endpoint with a valid port")
    try:
        parsed = urlsplit(value)
        port = parsed.port
        valid = (isinstance(value, str) and not any(character.isspace() for character in value)
                 and parsed.scheme in ("http", "https") and parsed.hostname in ("127.0.0.1", "localhost", "::1")
                 and parsed.username is None and parsed.password is None and "?" not in value and "#" not in value
                 and parsed.path in ("/v1", "/v1/") and (port is None or 1 <= port <= 65535))
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("OmniRoute requires a keyless loopback http(s) /v1 endpoint with a valid port")
    host = "[::1]" if parsed.hostname == "::1" else parsed.hostname
    authority = f"{host}:{port}" if port is not None else host
    return f"{parsed.scheme}://{authority}/v1"


def omniroute_config(endpoint: str) -> list:
    """Transport-only CLI overrides, following landscape-sweep/codex_job.py:695-703 at main 4d345267.

    Keep ISOLATION_ARGS and the blind environment rather than the sweep's profile/API-key setup.
    The memory header is an upstream opt-out; compression off is a request, not a guarantee against
    the pinned gateway's adaptive planning. Global prompt/payload/plugin configuration remains
    an independently reviewed boundary (docs/decisions/2026-10-10-codex-lane-omniroute.md).
    """
    endpoint = omniroute_endpoint(endpoint)
    return ["-c", 'model_provider="omniroute"',
            "-c", 'model_providers.omniroute.name="OmniRoute loopback"',
            "-c", "model_providers.omniroute.base_url=" + json.dumps(endpoint),
            "-c", 'model_providers.omniroute.wire_api="responses"',
            "-c", "model_providers.omniroute.requires_openai_auth=false",
            "-c", 'model_providers.omniroute.http_headers={"x-omniroute-no-memory"="true",'
                  '"x-omniroute-compression"="off"}',
            "-c", "features.shell_snapshot=false"]

# Recognized directly on an event dict or anywhere nested under it (e.g. a
# ``turn.completed`` event's ``usage`` object). Extra keys on the event are
# ignored; missing keys are simply omitted from the extracted usage dict --
# this list is a superset covering both codex's ``usage`` shape
# (input_tokens/cached_input_tokens/cache_write_input_tokens/output_tokens/
# reasoning_output_tokens) and a couple of plausible synonyms, so an
# unrecognized future shape degrades to "no usage found" instead of raising.
USAGE_KEYS = (
    "input_tokens", "output_tokens", "cached_input_tokens", "cache_write_input_tokens",
    "reasoning_output_tokens", "reasoning_tokens", "cached_tokens", "total_tokens",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def discover_packets(work_dir: Path, layers: "set[str] | None") -> list:
    """Sorted ``(catalog, layer_id, packet_path)`` for every
    ``packets/<catalog>__<layer_id>.json`` file, optionally filtered to the
    given set of layer ids (the part after ``__``, matched across every
    catalog). ``packets/SHA256SUMS`` itself is never a packet."""
    packets_dir = work_dir / "packets"
    found = []
    if not packets_dir.is_dir():
        return found
    for path in sorted(packets_dir.glob("*.json")):
        stem = path.stem
        if "__" not in stem:
            continue
        catalog, layer_id = stem.split("__", 1)
        if layers is not None and layer_id not in layers:
            continue
        found.append((catalog, layer_id, path))
    return found


def existing_output_is_valid(out_path: Path, catalog: str, layer_id: str, packet_sha256: str,
                             provenance: dict = None, configured_model: str = None,
                             configured_effort: str = None, audit_roots=None) -> bool:
    """Resumable-skip check: the file must parse as a JSON object already
    forced onto this lane and this exact packet. A present-but-different
    ``packet_sha256`` (the packet changed since the file was written) is
    treated as invalid so the layer reruns; a missing ``packet_sha256`` on an
    otherwise-matching old file is not itself disqualifying -- a rerun would
    only fill it in, so there is nothing to gain by discarding the file.

    ``provenance`` is the current ``lane_provenance(prompt_path)``: when given, the file's own
    ``provenance`` must equal it field for field. A return written by older lane code or from an older
    prompt (or one without provenance) is stale: record_verdicts.py rejects it, so skipping it would
    leave the layer rejected on every later run (PR #141 review). It reruns instead.

    A return whose ``model.name`` is ``"unknown"`` (no model was configured or observed; record_verdicts.py
    rejects it by family pattern), or differs from a given ``configured_model`` (the ``--model`` of this
    run), also reruns (round-2 review).

    ``audit_roots`` (a blind run's export and packets) re-audits the layer's retained events: a return whose events
    are missing or flagged reruns, so a return an interrupted run wrote before its audit is never resumed as clean
    (independent review of #145, round 7, REG7-1/ISO-R7-1)."""
    if not out_path.exists():
        return False
    if audit_roots is not None:
        events_path = out_path.parent / "events" / f"{out_path.stem}.jsonl"
        # A child always emits events: an empty stream is a truncated one (round 8, NEW-1), never a clean audit.
        if not events_path.is_file() or not parse_events(events_path.read_text(encoding="utf-8", errors="replace")) \
                or audit_is_flagged(blind_audit(events_path, audit_roots)):
            return False
    try:
        data = load_json(out_path)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    if data.get("lane") != LANE:
        return False
    if data.get("catalog") != catalog or data.get("layer_id") != layer_id:
        return False
    existing_hash = data.get("packet_sha256")
    if existing_hash and existing_hash != packet_sha256:
        return False
    if provenance is not None:
        # Field for field and nothing more: landscape.py rejects a provenance object with extra keys, so a
        # return carrying one is rerun, not skipped (Codex review of #145).
        if data.get("provenance") != provenance:
            return False
    model = data.get("model") if isinstance(data.get("model"), dict) else {}
    if model.get("name") in (None, "", "unknown"):
        return False
    if configured_model and model.get("name") != configured_model:
        return False
    # A changed --effort reruns the layer too (Codex review of #145): the requested reasoning setting must
    # not be silently ignored by resuming a return made at another effort.
    if configured_effort and model.get("effort") != configured_effort:
        return False
    return True


def fill_prompt(template: str, packet_path: Path, repo_root: Path) -> str:
    return (
        template.replace("{PACKET_PATH}", str(packet_path))
        .replace("{REPO_ROOT}", str(repo_root))
        .replace("{LANE}", LANE)
    )


def build_command(repo_root: Path, schema_path: Path, out_tmp: Path, effort: str, prompt_text: str,
                  model: str = None, isolation=(), *, provider="native", omniroute_base_url=None) -> list:
    provider_args = omniroute_config(omniroute_base_url) if provider == "omniroute" else []
    if provider == "omniroute":
        model = model or DEFAULT_OMNIROUTE_MODEL
        model = model if model.startswith("cx/") else "cx/" + model
    return [
        "codex", "exec",
        *(["-m", model] if model else []),
        "--sandbox", "read-only",
        "--skip-git-repo-check",
        "--ephemeral",
        "-C", str(repo_root),
        "--output-schema", str(schema_path),
        "-o", str(out_tmp),
        "--json",
        "-c", f"model_reasoning_effort={effort}",
        *isolation,
        *provider_args,
        prompt_text,
    ]


# Channels a lane child is denied by configuration (2026-09-23 re-record); memory stores, code indexes and
# the web can return the incumbent verdicts or the catalog's selection labels.
# - ``--ignore-user-config`` skips ``$CODEX_HOME/config.toml`` (auth still uses ``CODEX_HOME``), so the user's
#   MCP servers, plugins, profiles and project trust do not load, and without trust no project
#   ``.codex/config.toml`` loads either. Measured with codex-cli 0.155.1 from the agent-lab checkout
#   (RUST_LOG=info): a default ``codex exec`` initialized seven MCP servers (ai-memory, SocratiCode,
#   jCodeMunch, Serena, context-mode, plugin-runtime, OpenAI Developers MCP); with these flags only
#   plugin-runtime and OpenAI Developers MCP initialized.
# - Lifecycle hooks are off (``features.hooks``, ``features.plugin_hooks``).
# - Native web search is off (``web_search="disabled"``): without it a probe child ran a web search, with
#   it the child reported no web search tool.
# - A blind child runs with a run-scoped CODEX_HOME and an empty HOME (isolated_codex_home): the flags do not skip
#   ``$CODEX_HOME/AGENTS.md`` or user skills under ``~/.agents/skills``, which probe children loaded otherwise.
# Not denied: shell reads under ``--sandbox read-only`` (any host path, and CLIs such as ai-memory on PATH).
# Those rest on lane-prompt.md rule 1, a repository without ``.git`` (refused unless --allow-git-history) and the
# post-run blind audit below. A non-blind --allow-git-history run inherits the native Codex home.
# Per-server ``mcp_servers.<name>.enabled=false`` overrides are not used: codex rejects them as a partial
# table ("invalid transport") when the loaded config does not define that server.
# The file credential store is pinned (round 5, ISO-R5-4): a keyring or auto store from a system or managed layer
# would save a blind child's rotated tokens apart from the native auth.json.
# No shell_environment_policy override (round 6, ISO-R6-4): measured 2026-09-24 with codex-cli 0.155.1, the model's
# shell in `codex exec` got the same variables under inherit="core", inherit="none", include_only=["PATH"] and no
# override (a planted non-core SSL_CERT_DIR reached it every time), so it protects nothing here. Instead a blind child
# never receives an API key: child_env forwards none, and codex_home_issue requires the native auth.json.
# Overturn: a codex exec probe in which such an override removes a non-core variable from the model's shell.
ISOLATION_ARGS = ("--ignore-user-config", "-c", "features.hooks=false", "-c", "features.plugin_hooks=false",
                  "-c", 'web_search="disabled"', "-c", 'cli_auth_credentials_store="file"')

AUDIT_NAME = "blind-audit.json"
# Bind the existing verified Bash parser and its thin adapter into this runner's digest.
# Codex@092d3acd exec_events.rs:159-166 records a command display, not syscall paths.
AUDIT_ADAPTER = HERE / "blind-command-analysis.mjs"
AUDIT_DEPENDENCIES = {
    AUDIT_ADAPTER: "bcb1b9d483901259aee4cdafa3d779a2c2ee2feec71cb997257035b4549939dd",
    HERE.parents[1] / "examples/claude-native/workflows/child-usage.mjs":
        "3e5189342734135e88a2295c1c2152275d9e26c0c7731ed5cbc8905bbccd98a4",
    HERE.parents[1] / "examples/claude-native/workflows/shell-parser.pin.json":
        "961f4555c9067f17ae5fc2666d20ee797fbd2cd7abcbff80aa4963e912bf64d0",
}
# CLIs that reach memory stores, code indexes or session history, and the agent CLIs (a nested ``codex exec`` would
# find the linked credential and run without the isolation flags). A blind child's PATH resolves none of them
# (BLIND_CHILD_PATH; blind_path_issue refuses a host where one would), so its audit no longer looks for their names:
# they are also candidates a lane must search for, and on the 2026-09-24 re-record `rg -i 'qmd|...'` and Python lists
# of candidate ids voided 11 of 32 layers with no read outside the export. A non-blind run keeps looking for them.
BLIND_UNRESOLVABLE = ("ai-memory", "agentsview", "mcporter", "qmd", "socraticode", "jcodemunch", "serena", "codex",
                      "claude")
# System tools a blind child's PATH keeps (git history, a database, the network): executing one is flagged.
AUDIT_TOOLS = ("git", "sqlite3", "curl", "wget")
# A blind child's PATH: the system executable directories only. The caller's PATH carried the retrieval CLIs
# (~/.local/share/codex-ecosystem/bin on this WSL host); codex itself is launched by the absolute path the caller's
# PATH resolves (run_attempt).
BLIND_CHILD_PATH = os.pathsep.join(("/usr/bin", "/bin", "/usr/sbin", "/sbin"))
# A URL scheme right before ``//``: its authority is no filesystem path unless the scheme is ``file`` (``jar:file://``
# too). Any other scheme needs the network, which the read-only sandbox refuses a blind child (measured 2026-09-24), or
# a CLI a blind child cannot resolve, so ``qmd://``, ``s3://`` and ``https://`` search terms stay clean (independent
# review of #206, R2-1).
URL_SCHEME_BEFORE = re.compile(r"(?i)(?<![A-Za-z0-9+.-])([A-Za-z][A-Za-z0-9+.-]*):\Z")
# Not after ``)`` or ``]``: Python's path join (``Path.cwd()/ref``, ``parts[0]/name``) names no absolute path
# (2026-09-24 re-record).
ABSOLUTE_PATH = re.compile(r"(?<![\w.~})\]-])(/[^\s'\"|;&<>()`]+)")
HOME_PATH = re.compile(r"(?:~|\$HOME|\$\{HOME\})(?:/[^\s'\"|;&<>()`]*)?")
# Any other environment variable used as a path (``$CODEX_HOME/AGENTS.md``, ``${XDG_DATA_HOME}/x``) can point
# outside the repository; only its value, which the event does not show, says where (round-2 review).
VARIABLE_PATH = re.compile(r"\$(?:\{(?!HOME\})[A-Za-z_]\w*\}|(?!HOME\b)[A-Za-z_]\w*)/[^\s'\"|;&<>()`]*")
# Only an expansion that transforms its value (${X%/*}, ${X:-/p}, ${X/a/b}, ${!X}) hides the path it builds; a plain
# ${name} is caught by VARIABLE_PATH when a path follows it, and by INHERITED_DIRECTORY when it is itself the
# directory argument (``rg -l x ${TMPDIR}``, ``cp -r $SSL_CERT_DIR .``; round 6, REG6-3). A child's TMPDIR is a fresh,
# empty directory of its run home, so it names no lane data either way.
INHERITED_DIRECTORY = re.compile(r"\$\{?(?:TMPDIR|SSL_CERT_DIR|SSL_CERT_FILE|OLDPWD)\b\}?")
CODEX_HOME_REFERENCE = re.compile(r"\$\{?CODEX_HOME\b[^\s'\"]*")
# A command that reads the environment, where the Codex home's path is (``printenv CODEX_HOME | xargs dirname``;
# round 7, ISO-R7-9). The bare word in a search (``rg -n CODEX_HOME docs``) is not one (round 8, REG8-3).
ENVIRONMENT_READ = re.compile(r"(?:^|[\s;&|(`'\"])(printenv|env|export\s+-p|declare\s+-p)(?=$|[\s;&|)`'\"])")
COMMAND_SUBSTITUTION = re.compile(r"\$\(|`")
# Match only expansion spans supplied by the Bash grammar. Quoted literal data and quoted heredoc bodies
# are not shell expansion; nested shell code is parsed separately.
PARAMETER_EXPANSION = re.compile(r"\$\{(?:![^}]*|[^}]*[%#:/^,@*?\[][^}]*)\}")
# A ``cd`` that leaves the working directory for somewhere the command does not name: bare ``cd`` (home),
# ``cd -``, ``cd ~`` and ``cd $OLDPWD`` / ``cd "${OLDPWD}"`` (the previous directory), or any other bare variable.
CD_TARGET = re.compile(r"(?:^|[;&|\n(]|\b(?:ba|z|da)?sh\s+-l?c\s+['\"])\s*cd(?=$|[\s;&|)'\"])([^;&|\n)]*)")
UNNAMED_CD_TARGETS = re.compile(r"-|~|\$[A-Za-z_]\w*|\$\{[A-Za-z_]\w*\}|")
PARENT_PATH = re.compile(r"(?:^|[\s'\"=:])((?:[^\s'\"|;&<>()`]*/)?\.\.(?:/[^\s'\"|;&<>()`]*)?)")
ROOT_PATH = re.compile(r"(?:^|[\s'\"=])/(?=$|[\s'\";&|)])")
# Only the executable token of a command segment is exempt, and only when it is a system executable: the
# first word at the start, after ``;``, ``&&``, ``||``, ``|`` or a newline, or right after ``bash -lc '``
# (``sh -c "`` and the like). Every other absolute path outside the roots is flagged, a ``/usr/...`` or
# ``/bin/...`` data path included -- ``/bin/cat /usr/local/share/prior-verdict.json`` reads data (PR #141
# review). ``/dev/null`` stays exempt wherever it appears.
EXECUTABLE_TOKEN = re.compile(r"(?:^|;|&&|\|\||\||\n|\b(?:ba|z|da)?sh\s+-l?c\s+['\"])\s*(?=/)")
# ``/usr/`` only for its executable directories: ``bash -lc '/usr/local/share/verdicts/show'`` runs a script
# kept with data and is flagged (round-2 review).
SYSTEM_EXECUTABLE_PREFIXES = ("/bin/", "/sbin/", "/usr/bin/", "/usr/sbin/", "/usr/local/bin/")
EXEMPT_PATHS = ("/dev/null",)


def audit_is_flagged(report: dict) -> bool:
    """Whether a blind_audit report flags anything: web search, an MCP tool call or a flagged command."""
    return bool(report.get("web_search") or report.get("mcp_tool_calls") or report.get("flagged_commands"))


def executable_token_starts(command: str) -> set:
    """Offsets where a command segment's executable token begins, when that token is an absolute path."""
    return {match.end() for match in EXECUTABLE_TOKEN.finditer(command)}


def network_authority(command: str, match) -> bool:
    """Whether an ABSOLUTE_PATH match is a URL's authority (``https://host/x``, a bare ``'https://'``, ``qmd://x``),
    which is no filesystem path (2026-09-24 re-record); ``file://`` and ``https:///`` are not one (Codex review of
    #206, P2; independent review of #206, C1)."""
    path = match.group(1)
    scheme = URL_SCHEME_BEFORE.search(command[max(0, match.start(1) - 32):match.start(1)])
    return path.startswith("//") and not path.startswith("///") and bool(scheme) and not local_scheme(scheme.group(1))


def local_scheme(scheme: str) -> bool:
    """A scheme whose authority names a local path: ``file``, fsspec's ``local`` and any ``unix`` one
    (``http+unix://%2Frun%2F...``) (independent review of #206 at 891ab70f)."""
    scheme = scheme.lower()
    return scheme in ("file", "local") or "unix" in scheme


def outside_paths(command: str, allowed_roots) -> list:
    """Absolute paths in ``command`` outside ``allowed_roots``, except /dev/null and a segment's system
    executable token."""
    executables = executable_token_starts(command)
    found = []
    for match in ABSOLUTE_PATH.finditer(command):
        path = match.group(1)
        if path in EXEMPT_PATHS:
            continue
        if network_authority(command, match):
            continue
        if match.start(1) in executables and path.startswith(SYSTEM_EXECUTABLE_PREFIXES):
            continue
        if any(path == root or path.startswith(root.rstrip("/") + "/") for root in allowed_roots):
            continue
        found.append(path)
    return found


def names_root(command: str) -> bool:
    """Whether ``command`` names the filesystem root ``/``: ROOT_PATH, except a quoted ``'/'`` joined with ``+`` between
    two non-literal operands (``p+'/'+k``, ``path + '/' + str(i)`` walking a JSON document), which names no directory;
    ``os.walk('/')``, ``'/'+'etc/passwd'``, ``''+'/'+'etc'`` and ``ls /`` still do (2026-09-24 re-record: 8 voided
    layers)."""
    for match in ROOT_PATH.finditer(command):
        slash = match.end() - 1
        quote = command[slash - 1:slash]
        # Joined between two non-literal operands only: '/'+'etc/passwd' and ''+'/'+'etc/passwd' build /etc/passwd
        # (independent review of #206, C2 and round 1 (a)).
        if quote in ("'", '"') and command[slash + 1:slash + 2] == quote and (
                re.search(r"[\w)\]]\s*\+\s*\Z", command[:slash - 1])
                and re.match(r"\s*\+\s*[A-Za-z_(]", command[slash + 2:])):
            continue
        return True
    return False


def unnamed_cd_targets(command: str) -> list:
    """The raw argument of every ``cd`` in ``command`` that goes home or back rather than to a named path."""
    found = []
    for match in CD_TARGET.finditer(command):
        target = match.group(1).strip().strip("'\"").strip()
        if UNNAMED_CD_TARGETS.fullmatch(target):
            found.append(target or "(home)")
    return found


class AuditAnalysisUnavailable(ValueError):
    """An audit dependency cannot establish command structure; never a clean audit."""


def command_analyses(commands: list[str]) -> list[dict]:
    """Parse recorded command displays with the repository's pinned Bash grammar; execute no payload."""
    for path, expected in AUDIT_DEPENDENCIES.items():
        if not path.is_file() or sha256_file(path) != expected:
            raise AuditAnalysisUnavailable(f"blind audit dependency missing or digest mismatch: {path.name}")
    node = shutil.which("node")
    if node is None:
        raise AuditAnalysisUnavailable("blind audit needs Node and the pinned shell parser")
    try:
        result = subprocess.run([node, str(AUDIT_ADAPTER)], input=json.dumps(commands),
                                capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise AuditAnalysisUnavailable("blind audit command parser unavailable") from error
    if result.returncode or not isinstance(data, list) or len(data) != len(commands) or \
            any(not isinstance(item, dict) for item in data):
        raise AuditAnalysisUnavailable("blind audit pinned shell parser unavailable or invalid")
    return data


def audit_analysis_issue() -> str | None:
    """Setup refusal before a pending real run spends a model turn; previews still write nothing."""
    try:
        command_analyses([])
    except AuditAnalysisUnavailable as error:
        return str(error)
    return None


def operand_reasons(value: str, allowed_roots) -> list[str]:
    """Apply the existing boundary policy to a read operand, rather than unrelated command data."""
    text = "operand " + repr(value)
    reasons = [f"path outside the repository and packets: {p}" for p in outside_paths(text, allowed_roots)]
    if names_root(text):
        reasons.append("names the filesystem root /")
    reasons += [f"home-relative path: {p}" for p in HOME_PATH.findall(text)]
    reasons += [f"variable path: {p}" for p in VARIABLE_PATH.findall(text)]
    reasons += [f"path climbs out of the working directory: {p}" for p in PARENT_PATH.findall(text)]
    return reasons


def search_operands(program: str, words: list[str]) -> tuple[list[str], list[str]]:
    """Separate search/filter data from files, including pattern files and jq variable files.

    An unrecognized option is refused instead of guessing which later word is data. In particular -f never
    consumes a file silently as the positional pattern. Shell expansions are handled before this function.
    """
    files, reasons = [], []
    pattern_given = "--files" in words
    positional, index = False, 0
    file_options = {"-f", "--file", "--from-file", "--ignore-file", "--exclude-from"}
    pattern_options = {"-e", "--regexp"} if program != "jq" else set()
    data_options = {"-g", "--glob", "--iglob", "--include", "--exclude", "--exclude-dir", "-t", "--type",
                    "-T", "--type-not", "--type-add", "--type-clear", "--encoding", "-E", "--engine",
                    "--color", "--colors", "--sort", "--sortr", "--path-separator", "--field-context-separator",
                    "--field-match-separator", "-r", "--replace", "-A", "--after-context", "-B",
                    "--before-context", "-C", "--context", "-m", "--max-count", "-M", "--max-columns",
                    "-j", "--threads", "--maxdepth", "--max-filesize", "--dfa-size-limit", "--regex-size-limit",
                    "--context-separator", "--label", "--binary-files", "--directories", "--devices",
                    "--tab", "--indent"}
    if program != "rg":
        # The same short spelling can mean a flag in grep/jq and take a value in rg.
        data_options -= {"-E", "-r", "-j", "-M", "-t", "-T", "-g"}
    if program == "jq":
        data_options = {"--indent"}
        file_options.add("-L")
    flags = {"--files", "--hidden", "--no-ignore", "--no-ignore-vcs", "--no-ignore-parent", "--no-ignore-global",
             "--no-ignore-dot", "--no-messages", "--no-heading", "--heading", "--line-number", "--no-line-number",
             "--column", "--with-filename", "--no-filename", "--files-with-matches", "--files-without-match",
             "--fixed-strings", "--ignore-case", "--smart-case", "--invert-match", "--word-regexp", "--line-regexp",
             "--only-matching", "--count", "--count-matches", "--quiet", "--null", "--null-data", "--text",
             "--multiline", "--multiline-dotall", "--pcre2", "--pcre2-unicode", "--crlf", "--json", "--stats",
             "--follow", "--no-follow", "--help", "--version", "--extended-regexp", "--basic-regexp",
             "--recursive", "--dereference-recursive", "--raw-input", "--raw-output", "--join-output", "--compact-output",
             "--slurp", "--null-input", "--sort-keys", "--monochrome-output", "--color-output", "--exit-status"}
    short_flags = "inlLHhvwxcqoszZaPUuNFSErR" if program != "jq" else "rRscnjSMCe"
    while index < len(words):
        word = words[index]
        index += 1
        if word == "--" and not positional:
            positional = True
            continue
        if not positional and word.startswith("-") and word != "-":
            option, separator, attached = word.partition("=")
            if word.startswith(("-f", "-e")) and not word.startswith("--") and len(word) > 2:
                option, separator, attached = word[:2], "=", word[2:]
            if option in file_options | pattern_options | data_options:
                if not separator:
                    if index == len(words):
                        reasons.append("unresolved search/filter option operand: " + option)
                        continue
                    attached = words[index]
                    index += 1
                if option in file_options:
                    files.append(attached)
                if option in file_options & {"-f", "--file", "--from-file"} or option in pattern_options:
                    pattern_given = True
                continue
            if program == "jq" and option in {"--arg", "--argjson", "--rawfile", "--slurpfile"}:
                if separator or index + 1 >= len(words):
                    reasons.append("unresolved jq variable option: " + option)
                    continue
                if option in {"--rawfile", "--slurpfile"}:
                    files.append(words[index + 1])
                index += 2
                continue
            if word in flags or re.fullmatch(r"-[" + short_flags + r"]+", word) or \
                    re.fullmatch(r"-(?:[ABCmjM]|[0-9])[0-9]+", word):
                continue
            reasons.append("unresolved search/filter option: " + word)
            files.append(word)
            continue
        if pattern_given:
            files.append(word)
        else:
            pattern_given = True
    return files, reasons


def argv_reasons(argv: list[str], allowed_roots, tools, *, forwarding=False) -> list[str]:
    """Executable position is distinct from pattern/filter arguments; inspect file operands separately."""
    if not argv or any(not isinstance(word, str) for word in argv):
        return ["unresolved executable or argument"]
    program = os.path.basename(argv[0])
    reasons = [f"runs {program}"] if program in tools else []
    if argv[0].startswith("/"):
        if not argv[0].startswith(SYSTEM_EXECUTABLE_PREFIXES):
            reasons += operand_reasons(argv[0], allowed_roots)
        if program in AUDIT_TOOLS + BLIND_UNRESOLVABLE and program not in tools:
            reasons.append(f"runs {program} by path: {argv[0]}")
    if program == "printenv" or program == "env" and not forwarding or \
            program in ("export", "declare") and "-p" in argv[1:]:
        reasons.append(f"reads the environment: {program}")
    if program == "cd" and (len(argv) == 1 or UNNAMED_CD_TARGETS.fullmatch(argv[1])):
        reasons.append(f"cd leaves for an unnamed directory: cd {argv[1] if len(argv) > 1 else '(home)'}")
    operands = argv[1:]
    if program in ("echo", "printf", "true", "false"):
        operands = []
    elif program in ("rg", "grep", "egrep", "fgrep", "jq"):
        operands, option_reasons = search_operands(program, operands)
        reasons += option_reasons
    for word in operands:
        reasons += operand_reasons(word, allowed_roots)
    return reasons


def _packet_document_valid(document, pathname):
    """Accept only bounded inert JSON and the packet fields used by the static projection."""
    import math

    pending = [(document, 0)]
    count = 0
    while pending:
        value, level = pending.pop()
        count += 1
        if count > 20_000 or level > 64:
            return False
        if type(value) is dict:
            pending.extend((child, level + 1) for pair in value.items() for child in pair)
        elif type(value) is list:
            pending.extend((child, level + 1) for child in value)
        elif type(value) is float:
            if not math.isfinite(value):
                return False
        elif type(value) not in (str, int, bool, type(None)):
            return False
    catalog, layer = Path(pathname).stem.split("__", 1)
    if type(document) is not dict or type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        return False
    if document.get("catalog") != catalog or document.get("layer_id") != layer or type(document.get("candidates")) is not list:
        return False
    for candidate in document["candidates"]:
        if type(candidate) is not dict or type(candidate.get("adopted")) is not bool:
            return False
        refs = candidate.get("evidence_refs")
        if type(refs) is not list or any(type(ref) is not str or len(ref) > 16_384 for ref in refs):
            return False
    return True


def _load_approved_packet_json(pathname, allowed_roots, expected_sha256=None):
    """Load a bounded, digest-bound public packet snapshot; never open its evidence references.

    Only flat catalog__layer.json inputs in an approved packets directory are eligible. The
    caller may supply a trusted digest; otherwise the approved input root's SHA256SUMS supplies it.
    A refusal returns None. This seam also permits portable tests with an approved snapshot.
    CPython v3.13.16 Modules/posixmodule.c:11159-11170 forwards dir_fd to openat;
    Linux v6.12 fs/open.c:1316-1326 and fs/pipe.c:1145-1164 define no-follow,
    directory-only, and nonblocking opens. The byte cap applies before decoding;
    node/depth bounds apply to accepted results (CPython Doc/library/json.rst:716-727).
    """
    import stat

    maximum = 1_048_576
    root_fd = None
    try:
        path = Path(pathname)
        forbidden = {"auth", "credential", "credentials", "secret", "secrets", "key", "keys", "config", "settings", "session"}
        if not path.is_absolute() or ".." in path.parts or not re.fullmatch(r"[a-z][a-z0-9_-]*__[a-z][a-z0-9_-]*\.json", path.name):
            return None
        if forbidden.intersection(re.split(r"[_-]+", path.stem)):
            return None
        packet_roots = [Path(root) for root in allowed_roots if Path(root).name == "packets" and path.parent == Path(root)]
        if len(packet_roots) != 1 or path.is_symlink() or packet_roots[0].is_symlink():
            return None
        root = packet_roots[0].resolve(strict=True)
        canonical = path.resolve(strict=True)
        if canonical.parent != root or canonical.name != path.name:
            return None
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            return None
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        root_fd = os.open(packet_roots[0].anchor, directory_flags)
        for component in packet_roots[0].parts[1:]:
            if component in {".", ".."}:
                return None
            child_fd = os.open(component, directory_flags, dir_fd=root_fd)
            os.close(root_fd)
            root_fd = child_fd

        def read_bounded(name, limit):
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
            with os.fdopen(descriptor, "rb") as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
                    return None
                value = stream.read(limit + 1)
                after = os.fstat(stream.fileno())
                named = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
                identity = lambda info: (info.st_dev, info.st_ino, info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                return value if len(value) <= limit and identity(before) == identity(after) == identity(named) else None

        if expected_sha256 is None:
            manifest = read_bounded("SHA256SUMS", 131_072)
            if manifest is None:
                return None
            matches = []
            for line in manifest.decode("ascii").splitlines():
                fields = line.split(None, 1)
                if len(fields) == 2 and fields[1].lstrip('*') == path.name:
                    matches.append(fields[0])
            if len(matches) != 1:
                return None
            expected_sha256 = matches[0]
        if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
            return None
        contents = read_bounded(path.name, maximum)
        if contents is None or hashlib.sha256(contents).hexdigest() != expected_sha256.lower():
            return None
        document = json.loads(contents)
        return document if _packet_document_valid(document, path) else None
    except (OSError, ValueError, TypeError, RecursionError, UnicodeError, NotImplementedError):
        return None
    finally:
        if root_fd is not None:
            os.close(root_fd)


def python_audit(source: str, allowed_roots, tools, depth=0, *, cwd=None) -> list[str]:
    """Statically identify Python read operands and subprocess argv with ast; never eval/exec code.

    Literal data (including '/'.join for JSON locations) is not a filesystem read. Dynamic/unresolved read
    operands and execution stay refused. This is command analysis, not syscall or branch attestation.
    """
    if depth > 8 or len(source) > 250_000:
        return ["Python audit nesting or source limit"]
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return ["unresolved Python interpreter source"]
    nodes = list(ast.walk(tree))
    if len(nodes) > 50_000:
        return ["Python audit node limit"]
    reasons = []
    read_keywords = {"open": "file", "io.open": "file", "builtins.open": "file", "os.open": "path",
                     "os.listdir": "path", "os.scandir": "path", "os.walk": "top", "os.stat": "path",
                     "os.lstat": "path", "os.readlink": "path", "os.chdir": "path", "glob.glob": "pathname",
                     "glob.iglob": "pathname", "urllib.request.urlopen": "url", "os.path.samefile": "f1"}
    path_methods = {"read_text", "read_bytes", "open", "iterdir", "glob", "rglob", "stat", "lstat",
                    "is_file", "is_dir", "exists", "is_symlink", "readlink", "samefile"}
    execution = {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call",
                 "subprocess.check_output", "subprocess.getoutput", "subprocess.getstatusoutput", "os.system", "os.popen"}
    dynamic = {"eval", "exec", "__import__", "compile", "globals", "locals"}
    constructors = {"Path", "pathlib.Path", "PurePath", "pathlib.PurePath", "pathlib.PosixPath", "pathlib.PurePosixPath"}
    read_keywords.update({constructor + '.' + method: "self" for constructor in constructors for method in ("owner", "group")})
    known = set(read_keywords) | execution | dynamic | constructors | {"getattr", "os.getenv", "os.environ.get", "json.loads"}

    # Bindings are lexical and conservative across branches: every possible assignment must resolve.
    scopes, parent_scope, bindings, namespace_writes = {}, {id(tree): None}, {}, []
    parents = {id(child): node for node in nodes for child in ast.iter_child_nodes(node)}
    stack = [(tree, id(tree))]
    while stack:
        node, scope = stack.pop()
        scopes[id(node)] = scope
        child_scope = scope
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            if not isinstance(node, ast.Lambda):
                bindings.setdefault((scope, node.name), []).append(node)
            child_scope = id(node)
            parent_scope[child_scope] = scope
            if hasattr(node, "args"):
                parameters = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                parameters += [arg for arg in (node.args.vararg, node.args.kwarg) if arg]
                for arg in parameters:
                    bindings[(child_scope, arg.arg)] = [None]
        stack.extend((child, child_scope) for child in ast.iter_child_nodes(node))

    def bind(target, value, scope):
        if isinstance(target, ast.Name):
            bindings.setdefault((scope, target.id), []).append(value)
        elif isinstance(target, (ast.List, ast.Tuple)):
            parts = value.elts if isinstance(value, (ast.List, ast.Tuple)) and len(value.elts) == len(target.elts) else [None] * len(target.elts)
            for element, part in zip(target.elts, parts):
                bind(element, part, scope)
        elif isinstance(target, (ast.Attribute, ast.Subscript)):
            namespace_writes.append(value)

    for node in nodes:
        scope = scopes[id(node)]
        if isinstance(node, ast.Import):
            for alias in node.names:
                bind(ast.Name(id=alias.asname or alias.name.split('.')[0]),
                     alias.name if alias.asname else alias.name.split('.')[0], scope)
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "*":
                    reasons.append("unresolved Python imported namespace")
                else:
                    bind(ast.Name(id=alias.asname or alias.name), node.module + '.' + alias.name, scope)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                bind(target, node.value, scope)
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
            bind(node.target, node.value, scope)
        elif isinstance(node, ast.AugAssign):
            bind(node.target, None, scope)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            if isinstance(node.iter, (ast.List, ast.Tuple)):
                for element in node.iter.elts:
                    bind(node.target, element, scope)
            elif isinstance(node, ast.For) and isinstance(node.target, ast.Name):
                bind(node.target, node, scope)
            else:
                bind(node.target, None, scope)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            reasons.append("unresolved Python namespace rebinding")

    def binding_key(node):
        scope = scopes.get(id(node), id(tree))
        while scope is not None:
            key = (scope, node.id)
            if key in bindings:
                return key
            scope = parent_scope[scope]
        return None

    def lookup(node):
        key = binding_key(node)
        return bindings[key] if key is not None else None

    memo, active, path_receivers, path_receiver_active = {}, set(), {}, set()
    budget = {"work": 20_000, "characters": 1_000_000}
    read_use = None

    def limited():
        if "Python static resolution limit" not in reasons:
            reasons.append("Python static resolution limit")
        return None

    def resolve(node, domain, level):
        if node is None:
            return None
        key = (domain, id(node), id(read_use))
        if key in memo:
            return memo[key]
        if level > 64 or budget["work"] <= 0:
            return limited()
        if key in active:
            return None
        budget["work"] -= 1
        active.add(key)
        try:
            result = string_values(node, level + 1) if domain == "strings" else callable_values(node, level + 1)
            if result is not None:
                if len(result) > 64:
                    result = limited()
                elif domain == "strings":
                    size = sum(len(value) for value in result)
                    if any(len(value) > 16_384 for value in result) or size > budget["characters"]:
                        result = limited()
                    else:
                        budget["characters"] -= size
            memo[key] = result
            return result
        finally:
            active.remove(key)

    def strings(node, level=0):
        return resolve(node, "strings", level)

    def callables(node, level=0):
        return resolve(node, "callables", level)

    def labels(node, level=0):
        values = callables(node, level)
        return {label for kind, label, _ in values if kind == "named"} if values is not None else set()

    def attributes(receiver, attribute, level):
        prefixes = labels(receiver, level)
        named = {prefix + '.' + attribute for prefix in prefixes}
        if named & known or named & {"os.environ", "os.getcwd"}:
            return {("named", value, None) for value in named}
        if attribute in path_methods:
            return {("path", attribute, receiver)}
        if attribute in {"owner", "group"} and path_receiver(receiver, level):
            return {("path", attribute, receiver)}
        if attribute != "get" and attribute in {value.rsplit('.', 1)[-1] for value in known}:
            return None
        return {("named", value, None) for value in named} if named else {("named", attribute, None)}

    def path_receiver(node, level):
        key = id(node)
        if key in path_receivers:
            return path_receivers[key]
        if level > 64 or budget["work"] <= 0:
            limited()
            return False
        if key in path_receiver_active:
            reasons.append("unresolved Python path receiver")
            return False
        budget["work"] -= 1
        path_receiver_active.add(key)
        try:
            value = False
            if isinstance(node, ast.Name):
                values = lookup(node)
                value = bool(values) and all(isinstance(item, ast.AST) and path_receiver(item, level + 1) for item in values)
            elif isinstance(node, ast.Attribute) and node.attr == "parent":
                value = path_receiver(node.value, level + 1)
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                value = path_receiver(node.left, level + 1)
            elif isinstance(node, ast.Call):
                value = bool(labels(node.func, level) & (constructors | {"Path.cwd", "pathlib.Path.cwd"})) or (
                    isinstance(node.func, ast.Attribute) and node.func.attr in {"resolve", "absolute", "joinpath"}
                    and path_receiver(node.func.value, level + 1))
            path_receivers[key] = value
            return value
        finally:
            path_receiver_active.remove(key)

    def callable_values(node, level):
        if isinstance(node, ast.Name):
            assigned = lookup(node)
            if assigned is None:
                return {("named", node.id, None)}
            result = set()
            for value in assigned:
                part = {("named", value, None)} if isinstance(value, str) else callables(value, level)
                if part is None:
                    return None
                result.update(part)
            return result
        if isinstance(node, ast.Attribute):
            return attributes(node.value, node.attr, level)
        if isinstance(node, ast.Call) and labels(node.func, level) == {"getattr"}:
            if len(node.args) != 2 or node.keywords:
                return None
            names = strings(node.args[1], level)
            if names is None or len(names) != 1:
                return None
            return attributes(node.args[0], next(iter(names)), level)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return {("local", node.name, None)}
        return None

    def combine(left, right, join):
        if left is None or right is None:
            return None
        if len(left) * len(right) > 64:
            return limited()
        if any(len(a) + len(b) > 16_384 for a in left for b in right):
            return limited()
        return {join(a, b) for a in left for b in right}

    # The only data decoder is CPython v3.13.16 json.loads' default inert decoder
    # (Lib/json/__init__.py:339-352). AST expressions below select native values;
    # they do not execute payloads, callbacks, imports, or evidence-reference reads.
    class PacketSnapshot:
        def __init__(self, document):
            self.document = document

    data_memo, data_active, packet_snapshots = {}, set(), {}
    dependency_memo, mutation_memo = {}, {}
    dependency_unknown = object()

    def data_value(node, environment=None, level=0):
        if node is None or level > 64 or budget["work"] <= 0:
            limited()
            return None
        budget["work"] -= 1
        key = id(node)
        if not environment and key in data_memo:
            return data_memo[key]
        if not environment and key in data_active:
            return None
        if not environment:
            data_active.add(key)
        try:
            result = data_expression(node, environment or {}, level + 1)
            if not environment:
                data_memo[key] = result
            return result
        except (KeyError, IndexError, TypeError, ValueError, RecursionError):
            return None
        finally:
            if not environment:
                data_active.remove(key)

    def data_expression(node, environment, level):
        if isinstance(node, ast.Constant) and type(node.value) in (str, int, float, bool, type(None)):
            return node.value, frozenset()
        if isinstance(node, ast.Name):
            if node.id in environment:
                return environment[node.id]
            assigned = lookup(node)
            if assigned is None or len(assigned) != 1 or not isinstance(assigned[0], ast.AST):
                return None
            value = data_value(assigned[0], level=level)
            return (value[0], value[1] | {binding_key(node)}) if value is not None else None
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and type(node.slice.value) in (str, int):
            base = data_value(node.value, environment, level)
            if base is not None and type(base[0]) in (dict, list, tuple):
                return base[0][node.slice.value], base[1]
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values = [data_value(item, environment, level) for item in node.elts]
            if any(value is None for value in values) or len(values) > 4096:
                return None
            container = tuple if isinstance(node, ast.Tuple) else set if isinstance(node, ast.Set) else list
            return container(value[0] for value in values), frozenset().union(*(value[1] for value in values))
        if isinstance(node, (ast.ListComp, ast.SetComp)):
            if len(node.generators) > 64:
                return limited()
            results, dependencies = [], set()

            def project(index, current):
                if index == len(node.generators):
                    value = data_value(node.elt, current, level)
                    if value is None or len(results) >= 4096:
                        return False
                    results.append(value[0])
                    dependencies.update(value[1])
                    return True
                generator = node.generators[index]
                if generator.is_async or not isinstance(generator.target, ast.Name):
                    return False
                iterable = data_value(generator.iter, current, level)
                if iterable is None or type(iterable[0]) not in (list, tuple, set) or len(iterable[0]) > 4096:
                    return False
                dependencies.update(iterable[1])
                for value in iterable[0]:
                    nested = dict(current)
                    nested[generator.target.id] = value, iterable[1]
                    predicates = [data_value(condition, nested, level) for condition in generator.ifs]
                    if any(predicate is None for predicate in predicates):
                        return False
                    dependencies.update(frozenset().union(*(predicate[1] for predicate in predicates)))
                    if all(bool(predicate[0]) for predicate in predicates) and not project(index + 1, nested):
                        return False
                return True

            if project(0, environment):
                return (set(results) if isinstance(node, ast.SetComp) else results), frozenset(dependencies)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            operand = data_value(node.operand, environment, level)
            return (not operand[0], operand[1]) if operand is not None else None
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left = data_value(node.left, environment, level)
            right = data_value(node.comparators[0], environment, level)
            if left is not None and right is not None:
                a, b = left[0], right[0]
                operation = node.ops[0]
                if isinstance(operation, ast.In):
                    value = a in b
                elif isinstance(operation, ast.NotIn):
                    value = a not in b
                elif isinstance(operation, ast.Eq):
                    value = a == b
                elif isinstance(operation, ast.NotEq):
                    value = a != b
                else:
                    return None
                return value, left[1] | right[1]
        if isinstance(node, ast.Call):
            called = labels(node.func, level)
            if called == {"json.loads"} and len(node.args) == 1 and not node.keywords:
                value = data_value(node.args[0], environment, level)
                if value is not None and type(value[0]) is PacketSnapshot:
                    return value[0].document, value[1]
            if called == {"sorted"} and len(node.args) == 1 and not node.keywords:
                value = data_value(node.args[0], environment, level)
                if value is not None and type(value[0]) in (list, tuple, set) and len(value[0]) <= 4096:
                    return sorted(value[0]), value[1]
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"read_bytes", "read_text"} and path_receiver(node.func.value, level):
                if node.args or (node.keywords and not (node.func.attr == "read_text" and len(node.keywords) == 1
                        and node.keywords[0].arg == "encoding" and isinstance(node.keywords[0].value, ast.Constant)
                        and node.keywords[0].value.value in ("utf-8", "utf8"))):
                    return None
                paths = strings(node.func.value, level)
                if paths is None or len(paths) != 1:
                    return None
                pathname = next(iter(paths))
                path = Path(pathname)
                if not path.is_absolute() or ".." in path.parts or not re.fullmatch(r"[a-z][a-z0-9_-]*__[a-z][a-z0-9_-]*\.json", path.name):
                    return None
                if not any(Path(root).name == "packets" and Path(root) == path.parent for root in allowed_roots):
                    return None
                if pathname not in packet_snapshots:
                    document = _load_approved_packet_json(pathname, allowed_roots)
                    packet_snapshots[pathname] = PacketSnapshot(document) if _packet_document_valid(document, pathname) else None
                snapshot = packet_snapshots[pathname]
                return (snapshot, frozenset()) if snapshot is not None else None
        return None

    def dependency_names(node, level=0):
        if not isinstance(node, ast.AST):
            return set()
        if id(node) in dependency_memo:
            return dependency_memo[id(node)]
        if level > 64 or budget["work"] <= 0:
            limited()
            return {dependency_unknown}
        budget["work"] -= 1
        if isinstance(node, ast.Name):
            key = binding_key(node)
            result = {key} if key is not None else set()
        else:
            children = ([node.iter] if isinstance(node, ast.For) else
                        [*node.args, *(keyword.value for keyword in node.keywords)] if isinstance(node, ast.Call) else
                        ast.iter_child_nodes(node))
            result = set().union(*(dependency_names(child, level + 1) for child in children))
        dependency_memo[id(node)] = result
        return result

    def dependency_closure(expression):
        pending, found = list(dependency_names(expression)), set()
        while pending:
            key = pending.pop()
            if key is dependency_unknown:
                return None
            if key in found:
                continue
            if budget["work"] <= 0 or len(found) >= 4096:
                limited()
                return None
            budget["work"] -= 1
            found.add(key)
            for value in bindings[key]:
                pending.extend(dependency_names(value) - found)
        return found

    def data_safe(dependencies):
        if not dependencies:
            return True
        if dependencies in mutation_memo:
            return mutation_memo[dependencies]

        def relevant(expression):
            closure = dependency_closure(expression)
            return closure is None or bool(closure & dependencies)

        safe = True
        for item in nodes:
            # Reflective namespace mutation defeats an exact stdlib callable label.
            # Refuse it lazily for packet-dependent reads, including callable aliases.
            reflective = {"__dict__", "__setattr__", "__delattr__", "__getattribute__"}
            if isinstance(item, ast.Attribute) and item.attr in reflective:
                safe = False
            targets = item.targets if isinstance(item, (ast.Assign, ast.Delete)) else [item.target] if isinstance(item, (ast.AugAssign, ast.AnnAssign)) else []
            for target in targets:
                if isinstance(target, (ast.Subscript, ast.Attribute)) and relevant(target.value):
                    safe = False
                elif isinstance(item, (ast.AugAssign, ast.Delete)) and isinstance(target, ast.Name) and relevant(target):
                    safe = False
            if not isinstance(item, ast.Call):
                continue
            called = labels(item.func)
            if any(name.rsplit('.', 1)[-1] in {"setattr", "delattr", "vars"} | reflective for name in called):
                safe = False
            if called == {"getattr"} and len(item.args) > 1 and (strings(item.args[1]) or set()) & reflective:
                safe = False
            operands = [*item.args, *(keyword.value for keyword in item.keywords)]
            if isinstance(item.func, ast.Attribute):
                operands.append(item.func.value)
            if isinstance(item.func, ast.Name):
                assigned = lookup(item.func) or []
                operands.extend(value for value in assigned if isinstance(value, ast.AST))
            if not any(relevant(operand) for operand in operands):
                continue
            resolved = callables(item.func)
            harmless = bool(called) and called <= constructors | set(read_keywords) | path_methods
            harmless |= bool(resolved) and all(kind == "path" for kind, _, _ in resolved)
            harmless |= called in ({"json.loads"}, {"json.dumps"}, {"sorted"}, {"len"}, {"str"}, {"hashlib.sha256"}) and len(item.args) == 1 and not item.keywords
            harmless |= called == {"print"} and not item.keywords
            harmless |= (isinstance(item.func, ast.Attribute) and item.func.attr == "hexdigest" and not item.args and not item.keywords
                         and isinstance(item.func.value, ast.Call) and labels(item.func.value.func) == {"hashlib.sha256"})
            if not harmless:
                safe = False
        mutation_memo[dependencies] = safe
        if not safe:
            reasons.append("unresolved Python packet mutation or callback")
        return safe

    def guarded_loop_values(loop, values):
        current = read_use
        while current is not None and parents.get(id(current)) is not loop:
            current = parents.get(id(current))
        if current not in loop.body:
            return values
        for statement in loop.body[:loop.body.index(current)]:
            if not isinstance(statement, ast.If) or statement.orelse or not statement.body or not isinstance(statement.body[-1], ast.Continue):
                continue
            test = statement.test
            if (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.In)
                    and isinstance(test.left, ast.Constant) and test.left.value == "://"
                    and isinstance(test.comparators[0], ast.Name) and binding_key(test.comparators[0]) == binding_key(loop.target)):
                return {value for value in values if "://" not in value}
        return values

    def string_values(node, level):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {node.value}
        if isinstance(node, ast.Name):
            assigned = lookup(node)
            if assigned is None:
                return None
            result = set()
            for value in assigned:
                part = strings(value, level) if isinstance(value, ast.AST) else None
                if part is None:
                    return None
                result.update(part)
                if len(result) > 64:
                    return limited()
            return result
        if isinstance(node, ast.For):
            projection = data_value(node.iter, level=level)
            if projection is not None and type(projection[0]) in (list, tuple, set) and all(type(value) is str for value in projection[0]) and data_safe(projection[1]):
                return guarded_loop_values(node, set(projection[0]))
            return None
        if isinstance(node, ast.Subscript):
            projection = data_value(node, level=level)
            if projection is not None and type(projection[0]) is str and data_safe(projection[1]):
                return {projection[0]}
            return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Div)):
            return combine(strings(node.left, level), strings(node.right, level),
                           (lambda a, b: a + b) if isinstance(node.op, ast.Add) else os.path.join)
        if isinstance(node, ast.Attribute) and node.attr == "parent":
            base = strings(node.value, level)
            return {os.path.dirname(value.rstrip('/')) or ("/" if value.startswith('/') else ".") for value in base} if base is not None else None
        if isinstance(node, ast.Call):
            called = labels(node.func, level)
            if called and called <= constructors | {"os.path.join"}:
                if node.keywords:
                    return None
                result = {"."} if not node.args else {""}
                for argument in node.args:
                    result = combine(result, strings(argument, level), os.path.join)
                return result
            if called & {"Path.cwd", "pathlib.Path.cwd", "os.getcwd"}:
                base = cwd if cwd is not None else allowed_roots[0] if allowed_roots else None
                return {str(base)} if base is not None and not node.args and not node.keywords else None
            if isinstance(node.func, ast.Attribute):
                method = node.func.attr
                if method in ("resolve", "absolute"):
                    return strings(node.func.value, level)
                if method == "joinpath":
                    result = strings(node.func.value, level)
                    for argument in node.args:
                        result = combine(result, strings(argument, level), os.path.join)
                    return result if not node.keywords else None
                if method in ("rstrip", "lstrip", "strip"):
                    base = strings(node.func.value, level)
                    chars = strings(node.args[0], level) if node.args else {None}
                    if base is not None and chars is not None and len(base) * len(chars) <= 64:
                        return {getattr(value, method)(char) for value in base for char in chars}
        return None

    def argument(node, position, keywords):
        if len(node.args) > position:
            return node.args[position]
        return next((keyword.value for keyword in node.keywords if keyword.arg in keywords), None)

    def read_operand(operand, default=None, network=False):
        if operand is None and default is not None:
            resolved = {default}
        else:
            resolved = strings(operand)
        if resolved is None:
            expression = ast.get_source_segment(source, operand) if operand is not None else None
            if expression:
                reasons.extend(operand_reasons(expression, allowed_roots))
            reasons.append("unresolved Python read operand")
            return
        for value in resolved:
            original = value
            try:
                parsed = urlsplit(value)
            except ValueError:
                reasons.append("unresolved Python read URL")
                continue
            if parsed.scheme and local_scheme(parsed.scheme):
                value = parsed.path or "/"
            elif parsed.scheme and network:
                reasons.append("Python network read")
            path_reasons = operand_reasons(value, allowed_roots)
            reasons.extend(path_reasons)
            if path_reasons:
                if value != original:
                    reasons.extend(operand_reasons(original, allowed_roots))
                if os.path.isabs(value) and operand is not None:
                    expression = ast.get_source_segment(source, operand) or ""
                    if names_root(expression):
                        reasons.append("names the filesystem root /")

    def sequence(node):
        if isinstance(node, (ast.List, ast.Tuple)):
            return node.elts
        if isinstance(node, ast.Name):
            assigned = lookup(node)
            if assigned is not None and len(assigned) == 1 and isinstance(assigned[0], (ast.List, ast.Tuple)):
                return assigned[0].elts
        return None

    def analyze_execution(node, called):
        operand = argument(node, 0, {"args", "command", "cmd"})
        elements = sequence(operand)
        shell_keyword = next((keyword.value for keyword in node.keywords if keyword.arg == "shell"), None)
        shell = called in {"os.system", "os.popen", "subprocess.getoutput", "subprocess.getstatusoutput"}
        if shell_keyword is not None:
            if not isinstance(shell_keyword, ast.Constant) or not isinstance(shell_keyword.value, bool):
                reasons.append("unresolved Python shell execution mode")
                return
            shell = shell_keyword.value
        if elements is not None:
            argv = []
            for element in elements:
                candidates = strings(element)
                if candidates is None or len(candidates) != 1:
                    reasons.append("unresolved Python executable argv")
                    return
                argv.append(next(iter(candidates)))
            if not argv:
                reasons.append("unresolved Python executable argv")
                return
            commands = [shlex.join(["/bin/sh", "-c", *argv] if shell else argv)]
        else:
            candidates = strings(operand)
            if candidates is None:
                reasons.append("unresolved Python executable source")
                return
            commands = [value if shell else shlex.join([value]) for value in candidates]
        for keyword in node.keywords:
            if keyword.arg in {"cwd", "executable"}:
                read_operand(keyword.value)
            if keyword.arg == "cwd":
                reasons.append("working directory changed by Python subprocess; command unverified")
        for command in commands:
            try:
                reasons.extend(analysis_reasons(command_analyses([command])[0], allowed_roots, tools, depth + 1,
                                                cwd=cwd))
            except AuditAnalysisUnavailable as error:
                reasons.append(str(error))

    for expression in namespace_writes:
        if expression is not None and not isinstance(expression, (ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.Set)) and strings(expression) is None:
            reasons.append("unresolved Python callable namespace write")

    for node in nodes:
        if isinstance(node, ast.Attribute) and "os.environ" in labels(node):
            reasons.append("reads the environment: os.environ")
        if not isinstance(node, ast.Call):
            continue
        read_use = node
        resolved = callables(node.func)
        if resolved is None:
            reasons.append("unresolved Python callable alias")
            continue
        for kind, called, receiver in resolved:
            if kind == "path":
                read_operand(receiver)
                if called == "samefile":
                    read_operand(argument(node, 0, {"other_path"}))
                if called in ("glob", "rglob"):
                    pattern = argument(node, 0, {"pattern"})
                    read_operand(pattern)
                    bases, patterns = strings(receiver), strings(pattern)
                    joined = combine(bases, patterns, os.path.join)
                    if joined is None:
                        reasons.append("unresolved Python glob operand")
                    else:
                        for value in joined:
                            reasons.extend(operand_reasons(value, allowed_roots))
            elif called in dynamic:
                reasons.append("unresolved dynamic Python execution or namespace")
            elif called in ("os.getenv", "os.environ.get"):
                reasons.append("reads the environment: " + called)
            elif called in ("os.chdir", "os.fchdir"):
                reasons.append("working directory changed by Python; command unverified")
            elif called in read_keywords:
                read_operand(argument(node, 0, {read_keywords[called]}),
                             default="." if called in ("os.listdir", "os.scandir") else None,
                             network=called == "urllib.request.urlopen")
                if called == "os.path.samefile":
                    read_operand(argument(node, 1, {"f2"}))
            elif called in execution:
                analyze_execution(node, called)
            elif called.startswith(("os.exec", "os.spawn")):
                reasons.append("unresolved Python executable interface")
            if kind == "path" or called in read_keywords:
                for keyword in node.keywords:
                    if keyword.arg in {"root_dir", "cwd"}:
                        read_operand(keyword.value)
                    elif keyword.arg == "dir_fd" and not (isinstance(keyword.value, ast.Constant) and keyword.value.value is None):
                        reasons.append("unresolved Python read directory descriptor")
    return list(dict.fromkeys(reasons))


def analysis_reasons(analysis, allowed_roots, tools, depth=0, *, cwd=None) -> list[str]:
    """Policy over parsed command positions, read operands, interpreter source and real shell expansions."""
    if depth > 8:
        return ["command audit nesting limit"]
    reasons = ["unresolved shell command: " + str(error) for error in analysis.get("errors", [])]
    if not analysis.get("ok") and not reasons:
        reasons.append("unresolved shell command")
    for invocation in analysis.get("invocations", []):
        argv = invocation.get("argv", [])
        end = invocation.get("wrapped_program_index", len(argv))
        code_index = invocation.get("code_arg_index")
        raw = invocation.get("raw_argv", [])
        # An unresolved shell word remains refused. Its source span can still preserve a specific home/variable
        # path or cd reason; it is never expanded or used to infer a clean command.
        operands = [value if value is not None else raw[i].strip("'\"") if i < len(raw) else None
                    for i, value in enumerate(argv[:end]) if i != code_index]
        reasons += argv_reasons(operands, allowed_roots, tools,
                                forwarding=invocation.get("source_kind") == "wrapper")
        if operands and isinstance(operands[0], str):
            program = os.path.basename(operands[0])
            if program in {"cd", "pushd", "popd", "chroot", "nsenter", "unshare"} or program == "env" and any(
                    isinstance(word, str) and (word in {"-C", "--chdir"} or word.startswith("--chdir=")
                                              or word.startswith("-C") and len(word) > 2)
                    for word in operands[1:]):
                reasons.append(f"working directory changed by {program}; command unverified")
    for source in analysis.get("python_sources", []):
        reasons += python_audit(source, allowed_roots, tools, depth, cwd=cwd)
    for source in analysis.get("expansions", []):
        if COMMAND_SUBSTITUTION.search(source) or source.startswith("<(") or source.startswith(">("):
            reasons.append("command substitution")
        reasons += [f"parameter expansion: {m}" for m in PARAMETER_EXPANSION.findall(source)]
        reasons += [f"inherited directory variable: {m}" for m in INHERITED_DIRECTORY.findall(source)]
        reasons += [f"names the Codex home: {m}" for m in CODEX_HOME_REFERENCE.findall(source)]
        reasons += [f"home-relative path: {m}" for m in HOME_PATH.findall(source)]
        reasons += [f"variable path: {m}" for m in VARIABLE_PATH.findall(source)]
    for value in analysis.get("redirect_paths", []):
        reasons += operand_reasons(value, allowed_roots)
    return list(dict.fromkeys(reasons))


def recorded_command_cwd(item, cwd_records, allowed_roots) -> tuple[str | None, list[str]]:
    """Bind a display to a caller-owned native record; stdout's cwd/workdir fields are not telemetry.

    Codex 0.162.1's exec JSONL omits cwd. A separately captured record must preserve the item identity,
    exact display and absolute working directory. The runner has no such capture and never infers it from -C.
    """
    identity = item.get("id")
    record = cwd_records.get(identity) if isinstance(identity, str) and isinstance(cwd_records, dict) else None
    if not isinstance(record, dict) or record.get("command") != item.get("command"):
        return None, ["working directory unverified: missing or mismatched independent command record"]
    cwd = record.get("cwd")
    if not isinstance(cwd, str) or not cwd.startswith("/") or "\x00" in cwd:
        return None, ["working directory unverified: independent record has no absolute cwd"]
    cwd = os.path.normpath(cwd)
    if cwd == "/" or not any(cwd == root or cwd.startswith(root.rstrip("/") + "/") for root in allowed_roots):
        return None, ["working directory outside the repository and packets: " + cwd]
    return cwd, []


def blind_audit(events_path: Path, allowed_roots, tools=AUDIT_TOOLS, *, cwd_records=None) -> dict:
    """Reading of one child's event stream: web searches, MCP tool calls, and commands with read operands
    outside ``allowed_roots`` (the repository and the packets directory) or executables in ``tools`` (AUDIT_TOOLS; a
    non-blind run adds BLIND_UNRESOLVABLE, which its PATH may resolve). In a blind run
    a flagged layer is void: its return is set aside before it is written, and a resume re-audits a kept return
    (round 7, REG7-1); in a non-blind run the report is for review and disclosure.

    This statically parses Codex's recorded command display. It is not syscall/branch attestation: indirect
    script/config/symlink reads are not observed. Unsupported shell source/expansion and unresolved interpreted
    read or execution operands are refused. Every command needs an independent cwd record; the pinned exec
    JSONL lacks it, so current native streams are explicitly unverified rather than assuming the turn cwd.
    Executable words and interpreter read operands are distinguished from patterns and formatting data."""
    report = {"web_search": 0, "mcp_tool_calls": 0, "commands": 0, "flagged_commands": []}
    if not events_path.is_file():
        return report
    completed = []
    for line in events_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict) or event.get("type") != "item.completed":
            continue
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        kind = item.get("type")
        if kind == "web_search":
            report["web_search"] += 1
        elif kind == "mcp_tool_call":
            report["mcp_tool_calls"] += 1
        elif kind == "command_execution":
            report["commands"] += 1
            command = item.get("command") if isinstance(item.get("command"), str) else ""
            completed.append((command, item))
    try:
        analyses = command_analyses([command for command, _ in completed]) if completed else []
        identities = [item.get("id") for _, item in completed]
        for (command, item), analysis in zip(completed, analyses):
            cwd, reasons = recorded_command_cwd(item, cwd_records, allowed_roots)
            if item.get("id") is not None and identities.count(item.get("id")) > 1:
                cwd = None
                reasons.append("working directory unverified: duplicate command identity")
            reasons += analysis_reasons(analysis, allowed_roots, tools, cwd=cwd)
            if reasons:
                report["flagged_commands"].append({"command": command, "reasons": reasons})
    except AuditAnalysisUnavailable as error:
        report["flagged_commands"].append({"command": "", "reasons": [str(error)]})
    return report


# The CODEX_HOME every blind child runs with (isolated_codex_home), or None to inherit the caller's.
CHILD_CODEX_HOME = None
# Where run-scoped Codex homes live: outside the work dir (which holds both lanes' returns) and outside the
# adjudication state dir (the position index). The default base shares a parent with that state dir, so a path a
# child derives from its CODEX_HOME can reach it; the blind audit flags any use of CODEX_HOME and any path outside
# the export and packets, as far as command text shows (independent review of #145, BIND-R4-7; round 7, ISO-R7-9).
# Each run gets a fresh directory there (mkdtemp); nothing is ever removed to make one (round 5, INT-R5-2: removing
# a home that was, or held, the native home deleted it).
CODEX_HOME_BASE_ENV = "NAS_CODEX_HOME_DIR"
DEFAULT_CODEX_HOME_BASE = Path("~/.local/state/native-agent-stack/codex-home")


class CodexHomeRefused(ValueError):
    """The run-scoped Codex home cannot be set up without touching a credential or a lane input."""


def codex_home_base() -> Path:
    """``$NAS_CODEX_HOME_DIR``, else ``~/.local/state/native-agent-stack/codex-home``, absolutized."""
    return Path(os.environ.get(CODEX_HOME_BASE_ENV) or DEFAULT_CODEX_HOME_BASE).expanduser().absolute()


def codex_home_prefix(work_dir: Path) -> str:
    """The name prefix of ``work_dir``'s run homes under codex_home_base: sha256(resolved work dir)[:16]."""
    return hashlib.sha256(str(Path(work_dir).resolve()).encode("utf-8")).hexdigest()[:16]


def native_codex_home() -> Path:
    """The native Codex home: ``$CODEX_HOME``, else ``~/.codex``, absolutized."""
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().absolute()


def native_auth_path() -> Path:
    """The native Codex credential, ``native_codex_home()/auth.json``."""
    return native_codex_home() / "auth.json"


def _contains(outer: Path, inner: Path) -> bool:
    return inner == outer or outer in inner.parents


def _overlap(first: Path, second: Path) -> bool:
    spellings = [(a, b) for a in {first, Path(os.path.realpath(first))} for b in {second, Path(os.path.realpath(second))}]
    return any(_contains(a, b) or _contains(b, a) for a, b in spellings)


def codex_home_issue(work_dir: Path, repo: Path = None, *, provider="native"):
    """Why a run-scoped Codex home cannot be set up, or None; creates nothing, so a dry run and the lock run it first
    (round 6, ISO-R6-5). Refused: a base that is, holds or sits inside the native Codex home (either spelling), a
    base overlapping the work dir or ``repo``, and no native auth.json: a blind child never gets an API key, which
    its shell would inherit (round 6, ISO-R6-4); `codex login --with-api-key` makes a native auth.json from one."""
    base = codex_home_base()
    native_home = native_codex_home()
    if _overlap(base, native_home):
        return (f"the run-scoped Codex homes' base {base} and the native Codex home {native_home} overlap; set "
                f"{CODEX_HOME_BASE_ENV} to a directory apart from the native home")
    for place in (Path(work_dir).resolve(), *([Path(repo).resolve()] if repo is not None else [])):
        if _overlap(base, place):
            return (f"the run-scoped Codex homes' base {base} overlaps {place}; set {CODEX_HOME_BASE_ENV} to a "
                    "directory outside the work dir and the export")
    if provider == "native":
        native = native_auth_path()
        if not native.is_file():
            return (f"no native Codex credential at {native}; sign in natively with `codex login` (with an API key: "
                    "`codex login --with-api-key`); a blind child is never given an API key variable")
    for key in PROXY_VARIABLES:
        if PROXY_USERINFO.match(os.environ.get(key) or ""):
            # Every variable a child gets is exported into the model's shell (round 7, ISO-R7-5).
            return (f"{key} carries credentials (user:password@host); every variable a blind child gets reaches the "
                    "model's shell and its events, so use a proxy without inline credentials for a blind run")
    return None


def codex_home_lock(work_dir: Path) -> Path:
    """The homes' base lock for a work dir, held with work_run_lock by both codex_lane and adjudicate codex, so
    neither sweeps or shares the other's credential link (review of 52344da8; round 6, ISO-R6-1)."""
    return codex_home_base() / f"{codex_home_prefix(work_dir)}.lock"


def work_run_lock(work_dir: Path) -> Path:
    """The work dir's own lock, shared by both runners: two runs of one work dir with different homes' bases would
    otherwise both run and interleave the events files (round 7, REG7-2/ISO-R7-4)."""
    return Path(work_dir) / ".codex-run.lock"


IN_USE_NAME = ".in-use"
# The current run home's in-use lock handle; every child inherits it (run_attempt pass_fds), so the flock stays held
# while any child lives, even after the lane is SIGKILLed (round 7, ISO-R7-2).
IN_USE_HANDLE = None


def home_in_use(home: Path) -> bool:
    """Whether a live process (a run, or a child it started) still holds ``home``'s in-use lock."""
    import fcntl
    marker = Path(home) / IN_USE_NAME
    if not marker.is_file():
        return False
    with open(marker, "a", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(handle, fcntl.LOCK_UN)
    return False


def sweep_stale_links(work_dir: Path) -> None:
    """Remove the credential links an interrupted (SIGKILLed) earlier run of this work dir left in its homes; only
    symlinks named auth.json are removed, and never in a home whose in-use lock a live child still holds (round 7,
    ISO-R7-2). The caller holds the run locks (round 6, ISO-R6-1)."""
    for home in codex_home_base().glob(f"{codex_home_prefix(work_dir)}-*"):
        if home.is_dir() and not home_in_use(home):
            remove_codex_home_link(home)


def isolated_codex_home(work_dir: Path, repo: Path = None, *, provider="native") -> Path:
    """Create a fresh run-scoped CODEX_HOME (mode 0700) under codex_home_base, holding only a symlink to the native
    ``auth.json`` (never a copy), the child's empty HOME and an empty TMPDIR. ``--ignore-user-config`` skips
    config.toml but not ``$CODEX_HOME/AGENTS.md``, the user's global instructions, which name adopted tools
    (measured 2026-09-24: a child quoted its "# AGENTS.md instructions" block; with this home it answered "none").
    A fresh directory per run (tempfile.mkdtemp) means no leftover AGENTS.md or config is loaded and nothing is
    removed to make it; the caller removes the credential link when the run ends (remove_codex_home_link). The
    child's sessions and logs stay in the run home for inspection.

    The child's HOME is the empty ``<run home>/home`` (child_home): Codex also discovers user Agent Skills under
    ``$HOME/.agents/skills``, whose names are adopted tools (review of #145, measured 2026-09-24: a child with this
    CODEX_HOME but the caller's HOME listed qmd, tavily-* and typesafe-ai; with the empty HOME it listed only the
    CLI's bundled skills). Its TMPDIR is the empty ``<run home>/tmp``, not the caller's (round 6, REG6-3).

    Raises CodexHomeRefused, creating nothing, for any codex_home_issue."""
    # The keyless OmniRoute provider keeps this private home/lock lifecycle but never
    # resolves, reads, copies or links the native auth path.
    issue = codex_home_issue(work_dir, repo, provider=provider)
    if issue:
        raise CodexHomeRefused(issue)
    base = codex_home_base()
    import fcntl
    global IN_USE_HANDLE
    private_dir(base)
    home = Path(tempfile.mkdtemp(prefix=f"{codex_home_prefix(work_dir)}-", dir=base))
    home.chmod(0o700)
    child_home(home).mkdir(mode=0o700)
    (home / "tmp").mkdir(mode=0o700)
    IN_USE_HANDLE = open(home / IN_USE_NAME, "a", encoding="utf-8")
    fcntl.flock(IN_USE_HANDLE, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if provider == "native":
        native = native_auth_path()
        if native.is_file():
            (home / "auth.json").symlink_to(native)
    return home


def release_codex_home(home) -> None:
    """End a run's use of its home: stop and wait for every live child, then remove the credential link and release
    the in-use lock, in that order, so no child outlives its link (round 7, ISO-R7-2)."""
    global IN_USE_HANDLE
    terminate_children()
    remove_codex_home_link(home)
    if IN_USE_HANDLE is not None:
        IN_USE_HANDLE.close()
        IN_USE_HANDLE = None


def private_dir(path: Path) -> None:
    """Create ``path`` (and its parents) if missing; a directory created here is mode 0700 (round 7, ISO-R7-8)."""
    path = Path(path)
    if not path.is_dir():
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)


def remove_codex_home_link(home) -> None:
    """Remove the run-scoped home's credential link at the end of a run (independent review of #145, OPS-4); the
    child's sessions and logs stay for inspection. Only a symlink is ever removed."""
    if home is None:
        return
    link = Path(home) / "auth.json"
    if link.is_symlink():
        link.unlink()


RUN_LOCK_NAME = ".run.lock"


class RunLocked(RuntimeError):
    """Another run holds this work dir's lock."""


@contextlib.contextmanager
def exclusive_run_lock(path: Path):
    """Hold an exclusive, non-blocking flock on ``path`` for the run (independent review of #145, BIND-R4-5): two
    runs on one work dir would recreate each other's Codex home and interleave each other's events files."""
    import fcntl
    private_dir(path.parent)
    handle = open(path, "a", encoding="utf-8")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RunLocked(f"another run holds {path}; wait for it to finish") from None
    try:
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


# The environment a blind child gets (independent review of #145, round 5, ISO-R5-2): not the caller's, which
# carries the coordinator's transcript pointer, cross-session messaging socket and token, and broker variables.
CHILD_ENV_ALLOWLIST = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "SSL_CERT_FILE", "SSL_CERT_DIR",
                       "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "no_proxy",
                       "all_proxy")
# Extra variable-name prefixes a child keeps; empty in production (the test fixtures' fake codex reads its own).
CHILD_ENV_EXTRA_PREFIXES = ()


PROXY_VARIABLES = tuple(key for key in CHILD_ENV_ALLOWLIST if key.lower().endswith("_proxy") and "no_" not in
                        key.lower())
# userinfo before the host, with or without a scheme, up to the last '@' (round 7, ISO-R7-6).
PROXY_USERINFO = re.compile(r"^((?:[A-Za-z][A-Za-z0-9+.-]*://)?)[^/\s]*@")


def redact_userinfo(value: str) -> str:
    """A proxy URL's user:password@ as ***@ in printed output (round 6, ISO-R6-5; round 7, ISO-R7-6)."""
    return PROXY_USERINFO.sub(r"\1***@", value) if isinstance(value, str) else value


# Set by a stop signal: no attempt starts, no return is written, and every live child is terminated (independent
# review of #145, round 7, REG7-1/ISO-R7-3). Cleared when a run starts.
STOP = threading.Event()
_LIVE_CHILDREN: set = set()
_LIVE_LOCK = threading.Lock()
STOP_GRACE_SECONDS = 10.0


def terminate_children(grace: float = STOP_GRACE_SECONDS) -> None:
    """Terminate every live child, wait up to ``grace`` seconds, then kill those still running."""
    with _LIVE_LOCK:
        children = list(_LIVE_CHILDREN)
    for child in children:
        if child.poll() is None:
            child.terminate()
    deadline = time.monotonic() + grace
    for child in children:
        try:
            child.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


@contextlib.contextmanager
def terminate_on_signal():
    """While held, SIGTERM, SIGHUP and SIGINT set STOP, terminate the live children and raise SystemExit, so the
    caller's cleanup (release_codex_home) runs with no child left; a second signal changes nothing, so it cannot
    interrupt that cleanup (round 6, ISO-R6-1; round 7, ISO-R7-2/ISO-R7-3). A SIGKILLed run leaves its link for the
    next run's sweep_stale_links, which skips a home a live child still holds."""
    import signal
    def stop(signum, _frame):
        if STOP.is_set():
            return
        STOP.set()
        terminate_children()
        raise SystemExit(128 + signum)
    STOP.clear()
    previous = {signum: signal.signal(signum, stop) for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)}
    try:
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def child_env(codex_home: Path, *, provider="native", omniroute_base_url=None) -> dict:
    """The whole environment of a blind child: the allowlisted variables, CODEX_HOME, the empty HOME and TMPDIR, and
    BLIND_CHILD_PATH instead of the caller's PATH. No API key variable: the child authenticates through the linked
    native auth.json (round 6, ISO-R6-4)."""
    # Opt-in OmniRoute adds only its validated public endpoint; no gateway key,
    # auth/account variable, coordinator variable or other ambient provider setting.
    env = {key: value for key, value in os.environ.items()
           if key in CHILD_ENV_ALLOWLIST or (CHILD_ENV_EXTRA_PREFIXES and key.startswith(CHILD_ENV_EXTRA_PREFIXES))}
    env.update({"CODEX_HOME": str(codex_home), "HOME": str(child_home(codex_home)),
                "TMPDIR": str(Path(codex_home) / "tmp"), "PATH": BLIND_CHILD_PATH})
    if provider == "omniroute":
        env[OMNIROUTE_BASE_URL_ENV] = omniroute_endpoint(omniroute_base_url)
    return env


PATH_SENTINEL = "__NAS_BLIND_PATH__="


class PathUnmeasured(Exception):
    """A PATH a blind child's commands can end up with could not be measured (the probe and why)."""


def login_shell_path() -> str:
    """Every PATH a blind child's commands can end up with on this host, joined; PathUnmeasured names the probe that
    could not be measured and why (independent review of #206, R2-4).
    Codex runs each command through the user's shell with ``-lc`` (``/bin/bash -lc`` here), whose profile can add
    directories: on this WSL host /etc/profile.d/apps-bin-path.sh adds /snap/bin, and macOS path_helper adds /etc/paths
    and /etc/paths.d (2026-09-24 probe: codex also prepends its own codex-path directory, which holds only rg). A command
    can also drop PATH (``subprocess.run(..., shell=True, env={})``), and a shell started without one sets its compiled
    default, /usr/local/bin included, while Python's exec uses os.defpath (independent review of #206, C3). Each is
    measured after a sentinel, so profile output is not read as a directory (C5)."""
    import pwd
    import tempfile
    try:
        shell = pwd.getpwuid(os.getuid()).pw_shell or "/bin/sh"
    except KeyError as error:
        raise PathUnmeasured(f"no login shell for this user: {error}") from error
    probe = f'printf "\\n{PATH_SENTINEL}%s" "$PATH"'
    paths = [os.defpath]
    with tempfile.TemporaryDirectory() as home:
        for argv, env in (([shell, "-lc", probe], {"PATH": BLIND_CHILD_PATH, "HOME": home}),
                          (["/bin/sh", "-c", probe], {}), ([shell, "-c", probe], {})):
            where = f"`{argv[0]} {argv[1]}`" + (" with an empty environment" if not env else "")
            try:
                # Profile output need not be UTF-8 (R2-4): it is decoded leniently and only the sentinel's tail is read.
                result = subprocess.run(argv, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                                        encoding="utf-8", errors="replace", timeout=30)
            except (OSError, subprocess.SubprocessError) as error:
                raise PathUnmeasured(f"{where}: {error}") from error
            if result.returncode != 0 or PATH_SENTINEL not in result.stdout:
                raise PathUnmeasured(f"{where} exited {result.returncode} without printing its PATH: "
                                     f"{result.stderr.strip()[-200:] or 'no output'}")
            paths.append(result.stdout.rsplit(PATH_SENTINEL, 1)[1])
    return os.pathsep.join(path for path in paths if path)


def blind_path_issue(path: str = None):
    """None when no BLIND_UNRESOLVABLE CLI resolves on a blind child's PATH, else the refusal naming each one that does:
    the audit relies on their not running by name. ``path`` defaults to BLIND_CHILD_PATH and what the login shell adds
    (login_shell_path); a login shell that cannot be measured is a refusal too."""
    if path is None:
        try:
            measured = login_shell_path()
        except PathUnmeasured as error:
            return (f"the PATH a blind child's commands can end up with could not be measured ({error}), so a blind "
                    "run is refused")
        path = os.pathsep.join((BLIND_CHILD_PATH, measured))
    directories = [d for d in path.split(os.pathsep) if d]
    found = [f"{name} ({where})" for name in BLIND_UNRESOLVABLE
             for where in [next((os.path.join(d, name) for d in directories if os.path.isfile(os.path.join(d, name))
                                 and os.access(os.path.join(d, name), os.X_OK)), None)] if where]
    return (f"a blind child's PATH ({path}) resolves {', '.join(found)}; the blind audit relies on those CLIs not "
            "running by name, so a blind run is refused on this host") if found else None


def child_executable(name: str):
    """The absolute path the caller's PATH resolves ``name`` to, for a blind child whose own PATH cannot."""
    return name if os.path.isabs(name) else shutil.which(name)


SHELL_INTERPRETERS = frozenset({"sh", "bash", "dash", "zsh", "ksh", "mksh", "ash", "fish"})


def launcher_shebang(program: str) -> tuple[list, bool]:
    """The shared interpreter words and whether they follow env, using the lane's existing env/-S subset.
    GNU coreutils env invocation and Linux execve(2), Interpreter scripts, describe the native grammar."""
    try:
        with open(program, "rb") as handle:
            first = handle.readline(256)
    except OSError:
        return [], False
    words = first[2:].decode("utf-8", errors="replace").split() if first.startswith(b"#!") else []
    if len(words) >= 2 and os.path.basename(words[0]) == "env":
        # Only env's own -S; an interpreter's -S (python -S) stays (R2-6).
        return (words[2:] if words[1] == "-S" else words[1:]), True
    return words, False


def codex_launch_issue(name: str = "codex"):
    """Refuse absolute-shell launchers as before, and env-shell launchers only when a blind --version probe exits
    126/127. The telemetry identity launcher can exec an absolute binary; asdf shims run a tool by name.
    Other probe failures are console diagnostics, not refusal (PR #216 custody F1; blind_path_issue pattern)."""
    program = child_executable(name)
    if program is None:
        return None
    words, env_style = launcher_shebang(program)
    if not words or os.path.basename(words[0]) not in SHELL_INTERPRETERS:
        return None
    if not env_style:
        return (f"{program} is a shell-script launcher ({' '.join(words)}); it runs its tools by name, which a blind "
                f"child's PATH ({BLIND_CHILD_PATH}) does not resolve, so a blind run is refused. Put a native codex "
                "binary or an env-style launcher (#!/usr/bin/env node) first on PATH")
    try:
        with tempfile.TemporaryDirectory(prefix="codex-launch-probe-") as scratch:
            home = Path(scratch) / "codex-home"
            home.mkdir()
            env = child_env(home)
            Path(env["HOME"]).mkdir()
            Path(env["TMPDIR"]).mkdir()
            result = subprocess.run(blind_child_argv([program, "--version"]), env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        detail = "timed out after 5 seconds" if isinstance(exc, subprocess.TimeoutExpired) else str(exc)
        print(f"codex_lane: {program} launcher --version probe {detail}; continuing", file=sys.stderr)
        return None
    if result.returncode:
        lines = [line for line in (result.stderr or "").splitlines() if line.strip()]
        detail = lines[-1][-400:] if lines else "no stderr"
        message = (f"{program} is a shell-script launcher ({' '.join(words)}); --version exited {result.returncode} "
                   f"under the blind child's PATH ({BLIND_CHILD_PATH}): {detail}")
        if result.returncode in (126, 127):
            return message + "; a blind run is refused"
        print(f"codex_lane: {message}; continuing", file=sys.stderr)
    return None


def child_failure_detail(result: dict) -> str:
    """The last lines of a failed child's stderr, for the operator's console only: recorded reasons stay fixed text,
    since stderr can carry host paths (independent review of #206, R2-2)."""
    lines = [line for line in (result.get("stderr") or "").splitlines()
             if line.strip() and not line.startswith("Reading additional input from stdin")]
    return " | ".join(lines[-3:])[-400:]


def blind_child_argv(cmd: list) -> list:
    """``cmd`` as a blind child runs it: its program by the absolute path the caller's PATH resolves, and, when that
    program is a ``#!/usr/bin/env <interpreter>`` script (npm's codex launcher: ``#!/usr/bin/env node``, installed by
    adoption/bootstrap-macos.sh), preceded by the interpreter the caller's PATH resolves, since the child's own PATH
    (BLIND_CHILD_PATH) has no node (Codex review of #206, P1). An unresolved program is left for Popen to report."""
    program = child_executable(cmd[0])
    if program is None:
        return list(cmd)
    words, env_style = launcher_shebang(program)
    if env_style:
        interpreter = shutil.which(words[0]) if words and not words[0].startswith("-") else None
        if interpreter:
            return [interpreter, *words[1:], program, *cmd[1:]]
    return [program, *cmd[1:]]


def child_home(codex_home: Path) -> Path:
    """The empty HOME a blind child runs with, inside its run-scoped CODEX_HOME (isolated_codex_home)."""
    return Path(codex_home) / "home"


def run_attempt(cmd: list, timeout: float, *, provider="native", omniroute_base_url=None) -> dict:
    """Run one child to completion or ``timeout``; after a stop (STOP) none starts and ``stopped`` is true."""
    started = time.monotonic()
    if STOP.is_set():
        return {"exit_code": None, "stdout": "", "stderr": "", "elapsed": 0.0, "timed_out": False, "stopped": True}
    if provider == "omniroute" and CHILD_CODEX_HOME is None:
        raise CodexHomeRefused("OmniRoute requires a fresh keyless Codex home")
    env = child_env(CHILD_CODEX_HOME, provider=provider, omniroute_base_url=omniroute_base_url) \
        if CHILD_CODEX_HOME is not None else None
    # A blind child's PATH has no codex (BLIND_CHILD_PATH), so it runs the one the caller's PATH resolves.
    cmd = blind_child_argv(cmd) if env is not None else cmd
    # The in-use lock rides along (round 7, ISO-R7-2); no stdin (round 5, ISO-R5-3): codex exec appends a
    # non-terminal stdin to the prompt and waits for its end.
    pass_fds = (IN_USE_HANDLE.fileno(),) if IN_USE_HANDLE is not None else ()
    child = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env=env, pass_fds=pass_fds)
    with _LIVE_LOCK:
        _LIVE_CHILDREN.add(child)
    if STOP.is_set():
        child.terminate()
    timed_out = False
    try:
        stdout, stderr = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        child.kill()
        stdout, stderr = child.communicate()
        timed_out = True
    finally:
        with _LIVE_LOCK:
            _LIVE_CHILDREN.discard(child)
    return {"exit_code": None if timed_out else child.returncode, "stdout": stdout or "", "stderr": stderr or "",
            "elapsed": time.monotonic() - started, "timed_out": timed_out, "stopped": STOP.is_set()}


def parse_events(stdout_text: str) -> list:
    """One JSON object per non-blank line; a line that fails to parse (e.g.
    truncated mid-write by a killed timeout) is dropped rather than raising --
    the event stream is diagnostic, not a contract this script enforces."""
    events = []
    for line in stdout_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _find_first_str(node, key: str):
    if isinstance(node, dict):
        value = node.get(key)
        if isinstance(value, str) and value:
            return value
        for child in node.values():
            found = _find_first_str(child, key)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_first_str(item, key)
            if found is not None:
                return found
    return None


def usage_row_belongs_to_layer(row, expected_layer: str) -> bool:
    """The native usage writer's identity field, shared by post-run supervisors."""
    return isinstance(row, dict) and row.get("layer") == expected_layer


def layer_usage_suffix(prefix: bytes, current: bytes, expected_layer: str) -> list[dict]:
    """Validate append-only usage capture and select the newly completed native layer rows.

    A supervisor must check native usage rows, rather than the lane return schema's layer_id field.
    Partial/malformed JSON or another layer cannot silently pass collection. No model or filesystem call.
    """
    if not isinstance(prefix, bytes) or not isinstance(current, bytes) or not current.startswith(prefix):
        raise ValueError("original usage prefix changed")
    if prefix and not prefix.endswith(b"\n") or current and not current.endswith(b"\n"):
        raise ValueError("incomplete native usage row")
    try:
        rows = [json.loads(line) for line in current[len(prefix):].splitlines() if line.strip()]
    except (ValueError, UnicodeError) as error:
        raise ValueError("malformed native usage row") from error
    if any(not usage_row_belongs_to_layer(row, expected_layer) for row in rows):
        raise ValueError("native usage rows do not belong to the selected layer")
    return rows


def _find_usage(node):
    if isinstance(node, dict):
        matched = {key: node[key] for key in USAGE_KEYS if key in node}
        if matched:
            return matched
        for child in node.values():
            found = _find_usage(child)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_usage(item)
            if found:
                return found
    return None


def extract_events_summary(events: list):
    """Model name and usage/token fields found in the *last* events that
    carry them (later events -- e.g. ``turn.completed`` -- override earlier
    ones), tolerant of any event shape. Returns ``(model_name_or_None,
    usage_dict_possibly_empty)``; never raises."""
    model_name = None
    usage: dict = {}
    for event in events:
        found_model = _find_first_str(event, "model")
        if found_model:
            model_name = found_model
        found_usage = _find_usage(event)
        if found_usage:
            usage = found_usage
    return model_name, usage


LANE_FAMILY = "openai"


# The repository roots the blind-adjudicator role refuses (agent-lab PR #40), enforced by every blind tool:
# blind_checkout --export, both lane runners and adjudicate (round-2 review; independent review of #145, O3).
MIN_ROOT_COMPONENTS = 4
REFUSED_ROOTS = ("/", "/home", "/tmp", "/Users", "/root")


def root_issue(path) -> str:
    """None when ``path`` is a repository root blind-adjudicator accepts, else why not: it must be absolute with
    no ``.``/``..`` segment, ``~``, ``$`` or wildcard, and not ``/``, ``/home``, ``/tmp``, a home directory
    (``/home/<name>``, ``/Users/<name>``, ``/root`` or this user's home) or a path of fewer than four
    components."""
    text = str(path)
    parts = [part for part in text.split("/") if part]
    if not text.startswith("/"):
        return f"{text!r} is not an absolute path"
    if any(part in (".", "..") for part in parts) or any(char in text for char in "~$*?["):
        return f"{text!r} has a '.', '..', '~', '$' or wildcard segment"
    if any(char.isspace() for char in text):
        # Path scrubbing tokenizes on whitespace, so a root with a space could not be recognized in the returns.
        return f"{text!r} contains whitespace"
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", text):
        # Parentheses, quotes, backticks and the other tokenizer delimiters would split the root in scrubbing.
        return f"{text!r} contains a character outside [A-Za-z0-9._/-]"
    home = str(Path.home()).rstrip("/")
    if (text.rstrip("/") or "/") in REFUSED_ROOTS or text.rstrip("/") == home or (
            len(parts) == 2 and parts[0] in ("home", "Users")):
        return f"{text!r} is /, /home, /tmp or a home directory"
    if len(parts) < MIN_ROOT_COMPONENTS:
        return f"{text!r} has {len(parts)} path components; a repository root needs at least {MIN_ROOT_COMPONENTS}"
    return None


def tree_sha256(repo: Path, allow_escaping_links: bool = False) -> str:
    """A digest of the evidence repository's content: every regular file's relative path and sha256, sorted,
    and each retained symlink's text. The packet names evidence paths, not their bytes, so a return (and an
    adjudication judgment) is bound to the tree it read."""
    repo = Path(repo)
    if not repo.is_dir():
        # An empty walk would hash to a valid-looking digest (Codex review of #145).
        raise NotADirectoryError(f"evidence repository {repo} is not an existing directory")
    digest = hashlib.sha256()
    root = repo.resolve()
    for path in sorted(repo.rglob("*")):
        relative = path.relative_to(repo).as_posix()
        if path.is_symlink():
            target = os.readlink(path)
            try:
                # A loop is found by stat (ELOOP) on every Python version: 3.13's resolve() no longer raises on one
                # (delta review of #145). A dangling internal link (ENOENT) is hashed by its text.
                os.stat(path)
            except OSError as error:
                if error.errno == errno.ELOOP:
                    if not allow_escaping_links:
                        raise ValueError(f"evidence repository {repo} has a symlink loop: {relative}")
                    # A non-blind run hashes a looping link by its text without resolving it: 3.12's resolve()
                    # raises RuntimeError on a loop (independent review of #145, R4-REG-4).
                    digest.update(f"{relative}\0->{target}\n".encode("utf-8"))
                    continue
            resolved = (path.parent / target).resolve(strict=False)
            if not allow_escaping_links and (os.path.isabs(target)
                                             or not (resolved == root or root in resolved.parents)):
                # Content behind an escaping link could change under an unchanged digest (Codex review of #145);
                # blind_checkout --export removes such links, so one here means the tree is not a blind export.
                raise ValueError(f"evidence repository {repo} has a symlink leaving it: {relative} -> {target}")
            # A retained internal link: its text is part of the tree (the target file is hashed on its own).
            digest.update(f"{relative}\0->{target}\n".encode("utf-8"))
        elif path.is_file():
            digest.update(f"{relative}\0{sha256_file(path)}\n".encode("utf-8"))
        elif not path.is_dir() and not allow_escaping_links:
            # A FIFO, socket or device is not evidence and would otherwise be skipped silently (cross-family
            # review of #145). A deliberately non-blind run may hold git's fsmonitor socket, so it is not refused.
            raise ValueError(f"evidence repository {repo} has a non-regular entry: {relative}")
    return digest.hexdigest()


def lane_provenance(prompt_path: Path, repo: Path = None, allow_escaping_links: bool = False,
                    *, provider="native", omniroute_base_url=None) -> dict:
    """What produced a return: this runner file's and the filled prompt template's sha256, and (given
    ``repo``) the digest of the evidence tree the lane read, so a resume against another export reruns
    (Codex review of #145)."""
    provenance = {"codex_lane_py_sha256": sha256_file(Path(__file__).resolve()),
                  "prompt_sha256": sha256_file(Path(prompt_path))}
    if provider == "omniroute":
        provenance["provider"] = provider
        provenance["provider_base_url"] = omniroute_endpoint(omniroute_base_url)
        provenance["pass_through"] = OMNIROUTE_PASS_THROUGH
    if repo is not None:
        provenance["repo_tree_sha256"] = tree_sha256(Path(repo), allow_escaping_links)
    return provenance


def finalize_lane_return(data: dict, catalog: str, layer_id: str, packet_sha256: str,
                          event_model_name, effort: str, provenance: dict = None,
                          configured_model: str = None) -> dict:
    data = dict(data)
    data["lane"] = LANE
    if not data.get("packet_sha256"):
        data["packet_sha256"] = packet_sha256
    # Runner-owned: the model identity is what this runner configured or observed in the event
    # stream, never the model's self-declared name, effort, family or provenance.
    data["model"] = {"name": configured_model or event_model_name or "unknown", "effort": effort,
                     "family": LANE_FAMILY}
    if provenance is not None:
        data["provenance"] = dict(provenance)
    return data


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2] if len(__doc__.splitlines()) > 2 else __doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--layers", default=None,
                         help="Comma-separated layer ids to run (matched across every catalog); default: all.")
    parser.add_argument("--effort", default=DEFAULT_EFFORT,
                        help="model_reasoning_effort passed via -c (default max, the standing GPT-6 lane setting; a return made at another effort is not reused).")
    parser.add_argument("--model", default=None,
                        help="Model passed to codex exec -m and recorded as the return's model.name "
                             "(native default: Codex's configured model from events; OmniRoute default: "
                             "gpt-6.1-sol on the pinned cx route).")
    parser.add_argument("--provider", choices=("native", "omniroute"), default="native",
                        help="Explicit transport opt-in; native stays the default. OmniRoute needs a reviewed "
                             "keyless loopback route and does not by itself prove upstream prompt preservation.")
    parser.add_argument("--omniroute-base-url", default=None,
                        help="Keyless loopback /v1 endpoint for --provider omniroute; defaults to "
                             "OMNIROUTE_BASE_URL or http://127.0.0.1:21128/v1.")
    parser.add_argument("--jobs", type=int, default=1, help="Concurrent codex exec invocations.")
    parser.add_argument("--dry-run", action="store_true", help="Print the command per pending layer; write nothing.")
    parser.add_argument("--allow-git-history", action="store_true",
                        help="Run against a --repo that has .git. A blind wave never does: git history recovers "
                             "every label blind_checkout.py strips, so give the lanes its --export copy.")
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT,
                         help="Override the lane prompt template path (default: lane-prompt.md next to this script).")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA,
                         help="Override the JSON Schema path passed to --output-schema "
                              "(default: lane-return.schema.json next to this script).")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                         help="Per-attempt codex exec timeout in seconds (default: 900).")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.provider == "omniroute":
        try:
            args.omniroute_base_url = omniroute_endpoint(args.omniroute_base_url
                or os.environ.get(OMNIROUTE_BASE_URL_ENV) or DEFAULT_OMNIROUTE_BASE_URL)
        except ValueError as error:
            print(f"codex_lane: {error}", file=sys.stderr)
            return 2
        # The cx/ prefix selects gateway routing, not an OpenAI model identity.
        # Keep canonical model names in receipts and resume checks; build_command
        # adds the prefix only to the CLI's routed model.
        args.model = (args.model or DEFAULT_OMNIROUTE_MODEL).removeprefix("cx/")
        if not args.model or "/" in args.model:
            print("codex_lane: OmniRoute --model needs a bare model or its cx/ route spelling", file=sys.stderr)
            return 2
    elif args.omniroute_base_url is not None:
        print("codex_lane: --omniroute-base-url requires --provider omniroute", file=sys.stderr)
        return 2
    work_dir = args.work_dir.resolve()
    repo = args.repo.resolve()
    prompt_path = args.prompt
    schema_path = args.schema

    if not prompt_path.exists():
        print(f"codex_lane: prompt template not found: {prompt_path}", file=sys.stderr)
        return 2
    if not schema_path.exists():
        print(f"codex_lane: output schema not found: {schema_path}", file=sys.stderr)
        return 2
    template = prompt_path.read_text(encoding="utf-8")
    if not repo.is_dir():
        print(f"codex_lane: --repo {repo} is not an existing directory", file=sys.stderr)
        return 2
    if not args.allow_git_history:
        # The blind export must sit where the adjudicator role accepts it, checked as given and resolved (O3).
        for candidate in (Path(os.path.abspath(args.repo)), repo):
            issue = root_issue(candidate)
            if issue:
                print(f"codex_lane: --repo {issue}; place the blind export at least four directories deep (not /, "
                      "/home, /tmp or a home directory itself) and outside every repository", file=sys.stderr)
                return 2
    git_dirs = [str(path) for path in (repo, *repo.parents) if (path / ".git").exists()]
    if git_dirs and not args.allow_git_history:
        # git walks up from a subdirectory, so an export inside any repository still reaches history.
        print(f"codex_lane: {git_dirs[0]} has .git, whose history a child can read from {repo}; run the lane on a "
              "blind_checkout.py --export copy placed outside every repository, or pass --allow-git-history "
              "outside a blind wave", file=sys.stderr)
        return 2

    work_repos = [str(path) for path in (work_dir, *work_dir.parents) if (path / ".git").exists()]
    if work_repos and not args.allow_git_history:
        # WORK_DIR sits outside every repository, as the recipe says (independent review of #145, round 4, OPS-6).
        print(f"codex_lane: --work-dir {work_dir} is inside the git repository {work_repos[0]}; place it outside "
              "every repository", file=sys.stderr)
        return 2

    layers_filter = None
    if args.layers:
        layers_filter = {item.strip() for item in args.layers.split(",") if item.strip()}

    packets = discover_packets(work_dir, layers_filter)
    codex_dir = work_dir / "codex"
    events_dir = codex_dir / "events"
    usage_path = codex_dir / "usage.jsonl"

    global CHILD_CODEX_HOME
    try:
        # A deliberately non-blind run (--allow-git-history) may read a checkout whose ignored .venv links leave
        # it (re-review L2); a blind export never has such links.
        provenance = lane_provenance(prompt_path, repo, allow_escaping_links=args.allow_git_history,
                                    provider=args.provider, omniroute_base_url=args.omniroute_base_url)
    except ValueError as error:  # an escaping symlink: not a blind export
        print(f"codex_lane: {error}", file=sys.stderr)
        return 2
    blind = not args.allow_git_history
    isolated = blind or args.provider == "omniroute"
    audit_roots = [str(repo), str((work_dir / "packets").resolve())]
    pending = []
    for catalog, layer_id, packet_path in packets:
        packet_sha256 = sha256_file(packet_path)
        out_path = codex_dir / f"{catalog}__{layer_id}.json"
        # A blind return counts only with clean retained events (round 7, REG7-1/ISO-R7-1).
        if existing_output_is_valid(out_path, catalog, layer_id, packet_sha256, provenance, args.model,
                                    args.effort, audit_roots=audit_roots if blind else None):
            continue
        pending.append((catalog, layer_id, packet_path, packet_sha256, out_path))

    if isolated:
        # The home refusals create nothing, so they run before the dry run and the lock (round 6, ISO-R6-5).
        issue = codex_home_issue(work_dir, repo, provider=args.provider)
        if blind:
            issue = issue or blind_path_issue() or codex_launch_issue()
        if issue:
            print(f"codex_lane: {issue}", file=sys.stderr)
            return 2
    if args.dry_run:
        strict_display = codex_dir / "lane-return.codex-strict.schema.json"
        print(f"# --dry-run writes nothing; a real run first writes {strict_display}", file=sys.stderr)
        # A blind child's environment is printed with its command; the dry run creates no home (OPS-4).
        run_home = codex_home_base() / f"{codex_home_prefix(work_dir)}-<run>"
        if isolated:
            print(f"# a real run creates a fresh {run_home} (mkdtemp) and runs each child with only this environment",
                  file=sys.stderr)
        # Never an API key value on stdout: the printed environment omits the key variables.
        env_prefix = ["env", "-i", *(f"{key}={redact_userinfo(value)}" for key, value in child_env(
            run_home, provider=args.provider, omniroute_base_url=args.omniroute_base_url).items()
            if key not in ("CODEX_API_KEY", "OPENAI_API_KEY"))] if isolated else []
        for catalog, layer_id, packet_path, packet_sha256, out_path in pending:
            prompt_text = fill_prompt(template, packet_path.resolve(), repo)
            tmp_out = codex_dir / f"{catalog}__{layer_id}.out.tmp"
            cmd = build_command(repo, strict_display, tmp_out, args.effort, prompt_text, args.model, ISOLATION_ARGS,
                                provider=args.provider, omniroute_base_url=args.omniroute_base_url)
            # The child's PATH has no codex, so the printed command names the one this PATH resolves.
            print(shlex.join(env_prefix + (blind_child_argv(cmd) if isolated else cmd)))
        return 0

    if pending and shutil.which("codex") is None:
        # A missing CLI is a setup error, not a lane failure: say so instead of a traceback.
        print("codex_lane: the codex CLI is not on PATH; install it and sign in natively "
              "(see adoption/) before running the Codex lane", file=sys.stderr)
        return 2
    if pending and blind:
        issue = audit_analysis_issue()
        if issue:
            print(f"codex_lane: {issue}", file=sys.stderr)
            return 2
    with contextlib.ExitStack() as stack:
        if pending:
            try:
                # The work dir's own lock, then the homes' base lock, both shared by the two runners (round 6,
                # ISO-R6-1; round 7, REG7-2/ISO-R7-4).
                stack.enter_context(exclusive_run_lock(work_run_lock(work_dir)))
                stack.enter_context(exclusive_run_lock(codex_home_lock(work_dir)))
            except RunLocked as error:
                print(f"codex_lane: {error}", file=sys.stderr)
                return 2
            stack.enter_context(terminate_on_signal())
            sweep_stale_links(work_dir)
        if pending and isolated:
            # Blind children never load the user's global Codex instructions or user skills (isolated_codex_home),
            # set up only once every refusal has passed, the run holds its lock and something is to run (R4-REG-3).
            try:
                CHILD_CODEX_HOME = isolated_codex_home(work_dir, repo, provider=args.provider)
            except CodexHomeRefused as error:
                print(f"codex_lane: {error}", file=sys.stderr)
                return 2
        try:
            return run_pending(args, work_dir, repo, template, schema_path, codex_dir, events_dir, usage_path,
                               pending, provenance)
        finally:
            release_codex_home(CHILD_CODEX_HOME)
            CHILD_CODEX_HOME = None


def _write_failure_snapshot(path, failures, kept=(), keep_empty=True):
    """Publish a complete failure snapshot without exposing a partially written JSON file.

    CC's 2026-10-10 adjudication cites native main 9d4c00cd, codex_lane.py:1538-1556:
    the former end-only write lost earlier layer failures on interruption. Adopt same-directory
    tempfile + os.replace (CPython v3.13.16 Doc/library/os.rst:2755-2760: atomic on success).
    """
    recorded = sorted(set(failures) | set(kept))
    if not recorded and not keep_empty:
        path.unlink(missing_ok=True)
        return
    text = json.dumps({"lane": LANE, "failures": [
        {"catalog": catalog, "layer_id": layer_id, "reason": reason}
        for catalog, layer_id, reason in recorded]}, indent=1, sort_keys=True) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run_pending(args, work_dir, repo, template, schema_path, codex_dir, events_dir, usage_path, pending,
                provenance) -> int:
    events_dir.mkdir(parents=True, exist_ok=True)
    strict_schema_path = write_strict_schema(schema_path, codex_dir)
    usage_lock = threading.Lock()
    audit_lock = threading.Lock()
    failures_lock = threading.Lock()
    failures: list = []
    failures_path = codex_dir / FAILURES_NAME
    # Preserve failures outside --layers before replacing the initial snapshot, rather than
    # waiting until the end (native main 9d4c00cd:1538-1556, CC 2026-10-10 follow-up).
    kept = []
    if args.layers and failures_path.is_file():
        selected = {item.strip() for item in args.layers.split(",") if item.strip()}
        try:
            earlier = json.loads(failures_path.read_text(encoding="utf-8")).get("failures") or []
        except (ValueError, AttributeError):
            earlier = []
        kept = [(entry.get("catalog"), entry.get("layer_id"), entry.get("reason")) for entry in earlier
                if isinstance(entry, dict) and entry.get("layer_id") not in selected
                and f"{entry.get('catalog')}__{entry.get('layer_id')}" not in selected]
    _write_failure_snapshot(failures_path, failures, kept)

    def record_failure(catalog, layer_id, reason):
        with failures_lock:
            failures.append((catalog, layer_id, reason))
            _write_failure_snapshot(failures_path, failures, kept)

    blind = not args.allow_git_history
    roots = [str(repo), str((work_dir / "packets").resolve())]
    # A non-blind child inherits the caller's PATH, where the retrieval CLIs may resolve (BLIND_UNRESOLVABLE).
    tools = AUDIT_TOOLS if blind else AUDIT_TOOLS + BLIND_UNRESOLVABLE
    audit_path = codex_dir / AUDIT_NAME
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.is_file() else {}
    except ValueError:
        audit = {}
    audit_layers = audit.get("layers") if isinstance(audit.get("layers"), dict) else {}

    def record_audit(name, report):
        # Written as each layer is audited, so an interrupted run keeps what it audited.
        with audit_lock:
            audit_layers[name] = report
            audit_path.write_text(json.dumps({"schema_version": 1, "allowed_roots": roots, "layers": audit_layers},
                                             indent=1, sort_keys=True) + "\n", encoding="utf-8")

    def process(item):
        catalog, layer_id, packet_path, packet_sha256, out_path = item
        name = f"{catalog}__{layer_id}"
        prompt_text = fill_prompt(template, packet_path.resolve(), repo)
        tmp_out = codex_dir / f"{name}.out.tmp"
        cmd = build_command(repo, strict_schema_path.resolve(), tmp_out, args.effort, prompt_text, args.model,
                            ISOLATION_ARGS, provider=args.provider, omniroute_base_url=args.omniroute_base_url)
        events_path = events_dir / f"{name}.jsonl"
        if STOP.is_set():
            return
        # The layer is pending, so its old return does not count: remove it before its events are rewritten, so an
        # interrupted rerun never leaves it beside a truncated, clean-looking stream (round 8, NEW-1).
        out_path.unlink(missing_ok=True)
        events_path.write_text("", encoding="utf-8")

        succeeded = False
        last_model_name = None
        last_failure = "no attempt ran"
        for attempt in (1, 2):
            # Clear any stale out.tmp left by a killed prior run (SIGKILL,
            # Ctrl-C, OOM) before launching this attempt, so a codex exec
            # that exits 0 without writing -o is never misread as having
            # produced a stale earlier attempt's (or run's) output.
            tmp_out.unlink(missing_ok=True)
            if args.provider == "omniroute":
                result = run_attempt(cmd, args.timeout, provider=args.provider,
                                     omniroute_base_url=args.omniroute_base_url)
            else:
                result = run_attempt(cmd, args.timeout)
            if result.get("stopped") and not result["stdout"]:
                return  # stopped before a child ran
            events = parse_events(result["stdout"])
            with events_path.open("a", encoding="utf-8") as handle:
                for line in result["stdout"].splitlines():
                    if line.strip():
                        handle.write(line + "\n")

            model_name, usage = extract_events_summary(events)
            if model_name:
                last_model_name = model_name

            usage_row = {
                "catalog": catalog, "layer": layer_id, "attempt": attempt,
                "exit_code": result["exit_code"], "timed_out": result["timed_out"],
                "model": model_name, "seconds": round(result["elapsed"], 3),
            }
            if args.provider == "omniroute":
                usage_row["provider"] = args.provider
                usage_row["provider_base_url"] = args.omniroute_base_url
                usage_row["pass_through"] = OMNIROUTE_PASS_THROUGH
            usage_row.update(usage)
            with usage_lock, usage_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(usage_row, sort_keys=True) + "\n")
            if STOP.is_set():
                # After a stop nothing is promoted and no retry starts (round 7, REG7-1/ISO-R7-3).
                tmp_out.unlink(missing_ok=True)
                return

            if result["timed_out"] or result["exit_code"] != 0:
                last_failure = "timed out" if result["timed_out"] else f"codex exec exited {result['exit_code']}"
                detail = child_failure_detail(result)
                if detail:
                    print(f"codex_lane: {name} attempt {attempt}: {last_failure}: {detail}", file=sys.stderr)
                tmp_out.unlink(missing_ok=True)
                continue
            if not tmp_out.exists():
                last_failure = "codex exec wrote no output file"
                continue
            try:
                data = load_json(tmp_out)
            except (json.JSONDecodeError, UnicodeDecodeError):
                last_failure = "the output file was not valid JSON"
                tmp_out.unlink(missing_ok=True)
                continue
            if not isinstance(data, dict):
                last_failure = "the output was not a JSON object"
                tmp_out.unlink(missing_ok=True)
                continue

            final = finalize_lane_return(data, catalog, layer_id, packet_sha256, last_model_name, args.effort,
                                         provenance, configured_model=args.model)
            tmp_out.unlink(missing_ok=True)
            # This layer's own audit, before its return is written (round 7, REG7-1/ISO-R7-1): in a blind run a
            # flagged layer (a read outside the export and packets, web search or an MCP tool) is void, as an
            # adjudication judgment is, since it may have read the packet keys or another lane's return (Codex review
            # of #145). Its return is kept only as <name>.json.audit-flagged, and the layer is recorded as failed.
            report = blind_audit(events_path, roots, tools)
            record_audit(name, report)
            if blind and audit_is_flagged(report):
                out_path.unlink(missing_ok=True)
                out_path.with_name(out_path.name + ".audit-flagged").write_text(
                    json.dumps(final, indent=1, sort_keys=True) + "\n", encoding="utf-8")
                last_failure = None
                record_failure(catalog, layer_id, "the blind audit flagged this layer's calls (web, MCP or a read "
                                                "outside the export and packets)")
                return
            if STOP.is_set():
                return
            out_path.write_text(json.dumps(final, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            succeeded = True
            break

        if not succeeded:
            # A stale return (e.g. one rejected for an older packet hash) must
            # not survive, so record_verdicts.py records this `failed` reason.
            record_audit(name, blind_audit(events_path, roots, tools))
            out_path.unlink(missing_ok=True)
            record_failure(catalog, layer_id, f"failed after retry: {last_failure}")

    if args.jobs > 1:
        executor = ThreadPoolExecutor(max_workers=args.jobs)
        try:
            list(executor.map(process, pending))
        finally:
            # A stop cancels the queued layers; the in-flight ones return at once (round 7, ISO-R7-3).
            executor.shutdown(wait=True, cancel_futures=True)
    else:
        for item in pending:
            process(item)

    try:
        tree_after = tree_sha256(repo, allow_escaping_links=args.allow_git_history)
    except ValueError:
        tree_after = None
    if pending and tree_after != provenance["repo_tree_sha256"]:
        # The evidence changed while the children read it (Codex review of #145): no return of this run is
        # bound to one tree, so each is set aside (kept for inspection, never resumed or sealed).
        for catalog, layer_id, _packet_path, _packet_sha256, out_path in pending:
            if out_path.is_file():
                out_path.replace(out_path.with_name(out_path.name + ".tree-changed"))
            record_failure(catalog, layer_id, "the evidence tree changed during the run; rerun on a fixed export")

    flagged = sorted(name for name, entry in audit_layers.items() if isinstance(entry, dict) and audit_is_flagged(entry))
    if flagged:
        print(f"codex_lane: blind audit flags {len(flagged)} layer(s) for review in {audit_path}: "
              + ", ".join(flagged), file=sys.stderr)

    with failures_lock:
        _write_failure_snapshot(failures_path, failures, kept, keep_empty=STOP.is_set())
    for catalog, layer_id, reason in sorted(failures):
        print(f"codex_lane: {catalog}__{layer_id}: {reason}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
