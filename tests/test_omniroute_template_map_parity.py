"""The OmniRoute Codex profile template and the client-config map agree on standalone web search (2026-10-15).

The map holds standalone web search out for the gateway slot (adoption/new-wsl/client-config-map.json, entries for
codex/omniroute/web_search, model_providers.omniroute.supports_standalone_web_search, features.standalone_web_search),
and 2604's live ~/.codex/omniroute.config.toml reads false for both keys (key-only read, 2026-10-15T05:45Z). The
running 21128 build (3.8.51, 2a41147b7) has no api/v1/alpha route, so a request to POST /v1/alpha/search falls to the
catch-all 404 (the co-op's parity record omniroute-web-search-parity-20261015.md). The template said true; it now matches the map, and this test keeps them
together. The map also records the running build.
"""
import json
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "adoption/templates/codex.omniroute.config.toml"
MAP = ROOT / "adoption/new-wsl/client-config-map.json"


def map_override(piece: str):
    entries = json.loads(MAP.read_text(encoding="utf-8"))["entries"]
    (entry,) = [e for e in entries if piece in e.get("match", [])]
    return entry


class OmniRouteTemplateMapParity(unittest.TestCase):
    def test_the_template_and_the_map_agree_on_standalone_web_search(self):
        profile = tomllib.loads(TEMPLATE.read_text(encoding="utf-8"))
        provider = profile["model_providers"]["omniroute"]["supports_standalone_web_search"]
        feature = profile["features"]["standalone_web_search"]
        self.assertIs(provider, map_override("codex/omniroute/model_providers.omniroute.supports_standalone_web_search")["override"])
        self.assertIs(feature, map_override("codex/omniroute/features.standalone_web_search")["override"])
        self.assertEqual(map_override("codex/omniroute/web_search")["override"], "disabled")

    def test_the_map_records_the_running_gateway_build(self):
        for piece in ("codex/omniroute/model", "codex/omniroute/model_reasoning_effort"):
            note = map_override(piece)["note"]
            with self.subTest(piece=piece):
                self.assertIn("2a41147b7", note)
                self.assertIn("Superseded 2026-10-15 for the running build", note)


    def test_the_parity_record_is_cited_by_name_not_by_digest(self):
        # Digest custody (command center, 2026-10-15): the co-op's parity record is not in the repository, so the
        # template, the lane-home builder and the decision name it; a digest prefix would commit to unpublished bytes.
        for path in ("adoption/templates/codex.omniroute.config.toml", "tools/sota-convergence/landscape-sweep/build_args.py",
                     "docs/decisions/2026-10-05-omniroute-gateway-composition.md"):
            text = (ROOT / path).read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("omniroute-web-search-parity-20261015.md", text)
                self.assertIsNone(re.search(r"parity record\s*#?\s*[0-9a-f]{7,}", text))

if __name__ == "__main__":
    unittest.main()
