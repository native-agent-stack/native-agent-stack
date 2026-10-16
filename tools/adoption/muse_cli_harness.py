#!/usr/bin/env python3
"""Native Claude Code/Codex subscription-Muse TRIAL profiles for ns-run.

Uses the committed WSL renderer and vendor-native settings/plugin mechanisms;
never imports a live client config, auth file or session store. Source screen:
notes/muse-harness-trials-20261016/CLI-ROUTE-SCREEN.md.
"""
from __future__ import annotations

import contextlib
import copy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tomllib
import uuid

ROOT = Path(__file__).resolve().parents[2]
MODEL = "mc/muse-wonder-full-1.0"
GATEWAY = "http://127.0.0.1:21128"
PROFILES = ("claude-muse", "codex-muse")
VERSIONS = {"claude": "2.1.301", "codex": "0.162.1"}
RUNTIME_SHA256 = {
    "claude": "bc1aad9982c7b59c7d889ff92595d61cf46e0a6eae074cb551d932a989bcd222",
    "codex": "628e35487d888a28f0427fc37501da529dd3d81fcbad7a2c3421c1e8670d92e1",
}  # Installed native ELF observations, 2026-10-16; screen record names source pins.
CONTEXT_MODE_VERSION = "1.0.169"
MEMORY_VERSION = "2.6.6"
MEMORY_SHA256 = "2f74b0195a259096fcb0588b4426835b5363eb4e44793ef15f2eb0587ab5e0b5"


class HarnessError(ValueError):
    """An unqualified or incomplete native harness is refused."""


def adoption_module(name):
    directory = str(ROOT / "tools/adoption")
    if directory not in sys.path:
        sys.path.insert(0, directory)
    return importlib.import_module(name)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def private_write(path: Path, content: str):
    adoption_module("runtime_profiles").private_write(path, content)


def executable_identity(runtime: str, executable: Path) -> dict:
    selected = executable.resolve(strict=True)
    result = subprocess.run([str(selected), "--version"], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=20, check=True)
    if VERSIONS[runtime] not in result.stdout.split():
        raise HarnessError("runtime differs from the qualified version")
    digest = sha256(selected)
    if digest != RUNTIME_SHA256[runtime]:
        raise HarnessError("runtime differs from the qualified ELF")
    return {"executable": str(selected), "version": VERSIONS[runtime], "sha256": digest}


def claude_settings(baseline: dict) -> dict:
    """Keep canonical hooks/deny rules; route aliases and children to Wonder Full.

    Claude Code 2.1.301 --help (--effort), official model-config custom-model
    capability opt-in, captured 2026-10-16; no fallback provider is configured.
    """
    settings = copy.deepcopy(baseline)
    settings.update(model=MODEL, effortLevel="max", advisorModel=MODEL)
    environment = settings.setdefault("env", {})
    environment.update(CLAUDE_CODE_SUBAGENT_MODEL=MODEL,
                       ANTHROPIC_MODEL=MODEL,
                       ANTHROPIC_CUSTOM_MODEL_OPTION=MODEL,
                       ANTHROPIC_CUSTOM_MODEL_OPTION_SUPPORTED_CAPABILITIES="effort,xhigh_effort,max_effort")
    for alias in ("OPUS", "SONNET", "HAIKU", "FABLE"):
        environment["ANTHROPIC_DEFAULT_" + alias + "_MODEL"] = MODEL
    settings["modelSettings"] = {MODEL: {"effortLevel": "max"}}
    # Headless profiles load the selected local plugin with --plugin-dir.
    # Preserve the canonical hook source; do not auto-fetch unrelated plugins.
    settings.pop("extraKnownMarketplaces", None)
    settings["enabledPlugins"] = {}
    return settings


