"""Skills status checker: nonmutating, value-free checks against a fake HOME.

Local integration class: every fixture lives under a per-test temporary directory
standing in for a user's home; the real skills CLI, lock file, and Claude/Codex
homes are never touched. Fixture "hash" fields are always computed with hashlib
from fixture content at test time, never hardcoded literals, so a drift test
mutates content and lets the digest follow rather than embedding a second,
independently-typed expectation.
"""

import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import skills_status as ss

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/skills_status.py"


class SkillsStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {"HOME": str(self.home)}

    # -- fixture builders ---------------------------------------------------

    def write_canonical(self, name: str, content: bytes) -> Path:
        directory = self.home / ".agents" / "skills" / name
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "SKILL.md"
        path.write_bytes(content)
        return path

    def make_skill(self, name, *, claude_listing="on", codex_enabled=True,
                   description_chars=120, content=None) -> dict:
        content = content if content is not None else f"# {name}\n\nBody text for {name}.\n".encode()
        self.write_canonical(name, content)
        return {
            "name": name,
            "tree_sha": hashlib.sha1(f"tree:{name}".encode()).hexdigest(),
            "skill_md_sha256": hashlib.sha256(content).hexdigest(),
            "skill_md_bytes": len(content),
            "description_chars": description_chars,
            "claude_listing": claude_listing,
            "codex_enabled": codex_enabled,
        }

    def build_manifest(self, skills, budget=None, cli_version="1.7.0") -> dict:
        manifest = {"schema_version": 1, "cli": {"version": cli_version}, "skills": list(skills)}
        if budget is not None:
            manifest["budget"] = budget
        return manifest

    def lock_entries_for(self, skills) -> dict:
        return {s["name"]: {"source": "github", "sourceType": "github",
                            "sourceUrl": "https://example.invalid/repo", "skillPath": f"skills/{s['name']}",
                            "skillFolderHash": s["tree_sha"], "installedAt": "2026-09-25T00:00:00Z",
                            "updatedAt": "2026-09-25T00:00:00Z"} for s in skills}

    def write_lock(self, entries: dict, version=3, path: Path | None = None) -> Path:
        lock_path = path or (self.home / ".agents" / ".skill-lock.json")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(json.dumps({"version": version, "skills": entries}))
        return lock_path

    def write_claude_link(self, name: str, kind="relative") -> Path:
        claude_skills = self.home / ".claude" / "skills"
        claude_skills.mkdir(parents=True, exist_ok=True)
        link = claude_skills / name
        canonical = self.home / ".agents" / "skills" / name
        if kind == "relative":
            link.symlink_to(f"../../.agents/skills/{name}", target_is_directory=True)
        elif kind == "absolute":
            link.symlink_to(canonical, target_is_directory=True)
        elif kind == "copy":
            shutil.copytree(canonical, link)
        elif kind == "wrong_target":
            elsewhere = self.home / "elsewhere-skill"
            elsewhere.mkdir(exist_ok=True)
            link.symlink_to(elsewhere, target_is_directory=True)
        else:
            raise ValueError(kind)
        return link

    def write_claude_settings(self, overrides: dict, extra_env_sentinel=None) -> None:
        claude_dir = self.home / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        settings = {"skillOverrides": overrides}
        if extra_env_sentinel is not None:
            settings["env"] = {"SOME_OTHER_SETTING": extra_env_sentinel}
        (claude_dir / "settings.json").write_text(json.dumps(settings))

    def write_codex_config(self, disable_names, extra_sentinel=None, disable_paths=()) -> None:
        """Name-keyed tables for disable_names, then path-keyed tables for disable_paths."""
        self.write_codex_entries([{"name": name, "enabled": False} for name in disable_names]
                                 + [{"path": str(path), "enabled": False} for path in disable_paths],
                                 extra_sentinel=extra_sentinel)

    def write_codex_entries(self, entries, extra_sentinel=None) -> None:
        codex_dir = self.home / ".codex"
        codex_dir.mkdir(parents=True, exist_ok=True)
        lines = []
        for entry in entries:
            lines.append("[[skills.config]]")
            lines += [f"{key} = {json.dumps(value)}" for key, value in entry.items()]  # a JSON string or bool is TOML
            lines.append("")
        if extra_sentinel is not None:
            lines.append(f"# {extra_sentinel}")
        (codex_dir / "config.toml").write_text("\n".join(lines) + "\n")

    def skill_md_path(self, name: str) -> Path:
        """Where skills 1.7.0 installs a global skill's SKILL.md and Codex loads it from ($HOME/.agents/skills)."""
        return self.home / ".agents" / "skills" / name / "SKILL.md"

    def setup_pair(self):
        """Two fully-wired, passing skills: alpha (on/codex-enabled), beta (name-only/codex-disabled)."""
        alpha = self.make_skill("alpha-skill", claude_listing="on", codex_enabled=True)
        beta = self.make_skill("beta-skill", claude_listing="name-only", codex_enabled=False)
        manifest = self.build_manifest([alpha, beta])
        self.write_lock(self.lock_entries_for([alpha, beta]))
        self.write_claude_link("alpha-skill")
        self.write_claude_link("beta-skill")
        self.write_claude_settings({"beta-skill": "name-only"})
        self.write_codex_config(["beta-skill"])
        return manifest, alpha, beta

    # -- CPA-V-07: a skill that a plugin also delivers is listed twice; only the other copy can be hidden ------------------------

    def write_plugin_state(self, plugin_id, *, enabled=True, installed=True, overrides=None, scope="user", shape="list", settings=None):
        """settings.json with skillOverrides and enabledPlugins (and any ``settings`` keys besides), and the user-plugin registry. ``shape`` is how the registry holds the install: a list of installs (schema 2) or one
        object; ``installed="invalid"`` writes a registry that is not JSON. For the plugin of the row that twin_row made, the install is the pinned plugin: its cache holds the row's SKILL.md at the row's commit (a
        replacement plugin is accepted only so; break it with ``break_plugin``)."""
        claude_dir = self.home / ".claude"
        (claude_dir / "plugins").mkdir(parents=True, exist_ok=True)
        (claude_dir / "settings.json").write_text(json.dumps({"skillOverrides": overrides or {}, "enabledPlugins": {plugin_id: enabled}, **(settings or {})}))
        install = {"scope": scope, "installPath": "x", "gitCommitSha": "a" * 40}
        skill = getattr(self, "twin_skill", None)
        if skill is not None and skill.get("claude_plugin") == plugin_id and installed is True:
            root = claude_dir / "plugins/cache/market" / plugin_id.split("@")[0] / "pinned"
            (root / skill["path"]).mkdir(parents=True, exist_ok=True)
            source = next(path for path in (self.home / ".agents/skills" / skill["name"] / "SKILL.md", self.home / ".claude/skills" / skill["name"] / "SKILL.md") if path.is_file())
            shutil.copy(source, root / skill["path"] / "SKILL.md")
            install = {"scope": scope, "installPath": str(root), "gitCommitSha": skill["ref"], "installedAt": "2026-10-10T00:00:00Z"}
        registry = {"version": 2, "plugins": {plugin_id: [install] if shape == "list" else install} if installed is True else {}}
        text = "{not json" if installed == "invalid" else json.dumps(registry)
        (claude_dir / "plugins" / "installed_plugins.json").write_text(text)

    def twin_row(self, name="twin-skill", plugin="twin@market"):
        skill = self.make_skill(name)
        skill.update(claude_plugin=plugin, claude_skill_name=f"{plugin.split('@')[0]}:{name}", ref="a" * 40, path=f"skills/{name}")
        self.twin_skill = skill
        self.write_lock(self.lock_entries_for([skill]))
        self.write_claude_link(name)
        self.write_codex_config([])
        return skill

    def break_plugin(self, how):
        """Make the installed plugin of twin_row something other than the pinned one: another commit, a folder outside the plugin cache, a SKILL.md that is not the pinned bytes, or no SKILL.md at all."""
        registry_path = self.home / ".claude/plugins/installed_plugins.json"
        registry = json.loads(registry_path.read_text())
        install = registry["plugins"][self.twin_skill["claude_plugin"]][0]
        skill_md = Path(install["installPath"]) / self.twin_skill["path"] / "SKILL.md"
        if how == "pin":
            install["gitCommitSha"] = "b" * 40
        elif how == "outside":
            outside = self.tmp / "elsewhere-plugin"
            (outside / self.twin_skill["path"]).mkdir(parents=True, exist_ok=True)
            shutil.copy(skill_md, outside / self.twin_skill["path"] / "SKILL.md")
            install["installPath"] = str(outside)
        elif how == "bytes":
            skill_md.write_bytes(skill_md.read_bytes() + b"changed\n")
        elif how == "gone":
            skill_md.unlink()
        else:
            raise ValueError(how)
        registry_path.write_text(json.dumps(registry))

    def test_a_plugin_that_is_installed_and_enabled_makes_the_personal_copy_a_duplicate_until_it_is_hidden(self):
        skill = self.twin_row()
        manifest = self.build_manifest([skill])
        self.write_plugin_state("twin@market")
        entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
        self.assertEqual(entry["claude_twin"], {"state": "duplicate_listing", "twin": "twin-skill", "plugin_present": True})
        self.assertEqual(entry["claude_listing"], {"state": "mismatch", "actual": "on"}, "where the plugin is present the other copy is expected hidden")
        self.assertFalse(entry["pass"])
        self.write_plugin_state("twin@market", overrides={"twin-skill": "off"})
        report = ss.inspect(manifest, self.home, self.env)
        entry = report["skills"][0]
        self.assertEqual(entry["claude_twin"]["state"], "ok")
        self.assertEqual(entry["claude_listing"], {"state": "ok", "actual": "off"})
        self.assertTrue(entry["pass"])
        self.assertEqual(report["result"], "ok")

    def test_without_the_plugin_the_personal_copy_keeps_the_manifest_listing_so_a_fresh_host_keeps_its_one_copy(self):
        skill = self.twin_row()
        manifest = self.build_manifest([skill])
        for label, state in (("not enabled", dict(enabled=False)), ("not installed", dict(installed=False)), ("neither", dict(enabled=False, installed=False))):
            with self.subTest(plugin=label):
                self.write_plugin_state("twin@market", **state)
                entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
                self.assertEqual(entry["claude_twin"], {"state": "ok", "twin": "twin-skill", "plugin_present": False})
                self.assertTrue(entry["pass"])
                self.write_plugin_state("twin@market", overrides={"twin-skill": "off"}, **state)  # hiding the only copy is wrong where there is no plugin
                entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
                self.assertEqual(entry["claude_listing"], {"state": "mismatch", "actual": "off"})
                self.assertFalse(entry["pass"])

    def test_overrides_of_the_wrong_type_hide_nothing_so_the_twin_stays_a_duplicate(self):
        skill = self.twin_row()
        self.write_plugin_state("twin@market")
        settings = json.loads((self.home / ".claude/settings.json").read_text())
        settings["skillOverrides"] = ["twin-skill"]  # not a mapping: nothing is hidden by it
        (self.home / ".claude/settings.json").write_text(json.dumps(settings))
        entry = ss.inspect(self.build_manifest([skill]), self.home, self.env)["skills"][0]
        self.assertEqual(entry["claude_twin"]["state"], "duplicate_listing")
        self.assertFalse(entry["pass"])

    def test_only_an_explicit_true_enables_a_plugin_and_only_a_user_install_counts(self):
        """settings reference, enabledPlugins: a Boolean per plugin; an install of another scope serves another project, and an unreadable registry is no install."""
        skill = self.twin_row()
        manifest = self.build_manifest([skill])
        cases = (("a string", dict(enabled="true"), False), ("a number", dict(enabled=1), False), ("a list", dict(enabled=["x"]), False), ("false", dict(enabled=False), False),
                 ("a project-scope install", dict(scope="project"), False), ("a local-scope install", dict(scope="local"), False), ("an unreadable registry", dict(installed="invalid"), False),
                 ("a user install written as one object", dict(shape="object"), True), ("a user install in a list", dict(), True))
        for label, state, present in cases:
            with self.subTest(case=label):
                self.write_plugin_state("twin@market", **state)
                entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
                self.assertEqual(entry["claude_twin"]["plugin_present"], present)
                self.assertEqual(entry["claude_twin"]["state"], "duplicate_listing" if present else "ok")

    def test_only_off_hides_the_twin(self):
        skill = self.twin_row()
        manifest = self.build_manifest([skill])
        for value in ("on", "name-only", "user-invocable-only", "off"):
            with self.subTest(override=value):
                self.write_plugin_state("twin@market", overrides={"twin-skill": value})
                entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
                self.assertEqual(entry["claude_twin"]["state"], "ok" if value == "off" else "duplicate_listing")

    def test_a_native_plugin_row_without_a_bundled_twin_has_no_twin_entry(self):
        skill = {k: v for k, v in self.native_twin_row(hidden=False).items() if k != "bundled_twin"}
        entry = ss.inspect(self.build_manifest([skill]), self.home, self.env)["skills"][0]
        self.assertNotIn("claude_twin", entry)
        self.assertTrue(entry["pass"])

    def test_a_bundled_twin_is_hidden_under_its_own_name(self):
        """The row's name and the bundled skill's name need not be the same word; the override that hides the bundled copy is keyed by the bundled name."""
        skill = {**self.native_twin_row(hidden=False), "bundled_twin": "claude-api-bundled"}
        entry = ss.inspect(self.build_manifest([skill]), self.home, self.env)["skills"][0]
        self.assertEqual(entry["claude_twin"], {"state": "duplicate_listing", "twin": "claude-api-bundled", "plugin_present": True})
        self.write_plugin_state("claude-api@market", overrides={"claude-api-bundled": "off"})
        registry = json.loads((self.home / ".claude/plugins/installed_plugins.json").read_text())
        registry["plugins"]["claude-api@market"][0]["installPath"] = str(self.home / ".claude/plugins/cache/market/claude-api/pinned")
        (self.home / ".claude/plugins/installed_plugins.json").write_text(json.dumps(registry))
        entry = ss.inspect(self.build_manifest([skill]), self.home, self.env)["skills"][0]
        self.assertEqual(entry["claude_twin"]["state"], "ok")

    def test_a_plugin_row_that_is_not_as_pinned_fails_even_with_its_twin_hidden(self):
        skill = self.native_twin_row(hidden=True)
        skill["skill_md_sha256"] = "0" * 64  # the installed plugin's SKILL.md is not the pinned one
        entry = ss.inspect(self.build_manifest([skill]), self.home, self.env)["skills"][0]
        self.assertEqual(entry["claude_twin"], {"state": "plugin_invalid", "twin": "claude-api", "plugin_present": True, "plugin": "hash_mismatch"}, "the twin is hidden, and the plugin that remains is not the pinned one")
        self.assertNotEqual(entry["canonical"]["state"], "ok")
        self.assertFalse(entry["pass"])

    def test_an_unreadable_settings_file_lists_no_plugin_and_the_personal_row_fails_on_its_own_listing_check(self):
        skill = self.twin_row()
        self.write_plugin_state("twin@market", overrides={"twin-skill": "off"})
        (self.home / ".claude/settings.json").write_text("{not json")
        entry = ss.inspect(self.build_manifest([skill]), self.home, self.env)["skills"][0]
        self.assertEqual(entry["claude_twin"], {"state": "ok", "twin": "twin-skill", "plugin_present": False})
        self.assertEqual(entry["claude_listing"]["state"], "settings_unreadable")
        self.assertFalse(entry["pass"])

    def test_a_row_without_a_twin_has_no_twin_entry_and_the_text_shows_it_only_for_a_twin(self):
        manifest, alpha, beta = self.setup_pair()
        report = ss.inspect(manifest, self.home, self.env)
        self.assertTrue(all("claude_twin" not in entry for entry in report["skills"]))
        self.assertNotIn("twin=", ss.render_text(report))
        skill = self.twin_row()
        self.write_plugin_state("twin@market", overrides={"twin-skill": "off"})
        text = ss.render_text(ss.inspect(self.build_manifest([skill]), self.home, self.env))
        self.assertIn("twin=ok", text)

    def native_twin_row(self, *, hidden):
        """The claude-api shape: a native plugin row whose bundled twin is listed under the bare name."""
        config = self.home / ".claude"
        root = config / "plugins/cache/market/claude-api/pinned"
        (root / "skills/claude-api").mkdir(parents=True)
        raw = b"---\nname: claude-api\ndescription: fixture\n---\n"
        (root / "skills/claude-api/SKILL.md").write_bytes(raw)
        skill = {"name": "claude-api", "native_plugin": "claude-api@market", "claude_skill_name": "claude-api:claude-api", "bundled_twin": "claude-api", "path": "skills/claude-api",
                 "ref": "a" * 40, "skill_md_sha256": hashlib.sha256(raw).hexdigest(), "tree_sha": "b" * 40, "skill_md_bytes": len(raw), "description_chars": 10,
                 "claude_listing": "on", "codex_enabled": False}
        self.write_plugin_state("claude-api@market", overrides={"claude-api": "off"} if hidden else {})
        registry = {"version": 2, "plugins": {"claude-api@market": [{"scope": "user", "installPath": str(root), "gitCommitSha": "a" * 40, "installedAt": "2026-10-10T00:00:00Z"}]}}
        (config / "plugins/installed_plugins.json").write_text(json.dumps(registry))
        return skill

    def test_the_bundled_twin_of_a_native_plugin_row_must_be_hidden_where_the_plugin_is_enabled(self):
        for hidden, state, ok in ((False, "duplicate_listing", False), (True, "ok", True)):
            with self.subTest(hidden=hidden):
                skill = self.native_twin_row(hidden=hidden)
                entry = ss.inspect(self.build_manifest([skill]), self.home, self.env)["skills"][0]
                self.assertEqual(entry["canonical"]["state"], "ok", "the plugin itself is as pinned")
                self.assertEqual(entry["claude_twin"], {"state": state, "twin": "claude-api", "plugin_present": True})
                self.assertEqual(entry["pass"], ok)
                shutil.rmtree(self.home / ".claude")

    # -- review of #1074 at 2dae9751 (Astra's read and the local codex review) -------------------------------------------------

    def change_settings(self, **changes):
        path = self.home / ".claude/settings.json"
        data = json.loads(path.read_text())
        data.update(changes)
        path.write_text(json.dumps(data))

    def test_a_bundled_twin_is_hidden_by_disabling_bundled_skills_as_a_whole(self):
        """Astra's read (P1): disableBundledSkills hides every bundled skill and keeps the plugin's copy listed (measured on 2.1.296, receipts/global-disable-init-records.json: 77 skills listed, 61 with it, the bundled
        claude-api gone and claude-api:claude-api kept), so a host that disables them has one copy of the skill and was reported as a duplicate. Only the JSON boolean true counts."""
        manifest = self.build_manifest([self.native_twin_row(hidden=False)])
        for label, value, hidden in (("true", True, True), ("false", False, False), ("the string true", "true", False), ("the number 1", 1, False), ("null", None, False)):
            with self.subTest(disableBundledSkills=label):
                self.change_settings(disableBundledSkills=value)
                entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
                self.assertEqual(entry["claude_twin"], {"state": "ok" if hidden else "duplicate_listing", "twin": "claude-api", "plugin_present": True})
                self.assertEqual(entry["pass"], hidden)

    def test_a_bundled_twin_is_hidden_by_the_environment_equivalent_of_that_setting(self):
        """The variable reads as set for 1, true, TRUE, yes, on and a padded " 1", and for no other value (measured on 2.1.296: 0, 2, false, off, no, y, t, enabled and an empty value list 77 skills)."""
        manifest = self.build_manifest([self.native_twin_row(hidden=False)])
        for value, hidden in (("1", True), ("true", True), ("TRUE", True), ("yes", True), ("on", True), (" 1", True), ("0", False), ("2", False), ("", False), ("false", False), ("off", False), ("no", False), ("y", False)):
            with self.subTest(value=value):
                env = {**self.env, "CLAUDE_CODE_DISABLE_BUNDLED_SKILLS": value}
                self.assertEqual(ss.inspect(manifest, self.home, env)["skills"][0]["claude_twin"]["state"], "ok" if hidden else "duplicate_listing")
        self.assertEqual(ss.inspect(manifest, self.home, self.env)["skills"][0]["claude_twin"]["state"], "duplicate_listing", "without the variable")

    def test_the_env_entry_of_settings_overrides_the_environment_and_may_be_a_number_or_a_boolean(self):
        """Measured on 2.1.296: an env entry of settings.json becomes the client's environment (the string 1 or true, the number 1, the boolean true), and it overrides the process environment in both directions (1 in
        the environment and 0 in the entry: not disabled; 0 and 1: disabled)."""
        manifest = self.build_manifest([self.native_twin_row(hidden=False)])
        name = "CLAUDE_CODE_DISABLE_BUNDLED_SKILLS"
        for label, entry_value, process_value, hidden in (("the string 1", "1", None, True), ("the number 1", 1, None, True), ("the boolean true", True, None, True), ("the string 0", "0", None, False),
                                                          ("the boolean false", False, None, False), ("0 in the entry beats 1 in the environment", "0", "1", False),
                                                          ("1 in the entry beats 0 in the environment", "1", "0", True)):
            with self.subTest(case=label):
                self.change_settings(env={name: entry_value})
                env = {**self.env, **({name: process_value} if process_value is not None else {})}
                self.assertEqual(ss.inspect(manifest, self.home, env)["skills"][0]["claude_twin"]["state"], "ok" if hidden else "duplicate_listing")
        self.change_settings(env={"SOME_OTHER_SETTING": "x"})
        self.assertEqual(ss.inspect(manifest, self.home, {**self.env, name: "1"})["skills"][0]["claude_twin"]["state"], "ok", "an env entry for another variable leaves the environment's")

    def test_a_number_or_an_array_in_an_env_entry_is_the_text_javascript_makes_of_it(self):
        """The local review of the rebased head (P2-1, `skills_status.py` env_text): the client reads a settings env value as JavaScript's String() of it, so 1.0 and 1e0 are 1 and an array is its elements joined
        by commas. Measured on 2.1.296 (receipts/numeric-env-init-records.json, 28 init-record runs): 61 skills listed, the bundled claude-api gone, with 1, 1.0, 1e0, 10e-1, 0.1e1, 1E0, 1.00, true, "1", [1], ["1"],
        [true] and [[1]]; 77 with 0, 0.0, 2, 1.5, -0, null, [], an object, [1, 2], ["1", "x"], [null], [null, 1] and [1, true]; the skill's own switch reads 1.0 and 1e0 the same way."""
        manifest = self.build_manifest([self.native_twin_row(hidden=False)])
        settings = self.home / ".claude/settings.json"
        base = json.loads(settings.read_text())
        name = "CLAUDE_CODE_DISABLE_BUNDLED_SKILLS"
        for raw, hidden in (("1", True), ("1.0", True), ("1e0", True), ("10e-1", True), ("0.1e1", True), ("1E0", True), ("1.00", True), ("true", True), ('"1"', True), ("[1]", True), ('["1"]', True),
                            ("[true]", True), ("[[1]]", True), ("0", False), ("0.0", False), ("2", False), ("1.5", False), ("-0", False), ("null", False), ("[]", False), ('{"a": 1}', False), ('"0"', False),
                            ("[1, 2]", False), ('["1", "x"]', False), ("[null]", False), ("[null, 1]", False), ("[1, true]", False)):
            with self.subTest(env_value=raw):
                settings.write_text(json.dumps({**base, "env": {name: "@@RAW@@"}}).replace('"@@RAW@@"', raw))
                self.assertEqual(ss.bundled_skills_disabled(settings, self.env), hidden)
                self.assertEqual(ss.inspect(manifest, self.home, self.env)["skills"][0]["claude_twin"]["state"], "ok" if hidden else "duplicate_listing")
        skill_switch = "CLAUDE_CODE_DISABLE_CLAUDE_API_SKILL"
        for raw in ("1.0", "1e0", "[1]"):
            with self.subTest(skill_switch=raw):
                settings.write_text(json.dumps({**base, "env": {skill_switch: "@@RAW@@"}}).replace('"@@RAW@@"', raw))
                self.assertTrue(ss.bundled_skill_disabled(settings, self.env, "claude-api"))
                self.assertFalse(ss.bundled_skills_disabled(settings, self.env), "the skill's own switch hides that skill only")
        deep = []
        for _ in range(5000):
            deep = [deep]
        self.assertFalse(ss.env_switch({name: deep}, {}, name), "an array nested beyond the interpreter's depth is no switch and no crash")

    def test_a_missing_settings_file_is_empty_settings_and_the_environment_switch_still_counts(self):
        """The local review of the rebased head (P2-2, `skills_status.py` read_switches): with no settings.json the client starts with empty settings and reads its environment, so
        CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1 still hides the bundled copy; the plugin is not enabled either (no settings), so no route lists the skill and the row fails. A file that exists and cannot be read
        still disables nothing."""
        manifest = self.build_manifest([self.native_twin_row(hidden=False)])
        settings = self.home / ".claude/settings.json"
        settings.unlink()
        switched = {**self.env, "CLAUDE_CODE_DISABLE_BUNDLED_SKILLS": "1"}
        self.assertTrue(ss.bundled_skills_disabled(settings, switched))
        self.assertTrue(ss.bundled_skill_disabled(settings, {**self.env, "CLAUDE_CODE_DISABLE_CLAUDE_API_SKILL": "1"}, "claude-api"))
        self.assertFalse(ss.bundled_skills_disabled(settings, self.env), "no file and no variable: nothing is hidden")
        entry = ss.inspect(manifest, self.home, switched)["skills"][0]
        self.assertEqual(entry["claude_twin"]["state"], "not_listed", "the bundled copy is hidden by the environment and no plugin is enabled: no route lists the skill")
        self.assertFalse(entry["pass"])
        self.assertEqual(ss.inspect(manifest, self.home, self.env)["skills"][0]["claude_twin"]["state"], "ok", "without the variable the bundled copy is the one listed")
        settings.write_text("{not json")
        self.assertFalse(ss.bundled_skills_disabled(settings, switched), "a file that exists and cannot be read disables nothing")

    def test_disabling_bundled_skills_hides_no_personal_copy_and_an_unreadable_settings_file_disables_nothing(self):
        """The personal twin is not a bundled skill: it stays listed, so it stays a duplicate until skillOverrides hides it. Settings that cannot be read disable nothing (the personal row then fails on its listing)."""
        skill = self.twin_row()
        manifest = self.build_manifest([skill])
        self.write_plugin_state("twin@market", settings={"disableBundledSkills": True})
        env = {**self.env, "CLAUDE_CODE_DISABLE_BUNDLED_SKILLS": "1"}
        entry = ss.inspect(manifest, self.home, env)["skills"][0]
        self.assertEqual(entry["claude_twin"], {"state": "duplicate_listing", "twin": "twin-skill", "plugin_present": True})
        self.assertFalse(entry["pass"])
        self.write_plugin_state("twin@market", overrides={"twin-skill": "off"}, settings={"disableBundledSkills": True})
        self.assertTrue(ss.inspect(manifest, self.home, env)["skills"][0]["pass"])
        bundled = self.build_manifest([self.native_twin_row(hidden=False)])
        (self.home / ".claude/settings.json").write_text("{not json")
        self.assertFalse(ss.bundled_skills_disabled(self.home / ".claude/settings.json", env))
        self.assertEqual(ss.inspect(bundled, self.home, env)["skills"][0]["claude_twin"]["plugin_present"], False)

    def test_the_skill_specific_switch_hides_the_bundled_twin_and_only_that_twin(self):
        """The local codex review of f7e0cd70 (P2): the client disables its bundled claude-api through `registerClaudeApiSkill({disabled: env.CLAUDE_CODE_DISABLE_CLAUDE_API_SKILL === true})` (the installed 2.1.296
        binary; receipts/skill-switch-init-records.json: 77 skills, 76 with the switch, the bundled copy gone and the plugin's kept), so a host that sets it has one copy and was reported as a duplicate. The
        variable reads as the all-bundled one does (1, true, yes, on in any case, padded or not; not 0, 2, false or empty), the settings env entry overrides the process environment either way, and a bundled
        twin of another name has no such switch."""
        manifest = self.build_manifest([self.native_twin_row(hidden=False)])
        name = "CLAUDE_CODE_DISABLE_CLAUDE_API_SKILL"
        for value, hidden in (("1", True), ("true", True), ("TRUE", True), ("yes", True), ("on", True), (" 1", True), ("0", False), ("2", False), ("", False), ("false", False)):
            with self.subTest(process_environment=value):
                env = {**self.env, name: value}
                self.assertEqual(ss.inspect(manifest, self.home, env)["skills"][0]["claude_twin"]["state"], "ok" if hidden else "duplicate_listing")
        for label, entry, process, hidden in (("the string 1", "1", None, True), ("the number 1", 1, None, True), ("the boolean true", True, None, True), ("0 in the entry beats 1 in the environment", "0", "1", False),
                                              ("1 in the entry beats 0 in the environment", "1", "0", True)):
            with self.subTest(settings_env=label):
                self.change_settings(env={name: entry})
                env = {**self.env, **({name: process} if process is not None else {})}
                self.assertEqual(ss.inspect(manifest, self.home, env)["skills"][0]["claude_twin"]["state"], "ok" if hidden else "duplicate_listing")
        self.change_settings(env={})
        other = {**manifest["skills"][0], "bundled_twin": "claude-api-bundled"}
        entry = ss.inspect(self.build_manifest([other]), self.home, {**self.env, name: "1"})["skills"][0]
        self.assertEqual(entry["claude_twin"]["state"], "duplicate_listing", "the switch is the client's for its claude-api, not for any bundled name")
        # the switch of one skill hides no personal twin either
        personal = self.twin_row()
        self.write_plugin_state("twin@market")
        entry = ss.inspect(self.build_manifest([personal]), self.home, {**self.env, name: "1"})["skills"][0]
        self.assertEqual(entry["claude_twin"]["state"], "duplicate_listing")

    def test_a_bundled_twin_that_no_route_lists_is_not_listed_and_fails_the_row(self):
        """Astra's read of 48e083e8 (P2, adjacent) and the same case through the switches: with the plugin disabled and the bundled twin hidden (skillOverrides, the all-bundled switch or the skill's own) the
        skill is listed by no route, and the row passed. A disabled plugin with the bundled copy visible is one copy and is fine; the personal twin's listing is the manifest's own check."""
        name = "CLAUDE_CODE_DISABLE_CLAUDE_API_SKILL"
        skill = self.native_twin_row(hidden=True)
        manifest = self.build_manifest([skill])
        registry_path = self.home / ".claude/plugins/installed_plugins.json"
        registry = registry_path.read_text()   # the pinned install that native_twin_row wrote

        def settings(*, enabled, overrides=None, extra=None, registered=True):
            (self.home / ".claude/settings.json").write_text(json.dumps({"skillOverrides": overrides or {}, "enabledPlugins": {"claude-api@market": enabled}, **(extra or {})}))
            registry_path.write_text(registry if registered else json.dumps({"version": 2, "plugins": {}}))
        for label, overrides, extra, env_extra in (("skillOverrides off", {"claude-api": "off"}, {}, {}), ("disableBundledSkills", {}, {"disableBundledSkills": True}, {}),
                                                   ("the skill's own switch", {}, {}, {name: "1"}), ("the all-bundled variable", {}, {}, {"CLAUDE_CODE_DISABLE_BUNDLED_SKILLS": "1"})):
            with self.subTest(hidden_by=label):
                settings(enabled=False, overrides=overrides, extra=extra)
                env = {**self.env, **env_extra}
                entry = ss.inspect(manifest, self.home, env)["skills"][0]
                self.assertEqual(entry["canonical"]["state"], "ok", "the plugin itself is installed as pinned")
                self.assertEqual(entry["claude_twin"], {"state": "not_listed", "twin": "claude-api", "plugin_present": False})
                self.assertFalse(entry["pass"])
                self.assertIn("twin=not_listed", ss.render_text(ss.inspect(manifest, self.home, env)))
        with self.subTest(case="a plugin that is enabled and not registered"):
            settings(enabled=True, overrides={"claude-api": "off"}, registered=False)
            entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
            self.assertEqual(entry["claude_twin"]["state"], "not_listed")
            self.assertFalse(entry["pass"])
        with self.subTest(case="a disabled plugin with the bundled copy visible"):
            settings(enabled=False)
            entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
            self.assertEqual(entry["claude_twin"], {"state": "ok", "twin": "claude-api", "plugin_present": False})
            self.assertTrue(entry["pass"], "one copy, the client's own")
        with self.subTest(case="an enabled plugin with the twin hidden"):
            settings(enabled=True, overrides={"claude-api": "off"})
            entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
            self.assertEqual((entry["claude_twin"]["state"], entry["pass"]), ("ok", True))
        with self.subTest(case="an enabled plugin with the twin hidden by the skill's own switch"):
            settings(enabled=True)
            entry = ss.inspect(manifest, self.home, {**self.env, name: "1"})["skills"][0]
            self.assertEqual((entry["claude_twin"]["state"], entry["pass"]), ("ok", True))

    def test_a_replacement_plugin_that_is_not_the_pinned_one_is_not_accepted_for_a_hidden_copy(self):
        """The local codex review (P2): a registry row with scope user was enough, even at another commit or with its cached skill gone, so the personal copy hidden behind such a plugin passed although nothing
        pinned was listed. The client lists the plugin all the same, so the twin check reports it (plugin_invalid), whether or not the other copy is hidden."""
        skill = self.twin_row()
        manifest = self.build_manifest([skill])
        for how, expected in (("pin", "pin_mismatch"), ("outside", "invalid_install_path"), ("bytes", "hash_mismatch"), ("gone", "cache_unreadable")):
            for hidden in (True, False):
                with self.subTest(plugin=how, personal_copy_hidden=hidden):
                    self.write_plugin_state("twin@market", overrides={"twin-skill": "off"} if hidden else {})
                    self.break_plugin(how)
                    entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
                    self.assertEqual(entry["claude_twin"], {"state": "plugin_invalid", "twin": "twin-skill", "plugin_present": True, "plugin": expected})
                    self.assertFalse(entry["pass"])
        self.write_plugin_state("twin@market", overrides={"twin-skill": "off"})
        entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
        self.assertEqual((entry["claude_twin"]["state"], entry["pass"]), ("ok", True), "the pinned plugin is accepted")
        self.write_plugin_state("twin@market", enabled=False)
        self.break_plugin("pin")
        self.assertEqual(ss.inspect(manifest, self.home, self.env)["skills"][0]["claude_twin"]["state"], "ok", "a plugin that is not enabled is not listed, so its state does not matter")

    def test_a_native_plugin_row_that_is_not_as_pinned_reports_its_twin_as_invalid_too(self):
        skill = self.native_twin_row(hidden=True)
        skill["ref"] = "c" * 40
        entry = ss.inspect(self.build_manifest([skill]), self.home, self.env)["skills"][0]
        self.assertEqual(entry["canonical"]["state"], "pin_mismatch")
        self.assertEqual(entry["claude_twin"], {"state": "plugin_invalid", "twin": "claude-api", "plugin_present": True, "plugin": "pin_mismatch"})
        self.assertFalse(entry["pass"])

    def test_a_registry_of_the_wrong_shape_is_no_plugin_rather_than_a_crash(self):
        skill = self.twin_row()
        self.write_plugin_state("twin@market", overrides={"twin-skill": "off"})
        (self.home / ".claude/plugins/installed_plugins.json").write_text("[]")
        entry = ss.inspect(self.build_manifest([skill]), self.home, self.env)["skills"][0]
        self.assertEqual(entry["claude_twin"], {"state": "ok", "twin": "twin-skill", "plugin_present": False})

    def test_the_plugin_registry_is_read_from_the_folder_of_the_settings_that_enable_the_plugin(self):
        """The local codex review (P2): the settings are read under CLAUDE_CONFIG_DIR as the client reads them (not trimmed, a blank value counts: its resolution is the working directory), the plugin registry was read
        under the skills CLI's trimmed folder, so a padded or blank value sent the two to different folders and an enabled plugin looked absent. CLAUDE_CONFIG_DIR moves "all settings, session history, and plugins"
        (code.claude.com/docs/en/env-vars, fetched 2026-10-13)."""
        skill = self.twin_row()
        manifest = self.build_manifest([skill])
        installed = self.home / ".claude"
        self.write_plugin_state("twin@market", overrides={"twin-skill": "off"})
        registry = installed / "plugins/installed_plugins.json"
        padded = self.tmp / "padded "
        shutil.copytree(installed, padded, symlinks=True)
        rewritten = registry.read_text().replace(str(installed), str(padded))
        (padded / "plugins/installed_plugins.json").write_text(rewritten)
        shutil.rmtree(installed / "plugins")  # the home's own folder holds no registry: only the folder the variable names does
        entry = ss.inspect(manifest, self.home, {**self.env, "CLAUDE_CONFIG_DIR": str(padded)})["skills"][0]
        self.assertEqual(entry["claude_twin"], {"state": "ok", "twin": "twin-skill", "plugin_present": True}, "a trailing blank belongs to the name, as the client reads it")
        cwd = self.tmp / "cwd"
        shutil.copytree(padded, cwd, symlinks=True)
        (cwd / "plugins/installed_plugins.json").write_text(rewritten.replace(str(padded), str(cwd)))
        with contextlib.chdir(cwd):
            entry = ss.inspect(manifest, self.home, {**self.env, "CLAUDE_CONFIG_DIR": ""})["skills"][0]
        self.assertTrue(entry["claude_twin"]["plugin_present"], "a blank value is the working directory, for the settings and for the plugins alike")

    def test_the_native_plugin_status_reads_the_registry_of_the_folder_the_client_uses(self):
        """The same root for the native plugin rows: a padded CLAUDE_CONFIG_DIR names a folder of its own, the one holding both the settings and the registry."""
        skill = self.native_twin_row(hidden=True)
        padded = self.tmp / "padded "
        (self.home / ".claude").rename(padded)
        registry = padded / "plugins/installed_plugins.json"
        registry.write_text(registry.read_text().replace(str(self.home / ".claude"), str(padded)))
        env = {**self.env, "CLAUDE_CONFIG_DIR": str(padded)}
        self.assertEqual(ss.native_plugin_status(skill, self.home, env)["state"], "ok")
        entry = ss.inspect(self.build_manifest([skill]), self.home, env)["skills"][0]
        self.assertEqual((entry["canonical"]["state"], entry["claude_twin"]["state"], entry["pass"]), ("ok", "ok", True))

    def test_a_claude_only_copied_skill_gets_the_twin_policy_too(self):
        """The local codex review (P2): a row with copy and claude_plugin took the copied-skill branch, which never computed the twin, so with the plugin installed and enabled a copy left on passed with duplicate
        listings and a copy hidden failed as a mismatch."""
        skill = self.twin_row()
        skill.update(copy=True, agents=["claude-code"], codex_enabled=False)
        (self.home / ".claude/skills/twin-skill").unlink()
        shutil.copytree(self.home / ".agents/skills/twin-skill", self.home / ".claude/skills/twin-skill")
        shutil.rmtree(self.home / ".agents/skills/twin-skill")
        manifest = self.build_manifest([skill])
        self.write_plugin_state("twin@market")
        entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
        self.assertEqual(entry["scope"], "claude-code copy")
        self.assertEqual(entry["claude_twin"], {"state": "duplicate_listing", "twin": "twin-skill", "plugin_present": True})
        self.assertFalse(entry["pass"], "left on, beside the plugin's copy")
        self.write_plugin_state("twin@market", overrides={"twin-skill": "off"})
        entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
        self.assertEqual((entry["claude_twin"]["state"], entry["claude_listing"], entry["pass"]), ("ok", {"state": "ok", "actual": "off"}, True))
        self.write_plugin_state("twin@market", enabled=False, overrides={"twin-skill": "off"})
        entry = ss.inspect(manifest, self.home, self.env)["skills"][0]
        self.assertEqual((entry["claude_twin"]["plugin_present"], entry["claude_listing"]["state"], entry["pass"]), (False, "mismatch", False), "hiding the only copy is wrong where there is no plugin")

    def test_the_manifest_loader_checks_the_plugin_fields(self):
        base = self.make_skill("loader-skill")
        cases = {
            "a plugin id without a marketplace": dict(claude_plugin="twin", claude_skill_name="twin:loader-skill"),
            "a listing name that is not <plugin>:<skill>": dict(claude_plugin="twin@market", claude_skill_name="loader-skill"),
            "a listing name of another plugin": dict(claude_plugin="twin@market", claude_skill_name="other:loader-skill"),
            "a copy and a plugin row at once": dict(claude_plugin="twin@market", native_plugin="twin@market", claude_skill_name="twin:loader-skill"),
            "a bundled twin on a row that is not a plugin row": dict(bundled_twin="loader-skill"),
            "a bundled twin that is not a name": dict(native_plugin="twin@market", claude_skill_name="twin:loader-skill", bundled_twin="not a name"),
        }
        path = self.tmp / "manifest.json"
        for label, extra in cases.items():
            with self.subTest(case=label):
                path.write_text(json.dumps(self.build_manifest([{**base, **extra}])))
                with self.assertRaises(ss.ManifestError):
                    ss.load_manifest(path)
        good = {**base, "claude_plugin": "twin@market", "claude_skill_name": "twin:loader-skill"}
        path.write_text(json.dumps(self.build_manifest([good])))
        self.assertEqual(ss.load_manifest(path)["skills"][0]["claude_plugin"], "twin@market")

    def make_fake_bin(self, version_output: str, exit_code=0) -> Path:
        script = self.tmp / "fake-skills-bin"
        script.write_text(f"#!/bin/sh\necho '{version_output}'\nexit {exit_code}\n")
        script.chmod(0o755)
        return script

    # -- call helpers ---------------------------------------------------------

    def report(self, manifest, env=None, skills_bin=None) -> dict:
        return ss.inspect(manifest, self.home, env if env is not None else self.env, skills_bin=skills_bin)

    def skill_result(self, report, name: str) -> dict:
        return next(s for s in report["skills"] if s["name"] == name)

    def run_cli(self, manifest, *extra_args, env=None, home_args=None):
        """home_args replaces ["--home", <fixture home>]; [] leaves --home at its default, Path.home()."""
        manifest_path = self.tmp / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        cli_env = {"PATH": os.environ.get("PATH", ""), **(env if env is not None else self.env)}
        home_args = ["--home", str(self.home)] if home_args is None else home_args
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--manifest", str(manifest_path), *home_args, *extra_args],
            cwd=str(ROOT), env=cli_env, capture_output=True, text=True, timeout=60)

    # -- all-pass -------------------------------------------------------------

    def test_all_pass(self):
        manifest, alpha, beta = self.setup_pair()
        report = self.report(manifest)
        self.assertEqual(report["result"], "ok")
        for skill in report["skills"]:
            self.assertTrue(skill["pass"], skill)
        self.assertEqual(report["extra_skills"], [])
        self.assertEqual(report["unlocked_folders"], [])
        self.assertEqual(report["lock"], {"source": "default", "state": "ok", "version": 3, "version_matches": True})
        result = self.run_cli(manifest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("result: ok", result.stdout)

    # -- sha drift --------------------------------------------------------------

    def test_sha_drift(self):
        manifest, alpha, beta = self.setup_pair()
        self.write_canonical("alpha-skill", b"# drifted content, not what the manifest hashed\n")
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "alpha-skill")["canonical"]["state"], "sha_mismatch")
        self.assertFalse(self.skill_result(report, "alpha-skill")["pass"])
        self.assertTrue(self.skill_result(report, "beta-skill")["pass"])
        self.assertEqual(report["result"], "fail")
        result = self.run_cli(manifest)
        self.assertEqual(result.returncode, 1)
        self.assertIn("sha_mismatch", result.stdout)

    def test_canonical_missing_and_wrong_type(self):
        alpha = self.make_skill("alpha-skill")
        shutil.rmtree(self.home / ".agents" / "skills" / "alpha-skill")
        manifest = self.build_manifest([alpha])
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "alpha-skill")["canonical"]["state"], "missing")
        (self.home / ".agents" / "skills" / "alpha-skill").mkdir(parents=True)
        (self.home / ".agents" / "skills" / "alpha-skill" / "SKILL.md").mkdir()  # a directory, not a file
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "alpha-skill")["canonical"]["state"], "not_a_file")

    # -- lock drift ---------------------------------------------------------

    def test_lock_drift(self):
        manifest, alpha, beta = self.setup_pair()
        entries = self.lock_entries_for([alpha, beta])
        entries["alpha-skill"]["skillFolderHash"] = hashlib.sha1(b"tree:not-alpha-skill").hexdigest()
        self.write_lock(entries)
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "alpha-skill")["lock"]["state"], "hash_mismatch")
        self.assertFalse(self.skill_result(report, "alpha-skill")["pass"])
        self.assertTrue(self.skill_result(report, "beta-skill")["pass"])
        self.assertEqual(report["result"], "fail")
        self.assertEqual(self.run_cli(manifest).returncode, 1)

    def test_lock_unreadable_fails_every_skill(self):
        manifest, alpha, beta = self.setup_pair()
        (self.home / ".agents" / ".skill-lock.json").write_text("{not json")
        report = self.report(manifest)
        self.assertEqual(report["lock"]["state"], "invalid")
        self.assertEqual(self.skill_result(report, "alpha-skill")["lock"]["state"], "lock_unreadable")
        self.assertEqual(report["result"], "fail")

    # -- missing link ---------------------------------------------------------

    def test_missing_link(self):
        alpha = self.make_skill("alpha-skill")
        manifest = self.build_manifest([alpha])
        self.write_lock(self.lock_entries_for([alpha]))
        self.write_claude_settings({})
        self.write_codex_config([])
        # No ~/.claude/skills/alpha-skill created at all.
        report = self.report(manifest)
        link = self.skill_result(report, "alpha-skill")["claude_link"]
        self.assertEqual((link["state"], link["kind"]), ("missing", "missing"))
        self.assertEqual(report["result"], "fail")

    # -- absolute link reported (still passes) --------------------------------

    def test_absolute_link_reported(self):
        alpha = self.make_skill("alpha-skill")
        manifest = self.build_manifest([alpha])
        self.write_lock(self.lock_entries_for([alpha]))
        self.write_claude_link("alpha-skill", kind="absolute")
        self.write_claude_settings({})
        self.write_codex_config([])
        report = self.report(manifest)
        link = self.skill_result(report, "alpha-skill")["claude_link"]
        self.assertEqual(link, {"state": "ok", "kind": "absolute"})
        self.assertTrue(self.skill_result(report, "alpha-skill")["pass"])
        self.assertEqual(report["result"], "ok")

    def test_relative_link_reported(self):
        alpha = self.make_skill("alpha-skill")
        manifest = self.build_manifest([alpha])
        self.write_lock(self.lock_entries_for([alpha]))
        self.write_claude_link("alpha-skill", kind="relative")
        self.write_claude_settings({})
        self.write_codex_config([])
        link = self.skill_result(self.report(manifest), "alpha-skill")["claude_link"]
        self.assertEqual(link, {"state": "ok", "kind": "relative"})

    def test_copy_kind_is_reported_and_fails(self):
        alpha = self.make_skill("alpha-skill")
        manifest = self.build_manifest([alpha])
        self.write_lock(self.lock_entries_for([alpha]))
        self.write_claude_link("alpha-skill", kind="copy")
        self.write_claude_settings({})
        self.write_codex_config([])
        report = self.report(manifest)
        link = self.skill_result(report, "alpha-skill")["claude_link"]
        self.assertEqual((link["state"], link["kind"]), ("not_a_symlink", "copy"))
        self.assertEqual(report["result"], "fail")

    def layout_report(self, alpha):
        manifest = self.build_manifest([alpha])
        self.write_lock(self.lock_entries_for([alpha]))
        self.write_claude_settings({})
        self.write_codex_config([])
        report = self.report(manifest)
        return report, self.skill_result(report, alpha["name"])

    def test_a_claude_skills_folder_linked_onto_the_canonical_one_is_the_layout_createsymlink_accepts(self):
        """skills@7407f389 src/installer.ts L240-250: createSymlink returns without touching anything when the link path and the canonical folder are one real path, which is what a
        parent link makes them. install_skills.py has accepted it since 2026-10-11; the status check reported it as not_a_symlink (Astra's read of 0d5272df7, follow-up 1)."""
        alpha = self.make_skill("alpha-skill")
        (self.home / ".claude").mkdir()
        (self.home / ".claude" / "skills").symlink_to(self.home / ".agents" / "skills", target_is_directory=True)
        report, skill = self.layout_report(alpha)
        self.assertEqual(skill["claude_link"], {"state": "ok", "kind": "parent_link"})
        self.assertEqual((skill["canonical"]["state"], skill["pass"], report["result"]), ("ok", True, "ok"))

    def test_a_canonical_skills_folder_linked_onto_the_claude_one_is_accepted_too(self):
        alpha = self.make_skill("alpha-skill")
        real = self.home / ".claude" / "skills"
        real.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self.home / ".agents" / "skills"), str(real))  # the folder, with the skill, now lives under .claude
        (self.home / ".agents" / "skills").symlink_to(real, target_is_directory=True)
        report, skill = self.layout_report(alpha)
        self.assertEqual(skill["claude_link"], {"state": "ok", "kind": "parent_link"})
        self.assertEqual((skill["canonical"]["state"], report["result"]), ("ok", "ok"))

    def test_a_canonical_leaf_that_is_a_link_is_not_the_folder_the_cli_writes(self):
        """install_skills.py refuses a link at the canonical skill path (the add removes it first, src/installer.ts L389) as local-modified; the status check followed it and said ok
        (Astra's read of 0d5272df7, follow-up 1, and the Codex review in GitHub, thread 2). Both required checks now enforce the same rule."""
        alpha = self.make_skill("alpha-skill")
        content = (self.home / ".agents" / "skills" / "alpha-skill" / "SKILL.md").read_bytes()
        shutil.rmtree(self.home / ".agents" / "skills" / "alpha-skill")
        elsewhere = self.home / "dotfiles" / "alpha-skill"
        elsewhere.mkdir(parents=True)
        (elsewhere / "SKILL.md").write_bytes(content)
        (self.home / ".agents" / "skills" / "alpha-skill").symlink_to(elsewhere, target_is_directory=True)
        self.write_claude_link("alpha-skill", kind="relative")
        report, skill = self.layout_report(alpha)
        self.assertEqual(skill["canonical"]["state"], "canonical_link")
        self.assertEqual((skill["pass"], report["result"]), (False, "fail"))

    def test_a_canonical_link_onto_a_real_claude_folder_is_not_ok_in_either_check(self):
        """The reverse alias of #1024: the canonical path links onto the real folder at the Claude path, so the two resolve equal while the Claude entry is no link of the CLI's."""
        alpha = self.make_skill("alpha-skill")
        content = (self.home / ".agents" / "skills" / "alpha-skill" / "SKILL.md").read_bytes()
        shutil.rmtree(self.home / ".agents" / "skills" / "alpha-skill")
        real = self.home / ".claude" / "skills" / "alpha-skill"
        real.mkdir(parents=True)
        (real / "SKILL.md").write_bytes(content)
        (self.home / ".agents" / "skills" / "alpha-skill").symlink_to(real, target_is_directory=True)
        report, skill = self.layout_report(alpha)
        self.assertEqual(skill["canonical"]["state"], "canonical_link")
        self.assertEqual(skill["claude_link"]["state"], "not_a_symlink")
        self.assertEqual(report["result"], "fail")

    def test_a_canonical_link_is_not_judged_for_an_entry_that_is_not_installed_for_claude_code(self):
        """The installer applies the rule to an entry installed for Claude Code only (the CLI returns after the canonical write for a universal agent, src/installer.ts L395-402; the Codex
        review in GitHub on #1035)."""
        alpha = dict(self.make_skill("alpha-skill"), agents=["codex"])
        content = (self.home / ".agents" / "skills" / "alpha-skill" / "SKILL.md").read_bytes()
        shutil.rmtree(self.home / ".agents" / "skills" / "alpha-skill")
        elsewhere = self.home / "dotfiles" / "alpha-skill"
        elsewhere.mkdir(parents=True)
        (elsewhere / "SKILL.md").write_bytes(content)
        (self.home / ".agents" / "skills" / "alpha-skill").symlink_to(elsewhere, target_is_directory=True)
        self.write_claude_link("alpha-skill", kind="relative")
        report, skill = self.layout_report(alpha)
        self.assertEqual(skill["canonical"]["state"], "ok")

    def test_git_tree_sha_skips_a_named_directory_but_hashes_a_file_or_link_of_that_name_when_asked(self):
        folder = self.tmp / "tree"
        (folder / ".venv").mkdir(parents=True)
        (folder / ".venv" / "x").write_text("x")
        (folder / "SKILL.md").write_text("# s\n")
        skip = frozenset({".venv", "node_modules"})
        plain = ss.git_tree_sha(folder, frozenset())
        skipped = ss.git_tree_sha(folder, skip)
        self.assertNotEqual(plain, skipped)
        self.assertEqual(ss.git_tree_sha(folder, skip, skip_dirs_only=True), skipped, "a real directory of that name is skipped either way")
        shutil.rmtree(folder / ".venv")
        (folder / ".venv").write_text("mine")
        self.assertEqual(ss.git_tree_sha(folder, skip), ss.git_tree_sha(folder, skip), "the default skips by name, as the status check always has")
        self.assertNotEqual(ss.git_tree_sha(folder, skip, skip_dirs_only=True), skipped, "a file named .venv is content")
        (folder / ".venv").unlink()
        (folder / "node_modules").symlink_to(self.tmp, target_is_directory=True)
        self.assertNotEqual(ss.git_tree_sha(folder, skip, skip_dirs_only=True), ss.git_tree_sha(folder, skip), "a link named node_modules is content")
        (folder / "node_modules").unlink()
        (folder / "scripts").mkdir()
        (folder / "scripts" / "__pycache__").write_text("mine")
        nested = frozenset({"__pycache__"})
        self.assertNotEqual(ss.git_tree_sha(folder, nested, skip_dirs_only=True), ss.git_tree_sha(folder, nested), "the rule holds below the top level too")

    def test_git_tree_sha_in_strict_mode_refuses_an_entry_a_git_tree_cannot_hold(self):
        """Review of 9a77a96e in GitHub (#1035, round two): an empty directory and a special file have no entry in a git tree, so the hash accepted a folder that held one, and the add deletes it."""
        folder = self.tmp / "strict"
        skip = frozenset({"__pycache__"})
        cases = (("an empty directory", {}, lambda: (folder / "notes").mkdir()), ("a nested empty directory", {}, lambda: (folder / "notes" / "inner").mkdir(parents=True)),
                 ("a named pipe", {}, lambda: os.mkfifo(folder / "pipe")), ("a directory holding only a skipped one", {}, lambda: (folder / "cache" / "__pycache__").mkdir(parents=True)),
                 ("an empty directory beside a file", {"refs/a.md": "a"}, lambda: (folder / "refs" / "empty").mkdir()))
        for label, files, make in cases:
            with self.subTest(entry=label):
                shutil.rmtree(folder, ignore_errors=True)
                folder.mkdir()
                for name, text in {"SKILL.md": "# s\n", **files}.items():
                    (folder / name).parent.mkdir(parents=True, exist_ok=True)
                    (folder / name).write_text(text)
                plain = ss.git_tree_sha(folder, skip)
                make()
                self.assertEqual(ss.git_tree_sha(folder, skip), plain, "the default leaves it out, as git does, and as the status check always has")
                with self.assertRaises(ss.UnrepresentedEntry):
                    ss.git_tree_sha(folder, skip, skip_dirs_only=True, strict=True)
        shutil.rmtree(folder, ignore_errors=True)
        (folder / ".venv").mkdir(parents=True)
        (folder / "SKILL.md").write_text("# s\n")
        self.assertEqual(ss.git_tree_sha(folder, frozenset({".venv"}), skip_dirs_only=True, strict=True), ss.git_tree_sha(folder, frozenset({".venv"})), "an empty skipped directory is regenerated, not content")

    def test_a_real_folder_that_cannot_be_resolved_is_not_accepted_as_a_parent_alias(self):
        link, canonical = self.home / ".claude" / "skills" / "alpha-skill", self.home / ".agents" / "skills" / "alpha-skill"
        link.mkdir(parents=True)
        canonical.mkdir(parents=True)
        with mock.patch.object(ss.Path, "resolve", side_effect=RuntimeError("Symlink loop from 'x'")):
            result = ss.check_claude_link(link, canonical, parent_alias=True)
        self.assertEqual(result, {"state": "not_a_symlink", "kind": "copy"})

    def test_a_claude_code_copy_is_still_a_real_folder_in_its_own_place(self):
        """A parent link must not turn the copy check around: a copy entry compares the Claude path with itself."""
        alpha = dict(self.make_skill("alpha-skill"), copy=True, agents=["claude-code"])
        real = self.home / ".claude" / "skills" / "alpha-skill"
        real.mkdir(parents=True)
        shutil.copy(self.home / ".agents" / "skills" / "alpha-skill" / "SKILL.md", real / "SKILL.md")
        shutil.rmtree(self.home / ".agents" / "skills" / "alpha-skill")
        report, skill = self.layout_report(alpha)
        self.assertEqual(skill["claude_link"], {"state": "ok", "kind": "copy"})

    def test_wrong_target_link_fails(self):
        alpha = self.make_skill("alpha-skill")
        manifest = self.build_manifest([alpha])
        self.write_lock(self.lock_entries_for([alpha]))
        self.write_claude_link("alpha-skill", kind="wrong_target")
        self.write_claude_settings({})
        self.write_codex_config([])
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "alpha-skill")["claude_link"]["state"], "wrong_target")
        self.assertEqual(report["result"], "fail")

    def test_symlink_loop_reports_cannot_resolve_without_crashing(self):
        """A symlink cycle makes Path.resolve() raise RuntimeError("Symlink loop from ...")
        on CPython 3.11/3.12 (verified empirically against this repo's own interpreters);
        3.13+ instead tolerates the cycle silently in non-strict mode and raises nothing.
        The real symlink below exercises the state/kind computation that runs before the
        resolve() call; RuntimeError itself is forced via mock so the regression holds
        under whichever interpreter actually runs this suite, not just the ones where a
        real filesystem loop happens to reproduce it."""
        claude_skills = self.home / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        link = claude_skills / "looped-skill"
        link.symlink_to(link.name)  # a real, relative, self-referential symlink
        canonical = self.home / ".agents" / "skills" / "looped-skill"
        with mock.patch.object(ss.Path, "resolve", side_effect=RuntimeError("Symlink loop from 'x'")):
            result = ss.check_claude_link(link, canonical)
        self.assertEqual(result, {"state": "cannot_resolve", "kind": "relative"})

    # -- wrong override -------------------------------------------------------

    def test_wrong_override(self):
        manifest, alpha, beta = self.setup_pair()
        self.write_claude_settings({"beta-skill": "off"})  # manifest pins beta at "name-only"
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "beta-skill")["claude_listing"],
                         {"state": "mismatch", "actual": "off"})
        self.assertFalse(self.skill_result(report, "beta-skill")["pass"])
        self.assertTrue(self.skill_result(report, "alpha-skill")["pass"])
        self.assertEqual(report["result"], "fail")
        self.assertEqual(self.run_cli(manifest).returncode, 1)

    def test_missing_override_key_defaults_to_on(self):
        on_skill = self.make_skill("on-skill", claude_listing="on")
        off_skill = self.make_skill("off-skill", claude_listing="off", codex_enabled=False)
        manifest = self.build_manifest([on_skill, off_skill])
        self.write_lock(self.lock_entries_for([on_skill, off_skill]))
        self.write_claude_link("on-skill")
        self.write_claude_link("off-skill")
        self.write_claude_settings({})  # no key for either skill: Claude's own default of "on" applies
        self.write_codex_config(["off-skill"])
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "on-skill")["claude_listing"], {"state": "ok", "actual": "on"})
        self.assertEqual(self.skill_result(report, "off-skill")["claude_listing"],
                         {"state": "mismatch", "actual": "on"})
        self.assertTrue(self.skill_result(report, "on-skill")["pass"])
        self.assertFalse(self.skill_result(report, "off-skill")["pass"])

    def test_missing_settings_file_defaults_to_on(self):
        on_skill = self.make_skill("on-skill", claude_listing="on")
        manifest = self.build_manifest([on_skill])
        self.write_lock(self.lock_entries_for([on_skill]))
        self.write_claude_link("on-skill")
        self.write_codex_config([])
        # ~/.claude/settings.json is never written.
        report = self.report(manifest)
        self.assertEqual(report["claude_settings"]["state"], "ok")
        self.assertTrue(self.skill_result(report, "on-skill")["pass"])

    def test_malformed_settings_fails_every_listing_check(self):
        manifest, alpha, beta = self.setup_pair()
        (self.home / ".claude" / "settings.json").write_text("{not json")
        report = self.report(manifest)
        self.assertEqual(report["claude_settings"]["state"], "invalid")
        listing = self.skill_result(report, "alpha-skill")["claude_listing"]
        self.assertEqual(listing, {"state": "settings_unreadable", "actual": None})
        self.assertEqual(report["result"], "fail")

    # -- missing codex disable -------------------------------------------------

    def test_missing_codex_disable_no_config_file(self):
        skill = self.make_skill("gated-skill", codex_enabled=False)
        manifest = self.build_manifest([skill])
        self.write_lock(self.lock_entries_for([skill]))
        self.write_claude_link("gated-skill")
        self.write_claude_settings({})
        # ~/.codex/config.toml is never written.
        report = self.report(manifest)
        self.assertEqual(report["codex_config"]["state"], "missing")
        self.assertEqual(self.skill_result(report, "gated-skill")["codex_disable"],
                         {"state": "config_missing", "disable_entry_present": False})
        self.assertEqual(report["result"], "fail")

    def test_missing_codex_disable_entry_in_present_config(self):
        skill = self.make_skill("gated-skill", codex_enabled=False)
        manifest = self.build_manifest([skill])
        self.write_lock(self.lock_entries_for([skill]))
        self.write_claude_link("gated-skill")
        self.write_claude_settings({})
        self.write_codex_config([])  # config.toml exists but names no skill
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "gated-skill")["codex_disable"],
                         {"state": "missing_disable_entry", "disable_entry_present": False})
        self.assertEqual(report["result"], "fail")

    def test_codex_config_invalid_toml_fails_disabled_skill(self):
        skill = self.make_skill("gated-skill", codex_enabled=False)
        manifest = self.build_manifest([skill])
        self.write_lock(self.lock_entries_for([skill]))
        self.write_claude_link("gated-skill")
        self.write_claude_settings({})
        codex_dir = self.home / ".codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "config.toml").write_text("this is not [ valid toml")
        report = self.report(manifest)
        self.assertEqual(report["codex_config"]["state"], "invalid")
        self.assertEqual(self.skill_result(report, "gated-skill")["codex_disable"]["state"], "config_unreadable")

    def test_codex_enabled_true_rejects_unexpected_disable_entry(self):
        skill = self.make_skill("open-skill", codex_enabled=True)
        manifest = self.build_manifest([skill])
        self.write_lock(self.lock_entries_for([skill]))
        self.write_claude_link("open-skill")
        self.write_claude_settings({})
        self.write_codex_config(["open-skill"])  # should not be disabled per the manifest
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "open-skill")["codex_disable"],
                         {"state": "unexpected_disable_entry", "disable_entry_present": True})
        self.assertEqual(report["result"], "fail")

    def test_codex_enabled_true_passes_with_missing_config(self):
        skill = self.make_skill("open-skill", codex_enabled=True)
        manifest = self.build_manifest([skill])
        self.write_lock(self.lock_entries_for([skill]))
        self.write_claude_link("open-skill")
        self.write_claude_settings({})
        # No ~/.codex/config.toml: trivially "no such disabling table".
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "open-skill")["codex_disable"], {"state": "ok",
                                                                                    "disable_entry_present": False})
        self.assertEqual(report["result"], "ok")

    # -- codex path selector ------------------------------------------------------
    # Codex applies a [[skills.config]] name rule to every loaded skill of that name and a path rule to the one skill
    # whose canonical path_to_skills_md it names (openai/codex rust-v0.159.2 codex-rs/config/src/skills_config.rs
    # L94-125, codex-rs/ext/skills/src/host_service.rs L366-371, host_outcome.rs L52-54).

    def setup_disabled(self, name="gated-skill"):
        skill = self.make_skill(name, codex_enabled=False)
        manifest = self.build_manifest([skill])
        self.write_lock(self.lock_entries_for([skill]))
        self.write_claude_link(name)
        self.write_claude_settings({})
        return manifest, skill

    def codex_disable_of(self, manifest, name):
        return self.skill_result(self.report(manifest), name)["codex_disable"]

    def test_path_keyed_disable_entry_passes(self):
        manifest, skill = self.setup_disabled()
        self.write_codex_config([], disable_paths=[self.skill_md_path("gated-skill")])
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "gated-skill")["codex_disable"],
                         {"state": "ok", "disable_entry_present": True})
        self.assertEqual(report["result"], "ok")
        result = self.run_cli(manifest)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn(str(self.home), result.stdout)  # the entry's path is read, never echoed

    def test_path_keyed_entry_is_resolved_as_codex_resolves_it(self):
        # A leading ~ expands against the home (codex-rs/utils/absolute-path/src/lib.rs L28-44 at rust-v0.159.2), a
        # relative path against config.toml's folder (config/src/loader/mod.rs L573-582 and L1424-1431), and both
        # the rule's path and the loaded skill's are canonicalized (skills_config.rs L188-192;
        # ext/skills/src/loader/host.rs L192-196), so a path through a symlink to the home names the same skill.
        manifest, skill = self.setup_disabled()
        link = self.tmp / "home-link"
        link.symlink_to(self.home, target_is_directory=True)
        for value in ("~/.agents/skills/gated-skill/SKILL.md", "../.agents/skills/gated-skill/SKILL.md",
                      str(link / ".agents" / "skills" / "gated-skill" / "SKILL.md"),
                      str(self.home / ".agents" / "x" / ".." / "skills" / "gated-skill" / "SKILL.md")):
            with self.subTest(path=value):
                self.write_codex_config([], disable_paths=[value])
                self.assertEqual(self.codex_disable_of(manifest, "gated-skill"),
                                 {"state": "ok", "disable_entry_present": True})

    def test_path_keyed_entry_for_another_copy_is_not_the_match(self):
        # Another home's copy, or the skill folder instead of its SKILL.md, leaves the installed copy enabled.
        manifest, skill = self.setup_disabled()
        elsewhere = self.tmp / "other-home" / ".agents" / "skills" / "gated-skill" / "SKILL.md"
        for value in (elsewhere, self.skill_md_path("gated-skill").parent, "~other/.agents/skills/gated-skill/SKILL.md"):
            with self.subTest(path=str(value)):
                self.write_codex_config([], disable_paths=[value])
                self.assertEqual(self.codex_disable_of(manifest, "gated-skill"),
                                 {"state": "missing_disable_entry", "disable_entry_present": False})

    def test_without_a_known_path_a_path_entry_matches_by_its_skill_folder_name(self):
        skill = self.make_skill("gated-skill", codex_enabled=False)
        entry = {"path": "/srv/example-home/.agents/skills/gated-skill/SKILL.md", "enabled": False}
        config = {"skills": {"config": [entry]}}
        self.assertEqual(ss.check_codex_disable(config, "ok", skill), {"state": "ok", "disable_entry_present": True})
        for other in ("/srv/example-home/.agents/skills/other-skill/SKILL.md",
                      "/srv/example-home/.agents/skills/gated-skill"):
            with self.subTest(path=other):
                entry["path"] = other
                self.assertEqual(ss.check_codex_disable(config, "ok", skill),
                                 {"state": "missing_disable_entry", "disable_entry_present": False})

    def test_a_name_keyed_disable_of_skill_creator_is_reported_as_hiding_the_bundled_skill(self):
        # Codex installs its own skill-creator into CODEX_HOME/skills/.system (codex-rs/skills/src/lib.rs L55-67,
        # src/assets/samples/skill-creator/SKILL.md L2 at rust-v0.159.2), so a name rule for it disables that
        # bundled copy along with the pinned one; only the path rule leaves the bundled copy enabled.
        manifest, skill = self.setup_disabled("skill-creator")
        hidden = {"state": "name_entry_hides_bundled_skill", "disable_entry_present": True}
        for paths in ([], [self.skill_md_path("skill-creator")]):
            with self.subTest(with_path_entry=bool(paths)):
                self.write_codex_config(["skill-creator"], disable_paths=paths)
                report = self.report(manifest)
                self.assertEqual(self.skill_result(report, "skill-creator")["codex_disable"], hidden)
                self.assertFalse(self.skill_result(report, "skill-creator")["pass"])
                self.assertEqual(report["result"], "fail")
        self.write_codex_config([], disable_paths=[self.skill_md_path("skill-creator")])
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "skill-creator")["codex_disable"],
                         {"state": "ok", "disable_entry_present": True})
        self.assertEqual(report["result"], "ok")
        result = self.run_cli(manifest)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_path_keyed_disable_of_a_codex_enabled_skill_is_unexpected(self):
        skill = self.make_skill("open-skill", codex_enabled=True)
        manifest = self.build_manifest([skill])
        self.write_lock(self.lock_entries_for([skill]))
        self.write_claude_link("open-skill")
        self.write_claude_settings({})
        self.write_codex_config([], disable_paths=[self.skill_md_path("open-skill")])
        self.assertEqual(self.codex_disable_of(manifest, "open-skill"),
                         {"state": "unexpected_disable_entry", "disable_entry_present": True})

    def test_entries_codex_ignores_disable_nothing_and_a_name_is_trimmed(self):
        # skills_config.rs L188-210: an entry with both selectors or neither is ignored, and so is a blank name; a
        # name is trimmed before it is compared.
        manifest, skill = self.setup_disabled()
        path = str(self.skill_md_path("gated-skill"))
        for entry in ({"name": "gated-skill", "path": path, "enabled": False}, {"enabled": False},
                      {"name": "   ", "enabled": False}):
            with self.subTest(entry=sorted(entry)):
                self.write_codex_entries([entry])
                self.assertEqual(self.codex_disable_of(manifest, "gated-skill"),
                                 {"state": "missing_disable_entry", "disable_entry_present": False})
        self.write_codex_entries([{"name": " gated-skill ", "enabled": False}])
        self.assertEqual(self.codex_disable_of(manifest, "gated-skill"), {"state": "ok", "disable_entry_present": True})

    def test_a_path_no_file_can_have_selects_nothing_instead_of_crashing(self):
        # TOML allows an escaped NUL in a string, which no path can hold (os.path.realpath raises ValueError on it).
        manifest, skill = self.setup_disabled()
        self.write_codex_entries([{"path": str(self.skill_md_path("gated-skill")) + "\u0000", "enabled": False}])
        self.assertEqual(self.codex_disable_of(manifest, "gated-skill"),
                         {"state": "missing_disable_entry", "disable_entry_present": False})

    # -- XDG lock path ----------------------------------------------------------

    def test_xdg_lock_path(self):
        manifest, alpha, beta = self.setup_pair()
        xdg_state = self.tmp / "xdg-state"
        env = {**self.env, "XDG_STATE_HOME": str(xdg_state)}
        xdg_lock, source = ss.resolve_lock_path(self.home, env)
        self.assertEqual(source, "xdg_state_home")
        (self.home / ".agents" / ".skill-lock.json").unlink()  # only the XDG-selected path may hold it now
        self.write_lock(self.lock_entries_for([alpha, beta]), path=xdg_lock)
        report = self.report(manifest, env=env)
        self.assertEqual(report["lock"], {"source": "xdg_state_home", "state": "ok", "version": 3,
                                          "version_matches": True})
        self.assertEqual(report["result"], "ok")
        result = self.run_cli(manifest, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        # Without XDG_STATE_HOME the default path is consulted, and it is now empty.
        default_report = self.report(manifest)
        self.assertEqual(default_report["lock"]["state"], "missing")
        self.assertEqual(default_report["result"], "fail")

    def test_lock_path_is_joined_as_the_cli_path_join_joins_it(self):
        # skills 1.7.0 builds the lock path with path.join (vercel-labs/skills@7407f389 src/skill-lock.ts:67-72),
        # which collapses ".." and a leading //, from HOME or XDG_STATE_HOME verbatim. pathlib keeps the "..",
        # and a path through the missing folder does not exist, so the lock the CLI wrote read as missing.
        manifest, alpha, beta = self.setup_pair()
        missing, xdg_state = self.tmp / "missing", self.tmp / "xdg-state"
        xdg_lock = xdg_state / "skills" / ".skill-lock.json"
        env = {**self.env, "XDG_STATE_HOME": str(missing / ".." / "xdg-state")}
        self.assertEqual(ss.resolve_lock_path(self.home, env), (xdg_lock, "xdg_state_home"))
        self.assertEqual(ss.resolve_lock_path(self.home, {"XDG_STATE_HOME": "/" + str(xdg_state)}),
                         (xdg_lock, "xdg_state_home"))
        self.assertEqual(ss.resolve_lock_path(missing / ".." / "home", {}),
                         (self.home / ".agents" / ".skill-lock.json", "default"))
        (self.home / ".agents" / ".skill-lock.json").unlink()  # only the CLI's XDG lock holds the entries now
        self.write_lock(self.lock_entries_for([alpha, beta]), path=xdg_lock)
        report = self.report(manifest, env=env)
        self.assertEqual(report["lock"], {"source": "xdg_state_home", "state": "ok", "version": 3,
                                          "version_matches": True})
        self.assertEqual(report["result"], "ok")
        result = self.run_cli(manifest, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)

    def make_link_dotdot(self) -> Path:
        """tmp/link -> deep/er, so tmp/link/.. is tmp/deep on disk and tmp lexically."""
        (self.tmp / "deep" / "er").mkdir(parents=True)
        (self.tmp / "link").symlink_to("deep/er", target_is_directory=True)
        return self.tmp / "link" / ".."

    def test_report_reads_every_path_through_a_dotdot_in_home_as_the_cli_joins_it(self):
        # skills 1.7.0 joins the canonical folder, the lock and the claude-code link folder with path.join from HOME
        # verbatim (os.homedir(); npm dist/cli.mjs L2208-2210, L3746-3750, L1398 and L1511), which collapses a ".."
        # lexically, and so do Claude Code for its settings and Codex for its default config (claude_settings_path,
        # codex_config_path). pathlib keeps the "..": after a missing folder that path does not exist, and after a
        # symlink it names the link target's parent. The fixture is installed at the lexical tmp/home.
        manifest, alpha, beta = self.setup_pair()
        for label, parent in (("missing", self.tmp / "missing" / ".."), ("symlink", self.make_link_dotdot())):
            home = parent / "home"
            with self.subTest(case=label, home=str(home)):
                report = ss.inspect(manifest, home, {"HOME": str(home)})
                self.assertEqual(report["lock"], {"source": "default", "state": "ok", "version": 3,
                                                  "version_matches": True})
                self.assertEqual([{check: skill[check]["state"] for check in ("canonical", "lock", "claude_link")}
                                  for skill in report["skills"]],
                                 [{"canonical": "ok", "lock": "ok", "claude_link": "ok"}] * 2)
                self.assertEqual(report["result"], "ok")
                # Through main() without --home, whose default is Path.home(): HOME verbatim.
                result = self.run_cli(manifest, "--json", env={"HOME": str(home)}, home_args=[])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["skills"], report["skills"])

    def test_claude_config_dir_moves_the_link_folder_as_the_cli_does(self):
        # skills 1.7.0 links claude-code skills in path.join(CLAUDE_CONFIG_DIR.trim(), "skills") when that is not
        # blank, else in path.join(HOME, ".claude", "skills") (dist/cli.mjs L1398, L1511). JavaScript's trim() also
        # removes U+FEFF and U+3000, and path.join collapses the "..".
        manifest, alpha, beta = self.setup_pair()
        links = {"alpha-skill": {"state": "ok", "kind": "relative"}, "beta-skill": {"state": "ok", "kind": "relative"}}
        missing = {name: {"state": "missing", "kind": "missing"} for name in links}

        def link_states(value: str) -> dict:
            report = self.report(manifest, env={**self.env, "CLAUDE_CONFIG_DIR": value})
            return {skill["name"]: skill["claude_link"] for skill in report["skills"]}

        # While it is set, the correct links under ~/.claude are not the CLI's; a blank value is unset.
        (self.tmp / "claude-config").mkdir()
        self.assertEqual(link_states(str(self.tmp / "claude-config")), missing)
        self.assertEqual(link_states(" 　\t"), links)
        link_dir = self.tmp / "claude-config" / "skills"
        link_dir.mkdir()
        for name in links:
            canonical = self.home / ".agents" / "skills" / name
            (link_dir / name).symlink_to(os.path.relpath(canonical, link_dir), target_is_directory=True)
            default_link = self.home / ".claude" / "skills" / name
            default_link.unlink()
            default_link.symlink_to(self.tmp, target_is_directory=True)  # only the moved link can pass now
        padded = "﻿" + str(self.tmp / "missing" / ".." / "claude-config") + "　"
        self.assertEqual(link_states(padded), links)

    def test_claude_config_dir_moves_the_settings_file_as_claude_code_does(self):
        # Claude Code keeps settings under CLAUDE_CONFIG_DIR when set (code.claude.com/docs/en/env-vars, settings).
        # Its installed 2.1.284 bundle reads path.join(path.resolve(dir), "settings.json") with
        # dir = (CLAUDE_CONFIG_DIR ?? path.join(os.homedir(), ".claude")).normalize("NFC"): not trimmed, unlike the
        # skills CLI's link folder, and set even when empty.
        manifest, alpha, beta = self.setup_pair()
        self.write_claude_settings({"beta-skill": "off"})  # the default file now disagrees with the manifest
        config_dir = self.tmp / "café"
        config_dir.mkdir()
        (config_dir / "settings.json").write_text(json.dumps({"skillOverrides": {"beta-skill": "name-only"}}))

        def beta_listing(env: dict) -> dict:
            report = self.report(manifest, env=env)
            self.assertEqual(report["claude_settings"], {"state": "ok"})
            return self.skill_result(report, "beta-skill")["claude_listing"]

        for label, value in (("dotdot", str(self.tmp / "missing" / ".." / "café")),
                             ("nfd", str(self.tmp / "café"))):
            with self.subTest(case=label):
                self.assertEqual(beta_listing({**self.env, "CLAUDE_CONFIG_DIR": value}),
                                 {"state": "ok", "actual": "name-only"})
        # Untrimmed, a padded value names no settings file, so beta falls back to the default "on".
        self.assertEqual(beta_listing({**self.env, "CLAUDE_CONFIG_DIR": "　" + str(config_dir)}),
                         {"state": "mismatch", "actual": "on"})
        self.assertEqual(beta_listing(self.env), {"state": "mismatch", "actual": "off"})
        self.assertEqual(ss.claude_settings_path(self.home, {"CLAUDE_CONFIG_DIR": ""}),
                         Path(os.getcwd()) / "settings.json")  # path.resolve("") is the working directory
        self.assertEqual(ss.claude_settings_path(self.home, {}), self.home / ".claude" / "settings.json")

    def test_codex_home_moves_the_config_file_as_codex_does(self):
        # Codex reads config.toml under CODEX_HOME (developers.openai.com/codex/config-advanced). rust-v0.157.1
        # canonicalizes a non-empty CODEX_HOME (codex-rs/utils/home-dir/src/lib.rs find_codex_home), so a ".." after
        # a symlink is resolved on disk: link/../codex is deep/codex, not the tmp/codex that path.join would name.
        manifest, alpha, beta = self.setup_pair()
        self.write_codex_config([])  # the default config now lacks beta's disable entry
        parent = self.make_link_dotdot()
        for folder, names in ((self.tmp / "deep" / "codex", ["beta-skill"]), (self.tmp / "codex", [])):
            folder.mkdir()
            (folder / "config.toml").write_text(
                "".join(f'[[skills.config]]\nname = "{name}"\nenabled = false\n\n' for name in names))

        def beta_disable(value: str) -> dict:
            report = self.report(manifest, env={**self.env, "CODEX_HOME": value})
            return self.skill_result(report, "beta-skill")["codex_disable"]

        self.assertEqual(beta_disable(str(parent / "codex")), {"state": "ok", "disable_entry_present": True})
        self.assertEqual(beta_disable(str(self.tmp / "codex")),
                         {"state": "missing_disable_entry", "disable_entry_present": False})
        # An empty CODEX_HOME is unset (find_codex_home filters it): the default config is read again.
        self.assertEqual(beta_disable(""), {"state": "missing_disable_entry", "disable_entry_present": False})

    def test_global_paths_agree_with_install_skills(self):
        # This checker keeps copies of install_skills.py's join and trim (node_path_join, JS_TRIM_CHARS); the global
        # paths both build from them must agree, for a "..", // or relative HOME and a blank, padded or ".."
        # CLAUDE_CONFIG_DIR or XDG_STATE_HOME.
        spec = importlib.util.spec_from_file_location("install_skills_for_status_tests",
                                                      ROOT / "tools" / "adoption" / "install_skills.py")
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        self.assertEqual(ss.JS_TRIM_CHARS, installer.JS_TRIM_CHARS)
        homes = (Path("/h/missing/../base"), Path("//h/./base"), Path("rel/../../x"))
        values = (None, " 　", "﻿/c/missing/../config ", "//c//config/", "\u0085/c", "rel/../c")
        for home in homes:
            for value in values:
                env = {} if value is None else {"CLAUDE_CONFIG_DIR": value, "XDG_STATE_HOME": value}
                with self.subTest(home=str(home), value=value), mock.patch.dict(os.environ, env):
                    for name in ("CLAUDE_CONFIG_DIR", "XDG_STATE_HOME"):
                        if value is None:
                            os.environ.pop(name, None)
                    self.assertEqual(ss.agents_skills_dir(home) / "x", installer.canonical_skill_dir(home, "x"))
                    self.assertEqual(ss.claude_skills_dir(home, env), installer.claude_skills_dir(home))
                    self.assertEqual(ss.resolve_lock_path(home, env)[0], installer.lock_file_path(home))

    # -- extra skill warning ----------------------------------------------------

    def test_extra_skill_warning(self):
        manifest, alpha, beta = self.setup_pair()
        extra = self.make_skill("extra-skill")  # a real canonical folder the manifest never mentions
        self.write_lock(self.lock_entries_for([alpha, beta, extra]))
        report = self.report(manifest)
        self.assertEqual(report["extra_skills"], [{"name": "extra-skill", "in_agents_dir": True, "in_lock": True}])
        self.assertEqual(report["unlocked_folders"], [])
        self.assertEqual(report["result"], "ok")  # a warning, not a failure
        result = self.run_cli(manifest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("extra-skill", result.stdout)

    def test_extra_skill_in_lock_only(self):
        manifest, alpha, beta = self.setup_pair()
        entries = self.lock_entries_for([alpha, beta])
        entries["ghost-skill"] = {"source": "github", "sourceType": "github", "sourceUrl": "https://example.invalid",
                                  "skillPath": "skills/ghost-skill", "skillFolderHash": "0" * 40,
                                  "installedAt": "2026-09-25T00:00:00Z", "updatedAt": "2026-09-25T00:00:00Z"}
        self.write_lock(entries)  # a lock entry with no folder on disk
        report = self.report(manifest)
        self.assertEqual(report["extra_skills"], [{"name": "ghost-skill", "in_agents_dir": False, "in_lock": True}])
        self.assertEqual(report["result"], "ok")

    # -- unlocked folders ---------------------------------------------------

    def test_unlocked_folder_reported_and_fails_its_lock_check(self):
        manifest, alpha, beta = self.setup_pair()
        entries = self.lock_entries_for([alpha, beta])
        del entries["alpha-skill"]  # the folder exists (make_skill wrote it) but the lock forgot it
        self.write_lock(entries)
        report = self.report(manifest)
        self.assertIn("alpha-skill", report["unlocked_folders"])
        self.assertEqual(self.skill_result(report, "alpha-skill")["lock"]["state"], "missing_entry")
        self.assertEqual(report["result"], "fail")

    # -- folder tree (informational) --------------------------------------------

    def populate_tree(self, name: str) -> Path:
        """A canonical folder with a regular file, an executable, a nested file and a symlink."""
        folder = self.home / ".agents" / "skills" / name
        (folder / "scripts" / "lib").mkdir(parents=True, exist_ok=True)
        (folder / "references").mkdir(exist_ok=True)
        (folder / "empty-dir").mkdir(exist_ok=True)  # git omits empty directories
        (folder / "references" / "notes.md").write_text("notes\n")
        # Git sorts the directory "scripts" as "scripts/", after this file; a plain name sort
        # would put the directory first and produce a different tree SHA.
        (folder / "scripts.md").write_text("index of scripts\n")
        tool = folder / "scripts" / "run.sh"
        tool.write_text("#!/bin/sh\necho run\n")
        tool.chmod(0o755)
        (folder / "scripts" / "lib" / "helper.py").write_text("VALUE = 1\n")
        (folder / "scripts" / "run-link.sh").symlink_to("run.sh")
        return folder

    def git_write_tree(self, folder: Path) -> str:
        """Git itself as the oracle: index the folder in a scratch repository, write its tree."""
        repo = self.tmp / "oracle-repo"
        shutil.rmtree(repo, ignore_errors=True)
        shutil.copytree(folder, repo, symlinks=True)
        git_env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        for args in (["init", "-q"], ["config", "core.fileMode", "true"], ["config", "core.symlinks", "true"],
                     ["add", "-A"]):
            subprocess.run(["git", "-C", str(repo), *args], check=True, env=git_env, capture_output=True)
        return subprocess.run(["git", "-C", str(repo), "write-tree"], check=True, env=git_env,
                              capture_output=True, text=True).stdout.strip()

    @unittest.skipUnless(shutil.which("git"), "git is the oracle for the tree hash")
    def test_git_tree_sha_matches_git_write_tree(self):
        skill = self.make_skill("tree-skill")
        folder = self.populate_tree("tree-skill")
        self.assertEqual(ss.git_tree_sha(folder), self.git_write_tree(folder))
        # A mode flip alone changes git's tree, and the recomputation follows it.
        (folder / "scripts" / "run.sh").chmod(0o644)
        self.assertEqual(ss.git_tree_sha(folder), self.git_write_tree(folder))
        self.assertTrue(skill["skill_md_sha256"])

    def test_folder_tree_states_are_reported_without_changing_the_result(self):
        manifest, alpha, beta = self.setup_pair()
        folder = self.populate_tree("alpha-skill")
        alpha["tree_sha"] = ss.git_tree_sha(folder)
        self.write_lock(self.lock_entries_for([alpha, beta]))
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "alpha-skill")["folder_tree"], {"state": "ok"})
        # beta keeps the fixture's placeholder tree_sha, so its on-disk tree cannot match.
        self.assertEqual(self.skill_result(report, "beta-skill")["folder_tree"], {"state": "drift"})
        self.assertEqual(report["result"], "ok")

        # What a skill's own `uv run` leaves behind: a project venv and bytecode caches.
        (folder / "scripts" / ".venv" / "bin").mkdir(parents=True)
        (folder / "scripts" / ".venv" / "pyvenv.cfg").write_text("home = /usr/bin\n")
        (folder / "scripts" / ".venv" / "bin" / "python").symlink_to("/usr/bin/python3")
        (folder / "scripts" / "lib" / "__pycache__").mkdir()
        (folder / "scripts" / "lib" / "__pycache__" / "helper.cpython-312.pyc").write_bytes(b"\x00pyc")
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "alpha-skill")["folder_tree"], {"state": "runtime_artifacts"})
        self.assertEqual(report["folder_trees"]["runtime_artifacts"], ["alpha-skill"])
        self.assertEqual(report["result"], "ok")

        # A pinned file rewritten in place (as `uv run` rewrote a pinned uv.lock) is drift.
        (folder / "references" / "notes.md").write_text("notes, rewritten after install\n")
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "alpha-skill")["folder_tree"], {"state": "drift"})
        self.assertEqual(report["folder_trees"]["drift"], ["alpha-skill", "beta-skill"])
        self.assertEqual(report["result"], "ok")
        self.assertIn("drift=alpha-skill,beta-skill", ss.render_text(report))

    def test_the_status_check_judges_content_as_the_installer_does(self):
        """Second GPT read of #1035 at 9a77a96e (~/.cache/ns2604-gpt-reads/fix1-pr1035-9a77a96e8/VERDICT.md, blocker 2): check_folder_tree still skipped a runtime-directory name whatever the entry was, so a regular
        `.venv` was `runtime_artifacts` for the status check and `local-modified` for the installer. A file or a link of that name is content (the add deletes it: vercel-labs/skills@7407f389 src/installer.ts
        L195); a real directory of a regenerated name is not. An empty directory or a special file stays invisible to this comparison, as to a git tree (the fixture's own `empty-dir`)."""
        manifest, alpha, beta = self.setup_pair()
        agents_skills = self.home / ".agents" / "skills"
        folder = self.populate_tree("alpha-skill")
        alpha["tree_sha"] = ss.git_tree_sha(folder)
        pristine = self.tmp / "pristine-alpha"
        shutil.copytree(folder, pristine, symlinks=True)
        cases = (("nothing added", lambda f: None, "ok"),
                 ("a real .venv directory with files", lambda f: ((f / ".venv").mkdir(), (f / ".venv" / "pyvenv.cfg").write_text("home = /usr/bin\n")), "runtime_artifacts"),
                 ("an empty .venv directory (invisible to a git tree)", lambda f: (f / ".venv").mkdir(), "ok"),
                 ("a regular file named .venv", lambda f: (f / ".venv").write_text("mine\n"), "drift"),
                 ("a regular file named .venv below scripts", lambda f: (f / "scripts" / ".venv").write_text("mine\n"), "drift"),
                 ("a link named .venv", lambda f: (f / ".venv").symlink_to("SKILL.md"), "drift"),
                 ("a link named node_modules", lambda f: (f / "node_modules").symlink_to(self.home, target_is_directory=True), "drift"),
                 ("a regular file named __pycache__ below scripts", lambda f: (f / "scripts" / "__pycache__").write_text("mine\n"), "drift"))
        for label, make, expected in cases:
            with self.subTest(entry=label):
                shutil.rmtree(folder, ignore_errors=True)
                shutil.copytree(pristine, folder, symlinks=True)
                make(folder)
                self.assertEqual(ss.check_folder_tree(agents_skills, alpha), {"state": expected})

    def test_folder_tree_missing_folder(self):
        manifest, alpha, beta = self.setup_pair()
        shutil.rmtree(self.home / ".agents" / "skills" / "beta-skill")
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "beta-skill")["folder_tree"], {"state": "missing"})
        self.assertEqual(report["folder_trees"]["missing"], ["beta-skill"])

    # -- --json shape -----------------------------------------------------------

    def test_json_shape(self):
        manifest, alpha, beta = self.setup_pair()
        result = self.run_cli(manifest, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(set(data), {"schema_version", "lock", "claude_settings", "codex_config", "skills",
                                     "extra_skills", "unlocked_folders", "budget", "folder_trees", "result"})
        self.assertEqual(set(data["folder_trees"]), {"ok", "runtime_artifacts", "drift", "missing", "unreadable", "held"})
        self.assertEqual(len(data["skills"]), 2)
        for skill in data["skills"]:
            self.assertEqual(set(skill), {"name", "pass", "canonical", "lock", "claude_link",
                                          "claude_listing", "codex_disable", "folder_tree"})
            self.assertEqual(set(skill["claude_link"]), {"state", "kind"})
        self.assertEqual(data["result"], "ok")
        # The CLI's JSON matches a direct call for the same fixture.
        self.assertEqual(self.report(manifest)["skills"], data["skills"])

    def test_json_and_text_agree_on_failure(self):
        manifest, alpha, beta = self.setup_pair()
        self.write_canonical("alpha-skill", b"drift\n")
        json_result = self.run_cli(manifest, "--json")
        text_result = self.run_cli(manifest)
        self.assertEqual(json_result.returncode, 1)
        self.assertEqual(text_result.returncode, 1)
        self.assertEqual(json.loads(json_result.stdout)["result"], "fail")
        self.assertIn("result: fail", text_result.stdout)

    # -- manifest loading / exit 2 --------------------------------------------

    def test_invalid_manifest_json_exits_2(self):
        path = self.tmp / "broken-manifest.json"
        path.write_text("{not valid json")
        with self.assertRaises(ss.ManifestError):
            ss.load_manifest(path)
        result = subprocess.run([sys.executable, str(SCRIPT), "--manifest", str(path), "--home", str(self.home)],
                                cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid manifest", result.stderr)

    def test_manifest_missing_required_key_exits_2(self):
        manifest, alpha, beta = self.setup_pair()
        del manifest["skills"][0]["tree_sha"]
        path = self.tmp / "manifest.json"
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ss.ManifestError):
            ss.load_manifest(path)
        result = subprocess.run([sys.executable, str(SCRIPT), "--manifest", str(path), "--home", str(self.home)],
                                cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 2)

    def test_manifest_missing_file_exits_2(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--manifest", str(self.tmp / "nope.json"), "--home", str(self.home)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 2)

    def test_real_manifest_loads_and_validates(self):
        real = ss.load_manifest(ROOT / "adoption" / "skills" / "manifest.json")
        names = {s["name"] for s in real["skills"]}
        self.assertIn("gh-fix-ci", names)
        self.assertGreaterEqual(len(names), 20)

    # -- value freedom --------------------------------------------------------

    def test_output_never_includes_settings_values_or_file_contents(self):
        manifest, alpha, beta = self.setup_pair()
        sentinel = "SENTINELSK" + os.urandom(12).hex()
        self.write_claude_settings({"beta-skill": "name-only"}, extra_env_sentinel=sentinel)
        self.write_codex_config(["beta-skill"], extra_sentinel=sentinel)
        self.write_canonical("alpha-skill", f"# drifted body carrying {sentinel}\n".encode())
        report = self.report(manifest)
        self.assertEqual(report["result"], "fail")
        dumped = json.dumps(report) + ss.render_text(report)
        self.assertNotIn(sentinel, dumped)
        self.assertNotIn("drifted body", dumped)
        for args in ((), ("--json",)):
            with self.subTest(args=args):
                result = self.run_cli(manifest, *args)
                self.assertNotIn(sentinel, result.stdout)
                self.assertNotIn(sentinel, result.stderr)
                self.assertNotIn("drifted body", result.stdout)

    def test_non_enum_claude_listing_value_is_never_echoed(self):
        """skillOverrides[name] is foreign input and may hold any string, not just the four
        documented states; an arbitrary one must never reach either output mode."""
        manifest, alpha, beta = self.setup_pair()
        foreign_value = "SENTINEL-NOT-AN-ENUM-VALUE-" + os.urandom(12).hex()
        self.write_claude_settings({"beta-skill": foreign_value})  # manifest pins beta at "name-only"
        report = self.report(manifest)
        self.assertEqual(self.skill_result(report, "beta-skill")["claude_listing"],
                         {"state": "mismatch", "actual": "invalid_value"})
        self.assertFalse(self.skill_result(report, "beta-skill")["pass"])
        dumped = json.dumps(report) + ss.render_text(report)
        self.assertNotIn(foreign_value, dumped)
        for args in ((), ("--json",)):
            with self.subTest(args=args):
                result = self.run_cli(manifest, *args)
                self.assertNotIn(foreign_value, result.stdout)
                self.assertNotIn(foreign_value, result.stderr)

    def test_non_string_claude_listing_value_does_not_crash(self):
        """overrides.get(name) can be an unhashable JSON value (a list/dict); the enum
        membership check must not raise TypeError on it."""
        manifest, alpha, beta = self.setup_pair()
        self.write_claude_settings({"beta-skill": ["nested", "nonsense"]})
        report = self.report(manifest)  # must not raise
        self.assertEqual(self.skill_result(report, "beta-skill")["claude_listing"],
                         {"state": "mismatch", "actual": "invalid_value"})
        result = self.run_cli(manifest, "--json")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("nested", result.stdout)

    def test_home_path_not_echoed_in_output(self):
        manifest, alpha, beta = self.setup_pair()
        result = self.run_cli(manifest)
        self.assertNotIn(str(self.home), result.stdout)
        self.assertNotIn(str(self.home), result.stderr)

    # -- --skills-bin / cli_version --------------------------------------------

    def test_cli_version_matches(self):
        manifest, alpha, beta = self.setup_pair()  # cli.version defaults to "1.7.0"
        binary = self.make_fake_bin("1.7.0")
        report = self.report(manifest, skills_bin=str(binary))
        self.assertEqual(report["cli_version"], {"invoked": True, "exit_code": 0, "output": "1.7.0",
                                                  "matches_manifest": True})
        self.assertEqual(report["result"], "ok")

    def test_cli_version_mismatch_fails_even_if_skills_pass(self):
        manifest, alpha, beta = self.setup_pair()
        binary = self.make_fake_bin("9.9.9")
        report = self.report(manifest, skills_bin=str(binary))
        self.assertFalse(report["cli_version"]["matches_manifest"])
        self.assertEqual(report["result"], "fail")
        result = self.run_cli(manifest, "--skills-bin", str(binary))
        self.assertEqual(result.returncode, 1)

    def test_cli_version_binary_not_found(self):
        manifest, alpha, beta = self.setup_pair()
        report = self.report(manifest, skills_bin=str(self.tmp / "does-not-exist"))
        self.assertEqual(report["cli_version"], {"invoked": False, "exit_code": None, "output": None,
                                                  "matches_manifest": False})
        self.assertEqual(report["result"], "fail")

    def test_skills_bin_omitted_leaves_cli_version_out_of_report(self):
        manifest, alpha, beta = self.setup_pair()
        report = self.report(manifest)
        self.assertNotIn("cli_version", report)

    # -- budget -----------------------------------------------------------------

    def test_budget_matches_and_reports_drift_without_failing(self):
        on1 = self.make_skill("on1", claude_listing="on", description_chars=300)
        on2 = self.make_skill("on2", claude_listing="on", description_chars=200)
        off1 = self.make_skill("off1", claude_listing="off", codex_enabled=False, description_chars=50)
        manifest = self.build_manifest(
            [on1, on2, off1],
            budget={"claude_on_description_chars": 500, "claude_on_cap": 8000,
                   "codex_enabled_description_chars": 500, "codex_catalog_description_chars": 500,
                   "codex_configured_budget_tokens": 6000, "codex_fallback_budget_chars": 8000})
        self.write_lock(self.lock_entries_for([on1, on2, off1]))
        for skill in (on1, on2, off1):
            self.write_claude_link(skill["name"])
        self.write_claude_settings({"off1": "off"})
        self.write_codex_config(["off1"])
        report = self.report(manifest)
        budget = report["budget"]
        self.assertEqual(budget["claude_on_description_chars"],
                         {"manifest": 500, "computed": 500, "matches_manifest": True})
        self.assertTrue(budget["claude_within_cap"])
        self.assertEqual(budget["codex_catalog_description_chars"],
                         {"manifest": 500, "computed": 500, "matches_manifest": True})
        self.assertEqual(report["result"], "ok")

        manifest["budget"]["claude_on_description_chars"] = 999  # drift the recorded sum only
        manifest["budget"]["codex_catalog_description_chars"] = 999
        drifted = self.report(manifest)
        self.assertFalse(drifted["budget"]["claude_on_description_chars"]["matches_manifest"])
        self.assertFalse(drifted["budget"]["codex_catalog_description_chars"]["matches_manifest"])
        self.assertEqual(drifted["result"], "ok")  # still informational only

    def test_budget_over_cap_is_reported_but_not_a_failure(self):
        big = self.make_skill("big-on", claude_listing="on", description_chars=9000)
        manifest = self.build_manifest([big], budget={"claude_on_description_chars": 9000, "claude_on_cap": 8000,
                                                       "codex_enabled_description_chars": 9000,
                                                       "codex_configured_budget_tokens": 100,
                                                       "codex_fallback_budget_chars": 8000})
        self.write_lock(self.lock_entries_for([big]))
        self.write_claude_link("big-on")
        self.write_claude_settings({})
        self.write_codex_config([])
        report = self.report(manifest)
        self.assertFalse(report["budget"]["claude_within_cap"])
        self.assertFalse(report["budget"]["codex_within_budget"])
        self.assertEqual(report["result"], "ok")

    def test_codex_catalog_is_estimated_as_render_rs_estimates_it_against_the_configured_token_budget(self):
        # openai/codex rust-v0.159.2 codex-rs/ext/skills/src/render.rs: each shown skill is the line
        # "- {name}: {description} (file: {path})" (L258-267), its description cut at 1,024 characters (L23), and a
        # token budget charges each line plus its newline at 4 bytes per token, rounded up (L154-160, L25;
        # utils/string/src/truncate.rs L71-74). A skill whose agents/openai.yaml sets allow_implicit_invocation:
        # false is left out of the catalog (ext/skills/src/provider/host.rs L147-148), and so is a disabled one.
        shown = self.make_skill("shown", description_chars=100)
        explicit_only = dict(self.make_skill("explicit-only", description_chars=40),
                             upstream_allow_implicit_invocation=False)
        disabled = self.make_skill("disabled", codex_enabled=False, description_chars=70)
        long_one = self.make_skill("long-one", description_chars=1500)
        skills = [shown, explicit_only, disabled, long_one]
        manifest = self.build_manifest(skills, budget={
            "claude_on_description_chars": 1710, "claude_on_cap": 10500, "codex_enabled_description_chars": 1640,
            "codex_catalog_description_chars": 1600, "codex_configured_budget_tokens": 6000,
            "codex_fallback_budget_chars": 8000})
        self.write_lock(self.lock_entries_for(skills))
        for skill in skills:
            self.write_claude_link(skill["name"])
        self.write_claude_settings({})
        self.write_codex_config([], disable_paths=[self.skill_md_path("disabled")])
        root = os.path.realpath(self.home / ".agents" / "skills")

        def line_tokens(name: str, chars: int) -> int:
            line = f"- {name}: {'d' * min(chars, 1024)} (file: {root}/{name}/SKILL.md)\n"
            return -(-len(line.encode("utf-8")) // 4)

        expected = line_tokens("shown", 100) + line_tokens("long-one", 1500)
        report = self.report(manifest)
        budget = report["budget"]
        self.assertEqual(budget["codex_catalog_skills"], 2)
        self.assertEqual(budget["codex_catalog_description_chars"],
                         {"manifest": 1600, "computed": 1600, "matches_manifest": True})
        self.assertEqual(budget["codex_catalog_estimated_tokens"], expected)
        self.assertEqual(budget["codex_configured_budget_tokens"], 6000)
        self.assertTrue(budget["codex_within_budget"])
        self.assertEqual(budget["codex_fallback_budget_chars"], 8000)  # metadata only, never the comparison
        self.assertNotIn("codex_within_cap", budget)
        self.assertEqual(report["result"], "ok")
        text = ss.render_text(report)
        self.assertIn(f"estimated_tokens={expected} configured_budget_tokens=6000 within_budget=True", text)
        manifest["budget"]["codex_configured_budget_tokens"] = expected - 1
        tight = self.report(manifest)
        self.assertFalse(tight["budget"]["codex_within_budget"])
        self.assertEqual(tight["result"], "ok")  # informational only

    def test_real_manifest_codex_catalog_fits_the_configured_token_budget(self):
        # The Codex template configures [skills] max_context_tokens = 6000; its 8,000-character fallback applies
        # only when the context window is unknown (render.rs L19-22 and L126-152 at rust-v0.159.2), so the
        # 10,048 Codex-enabled description characters are not measured against it.
        real = ss.load_manifest(ROOT / "adoption" / "skills" / "manifest.json")
        budget = ss.inspect(real, self.home, self.env)["budget"]
        self.assertEqual(budget["codex_configured_budget_tokens"], 6000)
        self.assertEqual(budget["codex_catalog_skills"], 28)  # the first-party claude-native-practice row added on 2026-10-10
        self.assertTrue(budget["codex_catalog_description_chars"]["matches_manifest"])
        self.assertLess(budget["codex_catalog_estimated_tokens"], 6000)
        self.assertTrue(budget["codex_within_budget"])

    def test_a_non_boolean_implicit_invocation_flag_is_a_manifest_error(self):
        manifest, alpha, beta = self.setup_pair()
        manifest["skills"][0]["upstream_allow_implicit_invocation"] = "false"
        path = self.tmp / "manifest.json"
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ss.ManifestError):
            ss.load_manifest(path)

    # -- held and Claude-Code-only copy entries (wave-2 skills ruling, change 6) ------------------------------------
    # A held skill is reported as held, never missing; a Claude-Code-only copy is checked in Claude Code's own folder.

    def held_manifest(self):
        manifest, alpha, beta = self.setup_pair()
        held = dict(self.make_skill("held-skill"), status="held", held_for="a measurement")
        shutil.rmtree(self.home / ".agents" / "skills" / "held-skill")  # not installed while held
        manifest["skills"].append(held)
        return manifest

    def copy_manifest(self, shared_too=False, as_link=False):
        manifest, alpha, beta = self.setup_pair()
        skill = dict(self.make_skill("copy-skill", codex_enabled=False), agents=["claude-code"], copy=True)
        canonical = self.home / ".agents" / "skills" / "copy-skill"
        claude_copy = self.home / ".claude" / "skills" / "copy-skill"
        if as_link:
            claude_copy.symlink_to(canonical, target_is_directory=True)
        else:
            shutil.copytree(canonical, claude_copy)
        if not shared_too and not as_link:
            shutil.rmtree(canonical)
        self.write_lock(self.lock_entries_for([alpha, beta, skill]))
        manifest["skills"].append(skill)
        return manifest

    def test_a_held_skill_is_reported_held_and_never_fails_the_run(self):
        report = self.report(self.held_manifest())
        held = self.skill_result(report, "held-skill")
        self.assertTrue(held["pass"])
        self.assertTrue(held["held"])
        self.assertFalse(held["present"])
        self.assertEqual(held["canonical"]["state"], "held")
        self.assertEqual(report["folder_trees"]["held"], ["held-skill"])
        self.assertEqual(report["result"], "ok")

    def test_a_held_skill_left_installed_is_reported_present(self):
        manifest = self.held_manifest()
        self.write_canonical("held-skill", b"# left from an earlier install\n")
        held = self.skill_result(self.report(manifest), "held-skill")
        self.assertTrue(held["pass"])
        self.assertTrue(held["present"])

    def test_a_claude_code_copy_passes_in_claude_codes_folder(self):
        report = self.report(self.copy_manifest())
        copy = self.skill_result(report, "copy-skill")
        self.assertTrue(copy["pass"], copy)
        self.assertEqual(copy["scope"], "claude-code copy")
        self.assertEqual(copy["claude_link"], {"state": "ok", "kind": "copy"})
        self.assertEqual(report["result"], "ok")

    def test_a_shared_folder_fails_a_claude_code_copy(self):
        shared = self.skill_result(self.report(self.copy_manifest(shared_too=True)), "copy-skill")
        self.assertFalse(shared["pass"])
        self.assertEqual(shared["codex_disable"]["state"], "shared_copy_present")

    def test_a_link_fails_a_claude_code_copy(self):
        linked = self.skill_result(self.report(self.copy_manifest(as_link=True)), "copy-skill")
        self.assertFalse(linked["pass"])
        self.assertEqual(linked["claude_link"]["state"], "is_a_symlink")

    def test_a_copy_entry_for_codex_is_a_manifest_error(self):
        manifest, alpha, beta = self.setup_pair()
        manifest["skills"][0]["copy"] = True
        path = self.tmp / "manifest.json"
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ss.ManifestError):
            ss.load_manifest(path)


if __name__ == "__main__":
    unittest.main()
