"""Tests for tools/adoption/install_skills.py against a fake 'skills' CLI.

The fake executable (write_fake_skills_bin) is a small stdlib-only Python
script written into its own temp directory per test. It emulates just enough
of the real `skills` CLI (v1.7.0) to exercise install_skills.py end to end:

  --version         prints the pinned version.
  add <url> --skill <name> -g -y -a claude-code codex
                    writes home/.agents/skills/<name>/SKILL.md and a relative
                    home/.claude/skills/<name> symlink from a per-test fixture
                    map keyed by skill name, then records a matching lock
                    entry (skillFolderHash = the fixture's tree_sha) at
                    home/.agents/.skill-lock.json or, when $XDG_STATE_HOME is
                    set, $XDG_STATE_HOME/skills/.skill-lock.json -- the same
                    rule install_skills.py itself applies when reading it
                    back, so a test that sets $XDG_STATE_HOME exercises both
                    sides of that contract at once.
  remove <name> -g -y -a claude-code codex
                    deletes the canonical folder, the symlink and the lock
                    entry. Per-fixture fault injection: retain_after_remove
                    keeps the named artifacts ("canonical", "lock",
                    "claude-link"), remove_exit fails the remove before it
                    deletes anything, remove_cannot_run leaves the binary
                    non-executable (1) or deletes it (2) after add, so the
                    rollback cannot start, lock_after_remove leaves the
                    lock "malformed" (truncated, entry kept) or "unreadable",
                    and, for add, no_claude_link (1) writes the canonical
                    folder and the lock entry but no Claude Code link, and
                    copy_fallback (1) writes a copy of the skill where the
                    link belongs, as the CLI does when it cannot symlink.
                    A set, non-blank $CLAUDE_CONFIG_DIR moves the global link
                    to $CLAUDE_CONFIG_DIR/skills, as in skills 1.7.0.
  Every global path (canonical folder, lock, link) is joined as skills 1.7.0's
  path.join joins it (node_join), so a ".." in HOME or $XDG_STATE_HOME lands
  under the normalized folder and the folder it passes through is never made.

Every invocation is also appended to calls.log next to the fake script
(independent of --home), so tests can assert not just the outcome but
whether, how often and with what arguments install_skills.py actually
invoked the binary -- in particular that an idempotent skip and a refused
local-modified skill never invoke it at all.

install_skills.py is run as a real subprocess (like tests/test_render_config.py's
`run()` helper) rather than imported, since the behavior under test is what it
does across process boundaries with a real (fake) CLI. $XDG_STATE_HOME is
stripped from the child environment by default so a variable already set on
the host running these tests can never redirect a lock-file write outside the
test's own temporary directory. Only the tests that name it set it again, each
inside its own temporary directory: the XDG tests (XdgStateHomeLockPathTests)
and the ".." cases built by dotdot_paths. The path unit test
test_global_paths_join_as_node_does_and_project_paths_are_unchanged also sets
it, in this process under mock.patch.dict, for paths it computes and never
writes. $CLAUDE_CONFIG_DIR is stripped the same way, and only the tests that
name it set it.
"""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "adoption" / "install_skills.py"
ADOPTION_MANIFEST = ROOT / "adoption" / "skills" / "manifest.json"
RUNTIME_MANIFEST = ROOT / "blueprints" / "runtime-workers" / "skills" / "manifest.json"
# A reused entry names main's adoption manifest and is matched there by its skill name.
ADOPTION_REF = "adoption/skills/manifest.json"
REUSE_PIN_KEYS = ("name", "source", "url", "ref", "path", "tree_sha", "skill_md_sha256",
                  "skill_md_bytes", "description_chars", "upstream_disable_model_invocation")


