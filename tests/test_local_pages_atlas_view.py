"""Harness atlas view: section order, state marks, labelled tables, stylesheet rules, privacy, URLs, unknowns and copy.

Pages are built from the shared synthetic roots (tests/local_pages_atlas_fixture.py). Private-looking values are
assembled at run time and written into every source the page reads; none may reach the rendered page.
"""
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_pages_atlas_fixture import HERE, LATEST, Fixture, final_stack, lane, latest, slots  # noqa: E402

SECTIONS = ["atlas-terms", "atlas-layers", "atlas-stacks", "atlas-measured", "atlas-routing", "atlas-monitoring", "atlas-rules", "atlas-changes", "atlas-evidence"]


class ViewCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="atlas-view-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)

    def page(self, fixture=None) -> str:
        fixture = fixture or Fixture(self.base)
        _, html, _ = fixture.build(self.base)
        return html

    @staticmethod
    def section(html: str, ident: str) -> str:
        start = html.index(f'id="{ident}"')
        following = [html.index(f'id="{other}"') for other in SECTIONS if f'id="{other}"' in html and html.index(f'id="{other}"') > start]
        return html[start:min(following) if following else len(html)]


class StructureTests(ViewCase):
    def test_nine_sections_appear_in_order_their_links_resolve_and_no_heading_is_numbered(self):
        html = self.page()
        positions = [html.index(f'<section class="mf-view ov-section" id="{ident}"') for ident in SECTIONS]
        self.assertEqual(positions, sorted(positions))
        links = re.findall(r'<nav class="mf-jump" aria-label="Page sections"><ul>(.*?)</ul></nav>', html)[0]
        self.assertEqual(re.findall(r'href="#([a-z-]+)"', links), SECTIONS)
        for heading in re.findall(r"<h[1-4][^>]*>(.*?)</h[1-4]>", html):
            self.assertNotRegex(heading, r"^\s*(?:\d+[.)]?|0\d)\s")
        self.assertIn('href="#atlas-evidence"', html)

    def test_every_state_mark_has_a_glyph_and_a_text_label(self):
        html = self.page()
        marks = re.findall(r'<svg class="mf-glyph"[^>]*>.*?</svg>([^<]*)', html)
        self.assertGreater(len(marks), 10)
        for label in marks:
            self.assertTrue(label.strip(), "a glyph without its text label")

    def test_every_table_is_captioned_scoped_and_in_a_labelled_scroll_region(self):
        html = self.page()
        wrappers = re.findall(r'<div class="table-wrap[^"]*" tabindex="0" role="region" aria-label="([^"]+)"><table><caption[^>]*>([^<]+)</caption>', html)
        self.assertEqual(len(wrappers), html.count("<table>"))
        for label, caption in wrappers:
            self.assertEqual(label, caption)
        for table in re.findall(r"<table>.*?</table>", html, re.S):
            self.assertIn('scope="col"', table)

    def test_the_matrix_has_seven_layer_rows_and_three_family_columns_naming_their_clients(self):
        matrix = re.search(r'aria-label="Seven harness layers by model family">(.*?)</table>', self.page(), re.S).group(1)
        self.assertEqual(len(re.findall(r'<th scope="row"', matrix)), 7)
        head = re.search(r"<thead>(.*?)</thead>", matrix, re.S).group(1)
        families = re.findall(r'<th scope="col">([^<]+)<small>(.*?)</small></th>', head)
        self.assertEqual([family for family, _ in families], ["Claude", "GPT", "Muse"])
        for (_, client), name in zip(families, ("Claude Code", "Codex", "Muse Code")):
            self.assertIn(name, client)
        self.assertIn("running <code>muse-wonder-full-1.0</code>", families[2][1])
        self.assertIn("No recorded mechanism", matrix)


