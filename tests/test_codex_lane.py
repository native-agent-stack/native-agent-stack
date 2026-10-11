"""Synthetic-fixture tests for tools/sota-convergence/codex_lane.py.

No real ``codex`` binary is ever invoked. A fake ``codex`` script fixture
(``tests/fixtures/codex-lane/bin/codex``) is placed first on PATH for every
test in this module; it is env-var driven (see its own docstring) so each
test configures the exact behavior it needs -- argv recording, a canned
event stream, a canned ``-o`` return, chosen failing attempts, and an
optional sleep to exercise the timeout path. Modules are loaded by file path
(tools/sota-convergence is not a dotted-import package name), matching the
pattern already used by test_layer_verdicts.py.
"""
import contextlib
import hashlib
import importlib.util
import io
import time
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "sota-convergence"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "codex-lane"
FIXTURE_PROMPT = FIXTURE_DIR / "lane-prompt.md"
FIXTURE_SCHEMA = FIXTURE_DIR / "lane-return.schema.json"
FIXTURE_BIN = FIXTURE_DIR / "bin"


def load_module(name, filename):
    path = TOOL_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


codex_lane = load_module("codex_lane", "codex_lane.py")
# The suite does not depend on the PATH this host's login shell ends up with (independent review of #206, R2-3): a new
# PC with npm globals in /usr/local/bin would otherwise refuse every blind fixture run. The real probe is tested below.
REAL_LOGIN_SHELL_PATH = codex_lane.login_shell_path
_SHELL_PATH = mock.patch.object(codex_lane, "login_shell_path", return_value=codex_lane.BLIND_CHILD_PATH)


def setUpModule():
    _SHELL_PATH.start()


def tearDownModule():
    _SHELL_PATH.stop()


def canned_return(**overrides):
    row = {
        "schema_version": 1, "lane": "codex", "catalog": "foundation", "layer_id": "native-clients",
        "winner_keys": ["c1"],
        "why_selected": "c1 is the only adopted candidate with native execution evidence recorded in receipt.json.",
        "winner_evidence_class": "native_proven", "winner_evidence_refs": ["evidence/receipt.json"],
        "alternatives": [{
            "key": "c2", "name": "Other", "repository": "https://github.com/example/other",
            "disposition": "conditional",
            "why_not_default": "No native execution evidence was found for this candidate in the packet.",
            "evidence_class": "source_review", "evidence_refs": [],
        }],
        "challenger_preferred": None,
        "overturn_when": "python3 tests/fixtures/codex-lane/rerun.py improves the measured result",
        "overturn_protocol": {"fixture_paths": [], "metric": "", "arms": []},
        "open_gaps": [], "sources_read": ["evidence/receipt.json"], "limits": [],
    }
    row.update(overrides)
    return row


def audit_with_fixture_cwd(events_path, allowed_roots, tools=codex_lane.AUDIT_TOOLS):
    """Command-only fixture oracle with independent synthetic cwd records; never restamp real streams."""
    rows = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = {}
    for index, row in enumerate(rows):
        item = row.get("item", {})
        if row.get("type") == "item.completed" and item.get("type") == "command_execution":
            identity = f"synthetic-cwd-{index}"
            item["id"] = identity
            records[identity] = {"command": item["command"], "cwd": str(allowed_roots[0])}
    events_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return codex_lane.blind_audit(events_path, allowed_roots, tools, cwd_records=records)


CANNED_EVENTS = "\n".join([
    json.dumps({"type": "thread.started", "thread_id": "fixture-thread"}),
    json.dumps({"type": "turn.started"}),
    json.dumps({"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": "done"}}),
    json.dumps({"type": "turn.completed", "usage": {
        "input_tokens": 1234, "cached_input_tokens": 200, "cache_write_input_tokens": 0,
        "output_tokens": 56, "reasoning_output_tokens": 12,
    }, "model": "gpt-6-astra"}),
]) + "\n"


class CodexLaneFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        # A blind export sits at least four directories deep (codex_lane.root_issue, independent review of #145).
        self.repo = base / "hosts" / "blind" / "repo"
        self.work_dir = base / "work"
        self.repo.mkdir(parents=True)
        self.work_dir.mkdir()
        (self.work_dir / "packets").mkdir()

        self._old_environ = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self._old_environ)))
        os.environ["PATH"] = str(FIXTURE_BIN) + os.pathsep + os.environ.get("PATH", "")
        for key in list(os.environ):
            if key.startswith("CODEX_FAKE_"):
                os.environ.pop(key)

        self.argv_log = base / "argv.jsonl"
        self.counter_file = base / "counter.txt"
        self.events_file = base / "events.jsonl"
        self.return_file = base / "return.json"
        os.environ["CODEX_FAKE_ARGV_LOG"] = str(self.argv_log)
        os.environ["CODEX_FAKE_COUNTER_FILE"] = str(self.counter_file)
        os.environ["CODEX_FAKE_EVENTS_FILE"] = str(self.events_file)
        os.environ["CODEX_FAKE_RETURN_FILE"] = str(self.return_file)
        self.events_file.write_text(CANNED_EVENTS, encoding="utf-8")
        self.return_file.write_text(json.dumps(canned_return()), encoding="utf-8")
        # Never the developer's credential or state (independent review of #145, R4-REG-7): a fixture native
        # Codex home with a dummy auth.json, and run-scoped homes under the fixture.
        self.native_codex = base / "native-codex"
        self.native_codex.mkdir()
        (self.native_codex / "auth.json").write_text("{}", encoding="utf-8")
        os.environ["CODEX_HOME"] = str(self.native_codex)
        os.environ[codex_lane.CODEX_HOME_BASE_ENV] = str(base / "codex-homes")
        self.addCleanup(setattr, codex_lane, "CHILD_CODEX_HOME", None)
        # A stop signal in one test never leaks into the next (round 7), nor a held in-use lock.
        codex_lane.STOP.clear()
        self.addCleanup(codex_lane.STOP.clear)
        self.addCleanup(lambda: codex_lane.IN_USE_HANDLE and codex_lane.release_codex_home(None))
        # The fake codex reads its CODEX_FAKE_* settings; production children get only the allowlist (ISO-R5-2).
        prefixes = mock.patch.object(codex_lane, "CHILD_ENV_EXTRA_PREFIXES", ("CODEX_FAKE_",))
        prefixes.start()
        self.addCleanup(prefixes.stop)

    def write_packet(self, catalog: str, layer_id: str, content=None) -> Path:
        path = self.work_dir / "packets" / f"{catalog}__{layer_id}.json"
        path.write_text(json.dumps(content or {"schema_version": 1, "catalog": catalog, "layer_id": layer_id}),
                         encoding="utf-8")
        return path

    def run_lane(self, extra_args=None):
        args = [
            "--work-dir", str(self.work_dir), "--repo", str(self.repo),
            "--prompt", str(FIXTURE_PROMPT), "--schema", str(FIXTURE_SCHEMA),
        ]
        args.extend(extra_args or [])
        return codex_lane.main(args)

    def argv_calls(self):
        if not self.argv_log.exists():
            return []
        return [json.loads(line) for line in self.argv_log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def usage_rows(self):
        usage_path = self.work_dir / "codex" / "usage.jsonl"
        if not usage_path.exists():
            return []
        return [json.loads(line) for line in usage_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def out_path(self, catalog: str, layer_id: str) -> Path:
        return self.work_dir / "codex" / f"{catalog}__{layer_id}.json"


class MissingCliTests(CodexLaneFixture):
    def test_a_missing_codex_cli_exits_2_with_a_message(self):
        self.write_packet("foundation", "native-clients")
        empty = self.work_dir / "empty-bin"
        empty.mkdir()
        os.environ["PATH"] = str(empty)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = self.run_lane()
        self.assertEqual(code, 2)
        self.assertIn("codex CLI is not on PATH", err.getvalue())
        self.assertFalse(self.argv_log.exists())


class CodexLaneTests(CodexLaneFixture):
    def test_dry_run_prints_command_and_writes_nothing(self):
        self.write_packet("foundation", "native-clients")
        import contextlib
        import io
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            exit_code = self.run_lane(["--dry-run"])
        self.assertEqual(exit_code, 0)
        printed = captured.getvalue().strip()
        self.assertIn("codex exec", printed)
        self.assertIn("--sandbox", printed)
        self.assertIn("read-only", printed)
        self.assertIn("--skip-git-repo-check", printed)
        # Verdict runs retain native command cwd history in their fresh scratch home.
        self.assertNotIn("--ephemeral", printed)
        self.assertIn("--output-schema", printed)
        self.assertIn("model_reasoning_effort=max", printed)
        # Nothing written: not even the codex/ directory.
        self.assertFalse((self.work_dir / "codex").exists())
        self.assertEqual(self.argv_calls(), [])

    def test_first_attempt_fails_then_retry_succeeds(self):
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_FAIL_ATTEMPTS"] = "1"
        os.environ["CODEX_FAKE_EXIT_CODE"] = "7"
        # The canned return omits packet_sha256 and model so both must be filled.
        self.return_file.write_text(json.dumps(canned_return(packet_sha256=None, model=None)), encoding="utf-8")

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)

        calls = self.argv_calls()
        self.assertEqual(len(calls), 2, "expected exactly one retry (two invocations)")

        rows = self.usage_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["attempt"], 1)
        self.assertEqual(rows[0]["exit_code"], 7)
        self.assertEqual(rows[1]["attempt"], 2)
        self.assertEqual(rows[1]["exit_code"], 0)
        # The second (successful) attempt's usage row carries the canned
        # token fields found in the event stream.
        self.assertEqual(rows[1]["input_tokens"], 1234)
        self.assertEqual(rows[1]["model"], "gpt-6-astra")

        out_path = self.out_path("foundation", "native-clients")
        self.assertTrue(out_path.exists())
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(data["lane"], "codex")
        self.assertEqual(data["catalog"], "foundation")
        self.assertEqual(data["layer_id"], "native-clients")
        packet_path = self.work_dir / "packets" / "foundation__native-clients.json"
        import hashlib
        expected_sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        self.assertEqual(data["packet_sha256"], expected_sha)
        self.assertEqual(data["model"], {"name": "gpt-6-astra", "effort": "max", "family": "openai"})

    def test_lane_forced_and_self_declared_model_replaced_by_the_event_stream_model(self):
        self.write_packet("foundation", "native-clients")
        # lane deliberately wrong and a self-declared model in the response text: the runner forces
        # lane and records the model it observed in the event stream, never the response's claim
        # (re-review 2026-09-23: a non-OpenAI provider answering "gpt-5" would otherwise be sealed).
        self.return_file.write_text(
            json.dumps(canned_return(lane="claude", model={"name": "gpt-5", "effort": "medium"})),
            encoding="utf-8")
        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["lane"], "codex")
        self.assertEqual(data["model"], {"name": "gpt-6-astra", "effort": "max", "family": "openai"})

    def test_configured_model_is_passed_to_codex_and_recorded(self):
        self.write_packet("foundation", "native-clients")
        self.return_file.write_text(json.dumps(canned_return(model={"name": "gpt-5", "effort": "low"})),
                                    encoding="utf-8")
        self.assertEqual(self.run_lane(["--model", "gpt-6-configured"]), 0)
        argv = self.argv_calls()[0]
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6-configured")
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["model"], {"name": "gpt-6-configured", "effort": "max", "family": "openai"})

    def test_without_an_observed_model_the_name_is_unknown_not_the_response_text(self):
        self.write_packet("foundation", "native-clients")
        self.events_file.write_text("\n".join(line for line in CANNED_EVENTS.splitlines()
                                              if '"model"' not in line) + "\n", encoding="utf-8")
        self.return_file.write_text(json.dumps(canned_return(model={"name": "gpt-5", "effort": "high"})),
                                    encoding="utf-8")
        self.assertEqual(self.run_lane(), 0)
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["model"]["name"], "unknown")
        self.assertEqual(self.argv_calls()[0].count("-m"), 0, "no -m without --model")

    def test_written_return_records_its_own_provenance_and_family(self):
        import hashlib
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["provenance"], {
            "codex_lane_py_sha256": hashlib.sha256((TOOL_DIR / "codex_lane.py").read_bytes()).hexdigest(),
            "prompt_sha256": hashlib.sha256(FIXTURE_PROMPT.read_bytes()).hexdigest(),
            "repo_tree_sha256": codex_lane.tree_sha256(self.repo),
        })
        self.assertEqual(data["model"]["family"], "openai")
        self.assertEqual(data["model"]["name"], "gpt-6-astra")

    def test_a_self_declared_provenance_or_family_is_replaced_by_the_runner(self):
        self.write_packet("foundation", "native-clients")
        self.return_file.write_text(json.dumps(canned_return(
            model={"name": "gpt-6-astra", "effort": "high", "family": "anthropic"},
            provenance={"codex_lane_py_sha256": "0" * 64, "prompt_sha256": "0" * 64})), encoding="utf-8")
        self.assertEqual(self.run_lane(), 0)
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["model"]["family"], "openai")
        self.assertNotEqual(data["provenance"]["prompt_sha256"], "0" * 64)

    def test_resumable_skip_of_an_existing_valid_file(self):
        packet_path = self.write_packet("foundation", "native-clients")
        import hashlib
        packet_sha256 = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        codex_dir = self.work_dir / "codex"
        codex_dir.mkdir()
        existing = canned_return(packet_sha256=packet_sha256,
                                 provenance=codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo),
                                 model={"name": "gpt-6-astra", "effort": "max", "family": "openai"})
        out_path = codex_dir / "foundation__native-clients.json"
        out_path.write_text(json.dumps(existing, sort_keys=True, indent=1) + "\n", encoding="utf-8")
        # A blind return is resumed only with its clean retained events (round 7, REG7-1).
        (codex_dir / "events").mkdir()
        (codex_dir / "events" / "foundation__native-clients.jsonl").write_text(CANNED_EVENTS, encoding="utf-8")
        before = out_path.read_text(encoding="utf-8")

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)
        self.assertEqual(self.argv_calls(), [], "the fake codex must never be invoked for an already-valid layer")
        self.assertEqual(out_path.read_text(encoding="utf-8"), before)

    def test_a_return_from_older_lane_code_or_prompt_reruns_instead_of_being_skipped(self):
        """PR #141 review (P1): the skip ignored provenance, so a return from older lane code or an older
        prompt was skipped forever and then rejected by record_verdicts.py."""
        packet_path = self.write_packet("foundation", "native-clients")
        packet_sha256 = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        current = codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo)
        out_path = self.out_path("foundation", "native-clients")
        out_path.parent.mkdir()
        stale = (None, {**current, "codex_lane_py_sha256": "1" * 64}, {**current, "prompt_sha256": "2" * 64})
        for index, provenance in enumerate(stale, start=1):
            # At the lane's own default effort, so the provenance rule is the only thing that can force the rerun.
            existing = canned_return(packet_sha256=packet_sha256,
                                     model={"name": "gpt-6-astra", "effort": codex_lane.DEFAULT_EFFORT, "family": "openai"})
            if provenance is not None:
                existing["provenance"] = provenance
            out_path.write_text(json.dumps(existing), encoding="utf-8")
            self.assertEqual(self.run_lane(), 0)
            self.assertEqual(len(self.argv_calls()), index, f"stale provenance {provenance} must rerun")
            self.assertEqual(json.loads(out_path.read_text(encoding="utf-8"))["provenance"], current)
        self.assertTrue(codex_lane.existing_output_is_valid(out_path, "foundation", "native-clients",
                                                             packet_sha256, current))

    def test_a_return_with_an_unknown_or_other_model_reruns_instead_of_being_skipped(self):
        """Round-2 review: a return whose model.name is "unknown", or differs from --model, was skipped."""
        packet_path = self.write_packet("foundation", "native-clients")
        packet_sha256 = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        current = codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo)
        out_path = self.out_path("foundation", "native-clients")
        out_path.parent.mkdir()

        def write(name):
            # At the lane's own default effort, so the model rule is the only thing that can force the rerun.
            out_path.write_text(json.dumps(canned_return(
                packet_sha256=packet_sha256, provenance=current,
                model={"name": name, "effort": codex_lane.DEFAULT_EFFORT, "family": "openai"})), encoding="utf-8")

        write("unknown")
        self.assertEqual(self.run_lane(), 0)
        self.assertEqual(len(self.argv_calls()), 1, "an unknown model reruns")
        self.assertEqual(json.loads(out_path.read_text(encoding="utf-8"))["model"]["name"], "gpt-6-astra")
        write("gpt-6-astra")
        self.assertEqual(self.run_lane(["--model", "gpt-6-codex"]), 0)
        self.assertEqual(len(self.argv_calls()), 2, "a return from another model than --model reruns")
        self.assertEqual(json.loads(out_path.read_text(encoding="utf-8"))["model"]["name"], "gpt-6-codex")
        self.assertEqual(self.run_lane(["--model", "gpt-6-codex"]), 0)
        self.assertEqual(len(self.argv_calls()), 2, "a return from the configured model is skipped")

    def test_timeout_handling_retries_once_then_fails(self):
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_SLEEP_SECONDS"] = "2"

        exit_code = self.run_lane(["--timeout", "1"])
        self.assertEqual(exit_code, 1, "both attempts time out, so the layer must be reported failed")

        calls = self.argv_calls()
        self.assertEqual(len(calls), 2, "expected exactly one retry after the first timeout")

        rows = self.usage_rows()
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertTrue(row["timed_out"])
            self.assertIsNone(row["exit_code"])

        self.assertFalse(self.out_path("foundation", "native-clients").exists())
        # Review of catalog #122, finding 7: the failure and its reason reach record_verdicts.py's
        # run manifest through codex/failures.json instead of a bare "missing".
        failures_path = self.out_path("foundation", "native-clients").parent / "failures.json"
        failures = json.loads(failures_path.read_text(encoding="utf-8"))
        self.assertEqual(failures["failures"], [{"catalog": "foundation", "layer_id": "native-clients",
                                                 "reason": "failed after retry: timed out"}])

    def test_a_failed_rerun_removes_the_stale_return_for_an_older_packet(self):
        # Review of catalog #124 (codex_lane.py:482): a stale return rejected for an older packet
        # hash must not survive a failed rerun, or record_verdicts.py records `rejected`, not `failed`.
        self.write_packet("foundation", "native-clients")
        codex_dir = self.work_dir / "codex"
        codex_dir.mkdir()
        stale = self.out_path("foundation", "native-clients")
        stale.write_text(json.dumps(canned_return(packet_sha256="f" * 64), sort_keys=True, indent=1) + "\n",
                         encoding="utf-8")
        os.environ["CODEX_FAKE_FAIL_ATTEMPTS"] = "1,2"
        os.environ["CODEX_FAKE_EXIT_CODE"] = "7"
        self.assertEqual(self.run_lane(), 1)
        self.assertEqual(len(self.argv_calls()), 2, "the stale return must not be skipped as valid")
        self.assertFalse(stale.exists())
        failures = json.loads((codex_dir / "failures.json").read_text(encoding="utf-8"))
        self.assertEqual(failures["failures"], [{"catalog": "foundation", "layer_id": "native-clients",
                                                 "reason": "failed after retry: codex exec exited 7"}])

    def test_a_layers_rerun_keeps_the_failures_of_unselected_layers(self):
        # Codex review of #145 at a4dfd99e: a --layers rerun replaced failures.json with its own subset.
        self.write_packet("foundation", "native-clients")
        self.write_packet("foundation", "workers")
        codex_dir = self.work_dir / "codex"
        codex_dir.mkdir()
        (codex_dir / "failures.json").write_text(json.dumps({"lane": "codex", "failures": [
            {"catalog": "foundation", "layer_id": "workers", "reason": "failed after retry: timed out"},
            {"catalog": "foundation", "layer_id": "native-clients", "reason": "failed after retry: timed out"}]}),
            encoding="utf-8")
        self.assertEqual(self.run_lane(["--layers", "native-clients"]), 0)
        failures = json.loads((codex_dir / "failures.json").read_text(encoding="utf-8"))["failures"]
        self.assertEqual(failures, [{"catalog": "foundation", "layer_id": "workers",
                                     "reason": "failed after retry: timed out"}])

    def test_timed_out_attempt_keeps_its_partial_event_stream(self):
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_SLEEP_SECONDS"] = "3"
        os.environ["CODEX_FAKE_EMIT_BEFORE_SLEEP"] = "1"

        self.assertEqual(self.run_lane(["--timeout", "1"]), 1)
        events_path = self.work_dir / "codex" / "events" / "foundation__native-clients.jsonl"
        self.assertTrue(events_path.exists())
        captured = events_path.read_text(encoding="utf-8")
        partial_payload = CANNED_EVENTS.strip().splitlines()[2]
        self.assertIn(partial_payload, captured, "partial output of a timed-out attempt must be kept, not discarded")
        threads = [event["thread_id"] for event in codex_lane.parse_events(captured)
                   if event.get("type") == "thread.started"]
        self.assertEqual(len(threads), 2)
        self.assertEqual(len(set(threads)), 2, "each timed-out child retains its own native thread identity")

    def test_layers_filter_only_runs_the_selected_layer(self):
        self.write_packet("foundation", "layer-a")
        self.write_packet("foundation", "layer-b")
        self.return_file.write_text(json.dumps(canned_return(layer_id="layer-a")), encoding="utf-8")

        exit_code = self.run_lane(["--layers", "layer-a"])
        self.assertEqual(exit_code, 0)
        self.assertTrue(self.out_path("foundation", "layer-a").exists())
        self.assertFalse(self.out_path("foundation", "layer-b").exists())
        self.assertEqual(len(self.argv_calls()), 1)

    def test_stale_out_tmp_is_cleared_before_each_attempt(self):
        # A stale <catalog>__<layer>.out.tmp left behind by a prior killed
        # run (SIGKILL / Ctrl-C / OOM) must never be misread as *this*
        # attempt's own output; codex_lane.py must clear it before launching
        # the attempt, not only after detecting a failure.
        self.write_packet("foundation", "native-clients")
        codex_dir = self.work_dir / "codex"
        codex_dir.mkdir(parents=True)
        tmp_out = codex_dir / "foundation__native-clients.out.tmp"
        stale_payload = canned_return(why_selected=(
            "STALE leftover from a killed prior run; this text must never be read as a real result."
        ))
        tmp_out.write_text(json.dumps(stale_payload), encoding="utf-8")

        # Attempt 1's fake codex exits 0 but never touches -o at all; a
        # correct implementation must not find the stale file still there
        # and treat it as attempt 1's own output.
        os.environ["CODEX_FAKE_SKIP_OUTPUT_ATTEMPTS"] = "1"

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(self.argv_calls()), 2,
                          "attempt 1 must be treated as failed (stale file cleared first), forcing a retry")

        out_path = self.out_path("foundation", "native-clients")
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertNotIn("STALE", data["why_selected"], "the stale leftover out.tmp must never be read as a result")
        self.assertFalse(tmp_out.exists())

    def test_missing_output_file_retries_then_succeeds(self):
        # Attempt 1 exits 0 (a "successful" codex run) but never writes the
        # -o file at all; codex_lane.py must treat that as a failed attempt,
        # retry, and succeed on attempt 2's normal canned return.
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_SKIP_OUTPUT_ATTEMPTS"] = "1"

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)

        calls = self.argv_calls()
        self.assertEqual(len(calls), 2, "expected exactly one retry after the missing-output attempt")

        rows = self.usage_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["exit_code"], 0)
        self.assertEqual(rows[1]["exit_code"], 0)

        out_path = self.out_path("foundation", "native-clients")
        self.assertTrue(out_path.exists())
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(data["lane"], "codex")

    def test_missing_output_file_both_attempts_fails(self):
        # Both attempts exit 0 but never write -o: the layer must be
        # reported failed, main() must return 1, and nothing must be
        # written for that layer (resumable: a later run retries it).
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_SKIP_OUTPUT_ATTEMPTS"] = "1,2"

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 1)

        calls = self.argv_calls()
        self.assertEqual(len(calls), 2, "expected exactly one retry after the first missing-output attempt")

        out_path = self.out_path("foundation", "native-clients")
        self.assertFalse(out_path.exists())
        tmp_out = self.work_dir / "codex" / "foundation__native-clients.out.tmp"
        self.assertFalse(tmp_out.exists(), "no stale out.tmp should be left behind")

    def test_unparseable_output_both_attempts_fails(self):
        # Both attempts exit 0 but write text that fails json.loads
        # (JSONDecodeError) to -o: same failed-layer contract as a missing
        # file.
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_BAD_OUTPUT_ATTEMPTS"] = "1,2"
        os.environ["CODEX_FAKE_BAD_OUTPUT_TEXT"] = "not json at all {{{"

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 1)
        self.assertEqual(len(self.argv_calls()), 2)
        self.assertFalse(self.out_path("foundation", "native-clients").exists())
        tmp_out = self.work_dir / "codex" / "foundation__native-clients.out.tmp"
        self.assertFalse(tmp_out.exists(), "the unparseable out.tmp must be cleaned up, not left behind")

    def test_non_dict_output_retries_then_fails(self):
        # Both attempts exit 0 and write *valid* JSON to -o, but it is not a
        # JSON object (a bare list here) -- must be rejected the same as
        # missing/unparseable output, not accepted because json.loads
        # succeeded.
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_BAD_OUTPUT_ATTEMPTS"] = "1,2"
        os.environ["CODEX_FAKE_BAD_OUTPUT_TEXT"] = json.dumps(["not", "a", "dict"])

        exit_code = self.run_lane()
        self.assertEqual(exit_code, 1)
        self.assertEqual(len(self.argv_calls()), 2, "expected exactly one retry after a non-dict output attempt")
        self.assertFalse(self.out_path("foundation", "native-clients").exists())

    def test_usage_jsonl_rows_accumulate_across_layers(self):
        self.write_packet("foundation", "layer-a")
        self.write_packet("foundation", "layer-b")
        self.return_file.write_text(json.dumps(canned_return(layer_id="layer-a")), encoding="utf-8")
        # Both layers share the same canned return content object at the
        # filesystem level (the fake codex just copies bytes); layer_id
        # mismatches inside the payload are not validated by codex_lane.py
        # itself (that is record_verdicts.py's job), so this only exercises
        # that a usage row is appended per attempt per layer.
        exit_code = self.run_lane()
        self.assertEqual(exit_code, 0)
        rows = self.usage_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["layer"] for row in rows}, {"layer-a", "layer-b"})
        for row in rows:
            self.assertEqual(row["attempt"], 1)
            self.assertEqual(row["exit_code"], 0)



