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
phase A. A code citation names a commit, path and line range, in one of two forms:

    https://github.com/OWNER/REPO/blob/REF/PATH#Lx    or #Lx-Ly   (?plain=1 and Cn column suffixes are accepted)
    OWNER/REPO@REF:PATH:Lx                            or :Lx-Ly

SHA policy. A ref of 12 to 40 hex characters is resolved with GET /repos/{o}/{r}/commits/{ref} (the
application/vnd.github.sha media type returns only the SHA). For abbreviated refs, exact git/ref/heads and
git/ref/tags lookups must establish that no same-named mutable ref exists; lookup failures are unavailable.
The resolved SHA must also start with the ref. A branch named like hex is "unpinned"; the full SHA is recorded.
An unresolved prefix is "sha-unresolved"
(indeterminate, cite the full SHA), distinct from a missing full SHA. A shorter hex ref containing a-f is "short-sha" and any
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
     unverifiable-size, before generic unavailable classification (including ordinary HTTP 403).
     Contents response codes: github/rest-api-description@58b1e0c00b39b9e46c24dc4a0ba6a2669c90e9c1:
     descriptions/api.github.com/api.github.com.json:L55991-L56059. No live over-limit refusal was observed.
  3. 1 <= x <= y <= the file's line count                                     else line-range-out-of-bounds
  4. Resolve and record the default branch tip SHA once per repository, then
     GET /repos/{o}/{r}/compare/{sha}...{tip SHA}?per_page=1&page=2 returns status ahead or identical with
     merge_base_commit.sha equal to the cited SHA                             else not-on-default-branch
     compare and git/commits both accept a SHA from a fork in the same repository network, so this is the check
     that puts the commit on the upstream's own history.
A compare limitation, incomplete/oversize JSON, a 400, a timeout, a connection error, a 5xx,
a 408 request timeout, an ordinary/rate-limited 403, a 429 or a rejected token is "unavailable", with the HTTP
code when there was one. A commit/content/compare 404 followed by a repository 404 is also unavailable:
the repository is not visible to this token (GitHub REST authentication, "Failed login limit"). lychee cannot do
the line check: it deletes GitHub #L fragments before the request
(lycheeverse/lychee@2bba271688c1abb1503097a064e6c3bc1d1b6a9b:lychee-lib/src/quirks/mod.rs:L23-L24).

