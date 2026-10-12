"""C1's public-ref and reviewed-merge seams, using native Git and pinned Gitleaks."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests import test_ci_secret_scan_range as range_tests
from tests.test_workflow_hardening import jobs, step_block, run_block
from tests.test_workflow_policy import load_workflow


ROOT = Path(__file__).resolve().parents[1]
SELECTOR = Path(os.environ.get("C1_TEST_SELECTOR", str(ROOT / "scripts/ci_secret_scan_range.py")))
GITLEAKS = shutil.which("gitleaks")


ZERO_SHA = range_tests.ZERO_SHA


class PublicationRangeTests(range_tests.CiSecretScanRangeTests):
    def test_new_branch_and_tag_cover_intermediate_commits_from_main_merge_base(self):
        for ref in ("refs/heads/topic", "refs/tags/release"):
            with self.subTest(ref=ref):
                outputs = self.assert_range("push", {"before": ZERO_SHA, "after": self.feature_two, "ref": ref},
                                            self.base, self.feature_two, (self.feature_one, self.feature_two))
                self.assertEqual(outputs["reason"], "new-ref-main-merge-base")

    def test_force_push_with_available_or_unavailable_before_covers_new_ancestry(self):
        old = self.commit("old branch", self.base)
        for before in (old, "f" * 40):
            with self.subTest(before=before):
                self.assert_range("push", {"before": before, "after": self.feature_two,
                                           "forced": True, "ref": "refs/heads/topic"},
                                  self.base, self.feature_two, (self.feature_one, self.feature_two))

    def test_unrelated_new_ref_fails_closed(self):
        self.checkout(self.commit("unrelated root"))
        head = self.git("rev-parse", "HEAD")
        self.assert_rejected("push", {"before": ZERO_SHA, "after": head, "ref": "refs/tags/new"})

    def test_annotated_tag_peels_its_exact_payload_object_to_the_checked_out_commit(self):
        self.git("tag", "-a", "release", "-m", "fixture release", self.feature_two)
        tag = self.git("rev-parse", "refs/tags/release")
        self.assertNotEqual(tag, self.feature_two)
        self.assert_range("push", {"before": ZERO_SHA, "after": tag, "ref": "refs/tags/release"},
                          self.base, self.feature_two, (self.feature_one, self.feature_two))
        self.assert_rejected("push", {"before": ZERO_SHA, "after": tag, "ref": "refs/heads/topic"})

    def test_nonempty_merge_tree_enumeration_contains_only_commit_ids(self):
        blob = self.git("hash-object", "-w", "--stdin", input="ordinary fixture content\n")
        self.tree = self.git("mktree", input=f"100644 blob {blob}\tfixture.txt\n")
        side = self.commit("nonempty feature", self.base)
        merge = self.commit("nonempty merge", self.main, side)
        self.checkout(merge)
        self.assert_range("push", {"before": self.main, "after": merge}, self.main, merge, (side, merge))


class PublicationWorkflowTests(unittest.TestCase):
    def test_backstop_and_pr_jobs_share_pinned_installs_and_native_history_commands(self):
        regular = jobs((ROOT / ".github/workflows/validate.yml").read_text())
        backstop = jobs((ROOT / ".github/workflows/secret-scan-history.yml").read_text())
        for job in ("secret-scan", "secret-scan-betterleaks"):
            public_job = "publication-secret-scan" if job == "secret-scan" else "publication-betterleaks"
            self.assertEqual(run_block(step_block(regular[job], "Scan git history")),
                             run_block(step_block(backstop[public_job], "Scan git history")))
            install = "Install checksum-verified pinned gitleaks" if job == "secret-scan" else "Install betterleaks after Sigstore"
            self.assertEqual(step_block(regular[job], install), step_block(backstop[public_job], install))
        self.assertTrue(set(regular).isdisjoint(backstop), "Required PR contexts must remain unambiguous")
    def test_all_branch_and_tag_pushes_trigger_the_gate(self):
        workflow = load_workflow((ROOT / ".github/workflows/secret-scan-history.yml").read_text())
        push = workflow["on"]["push"]
        self.assertEqual(push.get("branches"), ["**"])
        self.assertEqual(push.get("tags"), ["**"])

    def test_scanner_equipped_step_enrolls_native_merge_regressions(self):
        job = jobs((ROOT / ".github/workflows/validate.yml").read_text())["secret-scan"]
        script = run_block(step_block(job, "gitleaks allowlist regression tests"))
        self.assertIn("tests.test_secret_scan_size.CiSecretScanMergedHistoryTests", script)
        self.assertIn("tests.test_ci_secret_publication.ReviewedMergeTests", script)

    def test_separate_backstop_has_schedule_and_dispatch_and_history_only_scanners(self):
        path = ROOT / ".github/workflows/secret-scan-history.yml"
        self.assertTrue(path.is_file(), "Separate CI backstop must be wired")
        workflow = load_workflow(path.read_text())
        self.assertIn("schedule", workflow["on"])
        self.assertIn("workflow_dispatch", workflow["on"])
        for job in workflow["jobs"].values():
            scripts = [s.get("run", "") for s in job.get("steps", [])]
            self.assertFalse(any(re.search(r'/(?:gitleaks|betterleaks)" dir\s', s) for s in scripts))
            self.assertTrue(any('--log-opts="$SCAN_LOG_OPTS"' in s for s in scripts))


@unittest.skipUnless(GITLEAKS, "gitleaks not found on PATH")
class ReviewedMergeTests(unittest.TestCase):
    """Native fingerprints must not suppress a different later same-location value."""

    def test_reviewed_pr_merge_replay_is_bound_but_new_same_location_value_is_detected(self):
        with tempfile.TemporaryDirectory(prefix="reviewed-pr-merge-") as scratch:
            base = Path(scratch)
            repo = base / "repo"
            repo.mkdir()
            env = {"PATH": os.environ.get("PATH", os.defpath), "GIT_CONFIG_GLOBAL": os.devnull,
                   "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                   "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}

            def git(*args, input=None):
                r = subprocess.run(["git", *args], cwd=repo, env=env, input=input,
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, 0, "Fixture Git failed")
                return r.stdout.strip()

            def commit(label, tree, *parents):
                args = ["commit-tree", tree, "-m", label]
                for p in parents:
                    args.extend(("-p", p))
                return git(*args)

            from hashlib import sha1

            def content_tree(seed):
                value = "sgp_" + sha1(seed.encode()).hexdigest()
                blob = git("hash-object", "-w", "--stdin", input=json.dumps({"reviewed": value}) + "\n")
                return git("mktree", input=f"100644 blob {blob}\treviewed.json\n")

            git("init", "-q", "--object-format=sha1", "--initial-branch=main")
            empty = git("mktree", input="")
            original = content_tree("reviewed synthetic fixture")
            fresh = content_tree("different synthetic fixture")
            root = commit("root", empty)
            reviewed = commit("reviewed", original, root)
            main = commit("main", original, reviewed)
            removed = commit("removed", empty, reviewed)
            merged = commit("restored by merge", original, removed, main)
            checkout = commit("generated PR merge", original, main, merged)
            replaced = commit("new same-location value", fresh, merged)
            new_checkout = commit("generated merge with new value", fresh, main, replaced)
            (repo / ".gitleaksignore").write_text(reviewed + ":reviewed.json:sourcegraph-access-token:1\n")
            for relative in (".gitleaks.toml", "scripts/secret_scan_metrics.py", ".github/workflows/validate.yml"):
                dest = repo / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, dest)
            runner = base / "runner"
            native = runner / "gitleaks"
            native.mkdir(parents=True)
            (native / "gitleaks").symlink_to(Path(GITLEAKS).resolve())
            script = run_block(step_block(jobs((ROOT / ".github/workflows/validate.yml").read_text())["secret-scan"], "Scan git history"))
            for head, pr_head, expected in ((checkout, merged, 0), (new_checkout, replaced, 1)):
                with self.subTest(expected=expected):
                    git("update-ref", "refs/heads/main", head)
                    event = base / "event.json"
                    event.write_text(json.dumps({"pull_request": {"base": {"sha": main}, "head": {"sha": pr_head}}}))
                    ignore = native / "merge-ignore"
                    selection = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/ci_secret_scan_range.py"),
                                                "--event-name", "pull_request", "--event-path", str(event),
                                                "--ignore-output", str(ignore)], cwd=repo, env=env,
                                               capture_output=True, text=True, timeout=30)
                    self.assertEqual(selection.returncode, 0, "Resolver must prepare exact reviewed merge bindings")
                    out = dict(line.split("=", 1) for line in selection.stdout.splitlines())
                    r = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail"], input=script,
                                       cwd=repo, env={**env, "RUNNER_TEMP": str(runner), "SCAN_LOG_OPTS": out["log_opts"],
                                                      "SCAN_IGNORE_PATH": str(ignore)}, capture_output=True, text=True, timeout=60)
                    self.assertEqual(r.returncode, expected, "Reviewed replay and a fresh same-location value need different outcomes")
                    findings = json.loads((native / "gitleaks.json").read_text()) or []
                    self.assertEqual(bool(findings), bool(expected))

    def test_historical_reviewed_merge_has_exact_bindings(self):
        # Native Git resolves the public merge already pinned by the reviewed
        # ignore entries and decision, avoiding a redundant token-shaped literal.
        merge = subprocess.check_output(["git", "rev-parse", "9b7a67b9"], cwd=ROOT, text=True).strip()
        with tempfile.TemporaryDirectory(prefix="reviewed-history-merge-") as scratch:
            report = Path(scratch) / "report.json"
            r = subprocess.run([GITLEAKS, "git", ".", "--config", str(ROOT / ".gitleaks.toml"),
                                "--gitleaks-ignore-path", str(ROOT / ".gitleaksignore"),
                                "--log-opts=--diff-merges=first-parent -1 " + merge,
                                "--redact", "--no-banner", "--report-format", "json", "--report-path", str(report)],
                               cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, "One reviewed historical merge must not re-report its accepted fingerprints")
            self.assertEqual(json.loads(report.read_text()) or [], [])


@unittest.skipUnless(GITLEAKS, "gitleaks not found on PATH")
class NativePublicationTests(unittest.TestCase):
    def test_new_branch_tag_force_push_and_merge_detect_removed_large_target(self):
        from tests.test_gitleaks_config import GH_PAT_SHAPED_VALUE
        with tempfile.TemporaryDirectory(prefix="public-ref-native-") as scratch:
            base = Path(scratch)
            repo = base / "repo"
            repo.mkdir()
            env = {"PATH": os.environ.get("PATH", os.defpath), "GIT_CONFIG_GLOBAL": os.devnull,
                   "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                   "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}

            def git(*args, input=None):
                r = subprocess.run(["git", *args], cwd=repo, env=env, input=input,
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, 0, "Synthetic Git failed")
                return r.stdout.strip()

            def commit(label, tree, *parents):
                args = ["commit-tree", tree, "-m", label]
                for p in parents:
                    args.extend(("-p", p))
                return git(*args)

            git("init", "-q", "--object-format=sha1", "--initial-branch=main")
            empty = git("mktree", input="")
            raw = 'token = "' + GH_PAT_SHAPED_VALUE + '"\n' + 'padding\n' * 375000
            blob = git("hash-object", "-w", "--stdin", input=raw)
            target = git("mktree", input=f"100644 blob {blob}\tcanary.txt\n")
            root = commit("root", empty)
            leaked = commit("synthetic introduction", target, root)
            clean = commit("synthetic removal", empty, leaked)
            old = commit("old tip", empty, root)
            merged = commit("merged cleaned branch", empty, old, clean)
            git("update-ref", "refs/remotes/origin/main", root)
            for relative in (".gitleaks.toml", ".gitleaksignore", "scripts/secret_scan_metrics.py", ".github/workflows/validate.yml"):
                path = repo / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, path)
            runner = base / "runner"
            native = runner / "gitleaks"
            native.mkdir(parents=True)
            (native / "gitleaks").symlink_to(Path(GITLEAKS).resolve())
            script = run_block(step_block(jobs((ROOT / ".github/workflows/validate.yml").read_text())["secret-scan"], "Scan git history"))
            cases = (("new-branch", ZERO_SHA, clean, "refs/heads/topic", False),
                     ("new-tag", ZERO_SHA, clean, "refs/tags/release", False),
                     ("force-push", "f" * 40, clean, "refs/heads/topic", True),
                     ("merge", old, merged, "refs/heads/main", False))
            for label, before, head, ref, forced in cases:
                with self.subTest(case=label):
                    git("update-ref", "refs/heads/main", head)
                    payload = base / "event.json"
                    payload.write_text(json.dumps({"before": before, "after": head, "ref": ref, "forced": forced}))
                    r = subprocess.run([sys.executable, "-B", str(SELECTOR), "--event-name", "push",
                                        "--event-path", str(payload)], cwd=repo, env=env, capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, "Public-ref scan must establish complete history, not stop at the tip")
                    outputs = dict(line.split("=", 1) for line in r.stdout.splitlines())
                    scan = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail"], input=script,
                                          cwd=repo, env={**env, "RUNNER_TEMP": str(runner), "SCAN_LOG_OPTS": outputs["log_opts"]},
                                          capture_output=True, text=True, timeout=60)
                    self.assertEqual(scan.returncode, 1, "Production history step must catch the removed synthetic value")
                    findings = json.loads((native / "gitleaks.json").read_text()) or []
                    self.assertTrue(any(f.get("RuleID") == "github-pat" for f in findings))
                    self.assertEqual(json.loads((native / "full-git.metrics.json").read_text())["history_scope"], outputs["log_opts"])
