"""The trading-2604 installer's locked-project admission, run against a scratch project only.

Only the installer's hash definitions and its `step=locked-project` admission and copy block run, taken
verbatim from install-trading-2604.sh. No uv, sync, network or host-runtime command runs, and the block
writes only inside a temporary project directory. The published October 8 pair (lock f451ef97...) is a
recorded migration input since the aiohttp 3.14.4 re-pin: an install still at it must be admitted and
moved to the current lock, never accepted as current. Its bytes are the retained evidence fixture.
"""

import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "blueprints/us-equities/runtime-2604"
PROJECT = BUNDLE / "trading-2604-runtime"
INSTALLER = BUNDLE / "install-trading-2604.sh"
PUBLISHED_LOCK = ROOT / "evidence/artifacts/trading-2604-aiohttp-repin-20261020/published-f451-trading-2604-runtime.lock"
PRE_PILLOW_LOCK = ROOT / "evidence/artifacts/pillow-13-repin-20261020/historical/on-1266/blueprints/us-equities/runtime-2604/trading-2604-runtime/published-2df71327.source.txt"
PUBLISHED_ADMISSION = (
    "            ! printf '%s  %s\\n' \"$intermediate_hash\" \"$project/$filename\" | sha256sum --check --status &&\n"
    "            ! printf '%s  %s\\n' \"$published_hash\" \"$project/$filename\" | sha256sum --check --status; then\n"
)
WITHOUT_PUBLISHED = (
    "            ! printf '%s  %s\\n' \"$intermediate_hash\" \"$project/$filename\" | sha256sum --check --status; then\n"
)


def admission_script(installer_text):
    hashes = re.search(r"(?ms)^readonly lock_bundle=.*?^readonly recorded_lock_hash=[0-9a-f]{64}$", installer_text)
    block = re.search(r'(?ms)^step=locked-project$.*?(?=^"\$\{safe\[@\]\}" "\$runtime_python" -I -)', installer_text)
    if hashes is None or block is None:
        raise AssertionError("installer hash definitions or locked-project block not found")
    return hashes[0] + "\n" + block[0]


class LockedProjectAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.installer = INSTALLER.read_text()
        self.current_lock = (PROJECT / "uv.lock").read_bytes()

    def admit(self, seed, installer_text=None):
        """Run the admission block with `seed` as the existing project lock; return (result, lock bytes after)."""
        script = admission_script(installer_text if installer_text is not None else self.installer)
        with tempfile.TemporaryDirectory() as scratch:
            project = Path(scratch) / "project"
            project.mkdir()
            (project / "pyproject.toml").write_bytes((PROJECT / "pyproject.toml").read_bytes())
            (project / "uv.lock").write_bytes(seed)
            preamble = (
                "set -Eeuo pipefail\n"
                "die() { printf '%s\\n' \"$1\" >&2; exit \"$2\"; }\n"
                "temporary=''\n"
                'script_directory="$1"\n'
                'project="$2"\n'
            )
            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-c", preamble + script, "admission", str(BUNDLE), str(project)],
                capture_output=True, env={"PATH": os.defpath, "LC_ALL": "C"}, check=False,
            )
            return result, (project / "uv.lock").read_bytes()

    def test_retained_fixture_is_the_published_lock_the_installer_names(self):
        published = re.search(r"(?m)^readonly published_lock_hash=([0-9a-f]{64})$", self.installer)
        self.assertIsNotNone(published, "the installer names the published lock")
        self.assertEqual(hashlib.sha256(PUBLISHED_LOCK.read_bytes()).hexdigest(), published[1])
        self.assertNotEqual(PUBLISHED_LOCK.read_bytes(), self.current_lock)

    def test_published_lock_is_admitted_and_replaced_by_the_current_lock(self):
        result, after = self.admit(PUBLISHED_LOCK.read_bytes())
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(after, self.current_lock, "an install at f451 moves to the current lock")

    def test_pre_certifi_lock_is_admitted_and_replaced(self):
        prior = ROOT / "evidence/artifacts/certifi-2026.10.19-repin-20261020/historical/blueprints/us-equities/runtime-2604/trading-2604-runtime/published-a1413f20-uv.lock"
        seed = prior.read_bytes()
        bound = re.search(r"(?m)^readonly pre_certifi_lock_hash=([0-9a-f]{64})$", self.installer)
        self.assertIsNotNone(bound)
        self.assertEqual(hashlib.sha256(seed).hexdigest(), bound[1])
        result, after = self.admit(seed)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(after, self.current_lock)

    def test_dropping_pre_certifi_admission_refuses_that_lock(self):
        prior = ROOT / "evidence/artifacts/certifi-2026.10.19-repin-20261020/historical/blueprints/us-equities/runtime-2604/trading-2604-runtime/published-a1413f20-uv.lock"
        line = "            ! printf '%s  %s\\n' \"$pre_certifi_hash\" \"$project/$filename\" | sha256sum --check --status &&\n"
        self.assertEqual(self.installer.count(line), 1)
        mutant = self.installer.replace(line, "")
        result, after = self.admit(prior.read_bytes(), mutant)
        self.assertEqual(result.returncode, 73)
        self.assertEqual(after, prior.read_bytes())

    def test_pre_pillow_lock_is_admitted_and_replaced(self):
        result, after = self.admit(PRE_PILLOW_LOCK.read_bytes())
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(after, self.current_lock)

    def test_current_lock_passes_unchanged(self):
        result, after = self.admit(self.current_lock)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(after, self.current_lock)

    def test_unknown_lock_is_refused_and_left_in_place(self):
        unknown = self.current_lock + b"\n"
        result, after = self.admit(unknown)
        self.assertEqual(result.returncode, 73)
        self.assertIn(b"differs from all verified bundles: uv.lock", result.stderr)
        self.assertEqual(after, unknown, "a refused lock is not replaced")

    def test_dropping_the_published_admission_refuses_the_published_lock(self):
        self.assertEqual(self.installer.count(PUBLISHED_ADMISSION), 1, "the published admission line is present once")
        mutant = self.installer.replace(PUBLISHED_ADMISSION, WITHOUT_PUBLISHED)
        result, after = self.admit(PUBLISHED_LOCK.read_bytes(), mutant)
        self.assertEqual(result.returncode, 73, "without the published admission an f451 install must be refused")
        self.assertEqual(after, PUBLISHED_LOCK.read_bytes())


if __name__ == "__main__":
    unittest.main()
