#!/usr/bin/env python3
"""Verify the code citations in a pull request's "SOTA sources" section through GitHub REST.

W1b phase A, report-only. The checker reads the section the required sota-sources check reads, finds each entry's code
citations and checks every one against GitHub REST at its pinned commit, then writes a JSON report and a Markdown
summary. Packages, documents, upstream health and SWHIDs come in later phases: an entry without a code citation is
listed as "not checked in phase A".

    python3 tools/sota-sources/verify_sources.py --body-file pr-body.md [--mode report|enforce]
    python3 tools/sota-sources/verify_sources.py --repo OWNER/NAME --pr N [--report out.json] [--summary out.md]
    python3 tools/sota-sources/verify_sources.py --smoke    # two live lychee citations: run locally, never in CI

Grammar. The section is found exactly as pr-metadata.yml's sota-sources job finds it (SOTA_SECTION). Each list item,
or each paragraph outside a list, is an entry. An entry may start with a role tag, [mechanism], [adopt], [reference],
[trial:<id>] or [exception:<record>]; an untagged entry has the role "unknown", which is reported and never failed in
phase A. A code citation takes one of two forms, modelled on SWHID (ISO/IEC 18670:2025: an anchor revision, a path and
a line range):

    https://github.com/OWNER/REPO/blob/REF/PATH#Lx    or #Lx-Ly   (?plain=1 and Cn column suffixes are accepted)
    OWNER/REPO@REF:PATH:Lx                            or :Lx-Ly

SHA policy. A ref of 12 to 40 hex characters is resolved with GET /repos/{o}/{r}/commits/{ref} (the
application/vnd.github.sha media type returns only the SHA), and the SHA it returns must start with the ref, so a
branch named like hex is refused as "unpinned"; the full SHA is recorded. A shorter hex ref is "short-sha" and any
other ref, a branch or a tag, is "unpinned": GitHub's permalinks accept all of these, so the checker refuses them
itself. The 12-character floor is the Linux kernel's rule for a Fixes: tag
(torvalds/linux@a5ebb76233b79db01e82e061173cb73c6d2b5c6b:Documentation/process/submitting-patches.rst:L145-L147),
and checkpatch's UNKNOWN_COMMIT_ID warning refuses a cited commit it cannot find
(torvalds/linux@a5ebb76233b79db01e82e061173cb73c6d2b5c6b:scripts/checkpatch.pl:L3584-L3593).

Checks, in order; the first that fails sets the row's status:
  1. GET /repos/{o}/{r}/git/commits/{sha}                                     else commit-not-found
  2. GET /repos/{o}/{r}/contents/{path}?ref={sha}, raw media type             else path-not-found
     The JSON media type returns no content above 1 MB, and the endpoint serves nothing above 100 MB. A directory
     comes back as application/json: path-is-directory. A body over 100 MiB, or a too_large refusal:
     unverifiable-size.
  3. 1 <= x <= y <= the file's line count                                     else line-range-out-of-bounds
  4. GET /repos/{o}/{r}/compare/{sha}...{default branch}?per_page=1 returns status ahead or identical with
     merge_base_commit.sha equal to the cited SHA                             else not-on-default-branch
     compare and git/commits both accept a SHA from a fork in the same repository network, so this is the check
     that puts the commit on the upstream's own history.
A timeout, a connection error, a 5xx, a rate-limited 403, a 429 or a rejected token is "unavailable", with the HTTP
code when there was one. It is never a failure status, and no failure is reported as "unavailable". lychee cannot do
the line check: it deletes GitHub #L fragments before the request
(lycheeverse/lychee@2bba271688c1abb1503097a064e6c3bc1d1b6a9b:lychee-lib/src/quirks/mod.rs:L23-L24).

Observed on api.github.com on 2026-10-11 (UTC) and relied on: a raw contents response for a file is
application/vnd.github.raw+json, with an ETag equal to the path's git blob SHA; a directory comes back as
application/json; for a symlink to a file the body is the target's content while the ETag stays the link's own blob
SHA, so that mismatch is recorded as a note, never a status. Untested boundaries: a symlink to a directory returned
the link text as a one-line file, which one raw request cannot tell apart from a file; no file over 100 MB was
observed, so both unverifiable-size signals follow the documentation only. Measured limit of check 4: a release
commit on a maintenance branch is not on the default branch (CPython's v3.12.3 commit compares "diverged" with main),
so citing such a release fails as not-on-default-branch.

Output. A JSON report (stdout, or --report) with one row per citation and one per unchecked entry, and a Markdown
summary appended to $GITHUB_STEP_SUMMARY when it is set (and written to --summary). --mode report always exits 0.
--mode enforce exits 1 on any failure status, 3 when nothing failed but something is unavailable, and 0 otherwise.
A missing or empty section is reported (section.present false) and exits 0, because the required sota-sources job
owns presence. GITHUB_TOKEN, when set, is sent to api.github.com as a bearer token, never across a redirect, and is
never printed or written.
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"
# docs.github.com/en/rest/about-the-rest-api/api-versions: requests without the header get 2022-11-28. None of
# 2026-03-10's breaking changes touches a field read here (docs.github.com/en/rest/about-the-rest-api/breaking-changes).
API_VERSION = "2026-03-10"
USER_AGENT = "native-agent-stack tools/sota-sources/verify_sources.py"
TIMEOUT = 30.0
SHA_MEDIA = "application/vnd.github.sha"
RAW_MEDIA = "application/vnd.github.raw+json"
JSON_MEDIA = "application/vnd.github+json"
# "Greater than 100 MB: This endpoint is not supported" (docs.github.com/en/rest/repos/contents, "Get repository
# content"); GitHub refuses pushes of files over 100 MiB, so a body past this cap is never served whole.
MAX_CONTENT_BYTES = 100 * 1024 * 1024
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_ERROR_BYTES = 64 * 1024

FAILURES = frozenset({"short-sha", "unpinned", "commit-not-found", "path-not-found", "path-is-directory",
                      "unverifiable-size", "line-range-out-of-bounds", "not-on-default-branch"})
UNAVAILABLE = "unavailable"
NOT_CHECKED = "not-checked"
ROLES = ("mechanism", "adopt", "reference", "trial", "exception", "unknown")

# pr-metadata.yml's sota-sources job (sota-sources-gate.yml runs it byte for byte), as
# blueprints/runtime-workers/openhands/resolver.py:456-471 ports it from JavaScript. Copied rather than imported:
# importing resolver.py loads its four sibling modules. Line breaks are made "\n" first, because JavaScript's
# multiline ^ and $ also break at \r, U+2028 and U+2029; JS_TRIM is String.prototype.trim's set (WhiteSpace plus
# LineTerminator). tests/test_verify_sources.py runs this and the workflow's own script on the same bodies.
SOTA_SECTION = re.compile(r"^#{2,3}[ \t]+SOTA sources[ \t]*$([\s\S]*?)(?=^#{2,3}[ \t]|(?![\s\S]))", re.M)
HTML_COMMENT = re.compile(r"<!--[\s\S]*?-->")
JS_LINE_BREAKS = re.compile("\r\n|[\r  ]")
JS_TRIM = ("\t\n\v\f\r              "
           "    　﻿")

LIST_ITEM = re.compile(r"[ \t]*(?:[-*+]|\d{1,9}[.)])(?:[ \t]+|$)")
ROLE_TAG = re.compile(r"\[(?:(mechanism|adopt|reference)|(trial|exception):([^\]\s]+))\](?![(\[])")
BLOB_URL = re.compile(
    r"https?://(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9-]+)/(?P<repo>[A-Za-z0-9._-]+)/blob/"
    r"(?P<ref>[^/\s?#]+)/(?P<path>[^\s?#<>()\[\]`'\"]+)(?:\?[^\s#<>()\[\]`'\"]*)?"
    r"#L(?P<start>\d+)(?:C\d+)?(?:-L?(?P<end>\d+)(?:C\d+)?)?(?![\w-])")
AT_REF = re.compile(
    r"(?<![\w./@-])(?P<owner>[A-Za-z0-9-]+)/(?P<repo>[A-Za-z0-9._-]+)@(?P<ref>[^\s:@<>()\[\]`'\"]+)"
    r":(?P<path>[^\s:<>()\[\]`'\"]+):L(?P<start>\d+)(?:-L?(?P<end>\d+))?(?![\w-])")
ANY_BLOB_URL = re.compile(r"https?://(?:www\.)?github\.com/[^/\s]+/[^/\s]+/blob/")
ANY_URL = re.compile(r"https?://")
HEX = re.compile(r"[0-9A-Fa-f]+")
FULL_SHA = re.compile(r"[0-9a-f]{40}")
REPO_ARGUMENT = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+")

# The smoke's two public citations (the W1b primary-source review): lychee's line-fragment quirk at the
# lychee-v0.24.2 commit, and a range that straddles that file's last line (it has 318 lines).
SMOKE = (
    ("[mechanism] https://github.com/lycheeverse/lychee/blob/2bba271688c1abb1503097a064e6c3bc1d1b6a9b/"
     "lychee-lib/src/quirks/mod.rs#L23-L24", "ok"),
    ("[mechanism] lycheeverse/lychee@2bba271688c1:lychee-lib/src/quirks/mod.rs:L318-L319", "line-range-out-of-bounds"),
)


def sota_section_content(body):
    """The required check's view of a PR body: the first "SOTA sources" section, comments removed.

    An empty result fails the required sota-sources check.
    """
    found = SOTA_SECTION.search(JS_LINE_BREAKS.sub("\n", body or ""))
    return HTML_COMMENT.sub("", found.group(1)).strip(JS_TRIM) if found else ""


@dataclasses.dataclass
class Entry:
    text: str
    role: str
    role_ref: str | None = None


@dataclasses.dataclass
class Citation:
    text: str
    owner: str
    repo: str
    ref: str
    path: str
    start: int
    end: int


def parse_entries(content):
    """Entries of a section: each list item, or each paragraph outside a list, with its role tag."""
    paragraphs, current = [], None
    for line in content.split("\n"):
        if not line.strip(JS_TRIM):
            current = None
            continue
        marker = LIST_ITEM.match(line)
        if marker or current is None:
            current = [line[marker.end():] if marker else line]
            paragraphs.append(current)
        else:
            current.append(line)
    entries = []
    for parts in paragraphs:
        text = " ".join(part.strip(JS_TRIM) for part in parts).strip(JS_TRIM)
        if not text:
            continue
        tag = ROLE_TAG.match(text)
        if tag is None:
            entries.append(Entry(text, "unknown"))
        elif tag.group(1):
            entries.append(Entry(text, tag.group(1)))
        else:
            entries.append(Entry(text, tag.group(2), tag.group(3)))
    return entries


def find_citations(text):
    """The entry's code citations in the order they appear, each (repository, ref, path, lines) once."""
    found = []
    for match in BLOB_URL.finditer(text):
        found.append((match.start(), match, urllib.parse.unquote(match.group("path"))))
    for match in AT_REF.finditer(text):
        found.append((match.start(), match, match.group("path")))
    citations, seen = [], set()
    for _, match, path in sorted(found, key=lambda item: item[0]):
        start = int(match.group("start"))
        end = int(match.group("end")) if match.group("end") else start
        key = (match.group("owner").lower(), match.group("repo").lower(), match.group("ref"), path, start, end)
        if key not in seen:
            seen.add(key)
            citations.append(Citation(match.group(0), match.group("owner"), match.group("repo"), match.group("ref"),
                                      path, start, end))
    return citations


