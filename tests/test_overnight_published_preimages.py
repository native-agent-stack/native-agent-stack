"""#161/a0491701 regression: every receipt digest has a sanitized published preimage."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("published_preimages", ROOT/"scripts/published_preimages.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
RECEIPTS = ("blueprints/us-equities/adaptive-paper/overnight-arming-validation.json",
            "blueprints/us-equities/adaptive-paper/overnight-guard-pins-validation.json",
            "blueprints/us-equities/adaptive-paper/overnight-review-fix-validation.json",
            "blueprints/us-equities/adaptive-paper/overnight-review-round2-validation.json",
            "blueprints/us-equities/adaptive-paper/overnight-cancel-refusal-validation.json",
            "blueprints/us-equities/adaptive-paper/overnight-cancel-worker-validation.json",
            "evidence/artifacts/overnight-arming-20261013/review-cancel-worker/worker-only/validation.json",
            "blueprints/us-equities/adaptive-paper/overnight-cancel-ack-validation.json")
ARTIFACTS = "evidence/artifacts/overnight-arming-20261013"


class PublishedPreimages(unittest.TestCase):
    def test_seven_character_private_prefixes_fail_without_a_public_blacklist(self):
        private=hashlib.sha256(b'synthetic unpublished account fixture bytes').hexdigest()
        check=getattr(policy,'private_digest_prefix_locations',None)
        self.assertTrue(callable(check),'publication guard must detect shortened private digests')
        for width in (7,8,64):
            with self.subTest(width=width):
                self.assertEqual(check({'record.txt':private[:width].encode()},[private]),[('record.txt',1)])
                self.assertEqual(check({'record.txt':private[:width].upper().encode()},[private]),[('record.txt',1)])
        self.assertEqual(check({'record.txt':private[:6].encode()},[private]),[])
        self.assertEqual(check({'record.txt':b'published sanitized output'},[private]),[])

    def test_absent_preimage_fails_even_when_its_private_bytes_can_be_found(self):
        private = b"trace from /home/" + b"fixture-person" + b"/runtime with duration 1.23"
        public = b"trace from ~/runtime with duration 1.23"
        record = {"run":{"output_sha256":hashlib.sha256(private).hexdigest()}}
        self.assertEqual(policy.unpublished_digests({"receipt":record},{"public.log":public}),
                         [("receipt","/run/output_sha256")])
        record["run"]["output_sha256"] = hashlib.sha256(public).hexdigest()
        self.assertEqual(policy.unpublished_digests({"receipt":record},{"public.log":public}),[])

    def test_all_overnight_receipt_digests_resolve_to_published_bytes(self):
        records = {p:json.loads((ROOT/p).read_text()) for p in RECEIPTS}
        # Exact publication inventory, not arbitrary host-local retained_log paths.
        known = set()
        for value in records.values():
            known.update(value.get("input_hashes",{}))
            if "tests_patch" in value:
                known.add(value["tests_patch"]["path"])
        published=set(subprocess.check_output(["git","ls-files"],cwd=ROOT,text=True).splitlines())
        for p in published:
            if p.startswith(ARTIFACTS+"/historical/") and p.endswith("/source-hashes.json.txt"):
                data=(ROOT/p).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(),Path(p).parent.name)
                snapshot=json.loads(data)
                self.assertTrue(all(isinstance(k,str) and isinstance(v,str) for k,v in snapshot.items()))
                records[p]=snapshot
                known.update(snapshot)
        self.assertTrue(known<=published,"receipt names a file outside the published inventory")
        files = {p:(ROOT/p).read_bytes() for p in known if p in published}
        paths = subprocess.check_output(["git","ls-files","--",ARTIFACTS],cwd=ROOT,text=True).splitlines()
        files.update({p:(ROOT/p).read_bytes() for p in paths})
        self.assertEqual(policy.unpublished_digests(records,files),[],
                         "a published digest has no file inside the published set")

    def test_published_logs_are_sanitized_and_named_inside_publication(self):
        records = [json.loads((ROOT/p).read_text()) for p in RECEIPTS]
        inventory=set(subprocess.check_output(["git","ls-files"],cwd=ROOT,text=True).splitlines())
        for record in records:
            for run in record["runs"]:
                self.assertIn("published_log",run,"output digest names only a private host-local preimage")
                path = run.get("published_log", "")
                self.assertTrue(path.startswith(ARTIFACTS+"/"),path)
                self.assertIn(path,inventory,"log preimage is outside the published inventory")
                data=(ROOT/path).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(),run["output_sha256"])
                self.assertEqual(len(data),run["output_bytes"])
                self.assertNotIn(b"/home/",data)
                self.assertNotIn(b"/Users/",data)
            regression=record.get("prepush_review_regressions")
            if regression:
                path=regression["base_published_log"]
                self.assertIn(path,inventory,"base preimage is outside the published inventory")
                data=(ROOT/path).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(),regression["base_output_sha256"])
                self.assertEqual(len(data),regression["base_output_bytes"])
        for path in inventory:
            if path.startswith(ARTIFACTS+"/") and path.endswith(".sanitized.txt"):
                data=(ROOT/path).read_bytes()
                self.assertNotIn(b"/home/",data,path)
                self.assertNotIn(b"/Users/",data,path)
