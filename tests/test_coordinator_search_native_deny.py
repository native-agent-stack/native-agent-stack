"""CPA-V-03: a marked coordinator's WebSearch is denied natively at launch, not by failing the shared hook closed.

The claude-practice-audit finding (G03) was that the PreToolUse entry that denied WebSearch for marked coordinators had a 5 s timeout and no onFailure, so a missing runner, a timeout or a
crash let the call through. The command center ruled (docs/decisions/2026-10-13-coordinator-search-native-deny.md): enforcement is the launch's, a `permissions.deny` rule in the
coordinator's own --settings overlay (or --disallowedTools), which needs no runner and holds in every permission mode; the hook is advisory and its registration cannot exit 2.
These tests hold the overlay, the existence-checked registrations, the applier's retirement of the replaced command and, where the client is installed and the probe is asked for, the
client's own listing of its tools.
"""
import copy
import json
import os
import shutil
import signal
import string
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/adoption"))
import apply_claude_settings as acs  # noqa: E402

OVERLAY = ROOT / "adoption/templates/claude.coordinator.settings.template.json"
TEMPLATE = ROOT / "adoption/templates/claude.settings.template.json"
GUARD_NAME = "research-routing-guard.py"
OLD_COMMAND = 'python3 "${HOME}/.claude/hooks/research-routing-guard.py"'
SESSION = "synthetic-native-coordinator-session"


