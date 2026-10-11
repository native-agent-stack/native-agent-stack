"""Published digests bind published bytes: no new digest under evidence/, blueprints/ or manifests/ is an offline oracle
(correction #161).

A sha256 of the bytes before sanitization, published beside the sanitized copy, lets anyone confirm a guessed home directory or
account name offline: put the guess back in place of the mask, hash, compare. scripts/host_receipts.py record has digested only
the published excerpt since #492 (the comment at line 1012, the hash at line 1029).

findings() walks every JSON file under SCANNED. For each 64-hex string value it collects, from the value's own object and the
object that encloses it, the strings that carry a mask and the files named under FILE_KEYS (resolved against the JSON file's
directory first, then the checkout root). A finding is a digest that hashes none of those texts or files as published but does
hash one of them once masks are put back. Each mask is either left alone or put back everywhere (every subset of up to four
masks; beyond four, all of them or one at a time): a home mask as /home/<name> or /Users/<name>, %USERPROFILE% as C:\\Users\\<name>,
C:/Users/<name> or /mnt/c/Users/<name>, and an account or host mask as <name>. Texts are also tried with a trailing newline. A
finding is reported as path, key and the digest's first 8 hex digits, never a name, a home path or a candidate. Forms this
detector does not reach (content-addressed tables, nested or non-JSON digests, keys outside FILE_KEYS) are follow-up F3 of #1010.

The names are scripts/host_name_scan.py host_names() (#934; docs/decisions/2026-10-09-host-name-scan.md) when
PUBLISHED_DIGEST_GUARD_HOST_NAMES=1, which scripts/git-hooks/pre-push sets: they stay in this process, an unavailable source
fails the check, and NATIVE_AGENT_HOST_NAMES_JSON replaces them in fixtures. Otherwise they are the comma-separated
LANDING_PROHIBITED_NAMES, and without either the repository check skips, as in CI. So it is a local and pre-push guard. The
allowlist bookkeeping, the regression for the sites fixed with this test, the readiness pin check and the synthetic cases need no
names and run everywhere.

LEGACY_SITES freezes the sites left at the freeze. LEGACY_HOST_RECEIPTS holds 96 output_sha256 values in evidence/hosts receipts
recorded before 2026-09-29, which #492 left append-only. OUTSIDE_THE_AUDIT holds 10 sites that the 2026-10-11 audit's probe, which
put back only ~ and <user> and read only files named in the digest's own object, did not reach. An unlisted site fails. A listed
site these names do not reproduce is only reported, because another clone's names differ; test_the_frozen_list_only_shrinks
fails, without names, once a listed digest is gone from its file, so a fixed site leaves the list and the list only shrinks.
"""

from __future__ import annotations

import functools
import hashlib
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("evidence", "blueprints", "manifests")
NAMES_VARIABLE = "LANDING_PROHIBITED_NAMES"
HOST_NAMES_SWITCH = "PUBLISHED_DIGEST_GUARD_HOST_NAMES"
DIGEST = re.compile(r"[0-9a-f]{64}")
FILE_KEYS = frozenset({"path", "file", "log", "output_path", "raw_path", "capture"})
HOME_MASKS = ("~", "<home>", "<HOME>", "<host-home>", "<user-home>", "<SCRATCH_HOME>", "$HOME", "${HOME}")
WINDOWS_HOME_MASKS = ("%USERPROFILE%",)
USER_MASKS = ("<user>", "<USER>", "$USER", "<WSL_USER>", "<hostname>")
MASKS = (*HOME_MASKS, *WINDOWS_HOME_MASKS, *USER_MASKS)
HOME_PREFIXES = ("/home/", "/Users/")
WINDOWS_HOME_PREFIXES = ("C:\\Users\\", "C:/Users/", "/mnt/c/Users/")
ALL_SUBSETS_UP_TO = 4
MAX_FILE_BYTES = 64 * 1024 * 1024
MASK_BYTES = tuple(mask.encode() for mask in MASKS)
MASK_STARTS = "".join(sorted({mask[0] for mask in MASKS}))
READINESS = "catalogs/north-star/readiness.json"
READINESS_BINDING = re.compile(r"repo:(.+)@([0-9a-f]{64})")

