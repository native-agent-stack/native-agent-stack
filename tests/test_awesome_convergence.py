"""Synthetic controls for the gh-only awesome-list counter, via native unittest."""

from copy import deepcopy
import json
import re
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from scripts import awesome_convergence as counter


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "evidence/artifacts/q4-awesome-convergence-20261013"


class AwesomeConvergenceTests(unittest.TestCase):
    def setUp(self):
        # Paired synthetic READMEs/HTML reflect GitHub's Markdown API contract.
        # The renderer is upstream; this fixture doesn't implement Markdown.
        self.readmes = [
            ("# AI Agents\n## Agent Memory\n- [Old](https://github.com/old/memory)\n- [Again](https://github.com/renamed/memory)\n",
             '<h1>AI Agents</h1><h2>Agent Memory</h2><ul><li><a href="https://github.com/old/memory">Old</a></li><li><a href="https://github.com/renamed/memory">Again</a></li></ul>'),
            ("# AI Agents\n## Agent Memory\n- [Memory](https://github.com/renamed/memory)\n",
             '<h1>AI Agents</h1><h2>Agent Memory</h2><ul><li><a href="https://github.com/renamed/memory">Memory</a></li></ul>'),
            ("# AI Agents\n## Agent Memory\n- [Memory](https://github.com/renamed/memory)\n",
             '<h1>AI Agents</h1><h2>Agent Memory</h2><ul><li><a href="https://github.com/renamed/memory">Memory</a></li></ul>'),
        ]
        self.corpus = {"completed_at": "2026-10-13T00:00:00Z", "lists": [],
                       "canonicalization": [
                           {"requested": name, "status": "resolved", "repository": "renamed/memory", "repository_id": 100}
                           for name in ["old/memory", "renamed/memory"]]}
        for i, (_, rendered) in enumerate(self.readmes):
            parsed = counter.parse_html(rendered)
            links = [{**link, "requested_repository": counter.repository_link(link["url"])} for link in parsed.links]
            self.corpus["lists"].append({"repository": f"list/list-{i}", "repository_id": i,
                "commit": str(i) * 40, "url": f"https://github.com/list/list-{i}",
                "documents": [{"path": "README.md", "sections": parsed.sections, "links": links}]})
        self.mapping = {"categories": list(counter.CATEGORIES), "limitations": [],
                        "rules": [{"id": "memory", "category": "agent-memory", "heading_regex": "Memory"}]}

    def test_renamed_repository_redirect_uses_api_identity(self):
        completed = subprocess.CompletedProcess([], 0, stdout=json.dumps({
            "full_name": "renamed/memory", "id": 100, "html_url": "https://github.com/renamed/memory"}), stderr="")
        with patch.object(counter, "utc", return_value="2026-10-13T00:00:00Z"), patch.object(counter.subprocess, "run", return_value=completed) as run:
            actual = counter.Github().repository("old/memory")
        self.assertEqual(actual["requested"], "old/memory")
        self.assertEqual(actual["repository"], "renamed/memory")
        self.assertEqual(actual["repository_id"], 100)
        self.assertIn("repos/old/memory", run.call_args.args[0])

    def test_duplicate_links_in_one_list_count_once(self):
        rows = counter.mapped_rows(self.corpus, self.mapping)
        result = counter.count_rows(rows)["agent-memory"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["repository"], "renamed/memory")
        self.assertEqual(result[0]["distinct_list_count"], 3)
        self.assertEqual(len(result[0]["memberships"][0]["headings"]), 2)

    def test_two_lists_do_not_meet_three_list_threshold(self):
        self.corpus["lists"].pop()
        rows = counter.mapped_rows(self.corpus, self.mapping)
        self.assertEqual(counter.count_rows(rows)["agent-memory"], [])
        self.assertEqual(counter.count_rows(rows, threshold=2)["agent-memory"][0]["distinct_list_count"], 2)

    def test_linked_files_in_one_list_do_not_add_a_vote(self):
        self.corpus["lists"].pop()
        doc = deepcopy(self.corpus["lists"][0]["documents"][0])
        doc["path"] = "categories/memory.md"
        self.corpus["lists"][0]["documents"].append(doc)
        self.assertEqual(counter.count_rows(counter.mapped_rows(self.corpus, self.mapping))["agent-memory"], [])

    def test_heading_hierarchy_and_html_table_links(self):
        rendered = '<h1>AI Agents</h1><h2>Agent Memory</h2><h3>Local</h3><table><tr><td><a href="https://github.com/renamed/memory">Memory</a></td></tr></table><h2>Other</h2><a href="https://github.com/renamed/other">Other</a>'
        parsed = counter.parse_html(rendered)
        self.assertEqual(parsed.sections[3]["headings"], ["AI Agents", "Agent Memory", "Local"])
        self.assertEqual(parsed.sections[4]["headings"], ["AI Agents", "Other"])
        self.assertEqual([link["section_id"] for link in parsed.links], ["h3", "h4"])

    def test_unresolved_links_are_retained_and_never_guessed(self):
        self.corpus["canonicalization"][0] = {"requested": "old/memory", "status": "unresolvable", "http_status": 404}
        rows = counter.mapped_rows(self.corpus, self.mapping)
        unresolved = [r for r in rows if r["resolution_status"] == "unresolvable"]
        self.assertEqual(len(unresolved), 1)
        self.assertIsNone(unresolved[0]["canonical_repository"])
        self.assertEqual(unresolved[0]["mapping_categories"], [])

    def test_images_and_self_links_do_not_vote(self):
        self.corpus["lists"][0]["documents"][0]["links"][0]["kind"] = "image"
        self.corpus["lists"][0]["documents"][0]["links"][1]["kind"] = "image"
        self.assertEqual(counter.count_rows(counter.mapped_rows(self.corpus, self.mapping))["agent-memory"], [])

    def test_repository_urls_and_non_repository_surfaces(self):
        self.assertEqual(counter.repository_link("https://github.com/Org/Repo.git/tree/main?x=1#readme"), "Org/Repo")
        for link in ["https://github.com/topics/memory", "https://github.com/sponsors/user", "https://example.com/new/memory"]:
            self.assertIsNone(counter.repository_link(link))

    def test_relative_and_pinned_category_files(self):
        self.assertEqual(counter.linked_markdown("../memory.md#local", "org/list", "categories/index.md"), "memory.md")
        self.assertEqual(counter.linked_markdown("https://github.com/org/list/blob/main/categories/memory.md", "org/list", "README.md"), "categories/memory.md")
        self.assertIsNone(counter.linked_markdown("https://github.com/other/list/blob/main/README.md", "org/list", "README.md"))
        self.assertIsNone(counter.linked_markdown("../../escape.md", "org/list", "README.md"))

    def test_api_failure_is_not_a_guessed_canonical_name(self):
        bad = subprocess.CompletedProcess([], 1, stdout="", stderr="gh: Not Found (HTTP 404)")
        with patch.object(counter, "utc", return_value="2026-10-13T00:00:00Z"), patch.object(counter.subprocess, "run", return_value=bad):
            result = counter.Github().repository("missing/repo")
        self.assertEqual(result["status"], "unresolvable")
        self.assertNotIn("repository", result)
        denied = subprocess.CompletedProcess([], 1, stdout="", stderr="gh: rate limit exceeded (HTTP 403)")
        with patch.object(counter, "utc", return_value="2026-10-13T00:00:00Z"), patch.object(counter.subprocess, "run", return_value=denied):
            with self.assertRaises(counter.GithubError):
                counter.Github().repository("missing/repo")

    def test_unmatched_sections_stay_uncategorized(self):
        self.mapping["rules"] = []
        self.assertTrue(all(not r["mapping_categories"] for r in counter.mapped_rows(self.corpus, self.mapping)))
        self.assertTrue(all(not v for v in counter.count_rows(counter.mapped_rows(self.corpus, self.mapping)).values()))

    def test_render_uses_get_html_media_type_and_exact_pin(self):
        response = subprocess.CompletedProcess([], 0, stdout='<h1>AI Agents</h1>', stderr='')
        with patch.object(counter.subprocess, "run", return_value=response) as run:
            result = counter.Github().render("org/list", "README.md", "a" * 40, 100)
        argv = run.call_args.args[0]
        self.assertEqual(result, '<h1>AI Agents</h1>')
        self.assertIn("GET", argv)
        self.assertNotIn("POST", argv)
        self.assertIn("Accept: application/vnd.github.html+json", argv)
        self.assertIn("ref=" + "a" * 40, argv)

    def test_oversize_file_is_not_rendered_or_parsed(self):
        with patch.object(counter.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "exceeds the 1 MB"):
                counter.Github().render("org/list", "README.md", "a" * 40, 1_000_001)
        run.assert_not_called()

    def test_rate_headers_retained_on_api_denial(self):
        response = subprocess.CompletedProcess([], 1,
            stdout='HTTP/2.0 403 Forbidden\nX-Ratelimit-Remaining: 0\nRetry-After: 60\n\n{"message":"denied"}',
            stderr='gh: Forbidden (HTTP 403)')
        with patch.object(counter.subprocess, "run", return_value=response):
            with self.assertRaises(counter.GithubError) as raised:
                counter.Github().api("repos/org/list")
        self.assertEqual(raised.exception.headers, {"x-ratelimit-remaining": "0", "retry-after": "60"})

    def test_raw_fixture_comments_fence_reference_link_and_setext(self):
        raw = ('# AI Agents\n'
               '<!-- https://github.com/comment/hidden -->\n'
               '```markdown\nhttps://github.com/fenced/hidden\n```\n'
               'Agent Memory\n------------\n'
               '[Memory][reference]\n'
               '[reference]: https://github.com/renamed/memory\n')
        parsed = counter.parse_raw(raw)
        self.assertEqual([r["requested_repository"] for r in parsed["links"]], ["renamed/memory"])
        section = next(r for r in parsed["sections"] if r["id"] == parsed["links"][0]["section_id"])
        self.assertEqual(section["heading"], "Agent Memory")
        self.assertEqual(section["headings"], ["AI Agents", "Agent Memory"])
        self.assertEqual(parsed["links"][0]["line"], 9)

    def test_raw_urls_include_definitions_inline_code_and_image_sources(self):
        parsed = counter.parse_raw('# Agents\n`github.com/org/inline`\n![logo](https://github.com/org/image/blob/main/logo.svg)\n[ref]: https://github.com/org/defined\n')
        self.assertEqual([r["requested_repository"] for r in parsed["links"]], ["org/inline", "org/image", "org/defined"])

    def test_set_overlap_records_both_differences_and_jaccard(self):
        rows = lambda names: [{"url": "https://github.com/org/" + n} for n in names]
        actual = counter.repository_overlap(rows(["a", "b"]), rows(["b", "c"]))
        self.assertAlmostEqual(actual["jaccard"], 1 / 3)
        self.assertEqual(actual["raw_only"], ["org/a"])
        self.assertEqual(actual["html_only"], ["org/c"])

    def test_html_corpus_cannot_supply_uniform_raw_count(self):
        with self.assertRaisesRegex(ValueError, "uniform raw corpus"):
            counter.build(self.corpus, self.mapping, "corpus.json", "mapping.json")

    def test_html_crosscheck_collects_heading_entries_and_skips_permalink(self):
        rendered = ('<div class="markdown-heading"><h2 class="heading-element">'
                    '<a href="https://github.com/paul-gauthier/aider">Aider</a></h2>'
                    '<a class="anchor" href="#aider">permalink</a></div>')
        parsed = counter.parse_html(rendered)
        self.assertEqual([r["url"] for r in parsed.links], ["https://github.com/paul-gauthier/aider"])

    def test_raw_heading_entry_uses_parent_section_and_retains_entry(self):
        parsed = counter.parse_raw('# AI Agents\n## Coding Agents\n### [Aider](https://github.com/paul-gauthier/aider)\n')
        row = parsed["links"][0]
        section = next(s for s in parsed["sections"] if s["id"] == row["section_id"])
        self.assertEqual(section["heading"], "Coding Agents")
        self.assertEqual(row["entry_heading"], '### [Aider](https://github.com/paul-gauthier/aider)')
        self.assertEqual(row["section"], "Coding Agents")

    def test_batch_canonicalization_preserves_renamed_and_missing_targets(self):
        body = {"data": {"r0": {"nameWithOwner": "renamed/memory", "url": "https://github.com/renamed/memory",
                 "id": "NODE", "databaseId": 100, "isPrivate": False}, "r1": None},
                "errors": [{"type": "NOT_FOUND", "path": ["r1"]}]}
        response = subprocess.CompletedProcess([], 1, stdout=json.dumps(body), stderr="gh: Could not resolve repository")
        with patch.object(counter, "utc", return_value="2026-10-13T00:00:00Z"), patch.object(counter.subprocess, "run", return_value=response) as run:
            rows = counter.Github().repository_batch(["old/memory", "missing/repo"])
        self.assertEqual(rows[0]["repository"], "renamed/memory")
        self.assertEqual(rows[0]["requested"], "old/memory")
        self.assertEqual(rows[1]["status"], "unresolvable")
        self.assertNotIn("repository", rows[1])
        self.assertIn("graphql", run.call_args.args[0])

    def test_batch_null_without_api_error_is_not_guessed(self):
        response = subprocess.CompletedProcess([], 0, stdout='{"data":{"r0":null}}', stderr="")
        with patch.object(counter, "utc", return_value="2026-10-13T00:00:00Z"), patch.object(counter.subprocess, "run", return_value=response):
            with self.assertRaisesRegex(ValueError, "null repository"):
                counter.Github().repository_batch(["missing/repo"])

    def test_three_list_threshold_uses_repository_membership_and_retains_category_support(self):
        for listing in self.corpus["lists"][1:]:
            listing["documents"][0]["sections"][2]["heading"] = "Other"
            listing["documents"][0]["sections"][2]["headings"] = ["AI Agents", "Other"]
        result = counter.count_rows(counter.mapped_rows(self.corpus, self.mapping))["agent-memory"]
        self.assertEqual(result[0]["distinct_list_count"], 3)
        self.assertEqual(result[0]["category_support_distinct_list_count"], 1)

    def test_raw_published_url_is_repository_identity_only(self):
        parsed = counter.parse_raw('# Agents\nhttps://github.com/org/repo/assets/example-asset-id?download=1\n')
        self.assertEqual(parsed["links"][0]["url"], "https://github.com/org/repo")

    def test_html_crosscheck_drops_ancillary_urls_and_asset_suffixes(self):
        parsed = counter.parse_html('<img src="https://example.com/image.gif?temporary=example"><a href="https://github.com/org/repo/assets/example-asset-id">repo</a>')
        self.assertEqual([r["url"] for r in parsed.links], ["https://github.com/org/repo"])

    def test_published_count_files_contain_no_forty_hex_string(self):
        for path in DIRECTORY.glob("*.json"):
            if path.name != "identifiers.json":
                self.assertIsNone(re.search(r"[0-9a-f]{40}", path.read_text(), re.I), path.name)

    def test_pin_file_contains_no_repository_name(self):
        path = DIRECTORY / "identifiers.json"
        self.assertTrue(path.is_file())
        data = json.loads(path.read_text())
        self.assertEqual(set(data), {"schema_version", "identifiers"})
        for row in data["identifiers"]:
            self.assertEqual(set(row), {"id", "value"})
            self.assertRegex(row["id"], r"^I\d+$")
            self.assertRegex(row["value"], r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
        self.assertNotRegex(path.read_text(), r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")

    def test_reference_encoding_is_lossless_for_typed_metadata(self):
        original = {"repository": "org/repo", "pin": "a" * 40, "sha256": "b" * 64,
                    "command": "contents/README.md?ref=" + "a" * 40}
        refs = counter.PublicationReferences()
        packed = refs.pack(original, counter.metadata_identifiers(original))
        self.assertIsNone(re.search(r"[0-9a-f]{40}", json.dumps(packed)))
        self.assertEqual(refs.unpack(packed), original)
        self.assertNotIn("org/repo", json.dumps(refs.registry()))

    def test_unclassified_opaque_string_is_not_relocated(self):
        original = {"repository": "org/repo", "unclassified": "d" * 40}
        refs = counter.PublicationReferences()
        self.assertEqual(refs.pack(original, counter.metadata_identifiers(original)), original)
        self.assertEqual(refs.registry()["identifiers"], [])

    def test_count_references_round_trip_and_reject_wrong_document_owner(self):
        sources = {"schema_version": 1, "lists": [
            {"id": "L1", "repository": "list/one", "commit": "a" * 40, "url": "https://github.com/list/one"},
            {"id": "L2", "repository": "list/two", "commit": "b" * 40, "url": "https://github.com/list/two"}],
            "documents": [{"id": "D1", "list_id": "L1", "path": "README.md"}, {"id": "D2", "list_id": "L2", "path": "README.md"}]}
        original = {"list_repository": "list/one", "list_commit": "a" * 40,
                    "list_url": "https://github.com/list/one", "file": "README.md", "canonical_repository": "org/repo"}
        refs = counter.PublicationReferences(sources=sources)
        encoded = refs.count_references(original)
        self.assertEqual(encoded["list_id"], "L1")
        self.assertEqual(encoded["document_id"], "D1")
        self.assertNotIn("list_repository", encoded)
        self.assertNotIn("list_commit", encoded)
        self.assertEqual(refs.restore_count(encoded), original)
        encoded["document_id"] = "D2"
        with self.assertRaisesRegex(ValueError, "different list"):
            refs.restore_count(encoded)


if __name__ == "__main__":
    unittest.main()
