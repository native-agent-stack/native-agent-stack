#!/usr/bin/env python3
"""Render and launch isolated *trial* Pi/OpenCode profiles from canonical inputs.

Vendor mechanisms (not a replacement model loop):
earendil-works/pi@04566631:packages/coding-agent/docs/configuration.md:9,
docs/models.md:21, docs/mcp.md:104, docs/cli.md:47, docs/prompt-templates.md:51.
anomalyco/opencode@53d1eabb:packages/web/src/content/docs/{config,providers,
agents,mcp-servers,skills}.mdx; current mirror 4d9678a7 retains the v1 contract.
RTK owns shell rewriting; native MCP, model transports and sessions stay native.
All writes are scoped to new private profile roots or new launcher/fragment files.
No live credential/auth/config store is read, copied, hashed or published.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import uuid
import stat
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ("pi-claude", "pi-gpt", "opencode-claude", "opencode-gpt")
ROLES = ("evidence-reviewer", "security-reviewer", "stack-researcher", "source-scout",
         "stack-verifier", "isolated-builder")
CLAUDE_MODEL = "claude-opus-5-5"
GPT_MODEL = "cx/gpt-6.1-sol"
GATEWAY = "http://127.0.0.1:21128/v1"
SUPERPOWERS = "bb92a77741419a4ab5f06e711a283343f1ada0c3"
PI_OTEL = "npm:@b1tank/pi-otel@0.5.0"  # b1tank/pi-otel@3cd674533a8d24c9b8a2a6a94072eec25466e128
ROLE_SCOPES = {
    "builder": ("isolated-builder", ["test-driven-development", "writing-plans", "executing-plans",
                                    "using-git-worktrees", "finishing-a-development-branch"]),
    "reviewer": ("evidence-reviewer", ["requesting-code-review", "receiving-code-review", "verification-before-completion"]),
    "auditor": ("security-reviewer", ["systematic-debugging", "verification-before-completion"]),
    "researcher": ("stack-researcher", []),
}
ROLE_VERDICT = (
    "\nFor a review, write the CC verdict record: separate BLOCKERS from FOLLOW-UPS, "
    "cite the reviewed head and reproduced source evidence; the last line must be "
    "Verdict: <word> at <head8>.\n"
)


class ProfileError(ValueError):
    pass


def profile_name(value):
    return value.removeprefix("ns-")


def module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def private_write(path: Path, text: str, mode=0o600):
    """Exclusive creation: an existing native profile is never replaced."""
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


def utc() -> str:
    return subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], text=True).strip()


def owned_destination(path: Path):
    """Refuse symlink traversal and protected client roots before any write."""
    path = path.absolute()
    protected = [Path.home() / name for name in (".codex", ".claude", ".agents", ".pi")]
    protected += [Path.home() / ".config/opencode"]
    if any(path == root or path.is_relative_to(root) for root in protected):
        raise ProfileError("protected native root")
    if any(parent.is_symlink() for parent in [path, *path.parents]):
        raise ProfileError("symlink in destination")
    return path


def native_name(value: str, runtime="pi", *, pattern=False) -> str:
    # OpenCode 53d1eabb mcp/catalog.ts:117 retains hyphens. Role wildcard
    # grants must remain patterns rather than being converted to underscores.
    allowed = r"a-zA-Z0-9_" + (r"\-" if runtime == "opencode" else "")
    if pattern:
        allowed += r"*?"
    return re.sub("[^" + allowed + "]", "_", value)


def role_source(name: str) -> tuple[dict, str]:
    source = ROOT / "adoption/agents/claude" / (name + ".md")
    pieces = source.read_text().split("---", 2)
    if len(pieces) != 3:
        raise ProfileError("role lacks YAML frontmatter")
    metadata = yaml.safe_load(pieces[1])
    return metadata, pieces[2].strip() + "\n" + (ROLE_VERDICT if "reviewer" in name else "")


def granted_tools(metadata: dict, runtime: str) -> tuple[list[str], list[str]]:
    """Translate only known exact grants; an absent equivalent is omitted.

    Pi docs/mcp.md:77 names tools mcp__<server>__<tool>. OpenCode's native
    MCP names are sanitized <server>_<tool> (53d1eabb, src/mcp/index.ts).
    Neither runtime gains a wildcard MCP grant from a discovery/Search tool.
    """
    builtins = {"Read": "read", "Grep": "grep", "Glob": "find" if runtime == "pi" else "glob",
                "Bash": "bash", "Edit": "edit", "Write": "write" if runtime == "pi" else "edit",
                "WebSearch": "websearch" if runtime == "opencode" else None,
                "Skill": "skill" if runtime == "opencode" else None}
    permitted, omitted = set(), []
    raw = metadata.get("tools", "")
    tools = raw if isinstance(raw, list) else [v.strip() for v in raw.split(",")]
    for tool in tools:
        if tool in builtins and builtins[tool]:
            permitted.add(builtins[tool])
        elif tool.startswith("mcp__"):
            parts = tool.split("__", 2)
            if len(parts) != 3:
                raise ProfileError("malformed role MCP grant")
            server, action = parts[1:]
            # Claude plugin prefixes identify the same canonical MCP server.
            if server.startswith("plugin_context-mode"):
                server = "context-mode"
            prefix = "mcp__" + native_name(server) + "__" if runtime == "pi" else native_name(server, runtime) + "_"
            permitted.add(prefix + native_name(action, runtime, pattern=True))
        else:
            omitted.append(tool)
    return sorted(permitted), sorted(omitted)


def canonical_servers(home: Path, eco_root: Path, templates: list[Path], *, require_token_layer=True) -> dict:
    """Reuse the reviewed Claude renderer; no second authored server list."""
    install = module("runtime_claude_install", ROOT / "tools/adoption/install_claude_profile.py")
    servers = {}
    for path in templates:
        rendered = install.render_servers(json.loads(path.read_text()), home, eco_root)
        for name, server in rendered.items():
            if name in servers and servers[name] != server:
                raise ProfileError("conflicting canonical MCP definitions")
            if server.get("type", "stdio") not in {"stdio", "http", "streamable-http"}:
                raise ProfileError("unsupported MCP transport")
            servers[name] = server
    if require_token_layer and "context-mode" not in servers:
        raise ProfileError("canonical templates must include Context Mode")
    return servers


def render_wsl_mcp(home: Path, eco_root: Path) -> dict:
    """Use the existing WSL source, additions and wiring map without live config reads.

    Same analyse/render APIs as new_wsl_client_config --render. The public WSL
    host template supplies endpoints; only HOME/ECO_ROOT are task values.
    """
    sys.path.insert(0, str(ROOT / "tools/adoption"))
    import new_wsl_client_config as wiring
    results, manifest, plan, errors, _ = wiring.analyse(ROOT, authorization=False)
    if errors:
        raise ProfileError("canonical WSL MCP wiring check failed")
    host = json.loads((ROOT / "adoption/templates/wsl/host.new-distro.json.template").read_text())
    values = {key: value.replace("${WSL_USER}", home.name) for key, value in host.items()}
    values.update(HOME=str(home), ECO_ROOT=str(eco_root), XDG_RUNTIME_DIR=f"/run/user/{os.getuid()}",
                  OTEL_ENDPOINT=f"127.0.0.1:{plan['ports']['collector_http_port']}",
                  CODEX_MODEL=plan["codex_model"])
    files = wiring.render(ROOT, results, plan, values, manifest)
    install = module("runtime_claude_install", ROOT / "tools/adoption/install_claude_profile.py")
    return install.render_servers(json.loads(files["mcp-servers.json"]), home, eco_root)


def opencode_mcp(servers: dict) -> dict:
    converted = {}
    for name, server in servers.items():
        if server.get("type", "stdio") == "stdio":
            converted[name] = {"type": "local", "command": [server["command"], *server.get("args", [])],
                               "environment": server.get("env", {}), "enabled": True, "timeout": 120000}
            if server.get("cwd"):
                converted[name]["cwd"] = server["cwd"]
        else:
            converted[name] = {"type": "remote", "url": server["url"],
                               "headers": server.get("headers", {}), "oauth": False,
                               "enabled": True, "timeout": 120000}
    return converted


def pi_models(route: str) -> dict:
    if route == "claude":
        return {"providers": {"anthropic": {
            "headers": {"x-client-request-id": "${NS_RUNTIME_REQUEST_ID}"},
            "modelOverrides": {CLAUDE_MODEL: {"maxTokens": 8192}}}}}
    return {"providers": {"omniroute": {
        "baseUrl": GATEWAY, "api": "openai-responses", "apiKey": "local",
        "headers": {"x-omniroute-session-id": "${NS_RUNTIME_REQUEST_ID}"},
        "models": [{"id": GPT_MODEL, "name": "OmniRoute GPT-6.1 Sol", "reasoning": True,
                    "input": ["text"], "contextWindow": 258400, "maxTokens": 8192,
                    "cost": {"input": 2, "output": 10, "cacheRead": 0.1, "cacheWrite": 2.5}}],
    }}}


def opencode_provider(route: str) -> dict:
    if route == "claude":
        return {"anthropic": {"options": {"apiKey": "{env:ANTHROPIC_API_KEY}",
                "headers": {"x-client-request-id": "{env:NS_RUNTIME_REQUEST_ID}"}}}}
    return {"omniroute": {"npm": "@ai-sdk/openai", "name": "OmniRoute loopback",
            "options": {"baseURL": GATEWAY, "apiKey": "local",
                        "headers": {"x-omniroute-session-id": "{env:NS_RUNTIME_REQUEST_ID}"}},
            "models": {GPT_MODEL: {"name": "GPT-6.1 Sol", "reasoning": True,
                       "limit": {"context": 258400, "output": 8192},
                       "options": {"reasoningEffort": "high"},
                       "cost": {"input": 2, "output": 10, "cache_read": 0.1, "cache_write": 2.5}}}}}


def profile_environment(profile: str, state: Path, role_scope: str | None = None, auxiliary_root: Path | None = None) -> dict:
    root = state / profile
    if role_scope:
        root = root / "roles" / role_scope
    host = json.loads((ROOT / "adoption/templates/wsl/host.new-distro.json.template").read_text())
    endpoint = "http://" + host["OTEL_ENDPOINT"]
    telemetry = {"OTEL_EXPORTER_OTLP_ENDPOINT": endpoint,
                 "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                 "OTEL_RESOURCE_ATTRIBUTES": "service.name=ns-" + profile + ",deployment.environment=trial"}
    # XDG isolation also changes mise's config lookup. MCP subprocesses must
    # reach the already selected interpreter/node directly, not depend on a
    # host shim finding its now-hidden global config. No extra runtime install.
    native_bins = [str(Path(sys.executable).resolve().parent)]
    if auxiliary_root:
        native_bins += [str(auxiliary_root / name) for name in ("bin", "agent-browser/bin", "openresearch-0.2.15")]
    for binary in ("node", "uv", "rtk", "wt"):
        selected = shutil.which(binary)
        if selected:
            native_bins.append(str(Path(selected).resolve().parent))
    telemetry["PATH"] = os.pathsep.join(dict.fromkeys(native_bins)) + os.pathsep + os.environ.get("PATH", os.defpath)
    for signal in ("TRACES", "METRICS", "LOGS"):
        telemetry["OTEL_EXPORTER_OTLP_" + signal + "_ENDPOINT"] = endpoint + "/v1/" + signal.lower()
    if profile.startswith("pi-"):
        telemetry["PI_OTEL_ENABLED"] = "true"
        for flag in ("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "PI_OTEL_CAPTURE_CONTENT",
                     "OTEL_LOG_USER_PROMPTS", "OTEL_LOG_ASSISTANT_RESPONSES", "OTEL_LOG_TOOL_DETAILS",
                     "OTEL_LOG_TOOL_CONTENT", "PI_OTEL_CAPTURE_SYSTEM_INSTRUCTIONS", "PI_OTEL_CAPTURE_PROVIDER_PAYLOAD",
                     "PI_OTEL_CAPTURE_PROVIDER_HEADERS", "PI_OTEL_CAPTURE_OBSERVABILITY_TOOL_CONTENT"):
            telemetry[flag] = "false"
        return {**telemetry, "PI_CODING_AGENT_DIR": str(root / "agent")}
    return {**telemetry, "XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data"),
            "XDG_CACHE_HOME": str(root / "cache"), "XDG_STATE_HOME": str(root / "state"),
            "OPENCODE_CONFIG": str(root / "config/opencode/opencode.json"),
            "OPENCODE_CONFIG_DIR": str(root / "config/opencode"),
            "OPENCODE_DISABLE_CLAUDE_CODE_SKILLS": "1", "OPENCODE_DISABLE_MODELS_FETCH": "1"}


def render(profile: str, *, state: Path, home: Path, eco_root: Path, templates: list[Path],
           pi_bin: Path, opencode_bin: Path, rtk_source: Path, wsl=False, role_scope=None,
           auxiliary_root: Path | None = None, tier1_input: Path | None = None,
           skills_bin: Path | None = None):
    if profile not in PROFILES:
        raise ProfileError("unknown profile")
    tier1 = None
    if tier1_input:
        tier1 = json.loads(tier1_input.read_text())
        manifest = json.loads((ROOT / "adoption/skills/manifest.json").read_text())
        managed = sorted(s["name"] for s in manifest["skills"] if s.get("status") != "held"
                         and not s.get("native_plugin") and s.get("agents") != ["claude-code"])
        if (tier1.get("kind") != "tier1-skill-defaults-input" or tier1.get("problems")
                or sorted(tier1.get("managed_installer_names", [])) != managed
                or len(tier1.get("slots", [])) != 13):
            raise ProfileError("canonical Tier1 input differs from managed manifest")
    runtime, route = profile.split("-")
    destination = owned_destination(state / profile)
    if role_scope:
        destination = destination / "roles" / role_scope
    if destination.exists():
        raise ProfileError("use a new profile state root; existing runtime state is preserved")
    if wsl:
        servers = render_wsl_mcp(home, eco_root)
        additions = canonical_servers(home, eco_root, templates, require_token_layer=False)
        for name, spec in additions.items():
            if name in servers and spec != servers[name]:
                raise ProfileError("explicit overlay conflicts with rendered MCP source")
            servers[name] = spec
        if "context-mode" not in servers:
            raise ProfileError("canonical templates must include Context Mode")
    else:
        servers = canonical_servers(home, eco_root, templates)
    # CC 05:54:08Z: these require a committed route/pin or a separate bank
    # grant. A live overlay is research evidence, not configuration authority.
    excluded_servers = {}
    for name in ("headroom", "hindsight", "grafana"):
        if name in servers:
            excluded_servers[name] = "awaiting committed route/pin or lane grant"
            servers.pop(name)
    destination.mkdir(mode=0o700, parents=True)
    roles = {}
    for name in ROLES:
        metadata, prompt = role_source(name)
        tools, omitted = granted_tools(metadata, runtime)
        roles[name] = {"tools": tools, "omitted_unmapped_tools": omitted,
                       "source": "adoption/agents/claude/" + name + ".md"}
        if runtime == "pi":
            front = yaml.safe_dump({"description": metadata["description"]}, sort_keys=False).strip()
            private_write(destination / "agent/prompts" / (name + ".md"),
                          "---\n" + front + "\n---\n" + prompt + "\n$ARGUMENTS\n")
        else:
            permissions = {"*": "deny", **{tool: "allow" for tool in tools}}
            if "read" in tools:
                # OpenCode 53d1eabb session/tools.ts:172,255,343 asks read
                # on mcp:<server>:<uri> for resource helpers. Native ordered
                # permission patterns keep filesystem reads and deny the
                # ungranted resource surface; no custom permission hook.
                permissions["read"] = {"*": "allow", "mcp:*": "deny"}
                permissions["external_directory"] = {
                    "*": "deny", str(home / ".agents/skills") + "/*": "allow"}
            roles[name]["agent"] = {"description": metadata["description"], "mode": "primary",
                                    "prompt": prompt, "permission": permissions,
                                    "options": {"reasoningEffort": "xhigh" if route == "claude" else "high"}}
    if runtime == "pi":
        private_write(destination / "agent/models.json", json.dumps(pi_models(route), indent=2) + "\n")
        # Strict role sessions use direct tools. Deferred activation and
        # codemode must not offer a second route around the imported fence.
        direct = {name: {**server, "exposure": "direct"} for name, server in servers.items()}
        private_write(destination / "agent/mcp.json", json.dumps({"mcpServers": direct,
                      "autoEnableCodemode": False}, indent=2) + "\n")
        private_write(destination / "agent/settings.json", json.dumps({
            "retry": {"enabled": False, "provider": {"maxRetries": 0}},
            "cacheWarming": "off", "enableInstallTelemetry": False,
        }, indent=2) + "\n")
        (destination / "sessions").mkdir(mode=0o700)
    else:
        config = {"$schema": "https://opencode.ai/config.json", "provider": opencode_provider(route),
                  "experimental": {"openTelemetry": True},
                  "model": "anthropic/" + CLAUDE_MODEL if route == "claude" else "omniroute/" + GPT_MODEL,
                  "enabled_providers": ["anthropic" if route == "claude" else "omniroute"],
                  "share": "disabled", "snapshot": False, "autoupdate": False,
                  "mcp": opencode_mcp(servers),
                  "plugin": [(destination / "rtk-home/.config/opencode/plugins/rtk.ts").as_uri()],
                  "agent": {name: value["agent"] for name, value in roles.items()}}
        config["agent"]["title"] = {"disable": True}
        config["agent"]["summary"] = {"disable": True}
        config["agent"]["build"] = {"options": {"reasoningEffort": "xhigh" if route == "claude" else "high"}}
        if role_scope and ROLE_SCOPES[role_scope][1]:
            # obra/superpowers@bb92a777 .opencode/INSTALL.md:15: the native
            # V1 plugin manager installs pinned Git dependencies. Native skill
            # permissions below narrow the pack into the assigned role set.
            config["plugin"].append("superpowers@git+https://github.com/obra/superpowers.git#" + SUPERPOWERS)
            manifest = json.loads((ROOT / "adoption/skills/manifest.json").read_text())
            skills = [s["name"] for s in manifest["skills"]
                      if s.get("status") != "held" and not s.get("native_plugin")
                      and s.get("agents") != ["claude-code"]]
            allowed_skills = [*skills, *ROLE_SCOPES[role_scope][1], "using-superpowers"]
            skill_permission = {"*": "deny", **{name: "allow" for name in allowed_skills}}
            for name in ROLES:
                if "skill" in roles[name]["tools"]:
                    config["agent"][name]["permission"]["skill"] = skill_permission
            # These imported roles grant Read but not Claude Skill. Preserve
            # that fence: SKILL.md reads count through the native tracker.
            # The vendor bootstrap remains, while its native skill helper is
            # unavailable unless the canonical role explicitly grants Skill.
        # Keep the same SKILL.md sources, loaded through OpenCode's native
        # Agent Skills paths; no copied skills or rewritten skill bodies.
        private_write(destination / "config/opencode/opencode.json", json.dumps(config, indent=2) + "\n")
    metadata = {"schema_version": 1, "profile": profile, "role_scope": role_scope, "status": "trial",
                "model": CLAUDE_MODEL if route == "claude" else GPT_MODEL,
                "effort": "xhigh" if route == "claude" else "high",
                "pi_bin": str(pi_bin), "opencode_bin": str(opencode_bin),
                "roles": {name: {k: v for k, v in item.items() if k != "agent"} for name, item in roles.items()},
                "canonical_mcp_sources": [str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
                                          for p in templates], "mcp_server_names": sorted(servers)}
    metadata["excluded_mcp_servers"] = excluded_servers
    metadata["auxiliary_root"] = str(auxiliary_root) if auxiliary_root else None
    metadata["tier1_input"] = str(tier1_input) if tier1_input else None
    metadata["tier1_slots"] = [s["layer_id"] for s in tier1["slots"]] if tier1 else []
    metadata["skills_bin"] = str(skills_bin) if skills_bin else None
    metadata["tier2"] = "unmodified skills find; SKILLS_API_URL unset uses skills.sh; pinned project installs via install_skills.py --project-dir"
    private_write(destination / "profile.json", json.dumps(metadata, indent=2) + "\n")
    # RTK 0.51.0 e001f773 src/hooks/init/{pi,opencode}.rs: vendor installer
    # owns these extension bytes. Pi honors its agent-dir override; OpenCode's
    # installer uses HOME/.config, so give *that installer only* a private HOME
    # and reference its installed plugin through OpenCode's native file URI.
    rtk = shutil.which("rtk")
    if not rtk:
        raise ProfileError("the selected RTK vendor CLI is required")
    version = subprocess.check_output([rtk, "--version"], text=True).strip()
    pin = subprocess.check_output(["git", "-C", str(rtk_source), "rev-parse", "HEAD"], text=True).strip()
    if version != "rtk 0.51.0" or pin != "e001f773f80b22b7dc4c7a79521b30e35aaef026":
        raise ProfileError("RTK installer/source version mismatch")
    if runtime == "pi":
        command = [rtk, "init", "--global", "--agent", "pi", "--hook-only", "--no-patch"]
        environment = {**os.environ, **profile_environment(profile, state, role_scope)}
    else:
        rtk_home = destination / "rtk-home"
        rtk_home.mkdir(mode=0o700)
        command = [rtk, "init", "--global", "--opencode", "--hook-only", "--no-patch"]
        environment = {**os.environ, "HOME": str(rtk_home)}
    subprocess.run(command, env=environment, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if runtime == "pi" and role_scope and ROLE_SCOPES[role_scope][1]:
        # Vendor install first, then native resource-selection settings; no
        # copied SKILL.md and no fork of the package's bootstrap extension.
        package = "git:github.com/obra/superpowers@" + SUPERPOWERS
        subprocess.run([str(pi_bin), "install", package], env=environment, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        settings = destination / "agent/settings.json"
        value = json.loads(settings.read_text())
        # CC option C: Pi scope is package granularity. The vendor bootstrap
        # re-exposes its whole skill directory after package resource filters.
        # Preserve it unchanged; measure listing size instead of claiming an
        # unsupported per-skill CLI filter.
        value["packages"] = [package]
        # This is the newly owned per-profile configuration, not a host file;
        # package resource filtering is Pi docs/packages.md:94-119.
        settings.write_text(json.dumps(value, indent=2) + "\n")
    if runtime == "pi":
        # Upstream package owns OTLP hooks; no custom telemetry extension.
        # Content capture is disabled and the committed local endpoint is set
        # before its first load (README bootstrap defaults otherwise remote).
        subprocess.run([str(pi_bin), "install", PI_OTEL], env=environment, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return {"profile": profile, "status": "trial", "mcp_servers": len(servers), "roles": len(roles)}


def choose_slot() -> str:
    """Reuse the installed no-token inventory/loader probe, fill-first 4/3/2."""
    health = module("runtime_key_health", ROOT / "tools/credentials/anthropic_key_health.py")
    for slot in ("anthropic-api-4", "anthropic-api-3", "anthropic-api-2"):
        result = health.health([slot])[0]
        if result.get("state") == "stored" and result.get("validity") == "valid":
            return slot
    raise ProfileError("no ready Anthropic Console slot in fill-first api-4/3/2")


def inference_facts(log: Path, runtime: str):
    """Numeric native usage and safe response identifiers, without raw text."""
    usage = {k: 0 for k in ("input", "output", "reasoning", "cache_read", "cache_write", "total_tokens")}
    cost, completed, ids, sessions = 0.0, 0, set(), set()
    for line in log.read_text().split("\n"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if runtime == "pi":
            message = event.get("message", {})
            if event.get("type") != "message_end" or not isinstance(message, dict) or message.get("role") != "assistant":
                continue
            values = message.get("usage", {})
            identifier = message.get("responseId")
            amount = values.get("cost", {}).get("total", 0)
            translated = {"input": "input", "output": "output", "reasoning": "reasoning",
                          "cache_read": "cacheRead", "cache_write": "cacheWrite", "total_tokens": "totalTokens"}
            values = {key: values.get(source, 0) for key, source in translated.items()}
        else:
            part = event.get("part", {})
            if event.get("type") != "step_finish" or not isinstance(part, dict):
                continue
            tokens = part.get("tokens", {})
            amount, identifier = part.get("cost", 0), part.get("messageID")
            values = {k: tokens.get(k, 0) for k in ("input", "output", "reasoning")}
            values.update(cache_read=tokens.get("cache", {}).get("read", 0),
                          cache_write=tokens.get("cache", {}).get("write", 0), total_tokens=tokens.get("total", 0))
            session = event.get("sessionID")
            if isinstance(session, str) and re.fullmatch(r"ses_[A-Za-z0-9_-]{1,90}", session):
                sessions.add(session)
        if isinstance(identifier, str) and re.fullmatch(r"msg_[A-Za-z0-9_-]{1,90}", identifier):
            if identifier in ids:
                continue
            ids.add(identifier)
        for key, value in values.items():
            if type(value) in (int, float) and 0 <= value < 10**10:
                usage[key] += value
        if type(amount) in (int, float) and 0 <= amount < 10**6:
            cost += amount
        completed += 1
    return {"completed_native_steps": completed, "usage": usage, "native_cost_usd": round(cost, 8),
            "usage_measured": completed > 0,
            "response_ids": sorted(ids), "native_session_ids": sorted(sessions),
            "http_request_id": "UNVERIFIED: native events expose no independently traced HTTP request id",
            "cost_basis": "native usage priced by runtime model metadata; GPT is API-price equivalent",
            "invoice_verified": False}


def fresh_worktree(repository: Path, profile: str) -> Path:
    run_id = uuid.uuid4().hex[:12]
    branch = "runtime/" + profile + "-" + run_id
    # Worktrunk documents --format json/--no-cd; no repository hook approval is
    # synthesized here. Unapproved hooks fail closed through native Worktrunk.
    subprocess.run(["git", "-C", str(repository), "fetch", "origin", "main"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    completed = subprocess.run(["wt", "-C", str(repository), "switch", "--create", branch,
                                "--base", "origin/main", "--no-cd", "--format=json"],
                               capture_output=True, text=True, check=True)
    return Path(json.loads(completed.stdout)["path"])


def launch(args):
    profile = args.profile
    runtime, route = profile.split("-")
    root = owned_destination(args.state_root / profile)
    role_scope = next((scope for scope, (name, _) in ROLE_SCOPES.items() if name == args.role), None)
    if role_scope:
        root = root / "roles" / role_scope
    # Only our own generated non-secret descriptor is read; native auth/config
    # and session stores remain owned by the vendor runtime.
    meta = json.loads((root / "profile.json").read_text())
    if meta.get("status") != "trial":
        raise ProfileError("only measured selections may change trial status")
    workspace = fresh_worktree(args.repository.resolve(), profile)
    aux = Path(meta["auxiliary_root"]) if meta.get("auxiliary_root") else None
    runtime_env = profile_environment(profile, args.state_root, role_scope, aux)
    if meta.get("skills_bin"):
        runtime_env["PATH"] = str(Path(meta["skills_bin"]).parent) + os.pathsep + runtime_env["PATH"]
    if meta.get("tier1_input"):
        runtime_env["NS_TIER1_INPUT"] = meta["tier1_input"]
    env = {**os.environ, **runtime_env,
           "NS_RUNTIME_REQUEST_ID": "ns-run-" + profile + "-" + uuid.uuid4().hex}
    title = "native-stack " + profile + " trial"
    if not args.print:
        print("\033]0;" + title + "\007", end="", flush=True)
    interactive_run = root / "runs" / uuid.uuid4().hex
    if not args.print:
        interactive_run.mkdir(mode=0o700, parents=True)
    if runtime == "pi":
        command = [meta["pi_bin"], "--provider", "anthropic" if route == "claude" else "omniroute",
                   "--model", meta["model"], "--thinking", meta["effort"],
                   "--session-dir", str(root / "sessions" if args.print else interactive_run / "sessions")]
        if args.role:
            grant = meta["roles"][args.role]["tools"]
            command += ["--tools", ",".join(grant)]
            if not any(tool.startswith("mcp__") for tool in grant):
                command += ["--no-mcp"]
            else:
                command += ["--exclude-tools", "codemode,tool_search,list_mcp_resources,list_mcp_resource_templates,read_mcp_resource"]
        if args.print:
            command += ["--mode", "json"]
        if args.prompt:
            command += [("/" + args.role + " " if args.role else "") + args.prompt]
    else:
        if args.role and args.role not in ROLES:
            raise ProfileError("unknown role")
        command = [meta["opencode_bin"]]
        if args.print:
            command += ["run", "--format", "json", "--title", "runtime-" + uuid.uuid4().hex]
        command += ["--model", ("anthropic/" if route == "claude" else "omniroute/") + meta["model"],
                    "--variant", meta["effort"]]
        if args.role:
            command += ["--agent", args.role]
        if args.prompt:
            command.append(args.prompt)
    if not args.print:
        # credential_run masks through pipes. util-linux script provides the
        # native TUI a PTY without reading/copying authentication state.
        command = ["script", "--quiet", "--return", "--command", shlex.join(command), "/dev/null"]
    if route == "claude":
        slot = choose_slot()
        command = [sys.executable, str(ROOT / "tools/credentials/credential_run.py"), slot,
                   "--only", "ANTHROPIC_API_KEY", "--", "env",
                   *[key + "=" + value for key, value in runtime_env.items()],
                   *command]
        # XDG_STATE_HOME also locates credential_run's inventory store. Resolve
        # the host store in the loader's original environment; apply runtime
        # XDG isolation only to its child through env. No store is copied into
        # a runtime profile and no credential path/value is materialized here.
        env = {**os.environ, "NS_RUNTIME_REQUEST_ID": env["NS_RUNTIME_REQUEST_ID"]}
    if args.print:
        run = root / "runs" / uuid.uuid4().hex
        run.mkdir(mode=0o700, parents=True)
        log, errors = run / "events.jsonl", run / "stderr.log"
        started = utc()
        # GNU timeout owns the bounded process group and gives the credential
        # runner its normal TERM cleanup grace; subprocess timeout is only an
        # outer watchdog. This also bounds GPT descendants without credentials.
        command = ["timeout", "--signal=TERM", "--kill-after=5s", str(args.timeout_seconds), *command]
        with log.open("x", encoding="utf-8") as handle, errors.open("x", encoding="utf-8") as stderr:
            log.chmod(0o600); errors.chmod(0o600)
            # The loader masks Claude output before it reaches this private log.
            try:
                result = subprocess.run(command, cwd=workspace, env=env, stdout=handle, stderr=stderr,
                                        timeout=args.timeout_seconds + 15)
                exit_code = result.returncode
            except subprocess.TimeoutExpired:
                exit_code = 124
        # Use the existing adapter API directly: the general tracker CLI also
        # visits Claude/Codex native stores, which this isolated run need not.
        sys.path.insert(0, str(ROOT / "tools/skill-usage"))
        from runtime_usage import scan
        from skill_usage import skillmd_hits
        inventory = json.loads((ROOT / "adoption/skills/manifest.json").read_text())
        names = {s["name"] for s in inventory["skills"]}
        report = scan([(runtime, log)], names, skillmd_hits=skillmd_hits)[runtime]
        tracker_code = 0
        private_write(run / "invocations.json", json.dumps(report, indent=2) + "\n")
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip()
        private_write(run / "receipt.json", json.dumps({
            "schema_version": 1, "status": "trial", "profile": profile, "role": args.role,
            "started_at": started, "finished_at": utc(), "head": head,
            "request_label": env["NS_RUNTIME_REQUEST_ID"], "model": meta["model"],
            "credential_loader_id": slot if route == "claude" else None,
            "inference": inference_facts(log, runtime),
            "runtime_exit_code": exit_code, "tracker_exit_code": tracker_code,
            "invocations": report, "publication_boundary": "derived facts only; native state remains private",
        }, indent=2) + "\n")
        # Explicit JSON-mode output is read in place, never copied or hashed.
        # The response record stays private and requires the usual publication
        # scan before anybody chooses to include its text in a review packet.
        texts = []
        for line in log.read_text().split("\n"):
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if runtime == "pi" and event.get("type") == "message_end":
                message = event.get("message", {})
                if message.get("role") == "assistant":
                    texts += [c["text"] for c in message.get("content", []) if c.get("type") == "text"]
            elif runtime == "opencode" and event.get("type") == "text":
                part = event.get("part", {})
                if isinstance(part.get("text"), str):
                    texts.append(part["text"])
        final = texts[-1].strip() if texts else "No completed assistant text."
        record = (f"# Trial runtime handoff\n\nProfile: ns-{profile}\nRole: {args.role or 'interactive'}\n"
                  f"Head: {head}\nRuntime exit: {exit_code}\nTracker exit: {tracker_code}\n"
                  "Standing checks: privacy/publication, digest, review threads and fail-before are "
                  "task-scoped evidence obligations, never inferred from a process exit.\n\n" + final + "\n")
        if args.role == "isolated-builder":
            record += f"\nBuilder handoff at {head[:8]} (trial; inspect standing checks above).\n"
        elif not re.search(r"Verdict: [A-Z_-]+ at " + re.escape(head[:8]) + r"\s*$", record):
            record += f"\nVerdict: UNVERIFIED at {head[:8]}\n"
        private_write(run / "CC-RECORD.md", record)
        print(json.dumps({"runtime_exit_code": exit_code, "tracker_exit_code": tracker_code,
                          "receipt": str(run / "receipt.json"), "record": str(run / "CC-RECORD.md")}))
        return exit_code or (2 if tracker_code else 0)
    else:
        result = subprocess.run(command, cwd=workspace, env=env)
        sys.path.insert(0, str(ROOT / "tools/skill-usage"))
        from runtime_usage import scan, scan_opencode_export
        from skill_usage import skillmd_hits
        inventory = json.loads((ROOT / "adoption/skills/manifest.json").read_text())
        names = {s["name"] for s in inventory["skills"]}
        if runtime == "pi":
            explicit_logs = [("pi", path) for path in (interactive_run / "sessions").rglob("*.jsonl")]
            measured = scan(explicit_logs, names, skillmd_hits=skillmd_hits)
        else:
            # Native metadata listing scopes collection to this fresh
            # worktree. Export is read transiently, reduced, then discarded.
            # Claude's loader used the host environment; restore only the
            # native profile variables for post-run collection. Otherwise
            # session list/export would visit the account's main OpenCode DB.
            collector_env = {**os.environ, **runtime_env}
            with tempfile.TemporaryFile(mode="w+") as stream:
                listing = subprocess.run([meta["opencode_bin"], "session", "list", "--format", "json"],
                                         cwd=workspace, env=collector_env, stdout=stream, stderr=subprocess.DEVNULL)
                stream.seek(0)
                sessions = json.load(stream) if listing.returncode == 0 else []
            measured = []
            for session in sessions:
                if session.get("directory") != str(workspace):
                    continue
                with tempfile.TemporaryFile(mode="w+") as stream:
                    exported = subprocess.run([meta["opencode_bin"], "export", session["id"]],
                                              cwd=workspace, env=collector_env, stdout=stream, stderr=subprocess.DEVNULL)
                    if exported.returncode == 0:
                        stream.seek(0)
                        measured.append(scan_opencode_export(json.load(stream), names, skillmd_hits=skillmd_hits))
        private_write(interactive_run / "invocations.json", json.dumps(measured, indent=2) + "\n")
        print(json.dumps({"invocations": str(interactive_run / "invocations.json"),
                          "runtime_exit_code": result.returncode}))
    return result.returncode


def install_launchers(args):
    root = args.home / ".local/bin"
    def launcher(path, content):
        if path.exists() and getattr(args, "update_owned", False):
            if path.is_symlink() or not path.is_file():
                raise ProfileError("launcher is not an owned regular file")
            previous = path.read_text()
            lines = previous.splitlines()
            if len(lines) != 2 or lines[0] != "#!/usr/bin/env bash" or not lines[1].startswith("exec "):
                raise ProfileError("launcher ownership mismatch")
            parts = shlex.split(lines[1][5:])
            if parts[:2] != [sys.executable, str(Path(__file__).resolve())] or parts[2] not in {"launch", "run"}:
                raise ProfileError("launcher ownership mismatch")
            replacement = path.with_name(path.name + "." + uuid.uuid4().hex)
            private_write(replacement, content, 0o700)
            os.replace(replacement, path)
        else:
            private_write(path, content, 0o700)
    for profile in PROFILES:
        command = [sys.executable, str(Path(__file__).resolve()), "launch", profile,
                   "--state-root", str(args.state_root), "--repository", str(args.repository)]
        launcher(root / ("ns-" + profile), "#!/usr/bin/env bash\nexec " + shlex.join(command) + ' "$@"\n')
    runner = [sys.executable, str(Path(__file__).resolve()), "run", "--state-root", str(args.state_root),
              "--repository", str(args.repository)]
    launcher(root / "ns-run", "#!/usr/bin/env bash\nexec " + shlex.join(runner) + ' "$@"\n')
    # MicrosoftDocs/terminal:TerminalDocs/json-fragment-extensions.md, Structure
    # and Fragment installation. This is a new fragment, never settings.json.
    fragment = {"profiles": [{"name": "NativeStack " + profile + " (trial)",
                               "commandline": 'wsl.exe --exec sh -lc "exec $HOME/.local/bin/ns-' + profile + '"',
                               "tabTitle": profile + " trial"} for profile in PROFILES]}
    content = json.dumps(fragment, indent=2) + "\n"
    if not (args.fragment.is_file() and not args.fragment.is_symlink() and args.fragment.read_text() == content):
        private_write(args.fragment, content)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--state-root", type=Path, required=True)
    prepare.add_argument("--home", type=Path, default=Path.home())
    prepare.add_argument("--eco-root", type=Path, required=True)
    prepare.add_argument("--mcp-template", type=Path, action="append", required=True)
    prepare.add_argument("--pi-bin", type=Path, required=True)
    prepare.add_argument("--opencode-bin", type=Path, required=True)
    prepare.add_argument("--rtk-source", type=Path, required=True)
    prepare.add_argument("--wsl-render", action="store_true",
                         help="render canonical MCP through new_wsl_client_config's WSL map first")
    prepare.add_argument("--role-scoped", action="store_true",
                         help="also install vendor role sets into separate native role profile roots")
    prepare.add_argument("--auxiliary-root", type=Path,
                         help="owned vendor-install prefix for Tavily, agent-browser and OpenResearch; no installer duplication")
    prepare.add_argument("--tier1-input", type=Path,
                         help="CNP-owned derived lifecycle input, consumed by path without copying")
    prepare.add_argument("--skills-bin", type=Path,
                         help="existing pinned vendor Skills CLI for Tier2 find and run-scoped install")
    run = sub.add_parser("launch")
    run.add_argument("profile", type=profile_name, choices=PROFILES)
    run.add_argument("--state-root", type=Path, required=True)
    run.add_argument("--repository", type=Path, required=True)
    run.add_argument("--role", choices=ROLES, default="isolated-builder")
    run.add_argument("--print", action="store_true")
    run.add_argument("--prompt")
    run.add_argument("--timeout-seconds", type=int, default=900)
    lane = sub.add_parser("run", help="ns-run <profile> <role> <brief-file>")
    lane.add_argument("--state-root", type=Path, required=True)
    lane.add_argument("--repository", type=Path, required=True)
    lane.add_argument("profile", type=profile_name, choices=PROFILES)
    lane.add_argument("role", choices=("builder", "reviewer", "auditor", "researcher"))
    lane.add_argument("brief", type=Path)
    lane.add_argument("--timeout-seconds", type=int, default=900)
    install = sub.add_parser("install-launchers")
    install.add_argument("--home", type=Path, default=Path.home())
    install.add_argument("--state-root", type=Path, required=True)
    install.add_argument("--repository", type=Path, required=True)
    install.add_argument("--fragment", type=Path, required=True)
    install.add_argument("--update-owned", action="store_true",
                         help="replace only launchers whose exact exec prefix identifies this generator")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "prepare":
            for profile in PROFILES:
                for scope in [None, *ROLE_SCOPES] if args.role_scoped else [None]:
                    print(json.dumps(render(profile, state=args.state_root, home=args.home,
                                            eco_root=args.eco_root, templates=args.mcp_template,
                                            pi_bin=args.pi_bin, opencode_bin=args.opencode_bin,
                                            rtk_source=args.rtk_source, wsl=args.wsl_render, role_scope=scope,
                                            auxiliary_root=args.auxiliary_root, tier1_input=args.tier1_input,
                                            skills_bin=args.skills_bin)))
            return 0
        if args.command == "install-launchers":
            install_launchers(args)
            return 0
        if args.command == "run":
            # A brief is explicit user/co-op input, never an authentication
            # store; require the ordinary Markdown/text task carrier.
            if (args.brief.suffix not in {".md", ".txt"} or args.brief.is_symlink()
                    or not stat.S_ISREG(args.brief.stat().st_mode)):
                raise ProfileError("brief must be a regular Markdown/text task file")
            args.role = {"builder": "isolated-builder", "reviewer": "evidence-reviewer",
                         "auditor": "security-reviewer", "researcher": "stack-researcher"}[args.role]
            args.print = True
            args.prompt = args.brief.read_text() + (
                "\nStanding checks: inspect privacy/publication scan results, digest correctness, "
                "open review threads and fail-before regression evidence within this brief's scope. "
                "Report missing evidence explicitly. Use the CC verdict format for review roles.\n")
        return launch(args)
    except (OSError, ValueError, subprocess.SubprocessError):
        # Do not expose native configuration/authentication details on errors.
        print("runtime_profiles: operation refused; native private state retained", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
