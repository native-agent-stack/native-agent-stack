"""Constants of the E1 harness, shared by e1_prepare.py, e1_run.py, e1_decide.py, e1_assert.py and e1_tests.py.

promptfooconfig.yaml states the same values for promptfoo; tests/test_e_series.py compares the two, so a change to one fails until the other follows. ASCII only.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_repo_root():
    """The repository this folder sits in (the nearest parent that holds tools/credentials/credential_run.py), or None for a copy outside one, such as a staged config directory."""
    for parent in HERE.parents:
        if (parent / "tools" / "credentials" / "credential_run.py").is_file():
            return parent
    return None


REPO_ROOT = find_repo_root()
CLIENT_VERSION = "2.1.296"  # the versioned client binary the runner and the parity cell used; the wrapper on PATH adds interactive-session flags
PROMPTFOO_MINIMUM = "0.124.0"  # copy_working_dir exists from this release (promptfoo/promptfoo@30949931ee90, src/providers/agentWorkspace.ts)
SDK_VERSION = "0.3.283"  # @anthropic-ai/claude-agent-sdk as pinned by promptfoo 0.124.0 (package.json)
MODEL = "claude-opus-5-5"
EFFORT = "medium"
BUDGET_USD = 4
FENCE_TOOLS = ["Bash", "Read", "Glob", "Grep", "ToolSearch"]
DENIED_TOOLS = ["Agent", "Task", "Workflow", "ScheduleWakeup", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"]
CHILD_ENV = {"MCP_TIMEOUT": "120000", "CLAUDE_CODE_ENABLE_TELEMETRY": "0", "DISABLE_TELEMETRY": "1", "ENABLE_CLAUDEAI_MCP_SERVERS": "false"}
# Variables that change the model, the effort or the credential route of a client session; e1_run.py removes them from the environment of the promptfoo process.
BEHAVIOUR_VARS = ["CLAUDECODE", "CLAUDE_CODE_DISABLE_ADVISOR_TOOL", "CLAUDE_CODE_EFFORT_LEVEL", "MAX_THINKING_TOKENS", "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE", "ANTHROPIC_MODEL",
                  "ANTHROPIC_SMALL_FAST_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL", "CLAUDE_CODE_MAX_OUTPUT_TOKENS", "CLAUDE_CODE_DISABLE_THINKING",
                  "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "ENABLE_TOOL_SEARCH", "CLAUDE_CONFIG_DIR"]
SERVERS = ("serena", "semble", "codebase-memory-mcp", "jcodemunch")  # the four servers every arm with servers connects
SERVER_COMMANDS = {"serena": "serena", "semble": "semble", "codebase-memory-mcp": "codebase-memory-mcp", "jcodemunch": "jcodemunch-mcp"}  # the executable of each, resolved on PATH
CODE_NAV_SERVERS = SERVERS + ("socraticode",)  # a tool named mcp__<server>__* of these counts as a code-navigation call (m1)
SCHEMA = {"type": "object", "properties": {
    "answer": {"type": "string"},
    "citations": {"type": "array", "items": {"type": "object", "properties": {"file": {"type": "string"}, "line": {"type": "integer"}}, "required": ["file", "line"]}},
    "functions": {"type": "array", "items": {"type": "string"}}}, "required": ["answer", "citations"]}

# tree directory under <root>/trees -> (commit it is checked out at, directive placed in CLAUDE.local.md or None)
TREES = {"base": ("base", None), "base-serena": ("base", "serena"), "stale": ("stale", None), "stale-path": ("stale", "path")}
# arm -> the tree its session starts in, the tree it may also read (--add-dir; the stale-start arms), whether the four servers are configured, the directive it carries
ARMS = {
    "A0a": {"tree": "stale", "add": "base", "servers": True, "directive": None},
    "A0b": {"tree": "base", "add": None, "servers": True, "directive": None},
    "A1": {"tree": "base-serena", "add": None, "servers": True, "directive": "serena"},
    "A3": {"tree": "stale-path", "add": "base", "servers": True, "directive": "path"},
    "A5": {"tree": "base", "add": None, "servers": False, "directive": None},
}
# What the pre-flight row expects a session to quote for its directive: the first sentence of the paragraph the arm carries (NONE for the others).
DIRECTIVE_FIRST_SENTENCE = {
    "serena": "This session's code tools are bound to the current directory, the worktree you work in.",
    "path": "The worktree for a task is a directory other than this session's start directory.",
}
# Files copied from this directory into <root>/config, the directory promptfoo runs from (the SDK package is resolved from there).
STAGED_FILES = ["promptfooconfig.yaml", "tasks.json", "e1_common.py", "e1_grade.py", "e1_tests.py", "e1_assert.py", "directives/serena.md", "directives/path.md"]
