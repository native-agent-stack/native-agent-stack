"""A receipt's `*_sha256` key binds bytes anyone can check: a tracked repository file or a named public artifact (correction #161).

tests/test_provenance_digest_custody.py checks the digests in `provenance` lists. The Claude read of #1060 at e3933560 (verdict
CHANGES_REQUESTED, P1) found two keys outside such a list, `control_uv_lock_sha256` and `new_uv_lock_sha256` in
evidence/receipts/osv-openhands-oauthlib-relock-20261013.json, that hashed scratch uv.lock files no repository file holds, and that check
never reached them. docs/decisions/2026-10-12-harbor-parallel-runtimes.md ("Custody of the run originals") publishes a digest only of
bytes in the repository: the repository is public, and a digest of unpublished bytes lets a guessed path or name be confirmed offline
while nothing shows which bytes it covers.

findings() walks every JSON file under RECEIPTS. A string under a key that ends in `_sha256` and is 64 lowercase hex characters must
- be the sha256 of a tracked regular file (git ls-files; a symlink or an untracked file does not count), or
- name a public artifact: the same object holds an https URL under `url` or under a key of the digest's own prefix (`<prefix>_url`,
  `<prefix>_published_source`), or a tracked pin record (PIN_RECORD: a pins.json or pins-*.json file, or a workflow under
  .github/workflows/) carries the same digest.
A digest that only another evidence file repeats, as #1060's relock output did, stays unresolved. LEGACY freezes the receipts that predate
the check with their count of unresolved keys: a count may fall, and must then be lowered here, but never rise, and any other receipt
fails on its first unresolved key. Findings name the file and its key paths, never a digest.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = "evidence/receipts"
DIGEST = re.compile(r"[0-9a-f]{64}")
PIN_RECORD = re.compile(r"(?:\A|/)pins(?:-[^/]*)?\.json\Z|\A\.github/workflows/[^/]+\.ya?ml\Z")
OAUTHLIB_RECEIPT = "evidence/receipts/osv-openhands-oauthlib-relock-20261013.json"

LEGACY = {
    # file -> keys ending in _sha256 whose digest hashes no tracked file and names no public artifact, at the freeze (#1060)
    "evidence/receipts/adoption-macos-hosted-smoke-20260922.json": 6,
    "evidence/receipts/adoption-macos-hosted-smoke-20260923.json": 1,
    "evidence/receipts/ai-memory-240-qualification-20260925.json": 2,
    "evidence/receipts/ai-memory-241-qualification-20260925.json": 1,
    "evidence/receipts/ao-bounded-effect-20261008.json": 11,
    "evidence/receipts/ao-bounded-feedback-20261008.json": 11,
    "evidence/receipts/ao-orchestration-landscape-20261008.json": 2,
    "evidence/receipts/artifact-reductions.json": 1,
    "evidence/receipts/canary-proof-verification-20261001.json": 1,
    "evidence/receipts/catalog-clean-install-20260921.json": 1,
    "evidence/receipts/claude-advisor-usage-scan-20260928.json": 1,
    "evidence/receipts/claude-host-practice-readback-20260928.json": 1,
    "evidence/receipts/claude-hud-0100-qualification-20261003.json": 4,
    "evidence/receipts/claude-max-default-effort-20260929.json": 4,
    "evidence/receipts/claude-selective-context-pilot-20260921.json": 15,
    "evidence/receipts/claude-spend-window-20261004.json": 5,
    "evidence/receipts/codex-01571-qualification-20260926.json": 1,
    "evidence/receipts/codex-01592-qualification-20260930.json": 5,
    "evidence/receipts/codex-desktop-live-20260920.json": 1,
    "evidence/receipts/codex-serena-startup-port-20261003.json": 149,
    "evidence/receipts/codex-session-environment-20260920.json": 4,
    "evidence/receipts/current-session-observation-20260920.json": 22,
    "evidence/receipts/dagu-mise-pin-qualification-20261005.json": 3,
    "evidence/receipts/decision-record-index-20261008.json": 2,
    "evidence/receipts/dependabot-alert-16-dismissal-20261003.json": 1,
    "evidence/receipts/desktop-direct-rag.json": 1,
    "evidence/receipts/foundation-catalog-ui-20260920.json": 2,
    "evidence/receipts/foundation-native-20260920.json": 5,
    "evidence/receipts/guard-k3-verification-20260930.json": 2,
    "evidence/receipts/guard-k4-verification-20261001.json": 4,
    "evidence/receipts/harbor-e2e-token-tools-20260930.json": 22,
    "evidence/receipts/headroom-039-qualification-20260925.json": 1,
    "evidence/receipts/hindsight-research-memory-20261008.json": 1,
    "evidence/receipts/ibkr-readonly-acceptance-20261005.json": 13,
    "evidence/receipts/jcodemunch-1108327-qualification-20261003.json": 4,
    "evidence/receipts/mcp-inspector-280-qualification-20260926.json": 1,
    "evidence/receipts/mcp-inspector-290-qualification-20261003.json": 4,
    "evidence/receipts/mcporter-0141-qualification-20260925.json": 1,
    "evidence/receipts/mcporter-0142-qualification-20261003.json": 4,
    "evidence/receipts/native-catalog-retrieval-20260920.json": 6,
    "evidence/receipts/native-claude-profile-20260920.json": 1,
    "evidence/receipts/native-dagu-retry-tests-20260920.json": 4,
    "evidence/receipts/native-dashboard-access-20260921.json": 2,
    "evidence/receipts/native-dashboard-data-20260921.json": 4,
    "evidence/receipts/native-harness-defaults-20260920.json": 3,
    "evidence/receipts/native-jcodemunch-20260920.json": 2,
    "evidence/receipts/native-linux-zizmor-20260920.json": 1,
    "evidence/receipts/native-nautilus-ci-20260920.json": 4,
    "evidence/receipts/native-nautilus-v2-20260920.json": 4,
    "evidence/receipts/native-offhost-app-state-20260920.json": 6,
    "evidence/receipts/native-offhost-restic-20260920.json": 1,
    "evidence/receipts/native-quality-defaults-20260920.json": 5,
    "evidence/receipts/native-returned-results-20260921.json": 1,
    "evidence/receipts/native-sandbox-codex-binding-20261008.json": 5,
    "evidence/receipts/native-sandbox-network-20260920.json": 1,
    "evidence/receipts/native-service-reboot-20260920.json": 3,
    "evidence/receipts/native-session-defaults-20260920.json": 45,
    "evidence/receipts/native-tavily-cli-20260920.json": 1,
    "evidence/receipts/native-tavily-session-20260920.json": 11,
    "evidence/receipts/native-token-ci-github-20260920.json": 36,
    "evidence/receipts/native-token-ci-local-20260920.json": 35,
    "evidence/receipts/native-token-clean-prefix-20260920.json": 27,
    "evidence/receipts/native-token-stack-final-20260920.json": 22,
    "evidence/receipts/native-trading-runtime-2604-20261004.json": 10,
    "evidence/receipts/nextjs-1638-qualification-20261001.json": 1,
    "evidence/receipts/omniroute-claude-callsite-20260930.json": 2,
    "evidence/receipts/omniroute-runtime-enhancements-20260930.json": 13,
    "evidence/receipts/omniroute-runtime-workers-20260930.json": 5,
    "evidence/receipts/omniroute-sdk-worker-0160-20261003.json": 5,
    "evidence/receipts/openresearch-0215-qualification-20261003.json": 4,
    "evidence/receipts/osv-openhands-fsspec-relock-20261005.json": 2,
    "evidence/receipts/osv-openhands-litellm-relock-20260930.json": 1,
    "evidence/receipts/osv-openhands-pyjwt-relock-20260930.json": 3,
    "evidence/receipts/osv-split-hardening-port-20261003.json": 2,
    "evidence/receipts/osv-urllib3-next-20260930.json": 4,
    "evidence/receipts/otelcol-contrib-0162-qualification-20261003.json": 4,
    "evidence/receipts/playwright-cli-0122-qualification-20261003.json": 4,
    "evidence/receipts/portable-userspace-install-20260921.json": 2,
    "evidence/receipts/row70-records-b-e-20261008.json": 1,
    "evidence/receipts/rtk-050-qualification-20260925.json": 3,
    "evidence/receipts/rtk-fold-harbor-20261004.json": 3,
    "evidence/receipts/runtime-final-native-24-acceptance-20261008.json": 2,
    "evidence/receipts/skills-listing-restore-20260928.json": 4,
    "evidence/receipts/skills-m4-host-removal-20260928.json": 10,
    "evidence/receipts/socraticode-1160-qualification-20260929.json": 1,
    "evidence/receipts/sota-convergence-20260922.json": 7,
    "evidence/receipts/syft-1540-qualification-20261003.json": 4,
    "evidence/receipts/terminal-experience-20260928.json": 1,
    "evidence/receipts/token-native-retained-functional-20260920.json": 1,
    "evidence/receipts/token-practice-confirmation-20260920.json": 3,
    "evidence/receipts/token-practice-gap-followup-20260920.json": 2,
    "evidence/receipts/token-practice-native-pairs-20260920.json": 4,
    "evidence/receipts/trading-unattended-hosting-recovery-r2-20261005.json": 1,
    "evidence/receipts/trading-unattended-hosting-recovery-r3-20261005.json": 29,
    "evidence/receipts/upstream-native-tools-20260920.json": 5,
    "evidence/receipts/vllm-030-switch-20260925.json": 2,
    "evidence/receipts/vllm-030-switch-laptop-20260926.json": 2,
    "evidence/receipts/vllm-compatibility.json": 1,
    "evidence/receipts/worktrunk-0800-qualification-20261003.json": 4,
}
LEGACY_ENTRIES = 702  # the sum at the freeze; lower it with each entry fixed, never raise it


def tracked_files(root: Path) -> list[str]:
    """Repository-relative paths that git tracks; raises when git cannot list them, so the check fails closed."""
    listing = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True)
    return [name for name in listing.stdout.decode("utf-8", "surrogateescape").split("\0") if name]


def checkable_digests(root: Path, tracked: list[str]) -> tuple[set[str], set[str]]:
    """The sha256 of every tracked regular file, and every digest that a tracked pin record carries."""
    files, pinned = set(), set()
    for name in tracked:
        path = root / name
        if path.is_symlink() or not path.is_file():
            continue
        data = path.read_bytes()
        files.add(hashlib.sha256(data).hexdigest())
        if PIN_RECORD.search(name):
            pinned.update(DIGEST.findall(data.decode("utf-8", "replace")))
    return files, pinned


def names_public_artifact(key: str, holder: dict) -> bool:
    """The same object holds an https URL under `url` or under a key of the digest's own prefix, such as `<prefix>_url` or
    `<prefix>_published_source` (the Harbor receipt's `wheel_published_source` beside its `wheel_sha256`)."""
    prefix = key[: -len("sha256")]
    return any(isinstance(value, str) and value.startswith("https://") and (name == "url" or (name.startswith(prefix) and name != key))
               for name, value in holder.items())


def unresolved_keys(node, files: set[str], pinned: set[str], path: str = "") -> list[str]:
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else str(key)
            if (isinstance(key, str) and key.endswith("_sha256") and isinstance(value, str) and DIGEST.fullmatch(value)
                    and value not in files and value not in pinned and not names_public_artifact(key, node)):
                found.append(here)
            found += unresolved_keys(value, files, pinned, here)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found += unresolved_keys(value, files, pinned, f"{path}[{index}]")
    return found


def findings(root: Path, tracked: list[str] | None = None) -> dict[str, list[str]]:
    """Repository-relative receipt -> key paths whose digest no one can check, for the receipts that have any."""
    files, pinned = checkable_digests(root, tracked_files(root) if tracked is None else tracked)
    found = {}
    for directory, _, names in os.walk(root / RECEIPTS):
        for name in sorted(names):
            if not name.endswith(".json"):
                continue
            path = Path(directory) / name
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            keys = unresolved_keys(document, files, pinned)
            if keys:
                found[path.relative_to(root).as_posix()] = keys
    return found


class ReceiptSha256KeyCustodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found = findings(ROOT)

    def test_no_receipt_sha256_key_lacks_a_checkable_preimage(self):
        unlisted = {path: keys for path, keys in self.found.items() if len(keys) > LEGACY.get(path, 0)}
        self.assertEqual(
            unlisted, {},
            "receipt keys ending in _sha256 whose digest hashes no tracked file and names no public artifact (file: keys). "
            "Delete the digest and keep the original private, commit the bytes it hashes, or name the public artifact with an "
            "https URL under url or a <prefix>_ key, or in a pin record.",
        )

    def test_the_frozen_list_only_shrinks(self):
        stale = {path: (frozen, len(self.found.get(path, []))) for path, frozen in LEGACY.items()
                 if len(self.found.get(path, [])) < frozen}
        self.assertEqual(stale, {}, "lower these LEGACY counts (file: (frozen, found)); the list only shrinks")
        self.assertEqual(sum(LEGACY.values()), LEGACY_ENTRIES)

    def test_the_oauthlib_relock_receipt_publishes_no_scratch_digest(self):
        self.assertNotIn(OAUTHLIB_RECEIPT, LEGACY)
        self.assertNotIn(OAUTHLIB_RECEIPT, self.found)
        reproduction = json.loads((ROOT / OAUTHLIB_RECEIPT).read_text(encoding="utf-8"))["reproduction"]
        for key in ("control_uv_lock_sha256", "new_uv_lock_sha256"):
            self.assertNotIn(key, reproduction)


class SyntheticKeyCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.tracked = []

    def write(self, relative: str, content: bytes | str, tracked: bool = True) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        if tracked:
            self.tracked.append(relative)
        return path

    def scan(self, document) -> dict[str, list[str]]:
        self.write("evidence/receipts/fixture.json", json.dumps(document))
        return findings(self.root, self.tracked)

    def test_a_digest_of_unpublished_bytes_is_found(self):
        digest = hashlib.sha256(b"scratch uv.lock\n").hexdigest()
        self.assertEqual(self.scan({"reproduction": {"control_uv_lock_sha256": digest}}),
                         {"evidence/receipts/fixture.json": ["reproduction.control_uv_lock_sha256"]})

    def test_a_digest_that_only_another_evidence_file_repeats_is_found(self):
        digest = hashlib.sha256(b"scratch uv.lock\n").hexdigest()
        self.write("blueprints/recipe/evidence/relock.txt", f"{digest}  <scratch>/u3/new/uv.lock\n")
        self.assertEqual(self.scan({"new_uv_lock_sha256": digest}), {"evidence/receipts/fixture.json": ["new_uv_lock_sha256"]})

    def test_a_digest_of_a_tracked_file_passes(self):
        data = b"lock bytes\n"
        self.write("blueprints/recipe/requirements.lock", data)
        self.assertEqual(self.scan({"lock_sha256": hashlib.sha256(data).hexdigest()}), {})

    def test_an_untracked_file_or_a_symlink_is_not_a_preimage(self):
        data = b"scratch bytes\n"
        target = self.write("blueprints/recipe/scratch.lock", data, tracked=False)
        (self.root / "blueprints/recipe/link.lock").symlink_to(target)
        self.tracked.append("blueprints/recipe/link.lock")
        self.assertEqual(self.scan({"lock_sha256": hashlib.sha256(data).hexdigest()}),
                         {"evidence/receipts/fixture.json": ["lock_sha256"]})

    def test_a_named_public_artifact_passes(self):
        digest = hashlib.sha256(b"release asset\n").hexdigest()
        for holder in ({"binary_sha256": digest, "binary_url": "https://example.invalid/asset"},
                       {"binary_sha256": digest, "binary_published_source": "https://example.invalid/asset"},
                       {"binary_sha256": digest, "url": "https://example.invalid/asset"}):
            with self.subTest(keys=sorted(holder)):
                self.assertEqual(self.scan({"osv": holder}), {})

    def test_a_plain_http_or_an_unrelated_url_does_not_name_it(self):
        digest = hashlib.sha256(b"release asset\n").hexdigest()
        for holder in ({"binary_sha256": digest, "binary_url": "http://example.invalid/asset"},
                       {"binary_sha256": digest, "repository": "https://example.invalid/repository"},
                       {"binary_sha256": digest, "wheel_url": "https://example.invalid/other-asset"},
                       {"binary_sha256": digest, "binaryish_url": "https://example.invalid/other-asset"}):
            with self.subTest(keys=sorted(holder)):
                self.assertEqual(self.scan({"osv": holder}), {"evidence/receipts/fixture.json": ["osv.binary_sha256"]})

    def test_a_digest_a_pin_record_carries_passes(self):
        digest = hashlib.sha256(b"source archive\n").hexdigest()
        for record in ("blueprints/recipe/pins.json", "adoption/pins-linux-x86_64.json", ".github/workflows/scan.yml"):
            with self.subTest(record=record):
                self.tracked = []
                self.write(record, json.dumps({"source_archive": {"sha256": digest}}))
                self.assertEqual(self.scan({"sdk_source_archive_sha256": digest}), {})

    def test_only_keys_ending_in_sha256_that_hold_a_digest_are_checked(self):
        digest = hashlib.sha256(b"x\n").hexdigest()
        self.assertEqual(self.scan({"sha256": digest, "sha256_before": digest, "note_sha256": "not a digest",
                                    "rows": [{"sha256": digest}]}), {})

    def test_keys_are_found_at_any_depth_and_only_receipts_are_walked(self):
        digest = hashlib.sha256(b"y\n").hexdigest()
        expected = {"evidence/receipts/fixture.json": ["a[0].b.stdout_sha256"]}
        self.assertEqual(self.scan({"a": [{"b": {"stdout_sha256": digest}}]}), expected)
        self.write("evidence/artifacts/run/receipt.json", json.dumps({"stdout_sha256": digest}))
        self.write("docs/fixture.json", json.dumps({"stdout_sha256": digest}))
        self.assertEqual(findings(self.root, self.tracked), expected)


if __name__ == "__main__":
    unittest.main()
