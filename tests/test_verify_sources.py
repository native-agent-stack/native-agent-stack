"""tools/sota-sources/verify_sources.py, the W1b phase A code-citation verifier, on recorded fixtures only.

tests/fixtures/verify_sources/github-rest-recorded.json holds api.github.com responses recorded on 2026-10-11 through
the verifier's own fetcher (unauthenticated), trimmed to the fields it reads. Responses the API cannot be made to
return on demand are synthetic and say so: a timeout, a 429, a 503 and a rate-limited 403, a hex-named branch, both
over-100 MB signals, a JSON object for a symlink or a submodule, and a compare that says "ahead" with another merge
base. No test touches the network.

Correction #151: every rule has a fixture that fails it and one that passes it. RULES names both tests for each rule,
and test_every_rule_has_a_failing_and_a_passing_fixture holds RULES to the verifier's own status list.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unicodedata
import unittest
from unittest import mock
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "sota-sources"))
import verify_sources as V  # noqa: E402

RECORDED = json.loads((ROOT / "tests/fixtures/verify_sources/github-rest-recorded.json").read_text(encoding="utf-8"))
LYCHEE = "/repos/lycheeverse/lychee"
TAG = "2bba271688c1abb1503097a064e6c3bc1d1b6a9b"  # lychee-v0.24.2
MOD_RS = "lychee-lib/src/quirks/mod.rs"
FORK_BEHIND = "5d57da580790e360a88d38d6af6e1e1b122f15a7"  # lychee PR #2316's head, pushed to a fork
FORK_DIVERGED = "2677ce10d16fb8444c70fdeabbd9c7be75fe8f62"  # lychee PR #2311's head, pushed to a fork
MASTER = RECORDED["lychee_master_at_recording"]
LINES = RECORDED["responses"]["contents-file"]["synthetic_lines"]
AT_FORM = f"[mechanism] lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L23-L24"
URL_FORM = f"[mechanism] https://github.com/lycheeverse/lychee/blob/{TAG}/{MOD_RS}#L23-L24"
SENTINEL = "sentinel-token-never-printed-0123456789"  # not token-shaped, so the publication scan stays clean

# Correction #151: (rule, the test whose fixture fails the rule, the test whose fixture passes it).
RULES = (
    ("section heading", "SectionTests.test_a_lower_case_heading_is_no_section",
     "SectionTests.test_a_level_three_heading_is_the_section"),
    ("role tags", "GrammarTests.test_an_untagged_or_malformed_entry_has_role_unknown",
     "GrammarTests.test_each_role_tag_parses"),
    ("short-sha", "ShaPolicyTests.test_eight_hex_characters_are_short_sha_without_a_request",
     "ShaPolicyTests.test_a_twelve_hex_ref_resolves_and_records_the_full_sha"),
    ("unpinned", "ShaPolicyTests.test_a_branch_or_tag_ref_is_unpinned_without_a_request",
     "ShaPolicyTests.test_a_full_sha_url_passes"),
    ("unpinned: hex-named branch", "ShaPolicyTests.test_a_hex_named_branch_resolving_elsewhere_is_unpinned",
     "ShaPolicyTests.test_a_twelve_hex_ref_resolves_and_records_the_full_sha"),
    ("commit-not-found", "CommitTests.test_a_ref_or_commit_github_cannot_find_is_commit_not_found",
     "CommitTests.test_a_commit_github_finds_passes"),
    ("path-not-found", "ContentsTests.test_a_missing_path_is_path_not_found",
     "ContentsTests.test_a_present_path_passes"),
    ("path-is-directory", "ContentsTests.test_a_directory_is_path_is_directory",
     "ContentsTests.test_a_present_path_passes"),
    ("unverifiable-size", "ContentsTests.test_over_100_mb_is_unverifiable_size",
     "ContentsTests.test_over_1_mb_is_read_through_the_raw_media_type"),
    ("line-range-out-of-bounds", "LineRangeTests.test_a_range_outside_the_file_is_out_of_bounds",
     "LineRangeTests.test_a_range_inside_the_file_passes"),
    ("not-on-default-branch", "AncestryTests.test_behind_diverged_or_another_merge_base_is_not_on_default_branch",
     "AncestryTests.test_ahead_or_identical_with_the_cited_merge_base_passes"),
    ("not-on-default-branch:behind", "AncestryTests.test_behind_diverged_or_another_merge_base_is_not_on_default_branch",
     "AncestryTests.test_ahead_or_identical_with_the_cited_merge_base_passes"),
    ("not-on-default-branch:diverged", "AncestryTests.test_behind_diverged_or_another_merge_base_is_not_on_default_branch",
     "AncestryTests.test_ahead_or_identical_with_the_cited_merge_base_passes"),
    ("unavailable", "UnavailableTests.test_timeout_429_503_and_rate_limits_are_unavailable_not_failures",
     "UnavailableTests.test_a_plain_403_is_a_failure_not_unavailable"),
    ("symlink note", "ContentsTests.test_a_symlink_to_a_file_is_checked_against_its_target_with_a_note",
     "ContentsTests.test_a_present_path_passes"),
    ("enforce exit codes", "ExitCodeTests.test_enforce_exits_1_on_a_failure_and_3_when_only_unavailable",
     "ExitCodeTests.test_enforce_exits_0_when_all_is_ok_and_report_always_exits_0"),
)


def replay(label):
    """A recorded response as the fetcher returns it."""
    record = RECORDED["responses"][label]
    if "json" in record:
        body = json.dumps(record["json"]).encode()
    elif "text" in record:
        body = record["text"].encode()
    else:
        body = numbered_lines(record["synthetic_lines"])
    return V.Response(record["status"], dict(record["headers"]), body)


def route(label):
    record = RECORDED["responses"][label]
    return record["path"], record["accept"]


def numbered_lines(count):
    return b"".join(b"line %d\n" % number for number in range(1, count + 1))


def raw_file(body):
    return V.Response(200, {"content-type": "application/vnd.github.raw+json; charset=utf-8",
                            "etag": '"%s"' % V.git_blob_sha(body)}, body)


def json_response(status, data, headers=None):
    return V.Response(status, {"content-type": "application/json; charset=utf-8", **(headers or {})},
                      json.dumps(data).encode())


def contents_key(path, sha=TAG):
    return f"{LYCHEE}/contents/{path}?ref={sha}", V.RAW_MEDIA


def compare_key(sha=TAG):
    return f"{LYCHEE}/compare/{sha}...{MASTER}?per_page=1&page=2", V.JSON_MEDIA


def recorded_routes():
    """lycheeverse/lychee@2bba271688c1:lychee-lib/src/quirks/mod.rs, every response as recorded: all checks pass."""
    routes = {route(label): replay(label) for label in
              ("commit-sha-12", "commit-sha-40", "git-commit", "contents-file", "repository")}
    # Synthetic replay of the recorded comparison against its recorded tip, now on page 2.
    routes[compare_key()] = replay("compare-ahead")
    routes[(f"{LYCHEE}/commits/master", V.SHA_MEDIA)] = V.Response(200, {}, MASTER.encode())
    for namespace in ("heads", "tags"):
        for spelling in (TAG[:12], TAG[:12].upper()):
            routes[(f"{LYCHEE}/git/ref/{namespace}/{spelling}", V.JSON_MEDIA)] = json_response(404, {"message": "Not Found"})
    return routes


def routes_at(sha, compare, commit_label=None, git_label=None, repository=LYCHEE, path=MOD_RS, body=None):
    """Passing routes for <repository>@<sha>:<path> up to the comparison, which returns `compare`; the responses
    not named by a recorded label are synthetic, in the recorded shapes."""
    resolved = replay(commit_label) if commit_label else V.Response(
        200, {"content-type": "application/vnd.github.sha; charset=utf-8"}, sha.encode())
    return {(f"{repository}/git/ref/heads/{sha[:12]}", V.JSON_MEDIA): json_response(404, {"message": "Not Found"}),
            (f"{repository}/git/ref/tags/{sha[:12]}", V.JSON_MEDIA): json_response(404, {"message": "Not Found"}),
            (f"{repository}/commits/{sha[:12]}", V.SHA_MEDIA): resolved,
            (f"{repository}/commits/{sha}", V.SHA_MEDIA): resolved,
            (f"{repository}/git/commits/{sha}", V.JSON_MEDIA):
                replay(git_label) if git_label else json_response(200, {"sha": sha}),
            (f"{repository}/contents/{urllib.parse.quote(path)}?ref={sha}", V.RAW_MEDIA):
                raw_file(numbered_lines(LINES) if body is None else body),
            (repository, V.JSON_MEDIA):
                replay("repository") if repository == LYCHEE else json_response(200, {"default_branch": "master"}),
            (f"{repository}/commits/master", V.SHA_MEDIA): V.Response(200, {}, MASTER.encode()),
            (f"{repository}/compare/{sha}...{MASTER}?per_page=1&page=2", V.JSON_MEDIA): compare}


class Fake:
    """A fetcher over {(path, accept): Response or exception}; a request outside the table fails the test."""

    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []

    def __call__(self, url, headers, timeout, limit):
        assert url.startswith(V.API + "/"), url
        key = (url[len(V.API):], headers["Accept"])
        self.calls.append((key, dict(headers), limit))
        if key not in self.routes:
            raise AssertionError(f"unrouted request {key}")
        outcome = self.routes[key]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def verify(entries, routes=None):
    """(rows, fetcher) for a SOTA sources section holding `entries` (one string or several)."""
    fake = Fake(recorded_routes() if routes is None else routes)
    entries = [entries] if isinstance(entries, str) else entries
    body = "## Summary\n\nx\n\n### SOTA sources\n\n" + "".join(f"- {entry}\n" for entry in entries) + "\n### Next\n"
    _, rows = V.verify_body(body, V.GitHub(fetch=fake))
    return rows, fake


def run_main(arguments, routes=None, environment=None):
    """(exit code, stdout, stderr, fetcher) of main() with only `environment` among the variables it reads."""
    fake = Fake(routes or {})
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, environment or {}):
        for name in ("GITHUB_TOKEN", "GITHUB_STEP_SUMMARY"):
            if name not in (environment or {}):
                os.environ.pop(name, None)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = V.main(arguments, fetch=fake)
    return code, out.getvalue(), err.getvalue(), fake


class SectionTests(unittest.TestCase):
    """The section is found exactly as the required sota-sources check finds it."""

    JS_PATTERN = r"/^#{2,3}[ \t]+SOTA sources[ \t]*$([\s\S]*?)(?=^#{2,3}[ \t]|(?![\s\S]))/m"
    EDGE_BODIES = (
        "## SOTA sources\r- lone carriage returns\r",
        "## SOTA sources - line separators ",
        "## SOTA sources\n \n",
        "## SOTA sources\n﻿\n",
        "## SOTA sources\n\x1c\n",
        "## SOTA sources\n\x85\n",
        "## SOTA sources\n᠎\n",
        "##\tSOTA sources\t\n- tabs\n",
        "## SOTA sources:\n- a colon\n",
        "### SOTA sources\n<!-- c -->\n- after a comment\n### Next\n",
        "## SOTA sources\n\n## SOTA sources\n- only the second has content\n",
        "# SOTA sources\n- level one\n",
        " ## SOTA sources\n- indented\n",
        "## SOTA sources\n- \U0001F600\n",
    )

    def test_the_section_regex_is_the_required_checks(self):
        for name in ("pr-metadata.yml", "sota-sources-gate.yml"):
            with self.subTest(workflow=name):
                workflow = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
                self.assertIn(f"body.match({self.JS_PATTERN});", workflow)
                self.assertIn(r"match[1].replace(/<!--[\s\S]*?-->/g, '').trim()", workflow)
        self.assertEqual("/" + V.SOTA_SECTION.pattern + "/m", self.JS_PATTERN)
        self.assertEqual(V.HTML_COMMENT.pattern, r"<!--[\s\S]*?-->")

    def test_js_trim_is_white_space_plus_line_terminators(self):
        # ECMAScript WhiteSpace and LineTerminator: tc39/ecma262@5345883164f463e87f8b40aca4956157ecba8783:spec.html,
        # the White Space and Line Terminators clauses; USP is every Space_Separator (Zs) code point.
        space_separators = {chr(code) for code in range(0x110000) if unicodedata.category(chr(code)) == "Zs"}
        self.assertEqual(set(V.JS_TRIM), {"\t", "\v", "\f", "﻿", "\n", "\r", " ", " "} | space_separators)

    @unittest.skipUnless(shutil.which("node"), "node unavailable; CI's runner images carry it")
    def test_the_mirror_and_the_workflow_script_pass_and_fail_the_same_bodies(self):
        from tests.test_sota_sources_gate import CASES, GATE, VALIDATE, body, inline_script, run_check, sota_job
        payloads = [payload for _, payload, _ in CASES] + [body(text) for text in self.EDGE_BODIES]
        for path in (VALIDATE, GATE):
            outcomes = run_check(inline_script(sota_job(path)), payloads)
            for payload, outcome in zip(payloads, outcomes):
                text = (payload.get("pull_request") or {}).get("body")
                with self.subTest(workflow=path.name, body=text):
                    self.assertIs(outcome["failed"] is None, bool(V.sota_section_content(text)), outcome)

    def test_a_lower_case_heading_is_no_section(self):
        content, rows = V.verify_body("## sota sources\n- " + AT_FORM + "\n", V.GitHub(fetch=Fake({})))
        self.assertEqual((content, rows), ("", []))

    def test_a_level_three_heading_is_the_section(self):
        content, rows = V.verify_body("### SOTA sources\n- " + AT_FORM + "\n", V.GitHub(fetch=Fake(recorded_routes())))
        self.assertEqual(content, "- " + AT_FORM)
        self.assertEqual([row["status"] for row in rows], ["ok"])

    def test_a_missing_section_is_reported_and_exits_0_in_enforce_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "body.md"
            path.write_text("## Summary\nno sources\n", encoding="utf-8")
            code, out, _, fake = run_main(["--body-file", str(path), "--mode", "enforce"])
        report = json.loads(out)
        self.assertEqual((code, report["section"], report["rows"], fake.calls),
                         (0, {"present": False, "characters": 0}, [], []))


class GrammarTests(unittest.TestCase):
    def test_both_citation_forms_and_their_line_spellings_parse(self):
        url = f"https://github.com/lycheeverse/lychee/blob/{TAG}/{MOD_RS}"
        cases = {
            f"{url}#L23-L24": (TAG, 23, 24),
            f"{url}#L23": (TAG, 23, 23),
            f"{url}?plain=1#L5C2-L7C9": (TAG, 5, 7),
            f"lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L23-L24": (TAG[:12], 23, 24),
            f"lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L23": (TAG[:12], 23, 23),
            f"lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L23-24": (TAG[:12], 23, 24),
            f"see `lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L23-L24`, the quirk": (TAG[:12], 23, 24),
            f"[the quirk]({url}#L94-L98).": (TAG, 94, 98),
        }
        for text, (ref, start, end) in cases.items():
            with self.subTest(text=text):
                (citation,) = V.find_citations(text)
                self.assertEqual((citation.owner, citation.repo, citation.ref, citation.path, citation.start,
                                  citation.end), ("lycheeverse", "lychee", ref, MOD_RS, start, end))

    def test_a_percent_encoded_url_path_is_decoded_and_requoted(self):
        (citation,) = V.find_citations(f"https://github.com/o/r/blob/{TAG}/docs/a%20b.md?plain=1#L1")
        self.assertEqual(citation.path, "docs/a b.md")
        routes = routes_at(TAG, json_response(200, {"status": "ahead", "merge_base_commit": {"sha": TAG}}),
                           repository="/repos/o/r", path="docs/a b.md", body=b"x\n")
        self.assertIn((f"/repos/o/r/contents/docs/a%20b.md?ref={TAG}", V.RAW_MEDIA), routes)
        rows, _ = verify(f"https://github.com/o/r/blob/{TAG}/docs/a%20b.md?plain=1#L1", routes)
        self.assertEqual(rows[0]["status"], "ok", rows[0])

    def test_entries_without_a_code_citation_are_listed_as_not_checked_in_phase_a(self):
        entries = {
            f"[reference] https://github.com/lycheeverse/lychee/blob/{TAG}/{MOD_RS}":
                "a GitHub blob URL without a #L line anchor",
            "[reference] https://docs.github.com/en/rest/repos/contents": "a document or other URL",
            "[reference] swh:1:cnt:16123f54b8b404d596ec69d7a08ea51b73064673": "a SWHID",
            "[adopt] pypi:requests@2.32.3": "no code citation",
            f"[reference] https://github.com/lycheeverse/lychee/tree/{TAG}/lychee-lib": "a document or other URL",
        }
        rows, fake = verify(list(entries))
        self.assertEqual(fake.calls, [])
        self.assertEqual([(row["status"], row["reason"]) for row in rows],
                         [(V.NOT_CHECKED, f"not checked in phase A: {kind}") for kind in entries.values()])
        self.assertEqual(V.exit_code(rows, "enforce"), 0)

    def test_list_items_paragraphs_and_continuation_lines_are_entries(self):
        content = ("- [mechanism] first\n  continued\n* second\n1. third\n2) fourth\n\nA paragraph\nthat goes on.\n"
                   "\n  - [adopt] nested\n")
        self.assertEqual([(entry.text, entry.role) for entry in V.parse_entries(content)],
                         [("[mechanism] first continued", "mechanism"), ("second", "unknown"), ("third", "unknown"),
                          ("fourth", "unknown"), ("A paragraph that goes on.", "unknown"), ("[adopt] nested", "adopt")])

    def test_each_role_tag_parses(self):
        cases = {"[mechanism] x": ("mechanism", None), "[adopt] x": ("adopt", None), "[reference] x": ("reference", None),
                 "[trial:cmp-2026-10-11-a] x": ("trial", "cmp-2026-10-11-a"),
                 "[exception:docs/decisions/x.md] x": ("exception", "docs/decisions/x.md")}
        entries = V.parse_entries("\n".join(f"- {text}" for text in cases))
        self.assertEqual([(entry.role, entry.role_ref) for entry in entries], list(cases.values()))

    def test_an_untagged_or_malformed_entry_has_role_unknown(self):
        texts = ("x", "[trial:] x", "[exception] x", "[Mechanism] x", "[adopt](https://example.org) x",
                 "x [mechanism]", "[mech] x")
        entries = V.parse_entries("\n".join(f"- {text}" for text in texts))
        self.assertEqual([entry.role for entry in entries], ["unknown"] * len(texts))
        rows, _ = verify(f"lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L23-L24")
        self.assertEqual((rows[0]["role"], rows[0]["status"]), ("unknown", "ok"))

    def test_one_citation_repeated_in_an_entry_is_one_row(self):
        rows, _ = verify(f"{AT_FORM} and again lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L23-L24")
        self.assertEqual(len(rows), 1)


class ShaPolicyTests(unittest.TestCase):
    def test_eight_hex_characters_are_short_sha_without_a_request(self):
        for ref in (TAG[:8], TAG[:11], TAG[:6]):
            with self.subTest(ref=ref):
                rows, fake = verify(f"lycheeverse/lychee@{ref}:{MOD_RS}:L23")
                self.assertEqual((rows[0]["status"], fake.calls), ("short-sha", []))

    def test_a_twelve_hex_ref_resolves_and_records_the_full_sha(self):
        rows, fake = verify(AT_FORM)
        self.assertEqual((rows[0]["status"], rows[0]["sha"], rows[0]["ref"]), ("ok", TAG, TAG[:12]))
        self.assertIn((f"{LYCHEE}/commits/{TAG[:12]}", V.SHA_MEDIA), [key for key, _, _ in fake.calls])
        upper, _ = verify(f"lycheeverse/lychee@{TAG[:12].upper()}:{MOD_RS}:L23-L24")
        self.assertEqual((upper[0]["status"], upper[0]["sha"]), ("ok", TAG))

    def test_a_full_sha_url_passes(self):
        rows, fake = verify(URL_FORM)
        self.assertEqual((rows[0]["status"], rows[0]["sha"]), ("ok", TAG))
        self.assertEqual([key for key, _, _ in fake.calls],
                         [(f"{LYCHEE}/commits/{TAG}", V.SHA_MEDIA), (f"{LYCHEE}/git/commits/{TAG}", V.JSON_MEDIA),
                          contents_key(MOD_RS), (LYCHEE, V.JSON_MEDIA),
                          (f"{LYCHEE}/commits/master", V.SHA_MEDIA), compare_key()])

    def test_a_branch_or_tag_ref_is_unpinned_without_a_request(self):
        for ref in ("master", "lychee-v0.24.2", "release/1.x", TAG + "0"):
            with self.subTest(ref=ref):
                rows, fake = verify(f"https://github.com/lycheeverse/lychee/blob/{ref}/{MOD_RS}#L23-L24")
                self.assertEqual((rows[0]["status"], fake.calls), ("unpinned", []))

    def test_a_hex_named_branch_resolving_elsewhere_is_unpinned(self):
        # Synthetic: a branch named like the 12-hex prefix resolves to another commit (here the recorded master).
        routes = recorded_routes()
        routes[route("commit-sha-12")] = V.Response(200, {"content-type": "application/vnd.github.sha"},
                                                    MASTER.encode())
        rows, fake = verify(AT_FORM, routes)
        self.assertEqual((rows[0]["status"], rows[0]["sha"], len(fake.calls)), ("unpinned", None, 3))
        self.assertIn(f"resolves to {MASTER}", rows[0]["reason"])


class CommitTests(unittest.TestCase):
    def test_a_ref_or_commit_github_cannot_find_is_commit_not_found(self):
        missing = "0123456789ab"
        routes = {route("commit-sha-missing"): replay("commit-sha-missing"),
                  (f"{LYCHEE}/git/ref/heads/{missing}", V.JSON_MEDIA): json_response(404, {}),
                  (f"{LYCHEE}/git/ref/tags/{missing}", V.JSON_MEDIA): json_response(404, {})}
        rows, _ = verify(f"lycheeverse/lychee@{missing}:{MOD_RS}:L1", routes)
        self.assertEqual((rows[0]["status"], rows[0]["http_status"]), ("sha-unresolved", 422))
        self.assertIn("cite the full SHA", rows[0]["reason"])
        routes = recorded_routes()
        routes[route("git-commit")] = replay("git-commit-missing")
        rows, _ = verify(AT_FORM, routes)
        self.assertEqual((rows[0]["status"], rows[0]["http_status"], rows[0]["sha"]), ("commit-not-found", 404, TAG))

    def test_a_commit_github_finds_passes(self):
        rows, fake = verify(AT_FORM)
        self.assertEqual(rows[0]["status"], "ok")
        self.assertIn(((f"{LYCHEE}/git/commits/{TAG}", V.JSON_MEDIA)), [key for key, _, _ in fake.calls])


class ContentsTests(unittest.TestCase):
    def test_a_present_path_passes(self):
        rows, fake = verify(AT_FORM)
        row = rows[0]
        self.assertEqual((row["status"], row["line_count"], row["notes"]), ("ok", LINES, []))
        self.assertEqual(row["blob_sha"], V.git_blob_sha(numbered_lines(LINES)))
        (contents,) = [(headers, limit) for key, headers, limit in fake.calls if "/contents/" in key[0]]
        self.assertEqual((contents[0]["Accept"], contents[1]), (V.RAW_MEDIA, V.MAX_CONTENT_BYTES))

    def test_a_missing_path_is_path_not_found(self):
        routes = recorded_routes()
        routes[route("contents-missing")] = replay("contents-missing")
        rows, _ = verify(f"lycheeverse/lychee@{TAG[:12]}:no/such/file.rs:L1", routes)
        self.assertEqual((rows[0]["status"], rows[0]["http_status"]), ("path-not-found", 404))
        for path in ("../etc/passwd", "a//b.py", "a/./b.py"):
            with self.subTest(path=path):
                rows, fake = verify(f"lycheeverse/lychee@{TAG[:12]}:{path}:L1")
                self.assertEqual(rows[0]["status"], "path-not-found")
                self.assertFalse(any("/contents/" in key[0] for key, _, _ in fake.calls))

    def test_a_directory_is_path_is_directory(self):
        routes = recorded_routes()
        routes[route("contents-directory")] = replay("contents-directory")
        rows, _ = verify(f"lycheeverse/lychee@{TAG[:12]}:lychee-lib/src/quirks:L1", routes)
        self.assertEqual(rows[0]["status"], "path-is-directory")
        # Synthetic, from the documented object responses: a submodule, and a symlink whose target is not a file.
        for data, status in (({"type": "submodule", "sha": TAG}, "path-is-directory"),
                             ({"type": "symlink", "target": "../elsewhere"}, "path-not-found")):
            with self.subTest(kind=data["type"]):
                routes = recorded_routes()
                routes[contents_key(MOD_RS)] = json_response(200, data)
                rows, _ = verify(AT_FORM, routes)
                self.assertEqual(rows[0]["status"], status)

    def test_a_json_file_served_raw_is_a_file(self):
        routes = recorded_routes()
        routes[contents_key(MOD_RS)] = V.Response(200, {"content-type": "application/vnd.github.raw+json"},
                                                  b'[\n  "a list in a .json file"\n]\n')
        rows, _ = verify(f"lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L1-L3", routes)
        self.assertEqual((rows[0]["status"], rows[0]["line_count"]), ("ok", 3))

    def test_over_1_mb_is_read_through_the_raw_media_type(self):
        # Synthetic body; JSON mode would return content "" and encoding "none" above 1 MB (recorded 2026-10-11 for
        # github/rest-api-description's 13 MB api.github.com.json), so the request asks for the raw media type.
        body = numbered_lines(150_000)
        self.assertGreater(len(body), 1024 * 1024)
        routes = recorded_routes()
        routes[contents_key(MOD_RS)] = raw_file(body)
        rows, fake = verify(f"lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L149999-L150000", routes)
        self.assertEqual((rows[0]["status"], rows[0]["line_count"]), ("ok", 150_000))
        self.assertIn((contents_key(MOD_RS), V.MAX_CONTENT_BYTES),
                      [(key, limit) for key, headers, limit in fake.calls if headers["Accept"] == V.RAW_MEDIA])

    def test_over_100_mb_is_unverifiable_size(self):
        # Both synthetic and docs-derived ("Greater than 100 MB: This endpoint is not supported"): no such file was
        # observed. A 200 the fetcher cut off at the cap, and a refusal carrying a too_large error code.
        cut = V.Response(200, {"content-type": "application/vnd.github.raw+json",
                               "content-length": str(V.MAX_CONTENT_BYTES + 1)}, b"", oversize=True)
        refused = json_response(403, {"message": "This API returns blobs up to 100 MB in size.",
                                      "errors": [{"resource": "Blob", "field": "data", "code": "too_large"}]})
        for name, response in (("cut", cut), ("refused", refused)):
            with self.subTest(response=name):
                routes = recorded_routes()
                routes[contents_key(MOD_RS)] = response
                rows, _ = verify(AT_FORM, routes)
                self.assertEqual(rows[0]["status"], "unverifiable-size")

    def test_a_symlink_to_a_file_is_checked_against_its_target_with_a_note(self):
        # Recorded from Wilfred/difftastic's CLAUDE.md -> AGENTS.md: the body is the target's (synthetic here, with
        # the recorded line count) and the ETag stays the link's own blob SHA.
        recorded = RECORDED["responses"]["contents-symlink-to-file"]
        routes = recorded_routes()
        routes[contents_key(MOD_RS)] = replay("contents-symlink-to-file")
        rows, _ = verify(f"lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L1-L3", routes)
        row = rows[0]
        self.assertEqual((row["status"], row["line_count"]), ("ok", recorded["synthetic_lines"]))
        (note,) = row["notes"]
        self.assertIn(recorded["headers"]["etag"].strip('"'), note)
        self.assertNotEqual(recorded["recorded"]["etag"].strip('"'), recorded["recorded"]["content_blob"])

    def test_a_symlink_to_a_directory_reads_as_its_link_text_an_untested_boundary(self):
        # Recorded: the raw request returned the link text with a matching ETag, so one request reads it as a
        # one-line file. The module docstring lists this as an untested boundary.
        routes = recorded_routes()
        routes[contents_key(MOD_RS)] = replay("contents-symlink-to-directory")
        rows, _ = verify(f"lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L1", routes)
        self.assertEqual((rows[0]["status"], rows[0]["line_count"], rows[0]["notes"]), ("ok", 1, []))


class LineRangeTests(unittest.TestCase):
    def test_line_count_matches_a_numbered_file_view(self):
        for content, count in ((b"", 0), (b"a", 1), (b"a\n", 1), (b"a\nb", 2), (b"\n", 1), (b"a\r\nb\r\n", 2)):
            with self.subTest(content=content):
                self.assertEqual(V.line_count(content), count)
        self.assertEqual(RECORDED["responses"]["contents-file"]["recorded"]["lines"], LINES)

    def test_a_range_inside_the_file_passes(self):
        for lines in ("L23-L24", "L1", f"L{LINES}", f"L1-L{LINES}"):
            with self.subTest(lines=lines):
                rows, _ = verify(f"lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:{lines}")
                self.assertEqual(rows[0]["status"], "ok")

    def test_a_range_outside_the_file_is_out_of_bounds(self):
        for lines in (f"L{LINES}-L{LINES + 1}", f"L{LINES + 1}", "L0", "L0-L3", "L24-L23"):
            with self.subTest(lines=lines):
                rows, fake = verify(f"lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:{lines}")
                self.assertEqual(rows[0]["status"], "line-range-out-of-bounds")
                self.assertNotIn(compare_key(), [key for key, _, _ in fake.calls])


class AncestryTests(unittest.TestCase):
    def test_ahead_or_identical_with_the_cited_merge_base_passes(self):
        rows, _ = verify(AT_FORM)
        self.assertEqual((rows[0]["status"], rows[0]["compare_status"], rows[0]["default_branch"]),
                         ("ok", "ahead", "master"))
        rows, _ = verify(f"lycheeverse/lychee@{MASTER[:12]}:{MOD_RS}:L1", routes_at(MASTER, replay("compare-identical")))
        self.assertEqual((rows[0]["status"], rows[0]["compare_status"]), ("ok", "identical"))

    def test_behind_diverged_or_another_merge_base_is_not_on_default_branch(self):
        # Recorded: a fork's commit resolves, has a commit object and has the file through the upstream's own
        # endpoints; only the comparison shows it is not on master.
        behind = routes_at(FORK_BEHIND, replay("compare-behind-fork"), "commit-sha-fork", "git-commit-fork")
        diverged = routes_at(FORK_DIVERGED, replay("compare-diverged-fork"))
        synthetic = json_response(200, {"status": "ahead", "merge_base_commit": {"sha": MASTER}})
        cases = ((FORK_BEHIND, behind, "behind"), (FORK_DIVERGED, diverged, "diverged"),
                 (TAG, {**recorded_routes(), compare_key(): synthetic}, "ahead"),
                 (TAG, {**recorded_routes(), compare_key(): json_response(404, {"message": "Not Found"})}, None))
        for sha, routes, state in cases:
            with self.subTest(sha=sha, state=state):
                rows, _ = verify(f"lycheeverse/lychee@{sha[:12]}:{MOD_RS}:L23-L24", routes)
                self.assertEqual((rows[0]["status"], rows[0]["sha"], rows[0]["compare_status"]),
                                 ("not-on-default-branch:" + state if state in ("behind", "diverged")
                                  else "not-on-default-branch", sha, state))


class UnavailableTests(unittest.TestCase):
    TRANSIENT = (
        ("timeout", TimeoutError("timed out"), None),
        ("connection", urllib.error.URLError(ConnectionRefusedError(111, "refused")), None),
        ("429", json_response(429, {"message": "Too Many Requests"}), 429),
        ("503", V.Response(503, {}, b"Service Unavailable"), 503),
        ("primary rate limit", json_response(403, {"message": "API rate limit exceeded"},
                                             {"x-ratelimit-remaining": "0"}), 403),
        ("secondary rate limit", json_response(403, {"message": "You have exceeded a secondary rate limit."}), 403),
        ("retry-after", json_response(403, {"message": "Forbidden"}, {"retry-after": "60"}), 403),
        ("token refused", json_response(401, {"message": "Bad credentials"}), 401),
    )

    def test_timeout_429_503_and_rate_limits_are_unavailable_not_failures(self):
        steps = (route("commit-sha-12"), route("git-commit"), contents_key(MOD_RS), route("repository"), compare_key())
        for name, outcome, code in self.TRANSIENT:
            for step in steps:
                with self.subTest(response=name, step=step[0]):
                    rows, _ = verify(AT_FORM, {**recorded_routes(), step: outcome})
                    self.assertEqual((rows[0]["status"], rows[0]["http_status"]), (V.UNAVAILABLE, code))
                    self.assertNotIn(rows[0]["status"], V.FAILURES)

    def test_a_plain_403_is_a_failure_not_unavailable(self):
        forbidden = json_response(403, {"message": "Repository access blocked"})
        rows, _ = verify(AT_FORM, {**recorded_routes(), route("commit-sha-12"): forbidden})
        self.assertEqual((rows[0]["status"], rows[0]["http_status"]), ("commit-not-found", 403))
        rows, _ = verify(AT_FORM, {**recorded_routes(), contents_key(MOD_RS): forbidden})
        self.assertEqual(rows[0]["status"], "path-not-found")

    def test_transport_reasons_name_the_failure_and_nothing_else(self):
        self.assertEqual(V.transport_reason(TimeoutError()), "timed out")
        self.assertEqual(V.transport_reason(urllib.error.URLError(TimeoutError())), "timed out")
        self.assertEqual(V.transport_reason(urllib.error.URLError(ConnectionRefusedError())),
                         "connection error (ConnectionRefusedError)")


class ExitCodeTests(unittest.TestCase):
    def run_body(self, entries, routes, mode, environment=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "body.md"
            path.write_text("### SOTA sources\n\n" + "".join(f"- {entry}\n" for entry in entries), encoding="utf-8")
            return run_main(["--body-file", str(path), "--mode", mode], routes, environment)

    def test_enforce_exits_1_on_a_failure_and_3_when_only_unavailable(self):
        unavailable = {**recorded_routes(), compare_key(): V.Response(503, {}, b"")}
        bad_range = f"lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L900"
        self.assertEqual(self.run_body([AT_FORM, bad_range], recorded_routes(), "enforce")[0], 1)
        self.assertEqual(self.run_body([AT_FORM], unavailable, "enforce")[0], 3)
        self.assertEqual(self.run_body([AT_FORM, f"lycheeverse/lychee@{TAG[:8]}:{MOD_RS}:L1"], unavailable,
                                       "enforce")[0], 1)

    def test_enforce_exits_0_when_all_is_ok_and_report_always_exits_0(self):
        unchecked = "[reference] https://docs.github.com/en/rest/repos/contents"
        self.assertEqual(self.run_body([AT_FORM, unchecked], recorded_routes(), "enforce")[0], 0)
        for entries, routes in (([AT_FORM, f"lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L900"], recorded_routes()),
                                ([AT_FORM], {**recorded_routes(), compare_key(): V.Response(503, {}, b"")})):
            with self.subTest(entries=entries):
                self.assertEqual(self.run_body(entries, routes, "report")[0], 0)

    def test_a_pull_request_description_is_fetched_and_its_errors_exit_by_mode(self):
        pulls = ("/repos/o/r/pulls/7", V.JSON_MEDIA)
        code, out, _, fake = run_main(["--repo", "o/r", "--pr", "7", "--mode", "enforce"],
                                      {**recorded_routes(), pulls: json_response(200, {"body": "### SOTA sources\n- "
                                                                                      + AT_FORM + "\n"})})
        self.assertEqual((code, json.loads(out)["counts"], fake.calls[0][0]), (0, {"ok": 1}, pulls))
        for response, enforce, reason in ((json_response(200, {"body": None}), 0, None),
                                          (json_response(404, {"message": "Not Found"}), 1, "HTTP 404"),
                                          (V.Response(502, {}, b""), 3, "HTTP 502")):
            for mode, expected in (("enforce", enforce), ("report", 0)):
                with self.subTest(status=response.status, mode=mode):
                    code, out, err, _ = run_main(["--repo", "o/r", "--pr", "7", "--mode", mode], {pulls: response})
                    self.assertEqual(code, expected)
                    if reason:
                        self.assertIn(reason, json.loads(out)["error"])
                        self.assertIn(reason, err)


class OutputTests(unittest.TestCase):
    def test_the_report_and_the_summary_carry_every_row_and_never_the_token(self):
        bad = f"[adopt] lycheeverse/lychee@{TAG[:12]}:{MOD_RS}:L900"
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "body.md").write_text(f"### SOTA sources\n- {AT_FORM}\n- {bad}\n- plain | <b>text</b>\n",
                                            encoding="utf-8")
            (folder / "step.md").write_text("earlier step\n", encoding="utf-8")
            code, out, err, fake = run_main(
                ["--body-file", str(folder / "body.md"), "--report", str(folder / "report.json"),
                 "--summary", str(folder / "summary.md")], recorded_routes(),
                {"GITHUB_TOKEN": SENTINEL, "GITHUB_STEP_SUMMARY": str(folder / "step.md")})
            written = {name: (folder / name).read_text(encoding="utf-8")
                       for name in ("report.json", "summary.md", "step.md")}
        self.assertEqual((code, out), (0, ""))
        report = json.loads(written["report.json"])
        self.assertEqual(report["counts"], {"line-range-out-of-bounds": 1, "not-checked": 1, "ok": 1})
        self.assertEqual(report["roles"], {"mechanism": 1, "adopt": 1, "unknown": 1})
        self.assertEqual(set(report["rows"][0]), {
            "entry", "role", "role_ref", "citation", "repo", "path", "lines", "ref", "sha", "status", "reason",
            "http_status", "notes", "line_count", "blob_sha", "default_branch", "default_branch_sha", "compare_status"})
        self.assertEqual(report["rows"][0]["lines"], [23, 24])
        self.assertTrue(written["step.md"].startswith("earlier step\n## SOTA sources: code citations"))
        self.assertEqual(written["step.md"], "earlier step\n" + written["summary.md"])
        # A table cell escapes the pipe; the entry's own text stays inside a code span, where HTML is literal.
        self.assertIn("| unknown | `plain \\| <b>text</b>` | not-checked | not checked in phase A: no code citation |",
                      written["summary.md"])
        for header in (headers for _, headers, _ in fake.calls):
            self.assertEqual(header["Authorization"], f"Bearer {SENTINEL}")
            self.assertEqual(header["X-GitHub-Api-Version"], V.API_VERSION)
        for text in (out, err, *written.values()):
            self.assertNotIn(SENTINEL, text)

    def test_a_body_file_of_dash_is_read_from_stdin_and_an_unreadable_one_exits_2(self):
        with mock.patch.object(sys, "stdin", io.StringIO(f"### SOTA sources\n- {AT_FORM}\n")):
            code, out, _, _ = run_main(["--body-file", "-"], recorded_routes())
        self.assertEqual((code, json.loads(out)["counts"]), (0, {"ok": 1}))
        code, out, err, _ = run_main(["--body-file", str(ROOT / "no-such-body.md")])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("cannot read", err)

    def test_no_token_sends_no_authorization_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "body.md"
            path.write_text(f"### SOTA sources\n- {AT_FORM}\n", encoding="utf-8")
            code, _, _, fake = run_main(["--body-file", str(path)], recorded_routes())
        self.assertEqual(code, 0)
        self.assertTrue(fake.calls)
        self.assertFalse(any("Authorization" in headers for _, headers, _ in fake.calls))


class FakeOpener:
    def __init__(self, outcome):
        self.outcome, self.requests = outcome, []

    def open(self, request, timeout=None):
        self.requests.append((request, timeout))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class FakeHTTPResponse(io.BytesIO):
    def __init__(self, status, headers, body):
        super().__init__(body)
        self.status, self.headers, self.reads = status, headers, []

    def read(self, size=-1):
        self.reads.append(size)
        return super().read(size)


class FetcherTests(unittest.TestCase):
    URL = V.API + "/repos/o/r/commits/" + TAG

    def test_the_token_is_an_unredirected_header_that_no_redirect_carries(self):
        opener = FakeOpener(FakeHTTPResponse(200, {"Content-Type": V.SHA_MEDIA}, TAG.encode()))
        response = V.urllib_fetch(self.URL, {"Accept": V.SHA_MEDIA, "Authorization": f"Bearer {SENTINEL}"}, 7, 100,
                                  opener)
        self.assertEqual((response.status, response.body, response.headers), (200, TAG.encode(),
                                                                             {"content-type": V.SHA_MEDIA}))
        request, timeout = opener.requests[0]
        self.assertEqual((request.get_method(), timeout), ("GET", 7))
        self.assertEqual(request.unredirected_hdrs, {"Authorization": f"Bearer {SENTINEL}"})
        self.assertNotIn("Authorization", request.headers)
        redirected = urllib.request.HTTPRedirectHandler().redirect_request(
            request, None, 302, "Found", {}, "https://elsewhere.example/x")
        self.assertFalse(redirected.has_header("Authorization"))
        self.assertEqual(redirected.get_header("Accept"), V.SHA_MEDIA)

    def test_an_http_error_is_a_response_with_its_status_and_body(self):
        error = urllib.error.HTTPError(self.URL, 422, "Unprocessable", {"Content-Type": "application/json"},
                                       io.BytesIO(b'{"message":"No commit found for SHA: x"}'))
        response = V.urllib_fetch(self.URL, {"Accept": V.SHA_MEDIA}, 7, 100, FakeOpener(error))
        self.assertEqual((response.status, response.headers["content-type"], V.api_message(response)),
                         (422, "application/json", "No commit found for SHA: x"))

    def test_a_body_over_the_limit_is_oversize_and_not_read_past_it(self):
        declared = FakeHTTPResponse(200, {"Content-Length": "101"}, b"x" * 101)
        response = V.urllib_fetch(self.URL, {}, 7, 100, FakeOpener(declared))
        self.assertEqual((response.oversize, response.body, declared.reads), (True, b"", []))
        undeclared = FakeHTTPResponse(200, {}, b"x" * 150)
        response = V.urllib_fetch(self.URL, {}, 7, 100, FakeOpener(undeclared))
        self.assertEqual((response.oversize, len(response.body), undeclared.reads), (True, 100, [101]))

    def test_a_transport_failure_reaches_the_client_as_unreachable(self):
        for error, reason in ((TimeoutError("timed out"), "timed out"),
                              (urllib.error.URLError(ConnectionResetError()), "connection error (ConnectionResetError)")):
            with self.subTest(reason=reason):
                github = V.GitHub(fetch=lambda url, headers, timeout, limit, error=error: V.urllib_fetch(
                    url, headers, timeout, limit, FakeOpener(error)))
                self.assertEqual(github.get("/repos/o/r"), V.Unreachable(reason))


class SmokeTests(unittest.TestCase):
    def test_the_smoke_citations_pass_and_fail_as_expected_on_the_recorded_responses(self):
        self.assertIn(f"/blob/{TAG}/{MOD_RS}#L23-L24", V.SMOKE[0][0])
        self.assertIn(f"@{TAG[:12]}:{MOD_RS}:L{LINES}-L{LINES + 1}", V.SMOKE[1][0])
        code, out, _, _ = run_main(["--smoke"], recorded_routes())
        report = json.loads(out)
        self.assertEqual((code, report["mode"], [row["status"] for row in report["rows"]]),
                         (0, "smoke", ["ok", "line-range-out-of-bounds"]))
        code, out, _, _ = run_main(["--smoke"], {**recorded_routes(), compare_key(): V.Response(503, {}, b"")})
        self.assertEqual(code, 3)


class RuleCoverageTests(unittest.TestCase):
    def test_every_rule_has_a_failing_and_a_passing_fixture(self):
        names = [rule for rule, _, _ in RULES]
        for status in sorted(V.FAILURES | {V.UNAVAILABLE}):
            self.assertIn(status, names)
        for rule, failing, passing in RULES:
            for test in (failing, passing):
                with self.subTest(rule=rule, test=test):
                    owner, method = test.split(".")
                    self.assertTrue(callable(getattr(globals()[owner], method, None)), test)


if __name__ == "__main__":
    unittest.main()
