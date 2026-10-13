"""Count distinct pinned awesome lists per canonical GitHub repository.

Only gh api performs network operations. Uniform pinned raw source supplies
the count; native Contents HTML plus HTMLParser supplies the set cross-check.
This is the absent counter glue, using upstream alias-based API hydration.
References: cli/cli@fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd,
pkg/cmd/api/api.go:373; subev/awesome-stars@2a86cfbbc9a8eb8de49135c1ddbee4a9e3064bdf,
scripts/crawl.ts:440-459 and app/lib/repoIndex.server.ts:23-26.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import posixpath
import re
import subprocess
from urllib.parse import unquote, urlsplit


NAMES = (
    "awesome-claude-code", "awesome-ai-agents", "awesome-mcp-servers",
    "awesome-llm-apps", "awesome-agents", "awesome-codex",
)
CATEGORIES = {
    "agent-orchestration": "agent orchestration",
    "agent-observability": "agent observability",
    "coding-agent-harnesses": "coding agent harness",
    "agent-memory": "agent memory",
    "mcp-code-navigation": "MCP code navigation",
    "evaluation-harnesses": "evaluation harness",
}
RESERVED = {
    "about", "apps", "collections", "contact", "enterprise", "events", "explore",
    "features", "issues", "login", "marketplace", "new", "notifications", "orgs",
    "pricing", "pulls", "readme", "search", "security", "settings", "site",
    "sponsors", "topics", "users",
}
SLUG = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
RAW_REPOSITORY_URL = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:https?://)?(?:www\.)?github\.com/"
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[^\s<>\"')\]]*)?", re.I)
ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+|$)(.*)$")
SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def strip_comments_and_fences(text: str) -> str:
    """Freeze the lexical method: comments first, then fenced blocks; keep lines."""
    text = re.sub(r"<!--.*?(?:-->|\Z)",
                  lambda match: "\n" * match.group().count("\n"), text, flags=re.S)
    result = []
    fence = None
    for line in text.splitlines(keepends=True):
        match = FENCE.match(line.rstrip("\r\n"))
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
            result.append("\n" if line.endswith("\n") else "")
        elif match:
            fence = match[1]
            result.append("\n" if line.endswith("\n") else "")
        else:
            result.append(line)
    return "".join(result)


def parse_raw(text: str) -> dict:
    cleaned = strip_comments_and_fences(text)
    lines = cleaned.splitlines()
    heading_at = {}
    for index, line in enumerate(lines):
        atx = ATX.match(line)
        if atx:
            heading_at[index] = (len(atx[1]), re.sub(r"[ \t]+#+[ \t]*$", "", atx[2]).strip())
        elif index + 1 < len(lines) and line.strip() and not re.match(r"^\s*(?:[-*+]\s|>|\d+[.)]\s)", line):
            setext = SETEXT.match(lines[index + 1])
            if setext:
                heading_at[index] = (1 if setext[1][0] == "=" else 2, line.strip())
    sections = [{"id": "preamble", "heading": "(preamble)", "headings": []}]
    stack = []
    links = []
    for index, line in enumerate(lines):
        entry_heading = None
        section_id = sections[-1]["id"]
        if index in heading_at:
            level, heading = heading_at[index]
            while stack and stack[-1][0] >= level:
                stack.pop()
            section_id = stack[-1][2] if stack else "preamble"
            own_id = f"h{len(sections)}"
            stack.append((level, heading, own_id))
            sections.append({"id": own_id, "heading": heading,
                             "headings": [h for _, h, _ in stack], "line": index + 1})
            entry_heading = line.strip()
        section = next(s for s in sections if s["id"] == section_id)
        for match in RAW_REPOSITORY_URL.finditer(line):
            url = match.group()
            if not url.lower().startswith(("http://", "https://")):
                url = "https://" + url
            url = url.replace("://www.github.com/", "://github.com/")
            slug = repository_link(url)
            if slug:
                # Repository identity suffices; asset IDs/query parameters are
                # unnecessary publication data. Source pin/file/line retain provenance.
                url = "https://github.com/" + slug
                links.append({"url": url, "requested_repository": slug,
                              "section_id": section_id, "section": section["heading"],
                              "entry_heading": entry_heading, "line": index + 1,
                              "occurrence": len(links) + 1, "kind": "link"})
    local_links = re.findall(r"\]\(\s*<?([^\s)>]+)", cleaned)
    local_links += re.findall(r"^ {0,3}\[[^\]]+\]:\s*<?([^\s>]+)", cleaned, flags=re.M)
    local_links += [match.group() for match in RAW_REPOSITORY_URL.finditer(cleaned)]
    return {"sections": sections, "links": links, "local_links": local_links}


def repository_overlap(raw_links: list[dict], html_links: list[dict]) -> dict:
    raw = {repository_link(row["url"]).lower() for row in raw_links if repository_link(row["url"])}
    html = {repository_link(row["url"]).lower() for row in html_links if repository_link(row["url"])}
    union = raw | html
    return {"set_identity": "normalized requested owner/repo, before canonical API resolution",
            "raw_set_size": len(raw), "html_set_size": len(html),
            "intersection_size": len(raw & html), "union_size": len(union),
            "jaccard": len(raw & html) / len(union) if union else 1.0,
            "raw_only": sorted(raw - html), "html_only": sorted(html - raw)}


def utc() -> str:
    return subprocess.check_output(
        ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], text=True
    ).strip()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


LONG_HEX = re.compile(r"[0-9a-f]{40,64}", re.I)


def metadata_identifiers(value) -> set[str]:
    """Only typed public pin/digest fields approve opaque identifiers for relocation."""
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            typed = key in {"pin", "commit", "blob_sha", "ref", "sha256", "raw_ref", "html_crosscheck_ref"} or key.endswith(("_sha256", "_pin"))
            if typed and isinstance(item, str) and LONG_HEX.fullmatch(item):
                found.add(item)
            found.update(metadata_identifiers(item))
    elif isinstance(value, list):
        for item in value:
            found.update(metadata_identifiers(item))
    return found


class PublicationReferences:
    """Lossless JSON references keep opaque identifiers separate from named data."""
    def __init__(self, identifiers: dict | None = None, sources: dict | None = None):
        self.values = {row["id"]: row["value"] for row in (identifiers or {}).get("identifiers", [])}
        if len(self.values) != len((identifiers or {}).get("identifiers", [])):
            raise ValueError("duplicate identifier ID")
        if any(not re.fullmatch(r"I\d+", key) or not LONG_HEX.fullmatch(value)
               for key, value in self.values.items()):
            raise ValueError("invalid identifier registry")
        self.by_value = {value: key for key, value in self.values.items()}
        self.sources = sources or {"schema_version": 1, "lists": [], "documents": []}
        self.lists = {row["id"]: row for row in self.sources["lists"]}
        self.documents = {row["id"]: row for row in self.sources["documents"]}
        self.list_names = {row["repository"]: row["id"] for row in self.sources["lists"]}
        self.document_names = {(row["list_id"], row["path"]): row["id"] for row in self.sources["documents"]}

    def identifier(self, value: str) -> dict:
        if value not in self.by_value:
            key = f"I{len(self.values) + 1:05d}"
            self.by_value[value] = key
            self.values[key] = value
        return {"identifier_id": self.by_value[value]}

    def pack(self, value, approved: set[str]):
        if isinstance(value, dict):
            return {key: self.pack(item, approved) for key, item in value.items()}
        if isinstance(value, list):
            return [self.pack(item, approved) for item in value]
        if isinstance(value, str):
            if value in approved:
                return self.identifier(value)
            matches = [match for match in LONG_HEX.finditer(value) if match.group() in approved]
            if matches:
                parts, offset = [], 0
                for match in matches:
                    parts += [value[offset:match.start()], self.identifier(match.group())]
                    offset = match.end()
                return {"string_parts": parts + [value[offset:]]}
        return value

    def unpack(self, value):
        if isinstance(value, dict):
            if set(value) == {"identifier_id"}:
                try:
                    return self.values[value["identifier_id"]]
                except KeyError:
                    raise ValueError("unknown identifier reference") from None
            if set(value) == {"string_parts"}:
                return "".join(self.unpack(item) for item in value["string_parts"])
            return {key: self.unpack(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.unpack(item) for item in value]
        return value

    def count_references(self, value, parent_list: str | None = None):
        if isinstance(value, list):
            return [self.count_references(item, parent_list) for item in value]
        if not isinstance(value, dict):
            return value
        result = dict(value)
        if "list_repository" in result:
            name = result["list_repository"]
            parent_list = self.list_names[name]
            result["list_id"] = parent_list
            keys = [key for key in ["list_repository", "list_commit", "list_url"] if key in result]
            result["list_reference_fields"] = keys
            for key in keys:
                result.pop(key)
        if "file" in result and parent_list:
            result["document_id"] = self.document_names[(parent_list, result.pop("file"))]
        return {key: self.count_references(item, parent_list) for key, item in result.items()}

    def restore_count(self, value, parent_list: str | None = None):
        if isinstance(value, list):
            return [self.restore_count(item, parent_list) for item in value]
        if not isinstance(value, dict):
            return value
        result = dict(value)
        if "list_reference_fields" in result:
            parent_list = result.pop("list_id")
            source = self.lists[parent_list]
            fields = {"list_repository": source["repository"], "list_commit": source["commit"], "list_url": source["url"]}
            for key in result.pop("list_reference_fields"):
                result[key] = fields[key]
        if "document_id" in result:
            document = self.documents[result.pop("document_id")]
            if document["list_id"] != parent_list:
                raise ValueError("document reference belongs to a different list")
            result["file"] = document["path"]
        return {key: self.restore_count(item, parent_list) for key, item in result.items()}

    def registry(self) -> dict:
        return {"schema_version": 1, "identifiers": [{"id": key, "value": value} for key, value in self.values.items()]}


def raw_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Native JSON serialization, one top-level array record per line. Large
    # derived receipts stay inspectable without repeated indentation overhead.
    def encode(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    parts = []
    for key, item in value.items():
        rendered = "[\n" + ",\n".join("    " + encode(row) for row in item) + "\n  ]" if isinstance(item, list) and item else encode(item)
        parts.append("  " + encode(key) + ": " + rendered)
    path.write_text("{\n" + ",\n".join(parts) + "\n}\n", encoding="utf-8")


def publication_references(directory: Path) -> PublicationReferences | None:
    path = directory / "identifiers.json"
    if not path.exists():
        return None
    identifiers = json.loads(path.read_text())
    initial = PublicationReferences(identifiers)
    sources = initial.unpack(json.loads((directory / "sources.json").read_text()))
    return PublicationReferences(identifiers, sources)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    refs = publication_references(path.parent)
    if refs and path.name not in {"identifiers.json", "sources.json"}:
        value = refs.unpack(value)
        if path.name == "a3.json":
            value = refs.restore_count(value)
    return value


def write_json(path: Path, value: dict) -> None:
    refs = publication_references(path.parent)
    if refs and path.name not in {"identifiers.json", "sources.json"}:
        approved = set(refs.by_value) | metadata_identifiers(value)
        if path.name == "a3.json":
            value = refs.count_references(value)
        value = refs.pack(value, approved)
        if LONG_HEX.search(json.dumps(value)):
            raise ValueError("unclassified opaque identifier remains in named publication data")
        raw_write_json(path.parent / "identifiers.json", refs.registry())
    raw_write_json(path, value)


def publish_references(directory: Path) -> None:
    """Split all named JSON receipts and the per-repository count references."""
    if (directory / "identifiers.json").exists():
        raise ValueError("publication references already exist")
    records = {path.name: json.loads(path.read_text()) for path in directory.glob("*.json")}
    corpus = records["corpus.json"]
    sources = {"schema_version": 1, "lists": [], "documents": []}
    for index, listing in enumerate(corpus["lists"], 1):
        list_id = f"L{index:04d}"
        sources["lists"].append({"id": list_id, "repository": listing["repository"],
                                "commit": listing["commit"], "url": listing["url"]})
        for doc in listing["documents"]:
            sources["documents"].append({"id": f"D{len(sources['documents']) + 1:04d}",
                "list_id": list_id, "path": doc["path"], "blob_sha": doc["blob_sha"],
                "sha256": doc["sha256"]})
    refs = PublicationReferences(sources=sources)
    approved = metadata_identifiers(sources)
    for value in records.values():
        approved.update(metadata_identifiers(value))
    for name, original in records.items():
        counted = refs.count_references(original) if name == "a3.json" else original
        encoded = refs.pack(counted, approved)
        if LONG_HEX.search(json.dumps(encoded)):
            raise ValueError(f"unclassified opaque identifier in {name}")
        restored = refs.unpack(encoded)
        if name == "a3.json":
            restored = refs.restore_count(restored)
        if restored != original:
            raise ValueError(f"publication reference round-trip differs for {name}")
        raw_write_json(directory / name, encoded)
    raw_write_json(directory / "sources.json", refs.pack(sources, approved))
    raw_write_json(directory / "identifiers.json", refs.registry())
    print(json.dumps({"status": "published-references", "named_files": len(records),
                      "lists": len(sources["lists"]), "documents": len(sources["documents"]),
                      "identifiers": len(refs.values), "round_trips_agree": True}))


class GithubError(RuntimeError):
    def __init__(self, status: int | None, headers: dict | None = None):
        self.status = status
        self.headers = headers or {}
        super().__init__(f"GitHub API failed (HTTP {status or 'unknown'})")


class Github:
    def api(self, endpoint: str, *, fields: dict | None = None,
            raw: bool = False, accept: str | None = None, method: str = "GET"):
        if method not in {"GET", "POST"} or (method == "POST" and endpoint != "graphql"):
            raise ValueError("only read-only GraphQL queries may use POST")
        argv = ["gh", "api", "--hostname", "github.com", "--include", "--method", method, endpoint]
        if accept:
            argv += ["-H", f"Accept: {accept}"]
        for key, value in (fields or {}).items():
            argv += ["-f", f"{key}={value}"]
        result = subprocess.run(
            argv,
            text=True, capture_output=True, timeout=60,
        )
        response = result.stdout
        headers = {}
        while response.startswith("HTTP/") and "\n\n" in response:
            header_text, response = response.split("\n\n", 1)
            for line in header_text.splitlines()[1:]:
                key, separator, value = line.partition(":")
                key = key.lower()
                if separator and (key.startswith("x-ratelimit-") or key in {"retry-after", "content-type"}):
                    headers[key] = value.strip()
        self.last_headers = headers
        if result.returncode:
            if endpoint == "graphql" and response.startswith("{"):
                partial = json.loads(response)
                if partial.get("data") is not None and all(
                    error.get("type") == "NOT_FOUND" for error in partial.get("errors", [])):
                    return partial
            match = re.search(r"HTTP (\d{3})", result.stderr)
            # Do not publish native authentication diagnostics or account details.
            raise GithubError(int(match.group(1)) if match else None, headers)
        return response if raw else json.loads(response)

    def repository(self, requested: str) -> dict:
        if not SLUG.fullmatch(requested):
            raise ValueError("invalid repository slug")
        read_at = utc()
        try:
            data = self.api(f"repos/{requested}")
        except GithubError as error:
            if error.status not in {404, 410, 451}:
                raise
            return {"requested": requested, "read_at": read_at,
                    "status": "unresolvable", "http_status": error.status}
        return {"requested": requested, "read_at": read_at, "status": "resolved",
                "repository": data["full_name"], "repository_id": data["id"],
                "url": data["html_url"]}

    def render(self, repository: str, path: str, commit: str, size: int) -> str:
        if size > 1_000_000:
            raise ValueError(f"not rendered: {repository}/{path} exceeds the 1 MB Contents html limit")
        return self.api(f"repos/{repository}/contents/{path}", fields={"ref": commit},
                        accept="application/vnd.github.html+json", raw=True)

    def repository_batch(self, requested: list[str]) -> list[dict]:
        """Upstream awesome-stars' 40-alias hydration, through native gh only."""
        if any(not SLUG.fullmatch(slug) for slug in requested):
            raise ValueError("invalid repository slug")
        fields = []
        for index, slug in enumerate(requested):
            owner, name = slug.split("/")
            fields.append(f"r{index}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) "
                          "{ nameWithOwner url databaseId isPrivate }")
        read_at = utc()
        result = self.api("graphql", fields={"query": "query { " + " ".join(fields) + " }"}, method="POST")
        errors = {str(error.get("path", [""])[0]): error for error in result.get("errors", [])}
        if any(error.get("type") != "NOT_FOUND" for error in errors.values()):
            raise ValueError("GraphQL repository batch has an unresolved API error")
        rows = []
        for index, slug in enumerate(requested):
            alias = f"r{index}"
            data = result.get("data", {}).get(alias)
            if data is None:
                if alias not in errors:
                    raise ValueError("GraphQL returned a null repository without a NOT_FOUND result")
                rows.append({"requested": slug, "read_at": read_at, "status": "unresolvable",
                             "api_error_type": "NOT_FOUND", "api": "gh api graphql"})
            elif data["isPrivate"]:
                rows.append({"requested": slug, "read_at": read_at, "status": "unresolvable",
                             "api_error_type": "NONPUBLIC", "api": "gh api graphql"})
            else:
                rows.append({"requested": slug, "read_at": read_at, "status": "resolved",
                    "repository": data["nameWithOwner"], "repository_id": data["databaseId"],
                    "url": data["url"], "api": "gh api graphql"})
        return rows