def load_installer_module():
    """The installer as a module, for load_manifest against a synthetic adoption manifest root."""
    spec = importlib.util.spec_from_file_location("install_skills_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PINNED_VERSION = "1.7.0"
INSTALL_HINT = "npm install --global --prefix <tools-root>/skills-1.7.0 skills@1.7.0"

# JavaScript trim()'s whitespace (ECMA-262 WhiteSpace and LineTerminator), used by the fake CLI;
# test_js_trim_chars_match_node checks it against node and against install_skills.JS_TRIM_CHARS.
JS_TRIM_CHARS = ("\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
                 "\u2028\u2029\u202f\u205f\u3000\ufeff")

FAKE_SKILLS_BIN_TEMPLATE = r'''#!/usr/bin/env python3
import json, os, sys, shutil, hashlib
from pathlib import Path

VERSION = "__VERSION__"
FIXTURES = __FIXTURES_JSON__
JS_TRIM_CHARS = __JS_TRIM_CHARS__

LOG = Path(__file__).resolve().parent / "calls.log"
with open(LOG, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\n")


def node_join(*parts: str) -> Path:
    # Node's POSIX path.join, which skills 1.7.0 builds every global path with (npm dist/cli.mjs L10 imports it
    # from "path"): the non-empty parts joined with / and normalized, so ".." collapses; a leading // becomes /.
    joined = os.path.normpath("/".join(part for part in parts if part))
    return Path("/" + joined.lstrip("/") if joined.startswith("//") else joined)


def lock_path(home: Path) -> Path:
    # dist/cli.mjs L3746-3750: a non-empty XDG_STATE_HOME, untrimmed, else os.homedir(), which is HOME verbatim,
    # each through path.join.
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return node_join(xdg, "skills", ".skill-lock.json")
    return node_join(str(home), ".agents", ".skill-lock.json")


def load_lock(path: Path) -> dict:
    if path.is_file():
        try:
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {"lockfileVersion": 3, "skills": {}}


def claude_skills_dir(target: Path, project: bool) -> Path:
    # skills@1.7.0 npm dist/cli.mjs L1398 and L1511: a set, non-blank CLAUDE_CONFIG_DIR moves the
    # global claude-code skills folder, trimmed by JavaScript's trim() and normalized by path.join;
    # project installs keep <project>/.claude/skills.
    if project:
        return target / ".claude" / "skills"
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "").strip(JS_TRIM_CHARS)
    return node_join(config_dir or str(target / ".claude"), "skills")


argv = sys.argv[1:]
if not argv:
    sys.exit(2)

if argv[0] == "--version":
    print(f"skills/{VERSION}")
    sys.exit(0)

home = Path(os.environ["HOME"])
project = "-g" not in argv
# Globally the canonical folder is path.join(os.homedir(), ".agents", "skills") (dist/cli.mjs L2208-2210), so every
# global path below starts from the normalized HOME, before anything is made or removed; a project uses its cwd.
target = Path.cwd() if project else node_join(str(home))

if argv[0] == "add":
    url = argv[1]
    name = argv[argv.index("--skill") + 1]
    if name not in FIXTURES:
        print(f"fake skills add: no fixture for {name!r}", file=sys.stderr)
        sys.exit(1)
    fixture = FIXTURES[name]
    copy = "--copy" in argv
    # --copy with one agent writes into that agent's own folder only (installSkillForAgent in the 1.7.0 bundle);
    # the fake supports the one form install_skills.py uses, a global copy for claude-code.
    skill_dir = claude_skills_dir(target, project) / name if copy else target / ".agents" / "skills" / name
    if skill_dir.is_symlink():
        skill_dir.unlink()
    elif skill_dir.exists():
        shutil.rmtree(skill_dir)
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(fixture["skill_md"], encoding="utf-8")
    for relative, content in fixture.get("files", {}).items():  # the rest of the pinned vendor folder
        (skill_dir / relative).parent.mkdir(parents=True, exist_ok=True)
        (skill_dir / relative).write_text(content, encoding="utf-8")
    if not copy and not fixture.get("no_claude_link") and (not project or "claude-code" in argv):
        link_dir = claude_skills_dir(target, project)
        link_dir.mkdir(parents=True, exist_ok=True)
        link = link_dir / name
        # skills@7407f389 installer.ts:254-264 removes an existing directory
        # before creating the alias. The wrapper must protect local content.
        if link.is_symlink():
            link.unlink()
        elif link.is_dir():
            shutil.rmtree(link)
        elif link.exists():
            link.unlink()
        if fixture.get("copy_fallback"):
            shutil.copytree(skill_dir, link)  # what the CLI does when it cannot create the symlink (installer.ts L428-440)
        else:
            os.symlink(os.path.relpath(skill_dir, link_dir), link)
    path = target / "skills-lock.json" if project else lock_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = load_lock(path)
    lock.setdefault("skills", {})[name] = {
        "source": "github", "sourceType": "github", "sourceUrl": url,
        "skillPath": fixture.get("path", name), "skillFolderHash": fixture["tree_sha"],
        "installedAt": "2026-09-25T00:00:00Z", "updatedAt": "2026-09-25T00:00:00Z",
    }
    if project:
        # Native v1.7.0 local-lock.ts:15-37: no skillFolderHash here.
        lock = {"version": 1, "skills": lock["skills"]}
        lock["skills"][name] = {
            "source": fixture.get("source", f"example/{name}"), "sourceType": "github",
            "ref": fixture.get("ref", "a" * 40),
            "skillPath": fixture.get("path", f"skills/{name}") + "/SKILL.md",
            "computedHash": hashlib.sha256(b"SKILL.md" + fixture["skill_md"].encode()).hexdigest(),
        }
    path.write_text(json.dumps(lock))
    if fixture.get("remove_cannot_run") == 2:
        os.remove(__file__)  # The rollback's exec then fails with FileNotFoundError: the binary is gone.
    elif fixture.get("remove_cannot_run"):
        # The rollback's exec then fails with PermissionError, an OSError, as for a binary that cannot run.
        os.chmod(__file__, 0o644)
    sys.exit(0)

if argv[0] == "remove":
    name = argv[1]
    # Synthetic fault injection for independently checking cleanup artifacts.
    retained = FIXTURES.get(name, {}).get("retain_after_remove", [])
    if FIXTURES.get(name, {}).get("remove_exit"):
        print(f"fake skills remove: simulated failure for {name!r}", file=sys.stderr)
        sys.exit(FIXTURES[name]["remove_exit"])
    if project:
        # Relevant subset of skills@7407f389 remove.ts:209-333. A same-named
        # OpenClaw source directory is a removal target even if not detected.
        agent_dirs = {"universal": ".agents/skills", "codex": ".agents/skills",
                      "claude-code": ".claude/skills", "cursor": ".cursor/skills",
                      "openclaw": "skills"}
        targets = argv[argv.index("-a") + 1:] if "-a" in argv else list(agent_dirs)
        canonical = target / ".agents" / "skills" / name
        for agent in targets:
            path = target / agent_dirs[agent] / name
            if path == canonical:
                continue
            if agent == "claude-code" and "claude-link" in retained:
                continue
            if path.is_symlink():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        # Fixture detection is deliberately limited to a Codex home marker.
        # remove.ts:293-310 retains canonical data and lock for another agent.
        if "codex" not in targets and (home / ".codex").exists() and canonical.exists():
            sys.exit(0)
    if "canonical" not in retained:
        shutil.rmtree(target / ".agents" / "skills" / name, ignore_errors=True)
    link = claude_skills_dir(target, project) / name
    if not project and "claude-link" not in retained and (link.is_symlink() or link.exists()):
        if link.is_dir() and not link.is_symlink():
            shutil.rmtree(link)  # a Claude Code copy (--copy), not a link
        else:
            link.unlink()
    path = target / "skills-lock.json" if project else lock_path(home)
    lock = load_lock(path)
    # lock_after_remove: "malformed" leaves a truncated lock that still holds the entry;
    # "unreadable" removes the entry and then makes the lock unreadable.
    fault = FIXTURES.get(name, {}).get("lock_after_remove")
    if "lock" not in retained and fault != "malformed":
        lock.get("skills", {}).pop(name, None)
    text = json.dumps(lock)
    path.write_text(text[:-1] if fault == "malformed" else text)
    if fault == "unreadable":
        os.chmod(path, 0)
    sys.exit(0)

print(f"fake skills: unknown subcommand {argv[0]!r}", file=sys.stderr)
sys.exit(2)
'''


def write_fake_skills_bin(directory: Path, fixtures: dict, version: str = PINNED_VERSION) -> Path:
    text = FAKE_SKILLS_BIN_TEMPLATE.replace("__VERSION__", version).replace(
        "__FIXTURES_JSON__", json.dumps(fixtures)).replace("__JS_TRIM_CHARS__", ascii(JS_TRIM_CHARS))
    path = directory / "skills"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def calls_log(fake_bin: Path) -> list[list[str]]:
    log = fake_bin.parent / "calls.log"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_skill(name: str, skill_md: str, tree_sha: str, codex_enabled: bool = True) -> dict:
    return {
        "name": name,
        "source": f"example/{name}",
        "url": f"https://github.com/example/{name}/tree/{'a' * 40}/skills/{name}",
        "ref": "a" * 40,
        "path": f"skills/{name}",
        "tree_sha": tree_sha,
        "skill_md_sha256": sha256_text(skill_md),
        "skill_md_bytes": len(skill_md.encode("utf-8")),
        "description_chars": 10,
        "upstream_disable_model_invocation": False,
        "license": "MIT",
        "official": False,
        "audits": {"gen_agent_trust_hub": "Pass", "socket": "Pass", "snyk": "Pass",
                   "url": f"https://skills.sh/example/{name}", "checked_at": "2026-09-25"},
        "status": "trial",
        "gap": "test fixture",
        "claude_listing": "on",
        "codex_enabled": codex_enabled,
    }


def make_manifest(skills: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "kind": "skills_trial_manifest",
        "checked_at": "2026-09-25",
        "cli": {
            "package": "skills",
            "version": PINNED_VERSION,
            "source": "https://github.com/vercel-labs/skills/tree/v1.7.0",
            "install": INSTALL_HINT,
            "env": {"DISABLE_TELEMETRY": "1"},
            "lock_path": "$XDG_STATE_HOME/skills/.skill-lock.json when XDG_STATE_HOME is set, "
                         "else ~/.agents/.skill-lock.json",
        },
        "skills": skills,
    }


def tree_sha(label: str) -> str:
    """A deterministic 40-hex string distinct per label; not a real git tree SHA."""
    return hashlib.sha1(label.encode("utf-8")).hexdigest()


def pinned_tree_sha(files: dict) -> str:
    """The git tree SHA of a folder holding these files (path -> text): what the manifest's tree_sha is for a pinned vendor folder, hashed by the repository's own function."""
    sys.path.insert(0, str(ROOT))
    from scripts import skills_status
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for relative, text in files.items():
            (folder / relative).parent.mkdir(parents=True, exist_ok=True)
            (folder / relative).write_text(text, encoding="utf-8")
        return skills_status.git_tree_sha(folder)


class InstallSkillsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.home = self.tmp_path / "home"
        self.home.mkdir()
        self.bin_dir = self.tmp_path / "bin"
        self.bin_dir.mkdir()

    def write_manifest(self, skills: list[dict]) -> Path:
        path = self.tmp_path / "manifest.json"
        path.write_text(json.dumps(make_manifest(skills)))
        return path

    def run_install(self, manifest: Path, *extra: str, env: dict | None = None,
                    fake_bin: Path | None = None, home_arg: str | None = None) -> subprocess.CompletedProcess:
        full_env = dict(os.environ)
        full_env.pop("XDG_STATE_HOME", None)  # never let the host redirect the lock write
        full_env.pop("CLAUDE_CONFIG_DIR", None)  # nor the global Claude link
        full_env.update(env or {})
        args = [sys.executable, str(SCRIPT), "--manifest", str(manifest), "--home", home_arg or str(self.home)]
        if fake_bin is not None:
            args += ["--skills-bin", str(fake_bin)]
        args += list(extra)
        return subprocess.run(args, capture_output=True, text=True, check=False, env=full_env, timeout=60)

    def lock_data(self, xdg_state_home: Path | None = None) -> dict:
        path = (Path(xdg_state_home) / "skills" / ".skill-lock.json") if xdg_state_home \
            else (self.home / ".agents" / ".skill-lock.json")
        return json.loads(path.read_text()) if path.is_file() else {}

    def dotdot_paths(self, label: str, via: str) -> tuple[dict | None, str | None, Path]:
        """(env, --home argument, lock) with a ".." through the missing folder tmp/missing in --home ("home") or in
        XDG_STATE_HOME ("xdg"); the home is tmp/<label>. skills 1.7.0 joins both with path.join, which collapses
        the ".." (dist/cli.mjs L2208-2210, L3746-3750), so the returned lock is the normalized path and tmp/missing
        is never made. pathlib keeps the "..", and a path through a missing folder does not exist."""
        missing = self.tmp_path / "missing"
        if via == "home":
            return None, str(missing / ".." / label), self.tmp_path / label / ".agents" / ".skill-lock.json"
        state = f"state-{label}"
        return ({"XDG_STATE_HOME": str(missing / ".." / state)}, str(self.tmp_path / label),
                self.tmp_path / state / "skills" / ".skill-lock.json")

    def assert_fake_cli_made_no_missing_folder(self) -> None:
        """A fake-CLI fidelity check, not a check of install_skills.py, which makes no path itself: like skills
        1.7.0, whose path.join collapses a ".." before any mkdir, the fake CLI never makes tmp/missing."""
        self.assertFalse((self.tmp_path / "missing").exists())


class DryRunTests(InstallSkillsTestCase):
    def test_dry_run_changes_nothing_and_exits_zero(self):
        skill = make_skill("fresh-skill", "# Fresh\n", tree_sha("fresh"))
        fake_bin = write_fake_skills_bin(self.bin_dir, {"fresh-skill": {"skill_md": "# Fresh\n",
                                                                        "tree_sha": tree_sha("fresh")}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, "--dry-run", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("would run", result.stdout)
        self.assertFalse((self.home / ".agents").exists())
        self.assertFalse((self.home / ".claude").exists())
        self.assertEqual(calls_log(fake_bin), [["--version"]])  # only the version check ran


class ProjectInstallTests(InstallSkillsTestCase):
    """CLI seam: project cwd/lock, source-tree verification and scoped rollback.

    Fake gh returns independently selected source-tree metadata. These are
    integration fixtures, not a native CLI run or upstream acceptance.
    """

    def setUp(self):
        super().setUp()
        self.project = self.tmp_path / "project with spaces"
        self.project.mkdir()
        self.content = "# Project skill\n"
        self.skill = make_skill("project-skill", self.content, pinned_tree_sha({"SKILL.md": self.content}))  # a real tree: the repairing add judges the canonical folder against it
        self.manifest = self.write_manifest([self.skill])
        self.fake_bin = write_fake_skills_bin(self.bin_dir, {
            "project-skill": {"skill_md": self.content, "tree_sha": self.skill["tree_sha"]}})
        self.write_gh_tree(self.skill["tree_sha"])

    def write_gh_tree(self, sha):
        data = {"truncated": False, "tree": [{"path": self.skill["path"], "type": "tree", "sha": sha}]}
        endpoint = f"repos/{self.skill['source']}/git/trees/{self.skill['ref']}?recursive=1"
        self.write_gh_responses({endpoint: (0, json.dumps(data))})

    def write_gh_responses(self, responses):
        gh = self.bin_dir / "gh"
        gh.write_text("""#!/usr/bin/env python3
import json, sys
from pathlib import Path
responses = """ + repr(responses) + """
directory = Path(__file__).resolve().parent
calls = directory / "calls.log"
mutations = [json.loads(line) for line in calls.read_text().splitlines()
             if json.loads(line)[0] in ("add", "remove")] if calls.exists() else []
with (directory / "gh_calls.log").open("a") as log:
    log.write(json.dumps({"args": sys.argv[1:], "mutations": mutations}) + "\\n")
code, response = responses[sys.argv[2]]
print(response)
sys.exit(code)
""")
        gh.chmod(0o755)

    def install(self, *extra):
        return self.run_install(
            self.manifest, "--project-dir", str(self.project), "--agent", "universal", *extra,
            fake_bin=self.fake_bin,
            env={"PATH": str(self.bin_dir) + os.pathsep + os.environ["PATH"]})

    def test_project_install_uses_project_cwd_local_lock_and_explicit_agent(self):
        result = self.install("--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "installed"})
        self.assertEqual((self.project / ".agents/skills/project-skill/SKILL.md").read_text(), self.content)
        self.assertFalse((self.home / ".agents").exists())
        lock = json.loads((self.project / "skills-lock.json").read_text())
        self.assertNotIn("skillFolderHash", lock["skills"]["project-skill"])
        self.assertEqual(calls_log(self.fake_bin)[1], [
            "add", self.skill["url"], "--skill", "project-skill", "-y", "-a", "universal"])
        again = self.install("--json")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(json.loads(again.stdout)["skills"], {"project-skill": "ok"})
        self.assertEqual([c[0] for c in calls_log(self.fake_bin)], ["--version", "add", "--version"])

    def test_check_only_reports_missing_without_installing(self):
        result = self.install("--check-only", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "missing-or-drifted"})
        self.assertEqual(calls_log(self.fake_bin), [["--version"]])
        self.assertFalse((self.project / "skills-lock.json").exists())

    def test_project_preflight_failure_on_later_source_changes_nothing(self):
        projects = self.project
        for same_source in (False, True):
            for failure in ("unavailable", "invalid-json", "truncated"):
                with self.subTest(same_source=same_source, failure=failure):
                    self.project = projects / f"{same_source}-{failure}"
                    self.project.mkdir()
                    second = make_skill("second-skill", "# Second\n", tree_sha("second"))
                    if same_source:
                        second["source"] = self.skill["source"]
                        second["ref"] = "b" * 40
                        second["url"] = f"https://github.com/{second['source']}/tree/{second['ref']}/{second['path']}"
                    self.manifest = self.write_manifest([self.skill, second])
                    self.fake_bin = write_fake_skills_bin(self.bin_dir, {
                        s["name"]: {"skill_md": content, "tree_sha": s["tree_sha"],
                                    "source": s["source"], "ref": s["ref"], "path": s["path"]}
                        for s, content in ((self.skill, self.content), (second, "# Second\n"))})
                    failed_response = {"unavailable": (1, "fixture API failure"),
                                       "invalid-json": (0, "not JSON"),
                                       "truncated": (0, json.dumps({"truncated": True, "tree": []}))}[failure]
                    self.write_gh_responses({
                        f"repos/{self.skill['source']}/git/trees/{self.skill['ref']}?recursive=1":
                            (0, json.dumps({"tree": [{"path": self.skill["path"], "type": "tree", "sha": self.skill["tree_sha"]}]})),
                        f"repos/{second['source']}/git/trees/{second['ref']}?recursive=1": failed_response})
                    before = calls_log(self.fake_bin)
                    result = self.install()
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("unverified (gh unavailable)" if failure == "unavailable" else "unverified", result.stderr)
                    self.assertNotIn("did not match", result.stderr)
                    self.assertNotIn("rolled back", result.stderr)
                    self.assertEqual(calls_log(self.fake_bin)[len(before):], [["--version"]])
                    self.assertEqual(list(self.project.iterdir()), [])

    def test_project_fetches_each_selected_source_ref_before_any_add(self):
        second = make_skill("second-skill", "# Second\n", tree_sha("second"))
        second["source"] = self.skill["source"]
        second["url"] = f"https://github.com/{second['source']}/tree/{second['ref']}/{second['path']}"
        third = make_skill("third-skill", "# Third\n", tree_sha("third"))
        self.manifest = self.write_manifest([self.skill, second, third])
        self.fake_bin = write_fake_skills_bin(self.bin_dir, {
            s["name"]: {"skill_md": content, "tree_sha": s["tree_sha"],
                        "source": s["source"], "ref": s["ref"], "path": s["path"]}
            for s, content in ((self.skill, self.content), (second, "# Second\n"), (third, "# Third\n"))})
        responses = {}
        for group in ((self.skill, second), (third,)):
            skill = group[0]
            responses[f"repos/{skill['source']}/git/trees/{skill['ref']}?recursive=1"] = (
                0, json.dumps({"tree": [{"path": s["path"], "type": "tree", "sha": s["tree_sha"]} for s in group]}))
        self.write_gh_responses(responses)
        result = self.install("--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        gh_calls = [json.loads(line) for line in (self.bin_dir / "gh_calls.log").read_text().splitlines()]
        self.assertEqual([c["args"] for c in gh_calls], [["api", endpoint] for endpoint in responses])
        self.assertTrue(all(not call["mutations"] for call in gh_calls), gh_calls)
        self.assertEqual(json.loads(result.stdout)["skills"],
                         {"project-skill": "installed", "second-skill": "installed", "third-skill": "installed"})

    def test_project_tree_mismatch_is_refused_before_any_add(self):
        # A rollback after add cannot be relied on: on a host where Codex is detected, the native remove keeps
        # the canonical folder and lock for it (skills@7407f389 remove.ts:293-310, agents.ts:224-232).
        (self.home / ".codex").mkdir()
        other_path = {"truncated": False, "tree": [{"path": "skills/other", "type": "tree", "sha": tree_sha("x")}]}
        endpoint = f"repos/{self.skill['source']}/git/trees/{self.skill['ref']}?recursive=1"
        for label, response in (("different tree", None), ("path absent at the pinned ref", other_path)):
            with self.subTest(label):
                if response is None:
                    self.write_gh_tree(tree_sha("other"))
                else:
                    self.write_gh_responses({endpoint: (0, json.dumps(response))})
                before = calls_log(self.fake_bin)
                for mode in ((), ("--dry-run",), ("--check-only",)):
                    result = self.install(*mode)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("pinned source tree differs from the manifest tree_sha", result.stderr)
                    self.assertIn("project-skill", result.stderr)
                self.assertEqual(calls_log(self.fake_bin)[len(before):], [["--version"]] * 3)  # no add, no remove
                self.assertEqual(list(self.project.iterdir()), [])

    def write_drifting_fake_bin(self, **extra):
        """Installs different SKILL.md bytes than the pin, so verification after add fails and rolls back."""
        self.fake_bin = write_fake_skills_bin(self.bin_dir, {"project-skill": {
            "skill_md": "# Drifted bytes\n", "tree_sha": self.skill["tree_sha"], **extra}})

    def test_project_rollback_preserves_other_agents_and_source_directories(self):
        self.write_drifting_fake_bin()
        for agent, targets in (("universal", ["universal"]),
                               ("codex", ["universal", "codex"]),
                               ("claude-code", ["universal", "claude-code"])):
            with self.subTest(agent=agent):
                sentinels = []
                for directory in ("skills", ".cursor/skills"):
                    sentinel = self.project / directory / "project-skill" / "LOCAL.md"
                    sentinel.parent.mkdir(parents=True, exist_ok=True)
                    sentinel.write_text("owned before this run\n")
                    sentinels.append(sentinel)
                result = self.install("--agent", agent)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("rolled back", result.stderr)
                calls = calls_log(self.fake_bin)
                self.assertEqual(calls[-1], ["remove", "project-skill", "-y", "-a", *targets])
                self.assertEqual(calls[-2][calls[-2].index("-a"):], calls[-1][calls[-1].index("-a"):])
                for sentinel in sentinels:
                    self.assertEqual(sentinel.read_text(), "owned before this run\n")
                self.assertFalse((self.project / ".agents/skills/project-skill").exists())
                link = self.project / ".claude/skills/project-skill"
                self.assertFalse(link.exists() or link.is_symlink())
                self.assertNotIn("project-skill", json.loads((self.project / "skills-lock.json").read_text())["skills"])

    def test_project_rollback_reports_canonical_retained_for_another_agent(self):
        (self.home / ".codex").mkdir()
        self.write_drifting_fake_bin()
        result = self.install("--agent", "claude-code", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "error"})
        self.assertIn("rollback retained, in use by another agent", result.stderr)
        self.assertEqual(calls_log(self.fake_bin)[-1],
                         ["remove", "project-skill", "-y", "-a", "universal", "claude-code"])
        self.assertTrue((self.project / ".agents/skills/project-skill").is_dir())
        self.assertIn("project-skill", json.loads((self.project / "skills-lock.json").read_text())["skills"])
        link = self.project / ".claude/skills/project-skill"
        self.assertFalse(link.exists() or link.is_symlink())
        self.assertEqual([call[0] for call in calls_log(self.fake_bin)], ["--version", "add", "remove"])

    def test_project_rollback_checks_each_artifact_independently(self):
        projects = self.project
        for artifact in ("canonical", "lock", "claude-link"):
            with self.subTest(artifact=artifact):
                # A retained drifted copy is local content to the next run, so each case gets its own project.
                self.project = projects / artifact
                self.project.mkdir()
                self.write_drifting_fake_bin(retain_after_remove=[artifact])
                result = self.install("--agent", "claude-code", "--json")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "error"})
                self.assertNotIn("rolled back", result.stderr)
                canonical = self.project / ".agents/skills/project-skill"
                link = self.project / ".claude/skills/project-skill"
                lock = json.loads((self.project / "skills-lock.json").read_text())["skills"]
                self.assertEqual(canonical.exists(), artifact == "canonical")
                self.assertEqual("project-skill" in lock, artifact == "lock")
                self.assertEqual(link.is_symlink(), artifact == "claude-link")
                if artifact == "claude-link":
                    self.assertFalse(link.exists(), "dangling Claude link must still count as retained")

    def test_project_rollback_with_a_malformed_lock_is_error_could_not_be_verified(self):
        self.write_drifting_fake_bin(lock_after_remove="malformed")
        result = self.install("--agent", "claude-code", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "error"})
        self.assertIn("project-skill: error: rollback could not be verified (exit 0; read-back failed: ",
                      result.stderr)
        self.assertNotIn("rolled back", result.stderr)
        self.assertFalse((self.project / ".agents/skills/project-skill").exists())

    def test_wrong_source_ref_or_path_is_not_accepted_even_when_bytes_match(self):
        for field, value in (("source", "other/repo"), ("ref", "b" * 40), ("path", "elsewhere/skill")):
            with self.subTest(field=field):
                self.fake_bin = write_fake_skills_bin(self.bin_dir, {"project-skill": {
                    "skill_md": self.content, "tree_sha": self.skill["tree_sha"], field: value}})
                result = self.install()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("rolled back", result.stderr)

    def test_project_byte_mismatch_rolls_back(self):
        self.fake_bin = write_fake_skills_bin(self.bin_dir, {"project-skill": {
            "skill_md": "# Wrong content\n", "tree_sha": self.skill["tree_sha"]}})
        result = self.install()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("rolled back", result.stderr)

    def test_project_dry_run_and_unlocked_local_refusal_are_nonmutating(self):
        result = self.install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.project / ".agents").exists())
        folder = self.project / ".agents/skills/project-skill"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("local content")
        result = self.install()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("local-modified", result.stderr)
        self.assertEqual((folder / "SKILL.md").read_text(), "local content")
        self.assertEqual(calls_log(self.fake_bin), [["--version"], ["--version"]])

    def test_explicit_project_claude_target_keeps_canonical_directory(self):
        result = self.install("--agent", "claude-code")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(calls_log(self.fake_bin)[1][-3:], ["-a", "universal", "claude-code"])
        again = self.install("--agent", "claude-code", "--json")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(json.loads(again.stdout)["skills"], {"project-skill": "ok"})
        self.assertEqual([c[0] for c in calls_log(self.fake_bin)], ["--version", "add", "--version"])

    def test_project_claude_directory_is_protected_with_or_without_lock(self):
        projects = self.project
        for locked in (False, True):
            for content_kind in ("local", "matching", "missing"):
                with self.subTest(locked=locked, content=content_kind):
                    self.project = projects / f"locked-{locked}-{content_kind}"
                    self.project.mkdir()
                    if locked:
                        first = self.install()
                        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                    local = self.project / ".claude/skills/project-skill"
                    local.mkdir(parents=True)
                    (local / "LOCAL.md").write_text("hand-written support file\n")
                    if content_kind != "missing":
                        (local / "SKILL.md").write_text(self.content if content_kind == "matching" else "local edits\n")
                    before = calls_log(self.fake_bin)
                    for mode in ((), ("--dry-run",), ("--check-only",)):
                        result = self.install("--agent", "claude-code", "--json", *mode)
                        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                        self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "local-modified"})
                        self.assertFalse(local.is_symlink())
                        self.assertEqual((local / "LOCAL.md").read_text(), "hand-written support file\n")
                    self.assertEqual(calls_log(self.fake_bin)[len(before):], [["--version"]] * 3)
                    forced = self.install("--agent", "claude-code", "--force", "--json")
                    self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
                    self.assertEqual(json.loads(forced.stdout)["skills"], {"project-skill": "installed"})
                    self.assertTrue(local.is_symlink())
                    self.assertEqual(local.resolve(), (self.project / ".agents/skills/project-skill").resolve())
                    self.assertEqual((local / "SKILL.md").read_text(), self.content)

    def test_project_claude_foreign_symlink_requires_force(self):
        projects = self.project
        for locked in (False, True):
            with self.subTest(locked=locked):
                self.project = projects / f"locked-{locked}"
                self.project.mkdir()
                if locked:
                    self.assertEqual(self.install().returncode, 0)
                local = self.project / ".claude/skills/project-skill"
                local.parent.mkdir(parents=True)
                foreign = self.project / "hand-written-skill"
                local.symlink_to(foreign)  # dangling foreign link still belongs to the user
                before = calls_log(self.fake_bin)
                result = self.install("--agent", "claude-code", "--json")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["skills"], {"project-skill": "local-modified"})
                self.assertEqual(local.readlink(), foreign)
                self.assertEqual(calls_log(self.fake_bin)[len(before):], [["--version"]])
                forced = self.install("--agent", "claude-code", "--force")
                self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
                self.assertEqual(local.resolve(), (self.project / ".agents/skills/project-skill").resolve())

    def test_project_paths_the_cli_writes_must_stay_inside_the_project(self):
        # skills@7407f389 installer.ts:388 recreates <cwd>/.agents/skills/<name> with rm and mkdir
        # (installer.ts:193-200), and remove.ts:296 keeps it for another detected agent. Through a symlink,
        # or with --project-dir at --home, a project install would recreate and then roll back a global
        # skill and leave the global lock stale. Each case is refused before any skills or gh call.
        global_skills = self.home / ".agents" / "skills"
        (global_skills / "project-skill").mkdir(parents=True)
        (global_skills / "project-skill" / "SKILL.md").write_text(self.content)  # matching bytes
        global_lock = self.home / ".agents" / ".skill-lock.json"
        global_lock.write_text(json.dumps({"lockfileVersion": 3, "skills": {}}))
        (self.home / ".claude" / "skills" / "project-skill").mkdir(parents=True)
        projects, gh_log = self.project, self.bin_dir / "gh_calls.log"
        cases = (
            ("universal", ".agents/skills", global_skills),
            ("codex", ".agents", self.home / ".agents"),
            ("universal", ".claude/skills", self.home / ".claude" / "skills"),
            ("universal", "skills-lock.json", global_lock),
            ("universal", ".agents/skills", "inside"),  # a symlinked target directory, even one inside
            ("universal", ".agents/skills/project-skill", global_skills / "project-skill"),
            ("claude-code", ".claude/skills/project-skill", self.home / ".claude" / "skills" / "project-skill"),
            ("universal", None, None),  # --project-dir is --home itself
        )
        for index, (agent, relative, target) in enumerate(cases):
            with self.subTest(agent=agent, path=relative, target=str(target)):
                if relative is None:
                    self.project = self.home
                else:
                    self.project = projects / f"case-{index}"
                    link = self.project / relative
                    link.parent.mkdir(parents=True, exist_ok=True)
                    if target == "inside":
                        target = self.project / "elsewhere"
                        target.mkdir()
                    link.symlink_to(target)
                calls_before = calls_log(self.fake_bin)
                gh_before = gh_log.read_text() if gh_log.exists() else ""
                for mode in ((), ("--dry-run",), ("--check-only",)):
                    result = self.install("--agent", agent, *mode)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("project containment", result.stderr)
                self.assertEqual(calls_log(self.fake_bin), calls_before)  # not even --version ran
                self.assertEqual(gh_log.read_text() if gh_log.exists() else "", gh_before)
                self.assertEqual((global_skills / "project-skill" / "SKILL.md").read_text(), self.content)
                self.assertEqual(json.loads(global_lock.read_text()), {"lockfileVersion": 3, "skills": {}})
                self.assertFalse((self.home / "skills-lock.json").exists())

    def test_project_dir_is_compared_with_the_home_the_cli_joins(self):
        # The CLI's global home is path.join(HOME) (dist/cli.mjs L2208-2210), so --home tmp/link/../h is tmp/h, the
        # project. pathlib keeps the "..": through the symlink link -> x/y it names tmp/x/h. A ".." after a real
        # directory (the control) names tmp/h either way. Each is refused before any skills or gh call.
        (self.tmp_path / "x" / "y").mkdir(parents=True)
        (self.tmp_path / "link").symlink_to("x/y", target_is_directory=True)
        (self.tmp_path / "real").mkdir()
        path_env = {"PATH": str(self.bin_dir) + os.pathsep + os.environ["PATH"]}
        gh_log = self.bin_dir / "gh_calls.log"
        self.project = self.tmp_path / "h"
        self.project.mkdir()
        for via in ("real", "link"):
            with self.subTest(home=f"{via}/../h"):
                calls_before = calls_log(self.fake_bin)
                gh_before = gh_log.read_text() if gh_log.exists() else ""
                result = self.run_install(self.manifest, "--project-dir", str(self.project), "--agent", "universal",
                                          fake_bin=self.fake_bin, env=path_env,
                                          home_arg=str(self.tmp_path / via / ".." / "h"))
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("project containment: --project-dir is --home", result.stderr)
                self.assertEqual(calls_log(self.fake_bin), calls_before)  # not even --version ran
                self.assertEqual(gh_log.read_text() if gh_log.exists() else "", gh_before)
                self.assertFalse((self.project / ".agents").exists())
        # tmp/x/h, which pathlib names for link/../h, is not the CLI's global home: an ordinary project.
        self.project = self.tmp_path / "x" / "h"
        self.project.mkdir()
        result = self.run_install(self.manifest, "--project-dir", str(self.project), "--agent", "universal",
                                  "--dry-run", fake_bin=self.fake_bin, env=path_env,
                                  home_arg=str(self.tmp_path / "link" / ".." / "h"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("project containment", result.stderr)
        self.assertIn("would run", result.stdout)

    def test_adding_claude_target_to_existing_universal_install_creates_its_link(self):
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        link = self.project / ".claude/skills/project-skill"
        self.assertFalse(link.exists())
        check = self.install("--agent", "claude-code", "--check-only")
        self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
        second = self.install("--agent", "claude-code")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertTrue(link.is_symlink())

    def test_pruned_skills_are_not_reinstalled(self):
        self.skill["status"] = "pruned"
        self.manifest = self.write_manifest([self.skill])
        result = self.install("--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {})
        self.assertEqual(calls_log(self.fake_bin), [["--version"]])

    def test_only_naming_a_pruned_skill_reports_it_as_pruned_not_unknown(self):
        self.skill["status"] = "pruned"
        self.manifest = self.write_manifest([self.skill])
        result = self.install("--only", "project-skill")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("pruned --only name(s)", result.stderr)
        self.assertIn("project-skill", result.stderr)
        self.assertNotIn("unknown", result.stderr)
        self.assertEqual(calls_log(self.fake_bin), [])  # rejected before even the version check

    def test_relative_binary_is_resolved_before_changing_to_project_directory(self):
        result = self.run_install(
            self.manifest, "--project-dir", str(self.project), "--agent", "universal",
            fake_bin=Path(os.path.relpath(self.fake_bin, Path.cwd())),
            env={"PATH": str(self.bin_dir) + os.pathsep + os.environ["PATH"]})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.project / ".agents/skills/project-skill/SKILL.md").is_file())

    def test_global_default_add_arguments_remain_exact(self):
        result = self.run_install(self.manifest, fake_bin=self.fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(calls_log(self.fake_bin)[1], ["add", self.skill["url"], "--skill", "project-skill",
                                                       "-g", "-y", "-a", "claude-code", "codex"])

    def test_help_describes_project_authentication_and_scoped_global_rollback(self):
        result = self.install("--help")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        help_text = " ".join(result.stdout.split())
        self.assertIn("gh uses its own configured authentication", help_text)
        self.assertIn("script itself never reads, prints or passes a token", help_text)
        self.assertNotIn("never reads a credential store", help_text)
        self.assertIn("skills remove <name> -g -y -a claude-code codex", help_text)
        # --force also overwrites a global Claude Code entry that is not the link onto the canonical folder (the command center's read of #1024, P3-2)
        self.assertIn("a global Claude Code entry that is not the link onto the canonical folder", help_text)


class IdempotentSkipTests(InstallSkillsTestCase):
    def test_matching_folder_and_lock_is_skipped_without_invoking_the_binary(self):
        content = "# Already installed\n"
        skill = make_skill("steady-skill", content, tree_sha("steady"))
        skill_dir = self.home / ".agents" / "skills" / "steady-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        link_dir = self.home / ".claude" / "skills"  # the link a finished add leaves (GlobalClaudeLinkTests)
        link_dir.mkdir(parents=True)
        os.symlink(os.path.relpath(skill_dir, link_dir), link_dir / "steady-skill")
        lock_dir = self.home / ".agents"
        lock_dir.mkdir(exist_ok=True)
        (lock_dir / ".skill-lock.json").write_text(json.dumps(
            {"lockfileVersion": 3, "skills": {"steady-skill": {"skillFolderHash": tree_sha("steady")}}}))
        fake_bin = write_fake_skills_bin(self.bin_dir, {})  # no fixtures needed: add must never run
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ok", result.stdout)
        self.assertEqual(calls_log(fake_bin), [["--version"]])


def make_real_folder(entry: Path) -> None:
    entry.mkdir()
    (entry / "SKILL.md").write_text("# my own copy\n", encoding="utf-8")
    (entry / "local-work.txt").write_text("work that exists nowhere else\n", encoding="utf-8")


def make_foreign_link(entry: Path) -> None:
    elsewhere = entry.parent.parent / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "local-work.txt").write_text("work that exists nowhere else\n", encoding="utf-8")
    os.symlink(elsewhere, entry)


def make_dangling_link(entry: Path) -> None:
    os.symlink(entry.parent.parent / "nowhere", entry)


def snapshot_entry(entry: Path):
    """What sits at the Claude path, whole: a link's text, or every file of a folder with its bytes."""
    if entry.is_symlink():
        return ("link", os.readlink(entry), sorted(p.name for p in entry.resolve().iterdir()) if entry.exists() else None)
    return ("folder", {p.name: p.read_bytes() for p in sorted(entry.iterdir())})


class GlobalClaudeLinkTests(InstallSkillsTestCase):
    """A global skill is installed only when the canonical folder, its lock entry AND the Claude Code link are in place.

    The contract is the Skills CLI's own (vercel-labs/skills@7407f3893ad4dceab546ac002c3ef806e4000c73, src/installer.ts; for a source outside its blob allowlist, src/add.ts
    L1370-1392 and L1978): installSkillForAgent runs cleanAndCreateDirectory(canonicalDir) (L389), returns without an agent link only for a universal agent (L395-402;
    Codex is one, src/agents.ts L227 and L910-912, Claude Code is not, L158), and otherwise calls createSymlink(canonicalDir, agentDir) (L426). createSymlink (L227-293)
    replaces whatever sits at the link path, a folder with rm(linkPath, { recursive: true }) at L263, and writes symlink(relative(realLinkDir, target), linkPath) at L284-288;
    when that fails the CLI copies the skill there (L428-440). The same add writes the lock entry.
    tools/adoption/install_skills.py used to check only the first two, so --check-only said ok for typesafe-ai on 2026-10-11 while ~/.claude/skills had no entry for it and no
    Claude Code session listed the skill (scripts/skills_status.py failed it as claude_link missing)."""

    CONTENT = "# Linked skill\n"
    TREE = pinned_tree_sha({"SKILL.md": CONTENT})  # a folder of the pinned SKILL.md alone is, file for file, the pinned tree of this fixture
    NAME = "linked-skill"

    def build_installed(self, home: Path, link: bool = True, name: str | None = None) -> dict:
        """The state a finished add leaves (canonical folder with the pinned SKILL.md, lock entry, and optionally the relative Claude link)."""
        name = name or self.NAME
        skill_dir = home / ".agents" / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(self.CONTENT, encoding="utf-8")
        (home / ".agents" / ".skill-lock.json").write_text(json.dumps(
            {"lockfileVersion": 3, "skills": {name: {"skillFolderHash": self.TREE}}}))
        if link:
            link_dir = home / ".claude" / "skills"
            link_dir.mkdir(parents=True)
            os.symlink(os.path.relpath(skill_dir, link_dir), link_dir / name)
        return make_skill(name, self.CONTENT, self.TREE)

    def states(self, manifest: Path, *flags: str, **kwargs) -> tuple[int, dict]:
        result = self.run_install(manifest, *flags, "--json", **kwargs)
        return result.returncode, json.loads(result.stdout)["skills"]

    def test_a_complete_install_stays_ok_in_check_only(self):
        skill = self.build_installed(self.home, link=True)
        fake_bin = write_fake_skills_bin(self.bin_dir, {})
        code, skills = self.states(self.write_manifest([skill]), "--check-only", fake_bin=fake_bin)
        self.assertEqual((code, skills), (0, {self.NAME: "ok"}))
        self.assertEqual(calls_log(fake_bin), [["--version"]])

    def test_a_canonical_folder_and_lock_entry_without_the_claude_link_is_not_ok_in_check_only(self):
        # The command center's required case (2026-10-11): returncode 0 and "ok" before the fix, 1 and "missing-or-drifted" after.
        skill = self.build_installed(self.home, link=False)
        self.assertFalse((self.home / ".claude" / "skills" / self.NAME).exists())
        fake_bin = write_fake_skills_bin(self.bin_dir, {})
        result = self.run_install(self.write_manifest([skill]), "--check-only", "--json", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["ok"])
        self.assertEqual(report["skills"], {self.NAME: "missing-or-drifted"})
        self.assertEqual(calls_log(fake_bin), [["--version"]])  # check-only never runs the add

    def test_a_missing_claude_link_is_planned_in_a_dry_run_and_repaired_by_the_pinned_add(self):
        skill = self.build_installed(self.home, link=False)
        fake_bin = write_fake_skills_bin(self.bin_dir, {self.NAME: {"skill_md": self.CONTENT, "tree_sha": self.TREE}})
        manifest = self.write_manifest([skill])
        code, skills = self.states(manifest, "--dry-run", fake_bin=fake_bin)
        self.assertEqual((code, skills), (0, {self.NAME: "planned"}))
        self.assertEqual(calls_log(fake_bin), [["--version"]])
        self.assertFalse((self.home / ".claude" / "skills" / self.NAME).exists())
        code, skills = self.states(manifest, fake_bin=fake_bin)
        self.assertEqual((code, skills), (0, {self.NAME: "installed"}))
        self.assertEqual(calls_log(fake_bin)[-1], ["add", skill["url"], "--skill", self.NAME, "-g", "-y", "-a", "claude-code", "codex"])
        link = self.home / ".claude" / "skills" / self.NAME
        self.assertEqual(os.readlink(link), os.path.join("..", "..", ".agents", "skills", self.NAME))
        code, skills = self.states(manifest, "--check-only", fake_bin=fake_bin)
        self.assertEqual((code, skills), (0, {self.NAME: "ok"}))

    def fresh_home(self, label: str) -> tuple[Path, Path]:
        home, bin_dir = self.tmp_path / ("home-" + label.replace(" ", "-")), self.tmp_path / ("bin-" + label.replace(" ", "-"))
        home.mkdir()
        bin_dir.mkdir()
        return home, bin_dir

    def assert_refused_then_replaced_by_force(self, home: Path, bin_dir: Path, skill: dict, entry: Path) -> None:
        """Whatever the lock says, an entry at the Claude path that is not the link onto the canonical folder is local content."""
        before = snapshot_entry(entry)
        fake_bin = write_fake_skills_bin(bin_dir, {self.NAME: {"skill_md": self.CONTENT, "tree_sha": self.TREE}})
        manifest = self.write_manifest([skill])
        code, skills = self.states(manifest, "--check-only", fake_bin=fake_bin, home_arg=str(home))
        self.assertEqual((code, skills), (1, {self.NAME: "local-modified"}))
        result = self.run_install(manifest, "--json", fake_bin=fake_bin, home_arg=str(home))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "local-modified"})
        self.assertIn(str(entry), result.stderr)  # the refusal names the Claude entry, not an unlocked SKILL.md
        self.assertEqual(calls_log(fake_bin), [["--version"], ["--version"]])  # neither run reached the add
        self.assertEqual(snapshot_entry(entry), before)  # the local content survived both refused runs, whole
        forced = self.run_install(manifest, "--force", "--json", fake_bin=fake_bin, home_arg=str(home))
        self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
        self.assertEqual(json.loads(forced.stdout)["skills"], {self.NAME: "installed"})
        self.assertEqual(os.readlink(entry), os.path.join("..", "..", ".agents", "skills", self.NAME))

    def test_a_claude_entry_that_is_not_the_link_onto_the_canonical_folder_is_protected_and_force_replaces_it(self):
        # createSymlink (installer.ts L255-263) removes whatever sits at the link path, a real folder recursively, so a
        # folder or a foreign link there is local content: refused without --force, as the project-scope check already does.
        for label, make in (("a real folder", make_real_folder), ("a link to another folder", make_foreign_link),
                            ("a dangling link", make_dangling_link)):
            with self.subTest(entry=label):
                home, bin_dir = self.fresh_home(label)
                skill = self.build_installed(home, link=False)
                entry = home / ".claude" / "skills" / self.NAME
                entry.parent.mkdir(parents=True)
                make(entry)
                self.assert_refused_then_replaced_by_force(home, bin_dir, skill, entry)

    def test_a_fresh_install_an_upgrade_or_an_unlocked_install_over_an_unmanaged_claude_entry_is_refused(self):
        # Astra's first read of 114d539f (P1) and the Codex review in GitHub (thread 1): the add replaces what sits at the link path
        # (installer.ts L255-263, a folder recursively) whatever the lock or the canonical folder say, so the protection comes before
        # every return that can authorize an add: nothing installed, an unlocked or locked-and-different canonical state, an upgrade.
        older = tree_sha("an older tree")

        def canonical(home: Path, text: str) -> None:
            folder = home / ".agents" / "skills" / self.NAME
            folder.mkdir(parents=True)
            (folder / "SKILL.md").write_text(text, encoding="utf-8")

        def lock(home: Path, tree: str) -> None:
            (home / ".agents").mkdir(exist_ok=True)
            (home / ".agents" / ".skill-lock.json").write_text(json.dumps({"lockfileVersion": 3, "skills": {self.NAME: {"skillFolderHash": tree}}}))

        def locked_older_tree(home: Path) -> None:
            canonical(home, self.CONTENT)
            lock(home, older)

        def lock_at_the_pin_but_edited_canonical(home: Path) -> None:
            canonical(home, "# edited\n")
            lock(home, self.TREE)

        states = (
            ("nothing installed", lambda home: None),
            ("an unlocked canonical folder at the pin", lambda home: canonical(home, self.CONTENT)),
            ("an unlocked canonical folder with an edited SKILL.md", lambda home: canonical(home, "# edited\n")),
            ("a lock of an older tree (an upgrade)", locked_older_tree),
            ("a lock at the pin but an edited canonical SKILL.md", lock_at_the_pin_but_edited_canonical),
            ("a lock at the pin but no canonical folder", lambda home: lock(home, self.TREE)),
        )
        kinds = (("a real folder", make_real_folder), ("a link to another folder", make_foreign_link), ("a dangling link", make_dangling_link))
        for state, prepare in states:
            for kind, make in kinds:
                with self.subTest(state=state, entry=kind):
                    home, bin_dir = self.fresh_home(state + " " + kind)
                    prepare(home)
                    entry = home / ".claude" / "skills" / self.NAME
                    entry.parent.mkdir(parents=True)
                    make(entry)
                    self.assert_refused_then_replaced_by_force(home, bin_dir, make_skill(self.NAME, self.CONTENT, self.TREE), entry)

    def test_a_refusal_names_every_local_content_it_protects(self):
        # The command center's read of 114d539f (P3-3): an unlocked canonical folder whose SKILL.md was edited AND a foreign link at the
        # Claude path are two reasons; the refusal named only the second. Each alone still names only itself.
        cases = (("only the edited SKILL.md", False, True), ("only the foreign link", True, False), ("both", True, True))
        for label, foreign, edited in cases:
            with self.subTest(case=label):
                home, bin_dir = self.fresh_home("names-" + label)
                folder = home / ".agents" / "skills" / self.NAME
                folder.mkdir(parents=True)
                (folder / "SKILL.md").write_text("# a local edit\n" if edited else self.CONTENT, encoding="utf-8")
                entry = home / ".claude" / "skills" / self.NAME
                entry.parent.mkdir(parents=True)
                if foreign:
                    make_foreign_link(entry)
                fake_bin = write_fake_skills_bin(bin_dir, {self.NAME: {"skill_md": self.CONTENT, "tree_sha": self.TREE}})
                skill = make_skill(self.NAME, self.CONTENT, self.TREE)
                result = self.run_install(self.write_manifest([skill]), "--json", fake_bin=fake_bin, home_arg=str(home))
                if not (foreign or edited):
                    continue
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "local-modified"})
                self.assertEqual(str(entry) in result.stderr, foreign, result.stderr)
                self.assertEqual("an unlocked local SKILL.md that does not match the pinned manifest hash" in result.stderr, edited, result.stderr)

    def write_lock(self, home: Path, tree: str) -> None:
        (home / ".agents").mkdir(exist_ok=True)
        (home / ".agents" / ".skill-lock.json").write_text(json.dumps({"lockfileVersion": 3, "skills": {self.NAME: {"skillFolderHash": tree}}}))

    def assert_canonical_link_refused_then_replaced_by_force(self, home: Path, bin_dir: Path, skill: dict, canonical: Path, claude: Path) -> None:
        """The canonical path is a link: an ordinary run and check-only refuse it as local-modified (no add, nothing changed), --force replaces it."""
        link_text, claude_before = os.readlink(canonical), snapshot_entry(claude) if claude.is_dir() and not claude.is_symlink() else None
        fake_bin = write_fake_skills_bin(bin_dir, {self.NAME: {"skill_md": self.CONTENT, "tree_sha": self.TREE}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, "--json", fake_bin=fake_bin, home_arg=str(home))  # the ordinary run first: it must not reach the add
        if claude_before is not None:
            self.assertEqual(snapshot_entry(claude), claude_before, "the ordinary run replaced the Claude folder and the files in it")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "local-modified"})
        self.assertIn(str(canonical), result.stderr)  # the refusal names the link and the Claude entry the add would replace after it
        self.assertIn(str(claude), result.stderr)
        self.assertEqual(calls_log(fake_bin), [["--version"]])
        self.assertEqual(self.states(manifest, "--check-only", fake_bin=fake_bin, home_arg=str(home)), (1, {self.NAME: "local-modified"}))
        self.assertEqual(calls_log(fake_bin), [["--version"], ["--version"]])  # neither run reached the add
        self.assertEqual(os.readlink(canonical), link_text)
        if claude_before is not None:
            self.assertEqual(snapshot_entry(claude), claude_before)  # the local files survived both refused runs, whole
        with mock.patch.dict(os.environ):
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
            os.environ.pop("XDG_STATE_HOME", None)
            self.assertEqual(load_installer_module().claude_link_problem(skill, home), "canonical-link")  # equal resolved paths are not proof of ownership here
        forced = self.run_install(manifest, "--force", "--json", fake_bin=fake_bin, home_arg=str(home))
        self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
        self.assertEqual(json.loads(forced.stdout)["skills"], {self.NAME: "installed"})
        self.assertFalse(canonical.is_symlink())
        self.assertEqual(os.readlink(claude), os.path.join("..", "..", ".agents", "skills", self.NAME))

    def test_a_canonical_link_onto_a_real_claude_folder_is_refused_before_the_add_removes_its_files(self):
        # Astra's delta read of 0d2bce2a9, blocker 1, ruled by the command center on 2026-10-12: equal resolved paths are not proof that the
        # Claude entry is the CLI's own link when the canonical path is itself a link. The add removes that link first (installer.ts L389, rm and
        # mkdir) and createSymlink then removes the real Claude folder with local-work.txt (L263). Refused whatever the lock says: absent, older, at the pin.
        older = tree_sha("an older tree")
        for label, tree in (("no lock", None), ("a lock of an older tree", older), ("a lock at the pin", self.TREE)):
            with self.subTest(lock=label):
                home, bin_dir = self.fresh_home("reverse-alias " + label)
                claude = home / ".claude" / "skills" / self.NAME
                claude.mkdir(parents=True)
                (claude / "SKILL.md").write_text(self.CONTENT, encoding="utf-8")  # the pinned SKILL.md, so only the other file tells it from the CLI's folder
                (claude / "local-work.txt").write_text("work that exists nowhere else\n", encoding="utf-8")
                (home / ".agents" / "skills").mkdir(parents=True)
                canonical = home / ".agents" / "skills" / self.NAME
                os.symlink(claude, canonical)
                if tree is not None:
                    self.write_lock(home, tree)
                self.assertEqual(claude.resolve(), canonical.resolve())  # the layout that the equality test used to accept
                self.assert_canonical_link_refused_then_replaced_by_force(home, bin_dir, make_skill(self.NAME, self.CONTENT, self.TREE), canonical, claude)

    def test_any_canonical_link_is_refused_because_the_cli_writes_a_real_folder_there(self):
        # The command center's ruling (2026-10-12): the canonical leaf is the CLI's own real folder, so a link there is not state the installer wrote.
        # Measured with the real pinned CLI (pr-installlink/real-cli-reverse-alias-20261012T0415Z.txt): a link onto a folder elsewhere loses only the link,
        # the folder it led to survives; the refusal is the conservative reading, and a person who wants the link replaced passes --force.
        for label, claude_entry, tree in (("claude entry absent", "absent", None), ("claude entry absent, lock at the pin", "absent", self.TREE),
                                          ("claude entry the relative link onto the canonical path, lock at the pin", "link", self.TREE),
                                          ("a dangling canonical link, claude entry absent", "dangling", None)):
            with self.subTest(case=label):
                home, bin_dir = self.fresh_home("canonical-link " + label)
                elsewhere = home.parent / ("dotfiles-" + home.name)  # a dangling link points at it without it being made
                if claude_entry != "dangling":
                    elsewhere.mkdir()
                    (elsewhere / "SKILL.md").write_text(self.CONTENT, encoding="utf-8")
                    (elsewhere / "local-work.txt").write_text("work that exists nowhere else\n", encoding="utf-8")
                (home / ".agents" / "skills").mkdir(parents=True)
                canonical = home / ".agents" / "skills" / self.NAME
                os.symlink(elsewhere, canonical)
                claude = home / ".claude" / "skills" / self.NAME
                if claude_entry == "link":
                    claude.parent.mkdir(parents=True)
                    os.symlink(os.path.join("..", "..", ".agents", "skills", self.NAME), claude)
                if tree is not None:
                    self.write_lock(home, tree)
                self.assert_canonical_link_refused_then_replaced_by_force(home, bin_dir, make_skill(self.NAME, self.CONTENT, self.TREE), canonical, claude)

    def test_a_link_on_a_parent_folder_is_the_layout_createsymlink_accepts_and_stays_ok(self):
        # createSymlink returns without touching anything when ~/.claude/skills (or ~/.agents/skills) is a link onto the other, so both entries are one real
        # folder (installer.ts L240-250). The canonical-link refusal is about the canonical path itself, never about a parent: this layout stays ok.
        for label, canonical_parent_is_the_link in (("the Claude skills folder links onto the canonical one", False), ("the canonical skills folder links onto the Claude one", True)):
            with self.subTest(layout=label):
                home, bin_dir = self.fresh_home("parent-link " + label)
                real, other = (home / ".claude" / "skills", home / ".agents" / "skills") if canonical_parent_is_the_link else (home / ".agents" / "skills", home / ".claude" / "skills")
                (real / self.NAME).mkdir(parents=True)
                (real / self.NAME / "SKILL.md").write_text(self.CONTENT, encoding="utf-8")
                other.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(real, other)
                self.write_lock(home, self.TREE)
                skill = make_skill(self.NAME, self.CONTENT, self.TREE)
                fake_bin = write_fake_skills_bin(bin_dir, {})
                self.assertEqual(self.states(self.write_manifest([skill]), "--check-only", fake_bin=fake_bin, home_arg=str(home)), (0, {self.NAME: "ok"}))
                self.assertEqual(calls_log(fake_bin), [["--version"]])

    def test_a_codex_only_entry_is_not_refused_for_a_canonical_link(self):
        # Codex is universal: the CLI returns after the canonical write (installer.ts L395-402) and judges no Claude entry, so the canonical-link refusal,
        # which protects the Claude entry the add would remove, does not apply to an entry that is not installed for Claude Code.
        skill = self.build_installed(self.home, link=False)
        skill["agents"] = ["codex"]
        elsewhere = self.tmp_path / "dotfiles"
        elsewhere.mkdir()
        (elsewhere / "SKILL.md").write_text(self.CONTENT, encoding="utf-8")
        canonical = self.home / ".agents" / "skills" / self.NAME
        shutil.rmtree(canonical)
        os.symlink(elsewhere, canonical)
        fake_bin = write_fake_skills_bin(self.bin_dir, {})
        self.assertEqual(self.states(self.write_manifest([skill]), "--check-only", fake_bin=fake_bin), (0, {self.NAME: "ok"}))

    def test_classify_skill_and_the_refusal_wording_ask_one_skill_md_check(self):
        # The command center's condition 2 for #1024 (2026-10-12): the refusal wording (unlocked_folder_differs) and classify_skill ask the
        # same question, whether the installed SKILL.md is the pinned one, through ONE helper (installed_skill_md_matches). A second copy of
        # the check would also be a second unclassified read for the push gate's monitoring baseline (tests.test_runtime_worker_openhands_push_gate).
        installer = load_installer_module()
        skill = make_skill(self.NAME, self.CONTENT, pinned_tree_sha({"SKILL.md": "# a local edit\n"}))  # the edited folder is the manifest's tree, so only the SKILL.md check decides
        folder = self.home / ".agents" / "skills" / self.NAME
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("# a local edit\n", encoding="utf-8")  # an unlocked canonical folder whose SKILL.md is not the pinned one
        with mock.patch.dict(os.environ):
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
            os.environ.pop("XDG_STATE_HOME", None)
            self.assertEqual((installer.classify_skill(skill, self.home), installer.unlocked_folder_differs(skill, self.home)), ("local-modified", True))
            for matches in (False, True):
                with self.subTest(helper_says_the_skill_md_matches=matches):
                    with mock.patch.object(installer, "installed_skill_md_matches", return_value=matches) as helper:
                        state = installer.classify_skill(skill, self.home)
                        differs = installer.unlocked_folder_differs(skill, self.home)
                    self.assertEqual(state, "install" if matches else "local-modified")
                    self.assertEqual(differs, not matches)
                    self.assertEqual(helper.call_count, 2, "both paths must ask the one helper")

    def test_a_dangling_link_onto_the_canonical_folder_is_the_clis_own_and_is_not_refused(self):
        # A half-removed install leaves the CLI's own link without its canonical folder. It points where the CLI would point
        # (createSymlink keeps a link with the same target, L258-259), so it is not local content: the add simply reinstalls.
        link_dir = self.home / ".claude" / "skills"
        link_dir.mkdir(parents=True)
        os.symlink(os.path.join("..", "..", ".agents", "skills", self.NAME), link_dir / self.NAME)
        self.assertFalse((link_dir / self.NAME).exists())  # dangling
        skill = make_skill(self.NAME, self.CONTENT, self.TREE)
        fake_bin = write_fake_skills_bin(self.bin_dir, {self.NAME: {"skill_md": self.CONTENT, "tree_sha": self.TREE}})
        manifest = self.write_manifest([skill])
        self.assertEqual(self.states(manifest, "--check-only", fake_bin=fake_bin), (1, {self.NAME: "missing-or-drifted"}))
        self.assertEqual(self.states(manifest, fake_bin=fake_bin), (0, {self.NAME: "installed"}))
        self.assertEqual(os.readlink(link_dir / self.NAME), os.path.join("..", "..", ".agents", "skills", self.NAME))

    def test_the_link_is_read_where_claude_config_dir_moves_it(self):
        skill = self.build_installed(self.home, link=True)  # the link is in the default ~/.claude/skills
        fake_bin = write_fake_skills_bin(self.bin_dir, {})
        manifest = self.write_manifest([skill])
        config = self.tmp_path / "claude-config"
        env = {"CLAUDE_CONFIG_DIR": str(config)}
        self.assertEqual(self.states(manifest, "--check-only", env=env, fake_bin=fake_bin), (1, {self.NAME: "missing-or-drifted"}))
        (config / "skills").mkdir(parents=True)
        os.symlink(os.path.relpath(self.home / ".agents" / "skills" / self.NAME, config / "skills"), config / "skills" / self.NAME)
        self.assertEqual(self.states(manifest, "--check-only", env=env, fake_bin=fake_bin), (0, {self.NAME: "ok"}))

    def test_a_link_that_cannot_be_resolved_is_foreign_not_accepted(self):
        # CPython 3.11 and 3.12 raise RuntimeError from Path.resolve() for a symlink loop (3.13 tolerates it in non-strict mode, as
        # scripts/skills_status.py notes). A link that cannot be resolved is not the canonical link: protected, never accepted.
        installer = load_installer_module()
        skill = self.build_installed(self.home, link=True)
        with mock.patch.dict(os.environ):
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
            self.assertIsNone(installer.claude_link_problem(skill, self.home))
            with mock.patch.object(Path, "resolve", side_effect=RuntimeError("Symlink loop")):
                self.assertEqual(installer.claude_link_problem(skill, self.home), "elsewhere")

    def test_a_codex_only_entry_needs_no_claude_link(self):
        # Codex loads the canonical folder itself (installer.ts L395-402 skips the agent link for a universal agent).
        skill = self.build_installed(self.home, link=False)
        skill["agents"] = ["codex"]
        fake_bin = write_fake_skills_bin(self.bin_dir, {})
        code, skills = self.states(self.write_manifest([skill]), "--check-only", fake_bin=fake_bin)
        self.assertEqual((code, skills), (0, {self.NAME: "ok"}))

    def test_an_add_that_leaves_no_claude_link_is_not_verified_and_is_rolled_back(self):
        skill = make_skill(self.NAME, self.CONTENT, self.TREE)
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {self.NAME: {"skill_md": self.CONTENT, "tree_sha": self.TREE, "no_claude_link": 1}})
        result = self.run_install(self.write_manifest([skill]), "--json", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "rolled-back"})
        self.assertEqual([call[0] for call in calls_log(fake_bin)], ["--version", "add", "remove"])
        self.assertIn("rolled back", result.stderr)
        self.assertIn("left no Claude Code link", result.stderr)
        self.assertFalse((self.home / ".agents" / "skills" / self.NAME).exists())

    def test_an_add_that_falls_back_to_a_copy_is_rolled_back_and_the_message_names_the_cause(self):
        # The CLI copies the skill into the Claude folder when it cannot create the symlink and reports success (installer.ts
        # L428-440). That layout is not the one scripts/skills_status.py accepts (not_a_symlink), so the installer keeps requiring
        # the link, rolls the add back and says why; the Codex review in GitHub of 114d539f5 (P2, thread 2) asked it to accept the copy.
        skill = make_skill(self.NAME, self.CONTENT, self.TREE)
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {self.NAME: {"skill_md": self.CONTENT, "tree_sha": self.TREE, "copy_fallback": 1}})
        result = self.run_install(self.write_manifest([skill]), "--json", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "rolled-back"})
        self.assertEqual([call[0] for call in calls_log(fake_bin)], ["--version", "add", "remove"])
        self.assertIn("rolled back", result.stderr)
        self.assertIn("cannot create a symlink", result.stderr)
        self.assertIn(str(self.home / ".claude" / "skills" / self.NAME), result.stderr)
        self.assertFalse((self.home / ".agents" / "skills" / self.NAME).exists())
        self.assertFalse((self.home / ".claude" / "skills" / self.NAME).exists())