def guard_commands(settings):
    """(event, command) of every hook entry of `settings` that runs the research routing guard."""
    found = []
    for event, groups in (settings.get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                if GUARD_NAME in hook.get("command", ""):
                    found.append((event, hook["command"]))
    return found


def render(command, home):
    """What the installer's renderer makes of a template command: one string.Template pass with HOME given as written."""
    return string.Template(command).safe_substitute(HOME=home)   # the template names other placeholders too; $$ becomes $ as the renderer makes it


class OverlayTests(unittest.TestCase):
    def test_the_overlay_denies_websearch_and_nothing_else(self):
        data = json.loads(OVERLAY.read_text(encoding="utf-8"))
        self.assertEqual(data, {"permissions": {"deny": ["WebSearch"]}}, "only WebSearch: WebFetch and fetch-and-index keep their normal checks and their URL log")

    def test_the_profile_template_does_not_carry_the_denial(self):
        """The shared profile is every session's: an unmarked session keeps WebSearch, so the denial is in the coordinator's own overlay and in no shared file."""
        settings = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        self.assertNotIn("WebSearch", settings.get("permissions", {}).get("deny", []))
        self.assertNotIn("WebSearch", json.dumps(settings.get("disallowedTools", [])))


class RegistrationTests(unittest.TestCase):
    """Both registrations of the guard (UserPromptSubmit and PreToolUse) are existence-checked."""

    def commands(self):
        found = guard_commands(json.loads(TEMPLATE.read_text(encoding="utf-8")))
        self.assertEqual(sorted(event for event, _ in found), ["PreToolUse", "UserPromptSubmit"])
        return [command for _, command in found]

    def run_command(self, command, home, stdin=""):
        return subprocess.run(["sh", "-c", render(command, str(home))], input=stdin, text=True, capture_output=True, timeout=20, env={"PATH": os.environ["PATH"], "HOME": str(home)})

    def test_a_missing_guard_file_is_not_an_exit_2(self):
        """Fail-first: the bare `python3 <file>` of #868 exits 2 on a missing file, which blocks a prompt (UserPromptSubmit) or the tool call (PreToolUse); the registered command exits 0 and says nothing."""
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            old = self.run_command(OLD_COMMAND, home)
            self.assertEqual(old.returncode, 2, "the replaced command blocks on a missing file")
            for command in self.commands():
                with self.subTest(command=command[:60]):
                    done = self.run_command(command, home)
                    self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))

    def test_a_present_guard_file_is_run_with_the_hook_input(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            hooks = home / ".claude/hooks"
            hooks.mkdir(parents=True)
            shutil.copy(ROOT / "adoption/hooks/claude" / GUARD_NAME, hooks / GUARD_NAME)
            event = json.dumps({"session_id": SESSION, "hook_event_name": "PreToolUse", "tool_name": "WebSearch", "tool_input": {}})
            marked = {"PATH": os.environ["PATH"], "HOME": str(home), "NAS_RESEARCH_COORDINATOR_ROLE": "command-center", "NAS_RESEARCH_COORDINATOR_SESSION_ID": SESSION,
                      "XDG_STATE_HOME": str(home / "state")}
            for command in self.commands():
                with self.subTest(command=command[:60]):
                    done = subprocess.run(["sh", "-c", render(command, str(home))], input=event, text=True, capture_output=True, timeout=20, env=marked)
                    self.assertEqual(done.returncode, 0, done.stderr)
                    fields = json.loads(done.stdout)["hookSpecificOutput"]
                    self.assertIn("tools/research/dispatch --question", fields["additionalContext"])
                    self.assertNotIn("permissionDecision", fields)

    def test_the_registered_commands_keep_the_file_name_the_map_and_the_installer_look_for(self):
        for command in self.commands():
            self.assertIn(".claude/hooks/research-routing-guard.py", command)


class ApplierRetirementTests(unittest.TestCase):
    """merge_hooks de-duplicates by command, so the replaced command would run beside its replacement: the applier retires it (SUPERSEDED_HOOK_COMMANDS)."""

    HOME = "/home/example"

    def template(self):
        return json.loads(render(TEMPLATE.read_text(encoding="utf-8"), self.HOME))

    def host_with_old(self, extra=None):
        old = render(OLD_COMMAND, self.HOME)
        hooks = {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": old, "timeout": 5}]}],
                 "PreToolUse": [{"matcher": "^(WebSearch|WebFetch)$", "hooks": [{"type": "command", "command": old, "timeout": 5}]}]}
        hooks.update(extra or {})
        return {"hooks": hooks, "hostOnlySetting": "kept"}

    def test_the_replaced_command_is_retired_and_exactly_one_registration_remains_per_event(self):
        merged = acs.merge_settings(self.host_with_old(), self.template(), False, self.HOME)
        found = guard_commands(merged)
        self.assertEqual(sorted(event for event, _ in found), ["PreToolUse", "UserPromptSubmit"], found)
        for _, command in found:
            self.assertIn("[ -f", command)
            self.assertNotEqual(command, render(OLD_COMMAND, self.HOME))
        self.assertEqual(merged["hostOnlySetting"], "kept", "the host's own settings stay")

    def test_the_replaced_command_is_retired_when_the_host_keeps_its_held_out_carriers(self):
        merged = acs.merge_settings(self.host_with_old(), self.template(), True, self.HOME)
        self.assertEqual(len(guard_commands(merged)), 2)
        self.assertNotIn(render(OLD_COMMAND, self.HOME), [command for _, command in guard_commands(merged)])

    def test_the_unrendered_spelling_and_another_spelling_of_the_home_are_retired(self):
        for spelling in (OLD_COMMAND, render(OLD_COMMAND, self.HOME + "/"), render(OLD_COMMAND, self.HOME + "/./")):
            host = {"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": spelling}]}]}}
            with self.subTest(spelling=spelling):
                self.assertTrue(acs.runs_superseded_hook({"command": spelling}, self.HOME))
                merged = acs.merge_settings(copy.deepcopy(host), self.template(), False, self.HOME)
                self.assertEqual(sorted(event for event, _ in guard_commands(merged)), ["PreToolUse", "UserPromptSubmit"])

    def test_a_hook_the_host_wrote_for_itself_stays_even_when_it_runs_the_guard(self):
        own = [render(OLD_COMMAND, self.HOME) + " 2>/dev/null || true", "env X=1 " + render(OLD_COMMAND, self.HOME), render(OLD_COMMAND, "/opt/other-home"),
               render(OLD_COMMAND, self.HOME) + " # mine", 'python3 "/opt/other/research-routing-guard.py"']
        for command in own:
            with self.subTest(command=command):
                self.assertFalse(acs.runs_superseded_hook({"command": command}, self.HOME))
                host = {"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": command}]}]}}
                merged = acs.merge_settings(host, self.template(), False, self.HOME)
                self.assertIn(command, [c for _, c in guard_commands(merged)])

    def test_without_a_known_home_nothing_is_retired(self):
        host = self.host_with_old()
        merged = acs.merge_settings(copy.deepcopy(host), self.template(), False, None)
        commands = [command for _, command in guard_commands(merged)]
        self.assertIn(render(OLD_COMMAND, self.HOME), commands)
        self.assertFalse(acs.runs_superseded_hook({"command": render(OLD_COMMAND, self.HOME)}, None))
        self.assertFalse(acs.runs_superseded_hook({"command": render(OLD_COMMAND, self.HOME)}, "relative/home"))

    def test_a_template_that_still_runs_the_replaced_command_keeps_it(self):
        """The host's own entry stays, with its own tuning, when the incoming template runs the same command: retiring it would replace it with the template's entry and lose the tuning."""
        old = render(OLD_COMMAND, self.HOME)
        incoming = {"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": old}]}]}}
        host = self.host_with_old()
        host["hooks"]["UserPromptSubmit"][0]["hooks"][0]["timeout"] = 9   # the host's own timeout; the template's entry has none
        merged = acs.merge_settings(host, incoming, False, self.HOME)
        entries = [hook for group in merged["hooks"]["UserPromptSubmit"] for hook in group["hooks"] if hook.get("command") == old]
        self.assertEqual(entries, [{"type": "command", "command": old, "timeout": 9}], "exactly one entry, the host's, with its timeout")

    def test_the_list_names_its_source_and_every_command_names_home_once(self):
        self.assertTrue(acs.SUPERSEDED_HOOK_COMMANDS)
        for command, source in acs.SUPERSEDED_HOOK_COMMANDS:
            self.assertEqual(command.count("${HOME}"), 1)
            self.assertTrue(source)
        self.assertEqual([command for command, _ in acs.SUPERSEDED_HOOK_COMMANDS], [OLD_COMMAND])


