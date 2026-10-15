"""tools/memory-index-guard/memory_index_guard.py: limits read from the client binary, index sizes, the auto-dream watch.

Every check runs in a temporary home: a byte-string stand-in for the client binary (the loader's warning template and the
`"MEMORY.md"` declaration, a mismatched one, an empty file), fake memory directories, `settings.json` and `.claude.json`.
No check reads the host's client, settings or memory. The template follows the 2.1.300 loader as quoted in
evidence/artifacts/memory-maintenance-20261015/sources.json; the caps in the stand-ins are not the documented 200 and
25000, so an answer that hard-codes those numbers fails.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "memory-index-guard"
TOOL = TOOL_DIR / "memory_index_guard.py"
EVIDENCE = ROOT / "evidence" / "artifacts" / "memory-maintenance-20261015"
spec = importlib.util.spec_from_file_location("memory_index_guard", TOOL)
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

BACKSLASH = bytes([92])  # built from its code point, so no escape sequence is written in this file
SENTINEL = "sentinel-content-that-must-never-be-reported"
T0 = 1_791_000_000 * 10**9  # 2026-10-03T04:00:00Z in nanoseconds; lock mtimes are set relative to it


def template(line_id: bytes = b"S$", size_id: bytes = b"Yie") -> bytes:
    """The loader's truncation warning as 2.1.300 builds it; the identifiers differ in every build."""
    return (b"let A=r>" + line_id + b"&&s>" + size_id + b"?`${r} lines and ${Zt(s)}`:r>" + line_id
            + b"?`${r} lines (limit: ${" + line_id + b"})`:`${Zt(s)} (limit: ${Zt(" + size_id + b")}) "
            + BACKSLASH + b"u2014 index entries are too long`;w.push(`> WARNING: ${Xu} is ${A}. Only part of it was "
            + b"loaded: ${U}. Keep index entries to one line under ~200 chars; move detail into topic files.`);")


def declaration(line_id: bytes = b"S$", line_cap: bytes = b"150", size_id: bytes = b"Yie", size_cap: bytes = b"12345",
                tail: bytes = b",wPr=4*Yie;") -> bytes:
    return b'var Xu="MEMORY.md",' + line_id + b"=" + line_cap + b"," + size_id + b"=" + size_cap + tail


