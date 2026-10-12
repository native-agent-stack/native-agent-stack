"""Native scanner coverage for large synthetic targets using the current CI options.

Only throwaway fixtures are scanned; git scans use a two-commit PR-shaped range.
The canary is fabricated, all scanner reports are redacted, and GNU time measures
the Linux subprocess without imposing a resource cap.
"""

import json
import io
import os
import platform
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from tests.test_workflow_hardening import jobs, step_block, run_block
from tests.test_gitleaks_config import GH_PAT_SHAPED_VALUE
from tests import test_gitleaks_config as history_tests


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/validate.yml"
DECISION = ROOT / "docs/decisions/2026-10-10-secret-scan-large-targets.md"
CANARY = GH_PAT_SHAPED_VALUE
SIZES = (2_000_001, 3_000_000)
GITLEAKS = shutil.which("gitleaks")
BETTERLEAKS = os.environ.get("BETTERLEAKS_TEST_BINARY")


@unittest.skipUnless(GITLEAKS, "gitleaks not found on PATH")
class CiSecretScanMergedHistoryTests(unittest.TestCase):
    """Astra's add/remove and merge-resolution graphs, through the actual CI step."""

    def test_large_removed_secrets_in_merged_histories_and_resolution_patches_are_detected(self):
        with tempfile.TemporaryDirectory(prefix="ci-secret-merged-history-") as scratch:
            base = Path(scratch)
            repo = base / "repo"
            repo.mkdir()
            env = {"PATH": os.environ.get("PATH", os.defpath), "GIT_CONFIG_NOSYSTEM": "1",
                   "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_NAME": "Fixture",
                   "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "Fixture",
                   "GIT_COMMITTER_EMAIL": "fixture@example.invalid", "TMPDIR": str(base)}

            def git(*args, input=None):
                result = subprocess.run(["git", *args], cwd=repo, env=env, input=input,
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, "Fixture Git operation failed")
                return result.stdout.strip()

            git("init", "-q", "--object-format=sha1", "--initial-branch=main")
            empty = git("mktree", input="")
            raw = 'token = "' + CANARY + '"\n' + 'padding\n' * 375000
            self.assertGreater(len(raw), 3_000_000)
            blob = git("hash-object", "-w", "--stdin", input=raw)
            secret_tree = git("mktree", input=f"100644 blob {blob}\tcanary.txt\n")

            def commit(label, tree, *parents):
                args = ["commit-tree", tree, "-m", label]
                for parent in parents:
                    args.extend(("-p", parent))
                return git(*args)

            root = commit("safe root", empty)
            exposed = commit("synthetic addition", secret_tree, root)
            clean = commit("synthetic removal", empty, exposed)
            old = commit("old main", empty, root)
            merge = commit("merge cleaned branch", empty, old, clean)
            after = commit("clean after merge", empty, merge)
            safe_side = commit("safe side", empty, root)
            resolution = commit("synthetic merge resolution", secret_tree, old, safe_side)
            resolution_clean = commit("remove resolution", empty, resolution)
            checkout = commit("generated PR merge", empty, old, resolution_clean)
            runner = base / "runner"
            native = runner / "gitleaks"
            native.mkdir(parents=True)
            (native / "gitleaks").symlink_to(Path(GITLEAKS).resolve())
            for relative in (".gitleaks.toml", ".gitleaksignore", "scripts/secret_scan_metrics.py",
                             ".github/workflows/validate.yml"):
                destination = repo / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, destination)
            script = run_block(step_block(jobs(WORKFLOW.read_text())["secret-scan"], "Scan git history"))
            cases = (("push-merge-only", "push", {"before": old, "after": merge}, merge),
                     ("push-merge-then-clean", "push", {"before": old, "after": after}, after),
                     ("pr-resolution", "pull_request", {"pull_request": {
                         "base": {"sha": root}, "head": {"sha": resolution_clean}}}, resolution_clean),
                     ("pr-generated-merge", "pull_request", {"pull_request": {
                         "base": {"sha": old}, "head": {"sha": resolution_clean}}}, checkout))
            for label, event, payload, head in cases:
                with self.subTest(case=label):
                    git("update-ref", "refs/heads/main", head)
                    git("update-ref", "refs/remotes/origin/main", head if event == "push" else root)
                    event_path = base / "event.json"
                    event_path.write_text(json.dumps(payload))
                    selection = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/ci_secret_scan_range.py"),
                                                "--event-name", event, "--event-path", str(event_path)],
                                               cwd=repo, env=env, capture_output=True, text=True)
                    self.assertEqual(selection.returncode, 0, "Verified merge graph must be accepted")
                    outputs = dict(line.split("=", 1) for line in selection.stdout.splitlines())
                    result = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail"],
                                            input=script, cwd=repo, capture_output=True, text=True, timeout=60,
                                            env={**env, "RUNNER_TEMP": str(runner), "SCAN_LOG_OPTS": outputs["log_opts"]})
                    self.assertEqual(result.returncode, 1, "Actual CI history step must detect the removed synthetic secret")
                    findings = json.loads((native / "gitleaks.json").read_text()) or []
                    self.assertTrue(any(f.get("RuleID") == "github-pat" for f in findings),
                                    "Actual CI history scan must report the synthetic detector")
                    receipt = json.loads((native / "full-git.metrics.json").read_text())
                    self.assertEqual(receipt["history_scope"], outputs["log_opts"])
                    acceptance = unittest.TestResult()
                    ci_env = {**env, "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": event,
                              "GITLEAKS_TESTS_REQUIRED": "1", "GITLEAKS_HISTORY_RANGE": outputs["range"],
                              "GITLEAKS_HISTORY_MODE": outputs["mode"]}
                    with patch.object(history_tests, "ROOT", repo), \
                            patch.object(history_tests, "CONFIG_PATH", repo / ".gitleaks.toml"), \
                            patch.object(history_tests, "GITLEAKS", GITLEAKS), \
                            patch.dict(os.environ, ci_env, clear=True), redirect_stdout(io.StringIO()):
                        for cls in (history_tests.GitleaksLocalPrHistoryTests,
                                    history_tests.GitleaksBranchAncestryHistoryTests):
                            cls("test_head_ancestry_scoped_scan_has_zero_findings").run(acceptance)
                    self.assertEqual(acceptance.errors, [])
                    self.assertEqual(len(acceptance.skipped), 1 if event == "push" else 0)
                    self.assertEqual(len(acceptance.failures), 1 if event == "push" else 2,
                                     "Every applicable duplicate history scan must detect the large removed secret")


