"""Render-only and native syntax checks; no unit is installed or started."""

from __future__ import annotations

import importlib.util
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "tools" / "starred-maintenance" / "render_units.py"
SPEC = importlib.util.spec_from_file_location("starred_render_units", RENDERER)
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


class StarredMaintenanceTests(unittest.TestCase):
    def test_readme_documents_current_native_cli_verification(self):
        readme = (ROOT / "tools/starred-maintenance/README.md").read_text()
        self.assertIn("`%h/.local/share/mise/shims`", readme)
        self.assertIn("runs the installed", readme)
        self.assertIn("It plants no executable.", readme)
        self.assertNotIn("it now resolves a fixture", readme)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.scratch = Path(self.temporary.name)
        self.repo = self.scratch / "supplied live clone"
        (self.repo / "scripts").mkdir(parents=True)
        (self.repo / "scripts" / "build_ecosystem.py").write_text("# synthetic builder\n")
        self.state = self.scratch / "external state"
        self.questions = self.scratch / "coordination" / "lane.questions.md"

    def test_render_uses_supplied_clone_and_weekly_persistent_service(self):
        units = renderer.render_units(self.repo, self.state, self.questions)
        service, timer = units[renderer.SERVICE], units[renderer.TIMER]
        self.assertIn(str(self.repo / "scripts" / "build_ecosystem.py"), service)
        for setting in ["Type=oneshot", "UMask=0077", "TimeoutStartSec=600"]:
            self.assertIn(setting, service.splitlines())
        self.assertNotIn("[Install]", service)
        self.assertEqual(sum(line.startswith("ExecStart=") for line in service.splitlines()), 1)
        self.assertIn("ExecStart=:/usr/bin/python3", service)
        self.assertNotIn("ExecStart=-", service)
        self.assertNotIn("ExecStartPost=", service)
        for setting in ["OnCalendar=weekly", "Persistent=true", "Unit=" + renderer.SERVICE]:
            self.assertIn(setting, timer.splitlines())

    def test_render_includes_mise_shims_for_noninteractive_cli_lookup(self):
        service = renderer.render_units(self.repo, self.state, self.questions)[renderer.SERVICE]
        paths = [line.removeprefix("Environment=PATH=").split(":")
                 for line in service.splitlines() if line.startswith("Environment=PATH=")]
        self.assertEqual(len(paths), 1)
        self.assertIn("%h/.local/share/mise/shims", paths[0])

    def test_invalid_runtime_paths_are_rejected(self):
        for value in ["relative", "~/unexpanded", "/tmp/new\nline", "/tmp/tab\tpath", "/tmp/null\0path"]:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    renderer.render_units(self.repo, value, self.questions)
        for state, questions in [(self.repo / "state", self.questions), (self.state, self.repo / "questions.md")]:
            with self.subTest(state=state, questions=questions):
                with self.assertRaisesRegex(ValueError, "outside the repository"):
                    renderer.render_units(self.repo, state, questions)

    def test_symlink_paths_cannot_send_runtime_writes_into_clone(self):
        alias = self.scratch / "external-looking-link"
        try:
            alias.symlink_to(self.repo, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"symlinks unavailable: {error}")
        for state, questions in [(alias / "state", self.questions), (self.state, alias / "questions.md")]:
            with self.subTest(state=state, questions=questions):
                with self.assertRaisesRegex(ValueError, "including symlinks"):
                    renderer.render_units(self.repo, state, questions)

    def test_questions_cannot_share_the_state_directory_or_its_files(self):
        for questions in [self.state, self.state / "public-starred.latest.json",
                          self.state / "newstars-journal.json", self.state / "nested" / "questions.md"]:
            with self.subTest(questions=questions):
                with self.assertRaisesRegex(ValueError, "outside the state directory"):
                    renderer.render_units(self.repo, self.state, questions)
        self.assertFalse(self.state.exists(), "path rejection must happen before runtime writes")

    def test_questions_symlink_cannot_enter_the_state_directory(self):
        self.state.mkdir()
        alias = self.scratch / "co-op-looking-link"
        try:
            alias.symlink_to(self.state, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"symlinks unavailable: {error}")
        with self.assertRaisesRegex(ValueError, "outside the state directory"):
            renderer.render_units(self.repo, self.state, alias / "questions.md")
        self.assertEqual(list(self.state.iterdir()), [])

    def test_existing_runtime_path_types_are_checked(self):
        self.state.write_text("not a directory\n")
        with self.assertRaisesRegex(ValueError, "--state-dir must name a directory"):
            renderer.render_units(self.repo, self.state, self.questions)
        self.state.unlink()
        self.questions.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "--questions-file must name a file"):
            renderer.render_units(self.repo, self.state, self.questions)

    def test_repo_requires_its_own_builder(self):
        (self.repo / "scripts" / "build_ecosystem.py").unlink()
        with self.assertRaisesRegex(ValueError, "scripts/build_ecosystem.py"):
            renderer.render_units(self.repo, self.state, self.questions)

    def test_builder_symlink_cannot_escape_supplied_clone(self):
        builder = self.repo / "scripts" / "build_ecosystem.py"
        builder.unlink()
        external_builder = self.scratch / "external builder.py"
        external_builder.write_text("# outside the supplied clone\n")
        try:
            builder.symlink_to(external_builder)
        except OSError as error:
            self.skipTest(f"symlinks unavailable: {error}")
        with self.assertRaisesRegex(ValueError, "within the repository"):
            renderer.render_units(self.repo, self.state, self.questions)

    def test_cli_only_stages_unit_files(self):
        output = self.scratch / "review units"
        before = {path.relative_to(self.repo) for path in self.repo.rglob("*")}
        result = subprocess.run([
            sys.executable, "-B", str(RENDERER), "--repo", str(self.repo),
            "--state-dir", str(self.state), "--questions-file", str(self.questions),
            "--output-dir", str(output),
        ], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({path.name for path in output.iterdir()}, {renderer.SERVICE, renderer.TIMER})
        self.assertFalse(self.state.exists())
        self.assertFalse(self.questions.exists())
        self.assertEqual(before, {path.relative_to(self.repo) for path in self.repo.rglob("*")})

    def test_renderer_refuses_checkout_output_and_symlink_unit_targets(self):
        output = self.scratch / "review units"
        output.mkdir()
        target = self.scratch / "unchanged target"
        target.write_text("keep this file\n")
        try:
            (output / renderer.TIMER).symlink_to(target)
        except OSError as error:
            self.skipTest(f"symlinks unavailable: {error}")
        for destination in [self.repo / "units", output]:
            result = subprocess.run([
                sys.executable, "-B", str(RENDERER), "--repo", str(self.repo),
                "--state-dir", str(self.state), "--questions-file", str(self.questions),
                "--output-dir", str(destination),
            ], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
        self.assertEqual(target.read_text(), "keep this file\n")
        self.assertFalse((output / renderer.SERVICE).exists())
        self.assertFalse((self.repo / "units").exists())

    @unittest.skipUnless(shutil.which("systemd-analyze") and shutil.which("gh")
                         and Path("/usr/bin/python3").is_file(),
                         "requires installed systemd-analyze, gh and /usr/bin/python3")
    def test_native_environment_finds_gh_without_interactive_shell_path(self):
        home = Path.home()
        ecosystem_bin = home / ".local" / "share" / "codex-ecosystem" / "bin"
        mise_shims = home / ".local" / "share" / "mise" / "shims"
        output = self.scratch / "native environment review"
        output.mkdir()
        units = renderer.render_units(self.repo, self.state, self.questions)
        for name, text in units.items():
            (output / name).write_text(text, encoding="utf-8")
        runtime = self.scratch / "runtime"
        runtime.mkdir(mode=0o700)
        system_paths = [path for path in ["/usr/lib/systemd/user", "/lib/systemd/user"] if Path(path).is_dir()]
        result = subprocess.run([
            "systemd-analyze", "--user", "verify", str(output / renderer.SERVICE), str(output / renderer.TIMER)
        ], capture_output=True, text=True, timeout=20, env={
            "HOME": str(home), "PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8",
            "XDG_RUNTIME_DIR": str(runtime), "SYSTEMD_LOG_LEVEL": "debug",
            "SYSTEMD_UNIT_PATH": ":".join([str(output), *system_paths]),
        })
        self.assertEqual(result.returncode, 0, "systemd-analyze --user verify rejected rendered units")
        paths = [line.split("Environment: PATH=", 1)[1]
                 for line in (result.stdout + result.stderr).splitlines() if "Environment: PATH=" in line]
        self.assertEqual(len(paths), 1, "the rendered service must declare its own CLI PATH")
        self.assertEqual(paths[0].split(":")[0], str(ecosystem_bin))
        self.assertIn(str(mise_shims), paths[0].split(":"))
        command = subprocess.run(["gh", "--version"], capture_output=True, text=True, timeout=5,
                                 env={"PATH": paths[0], "HOME": str(home)})
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertRegex(command.stdout, r"^gh version \d+\.")

    @unittest.skipUnless(shutil.which("systemd-analyze") and Path("/usr/bin/python3").is_file(),
                         "requires installed systemd-analyze and /usr/bin/python3")
    def test_native_verify_preserves_special_path_arguments(self):
        special = 'engineering 工程 %h $HOME "quoted" \\literal'
        repo = self.scratch / special / "clone"
        (repo / "scripts").mkdir(parents=True)
        (repo / "scripts" / "build_ecosystem.py").write_text("# synthetic builder\n")
        state = self.scratch / special / "external state"
        questions = self.scratch / special / "lane questions.md"
        output = self.scratch / "native review"
        output.mkdir()
        for name, text in renderer.render_units(repo, state, questions).items():
            (output / name).write_text(text, encoding="utf-8")
        runtime = self.scratch / "runtime"
        runtime.mkdir(mode=0o700)
        system_paths = [path for path in ["/usr/lib/systemd/user", "/lib/systemd/user"] if Path(path).is_dir()]
        result = subprocess.run([
            "systemd-analyze", "--user", "verify", str(output / renderer.SERVICE), str(output / renderer.TIMER)
        ], capture_output=True, text=True, timeout=20, env={
            "PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8",
            "XDG_RUNTIME_DIR": str(runtime), "SYSTEMD_LOG_LEVEL": "debug",
            "SYSTEMD_UNIT_PATH": ":".join([str(output), *system_paths]),
        })
        self.assertEqual(result.returncode, 0, "systemd-analyze --user verify rejected rendered units")
        commands = [line.split("Command Line: ", 1)[1] for line in (result.stdout + result.stderr).splitlines()
                    if "Command Line: /usr/bin/python3" in line]
        self.assertEqual(len(commands), 1)
        # The native dump shell-escapes '$' even within double quotes; shlex
        # preserves that diagnostic escape, unlike a shell's double quoting.
        parsed = [argument.replace("\\$", "$") for argument in shlex.split(commands[0])]
        self.assertEqual(parsed, [
            "/usr/bin/python3", "-B", str(repo / "scripts" / "build_ecosystem.py"),
            "--root", str(repo), "--refresh-stars", "--starred-state-dir", str(state),
            "--newstars-questions", str(questions),
        ])


if __name__ == "__main__":
    unittest.main()
