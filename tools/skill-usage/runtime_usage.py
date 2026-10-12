"""Derived invoke facts from explicitly supplied native Pi/OpenCode JSONL.

Primary contracts (upstream source, not inferred transcript mentions):
* earendil-works/pi@04566631c2b51fb688486bc1f040f60d1518c126:
  packages/coding-agent/docs/json.md (LF framing and tool execution events),
  docs/session-format.md (message entries), docs/message-types.md (toolCall,
  toolResult/isError), and src/core/tools/read.ts (the path input).
* anomalyco/opencode@53d1eabb61e21162157817bf677da0a4ad3332e3:
  packages/opencode/src/cli/cmd/run.ts:728-750 (own-session tool_use events),
  src/tool/skill.ts:8-10 (name input), src/tool/read.ts:28-29 (filePath input).
* anomalyco/opencode@4d9678a79d6367ad1257c258049075e7a2d0c6c8:
  packages/core/src/tool/mcp.ts:16-17,78-86 (server_tool sanitization and
  MCP isError becomes ToolFailure). CLI v1 JSON uses state.input.name for
  skill and state.input.filePath for read; newer internal plugin input IDs
  are not evidence of the CLI's v1 argument spelling.

Only successful completed own calls count. Repeated exports, native event and
persisted message representations are reconciled by session/call identity.
Files are read in place, never copied or hashed, and only on explicit paths.
Session/call IDs, arguments, text, output and filesystem paths are never
returned. Known skill/server inventory names are the only public count keys.
An unclassified log proves wiring; it does not establish organic invocation.
"""

from collections import Counter
from dataclasses import dataclass, field
import json
from pathlib import Path, PurePosixPath
import re
import stat

RUNTIMES = ("pi", "opencode")
MCP_NAMES = (
    "chrome-devtools", "codebase-memory", "context-mode", "ai-memory", "hindsight",
    "socraticode", "jcodemunch", "headroom", "promptfoo", "serena", "semble", "qmd",
)
VENDOR_SKILL_SOURCES = {
    name: "obra/superpowers@bb92a77741419a4ab5f06e711a283343f1ada0c3"
    for name in (
        "brainstorming", "diagnosing-superpowers", "dispatching-parallel-agents", "executing-plans",
        "finishing-a-development-branch", "receiving-code-review", "requesting-code-review",
        "subagent-driven-development", "systematic-debugging", "test-driven-development",
        "using-git-worktrees", "using-superpowers", "verification-before-completion", "writing-plans", "writing-skills",
    )
}  # pinned package skills/ inventory; metadata, not installed/copied skill text
VENDOR_SKILL_SOURCES["context-mode"] = "mksglu/context-mode@6f0cc6841c687e754059f36714a11233fda1a02b"


def mcp_server(name: str, runtime: str) -> str | None:
    """Attribute known server aliases only; never publish arbitrary log names."""
    for server in sorted(MCP_NAMES, key=len, reverse=True):
        # Inventory deployments use both '-' and '_' server aliases. Upstream
        # preserves either character; it replaces other punctuation with '_'.
        for alias in {server, server.replace("-", "_")}:
            prefix = f"mcp__{alias}__" if runtime == "pi" else f"{alias}_"
            if name.startswith(prefix) and re.fullmatch(r"[A-Za-z0-9_-]+", name[len(prefix):]):
                return server
    return None


def _identifier(value) -> bool:
    return isinstance(value, str) and bool(value)


@dataclass
class _Call:
    tool: str | None = None
    arguments: dict = field(default_factory=dict)
    result_tools: set = field(default_factory=set)
    outcomes: set = field(default_factory=set)
    conflict: bool = False

    def start(self, tool, arguments):
        if self.tool is not None and (self.tool != tool or self.arguments != arguments):
            self.conflict = True
        if self.result_tools - {tool}:
            self.conflict = True
        self.tool, self.arguments = tool, arguments

    def finish(self, tool, successful):
        if tool is not None:
            self.result_tools.add(tool)
            if self.tool is not None and self.tool != tool:
                self.conflict = True
        self.outcomes.add(successful)