def workflow_scanner_arguments(job, mode):
    # Existing stdlib job parser: the native scanner jobs install no YAML dependency.
    source = re.sub(r"\\\n\s*", " ", jobs(WORKFLOW.read_text())[job])
    for line in source.splitlines():
        if not line.lstrip().startswith(('"$RUNNER_TEMP/', '/usr/bin/time ')):
            continue
        words = shlex.split(line)
        binary = next((i for i, word in enumerate(words) if word in (
            "$RUNNER_TEMP/gitleaks/gitleaks", "$RUNNER_TEMP/betterleaks/betterleaks")), None)
        if binary is not None and words[binary + 1:binary + 3] == [mode, "."]:
            end = words.index("||") if "||" in words else len(words)
            return words[binary + 3:end]
    raise AssertionError(f"No native {job} {mode} command in the workflow")


def gnu_time_on_linux():
    # GNU time's --version contract; BSD time does not support -f/-o.
    timer = Path("/usr/bin/time")
    if platform.system() != "Linux" or not timer.is_file():
        return None
    probe = subprocess.run([str(timer), "--version"], capture_output=True, text=True)
    return str(timer) if probe.returncode == 0 and "(GNU Time)" in probe.stdout else None


def scan_fixture(binary, job, mode, size, path="manifests/large-shape.json", *, event_scope=None):
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        target = base / "tree"
        target.mkdir()
        raw = ('github_pat_fixture = "' + CANARY + '"\n').encode()
        raw += (b"padding\n" * ((size - len(raw)) // 8 + 1))[:size - len(raw)]
        env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(base),
               "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
               "LANG": "C.UTF-8"}
        range_arg = None
        event_log_opts = None
        if mode == "git":
            for args in (["init", "-q"], ["config", "user.name", "Fixture"],
                         ["config", "user.email", "fixture@example.invalid"],
                         ["commit", "--allow-empty", "-qm", "fixture base"]):
                subprocess.run(["git", *args], cwd=target, env=env, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if event_scope:
                # A finding before the event window must stay out of this scan.
                (target / "prior-window.txt").write_text('github_pat_fixture = "' + CANARY + '"\n')
                for args in (["add", "prior-window.txt"], ["commit", "-qm", "prior window"]):
                    subprocess.run(["git", *args], cwd=target, env=env, check=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            range_arg = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target, env=env,
                                                text=True).strip() + "..HEAD"
        file = target / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(raw)
        if mode == "git":
            for args in (["add", "--", path], ["commit", "-qm", "fixture target"]):
                subprocess.run(["git", *args], cwd=target, env=env, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if event_scope:
            before = range_arg.split("..", 1)[0]
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target, env=env,
                                           text=True).strip()
            payload = ({"before": before, "after": head} if event_scope == "push" else
                       {"pull_request": {"base": {"sha": before}, "head": {"sha": head}}})
            event_file = base / "event.json"
            event_file.write_text(json.dumps(payload))
            selected = subprocess.run(
                [sys.executable, str(ROOT / "scripts/ci_secret_scan_range.py"),
                 "--event-name", event_scope, "--event-path", str(event_file)],
                cwd=target, env=env, capture_output=True, text=True,
            )
            if selected.returncode:
                raise AssertionError("Production event helper rejected the real checkout fixture")
            outputs = dict(line.split("=", 1) for line in selected.stdout.splitlines())
            if outputs.get("mode") != "range" or outputs.get("range") != f"{before}..{head}":
                raise AssertionError("Production helper did not retain the exact event window")
            event_log_opts = outputs["log_opts"]
        report = base / "report.json"
        metrics_file = base / "metrics.txt"
        words = workflow_scanner_arguments(job, mode)
        args = [binary, mode, "."]
        for word in words:
            if word == ".gitleaks.toml":
                word = str(ROOT / ".gitleaks.toml")
            elif word == ".gitleaksignore":
                word = str(ROOT / ".gitleaksignore")
            elif word == "${SCAN_IGNORE_PATH:-.gitleaksignore}":
                word = str(ROOT / ".gitleaksignore")
            elif word.startswith("--log-opts="):
                word = "--log-opts=" + (event_log_opts or range_arg)
            elif word in ("$report", "$RUNNER_TEMP/gitleaks/gitleaks.json"):
                word = str(report)
            args.append(word)
        if "--report-path" not in args:
            args.extend(["--report-format", "json", "--report-path", str(report)])
        timer = gnu_time_on_linux()
        command = ([timer, "-f", "%e %M", "-o", str(metrics_file)] if timer else []) + args
        if event_scope:
            # Execute the checked-in history step, including #964's native timer
            # and resource-receipt writer, against this real Git checkout.
            runner = base / "runner"
            native = runner / "gitleaks"
            native.mkdir(parents=True)
            (native / "gitleaks").symlink_to(Path(binary).resolve())
            for relative in (".gitleaks.toml", ".gitleaksignore", "scripts/secret_scan_metrics.py"):
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, destination)
            binding = target / ".github/workflows/validate.yml"
            binding.parent.mkdir(parents=True)
            binding.write_bytes(WORKFLOW.read_bytes())
            script = run_block(step_block(jobs(WORKFLOW.read_text())[job], "Scan git history"))
            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-eo", "pipefail"], input=script,
                cwd=target, env={**env, "RUNNER_TEMP": str(runner), "SCAN_LOG_OPTS": event_log_opts},
                capture_output=True, text=True,
            )
            report = native / "gitleaks.json"
            if "scripts/secret_scan_metrics.py" in script:
                receipt = json.loads((native / "full-git.metrics.json").read_text())
                if not receipt:
                    raise AssertionError("Native workflow step did not retain its resource receipt")
                if receipt.get("history_scope") != event_log_opts:
                    raise AssertionError("Native receipt must record the verified event scope")
        else:
            result = subprocess.run(command, cwd=target, env=env, capture_output=True, text=True)
        if result.returncode not in (0, 1):
            raise AssertionError(f"Scanner error, rc={result.returncode}; raw output withheld")
        findings = json.loads(report.read_text()) or []
        if event_scope and any(f.get("File") != path or f.get("Commit") != head for f in findings):
            raise AssertionError("Event-scoped scanner included a finding outside the event commit/path")
        located = [f for f in findings if f.get("File") == path]
        metrics = {"scanner": Path(binary).name, "mode": mode, "size_bytes": size,
                   "findings": len(located), "rc": result.returncode, "host": platform.system(),
                   "measurement": "gnu_time" if timer else "unmeasured"}
        if event_scope:
            metrics.update(event=event_scope, verified_event_range=True)
        if timer and not event_scope:
            seconds, rss = metrics_file.read_text().splitlines()[-1].split()
            metrics.update(elapsed_seconds=float(seconds), peak_rss_kib=int(rss))
        elif event_scope and (native / "full-git.time.json").is_file():
            native_timing = json.loads((native / "full-git.time.json").read_text())
            metrics.update(elapsed_seconds=native_timing["elapsed_seconds"],
                           peak_rss_kib=native_timing["peak_rss_kib"], native_workflow_step=True)
        elif event_scope:
            metrics["measurement"] = "unmeasured"
        print("large-file-scan-metrics: " + json.dumps(metrics, sort_keys=True))
        return located


