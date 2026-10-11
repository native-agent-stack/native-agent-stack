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
                self.assertEqual(helper.text(long + form + " tail"), "[email omitted] tail")
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
        self.assertEqual(helper.text("owner" + at + "example.services"), "[email omitted]")

    def test_addresses_on_the_target_domain_are_masked(self):
        # The micro at bdc09788, (a)1: `target` is a delegated top-level domain (public_suffix_list.dat:10339-10341),
        # so exempting it as a systemd unit type left an address there readable in every form, short or long.
        helper = load_helper()
        at = "@"
        for form in ("owner" + at + "example.target", "owner%40example.target", "owner&#64;example.target"):
            with self.subTest(form=form):
                self.assertEqual(helper.text("mail " + form + " now"), "mail [email omitted] now")
                self.assertEqual(helper.text("x" * 4100 + form), "[email omitted]")

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

    def test_email_placeholder_survives_identity_projection(self):
        helper = load_helper()
        for identity in ["email", "omitted"]:
            with self.subTest(identity=identity), patch.object(helper.Path, "home", return_value=Path("/synthetic") / identity):
                self.assertEqual(helper.text("owner" + "@" + "example.org"), "[email omitted]")


if __name__ == "__main__":
    unittest.main()