HOSTS = "evidence/hosts/nativestack-5975wx-20260925/nativestack-5975wx-20260925--"
LEGACY_HOST_RECEIPTS = frozenset((f"{HOSTS}{stem}.json", "output_sha256", prefix) for stem, prefix in (
    ("agentsview--install--20260925", "f1eaa384"),
    ("ai-memory--install--20260925", "3d0a172d"),
    ("ai-memory--use--20260925", "420378f2"),
    ("ast-grep--install--20260925", "186db670"),
    ("ccusage--install--20260925", "ca118792"),
    ("ccusage--use--20260925", "d37962cd"),
    ("claude-code--install--20260925", "f79cbad7"),
    ("codebase-memory-mcp--install--20260925", "d52dee79"),
    ("codex--install--20260925", "12d13672"),
    ("context-hub--install--20260925", "571a4eaf"),
    ("context-mode--install--20260925", "55f6e084"),
    ("context-mode--install--20260925", "ddf1b983"),
    ("context-mode--install--20260926", "fcb239f4"),
    ("dagu--install--20260925", "81fd844b"),
    ("dagu--use--20260925", "5ca60375"),
    ("difftastic--install--20260925", "e0fbc114"),
    ("difftastic--use--20260925", "8f665f81"),
    ("gitleaks--install--20260925", "a2c6088b"),
    ("gitleaks--install--20260925", "af23f379"),
    ("gitleaks--use--20260925", "c3a7a425"),
    ("headroom--install--20260925", "961fd521"),
    ("headroom--use--20260925", "fa85efe2"),
    ("inspect-ai--install--20260926-2", "80557426"),
    ("inspect-ai--install--20260926-2", "b4dedcdd"),
    ("jcodemunch-mcp--install--20260925", "5877b20c"),
    ("jcodemunch-mcp--use--20260925-2", "34c20deb"),
    ("jcodemunch-mcp--use--20260925", "34c20deb"),
    ("lean--use--20260925", "c8ba2c2e"),
    ("llama-cpp--use--20260926", "1d805524"),
    ("llama-cpp--use--20260926", "319dc1d1"),
    ("llama-cpp--use--20260926", "5f804ec8"),
    ("loki--install--20260925", "bbd36e86"),
    ("loki--use--20260925", "a1507073"),
    ("markitdown--install--20260925", "e7028064"),
    ("markitdown--use--20260925", "c7336eaa"),
    ("mcporter--install--20260925", "727164f8"),
    ("mcporter--use--20260925-2", "158be834"),
    ("mcporter--use--20260925-3", "158be834"),
    ("mcporter--use--20260925", "158be834"),
    ("opentelemetry-collector-contrib--install--20260925", "b7673dbd"),
    ("opentelemetry-collector-contrib--use--20260925", "1aa15f5a"),
    ("otel-tui--install--20260925", "c7079147"),
    ("poppler--install--20260925", "808755c0"),
    ("poppler--install--20260926", "3d5fab47"),
    ("poppler--use--20260925-2", "c3ae1404"),
    ("poppler--use--20260925", "77ce0ea0"),
    ("prometheus--install--20260925", "14fe0136"),
    ("prometheus--use--20260925", "51e0e7f1"),
    ("promptfoo--install--20260926-2", "23d213e6"),
    ("promptfoo--install--20260926-2", "a0827c1c"),
    ("promptfoo--install--20260926", "a11cd6b0"),
    ("qdrant--install--20260925", "e53d55b8"),
    ("qdrant--recovery--20260925", "bfb11564"),
    ("qmd--install--20260925", "66452f6d"),
    ("qmd--use--20260925", "44937a7c"),
    ("qmd--use--20260925", "d0f8ea5b"),
    ("repomix--install--20260925", "904edca9"),
    ("repomix--use--20260925-2", "5aad2472"),
    ("repomix--use--20260925", "5aad2472"),
    ("restic--install--20260925", "8a144369"),
    ("restic--recovery--20260925", "d6d064f9"),
    ("restic--use--20260925", "d6d064f9"),
    ("rtk--install--20260925", "4421f231"),
    ("rtk--use--20260925-2", "18487089"),
    ("rtk--use--20260925-2", "359e02bb"),
    ("rtk--use--20260925-3", "18487089"),
    ("rtk--use--20260925-3", "319ce38f"),
    ("rtk--use--20260925", "4421f231"),
    ("sandbox-runtime--use--20260925", "6c42c8df"),
    ("serena--install--20260925", "20a66e37"),
    ("serena--use--20260925-2", "e4fc3645"),
    ("serena--use--20260925", "e4fc3645"),
    ("socraticode--install--20260925", "427dfdf7"),
    ("socraticode--use--20260925-2", "4e5653f7"),
    ("socraticode--use--20260925-2", "69d84377"),
    ("socraticode--use--20260925", "2664724e"),
    ("socraticode--use--20260925", "4e5653f7"),
    ("syft--install--20260925", "fe81d2d1"),
    ("syft--use--20260925", "94fae0c9"),
    ("syft--use--20260925", "ae97df60"),
    ("toon--install--20260925", "b27f3540"),
    ("toon--use--20260925-2", "224f261f"),
    ("toon--use--20260925", "224f261f"),
    ("vllm--install--20260925", "a23199cb"),
    ("vllm--use--20260925-2", "ab46ba7b"),
    ("vllm--use--20260925-2", "c30eaa1b"),
    ("vllm--use--20260925-3", "ab46ba7b"),
    ("vllm--use--20260925-3", "c30eaa1b"),
    ("vllm--use--20260925-4", "978388bb"),
    ("vllm--use--20260925-4", "ab46ba7b"),
    ("vllm--use--20260925-4", "c30eaa1b"),
    ("vllm--use--20260925", "ab46ba7b"),
    ("worktrunk--install--20260925", "05bc4403"),
    ("worktrunk--use--20260925", "1b6e8782"),
    ("zizmor--install--20260925", "a25ab153"),
    ("zizmor--use--20260925", "580e1e17"),
))
OUTSIDE_THE_AUDIT = frozenset({
    ("blueprints/trials-20260926/byterover-cli/retained-outputs.json", "sha256", "549e503b"),
    ("evidence/artifacts/native-skill-lifecycle-20260930/receipt.json", "final_sha256", "cc707baf"),
    ("evidence/artifacts/skills-trials-20261009/native/native-results.json", "sha256", "55b5ad93"),
    ("evidence/artifacts/skills-trials-20261009/native/native-results.json", "sha256", "9db79be8"),
    ("evidence/artifacts/skills-trials-20261009/publication-redaction.json", "original_sha256", "55b5ad93"),
    ("evidence/artifacts/skills-trials-20261009/publication-redaction.json", "original_sha256", "9db79be8"),
    ("evidence/artifacts/skills-trials-20261009/publication-redaction.json", "original_sha256", "c4a6249b"),
    ("evidence/artifacts/skills-trials-20261009/publication-redaction.json", "original_sha256", "c8b28445"),
    ("evidence/artifacts/skills-trials-20261009/publication-redaction.json", "original_sha256", "ea4e2998"),
    ("evidence/artifacts/skills-trials-20261009/publication-redaction.json", "original_sha256", "f7fa1723"),
})
LEGACY_SITES = LEGACY_HOST_RECEIPTS | OUTSIDE_THE_AUDIT
LEGACY_COUNT = 106  # the count at the freeze; lower it with each site fixed, never raise it

