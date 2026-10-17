"""Opt-in lane hardening of tools/sota-convergence/landscape-sweep/codex_job.py and build_args.py (no network, no codex,
no rtk, no ai-memory, no model call): per-job RTK and secret-path-guard hook trust, `--disable apps`, loopback OTEL export,
the rollout-derived usage of a failed attempt and the gateway lane's ai-memory bearer variable.

The decision record is docs/decisions/2026-10-17-codex-job-lane-hooks-mcp-memory.md. A fake `codex` stands in for the CLI
(the harness test module's, extended to record two more environment facts), a stub `rtk` for upstream's installer, and
every hook claim is checked by parsing the recorded -c values the way Codex does (a TOML inline value). Pins: openai/codex
rust-v0.163.0 at 83086188ae0614bd882818ff1aa23f3194962012; rtk 1.0.1; ai-memory 3.1.0. The class names follow the item
numbers of the implementation plan: b (RTK trust), g (guard), c (disable apps), d (OTEL), e (rollout usage), a (ai-memory).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

import tests.test_landscape_sweep_harness as H  # noqa: E402  (helpers only; its test classes run there)

ROOT, HARNESS = H.ROOT, H.HARNESS
codex_job, build_args, convert = H.codex_job, H.build_args, H.convert
GUARD_SOURCE = ROOT / "scripts" / "hooks" / "secret_path_guard.py"
# Codex's own record of `rtk hook codex` (matcher Bash, default timeout 600 s) in a live hooks.json, reproduced by
# recomputing upstream's algorithm: sha256 of {"event_name":"pre_tool_use","hooks":[{"async":false,"command":
# "rtk hook codex","timeout":600,"type":"command"}],"matcher":"Bash"}.
RTK_GOLDEN = "sha256:be6c6fcb2978ea348dd05101efed0afcf00efcbfb5d7e78949108142c875a77d"
RTK_GROUP = {"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook codex"}]}
OTHER_GROUP = {"matcher": "", "hooks": [{"type": "command", "command": "/opt/fixture/other-hook --echo SENTINEL-HOOK-TEXT"}]}
SENTINEL_TEXT = "marker-sentinel-0001"  # stands in for a bearer value; it must reach no file
THREAD = "fixture-thread-0001"  # a real thread id is a UUID; the lookup only needs the id shape
FAILED = [{"type": "thread.started", "thread_id": THREAD}, {"type": "error", "message": "boom"},
          {"type": "turn.failed", "error": {"message": "boom"}}]
USAGE = {"input_tokens": 189046, "cached_input_tokens": 127360, "cache_write_input_tokens": 0, "output_tokens": 3633,
         "reasoning_output_tokens": 805, "total_tokens": 192679}
BASE_ARGV = ["exec", "--ignore-user-config", "--skip-git-repo-check", "-s", "read-only", "-m", "gpt-6-astra",
             "-c", 'model_reasoning_effort="max"', "-c", 'web_search="live"']

# The harness test module's fake codex, plus the two environment facts these tests read.
FAKE = H.FAKE_CODEX.replace(
    '"api_key_present": bool(os.environ.get("OMNIROUTE_API_KEY"))}}',
    '"api_key_present": bool(os.environ.get("OMNIROUTE_API_KEY")), "rtk_telemetry": os.environ.get('
    '"RTK_TELEMETRY_DISABLED"), "ai_memory_token_present": bool(os.environ.get("AI_MEMORY_AUTH_TOKEN"))}}')
assert FAKE != H.FAKE_CODEX, "the harness fake codex changed; update the replaced record line"


def inline(value: str):
    """A -c value as Codex parses it: a TOML value."""
    return tomllib.loads("_x_ = " + value)["_x_"]


def flags(argv: list) -> list:
    """Every -c value, in order."""
    return [argv[index + 1] for index, item in enumerate(argv[:-1]) if item == "-c"]


def flag(argv: list, key: str) -> list:
    return [value for value in flags(argv) if value.startswith(key + "=")]


def hooks_json(home: Path, groups: list) -> Path:
    path = home / "hooks.json"
    path.write_text(json.dumps({"hooks": {"PreToolUse": groups}}), encoding="utf-8")
    return path


def write_rollout(home: Path, thread: str, totals: list, folder=("2026", "10", "16"),
                  stamp="2026-10-16T22-42-51") -> Path:
    """A rollout as codex-rs/rollout writes it: JSON lines, token_count events with info.total_token_usage (a line whose
    info is null carries only rate limits)."""
    path = home / "sessions" / Path(*folder) / f"rollout-{stamp}-{thread}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [{"timestamp": "t0", "type": "session_meta", "payload": {"id": thread}},
             {"timestamp": "t1", "type": "event_msg", "payload": {"type": "agent_message", "message": "hello"}}]
    for number, total in enumerate(totals):
        lines.append({"timestamp": f"t{number + 2}", "type": "event_msg", "payload": {
            "type": "token_count", "info": {"total_token_usage": total, "last_token_usage": total,
                                            "model_context_window": 1000}, "rate_limits": None}})
    lines.append({"timestamp": "t9", "type": "event_msg", "payload": {"type": "token_count", "info": None}})
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return path


class HardeningCase(H.RunnerCase):
    """RunnerCase with the extended fake codex, HOME and CODEX_HOME in the test's own directories."""

    def setUp(self):
        super().setUp()
        (self.bin / "codex").write_text(FAKE.format(python=sys.executable), encoding="utf-8")
        self.home = H.temp_dir(self)
        self.codex_home = self.home / ".codex"
        self.codex_home.mkdir()
        self.env["HOME"] = str(self.home)
        self.env.pop("CODEX_HOME", None)
        for name in ("AI_MEMORY_AUTH_TOKEN", "OMNIROUTE_API_KEY", "RTK_TELEMETRY_DISABLED"):
            self.env.pop(name, None)

    def stage(self, guard=False, **codex):
        """staged.json for the runner; guard copies the repository's secret_path_guard.py beside it, as build_args.py does."""
        staged = {"codex": {"wait_poll_s": 0.05, "slot_poll_s": 0.05, "timeout_s": 30, **codex}}
        if guard:
            copy = self.work / codex_job.GUARD_FILE
            copy.write_bytes(GUARD_SOURCE.read_bytes())
            staged["harness"] = {"files": {codex_job.GUARD_FILE: hashlib.sha256(copy.read_bytes()).hexdigest()}}
        H.write_json(self.work / "staged.json", staged)

    def lane(self, **codex):
        home = self.work / "codex-home"
        home.mkdir(exist_ok=True)
        (home / "config.toml").write_text(
            'model = "cx/gpt-6-astra"\nmodel_provider = "omniroute"\n\n[mcp_servers.ai-memory]\n'
            'url = "http://127.0.0.1:1/mcp"\n' + (f'bearer_token_env_var = "{codex["ai_memory_token_env"]}"\n'
                                                   if codex.get("ai_memory_token_env") else ""), encoding="utf-8")
        (home / "stack-worker.config.toml").write_text(H.STACK_WORKER_FIXTURE, encoding="utf-8")
        self.stage(guard=codex.pop("guard", False), provider="omniroute", codex_home="codex-home",
                   profile="stack-worker", api_key_env="OMNIROUTE_API_KEY", model="cx/gpt-6-astra", **codex)
        self.env["OMNIROUTE_API_KEY"] = "fixture-not-a-key"
        return home

    def argv(self):
        return self.record()["argv"]

    def sentinel_free(self, sentinel: str):
        for base in (self.work, self.bin):
            for path in base.rglob("*"):
                if path.is_file():
                    self.assertNotIn(sentinel.encode(), path.read_bytes(), str(path))


