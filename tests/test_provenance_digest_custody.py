"""A digest in a receipt's `provenance` list binds a repository file, never unpublished bytes (correction #161; #1047 P1).

tests/test_published_digest_privacy.py finds a digest that hashes unmasked bytes once a mask is put back. It cannot reach a
`provenance` entry whose preimage is not published at all, such as a run log, a Claude stream or a home-state snapshot kept in a
private tree: no mask can be put back, yet the digest still lets anyone confirm a guessed path or name offline, and nothing in the
repository shows which bytes it covers. The GPT read of #1047 found ten of them in a new receipt (verdict P1).

findings() walks every JSON file under SCANNED. In each `provenance` list, at any depth, an entry that holds a 64-hex string value
must name a repository file under one of FILE_KEYS, resolved against the JSON file's directory and then the checkout root, that
stays inside the checkout, and the file's sha256 must be that value. LEGACY freezes the receipts that predate the check with the
number of such entries each still has: a count may fall, and must then be lowered here, but never rise, and a file that is not
listed fails on its first unresolved entry. Findings are reported as file and count, never as a digest.
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
SCANNED = ("evidence", "blueprints", "manifests")
DIGEST = re.compile(r"[0-9a-f]{64}")
FILE_KEYS = ("path", "file", "log", "output_path", "raw_path", "capture")
HARBOR_RECEIPT = "evidence/receipts/harbor-smoke-20261012.json"
REGISTRATION_RECORD = "docs/decisions/2026-10-15-unrun-registration-rules.md"

LEGACY = {
    # file -> provenance digests that hash no published repository file, at the freeze (#1047)
    "evidence/receipts/artifact-reductions.json": 3,
    "evidence/receipts/codex-01592-qualification-20260930.json": 13,
    "evidence/receipts/component-history.json": 1,
    "evidence/receipts/desktop-cli-workflows.json": 5,
    "evidence/receipts/local-inference-c2-serving-switch-20260926.json": 2,
    "evidence/receipts/native-context-memory.json": 2,
    "evidence/receipts/native-memory.json": 1,
    "evidence/receipts/native-rag.json": 3,
    "evidence/receipts/runtime-tools.json": 3,
    "evidence/receipts/vllm-030-switch-20260925.json": 6,
    "evidence/receipts/vllm-030-switch-laptop-20260926.json": 2,
    "evidence/receipts/vllm-compatibility.json": 3,
}
LEGACY_ENTRIES = 44  # the sum at the freeze; lower it with each entry fixed, never raise it


def confined_file(base: Path, root: Path, reference: str) -> Path | None:
    """The regular file `reference` names under base, only if it stays inside root (no .., no absolute path, no symlink)."""
    if not reference or reference.startswith(("/", "\\")) or ".." in Path(reference.replace("\\", "/")).parts:
        return None
    candidate = base / reference
    try:
        inside = candidate.resolve().is_relative_to(root.resolve())
    except OSError:
        return None
    if not inside or candidate.is_symlink() or not candidate.is_file():
        return None
    return candidate


def resolves(entry: dict, directory: Path, root: Path, digest: str) -> bool:
    for key in FILE_KEYS:
        reference = entry.get(key)
        if not isinstance(reference, str) or reference.startswith(("http://", "https://")):
            continue
        for base in (directory, root):
            found = confined_file(base, root, reference)
            if found is not None and hashlib.sha256(found.read_bytes()).hexdigest() == digest:
                return True
    return False


def unresolved_in(node, directory: Path, root: Path) -> int:
    count = 0
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "provenance" and isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict):
                        for held in entry.values():
                            if isinstance(held, str) and DIGEST.fullmatch(held) and not resolves(entry, directory, root, held):
                                count += 1
            count += unresolved_in(value, directory, root)
    elif isinstance(node, list):
        for value in node:
            count += unresolved_in(value, directory, root)
    return count


def findings(root: Path, subdirs: tuple[str, ...] = SCANNED) -> dict[str, int]:
    """Repository-relative JSON file -> unresolved provenance digests, for files that have any."""
    found = {}
    for subdir in subdirs:
        for directory, _, names in os.walk(root / subdir):
            for name in sorted(names):
                if not name.endswith(".json"):
                    continue
                path = Path(directory) / name
                try:
                    document = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                count = unresolved_in(document, Path(directory), root)
                if count:
                    found[path.relative_to(root).as_posix()] = count
    return found


class ProvenanceDigestCustodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found = findings(ROOT)

    def test_no_provenance_digest_lacks_a_published_preimage(self):
        unlisted = {path: count for path, count in self.found.items() if count > LEGACY.get(path, 0)}
        self.assertEqual(
            unlisted, {},
            "provenance digests that hash no published repository file (file: count). Remove the digest and keep the "
            "original private, or publish a sanitized projection and hash those bytes, naming it under `path`.",
        )

    def test_the_frozen_list_only_shrinks(self):
        stale = {path: (frozen, self.found.get(path, 0)) for path, frozen in LEGACY.items() if self.found.get(path, 0) < frozen}
        self.assertEqual(stale, {}, "lower these LEGACY counts (file: (frozen, found)); the list only shrinks")
        self.assertEqual(sum(LEGACY.values()), LEGACY_ENTRIES)

    def test_the_harbor_receipt_digests_hash_the_files_it_publishes(self):
        receipt = json.loads((ROOT / HARBOR_RECEIPT).read_text(encoding="utf-8"))
        entries = receipt["provenance"]
        self.assertTrue(entries)
        for entry in entries:
            with self.subTest(name=entry.get("name")):
                self.assertRegex(entry["sha256"], DIGEST.pattern)
                self.assertTrue(resolves(entry, (ROOT / HARBOR_RECEIPT).parent, ROOT, entry["sha256"]))
        unpublished = json.dumps(receipt["unpublished_originals"])
        self.assertEqual(DIGEST.findall(unpublished), [], "the private originals carry no digest of any kind")

    def test_the_harbor_receipt_is_not_a_legacy_site(self):
        self.assertNotIn(HARBOR_RECEIPT, LEGACY)
        self.assertNotIn(HARBOR_RECEIPT, self.found)

    def test_registration_record_cites_private_gpt_review_without_a_digest(self):
        text = (ROOT / REGISTRATION_RECORD).read_text(encoding="utf-8")
        citation = re.search(r"The Astra fix-one read\b.*?(?=added two P2 blockers)", text, re.DOTALL)
        self.assertIsNotNone(citation, "identify the private GPT review citation for custody validation")
        self.assertEqual(len(DIGEST.findall(citation.group(0))), 0,
                         "the private GPT review is cited by name without any unpublished-byte digest")
        self.assertIn("GPT-VERDICT-94f4c7649.md", citation.group(0))

    def test_every_registration_record_digest_has_a_published_preimage(self):
        text = (ROOT / REGISTRATION_RECORD).read_text(encoding="utf-8")
        held = set(DIGEST.findall(text))
        tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
        published = set()
        for reference in tracked:
            path = confined_file(ROOT, ROOT, reference)
            if path is not None:
                published.add(hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(len(held - published), 0,
                         "record digests lacking a published repository preimage (count only); "
                         "cite unpublished records by name without a digest")


class ModelCurrencyPrivateCitationTests(unittest.TestCase):
    """The corrected October 7 record cites private packets by name (PR #1201 P1)."""

    def test_private_source_record_citations_have_no_digest_or_prefix(self):
        text = (ROOT / "docs/decisions/2026-10-07-model-currency-enforcement.md").read_text()
        sections = (
            ("initial", r"The command center's model refresh\b.*?(?=The current catalog)"),
            ("later", r"The later living source record\b.*?(?=The CC\nreports)"),
        )
        for name, pattern in sections:
            with self.subTest(citation=name):
                citation = re.search(pattern, text, re.DOTALL)
                self.assertIsNotNone(citation, "private citation must remain identifiable")
                held = re.findall(r"(?<![A-Za-z0-9_])[0-9a-f]{5,64}(?![A-Za-z0-9_])", citation.group(0))
                self.assertEqual(len(held), 0, "private citation digest/prefix count; never print values")
                self.assertTrue("model-currency-wf_5053494c-265.json" in citation.group(0),
                                "cite the actual private packet name")

    def test_linked_source_review_and_checks_use_name_only_private_references(self):
        private_fields = {"source_packet_sha256", "current_source_packet_sha256",
                          "previous_source_packet_sha256", "proposal_sha256", "stderr_sha256"}

        def locations(node, prefix=""):
            if isinstance(node, dict):
                return [prefix + "/" + key for key in node if key in private_fields] + [
                    site for key, value in node.items() for site in locations(value, prefix + "/" + key)]
            if isinstance(node, list):
                return [site for i, value in enumerate(node) for site in locations(value, prefix + f"/{i}")]
            return []

        directory = ROOT / "evidence/artifacts/model-currency-enforcement-20261007"
        found = {name: locations(json.loads((directory / name).read_text()))
                 for name in ("fill-source-review.json", "j826-checks.json")}
        self.assertEqual({name: sites for name, sites in found.items() if sites}, {},
                         "private reference fields by file/locator only; cite records by name")


class SyntheticDetectorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "evidence/receipts").mkdir(parents=True)

    def write(self, relative: str, content: bytes | str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        return path

    def receipt(self, provenance, key="provenance", nested=False):
        document = {"id": "fixture", key: provenance}
        if nested:
            document = {"id": "fixture", "data": {"inner": {key: provenance}}}
        self.write("evidence/receipts/fixture.json", json.dumps(document))
        return findings(self.root)

    def test_the_new_shape_a_digest_with_no_published_file_is_found(self):
        digest = hashlib.sha256(b"unsanitized run output").hexdigest()
        found = self.receipt([{"name": "run.log", "sha256": digest, "disclosure": "Retained privately; only the result is exported."}])
        self.assertEqual(found, {"evidence/receipts/fixture.json": 1})

    def test_a_digest_of_the_published_file_it_names_passes(self):
        data = b"sanitized projection\n"
        self.write("evidence/artifacts/fixture/projection.txt", data)
        found = self.receipt([{"name": "projection", "path": "evidence/artifacts/fixture/projection.txt",
                               "sha256": hashlib.sha256(data).hexdigest()}])
        self.assertEqual(found, {})

    def test_a_path_next_to_the_json_file_resolves_too(self):
        data = b"neighbour\n"
        self.write("evidence/receipts/neighbour.txt", data)
        found = self.receipt([{"path": "neighbour.txt", "sha256": hashlib.sha256(data).hexdigest()}])
        self.assertEqual(found, {})

    def test_a_named_file_with_different_bytes_is_found(self):
        self.write("evidence/artifacts/fixture/projection.txt", b"published bytes\n")
        found = self.receipt([{"path": "evidence/artifacts/fixture/projection.txt",
                               "sha256": hashlib.sha256(b"unsanitized original\n").hexdigest()}])
        self.assertEqual(found, {"evidence/receipts/fixture.json": 1})

    def test_a_path_that_leaves_the_checkout_never_resolves(self):
        data = b"outside\n"
        outside = Path(self.temporary.name).parent / "custody-fixture-outside.txt"
        outside.write_bytes(data)
        self.addCleanup(outside.unlink)
        digest = hashlib.sha256(data).hexdigest()
        for reference in ("../custody-fixture-outside.txt", str(outside), "evidence/../../custody-fixture-outside.txt"):
            with self.subTest(reference=reference):
                found = self.receipt([{"path": reference, "sha256": digest}])
                self.assertEqual(found, {"evidence/receipts/fixture.json": 1})

    def test_a_symlink_to_a_file_is_not_a_published_preimage(self):
        data = b"linked\n"
        target = self.write("evidence/artifacts/fixture/real.txt", data)
        link = self.root / "evidence/artifacts/fixture/link.txt"
        link.symlink_to(target)
        found = self.receipt([{"path": "evidence/artifacts/fixture/link.txt", "sha256": hashlib.sha256(data).hexdigest()}])
        self.assertEqual(found, {"evidence/receipts/fixture.json": 1})

    def test_provenance_is_found_at_any_depth_and_other_lists_are_ignored(self):
        digest = hashlib.sha256(b"x").hexdigest()
        self.assertEqual(self.receipt([{"sha256": digest}], nested=True), {"evidence/receipts/fixture.json": 1})
        self.assertEqual(self.receipt([{"sha256": digest}], key="inputs"), {})

    def test_an_entry_without_a_digest_and_the_unpublished_list_are_clean(self):
        found = self.receipt([{"name": "run.log", "disclosure": "Retained privately; no digest is published."}])
        self.assertEqual(found, {})

    def test_only_the_scanned_directories_are_walked(self):
        self.write("docs/fixture.json", json.dumps({"provenance": [{"sha256": hashlib.sha256(b"y").hexdigest()}]}))
        self.assertEqual(findings(self.root), {})


class JevPrivateRecordCustodyTests(unittest.TestCase):
    """Private authorizations/reviews are name/path references, never public digests."""

    def test_jev_mutation_exports_omit_unpublished_failure_digests(self):
        root = ROOT / "evidence/artifacts/jev-trading-build-20261015"
        for path in root.glob("guard-mutants*.json"):
            with self.subTest(path=path.name):
                self.assertNotIn('"failure_sha256"', path.read_text())
        source = ROOT / "blueprints/native-skill-practice/p1/jev_trading_mutants.py"
        self.assertNotIn('"failure_sha256"', source.read_text())

    def test_runtime_source_does_not_embed_private_authorization_digest(self):
        import ast
        path = ROOT / "blueprints/native-skill-practice/p1/jev_trading_run.py"
        found = 0
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                names = [target.id for target in node.targets if isinstance(target, ast.Name)]
                if any("ADDENDUM" in name or "PRIVATE_RECORD" in name for name in names) and DIGEST.fullmatch(node.value.value):
                    found += 1
        self.assertEqual(found, 0, "private authorization digest must be read privately at runtime")

    def test_public_jev_evidence_has_no_private_record_or_review_digest_fields(self):
        private_keys = {"addendum_sha256", "record_sha256", "source_evidence_sha256", "two_family_reads", "amendment_sha256"}
        def count(node):
            if isinstance(node, dict):
                return sum(len(DIGEST.findall(json.dumps(value))) if key in private_keys else count(value)
                           for key, value in node.items())
            if isinstance(node, list):
                return sum(count(value) for value in node)
            return 0
        root = ROOT / "evidence/artifacts/jev-trading-build-20261015"
        findings = {path.relative_to(ROOT).as_posix(): count(json.loads(path.read_text())) for path in root.rglob("*.json")}
        self.assertEqual({path: n for path, n in findings.items() if n}, {}, "private evidence digest field counts only")

    def test_private_record_citations_use_names_and_paths_only(self):
        paths = ("blueprints/native-skill-practice/p1/JEV-TRADING.md",
                 "docs/decisions/2026-10-15-jev-trading-harness-build.md")
        for name in paths:
            with self.subTest(path=name):
                # These introductions cite private authority. Public upstream
                # package/dataset digests belong to their later source sections.
                text = "\n".join((ROOT / name).read_text().splitlines()[:20])
                self.assertEqual(len(DIGEST.findall(text)), 0, "private citations contain a digest")


MODEL_ROUTES_RECORD = "evidence/artifacts/model-routes-sweep-claude-20261015"
MODEL_ROUTES_ATTEMPTS = "evidence/artifacts/model-routes-sweep-claude-20261015-attempts"
# The commit the run read its harness, templates, ledger rule and catalog inputs at (RUN-RECORD.md); main carries it.
MODEL_ROUTES_PIN = "8053f14e7e0817d2502dff2bb284bfb7e1b0152f"
DIRECTION_RECORD = "direction-cc-20261015T1912Z-new-wsl-harness-first.md"
HEX_RUN = re.compile(r"(?<![0-9a-f])[0-9a-f]{64,}(?![0-9a-f])")
ABBREVIATED_DIGEST = re.compile(r"(?<![0-9A-Za-z])[0-9a-f]{7,63}(?:\.\.\.|…)")
PINNED_SOURCES = tuple(f"tools/sota-convergence/landscape-sweep/{name}" for name in (
    "build_args.py", "codex_job.py", "make_prompt.py", "sweep_common.py", "templates.json")) + (
    "scripts/saturation_ledger.py", "adoption/manifest.json", "adoption/skills/manifest.json")
# Runs in a child process over PINNED_SOURCES as they were at MODEL_ROUTES_PIN, so no harness module this process loaded
# is reused: the run's fill_build (date 2026-10-15, one layer, the skills manifest's checked_at, repository modality) and
# prompts_sha256, and the ledger's requirement_sha256 (over stdin's fields) and platform_profiles_sha256.
PINNED_COMPUTE = r'''
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path[:0] = [str(root / "tools/sota-convergence/landscape-sweep"), str(root / "scripts")]
import build_args, saturation_ledger, sweep_common
skills = json.loads((root / build_args.SKILLS_MANIFEST).read_text(encoding="utf-8"))
frozen = build_args.fill_build(build_args.load_templates(), "2026-10-15", 1, skills["checked_at"],
                               build_args.REPOSITORY_MODALITY)
adoption = json.loads((root / saturation_ledger.ADOPTION).read_text(encoding="utf-8"))
print(json.dumps({"prompts_sha256": sweep_common.prompts_sha256(frozen),
                  "requirement_sha256": saturation_ledger.requirement_sha256(json.load(sys.stdin)),
                  "platform_profiles_sha256": saturation_ledger.platform_profiles_sha256(adoption)}))
'''


def git_bytes(*args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, input=data, capture_output=True, check=True).stdout


def pin_blob_digests() -> set[str]:
    """Hash pinned blobs except those whose unchanged HEAD bytes are already hashed from the checkout."""
    changed = set(git_bytes("diff", "--name-only", "-z", "HEAD").decode().split("\0"))
    head = {entry.split()[2] for entry in git_bytes("ls-tree", "-r", "-z", "HEAD").decode().split("\0")
            if entry and entry.split("\t", 1)[1] not in changed}
    pinned = {entry.split()[2] for entry in git_bytes("ls-tree", "-r", "-z", MODEL_ROUTES_PIN).decode().split("\0")
              if entry and entry.split()[1] == "blob"}
    data = git_bytes("cat-file", "--batch", data="".join(f"{oid}\n" for oid in sorted(pinned - head)).encode())
    found, offset = set(), 0
    while offset < len(data):
        end = data.index(b"\n", offset)
        header, offset = data[offset:end].split(), end + 1
        if len(header) == 3 and header[1] == b"blob":
            size = int(header[2])
            found.add(hashlib.sha256(data[offset:offset + size]).hexdigest())
            offset += size + 1
    return found


def pinned_computed_hashes(fields: dict) -> dict:
    """The three hashes the record names, recomputed from tracked bytes at MODEL_ROUTES_PIN (PINNED_COMPUTE)."""
    import sys
    with tempfile.TemporaryDirectory() as directory:
        for relative in PINNED_SOURCES:
            target = Path(directory) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git_bytes("show", f"{MODEL_ROUTES_PIN}:{relative}"))
        result = subprocess.run([sys.executable, "-I", "-B", "-c", PINNED_COMPUTE, directory], input=json.dumps(fields),
                                capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


class PinnedBlobDigestTests(unittest.TestCase):
    def check_checkout(self, changed: bool):
        from unittest.mock import patch
        oid = "1" * 40
        path = "catalogs/landscape/final-stack.json"
        blob = b"published run input\n"
        tree = f"100644 blob {oid}\t{path}\0".encode()

        def fixture(*args, data=None):
            if args[0] == "ls-tree":
                return tree
            if args[0] == "diff":
                return (path + "\0").encode() if changed else b""
            if args[:2] == ("cat-file", "--batch"):
                return f"{oid} blob {len(blob)}\n".encode() + blob + b"\n" if data else b""
            raise AssertionError("unexpected Git fixture command")

        with patch(__name__ + ".git_bytes", side_effect=fixture):
            return hashlib.sha256(blob).hexdigest() in pin_blob_digests()

    def test_modified_checkout_still_resolves_public_pinned_blob(self):
        self.assertTrue(self.check_checkout(changed=True),
                        "a modified checkout must resolve the original published blob at the run pin")

    def test_unchanged_checkout_skips_duplicate_blob_read(self):
        self.assertFalse(self.check_checkout(changed=False),
                         "unchanged published bytes are already hashed from the checkout")


class ModelRoutesClaudeHalfCustodyTests(unittest.TestCase):
    """The model-routes Claude-half record publishes digests of published bytes only (CC full read of #1188, two P1s).

    Its first head published the sha256 of the unmasked layer input, of the three stage scripts as run and of the merged
    proposal list (they hold the work-directory path or pre-convert paths), and of the CC direction record, with
    abbreviated prefixes of some of them and of a private receipt. Every 64-hex value in the record's two directories
    must be the sha256 of a tracked file, as checked out or at the run's pin, or one of the three hashes the record names
    and this test recomputes from tracked bytes with the harness's own functions. Private records are cited by name, and
    no abbreviated digest stands in for a value. Findings are reported as file and count, never as a digest.
    """

    @classmethod
    def setUpClass(cls):
        cls.files = {}
        for directory in (MODEL_ROUTES_RECORD, MODEL_ROUTES_ATTEMPTS):
            for path in sorted((ROOT / directory).iterdir()):
                if path.is_file():
                    cls.files[path.relative_to(ROOT).as_posix()] = path.read_text(encoding="utf-8")

    def test_every_digest_hashes_published_bytes_or_recomputes_from_them(self):
        present = subprocess.run(["git", "cat-file", "-e", f"{MODEL_ROUTES_PIN}^{{commit}}"], cwd=ROOT, capture_output=True)
        if present.returncode != 0:
            self.skipTest(f"{MODEL_ROUTES_PIN} is not a commit object in this clone (shallow?); validate.yml fetches it")
        layer_input = json.loads(self.files[f"{MODEL_ROUTES_RECORD}/layer-input.json"])
        computed = pinned_computed_hashes({"next_action": layer_input["next_action"],
                                           "decision_ref": layer_input["decision_ref"]})
        published = pin_blob_digests()
        for reference in git_bytes("ls-files", "-z").decode().split("\0"):
            path = confined_file(ROOT, ROOT, reference)
            if path is not None:
                published.add(hashlib.sha256(path.read_bytes()).hexdigest())
        unresolved = {}
        for name, text in self.files.items():
            count = sum(1 for value in HEX_RUN.findall(text) if value not in published and value not in computed.values())
            if count:
                unresolved[name] = count
        self.assertEqual(unresolved, {}, "64-hex values that hash no published bytes and recompute from none "
                                         "(file: count); name an unpublished original without any digest")
        discovery = json.loads(self.files[f"{MODEL_ROUTES_RECORD}/returns.json"])["discovery"]["model-routes"]
        hashes = json.loads(self.files[f"{MODEL_ROUTES_ATTEMPTS}/hashes.json"])
        sites = {"layer-input.json requirement_sha256": (layer_input, "requirement_sha256"),
                 "returns.json requirement_sha256": (discovery, "requirement_sha256"),
                 "layer-input.json platform_profiles_sha256": (layer_input, "platform_profiles_sha256"),
                 "returns.json platform_profiles_sha256": (discovery, "platform_profiles_sha256"),
                 "hashes.json prompts_sha256": (hashes, "prompts_sha256")}
        self.assertEqual([site for site, (document, key) in sites.items() if document.get(key) != computed[key]], [],
                         "named hashes that do not recompute from tracked bytes")

    def test_unpublished_originals_are_named_without_a_digest(self):
        originals = json.loads(self.files[f"{MODEL_ROUTES_ATTEMPTS}/hashes.json"]).get("unpublished_originals")
        self.assertIsInstance(originals, list, "hashes.json names the private originals under unpublished_originals")
        text = json.dumps(originals)
        self.assertEqual((len(HEX_RUN.findall(text)), len(ABBREVIATED_DIGEST.findall(text))), (0, 0),
                         "the private originals carry no digest of any kind")
        names = " ".join(str(item.get("name")) for item in originals)
        for original in ("inputs/model-routes.json", "claude-stage1-discover.embedded.js",
                         "claude-stage2-refute.embedded.js", "claude-stage3-critic.embedded.js", "stage2-merged.json"):
            self.assertIn(original, names)

    def test_the_direction_record_is_cited_by_name_without_a_digest(self):
        import ast
        citation = re.search(r"The owner direction is recorded\b.*?(?=\n- |\n\n)",
                             self.files[f"{MODEL_ROUTES_RECORD}/RUN-RECORD.md"], re.DOTALL)
        self.assertIsNotNone(citation, "identify RUN-RECORD.md's citation of the CC direction record")
        generator = ast.parse(self.files[f"{MODEL_ROUTES_ATTEMPTS}/build_input.py"])
        sites = {
            "RUN-RECORD.md": citation.group(0),
            "layer-input.json decision_ref": json.loads(self.files[f"{MODEL_ROUTES_RECORD}/layer-input.json"])["decision_ref"],
            "build_input.py decision_ref": next(
                node.value.value for node in ast.walk(generator) if isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Constant)
                and any(isinstance(target, ast.Name) and target.id == "decision_ref" for target in node.targets)),
        }
        for site, text in sites.items():
            with self.subTest(site=site):
                self.assertIn(DIRECTION_RECORD, text)
                self.assertEqual(len(DIGEST.findall(text)), 0, "cite the private record by name, without a digest")

    def test_the_record_holds_no_abbreviated_digest(self):
        found = {name: len(ABBREVIATED_DIGEST.findall(self.files[f"{MODEL_ROUTES_RECORD}/{name}"]))
                 for name in ("RUN-RECORD.md", "MERGE-PLAN.md")}
        self.assertEqual({name: count for name, count in found.items() if count}, {},
                         "abbreviated digests (file: count); give a published value in full or name the original")


if __name__ == "__main__":
    unittest.main()
