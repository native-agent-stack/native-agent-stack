"""The 2026-10-17 currency re-pin: the seven profile rows, the claude-hud tag and the public records agree.

docs/decisions/2026-10-17-currency-sweep-repin.md states the versions below. Every test here except test_the_held_rows_stay_where_the_record_says fails on the plan files as they stood
before that change (the old pins, rows without their receipts and blocking gaps, a SocratiCode command with a buffer of our own, a claude-hud tag that differed across the template, the
client map, bootstrap and the recipe row); the held-rows test guards the two rows that did not move.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "adoption/new-wsl-profile.json"
RECORDS = ROOT / "evidence/artifacts/currency-sweep-20261017"
RECORDS_REL = "evidence/artifacts/currency-sweep-20261017/"
DECISION = ROOT / "docs/decisions/2026-10-17-currency-sweep-repin.md"
HUD_TAG = "v0.11.3"
HUD_COMMIT = "5621429b84ea2503185221244c43a06797bfd05e"
HUD_OLD_COMMITS = ("ad322b8d9016816a1858334ba57a085512110e83", "75683c6de1ac07f6bbef00d739001679dba0740c")   # v0.11.2 and v0.10.0

# row name -> (pin, public record tool name, values the row must no longer carry)
ROWS = {
    "RTK": ("1.0.1", "rtk", ("0.51.0",)),
    "Serena": ("2.0.0", "serena", ("c6fbd1c5", "2.0.0.dev0")),
    "Chrome DevTools MCP": ("1.11.0", "chrome-devtools-mcp", ("1.10.1", "e52c6b59")),
    "jcodemunch-mcp": ("1.108.374", "jcodemunch-mcp", ("1.108.327", "6d5ae86c")),
    "promptfoo": ("0.124.1", "promptfoo", ("0.123.1",)),
    "SocratiCode": ("1.16.1", "socraticode", ("1.15.0",)),
    "semble": ("0.7.0", "semble", ("0.6.1",)),
}
HELD = {"codebase-memory-mcp": "0.11.0", "Headroom": "0.37.0"}
# Shapes of private locators, case-insensitive. The account name and the lane builder's name are held out by the generator's own sanitization and by the repository's host-name scan
# (validate.py --scan-file, whose names live outside the repository); a token spelled here would publish it, so this checks the shapes: home, scratch, run-time and account-scratch paths,
# the private tracker's and receipt notes' file names, the numbered scripts, logs and backup directories of the lane builder's upgrade records, and a command-center message id.
PRIVATE = re.compile(r"/home/\S|/var/tmp/|/tmp/claude-\d|/run/user/\d|tracker\S{0,40}\.md|RECEIPT-[\w-]+\.md|(?<![\w./-])\d{2}-[a-z0-9][\w-]*\.(?:sh|log|py)\b|(?<![\w./-])\d{2}-[a-z]+-backup/|#\d{5}|\bGO #\d", re.I)
HEX = {"sha256": 64, "git-sha1": 40}
EQUAL_HEAD = "omission_notice_levels_equal_levels_over_omitted_lines_only"


def rows():
    return {row["name"]: row for row in json.loads(PROFILE.read_text(encoding="utf-8"))["entries"]}


def records(prefix):
    paths = sorted(RECORDS.glob(prefix + "*.json"))
    assert len(paths) == 1, (prefix, paths)
    return paths[0], json.loads(paths[0].read_text(encoding="utf-8"))


def record(tool):
    return records("currency-%s-2026" % tool)


class CurrencySweepRepin(unittest.TestCase):
    def test_rows_carry_the_verified_pins_and_their_artifacts(self):
        by_name = rows()
        for name, (pin, _tool, _old) in ROWS.items():
            row = by_name[name]
            self.assertEqual(row["pin"], pin, name)
            self.assertIn(pin, row["release"]["tag"], name)
            self.assertIn(pin, row["artifact"]["url"], name)
            algorithm, value = row["checksum"]["algorithm"], row["checksum"]["value"]
            self.assertRegex(value, r"\A[0-9a-f]{%d}\Z" % HEX[algorithm], name)

    def test_the_old_pins_left_the_re_pinned_rows(self):
        by_name = rows()
        for name, (_pin, _tool, old) in ROWS.items():
            row = dict(by_name[name])
            row.pop("blocking_gaps")  # the gaps name the versions the plan's carriers and exec rules still hold
            text = json.dumps(row)
            for value in old:
                self.assertNotIn(value, text, "%s still carries %s" % (name, value))

    def test_the_held_rows_stay_where_the_record_says(self):
        by_name = rows()
        for name, pin in HELD.items():
            self.assertEqual(by_name[name]["pin"], pin, name)

    def test_the_rtk_row_records_the_owed_exec_rule_review(self):
        gaps = " ".join(rows()["RTK"]["blocking_gaps"])
        for needle in ("codex_hook_trust.py", "exec_rules_reviewed.json", "rtk-rewrite-heads"):
            self.assertIn(needle, gaps)

    def test_each_re_pinned_row_says_which_old_pin_the_plan_carriers_still_hold(self):
        by_name = rows()
        for name, (_pin, _tool, old) in ROWS.items():
            gaps = " ".join(by_name[name]["blocking_gaps"])
            self.assertTrue(any(value in gaps for value in old), "%s does not say what the plan's carriers still name" % name)
            self.assertIn("amended in their own change", gaps, name)

    def test_socraticode_installs_without_an_age_buffer_of_ours(self):
        command = rows()["SocratiCode"]["install"]["command"]
        self.assertNotIn("--before", command)
        self.assertIn("socraticode@1.16.1", command)
        handbook = (ROOT / "docs/new-wsl-handbook.md").read_text(encoding="utf-8") + (ROOT / "docs/new-wsl-handbook.json").read_text(encoding="utf-8")
        self.assertNotIn("--before=2026-10-16", handbook)

    def test_the_serena_row_records_the_repl_default_of_a_fresh_install(self):
        gaps = " ".join(rows()["Serena"]["blocking_gaps"])
        for needle in ("agent_interface", "REPL", "serena init", "install.sh:432"):
            self.assertIn(needle, gaps)

    def test_the_headroom_row_names_the_three_pins_and_the_recheck(self):
        row = rows()["Headroom"]
        gaps = " ".join(row["blocking_gaps"])
        for needle in ("0.37.0", "0.40.0", "0.41.0", "W1b", "pins-linux-x86_64.json:319-320", "manifests/stack.json:521-523", "omission count"):
            self.assertIn(needle, gaps)
        path, data = records("currency-headroom-recheck-")
        self.assertIn(RECORDS_REL + path.name, row["evidence_refs"])
        for label in ("0.40.0_scratch_install", "0.41.0_live_install"):
            self.assertEqual(data["rechecks"][label]["criteria_failing"], [EQUAL_HEAD], label)
        self.assertEqual(data["criteria"]["failing_on_both_versions"], [EQUAL_HEAD])
        self.assertEqual({data["rechecks"][k]["headroom_ai_version"] for k in data["rechecks"]}, {"0.40.0", "0.41.0"})

    def test_the_codebase_memory_hold_cites_the_readme_lines_and_rests_on_the_measurement(self):
        row = rows()["codebase-memory-mcp"]
        gaps = " ".join(row["blocking_gaps"])
        for needle in (":155", ":157-159", "target-entry-snapshot"):
            self.assertIn(needle, gaps)
        decision = DECISION.read_text(encoding="utf-8")
        for needle in ("`:155`", "`:157-159`", "target-entry-snapshot"):
            self.assertIn(needle, decision)
        path, data = records("currency-codebase-memory-mcp-native-route-")
        self.assertIn(RECORDS_REL + path.name, row["evidence_refs"])
        scenarios = data["measurement"]["scenarios"]
        refused = scenarios["symlink_layout_running_0_11_0_session"]
        self.assertEqual(refused["install"]["exit"], 1)
        self.assertIn("target-entry-snapshot", refused["install"]["stderr"])
        self.assertFalse(refused["after"]["standin_session"]["exited"], "the refusal must leave the running session untouched")
        drained = scenarios["regular_file_layout_running_0_11_0_session"]
        self.assertEqual(drained["install"]["exit"], 0)
        self.assertTrue(drained["after"]["standin_session"]["exited"])
        self.assertEqual(drained["after"]["version_via_entry"], "codebase-memory-mcp 0.12.1")

    def test_the_claude_hud_pin_agrees_across_the_plan(self):
        template = json.loads((ROOT / "adoption/templates/claude.settings.template.json").read_text(encoding="utf-8"))
        self.assertEqual(template["extraKnownMarketplaces"]["claude-hud"]["source"]["ref"], HUD_TAG)
        client_map = (ROOT / "adoption/new-wsl/client-config-map.json").read_text(encoding="utf-8")
        override = re.search(r'"repo": "jarrodwatts/claude-hud",\s*"ref": "([^"]+)"', client_map)
        self.assertEqual(override.group(1), HUD_TAG)
        bootstrap = (ROOT / "adoption/bootstrap.md").read_text(encoding="utf-8")
        recipe = (ROOT / "recipes/README.md").read_text(encoding="utf-8")
        self.assertIn("claude-hud@%s --scope user" % HUD_TAG, bootstrap)
        self.assertIn("claude-hud@%s --scope user" % HUD_TAG, recipe)
        self.assertIn('"claude-hud@claude-hud": "%s",' % HUD_COMMIT, bootstrap)
        self.assertIn("`claude-hud` · `0.11.3` / `%s`" % HUD_COMMIT, recipe)
        for old_tag in ("v0.10.0", "v0.11.2"):
            self.assertNotIn("claude-hud@%s --scope user\n   claude plugin install" % old_tag, bootstrap)
            self.assertNotIn("claude-hud@%s --scope user`;" % old_tag, recipe)
        for old in HUD_OLD_COMMITS:
            self.assertNotIn('"claude-hud@claude-hud": "%s"' % old, bootstrap)
        for pins in ("adoption/pins-linux-x86_64.json", "adoption/pins-macos-arm64.json"):
            self.assertNotIn("installed from tag v0.10.0 through the settings template and recipe", (ROOT / pins).read_text(encoding="utf-8"), pins)

    def test_the_claude_hud_route_record_shows_the_pin_installed_through_the_tagged_route(self):
        path, data = records("claude-hud-0.11.3-")
        self.assertEqual(data["upstream"]["commit"], HUD_COMMIT)
        self.assertEqual(data["upstream"]["tag"], HUD_TAG)
        self.assertTrue(data["verification"]["installed_gitCommitSha_equals_the_v0_11_3_commit"])
        exits = {step["label"][:2]: step["exit"] for step in data["smoke"]["steps"]}
        for step in ("A1", "A2", "B1", "B2", "B3"):
            self.assertEqual(exits[step], 0, step)
        self.assertNotEqual(exits["B0"], 0, "the refresh of a marketplace that is not on disk fails; the tagged add is the route")
        self.assertIn("settings.json", " ".join(data["live_application_for_the_command_center_not_run_here"]))
        self.assertFalse(data["link"]["changed_by_this_builder"])
        update = json.loads((RECORDS / "claude-hud-0.11.2-20261017T072723Z.json").read_text(encoding="utf-8"))
        self.assertEqual(update["upstream"]["tag"], "v0.11.2")

    def test_each_public_record_names_the_pin_its_row_carries(self):
        for name, (pin, tool, _old) in ROWS.items():
            path, data = record(tool)
            self.assertIn(pin, data["to"], name)
            self.assertIn("public_copy", data, path.name)

    def test_no_public_record_holds_a_private_locator(self):
        files = sorted(RECORDS.glob("*.json"))
        self.assertGreaterEqual(len(files), 13, "the thirteen public receipts are not all there, so there is nothing to scan")
        for path in files:
            text = path.read_text(encoding="utf-8")
            found = PRIVATE.search(text)
            self.assertIsNone(found, "%s holds a private locator: %r" % (path.name, found.group(0) if found else None))
            for key in re.findall(r'"([^"]+)":', text):
                self.assertIsNone(PRIVATE.search(key), "%s has a key that is a private locator: %r" % (path.name, key))

    def test_each_public_record_carries_the_registry_digests_and_the_local_ones_and_its_row_cites_it(self):
        by_name = rows()
        for name, (_pin, tool, _old) in ROWS.items():
            path, data = record(tool)
            block = data["digest_comparison"]
            self.assertIn(RECORDS_REL + path.name, by_name[name]["evidence_refs"], name)
            self.assertTrue(block["all_registry_comparisons_equal"], name)
            compared = [c for c in block["comparisons"] if c["equal"] is not None]
            self.assertTrue(compared, name)
            self.assertTrue(all(c["equal"] is True for c in compared), name)
            self.assertTrue(block["what_was_compared_with_what"], name)
            pinned = by_name[name]["checksum"]
            if pinned["algorithm"] == "sha256":
                self.assertTrue(block["profile_pin"]["equals_local_sha256"], name)
                self.assertIn(pinned["value"], json.dumps(block), "%s: the pinned sha256 has no trace in its receipt" % name)
            if block["registry"].get("npm_publishes_sha256") is False:   # npm: sha512 SRI and sha1 are the registry's own digests
                self.assertEqual(block["registry"]["published_digests"]["integrity_sha512_sri"], pinned.get("integrity"), name)
        _path, jcm = record("jcodemunch-mcp")
        files = jcm["digest_comparison"]["registry"]["files"]
        self.assertEqual({f["packagetype"] for f in files}, {"bdist_wheel", "sdist"})
        for f in files:
            self.assertEqual(f["registry_published_digests"]["sha256"], f["local"]["sha256"], f["filename"])
            self.assertIn(f["local"]["sha256"], DECISION.read_text(encoding="utf-8") if f["packagetype"] == "bdist_wheel" else json.dumps(jcm))

    def test_each_public_record_resolves_its_source_commit(self):
        by_name = rows()
        for name, (_pin, tool, _old) in ROWS.items():
            _path, data = record(tool)
            resolution = data["source_commit_resolution"]
            commit = resolution["git_ls_remote"]["commit"]
            self.assertRegex(commit, r"\A[0-9a-f]{40}\Z", name)
            self.assertEqual(resolution["git_ls_remote"]["exit"], 0, name)
            if tool != "rtk":   # the RTK row cites the release tag in its URLs, the others cite the commit
                self.assertIn(commit, json.dumps(by_name[name]), "%s does not cite the commit its receipt resolved" % name)
            head = resolution.get("npm_gitHead")
            if head and head != commit:
                compared = resolution["compare_gitHead_to_tag_commit"]
                self.assertEqual((compared["status"], compared["behind_by"]), ("ahead", 0), name)
                self.assertNotIn("README.md", compared["files"], "%s: the README the row cites differs between gitHead and the tag commit" % name)

    def test_the_decision_table_matches_the_profile(self):
        text = DECISION.read_text(encoding="utf-8")
        by_name = rows()
        for name, (pin, _tool, _old) in ROWS.items():
            self.assertIn(by_name[name]["checksum"]["value"], text, name)
            self.assertRegex(text, r"\*\*[^|*]*%s[^|*]*\*\*" % re.escape(pin), name)
        self.assertIn(HUD_COMMIT, text)


if __name__ == "__main__":
    unittest.main()
