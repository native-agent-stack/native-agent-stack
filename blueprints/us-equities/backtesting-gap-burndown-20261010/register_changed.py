"""Use the native manifest registration API for this worktree's explicit files."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts import host_receipts


def main():
    names = set(subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True).splitlines())
    names.update(subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True).splitlines())
    excluded = {"manifests/evidence.json", "catalogs/landscape/component-evidence-matrix.json", "docs/component-evidence-matrix.md"}
    count = 0
    for name in sorted(names - excluded):
        if (ROOT / name).is_file():
            host_receipts.register_file(ROOT, name)
            count += 1
    print("registered explicit changed paths:", count)


if __name__ == "__main__":
    main()