class ScannerMechanismSourcesTests(unittest.TestCase):
    def test_decision_cites_betterleaks_native_path_prefilter_and_source_callback(self):
        # betterleaks v1.8.1: translation96-108 -> SkipFunc436-451 -> source callbacks.
        decision = DECISION.read_text()
        prefix = "https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/"
        for locator in ("config/translate_filters.go#L96", "detect/detect.go#L436",
                        "sources/common.go#L55", "sources/files.go#L117"):
            with self.subTest(locator=locator):
                self.assertTrue(prefix + locator in decision, f"Missing pinned betterleaks mechanism: {locator}")
        self.assertTrue("prefilter" in decision, "Decision must identify the native prefilter")
        self.assertFalse("Both implementations use" in decision, "The two scanners have different path mechanisms")

    def test_decision_pins_the_gitleaks_path_allowlist_definition(self):
        # gitleaks v8.30.1 defines PathAllowed at136, after the comment at135.
        decision = DECISION.read_text()
        self.assertTrue("https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/allowlist.go#L136" in decision,
                        "Gitleaks PathAllowed starts at136;135 is its comment")

    def test_decision_distinguishes_git_path_skipping_from_archive_blob_callback(self):
        # betterleaks v1.8.1 git.go:423 sets Path, :436 skips the entry,
        # :449-461 handles the archive blob and passes ShouldSkip to File at460.
        paragraphs = [line for line in DECISION.read_text().splitlines()
                      if line.startswith("- Betterleaks v1.8.1 translates")]
        self.assertEqual(len(paragraphs), 1, "Require one explicit pinned Git-source explanation")
        paragraph = paragraphs[0]
        self.assertIn("https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/sources/git.go#L436",
                      paragraph)
        self.assertRegex(paragraph,
            r"callback at :460 is propagated into the archive-blob `File` branch at :449[–-]461; "
            r"it is not the text-diff path",
            "Line460 is the archive File callback, not ordinary diff scanning")
        self.assertIn("sets the changed path at :423", paragraph)
        self.assertIn("applies `ShouldSkip` to its commit attributes", paragraph)

    def betterleaks_header(self):
        header = jobs(WORKFLOW.read_text())["secret-scan-betterleaks"].split("\n    steps:\n", 1)[0]
        return " ".join(line.strip().removeprefix("#").strip()
                        for line in header.splitlines() if line.lstrip().startswith("#"))

    def test_betterleaks_header_includes_resource_writer_failure_after_successful_scan(self):
        header = self.betterleaks_header()
        self.assertIn("verification, scanning or a test run errors", header)
        self.assertIn("required large-target regression fails", header)
        self.assertIn("resource-receipt writer fails after a successful scan", header,
                      "A successful scanner cannot hide a failed resource receipt writer")

    def test_betterleaks_header_binds_hosted_figures_to_the_named_historical_scope(self):
        header = self.betterleaks_header()
        self.assertNotIn("hosted-runner figures are pending", header,
                         "The retained hosted measurement has already completed")
        self.assertIn("Native hosted full git scan at run38053675250:19.01 s/1,074,456 KiB peak", header)
        self.assertRegex(header, r"took\s*64 s of\s*1,200 s, including verification/regressions/post steps")
        self.assertIn("The decision retains scope", header)
        decision = " ".join(DECISION.read_text().split())
        self.assertIn("[run38053675250](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/38053675250)",
                      decision)
        self.assertIn("attempt 1, `pull_request`, `refs/pull/964/merge`, exact checkout", decision)
        self.assertIn("`f2f10412c68a859800b2bcad034c8ab639fd6f2e`", decision,
                      "The checkout identifies measurement provenance, not a dependency pin")
        self.assertIn("| betterleaks 1.8.1 git, HEAD ancestry | 19.01 | 1074456 |", decision)
        self.assertIn("completed SUCCESS in 64 seconds of its 1,200-second limit", decision)

    def test_decision_labels_original_branch_point_and_published_landing_base(self):
        decision = " ".join(DECISION.read_text().split())
        self.assertFalse("The current base is main `c8a29c3ee9b4337564165d9e588b3fe81e8ba817`" in decision,
                         "The original branch point must not be described as the current base")
        self.assertTrue("The original branch point was main `c8a29c3ee9b4337564165d9e588b3fe81e8ba817`" in decision,
                        "Retain the original branch point with its historical label")
        self.assertTrue("The first published landing revision used main `0947b01289dcaa9157aa38392a94cf00f592b86d`" in decision,
                        "Record the published landing preparation's main base")