def classify_ref(ref):
    """(status, reason) for a ref the SHA policy refuses without a request, else (None, None)."""
    if not HEX.fullmatch(ref):
        return "unpinned", f"ref {ref!r} is a branch or tag name; cite a commit SHA of at least 12 hex characters"
    if len(ref) < 12:
        return "short-sha", f"{len(ref)} hex characters; cite at least 12 (the kernel's Fixes: rule)"
    if len(ref) > 40:
        return "unpinned", f"{len(ref)} hex characters is no SHA-1: a branch or tag name"
    return None, None


@dataclasses.dataclass
class Response:
    status: int
    headers: dict
    body: bytes = b""
    oversize: bool = False


@dataclasses.dataclass
class Unreachable:
    """No HTTP response: a timeout or a connection error."""
    reason: str


def urllib_fetch(url, headers, timeout, limit, opener=None):
    """GET url and return a Response; a transport failure raises OSError or http.client.HTTPException.

    The token goes in an unredirected header: urllib's redirect_request copies req.headers, never
    unredirected_hdrs, so a redirect cannot carry it to another host
    (python/cpython@f6650f9ad73359051f3e558c2431a109bc016664:Lib/urllib/request.py:L401-L403 and L675-L679).
    """
    public = {name: value for name, value in headers.items() if name.lower() != "authorization"}
    request = urllib.request.Request(url, headers=public, method="GET")
    for name, value in headers.items():
        if name.lower() == "authorization":
            request.add_unredirected_header("Authorization", value)
    opener = opener or urllib.request.build_opener()
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        try:
            body = error.read(MAX_ERROR_BYTES) if error.fp else b""
        finally:
            error.close()
        return Response(error.code, lower_headers(error.headers), body)
    with response:
        found = lower_headers(response.headers)
        length = found.get("content-length", "")
        if length.isdigit() and int(length) > limit:
            return Response(response.status, found, b"", oversize=True)
        body = response.read(limit + 1)
        return Response(response.status, found, body[:limit], oversize=len(body) > limit)


