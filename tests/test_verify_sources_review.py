"""Fail-before regressions for #1003 review at a46fce0d; no network or real credential."""
import io
import json
from email.message import Message
from pathlib import Path
import unittest
from unittest import mock
import urllib.request
import urllib.response

from tests.test_verify_sources import (
    V, ROOT, TAG, MASTER, MOD_RS, LYCHEE, AT_FORM, SENTINEL, Fake,
    compare_key, contents_key, json_response, raw_file, recorded_routes, verify, run_main,
)

CORRECTIONS = json.loads((ROOT / "tests/fixtures/verify_sources/review-corrections.json").read_text())


class ReviewCorrectionsTests(unittest.TestCase):
    def test_compare_limitations_are_unavailable(self):
        captured = CORRECTIONS["compare-not-available"]
        cases = [json_response(captured["status"], captured["json"]),
                 json_response(400, {"message": "Bad Request"}),
                 json_response(403, {"message": "Forbidden"}),
                 V.Response(200, {}, b"{}", oversize=True),
                 V.Response(200, {}, b"not json"),
                 json_response(200, {"status": "ahead"}),
                 json_response(200, {"merge_base_commit": {"sha": TAG}}),
                 json_response(200, {"status": "unknown", "merge_base_commit": {"sha": TAG}})]
        for response in cases:
            with self.subTest(status=response.status, body=response.body):
                rows, _ = verify(AT_FORM, {**recorded_routes(), compare_key(): response})
                self.assertEqual(rows[0]["status"], V.UNAVAILABLE)
                self.assertNotIn(rows[0]["status"], V.FAILURES)

    def test_unresolved_prefix_is_distinct_from_missing_full_sha(self):
        record = CORRECTIONS["prefix-unresolved"]
        response = json_response(record["status"], record["json"])
        rows, _ = verify("torvalds/linux@1da177e4c3f4:README:L1-L2",
                         {(record["path"], V.SHA_MEDIA): response,
                          ("/repos/torvalds/linux/git/ref/heads/1da177e4c3f4", V.JSON_MEDIA): json_response(404, {}),
                          ("/repos/torvalds/linux/git/ref/tags/1da177e4c3f4", V.JSON_MEDIA): json_response(404, {})})
        self.assertEqual(rows[0]["status"], "sha-unresolved")
        self.assertIn("full SHA", rows[0]["reason"])
        self.assertNotIn("sha-unresolved", V.FAILURES)
        self.assertEqual(V.exit_code(rows, "enforce"), 3)

    def test_citation_cap_marks_every_excess_row_without_requests(self):
        entries = [f"o/r@{n:040x}:x:L1" for n in range(1, 6)]
        fake = Fake({(f"/repos/o/r/commits/{n:040x}", V.SHA_MEDIA):
                     json_response(404, {"message": "Not Found"}) for n in range(1, 6)})
        with mock.patch.object(V, "MAX_CITATIONS", 2, create=True):
            _, rows = V.verify_body("## SOTA sources\n- " + "\n- ".join(entries), V.GitHub(fetch=fake))
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual([r["status"] for r in rows[2:]], [V.NOT_CHECKED] * 3)
        self.assertTrue(all("per-body cap" in r["reason"] for r in rows[2:]))

    def test_request_cap_stops_mid_citation(self):
        fake = Fake(recorded_routes())
        with mock.patch.object(V, "MAX_REQUESTS", 2, create=True):
            github = V.GitHub(fetch=fake)
            _, rows = V.verify_body("## SOTA sources\n- " + AT_FORM, github)
        self.assertEqual((len(fake.calls), github.requests, rows[0]["status"]), (2, 2, V.UNAVAILABLE))
        self.assertIn("request cap", rows[0]["reason"])

    def test_rate_limit_stops_all_later_requests(self):
        for response in [json_response(429, {}), json_response(403, {}, {"x-ratelimit-remaining": "0"}),
                         json_response(403, {"message": "secondary rate limit"})]:
            with self.subTest(status=response.status):
                routes = {(f"/repos/o/r/commits/{n:040x}", V.SHA_MEDIA): response for n in range(1, 5)}
                rows, fake = verify([f"o/r@{n:040x}:x:L1" for n in range(1, 5)], routes)
                self.assertEqual(len(fake.calls), 1)
                self.assertEqual([r["status"] for r in rows], [V.UNAVAILABLE] * 4)

    def test_contents_cache_discards_raw_bytes_and_keeps_line_blob(self):
        fake = Fake(recorded_routes())
        github = V.GitHub(fetch=fake)
        _, rows = V.verify_body("## SOTA sources\n- " + AT_FORM + "\n- " + AT_FORM.replace("L23-L24", "L1"), github)
        cached = github.cache[contents_key(MOD_RS)]
        self.assertEqual(cached.body, b"")
        self.assertEqual([r["status"] for r in rows], ["ok", "ok"])
        self.assertEqual(rows[0]["line_count"], rows[1]["line_count"])
        self.assertEqual(rows[0]["blob_sha"], rows[1]["blob_sha"])
        self.assertEqual(sum("/contents/" in key[0] for key, _, _ in fake.calls), 1)

    def test_diverged_and_behind_have_separate_counts_and_deferral(self):
        for state in ("diverged", "behind"):
            with self.subTest(state=state):
                response = json_response(200, {"status": state, "merge_base_commit": {"sha": MASTER}})
                rows, _ = verify(AT_FORM, {**recorded_routes(), compare_key(): response})
                self.assertEqual(rows[0]["status"], "not-on-default-branch:" + state)
                self.assertIn(rows[0]["status"], V.FAILURES)
        self.assertIn("phase B", V.__doc__)

    def test_invalid_header_is_safe_unavailable(self):
        def invalid(*args):
            raise ValueError("Invalid header value " + SENTINEL)
        github = V.GitHub(fetch=invalid)
        _, rows = V.verify_body("## SOTA sources\n- " + AT_FORM, github)
        self.assertEqual(rows[0]["status"], V.UNAVAILABLE)
        self.assertIn("invalid request header", rows[0]["reason"])
        self.assertNotIn(SENTINEL, json.dumps(rows))

    def test_bad_request_is_unavailable_at_every_step(self):
        routes = recorded_routes()
        for key in routes:
            if TAG[:12].upper() in key[0]:
                continue  # alternate uppercase spelling is not requested by AT_FORM
            if key[0].endswith(TAG) and key[1] == V.SHA_MEDIA:
                continue  # AT_FORM uses the prefix, not this alternate recorded route
            with self.subTest(step=key):
                rows, _ = verify(AT_FORM, {**routes, key: json_response(400, {"message": "unsupported API version"})})
                self.assertEqual(rows[0]["status"], V.UNAVAILABLE)

    def test_compare_uses_page_two_and_records_frozen_default_tip(self):
        rows, fake = verify(AT_FORM)
        keys = [key for key, _, _ in fake.calls]
        self.assertIn((f"{LYCHEE}/commits/master", V.SHA_MEDIA), keys)
        self.assertIn((f"{LYCHEE}/compare/{TAG}...{MASTER}?per_page=1&page=2", V.JSON_MEDIA), keys)
        self.assertEqual(rows[0]["default_branch_sha"], MASTER)

    def test_parser_ascii_numeric_branch_and_common_url_spellings(self):
        url = f"https://github.com/o/r/blob/{TAG}/docs/a(b).md#L1"
        for text in (url, "_" + url + "_", url.replace("github.com", "GitHub.com")):
            with self.subTest(text=text):
                citations = V.find_citations(text)
                self.assertEqual(len(citations), 1)
                self.assertEqual(citations[0].path, "docs/a(b).md")
        self.assertEqual(V.find_citations(f"o/r@{TAG}:x:L١٢"), [])
        self.assertIsNone(V.LIST_ITEM.match("١. numbered"))
        self.assertEqual(V.classify_ref("2024")[0], "unpinned")

    def test_token_whitespace_is_stripped_and_invalid_header_report_exits_zero(self):
        fake = Fake(recorded_routes())
        github = V.GitHub(fetch=fake, token=" " + SENTINEL + "\r\n")
        _, rows = V.verify_body("## SOTA sources\n- " + AT_FORM, github)
        self.assertEqual(rows[0]["status"], "ok")
        self.assertTrue(all(headers["Authorization"] == "Bearer " + SENTINEL for _, headers, _ in fake.calls))
        with mock.patch.object(V.sys, "stdin", io.StringIO("## SOTA sources\n- " + AT_FORM)):
            outcome = {**recorded_routes(), (f"{LYCHEE}/commits/{TAG[:12]}", V.SHA_MEDIA): ValueError(SENTINEL)}
            code, out, err, _ = run_main(["--body-file", "-", "--mode", "report"], outcome)
        self.assertEqual((code, json.loads(out)["counts"]), (0, {V.UNAVAILABLE: 1}))
        self.assertNotIn(SENTINEL, out + err)

    def test_redirect_budget_prevents_the_next_hop(self):
        seen = []
        def open_https(handler, req):
            seen.append(req.full_url)
            headers = Message()
            headers["Location"] = V.API + "/repositories/123"
            response = urllib.response.addinfourl(io.BytesIO(b""), headers, req.full_url, 301)
            response.msg = "Moved"
            return response
        with mock.patch.object(V, "MAX_REQUESTS", 1, create=True), mock.patch.object(
                urllib.request.HTTPSHandler, "https_open", open_https):
            github = V.GitHub()
            result = github.get("/repos/o/old")
        self.assertIsInstance(result, V.Unreachable)
        self.assertEqual((github.requests, len(seen)), (1, 1))
        self.assertIn("request cap", result.reason)


class ReviewRedirectTests(unittest.TestCase):
    def test_api_rename_keeps_auth_and_counts_each_hop(self):
        self.redirect_case(V.API + "/repositories/123", True)

    def test_other_host_redirect_never_receives_auth(self):
        self.redirect_case("https://elsewhere.example/public", False)

    def redirect_case(self, target, same_host):
        seen = []
        def open_https(handler, req):
            seen.append((req.full_url, req.get_header("Authorization")))
            status = 301 if len(seen) == 1 else 200
            headers = Message()
            if status == 301:
                headers["Location"] = target
            response = urllib.response.addinfourl(io.BytesIO(b"{}"), headers, req.full_url, status)
            response.msg = "Moved" if status == 301 else "OK"
            return response
        with mock.patch.object(urllib.request.HTTPSHandler, "https_open", open_https):
            github = V.GitHub(token=SENTINEL)
            result = github.get("/repos/o/old")
        self.assertEqual(result.status, 200)
        self.assertEqual(github.requests, 2)
        self.assertEqual(seen[0][1], "Bearer " + SENTINEL)
        self.assertEqual(seen[1][1], "Bearer " + SENTINEL if same_host else None)


if __name__ == "__main__":
    unittest.main()
