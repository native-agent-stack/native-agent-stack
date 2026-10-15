"""Gap-ledger rows for the agent-sdks layer page (slot headless-sdk), 2026-10-15: B1-0006, B2-0002 with B4-0001 (one
change, the same background-command limit), B4-0002 and C1-0001.

Sources (fetch time, then the sha256 of the bytes read; docs describe client 2.1.300):
- https://code.claude.com/docs/en/tools-reference.md, 2026-10-15T10:34:35Z, 320420019ef6: :188, :192-210.
- https://code.claude.com/docs/en/env-vars.md, 2026-10-15T10:34:35Z, 54351937e4d1: :191, :366, :379-380.
- https://code.claude.com/docs/en/cross-session-messaging.md, 2026-10-15T10:34:35Z, 7b359027749f: :203-231.
- https://code.claude.com/docs/en/cli-reference.md, 2026-10-15T10:34:35Z, 0acf910e96c4: :125, :129.
- https://code.claude.com/docs/en/agent-sdk/python.md, 2026-10-15T10:34:36Z, 97dfac82b148: :891 (cli_path).
- https://pypi.org/pypi/claude-agent-sdk/0.2.167/json, 2026-10-15T10:34:36Z, 6fa3331e7e98: the sdist and its digest.
- anthropics/claude-agent-sdk-python@c10b52c674e5c709c7263544b38e8a5dad10e01d (tag v0.2.167): README.md:15-18,
  CHANGELOG.md:3-7 (0.2.167 bundles 2.1.300) and :40-44 (0.2.163 bundled 2.1.286).
- anthropics/claude-code@94506ff0d3bd9185f1752da36e968775021fb48f CHANGELOG.md:369-371 (onFailure, 2.1.295), :384 (the
  watchdog cap, 2.1.295), :978 (the limit only in unattended sessions, 2.1.288) and :1280 (the limit, 2.1.285).
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / ".claude/skills/claude-native-practice/reference"
PROFILE = ROOT / "adoption/new-wsl-profile.json"
DISPOSITIONS = ROOT / "catalogs/foundation/upstream-surface-dispositions.json"
TEMPLATE = ROOT / "adoption/templates/claude.settings.template.json"
WORKER = ROOT / "tools/claude-review-worker/worker.py"
# The CLI each SDK release bundles: anthropics/claude-agent-sdk-python@c10b52c6 CHANGELOG.md:3-7 and :40-44.
BUNDLED_CLI = {"0.2.163": "2.1.286", "0.2.167": "2.1.300"}
SDIST_SHA256 = "06c9b8137f39c5dd8d0959321267c1de006f0458f5a27f645dfbffe479f8e207"  # PyPI's digest for the 0.2.167 sdist


def version(text):
    return tuple(int(part) for part in text.split("."))


def load_worker():
    name = "claude_review_worker_for_ledger_rows"
    spec = importlib.util.spec_from_file_location(name, WORKER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class AgentSdksLedgerRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        slots = json.loads((REF / "slots.json").read_text(encoding="utf-8"))["slots"]
        cls.slot = next(slot for slot in slots if slot["id"] == "headless-sdk")
        cls.notes = cls.slot["notes"]
        cls.crw = load_worker()

    def test_the_background_time_limit_is_one_change_citing_both_rows(self):  # B2-0002 and B4-0001
        for fragment in ("Background commands (B2-0002, B4-0001)", "tools-reference.md:192, :196",
                         "anthropics/claude-code@94506ff0 CHANGELOG.md:1280 and :978", "up to 2 hours (:198-199)",
                         "10 minutes in a `-p` run whose prompt is text", "never shortens them (:207-210)",
                         "also lengthens every foreground command (env-vars.md:191)",
                         "The limit is not `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`"):
            self.assertIn(fragment, self.notes)
        self.assertEqual((self.notes.count("B2-0002"), self.notes.count("B4-0001")), (1, 1))
        # The note says the template leaves the 2-hour maximum: its effective ceiling stays at or under 7200000
        # (env-vars.md:193 and tools-reference.md:210), and the cited line is the one that sets it.
        self.assertIn("(adoption/templates/claude.settings.template.json:29)", self.notes)
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('"BASH_MAX_TIMEOUT_MS": "1800000"', text.splitlines()[28])
        env = json.loads(text)["env"]
        self.assertLessEqual(max(int(env["BASH_MAX_TIMEOUT_MS"]), int(env.get("BASH_DEFAULT_TIMEOUT_MS", "0"))), 7200000)

    def test_the_review_worker_runs_with_a_bounded_retry_watchdog(self):  # C1-0001
        argv = self.crw.sandbox_argv("/usr/bin/bwrap", "/s/work/main", "/s/work/input", "/s/tmp/config-1", "/c/claude")
        env = {argv[i + 1]: argv[i + 2] for i, word in enumerate(argv) if word == "--setenv"}
        self.assertEqual(env.get("CLAUDE_CODE_RETRY_WATCHDOG"), "1")
        cap = int(env["CLAUDE_CODE_RETRY_WATCHDOG_MAX_WAIT_MS"])
        self.assertEqual(cap, 900000)
        self.assertLess(cap, self.crw.DEFAULT_TIMEOUT_SECONDS * 1000)  # a capacity wait ends inside the run
        # The cap needs 2.1.295 (CHANGELOG.md:384); the worker's pinned client is at least that.
        self.assertGreaterEqual(version(Path(self.crw.DEFAULT_CLAUDE_BIN).name), (2, 1, 295))
        # Fill-first still switches only on the refusals the watchdog does not wait out (a 402, or a 400).
        self.assertEqual(self.crw.SWITCH_CLASSES, ("credit_exhausted", "revoked_key"))
        for fragment in ("Retry (C1-0001)", "(env-vars.md:379-380; the cap needs 2.1.295, CHANGELOG.md:384)",
                         "`CLAUDE_CODE_RETRY_WATCHDOG=1`", "the cap at 900000 ms, a third of its 2700 s run timeout",
                         "capacity probes, where a 429 is the reading",
                         "the ns-run profiles run pi and OpenCode, not Claude Code"):
            self.assertIn(fragment, self.notes)

    def test_the_watchdog_dispositions_follow_the_worker(self):  # C1-0001
        rows = {row["key"]: row for row in json.loads(DISPOSITIONS.read_text(encoding="utf-8"))["rows"]}
        watchdog = rows["claude:env:CLAUDE_CODE_RETRY_WATCHDOG"]
        cap = rows["claude:env:CLAUDE_CODE_RETRY_WATCHDOG_MAX_WAIT_MS"]
        self.assertEqual((watchdog["disposition"], watchdog["value"]), ("enabled", "1"))
        self.assertEqual((cap["disposition"], cap["value"]), ("enabled", str(self.crw.RETRY_WAIT_CAP_MS)))
        for row in (watchdog, cap):
            with self.subTest(key=row["key"]):
                self.assertTrue(row["carrier"].startswith("tools/claude-review-worker/worker.py"))
                self.assertNotIn("off on both hosts", row["reason"])

    def test_a_fenced_worker_that_takes_messages_carries_the_accept_in_its_settings(self):  # B4-0002
        for fragment in ("Messages (B4-0002)", "(cross-session-messaging.md:203, :205, :224, :227)",
                         "`--restricted` loads only managed settings and `--settings` (cli-reference.md:125)",
                         'starts with `{"crossSessionInbound":"accept"}` in its `--settings` (cross-session-messaging.md:231)',
                         "No launcher in this repository takes messages"):
            self.assertIn(fragment, self.notes)
        # The review worker must not take messages: --restricted drops the user settings' accept, and its own
        # --settings carries none.
        flags = self.crw.claude_flags("/review/input")
        self.assertIn("--restricted", flags)
        self.assertNotIn("crossSessionInbound", json.loads(flags[flags.index("--settings") + 1]))

    def test_the_profile_pins_an_sdk_whose_bundled_cli_meets_the_floor(self):  # B1-0006
        entries = {entry["name"]: entry for entry in json.loads(PROFILE.read_text(encoding="utf-8"))["entries"]}
        sdk, claude = entries["Claude Agent SDK"], entries["Claude Code"]
        self.assertEqual(sdk["pin"], "0.2.167")
        self.assertGreaterEqual(version(BUNDLED_CLI[sdk["pin"]]), version(claude["pin"]))  # the onFailure floor
        self.assertEqual(sdk["install"]["command"], "pip install claude-agent-sdk==0.2.167")
        self.assertEqual((sdk["checksum"]["value"], sdk["checksum"]["source"]),
                         (SDIST_SHA256, "https://pypi.org/pypi/claude-agent-sdk/0.2.167/json"))
        self.assertEqual((sdk["artifact"]["name"], sdk["release"]["tag"]), ("claude_agent_sdk-0.2.167.tar.gz", "0.2.167"))
        self.assertNotIn("0.2.163", json.dumps(sdk))
        self.assertIn("| Claude Agent SDK | 0.2.167 |", (ROOT / "adoption/new-wsl-profile.md").read_text(encoding="utf-8"))
        for fragment in ("SDK client (B1-0006)", "anthropics/claude-agent-sdk-python@c10b52c6 README.md:15-18",
                         "agent-sdk/python.md:891", "(CHANGELOG.md:3-7, :40-44)",
                         "anthropics/claude-code@94506ff0 CHANGELOG.md:369-371", "now pins 0.2.167"):
            self.assertIn(fragment, self.notes)

    def test_the_page_renders_the_row(self):
        page = (REF / "agent-sdks.md").read_text(encoding="utf-8")
        (line,) = [line for line in page.splitlines() if line.startswith("- **Notes:** ")]
        for row_id in ("B1-0006", "B2-0002", "B4-0001", "B4-0002", "C1-0001"):
            self.assertIn(row_id, line)
        self.assertIn(f"- **Notes:** {self.notes}\n", page)
        self.assertIn(f"- **Route:** {self.slot['route']}\n", page)


if __name__ == "__main__":
    unittest.main()