@unittest.skipUnless(GITLEAKS, "native gitleaks is needed for timer fallback controls")
class ScannerTimerTests(unittest.TestCase):
    def exercise(self, host, gnu):
        native_run = subprocess.run
        native_file = Path.is_file
        scanner_calls = []
        timer_calls = []
        console = io.StringIO()

        def is_file(path):
            return True if str(path) == "/usr/bin/time" else native_file(path)

        def run(command, *args, **kwargs):
            if command[0] == "/usr/bin/time":
                timer_calls.append(command)
                if "--version" in command:
                    return subprocess.CompletedProcess(command, 0 if gnu else 1,
                        stdout="time (GNU Time) 1.9" if gnu else "", stderr="")
                if not gnu:
                    # BSD time refuses these options before launching the scanner.
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="unsupported option")
            if command[0] == GITLEAKS or GITLEAKS in command:
                scanner_calls.append(command)
            return native_run(command, *args, **kwargs)

        with patch("platform.system", return_value=host), patch.object(Path, "is_file", is_file), \
                patch.object(subprocess, "run", run), redirect_stdout(console):
            try:
                findings = scan_fixture(GITLEAKS, "secret-scan", "dir", 256)
            except (AssertionError, FileNotFoundError):
                self.fail("Existing non-GNU timer prevented the scanner's detection")
        self.assertTrue(findings)
        self.assertEqual(len(scanner_calls), 1)
        metrics = json.loads(console.getvalue().split("large-file-scan-metrics: ", 1)[1])
        self.assertEqual(metrics["host"], host)
        return metrics, timer_calls

    def test_darwin_existing_bsd_time_does_not_prevent_scanner_detection(self):
        metrics, calls = self.exercise("Darwin", False)
        self.assertFalse(calls)
        self.assertNotIn("elapsed_seconds", metrics)
        self.assertNotIn("peak_rss_kib", metrics)

    def test_linux_existing_non_gnu_timer_falls_back_to_direct_detection(self):
        metrics, calls = self.exercise("Linux", False)
        self.assertEqual(len(calls), 1)
        self.assertIn("--version", calls[0])
        self.assertNotIn("elapsed_seconds", metrics)
        self.assertNotIn("peak_rss_kib", metrics)

    @unittest.skipUnless(platform.system() == "Linux" and Path("/usr/bin/time").is_file(),
                         "native GNU time needed on Linux")
    def test_linux_confirmed_gnu_time_retains_measured_detection(self):
        metrics, calls = self.exercise("Linux", True)
        self.assertEqual(len(calls), 2)
        self.assertIn("--version", calls[0])
        self.assertGreaterEqual(metrics["elapsed_seconds"], 0)
        self.assertGreater(metrics["peak_rss_kib"], 0)


