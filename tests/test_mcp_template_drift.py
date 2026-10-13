"""Tests for tools/adoption/mcp_template_drift.py, the read-only report of where the MCP servers the committed new-WSL templates render differ from the servers an account's clients have registered.

The live files here are fixtures written from the render itself, so "no difference" is exact and each difference is one deliberate change. The tool never starts a server, never calls a client and never writes outside the
temporary directory of the test. No value of a registration reaches the output, in either format or on either stream: environment and header values and every argument (they are counted, never shown) are withheld, and so is every part of a URL but scheme://host (the SENTINEL, credential-form and property tests).
"""

import contextlib
import io
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile
import tomllib
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import mcp_template_drift as drift  # noqa: E402
import render_config  # noqa: E402

SCRIPT = ROOT / "tools" / "adoption" / "mcp_template_drift.py"
SENTINEL = "SENTINEL-must-never-be-printed"
SOURCE = "adoption/new-wsl/client-config-map.json"   # any file of this repository: an acknowledgement's source must exist
CLAUDE_FIXTURE = "headroom"   # a Claude user-scope server of the render with a command, arguments and an environment (the code-navigation servers left the render on 2026-10-12, FIX-3)


class DriftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.home = Path(cls.tmp.name) / "home"
        cls.home.mkdir()
        cls.eco = cls.home / ".local" / "share" / "codex-ecosystem"
        cls.files = drift.render_files(cls.home)
        cls.claude = drift.icp.render_servers(json.loads(cls.files["mcp-servers.json"]), cls.home, cls.eco)
        cls.codex_text = cls.files["codex.config.toml"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # ------------------------------------------------------------------ helpers
    def live(self, claude=None, codex_text=None):
        """Write live files into a fresh directory: the render by default; returns (claude json path, codex config path)."""
        directory = Path(tempfile.mkdtemp(dir=self.tmp.name))
        servers = json.loads(json.dumps(self.claude)) if claude is None else claude
        (directory / "claude.json").write_text(json.dumps({"numStartups": 7, "projects": {}, "mcpServers": servers}), encoding="utf-8")
        (directory / "config.toml").write_text(self.codex_text if codex_text is None else codex_text, encoding="utf-8")
        return directory / "claude.json", directory / "config.toml"

    def run_tool(self, claude_path, codex_path, *extra):
        out, err = io.StringIO(), io.StringIO()
        argv = ["--home", str(self.home), "--eco-root", str(self.eco), "--claude-json", str(claude_path), "--codex-config", str(codex_path), *extra]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = drift.main(argv)
        return code, out.getvalue(), err.getvalue()

    def rows(self, claude_path, codex_path, *extra):
        code, out, _ = self.run_tool(claude_path, codex_path, "--json", *extra)
        data = json.loads(out)
        return code, {(r["client"], r["name"]): r for r in data["rows"]}, data

    def codex_with(self, change):
        data = tomllib.loads(self.codex_text)
        change(data["mcp_servers"])
        return drift.new_wsl.emit_toml(data, "")

    def acknowledgements(self, *entries, schema=drift.ACK_SCHEMA):
        path = Path(tempfile.mkdtemp(dir=self.tmp.name)) / "ack.json"
        path.write_text(json.dumps({"schema": schema, "acknowledged": list(entries)}), encoding="utf-8")
        return path

    @staticmethod
    def entry(client, name, row, fields=None, reason="a decision accepts it", source=SOURCE):
        return {"client": client, "name": name, "row": row, **({"fields": fields} if fields else {}), "reason": reason, "source": source}

    # ------------------------------------------------------------------ the render
    def test_render_is_for_the_account_home_and_names_servers_for_both_clients(self):
        self.assertTrue(self.claude and tomllib.loads(self.codex_text).get("mcp_servers"))
        self.assertTrue(all("/home/example" not in text for text in self.files.values()), "the template's stand-in account name is replaced everywhere")
        self.assertIn(str(self.eco), json.dumps(self.claude), "the Claude commands carry the rendered ecosystem prefix")
        other = Path(self.tmp.name) / "elsewhere"
        other.mkdir()
        moved = drift.render_files(other)["codex.config.toml"]
        self.assertIn(str(other), moved)
        self.assertNotIn(str(self.home), moved)

    def test_templates_carry_the_live_names_of_the_two_reconciled_servers(self):
        """The reconciliation of 2026-10-12: promptfoo is wired for Claude Code (the Codex entry is a separate decision, acknowledged as live-only), and the code graph server is
        registered under the vendor's name, not under a shortened one: in the Codex template, and (since FIX-3, docs/decisions/2026-10-12-code-navigation-on-demand.md) in the on-demand file
        of Claude Code, which the user-scope render no longer carries."""
        codex = tomllib.loads(self.codex_text)["mcp_servers"]
        self.assertIn("promptfoo", self.claude)
        self.assertNotIn("promptfoo", codex)
        on_demand = json.loads((ROOT / "adoption" / "mcp" / "claude-code-navigation.json").read_text(encoding="utf-8"))["mcpServers"]
        for client, servers in (("claude on demand", on_demand), ("codex", codex)):
            self.assertIn("codebase-memory-mcp", servers, client)
            self.assertNotIn("codebase-memory", servers, client)
        for name in ("serena", "socraticode", "codebase-memory-mcp", "semble"):
            self.assertNotIn(name, self.claude, "the code-navigation servers are not registered at user scope")
            self.assertIn(name, on_demand)
        spec = self.claude["promptfoo"]
        self.assertEqual((spec["command"], spec["args"]), (f"{self.eco}/bin/promptfoo", ["mcp", "--transport", "stdio"]))
        self.assertEqual(sorted(spec["env"]), ["PROMPTFOO_CONFIG_DIR", "PROMPTFOO_DISABLE_TELEMETRY", "PROMPTFOO_DISABLE_UPDATE"])
        self.assertTrue(spec["env"]["PROMPTFOO_CONFIG_DIR"].startswith(str(self.home)), "the state directory is the account's own")

    def test_the_authorization_option_adds_the_tool_approval_modes(self):
        plain = tomllib.loads(self.codex_text)["mcp_servers"]
        approving = tomllib.loads(drift.render_files(self.home, authorization=True)["codex.config.toml"])["mcp_servers"]
        self.assertFalse([n for n, s in plain.items() if "default_tools_approval_mode" in s])
        self.assertTrue([n for n, s in approving.items() if "default_tools_approval_mode" in s])

    def test_a_failed_render_restores_the_host_value_loader(self):
        original = render_config.load_host_values
        with mock.patch.object(drift.new_wsl, "analyse", side_effect=drift.new_wsl.ConfigError("planned failure")):
            with self.assertRaises(drift.DriftError):
                drift.render_files(self.home)
        self.assertIs(render_config.load_host_values, original)
        drift.render_files(self.home)
        self.assertIs(render_config.load_host_values, original, "a render that succeeds restores it too")

    # ------------------------------------------------------------------ the comparison
    def test_live_files_equal_to_the_render_show_no_difference(self):
        claude_path, codex_path = self.live()
        code, rows, data = self.rows(claude_path, codex_path)
        self.assertEqual(code, 0, [k for k, r in rows.items() if r["row"] != "SAME"])
        self.assertTrue(rows and all(r["row"] == "SAME" for r in rows.values()))
        self.assertTrue(data["ok"])
        code, out, _ = self.run_tool(claude_path, codex_path)
        self.assertEqual(code, 0)
        self.assertIn("unacknowledged 0", out)

    def test_each_kind_of_difference_is_one_row_and_fails_the_run(self):
        servers = json.loads(json.dumps(self.claude))
        servers["ai-memory"]["url"] = "http://127.0.0.1:1/mcp"
        removed = "qmd"
        del servers[removed]
        servers["brand-new"] = {"type": "stdio", "command": "brand-new", "args": [], "env": {}}
        claude_path, codex_path = self.live(servers)
        code, rows, _ = self.rows(claude_path, codex_path)
        self.assertEqual(code, 1)
        self.assertEqual((rows[("claude", "ai-memory")]["row"], rows[("claude", "ai-memory")]["fields"]), ("DIFFERS", ["url"]))
        self.assertEqual(rows[("claude", removed)]["row"], "TEMPLATE-ONLY")
        self.assertEqual(rows[("claude", "brand-new")]["row"], "LIVE-ONLY")
        self.assertEqual(rows[("claude", CLAUDE_FIXTURE)]["row"], "SAME")
        self.assertTrue(all(r["row"] == "SAME" for k, r in rows.items() if k[0] == "codex"), "the Codex side is untouched")

    def test_an_env_wrapped_registration_is_the_same_server(self):
        servers = json.loads(json.dumps(self.claude))
        spec = servers[CLAUDE_FIXTURE]
        assert spec["env"], "the fixture server has an environment"
        servers[CLAUDE_FIXTURE] = {"type": "stdio", "command": "env", "args": [f"{k}={v}" for k, v in spec["env"].items()] + [spec["command"], *spec["args"]]}
        claude_path, codex_path = self.live(servers)
        code, rows, _ = self.rows(claude_path, codex_path)
        self.assertEqual((code, rows[("claude", CLAUDE_FIXTURE)]["row"]), (0, "SAME"))

    def test_a_changed_env_value_is_a_difference_named_env(self):
        servers = json.loads(json.dumps(self.claude))
        key = sorted(servers[CLAUDE_FIXTURE]["env"])[0]
        servers[CLAUDE_FIXTURE]["env"][key] = "another value"
        code, rows, _ = self.rows(*self.live(servers))
        self.assertEqual((code, rows[("claude", CLAUDE_FIXTURE)]["row"], rows[("claude", CLAUDE_FIXTURE)]["fields"]), (1, "DIFFERS", ["env"]))

    def test_codex_timeouts_compare_as_numbers_and_enabled_defaults_to_true(self):
        self.assertIn("startup_timeout_sec = 60\n", self.codex_text)
        floats = self.codex_text.replace("startup_timeout_sec = 60\n", "startup_timeout_sec = 60.0\n")
        code, rows, _ = self.rows(*self.live(codex_text=floats))
        self.assertEqual(code, 0, [k for k, r in rows.items() if r["row"] != "SAME"])
        explicit = self.codex_with(lambda servers: servers["semble"].update(enabled=True))
        code, rows, _ = self.rows(*self.live(codex_text=explicit))
        self.assertEqual(code, 0)
        disabled = self.codex_with(lambda servers: servers["semble"].update(enabled=False))
        code, rows, _ = self.rows(*self.live(codex_text=disabled))
        self.assertEqual((code, rows[("codex", "semble")]["fields"]), (1, ["enabled"]))

    def test_codex_tool_lists_and_forwarded_variables_compare_without_order(self):
        data = tomllib.loads(self.codex_text)["mcp_servers"]
        tools = data["semble"].get("enabled_tools")
        assert tools and len(tools) > 1, "the fixture server limits its tools"
        reordered = self.codex_with(lambda servers: servers["semble"].update(enabled_tools=list(reversed(tools))))
        code, rows, _ = self.rows(*self.live(codex_text=reordered))
        self.assertEqual((code, rows[("codex", "semble")]["row"]), (0, "SAME"))
        forwarded = self.codex_with(lambda servers: servers["semble"].update(env_vars=["B_NAME", "A_NAME"]))
        code, rows, _ = self.rows(*self.live(codex_text=forwarded))
        self.assertEqual((code, rows[("codex", "semble")]["fields"]), (1, ["env_vars"]))

    def test_the_authorization_option_changes_what_counts_as_the_template(self):
        approving_text = drift.render_files(self.home, authorization=True)["codex.config.toml"]
        claude_path, codex_path = self.live(codex_text=approving_text)
        code, rows, _ = self.rows(claude_path, codex_path)
        self.assertEqual(code, 1)
        self.assertEqual(rows[("codex", "ai-memory")]["fields"], ["default_tools_approval_mode"])
        code, rows, _ = self.rows(claude_path, codex_path, "--with-authorization-settings")
        self.assertEqual(code, 0, [k for k, r in rows.items() if r["row"] != "SAME"])

    # ------------------------------------------------------------------ what is never printed
    CREDENTIAL = "Review-S3cret!x9"
    CREDENTIAL_FORMS = {
        "an option and its value": lambda raw, quoted: ["--api-key", raw],
        "an option and its percent-encoded value": lambda raw, quoted: ["--api-key", quoted],
        "an option=value": lambda raw, quoted: [f"--api-key={raw}"],
        "URL userinfo in an argument": lambda raw, quoted: [f"https://user:{quoted}@example.invalid/mcp"],
        "a URL query in an argument": lambda raw, quoted: [f"https://example.invalid/mcp?key={quoted}"],
        "an Authorization header argument": lambda raw, quoted: ["--header", f"Authorization: Bearer {raw}"],
        "a long credential with a special character": lambda raw, quoted: ["--token", raw + "A" * 42],
    }

    def test_values_of_env_headers_urls_and_arguments_never_reach_the_output(self):
        servers = json.loads(json.dumps(self.claude))
        servers[CLAUDE_FIXTURE]["env"][sorted(servers[CLAUDE_FIXTURE]["env"])[0]] = SENTINEL
        servers["leaky-http"] = {"type": "http", "url": f"http://user:{SENTINEL}@127.0.0.1:1/mcp/{SENTINEL}?token={SENTINEL}", "headers": {"Authorization": f"Bearer {SENTINEL}"}}
        servers["leaky-stdio"] = {"type": "stdio", "command": f"/opt/{SENTINEL}/bin/leaky", "args": [f"API_TOKEN={SENTINEL}", SENTINEL + "A" * 40, "--plain"], "env": {"API_KEY": SENTINEL}}
        servers["plain-http"] = {"type": "http", "url": "http://127.0.0.1:1/mcp/path?x=1", "headers": {}}
        claude_path, codex_path = self.live(servers)
        for extra in ((), ("--json",)):
            code, out, err = self.run_tool(claude_path, codex_path, *extra)
            self.assertEqual(code, 1)
            self.assertNotIn(SENTINEL, out + err)
        code, out, _ = self.run_tool(claude_path, codex_path)
        for shown in ("leaky-http", "leaky-stdio", "API_KEY", "header:Authorization", "http <withheld> env/headers: header:Authorization", "http http://127.0.0.1", " leaky 3 args "):
            self.assertIn(shown, out)
        for hidden in ("API_TOKEN", "--plain", "127.0.0.1:1", "/mcp", "token=", "/opt/"):
            self.assertNotIn(hidden, out, "arguments are counted, never shown; a URL's port, path and query are withheld")

    def test_no_argument_value_reaches_either_output_format_for_either_client(self):
        """The forms of the review of 2026-10-12 (Astra, #1034 at 6a7a7ce7): 7 forms x 2 clients x 2 formats, each on a server the templates lack (LIVE-ONLY) and on one they have (DIFFERS)."""
        raw, quoted = self.CREDENTIAL, urllib.parse.quote(self.CREDENTIAL, safe="")
        needles = (raw, quoted, "S3cret")
        for label, make in self.CREDENTIAL_FORMS.items():
            arguments = make(raw, quoted)
            for client in ("claude", "codex"):
                if client == "claude":
                    servers = json.loads(json.dumps(self.claude))
                    servers["only-live"] = {"type": "stdio", "command": "fixture", "args": list(arguments)}
                    servers[CLAUDE_FIXTURE]["args"] = [*servers[CLAUDE_FIXTURE].get("args", []), *arguments]
                    paths = self.live(servers)
                else:
                    def change(servers, arguments=arguments):
                        servers["only-live"] = {"command": "fixture", "args": list(arguments)}
                        servers["semble"]["args"] = [*servers["semble"].get("args", []), *arguments]
                    paths = self.live(codex_text=self.codex_with(change))
                for extra in ((), ("--json",)):
                    with self.subTest(form=label, client=client, json=bool(extra)):
                        code, out, err = self.run_tool(*paths, *extra)
                        self.assertEqual(code, 1, "the drift itself is still reported")
                        for needle in needles:
                            self.assertNotIn(needle, out + err)
                        self.assertIn("only-live", out)
                        self.assertIn(CLAUDE_FIXTURE if client == "claude" else "semble", out)

    def test_a_description_is_built_from_names_and_fixed_words_only(self):
        """Value-free by construction: for 300 seeded random values placed in the arguments, an environment value, a header value, the directory of the command, the username, password, port, path, query and fragment of
        a URL (with an `@`, and without one: a plain path, query and fragment, and the value as the port) and the whole of the transport type, no 8-character piece of the value is in the description. Not covered here, because they are printed as names by design when they have the shape of one: the
        host label and the command's file name (the shape tests below cover a credential that parses as a host)."""
        rnd = random.Random(1034)
        alphabet = string.ascii_letters + string.digits + "!#$%&()*+,-./:;<=>?@[]^_{|}~ "
        for index in range(300):
            secret = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(12, 48)))
            stdio = {"type": "stdio", "url": None, "command": f"/opt/{secret}/bin/fixture", "args": [secret, f"--key={secret}", "--key", secret, f"-{secret}", f"https://{secret}@host.invalid/{secret}?q={secret}"],
                     "env": {"ONE": secret}, "headers": {"X-Header": secret}}
            http = {"type": "http", "url": f"https://u:{secret}@host.invalid:8443/{secret}?token={secret}#{secret}", "command": None, "args": [secret], "env": {"TWO": secret}, "headers": {"Authorization": secret}}
            username = {"type": "http", "url": f"https://{secret}:password@host.invalid:{rnd.randint(1, 65535)}/path", "command": None, "args": [], "env": {}, "headers": {}}
            typed = {"type": secret, "url": None, "command": "fixture", "args": [], "env": {}, "headers": {}}
            plain = {"type": "http", "url": f"https://host.invalid/{secret}?q={secret}#{secret}", "command": None, "args": [], "env": {}, "headers": {}}
            ported = {"type": "http", "url": f"https://host.invalid:{secret}/", "command": None, "args": [], "env": {}, "headers": {}}
            port = rnd.randint(10000, 65535)
            numbered = {"type": "http", "url": f"https://host.invalid:{port}/{secret}", "command": None, "args": [], "env": {}, "headers": {}}
            self.assertNotIn(str(port), drift.describe(numbered), "a valid port is a value too: five digits are below the 8-character piece")
            for spec in (stdio, http, username, typed, plain, ported, numbered):
                text = drift.describe(spec)
                for position in range(len(secret) - 7):
                    self.assertNotIn(secret[position:position + 8], text, (index, position, text))

    def test_no_argument_token_is_printed_whatever_it_looks_like(self):
        """Review of the open threads on #1034 at 4916d3a4 (the Codex reviewer): in `['--api-key', '--secret-token']` the second token is the credential and has the shape of an option, so the shape of a token
        cannot decide what may be printed. Arguments are counted."""
        hostile = ["--api-key", "--secret-token", "-A", "--api-key=--secret-token", "-AbCdEfGhIjKlMnOp", "--9digitsFirst", "---triple", "--", "-", "--k e y", "--key\\n=v", "plain"]
        text = drift.describe({"command": "tool", "args": hostile, "env": {}, "headers": {}})
        self.assertEqual(text, "stdio tool 12 args")
        for arguments, expected in (([], "stdio tool"), (["-y"], "stdio tool 1 arg"), (["--api-key", "--secret-token"], "stdio tool 2 args")):
            self.assertEqual(drift.describe({"command": "tool", "args": arguments, "env": {}, "headers": {}}), expected)
        self.assertFalse(hasattr(drift, "shown_arg"), "no function prints an argument")

    def test_a_credential_that_looks_like_an_option_is_not_printed_by_either_client_in_either_format(self):
        """The forms of the Codex review thread (`--api-key --secret-token-abcdef`) and of the second GPT read at 4916d3a4 (~/.cache/ns2604-gpt-reads/fix1-pr1034-4916d3a47/VERDICT.md, blocker 1): a positional value after
        `--` and the operand of a short option are values with the shape of an option. CPython v3.12.3 `Lib/argparse.py` L1964 and L2503 (end-of-options handling) and `Lib/getopt.py` (`getopt(['-k', '--x'], 'k:')`
        returns `[('-k', '--x')]`) execute them as values."""
        for label, arguments in (("a long option-shaped value", ["--api-key", "--secret-token-abcdef"]), ("an option=value with an option-shaped value", ["--api-key=--secret-token-abcdef"]),
                                 ("a short option-shaped value", ["--token", "-Z"]), ("a positional value after the end-of-options marker", ["--", "--review-secret-9"]),
                                 ("the operand of a short option", ["-k", "--review-secret-9"])):
            for client in ("claude", "codex"):
                if client == "claude":
                    servers = json.loads(json.dumps(self.claude))
                    servers["only-live"] = {"type": "stdio", "command": "fixture", "args": list(arguments)}
                    paths = self.live(servers)
                else:
                    paths = self.live(codex_text=self.codex_with(lambda servers, arguments=arguments: servers.update({"only-live": {"command": "fixture", "args": list(arguments)}})))
                for extra in ((), ("--json",)):
                    with self.subTest(form=label, client=client, json=bool(extra)):
                        code, out, err = self.run_tool(*paths, *extra)
                        self.assertEqual(code, 1)
                        for needle in ("secret-token-abcdef", "review-secret-9", "--token", " -k "):
                            self.assertNotIn(needle, out + err)
                        self.assertIn("only-live", out)

    def test_a_field_of_an_unexpected_shape_ends_the_run_with_exit_two_and_never_prints_its_value(self):
        """Review of the open threads on #1034 at 4916d3a4 (the Codex reviewer): `normalise_codex({'startup_timeout_sec': 'SENTINEL-value'})` raised a ValueError that quotes the value, and main() caught only DriftError."""
        for label, bad in (("a string", "SENTINEL-value"), ("a list", ["SENTINEL-value"]), ("a table", {"SENTINEL": "value"})):
            with self.subTest(codex_timeout=label):
                text = self.codex_with(lambda servers, bad=bad: servers["semble"].update(startup_timeout_sec=bad))
                code, out, err = self.run_tool(*self.live(codex_text=text))
                self.assertEqual((code, out), (2, ""))
                self.assertNotIn("SENTINEL", err)
                self.assertIn("semble", err)
                self.assertIn("unexpected shape", err)
        for label, field, bad in (("an environment that is a string", "env", "SENTINEL-value"), ("arguments that are a number", "args", 5)):
            with self.subTest(claude=label):
                servers = json.loads(json.dumps(self.claude))
                servers[CLAUDE_FIXTURE][field] = bad
                code, out, err = self.run_tool(*self.live(servers))
                self.assertEqual((code, out), (2, ""))
                self.assertNotIn("SENTINEL", err)
                self.assertIn(CLAUDE_FIXTURE, err)

    def test_names_that_do_not_look_like_names_are_withheld(self):
        """Server, variable and header names are keys, printed as they are while they have the shape of a name."""
        odd = "bad name =secret AKIAEXAMPLE!"
        servers = json.loads(json.dumps(self.claude))
        servers[odd] = {"type": "stdio", "command": "tool", "args": [], "env": {odd: "v", "GOOD_NAME": "v"}, "headers": {odd: "v"}}
        for extra in ((), ("--json",)):
            code, out, err = self.run_tool(*self.live(servers), *extra)
            self.assertEqual(code, 1)
            self.assertNotIn("AKIAEXAMPLE", out + err)
            self.assertNotIn("secret", out + err)
            self.assertIn("GOOD_NAME", out)
            self.assertIn(drift.WITHHELD, out)

    def test_a_malformed_timeout_ends_the_command_with_exit_two_and_prints_no_secret_on_either_stream(self):
        """Blocker 2 of the second GPT read at 4916d3a4 (~/.cache/ns2604-gpt-reads/fix1-pr1034-4916d3a47/VERDICT.md): the real command, as a subprocess, with a secret in each malformed timeout field. float() formats its
        failure with %R of the input (CPython Objects/floatobject.c, `float_from_string_inner`: v3.12.3 L190-193, v3.13.16 L183-186), the report caught only DriftError, so the traceback printed the secret and the exit
        code was 1."""
        secret = "Review-S3cret!x9"
        for field in ("startup_timeout_sec", "tool_timeout_sec"):
            claude_path, codex_path = self.live(codex_text=self.codex_with(lambda servers, field=field: servers["semble"].update({field: secret})))
            for extra in ((), ("--json",)):
                with self.subTest(field=field, json=bool(extra)):
                    done = subprocess.run([sys.executable, "-I", str(SCRIPT), "--home", str(self.home), "--eco-root", str(self.eco), "--claude-json", str(claude_path), "--codex-config", str(codex_path), *extra],
                                          capture_output=True, text=True, timeout=180, env={"PATH": os.environ["PATH"], "HOME": str(self.home)})
                    self.assertEqual(done.returncode, 2, done.stderr)
                    for needle in (secret, "S3cret", "x9"):
                        self.assertNotIn(needle, done.stdout + done.stderr)
                    self.assertEqual(done.stdout, "")
                    self.assertIn("semble", done.stderr)
                    self.assertNotIn("Traceback", done.stderr)

    def test_an_input_that_cannot_be_read_ends_the_run_with_exit_two_and_a_fixed_message(self):
        """The CC's micro read of cecf039f (pr1034-claude-micro-cecf039f.md, P3-1 and P3-3): a directory that cannot be searched, and an input nested deeper than the parser's recursion limit, ended the run with
        exit 1 and a traceback that names an absolute path (CPython Lib/pathlib/_abc.py is_file L476-L488 re-raises EACCES; json and tomllib raise RecursionError)."""
        for label, text, field in (("deeply nested JSON", "[" * 200000, "claude"), ("deeply nested TOML", "a = " + "[" * 200000, "codex")):
            with self.subTest(label=label):
                claude_path, codex_path = self.live()
                (claude_path if field == "claude" else codex_path).write_text(text, encoding="utf-8")
                code, out, err = self.run_tool(claude_path, codex_path)
                self.assertEqual((code, out), (2, ""))
                self.assertIn("RecursionError", err)
                self.assertNotIn("Traceback", err)
                self.assertNotIn(self.tmp.name, err)

    def test_a_deeply_nested_acknowledged_file_ends_the_run_with_exit_two_and_a_fixed_message(self):
        """The CC's P3-6: the RecursionError catch of load_acknowledged had no test (dropping it left the module green). CPython Modules/_json.c L1033 and L1041: _Py_EnterRecursiveCall while decoding an object and an array."""
        claude_path, codex_path = self.live()
        nested = Path(tempfile.mkdtemp(dir=self.tmp.name)) / "ack.json"
        nested.write_text("[" * 200000, encoding="utf-8")
        for extra in ((), ("--json",)):
            with self.subTest(json=bool(extra)):
                code, out, err = self.run_tool(claude_path, codex_path, "--acknowledged", str(nested), *extra)
                self.assertEqual((code, out), (2, ""))
                self.assertIn("RecursionError", err)
                self.assertNotIn("Traceback", err)
                self.assertNotIn(self.tmp.name, err)

    @unittest.skipIf(os.geteuid() == 0, "root can search any directory")
    def test_a_home_whose_codex_directory_cannot_be_searched_ends_the_run_with_exit_two(self):
        home = Path(tempfile.mkdtemp(dir=self.tmp.name))
        (home / ".codex").mkdir()
        (home / ".codex" / "config.toml").write_text(self.codex_text, encoding="utf-8")
        (home / ".claude.json").write_text(json.dumps({"mcpServers": json.loads(json.dumps(self.claude))}), encoding="utf-8")
        (home / ".codex").chmod(0)
        self.addCleanup((home / ".codex").chmod, 0o700)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = drift.main(["--home", str(home), "--eco-root", str(self.eco)])
        self.assertEqual((code, out.getvalue()), (2, ""))
        self.assertIn("cannot read ~/.codex/config.toml: PermissionError", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        self.assertNotIn(str(home), err.getvalue())

    def test_the_fields_of_a_differing_acknowledgement_are_a_list_of_names(self):
        """The CC's micro read, P3-2: `sorted(entry["fields"])` raised TypeError for a list that mixes types, and a list of lists, a string and a number passed the check."""
        for label, fields in (("mixed types", ["args", 1]), ("a list of lists", [["args"]]), ("a string", "args"), ("a number", 5), ("an empty list", []), ("a null", None)):
            with self.subTest(fields=label):
                path = self.acknowledgements({**self.entry("claude", CLAUDE_FIXTURE, "DIFFERS"), "fields": fields})
                with self.assertRaises(drift.DriftError):
                    drift.load_acknowledged(path)
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                    code = drift.main(["--home", str(self.home), "--eco-root", str(self.eco), "--acknowledged", str(path)])
                self.assertEqual(code, 2)
                self.assertNotIn("Traceback", err.getvalue())
        good = self.acknowledgements(self.entry("claude", CLAUDE_FIXTURE, "DIFFERS", fields=["args", "env"]))
        self.assertEqual(len(drift.load_acknowledged(good)), 1)

    def test_a_credential_that_ends_the_authority_early_is_not_printed_as_a_host(self):
        """The CC's read of 4916d3a4 (~/.local/state/native-agent-stack/coordination/command-center/research-cc-role-20261008/pr1034-claude-read-4916d3a4.md, P3-a and P3-d): a userinfo that holds an unescaped `/`,
        `?` or `#` parses as the host (CPython Lib/urllib/parse.py urlsplit), and the transport type is any name-shaped text. A URL with an `@` anywhere is withheld whole, and the type is a fixed vocabulary."""
        sentinel = "Zq7secretpartK2"
        forms = {"a userinfo with a slash": f"https://{sentinel}/p@host.invalid", "a userinfo with a question mark": f"https://user:{sentinel}?x@host.invalid",
                 "a userinfo with a number sign": f"https://user:{sentinel}#x@host.invalid", "a password with a slash": f"https://user:{sentinel}/x@host.invalid",
                 "a port that is not a number": f"https://host.invalid:{sentinel}/x"}
        for label, url in forms.items():
            for client in ("claude", "codex"):
                if client == "claude":
                    servers = json.loads(json.dumps(self.claude))
                    servers["only-live"] = {"type": sentinel, "url": url}
                    paths = self.live(servers)
                else:
                    paths = self.live(codex_text=self.codex_with(lambda servers, url=url: servers.update({"only-live": {"url": url}})))
                for extra in ((), ("--json",)):
                    with self.subTest(form=label, client=client, json=bool(extra)):
                        code, out, err = self.run_tool(*paths, *extra)
                        self.assertEqual(code, 1)
                        self.assertNotIn(sentinel.lower(), (out + err).lower())
                        self.assertIn("only-live", out)

    def test_a_registration_of_the_wrong_shape_ends_the_run_with_exit_two_and_names_the_server_only(self):
        """The same read, P3-b: a list given as text printed a count of its characters, and a Codex `mcp_servers` that is not a table ended in an uncaught AttributeError and exit 1."""
        sentinel = "Zq7secretpartK2 with spaces"
        cases = (("args as a string", "claude", lambda servers: servers[CLAUDE_FIXTURE].update({"args": sentinel})), ("args holding a non-string", "claude", lambda servers: servers[CLAUDE_FIXTURE].update({"args": [1, sentinel]})),
                 ("env as a list", "claude", lambda servers: servers[CLAUDE_FIXTURE].update({"env": [sentinel]})), ("headers as a string", "claude", lambda servers: servers[CLAUDE_FIXTURE].update({"headers": sentinel})),
                 ("a registration that is a string", "claude", lambda servers: servers.update({CLAUDE_FIXTURE: sentinel})),
                 ("env as a list of pairs", "claude", lambda servers: servers[CLAUDE_FIXTURE].update({"env": [[sentinel, "v"]]})), ("headers as a list of pairs", "claude", lambda servers: servers[CLAUDE_FIXTURE].update({"headers": [[sentinel, "v"]]})),
                 ("args as a string", "codex", lambda servers: servers["semble"].update({"args": sentinel})), ("env as a list", "codex", lambda servers: servers["semble"].update({"env": [sentinel]})),
                 ("env as a list of pairs", "codex", lambda servers: servers["semble"].update({"env": [[sentinel, "v"]]})), ("env_vars as a table", "codex", lambda servers: servers["semble"].update({"env_vars": {sentinel: "v"}})),
                 ("enabled_tools as a string", "codex", lambda servers: servers["semble"].update({"enabled_tools": sentinel})))
        for label, client, change in cases:
            with self.subTest(client=client, shape=label):
                if client == "claude":
                    servers = json.loads(json.dumps(self.claude))
                    change(servers)
                    paths = self.live(servers)
                else:
                    paths = self.live(codex_text=self.codex_with(change))
                code, out, err = self.run_tool(*paths)
                self.assertEqual((code, out), (2, ""), err)
                self.assertIn(CLAUDE_FIXTURE if client == "claude" else "semble", err)
                self.assertNotIn("Zq7secretpartK2", err)
        claude_path, codex_path = self.live()
        codex_path.write_text('[[mcp_servers]]\nname = "Zq7secretpartK2"\n', encoding="utf-8")
        code, out, err = self.run_tool(claude_path, codex_path)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("is not a table", err)
        self.assertNotIn("Zq7secretpartK2", err)

    def test_paths_are_printed_relative_to_the_home(self):
        """The same read, P3-c: the notes and the read errors printed the absolute path of the live files, which holds the account's name."""
        claude_path, codex_path = self.live()
        (self.home / ".codex").mkdir(exist_ok=True)
        shutil.copy(claude_path, self.home / ".claude.json")
        shutil.copy(codex_path, self.home / ".codex" / "config.toml")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = drift.main(["--home", str(self.home), "--eco-root", str(self.eco)])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("(~/.claude.json)", out.getvalue())
        self.assertIn("(~/.codex/config.toml)", out.getvalue())
        self.assertNotIn(str(self.home), out.getvalue() + err.getvalue())
        (self.home / ".claude.json").write_text("{", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(drift.main(["--home", str(self.home), "--eco-root", str(self.eco)]), 2)
        self.assertIn("cannot read ~/.claude.json: JSONDecodeError", err.getvalue())
        self.assertNotIn(str(self.home), err.getvalue())
        outside = self.live()
        code, out, err = self.run_tool(*outside)
        self.assertEqual(code, 0, out)
        self.assertIn("(claude.json)", out, "a file outside the home is named by its file name alone")
        self.assertIn("(config.toml)", out)
        self.assertNotIn(self.tmp.name, out + err)
        directory = Path(tempfile.mkdtemp(dir=self.tmp.name))
        for label, arguments in (("claude", [str(directory), str(outside[1])]), ("codex", [str(outside[0]), str(directory)])):
            code, out, err = self.run_tool(*arguments)
            self.assertEqual((code, out), (2, ""), label)
            self.assertIn("IsADirectoryError", err, "a read error names the kind of error, not its text (which carries the path)")
            self.assertNotIn(self.tmp.name, err)

    def test_the_description_keeps_what_a_reader_needs_without_a_value(self):
        stdio = {"type": "stdio", "url": None, "command": "/home/example/.local/bin/server", "args": ["-y", "@scope/pkg@1.2.3", "--port", "8787", "--token=abc", "--header", "Authorization: Bearer abc"],
                 "env": {"B_NAME": "1", "A_NAME": "2"}, "headers": {}}
        self.assertEqual(drift.describe(stdio), "stdio server 7 args env/headers: A_NAME,B_NAME")
        http = {"type": "http", "url": "https://Example.invalid:8443/mcp/path?key=v#frag", "command": None, "args": [], "env": {}, "headers": {"X-Api-Key": "v", "Authorization": "w"}}
        self.assertEqual(drift.describe(http), "http https://example.invalid env/headers: header:Authorization,header:X-Api-Key")
        self.assertEqual(drift.describe({**http, "url": "https://user:pw@Example.invalid:8443/mcp/path?key=v#frag"}), "http <withheld> env/headers: header:Authorization,header:X-Api-Key", "a URL with userinfo is withheld whole")
        for port in ("notaport", "99999", "-1"):
            self.assertEqual(drift.describe({**http, "url": f"https://example.invalid:{port}/mcp"}), "http <withheld> env/headers: header:Authorization,header:X-Api-Key", f"a URL whose port is {port} does not parse: withheld whole")
        self.assertEqual(drift.describe({**http, "type": "Zq7-not-a-transport"}), "<withheld> https://example.invalid env/headers: header:Authorization,header:X-Api-Key", "the type is a fixed vocabulary")
        for transport in ("stdio", "http", "sse"):
            self.assertTrue(drift.describe({**http, "type": transport}).startswith(transport + " "))
        self.assertEqual(drift.describe({"command": None, "args": [], "env": {}, "headers": {}}), "stdio (no command)")

    # ------------------------------------------------------------------ acknowledged differences
    def test_acknowledged_rows_pass_and_are_reported_as_such(self):
        servers = json.loads(json.dumps(self.claude))
        del servers["qmd"]
        servers["brand-new"] = {"type": "stdio", "command": "brand-new"}
        servers["ai-memory"]["url"] = "http://127.0.0.1:1/mcp"
        claude_path, codex_path = self.live(servers)
        ack = self.acknowledgements(self.entry("claude", "qmd", "TEMPLATE-ONLY"), self.entry("claude", "brand-new", "LIVE-ONLY"), self.entry("claude", "ai-memory", "DIFFERS", ["url"]))
        code, out, _ = self.run_tool(claude_path, codex_path, "--acknowledged", str(ack))
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("ack "), 3)
        self.assertIn("(adoption/new-wsl/client-config-map.json)", out)

    def test_a_stale_acknowledgement_fails_the_run(self):
        claude_path, codex_path = self.live()
        ack = self.acknowledgements(self.entry("claude", "brand-new", "LIVE-ONLY"))
        code, out, _ = self.run_tool(claude_path, codex_path, "--acknowledged", str(ack))
        self.assertEqual(code, 1)
        self.assertIn("STALE-ACK", out)

    def test_an_acknowledgement_names_the_exact_fields(self):
        servers = json.loads(json.dumps(self.claude))
        servers["ai-memory"]["url"] = "http://127.0.0.1:1/mcp"
        claude_path, codex_path = self.live(servers)
        for fields in (["command"], ["url", "command"]):
            ack = self.acknowledgements(self.entry("claude", "ai-memory", "DIFFERS", fields))
            code, out, _ = self.run_tool(claude_path, codex_path, "--acknowledged", str(ack))
            self.assertEqual(code, 1, fields)
            self.assertIn("STALE-ACK", out)
            self.assertNotIn("ack DIFFERS", out)

    def test_an_acknowledgement_for_a_client_that_was_not_compared_is_not_stale(self):
        self.assertFalse((self.home / ".codex" / "config.toml").exists(), "the fixture home has no Codex config, so the default path is absent")
        claude_path, _ = self.live()
        ack = self.acknowledgements(self.entry("codex", "hindsight", "LIVE-ONLY"))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = drift.main(["--home", str(self.home), "--eco-root", str(self.eco), "--claude-json", str(claude_path), "--acknowledged", str(ack)])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("codex: no ", out.getvalue())
        self.assertNotIn("STALE-ACK", out.getvalue())

    def test_malformed_acknowledgements_are_refused_with_exit_two(self):
        claude_path, codex_path = self.live()
        bad = {
            "schema": self.acknowledgements(self.entry("claude", "x", "LIVE-ONLY"), schema="something/else"),
            "client": self.acknowledgements(self.entry("gemini", "x", "LIVE-ONLY")),
            "row": self.acknowledgements(self.entry("claude", "x", "SAME")),
            "fields": self.acknowledgements({"client": "claude", "name": "x", "row": "DIFFERS", "reason": "r", "source": SOURCE}),
            "reason": self.acknowledgements(self.entry("claude", "x", "LIVE-ONLY", reason=" ")),
            "source": self.acknowledgements(self.entry("claude", "x", "LIVE-ONLY", source="docs/no-such-file.md")),
        }
        for label, path in bad.items():
            code, out, err = self.run_tool(claude_path, codex_path, "--acknowledged", str(path))
            self.assertEqual(code, 2, label)
            self.assertEqual(out, "", label)
            self.assertIn(label, err, label)

    def test_an_acknowledgement_source_is_a_regular_file_beneath_the_repository(self):
        """Review of 2026-10-12 (Astra, #1034 at 6a7a7ce7): `(ROOT / source).is_file()` accepted /etc/passwd and ../pr-body.md, and main() then answered rc 0 with ok true."""
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repository"
            (repository / "docs").mkdir(parents=True)
            record = repository / "docs" / "record.md"
            record.write_text("# Heading\n", encoding="utf-8")
            (repository / "4242").write_text("a file whose name a number spells\n", encoding="utf-8")
            outside = Path(directory) / "outside.md"
            outside.write_text("not a file of the repository\n", encoding="utf-8")
            (repository / "docs" / "escape.md").symlink_to(outside)
            (repository / "docs" / "alias.md").symlink_to(record)
            (repository / "docs" / "folder").mkdir()
            accepted = ["docs/record.md", "docs/record.md#heading", "docs/alias.md"]
            refused = {"an absolute path": str(outside), "the absolute system file": "/etc/passwd", "an absolute path inside the repository": str(record), "parent traversal": "../outside.md",
                       "traversal that returns inside": "docs/../docs/record.md", "a symlink to a file outside": "docs/escape.md", "a directory": "docs/folder",
                       "a missing file": "docs/missing.md", "no path, only a fragment": "#heading", "a null byte": "docs/rec\0ord.md", "a number that spells a file": 4242}
            with mock.patch.object(drift, "ROOT", repository):
                for source in accepted:
                    with self.subTest(accepted=source):
                        entries = drift.load_acknowledged(self.acknowledgements(self.entry("claude", "x", "LIVE-ONLY", source=source)))
                        self.assertEqual(len(entries), 1)
                for label, source in refused.items():
                    with self.subTest(refused=label):
                        with self.assertRaises(drift.DriftError) as caught:
                            drift.load_acknowledged(self.acknowledgements(self.entry("claude", "x", "LIVE-ONLY", source=source)))
                        self.assertIn("source", str(caught.exception))
            claude_path, codex_path = self.live()
            for source in ("/etc/passwd", os.path.relpath(outside, ROOT)):
                with self.subTest(through_main=source):
                    code, out, err = self.run_tool(claude_path, codex_path, "--acknowledged", str(self.acknowledgements(self.entry("claude", "x", "LIVE-ONLY", source=source))))
                    self.assertEqual((code, out), (2, ""))
                    self.assertIn("source", err)

    def test_a_rejected_acknowledgement_source_is_never_printed(self):
        """Astra's read of cecf039f (~/.cache/ns2604-gpt-reads/fix2-pr1034-cecf039f9/VERDICT.md, blocker 1): the refusal interpolated the rejected value with `!r`, so a path of the account, or a malformed object
        holding a token, reached stderr with rc 2, in both formats. CPython `Doc/reference/lexical_analysis.rst` (v3.13.16 L785-L786): `!r` calls repr, which quotes the operand and does not redact it. The refusal names
        the entry and the field and never what was given."""
        claude_path, codex_path = self.live()
        sources = {"an absolute path of an account": "/home/example/review-account-7f3a/decision.md", "an object holding a token": {"token": "private-review-token"}, "a list": ["private-review-token"],
                   "a number": 90817263, "text with a token": "private-review-token/../x.md", "a null byte": "docs/rec\0ord-private.md", "a null": None, "a relative path to a missing file": "docs/private-review-missing.md"}
        needles = ("review-account-7f3a", "private-review-token", "90817263", "ord-private", "private-review-missing")
        for label, source in sources.items():
            for extra in ((), ("--json",)):
                with self.subTest(source=label, json=bool(extra)):
                    path = self.acknowledgements({**self.entry("claude", "x", "LIVE-ONLY"), "source": source})
                    done = subprocess.run([sys.executable, "-I", str(SCRIPT), "--home", str(self.home), "--eco-root", str(self.eco), "--claude-json", str(claude_path), "--codex-config", str(codex_path),
                                           "--acknowledged", str(path), *extra], capture_output=True, text=True, timeout=180, env={"PATH": os.environ["PATH"], "HOME": str(self.home)})
                    self.assertEqual(done.returncode, 2, done.stderr)
                    self.assertEqual(done.stdout, "")
                    for needle in needles:
                        self.assertNotIn(needle, done.stdout + done.stderr)
                    self.assertIn("acknowledged[0]", done.stderr)
                    self.assertIn("source must be a relative path", done.stderr)

    def run_with_acknowledgement(self, entry, *extra):
        """The real command as a subprocess with one acknowledgement entry; returns (code, stdout, stderr)."""
        claude_path, codex_path = self.live()
        path = self.acknowledgements(entry)
        done = subprocess.run([sys.executable, "-I", str(SCRIPT), "--home", str(self.home), "--eco-root", str(self.eco), "--claude-json", str(claude_path), "--codex-config", str(codex_path),
                               "--acknowledged", str(path), *extra], capture_output=True, text=True, timeout=180, env={"PATH": os.environ["PATH"], "HOME": str(self.home)})
        return done.returncode, done.stdout, done.stderr

    def test_an_acknowledgement_with_a_key_the_schema_does_not_define_is_refused_and_never_published(self):
        """Astra's read of 55dba7f4 (~/.cache/ns2604-gpt-reads/fix3-pr1034-55dba7f4c/VERDICT.md, blocker 1): `shown_stale` copied the whole entry (`{**e, ...}`), so a nested key of the acknowledged file that is not
        a defined field reached stdout in JSON (CPython Doc/reference/expressions.rst L359: dictionary unpacking copies every item; Lib/json/encoder.py L354 iterates them). The entry is refused at load with a message
        that names it and never what it holds, and the report is built from the defined keys."""
        base = self.entry("claude", "review-absent", "LIVE-ONLY")
        shapes = {"a nested object": {"private_context": {"token": "private-review-token"}}, "a text key": {"note": "private-review-token"}, "a list": {"extra": ["private-review-token"]},
                  "a key that spells a defined one": {"Reason": "private-review-token"}, "a null": {"owner": None}}
        for label, extra_keys in shapes.items():
            for extra in ((), ("--json",)):
                with self.subTest(keys=label, json=bool(extra)):
                    code, out, err = self.run_with_acknowledgement({**base, **extra_keys}, *extra)
                    self.assertEqual((code, out), (2, ""), err)
                    self.assertNotIn("private-review-token", out + err)
                    self.assertNotIn("Traceback", err)
                    self.assertIn("acknowledged[0]", err)
                    self.assertIn("keys that the schema does not define", err)

    def test_the_reason_of_an_acknowledgement_is_text(self):
        """The same read, the adjacent probe: a `reason` that is an object holding a token was accepted and serialised in the stale entry."""
        base = self.entry("claude", "review-absent", "LIVE-ONLY")
        reasons = {"an object": {"token": "private-review-token"}, "a list": ["private-review-token"], "a number": 90817263, "a boolean": True, "a null": None, "blank text": "   ", "empty text": ""}
        for label, reason in reasons.items():
            for extra in ((), ("--json",)):
                with self.subTest(reason=label, json=bool(extra)):
                    code, out, err = self.run_with_acknowledgement({**base, "reason": reason}, *extra)
                    self.assertEqual((code, out), (2, ""), err)
                    for needle in ("private-review-token", "90817263"):
                        self.assertNotIn(needle, out + err)
                    self.assertNotIn("Traceback", err)
                    self.assertIn("reason must be text", err)

    def test_fields_of_an_acknowledgement_are_a_list_of_names_for_every_kind_of_row(self):
        """Astra's follow-up 1 and the CC's P3-7: `fields` was checked for DIFFERS only, and a stale LIVE-ONLY entry with `fields: 42` ended in a TypeError traceback (exit 1) while the report was built."""
        for row in ("LIVE-ONLY", "TEMPLATE-ONLY"):
            for label, fields in (("a number", 42), ("a float", 4.5), ("a boolean", True), ("text", "args"), ("a list of numbers", [1]), ("a list of lists", [["args"]]), ("a table", {"args": "x"})):
                for extra in ((), ("--json",)):
                    with self.subTest(row=row, fields=label, json=bool(extra)):
                        code, out, err = self.run_with_acknowledgement({**self.entry("claude", "review-absent", row), "fields": fields}, *extra)
                        self.assertEqual((code, out), (2, ""), err)
                        self.assertNotIn("Traceback", err)
                        self.assertIn("fields, when given, are a list of strings", err)
        for fields in (None, [], ["args"]):
            with self.subTest(accepted=fields):
                entry = self.entry("claude", "review-absent", "LIVE-ONLY")
                code, out, err = self.run_with_acknowledgement({**entry, "fields": fields}, "--json")
                self.assertEqual((code, err), (1, ""), "the entry is valid and stale: exit 1, nothing on stderr")

    def test_a_stale_acknowledgement_is_published_from_its_defined_keys_only(self):
        """The report is built from the defined keys: the stale entry of the JSON output holds exactly those, with the name and the fields as names."""
        entry = {**self.entry("claude", "review absent!", "LIVE-ONLY", reason="a decision accepts it"), "fields": ["args", "bad name!"]}
        code, out, err = self.run_with_acknowledgement(entry, "--json")
        self.assertEqual((code, err), (1, ""))
        stale = json.loads(out)["stale"]
        self.assertEqual(len(stale), 1)
        self.assertEqual(sorted(stale[0]), sorted(drift.ACK_FIELDS))
        self.assertEqual((stale[0]["name"], stale[0]["fields"], stale[0]["row"], stale[0]["client"]), (drift.WITHHELD, ["args", drift.WITHHELD], "LIVE-ONLY", "claude"))
        self.assertEqual(stale[0]["source"], SOURCE)
        loaded = drift.load_acknowledged(self.acknowledgements(entry))
        self.assertEqual(sorted(loaded[0]), sorted(drift.ACK_FIELDS), "the loaded entries hold the defined keys")

    def test_the_report_copies_no_entry_whatever_the_loader_returned(self):
        """Defence in depth: the stale entry of both formats is built from the defined keys, so a loader that let a key through (here a stub that returns one) still publishes none of it."""
        claude_path, codex_path = self.live()
        leaking = [{**self.entry("claude", "review-absent", "LIVE-ONLY"), "private_context": {"token": "private-review-token"}, "fields": ["args"]}]
        for extra in ((), ("--json",)):
            with self.subTest(json=bool(extra)), mock.patch.object(drift, "load_acknowledged", return_value=leaking):
                code, out, err = self.run_tool(claude_path, codex_path, "--acknowledged", str(self.acknowledgements()), *extra)
                self.assertEqual((code, err), (1, ""))
                self.assertNotIn("private-review-token", out)
                self.assertNotIn("private_context", out)
                if extra:
                    self.assertEqual(sorted(json.loads(out)["stale"][0]), sorted(drift.ACK_FIELDS))

    def test_a_command_that_is_not_text_is_withheld_for_either_client_in_either_format(self):
        """Astra's P2 and the CC's B6 (55dba7f4): `shown_command` called str() on the command, so a number or a boolean, which has the shape of a file name, was printed (90817263 in all four combinations of
        client and format) although the docstring, the record and the body said a command of another kind is withheld."""
        needle = "90817263"
        for label, value in (("an integer", 90817263), ("a float", 90817263.5), ("true", True), ("false", False), ("a list", [90817263]), ("a table", {"command": 90817263})):
            for client in ("claude", "codex"):
                if client == "claude":
                    servers = json.loads(json.dumps(self.claude))
                    servers[CLAUDE_FIXTURE]["command"] = value
                    paths = self.live(servers)
                else:
                    paths = self.live(codex_text=self.codex_with(lambda servers, value=value: servers["semble"].update(command=value)))
                for extra in ((), ("--json",)):
                    with self.subTest(command=label, client=client, json=bool(extra)):
                        code, out, err = self.run_tool(*paths, *extra)
                        self.assertEqual(code, 1, err)
                        self.assertNotIn(needle, out + err)
                        self.assertIn(CLAUDE_FIXTURE if client == "claude" else "semble", out)
                        self.assertIn(drift.WITHHELD, out)
        self.assertEqual(drift.shown_command(90817263), drift.WITHHELD)
        self.assertEqual(drift.shown_command(None), "(no command)")
        self.assertEqual(drift.shown_command(""), "(no command)")
        self.assertEqual(drift.shown_command("/opt/tools/bin/server"), "server", "a string keeps its file name")
        self.assertEqual(drift.describe({"command": 90817263, "args": [], "env": {}, "headers": {}}), f"stdio {drift.WITHHELD}")

    def test_the_committed_acknowledgements_agree_with_the_render_and_cite_sections_of_their_record(self):
        """What can be checked without a live host: the file is well formed, each source is a heading of the record, a LIVE-ONLY entry names a server the render does not have and a DIFFERS entry one it has."""
        path = ROOT / "adoption" / "new-wsl" / "mcp-drift-acknowledged.json"
        entries = drift.load_acknowledged(path)
        codex = tomllib.loads(self.codex_text)["mcp_servers"]
        rendered = {"claude": self.claude, "codex": codex}
        record = (ROOT / "docs" / "decisions" / "2026-10-12-mcp-template-live-reconciliation.md").read_text(encoding="utf-8")
        slugs = {re.sub(r"[^a-z0-9 -]", "", line.lstrip("#").strip().lower()).replace(" ", "-") for line in record.splitlines() if line.startswith("#")}
        self.assertTrue(entries)
        seen = set()
        for entry in entries:
            where = (entry["client"], entry["name"], entry["row"])
            with self.subTest(entry=where):
                self.assertNotIn(where, seen, "an entry is listed once")
                seen.add(where)
                file_name, _, anchor = entry["source"].partition("#")
                self.assertEqual(file_name, "docs/decisions/2026-10-12-mcp-template-live-reconciliation.md")
                self.assertIn(anchor, slugs, "the source names a heading of the record")
                if entry["row"] == "LIVE-ONLY":
                    self.assertNotIn(entry["name"], rendered[entry["client"]])
                else:
                    self.assertEqual(entry["row"], "DIFFERS")
                    self.assertIn(entry["name"], rendered[entry["client"]])
                    self.assertEqual(entry["fields"], sorted(entry["fields"]), "fields are listed in the order the report prints them")

    # ------------------------------------------------------------------ the ecosystem prefix
    def test_the_ecosystem_root_reaches_both_templates(self):
        """Review of 2026-10-12 (Astra, #1034 at 6a7a7ce7): the prefix went to the Claude renderer only, so Codex kept <home>/.local/share/codex-ecosystem (six false DIFFERS rows under another prefix)."""
        custom = Path(self.tmp.name) / "another-prefix" / "ecosystem"
        default_claude, default_codex = drift.render_templates(self.home, self.eco)
        claude, codex = drift.render_templates(self.home, custom)

        def moved(servers):
            return json.loads(json.dumps(servers).replace(str(self.eco), str(custom)))
        for client, got, base in (("claude", claude, default_claude), ("codex", codex, default_codex)):
            with self.subTest(client=client):
                self.assertIn(str(self.eco), json.dumps(base), "the default render uses the default prefix")
                self.assertIn(str(custom), json.dumps(got), "the requested prefix is in the render")
                self.assertNotIn(str(self.eco), json.dumps(got), "and none of the default prefix is left")
                self.assertEqual(got, moved(base), "the prefix is the only difference")

    def test_a_non_default_prefix_compares_the_same_for_both_clients_from_the_option_and_the_environment(self):
        custom = Path(self.tmp.name) / "another-prefix" / "ecosystem"
        claude_path, codex_path = self.live(json.loads(json.dumps(self.claude).replace(str(self.eco), str(custom))), self.codex_text.replace(str(self.eco), str(custom)))
        for label, option, environment in (("the option", ["--eco-root", str(custom)], {}), ("ECO_INSTALL_ROOT", [], {"ECO_INSTALL_ROOT": str(custom)})):
            with self.subTest(prefix_from=label), mock.patch.dict(os.environ):
                os.environ.pop("ECO_INSTALL_ROOT", None)
                os.environ.update(environment)
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = drift.main(["--home", str(self.home), *option, "--claude-json", str(claude_path), "--codex-config", str(codex_path), "--json"])
                data = json.loads(out.getvalue())
                self.assertEqual([(r["client"], r["name"], r["fields"]) for r in data["rows"] if r["row"] != "SAME"], [], err.getvalue())
                self.assertEqual(code, 0)
                self.assertEqual({r["client"] for r in data["rows"]}, {"claude", "codex"})

    # ------------------------------------------------------------------ inputs that cannot be read
    def test_unreadable_live_files_exit_two_and_absent_default_files_are_skipped(self):
        claude_path, codex_path = self.live()
        missing = Path(self.tmp.name) / "missing.json"
        code, out, err = self.run_tool(missing, codex_path)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("cannot read", err)
        broken = Path(self.tmp.name) / "broken.json"
        broken.write_text("{", encoding="utf-8")
        self.assertEqual(self.run_tool(broken, codex_path)[0], 2)
        no_servers = Path(self.tmp.name) / "no-servers.json"
        no_servers.write_text("{}", encoding="utf-8")
        self.assertEqual(self.run_tool(no_servers, codex_path)[0], 2)
        empty_home = Path(tempfile.mkdtemp(dir=self.tmp.name))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = drift.main(["--home", str(empty_home), "--eco-root", str(self.eco)])
        self.assertEqual(code, 0)
        self.assertIn("claude: no ", out.getvalue())
        self.assertIn("codex: no ", out.getvalue())

    def test_the_script_runs_as_a_command(self):
        done = subprocess.run([sys.executable, "-I", str(SCRIPT), "--help"], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Read-only drift report", done.stdout)


if __name__ == "__main__":
    unittest.main()