# The sites this test was added with re-derived over the published bytes, by the digest's first 8 hex digits.
FIXED_SITES = (
    ("evidence/artifacts/sota-refresh-20260925/markitdown/results.json", "run_copy_sha256", "98299a10"),
    ("evidence/artifacts/sota-refresh-20260925/markitdown/results.json", "run_copy_sha256", "6134751a"),
    ("evidence/artifacts/sota-refresh-20260925/mcporter/results.json", "run_copy_sha256", "689a0ba4"),
    ("evidence/artifacts/sota-refresh-20260925/mcporter/results.json", "run_copy_sha256", "b48758aa"),
    ("evidence/artifacts/sota-refresh-20260925/mcporter/results.json", "run_copy_sha256", "54f9f581"),
    ("evidence/artifacts/sota-refresh-20260925/rtk/results.json", "run_copy_sha256", "388552e4"),
    ("evidence/artifacts/workstation-lane-20260925/nemotron-qualification/withdrawn/"
     "nativestack-5975wx-20260925--vllm--use--20260925-2.withdrawn.json", "output_sha256", "f24f21c2"),
    ("evidence/artifacts/workstation-lane-20260925/nemotron-qualification/withdrawn/"
     "nativestack-5975wx-20260925--vllm--use--20260925-2.withdrawn.json", "output_sha256", "2d37f307"),
    ("blueprints/retrieval-quality-v2/review-293-repro-20260926.json", "as_run_sha256", "7aba596a"),
    ("blueprints/trials-20260926/byterover-cli/withdrawn-host-receipts/"
     "nativestack-5975wx-20260925--byterover-cli--install--20260926.json", "output_sha256", "eda25377"),
)


