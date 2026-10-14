"""Native runtime profiles: live-port binding and generated tool fences.

The source of the endpoint is the repository's new-WSL client-config record;
the CC's 2026-10-12 measurement corroborates that record, without a network test.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
import importlib.util
import argparse
from unittest import mock
import io
import shutil
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/adoption"))
import runtime_profiles as profiles
import runtime_acceptance as acceptance


WORKER = ROOT / "tools/claude-review-worker/worker.py"


def pi_events(handle, *, error=None, tokens=0):
    """Pi --mode json events for one assistant turn: refused with `error` ("<status> <body>"), or completed."""
    message = {"role": "assistant", "content": [] if error else [{"type": "text", "text": "fixture"}],
               "usage": {"input": tokens, "output": 0, "totalTokens": tokens, "cost": {"total": 0}},
               "stopReason": "error" if error else "stop"}
    if error:
        message["errorMessage"] = error
    for kind in ("message_start", "message_end"):
        handle.write(json.dumps({"type": kind, "message": message}) + "\n")


CREDIT_400 = '400 {"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API."}}'


class FillFirstSlotTests(unittest.TestCase):
    """ns-run's Anthropic slot choice (the command center's incident of 2026-10-14, 01:01:52Z): a researcher run on
    anthropic-api-4 was refused for exhausted credit because the profile chose by a no-token check, from a stale 4/3/2
    list, and never moved on. The order is the review worker's DEFAULT_KEYS, the no-token check only screens out an
    invalid or forbidden key, and a first call refused as credit-exhausted (the worker's classifier) moves the run to the
    next slot."""

    def worker(self):
        spec = importlib.util.spec_from_file_location("fill_first_test_worker", WORKER)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod  # its dataclasses resolve their module through sys.modules
        spec.loader.exec_module(mod)
        return mod

    def launch(self, slot_outcomes, health_rows=None, ends=None):
        """A pi-claude print launch whose runtime writes, per slot, a credit refusal, another refusal or a completed
        turn, then ends with status `ends[slot]` (0 when absent; "watchdog" raises the outer subprocess timeout).
        Returns (exit, receipt, runtime calls)."""
        real_module = profiles.module
        rows = health_rows or {}

        class Health:
            @staticmethod
            def health(selected, run=None):
                return [rows.get(slot, {"id": slot, "state": "stored", "validity": "valid"}) for slot in selected]

        calls = []
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            root, workspace = state / "pi-claude", state / "worktree"
            root.mkdir(); workspace.mkdir()
            (root / "profile.json").write_text(json.dumps({"status": "trial", "pi_bin": "/fixture/pi",
                                                          "model": "fixture", "effort": "high", "roles": {}}))
            args = argparse.Namespace(profile="pi-claude", state_root=state, repository=state,
                                      role=None, print=True, prompt="fixture", timeout_seconds=1)

            def runtime(command, **kwargs):
                if command[0] == "timeout":
                    slot = next(s for s in self.worker().DEFAULT_KEYS if s in command)
                    calls.append(slot)
                    outcome = slot_outcomes.get(slot, "ok")
                    pi_events(kwargs["stdout"], error=None if outcome == "ok" else outcome, tokens=12 if outcome == "ok" else 0)
                    end = (ends or {}).get(slot, 0)
                    if end == "watchdog":
                        raise subprocess.TimeoutExpired(command, kwargs["timeout"])
                    return subprocess.CompletedProcess(command, end)
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.object(profiles, "module", side_effect=lambda name, path: Health if "key_health" in name
                                   else real_module(name, path)), \
                    mock.patch.object(profiles, "fresh_worktree", return_value=workspace), \
                    mock.patch.object(profiles, "verify_runtime_binary", return_value="fixture"), \
                    mock.patch.object(profiles.subprocess, "run", side_effect=runtime), \
                    mock.patch.object(profiles.subprocess, "check_output", return_value="a" * 40), \
                    mock.patch.object(profiles, "utc", return_value="2026-10-14T00:00:00Z"), \
                    mock.patch.object(profiles, "cleanup_worktree", return_value={"status": "removed"}), \
                    redirect_stdout(io.StringIO()) as out:
                code = profiles.launch(args)
            receipt = json.loads(Path(json.loads(out.getvalue().strip().splitlines()[-1])["receipt"]).read_text())
        return code, receipt, calls

    def test_an_exhausted_key_that_reports_valid_is_not_chosen_as_final(self):
        order = self.worker().DEFAULT_KEYS
        code, receipt, calls = self.launch({order[0]: CREDIT_400})
        self.assertEqual(calls, [order[0], order[1]])
        self.assertEqual(receipt["credential_loader_id"], order[1])
        self.assertEqual([row["credential_loader_id"] for row in receipt["credit_refused_slots"]], [order[0]])
        self.assertEqual(receipt["inference"]["usage"]["total_tokens"], 12)

    def test_every_exhausted_slot_is_passed_over_in_order(self):
        order = self.worker().DEFAULT_KEYS
        code, receipt, calls = self.launch({order[0]: CREDIT_400, order[1]: CREDIT_400.replace("400 ", "402 ", 1)})
        self.assertEqual(calls, [order[0], order[1], order[2]])
        self.assertEqual(receipt["credential_loader_id"], order[2])

    def test_the_last_exhausted_slot_is_recorded_when_no_slot_follows(self):
        # With no successor the last refused run's receipt stands, and it still names its own slot as refused.
        order = list(self.worker().DEFAULT_KEYS)
        code, receipt, calls = self.launch({slot: CREDIT_400 for slot in order})
        self.assertEqual(calls, order)
        self.assertEqual([row["credential_loader_id"] for row in receipt["credit_refused_slots"]], order)
        self.assertEqual(receipt["credential_loader_id"], order[-1])
        only_first = {slot: {"id": slot, "state": "missing"} for slot in order[1:]}
        code, receipt, calls = self.launch({order[0]: CREDIT_400}, only_first)
        self.assertEqual(calls, [order[0]])
        self.assertEqual([row["credential_loader_id"] for row in receipt["credit_refused_slots"]], [order[0]])

    def test_a_timed_out_or_signalled_attempt_never_moves_to_another_slot(self):
        # A credit refusal already flushed to the log authorizes nothing once the attempt itself was cut short: the
        # outer watchdog, timeout's 124 and 137, the credential runner's 128+N, a signal on the direct child.
        order = self.worker().DEFAULT_KEYS
        for end, status in (("watchdog", 124), (124, 124), (137, 137), (143, 143), (-15, -15)):
            with self.subTest(end=end):
                code, receipt, calls = self.launch({order[0]: CREDIT_400}, ends={order[0]: end})
                self.assertEqual(calls, [order[0]])
                self.assertEqual((code, receipt["runtime_exit_code"]), (status, status))
                self.assertEqual(receipt["credential_loader_id"], order[0])
                self.assertEqual(receipt["credit_refused_slots"], [])
        # A native refusal that ended on its own still moves on: Pi exits 0, OpenCode 1.
        for end in (0, 1):
            with self.subTest(end=end):
                code, receipt, calls = self.launch({order[0]: CREDIT_400}, ends={order[0]: end})
                self.assertEqual(calls, [order[0], order[1]])

    def test_any_other_refusal_ends_the_run_on_its_slot(self):
        order = self.worker().DEFAULT_KEYS
        for refusal in ('401 {"type":"error","error":{"type":"authentication_error","message":"invalid x-api-key"}}',
                        '429 {"type":"error","error":{"type":"rate_limit_error","message":"slow down"}}',
                        '400 {"type":"error","error":{"type":"invalid_request_error","message":"prompt is too long"}}'):
            with self.subTest(refusal=refusal[:3]):
                code, receipt, calls = self.launch({order[0]: refusal})
                self.assertEqual(calls, [order[0]])
                self.assertEqual(receipt["credit_refused_slots"], [])

    def test_the_no_token_check_screens_out_only_invalid_or_forbidden_keys(self):
        order = self.worker().DEFAULT_KEYS
        rows = {order[0]: {"id": order[0], "state": "stored", "validity": "invalid"},
                order[1]: {"id": order[1], "state": "missing"},
                order[2]: {"id": order[2], "state": "stored", "validity": "forbidden"},
                order[3]: {"id": order[3], "state": "stored", "validity": "rate_limited"}}
        code, receipt, calls = self.launch({}, rows)
        self.assertEqual(calls, [order[3]])

    def test_the_order_is_the_review_worker_default_keys(self):
        # One fill-first order for every Anthropic Console consumer: ns-run follows the review worker's DEFAULT_KEYS.
        self.assertEqual(profiles.fill_first_order(), tuple(self.worker().DEFAULT_KEYS))

    def test_first_call_refusal_reads_pi_and_opencode_events(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "events.jsonl"
            with log.open("w") as handle:
                pi_events(handle, error=CREDIT_400)
            self.assertTrue(profiles.credit_refused(log, "pi"))
            with log.open("w") as handle:
                pi_events(handle, tokens=5)
            self.assertFalse(profiles.credit_refused(log, "pi"))
            for error, expected in (({"name": "APIError", "data": {"statusCode": 402, "message": "billing"}}, True),
                                    ({"message": CREDIT_400[4:]}, True),
                                    ({"name": "APIError", "data": {"statusCode": 401, "message": "invalid x-api-key"}}, False)):
                with self.subTest(error=str(error)[:40]):
                    log.write_text(json.dumps({"type": "error", "error": error}) + "\n")
                    self.assertEqual(profiles.credit_refused(log, "opencode"), expected)
            log.write_text(json.dumps({"type": "step_finish", "part": {"tokens": {"total": 3}}}) + "\n"
                           + json.dumps({"type": "error", "error": {"data": {"statusCode": 402}}}) + "\n")
            self.assertFalse(profiles.credit_refused(log, "opencode"))


class GatewayPortBindingTests(unittest.TestCase):
    def test_omniroute_template_matches_new_wsl_gateway_record(self):
        source = ROOT / "adoption/new-wsl/client-config-map.json"
        records = json.loads(source.read_text())["entries"]
        records = [row for row in records if row.get("owner") == "OmniRoute"
                   and "gateway listens on 21128" in row.get("source", "")]
        self.assertEqual(len(records), 1, "the recorded live gateway must have one source")
        rendered = tomllib.loads((ROOT / "adoption/templates/codex.omniroute.config.toml").read_text())
        self.assertEqual(rendered["model_providers"]["omniroute"]["base_url"],
                         "http://127.0.0.1:21128/v1")


class RuntimeInvokeTrackerTests(unittest.TestCase):
    def test_pi_completed_skill_and_mcp_calls_reach_existing_tracker(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "pi.jsonl"
            records = [
                {"type": "session", "id": "fixture-pi-session"},
                {"type": "tool_execution_start", "toolCallId": "call-1", "toolName": "read",
                 "args": {"path": "/fixture/.agents/skills/codebase-design/SKILL.md"}},
                {"type": "tool_execution_end", "toolCallId": "call-1", "toolName": "read",
                 "isError": False},
                {"type": "tool_execution_start", "toolCallId": "call-2",
                 "toolName": "mcp__headroom__get_stats", "args": {}},
                {"type": "tool_execution_end", "toolCallId": "call-2",
                 "toolName": "mcp__headroom__get_stats", "isError": False},
            ]
            log.write_text("\n".join(json.dumps(row) for row in records) + "\n")
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "tools/skill-usage/skill_usage.py"),
                 "--runtime-log", "pi", str(log), "--json"],
                cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            measured = json.loads(result.stdout)["runtimes"]["pi"]
            self.assertEqual(measured["sessions_measured"], 1)
            self.assertEqual(measured["successful_skill_uses"], {"codebase-design": 1})
            self.assertEqual(measured["successful_mcp_calls"], {"headroom": 1})
            self.assertNotIn("/fixture/", result.stdout)


class NativeProfileGenerationTests(unittest.TestCase):
    def setUp(self):
        # Renderer/command contracts use controlled fixture binaries. Actual
        # absent/wrong/native version admission is covered without this stub
        # by test_runtime_profile_readiness and the installed-CLI module.
        self.version_patch = mock.patch.object(profiles, "verify_runtime_binary", return_value="fixture-version")
        self.version_patch.start()
        self.addCleanup(self.version_patch.stop)
    def test_escaping_links_are_refused_in_worktree_and_selected_vendor_roots(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory)
            workspace, vendor, primary = [root / name for name in ("worktree", "vendor", "primary")]
            for path in (workspace, vendor, primary):
                path.mkdir()
            outside = primary / "private.txt"; outside.write_text("synthetic outside")
            owned = workspace / "owned.txt"; owned.write_text("synthetic owned")
            (workspace / "safe.txt").symlink_to(owned)
            profiles.check_read_links([workspace, vendor])
            for base, target in ((workspace, outside), (workspace, primary), (vendor, outside)):
                with self.subTest(base=base.name, directory=target.is_dir()):
                    alias = base / "escape"
                    alias.symlink_to(target, target_is_directory=target.is_dir())
                    with self.assertRaisesRegex(profiles.ProfileError, "escaping or unresolved read link"):
                        profiles.check_read_links([workspace, vendor])
                    alias.unlink()
            cyclic=workspace/'cycle';cyclic.symlink_to(cyclic)
            with self.assertRaises(profiles.ProfileError):profiles.check_read_links([workspace,vendor])
            cyclic.unlink()
            (workspace / "broken").symlink_to(primary / "missing")
            with self.assertRaises(profiles.ProfileError):
                profiles.check_read_links([workspace, vendor])

    def test_opencode_launch_binds_vendor_session_directory_on_both_routes(self):
        for route in ("gpt", "claude"):
            for headless in (True, False):
                with self.subTest(route=route, headless=headless), tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
                    state = Path(directory)
                    profile = "opencode-" + route
                    root = state / profile / "roles/reviewer"
                    root.mkdir(parents=True)
                    workspace = state / "worktree"; workspace.mkdir()
                    (root / "profile.json").write_text(json.dumps({"status": "trial", "model": "fixture",
                        "effort": "high", "opencode_bin": "/fixture/opencode",
                        "roles": {"evidence-reviewer": {"tools": ["read"]}}}))
                    config = root / "config/opencode/opencode.json"
                    config.parent.mkdir(parents=True); config.write_text('{"agent":{}}')
                    observed = []
                    def runtime(command, **kwargs):
                        if "/fixture/opencode" in command or command[0] in ("script", sys.executable, "timeout"):
                            observed.append((command, kwargs))
                        if command[0] == "/fixture/opencode" and "session" in command:
                            kwargs["stdout"].write("[]")
                        return subprocess.CompletedProcess(command, 0)
                    args = argparse.Namespace(profile=profile, state_root=state, repository=state,
                        role="evidence-reviewer", print=headless, prompt="fixture", timeout_seconds=1)
                    with mock.patch.dict(os.environ, {"PWD": str(state / "primary"),
                                                       "OPENCODE_DISABLE_PROJECT_CONFIG": "1"}), \
                            mock.patch.object(profiles, "opencode_sandbox_command", side_effect=lambda command, *args: command), \
                            mock.patch.object(profiles, "fresh_worktree", return_value=workspace), \
                            mock.patch.object(profiles, "choose_slot", return_value="anthropic-api-4"), \
                            mock.patch.object(profiles.subprocess, "run", side_effect=runtime), \
                            mock.patch.object(profiles.subprocess, "check_output", return_value="a" * 40), \
                            mock.patch.object(profiles, "utc", return_value="2026-10-12T00:00:00Z"), \
                            mock.patch.object(profiles, "cleanup_worktree", return_value={"status": "removed"}), \
                            redirect_stdout(io.StringIO()):
                        self.assertEqual(profiles.launch(args), 0)
                    command, kwargs = observed[0]
                    self.assertEqual(kwargs["cwd"], workspace)
                    if route == "claude":
                        self.assertIn("PWD=" + str(workspace), command)
                        self.assertIn("OPENCODE_DISABLE_PROJECT_CONFIG=1", command)
                    else:
                        self.assertEqual(kwargs["env"]["PWD"], str(workspace))
                        self.assertEqual(kwargs["env"]["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")
                    if headless:
                        start = command.index("/fixture/opencode")
                        self.assertEqual(command[start + 1:start + 4], ["run", "--dir", str(workspace)])

    def test_selected_vendor_skills_read_with_pinned_native_permission_evaluator(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("native Node permission evaluator unavailable")
        # The exact vendor functions are a test fixture, never deployed by the
        # profile. Source paths/pin are in the fixture header. Node24 matches
        # the installed client; do not replace native last-match semantics.
        javascript = r'''
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { stripTypeScriptTypes } = require('node:module');
let input = '';
process.stdin.on('data', value => input += value);
process.stdin.on('end', () => {
  const data = JSON.parse(input);
  const ts = fs.readFileSync(data.fixture, 'utf8').replaceAll('export ', '');
  const native = new Function('os', stripTypeScriptTypes(ts, {mode:'strip'})
    + '; const Wildcard={match}; return {evaluate,fromConfig,merge,sanitize,disabled};')(os);
  const packageRoot = path.join(data.root, 'cache/opencode/packages', native.sanitize(data.plugin), 'node_modules/superpowers');
  const outputs = {};
  for (const [name, agent] of Object.entries(data.config.agent)) {
    if (!agent.permission) continue;
    const rules = native.merge(native.fromConfig({'*':'allow',external_directory:{'*':'ask',[path.join(packageRoot,'skills/*')]:'allow'}}), native.fromConfig(agent.permission));
    outputs[name] = {
      selected: native.evaluate('external_directory',path.join(packageRoot,'skills/verification-before-completion/*'),rules).action,
      unselected: native.evaluate('external_directory',path.join(packageRoot,'skills/test-driven-development/*'),rules).action,
      unrelated: native.evaluate('external_directory',path.join(data.home,'unrelated/*'),rules).action,
      canonical: native.evaluate('external_directory',path.join(data.home,'.agents/skills/find-skills/*'),rules).action,
      nativeSkill: native.evaluate('skill','verification-before-completion',rules).action,
      unrelatedSkill: native.evaluate('skill','unrelated-unknown-skill',rules).action,
      skillHidden: native.disabled(['skill'],rules).has('skill'),
      // skill/index.ts:310-314 uses precisely this native evaluate filter.
      listed: data.inventory.filter(skill=>native.evaluate('skill',skill,rules).action!=='deny').sort(),
    };
  }
  console.log(JSON.stringify(outputs));
});
'''
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            servers = {"context-mode": {"type": "stdio", "command": "/fixture/mcp"}}
            with mock.patch.object(profiles, "canonical_servers", return_value=servers), \
                    mock.patch.object(profiles.shutil, "which", return_value="/fixture/rtk"), \
                    mock.patch.object(profiles.subprocess, "check_output", side_effect=[
                        "rtk 0.51.0\n", "e001f773f80b22b7dc4c7a79521b30e35aaef026\n"]), \
                    mock.patch.object(profiles.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
                profiles.render("opencode-gpt", state=state, home=state, eco_root=state, templates=[],
                                pi_bin=state / "pi", opencode_bin=state / "opencode", rtk_source=state,
                                role_scope="reviewer")
            role_root = state / "opencode-gpt/roles/reviewer"
            config = json.loads((role_root / "config/opencode/opencode.json").read_text())
            payload = {"config": config, "root": str(role_root), "home": str(state),
                       "plugin": "superpowers@git+https://github.com/obra/superpowers.git#" + profiles.SUPERPOWERS,
                       "fixture": str(ROOT / "tests/fixtures/opencode-permission-53d1eabb.ts")}
            managed = {s["name"] for s in json.loads((ROOT / "adoption/skills/manifest.json").read_text())["skills"]
                       if s.get("status") != "held" and not s.get("native_plugin")
                       and s.get("agents") != ["claude-code"]}
            payload["inventory"] = sorted(managed | set(profiles.SUPERPOWERS_SKILLS)
                                           | {"context-mode", "unrelated-unknown-skill"})
            result = subprocess.run([node, "-e", javascript], input=json.dumps(payload), text=True,
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs = json.loads(result.stdout)
            self.assertEqual(set(outputs), set(profiles.ROLES))
            for role, outcome in outputs.items():
                with self.subTest(role=role):
                    selected_role = role in {"evidence-reviewer", "security-reviewer"}
                    self.assertFalse(outcome.pop("skillHidden"))
                    expected = managed | {"using-superpowers"}
                    for role_name, skills in profiles.ROLE_SCOPES.values():
                        if role_name == role:
                            expected |= set(skills)
                    if role == "isolated-builder":
                        expected.add("context-mode")
                    self.assertEqual(outcome.pop("listed"), sorted(expected))
                    self.assertEqual(outcome, {"selected": "allow" if selected_role else "deny",
                        "unselected": "allow" if role == "isolated-builder" else "deny", "unrelated": "deny",
                        "canonical": "deny", "nativeSkill": "allow" if selected_role else "deny",
                        "unrelatedSkill": "deny"})

    def test_run_permissions_deny_primary_checkout_reads_with_pinned_evaluator(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("native Node permission evaluator unavailable")
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            base = Path(directory)
            root, worktree = base / "profile", base / "worktree"
            root.mkdir(); worktree.mkdir()
            vendor = root / "vendor/selected"
            config = {"agent": {"evidence-reviewer": {"permission": {
                "*": "deny", "read": {"*": "allow", "mcp:*": "deny"},
                "external_directory": {"*": "deny", str(vendor) + "/*": "allow"},
                "skill": {"*": "deny", "verification-before-completion": "allow"},
            }}}}
            path = root / "config/opencode/opencode.json"
            path.parent.mkdir(parents=True); path.write_text(json.dumps(config))
            overlay = profiles.worktree_permissions(root, worktree)
            javascript = r'''
const fs=require('node:fs'), os=require('node:os'), path=require('node:path');
const {stripTypeScriptTypes}=require('node:module');
let input=''; process.stdin.on('data',x=>input+=x); process.stdin.on('end',()=>{
 const data=JSON.parse(input);
 const ts=fs.readFileSync(data.fixture,'utf8').replaceAll('export ','');
 const native=new Function('os',stripTypeScriptTypes(ts,{mode:'strip'})+';const Wildcard={match};return {fromConfig,merge,evaluate};')(os);
 const rules=native.merge(native.fromConfig(data.overlay.permission),native.fromConfig(data.overlay.agent['evidence-reviewer'].permission));
 const out={};
 for (const [name,target] of Object.entries(data.targets)) {
  out[name]={read:native.evaluate('read',path.relative(data.worktree,target),rules).action,
    external:native.evaluate('external_directory',path.dirname(target)+'/*',rules).action};
 }
 console.log(JSON.stringify(out));
});'''
            payload = {"overlay": overlay, "worktree": str(worktree),
                "fixture": str(ROOT / "tests/fixtures/opencode-permission-53d1eabb.ts"),
                "targets": {"owned": str(worktree / "scripts/check.py"),
                    "primary": str(base / "primary/scripts/check.py"),
                    "vendor": str(vendor / "SKILL.md"),
                    "other_vendor": str(root / "vendor/unselected/SKILL.md"),
                    "outside": str(base / "unrelated/SKILL.md")}}
            result = subprocess.run([node, "-e", javascript], input=json.dumps(payload), text=True,
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {
                "owned": {"read": "allow", "external": "allow"},
                "primary": {"read": "deny", "external": "deny"},
                "vendor": {"read": "allow", "external": "allow"},
                "other_vendor": {"read": "deny", "external": "deny"},
                "outside": {"read": "deny", "external": "deny"}})

    def test_clean_worktree_removed_and_dirty_or_active_worktree_retained(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            repository = Path(directory) / "repo"
            repository.mkdir()
            subprocess.run(["git", "init", "-q", str(repository)], check=True)
            subprocess.run(["git", "-C", str(repository), "-c", "user.name=Fixture",
                            "-c", "user.email=fixture@users.noreply.github.com", "commit", "-q",
                            "--allow-empty", "-m", "fixture"], check=True)
            for state in ("clean", "dirty", "active"):
                worktree = Path(directory) / state
                subprocess.run(["git", "-C", str(repository), "worktree", "add", "--detach",
                                str(worktree)], check=True, capture_output=True)
                if state == "dirty":
                    (worktree / "keep.txt").write_text("fixture")
                with mock.patch.object(profiles, "active_worktree", return_value=state == "active"):
                    result = profiles.cleanup_worktree(repository, worktree)
                self.assertEqual(result["status"], "removed" if state == "clean" else "retained_" + state)
                self.assertEqual(worktree.exists(), state != "clean")
                if state == "dirty":
                    self.assertEqual(result["dirty_entries"], 1)
                    self.assertNotIn("keep.txt", json.dumps(result))

    def test_print_launch_cleans_only_after_usage_and_handoff_receipts(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            root, workspace = state / "pi-gpt", state / "worktree"
            root.mkdir(); workspace.mkdir()
            (root / "profile.json").write_text(json.dumps({"status": "trial", "pi_bin": "/fixture/pi",
                "model": "fixture", "effort": "high", "roles": {}}))
            args = argparse.Namespace(profile="pi-gpt", state_root=state, repository=state,
                role=None, print=True, prompt="fixture", timeout_seconds=1)
            def runtime(command, **kwargs):
                self.assertEqual(kwargs["cwd"], workspace)
                return subprocess.CompletedProcess(command, 0)
            def cleanup(repository, worktree):
                self.assertEqual(worktree, workspace)
                runs = list((root / "runs").iterdir())
                self.assertEqual(len(runs), 1)
                for name in ("invocations.json", "receipt.json", "CC-RECORD.md"):
                    self.assertTrue((runs[0] / name).is_file(), name)
                return {"status": "removed", "exit_code": 0}
            with mock.patch.object(profiles, "fresh_worktree", return_value=workspace), \
                    mock.patch.object(profiles.subprocess, "run", side_effect=runtime), \
                    mock.patch.object(profiles.subprocess, "check_output", return_value="a" * 40), \
                    mock.patch.object(profiles, "utc", return_value="2026-10-12T00:00:00Z"), \
                    mock.patch.object(profiles, "cleanup_worktree", side_effect=cleanup) as removed, \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(profiles.launch(args), 0)
                removed.assert_called_once()
            self.assertEqual(json.loads(next((root / "runs").glob("*/worktree-cleanup.json")).read_text())["status"], "removed")

    def test_valid_native_json_strings_with_unicode_line_separators_keep_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "events.jsonl"
            event = {"type": "message_end", "message": {"role": "assistant",
                     "content": [{"type": "text", "text": "first\u2028second\u2029third"}],
                     "usage": {"input": 5, "output": 2, "totalTokens": 7, "cost": {"total": 0.01}}}}
            log.write_text(json.dumps(event, ensure_ascii=False) + "\n")
            measured = profiles.inference_facts(log, "pi")
            self.assertEqual(measured["completed_native_steps"], 1)
            self.assertEqual(measured["usage"]["total_tokens"], 7)
            self.assertEqual(measured["native_cost_usd"], 0.01)

    def test_pi_mcp_exit_zero_does_not_accept_absent_or_disabled_mandatory_server(self):
        for servers in [[], [{"name": "context-mode", "state": "disabled", "tools": []}]]:
            with self.subTest(servers=servers), tempfile.TemporaryDirectory() as directory:
                state = Path(directory)
                root = state / "pi-gpt"
                root.mkdir()
                (root / "profile.json").write_text(json.dumps({"pi_bin": "/fixture/pi",
                    "mcp_server_names": ["context-mode"]}))
                args = argparse.Namespace(state_root=state, workspace=state, out=state / "receipts",
                                          role_scope=None, tokenizer_python=Path(sys.executable))

                def native(command, **kwargs):
                    if "mcp" in command:
                        return 0, json.dumps({"servers": servers})
                    return 0, "{}"

                with mock.patch.object(acceptance, "native", side_effect=native), \
                        mock.patch.object(acceptance, "discovered", return_value=[]), \
                        mock.patch.object(acceptance, "skill_integrity", return_value={"managed_pass": True}), \
                        redirect_stdout(io.StringIO()):
                    self.assertFalse(acceptance.check(args, "pi-gpt"))
                receipt = json.loads((args.out / "pi-gpt.discovery.json").read_text())
                self.assertFalse(receipt["mcp"]["all_connected"])

    def test_interactive_claude_opencode_collector_uses_profile_xdg_after_loader(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            role = state / "opencode-claude/roles/builder"
            role.mkdir(parents=True)
            (role / "profile.json").write_text(json.dumps({
                "status": "trial", "model": "fixture", "effort": "xhigh",
                "opencode_bin": "/fixture/opencode", "roles": {"isolated-builder": {"tools": []}},
            }))
            config = role / "config/opencode/opencode.json"
            config.parent.mkdir(parents=True)
            config.write_text('{"agent":{}}')
            expected = {"XDG_STATE_HOME": str(role / "state"), "XDG_DATA_HOME": str(role / "data"),
                        "OPENCODE_CONFIG_DIR": str(role / "config")}
            observed = []

            def run(command, **kwargs):
                if command[0] == "/fixture/opencode":
                    observed.append(kwargs["env"])
                    kwargs["stdout"].write("[]")
                return subprocess.CompletedProcess(command, 0)

            args = argparse.Namespace(profile="opencode-claude", state_root=state, repository=state,
                                      role="isolated-builder", print=False, prompt=None)
            with mock.patch.object(profiles, "fresh_worktree", return_value=state), \
                    mock.patch.object(profiles, "opencode_sandbox_command", side_effect=lambda command, *args: command), \
                    mock.patch.object(profiles, "cleanup_worktree", return_value={"status": "removed"}), \
                    mock.patch.object(profiles, "choose_slot", return_value="anthropic-api-4"), \
                    mock.patch.object(profiles, "profile_environment", return_value=expected), \
                    mock.patch.object(profiles.subprocess, "run", side_effect=run), redirect_stdout(io.StringIO()):
                self.assertEqual(profiles.launch(args), 0)
            self.assertEqual(len(observed), 1)
            for name, value in expected.items():
                self.assertEqual(observed[0].get(name), value, name)
            self.assertEqual(observed[0]["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")
            self.assertEqual(observed[0]["PWD"], str(state))
            self.assertEqual(json.loads(observed[0]["OPENCODE_CONFIG_CONTENT"])["permission"]["read"]["../*"], "deny")

    def test_read_only_vendor_skill_loader_is_explicitly_narrowed_per_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            servers = {"context-mode": {"type": "stdio", "command": "/fixture/mcp"}}
            with mock.patch.object(profiles, "canonical_servers", return_value=servers), \
                    mock.patch.object(profiles.shutil, "which", return_value="/fixture/rtk"), \
                    mock.patch.object(profiles.subprocess, "check_output", side_effect=[
                        "rtk 0.51.0\n", "e001f773f80b22b7dc4c7a79521b30e35aaef026\n"]), \
                    mock.patch.object(profiles.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
                profiles.render("opencode-gpt", state=state, home=state, eco_root=state, templates=[],
                                pi_bin=state / "pi", opencode_bin=state / "opencode", rtk_source=state,
                                role_scope="auditor")
            config = json.loads((state / "opencode-gpt/roles/auditor/config/opencode/opencode.json").read_text())
            # CC09:55Z B1 supersedes the no-Skill expectation: this native
            # helper is a read-only loader and drives skill discoverability.
            for name in profiles.ROLES:
                permissions = config["agent"][name]["permission"]
                self.assertEqual(permissions["skill"]["*"], "deny", name)
                self.assertEqual(permissions["skill"]["find-skills"], "allow", name)
                self.assertNotIn("unrelated-unknown-skill", permissions["skill"])
            self.assertEqual(config["agent"]["security-reviewer"]["permission"]["skill"]["systematic-debugging"], "allow")
            self.assertNotIn("systematic-debugging", config["agent"]["source-scout"]["permission"]["skill"])

    def test_token_layer_is_private_on_both_runtimes_and_claude_prompt_fallback_disabled(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            for profile in profiles.PROFILES:
                env = profiles.profile_environment(profile, state, "reviewer")
                root = state / profile / "roles/reviewer"
                for variable in ("CLAUDE_CONFIG_DIR", "CONTEXT_MODE_DIR", "CONTEXT_MODE_DATA_DIR"):
                    self.assertTrue(Path(env[variable]).is_relative_to(root), variable)
                if profile.startswith("opencode"):
                    self.assertEqual(env["OPENCODE_DISABLE_CLAUDE_CODE_PROMPT"], "1")

    def test_both_canonical_role_preloads_use_native_files_without_copying_skill_text(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            state = Path(directory)
            for profile in ("pi-gpt", "opencode-gpt"):
                servers = {"context-mode": {"type": "stdio", "command": "/fixture/node"}}
                with mock.patch.object(profiles, "canonical_servers", return_value=servers), \
                        mock.patch.object(profiles.shutil, "which", return_value="/fixture/rtk"), \
                        mock.patch.object(profiles.subprocess, "check_output", side_effect=[
                            "rtk 0.51.0\n", "e001f773f80b22b7dc4c7a79521b30e35aaef026\n"]), \
                        mock.patch.object(profiles.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as installs:
                    profiles.render(profile, state=state, home=state, eco_root=state, templates=[],
                                    pi_bin=state / "pi", opencode_bin=state / "opencode", rtk_source=state)
                    npm = [call.args[0] for call in installs.call_args_list if call.args[0][0] == "npm"]
                    self.assertEqual(npm[0][1], "install")
                    self.assertIn("--ignore-scripts", npm[0])
                    self.assertEqual(npm[1][1], "rebuild")
                    self.assertEqual(npm[1][-1], "better-sqlite3")
                root = state / profile
                meta = json.loads((root / "profile.json").read_text())
                security = meta["roles"]["security-reviewer"]["preloads"]
                builder = meta["roles"]["isolated-builder"]["preloads"]
                self.assertEqual(security[0]["path"], str(state / ".agents/skills/security-best-practices/SKILL.md"))
                self.assertEqual(builder[0]["path"], str(profiles.context_mode_package(root) / "skills/context-mode/SKILL.md"))
                if profile.startswith("opencode"):
                    config = json.loads((root / "config/opencode/opencode.json").read_text())
                    for role, preloads in [("security-reviewer", security), ("isolated-builder", builder)]:
                        self.assertIn("{file:" + preloads[0]["path"] + "}", config["agent"][role]["prompt"])
                        self.assertEqual(config["agent"][role]["permission"]["skill"][preloads[0]["name"]], "allow")
                context = (json.loads((root / "agent/mcp.json").read_text())["mcpServers"]["context-mode"]
                           if profile.startswith("pi") else config["mcp"]["context-mode"])
                environment = context.get("env", context.get("environment"))
                self.assertTrue(Path(environment["HOME"]).is_relative_to(root))
                self.assertEqual(environment["CONTEXT_MODE_PLATFORM"], profile.split("-")[0])

    def test_native_mcp_failed_or_absent_status_is_not_connected_despite_exit_zero(self):
        output = "│ ✓ serena connected\n│ ✗ socraticode failed\n"
        states = acceptance.opencode_statuses(output, ["serena", "socraticode", "context-mode"])
        self.assertEqual(states, {"serena": "connected", "socraticode": "failed", "context-mode": "unverified"})

    def test_mcp_conversion_preserves_transport_environment_and_arguments(self):
        servers = {
            "stdio-fixture": {"type": "stdio", "command": "/tool with spaces", "args": ["--one", "two words"],
                              "env": {"PUBLIC_OPTION": "value"}},
            "remote-fixture": {"type": "http", "url": "http://127.0.0.1:19999/mcp"},
        }
        converted = profiles.opencode_mcp(servers)
        self.assertEqual(converted["stdio-fixture"]["command"], ["/tool with spaces", "--one", "two words"])
        self.assertEqual(converted["stdio-fixture"]["environment"], {"PUBLIC_OPTION": "value"})
        self.assertEqual(converted["remote-fixture"]["type"], "remote")
        self.assertFalse(converted["remote-fixture"]["oauth"])

    def test_roles_cannot_gain_shell_write_or_mcp_wildcards(self):
        metadata, _ = profiles.role_source("evidence-reviewer")
        for runtime in ["pi", "opencode"]:
            tools, omitted = profiles.granted_tools(metadata, runtime)
            self.assertNotIn("bash", tools)
            self.assertNotIn("edit", tools)
            self.assertNotIn("write", tools)
            self.assertNotIn("mcp__*", tools)
            self.assertNotIn("*", tools)
            self.assertTrue(any("serena" in tool for tool in tools))
        metadata, _ = profiles.role_source("source-scout")
        tools, _ = profiles.granted_tools(metadata, "pi")
        self.assertEqual(tools, ["bash", "find", "grep", "read"])

    def test_native_tool_identity_preserves_vendor_hyphens_and_role_patterns(self):
        metadata = {"tools": "mcp__ai-memory__memory_query, mcp__serena__find_*"}
        tools, _ = profiles.granted_tools(metadata, "opencode")
        self.assertEqual(tools, ["ai-memory_memory_query", "serena_find_*"])
        tools, _ = profiles.granted_tools(metadata, "pi")
        self.assertEqual(tools, ["mcp__ai_memory__memory_query", "mcp__serena__find_*"])

    def test_profile_destinations_refuse_symlink_and_protected_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "link").symlink_to(root / "target", target_is_directory=True)
            with self.assertRaises(profiles.ProfileError):
                profiles.owned_destination(root / "link/nested")
        with self.assertRaises(profiles.ProfileError):
            profiles.owned_destination(Path.home() / ".codex/never")

    def test_ns_run_accepts_named_launcher_profile(self):
        args = profiles.parser().parse_args(["run", "--state-root", "/fixture",
                                            "--repository", "/fixture", "ns-pi-gpt", "builder", "brief.md"])
        self.assertEqual(args.profile, "pi-gpt")

    def test_xdg_profile_path_reaches_selected_python_without_host_shim_config(self):
        with tempfile.TemporaryDirectory() as directory:
            env = profiles.profile_environment("opencode-gpt", Path(directory))
            expected = str(Path(sys.executable).resolve().parent)
            self.assertEqual(env["PATH"].split(os.pathsep)[0], expected)
            self.assertTrue(env["XDG_STATE_HOME"].startswith(directory))
            self.assertEqual(env["OTEL_EXPORTER_OTLP_ENDPOINT"], "http://127.0.0.1:21318")

    def test_existing_profile_is_preserved_and_token_layer_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            destination = state / "pi-gpt"
            destination.mkdir()
            (destination / "owner-file").write_text("keep")
            with self.assertRaises(profiles.ProfileError):
                profiles.render("pi-gpt", state=state, home=state, eco_root=state, templates=[],
                                pi_bin=state / "pi", opencode_bin=state / "opencode", rtk_source=state)
            self.assertEqual((destination / "owner-file").read_text(), "keep")
            with self.assertRaises(profiles.ProfileError):
                profiles.canonical_servers(state, state, [])

    def test_secret_is_environment_reference_not_stored_value(self):
        provider = profiles.opencode_provider("claude")
        self.assertEqual(provider["anthropic"]["options"]["apiKey"], "{env:ANTHROPIC_API_KEY}")
        self.assertNotIn("apiKey", json.dumps(profiles.pi_models("claude")))

    def test_windows_fragments_are_new_profiles_not_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = argparse.Namespace(home=root, state_root=root / "state", repository=ROOT,
                                      fragment=root / "Fragments/native-stack/runtimes.json")
            profiles.install_launchers(args)
            fragment = json.loads(args.fragment.read_text())
            self.assertEqual(len(fragment["profiles"]), 4)
            self.assertTrue(all("updates" not in item for item in fragment["profiles"]))
            self.assertTrue(all("wsl.exe" in item["commandline"] for item in fragment["profiles"]))
            self.assertFalse((root / "settings.json").exists())


if __name__ == "__main__":
    unittest.main()