def codex_settings(baseline: dict) -> dict:
    """Native Responses provider; max is supported by both pinned vocabularies.

    openai/codex rust-v0.162.1 protocol/src/openai_models/reasoning_effort.rs;
    official advanced config custom-provider schema. Effort remains requested
    evidence until an upstream response independently establishes it.
    """
    settings = copy.deepcopy(baseline)
    settings.update(model=MODEL, model_provider="omniroute-muse", model_reasoning_effort="max",
                    approval_policy="never", sandbox_mode="workspace-write", service_tier=None)
    settings.pop("service_tier", None)
    settings["model_providers"] = {"omniroute-muse": {
        "name": "OmniRoute Muse subscription TRIAL", "base_url": GATEWAY + "/v1",
        "wire_api": "responses", "requires_openai_auth": False,
        # rust-v0.162.1 model-provider-info/src/lib.rs:180-183,498-509:
        # explicit zero is retained, so the first failed qualification stays
        # one attempt rather than the client's default five reconnects.
        "request_max_retries": 0, "stream_max_retries": 0,
        "http_headers": {"Authorization": "Bearer local"}}}
    agents = settings.setdefault("agents", {})
    agents.update(default_subagent_model=MODEL, default_subagent_reasoning_effort="max")
    features = settings.setdefault("features", {})
    features.update(hooks=True, daemon_auto_start=False, shell_snapshot=False)
    # A profile-local native registration selects the existing pinned package.
    settings.pop("marketplaces", None)
    return settings


def layer_bundle(profile_home: Path, eco_root: Path, repository: Path, *, memory_binary: Path | None = None) -> dict:
    """Same supported renderer as the committed WSL deployment, no host reads."""
    wiring = adoption_module("new_wsl_client_config")
    results, manifest, plan, errors, _ = wiring.analyse(ROOT, authorization=False)
    if errors:
        raise HarnessError("canonical WSL render did not pass its own checks")
    host = json.loads((ROOT / wiring.HOST_TEMPLATE_REL).read_text())
    values = {key: value.replace("${WSL_USER}", Path.home().name) for key, value in host.items()}
    values.update(HOME=str(profile_home), ECO_ROOT=str(eco_root), PROJECT_ROOT=str(repository),
                  CODEX_MODEL=MODEL, XDG_RUNTIME_DIR=f"/run/user/{os.getuid()}",
                  OTEL_ENDPOINT=f"127.0.0.1:{plan['ports']['collector_http_port']}")
    # Match new_wsl_client_config.host_values:1123-1124 and the documented
    # render_config.py:15-22 override. Runtime and profile data have distinct
    # roots; do not derive a hook executable from the private profile HOME.
    if memory_binary is not None:
        values["AI_MEMORY_BIN"] = str(memory_binary)
    elif plan.get("ai_memory_bin"):
        values["AI_MEMORY_BIN"] = str(Path.home() / plan["ai_memory_bin"])
    return wiring.render(ROOT, results, plan, values, manifest)


def memory_identity(source_home: Path) -> dict:
    """Bind the existing host dependency; this does not install a memory tool.

    docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:684 records 2.6.6
    live. The installed client and upstream v2.6.6 hook CLI support the
    rendered --data-dir/--event/--agent/--server-url arguments.
    """
    plan = adoption_module("new_wsl_client_config").load_plan(ROOT)
    if not plan.get("ai_memory_bin"):
        raise HarnessError("canonical host plan does not name a memory executable")
    selected = (source_home / plan["ai_memory_bin"]).resolve(strict=True)
    version = subprocess.run([str(selected), "--version"], stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, timeout=20, check=True).stdout.strip()
    digest = sha256(selected)
    if version != "ai-memory " + MEMORY_VERSION or digest != MEMORY_SHA256:
        raise HarnessError("host memory executable differs from the screened dependency")
    return {"executable": str(selected), "version": MEMORY_VERSION, "sha256": digest,
            "class": "existing host dependency; explicit canonical renderer input"}


def selected_skills(source_home: Path, profile_home: Path, runtime: str, package: Path) -> list[str]:
    """Link only the committed install inventory, not a host config/cache root."""
    inventory = json.loads((ROOT / "adoption/skills/manifest.json").read_text())["skills"]
    names = []
    for item in inventory:
        if item.get("status") == "held" or item.get("native_plugin"):
            continue
        if runtime == "codex" and (item.get("agents") == ["claude-code"] or not item.get("codex_enabled", False)):
            continue
        source = source_home / (".claude/skills" if item.get("agents") == ["claude-code"]
                                else ".agents/skills") / item["name"]
        if not (source / "SKILL.md").is_file():
            raise HarnessError("a canonical managed skill is unavailable: " + item["name"])
        destination = profile_home / ".agents/skills" / item["name"]
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination.symlink_to(source.resolve(strict=True), target_is_directory=True)
        if runtime == "claude":
            native = profile_home / ".claude/skills" / item["name"]
            native.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            native.symlink_to(source.resolve(strict=True), target_is_directory=True)
        names.append(item["name"])
    if not (package / "skills/context-mode/SKILL.md").is_file():
        raise HarnessError("pinned Context Mode skill is unavailable")
    return names