class AddAndVerifyTests(InstallSkillsTestCase):
    def test_fresh_install_is_verified_and_reported_installed(self):
        content = "# New skill\n"
        skill = make_skill("new-skill", content, tree_sha("new"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"new-skill": {"skill_md": content, "tree_sha": tree_sha("new")}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("installed", result.stdout)
        calls = calls_log(fake_bin)
        self.assertEqual([c[0] for c in calls], ["--version", "add"])
        skill_md = self.home / ".agents" / "skills" / "new-skill" / "SKILL.md"
        self.assertEqual(skill_md.read_text(), content)
        link = self.home / ".claude" / "skills" / "new-skill"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), os.path.join("..", "..", ".agents", "skills", "new-skill"))
        self.assertEqual(self.lock_data()["skills"]["new-skill"]["skillFolderHash"], tree_sha("new"))

    def test_second_run_of_a_fresh_install_is_then_an_idempotent_skip(self):
        content = "# New skill\n"
        skill = make_skill("new-skill", content, tree_sha("new"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"new-skill": {"skill_md": content, "tree_sha": tree_sha("new")}})
        manifest = self.write_manifest([skill])
        first = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("ok", second.stdout)
        self.assertEqual([c[0] for c in calls_log(fake_bin)], ["--version", "add", "--version"])

    def test_install_through_dotdot_in_home_or_xdg_state_home_is_verified(self):
        # The post-add check reads the canonical folder and the lock where the CLI wrote them (dotdot_paths),
        # so a matching add through tmp/missing/.. is installed, not rolled back as unverified.
        content = "# New skill\n"
        for label, via in (("home-dotdot", "home"), ("xdg-dotdot", "xdg")):
            with self.subTest(case=label):
                env, home_arg, lock = self.dotdot_paths(label, via)
                bin_dir = self.tmp_path / f"bin-{label}"
                bin_dir.mkdir()
                fake_bin = write_fake_skills_bin(
                    bin_dir, {"new-skill": {"skill_md": content, "tree_sha": tree_sha("new")}})
                manifest = self.write_manifest([make_skill("new-skill", content, tree_sha("new"))])
                result = self.run_install(manifest, "--json", env=env, fake_bin=fake_bin, home_arg=home_arg)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["skills"], {"new-skill": "installed"})
                self.assertEqual([c[0] for c in calls_log(fake_bin)], ["--version", "add"])
                skill_md = self.tmp_path / label / ".agents" / "skills" / "new-skill" / "SKILL.md"
                self.assertEqual(skill_md.read_text(), content)
                self.assertEqual(json.loads(lock.read_text())["skills"]["new-skill"]["skillFolderHash"],
                                 tree_sha("new"))
                self.assert_fake_cli_made_no_missing_folder()

    def test_global_paths_join_as_node_does_and_project_paths_are_unchanged(self):
        installer = load_installer_module()
        home, project = Path("/h/missing/../base"), Path("/p/missing/../project")
        with mock.patch.dict(os.environ):
            os.environ.pop("XDG_STATE_HOME", None)
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
            self.assertEqual(installer.canonical_skill_dir(home, "x"), Path("/h/base/.agents/skills/x"))
            self.assertEqual(installer.lock_file_path(home), Path("/h/base/.agents/.skill-lock.json"))
            self.assertEqual(installer.claude_skills_dir(home), Path("/h/base/.claude/skills"))
            os.environ["XDG_STATE_HOME"] = "//s/missing/../state"  # a leading // collapses to /, as in Node
            self.assertEqual(installer.lock_file_path(home), Path("/s/state/skills/.skill-lock.json"))
            # main() resolves --project-dir; each project path is the given directory joined by pathlib, as before.
            self.assertEqual(installer.canonical_skill_dir(home, "x", project), project / ".agents" / "skills" / "x")
            self.assertEqual(installer.lock_file_path(home, project), project / "skills-lock.json")
            self.assertEqual(installer.claude_skills_dir(home, project), project / ".claude" / "skills")

    @unittest.skipUnless(shutil.which("node"), "node is not on PATH")
    def test_node_path_join_matches_node(self):
        # The one join every global path goes through, against node's own path.join (no case ends in /, which
        # Node keeps and a Path cannot).
        cases = [["/a/missing/../state", "skills", ".skill-lock.json"], ["//a/b", ".agents", "skills", "x"],
                 ["///a", ".agents"], ["rel/../../x", ".agents"], ["a/./b//c", "skills"], ["/..", "x"],
                 ["", "skills"], ["/a/b/", ".claude", "skills"], ["..", "x"], ["", ""]]
        script = ("const {join} = require('path'); "
                  "console.log(JSON.stringify(JSON.parse(process.argv[1]).map(parts => join(...parts))));")
        result = subprocess.run(["node", "-e", script, json.dumps(cases)], capture_output=True, text=True,
                                check=True, timeout=60)
        installer = load_installer_module()
        self.assertEqual([str(installer.node_path_join(*parts)) for parts in cases], json.loads(result.stdout))