def lower_headers(message):
    return {str(name).lower(): str(value) for name, value in (message.items() if message else ())}


class GitHub:
    """GitHub REST GETs through an injectable fetcher, each URL and media type fetched once per run."""

    def __init__(self, fetch=None, token=None, timeout=TIMEOUT):
        self.fetch = fetch or urllib_fetch
        self.token = token
        self.timeout = timeout
        self.cache = {}

    @property
    def requests(self):
        return len(self.cache)

    def get(self, path, accept=JSON_MEDIA, limit=MAX_JSON_BYTES):
        key = (path, accept)
        if key not in self.cache:
            headers = {"Accept": accept, "X-GitHub-Api-Version": API_VERSION, "User-Agent": USER_AGENT}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            try:
                self.cache[key] = self.fetch(API + path, headers, self.timeout, limit)
            except (OSError, http.client.HTTPException) as error:
                self.cache[key] = Unreachable(transport_reason(error))
        return self.cache[key]


def transport_reason(error):
    reason = getattr(error, "reason", None)
    if isinstance(error, TimeoutError) or isinstance(reason, TimeoutError):
        return "timed out"
    return f"connection error ({type(reason if isinstance(reason, BaseException) else error).__name__})"


def json_body(response):
    try:
        return json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def api_message(response):
    data = json_body(response)
    message = data.get("message") if isinstance(data, dict) else None
    return " ".join(str(message).split())[:200] if message else ""