class StrictSchemaTests(CodexLaneFixture):
    def test_strict_copy_drops_keywords_codex_rejects_and_keeps_the_rest(self):
        schema = {"$schema": "x", "type": "object", "additionalProperties": False,
                  "properties": {"keys": {"type": "array", "uniqueItems": True, "minItems": 1,
                                          "items": {"type": "string", "pattern": "^c"}}},
                  "required": ["keys"]}
        strict = codex_lane.strict_output_schema(schema)
        self.assertNotIn("$schema", strict)
        self.assertNotIn("uniqueItems", strict["properties"]["keys"])
        self.assertEqual(strict["properties"]["keys"]["minItems"], 1)
        self.assertEqual(strict["properties"]["keys"]["items"]["pattern"], "^c")
        self.assertFalse(strict["additionalProperties"])

    def test_the_real_lane_schema_has_no_rejected_keyword_after_stripping(self):
        text = json.dumps(codex_lane.strict_output_schema(json.loads(codex_lane.DEFAULT_SCHEMA.read_text())))
        for keyword in codex_lane.STRICT_UNSUPPORTED_KEYWORDS:
            self.assertNotIn('"' + keyword + '"', text)

    def test_the_strict_schema_leaves_runner_owned_fields_to_the_runner(self):
        # provenance and model.family are written by codex_lane.py itself; Codex strict output
        # also requires every listed property to be required, so they are not asked of the model.
        strict = codex_lane.strict_output_schema(json.loads(codex_lane.DEFAULT_SCHEMA.read_text()))
        self.assertNotIn("provenance", strict["properties"])
        self.assertNotIn("family", strict["properties"]["model"]["properties"])
        # The Claude lane's refutation summary (review of catalog #122, finding 5) is never asked of Codex.
        self.assertIn("refutation", json.loads(codex_lane.DEFAULT_SCHEMA.read_text())["properties"])
        self.assertNotIn("refutation", strict["properties"])
        self.assertEqual(set(strict["properties"]), set(strict["required"]))
        self.assertEqual(set(strict["properties"]["model"]["properties"]), set(strict["properties"]["model"]["required"]))

    def test_codex_exec_receives_the_strict_schema(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        argv = self.argv_calls()[0]
        schema_arg = argv[argv.index("--output-schema") + 1]
        self.assertTrue(schema_arg.endswith("lane-return.codex-strict.schema.json"))
        self.assertTrue(Path(schema_arg).exists())

    def test_property_names_that_match_dropped_keywords_are_kept(self):
        schema = {"type": "object", "additionalProperties": False, "required": ["title", "description"],
                  "properties": {"title": {"type": "string", "description": "dropped"},
                                 "description": {"type": "string", "title": "dropped"}},
                  "$defs": {"$id": {"type": "string", "uniqueItems": True}}}
        strict = codex_lane.strict_output_schema(schema)
        self.assertEqual(strict["properties"], {"title": {"type": "string"}, "description": {"type": "string"}})
        self.assertEqual(strict["required"], ["title", "description"])
        self.assertEqual(strict["$defs"], {"$id": {"type": "string"}})

    def test_property_dependencies_keep_their_names(self):
        schema = {"type": "object", "dependentRequired": {"title": ["description"]},
                  "dependencies": {"title": ["$id"], "description": {"required": ["title"], "title": "dropped"}}}
        strict = codex_lane.strict_output_schema(schema)
        self.assertEqual(strict["dependentRequired"], {"title": ["description"]})
        self.assertEqual(strict["dependencies"], {"title": ["$id"], "description": {"required": ["title"]}})

    def test_instance_data_keywords_are_kept_verbatim(self):
        schema = {"type": "object", "const": {"title": "x"}, "default": {"description": "y"},
                  "enum": [{"$id": "z"}], "examples": [{"uniqueItems": True}]}
        strict = codex_lane.strict_output_schema(schema)
        for keyword in ("const", "default", "enum", "examples"):
            self.assertEqual(strict[keyword], schema[keyword])

    def test_dry_run_writes_no_strict_schema(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(["--dry-run"]), 0)
        self.assertFalse(any(self.work_dir.rglob("lane-return.codex-strict.schema.json")))


class PromptFillTests(CodexLaneFixture):
    """The prompt that reaches ``codex exec`` is lane-prompt.md with every
    placeholder filled: PACKET_PATH absolute, REPO_ROOT, LANE=codex."""

    def test_prompt_placeholders_are_filled_from_the_template(self):
        packet = self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        calls = self.argv_calls()
        self.assertEqual(len(calls), 1)
        prompt = calls[0][-1]
        self.assertIn(str(packet.resolve()), prompt, "PACKET_PATH must be the absolute packet path")
        self.assertIn(str(self.repo), prompt, "REPO_ROOT must be the --repo root")
        self.assertIn("You are the codex lane", prompt, "LANE must be filled with codex")
        for marker in ("{PACKET_PATH}", "{REPO_ROOT}", "{LANE}"):
            self.assertNotIn(marker, prompt)


class BlindIsolationTests(CodexLaneFixture):
    """2026-09-23 re-record: every lane child ignores the user config and runs without hooks, in a real run
    and in the dry run's printed commands alike."""

    def test_every_attempt_ignores_the_user_config_and_hooks(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        argv = self.argv_calls()[0]
        overrides = [argv[index + 1] for index, arg in enumerate(argv) if arg == "-c"]
        self.assertIn("--ignore-user-config", argv)
        self.assertIn("features.hooks=false", overrides)
        self.assertIn("features.plugin_hooks=false", overrides)
        self.assertLess(argv.index("--ignore-user-config"), len(argv) - 1, "the flags precede the prompt")

    def test_the_dry_run_prints_the_same_flags(self):
        self.write_packet("foundation", "native-clients")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_lane(["--dry-run"]), 0)
        self.assertIn("--ignore-user-config -c features.hooks=false -c features.plugin_hooks=false", out.getvalue())

    def test_native_web_search_is_off(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        argv = self.argv_calls()[0]
        self.assertIn('web_search="disabled"', [argv[index + 1] for index, arg in enumerate(argv) if arg == "-c"])

    def test_a_repository_with_git_history_is_refused_unless_allowed(self):
        self.write_packet("foundation", "native-clients")
        (self.repo / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(self.run_lane(), 2)
        self.assertIn("--export copy", err.getvalue())
        self.assertFalse(self.argv_log.exists())
        self.assertEqual(self.run_lane(["--allow-git-history"]), 0)

    def test_a_repository_inside_another_repository_is_refused(self):
        self.write_packet("foundation", "native-clients")
        (self.repo.parent / ".git").mkdir()
        nested = self.repo / "export"
        nested.mkdir()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(codex_lane.main(["--work-dir", str(self.work_dir), "--repo", str(nested),
                                              "--prompt", str(FIXTURE_PROMPT), "--schema", str(FIXTURE_SCHEMA)]), 2)
        self.assertFalse(self.argv_log.exists())

    def test_the_blind_audit_reports_what_a_child_reached_outside_the_boundary(self):
        self.write_packet("foundation", "native-clients")
        def done(item):
            return json.dumps({"type": "item.completed", "item": item})
        self.events_file.write_text("\n".join([
            done({"type": "command_execution", "command": f"/bin/bash -lc 'sed -n 1,40p {self.repo}/catalogs/x.json'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'rg -n verdict /home/example/code/agent-lab/docs'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'git log -p -- catalogs'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'rg -n verdict ~/code/agent-lab/docs/tasks'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'cat $HOME/code/agent-lab/docs/x.md'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'rg verdict ../../agent-lab/docs'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'sqlite3 db.sqlite .dump'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'cd /; rg -l verdict home'"}),
            done({"type": "command_execution", "command": "/bin/bash -lc 'sed -n 1,20p catalogs/landscape/foundation.json'"}),
            done({"type": "web_search", "query": "x"}),
            done({"type": "mcp_tool_call", "server": "s", "tool": "t"}),
        ]) + "\n" + CANNED_EVENTS, encoding="utf-8")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            # A flagged blind layer is void (Codex review of #145 at a516c477): exit 1, return set aside.
            self.assertEqual(self.run_lane(), 1)
        self.assertFalse((self.work_dir / "codex" / "foundation__native-clients.json").exists())
        self.assertTrue((self.work_dir / "codex" / "foundation__native-clients.json.audit-flagged").exists())
        failures = json.loads((self.work_dir / "codex" / "failures.json").read_text(encoding="utf-8"))["failures"]
        self.assertIn("blind audit flagged", failures[0]["reason"])
        audit = json.loads((self.work_dir / "codex" / "blind-audit.json").read_text(encoding="utf-8"))
        entry = audit["layers"]["foundation__native-clients"]
        self.assertEqual((entry["web_search"], entry["mcp_tool_calls"], entry["commands"]), (1, 1, 9))
        flagged = {item["command"]: item["reasons"] for item in entry["flagged_commands"]}
        # Exec JSONL does not retain native cwd; even otherwise approved operands require that evidence.
        self.assertEqual(len(flagged), 9, flagged)
        self.assertTrue(all(any("working directory unverified" in reason for reason in reasons)
                            for reasons in flagged.values()), flagged)
        joined = " ".join(reason for reasons in flagged.values() for reason in reasons)
        for expected in ("home-relative path: ~/code/agent-lab/docs/tasks", "home-relative path: $HOME/code/agent-lab/docs/x.md",
                         "path climbs out of the working directory: ../../agent-lab/docs", "runs sqlite3",
                         "names the filesystem root /"):
            self.assertIn(expected, joined)
        self.assertTrue(any("path outside the repository and packets: /home/example/code/agent-lab/docs" in reason
                            for reasons in flagged.values() for reason in reasons))
        self.assertTrue(any("runs git" in reasons for reasons in flagged.values()))
        self.assertIn("blind audit flags 1 layer(s)", err.getvalue())

    def audit_paths(self, *commands):
        events = self.work_dir / "audit-events.jsonl"
        events.write_text("".join(json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": command}}) + "\n" for command in commands), encoding="utf-8")
        report = audit_with_fixture_cwd(events, [str(self.repo), str(self.work_dir / "packets")])
        return {item["command"]: [reason.split(": ", 1)[1] for reason in item["reasons"]
                                  if reason.startswith("path outside")]
                for item in report["flagged_commands"]}

    def test_only_a_segment_executable_under_a_system_prefix_is_exempt(self):
        """PR #141 review (P2): every /usr/ or /bin/ path was exempt, which hid data reads such as
        /bin/cat /usr/local/share/prior-verdict.json."""
        repo = self.repo
        flagged = self.audit_paths(
            "/bin/cat /usr/local/share/prior-verdict.json",
            "/bin/bash -lc '/usr/bin/sed -n 1,20p /usr/share/doc/verdicts.txt'",
            f"/bin/bash -lc 'cat {repo}/a.json | /usr/bin/head -5 && /usr/bin/python3 {repo}/x.py || /bin/true; /usr/bin/wc -l {repo}/b'",
            f"/bin/bash -lc 'rg -n x {repo} 2>/dev/null'",
            "/bin/bash -lc 'cat /bin/prior-verdicts'",
            "/bin/bash -lc \"ls /usr/local/lib/verdicts\"",
            "/bin/sh -c '/home/example/bin/tool --flag'",
            "/usr/bin/env python3 -c 'print(1)'",
        )
        self.assertEqual(flagged, {
            "/bin/cat /usr/local/share/prior-verdict.json": ["/usr/local/share/prior-verdict.json"],
            "/bin/bash -lc '/usr/bin/sed -n 1,20p /usr/share/doc/verdicts.txt'": ["/usr/share/doc/verdicts.txt"],
            "/bin/bash -lc 'cat /bin/prior-verdicts'": ["/bin/prior-verdicts"],
            "/bin/bash -lc \"ls /usr/local/lib/verdicts\"": ["/usr/local/lib/verdicts"],
            "/bin/sh -c '/home/example/bin/tool --flag'": ["/home/example/bin/tool"],
        })

    def audit_reasons(self, command):
        events = self.work_dir / "audit-events.jsonl"
        events.write_text(json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": command}}) + "\n", encoding="utf-8")
        report = audit_with_fixture_cwd(events, [str(self.repo), str(self.work_dir / "packets")])
        return [reason for item in report["flagged_commands"] for reason in item["reasons"]]

    def test_round_two_audit_gaps_are_flagged(self):
        """Round-2 review: cd to an unnamed directory, non-HOME variable paths and a /usr/ executable outside
        the executable directories were not flagged."""
        expected = {
            "/bin/bash -lc 'cd'": "cd leaves for an unnamed directory: cd (home)",
            "cd": "cd leaves for an unnamed directory: cd (home)",
            "/bin/bash -lc 'cd -'": "cd leaves for an unnamed directory: cd -",
            "/bin/bash -lc 'cd ~ && rg verdict'": "cd leaves for an unnamed directory: cd ~",
            "/bin/bash -lc 'cd $OLDPWD'": "cd leaves for an unnamed directory: cd $OLDPWD",
            "/bin/bash -lc 'cd \"$OLDPWD\"; ls'": "cd leaves for an unnamed directory: cd $OLDPWD",
            "/bin/bash -lc 'cat $CODEX_HOME/AGENTS.md'": "variable path: $CODEX_HOME/AGENTS.md",
            "/bin/bash -lc 'ls ${XDG_DATA_HOME}/x'": "variable path: ${XDG_DATA_HOME}/x",
            "/bin/bash -lc '/usr/local/share/verdicts/show'":
                "path outside the repository and packets: /usr/local/share/verdicts/show",
            "/bin/bash -lc '/usr/lib/verdicts/show --all'":
                "path outside the repository and packets: /usr/lib/verdicts/show",
        }
        for command, reason in expected.items():
            self.assertIn(reason, self.audit_reasons(command), command)
        self.assertIn("working directory changed by cd; command unverified",
                      self.audit_reasons("/bin/bash -lc 'cd catalogs && ls'"))
        for command in ("/usr/local/bin/rg -n x catalogs",
                        "/usr/sbin/tool x", "/sbin/tool x", "/bin/bash -lc 'cat a; cat b'"):
            self.assertEqual(self.audit_reasons(command), [], command)
        # The parser cannot resolve an iteration variable into a bounded read operand.
        self.assertTrue(self.audit_reasons("/bin/bash -lc 'for f in a b; do cat $f; done'"))



class LiteralBoundaryRegressionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.repo = self.base / "export"
        self.packets = self.base / "packets"
        self.repo.mkdir()
        self.packets.mkdir()

    def audit_python(self, code):
        self.assertIsNone(codex_lane.audit_analysis_issue(), "literal tests require the verified parser")
        command = shlex.join(["/bin/bash", "-lc", "python3 -c " + shlex.quote(code)])
        events = self.base / "literal-events.jsonl"
        events.write_text(json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": command}}) + "\n", encoding="utf-8")
        return audit_with_fixture_cwd(events, [str(self.repo), str(self.packets)])

    def test_outside_literals_at_read_interfaces_do_not_depend_on_a_fixed_call_list(self):
        cases = {
            "linecache": "import linecache;linecache.getline('../codex/foundation__x.json',1)",
            "sqlite": "import sqlite3;sqlite3.connect('/var/lib/x')",
            "fileio": "import io;io.FileIO('/etc/passwd')",
            "fileinput": "import fileinput;fileinput.input(files='/etc/passwd')",
            "copyfile": "import shutil;shutil.copyfile('/etc/passwd','evidence/copy')",
            "getsize": "import os;os.path.getsize('/etc/passwd')",
            "pandas": "import pandas;pandas.read_json('/srv/x')",
            "walk_root": "import os;list(os.walk('/'))",
        }
        for interface, code in cases.items():
            with self.subTest(interface=interface):
                self.assertTrue(self.audit_python(code)["flagged_commands"], "an unproven outside literal must be refused")

    def test_proven_print_formatting_and_comparison_literals_remain_data(self):
        cases = [
            "print('/etc/passwd')",
            "print('/'.join(['a','b']))",
            "import json;print(json.dumps({'reference':'/etc/passwd'},indent=2))",
            "if '://' in 'file:///outside/file':\n print('external')",
        ]
        for code in cases:
            with self.subTest(data_use=code):
                self.assertEqual(self.audit_python(code)["flagged_commands"], [])

    def test_data_operations_do_not_prove_unknown_or_mutated_calls_safe(self):
        cases = [
            "import sqlite3;sqlite3.connect('/'.join(['','var','lib','x']))",
            "print=open;print('/etc/passwd')",
            "def print(value):\n return value\nprint('/etc/passwd')",
            "import json;setattr(json,'dumps',open);print(json.dumps('/etc/passwd'))",
            "import sqlite3;path='/var/lib/x';sqlite3.connect(path)",
        ]
        for code in cases:
            with self.subTest(unproven_use=code):
                self.assertTrue(self.audit_python(code)["flagged_commands"], "data must not launder an outside literal")

    def test_bytes_literals_at_read_interfaces_remain_subject_to_the_boundary(self):
        # CPython v3.13.16 filesystem APIs accept bytes paths. The command auditor
        # must inspect their AST constants before any payload could execute.
        cases = {
            "fileio": "import io;io.FileIO(b'../codex/foundation__x.json')",
            "getsize": "import os;os.path.getsize(b'/etc/passwd')",
            "copyfile": "import shutil;shutil.copyfile(b'/etc/passwd','evidence/copy')",
            "sqlite": "import sqlite3;sqlite3.connect(b'/var/lib/x.db')",
            "mixed_str_bytes": "import shutil;shutil.copyfile('evidence/input',b'/etc/passwd')",
            # These native APIs reject the wrappers, but an unsupported wrapper
            # must not hide its outside byte literal from conservative analysis.
            "bytearray": "import io;io.FileIO(bytearray(b'../codex/foundation__x.json'))",
            "memoryview": "import os;os.path.getsize(memoryview(b'/etc/passwd'))",
        }
        for interface, code in cases.items():
            with self.subTest(interface=interface):
                self.assertTrue(self.audit_python(code)["flagged_commands"],
                                "an outside byte literal must not bypass the command boundary")

    def test_printed_and_joined_bytes_literals_remain_data(self):
        for code in ("print(b'/etc/passwd')", "print(b'/'.join([b'evidence',b'receipt']))",
                     "print(b'/etc/passwd'.decode())", "print(b'/etc/passwd'.hex())",
                     "if b'://' in b'file:///synthetic/outside': print('external')"):
            with self.subTest(data_use=code):
                self.assertEqual(self.audit_python(code)["flagged_commands"], [])

    def test_bytes_decode_cannot_send_boundary_literals_to_codec_callbacks(self):
        self.install_reader_callbacks()
        cases = {
            "codec_search": "import codecs\nfrom reader_codec import search\n"
                            "codecs.register(search)\nprint(b'../outside-marker.txt'.decode('rd'))",
            "custom_error": "import codecs\nfrom reader_codec import handler\ncodecs.register_error('rd',handler)\n"
                            "print(b'../outside-marker.txt\\xff'.decode('utf-8','rd'))",
            "overridden_strict": "import codecs\nfrom reader_codec import handler\ncodecs.register_error('strict',handler)\n"
                                 "print(b'../outside-marker.txt\\xff'.decode())",
        }
        for case, code in cases.items():
            with self.subTest(callback=case):
                self.assert_callback_reads_fixture(code)
                self.assertTrue(self.audit_python(code)["flagged_commands"],
                                "decode must not carry outside bytes into registered codec callbacks")

    def test_unknown_comparison_dunders_do_not_receive_boundary_literals(self):
        self.install_reader_callbacks()
        cases = {
            "str_eq": "from reader_codec import P\n"
                      "print('../outside-marker.txt' == P())",
            "bytes_eq": "from reader_codec import P\n"
                        "print(b'../outside-marker.txt' == P())",
            "contains": "from reader_codec import P\n"
                        "print('../outside-marker.txt' in P())",
        }
        for case, code in cases.items():
            with self.subTest(callback=case):
                self.assert_callback_reads_fixture(code)
                self.assertTrue(self.audit_python(code)["flagged_commands"],
                                "unknown comparison dunders can receive the path literal")

    def install_reader_callbacks(self):
        # Only this temporary synthetic sibling is read; no system or user file is opened.
        (self.base / "outside-marker.txt").write_text("OUTSIDE_MARKER")
        (self.repo / "reader_codec.py").write_text(
            "import codecs\n"
            "def read(path):\n with open(path) as handle: print(handle.read())\n"
            "def decode(raw, errors='strict'):\n read(bytes(raw)); return ('read',len(raw))\n"
            "def search(name):\n return codecs.CodecInfo(name='rd',encode=None,decode=decode) if name=='rd' else None\n"
            "def handler(error):\n read(error.object[:-1]); return ('',len(error.object))\n"
            "class P:\n"
            " def __eq__(self,path):\n  read(path); return True\n"
            " def __contains__(self,path):\n  read(path); return True\n")

    def assert_callback_reads_fixture(self, code):
        result = subprocess.run([sys.executable, "-E", "-s", "-B", "-c", code], cwd=self.repo,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OUTSIDE_MARKER", result.stdout)


class NativeUsageSuffixTests(unittest.TestCase):
    def setUp(self):
        self.prefix = b'{"catalog":"foundation","layer":"previous","attempt":1,"exit_code":0}\n'
        self.native_bytes = (ROOT / "tests" / "fixtures" / "codex_lane_workers_native_usage.jsonl").read_bytes()
        self.native = json.loads(self.native_bytes)

    def test_the_real_native_workers_row_uses_layer_and_keeps_recorded_attempt_metadata(self):
        self.assertEqual(hashlib.sha256(self.native_bytes).hexdigest(),
                         "890024fb9b1387a0f53fddb9af5c9bb551dacbc855f46cd9dbb08c6e3ac0f13f")
        with self.subTest(boundary="native-layer-predicate"):
            self.assertTrue(codex_lane.usage_row_belongs_to_layer(self.native, "workers"))
        with self.subTest(boundary="appended-native-usage"):
            rows = codex_lane.layer_usage_suffix(self.prefix, self.prefix + self.native_bytes, "workers")
            self.assertEqual(rows, [self.native])
            self.assertEqual(rows[0]["seconds"], 358.707)
            self.assertEqual(rows[0]["exit_code"], 0)
            self.assertEqual(rows[0]["input_tokens"], 871007)
            self.assertEqual(rows[0]["cached_input_tokens"], 749568)
            self.assertEqual(rows[0]["output_tokens"], 16500)
            self.assertEqual(rows[0]["reasoning_output_tokens"], 6793)

    def test_a_changed_prefix_or_invalid_native_suffix_is_refused(self):
        invalid = {
            "changed-prefix": b"changed\n" + self.native_bytes,
            "legacy-layer-id-only": self.prefix + b'{"layer_id":"workers"}\n',
            "another-layer": self.prefix + b'{"layer":"other"}\n',
            "non-object": self.prefix + b'[]\n',
            "malformed-json": self.prefix + b'{invalid}\n',
            "partial-final-row": self.prefix + self.native_bytes.rstrip(b"\n"),
        }
        for case, current in invalid.items():
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    codex_lane.layer_usage_suffix(self.prefix, current, "workers")
        self.assertFalse(codex_lane.usage_row_belongs_to_layer({"layer_id": "workers"}, "workers"))
        self.assertFalse(codex_lane.usage_row_belongs_to_layer({"layer": "other"}, "workers"))

    def test_no_new_usage_rows_is_a_valid_stopped_run_observation(self):
        self.assertEqual(codex_lane.layer_usage_suffix(self.prefix, self.prefix, "workers"), [])


class ApprovedPacketSnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.packets = self.base / "packets"
        self.packets.mkdir()
        self.path = self.packets / "foundation__workers.json"
        self.packet_bytes = (ROOT / "tests" / "fixtures" / "codex_lane_approved_packet.json").read_bytes()
        self.packet = json.loads(self.packet_bytes)
        self.path.write_bytes(self.packet_bytes)
        self.recorded_hash(self.packet_bytes)

    def recorded_hash(self, data):
        (self.packets / "SHA256SUMS").write_text(hashlib.sha256(data).hexdigest() + "  foundation__workers.json\n",
                                                encoding="utf-8")

    def load(self, path=None, expected_sha256=None):
        return codex_lane._load_approved_packet_json(str(path or self.path), [str(self.packets)], expected_sha256)

    def test_a_snapshot_needs_a_recorded_or_explicit_matching_digest(self):
        self.assertEqual(self.load(), self.packet)
        (self.packets / "SHA256SUMS").unlink()
        self.assertIsNone(self.load())
        self.assertEqual(self.load(expected_sha256=hashlib.sha256(self.packet_bytes).hexdigest()), self.packet)
        self.assertIsNone(self.load(expected_sha256="0" * 64))

    def test_malformed_or_wrong_shaped_data_remains_unapproved(self):
        wrong = {**self.packet, "candidates": [{"adopted": "true", "evidence_refs": ["evidence/receipt.json"]}]}
        for data in (b"not-json", json.dumps(wrong).encode("utf-8")):
            with self.subTest(data_kind="malformed" if data == b"not-json" else "wrong-shape"):
                self.path.write_bytes(data)
                self.recorded_hash(data)
                self.assertIsNone(self.load())

    def test_an_oversized_valid_packet_remains_unapproved_even_with_a_matching_digest(self):
        data = json.dumps({**self.packet, "padding": "x" * (1024 * 1024)}).encode("utf-8")
        self.assertGreater(len(data), 1024 * 1024)
        self.path.write_bytes(data)
        self.recorded_hash(data)
        self.assertIsNone(self.load())

    def test_outside_symlinked_or_nonpacket_paths_remain_unapproved(self):
        outside = self.base / "foundation__workers.json"
        outside.write_bytes(self.packet_bytes)
        expected = hashlib.sha256(self.packet_bytes).hexdigest()
        self.assertIsNone(self.load(outside, expected))
        nonpacket = self.packets / "ordinary.json"
        nonpacket.write_bytes(self.packet_bytes)
        self.assertIsNone(self.load(nonpacket, expected))
        self.path.unlink()
        self.path.symlink_to(outside)
        self.assertIsNone(self.load(expected_sha256=expected))

    def test_checksum_and_ancestor_symlinks_do_not_approve_packet_data(self):
        expected = hashlib.sha256(self.packet_bytes).hexdigest()
        recorded = self.packets / "SHA256SUMS"
        outside_sums = self.base / "outside-sums"
        outside_sums.write_text(expected + "  foundation__workers.json\n", encoding="utf-8")
        recorded.unlink()
        recorded.symlink_to(outside_sums)
        self.assertIsNone(self.load())
        alias = self.base / "alias"
        alias.symlink_to(self.base, target_is_directory=True)
        alias_root = alias / "packets"
        self.assertIsNone(codex_lane._load_approved_packet_json(str(alias_root / self.path.name),
                                                              [str(alias_root)], expected))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO safety applies to POSIX packet descriptors")
    def test_fifo_or_hard_linked_packet_inputs_remain_unapproved(self):
        import sys

        expected = hashlib.sha256(self.packet_bytes).hexdigest()
        os.link(self.path, self.base / "linked-packet")
        self.assertIsNone(self.load(expected_sha256=expected))
        self.path.unlink()
        os.mkfifo(self.path)
        # Bound the probe so removing nonblocking opens produces a test failure rather than a hung suite.
        code = (
            "import importlib.util,sys;"
            "spec=importlib.util.spec_from_file_location('packet_loader_probe',sys.argv[1]);"
            "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
            "result=m._load_approved_packet_json(sys.argv[2],[sys.argv[3]],sys.argv[4]);"
            "print('refused' if result is None else 'approved')"
        )
        done = subprocess.run([sys.executable, "-B", "-c", code, str(TOOL_DIR / "codex_lane.py"), str(self.path),
                               str(self.packets), expected], capture_output=True, text=True, timeout=5)
        self.assertEqual(done.returncode, 0, "the bounded FIFO refusal probe failed")
        self.assertEqual(done.stdout.strip(), "refused")


class BlindAuditQuarantineRegressionTests(unittest.TestCase):
    """Replay only retained tool command metadata from the three tier-1 quarantines; execute no command."""

    def setUp(self):
        self.fixture = json.loads((ROOT / "tests" / "fixtures" / "codex_lane_blind_audit_quarantines.json")
                                  .read_text(encoding="utf-8"))

    def audit_command(self, command):
        self.assertIsNone(codex_lane.audit_analysis_issue(), "regression cases require a verified audit parser")
        with tempfile.TemporaryDirectory() as temporary:
            events = Path(temporary) / "events.jsonl"
            events.write_text(json.dumps({"type": "item.completed", "item": {
                "type": "command_execution", "command": command}}) + "\n", encoding="utf-8")
            return audit_with_fixture_cwd(events, self.fixture["allowed_roots"])

    def assert_case_is_clean(self, layer):
        report = self.audit_command(self.fixture["cases"][layer]["command"])
        self.assertEqual((report["commands"], report["web_search"], report["mcp_tool_calls"]), (1, 0, 0))
        self.assertEqual(report["flagged_commands"], [], report["flagged_commands"])

    def test_document_retrieval_python_join_separator_is_not_a_root_read(self):
        self.assert_case_is_clean("document-retrieval")

    def test_git_github_automation_rg_pattern_is_not_git_execution(self):
        self.assert_case_is_clean("git-github-automation")

    def test_mcp_surfaces_backtick_literal_in_a_quoted_heredoc_is_not_substitution(self):
        self.assert_case_is_clean("mcp-surfaces")

    def test_workers_packet_reference_walk_is_clean(self):
        packet = json.loads((ROOT / "tests" / "fixtures" / "codex_lane_approved_packet.json").read_bytes())
        with mock.patch.object(codex_lane, "_load_approved_packet_json", return_value=packet, create=True):
            self.assert_case_is_clean("workers")

    def test_workers_reference_walk_rejects_outside_or_unapproved_json_paths(self):
        packet = json.loads((ROOT / "tests" / "fixtures" / "codex_lane_approved_packet.json").read_bytes())
        command = self.fixture["cases"]["workers"]["command"]
        for ref in ("/outside/file", "../outside"):
            unsafe = {**packet, "candidates": [{"adopted": True, "evidence_refs": [ref]}]}
            with self.subTest(outside_reference=ref), \
                    mock.patch.object(codex_lane, "_load_approved_packet_json", return_value=unsafe, create=True):
                self.assertTrue(self.audit_command(command)["flagged_commands"], "approved JSON cannot authorize outside reads")
        malformed = {**packet, "candidates": [{"adopted": True, "evidence_refs": [{"path": "/outside/file"}]}]}
        for unapproved in (None, malformed):
            with self.subTest(unapproved_data=unapproved is not None), \
                    mock.patch.object(codex_lane, "_load_approved_packet_json", return_value=unapproved, create=True):
                self.assertTrue(self.audit_command(command)["flagged_commands"], "an unapproved snapshot must remain unresolved")
        original = "/tmp/ns2604-tier1-codex-ready-20261010-OWFxvw/work/packets/foundation__workers.json"
        with mock.patch.object(codex_lane, "_load_approved_packet_json", return_value=packet, create=True):
            outside_packet = command.replace(original, "/outside/foundation__workers.json")
            self.assertTrue(self.audit_command(outside_packet)["flagged_commands"], "outside packet input must remain refused")

    def test_approved_json_uri_guards_and_aliases_do_not_authorize_other_reads(self):
        packet = json.loads((ROOT / "tests" / "fixtures" / "codex_lane_approved_packet.json").read_bytes())
        literal = "/tmp/ns2604-tier1-codex-ready-20261010-OWFxvw/work/packets/foundation__workers.json"
        prelude = "import json\nfrom pathlib import Path\np=json.loads(Path(" + repr(literal) + ").read_bytes())\n"
        cases = {
            "unguarded_local_uri": (
                {**packet, "candidates": [{"adopted": True, "evidence_refs": ["file:///outside/file"]}]},
                "for ref in p['candidates'][0]['evidence_refs']:\n    Path(ref).read_text()\n",
            ),
            "read_before_uri_guard": (
                {**packet, "candidates": [{"adopted": True, "evidence_refs": ["file:///outside/file"]}]},
                "for ref in p['candidates'][0]['evidence_refs']:\n"
                "    Path(ref).read_text()\n    if '://' in ref:\n        continue\n",
            ),
            "read_inside_uri_guard": (
                {**packet, "candidates": [{"adopted": True, "evidence_refs": ["file:///outside/file"]}]},
                "for ref in p['candidates'][0]['evidence_refs']:\n"
                "    if '://' in ref:\n        Path(ref).read_text()\n",
            ),
            "reference_rebound_after_guard": (
                packet,
                "for ref in p['candidates'][0]['evidence_refs']:\n"
                "    if '://' in ref:\n        continue\n"
                "    ref='/outside/file'\n    Path(ref).read_text()\n",
            ),
            "packet_alias_mutation": (
                packet,
                "q=p\nq['candidates'][0]['evidence_refs']=['/outside/file']\n"
                "for ref in p['candidates'][0]['evidence_refs']:\n    Path(ref).read_text()\n",
            ),
            "bound_callback_alias_mutation": (
                packet,
                "getter=p.get\nq=getter('candidates')\nq[0]['evidence_refs']=['/outside/file']\n"
                "for ref in p['candidates'][0]['evidence_refs']:\n    Path(ref).read_text()\n",
            ),
            "reference_set_mutation": (
                packet,
                "refs={r for c in p['candidates'] if c['adopted'] for r in c['evidence_refs']}\n"
                "refs.add('/outside/file')\nfor ref in refs:\n    Path(ref).read_text()\n",
            ),
            "unknown_packet_callback": (
                packet,
                "mutate(p)\nfor ref in p['candidates'][0]['evidence_refs']:\n    Path(ref).read_text()\n",
            ),
            "local_return_alias_mutation": (
                packet,
                "def escape():\n    return p\nq=escape()\nq['candidates'][0]['evidence_refs']=['/outside/file']\n"
                "for ref in p['candidates'][0]['evidence_refs']:\n    Path(ref).read_text()\n",
            ),
            "stdlib_decoder_rebound_before_packet_load": (
                packet,
                "setattr(json,'loads',lambda _: {'candidates':[{'adopted':True,'evidence_refs':['/outside/file']}]})\n"
                "p=json.loads(Path(" + repr(literal) + ").read_bytes())\n"
                "for ref in p['candidates'][0]['evidence_refs']:\n    Path(ref).read_text()\n",
            ),
        }
        for case, (snapshot, body) in cases.items():
            with self.subTest(case=case), \
                    mock.patch.object(codex_lane, "_load_approved_packet_json", return_value=snapshot, create=True):
                initial = "import json\nfrom pathlib import Path\n" if case == "stdlib_decoder_rebound_before_packet_load" else prelude
                script = "python3 - <<'PY'\n" + initial + body + "PY"
                command = shlex.join(["/bin/bash", "-lc", script])
                self.assertTrue(self.audit_command(command)["flagged_commands"], "approved input must not authorize an outside read")
        guarded = {**packet, "candidates": [{"adopted": True,
                                            "evidence_refs": ["evidence/receipt.json", "file:///outside/file"]}]}
        body = ("for ref in p['candidates'][0]['evidence_refs']:\n"
                "    path=Path(ref)\n    if '://' in ref:\n        continue\n    path.stat()\n")
        with mock.patch.object(codex_lane, "_load_approved_packet_json", return_value=guarded, create=True):
            command = shlex.join(["/bin/bash", "-lc", "python3 - <<'PY'\n" + prelude + body + "PY"])
            self.assertEqual(self.audit_command(command)["flagged_commands"], [],
                             "the dominated read uses only local values even when its alias precedes the guard")

    def test_an_actual_python_root_read_remains_flagged(self):
        report = self.audit_command("/bin/bash -lc \"python3 - <<'PY'\nfrom pathlib import Path\n"
                                    "print(list(Path('/').iterdir()))\nPY\"")
        self.assertTrue(report["flagged_commands"])
        self.assertTrue(any("filesystem root" in reason for row in report["flagged_commands"]
                            for reason in row["reasons"]), report["flagged_commands"])

    def test_python_alias_keyword_attribute_and_indirect_reads_remain_flagged(self):
        cases = {
            "open_alias": "reader=open;reader('/etc/passwd')",
            "rebound_print": "print=open;print('/etc/passwd')",
            "open_keyword": "open(file='/etc/passwd')",
            "listdir_keyword": "import os;os.listdir(path='/')",
            "urlopen_keyword": "from urllib.request import urlopen;urlopen(url='file:///etc/passwd')",
            "path_parent_glob": "from pathlib import Path;Path('/etc/passwd').parent.glob('*')",
            "path_getattr": "from pathlib import Path;getattr(Path('/etc/passwd'),'read_text')()",
            "readlink": "import os;os.readlink('/etc/passwd')",
        }
        for name, code in cases.items():
            with self.subTest(operation=name):
                shell = "python3 -c " + shlex.quote(code)
                command = shlex.join(["/bin/bash", "-lc", shell])
                report = self.audit_command(command)
                self.assertTrue(report["flagged_commands"], "an outside read must be flagged")

    def test_pattern_and_filter_file_options_audit_the_file_argument(self):
        for tool, long_option in (("rg", "--file"), ("grep", "--file"), ("jq", "--from-file")):
            for option, attached in (("-f", False), ("-f", True), (long_option, False), (long_option, True)):
                with self.subTest(tool=tool, option=option, attached=attached):
                    if attached:
                        arguments = [option + ("=" if option.startswith("--") else "") + "/etc/passwd"]
                    else:
                        arguments = [option, "/etc/passwd"]
                    argv = [tool, *arguments, "evidence/input.json"]
                    command = shlex.join(["/bin/bash", "-lc", shlex.join(argv)])
                    self.assertTrue(self.audit_command(command)["flagged_commands"],
                                    "a pattern/filter file outside the export must be flagged")
                    safe_argv = [argument.replace("/etc/passwd", "evidence/filter.txt") for argument in argv]
                    safe = shlex.join(["/bin/bash", "-lc", shlex.join(safe_argv)])
                    self.assertEqual(self.audit_command(safe)["flagged_commands"], [])

    def test_nested_python_subprocess_wrappers_audit_the_executed_command(self):
        cases = [
            (["sh", "-c", "git log"], ["sh", "-c", "rg -n x evidence"]),
            (["bash", "-lc", "printenv"], ["bash", "-lc", "printf '%s\\n' literal"]),
            (["nice", "git", "log"], ["nice", "rg", "-n", "x", "evidence"]),
        ]
        for unsafe_argv, safe_argv in cases:
            with self.subTest(argv=unsafe_argv):
                code = "import subprocess;subprocess.run(" + repr(unsafe_argv) + ")"
                unsafe = shlex.join(["/bin/bash", "-lc", "python3 -c " + shlex.quote(code)])
                self.assertTrue(self.audit_command(unsafe)["flagged_commands"],
                                "nested shell/wrapper execution must retain the blind audit")
                code = "import subprocess;subprocess.run(" + repr(safe_argv) + ")"
                safe = shlex.join(["/bin/bash", "-lc", "python3 -c " + shlex.quote(code)])
                self.assertEqual(self.audit_command(safe)["flagged_commands"], [])

    def test_python_os_open_parent_glob_and_alias_concat_read_paths(self):
        cases = {
            "os_open": "import os;os.open('/etc/passwd',os.O_RDONLY)",
            "parent_glob": "from pathlib import Path;list(Path('.').glob('../outside'))",
            "alias_concat": "reader=open;prefix='/etc/';reader(prefix+'passwd')",
        }
        for name, code in cases.items():
            with self.subTest(operation=name):
                command = shlex.join(["/bin/bash", "-lc", "python3 -c " + shlex.quote(code)])
                self.assertTrue(self.audit_command(command)["flagged_commands"], "an outside read must be flagged")
        safe_code = "reader=open;prefix='evidence/';reader(prefix+'receipt.json')"
        safe = shlex.join(["/bin/bash", "-lc", "python3 -c " + shlex.quote(safe_code)])
        self.assertEqual(self.audit_command(safe)["flagged_commands"], [])

    def test_git_through_stdio_lock_and_session_wrappers_remains_flagged(self):
        # These executing wrappers are outside the supported grammar; both payloads must fail closed.
        wrappers = [["stdbuf", "-oL"], ["flock", "local.lock"], ["setsid"]]
        for wrapper in wrappers:
            with self.subTest(wrapper=wrapper[0]):
                command = shlex.join(["/bin/bash", "-lc", shlex.join([*wrapper, "git", "log"])])
                self.assertTrue(self.audit_command(command)["flagged_commands"], "the wrapper must retain git refusal")
                safe = shlex.join(["/bin/bash", "-lc", shlex.join([*wrapper, "rg", "-n", "x", "evidence"])])
                self.assertTrue(self.audit_command(safe)["flagged_commands"], "unsupported wrappers must fail closed")
        bare = shlex.join(["/bin/bash", "-lc", "rg -n x evidence"])
        self.assertEqual(self.audit_command(bare)["flagged_commands"], [])

    def test_python_end_of_options_stdin_retains_path_read_auditing(self):
        unsafe_script = "python3 -- - <<'PY'\nopen('/outside/file').read()\nPY"
        command = shlex.join(["/bin/bash", "-lc", unsafe_script])
        self.assertTrue(self.audit_command(command)["flagged_commands"], "Python stdin must retain outside-read refusal")
        safe_script = "python3 -- - <<'PY'\nopen('evidence/receipt.json').read()\nPY"
        safe = shlex.join(["/bin/bash", "-lc", safe_script])
        self.assertEqual(self.audit_command(safe)["flagged_commands"], [])

    def test_a_quoted_heredoc_piped_to_a_shell_audits_the_executed_body(self):
        unsafe_script = "cat <<'SH' | sh\ngit log\nSH"
        command = shlex.join(["/bin/bash", "-lc", unsafe_script])
        self.assertTrue(self.audit_command(command)["flagged_commands"], "the receiving shell executes the heredoc")
        safe_script = "cat <<'SH'\ngit log\nSH"
        safe = shlex.join(["/bin/bash", "-lc", safe_script])
        self.assertEqual(self.audit_command(safe)["flagged_commands"], [])

    def test_python_namespace_read_aliases_and_path_metadata_reads_remain_flagged(self):
        cases = {
            "module_attribute_alias": "import os;os.reader=open;os.reader('/outside/file')",
            "namespace_attribute_alias": ("from types import SimpleNamespace;ns=SimpleNamespace();"
                                          "ns.reader=open;ns.reader('/outside/file')"),
            "path_is_symlink": "from pathlib import Path;Path('/outside/file').is_symlink()",
            "path_samefile_argument": ("from pathlib import Path;"
                                       "Path('evidence/receipt.json').samefile('/outside/file')"),
        }
        for name, code in cases.items():
            with self.subTest(operation=name):
                command = shlex.join(["/bin/bash", "-lc", "python3 -c " + shlex.quote(code)])
                self.assertTrue(self.audit_command(command)["flagged_commands"], "an outside read must be flagged")
        for code in ("from pathlib import Path;Path('evidence/receipt.json').is_symlink()",
                     "from pathlib import Path;Path('evidence/receipt.json').samefile('evidence/other.json')"):
            with self.subTest(local_metadata=code):
                safe = shlex.join(["/bin/bash", "-lc", "python3 -c " + shlex.quote(code)])
                self.assertEqual(self.audit_command(safe)["flagged_commands"], [])

    def test_opaque_interpreter_and_find_execution_remain_refused(self):
        cases = {
            "shell_stdin_pipe": "printf '%s\\n' 'git log' | sh",
            "node_code": shlex.join(["node", "-e", "require('child_process').execSync('git log')"]),
            "find_exec": shlex.join(["find", "evidence", "-exec", "git", "log", "{}", ";"]),
        }
        for name, script in cases.items():
            with self.subTest(operation=name):
                command = shlex.join(["/bin/bash", "-lc", script])
                self.assertTrue(self.audit_command(command)["flagged_commands"], "opaque command execution must fail closed")
        for script in ("printf '%s\\n' 'git log'", "find evidence -name 'git*'"):
            with self.subTest(literal_data=script):
                safe = shlex.join(["/bin/bash", "-lc", script])
                self.assertEqual(self.audit_command(safe)["flagged_commands"], [])


class CommandWorkingDirectoryTests(CodexLaneFixture):
    def audit_item(self, command, *, records=None, **fields):
        item = {"id": "fixture-command", "type": "command_execution", "command": command, **fields}
        self.events_file.write_text(json.dumps({"type": "item.completed", "item": item}) + "\n",
                                    encoding="utf-8")
        kwargs = {"cwd_records": records} if records is not None else {}
        return codex_lane.blind_audit(self.events_file, [str(self.repo), str(self.work_dir / "packets")], **kwargs)

    def test_missing_working_directory_is_unverified(self):
        report = self.audit_item("/bin/bash -lc 'cat catalogs/landscape/foundation.json'")
        self.assertTrue(codex_lane.audit_is_flagged(report))
        self.assertIn("working directory unverified", " ".join(report["flagged_commands"][0]["reasons"]))

    def test_model_chosen_outside_working_directory_is_refused(self):
        report = self.audit_item("/bin/bash -lc 'cat receipt.json'", cwd=str(self.repo.parent))
        self.assertTrue(codex_lane.audit_is_flagged(report))
        self.assertIn("working directory unverified", " ".join(report["flagged_commands"][0]["reasons"]))

    def test_recorded_approved_working_directory_binds_python_cwd(self):
        nested = self.repo / "nested"
        nested.mkdir()
        command = "/bin/bash -lc " + shlex.quote("python3 -c \"from pathlib import Path; (Path.cwd().parent / 'receipt.json').read_text()\"")
        records = {"fixture-command": {"command": command, "cwd": str(nested)}}
        report = self.audit_item(command, records=records)
        self.assertEqual(report["flagged_commands"], [])

    def test_outside_or_mismatched_independent_record_is_refused(self):
        command = "/bin/bash -lc 'cat receipt.json'"
        for record in ({"command": command, "cwd": str(self.repo.parent)},
                       {"command": "cat harmless.json", "cwd": str(self.repo)}):
            with self.subTest(record=record):
                report = self.audit_item(command, records={"fixture-command": record})
                self.assertTrue(codex_lane.audit_is_flagged(report))

    def test_shell_directory_change_requires_a_new_binding(self):
        command = "/bin/bash -lc " + shlex.quote("cd '" + str(self.repo) + "'; cat receipt.json")
        records = {"fixture-command": {"command": command, "cwd": str(self.repo)}}
        report = self.audit_item(command, records=records)
        self.assertTrue(codex_lane.audit_is_flagged(report))
        self.assertIn("working directory changed", " ".join(report["flagged_commands"][0]["reasons"]))

    def test_python_subprocess_cwd_override_is_unverified(self):
        source = "import subprocess; subprocess.run(['cat', 'receipt.json'], cwd=" + repr(str(self.repo)) + ")"
        command = "/bin/bash -lc " + shlex.quote("python3 -c " + shlex.quote(source))
        records = {"fixture-command": {"command": command, "cwd": str(self.repo)}}
        report = self.audit_item(command, records=records)
        self.assertTrue(codex_lane.audit_is_flagged(report))
        self.assertIn("working directory changed", " ".join(report["flagged_commands"][0]["reasons"]))

    def test_relative_or_conflicting_working_directory_is_unverified(self):
        for fields in ({"cwd": "nested"}, {"cwd": str(self.repo), "workdir": str(self.repo.parent)}):
            with self.subTest(fields=fields):
                report = self.audit_item("/bin/bash -lc 'cat receipt.json'", **fields)
                self.assertTrue(codex_lane.audit_is_flagged(report))


class BlindAuditBackendPreflightTests(CodexLaneFixture):
    def test_missing_or_changed_parser_dependencies_refuse_before_a_child_or_home(self):
        self.write_packet("foundation", "native-clients")
        cases = [("missing", None), ("digest-mismatch", "modified fixture adapter\n")]
        for name, content in cases:
            dependency = self.work_dir.parent / f"{name}-parser.mjs"
            if content is not None:
                dependency.write_text(content, encoding="utf-8")
            with self.subTest(dependency=name), \
                    mock.patch.object(codex_lane, "AUDIT_DEPENDENCIES", {dependency: "0" * 64}), \
                    contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(self.run_lane(), 2)
                self.assertIn("blind audit dependency missing or digest mismatch", err.getvalue())
                self.assertEqual(self.argv_calls(), [])
                self.assertFalse(codex_lane.codex_home_base().exists())
                self.assertFalse((self.work_dir / "codex").exists())
                self.assertIsNone(codex_lane.CHILD_CODEX_HOME)


class BlindPathAndPrecisionTests(CodexLaneFixture):
    """2026-09-24 re-record: 15 of 32 blind layers were voided with no read outside the export. Retrieval-CLI names were
    search terms or Python list items, a quoted '/' joined path parts, and Path.cwd()/ref and 'https://' read as
    absolute paths. A blind child's PATH now resolves no retrieval CLI (enforced, and refused otherwise), so the audit
    stops looking for their names; the root and path rules skip those Python forms."""

    def reasons(self, command, tools=codex_lane.AUDIT_TOOLS):
        events = self.work_dir / "audit-events.jsonl"
        events.write_text(json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": command}}) + "\n", encoding="utf-8")
        report = audit_with_fixture_cwd(events, [str(self.repo), str(self.work_dir / "packets")], tools)
        return [reason for item in report["flagged_commands"] for reason in item["reasons"]]

    def test_the_voided_re_record_commands_are_clean(self):
        for command in (
                "/bin/bash -lc \"rg -n -i 'qmd|original|body| get |context.hub' evidence/receipts\"",
                "/bin/bash -lc \"rg --files fixtures | rg -i 'rag|socraticode|qdrant'\"",
                "/bin/bash -lc \"python3 - <<'PY'\nfor t in ['serena','ast-grep','mcporter','ai-memory']: print(t)\nPY\"",
                "/bin/bash -lc \"python3 - <<'PY'\ndef walk(v,p=''):\n for k,x in v.items(): walk(x,p+'/'+k)\n "
                "for i,x in enumerate(v): walk(x, p + '/' + str(i))\nPY\"",
                "/bin/bash -lc \"python3 - <<'PY'\nfrom pathlib import Path\nfor ref in refs: print(Path.cwd()/ref)\nPY\"",
                "/bin/bash -lc \"python3 - <<'PY'\nfor ref in refs:\n if not ref.startswith('https://'): print(ref)\nPY\"",
                "/bin/bash -lc \"rg -n 'https://github.com/org/repo' catalogs\""):
            with self.subTest(command=command):
                self.assertEqual(self.reasons(command), [])

    def test_real_reaches_still_flag(self):
        expected = {
            "/bin/bash -lc 'ls /'": "names the filesystem root /",
            "/bin/bash -lc \"python3 -c \\\"import os; print(os.listdir('/'))\\\"\"": "names the filesystem root /",
            "/bin/bash -lc \"python3 - <<'PY'\nimport os\nprint(os.listdir('/'))\nPY\"": "names the filesystem root /",
            "/bin/bash -lc 'git log -p'": "runs git",
            "/bin/bash -lc 'curl -s https://example.invalid/x'": "runs curl",
            "/bin/bash -lc 'cat /home/example/.codex/AGENTS.md'":
                "path outside the repository and packets: /home/example/.codex/AGENTS.md",
            "/bin/bash -lc \"python3 -c \\\"print(open('/home/example/notes.md').read())\\\"\"":
                "path outside the repository and packets: /home/example/notes.md",
            "/bin/bash -lc 'cat https:/etc/passwd'": "path outside the repository and packets: /etc/passwd",
            "/bin/bash -lc 'cat x:/etc/passwd'": "path outside the repository and packets: /etc/passwd",
            "/bin/bash -lc '/home/example/.local/share/codex-ecosystem/bin/qmd search verdict'":
                "path outside the repository and packets: /home/example/.local/share/codex-ecosystem/bin/qmd",
        }
        for command, reason in expected.items():
            with self.subTest(command=command):
                self.assertIn(reason, self.reasons(command))

    def test_a_non_blind_run_still_looks_for_retrieval_cli_names(self):
        extended = codex_lane.AUDIT_TOOLS + codex_lane.BLIND_UNRESOLVABLE
        self.assertIn("runs qmd", self.reasons("/bin/bash -lc 'qmd search verdict'", extended))
        self.assertIn("runs codex", self.reasons("/bin/bash -lc 'codex exec --search x'", extended))
        self.assertEqual(self.reasons("/bin/bash -lc 'qmd search verdict'"), [])

    def test_a_blind_child_gets_the_system_path_and_the_callers_codex(self):
        env = codex_lane.child_env(self.work_dir / "home-probe")
        self.assertEqual(env["PATH"], codex_lane.BLIND_CHILD_PATH)
        self.assertEqual(codex_lane.child_executable("codex"), shutil.which("codex"))
        self.assertEqual(codex_lane.child_executable("/opt/x/codex"), "/opt/x/codex")

    def test_a_path_that_resolves_a_retrieval_cli_is_refused(self):
        bin_dir = self.work_dir / "sysbin"
        bin_dir.mkdir()
        self.assertIsNone(codex_lane.blind_path_issue(str(bin_dir)))
        (bin_dir / "qmd").write_text("#!/bin/sh\n", encoding="utf-8")
        self.assertIsNone(codex_lane.blind_path_issue(str(bin_dir)), "a file that is not executable resolves nothing")
        (bin_dir / "qmd").chmod(0o755)
        (bin_dir / "codex").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "codex").chmod(0o755)
        issue = codex_lane.blind_path_issue(str(bin_dir))
        self.assertIn(f"qmd ({bin_dir / 'qmd'})", issue)
        self.assertIn(f"codex ({bin_dir / 'codex'})", issue)
        # The default measures what the login shell adds, and refuses when it cannot.
        with mock.patch.object(codex_lane, "login_shell_path", return_value=str(bin_dir)):
            self.assertIn("qmd", codex_lane.blind_path_issue())
        with mock.patch.object(codex_lane, "login_shell_path", side_effect=codex_lane.PathUnmeasured("`/bin/sh -c` exited 2")):
            self.assertIn("could not be measured (`/bin/sh -c` exited 2)", codex_lane.blind_path_issue())

    def test_a_non_blind_lane_reports_a_retrieval_cli_and_a_blind_one_does_not(self):
        self.write_packet("foundation", "native-clients")
        command = json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": "/bin/bash -lc 'qmd search verdict'"}})
        self.events_file.write_text(command + "\n" + CANNED_EVENTS, encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_lane(["--allow-git-history"]), 0)
        audit = json.loads((self.work_dir / "codex" / codex_lane.AUDIT_NAME).read_text(encoding="utf-8"))
        reasons = [r for item in audit["layers"]["foundation__native-clients"]["flagged_commands"] for r in item["reasons"]]
        self.assertIn("runs qmd", reasons)
        # qmd cannot resolve on a blind child's PATH; missing native cwd still makes the event unverified.
        (self.work_dir / "codex" / "foundation__native-clients.json").unlink()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_lane(), 1)
        audit = json.loads((self.work_dir / "codex" / codex_lane.AUDIT_NAME).read_text(encoding="utf-8"))
        reasons = [r for item in audit["layers"]["foundation__native-clients"]["flagged_commands"]
                   for r in item["reasons"]]
        self.assertNotIn("runs qmd", reasons)
        self.assertTrue(any("working directory unverified" in reason for reason in reasons))

    def test_an_env_style_launcher_runs_with_the_callers_interpreter(self):
        # Codex review of #206 (P1): npm's codex is `#!/usr/bin/env node`, and a blind child's PATH has no node.
        bin_dir = self.work_dir / "npm-bin"
        bin_dir.mkdir()
        (bin_dir / "fakenode").write_text("#!/bin/sh\nexec python3 \"$@\"\n", encoding="utf-8")
        body = (FIXTURE_BIN / "codex").read_text(encoding="utf-8").split("\n", 1)[1]
        (bin_dir / "codex").write_text("#!/usr/bin/env fakenode\n" + body, encoding="utf-8")
        for name in ("fakenode", "codex"):
            (bin_dir / name).chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"]}):
            self.assertEqual(codex_lane.blind_child_argv(["codex", "exec", "x"]),
                             [str(bin_dir / "fakenode"), str(bin_dir / "codex"), "exec", "x"])
            self.write_packet("foundation", "native-clients")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(self.run_lane(), 0)
        self.assertTrue((self.work_dir / "codex" / "foundation__native-clients.json").is_file())
        # `env -S` with interpreter arguments, an absolute shebang, a binary, and an interpreter nobody resolves.
        (bin_dir / "s").write_text("#!/usr/bin/env -S fakenode -u -S\n", encoding="utf-8")
        (bin_dir / "a").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "b").write_bytes(b"\x7fELF\x02\x01")
        (bin_dir / "u").write_text("#!/usr/bin/env no-such-interpreter\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}):
            self.assertEqual(codex_lane.blind_child_argv([str(bin_dir / "s"), "x"]),
                             [str(bin_dir / "fakenode"), "-u", "-S", str(bin_dir / "s"), "x"])
            for name in ("a", "b", "u"):
                self.assertEqual(codex_lane.blind_child_argv([str(bin_dir / name), "x"]), [str(bin_dir / name), "x"])
            self.assertEqual(codex_lane.blind_child_argv(["missing-cli", "x"]), ["missing-cli", "x"])

    def test_a_cli_run_by_absolute_path_and_a_file_url_still_flag(self):
        # Codex review of #206 (P2 x2): /usr/local/bin/qmd is an exempt system executable token, and file:// is local.
        repo = self.repo
        expected = {
            "/bin/bash -lc '/usr/local/bin/qmd search verdict'": "runs qmd by path: /usr/local/bin/qmd",
            "/usr/local/bin/mcporter call x": "runs mcporter by path: /usr/local/bin/mcporter",
            "/bin/bash -lc 'cat https: //etc/passwd'": "path outside the repository and packets: //etc/passwd",
            "/bin/bash -lc \"python3 -c \\\"import subprocess; subprocess.run(['/opt/tools/serena'])\\\"\"":
                "runs serena by path: /opt/tools/serena",
            "/bin/bash -lc \"python3 -c \\\"import urllib.request as u; u.urlopen('file:///etc/os-release')\\\"\"":
                "path outside the repository and packets: ///etc/os-release",
        }
        for command, reason in expected.items():
            with self.subTest(command=command):
                self.assertIn(reason, self.reasons(command))
        for command in (f"/bin/bash -lc 'rg -n x {repo}/docs/qmd'", "/bin/bash -lc 'rg -n ssh://host/x docs'",
                        "/bin/bash -lc \"rg -n 'https://github.com/tobi/qmd' catalogs\"",
                        "/bin/bash -lc \"rg -n 'qmd://docs/verdict|s3://bucket/key|attachment://x/y' catalogs\"",
                        "/bin/bash -lc \"rg -n 'https://example.invalid/tools/serena/' catalogs\"",
                        "/bin/bash -lc \"rg -n 'wss://host/x|sftp://h/y' docs\""):
            with self.subTest(command=command):
                self.assertEqual(self.reasons(command), [])

    def test_independent_review_of_206_reaches_still_flag(self):
        # C2: root-prefixed concatenation remains an outside read; C1: file:/// and https:/// have no network authority.
        expected = {
            "/bin/bash -lc \"python3 -c \\\"print(open('/'+'etc/passwd').read())\\\"\"": "names the filesystem root /",
            "/bin/bash -lc \"python3 -c \\\"x = 'etc' ; print(open('/' + x))\\\"\"": "names the filesystem root /",
            "/bin/bash -lc \"python3 -c \\\"print(open(''+'/'+'etc/passwd').read())\\\"\"": "names the filesystem root /",
            "/bin/bash -lc 'python3 - <<\"PY\"\nprint(open(\"/\"+\"etc\"))\nPY'": "names the filesystem root /",
            "/bin/bash -lc \"python3 -c \\\"x='etc'; print(open(''+'/'+x))\\\"\"": "names the filesystem root /",
            "/bin/bash -lc 'cat https:///etc/passwd'": "path outside the repository and packets: ///etc/passwd",
            "/bin/bash -lc \"python3 -c \\\"import urllib.request as u; u.urlopen('FILE://localhost/etc/passwd')\\\"\"":
                "path outside the repository and packets: //localhost/etc/passwd",
            "/bin/bash -lc 'unzip -p jar:file:///etc/x.jar'": "path outside the repository and packets: ///etc/x.jar",
            "/bin/bash -lc 'cat LOCAL://etc/passwd'": "path outside the repository and packets: //etc/passwd",
            "/bin/bash -lc 'cat HTTP+UNIX://socket/v1'": "path outside the repository and packets: //socket/v1",
            "/bin/bash -lc '/bin/sh -c file:///usr/local/bin/qmd; /usr/local/bin/qmd x'":
                "runs qmd by path: /usr/local/bin/qmd",
        }
        for command, reason in expected.items():
            with self.subTest(command=command):
                self.assertIn(reason, self.reasons(command))
        for prefix, outside in (("a", False), ("", True)):
            code = f"x={prefix!r};print(open(x+'/'+'etc'))"
            command = shlex.join(["/bin/bash", "-lc", "python3 -c " + shlex.quote(code)])
            with self.subTest(bounded_prefix=prefix):
                self.assertEqual(bool(self.reasons(command)), outside)
        # Printed URI text does not read the resource; the cat/local-URI controls above still do.
        for code in ("print('http+unix://%2Frun%2Fuser%2F1000%2Fx.sock/v1')", "print('local://etc/passwd')",
                     "print('local://qmd')", "print('http+unix://qmd')"):
            command = shlex.join(["/bin/bash", "-lc", "python3 -c " + shlex.quote(code)])
            with self.subTest(printed_uri=code):
                self.assertEqual(self.reasons(command), [])

    def test_separator_and_anchor_exemptions_do_not_hide_constructed_reads(self):
        # PR #216's broad exemptions hide these command-text paths at both audit call sites.
        expected = {
            "/bin/bash -lc \"python3 -c \\\"print(open('://'[1:]+'etc/passwd').read())\\\"\"": "//",
            "/bin/bash -lc \"python3 -c \\\"import os; print(os.listdir('://'[1:]))\\\"\"": "//",
            "/bin/bash -lc \"python3 -c \\\"print(open('/etc/passwd$)'[:-2]).read())\\\"\"": "/etc/passwd$",
            "/bin/bash -lc \"python3 -c \\\"print(open('/etc/passwd$|'.rstrip('$|')).read())\\\"\"": "/etc/passwd$",
            "/bin/bash -lc \"rg x $(python3 -c \\\"print('|/etc/passwd$|'[1:-2])\\\")\"": "/etc/passwd$",
            "/bin/bash -lc \"cat /etc/passwd$''\"": "/etc/passwd",
            "/bin/bash -lc 'cat ://x'": "//x",
            "/bin/bash -lc 'ls //'": "//",
            "/bin/bash -lc 'cat /runner.py'": "/runner.py",
        }
        for command, path in expected.items():
            with self.subTest(command=command):
                reasons = self.reasons(command)
                if "$(" in command or "python3 -c" in command:
                    self.assertTrue(reasons, "a computed read or substitution must remain refused")
                else:
                    self.assertIn(f"path outside the repository and packets: {path}", reasons)
        for command in ("/bin/bash -lc \"rg -n '/runner.py$' x\"", "/bin/bash -lc 'rg -n \"://|file\" docs'",
                        shlex.join(["/bin/bash", "-lc", "python3 -c " + shlex.quote("print(':'+'//etc')")])):
            with self.subTest(literal_data=command):
                self.assertEqual(self.reasons(command), [])
        # URI text is data; an actual qmd executable invocation remains forbidden.
        for scheme in ("local", "http+unix"):
            code = f"print({scheme + '://qmd'!r})"
            command = shlex.join(["/bin/bash", "-lc", "python3 -c " + shlex.quote(code)])
            with self.subTest(scheme=scheme):
                self.assertEqual(self.reasons(command), [])
        self.assertIn("runs qmd by path: /usr/bin/qmd", self.reasons("/bin/bash -lc '/usr/bin/qmd search x'"))

    def test_wave_20260924_separator_and_regex_residuals(self):
        # The historical separator and regex are literal data, paired with actual reads outside the export.
        script = "python3 - <<'PY'\nfor ref in refs:\n print(ref, 'EXTERNAL' if '://' in ref else ref)\nPY"
        clean = [shlex.join(["/bin/bash", "-lc", script]),
                 "/bin/bash -lc \"rg --files tests | rg '(test_adaptive_paper_(recovery|safety)\\\\.py$|/runner.py$)'\""]
        for command in clean:
            with self.subTest(command=command):
                self.assertEqual(self.reasons(command), [])
        for command in ("/bin/bash -lc 'cat /runner.py'", "/bin/bash -lc 'cat file:///etc/passwd'"):
            with self.subTest(actual_read=command):
                self.assertTrue(self.reasons(command))

    def test_env_shell_shims_are_measured_under_the_blind_path(self):
        bin_dir = self.work_dir / "env-shims"
        bin_dir.mkdir()
        empty_path = self.work_dir / "empty-path"
        empty_path.mkdir()
        for name, text in (
                ("asdf-codex", '#!/usr/bin/env bash\nexec asdf exec codex "$@"\n'),
                ("s-codex", '#!/usr/bin/env -S bash -e\nexec no-such-codex-launch-tool-216 "$@"\n')):
            launcher = bin_dir / name
            launcher.write_text(text, encoding="utf-8")
            launcher.chmod(0o755)
            with self.subTest(launcher=name), mock.patch.object(codex_lane, "BLIND_CHILD_PATH", str(empty_path)):
                issue = codex_lane.codex_launch_issue(str(launcher))
                self.assertIsNotNone(issue)
                self.assertIn(str(launcher), issue)
                self.assertIn("exited 127", issue)
                self.assertIn("not found", issue)
        # A command that exists but cannot execute is a measured exit 126.
        target = bin_dir / "not-executable"
        target.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        launcher = bin_dir / "permission-codex"
        launcher.write_text(f'#!/usr/bin/env bash\nexec "{target}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
        issue = codex_lane.codex_launch_issue(str(launcher))
        self.assertIsNotNone(issue)
        self.assertIn("exited 126", issue)

    def test_identity_launcher_is_accepted_and_runs_in_the_blind_environment(self):
        # Use the original recipe unchanged, with a /bin/sh target for Linux/macOS determinism.
        target = self.work_dir / "absolute-codex"
        target.write_text(
            '#!/bin/sh\n[ "$1" = --version ] || exit 2\n'
            '[ -d "$HOME" ] && [ -d "$CODEX_HOME" ] || exit 3\n'
            '[ ! -e "$CODEX_HOME/auth.json" ] || exit 4\n'
            'printf "fixture codex version\\n"\n', encoding="utf-8")
        target.chmod(0o755)
        launcher = self.work_dir / "identity-codex"
        template = (ROOT / "observability/collector/codex-identity-launcher.sh.example").read_text(encoding="utf-8")
        launcher.write_text(template.replace("@CODEX_BIN@", str(target)), encoding="utf-8")
        launcher.chmod(0o755)
        self.assertIsNone(codex_lane.codex_launch_issue(str(launcher)))
        home = self.work_dir / "identity-probe-home"
        home.mkdir()
        env = codex_lane.child_env(home)
        Path(env["HOME"]).mkdir()
        Path(env["TMPDIR"]).mkdir()
        completed = subprocess.run(codex_lane.blind_child_argv([str(launcher), "--version"]), env=env,
                                   stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, "fixture codex version\n")

    def test_launcher_probe_uses_empty_scratch_homes_and_reports_other_failures(self):
        launcher = self.work_dir / "probe-codex"
        launcher.write_text("#!/usr/bin/env -S bash -e\n", encoding="utf-8")
        launcher.chmod(0o755)
        observed_homes = []

        def probe(argv, **kwargs):
            self.assertEqual(argv, [shutil.which("bash"), "-e", str(launcher), "--version"])
            self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
            self.assertEqual(kwargs["timeout"], 5)
            env = kwargs["env"]
            self.assertEqual(env["PATH"], codex_lane.BLIND_CHILD_PATH)
            self.assertEqual(list(Path(env["HOME"]).iterdir()), [])
            self.assertFalse((Path(env["CODEX_HOME"]) / "auth.json").exists())
            self.assertNotEqual(env["CODEX_HOME"], str(self.native_codex))
            observed_homes.append(Path(env["CODEX_HOME"]))
            return subprocess.CompletedProcess(argv, 2, "", "first line\nlast line\n")

        err = io.StringIO()
        with mock.patch.object(codex_lane.subprocess, "run", side_effect=probe), contextlib.redirect_stderr(err):
            self.assertIsNone(codex_lane.codex_launch_issue(str(launcher)))
        self.assertIn("exited 2", err.getvalue())
        self.assertIn("last line", err.getvalue())
        self.assertNotIn("first line", err.getvalue())
        self.assertTrue(observed_homes)
        self.assertTrue(all(not path.exists() for path in observed_homes))
        err = io.StringIO()
        with mock.patch.object(codex_lane.subprocess, "run", side_effect=subprocess.TimeoutExpired("probe", 5)), \
                contextlib.redirect_stderr(err):
            self.assertIsNone(codex_lane.codex_launch_issue(str(launcher)))
        self.assertIn("timed out", err.getvalue())
        err = io.StringIO()
        with mock.patch.object(codex_lane.subprocess, "run", side_effect=OSError("fixture launch error")), \
                contextlib.redirect_stderr(err):
            self.assertIsNone(codex_lane.codex_launch_issue(str(launcher)))
        self.assertIn("fixture launch error", err.getvalue())

    def test_the_measured_path_covers_a_shell_without_path_and_ignores_profile_output(self):
        # C3: subprocess.run(..., shell=True, env={}) starts /bin/sh with its compiled default PATH (/usr/local/bin);
        # C5: a profile that prints something must not turn it into a directory.
        calls = []

        def run(argv, env=None, **_kwargs):
            calls.append((argv, env))
            noise = "profile says hi\n" if "-lc" in argv else ""
            measured = "/login/bin" if "-lc" in argv else ("/sh/default" if argv[0] == "/bin/sh" else "/shell/default")
            return subprocess.CompletedProcess(argv, 0, noise + "\n" + codex_lane.PATH_SENTINEL + measured, "")

        with mock.patch.object(codex_lane.subprocess, "run", side_effect=run):
            measured = REAL_LOGIN_SHELL_PATH()
        self.assertEqual(measured.split(os.pathsep),
                         [*os.defpath.split(os.pathsep), "/login/bin", "/sh/default", "/shell/default"])
        self.assertEqual([env for _argv, env in calls][1:], [{}, {}])
        self.assertEqual(calls[0][1]["PATH"], codex_lane.BLIND_CHILD_PATH)
        self.assertEqual(calls[1][0][0], "/bin/sh")
        failing = lambda argv, env=None, **_kwargs: subprocess.CompletedProcess(argv, 0, "no sentinel", "profile broke")
        with mock.patch.object(codex_lane.subprocess, "run", side_effect=failing):
            with self.assertRaisesRegex(codex_lane.PathUnmeasured, "without printing its PATH: profile broke"):
                REAL_LOGIN_SHELL_PATH()
        # R2-4: a probe that raises is named, and so is non-UTF-8 profile output, which no longer escapes.
        with mock.patch.object(codex_lane.subprocess, "run", side_effect=subprocess.TimeoutExpired("sh", 30)):
            with self.assertRaisesRegex(codex_lane.PathUnmeasured, "timed out"):
                REAL_LOGIN_SHELL_PATH()
        self.assertIn("/usr/bin", REAL_LOGIN_SHELL_PATH().split(os.pathsep))
        # A login shell whose profile prints bytes that are not UTF-8 is still measured (R2-4).
        noisy = self.work_dir / "noisy-shell"
        noisy.write_bytes(b'#!/bin/sh\nprintf "\\377\\376 profile noise\\n"\nexec /bin/sh "$@"\n')
        noisy.chmod(0o755)
        import pwd
        with mock.patch.object(pwd, "getpwuid", return_value=mock.Mock(pw_shell=str(noisy))):
            self.assertIn("/usr/bin", REAL_LOGIN_SHELL_PATH().split(os.pathsep))

    def test_a_shell_script_codex_launcher_is_refused_up_front(self):
        # Independent review of #206, R2-2: pnpm's cmd-shim runs `exec node ...` by name, which exits 127 in a blind child.
        bin_dir = self.work_dir / "shim-bin"
        bin_dir.mkdir()
        (bin_dir / "codex").write_text('#!/bin/sh\nexec node "$0.js" "$@"\n', encoding="utf-8")
        (bin_dir / "codex").chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"]}):
            self.assertIn("is a shell-script launcher (/bin/sh)", codex_lane.codex_launch_issue())
            self.write_packet("foundation", "native-clients")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(self.run_lane(), 2)
        self.assertIn("shell-script launcher", err.getvalue())
        self.assertFalse(self.argv_log.exists() and self.argv_log.read_text(encoding="utf-8").strip())
        # The fixture's env-style launcher, a missing codex and a binary are not refused.
        self.assertIsNone(codex_lane.codex_launch_issue())
        self.assertIsNone(codex_lane.codex_launch_issue("no-such-codex"))
        (bin_dir / "native").write_bytes(b"\x7fELF\x02\x01")
        (bin_dir / "native").chmod(0o755)
        self.assertIsNone(codex_lane.codex_launch_issue(str(bin_dir / "native")))

    def test_a_failed_childs_stderr_reaches_the_console_not_the_record(self):
        # Independent review of #206, R2-2: "codex exec exited 127" alone did not say why.
        self.write_packet("foundation", "native-clients")
        failed = {"exit_code": 127, "stdout": "", "timed_out": False, "stopped": False, "elapsed": 0.1,
                  "stderr": "Reading additional input from stdin...\n/usr/bin/env: 'node': No such file or directory\n"}
        err = io.StringIO()
        with mock.patch.object(codex_lane, "run_attempt", return_value=failed), contextlib.redirect_stderr(err):
            self.assertEqual(self.run_lane(), 1)
        self.assertIn("codex exec exited 127: /usr/bin/env: 'node': No such file or directory", err.getvalue())
        self.assertNotIn("Reading additional input", err.getvalue())
        failures = json.loads((self.work_dir / "codex" / "failures.json").read_text(encoding="utf-8"))["failures"]
        self.assertEqual(failures[0]["reason"], "failed after retry: codex exec exited 127")

    def test_a_blind_run_is_refused_when_the_child_path_resolves_one(self):
        self.write_packet("foundation", "native-clients")
        with mock.patch.object(codex_lane, "blind_path_issue", return_value="a blind child's PATH resolves qmd"):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(self.run_lane(), 2)
        self.assertIn("resolves qmd", err.getvalue())
        self.assertFalse(self.argv_log.exists() and self.argv_log.read_text(encoding="utf-8").strip())


class InterruptionTests(CodexLaneFixture):
    """Independent review of #145, round 7 (REG7-1, ISO-R7-1..4): an interrupted or resumed blind run never keeps a
    flagged layer, a stop writes no return and starts no retry, and one work dir runs once whatever the base."""

    FLAGGED = json.dumps({"type": "item.completed", "item": {
        "type": "command_execution", "command": "/bin/bash -lc 'cat /home/example/.state/verdicts.json'"}}) + "\n"

    def flagged_events(self) -> Path:
        path = self.work_dir.parent / "flagged-events.jsonl"
        path.write_text(CANNED_EVENTS + "\n" + self.FLAGGED, encoding="utf-8")
        return path

    def test_an_interrupted_run_and_its_resume_never_keep_a_flagged_layer(self):
        self.write_packet("foundation", "a-layer")
        self.write_packet("foundation", "b-layer")
        os.environ["CODEX_FAKE_EVENTS_MAP"] = json.dumps({"foundation__a-layer": str(self.flagged_events())})
        os.environ["CODEX_FAKE_TERM_PARENT_MATCH"] = "foundation__b-layer"
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_lane()
        codex_dir = self.work_dir / "codex"
        # The flagged layer was audited before any write; the stopped one wrote nothing.
        self.assertFalse((codex_dir / "foundation__a-layer.json").exists())
        self.assertTrue((codex_dir / "foundation__a-layer.json.audit-flagged").exists())
        self.assertFalse((codex_dir / "foundation__b-layer.json").exists())
        audit = json.loads((codex_dir / codex_lane.AUDIT_NAME).read_text(encoding="utf-8"))
        self.assertTrue(audit["layers"]["foundation__a-layer"]["flagged_commands"])
        os.environ.pop("CODEX_FAKE_TERM_PARENT_MATCH")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_lane(), 1)
        self.assertFalse((codex_dir / "foundation__a-layer.json").exists())
        self.assertTrue((codex_dir / "foundation__b-layer.json").exists())

    def test_a_resume_reaudits_a_kept_return(self):
        packet_path = self.write_packet("foundation", "native-clients")
        codex_dir = self.work_dir / "codex"
        (codex_dir / "events").mkdir(parents=True)
        out_path = codex_dir / "foundation__native-clients.json"
        events_path = codex_dir / "events" / "foundation__native-clients.jsonl"
        for events in (self.FLAGGED, None):
            with self.subTest(events="flagged" if events else "missing"):
                self.argv_log.unlink(missing_ok=True)
                out_path.write_text(json.dumps(canned_return(
                    packet_sha256=hashlib.sha256(packet_path.read_bytes()).hexdigest(),
                    provenance=codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo),
                    model={"name": "gpt-6-astra", "effort": "high", "family": "openai"})), encoding="utf-8")
                if events:
                    events_path.write_text(events, encoding="utf-8")
                else:
                    events_path.unlink(missing_ok=True)
                with contextlib.redirect_stderr(io.StringIO()):
                    self.run_lane(["--model", "gpt-6-astra", "--effort", "high"])
                self.assertEqual(len(self.argv_calls()), 1, "a kept return with flagged or missing events reruns")

    def test_an_interrupted_rerun_never_leaves_a_countable_old_return(self):
        # Round 8, NEW-1: the rerun truncated the events and was interrupted, leaving the old return beside an empty,
        # clean-looking stream that the next resume counted.
        packet_path = self.write_packet("foundation", "native-clients")
        codex_dir = self.work_dir / "codex"
        (codex_dir / "events").mkdir(parents=True)
        out_path = codex_dir / "foundation__native-clients.json"
        out_path.write_text(json.dumps(canned_return(
            packet_sha256=hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            provenance=codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo),
            model={"name": "gpt-6-astra", "effort": "high", "family": "openai"})), encoding="utf-8")
        events_path = codex_dir / "events" / "foundation__native-clients.jsonl"
        events_path.write_text(self.FLAGGED, encoding="utf-8")
        os.environ["CODEX_FAKE_TERM_PARENT_MATCH"] = "foundation__native-clients"
        os.environ["CODEX_FAKE_TERM_SLEEP"] = "30"
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_lane(["--model", "gpt-6-astra", "--effort", "high"])
        self.assertFalse(out_path.exists(), "the rerun removed the old return before rewriting its events")
        # And a kept return beside an empty stream is never counted.
        out_path.write_text(json.dumps(canned_return(
            packet_sha256=hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            provenance=codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo),
            model={"name": "gpt-6-astra", "effort": "high", "family": "openai"})), encoding="utf-8")
        events_path.write_text("", encoding="utf-8")
        self.assertFalse(codex_lane.existing_output_is_valid(
            out_path, "foundation", "native-clients", hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            audit_roots=[str(self.repo)]))

    def test_a_stop_with_jobs_2_writes_no_return_and_starts_no_retry(self):
        self.write_packet("foundation", "a-layer")
        self.write_packet("foundation", "b-layer")
        os.environ["CODEX_FAKE_SLEEP_MAP"] = json.dumps({"foundation__a-layer": 30})
        os.environ["CODEX_FAKE_TERM_PARENT_MATCH"] = "foundation__b-layer"
        os.environ["CODEX_FAKE_TERM_SLEEP"] = "30"
        started = time.monotonic()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_lane(["--jobs", "2"])
        self.assertLess(time.monotonic() - started, 20)
        # Each layer's child ran at most once: no retry starts after a stop, and a layer whose child had not started
        # when the stop came never starts one.
        calls = [" ".join(call) for call in self.argv_calls()]
        for layer in ("foundation__a-layer", "foundation__b-layer"):
            self.assertLessEqual(sum(layer in call for call in calls), 1, layer)
        self.assertEqual(sum("foundation__b-layer" in call for call in calls), 1)
        self.assertEqual(sorted(p.name for p in (self.work_dir / "codex").glob("*__*.json")), [])
        # The run home's link is gone and no child is left holding it.
        homes = sorted(codex_lane.codex_home_base().glob(codex_lane.codex_home_prefix(self.work_dir) + "-*"))
        self.assertTrue(homes)
        self.assertFalse(any((home / "auth.json").is_symlink() for home in homes))
        self.assertFalse(any(codex_lane.home_in_use(home) for home in homes))

    def test_one_work_dir_runs_once_whatever_the_homes_base(self):
        self.write_packet("foundation", "native-clients")
        with codex_lane.exclusive_run_lock(codex_lane.work_run_lock(self.work_dir)):
            os.environ[codex_lane.CODEX_HOME_BASE_ENV] = str(self.work_dir.parent / "other-base")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(self.run_lane(), 2)
        self.assertIn("another run holds", err.getvalue())
        self.assertEqual(self.argv_calls(), [])


class DocumentedCommandTests(unittest.TestCase):
    """PR #141 review (P2): the README's codex exec block omitted -c web_search="disabled"."""

    def test_the_readme_command_block_carries_every_isolation_argument(self):
        readme = (TOOL_DIR / "README.md").read_text(encoding="utf-8")
        blocks = [block for block in re.findall(r"```sh\n(.*?)```", readme, re.S) if block.startswith("codex exec")]
        self.assertEqual(len(blocks), 1, "exactly one documented codex exec command block")
        argv = shlex.split(blocks[0].replace("\\\n", " "))
        isolation = list(codex_lane.ISOLATION_ARGS)
        self.assertTrue(any(argv[index:index + len(isolation)] == isolation for index in range(len(argv))),
                        f"{argv} must contain {isolation} in order")
        docstring = shlex.split(codex_lane.__doc__.split("then run", 1)[1].split("capturing", 1)[0]
                                .replace("\\\n", " "))
        self.assertTrue(any(docstring[index:index + len(isolation)] == isolation for index in range(len(docstring))),
                        f"the module docstring {docstring} must contain {isolation} in order")


class EffortResumeTests(CodexLaneFixture):
    """Codex review of #145: a changed --effort reruns a layer instead of resuming it."""

    def test_a_return_made_at_another_effort_is_not_resumed(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(["--model", "gpt-6-astra", "--effort", "high"]), 0)
        first = len(self.argv_calls())
        self.assertEqual(self.run_lane(["--model", "gpt-6-astra", "--effort", "high"]), 0)
        self.assertEqual(len(self.argv_calls()), first)
        self.assertEqual(self.run_lane(["--model", "gpt-6-astra", "--effort", "medium"]), 0)
        self.assertGreater(len(self.argv_calls()), first)


class EvidenceTreeProvenanceTests(CodexLaneFixture):
    """Round-9 review of #145: a return is bound to the evidence tree it read."""

    def test_a_resume_against_another_export_reruns(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        first = len(self.argv_calls())
        self.assertEqual(self.run_lane(), 0)
        self.assertEqual(len(self.argv_calls()), first, "same tree: resumed")
        (self.repo / "evidence.json").write_text('{"other": "export"}', encoding="utf-8")
        self.assertEqual(self.run_lane(), 0)
        self.assertGreater(len(self.argv_calls()), first, "another tree: rerun")
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["provenance"]["repo_tree_sha256"], codex_lane.tree_sha256(self.repo))

    def test_a_tree_changed_during_the_run_sets_the_returns_aside(self):
        self.write_packet("foundation", "native-clients")
        trees = iter(["a" * 64, "b" * 64])
        original_tree = codex_lane.tree_sha256
        with mock.patch.object(codex_lane, "tree_sha256", side_effect=lambda repo, *rest, **named:
                               next(trees) if Path(repo) == self.repo else original_tree(repo, *rest, **named)), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.run_lane(), 1)
        out_path = self.out_path("foundation", "native-clients")
        self.assertFalse(out_path.exists())
        self.assertTrue(out_path.with_name(out_path.name + ".tree-changed").is_file())
        self.assertIn("the evidence tree changed during the run", err.getvalue())


class EscapingSymlinkTreeTests(CodexLaneFixture):
    """Codex review of #145: content behind a symlink leaving the tree could change under an unchanged digest."""

    def test_the_tree_digest_refuses_a_symlink_leaving_the_repository(self):
        (self.repo / "inner.md").write_text("x", encoding="utf-8")
        os.symlink("inner.md", self.repo / "inner-link.md")
        codex_lane.tree_sha256(self.repo)
        os.symlink("/etc/hostname", self.repo / "outside-link")
        with self.assertRaises(ValueError):
            codex_lane.tree_sha256(self.repo)
        self.write_packet("foundation", "native-clients")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.run_lane(), 2)
        self.assertIn("symlink leaving it", err.getvalue())
        # A deliberately non-blind run (--allow-git-history) hashes such a link's text instead (re-review L2).
        self.assertIsInstance(codex_lane.tree_sha256(self.repo, allow_escaping_links=True), str)
        (self.repo / "outside-link").unlink()
        os.symlink("loop-b", self.repo / "loop-a")
        os.symlink("loop-a", self.repo / "loop-b")
        with self.assertRaisesRegex(ValueError, "symlink loop"):  # on 3.12 and 3.13 alike (delta review D1)
            codex_lane.tree_sha256(self.repo)
        # A non-blind run hashes a loop by its link text on 3.12 too, where resolve() raises (round 4, R4-REG-4).
        self.assertIsInstance(codex_lane.tree_sha256(self.repo, allow_escaping_links=True), str)
        os.symlink("missing-target", self.repo / "dangling")
        (self.repo / "loop-a").unlink()
        (self.repo / "loop-b").unlink()
        self.assertIsInstance(codex_lane.tree_sha256(self.repo), str)  # a dangling internal link is hashed
        (self.repo / "dangling").unlink()
        os.symlink("loop-b", self.repo / "loop-a")
        os.symlink("loop-a", self.repo / "loop-b")
        (self.repo / "loop-a").unlink()
        (self.repo / "loop-b").unlink()
        os.mkfifo(self.repo / "pipe")
        with self.assertRaisesRegex(ValueError, "non-regular entry"):
            codex_lane.tree_sha256(self.repo)
        # A non-blind run tolerates git's fsmonitor socket and similar entries (delta review L3).
        self.assertIsInstance(codex_lane.tree_sha256(self.repo, allow_escaping_links=True), str)


class OmniRouteProviderTests(CodexLaneFixture):
    """The insurance provider is opt-in, keyless, loopback-only, and keeps blind-child isolation.

    All executions use the fixture CLI; the prompt canary observes only the runner/client boundary,
    never an upstream gateway body or a gateway settings/log-detail route.
    """

    ENDPOINT = "http://127.0.0.1:21128/v1"
    PASS_THROUGH = ("not_attested (deployed settings unreadable by policy; OmniRoute@c1e30b76 chatCore.ts:3156, "
                    "systemPrompt.ts:210-217/278-283, strategySelector.ts:234-249)")

    def setUp(self):
        super().setUp()
        # A real caller's endpoint cannot affect these synthetic cases.
        os.environ.pop("OMNIROUTE_BASE_URL", None)

    def assert_isolation_args(self, argv):
        required = list(codex_lane.ISOLATION_ARGS)
        self.assertTrue(any(argv[index:index + len(required)] == required
                            for index in range(len(argv))), "OmniRoute must retain every isolation argument")

    def test_the_absent_provider_flag_keeps_the_legacy_native_metadata(self):
        self.write_packet("foundation", "native-clients")
        # An endpoint in the parent environment does not opt a wave into failover.
        with mock.patch.dict(os.environ, {"OMNIROUTE_BASE_URL": self.ENDPOINT}):
            self.assertEqual(self.run_lane(), 0)
        [argv] = self.argv_calls()
        self.assertFalse(any(value.startswith("model_provider=") or value.startswith("model_providers.")
                             for value in argv))
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(set(data["provenance"]), {"codex_lane_py_sha256", "prompt_sha256", "repo_tree_sha256"})
        self.assertFalse({"provider", "provider_base_url", "pass_through"} & set(self.usage_rows()[0]))

    def test_implicit_and_explicit_native_omit_transport_fields_on_receipts_and_retries(self):
        self.write_packet("foundation", "native-clients")
        os.environ["CODEX_FAKE_FAIL_ATTEMPTS"] = "1"
        legacy_keys = {"codex_lane_py_sha256", "prompt_sha256", "repo_tree_sha256"}
        transport_keys = {"provider", "provider_base_url", "pass_through"}
        for args in ([], ["--provider", "native"]):
            selection = "explicit" if args else "implicit"
            self.counter_file.unlink(missing_ok=True)
            self.out_path("foundation", "native-clients").unlink(missing_ok=True)
            previous_calls, previous_rows = len(self.argv_calls()), len(self.usage_rows())
            with mock.patch.dict(os.environ, {"OMNIROUTE_BASE_URL": self.ENDPOINT}):
                self.assertEqual(self.run_lane(args), 0)
            argv_calls = self.argv_calls()[previous_calls:]
            self.assertEqual(len(argv_calls), 2, "the failed native attempt must retry")
            for argv in argv_calls:
                self.assertFalse(any(value.startswith("model_provider=") or value.startswith("model_providers.")
                                     for value in argv), "native selection must retain native client config")
            data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
            with self.subTest(selection=selection, receipt=True):
                self.assertEqual(set(data["provenance"]), legacy_keys)
            rows = self.usage_rows()[previous_rows:]
            self.assertEqual([row["attempt"] for row in rows], [1, 2])
            self.assertNotEqual(rows[0]["exit_code"], 0)
            self.assertEqual(rows[1]["exit_code"], 0)
            for row in rows:
                with self.subTest(selection=selection, attempt=row["attempt"]):
                    self.assertFalse(transport_keys & set(row), "native usage keeps the legacy metadata shape")

    def test_omniroute_dry_run_on_a_synthetic_tier1_packet_writes_nothing(self):
        self.write_packet("foundation", "native-clients", {
            "schema_version": 1, "catalog": "foundation", "layer_id": "native-clients", "tier": 1,
        })
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(codex_lane, "native_auth_path", side_effect=AssertionError("native auth lookup")), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(self.run_lane(["--provider", "omniroute", "--dry-run"]), 0)
        # shlex.join quotes the filled prompt as one argument while preserving its embedded newlines.
        argv = shlex.split(out.getvalue())
        self.assertEqual(argv[:2], ["env", "-i"])
        self.assertIn("OMNIROUTE_BASE_URL=" + self.ENDPOINT, argv)
        self.assert_isolation_args(argv)
        self.assertTrue(any(value in ('model_provider="omniroute"', "model_provider='omniroute'")
                            for value in argv))
        self.assertTrue(any(value.startswith("model_providers.omniroute.base_url=")
                            and self.ENDPOINT in value for value in argv))
        self.assertTrue(any(value == 'model_providers.omniroute.wire_api="responses"'
                            or value == "model_providers.omniroute.wire_api='responses'" for value in argv))
        self.assertFalse(any("env_key" in value or "API_KEY" in value or "Bearer " in value for value in argv))
        self.assertFalse((self.work_dir / "codex").exists())
        self.assertFalse(codex_lane.codex_home_base().exists())
        self.assertEqual(self.argv_calls(), [])

    def test_omniroute_records_the_provider_per_family_without_native_auth(self):
        families = [("foundation", "native-clients"), ("runtime", "bounded-workers")]
        for catalog, layer_id in families:
            self.write_packet(catalog, layer_id)
        self.return_file.write_text(json.dumps(canned_return(provenance={"provider": "native"})),
                                    encoding="utf-8")
        env_log = self.work_dir.parent / "omniroute-homes.jsonl"
        os.environ["CODEX_FAKE_ENV_LOG"] = str(env_log)
        with mock.patch.object(codex_lane, "native_auth_path", side_effect=AssertionError("native auth lookup")):
            self.assertEqual(self.run_lane(["--provider", "omniroute"]), 0)
        for catalog, layer_id in families:
            data = json.loads(self.out_path(catalog, layer_id).read_text(encoding="utf-8"))
            self.assertEqual(data["provenance"].get("provider"), "omniroute")
            self.assertEqual(data["model"]["family"], "openai")
        self.assertEqual({(row["catalog"], row["layer"], row.get("provider")) for row in self.usage_rows()},
                         {(catalog, layer_id, "omniroute") for catalog, layer_id in families})
        for row in self.usage_rows():
            self.assertEqual(row.get("provider_base_url"), self.ENDPOINT)
        for argv in self.argv_calls():
            self.assert_isolation_args(argv)
        seen = [json.loads(line) for line in env_log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(seen), 2)
        for row in seen:
            home = Path(row["CODEX_HOME"])
            self.assertFalse(row["auth_link"])
            self.assertFalse((home / "auth.json").exists())
            self.assertEqual(row["HOME"], str(home / "home"))
            self.assertEqual(list((home / "home").iterdir()), [])
            self.assertEqual(oct(home.stat().st_mode & 0o777), "0o700")

    def test_omniroute_disclosure_is_runner_owned_on_every_packet_and_attempt(self):
        families = [("foundation", "native-clients"), ("runtime", "bounded-workers")]
        for catalog, layer_id in families:
            self.write_packet(catalog, layer_id)
        self.return_file.write_text(json.dumps(canned_return(provenance={
            "provider": "native", "pass_through": "fixture-spoofed-attestation",
        })), encoding="utf-8")
        # Retain a failed attempt as well as both successful packets: every usage row needs the disclosure.
        os.environ["CODEX_FAKE_FAIL_ATTEMPTS"] = "1"
        self.assertEqual(self.run_lane(["--provider", "omniroute"]), 0)
        for catalog, layer_id in families:
            with self.subTest(packet=f"{catalog}__{layer_id}"):
                data = json.loads(self.out_path(catalog, layer_id).read_text(encoding="utf-8"))
                self.assertEqual(data["provenance"].get("provider"), "omniroute")
                self.assertEqual(data["provenance"].get("pass_through"), self.PASS_THROUGH)
        rows = self.usage_rows()
        self.assertEqual(len(rows), 3)
        self.assertTrue(any(row["exit_code"] != 0 for row in rows))
        for row in rows:
            with self.subTest(usage=(row["catalog"], row["layer"], row["attempt"])):
                self.assertEqual(row.get("provider"), "omniroute")
                self.assertEqual(row.get("pass_through"), self.PASS_THROUGH)

    def test_omniroute_uses_a_fresh_keyless_home_for_each_run(self):
        self.write_packet("foundation", "native-clients")
        env_log = self.work_dir.parent / "fresh-omniroute-homes.jsonl"
        os.environ["CODEX_FAKE_ENV_LOG"] = str(env_log)
        (self.native_codex / "auth.json").unlink()
        with mock.patch.object(codex_lane, "native_auth_path", side_effect=AssertionError("native auth lookup")):
            self.assertEqual(self.run_lane(["--provider", "omniroute"]), 0)
            self.out_path("foundation", "native-clients").unlink()
            self.assertEqual(self.run_lane(["--provider", "omniroute"]), 0)
        seen = [json.loads(line) for line in env_log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len({row["CODEX_HOME"] for row in seen}), 2)
        self.assertFalse(any(row["auth_link"] for row in seen))

    def test_nonloopback_or_credential_bearing_endpoints_are_refused_before_a_child(self):
        self.write_packet("foundation", "native-clients")
        endpoints = [
            "https://example.invalid/v1", "http://192.0.2.1:21128/v1",
            "http://fixture-user:fixture-password@127.0.0.1:21128/v1",
            "http://127.0.0.1:21128/v1?token=fixture-query",
            "http://127.0.0.1:21128/v1#fixture-fragment", "http://127.0.0.1:99999/v1",
            "http://127.0.0.1:invalid/v1", "file:///v1",
        ]
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(self.run_lane(["--provider", "omniroute", "--omniroute-base-url", endpoint]), 2)
                self.assertIn("loopback", err.getvalue().lower())
                self.assertNotIn(endpoint, err.getvalue())
                self.assertNotIn("fixture-password", err.getvalue())
                self.assertNotIn("fixture-query", err.getvalue())
        self.assertEqual(self.argv_calls(), [])
        self.assertFalse((self.work_dir / "codex").exists())
        self.assertFalse(codex_lane.codex_home_base().exists())

    def test_an_endpoint_from_the_environment_is_checked_and_cli_override_takes_precedence(self):
        self.write_packet("foundation", "native-clients")
        with mock.patch.dict(os.environ, {"OMNIROUTE_BASE_URL": "https://example.invalid/v1"}), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.run_lane(["--provider", "omniroute"]), 2)
        self.assertIn("loopback", err.getvalue().lower())
        self.assertEqual(self.argv_calls(), [])
        with mock.patch.dict(os.environ, {"OMNIROUTE_BASE_URL": "https://example.invalid/v1"}):
            self.assertEqual(self.run_lane(["--provider", "omniroute", "--omniroute-base-url", self.ENDPOINT]), 0)
        [argv] = self.argv_calls()
        self.assertFalse(any("example.invalid" in value for value in argv))
        self.assertTrue(any(value.startswith("model_providers.omniroute.base_url=")
                            and self.ENDPOINT in value for value in argv))

    def test_the_endpoint_is_canonical_in_command_environment_and_provenance(self):
        self.write_packet("foundation", "native-clients")
        raw = "HTTP://LOCALHOST:021128/v1/"
        canonical = "http://localhost:21128/v1"
        seen = []
        real_popen = subprocess.Popen

        def capture_popen(cmd, **kwargs):
            if "-o" in cmd:
                seen.append(kwargs["env"])
            return real_popen(cmd, **kwargs)

        with mock.patch.object(codex_lane.subprocess, "Popen", side_effect=capture_popen):
            self.assertEqual(self.run_lane(["--provider", "omniroute", "--omniroute-base-url", raw]), 0)
        [argv] = self.argv_calls()
        base_config = next(value for value in argv if value.startswith("model_providers.omniroute.base_url="))
        self.assertEqual(base_config.split("=", 1)[1].strip('\"\''), canonical)
        self.assertEqual(seen[0]["OMNIROUTE_BASE_URL"], canonical)
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["provenance"]["provider_base_url"], canonical)

    def test_only_the_keyless_endpoint_is_added_to_the_blind_child_environment(self):
        self.write_packet("foundation", "native-clients")
        seen = []
        real_popen = subprocess.Popen

        def capture_popen(cmd, **kwargs):
            if "-o" in cmd:
                seen.append(kwargs)
            return real_popen(cmd, **kwargs)

        with mock.patch.dict(os.environ, {
            "OMNIROUTE_BASE_URL": self.ENDPOINT, "OMNIROUTE_API_KEY": "fixture-omniroute-value",
            "OPENAI_API_KEY": "fixture-openai-value", "CODEX_API_KEY": "fixture-codex-value",
            "UNRELATED_PROVIDER_EXTRA": "fixture-extra-value", "OMNIROUTE_MEMORY": "fixture-memory-value",
        }), mock.patch.object(codex_lane.subprocess, "Popen", side_effect=capture_popen):
            self.assertEqual(self.run_lane(["--provider", "omniroute"]), 0)
        [child] = seen
        env = child["env"]
        self.assertEqual(env["OMNIROUTE_BASE_URL"], self.ENDPOINT)
        baseline = {
            "PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "SSL_CERT_FILE", "SSL_CERT_DIR",
            "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "no_proxy",
            "all_proxy", "CODEX_HOME", "HOME", "TMPDIR",
        }
        self.assertLessEqual({key for key in env if not key.startswith("CODEX_FAKE_")},
                             baseline | {"OMNIROUTE_BASE_URL"})
        self.assertFalse({"OMNIROUTE_API_KEY", "OPENAI_API_KEY", "CODEX_API_KEY", "UNRELATED_PROVIDER_EXTRA",
                          "OMNIROUTE_MEMORY"} & set(env))
        self.assertIs(child["stdin"], subprocess.DEVNULL)
        self.assertEqual(env["HOME"], str(Path(env["CODEX_HOME"]) / "home"))
        self.assertEqual(list(Path(env["HOME"]).iterdir()), [])
        self.assertEqual(list(Path(env["TMPDIR"]).iterdir()), [])

    def test_the_endpoint_allowlist_does_not_allow_environment_reads_in_the_blind_audit(self):
        events = self.work_dir / "omniroute-env-audit.jsonl"
        for command in ("printenv OMNIROUTE_BASE_URL", "printenv UNRELATED_PROVIDER_EXTRA", "env"):
            with self.subTest(command=command):
                events.write_text(json.dumps({"type": "item.completed", "item": {
                    "type": "command_execution", "command": command}}) + "\n", encoding="utf-8")
                report = audit_with_fixture_cwd(events, [str(self.repo)])
                self.assertTrue(report["flagged_commands"])

    def test_the_client_boundary_canary_preserves_prompt_utf8_bytes(self):
        # This canary proves what the runner gives its CLI, not what a live gateway forwards upstream.
        self.write_packet("foundation", "native-clients")
        prompt = self.work_dir / "canary-prompt.md"
        prompt_bytes = 'OmniRoute canary Ω café\nLiteral "$dollar" and \\backslash\nFinal newline.\n'.encode("utf-8")
        prompt.write_bytes(prompt_bytes)
        self.assertEqual(self.run_lane(["--provider", "omniroute", "--prompt", str(prompt)]), 0)
        [argv] = self.argv_calls()
        self.assertEqual(argv[-1].encode("utf-8"), prompt_bytes)

    def test_switching_from_native_to_omniroute_reruns_a_packet_and_records_the_new_provider(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        self.assertEqual(len(self.argv_calls()), 1)
        self.assertEqual(self.run_lane(), 0)
        self.assertEqual(len(self.argv_calls()), 1, "same native provider resumes the clean return")
        self.assertEqual(self.run_lane(["--provider", "omniroute"]), 0)
        self.assertEqual(len(self.argv_calls()), 2, "a provider change must rerun the packet")
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["provenance"]["provider"], "omniroute")
        self.assertEqual([row.get("provider") for row in self.usage_rows()], [None, "omniroute"])
        self.assertEqual(self.run_lane(["--provider", "omniroute"]), 0)
        self.assertEqual(len(self.argv_calls()), 2, "the same OmniRoute provider resumes the clean return")

    def test_changing_the_omniroute_endpoint_reruns_instead_of_reusing_a_packet(self):
        self.write_packet("foundation", "native-clients")
        args = ["--provider", "omniroute", "--omniroute-base-url", self.ENDPOINT]
        self.assertEqual(self.run_lane(args), 0)
        self.assertEqual(len(self.argv_calls()), 1)
        self.assertEqual(self.run_lane(args), 0)
        self.assertEqual(len(self.argv_calls()), 1, "same endpoint resumes the clean return")
        changed = "http://127.0.0.1:21129/v1"
        self.assertEqual(self.run_lane(["--provider", "omniroute", "--omniroute-base-url", changed]), 0)
        self.assertEqual(len(self.argv_calls()), 2, "an endpoint change must rerun the packet")
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["provenance"]["provider"], "omniroute")
        self.assertEqual(data["provenance"]["provider_base_url"], changed)

    def test_the_cx_model_route_is_transported_but_canonicalized_for_receipt_and_resume(self):
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(["--provider", "omniroute", "--model", "cx/gpt-6.1-sol"]), 0)
        [argv] = self.argv_calls()
        self.assertEqual(argv[argv.index("-m") + 1], "cx/gpt-6.1-sol")
        data = json.loads(self.out_path("foundation", "native-clients").read_text(encoding="utf-8"))
        self.assertEqual(data["model"]["name"], "gpt-6.1-sol")
        self.assertEqual(data["model"]["family"], "openai")
        self.assertEqual(self.run_lane(["--provider", "omniroute", "--model", "gpt-6.1-sol"]), 0)
        self.assertEqual(len(self.argv_calls()), 1, "the bare model resumes its canonical receipt")

    def test_the_sealer_accepts_legacy_native_and_current_provider_receipts(self):
        from scripts.landscape import lane_provenance_issue

        legacy = {"codex_lane_py_sha256": "a" * 64, "prompt_sha256": "b" * 64, "repo_tree_sha256": "c" * 64}
        omniroute = {**legacy, "provider": "omniroute", "provider_base_url": self.ENDPOINT,
                     "pass_through": self.PASS_THROUGH}
        accepted = [legacy, {**legacy, "provider": "native"}, omniroute]
        for provenance in accepted:
            with self.subTest(provenance=provenance):
                self.assertIsNone(lane_provenance_issue("codex", provenance))
        refused = [
            {**legacy, "provider": "unknown"},
            {**legacy, "provider": "omniroute"},
            {**omniroute, "provider_base_url": "https://example.invalid/v1"},
            {**legacy, "provider": "native", "provider_base_url": self.ENDPOINT},
            {**legacy, "provider_base_url": self.ENDPOINT},
            {**omniroute, "extra_env": "not-allowed"},
            {"codex_lane_py_sha256": "a" * 64, "prompt_sha256": "b" * 64, "provider": "native"},
            {**legacy, "provider": "native", "prompt_sha256": "malformed"},
            {**legacy, "provider": "omniroute", "provider_base_url": self.ENDPOINT},
            {**omniroute, "pass_through": "fixture-spoofed-attestation"},
            {**omniroute, "pass_through": None},
            {**legacy, "provider": "native", "pass_through": self.PASS_THROUGH},
            {**legacy, "pass_through": self.PASS_THROUGH},
        ]
        refused.extend({**omniroute, "provider_base_url": value}
                       for value in (None, False, 0, 1, [self.ENDPOINT], {"url": self.ENDPOINT}))
        for provenance in refused:
            with self.subTest(provenance=provenance):
                self.assertIsNotNone(lane_provenance_issue("codex", provenance))

    def test_provider_metadata_is_refused_on_a_claude_receipt(self):
        from scripts.landscape import lane_provenance_issue

        claude = {
            "workflow_path": "tools/sota-convergence/lane.js", "workflow_sha256": "a" * 64,
            "agentlab_commit": "b" * 40, "agent_sha256": "c" * 64, "prompt_sha256": "d" * 64,
            "transcript_audit_py_sha256": "e" * 64, "repo_tree_sha256": "f" * 64,
        }
        self.assertIsNone(lane_provenance_issue("claude", claude))
        for extra in ({"provider": "native"}, {"provider": "omniroute", "provider_base_url": self.ENDPOINT},
                      {"pass_through": self.PASS_THROUGH}):
            with self.subTest(extra=extra):
                self.assertIsNotNone(lane_provenance_issue("claude", {**claude, **extra}))