class MismatchRollbackTests(InstallSkillsTestCase):
    def test_tree_sha_mismatch_after_add_rolls_back_and_exits_one(self):
        content = "# Drifted skill\n"
        # The manifest pins one tree; the (fake) upstream installs matching bytes but records a
        # different skillFolderHash, as if the tag had moved or the CLI resolved the wrong tree.
        skill = make_skill("drift-skill", content, tree_sha("pinned"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"drift-skill": {"skill_md": content, "tree_sha": tree_sha("actually-installed")}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("rolled back", result.stderr)
        calls = calls_log(fake_bin)
        self.assertEqual([c[0] for c in calls], ["--version", "add", "remove"])
        # The rollback is scoped to exactly the agents the install wrote for, never to every agent (#405).
        self.assertEqual(calls[2], ["remove", "drift-skill", "-g", "-y", "-a", "claude-code", "codex"])
        self.assertEqual(calls[1][calls[1].index("-a"):], calls[2][calls[2].index("-a"):])
        # The fake remove handler actually deleted what add wrote.
        self.assertFalse((self.home / ".agents" / "skills" / "drift-skill").exists())
        self.assertFalse((self.home / ".claude" / "skills" / "drift-skill").exists())
        self.assertNotIn("drift-skill", self.lock_data().get("skills", {}))

    def test_skill_md_bytes_mismatch_after_add_also_rolls_back(self):
        skill = make_skill("bytes-skill", "# Expected\n", tree_sha("bytes"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"bytes-skill": {"skill_md": "# Something else entirely\n",
                                            "tree_sha": tree_sha("bytes")}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("rolled back", result.stderr)
        self.assertEqual([c[0] for c in calls_log(fake_bin)], ["--version", "add", "remove"])


class GlobalRollbackReadBackTests(InstallSkillsTestCase):
    """A global rollback is read back from disk, as the project rollback is. skills 1.7.0's scoped
    `remove` keeps the canonical folder and its lock entry while any other detected agent resolves to
    that folder, and exits 0 either way (vercel-labs/skills v1.7.0 src/remove.ts L293-340). Codex reads
    the canonical folder while it exists, and the skills CLI still counts it as installed for every
    universal agent. What remains is reported as 'error' with the project path's reasons, and the
    script deletes nothing itself. Fake-CLI integration fixtures, not a native CLI run."""

    NAME = "drift-skill"
    CONTENT = "# Drifted skill\n"

    def run_drift(self, home_label: str = "home", env: dict | None = None, home_arg: str | None = None,
                  **fixture) -> subprocess.CompletedProcess:
        """A tree mismatch after add, so the global rollback runs; each label gets its own home and binary."""
        self.home = self.tmp_path / home_label
        self.home.mkdir(exist_ok=True)
        bin_dir = self.tmp_path / f"bin-{home_label}"
        bin_dir.mkdir()
        self.fake_bin = write_fake_skills_bin(bin_dir, {self.NAME: {
            "skill_md": self.CONTENT, "tree_sha": tree_sha("actually-installed"), **fixture}})
        manifest = self.write_manifest([make_skill(self.NAME, self.CONTENT, tree_sha("pinned"))])
        return self.run_install(manifest, "--json", fake_bin=self.fake_bin, env=env, home_arg=home_arg)

    def artifacts(self) -> dict:
        canonical = self.home / ".agents" / "skills" / self.NAME
        link = self.home / ".claude" / "skills" / self.NAME
        return {"canonical": canonical.exists() or canonical.is_symlink(),
                "lock": self.NAME in self.lock_data().get("skills", {}),
                "claude-link": link.exists() or link.is_symlink()}

    def assert_error(self, result: subprocess.CompletedProcess, reason: str) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "error"})
        self.assertIn(f"{self.NAME}: error: {reason} (exit ", result.stderr)
        self.assertNotIn("rolled back", result.stderr)

    def test_retained_canonical_folder_and_lock_are_error_in_use_by_another_agent(self):
        # What skills 1.7.0 does while another universal agent is detected: both stay and remove exits 0.
        result = self.run_drift(retain_after_remove=["canonical", "lock"])
        self.assert_error(result, "rollback retained, in use by another agent")
        calls = calls_log(self.fake_bin)
        self.assertEqual([c[0] for c in calls], ["--version", "add", "remove"])
        self.assertEqual(calls[-1], ["remove", self.NAME, "-g", "-y", "-a", "claude-code", "codex"])
        self.assertEqual(self.artifacts(), {"canonical": True, "lock": True, "claude-link": False})
        # The message names what remains, and nothing was deleted by the script itself.
        self.assertIn("canonical=True, lock=True, claude-link=False", result.stderr)
        self.assertIn(str(self.home / ".agents" / "skills" / self.NAME), result.stderr)
        self.assertIn(str(self.home / ".agents" / ".skill-lock.json"), result.stderr)
        self.assertEqual((self.home / ".agents" / "skills" / self.NAME / "SKILL.md").read_text(), self.CONTENT)

    def test_each_retained_artifact_is_error_on_its_own(self):
        for artifact, reason in (("canonical", "rollback retained, in use by another agent"),
                                 ("lock", "rollback incomplete"), ("claude-link", "rollback incomplete")):
            with self.subTest(artifact=artifact):
                # A retained drifted copy is local content to the next run, so each case gets its own home.
                result = self.run_drift(f"home-{artifact}", retain_after_remove=[artifact])
                self.assert_error(result, reason)
                self.assertEqual(self.artifacts(),
                                 {key: key == artifact for key in ("canonical", "lock", "claude-link")})
                if artifact == "claude-link":
                    link = self.home / ".claude" / "skills" / self.NAME
                    self.assertFalse(link.exists(), "a dangling Claude link must still count as retained")

    def test_remove_that_exits_nonzero_is_error_rollback_incomplete(self):
        result = self.run_drift(remove_exit=1)
        self.assert_error(result, "rollback incomplete")
        self.assertIn("(exit 1; canonical=True, lock=True, claude-link=True)", result.stderr)
        self.assertEqual(self.artifacts(), {"canonical": True, "lock": True, "claude-link": True})

    def test_remove_that_cannot_run_is_error_not_an_exception(self):
        # Fixtures are embedded in the fake CLI as Python source, so flags are ints rather than JSON booleans.
        for flag, case in ((1, "not executable"), (2, "missing")):
            with self.subTest(binary=case):
                result = self.run_drift(f"home-cannot-run-{flag}", remove_cannot_run=flag)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "error"})
                self.assertIn(f"{self.NAME}: verification failed and rollback could not run (", result.stderr)
                self.assertEqual([c[0] for c in calls_log(self.fake_bin)], ["--version", "add"])
                self.assertEqual(self.fake_bin.exists(), flag == 1)

    def test_malformed_lock_after_remove_is_error_could_not_be_verified(self):
        # Both copies are gone and the remove exits 0, but a truncated lock may still hold the entry.
        result = self.run_drift(lock_after_remove="malformed")
        self.assert_error(result, "rollback could not be verified")
        self.assertIn("read-back failed: ", result.stderr)
        lock_text = (self.home / ".agents" / ".skill-lock.json").read_text()
        self.assertIn(f'"{self.NAME}"', lock_text)
        self.assertRaises(ValueError, json.loads, lock_text)
        self.assertFalse((self.home / ".agents" / "skills" / self.NAME).exists())

    @unittest.skipIf(os.geteuid() == 0, "root reads a mode-000 file")
    def test_unreadable_lock_after_remove_is_error_not_an_exception(self):
        result = self.run_drift(lock_after_remove="unreadable")
        self.assert_error(result, "rollback could not be verified")
        self.assertIn("read-back failed: [Errno 13]", result.stderr)

    def test_claude_config_dir_link_is_read_back_where_the_cli_writes_it(self):
        config_dir = self.tmp_path / "claude-config"
        result = self.run_drift(env={"CLAUDE_CONFIG_DIR": str(config_dir)}, retain_after_remove=["claude-link"])
        self.assert_error(result, "rollback incomplete")
        link = config_dir / "skills" / self.NAME
        self.assertTrue(link.is_symlink())
        self.assertIn("canonical=False, lock=False, claude-link=True", result.stderr)
        self.assertIn(f"left: {link}", result.stderr)
        self.assertFalse((self.home / ".claude").exists())

    def test_claude_config_dir_is_trimmed_and_normalized_as_the_cli_does(self):
        # dist/cli.mjs L1398 trims with JavaScript's trim() and L1511 joins with path.join, which collapses "..".
        # U+FEFF is JS whitespace; U+0085 is Python whitespace only, so it stays part of the folder name.
        config_dir = self.tmp_path / "claude-config"
        cases = (("home-dotdot", str(self.tmp_path / "missing" / ".." / "claude-config"), config_dir / "skills"),
                 ("home-bom", "\ufeff", None),
                 ("home-nel", str(config_dir) + "\u0085", Path(str(config_dir) + "\u0085") / "skills"))
        for label, value, link_dir in cases:
            with self.subTest(case=label):
                result = self.run_drift(label, env={"CLAUDE_CONFIG_DIR": value}, retain_after_remove=["claude-link"])
                self.assert_error(result, "rollback incomplete")
                link = (link_dir or self.home / ".claude" / "skills") / self.NAME
                self.assertTrue(link.is_symlink())
                self.assertIn(f"left: {link}", result.stderr)
                self.assert_fake_cli_made_no_missing_folder()

    @unittest.skipUnless(shutil.which("node"), "node is not on PATH")
    def test_js_trim_chars_match_node(self):
        script = ('const out = []; for (let c = 0; c <= 0x10FFFF; c++) { if (c >= 0xD800 && c <= 0xDFFF) continue; '
                  'if (String.fromCodePoint(c).trim() === "") out.push(c); } console.log(JSON.stringify(out));')
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=60)
        node_set = set(json.loads(result.stdout))
        self.assertEqual({ord(c) for c in load_installer_module().JS_TRIM_CHARS}, node_set)
        self.assertEqual({ord(c) for c in JS_TRIM_CHARS}, node_set)

    def test_claude_config_dir_control_ignores_the_default_claude_folder(self):
        # Another copy under ~/.claude is not the CLI's link while CLAUDE_CONFIG_DIR is set; a blank value is unset.
        config_dir = self.tmp_path / "claude-config"
        for label, value, link_dir in (("home-config", str(config_dir), config_dir / "skills"),
                                       ("home-blank", "  ", None)):
            with self.subTest(claude_config_dir=value):
                other = self.tmp_path / label / ".claude" / "skills" / self.NAME / "SKILL.md"
                if link_dir is not None:
                    other.parent.mkdir(parents=True)
                    other.write_text("owned before this run\n")
                result = self.run_drift(label, env={"CLAUDE_CONFIG_DIR": value})
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "rolled-back"})
                self.assertNotIn(": error:", result.stderr)
                self.assertEqual(self.artifacts()["canonical"], False)
                self.assertEqual(self.artifacts()["lock"], False)
                if link_dir is not None:
                    self.assertEqual(other.read_text(), "owned before this run\n")
                    self.assertTrue(link_dir.is_dir())
                    self.assertFalse((link_dir / self.NAME).exists() or (link_dir / self.NAME).is_symlink())
                else:
                    self.assertTrue((self.home / ".claude" / "skills").is_dir())
                    self.assertEqual(self.artifacts()["claude-link"], False)

    def test_control_remove_that_deletes_everything_is_rolled_back(self):
        result = self.run_drift()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "rolled-back"})
        self.assertIn("rolled back", result.stderr)
        self.assertNotIn(": error:", result.stderr)
        self.assertEqual(self.artifacts(), {"canonical": False, "lock": False, "claude-link": False})

    def test_dotdot_in_home_or_xdg_state_home_is_read_back_where_the_cli_keeps_it(self):
        # The canonical folder and the lock are read back at the CLI's path.join paths (dotdot_paths): a kept
        # folder or lock entry through tmp/missing/.. is not read as removed.
        for label, via, retained, reason in (
                ("home-dotdot-canonical", "home", ["canonical"], "rollback retained, in use by another agent"),
                ("home-dotdot-lock", "home", ["lock"], "rollback incomplete"),
                ("xdg-dotdot-lock", "xdg", ["lock"], "rollback incomplete")):
            with self.subTest(case=label):
                env, home_arg, lock = self.dotdot_paths(label, via)
                result = self.run_drift(label, env=env, home_arg=home_arg, retain_after_remove=retained)
                self.assert_error(result, reason)
                canonical = self.home / ".agents" / "skills" / self.NAME
                kept = {"canonical": canonical.is_dir(), "lock": self.NAME in json.loads(lock.read_text())["skills"]}
                self.assertEqual(kept, {key: key in retained for key in kept})
                self.assertIn(f"canonical={kept['canonical']}, lock={kept['lock']}, claude-link=False", result.stderr)
                self.assertIn(f"left: {canonical}" if kept["canonical"] else f"left: its entry in {lock}",
                              result.stderr)
                self.assert_fake_cli_made_no_missing_folder()

    def test_dotdot_control_remove_that_deletes_everything_is_rolled_back(self):
        for label, via in (("home-dotdot-control", "home"), ("xdg-dotdot-control", "xdg")):
            with self.subTest(case=label):
                env, home_arg, lock = self.dotdot_paths(label, via)
                result = self.run_drift(label, env=env, home_arg=home_arg)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["skills"], {self.NAME: "rolled-back"})
                self.assertNotIn(": error:", result.stderr)
                # The fake CLI wrote and emptied the lock at the normalized path; nothing else is left.
                self.assertEqual(json.loads(lock.read_text())["skills"], {})
                self.assertFalse((self.home / ".agents" / "skills" / self.NAME).exists())
                link = self.home / ".claude" / "skills" / self.NAME
                self.assertFalse(link.exists() or link.is_symlink())
                self.assert_fake_cli_made_no_missing_folder()


