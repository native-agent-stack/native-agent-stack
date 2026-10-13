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


class PluginPinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(RECORD.read_text(encoding="utf-8"))
        cls.entries = {entry["id"]: entry for entry in cls.record["plugins"]}
        cls.templates = {path: load(path) for path in cls.record["templates"]}

    def enabled(self):
        return {plugin for template in self.templates.values() for plugin, on in (template.get("enabledPlugins") or {}).items() if on is True}

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
                    self.assertTrue(entry.get("reason"), "a built-in is recorded with its reason")
                    self.assertNotIn("sha", entry)
                    continue
                self.assertRegex(entry["sha"], SHA, "a full 40-character lowercase commit")
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
                block = text.split(f"{repo}:\n", 1)[1].split("\n\n", 1)[0] if f"{repo}:\n" in text else ""
                rows = {line.split("\t")[1].strip(): line.split("\t")[0].strip() for line in block.splitlines() if "\t" in line}
                commit = rows.get(f"refs/tags/{ref}^{{}}") or rows.get(f"refs/tags/{ref}")
                self.assertEqual(commit, entry["sha"])

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


if __name__ == "__main__":
    unittest.main()