def child_environment(root: Path, profile: str, workspace: Path) -> dict:
    """Allowlist process context; never forward a caller's provider credentials."""
    home = root / "home"
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "TERM", "DISPLAY",
                                           "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR") if key in os.environ}
    env.update(HOME=str(home), PWD=str(workspace), CODEX_HOME=str(home / ".codex"),
               CLAUDE_CONFIG_DIR=str(home / ".claude"),
               XDG_CONFIG_HOME=str(home / ".config"), XDG_DATA_HOME=str(home / ".local/share"),
               XDG_CACHE_HOME=str(home / ".cache"), XDG_STATE_HOME=str(home / ".local/state"),
               TMPDIR=str(root / "tmp"), RTK_TELEMETRY_DISABLED="1", MCP_AUTO_OPEN_ENABLED="false",
               CONTEXT_MODE_PROJECT_DIR=str(workspace), CLAUDE_PROJECT_DIR=str(workspace),
               CONTEXT_MODE_DATA_DIR=str(root / "context-state"),
               CONTEXT_MODE_DIR=str(root / "context-state/context-mode"),
               CONTEXT_MODE_PLATFORM="claude-code" if profile.startswith("claude-") else "codex",
               OTEL_RESOURCE_ATTRIBUTES="service.name=ns-" + profile + ",deployment.environment=trial")
    if profile == "claude-muse":
        env.update(ANTHROPIC_BASE_URL=GATEWAY, ANTHROPIC_AUTH_TOKEN="local",
                   ANTHROPIC_MODEL=MODEL, CLAUDE_CODE_SUBAGENT_MODEL=MODEL,
                   ANTHROPIC_CUSTOM_MODEL_OPTION=MODEL,
                   ANTHROPIC_CUSTOM_MODEL_OPTION_SUPPORTED_CAPABILITIES="effort,xhigh_effort,max_effort")
        for alias in ("OPUS", "SONNET", "HAIKU", "FABLE"):
            env["ANTHROPIC_DEFAULT_" + alias + "_MODEL"] = MODEL
    return env


def role_metadata(role: str):
    runtime = adoption_module("runtime_profiles")
    if role not in runtime.ROLES:
        raise HarnessError("unknown native role")
    return runtime.role_source(role)


def claude_tools(metadata: dict) -> list[str]:
    """Same exact role grants, addressed to the strict explicit MCP server.

    Native --strict-mcp-config uses the supplied registrations for print jobs.
    The canonical plugin namespace denotes the same Context Mode actions; the
    explicit server's native names are mcp__context-mode__<action>.
    """
    return [tool.strip().replace("mcp__plugin_context-mode_context-mode__", "mcp__context-mode__", 1)
            for tool in metadata["tools"].split(",")]


def command(meta: dict, root: Path, workspace: Path, args) -> list[str]:
    role = args.role or "isolated-builder"
    metadata, _ = role_metadata(role)
    if meta["runtime"] == "claude":
        tools = claude_tools(metadata)
        builtins = [tool for tool in tools if not tool.startswith("mcp__")]
        return [meta["executable"], "--model", MODEL, "--effort", "max", "--print",
                "--output-format", "stream-json", "--verbose", "--setting-sources", "user",
                "--strict-mcp-config", "--mcp-config", str(root / "mcp.json"),
                "--plugin-dir", meta["context_mode"], "--agent", role,
                "--tools", ",".join(builtins), "--allowedTools", ",".join(tools),
                "--permission-mode", "dontAsk", args.prompt]
    readonly = "Bash" not in metadata["tools"].split(", ")
    argv = [meta["executable"], "--ask-for-approval", "never", "exec", "--json",
            "--model", MODEL, "--sandbox", "read-only" if readonly else "workspace-write",
            "--cd", str(workspace), "-c", 'model_reasoning_effort="max"',
            "-c", "developer_instructions=" + json.dumps(codex_role_instructions(role))]
    grants = role_mcp_grants(role)
    definitions = meta.get("mcp_server_configs")
    if not isinstance(definitions, dict):
        raise HarnessError("complete native MCP definitions are required")
    for server, definition in definitions.items():
        # rust-v0.162.1 config/src/overrides.rs:17-27 splits paths literally.
        # Codex 0.162.1 --config therefore treats TOML quoting
        # inside that CLI key creates a different server name. All canonical
        # names are native bare-key components; refuse anything else.
        if not re.fullmatch(r"[A-Za-z0-9_-]+", server):
            raise HarnessError("MCP server cannot be represented by a native config override")
        # SessionFlags validates a server as a complete transport. Preserve
        # its canonical command/URL/env alongside the selected role's grants.
        scoped = {**definition, "enabled": server in grants}
        if server in grants:
            scoped["enabled_tools"] = grants[server]
        argv += ["-c", "mcp_servers." + server + "=" + adoption_module("new_wsl_client_config").toml_value(scoped)]
    if "WebSearch" not in metadata["tools"].split(", "):
        argv += ["-c", 'web_search="disabled"']
    return [*argv, args.prompt]