class NativeHookTrustTests(HardeningCase):
    def test_no_staged_hooks_key_leaves_argv_env_and_inputs_identical(self):  # b0, a control that passes on main
        self.stage()
        result = self.job("control", last=H.LAST, events=[H.COMPLETED])
        directory = self.work / "gpt6" / "control"
        self.assertEqual(self.argv(), [*BASE_ARGV, "--output-schema", str(directory / "schema.json"),
                                       "-o", str(directory / "last.json"), "--json", "Reply in JSON."])
        self.assertIsNone(self.record()["rtk_telemetry"])
        self.assertEqual(sorted(result["inputs"]), ["effort", "model", "prompt_sha256", "request_effort", "schema_sha256"])
        self.assertNotIn("rollout_usage", result)
        self.assertFalse((directory / "codex_home").exists())

    def test_rtk_trust_is_one_inline_table_keyed_by_the_hooks_file_and_command(self):  # b1
        real = self.home / "real-codex-home"
        real.mkdir()
        link = self.home / "link-codex-home"
        link.symlink_to(real)
        hooks_json(real, [OTHER_GROUP, RTK_GROUP])
        self.env["CODEX_HOME"] = str(link)
        self.stage(hooks={"rtk": True})
        self.job("rtk", last=H.LAST, events=[H.COMPLETED])
        argv = self.argv()
        tables = flag(argv, "hooks.state")
        self.assertEqual(len(tables), 1, argv)
        self.assertEqual(inline(tables[0].split("=", 1)[1]),
                         {f"{os.path.realpath(real)}/hooks.json:pre_tool_use:1:0": {"trusted_hash": RTK_GOLDEN}})
        self.assertFalse([value for value in flags(argv) if value.startswith("hooks.state.")])
        self.assertIn("--ignore-user-config", argv)
        self.assertNotIn("--dangerously-bypass-hook-trust", argv)
        self.assertEqual(flag(argv, "hooks.PreToolUse"), [])

    def test_rtk_trust_without_codex_home_uses_home_dot_codex(self):  # b1, the default home
        hooks_json(self.codex_home, [RTK_GROUP])
        self.stage(hooks={"rtk": True})
        self.job("rtk-home", last=H.LAST, events=[H.COMPLETED])
        self.assertEqual(inline(flag(self.argv(), "hooks.state")[0].split("=", 1)[1]),
                         {f"{self.codex_home}/hooks.json:pre_tool_use:0:0": {"trusted_hash": RTK_GOLDEN}})

    def test_trust_hash_matches_codex_written_vectors(self):  # b2
        handler = {"type": "command", "command": "rtk hook codex"}
        self.assertEqual(codex_job.hook_trust_hash("PreToolUse", "Bash", handler), RTK_GOLDEN)

        def sha(blob):
            return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()

        self.assertEqual(
            codex_job.hook_trust_hash("PreToolUse", "Bash", {**handler, "timeout": 7}),
            sha('{"event_name":"pre_tool_use","hooks":[{"async":false,"command":"rtk hook codex","timeout":7,'
                '"type":"command"}],"matcher":"Bash"}'))
        # Stop and UserPromptSubmit ignore a matcher, so none enters the identity; SessionEnd defaults to 1 s.
        self.assertEqual(
            codex_job.hook_trust_hash("Stop", "ignored", {"type": "command", "command": "x"}),
            sha('{"event_name":"stop","hooks":[{"async":false,"command":"x","timeout":600,"type":"command"}]}'))
        self.assertEqual(
            codex_job.hook_trust_hash("SessionEnd", "", {"type": "command", "command": "x"}),
            sha('{"event_name":"session_end","hooks":[{"async":false,"command":"x","timeout":1,"type":"command"}],'
                '"matcher":""}'))
        self.assertEqual(
            codex_job.hook_trust_hash("PreToolUse", "Bash", {**handler, "statusMessage": "m", "async": True}),
            sha('{"event_name":"pre_tool_use","hooks":[{"async":true,"command":"rtk hook codex","statusMessage":"m",'
                '"timeout":600,"type":"command"}],"matcher":"Bash"}'))
        # upstream's own published vector for the canonical form (codex-rs/config/src/fingerprint_tests.rs): keys sorted,
        # compact separators.
        canonical = json.dumps({"rows": [{"a": 1, "z": 2}, {"a": 3, "z": 4}], "nested": {"z": "text", "a": True}},
                               sort_keys=True, separators=(",", ":"))
        self.assertEqual(sha(canonical), "sha256:a5e4c8fbdbc75d185b0f2b5291bfb2de10e8c523d6c89248876fd78a97c83176")
        with self.assertRaises(codex_job.UsageError):
            codex_job.hook_trust_hash("Nope", None, handler)
        for extra in ({"additionalContextLimit": 5}, {"commandWindows": "x"}, {"timeout": 1.5}, {"timeout": True}):
            with self.subTest(extra=extra), self.assertRaises(codex_job.UsageError):
                codex_job.hook_trust_hash("PreToolUse", "Bash", {**handler, **extra})

    def test_missing_or_duplicate_rtk_hook_refuses_before_codex_starts(self):  # b3
        self.stage(hooks={"rtk": True})
        for name, groups in (("none", [OTHER_GROUP]), ("two", [RTK_GROUP, RTK_GROUP]),
                             ("absent", None)):
            with self.subTest(name):
                (self.bin / "record.json").unlink(missing_ok=True)
                if groups is None:
                    (self.codex_home / "hooks.json").unlink(missing_ok=True)
                else:
                    hooks_json(self.codex_home, groups)
                self.fake(last=H.LAST, events=[H.COMPLETED])
                started = self.call("start", f"refused-{name}", self.prompt, self.schema)
                self.assertEqual(started.returncode, 0, started.stderr)
                self.call("wait", f"refused-{name}", "20")
                result = json.loads(self.call("result", f"refused-{name}").stdout)
                self.assertEqual((result["exit"], result["failure"]["kind"]), (codex_job.EXIT_REFUSED, "hook_trust"))
                self.assertFalse((self.bin / "record.json").exists())  # codex never ran
                self.assertIn("hook_trust", result["stderr_tail"])
                self.assertNotIn("SENTINEL-HOOK-TEXT", result["stderr_tail"])  # hooks.json is never echoed

    def test_rtk_telemetry_switch_reaches_runner_env_and_model_shell(self):  # b4
        hooks_json(self.codex_home, [RTK_GROUP])
        self.stage(hooks={"rtk": True})
        self.job("telemetry", last=H.LAST, events=[H.COMPLETED])
        self.assertEqual(self.record()["rtk_telemetry"], "1")
        self.assertIn('shell_environment_policy.set.RTK_TELEMETRY_DISABLED="1"', flags(self.argv()))
        self.assertEqual(codex_job.codex_env(None, {"RTK_TELEMETRY_DISABLED": "1"})["RTK_TELEMETRY_DISABLED"], "1")
        with mock.patch.dict(os.environ):  # a host that exports the switch itself still gets the staged value only on request
            os.environ.pop("RTK_TELEMETRY_DISABLED", None)
            self.assertNotIn("RTK_TELEMETRY_DISABLED", codex_job.codex_env())

    def test_hooks_policy_is_bound_in_inputs_and_older_records_stay_reusable(self):  # b5
        hooks_json(self.codex_home, [RTK_GROUP])
        self.stage()
        first = self.job("bound", last=H.LAST, events=[H.COMPLETED])
        self.assertNotIn("hooks", first["inputs"])
        again = self.call("start", "bound", self.prompt, self.schema)
        self.assertEqual(again.stdout.strip(), "already done: bound")  # a record without the key equals one without it
        self.stage(hooks={"rtk": True})
        changed = self.call("start", "bound", self.prompt, self.schema)
        self.assertIn("inputs changed since bound finished", changed.stdout)
        self.call("wait", "bound", "20")
        result = json.loads(self.call("result", "bound").stdout)
        self.assertEqual(result["inputs"]["hooks"], {"rtk": True})
        self.assertEqual(len(result["attempts"]), 1)  # the unhooked run is kept under attempts/
        self.assertEqual(codex_job.job_inputs(b"p", b"s", "m", extras={"hooks": {"rtk": True}})["hooks"], {"rtk": True})
        self.assertNotIn("hooks", codex_job.job_inputs(b"p", b"s", "m"))
        self.assertTrue(codex_job.same_inputs(codex_job.job_inputs(b"p", b"s", "m"), codex_job.job_inputs(b"p", b"s", "m")))
        self.assertFalse(codex_job.same_inputs(codex_job.job_inputs(b"p", b"s", "m"),
                                               codex_job.job_inputs(b"p", b"s", "m", extras={"hooks": {"rtk": True}})))

    def test_hook_settings_refuse_anything_but_named_true_hooks(self):
        self.stage()
        for staged in ({}, [], "rtk", {"rtk": False}, {"other": True}, {"rtk": 1}, {"rtk": True, "x": True}):
            with self.subTest(staged=staged):
                self.stage(hooks=staged)
                with self.assertRaises(codex_job.UsageError):
                    codex_job.settings(self.work)
        self.stage(hooks={"secret_guard": True, "rtk": True})
        self.assertEqual(codex_job.settings(self.work)["hooks"], {"rtk": True, "secret_guard": True})


