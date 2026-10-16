#!/usr/bin/env python3
"""Step-1 coverage ledger: one disposition for every seed from the stars, the awesome lists and the research runs.

Deterministic: no model calls, no keyed calls and no GitHub API. The lists are read by screen_generic.extract() and
external_resources() (tools/landscape/screen_generic.py; the hash recorded at
catalogs/landscape/grand-catalog-20261008.json:340 binds its original bytes) on one clone per list at its pin.

  python3 -I tools/landscape/coverage_ledger.py build --clones DIR [--clones DIR ...] --state-root DIR \
      --pr-files DIR --scratch DIR [--gptr-checkout DIR] [--date YYYYMMDD] [--repo-root .]
  python3 tools/landscape/coverage_ledger.py check [--repo-root .]

build runs on a host that holds the list clones and the retained research inputs, and writes
  catalogs/landscape/coverage/awesome-lists-<date>.json               the pinned list table and its census reconciliation
  evidence/artifacts/landscape-coverage-ledger-<date>/runs-index.json  the research-runtime runs index
  catalogs/landscape/coverage/coverage-ledger-<date>.json             one row per seed, each with exactly one disposition
check reads committed files only: the newest coverage-ledger-<date>.json, the two files it names and the records they
reconcile with. It prints one problem per line and exits 1 when any remain (tests/test_landscape_coverage_ledger.py).
tools/landscape/README.md states the disposition rules and the boundaries.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import importlib.util
import ipaddress
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
SCREEN_GENERIC = Path(__file__).resolve().with_name("screen_generic.py")
GRAND = "catalogs/landscape/grand-catalog-20261008.json"
COVERAGE_ACCOUNTING = "catalogs/us-equities/architecture/coverage-accounting.json"
US_COVERAGE = "catalogs/us-equities/coverage.json"
STARS = "catalogs/convergence-practice/public-starred.json"
STARRED_SEEDS = "catalogs/convergence-practice/starred-seeds-20261010.json"
MASTER_SEEDS = "catalogs/convergence-practice/sources/master-seeds-20261010.json"
FINAL_STACK = "catalogs/landscape/final-stack.json"
STACK = "manifests/stack.json"
DISPATCH = "tools/research/dispatch"
LANDSCAPE_DIR = "catalogs/landscape"  # the canonical layer catalogs master_seeds reads
# The coverage documents live one level down. Readers glob the top level and parse every file there:
# scripts/host_receipts.py:449-462 (landscape_winners, once per component through winner_pins at :537-539 and
# scripts/receipt_staleness.py:75), and the Architecture refresh at tools/local-pages/architecture_sources.py:378
# and architecture_builder.py:383, all at 1b633d861518fa0d299279b1cfaec11d0fb47f82.
LEDGER_DIR = "catalogs/landscape/coverage"
LEDGER_NAME = re.compile(r"coverage-ledger-(\d{8})\.json")
LISTS_NAME = LEDGER_DIR + "/awesome-lists-{date}.json"
RUNS_NAME = "evidence/artifacts/landscape-coverage-ledger-{date}/runs-index.json"
SCHEMAS = {"ledger": LEDGER_DIR + "/coverage-ledger.schema.json",
           "lists": LEDGER_DIR + "/awesome-lists.schema.json",
           "runs": LEDGER_DIR + "/runs-index.schema.json"}
# Retained research inputs, relative to <state-root>/native-agent-stack: named here, never committed or hashed.
MCP_LEDGER = "research/coverage-gap-20261008/landscape-mcp/full-list-coverage.tsv"
GENERIC_LEDGER = "research/coverage-gap-20261008/landscape-stars/generic/coverage-ledger.tsv"
# NON-GITHUB (the CC's ruling of 2026-10-16 on named candidates): a named candidate whose link is not a GitHub
# repository and that the G5 list screen matched to layers. Step 3's readers rank GitHub repositories, so it stays
# outside LAYER-CANDIDATE, with its layers kept.
DISPOSITIONS = ("LAYER-CANDIDATE", "OUT-OF-SCOPE", "DUPLICATE", "RETIRED", "UNMAPPED", "NON-GITHUB")
STATES = ("CARRIED", "PROPOSED", "UNSCREENED")
CARRIED_POPULATIONS = ("grand", "master-seeds", "stars", "starred-seeds", "final-stack")
# C-4 of the approved step-1 plan: two starred repositories are lists by topic without "awesome" in the name.
LIST_TYPE_STARS = ("ripienaar/free-for-dev", "f/prompts.chat")
NO_LAYER_MATCH = "No committed layer capability matched"  # screen_generic.py:180, step 2's second input
GENERIC_PARSER = "screen_generic.py@"  # the list_populations parser label that names this module's original
PASS_RECORD = DISPATCH + ":247"  # the run-written record the dispatch adapter reads
PASS_ASSERTION = DISPATCH + ":277-283"  # the qualification check that asserts on it
# The commit that added the parser's recorded hash (git blame: line 340 at that commit is line 340 now).
PARSER_ANCHOR = ("native-agent-stack/native-agent-stack@c8a29c3ee9b4337564165d9e588b3fe81e8ba817:"
                 "catalogs/landscape/grand-catalog-20261008.json:340")
GITHUB_HOSTS = ("github.com", "www.github.com", "raw.githubusercontent.com")  # screen_generic.py:103 and :313
# screen_generic.py:287 and :314: badge, image and sponsor links, ignored there and here.
NOISE_HOSTS = {"img.shields.io", "shields.io", "badge.fury.io", "badgen.net", "ko-fi.com", "patreon.com",
               "opencollective.com", "buymeacoffee.com"}
IMAGE_PATH = re.compile(r"\.(?:png|jpe?g|gif|webp|svg)(?:\?|$)", re.I)
HTTP_URL = re.compile(r"https?://[^\s<>\"'`)\]|]+", re.I)
UNMAPPED_REASONS = {
    "repository": "Cited by a research run or PR output, and no other population maps it (a step-2 input).",
    "url": "Named by its non-GitHub URL in a research run or PR output, and no other population maps it "
           "(a step-2 input).",
}
# Withheld from the public runs index, each for privacy (the CC's ruling: only privacy or licence may withhold).
WITHHELD_REASONS = {
    "pi_claude_topics": "a briefed role run's answer heading can restate its brief, which may carry the owner's "
                        "direction, and no owner quote may be published",
    "pi_claude_first_user_turns": "the first user turn is the free-text brief itself; it was not read",
    "ddgs_frozen_queries": "the frozen queries are free text written for the run",
}
NON_GITHUB_REASON = ("Named candidate whose link is not a GitHub repository; the G5 list screen matched it to the "
                     "layers listed. Step 3's readers rank GitHub repositories, so it stays outside LAYER-CANDIDATE "
                     "until a reader for its host exists.")
# The nested DeerFlow test copies the plan names, as exact patterns so no per-run home/ tree is walked.
NESTED_DEERFLOW = ("client-checks/run.*/claude-state/native-agent-stack/research/deer-flow/run.*",
                   "wave-20261010/breadth/research-runtime/state/native-agent-stack/research/deer-flow/run.*")
# A github.com or raw.githubusercontent.com URL (the hosts screen_generic.repo_from accepts), not a subdomain such as
# api.github.com or gist.github.com.
GITHUB_URL = re.compile(r"(?<![\w.-])(?:https?://)?(?:(?:www\.)?github\.com|raw\.githubusercontent\.com)/"
                        r"[^\s<>\"'`)\]|]+", re.I)
HOME = re.compile(r"/home/[^/]+/")


class LedgerError(ValueError):
    pass


# --------------------------------------------------------------------------- identities


def slug(value) -> str | None:
    """owner/repo, lowercased, from a GitHub URL or an 'owner/repo[@ref]' entry; None for anything else. This is
    the identity rule behind the approved plan's counts (2,925 backlog slugs and 58 non-repository entries)."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    match = re.match(r"^(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:[/#?].*)?$",
                     text)
    if match is None:
        match = re.match(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:@.*)?$", text)
    return (match.group(1) + "/" + match.group(2)).lower() if match else None


def identity_of(value: str) -> str:
    """A repository's slug, or entry:<literal> for a recorded entry that names no GitHub repository."""
    return slug(value) or "entry:" + value


def master_seed_identity(item: str, grand_rows: list) -> str | None:
    """A master seed's identity is its leading token (owner/repo or a GitHub URL, any @pin removed), or the
    grand-catalog entry it points to (source=catalogs/landscape/grand-catalog-20261008.json#/rows/N)."""
    head = item.split(";", 1)[0].strip()
    found = slug(re.sub(r"@[^/\s]*$", "", head))
    if found:
        return found
    pointer = re.search(r"source=" + re.escape(GRAND) + r"#/rows/(\d+)", item)
    if pointer and int(pointer.group(1)) < len(grand_rows):
        return identity_of(grand_rows[int(pointer.group(1))]["repository_or_entry"])
    return None


def cited_repositories(text: str, repo_from) -> set[str]:
    """Every github.com owner/repo a text cites, through screen_generic.repo_from (its NONREPO and suffix rules)."""
    found = set()
    for match in GITHUB_URL.finditer(text):
        url = match.group(0)
        if not url.lower().startswith("http"):
            url = "https://" + url
        try:
            repository = repo_from(url)
        except ValueError:  # urlsplit refuses a truncated bracketed host
            continue
        if repository:
            found.add(repository.lower())
    return found


def public_host(host: str) -> bool:
    """A public DNS name: not localhost, an IP literal, a dotless name or a private suffix."""
    if not host or "." not in host or host.endswith((".local", ".internal", ".lan", ".localhost", ".home.arpa")):
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return True
    return False


# The repository's private-content patterns (scripts/validate.py PRIVATE_CONTENT, which validate.py applies to every
# hash-listed file); build() loads them, and canonical_url replaces a matching path segment with a placeholder.
PRIVACY = {"patterns": [], "redacted": {}}
PLACEHOLDERS = {"local session identifier": "<uuid>"}