def prohibited_names() -> tuple[str, ...]:
    """host_names() under PUBLISHED_DIGEST_GUARD_HOST_NAMES=1 (raising when a source is unavailable), else the comma-separated
    LANDING_PROHIBITED_NAMES; read when the test runs, blank entries dropped, never printed."""
    if os.environ.get(HOST_NAMES_SWITCH) == "1":
        from scripts import host_name_scan
        return tuple(dict.fromkeys(name for name in host_name_scan.host_names(ROOT) if name))
    return tuple(name for name in (part.strip() for part in os.environ.get(NAMES_VARIABLE, "").split(",")) if name)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(text: str) -> bytes | None:
    """The recorder's encoding of a published string (UTF-8, surrogateescape); None when a lone surrogate cannot be encoded."""
    try:
        return text.encode("utf-8", "surrogateescape")
    except UnicodeEncodeError:
        return None


def carries_mask(data: bytes) -> bool:
    return any(mask in data for mask in MASK_BYTES)


def text_carries_mask(text: str) -> bool:
    """carries_mask for a JSON string; most strings hold none of the masks' first characters and are skipped unencoded."""
    return any(start in text for start in MASK_STARTS) and any(mask in text for mask in MASKS)


def unmasked(data: bytes, names: tuple[str, ...]) -> set[bytes]:
    """``data`` with the masks it carries left alone or put back everywhere, for each name; never ``data`` itself."""
    present = sorted((mask for mask in MASKS if mask.encode() in data), key=len, reverse=True)
    if len(present) <= ALL_SUBSETS_UP_TO:
        choices = list(itertools.product((False, True), repeat=len(present)))
    else:
        choices = [(True,) * len(present), *(tuple(i == j for j in range(len(present))) for i in range(len(present)))]
    windows = WINDOWS_HOME_PREFIXES if any(mask in WINDOWS_HOME_MASKS for mask in present) else ("",)
    variants = set()
    for name in names:
        for prefix, windows_prefix in itertools.product(HOME_PREFIXES, windows):
            values = {mask: (prefix + name if mask in HOME_MASKS else windows_prefix + name if mask in WINDOWS_HOME_MASKS
                             else name).encode() for mask in present}
            for chosen in choices:
                variant = data
                for mask, put_back in zip(present, chosen):
                    if put_back:
                        variant = variant.replace(mask.encode(), values[mask])
                variants.add(variant)
    variants.discard(data)
    return variants