class GatewayHookTrustTests(HardeningCase):
    def test_gateway_lane_trusts_rtk_with_the_lane_home_key(self):  # b6
        home = self.lane(hooks={"rtk": True})
        hooks_json(home, [RTK_GROUP])
        before = (home / "config.toml").read_bytes()
        self.job("lane-rtk", last=H.LAST, events=[H.COMPLETED])
        argv = self.argv()
        self.assertEqual(argv[:3], ["exec", "-p", "stack-worker"])
        self.assertNotIn("--ignore-user-config", argv)
        self.assertEqual(inline(flag(argv, "hooks.state")[0].split("=", 1)[1]),
                         {f"{os.path.realpath(self.work)}/codex-home/hooks.json:pre_tool_use:0:0":
                          {"trusted_hash": RTK_GOLDEN}})
        self.assertEqual(self.record()["codex_home"], str(home))
        self.assertEqual((home / "config.toml").read_bytes(), before)  # the lane config stays trust-free
        self.assertNotIn(b"[hooks.state", before)

    def test_gateway_lane_without_its_hooks_file_refuses(self):
        self.lane(hooks={"rtk": True})
        self.fake(last=H.LAST, events=[H.COMPLETED])
        self.call("start", "lane-nohooks", self.prompt, self.schema)
        self.call("wait", "lane-nohooks", "20")
        result = json.loads(self.call("result", "lane-nohooks").stdout)
        self.assertEqual((result["exit"], result["failure"]["kind"]), (2, "hook_trust"))
        self.assertFalse((self.bin / "record.json").exists())