def transient(response):
    """Why the response is a transient failure (status "unavailable"), or None.

    Rate limits: a 403 or 429 with x-ratelimit-remaining 0 (primary), or with a retry-after header or a message
    naming the rate limit (secondary); docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api,
    "Exceeding the rate limit". A 401 means this run's token was refused, which says nothing about the citation.
    """
    if isinstance(response, Unreachable):
        return response.reason
    if response.status >= 500:
        return f"HTTP {response.status}"
    if response.status == 429:
        return "HTTP 429 (rate limited)"
    if response.status == 403 and (response.headers.get("x-ratelimit-remaining") == "0"
                                   or "retry-after" in response.headers
                                   or "rate limit" in api_message(response).lower()):
        return "HTTP 403 (rate limited)"
    if response.status == 401:
        return "HTTP 401 (the token was refused)"
    return None


def http_reason(response, what):
    message = api_message(response)
    return f"{what}: HTTP {response.status}" + (f" ({message})" if message else "")


def too_large(response):
    data = json_body(response)
    errors = data.get("errors") if isinstance(data, dict) else None
    return isinstance(errors, list) and any(isinstance(item, dict) and item.get("code") == "too_large"
                                            for item in errors)


def line_count(content):
    """Lines as a numbered file view counts them: a last line without a trailing newline still counts."""
    if not content:
        return 0
    return content.count(b"\n") + (0 if content.endswith(b"\n") else 1)


