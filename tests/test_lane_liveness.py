"""tools/lane-liveness/lane_liveness.py: the v2.1 reports and the LIMIT-BLOCKED report.

Everything is a fixture. A stand-in replaces subprocess.run for `claude agents --json --all` (one scripted snapshot per
call) and for `systemctl`; transcripts are temporary files under a temporary CLAUDE_CONFIG_DIR; the once-only state
lives under a temporary XDG_STATE_HOME; and the clock is injected, advanced by each snapshot's sleep. The limit-stop
records copy the shape client 2.1.300 wrote on this host (measured 2026-10-15): `isApiErrorMessage: true`,
`error: rate_limit`, model `<synthetic>`, one text block.

The V21Reports tests use only seams the v2.1 script also has, and they pass against it. Each test that expects a
LIMIT line fails against v2.1, and so does the V22Change test; the tests that expect no LIMIT line guard v2.2 against
over-reporting.
"""

import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "lane-liveness" / "lane_liveness.py"
spec = importlib.util.spec_from_file_location("lane_liveness", TOOL)
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)

UTC = dt.timezone.utc
SID, SID2, SID3 = (str(uuid.UUID(int=n)) for n in (1, 2, 3))  # generated, so no session id is committed
STOP_AT = "2026-10-15T07:19:45.449Z"
SESSION_STOP = "You've hit your session limit · resets 6:20am (America/New_York)"
RESET = "2026-10-15T10:20:00Z"  # 6:20am EDT
TRAILER = [{"type": "last-prompt"}, {"type": "custom-title"}, {"type": "agent-name"}, {"type": "mode"},
           {"type": "permission-mode"}, {"type": "atis-latch"}, {"type": "pr-link"}]


def at(text):
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


class Done(Exception):
    """The stand-in client raises this when the scripted snapshots run out; it ends the monitor's endless loop."""


class Clock:
    def __init__(self, start):
        self.now = at(start)

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += dt.timedelta(seconds=seconds)


def stop(text, when=STOP_AT, uuid="stop-1"):
    """A usage-limit stop as client 2.1.300 writes it."""
    return {"type": "assistant", "isApiErrorMessage": True, "error": "rate_limit", "isSidechain": False,
            "timestamp": when, "uuid": uuid, "sessionId": SID,
            "message": {"id": "msg-1", "model": "<synthetic>", "role": "assistant", "type": "message",
                        "stop_reason": "stop_sequence", "content": [{"type": "text", "text": text}]}}


def reply(text, when, uuid="reply-1"):
    """An ordinary assistant message from the model."""
    return {"type": "assistant", "isSidechain": False, "timestamp": when, "uuid": uuid, "sessionId": SID,
            "message": {"id": "msg-2", "model": "claude-opus-5-5", "role": "assistant", "type": "message",
                        "stop_reason": "end_turn", "content": [{"type": "text", "text": text}]}}


def row(state="blocked", kind="background", sid=SID, name="d4-bg", pid=4242):
    """One `claude agents --json` entry (fields from agent-view.md:785-790)."""
    entry = {"cwd": "/w", "kind": kind, "startedAt": 1792130000000, "sessionId": sid, "name": name}
    if kind == "background":
        entry.update(id="a1b2c3d4", state=state)
    if pid is not None:
        entry.update(pid=pid, status="idle")
    return entry


def events(lines):
    """The lines after the baseline, without the `[lanes] <utc> ` prefix."""
    return [line.split(" ", 2)[2] for line in lines
            if " baseline: " not in line and not line.startswith("[lanes] not on ")]


class MonitorCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.config = self.tmp / "claude-config"
        self.state_home = self.tmp / "state"
        environment = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.config),
                                                   "XDG_STATE_HOME": str(self.state_home)})
        environment.start()
        self.addCleanup(environment.stop)

    @property
    def state_file(self):
        return self.state_home / "native-agent-stack" / "lane-liveness" / "limits.json"

    def write(self, records, sid=SID, project="-w-lane", base=None):
        folder = (base or self.config / "projects") / project
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{sid}.jsonl"
        path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        return path

    def run_monitor(self, snapshots, clock, *argv):
        """Run main() over the scripted snapshots (row lists, or callables returning one); return the stdout lines."""
        queue = list(snapshots)

        def fake_run(cmd, **kwargs):
            if cmd[:2] == ["claude", "agents"]:
                if not queue:
                    raise Done
                item = queue.pop(0)
                rows = item() if callable(item) else item
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(rows), stderr="")
            if cmd[:1] == ["systemctl"]:
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            raise AssertionError(f"unexpected command {cmd!r}")

        out = io.StringIO()
        with mock.patch.object(L.subprocess, "run", fake_run), mock.patch.object(L.time, "sleep", clock.sleep), \
                mock.patch.object(L, "client_of", lambda pid: "-"), \
                mock.patch.object(L, "now_utc", clock, create=True), contextlib.redirect_stdout(out):
            with self.assertRaises(Done):
                L.main(["--interval", "60", *argv])
        return out.getvalue().splitlines()

    def limit_lines(self, lines):
        return [line for line in lines if " LIMIT-" in line]


