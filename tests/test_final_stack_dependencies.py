"""Read-only consumers stay usable without generation-only validation packages."""

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FinalStackDependencyTests(unittest.TestCase):
    def isolated(self, code):
        return subprocess.run([sys.executable, "-S", "-c", code], cwd=ROOT,
                              text=True, capture_output=True, check=False)

    def test_read_only_flags_work_without_site_packages(self):
        result = self.isolated("""
import importlib.util
from pathlib import Path
from scripts import final_stack
document = {"layers": [], "runs": []}
assert isinstance(final_stack.flags(document, None), dict)
path = Path('tools/local-pages/architecture_builder.py')
spec = importlib.util.spec_from_file_location('dependency_architecture', path)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
assert builder._final_stack_flags(document, None) == final_stack.flags(document, None)
""")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generation_refuses_cleanly_when_validation_packages_are_unavailable(self):
        result = self.isolated("""
from pathlib import Path
from scripts import final_stack
try:
    final_stack.build_document(Path.cwd())
except final_stack.FinalStackError as error:
    assert str(error) == 'angle validation dependencies are unavailable'
else:
    raise AssertionError('generation accepted absent validation dependencies')
""")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_explicit_final_refusal_precedes_missing_validator_diagnostics(self):
        result = self.isolated("""
import json
from pathlib import Path
import tempfile
from scripts import final_stack
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    path = root / 'catalogs/landscape/angles/foundation-alpha.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'terminal_state': 'FINAL'}))
    try:
        final_stack.build_document(root)
    except final_stack.FinalStackError as error:
        assert str(error) == final_stack.FINAL_ADMISSION_REFUSAL
    else:
        raise AssertionError('FINAL was admitted')
""")
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