def git_blob_sha(content):
    return hashlib.sha1(b"blob %d\0" % len(content) + content, usedforsecurity=False).hexdigest()


def invalid_path(path):
    return not path or path.startswith("/") or any(part in ("", ".", "..") for part in path.split("/"))


def new_row(entry, citation=None):
    row = {"entry": entry.text, "role": entry.role, "role_ref": entry.role_ref, "citation": None, "repo": None,
           "path": None, "lines": None, "ref": None, "sha": None, "status": None, "reason": "", "http_status": None,
           "notes": [], "line_count": None, "blob_sha": None, "default_branch": None, "compare_status": None}
    if citation is not None:
        row.update(citation=citation.text, repo=f"{citation.owner}/{citation.repo}", path=citation.path,
                   lines=[citation.start, citation.end], ref=citation.ref)
    return row


def settle(row, status, reason, response=None):
    row["status"], row["reason"] = status, reason
    if isinstance(response, Response):
        row["http_status"] = response.status
    return row


def verify_citation(row, citation, github):
    """Run the SHA policy and the four checks in order; the first failure settles the row."""
    status, reason = classify_ref(citation.ref)
    if status:
        return settle(row, status, reason)
    if citation.repo in (".", ".."):
        return settle(row, "commit-not-found", f"{citation.repo!r} is not a repository name")
    repository = f"/repos/{citation.owner}/{citation.repo}"
    ref = citation.ref.lower()
    step = f"commits/{ref}"
    resolved = github.get(f"{repository}/{step}", SHA_MEDIA)
    why = transient(resolved)
    if why:
        return settle(row, UNAVAILABLE, f"{step}: {why}", resolved)
    if resolved.status != 200:
        return settle(row, "commit-not-found", http_reason(resolved, step), resolved)
    sha = resolved.body.decode("ascii", "replace").strip().lower()
    if not FULL_SHA.fullmatch(sha):
        return settle(row, UNAVAILABLE, f"{step}: the response is not a SHA", resolved)
    if not sha.startswith(ref):
        return settle(row, "unpinned", f"{ref} resolves to {sha}, which does not start with it: "
                                       "a branch or tag named like hex")
    row["sha"] = sha

    step = f"git/commits/{sha[:12]}"
    commit = github.get(f"{repository}/git/commits/{sha}")
    why = transient(commit)
    if why:
        return settle(row, UNAVAILABLE, f"{step}: {why}", commit)
    if commit.status != 200:
        return settle(row, "commit-not-found", http_reason(commit, step), commit)

    if invalid_path(citation.path):
        return settle(row, "path-not-found", f"{citation.path!r} is not a file path in a repository")
    step = f"contents/{citation.path}"
    contents = github.get(f"{repository}/contents/{urllib.parse.quote(citation.path, safe='/')}?ref={sha}",
                          RAW_MEDIA, MAX_CONTENT_BYTES)
    why = transient(contents)
    if why:
        return settle(row, UNAVAILABLE, f"{step}: {why}", contents)
    if too_large(contents) or (contents.status == 200 and contents.oversize):
        return settle(row, "unverifiable-size", f"{step}: over the 100 MB the contents endpoint serves", contents)
    if contents.status != 200:
        return settle(row, "path-not-found", http_reason(contents, step), contents)
    media = contents.headers.get("content-type", "").split(";")[0].strip().lower()
    if media == "application/json":
        listing = json_body(contents)
        kind = listing.get("type") if isinstance(listing, dict) else None
        if isinstance(listing, list):
            return settle(row, "path-is-directory", f"{step}: a directory of {len(listing)} entries", contents)
        if kind in ("dir", "submodule"):
            return settle(row, "path-is-directory", f"{step}: a {kind}", contents)
        if kind == "symlink":
            return settle(row, "path-not-found", f"{step}: a symlink to {listing.get('target')!r}, not a file",
                          contents)
        return settle(row, "path-not-found", f"{step}: not a file", contents)
    count, blob = line_count(contents.body), git_blob_sha(contents.body)
    row["line_count"], row["blob_sha"] = count, blob
    etag = contents.headers.get("etag", "").removeprefix("W/").strip('"').lower()
    if FULL_SHA.fullmatch(etag) and etag != blob:
        row["notes"].append(f"the path's own blob is {etag}, not the content's: a symlink, checked against its "
                            "target's content")

    if not 1 <= citation.start <= citation.end <= count:
        return settle(row, "line-range-out-of-bounds",
                      f"L{citation.start}-L{citation.end} is not within the file's {count} lines")

    step = "repository"
    meta = github.get(repository)
    why = transient(meta)
    if why:
        return settle(row, UNAVAILABLE, f"{step}: {why}", meta)
    data = json_body(meta) if meta.status == 200 else None
    branch = data.get("default_branch") if isinstance(data, dict) else None
    if not isinstance(branch, str) or not branch:
        return settle(row, "not-on-default-branch", http_reason(meta, f"{step}: no default branch"), meta)
    row["default_branch"] = branch
    step = f"compare/{sha[:12]}...{branch}"
    compare = github.get(f"{repository}/compare/{sha}...{urllib.parse.quote(branch, safe='/')}?per_page=1")
    why = transient(compare)
    if why:
        return settle(row, UNAVAILABLE, f"{step}: {why}", compare)
    if compare.status != 200:
        return settle(row, "not-on-default-branch", http_reason(compare, step), compare)
    data = json_body(compare)
    data = data if isinstance(data, dict) else {}
    state = data.get("status")
    base = data.get("merge_base_commit")
    base = base.get("sha") if isinstance(base, dict) else None
    row["compare_status"] = state
    if state in ("ahead", "identical") and base == sha:
        return settle(row, "ok", f"on {branch} ({step}: {state})")
    return settle(row, "not-on-default-branch", f"{step}: status {state}, merge base {str(base)[:12]}", compare)