class V21Reports(MonitorCase):
    """The v2.1 reports behave as before (these pass against the v2.1 script too)."""

    def test_v21_new_and_gone(self):
        a = row(kind="interactive", name="cc", pid=101)
        b = row(kind="interactive", name="co-op", pid=102, sid=SID2)
        lines = self.run_monitor([[a], [a, b], [b]], Clock("2026-10-15T10:00:00Z"))
        self.assertEqual(events(lines), ["NEW: co-op kind=interactive pid=102 client=-",
                                         "GONE: cc kind=interactive pid=101 client=-"])

    def test_v21_needs_input_after_two_snapshots_then_cleared(self):
        idle = row(kind="interactive", name="cc", pid=101)
        asking = dict(idle, status="waiting", waitingFor="permission prompt")
        lines = self.run_monitor([[idle], [asking], [asking], [asking], [idle]], Clock("2026-10-15T10:00:00Z"))
        self.assertEqual(events(lines), ["NEEDS-INPUT: cc kind=interactive pid=101 waiting=permission prompt",
                                         "CLEARED: cc kind=interactive pid=101"])

    def test_v21_rows_without_a_process_are_not_lanes(self):
        live = row(kind="interactive", name="cc", pid=101)
        finished = row(state="done", name="old-bg", pid=None, sid=SID2)
        lines = self.run_monitor([[live, finished], [live, finished]], Clock("2026-10-15T10:00:00Z"))
        self.assertIn(" baseline: 1 sessions, 0 units;", lines[0])
        self.assertEqual(events(lines), [])


class V22Change(MonitorCase):
    """The one v2.1 edge v2.2 changes."""

    def test_a_reply_that_is_not_an_array_is_unreadable(self):
        # v2.1 reported every session GONE on a JSON object and stopped on `null`.
        live = row(kind="interactive", name="cc", pid=101)
        lines = self.run_monitor([[live], {"error": "client not ready"}, None, [live]], Clock("2026-10-15T10:00:00Z"))
        self.assertEqual(events(lines), [])