@unittest.skipUnless(os.environ.get("NAS_NATIVE_CLAUDE_PROBE") == "1" and shutil.which("claude"),
                     "opt-in native probe: set NAS_NATIVE_CLAUDE_PROBE=1 with the claude client on PATH (it starts the client, runs its session hooks and reads its init record; no model call is waited for)")
class NativeClientProbeTests(unittest.TestCase):
    """The client's own listing of its tools, from a headless start killed at the init record (the probe of the pull request's receipts)."""

    def tools(self, *arguments):
        with tempfile.TemporaryDirectory(prefix="coordinator-deny-") as scratch:
            command = ["claude", "-p", "Reply with the single word ok.", "--output-format", "stream-json", "--verbose", "--max-turns", "1", "--no-session-persistence", *arguments]
            process = subprocess.Popen(command, cwd=scratch, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
            started, init = time.monotonic(), None
            try:
                for line in process.stdout:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if record.get("type") == "system" and record.get("subtype") == "init":
                        init = record
                        break
                    if time.monotonic() - started > 90:
                        break
            finally:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                process.wait(timeout=30)
        self.assertIsNotNone(init, "no init record within 90 s")
        return set(init.get("tools") or [])

    def settings_file(self, directory, data):
        path = Path(directory) / "settings.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def test_the_overlay_removes_websearch_with_the_runner_missing_and_the_hook_alone_does_not(self):
        missing_runner = {"hooks": {"PreToolUse": [{"matcher": "WebSearch", "hooks": [{"type": "command", "command": "python3 /nonexistent/guard.py", "timeout": 5}]}]}}
        with tempfile.TemporaryDirectory() as temp:
            hook_only = self.settings_file(temp, missing_runner)
            self.assertIn("WebSearch", self.tools("--settings", hook_only), "the hook entry alone, runner missing: the call goes through (the finding)")
            overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
            both = self.settings_file(temp, {**overlay, **missing_runner})
            self.assertNotIn("WebSearch", self.tools("--settings", both), "the overlay with the same missing runner")
            self.assertNotIn("WebSearch", self.tools("--disallowedTools", "WebSearch"))
            self.assertIn("WebFetch", self.tools("--settings", both), "only WebSearch is denied")
            self.assertIn("WebSearch", self.tools(), "an unmarked session, launched without the overlay, keeps WebSearch")


if __name__ == "__main__":
    unittest.main()