def codex_role_instructions(role: str) -> str:
    candidates = [ROOT / "adoption/agents/codex/workers" / (role + ".toml"),
                  ROOT / "adoption/agents/codex" / (role + ".toml")]
    for path in candidates:
        if path.is_file():
            return tomllib.loads(path.read_text())["developer_instructions"]
    # Only canonical roles without a native file use their existing body.
    return role_metadata(role)[1]


def role_mcp_grants(role: str) -> dict[str, list[str]]:
    metadata, _ = role_metadata(role)
    grants = {}
    for raw in metadata["tools"].split(","):
        tool = raw.strip()
        if not tool.startswith("mcp__"):
            continue
        _, server, name = tool.split("__", 2)
        if server.startswith("plugin_context-mode"):
            server = "context-mode"
        if "*" in name:
            raise HarnessError("native role must use exact MCP tool names")
        grants.setdefault(server, []).append(name)
    return grants


def register_codex_plugin(executable: Path, root: Path, package: Path):
    """Native local marketplace registration; no account/config state is copied.

    rust-v0.162.1 cli/src/marketplace_cmd.rs:45,66-74;
    core-plugins/src/marketplace_add/source.rs:32-44,86-87.
    """
    env = child_environment(root, "codex-muse", ROOT)
    commands = [[str(executable), "plugin", "marketplace", "add", str(package), "--json"],
                [str(executable), "plugin", "add", "context-mode@context-mode", "--json"]]
    for index, argv in enumerate(commands):
        result = subprocess.run(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=120, check=False)
        private_write(root / f"plugin-prepare-{index}.json", result.stdout)
        if result.returncode:
            raise HarnessError("native profile-local plugin preparation failed")


