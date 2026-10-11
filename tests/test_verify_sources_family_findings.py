"""Astra FIRST and Codex regressions plus adjacent-state controls; offline only."""
import contextlib
import io
import json
import socket
import subprocess
import sys
import unittest
from unittest import mock

from tests.test_verify_sources import (
    V, ROOT, TAG, MASTER, MOD_RS, LYCHEE, AT_FORM, SENTINEL, Fake, compare_key,
    contents_key, raw_file, json_response, recorded_routes, verify, run_main,
)


class FamilyFindingsTests(unittest.TestCase):
    def test_mixed_entries_retain_every_unrecognized_candidate(self):
        candidates = [f"lycheeverse/lychee@{TAG}:{MOD_RS}:Lbad",
                      f"https://github.com/o/r/blob/{TAG}/src/x.rs",
                      f"https://github.com/o/r/blob/{TAG}/src/x.rs#Lbad",
                      "swh:1:cnt:" + TAG + ";lines=1-2"]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                rows, _ = verify(AT_FORM + " " + candidate)
                self.assertEqual([r["status"] for r in rows], ["ok", V.NOT_CHECKED])
                self.assertEqual(rows[1]["citation"], candidate)
        rows, _ = verify(AT_FORM + " " + " ".join(candidates))
        self.assertEqual(len(rows), 1 + len(candidates))

    def test_successful_raw_error_shaped_json_is_a_file(self):
        body = b'{"errors":[{"code":"too_large"}]}\n'
        rows, _ = verify(AT_FORM.replace("L23-L24", "L1"),
                         {**recorded_routes(), contents_key(MOD_RS): raw_file(body)})
        self.assertEqual((rows[0]["status"], rows[0]["line_count"], rows[0]["blob_sha"]),
                         ("ok", 1, V.git_blob_sha(body)))
        self.assertFalse(V.too_large(raw_file(body)))

    def test_long_start_and_end_numbers_emit_report_and_summary_without_requests(self):
        for lines in ("L" + "1" * 5000, "L1-L" + "1" * 5000):
            with self.subTest(which=lines[:3]):
                body = "## SOTA sources\n- o/r@" + "a" * 40 + ":f:" + lines + "\n"
                with mock.patch.object(V.sys, "stdin", io.StringIO(body)):
                    code, out, err, fake = run_main(["--body-file", "-", "--mode", "report"])
                report = json.loads(out)
                self.assertEqual((code, report["counts"], fake.calls),
                                 (0, {"line-range-out-of-bounds": 1}, []))
                self.assertIn("line-range-out-of-bounds", V.markdown(report))
                self.assertNotIn("Traceback", err)

    def test_matching_hex_branch_or_tag_is_unpinned(self):
        for namespace in ("heads", "tags"):
            with self.subTest(namespace=namespace):
                prefix = TAG[:12]
                routes = recorded_routes()
                routes[(f"{LYCHEE}/git/ref/{namespace}/{prefix}", V.JSON_MEDIA)] = json_response(
                    200, {"ref": f"refs/{namespace}/{prefix}", "object": {"sha": TAG}})
                rows, fake = verify(AT_FORM, routes)
                self.assertEqual(rows[0]["status"], "unpinned")
                self.assertFalse(any("/contents/" in key[0] for key, _, _ in fake.calls))

    def test_408_is_unavailable_at_all_steps_and_enforce_exits_three(self):
        routes = recorded_routes()
        for key in routes:
            if TAG[:12].upper() in key[0]:
                continue
            if key == (f"{LYCHEE}/commits/{TAG}", V.SHA_MEDIA):
                continue
            with self.subTest(step=key[0]):
                rows, _ = verify(AT_FORM, {**routes, key: json_response(408, {"message": "Request Timeout"})})
                self.assertEqual((rows[0]["status"], V.exit_code(rows, "enforce")), (V.UNAVAILABLE, 3))

    def test_embedded_header_controls_never_reach_fetch_or_socket(self):
        for control in ("\r", "\n", "\r\n"):
            with self.subTest(control=repr(control)):
                sentinel = SENTINEL + control + "invalid"
                with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")) as connect:
                    code, out, err, fake = run_main(["--repo", "o/r", "--pr", "1", "--mode", "report"],
                                                  environment={"GITHUB_TOKEN": sentinel})
                self.assertEqual(code, 0)
                self.assertEqual(fake.calls, [])
                self.assertFalse(connect.called)
                self.assertNotIn(SENTINEL, out + err)
                self.assertIn("invalid authorization", json.loads(out)["error"])

    def test_branch_moving_between_citations_uses_one_snapshot(self):
        routes = recorded_routes()
        other = "a" * 40
        routes[(f"{LYCHEE}/commits/{other}", V.SHA_MEDIA)] = V.Response(200, {}, other.encode())
        routes[(f"{LYCHEE}/git/commits/{other}", V.JSON_MEDIA)] = json_response(200, {"sha": other})
        routes[(f"{LYCHEE}/contents/{MOD_RS}?ref={other}", V.RAW_MEDIA)] = raw_file(b"x\n")
        routes[compare_key(other)] = json_response(200, {"status": "ahead", "merge_base_commit": {"sha": other}})
        fake = Fake(routes)
        def moving(url, headers, timeout, limit):
            response = fake(url, headers, timeout, limit)
            if "/compare/" in url:
                fake.routes[(f"{LYCHEE}/commits/master", V.SHA_MEDIA)] = V.Response(200, {}, ("b" * 40).encode())
            return response
        _, rows = V.verify_body("## SOTA sources\n- " + AT_FORM + f"\n- lycheeverse/lychee@{other}:{MOD_RS}:L1",
                                V.GitHub(fetch=moving))
        self.assertEqual([r["status"] for r in rows], ["ok", "ok"])
        self.assertEqual([r["default_branch_sha"] for r in rows], [MASTER, MASTER])
        self.assertEqual(sum(key[0].endswith("/commits/master") for key, _, _ in fake.calls), 1)

    def test_rate_limit_stop_also_blocks_prior_cached_requests(self):
        fake = Fake({("/a", V.JSON_MEDIA): json_response(200, {}),
                     ("/limited", V.JSON_MEDIA): json_response(403, {}, {"x-ratelimit-remaining": "0"})})
        github = V.GitHub(fetch=fake)
        self.assertEqual(github.get("/a").status, 200)
        self.assertEqual(github.get("/limited").status, 403)
        self.assertIsInstance(github.get("/a"), V.Unreachable)
        self.assertIsInstance(github.get("/other"), V.Unreachable)
        self.assertEqual((github.requests, len(fake.calls)), (2, 2))

    def test_actual_cli_rejects_long_numbers_and_bad_auth_without_network(self):
        runner = ("import socket,runpy; "
                  "socket.create_connection=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network')); "
                  f"runpy.run_path({str(ROOT / 'tools/sota-sources/verify_sources.py')!r},run_name='__main__')")
        for lines in ("L" + "1" * 5000, "L1-L" + "1" * 5000):
            result = subprocess.run([sys.executable, "-E", "-s", "-B", "-c", runner, "--body-file", "-"],
                                    input="## SOTA sources\n- o/r@" + "a" * 40 + ":f:" + lines,
                                    env={}, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["counts"], {"line-range-out-of-bounds": 1})
        result = subprocess.run([sys.executable, "-E", "-s", "-B", "-c", runner, "--repo", "o/r", "--pr", "1"],
                                env={"GITHUB_TOKEN": SENTINEL + "\ninvalid"}, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn(SENTINEL, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["requests"], 0)
        self.assertIn("invalid authorization", report["error"])

    def test_named_ref_lookup_failures_are_indeterminate_and_uppercase_ref_is_checked(self):
        key = (f"{LYCHEE}/git/ref/heads/{TAG[:12]}", V.JSON_MEDIA)
        for response in (json_response(200, {}), json_response(200, []), json_response(403, {}),
                         json_response(422, {}), V.Response(200, {}, b"{}", True)):
            with self.subTest(status=response.status):
                rows, _ = verify(AT_FORM, {**recorded_routes(), key: response})
                self.assertEqual(rows[0]["status"], V.UNAVAILABLE)
        spelling = TAG[:12].upper()
        key = (f"{LYCHEE}/git/ref/heads/{spelling}", V.JSON_MEDIA)
        response = json_response(200, {"ref": "refs/heads/" + spelling})
        rows, _ = verify(AT_FORM.replace(TAG[:12], spelling), {**recorded_routes(), key: response})
        self.assertEqual(rows[0]["status"], "unpinned")

    def test_full_sha_422_remains_a_failure_and_unknown_candidates_are_independent(self):
        key = (f"{LYCHEE}/commits/{TAG}", V.SHA_MEDIA)
        rows, _ = verify(AT_FORM.replace(TAG[:12], TAG), {**recorded_routes(), key: json_response(422, {})})
        self.assertEqual(rows[0]["status"], "commit-not-found")
        rows, _ = verify(f"o/r@{TAG}:x:Lbad o/r@{TAG}:x:Lbad")
        self.assertEqual([r["status"] for r in rows], [V.NOT_CHECKED, V.NOT_CHECKED])
        self.assertTrue(all("candidate_span" in r for r in rows))

    def test_redirect_origin_boundary_excludes_userinfo_ports_and_http(self):
        for url in ("http://api.github.com/x", "https://api.github.com:444/x",
                    "https://user@api.github.com/x", "https://api.github.com.evil.example/x"):
            with self.subTest(url=url):
                self.assertFalse(V.api_origin(url))
        self.assertTrue(V.api_origin("https://api.github.com:443/x"))


if __name__ == "__main__":
    unittest.main()
