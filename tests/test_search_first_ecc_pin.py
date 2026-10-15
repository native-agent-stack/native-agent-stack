"""The research skill must consume the selected ECC component identity.

Source: affaan-m/ECC@dd6ee538aee0f548d4a6b520118f875431fd749e,
skills/search-first/SKILL.md. The earlier c70874fa tree is a different payload.
"""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SearchFirstEccPinTests(unittest.TestCase):
    def test_search_first_uses_stack_ecc_revision(self):
        stack = json.loads((ROOT / 'manifests/stack.json').read_text())
        manifest = json.loads((ROOT / 'adoption/skills/manifest.json').read_text())
        ecc = next(row for row in stack['components'] if row['id'] == 'affaan-m/ECC')
        skill = next(row for row in manifest['skills'] if row['name'] == 'search-first')
        # A component pin must govern the payload selected by the installer,
        # not just a documentation label alongside a different skill commit.
        selected = ecc.get('source_pin') or ecc['version']
        self.assertEqual(selected, skill['ref'])
        self.assertEqual(f"https://github.com/{skill['source']}/tree/{selected}/{skill['path']}", skill['url'])


if __name__ == '__main__':
    unittest.main()