def prepare(args, profile: str) -> dict:
    if profile not in PROFILES:
        raise HarnessError("unknown native Muse profile")
    runtime = profile.split("-", 1)[0]
    executable = getattr(args, runtime + "_bin", None)
    if not executable:
        raise HarnessError("pass the exact existing native runtime executable")
    identity = executable_identity(runtime, Path(executable))
    profiles = adoption_module("runtime_profiles")
    destination = profiles.owned_destination(args.state_root / profile)
    if destination.exists():
        raise HarnessError("use a new native profile state root")
    package = args.eco_root / f"tools/context-mode-{CONTEXT_MODE_VERSION}/lib/node_modules/context-mode"
    if (not (package / "package.json").is_file()
            or json.loads((package / "package.json").read_text()).get("version") != CONTEXT_MODE_VERSION):
        raise HarnessError("pinned Context Mode package unavailable")
    home = destination / "home"
    memory = memory_identity(args.home)
    bundle = layer_bundle(home, args.eco_root, ROOT, memory_binary=Path(memory["executable"]))
    install = adoption_module("install_claude_profile")
    servers = install.render_servers(json.loads(bundle["mcp-servers.json"]), args.home, args.eco_root)
    token_template = ROOT / "adoption/mcp/runtime-token-layer.json"
    overlays = profiles.canonical_servers(args.home, args.eco_root,
        [token_template, *getattr(args, "mcp_template", [])], require_token_layer=True)
    for name, spec in overlays.items():
        if name in servers and servers[name] != spec:
            raise HarnessError("explicit MCP overlay conflicts with the canonical source")
        servers[name] = spec
    for name in ("headroom", "hindsight", "grafana"):
        servers.pop(name, None)
    if "context-mode" not in servers or "ai-memory" not in servers:
        raise HarnessError("canonical token/memory layer is unavailable")
    destination.mkdir(mode=0o700, parents=True)
    (destination / "tmp").mkdir(mode=0o700)
    skills = selected_skills(args.home, home, runtime, package)
    with contextlib.redirect_stdout(io.StringIO()):
        install.install_guards(home, False)
        if runtime == "claude":
            install.install_routing_skill(home, False)
    token_env = child_environment(destination, profile, ROOT)
    servers["context-mode"] = {**servers["context-mode"], "args": [str(package / "start.mjs")],
                               "env": {**servers["context-mode"].get("env", {}),
                                       **{k: token_env[k] for k in token_env if k.startswith("CONTEXT_MODE_")
                                          or k == "CLAUDE_CONFIG_DIR"}}}
    # Strict native print jobs use explicit registrations. The local plugin
    # still supplies Context Mode hooks and skills, while this named canonical
    # registration supplies its MCP tools under mcp__context-mode__<action>.
    private_write(destination / "mcp.json", json.dumps({"mcpServers": servers}, indent=2) + "\n")
    if runtime == "claude":
        native_mcp = servers
        data = claude_settings(json.loads(bundle["settings.json"]))
        data["env"].update(ANTHROPIC_BASE_URL=GATEWAY, ANTHROPIC_AUTH_TOKEN="local")
        private_write(home / ".claude/settings.json", json.dumps(data, indent=2) + "\n")
        private_write(home / ".claude/CLAUDE.md", bundle["claude-user-instructions.md"])
        for role in profiles.ROLES:
            metadata, body = profiles.role_source(role)
            # Native frontmatter may otherwise pin a non-Muse child model.
            metadata.update(model=MODEL, effort="max")
            metadata["tools"] = ", ".join(claude_tools(metadata))
            import yaml
            private_write(home / ".claude/agents" / (role + ".md"),
                          "---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---\n" + body)
    else:
        data = codex_settings(tomllib.loads(bundle["codex.config.toml"]))
        for name in ("headroom", "hindsight", "grafana"):
            data.get("mcp_servers", {}).pop(name, None)
        native_mcp = data.get("mcp_servers", {})
        data["shell_environment_policy"] = {"inherit": "none", "set": token_env}
        wiring = adoption_module("new_wsl_client_config")
        private_write(home / ".codex/config.toml", wiring.emit_toml(data, "# Native subscription Muse TRIAL"))
        private_write(home / ".codex/hooks.json", bundle["codex.hooks.json"])
        private_write(home / ".codex/AGENTS.md", bundle["codex-user-instructions.md"])
        register_codex_plugin(Path(identity["executable"]), destination, package)
    meta = {"profile": profile, "runtime": runtime, "status": "trial", "model": MODEL,
            "provider": "OmniRoute muse-code subscription", "reasoning_effort_requested": "max",
            "model_identity_limit": "gateway may echo request; not upstream attestation",
            "context_mode": str(package), "skills": skills, "mcp_servers": sorted(native_mcp),
            "mcp_server_configs": native_mcp,
            "native_cost_usd": None, "cost_basis": "subscription; billed cost unmeasured",
            "role_layout": "shared profile; native per-invocation role and exact tool grants",
            "roles": list(profiles.ROLES),
            "memory_runtime": memory,
            "canonical_source": "tools/adoption/new_wsl_client_config.py", **identity}
    private_write(destination / "profile.json", json.dumps(meta, indent=2) + "\n")
    return meta