@functools.lru_cache(maxsize=None)
def text_digests(text: str, names: tuple[str, ...]) -> tuple[str, frozenset[str]] | None:
    """(digest of the published text, digests of its unmasked variants with and without a trailing newline)."""
    data = encoded(text)
    if data is None:
        return None
    return sha256(data), frozenset(sha256(variant + ending) for variant in unmasked(data, names) for ending in (b"", b"\n"))


@functools.lru_cache(maxsize=None)
def file_digests(path: str, names: tuple[str, ...]) -> tuple[str, frozenset[str]] | None:
    """(digest of the file, digests of its unmasked variants), or None for a missing, binary, huge or mask-free file."""
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return None
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        return None
    if b"\0" in data[:8192] or not carries_mask(data):
        return None
    return sha256(data), frozenset(sha256(variant) for variant in unmasked(data, names))


@functools.lru_cache(maxsize=None)
def resolve(ref: str, directory: str, root: str) -> str | None:
    """``ref`` as an existing file under ``root``, against the JSON file's directory first, then the checkout root."""
    for base in (directory, root):
        candidate = os.path.normpath(os.path.join(base, ref))
        if (candidate == root or candidate.startswith(root + os.sep)) and os.path.isfile(candidate):
            return candidate
    return None


def is_oracle(digest: str, texts: list[str], refs: list[str], *, root: Path, directory: Path,
              names: tuple[str, ...]) -> bool:
    """True when ``digest`` hashes no published text or named file but does hash one of them unmasked."""
    published, hidden = set(), set()
    for text in texts:
        digests = text_digests(text, names)
        if digests is not None:
            published.add(digests[0])
            hidden.update(digests[1])
    for ref in refs:
        candidate = resolve(ref, str(directory), str(root))
        digests = file_digests(candidate, names) if candidate else None
        if digests is not None:
            published.add(digests[0])
            hidden.update(digests[1])
    return digest not in published and digest in hidden


def findings(root: Path, names: tuple[str, ...], subdirs: tuple[str, ...] = SCANNED) -> set[tuple[str, str, str]]:
    """(path, key, first 8 hex digits) for every published digest that hashes unmasked bytes; never the bytes or a name."""
    root = Path(os.path.normpath(root))
    found = set()

    def walk(value, enclosing, relative, directory):
        if isinstance(value, dict):
            texts = [item for item in value.values() if isinstance(item, str) and text_carries_mask(item)]
            refs = [item for key, item in value.items() if isinstance(item, str) and key.lower() in FILE_KEYS]
            candidates = (texts + enclosing[0], refs + enclosing[1])
            for key, item in value.items():
                if isinstance(item, str) and DIGEST.fullmatch(item) and (candidates[0] or candidates[1]) and is_oracle(
                        item, *candidates, root=root, directory=directory, names=names):
                    found.add((relative, key, item[:8]))
            for item in value.values():
                walk(item, (texts, refs), relative, directory)
        elif isinstance(value, list):
            for item in value:
                walk(item, enclosing, relative, directory)

    for subdir in subdirs:
        for directory, directories, files in os.walk(root / subdir):
            directories.sort()
            for name in sorted(files):
                if not name.endswith(".json"):
                    continue
                path = Path(directory) / name
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                except (UnicodeDecodeError, ValueError, OSError):
                    continue
                walk(value, ([], []), path.relative_to(root).as_posix(), Path(directory))
    return found


def holders(path: Path, key: str, prefix: str) -> list[dict]:
    """The objects in the JSON file at ``path`` whose ``key`` is a digest starting with ``prefix``."""
    found = []

    def walk(value):
        if isinstance(value, dict):
            if isinstance(value.get(key), str) and DIGEST.fullmatch(value[key]) and value[key].startswith(prefix):
                found.append(value)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(json.loads(path.read_text(encoding="utf-8")))
    return found


def listed(sites) -> list[str]:
    return sorted(" ".join(site) for site in sites)


