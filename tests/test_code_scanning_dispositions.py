"""Guards behind docs/decisions/2026-10-11-code-scanning-repo-level.md.

That record dismisses code-scanning alerts as false positives or won't-fix on the strength of facts about the
repository. These tests fail when a fact stops holding, so a dismissal cannot outlive its reason:

- the record's disposition table names every alert it disposes of, each exactly once;
- adoption/bootstrap-linux.sh's install_npm runs exactly one `npm install`, with the full argv pinned below, whose
  only package is the archive that fetch() verified against a sha256 (alert 91: Scorecard calls any `npm install`
  unpinned, v5.5.0 checks/raw/shell_download_validate.go:464-490; the tarball's own runtime dependencies are still
  resolved from the registry by range, which is why 91 is won't-fix and not a false positive);
- every `$/` self-repository `uses:` in validate.yml and publish-catalog.yml names an action directory that exists
  at the same commit (alerts 108, 109: Scorecard v5.5.0 checks/raw/pinned_dependencies.go:800 knows only `./`).
"""

from pathlib import Path
import hashlib
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests import test_adoption_bootstrap as bootstrap
from tests.test_workflow_policy import load_workflow

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs/decisions/2026-10-11-code-scanning-repo-level.md"
BOOTSTRAP = ROOT / "adoption/bootstrap-linux.sh"
SELF_REPOSITORY_WORKFLOWS = (
    ROOT / ".github/workflows/validate.yml",
    ROOT / ".github/workflows/publish-catalog.yml",
)
ALERTS = sorted(
    [14, 18, 20, 21, 22]  # repository-level Scorecard checks
    + [88, 89, 92, 97, 98]  # Scorecard PinnedDependencies in retained evidence scripts
    + [91]  # Scorecard PinnedDependencies, npm install of a verified tarball
    + [108, 109]  # Scorecard PinnedDependencies, `$/` action reference
    + list(range(99, 108))  # OSV, frozen macOS lock
)
# Mutation anchors only; the guard executes Bash and compares npm's observed argv.
INSTALL_COMMAND = 'npm install "${npm_install_args[@]}" "$archive" >/dev/null'


def expand(cell: str) -> list[int]:
    """Alert numbers in a table cell such as `99-107` or `88, 89, 92`."""
    numbers: list[int] = []
    for chunk in cell.split(","):
        low, _, high = chunk.strip().partition("-")
        numbers.extend(range(int(low), int(high or low) + 1))
    return numbers


def table_alert_numbers(text: str) -> list[int]:
    """Alert numbers in the second column of the disposition table, in table order."""
    numbers: list[int] = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("| Group |"):
            in_table = True
        elif in_table and not line.startswith("|"):
            break
        elif in_table and not set(line) <= set("|- "):
            numbers.extend(expand(line.strip("|").split("|")[1]))
    return numbers


def function_body(text: str, name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{\n(.*?)^\}}\n", text, re.S | re.M)
    if match is None:
        raise AssertionError(f"{name} not found")
    return match.group(1)


def installs_only_verified_archive(body: str) -> bool:
    """Execute the real install with existing offline stubs and compare the complete argv."""
    source = BOOTSTRAP.read_text(encoding="utf-8")
    source = source.replace(function_body(source, "install_npm"), body, 1)
    served = b"offline verified npm archive\n"
    for ignore_scripts in (True, False):
        pin = {**bootstrap.shipped_pin("socraticode"), "ignore_scripts": ignore_scripts,
               "sha256": hashlib.sha256(served).hexdigest()}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "bootstrap.sh"
            script.write_text(source, encoding="utf-8")
            # The existing shim records argv, then invokes this offline verifier.
            # Check the bytes at npm invocation time, not only after install_pin returns.
            verifier = root / "verified-npm"
            verifier.write_text(
                f"#!{sys.executable}\nfrom pathlib import Path\nimport hashlib, sys\n"
                "archive = Path(sys.argv[-1])\n"
                f"sys.exit(0 if archive.is_file() and hashlib.sha256(archive.read_bytes()).hexdigest() == {pin['sha256']!r} else 1)\n",
                encoding="utf-8")
            verifier.chmod(0o755)
            with patch.object(bootstrap, "SCRIPT_PATH", script):
                result, urls, npm_calls, uv_calls, eco = bootstrap.run_install_pin(
                    unittest.TestCase(), root, pin, served, eco_name="eco with spaces", real={"npm": verifier})
            archive = eco / f"downloads/{pin['id']}-{pin['version']}.tgz"
            prefix = Path(os.path.realpath(eco)) / f"tools/{pin['id']}-{pin['version']}"
            expected = ["install", "--global", "--no-audit", "--no-fund", "--prefix", str(prefix)]
            if ignore_scripts:
                expected.append("--ignore-scripts")
            expected.append(str(archive))
            if (result.returncode != 0 or urls != [pin["url"]] or uv_calls
                    or npm_calls != [expected] or not archive.is_file() or archive.read_bytes() != served):
                return False
    return True


class DispositionRecordTests(unittest.TestCase):
    def test_the_table_lists_each_alert_exactly_once(self) -> None:
        self.assertEqual(sorted(table_alert_numbers(RECORD.read_text(encoding="utf-8"))), ALERTS)

    def test_a_missing_and_a_duplicated_alert_are_caught(self) -> None:
        text = RECORD.read_text(encoding="utf-8")
        missing = text.replace("| 91 |", "| 90 |", 1)
        self.assertNotEqual(sorted(table_alert_numbers(missing)), ALERTS)
        duplicated = text.replace("| 88, 89, 92, 97, 98 |", "| 88, 88, 89, 92, 97, 98 |", 1)
        self.assertNotEqual(sorted(table_alert_numbers(duplicated)), ALERTS)


