"""The skill-usage refresh units render exact producer argv for the command-center grants."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("skill_usage_render_units", ROOT / "tools/skill-usage/render_units.py")
render = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render)


def unquote(line: str) -> list[str]:
    """systemd.syntax(7) double-quoted words with C escapes, then systemd.unit(5) '%%' specifier escapes."""
    words, index = [], 0
    while index < len(line):
        if line[index] == " ":
            index += 1
        elif line[index] == '"':
            index, word = index + 1, []
            while line[index] != '"':
                word.append(line[index + 1] if line[index] == "\\" else line[index])
                index += 2 if line[index] == "\\" else 1
            index += 1
            words.append("".join(word).replace("%%", "%"))
        else:
            end = line.find(" ", index)
            end = len(line) if end < 0 else end
            words.append(line[index:end].replace("%%", "%"))
            index = end
    return words


class SkillUsageUnitTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="skill-units-")))
        self.skills = self.base / "state with space/skills"
        self.codex = self.base / "codex %h $HOME"
        self.claude = self.base / 'claude "projects"'

    def rendered(self, **options):
        return render.render_units(ROOT, self.skills, self.codex, self.claude, **options)

    def test_units_carry_exact_destinations_and_round_trip_the_scripts(self):
        units = self.rendered()
        self.assertEqual(set(units), set(render.UNITS))
        hourly = units["native-agent-skill-usage.service"]
        daily = units["native-agent-skill-usage-codex-lanes.service"]
        self.assertNotIn("@", hourly + daily)
        lines = {name: re.findall(r"^ExecStart=(.*)$", text, re.M) for name, text in (("hourly", hourly), ("daily", daily))}
        self.assertEqual([len(lines["hourly"]), len(lines["daily"])], [2, 1])
        expected = {
            lines["hourly"][0]: (render.SCRIPTS["host"], [ROOT / "tools/skill-usage/skill_usage.py", self.codex, self.skills / "skill-usage-host-latest.json"]),
            lines["hourly"][1]: (render.SCRIPTS["claude"], [ROOT / "examples/claude-native/workflows/child-usage.mjs", self.claude,
                                                           self.skills / "skill-usage-claude-lanes-latest.json", ROOT / "tools/skill-usage/systemd/claude-lanes.jq"]),
            lines["daily"][0]: (render.SCRIPTS["codex"], [ROOT / "tools/skill-usage/skill_usage.py", self.codex, self.skills / "skill-usage-codex-lanes-latest.json"]),
        }
        for line, (script, arguments) in expected.items():
            with self.subTest(script=script[:30]):
                self.assertTrue(line.startswith(':/bin/sh -c "'))
                self.assertEqual(unquote(line[len(":/bin/sh"):]), ["-c", script, *map(str, arguments)])
                self.assertNotRegex(line, r"(?<!%)%(?!%)")
        grants = json.loads((ROOT / "tools/local-pages/source_policy.json").read_text())["command_center"]["command_center_skills"]
        names = {entry["path"].rsplit("/", 1)[1] for entry in grants}
        # The units' three reports are granted; the only other skill inputs are #970's daily projection and the practice slots.
        self.assertLessEqual(set(render.OUTPUTS.values()), names)
        self.assertEqual(names - set(render.OUTPUTS.values()), {"skill-invoke-rate-latest.json", "slots-final.json"})
        self.assertIn("OnCalendar=hourly", units["native-agent-skill-usage.timer"])
        self.assertIn("OnCalendar=*-*-* 01:30:00", units["native-agent-skill-usage-codex-lanes.timer"])

    def test_each_script_is_valid_shell_and_renames_only_a_finished_report(self):
        for name, script in render.SCRIPTS.items():
            with self.subTest(name=name):
                self.assertEqual(subprocess.run(["/bin/sh", "-n", "-c", script], capture_output=True).returncode, 0)
                self.assertIn('/usr/bin/mv -f "$2.tmp" "$2"', script)
                self.assertTrue(script.endswith('/usr/bin/rm -f "$2.full" "$2.tmp"; exit $status'))
        destination = self.base / "out/report.json"
        destination.parent.mkdir()
        destination.write_text('{"previous": true}')
        failing = render.SCRIPTS["host"].replace("/usr/bin/python3 -B", "/bin/false")
        result = subprocess.run(["/bin/sh", "-c", failing, "producer", str(self.codex), str(destination)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(destination.read_text(), '{"previous": true}')
        self.assertEqual(sorted(path.name for path in destination.parent.iterdir()), ["report.json"])

    def test_claude_projection_keeps_only_aggregate_skill_counts(self):
        if shutil.which("jq") is None:
            self.skipTest("jq is not installed")
        report = {"kind": "claude_child_lane_usage", "schema_version": 1, "window": {"since": "a", "until": "b"}, "limits": "x",
                  "actors": [{"transcript": "private"}], "main": {"children": 2, "children_with_skill_call": 1, "skill_calls": {"tdd": 1}, "bash_calls": 9},
                  "groups": {"all": {"children": 3, "children_with_skill_call": 1, "skill_calls": {"tdd": 2}, "fetch": {}},
                             "workers": {"children": 3, "children_with_skill_call": 1, "skill_calls": {"tdd": 2}},
                             "negative_controls": {"children": 0, "children_with_skill_call": 0, "skill_calls": {}},
                             "by_session": {"session-01": {"children": 1}},
                             "by_agent_type": {"cc-x": {"children": 1, "children_with_skill_call": 1, "skill_calls": {"tdd": 1}, "measurement": {}}}}}
        source = self.base / "full.json"
        source.write_text(json.dumps(report))
        result = subprocess.run(["jq", "-c", "-f", str(ROOT / "tools/skill-usage/systemd/claude-lanes.jq"), str(source)], capture_output=True, text=True, check=True)
        projected = json.loads(result.stdout)
        self.assertNotIn("actors", projected)
        self.assertEqual(set(projected["groups"]), {"all", "workers", "negative_controls", "by_agent_type"})
        self.assertEqual(projected["groups"]["by_agent_type"]["cc-x"], {"children": 1, "children_with_skill_call": 1, "skill_calls": {"tdd": 1}})
        self.assertEqual(projected["main"], {"children": 2, "children_with_skill_call": 1, "skill_calls": {"tdd": 1}})

    def test_renderer_refuses_unsafe_locations_and_calendars(self):
        for options, message in ((dict(skills_dir=ROOT / "tmp-skills"), "outside the repository"), (dict(skills_dir="relative/skills"), "absolute"),
                                 (dict(codex_root="codex\nroot"), "control characters"), (dict(on_calendar="hourly\nExecStart=/bin/true"), "calendar"),
                                 (dict(on_calendar_codex="daily;rm"), "calendar")):
            with self.subTest(options=options):
                arguments = dict(repo=ROOT, skills_dir=self.skills, codex_root=self.codex, claude_root=self.claude) | options
                with self.assertRaisesRegex(ValueError, message):
                    render.render_units(**arguments)
        with self.assertRaisesRegex(ValueError, "control characters"):
            render.quote_argument("a\x00b")
        output = self.base / "units"
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(render.main(["--repo", str(ROOT), "--skills-dir", str(self.skills), "--codex-root", str(self.codex),
                                          "--claude-root", str(self.claude), "--output-dir", str(output)]), 0)
        self.assertIn("for review", printed.getvalue())
        self.assertEqual(sorted(path.name for path in output.iterdir()), sorted(render.UNITS))

    @unittest.skipUnless(shutil.which("systemd-analyze"), "systemd-analyze is not installed")
    def test_rendered_units_pass_systemd_analyze_verify(self):
        output = self.base / "verify"
        output.mkdir()
        for name, text in self.rendered().items():
            (output / name).write_text(text)
        result = subprocess.run(["systemd-analyze", "--user", "verify", *sorted(map(str, output.iterdir()))], capture_output=True, text=True)
        if "Failed to" in result.stderr and "bus" in result.stderr.casefold():
            self.skipTest("no user systemd manager is reachable")
        self.assertEqual(result.returncode, 0, result.stderr[-500:])


if __name__ == "__main__":
    unittest.main()
