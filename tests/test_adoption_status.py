"""Adoption preflight boundaries; no credentials, services, or model calls."""

import builtins
from collections import Counter
import contextlib
from datetime import date, datetime, timezone
import dis
import errno
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import platform
import re
import shutil
from shutil import which as native_which
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from unittest.mock import patch

from scripts import adoption_status
from scripts.adoption_status import (CLIENT_WIRING_KEYS, CLIENT_WIRING_LIMITATIONS, LAUNCHER_LOGIN_PATH, STACK_AGENTS_SOURCE, VENDOR_HOST_AGENTS,
                                     LAUNCHER_RESOLUTION_KEYS, LAUNCHER_RESOLUTION_LIMITATIONS, LOGIN_FILE_STATES,
                                     LOGIN_SHELL_FILES, LOGIN_SHELL_KEYS, LOGIN_SHELL_LIMITATIONS, NO_CLIENT_STATE,
                                     NO_PINNED_VERSION, PINNED_VERSION_LIMITATIONS, client_wiring,
                                     fixed_launcher_resolution, fixed_login_shell, git_revision, inspect_adoption,
                                     launcher_resolution, login_file_state, login_shell, main, pins_file_path,
                                     probe_pinned_version, signals_interrupt_probes, version_output_matches)

REPO = Path(__file__).resolve().parents[1]
# Resolved at import, before a test narrows PATH to its own directory or patches the platform.
SLEEP = native_which("sleep")
HOST_PLATFORM = {"os": platform.system().lower(), "architecture": platform.machine().lower()}
PRIVATE = "private-value-never-reported"
CLAUDE_EVENTS = ("PreToolUse", "SessionStart", "SubagentStop", "PostToolUse", "PreCompact", "Stop", "SessionEnd",
                 "SubagentStart")
CODEX_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "Stop", "SessionEnd")
CODEX_BASE = f"""model = "{PRIVATE}"

[plugins."context-mode@context-mode"]
enabled = true

[mcp_servers.serena]
command = "/opt/{PRIVATE}/bin/serena"

[mcp_servers.socraticode]
command = "/opt/{PRIVATE}/bin/node"

[mcp_servers.socraticode.env]
QDRANT_URL = "http://{PRIVATE}"

[mcp_servers.ai-memory]
url = "http://{PRIVATE}/mcp"
"""
CODEX_CONFIG = CODEX_BASE + "\n[features]\nhooks = true\n"  # as the recipe's `codex features enable hooks` writes it
SERVERS = ("serena", "socraticode", "ai-memory")
# The two Codex role carriers (adoption/agents/codex/SHA256SUMS names exactly these two files). The fixtures give each
# a text that holds PRIVATE, so a test proves the check compares bytes and lets no file text into its report.
ROLE_FILES = ("stack-researcher.toml", "stack-verifier.toml")


def role_bytes(name: str) -> bytes:
    return f"# {name}\n# {PRIVATE}\nname = \"{name[:-len('.toml')]}\"\n".encode("utf-8")


# Three Claude agent definitions standing for adoption/agents/claude (it ships 11; the check compares every *.md of the folder). Each text holds PRIVATE, so a test proves the check compares bytes and
# lets no file text into its report.
AGENT_FILES = ("evidence-reviewer.md", "source-scout.md", "stack-verifier.md")
AGENT_TOOLS = "tools: Read, Grep, Glob"


def agent_bytes(name: str) -> bytes:
    return f"---\nname: {name[:-len('.md')]}\ndescription: {PRIVATE}\n{AGENT_TOOLS}\n---\n{PRIVATE}\n".encode("utf-8")


WIRED = {
    "claude": {"rtk_hook": True, "ai_memory_hook_events": 8, "context_mode_plugin_enabled": True,
               "subagent_spawn_depth_1": True, "workflow_concurrency_set": True,
               "effort_level_env_unset": True, "agent_teams_opt_in": 0, "stack_agents_drift": 0},
    "project": {"settings_depth_and_concurrency": True, "codex_mcp_servers_present": dict.fromkeys(SERVERS, True)},
    "codex": {"rtk_instructions": True, "context_mode_plugin_enabled": True,
              "mcp_servers_present": dict.fromkeys(SERVERS, True), "hooks_feature_enabled": True,
              "ai_memory_hook_events": 7, "ai_memory_hook_events_trusted": 7, "stack_roles_matching": 2},
    "complete": True,
}
# The RTK.md that `rtk init -g --codex` (rtk 0.50.0) writes: RTK's ownership line, then the instructions.
RTK_MD = (f"<!-- rtk-owned: written by `rtk init --codex`, removed by `rtk init --codex --uninstall` -->\n\n"
          f"# RTK {PRIVATE}\n\nPrefix every shell command with `rtk`: `rtk git status`.\n")
# The same instructions pasted into AGENTS.md: rewrapped, without the ownership line.
AGENTS_INLINE = f"# {PRIVATE}\n\n# RTK {PRIVATE}\nPrefix every shell command\nwith `rtk`: `rtk git status`.\n"
# currentHash that Codex's own `codex app-server` hooks/list returned for these hooks.json handlers, each alone in
# its event (codex-cli 0.157.1, 2026-09-26, a throwaway CODEX_HOME;
# evidence/artifacts/adoption-status-truth-20260926/codex-known-answers.json): known answers for codex_hook_hashes,
# whose source is byte-identical at rust-v0.155.1.
EXAMPLE_HOOK = ("/opt/example/ai-memory --data-dir /opt/example hook --event {} --agent codex "
                "--server-url http://127.0.0.1:1")
CODEX_KNOWN_HASHES = (
    ("SessionStart", "", {"type": "command", "command": EXAMPLE_HOOK.format("session-start")},
     "sha256:4d9205412446343ca20dacc40b406615e933c2f04732fbde2cb6b51d442817df"),
    ("UserPromptSubmit", "", {"type": "command", "command": EXAMPLE_HOOK.format("user-prompt-submit")},
     "sha256:bafdaee0246ea58754e42a0dde6985508cefd06c7510da4cee65a0fd29ff6297"),
    ("SessionEnd", "", {"type": "command", "command": EXAMPLE_HOOK.format("session-end"), "timeout": 10},
     "sha256:15f2c9d33be78a0162254dd01e08e2e0c9d7d7d284fa18db9fc2203be0970642"),
    ("PreToolUse", "Bash", {"type": "command", "command": "rtk hook codex", "timeout": 30,
                            "statusMessage": "rewriting"},
     "sha256:fd1656dbf26529a5398e69be444b6c6bf660a49f7a42ed33f5504b237ae5080a"),
    ("PostToolUse", "mcp__.*", {"type": "command", "command": EXAMPLE_HOOK.format("post-tool-use"), "async": True,
                                "additionalContextLimit": 4000},
     "sha256:717174d53c367657dfdeeb4663aa1a5b2eca26383a58d2c3d17c3b261007af34"),
    ("Stop", None, {"type": "command", "command": "echo 'quoted \"text\" \u00e9'", "commandWindows": "echo win"},
     "sha256:7e3fccfd4440e1614122d1f033d78f688ce70f27cbb06f81d233ed9bb02b47e1"),
)


def ai_memory_group(event: str) -> dict:
    command = f"/opt/{PRIVATE}/ai-memory --data-dir /opt/{PRIVATE} hook --event {event} --server-url http://{PRIVATE}"
    return {"matcher": "", "hooks": [{"type": "command", "command": command}]}


STOP_COMMAND = json.dumps(ai_memory_group("Stop")["hooks"][0]["command"])


def stop_handler(extra: str = "", command: str = STOP_COMMAND) -> str:
    return '{"type": "command", "command": ' + command + extra + '}'


def stop_group(handler: str | None = None, extra: str = "") -> str:
    return '{"matcher": "", "hooks": [' + (handler or stop_handler()) + ']' + extra + '}'


def codex_hooks_text(stop: str | None = None, *, top: str = "", events: str = "") -> str:
    """The wired Codex hooks.json as JSON text, for shapes json.dumps cannot write: its Stop groups replaced by
    ``stop``, ``top`` put before the "hooks" member and ``events`` after the Stop member."""
    other = json.dumps({event: [ai_memory_group(event)] for event in CODEX_EVENTS if event != "Stop"})[1:-1]
    return '{%s"hooks": {%s, "Stop": [%s]%s}}' % (top, other, stop or stop_group(), events)


def nested_arrays(depth: int) -> str:
    return "[" * depth + "]" * depth


# Codex 0.157.1's own verdicts on hooks.json shapes: `codex app-server` hooks/list in a throwaway CODEX_HOME, run
# 2026-09-26 on one Stop hook each (evidence/artifacts/adoption-status-truth-20260926/codex-parse-oracle.jsonl, a
# local integration check, not an upstream test). Here each shape changes only the Stop part of a wired file.
# Codex's serde parse fails on these, so it loads no hook from the file (its warning quoted in brief).
CODEX_REJECTED_HOOKS_FILES = (
    ("repeated top-level hooks (duplicate field `hooks`)", codex_hooks_text(top='"hooks": {}, ')),
    ("repeated event (duplicate field `Stop`)", codex_hooks_text(events=', "Stop": []')),
    ("repeated group field (duplicate field `matcher`)",
     codex_hooks_text('{"matcher": "", "matcher": "", "hooks": [' + stop_handler() + ']}')),
    ("repeated handler field (duplicate field `command`)",
     codex_hooks_text(stop_group('{"type": "command", "command": "echo", "command": ' + STOP_COMMAND + '}'))),
    ("repeated type tag (duplicate field `type`)",
     codex_hooks_text(stop_group('{"type": "command", "type": "command", "command": ' + STOP_COMMAND + '}'))),
    ("both commandWindows spellings (duplicate field `commandWindows`)",
     codex_hooks_text(stop_group(stop_handler(', "commandWindows": "a", "command_windows": "b"')))),
    ("NaN in an unknown handler field (expected value)", codex_hooks_text(stop_group(stop_handler(', "x": NaN')))),
    ("Infinity in an unknown group field (expected value)", codex_hooks_text(stop_group(extra=', "x": Infinity'))),
    ("lone surrogate in the command (unexpected end of hex escape)",
     codex_hooks_text(stop_group(stop_handler(command=STOP_COMMAND[:-1] + ' \\ud800"')))),
    ("lone surrogate in an unknown handler field", codex_hooks_text(stop_group(stop_handler(', "x": "\\ud800"')))),
    ("lone surrogate in an unknown group key", codex_hooks_text(stop_group(extra=', "\\ud800": 1'))),
    ("lone surrogate in the matcher", codex_hooks_text('{"matcher": "\\ud800", "hooks": [' + stop_handler() + ']}')),
    ("128 nested arrays inside a handler (recursion limit exceeded)",
     codex_hooks_text(stop_group(stop_handler(', "x": ' + nested_arrays(122))))),
    ("timeout 2^64 (invalid type: map, expected u64)",
     codex_hooks_text(stop_group(stop_handler(', "timeout": 18446744073709551616')))),
    ("timeout 5.0 (invalid type: map, expected u64)", codex_hooks_text(stop_group(stop_handler(', "timeout": 5.0')))),
    ("type tag as a variant index (expected variant identifier)",
     codex_hooks_text(stop_group('{"type": 0, "command": ' + STOP_COMMAND + '}'))),
    ("MCP input whose last duplicate is null (not representable as TOML)", codex_hooks_text(
        stop_group() + ', {"hooks": [{"type": "mcp_tool", "server": "s", "tool": "t", '
                       '"input": {"k": 1, "k": null}}]}')),
    ("group array with an element left over (trailing characters)",
     codex_hooks_text('[null, [' + stop_handler() + '], 1]')),
    # Codex cannot hash a timeout beyond a TOML integer: hook discovery panics and hooks/list never answers.
    ("timeout 2^63 (no answer)", codex_hooks_text(stop_group(stop_handler(', "timeout": 9223372036854775808')))),
)
# ... and parses these, loading the Stop hook with the same key and hash as the wired file's.
CODEX_ACCEPTED_HOOKS_FILES = (
    ("repeated unknown event", codex_hooks_text(events=', "Future": 1, "Future": 2')),
    ("repeated unknown group field", codex_hooks_text(stop_group(extra=', "x": 1, "x": 2'))),
    ("repeated unknown handler field", codex_hooks_text(stop_group(stop_handler(', "x": 1, "x": 2')))),
    ("lone surrogate in an unknown group field", codex_hooks_text(stop_group(extra=', "x": {"\\ud800": "\\udc00"}'))),
    ("lone surrogate in an unknown event", codex_hooks_text(events=', "Future": "\\ud800"')),
    ("1e400 in an unknown handler field", codex_hooks_text(stop_group(stop_handler(', "x": 1e400')))),
    ("400-digit integer in an unknown handler field",
     codex_hooks_text(stop_group(stop_handler(', "x": 1' + "0" * 400)))),
    ("127 nested arrays inside a handler", codex_hooks_text(stop_group(stop_handler(', "x": ' + nested_arrays(121))))),
    ("300 nested arrays in an unknown group field", codex_hooks_text(stop_group(extra=', "x": ' + nested_arrays(296)))),
    ("group as an array", codex_hooks_text('[null, [' + stop_handler() + ']]')),
    ("handler as an array", codex_hooks_text(stop_group('["command", ' + STOP_COMMAND + ']'))),
    ("MCP input whose last duplicate is set, with integers beyond i64", codex_hooks_text(
        stop_group() + ', {"hooks": [{"type": "mcp_tool", "server": "s", "tool": "t", '
                       '"input": {"k": null, "k": 9223372036854775808, "n": -9223372036854775809}}]}')),
    ("context limit 2^63 on Stop, which drops it",
     codex_hooks_text(stop_group(stop_handler(', "additionalContextLimit": 9223372036854775808')))),
    ("file and events as arrays", '[null, [' + ", ".join(
        json.dumps([ai_memory_group(event)] if event in CODEX_EVENTS else [])
        for event in adoption_status.CODEX_HOOK_EVENTS) + ']]'),
)
# Matchers whose loading Codex 0.157.1 decided in the same run (one PreToolUse group each). The check decides a
# matcher built from constructs both regex engines parse alike ...
CODEX_LOADS_MATCHERS = ("", "*", "Bash", "Bash|Edit", "mcp__.*", "^Bash$", "(Bash|Edit)", "(?:Bash)", "[A-Z]\\w+",
                        "\\bBash\\b", "Bash.*?", "a|", "()", "\\.", "\\-", "\\~", "\\n", "[a-]", "[^a-z]", "[\\]]",
                        "é+", "a b", "\\AB", "(^)*", "(a|)*", "[*+?]", "[-]", "a$b", "(|)", "[^\\W]")
CODEX_SKIPS_MATCHERS = ("(", ")", "*a", "a|*", "(*)", "[a", "[z-a]", "a\\")
# ... and answers null (undecided) for the rest, whichever way Codex went (Codex's verdict in the comment).
UNDECIDED_MATCHERS = ("(?#note)Bash", "(?a)Bash", "\\0Bash", "(B)?(?(1)ash|x)",  # Codex skips; Python compiles
                      "\\N{LATIN SMALL LETTER A}", "(?=a)", "a\\Z", "a{,2}", "a{", "[\\b]",  # the same
                      "a**", "^*", "\\b*", "a\\z", "\\p{L}", "(?<n>a)", "[a--b]", "\\x{41}",  # Codex loads; not Python
                      "(?i)bash", "a{2}", "}", "[[:alpha:]]", "\\x41", "\\/", "a*+", "[]a]")  # both load