class NpmInstallIsVerifiedTests(unittest.TestCase):
    text = BOOTSTRAP.read_text(encoding="utf-8")

    def test_install_npm_installs_only_the_verified_archive(self) -> None:
        self.assertTrue(installs_only_verified_archive(function_body(self.text, "install_npm")))

    def test_fetch_exits_on_a_checksum_mismatch_before_the_file_is_kept(self) -> None:
        valid, invalid = b"verified archive\n", b"wrong archive\n"
        for cached, served in ((None, valid), (None, invalid), (valid, invalid),
                               (invalid, valid), (invalid, invalid)):
            with self.subTest(cached=cached, served=served), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                destination, download = root / "archive", root / "served"
                download.write_bytes(served)
                if cached is not None:
                    destination.write_bytes(cached)
                harness = ("set -Eeuo pipefail\n"
                           + bootstrap.shell_functions(self.text, "verify_sha256", "fetch")
                           + "\ncurl() { cp -- " + shlex.quote(str(download)) + ' "${@: -1}"; }\n'
                           + "fetch https://example.invalid/archive "
                           + hashlib.sha256(valid).hexdigest() + " " + shlex.quote(str(destination)) + "\n")
                result = subprocess.run(["bash", "-c", harness], capture_output=True, text=True, timeout=10)
                accepted = cached == valid or served == valid
                self.assertEqual(result.returncode, 0 if accepted else 1, result.stdout + result.stderr)
                if accepted:
                    self.assertEqual(destination.read_bytes(), valid)
                elif cached is None:
                    self.assertFalse(destination.exists(), "unverified download was promoted")
                else:
                    self.assertEqual(destination.read_bytes(), cached, "bad download replaced the cached file")

    def test_each_mutant_of_the_install_is_caught(self) -> None:
        body = function_body(self.text, "install_npm")
        argv = '"${npm_install_args[@]}" "$archive"'
        mutants = {
            "registry spec": body.replace(argv, '"${npm_install_args[@]}" "$id@$version"'),
            "extra package before the archive": body.replace(argv, '"${npm_install_args[@]}" left-pad@1.3.0 "$archive"'),
            "registry override flag": body.replace(argv, '--registry=https://example.invalid "${npm_install_args[@]}" "$archive"'),
            "extra array element": body.replace("--no-fund --prefix", "--no-fund left-pad@1.3.0 --prefix"),
            "second install": body + '  npm install "${npm_install_args[@]}" "$archive" >/dev/null\n',
            "install before the fetch": body.replace('fetch "$url" "$sha256" "$archive"', "true"),
            "fetch only after install": body.replace('fetch "$url" "$sha256" "$archive"', ":").replace(
                INSTALL_COMMAND, INSTALL_COMMAND + '\n  fetch "$url" "$sha256" "$archive"'),
            "archive reassignment": body.replace(INSTALL_COMMAND, 'archive="left-pad@1.3.0"\n  ' + INSTALL_COMMAND),
            "indexed array append": body.replace(INSTALL_COMMAND, 'npm_install_args[${#npm_install_args[@]}]="left-pad@1.3.0"\n  ' + INSTALL_COMMAND),
        }
        for name, mutant in mutants.items():
            with self.subTest(name):
                self.assertNotEqual(mutant, body)
                self.assertFalse(installs_only_verified_archive(mutant))

    def test_checksum_guard_rejects_a_bypassed_download_verifier(self) -> None:
        mutant = self.text.replace('"$destination.partial" | verify_sha256 || {',
                                   '"$destination.partial" | true || {')
        self.assertNotEqual(mutant, self.text)
        case = type(self)("test_fetch_exits_on_a_checksum_mismatch_before_the_file_is_kept")
        case.text = mutant
        result = unittest.TestResult()
        case.run(result)
        self.assertTrue(result.failures, "the checksum guard accepted an unverified promoted download")


class SelfRepositoryReferencesTests(unittest.TestCase):
    def targets(self, path: Path) -> list[str]:
        document = load_workflow(path.read_text(encoding="utf-8"))
        targets = []
        for job in document["jobs"].values():
            for step in [job, *job.get("steps", [])]:
                target = step.get("uses", "")
                if isinstance(target, str) and target.startswith("$/"):
                    targets.append(target[2:])
        return targets

    def test_each_self_repository_reference_names_an_existing_local_action(self) -> None:
        found = [(workflow, target) for workflow in SELF_REPOSITORY_WORKFLOWS for target in self.targets(workflow)]
        self.assertGreaterEqual(len(found), 2)
        for workflow, target in found:
            action = ROOT / target
            self.assertTrue(
                (action / "action.yml").is_file() or (action / "action.yaml").is_file(),
                f"{workflow.name}: $/{target}",
            )

    def test_missing_actions_are_rejected_in_all_scalar_spellings(self) -> None:
        for value in ('"$/nonexistent-action"', "'$/nonexistent-action'", "$/nonexistent-action # comment"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                workflow = Path(tmp) / "fixture.yml"
                workflow.write_text(
                    "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n"
                    "      - uses: $/.github/actions/setup-host-name-scanner\n"
                    "      - uses: $/.github/actions/setup-host-name-scanner\n"
                    "      - uses: " + value + "\n", encoding="utf-8")
                case = type(self)("test_each_self_repository_reference_names_an_existing_local_action")
                result = unittest.TestResult()
                with patch(__name__ + ".SELF_REPOSITORY_WORKFLOWS", (workflow,)):
                    case.run(result)
                self.assertTrue(result.failures, "the action guard ignored " + value)


if __name__ == "__main__":
    unittest.main()