class StyleTests(unittest.TestCase):
    def test_the_stylesheet_uses_tokens_only_and_no_uppercase_or_motion(self):
        css = (HERE / "assets/atlas.css").read_text()
        rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        self.assertNotRegex(rules, r"#[0-9a-fA-F]{3,8}\b")
        self.assertNotRegex(rules, r"\b(?:rgba?|hsla?)\(")
        self.assertNotRegex(rules, r"text-transform\s*:\s*uppercase")
        self.assertNotRegex(rules, r"\banimation\b|\btransition\b")
        for selector in re.findall(r"([^{}]+)\{", rules):
            if selector.strip().startswith("@"):
                continue  # an at-rule prelude such as @media print, not a selector
            for part in selector.split(","):
                self.assertTrue(part.strip().startswith(('body[data-page="atlas"]', ".atlas-")), part.strip())


class PrivacyTests(ViewCase):
    def test_private_values_in_every_source_never_reach_the_page(self):
        home = "/".join(("", "home", "fixture-user", "notes"))
        email = "fixture.person" + "@" + "example.org"
        api = "sk-" + "a" * 30
        github = "gh" + "p_" + "B" * 36
        session = "-".join(("1234abcd", "0000", "1111", "2222", "3333abcd4444"))
        task = "task-" + "abcd1234" + "-" + "zyx987"
        host = "native" + "stack" + "lab"
        artifact = "https://claude" + ".ai/artifact/" + "fixture"
        private = [home, email, api, github, session, host, artifact]
        fixture = Fixture(self.base)
        stack = final_stack()
        stack["layers"][2]["title"] = "Code navigation " + host
        stack["layers"][0]["winners"][0]["component_id"] = "tool-" + github
        stack["runs"][2]["pin"] = "1.0.0 " + email
        Fixture.write(fixture.root / "catalogs/landscape/final-stack.json", json.dumps(stack))
        foundation = json.loads((fixture.root / "catalogs/landscape/foundation.json").read_text())
        foundation["layers"][0]["requirement"] = "Keep decisions in " + home + " for " + email
        foundation["layers"][1]["requirement"] = "Supply context from " + task + " only"
        Fixture.write(fixture.root / "catalogs/landscape/foundation.json", json.dumps(foundation))
        practice = slots()
        practice["slots"][0]["default"] = "Store the key " + api + " at " + artifact
        practice["slots"][1]["route"] = "Session " + session + " gets the 1-hour TTL; " + host + " gets 5 minutes"
        Fixture.write(fixture.root / ".claude/skills/claude-native-practice/reference/slots.json", json.dumps(practice))
        Fixture.write(fixture.root / "adoption/agents/claude/stack-verifier.md", "---\nmodel: " + email + "\neffort: " + api + "\n---\n")
        projection = latest()
        projection["servers"].append({"name": api, "repository": "https://github.com/fixture/memory-server"})
        projection["rollup"]["lanes"]["claude:workflow"]["models"] = {"claude-" + host: 1, email: 2, "claude-opus-5-5": 3}
        projection["rollup"]["lanes"]["claude:workflow"]["note"] = home
        projection["note"] = artifact
        Fixture.write(fixture.state / LATEST, json.dumps(projection))
        manifest = json.loads((fixture.root / "adoption/skills/manifest.json").read_text())
        manifest["skills"][0]["source"] = email
        Fixture.write(fixture.root / "adoption/skills/manifest.json", json.dumps(manifest))
        html = self.page(fixture)
        for value in private + [task, "fixture-user"]:
            self.assertNotIn(value, html, value)
        self.assertIn("${LOCAL_TASK_HANDLE}", html)
        self.assertIn("Withheld: it names a path, URL or token", html)

    def test_every_url_on_the_page_is_a_loopback_url(self):
        html = self.page()
        urls = re.findall(r"https?://[^\s\"'<>]+", html)
        self.assertTrue(urls)
        for url in urls:
            self.assertRegex(url, r"^http://127\.0\.0\.1:\d+(?:/[\w./~-]*)?$")


