"""20eac579 micro regressions; parser occurrence and request-state controls, offline only."""
import json
import string
import unicodedata
import unittest
from unittest import mock

from tests.test_verify_sources import (
    V, TAG, MASTER, MOD_RS, LYCHEE, AT_FORM, URL_FORM, Fake, recorded_routes,
    json_response, compare_key, contents_key, verify,
)

FORMS = (
    AT_FORM, AT_FORM.replace("L23-L24", "L23"), AT_FORM.replace("L23-L24", "L23-24"),
    AT_FORM.replace(TAG[:12], TAG), AT_FORM.replace(TAG[:12], TAG[:12].upper()),
    URL_FORM, URL_FORM.replace("#L23-L24", "#L23"), URL_FORM.replace("#L23-L24", "#L23-24"),
    URL_FORM.replace("#L23-L24", "?plain=1#L23C2-L24C9"),
    URL_FORM.replace("https://github.com", "http://www.GitHub.com"),
    URL_FORM.replace(TAG, TAG[:12]), "[mechanism] _" + URL_FORM.removeprefix("[mechanism] ") + "_",
)


class MicroTests(unittest.TestCase):
    def test_markdown_link_colon_preserves_citation(self):
        url = URL_FORM.removeprefix("[mechanism] ")
        rows, _ = verify(f"[reference] [label]({url}): explanation")
        self.assertEqual([r["status"] for r in rows], ["ok"])

    def test_prose_punctuation_preserves_each_form(self):
        for form in FORMS:
            for suffix in (": explanation", "?", "—explanation", "”", "): explanation"):
                with self.subTest(form=form, suffix=suffix):
                    rows, _ = verify(form + suffix)
                    self.assertEqual([r["status"] for r in rows], ["ok"])

    def test_comma_joined_citations_emit_every_occurrence(self):
        for first in (AT_FORM, URL_FORM):
            for second in (AT_FORM.removeprefix("[mechanism] "), URL_FORM.removeprefix("[mechanism] ")):
                for joiner in (",", ", ", ";", "—", "-", " | ", " and "):
                    with self.subTest(first=first, second=second, joiner=joiner):
                        rows, fake = verify(first + joiner + second)
                        self.assertEqual([r["status"] for r in rows], ["ok", "ok"])
                        self.assertEqual(sum("/contents/" in key[0] for key, _, _ in fake.calls), 1)

    def test_all_punctuation_after_both_forms_preserves_the_row(self):
        # Finite exhaustive invariant, using the interpreter's Unicode punctuation inventory.
        # # / @ are reserved grammar continuations, separately tested below.
        punctuation = set(string.punctuation) | {chr(i) for i in range(0x110000)
                                                  if unicodedata.category(chr(i)).startswith("P")}
        for form in FORMS:
            for suffix in sorted(punctuation - {"#", "/", "@"}):
                with self.subTest(form=form[:15], suffix=repr(suffix)):
                    rows, _ = verify(form + suffix + " explanation")
                    self.assertEqual([r["status"] for r in rows], ["ok"])

    def test_grammar_continuations_remain_explicit_diagnostics(self):
        for form in (AT_FORM, URL_FORM):
            for suffix in ("#Lbad", ":Lbad", ":123", "/more", "@more", "_more", "-Lbad"):
                with self.subTest(form=form[:15], suffix=suffix):
                    rows, fake = verify(form + suffix)
                    self.assertEqual([r["status"] for r in rows], [V.NOT_CHECKED])
                    self.assertEqual(fake.calls, [])

    def test_repository_pins_have_a_distinct_unchecked_reason(self):
        pin = "github/rest-api-description@" + "a" * 40
        rows, _ = verify(pin)
        self.assertEqual(rows[0]["status"], V.NOT_CHECKED)
        self.assertIn("repository or package pin", rows[0]["reason"])
        self.assertNotIn("invalid", rows[0]["reason"])

    def test_every_row_uses_the_same_span_schema(self):
        rows, _ = verify(AT_FORM + f" o/r@{TAG}:f:Lbad")
        self.assertEqual(set(rows[0]), set(rows[1]))
        self.assertTrue(all(r["candidate_span"] for r in rows))

    def test_json_cache_releases_large_commit_and_compare_payloads(self):
        routes = recorded_routes()
        routes[(f"{LYCHEE}/git/commits/{TAG}", V.JSON_MEDIA)] = json_response(200, {"sha": TAG, "message": "x" * 200000})
        routes[compare_key()] = json_response(200, {"status": "ahead", "merge_base_commit": {"sha": TAG},
                                                   "commits": [{"message": "x" * 200000}]})
        fake = Fake(routes)
        github = V.GitHub(fetch=fake)
        _, rows = V.verify_body("## SOTA sources\n- " + AT_FORM, github)
        self.assertEqual(rows[0]["status"], "ok")
        for key in ((f"{LYCHEE}/git/commits/{TAG}", V.JSON_MEDIA), compare_key()):
            self.assertEqual(github.cache[key].body, b"")
            self.assertLess(len(json.dumps(V.json_body(github.cache[key]))), 200)

    def test_plain_403_is_indeterminate_at_every_request_step(self):
        for key in recorded_routes():
            if key[0].endswith(TAG) and key[1] == V.SHA_MEDIA or TAG[:12].upper() in key[0]:
                continue
            with self.subTest(step=key):
                rows, _ = verify(AT_FORM, {**recorded_routes(), key: json_response(403, {"message": "Forbidden"})})
                self.assertEqual((rows[0]["status"], V.exit_code(rows, "enforce")), (V.UNAVAILABLE, 3))

    def test_case_aliases_share_one_default_tip_snapshot(self):
        routes = recorded_routes()
        alternate = {("/repos/LYCHEEVERSE/LYCHEE" + key[0][len(LYCHEE):], key[1]): value
                     for key, value in routes.items()}
        alternate[("/repos/LYCHEEVERSE/LYCHEE/commits/master", V.SHA_MEDIA)] = V.Response(200, {}, ("b" * 40).encode())
        alternate[(f"/repos/LYCHEEVERSE/LYCHEE/compare/{TAG}...{'b' * 40}?per_page=1&page=2", V.JSON_MEDIA)] = json_response(
            200, {"status": "diverged", "merge_base_commit": {"sha": MASTER}})
        rows, fake = verify([AT_FORM, AT_FORM.replace("lycheeverse/lychee", "LYCHEEVERSE/LYCHEE")], {**routes, **alternate})
        self.assertEqual([r["status"] for r in rows], ["ok", "ok"])
        self.assertEqual([r["default_branch_sha"] for r in rows], [MASTER, MASTER])
        self.assertEqual(sum(key[0].endswith("/commits/master") for key, _, _ in fake.calls), 1)

    def test_sha_policy_precedes_invalid_range_and_zero_padding_is_numeric(self):
        rows, fake = verify("o/r@master:f:L99999999999")
        self.assertEqual((rows[0]["status"], fake.calls), ("unpinned", []))
        rows, _ = verify(AT_FORM.replace("L23-L24", "L0000000023-L0000000024"))
        self.assertEqual(rows[0]["status"], "ok")

    def test_unfollowed_redirects_are_indeterminate_at_every_step(self):
        for key in recorded_routes():
            if key[0].endswith(TAG) and key[1] == V.SHA_MEDIA or TAG[:12].upper() in key[0]:
                continue
            with self.subTest(step=key):
                rows, _ = verify(AT_FORM, {**recorded_routes(), key: json_response(302, {})})
                self.assertEqual(rows[0]["status"], V.UNAVAILABLE)

    def test_json_dispatch_uses_endpoint_after_the_repository_identity(self):
        cases = {
            "/repos/o/compare/git/ref/heads/abc": {"ref": "refs/heads/abc"},
            "/repos/o/pulls": {"default_branch": "main"},
            "/repos/o/git/git/commits/" + TAG: {"sha": TAG},
            "/repos/o/pulls/compare/" + TAG + "..." + MASTER:
                {"status": "ahead", "merge_base_commit": {"sha": TAG}},
            "/repos/o/compare/pulls/1": {"body": "## SOTA sources\n- reference"},
        }
        fake = Fake({(path, V.JSON_MEDIA): json_response(200, data) for path, data in cases.items()})
        github = V.GitHub(fetch=fake)
        for path, data in cases.items():
            with self.subTest(path=path):
                response = github.get(path)
                self.assertEqual(V.json_body(response), data)
                self.assertEqual(response.body, b"")

    def test_rejected_auth_stops_later_and_cached_requests(self):
        fake = Fake({("/first", V.JSON_MEDIA): json_response(401, {"message": "Bad credentials"}),
                     ("/second", V.JSON_MEDIA): json_response(200, {})})
        github = V.GitHub(fetch=fake)
        self.assertEqual(github.get("/first").status, 401)
        self.assertIsInstance(github.get("/second"), V.Unreachable)
        self.assertIsInstance(github.get("/first"), V.Unreachable)
        self.assertEqual(len(fake.calls), 1)

    def test_renamed_repository_aliases_share_all_learned_cache_keys(self):
        old, new = "/repos/o/old", "/repos/o/new"
        suffixes = [("/commits/" + TAG, V.SHA_MEDIA), ("/git/commits/" + TAG, V.JSON_MEDIA),
                    ("/contents/File.py?ref=" + TAG, V.RAW_MEDIA), ("/git/ref/heads/AbC", V.JSON_MEDIA)]
        routes = {(old + suffix, media): V.Response(200, {}, TAG.encode()) if media == V.SHA_MEDIA
                  else json_response(200, {"sha": TAG}) if "git/commits" in suffix
                  else json_response(404, {}) if "git/ref" in suffix
                  else V.Response(200, {"content-type": V.RAW_MEDIA}, b"x\n") for suffix, media in suffixes}
        routes[(old, V.JSON_MEDIA)] = json_response(200, {"id": 123, "full_name": "o/new", "default_branch": "main"})
        routes.update({(new + suffix, media): routes[(old + suffix, media)] for suffix, media in suffixes})
        fake = Fake(routes)
        github = V.GitHub(fetch=fake)
        original = [github.get(old + suffix, media) for suffix, media in suffixes]
        github.get(old)
        for (suffix, media), expected in zip(suffixes, original):
            self.assertEqual(github.get(new + suffix, media).status, expected.status)
        self.assertEqual(len(fake.calls), 5)

    def test_rename_during_run_preserves_the_tip_for_one_repository_id(self):
        from tests.test_verify_sources import routes_at
        compare = json_response(200, {"status": "ahead", "merge_base_commit": {"sha": TAG}})
        old = routes_at(TAG, compare, repository="/repos/o/old")
        new = routes_at(TAG, compare, repository="/repos/o/new")
        old[("/repos/o/old", V.JSON_MEDIA)] = json_response(200, {"id": 123, "full_name": "o/old", "default_branch": "master"})
        new[("/repos/o/new", V.JSON_MEDIA)] = json_response(200, {"id": 123, "full_name": "o/new", "default_branch": "master"})
        new[("/repos/o/new/commits/master", V.SHA_MEDIA)] = V.Response(200, {}, ("b" * 40).encode())
        new[(f"/repos/o/new/compare/{TAG}...{'b' * 40}?per_page=1&page=2", V.JSON_MEDIA)] = json_response(
            200, {"status": "diverged", "merge_base_commit": {"sha": MASTER}})
        rows, fake = verify([f"o/old@{TAG}:{MOD_RS}:L1", f"o/new@{TAG}:{MOD_RS}:L1"], {**old, **new})
        self.assertEqual([r["status"] for r in rows], ["ok", "ok"])
        self.assertEqual([r["default_branch_sha"] for r in rows], [MASTER, MASTER])
        self.assertEqual(sum(key[0].endswith("/commits/master") for key, _, _ in fake.calls), 1)

    def test_case_and_url_forms_share_keys_but_ref_path_and_git_suffix_do_not(self):
        rows, fake = verify([AT_FORM, URL_FORM.replace("lycheeverse/lychee", "Lycheeverse/Lychee"),
                             URL_FORM.replace("https://github.com", "http://www.GitHub.com")])
        self.assertEqual([r["status"] for r in rows], ["ok"] * 3)
        self.assertEqual(sum(key[0].endswith("/commits/master") for key, _, _ in fake.calls), 1)
        routes = {(p, V.JSON_MEDIA): json_response(404, {}) for p in
                  ("/repos/o/r/git/ref/heads/AbC", "/repos/o/r/git/ref/heads/abc",
                   "/repos/o/r.git", "/repos/o/r")}
        fake = Fake(routes)
        github = V.GitHub(fetch=fake)
        for p, media in routes:
            github.get(p.replace("/repos/o/r", "/repos/O/R"), media)
        self.assertEqual(len(fake.calls), 4)


if __name__ == "__main__":
    unittest.main()