def unchecked_kind(text):
    if ANY_BLOB_URL.search(text):
        return "a GitHub blob URL without a #L line anchor"
    if "swh:1:" in text:
        return "a SWHID"
    if ANY_URL.search(text):
        return "a document or other URL"
    return "no code citation"


def verify_body(body, github):
    """(section content, rows): one row per code citation and one per entry without one."""
    content = sota_section_content(body)
    rows = []
    for entry in parse_entries(content):
        citations = find_citations(entry.text)
        if not citations:
            rows.append(settle(new_row(entry), NOT_CHECKED, f"not checked in phase A: {unchecked_kind(entry.text)}"))
        for citation in citations:
            rows.append(verify_citation(new_row(entry, citation), citation, github))
    return content, rows


def exit_code(rows, mode, error=None, error_transient=False):
    if mode == "report":
        return 0
    statuses = {row["status"] for row in rows}
    if statuses & FAILURES or (error and not error_transient):
        return 1
    if UNAVAILABLE in statuses or error:
        return 3
    return 0


def smoke_body():
    return "### SOTA sources\n\n" + "".join(f"- {entry}\n" for entry, _ in SMOKE)


def smoke_exit_code(rows):
    statuses = [row["status"] for row in rows]
    if statuses == [expected for _, expected in SMOKE]:
        return 0
    return 3 if UNAVAILABLE in statuses else 1


def pull_request_body(github, repo, number):
    """(body, error, error_is_transient) for the pull request's current description."""
    response = github.get(f"/repos/{repo}/pulls/{number}")
    why = transient(response)
    if why:
        return None, f"pulls/{number}: {why}", True
    if response.status != 200:
        return None, http_reason(response, f"pulls/{number}"), False
    data = json_body(response)
    if not isinstance(data, dict):
        return None, f"pulls/{number}: the response is not a pull request", True
    return data.get("body") or "", None, False


def cell(text):
    return (str(text).replace("\\", "\\\\").replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")
            .replace("\n", " "))


def code_cell(text, limit=160):
    text = " ".join(str(text).replace("`", "'").split())
    return "`" + (text if len(text) <= limit else text[:limit - 1] + "…").replace("|", "\\|") + "`"