class GuardHookTests(HardeningCase):
    def registered(self):
        """(matcher, handler, hooks.state table) of the guard hook as the recorded argv carries them."""
        argv = self.argv()
        groups = inline(flag(argv, "hooks.PreToolUse")[0].split("=", 1)[1])
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]["hooks"]), 1)
        return groups[0]["matcher"], groups[0]["hooks"][0], inline(flag(argv, "hooks.state")[0].split("=", 1)[1])

    def fake_home(self):
        """A fake HOME holding a fake Codex auth file; the guard only reads command text, so the file gives path realism."""
        home = H.temp_dir(self)
        (home / ".codex").mkdir()
        (home / ".codex" / "auth.json").write_text('{"fixture": "not a credential"}\n', encoding="utf-8")
        return home

    def run_command(self, command: str, payload: dict):
        return subprocess.run(["/bin/sh", "-c", command], input=json.dumps(payload), capture_output=True, text=True,
                              cwd=str(self.work / "empty"), check=False, timeout=30)

    def bash(self, command: str) -> dict:
        return {"tool_name": "Bash", "tool_input": {"command": command}}

    def test_guard_hook_is_registered_with_its_own_trust_entry(self):  # g1
        self.stage(guard=True, hooks={"secret_guard": True})
        self.job("guard", last=H.LAST, events=[H.COMPLETED])
        matcher, handler, state = self.registered()
        self.assertEqual(matcher, "Bash")  # alphanumeric, so Codex matches the tool name exactly (hooks/src/engine/matcher.rs)
        self.assertEqual((handler["type"], handler["timeout"]), ("command", 10))
        self.assertIn(str(self.work / codex_job.GUARD_FILE), handler["command"])
        self.assertEqual(state, {f"{codex_job.SESSION_FLAGS_CONFIG}:pre_tool_use:0:0":
                                 {"trusted_hash": codex_job.hook_trust_hash("PreToolUse", matcher, handler)}})
        self.assertEqual(len(flag(self.argv(), "hooks.state")), 1)
        self.assertIn("--ignore-user-config", self.argv())
        self.assertNotIn("apply_patch", " ".join(flags(self.argv())))  # Bash only: apply_patch is the guard PR's
        self.assertIsNone(self.record()["rtk_telemetry"])  # the guard alone sets no rtk variable

    def test_registered_guard_command_blocks_a_codex_auth_read_and_allows_credential_run(self):  # g2
        self.stage(guard=True, hooks={"secret_guard": True})
        self.job("guard-run", last=H.LAST, events=[H.COMPLETED])
        _, handler, _ = self.registered()
        fake = self.fake_home()
        blocked = self.run_command(handler["command"], self.bash(f"cat {fake}/.codex/auth.json"))
        self.assertEqual(blocked.returncode, 2, blocked.stderr)
        self.assertIn("native_store_path", blocked.stderr)
        self.assertNotIn("fixture", blocked.stdout + blocked.stderr)
        allowed = self.run_command(handler["command"], self.bash(
            "python3 tools/credentials/credential_run.py fake-id -- true"))
        self.assertEqual((allowed.returncode, allowed.stderr), (0, ""))
        # Controls: the repository guard says the same when run directly.
        direct = subprocess.run([sys.executable, "-B", str(GUARD_SOURCE)], input=json.dumps(
            self.bash(f"cat {fake}/.codex/auth.json")), capture_output=True, text=True, check=False)
        self.assertEqual(direct.returncode, 2)

    def test_registered_guard_fails_closed_when_the_staged_copy_is_missing(self):  # g3
        self.stage(guard=True, hooks={"secret_guard": True})
        self.job("guard-gone", last=H.LAST, events=[H.COMPLETED])
        _, handler, _ = self.registered()
        (self.work / codex_job.GUARD_FILE).unlink()
        # Codex lets the call continue on a crash or any exit but 2 with stderr text (pre_tool_use.rs:213-291).
        missing = self.run_command(handler["command"], self.bash("true"))
        self.assertEqual(missing.returncode, 2)
        self.assertIn("guard_missing", missing.stderr)
        # And the runner refuses before codex starts.
        (self.bin / "record.json").unlink()
        self.fake(last=H.LAST, events=[H.COMPLETED])
        self.call("start", "guard-gone-2", self.prompt, self.schema)
        self.call("wait", "guard-gone-2", "20")
        result = json.loads(self.call("result", "guard-gone-2").stdout)
        self.assertEqual((result["exit"], result["failure"]["kind"]), (2, "hook_trust"))
        self.assertFalse((self.bin / "record.json").exists())

    def test_a_staged_copy_that_differs_from_its_recorded_sha_is_refused(self):
        self.stage(guard=True, hooks={"secret_guard": True})
        (self.work / codex_job.GUARD_FILE).write_text("raise SystemExit(0)\n", encoding="utf-8")
        self.fake(last=H.LAST, events=[H.COMPLETED])
        self.call("start", "guard-tampered", self.prompt, self.schema)
        self.call("wait", "guard-tampered", "20")
        result = json.loads(self.call("result", "guard-tampered").stdout)
        self.assertEqual((result["exit"], result["failure"]["kind"]), (2, "hook_trust"))
        self.assertFalse((self.bin / "record.json").exists())

    def test_guard_lets_apply_patch_payloads_through_today(self):  # g4, characterization: flips with the guard PR
        patch = "*** Begin Patch\n*** Update File: /home/example/.codex/auth.json\n*** End Patch"
        done = subprocess.run([sys.executable, "-B", str(GUARD_SOURCE)], input=json.dumps(
            {"tool_name": "apply_patch", "tool_input": {"command": patch}}), capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_guard_and_rtk_share_one_state_table_on_both_lanes(self):
        hooks_json(self.codex_home, [RTK_GROUP])
        self.stage(guard=True, hooks={"rtk": True, "secret_guard": True})
        self.job("both", last=H.LAST, events=[H.COMPLETED])
        _, _, state = self.registered()
        self.assertEqual(sorted(state), sorted([f"{codex_job.SESSION_FLAGS_CONFIG}:pre_tool_use:0:0",
                                                f"{self.codex_home}/hooks.json:pre_tool_use:0:0"]))
        self.assertEqual(len(flag(self.argv(), "hooks.state")), 1)
        self.assertEqual(self.record()["rtk_telemetry"], "1")
        home = self.lane(guard=True, hooks={"rtk": True, "secret_guard": True})
        hooks_json(home, [RTK_GROUP])
        self.job("both-lane", last=H.LAST, events=[H.COMPLETED])
        _, _, lane_state = self.registered()
        self.assertEqual(sorted(lane_state), sorted([f"{codex_job.SESSION_FLAGS_CONFIG}:pre_tool_use:0:0",
                                                     f"{os.path.realpath(home)}/hooks.json:pre_tool_use:0:0"]))


class DisableAppsTests(HardeningCase):
    def test_disable_apps_is_a_staged_bound_flag_and_web_search_alone_adds_nothing(self):  # c1
        self.stage(web_search="disabled")
        plain = self.job("plain", last=H.LAST, events=[H.COMPLETED])
        self.assertNotIn("--disable", self.argv())  # no coupling: today's reviewer bytes stay
        self.assertNotIn("disable", plain["inputs"])
        self.stage(web_search="disabled", disable=["apps"])
        result = self.job("reviewer", last=H.LAST, events=[H.COMPLETED])
        argv = self.argv()
        at = argv.index("--disable")
        self.assertEqual(argv[at:at + 2], ["--disable", "apps"])
        self.assertNotIn("features.apps=false", flags(argv))
        self.assertEqual(result["inputs"]["disable"], ["apps"])
        self.stage(web_search="live")
        self.job("live", last=H.LAST, events=[H.COMPLETED])
        self.assertNotIn("--disable", self.argv())

    def test_gateway_reviewer_lane_disables_apps(self):  # c2
        self.lane(web_search="disabled", disable=["apps"])
        self.job("lane-reviewer", last=H.LAST, events=[H.COMPLETED])
        argv = self.argv()
        self.assertEqual(argv[:3], ["exec", "-p", "stack-worker"])
        self.assertEqual(argv[argv.index("--disable"):argv.index("--disable") + 2], ["--disable", "apps"])
        self.assertIn('web_search="disabled"', argv)

    def test_disable_accepts_only_listed_distinct_features(self):
        for staged in ([], "apps", ["apps", "apps"], ["unknown"], [1]):
            with self.subTest(staged=staged):
                self.stage(disable=staged)
                with self.assertRaises(codex_job.UsageError):
                    codex_job.settings(self.work)


class OtelTests(HardeningCase):
    def otel_values(self, argv):
        return {key: inline(flag(argv, key)[0].split("=", 1)[1]) for key in
                ("otel.exporter", "otel.metrics_exporter", "otel.tool_result.max_bytes", "otel.environment")}

    def test_otel_overrides_are_four_inline_values_tagged_with_the_job_id(self):  # d1
        job = "j" * 128  # the longest id JOB_ID admits
        self.stage(otel={"endpoint": "127.0.0.1:23318"})
        result = self.job(job, last=H.LAST, events=[H.COMPLETED])
        values = self.otel_values(self.argv())
        self.assertEqual(values["otel.exporter"], {"otlp-http": {"endpoint": "http://127.0.0.1:23318/v1/logs",
                                                                  "protocol": "binary"}})
        self.assertEqual(values["otel.metrics_exporter"], {"otlp-http": {"endpoint": "http://127.0.0.1:23318/v1/metrics",
                                                                          "protocol": "binary"}})
        self.assertEqual(values["otel.tool_result.max_bytes"], 0)
        self.assertEqual(values["otel.environment"], job)
        self.assertRegex(values["otel.environment"], r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
        for forbidden in ("span_attributes", "log_user_prompt"):
            self.assertFalse([value for value in flags(self.argv()) if forbidden in value])
        self.assertEqual(result["inputs"]["otel"], {"endpoint": "127.0.0.1:23318"})

    def test_lane_prefix_stays_inside_the_collector_id_pattern_and_limit(self):
        self.stage(otel={"endpoint": "localhost:23318", "lane": "gpt6.lane:a"})
        job = "x" * (128 - len("gpt6.lane:a-"))
        self.job(job, last=H.LAST, events=[H.COMPLETED])
        tag = self.otel_values(self.argv())["otel.environment"]
        self.assertEqual((tag, len(tag)), (f"gpt6.lane:a-{job}", 128))
        self.assertRegex(tag, r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
        # One more character would be deleted by the collector, so the job is refused before any state changes.
        long_job = job + "x"
        started = self.call("start", long_job, self.prompt, self.schema)
        self.assertEqual(started.returncode, codex_job.EXIT_REFUSED, started.stdout)
        self.assertIn("otel.environment", started.stderr)
        self.assertFalse((self.work / "gpt6" / long_job).exists())

    def test_otel_endpoint_must_be_loopback_and_is_refused_before_state_changes(self):  # d2
        for endpoint in ("10.0.0.5:4318", "example.org:4318", "127.0.0.1:0", "127.0.0.1", "127.0.0.1:70000",
                         "http://127.0.0.1:4318", None, 4318):
            with self.subTest(endpoint=endpoint):
                self.stage(otel={"endpoint": endpoint})
                with self.assertRaises(codex_job.UsageError):
                    codex_job.settings(self.work)
                started = self.call("start", "otel-bad", self.prompt, self.schema)
                self.assertEqual(started.returncode, codex_job.EXIT_REFUSED)
                self.assertFalse((self.work / "gpt6" / "otel-bad").exists())
        for staged in ({"endpoint": "127.0.0.1:4318", "lane": "bad lane"}, {"endpoint": "127.0.0.1:4318", "x": 1}, []):
            with self.subTest(staged=staged):
                self.stage(otel=staged)
                with self.assertRaises(codex_job.UsageError):
                    codex_job.settings(self.work)


class RolloutUsageTests(HardeningCase):
    def failed(self, name, home=None, **extra):
        if home is not None:
            self.env["CODEX_HOME"] = str(home)
        return self.job(name, exit=1, events=FAILED, **extra)

    def test_failed_attempt_usage_comes_from_the_rollout(self):  # e1
        write_rollout(self.codex_home, THREAD, [{**USAGE, "input_tokens": 1, "total_tokens": 1}, USAGE])
        self.stage(rollout_usage=True)
        result = self.job("failed", exit=1, events=FAILED)
        self.assertEqual(result["exit"], 1)
        self.assertEqual((result["usage"], result["usage_status"]), ({}, "unavailable"))  # these two stay as they were
        rollout = result["rollout_usage"]
        self.assertEqual((rollout["status"], rollout["thread_id"]), ("found", THREAD))
        self.assertEqual(rollout["usage"], {key: value for key, value in USAGE.items() if key != "total_tokens"})
        self.assertNotIn("total_tokens", rollout["usage"])
        self.assertEqual(rollout["rollout"], f"sessions/2026/10/16/rollout-2026-10-16T22-42-51-{THREAD}.jsonl")
        self.assertEqual(json.loads(self.call("result", "failed").stdout)["rollout_usage"], rollout)

    def test_rollout_is_found_by_thread_id_not_by_date_folder(self):  # e2
        write_rollout(self.codex_home, THREAD, [USAGE], folder=("1999", "01", "02"), stamp="1999-01-02T03-04-05")
        write_rollout(self.codex_home, "fixture-thread-ffff", [{**USAGE, "input_tokens": 5}])
        self.stage(rollout_usage=True)
        rollout = self.job("by-thread", exit=1, events=FAILED)["rollout_usage"]
        self.assertEqual((rollout["status"], rollout["usage"]["input_tokens"]), ("found", 189046))
        self.assertTrue(rollout["rollout"].startswith("sessions/1999/01/02/"))

    def test_gateway_lane_reads_the_lane_home_rollout(self):
        home = self.lane(rollout_usage=True)
        write_rollout(home, THREAD, [USAGE])
        write_rollout(self.codex_home, THREAD, [{**USAGE, "input_tokens": 7}])  # the caller's home is not the lane's
        rollout = self.job("lane-failed", exit=1, events=FAILED)["rollout_usage"]
        self.assertEqual(rollout["usage"]["input_tokens"], 189046)

    def test_archived_attempt_keeps_its_own_home_and_rollout_usage(self):  # e3
        first_home, second_home = self.home / "first", self.home / "second"
        for directory in (first_home, second_home):
            directory.mkdir()
        write_rollout(first_home, THREAD, [USAGE])
        self.stage(rollout_usage=True)
        self.failed("retried", first_home)
        self.env["CODEX_HOME"] = str(second_home)  # the caller's home moves before the second attempt and result
        result = self.job("retried", last=H.LAST, events=[H.COMPLETED])
        self.assertEqual(result["exit"], 0)
        self.assertEqual(result["rollout_usage"]["status"], "not_needed")  # a completed turn is not read from a rollout
        attempt = result["attempts"][0]
        self.assertEqual(attempt["rollout_usage"]["status"], "found")
        self.assertEqual(attempt["rollout_usage"]["usage"]["output_tokens"], 3633)
        self.assertEqual((attempt["usage"], attempt["usage_status"]), (None, "unavailable"))
        self.assertTrue((self.work / "gpt6" / "retried" / "attempts" / "1" / "codex_home").is_file())
        self.assertEqual((self.work / "gpt6" / "retried" / "attempts" / "1" / "codex_home").read_text().strip(),
                         str(first_home))

    def test_rollout_usage_survives_a_later_loss_of_the_rollout(self):
        path = write_rollout(self.codex_home, THREAD, [USAGE])
        self.stage(rollout_usage=True)
        self.job("kept", exit=1, events=FAILED)
        path.unlink()
        self.assertEqual(json.loads(self.call("result", "kept").stdout)["rollout_usage"]["status"], "found")

    def test_unavailable_cases_record_a_reason_and_leave_the_exit_alone(self):  # e4 controls
        self.stage(rollout_usage=True)
        died = self.job("before-thread", exit=1, events=[])
        self.assertEqual((died["exit"], died["usage_status"]), (1, "unavailable"))
        self.assertEqual(died["rollout_usage"]["status"], "unavailable")
        self.assertIn("thread.started", died["rollout_usage"]["reason"])
        missing = self.job("no-rollout", exit=1, events=FAILED)
        self.assertEqual((missing["exit"], missing["rollout_usage"]["status"]), (1, "unavailable"))
        self.assertEqual(missing["rollout_usage"]["thread_id"], THREAD)
        self.assertIn("no rollout", missing["rollout_usage"]["reason"])
        directory = self.work / "gpt6" / "no-rollout"
        rollout = write_rollout(self.codex_home, THREAD, [])  # a rollout without a token_count event
        empty = codex_job.find_rollout_usage(directory, self.codex_home)
        self.assertEqual((empty["status"], empty["reason"]), ("unavailable", "the rollout holds no token_count event"))
        # the finished attempt keeps the receipt it wrote, whatever happens to the rollout afterwards
        self.assertEqual(json.loads(self.call("result", "no-rollout").stdout)["rollout_usage"]["status"], "unavailable")
        rollout.unlink()
        (rollout.parent / f"rollout-x-{THREAD}.jsonl.zst").write_bytes(b"")
        record = codex_job.find_rollout_usage(directory, self.codex_home)
        self.assertEqual((record["status"], record["reason"]), ("unavailable", "the rollout is compressed"))

    def test_a_completed_turn_wins_and_the_rollout_is_not_read(self):  # e4 control
        write_rollout(self.codex_home, THREAD, [USAGE])
        self.stage(rollout_usage=True)
        result = self.job("done", last=H.LAST, events=[{"type": "thread.started", "thread_id": THREAD}, H.COMPLETED])
        self.assertEqual(result["usage"], H.COMPLETED["usage"])
        self.assertEqual(result["rollout_usage"], {"status": "not_needed", "reason": mock.ANY})

    def test_unstaged_jobs_carry_no_rollout_field(self):  # e4 control
        write_rollout(self.codex_home, THREAD, [USAGE])
        self.stage()
        result = self.job("unstaged", exit=1, events=FAILED)
        self.assertNotIn("rollout_usage", result)
        self.assertFalse((self.work / "gpt6" / "unstaged" / "codex_home").exists())

    def test_convert_counts_the_attempt_unavailable_and_never_sums_rollout_usage(self):  # e5
        total = {"usage": {}, "usage_unavailable": 0}
        convert.add_usage(total, {"usage": None, "usage_status": "unavailable",
                                  "rollout_usage": {"status": "found", "usage": {"input_tokens": 5}}})
        self.assertEqual(total, {"usage": {}, "usage_unavailable": 1})


class BuildCase(unittest.TestCase):
    def build(self, work, *extra, env=None):
        return H.run([sys.executable, HARNESS / "build_args.py", "--work-dir", work, "--sweep-id",
                      "landscape-sweep-20261026", "--date", "2026-10-26", *extra], env=env)

    def staged(self, work):
        return json.loads((work / "staged.json").read_text(encoding="utf-8"))

    def lane_args(self):
        profile = H.temp_dir(self) / "stack-worker.config.toml"
        profile.write_text(H.STACK_WORKER_FIXTURE, encoding="utf-8")
        return ["--gpt6-provider", "omniroute", "--codex-host", "example", "--stack-worker-profile", profile]

    def stub_rtk(self):
        """A stub for upstream's installer, recording its argv and CODEX_HOME: what `rtk init -g --codex` wrote in the
        measured dry run (RTK.md, an @RTK.md pointer in AGENTS.md, one PreToolUse group in hooks.json)."""
        directory = H.temp_dir(self)
        log = directory / "rtk.log"
        script = directory / "rtk"
        script.write_text(f'''#!{sys.executable}
import json, os, sys
home = os.environ["CODEX_HOME"]
with open({str(log)!r}, "a") as out:
    out.write(json.dumps({{"argv": sys.argv[1:], "codex_home": home, "telemetry": os.environ.get("RTK_TELEMETRY_DISABLED")}}) + "\\n")
if os.environ.get("RTK_STUB_FAIL"):
    sys.stderr.write("stub failure\\n")
    sys.exit(1)
hooks = os.path.join(home, "hooks.json")
if not os.path.exists(hooks):
    with open(hooks, "w") as out:
        json.dump({{"hooks": {{"PreToolUse": [{{"matcher": "Bash", "hooks": [{{"type": "command", "command": "rtk hook codex"}}]}}]}}}}, out)
with open(os.path.join(home, "RTK.md"), "w") as out:
    out.write("rtk fixture\\n")
agents = os.path.join(home, "AGENTS.md")
text = open(agents).read() if os.path.exists(agents) else ""
if "@RTK.md" not in text:
    with open(agents, "a") as out:
        out.write("\\n@" + os.path.join(home, "RTK.md") + "\\n")
''', encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return directory, log


class OptionsStageKeysTests(BuildCase):
    def test_build_args_stages_hook_otel_and_guard_keys(self):  # s1
        work = H.stage_work(self)
        done = self.build(work, "--codex-hook", "rtk", "--codex-hook", "secret_guard", "--codex-disable-feature", "apps",
                          "--web-search", "disabled", "--codex-otel-endpoint", "127.0.0.1:23318",
                          "--codex-otel-lane", "gpt6-a", "--rollout-usage")
        self.assertEqual(done.returncode, 0, done.stderr)
        staged = self.staged(work)
        self.assertEqual({key: staged["codex"][key] for key in ("hooks", "disable", "web_search", "otel", "rollout_usage")},
                         {"hooks": {"rtk": True, "secret_guard": True}, "disable": ["apps"], "web_search": "disabled",
                          "otel": {"endpoint": "127.0.0.1:23318", "lane": "gpt6-a"}, "rollout_usage": True})
        copy = work / codex_job.GUARD_FILE
        self.assertEqual(copy.read_bytes(), GUARD_SOURCE.read_bytes())
        self.assertEqual(staged["harness"]["files"][codex_job.GUARD_FILE], hashlib.sha256(copy.read_bytes()).hexdigest())
        settings = codex_job.settings(work)  # the runner accepts what the stager wrote
        self.assertEqual((settings["hooks"], settings["disable"], settings["rollout_usage"]),
                         ({"rtk": True, "secret_guard": True}, ("apps",), True))
        self.assertFalse((work / "codex-home").exists())  # a native lane runs no installer
        (work / "gpt6" / "earlier").mkdir()
        again = self.build(work, "--force", "--codex-hook", "rtk", "--codex-hook", "secret_guard")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.staged(work)["codex"]["hooks"], {"rtk": True, "secret_guard": True})
        self.assertNotIn("otel", self.staged(work)["codex"])  # a restage keeps what its options say
        plain = self.build(work, "--force")
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertFalse(set(self.staged(work)["codex"]) & {"hooks", "disable", "otel", "rollout_usage", "web_search"})
        self.assertFalse(copy.exists())  # no stale guard copy without the option
        self.assertNotIn(codex_job.GUARD_FILE, self.staged(work)["harness"]["files"])

    def test_invalid_hardening_options_stage_nothing(self):
        for extra in (("--codex-otel-endpoint", "10.0.0.5:4318"), ("--codex-otel-endpoint", "127.0.0.1"),
                      ("--codex-otel-lane", "gpt6"), ("--codex-otel-endpoint", "127.0.0.1:4318",
                                                      "--codex-otel-lane", "bad lane"),
                      ("--codex-hook", "other"), ("--codex-disable-feature", "web"),
                      ("--ai-memory-bearer-env",), ("--ai-memory-bearer-env", "AI_MEMORY_AUTH_TOKEN")):
            with self.subTest(extra=extra):
                work = H.stage_work(self)
                done = self.build(work, *extra)
                self.assertNotEqual(done.returncode, 0)
                self.assertFalse((work / "staged.json").exists())


class EndToEndTests(BuildCase, HardeningCase):
    def setUp(self):
        HardeningCase.setUp(self)

    def test_staged_options_drive_a_real_runner_job(self):  # the stager and the runner agree end to end
        H.stage_work(self, work=self.work)
        done = self.build(self.work, "--codex-hook", "secret_guard", "--codex-disable-feature", "apps",
                          "--web-search", "disabled", "--codex-otel-endpoint", "127.0.0.1:23318", "--rollout-usage")
        self.assertEqual(done.returncode, 0, done.stderr)
        staged = self.staged(self.work)
        staged["codex"].update(wait_poll_s=0.05, slot_poll_s=0.05, timeout_s=30)
        H.write_json(self.work / "staged.json", staged)
        write_rollout(self.codex_home, THREAD, [USAGE])
        result = self.job("end-to-end", exit=1, events=FAILED)
        argv = self.argv()
        self.assertIn("--disable", argv)
        self.assertEqual(len(flag(argv, "hooks.state")), 1)
        self.assertEqual(len(flag(argv, "hooks.PreToolUse")), 1)
        self.assertEqual(inline(flag(argv, "otel.environment")[0].split("=", 1)[1]), "end-to-end")
        self.assertIn('web_search="disabled"', argv)
        self.assertEqual(result["rollout_usage"]["status"], "found")


class AiMemoryBearerTests(BuildCase, HardeningCase):
    """The gateway lane's ai-memory entry reads its token from a variable (the host's own form); no token is written."""

    def setUp(self):
        HardeningCase.setUp(self)

    def test_lane_home_carries_the_bearer_variable_only_when_asked(self):  # a1
        work, argv = H.stage_work(self), self.lane_args()
        plain = self.build(work, *argv)
        self.assertEqual(plain.returncode, 0, plain.stderr)
        config = (work / "codex-home" / "config.toml").read_text(encoding="utf-8")
        self.assertNotIn("bearer_token_env_var", config)
        self.assertNotIn("AI_MEMORY_AUTH_TOKEN", config)
        self.assertNotIn("ai_memory_token_env", self.staged(work)["codex"])
        asked = self.build(work, "--force", *argv, "--ai-memory-bearer-env")
        self.assertEqual(asked.returncode, 0, asked.stderr)
        parsed = tomllib.loads((work / "codex-home" / "config.toml").read_text(encoding="utf-8"))
        self.assertEqual(parsed["mcp_servers"]["ai-memory"]["bearer_token_env_var"], "AI_MEMORY_AUTH_TOKEN")
        self.assertEqual(parsed["shell_environment_policy"]["filters"],
                         {"OMNIROUTE_API_KEY": "exclude", "AI_MEMORY_AUTH_TOKEN": "exclude"})
        self.assertIn("url", parsed["mcp_servers"]["ai-memory"])
        self.assertNotIn("Authorization", json.dumps(parsed))
        staged = self.staged(work)
        self.assertEqual(staged["codex"]["ai_memory_token_env"], "AI_MEMORY_AUTH_TOKEN")
        self.assertEqual(staged["codex"]["lane_home"]["config_sha256"],
                         hashlib.sha256((work / "codex-home" / "config.toml").read_bytes()).hexdigest())
        self.assertEqual(codex_job.settings(work)["ai_memory_token_env"], "AI_MEMORY_AUTH_TOKEN")
        other = self.build(work, "--force", *argv, "--ai-memory-bearer-env", "AI_MEMORY_OTHER_TOKEN")
        self.assertEqual(other.returncode, 0, other.stderr)
        self.assertEqual(codex_job.settings(work)["ai_memory_token_env"], "AI_MEMORY_OTHER_TOKEN")

    def test_stage_lane_home_adds_the_bearer_entry_without_touching_other_servers(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            profile = work / "profile.toml"
            profile.write_text(H.STACK_WORKER_FIXTURE, encoding="utf-8")
            kwargs = dict(model="cx/gpt-6-astra", base_url="http://127.0.0.1:21128/v1", host="example",
                          profile=profile, repo_root=ROOT)
            build_args.stage_lane_home(work, **kwargs)
            plain = tomllib.loads((work / "codex-home" / "config.toml").read_text(encoding="utf-8"))
            build_args.stage_lane_home(work, **kwargs, bearer_env="AI_MEMORY_AUTH_TOKEN")
            bearer = tomllib.loads((work / "codex-home" / "config.toml").read_text(encoding="utf-8"))
        entry = bearer["mcp_servers"].pop("ai-memory")
        self.assertEqual(entry, {**plain["mcp_servers"]["ai-memory"], "bearer_token_env_var": "AI_MEMORY_AUTH_TOKEN"})
        plain["mcp_servers"].pop("ai-memory")
        self.assertEqual(bearer["mcp_servers"], plain["mcp_servers"])
        for key in ("model", "model_provider", "features", "model_providers"):
            self.assertEqual(bearer[key], plain[key])

    def test_runner_refuses_a_start_without_the_variable_and_never_writes_its_value(self):  # a1
        self.lane(ai_memory_token_env="AI_MEMORY_AUTH_TOKEN")
        self.fake(last=H.LAST, events=[H.COMPLETED])
        self.call("start", "no-token", self.prompt, self.schema)
        self.call("wait", "no-token", "20")
        result = json.loads(self.call("result", "no-token").stdout)
        self.assertEqual((result["exit"], result["failure"]["kind"]), (codex_job.EXIT_NO_KEY, "no_key"))
        self.assertIn("AI_MEMORY_AUTH_TOKEN is not set", result["stderr_tail"])
        self.assertFalse((self.bin / "record.json").exists())
        self.env["AI_MEMORY_AUTH_TOKEN"] = "   "  # blank counts as unset
        self.call("start", "blank-token", self.prompt, self.schema)
        self.call("wait", "blank-token", "20")
        self.assertEqual(json.loads(self.call("result", "blank-token").stdout)["exit"], codex_job.EXIT_NO_KEY)
        self.env["AI_MEMORY_AUTH_TOKEN"] = SENTINEL_TEXT
        done = self.job("with-token", last=H.LAST, events=[H.COMPLETED])
        self.assertEqual(done["exit"], 0)
        self.assertTrue(self.record()["ai_memory_token_present"])
        self.assertEqual(done["inputs"]["ai_memory_token_env"], "AI_MEMORY_AUTH_TOKEN")
        self.sentinel_free(SENTINEL_TEXT)  # no file, argument, record or output holds the value
        self.assertNotIn(SENTINEL_TEXT, json.dumps(done) + " ".join(self.argv()))

    def test_lane_config_must_carry_the_staged_variable(self):
        home = self.lane(ai_memory_token_env="AI_MEMORY_AUTH_TOKEN")
        self.assertEqual(codex_job.settings(self.work)["ai_memory_token_env"], "AI_MEMORY_AUTH_TOKEN")
        (home / "config.toml").write_text('[mcp_servers.ai-memory]\nurl = "http://127.0.0.1:1/mcp"\n', encoding="utf-8")
        with self.assertRaises(codex_job.UsageError):
            codex_job.settings(self.work)
        self.stage(ai_memory_token_env="AI_MEMORY_AUTH_TOKEN")  # a native lane has no lane home
        with self.assertRaises(codex_job.UsageError):
            codex_job.settings(self.work)

    def test_an_unstaged_lane_needs_no_token_variable(self):
        self.lane()
        done = self.job("no-bearer", last=H.LAST, events=[H.COMPLETED])
        self.assertEqual(done["exit"], 0)
        self.assertFalse(self.record()["ai_memory_token_present"])
        self.assertNotIn("ai_memory_token_env", done["inputs"])


class RtkInitStageTests(BuildCase):
    def test_lane_home_runs_rtk_init_only_when_asked(self):
        directory, log = self.stub_rtk()
        env = {**os.environ, "PATH": f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"}
        work = H.stage_work(self)
        plain = self.build(work, *self.lane_args(), env=env)
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertFalse(log.exists())  # the default staging never runs rtk
        self.assertFalse((work / "codex-home" / "hooks.json").exists())
        asked = self.build(work, "--force", *self.lane_args(), "--codex-hook", "rtk", env=env)
        self.assertEqual(asked.returncode, 0, asked.stderr)
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual(calls, [{"argv": ["init", "-g", "--codex"], "codex_home": str(work / "codex-home"),
                                  "telemetry": "1"}])
        home = work / "codex-home"
        self.assertTrue((home / "RTK.md").is_file())
        entry = codex_job.rtk_hook_entry(home / "hooks.json")
        self.assertEqual(entry, (0, 0, RTK_GOLDEN))
        staged = self.staged(work)
        self.assertEqual(staged["codex"]["hooks"], {"rtk": True})
        lane = staged["codex"]["lane_home"]
        self.assertEqual(lane["agents_sha256"], hashlib.sha256((home / "AGENTS.md").read_bytes()).hexdigest())
        self.assertIn("@", (home / "AGENTS.md").read_text())  # the pointer rtk appended
        self.assertNotIn("[hooks.state", (home / "config.toml").read_text())  # the lane config stays trust-free
        self.assertEqual(lane["config_sha256"], hashlib.sha256((home / "config.toml").read_bytes()).hexdigest())
        again = self.build(work, "--force", *self.lane_args(), "--codex-hook", "rtk", env=env)  # idempotent restage
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(codex_job.rtk_hook_entry(home / "hooks.json"), (0, 0, RTK_GOLDEN))

    def test_native_lane_runs_no_installer(self):
        directory, log = self.stub_rtk()
        env = {**os.environ, "PATH": f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"}
        work = H.stage_work(self)
        self.assertEqual(self.build(work, "--codex-hook", "rtk", env=env).returncode, 0)
        self.assertFalse(log.exists())

    def test_a_failing_or_missing_installer_stages_nothing_further(self):
        directory, log = self.stub_rtk()
        env = {**os.environ, "PATH": f"{directory}{os.pathsep}{os.environ.get('PATH', '')}", "RTK_STUB_FAIL": "1"}
        work = H.stage_work(self)
        failed = self.build(work, *self.lane_args(), "--codex-hook", "rtk", env=env)
        self.assertEqual(failed.returncode, 2)
        self.assertIn("rtk init -g --codex", failed.stderr)
        self.assertFalse((work / "staged.json").exists())
        bare = H.temp_dir(self)  # a PATH holding no rtk
        path = f"{bare}{os.pathsep}/usr/bin{os.pathsep}/bin"
        if shutil.which("rtk", path=path) is None:
            missing = self.build(H.stage_work(self), *self.lane_args(), "--codex-hook", "rtk",
                                 env={**os.environ, "PATH": path})
            self.assertEqual(missing.returncode, 2)
            self.assertIn("needs the rtk binary", missing.stderr)


class PairedProbeTests(unittest.TestCase):
    """The paired probe is staged for a day GPT capacity returns: it prints a plan by default and never starts a job
    here (no test passes --run with the capacity flag)."""

    def probe(self, *extra, lane=None, scratch=None):
        tmp = H.temp_dir(self)
        lane = lane or tmp / "lane"
        if not lane.exists():
            H.write_json(lane / "staged.json", {"sweep_id": "landscape-sweep-20261017", "date": "2026-10-17", "codex": {}})
        scratch = scratch or tmp / "scratch"
        done = H.run([sys.executable, HARNESS / "paired_probe.py", "--lane", lane, "--pr-checkout", ROOT,
                      "--scratch", scratch, *extra])
        return done, lane, scratch

    def test_default_prints_the_interleaved_plan_and_touches_nothing(self):
        done, lane, scratch = self.probe("--build-flags=--gpt6-provider omniroute", "--hardening-flags=--codex-hook rtk")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("PLAN ONLY", done.stdout)
        order = re.findall(r"^- ([BA]\d): ", done.stdout, re.MULTILINE)
        self.assertEqual(order, ["B1", "A1", "B2", "A2", "B3", "A3"])
        self.assertIn("--force", done.stdout)
        self.assertIn("--codex-hook rtk", done.stdout)
        self.assertFalse(scratch.exists())
        self.assertEqual(sorted(path.name for path in lane.iterdir()), ["staged.json"])

    def test_run_needs_the_capacity_confirmation_and_an_outside_scratch(self):
        done, lane, scratch = self.probe("--run")
        self.assertEqual(done.returncode, 2)
        self.assertIn("--gpt-capacity-confirmed", done.stderr)
        self.assertFalse(scratch.exists())
        missing = H.run([sys.executable, HARNESS / "paired_probe.py", "--lane", lane / "nope", "--pr-checkout", ROOT,
                         "--scratch", H.temp_dir(self) / "s"])
        self.assertEqual(missing.returncode, 2)
        nested = H.run([sys.executable, HARNESS / "paired_probe.py", "--lane", lane, "--pr-checkout", ROOT,
                        "--scratch", lane / "inside"])
        self.assertEqual(nested.returncode, 2)
        self.assertIn("outside the lane", nested.stderr)


class DecisionRecordCoverageTests(unittest.TestCase):
    """The record states what the Bash-only guard does not see (review finding gate:R1)."""

    RECORD = ROOT / "docs" / "decisions" / "2026-10-17-codex-job-lane-hooks-mcp-memory.md"

    def hooks_section(self) -> str:
        text = self.RECORD.read_text(encoding="utf-8")
        start = text.index("## Hooks: per-job trust")
        return " ".join(text[start:text.index("### Supersession", start)].split())  # one line, runs of spaces folded

    def test_record_names_write_stdin_and_mcp_as_uncovered_with_upstream_citations(self):
        section = self.hooks_section()
        self.assertRegex(section, r"`write_stdin` is transport for an existing unified-exec session and runs no `PreToolUse`")
        self.assertIn("hooks.md:450-465", section)
        self.assertIn("unified_exec/write_stdin.rs:144-149", section)
        self.assertRegex(section, r"MCP tools do run `PreToolUse`, but under their own names")
        self.assertIn("mcp.rs:109-111,449-459", section)
        self.assertIn("matcher.rs:12-34", section)
        self.assertIn("`apply_patch` is therefore not the only uncovered path", section)


if __name__ == "__main__":
    unittest.main()
