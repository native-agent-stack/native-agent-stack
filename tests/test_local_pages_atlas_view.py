"""Harness atlas view: section order, state marks, labelled tables, stylesheet rules, privacy, URLs, unknowns and copy.

Pages are built from the shared synthetic roots (tests/local_pages_atlas_fixture.py). Private-looking values are
assembled at run time and written into every source the page reads; none may reach the rendered page. The cascade
tests read what the stylesheets do to the built page's own elements (tests/local_pages_css_cascade.py).
"""
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_pages_atlas_fixture import HERE, HISTORY, LATEST, Fixture, final_stack, history, lane, latest, slots  # noqa: E402
from local_pages_css_cascade import Cascade, Declaration  # noqa: E402

SECTIONS = ["atlas-terms", "atlas-layers", "atlas-stacks", "atlas-measured", "atlas-routing", "atlas-monitoring", "atlas-rules", "atlas-changes", "atlas-evidence"]
# The sheets the page inlines after the linked site.css, in this order (atlas_data.STYLES).
INLINE_SHEETS = ("architecture-manifest.css", "overview.css", "atlas.css")
# 320px, both site.css breakpoint bands (40-62rem and 62-72rem), 1440px, and print at an A4 width (794px), in rem.
SETTINGS = (("screen", 20.0), ("screen", 50.0), ("screen", 65.0), ("screen", 90.0), ("print", 49.625))


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


def _pixels(value: str) -> float:
    """A length in px or rem; the root font size is the browser default, 16px (site.css sets none)."""
    match = re.fullmatch(r"([\d.]+)(px|rem)", value)
    if match is None:
        raise ValueError(f"not a px or rem length: {value!r}")
    return float(match.group(1)) * (16 if match.group(2) == "rem" else 1)


class CascadeRecordTests(unittest.TestCase):
    """Reviews B7 to B9: the cascade helper's packages are pinned, and the plan and the stylesheet say what the tests and the page do."""
    ROOT = HERE.parents[1]

    def test_the_cascade_helper_packages_are_hash_pinned_for_ci(self):
        text = (self.ROOT / ".github/requirements-ci.txt").read_text()
        for name, version in (("cssselect2", "0.10.1"), ("tinycss2", "1.5.1"), ("webencodings", "0.6.1")):
            with self.subTest(package=name):
                entry = re.search(rf"^{name}=={re.escape(version)} \\\n((?:    --hash=sha256:[0-9a-f]{{64}}(?: \\)?\n?)+)", text, re.M)
                self.assertIsNotNone(entry, f"{name}=={version} with hashes")
                self.assertGreaterEqual(len(re.findall(r"--hash=sha256:", entry.group(1))), 2)
        plan = (HERE / "design-plan.md").read_text()
        self.assertIn("**CSS cascade helper.**", plan)
        for named in ("cssselect2 0.10.1", "tinycss2 1.5.1", "9,905", "76,717"):
            self.assertIn(named, " ".join(plan.split()))

    def test_the_plan_and_the_helper_describe_what_matcher_match_returns(self):
        """Fold 3 review B5: at the pin Matcher.match returns sorted (specificity, order, pseudo, payload) tuples, not the payloads."""
        tuples = "(specificity, order, pseudo, payload)"
        self.assertIn(tuples, " ".join((HERE / "design-plan.md").read_text().split()))
        self.assertIn(tuples, " ".join((self.ROOT / "tests/local_pages_css_cascade.py").read_text().split()))
        self.assertNotIn("returns the payloads", (self.ROOT / "tests/local_pages_css_cascade.py").read_text())

    def test_the_plan_and_the_stylesheet_say_same_named_properties(self):
        """B8: the helper compares only same-named properties at one importance, so no text claims to check each or every declaration."""
        plan, css = (HERE / "design-plan.md").read_text(), (HERE / "assets/atlas.css").read_text()
        self.assertIn("winning atlas declaration of each property", " ".join(plan.split()))
        self.assertIn("same-named property", " ".join(plan.split()))
        self.assertIn("compares same-named properties", css)
        for text in (plan, css):
            self.assertNotRegex(text, r"checks (each|every) (atlas )?declaration")

    def test_the_plan_says_which_identifiers_the_page_sets_in_monospace(self):
        """B9: atlas_view renders <code> for more than pins, paths and record names, and the Type line says so."""
        plan = (HERE / "design-plan.md").read_text()
        self.assertNotIn("monospace only for pins, paths and record names", plan)
        start = plan.index("**Tokens.** The palette above is unchanged and the atlas")
        type_line = " ".join(plan[start:plan.index("**Layout.**", start)].split())
        for named in ("pins", "paths", "record", "catalog layer ids", "slot keys", "model ids", "effort values", "route text", "MCP server names",
                      "agent roles", "monitoring commands", "ccusage command", "change kinds"):
            self.assertIn(named, type_line)
        view = (HERE / "atlas_view.py").read_text()
        self.assertGreater(view.count("<code>"), 10)