def leaves(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from leaves(item)
    else:
        yield value


class Descendant:
    """A child that a probe script starts in the background and leaves running: it writes "x" to a FIFO it
    keeps open on descriptor 3 and its PID to a file, then execs sleep, keeping the probe's stdout and stderr
    open too. The FIFO reads end-of-file only once no process holds it, which observes the kill without
    depending on when a reaper collects the zombie."""

    def __init__(self, test: unittest.TestCase, directory: Path):
        self.fifo, self.pidfile = directory / "descendant.fifo", directory / "descendant.pid"
        os.mkfifo(self.fifo)
        self.reader = os.open(self.fifo, os.O_RDONLY | os.O_NONBLOCK)  # first, so the writer's open never blocks
        test.addCleanup(self.cleanup)

    def script(self, then: str) -> str:
        """A probe script body: start the descendant, wait until it has written its marker, then ``then``."""
        return (f"/bin/sh -c 'printf x >&3; echo $$ > \"$1\"; exec \"$2\" 30' sh '{self.pidfile}' '{SLEEP}' "
                f"3> '{self.fifo}' &\nwhile [ ! -s '{self.pidfile}' ]; do :; done\n{then}")

    def started(self) -> bool:
        return self.pidfile.is_file() and self.pidfile.read_text().strip().isdigit()

    def gone(self, seconds: float = 10.0) -> bool:
        """Whether the FIFO reached end-of-file after the marker, within ``seconds``."""
        seen, deadline = b"", time.monotonic() + seconds
        while True:
            try:
                chunk = os.read(self.reader, 64)
            except BlockingIOError:  # still held open: the descendant is alive
                chunk = None
            if chunk:
                seen += chunk
            elif chunk == b"" and seen:
                return True
            elif time.monotonic() > deadline:
                return False
            else:
                time.sleep(0.02)

    def cleanup(self):
        os.close(self.reader)
        with contextlib.suppress(OSError, ValueError):  # already gone, or never started
            os.kill(int(self.pidfile.read_text()), signal.SIGKILL)


# Sets each named signal's disposition, then execs the rest of argv. exec keeps an ignored signal ignored and
# resets a handled one to its default, so the program starts with exactly these dispositions, whatever the
# test runner inherited (a background job of a non-interactive shell starts with SIGINT ignored; nohup, SIGHUP).
EXEC_WITH_DISPOSITIONS = ("import json, os, signal, sys\n"
                          "for name, action in json.loads(sys.argv[1]).items():\n"
                          "    signal.signal(getattr(signal, name),\n"
                          "                  signal.SIG_IGN if action == 'ignore' else signal.SIG_DFL)\n"
                          "os.execv(sys.argv[2], sys.argv[2:])\n")

# Runs the --pinned-versions CLI in this process and raises a signal on itself at one point inside
# run_version_probe, where a signal from outside would land only by chance. "created": after the probe's fork,
# once its background child runs, but before subprocess.Popen has returned the process. "cleanup": as the kill of
# the probe's group begins, after the test has interrupted the check once. Each point says on stderr that it was
# reached. argv: the point, the signal number, the background child's PID file, the checkout, the CLI's arguments.
INTERRUPT_INSIDE_A_PROBE = """\
import os, signal, subprocess, sys, time
point, signum, pidfile, checkout = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
sys.path.insert(0, checkout)
from scripts import adoption_status


def child_runs():
    try:
        with open(pidfile) as handle:
            return handle.read().strip().isdigit()
    except OSError:
        return False


def interrupt(where):
    print(f"raised {signal.Signals(signum).name} {where}", file=sys.stderr, flush=True)
    signal.raise_signal(signum)


if point == "created":
    class Popen(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if os.path.basename(self.args[0]) == "forking-tool":
                deadline = time.monotonic() + 20
                while not child_runs() and time.monotonic() < deadline:
                    time.sleep(0.01)
                interrupt("after the probe's fork, before subprocess.Popen returned")

    subprocess.Popen = Popen
else:
    kill_group = adoption_status.signal_group

    def signal_group(group, sent):
        if sent == signal.SIGKILL:
            interrupt("as the kill of the probe's group began")
        kill_group(group, sent)

    adoption_status.signal_group = signal_group
sys.exit(adoption_status.main(sys.argv[5:]))
"""


class AdoptionStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "adoption").mkdir()
        (self.root / "recipes").mkdir()
        (self.root / "recipes/README.md").write_text("Native recipe\n")
        self.path = self.root / "adoption/manifest.json"
        self.manifest = {
            "schema_version": 1,
            "supported_platforms": [{"os": "linux", "architecture": "x86_64", "python": "3.13"}],
            "profiles": [{"id": "foundation-cpu", "label": "CPU foundation",
                          "required_commands": ["qmd"], "component_ids": ["qmd"],
                          "recipe_paths": ["recipes/README.md"]}],
            "default_profile": "foundation-cpu",
            "source": {"baseline_commit": "a" * 40,
                       "repository": "https://github.com/example/reference"},
        }
        self.save()
        self.enter = contextlib.ExitStack()
        self.addCleanup(self.enter.close)
        self.enter.enter_context(patch("scripts.adoption_status.platform.system", return_value="Linux"))
        self.enter.enter_context(patch("scripts.adoption_status.platform.machine", return_value="x86_64"))
        self.enter.enter_context(patch("scripts.adoption_status.sys.version_info", (3, 13, 7)))
        self.which = self.enter.enter_context(patch("scripts.adoption_status.shutil.which", return_value="/private/bin/qmd"))
        self.git = self.enter.enter_context(patch("scripts.adoption_status.git_revision", return_value="a" * 40))

    def save(self):
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def inspect(self, profiles=None):
        return inspect_adoption(self.path, self.root, profiles)

    def test_present_prerequisites_do_not_claim_runtime_acceptance(self):
        result = self.inspect()
        self.assertEqual(result["status"], "prerequisites_present")
        self.assertEqual(result["git"]["comparison"], "baseline_matches")
        self.assertEqual(result["platform"]["python"], "3.13.7")
        self.assertFalse(result["runtime_acceptance_verified"])
        self.assertNotIn("/private/bin", json.dumps(result))
        self.which.assert_called_once_with("qmd")

    def test_missing_command_and_recipe_are_reported(self):
        self.which.return_value = None
        (self.root / "recipes/README.md").unlink()
        result = self.inspect()
        self.assertEqual(result["status"], "prerequisites_missing")
        self.assertFalse(result["profiles"][0]["commands"][0]["present"])
        self.assertFalse(result["profiles"][0]["recipes"][0]["present"])

    def prepare_loki_check(self):
        self.manifest["profiles"][0].update(required_commands=["loki"], component_ids=["loki"])
        self.save()
        directory = self.root / "bin"
        directory.mkdir()
        self.enter.enter_context(patch.dict("os.environ", {"PATH": str(directory)}))
        self.which.side_effect = native_which
        return directory

    def test_loki_archive_basename_is_presence_only_without_execution(self):
        directory = self.prepare_loki_check()
        marker = self.root / "must-not-run"
        executable = directory / "loki-linux-amd64"
        executable.write_text(f"#!/bin/sh\nprintf executed > '{marker}'\n")
        executable.chmod(0o755)
        with patch("scripts.adoption_status.subprocess.run") as run:
            result = self.inspect()
        self.assertEqual(result["status"], "prerequisites_present")
        self.assertEqual(result["profiles"][0]["commands"], [{"name": "loki", "present": True}])
        self.assertFalse(result["runtime_acceptance_verified"])
        self.assertFalse(marker.exists())
        self.assertNotIn(str(directory), json.dumps(result))
        run.assert_not_called()

    def test_conventional_loki_name_is_preferred(self):
        directory = self.prepare_loki_check()
        for name in ("loki", "loki-linux-amd64"):
            executable = directory / name
            executable.write_text("#!/bin/sh\nexit 1\n")
            executable.chmod(0o755)
        self.assertEqual(self.inspect()["status"], "prerequisites_present")
        self.which.assert_called_once_with("loki")

    def test_loki_archive_for_another_host_is_not_accepted(self):
        directory = self.prepare_loki_check()
        executable = directory / "loki-linux-amd64"
        executable.write_text("#!/bin/sh\nexit 1\n")
        executable.chmod(0o755)
        for system, machine in (("Darwin", "x86_64"), ("Windows", "AMD64"), ("Linux", "aarch64")):
            with self.subTest(system=system, machine=machine), \
                    patch("scripts.adoption_status.platform.system", return_value=system), \
                    patch("scripts.adoption_status.platform.machine", return_value=machine):
                self.assertFalse(self.inspect()["profiles"][0]["commands"][0]["present"])

    def test_loki_missing_or_nonexecutable_archive_is_not_present(self):
        directory = self.prepare_loki_check()
        executable = directory / "loki-linux-amd64"
        for exists in (False, True):
            with self.subTest(file_exists=exists):
                if exists:
                    executable.write_text("not an executable\n")
                    executable.chmod(0o644)
                result = self.inspect()
                self.assertEqual(result["status"], "prerequisites_missing")
                self.assertFalse(result["profiles"][0]["commands"][0]["present"])

    def test_unknown_profile_fails_without_probing_commands(self):
        result = self.inspect(["unknown"])
        self.assertEqual(result["manifest"]["status"], "invalid")
        self.assertIn("unknown profile", result["errors"][0])
        self.which.assert_not_called()

    def test_explicit_profiles_do_not_require_unselected_commands(self):
        self.manifest["profiles"].append({"id": "gpu", "label": "GPU",
            "required_commands": ["vllm"], "component_ids": ["vllm"], "recipe_paths": []})
        self.save()
        result = self.inspect(["foundation-cpu", "foundation-cpu"])
        self.assertEqual(len(result["profiles"]), 1)
        self.which.assert_called_once_with("qmd")

    def test_unsupported_platform_or_python_blocks_readiness(self):
        for target, value in [("platform.machine", "arm64"), ("sys.version_info", (3, 12, 9))]:
            override = (patch("scripts.adoption_status." + target, return_value=value)
                        if target.startswith("platform") else patch("scripts.adoption_status." + target, value))
            with self.subTest(target=target), override:
                result = self.inspect()
                self.assertEqual(result["status"], "prerequisites_missing")
                self.assertFalse(result["platform"]["supported"])

    def test_unsafe_recipe_references_are_rejected_before_probing(self):
        for reference in (".", "../outside", "/etc/passwd", "recipes/../secret", "recipes//README.md", "C:\\secret", "recipes/./README.md"):
            with self.subTest(reference=reference):
                self.manifest["profiles"][0]["recipe_paths"] = [reference]
                self.save()
                self.assertEqual(self.inspect()["manifest"]["status"], "invalid")
        self.which.assert_not_called()

    def test_symlink_recipe_and_symlink_parent_are_rejected(self):
        recipe = self.root / "recipes/README.md"
        recipe.unlink()
        recipe.symlink_to(self.path)
        self.assertEqual(self.inspect()["manifest"]["status"], "invalid")
        recipe.unlink()
        recipe.parent.rmdir()
        recipe.parent.symlink_to(self.root / "adoption", target_is_directory=True)
        self.assertEqual(self.inspect()["manifest"]["status"], "invalid")

    def test_malformed_shapes_and_command_paths_are_rejected(self):
        for mutate in (lambda d: d.update(schema_version=True),
                       lambda d: d.update(profiles=[]),
                       lambda d: d["profiles"][0].update(required_commands=["/bin/qmd"]),
                       lambda d: d["profiles"][0].update(required_commands=["qmd --help"]),
                       lambda d: d["source"].update(baseline_commit="not-a-revision"),
                       lambda d: d["source"].update(repository="https://secret@example.com/repo")):
            with self.subTest(mutate=mutate):
                original = json.loads(json.dumps(self.manifest))
                mutate(self.manifest)
                self.save()
                self.assertEqual(self.inspect()["manifest"]["status"], "invalid")
                self.manifest = original

    def test_invalid_json_and_duplicate_keys_are_bounded_errors(self):
        for raw in ('{"bad":', '{"schema_version":1,"schema_version":1}'):
            self.path.write_text(raw)
            result = self.inspect()
            self.assertEqual(result["manifest"]["status"], "invalid")
            self.assertNotIn(str(self.root), json.dumps(result))

    def test_git_difference_is_information_not_failed_acceptance(self):
        self.git.return_value = "b" * 40
        result = self.inspect()
        self.assertEqual(result["status"], "prerequisites_present")
        self.assertEqual(result["git"]["comparison"], "baseline_differs")
        self.git.return_value = None
        self.assertEqual(self.inspect()["git"]["comparison"], "unavailable")

    def test_json_cli_does_not_emit_environment_or_credential_paths(self):
        output = io.StringIO()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "never-publish-this", "HF_TOKEN": "nor-this"}), contextlib.redirect_stdout(output):
            code = main(["--manifest", str(self.path), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertNotIn("never-publish-this", output.getvalue())
        self.assertNotIn("nor-this", output.getvalue())
        self.assertNotIn(str(self.root), output.getvalue())
        self.assertEqual(payload["manifest"]["status"], "valid")

    def test_missing_manifest_returns_exit_two_and_help_does_not_read(self):
        self.path.unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--manifest", str(self.path), "--json"]), 2)
        with patch("scripts.adoption_status.inspect_adoption") as inspect, contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        inspect.assert_not_called()

    def test_component_namespace_ids_are_supported(self):
        self.manifest["profiles"][0]["component_ids"] = ["affaan-m/ECC"]
        self.save()
        self.assertEqual(self.inspect()["status"], "prerequisites_present")

    def test_native_git_output_is_strict_and_timeout_is_bounded(self):
        with patch("scripts.adoption_status.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, f"{self.root}\n{'a' * 40}\n", "")
            self.assertEqual(git_revision(self.root), "a" * 40)
            self.assertEqual(run.call_args.kwargs["timeout"], 5)
            run.return_value = subprocess.CompletedProcess([], 0, f"/another/repository\n{'a' * 40}\n", "")
            self.assertIsNone(git_revision(self.root))
            run.return_value = subprocess.CompletedProcess([], 1, "untrusted output", "private/path/secret")
            self.assertIsNone(git_revision(self.root))
            run.side_effect = subprocess.TimeoutExpired(["git"], 5)
            self.assertIsNone(git_revision(self.root))

    def test_a_symlink_loop_in_root_returns_none_not_an_uncaught_runtimeerror(self):
        # Path.resolve() on Python before 3.13 raises RuntimeError for a
        # symlink loop (3.13+ instead returns the unresolved remainder);
        # either way git_revision must return None, not propagate it.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            link_a = tmp_path / "a"
            link_b = tmp_path / "b"
            os.symlink(link_b, link_a)
            os.symlink(link_a, link_b)
            self.assertIsNone(git_revision(link_a))

    def test_manifest_outside_explicit_root_is_rejected(self):
        result = inspect_adoption(self.path, self.root / "recipes")
        self.assertEqual(result["manifest"]["status"], "invalid")
        self.assertIn("inside the repository root", result["errors"][0])

    def test_client_wiring_is_opt_in(self):
        with patch("scripts.adoption_status.client_wiring") as wiring, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--manifest", str(self.path), "--json"]), 0)
        wiring.assert_not_called()
        payload = json.loads(output.getvalue())
        self.assertNotIn("client_wiring", payload)
        self.assertIn(NO_CLIENT_STATE, payload["limitations"])

    def test_client_wiring_flag_reports_and_restates_the_limitations(self):
        canned = {"claude": {"rtk_hook": True}, "complete": False}
        with patch("scripts.adoption_status.client_wiring", return_value=canned) as wiring, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--manifest", str(self.path), "--json", "--client-wiring"]), 0)
        wiring.assert_called_once_with(self.root.resolve(), None)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["client_wiring"], canned)
        self.assertNotIn(NO_CLIENT_STATE, payload["limitations"])
        self.assertEqual(payload["limitations"][-2:], CLIENT_WIRING_LIMITATIONS)
        with patch("scripts.adoption_status.client_wiring", return_value=canned), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            # The exit code stays the prerequisite result; incomplete wiring is reported, not exited on.
            self.assertEqual(main(["--manifest", str(self.path), "--client-wiring"]), 0)
        self.assertIn('Client wiring complete: false\nClient wiring: {"claude": {"rtk_hook": true}}\n',
                      output.getvalue())

    def test_client_wiring_is_reported_even_for_an_invalid_manifest(self):
        self.path.write_text("{", encoding="utf-8")
        home = self.root / "empty-home"
        home.mkdir()
        result = inspect_adoption(self.path, self.root, with_client_wiring=True, env={"HOME": str(home)})
        self.assertEqual(result["manifest"]["status"], "invalid")
        self.assertEqual(set(result["client_wiring"]), {*CLIENT_WIRING_KEYS, "complete"})
        self.assertIs(result["client_wiring"]["complete"], False)
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_login_shell_is_opt_in(self):
        with patch("scripts.adoption_status.login_shell") as shell, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--manifest", str(self.path), "--json"]), 0)
        shell.assert_not_called()
        payload = json.loads(output.getvalue())
        self.assertNotIn("login_shell", payload)
        self.assertFalse(set(LOGIN_SHELL_LIMITATIONS) & set(payload["limitations"]))

    def test_login_shell_flag_reports_and_restates_the_limitations(self):
        home = self.root / "home"
        home.mkdir()
        (home / ".profile").write_text(f"export {PRIVATE}=1\n")
        with patch.dict("os.environ", {"HOME": str(home)}), contextlib.redirect_stdout(io.StringIO()) as output:
            # The exit code stays the prerequisite result: a reported login shell state is never exited on.
            self.assertEqual(main(["--manifest", str(self.path), "--json", "--login-shell"]), 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["login_shell"], {"bash_profile": "absent", "bash_login": "absent", "profile": "content",
                                                  "first_read": "profile", "profile_read": True})
        self.assertEqual(payload["limitations"][-1:], LOGIN_SHELL_LIMITATIONS)
        self.assertIn(NO_CLIENT_STATE, payload["limitations"])
        (home / ".bash_profile").write_bytes(b"")
        with patch.dict("os.environ", {"HOME": str(home)}), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--manifest", str(self.path), "--login-shell"]), 0)
        self.assertIn('Login shell: {"bash_login": "absent", "bash_profile": "empty", "first_read": "bash_profile", '
                      '"profile": "content", "profile_read": false}\n', output.getvalue())
        self.assertNotIn(PRIVATE, output.getvalue())
        self.assertNotIn(str(home), output.getvalue())

    def test_login_shell_is_reported_even_for_an_invalid_manifest(self):
        self.path.write_text("{", encoding="utf-8")
        home = self.root / "empty-home"
        home.mkdir()
        result = inspect_adoption(self.path, self.root, with_login_shell=True, env={"HOME": str(home)})
        self.assertEqual(result["manifest"]["status"], "invalid")
        self.assertEqual(set(result["login_shell"]), set(LOGIN_SHELL_KEYS))
        self.assertIs(result["login_shell"]["profile_read"], False)
        self.assertEqual(result["launcher_resolution"], {"status": "not_run", "flag": "--launcher-resolution"})
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_login_shell_composes_with_client_wiring_and_pinned_versions(self):
        home = self.root / "compose-home"
        home.mkdir()
        canned = {"claude": {"rtk_hook": True}, "complete": False}
        with patch("scripts.adoption_status.client_wiring", return_value=canned):
            result = inspect_adoption(self.path, self.root, with_client_wiring=True, with_pinned_versions=True,
                                      with_login_shell=True, env={"HOME": str(home)})
        self.assertEqual(result["limitations"][-1:], LOGIN_SHELL_LIMITATIONS)
        self.assertNotIn(NO_CLIENT_STATE, result["limitations"])
        self.assertNotIn(NO_PINNED_VERSION, result["limitations"])
        for statement in CLIENT_WIRING_LIMITATIONS + PINNED_VERSION_LIMITATIONS + LOGIN_SHELL_LIMITATIONS:
            self.assertIn(statement, result["limitations"])
        self.assertEqual(result["client_wiring"], canned)
        self.assertIn("login_shell", result)


class LoginShellTests(unittest.TestCase):
    """--login-shell against real files in a temporary HOME, and against the real bash login search: the static
    model must name the file bash reads, for every combination of startup-file states, from metadata alone."""

    def setUp(self):
        self.fresh_home()

    def fresh_home(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        return self.home

    def build(self, states: dict) -> None:
        """Materialize one state per startup file; a file with content exports MARK=<its key>."""
        for key, state in states.items():
            target = self.home / LOGIN_SHELL_FILES[key]
            line = f"MARK={key}; export MARK\n"
            if state == "empty":
                target.write_bytes(b"")
            elif state == "content":
                target.write_text(line)
            elif state == "directory":
                target.mkdir()
            elif state == "dangling":
                target.symlink_to(self.home / "nowhere")
            elif state == "linked":
                (self.home / f"real-{key}").write_text(line)
                target.symlink_to(self.home / f"real-{key}")
            elif state == "unreadable":
                target.write_text(line)
                target.chmod(0)
                self.addCleanup(target.chmod, 0o600)
            elif state == "devnull":
                target.symlink_to("/dev/null")
            elif state == "loop":
                target.symlink_to(target.name)
            elif state == "fifo":
                os.mkfifo(target)

    def report(self, states: dict) -> dict:
        self.build(states)
        return login_shell({"HOME": str(self.home)})

    def test_a_host_without_startup_files_reads_none(self):
        self.assertEqual(self.report({}), {"bash_profile": "absent", "bash_login": "absent", "profile": "absent",
                                          "first_read": None, "profile_read": False})

    def test_profile_alone_is_read(self):
        result = self.report({"profile": "content"})
        self.assertEqual((result["first_read"], result["profile_read"]), ("profile", True))

    def test_an_empty_bash_profile_hides_a_real_profile(self):
        # The 2026-09-29 incident: an empty ~/.bash_profile left by a sandbox scrub ended the login search, so
        # ~/.profile and its PATH were never read and `exec claude` exited 127.
        self.assertEqual(self.report({"bash_profile": "empty", "profile": "content"}),
                         {"bash_profile": "empty", "bash_login": "absent", "profile": "content",
                          "first_read": "bash_profile", "profile_read": False})

    def test_an_empty_bash_login_hides_a_real_profile_too(self):
        result = self.report({"bash_login": "empty", "profile": "content"})
        self.assertEqual((result["first_read"], result["profile_read"]), ("bash_login", False))

    def test_a_bash_profile_with_content_may_hand_off_and_that_is_not_read(self):
        result = self.report({"bash_profile": "content", "profile": "content"})
        self.assertEqual((result["first_read"], result["profile_read"]), ("bash_profile", None))

    def test_a_directory_or_unreadable_file_ends_the_search(self):
        for state in ("directory", *(() if os.geteuid() == 0 else ("unreadable",))):
            with self.subTest(state=state):
                self.fresh_home()
                result = self.report({"bash_profile": state, "profile": "content"})
                self.assertEqual((result["bash_profile"], result["first_read"], result["profile_read"]),
                                 ("unusable", "bash_profile", False))

    def test_symlinks_follow_the_target_as_open_does(self):
        result = self.report({"bash_profile": "dangling", "profile": "content"})
        self.assertEqual((result["bash_profile"], result["first_read"], result["profile_read"]),
                         ("absent", "profile", True))
        self.fresh_home()
        result = self.report({"bash_profile": "linked", "profile": "content"})
        self.assertEqual((result["bash_profile"], result["first_read"], result["profile_read"]),
                         ("content", "bash_profile", None))

    def test_a_device_reads_as_empty_and_a_fifo_blocks_and_both_end_the_search(self):
        # Verified against the real shell, not assumed: bash reads /dev/null as an empty file without a message, and a FIFO
        # blocks the login shell at open(); the model calls both unusable and reports that ~/.profile is not reached.
        for state in ("devnull", "fifo"):
            with self.subTest(state=state):
                self.fresh_home()
                result = self.report({"bash_profile": state, "profile": "content"})
                self.assertEqual((result["bash_profile"], result["first_read"], result["profile_read"]),
                                 ("unusable", "bash_profile", False))
                if not native_which("bash"):
                    continue
                run = lambda: subprocess.run([native_which("bash"), "-l", "-c", 'printf %s "$MARK"'], env={"HOME": str(self.home)},
                                             capture_output=True, text=True, timeout=3)
                if state == "fifo":
                    with self.assertRaises(subprocess.TimeoutExpired):
                        run()
                else:
                    self.assertEqual(run().stdout, "")

    def bash_mark(self, home: Path) -> str:
        return subprocess.run([native_which("bash"), "-l", "-c", 'printf %s "$MARK"'], env={"HOME": str(home)}, capture_output=True,
                              text=True, timeout=30).stdout

    def test_an_unusable_profile_is_reached_but_not_read(self):
        for state in ("directory", "devnull", *(() if os.geteuid() == 0 else ("unreadable",))):
            with self.subTest(state=state):
                self.fresh_home()
                result = self.report({"profile": state})
                self.assertEqual((result["profile"], result["first_read"], result["profile_read"]), ("unusable", "profile", False))
                if native_which("bash"):
                    self.assertEqual(self.bash_mark(self.home), "")

    def test_other_stat_errors_end_the_search_as_bash_open_errors_do(self):
        # ELOOP, ENOTDIR and EACCES are neither ENOENT nor a readable file, so bash's open() fails with an error that ends the search
        # (evalfile_internal returns -1): the state is unusable for each, checked against the real shell where one is installed.
        self.report({"bash_profile": "loop", "profile": "content"})
        loop = login_shell({"HOME": str(self.home)})
        self.assertEqual((loop["bash_profile"], loop["first_read"], loop["profile_read"]), ("unusable", "bash_profile", False))
        if native_which("bash"):
            self.assertEqual(self.bash_mark(self.home), "")
        regular = self.fresh_home() / "a-file-not-a-directory"
        regular.write_text("x\n")
        as_file = login_shell({"HOME": str(regular)})
        self.assertEqual((as_file["bash_profile"], as_file["bash_login"], as_file["profile"], as_file["profile_read"]),
                         ("unusable", "unusable", "unusable", False))
        if native_which("bash"):
            self.assertEqual(self.bash_mark(regular), "")
        if os.geteuid() != 0:
            closed = self.fresh_home() / "closed"
            closed.mkdir()
            (closed / ".profile").write_text("MARK=profile; export MARK\n")
            closed.chmod(0)
            self.addCleanup(closed.chmod, 0o700)
            searched = login_shell({"HOME": str(closed)})
            self.assertEqual((searched["bash_profile"], searched["first_read"], searched["profile_read"]), ("unusable", "bash_profile", False))
            if native_which("bash"):
                self.assertEqual(self.bash_mark(closed), "")

    def test_a_home_that_cannot_be_determined_falls_back_to_the_root_like_bash(self):
        # bash sets current_user.home_dir to "/" when getpwuid fails (shell.c), so a user with no home entry reads /.bash_profile,
        # /.bash_login and /.profile; the model stats those names and a traceback is never the answer.
        asked = []

        def record(path):
            asked.append(str(path))
            return "absent"

        with patch("scripts.adoption_status.Path.home", side_effect=RuntimeError("Could not determine home directory.")), \
                patch("scripts.adoption_status.login_file_state", side_effect=record):
            result = login_shell({})
            payload = inspect_adoption(REPO / "adoption/manifest.json", REPO, with_login_shell=True, env={})
        self.assertEqual(sorted(set(asked)), ["/.bash_login", "/.bash_profile", "/.profile"])
        self.assertEqual(result, {"bash_profile": "absent", "bash_login": "absent", "profile": "absent", "first_read": None, "profile_read": False})
        self.assertEqual(payload["login_shell"], result)

    def test_home_comes_from_the_passwd_entry_when_the_environment_has_none(self):
        # An environment with no HOME must not be read as the working directory: Path.home() (the passwd entry) is the second source.
        passwd_home = self.home
        (passwd_home / ".profile").write_text("MARK=profile; export MARK\n")
        elsewhere = self.fresh_home()
        (elsewhere / ".bash_profile").write_text("x\n")   # the current directory would find this one if it were read
        cwd = os.getcwd()
        os.chdir(elsewhere)
        self.addCleanup(os.chdir, cwd)
        with patch("scripts.adoption_status.Path.home", return_value=passwd_home):
            result = login_shell({})
        self.assertEqual((result["bash_profile"], result["profile"], result["first_read"], result["profile_read"]), ("absent", "content", "profile", True))

    def test_an_empty_profile_that_the_search_reaches_is_reached(self):
        # profile_read means the search reaches a usable ~/.profile: an empty one counts, since bash reads it and finds nothing to run.
        result = self.report({"profile": "empty"})
        self.assertEqual((result["profile"], result["first_read"], result["profile_read"]), ("empty", "profile", True))

    def test_only_metadata_is_used_and_no_content_or_path_is_reported(self):
        for name in LOGIN_SHELL_FILES.values():
            (self.home / name).write_text(f"export {PRIVATE}=1\n")

        def refuse(*_args, **_kwargs):
            raise AssertionError("a startup file must never be opened or read")

        with patch("builtins.open", refuse), patch("io.open", refuse), patch("os.open", refuse), \
                patch.object(Path, "open", refuse), patch.object(Path, "read_text", refuse), \
                patch.object(Path, "read_bytes", refuse):
            result = login_shell({"HOME": str(self.home)})
        self.assertEqual(result["first_read"], "bash_profile")
        self.assertNotIn(PRIVATE, json.dumps(result))
        self.assertNotIn(str(self.home), json.dumps(result))

    def test_home_defaults_to_the_process_home_and_a_missing_one_is_not_an_error(self):
        (self.home / ".profile").write_text("x\n")
        with patch.dict("os.environ", {"HOME": str(self.home)}):
            self.assertEqual(login_shell()["first_read"], "profile")
        self.assertIsNone(login_shell({"HOME": str(self.home / "missing")})["first_read"])

    def test_the_result_shape_is_fixed_and_a_stray_value_is_refused(self):
        good = self.report({"bash_profile": "empty", "profile": "content"})
        self.assertTrue(fixed_login_shell(good))
        self.assertEqual(tuple(good), LOGIN_SHELL_KEYS)
        for broken in ({**good, "extra": True}, {**good, "profile": "/private/dir/.profile"},
                       {**good, "first_read": "/private/dir"}, {**good, "profile_read": 1},
                       {key: value for key, value in good.items() if key != "profile_read"}, [], None):
            with self.subTest(broken=broken):
                self.assertFalse(fixed_login_shell(broken))
        with patch("scripts.adoption_status.login_file_state", return_value="export SECRET=1"), \
                self.assertRaises(AssertionError):
            login_shell({"HOME": str(self.home)})
        self.assertEqual(set(LOGIN_FILE_STATES), {"absent", "empty", "content", "unusable"})
        self.assertEqual(login_file_state(self.home / "nothing-here"), "absent")

    @unittest.skipUnless(native_which("bash"), "needs bash")
    def test_the_static_model_names_the_file_real_bash_reads(self):
        # Every combination of the three files over the states below (a FIFO blocks the shell and has its own test), each run through `bash -l`: the MARK bash
        # exports names the file it read, which is the first existing file when that has content and nothing when it
        # is empty or unusable. The negative control (an empty file taken as absent) must disagree with bash
        # somewhere, or this comparison could not tell a wrong model from a right one.
        states = ["absent", "empty", "content", "directory", "dangling", "linked", "devnull",
                  *(() if os.geteuid() == 0 else ("unreadable",))]
        bash = native_which("bash")
        keys = tuple(LOGIN_SHELL_FILES)
        combinations = mismatches = control_disagreements = 0
        for combo in itertools.product(states, repeat=len(keys)):
            self.fresh_home()
            result = self.report(dict(zip(keys, combo)))
            observed = subprocess.run([bash, "-l", "-c", 'printf %s "$MARK"'], env={"HOME": str(self.home)},
                                      capture_output=True, text=True, timeout=30).stdout
            first = result["first_read"]
            # first_read is the first startup file that exists and can be opened (not absent, not a dangling link); the exported MARK is empty for 344 of the 512
            # combinations, so the MARK alone cannot tell a wrong first_read from a right one.
            truth_first = next((key for key, state in zip(keys, combo) if state not in ("absent", "dangling")), None)
            self.assertEqual(first, truth_first, combo)
            predicted = first if first is not None and result[first] == "content" else ""
            control_first = next((key for key in keys if result[key] not in ("absent", "empty")), None)
            control = control_first if control_first is not None and result[control_first] == "content" else ""
            combinations += 1
            mismatches += observed != predicted
            control_disagreements += observed != control
            if result["profile_read"] is False:
                self.assertNotEqual(observed, "profile", combo)
            if result["profile_read"] is True:
                self.assertEqual(observed, "profile" if result["profile"] == "content" else "", combo)
        self.assertEqual(combinations, len(states) ** len(keys))
        self.assertEqual(mismatches, 0)
        self.assertGreater(control_disagreements, 0)


@unittest.skipUnless(shutil.which("bash", path=LAUNCHER_LOGIN_PATH), "needs bash in a system directory")
class LauncherResolutionTests(unittest.TestCase):
    """--launcher-resolution against a real Bash login shell in a temporary HOME: the managed ~/.profile block of
    tools/adoption/managed_block.py makes `claude` the ecosystem launcher, and each way a login shell misses it
    (the 2026-09-29 empty ~/.bash_profile, a profile without the block, a PATH only this process has) is reported as
    not the launcher. The stand-in launcher records a run, which must never happen."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.eco = self.base / "eco-root"  # outside HOME, as an ECO_INSTALL_ROOT may be
        (self.eco / "bin").mkdir(parents=True)
        self.ran = self.base / "launcher-ran"
        self.launcher = self.eco / "bin" / "claude"
        self.launcher.write_text(f"#!/bin/sh\n: > '{self.ran}'\n")
        self.launcher.chmod(0o755)
        self.env = {"HOME": str(self.home), "ECO_INSTALL_ROOT": str(self.eco)}

    def write_profile_block(self):
        sys.path.insert(0, str(REPO / "tools" / "adoption"))
        self.addCleanup(sys.path.remove, str(REPO / "tools" / "adoption"))
        import managed_block
        (self.home / ".profile").write_text(managed_block.merged_profile("umask 022\n", str(self.eco), str(self.home)))

    def check(self, result):
        self.assertTrue(fixed_launcher_resolution(result), result)
        self.assertEqual(tuple(result), LAUNCHER_RESOLUTION_KEYS)
        text = json.dumps(result)
        for private in (str(self.base), PRIVATE):
            self.assertNotIn(private, text)
        self.assertFalse(self.ran.exists(), "claude itself must never run")
        return result

    def test_the_managed_profile_block_makes_claude_the_ecosystem_launcher(self):
        self.write_profile_block()
        result = self.check(launcher_resolution(self.env))
        self.assertEqual(result, {"resolution": "ecosystem_launcher", "path": "$ECO_ROOT/bin/claude",
                                  "is_ecosystem_launcher": True,
                                  "launcher_sha256": hashlib.sha256(self.launcher.read_bytes()).hexdigest()})

    def test_an_empty_bash_profile_hides_the_block(self):
        self.write_profile_block()
        (self.home / ".bash_profile").write_bytes(b"")
        result = self.check(launcher_resolution(self.env))
        self.assertIs(result["is_ecosystem_launcher"], False)
        self.assertIn(result["resolution"], ("not_found", "other"))

    def test_this_processs_path_does_not_answer_for_the_login_shell(self):
        (self.home / ".profile").write_text(f"export {PRIVATE}=1\n")
        result = self.check(launcher_resolution({**self.env, "PATH": f"{self.eco}/bin:/usr/bin:/bin"}))
        self.assertIs(result["is_ecosystem_launcher"], False)
        self.write_profile_block()
        self.assertIs(self.check(launcher_resolution(self.env))["is_ecosystem_launcher"], True)

    def test_a_path_outside_the_anchors_or_a_function_is_withheld(self):
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "claude").write_text("#!/bin/sh\nexit 0\n")
        (elsewhere / "claude").chmod(0o755)
        (self.home / ".profile").write_text(f'PATH="{elsewhere}:$PATH"; export PATH\n')
        result = self.check(launcher_resolution(self.env))
        self.assertEqual((result["resolution"], result["path"]), ("other", None))
        (self.home / ".profile").write_text("claude() { :; }\n")
        result = self.check(launcher_resolution(self.env))
        self.assertEqual((result["resolution"], result["path"]), ("other", None))

    def test_a_path_under_home_is_shown_relative_to_it(self):
        native = self.home / ".local" / "bin"
        native.mkdir(parents=True)
        (native / "claude").write_text("#!/bin/sh\nexit 0\n")
        (native / "claude").chmod(0o755)
        (self.home / ".profile").write_text('PATH="$HOME/.local/bin:$PATH"; export PATH\n')
        result = self.check(launcher_resolution(self.env))
        self.assertEqual((result["resolution"], result["path"]), ("other", "$HOME/.local/bin/claude"))

    def test_a_blocking_startup_file_is_bounded(self):
        os.mkfifo(self.home / ".bash_profile")
        started = time.monotonic()
        result = self.check(launcher_resolution(self.env, seconds=1))
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual(result["resolution"], "unavailable")

    def test_no_launcher_has_no_sha256_and_no_bash_is_unavailable(self):
        self.launcher.unlink()
        self.assertIsNone(self.check(launcher_resolution(self.env))["launcher_sha256"])
        with patch("scripts.adoption_status.shutil.which", return_value=None):
            self.assertEqual(self.check(launcher_resolution(self.env))["resolution"], "unavailable")

    def test_the_result_shape_is_fixed_and_a_stray_value_is_refused(self):
        good = {"resolution": "other", "path": "$HOME/.local/bin/claude", "is_ecosystem_launcher": False,
                "launcher_sha256": None}
        self.assertTrue(fixed_launcher_resolution(good))
        for broken in ({**good, "path": "/mnt/c/Users/example/claude"}, {**good, "path": str(self.home)},
                       {**good, "is_ecosystem_launcher": True}, {**good, "resolution": "maybe"},
                       {**good, "launcher_sha256": "abc"}, {**good, "extra": 1},
                       {key: value for key, value in good.items() if key != "path"}, None):
            with self.subTest(broken=broken):
                self.assertFalse(fixed_launcher_resolution(broken))

    def test_the_flag_is_opt_in_separate_from_login_shell_and_restates_its_limitation(self):
        manifest = REPO / "adoption/manifest.json"
        with patch("scripts.adoption_status.launcher_resolution") as probe, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            main(["--manifest", str(manifest), "--json", "--login-shell"])
        probe.assert_not_called()
        payload = json.loads(output.getvalue())
        # --login-shell never executes a login file, so it names the flag that does instead of leaving the key out.
        self.assertEqual(payload["launcher_resolution"], {"status": "not_run", "flag": "--launcher-resolution"})
        self.assertEqual(payload["limitations"][-1:], LOGIN_SHELL_LIMITATIONS)
        with patch("scripts.adoption_status.launcher_resolution") as probe, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            main(["--manifest", str(manifest), "--login-shell"])
        probe.assert_not_called()
        self.assertIn('Launcher resolution: {"flag": "--launcher-resolution", "status": "not_run"}\n', output.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main(["--manifest", str(manifest), "--json"])
        self.assertNotIn("launcher_resolution", json.loads(output.getvalue()))  # nothing asked, nothing stated
        self.write_profile_block()
        with patch.dict("os.environ", self.env), contextlib.redirect_stdout(io.StringIO()) as output:
            main(["--manifest", str(manifest), "--json", "--login-shell", "--launcher-resolution"])
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["launcher_resolution"]["resolution"], "ecosystem_launcher")
        self.assertEqual(payload["limitations"][-2:], LOGIN_SHELL_LIMITATIONS + LAUNCHER_RESOLUTION_LIMITATIONS)
        with patch.dict("os.environ", self.env), contextlib.redirect_stdout(io.StringIO()) as output:
            main(["--manifest", str(manifest), "--launcher-resolution"])
        self.assertIn('Launcher resolution: {"is_ecosystem_launcher": true, "launcher_sha256": "', output.getvalue())
        self.assertNotIn(str(self.base), output.getvalue())
        self.assertFalse(self.ran.exists())


class PinnedVersionProbeTests(unittest.TestCase):
    """probe_pinned_version/version_output_matches units, against a real tiny script on PATH (never a
    fake subprocess): never execs a non-"exec" method, exact and minimum matching, a failing probe never
    matches, a missing command, malformed command string or timeout is unchecked rather than raising, and
    the probe's whole process group is killed on timeout and once it exits."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.bin = Path(temporary.name)
        self.enter = contextlib.ExitStack()
        self.addCleanup(self.enter.close)
        self.enter.enter_context(patch.dict("os.environ", {"PATH": str(self.bin)}))
        self.enter.enter_context(patch("scripts.adoption_status.shutil.which", side_effect=native_which))

    def script(self, name: str, body: str) -> None:
        executable = self.bin / name
        executable.write_text(f"#!/bin/sh\n{body}\n")
        executable.chmod(0o755)

    def test_exact_match_reports_checked_and_matched(self):
        self.script("gh", "printf 'gh version 2.101.0 (2026-09-22)\\n'")
        entry = {"version": "2.101.0", "version_probe": {"method": "exec", "command": "gh", "args": ["--version"]}}
        self.assertEqual(probe_pinned_version(entry),
                          {"pinned_version": "2.101.0", "checked": True, "matches_pin": True})

    def test_exact_mismatch_is_checked_and_not_matched(self):
        self.script("gh", "printf 'gh version 2.100.0\\n'")
        entry = {"version": "2.101.0", "version_probe": {"method": "exec", "command": "gh", "args": ["--version"]}}
        self.assertEqual(probe_pinned_version(entry),
                          {"pinned_version": "2.101.0", "checked": True, "matches_pin": False})

    def test_minimum_match_is_a_floor_not_a_ceiling(self):
        self.script("claude", "printf 'claude-code 2.1.290\\n'")
        entry = {"version": "2.1.284",
                 "version_probe": {"method": "exec", "command": "claude", "match": "minimum", "args": ["--version"]}}
        self.assertTrue(probe_pinned_version(entry)["matches_pin"])
        self.script("claude", "printf 'claude-code 2.1.100\\n'")
        self.assertFalse(probe_pinned_version(entry)["matches_pin"])

    def test_npm_metadata_method_is_never_executed(self):
        self.script("context-mode", "printf 'never run\\n'; exit 1")
        entry = {"version": "1.0.169", "version_probe": {"method": "npm-metadata", "note": "starts a server"}}
        with patch("scripts.adoption_status.subprocess.Popen") as popen:
            result = probe_pinned_version(entry)
        popen.assert_not_called()
        self.assertEqual(result, {"pinned_version": "1.0.169", "checked": False, "matches_pin": None})

    def test_an_undeclared_future_method_is_also_never_executed(self):
        self.script("future-tool", "printf 'never run\\n'; exit 1")
        entry = {"version": "9.9.9",
                 "version_probe": {"method": "some-future-method", "command": "future-tool", "args": ["--version"]}}
        with patch("scripts.adoption_status.subprocess.Popen") as popen:
            result = probe_pinned_version(entry)
        popen.assert_not_called()
        self.assertFalse(result["checked"])

    def test_a_command_not_on_path_is_unchecked_not_an_error(self):
        entry = {"version": "1.0.0",
                 "version_probe": {"method": "exec", "command": "definitely-not-on-any-path-xyz", "args": []}}
        self.assertEqual(probe_pinned_version(entry), {"pinned_version": "1.0.0", "checked": False, "matches_pin": None})

    def test_a_malformed_command_string_is_rejected_before_exec(self):
        for command in ("rm -rf /", "/bin/sh", "../escape", ""):
            with self.subTest(command=command):
                entry = {"version": "1.0.0", "version_probe": {"method": "exec", "command": command, "args": []}}
                with patch("scripts.adoption_status.subprocess.Popen") as popen:
                    result = probe_pinned_version(entry)
                popen.assert_not_called()
                self.assertFalse(result["checked"])

    def test_a_hanging_probe_times_out_and_is_unchecked(self):
        # A shell built-in loop only: PATH is scoped to this test's own bin dir, so an external "sleep"
        # binary would not be found on it (exit 127, not a hang) -- ":" and "while" need no PATH lookup.
        self.script("slow-tool", "while :; do :; done")
        entry = {"version": "1.0.0", "version_probe": {"method": "exec", "command": "slow-tool", "args": [],
                                                        "timeout_seconds": 0.2}}
        self.assertEqual(probe_pinned_version(entry), {"pinned_version": "1.0.0", "checked": False, "matches_pin": None})

    def test_a_failing_probe_never_matches_even_when_its_diagnostics_name_the_pin(self):
        # bootstrap-linux.sh reports any nonzero exit as "FAILED (exit N)" before it looks at the output.
        entry = {"version": "1.2.3", "version_probe": {"method": "exec", "command": "tool", "args": ["--version"]}}
        for stream in ("", " >&2"):
            with self.subTest(stream=stream or "stdout"):
                self.script("tool", f"printf 'tool 1.2.3: cannot open its data directory\\n'{stream}; exit 42")
                self.assertEqual(probe_pinned_version(entry),
                                 {"pinned_version": "1.2.3", "checked": True, "matches_pin": False})
                self.script("tool", f"printf 'tool 1.2.3: cannot open its data directory\\n'{stream}")
                self.assertTrue(probe_pinned_version(entry)["matches_pin"])  # the same output, exit 0

    def test_stdout_and_stderr_are_searched_as_two_streams(self):
        # As the bootstrap greps two files: a stdout without a final newline does not run into stderr.
        self.script("tool", "printf 'tool 1.2.3'; printf '4 warnings\\n' >&2")
        entry = {"version": "1.2.3", "version_probe": {"method": "exec", "command": "tool", "args": []}}
        self.assertTrue(probe_pinned_version(entry)["matches_pin"])

    @unittest.skipUnless(SLEEP, "needs a sleep executable")
    def test_a_timeout_kills_the_probe_s_whole_process_group(self):
        descendant = Descendant(self, self.bin)
        self.script("forking-tool", descendant.script("wait"))
        entry = {"version": "1.2.3", "version_probe": {"method": "exec", "command": "forking-tool", "args": [],
                                                        "timeout_seconds": 1}}
        self.assertEqual(probe_pinned_version(entry), {"pinned_version": "1.2.3", "checked": False, "matches_pin": None})
        self.assertTrue(descendant.started(), "the probe's background child never ran")
        self.assertTrue(descendant.gone(), "the probe's background child outlived the timeout")

    @unittest.skipUnless(SLEEP, "needs a sleep executable")
    def test_a_probe_s_leftover_descendants_are_killed_once_it_exits(self):
        # The leftover child also holds the probe's stdout and stderr open; the result must not wait for it.
        descendant = Descendant(self, self.bin)
        self.script("leaky-tool", descendant.script("printf 'leaky-tool 1.2.3\\n'"))
        entry = {"version": "1.2.3", "version_probe": {"method": "exec", "command": "leaky-tool", "args": [],
                                                        "timeout_seconds": 10}}
        started = time.monotonic()
        self.assertEqual(probe_pinned_version(entry), {"pinned_version": "1.2.3", "checked": True, "matches_pin": True})
        self.assertLess(time.monotonic() - started, 8)
        self.assertTrue(descendant.started(), "the probe's background child never ran")
        self.assertTrue(descendant.gone(), "the probe's background child outlived the probe")

    def test_version_output_matches_rules(self):
        self.assertTrue(version_output_matches("2.101.0", "exact", "gh version 2.101.0 (2026-09-22)\n"))
        self.assertFalse(version_output_matches("2.101.0", "exact", "gh version 2.100.0\n"))
        self.assertTrue(version_output_matches("2.1.284", "minimum", "claude-code 2.1.284\n"))
        self.assertTrue(version_output_matches("2.1.284", "minimum", "claude-code 2.2.0\n"))
        self.assertFalse(version_output_matches("2.1.284", "minimum", "claude-code 2.1.100\n"))
        self.assertFalse(version_output_matches("2.1.284", "minimum", "no version here\n"))

    def test_exact_is_bounded_by_non_version_characters_like_the_bootstrap(self):
        # bootstrap-linux.sh anchors "exact" with (^|[^0-9.])...([^0-9.]|$); a bare substring would match these.
        self.assertFalse(version_output_matches("2.10", "exact", "v12.10.0\n"))
        self.assertFalse(version_output_matches("1.0.0", "exact", "tool 21.0.0\n"))
        self.assertFalse(version_output_matches("0.49.0", "exact", "rtk 0.49.0.1\n"))
        self.assertTrue(version_output_matches("2.8.3", "exact", "qmd 2.8.3 (facd35e)"))
        self.assertTrue(version_output_matches("0.49.0", "exact", "first line\nrtk 0.49.0\n"))

    def test_minimum_with_a_non_numeric_part_is_not_a_match_and_never_raises(self):
        # bootstrap-linux.sh version_at_least returns 1 for a non-numeric part instead of failing.
        self.assertFalse(version_output_matches("2.0.0.dev0", "minimum", "Serena 2.0.0\n"))
        # As in the bootstrap, the observed version is the first dotted number, so ".dev0" is not part of it.
        self.assertTrue(version_output_matches("2.0.0", "minimum", "Serena 2.0.0.dev0\n"))
        self.assertTrue(version_output_matches("1.2", "minimum", "tool 1.2.0\n"))
        self.assertFalse(version_output_matches("1.0", "unknown-rule", "tool 1.0\n"))


class PinnedVersionsCheckTests(unittest.TestCase):
    """--pinned-versions end to end: opt-in, value-free JSON shape, and the swapped limitation."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "adoption").mkdir()
        (self.root / "recipes").mkdir()
        (self.root / "recipes/README.md").write_text("Native recipe\n")
        self.path = self.root / "adoption/manifest.json"
        self.manifest = {
            "schema_version": 1,
            "supported_platforms": [{"os": "linux", "architecture": "x86_64", "python": "3.13"}],
            "profiles": [{"id": "foundation-cpu", "label": "CPU foundation",
                          "required_commands": ["qmd"], "component_ids": ["qmd", "context-mode", "unpinned-tool"],
                          "recipe_paths": ["recipes/README.md"]}],
            "default_profile": "foundation-cpu",
            "source": {"baseline_commit": "a" * 40, "repository": "https://github.com/example/reference"},
        }
        self.path.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.pins = self.root / "adoption/pins-linux-x86_64.json"
        self.pins.write_text(json.dumps({"schema_version": 1, "platform": "linux-x86_64", "tools": [
            {"id": "qmd", "version": "2.8.3",
             "version_probe": {"method": "exec", "command": "qmd", "args": ["--version"]}},
            {"id": "context-mode", "version": "1.0.169", "version_probe": {"method": "npm-metadata"}},
        ]}), encoding="utf-8")
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        executable = bin_dir / "qmd"
        executable.write_text("#!/bin/sh\nprintf 'qmd 2.8.3\\n'\n")
        executable.chmod(0o755)
        self.enter = contextlib.ExitStack()
        self.addCleanup(self.enter.close)
        self.enter.enter_context(patch.dict("os.environ", {"PATH": str(bin_dir)}))
        self.enter.enter_context(patch("scripts.adoption_status.platform.system", return_value="Linux"))
        self.enter.enter_context(patch("scripts.adoption_status.platform.machine", return_value="x86_64"))
        self.enter.enter_context(patch("scripts.adoption_status.sys.version_info", (3, 13, 7)))
        self.enter.enter_context(patch("scripts.adoption_status.shutil.which", side_effect=native_which))
        self.enter.enter_context(patch("scripts.adoption_status.git_revision", return_value="a" * 40))

    def test_pinned_versions_is_opt_in(self):
        with patch("scripts.adoption_status.subprocess.Popen") as popen:
            result = inspect_adoption(self.path, self.root)
        popen.assert_not_called()
        self.assertEqual(result["profiles"][0].keys(), {"id", "commands", "recipes", "status"})
        self.assertNotIn("pinned_versions_match", result)
        self.assertIn(NO_PINNED_VERSION, result["limitations"])

    def test_pinned_versions_reports_matched_unchecked_and_absent(self):
        result = inspect_adoption(self.path, self.root, with_pinned_versions=True)
        self.assertEqual(result["profiles"][0]["pinned_versions"], [
            {"id": "qmd", "pinned_version": "2.8.3", "checked": True, "matches_pin": True},
            {"id": "context-mode", "pinned_version": "1.0.169", "checked": False, "matches_pin": None},
            {"id": "unpinned-tool", "pinned_version": None, "checked": False, "matches_pin": None},
        ])
        self.assertEqual(result["profiles"][0]["pinned_versions_summary"],
                         {"matched": ["qmd"], "mismatched": [], "unchecked": ["context-mode", "unpinned-tool"]})
        self.assertIs(result["pinned_versions_match"], True)  # unchecked components do not count either way
        self.assertNotIn(NO_PINNED_VERSION, result["limitations"])
        self.assertEqual(result["limitations"][-1:], PINNED_VERSION_LIMITATIONS)

    def test_a_mismatch_surfaces_at_the_top_while_status_and_exit_stay_the_prerequisite_result(self):
        (self.root / "bin/qmd").write_text("#!/bin/sh\nprintf 'qmd 2.9.0\\n'\n")
        result = inspect_adoption(self.path, self.root, with_pinned_versions=True)
        self.assertEqual(result["profiles"][0]["pinned_versions_summary"],
                         {"matched": [], "mismatched": ["qmd"], "unchecked": ["context-mode", "unpinned-tool"]})
        self.assertIs(result["pinned_versions_match"], False)
        self.assertEqual((result["status"], result["errors"]), ("prerequisites_present", []))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--manifest", str(self.path), "--repo-root", str(self.root), "--pinned-versions"])
        self.assertEqual(code, 0)
        self.assertIn("pinned versions: 0 matched, mismatched: qmd, unchecked: context-mode, unpinned-tool\n"
                      "Pinned versions match: false\n", output.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main(["--manifest", str(self.path), "--repo-root", str(self.root), "--pinned-versions", "--json"])
        self.assertIs(json.loads(output.getvalue())["pinned_versions_match"], False)

    def test_pinned_versions_match_is_absent_without_the_flag_and_null_when_nothing_was_checked(self):
        self.assertNotIn("pinned_versions_match", inspect_adoption(self.path, self.root))
        self.pins.unlink()
        self.assertIsNone(inspect_adoption(self.path, self.root, with_pinned_versions=True)["pinned_versions_match"])

    def test_an_absent_pins_file_reports_every_component_unchecked_not_an_error(self):
        self.pins.unlink()
        result = inspect_adoption(self.path, self.root, with_pinned_versions=True)
        self.assertTrue(all(item["checked"] is False and item["matches_pin"] is None
                            for item in result["profiles"][0]["pinned_versions"]))

    def test_a_malformed_pins_file_reports_every_component_unchecked_not_an_error(self):
        for body in ("{not json", "[]", '{"tools": {}}', '{"tools": [1, "x", null]}',
                     '{"tools": [{"version": "1.0"}]}', '{"tools": [{"id": "rtk"}]}'):
            with self.subTest(body=body):
                self.pins.write_text(body, encoding="utf-8")
                result = inspect_adoption(self.path, self.root, with_pinned_versions=True)
                self.assertTrue(all(item["checked"] is False and item["matches_pin"] is None
                                    for item in result["profiles"][0]["pinned_versions"]))

    def test_client_wiring_and_pinned_versions_compose(self):
        canned = {"claude": {"rtk_hook": True}, "complete": False}
        with patch("scripts.adoption_status.client_wiring", return_value=canned):
            result = inspect_adoption(self.path, self.root, with_client_wiring=True, with_pinned_versions=True)
        self.assertNotIn(NO_CLIENT_STATE, result["limitations"])
        self.assertNotIn(NO_PINNED_VERSION, result["limitations"])
        self.assertEqual(result["limitations"][-1:], PINNED_VERSION_LIMITATIONS)
        self.assertIn("client_wiring", result)
        self.assertIn("pinned_versions", result["profiles"][0])

    def test_cli_json_and_text_report_pinned_versions(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--manifest", str(self.path), "--repo-root", str(self.root), "--json", "--pinned-versions"])
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("pinned_versions", payload["profiles"][0])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main(["--manifest", str(self.path), "--repo-root", str(self.root), "--pinned-versions"])
        self.assertIn("pinned versions: 1 matched, unchecked: context-mode, unpinned-tool", output.getvalue())

    def test_pinned_versions_output_is_value_free(self):
        result = inspect_adoption(self.path, self.root, with_pinned_versions=True)
        rendered = json.dumps(result)
        self.assertNotIn(str(self.root), rendered)
        for item in result["profiles"][0]["pinned_versions"]:
            for key, value in item.items():
                self.assertTrue(value is None or isinstance(value, (bool, str)), repr((key, value)))


class DatedHoldTests(unittest.TestCase):
    """--pinned-versions with a pin's dated holds (docs/decisions/2026-10-04-codex-dated-holds.md). Synthetic: a real
    tiny script on PATH stands in for codex. A probe that names a hold's version is held before the hold's until date
    and mismatched, with the expiry stated, on and after it (an OSV-Scanner ignoreUntil's rule); any other version is
    drift as before, and a malformed hold or a failing probe never turns drift into a hold."""

    PLATFORM_DEPENDENCY = {
        "name": "codex-linux-x64", "resolved_package": "@openai/codex", "version": "0.160.0-linux-x64",
        "url": "https://registry.npmjs.org/@openai/codex/-/codex-0.160.0-linux-x64.tgz",
        "sha256": "1" * 64, "integrity": "sha512-" + "A" * 86 + "==", "checksum_ref": "synthetic fixture",
        "installed_binary_check": {"path": "vendor/bin/codex", "sha256": "2" * 64},
    }
    HOLD = {"version": "0.159.3", "until": "2026-11-04", "reason": "X18: synthetic reason",
            "url": "https://registry.npmjs.org/@openai/codex/-/codex-0.159.3.tgz", "sha256": "0" * 64,
            "platform_dependency": {
                **PLATFORM_DEPENDENCY, "version": "0.159.3-linux-x64",
                "url": "https://registry.npmjs.org/@openai/codex/-/codex-0.159.3-linux-x64.tgz",
                "sha256": "3" * 64, "integrity": "sha512-" + "B" * 86 + "==",
                "installed_binary_check": {"path": "vendor/bin/codex", "sha256": "4" * 64},
            }}
    BEFORE, ON, AFTER = date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 5)
    HELD_LINE = "    codex: 0.159.3 held until 2026-11-04 (X18: synthetic reason)\n"
    EXPIRED_LINE = "    codex: 0.159.3 hold expired 2026-11-04 (X18: synthetic reason); reported as drift\n"

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "adoption").mkdir()
        (self.root / "recipes").mkdir()
        (self.root / "recipes/README.md").write_text("Native recipe\n")
        self.path = self.root / "adoption/manifest.json"
        self.path.write_text(json.dumps({
            "schema_version": 1,
            "supported_platforms": [{"os": "linux", "architecture": "x86_64", "python": "3.13"}],
            "profiles": [{"id": "foundation-cpu", "label": "CPU foundation", "required_commands": ["codex"],
                          "component_ids": ["codex"], "recipe_paths": ["recipes/README.md"]}],
            "default_profile": "foundation-cpu",
            "source": {"baseline_commit": "a" * 40, "repository": "https://github.com/example/reference"},
        }), encoding="utf-8")
        self.pins = self.root / "adoption/pins-linux-x86_64.json"
        self.write_pin([dict(self.HOLD)])
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.codex_prints("0.159.3")
        self.enter = contextlib.ExitStack()
        self.addCleanup(self.enter.close)
        self.enter.enter_context(patch.dict("os.environ", {"PATH": str(self.bin)}))
        self.enter.enter_context(patch("scripts.adoption_status.platform.system", return_value="Linux"))
        self.enter.enter_context(patch("scripts.adoption_status.platform.machine", return_value="x86_64"))
        self.enter.enter_context(patch("scripts.adoption_status.sys.version_info", (3, 13, 7)))
        self.enter.enter_context(patch("scripts.adoption_status.shutil.which", side_effect=native_which))
        self.enter.enter_context(patch("scripts.adoption_status.git_revision", return_value="a" * 40))

    def write_pin(self, holds) -> None:
        self.pins.write_text(json.dumps({"schema_version": 1, "platform": "linux-x86_64", "tools": [
            {"id": "codex", "version": "0.160.0", "holds": holds, "platform_dependency": self.PLATFORM_DEPENDENCY,
             "version_probe": {"method": "exec", "command": "codex", "args": ["--version"]}}]}), encoding="utf-8")

    def codex_prints(self, version: str, status: int = 0) -> None:
        executable = self.bin / "codex"
        executable.write_text(f"#!/bin/sh\nprintf 'codex-cli {version}\\n'\nexit {status}\n")
        executable.chmod(0o755)

    def report(self, today: date) -> dict:
        return inspect_adoption(self.path, self.root, with_pinned_versions=True, today=today)

    def text(self, today: date) -> str:
        output = io.StringIO()
        with patch("scripts.adoption_status.utc_today", return_value=today), contextlib.redirect_stdout(output):
            code = main(["--manifest", str(self.path), "--repo-root", str(self.root), "--pinned-versions"])
        self.assertEqual(code, 0)  # a hold, held or expired, leaves the exit code the prerequisite result
        return output.getvalue()

    def test_a_hold_version_before_until_is_held_not_drift(self):
        result = self.report(self.BEFORE)
        self.assertEqual(result["profiles"][0]["pinned_versions"], [
            {"id": "codex", "pinned_version": "0.160.0", "checked": True, "matches_pin": False,
             "hold_version": "0.159.3", "hold_until": "2026-11-04", "hold_reason": "X18: synthetic reason",
             "hold_expired": False}])
        self.assertEqual(result["profiles"][0]["pinned_versions_summary"],
                         {"matched": [], "mismatched": [], "unchecked": [], "held": ["codex"]})
        self.assertIs(result["pinned_versions_match"], True)
        self.assertIn("  pinned versions: 0 matched, held: codex\n" + self.HELD_LINE + "Pinned versions match: true\n",
                      self.text(self.BEFORE))

    def test_on_and_after_until_the_hold_is_drift_with_the_expiry_stated(self):
        for today in (self.ON, self.AFTER):
            with self.subTest(today=today.isoformat()):
                result = self.report(today)
                item = result["profiles"][0]["pinned_versions"][0]
                self.assertEqual((item["matches_pin"], item["hold_until"], item["hold_expired"]),
                                 (False, "2026-11-04", True))
                self.assertEqual(result["profiles"][0]["pinned_versions_summary"],
                                 {"matched": [], "mismatched": ["codex"], "unchecked": []})
                self.assertIs(result["pinned_versions_match"], False)
                self.assertIn("  pinned versions: 0 matched, mismatched: codex\n" + self.EXPIRED_LINE
                              + "Pinned versions match: false\n", self.text(today))

    def test_any_other_version_is_drift_as_before(self):
        # "exact" is bounded by non-version characters, so 0.159.30 and 10.159.3 do not name the hold 0.159.3.
        for version in ("0.159.2", "0.159.30", "10.159.3", "0.159.3.1"):
            with self.subTest(version=version):
                self.codex_prints(version)
                result = self.report(self.BEFORE)
                self.assertEqual(result["profiles"][0]["pinned_versions"], [
                    {"id": "codex", "pinned_version": "0.160.0", "checked": True, "matches_pin": False}])
                self.assertEqual(result["profiles"][0]["pinned_versions_summary"],
                                 {"matched": [], "mismatched": ["codex"], "unchecked": []})
                # The summary line is followed directly by the match line: no hold line, held or expired.
                self.assertIn("  pinned versions: 0 matched, mismatched: codex\nPinned versions match: false\n",
                              self.text(self.BEFORE))

    def test_the_pin_itself_matches_and_reports_no_hold(self):
        self.codex_prints("0.160.0")
        result = self.report(self.BEFORE)
        self.assertEqual(result["profiles"][0]["pinned_versions"], [
            {"id": "codex", "pinned_version": "0.160.0", "checked": True, "matches_pin": True}])
        self.assertEqual(result["profiles"][0]["pinned_versions_summary"],
                         {"matched": ["codex"], "mismatched": [], "unchecked": []})

    def test_a_failing_probe_that_names_the_hold_is_drift(self):
        # As for the pin itself: bootstrap-linux.sh reports any nonzero exit as "FAILED (exit N)".
        self.codex_prints("0.159.3", status=3)
        result = self.report(self.BEFORE)
        self.assertNotIn("hold_version", result["profiles"][0]["pinned_versions"][0])
        self.assertEqual(result["profiles"][0]["pinned_versions_summary"]["mismatched"], ["codex"])

    def test_a_malformed_hold_never_turns_drift_into_a_hold(self):
        for holds in ([{key: value for key, value in self.HOLD.items() if key != "until"}],
                      [{key: value for key, value in self.HOLD.items() if key != "reason"}],
                      [{key: value for key, value in self.HOLD.items() if key != "version"}],
                      [{**self.HOLD, "reason": "  "}], [{**self.HOLD, "version": ""}],
                      [{**self.HOLD, "until": "2026-13-01"}], [{**self.HOLD, "until": "2026-02-30"}],
                      [{**self.HOLD, "until": "04/11/2026"}], [{**self.HOLD, "until": "2026-11-04T00:00:00Z"}],
                      [{**self.HOLD, "until": 20261104}], ["0.159.3"], [None], dict(self.HOLD), "0.159.3", None):
            with self.subTest(holds=holds):
                self.write_pin(holds)
                result = self.report(self.BEFORE)
                self.assertEqual(result["profiles"][0]["pinned_versions"], [
                    {"id": "codex", "pinned_version": "0.160.0", "checked": True, "matches_pin": False}])
                self.assertIs(result["pinned_versions_match"], False)

    def test_the_first_usable_hold_naming_the_version_applies(self):
        self.write_pin([{**self.HOLD, "until": "not a date"}, {**self.HOLD, "version": "0.159.2"},
                        {**self.HOLD, "until": "2026-11-20", "reason": "second"}])
        item = self.report(self.BEFORE)["profiles"][0]["pinned_versions"][0]
        self.assertEqual((item["hold_version"], item["hold_until"], item["hold_reason"]), ("0.159.3", "2026-11-20", "second"))

    def assert_hold_reports_drift(self, hold):
        self.write_pin([hold])
        with patch("scripts.adoption_status.run_version_probe", return_value=(0, "codex-cli 0.159.3\n")) as probe:
            result = self.report(self.BEFORE)
        probe.assert_called_once()
        self.assertEqual(result["profiles"][0]["pinned_versions"], [
            {"id": "codex", "pinned_version": "0.160.0", "checked": True, "matches_pin": False}])
        self.assertEqual(result["profiles"][0]["pinned_versions_summary"],
                         {"matched": [], "mismatched": ["codex"], "unchecked": []})
        self.assertIs(result["pinned_versions_match"], False)

    def test_a_hold_without_url_reports_drift(self):
        self.assert_hold_reports_drift({key: value for key, value in self.HOLD.items() if key != "url"})

    def test_a_hold_without_sha256_reports_drift(self):
        self.assert_hold_reports_drift({key: value for key, value in self.HOLD.items() if key != "sha256"})

    def test_a_hold_without_required_platform_dependency_reports_drift(self):
        self.assert_hold_reports_drift({key: value for key, value in self.HOLD.items() if key != "platform_dependency"})

    def test_a_hold_with_other_invalid_install_metadata_reports_drift(self):
        mutations = {
            "unknown field": lambda hold: hold.update(hosts=["a host"]),
            "HTTP wrapper URL": lambda hold: hold.update(url="http://registry.npmjs.org/codex.tgz"),
            "short wrapper digest": lambda hold: hold.update(sha256="0" * 63),
            "uppercase wrapper digest": lambda hold: hold.update(sha256="A" * 64),
            "non-string wrapper digest": lambda hold: hold.update(sha256=int("1" * 64)),
            "null platform payload": lambda hold: hold.update(platform_dependency=None),
            "platform shape": lambda hold: hold["platform_dependency"].pop("checksum_ref"),
            "platform package": lambda hold: hold["platform_dependency"].update(name="other-linux-x64"),
            "resolved package": lambda hold: hold["platform_dependency"].update(resolved_package="other"),
            "platform version": lambda hold: hold["platform_dependency"].update(version="0.160.0-linux-x64"),
            "HTTP platform URL": lambda hold: hold["platform_dependency"].update(url="http://registry.npmjs.org/codex.tgz"),
            "platform digest": lambda hold: hold["platform_dependency"].update(sha256="3"),
            "platform integrity": lambda hold: hold["platform_dependency"].update(integrity="sha256-x"),
            "binary path": lambda hold: hold["platform_dependency"]["installed_binary_check"].update(path="bin/codex"),
            "binary digest": lambda hold: hold["platform_dependency"]["installed_binary_check"].update(sha256="4"),
            "binary shape": lambda hold: hold["platform_dependency"]["installed_binary_check"].pop("sha256"),
        }
        for label, mutate in mutations.items():
            with self.subTest(mutation=label):
                hold = json.loads(json.dumps(self.HOLD))
                mutate(hold)
                self.assert_hold_reports_drift(hold)

    def test_the_default_date_is_today_in_utc(self):
        with patch("scripts.adoption_status.utc_today", return_value=self.BEFORE):
            held = inspect_adoption(self.path, self.root, with_pinned_versions=True)
        with patch("scripts.adoption_status.utc_today", return_value=self.ON):
            expired = inspect_adoption(self.path, self.root, with_pinned_versions=True)
        self.assertEqual((held["pinned_versions_match"], expired["pinned_versions_match"]), (True, False))
        before = datetime.now(timezone.utc).date()
        observed = adoption_status.utc_today()
        self.assertIn(observed, {before, datetime.now(timezone.utc).date()})

    def test_held_output_is_value_free(self):
        result = self.report(self.BEFORE)
        self.assertNotIn(str(self.root), json.dumps(result))
        for key, value in result["profiles"][0]["pinned_versions"][0].items():
            self.assertTrue(value is None or isinstance(value, (bool, str)), repr((key, value)))


def pin_manifest_disagreements(pins: dict, components: list[dict]) -> list[str]:
    """Linux pins whose version differs from manifests/stack.json's version of the same component. A stack version
    may carry a source commit after " @ " (serena's "2.0.0.dev0 @ <commit>"); only the part before it is a version."""
    stack = {component["id"]: component["version"].split(" @ ", 1)[0]
             for component in components if isinstance(component.get("version"), str)}
    return [f"{identifier}: pin {entry['version']}, manifests/stack.json {stack[identifier]}"
            for identifier, entry in sorted(pins.items()) if identifier in stack and entry["version"] != stack[identifier]]


class PinManifestAgreementTests(unittest.TestCase):
    """--pinned-versions compares an installed tool with the Linux pins file, while manifests/stack.json names the
    version that the component's receipts qualified. A pin moved without its manifest row (or the reverse) makes
    `matches_pin: true` certify a version the manifest does not claim. Found 2026-09-30 while moving codex from 0.157.1
    to 0.159.2: nothing tied the two files together. The macOS pins file is left out: its codex pin waits for its own
    qualification (manifests/stack.json codex freshness)."""

    def test_every_linux_pin_names_the_manifest_version(self):
        pins = adoption_status.read_pins(pins_file_path(REPO, {"os": "linux", "architecture": "x86_64"}))
        components = json.loads((REPO / "manifests/stack.json").read_text(encoding="utf-8"))["components"]
        self.assertIn("codex", pins)
        self.assertGreaterEqual(len([identifier for identifier in pins
                                     if identifier in {component["id"] for component in components}]), 10)
        self.assertEqual(pin_manifest_disagreements(pins, components), [])

    def test_the_check_rejects_a_moved_pin_and_reads_a_commit_suffix(self):
        pins = {"tool": {"id": "tool", "version": "2.0.0"}, "pinned": {"id": "pinned", "version": "1.0.dev0"},
                "pin-only": {"id": "pin-only", "version": "9.9.9"}}
        components = [{"id": "tool", "version": "1.0.0"}, {"id": "pinned", "version": "1.0.dev0 @ " + "a" * 40}]
        self.assertEqual(pin_manifest_disagreements(pins, components), ["tool: pin 2.0.0, manifests/stack.json 1.0.0"])
        components[0]["version"] = "2.0.0"
        self.assertEqual(pin_manifest_disagreements(pins, components), [])


@unittest.skipUnless(SLEEP, "needs a sleep executable")
class PinnedVersionInterruptionTests(unittest.TestCase):
    """The --pinned-versions CLI, run as its own process on this host's real platform, gets a signal while a
    probe runs. Started with the default dispositions, SIGINT, SIGTERM and SIGHUP all end the check with the
    probe's whole process group killed, as bootstrap-linux.sh's EXIT trap does. Started with one of them
    ignored (nohup; a background job of a non-interactive shell), that signal changes nothing, as CPython leaves
    an ignored SIGINT ignored and bash cannot trap a signal ignored on entry: the probe finishes, is reported,
    and its group is still killed once it exits. The group is also killed when the signal arrives while the
    probe's process is being created, or a second one as the kill begins. Each check starts with exactly the
    dispositions its test sets, whatever the test runner inherited."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "adoption").mkdir()
        self.manifest = self.root / "adoption/manifest.json"
        self.manifest.write_text(json.dumps({
            "schema_version": 1,
            "supported_platforms": [{"os": "linux", "architecture": "x86_64", "python": "3.13"}],
            "profiles": [{"id": "probe", "label": "Probe", "required_commands": [],
                          "component_ids": ["forking-tool"], "recipe_paths": []}],
            "default_profile": "probe",
            "source": {"baseline_commit": "a" * 40, "repository": "https://github.com/example/reference"},
        }), encoding="utf-8")
        pins_file_path(self.root, HOST_PLATFORM).write_text(json.dumps({"tools": [
            {"id": "forking-tool", "version": "1.2.3",
             "version_probe": {"method": "exec", "command": "forking-tool", "args": [], "timeout_seconds": 60}},
        ]}), encoding="utf-8")
        self.bin = self.root / "bin"
        self.bin.mkdir()

    def probe(self, body: str) -> None:
        executable = self.bin / "forking-tool"
        executable.write_text(f"#!/bin/sh\n{body}\n")
        executable.chmod(0o755)

    def start(self, ignored: signal.Signals | None, descendant: Descendant, **streams) -> subprocess.Popen:
        """Start the check with SIGINT, SIGTERM and SIGHUP at their defaults, apart from ``ignored``, and wait
        until the probe's background child runs."""
        dispositions = {signum.name: "ignore" if signum == ignored else "default"
                        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        check = subprocess.Popen([sys.executable, "-c", EXEC_WITH_DISPOSITIONS, json.dumps(dispositions),
                                  sys.executable, str(REPO / "scripts/adoption_status.py"), "--manifest",
                                  str(self.manifest), "--repo-root", str(self.root), "--pinned-versions", "--json"],
                                 env={"PATH": str(self.bin)}, stdin=subprocess.DEVNULL, **streams)
        self.addCleanup(check.kill)
        deadline = time.monotonic() + 20
        while not descendant.started() and check.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(descendant.started(), "the probe's background child never ran")
        return check

    @staticmethod
    def release(fifo: Path, check: subprocess.Popen) -> None:
        """Let a probe blocked reading ``fifo`` go on. A nonblocking open for writing fails with ENXIO until the
        probe has the FIFO open, so it is retried while the check runs; a check that already exited is left
        alone."""
        deadline = time.monotonic() + 20
        while check.poll() is None and time.monotonic() < deadline:
            try:
                descriptor = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
            except OSError as error:
                if error.errno != errno.ENXIO:
                    raise
                time.sleep(0.02)
                continue
            try:
                os.write(descriptor, b"go\n")
            finally:
                os.close(descriptor)
            return

    def test_an_interrupted_check_kills_the_running_probe_s_process_group(self):
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=signum.name):
                descendant = Descendant(self, Path(tempfile.mkdtemp(dir=self.root)))
                self.probe(descendant.script("wait"))
                check = self.start(None, descendant, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                check.send_signal(signum)
                self.assertIn(check.wait(timeout=20), (-signum, 128 + signum))
                self.assertTrue(descendant.gone(), f"the probe's background child outlived {signum.name}")

    def test_a_signal_ignored_on_entry_leaves_the_check_running(self):
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=signum.name):
                work = Path(tempfile.mkdtemp(dir=self.root))
                descendant, release = Descendant(self, work), work / "release.fifo"
                os.mkfifo(release)
                # The probe waits for the release, so the signal is sure to arrive while it runs.
                self.probe(descendant.script(f"read line < '{release}'\nprintf 'forking-tool 1.2.3\\n'"))
                check = self.start(signum, descendant, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                check.send_signal(signum)
                time.sleep(0.2)  # time for a handler to act, were one installed
                self.release(release, check)
                output, _ = check.communicate(timeout=20)
                # The prerequisite result (2 on a platform or Python this manifest does not list), never a signal's.
                self.assertIn(check.returncode, (0, 2), f"{signum.name}, ignored on entry, ended the check")
                self.assertEqual(json.loads(output)["profiles"][0]["pinned_versions"], [
                    {"id": "forking-tool", "pinned_version": "1.2.3", "checked": True, "matches_pin": True}])
                self.assertTrue(descendant.gone(), "the probe's background child outlived the probe")

    def interrupt_inside(self, point: str, signum: signal.Signals, descendant: Descendant) -> subprocess.Popen:
        """Start the check through INTERRUPT_INSIDE_A_PROBE, with SIGINT, SIGTERM and SIGHUP at their defaults."""
        defaults = {each.name: "default" for each in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        check = subprocess.Popen([sys.executable, "-c", EXEC_WITH_DISPOSITIONS, json.dumps(defaults), sys.executable,
                                  "-c", INTERRUPT_INSIDE_A_PROBE, point, str(int(signum)), str(descendant.pidfile),
                                  str(REPO), "--manifest", str(self.manifest), "--repo-root", str(self.root),
                                  "--pinned-versions", "--json"],
                                 env={"PATH": str(self.bin)}, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE, text=True)
        self.addCleanup(check.kill)
        return check

    def test_a_signal_while_the_probe_s_process_is_created_still_kills_its_group(self):
        # After the fork, before subprocess.Popen returns: nothing yet holds the process to kill its group.
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(signal=signum.name):
                descendant = Descendant(self, Path(tempfile.mkdtemp(dir=self.root)))
                self.probe(descendant.script("wait"))
                check = self.interrupt_inside("created", signum, descendant)
                _, stderr = check.communicate(timeout=60)
                self.assertIn(f"raised {signum.name} after the probe's fork", stderr)
                self.assertTrue(descendant.started(), "the probe's background child never ran")
                self.assertIn(check.returncode, (-signum, 128 + signum))
                self.assertTrue(descendant.gone(),
                                f"the probe's background child outlived {signum.name} while its process was created")

    def test_a_second_signal_as_the_group_kill_begins_does_not_stop_it(self):
        # The check is interrupted once (SIGTERM from here), and a second signal arrives as its cleanup starts.
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            with self.subTest(second_signal=signum.name):
                descendant = Descendant(self, Path(tempfile.mkdtemp(dir=self.root)))
                self.probe(descendant.script("wait"))
                check = self.interrupt_inside("cleanup", signum, descendant)
                deadline = time.monotonic() + 20
                while not descendant.started() and check.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(descendant.started(), "the probe's background child never ran")
                check.send_signal(signal.SIGTERM)
                _, stderr = check.communicate(timeout=60)
                self.assertIn(f"raised {signum.name} as the kill of the probe's group began", stderr)
                self.assertIn(check.returncode, (-signum, 128 + signum))
                self.assertTrue(descendant.gone(),
                                f"the probe's background child outlived a second signal, {signum.name}")


@unittest.skipUnless(hasattr(signal, "SIGHUP"), "needs POSIX signals")
class ProbeSignalDispositionTests(unittest.TestCase):
    """signals_interrupt_probes, in this process: it replaces SIGTERM's and SIGHUP's disposition only while that
    is the default action, and SIGINT's while it is the default action or CPython's own handler, which CPython
    installs only when SIGINT starts at its default action, and restores each afterwards. An ignored signal stays
    ignored and a handler installed by someone else stays in place. Inside held_interrupts, the handlers keep the
    first interrupt and raise it when the hold ends; interrupts_released lets them through again for its block.
    run_version_probe, interrupted at the start of each line it and its helpers run, one line per run, leaves
    nothing of its probe running. The handlers are called directly; no signal is sent."""

    SIGNALS = (signal.SIGTERM, signal.SIGHUP) if hasattr(signal, "SIGHUP") else ()
    ALL = (signal.SIGINT, *SIGNALS)
    # run_version_probe and the helpers it calls while its probe's process exists.
    PROBE_FUNCTIONS = ("run_version_probe", "held_interrupts", "interrupts_released", "signal_group")

    def setUp(self):
        if threading.current_thread() is not threading.main_thread():
            self.skipTest("signal handlers can be changed in the main thread only")
        for signum in self.ALL:
            previous = signal.getsignal(signum)
            if previous is None:  # installed outside Python: it could not be put back
                self.skipTest(f"{signum.name} has a handler installed outside Python")
            self.addCleanup(signal.signal, signum, previous)
        held = getattr(adoption_status, "HELD_INTERRUPTS", {})
        self.addCleanup(held.update, {key: value for key, value in held.items()})

    def set_all(self, handler, signals=None) -> None:
        for signum in self.SIGNALS if signals is None else signals:
            signal.signal(signum, handler)

    def test_an_ignored_signal_stays_ignored(self):
        self.set_all(signal.SIG_IGN, self.ALL)
        with signals_interrupt_probes():
            for signum in self.ALL:
                self.assertEqual(signal.getsignal(signum), signal.SIG_IGN, signum.name)
        for signum in self.ALL:
            self.assertEqual(signal.getsignal(signum), signal.SIG_IGN, signum.name)

    def test_sigint_still_raises_keyboard_interrupt_and_is_restored(self):
        for label, starting in (("default_int_handler", signal.default_int_handler), ("SIG_DFL", signal.SIG_DFL)):
            with self.subTest(starting=label):
                signal.signal(signal.SIGINT, starting)
                with signals_interrupt_probes():
                    handler = signal.getsignal(signal.SIGINT)
                    self.assertTrue(callable(handler))
                    self.assertIsNot(handler, starting)
                    with self.assertRaises(KeyboardInterrupt):
                        handler(signal.SIGINT, None)
                self.assertEqual(signal.getsignal(signal.SIGINT), starting)

    def test_an_interrupt_during_a_hold_is_raised_when_the_hold_ends(self):
        self.set_all(signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        reached = False
        with signals_interrupt_probes():
            with self.assertRaises(SystemExit) as raised:
                with adoption_status.held_interrupts():
                    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)  # held: nothing is raised yet
                    signal.getsignal(signal.SIGINT)(signal.SIGINT, None)  # a second one: the first is kept
                    reached = True
            self.assertTrue(reached, "an interrupt was raised inside the hold")
            self.assertEqual(raised.exception.code, 128 + signal.SIGTERM)
            with adoption_status.held_interrupts():  # nothing is left pending
                pass
            with self.assertRaises(KeyboardInterrupt):  # and outside a hold, the handlers raise at once
                signal.getsignal(signal.SIGINT)(signal.SIGINT, None)

    def test_a_release_raises_what_was_held_then_the_hold_resumes(self):
        # A failure inside the hold would itself be replaced by the interrupt held at its end, so the block
        # records that it ran to the end.
        self.set_all(signal.SIG_DFL)
        reached = False
        with signals_interrupt_probes():
            handler = signal.getsignal(signal.SIGTERM)
            with self.assertRaises(SystemExit):  # the last one, held until the hold ends
                with adoption_status.held_interrupts():
                    handler(signal.SIGTERM, None)
                    with self.assertRaises(SystemExit):
                        with adoption_status.interrupts_released():
                            self.fail("an interrupt held before the release was not raised as it started")
                    self.assertTrue(adoption_status.HELD_INTERRUPTS["holding"], "the hold did not resume")
                    with self.assertRaises(SystemExit):
                        with adoption_status.interrupts_released():
                            handler(signal.SIGTERM, None)  # raised at once
                    self.assertTrue(adoption_status.HELD_INTERRUPTS["holding"], "the hold did not resume")
                    handler(signal.SIGTERM, None)
                    reached = True
            self.assertTrue(reached, "the hold's block stopped early")
            self.assertEqual(adoption_status.HELD_INTERRUPTS, {"holding": False, "pending": None})

    def run_probe_interrupted_at(self, k: int, argv: list[str], seconds: float):
        """run_version_probe(argv, seconds), with the SIGTERM handler called at the start of the k-th line that
        PROBE_FUNCTIONS execute before a KILL to the probe's group has returned, as CPython calls a handler for a
        signal that has arrived. Once that KILL is sent, nothing of the group is left to outlive it. A line that
        starts with a NOP (a try statement's own line) is not counted: CPython runs a Python signal handler only
        where it checks for pending signals, never at a NOP, and a NOP can lie outside every exception handler's
        range, as the NOP of a try statement in run_version_probe does, so an exception raised there would skip
        every cleanup, which no signal can cause. Returns that line, or None when fewer than k lines ran."""
        functions = [getattr(adoption_status, name, None) for name in self.PROBE_FUNCTIONS]
        traced = {getattr(function, "__wrapped__", function).__code__ for function in functions if function}
        handler, count, where, killed = signal.getsignal(signal.SIGTERM), 0, None, False
        signal_group = adoption_status.signal_group

        def signal_group_noting_the_kill(group, signum):
            nonlocal killed
            signal_group(group, signum)
            killed = killed or signum == signal.SIGKILL

        def line(frame, event, _arg):
            nonlocal count, where
            if event == "line" and not killed and frame.f_code.co_code[frame.f_lasti] != dis.opmap["NOP"]:
                count += 1
                if count == k:
                    where = f"{frame.f_code.co_name}, line {frame.f_lineno}"
                    handler(signal.SIGTERM, frame)
            return line

        previous = sys.gettrace()
        with patch.object(adoption_status, "signal_group", signal_group_noting_the_kill):
            sys.settrace(lambda frame, _event, _arg: line if frame.f_code in traced else None)
            try:
                adoption_status.run_version_probe(argv, seconds)
            except SystemExit as error:
                self.assertEqual(error.code, 128 + signal.SIGTERM)
            finally:
                sys.settrace(previous)
        return where

    @unittest.skipUnless(SLEEP, "needs a sleep executable")
    def test_an_interrupt_at_the_start_of_any_line_of_a_probe_run_still_kills_its_group(self):
        # One run per line: the interrupt lands at the start of the first line, then the second, and so on, until a
        # run sends its group the KILL with no line left. The probe and its background child ignore SIGTERM, so only
        # that KILL ends them, whether the probe exits at once or outlives its bound (TERM, then KILL).
        self.set_all(signal.SIG_DFL)
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        scenarios = (("exits at once", "printf 'tool 1.2.3\\n'", 10),
                     ("outlives its bound", f"exec '{SLEEP}' 30", 0.1))
        with signals_interrupt_probes(), patch.object(adoption_status, "PINNED_VERSION_KILL_GRACE_SECONDS", 0.05):
            for scenario, then, seconds in scenarios:
                with self.subTest(probe=scenario):
                    left_running, started_then_interrupted, k = [], 0, 0
                    while True:
                        k += 1
                        work = Path(tempfile.mkdtemp(dir=root))
                        descendant = Descendant(self, work)
                        probe = work / "probe"
                        probe.write_text(f"#!/bin/sh\ntrap '' TERM\n{descendant.script(then)}\n")
                        probe.chmod(0o755)
                        where = self.run_probe_interrupted_at(k, [str(probe)], seconds)
                        self.assertEqual(adoption_status.HELD_INTERRUPTS, {"holding": False, "pending": None},
                                         f"a hold was left on after an interrupt at {where}")
                        if descendant.started():
                            started_then_interrupted += where is not None
                            if not descendant.gone(3):
                                left_running.append(where or "no interrupt")
                        if where is None:
                            break
                    self.assertGreater(started_then_interrupted, 0, "no interrupt landed after the child started")
                    self.assertEqual(left_running, [], "the probe's background child outlived these interrupts")

    def test_a_default_signal_ends_the_check_through_system_exit_and_is_restored(self):
        self.set_all(signal.SIG_DFL)
        with signals_interrupt_probes():
            for signum in self.SIGNALS:
                handler = signal.getsignal(signum)
                self.assertTrue(callable(handler), signum.name)
                with self.assertRaises(SystemExit) as raised:
                    handler(signum, None)
                self.assertEqual(raised.exception.code, 128 + signum)
        for signum in self.SIGNALS:
            self.assertEqual(signal.getsignal(signum), signal.SIG_DFL, signum.name)

    def test_a_handler_installed_by_someone_else_is_left_in_place(self):
        def theirs(_signum, _frame):
            pass

        self.set_all(theirs, self.ALL)
        with signals_interrupt_probes():
            for signum in self.ALL:
                self.assertIs(signal.getsignal(signum), theirs, signum.name)
        for signum in self.ALL:
            self.assertIs(signal.getsignal(signum), theirs, signum.name)


class Interleaving:
    """Tries a replacement at every point between two steps of a read. ``run(call, action, target)`` runs ``call`` with the file-system functions the checks use wrapped, and performs ``action`` once, right after the
    ``target``-th of their calls returns or raises (target 0: never). It returns (the value of ``call``, whether the action ran, how many calls were made), and leaves ``trace`` holding (function, first argument,
    error number or None) for each call: a replacement that another process could make between two syscalls of the check is made between exactly those two, with the real file system and no invented result."""

    FUNCTIONS = ((os, "lstat"), (os, "stat"), (os, "open"), (os, "fstat"), (os, "listdir"), (os, "scandir"), (builtins, "open"))

    def run(self, call, action, target):
        self.count, self.fired, self.busy, self.trace = 0, False, False, []

        def wrapped(real, label):
            def step(*args, **keywords):
                error = None
                try:
                    return real(*args, **keywords)
                except BaseException as caught:
                    error = caught
                    raise
                finally:
                    if not self.busy:
                        self.count += 1
                        self.trace.append((label, str(args[0]) if args else None, getattr(error, "errno", None) if error is not None else None))
                        if self.count == target and not self.fired:
                            self.busy = self.fired = True
                            try:
                                action()
                            finally:
                                self.busy = False
            return step
        with contextlib.ExitStack() as stack:
            for module, name in self.FUNCTIONS:
                stack.enter_context(patch.object(module, name, wrapped(getattr(module, name), f"{module.__name__}.{name}")))
            value = call()
        return value, self.fired, self.count


ROOT = Path(__file__).resolve().parents[1]

UNAVAILABLE_NOTE = "the workflow installs it"


def unavailable(reason):
    """A test that needs a tool this machine lacks: a skip on a developer's machine, a failure under GitHub Actions, where the workflow installs it and a green run has to mean something was asserted (the pattern of
    tests/test_token_full_save_evidence.py metadata_lines, which reads GITHUB_ACTIONS on every call so that a control can patch the environment)."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        raise AssertionError(f"{reason}; {UNAVAILABLE_NOTE}, so its absence there is a defect")
    raise unittest.SkipTest(reason)


def real_bun():
    """The bun that reads agent front matter as the client does: the one named by AGENT_FRONTMATTER_BUN or else the first on PATH, when it is CLIENT_BUN_VERSION; unavailable otherwise."""
    path = adoption_status.find_bun()
    if not path:
        unavailable(f"bun {adoption_status.CLIENT_BUN_VERSION} is not installed")
    try:
        version = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        version = None
    if version != adoption_status.CLIENT_BUN_VERSION:
        unavailable(f"the bun at hand is {version}, not {adoption_status.CLIENT_BUN_VERSION}, the version the client embeds")
    return path


# A stand-in for bun that answers the protocol of agent_names as it is told to (behavior.json beside it) and logs how it was called (calls.jsonl). It exercises the plumbing, never YAML: the tests that depend on what
# the client's parser reads run the real bun.
FAKE_BUN = r'''#!{python}
import json, os, sys, time

here = os.path.dirname(os.path.abspath(sys.argv[0]))
behavior = json.load(open(os.path.join(here, "behavior.json")))
args = sys.argv[1:]
config = [item[len("--config="):] for item in args if item.startswith("--config=")]
entry = {"cwd": os.getcwd(), "home": os.environ.get("HOME"), "environment": sorted(os.environ), "config_empty": bool(config) and os.path.getsize(config[0]) == 0,
         "config_in_cwd": bool(config) and os.path.dirname(os.path.abspath(config[0])) == os.getcwd(), "dash_e": "-e" in args}
if "--version" in args:
    entry["call"] = "version"
    open(os.path.join(here, "calls.jsonl"), "a").write(json.dumps(entry) + "\n")
    print(behavior.get("version", "1.4.3"))
    sys.exit(behavior.get("version_status", 0))
stdin = sys.stdin.read()
blocks = json.loads(stdin)
entry.update(call="parse", blocks=len(blocks), argv_holds_a_block=any(block and block in " ".join(args) for block in blocks))
open(os.path.join(here, "calls.jsonl"), "a").write(json.dumps(entry) + "\n")
mode = behavior.get("parse", "echo")
if mode == "exit":
    sys.exit(behavior.get("status", 3))
if mode == "hang":
    time.sleep(60)
if mode == "garbage":
    print("not json")
elif mode == "answers":
    print(json.dumps(behavior["answers"]))
elif mode == "short":
    print(json.dumps([{"state": "none"}] * (len(blocks) - 1)))
else:
    answers = []
    for block in blocks:
        lines = [line for line in block.split("\n") if line.startswith("name:")]
        answers.append({"state": "name", "name": lines[0][len("name:"):].strip()} if lines else {"state": "none"})
    print(json.dumps(answers))
sys.exit(behavior.get("exit_after", 0))
'''


def make_fake_bun(directory, **behavior):
    script = Path(directory) / "bun"
    script.write_text(FAKE_BUN.replace("{python}", sys.executable), encoding="utf-8")
    script.chmod(0o755)
    (Path(directory) / "behavior.json").write_text(json.dumps(behavior), encoding="utf-8")
    return script


def fake_calls(directory):
    path = Path(directory) / "calls.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


ORACLE = ROOT / "tests" / "fixtures" / "agent_frontmatter" / "client-oracle.json"


BOM, REPLACEMENT = chr(0xFEFF), chr(0xFFFD)


class ExtractionTests(unittest.TestCase):
    """agent_front_matter: the block the client hands to its YAML parser, extracted as the loader scan does (oi in the 2.1.296 binary: the text read as UTF-8, a leading byte order mark dropped, and what
    /^---\\s*\\n([\\s\\S]*?)---\\s*\\n?/ captures; the client's check that "---" occurs after the first three characters changes no result, as the pattern cannot match without it, and bounds the work: see the timing test). Pure text; no bun."""

    ROWS = (
        ("a plain block", b"---\nname: x\n---\nbody\n", "name: x\n"),
        ("a byte order mark", (BOM + "---\nname: x\n---\n").encode("utf-8"), "name: x\n"),
        ("only the first byte order mark", (BOM + BOM + "---\nname: x\n---\n").encode("utf-8"), None),
        ("CRLF line endings", b"---\r\nname: x\r\n---\r\n", "name: x\r\n"),
        ("spaces and blank lines after the opener", b"---   \n\nname: x\n---\n", "name: x\n"),
        ("a tab after the opener", b"---\t\nname: x\n---\n", "name: x\n"),
        ("no closing line", b"---\nname: x\n", None),
        ("an empty block", b"---\n---\nname: x\n", ""),
        ("the first --- after the opener ends the block, wherever it stands on a line", b"---\ndescription: a --- b\nname: x\n---\n", "description: a "),
        ("four dashes", b"----\nname: x\n---\n", None),
        ("text before the opener", b"text\n---\nname: x\n---\n", None),
        ("a space before the opener", b" ---\nname: x\n---\n", None),
        ("a blank line before the opener", b"\n---\nname: x\n---\n", None),
        ("only three characters", b"---", None),
        ("no front matter", b"name: x\n", None),
        ("an empty file", b"", None),
        ("a lone CR is no line end", b"---\rname: x\r---\r", None),
        ("an invalid byte is read as U+FFFD", b"---\nname: x\xff\n---\n", "name: x" + REPLACEMENT + "\n"),
    )

    def test_the_block_is_what_the_client_hands_to_its_parser(self):
        for label, data, expected in self.ROWS:
            with self.subTest(case=label):
                self.assertEqual(adoption_status.agent_front_matter(data), expected)

    def test_an_unterminated_block_of_whitespace_is_refused_in_linear_time(self):
        """Review of #1062 at 2723f8fd (the local codex review, P2): the pattern backtracks quadratically over the whitespace after the opening "---" when no closing line follows (a 64 KiB file of newlines took 18 s,
        and a file may be 1 MiB), and the extraction runs before bun, so no timeout of bun bounds it. The client checks that "---" occurs after the first three characters before it matches (its `oi`, Claude Code
        2.1.296: `e.indexOf("---",3)<0?null:e.match(RE)`)."""
        for label, filler in (("newlines", b"\n"), ("a space and a newline", b" \n"), ("a carriage return and a newline", b"\r\n"), ("a tab and a newline", b"\t\n"),
                              ("a vertical tab, a form feed and a newline", b"\x0b\x0c\n")):
            with self.subTest(filler=label):
                started = time.monotonic()
                self.assertIsNone(adoption_status.agent_front_matter(b"---" + filler * (65536 // len(filler))))
                self.assertLess(time.monotonic() - started, 1.0, "the extraction of an unterminated block took more than a second")

    def test_a_closing_line_far_below_a_long_run_of_whitespace_is_still_found_in_linear_time(self):
        started = time.monotonic()
        self.assertEqual(adoption_status.agent_front_matter(b"---" + b"\n" * 65536 + b"---\n"), "")
        self.assertEqual(adoption_status.agent_front_matter(b"---" + b" " * 65536 + b"---\n"), None, "the opening line must end in a newline: spaces and a dash are no opening")
        self.assertLess(time.monotonic() - started, 1.0)


class AgentNamesTests(unittest.TestCase):
    """agent_names with a stand-in bun: how the parser is found, checked, called and answered, and that every failure is Unknown. Review of #1062 at e7260fd3 (the command center's Claude read, P1; its adjudication of
    2026-10-13): the reader written here was replaced by the client's own YAML parser, so the case the parser cannot settle is not read as 'no name'."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="fake-bun-")
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)

    def names(self, blobs, **behavior):
        bun = make_fake_bun(self.directory, **behavior)
        return adoption_status.agent_names(blobs, environ={"PATH": "/usr/bin:/bin", adoption_status.BUN_ENV: str(bun)})

    def test_the_answers_of_the_parser_are_a_name_none_or_unreadable_in_the_order_of_the_texts(self):
        blobs = [b"---\nname: a\n---\n", b"no front matter", b"---\nname: b\n---\n", b"---\nname: c\n---\n", b"---\nx: y\n---\n"]
        answers = [{"state": "name", "name": "a"}, {"state": "name", "name": ""}, {"state": "throws"}, {"state": "none"}]
        names = self.names(blobs, parse="answers", answers=answers)
        self.assertEqual(names[:3], ["a", None, None], "a name, a text with no front matter (never sent), an empty name")
        self.assertIs(names[3], adoption_status.UNREADABLE)
        self.assertEqual(names[4:], [None])
        self.assertEqual(len(fake_calls(self.directory)), 2, "one call for the version and one for the whole batch")

    def test_a_batch_is_one_call_and_the_blocks_are_data_on_stdin(self):
        blobs = [f"---\nname: n{index}\n---\n".encode() for index in range(7)]
        names = self.names(blobs)
        self.assertEqual(names, [f"n{index}" for index in range(7)])
        calls = fake_calls(self.directory)
        self.assertEqual([call["call"] for call in calls], ["version", "parse"])
        self.assertEqual((calls[1]["blocks"], calls[1]["argv_holds_a_block"], calls[1]["dash_e"]), (7, False, True))

    def test_bun_runs_in_an_empty_directory_with_an_empty_configuration_and_no_home(self):
        """A bunfig.toml in the caller's directory or home is read by bun, and a preload in it runs code (measured: a preload that is not found stops bun)."""
        self.names([b"---\nname: a\n---\n"])
        caller = os.getcwd()
        for call in fake_calls(self.directory):
            with self.subTest(call=call["call"]):
                self.assertNotEqual(call["cwd"], caller)
                self.assertTrue(call["config_empty"] and call["config_in_cwd"], "an explicit empty configuration in the working directory")
                self.assertEqual(call["home"], call["cwd"], "the home is the scratch directory")
                self.assertEqual(set(call["environment"]) - {"PWD", "SHLVL", "_", "LC_CTYPE"}, {"PATH", "HOME", "LANG"}, "nothing else of the caller's environment reaches bun")

    def test_nothing_is_asked_of_bun_when_no_text_has_front_matter(self):
        names = adoption_status.agent_names([b"no front matter", b"# notes", b""], environ={"PATH": "/nonexistent", adoption_status.BUN_ENV: "/nonexistent/bun"})
        self.assertEqual(names, [None, None, None])
        self.assertEqual(adoption_status.agent_names([], environ={}), [])

    def test_a_scratch_directory_that_cannot_be_made_is_unknown(self):
        with mock.patch.object(adoption_status.tempfile, "TemporaryDirectory", side_effect=PermissionError(errno.EACCES, "denied")):
            with self.assertRaises(adoption_status.Unknown):
                self.names([b"---\nname: a\n---\n"])

    def test_a_missing_bun_is_unknown(self):
        blobs = [b"---\nname: a\n---\n"]
        with self.assertRaises(adoption_status.Unknown):
            adoption_status.agent_names(blobs, environ={"PATH": "/nonexistent"})
        with self.assertRaises(adoption_status.Unknown):
            adoption_status.agent_names(blobs, environ={"PATH": "/usr/bin:/bin", adoption_status.BUN_ENV: str(self.directory / "absent")})

    def test_the_named_bun_wins_over_the_one_on_path_and_a_named_one_that_is_missing_is_not_replaced(self):
        named = make_fake_bun(self.directory, version="1.4.3")
        self.assertEqual(adoption_status.find_bun({"PATH": "/usr/bin", adoption_status.BUN_ENV: str(named)}), str(named))
        other = self.directory / "other"
        other.mkdir()
        shutil.copy(named, other / "bun")
        self.assertEqual(adoption_status.find_bun({"PATH": str(other)}), str(other / "bun"))
        self.assertEqual(adoption_status.find_bun({"PATH": str(other), adoption_status.BUN_ENV: "/nonexistent/bun"}), "/nonexistent/bun")
        self.assertIsNone(adoption_status.find_bun({"PATH": "/nonexistent"}))

    def test_a_relative_bun_is_made_absolute_before_either_launch(self):
        """Review of #1062 at b3da64d7 (the local codex review, P2): both launches run with cwd=scratch, and subprocess looks for a relative executable relative to cwd (python/cpython@cbc944f4bc59639a444dd971c737788ba2283a91
        Doc/library/subprocess.rst L572-L576), so a relative AGENT_FRONTMATTER_BUN, or a bun found through a relative PATH entry such as ./bin, named a file of the caller's directory and was searched for in the scratch one:
        the same bun gave Unknown from its relative path (reproduced with bun 1.4.3) and parsed from its absolute one."""
        bin_directory = self.directory / "bin"
        bin_directory.mkdir()
        make_fake_bun(bin_directory)
        variable = adoption_status.BUN_ENV
        cases = (("a relative value of the variable", {"PATH": "/usr/bin:/bin", variable: "bin/bun"}, self.directory),
                 ("a value of the variable that starts with ./", {"PATH": "/usr/bin:/bin", variable: "./bin/bun"}, self.directory),
                 ("a value of the variable that climbs out of the directory and back", {"PATH": "/usr/bin:/bin", variable: "../" + self.directory.name + "/bin/bun"}, self.directory),
                 ("a PATH entry ./bin", {"PATH": "./bin"}, self.directory),
                 ("a PATH entry bin", {"PATH": "bin"}, self.directory),
                 ("an empty PATH entry, which is the caller's directory", {"PATH": ":/usr/bin"}, bin_directory))
        for label, environ, working in cases:
            (bin_directory / "calls.jsonl").unlink(missing_ok=True)
            with self.subTest(case=label), contextlib.chdir(working):
                found = adoption_status.find_bun(environ)
                self.assertTrue(found and os.path.isabs(found), found)
                self.assertEqual(Path(found).resolve(), (bin_directory / "bun").resolve())
                self.assertEqual(adoption_status.agent_names([b"---\nname: a\n---\n"], environ=environ), ["a"])
                self.assertEqual([call["call"] for call in fake_calls(bin_directory)], ["version", "parse"], "both launches ran the stand-in")

    def test_a_value_with_no_directory_is_a_name_looked_up_on_path_and_never_in_the_callers_directory(self):
        bun = make_fake_bun(self.directory)
        variable = adoption_status.BUN_ENV
        self.assertEqual(adoption_status.find_bun({"PATH": str(self.directory), variable: "bun"}), str(bun))
        self.assertIsNone(adoption_status.find_bun({"PATH": str(self.directory), variable: "no-such-bun"}))
        with contextlib.chdir(self.directory):
            self.assertIsNone(adoption_status.find_bun({"PATH": "/nonexistent", variable: "bun"}), "a name is not a file of the caller's directory")
            missing = adoption_status.find_bun({"PATH": "/usr/bin:/bin", variable: "bin/absent"})
            self.assertTrue(os.path.isabs(missing), "a relative path to a file that is not there is still named, not replaced")
            with self.assertRaises(adoption_status.Unknown):
                adoption_status.agent_names([b"---\nname: a\n---\n"], environ={"PATH": "/usr/bin:/bin", variable: "bin/absent"})

    def test_a_relative_bun_of_a_caller_whose_directory_is_gone_is_unknown(self):
        """A relative path cannot be made absolute without the caller's directory (os.getcwd raises FileNotFoundError): None from find_bun, Unknown from agent_names, never a traceback."""
        gone = Path(tempfile.mkdtemp(prefix="gone-", dir=self.directory))
        environ = {"PATH": "/usr/bin:/bin", adoption_status.BUN_ENV: "bin/bun"}
        with contextlib.chdir(gone):
            gone.rmdir()
            self.assertIsNone(adoption_status.find_bun(environ))
            with self.assertRaises(adoption_status.Unknown):
                adoption_status.agent_names([b"---\nname: a\n---\n"], environ=environ)

    def test_a_bun_that_is_not_the_version_the_client_embeds_is_unknown(self):
        for version in ("1.4.2", "1.4.4", "1.4", "1.4.3-canary", "", "bun 1.4.3"):
            with self.subTest(version=version):
                with self.assertRaises(adoption_status.Unknown):
                    self.names([b"---\nname: a\n---\n"], version=version)
        with self.assertRaises(adoption_status.Unknown):
            self.names([b"---\nname: a\n---\n"], version="1.4.3", version_status=1)
        self.assertEqual(self.names([b"---\nname: a\n---\n"], version=adoption_status.CLIENT_BUN_VERSION), ["a"])

    def test_every_way_the_answer_can_fail_is_unknown(self):
        blobs = [b"---\nname: a\n---\n", b"---\nname: b\n---\n"]
        cases = (("a non-zero status", dict(parse="exit", status=3)), ("an answer that is not JSON", dict(parse="garbage")), ("an answer of the right shape from a bun that fails", dict(parse="echo", exit_after=3)), ("one answer too few", dict(parse="short")),
                 ("an answer that is not a list", dict(parse="answers", answers={"state": "none"})), ("an item of an unknown state", dict(parse="answers", answers=[{"state": "name", "name": "a"}, {"state": "maybe"}])),
                 ("a name that is not a string", dict(parse="answers", answers=[{"state": "name", "name": 5}, {"state": "none"}])), ("an item that is not an object", dict(parse="answers", answers=["x", "y"])))
        for label, behavior in cases:
            with self.subTest(failure=label):
                with self.assertRaises(adoption_status.Unknown):
                    self.names(blobs, **behavior)

    def test_a_vendor_file_that_declares_no_name_is_not_drift_even_when_a_shipped_definition_declares_none(self):
        """A definition with no name is served under none (the client skips it), so two of them do not collide: the shipped names that a vendor could take are the names that are there."""
        with tempfile.TemporaryDirectory() as tree:
            source, home = Path(tree) / "source", Path(tree) / "home"
            (home / "agents").mkdir(parents=True)
            source.mkdir()
            nameless = b"---\ndescription: x\n---\nbody\n"
            (source / "stack-a.md").write_bytes(nameless)
            (home / "agents" / "stack-a.md").write_bytes(nameless)
            (home / "agents" / adoption_status.VENDOR_HOST_AGENTS[0]).write_bytes(b"---\ndescription: y\n---\nbody\n")
            environ = {"PATH": "/usr/bin:/bin", adoption_status.BUN_ENV: str(make_fake_bun(self.directory))}
            self.assertEqual(adoption_status.stack_agents_drift(home, source, environ=environ), 0)
            (home / "agents" / adoption_status.VENDOR_HOST_AGENTS[0]).write_bytes(b"---\nname: stack-a\ndescription: y\n---\nbody\n")
            (source / "stack-a.md").write_bytes(b"---\nname: stack-a\ndescription: x\n---\nbody\n")
            (home / "agents" / "stack-a.md").write_bytes(b"---\nname: stack-a\ndescription: x\n---\nbody\n")
            self.assertEqual(adoption_status.stack_agents_drift(home, source, environ=environ), 1, "the same name in a vendor file is the drift")

    def test_a_bun_that_does_not_answer_in_time_is_unknown(self):
        with mock.patch.object(adoption_status, "BUN_TIMEOUT_SECONDS", 1):
            with self.assertRaises(adoption_status.Unknown):
                self.names([b"---\nname: a\n---\n"], parse="hang")


class RealBunTests(unittest.TestCase):
    """agent_names with the real bun at CLIENT_BUN_VERSION, against what the client itself served (tests/fixtures/agent_frontmatter/client-oracle.json: the installed Claude Code 2.1.296 was started on each text as a
    project agent and its init record read, by the author's private client_oracle.py). They skip on a developer's machine without that bun and fail under GitHub Actions, where the workflow installs it."""

    @classmethod
    def setUpClass(cls):
        cls.environ = {"PATH": os.environ.get("PATH", ""), adoption_status.BUN_ENV: real_bun()}

    def names(self, *texts):
        return adoption_status.agent_names([text.encode("utf-8") if isinstance(text, str) else text for text in texts], environ=self.environ)

    def test_the_pipeline_never_reads_a_name_other_than_the_one_the_client_served(self):
        """The one-sided property that no reader written here could keep (three rounds missed a spelling): wherever the client served an agent under a name, the pipeline answers that name or says it cannot tell,
        never none and never another name. Where the client served none (no description, an invalid name, a text that fails both of its attempts) a name from the pipeline is an over-report, the safe direction."""
        oracle = json.loads(ORACLE.read_text(encoding="utf-8"))
        entries = oracle["entries"]
        self.assertGreater(len(entries), 2500)
        answers = []
        for start in range(0, len(entries), 500):
            answers += self.names(*[text for _, text, _ in entries[start:start + 500]])
        counts, misses = Counter(), []
        for index, ((family, text, served), answer) in enumerate(zip(entries, answers)):
            if served is None:
                counts["over-report" if isinstance(answer, str) else "unreadable-where-none" if answer is adoption_status.UNREADABLE else "agree-none"] += 1
            elif answer == served:
                counts["agree"] += 1
            elif answer is adoption_status.UNREADABLE:
                counts["unreadable"] += 1
            else:
                counts["MISS"] += 1
                misses.append((family, index))
        self.assertEqual(misses, [])
        served_count = sum(1 for _, _, served in entries if served is not None)
        self.assertEqual(counts["agree"] + counts["unreadable"], served_count)
        self.assertGreaterEqual(counts["agree"], int(served_count * 0.9), "most of what the client served is read, not merely not-misread")

    def test_the_counterexample_of_the_command_centers_read_and_its_variants_are_read_as_the_client_reads_them(self):
        """The P1 of #1062 at e7260fd3: a comment line at the left margin between `name:` and its indented value made the hand-written reader answer none (drift 0, complete: true)."""
        name = "stack-verifier"
        for label, text in (("a comment at the left margin", f"---\nname:\n# role\n  {name}\ndescription: x\n---\n"), ("a comment on the key line", f"---\nname: # c\n  {name}\ndescription: x\n---\n"),
                            ("a left-margin comment and a blank line", f"---\nname:\n# role\n\n  {name}\ndescription: x\n---\n"), ("an indented comment", f"---\nname:\n  # role\n  {name}\ndescription: x\n---\n")):
            with self.subTest(case=label):
                self.assertEqual(self.names(text), [name])

    def test_a_bun_named_by_a_path_relative_to_the_callers_directory_is_the_same_bun(self):
        """The case of the local codex review of #1062 at b3da64d7 (P2), with the real binary: the bun that parses from its absolute path gave Unknown from a relative path to the same file, a relative value of the
        variable or a relative PATH entry, because both launches run in the scratch directory."""
        bun = Path(real_bun())
        for label, environ in (("a relative value of the variable", {"PATH": "/usr/bin:/bin", adoption_status.BUN_ENV: "./" + bun.name}), ("a relative PATH entry", {"PATH": ".", adoption_status.BUN_ENV: bun.name})):
            with self.subTest(case=label), contextlib.chdir(bun.parent):   # from the bun's own directory, where nothing of the scratch directory's can answer
                self.assertEqual(adoption_status.agent_names([b"---\nname: a\n---\n"], environ=environ), ["a"])

    def test_a_bunfig_in_the_working_directory_is_not_read(self):
        """bun reads a bunfig.toml of its working directory and runs its preload (measured with 1.4.3); the call runs in an empty directory, so a caller's directory cannot change what it does."""
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "ran"
            (Path(directory) / "preload.js").write_text(f"require('fs').writeFileSync({str(marker)!r}, 'x')\n")
            (Path(directory) / "bunfig.toml").write_text('preload = ["./preload.js"]\n')
            before = os.getcwd()
            os.chdir(directory)
            try:
                names = self.names("---\nname: a\n---\n")
            finally:
                os.chdir(before)
            self.assertEqual(names, ["a"])
            self.assertFalse(marker.exists(), "the preload of the caller's directory ran")

    def test_a_name_with_characters_beyond_ascii_comes_back_exact_whatever_the_locale_of_the_caller(self):
        name = "caf" + chr(0xE9) + "-" + chr(0x4E2D) + chr(0x6587)
        self.assertEqual(self.names(f"---\nname: {name}\ndescription: x\n---\n".encode("utf-8")), [name])

    def test_every_shipped_definition_has_a_name_the_parser_reads_on_the_first_attempt(self):
        blobs = [path.read_bytes() for path in sorted(STACK_AGENTS_SOURCE.glob("*.md"))]
        names = self.names(*blobs)
        self.assertTrue(all(isinstance(name, str) and name for name in names), names)
        self.assertEqual(len(set(names)), len(names), "one name per shipped definition")
        self.assertEqual(names, [path.stem for path in sorted(STACK_AGENTS_SOURCE.glob("*.md"))], "a shipped definition is named by its file")

    def test_a_name_that_is_not_a_string_is_no_name_as_the_client_serves_none(self):
        """Iwt serves an agent only under a string name: a number, a boolean, a null, an empty value, a list or a mapping is no name, and what String() would make of one (123, true, null) must not come back as a name."""
        for label, value in (("a number", "123"), ("a boolean", "true"), ("a null", "null"), ("an empty value", ""), ("a list", "[a, b]"), ("a mapping", "{a: b}"), ("an array of the document", None)):
            with self.subTest(case=label):
                text = "---\n- a\n- b\n---\n" if value is None else f"---\nname: {value}\ndescription: x\n---\n"
                self.assertEqual(self.names(text), [None])
        self.assertEqual(self.names('---\nname: "123"\ndescription: x\n---\n', "---\nname: 'true'\ndescription: x\n---\n"), ["123", "true"], "a quoted number or boolean is a string")

    def test_a_text_the_parser_throws_on_is_unreadable_where_the_client_goes_on_with_a_second_attempt(self):
        """The client answers a throw with a rewrite of the text and a second parse (W9t); that is not reproduced here, so the definition is Unknown, never none."""
        for label, text in (("a description with a colon and a space", "---\nname: a\ndescription: Use when: a thing\n---\n"), ("an unterminated flow sequence", "---\nname: a\ntools: [a, b\n---\n"),
                            ("text after a closing quote", '---\nname: "a"x\ndescription: x\n---\n')):
            with self.subTest(case=label):
                self.assertIs(self.names(text)[0], adoption_status.UNREADABLE)


class WorkflowPinTests(unittest.TestCase):
    """The workflow installs the bun that the check and its tests require, at the release's version and checksum (the repository's pattern for a tool the tests need: the uv step of the same job)."""

    def test_the_validation_workflow_installs_the_bun_the_check_requires(self):
        text = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
        self.assertIn(f"BUN_VERSION: '{adoption_status.CLIENT_BUN_VERSION}'", text)
        self.assertIsNotNone(re.search(r"BUN_SHA256: ([0-9a-f]{64})\n", text), "the release's checksum is written in the step")
        step = text[text.index("BUN_VERSION:"):text.index("Provision the pinned tree-sitter-bash parser")]
        for needle in ("releases/download/bun-v${BUN_VERSION}/bun-linux-x64.zip", "sha256sum --check", f'echo "{adoption_status.BUN_ENV}=', "bun-linux-x64/bun"):
            self.assertIn(needle, step)
        self.assertLess(step.index("sha256sum --check"), step.index("unzip"), "the archive is checked before it is unpacked")


class NeedsBunTests(unittest.TestCase):
    """The tests that need the real bun skip on a developer's machine and fail under GitHub Actions (the command center's adjudication of 2026-10-13, point 4; the pattern of tests/test_token_full_save_evidence.py)."""

    def outcome(self):
        try:
            real_bun()
        except unittest.SkipTest as skipped:
            return "skip", str(skipped)
        except AssertionError as failed:
            return "fail", str(failed)
        return "returned", ""

    def test_a_missing_bun_skips_locally_and_fails_under_github_actions(self):
        for ci, expected in (("unset", "skip"), ("true", "fail"), ("false", "skip")):
            with self.subTest(GITHUB_ACTIONS=ci), mock.patch.dict(os.environ), mock.patch.object(adoption_status, "find_bun", return_value=None):
                os.environ.pop("GITHUB_ACTIONS", None)
                if ci != "unset":
                    os.environ["GITHUB_ACTIONS"] = ci
                kind, message = self.outcome()
                self.assertEqual(kind, expected)
                self.assertIn("is not installed", message)

    def test_a_bun_of_another_version_skips_locally_and_fails_under_github_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            bun = make_fake_bun(directory, version="1.4.2")
            for ci, expected in (("unset", "skip"), ("true", "fail")):
                with self.subTest(GITHUB_ACTIONS=ci), mock.patch.dict(os.environ), mock.patch.object(adoption_status, "find_bun", return_value=str(bun)):
                    os.environ.pop("GITHUB_ACTIONS", None)
                    if ci != "unset":
                        os.environ["GITHUB_ACTIONS"] = ci
                    kind, message = self.outcome()
                    self.assertEqual(kind, expected)
                    self.assertIn("1.4.2", message)


class ClientWiringTests(unittest.TestCase):
    """--client-wiring on fake homes: fixed keys, booleans and counts only, never text from a file."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.home, self.root = base / "home", base / "checkout"
        self.home.mkdir()
        self.root.mkdir()
        self.env = {"HOME": str(self.home)}
        for name in ROLE_FILES:  # the checkout's copies of the two Codex role carriers, which the count compares with
            self.write(f"adoption/agents/codex/{name}", role_bytes(name), self.root)
        for name in AGENT_FILES:  # the checkout's Claude agent definitions, which the drift count compares with
            self.write(f"adoption/agents/claude/{name}", agent_bytes(name), self.root)

    def write(self, relative: str, content, base: Path | None = None) -> Path:
        path = (base or self.home) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return path

    def claude_settings(self) -> dict:
        hooks = {event: [ai_memory_group(event)] for event in CLAUDE_EVENTS}
        hooks["PreToolUse"].insert(0, {"matcher": "Bash", "hooks": [
            {"type": "command", "command": f"/opt/{PRIVATE}/bin/rtk hook claude"},
            {"type": "command", "command": f"python3 /opt/{PRIVATE}/secret_path_guard.py", "timeout": 10}]})
        env = {"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1", "CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS": "8",
               "PATH": f"/opt/{PRIVATE}/bin", "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://{PRIVATE}"}
        return {"env": env, "hooks": hooks, "enabledPlugins": {"context-mode@context-mode": True}}

    def wire(self):
        self.write(".claude/settings.json", self.claude_settings())
        self.write(".claude/plugins/installed_plugins.json", {"version": 2, "plugins": {"context-mode@context-mode": [
            {"scope": "user", "installPath": f"/opt/{PRIVATE}", "gitCommitSha": "a" * 40}]}})
        self.write(".codex/AGENTS.md", AGENTS_INLINE)
        self.write(".codex/RTK.md", RTK_MD)
        self.write(".codex/hooks.json", {"hooks": {event: [ai_memory_group(event)] for event in CODEX_EVENTS}})
        self.write(".codex/config.toml", CODEX_CONFIG + self.trust())
        self.write(".codex/plugins/cache/context-mode/context-mode/1.0.169/.codex-plugin/plugin.json",
                   {"name": PRIVATE})
        for name in ROLE_FILES:  # the role carriers the Codex worker lane installs under the Codex home
            self.write(f".codex/agents/{name}", role_bytes(name))
        for name in AGENT_FILES:  # the Claude definitions the profile installer copies under the Claude home
            self.write(f".claude/agents/{name}", agent_bytes(name))
        self.write(".claude/settings.json", {"env": {"CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS": "8",
                                                     "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1"}}, self.root)
        self.write(".codex/config.toml", CODEX_CONFIG, self.root)

    def trust(self, codex_home: Path | None = None, key_root: str | None = None) -> str:
        """The [hooks.state] tables Codex's /hooks writes when every command hook in the Codex home's hooks.json is
        trusted: each hook's key (its hooks.json path as Codex spells it) and current hash."""
        codex_home = codex_home or self.home / ".codex"
        events = adoption_status.codex_hooks_json((codex_home / "hooks.json").read_text(encoding="utf-8"))
        hashes = adoption_status.codex_hook_hashes(f"{key_root or codex_home}/hooks.json", events)
        return "".join(f'\n[hooks.state."{key}"]\ntrusted_hash = "{digest}"\n'
                       for key, (_, _, digest, _) in hashes.items())

    def wiring(self, env=None) -> dict:
        result = client_wiring(self.root, self.env if env is None else env)
        self.assertEqual(set(result), {*CLIENT_WIRING_KEYS, "complete"})
        self.assertIsInstance(result["complete"], bool)
        self.assertEqual({group: tuple(result[group]) for group in CLIENT_WIRING_KEYS}, CLIENT_WIRING_KEYS)
        for value in leaves(result):
            self.assertTrue(value is None or isinstance(value, (bool, int)), repr(value))
        rendered = json.dumps(result)
        for private in (PRIVATE, str(self.home), str(self.root)):
            self.assertNotIn(private, rendered)
        return result

    def test_a_wired_home_reports_every_check_and_no_file_text(self):
        self.wire()
        self.assertEqual(self.wiring(), WIRED)

    def test_an_unwired_home_reports_false_and_zero(self):
        self.assertEqual(self.wiring(), {
            "claude": {"rtk_hook": False, "ai_memory_hook_events": 0, "context_mode_plugin_enabled": False,
                       "subagent_spawn_depth_1": False, "workflow_concurrency_set": False,
                       "effort_level_env_unset": True, "agent_teams_opt_in": 0, "stack_agents_drift": len(AGENT_FILES)},
            "project": {"settings_depth_and_concurrency": False,
                        "codex_mcp_servers_present": dict.fromkeys(SERVERS, False)},
            # Without a config.toml Codex keeps its default: hooks on.
            "codex": {"rtk_instructions": False, "context_mode_plugin_enabled": False,
                      "mcp_servers_present": dict.fromkeys(SERVERS, False), "hooks_feature_enabled": True,
                      "ai_memory_hook_events": 0, "ai_memory_hook_events_trusted": 0, "stack_roles_matching": 0},
            "complete": False})

    def test_malformed_files_report_null_without_raising(self):
        self.wire()
        self.write(".claude/settings.json", '{"hooks": ')
        self.write(".codex/config.toml", f"[mcp_servers.serena\ncommand = \"{PRIVATE}\"\n")
        self.write(".codex/hooks.json", f'["{PRIVATE}"]')
        self.write(".codex/AGENTS.md", b"\xff\xfe@RTK.md\n")
        self.write(".claude/settings.json", "[]", self.root)
        self.write(".codex/config.toml", "= broken", self.root)
        self.assertEqual(self.wiring(), {
            "claude": dict.fromkeys(CLIENT_WIRING_KEYS["claude"]),
            "project": {"settings_depth_and_concurrency": None, "codex_mcp_servers_present": dict.fromkeys(SERVERS)},
            "codex": {"rtk_instructions": None, "context_mode_plugin_enabled": None,
                      "mcp_servers_present": dict.fromkeys(SERVERS), "hooks_feature_enabled": None,
                      "ai_memory_hook_events": None, "ai_memory_hook_events_trusted": None,
                      "stack_roles_matching": 2},  # its own folder is not one of the malformed files
            "complete": False})

    def test_directories_oversized_files_and_dangling_links_are_unreadable(self):
        self.wire()
        (self.home / ".codex/config.toml").unlink()
        (self.home / ".codex/config.toml").mkdir()
        hooks = {"hooks": {event: [ai_memory_group(event)] for event in CODEX_EVENTS}}
        self.write(".codex/hooks.json", json.dumps(hooks) + " " * 1_048_576)  # valid JSON, over the limit
        (self.home / ".claude/settings.json").unlink()
        (self.home / ".claude/settings.json").symlink_to(self.home / "missing-settings.json")
        result = self.wiring()
        self.assertEqual(set(result["claude"].values()), {None})
        self.assertIsNone(result["codex"]["context_mode_plugin_enabled"])
        self.assertEqual(result["codex"]["mcp_servers_present"], dict.fromkeys(SERVERS))
        self.assertIsNone(result["codex"]["hooks_feature_enabled"])
        self.assertIsNone(result["codex"]["ai_memory_hook_events"])
        self.assertIsNone(result["codex"]["ai_memory_hook_events_trusted"])
        self.assertTrue(result["codex"]["rtk_instructions"])
        self.assertIs(result["complete"], False)

    def test_wrong_types_inside_valid_files_are_not_wiring(self):
        self.write(".claude/settings.json", {
            "hooks": {"PreToolUse": f"/opt/{PRIVATE}/rtk hook claude",
                      "Stop": [3, {"hooks": "ai-memory hook"}, {"hooks": [{"type": "command", "command": 7}]}]},
            "env": ["CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"], "enabledPlugins": ["context-mode@context-mode"]})
        self.write(".codex/config.toml",
                   'plugins = "context-mode@context-mode"\nmcp_servers = ["serena"]\nfeatures = ["hooks"]\n')
        self.write(".codex/hooks.json", {"hooks": [f"/opt/{PRIVATE}/ai-memory hook"]})
        self.write(".codex/AGENTS.md", "@RTK.md\n")  # the referenced RTK.md is absent
        self.write(".claude/settings.json", {"env": {"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": True,
                                                     "CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS": "999"}}, self.root)
        result = self.wiring()
        self.assertEqual(result["claude"], {"rtk_hook": False, "ai_memory_hook_events": 0,
                                            "context_mode_plugin_enabled": False, "subagent_spawn_depth_1": False,
                                            "workflow_concurrency_set": False, "effort_level_env_unset": True,
                                            "agent_teams_opt_in": 0, "stack_agents_drift": len(AGENT_FILES)})
        self.assertFalse(result["project"]["settings_depth_and_concurrency"])
        self.assertEqual(result["codex"], {"rtk_instructions": False, "context_mode_plugin_enabled": False,
                                           "mcp_servers_present": dict.fromkeys(SERVERS, False),
                                           "hooks_feature_enabled": False, "ai_memory_hook_events": 0,
                                           "ai_memory_hook_events_trusted": 0, "stack_roles_matching": 0})
        self.assertIs(result["complete"], False)

    def test_the_rtk_hook_needs_a_bash_matcher_and_the_claude_hook_subcommand(self):
        self.wire()
        settings = self.claude_settings()
        cases = (("Bash", "rtk hook claude", True), ("", "rtk hook claude", True), ("*", "rtk hook claude", True),
                 (None, "rtk hook claude", True), ("Edit|Bash", "rtk hook claude", True),
                 ("Edit", "rtk hook claude", False), ("(", "rtk hook claude", False),
                 (["Bash"], "rtk hook claude", False),
                 ("Bash", "rtk hook codex", False), ("Bash", "rtk rewrite", False),
                 ("Bash", "echo rtk hook claude", False), ("Bash", "rtk 'hook claude", False))
        for matcher, command, expected in cases:
            with self.subTest(matcher=matcher, command=command):
                group = {"hooks": [{"type": "command", "command": command}]}
                if matcher is not None:
                    group["matcher"] = matcher
                settings["hooks"]["PreToolUse"][0] = group
                self.write(".claude/settings.json", settings)
                self.assertIs(self.wiring()["claude"]["rtk_hook"], expected)
        settings = self.claude_settings()
        settings["disableAllHooks"] = True
        self.write(".claude/settings.json", settings)
        claude = self.wiring()["claude"]
        self.assertEqual((claude["rtk_hook"], claude["ai_memory_hook_events"]), (False, 0))

    def test_codex_hooks_are_on_by_default_and_false_turns_them_off(self):
        # Codex 0.155.1: "hooks" is stable and default-enabled, "codex_hooks" its legacy alias, applied first.
        self.wire()
        cases = (("", True), ("[features]\n", True), ("[features]\nhooks = true\n", True),
                 ("[features]\nhooks = false\n", False), ("[features]\ncodex_hooks = false\n", False),
                 ("[features]\ncodex_hooks = false\nhooks = true\n", True),
                 ("[features]\nhooks = false\ncodex_hooks = true\n", False),
                 ('[features]\nhooks = "true"\n', False), ("[features]\ncodex_hooks = 1\n", False))
        for features, expected in cases:
            with self.subTest(features=features):
                self.write(".codex/config.toml", CODEX_BASE + "\n" + features + self.trust())
                result = self.wiring()
                self.assertIs(result["codex"]["hooks_feature_enabled"], expected)
                self.assertEqual(result["codex"]["ai_memory_hook_events"], 7 if expected else 0)
                self.assertEqual(result["codex"]["ai_memory_hook_events_trusted"], 7 if expected else 0)
                self.assertIs(result["codex"]["context_mode_plugin_enabled"], True)
                self.assertIs(result["complete"], expected)
        self.write(".codex/config.toml", 'features = "hooks"\n' + CODEX_BASE)
        self.assertIs(self.wiring()["codex"]["hooks_feature_enabled"], False)
        self.write(".codex/config.toml", "= broken")  # hooks.json is still valid: the count is unknown, not zero
        codex = self.wiring()["codex"]
        self.assertEqual((codex["hooks_feature_enabled"], codex["ai_memory_hook_events"],
                          codex["ai_memory_hook_events_trusted"]), (None, None, None))

    def test_complete_is_the_documented_rule(self):
        self.wire()
        self.assertIs(self.wiring()["complete"], True)
        elsewhere = CODEX_CONFIG.replace("[mcp_servers.serena]\n", "[mcp_servers.other]\n")
        self.write(".codex/config.toml", elsewhere + self.trust())  # still named in the project config.toml
        self.assertIs(self.wiring()["complete"], True)
        self.write(".codex/config.toml", elsewhere, self.root)  # now in neither
        self.assertIs(self.wiring()["complete"], False)
        for relative, content, base in ((".codex/hooks.json", {"hooks": {}}, None),  # a zero hook count
                                        (".codex/AGENTS.md", "# no instructions\n", None),  # one false boolean
                                        (".codex/config.toml", CODEX_CONFIG, None),  # hooks configured, not trusted
                                        (".codex/config.toml", "= broken", self.root)):  # one unreadable file
            with self.subTest(relative=relative, project=base is not None, content=str(content)[:20]):
                self.wire()
                self.write(relative, content, base)
                self.assertIs(self.wiring()["complete"], False)

    def test_rtk_instructions_must_be_inline_not_a_reference(self):
        # Codex passes its AGENTS.md to the model verbatim and expands no "@" reference, so a pointer to RTK.md,
        # which is what `rtk init -g --codex` writes, leaves the model without the instructions.
        self.wire()
        cases = ((f"# {PRIVATE}\n\n@RTK.md\n", RTK_MD, False),
                 (f"@{self.home}/.codex/RTK.md\n", RTK_MD, False),
                 (AGENTS_INLINE, RTK_MD, True),  # rewrapped, without RTK's ownership line
                 (AGENTS_INLINE + "\n@RTK.md\n", RTK_MD, True),
                 (AGENTS_INLINE, RTK_MD.replace("`rtk git status`", "`rtk ls`"), False),  # RTK.md moved on since
                 (AGENTS_INLINE, "", False),  # no RTK.md
                 (AGENTS_INLINE, "<!-- rtk-owned: written by rtk -->\n \n", False),  # nothing but the ownership line
                 ("", RTK_MD, False),
                 (AGENTS_INLINE, b"\xff\xfe# RTK\n", None))  # RTK.md unreadable here
        for agents, rtk, expected in cases:
            with self.subTest(agents=agents[:20], rtk=rtk[:30]):
                self.write(".codex/AGENTS.md", agents)
                if rtk == "":
                    (self.home / ".codex/RTK.md").unlink(missing_ok=True)
                else:
                    self.write(".codex/RTK.md", rtk)
                result = self.wiring()
                self.assertIs(result["codex"]["rtk_instructions"], expected)
                self.assertIs(result["complete"], expected is True)

    def test_a_non_blank_agents_override_replaces_agents_md(self):
        # codex-rs/codex-home/src/instructions/mod.rs (rust-v0.157.1): AGENTS.override.md first, AGENTS.md only when
        # the override is blank under Rust's str::trim. That strips Unicode White_Space only, so an override holding
        # U+001C, which Python's str.strip() also strips, is still the text Codex sends in place of AGENTS.md.
        self.wire()
        for override, expected in ((f"# {PRIVATE}: override without RTK\n", False), (" \n\t\n", True),
                                   (" 　\n", True), ("\x1c\n", False), ("\n\x1c\x1d\x1e\x1f \n", False),
                                   (AGENTS_INLINE, True), (b"\xff\xfe# override\n", None)):
            with self.subTest(override=override[:20]):
                self.write(".codex/AGENTS.override.md", override)
                self.assertIs(self.wiring()["codex"]["rtk_instructions"], expected)
        (self.home / ".codex/AGENTS.override.md").unlink()
        self.write(".codex/AGENTS.md", f"# {PRIVATE}\n")
        self.write(".codex/AGENTS.override.md", AGENTS_INLINE)
        self.assertIs(self.wiring()["codex"]["rtk_instructions"], True)

    def test_codex_runs_an_ai_memory_hook_only_when_enabled_and_trusted(self):
        self.wire()
        hooks = f"{self.home}/.codex/hooks.json"
        trusted = self.trust()
        stale = trusted.replace('trusted_hash = "sha256:', 'trusted_hash = "sha256:0', 1)  # one hook modified
        disabled = trusted.replace(f'[hooks.state."{hooks}:stop:0:0"]\n',
                                   f'[hooks.state."{hooks}:stop:0:0"]\nenabled = false\n')
        mistyped = trusted.replace(f'[hooks.state."{hooks}:stop:0:0"]\n',
                                   f'[hooks.state."{hooks}:stop:0:0"]\nenabled = "yes"\n')
        spaced = trusted.replace(f'[hooks.state."{hooks}:stop:0:0"]', f'[hooks.state." {hooks}:stop:0:0 "]')
        # Rust's str::trim strips Unicode White_Space only; U+001C, which Python's str.strip() also strips, stays.
        separated = trusted.replace(f'[hooks.state."{hooks}:stop:0:0"]', f'[hooks.state."\\u001c{hooks}:stop:0:0"]')
        for state, expected in (("", 0), (trusted, 7), (stale, 6), (disabled, 6), (mistyped, 6), (spaced, 7),
                                (separated, 6)):
            with self.subTest(state=state[:60]):
                self.write(".codex/config.toml", CODEX_CONFIG + state)
                result = self.wiring()
                self.assertEqual((result["codex"]["ai_memory_hook_events"],
                                  result["codex"]["ai_memory_hook_events_trusted"]), (7, expected))
                self.assertIs(result["complete"], expected == 7)
        # A hook edited after it was trusted is "modified" to Codex until it is trusted again.
        self.write(".codex/config.toml", CODEX_CONFIG + trusted)
        edited = {"hooks": {event: [ai_memory_group(event)] for event in CODEX_EVENTS}}
        edited["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 30
        self.write(".codex/hooks.json", edited)
        self.assertEqual(self.wiring()["codex"]["ai_memory_hook_events_trusted"], 6)
        # Only ai-memory hooks count: a trusted hook that runs something else adds nothing.
        rtk = {"type": "command", "command": "rtk hook codex"}
        self.write(".codex/hooks.json", {"hooks": {"Stop": [{"hooks": [rtk]}]}})
        self.write(".codex/config.toml", CODEX_CONFIG + self.trust())
        self.assertEqual(self.wiring()["codex"]["ai_memory_hook_events_trusted"], 0)

    def test_a_hooks_file_codex_rejects_runs_no_hook(self):
        # Codex parses hooks.json whole (HooksFile, then each handler by "type"): one bad value and none load, so
        # both counts read as a malformed file's, null.
        self.wire()

        def stop(data):
            return data["hooks"]["Stop"][0]["hooks"]

        for label, change in (("unknown top-level key", lambda data: data.update(extra=True)),
                              ("timeout as text", lambda data: stop(data)[0].update(timeout="9")),
                              ("negative timeout", lambda data: stop(data)[0].update(timeout=-1)),
                              ("async null", lambda data: stop(data)[0].update({"async": None})),
                              ("unknown handler type", lambda data: stop(data).append({"type": "script"})),
                              ("event not a list", lambda data: data["hooks"].update(PreCompact={"hooks": []})),
                              ("MCP input with null", lambda data: stop(data).append(
                                  {"type": "mcp_tool", "server": "s", "tool": "t", "input": {"k": None}}))):
            with self.subTest(label=label):
                data = {"hooks": {event: [ai_memory_group(event)] for event in CODEX_EVENTS}}
                self.write(".codex/hooks.json", data)
                self.write(".codex/config.toml", CODEX_CONFIG + self.trust())  # trusted while valid
                change(data)
                self.write(".codex/hooks.json", data)
                codex = self.wiring()["codex"]
                self.assertEqual((codex["ai_memory_hook_events"], codex["ai_memory_hook_events_trusted"]), (None, None))
                self.assertIs(self.wiring()["complete"], False)
        # Unknown events and extra fields are ignored by Codex, and so here.
        data = {"hooks": {event: [ai_memory_group(event)] for event in CODEX_EVENTS}}
        data["hooks"]["Future"] = "anything"
        data["hooks"]["Stop"][0]["note"] = PRIVATE
        self.write(".codex/hooks.json", data)
        self.write(".codex/config.toml", CODEX_CONFIG + self.trust())
        self.assertEqual(self.wiring()["codex"]["ai_memory_hook_events_trusted"], 7)

    def test_a_hooks_file_codex_fails_to_parse_reports_null_as_a_malformed_file_does(self):
        # Codex reads hooks.json with serde_json::from_str: a repeated field, NaN, a lone surrogate where it parses
        # text, a number its field cannot hold, too deep a nesting or a hook it cannot hash, and it loads no hook.
        self.wire()
        trusted = CODEX_CONFIG + self.trust()  # the wired file's hooks, trusted
        for label, text in CODEX_REJECTED_HOOKS_FILES:
            with self.subTest(label=label):
                self.write(".codex/hooks.json", text)
                self.write(".codex/config.toml", trusted)
                result = self.wiring()
                self.assertEqual((result["codex"]["ai_memory_hook_events"],
                                  result["codex"]["ai_memory_hook_events_trusted"]), (None, None))
                self.assertIs(result["complete"], False)

    def test_a_hooks_file_codex_parses_runs_its_trusted_hooks(self):
        # What Codex's parse skips or keeps as text is not checked: a repeated unknown key, a lone surrogate in a
        # skipped value, any number outside a typed field, deep nesting in a skipped value, and serde's array form
        # of each struct.
        self.wire()
        trusted = CODEX_CONFIG + self.trust()
        for label, text in CODEX_ACCEPTED_HOOKS_FILES:
            with self.subTest(label=label):
                self.write(".codex/hooks.json", text)
                self.write(".codex/config.toml", trusted)
                result = self.wiring()
                self.assertEqual((result["codex"]["ai_memory_hook_events"],
                                  result["codex"]["ai_memory_hook_events_trusted"]), (7, 7))
                self.assertIs(result["complete"], True)
        # Codex reads "-0" as the integer 0 (serde_json with arbitrary_precision), which a timeout can hold.
        self.write(".codex/hooks.json", codex_hooks_text(stop_group(stop_handler(', "timeout": 0'))))
        self.write(".codex/config.toml", CODEX_CONFIG + self.trust())
        self.write(".codex/hooks.json", codex_hooks_text(stop_group(stop_handler(', "timeout": -0'))))
        self.assertEqual(self.wiring()["codex"]["ai_memory_hook_events_trusted"], 7)

    def test_a_group_whose_matcher_codex_cannot_load_is_skipped(self):
        self.wire()
        for matcher, loads in (("", True), ("*", True), ("Bash|Edit", True), ("mcp__.*", True), ("(", False),
                               ("(?=x)", None), ("(a)\\1", None), ("(?>a)", None), ("a\\Z", None),
                               ("(?#note)Bash", None), ("(?i)bash", None)):
            with self.subTest(matcher=matcher):
                data = {"hooks": {event: [ai_memory_group(event)] for event in CODEX_EVENTS}}
                data["hooks"]["PreToolUse"][0]["matcher"] = matcher
                self.write(".codex/hooks.json", data)
                self.write(".codex/config.toml", CODEX_CONFIG + self.trust())
                result = self.wiring()
                # A matcher this check cannot evaluate as Rust's regex crate does leaves the count unknown.
                self.assertEqual(result["codex"]["ai_memory_hook_events_trusted"],
                                 None if loads is None else 7 if loads else 6)
                self.assertEqual(result["codex"]["ai_memory_hook_events"], 7)
                self.assertIs(result["complete"], loads is True)
        # A matcher on an event without matchers (Stop) is never compiled, as in Codex.
        data = {"hooks": {event: [ai_memory_group(event)] for event in CODEX_EVENTS}}
        data["hooks"]["Stop"][0]["matcher"] = "("
        self.write(".codex/hooks.json", data)
        self.write(".codex/config.toml", CODEX_CONFIG + self.trust())
        self.assertEqual(self.wiring()["codex"]["ai_memory_hook_events_trusted"], 7)

    def test_matcher_verdicts_equal_codexs_or_are_left_undecided(self):
        for matchers, expected in ((CODEX_LOADS_MATCHERS, True), (CODEX_SKIPS_MATCHERS, False),
                                   (UNDECIDED_MATCHERS, None)):
            for matcher in matchers:
                with self.subTest(matcher=matcher):
                    self.assertIs(adoption_status.codex_matcher_loads(matcher), expected)

    def test_hook_hashes_equal_the_ones_codex_reports(self):
        root = str(self.home / ".codex")
        for event, matcher, handler, current_hash in CODEX_KNOWN_HASHES:
            with self.subTest(event=event, matcher=matcher):
                group = {"hooks": [handler]} if matcher is None else {"matcher": matcher, "hooks": [handler]}
                events = adoption_status.codex_hooks_json(json.dumps({"hooks": {event: [group]}}))
                label = adoption_status.CODEX_HOOK_EVENTS[event]
                self.assertEqual(adoption_status.codex_hook_hashes(f"{root}/hooks.json", events),
                                 {f"{root}/hooks.json:{label}:0:0": (event, True, current_hash,
                                                                    "ai-memory" in handler["command"])})
        # The identity is fingerprint.rs version_for_toml: SHA-256 of compact JSON with sorted keys, which a
        # hand-written string reproduces for the first known answer.
        canonical = ('{"event_name":"session_start","hooks":[{"async":false,"command":"'
                     + EXAMPLE_HOOK.format("session-start") + '","timeout":600,"type":"command"}],"matcher":""}')
        self.assertEqual("sha256:" + hashlib.sha256(canonical.encode()).hexdigest(), CODEX_KNOWN_HASHES[0][3])

    def test_the_concurrency_cap_must_be_an_integer_the_client_accepts(self):
        self.wire()
        for value, expected in (("8", True), (8, True), ("256", True), (" 16 ", True), ("1", True), ("0", False),
                                ("257", False), ("-1", False), ("8.5", False), ("", False), (True, False),
                                (None, False)):
            with self.subTest(value=value):
                settings = self.claude_settings()
                settings["env"]["CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS"] = value
                self.write(".claude/settings.json", settings)
                self.write(".claude/settings.json", {"env": settings["env"]}, self.root)
                result = self.wiring()
                self.assertIs(result["claude"]["workflow_concurrency_set"], expected)
                self.assertIs(result["project"]["settings_depth_and_concurrency"], expected)

    def test_only_ai_memory_hook_commands_are_counted(self):
        self.wire()
        settings = self.claude_settings()
        settings["hooks"]["Stop"] = [{"hooks": [{"type": "command", "command": f"/opt/{PRIVATE}/ai-memory status"}]}]
        settings["hooks"]["SessionEnd"] = [{"hooks": [{"type": "command", "command": "echo ai-memory hook"}]}]
        settings["hooks"]["PreCompact"][0]["hooks"][0]["type"] = "prompt"
        self.write(".claude/settings.json", settings)
        self.assertEqual(self.wiring()["claude"]["ai_memory_hook_events"], 5)

    def test_effort_and_agent_team_opt_ins_are_found_by_name_whatever_their_value(self):
        self.wire()
        claude = self.wiring({**self.env, "CLAUDE_CODE_EFFORT_LEVEL": PRIVATE})["claude"]
        self.assertEqual((claude["effort_level_env_unset"], claude["agent_teams_opt_in"]), (False, 0))
        claude = self.wiring({**self.env, "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "0"})["claude"]
        self.assertEqual((claude["effort_level_env_unset"], claude["agent_teams_opt_in"]), (True, 1))
        settings = self.claude_settings()
        settings["env"].update(CLAUDE_CODE_EFFORT_LEVEL=PRIVATE, CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=PRIVATE)
        self.write(".claude/settings.json", settings)
        claude = self.wiring()["claude"]
        self.assertEqual((claude["effort_level_env_unset"], claude["agent_teams_opt_in"]), (False, 1))

    def test_agent_teams_opt_in_is_information_and_never_blocks_completeness(self):
        # Agent teams are an allowed dispatch mode (user instructions 2026-09-27), so the opt-in is reported as a
        # 0/1 count and the completeness rule is the same with it set or unset.
        self.wire()
        unset = self.wiring()
        with_teams = self.wiring({**self.env, "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"})
        self.assertEqual((unset["claude"]["agent_teams_opt_in"], with_teams["claude"]["agent_teams_opt_in"]), (0, 1))
        self.assertEqual(with_teams["complete"], unset["complete"])

    def test_disabled_or_uninstalled_plugins_and_servers_are_not_wired(self):
        self.wire()
        self.write(".claude/plugins/installed_plugins.json",
                   {"version": 2, "plugins": {"context-mode@context-mode": []}})
        shutil.rmtree(self.home / ".codex/plugins")
        self.write(".codex/config.toml",
                   CODEX_CONFIG.replace("[mcp_servers.serena]\n", "[mcp_servers.serena]\nenabled = false\n"))
        result = self.wiring()
        self.assertFalse(result["claude"]["context_mode_plugin_enabled"])
        self.assertFalse(result["codex"]["context_mode_plugin_enabled"])
        self.assertEqual(result["codex"]["mcp_servers_present"],
                         {"serena": False, "socraticode": True, "ai-memory": True})
        self.write(".claude/plugins/installed_plugins.json", "{")
        self.assertIsNone(self.wiring()["claude"]["context_mode_plugin_enabled"])  # enabled, registry unreadable
        settings = self.claude_settings()
        settings["enabledPlugins"]["context-mode@context-mode"] = False
        self.write(".claude/settings.json", settings)
        self.assertFalse(self.wiring()["claude"]["context_mode_plugin_enabled"])

    def test_client_homes_follow_claude_config_dir_and_codex_home(self):
        self.wire()
        moved = self.home / "configured"
        moved.mkdir()
        (self.home / ".claude").rename(moved / "claude")
        (self.home / ".codex").rename(moved / "codex")
        env = {**self.env, "CLAUDE_CONFIG_DIR": str(moved / "claude"), "CODEX_HOME": str(moved / "codex")}
        # Codex keys hook trust by its hooks.json path, a set CODEX_HOME canonicalized: moving the home, or reaching
        # it through a symbolic link, leaves the old trust behind until /hooks records it again.
        self.assertEqual(self.wiring(env)["codex"]["ai_memory_hook_events_trusted"], 0)
        self.write("configured/codex/config.toml",
                   CODEX_CONFIG + self.trust(moved / "codex", os.path.realpath(moved / "codex")))
        self.assertEqual(self.wiring(env), WIRED)
        (self.home / "link").symlink_to(moved)
        self.assertEqual(self.wiring({**env, "CODEX_HOME": str(self.home / "link/codex")}), WIRED)
        self.assertFalse(self.wiring()["claude"]["rtk_hook"])

    # -- stack_roles_matching: how many of the two Codex role carriers under <Codex home>/agents equal the checkout's copies
    # (U13 design 3.4; the count is a number, never the file's text, its name or a path).

    def roles(self, env=None):
        """codex.stack_roles_matching of the fake home. The key is asserted first, so a base without it fails on that."""
        codex = self.wiring(env)["codex"]
        self.assertIn("stack_roles_matching", codex)
        return codex["stack_roles_matching"]

    def test_the_role_key_is_the_last_codex_key_and_a_count(self):
        self.assertEqual(CLIENT_WIRING_KEYS["codex"][-1], "stack_roles_matching")
        self.assertEqual(len(CLIENT_WIRING_KEYS["codex"]), 7)
        self.wire()
        value = self.wiring()["codex"]["stack_roles_matching"]
        self.assertIs(type(value), int)  # a number: a boolean would not say how many

    def test_stack_roles_matching_counts_the_carriers_equal_to_the_checkout_copies(self):
        self.assertEqual(self.roles(), 0)  # no agents folder: nothing installed
        self.wire()
        agents = self.home / ".codex/agents"
        self.assertEqual(self.roles(), 2)  # both installed, byte for byte
        researcher, verifier = agents / ROLE_FILES[0], agents / ROLE_FILES[1]
        researcher.write_bytes(researcher.read_bytes() + b"\n")  # one byte more
        self.assertEqual(self.roles(), 1)
        flipped = bytearray(verifier.read_bytes())
        flipped[0] ^= 1  # the same size, one bit different: equal length is not equal bytes
        verifier.write_bytes(bytes(flipped))
        self.assertEqual(self.roles(), 0)
        researcher.write_bytes(role_bytes(ROLE_FILES[0]))
        self.assertEqual(self.roles(), 1)
        verifier.unlink()  # absent
        self.assertEqual(self.roles(), 1)
        # Other files never count: an extra file, and a copy of a carrier's name in a nested folder.
        self.write(".codex/agents/extra.toml", role_bytes(ROLE_FILES[1]))
        self.write(".codex/agents/nested/" + ROLE_FILES[1], role_bytes(ROLE_FILES[1]))
        self.assertEqual(self.roles(), 1)
        self.write(".codex/agents/" + ROLE_FILES[1], role_bytes(ROLE_FILES[1]))
        self.assertEqual(self.roles(), 2)

    def test_a_link_or_a_folder_in_place_of_a_carrier_is_not_a_match(self):
        self.wire()
        agents = self.home / ".codex/agents"
        identical = self.write("identical-copy.toml", role_bytes(ROLE_FILES[0]))
        (agents / ROLE_FILES[0]).unlink()
        (agents / ROLE_FILES[0]).symlink_to(identical)  # the bytes are equal, but Codex's file is a link
        self.assertEqual(self.roles(), 1)
        (agents / ROLE_FILES[1]).unlink()
        (agents / ROLE_FILES[1]).mkdir()  # a folder where a file belongs
        self.assertEqual(self.roles(), 0)

    def test_the_role_count_follows_codex_home(self):
        self.wire()
        moved = self.home / "elsewhere"
        (self.home / ".codex").rename(moved)
        self.assertEqual(self.roles(), 0)  # the default home has no agents folder any more
        self.assertEqual(self.roles({**self.env, "CODEX_HOME": str(moved)}), 2)

    def test_the_role_count_is_null_when_a_carrier_source_or_the_folder_cannot_be_compared(self):
        self.wire()
        agents = self.home / ".codex/agents"
        source = self.root / "adoption/agents/codex" / ROLE_FILES[0]
        kept = source.read_bytes()
        source.unlink()  # a checkout without a source copy: nothing to compare with, even where the roles are absent
        self.assertIsNone(self.roles())
        shutil.rmtree(agents)
        self.assertIsNone(self.roles())
        source.write_bytes(kept)
        self.assertEqual(self.roles(), 0)
        agents.write_text("a file where the folder belongs", encoding="utf-8")
        self.assertIsNone(self.roles())
        agents.unlink()
        (self.home / "linked-agents").mkdir()
        agents.symlink_to(self.home / "linked-agents")  # a linked folder: what Codex loads through it is not known here
        self.assertIsNone(self.roles())

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads a file whatever its mode")
    def test_the_role_count_is_null_for_an_unreadable_folder_or_file(self):
        self.wire()
        agents = self.home / ".codex/agents"
        carrier = agents / ROLE_FILES[0]
        carrier.chmod(0)
        try:
            self.assertIsNone(self.roles())
        finally:
            carrier.chmod(0o644)
        agents.chmod(0)
        try:
            self.assertIsNone(self.roles())
        finally:
            agents.chmod(0o755)
        self.assertEqual(self.roles(), 2)

    def test_complete_ignores_a_role_count_but_a_null_count_makes_it_false(self):
        self.wire()
        self.assertEqual((self.roles(), self.wiring()["complete"]), (2, True))
        shutil.rmtree(self.home / ".codex/agents")
        self.assertEqual((self.roles(), self.wiring()["complete"]), (0, True))  # a count never blocks completeness
        (self.home / ".codex/agents").write_text("a file", encoding="utf-8")
        result = self.wiring()
        self.assertEqual((result["codex"]["stack_roles_matching"], result["complete"]), (None, False))
        # every other flag is still true: the null alone is what turned completeness off
        others = {key: value for key, value in result["codex"].items() if key != "stack_roles_matching"}
        self.assertEqual(others, {key: value for key, value in WIRED["codex"].items() if key != "stack_roles_matching"})

    def test_the_two_argument_form_of_codex_wiring_still_reports_the_count(self):
        # Retained evidence scripts (evidence/artifacts/adoption-status-truth-20260926) call codex_wiring(dir, key_root).
        codex_dir = self.home / ".codex"
        codex_dir.mkdir()
        report = adoption_status.codex_wiring(codex_dir, str(codex_dir))
        self.assertIn("stack_roles_matching", report)
        self.assertEqual(report["stack_roles_matching"], 0)  # this repository's own copies are the default source

    def test_the_limitations_name_the_role_files_the_check_compares(self):
        text = CLIENT_WIRING_LIMITATIONS[0]
        for needle in ("agents/", "adoption/agents/codex", "byte for byte"):
            self.assertIn(needle, text)

    # -- stack_agents_drift (CPA-V-10 of the Claude-family practice audit): the Claude agent definitions under <Claude home>/agents against the checkout's
    # adoption/agents/claude. A count that must be 0; never a name, a path or text.

    def drift(self, env=None):
        """claude.stack_agents_drift of the fake home. The key is asserted first, so a base without it fails on that."""
        claude = self.wiring(env)["claude"]
        self.assertIn("stack_agents_drift", claude)
        return claude["stack_agents_drift"]

    def test_the_drift_key_is_the_last_claude_key_and_a_count(self):
        self.assertEqual(CLIENT_WIRING_KEYS["claude"][-1], "stack_agents_drift")
        self.wire()
        self.assertIs(type(self.wiring()["claude"]["stack_agents_drift"]), int)  # a number: a boolean would not say how many

    def test_a_stale_or_wider_user_agent_makes_the_wiring_incomplete(self):
        """The fail-first of CPA-V-10: a fixture with one stale user agent reported `complete: true`, because nothing compared the agent files with adoption/agents/claude."""
        self.wire()
        self.assertEqual((self.drift(), self.wiring()["complete"]), (0, True))
        agent = self.home / ".claude/agents" / AGENT_FILES[0]
        agent.write_bytes(agent.read_bytes().replace(AGENT_TOOLS.encode(), b"tools: Read, Grep, Glob, Bash"))  # a wider copy: more tools than the source gives
        result = self.wiring()
        self.assertEqual((result["claude"]["stack_agents_drift"], result["complete"]), (1, False))
        others = {key: value for key, value in result["claude"].items() if key != "stack_agents_drift"}
        self.assertEqual(others, {key: value for key, value in WIRED["claude"].items() if key != "stack_agents_drift"}, "the drift alone turned completeness off")
        agent.write_bytes(agent.read_bytes().replace(b"tools: Read, Grep, Glob, Bash\n", b"\n"))  # the `tools` field gone: an omitted field means every tool
        self.assertEqual((self.drift(), self.wiring()["complete"]), (1, False))
        agent.write_bytes(agent_bytes(AGENT_FILES[0]))
        self.assertEqual((self.drift(), self.wiring()["complete"]), (0, True))

    def test_drift_counts_each_changed_missing_and_unlisted_definition(self):
        self.wire()
        agents = self.home / ".claude/agents"
        flipped = bytearray((agents / AGENT_FILES[0]).read_bytes())
        flipped[0] ^= 1  # the same size, one bit different: equal length is not equal bytes
        (agents / AGENT_FILES[0]).write_bytes(bytes(flipped))
        self.assertEqual(self.drift(), 1)
        (agents / AGENT_FILES[1]).unlink()  # absent
        self.assertEqual(self.drift(), 2)
        self.write(".claude/agents/not-shipped-here.md", agent_bytes("not-shipped-here.md"))  # a definition the client serves and nothing here checks
        self.assertEqual(self.drift(), 3)
        self.write(".claude/agents/another.md", b"")
        self.assertEqual(self.drift(), 4)
        (agents / AGENT_FILES[0]).write_bytes(agent_bytes(AGENT_FILES[0]))
        (agents / AGENT_FILES[1]).write_bytes(agent_bytes(AGENT_FILES[1]))
        (agents / "not-shipped-here.md").unlink()
        (agents / "another.md").unlink()
        self.assertEqual(self.drift(), 0)

    def test_the_four_vendor_definitions_are_listed_and_files_that_are_not_markdown_are_ignored(self):
        self.assertEqual(VENDOR_HOST_AGENTS, ("codebase-memory-auditor.md", "codebase-memory-scout.md", "codebase-memory.md", "semble-search.md"))
        self.assertFalse(set(VENDOR_HOST_AGENTS) & {path.name for path in STACK_AGENTS_SOURCE.glob("*.md")}, "a listed definition is one this checkout does not ship")
        self.wire()
        for name in VENDOR_HOST_AGENTS:  # whatever their text: they are the vendors' own
            self.write(f".claude/agents/{name}", f"vendor {PRIVATE}\n")
        self.assertEqual(self.drift(), 0)
        self.write(".claude/agents/" + AGENT_FILES[0] + ".bak.20261005T005836Z", agent_bytes(AGENT_FILES[0]) + b"\n")  # a backup is not an agent file
        self.write(".claude/agents/notes.txt", "x")
        self.write(".claude/agents/nested/notes.txt", "x")  # the client keeps names ending .md only
        self.assertEqual(self.drift(), 0)
        self.assertEqual(self.wiring()["complete"], True)

    def test_a_link_or_a_folder_in_place_of_a_definition_is_drift(self):
        self.wire()
        agents = self.home / ".claude/agents"
        identical = self.write("identical-copy.md", agent_bytes(AGENT_FILES[0]))
        (agents / AGENT_FILES[0]).unlink()
        (agents / AGENT_FILES[0]).symlink_to(identical)  # the bytes are equal, but the client's file is a link
        self.assertEqual(self.drift(), 1)
        (agents / AGENT_FILES[1]).unlink()
        (agents / AGENT_FILES[1]).mkdir()  # a folder where a file belongs
        self.assertEqual(self.drift(), 2)
        self.write(".claude/agents/linked-extra.md", "x")
        (agents / "linked-extra.md").unlink()
        (agents / "linked-extra.md").symlink_to(identical)  # a link the client would load, and nothing here ships it
        self.assertEqual(self.drift(), 3)

    def test_an_absent_agents_folder_counts_every_definition_of_the_checkout(self):
        self.write(".claude/settings.json", {})
        self.assertEqual(self.drift(), len(AGENT_FILES))

    def test_the_drift_follows_claude_config_dir(self):
        self.wire()
        moved = self.home / "elsewhere"
        (self.home / ".claude").rename(moved)
        self.assertEqual(self.drift(), len(AGENT_FILES))  # the default home has no agents folder any more
        env = {**self.env, "CLAUDE_CONFIG_DIR": str(moved)}
        self.assertEqual(self.drift(env), 0)
        (moved / "agents" / AGENT_FILES[2]).write_bytes(b"stale")
        self.assertEqual(self.drift(env), 1)

    def test_the_drift_is_null_when_a_source_or_the_folder_cannot_be_compared(self):
        self.wire()
        agents = self.home / ".claude/agents"
        source = self.root / "adoption/agents/claude"
        kept = (source / AGENT_FILES[0]).read_bytes()
        (source / AGENT_FILES[0]).unlink()
        self.assertEqual(self.drift(), 1, "a definition the checkout no longer ships, and that is not one of the vendors', is drift")
        (source / AGENT_FILES[0]).write_bytes(kept)
        shutil.rmtree(source)  # no source folder: nothing to compare with, even where the agents are installed
        self.assertIsNone(self.drift())
        source.mkdir(parents=True)
        self.assertIsNone(self.drift(), "a source folder with no definition")
        for name in AGENT_FILES:
            (source / name).write_bytes(agent_bytes(name))
        self.assertEqual(self.drift(), 0)
        (source / "folder.md").mkdir()  # a source entry that is not a file cannot be compared with
        self.assertIsNone(self.drift())
        (source / "folder.md").rmdir()
        self.assertEqual(self.drift(), 0)
        shutil.rmtree(agents)
        agents.write_text("a file where the folder belongs", encoding="utf-8")
        self.assertIsNone(self.drift())
        agents.unlink()
        (self.home / "linked-agents").mkdir()
        agents.symlink_to(self.home / "linked-agents")  # a linked folder: what the client loads through it is not known here
        self.assertIsNone(self.drift())

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads a file whatever its mode")
    def test_the_drift_is_null_for_an_unreadable_folder_or_definition(self):
        self.wire()
        agents = self.home / ".claude/agents"
        definition = agents / AGENT_FILES[0]
        definition.chmod(0)
        try:
            self.assertIsNone(self.drift())
        finally:
            definition.chmod(0o644)
        shipped = self.root / "adoption/agents/claude" / AGENT_FILES[1]
        shipped.chmod(0)  # a source copy that cannot be read: nothing to compare with
        try:
            self.assertIsNone(self.drift())
        finally:
            shipped.chmod(0o644)
        agents.chmod(0)
        try:
            self.assertIsNone(self.drift())
        finally:
            agents.chmod(0o755)
        self.assertEqual(self.drift(), 0)

    def test_a_null_drift_makes_complete_false_like_every_other_null(self):
        self.wire()
        shutil.rmtree(self.root / "adoption/agents/claude")
        result = self.wiring()
        self.assertEqual((result["claude"]["stack_agents_drift"], result["complete"]), (None, False))
        others = {key: value for key, value in result["claude"].items() if key != "stack_agents_drift"}
        self.assertEqual(others, {key: value for key, value in WIRED["claude"].items() if key != "stack_agents_drift"})

    def test_the_two_argument_form_of_claude_wiring_compares_with_this_repositorys_own_definitions(self):
        claude_dir = self.home / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text("{}", encoding="utf-8")
        report = adoption_status.claude_wiring(claude_dir, self.env)
        self.assertIn("stack_agents_drift", report)
        shipped = sorted(path.name for path in STACK_AGENTS_SOURCE.iterdir())
        self.assertTrue(shipped and all(name.endswith(".md") for name in shipped), "the source folder holds definitions only")
        self.assertEqual(report["stack_agents_drift"], len(shipped))  # nothing installed: every shipped definition is missing

    def make_socket(self, directory, name):
        """A socket file ``name`` in ``directory``, bound by its relative name from there so that the length limit of a socket path (104 bytes on macOS) never matters."""
        server = socket.socket(socket.AF_UNIX)
        self.addCleanup(server.close)
        here = os.getcwd()
        os.chdir(directory)
        try:
            server.bind(name)
        finally:
            os.chdir(here)

    def test_a_definition_below_the_top_is_drift_at_any_depth(self):
        """Review of #1062 at e70d2de0a (the Claude read, P1): the client loads the agents folder recursively (https://code.claude.com/docs/en/sub-agents.md L176-L182; its walker enters every folder and keeps names ending
        .md), so a definition below the top is one it serves, and the check read the top only: `agents/old/stack-verifier.md` reported 0 and `complete: true`."""
        self.wire()
        agents = self.home / ".claude/agents"
        self.write(".claude/agents/old/" + AGENT_FILES[0], agent_bytes(AGENT_FILES[0]))  # a shipped name, one folder down
        self.assertEqual((self.drift(), self.wiring()["complete"]), (1, False))
        self.write(".claude/agents/a/b/c/d/deep.md", agent_bytes("deep.md"))
        self.assertEqual(self.drift(), 2)
        self.write(".claude/agents/.hidden/dot.md", agent_bytes("dot.md"))  # the client lists hidden files too
        self.write(".claude/agents/.dot-at-the-top.md", agent_bytes("dot-at-the-top.md"))
        self.assertEqual(self.drift(), 4)
        self.write(".claude/agents/a/notes.txt", "x")
        (agents / "empty").mkdir()
        (agents / "folder.md").mkdir()  # a folder whose name ends .md is a folder: entered, not counted
        self.assertEqual(self.drift(), 4)
        shutil.rmtree(agents / "old")
        shutil.rmtree(agents / "a")
        shutil.rmtree(agents / ".hidden")
        (agents / ".dot-at-the-top.md").unlink()
        self.assertEqual((self.drift(), self.wiring()["complete"]), (0, True))

    # The rows of the vendor-collision test: (case, the text of a vendor-named file, what the check does). Each row was also given to the installed client (as a project agent with its own name token): the verdict
    # in the comment is the client's against this check's, see tests/fixtures/agent_frontmatter/client-oracle.json for the corpus. "agree": the check reads the name the client served; "agree-none": the client
    # served none and the check reads none; "over-report": the client serves nothing from the text (no description, an invalid name) and the check counts a name anyway, the safe direction; "unreadable": the
    # parse throws and the client goes on with a second attempt that the check does not reproduce, so the count is unknown.
    COLLISION_ROWS = (
        ('a comment at the left margin between the key and its indented value', '---\nname:\n# role\n  stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a comment on the key line, the value below', '---\nname: # c\n  stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a comment at the left margin, then a blank line, then the value', '---\nname:\n# role\n\n  stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('an indented comment between the key and the value', '---\nname:\n  # role\n  stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a comment at the left margin after a block scalar header', '---\nname: >-\n# role\n  stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'unknown'),  # unreadable-where-none
        ('a comment at the left margin after the value', '---\nname:\n  stack-verifier\n# role\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a quoted value below a comment at the left margin', '---\nname:\n# role\n  "stack-verifier"\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('the plain name', '---\nname: stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a quoted key', '---\n"name": stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a single-quoted key', "---\n'name': stack-verifier\ndescription: A fixture.\n---\nBody.\n", 'drift'),  # agree
        ('a folded block scalar that strips', '---\nname: >-\n  stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a folded block scalar that clips', '---\nname: >\n  stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'no drift'),  # agree
        ('a literal block scalar that strips', '---\nname: |-\n  stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a literal block scalar that clips', '---\nname: |\n  stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'no drift'),  # agree
        ('an escape sequence in a double-quoted value', '---\nname: "stack-\\u0076erifier"\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a hexadecimal escape', '---\nname: "stack-\\x76erifier"\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a byte order mark before the opener', '\ufeff---\nname: stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('CRLF line endings', '---\r\nname: stack-verifier\r\ndescription: A fixture.\r\n---\r\nBody.\r\n', 'drift'),  # agree
        ('the name in single quotes', "---\nname: 'stack-verifier'\ndescription: A fixture.\n---\nBody.\n", 'drift'),  # agree
        ('the name in double quotes', '---\nname: "stack-verifier"\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('the name and a comment', '---\nname: stack-verifier # c\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a hash that starts no comment', '---\nname: stack-verifier#x\ndescription: A fixture.\n---\nBody.\n', 'no drift'),  # agree
        ('the name with trailing spaces', '---\nname: stack-verifier   \ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('the value on the next line', '---\nname:\n  stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('an anchor on the name', '---\nname: &a stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a tag on the name', '---\nname: !!str stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a complex key', '---\n? name\n: stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('the name twice, the last winning', '---\nname: other\nname: stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ("the name twice, the first one's value kept in a first-wins reader", '---\nname: stack-verifier\nname: other\ndescription: A fixture.\n---\nBody.\n', 'no drift'),  # over-report
        ('a block indented as a whole', '---\n  name: stack-verifier\n  description: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a flow mapping as the whole block', '---\n{name: stack-verifier, description: x}\n---\nBody.\n', 'drift'),  # agree
        ('the key in capitals', '---\nName: stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'no drift'),  # agree-none
        ('a tab inside another value', '---\nname: stack-verifier\ndescription: a\tb\n---\nBody.\n', 'drift'),  # agree
        ('a name nested under another key', '---\nmeta:\n  name: stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'no drift'),  # agree-none
        ('a name inside a literal block of another key', '---\nnotes: |\n  name: stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'no drift'),  # agree-none
        ('a sequence at the left margin before the name', '---\ntools:\n- Read\n- Grep\nname: stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('a flow sequence over two lines in another key', '---\ntools: [a,\n  b]\nname: stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'drift'),  # agree
        ('an anchor on another key', '---\ndescription: &d x\nname: stack-verifier\n---\nBody.\n', 'drift'),  # agree
        ('a number as the name', '---\nname: 123\ndescription: A fixture.\n---\nBody.\n', 'no drift'),  # agree-none
        ('null as the name', '---\nname: null\ndescription: A fixture.\n---\nBody.\n', 'no drift'),  # agree-none
        ('an empty name', '---\nname:\ndescription: A fixture.\n---\nBody.\n', 'no drift'),  # agree-none
        ('an empty quoted name', "---\nname: ''\ndescription: A fixture.\n---\nBody.\n", 'no drift'),  # agree-none
        ('no description', '---\nname: stack-verifier\n---\nBody.\n', 'drift'),  # over-report
        ('a description that is not a string', '---\nname: stack-verifier\ndescription: [a, b]\n---\nBody.\n', 'drift'),  # over-report
        ('a flow sequence as the whole block', '---\n[a, b]\n---\nBody.\n', 'no drift'),  # agree-none
        ('a scalar as the whole block', '---\nname\n---\nBody.\n', 'no drift'),  # agree-none
        ('a name that starts with a dash', '---\nname: -stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'no drift'),  # over-report
        ('a name with a colon after normalization', '---\nname: "a:stack-verifier"\ndescription: A fixture.\n---\nBody.\n', 'no drift'),  # over-report
        ('text after a closing quote', '---\nname: "stack-verifier"x\ndescription: A fixture.\n---\nBody.\n', 'unknown'),  # unreadable-where-none
        ('an unclosed double quote', '---\nname: "stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'unknown'),  # unreadable-where-none
        ('a mapping where a name was meant', '---\nname: a: stack-verifier\ndescription: A fixture.\n---\nBody.\n', 'unknown'),  # unreadable-where-none
        ('a trailing colon', '---\nname: stack-verifier:\ndescription: A fixture.\n---\nBody.\n', 'unknown'),  # unreadable-where-none
        ('a description with a colon and a space', '---\nname: stack-verifier\ndescription: Use when: a thing\n---\nBody.\n', 'unknown'),  # unreadable
        ('a stray line at the left margin', '---\nname: stack-verifier\nstray line\ndescription: A fixture.\n---\nBody.\n', 'unknown'),  # unreadable-where-none
        ('an unterminated flow sequence', '---\nname: stack-verifier\ntools: [a, b\ndescription: A fixture.\n---\nBody.\n', 'unknown'),  # unreadable
        ('no front matter', 'name: stack-verifier\n', 'no drift'),  # agree-none
        ('an unterminated block', '---\nname: stack-verifier\n', 'no drift'),  # agree-none
        ('an empty block', '---\n---\nname: stack-verifier\n', 'no drift'),  # agree-none
        ('the block ends at the first --- after the opener', '---\ndescription: a --- b\nname: stack-verifier\n---\nBody.\n', 'no drift'),  # agree-none
        ('an opener followed by spaces and blank lines', '---   \n\nname: stack-verifier\ndescription: x\n---\nBody.\n', 'drift'),  # agree
        ('an opener with a tab after it', '---\t\nname: stack-verifier\ndescription: x\n---\nBody.\n', 'drift'),  # agree
        ('a closer with trailing text', '---\nname: stack-verifier\ndescription: x\n--- y\nBody.\n', 'drift'),  # agree
        ('four dashes', '----\nname: stack-verifier\ndescription: x\n---\nBody.\n', 'no drift'),  # agree-none
        ('text before the opener', 'text\n---\nname: stack-verifier\ndescription: x\n---\nBody.\n', 'no drift'),  # agree-none
        ('a space before the opener', ' ---\nname: stack-verifier\ndescription: x\n---\nBody.\n', 'no drift'),  # agree-none
        ('a blank line before the opener', '\n---\nname: stack-verifier\ndescription: x\n---\nBody.\n', 'no drift'),  # agree-none
        ('a lone CR line ending', '---\rname: stack-verifier\rdescription: A fixture.\r---\rBody.\r', 'no drift'),  # agree-none
        ('a line separator in a value', '---\nname: stack-verifier\ndescription: a\u2028b\n---\nBody.\n', 'drift'),  # agree
    )

    def real_env(self):
        """The environment of the wiring check with the pinned bun named in it; unavailable (a skip, or a failure under GitHub Actions) where that bun is not installed."""
        return {**self.env, adoption_status.BUN_ENV: real_bun()}

    def fake_env(self, **behavior):
        directory = Path(tempfile.mkdtemp(prefix="fake-bun-"))
        self.addCleanup(shutil.rmtree, directory, True)
        return {**self.env, adoption_status.BUN_ENV: str(make_fake_bun(directory, **behavior))}, directory

    def test_a_vendor_file_that_declares_the_name_of_a_shipped_definition_is_drift(self):
        """Review of #1062 (the Claude read, P3): the four vendor names were exempt whatever they held, and the client keys a definition by its `name`: one that declares a shipped role's name can replace it unseen
        (of two files that declare one name, one is chosen by file system read order). Rounds 1 and 2 read the name with a reader written here; each missed a spelling that the client's parser reads (a quoted key, a
        block scalar, a comment line at the left margin). The design round (the command center's adjudication of 2026-10-13) reads it with the client's own parser: every row below is what the client serves."""
        self.wire()
        env = self.real_env()
        for label, content, expectation in self.COLLISION_ROWS:
            with self.subTest(case=label):
                self.write(f".claude/agents/{VENDOR_HOST_AGENTS[0]}", content)
                report = self.wiring(env)
                self.assertEqual(report["claude"]["stack_agents_drift"], {"drift": 1, "no drift": 0, "unknown": None}[expectation])
                self.assertEqual(report["complete"], expectation == "no drift", "a count that is not zero, or unknown, is never complete wiring")
        (self.home / ".claude/agents" / VENDOR_HOST_AGENTS[0]).unlink()
        self.assertEqual(self.drift(env), 0)
        for name in VENDOR_HOST_AGENTS:  # each of the four, with a shipped name
            with self.subTest(vendor=name):
                self.write(f".claude/agents/{name}", agent_bytes(AGENT_FILES[1]))
                self.assertEqual(self.drift(env), 1)
                (self.home / ".claude/agents" / name).unlink()
        self.assertEqual(self.drift(env), 0)

    def test_the_vendor_definitions_of_this_host_shape_are_not_drift(self):
        """The shapes of the four vendor-installed definitions on the first host (a `tools` list over many lines, flow lists for `mcpServers` and `skills`, a permission mode): another name, so no drift."""
        self.wire()
        vendor = ("---\nname: vendors-own\ndescription: A search role of a code index.\ntools:\n  - mcp__x__a\n  - mcp__x__b\nmcpServers: [x-mcp]\npermissionMode: dontAsk\nskills: [y-skill]\neffort: low\n---\nbody\n")
        self.write(f".claude/agents/{VENDOR_HOST_AGENTS[0]}", vendor)
        report = self.wiring(self.real_env())
        self.assertEqual((report["claude"]["stack_agents_drift"], report["complete"]), (0, True))

    def test_a_vendor_file_without_front_matter_needs_no_bun(self):
        """Nothing is declared where there is no front matter, so a host without the pinned bun still has a count for the folders that hold such files (the ordinary fixtures of this class)."""
        self.wire()
        env = {**self.env, adoption_status.BUN_ENV: "/nonexistent/bun"}
        for content in (b"", b"# notes\n", b"vendor text\n", b"name: stack-verifier\n"):
            with self.subTest(content=content[:20]):
                self.write(f".claude/agents/{VENDOR_HOST_AGENTS[0]}", content)
                self.assertEqual(self.drift(env), 0)

    def test_without_the_pinned_bun_a_vendor_file_with_front_matter_makes_the_count_unknown_never_zero(self):
        self.wire()
        self.write(f".claude/agents/{VENDOR_HOST_AGENTS[0]}", "---\nname: vendors-own\ndescription: x\n---\nbody\n")
        absent = {**self.env, adoption_status.BUN_ENV: "/nonexistent/bun"}
        wrong, _ = self.fake_env(version="1.4.2")
        for label, env in (("no bun at the named path", absent), ("a bun of another version", wrong)):
            with self.subTest(case=label):
                report = self.wiring(env)
                self.assertIsNone(report["claude"]["stack_agents_drift"])
                self.assertFalse(report["complete"])

    def test_the_wiring_hands_one_batch_with_the_shipped_definitions_and_the_vendor_files_to_the_parser(self):
        self.wire()
        for name in VENDOR_HOST_AGENTS:
            self.write(f".claude/agents/{name}", f"---\nname: {name[:-3]}\ndescription: x\n---\nbody\n")
        env, directory = self.fake_env()
        self.assertEqual(self.drift(env), 0)
        calls = fake_calls(directory)
        self.assertEqual([call["call"] for call in calls], ["version", "parse"], "one process for the whole check")
        self.assertEqual(calls[1]["blocks"], len(AGENT_FILES) + len(VENDOR_HOST_AGENTS))
        self.write(f".claude/agents/{VENDOR_HOST_AGENTS[2]}", f"---\nname: {AGENT_FILES[0][:-3]}\ndescription: x\n---\nbody\n")
        self.assertEqual(self.drift(env), 1, "the stand-in reads `name:` plainly; the vendor file declares a shipped name")

    def test_a_parse_that_throws_for_a_vendor_file_or_for_a_shipped_definition_makes_the_count_unknown(self):
        self.wire()
        self.write(f".claude/agents/{VENDOR_HOST_AGENTS[0]}", "---\nname: vendors-own\ndescription: x\n---\nbody\n")
        shipped = len(AGENT_FILES)
        for label, position in (("a shipped definition", 0), ("the vendor's own file", shipped)):
            answers = [{"state": "name", "name": "n"}] * (shipped + 1)
            answers[position] = {"state": "throws"}
            env, _ = self.fake_env(parse="answers", answers=answers)
            with self.subTest(throws=label):
                report = self.wiring(env)
                self.assertIsNone(report["claude"]["stack_agents_drift"])
                self.assertFalse(report["complete"])

    def test_a_bun_that_fails_in_any_way_makes_the_count_unknown(self):
        self.wire()
        self.write(f".claude/agents/{VENDOR_HOST_AGENTS[0]}", "---\nname: vendors-own\ndescription: x\n---\nbody\n")
        for label, behavior in (("a bun that exits with an error", dict(parse="exit", status=1)), ("an answer that is not JSON", dict(parse="garbage")), ("too few answers", dict(parse="short"))):
            env, _ = self.fake_env(**behavior)
            with self.subTest(case=label):
                report = self.wiring(env)
                self.assertIsNone(report["claude"]["stack_agents_drift"])
                self.assertFalse(report["complete"])

    def test_every_shipped_definition_is_settled_by_the_parser_before_a_vendor_file_is_held_against_it(self):
        """A shipped source whose front matter the parser throws on (a description with a colon and a space) leaves nothing to compare the vendors' files with: unknown, as the client's second attempt is not reproduced."""
        self.wire()
        source = self.root / "adoption/agents/claude" / AGENT_FILES[0]
        source.write_bytes(source.read_bytes().replace(b"description: ", b"description: Use when: ", 1))
        (self.home / ".claude/agents" / AGENT_FILES[0]).write_bytes(source.read_bytes())
        self.write(f".claude/agents/{VENDOR_HOST_AGENTS[0]}", "---\nname: vendors-own\ndescription: x\n---\nbody\n")
        report = self.wiring(self.real_env())
        self.assertIsNone(report["claude"]["stack_agents_drift"])
        self.assertFalse(report["complete"])

    def test_a_vendor_file_over_the_clients_size_limit_is_unknown(self):
        """The client loads no file over its byte limit; this reads at most that many bytes, and a vendor file it cannot read whole declares a name that cannot be told (the first reader took it for a file with no name)."""
        self.wire()
        self.write(f".claude/agents/{VENDOR_HOST_AGENTS[0]}", b"---\nname: vendors-own\n---\n" + b"x" * adoption_status.CLIENT_FILE_LIMIT)
        report = self.wiring()
        self.assertIsNone(report["claude"]["stack_agents_drift"])
        self.assertFalse(report["complete"])

    def test_a_vendor_file_that_is_one_long_unterminated_block_is_read_in_linear_time(self):
        """Review of #1062 at 2723f8fd (the local codex review, P2): a 64 KiB fixture of this shape kept the whole client_wiring call past five seconds; the file declares nothing, so it needs no bun and is not drift."""
        self.wire()
        self.write(f".claude/agents/{VENDOR_HOST_AGENTS[0]}", b"---" + b"\n" * 65536)
        started = time.monotonic()
        report = self.wiring()
        self.assertLess(time.monotonic() - started, 10.0)
        self.assertEqual(report["claude"]["stack_agents_drift"], 0)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads a file whatever its mode")
    def test_a_vendor_file_that_cannot_be_read_is_not_drift_for_what_it_might_declare(self):
        """The client runs as the same user and cannot read it either, so it loads no definition from it."""
        self.wire()
        vendor = self.home / ".claude/agents" / VENDOR_HOST_AGENTS[0]
        vendor.write_bytes(agent_bytes(AGENT_FILES[0]))
        vendor.chmod(0)
        try:
            self.assertEqual(self.drift(), 0)
        finally:
            vendor.chmod(0o644)
        self.assertEqual(self.drift(self.real_env()), 1)

    def test_a_folder_that_cannot_be_listed_after_it_was_opened_is_unknown(self):
        self.wire()
        real = os.listdir

        def failing(path=None):
            if isinstance(path, int):  # the agents folder is read by descriptor
                raise PermissionError(errno.EACCES, "denied")
            return real(path)
        with patch.object(os, "listdir", failing):
            self.assertIsNone(self.drift())
        self.assertEqual(self.drift(), 0)

    def test_a_vendor_name_below_the_top_or_as_a_link_is_not_the_vendors_own(self):
        self.wire()
        agents = self.home / ".claude/agents"
        self.write(".claude/agents/sub/" + VENDOR_HOST_AGENTS[1], "vendor\n")  # the exemption is for the top, where the vendors' tools write
        self.assertEqual(self.drift(), 1)
        (agents / "sub" / VENDOR_HOST_AGENTS[1]).unlink()
        self.assertEqual(self.drift(), 0)
        elsewhere = self.write("elsewhere.md", "x")
        (agents / VENDOR_HOST_AGENTS[2]).symlink_to(elsewhere)  # the client follows it and nothing here can say what it declares
        self.assertEqual(self.drift(), 1)

    def test_a_link_to_a_file_is_counted_and_what_the_clients_walker_skips_is_not(self):
        """The 2.1.296 walker follows a link with stat and keeps a file whose name ends in .md (`isFile()`): a link to a file counts; a pipe, a socket, a device and a link to nothing are not kept (review of #1062 at
        e22358e46, the Claude delta, P3: they were counted)."""
        self.wire()
        agents = self.home / ".claude/agents"
        target_file, target_folder = self.write("target-file.md", agent_bytes("target.md")), self.home / "target-folder"
        target_folder.mkdir()
        (target_folder / "inside.md").write_bytes(agent_bytes("inside.md"))
        (agents / "sub").mkdir()
        (agents / "sub" / "link.md").symlink_to(target_file)  # a link to a file named *.md: a definition the client would load
        self.assertEqual(self.drift(), 1)
        (agents / "dangling.md").symlink_to(self.home / "missing.md")  # a link to nothing: the stat fails and the walker skips it
        self.assertEqual(self.drift(), 1)
        (agents / "notes-link").symlink_to(target_file)  # a link to a file not named *.md: the walker keeps names ending .md only
        (agents / "dangling-notes").symlink_to(self.home / "missing-notes")
        self.assertEqual(self.drift(), 1)
        os.mkfifo(agents / "pipe.md")  # opened without blocking; not a file, so the walker skips it
        os.mkfifo(agents / "pipe-notes")
        self.make_socket(agents, "socket.md")
        self.assertEqual(self.drift(), 1)
        (agents / "link-to-pipe.md").symlink_to(agents / "pipe.md")  # a link to a pipe or a socket leads to nothing the walker keeps
        (agents / "link-to-socket.md").symlink_to(agents / "socket.md")
        self.assertEqual(self.drift(), 1)
        (agents / "sub" / "link.md").unlink()
        self.assertEqual(self.drift(), 0)
        for where, name in ((agents, "linked-folder"), (agents, "linked-folder.md"), (agents / "sub", "deeper-link")):
            with self.subTest(link=f"{where.name}/{name}"):
                (where / name).symlink_to(target_folder)  # the client follows a link to a folder and loads what is in it: not known here
                self.assertIsNone(self.drift())
                self.assertEqual(self.wiring()["complete"], False)
                (where / name).unlink()
                self.assertEqual(self.drift(), 0)

    def test_describe_entry_tells_a_link_from_what_it_leads_to(self):
        folder = self.home / "described"
        folder.mkdir()
        (folder / "directory").mkdir()
        (folder / "link-to-directory").symlink_to(folder / "directory")
        (folder / "regular").write_bytes(b"x")
        os.mkfifo(folder / "pipe")
        descriptor = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, descriptor)
        describe = adoption_status.describe_entry
        self.assertEqual([describe(name, descriptor) for name in ("link-to-directory", "directory", "regular", "pipe", "missing")],
                         ["link", "folder", "unreadable", "other", "absent"])

    def test_a_markdown_file_without_a_name_is_still_counted_though_the_client_skips_it(self):
        """The client parses the front matter and skips a file with no `name` without a message (the 2.1.296 loader; CHANGELOG L7088). This check counts it: a file that is one line from being a definition, found by a
        reading of the front matter that is less exact than the client's. The record says so."""
        self.wire()
        agents = self.home / ".claude/agents"
        for label, content in (("an empty file", b""), ("notes", b"# notes about the agents\n"), ("front matter without a name", b"---\ndescription: x\n---\nbody\n")):
            with self.subTest(file=label):
                (agents / "no-name.md").write_bytes(content)
                self.assertEqual(self.drift(), 1)
                (agents / "no-name.md").unlink()
                self.assertEqual(self.drift(), 0)

    def test_the_walk_is_bounded_and_a_tree_past_the_bound_is_unknown_not_a_count(self):
        self.wire()
        agents = self.home / ".claude/agents"
        self.write(".claude/agents/one/two/three.md", agent_bytes("three.md"))
        with patch.object(adoption_status, "AGENT_WALK_DEPTH", 2):
            self.assertEqual(self.drift(), 1)  # the file sits two folders down: at the bound
        with patch.object(adoption_status, "AGENT_WALK_DEPTH", 1):
            self.assertIsNone(self.drift())
        entries = len(AGENT_FILES) + 3  # the shipped files, one, two and three.md
        with patch.object(adoption_status, "AGENT_WALK_ENTRIES", entries):
            self.assertEqual(self.drift(), 1)
        with patch.object(adoption_status, "AGENT_WALK_ENTRIES", entries - 1):
            self.assertIsNone(self.drift())
        self.assertEqual(adoption_status.AGENT_WALK_DEPTH, 8)
        self.assertGreaterEqual(adoption_status.AGENT_WALK_ENTRIES, 1_000)

    def test_the_folders_are_opened_below_a_descriptor_without_following_a_link(self):
        """Review of #1062 (Astra, P1): the check inspected a path and opened it again, so a replacement between the two was read through. Every open below the Claude home is relative to the descriptor of its folder
        and refuses a link; what is described is what the descriptor holds."""
        self.wire()
        self.write(".claude/agents/sub/extra.md", agent_bytes("extra.md"))
        opens = []
        real_open = os.open

        def recording(path, flags, *rest, dir_fd=None, **keywords):
            opens.append((str(path), flags, dir_fd))
            return real_open(path, flags, *rest, dir_fd=dir_fd, **keywords)
        with patch.object(os, "open", recording):
            self.assertEqual(adoption_status.stack_agents_drift(self.home / ".claude", self.root / "adoption/agents/claude"), 1)
        below = [entry for entry in opens if entry[2] is not None]
        self.assertGreaterEqual(len(below), len(AGENT_FILES) + 3, "agents, every entry and the folder below")
        for entry_path, flags, dir_fd in below:
            self.assertTrue(flags & os.O_NOFOLLOW, entry_path)
            self.assertEqual(os.sep in entry_path, False, "a name relative to its folder's descriptor, never a path")
        self.assertTrue(any(flags & os.O_DIRECTORY for _, flags, _ in below))
        self.assertEqual(len(opens) - len(below), len(AGENT_FILES) + 1, "the Claude home and the checkout's source files are the only opens by path")

    def test_a_platform_that_cannot_refuse_links_reads_nothing(self):
        self.wire()
        self.assertEqual((self.drift(), self.roles()), (0, 2))
        with patch.object(adoption_status, "NO_FOLLOW_READS", False):
            result = self.wiring()
            self.assertEqual((result["claude"]["stack_agents_drift"], result["codex"]["stack_roles_matching"], result["complete"]), (None, None, False))
            self.assertIsNone(adoption_status.read_regular_bytes(self.home / ".claude/settings.json"), "no fallback to checking the path first")
        self.assertEqual((self.drift(), self.roles(), self.wiring()["complete"]), (0, 2, True))

    def test_read_regular_bytes_answers_for_every_kind_of_entry_without_following_a_link(self):
        folder = self.home / "kinds"
        folder.mkdir()
        regular = self.write("kinds/regular.md", b"bytes")
        (folder / "link-to-file").symlink_to(regular)
        (folder / "dangling").symlink_to(folder / "missing")
        (folder / "folder").mkdir()
        os.mkfifo(folder / "pipe")
        self.make_socket(folder, "socket")
        (folder / "big").write_bytes(b"x" * 11)
        read = adoption_status.read_regular_bytes
        self.assertEqual(read(regular), b"bytes")
        self.assertEqual(read(folder / "absent"), adoption_status.ABSENT)
        for name in ("link-to-file", "dangling", "folder", "pipe", "socket"):
            with self.subTest(entry=name):
                self.assertEqual(read(folder / name), adoption_status.NOT_A_FILE)
        self.assertIsNone(read(folder / "big", 10), "over the limit")
        self.assertEqual(read(folder / "big", 11), b"x" * 11)
        self.assertIsNone(read(regular / "below-a-file"), "a path through a file")
        descriptor = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, descriptor)
        self.assertEqual(read("regular.md", dir_fd=descriptor), b"bytes")
        self.assertEqual(read("link-to-file", dir_fd=descriptor), adoption_status.NOT_A_FILE)

    def interleave(self, build, call, action_for, allowed, minimum_points):
        """Run ``call`` on a fresh fixture for every point at which ``action_for(fixture)`` can be made, and once with no action: every answer must be one of ``allowed``, and the points must be numerous."""
        fixture = build()
        value, fired, calls = Interleaving().run(lambda: call(fixture), lambda: None, 0)
        self.assertFalse(fired)
        self.assertIn(value, allowed, "no replacement: the answer the fixture gives")
        answers = {}
        for target in range(1, calls + 3):
            fixture = build()
            value, fired, _ = Interleaving().run(lambda: call(fixture), lambda: action_for(fixture), target)
            if not fired:
                break
            answers[target] = value
            self.assertIn(value, allowed, f"a replacement after step {target} changed the answer")
        self.assertGreaterEqual(len(answers), minimum_points, "the replacement was tried at too few points to mean anything")
        return answers

    def race_fixture(self, kind):
        """A Claude home whose first shipped definition is stale (drift 1 as it stands), a folder outside it that holds exact copies of everything (what a path read through a replacement would see), and the checkout's source folder."""
        base = Path(tempfile.mkdtemp(prefix=f"race-{kind}-"))
        self.addCleanup(shutil.rmtree, base, True)
        source, home, outside = base / "source", base / "claude", base / "outside"
        for folder in (source, home / "agents", outside / "agents"):
            folder.mkdir(parents=True)
        for name in AGENT_FILES:
            for folder in (source, outside / "agents"):
                (folder / name).write_bytes(agent_bytes(name))
            (home / "agents" / name).write_bytes(agent_bytes(name))
        (home / "agents" / AGENT_FILES[0]).write_bytes(agent_bytes(AGENT_FILES[0]) + b"stale\n")
        return {"base": base, "source": source, "home": home, "agents": home / "agents", "outside": outside}

    def test_a_replacement_of_a_shipped_file_at_any_point_is_never_read_through(self):
        """Review of #1062 (Astra, P1): after the check looked at a shipped copy, the entry became a link to an outside file whose bytes equal the source, and the check read it: 0 and `complete: true`. A replacement is
        made after every step of the read; the answer is the stale copy that was there (1) or unknown, never 0."""
        def swap_in_a_link(fixture):
            link = fixture["agents"] / ".swap"
            os.symlink(fixture["outside"] / "agents" / AGENT_FILES[0], link)
            os.replace(link, fixture["agents"] / AGENT_FILES[0])
        answers = self.interleave(lambda: self.race_fixture("file"), lambda f: adoption_status.stack_agents_drift(f["home"], f["source"]), swap_in_a_link, {1, None}, 12)
        self.assertIn(1, answers.values(), "a replacement after the file was opened reads the stale copy that was opened")

    def test_a_replacement_of_the_agents_folder_at_any_point_is_never_read_through(self):
        def swap_in_a_link(fixture):
            os.rename(fixture["agents"], fixture["home"] / "agents-original")
            os.symlink(fixture["outside"] / "agents", fixture["agents"])
        answers = self.interleave(lambda: self.race_fixture("folder"), lambda f: adoption_status.stack_agents_drift(f["home"], f["source"]), swap_in_a_link, {1, None}, 12)
        self.assertIn(None, answers.values(), "a link that is there when the folder is opened is refused")
        self.assertIn(1, answers.values(), "a link that comes after the folder was opened leaves the opened folder as the one read")

    def test_a_replacement_of_a_folder_below_the_top_at_any_point_is_never_read_through(self):
        def build():
            fixture = self.race_fixture("nested")
            (fixture["agents"] / AGENT_FILES[0]).write_bytes(agent_bytes(AGENT_FILES[0]))
            (fixture["agents"] / "nested").mkdir()
            (fixture["agents"] / "nested" / "extra.md").write_bytes(agent_bytes("extra.md"))
            (fixture["outside"] / "empty").mkdir()
            return fixture

        def swap_in_a_link(fixture):
            os.rename(fixture["agents"] / "nested", fixture["agents"] / "nested-original")
            os.symlink(fixture["outside"] / "empty", fixture["agents"] / "nested")
        answers = self.interleave(build, lambda f: adoption_status.stack_agents_drift(f["home"], f["source"]), swap_in_a_link, {1, None}, 12)
        self.assertNotIn(0, answers.values())

    def roles_fixture(self):
        """A Codex home whose first role carrier is stale (1 matches as it stands) and an outside folder with exact copies."""
        base = Path(tempfile.mkdtemp(prefix="race-roles-"))
        self.addCleanup(shutil.rmtree, base, True)
        source, home, outside = base / "source", base / "codex", base / "outside"
        for folder in (source, home / "agents", outside / "agents"):
            folder.mkdir(parents=True)
        for name in ROLE_FILES:
            for folder in (source, home / "agents", outside / "agents"):
                (folder / name).write_bytes(role_bytes(name))
        (home / "agents" / ROLE_FILES[0]).write_bytes(role_bytes(ROLE_FILES[0]) + b"stale\n")
        return {"base": base, "source": source, "home": home, "agents": home / "agents", "outside": outside}

    def test_the_codex_role_count_is_never_read_through_a_replacement_either(self):
        """The shared reader's other caller (Astra asked for it to be audited): the same two replacements, made after every step, with a count of 1 as it stands."""
        def file_link(fixture):
            link = fixture["agents"] / ".swap"
            os.symlink(fixture["outside"] / "agents" / ROLE_FILES[0], link)
            os.replace(link, fixture["agents"] / ROLE_FILES[0])

        def folder_link(fixture):
            os.rename(fixture["agents"], fixture["home"] / "agents-original")
            os.symlink(fixture["outside"] / "agents", fixture["agents"])
        for label, action in (("file", file_link), ("folder", folder_link)):
            with self.subTest(replaced=label):
                answers = self.interleave(self.roles_fixture, lambda f: adoption_status.stack_roles_matching(f["home"], f["source"]), action, {1, None}, 6)
                self.assertNotIn(2, answers.values())

    def test_an_installed_definition_over_the_size_limit_is_unknown_not_drift(self):
        self.wire()
        definition = self.home / ".claude/agents" / AGENT_FILES[0]
        definition.write_bytes(b"x" * (adoption_status.CLIENT_FILE_LIMIT + 1))  # the client reads a file up to a limit too
        self.assertIsNone(self.drift())
        definition.write_bytes(b"x" * adoption_status.CLIENT_FILE_LIMIT)  # at the limit it is read, and it differs
        self.assertEqual(self.drift(), 1)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads a folder whatever its mode")
    def test_an_unreadable_folder_below_the_top_is_unknown(self):
        self.wire()
        locked = self.home / ".claude/agents/locked"
        locked.mkdir()
        locked.chmod(0)
        try:
            self.assertIsNone(self.drift())
        finally:
            locked.chmod(0o755)
        self.assertEqual(self.drift(), 0)

    def test_an_entry_that_vanishes_between_the_listing_and_its_opening_is_unknown(self):
        """Not 0 and not a count that leaves it out: the entry was listed, so the folder changed while it was read, and what it held is not known."""
        def vanish(fixture):
            (fixture["agents"] / AGENT_FILES[1]).unlink()
        answers = self.interleave(lambda: self.race_fixture("vanish"), lambda f: adoption_status.stack_agents_drift(f["home"], f["source"]), vanish, {1, 2, None}, 12)
        self.assertIn(None, answers.values(), "a vanished entry is unknown")
        self.assertIn(1, answers.values(), "after it was opened it is read as it was")
        self.assertIn(2, answers.values(), "before the listing it is simply absent")

    def test_a_link_is_told_by_the_answer_of_the_open_and_not_by_a_later_look(self):
        """Review of #1062 at e22358e46 (the Claude delta, P3): the refusal of the open was classified by a look at the entry afterwards, so a vendor-named link replaced by a regular file in between read as an
        unreadable file and was exempt. The refusal is ELOOP: the link is what the open met."""
        def build():
            fixture = self.race_fixture("link-swap")
            (fixture["agents"] / AGENT_FILES[0]).write_bytes(agent_bytes(AGENT_FILES[0]))  # no other drift
            (fixture["agents"] / VENDOR_HOST_AGENTS[0]).symlink_to(fixture["outside"] / "agents" / AGENT_FILES[0])  # a link to a file
            return fixture

        def swap_for_a_file(fixture):
            replacement = fixture["agents"] / ".swap"
            replacement.write_bytes(b"the vendor's own text\n")
            os.replace(replacement, fixture["agents"] / VENDOR_HOST_AGENTS[0])
        fixture = build()
        interleaving = Interleaving()
        value, _, _ = interleaving.run(lambda: adoption_status.stack_agents_drift(fixture["home"], fixture["source"]), lambda: None, 0)
        self.assertEqual(value, 1, "the link counts")
        refused = [index for index, (label, name, number) in enumerate(interleaving.trace, 1) if label == "os.open" and name == VENDOR_HOST_AGENTS[0] and number == errno.ELOOP]
        self.assertEqual(len(refused), 1, "the open that met the link")
        fixture = build()
        value, fired, _ = Interleaving().run(lambda: adoption_status.stack_agents_drift(fixture["home"], fixture["source"]), lambda: swap_for_a_file(fixture), refused[0])
        self.assertTrue(fired)
        self.assertEqual(value, 1, "the entry the open refused as a link is counted as one, whatever it became afterwards")

    def test_the_limitations_name_the_agent_folders_the_check_compares(self):
        text = CLIENT_WIRING_LIMITATIONS[0]
        for needle in ("Claude agent definitions", "adoption/agents/claude", "must be 0", "any folder below it", "never through a link", "cannot be told", "Bun.YAML.parse"):
            self.assertIn(needle, text)

    def test_a_text_value_can_never_leave_the_check(self):
        leaked = {**dict.fromkeys(CLIENT_WIRING_KEYS["claude"], True), "rtk_hook": PRIVATE}
        with patch("scripts.adoption_status.claude_wiring", return_value=leaked), self.assertRaises(AssertionError):
            client_wiring(self.root, self.env)
        with patch("scripts.adoption_status.codex_wiring", return_value={"extra": True}), \
                self.assertRaises(AssertionError):
            client_wiring(self.root, self.env)


class TokenEfficiencyProfileTests(unittest.TestCase):
    """The selected token practice is a real, resolvable profile of adoption/manifest.json."""

    LAYERS = ("token-efficiency", "code-navigation", "document-retrieval", "semantic-rag", "durable-memory",
              "mcp-surfaces")
    CURRENT_CHOICE = {"RTK": "rtk", "Context Mode": "context-mode", "Repomix": "repomix", "Headroom": "headroom",
                      "TOON": "toon", "ccusage": "ccusage"}
    # jcodemunch-mcp, ast-grep and codebase-memory-mcp are the code-navigation layer's task-selected tools and the
    # SubagentStart carrier's task-appended lanes, and they stay optional rows: neither bootstrap can install a profile
    # member that has no pin, and none of the three has one (docs/decisions/2026-09-30-task-model-routing.md).
    OPTIONAL = {"jcodemunch-mcp", "ast-grep", "codebase-memory-mcp", "context-hub", "agentsview", "claude-hud",
                "otel-tui", "omniroute"}
    PIN_FILES = ("adoption/pins-linux-x86_64.json", "adoption/pins-macos-arm64.json")

    @staticmethod
    def load(relative: str):
        return json.loads((REPO / relative).read_text(encoding="utf-8"))

    def setUp(self):
        self.profile = next(p for p in self.load("adoption/manifest.json")["profiles"] if p["id"] == "token-efficiency")
        self.rows = {row["component_id"] for row in self.load("docs/token-efficiency-stack.json")["rows"]}

    def test_the_profile_resolves_to_its_commands_and_recipes(self):
        with patch("scripts.adoption_status.shutil.which", return_value="/private/bin/tool"), \
                patch("scripts.adoption_status.git_revision", return_value=None):
            result = inspect_adoption(REPO / "adoption/manifest.json", REPO, ["token-efficiency"])
        self.assertEqual(result["manifest"]["status"], "valid", result["errors"])
        [profile] = result["profiles"]
        self.assertEqual(profile["status"], "prerequisites_present")
        self.assertEqual([item["name"] for item in profile["commands"]], self.profile["required_commands"])
        self.assertTrue(profile["recipes"] and all(item["present"] for item in profile["recipes"]))

    def test_the_profile_is_the_landscape_selection_and_leaves_optional_rows_out(self):
        layers = {layer["layer_id"]: layer for layer in self.load("catalogs/landscape/foundation.json")["layers"]}
        stack = {component["id"] for component in self.load("manifests/stack.json")["components"]}
        selected = set(self.profile["component_ids"])
        self.assertLessEqual(selected, stack)
        self.assertEqual(selected - self.rows, {"codex", "claude-code"})
        choice = layers["token-efficiency"]["current_choice"]
        self.assertTrue(all(name in choice for name in self.CURRENT_CHOICE), choice)
        winners = {winner["component_id"] for layer_id in self.LAYERS for winner in layers[layer_id]["winners"]}
        self.assertEqual(selected & self.rows, (winners & self.rows) | set(self.CURRENT_CHOICE.values()),
                         "a token row these layers now select (or drop) must join (or leave) the profile")
        self.assertEqual(selected & self.OPTIONAL, set())
        self.assertLessEqual(self.OPTIONAL, self.rows)

    def test_the_sixteen_subagent_tools_are_ten_profile_rows_and_six_optional_rows(self):
        # docs/token-efficiency-stack.md, "Inside Ultracode subagents": the 16 tools that run used are not the
        # profile's 14 component_ids. Ten are profile rows; six are optional rows; the profile's other four are the
        # two clients, ccusage (not run) and MCPorter (there only as Headroom's bridge).
        receipt = self.load("evidence/artifacts/token-e2e-ultracode-20260925/receipt.json")
        tools = {tool["component_id"] for tool in receipt["tools"]}
        selected = set(self.profile["component_ids"])
        self.assertEqual((len(tools), len(selected), len(tools & selected)), (16, 14, 10))
        self.assertEqual(tools - selected, {"jcodemunch-mcp", "ast-grep", "codebase-memory-mcp", "context-hub",
                                            "agentsview", "otel-tui"})
        self.assertLessEqual(tools - selected, self.OPTIONAL)
        self.assertEqual(selected - tools, {"codex", "claude-code", "ccusage", "mcporter"})

    def test_every_profile_component_has_a_pin_on_both_platforms(self):
        # adoption/bootstrap-linux.sh and adoption/bootstrap-macos.sh fail closed on a selected component that their
        # pin file lacks ("No pin in <file> for selected component(s)", exit 3, before anything is installed), and
        # adoption/bootstrap-macos.sh no longer exempts any component from a pin by default. So a profile lists only
        # components that both pin files carry; the bootstrap plan tests (tests/test_adoption_bootstrap_macos.py,
        # TokenEfficiencyPlanTests) fail otherwise, and they are outside this file's module set.
        selected = set(self.profile["component_ids"])
        for pin_file in self.PIN_FILES:
            with self.subTest(pin_file=pin_file):
                pinned = {tool["id"] for tool in self.load(pin_file)["tools"]}
                self.assertEqual(selected - pinned, set(), "a profile component without a pin makes the bootstrap exit 3")


class RetainedEvidenceTests(unittest.TestCase):
    """What the checker's Codex model was compared against stays in every clone of the repository."""

    README = REPO / "evidence/artifacts/adoption-status-truth-20260926/README.md"

    def test_every_file_the_evidence_readme_links_is_registered_and_not_ignored(self):
        # scripts/validate.py enumerates files through Git, which leaves ignored files out, so an evidence file that
        # .gitignore matches (the oracle outputs under "*.jsonl") passes it on the host that wrote the file and is
        # missing from every clone.
        git = native_which("git")
        if git is None or subprocess.run([git, "-C", str(REPO), "rev-parse", "--git-dir"], capture_output=True,
                                         stdin=subprocess.DEVNULL).returncode != 0:
            self.skipTest("needs the repository's Git checkout")
        manifest = json.loads((REPO / "manifests/evidence.json").read_text(encoding="utf-8"))
        registered = {entry["path"] for entry in manifest["files"]}
        targets = set()
        for link in re.findall(r"\]\(([^)\s#]+)[^)]*\)", self.README.read_text(encoding="utf-8")):
            path = (self.README.parent / link).resolve()
            if "://" not in link and not path.is_dir():
                targets.add(path.relative_to(REPO).as_posix())
        self.assertGreater(len(targets), 10)
        for target in sorted(targets):
            with self.subTest(target=target):
                self.assertTrue((REPO / target).is_file(), "linked file is missing")
                self.assertTrue(target in registered, "not registered in manifests/evidence.json")
                ignored = subprocess.run([git, "-C", str(REPO), "check-ignore", "-q", target], capture_output=True,
                                         stdin=subprocess.DEVNULL)
                self.assertEqual(ignored.returncode, 1, "matched by .gitignore, so no clone has it")


if __name__ == "__main__":
    unittest.main()
