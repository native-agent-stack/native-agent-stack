#!/usr/bin/env python3
"""The sandbox read-deny overlay (CPA route B, docs/decisions/2026-10-13-sandbox-readdeny-credentials.md): the shipped overlay denies the credential paths to sandboxed commands (sandbox.filesystem.denyRead) and to
the Read tool (the same paths as Read deny rules), is derived from the shared profile template's own home-anchored rules so that the two cannot drift, carries no /proc rule (which breaks sandboxed Bash), and what
it claims is backed by the measured arms of the receipts. The opt-in native test runs the client itself (NAS_NATIVE_SANDBOX_PROBE=1, bubblewrap and the pinned client installed; no model call, no credential)."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "adoption/templates/claude.sandbox-readdeny.settings.template.json"
SHARED = ROOT / "adoption/templates/claude.settings.template.json"
PROBE = ROOT / "tools/sandbox-probe/readdeny_probe.py"
RECEIPTS = ROOT / "evidence/artifacts/sandbox-readdeny-20261013/receipts"
spec = importlib.util.spec_from_file_location("sandbox_probe_summarize", ROOT / "tools/sandbox-probe/summarize.py")
summarize = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summarize)


def home_rules(template):
    return [rule for rule in template["permissions"]["deny"] if rule.startswith("Read(~/")]


def path_of(rule):
    """The path a home-anchored Read rule names, as a sandbox path: the directory for `/**`, the parent directory for the patterns `*.env` and `*.key`."""
    path = rule[len("Read("):-1]
    for tail in ("/**", "/*.env", "/*.key"):
        if path.endswith(tail):
            return path[:-len(tail)]
    return path


def covered(path, entries):
    return any(path == entry or path.startswith(entry + "/") for entry in entries)


class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
        cls.shared = json.loads(SHARED.read_text(encoding="utf-8"))

    def test_the_overlay_enables_the_sandbox_fails_closed_and_refuses_the_unsandboxed_retry(self):
        sandbox = self.overlay["sandbox"]
        self.assertEqual({key: sandbox[key] for key in ("enabled", "failIfUnavailable", "allowUnsandboxedCommands")}, {"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False})
        self.assertEqual(sorted(sandbox), ["allowUnsandboxedCommands", "enabled", "failIfUnavailable", "filesystem"], "no other sandbox key: the network and the mode are the launcher's")
        self.assertEqual(sorted(sandbox["filesystem"]), ["denyRead"], "no allowRead: a re-open would be a hole")
        self.assertEqual(sorted(self.overlay), ["permissions", "sandbox"])
        self.assertEqual(sorted(self.overlay["permissions"]), ["deny"], "no mode and no allow rule: the launcher chooses them")

    def test_denyread_is_the_shared_templates_home_anchored_read_rules_as_paths(self):
        rules = home_rules(self.shared)
        self.assertEqual(len(rules), 24, "the shared template names 24 home-anchored credential locations")
        deny = self.overlay["sandbox"]["filesystem"]["denyRead"]
        self.assertEqual(deny, [path_of(rule) for rule in rules], "the same locations, in the template's order")
        self.assertEqual(len(set(deny)), len(deny), "no duplicate")
        for entry in deny:
            with self.subTest(entry=entry):
                self.assertTrue(entry.startswith("~/"), "a home-anchored path")
                self.assertNotRegex(entry, r"[*?\[]", "no wildcard: a directory or a file, as measured")

    def test_the_read_tool_rules_are_the_shared_templates_home_rules_and_no_rule_for_proc(self):
        self.assertEqual(self.overlay["permissions"]["deny"], home_rules(self.shared))
        self.assertFalse([rule for rule in self.overlay["permissions"]["deny"] if "proc" in rule], "a /proc rule is added to the sandbox's read denial and breaks sandboxed commands (receipts/arms.json)")
        self.assertIn("Read(//proc/*/environ)", self.shared["permissions"]["deny"], "the shared template keeps it for interactive sessions, which is why a sandboxed worker loads the overlay alone")

    def test_every_fixture_of_the_probe_is_a_credential_location_the_overlay_denies(self):
        tree = ast.parse(PROBE.read_text(encoding="utf-8"))
        fixtures = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and node.targets[0].id == "FIXTURES")
        self.assertGreaterEqual(len(fixtures), 14)
        entries = self.overlay["sandbox"]["filesystem"]["denyRead"]
        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                self.assertTrue(covered("~/" + fixture, entries), "the probe's synthetic file stands inside a denied location")

    def test_the_covered_helper_respects_path_boundaries(self):
        self.assertTrue(covered("~/.ssh/id_ed25519", ["~/.ssh"]))
        self.assertTrue(covered("~/.netrc", ["~/.netrc"]))
        self.assertFalse(covered("~/.sshx/key", ["~/.ssh"]))
        self.assertFalse(covered("~/.ssh", ["~/.ssh/keys"]))


class ReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arms = json.loads((RECEIPTS / "arms.json").read_text(encoding="utf-8"))["arms"]

    def runs(self, arm):
        found = [row for row in self.arms if row["arm"] == arm]
        self.assertEqual(len(found), 3, f"three repeats of {arm}")
        return found

    def test_without_a_denial_the_sandbox_reads_every_credential_and_the_read_tool_follows_the_rules_alone(self):
        for row in self.runs("control-no-sandbox"):
            self.assertEqual((row["shell"], row["python"], row["symlink"], row["copy"]), ({"REAL": 14}, {"REAL": 14}, "REAL", "COPIED"))
            self.assertEqual(row["read_tool_fixture"], "REFUSED", "the template's Read rules refuse the Read tool even without a sandbox")
        for row in self.runs("sandbox-open"):
            self.assertEqual((row["shell"], row["python"], row["symlink"], row["copy"], row["read_tool_fixture"]), ({"REAL": 14}, {"REAL": 14}, "REAL", "COPIED", "READABLE"), "a default sandbox reads credential files")

    def test_a_denyread_list_alone_blocks_sandboxed_commands_and_not_the_read_tool(self):
        for row in self.runs("overlay-denyread-only"):
            self.assertEqual((row["shell"], row["python"], row["symlink"], row["copy"]), ({"DENIED": 14}, {"DENIED": 14}, "DENIED", "NOT-COPIED"))
            self.assertEqual((row["read_tool_fixture"], row["tool_errors"]), ("READABLE", 0), "denyRead does not stop the Read tool: the Read rules are the other half")

    def test_the_template_with_its_proc_rule_breaks_sandboxed_commands_whether_or_not_the_overlay_is_added(self):
        for arm in ("sandbox-template", "overlay-user-scope-loaded"):
            for row in self.runs(arm):
                with self.subTest(arm=arm, repeat=row["repeat"]):
                    self.assertGreater(row["bwrap_proc_errors"], 0, "bwrap cannot create the path of a /proc/*/environ read denial")

    def test_the_deployment_denies_every_route_and_leaves_ordinary_commands_alone(self):
        """`--setting-sources project,local --settings <overlay>`: the user scope (and its /proc rule) is not read when the sandbox is built, and the overlay carries the rest."""
        for row in self.runs("overlay-setting-sources"):
            with self.subTest(repeat=row["repeat"]):
                self.assertEqual((row["shell"], row["python"], row["symlink"], row["copy"]), ({"DENIED": 14}, {"DENIED": 14}, "DENIED", "NOT-COPIED"))
                self.assertEqual((row["read_tool_fixture"], row["read_tool_decoy"]), ("REFUSED", "READABLE"))
                self.assertEqual({name: row["listing_counts"][name] for name in (".ssh", ".aws", ".config/native-agent-stack")}, {".ssh": "0", ".aws": "0", ".config/native-agent-stack": "0"})
                self.assertEqual(sorted(row["decoys_readable"]), [".config/gh/config.yml", "notes.txt"], "ordinary files stay readable")
                self.assertTrue(row["ordinary_commands_ok"])
                self.assertEqual((row["tool_errors"], row["bwrap_proc_errors"]), (0, 0))

    def test_the_documentation_lines_are_in_the_captured_pages(self):
        text = (RECEIPTS / "docs-excerpts.txt").read_text(encoding="utf-8")
        for phrase in ("Most of the machine, including credential files such as `~/.ssh` and `~/.aws/credentials`", "A `denyRead` entry doesn't stop the Read tool",
                       "Claude Code ignores its `sandbox.filesystem` entries, its `Edit` permission rules, and its `Read` deny rules when building the sandbox configuration", "Requires Claude Code v2.1.246 or later",
                       "Comma-separated list of setting sources to load"):
            with self.subTest(phrase=phrase[:50]):
                self.assertIn(phrase, text)


@unittest.skipUnless(os.environ.get("NAS_NATIVE_SANDBOX_PROBE") == "1" and shutil.which("bwrap") and (Path.home() / ".local/share/claude/versions" / os.environ.get("NAS_PROBE_CLIENT_VERSION", "2.1.296")).is_file(),
                     "opt-in native probe: set NAS_NATIVE_SANDBOX_PROBE=1 with bubblewrap and the pinned client installed (it starts the client against a loopback stand-in: no model call, no credential)")
class NativeProbeTests(unittest.TestCase):
    def run_arms(self, *arms):
        with tempfile.TemporaryDirectory() as out:
            command = [sys.executable, str(PROBE), out] + [word for arm in arms for word in ("--arm", arm)]
            done = subprocess.run(command, capture_output=True, text=True, timeout=900)
            self.assertEqual(done.returncode, 0, done.stderr[-400:])
            return {arm: summarize.summarize(json.loads((Path(out) / f"{arm}.json").read_text(encoding="utf-8"))) for arm in arms}

    def test_a_sandboxed_command_cannot_read_a_credential_path_under_the_deployment_and_can_without_it(self):
        found = self.run_arms("control-no-sandbox", "overlay-setting-sources")
        control, deployed = found["control-no-sandbox"], found["overlay-setting-sources"]
        self.assertEqual((control["shell"], control["python"]), ({"REAL": 14}, {"REAL": 14}), "the control reads them")
        self.assertEqual((deployed["shell"], deployed["python"], deployed["symlink"], deployed["copy"]), ({"DENIED": 14}, {"DENIED": 14}, "DENIED", "NOT-COPIED"))
        self.assertEqual((deployed["read_tool_fixture"], deployed["tool_errors"], deployed["ordinary_commands_ok"]), ("REFUSED", 0, True))


if __name__ == "__main__":
    unittest.main()