class _Ledger:
    def __init__(self):
        self.calls = {}
        self.sessions = set()
        self.detached_results = set()
        self.logs_scanned = 0
        self.parse_errors = 0
        self.invalid_records = 0

    def start(self, session, call_id, tool, arguments):
        if not _identifier(call_id) or not _identifier(tool) or not isinstance(arguments, dict):
            self.invalid_records += 1
            return
        self.calls.setdefault((session, call_id), _Call()).start(tool, arguments)

    def finish(self, session, call_id, tool, is_error):
        if (not _identifier(call_id) or (tool is not None and not _identifier(tool))
                or not isinstance(is_error, bool)):
            self.invalid_records += 1
            return
        self.calls.setdefault((session, call_id), _Call()).finish(tool, not is_error)

    def pi(self, record, session):
        kind = record.get("type")
        if kind == "tool_execution_start":
            self.start(session, record.get("toolCallId"), record.get("toolName"), record.get("args"))
        elif kind == "tool_execution_end":
            is_error = record.get("isError")
            result = record.get("result")
            if isinstance(is_error, bool) and isinstance(result, dict) and result.get("isError") is True:
                is_error = True
            self.finish(session, record.get("toolCallId"), record.get("toolName"), is_error)
        elif kind in {"message", "message_end"}:
            message = record.get("message")
            if not isinstance(message, dict):
                self.invalid_records += 1
                return
            if message.get("role") == "assistant":
                content = message.get("content")
                if not isinstance(content, list):
                    self.invalid_records += 1
                    return
                stop_reason = message.get("stopReason")
                if "stopReason" in message and not isinstance(stop_reason, str):
                    self.invalid_records += 1
                    return
                if stop_reason in {"pending", "error", "aborted"}:
                    return
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "toolCall":
                        self.start(session, block.get("id"), block.get("name"), block.get("arguments"))
            elif message.get("role") == "toolResult":
                self.finish(session, message.get("toolCallId"), message.get("toolName"), message.get("isError"))

    def opencode(self, record):
        # CLI run.ts filters foreign sessions before emitting tool_use. Do not
        # promote a similar part nested in text/system/error records to a call.
        if record.get("type") != "tool_use":
            return
        part = record.get("part")
        if not isinstance(part, dict) or part.get("type") != "tool":
            self.invalid_records += 1
            return
        state = part.get("state")
        session, call_id, tool = record.get("sessionID"), part.get("callID"), part.get("tool")
        if (not isinstance(state, dict) or not _identifier(session) or not _identifier(call_id)
                or not _identifier(tool) or not isinstance(state.get("input"), dict)):
            self.invalid_records += 1
            return
        status = state.get("status")
        if not isinstance(status, str) or status not in {"completed", "error", "running", "pending"}:
            self.invalid_records += 1
            return
        if part.get("sessionID", session) != session:
            self.detached_results.add((session, call_id))
            return
        self.start(session, call_id, tool, state["input"])
        if status in {"completed", "error"}:
            metadata = state.get("metadata")
            is_error = (status == "error" or state.get("isError") is True or part.get("isError") is True
                        or (isinstance(metadata, dict) and metadata.get("isError") is True))
            self.finish(session, call_id, tool, is_error)

    def report(self, runtime, names, skillmd_hits):
        # The canonical manifest omits vendor role packages. Their pinned
        # inventory is a known public attribution set, not an arbitrary name
        # extracted from output. Successful native calls remain the oracle.
        names = set(names) | set(VENDOR_SKILL_SOURCES)
        skills, mcp = Counter(), Counter()
        completed = failed = pending = conflicts = 0
        orphans = len(self.detached_results)
        for call in self.calls.values():
            conflicts += call.conflict
            failed += False in call.outcomes
            if call.tool is None:
                orphans += bool(call.outcomes)
                continue
            pending += not call.outcomes
            if call.conflict or call.outcomes != {True}:
                continue
            completed += 1
            if runtime == "opencode" and call.tool == "skill":
                name = call.arguments.get("name")
                if isinstance(name, str) and name in names:
                    skills[name] += 1
            elif call.tool == "read":
                key = "path" if runtime == "pi" else "filePath"
                path = call.arguments.get(key)
                if isinstance(path, str) and not any(c in path for c in "\n\r\0"):
                    normalized = path.replace("\\", "/")
                    parsed = PurePosixPath(normalized)
                    if (not normalized.endswith("/") and parsed.name == "SKILL.md"
                            and parsed.parent.name in names):
                        # The existing helper walks arbitrary strings. Pass only
                        # the actual native path input, never notes or output.
                        skills.update(skillmd_hits({key: normalized}, names))
            server = mcp_server(call.tool, runtime)
            if server:
                mcp[server] += 1
        return {
            "measured": True,
            "evidence_class": "prompted_or_unclassified_native_invocation",
            "organic_use_measured": False,
            "logs_scanned": self.logs_scanned,
            "sessions_measured": len(self.sessions),
            "parse_errors": self.parse_errors,
            "invalid_records": self.invalid_records,
            "orphan_results": orphans,
            "pending_tool_calls": pending,
            "failed_tool_calls": failed,
            "conflicting_tool_calls": conflicts,
            "completed_tool_calls": completed,
            "successful_skill_uses": dict(sorted(skills.items())),
            "skill_source_attribution": {name: VENDOR_SKILL_SOURCES.get(name, "adoption/skills/manifest.json")
                                         for name in sorted(skills)},
            "successful_mcp_calls": dict(sorted(mcp.items())),
        }