class TimedWorkflowArgumentsTests(unittest.TestCase):
    def test_verified_gitleaks_job_runs_timer_portability_regressions(self):
        native_job = jobs(WORKFLOW.read_text())["secret-scan"]
        self.assertIn("tests.test_secret_scan_size.ScannerTimerTests", native_job,
                      "Timer portability controls must run with CI's verified gitleaks")

    def test_timing_prefix_keeps_all_four_production_scanner_options(self):
        source = WORKFLOW.read_text()
        timed = re.sub(r'(?m)^(\s*)("\$RUNNER_TEMP/(?:gitleaks/gitleaks|betterleaks/betterleaks)" (?:git|dir) \.)',
                       r'\1/usr/bin/time --quiet --format "%e %M" --output "$RUNNER_TEMP/time.txt" \2', source)
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / "validate.yml"
            file.write_text(timed)
            with patch(__name__ + ".WORKFLOW", file):
                for job in ("secret-scan", "secret-scan-betterleaks"):
                    for mode in ("git", "dir"):
                        with self.subTest(job=job, mode=mode):
                            try:
                                args = workflow_scanner_arguments(job, mode)
                            except AssertionError:
                                self.fail("Canary parser lost production scanner options behind GNU time")
                            self.assertEqual(args[:2], ["--config", ".gitleaks.toml"])
                            self.assertIn("--redact", args)
                            if mode == "git":
                                self.assertIn("--log-opts=$SCAN_LOG_OPTS", args)
                            if job == "secret-scan-betterleaks":
                                self.assertIn("--exit-code", args)
                                self.assertTrue(".gitleaksignore" in args or "${SCAN_IGNORE_PATH:-.gitleaksignore}" in args)


