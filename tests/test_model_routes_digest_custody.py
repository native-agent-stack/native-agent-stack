"""Recursive public-preimage and prefix guards for the retained GPT model-routes sweep."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_provenance_digest_custody import (
    ROOT, MODEL_ROUTES_PIN, confined_file, git_bytes, pin_blob_digests, pinned_computed_hashes,
)


MODEL_ROUTES_GPT_RECORD = "evidence/artifacts/model-routes-sweep-20261015"
MODEL_ROUTES_PUBLIC = ROOT / "tests/fixtures/model_routes_public_sources"
GPT_HEX_RUN = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64,}(?![0-9a-fA-F])")
# A short Git commit is a valid source pin. A shortened SHA-256 is not a digest
# binding: recognize ellipses, explicit SHA-256 labels and digest-prefix fields.
SHORT_DIGEST = r"(?<![0-9A-Za-z_])[0-9a-fA-F]{5,63}(?![0-9A-Za-z_])"
GPT_ABBREVIATED_DIGEST = re.compile(
    rf"{SHORT_DIGEST}\s*(?:\.\.\.|…)|"
    rf"(?i:sha[-_ ]?256|(?:source\s+)?hash|digest)(?:[_ -](?i:prefix))?[\s\"'`:=]+{SHORT_DIGEST}"
)


def model_routes_digest_findings(directory: Path, published: set[str]) -> dict[str, dict[str, int]]:
    """Inspect every file and JSON depth; return file/count only, never digest material."""
    found = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", errors="replace")
        unresolved = sum(value.lower() not in published for value in GPT_HEX_RUN.findall(text))
        abbreviated = len(GPT_ABBREVIATED_DIGEST.findall(text))
        if unresolved or abbreviated:
            found[path.relative_to(directory).as_posix()] = {
                "unresolved": unresolved, "abbreviated": abbreviated}
    return found


def reconstructed_gpt_sources(deployed: dict) -> dict[str, bytes]:
    """Only public inputs: release source plus published insert, or complete published lines."""
    by_path = {row["path"]: row for row in deployed["files"]}
    codex_path = "open-sse/config/providers/registry/codex/index.ts"
    suffix_path = "open-sse/executors/codex/reasoningSuffix.ts"
    release = (MODEL_ROUTES_PUBLIC / "omniroute-codex.ts.txt").read_bytes().splitlines(keepends=True)
    inserted = [item for item in by_path[codex_path]["excerpts"] if 69 <= item["line"] <= 77]
    if [item["line"] for item in inserted] != list(range(69, 78)):
        raise ValueError("published Codex insert must contain contiguous lines 69-77")
    if b'id: "gpt-6-luna"' not in release[68]:
        raise ValueError("public release insertion anchor changed")
    codex = b"".join(release[:68]) + "".join(item["text"] + "\n" for item in inserted).encode() + b"".join(release[68:])
    lines = codex.decode().splitlines()
    if any(item["line"] > len(lines) or lines[item["line"] - 1] != item["text"]
           for item in by_path[codex_path]["excerpts"]):
        raise ValueError("reconstructed Codex bytes disagree with published excerpt locations")
    suffix = by_path[suffix_path]["excerpts"]
    if [item["line"] for item in suffix] != list(range(1, 61)):
        raise ValueError("published reasoning suffix must contain every line 1-60")
    return {codex_path: codex, suffix_path: "".join(item["text"] + "\n" for item in suffix).encode()}


class ModelRoutesGPTCustodyTests(unittest.TestCase):
    """Every GPT-half digest needs public bytes or reproducible public inputs (#1177 follow-up)."""

    @classmethod
    def setUpClass(cls):
        cls.directory = ROOT / MODEL_ROUTES_GPT_RECORD
        cls.scope = json.loads((cls.directory / "scope.json").read_text())
        cls.deployed = json.loads((cls.directory / "deployed-source-review.json").read_text())
        cls.reconstructed = reconstructed_gpt_sources(cls.deployed)

    def test_every_digest_recursively_resolves_and_no_prefix_substitutes_for_it(self):
        present = subprocess.run(["git", "cat-file", "-e", f"{MODEL_ROUTES_PIN}^{{commit}}"], cwd=ROOT, capture_output=True)
        if present.returncode != 0:
            self.skipTest(f"{MODEL_ROUTES_PIN} is unavailable in this clone; validate.yml fetches the run pin")
        computed = pinned_computed_hashes(self.scope["proposed_requirement"])
        published = pin_blob_digests() | set(computed.values())
        published.update(hashlib.sha256(data).hexdigest() for data in self.reconstructed.values())
        for reference in git_bytes("ls-files", "-z").decode().split("\0"):
            path = confined_file(ROOT, ROOT, reference)
            if path is not None:
                published.add(hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(model_routes_digest_findings(self.directory, published), {},
                         "unresolved or abbreviated digests (file/count only); publish their inputs or cite names only")
        proposal = json.loads((self.directory / "proposed-ledger-record.json").read_text())["proposed_record"]
        fields = {
            "scope requirement": (self.scope["requirement_sha256"]["foundation/model-routes"], computed["requirement_sha256"]),
            "scope platform": (self.scope["platform_profiles_sha256"], computed["platform_profiles_sha256"]),
            "ledger predecessor": (proposal["prev_sha256"], computed["ledger_head_sha256"]),
            "ledger requirement": (proposal["layers"][0]["requirement_sha256"], computed["requirement_sha256"]),
            "ledger platform": (proposal["layers"][0]["platform_profiles_sha256"], computed["platform_profiles_sha256"]),
        }
        self.assertEqual([site for site, (actual, expected) in fields.items() if actual != expected], [],
                         "named derived fields must match the pinned public algorithms")

    def test_each_declared_source_digest_matches_its_published_or_reconstructed_bytes(self):
        release_files = {
            "open-sse/config/providers/registry/muse-code/index.ts": "omniroute-muse-code.ts.txt",
            "open-sse/config/providers/shared.ts": "omniroute-shared.ts.txt",
            "open-sse/config/museCode.ts": "omniroute-museCode.ts.txt",
            "src/lib/providers/requestDefaults.ts": "omniroute-requestDefaults.ts.txt",
        }
        public = {path: (MODEL_ROUTES_PUBLIC / fixture).read_bytes() for path, fixture in release_files.items()}
        public.update(self.reconstructed)
        self.assertTrue(self.deployed["upstream_release"]["commit"] == "c1e30b7676975feb298b49eff6ff58923c04b89e")
        self.assertEqual({row["path"] for row in self.deployed["files"]}, set(public), "cover every declared source file")
        mismatches = [row["path"] for row in self.deployed["files"]
                      if row["sha256"] != hashlib.sha256(public[row["path"]]).hexdigest()]
        if self.deployed["package"]["package_sha256"] != hashlib.sha256(
                (MODEL_ROUTES_PUBLIC / "omniroute-package.json.txt").read_bytes()).hexdigest():
            mismatches.append("package.json")
        skill = json.loads((self.directory / "sources.json").read_text())["installed_skill"]
        self.assertTrue(skill["pin"] == "dbd4588f9e1033efb41dad4bef2f7947c8993d44")
        skill_files = {"SKILL.md": "claude-api-SKILL.md.txt", "shared/models.md": "claude-api-models.md.txt"}
        self.assertEqual({row["path"] for row in skill["files"]}, set(skill_files))
        mismatches += ["claude-api/" + row["path"] for row in skill["files"] if row["sha256"] != hashlib.sha256(
            (MODEL_ROUTES_PUBLIC / skill_files[row["path"]]).read_bytes()).hexdigest()]
        self.assertEqual(mismatches, [], "source mismatches by file only; never print digest values")


class ModelRoutesDigestDetectorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def check(self, text: str, published=()):
        path = self.root / "nested/new-candidate/arbitrary.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return model_routes_digest_findings(self.root, set(published))

    def test_unrecognized_keys_and_nested_directories_cannot_hide_a_digest(self):
        digest = hashlib.sha256(b"synthetic unpublished bytes").hexdigest()
        result = self.check(json.dumps({"new_key": [{"deep": "reference@" + digest + ":12"}]}))
        self.assertEqual(result, {"nested/new-candidate/arbitrary.txt": {"unresolved": 1, "abbreviated": 0}})

    def test_published_preimage_is_accepted_independently_of_field_name(self):
        digest = hashlib.sha256(b"synthetic published bytes").hexdigest()
        self.assertEqual(self.check("arbitrary " + digest, {digest}), {})

    def test_uppercase_and_overlong_hex_cannot_bypass_detection(self):
        digest = hashlib.sha256(b"synthetic uppercase original").hexdigest()
        for text in (digest.upper(), digest + digest):
            found = self.check(text)
            self.assertEqual(sum(row["unresolved"] for row in found.values()), 1)
        self.assertEqual(self.check(digest.upper(), {digest}), {})

    def test_every_abbreviated_form_is_rejected(self):
        examples = ("abcde...", "abcdef1…", "sha256: abcde", "SHA-256=`abcdef123`",
                    '"source_sha256_prefix": "abcdef123"', "source hash abcde")
        for index, text in enumerate(examples):
            with self.subTest(form=index):
                found = self.check(text)
                self.assertEqual(sum(row["abbreviated"] for row in found.values()), 1,
                                 "abbreviated digest count only")

    def test_short_public_git_pin_is_not_a_sha256_prefix(self):
        self.assertEqual(self.check("repo@8053f14e7:path:12; git commit abcde"), {})

    def test_a_match_in_a_second_record_does_not_publish_a_preimage(self):
        digest = hashlib.sha256(b"synthetic unretained original").hexdigest()
        (self.root / "second.json").write_text(json.dumps({"also": digest}))
        found = self.check(digest)
        self.assertEqual(sum(row["unresolved"] for row in found.values()), 2)

    def test_truncated_reconstruction_cannot_be_accepted(self):
        deployed = json.loads((ROOT / MODEL_ROUTES_GPT_RECORD / "deployed-source-review.json").read_text())
        deployed["files"][5]["excerpts"].pop()
        with self.assertRaisesRegex(ValueError, "every line"):
            reconstructed_gpt_sources(deployed)



if __name__ == "__main__":
    unittest.main()