class IsolatedCodexHomeTests(CodexLaneFixture):
    """2026-09-24 blindness: --ignore-user-config does not skip $CODEX_HOME/AGENTS.md, so blind children run
    with a fresh run-scoped CODEX_HOME that links, never copies, the native auth.json, an empty HOME and only an
    allowlisted environment."""

    def homes(self):
        base = codex_lane.codex_home_base()
        return sorted(base.glob(codex_lane.codex_home_prefix(self.work_dir) + "-*")) if base.is_dir() else []

    def test_the_home_links_the_native_auth_and_children_get_only_the_allowlisted_environment(self):
        (self.native_codex / "AGENTS.md").write_text("# global instructions naming tools", encoding="utf-8")
        home = codex_lane.isolated_codex_home(self.work_dir, self.repo)
        self.assertEqual(home.parent, codex_lane.codex_home_base())
        # Outside the work dir, which holds both lanes' returns (BIND-R4-7).
        self.assertNotIn(self.work_dir.resolve(), home.parents)
        self.assertTrue((home / "auth.json").is_symlink())
        self.assertEqual(os.readlink(home / "auth.json"), str(self.native_codex / "auth.json"))
        self.assertFalse((home / "AGENTS.md").exists())
        self.assertEqual(oct(home.stat().st_mode & 0o777), "0o700")
        seen = {}

        def fake_popen(cmd, **kwargs):
            seen.update(kwargs)
            return mock.Mock(returncode=0, communicate=mock.Mock(return_value=("", "")), poll=mock.Mock(return_value=0))

        with mock.patch.dict(os.environ, {"CLAUDE_CODE_SSE_PORT": "1", "ALPACA_API_KEY_ID": "x", "LANG": "C.UTF-8"}), \
                mock.patch.object(codex_lane, "CHILD_CODEX_HOME", home), \
                mock.patch.object(codex_lane.subprocess, "Popen", side_effect=fake_popen):
            codex_lane.run_attempt(["codex", "exec"], 5)
        # The run home's in-use lock rides along to the child (round 7, ISO-R7-2).
        self.assertEqual(seen["pass_fds"], (codex_lane.IN_USE_HANDLE.fileno(),))
        env = seen["env"]
        self.assertEqual(env["CODEX_HOME"], str(home))
        # Review of #145: user Agent Skills under $HOME/.agents/skills name adopted tools; the child's HOME is empty.
        self.assertEqual(env["HOME"], str(home / "home"))
        self.assertEqual(list((home / "home").iterdir()), [])
        # Round 5, ISO-R5-2 and ISO-R5-3: no coordinator or broker variable, no stdin.
        self.assertNotIn("CLAUDE_CODE_SSE_PORT", env)
        self.assertNotIn("ALPACA_API_KEY_ID", env)
        self.assertEqual(env["LANG"], "C.UTF-8")
        self.assertIs(seen["stdin"], subprocess.DEVNULL)

    def test_each_run_gets_a_fresh_home_and_a_dry_run_writes_none(self):
        # Codex review of #145: a leftover AGENTS.md would be loaded; round 5, INT-R5-2: nothing is ever removed to
        # make a home. A dry run writes nothing but prints each child's environment (OPS-4, N7).
        first = codex_lane.isolated_codex_home(self.work_dir, self.repo)
        (first / "AGENTS.md").write_text("# leftover instructions", encoding="utf-8")
        second = codex_lane.isolated_codex_home(self.work_dir, self.repo)
        self.assertNotEqual(first, second)
        self.assertFalse((second / "AGENTS.md").exists())
        self.assertTrue((first / "AGENTS.md").exists())  # never removed
        for home in self.homes():
            shutil.rmtree(home)
        self.write_packet("foundation", "native-clients")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(self.run_lane(["--dry-run"]), 0)
        self.assertEqual(self.homes(), [])
        self.assertIn("env -i", out.getvalue())
        self.assertIn("CODEX_HOME=" + str(codex_lane.codex_home_base()), out.getvalue())
        self.assertIn("fresh", err.getvalue())

    def test_a_blind_run_uses_a_home_and_removes_the_credential_link_after(self):
        env_log = self.work_dir.parent / "env.jsonl"
        os.environ["CODEX_FAKE_ENV_LOG"] = str(env_log)
        self.write_packet("foundation", "native-clients")
        self.assertEqual(self.run_lane(), 0)
        seen = [json.loads(line) for line in env_log.read_text(encoding="utf-8").splitlines()]
        [home] = self.homes()
        self.assertEqual(seen, [{"CODEX_HOME": str(home), "HOME": str(home / "home"), "auth_link": True}])
        self.assertFalse((home / "auth.json").is_symlink())
        self.assertIsNone(codex_lane.CHILD_CODEX_HOME)

    def test_a_base_overlapping_the_native_home_is_refused_and_nothing_is_removed(self):
        # Round 5, INT-R5-2: with the native home at, inside or around the run homes' base, nothing is created
        # and nothing is removed.
        (self.native_codex / "config.toml").write_text("model = 'x'", encoding="utf-8")
        for base in (self.native_codex, self.native_codex / "runs", self.native_codex.parent):
            with self.subTest(base=str(base)), mock.patch.dict(os.environ, {codex_lane.CODEX_HOME_BASE_ENV: str(base)}):
                with self.assertRaisesRegex(codex_lane.CodexHomeRefused, "overlap"):
                    codex_lane.isolated_codex_home(self.work_dir, self.repo)
        self.assertEqual(sorted(p.name for p in self.native_codex.iterdir()), ["auth.json", "config.toml"])
        self.assertFalse((self.native_codex / "runs").exists())

    def test_a_base_inside_the_work_dir_or_without_a_credential_is_refused(self):
        with mock.patch.dict(os.environ, {codex_lane.CODEX_HOME_BASE_ENV: str(self.work_dir / "homes")}):
            with self.assertRaisesRegex(codex_lane.CodexHomeRefused, "overlaps"):
                codex_lane.isolated_codex_home(self.work_dir, self.repo)
        (self.native_codex / "auth.json").unlink()
        for key in ("CODEX_API_KEY", "OPENAI_API_KEY"):
            os.environ.pop(key, None)
        with self.assertRaisesRegex(codex_lane.CodexHomeRefused, "no native Codex credential"):
            codex_lane.isolated_codex_home(self.work_dir, self.repo)
        self.write_packet("foundation", "native-clients")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.run_lane(), 2)
        self.assertIn("codex login", err.getvalue())
        self.assertFalse((self.work_dir / "codex" / "foundation__native-clients.json").exists())

    def test_an_api_key_never_reaches_a_child(self):
        # Round 6, ISO-R6-4: the model's shell inherits the child's variables, so a blind child gets no key; an API key
        # alone does not satisfy the credential check.
        with mock.patch.dict(os.environ, {"CODEX_API_KEY": "k", "OPENAI_API_KEY": "o"}):
            home = codex_lane.isolated_codex_home(self.work_dir, self.repo)
            (home / "auth.json").unlink()
            self.assertFalse({"CODEX_API_KEY", "OPENAI_API_KEY"} & set(codex_lane.child_env(home)))
            (self.native_codex / "auth.json").unlink()
            self.assertIn("codex login --with-api-key", codex_lane.codex_home_issue(self.work_dir, self.repo))

    def test_round6_isolation_details(self):
        # Round 6: a fresh TMPDIR (REG6-3), no API key forwarded (ISO-R6-4), stale links swept under the
        # shared lock (ISO-R6-1), proxy credentials redacted in printed output (ISO-R6-5).
        home = codex_lane.isolated_codex_home(self.work_dir, self.repo)
        env = codex_lane.child_env(home)
        self.assertEqual(env["TMPDIR"], str(home / "tmp"))
        self.assertEqual(list((home / "tmp").iterdir()), [])
        (home / "auth.json").unlink()
        with mock.patch.dict(os.environ, {"CODEX_API_KEY": "k", "OPENAI_API_KEY": "o"}):
            env = codex_lane.child_env(home)
        self.assertEqual((env.get("CODEX_API_KEY"), env.get("OPENAI_API_KEY")), (None, None))
        stale = codex_lane.isolated_codex_home(self.work_dir, self.repo)
        self.assertTrue((stale / "auth.json").is_symlink())
        # A live holder of the in-use lock (a child of a killed run) keeps its link (round 7, ISO-R7-2) ...
        codex_lane.sweep_stale_links(self.work_dir)
        self.assertTrue((stale / "auth.json").is_symlink())
        # ... and once no process holds it, the next run's sweep removes it.
        codex_lane.IN_USE_HANDLE.close()
        codex_lane.IN_USE_HANDLE = None
        codex_lane.sweep_stale_links(self.work_dir)
        self.assertFalse((stale / "auth.json").is_symlink())
        self.assertTrue((self.native_codex / "auth.json").is_file())
        self.assertEqual(codex_lane.redact_userinfo("http://user:secret@proxy:3128"), "http://***@proxy:3128")
        # Round 7, ISO-R7-6: scheme-less, and a password holding '@'.
        self.assertEqual(codex_lane.redact_userinfo("user:pass@proxy:3128"), "***@proxy:3128")
        self.assertEqual(codex_lane.redact_userinfo("socks5h://user:p@ss@proxy:1080"), "socks5h://***@proxy:1080")
        self.assertEqual(codex_lane.redact_userinfo("/usr/bin:/bin"), "/usr/bin:/bin")
        self.assertEqual(codex_lane.codex_home_lock(self.work_dir).parent, codex_lane.codex_home_base())
        # Round 7, ISO-R7-8: the homes' base is private.
        self.assertEqual(oct(codex_lane.codex_home_base().stat().st_mode & 0o777), "0o700")

    def test_the_audit_reads_the_raw_command_text(self):
        # Round 8, REG8-1: a narrower reading of what bash expands hid reads; the raw text is matched. REG8-3: the
        # bare word CODEX_HOME in a search is benign, reading the environment is not.
        events = self.work_dir / "active-events.jsonl"
        commands = {"/bin/bash -lc \"rg -n CODEX_HOME docs\"": False,
                    "/bin/bash -lc \"rg -n 'CODEX_HOME' docs\"": False,
                    "/bin/bash -lc 'cat $(dirname x)/y'": True,
                    "/bin/bash -lc \"echo \\\"it's\\\" $(pwd)\"": True,
                    "/bin/bash -lc \"cat <<EOF\n$(cat evidence/x)\nEOF\"": True,
                    "/bin/bash -c \"sh -c 'ls $CODEX_HOME'\"": True,
                    "/bin/bash -lc 'printenv CODEX_HOME | xargs dirname'": True,
                    "/bin/bash -lc 'env | grep HOME'": True,
                    "/bin/bash -lc 'rg -l winner ${TMPDIR}'": True,
                    # A known low (REG7-3): a literal backtick in a single-quoted pattern is voided too.
                    "/bin/bash -lc \"rg -n '`component_id`' docs\"": True}
        for command, flagged in commands.items():
            events.write_text(json.dumps({"type": "item.completed", "item": {
                "type": "command_execution", "command": command}}) + "\n", encoding="utf-8")
            report = audit_with_fixture_cwd(events, [str(self.repo)])
            self.assertEqual(bool(report["flagged_commands"]), flagged, command)

    def test_round7_a_proxy_with_credentials_is_refused_for_a_blind_run(self):
        # ISO-R7-5: every child variable reaches the model's shell.
        with mock.patch.dict(os.environ, {"HTTPS_PROXY": "http://user:secret@proxy.example:3128"}):
            issue = codex_lane.codex_home_issue(self.work_dir, self.repo)
        self.assertIn("carries credentials", issue)
        self.assertNotIn("secret", issue)
        with mock.patch.dict(os.environ, {"HTTPS_PROXY": "http://proxy.example:3128", "NO_PROXY": "a@b"}):
            self.assertIsNone(codex_lane.codex_home_issue(self.work_dir, self.repo))

    def test_a_dry_run_refuses_a_home_it_could_not_set_up(self):
        # Round 6, ISO-R6-5: the refusals run before the dry run and create nothing.
        (self.native_codex / "auth.json").unlink()
        for key in ("CODEX_API_KEY", "OPENAI_API_KEY"):
            os.environ.pop(key, None)
        self.write_packet("foundation", "native-clients")
        with contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.run_lane(["--dry-run"]), 2)
        self.assertIn("codex login", err.getvalue())
        self.assertFalse(codex_lane.codex_home_base().exists())

    def test_the_codex_home_and_command_substitution_are_flagged(self):
        # Round 6, ISO-R6-2.
        events = self.work_dir / "home-events.jsonl"
        events.write_text("".join(json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": command}}) + "\n"
            for command in ("ls $CODEX_HOME", "cat $(dirname x)/y", "cat `pwd`/y", "rg -l winner ${TMPDIR}",
                            "cp -r $SSL_CERT_DIR .")), encoding="utf-8")
        report = codex_lane.blind_audit(events, [str(self.repo)])
        reasons = " ".join(reason for item in report["flagged_commands"] for reason in item["reasons"])
        self.assertIn("names the Codex home", reasons)
        self.assertEqual(reasons.count("command substitution"), 2)
        self.assertEqual(reasons.count("inherited directory variable"), 2)  # REG6-3
        self.assertEqual(len(report["flagged_commands"]), 5)

    def test_a_work_dir_inside_a_repository_is_refused(self):
        # Independent review of #145, round 4, OPS-6: the recipe's rule, enforced.
        (self.work_dir / ".git").mkdir()
        self.write_packet("foundation", "native-clients")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(self.run_lane(), 2)
        self.assertIn("is inside the git repository", err.getvalue())

    def test_parameter_expansion_is_flagged(self):
        # Independent review of #145, BIND-R4-7: ${...} builds a path the event does not show.
        events = self.work_dir / "expansion.jsonl"
        events.write_text(json.dumps({"type": "item.completed", "item": {
            "type": "command_execution", "command": "bash -lc 'cat \"${CODEX_HOME%/*}/x.json\"'"}}) + "\n",
            encoding="utf-8")
        report = codex_lane.blind_audit(events, [str(self.repo)])
        self.assertTrue(any("parameter expansion" in reason for item in report["flagged_commands"]
                            for reason in item["reasons"]), report)


