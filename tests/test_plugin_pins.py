#!/usr/bin/env python3
"""The plugin pin record (CPA-V-11 stage 1, adoption/plugins/pins.json): every plugin that a profile template enables resolves to a pin or to a recorded exception, the record agrees with the template's own
marketplace sources and with the revision check of adoption/bootstrap.md step 4a, and each pin is backed by the receipt that shows it. Offline: the receipts are the captures; the test never reaches a network."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "adoption/plugins/pins.json"
RECEIPTS = ROOT / "evidence/artifacts/plugin-pins-20261013"
SHA = re.compile(r"[0-9a-f]{40}")


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def enabled_plugins(template):
    """The plugins a template enables, as Claude Code reads an enabledPlugins value: `true` or a list (the 2.1.296 client's `lM(e)=e===!0||Array.isArray(e)`, bytes 215984845 and 215984892 of the binary; its
    schema bytes 208959019 and 208925317). Any other value (false, a string, a number, null, an object) enables nothing."""
    return {plugin for plugin, value in (template.get("enabledPlugins") or {}).items() if value is True or isinstance(value, list)}


def is_sha(value):
    """A full 40-character lowercase commit, and nothing around it (fullmatch: a longer text that contains one is not a commit)."""
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def tag_commit(text, repo, ref):
    """The commit that the captured resolution lists for `ref` under exactly `repo`: the peeled commit of an annotated tag, else the commit of a lightweight one; None when that repository's rows do not list it.
    A repository's rows are the indented lines below its header line `repo:` (a line at the left margin that ends in a colon) up to the next header line or a blank line: the capture lists its repositories one
    after another with no blank line between them, and a repository whose name merely ends with `repo` is another repository."""
    rows, inside = {}, False
    for line in text.splitlines():
        if not line.strip():
            inside = False
        elif not line[0].isspace() and line.endswith(":"):
            inside = line[:-1] == repo
        elif inside and "\t" in line:
            commit, name = (part.strip() for part in line.split("\t", 1))
            rows[name] = commit
    return rows.get(f"refs/tags/{ref}^{{}}") or rows.get(f"refs/tags/{ref}")


class PluginPinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(RECORD.read_text(encoding="utf-8"))
        cls.entries = {entry["id"]: entry for entry in cls.record["plugins"]}
        cls.templates = {path: load(path) for path in cls.record["templates"]}

    def enabled(self):
        return {plugin for template in self.templates.values() for plugin in enabled_plugins(template)}

    def marketplaces(self):
        found = {}
        for template in self.templates.values():
            for name, entry in (template.get("extraKnownMarketplaces") or {}).items():
                found[name] = entry.get("source")
        return found

    def test_every_enabled_plugin_of_the_templates_has_a_pin_or_a_recorded_exception_and_no_entry_is_stale(self):
        """The audit's fail-first test (CPA-V-11): every enabledPlugins entry resolves to a sha-pinned catalog entry or a recorded exception."""
        self.assertEqual(sorted(self.enabled()), sorted(self.entries), "the record names exactly the plugins the templates enable")
        self.assertEqual(len(self.entries), len(self.record["plugins"]), "one entry per plugin")

    def test_each_entry_is_a_tag_pin_a_recorded_exception_or_a_builtin_with_its_reason(self):
        for plugin, entry in self.entries.items():
            with self.subTest(plugin=plugin):
                name, _, marketplace = plugin.partition("@")
                self.assertTrue(name and marketplace, "an id is name@marketplace")
                self.assertEqual(entry["marketplace"], marketplace)
                self.assertIn(entry["pin"], ("tag", "exception", "builtin"))
                if entry["pin"] == "builtin":
                    self.assertEqual(marketplace, "builtin", "only a plugin of the builtin marketplace is pinned as a built-in")
                    self.assertTrue(entry.get("reason"), "a built-in is recorded with its reason")
                    self.assertNotIn("sha", entry)
                    continue
                self.assertTrue(is_sha(entry["sha"]), "a full 40-character lowercase commit")
                self.assertTrue(entry.get("version"))
                if entry["pin"] == "exception":
                    self.assertTrue(entry["exception"].get("reason"), "an exception states why")
                    self.assertTrue(entry["exception"].get("content_rule"), "an exception states what is checked instead")

    def test_the_record_holds_the_templates_own_marketplace_sources(self):
        """A marketplace source takes a ref and never a sha (receipts/docs-excerpts.txt), so the record's source is the template's, key for key; a tag pin has the template's ref, an exception has none."""
        sources = self.marketplaces()
        for plugin, entry in self.entries.items():
            if entry["pin"] == "builtin":
                continue
            with self.subTest(plugin=plugin):
                self.assertIn(entry["marketplace"], sources, "the template registers the plugin's marketplace")
                self.assertEqual(entry["marketplace_source"], sources[entry["marketplace"]])
                self.assertNotIn("sha", entry["marketplace_source"])
                self.assertEqual("ref" in entry["marketplace_source"], entry["pin"] == "tag")

    def test_a_tag_pin_is_the_commit_that_the_captured_tag_resolution_lists(self):
        """The pin is backed by the receipt that shows it: the peeled commit of an annotated tag, or the commit of a lightweight one, under the plugin's repository."""
        text = (RECEIPTS / "receipts/tag-resolution.txt").read_text(encoding="utf-8")
        for plugin, entry in self.entries.items():
            if entry["pin"] != "tag":
                continue
            with self.subTest(plugin=plugin):
                repo, ref = entry["marketplace_source"]["repo"], entry["marketplace_source"]["ref"]
                self.assertEqual(tag_commit(text, repo, ref), entry["sha"])

    def test_an_exception_for_a_default_branch_install_is_backed_by_the_compare_that_the_content_rule_names(self):
        """context-mode installs the default branch: the reviewed commit is held by content (the installed commit ahead of it with stats.json the only changed file), and the receipt shows the same rule against the
        commit the first host installed, and that the plugin's newest tag is not the reviewed content."""
        for plugin, entry in self.entries.items():
            if entry["pin"] != "exception":
                continue
            with self.subTest(plugin=plugin):
                compare = json.loads((RECEIPTS / entry["exception"]["compare_receipt"]).read_text(encoding="utf-8"))
                by_content = [c for c in compare["comparisons"] if c["base"] == entry["sha"]]
                self.assertEqual(len(by_content), 1)
                self.assertEqual((by_content[0]["result"]["status"], by_content[0]["result"]["files"]), ("ahead", ["stats.json"]))
                tag = [c for c in compare["comparisons"] if c["head"] == entry["sha"]]
                self.assertEqual(len(tag), 1, "the tag's commit is compared with the reviewed one")
                self.assertNotEqual(tag[0]["result"]["files"], ["stats.json"], "the tag is not the reviewed content, which is why the plugin is an exception")

    def test_the_revision_check_of_the_bootstrap_guide_holds_the_same_commits(self):
        """adoption/bootstrap.md step 4a carries a reviewed-revisions dict in its check; the record is the one source and the guide must agree with it."""
        guide = (ROOT / "adoption/bootstrap.md").read_text(encoding="utf-8")
        block = guide[guide.index("reviewed = {"):guide.index("by_content = {")]
        in_guide = dict(re.findall(r'"([a-z0-9-]+@[a-z0-9-]+)":\s*"([0-9a-f]{40})"', block))
        expected = {plugin: entry["sha"] for plugin, entry in self.entries.items() if entry["pin"] in ("tag", "exception")}
        self.assertEqual(in_guide, expected)
        self.assertEqual(sorted(re.findall(r'"([a-z0-9-]+@[a-z0-9-]+)":\s*"mksglu/context-mode"', guide)),
                         sorted(plugin for plugin, entry in self.entries.items() if entry["pin"] == "exception"), "the by-content list is the record's exceptions")

    def test_the_documented_rules_the_record_rests_on_are_in_the_captured_pages(self):
        text = (RECEIPTS / "receipts/docs-excerpts.txt").read_text(encoding="utf-8")
        self.assertIn("| `github` | `repo`, `ref`, `sha` | GitHub repository in `owner/repo` form |", text, "a plugin source carries ref and sha")
        self.assertIn("a full 40-character lowercase commit SHA", text)
        self.assertIn("A GitHub repository, with fields `repo`, `ref`, `path`, and `sparsePaths` | A GitHub repository, with fields `repo`, `ref`, and `sha`", text,
                      "a marketplace source has no sha where a plugin source has")

    def test_a_plugin_is_enabled_as_the_client_reads_the_value_true_or_a_list(self):
        """Review round 1 (the command center's read of e9a75c5d, P2-1): the client enables a plugin whose value is true or any list, so a list-enabled plugin with no entry must fail the record's test."""
        enabled = enabled_plugins({"enabledPlugins": {"a@m": True, "b@m": ["x"], "c@m": [], "d@m": ["x", "y"]}})
        self.assertEqual(enabled, {"a@m", "b@m", "c@m", "d@m"})
        for value in (False, None, "true", "yes", 1, 0, 1.0, {}, {"a": 1}):
            with self.subTest(value=repr(value)):
                self.assertEqual(enabled_plugins({"enabledPlugins": {"a@m": value}}), set(), "the client enables nothing for this value")
        self.assertEqual(enabled_plugins({}), set())
        self.assertEqual(enabled_plugins({"enabledPlugins": None}), set())

    def test_a_sha_is_forty_lowercase_hex_characters_and_nothing_else(self):
        sha = "75683c6de1ac07f6bbef00d739001679dba0740c"
        self.assertTrue(is_sha(sha))
        for value in (sha + "0", sha[:-1], sha.upper(), sha + "\n", " " + sha, "x" + sha, sha + " # tag", "", None, 40, [sha]):
            with self.subTest(value=repr(value)[:50]):
                self.assertFalse(is_sha(value))

    def test_the_tag_resolution_is_read_under_exactly_the_plugins_repository(self):
        """Review round 1 (P3-3): a repository's rows are the ones below its own header line, up to the next header or a blank line (the capture lists repositories one after another); the text of another
        repository whose name ends the same way, and the rows of the repository listed next, are not its rows, and a repository that does not list the tag yields nothing."""
        real, decoy = "a" * 40, "b" * 40
        capture = ("header of the capture:\n\n"
                   f"someone-else/owner/repo:\n  {decoy}\trefs/tags/v1^{{}}\n"
                   f"owner/repo-other:\n  {decoy}\trefs/tags/v1^{{}}\n"
                   f"owner/repo:\n  {real}\trefs/tags/v1^{{}}\n  {decoy}\trefs/tags/v1\n  {decoy}\tHEAD\n"
                   f"owner/next:\n  {decoy}\trefs/tags/v2^{{}}\n  {decoy}\trefs/tags/v3\n")
        self.assertEqual(tag_commit(capture, "owner/repo", "v1"), real, "the peeled commit of the repository's own rows")
        self.assertIsNone(tag_commit(capture, "owner/repo", "v2"), "the tag of the repository listed next is not this repository's")
        self.assertIsNone(tag_commit(capture, "owner/repo", "v3"), "nor is a lightweight tag of the repository listed next")
        self.assertEqual(tag_commit(capture, "owner/next", "v2"), decoy, "each repository still reads its own rows")
        self.assertIsNone(tag_commit(capture, "owner/missing", "v1"), "a repository that has no block")
        self.assertIsNone(tag_commit(capture, "repo", "v1"), "the end of a repository's name is not the repository")
        self.assertEqual(tag_commit(f"owner/repo:\n  {real}\trefs/tags/v1\n", "owner/repo", "v1"), real, "a lightweight tag lists its commit")
        self.assertIsNone(tag_commit(f"someone-else/owner/repo:\n  {decoy}\trefs/tags/v1^{{}}\n", "owner/repo", "v1"), "only the other repository's block is there")
        blank = f"owner/repo:\n  {real}\trefs/tags/v1\n\n  {decoy}\trefs/tags/v2\n"
        self.assertIsNone(tag_commit(blank, "owner/repo", "v2"), "a blank line ends the block")


if __name__ == "__main__":
    unittest.main()