def markdown(report):
    counts = report["counts"]
    checked = sum(n for status, n in counts.items() if status != NOT_CHECKED)
    tally = ", ".join(f"{n} {status}" for status, n in counts.items() if status != NOT_CHECKED) or "none"
    lines = ["## SOTA sources: code citations (W1b phase A)", "",
             f"Mode `{report['mode']}`, exit {report['exit_code']}. {checked} code citations ({tally}); "
             f"{counts.get(NOT_CHECKED, 0)} entries not checked in phase A. {report['requests']} GitHub REST requests.",
             ""]
    if report["error"]:
        lines += [f"The description could not be read: {cell(report['error'])}.", ""]
    elif not report["section"]["present"]:
        lines += ["No non-empty `SOTA sources` section; the required `sota-sources` check owns presence.", ""]
    if report["rows"]:
        lines += ["| Role | Citation | Status | Reason |", "| --- | --- | --- | --- |"]
        for row in report["rows"]:
            role = row["role"] + (f":{row['role_ref']}" if row["role_ref"] else "")
            reason = row["reason"] + "".join(f"; {note}" for note in row["notes"])
            lines.append(f"| {cell(role)} | {code_cell(row['citation'] or row['entry'])} | {cell(row['status'])} "
                         f"| {cell(reason)} |")
        lines.append("")
    return "\n".join(lines)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--body-file", type=Path, help="the PR description as a file, or - for stdin")
    source.add_argument("--pr", type=int, help="fetch the description of pull request N (with --repo)")
    source.add_argument("--smoke", action="store_true", help="check the two live smoke citations (network)")
    parser.add_argument("--repo", help="OWNER/NAME of the pull request")
    parser.add_argument("--mode", choices=("report", "enforce"), default="report")
    parser.add_argument("--report", type=Path, help="write the JSON report here instead of stdout")
    parser.add_argument("--summary", type=Path, help="also write the Markdown summary here")
    parser.add_argument("--timeout", type=float, default=TIMEOUT, help="seconds per socket operation")
    args = parser.parse_args(argv)
    if args.pr is not None and not (args.repo and REPO_ARGUMENT.fullmatch(args.repo)):
        parser.error("--pr needs --repo OWNER/NAME")
    return args


def main(argv=None, fetch=None):
    args = parse_args(argv)
    github = GitHub(fetch=fetch, token=os.environ.get("GITHUB_TOKEN") or None, timeout=args.timeout)
    error, error_transient = None, False
    if args.smoke:
        body, source = smoke_body(), {"kind": "smoke"}
    elif args.body_file is not None:
        source = {"kind": "body-file", "path": str(args.body_file)}
        try:
            body = sys.stdin.read() if str(args.body_file) == "-" else args.body_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as problem:
            print(f"verify_sources: cannot read {args.body_file}: {problem}", file=sys.stderr)
            return 2
    else:
        source = {"kind": "pull-request", "repo": args.repo, "pr": args.pr}
        body, error, error_transient = pull_request_body(github, args.repo, args.pr)
    content, rows = verify_body(body, github) if body is not None else ("", [])
    mode = "smoke" if args.smoke else args.mode
    code = smoke_exit_code(rows) if args.smoke else exit_code(rows, args.mode, error, error_transient)
    report = {
        "schema": "verify-sources/1",
        "phase": "A",
        "mode": mode,
        "source": source,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "api_version": API_VERSION,
        "requests": github.requests,
        "error": error,
        "section": {"present": bool(content), "characters": len(content)},
        "counts": dict(sorted(collections.Counter(row["status"] for row in rows).items())),
        "roles": {role: n for role in ROLES if (n := sum(row["role"] == role for row in rows))},
        "exit_code": code,
        "rows": rows,
    }
    text = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    summary = markdown(report)
    if args.summary:
        args.summary.write_text(summary, encoding="utf-8")
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(summary)
    if error:
        print(f"verify_sources: {error}", file=sys.stderr)
    print(f"verify_sources: {sum(row['status'] != NOT_CHECKED for row in rows)} code citations "
          f"{report['counts']}; mode {mode}, exit {code}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