Observed on api.github.com on 2026-10-11 (UTC) and relied on: a raw contents response for a file is
application/vnd.github.raw+json, with an ETag equal to the path's git blob SHA; a directory comes back as
application/json; for a symlink to a file the body is the target's content while the ETag stays the link's own blob
SHA, so that mismatch is recorded as a note, never a status. Untested boundaries: a symlink to a directory returned
the link text as a one-line file, which one raw request cannot tell apart from a file; no file over 100 MB was
observed, so both unverifiable-size signals follow the documentation only. Measured limit of check 4: a release
commit on a maintenance branch is not on the default branch (CPython's v3.12.3 commit compares "diverged" with main),
so citing such a release is counted separately as not-on-default-branch:diverged (or :behind). Release-tag heads
and the grammar that names a tag are deferred to phase B by the plan owner's ruling. SWHID anchor/path/lines
verification also remains deferred; phase A reports it explicitly as not-checked, never as a GitHub code citation.

Budgets: at most 64 recognized citation occurrences are checked per body (excess rows are not-checked), and at most
256 data rows plus one exact omission row are reported. Entry text and other row display fields retain at most
1024 characters each, with an ellipsis and note; spans refer to the original input. Omitted rows are indeterminate
and are not verified. At most 256 HTTP requests are sent per run, including redirect hops and PR retrieval.
The first rate limit stops all further requests;
remaining rows are unavailable. Raw contents are discarded after counting lines and computing the blob, so cached
files retain only those measurements and headers. The JSON report records the limits.

Output. A JSON report (stdout, or --report) with one row per recognized citation occurrence, one diagnostic per
unrecognized candidate (including repository/package pins), and one per entry with no candidate within the row
budget, followed by an exact omission count when needed, and a Markdown
summary appended to $GITHUB_STEP_SUMMARY when it is set (and written to --summary). --mode report always exits 0.
--mode enforce exits 1 on any failure status, 3 when nothing failed but something is unavailable, and 0 otherwise.
A missing or empty section is reported (section.present false) and exits 0, because the required sota-sources job
owns presence. GITHUB_TOKEN, when set, is sent to api.github.com as a bearer token; a redirect retains it only between
HTTPS api.github.com URLs without userinfo or a nonstandard port. It is
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
MAX_CITATIONS = 64
MAX_REQUESTS = 256
# Bounds on report data, separate from the HTTP/recognized-occurrence budget.
# At most MAX_ROWS data rows plus one exact omission row are serialized.
MAX_ROWS = 256
MAX_ENTRY_CHARS = 1024
MAX_ROW_FIELD_CHARS = 1024
# A raw file has at most one line per byte. Bound numeric tokens before int(): CPython's default conversion
# limit is 4300 digits, python/cpython@f6650f9ad73359051f3e558c2431a109bc016664:Include/internal/pycore_long.h:L29
# (_PY_LONG_DEFAULT_MAX_STR_DIGITS). Zero padding is removed before this local file-size bound is applied.
MAX_LINE_NUMBER = MAX_CONTENT_BYTES

FAILURES = frozenset({"short-sha", "unpinned", "commit-not-found", "path-not-found", "path-is-directory",
                      "unverifiable-size", "line-range-out-of-bounds", "not-on-default-branch",
                      "not-on-default-branch:diverged", "not-on-default-branch:behind"})
UNAVAILABLE = "unavailable"
SHA_UNRESOLVED = "sha-unresolved"
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

LIST_ITEM = re.compile(r"[ \t]*(?:[-*+]|[0-9]{1,9}[.)])(?:[ \t]+|$)")
ROLE_TAG = re.compile(r"\[(?:(mechanism|adopt|reference)|(trial|exception):([^\]\s]+))\](?![(\[])")
BLOB_URL = re.compile(
    r"(?i:https?://(?:www\.)?github\.com)/(?P<owner>[A-Za-z0-9-]+)/(?P<repo>[A-Za-z0-9._-]+)/blob/"
    r"(?P<ref>[^/\s?#]+)/(?P<path>[^\s?#<>\[\]`'\"]+)(?:\?[^\s#<>\[\]`'\"]*)?"
    r"#L(?P<start>[0-9]+)(?:C[0-9]+)?(?:-L?(?P<end>[0-9]+)(?:C[0-9]+)?)?(?![^\W_])")
AT_REF = re.compile(
    r"(?<![\w./@])(?P<owner>[A-Za-z0-9-]+)/(?P<repo>[A-Za-z0-9._-]+)@(?P<ref>[^\s:@<>()\[\]`'\"]+)"
    r":(?P<path>[^\s:<>\[\]`'\"]+):L(?P<start>[0-9]+)(?:-L?(?P<end>[0-9]+))?(?![^\W_])")
ANY_BLOB_URL = re.compile(r"https?://(?:www\.)?github\.com/[^/\s]+/[^/\s]+/blob/", re.I)
ANY_URL = re.compile(r"https?://", re.I)
HEX = re.compile(r"[0-9A-Fa-f]+")
FULL_SHA = re.compile(r"[0-9a-f]{40}")
REPO_ARGUMENT = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+")
CANDIDATE_START = re.compile(
    r"(?i:https?://(?:www\.)?github\.com)/[^/\s<>`'\"\[\]]+/[^/\s<>`'\"\[\]]+/blob/"
    r"|(?<![\w./@])[A-Za-z0-9-]+/[A-Za-z0-9._-]+@|swh:1:")
CANDIDATE_END = re.compile(r"[\s<>`'\"\[\]]")
GRAMMAR_CONTINUATION = re.compile(r"^(?:#|:L|:[0-9]|/|@|_+[^\W_]|-L|-[0-9]|[‐-―−~,]L?[0-9])")
REPOSITORY_PIN = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+@[^\s:<>`'\"\[\]]+")

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
    start: int | None
    end: int | None
    span: tuple | None = None
    parse_error: str | None = None


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


def bounded_line(token):
    token = token.lstrip("0") or "0"
    if len(token) > len(str(MAX_LINE_NUMBER)):
        return None
    value = int(token)
    return value if value <= MAX_LINE_NUMBER else None


def find_citations(text, deduplicate=True):
    """The entry's code citations in the order they appear, each (repository, ref, path, lines) once."""
    found = []
    urls = list(BLOB_URL.finditer(text))
    for match in urls:
        found.append((match.start(), match, urllib.parse.unquote(match.group("path"))))
    # A URL's path and fragment are atomic: an AT-shaped substring there must not consume a real neighbour.
    cursor = 0
    at_matches = []
    for url in urls:
        at_matches.extend(AT_REF.finditer(text, cursor, url.start()))
        cursor = url.end()
    at_matches.extend(AT_REF.finditer(text, cursor))
    for match in at_matches:
        found.append((match.start(), match, match.group("path")))
    citations, seen = [], set()
    for _, match, path in sorted(found, key=lambda item: item[0]):
        start = bounded_line(match.group("start"))
        end = bounded_line(match.group("end")) if match.group("end") else start
        key = (match.group("owner").lower(), match.group("repo").lower(), match.group("ref"), path, start, end)
        if not deduplicate or key not in seen:
            seen.add(key)
            citations.append(Citation(match.group(0), match.group("owner"), match.group("repo"), match.group("ref"),
                                      path, start, end, match.span(),
                                      "line number exceeds the supported file-size bound" if start is None or end is None else None))
    return citations


def citation_candidates(text):
    """Keep spans for all candidates; matching one citation must not swallow an unrecognized neighbour."""
    recognized = []
    for citation in find_citations(text, deduplicate=False):
        if not recognized or citation.span[0] >= recognized[-1].span[1]:
            recognized.append(citation)  # a complete URL/path is atomic; ignore nested lookalikes
    by_start = {citation.span[0]: citation for citation in recognized}
    starts = set(by_start)
    cursor = 0
    for citation in recognized:
        starts.update(match.start() for match in CANDIDATE_START.finditer(text, cursor, citation.span[0]))
        cursor = citation.span[1]
    starts.update(match.start() for match in CANDIDATE_START.finditer(text, cursor))
    starts = sorted(starts)
    found = []
    for index, start in enumerate(starts):
        delimiter = CANDIDATE_END.search(text, start)
        end = delimiter.start() if delimiter else len(text)
        if index + 1 < len(starts):
            end = min(end, starts[index + 1])
        candidate = text[start:end].rstrip(".,;)*_")
        citation = by_start.get(start)
        if citation is not None and GRAMMAR_CONTINUATION.match(text[citation.span[1]:end]):
            citation = None  # only syntax continuation invalidates an otherwise recognized citation
        if citation is not None:
            found.append((citation.span, citation, None))
        else:
            found.append(((start, start + len(candidate)), None, candidate))
    return found


def classify_ref(ref):
    """(status, reason) for a ref the SHA policy refuses without a request, else (None, None)."""
    if not HEX.fullmatch(ref):
        return "unpinned", f"ref {ref!r} is a branch or tag name; cite a commit SHA of at least 12 hex characters"
    if len(ref) < 12:
        if ref.isdecimal():
            return "unpinned", f"ref {ref!r} is a numeric branch or tag name; cite a commit SHA"
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
    content: dict | None = None
    json_data: object = None
    json_parsed: bool = False


@dataclasses.dataclass
class Unreachable:
    """No HTTP response: a timeout or a connection error."""
    reason: str


def api_origin(url):
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme == "https" and parsed.netloc.lower() in ("api.github.com", "api.github.com:443")


class APIRedirectHandler(urllib.request.HTTPRedirectHandler):
    """CPython's redirect policy plus same-API unredirected auth (request.py at f6650f9a:675-679)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and api_origin(req.full_url) and api_origin(newurl):
            auth = req.get_header("Authorization")
            if auth:
                redirected.add_unredirected_header("Authorization", auth)
        return redirected


class RequestCounter(urllib.request.BaseHandler):
    """Run before each HTTP request, including CPython's recursively opened redirects."""
    handler_order = 400

    def __init__(self, before_request):
        self.before_request = before_request

    def http_request(self, request):
        self.before_request()
        return request

    https_request = http_request


class RequestBudgetExceeded(OSError):
    pass


def urllib_fetch(url, headers, timeout, limit, opener=None, before_request=None):
    """GET url and return a Response; a transport failure raises OSError or http.client.HTTPException.

    The token goes in an unredirected header: urllib's redirect_request copies req.headers, never
    unredirected_hdrs; APIRedirectHandler restores it only for same-API HTTPS redirects
    (python/cpython@f6650f9ad73359051f3e558c2431a109bc016664:Lib/urllib/request.py:L401-L403 and L675-L679).
    """
    public = {name: value for name, value in headers.items() if name.lower() != "authorization"}
    request = urllib.request.Request(url, headers=public, method="GET")
    for name, value in headers.items():
        if name.lower() == "authorization":
            request.add_unredirected_header("Authorization", value)
    handlers = [APIRedirectHandler()]
    if before_request is not None:
        handlers.append(RequestCounter(before_request))
    opener = opener or urllib.request.build_opener(*handlers)
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
        self.fetch = fetch
        self.token = token.strip() if token else None
        self.timeout = timeout
        self.cache = {}
        self.repository_ids = {}
        self._requests = 0
        self.max_requests = MAX_REQUESTS
        self.stopped = None
        if self.token and (any(ord(char) < 32 or ord(char) == 127 or ord(char) > 255 for char in self.token)):
            self.stopped = "invalid authorization header configuration"

    @property
    def requests(self):
        return self._requests

    def before_request(self):
        if self.requests >= self.max_requests:
            self.stopped = f"over the per-run request cap ({self.max_requests})"
            raise RequestBudgetExceeded()
        self._requests += 1

    def cache_key(self, path, accept):
        parts = path.split("/", 4)
        if len(parts) >= 4 and parts[1] == "repos":
            repository = "/".join(parts[:4])
            identity = self.repository_ids.get(repository)
            if identity is not None:
                suffix = "/" + parts[4] if len(parts) == 5 else ""
                return f"/repositories/{identity}{suffix}", accept
        return path, accept

    def learn_repository_identity(self, path, response):
        """Use the API's numeric id/full_name; aliases returned by redirects/renames share cached state."""
        parts = path.split("/")
        if len(parts) != 4 or parts[1] != "repos" or response.status != 200:
            return
        data = json_body(response)
        identity = data.get("id") if isinstance(data, dict) else None
        if type(identity) is not int or not 0 < identity < 2 ** 63:
            return
        aliases = [path]
        full_name = data.get("full_name")
        if isinstance(full_name, str) and REPO_ARGUMENT.fullmatch(full_name):
            aliases.append("/repos/" + full_name.lower())
        for alias in aliases:
            self.repository_ids[alias] = identity
            for old_key, value in list(self.cache.items()):
                if old_key[0] == alias or old_key[0].startswith(alias + "/"):
                    new_key = self.cache_key(old_key[0], old_key[1])
                    self.cache.setdefault(new_key, value)
                    if old_key != new_key:
                        del self.cache[old_key]

    def get(self, path, accept=JSON_MEDIA, limit=MAX_JSON_BYTES):
        parts = path.split("/", 4)
        if len(parts) >= 4 and parts[1] == "repos":
            parts[2], parts[3] = parts[2].lower(), parts[3].lower()
            path = "/".join(parts)
        key = self.cache_key(path, accept)
        if self.stopped:
            return Unreachable(self.stopped)
        if key not in self.cache:
            headers = {"Accept": accept, "X-GitHub-Api-Version": API_VERSION, "User-Agent": USER_AGENT}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            try:
                if self.fetch is None:
                    response = urllib_fetch(API + path, headers, self.timeout, limit, before_request=self.before_request)
                else:
                    self.before_request()
                    response = self.fetch(API + path, headers, self.timeout, limit)
                why = transient(response)
                # GitHub authentication docs, Failed login limit: repeated invalid-auth requests can
                # temporarily reject all authentication. Stop on 401 as well as an identified rate limit.
                if isinstance(response, Response) and why and ("rate limited" in why or response.status == 401):
                    self.stopped = f"requests stopped after {why}"
                if isinstance(response, Response) and accept == RAW_MEDIA:
                    response = compact_contents(response)
                elif isinstance(response, Response) and accept == JSON_MEDIA and response.status == 200:
                    response = compact_json(response, path)
                    self.learn_repository_identity(path, response)
                    key = self.cache_key(path, accept)
                self.cache.setdefault(key, response)
            except RequestBudgetExceeded:
                self.cache[key] = Unreachable(self.stopped)
            except ValueError:
                # http.client at f6650f9a:1311-1314 can include a header value in its exception.
                self.cache[key] = Unreachable("invalid request header")
            except (OSError, http.client.HTTPException) as error:
                self.cache[key] = Unreachable(transport_reason(error))
        return self.cache[key]


def transport_reason(error):
    reason = getattr(error, "reason", None)
    if isinstance(error, TimeoutError) or isinstance(reason, TimeoutError):
        return "timed out"
    return f"connection error ({type(reason if isinstance(reason, BaseException) else error).__name__})"


def json_body(response):
    if response.json_parsed:
        return response.json_data
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
    if response.status == 403:
        return "HTTP 403 (permission or authentication unavailable)"
    if 300 <= response.status < 400:
        return f"HTTP {response.status} (redirect not completed)"
    if response.status == 400:
        return "HTTP 400 (request unavailable)"
    if response.status == 408:
        return "HTTP 408 (request timed out)"
    return None


def http_reason(response, what):
    message = api_message(response)
    return f"{what}: HTTP {response.status}" + (f" ({message})" if message else "")


def too_large(response):
    if not isinstance(response, Response) or response.status < 400:
        return False  # successful raw source JSON is never an API error envelope
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


def compact_contents(response):
    """Keep file measurements, never the up-to-100-MiB body; directory JSON becomes small metadata."""
    if response.status != 200 or response.oversize:
        return dataclasses.replace(response, body=response.body[:MAX_ERROR_BYTES])
    media = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if media == "application/json":
        data = json_body(response)
        if isinstance(data, list):
            info = {"kind": "dir", "entries": len(data)}
        elif isinstance(data, dict):
            info = {"kind": data.get("type"), "target": data.get("target")}
        else:
            info = {"kind": None}
    else:
        info = {"kind": "file", "lines": line_count(response.body), "blob": git_blob_sha(response.body)}
    return dataclasses.replace(response, body=b"", content=info)


def compact_json(response, path):
    """Drop commit messages/patches and unused metadata; all JSON consumers use json_body()."""
    data = json_body(response) if not response.oversize else None
    if not isinstance(data, dict):
        return dataclasses.replace(response, body=b"", json_data=None, json_parsed=True)

    def field(mapping, key, limit):
        value = mapping.get(key)
        return value if isinstance(value, str) and len(value) <= limit else None

    parts = path.split("/", 4)
    endpoint = parts[4] if len(parts) == 5 else ""
    if endpoint.startswith("compare/"):
        base = data.get("merge_base_commit")
        kept = {"status": field(data, "status", 16),
                "merge_base_commit": {"sha": field(base, "sha", 40) if isinstance(base, dict) else None}}
    elif endpoint.startswith("git/ref/"):
        kept = {"ref": field(data, "ref", 256)}
    elif endpoint.startswith("git/commits/"):
        kept = {"sha": field(data, "sha", 40)}
    elif endpoint.startswith("pulls/"):
        body = data.get("body")
        if "body" not in data or body is not None and not isinstance(body, str):
            return dataclasses.replace(response, body=b"", json_data=None, json_parsed=True)
        if isinstance(body, str) and len(body) > 65536:
            return dataclasses.replace(response, body=b"", json_data=None, json_parsed=True, oversize=True)
        kept = {"body": body}
    else:
        kept = {"default_branch": field(data, "default_branch", 4096)}
        if type(data.get("id")) is int and 0 < data["id"] < 2 ** 63:
            kept["id"] = data["id"]
        if isinstance(data.get("full_name"), str) and len(data["full_name"]) <= 512 and REPO_ARGUMENT.fullmatch(data["full_name"]):
            kept["full_name"] = data["full_name"]
    return dataclasses.replace(response, body=b"", json_data=kept, json_parsed=True)


def invalid_path(path):
    return not path or path.startswith("/") or any(part in ("", ".", "..") for part in path.split("/"))


def new_row(entry, citation=None):
    row = {"entry": entry.text, "role": entry.role, "role_ref": entry.role_ref, "citation": None, "repo": None,
           "path": None, "lines": None, "ref": None, "sha": None, "status": None, "reason": "", "http_status": None,
           "notes": [], "line_count": None, "blob_sha": None, "default_branch": None,
           "default_branch_sha": None, "compare_status": None, "candidate_span": None}
    if citation is not None:
        row.update(citation=citation.text, repo=f"{citation.owner}/{citation.repo}", path=citation.path,
                   lines=[citation.start, citation.end], ref=citation.ref,
                   candidate_span=list(citation.span) if citation.span is not None else None)
    return row


def settle(row, status, reason, response=None):
    row["status"], row["reason"] = status, reason
    if isinstance(response, Response):
        row["http_status"] = response.status
    return row


def repository_visibility(row, repository, github):
    """A resource 404 is definitive only after this run establishes repository visibility.

    GitHub REST troubleshooting, "404 Not Found for an existing resource": private resources are hidden as
    404 to avoid confirming their existence. Metadata is cached with the same repository identity as all checks.
    """
    meta = github.get(repository)
    why = transient(meta)
    if why:
        return settle(row, UNAVAILABLE, f"repository visibility: {why}", meta)
    if meta.status == 404:
        return settle(row, UNAVAILABLE, "repository not visible to this token", meta)
    if meta.status != 200 or not isinstance(json_body(meta), dict):
        return settle(row, UNAVAILABLE, "repository visibility could not be established", meta)
    return None


def verify_citation(row, citation, github):
    """Run the SHA policy and the four checks in order; the first failure settles the row."""
    status, reason = classify_ref(citation.ref)
    if status:
        return settle(row, status, reason)
    if citation.parse_error:
        return settle(row, "line-range-out-of-bounds", citation.parse_error)
    if citation.repo in (".", ".."):
        return settle(row, "commit-not-found", f"{citation.repo!r} is not a repository name")
    repository = f"/repos/{citation.owner.lower()}/{citation.repo.lower()}"
    ref = citation.ref.lower()
    if len(ref) < 40:
        # REST git/refs, API 2026-03-10: GET a reference is exact; absent heads and tags return 404.
        # A matching prefix alone is insufficient: a same-named mutable ref can point at that very SHA.
        for namespace, spelling in ((ns, spelling) for spelling in dict.fromkeys((citation.ref, ref)) for ns in ("heads", "tags")):
            name = f"refs/{namespace}/{spelling}"
            named = github.get(f"{repository}/git/ref/{namespace}/{spelling}")
            why = transient(named)
            if why:
                return settle(row, UNAVAILABLE, f"{name}: {why}", named)
            if named.status == 404:
                continue
            data = json_body(named) if named.status == 200 and not named.oversize else None
            if isinstance(data, dict) and data.get("ref") == name:
                return settle(row, "unpinned", f"{citation.ref} names a mutable {namespace} ref; cite the full SHA", named)
            return settle(row, UNAVAILABLE, f"{name}: could not rule out a mutable named ref", named)
    step = f"commits/{ref}"
    resolved = github.get(f"{repository}/{step}", SHA_MEDIA)
    why = transient(resolved)
    if why:
        return settle(row, UNAVAILABLE, f"{step}: {why}", resolved)
    if resolved.status != 200:
        if resolved.status == 404:
            hidden = repository_visibility(row, repository, github)
            if hidden:
                return hidden
        if resolved.status == 422 and len(ref) < 40:
            return settle(row, SHA_UNRESOLVED,
                          "not found or ambiguous in the repository network; cite the full SHA", resolved)
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
        if commit.status == 404:
            hidden = repository_visibility(row, repository, github)
            if hidden:
                return hidden
        return settle(row, "commit-not-found", http_reason(commit, step), commit)

    if invalid_path(citation.path):
        return settle(row, "path-not-found", f"{citation.path!r} is not a file path in a repository")
    step = f"contents/{citation.path}"
    contents = github.get(f"{repository}/contents/{urllib.parse.quote(citation.path, safe='/')}?ref={sha}",
                          RAW_MEDIA, MAX_CONTENT_BYTES)
    # Contents documents 403, not 422: github/rest-api-description@58b1e0c00b39b9e46c24dc4a0ba6a2669c90e9c1:
    # descriptions/api.github.com/api.github.com.json:L55991-L56059. An explicit size error has precedence
    # over generic forbidden; GitHub.get still stops the run if the same response identifies a rate limit.
    if too_large(contents) or (isinstance(contents, Response) and contents.status == 200 and contents.oversize):
        return settle(row, "unverifiable-size", f"{step}: over the 100 MB the contents endpoint serves", contents)
    why = transient(contents)
    if why:
        return settle(row, UNAVAILABLE, f"{step}: {why}", contents)
    if contents.status != 200:
        if contents.status == 404:
            hidden = repository_visibility(row, repository, github)
            if hidden:
                return hidden
        return settle(row, "path-not-found", http_reason(contents, step), contents)
    media = contents.headers.get("content-type", "").split(";")[0].strip().lower()
    if media == "application/json":
        listing = contents.content or {}
        kind = listing.get("kind")
        if kind in ("dir", "submodule"):
            return settle(row, "path-is-directory", f"{step}: a {kind}", contents)
        if kind == "symlink":
            return settle(row, "path-not-found", f"{step}: a symlink to {listing.get('target')!r}, not a file",
                          contents)
        return settle(row, "path-not-found", f"{step}: not a file", contents)
    count, blob = contents.content["lines"], contents.content["blob"]
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
        return settle(row, UNAVAILABLE, http_reason(meta, f"{step}: no default branch"), meta)
    row["default_branch"] = branch
    tip = github.get(f"{repository}/commits/{urllib.parse.quote(branch, safe='')}", SHA_MEDIA)
    why = transient(tip)
    if why:
        return settle(row, UNAVAILABLE, f"default branch tip: {why}", tip)
    tip_sha = tip.body.decode("ascii", "replace").strip().lower()
    if tip.status != 200 or tip.oversize or not FULL_SHA.fullmatch(tip_sha):
        return settle(row, UNAVAILABLE, "default branch tip could not be resolved", tip)
    row["default_branch_sha"] = tip_sha
    step = f"compare/{sha[:12]}...{branch}"
    # GitHub REST 2026-03-10, Compare two commits: changed files appear only on page 1.
    compare = github.get(f"{repository}/compare/{sha}...{tip_sha}?per_page=1&page=2")
    why = transient(compare)
    if why:
        return settle(row, UNAVAILABLE, f"{step}: {why}", compare)
    if compare.status != 200:
        if compare.status == 404:
            hidden = repository_visibility(row, repository, github)
            if hidden:
                return hidden
        status = "not-on-default-branch" if compare.status == 404 else UNAVAILABLE
        return settle(row, status, http_reason(compare, step), compare)
    data = json_body(compare)
    data = data if isinstance(data, dict) else {}
    state = data.get("status")
    base = data.get("merge_base_commit")
    base = base.get("sha") if isinstance(base, dict) else None
    row["compare_status"] = state
    if compare.oversize or state not in ("ahead", "identical", "behind", "diverged") or not isinstance(base, str) or not FULL_SHA.fullmatch(base):
        return settle(row, UNAVAILABLE, f"{step}: incomplete or oversize comparison", compare)
    if state in ("ahead", "identical") and base == sha:
        return settle(row, "ok", f"on {branch} ({step}: {state})")
    status = "not-on-default-branch:" + state if state in ("behind", "diverged") else "not-on-default-branch"
    return settle(row, status, f"{step}: status {state}, merge base {str(base)[:12]}", compare)


def unchecked_kind(text):
    if ANY_BLOB_URL.search(text):
        return "a GitHub blob URL without a #L line anchor"
    if "swh:1:" in text:
        return "a SWHID"
    if ANY_URL.search(text):
        return "a document or other URL"
    return "no code citation"


def bound_row_text(row):
    """Bound repeated display strings; spans and verification refer to the original input."""
    truncated = False
    for key, value in row.items():
        limit = MAX_ENTRY_CHARS if key == "entry" else MAX_ROW_FIELD_CHARS
        if isinstance(value, str) and len(value) > limit:
            row[key] = value[:limit - 1] + "…"
            truncated = True
    row["notes"] = [note[:MAX_ROW_FIELD_CHARS - 1] + "…" if len(note) > MAX_ROW_FIELD_CHARS else note
                    for note in row["notes"]]
    if truncated:
        row["notes"].append("display text truncated; spans refer to original input")
    return row


def verify_body(body, github):
    """(section content, rows): each recognized occurrence, each unrecognized candidate, and candidate-free entries.

    The citation budget counts recognized occurrences, including repetitions. The separate report budget
    counts every data row; excess rows are counted in one indeterminate omission row and never checked.
    """
    content = sota_section_content(body)
    rows = []
    checked = 0
    omitted = 0
    for entry in parse_entries(content):
        candidates = citation_candidates(entry.text)
        if not candidates:
            if len(rows) >= MAX_ROWS:
                omitted += 1
                continue
            rows.append(settle(new_row(entry), NOT_CHECKED, f"not checked in phase A: {unchecked_kind(entry.text)}"))
        for span, citation, candidate in candidates:
            if len(rows) >= MAX_ROWS:
                omitted += 1
                continue
            if citation is None:
                row = new_row(entry)
                row["citation"] = candidate
                row["candidate_span"] = list(span)
                kind = unchecked_kind(candidate)
                if REPOSITORY_PIN.fullmatch(candidate):
                    kind = "repository or package pin"
                elif "#L" in candidate or ("@" in candidate and not ANY_URL.search(candidate)):
                    kind = "unrecognized code citation (invalid or unsupported syntax)"
                rows.append(settle(row, NOT_CHECKED, f"not checked in phase A: {kind}"))
                continue
            row = new_row(entry, citation)
            if checked >= MAX_CITATIONS:
                rows.append(settle(row, NOT_CHECKED, f"over the per-body cap ({MAX_CITATIONS} citations)"))
            else:
                checked += 1
                rows.append(verify_citation(row, citation, github))
    if omitted:
        row = new_row(Entry("", "unknown"))
        row["omitted_rows"] = omitted
        rows.append(settle(row, UNAVAILABLE, f"report row limit ({MAX_ROWS} data rows): {omitted} rows omitted"))
    return content, [bound_row_text(row) for row in rows]


def exit_code(rows, mode, error=None, error_transient=False):
    if mode == "report":
        return 0
    statuses = {row["status"] for row in rows}
    if statuses & FAILURES or (error and not error_transient):
        return 1
    if statuses & {UNAVAILABLE, SHA_UNRESOLVED} or error:
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
    code_counts = dict(counts)
    code_counts[UNAVAILABLE] = code_counts.get(UNAVAILABLE, 0) - sum(
        bool(row.get("omitted_rows")) for row in report["rows"])
    checked = sum(n for status, n in code_counts.items() if status != NOT_CHECKED)
    tally = ", ".join(f"{n} {status}" for status, n in sorted(code_counts.items())
                      if status != NOT_CHECKED and n) or "none"
    lines = ["## SOTA sources: code citations (W1b phase A)", "",
             f"Mode `{report['mode']}`, exit {report['exit_code']}. {checked} code citations ({tally}); "
             f"{counts.get(NOT_CHECKED, 0)} entries not checked in phase A. {report['requests']} GitHub REST requests.",
             ""]
    if report.get("omitted_rows"):
        lines += [f"Report limited: {report['omitted_rows']} rows omitted; their outcomes are indeterminate.", ""]
    limits = report.get("limits", {})
    if "rows" in limits:
        lines += [f"Report bounds: {limits['rows']} data rows plus one omission row; "
                  f"{limits['entry_characters']} entry characters and {limits['row_field_characters']} "
                  "characters per other display field. Spans refer to the original input.", ""]
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
        "limits": {"citations": MAX_CITATIONS, "requests": github.max_requests,
                   "rows": MAX_ROWS, "omission_rows": 1, "entry_characters": MAX_ENTRY_CHARS,
                   "row_field_characters": MAX_ROW_FIELD_CHARS},
        "omitted_rows": sum(row.get("omitted_rows", 0) for row in rows),
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
    print(f"verify_sources: {sum(row['status'] != NOT_CHECKED and not row.get('omitted_rows') for row in rows)} code citations "
          f"{report['counts']}; mode {mode}, exit {code}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
