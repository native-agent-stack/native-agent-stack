"""One sanitizer preserves the native portable recipe and omits account URLs."""

import ast
import base64
import importlib.util
from pathlib import Path
import re
from typing import Any
import unittest
from unittest.mock import patch
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_HOME = "/".join(["", "home", "synthetic-user"])
SYNTHETIC_MAC_HOME = "/".join(["", "Users", "synthetic-user"])
SYNTHETIC_SESSION = "-".join(["01234567", "89ab", "cdef", "0123", "456789abcdef"])
SYNTHETIC_TASK = "-".join(["task", "abcd1234", "ef5678"])


def load_helper():
    spec = importlib.util.spec_from_file_location("local_pages_sanitization_tests", ROOT / "tools/local-pages/sanitization.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SanitizationTests(unittest.TestCase):
    def test_native_reference_recipe_remains_exact_without_loading_reader(self):
        syntax = ast.parse((ROOT / "tools/north-star/build_readiness.py").read_text())
        render = next(node for node in syntax.body if isinstance(node, ast.FunctionDef) and node.name == "render")
        portable = next(node for node in render.body if isinstance(node, ast.FunctionDef) and node.name == "portable")
        namespace = {"Any": Any, "re": re}
        exec(compile(ast.Module(body=[portable], type_ignores=[]), "native portable reference", "exec"), namespace)
        home_text = SYNTHETIC_HOME + "/code/project " + SYNTHETIC_MAC_HOME + "/notes"
        data = {"home": home_text, "identities": ["before " + SYNTHETIC_SESSION + " after", SYNTHETIC_TASK.upper(), 5, False, None], "nested": {"value": SYNTHETIC_HOME + "/private/" + SYNTHETIC_TASK}}
        self.assertEqual(load_helper().sanitize(data), namespace["portable"](data))
        self.assertEqual(data["home"], home_text)

    def test_account_artifact_filter_applies_recursively(self):
        helper = load_helper()
        values = {"links": ["See https://claude.ai/artifact/private-item", "https://chatgpt.com/c/private-item", "https://chat.openai.com/c/private-item"], "keep": "https://example.org/public"}
        result = helper.sanitize(values)
        self.assertTrue(all(value.endswith("[account artifact omitted]") for value in result["links"]))
        self.assertEqual(result["keep"], values["keep"])

    def test_encoded_account_artifacts_follow_the_same_plain_policy(self):
        helper = load_helper()
        raw = "https://chatgpt.com/c/private-fixture"
        for encoded in (quote(raw, safe=""), raw.encode().hex(), base64.b64encode(raw.encode()).decode()):
            with self.subTest(encoded=encoded):
                self.assertEqual(helper.text(encoded), helper.text(raw))

    def test_url_classification_uses_supported_url_parser(self):
        helper = load_helper()
        for value in ["https://claude.ai/artifact/id", "HTTPS://CHATGPT.COM/c/id", "https://chat.openai.com/c/id", "https://chatgpt.com", "https://%63hatgpt.com/c/id"]:
            with self.subTest(value=value):
                self.assertTrue(helper.is_account_url(value))
        for value in ["https://platform.openai.com/docs", "https://example.org/chatgpt.com/c/id", "https://chatgpt.com.example.org/c/id", None]:
            with self.subTest(value=value):
                self.assertFalse(helper.is_account_url(value))

    def test_text_normalizes_scalars_and_keeps_native_placeholders(self):
        helper = load_helper()
        self.assertEqual(helper.text(None), "Unspecified in source")
        self.assertEqual(helper.text(4), "4")
        self.assertEqual(helper.text(SYNTHETIC_HOME + "/project"), "${USER_HOME}/project")
        self.assertEqual(helper.text(SYNTHETIC_SESSION), "${LOCAL_SESSION_ID}")
        self.assertEqual(helper.text(SYNTHETIC_TASK), "${LOCAL_TASK_HANDLE}")

    def test_sanitization_is_idempotent_for_rendered_source_values(self):
        helper = load_helper()
        source = {"path": SYNTHETIC_HOME + "/research", "account": "https://chatgpt.com/c/private-id", "task": SYNTHETIC_TASK, "number": 1}
        first = helper.sanitize(source)
        self.assertEqual(helper.sanitize(first), first)

    def test_text_projects_keys_and_other_stringified_container_values(self):
        rendered = load_helper().text({SYNTHETIC_HOME + "/key": (SYNTHETIC_MAC_HOME + "/value", SYNTHETIC_TASK)})
        self.assertNotIn(SYNTHETIC_HOME, rendered)
        self.assertNotIn(SYNTHETIC_MAC_HOME, rendered)
        self.assertNotIn(SYNTHETIC_TASK, rendered)

    def test_short_home_names_and_public_substrings_do_not_damage_html(self):
        helper = load_helper()
        spec = importlib.util.spec_from_file_location("short_home_composer", ROOT / "tools/local-pages/build_pages.py")
        composer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(composer)
        for name in ("li", "link", "section"):
            with self.subTest(name=name), patch.object(helper.Path, "home", return_value=Path("/synthetic") / name):
                public = "<link href='assets/site.css'><section><li>public list</li></section>"
                rendered = composer.document("index", "Public", "Public page", "fixture", public, "2026-10-09T05:00:00Z", "a" * 64, []).decode()
                self.assertIn(public, rendered)
                self.assertEqual(helper.text("linked public selection"), "linked public selection")

    def test_classified_encodings_preserve_portable_native_context(self):
        helper = load_helper()
        raw = SYNTHETIC_HOME + "/fixture"
        expected = helper.sanitize(raw)
        for encoded in (quote(raw, safe=""), raw.replace("/", "&#47;"), "".join("\\u" + format(ord(char), "04x") for char in raw), raw.encode().hex(), base64.b64encode(raw.encode()).decode()):
            with self.subTest(encoded=encoded):
                self.assertEqual(helper.text("prefix " + encoded + " suffix"), "prefix " + expected + " suffix")

    def test_actual_home_name_is_masked_as_a_public_label_after_aggregation(self):
        helper = load_helper()
        identity = "-".join(["dummy", "synthetic", "user"])
        raw = {identity: {"calls": 7}}
        with patch.object(helper.Path, "home", return_value=Path("/synthetic") / identity):
            self.assertNotIn(identity, helper.text(identity))
            self.assertNotIn(identity, helper.text("host-" + identity + "-session"))
            self.assertEqual(raw[identity]["calls"], 7)

    def test_encoded_identifiers_are_masked_only_after_positive_classification(self):
        helper = load_helper()
        identity = "-".join(["dummy", "synthetic", "user"])
        path = "/".join(["", "home", identity, "fixture"])
        encoded = [quote(path, safe=""), path.replace("/", "&#47;"), "".join("\\u" + format(ord(char), "04x") for char in path), path.encode().hex(), base64.b64encode(path.encode()).decode()]
        with patch.object(helper.Path, "home", return_value=Path("/synthetic") / identity):
            for value in encoded:
                with self.subTest(value=value):
                    projected = helper.text(value)
                    self.assertNotIn(value, projected)
                    self.assertNotIn(identity, projected)
            public = base64.b64encode(b"public fixture label").decode()
            self.assertEqual(helper.text(public), public)
            self.assertEqual(helper.text("&lt;script&gt;public&lt;/script&gt;"), "&lt;script&gt;public&lt;/script&gt;")

    def test_home_name_label_filter_preserves_native_placeholders(self):
        helper = load_helper()
        with patch.object(helper.Path, "home", return_value=Path("/synthetic") / "user"):
            for value in ["${USER_HOME}", "${LOCAL_SESSION_ID}", "${LOCAL_TASK_HANDLE}"]:
                self.assertEqual(helper.text(value), value)

    def test_identity_is_masked_at_underscore_boundaries_without_public_substrings(self):
        helper = load_helper()
        identity = "-".join(["dummy", "synthetic", "user"])
        labels = ["worker_" + identity + "_read", "_" + identity.upper() + "_"]
        with patch.object(helper.Path, "home", return_value=Path("/synthetic") / identity):
            for label in labels:
                with self.subTest(label=label):
                    self.assertNotIn(identity.casefold(), helper.text(label).casefold())
            self.assertEqual(helper.text("pre" + identity + "post"), "pre" + identity + "post")

    def test_decoded_tokens_use_the_same_underscore_identity_classification(self):
        helper = load_helper()
        identity = "-".join(["dummy", "synthetic", "user"])
        raw = "worker_" + identity + "_read"
        encoded = ["".join("%" + format(ord(char), "02x") for char in raw), "".join("&#" + str(ord(char)) + ";" for char in raw), "".join("\\u" + format(ord(char), "04x") for char in raw), raw.encode().hex(), base64.b64encode(raw.encode()).decode()]
        with patch.object(helper.Path, "home", return_value=Path("/synthetic") / identity):
            for label in encoded:
                with self.subTest(label=label):
                    self.assertEqual(helper.text(label), helper.text(raw))

    def test_known_placeholders_and_owner_identifier_survive_identity_projection(self):
        helper = load_helper()
        for identity in ["user", "session", "native"]:
            with patch.object(helper.Path, "home", return_value=Path("/synthetic") / identity):
                for label in ["${USER_HOME}", "${LOCAL_SESSION_ID}", "${LOCAL_TASK_HANDLE}", "native-agent-stack-1a", "[personal identifier omitted]", "[account artifact omitted]"]:
                    with self.subTest(identity=identity, label=label):
                        self.assertEqual(helper.text(label), label)


    def test_email_addresses_are_omitted_after_the_shared_token_decoding(self):
        # The #1012 Claude read (B1) found a page-local mask that missed an HTML5 entity, encoded dots,
        # double percent-encoding and a semicolon-less reference; every page now gets the shared mask.
        helper = load_helper()
        at = "@"
        forms = ["owner" + at + "example.org", "owner%40example.org", "owner&#64;example.org", "owner&commat;example.org", "owner" + at + "example%2Eorg",
                 "owner" + at + "example&#46;org", "owner%2540example.org", "owner&#64example.org", "Owner.Name+tag" + at + "sub.example.co.uk", "owner&#x40;example.org"]
        for form in forms:
            with self.subTest(form=form):
                rendered = helper.text("mail " + form + " now")
                self.assertEqual(rendered, "mail [email omitted] now")
                self.assertEqual(helper.text(rendered), rendered)
                self.assertEqual(helper.sanitize({"nested": [form]}), {"nested": ["[email omitted]"]})
        for public in ["@codex review", "user" + at + "host", "a " + at + " b.org", "${USER_HOME}", "[email omitted]", "https://github.com/org/repo"]:
            with self.subTest(public=public):
                self.assertEqual(helper.text(public), public)

    def test_encoded_at_signs_in_tokens_over_the_decoding_bound_are_masked(self):
        # The micro's (a)4 at 50977b00: _encoded_token leaves a token over 4,096 characters undecoded, and _EMAIL
        # matched only a literal @, so %40 and &#64; there rendered unmasked where b209afe8's page-local mask omitted them.
        helper = load_helper()
        at = "@"
        long = "x" * 4100
        for form in ("owner%40example.org", "owner&#64;example.org", "owner&#64example.org", "owner&#x40;example.org", "owner&commat;example.org",
                     "owner%2540example.org", "owner" + at + "example%2Eorg", "owner" + at + "example&#46;org", "owner" + at + "example&period;org"):
            with self.subTest(form=form):
                out = helper.text(long + form + " tail")
                self.assertTrue(out.endswith("[email omitted] tail"), out[-60:])
                self.assertNotIn("owner", out)
                self.assertNotIn("example", out)
                self.assertEqual(set(out[:-len("[email omitted] tail")]), {"x"})
        for public in ("https://registry.npmjs.org/%40openai%2fcodex", "https://www.npmjs.com/package/%40anthropic-ai/claude-code", "100%40 off", "a&#64b"):
            with self.subTest(public=public):
                self.assertEqual(helper.text(long + " " + public), long + " " + public)

    def test_systemd_template_unit_names_are_not_addresses(self):
        # The architecture layer pages list user timers such as git-maintenance@daily.timer; since the shared
        # mask (50977b00) they rendered as "[email omitted]" (9 cells on the live layer pages at 2dfb3c8c).
        helper = load_helper()
        at = "@"
        for unit in ("git-maintenance" + at + "daily.timer", "${USER_HOME}/.config/systemd/user/git-maintenance" + at + "weekly.timer",
                     "getty" + at + "tty1.service", "user" + at + "1000.slice", "systemd-fsck" + at + "dev-disk.service"):
            with self.subTest(unit=unit):
                self.assertEqual(helper.text(unit), unit)
        self.assertEqual(helper.text("owner" + at + "timer.example.org"), "[email omitted]")
        # Pinned current behaviour (#1012 Follow-ups (a)5): a dotted instance name still masks up to its last label.
        self.assertEqual(helper.text("openvpn-client" + at + "site.conf.service"), "[email omitted].service")
        self.assertEqual(helper.text("owner" + at + "example.services"), "[email omitted]")

    def test_quoted_and_rfc_local_parts_are_masked_whole(self):
        # Astra's first read of a737ef98 (P1): "reviewer"@example.org and other RFC 5322 local parts (a quoted string,
        # or atext such as ! ' { }) left all or part of the address readable. Each local part and domain here is unique,
        # so the assertions need no address grammar: no part may remain, short or inside a token over 4,096 characters.
        helper = load_helper()
        at = "@"
        locals_ = ('"zqa"', '"zqb zqb"', '"zq\\"c"', "%22zqd%22", "&quot;zqe&quot;", "&#34;zqf&#34;", "%2522zqg%2522", "zq!h", "zq'i", "{zqj}", "zq=l", "zq?m", "zq&n")
        for local in locals_:
            for at_form in (at, "%40", "&#64;", "%2540", "&commat;"):
                for prefix in ("mail ", "x" * 4100 + " "):
                    with self.subTest(local=local, at=at_form, long=len(prefix) > 10):
                        out = helper.text(prefix + local + at_form + "zqdomain.example.org now")
                        self.assertNotIn("zq", out)
                        self.assertTrue(out.endswith("[email omitted] now"), out[-60:])
        self.assertEqual(helper.text('Reply to "reviewer"' + at + "example.org"), "Reply to [email omitted]")
        for public in ('say "hi" to them', 'He said "hello" and left', "uses: actions/checkout" + at + "v4", "npm i @anthropic-ai/claude-code" + at + "2.1.296",
                       "https://medium.com/" + at + "someone.handle/a-post", "imports `" + at + "AGENTS.md`", "run_events/" + at + "agent.tool/history",
                       "owner" + at + "example.org).", "git" + at + "github.com:org/repo.git"):
            with self.subTest(public=public):
                expected = {"owner" + at + "example.org).": "[email omitted]).", "git" + at + "github.com:org/repo.git": "[email omitted]:org/repo.git"}.get(public, public)
                self.assertEqual(helper.text(public), expected)

    def test_the_email_mask_is_linear_in_the_text_length(self):
        # The micro's (a)5: the a737ef98 pattern backtracked on long runs (1.5-2.5 s per search at 16,000 characters).
        helper = load_helper()
        import time
        started = time.perf_counter()
        helper.text("x" * 32000)
        self.assertLess(time.perf_counter() - started, 1.0)

    def test_escaped_shell_text_before_an_at_sign_stays_linear(self):
        # A quoted local part's content once allowed a backslash two parses (a quoted pair, or a plain character), so
        # JSON-escaped shell text before an at sign backtracked exponentially: 90 s in one live build. Run in a child
        # with a hard timeout, so a regression fails instead of hanging the suite.
        import subprocess
        import sys
        child = (
            "import importlib.util, sys\n"
            "bs, q = chr(92), chr(34)\n"
            "unit = \"'%a\" + bs * 2 + \"a' \" + bs + q + \"$aaa\" + bs + q + \" | aaaa -a '^\" + bs * 2 + \"[aa\" + bs * 2 + \"] aaa\" + bs * 2 + \".aa: .*\" + bs * 2 + \".aaaaaa/aaa\" + bs * 2 + \".aa' && \"\n"
            "probe = unit * 3 + 'aaaa ' + q + 'aaaa: aaaa, aaaaaa ' + chr(64) + 'aaa.aa aaaa'\n"
            "spec = importlib.util.spec_from_file_location('helper', sys.argv[1])\n"
            "helper = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(helper)\n"
            "print(helper.text(probe) == probe)\n")
        result = subprocess.run([sys.executable, "-B", "-c", child, str(ROOT / "tools/local-pages/sanitization.py")], capture_output=True, text=True, timeout=30)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "True"), result.stderr[-400:])

    def test_empty_quoted_and_punctuation_only_local_parts_are_masked(self):
        # Astra's read of 51f85b5b, P1 1: a quoted local part needed at least one character and an atext one a letter
        # or digit, so an empty quoted one and a punctuation-only one on the target domain stayed readable. CPython's parser accepts both
        # (Lib/email/_parseaddr.py getaddrspec, lines 365-385, getatom, lines 475-493, and getdelimited, line 449, at cbc944f4).
        helper = load_helper()
        at = "@"
        forms = ('""' + at + "zqdomain.example.target", "!!!" + at + "zqdomain.example.target", "%22%22%40zqdomain.example.target",
                 "&quot;&quot;&#64;zqdomain.example.target", "%21%21%21%40zqdomain.example.target", "&#33;&#33;&#33;" + at + "zqdomain.example.target",
                 "''" + at + "zqdomain.example.target", "{}" + at + "zqdomain.example.target", '\\"\\"' + at + "zqdomain.example.target")
        for form in forms:
            for prefix in ("Reply to ", "x" * 4100 + " "):
                with self.subTest(form=form, long=len(prefix) > 10):
                    out = helper.text(prefix + form)
                    self.assertNotIn("zqdomain", out)
                    self.assertTrue(out.endswith("[email omitted]"), out[-40:])

    def test_long_atext_runs_with_encoded_at_signs_stay_fast(self):
        # The 51f85b5b micro's B1: the walk back over atext had no bound, and %40 and &#64 are themselves atext, so
        # each at sign rescanned the run: 9.6 s for one 50,000-character token. Each form here must finish under 0.5 s,
        # timed in a child process with a hard timeout so a regression cannot hang the suite.
        import subprocess
        import sys
        child = (
            "import importlib.util, sys, time\n"
            "spec = importlib.util.spec_from_file_location('helper', sys.argv[1])\n"
            "helper = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(helper)\n"
            "forms = {'pct': 'a%40b.cc' * 6250, 'ent': 'a&#64b.cc' * 5556, 'apos': chr(39).join(['a%252540b.cc'] * 3847)}\n"
            "for name, value in forms.items():\n"
            "    started = time.perf_counter()\n"
            "    out = helper.text(value)\n"
            "    print(name, round(time.perf_counter() - started, 3), 'b.cc' in out)\n")
        result = subprocess.run([sys.executable, "-B", "-c", child, str(ROOT / "tools/local-pages/sanitization.py")], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-400:])
        rows = [line.split() for line in result.stdout.split("\n") if line.strip()]
        self.assertEqual([row[0] for row in rows], ["pct", "ent", "apos"])
        for name, seconds, left in rows:
            with self.subTest(form=name):
                self.assertLess(float(seconds), 0.5)
                self.assertEqual(left, "False")

    def test_every_atext_character_is_a_whole_local_part_alone_and_mixed(self):
        # Astra's read of 3d7b1e7a, P1 1 (review_probes.py test_all_81_atext_characters): CPython's parser takes each of the
        # 81 atext characters as a whole local part (Lib/email/_parseaddr.py getatom, lines 475-493, at cbc944f4), and the
        # slash and a lone backtick stayed readable. Each domain is unique, so the assertions need no address grammar.
        helper = load_helper()
        at = "@"
        atext = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'*+-/=?^_`{|}~"
        self.assertEqual(len(atext), 81)
        for char in atext:
            for local in (char, "x" + char, char + "x", "x" + char + "x"):
                for prefix in ("mail ", "x" * 4100 + " "):
                    with self.subTest(local=local, long=len(prefix) > 10):
                        self.assertEqual(helper.text(prefix + local + at + "zqdomain.example.org now"), prefix + "[email omitted] now")

    def test_a_slash_before_the_at_sign_is_part_of_the_address_outside_a_url(self):
        # Astra's read of 3d7b1e7a, P1 1: the atext set left out the slash, so "/" and "x/" before an at sign survived,
        # also encoded ("%2F", "&#47;") and in the token report's keys and values. Inside a URL the slash still ends the
        # local part, so a path is not an address and an address after a path segment is masked from that segment on.
        helper = load_helper()
        at = "@"
        domain = at + "zqdomain.example.org"
        for local in ("/", "x/", "zqa/zqb", "zqa//", "/zqa"):
            for at_form in (at, "%40", "&#64;"):
                with self.subTest(local=local, at=at_form):
                    self.assertEqual(helper.text("mail " + local + at_form + "zqdomain.example.org now"), "mail [email omitted] now")
        for encoded in ("%2F" + "%40zqdomain.example.org", "x%2F" + domain, "&#47;&#64;zqdomain.example.org", "x&#47;" + domain, "%2f" + domain):
            with self.subTest(encoded=encoded):
                self.assertEqual(helper.text("mail " + encoded + " now"), "mail [email omitted] now")
        self.assertEqual(helper.text("mail x/" + domain + "."), "mail [email omitted].")
        self.assertEqual(helper.text("see https://zqlocal" + domain + "/x"), "see https://[email omitted]/x")
        self.assertEqual(helper.text("see https://example.org/path/zqlocal" + domain + " now"), "see https://example.org/path/[email omitted] now")
        self.assertEqual(helper.text("see ssh://zqlocal" + domain + "/repo"), "see ssh://[email omitted]/repo")

    def test_backticks_open_a_code_span_only_when_one_closes_after_the_address(self):
        # Astra's read of 3d7b1e7a, P1 1: leading backticks were skipped without any code span, so a lone backtick before
        # the at sign stayed readable. CommonMark 6.1 closes a span with a backtick string of equal length, so the leading
        # backticks are delimiters only when such a string follows the at sign; otherwise they are part of the local part.
        helper = load_helper()
        at = "@"
        domain = at + "zqdomain.example.org"
        for value, expected in (("mail `" + domain + " now", "mail [email omitted] now"),
                                ("mail `zqa" + domain + " now", "mail [email omitted] now"),
                                ("mail ``zqa" + domain + " now", "mail [email omitted] now"),
                                ("mail `zqa`" + domain + " now", "mail [email omitted] now"),
                                ("mail ``zqa" + domain + "` now", "mail [email omitted]` now"),
                                ("mail `/" + domain + " now", "mail [email omitted] now"),
                                ("run `zqa" + domain + "` now", "run `[email omitted]` now"),
                                ("run ``zqa" + domain + "`` now", "run ``[email omitted]`` now"),
                                ("run `a/zqb" + domain + "` now", "run `[email omitted]` now"),
                                ("run `/" + domain + "` now", "run `[email omitted]` now"),
                                ("run `zqa" + domain + " and more` now", "run `[email omitted] and more` now"),
                                ("x`" + domain + "` y", "[email omitted]` y")):
            with self.subTest(value=value):
                self.assertEqual(helper.text(value), expected)
        for public in ("imports `" + at + "AGENTS.md` and `CLAUDE.md`", "``" + at + "AGENTS.md``", "[`" + at + "AGENTS.md`](AGENTS.md)", "a `b` then `" + at + "RTK.md` stays"):
            with self.subTest(public=public):
                self.assertEqual(helper.text(public), public)

    def test_urls_markdown_links_and_path_segments_keep_their_at_signs(self):
        # The contexts the walk sets aside, each positively identified (Astra's 3d7b1e7a P1 1: "preserve only positively
        # identified surrounding URL/Markdown contexts"): a URL, a closed code span, and a name that follows a slash and is
        # itself followed by a slash or an opening parenthesis. Every public string here stays as written.
        helper = load_helper()
        at = "@"
        for public in ("https://medium.com/" + at + "someone.handle/a-post", "see https://medium.com/" + at + "someone.handle now",
                       "https://medium.com/" + at + "someone.handle", "[docs](https://medium.com/" + at + "someone.handle/a-post)",
                       "<https://medium.com/" + at + "someone.handle>", "https://example.org/a/" + at + "b.example.net/c",
                       "[" + at + "AGENTS.md](AGENTS.md)",
                       "run_stream_events/" + at + "agent.tool/message_history", "decorators " + at + "DBOS.workflow()/" + at + "DBOS.step() stay"):
            with self.subTest(public=public):
                self.assertEqual(helper.text(public), public)
                self.assertEqual(helper.text(helper.text(public)), public)

    def test_the_path_segment_exemption_needs_a_slash_right_before_the_at_sign(self):
        # The CC's condition for the path-segment exemption (accepted 10-12): it fires only when the character right before the
        # at sign is a slash, which no real mailbox has. gcloud keeps one directory per account, so an address that is itself a
        # path segment (legacy_credentials/ + the account address + /adc.json) and x/ + an address + /y still mask. Outside a
        # URL the slash is part of the local part, so the directory prefix goes with the address: the first group pins that
        # cost. Inside a URL the slash ends the local part, so the prefix stays. The names are unique and built at run time.
        helper = load_helper()
        at = "@"
        domain = at + "zqdomain.example.org"
        for value, expected in (("see legacy_credentials/zqlocal" + domain + "/adc.json now", "see [email omitted]/adc.json now"),
                                ("see x/zqlocal" + domain + "/y now", "see [email omitted]/y now"),
                                ("see x/zqlocal" + domain + "(y) now", "see [email omitted](y) now"),
                                ("see x//zqlocal" + domain + "/y now", "see [email omitted]/y now"),
                                ("see https://h.example.org/legacy_credentials/zqlocal" + domain + "/adc.json now",
                                 "see https://h.example.org/legacy_credentials/[email omitted]/adc.json now")):
            with self.subTest(value=value):
                out = helper.text(value)
                self.assertNotIn("zqlocal", out)
                self.assertNotIn("zqdomain", out)
                self.assertEqual(out, expected)
        # The exempt shape is only a slash-ended name with a slash or an opening parenthesis after its domain; it stays readable,
        # and without that continuation the same slash-ended address masks whole.
        for public in ("see x/" + domain + "/y now", "see x/" + domain + "(y) now", "see /" + domain + "/y now"):
            with self.subTest(public=public):
                self.assertEqual(helper.text(public), public)
        for value in ("see x/" + domain + " now", "see x/" + domain + ", now", "see x/" + domain + ". now"):
            with self.subTest(value=value):
                self.assertNotIn("zqdomain", helper.text(value))

    def test_slash_backtick_and_url_runs_stay_fast(self):
        # The contexts above scan for URLs and for backtick strings; each form below would be quadratic if either scan
        # restarted per at sign. Timed in a child process with a hard timeout, so a regression cannot hang the suite.
        import subprocess
        import sys
        child = (
            "import importlib.util, sys, time\n"
            "spec = importlib.util.spec_from_file_location('helper', sys.argv[1])\n"
            "helper = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(helper)\n"
            "at = chr(64)\n"
            "forms = {'slash': ('x/' + at + 'b.cc ') * 4000, 'ticks': (chr(96) + 'a' + at + 'b.cc ') * 4000, 'run': chr(96) * 50000 + at + 'b.cc',\n"
            "         'url': 'https://h.example.org/' + ('a' + at + 'b.cc/') * 4500, 'schemes': 'a://' * 6000 + at + 'b.cc', 'path': ('/' + at + 'b.cc/') * 4500}\n"
            "for name, value in forms.items():\n"
            "    started = time.perf_counter()\n"
            "    helper.text(value)\n"
            "    print(name, round(time.perf_counter() - started, 3))\n")
        result = subprocess.run([sys.executable, "-B", "-c", child, str(ROOT / "tools/local-pages/sanitization.py")], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr[-400:])
        rows = [line.split() for line in result.stdout.split("\n") if line.strip()]
        self.assertEqual([row[0] for row in rows], ["slash", "ticks", "run", "url", "schemes", "path"])
        for name, seconds in rows:
            with self.subTest(form=name):
                self.assertLess(float(seconds), 0.5)

    def test_a_quoted_local_part_holding_an_at_sign_is_omitted_whole(self):
        # The 51f85b5b micro's B2: the inner match started later than the outer quoted string, and the merge kept the
        # inner start, so the first quoted word survived. Spans now merge from their earliest start.
        helper = load_helper()
        at = "@"
        for value in ('"zqmh zqmi' + at + 'zqdmh.example.org"' + at + "zqdmi.example.org", 'Mail "zqa zqb' + at + 'zqc.example.org"%40zqd.example.org now'):
            with self.subTest(value=value):
                out = helper.text(value)
                self.assertNotIn("zq", out)
                self.assertIn("[email omitted]", out)

    def test_json_escaped_quotes_open_and_close_a_quoted_local_part(self):
        # The 51f85b5b micro's (c)1, ruled a P1: a JSON-serialized string writes the quotes of a quoted local part as \",
        # which read as a quoted pair, so \"w1 w2\"@d.example.org stayed readable on three pages.
        import json
        helper = load_helper()
        at = "@"
        address = '"zqmb zqmc"' + at + "zqdmb.example.org"
        for value in (json.dumps(address)[1:-1], json.dumps({"to": address}), json.dumps(json.dumps({"to": address})), "note: " + json.dumps(address)):
            with self.subTest(value=value):
                out = helper.text(value)
                self.assertNotIn("zqmb", out)
                self.assertNotIn("zqdmb", out)

    def test_residue_after_masking_drops_the_value(self):
        # The 51f85b5b adjudication's fail-closed guard: a value that still holds an at sign, raw or encoded, followed by
        # a domain and directly after a word character, or after a quote with only whitespace between, is dropped.
        helper = load_helper()
        at = "@"
        for value in ('"zqsp" ' + at + "zqdsp.example.org", '"zq' + "w" * 300 + '"' + at + "zqdlong.example.org", "'zqq' %40zqdq.example.org"):
            with self.subTest(value=value[:30]):
                self.assertEqual(helper.text(value), helper.RESIDUE_OMITTED)
                self.assertEqual(helper.sanitize({"k": [value]}), {"k": [helper.RESIDUE_OMITTED]})
        for public in ("imports " + at + "AGENTS.md", "- serena " + at + " 2.0.0.dev0 " + at + " c6fbd1c5", "as " + at + "DBOS.workflow", "--body " + at + "preview.json",
                       "fixture/skills" + at + "0123456789ab", "git-maintenance" + at + "daily.timer", "npm i " + at + "anthropic-ai/claude-code" + at + "2.1.296",
                       "actions/checkout" + at + "v4", "`CLAUDE.md` that imports `" + at + "AGENTS.md`", "@codex review", "https://medium.com/" + at + "someone.handle/post"):
            with self.subTest(public=public):
                self.assertEqual(helper.text(public), public)
        self.assertEqual(helper.text(helper.RESIDUE_OMITTED), helper.RESIDUE_OMITTED)

    def test_addresses_on_the_target_domain_are_masked(self):
        # The micro at bdc09788, (a)1: `target` is a delegated top-level domain (public_suffix_list.dat:10339-10341),
        # so exempting it as a systemd unit type left an address there readable in every form, short or long.
        helper = load_helper()
        at = "@"
        for form in ("owner" + at + "example.target", "owner%40example.target", "owner&#64;example.target"):
            with self.subTest(form=form):
                self.assertEqual(helper.text("mail " + form + " now"), "mail [email omitted] now")
                out = helper.text("x" * 4100 + form)
                self.assertTrue(out.endswith("[email omitted]"))
                self.assertNotIn("owner", out)
                self.assertNotIn("target", out)

    def test_exempt_unit_types_are_not_public_suffixes(self):
        # Class guard for the same finding: a unit type exempted from the mask must not be a top-level domain in the
        # installed public suffix list, or real addresses there would render unmasked.
        listing = Path("/usr/share/publicsuffix/public_suffix_list.dat")
        if not listing.is_file():
            self.skipTest(f"{listing} is absent (Debian package publicsuffix), so exempt unit types cannot be checked against it")
        rules = [line.strip() for line in listing.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("//")]
        tlds = {rule.lstrip("!*.").rsplit(".", 1)[-1].casefold() for rule in rules}
        self.assertIn("com", tlds)
        exempt = re.fullmatch(r"\(\?:([a-z|]+)\)\(\?!\[A-Za-z\]\)", load_helper()._UNIT).group(1).split("|")
        self.assertEqual(len(exempt), len(set(exempt)))
        self.assertEqual(sorted(set(exempt) & tlds), [])

    def test_the_page_and_skill_usage_sources_write_no_address_at_a_delegated_domain(self):
        # Astra's read of 3d7b1e7a, P1 3: a comment in sanitization.py wrote out a complete address at a delegated top-level
        # domain, and this repository publishes only a no-reply form or an example on a name RFC 2606 and RFC 6761 reserve
        # (example.com, example.net, example.org, .example, .invalid, .test, .localhost). The grammar is the sanitizer's own:
        # a nonempty run of atext, the slash included, before an at sign and a dotted domain. The backtick is left out of the
        # local part, since it opens a Markdown code span (an AGENTS import is no address), and a name ending in a systemd
        # unit type is a template-unit instance. A hit is reported by file and line only, so the check never prints an address.
        helper = load_helper()
        tail = re.compile("@" + r"([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
        atext = set(helper._ATEXT) - {"`"}
        reserved = ("example.com", "example.net", "example.org")
        reserved_tlds = ("invalid", "test", "example", "localhost")
        patterns = ("tools/local-pages/**/*", "tools/skill-usage/**/*", "tests/test_local_pages*.py", "tests/test_skill_usage*.py")
        paths = sorted({path for pattern in patterns for path in ROOT.glob(pattern) if path.is_file()})
        self.assertGreater(len(paths), 50)
        hits = []
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                for match in tail.finditer(line):
                    start = match.start()
                    if start == 0 or line[start - 1] not in atext:
                        continue
                    local = start
                    while local > 0 and line[local - 1] in atext:
                        local -= 1
                    name = match.group(1).lower()
                    if (line[local:start].lower() in ("noreply", "no-reply") or "noreply" in name or name.rsplit(".", 1)[-1] in reserved_tlds + tuple(helper._UNIT_TYPES)
                            or any(name == known or name.endswith("." + known) for known in reserved)):
                        continue
                    hits.append(f"{path.relative_to(ROOT)}:{number}")
        self.assertEqual(hits, [], "a complete address at a delegated domain (the address itself is withheld from this report)")

    def test_email_placeholder_survives_identity_projection(self):
        helper = load_helper()
        for identity in ["email", "omitted"]:
            with self.subTest(identity=identity), patch.object(helper.Path, "home", return_value=Path("/synthetic") / identity):
                self.assertEqual(helper.text("owner" + "@" + "example.org"), "[email omitted]")


if __name__ == "__main__":
    unittest.main()