class LimitBlocked(MonitorCase):
    def test_blocked_background_row_prints_one_line_ten_minutes_after_the_reset(self):
        self.write([reply("Working on the gate.", "2026-10-15T07:10:00.000Z"), stop(SESSION_STOP), *TRAILER])
        lines = self.run_monitor([[row()], [row()]], Clock("2026-10-15T10:29:00Z"))
        self.assertEqual(self.limit_lines(lines), [
            f"[lanes] 2026-10-15T10:30:00Z LIMIT-BLOCKED: d4-bg kind=background pid=4242 session={SID} "
            f"reset={RESET} blocked_for=600"])

    def test_a_second_snapshot_prints_nothing_more(self):
        self.write([stop(SESSION_STOP), *TRAILER])
        lines = self.run_monitor([[row()], [row()], [row()]], Clock("2026-10-15T10:30:00Z"))
        self.assertEqual(len(self.limit_lines(lines)), 1, lines)

    def test_a_restart_with_the_same_state_file_prints_nothing(self):
        self.write([stop(SESSION_STOP), *TRAILER])
        first = self.run_monitor([[row()]], Clock("2026-10-15T10:31:00Z"))
        self.assertEqual(len(self.limit_lines(first)), 1, first)
        second = self.run_monitor([[row()], [row()]], Clock("2026-10-15T10:40:00Z"))
        self.assertEqual(self.limit_lines(second), [])
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state["schema"], "lane-liveness-limits/1")
        self.assertEqual(list(state["printed"]), [f"blocked {SID} {RESET}"])
        self.assertEqual(stat.S_IMODE(self.state_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.state_file.parent.stat().st_mode), 0o700)
        self.assertEqual(sorted(path.name for path in self.state_file.parent.iterdir()), ["limits.json", "limits.lock"])

    def test_a_new_reset_prints_one_line_again(self):
        self.write([stop(SESSION_STOP), *TRAILER])
        clock = Clock("2026-10-15T10:30:00Z")

        def resumed_and_stopped_again():
            # A reply at 10:24 started a turn; at 16:00Z the session hit the limit again, resetting 4:20pm EDT.
            self.write([stop(SESSION_STOP), *TRAILER, reply("Resuming.", "2026-10-15T10:24:30.000Z", uuid="r2"),
                        stop("You've hit your session limit · resets 4:20pm (America/New_York)",
                             "2026-10-15T16:00:00.000Z", uuid="stop-2"), *TRAILER])
            clock.now = at("2026-10-15T20:30:00Z")
            return [row()]

        lines = self.run_monitor([[row()], resumed_and_stopped_again, [row()]], clock)
        self.assertEqual(events(self.limit_lines(lines)), [
            f"LIMIT-BLOCKED: d4-bg kind=background pid=4242 session={SID} reset={RESET} blocked_for=600",
            f"LIMIT-BLOCKED: d4-bg kind=background pid=4242 session={SID} reset=2026-10-15T20:20:00Z blocked_for=600"])

    def test_nothing_before_the_reset_plus_600_s(self):
        self.write([stop(SESSION_STOP), *TRAILER])
        lines = self.run_monitor([[row()], [row()], [row()]], Clock("2026-10-15T10:27:59Z"))  # 479, 539, 599 s
        self.assertEqual(self.limit_lines(lines), [])

    def test_done_and_working_rows_print_nothing(self):
        self.write([stop(SESSION_STOP), *TRAILER])
        self.write([stop(SESSION_STOP), *TRAILER], sid=SID2)
        lines = self.run_monitor([[row(state="done"), row(state="working", sid=SID2, name="other-bg")]] * 2,
                                 Clock("2026-10-15T10:31:00Z"))
        self.assertEqual(self.limit_lines(lines), [])

    def test_an_interactive_row_prints_nothing(self):
        self.write([stop(SESSION_STOP), *TRAILER])
        interactive = dict(row(kind="interactive", name="cc", pid=101), state="blocked")
        lines = self.run_monitor([[interactive]] * 2, Clock("2026-10-15T10:31:00Z"))
        self.assertEqual(self.limit_lines(lines), [])

    def test_a_later_reply_after_the_stop_prints_nothing(self):
        self.write([stop(SESSION_STOP), *TRAILER, {"type": "user", "timestamp": "2026-10-15T10:24:10.000Z"},
                    reply("Picking up where I stopped.", "2026-10-15T10:24:20.000Z"), *TRAILER])
        lines = self.run_monitor([[row()]] * 2, Clock("2026-10-15T10:31:00Z"))
        self.assertEqual(self.limit_lines(lines), [])

    def test_a_model_reply_quoting_the_stop_prints_nothing(self):
        self.write([reply(SESSION_STOP, "2026-10-15T07:19:45.449Z"), *TRAILER])
        lines = self.run_monitor([[row()]] * 2, Clock("2026-10-15T10:31:00Z"))
        self.assertEqual(self.limit_lines(lines), [])

    def test_the_date_form_resets_on_the_stated_day(self):
        self.write([stop("You've hit your weekly limit · resets Oct 20, 10am (America/New_York)",
                         "2026-10-15T03:11:56.147Z"), *TRAILER])
        lines = self.run_monitor([[row()], [row()]], Clock("2026-10-20T14:09:00Z"))
        self.assertEqual(events(self.limit_lines(lines)), [
            f"LIMIT-BLOCKED: d4-bg kind=background pid=4242 session={SID} reset=2026-10-20T14:00:00Z blocked_for=600"])

    def test_a_reset_across_the_november_change_uses_the_new_offset(self):
        # Stopped at 6pm EDT on Oct 31; 6:20am on Nov 1 is EST (UTC-5), 11:20Z. At 10:30Z, the old offset's
        # reset plus 600 s, nothing is due yet.
        self.write([stop(SESSION_STOP, "2026-10-31T22:00:00.000Z"), *TRAILER])
        lines = self.run_monitor([[row()], [row()]], Clock("2026-11-01T10:30:00Z"), "--interval", "3600")
        self.assertEqual(self.limit_lines(lines), [
            f"[lanes] 2026-11-01T11:30:00Z LIMIT-BLOCKED: d4-bg kind=background pid=4242 session={SID} "
            f"reset=2026-11-01T11:20:00Z blocked_for=600"])

    def test_a_repeated_wall_time_resolves_to_the_first_occurrence_after_the_stop(self):
        # 1:30am happens twice on Nov 1 (05:30Z EDT, 06:30Z EST); a stop at 1:45am EDT means the second one.
        self.write([stop("You've hit your session limit · resets 1:30am (America/New_York)",
                         "2026-11-01T05:45:00.000Z"), *TRAILER])
        lines = self.run_monitor([[row()]], Clock("2026-11-01T06:40:00Z"))
        self.assertEqual(events(self.limit_lines(lines)), [
            f"LIMIT-BLOCKED: d4-bg kind=background pid=4242 session={SID} reset=2026-11-01T06:30:00Z blocked_for=600"])

    def test_unparseable_reset_text_prints_limit_unparsed_once(self):
        self.write([stop("You've hit your session limit · resets 6:20am"), *TRAILER])  # no zone
        first = self.run_monitor([[row()]] * 3, Clock("2026-10-15T10:31:00Z"))
        second = self.run_monitor([[row()]] * 2, Clock("2026-10-15T11:00:00Z"))
        self.assertEqual(self.limit_lines(first), [
            f"[lanes] 2026-10-15T10:31:00Z LIMIT-UNPARSED: d4-bg kind=background pid=4242 session={SID} "
            f"at=2026-10-15T07:19:45Z"])
        self.assertEqual(self.limit_lines(second), [])

    def test_limit_unparsed_is_once_per_message_and_never_blocked(self):
        variants = ["You've hit your session limit · resets 6:20am (Mars/Olympus_Mons)",
                    "You've hit your monthly spend limit · raise it at https://claude.ai/settings/usage",
                    "You've hit your session limit · resets soon (America/New_York)"]
        clock = Clock("2026-10-15T10:31:00Z")
        script = []
        for number, text in enumerate(variants):
            def next_message(text=text, number=number):
                self.write([stop(text, uuid=f"stop-{number}"), *TRAILER])
                return [row()]
            script += [next_message, [row()]]
        lines = self.run_monitor(script, clock)
        self.assertEqual([line.split(" LIMIT-")[1].split(":")[0] for line in self.limit_lines(lines)],
                         ["UNPARSED"] * 3)