def write_binary(directory: Path, *parts: bytes, name: str = "9.9.9") -> Path:
    """A stand-in binary: the parts separated by more filler than the template window, so each part stands alone."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(b"\0" * 64 + (b"\0" * 5000).join(parts) + b"\0" * 64)
    return path


def lines_of(count: int) -> str:
    return "\n".join("x" for _ in range(count))


def tree(root: Path) -> dict:
    """Every path under root with its mode, mtime and content hash: the read-only check compares two of these."""
    found = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if stat.S_ISREG(info.st_mode) else None
        found[str(path.relative_to(root))] = (stat.S_IMODE(info.st_mode), info.st_mtime_ns, digest)
    return found


class Limits(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_the_caps_bind_from_the_template_and_the_declaration(self):
        limits = G.read_limits(write_binary(self.tmp, declaration(), template()))
        self.assertEqual((limits["status"], limits["line_cap"], limits["size_cap"]), ("ok", 150, 12345))
        self.assertEqual(limits["identifiers"], ["S$", "Yie"])
        self.assertRegex(limits["sha256"], r"^[0-9a-f]{64}$")

    def test_a_same_named_value_in_another_chunk_does_not_decide(self):
        # 2.1.299: `qN=8` in an unrelated chunk and `qN=200` in the memory chunk; a global search could not decide.
        binary = write_binary(self.tmp, b"var qN=8,Yse=1;", declaration(b"qN", b"200", b"Yse", b"25000", b";"),
                              template(b"qN", b"Yse"))
        limits = G.read_limits(binary)
        self.assertEqual((limits["status"], limits["line_cap"], limits["size_cap"]), ("ok", 200, 25000))
        self.assertEqual(limits["identifiers"], ["qN", "Yse"])

    def test_a_declaration_with_other_identifiers_is_unknown(self):
        limits = G.read_limits(write_binary(self.tmp, declaration(b"A$", b"150", b"Bie", b"12345"), template()))
        self.assertEqual((limits["status"], limits["line_cap"], limits["size_cap"]), ("unknown", None, None))
        self.assertIn("bind", limits["reason"])

    def test_an_empty_file_is_unknown(self):
        empty = self.tmp / "empty"
        empty.write_bytes(b"")
        limits = G.read_limits(empty)
        self.assertEqual((limits["status"], limits["line_cap"], limits["size_cap"]), ("unknown", None, None))
        self.assertIn("empty", limits["reason"])

    def test_a_missing_binary_is_unknown(self):
        self.assertEqual(G.read_limits(self.tmp / "absent")["status"], "unknown")
        self.assertEqual(G.read_limits(None)["status"], "unknown")

    def test_two_different_bindings_are_unknown(self):
        binary = write_binary(self.tmp, declaration(), declaration(line_cap=b"151"), template())
        self.assertEqual(G.read_limits(binary)["status"], "unknown")

    def test_a_computed_cap_is_unknown(self):
        binary = write_binary(self.tmp, declaration(size_cap=b"25*1000"), template())
        self.assertEqual(G.read_limits(binary)["status"], "unknown")

    def test_a_zero_cap_is_unknown(self):
        self.assertEqual(G.read_limits(write_binary(self.tmp, declaration(line_cap=b"0"), template()))["status"], "unknown")

    def test_without_the_user_visible_anchor_the_template_does_not_count(self):
        no_anchor = template().replace(b"Only part of it was loaded", b"Part of it was loaded")
        self.assertEqual(G.read_limits(write_binary(self.tmp, declaration(), no_anchor))["status"], "unknown")

    def test_the_default_binary_is_the_realpath_of_local_bin_claude(self):
        home = self.tmp / "home"
        target = write_binary(home / ".local" / "share" / "claude" / "versions", declaration(), template(), name="2.9.9")
        (home / ".local" / "bin").mkdir(parents=True)
        (home / ".local" / "bin" / "claude").symlink_to(target)
        self.assertEqual(G.default_binary(home), target)
        self.assertIsNone(G.default_binary(self.tmp / "nobody"))


class Measure(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def write(self, text: str) -> Path:
        path = self.tmp / "MEMORY.md"
        path.write_bytes(text.encode("utf-8"))
        return path

    def test_the_trim_set_is_the_one_measured_in_two_javascript_engines(self):
        measured = json.loads((EVIDENCE / "js-trim-set.json").read_text(encoding="utf-8"))
        engines = measured["engines"]
        self.assertEqual(len(engines), 2)
        self.assertEqual(engines[0]["removed"], engines[1]["removed"])
        self.assertEqual(sorted(map(ord, G.JS_TRIM)), engines[0]["removed"])
        # Python's own strip() differs: it removes U+001C-U+001F and U+0085 and keeps U+FEFF.
        self.assertEqual((chr(0x1C) + "a").strip(), "a")
        self.assertEqual((chr(0x1C) + "a").strip(G.JS_TRIM), chr(0x1C) + "a")
        self.assertEqual((chr(0xFEFF) + "a").strip(G.JS_TRIM), "a")

    def test_size_is_utf16_code_units_of_the_trimmed_text_and_utf8_bytes_are_reported_too(self):
        dash, face = chr(0x2014), chr(0x1F600)  # 1 code unit and 3 bytes; 2 code units and 4 bytes
        text = chr(0xFEFF) + "  " + "a" + dash + face + "\nb" + " \n\n" + chr(0x3000)
        measure = G.measure_index(self.write(text))
        self.assertEqual(measure["code_units"], 1 + 1 + 2 + 2)  # "a", dash, face, "\nb"
        self.assertEqual(measure["lines"], 2)
        self.assertEqual(measure["utf8_bytes"], len(text.encode("utf-8")))

    def test_lines_are_the_newline_count_of_the_trimmed_text_plus_one(self):
        self.assertEqual(G.measure_index(self.write("\n\na\n\nb\n\n\n"))["lines"], 3)
        self.assertEqual(G.measure_index(self.write("a\r\nb"))["lines"], 2)
        self.assertEqual(G.measure_index(self.write(""))["lines"], 1)  # the client's lineCount of an empty index

    def test_frontmatter_or_an_html_comment_marks_the_numbers_as_an_upper_bound(self):
        self.assertFalse(G.measure_index(self.write("- [a](a.md)\n"))["stripped_parts_present"])
        self.assertTrue(G.measure_index(self.write("---\nname: x\n---\n- [a](a.md)\n"))["stripped_parts_present"])
        self.assertTrue(G.measure_index(self.write("<!-- note -->\n- [a](a.md)\n"))["stripped_parts_present"])


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.home = self.tmp / "home"
        self.claude = self.home / ".claude"
        (self.claude / "projects").mkdir(parents=True)
        self.claude_json = self.home / ".claude.json"
        self.state = self.tmp / "state"
        self.binary = write_binary(self.tmp / "bin", declaration(line_cap=b"100", size_cap=b"1000"), template())
        self.enterContext(mock.patch.dict(os.environ, {"HOME": str(self.home)}))

    def project(self, name: str, files: dict[str, str] | None = None) -> Path:
        memory = self.claude / "projects" / name / "memory"
        memory.mkdir(parents=True, exist_ok=True)
        for file_name, text in (files or {}).items():
            (memory / file_name).write_text(text, encoding="utf-8")
        return memory

    def settings(self, **keys) -> None:
        (self.claude / "settings.json").write_text(json.dumps(keys), encoding="utf-8")

    def flag(self, value, **other) -> None:
        self.claude_json.write_text(json.dumps({**other, "cachedGrowthBookFeatures": {"tengu_onyx_plover": value}}),
                                    encoding="utf-8")

    def lock(self, memory: Path, mtime_ns: int, pid: int = 4194305) -> Path:
        path = memory / ".consolidate-lock"
        path.write_text(str(pid), encoding="utf-8")
        os.utime(path, ns=(mtime_ns, mtime_ns))
        return path

    def run_guard(self, *extra: str, binary: Path | None = None):
        argv = ["--binary", str(binary or self.binary), "--state-dir", str(self.state), "--claude-dir", str(self.claude),
                "--claude-json", str(self.claude_json), *extra]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = G.main(argv)
        report = json.loads(out.getvalue()) if out.getvalue().strip() else None
        return rc, report, out.getvalue(), err.getvalue()

    def index_of(self, report: dict, project: str) -> dict:
        return next(row for row in report["indexes"] if row["project"] == project)


class Indexes(Fixture):
    def test_every_project_index_and_the_auto_memory_directory_are_measured(self):
        self.project("-home-example-code-a", {"MEMORY.md": "- [a](a.md)\n"})
        self.project("-home-example-code-b", {"MEMORY.md": "- [b](b.md)\n", "b.md": "b\n"})
        self.project("-home-example-code-c", {"note.md": "c\n"})  # a memory directory without an index
        custom = self.home / "custom-memory"
        custom.mkdir()
        (custom / "MEMORY.md").write_text("- [d](d.md)\n", encoding="utf-8")
        self.settings(autoMemoryDirectory="~/custom-memory")
        rc, report, _, _ = self.run_guard()
        self.assertEqual(rc, 0)
        self.assertEqual(sorted(row["project"] for row in report["indexes"]),
                         ["-home-example-code-a", "-home-example-code-b", "autoMemoryDirectory"])
        self.assertEqual(report["auto_dream"]["memory_dirs"], 4)

    def test_status_follows_the_bound_caps_warn_at_80_and_alert_at_90_percent(self):
        cases = {"l79": (lines_of(79), "ok"), "l80": (lines_of(80), "warn"), "l89": (lines_of(89), "warn"),
                 "l90": (lines_of(90), "alert"), "u799": ("x" * 799, "ok"), "u800": ("x" * 800, "warn"),
                 "u900": ("x" * 900, "alert"), "over": ("x" * 1001, "alert")}
        for name, (text, _) in cases.items():
            self.project(name, {"MEMORY.md": text})
        rc, report, _, _ = self.run_guard()
        for name, (_, expected) in cases.items():
            with self.subTest(index=name):
                self.assertEqual(self.index_of(report, name)["status"], expected)
        self.assertEqual(rc, 1, "an index at alert fails the unit")
        row = self.index_of(report, "l80")
        self.assertEqual((row["lines"], row["lines_pct"]), (80, 80.0))
        self.assertEqual(report["limits"]["line_cap"], 100)

    def test_code_units_decide_and_not_utf8_bytes(self):
        # 799 code units (79.9% of 1000) but 2,397 UTF-8 bytes: the client counts the string's length, so this is ok.
        self.project("dashes", {"MEMORY.md": chr(0x2014) * 799})
        rc, report, _, _ = self.run_guard()
        row = self.index_of(report, "dashes")
        self.assertEqual((row["code_units"], row["utf8_bytes"], row["status"]), (799, 2397, "ok"))
        self.assertEqual(row["utf8_bytes_pct"], 239.7)
        self.assertEqual(rc, 0)

    def test_unknown_limits_report_unknown_status_and_exit_0(self):
        self.project("big", {"MEMORY.md": "x" * 5000})
        empty = self.tmp / "empty"
        empty.write_bytes(b"")
        rc, report, _, err = self.run_guard(binary=empty)
        self.assertEqual(rc, 0, "fail-open: unknown limits never alert")
        self.assertEqual(report["limits"]["status"], "unknown")
        row = self.index_of(report, "big")
        self.assertEqual((row["status"], row["lines_pct"], row["size_pct"], row["code_units"]), ("unknown", None, None, 5000))
        self.assertIn("limits unknown", err)

    def test_the_default_binary_comes_from_home(self):
        target = write_binary(self.home / ".local" / "share" / "claude" / "versions", declaration(), template(),
                              name="2.9.9")
        (self.home / ".local" / "bin").mkdir(parents=True)
        (self.home / ".local" / "bin" / "claude").symlink_to(target)
        argv = ["--state-dir", str(self.state), "--claude-dir", str(self.claude), "--claude-json", str(self.claude_json)]
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(G.main(argv), 0)
        limits = json.loads(out.getvalue())["limits"]
        self.assertEqual((limits["status"], limits["line_cap"], limits["version"]), ("ok", 150, "2.9.9"))
        self.assertEqual(limits["binary"], "~/.local/share/claude/versions/2.9.9")


class AutoDream(Fixture):
    def test_settings_report_only_auto_dream_enabled(self):
        self.settings(autoDreamEnabled=True, env={"SECRET_TOKEN": SENTINEL}, model=SENTINEL)
        rc, report, out, err = self.run_guard()
        self.assertEqual(report["auto_dream"]["autoDreamEnabled"], True)
        self.assertNotIn(SENTINEL, out + err + (self.state / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(rc, 0)

    def test_the_flag_reports_only_enabled_and_available(self):
        self.flag({"enabled": False, "minHours": 24, "minSessions": 3, "remoteEnabled": False},
                  oauthAccount={"emailAddress": SENTINEL}, userID=SENTINEL)
        rc, report, out, err = self.run_guard()
        self.assertEqual(report["auto_dream"]["flag"], {"status": "read", "enabled": False, "available": "absent"})
        for hidden in (SENTINEL, "minSessions", "remoteEnabled", "minHours"):
            self.assertNotIn(hidden, out + err + (self.state / "report.json").read_text(encoding="utf-8"))
        self.assertEqual((report["auto_dream"]["gate_open"], report["auto_dream"]["effective"]), (False, False))
        self.assertEqual(rc, 0)

    def test_a_non_boolean_flag_field_is_not_echoed(self):
        self.flag({"enabled": SENTINEL, "available": True})
        _, report, out, _ = self.run_guard()
        self.assertEqual(report["auto_dream"]["flag"]["enabled"], "non-boolean")
        self.assertNotIn(SENTINEL, out)

    def test_the_gate_opens_on_enabled_or_available_and_the_setting_then_decides(self):
        for value, setting, gate, effective in (({"available": True}, True, True, True), ({"available": True}, False, True, False),
                                                ({"enabled": True}, None, True, True), ({"available": True}, None, True, False),
                                                ({"enabled": False}, True, False, False)):
            with self.subTest(flag=value, setting=setting):
                self.flag(value)
                self.settings(**({} if setting is None else {"autoDreamEnabled": setting}))
                _, report, _, _ = self.run_guard()
                self.assertEqual((report["auto_dream"]["gate_open"], report["auto_dream"]["effective"]), (gate, effective))

    def test_a_missing_or_unreadable_flag_is_unknown_and_exit_0(self):
        rc, report, _, err = self.run_guard()
        self.assertEqual(report["auto_dream"]["flag"]["status"], "unknown")
        self.assertIsNone(report["auto_dream"]["gate_open"])
        self.assertEqual(rc, 0)
        self.assertIn("flag unknown", err)
        self.claude_json.write_text("{not json", encoding="utf-8")
        rc, report, _, _ = self.run_guard()
        self.assertEqual((rc, report["auto_dream"]["flag"]["status"]), (0, "unknown"))

    def test_the_flag_is_read_in_process(self):
        self.assertFalse(hasattr(G, "subprocess"), "the guard starts no process")
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("os.system", source)


class Consolidation(Fixture):
    def setUp(self):
        super().setUp()
        self.memory = self.project("-home-example-code-p", {"MEMORY.md": "- [a](a.md)\n- [b](b.md)\n",
                                                             "a.md": SENTINEL + "\none\n", "b.md": "two\n"})

    def test_the_first_run_records_the_lock_baseline_and_a_private_snapshot(self):
        rc, report, _, _ = self.run_guard()
        self.assertEqual((rc, report["new_consolidations"]), (0, []))
        state = json.loads((self.state / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["locks"]["-home-example-code-p"], 0)
        self.assertIsNone(state["first_dream_seen"])
        snapshot = self.state / "snapshots" / "-home-example-code-p.tar"
        self.assertEqual(stat.S_IMODE(snapshot.stat().st_mode), 0o400)
        for directory in (self.state, self.state / "snapshots"):
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        with tarfile.open(snapshot) as archive:
            self.assertEqual(sorted(archive.getnames()), ["MEMORY.md", "a.md", "b.md"])
            self.assertEqual(archive.extractfile("a.md").read().decode("utf-8"), SENTINEL + "\none\n")
        self.assertEqual(report["snapshots"]["written"], ["-home-example-code-p"])

    def test_a_new_consolidation_alerts_once_with_a_names_and_counts_diff(self):
        self.run_guard()
        (self.memory / "b.md").unlink()
        (self.memory / "c.md").write_text("three\nfour\n", encoding="utf-8")
        (self.memory / "MEMORY.md").write_text("- [a](a.md)\n- [c](c.md)\n- [d](d.md)\n", encoding="utf-8")
        self.lock(self.memory, T0)
        rc, report, out, err = self.run_guard()
        self.assertEqual(rc, 1, "a new consolidation fails the unit so stack-alert runs")
        (seen,) = report["new_consolidations"]
        self.assertEqual(seen["dir"], "-home-example-code-p")
        self.assertEqual(seen["lock_mtime_utc"], "2026-10-03T04:00:00Z")
        self.assertEqual(seen["added"], [{"name": "c.md", "lines": 2, "bytes": 11}])
        self.assertEqual(seen["removed"], [{"name": "b.md", "lines": 1, "bytes": 4}])
        self.assertEqual(seen["changed"], [{"name": "MEMORY.md", "lines_before": 2, "lines_after": 3,
                                            "bytes_before": 24, "bytes_after": 36}])
        self.assertEqual(seen["unchanged"], 1)
        # Names and counts only: no digest or text of a memory file enters the report.
        self.assertEqual(sorted(seen), ["added", "baseline_taken_at", "changed", "detected_at", "dir", "holder_pid_running",
                                        "lock_age_s", "lock_mtime_utc", "record", "removed", "unchanged"])
        self.assertEqual({key for row in seen["added"] + seen["removed"] for key in row}, {"name", "lines", "bytes"})
        # The rolling snapshot is taken only when no new consolidation is seen, so it still holds the directory before.
        self.assertEqual(report["snapshots"]["written"], [])
        with tarfile.open(self.state / "snapshots" / "-home-example-code-p.tar") as archive:
            self.assertIn("b.md", archive.getnames())
        record = self.state / "dreams" / "-home-example-code-p" / "20261003T040000000Z"
        for name in ("before.tar", "after.tar", "diff.json"):
            self.assertEqual(stat.S_IMODE((record / name).stat().st_mode), 0o400, name)
        self.assertEqual(json.loads((record / "diff.json").read_text(encoding="utf-8"))["added"], seen["added"])
        with tarfile.open(record / "before.tar") as archive:
            self.assertIn("b.md", archive.getnames())
        with tarfile.open(record / "after.tar") as archive:
            self.assertEqual(sorted(archive.getnames()), ["MEMORY.md", "a.md", "c.md"])
        for text in (out, err, (record / "diff.json").read_text(encoding="utf-8")):
            self.assertNotIn(SENTINEL, text)
            self.assertNotIn("three", text)
        self.assertEqual(report["auto_dream"]["first_dream_seen"]["dir"], "-home-example-code-p")
        self.assertIn("1 new consolidation", err)
        rc, report, _, _ = self.run_guard()
        self.assertEqual((rc, report["new_consolidations"]), (0, []), "the same lock is not new again")

    def test_the_first_dream_time_is_kept_across_later_ones(self):
        self.run_guard()
        self.lock(self.memory, T0)
        self.run_guard()
        first = json.loads((self.state / "state.json").read_text(encoding="utf-8"))["first_dream_seen"]
        self.lock(self.memory, T0 + 30 * 3600 * 10**9)
        rc, report, _, _ = self.run_guard()
        self.assertEqual(rc, 1)
        state = json.loads((self.state / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["first_dream_seen"], first)
        self.assertEqual(first["lock_mtime_utc"], "2026-10-03T04:00:00Z")
        self.assertEqual(len(state["dreams"]), 2)

    def test_a_lock_that_moves_back_is_reported_and_is_not_an_alert(self):
        # The client's rollback after a failed run writes the previous mtime back onto the lock (utimes).
        self.run_guard()
        self.lock(self.memory, T0)
        self.run_guard()
        self.lock(self.memory, T0 - 3600 * 10**9)
        rc, report, _, _ = self.run_guard()
        self.assertEqual((rc, report["new_consolidations"]), (0, []))
        self.assertEqual([row["dir"] for row in report["locks_moved_back"]], ["-home-example-code-p"])

    def test_a_lock_present_at_the_first_run_counts_as_new(self):
        # The client reads a missing lock as 0 (never consolidated), so any lock is newer than an empty record.
        self.lock(self.memory, T0)
        rc, report, _, _ = self.run_guard()
        self.assertEqual(rc, 1)
        (seen,) = report["new_consolidations"]
        self.assertIsNone(seen["baseline_taken_at"])
        self.assertEqual(sorted(row["name"] for row in seen["added"]), ["MEMORY.md", "a.md", "b.md"])

    def test_the_snapshot_is_rewritten_only_when_the_directory_changed(self):
        self.run_guard()
        snapshot = self.state / "snapshots" / "-home-example-code-p.tar"
        before = snapshot.stat().st_ino
        _, report, _, _ = self.run_guard()
        self.assertEqual((snapshot.stat().st_ino, report["snapshots"]["written"]), (before, []))
        (self.memory / "b.md").write_text("two\nmore\n", encoding="utf-8")
        _, report, _, _ = self.run_guard()
        self.assertNotEqual(snapshot.stat().st_ino, before)
        self.assertEqual(report["snapshots"]["written"], ["-home-example-code-p"])

    def test_the_pre_dream_snapshot_outlives_the_next_rolling_snapshot(self):
        self.run_guard()
        (self.memory / "b.md").unlink()
        self.lock(self.memory, T0)
        self.run_guard()
        self.run_guard()  # no new consolidation: the rolling snapshot now holds the post-dream directory
        with tarfile.open(self.state / "snapshots" / "-home-example-code-p.tar") as archive:
            self.assertNotIn("b.md", archive.getnames())
        with tarfile.open(self.state / "dreams" / "-home-example-code-p" / "20261003T040000000Z" / "before.tar") as archive:
            self.assertIn("b.md", archive.getnames())

    def test_a_live_holder_pid_is_reported(self):
        self.lock(self.memory, T0, pid=os.getpid())
        _, report, _, _ = self.run_guard()
        (lock,) = report["auto_dream"]["locks"]
        self.assertTrue(lock["holder_pid_running"])
        self.assertTrue(report["new_consolidations"][0]["holder_pid_running"])

    def test_empty_memory_directories_get_no_snapshot(self):
        self.project("-home-example-code-empty")
        _, report, _, _ = self.run_guard()
        self.assertFalse((self.state / "snapshots" / "-home-example-code-empty.tar").exists())
        self.assertEqual(report["auto_dream"]["memory_dirs"], 2)

    def test_an_oversized_directory_is_not_tarred_and_says_why(self):
        with mock.patch.object(G, "SNAPSHOT_MAX_BYTES", 10):
            _, report, _, _ = self.run_guard()
        self.assertEqual(report["snapshots"]["skipped"], [{"dir": "-home-example-code-p", "reason": "over 10 bytes"}])
        self.assertFalse((self.state / "snapshots" / "-home-example-code-p.tar").exists())


class Output(Fixture):
    def setUp(self):
        super().setUp()
        self.project("-home-example-code-p", {"MEMORY.md": lines_of(85), "a.md": SENTINEL})
        self.settings(autoDreamEnabled=True)
        self.flag({"enabled": False})

    def test_one_json_report_on_stdout_and_in_the_state_dir_and_one_summary_line_on_stderr(self):
        rc, report, out, err = self.run_guard()
        self.assertEqual(json.loads((self.state / "report.json").read_text(encoding="utf-8")), report)
        self.assertEqual(stat.S_IMODE((self.state / "report.json").stat().st_mode), 0o600)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertTrue(err.startswith("memory-index-guard: exit 0;"), err)
        self.assertIn("1 index: 0 alert, 1 warn, 0 ok", err)
        self.assertIn("auto-dream inert (flag enabled=false available=absent, autoDreamEnabled=true)", err)
        self.assertEqual((rc, report["exit_code"], report["schema"]), (0, 0, "memory-index-guard-report/1"))

    def test_nothing_outside_the_state_dir_changes(self):
        self.lock(self.claude / "projects" / "-home-example-code-p" / "memory", T0)
        (self.claude / "projects" / "-home-example-code-p" / "memory" / "MEMORY.md").write_text(lines_of(95), encoding="utf-8")
        before = tree(self.home)
        binary_before = tree(self.binary.parent)
        rc, _, _, _ = self.run_guard()
        self.assertEqual(rc, 1)
        self.assertEqual(tree(self.home), before)
        self.assertEqual(tree(self.binary.parent), binary_before)

    def test_a_held_run_lock_skips_the_run(self):
        self.state.mkdir(mode=0o700)
        with open(self.state / "guard.lock", "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            rc, report, out, err = self.run_guard()
        self.assertEqual((rc, report, out), (0, None, ""))
        self.assertIn("another run holds", err)
        self.assertFalse((self.state / "report.json").exists())

    def test_an_unreadable_state_file_is_a_fault_not_a_fresh_start(self):
        self.state.mkdir(mode=0o700)
        (self.state / "state.json").write_text("{broken", encoding="utf-8")
        rc, _, _, err = self.run_guard()
        self.assertEqual(rc, 2)
        self.assertIn("state.json", err)

    def test_it_runs_under_python_isolated_mode(self):
        result = subprocess.run([sys.executable, "-I", str(TOOL), "--binary", str(self.binary), "--state-dir", str(self.state),
                                 "--claude-dir", str(self.claude), "--claude-json", str(self.claude_json)],
                                capture_output=True, text=True, timeout=60, env={"HOME": str(self.home), "PATH": os.defpath})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["indexes"][0]["status"], "warn")

    def test_the_sources_are_ascii(self):
        for path in (TOOL, Path(__file__)):
            with self.subTest(path=path.name):
                self.assertTrue(path.read_bytes().isascii())


class Units(unittest.TestCase):
    SERVICE = TOOL_DIR / "units" / "memory-index-guard.service"
    TIMER = TOOL_DIR / "units" / "memory-index-guard.timer"

    def test_the_service_runs_the_installed_tool_and_alerts_on_failure(self):
        service = self.SERVICE.read_text(encoding="utf-8")
        self.assertIn("ExecStart=/usr/bin/python3 -I %h/.local/share/native-agent-stack/memory-index-guard/memory_index_guard.py "
                      "--state-dir %h/.local/state/native-agent-stack/memory-index-guard\n", service)
        unit_section = service.split("[Unit]", 1)[1].split("[Service]", 1)[0]
        self.assertIn("OnFailure=stack-alert@%n.service", unit_section)
        self.assertIn("Type=oneshot", service)

    def test_the_timer_runs_every_six_hours_from_ten_minutes_after_boot(self):
        timer = self.TIMER.read_text(encoding="utf-8")
        for line in ("OnBootSec=10min", "OnUnitActiveSec=6h", "WantedBy=timers.target"):
            self.assertIn(line + "\n", timer)

    @unittest.skipUnless(shutil.which("systemd-analyze"), "native systemd verifier unavailable")
    def test_the_units_pass_the_native_verifier_without_a_session_or_an_install(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            runtime.mkdir(mode=0o700)
            for unit in (self.SERVICE, self.TIMER):
                shutil.copy(unit, root / unit.name)
            result = subprocess.run([shutil.which("systemd-analyze"), "--user", "--man=no", "verify",
                                     str(root / self.SERVICE.name), str(root / self.TIMER.name)],
                                    env={"HOME": str(root), "PATH": os.defpath, "XDG_RUNTIME_DIR": str(runtime)},
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((root / ".config" / "systemd" / "user").exists())


if __name__ == "__main__":
    unittest.main()