def readiness_receipt_pins(document) -> list[tuple[str, str]]:
    """(path, digest) for each repo:<receipt>@<digest> binding in readiness.json: the key, its entry's sha256 and expected_sha256,
    and every repo-rooted object under a "receipt" key that names one of those receipts."""
    keyed, nested = [], []

    def walk(value, parent_key):
        if isinstance(value, dict):
            if parent_key == "receipt" and value.get("root") == "repo" and isinstance(value.get("path"), str) \
                    and isinstance(value.get("sha256"), str):
                nested.append((value["path"], value["sha256"]))
            for key, item in value.items():
                match = READINESS_BINDING.fullmatch(key)
                if match:
                    keyed.append(match.groups())
                    if isinstance(item, dict):
                        keyed.extend((match.group(1), item[field]) for field in ("sha256", "expected_sha256")
                                     if isinstance(item.get(field), str))
                walk(item, key)
        elif isinstance(value, list):
            for item in value:
                walk(item, parent_key)

    walk(document, None)
    receipts = {path for path, _ in keyed}
    return keyed + [pin for pin in nested if pin[0] in receipts]


def changed_since_merge_base(root: Path) -> set[str] | None:
    """Tracked paths that differ between the merge base of HEAD and origin/main and the working tree, or None without history."""
    try:
        base = subprocess.run(["git", "merge-base", "HEAD", "refs/remotes/origin/main"], cwd=root, capture_output=True,
                              text=True, check=True).stdout.strip()
        listing = subprocess.run(["git", "diff", "--name-only", "-z", base, "--"], cwd=root, capture_output=True,
                                 check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return {path.decode("utf-8", "surrogateescape") for path in listing.split(b"\0") if path}


def stale_readiness_pins(root: Path, changed: set[str]) -> list[str]:
    """``path prefix`` for each readiness binding of a changed receipt whose digest is not the receipt's current sha256."""
    document = json.loads((root / READINESS).read_text(encoding="utf-8"))
    current = {}
    stale = []
    for path, digest in readiness_receipt_pins(document):
        if path not in changed:
            continue
        if path not in current:
            current[path] = sha256((root / path).read_bytes()) if (root / path).is_file() else None
        if digest != current[path]:
            stale.append(f"{path} {digest[:8]}")
    return sorted(stale)


class PublishedDigestPrivacyTests(unittest.TestCase):
    maxDiff = None  # the messages are path, key and an 8-hex prefix only

    def test_no_unlisted_published_digest_hashes_unmasked_bytes(self):
        names = prohibited_names()
        if not names:
            self.skipTest(f"neither {HOST_NAMES_SWITCH}=1 nor {NAMES_VARIABLE} is set: this is a local and pre-push guard "
                          "(CI has no host names)")
        found = findings(ROOT, names)
        self.assertEqual(listed(found - LEGACY_SITES), [],
                         "a new published digest hashes its text or file with a masked home directory or name put back")
        missing = LEGACY_SITES - found
        if missing:  # another clone's names: reported, never a failure (test_the_frozen_list_only_shrinks needs no names)
            print(f"published-digest guard: {len(missing)} of {len(LEGACY_SITES)} frozen sites not reproduced with these names",
                  file=sys.stderr)

    def test_the_frozen_list_only_shrinks(self):
        self.assertEqual(len(LEGACY_SITES), LEGACY_COUNT)
        self.assertEqual(len(LEGACY_HOST_RECEIPTS), 96)
        self.assertFalse(LEGACY_HOST_RECEIPTS & OUTSIDE_THE_AUDIT)
        gone = [site for site in LEGACY_SITES if not (ROOT / site[0]).is_file() or not holders(ROOT / site[0], *site[1:])]
        self.assertEqual(listed(gone), [], "a frozen site is gone: remove it from the list and lower LEGACY_COUNT")

    def test_the_fixed_sites_hash_the_published_bytes(self):
        for relative, key, prefix in FIXED_SITES:
            with self.subTest(site=f"{relative} {key} {prefix}"):
                path = ROOT / relative
                entries = holders(path, key, prefix)
                self.assertEqual(len(entries), 1)
                entry = entries[0]
                if "output_excerpt" in entry:
                    published = sha256(entry["output_excerpt"].encode("utf-8", "surrogateescape"))
                else:
                    published = sha256((path.parent / entry["path"]).read_bytes())
                self.assertEqual(entry[key], published)


class ReadinessPinTests(unittest.TestCase):
    """A receipt that changes must not leave its old sha256 in readiness.json: rebuilt from a guess, the old receipt would
    confirm the guess against that pin (#1010 B1). Needs no names; skips without origin/main."""

    def test_readiness_pins_of_receipts_changed_since_the_merge_base_hash_their_current_bytes(self):
        changed = changed_since_merge_base(ROOT)
        if changed is None:
            self.skipTest("needs HEAD and refs/remotes/origin/main to find the merge base")
        self.assertEqual(stale_readiness_pins(ROOT, changed), [],
                         f"{READINESS} still pins an earlier sha256 of a receipt this branch changes")

    def test_every_binding_form_is_read(self):
        digest, other = "a" * 64, "b" * 64
        document = {"receipts": {f"repo:evidence/receipts/r.json@{digest}": {"sha256": digest, "expected_sha256": digest},
                                 "evidence": {"path": "manifests/evidence.json", "root": "repo", "sha256": other}},
                    "gates": [{"kind": {"receipt": {"path": "evidence/receipts/r.json", "root": "repo", "sha256": other}},
                               "receipt": {"path": "evidence/receipts/r.json", "root": "repo", "sha256": digest}}]}
        self.assertEqual(sorted(readiness_receipt_pins(document)),
                         sorted([("evidence/receipts/r.json", digest)] * 4 + [("evidence/receipts/r.json", other)]))


class SyntheticOracleTests(unittest.TestCase):
    """The detector on scratch trees with a synthetic account; these run in CI too."""

    NAME = "example"
    HOME = HOME_PREFIXES[0] + NAME
    EXCERPT = "root ~/.local/share/models/m by <user>\n"

    def scan(self, files: dict[str, object], subdirs: tuple[str, ...] = SCANNED) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative, content in files.items():
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, bytes):
                    (root / relative).write_bytes(content)
                else:
                    (root / relative).write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
            for cached in (file_digests, text_digests, resolve):
                cached.cache_clear()
            return listed(findings(root, (self.NAME,), subdirs))

    def raw(self, text: str) -> str:
        return text.replace("~", self.HOME).replace("<user>", self.NAME)

    def receipt(self, digest: str, excerpt: str = EXCERPT) -> dict[str, object]:
        return {"commands": [{"cmd": "c", "output_sha256": digest, "output_excerpt": excerpt}]}

    def test_a_digest_of_the_raw_output_is_found_with_or_without_a_trailing_newline(self):
        digest = sha256(self.raw(self.EXCERPT).encode())
        for excerpt in (self.EXCERPT, self.EXCERPT.rstrip("\n")):
            with self.subTest(published_newline=excerpt.endswith("\n")):
                self.assertEqual(self.scan({"evidence/hosts/h/r.json": self.receipt(digest, excerpt)}),
                                 [f"evidence/hosts/h/r.json output_sha256 {digest[:8]}"])

    def test_the_recorders_digest_of_the_published_excerpt_passes(self):
        digest = hashlib.sha256(self.EXCERPT.encode("utf-8", "surrogateescape")).hexdigest()
        self.assertEqual(self.scan({"evidence/hosts/h/r.json": self.receipt(digest)}), [])

    def test_one_mask_put_back_while_another_stays_is_found(self):
        digest = sha256(self.EXCERPT.replace("<user>", self.NAME).encode())
        self.assertEqual(len(self.scan({"evidence/artifacts/r.json": self.receipt(digest)})), 1)

    def test_a_run_copy_digest_of_the_unmasked_file_is_found_and_the_published_digest_passes(self):
        published = b"installed to ~/.local/bin\n"
        for run_copy in (published.replace(b"~", self.HOME.encode()), published):
            with self.subTest(unmasked=run_copy != published):
                entry = {"path": "out/install.log", "sha256": sha256(published), "run_copy_sha256": sha256(run_copy)}
                expected = [f"blueprints/u/results.json run_copy_sha256 {sha256(run_copy)[:8]}"] if run_copy != published else []
                self.assertEqual(self.scan({"blueprints/u/results.json": {"files": [entry]},
                                            "blueprints/u/out/install.log": published}), expected)

    def test_a_private_original_digest_below_its_path_and_other_home_masks_are_found(self):
        for mask in ("<host-home>", "<home>", "$HOME"):
            with self.subTest(mask=mask):
                published = f"cache at {mask}/.cache/tool\n".encode()
                original = sha256(published.replace(mask.encode(), self.HOME.encode()))
                entry = {"path": "out/tool.log", "private_original": {"name": "tool.log", "sha256": original},
                         "published": {"sha256": sha256(published)}}
                self.assertEqual(self.scan({"evidence/artifacts/t/retained.json": {"outputs": [entry]},
                                            "evidence/artifacts/t/out/tool.log": published}),
                                 [f"evidence/artifacts/t/retained.json sha256 {original[:8]}"])

    def test_a_macos_home_is_put_back_too(self):
        digest = sha256(self.EXCERPT.replace("~", HOME_PREFIXES[1] + self.NAME).encode())
        self.assertEqual(len(self.scan({"manifests/r.json": self.receipt(digest)})), 1)

    def test_only_the_scanned_directories_are_walked(self):
        digest = sha256(self.raw(self.EXCERPT).encode())
        self.assertEqual(self.scan({"docs/r.json": self.receipt(digest)}), [])
        self.assertEqual(len(self.scan({"docs/r.json": self.receipt(digest)}, ("docs",))), 1)

    def test_windows_profile_account_and_host_masks_are_put_back(self):
        for mask, value in (("%USERPROFILE%", "C:\\Users\\" + self.NAME), ("%USERPROFILE%", "/mnt/c/Users/" + self.NAME),
                            ("<WSL_USER>", self.NAME), ("<hostname>", self.NAME), ("<user-home>", self.HOME),
                            ("<SCRATCH_HOME>", self.HOME)):
            with self.subTest(mask=mask, value=value.replace(self.NAME, "<name>")):
                excerpt = f"profile {mask}/cache\n"
                digest = sha256(excerpt.replace(mask, value).encode())
                self.assertEqual(len(self.scan({"evidence/artifacts/r.json": self.receipt(digest, excerpt)})), 1)

    def test_names_are_comma_separated_with_blank_entries_dropped(self):
        with mock.patch.dict(os.environ, {NAMES_VARIABLE: " , a ,, b ", HOST_NAMES_SWITCH: "0"}):
            self.assertEqual(prohibited_names(), ("a", "b"))
        with mock.patch.dict(os.environ, {NAMES_VARIABLE: "", HOST_NAMES_SWITCH: "0"}):
            self.assertEqual(prohibited_names(), ())

    def test_the_host_names_switch_reads_the_repository_source(self):
        from scripts import host_name_scan
        fixture = {HOST_NAMES_SWITCH: "1", NAMES_VARIABLE: "ignored"}
        with mock.patch.dict(os.environ, {**fixture, host_name_scan.OVERRIDE: '["fixture_a", "fixture_b", "fixture_a"]'}):
            self.assertEqual(prohibited_names(), ("fixture_a", "fixture_b"))
        with mock.patch.dict(os.environ, {**fixture, host_name_scan.OVERRIDE: "invalid-json"}):
            with self.assertRaises(host_name_scan.HostNameScanError):
                prohibited_names()


if __name__ == "__main__":
    unittest.main()