class UnknownAndCopyTests(ViewCase):
    def test_unknown_renders_not_measured_with_its_reason_and_a_zero_denominator_renders_no_data(self):
        fixture = Fixture(self.base)
        projection = latest()
        projection["rollup"]["lanes"]["claude:agent_tool"] = {**lane(tool_calls=0, mcp={}), "usage": {key: 0 for key in lane()["usage"]}}
        projection["rollup"]["lanes"]["claude:main"] = {**lane(), "actors": None, "tool_calls": None, "mcp": None, "mcp_other": None, "usage": None, "unmeasured": "collector_failed"}
        Fixture.write(fixture.state / LATEST, json.dumps(projection))
        section = self.section(self.page(fixture), "atlas-measured")
        main = re.search(r"Claude main sessions</strong>.*?</tr>", section, re.S).group(0)
        self.assertIn("Not measured: the collector did not run", main)
        self.assertNotIn("<td>0</td>", main)
        muse = re.search(r"Muse fenced runs</strong>.*?</tr>", section, re.S).group(0)
        self.assertIn("Not measured: no Muse receipt root is configured", muse)
        agent = re.search(r"Claude Agent-tool subagents</strong>.*?</tr>", section, re.S).group(0)
        self.assertIn("No data", agent)

    def test_an_unparsable_projection_says_so_and_never_claims_the_projection_has_not_run(self):
        fixture = Fixture(self.base)
        Fixture.write(fixture.state / LATEST, "{not json")
        section = self.section(self.page(fixture), "atlas-measured")
        self.assertIn("Not measured: the daily token projection does not parse, so it is kept for inspection.", section)
        self.assertIn("the next run of token-rate.timer publishes a projection that parses", section)
        self.assertNotIn("has not run", section)

    def test_rtk_use_is_labelled_per_client(self):
        fixture = Fixture(self.base)
        projection = latest()
        projection["rollup"]["lanes"]["gpt:codex"]["rtk"] = {"rewrites": None, "typed": 2, "shell_calls": 8}
        Fixture.write(fixture.state / LATEST, json.dumps(projection))
        section = self.section(self.page(fixture), "atlas-measured")
        codex = re.search(r"Codex sessions</strong>.*?</tr>", section, re.S).group(0)
        self.assertIn("2 of 8<small>typed with the rtk prefix</small>", codex)
        workflow = re.search(r"Claude Workflow agents</strong>.*?</tr>", section, re.S).group(0)
        self.assertIn("3 of 6<small>rewritten by the hook; 0 typed</small>", workflow)

    def test_advisor_sub_inference_is_stated_apart_from_the_token_columns(self):
        fixture = Fixture(self.base)
        projection = latest()
        projection["rollup"]["lanes"]["claude:workflow"]["advisor"] = {"input": 1234, "output": 56}
        Fixture.write(fixture.state / LATEST, json.dumps(projection))
        section = self.section(self.page(fixture), "atlas-measured")
        self.assertIn("Advisor sub-inference, which the kernel counts apart, adds 1,234 input and 56 output tokens", section)
        self.assertNotIn("Advisor sub-inference", self.section(self.page(Fixture(self.base / "plain")), "atlas-measured"))

    def test_pending_and_failure_blocks_name_what_makes_them_present(self):
        fixture = Fixture(self.base, projections=False, agents=())
        html = self.page(fixture)
        measured = self.section(html, "atlas-measured")
        self.assertIn("Ready when", measured)
        self.assertIn("the CC installs token-rate.timer (tools/skill-usage/README.md)", measured)
        rules = self.section(html, "atlas-rules")
        self.assertEqual(rules.count("Ready when the CC names the ruling record."), 3)
        routing = self.section(html, "atlas-routing")
        self.assertIn("Pending: the definition is not in the checkout", routing)
        self.assertIn("The observed models appear once the daily token projection is published and readable.", routing)


if __name__ == "__main__":
    unittest.main()