@unittest.skipUnless(GITLEAKS, "gitleaks is installed in its native secret-scan job")
class GitleaksLargeFileTests(unittest.TestCase):
    def test_verified_event_scope_keeps_large_targets_and_the_exact_explorer_exclusion(self):
        for event in ("pull_request", "push"):
            with self.subTest(event=event):
                self.assertTrue(scan_fixture(GITLEAKS, "secret-scan", "git", 3_000_000,
                                             event_scope=event),
                                "Verified event scope must not restore the old large-target skip")
                self.assertEqual(scan_fixture(GITLEAKS, "secret-scan", "git", 3_000_000,
                                              path="docs/ecosystem/index.html", event_scope=event), [])

    def test_git_and_dir_find_canaries_above_both_old_skip_boundaries(self):
        for mode in ("git", "dir"):
            for size in SIZES:
                with self.subTest(mode=mode, size=size):
                    self.assertTrue(scan_fixture(GITLEAKS, "secret-scan", mode, size),
                                    "Native workflow arguments silently skip this large canary target")

    def test_only_the_exact_generated_explorer_path_is_excluded(self):
        for mode in ("git", "dir"):
            with self.subTest(mode=mode):
                self.assertEqual(scan_fixture(GITLEAKS, "secret-scan", mode, 256,
                                              path="docs/ecosystem/index.html"), [])
                self.assertTrue(scan_fixture(GITLEAKS, "secret-scan", mode, 256,
                                             path="docs/ecosystem/index.html.extra"))
                self.assertTrue(scan_fixture(GITLEAKS, "secret-scan", mode, 256,
                                             path="other/docs/ecosystem/index.html"))


@unittest.skipUnless(BETTERLEAKS, "verified CI betterleaks binary is supplied explicitly")
class BetterleaksLargeFileTests(unittest.TestCase):
    def test_dir_finds_canaries_above_both_old_skip_boundaries(self):
        self.assertEqual(subprocess.check_output([BETTERLEAKS, "version"], text=True).strip(), "1.8.1")
        for size in SIZES:
            with self.subTest(size=size):
                self.assertTrue(scan_fixture(BETTERLEAKS, "secret-scan-betterleaks", "dir", size),
                                "Native betterleaks workflow arguments silently skip this large canary target")

    def test_only_the_exact_generated_explorer_path_is_excluded(self):
        self.assertEqual(scan_fixture(BETTERLEAKS, "secret-scan-betterleaks", "dir", 256,
                                      path="docs/ecosystem/index.html"), [])
        self.assertTrue(scan_fixture(BETTERLEAKS, "secret-scan-betterleaks", "dir", 256,
                                     path="docs/ecosystem/index.html.extra"))


if __name__ == "__main__":
    unittest.main()