def load_private_patterns(repo_root: Path) -> list:
    spec = importlib.util.spec_from_file_location("landscape_validate_patterns", repo_root / "scripts" / "validate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.PRIVATE_CONTENT)


def privacy_safe(url: str) -> str:
    """The URL with each private-content match replaced (a UUID by <uuid>, a home directory by <user>); each
    redacted URL is counted under its pattern's description."""
    safe = url
    for description, pattern in PRIVACY["patterns"]:
        if pattern.search(safe):
            def placeholder(match, description=description):
                text = match.group(0)
                home = re.match(r"(/(?:home|Users)/)[^/]*(/?)$", text)
                return home.group(1) + "<user>" + home.group(2) if home else PLACEHOLDERS.get(description, "<redacted>")
            safe = pattern.sub(placeholder, safe)
            PRIVACY["redacted"].setdefault(description, set()).add(url)
    return safe


def canonical_url(value: str) -> str | None:
    """https, lowercase host without www., no userinfo, port, query or fragment, no trailing slash, and no path
    segment that matches the repository's private-content patterns. None for a link that is not a public http(s)
    URL."""
    try:
        parts = urlsplit(value.strip("<> "))
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not host:
        return None
    host = host.lower()
    host = host[4:] if host.startswith("www.") else host
    if not public_host(host):
        return None
    path = "/".join(segment for segment in parts.path.split("/") if segment)
    return privacy_safe("https://" + host + ("/" + path if path else ""))


def cited_urls(text: str) -> set[str]:
    """Canonical URLs of every non-GitHub http(s) link a text cites, without screen_generic's badge, image and
    sponsor links: the named candidates that have no GitHub URL."""
    found = set()
    for match in HTTP_URL.finditer(text):
        target = match.group(0).rstrip(".,;:")
        try:
            host = (urlsplit(target).hostname or "").lower()
        except ValueError:
            continue
        if host in GITHUB_HOSTS or host in NOISE_HOSTS or IMAGE_PATH.search(urlsplit(target).path):
            continue
        canonical = canonical_url(target)
        if canonical:
            found.add(canonical)
    return found


def redact(text: str) -> str:
    return HOME.sub("/home/<user>/", text)


def pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


# --------------------------------------------------------------------------- reading


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv(path: Path) -> list[dict]:
    csv.field_size_limit(1_000_000_000)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def final_stack_projection(document: dict) -> dict:
    """The part of final-stack.json the ledger reads. final_stack.py reads the ledger back into its intake, so the
    ledger binds this projection, not the whole file (a whole-file hash would invalidate each check in turn)."""
    return {"index": document["index"]["by_repository"],
            "layers": sorted(layer["layer_id"] for layer in document["layers"]),
            "skills": sorted(row["layer_id"] for row in document["coverage"]["skills"])}


def git(directory: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(directory), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def blob_info(directory: Path, paths: list[str]) -> dict[str, tuple[str, int]]:
    """(sha256, bytes) of each path's blob at HEAD (a symlink is its link text, as the G5 captures hashed it)."""
    process = subprocess.Popen(["git", "-C", str(directory), "cat-file", "--batch"], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE)
    out = {}
    try:
        for path in paths:
            process.stdin.write(f"HEAD:{path}\n".encode())
            process.stdin.flush()
            header = process.stdout.readline().decode().split()
            if len(header) < 3 or header[1] != "blob":
                raise LedgerError(f"{directory.name}: no blob for {path}")
            size = int(header[2])
            data = process.stdout.read(size)
            process.stdout.read(1)
            out[path] = (sha256_bytes(data), size)
    finally:
        process.stdin.close()
        process.wait()
    return out


def load_screen_generic():
    spec = importlib.util.spec_from_file_location("screen_generic", SCREEN_GENERIC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- lists


def list_universe(repo_root: Path, state: Path) -> dict[str, dict]:
    """Every list repository with its populations and recorded pins, from the committed records and the retained
    MCP ledger. Keys are lowercase owner/repo."""
    lists: dict[str, dict] = {}

    def add(repository, population, pin=None, date=None, record=None):
        entry = lists.setdefault(repository.lower(), {"repository": repository, "populations": [], "recorded": []})
        if population not in entry["populations"]:
            entry["populations"].append(population)
        if pin and not any(item["commit"] == pin and item["population"] == population for item in entry["recorded"]):
            entry["recorded"].append({"population": population, "commit": pin, "commit_date": date, "record": record})

    accounting = load_json(repo_root / COVERAGE_ACCOUNTING)
    for index, source in enumerate(accounting["list_sources"]):
        add(source["repository"], "coverage-accounting", source["commit"], source["commit_date"],
            f"{COVERAGE_ACCOUNTING}#/list_sources/{index}")
    grand = load_json(repo_root / GRAND)
    for item in grand["coverage"]["list_populations"]:
        add(item["source_repository"], "grand-list-populations", item["pin"]["version_or_commit"], None,
            f"{GRAND}#/coverage/list_populations")
    for row in read_tsv(state / MCP_LEDGER):
        add(row["source_repository"], "mcp-lane", row["source_pin"], None, "retained:" + MCP_LEDGER)
    for star in load_json(repo_root / STARS)["repositories"]:
        name = star["repository"]
        if "awesome" in name.lower() or name.lower() in LIST_TYPE_STARS:
            add(name, "starred")
    return dict(sorted(lists.items()))


def index_clones(directories: list[Path]) -> dict:
    """(lowercase owner/repo, commit) -> clone path, and lowercase owner/repo -> [clone paths]."""
    by_pin, by_repo = {}, collections.defaultdict(list)
    for base in directories:
        for clone in sorted(base.iterdir()):
            if not (clone / ".git").exists():
                continue
            repository = clone.name.replace("__", "/", 1)
            by_pin[(repository.lower(), git(clone, "rev-parse", "HEAD"))] = clone
            by_repo[repository.lower()].append(clone)
    return {"by_pin": by_pin, "by_repo": by_repo}


def extract_clone(sg, clone: Path, selected: dict):
    """screen_generic.extract() and external_resources() on one clone. The module's own run() sets the csv field
    limit before extract (screen_generic.py:330); a caller sets BASE and REPOS (lines 20 and 25)."""
    repository = clone.name.replace("__", "/", 1)
    csv.field_size_limit(8_000_000)
    sg.BASE, sg.REPOS = clone.parent, [repository]
    summary, rows = sg.extract(repository, selected, [])
    try:
        external, ignored = sg.external_resources(selected, [])
    except ValueError:
        # urlsplit at screen_generic.py:311 refuses a truncated bracketed host ("http://[::1") and the whole pass
        # stops. Retry with a urlsplit that maps only such a refusal to an empty result, which the next line already
        # skips (screen_generic.py:312, a scheme that is not http or https); every other target is unchanged.
        refused, original = [], sg.urlsplit

        def tolerant(url, *args, **kwargs):
            try:
                return original(url, *args, **kwargs)
            except ValueError:
                refused.append(url)
                return original("")

        sg.urlsplit = tolerant
        try:
            external, ignored = sg.external_resources(selected, [])
        finally:
            sg.urlsplit = original
        ignored = {**ignored, "urlsplit-refused-targets": len(refused)}
    return repository, summary, rows, external, ignored


def file_table(clone: Path, summary: dict, rows: list, external: list | None) -> tuple[list[dict], dict]:
    """The scanned documents with at least one entry, and a hash over the whole scanned inventory."""
    github = collections.Counter(row["path"] for row in rows)
    outside = collections.Counter(row["path"] for row in external or [])
    paths = [item["path"] for item in summary["inventory_files"]]
    hashes = {path: info[0] for path, info in blob_info(clone, paths).items()}
    inventory = {"document_files": len(paths),
                 "sha256": sha256_bytes("".join(f"{path}\t{hashes[path]}\n" for path in sorted(paths)).encode()),
                 "unit": "sha256 of sorted '<path>\\t<blob sha256>\\n' lines over every scanned document"}
    files = [{"path": path, "blob_sha256": hashes[path], "github_entries": github.get(path, 0),
              "external_entries": None if external is None else outside.get(path, 0)}
             for path in paths if github.get(path) or outside.get(path)]
    return files, inventory


def group_list_occurrences(items: list[dict]) -> dict:
    """One identity's list occurrences, grouped by screen_generic run()'s own rule (screen_generic.py:340-353): the
    relevant occurrences (not OUT-OF-SCOPE, with a layer or an incumbent) decide, and a real capability entry
    outranks a prompt-embedded reference or a discovery pointer. Lifecycle matches are kept as hints only: the
    module retains them separately and never lets them alone promote an entry (screen_generic.py:160-161)."""
    priority = {"NO-GAP": 0, "WATCH": 1, "REJECT": 2, "OUT-OF-SCOPE": 3}
    relevant = [item for item in items if item["disposition"] != "OUT-OF-SCOPE"
                and (item["layer_ids"] or item["incumbent_ids"])]
    if relevant:
        real = [item for item in relevant if not (item["kind"] == "prompt-embedded-reference" or (
            item["disposition"] == "NO-GAP" and not item["incumbent_ids"]))]
        chosen = min(real or relevant, key=lambda item: priority[item["disposition"]])
        return {"relevant": True, "disposition": chosen["disposition"],
                "layers": sorted({layer for item in relevant for layer in item["layer_ids"]}),
                "lifecycle": sorted({field for item in relevant for field in item["lifecycle"]}), "reason": None}
    reasons = collections.Counter(item["reason"] for item in items)
    return {"relevant": False, "disposition": "OUT-OF-SCOPE", "layers": [], "lifecycle": [],
            "reason": sorted(reasons.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]}


def occurrence(list_name: str, commit: str, row: dict) -> dict:
    """One extracted list entry (a GitHub row of extract() or an external row of external_resources())."""
    return {"list": list_name, "commit": commit, "path": row["path"], "line": row["line"], "section": row["section"],
            "disposition": row["disposition"], "layer_ids": row["layer_ids"], "lifecycle": row["lifecycle_fields"],
            "incumbent_ids": row["incumbent_ids"], "kind": row["kind"], "reason": row["reason"]}


def list_ref(item: dict, pins: dict) -> str:
    """<list>:<path>:<line> at the list's pin in the list table, or <list>@<commit>:<path>:<line> at another pin."""
    at = "" if pins.get(item["list"]) == item["commit"] else "@" + item["commit"]
    return f"{item['list']}{at}:{item['path']}:{item['line']}"


def build_lists(repo_root: Path, state: Path, clones: dict, sg, selected: dict, checked_at: str):
    """The pinned list table, the per-identity list occurrences and the reconciliation with every recorded census."""
    universe = list_universe(repo_root, state)
    accounting = load_json(repo_root / COVERAGE_ACCOUNTING)
    grand = load_json(repo_root / GRAND)
    populations = collections.defaultdict(list)
    for item in grand["coverage"]["list_populations"]:
        populations[item["source_repository"].lower()].append(item)
    mcp_rows = collections.defaultdict(list)
    for row in read_tsv(state / MCP_LEDGER):
        mcp_rows[row["source_repository"].lower()].append(row)
    cache: dict = {}

    def extraction(key, commit):
        clone = clones["by_pin"].get((key, commit))
        if clone is None:
            raise LedgerError(f"{key}: no clone at recorded pin {commit}")
        if (key, commit) not in cache:
            repository, summary, rows, external, ignored = extract_clone(sg, clone, selected)
            cache[(key, commit)] = {"clone": clone, "repository": repository, "summary": summary, "rows": rows,
                                    "external": external, "ignored": ignored,
                                    "date": git(clone, "show", "-s", "--format=%cI", "HEAD")}
        return cache[(key, commit)]

    table, occurrences, url_occurrences = [], collections.defaultdict(list), collections.defaultdict(list)
    accounting_union, accounting_rows = set(), []
    for key, entry in universe.items():
        recorded = entry["recorded"]
        if recorded:
            dated = [(extraction(key, item["commit"])["date"], item["commit"]) for item in recorded]
            pin_date, pin = max(dated)
            pin_rule = "newest recorded pin (Q1-2 default)" if len({c for _, c in dated}) > 1 else "recorded pin"
        else:
            candidates = clones["by_repo"].get(key, [])
            if len(candidates) != 1:
                raise LedgerError(f"{key}: expected one clone at the fetched default-branch head, found {len(candidates)}")
            pin = git(candidates[0], "rev-parse", "HEAD")
            pin_date = extraction(key, pin)["date"]
            pin_rule = f"no recorded pin; default-branch head fetched for this ledger on {checked_at[:10]}"
        main = extraction(key, pin)
        # Across every pin read: the list's pin and its recorded pins (each under a "commit" key in the table).
        seeded = {"github": 0, "external": 0, "external_not_public": 0}
        for commit in sorted({pin} | {item["commit"] for item in recorded}):
            data = extraction(key, commit)
            for row in data["rows"]:
                occurrences[row["repository"].lower()].append(occurrence(data["repository"], commit, row))
                seeded["github"] += 1
            for row in data["external"] or []:
                canonical = canonical_url(row["target"])
                if canonical is None:  # an IP literal, localhost or a private suffix: no named public candidate
                    seeded["external_not_public"] += 1
                    continue
                url_occurrences[canonical].append(occurrence(data["repository"], commit, row))
                seeded["external"] += 1
        census = []
        for index, source in enumerate(accounting["list_sources"]):
            if source["repository"].lower() != key:
                continue
            data = extraction(key, source["commit"])
            readme = source["readme_path"]
            raw_hash, raw_bytes = blob_info(data["clone"], [readme])[readme]
            ids = {row["repository"].lower() for row in data["rows"] if row["path"] == readme}
            accounting_union |= ids
            delta = len(ids) - source["github_identity_links"]
            cause = None
            if delta and not re.search(r"\.(?:md|mdx|rst)$", readme, re.I):
                cause = f"{readme} is outside screen_generic's .md/.mdx/.rst document set (screen_generic.py:150)"
            elif delta:
                cause = ("identity normalization differs from the 2026-09-19 extractor, whose identities were never "
                         "committed; not attributable per identity")
            census.append({"record": f"{COVERAGE_ACCOUNTING}#/list_sources/{index}", "commit": source["commit"],
                           "unit": f"unique GitHub owner/repo identities linked from {readme}",
                           "file_sha256": raw_hash, "file_bytes": raw_bytes,
                           "file_matches_record": raw_hash == source["readme_sha256"] and raw_bytes == source["readme_bytes"],
                           "recorded": source["github_identity_links"], "reextracted": len(ids), "delta": delta,
                           "cause": cause})
            accounting_rows.append((source["repository"], delta))
        if key in populations:
            items = populations[key]
            data = extraction(key, items[0]["pin"]["version_or_commit"])
            if data["external"] is None:
                raise LedgerError(f"{key}: external_resources failed at a recorded census pin: {data['ignored']}")
            got = collections.Counter(r["path"] for r in data["rows"]) + collections.Counter(
                r["path"] for r in data["external"])
            hashes = {path: info[0] for path, info in blob_info(data["clone"], [i["path"] for i in items]).items()}
            parser = items[0]["parser"].split(";")[0]
            recorded_total = sum(item["counted"]["physical_entries"] for item in items)
            files = [{"path": item["path"], "capture_sha256": item["capture_sha256"],
                      "blob_matches_capture": hashes[item["path"]] == item["capture_sha256"],
                      "recorded": item["counted"]["physical_entries"], "reextracted": got.get(item["path"], 0)}
                     for item in items]
            reextracted = sum(file["reextracted"] for file in files)
            census.append({"record": f"{GRAND}#/coverage/list_populations", "commit": items[0]["pin"]["version_or_commit"],
                           "unit": "physical entries per file (extract GitHub rows plus external_resources rows)",
                           "recorded_parser": parser, "files": files, "recorded": recorded_total,
                           "reextracted": reextracted, "delta": reextracted - recorded_total,
                           "cause": None if parser.startswith(GENERIC_PARSER)
                           else f"recorded census parser is not screen_generic: {parser}",
                           "extra_files_with_entries": sorted(set(got) - {item["path"] for item in items})})
        if key in mcp_rows:
            rows = mcp_rows[key]
            data = extraction(key, rows[0]["source_pin"])
            recorded_ids = {row["repository"].lower() for row in rows if row["repository"]}
            ids = {row["repository"].lower() for row in data["rows"]}
            census.append({"record": "retained:" + MCP_LEDGER, "commit": rows[0]["source_pin"],
                           "unit": "distinct GitHub owner/repo identities", "recorded_rows": len(rows),
                           "recorded": len(recorded_ids), "reextracted": len(ids), "delta": len(ids) - len(recorded_ids),
                           "shared": len(ids & recorded_ids),
                           "cause": "recorded census parser is not screen_generic: the MCP lane's list-entry and "
                                    "translation-alias screens"})
        summary = main["summary"]
        files, inventory = file_table(main["clone"], summary, main["rows"], main["external"])
        table.append({
            "repository": main["repository"], "populations": sorted(entry["populations"]),
            "pin": {"commit": pin, "commit_date": pin_date, "rule": pin_rule},
            "recorded_pins": sorted(recorded, key=lambda item: (item["population"], item["commit"])),
            "shallow": summary["shallow"] == "true", "inventory": inventory,
            "extraction": {"entries": summary["entries_extracted"],
                           "external_entries": None if main["external"] is None else len(main["external"]),
                           "physical_entries": None if main["external"] is None
                           else summary["entries_extracted"] + len(main["external"]),
                           "unique_repositories": summary["unique_repository_links"],
                           "counts_by_disposition": dict(sorted(summary["counts_by_disposition"].items())),
                           "ignored": dict(sorted(main["ignored"].items()))},
            "seeded_occurrences": seeded, "files": files, "census": census})
    accounting_summary = {
        "lists": len(accounting["list_sources"]),
        "recorded_unique": accounting["counts"]["unique_extracted_github_identities"],
        "recorded_unassessed": accounting["counts"]["discovery_only_unassessed"],
        "recorded_checked_at": accounting["checked_at_utc"],
        "recorded_sum_of_lists": sum(s["github_identity_links"] for s in accounting["list_sources"]),
        "reextracted_union": len(accounting_union),
        "delta": len(accounting_union) - accounting["counts"]["unique_extracted_github_identities"],
        "lists_with_delta": {name: delta for name, delta in sorted(accounting_rows) if delta}}
    return table, occurrences, url_occurrences, accounting_summary


def generic_comparison(occurrences: dict, retained: list[dict], generic_lists: set[str]) -> dict:
    """The retained G5 generic ledger against this module's grouping of the same 14 lists' occurrences."""
    derived = {}
    for identity, items in occurrences.items():
        scoped = [item for item in items if item["list"].lower() in generic_lists]
        mapping = group_list_occurrences(scoped) if scoped else None
        if mapping and mapping["relevant"]:
            derived[identity] = mapping
    recorded = {row["repository"].lower(): row for row in retained}
    same_layers = {key for key, row in recorded.items() if key in derived
                   and derived[key]["layers"] == sorted(filter(None, row["layer_ids"].split(",")))}
    return {"record": "retained:" + GENERIC_LEDGER, "recorded": len(recorded), "rederived": len(derived),
            "shared": len(set(recorded) & set(derived)),
            "same_disposition": sum(1 for key, row in recorded.items()
                                    if key in derived and derived[key]["disposition"] == row["disposition"]),
            "same_layer_ids": len(same_layers),
            "layer_ids_differ_with_candidate_pin": sum(1 for key, row in recorded.items() if key in derived
                                                       and key not in same_layers and row["candidate_pin"] != "UNVERIFIED"),
            "layer_ids_note": "run() adds the native survivor review's layers for its reviewed candidates "
                              "(screen_generic.py:358-366); this ledger does not read that review"}


# --------------------------------------------------------------------------- research runs


def first_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            if heading:
                return heading[:200]
    return None


def utc_from_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")


def passes_dispatch_assertion(metadata: dict | None, answer_text: str) -> bool | None:
    """The predicate of tools/research/dispatch:277-283 on the run-written native-retrieval-metadata.json."""
    if metadata is None:
        return None
    matches = metadata.get("cited_retrieved_url_matches")
    return (metadata.get("integration_assertion_pass") is True and type(matches) is int and matches >= 1
            and bool(answer_text.strip()))


def database_tables(run: Path, scratch: Path) -> dict:
    """Copy deerflow.db with its -wal and -shm files, verify each copy's sha256, read only sqlite_master names and,
    where a runs table exists, its named run columns; then delete the copy. The original is never opened."""
    source = run / ".deer-flow" / "data" / "deerflow.db"
    if not source.is_file():
        return {"copied": 0, "tables": [], "runs": []}
    copy_dir = scratch / ("copy-" + run.name)
    copy_dir.mkdir(parents=True)
    try:
        copied = 0
        for suffix in ("", "-wal", "-shm"):
            original = Path(str(source) + suffix)
            if original.exists():
                target = copy_dir / ("deerflow.db" + suffix)
                shutil.copy2(original, target)
                if file_sha256(original) != file_sha256(target):
                    raise LedgerError(f"{run.name}: database copy differs from its source")
                copied += 1
        connection = sqlite3.connect(f"file:{copy_dir / 'deerflow.db'}?mode=ro", uri=True)
        try:
            tables = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
            runs = []
            if "runs" in tables:
                runs = [{"status": row[0], "model_name": row[1], "created_at": row[2]} for row in connection.execute(
                    "SELECT status, model_name, created_at FROM runs ORDER BY created_at")]
        finally:
            connection.close()
    finally:
        shutil.rmtree(copy_dir)
    return {"copied": copied, "tables": tables, "runs": runs}


def dispatch_receipts(state: Path) -> tuple[dict, list[dict]]:
    """Dispatch receipts by the DeerFlow run directory they name, and the exact-query (DDGS) receipts."""
    by_run, exact = {}, []
    for path in sorted((state / "research" / "dispatch").glob("run.*/dispatch.json")):
        receipt = load_json(path)
        record = {"path": redact(str(path)), "status": receipt.get("status"),
                  "started_at_utc": receipt.get("started_at_utc"), "directory": path.parent}
        if receipt.get("mode") == "exact_queries_ddgs":
            exact.append(record)
        directory = receipt.get("native_run_directory")
        if isinstance(directory, str) and directory:
            by_run[Path(directory).name] = record
    return by_run, exact


def run_row(**fields) -> dict:
    row = {"run_id": None, "runtime": None, "runtime_version": None, "runtime_version_source": None,
           "location": None, "source_path": None, "profile": None, "model": None, "model_source": None,
           "date": None, "date_source": None, "topic": None, "topic_source": None, "question_text": None,
           "question_status": None, "database": None, "pass_flag": "UNVERIFIED", "pass_record": None,
           "receipt": None, "seeds": [], "named_urls": []}
    row.update(fields)
    return row


def deerflow_runs(state: Path, scratch: Path, receipts: dict, repo_from) -> list[dict]:
    base = state / "research"
    found = {path.name: path for path in sorted((base / "deer-flow").glob("run.*"))}
    nested = []
    for pattern in NESTED_DEERFLOW:
        for path in sorted(base.glob(pattern)):
            if path.name not in found and (path / ".deer-flow").is_dir():
                nested.append(path)
                found[path.name] = path
    out = []
    for name, run in sorted(found.items()):
        answer_path = run / "answer.md"
        answer = answer_path.read_text(encoding="utf-8", errors="replace") if answer_path.is_file() else ""
        metadata_path = run / "native-retrieval-metadata.json"
        metadata = load_json(metadata_path) if metadata_path.is_file() else None
        runtime_readback = run / "qualification-runtime-readback.json"
        version = load_json(runtime_readback).get("deerflow-harness") if runtime_readback.is_file() else None
        config_readback = run / "qualification-config-readback.json"
        model = load_json(config_readback).get("model_name") if config_readback.is_file() else None
        database = database_tables(run, scratch)
        receipt = receipts.get(name)
        passed = passes_dispatch_assertion(metadata, answer)
        db_model = database["runs"][0]["model_name"] if database["runs"] else None
        out.append(run_row(
            run_id=name, runtime="deer-flow", runtime_version=version if isinstance(version, str) else None,
            runtime_version_source="qualification-runtime-readback.json deerflow-harness" if isinstance(version, str)
            else None,
            location="nested test copy" if run in nested else "research/deer-flow", source_path=redact(str(run)),
            model=db_model or (model if isinstance(model, str) else None),
            model_source="runs.model_name" if db_model else (
                "qualification-config-readback.json model_name (a readback; metadata only)"
                if isinstance(model, str) else None),
            date=receipt["started_at_utc"] if receipt else (utc_from_mtime(answer_path) if answer else None),
            date_source="dispatch receipt started_at_utc" if receipt else ("answer.md mtime" if answer else None),
            topic=first_heading(answer), topic_source="answer.md first heading (the plan's fallback 2)",
            question_status=("not recorded: the run database holds no runs table (tables: "
                             + (", ".join(database["tables"]) or "none") + "), producer.stdout carries the answer, "
                             "and the receipt holds only the question's hash"),
            database={"copied_files": database["copied"], "tables": database["tables"]},
            pass_flag="UNVERIFIED" if passed is None else passed,
            pass_record=None if metadata is None else {
                "path": "native-retrieval-metadata.json", "read_at": PASS_RECORD, "assertion": PASS_ASSERTION,
                "integration_assertion_pass": metadata.get("integration_assertion_pass"),
                "cited_retrieved_url_matches": metadata.get("cited_retrieved_url_matches"),
                "answer_nonempty": bool(answer.strip())},
            receipt=None if receipt is None else {"path": receipt["path"], "status": receipt["status"]},
            seeds=sorted(cited_repositories(answer, repo_from)), named_urls=sorted(cited_urls(answer))))
    return out


def gptr_version(checkout: Path | None) -> dict | None:
    """The installed GPT Researcher checkout's release tag and commit (runs record no version of their own)."""
    if checkout is None or not (checkout / ".git").exists():
        return None
    return {"tag": git(checkout, "describe", "--tags"), "commit": git(checkout, "rev-parse", "HEAD")}


def gptr_runs(state_root: Path, repo_from, version: dict | None) -> list[dict]:
    allow = ("FAST_LLM", "SMART_LLM", "STRATEGIC_LLM", "RETRIEVER", "REPORT_SOURCE")  # model and retriever settings
    out = []
    for run in sorted((state_root / "new-wsl-native-stack" / "research" / "gptr").glob("*/")):
        config = load_json(run / "config.json") if (run / "config.json").is_file() else {}
        reports = sorted((run / "outputs").glob("*.md")) if (run / "outputs").is_dir() else []
        text = "\n".join(report.read_text(encoding="utf-8", errors="replace") for report in reports)
        stamp = re.match(r"(\d{8}T\d{6}Z)-", run.name)
        out.append(run_row(
            run_id=run.name, runtime="gpt-researcher", runtime_version=(version or {}).get("tag"),
            runtime_version_source=("installed checkout tag at " + version["commit"]
                                    + "; the run records no version") if version else None,
            location="new-wsl-native-stack/research/gptr", source_path=redact(str(run).rstrip("/")),
            model={key: config.get(key) for key in allow if isinstance(config.get(key), str)},
            model_source="config.json allowlisted fields " + ", ".join(allow),
            date=(datetime.strptime(stamp.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                  .isoformat().replace("+00:00", "Z")) if stamp else None,
            date_source="run directory name" if stamp else None,
            topic=first_heading(text) if text else None, topic_source="report title (first heading)",
            question_status="not recorded: config.json carries no question; its allowlisted fields are settings",
            reports=len(reports), seeds=sorted(cited_repositories(text, repo_from)),
            named_urls=sorted(cited_urls(text))))
    return out


def pi_claude_runs(state: Path, repo_from) -> list[dict]:
    out = []
    for run in sorted((state / "runtime-profiles").glob("w6-*/pi-claude/roles/researcher/runs/*")):
        if not run.is_dir():
            continue
        receipt = load_json(run / "receipt.json") if (run / "receipt.json").is_file() else None
        texts, models, started = [], set(), None
        with (run / "events.jsonl").open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("type") == "session" and started is None:
                    started = event.get("timestamp")
                message = event.get("message")
                if event.get("type") == "message_end" and isinstance(message, dict) and message.get("role") == "assistant":
                    if isinstance(message.get("model"), str):
                        models.add(message["model"])
                    for block in message.get("content") or []:
                        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                            texts.append(block["text"])
        text = "\n".join(texts)
        profile = run.parts[run.parts.index("runtime-profiles") + 1]
        model = (receipt or {}).get("model")
        out.append(run_row(
            run_id=run.name, runtime="pi-claude-researcher", location=f"runtime-profiles/{profile}",
            source_path=redact(str(run)), profile=profile,
            model=model or (sorted(models)[0] if len(models) == 1 else None),
            model_source="receipt.json model" if model else ("assistant message model" if len(models) == 1 else None),
            date=(receipt or {}).get("started_at") or started,
            date_source="receipt.json started_at" if receipt else ("session event timestamp" if started else None),
            topic_source="withheld (privacy): " + WITHHELD_REASONS["pi_claude_topics"],
            topic_withheld=first_heading(text) is not None,
            question_status="withheld (privacy): " + WITHHELD_REASONS["pi_claude_first_user_turns"],
            receipt=None if receipt is None else {"path": "receipt.json", "status": receipt.get("status")},
            seeds=sorted(cited_repositories(text, repo_from)), named_urls=sorted(cited_urls(text))))
    return out


def exact_query_runs(exact: list[dict], repo_from) -> list[dict]:
    out = []
    for record in exact:
        directory = record["directory"]
        captures = sorted(directory.glob("*-search.json")) + sorted(directory.glob("*-source-*.json"))
        text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in captures)
        out.append(run_row(
            run_id=directory.name, runtime="ddgs-exact-query", location="research/dispatch",
            source_path=redact(str(directory)), model_source="none: the exact-query route makes no model call",
            date=record["started_at_utc"], date_source="receipt started_at_utc",
            question_status="withheld (privacy): " + WITHHELD_REASONS["ddgs_frozen_queries"],
            receipt={"path": record["path"], "status": record["status"]},
            seeds=sorted(cited_repositories(text, repo_from)), named_urls=sorted(cited_urls(text))))
    return out


def withheld_record(runs: list[dict]) -> dict:
    """What the runs index withholds, with each count and its reason (the CC's ruling: privacy or licence only)."""
    pi = [run for run in runs if run["runtime"] == "pi-claude-researcher"]
    ddgs = [run for run in runs if run["runtime"] == "ddgs-exact-query"]
    return {"reasons_allowed": ["privacy", "licence"], "withheld_for_licence": 0, "items": [
        {"field": "topic", "runtime": "pi-claude-researcher", "withheld": sum(1 for run in pi if run["topic_withheld"]),
         "runs": len(pi), "reason": "privacy", "detail": WITHHELD_REASONS["pi_claude_topics"]},
        {"field": "question_text", "runtime": "pi-claude-researcher", "withheld": len(pi), "runs": len(pi),
         "reason": "privacy", "detail": WITHHELD_REASONS["pi_claude_first_user_turns"]},
        {"field": "question_text", "runtime": "ddgs-exact-query", "withheld": len(ddgs), "runs": len(ddgs),
         "reason": "privacy", "detail": WITHHELD_REASONS["ddgs_frozen_queries"]}]}


def research_join(identities: set[str], populations_of: dict, installed: set[str]) -> tuple[dict, list[str]]:
    """Each research seed's first bucket: installed (manifests/stack.json), catalog (a committed record holds it),
    lists (only a list holds it) or new. New code; its buckets follow the earlier audit joins' shape."""
    buckets, new = collections.Counter(), []
    for identity in sorted(identities):
        populations = set(populations_of.get(identity, ())) - {"runs", "pr-outputs"}
        bucket = ("installed" if identity in installed else "catalog" if populations & set(CARRIED_POPULATIONS)
                  else "lists" if populations else "new")
        buckets[bucket] += 1
        if bucket == "new":
            new.append(identity)
    return dict(sorted(buckets.items())), new


def pr_outputs(directory: Path, repo_from) -> list[dict]:
    """Text records the plan's open PRs (#1177, #1181, #1182, #1183) add or change, read at each pinned head."""
    manifest = load_json(directory / "manifest.json")
    out = []
    for pr in manifest["prs"]:
        seeds, urls, files = set(), set(), []
        for relative in pr["files"]:
            text = (directory / f"pr-{pr['number']}" / relative).read_text(encoding="utf-8", errors="replace")
            found, named = cited_repositories(text, repo_from), cited_urls(text)
            seeds |= found
            urls |= named
            files.append({"path": relative, "seeds": len(found), "named_urls": len(named)})
        out.append({"number": pr["number"], "head_sha": pr["head_sha"], "title": pr["title"], "state": pr["state"],
                    "files": files, "seeds": sorted(seeds), "named_urls": sorted(urls)})
    return out


# --------------------------------------------------------------------------- ledger


class Seeds:
    """Every seed with the mappings its populations record; decide() turns them into exactly one disposition."""

    def __init__(self):
        self.rows: dict[str, dict] = {}

    def seed(self, identity: str) -> dict:
        return self.rows.setdefault(identity, {"populations": {}, "mappings": [], "existing": {}, "runs": [],
                                               "lifecycle": set(), "cluster": None, "aliases": []})

    def source(self, identity: str, population: str, ref: str | None):
        entry = self.seed(identity)["populations"].setdefault(population, [0, ref])
        entry[0] += 1

    def map(self, identity: str, state: str, kind: str, value, population: str):
        self.seed(identity)["mappings"].append((state, kind, value, population))

    def cluster(self, identity: str, cluster: tuple):
        row = self.seed(identity)
        if row["cluster"] is None:
            row["cluster"] = cluster


def decide(identity: str, row: dict, aliases: dict, layer_ids: set[str]) -> dict:
    """Exactly one disposition, in this precedence: DUPLICATE (a verified alias), RETIRED (an existing record shows
    the upstream archived), the CARRIED mappings (committed records), the PROPOSED mappings (G5's one-family list
    screens, Q1-3; NON-GITHUB for a matched candidate whose link is not a GitHub repository), and UNMAPPED with
    its reason and step-2 cluster when nothing maps the seed."""
    if identity in aliases:
        return {"disposition": "DUPLICATE", "state": "CARRIED", "duplicate_of": aliases[identity]}
    retired = sorted({value for state, kind, value, _ in row["mappings"] if kind == "retired"})
    if retired:
        return {"disposition": "RETIRED", "state": "CARRIED", "retired": retired[0]}
    for state in ("CARRIED", "PROPOSED"):
        layers = sorted({value for s, kind, value, _ in row["mappings"] if s == state and kind == "layer"})
        unknown = [layer for layer in layers if layer not in layer_ids]
        if unknown:
            raise LedgerError(f"{identity}: unknown layer ids {unknown}")
        reasons = sorted({(population, value) for s, kind, value, population in row["mappings"]
                          if s == state and kind == "out-of-scope"})
        # A repository-level decision (a public star's OUT-OF-SCOPE) outranks backlog slots, which are unassessed;
        # only a final-stack role (a recorded verdict) outranks it. A grand OUT-OF-SCOPE row is slot-scoped.
        seed_decisions = sorted({(population, value) for s, kind, value, population in row["mappings"]
                                 if s == state and kind == "seed-out-of-scope"})
        verdict_layers = {value for s, kind, value, population in row["mappings"]
                          if s == state and kind == "layer" and population == "final-stack"}
        if seed_decisions and not verdict_layers:
            population, reason = seed_decisions[0]
            result = {"disposition": "OUT-OF-SCOPE", "state": state, "reason_text": reason, "reason_source": population}
            overridden = sorted({"layer:" + p for s, kind, _, p in row["mappings"] if s == state and kind == "layer"})
            if overridden:
                result["conflicts"] = overridden
            return result
        reasons += seed_decisions
        if layers:
            result = {"disposition": "LAYER-CANDIDATE", "state": state, "layers": layers}
            if reasons:
                result["conflicts"] = sorted({"out-of-scope:" + population for population, _ in reasons})
            return result
        # A named candidate without a GitHub URL that the G5 list screen matched: NON-GITHUB, with its layers.
        url_layers = sorted({value for s, kind, value, _ in row["mappings"] if s == state and kind == "non-github"})
        if [layer for layer in url_layers if layer not in layer_ids]:
            raise LedgerError(f"{identity}: unknown layer ids {url_layers}")
        if url_layers:
            result = {"disposition": "NON-GITHUB", "state": state, "layers": url_layers,
                      "reason_text": NON_GITHUB_REASON, "reason_source": "lists"}
            if reasons:
                result["conflicts"] = sorted({"out-of-scope:" + population for population, _ in reasons})
            return result
        if reasons:
            population, reason = reasons[0]
            result = {"disposition": "OUT-OF-SCOPE", "state": state, "reason_text": reason, "reason_source": population}
            if reason.startswith(NO_LAYER_MATCH):
                if row["cluster"] is None:
                    raise LedgerError(f"{identity}: no-layer-match OUT-OF-SCOPE without a step-2 cluster")
                result["cluster_key"] = row["cluster"]
            return result
    if row["cluster"] is None:
        raise LedgerError(f"{identity}: UNMAPPED without a step-2 cluster")
    return {"disposition": "UNMAPPED", "state": "UNSCREENED", "cluster_key": row["cluster"],
            "reason_text": UNMAPPED_REASONS["url" if identity.startswith("url:") else "repository"],
            "reason_source": "runs" if "runs" in row["populations"] else "pr-outputs"}


def layer_universe(repo_root: Path) -> set[str]:
    projection = final_stack_projection(load_json(repo_root / FINAL_STACK))
    return set(projection["layers"]) | set(projection["skills"])


def collect(repo_root: Path, state: Path, occurrences: dict, runs: list[dict], prs: list[dict],
            url_occurrences: dict | None = None, pins: dict | None = None) -> Seeds:
    seeds = Seeds()
    url_occurrences, pins = url_occurrences or {}, pins or {}
    grand = load_json(repo_root / GRAND)
    for index, row in enumerate(grand["rows"]):
        identity = identity_of(row["repository_or_entry"])
        seeds.source(identity, "grand", f"/rows/{index}")
        seeds.seed(identity)["existing"].setdefault("grand", set()).add(row["disposition"])
        if row["disposition"] == "OUT-OF-SCOPE":
            seeds.map(identity, "CARRIED", "out-of-scope",
                      f"Grand catalog OUT-OF-SCOPE row {GRAND}#/rows/{index}; reopen when: {row.get('reopen_when')}",
                      "grand")
        else:
            seeds.map(identity, "CARRIED", "layer", row["slot"], "grand")
    for layer, items in load_json(repo_root / MASTER_SEEDS).items():
        for index, item in enumerate(items):
            identity = master_seed_identity(item, grand["rows"])
            if identity is None:
                raise LedgerError(f"{MASTER_SEEDS}#/{layer}/{index}: no identity")
            seeds.source(identity, "master-seeds", f"/{layer}/{index}")
            seeds.map(identity, "CARRIED", "layer", layer, "master-seeds")
    for index, star in enumerate(load_json(repo_root / STARS)["repositories"]):
        identity = identity_of(star["repository"])
        seeds.source(identity, "stars", f"/repositories/{index}")
        seeds.seed(identity)["existing"]["stars"] = star["disposition_status"]
        if star.get("archived") is True:
            seeds.map(identity, "CARRIED", "retired", f"{STARS}#/repositories/{index}", "stars")
        if star["disposition_status"] == "OUT-OF-SCOPE":
            seeds.map(identity, "CARRIED", "seed-out-of-scope", "Public star OUT-OF-SCOPE: " + star["reason"], "stars")
        for layer in star.get("layer_keys") or []:
            seeds.map(identity, "CARRIED", "layer", layer, "stars")
    for index, seed in enumerate(load_json(repo_root / STARRED_SEEDS)["seeds"]):
        identity = identity_of(seed["repository"])
        seeds.source(identity, "starred-seeds", f"/seeds/{index}")
        seeds.map(identity, "CARRIED", "layer", seed["layer"], "starred-seeds")
    for key, roles in final_stack_projection(load_json(repo_root / FINAL_STACK))["index"].items():
        identity = identity_of(key)
        seeds.source(identity, "final-stack", "/index/by_repository/" + pointer_token(key))
        for role in roles:
            seeds.map(identity, "CARRIED", "layer", role["layer_id"], "final-stack")
            seeds.seed(identity)["existing"].setdefault("roles", set()).add(role["role"])
    for index, source in enumerate(load_json(repo_root / COVERAGE_ACCOUNTING)["list_sources"]):
        if source.get("archived") is True and source["repository"].lower() in occurrences:
            seeds.map(source["repository"].lower(), "CARRIED", "retired",
                      f"{COVERAGE_ACCOUNTING}#/list_sources/{index}", "lists")
    # The GitHub entries (extract) map to layers; the external entries (external_resources), keyed by canonical
    # URL, map to NON-GITHUB: both by the same grouping of the G5 screen's occurrence dispositions.
    for kind, table in (("layer", occurrences), ("non-github", url_occurrences)):
        for key, items in sorted(table.items()):
            identity = key if kind == "layer" else "url:" + key
            first = min(items, key=lambda item: (item["list"].lower(), item["commit"], item["path"], item["line"]))
            seeds.source(identity, "lists", list_ref(first, pins))
            seeds.seed(identity)["populations"]["lists"][0] = len(items)
            grouped = group_list_occurrences(items)
            if grouped["relevant"]:
                for layer in grouped["layers"]:
                    seeds.map(identity, "PROPOSED", kind, layer, "lists")
                seeds.seed(identity)["lifecycle"] |= set(grouped["lifecycle"])
            else:
                seeds.map(identity, "PROPOSED", "out-of-scope", grouped["reason"], "lists")
                if grouped["reason"].startswith(NO_LAYER_MATCH):
                    seeds.cluster(identity, ("list", f"{first['list']} / {first['section'] or '(no heading)'}"))
    for row in read_tsv(state / MCP_LEDGER):
        identity = slug(row["repository"]) if row["repository"] else None
        if identity is None:
            continue
        seeds.source(identity, "mcp-ledger", row["input_id"])
        if row["disposition"] == "REJECT" and "archived=true" in row["rationale"]:
            seeds.map(identity, "CARRIED", "retired", f"retained:{MCP_LEDGER}#{row['input_id']}", "mcp-ledger")
        elif row["disposition"] in ("WATCH", "TRIAL", "NO-GAP"):
            for layer in filter(None, row["catalog_layers"].split(";")):
                seeds.map(identity, "PROPOSED", "layer", layer, "mcp-ledger")
        elif row["disposition"] == "OUT-OF-SCOPE":
            seeds.map(identity, "PROPOSED", "out-of-scope", row["rationale"], "mcp-ledger")
    for row in read_tsv(state / GENERIC_LEDGER):
        identity = slug(row["repository"])
        seeds.source(identity, "generic-ledger", row["repository"])
        for layer in filter(None, row["layer_ids"].split(",")):
            seeds.map(identity, "PROPOSED", "layer", layer, "generic-ledger")
    for run in runs:
        for identity in run["seeds"] + ["url:" + url for url in run["named_urls"]]:
            seeds.source(identity, "runs", f"{run['runtime']}/{run['run_id']}")
            seeds.seed(identity)["runs"].append(run["pass_flag"])
            seeds.cluster(identity, ("research", f"{run['runtime']}/{run['run_id']}"))
    for pr in prs:  # the runs index's pr_outputs row holds the PR's pinned head_sha
        for identity in pr["seeds"] + ["url:" + url for url in pr["named_urls"]]:
            seeds.source(identity, "pr-outputs", f"#{pr['number']}")
            seeds.cluster(identity, ("pr", f"#{pr['number']}"))
    return seeds


def ledger_rows(repo_root: Path, seeds: Seeds) -> tuple[list[dict], list[str], list[dict]]:
    """The ledger rows, the reason table and the step-2 cluster table."""
    aliases = {old.lower(): new.lower() for old, new in load_json(repo_root / US_COVERAGE)["aliases"].items()}
    layer_ids = layer_universe(repo_root)
    for old, new in sorted(aliases.items()):
        if old in seeds.rows:  # the canonical seed decides with its alias's mappings; the alias keeps its provenance
            target = seeds.seed(new)
            target["mappings"].extend(seeds.rows[old]["mappings"])
            seeds.source(new, "aliases", old)
            target["aliases"].append(old)
            if seeds.rows[old]["cluster"] is not None and target["cluster"] is None:
                target["cluster"] = seeds.rows[old]["cluster"]
    decided = {identity: decide(identity, seeds.rows[identity], aliases, layer_ids) for identity in sorted(seeds.rows)}
    reasons = sorted({row["reason_text"] for row in decided.values() if "reason_text" in row})
    reason_index = {reason: index for index, reason in enumerate(reasons)}
    keys = collections.Counter(row["cluster_key"] for row in decided.values() if "cluster_key" in row)
    clusters, cluster_id = [], {}
    for number, key in enumerate(sorted(keys), 1):
        cluster_id[key] = f"C{number:04d}"
        inputs = sorted({"unmapped" if row["disposition"] == "UNMAPPED" else "no-layer-match"
                         for row in decided.values() if row.get("cluster_key") == key})
        clusters.append({"id": cluster_id[key], "source": key[0], "label": key[1], "seeds": keys[key],
                         "inputs": inputs})
    rows = []
    for identity, result in decided.items():
        seed = seeds.rows[identity]
        row = {"seed": identity, "disposition": result["disposition"], "state": result["state"]}
        for field in ("layers", "duplicate_of", "retired", "conflicts"):
            if field in result:
                row[field] = result[field]
        if "reason_text" in result:
            row["reason"] = reason_index[result["reason_text"]]
            row["reason_source"] = result["reason_source"]
        if "cluster_key" in result:
            row["cluster"] = cluster_id[result["cluster_key"]]
        if seed["lifecycle"]:
            row["lifecycle"] = sorted(seed["lifecycle"])
        existing = {key: (sorted(value) if isinstance(value, set) else value) for key, value in seed["existing"].items()}
        if existing:
            row["existing"] = dict(sorted(existing.items()))
        if seed["runs"]:
            row["research"] = {"runs": len(seed["runs"]),
                               "pass": "PASS" if any(flag is True for flag in seed["runs"]) else "UNVERIFIED"}
        if seed["aliases"]:
            row["aliases"] = sorted(seed["aliases"])
        row["populations"] = {key: seed["populations"][key] for key in sorted(seed["populations"])}
        rows.append(row)
    return rows, reasons, clusters


def ledger_counts(rows: list[dict]) -> dict:
    by_population = collections.Counter(population for row in rows for population in row["populations"])
    by_population_disposition = collections.defaultdict(collections.Counter)
    for row in rows:
        for population in row["populations"]:
            by_population_disposition[population][str(row.get("disposition"))] += 1
    repositories = [row for row in rows if ":" not in row["seed"]]  # owner/repo slugs; entry: and url: seeds aside
    return {"seeds": len(rows), "repositories": len(repositories),
            "entries": sum(1 for row in rows if row["seed"].startswith("entry:")),
            "named_urls": sum(1 for row in rows if row["seed"].startswith("url:")),
            "by_disposition": {key: sum(row.get("disposition") == key for row in rows) for key in DISPOSITIONS},
            "by_state": {key: sum(row.get("state") == key for row in rows) for key in STATES},
            "layer_candidates": {state: sum(row.get("disposition") == "LAYER-CANDIDATE" and row.get("state") == state
                                            for row in rows) for state in ("CARRIED", "PROPOSED")},
            "layer_candidate_repositories": sum(row.get("disposition") == "LAYER-CANDIDATE" for row in repositories),
            "layer_candidate_pairs": sum(len(row.get("layers", [])) for row in rows),
            "by_population": dict(sorted(by_population.items())),
            "by_population_disposition": {population: dict(sorted(counter.items()))
                                          for population, counter in sorted(by_population_disposition.items())},
            "conflicts": sum(1 for row in rows if row.get("conflicts")),
            "step2_inputs": sum(1 for row in rows if row.get("cluster")),
            "step2_clusters": len({row["cluster"] for row in rows if row.get("cluster")})}


def ref_list(ref: str) -> str:
    """The lowercase owner/repo of a list ref (<list>[@<commit>]:<path>:<line>)."""
    return re.match(r"[^/@:]+/[^/@:]+", ref).group(0).lower()


def named_url_reconciliation(rows: list[dict]) -> dict:
    """The named candidates without a GitHub URL (url: seeds) by where they were named, each with its dispositions;
    the committed entries that name no GitHub repository keep their own rows (entry: seeds)."""
    order = ("list entries (screen_generic external_resources)", "list entries and research or PR outputs",
             "research runs and PR outputs only")
    by_scope = {scope: collections.Counter() for scope in order}
    for row in rows:
        if not row["seed"].startswith("url:"):
            continue
        populations = set(row["populations"])
        scope = (order[1] if "lists" in populations and populations & {"runs", "pr-outputs"} else
                 order[0] if "lists" in populations else order[2])
        by_scope[scope][row["disposition"]] += 1
    entries = collections.Counter(row["disposition"] for row in rows if row["seed"].startswith("entry:"))
    return {"unit": "distinct canonical URLs: https, lowercase host without www., no userinfo, port, query or "
                    "fragment, no trailing slash; public hosts only",
            "steps": [{"scope": scope, "seeds": sum(by_scope[scope].values()),
                       "by_disposition": dict(sorted(by_scope[scope].items()))} for scope in order],
            "total": sum(sum(counter.values()) for counter in by_scope.values()),
            "committed_entries": {"seeds": sum(entries.values()), "by_disposition": dict(sorted(entries.items()))}}


def universe_reconciliation(rows: list[dict], lists: dict) -> dict:
    """The LAYER-CANDIDATE repositories against the approved plan's 8.3k-10.7k ESTIMATE (C-5): each repository
    counted once, in the first scope that holds it, in the order the estimate was built."""
    recorded_scope = {}
    for item in lists["lists"]:
        populations = set(item["populations"])
        recorded_scope[item["repository"].lower()] = (
            "lists without a recorded pin (starred, fetched at head)" if not item["recorded_pins"] else
            "coverage-accounting lists no retained ledger covers"
            if not populations & {"grand-list-populations", "mcp-lane"} else
            "whole-document parsing of lists G5 censused by another parser or a section subsequence")
    order = ("carried records (grand catalog, master seeds, stars, starred seeds, final-stack)",
             "retained G5 list ledgers (MCP and generic)",
             "coverage-accounting lists no retained ledger covers",
             "lists without a recorded pin (starred, fetched at head)",
             "whole-document parsing of lists G5 censused by another parser or a section subsequence")
    counts = collections.Counter()
    for row in rows:
        if row["disposition"] != "LAYER-CANDIDATE" or ":" in row["seed"]:
            continue
        populations = row["populations"]
        if set(populations) & set(CARRIED_POPULATIONS):
            counts[order[0]] += 1
        elif set(populations) & {"mcp-ledger", "generic-ledger"}:
            counts[order[1]] += 1
        else:
            counts[recorded_scope[ref_list(populations["lists"][1])]] += 1
    running, steps = 0, []
    for scope in order:
        running += counts[scope]
        steps.append({"scope": scope, "repositories": counts[scope], "cumulative": running})
    return {"estimate": "8.3k-10.7k distinct repositories (the approved plan's C-5, an ESTIMATE)",
            "steps": steps, "total": running,
            "note": "PROPOSED rows are one-family G5 screen results (Q1-3); step 3 confirms or overturns each"}


def grand_reconciliation(repo_root: Path) -> dict:
    grand = load_json(repo_root / GRAND)
    rows = grand["rows"]
    backlog = [row for row in rows if row["disposition"] in ("PENDING", "WATCH")]
    ids = set(grand["coverage"]["outside_declared_union"]["occurrence_ids"])

    def leaves(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from leaves(child)
        elif isinstance(value, list):
            for child in value:
                yield from leaves(child)

    hit = [row for row in rows if ids & set(leaves(row))]
    backlog_ids = {identity_of(row["repository_or_entry"]) for row in backlog}
    return {"rows": len(rows), "by_disposition": dict(sorted(collections.Counter(r["disposition"] for r in rows).items())),
            "backlog_rows": len(backlog), "backlog_slots": len({row["slot"] for row in backlog}),
            "backlog_slugs": sum(1 for identity in backlog_ids if not identity.startswith("entry:")),
            "backlog_entries": sum(1 for identity in backlog_ids if identity.startswith("entry:")),
            "backlog_pairs": len({(row["slot"], slug(row["repository_or_entry"])) for row in backlog
                                  if slug(row["repository_or_entry"])}),
            "f3_occurrence_ids": len(ids), "f3_rows": len(hit),
            "f3_rows_by_disposition": dict(sorted(collections.Counter(row["disposition"] for row in hit).items())),
            "f3_entries": len({row["repository_or_entry"] for row in hit}),
            "f3_entries_outside_backlog": len({identity_of(row["repository_or_entry"]) for row in hit} - backlog_ids)}


# --------------------------------------------------------------------------- output


def dump(document: dict, rows_key: str) -> str:
    """Pretty JSON with one compact line per row of document[rows_key] (reviewable, diffable, parseable)."""
    head = dict(document)
    head[rows_key] = "__ROWS__"
    text = json.dumps(head, indent=1, ensure_ascii=False)
    body = ",\n".join("  " + json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in document[rows_key])
    return text.replace('"__ROWS__"', "[\n" + body + "\n ]") + "\n"


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def committed_inputs(repo_root: Path) -> dict:
    out = {path: {"sha256": file_sha256(repo_root / path)} for path in (
        GRAND, COVERAGE_ACCOUNTING, US_COVERAGE, STARS, STARRED_SEEDS, MASTER_SEEDS, STACK)}
    out[FINAL_STACK] = {"projection_sha256": canonical_sha256(final_stack_projection(load_json(repo_root / FINAL_STACK))),
                        "projection": "index.by_repository and the layer and skills ids (final_stack_projection)"}
    return dict(sorted(out.items()))


def build(args) -> int:
    repo_root, state_root = args.repo_root.resolve(), args.state_root.resolve()
    state = state_root / "native-agent-stack"
    checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    date = args.date or checked_at[:10].replace("-", "")
    PRIVACY["patterns"], PRIVACY["redacted"] = load_private_patterns(REPO_ROOT), {}
    sg = load_screen_generic()
    g5_lists = {repository.lower() for repository in sg.REPOS}  # the module's 14 G5 generic lists
    sg.ROOT = repo_root
    board = args.scratch / "empty-readiness-board.json"  # readiness slots feed no disposition here
    write(board, json.dumps({"slots": []}) + "\n")
    sg.BOARD = board
    selected = sg.definitions()[3]
    clones = index_clones([path.resolve() for path in args.clones])
    table, occurrences, url_occurrences, accounting = build_lists(repo_root, state, clones, sg, selected, checked_at)
    generic = generic_comparison(occurrences, read_tsv(state / GENERIC_LEDGER), g5_lists)
    lists_path, runs_path = LISTS_NAME.format(date=date), RUNS_NAME.format(date=date)
    lists_document = {
        "schema_version": 1, "kind": "landscape-awesome-list-table", "checked_at": checked_at,
        "schema": SCHEMAS["lists"],
        "parser": {"module": "tools/landscape/screen_generic.py", "functions": ["extract", "external_resources"],
                   "original_binding": PARSER_ANCHOR,
                   "edits": "path constants only, lines 19-24 and 427-428 (tests/test_landscape_screen_generic.py)"},
        "pin_rule": "Each list is read at its newest recorded pin (the Q1-2 PROPOSAL default); every older recorded "
                    "census is re-read at its own pin as provenance. A list with no recorded pin is read at the "
                    "default-branch head fetched for this ledger.",
        "boundaries": ["unauthenticated depth-1 partial clones; no GitHub API; no cloned code executed",
                       "screen_generic reads .md, .mdx and .rst documents only (screen_generic.py:150)",
                       "a list whose external_resources pass stops on a link urlsplit refuses is read again with "
                       "only those links skipped; extraction.ignored counts them",
                       "external entries are seeded by canonical URL; an IP literal, localhost or a private suffix "
                       "is no public candidate and is counted under seeded_occurrences.external_not_public"],
        "seeded_occurrences": {key: sum(item["seeded_occurrences"][key] for item in table)
                               for key in ("github", "external", "external_not_public")},
        "coverage_accounting": accounting, "g5_generic_ledger": generic, "lists": table}
    # Fully indented: each "commit" pin sits on its own line, the shape the rule-scoped .gitleaks.toml allowlist
    # for this exact file exempts (its 2026-10-16 note there).
    write(repo_root / lists_path, json.dumps(lists_document, indent=1, ensure_ascii=False) + "\n")
    by_run, exact = dispatch_receipts(state)
    repo_from = sg.repo_from
    runs = (deerflow_runs(state, args.scratch, by_run, repo_from)
            + gptr_runs(state_root, repo_from, gptr_version(args.gptr_checkout))
            + pi_claude_runs(state, repo_from) + exact_query_runs(exact, repo_from))
    prs = pr_outputs(args.pr_files, repo_from)
    pins = {item["repository"]: item["pin"]["commit"] for item in table}
    seeds = collect(repo_root, state, occurrences, runs, prs, url_occurrences, pins)
    installed = {slug(component.get("repository")) for component in load_json(repo_root / STACK)["components"]} - {None}
    join, new = research_join({identity for run in runs for identity in run["seeds"]},
                              {identity: set(row["populations"]) for identity, row in seeds.rows.items()}, installed)
    write(repo_root / runs_path, dump({
        "schema_version": 1, "kind": "landscape-research-runs-index", "checked_at": checked_at,
        "schema": SCHEMAS["runs"],
        "boundaries": [
            "Each DeerFlow database is copied with its -wal and -shm files and each copy's sha256 is verified; "
            "only sqlite_master names and the named runs columns are read, and the copy is deleted. No user, "
            "password, token, session or credential table is read, and no SELECT * is issued.",
            "Per-run home and state trees, credential files and configuration holding keys are not read.",
            "Question and query text is not published; the topic is a model-written heading or title. Each "
            "withheld field is counted, with its reason, under withheld.",
            "A pass flag is metadata only and never replaces primary-source review.",
            "Seeds are cited GitHub owner/repo identities (seeds) and the canonical URLs of every other cited "
            "public http(s) link (named_urls), without screen_generic's badge, image and sponsor links. A name "
            "with no link at all is not extracted."],
        "withheld": withheld_record(runs),
        "pass_flag_rule": {"record": "native-retrieval-metadata.json, written in the DeerFlow run directory",
                           "read_at": PASS_RECORD, "assertion": PASS_ASSERTION, "no_record": "UNVERIFIED (Q1-4)"},
        "database_schema_source": "bytedance/deer-flow@345f08be00c8a9495079b732a39b46aa9af1584e:"
                                  "backend/packages/harness/deerflow/persistence/run/model.py:14-35; the installed "
                                  "2.1.0 source at the same commit is identical",
        "counts": {"runs": len(runs),
                   "by_runtime": dict(sorted(collections.Counter(r["runtime"] for r in runs).items())),
                   "by_pass_flag": dict(sorted(collections.Counter(str(r["pass_flag"]) for r in runs).items())),
                   "databases_by_tables": dict(sorted(collections.Counter(
                       ",".join(r["database"]["tables"]) for r in runs if r["database"]).items())),
                   "runs_with_seeds": sum(1 for r in runs if r["seeds"]),
                   "seeds": len({identity for run in runs for identity in run["seeds"]}),
                   "named_urls": len({url for run in runs for url in run["named_urls"]}),
                   "pr_seeds": len({identity for pr in prs for identity in pr["seeds"]}),
                   "pr_named_urls": len({url for pr in prs for url in pr["named_urls"]})},
        "join": {"buckets": join, "new": new},
        "pr_outputs": prs, "runs": runs}, "runs"))
    rows, reasons, clusters = ledger_rows(repo_root, seeds)
    write(repo_root / LEDGER_DIR / f"coverage-ledger-{date}.json", dump({
        "schema_version": 1, "kind": "landscape-coverage-ledger", "checked_at": checked_at,
        "schema": SCHEMAS["ledger"],
        "rules": {
            "dispositions": list(DISPOSITIONS), "states": list(STATES),
            "precedence": "DUPLICATE (verified alias), RETIRED (an existing record shows the upstream archived), "
                          "CARRIED mappings, PROPOSED mappings, UNMAPPED. Within CARRIED, a public star's "
                          "OUT-OF-SCOPE (a repository-level decision) outranks unassessed backlog slots and yields "
                          "only to a final-stack role; a grand-catalog OUT-OF-SCOPE row is slot-scoped. Overridden "
                          "mappings are listed under conflicts",
            "carried": "committed records: grand-catalog rows, master seeds, public stars, starred seeds and the "
                       "final-stack index; existing verdicts stay under existing",
            "proposed": "G5's one-family list screens (the re-extracted lists, the MCP ledger and the generic "
                        "ledger) are PROPOSED dispositions, never final; step 3's two-family screen confirms or "
                        "overturns each one (Q1-3)",
            "non_github": "a named candidate whose link is not a GitHub repository and that the G5 list screen "
                          "matched to layers; its layers are kept, and step 3's GitHub readers cannot rank it",
            "unmapped": "research-run and PR seeds that no other population maps; each has its reason and a step-2 "
                        "cluster",
            "lifecycle": "screen_generic lifecycle matches are hints, not layer mappings (screen_generic.py:160-161)",
            "identity": "lowercase owner/repo; a recorded entry naming no GitHub repository stays entry:<literal>; "
                        "a named candidate whose link is not a GitHub repository is url:<canonical URL>",
            "list_refs": "<list>:<path>:<line> at the list's pin in the list table, <list>@<commit>:<path>:<line> "
                         "at an older recorded pin"},
        "population_sources": {
            "grand": GRAND, "master-seeds": MASTER_SEEDS, "stars": STARS, "starred-seeds": STARRED_SEEDS,
            "final-stack": FINAL_STACK, "lists": lists_path, "mcp-ledger": "retained:" + MCP_LEDGER,
            "generic-ledger": "retained:" + GENERIC_LEDGER, "runs": runs_path, "pr-outputs": runs_path + "#/pr_outputs",
            "aliases": US_COVERAGE + "#/aliases"},
        "inputs": {"committed": committed_inputs(repo_root), "outputs": {"lists": lists_path, "runs": runs_path},
                   "retained": {"mcp-ledger": {"path": MCP_LEDGER, "rows": len(read_tsv(state / MCP_LEDGER))},
                                "generic-ledger": {"path": GENERIC_LEDGER,
                                                   "rows": len(read_tsv(state / GENERIC_LEDGER))}}},
        "reconciliation": {"grand": grand_reconciliation(repo_root), "coverage_accounting": accounting,
                           "g5_generic_ledger": generic, "lists": f"{lists_path}#/lists/*/census",
                           "universe": universe_reconciliation(rows, lists_document),
                           "named_urls": {**named_url_reconciliation(rows), "privacy_redacted": {
                               "reason": "privacy: a URL path segment matched the repository's private-content "
                                         "patterns (scripts/validate.py PRIVATE_CONTENT) and is replaced by a "
                                         "placeholder; the seed keeps its row",
                               "urls_by_pattern": {description: len(urls) for description, urls
                                                   in sorted(PRIVACY["redacted"].items())}}}},
        # "seeds", not "rows": the Architecture supplement glob projects a top-level layers/rows/candidates/components
        # collection onto layer pages (tools/local-pages/architecture_sources.py:391), and a seed is no layer record.
        "counts": ledger_counts(rows), "reasons": reasons, "clusters": clusters, "seeds": rows}, "seeds"))
    print(json.dumps({"lists": len(table), "runs": len(runs), "seeds": len(rows), "clusters": len(clusters),
                      "by_disposition": ledger_counts(rows)["by_disposition"]}))
    return 0


# --------------------------------------------------------------------------- check


def newest_ledger(repo_root: Path) -> Path | None:
    directory = repo_root / LEDGER_DIR
    dated = sorted(path for path in (directory.iterdir() if directory.is_dir() else [])
                   if LEDGER_NAME.fullmatch(path.name))
    return dated[-1] if dated else None


def check_rows(ledger: dict, layer_ids: set[str]) -> list[str]:
    problems = []
    rows, reasons = ledger["seeds"], ledger["reasons"]
    clusters = {cluster["id"]: cluster for cluster in ledger["clusters"]}
    seeds = [row["seed"] for row in rows]
    if seeds != sorted(set(seeds)):
        problems.append("ledger rows must be unique and sorted by seed")
    by_seed = {row["seed"]: row for row in rows}
    referenced = collections.Counter()
    for row in rows:
        seed, disposition = row["seed"], row.get("disposition")
        if not row.get("populations"):
            problems.append(f"{seed}: no population")
        if disposition not in DISPOSITIONS:
            problems.append(f"{seed}: disposition {disposition!r} is not one of {DISPOSITIONS}")
        elif disposition == "LAYER-CANDIDATE" and not (row.get("layers") and set(row["layers"]) <= layer_ids):
            problems.append(f"{seed}: LAYER-CANDIDATE needs layers from the landscape's layer ids")
        elif disposition == "OUT-OF-SCOPE" and not (isinstance(row.get("reason"), int) and 0 <= row["reason"] < len(reasons)):
            problems.append(f"{seed}: OUT-OF-SCOPE needs a reason")
        elif disposition == "DUPLICATE" and by_seed.get(row.get("duplicate_of"), {}).get("disposition") in (None, "DUPLICATE"):
            problems.append(f"{seed}: DUPLICATE of a missing or duplicate seed")
        elif disposition == "RETIRED" and not row.get("retired"):
            problems.append(f"{seed}: RETIRED without the record that shows the upstream archived")
        elif disposition == "UNMAPPED" and (row.get("cluster") not in clusters or not (
                isinstance(row.get("reason"), int) and 0 <= row["reason"] < len(reasons))):
            problems.append(f"{seed}: UNMAPPED without its reason and step-2 cluster")
        elif disposition == "NON-GITHUB" and not (seed.startswith("url:") and row.get("layers")
                                                  and set(row["layers"]) <= layer_ids
                                                  and isinstance(row.get("reason"), int)
                                                  and 0 <= row["reason"] < len(reasons)):
            problems.append(f"{seed}: NON-GITHUB needs a url: seed, its reason and layers from the landscape")
        if disposition == "OUT-OF-SCOPE" and isinstance(row.get("reason"), int) and row["reason"] < len(reasons) \
                and reasons[row["reason"]].startswith(NO_LAYER_MATCH) and row.get("cluster") not in clusters:
            problems.append(f"{seed}: no-layer-match OUT-OF-SCOPE without a step-2 cluster")
        if row.get("cluster"):
            referenced[row["cluster"]] += 1
    for cluster_id, cluster in clusters.items():
        if referenced[cluster_id] != cluster["seeds"]:
            problems.append(f"cluster {cluster_id}: {cluster['seeds']} seeds recorded, {referenced[cluster_id]} found")
    if ledger["counts"] != ledger_counts(rows):
        problems.append("ledger counts differ from the rows")
    return problems


# Frozen records: a change to one is a problem. A change to any other recorded input makes the ledger STALE, which
# check reports and --strict makes fatal: rebuilding needs the list clones and the retained research inputs.
FROZEN_INPUTS = (GRAND, COVERAGE_ACCOUNTING)


def check(repo_root: Path, stale: list | None = None) -> list[str]:
    """Problems with the committed ledger, list table and runs index; empty when they pass. Inputs that changed
    since the build are appended to ``stale`` (a list the caller passes) instead of being problems."""
    stale = stale if stale is not None else []
    path = newest_ledger(repo_root)
    if path is None:
        return [f"no {LEDGER_DIR}/coverage-ledger-<date>.json"]
    ledger = load_json(path)
    lists = load_json(repo_root / ledger["inputs"]["outputs"]["lists"])
    runs = load_json(repo_root / ledger["inputs"]["outputs"]["runs"])
    problems = []
    try:
        import jsonschema
    except ImportError:  # pragma: no cover - .github/requirements-ci.txt pins jsonschema 4.26.0
        jsonschema = None
    if jsonschema is not None:
        for name, document in (("ledger", ledger), ("lists", lists), ("runs", runs)):
            validator = jsonschema.Draft202012Validator(load_json(repo_root / SCHEMAS[name]))
            for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))[:5]:
                problems.append(f"{name}: schema: {error.message[:160]} at {list(error.absolute_path)[:4]}")
    current = committed_inputs(repo_root)
    changed = {input_path for input_path, recorded in ledger["inputs"]["committed"].items()
               if current.get(input_path) != recorded}
    for input_path in sorted(changed):
        message = f"{input_path} changed since the ledger was built; rebuild it (coverage_ledger.py build)"
        (problems if input_path in FROZEN_INPUTS else stale).append(message)
    problems += check_rows(ledger, layer_universe(repo_root))
    rows = ledger["seeds"]
    by_seed = {row["seed"]: row for row in rows}
    if ledger["reconciliation"]["universe"] != universe_reconciliation(rows, lists):
        problems.append("universe reconciliation differs from the rows and the list table")
    expected = grand_reconciliation(repo_root)
    if ledger["reconciliation"]["grand"] != expected:
        problems.append("grand reconciliation differs from the committed grand catalog")
    if (expected["rows"], expected["by_disposition"].get("PENDING"), expected["by_disposition"].get("WATCH"),
            expected["backlog_slots"], expected["f3_occurrence_ids"], expected["f3_rows"],
            expected["f3_entries_outside_backlog"]) != (4606, 4058, 401, 45, 797, 769, 0):
        problems.append(f"grand catalog no longer reconciles with 4,606/4,058/401/45 and F3 797 -> 769: {expected}")
    grand = load_json(repo_root / GRAND)
    expected_sources = [("grand", identity_of(row["repository_or_entry"])) for row in grand["rows"]]
    if STARS not in changed:  # a changed input's completeness waits for the rebuild that the STALE line names
        expected_sources += [("stars", identity_of(star["repository"]))
                             for star in load_json(repo_root / STARS)["repositories"]]
    if STARRED_SEEDS not in changed:
        expected_sources += [("starred-seeds", identity_of(seed["repository"]))
                             for seed in load_json(repo_root / STARRED_SEEDS)["seeds"]]
    if MASTER_SEEDS not in changed:
        expected_sources += [("master-seeds", master_seed_identity(item, grand["rows"]))
                             for items in load_json(repo_root / MASTER_SEEDS).values() for item in items]
    if FINAL_STACK not in changed:
        expected_sources += [("final-stack", identity_of(key)) for key in
                             final_stack_projection(load_json(repo_root / FINAL_STACK))["index"]]
    missing = sorted({(population, identity) for population, identity in expected_sources
                      if population not in by_seed.get(identity, {}).get("populations", {})}, key=str)
    if missing:
        problems.append(f"{len(missing)} committed records have no ledger seed, e.g. {missing[:3]}")
    accounting = load_json(repo_root / COVERAGE_ACCOUNTING)
    summary = lists["coverage_accounting"]
    if (summary["lists"], summary["recorded_unique"], summary["recorded_unassessed"]) != (
            len(accounting["list_sources"]), accounting["counts"]["unique_extracted_github_identities"],
            accounting["counts"]["discovery_only_unassessed"]) or summary["delta"] != (
            summary["reextracted_union"] - summary["recorded_unique"]) or (
            summary["recorded_unique"], summary["recorded_unassessed"]) != (7028, 6939):
        problems.append("coverage-accounting reconciliation differs from the committed record (12 lists, 7,028/6,939)")
    census = {(entry["record"], entry["commit"]): entry for item in lists["lists"] for entry in item["census"]}
    for index, source in enumerate(accounting["list_sources"]):
        entry = census.get((f"{COVERAGE_ACCOUNTING}#/list_sources/{index}", source["commit"]))
        if entry is None or entry["recorded"] != source["github_identity_links"] or not entry["file_matches_record"] \
                or entry["delta"] != entry["reextracted"] - entry["recorded"] or (entry["delta"] and not entry["cause"]):
            problems.append(f"coverage-accounting list {source['repository']}: census at its pin does not reconcile")
    populations = collections.defaultdict(list)
    for item in grand["coverage"]["list_populations"]:
        populations[item["source_repository"]].append(item)
    for repository, items in populations.items():
        entry = census.get((f"{GRAND}#/coverage/list_populations", items[0]["pin"]["version_or_commit"]))
        recorded_files = {(item["path"], item["capture_sha256"], item["counted"]["physical_entries"]) for item in items}
        if entry is None or {(f["path"], f["capture_sha256"], f["recorded"]) for f in entry["files"]} != recorded_files:
            problems.append(f"list_populations {repository}: recorded census differs from the committed record")
        elif entry["recorded_parser"].startswith(GENERIC_PARSER) and (entry["delta"] or not all(
                f["blob_matches_capture"] and f["reextracted"] == f["recorded"] for f in entry["files"])):
            problems.append(f"list_populations {repository}: screen_generic re-extraction differs at its pin")
        elif not entry["recorded_parser"].startswith(GENERIC_PARSER) and not entry["cause"]:
            problems.append(f"list_populations {repository}: a census delta needs its cause")
    run_seeds = {identity for run in runs["runs"] for identity in run["seeds"]}
    run_seeds |= {identity for pr in runs["pr_outputs"] for identity in pr["seeds"]}
    run_seeds |= {"url:" + url for item in runs["runs"] + runs["pr_outputs"] for url in item["named_urls"]}
    missing_runs = sorted(identity for identity in run_seeds if identity not in by_seed)
    if missing_runs:
        problems.append(f"{len(missing_runs)} research seeds are not ledger seeds, e.g. {missing_runs[:3]}")
    # Every extracted list entry is a seed: the list-population occurrences of the owner/repo seeds and of the url:
    # seeds add up to what the list table records as seeded across every pin read.
    totals = lists["seeded_occurrences"]
    observed = {"github": sum(row["populations"]["lists"][0] for row in rows
                              if "lists" in row["populations"] and ":" not in row["seed"]),
                "external": sum(row["populations"]["lists"][0] for row in rows
                                if "lists" in row["populations"] and row["seed"].startswith("url:"))}
    if (observed["github"], observed["external"]) != (totals["github"], totals["external"]) or totals != {
            key: sum(item["seeded_occurrences"][key] for item in lists["lists"])
            for key in ("github", "external", "external_not_public")}:
        problems.append(f"list occurrences do not reconcile with the seeds: table {totals}, seeds {observed}")
    recorded_urls = {key: value for key, value in ledger["reconciliation"]["named_urls"].items()
                     if key != "privacy_redacted"}
    if recorded_urls != named_url_reconciliation(rows):
        problems.append("named-URL reconciliation differs from the rows")
    patterns = load_private_patterns(REPO_ROOT)  # rules from this tool's checkout, data from the checked root
    published = [row["seed"] for row in rows if row["seed"].startswith("url:")]
    published += [url for item in runs["runs"] + runs["pr_outputs"] for url in item["named_urls"]]
    leaking = sorted({description for value in published for description, pattern in patterns if pattern.search(value)})
    if leaking:
        problems.append(f"named URLs match private-content patterns: {leaking}")
    if runs["withheld"] != withheld_record(runs["runs"]):
        problems.append("the withheld record differs from the runs it counts")
    for run in runs["runs"]:
        record = run.get("pass_record")
        expected_flag = "UNVERIFIED" if record is None else (
            record["integration_assertion_pass"] is True and type(record["cited_retrieved_url_matches"]) is int
            and record["cited_retrieved_url_matches"] >= 1 and record["answer_nonempty"])
        if run["pass_flag"] != expected_flag:
            problems.append(f"run {run['run_id']}: pass flag does not follow {PASS_ASSERTION}")
        if run.get("question_text") is not None:
            problems.append(f"run {run['run_id']}: question text is published")
    return problems


def master_seeds(repo_root: Path, modality: str) -> dict[str, list[str]]:
    """The committed master seeds as build_inputs.py --seeds JSON for one modality: the landscape catalogs' layer
    ids (repository) or the skills-lifecycle task ids (skills). A key in neither is an error."""
    catalog_ids = {layer["layer_id"] for name in ("foundation.json", "us-equities.json")
                   for layer in load_json(repo_root / LANDSCAPE_DIR / name)["layers"]}
    skills_ids = {task["layer_id"] for task in load_json(repo_root / LANDSCAPE_DIR / "skills-lifecycle.json")["tasks"]}
    master = load_json(repo_root / MASTER_SEEDS)
    unknown = sorted(set(master) - catalog_ids - skills_ids)
    if unknown:
        raise LedgerError(f"{MASTER_SEEDS}: layer ids in no landscape catalog: {unknown}")
    wanted = skills_ids if modality == "skills" else catalog_ids
    return {layer: list(items) for layer, items in master.items() if layer in wanted}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    seeds_parser = sub.add_parser("seeds", help="emit the master seeds as build_inputs.py --seeds JSON")
    seeds_parser.add_argument("--modality", choices=("repository", "skills"), required=True)
    seeds_parser.add_argument("--out", type=Path)
    seeds_parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--clones", type=Path, action="append", required=True)
    build_parser.add_argument("--state-root", type=Path, required=True)
    build_parser.add_argument("--pr-files", type=Path, required=True)
    build_parser.add_argument("--scratch", type=Path, required=True)
    build_parser.add_argument("--gptr-checkout", type=Path)
    build_parser.add_argument("--date")
    build_parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    check_parser.add_argument("--strict", action="store_true", help="a STALE input is a problem too")
    args = parser.parse_args(argv)
    if args.command == "build":
        try:
            return build(args)
        except (LedgerError, OSError, KeyError, ValueError) as error:
            print(f"coverage_ledger.py: {error}", file=sys.stderr)
            return 2
    if args.command == "seeds":
        try:
            text = json.dumps(master_seeds(args.repo_root.resolve(), args.modality), indent=1, ensure_ascii=False) + "\n"
        except (LedgerError, OSError, KeyError) as error:
            print(f"coverage_ledger.py: {error}", file=sys.stderr)
            return 2
        if args.out:
            write(args.out, text)
        else:
            sys.stdout.write(text)
        return 0
    stale: list[str] = []
    problems = check(args.repo_root.resolve(), stale)
    for problem in problems:
        print(problem)
    for line in stale:
        print("STALE: " + line)
    failed = problems + (stale if args.strict else [])
    print(f"coverage_ledger.py check: {len(problems)} problem(s), {len(stale)} stale input(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