class ExactProvenanceResumeTests(CodexLaneFixture):
    """Round-8 review of #145: resume needs the recorded provenance to equal the current one exactly; a return
    carrying an extra or changed provenance field is not resumed."""

    def test_a_return_with_an_extra_provenance_field_reruns(self):
        packet_path = self.write_packet("foundation", "native-clients")
        packet_sha256 = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        current = codex_lane.lane_provenance(FIXTURE_PROMPT, self.repo)
        out_path = self.out_path("foundation", "native-clients")
        out_path.parent.mkdir()
        existing = canned_return(packet_sha256=packet_sha256, provenance={**current, "extra": "1" * 64},
                                 model={"name": "gpt-6-astra", "effort": "high", "family": "openai"})
        out_path.write_text(json.dumps(existing), encoding="utf-8")
        self.assertFalse(codex_lane.existing_output_is_valid(out_path, "foundation", "native-clients",
                                                              packet_sha256, current))
        existing["provenance"] = current
        out_path.write_text(json.dumps(existing), encoding="utf-8")
        self.assertTrue(codex_lane.existing_output_is_valid(out_path, "foundation", "native-clients",
                                                             packet_sha256, current))


class IncrementalFailuresTests(unittest.TestCase):
    """An interrupted runner keeps the failure observations already made, without launching children."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.repo = self.base / "repo"
        self.work_dir = self.base / "work"
        self.codex_dir = self.work_dir / "codex"
        self.repo.mkdir()
        (self.work_dir / "packets").mkdir(parents=True)
        self.codex_dir.mkdir()
        self.failures_path = self.codex_dir / codex_lane.FAILURES_NAME
        self.provenance = {"repo_tree_sha256": "a" * 64}
        codex_lane.STOP.clear()
        self.addCleanup(codex_lane.STOP.clear)

    def pending(self, *layers):
        return [("foundation", layer, self.work_dir / "packets" / f"foundation__{layer}.json", "b" * 64,
                 self.codex_dir / f"foundation__{layer}.json") for layer in layers]

    def run_pending(self, pending, attempts, layers=None):
        args = codex_lane.argparse.Namespace(allow_git_history=True, jobs=1, layers=layers,
                                            effort="high", model=None, provider="native",
                                            omniroute_base_url=None, timeout=1)
        clean_audit = {"commands": 0, "web_search": 0, "mcp_tool_calls": 0, "flagged_commands": []}
        with mock.patch.object(codex_lane, "run_attempt", side_effect=attempts), \
                mock.patch.object(codex_lane, "write_strict_schema", return_value=FIXTURE_SCHEMA), \
                mock.patch.object(codex_lane, "fill_prompt", return_value="fixture prompt"), \
                mock.patch.object(codex_lane, "build_command", return_value=["mocked-codex"]), \
                mock.patch.object(codex_lane, "blind_audit", return_value=clean_audit), \
                mock.patch.object(codex_lane, "tree_sha256", return_value=self.provenance["repo_tree_sha256"]), \
                contextlib.redirect_stderr(io.StringIO()):
            return codex_lane.run_pending(args, self.work_dir, self.repo, "fixture prompt", FIXTURE_SCHEMA,
                                          self.codex_dir, self.codex_dir / "events", self.codex_dir / "usage.jsonl",
                                          pending, self.provenance)

    def test_completed_failure_survives_interruption_before_the_next_layer(self):
        # CC's 2026-10-10 adjudication cites the end-only write at upstream main
        # 9d4c00cd tools/sota-convergence/codex_lane.py:1538-1556.
        failed = {"exit_code": 7, "timed_out": False, "stdout": "", "elapsed": 0.01}
        with self.assertRaises(SystemExit) as stopped:
            self.run_pending(self.pending("a-layer", "b-layer"), [failed, failed, SystemExit(143)])
        self.assertEqual(stopped.exception.code, 143)
        self.assertTrue(self.failures_path.is_file(), "the completed failure must be durable before b-layer starts")
        self.assertEqual(json.loads(self.failures_path.read_text(encoding="utf-8")), {
            "lane": "codex", "failures": [{"catalog": "foundation", "layer_id": "a-layer",
                                             "reason": "failed after retry: codex exec exited 7"},
                                            {"catalog": "foundation", "layer_id": "b-layer",
                                             "reason": "execution or audit interrupted: SystemExit"}]})
        self.assertFalse((self.codex_dir / "foundation__b-layer.json").exists())

    def test_pending_layers_are_durable_before_the_first_launch(self):
        def interrupted_before_child(*_args, **_kwargs):
            self.assertTrue(self.failures_path.is_file(), "the initial snapshot must precede child launch")
            saved = json.loads(self.failures_path.read_text(encoding="utf-8"))
            self.assertEqual([(entry["catalog"], entry["layer_id"]) for entry in saved["failures"]],
                             [("foundation", "a-layer")])
            self.assertIn("unfinished layer", saved["failures"][0]["reason"])
            raise SystemExit(143)

        with self.assertRaises(SystemExit):
            self.run_pending(self.pending("a-layer"), interrupted_before_child)

    def test_a_clean_signal_stop_keeps_the_unfinished_layer_snapshot(self):
        def signal_stop(*_args, **_kwargs):
            codex_lane.STOP.set()
            return {"exit_code": None, "timed_out": False, "stdout": "", "stderr": "",
                    "elapsed": 0.01, "stopped": True}

        self.run_pending(self.pending("a-layer"), signal_stop)
        self.assertTrue(self.failures_path.is_file(), "signal cleanup must retain the partial snapshot")
        saved = json.loads(self.failures_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["failures"][0]["layer_id"], "a-layer")
        self.assertIn("unfinished layer", saved["failures"][0]["reason"])

    def test_a_selected_rerun_retains_unselected_failures_when_interrupted(self):
        kept = {"catalog": "foundation", "layer_id": "workers", "reason": "failed after retry: timed out"}
        selected = {"catalog": "foundation", "layer_id": "a-layer", "reason": "old selected failure"}
        self.failures_path.write_text(json.dumps({"lane": "codex", "failures": [selected, kept]}), encoding="utf-8")

        def interrupted_before_child(*_args, **_kwargs):
            saved = json.loads(self.failures_path.read_text(encoding="utf-8"))["failures"]
            self.assertIn(kept, saved)
            pending = next(entry for entry in saved if entry["layer_id"] == "a-layer")
            self.assertIn("unfinished layer", pending["reason"])
            raise SystemExit(143)

        with self.assertRaises(SystemExit):
            self.run_pending(self.pending("a-layer"), interrupted_before_child, layers="foundation__a-layer")

    def test_preexecution_stop_cannot_leave_a_stale_pending_return(self):
        pending = self.pending("a-layer", "b-layer")
        for _catalog, _layer, _packet, _sha, out_path in pending:
            out_path.write_text('{"old": "stale"}')
        codex_lane.STOP.set()
        self.run_pending(pending, AssertionError("no child should start after stop"))
        for _catalog, layer, _packet, _sha, out_path in pending:
            with self.subTest(layer=layer):
                self.assertFalse(out_path.exists(), "queued pending returns must be invalidated before execution")
        recorder = load_module("record_verdicts_stopped_pending", "record_verdicts.py")
        failures = recorder.load_lane_failures(self.work_dir)
        self.assertEqual(recorder.missing_outcome(failures, "codex", "foundation", "a-layer")["outcome"], "failed")


class Full1cBoundaryTests(CodexLaneFixture):
    """Neutral local markers and native-journal simulation; never read a user/system file."""

    def setUp(self):
        super().setUp()
        self.write_packet("foundation", "native-clients")
        self.marker = self.repo.parent / "outside-marker.txt"
        self.marker.write_text("OUTSIDE_MARKER\n", encoding="utf-8")
        (self.repo / "inside-marker.txt").write_text("INSIDE_MARKER\n", encoding="utf-8")
        self.options = ["--provider", "omniroute", "--omniroute-base-url", "http://127.0.0.1:21128/v1"]

    def python_command(self, source):
        return shlex.join(["python3", "-B", "-c", source])

    def set_command(self, command):
        outer = shlex.join(["/bin/bash", "-lc", command])
        self.events_file.write_text(CANNED_EVENTS + "\n" + json.dumps({"type": "item.completed", "item": {
            "id": "item_0", "type": "command_execution", "command": outer,
            "aggregated_output": "OUTSIDE_MARKER\n", "exit_code": 0, "status": "completed"}}) + "\n")
        return outer

    def audit(self, command):
        path = self.work_dir / "probe-events.jsonl"
        path.write_text(json.dumps({"type": "item.completed", "item": {
            "id": "probe", "type": "command_execution", "command": command,
            "aggregated_output": "OUTSIDE_MARKER\n", "exit_code": 0, "status": "completed"}}) + "\n")
        return audit_with_fixture_cwd(path, [str(self.repo), str(self.work_dir / "packets")])

    def assert_real_marker_read(self, command):
        result = subprocess.run(["/bin/sh", "-c", command], cwd=self.repo, capture_output=True, text=True,
                                timeout=10, env={"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OUTSIDE_MARKER", result.stdout)

    def assert_quarantined(self, command):
        self.set_command(command)
        with contextlib.redirect_stderr(io.StringIO()):
            code = self.run_lane(self.options)
        self.assertEqual(code, 1)
        out = self.out_path("foundation", "native-clients")
        self.assertFalse(out.exists(), "a boundary violation must never be promoted")
        self.assertTrue(out.with_name(out.name + ".audit-flagged").exists())
        recorder = load_module("record_verdicts_full1c", "record_verdicts.py")
        failures = recorder.load_lane_failures(self.work_dir)
        self.assertEqual(recorder.missing_outcome(failures, "codex", "foundation", "native-clients")["outcome"],
                         "failed")

    def computed_readers(self):
        encoded = os.fsencode("../outside-marker.txt").hex()
        return [self.python_command("import io; print(io.FileIO(bytes.fromhex(" + repr(encoded) + ")).read())"),
                self.python_command("import io; print(io.FileIO(chr(46)+chr(46)+chr(47)+'outside-marker.txt').read())")]

    def test_computed_unmodeled_readers_fail_audit_and_promotion(self):
        for command in self.computed_readers():
            with self.subTest(command=command):
                self.assert_real_marker_read(command)
                self.assertTrue(self.audit(command)["flagged_commands"])

    def test_computed_unmodeled_readers_never_promote(self):
        for command in self.computed_readers():
            with self.subTest(command=command):
                self.assert_quarantined(command)

    def test_unverified_imported_reader_calls_are_not_assumed_pure(self):
        (self.repo / "outside_reader.py").write_text(
            "def read(path):\n with open(path) as handle: return handle.read()\n")
        command = self.python_command("import outside_reader; print(outside_reader.read(bytes.fromhex(" +
                                      repr(os.fsencode("../outside-marker.txt").hex()) + ")))")
        self.assert_real_marker_read(command)
        self.assertTrue(self.audit(command)["flagged_commands"])
        self.assert_quarantined(command)

    def test_imported_reader_aliases_are_checked_at_their_call_sites(self):
        (self.repo / "outside_reader.py").write_text(
            "def read(path):\n with open(path) as handle: return handle.read()\n")
        encoded = repr(os.fsencode("../outside-marker.txt").hex())
        for source in ("from io import FileIO as reader; print(reader(bytes.fromhex(" + encoded + ")).read())",
                       "from outside_reader import read as reader; print(reader(bytes.fromhex(" + encoded + ")))"):
            with self.subTest(alias=source):
                command = self.python_command(source)
                self.assert_real_marker_read(command)
                self.assertTrue(self.audit(command)["flagged_commands"])
                self.assert_quarantined(command)

    def test_imported_json_callback_paths_are_not_treated_as_pure_data(self):
        (self.repo / "outside_reader.py").write_text(
            "def hook(value):\n with open('../outside-marker.txt') as handle: return handle.read()\n")
        for source in ("import json, outside_reader; print(json.loads('{}', object_hook=outside_reader.hook))",
                       "import json, outside_reader; print(json.dumps(object(), default=outside_reader.hook))"):
            with self.subTest(callback=source):
                command = self.python_command(source)
                self.assert_real_marker_read(command)
                self.assertTrue(self.audit(command)["flagged_commands"])
                self.assert_quarantined(command)

    def encoded_urls(self):
        from urllib.parse import quote
        return ["file:" + quote(str(self.marker), safe=""),
                "file:" + str(self.repo) + "/%2e%2e/outside-marker.txt"]

    def test_encoded_local_urls_fail_audit_and_promotion(self):
        for url in self.encoded_urls():
            with self.subTest(url=url):
                command = self.python_command("import urllib.request; print(urllib.request.urlopen(" + repr(url) +
                                              ").read())")
                self.assert_real_marker_read(command)
                self.assertTrue(self.audit(command)["flagged_commands"])

    def test_encoded_local_urls_never_promote(self):
        for url in self.encoded_urls():
            with self.subTest(url=url):
                self.assert_quarantined(self.python_command(
                    "import urllib.request; print(urllib.request.urlopen(" + repr(url) + ").read())"))

    def test_local_url_authority_and_encoding_forms_fail_closed(self):
        for url in ("file://remote-host/inside-marker.txt", "file:///tmp/%zz", "file:inside-marker.txt",
                    "file:///tmp/%00", "local:///tmp/inside-marker.txt", "file:///tmp/inside-marker.txt?x=1"):
            with self.subTest(url=url):
                self.assertTrue(self.audit(self.python_command(
                    "import urllib.request; print(urllib.request.urlopen(" + repr(url) + ").read())"))["flagged_commands"])

    def test_encoded_in_tree_file_url_remains_approved(self):
        from urllib.parse import quote
        url = "file:" + quote(str(self.repo / "inside-marker.txt"), safe="")
        command = self.python_command("import urllib.request; print(urllib.request.urlopen(" + repr(url) + ").read())")
        self.assertEqual(self.audit(command)["flagged_commands"], [])

    def sed_commands(self):
        (self.repo.parent / "outside-program.txt").write_text("r../outside-marker.txt\n")
        return ["sed -n 'r../outside-marker.txt' inside-marker.txt",
                "sed -n 'R../outside-marker.txt' inside-marker.txt",
                shlex.join(["sed", "-n", "r" + str(self.marker), "inside-marker.txt"]),
                "sed -n -f../outside-program.txt inside-marker.txt",
                "sed -n --file=../outside-program.txt inside-marker.txt"]

    def test_sed_source_and_script_files_fail_audit_and_promotion(self):
        for command in self.sed_commands():
            with self.subTest(command=command):
                self.assert_real_marker_read(command)
                self.assertTrue(self.audit(command)["flagged_commands"])

    def test_sed_source_and_script_files_never_promote(self):
        for command in self.sed_commands():
            with self.subTest(command=command):
                self.assert_quarantined(command)

    def test_sed_unmodeled_source_and_attached_script_reads_are_refused(self):
        for command in ("sed '1e cat ../outside-marker.txt' inside-marker.txt",
                        "sed -n 's/a/b/e' inside-marker.txt", "sed -n -finside-marker.txt inside-marker.txt",
                        "sed -n 'p;r../outside-marker.txt' inside-marker.txt"):
            with self.subTest(command=command):
                self.assertTrue(self.audit(command)["flagged_commands"])

    def test_packet_symlink_read_is_refused_before_promotion(self):
        link = self.work_dir / "packets" / "marker-link"
        link.symlink_to(self.marker)
        command = shlex.join(["cat", str(link)])
        self.assert_real_marker_read(command)
        self.assertTrue(self.audit(command)["flagged_commands"])

    def test_packet_symlink_never_promotes_a_verdict(self):
        link = self.work_dir / "packets" / "marker-link"
        link.symlink_to(self.marker)
        command = shlex.join(["cat", str(link)])
        self.set_command(command)
        with contextlib.redirect_stderr(io.StringIO()):
            code = self.run_lane(self.options)
        self.assertNotEqual(code, 0)
        self.assertFalse(self.out_path("foundation", "native-clients").exists())

    def test_confined_packet_file_read_remains_approved(self):
        command = shlex.join(["cat", str(self.work_dir / "packets" / "foundation__native-clients.json")])
        self.assertEqual(self.audit(command)["flagged_commands"], [])

    def test_repository_symlink_remains_a_prelaunch_refusal(self):
        (self.repo / "marker-link").symlink_to(self.marker)
        self.set_command("cat marker-link")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_lane(self.options), 2)
        self.assertEqual(self.argv_calls(), [])

    def test_audit_interruption_is_durable_failed_at_the_consumer(self):
        self.set_command("cat inside-marker.txt")
        with mock.patch.object(codex_lane, "blind_audit", side_effect=RuntimeError("neutral audit interruption")), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(RuntimeError):
            self.run_lane(self.options)
        self.assertFalse(self.out_path("foundation", "native-clients").exists())
        recorder = load_module("record_verdicts_interrupted", "record_verdicts.py")
        failures = recorder.load_lane_failures(self.work_dir)
        outcome = recorder.missing_outcome(failures, "codex", "foundation", "native-clients")
        self.assertEqual(outcome["outcome"], "failed")
        self.assertIn("RuntimeError", " ".join(outcome["reasons"]))

    def test_failure_snapshot_interruption_after_promotion_removes_the_return(self):
        self.set_command("cat inside-marker.txt")
        write = codex_lane._write_failure_snapshot
        def interrupted_clear(path, failures, *args, **kwargs):
            if not failures and self.out_path("foundation", "native-clients").exists():
                raise RuntimeError("neutral snapshot interruption")
            return write(path, failures, *args, **kwargs)
        with mock.patch.object(codex_lane, "_write_failure_snapshot", side_effect=interrupted_clear), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(RuntimeError):
            self.run_lane(self.options)
        self.assertFalse(self.out_path("foundation", "native-clients").exists())
        recorder = load_module("record_verdicts_snapshot_interrupted", "record_verdicts.py")
        outcome = recorder.missing_outcome(recorder.load_lane_failures(self.work_dir),
                                         "codex", "foundation", "native-clients")
        self.assertEqual(outcome["outcome"], "failed")
        self.assertIn("RuntimeError", " ".join(outcome["reasons"]))

    def test_harmless_sed_and_in_tree_python_reads_still_promote(self):
        for command in ["sed -n '1,2p' inside-marker.txt",
                        self.python_command("import io; print(io.FileIO('inside-marker.txt').read())")]:
            with self.subTest(command=command):
                self.assertEqual(self.audit(command)["flagged_commands"], [])
                self.set_command(command)
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(self.run_lane(self.options), 0)
                self.assertFalse((self.work_dir / "codex" / codex_lane.FAILURES_NAME).exists(),
                                 "successful audited promotion clears durable unfinished entries")


class NativeCwdCaptureTests(CodexLaneFixture):
    """Native command history binds cwd for live and resumed verdict attempts; no model is called."""

    def setUp(self):
        super().setUp()
        self.write_packet("foundation", "native-clients")
        command = shlex.join(["/bin/bash", "-lc", "cat evidence/receipt.json"])
        self.events_file.write_text(CANNED_EVENTS + "\n" + json.dumps({"type": "item.completed", "item": {
            "id": "item_0", "type": "command_execution", "command": command,
            "cwd": str(self.repo), "workdir": str(self.repo),
            "aggregated_output": "fixture receipt\n", "exit_code": 0, "status": "completed"}}) + "\n",
            encoding="utf-8")
        self.options = ["--provider", "omniroute", "--omniroute-base-url", "http://127.0.0.1:21128/v1"]

    def run_native_fixture(self):
        with contextlib.redirect_stderr(io.StringIO()):
            return self.run_lane(self.options)

    def test_launch_root_is_accepted_with_native_cwd_and_resumes_without_another_child(self):
        self.assertEqual(self.run_native_fixture(), 0, "a native-recorded launch cwd must bind the relative read")
        calls = self.argv_calls()
        self.assertEqual(len(calls), 1)
        self.assertNotIn("--ephemeral", calls[0])
        self.assertTrue(self.out_path("foundation", "native-clients").is_file())
        self.assertEqual(self.run_native_fixture(), 0)
        self.assertEqual(self.argv_calls(), calls, "resume must rebind retained native evidence without another child")

    def test_missing_or_mismatched_native_evidence_never_uses_model_cwd(self):
        for mode in ("missing", "mismatched_argv", "mismatched_thread", "legacy", "ambiguous", "malformed",
                     "mismatched_session"):
            with self.subTest(mode=mode):
                os.environ["CODEX_FAKE_NATIVE_JOURNAL_MODE"] = mode
                self.assertEqual(self.run_native_fixture(), 1)
                self.assertFalse(self.out_path("foundation", "native-clients").exists())
                audit = json.loads((self.work_dir / "codex" / codex_lane.AUDIT_NAME).read_text(encoding="utf-8"))
                self.assertTrue(audit["layers"]["foundation__native-clients"]["flagged_commands"])

    def test_native_workdir_outside_the_launch_root_is_refused(self):
        os.environ["CODEX_FAKE_NATIVE_CWD"] = "/outside"
        self.assertEqual(self.run_native_fixture(), 1)
        self.assertFalse(self.out_path("foundation", "native-clients").exists())
        audit = json.loads((self.work_dir / "codex" / codex_lane.AUDIT_NAME).read_text(encoding="utf-8"))
        reasons = [reason for item in audit["layers"]["foundation__native-clients"]["flagged_commands"]
                   for reason in item["reasons"]]
        self.assertTrue(any("working directory outside" in reason for reason in reasons), reasons)

    def test_resume_with_missing_or_corrupt_native_capture_reruns_the_child(self):
        capture = self.work_dir / "codex" / "events" / "foundation__native-clients.native-cwd.json"
        for damage in ("missing", "invalid_json", "changed_events", "changed_capture"):
            with self.subTest(damage=damage):
                self.assertEqual(self.run_native_fixture(), 0)
                before = len(self.argv_calls())
                if damage == "missing":
                    capture.unlink()
                elif damage == "invalid_json":
                    capture.write_text("{", encoding="utf-8")
                else:
                    data = json.loads(capture.read_text(encoding="utf-8"))
                    if damage == "changed_events":
                        data["events_sha256"] = "0" * 64
                    else:
                        data["captures"][0]["snapshot"]["commands"][0]["cwd"] = "file:///outside"
                    capture.write_text(json.dumps(data), encoding="utf-8")
                self.assertEqual(self.run_native_fixture(), 0)
                self.assertEqual(len(self.argv_calls()), before + 1,
                                 "a kept return without intact independent cwd evidence must rerun")

    def test_retry_keeps_an_unsafe_cwd_from_the_first_failed_attempt(self):
        os.environ["CODEX_FAKE_FAIL_ATTEMPTS"] = "1"
        os.environ["CODEX_FAKE_NATIVE_CWD_MAP"] = json.dumps({"1": "/outside"})
        self.assertEqual(self.run_native_fixture(), 1)
        self.assertEqual(len(self.argv_calls()), 2)
        self.assertFalse(self.out_path("foundation", "native-clients").exists())
        audit = json.loads((self.work_dir / "codex" / codex_lane.AUDIT_NAME).read_text(encoding="utf-8"))
        reasons = [reason for item in audit["layers"]["foundation__native-clients"]["flagged_commands"]
                   for reason in item["reasons"]]
        self.assertTrue(any("working directory outside" in reason for reason in reasons), reasons)

    def test_unfinished_command_start_is_unverified_and_a_completed_pair_counts_once(self):
        path = self.work_dir / "unfinished.jsonl"
        item = {"id": "item_0", "type": "command_execution", "status": "in_progress",
                "command": shlex.join(["/bin/bash", "-lc", "cat /srv/outside.txt"])}
        rows = [{"type": "thread.started", "thread_id": "fixture-thread"},
                {"type": "item.started", "item": item}]
        roots = [str(self.repo), str(self.work_dir / "packets")]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        audit = codex_lane.blind_audit(path, roots)
        self.assertEqual(audit["commands"], 1)
        self.assertTrue(audit["flagged_commands"], "an unfinished command has no completed native cwd evidence")

        item["command"] = shlex.join(["/bin/bash", "-lc", "cat evidence/receipt.json"])
        rows.append({"type": "item.completed", "item": {**item, "status": "completed"}})
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        audit = codex_lane.blind_audit(path, roots, cwd_records={
            "item_0": {"command": item["command"], "cwd": str(self.repo)}})
        self.assertEqual(audit["commands"], 1)
        self.assertEqual(audit["flagged_commands"], [])

    def test_retry_keeps_an_unfinished_command_from_the_first_failed_attempt(self):
        os.environ["CODEX_FAKE_FAIL_ATTEMPTS"] = "1"
        os.environ["CODEX_FAKE_UNFINISHED_ATTEMPTS"] = "1"
        os.environ["CODEX_FAKE_UNFINISHED_COMMAND"] = shlex.join(["/bin/bash", "-lc", "cat /srv/outside.txt"])
        self.assertEqual(self.run_native_fixture(), 1)
        self.assertEqual(len(self.argv_calls()), 2)
        self.assertFalse(self.out_path("foundation", "native-clients").exists())
        audit = json.loads((self.work_dir / "codex" / codex_lane.AUDIT_NAME).read_text(encoding="utf-8"))
        layer = audit["layers"]["foundation__native-clients"]
        self.assertEqual(layer["commands"], 2)
        self.assertTrue(any("unfinished" in reason for item in layer["flagged_commands"] for reason in item["reasons"]))

    def test_retry_threads_can_reuse_exec_item_ids_without_cwd_collision(self):
        os.environ["CODEX_FAKE_FAIL_ATTEMPTS"] = "1"
        self.assertEqual(self.run_native_fixture(), 0)
        self.assertEqual(len(self.argv_calls()), 2)
        events = codex_lane.parse_events((self.work_dir / "codex" / "events" / "foundation__native-clients.jsonl").read_text())
        threads = [event["thread_id"] for event in events if event.get("type") == "thread.started"]
        self.assertEqual(len(set(threads)), 2)
        audit = json.loads((self.work_dir / "codex" / codex_lane.AUDIT_NAME).read_text(encoding="utf-8"))
        self.assertEqual(audit["layers"]["foundation__native-clients"]["flagged_commands"], [])


if __name__ == "__main__":
    unittest.main()
