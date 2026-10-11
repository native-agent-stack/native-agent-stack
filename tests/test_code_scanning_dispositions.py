"""Guards behind docs/decisions/2026-10-11-code-scanning-repo-level.md.

That record dismisses code-scanning alerts as false positives or won't-fix on the strength of facts about the
repository. These tests fail when a fact stops holding, so a dismissal cannot outlive its reason:

- the record's disposition table names every alert it disposes of, each exactly once;
- adoption/bootstrap-linux.sh's install_npm installs only the archive that fetch() verified against a sha256
  (alert 91: Scorecard calls any `npm install` unpinned, v5.5.0 checks/raw/shell_download_validate.go:464-490);
- every `$/` self-repository `uses:` in validate.yml and publish-catalog.yml names an action directory that exists
  at the same commit (alerts 108, 109: Scorecard v5.5.0 checks/raw/pinned_dependencies.go:800 knows only `./`).
"""

from pathlib import Path
import re
import unittest

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
INSTALL_LINE = re.compile(r"^\s*npm install .*$", re.M)


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
    """One `npm install` whose last argument is "$archive", after the fetch() that verified it."""
    installs = INSTALL_LINE.findall(body)
    fetch_at = body.find('fetch "$url" "$sha256" "$archive"')
    if len(installs) != 1 or fetch_at < 0 or fetch_at > body.index(installs[0]):
        return False
    return installs[0].split(">")[0].rstrip().endswith('"$archive"')


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
        body = function_body(self.text, "fetch")
        self.assertIn("verify_sha256", body)
        self.assertLess(body.index("exit 1"), body.index('mv -- "$destination.partial" "$destination"'))

    def test_a_registry_spec_is_caught(self) -> None:
        body = function_body(self.text, "install_npm")
        mutant = body.replace('"${npm_install_args[@]}" "$archive"', '"${npm_install_args[@]}" "$id@$version"')
        self.assertNotEqual(mutant, body)
        self.assertFalse(installs_only_verified_archive(mutant))


class SelfRepositoryReferencesTests(unittest.TestCase):
    def targets(self, path: Path) -> list[str]:
        return re.findall(r"^\s*(?:-\s+)?uses:\s*\$/(\S+)\s*$", path.read_text(encoding="utf-8"), re.M)

    def test_each_self_repository_reference_names_an_existing_local_action(self) -> None:
        found = [(workflow, target) for workflow in SELF_REPOSITORY_WORKFLOWS for target in self.targets(workflow)]
        self.assertEqual(len(found), 2)
        for workflow, target in found:
            action = ROOT / target
            self.assertTrue(
                (action / "action.yml").is_file() or (action / "action.yaml").is_file(),
                f"{workflow.name}: $/{target}",
            )


if __name__ == "__main__":
    unittest.main()