class LimitDetails(MonitorCase):
    def test_reset_text_forms(self):
        stopped = at("2026-10-15T07:19:45.449Z")
        cases = {
            "You've hit your session limit · resets 6:20am (America/New_York)": "2026-10-15T10:20:00Z",
            "You've hit your session limit · resets 9pm (America/New_York)": "2026-10-16T01:00:00Z",
            "You've hit your session limit · resets 12am (America/New_York)": "2026-10-16T04:00:00Z",
            "You've hit your session limit · resets 12:05pm (UTC)": "2026-10-15T12:05:00Z",
            "You've hit your session limit · resets 6:20\N{NARROW NO-BREAK SPACE}AM (America/New_York)": "2026-10-15T10:20:00Z",
            "You've hit your Opus limit · resets 3:45am (Europe/Berlin)": "2026-10-16T01:45:00Z",
            "You've hit your weekly limit · resets Oct 20, 10am (America/New_York)": "2026-10-20T14:00:00Z",
            "You've hit your weekly limit · resets Jan 3, 2027, 6:30am (America/New_York)": "2027-01-03T11:30:00Z",
            "You've hit your weekly limit · resets Sept 1, 2027, 6am (America/New_York)": "2027-09-01T10:00:00Z",
            "You've hit your weekly limit · resets Mon 12:00am (America/New_York)": "2026-10-19T04:00:00Z",
            "You've hit your session limit · resets 6:20am (America/New_York) · progress saved":
                "2026-10-15T10:20:00Z",
            "You've hit your monthly spend limit · raise it at https://claude.ai/settings/usage · "
            "your session limit resets 6:20am (America/New_York)": "2026-10-15T10:20:00Z",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(L.stamp_of(L.reset_of(text, stopped)), expected)
        # The text drops seconds: a stop in the reset's own minute still means that minute, not the next day.
        self.assertEqual(L.stamp_of(L.reset_of("You've hit your session limit · resets 6:19am (America/New_York)",
                                               at("2026-10-15T10:19:30.500Z"))), "2026-10-15T10:19:00Z")
        # 2:30am does not occur on 2027-03-14 in New York; its first occurrence is the next day.
        self.assertEqual(L.stamp_of(L.reset_of("You've hit your session limit · resets 2:30am (America/New_York)",
                                               at("2027-03-14T06:00:00Z"))), "2027-03-15T06:30:00Z")
        for text in ["You've hit your session limit · resets 6:20am",
                     "You've hit your session limit · resets 13:20am (America/New_York)",
                     "You've hit your weekly limit · resets Oct 32, 10am (America/New_York)",
                     "You've hit your session limit · resets 6:20am (../../etc/passwd)",
                     "You've hit your session limit"]:
            with self.subTest(text=text):
                self.assertIsNone(L.reset_of(text, stopped))
        warning = dict(stop("You've used 85% of your session limit · resets 3:45pm (America/New_York)"))
        self.assertIsNone(L.stop_text(warning))

    def test_lines_never_carry_message_text(self):
        self.write([stop(SESSION_STOP + " · progress saved"), *TRAILER])
        self.write([stop("You've hit your monthly spend limit · raise it at https://claude.ai/settings/usage · "
                         "your session limit resets 6:20am (America/New_York)")], sid=SID2)
        self.write([stop("You've hit your monthly spend limit · raise it at https://claude.ai/settings/usage",
                         uuid="stop-x")], sid=SID3)
        rows = [row(), row(sid=SID2, name="lane-2", pid=4243), row(sid=SID3, name="lane-3", pid=4244)]
        lines = self.limit_lines(self.run_monitor([rows, rows], Clock("2026-10-15T10:30:00Z")))
        self.assertEqual(len(lines), 3, lines)
        for line in lines:
            for fragment in ["hit your", "limit ·", "progress saved", "raise it", "https://", "spend"]:
                self.assertNotIn(fragment, line)

    def test_only_the_transcript_tail_is_read(self):
        padding = {"type": "attachment", "content": "x" * 2000}
        self.write([{"type": "user", "content": "y" * 200_000}, stop(SESSION_STOP), *TRAILER])
        self.write([stop(SESSION_STOP), *[padding] * 3, *TRAILER], sid=SID2)  # the stop is beyond 4096 bytes
        rows = [row(), row(sid=SID2, name="lane-2", pid=4243)]
        lines = self.limit_lines(self.run_monitor([rows], Clock("2026-10-15T10:30:00Z"), "--tail-bytes", "4096"))
        self.assertEqual(events(lines), [
            f"LIMIT-BLOCKED: d4-bg kind=background pid=4242 session={SID} reset={RESET} blocked_for=600"])

    def test_session_ids_that_are_not_uuids_are_never_looked_up(self):
        (self.config / "projects" / "p").mkdir(parents=True)
        (self.config / "projects" / "escape.jsonl").write_text(json.dumps(stop(SESSION_STOP)) + "\n")
        lines = self.run_monitor([[row(sid="../escape")]], Clock("2026-10-15T10:30:00Z"))
        self.assertEqual(self.limit_lines(lines), [])

    def test_a_blocked_row_without_a_process_is_reported(self):
        # `claude agents --json` keeps listing a blocked background session after its process exits
        # (agent-view.md:779); it has no pid then (agent-view.md:788).
        self.write([stop(SESSION_STOP), *TRAILER])
        lines = self.run_monitor([[row(pid=None)]], Clock("2026-10-15T10:30:00Z"))
        self.assertEqual(events(self.limit_lines(lines)), [
            f"LIMIT-BLOCKED: d4-bg kind=background pid=- session={SID} reset={RESET} blocked_for=600"])

    def test_a_row_name_cannot_split_the_line(self):
        # A newline in a session name would otherwise start a second, forged `[lanes]` line.
        self.write([stop(SESSION_STOP), *TRAILER])
        lines = self.run_monitor([[row(name="d4-bg" + chr(10) + "[lanes] forged")]], Clock("2026-10-15T10:30:00Z"))
        self.assertEqual(self.limit_lines(lines), [
            f"[lanes] 2026-10-15T10:30:00Z LIMIT-BLOCKED: d4-bg?[lanes] forged kind=background pid=4242 "
            f"session={SID} reset={RESET} blocked_for=600"])
        self.assertFalse([line for line in lines if line.startswith("[lanes] forged")])

    def test_default_paths_under_home(self):
        home = self.tmp / "home"
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            os.environ.pop("CLAUDE_CONFIG_DIR")
            os.environ.pop("XDG_STATE_HOME")
            self.write([stop(SESSION_STOP), *TRAILER], base=home / ".claude" / "projects")
            lines = self.run_monitor([[row()]], Clock("2026-10-15T10:30:00Z"))
        self.assertEqual(len(self.limit_lines(lines)), 1, lines)
        state = home / ".local" / "state" / "native-agent-stack" / "lane-liveness" / "limits.json"
        self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(state.parent.stat().st_mode), 0o700)

    def test_an_unwritable_state_directory_still_prints_once_per_process(self):
        self.state_home.write_text("not a directory")
        self.write([stop(SESSION_STOP), *TRAILER])
        lines = self.limit_lines(self.run_monitor([[row()]] * 3, Clock("2026-10-15T10:30:00Z")))
        self.assertEqual([line.split(" LIMIT-")[1].split(":")[0] for line in lines], ["STATE", "BLOCKED"])


if __name__ == "__main__":
    unittest.main()
