"""Targeted bootstrap dispatch, with vendor installers stubbed at their boundary.

The real parser, preflight, pin reader, dispatch and bounded version report run.
Only native package installation is replaced; no network or host install occurs.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SelectedPinsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        adoption = self.root / "adoption"
        (adoption / "skills").mkdir(parents=True)
        for name in ("manifest.json", "pins-linux-x86_64.json", "skills/manifest.json"):
            shutil.copyfile(ROOT / "adoption" / name, adoption / name)
        text = (ROOT / "adoption/bootstrap-linux.sh").read_text()
        # Existing suite uses the same native-function seam; retain every
        # selection and verification statement, replacing only the installers.
        marker = "installed_pin_ids=()"
        stubs = r'''
stub_install() {
  printf '%s\n' "$1" >>"$ecosystem_root/selected.log"
  local command="$1"
  [[ "$command" != tavily-cli ]] || command=tvly
  printf '#!/bin/sh\nprintf "%%s\\n" "%s"\n' "$2" >"$bin_dir/$command"
  chmod +x "$bin_dir/$command"
}
install_npm() { stub_install "$1" "$2"; }
install_uv_tool() { stub_install "$1" "$2"; }
install_single_binary_tarball() { stub_install "$1" "$2"; }
'''
        self.script = adoption / "bootstrap-linux.sh"
        self.script.write_text(text.replace(marker, stubs + "\n" + marker, 1))
        self.eco = self.root / "ecosystem"
        self.env = {**os.environ, "HOME": str(self.root / "home"), "ECO_INSTALL_ROOT": str(self.eco)}

    def run_bootstrap(self, *args):
        return subprocess.run(["bash", str(self.script), "--skip-system-packages", *args],
                              capture_output=True, text=True, env=self.env, timeout=60)

    def test_only_installs_requested_pins_and_checks_their_declared_versions(self):
        result = self.run_bootstrap("--only", "skills", "--only", "tavily-cli", "--only", "orx")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.eco / "selected.log").read_text().splitlines(), ["skills", "tavily-cli", "orx"])
        self.assertIn("summary: 3 verified, 0 failed", result.stdout)
        self.assertFalse((self.eco / "bin/agent-browser").exists())
        self.assertFalse((self.eco / "bin/node").exists())
        self.assertFalse((self.root / "home/.profile").exists())

    def test_unknown_selection_refuses_before_creating_an_install_root(self):
        result = self.run_bootstrap("--only", "not-a-pinned-component")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.eco.exists())

    def test_only_cannot_be_combined_with_a_profile_or_profile_configuration(self):
        for extra in (("--profile", "foundation-cpu"), ("--configure-full-profile",)):
            with self.subTest(extra=extra):
                result = self.run_bootstrap("--only", "orx", *extra)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertFalse(self.eco.exists())

    def test_duplicate_selections_install_once(self):
        result = self.run_bootstrap("--only", "orx", "--only", "orx")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.eco / "selected.log").read_text().splitlines(), ["orx"])

    def test_null_hash_refuses_before_the_vendor_installer_runs(self):
        path = self.root / "adoption/pins-linux-x86_64.json"
        data = json.loads(path.read_text())
        next(pin for pin in data["tools"] if pin["id"] == "orx")["sha256"] = None
        path.write_text(json.dumps(data))
        result = self.run_bootstrap("--only", "orx")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("no verified sha256", result.stderr)
        self.assertFalse((self.eco / "selected.log").exists())

    def test_wrong_installed_version_fails_the_normal_bounded_report(self):
        text = self.script.read_text().replace('stub_install "$1" "$2"; }',
                                                'stub_install "$1" "0.0.0"; }')
        self.script.write_text(text)
        result = self.run_bootstrap("--only", "orx")
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertIn("summary: 0 verified, 1 failed", result.stdout)

    def test_skills_version_is_read_from_the_skills_manifest(self):
        path = self.root / "adoption/skills/manifest.json"
        data = json.loads(path.read_text())
        data["cli"]["version"] = "3.2.1"
        path.write_text(json.dumps(data))
        result = self.run_bootstrap("--only", "skills")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("verified (exact 3.2.1)", result.stdout)


if __name__ == "__main__":
    unittest.main()