class CascadeTests(ViewCase):
    """What the stylesheets do to the built page's elements; design-plan.md "Atlas page" records the browser measurement."""

    def cascade(self) -> Cascade:
        fixture = Fixture(self.base)
        # Sixteen closed days, so the two oldest fold into the older-days disclosure.
        Fixture.write(fixture.state / HISTORY, json.dumps(history(tuple(f"2026-09-{day:02d}" for day in range(16, 0, -1)))))
        html = self.page(fixture)
        inline = [(name, (HERE / "assets" / name).read_text()) for name in INLINE_SHEETS]
        self.assertIn("<style>\n" + "".join(text for _, text in inline), html)
        self.assertLess(html.index('<link rel="stylesheet" href="assets/site.css">'), html.index("<style>"))
        return Cascade(html, [("site.css", (HERE / "assets/site.css").read_text())] + inline)

    def test_every_disclosure_summary_is_at_least_44px_tall(self):
        """Rule 13 and DP:31: controls are at least 44px tall, and a summary is its disclosure's control."""
        page = self.cascade()
        summaries = [element for element in page.elements if element.tag == "summary"]
        self.assertEqual({re.sub(r"^\d+ ", "", "".join(element.text)) for element in summaries}, {"What each slot sets", "older closed days", "List them"})
        for setting in SETTINGS[:4]:
            for summary in summaries:
                label = f'{"".join(summary.text)} at {setting[1]}rem'
                floor = page.winner(summary, "min-height", setting)
                self.assertIsNotNone(floor, label)
                self.assertGreaterEqual(_pixels(floor.value), 44, label)
                for cap in ("height", "max-height"):
                    self.assertIsNone(page.winner(summary, cap, setting), label)

    def test_empty_is_evaluated_against_the_real_text_and_children(self):
        """Review B1 (fold 3): cssselect2 tests :empty on the ElementTree node's children and text, so the helper's tree must carry both."""
        html = ('<html><body><p class="none"></p><p class="text">words</p><p class="child"><i></i></p>'
                '<p class="tail"><i></i>after</p><p class="space"> </p></body></html>')
        page = Cascade(html, [("probe.css", "p:empty { color: red }")])
        setting = ("screen", 50.0)
        found = {element.attrs["class"]: page.winner(element, "color", setting) is not None for element in page.elements if element.tag == "p"}
        self.assertEqual(found, {"none": True, "text": False, "child": False, "tail": False, "space": False})

    def test_every_atlas_override_of_a_shared_rule_wins_by_specificity(self):
        """Rule 15 and FD:55: where atlas.css and a shared sheet set one property of one element to different values at
        the same importance, the atlas declaration has the higher specificity, so stylesheet order never decides."""
        page = self.cascade()
        breaches = set()
        for setting in SETTINGS:
            for element in page.elements:
                declared: dict[str, list[Declaration]] = {}
                for declaration in page.declarations(element, setting):
                    declared.setdefault(declaration.property, []).append(declaration)
                for name, found in declared.items():
                    own = max((item for item in found if item.sheet == "atlas.css"), key=Declaration.rank, default=None)
                    if own is None:
                        continue
                    for shared in found:
                        if (shared.sheet != "atlas.css" and shared.value != own.value and shared.important == own.important
                                and own.specificity <= shared.specificity):
                            breaches.add(f"{setting[0]} at {setting[1]}rem, {name}: {own.selector} {own.specificity} against "
                                         f"{shared.sheet} {shared.selector} {shared.specificity}")
        self.assertEqual(sorted(breaches), [])

    def test_the_display_serif_sets_only_the_title_and_the_matrix_row_headers(self):
        """The Type line and rule 11: the serif marks the title and the matrix row headers; section headings keep the sans."""
        page = self.cascade()

        def in_matrix(element) -> bool:
            while element is not None and "atlas-matrix" not in element.classes:
                element = element.parent
            return element is not None

        expected = [element for element in page.elements
                    if element.tag == "h1" or (element.tag == "th" and element.attrs.get("scope") == "row" and in_matrix(element))]
        self.assertEqual([element.label() for element in expected], ["h1"] + ["th"] * 7)
        headings = [element for element in page.elements if element.tag == "h2"]
        self.assertEqual(len(headings), len(SECTIONS))
        for setting in SETTINGS:
            serif = [element for element in page.elements
                     if (winner := page.winner(element, "font-family", setting)) is not None and winner.value == "var(--mf-display)"]
            self.assertEqual([id(element) for element in serif], [id(element) for element in expected], (setting, [element.label() for element in serif]))
            for heading in headings:
                self.assertEqual(page.winner(heading, "font-family", setting).value, "var(--font)", heading.label())

    def test_print_releases_every_table_minimum_width(self):
        """atlas.css's print block: the minimum widths that outrank site.css's print table rule (:470) are released."""
        page = self.cascade()
        tables = [element for element in page.elements if element.tag == "table"]
        self.assertGreater(len(tables), 10)
        for table in tables:
            self.assertEqual(page.winner(table, "min-width", ("print", 49.625)).value, "0", table.parent.label())


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

    def test_an_unknown_advisor_field_renders_as_unknown_never_zero_or_a_partial_sum(self):
        """Review B4: {"input": 5, "output": null} is 5 input and unknown output; a lane with any known field takes part, and an
        unknown field in it makes that total unknown; a lane whose fields are all unknown is ignored."""
        def note(**advisors):
            fixture = Fixture(self.base / "-".join(advisors))
            projection = latest()
            for lane_key, value in advisors.items():
                projection["rollup"]["lanes"].setdefault("claude:" + lane_key, lane())["advisor"] = value
            Fixture.write(fixture.state / LATEST, json.dumps(projection))
            return re.search(r"Advisor sub-inference.*?</p>", self.section(self.page(fixture), "atlas-measured"), re.S).group(0)
        half = note(workflow={"input": 5, "output": None})
        self.assertIn("adds 5 input and unknown output tokens", half)
        self.assertNotIn("0 output", half)
        mixed = note(workflow={"input": 5, "output": None}, main={"input": 1, "output": 2})
        self.assertIn("adds 6 input and unknown output tokens", mixed)
        self.assertIn("adds 1,234 input and 56 output tokens", note(workflow={"input": 1234, "output": 56}, agent_tool={"input": None, "output": None}))

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