def scan_opencode_export(document, names, *, skillmd_hits) -> dict:
    """Derive interactive-session counts from native `opencode export` in memory.

    No raw export is persisted. The vendor export is an info/messages envelope;
    OpenCode@53d1eabb packages/opencode/src/cli/cmd/export.ts:284-289
    exports Session.Service.messages({sessionID}) with each message's info/parts;
    completed tool parts carry the same state/callID contract as run JSONL.
    Foreign session parts and malformed exports never count as own calls.
    """
    ledger = _Ledger()
    if not isinstance(document, dict) or not isinstance(document.get("info"), dict):
        raise ValueError("invalid native export envelope")
    session = document["info"].get("id")
    messages = document.get("messages")
    if not _identifier(session) or not isinstance(messages, list):
        raise ValueError("invalid native export session")
    ledger.sessions.add(session)
    for message in messages:
        if (not isinstance(message, dict) or not isinstance(message.get("info"), dict)
                or not isinstance(message.get("parts"), list)):
            ledger.invalid_records += 1
            continue
        info = message["info"]
        if not _identifier(info.get("sessionID")) or info.get("role") not in ("assistant", "user"):
            ledger.invalid_records += 1
            continue
        if info["sessionID"] != session:
            for part in message["parts"]:
                if isinstance(part, dict) and part.get("type") == "tool" and _identifier(part.get("callID")):
                    ledger.detached_results.add((info["sessionID"], part["callID"]))
            continue
        for part in message["parts"]:
            if not isinstance(part, dict):
                ledger.invalid_records += 1
                continue
            if part.get("type") != "tool":
                continue
            if info["role"] != "assistant" or not _identifier(part.get("sessionID")):
                ledger.invalid_records += 1
                continue
            ledger.opencode({"type": "tool_use", "sessionID": session, "part": part})
    result = ledger.report("opencode", names, skillmd_hits)
    result["source_format"] = "native_opencode_export_in_memory"
    result["native_exports_measured"] = 1
    return result


def scan(logs, names, *, skillmd_hits) -> dict:
    """Read only explicit regular JSONL files; return public derived counters.

    A native session ID scopes call identities across all supplied files. Logs
    without session headers can still show calls but cannot establish a measured
    session. No timestamps are inferred from a filename or a surrounding path.
    """
    ledgers, seen_files = {}, set()
    for runtime, filename in logs:
        if runtime not in RUNTIMES:
            raise ValueError("unsupported runtime")
        path = Path(filename)
        try:
            metadata = path.stat()
            if path.suffix != ".jsonl" or path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
                raise ValueError("runtime logs must be explicit regular JSONL files")
            identity = (runtime, metadata.st_dev, metadata.st_ino)
            if identity in seen_files:
                continue
            seen_files.add(identity)
            ledger = ledgers.setdefault(runtime, _Ledger())
            ledger.logs_scanned += 1
            session = None
            # Binary line iteration splits only on LF, not Unicode separators.
            # Decode each line separately so a bad line cannot discard the log.
            with path.open("rb") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line.decode("utf-8"))
                    except (ValueError, UnicodeError):
                        ledger.parse_errors += 1
                        continue
                    if not isinstance(record, dict):
                        ledger.parse_errors += 1
                        continue
                    if not isinstance(record.get("type"), str):
                        ledger.invalid_records += 1
                        continue
                    if runtime == "pi":
                        if record.get("type") == "session":
                            session = record.get("id")
                            if _identifier(session):
                                ledger.sessions.add(session)
                            else:
                                ledger.invalid_records += 1
                                session = None
                        else:
                            ledger.pi(record, session)
                    else:
                        if _identifier(record.get("sessionID")):
                            ledger.sessions.add(record["sessionID"])
                        ledger.opencode(record)
        except OSError:
            raise ValueError("cannot read runtime log") from None
    return {runtime: ledger.report(runtime, names, skillmd_hits)
            for runtime, ledger in sorted(ledgers.items())}