class LocalModifiedTests(InstallSkillsTestCase):
    def setUp(self):
        super().setUp()
        self.pinned_content = "# Pinned upstream content\n"
        self.tree = pinned_tree_sha({"SKILL.md": self.pinned_content})
        self.skill = make_skill("hand-installed", self.pinned_content, self.tree)
        skill_dir = self.home / ".agents" / "skills" / "hand-installed"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# A locally hand-edited copy\n", encoding="utf-8")
        # No lock entry at all: exactly the "installed by hand before the manifest existed" case.

    def test_unlocked_local_modification_is_refused_without_force(self):
        fake_bin = write_fake_skills_bin(self.bin_dir, {})  # must never be asked to add/remove
        manifest = self.write_manifest([self.skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("local-modified", result.stderr)
        self.assertEqual(calls_log(fake_bin), [["--version"]])
        # The local copy is untouched.
        self.assertEqual((self.home / ".agents" / "skills" / "hand-installed" / "SKILL.md").read_text(),
                         "# A locally hand-edited copy\n")

    def test_unlocked_folder_without_skill_md_is_refused_as_local_modified(self):
        # A canonical folder that exists but has no SKILL.md at all (e.g. an
        # unrelated file dropped there by hand, or a partial install) must still
        # be refused as (b), not fall through to "install": `skills add` recreates
        # its target directory from scratch, so treating this like a fresh (c)
        # install would silently discard whatever is actually in the folder.
        skill = make_skill("no-skill-md", "# Would-be pinned content\n", tree_sha("no-skill-md"))
        skill_dir = self.home / ".agents" / "skills" / "no-skill-md"
        skill_dir.mkdir(parents=True)
        (skill_dir / "OTHER_FILE.md").write_text("unrelated local content\n", encoding="utf-8")
        fake_bin = write_fake_skills_bin(self.bin_dir, {})  # must never be asked to add/remove
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("local-modified", result.stderr)
        self.assertEqual(calls_log(fake_bin), [["--version"]])
        # The unrelated local file survives untouched, and no SKILL.md was fabricated.
        self.assertEqual((skill_dir / "OTHER_FILE.md").read_text(), "unrelated local content\n")
        self.assertFalse((skill_dir / "SKILL.md").exists())

    def test_an_unlocked_but_byte_identical_copy_is_not_local_modified(self):
        # Same setup, but the on-disk SKILL.md already matches the manifest exactly: (b) says this
        # is safe to bring under lock management, not a local edit to protect.
        skill_dir = self.home / ".agents" / "skills" / "hand-installed"
        (skill_dir / "SKILL.md").write_text(self.pinned_content, encoding="utf-8")
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"hand-installed": {"skill_md": self.pinned_content, "tree_sha": self.tree}})
        manifest = self.write_manifest([self.skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([c[0] for c in calls_log(fake_bin)], ["--version", "add"])

    def test_force_overwrites_a_genuine_local_modification(self):
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"hand-installed": {"skill_md": self.pinned_content, "tree_sha": self.tree}})
        manifest = self.write_manifest([self.skill])
        result = self.run_install(manifest, "--force", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("installed", result.stdout)
        self.assertEqual([c[0] for c in calls_log(fake_bin)], ["--version", "add"])
        self.assertEqual((self.home / ".agents" / "skills" / "hand-installed" / "SKILL.md").read_text(),
                         self.pinned_content)


class XdgStateHomeLockPathTests(InstallSkillsTestCase):
    def test_lock_is_read_and_written_under_xdg_state_home_when_set(self):
        xdg = self.tmp_path / "xdg-state"
        xdg.mkdir()
        content = "# XDG-pathed skill\n"
        skill = make_skill("xdg-skill", content, tree_sha("xdg"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"xdg-skill": {"skill_md": content, "tree_sha": tree_sha("xdg")}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, env={"XDG_STATE_HOME": str(xdg)}, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("installed", result.stdout)
        xdg_lock = xdg / "skills" / ".skill-lock.json"
        self.assertTrue(xdg_lock.is_file())
        self.assertEqual(json.loads(xdg_lock.read_text())["skills"]["xdg-skill"]["skillFolderHash"],
                         tree_sha("xdg"))
        self.assertFalse((self.home / ".agents" / ".skill-lock.json").exists())

    def test_second_run_under_the_same_xdg_state_home_is_an_idempotent_skip(self):
        xdg = self.tmp_path / "xdg-state"
        xdg.mkdir()
        content = "# XDG-pathed skill\n"
        skill = make_skill("xdg-skill", content, tree_sha("xdg"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"xdg-skill": {"skill_md": content, "tree_sha": tree_sha("xdg")}})
        manifest = self.write_manifest([skill])
        first = self.run_install(manifest, env={"XDG_STATE_HOME": str(xdg)}, fake_bin=fake_bin)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self.run_install(manifest, env={"XDG_STATE_HOME": str(xdg)}, fake_bin=fake_bin)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("ok", second.stdout)
        self.assertEqual([c[0] for c in calls_log(fake_bin)], ["--version", "add", "--version"])


class ManifestScopeAndPruneTests(InstallSkillsTestCase):
    """A manifest marked "scope": "project" never runs without --project-dir, and a pruned
    entry is never installed, in either mode."""

    def test_project_scoped_manifest_refuses_to_run_without_project_dir(self):
        skill = make_skill("scoped-skill", "# scoped\n", tree_sha("scoped"))
        fake_bin = write_fake_skills_bin(self.bin_dir, {"scoped-skill": {"skill_md": "# scoped\n",
                                                                         "tree_sha": tree_sha("scoped")}})
        data = dict(make_manifest([skill]), scope="project")
        scoped = self.tmp_path / "scoped.json"
        scoped.write_text(json.dumps(data))
        for manifest in (scoped, RUNTIME_MANIFEST):
            for mode in ((), ("--dry-run",), ("--check-only",)):
                with self.subTest(manifest=manifest.name, mode=mode):
                    result = self.run_install(manifest, *mode, fake_bin=fake_bin)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("scoped to projects", result.stderr)
                    self.assertIn("--project-dir", result.stderr)
        self.assertEqual(calls_log(fake_bin), [])  # refused before even the version check
        self.assertFalse((self.home / ".agents").exists())
        # A path-keyed Codex table names the project's installed SKILL.md, so printing needs --project-dir too.
        printed = self.run_install(scoped, "--print-codex-config")
        self.assertEqual(printed.returncode, 1, printed.stdout + printed.stderr)
        self.assertIn("--project-dir", printed.stderr)
        self.assertNotIn("[[skills.config]]", printed.stdout)
        project = self.tmp_path / "project"
        project.mkdir()
        printed = self.run_install(scoped, "--print-codex-config", "--project-dir", str(project))  # print-only
        self.assertEqual(printed.returncode, 0, printed.stdout + printed.stderr)
        self.assertEqual(list(project.iterdir()), [])
        scoped.write_text(json.dumps(dict(data, scope="planet")))
        for mode in ((), ("--print-codex-config",)):
            with self.subTest(scope="planet", mode=mode):
                unknown = self.run_install(scoped, *mode, fake_bin=fake_bin)
                self.assertEqual(unknown.returncode, 1, unknown.stdout + unknown.stderr)
                self.assertIn("unknown manifest scope", unknown.stderr)
        self.assertEqual(calls_log(fake_bin), [])
        self.assertFalse((self.home / ".agents").exists())

    def test_pruned_entries_are_never_installed_in_global_mode_either(self):
        kept = make_skill("kept-skill", "# kept\n", tree_sha("kept"))
        pruned = dict(make_skill("pruned-skill", "# pruned\n", tree_sha("pruned")), status="pruned")
        fake_bin = write_fake_skills_bin(self.bin_dir, {
            "kept-skill": {"skill_md": "# kept\n", "tree_sha": tree_sha("kept")},
            "pruned-skill": {"skill_md": "# pruned\n", "tree_sha": tree_sha("pruned")}})
        manifest = self.write_manifest([kept, pruned])
        result = self.run_install(manifest, "--json", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {"kept-skill": "installed"})
        self.assertEqual([call[3] for call in calls_log(fake_bin) if call[0] == "add"], ["kept-skill"])
        self.assertFalse((self.home / ".agents" / "skills" / "pruned-skill").exists())
        only = self.run_install(manifest, "--only", "pruned-skill", fake_bin=fake_bin)
        self.assertEqual(only.returncode, 1, only.stdout + only.stderr)
        self.assertIn("pruned --only name(s)", only.stderr)
        self.assertNotIn("unknown", only.stderr)


def printed_tables(stdout: str) -> list[dict]:
    """The [[skills.config]] tables --print-codex-config printed, parsed as Codex parses config.toml."""
    return tomllib.loads(stdout).get("skills", {}).get("config", [])


class PrintCodexConfigTests(InstallSkillsTestCase):
    """--print-codex-config keys each table by the installed SKILL.md path, never by name. Codex applies a
    name rule to every loaded skill of that name (openai/codex rust-v0.159.2
    codex-rs/config/src/skills_config.rs L109-119), its bundled .system copy included, and a path rule to the
    one skill whose canonical path_to_skills_md it names (codex-rs/ext/skills/src/host_service.rs L366-371,
    host_outcome.rs L52-54). skills 1.7.0 installs a global Codex skill only at the canonical
    ~/.agents/skills/<name> (vercel-labs/skills@7407f389 src/installer.ts L392-402), which Codex loads from its
    $HOME/.agents/skills root (codex-rs/ext/skills/src/host_roots.rs L103-108)."""

    def skill_md(self, name: str, root: Path | None = None) -> str:
        return str((root or self.home) / ".agents" / "skills" / name / "SKILL.md")

    def test_prints_only_codex_disabled_skills_and_never_touches_the_binary(self):
        on_skill = make_skill("codex-on", "# on\n", tree_sha("on"), codex_enabled=True)
        off_skill = make_skill("codex-off", "# off\n", tree_sha("off"), codex_enabled=False)
        manifest = self.write_manifest([on_skill, off_skill])
        result = self.run_install(manifest, "--print-codex-config",
                                  fake_bin=Path("/nonexistent/skills-binary"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(printed_tables(result.stdout), [{"path": self.skill_md("codex-off"), "enabled": False}])
        self.assertNotIn("codex-on", result.stdout)
        self.assertNotRegex(result.stdout, r"(?m)^name = ")

    def test_multiple_disabled_skills_each_get_their_own_table(self):
        skills = [make_skill(f"off-{i}", f"# {i}\n", tree_sha(f"off-{i}"), codex_enabled=False)
                  for i in range(3)]
        manifest = self.write_manifest(skills)
        result = self.run_install(manifest, "--print-codex-config")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("[[skills.config]]"), 3)
        self.assertEqual(printed_tables(result.stdout),
                         [{"path": self.skill_md(f"off-{i}"), "enabled": False} for i in range(3)])

    def test_skill_creator_is_a_claude_code_copy_and_gets_no_codex_rule(self):
        # Codex ships its own .system/skill-creator (codex-rs/skills/src/assets/samples/skill-creator/SKILL.md L2
        # at rust-v0.159.2), so a name rule would hide the bundled copy along with the pinned one. Since 2026-10-03 the
        # manifest's skill-creator is a copy for Claude Code only (agents ["claude-code"], copy true), never installed
        # where Codex loads skills, so no rule is printed for it at all, by path or by name.
        result = self.run_install(ADOPTION_MANIFEST, "--print-codex-config")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        tables = printed_tables(result.stdout)
        self.assertNotIn({"path": self.skill_md("skill-creator"), "enabled": False}, tables)
        self.assertEqual([table for table in tables if set(table) != {"path", "enabled"}], [])
        self.assertNotRegex(result.stdout, r"(?m)^name = ")
        self.assertNotIn("skill-creator", result.stdout)
        # The same entry as a shared skill (agents and copy left out) is still disabled by its path.
        manifest = json.loads(ADOPTION_MANIFEST.read_text())
        shared = next(s for s in manifest["skills"] if s["name"] == "skill-creator")
        shared.pop("agents")
        shared.pop("copy")
        path = self.tmp_path / "shared-manifest.json"
        path.write_text(json.dumps(manifest))
        tables = printed_tables(self.run_install(path, "--print-codex-config").stdout)
        self.assertIn({"path": self.skill_md("skill-creator"), "enabled": False}, tables)

    def test_path_is_joined_as_the_cli_joins_the_canonical_folder_and_quoted_for_toml(self):
        # The canonical folder is path.join(os.homedir(), ".agents", "skills", name) (dist/cli.mjs L2208-2210), which
        # collapses a ".." lexically; a quote or backslash in the path stays a valid TOML basic string.
        home = self.tmp_path / 'we"ird\\home'
        home.mkdir()
        off_skill = make_skill("off-skill", "# off\n", tree_sha("off"), codex_enabled=False)
        result = self.run_install(self.write_manifest([off_skill]), "--print-codex-config",
                                  home_arg=str(self.tmp_path / "missing" / ".." / home.name))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(printed_tables(result.stdout), [{"path": self.skill_md("off-skill", home), "enabled": False}])
        self.assertFalse((self.tmp_path / "missing").exists())

    def test_a_project_scoped_manifest_names_the_project_copy(self):
        off_skill = make_skill("off-skill", "# off\n", tree_sha("off"), codex_enabled=False)
        scoped = self.tmp_path / "scoped.json"
        scoped.write_text(json.dumps(dict(make_manifest([off_skill]), scope="project")))
        project = self.tmp_path / "project"
        project.mkdir()
        result = self.run_install(scoped, "--print-codex-config", "--project-dir", str(project))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(printed_tables(result.stdout),
                         [{"path": self.skill_md("off-skill", project.resolve()), "enabled": False}])
        self.assertEqual(list(project.iterdir()), [])

    def test_a_disabled_name_that_is_not_one_path_component_is_refused(self):
        off_skill = make_skill("../escape", "# off\n", tree_sha("off"), codex_enabled=False)
        result = self.run_install(self.write_manifest([off_skill]), "--print-codex-config")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("[[skills.config]]", result.stdout)


class ReuseRefGateTests(InstallSkillsTestCase):
    """A `reuse_ref` entry takes main's per-skill gates when the manifest is read.

    The references resolve against this checkout's adoption/skills/manifest.json, so the
    fixtures pick real entries by their current gate instead of hard-coding a name. An entry
    is matched there by its skill name, not by an array index.
    """

    def reuse(self, predicate) -> dict:
        old = next(s for s in json.loads(ADOPTION_MANIFEST.read_text())["skills"] if predicate(s))
        entry = {key: old[key] for key in REUSE_PIN_KEYS}
        entry.update(status="trial", reuse_ref=ADOPTION_REF)
        return entry

    def test_runtime_manifest_still_loads_after_main_reorders_or_inserts_entries(self):
        base = json.loads(ADOPTION_MANIFEST.read_text())
        gates = {s["name"]: (s.get("codex_enabled"), s.get("claude_listing")) for s in base["skills"]}
        base["skills"].reverse()
        base["skills"].insert(0, dict(base["skills"][0], name="inserted-main-skill"))
        root = self.tmp_path / "reordered-root"
        (root / "adoption" / "skills").mkdir(parents=True)
        (root / "adoption" / "skills" / "manifest.json").write_text(json.dumps(base))
        manifest = load_installer_module().load_manifest(RUNTIME_MANIFEST, root=root)
        reused = [s for s in manifest["skills"] if "reuse_ref" in s]
        self.assertTrue(reused)
        for skill in reused:
            self.assertEqual((skill.get("codex_enabled"), skill.get("claude_listing")), gates[skill["name"]],
                             skill["name"])

    def test_reuse_ref_without_a_same_named_main_skill_is_refused(self):
        entry = dict(self.reuse(lambda s: True), name="not-in-main")
        result = self.run_install(self.write_manifest([entry]), "--print-codex-config")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("not-in-main", result.stderr)
        self.assertIn("names no single", result.stderr)

    def test_reused_skill_that_main_disables_for_codex_comes_out_disabled(self):
        off = self.reuse(lambda s: s.get("codex_enabled") is False)
        on = self.reuse(lambda s: s.get("codex_enabled") is True)
        result = self.run_install(self.write_manifest([off, on]), "--print-codex-config")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(printed_tables(result.stdout),
                         [{"path": str(self.home / ".agents" / "skills" / off["name"] / "SKILL.md"),
                           "enabled": False}])

    def test_reused_entry_that_restates_a_gate_is_refused(self):
        entry = self.reuse(lambda s: s.get("codex_enabled") is False)
        entry["codex_enabled"] = True  # would silently widen main's Codex gate
        result = self.run_install(self.write_manifest([entry]), "--print-codex-config")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("restates main's codex_enabled", result.stderr)
        self.assertNotIn("[[skills.config]]", result.stdout)

    def test_reuse_ref_that_drifted_from_main_is_refused_before_any_install(self):
        entry = self.reuse(lambda s: s.get("codex_enabled") is False)
        entry["tree_sha"] = tree_sha("drifted")
        manifest = self.write_manifest([entry])
        printed = self.run_install(manifest, "--print-codex-config")
        self.assertEqual(printed.returncode, 1, printed.stdout + printed.stderr)
        self.assertIn("reuse_ref", printed.stderr)
        fake_bin = write_fake_skills_bin(self.bin_dir, {})
        installed = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(installed.returncode, 1, installed.stdout + installed.stderr)
        self.assertEqual(calls_log(fake_bin), [])  # refused before even the version check


class VersionRefusalTests(InstallSkillsTestCase):
    def test_wrong_version_is_refused_before_any_skill_is_touched(self):
        skill = make_skill("irrelevant", "# x\n", tree_sha("irrelevant"))
        fake_bin = write_fake_skills_bin(self.bin_dir, {}, version="1.6.0")
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(PINNED_VERSION, result.stderr)
        self.assertIn(INSTALL_HINT, result.stderr)
        self.assertEqual([c[0] for c in calls_log(fake_bin)], ["--version"])

    def test_missing_binary_is_refused_with_the_install_hint(self):
        skill = make_skill("irrelevant", "# x\n", tree_sha("irrelevant"))
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, fake_bin=Path("/nonexistent/skills-binary"))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(INSTALL_HINT, result.stderr)


class OnlyFilterTests(InstallSkillsTestCase):
    def test_only_limits_processing_to_the_named_skill(self):
        wanted = make_skill("wanted", "# wanted\n", tree_sha("wanted"))
        other = make_skill("other", "# other\n", tree_sha("other"))
        fake_bin = write_fake_skills_bin(self.bin_dir, {
            "wanted": {"skill_md": "# wanted\n", "tree_sha": tree_sha("wanted")},
            "other": {"skill_md": "# other\n", "tree_sha": tree_sha("other")},
        })
        manifest = self.write_manifest([wanted, other])
        result = self.run_install(manifest, "--only", "wanted", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.home / ".agents" / "skills" / "wanted").exists())
        self.assertFalse((self.home / ".agents" / "skills" / "other").exists())

    def test_unknown_only_name_fails_cleanly(self):
        skill = make_skill("known", "# known\n", tree_sha("known"))
        fake_bin = write_fake_skills_bin(self.bin_dir, {})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, "--only", "nope", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("nope", result.stderr)
        self.assertEqual(calls_log(fake_bin), [])  # rejected before even the version check


class JsonOutputTests(InstallSkillsTestCase):
    def test_json_output_is_compact_and_value_free(self):
        content = "# json skill\n"
        skill = make_skill("json-skill", content, tree_sha("json"))
        fake_bin = write_fake_skills_bin(
            self.bin_dir, {"json-skill": {"skill_md": content, "tree_sha": tree_sha("json")}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, "--json", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["skills"]["json-skill"], "installed")
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["dry_run"])
        # No absolute host path, sha256 or URL leaks into the compact summary.
        self.assertNotIn(str(self.home), result.stdout)
        self.assertNotIn(skill["skill_md_sha256"], result.stdout)
        self.assertNotIn(skill["url"], result.stdout)


class HeldAndCopyTests(InstallSkillsTestCase):
    """A held skill is never installed (adoption/skills/lifecycle.md, Held); a Claude-Code-only copy entry installs with
    --copy -a claude-code into Claude Code's own folder and keeps no shared canonical folder (wave-2 skills ruling,
    change 6)."""

    def test_a_held_skill_is_skipped_and_only_refuses_it(self):
        held = dict(make_skill("held-skill", "# held\n", tree_sha("held")), status="held", held_for="a measurement")
        kept = make_skill("kept-skill", "# kept\n", tree_sha("kept"))
        fake_bin = write_fake_skills_bin(self.bin_dir, {"kept-skill": {"skill_md": "# kept\n", "tree_sha": tree_sha("kept")}})
        manifest = self.write_manifest([held, kept])
        result = self.run_install(manifest, "--json", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {"kept-skill": "installed"})
        self.assertFalse(any("held-skill" in call for call in calls_log(fake_bin)))
        refused = self.run_install(manifest, "--only", "held-skill", fake_bin=fake_bin)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("held --only name(s), not installed while held: ['held-skill']", refused.stderr)

    def test_a_claude_code_copy_installs_into_claude_codes_folder_only(self):
        skill = dict(make_skill("copy-skill", "# copy\n", tree_sha("copy"), codex_enabled=False),
                     agents=["claude-code"], copy=True)
        fake_bin = write_fake_skills_bin(self.bin_dir, {"copy-skill": {"skill_md": "# copy\n", "tree_sha": tree_sha("copy")}})
        manifest = self.write_manifest([skill])
        result = self.run_install(manifest, "--json", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["skills"], {"copy-skill": "installed"})
        adds = [call for call in calls_log(fake_bin) if call and call[0] == "add"]
        self.assertEqual(adds, [["add", skill["url"], "--skill", "copy-skill", "-g", "-y", "--copy", "-a", "claude-code"]])
        copy_dir = self.home / ".claude" / "skills" / "copy-skill"
        self.assertTrue(copy_dir.is_dir() and not copy_dir.is_symlink())
        self.assertFalse((self.home / ".agents" / "skills" / "copy-skill").exists())
        # Idempotent: the second run reads the copy back and never runs the binary's add.
        again = self.run_install(manifest, "--json", fake_bin=fake_bin)
        self.assertEqual(json.loads(again.stdout)["skills"], {"copy-skill": "ok"})
        self.assertEqual(len([call for call in calls_log(fake_bin) if call and call[0] == "add"]), 1)
        # The Codex tables name nothing for an entry Codex never receives.
        printed = self.run_install(manifest, "--print-codex-config")
        self.assertEqual((printed.returncode, printed.stdout.strip()), (0, ""))

    def test_a_copy_that_does_not_verify_is_removed_for_claude_code_only(self):
        skill = dict(make_skill("copy-skill", "# copy\n", tree_sha("copy"), codex_enabled=False),
                     agents=["claude-code"], copy=True)
        fake_bin = write_fake_skills_bin(self.bin_dir, {"copy-skill": {"skill_md": "# other\n", "tree_sha": tree_sha("copy")}})
        result = self.run_install(self.write_manifest([skill]), "--json", fake_bin=fake_bin)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["skills"], {"copy-skill": "rolled-back"})
        removes = [call for call in calls_log(fake_bin) if call and call[0] == "remove"]
        self.assertEqual(removes, [["remove", "copy-skill", "-g", "-y", "-a", "claude-code"]])
        self.assertFalse((self.home / ".claude" / "skills" / "copy-skill").exists())

    def test_a_copy_is_ok_only_as_claude_codes_own_folder_with_no_shared_entry(self):
        """Finding 3 of the Codex root lane's read of b6828c7d: --check-only, which the install plan's smoke check runs, took
        the pinned bytes and a matching lock entry for 'ok' wherever the Claude entry led. A Claude-Code-only copy is 'ok'
        only as a real folder in Claude Code's skills folder with no entry of its name in the shared canonical folder,
        where Codex loads skills (scripts/skills_status.py fails the other layouts too). A link at the Claude entry, or a
        shared same-name entry (a dangling link included), is 'misplaced' in every mode, exits 1, runs no add or remove and
        changes nothing. Every layout holds the same pinned bytes and lock entry, so placement is the one difference: the
        real folder is the positive control, and the link and shared layouts are the negative controls that the earlier
        classify_skill passed as 'ok'."""
        text = "# copy\n"
        skill = dict(make_skill("copy-skill", text, tree_sha("copy"), codex_enabled=False), agents=["claude-code"],
                     copy=True)
        fake_bin = write_fake_skills_bin(self.bin_dir, {"copy-skill": {"skill_md": text, "tree_sha": tree_sha("copy")}})
        manifest = self.write_manifest([skill])
        claude = self.home / ".claude" / "skills" / "copy-skill"
        shared = self.home / ".agents" / "skills" / "copy-skill"

        def folder(path):
            path.mkdir(parents=True)
            (path / "SKILL.md").write_text(text, encoding="utf-8")

        def layout(kind):
            for path in (claude, shared):
                if path.is_symlink():
                    path.unlink()
                elif path.exists():
                    shutil.rmtree(path)
            if kind == "link":   # a shared install's layout: the canonical folder, and a relative link onto it
                folder(shared)
                claude.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(os.path.relpath(shared, claude.parent), claude)
            else:
                folder(claude)
                if kind == "shared":
                    folder(shared)
                elif kind == "dangling":
                    shared.parent.mkdir(parents=True, exist_ok=True)
                    os.symlink("no-such-folder", shared)
            lock = self.home / ".agents" / ".skill-lock.json"   # the entry the CLI's add writes (fake bin above)
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text(json.dumps({"lockfileVersion": 3, "skills": {"copy-skill": {
                "source": "github", "sourceType": "github", "sourceUrl": skill["url"], "skillPath": "copy-skill",
                "skillFolderHash": tree_sha("copy")}}}), encoding="utf-8")

        def snapshot():
            return {str(path.relative_to(self.home)): os.readlink(path) if path.is_symlink() else
                    path.read_bytes() if path.is_file() else None for path in sorted(self.home.rglob("*"))}

        layout("own")
        result = self.run_install(manifest, "--check-only", "--json", fake_bin=fake_bin)
        self.assertEqual((result.returncode, json.loads(result.stdout)["skills"]), (0, {"copy-skill": "ok"}), result.stderr)
        for kind, problem in (("link", f"{claude} is a link, not Claude Code's own copy"),
                              ("shared", f"{shared} exists, in the shared folder where Codex loads skills"),
                              ("dangling", f"{shared} exists, in the shared folder where Codex loads skills")):
            for mode in (("--check-only",), ("--dry-run",), (), ("--force",)):
                with self.subTest(layout=kind, mode=mode):
                    layout(kind)
                    before = snapshot()
                    result = self.run_install(manifest, *mode, "--json", fake_bin=fake_bin)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertEqual(json.loads(result.stdout)["skills"], {"copy-skill": "misplaced"})
                    self.assertIn(f"copy-skill: misplaced -- {problem}", result.stderr)
                    self.assertEqual(snapshot(), before)
        self.assertFalse([call for call in calls_log(fake_bin) if call and call[0] in ("add", "remove")])

    def test_a_copy_for_both_agents_or_a_malformed_agent_list_is_refused_before_any_add(self):
        for name, extra, message in (
                ("both", {"copy": True}, "copy installs only into Claude Code's own folder"),
                ("unknown", {"agents": ["cursor"]}, "agents names claude-code and/or codex, each once"),
                ("twice", {"agents": ["codex", "codex"]}, "agents names claude-code and/or codex, each once")):
            with self.subTest(case=name):
                skill = dict(make_skill(f"{name}-skill", "# x\n", tree_sha(name)), **extra)
                fake_bin = write_fake_skills_bin(self.bin_dir, {})
                result = self.run_install(self.write_manifest([skill]), fake_bin=fake_bin)
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertFalse([call for call in calls_log(fake_bin) if call and call[0] == "add"])


class ForeignContentTests(InstallSkillsTestCase):
    """F3 (research-queue row 42): no content the installer did not write is removed without --force.

    The add recreates the canonical folder from nothing (vercel-labs/skills@7407f3893ad4dceab546ac002c3ef806e4000c73, src/installer.ts L193-200 and L389-390), so a file beside a pinned
    SKILL.md that the CLI would not write is lost with the folder, and so is an edited support file. The installer asks the question scripts/skills_status.py already asks of an
    installed folder (check_folder_tree): does its git tree SHA, with the regenerable runtime-artifact directories left out, equal the manifest's tree_sha? A folder of SKILL.md alone has
    nothing else to lose. Fake CLI fixtures with real git tree SHAs: integration fixtures, not a native run."""

    NAME = "multi-file-skill"
    CONTENT = "# Multi-file skill\n"
    PINNED = {"references/guide.md": "# Guide\n", "scripts/run.py": "print('pinned')\n"}

    def setUp(self):
        super().setUp()
        self.tree = pinned_tree_sha({"SKILL.md": self.CONTENT, **self.PINNED})
        self.skill = make_skill(self.NAME, self.CONTENT, self.tree)
        self.fake_bin = write_fake_skills_bin(self.bin_dir, {self.NAME: {"skill_md": self.CONTENT, "tree_sha": self.tree, "files": self.PINNED}})
        self.manifest = self.write_manifest([self.skill])
        self.folder = self.home / ".agents" / "skills" / self.NAME

    def install(self, *flags, manifest=None, fake_bin=None, env=None):
        return self.run_install(manifest or self.manifest, *flags, "--json", fake_bin=fake_bin or self.fake_bin, env=env)

    def states(self, *flags, **kwargs):
        result = self.install(*flags, **kwargs)
        return result, (json.loads(result.stdout)["skills"] if result.stdout.strip() else None)

    def add_calls(self, fake_bin=None):
        return [call for call in calls_log(fake_bin or self.fake_bin) if call and call[0] == "add"]

    def canonical(self, files=None, skill_md=None, folder=None):
        folder = folder or self.folder
        for rel, text in {"SKILL.md": self.CONTENT if skill_md is None else skill_md, **(self.PINNED if files is None else files)}.items():
            (folder / rel).parent.mkdir(parents=True, exist_ok=True)
            (folder / rel).write_text(text, encoding="utf-8")

    def lock(self, tree):
        (self.home / ".agents").mkdir(exist_ok=True)
        (self.home / ".agents" / ".skill-lock.json").write_text(json.dumps({"lockfileVersion": 3, "skills": {self.NAME: {"skillFolderHash": tree}}}))

    @staticmethod
    def snapshot(folder):
        return {str(p.relative_to(folder)): (os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None) for p in sorted(folder.rglob("*"))}

    def assert_protected_then_replaced_by_force(self):
        """check-only and an ordinary run refuse and say why; nothing is touched and the add is not reached; --force then writes the pinned folder alone."""
        before = self.snapshot(self.folder)
        result, skills = self.states("--check-only")
        self.assertEqual((result.returncode, skills), (1, {self.NAME: "local-modified"}), result.stdout + result.stderr)
        result, skills = self.states()
        self.assertEqual((result.returncode, skills), (1, {self.NAME: "local-modified"}), result.stdout + result.stderr)
        self.assertIn(str(self.folder), result.stderr)
        self.assertIn("not the pinned tree", result.stderr)
        self.assertIn(self.tree[:12], result.stderr)
        self.assertEqual(self.add_calls(), [])
        self.assertEqual(self.snapshot(self.folder), before)
        forced, skills = self.states("--force")
        self.assertEqual((forced.returncode, skills), (0, {self.NAME: "installed"}), forced.stdout + forced.stderr)
        self.assertEqual(len(self.add_calls()), 1)
        self.assertEqual(sorted(k for k, v in self.snapshot(self.folder).items() if v is not None), sorted(["SKILL.md", *self.PINNED]))

    # ---- an unlocked canonical folder whose SKILL.md is the pinned one
    def test_an_unlocked_folder_with_the_pinned_files_and_one_more_is_protected(self):
        self.canonical()
        (self.folder / "local-work.txt").write_text("work that exists nowhere else\n", encoding="utf-8")
        self.assert_protected_then_replaced_by_force()

    def test_an_unlocked_folder_with_an_edited_support_file_is_protected(self):
        self.canonical({**self.PINNED, "references/guide.md": "# Guide, with my notes\n"})
        self.assert_protected_then_replaced_by_force()

    def test_a_folder_that_lacks_a_pinned_file_is_not_the_pinned_tree_either(self):
        """Nothing is lost by adding it back, but the comparison is the tree's: a missing file is repaired by --force (the status check calls this folder drift too)."""
        self.canonical({"references/guide.md": self.PINNED["references/guide.md"]})
        self.assert_protected_then_replaced_by_force()

    def test_a_git_directory_a_metadata_file_and_a_linked_directory_are_content(self):
        makers = (("a git directory", lambda f: (f / ".git").mkdir() or (f / ".git" / "HEAD").write_text("ref: refs/heads/main\n")),
                  ("a metadata.json file", lambda f: (f / "metadata.json").write_text("{}", encoding="utf-8")),
                  ("a linked directory", lambda f: os.symlink(self.tmp_path, f / "linked")),
                  ("a linked file", lambda f: os.symlink(f / "SKILL.md", f / "alias.md")))
        for label, make in makers:
            with self.subTest(foreign=label):
                shutil.rmtree(self.folder, ignore_errors=True)
                self.canonical()
                make(self.folder)
                result, skills = self.states("--check-only")
                self.assertEqual((result.returncode, skills), (1, {self.NAME: "local-modified"}), label)

    def test_an_unlocked_folder_that_is_exactly_the_pinned_one_is_adopted_without_force(self):
        self.canonical()
        result, skills = self.states()
        self.assertEqual((result.returncode, skills), (0, {self.NAME: "installed"}), result.stdout + result.stderr)
        self.assertEqual(len(self.add_calls()), 1)

    def test_the_directories_a_skills_own_tooling_regenerates_are_not_content_to_protect(self):
        for directory in ("scripts/__pycache__", ".venv", "node_modules", ".pytest_cache"):
            with self.subTest(directory=directory):
                shutil.rmtree(self.folder, ignore_errors=True)
                self.canonical()
                (self.folder / directory).mkdir(parents=True)
                (self.folder / directory / "artifact.bin").write_bytes(b"regenerated")
                result, skills = self.states("--check-only")
                self.assertEqual((result.returncode, skills), (1, {self.NAME: "missing-or-drifted"}), (directory, result.stdout))  # install-bound, not refused

    def test_a_file_or_a_link_named_like_a_regenerated_directory_is_content(self):
        """The name alone is not enough: a regular file `.venv`, a link `node_modules` or a file `scripts/__pycache__` is something the add would delete (the Codex review in GitHub, #1035)."""
        makers = (("a file named .venv", lambda f: (f / ".venv").write_text("mine\n", encoding="utf-8")),
                  ("a file named .venv below scripts", lambda f: (f / "scripts" / ".venv").write_text("mine\n", encoding="utf-8")),
                  ("a link named .venv", lambda f: os.symlink("SKILL.md", f / ".venv")),
                  ("a link named node_modules", lambda f: os.symlink(self.tmp_path, f / "node_modules")),
                  ("a file named __pycache__ below scripts", lambda f: (f / "scripts" / "__pycache__").write_text("mine\n", encoding="utf-8")))
        for label, make in makers:
            with self.subTest(foreign=label):
                shutil.rmtree(self.folder, ignore_errors=True)
                self.canonical()
                make(self.folder)
                result, skills = self.states("--check-only")
                self.assertEqual((result.returncode, skills), (1, {self.NAME: "local-modified"}), label)

    def test_an_entry_a_git_tree_cannot_hold_is_content_too(self):
        """An empty directory and a special file have no entry in the pinned tree and no bytes in a hash, and the add deletes them (the Codex review in GitHub, #1035, round two)."""
        makers = (("an empty directory", lambda f: (f / "notes").mkdir()), ("an empty directory below references", lambda f: (f / "references" / "empty").mkdir()),
                  ("a directory that holds only a regenerated one", lambda f: (f / "cache-holder" / "__pycache__").mkdir(parents=True)), ("a named pipe", lambda f: os.mkfifo(f / "pipe")))
        for label, make in makers:
            with self.subTest(foreign=label):
                shutil.rmtree(self.folder, ignore_errors=True)
                self.canonical()
                make(self.folder)
                result, skills = self.states("--check-only")
                self.assertEqual((result.returncode, skills), (1, {self.NAME: "local-modified"}), label)
                result, skills = self.states()
                self.assertEqual((result.returncode, skills), (1, {self.NAME: "local-modified"}), label)
                self.assertIn("an empty directory or a special file", result.stderr)
                self.assertEqual(self.add_calls(), [])
        shutil.rmtree(self.folder, ignore_errors=True)
        self.canonical()
        (self.folder / ".venv").mkdir()
        result, skills = self.states("--check-only")
        self.assertEqual((result.returncode, skills), (1, {self.NAME: "missing-or-drifted"}), "an empty regenerated directory is not content to protect")

    def test_a_skill_md_that_is_a_link_is_not_the_pinned_file_even_when_its_bytes_are(self):
        """The SKILL.md check follows a link; the tree comparison does not (a link is a tree entry of its own kind), so a folder of one linked SKILL.md is protected too."""
        shutil.rmtree(self.folder, ignore_errors=True)
        self.folder.mkdir(parents=True)
        elsewhere = self.tmp_path / "managed-elsewhere.md"
        elsewhere.write_text(self.CONTENT, encoding="utf-8")
        os.symlink(elsewhere, self.folder / "SKILL.md")
        result, skills = self.states("--check-only")
        self.assertEqual((result.returncode, skills), (1, {self.NAME: "local-modified"}))

    # ---- a locked folder
    def test_a_locked_folder_at_the_pin_without_its_claude_link_is_protected_from_the_repairing_add(self):
        self.lock(self.tree)
        self.canonical()
        (self.folder / "local-work.txt").write_text("work that exists nowhere else\n", encoding="utf-8")
        self.assert_protected_then_replaced_by_force()

    def test_a_locked_folder_at_the_pin_without_its_claude_link_and_without_extras_is_repaired(self):
        self.lock(self.tree)
        self.canonical()
        result, skills = self.states()
        self.assertEqual((result.returncode, skills), (0, {self.NAME: "installed"}), result.stdout + result.stderr)
        self.assertTrue((self.home / ".claude" / "skills" / self.NAME).is_symlink())

    def test_an_upgrade_over_an_older_pin_is_not_covered(self):
        """The lock proves the CLI wrote an earlier version there, and nothing offline can name that version's files, so the upgrade add runs as before (adoption/skills/lifecycle.md)."""
        self.lock(tree_sha("an older tree"))
        self.canonical()
        (self.folder / "local-work.txt").write_text("work that exists nowhere else\n", encoding="utf-8")
        result, skills = self.states()
        self.assertEqual((result.returncode, skills), (0, {self.NAME: "installed"}), result.stdout + result.stderr)
        self.assertFalse((self.folder / "local-work.txt").exists(), "the boundary this record states: an upgrade replaces the folder")

    def test_a_complete_locked_install_stays_ok_whatever_the_folder_holds(self):
        """No add runs for an ok install, so nothing is deleted and the folder is not judged (scripts/skills_status.py reports drift separately)."""
        self.lock(self.tree)
        self.canonical()
        (self.folder / "local-work.txt").write_text("kept: no add runs for an ok install\n", encoding="utf-8")
        link_dir = self.home / ".claude" / "skills"
        link_dir.mkdir(parents=True)
        os.symlink(os.path.relpath(self.folder, link_dir), link_dir / self.NAME)
        result, skills = self.states("--check-only")
        self.assertEqual((result.returncode, skills), (0, {self.NAME: "ok"}))

    # ---- the other places a canonical folder is recreated
    def test_a_claude_code_copy_entry_protects_the_claude_folder(self):
        files = {"scripts/x.py": "x = 1\n"}
        tree = pinned_tree_sha({"SKILL.md": "# Copy\n", **files})
        skill = dict(make_skill("copy-skill", "# Copy\n", tree, codex_enabled=False), agents=["claude-code"], copy=True)
        fake_bin = write_fake_skills_bin(self.bin_dir, {"copy-skill": {"skill_md": "# Copy\n", "tree_sha": tree, "files": files}})
        manifest = self.write_manifest([skill])
        folder = self.home / ".claude" / "skills" / "copy-skill"
        self.canonical(files, skill_md="# Copy\n", folder=folder)
        (folder / "notes.txt").write_text("mine\n", encoding="utf-8")
        result, skills = self.states("--check-only", manifest=manifest, fake_bin=fake_bin)
        self.assertEqual((result.returncode, skills), (1, {"copy-skill": "local-modified"}), result.stdout + result.stderr)
        (folder / "notes.txt").unlink()
        result, skills = self.states(manifest=manifest, fake_bin=fake_bin)
        self.assertEqual((result.returncode, skills), (0, {"copy-skill": "installed"}), result.stdout + result.stderr)

    def test_a_project_canonical_folder_is_protected_too(self):
        project = self.tmp_path / "project"
        project.mkdir()
        self.canonical(folder=project / ".agents" / "skills" / self.NAME)
        (project / ".agents" / "skills" / self.NAME / "local-work.txt").write_text("work that exists nowhere else\n", encoding="utf-8")
        gh = self.bin_dir / "gh"  # a project run verifies the pinned source tree through gh before it classifies anything
        gh.write_text("#!/usr/bin/env python3\nimport json\nprint(json.dumps({'truncated': False, 'tree': [{'path': " + repr(self.skill["path"]) + ", 'type': 'tree', 'sha': " + repr(self.tree) + "}]}))\n")
        gh.chmod(0o755)
        result, skills = self.states("--project-dir", str(project), "--agent", "universal", "--check-only", env={"PATH": str(self.bin_dir) + os.pathsep + os.environ["PATH"]})
        self.assertEqual((result.returncode, skills), (1, {self.NAME: "local-modified"}), result.stdout + result.stderr)
        self.assertEqual(self.add_calls(), [])

    def test_a_project_folder_locked_at_the_pin_without_its_claude_target_is_protected_from_the_repairing_add(self):
        """With --agent claude-code the project lock, the pinned tree and the pinned SKILL.md all match and only .claude/skills/<name> is missing: the add that makes it recreates the canonical folder
        (the Codex review in GitHub, #1035, P1)."""
        project = self.tmp_path / "project"
        folder = project / ".agents" / "skills" / self.NAME
        project.mkdir()
        self.canonical(folder=folder)
        (project / "skills-lock.json").write_text(json.dumps({"version": 1, "skills": {self.NAME: {
            "source": self.skill["source"], "sourceType": "github", "ref": self.skill["ref"], "skillPath": self.skill["path"] + "/SKILL.md", "computedHash": "a" * 64}}}))
        gh = self.bin_dir / "gh"
        gh.write_text("#!/usr/bin/env python3\nimport json\nprint(json.dumps({'truncated': False, 'tree': [{'path': " + repr(self.skill["path"]) + ", 'type': 'tree', 'sha': " + repr(self.tree) + "}]}))\n")
        gh.chmod(0o755)
        env = {"PATH": str(self.bin_dir) + os.pathsep + os.environ["PATH"]}
        flags = ("--project-dir", str(project), "--agent", "claude-code", "--check-only")
        result, skills = self.states(*flags, env=env)
        self.assertEqual((result.returncode, skills), (1, {self.NAME: "missing-or-drifted"}), "the pinned folder alone: the repair is allowed")
        (folder / "local-work.txt").write_text("work that exists nowhere else\n", encoding="utf-8")
        result, skills = self.states(*flags, env=env)
        self.assertEqual((result.returncode, skills), (1, {self.NAME: "local-modified"}), result.stdout + result.stderr)

    # ---- a locked folder at the pin whose SKILL.md was edited: the same add recreates the folder
    def locked_global_install(self):
        """A complete locked install at the pin: the lock names the pinned tree, the folder is the pinned tree, the Claude link is in place."""
        self.lock(self.tree)
        self.canonical()
        link_dir = self.home / ".claude" / "skills"
        link_dir.mkdir(parents=True, exist_ok=True)
        os.symlink(os.path.relpath(self.folder, link_dir), link_dir / self.NAME)

    def test_a_locked_install_at_the_pin_with_an_edited_skill_md_is_protected_from_the_add(self):
        """Second GPT read of #1035 at 9a77a96e (~/.cache/ns2604-gpt-reads/fix1-pr1035-9a77a96e8/VERDICT.md, blocker 1): the lock names the pinned tree, SKILL.md is edited, md_matches is False, and the early
        `install` let the add delete the edit and every extra file (vercel-labs/skills@7407f389 src/installer.ts L195, called at L389). The folder must be the pinned tree before every add over it."""
        edits = (("an edited SKILL.md", lambda f: (f / "SKILL.md").write_text(self.CONTENT + "a local instruction\n", encoding="utf-8")),
                 ("an edited SKILL.md and an extra file", lambda f: ((f / "SKILL.md").write_text(self.CONTENT + "a local instruction\n", encoding="utf-8"), (f / "local-work.txt").write_text("mine\n", encoding="utf-8"))),
                 ("no SKILL.md and an extra file", lambda f: ((f / "SKILL.md").unlink(), (f / "local-work.txt").write_text("mine\n", encoding="utf-8"))))
        for label, change in edits:
            with self.subTest(change=label):
                shutil.rmtree(self.home, ignore_errors=True)
                self.home.mkdir()
                (self.fake_bin.parent / "calls.log").unlink(missing_ok=True)   # each case counts its own add calls
                self.locked_global_install()
                change(self.folder)
                self.assert_protected_then_replaced_by_force()

    def test_a_locked_install_at_the_pin_with_an_edited_skill_md_and_no_link_is_protected_too(self):
        self.lock(self.tree)
        self.canonical()
        (self.folder / "SKILL.md").write_text(self.CONTENT + "a local instruction\n", encoding="utf-8")
        self.assert_protected_then_replaced_by_force()

    def test_a_locked_install_at_the_pin_whose_folder_is_gone_is_repaired_without_force(self):
        """The clean controls of the same transition: nothing to lose when the folder is missing, and the pinned folder with a missing link is repaired (test above)."""
        self.lock(self.tree)
        result, skills = self.states("--check-only")
        self.assertEqual((result.returncode, skills), (1, {self.NAME: "missing-or-drifted"}), result.stdout + result.stderr)
        result, skills = self.states()
        self.assertEqual((result.returncode, skills), (0, {self.NAME: "installed"}), result.stdout + result.stderr)
        self.assertEqual(len(self.add_calls()), 1)

    def test_an_upgrade_over_an_older_pin_with_an_edited_skill_md_is_still_not_covered(self):
        self.lock(tree_sha("an older tree"))
        self.canonical()
        (self.folder / "SKILL.md").write_text(self.CONTENT + "a local instruction\n", encoding="utf-8")
        result, skills = self.states()
        self.assertEqual((result.returncode, skills), (0, {self.NAME: "installed"}), result.stdout + result.stderr)

    # ---- a lock that identifies nothing is not an older pin (Astra, #1035 at 5ace90c1, blocker 1)
    def fresh_home(self):
        shutil.rmtree(self.home, ignore_errors=True)
        self.home.mkdir()
        (self.fake_bin.parent / "calls.log").unlink(missing_ok=True)   # each case counts its own add calls

    def test_a_global_lock_that_names_no_tree_is_not_an_older_pin(self):
        """Astra's read of #1035 at 5ace90c1 (~/.cache/ns2604-gpt-reads/fix2-pr1035-5ace90c12/VERDICT.md, blocker 1, one step wider; the CC asked for every lock shape): a global entry whose `skillFolderHash` is missing,
        empty or not text was read as 'the lock names another tree' and sent to `install`, so the add deleted local work (vercel-labs/skills@7407f389 src/installer.ts L195, called at L389). Only a hash that
        is another tree identifies an older pin (the documented boundary, the test after this one)."""
        entries = {"no hash": {}, "an empty hash": {"skillFolderHash": ""}, "a null hash": {"skillFolderHash": None}, "a number as hash": {"skillFolderHash": 5}, "a list as hash": {"skillFolderHash": [self.tree]}}
        for label, entry in entries.items():
            with self.subTest(lock=label):
                self.fresh_home()
                (self.home / ".agents").mkdir()
                (self.home / ".agents" / ".skill-lock.json").write_text(json.dumps({"version": 3, "skills": {self.NAME: entry}}))
                self.canonical()
                (self.folder / "local-work.txt").write_text("work that exists nowhere else\n", encoding="utf-8")
                self.assert_protected_then_replaced_by_force()
                self.fresh_home()
                (self.home / ".agents").mkdir()
                (self.home / ".agents" / ".skill-lock.json").write_text(json.dumps({"version": 3, "skills": {self.NAME: entry}}))
                self.canonical()
                result, skills = self.states("--check-only")
                self.assertEqual((result.returncode, skills), (1, {self.NAME: "missing-or-drifted"}), "the pinned folder alone: the add may normalise the lock")
                result, skills = self.states()
                self.assertEqual((result.returncode, skills), (0, {self.NAME: "installed"}), result.stdout + result.stderr)
                self.assertEqual(len(self.add_calls()), 1)
                self.fresh_home()
                (self.home / ".agents").mkdir()
                (self.home / ".agents" / ".skill-lock.json").write_text(json.dumps({"version": 3, "skills": {self.NAME: entry}}))
                link_dir = self.home / ".claude" / "skills"
                link_dir.mkdir(parents=True)
                self.canonical()
                os.symlink(os.path.relpath(self.folder, link_dir), link_dir / self.NAME)
                result, skills = self.states("--check-only")
                self.assertEqual((result.returncode, skills), (1, {self.NAME: "missing-or-drifted"}), "linked and pinned, but the lock names no tree: not ok, the add writes it whole")
                shutil.rmtree(self.folder)
                result, skills = self.states("--check-only")
                self.assertEqual((result.returncode, skills), (1, {self.NAME: "missing-or-drifted"}), "a folder that is gone is a clean repair, not a refusal")
                result, skills = self.states()
                self.assertEqual((result.returncode, skills), (0, {self.NAME: "installed"}), result.stdout + result.stderr)

    def test_a_global_lock_that_names_another_tree_stays_an_upgrade_over_an_older_pin(self):
        """The control of the test above and the documented boundary: a hash that is another tree says the CLI wrote another version there."""
        self.lock(tree_sha("an older tree"))
        self.canonical()
        (self.folder / "local-work.txt").write_text("work that exists nowhere else\n", encoding="utf-8")
        result, skills = self.states()
        self.assertEqual((result.returncode, skills), (0, {self.NAME: "installed"}), result.stdout + result.stderr)

    PROJECT_LOCK_SHAPES = {
        "no skillPath (a lock written before the field existed)": lambda e: e.pop("skillPath"),
        "no ref (a source that is not a repository, or an install without a ref)": lambda e: e.pop("ref"),
        "an empty ref": lambda e: e.update(ref=""),
        "a ref that is not text": lambda e: e.update(ref=7),
        "no computedHash": lambda e: e.pop("computedHash"),
        "an empty computedHash": lambda e: e.update(computedHash=""),
        "a 63-character computedHash": lambda e: e.update(computedHash="a" * 63),
        "a computedHash that is not text": lambda e: e.update(computedHash=7),
        "another skillPath": lambda e: e.update(skillPath="skills/another/SKILL.md"),
        "a source that is not a repository, as the CLI writes it": lambda e: (e.update(sourceType="local", source="../source/" + "native-demo-skill"), e.pop("ref"), e.pop("skillPath")),
        "another source": lambda e: e.update(source="someone/else"),
        "another source at another ref (a revision of something else is no older pin of this skill)": lambda e: e.update(source="someone/else", ref="b" * 40),
        "no sourceType": lambda e: e.pop("sourceType"),
    }

    def test_a_project_lock_that_identifies_no_older_pin_is_compared_like_an_unlocked_folder(self):
        """The same one step wider, for a project: `src/local-lock.ts` L16-L37 makes `ref` and `skillPath` optional ("optional for backward compatibility with lock files written before this field existed",
        "omitted for non-repo sources") and `computedHash` is the CLI's own hash of the folder, so an entry without them, or that names another source, says nothing about which revision wrote the folder. It
        returned `install` before the content check, for both agents, and the add deleted local work."""
        for agent in ("universal", "claude-code"):
            for label, change in self.PROJECT_LOCK_SHAPES.items():
                with self.subTest(agent=agent, lock=label):
                    (self.fake_bin.parent / "calls.log").unlink(missing_ok=True)
                    project, folder, env = self.project_locked_at_the_pin(change)
                    flags = ("--project-dir", str(project), "--agent", agent)
                    (folder / "local-work.txt").write_text("mine\n", encoding="utf-8")
                    result, skills = self.states(*flags, "--check-only", env=env)
                    self.assertEqual((result.returncode, skills), (1, {self.NAME: "local-modified"}), result.stdout + result.stderr)
                    result, skills = self.states(*flags, env=env)
                    self.assertEqual((result.returncode, skills), (1, {self.NAME: "local-modified"}), result.stdout + result.stderr)
                    self.assertEqual(self.add_calls(), [])
                    (folder / "local-work.txt").unlink()
                    result, skills = self.states(*flags, "--check-only", env=env)
                    self.assertEqual((result.returncode, skills), (1, {self.NAME: "missing-or-drifted"}), "the pinned folder alone, a lock that is not whole: the add normalises the lock")
                    result, skills = self.states(*flags, env=env)
                    self.assertEqual((result.returncode, skills), (0, {self.NAME: "installed"}), result.stdout + result.stderr)
                    self.assertEqual(len(self.add_calls()), 1)
                    shutil.rmtree(folder)
                    result, skills = self.states(*flags, "--check-only", env=env)
                    self.assertEqual((result.returncode, skills), (1, {self.NAME: "missing-or-drifted"}), "a folder that is gone is a clean repair, not a refusal")

    def test_a_project_lock_that_names_another_revision_of_the_source_stays_an_upgrade_over_an_older_pin(self):
        """The control and the documented boundary: the same source with another `ref` says the CLI wrote another revision there."""
        for agent in ("universal", "claude-code"):
            with self.subTest(agent=agent):
                (self.fake_bin.parent / "calls.log").unlink(missing_ok=True)
                project, folder, env = self.project_locked_at_the_pin(lambda e: e.update(ref="b" * 40))
                (folder / "local-work.txt").write_text("mine\n", encoding="utf-8")
                result, skills = self.states("--project-dir", str(project), "--agent", agent, env=env)
                self.assertEqual((result.returncode, skills), (0, {self.NAME: "installed"}), result.stdout + result.stderr)

    def test_a_complete_project_lock_at_the_pin_is_ok_and_an_incomplete_one_is_not_ok(self):
        """`ok` (no add) needs the whole entry: the same pinned folder with a lock that lacks `skillPath` is repaired once, and then the entry the CLI writes is whole."""
        for agent in ("universal", "claude-code"):
            with self.subTest(agent=agent):
                project, folder, env = self.project_locked_at_the_pin()
                if agent == "claude-code":
                    target = project / ".claude" / "skills" / self.NAME
                    target.parent.mkdir(parents=True)
                    os.symlink(os.path.relpath(folder, target.parent), target)   # the link the CLI makes
                result, skills = self.states("--project-dir", str(project), "--agent", agent, "--check-only", env=env)
                self.assertEqual((result.returncode, skills), (0, {self.NAME: "ok"}), result.stdout + result.stderr)
                project, folder, env = self.project_locked_at_the_pin(lambda e: e.pop("skillPath"))
                if agent == "claude-code":
                    target = project / ".claude" / "skills" / self.NAME
                    target.parent.mkdir(parents=True)
                    os.symlink(os.path.relpath(folder, target.parent), target)   # the link the CLI makes
                result, skills = self.states("--project-dir", str(project), "--agent", agent, "--check-only", env=env)
                self.assertEqual((result.returncode, skills), (1, {self.NAME: "missing-or-drifted"}), result.stdout + result.stderr)

    def project_locked_at_the_pin(self, change=None):
        """A project locked at the pin with the pinned folder; `change` edits the lock entry before it is written (the shapes of src/local-lock.ts L16-L37)."""
        project = self.tmp_path / "project"
        folder = project / ".agents" / "skills" / self.NAME
        shutil.rmtree(project, ignore_errors=True)
        project.mkdir()
        self.canonical(folder=folder)
        entry = {"source": self.skill["source"], "sourceType": "github", "ref": self.skill["ref"], "skillPath": self.skill["path"] + "/SKILL.md", "computedHash": "a" * 64}
        if change:
            change(entry)
        (project / "skills-lock.json").write_text(json.dumps({"version": 1, "skills": {self.NAME: entry}}))
        gh = self.bin_dir / "gh"
        gh.write_text("#!/usr/bin/env python3\nimport json\nprint(json.dumps({'truncated': False, 'tree': [{'path': " + repr(self.skill["path"]) + ", 'type': 'tree', 'sha': " + repr(self.tree) + "}]}))\n")
        gh.chmod(0o755)
        return project, folder, {"PATH": str(self.bin_dir) + os.pathsep + os.environ["PATH"]}

    def test_a_project_locked_at_the_pin_with_an_edited_skill_md_is_protected_from_the_add(self):
        """The same state in a project, for both agents (the Claude target is missing for claude-code, absent by design for universal)."""
        edits = (("an edited SKILL.md", lambda f: (f / "SKILL.md").write_text(self.CONTENT + "a local instruction\n", encoding="utf-8")),
                 ("an edited SKILL.md and an extra file", lambda f: ((f / "SKILL.md").write_text(self.CONTENT + "a local instruction\n", encoding="utf-8"), (f / "local-work.txt").write_text("mine\n", encoding="utf-8"))),
                 ("no SKILL.md and an extra file", lambda f: ((f / "SKILL.md").unlink(), (f / "local-work.txt").write_text("mine\n", encoding="utf-8"))))
        for agent in ("universal", "claude-code"):
            for label, change in edits:
                with self.subTest(agent=agent, change=label):
                    project, folder, env = self.project_locked_at_the_pin()
                    change(folder)
                    flags = ("--project-dir", str(project), "--agent", agent)
                    result, skills = self.states(*flags, "--check-only", env=env)
                    self.assertEqual((result.returncode, skills), (1, {self.NAME: "local-modified"}), result.stdout + result.stderr)
                    result, skills = self.states(*flags, env=env)
                    self.assertEqual((result.returncode, skills), (1, {self.NAME: "local-modified"}), result.stdout + result.stderr)
                    self.assertEqual(self.add_calls(), [])

    def test_a_project_locked_at_the_pin_whose_folder_is_gone_is_repaired_without_force(self):
        for agent in ("universal", "claude-code"):
            with self.subTest(agent=agent):
                project, folder, env = self.project_locked_at_the_pin()
                shutil.rmtree(folder)
                result, skills = self.states("--project-dir", str(project), "--agent", agent, "--check-only", env=env)
                self.assertEqual((result.returncode, skills), (1, {self.NAME: "missing-or-drifted"}), result.stdout + result.stderr)

    def test_a_folder_that_cannot_be_read_is_unverified_not_a_pass(self):
        module = load_installer_module()
        self.canonical()
        with mock.patch.object(module.skills_status_module(), "git_tree_sha", side_effect=PermissionError("denied")):
            with self.assertRaises(module.InstallError) as caught:
                module.unpinned_content(self.skill, self.home)
        self.assertIn("unverified (cannot read", str(caught.exception))


PINNED_SKILLS_BIN = Path(os.environ.get("SKILLS_BIN") or Path.home() / ".local" / "share" / "new-wsl-native-stack" / "tools" / "skills-1.7.0" / "bin" / "skills")


@unittest.skipUnless(PINNED_SKILLS_BIN.is_file() and os.access(PINNED_SKILLS_BIN, os.X_OK),
                     "the pinned skills CLI (SKILLS_BIN of adoption/skills/lifecycle.md) is not installed here")
class PinnedCliForeignContentTests(unittest.TestCase):
    """What the guard rests on, measured with the pinned CLI itself (skills 1.7.0, vercel-labs/skills@7407f3893ad4dceab546ac002c3ef806e4000c73): `skills add` removes the canonical folder it is about to write
    (src/installer.ts L193-200, written at L389-390), so any entry in it that the CLI would not write is lost with the folder, a regular file or a link named like a regenerated directory included. Each case runs
    the CLI offline (a local source folder, a scratch HOME and project, telemetry off) twice: the classifier must call the state local-modified before any add, and the same add on a copy of it must delete the
    entry. That control is what makes the refusal necessary; a pinned CLI that stopped deleting it would fail the control and send the guard back to review."""

    NAME = "native-demo-skill"
    FILES = {"SKILL.md": "---\nname: native-demo-skill\ndescription: A skill that the pinned CLI installs from a local folder.\n---\n# Native demo\n",
             "scripts/run.py": "print('pinned')\n"}
    EXTRAS = {"a stray file": ("local-work.txt", "file"), "a regular file named .venv": (".venv", "file"), "a regular file named .venv below scripts": ("scripts/.venv", "file"),
              "a link named .venv": (".venv", "link"), "an empty directory": ("notes", "dir"), "a named pipe": ("pipe", "fifo")}

    def setUp(self):
        self.module = load_installer_module()
        self.row = make_skill(self.NAME, self.FILES["SKILL.md"], pinned_tree_sha(self.FILES))

    def cli(self, *args, home, cwd):
        env = {"HOME": str(home), "PATH": os.environ["PATH"], "DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1"}
        return subprocess.run([str(PINNED_SKILLS_BIN), *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)

    def source(self, root):
        source = root / "source" / self.NAME
        for relative, text in self.FILES.items():
            (source / relative).parent.mkdir(parents=True, exist_ok=True)
            (source / relative).write_text(text, encoding="utf-8")
        return source

    @staticmethod
    def put(folder, relative, kind):
        entry = folder / relative
        entry.parent.mkdir(parents=True, exist_ok=True)
        if kind == "file":
            entry.write_text("unique local work\n", encoding="utf-8")
        elif kind == "link":
            os.symlink("SKILL.md", entry)
        elif kind == "dir":
            entry.mkdir()
        else:
            os.mkfifo(entry)
        return entry

    def test_an_unlocked_canonical_folder_with_an_extra_entry_is_refused_where_the_native_add_deletes_it(self):
        for label, (relative, kind) in self.EXTRAS.items():
            with self.subTest(extra=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                home = root / "home"
                home.mkdir()
                source = self.source(root)
                add = ["add", str(source), "--skill", self.NAME, "-g", "-y", "-a", "claude-code", "codex"]
                done = self.cli(*add, home=home, cwd=root)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                folder = home / ".agents" / "skills" / self.NAME
                self.assertEqual(self.module.skills_status_module().git_tree_sha(folder), self.row["tree_sha"], "the pinned CLI wrote exactly the pinned files")
                (home / ".agents" / ".skill-lock.json").unlink(missing_ok=True)   # an unlocked folder: copied by hand, or its lock lost
                link = home / ".claude" / "skills" / self.NAME
                if link.is_symlink() or link.exists():
                    link.unlink() if link.is_symlink() else shutil.rmtree(link)
                copy = root / "copy"
                shutil.copytree(home, copy / "home", symlinks=True)   # before the entry goes in: a named pipe cannot be copied
                self.put(folder, relative, kind)
                self.put(copy / "home" / ".agents" / "skills" / self.NAME, relative, kind)
                with mock.patch.dict(os.environ, {"XDG_STATE_HOME": "", "CLAUDE_CONFIG_DIR": ""}):
                    self.assertEqual(self.module.classify_skill(self.row, home), "local-modified")
                done = self.cli(*add, home=copy / "home", cwd=root)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                self.assertFalse(os.path.lexists(copy / "home" / ".agents" / "skills" / self.NAME / relative), "the control: the pinned CLI deletes it")

    def test_a_locked_install_at_the_pin_with_an_edited_skill_md_is_refused_where_the_native_add_deletes_the_edit_and_the_extra_file(self):
        """Second GPT read of #1035 at 9a77a96e (blocker 1): the same-pin lock plus an edited SKILL.md returned `install` before the content check. Global scope, the lock as the installer reads it."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir()
            source = self.source(root)
            add = ["add", str(source), "--skill", self.NAME, "-g", "-y", "-a", "claude-code", "codex"]
            done = self.cli(*add, home=home, cwd=root)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            lock_file = home / ".agents" / ".skill-lock.json"
            # An install from the manifest's GitHub source records the pinned tree here; a local source records none, so the entry is written as the installer reads it.
            lock_file.write_text(json.dumps({"lockfileVersion": 3, "skills": {self.NAME: {"skillFolderHash": self.row["tree_sha"]}}}), encoding="utf-8")
            folder = home / ".agents" / "skills" / self.NAME
            copy = root / "copy"
            shutil.copytree(home, copy / "home", symlinks=True)
            with mock.patch.dict(os.environ, {"XDG_STATE_HOME": "", "CLAUDE_CONFIG_DIR": ""}):
                self.assertEqual(self.module.classify_skill(self.row, home), "ok", "the complete locked install, before any edit")
                for target in (folder, copy / "home" / ".agents" / "skills" / self.NAME):
                    (target / "SKILL.md").write_text(self.FILES["SKILL.md"] + "a local instruction\n", encoding="utf-8")
                    self.put(target, "local-work.txt", "file")
                self.assertEqual(self.module.classify_skill(self.row, home), "local-modified")
            done = self.cli(*add, home=copy / "home", cwd=root)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            replaced = copy / "home" / ".agents" / "skills" / self.NAME
            self.assertEqual((replaced / "SKILL.md").read_text(encoding="utf-8"), self.FILES["SKILL.md"], "the control: the pinned CLI replaces the edit")
            self.assertFalse(os.path.lexists(replaced / "local-work.txt"), "and deletes the extra file")

    def test_a_project_locked_at_the_pin_with_an_edited_skill_md_is_refused_where_the_native_add_deletes_the_edit_and_the_extra_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, project = root / "home", root / "project"
            home.mkdir()
            project.mkdir()
            source = self.source(root)
            add = ["add", str(source), "--skill", self.NAME, "-y", "-a", "universal", "claude-code"]
            done = self.cli(*add, home=home, cwd=project)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            lock_file = project / "skills-lock.json"
            lock = json.loads(lock_file.read_text(encoding="utf-8"))
            lock["skills"][self.NAME].update(sourceType="github", source=self.row["source"], ref=self.row["ref"], skillPath=self.row["path"] + "/SKILL.md")
            lock_file.write_text(json.dumps(lock), encoding="utf-8")
            folder = project / ".agents" / "skills" / self.NAME
            copy = root / "copy"
            shutil.copytree(project, copy, symlinks=True)
            pinned = {self.row["path"]: self.row["tree_sha"]}
            with mock.patch.object(self.module, "pinned_source_trees", return_value=pinned), mock.patch.dict(os.environ, {"XDG_STATE_HOME": "", "CLAUDE_CONFIG_DIR": ""}):
                for agent in ("claude-code", "universal"):
                    self.assertEqual(self.module.classify_skill(self.row, home, project, agent), "ok", f"the complete locked project install for {agent}, before any edit")
                for target in (folder, copy / ".agents" / "skills" / self.NAME):
                    (target / "SKILL.md").write_text(self.FILES["SKILL.md"] + "a local instruction\n", encoding="utf-8")
                    self.put(target, "local-work.txt", "file")
                for agent in ("claude-code", "universal"):
                    self.assertEqual(self.module.classify_skill(self.row, home, project, agent), "local-modified", agent)
            done = self.cli(*add, home=home, cwd=copy)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            replaced = copy / ".agents" / "skills" / self.NAME
            self.assertEqual((replaced / "SKILL.md").read_text(encoding="utf-8"), self.FILES["SKILL.md"], "the control: the pinned CLI replaces the edit")
            self.assertFalse(os.path.lexists(replaced / "local-work.txt"), "and deletes the extra file")

    def test_a_project_locked_at_the_pin_with_its_claude_link_missing_is_refused_where_the_native_add_deletes_the_extra_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, project = root / "home", root / "project"
            home.mkdir()
            project.mkdir()
            source = self.source(root)
            add = ["add", str(source), "--skill", self.NAME, "-y", "-a", "universal", "claude-code"]
            done = self.cli(*add, home=home, cwd=project)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            folder = project / ".agents" / "skills" / self.NAME
            lock_file = project / "skills-lock.json"
            lock = json.loads(lock_file.read_text(encoding="utf-8"))
            entry = lock["skills"][self.NAME]
            entry.update(sourceType="github", source=self.row["source"], ref=self.row["ref"], skillPath=self.row["path"] + "/SKILL.md")   # the lock names the manifest's source, as an install from it does
            lock_file.write_text(json.dumps(lock), encoding="utf-8")
            link = project / ".claude" / "skills" / self.NAME
            self.assertTrue(os.path.lexists(link), "the pinned CLI linked the Claude folder")
            link.unlink() if link.is_symlink() else shutil.rmtree(link)
            pinned = {self.row["path"]: self.row["tree_sha"]}
            with mock.patch.object(self.module, "pinned_source_trees", return_value=pinned), mock.patch.dict(os.environ, {"XDG_STATE_HOME": "", "CLAUDE_CONFIG_DIR": ""}):
                self.assertEqual(self.module.classify_skill(self.row, home, project, "claude-code"), "install", "the pinned folder alone: the repair is allowed")
                extra = self.put(folder, "local-work.txt", "file")
                self.assertEqual(self.module.classify_skill(self.row, home, project, "claude-code"), "local-modified")
            copy = root / "copy"
            shutil.copytree(project, copy, symlinks=True)
            done = self.cli(*add, home=home, cwd=copy)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertFalse((copy / ".agents" / "skills" / self.NAME / extra.name).exists(), "the control: the pinned CLI deletes it")

    def test_a_project_installed_from_a_source_that_is_not_a_repository_keeps_the_lock_the_cli_wrote_and_is_still_protected(self):
        """Astra's read of #1035 at 5ace90c1, blocker 1, with the lock as the pinned CLI writes it (no hand edit): an install from a local folder records `sourceType: local`, a relative `source` and a
        `computedHash`, and no `ref` or `skillPath` (src/local-lock.ts L16-L37). That entry named no source of the manifest and was sent to `install`, so the add deleted local work."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, project = root / "home", root / "project"
            home.mkdir()
            project.mkdir()
            source = self.source(root)
            add = ["add", str(source), "--skill", self.NAME, "-y", "-a", "universal", "claude-code"]
            done = self.cli(*add, home=home, cwd=project)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            entry = json.loads((project / "skills-lock.json").read_text(encoding="utf-8"))["skills"][self.NAME]
            self.assertEqual((entry["sourceType"], "ref" in entry, "skillPath" in entry), ("local", False, False), "the shape the pinned CLI writes")
            folder = project / ".agents" / "skills" / self.NAME
            link = project / ".claude" / "skills" / self.NAME
            self.assertTrue(os.path.lexists(link))
            link.unlink() if link.is_symlink() else shutil.rmtree(link)
            extra = self.put(folder, "local-work.txt", "file")
            pinned = {self.row["path"]: self.row["tree_sha"]}
            with mock.patch.object(self.module, "pinned_source_trees", return_value=pinned), mock.patch.dict(os.environ, {"XDG_STATE_HOME": "", "CLAUDE_CONFIG_DIR": ""}):
                self.assertEqual(self.module.classify_skill(self.row, home, project, "claude-code"), "local-modified")
                extra.unlink()
                self.assertEqual(self.module.classify_skill(self.row, home, project, "claude-code"), "install", "the pinned folder alone: the repair is allowed")
                self.put(folder, "local-work.txt", "file")
            copy = root / "copy"
            shutil.copytree(project, copy, symlinks=True)
            done = self.cli(*add, home=home, cwd=copy)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertFalse((copy / ".agents" / "skills" / self.NAME / "local-work.txt").exists(), "the control: the pinned CLI deletes it")

    def test_a_project_lock_without_skill_path_is_refused_where_the_native_add_deletes_the_extra_file(self):
        """Astra's reproduction: the matching source, type, ref and a hash the CLI wrote, only the optional `skillPath` omitted (a lock written before the field existed)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, project = root / "home", root / "project"
            home.mkdir()
            project.mkdir()
            source = self.source(root)
            add = ["add", str(source), "--skill", self.NAME, "-y", "-a", "universal", "claude-code"]
            done = self.cli(*add, home=home, cwd=project)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            lock_file = project / "skills-lock.json"
            lock = json.loads(lock_file.read_text(encoding="utf-8"))
            lock["skills"][self.NAME].update(sourceType="github", source=self.row["source"], ref=self.row["ref"])
            lock["skills"][self.NAME].pop("skillPath", None)
            lock_file.write_text(json.dumps(lock), encoding="utf-8")
            folder = project / ".agents" / "skills" / self.NAME
            link = project / ".claude" / "skills" / self.NAME
            link.unlink() if link.is_symlink() else shutil.rmtree(link)
            pinned = {self.row["path"]: self.row["tree_sha"]}
            with mock.patch.object(self.module, "pinned_source_trees", return_value=pinned), mock.patch.dict(os.environ, {"XDG_STATE_HOME": "", "CLAUDE_CONFIG_DIR": ""}):
                self.assertEqual(self.module.classify_skill(self.row, home, project, "claude-code"), "install", "the pinned folder alone: the repair is allowed")
                extra = self.put(folder, "local-work.txt", "file")
                for agent in ("claude-code", "universal"):
                    self.assertEqual(self.module.classify_skill(self.row, home, project, agent), "local-modified", agent)
            copy = root / "copy"
            shutil.copytree(project, copy, symlinks=True)
            done = self.cli(*add, home=home, cwd=copy)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertFalse((copy / ".agents" / "skills" / self.NAME / extra.name).exists(), "the control: the pinned CLI deletes it")

    def test_a_global_lock_that_names_no_tree_is_refused_where_the_native_add_deletes_the_extra_file(self):
        """The global lock of an install from a local folder holds no pinned tree; so does a lock whose hash was lost. The entry is written as the installer reads it."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir()
            source = self.source(root)
            add = ["add", str(source), "--skill", self.NAME, "-g", "-y", "-a", "claude-code", "codex"]
            done = self.cli(*add, home=home, cwd=root)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            lock_file = home / ".agents" / ".skill-lock.json"
            lock_file.write_text(json.dumps({"version": 3, "skills": {self.NAME: {"source": self.row["source"], "sourceType": "github", "skillFolderHash": ""}}}), encoding="utf-8")
            folder = home / ".agents" / "skills" / self.NAME
            self.put(folder, "local-work.txt", "file")
            copy = root / "copy"
            shutil.copytree(home, copy / "home", symlinks=True)
            with mock.patch.dict(os.environ, {"XDG_STATE_HOME": "", "CLAUDE_CONFIG_DIR": ""}):
                self.assertEqual(self.module.classify_skill(self.row, home), "local-modified")
            done = self.cli(*add, home=copy / "home", cwd=root)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertFalse((copy / "home" / ".agents" / "skills" / self.NAME / "local-work.txt").exists(), "the control: the pinned CLI deletes it")


if __name__ == "__main__":
    unittest.main()