def repository_link(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.hostname != "github.com":
        return None
    parts = unquote(parsed.path).strip("/").split("/")
    if len(parts) < 2 or parts[0].lower() in RESERVED:
        return None
    slug = "/".join(parts[:2])
    if slug.endswith(".git"):
        slug = slug[:-4]
    return slug if SLUG.fullmatch(slug) else None


class HeadingLinks(HTMLParser):
    """Read rendered HTML, preserving section hierarchy and link occurrences."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections = [{"id": "preamble", "heading": "(preamble)", "headings": []}]
        self.links: list[dict] = []
        self.stack: list[tuple[int, str]] = []
        self.heading_level: int | None = None
        self.heading_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if re.fullmatch(r"h[1-6]", tag):
            self.heading_level = int(tag[1])
            self.heading_parts = []
        if (tag == "a" and attrs.get("href") and repository_link(attrs["href"])
                and not attrs["href"].startswith("#")
                and "anchor" not in attrs.get("class", "").split()):
            self.links.append({"url": "https://github.com/" + repository_link(attrs["href"]), "section_id": self.sections[-1]["id"],
                               "occurrence": len(self.links) + 1, "kind": "link"})
        if tag == "img" and attrs.get("src") and repository_link(attrs["src"]):
            self.links.append({"url": "https://github.com/" + repository_link(attrs["src"]), "section_id": self.sections[-1]["id"],
                               "occurrence": len(self.links) + 1, "kind": "image"})

    def handle_data(self, text):
        if self.heading_level is not None:
            self.heading_parts.append(text)

    def handle_endtag(self, tag):
        if re.fullmatch(r"h[1-6]", tag) and self.heading_level is not None:
            heading = " ".join("".join(self.heading_parts).split())
            while self.stack and self.stack[-1][0] >= self.heading_level:
                self.stack.pop()
            self.stack.append((self.heading_level, heading))
            self.sections.append({"id": f"h{len(self.sections)}", "heading": heading,
                                  "headings": [text for _, text in self.stack]})
            self.heading_level = None


def parse_html(rendered: str) -> HeadingLinks:
    parser = HeadingLinks()
    parser.feed(rendered)
    parser.close()
    return parser


def linked_markdown(url: str, repository: str, current_path: str) -> str | None:
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    if parsed.netloc:
        if repository_link(url) != repository:
            return None
        parts = path.strip("/").split("/")
        if len(parts) < 5 or parts[2] not in {"blob", "raw"}:
            return None
        path = "/".join(parts[4:])
    elif parsed.scheme or not path:
        return None
    elif path.startswith("/"):
        path = path.lstrip("/")
    else:
        path = posixpath.join(posixpath.dirname(current_path), path)
    path = posixpath.normpath(path)
    if path.startswith("../") or not path.lower().endswith(".md"):
        return None
    return path


def search_lists(github: Github, query: str, purpose: str) -> dict:
    read_at = utc()
    result = github.api("search/repositories", fields={
        "q": query, "sort": "stars", "order": "desc", "per_page": 100,
    })
    if result.get("incomplete_results"):
        raise ValueError("GitHub search returned incomplete results")
    fields = ("full_name", "name", "stargazers_count", "pushed_at", "archived", "default_branch")
    return {"purpose": purpose, "query": query, "read_at": read_at,
            "total_count": result["total_count"],
            "returned": [{key: row[key] for key in fields} for row in result["items"]]}


def select_lists(github: Github, directory: Path) -> dict:
    started_at = utc()
    cutoff = (datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ") - timedelta(days=90)).date()
    searches = []
    selections: dict[str, list[dict]] = defaultdict(list)
    for name in NAMES:
        query = f"{name} in:name pushed:>={cutoff} archived:false"
        search = search_lists(github, query, "named:" + name)
        matches = [r for r in search["returned"] if r["name"].lower() == name]
        if not matches:
            raise ValueError(f"no exact maintained list found: {name}")
        chosen = matches[0]
        search["selected"] = [chosen["full_name"]]
        searches.append(search)
        selections[chosen["full_name"]].append({"named_list": name,
            "rule": "highest-star exact repository name, nonarchived, pushed within 90 days; named lists have no minimum-star rule"})
    for category, keywords in CATEGORIES.items():
        query = (f"awesome {keywords} in:name,description,readme topic:awesome-list "
                 f"stars:>=1000 pushed:>={cutoff} archived:false")
        search = search_lists(github, query, "extension:" + category)
        chosen = search["returned"][:2]
        if len(chosen) != 2:
            raise ValueError(f"fewer than two extension lists: {category}")
        search["selected"] = [r["full_name"] for r in chosen]
        searches.append(search)
        for row in chosen:
            selections[row["full_name"]].append({"extension_category": category,
                "rule": "top two GitHub results by stars; awesome-list topic restricts search to curated lists"})
    lists = []
    for requested, selected_for in sorted(selections.items()):
        resolution = github.repository(requested)
        if resolution["status"] != "resolved":
            raise ValueError("selected list cannot be resolved")
        repo = resolution["repository"]
        metadata = github.api(f"repos/{repo}")
        commit = github.api(f"repos/{repo}/commits/{metadata['default_branch']}")["sha"]
        lists.append({"repository": repo, "repository_id": resolution["repository_id"],
                      "url": resolution["url"], "commit": commit, "read_at": utc(),
                      "stars": metadata["stargazers_count"], "pushed_at": metadata["pushed_at"],
                      "selected_for": selected_for})
    result = {"schema_version": 1, "kind": "awesome-list-selection", "started_at": started_at,
              "cutoff": str(cutoff), "searches": searches, "lists": lists}
    write_json(directory / "selection.json", result)
    return result


def collect_raw(github: Github, directory: Path) -> dict:
    """Apply one raw method to the frozen selection; HTML is a set cross-check."""
    selected = directory / "selection.json"
    previous = read_json(selected if selected.exists() else directory / "progress.json")
    started_at = utc()
    selections = defaultdict(list)
    for search in previous["searches"]:
        for name in search["selected"]:
            selections[name].append(search["purpose"])
    retained = {row["repository"]: row for row in previous["lists"]}
    lists = []
    for requested, selected_for in sorted(selections.items()):
        original_list = retained.get(requested)
        resolution = github.repository(requested)
        if resolution["status"] != "resolved":
            raise ValueError("selected list cannot be resolved")
        repo = resolution["repository"]
        metadata = github.api(f"repos/{repo}")
        if original_list:
            commit = original_list["commit"]
        elif repo == "punkpeye/awesome-mcp-servers":
            commit = "cc7f1f42c3fa8ced6fd5c0e02ea366ef7ed8cf1b"
        else:
            commit = github.api(f"repos/{repo}/commits/{metadata['default_branch']}")["sha"]
        readme = github.api(f"repos/{repo}/readme", fields={"ref": commit})
        old_docs = {doc["path"]: doc for doc in original_list.get("documents", [])} if original_list else {}
        queue = list(dict.fromkeys([readme["path"], *old_docs]))
        seen = set()
        documents = []
        ignored = []
        for path in queue:
            if path in seen:
                continue
            seen.add(path)
            if len(seen) > 200:
                raise ValueError("linked Markdown document bound exceeded")
            try:
                data = readme if path == readme["path"] else github.api(
                    f"repos/{repo}/contents/{path}", fields={"ref": commit})
            except GithubError as error:
                if error.status != 404:
                    raise
                ignored.append({"path": path, "reason": "404 at pinned commit"})
                continue
            raw_read_at = utc()
            raw = github.api(f"repos/{repo}/contents/{path}", fields={"ref": commit},
                             accept="application/vnd.github.raw", raw=True)
            parsed = parse_raw(raw)
            old = old_docs.get(path)
            if old and old["sha256"] != digest(raw.encode()):
                raise ValueError("pinned raw bytes differ from previously read source")
            if old:
                html_links = old["links"]
                html_provenance = {"read_at": old["read_at"], "sha256": old["rendered_sha256"],
                    "media_type": "application/vnd.github.html+json", "ref": commit,
                    "reused": True, "status": "rendered"}
            elif data["size"] <= 1_000_000:
                html_read_at = utc()
                html = github.render(repo, path, commit, data["size"])
                html_links = parse_html(html).links
                html_provenance = {"read_at": html_read_at, "sha256": digest(html.encode()),
                    "media_type": "application/vnd.github.html+json", "ref": commit,
                    "reused": False, "status": "rendered"}
            else:
                html_links = []
                html_provenance = {"status": "not_rendered", "size_bytes": data["size"],
                    "media_type": "application/vnd.github.html+json", "ref": commit,
                    "reason": "exceeds supported 1 MB html media-type limit"}
            for url in [*parsed["local_links"], *(row["url"] for row in parsed["links"])]:
                linked = linked_markdown(url, repo, path)
                if linked and linked not in seen and linked not in queue:
                    if re.search(r"(?:^|/)readme[._-][^.]+\.md$", linked, re.I) or "translations/" in linked:
                        ignored.append({"path": linked, "reason": "translated README; same list"})
                    else:
                        queue.append(linked)
            documents.append({"path": path, "read_at": raw_read_at, "blob_sha": data["sha"],
                "size_bytes": data["size"], "sha256": digest(raw.encode()),
                "raw_request": {"media_type": "application/vnd.github.raw", "ref": commit},
                "html_crosscheck": html_provenance, "html_links": html_links,
                "source": {"kind": "repo", "repository": f"https://github.com/{repo}",
                           "pin": commit, "path": path, "line": 1},
                "sections": parsed["sections"], "links": parsed["links"]})
        compared = [doc for doc in documents if doc["html_crosscheck"]["status"] == "rendered"]
        overlap = repository_overlap([r for d in compared for r in d["links"]],
                                     [r for d in compared for r in d["html_links"]])
        overlap["compared_files"] = [d["path"] for d in compared]
        overlap["not_rendered_files"] = [d["path"] for d in documents if d not in compared]
        overlap["status"] = "measured" if compared else "not_available"
        lists.append({"repository": repo, "repository_id": resolution["repository_id"],
            "url": resolution["url"], "commit": commit, "read_at": started_at,
            "stars": metadata["stargazers_count"], "pushed_at": metadata["pushed_at"],
            "selected_for": selected_for, "documents": documents,
            "raw_media_type": "application/vnd.github.raw", "raw_ref": commit,
            "html_crosscheck_media_type": "application/vnd.github.html+json", "html_crosscheck_ref": commit,
            "overlap": overlap, "unavailable_or_translated_documents": ignored})
        progress = {"schema_version": 1, "kind": "awesome-list-raw-corpus", "started_at": started_at,
            "cutoff": previous["cutoff"], "searches": previous["searches"], "lists": lists,
            "canonicalization": [], "status": "collecting_raw"}
        write_json(directory / "raw-progress.json", progress)
        print(json.dumps({"list": repo, "documents": len(documents), "overlap": overlap["jaccard"],
                          "raw_only": len(overlap["raw_only"]), "html_only": len(overlap["html_only"]),
                          "crosscheck_status": overlap["status"]}), flush=True)
    progress["completed_at"] = utc()
    progress["status"] = "awaiting_overlap_review" if any(
        r["overlap"]["status"] == "measured" and r["overlap"]["jaccard"] < 0.95 for r in lists) else "ready_for_canonicalization"
    write_json(directory / "raw-progress.json", progress)
    write_json(directory / "overlap.json", {"schema_version": 1, "count_method": "raw only",
        "completed_at": progress["completed_at"], "threshold": 0.95,
        "crosscheck_only": True, "status": progress["status"],
        "lists": [{"repository": r["repository"], "commit": r["commit"], **r["overlap"]} for r in lists]})
    return progress


def remeasure(github: Github, directory: Path) -> dict:
    """Retain the failed overlap, then re-read the same pins after the two fixes."""
    corpus = read_json(directory / "raw-progress.json")
    before = read_json(directory / "overlap.json")
    if (directory / "overlap-before-heading-fix.json").exists():
        raise ValueError("retain this measured attempt before another remeasurement")
    write_json(directory / "overlap-before-heading-fix.json", before)
    write_json(directory / "raw-before-heading-fix.json", corpus)
    started_at = utc()
    for listing in corpus["lists"]:
        for doc in listing["documents"]:
            repo, path, commit = listing["repository"], doc["path"], listing["commit"]
            raw_read_at = utc()
            raw = github.api(f"repos/{repo}/contents/{path}", fields={"ref": commit},
                             accept="application/vnd.github.raw", raw=True)
            if digest(raw.encode()) != doc["sha256"]:
                raise ValueError("raw bytes changed at the recorded source pin")
            parsed = parse_raw(raw)
            if {r["requested_repository"].lower() for r in parsed["links"]} != {
                r["requested_repository"].lower() for r in doc["links"]}:
                raise ValueError("heading refinement changed the raw URL set")
            doc["sections"], doc["links"] = parsed["sections"], parsed["links"]
            doc["raw_refinement_read_at"] = raw_read_at
            if doc["size_bytes"] <= 1_000_000:
                html_read_at = utc()
                html = github.render(repo, path, commit, doc["size_bytes"])
                doc["html_links"] = parse_html(html).links
                doc["html_crosscheck_before_fix"] = doc["html_crosscheck"]
                doc["html_crosscheck"] = {"read_at": html_read_at, "sha256": digest(html.encode()),
                    "media_type": "application/vnd.github.html+json", "ref": commit,
                    "reused": False, "status": "rendered"}
        compared = [d for d in listing["documents"] if d["html_crosscheck"]["status"] == "rendered"]
        overlap = repository_overlap([r for d in compared for r in d["links"]],
                                     [r for d in compared for r in d["html_links"]])
        overlap["compared_files"] = [d["path"] for d in compared]
        overlap["not_rendered_files"] = [d["path"] for d in listing["documents"] if d not in compared]
        overlap["status"] = "measured" if compared else "not_available"
        if not compared:
            overlap["jaccard"] = None
        listing["overlap"] = overlap
        write_json(directory / "remeasure-progress.json", corpus)
        print(json.dumps({"list": listing["repository"], "jaccard": overlap["jaccard"],
                          "raw_only": len(overlap["raw_only"]), "html_only": len(overlap["html_only"])}), flush=True)
    corpus["remeasurement_started_at"] = started_at
    corpus["remeasurement_completed_at"] = utc()
    corpus["status"] = "awaiting_overlap_review" if any(
        r["overlap"]["status"] == "measured" and r["overlap"]["jaccard"] < 0.95
        for r in corpus["lists"]) else "ready_for_canonicalization"
    write_json(directory / "raw-progress.json", corpus)
    after = {"schema_version": 1, "count_method": "raw only", "crosscheck_only": True,
             "completed_at": corpus["remeasurement_completed_at"], "threshold": 0.95,
             "status": corpus["status"], "lists": [{"repository": r["repository"],
             "commit": r["commit"], **r["overlap"]} for r in corpus["lists"]]}
    write_json(directory / "overlap.json", after)
    return corpus


def canonicalize_raw(github: Github, directory: Path, workers: int) -> dict:
    corpus = read_json(directory / "raw-progress.json")
    if corpus["status"] != "ready_for_canonicalization":
        raise ValueError("overlap below 0.95 requires a coordination ruling before counting")
    requested = {}
    for listing in corpus["lists"]:
        for doc in listing["documents"]:
            for row in doc["links"]:
                requested.setdefault(row["requested_repository"].lower(), row["requested_repository"])
    resolutions = []
    targets = [requested[k] for k in sorted(requested)]
    batches = [targets[index:index + 40] for index in range(0, len(targets), 40)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for batch in pool.map(github.repository_batch, batches):
            resolutions.extend(batch)
            if len(resolutions) % 400 == 0 or len(resolutions) == len(targets):
                write_json(directory / "canonicalization-progress.json", {"schema_version": 1,
                    "started_at": corpus["started_at"], "target_count": len(targets),
                    "canonicalization": resolutions})
                print(json.dumps({"canonicalized": len(resolutions), "targets": len(requested)}), flush=True)
    corpus["canonicalization"] = resolutions
    corpus["completed_at"] = utc()
    corpus["status"] = "complete"
    corpus["canonicalization_interface"] = {
        "command": "gh api graphql", "read_only_query": True, "batch_size": 40,
        "upstream_repository": "https://github.com/subev/awesome-stars",
        "pin": "2a86cfbbc9a8eb8de49135c1ddbee4a9e3064bdf",
        "path": "app/lib/graphql.server.ts", "line": 97}
    return corpus


def sanitize_receipts(directory: Path) -> None:
    """Minimize URL payloads without changing any repository-set observation."""
    files = ["corpus.json", "progress.json", "raw-before-heading-fix.json",
             "raw-progress.json", "remeasure-progress.json", "canonicalization-progress.json"]
    before_bytes = after_bytes = 0
    for filename in files:
        path = directory / filename
        if not path.exists():
            continue
        record = read_json(path)
        before_bytes += path.stat().st_size
        for listing in record.get("lists", []):
            for doc in listing["documents"]:
                for key in ["links", "html_links"]:
                    if key not in doc:
                        continue
                    original = doc[key]
                    minimized = [{**row, "url": "https://github.com/" + repository_link(row["url"])}
                                 for row in original if repository_link(row["url"])]
                    old_set = {repository_link(row["url"]).lower() for row in original if repository_link(row["url"])}
                    new_set = {repository_link(row["url"]).lower() for row in minimized}
                    if old_set != new_set:
                        raise ValueError("URL minimization changed repository identity sets")
                    doc[key] = minimized
        for resolution in record.get("canonicalization", []):
            resolution.pop("api_node_id", None)
        record["publication_sanitization"] = "Repository URLs reduced to owner/repo; non-repository HTML links/images omitted. Source hashes, pins, file/line, repository sets and measured differences preserved."
        write_json(path, record)
        after_bytes += path.stat().st_size
    print(json.dumps({"status": "sanitized", "before_bytes": before_bytes,
                      "after_bytes": after_bytes, "repository_sets_unchanged": True}))


def mapped_rows(corpus: dict, mapping: dict) -> list[dict]:
    if set(mapping["categories"]) != set(CATEGORIES):
        raise ValueError("mapping must name all six categories")
    rules = mapping["rules"]
    compiled = [(r, re.compile(r["heading_regex"], re.I),
                 re.compile(r.get("context_regex", ".*"), re.I)) for r in rules]
    canonical = {r["requested"].lower(): r for r in corpus["canonicalization"]}
    rows = []
    for listing in corpus["lists"]:
        for doc in listing["documents"]:
            sections = {s["id"]: s for s in doc["sections"]}
            for link in doc["links"]:
                resolution = canonical[link["requested_repository"].lower()]
                section = sections[link["section_id"]]
                matches = [r for r, heading, context in compiled
                           if any(heading.search(h) for h in section["headings"])
                           and context.search(" / ".join(section["headings"]))]
                eligible = resolution["status"] == "resolved" and link["kind"] == "link"
                categories = sorted({r["category"] for r in matches}) if eligible else []
                if any(c not in CATEGORIES for c in categories):
                    raise ValueError("unknown mapping category")
                rows.append({"list_repository": listing["repository"],
                    "list_commit": listing["commit"], "list_url": listing["url"],
                    "file": doc["path"], **link, "section_heading": section["heading"],
                    "section_path": section["headings"], "mapping_categories": categories,
                    "mapping_rule_ids": [r["id"] for r in matches] if eligible else [],
                    "canonical_repository": resolution.get("repository"),
                    "repository_id": resolution.get("repository_id"),
                    "resolution_status": resolution["status"], "eligible": eligible})
    return rows


def count_rows(rows: list[dict], threshold: int = 3) -> dict:
    if threshold < 1:
        raise ValueError("positive threshold required")
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["eligible"]:
            grouped[row["canonical_repository"]][row["list_repository"]].append(row)
    result = {category: [] for category in CATEGORIES}
    for repository, memberships in sorted(grouped.items()):
        if len(memberships) >= threshold:
            categories = sorted({c for links in memberships.values() for r in links for c in r["mapping_categories"]})
            for category in categories:
                result[category].append({"repository": repository, "distinct_list_count": len(memberships),
                "category_support_distinct_list_count": sum(any(category in r["mapping_categories"] for r in links) for links in memberships.values()),
                "memberships": [{"list_repository": name, "list_commit": links[0]["list_commit"],
                    "list_url": links[0]["list_url"],
                    "headings": [{"file": r["file"], "section_heading": r["section_heading"],
                        "section_path": r["section_path"], "mapping_rule_ids": r["mapping_rule_ids"],
                        "mapping_categories": r["mapping_categories"], "entry_heading": r.get("entry_heading"),
                        "section": r.get("section", r["section_heading"]), "line": r.get("line"),
                        "url": r["url"], "occurrence": r["occurrence"]} for r in links]}
                    for name, links in sorted(memberships.items())]})
    return result


def build(corpus: dict, mapping: dict, corpus_ref: str, mapping_ref: str) -> dict:
    if corpus.get("kind") != "awesome-list-raw-corpus" or corpus.get("status") != "complete":
        raise ValueError("only the completed uniform raw corpus can supply a count")
    rows = mapped_rows(corpus, mapping)
    return {"schema_version": 1, "kind": "awesome-list-community-evidence", "angle": "A3",
        "angle_protocol": "angle-convergence/2", "evidence_class": "source_review",
        "read_at": corpus["completed_at"], "threshold": 3,
        "sources": [{"kind": "receipt", "path": corpus_ref}, {"kind": "receipt", "path": mapping_ref}],
        "corpus_sha256": digest(json.dumps(corpus, sort_keys=True, ensure_ascii=False).encode()),
        "mapping_sha256": digest(json.dumps(mapping, sort_keys=True, ensure_ascii=False).encode()),
        "list_count": len(corpus["lists"]), "category_results": count_rows(rows),
        "rows": rows, "unresolvable_links": [r for r in corpus["canonicalization"] if r["status"] != "resolved"],
        "limitations": mapping["limitations"]}


def summary(artifact: dict) -> str:
    lines = ["# Awesome-list cross-list counts (A3)", "",
        f"Read completed {artifact['read_at']}; {artifact['list_count']} distinct pinned lists.", "",
        "Each count is the number of distinct lists linking the canonical repository. Categories come from the recorded section mapping; the JSON also reports how many lists support each category.",
        "A3 is a community proxy; these counts do not select defaults or establish convergence.", "",
        "| Category | Repositories in at least three lists |", "| --- | --- |"]
    for category, results in artifact["category_results"].items():
        text = ", ".join(f"[{r['repository']}](https://github.com/{r['repository']}) ({r['distinct_list_count']} lists; {r['category_support_distinct_list_count']} supports this category)" for r in results) or "None in this mapped corpus"
        lines.append(f"| {category} | {text} |")
    lines += ["", "`a3.json` references lists/documents by ID; `sources.json` maps those IDs to repository/path metadata, and `identifiers.json` holds the full pins and digests without repository names. `corpus.json` retains source rows and canonical identities. The script resolves references for offline verification.", ""]
    lines += ["The extension queries selected broad curated lists. Unmapped sections remain uncategorized; empty categories describe this corpus, not the ecosystem. The full method and limitations are in `mapping.json`.", "",
              "Nine supported HTML cross-checks met the 0.95 overlap threshold after the heading-link fix; the oversized MCP README was counted through raw only. `OVERLAP.md` retains the diagnosis and before/after measurements."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["select", "freeze-selection", "collect-raw", "remeasure", "canonicalize", "sanitize", "publish", "build", "check"])
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    directory = args.directory
    if not 1 <= args.workers <= 8:
        parser.error("workers must be between 1 and 8")
    if args.action == "publish":
        publish_references(directory)
        return
    if args.action == "sanitize":
        sanitize_receipts(directory)
        return
    if args.action == "select":
        if (directory / "selection.json").exists():
            parser.error("use a new directory to preserve the previous selection")
        select_lists(Github(), directory)
        return
    if args.action == "freeze-selection":
        retained = read_json(directory / "raw-progress.json")
        fields = ["repository", "repository_id", "url", "commit", "read_at", "stars", "pushed_at", "selected_for"]
        write_json(directory / "selection.json", {"schema_version": 1, "kind": "awesome-list-selection",
            "started_at": retained["started_at"], "cutoff": retained["cutoff"],
            "searches": retained["searches"],
            "lists": [{key: row[key] for key in fields} for row in retained["lists"]]})
        return
    if args.action == "remeasure":
        result = remeasure(Github(), directory)
        if result["status"] == "awaiting_overlap_review":
            raise SystemExit(2)
        return
    if args.action == "collect-raw":
        if (directory / "raw-progress.json").exists():
            parser.error("preserve the previous raw source read before starting another")
        result = collect_raw(Github(), directory)
        if result["status"] == "awaiting_overlap_review":
            raise SystemExit(2)
        return
    if args.action == "canonicalize":
        if (directory / "corpus.json").exists():
            parser.error("use a new directory to preserve the previous source read")
        write_json(directory / "corpus.json", canonicalize_raw(Github(), directory, args.workers))
        return
    corpus = read_json(directory / "corpus.json")
    mapping = read_json(directory / "mapping.json")
    relative = directory.as_posix()
    if directory.is_absolute():
        relative = directory.relative_to(Path(__file__).resolve().parents[1]).as_posix()
    artifact = build(corpus, mapping, relative + "/corpus.json", relative + "/mapping.json")
    markdown = summary(artifact)
    if args.action == "check":
        if read_json(directory / "a3.json") != artifact or (directory / "SUMMARY.md").read_text() != markdown:
            raise ValueError("committed counts or summary differ from the retained corpus/mapping")
    else:
        write_json(directory / "a3.json", artifact)
        (directory / "SUMMARY.md").write_text(markdown, encoding="utf-8")
    print(json.dumps({"status": "checked" if args.action == "check" else "built",
                      "lists": artifact["list_count"], "rows": len(artifact["rows"]),
                      "unresolved": len(artifact["unresolvable_links"]),
                      "repositories_per_category": {k: len(v) for k, v in artifact["category_results"].items()}}))


if __name__ == "__main__":
    main()