def event_facts(path: Path, runtime: str) -> dict:
    count, terminal, completed_terminal, error_terminal = 0, 0, 0, 0
    attempts, outcomes = {}, {}
    initialized_tools, initialized_skills, initialized_servers = [], [], []
    models = set()
    with path.open() as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if not isinstance(event, dict):
                continue
            count += 1
            if event.get("type") in ("result", "turn.completed"):
                terminal += 1
                if event.get("is_error") or str(event.get("subtype", "")).startswith("error"):
                    error_terminal += 1
                else:
                    completed_terminal += 1
            elif event.get("type") == "turn.failed":
                terminal += 1
                error_terminal += 1
            if event.get("type") == "system" and event.get("subtype") == "init":
                initialized_tools = event.get("tools", [])
                initialized_skills = event.get("skills", [])
                initialized_servers = [{"name": server.get("name"), "status": server.get("status")}
                                       for server in event.get("mcp_servers", []) if isinstance(server, dict)]
            message = event.get("message", {})
            if isinstance(message, dict) and isinstance(message.get("model"), str):
                models.add(message["model"])
            if isinstance(event.get("model"), str):
                models.add(event["model"])
            for block in message.get("content", []) if isinstance(message, dict) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    call = block.get("id") or "unkeyed-" + str(count) + "-" + str(len(attempts))
                    attempts.setdefault(call, block.get("name"))
                elif isinstance(block, dict) and block.get("type") == "tool_result" and block.get("tool_use_id"):
                    outcomes[block["tool_use_id"]] = not bool(block.get("is_error"))
            item = event.get("item", {})
            if isinstance(item, dict) and item.get("type") in ("command_execution", "mcp_tool_call", "web_search"):
                call = item.get("id") or "unkeyed-" + str(count)
                attempts.setdefault(call, item.get("tool") or item["type"])
                if event.get("type") == "item.completed":
                    result = item.get("result", {})
                    failed = (item.get("status") == "failed" or bool(item.get("error"))
                              or item.get("exit_code", 0) not in (None, 0)
                              or (isinstance(result, dict) and bool(result.get("is_error"))))
                    outcomes[call] = not failed
    tool_attempts = list(attempts.values())
    tool_completed = [name for call, name in attempts.items() if outcomes.get(call) is True]
    tool_failed = [name for call, name in attempts.items() if outcomes.get(call) is False]
    return {"event_count": count, "terminal_event_count": terminal,
            "completed_terminal_count": completed_terminal, "error_terminal_count": error_terminal,
            "tool_events": tool_attempts, "tool_events_semantics": "attempts; use completed/failure counts for acceptance",
            "tool_attempt_counts": dict(Counter(tool_attempts)),
            "tool_completed_counts": dict(Counter(tool_completed)),
            "tool_failure_counts": dict(Counter(tool_failed)),
            "unresolved_tool_attempt_count": sum(call not in outcomes for call in attempts),
            "initialized_tools": initialized_tools, "initialized_skills": initialized_skills,
            "initialized_mcp_servers": initialized_servers,
            "runtime_reported_models": sorted(models), "model_identity_evidence":
            "runtime-or-gateway-reported; upstream-unverified" if models else "not-reported"}


def launch(args) -> int:
    if args.profile not in PROFILES or not args.print or not args.prompt:
        raise HarnessError("native Muse TRIAL requires a named headless task")
    if getattr(args, "resume", None):
        raise HarnessError("native Muse TRIAL resume has not qualified")
    profiles = adoption_module("runtime_profiles")
    root = profiles.owned_destination(args.state_root / args.profile)
    meta = json.loads((root / "profile.json").read_text())
    if meta.get("status") != "trial" or meta.get("model") != MODEL:
        raise HarnessError("only the qualified subscription TRIAL route is permitted")
    actual = executable_identity(meta["runtime"], Path(meta["executable"]))
    if actual["sha256"] != meta["sha256"]:
        raise HarnessError("native runtime changed since qualification")
    memory = meta.get("memory_runtime")
    if not memory or memory_identity(Path.home()) != memory:
        raise HarnessError("complete screened memory dependency is required")
    role_metadata(args.role or "isolated-builder")
    workspace = profiles.fresh_worktree(args.repository.resolve(), args.profile)
    run = root / "runs" / uuid.uuid4().hex
    run.mkdir(mode=0o700, parents=True)
    argv = command(meta, root, workspace, args)
    environment = child_environment(root, args.profile, workspace)
    started = datetime.now(timezone.utc).isoformat()
    events = run / "events.jsonl"
    exit_code, timed_out, launch_error = 1, False, None
    with events.open("x") as stdout, (run / "stderr.log").open("x") as stderr:
        os.chmod(events, 0o600)
        os.chmod(run / "stderr.log", 0o600)
        try:
            process = subprocess.Popen(argv, cwd=workspace, env=environment,
                                       stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                       start_new_session=True)
            exit_code = process.wait(timeout=args.timeout_seconds)
        except OSError as error:
            launch_error = type(error).__name__
            exit_code = 127
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            exit_code = 124
    receipt = {"schema": "native-stack/muse-cli-harness-trial/v1", "profile": args.profile,
               "status": "trial", "role": args.role or "isolated-builder", "workspace": str(workspace),
               "requested_model": MODEL, "reasoning_effort_requested": "max",
               "runtime_version": meta["version"], "runtime_sha256": meta["sha256"],
               "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
               "exit_code": exit_code, "timed_out": timed_out, "launch_error": launch_error, "argv": argv,
               "events": str(events), **event_facts(events, meta["runtime"])}
    private_write(run / "receipt.json", json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"profile": args.profile, "receipt": str(run / "receipt.json"), "exit_code": exit_code}))
    return exit_code
