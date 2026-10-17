#!/usr/bin/env python3
"""Tests for tools/coord-sync/publish_cc_verdicts.py against temporary roots (stdlib unittest)."""
import contextlib
import hashlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'coord-sync' / 'publish_cc_verdicts.py'


def load(src, staging, ledger):
    os.environ.update(CC_VERDICT_SRC=str(src), REVERSE_SYNC_STAGING=str(staging), REVERSE_SYNC_LEDGER=str(ledger),
                      REVERSE_SYNC_NO_ALERT='1')
    spec = importlib.util.spec_from_file_location('publish', TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def put(path, text, sealed=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        os.chmod(path, 0o600)
    path.write_text(text)
    os.chmod(path, 0o400 if sealed else 0o644)


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = Path(self.tmp.name)
        self.src, self.staging, self.ledger = r / 'src', r / 'staging', r / 'ledger.tsv'
        self.src.mkdir()
        self.m = load(self.src, self.staging, self.ledger)
        self.alerts = []
        self.m.alert = self.alerts.append

    def tearDown(self):
        for p in Path(self.tmp.name).rglob('*'):
            if p.is_file() and not p.is_symlink():
                os.chmod(p, 0o600)
        self.tmp.cleanup()

    def batches(self):
        return sorted(p for p in self.staging.iterdir() if p.is_dir()) if self.staging.exists() else []

    def test_only_sealed_cc_and_micro_files_in_micro_dirs_are_staged(self):
        put(self.src / 'uet131-micro/CC-FULL-6d5c8c00.md', 'VERDICT: PASS at 6d5c8c00\n')
        put(self.src / 'uet131-micro/MICRO-full-6d5c8c00.md', 'micro\n')
        put(self.src / 'uet131-micro/CC-DELTA-unsealed.md', 'draft\n', sealed=False)
        put(self.src / 'uet131-micro/BRIEF-full-6d5c8c00.md', 'brief\n')
        put(self.src / 'uet131-6d5c8c00/CC-FULL-x.md', 'a worktree, not a micro dir\n')
        os.symlink(self.src / 'uet131-micro/CC-FULL-6d5c8c00.md', self.src / 'uet131-micro/CC-FULL-link.md')
        self.assertEqual(self.m.main(), 0)
        [b] = self.batches()
        sums = (b / 'SHA256SUMS').read_text().splitlines()
        rels = sorted(l.split('  ', 1)[1] for l in sums)
        self.assertEqual(rels, ['cc-cc-work/uet131-micro/CC-FULL-6d5c8c00.md', 'cc-cc-work/uet131-micro/MICRO-full-6d5c8c00.md'])
        for l in sums:
            digest, rel = l.split('  ', 1)
            self.assertEqual(hashlib.sha256((b / rel).read_bytes()).hexdigest(), digest)
        self.assertFalse((b / 'SHA256SUMS.tmp').exists())
        self.assertEqual(self.m.main(), 0)  # idempotent: nothing new, no second batch
        self.assertEqual(len(self.batches()), 1)

    def test_same_path_change_refuses_and_alerts_once(self):
        f = self.src / 'uet131-micro/CC-FULL-6d5c8c00.md'
        put(f, 'VERDICT: PASS at 6d5c8c00\n')
        self.assertEqual(self.m.main(), 0)
        put(f, 'VERDICT: CHANGES_REQUESTED at 6d5c8c00\n')
        put(self.src / 'uet131-micro/MICRO-new.md', 'new\n')
        self.assertEqual(self.m.main(), 2)
        self.assertEqual(self.m.main(), 2)
        self.assertEqual(len(self.batches()), 1)  # nothing staged by the refused runs
        self.assertEqual(len(self.alerts), 1)

    def test_cleanup_removes_only_batches_with_a_matching_marker(self):
        put(self.src / 'a-micro/CC-DELTA-11111111.md', 'one\n')
        self.assertEqual(self.m.main(), 0)
        [b1] = self.batches()
        (self.staging / f'{b1.name}.ingested').write_text(
            hashlib.sha256((b1 / 'SHA256SUMS').read_bytes()).hexdigest() + ' 2026-10-16T21:50:00Z\n')
        b2 = self.staging / '20200101T000000Z'
        b2.mkdir()
        (b2 / 'SHA256SUMS').write_text('x\n')
        (self.staging / '20200101T000000Z.ingested').write_text('0' * 64 + ' wrong\n')
        self.assertEqual(self.m.main(), 0)
        self.assertFalse(b1.exists())
        self.assertFalse((self.staging / f'{b1.name}.ingested').exists())
        self.assertTrue(b2.exists())


class MissingStagingTests(unittest.TestCase):
    def test_unset_or_empty_staging_exits_3_and_creates_nothing(self):
        saved = {k: os.environ.get(k) for k in ('CC_VERDICT_SRC', 'REVERSE_SYNC_STAGING', 'REVERSE_SYNC_LEDGER', 'REVERSE_SYNC_NO_ALERT')}
        try:
            for value in (None, ''):
                with self.subTest(value=value), tempfile.TemporaryDirectory() as t:
                    root = Path(t)
                    src, ledger = root / 'src', root / 'ledger.tsv'
                    sealed = src / 'a-micro/CC-DELTA-11111111.md'
                    put(sealed, 'one\n')
                    before = sorted(str(p.relative_to(root)) for p in root.rglob('*'))
                    if value is None:
                        os.environ.pop('REVERSE_SYNC_STAGING', None)
                    else:
                        os.environ['REVERSE_SYNC_STAGING'] = value
                    os.environ.update(CC_VERDICT_SRC=str(src), REVERSE_SYNC_LEDGER=str(ledger), REVERSE_SYNC_NO_ALERT='1')
                    spec = importlib.util.spec_from_file_location('publish', TOOL)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        self.assertEqual(mod.main(), 3)
                    lines = out.getvalue().strip().splitlines()
                    self.assertEqual(len(lines), 1)
                    self.assertIn('REVERSE_SYNC_STAGING', lines[0])
                    self.assertFalse(ledger.exists())
                    self.assertEqual(sorted(str(p.relative_to(root)) for p in root.rglob('*')), before)
                    os.chmod(sealed, 0o600)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class AlertTests(unittest.TestCase):
    def test_alert_reaches_hcom_off_path_and_names_the_cc_and_the_fallback(self):
        # A systemd --user unit's PATH lacks ~/.local/bin (systemd 259 here), so the 2026-10-16T22:55:43Z refusal's alert
        # died with FileNotFoundError. The stub hcom sits only in $HOME/.local/bin and records its argv.
        with tempfile.TemporaryDirectory() as t:
            home = Path(t)
            out = home / 'argv.txt'
            stub = home / '.local/bin/hcom'
            stub.parent.mkdir(parents=True)
            stub.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "' + str(out) + '"\n')
            stub.chmod(0o755)
            saved = {k: os.environ.get(k) for k in ('PATH', 'HOME', 'REVERSE_SYNC_NO_ALERT')}
            try:
                m = load(home / 'src', home / 'staging', home / 'ledger.tsv')
                os.environ.update(PATH='/usr/bin:/bin', HOME=str(home))
                os.environ['REVERSE_SYNC_NO_ALERT'] = '0'
                m.alert('probe text')
            finally:
                for k, v in saved.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
            self.assertTrue(out.exists(), 'the alert never reached hcom')
            argv = out.read_text().splitlines()
            self.assertEqual(argv[:3], ['send', '@nhny-gino', '@nami'])  # dula closed (#2427); the co-op holds the fallback
            self.assertNotIn('@dula', argv)
            self.assertEqual(argv[-1], 'probe text')

if __name__ == '__main__':
    unittest.main(verbosity=2)
