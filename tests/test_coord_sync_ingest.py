#!/usr/bin/env python3
"""Tests for tools/coord-sync/ingest_coord_sync.py against temporary staging and coordination roots (stdlib unittest)."""
import contextlib
import hashlib
import importlib.util
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'coord-sync' / 'ingest_coord_sync.py'
GPT = 'cc-reads-20261005/uet122-pr122/GPT-VERDICT-c1e90354-x.md'
TCC = 'trading-cc/reads/READ-uet122-c1e90354.md'
CCV = 'cc-cc-work/uet122-micro/CC-DELTA-c1e90354.md'
MIC = 'cc-cc-work/uet122-micro/MICRO-delta-c1e90354.md'
RCP = 'command-center/receipts/cc-dula-close-20261016.md'


def load(staging, coord):
    os.environ['COORD_SYNC_STAGING'] = str(staging)
    os.environ['COORD_ROOT'] = str(coord)
    os.environ['COORD_SYNC_NO_ALERT'] = '1'
    spec = importlib.util.spec_from_file_location('ingest', TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def batch(staging, name, files):
    b = staging / name
    for rel, text in files.items():
        p = b / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    lines = [f'{hashlib.sha256(t.encode()).hexdigest()}  {rel}' for rel, t in files.items()]
    (b / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
    return b


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.staging, self.coord = root / 'staging', root / 'coord'
        self.staging.mkdir()
        self.m = load(self.staging, self.coord)
        self.alerts = []
        self.m.alert = self.alerts.append

    def tearDown(self):
        self.tmp.cleanup()

    def written(self):
        return sorted(str(p.relative_to(self.coord)) for p in self.coord.rglob('*')
                      if p.is_file() and not p.name.startswith('.sync-ingest'))

    def test_new_files_in_all_three_scopes_land_read_only_with_marker(self):
        batch(self.staging, '20261016T205433Z', {GPT: 'g\n', TCC: 't\n', CCV: 'c\n', MIC: 'm\n'})
        self.assertEqual(self.m.main(), 0)
        self.assertEqual(self.written(), sorted([GPT, TCC, CCV, MIC]))
        self.assertTrue(all(os.stat(self.coord / r).st_mode & 0o777 == 0o444 for r in (GPT, TCC, CCV, MIC)))
        self.assertTrue((self.staging / '20261016T205433Z.ingested').exists())
        self.assertEqual(self.m.main(), 0)  # idempotent: the marker matches, nothing re-runs
        self.assertEqual(self.alerts, [])

    def test_tampered_file_refuses_and_writes_nothing(self):
        b = batch(self.staging, '20261016T205433Z', {GPT: 'a\n', TCC: 'b\n'})
        (b / TCC).write_text('tampered\n')
        self.assertEqual(self.m.main(), 2)
        self.assertEqual(self.written(), [])
        self.assertFalse((self.staging / '20261016T205433Z.ingested').exists())

    def test_unlisted_file_refuses(self):
        b = batch(self.staging, '20261016T205433Z', {GPT: 'a\n'})
        (b / 'trading-cc/reads').mkdir(parents=True)
        (b / 'trading-cc/reads/extra.md').write_text('x\n')
        self.assertEqual(self.m.main(), 2)
        self.assertEqual(self.written(), [])

    def test_symlink_refuses(self):
        b = batch(self.staging, '20261016T205433Z', {GPT: 'a\n'})
        os.symlink('/etc/hostname', b / 'cc-reads-20261005/uet122-pr122/GPT-link.md')
        self.assertEqual(self.m.main(), 2)
        self.assertEqual(self.written(), [])

    def test_out_of_scope_parent_path_and_brief_refuse(self):
        batch(self.staging, '20261016T205433Z', {'command-center/cc-tools/uet_land.sh': 'x\n'})
        self.assertEqual(self.m.main(), 2)
        (self.staging / '20261016T205433Z.refused').unlink()
        (self.staging / '20261016T205433Z' / 'SHA256SUMS').write_text(
            f'{hashlib.sha256(b"x").hexdigest()}  ../escape.md\n')
        self.assertEqual(self.m.main(), 2)
        self.assertEqual(self.written(), [])
        other = Path(self.tmp.name) / 'staging2'
        other.mkdir()
        m2 = load(other, self.coord)
        m2.alert = self.alerts.append
        batch(other, '20261016T205433Z', {'cc-cc-work/uet122-micro/BRIEF-delta-c1e90354.md': 'b\n'})
        self.assertEqual(m2.main(), 2)
        self.assertEqual(self.written(), [])

    def test_same_path_change_refuses_in_every_scope(self):
        batch(self.staging, '20261016T205433Z', {GPT: 'g1\n', TCC: 't1\n', CCV: 'c1\n'})
        self.assertEqual(self.m.main(), 0)
        for i, rel in enumerate((GPT, TCC, CCV)):
            name = f'20261016T21{i}000Z'
            batch(self.staging, name, {rel: 'changed\n'})
            self.assertEqual(self.m.main(), 2, rel)
            self.assertNotEqual((self.coord / rel).read_text(), 'changed\n', rel)
            os.rename(self.staging / name, Path(self.tmp.name) / f'aside-{i}')
            (self.staging / f'{name}.refused').unlink()
        self.assertEqual(len(self.alerts), 3)

    def test_refused_batch_blocks_later_batches(self):
        b = batch(self.staging, '20261016T205433Z', {GPT: 'a\n'})
        (b / GPT).write_text('tampered\n')
        batch(self.staging, '20261016T210000Z', {TCC: 'later\n'})
        self.assertEqual(self.m.main(), 2)
        self.assertEqual(self.written(), [])
        self.assertFalse((self.staging / '20261016T210000Z.ingested').exists())

    def test_refusal_is_reported_and_alerted_once(self):
        b = batch(self.staging, '20261016T205433Z', {GPT: 'a\n'})
        (b / GPT).write_text('tampered\n')
        self.assertEqual(self.m.main(), 2)
        self.assertEqual(self.m.main(), 2)
        refusals = [l for l in (self.coord / '.sync-ingest.log').read_text().splitlines() if 'REFUSED' in l]
        self.assertEqual(len(refusals), 1)
        self.assertEqual(len(self.alerts), 1)
        self.assertTrue((self.staging / '20261016T205433Z.refused').exists())

    def test_incomplete_batch_is_skipped(self):
        b = self.staging / '20261016T205433Z'
        (b / 'cc-reads-20261005/x-pr1').mkdir(parents=True)
        (b / 'cc-reads-20261005/x-pr1/GPT-VERDICT-aaaaaaaa.md').write_text('a\n')
        self.assertEqual(self.m.main(), 0)
        self.assertEqual(self.written(), [])

    def test_mid_batch_failure_is_logged_alerted_and_completed_by_next_run(self):
        batch(self.staging, '20261016T205433Z', {GPT: 'g\n', TCC: 't\n', CCV: 'c\n'})
        orig_place = self.m.place
        calls = []

        def flaky_place(src, dst, *args):
            calls.append(src)
            if len(calls) == 2:
                raise OSError('injected mid-batch failure')
            return orig_place(src, dst, *args)

        self.m.place = flaky_place
        self.assertEqual(self.m.main(), 2)
        self.assertEqual(len(self.written()), 1)
        self.assertFalse((self.staging / '20261016T205433Z.ingested').exists())
        self.assertFalse((self.staging / '20261016T205433Z.refused').exists())
        self.assertEqual(len(self.alerts), 1)
        failed = [l for l in (self.coord / '.sync-ingest.log').read_text().splitlines() if 'FAILED' in l]
        self.assertEqual(len(failed), 1)
        self.m.place = orig_place
        self.assertEqual(self.m.main(), 0)
        self.assertEqual(self.written(), sorted([GPT, TCC, CCV]))
        self.assertTrue((self.staging / '20261016T205433Z.ingested').exists())
        self.assertEqual(len(self.alerts), 1)

    def test_persistent_mid_batch_failure_alerts_once_until_success_clears_flag(self):
        batch(self.staging, '20261016T205433Z', {GPT: 'g\n', TCC: 't\n', CCV: 'c\n'})
        orig_place = self.m.place
        calls = []

        def failing_place(src, dst, *args):
            calls.append(src)
            if len(calls) == 1:
                return orig_place(src, dst, *args)
            raise OSError('injected persistent failure')

        self.m.place = failing_place
        self.assertEqual(self.m.main(), 2)
        self.assertEqual(self.m.main(), 2)
        self.assertEqual(len(self.alerts), 1)
        failed = [l for l in (self.coord / '.sync-ingest.log').read_text().splitlines() if 'FAILED' in l]
        self.assertEqual(len(failed), 1)
        self.assertTrue((self.staging / '20261016T205433Z.failed').exists())
        self.assertFalse((self.staging / '20261016T205433Z.ingested').exists())
        self.assertFalse((self.staging / '20261016T205433Z.refused').exists())
        self.m.place = orig_place
        self.assertEqual(self.m.main(), 0)
        self.assertEqual(self.written(), sorted([GPT, TCC, CCV]))
        self.assertTrue((self.staging / '20261016T205433Z.ingested').exists())
        self.assertFalse((self.staging / '20261016T205433Z.failed').exists())
        self.assertEqual(len(self.alerts), 1)

    def test_failed_alert_and_exit_2_survive_log_failure(self):
        batch(self.staging, '20261016T205433Z', {GPT: 'g\n'})

        def failing_place(src, dst, *args):
            raise OSError('injected copy failure')

        def failing_log(line):
            raise OSError('injected log failure')

        self.m.place = failing_place
        self.m.log = failing_log
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = self.m.main()
        self.assertEqual(rc, 2)
        self.assertEqual(len(self.alerts), 1)
        self.assertIn('FAILED', out.getvalue())

    def test_file_changed_between_verify_and_copy_is_not_installed(self):
        batch(self.staging, '20261016T205433Z', {GPT: 'good\n', CCV: 'first\n'})
        orig_place = self.m.place

        def tampering_place(src, dst, *args):
            if Path(src).name == Path(GPT).name:
                Path(src).write_text('evil\n')  # changed after SHA256SUMS was written and verified
            return orig_place(src, dst, *args)

        self.m.place = tampering_place
        self.assertEqual(self.m.main(), 2)
        self.assertEqual(self.written(), [CCV])
        self.assertFalse((self.coord / GPT).exists())
        self.assertFalse((self.staging / '20261016T205433Z.ingested').exists())
        self.assertEqual(len(self.alerts), 1)
        self.assertNotIn('completes it once the fault clears', self.alerts[0])
        leftovers = list(self.coord.rglob('.ingest-*')) if self.coord.exists() else []
        self.assertEqual(leftovers, [])
        self.m.place = orig_place
        self.assertEqual(self.m.main(), 2)  # the changed staged file now refuses in plan()
        self.assertEqual(self.written(), [CCV])  # the file copied by the earlier run stays
        self.assertFalse((self.coord / GPT).exists())
        self.assertTrue((self.staging / '20261016T205433Z.refused').exists())
        self.assertFalse((self.staging / '20261016T205433Z.ingested').exists())
        self.assertEqual(len(self.alerts), 2)
        self.assertNotIn('Nothing from it was written', self.alerts[1])
        self.assertIn('in this run', self.alerts[1])
        log_text = (self.coord / '.sync-ingest.log').read_text()
        self.assertIn('nothing written in this run', log_text)

    def test_batch_vanishing_before_hash_is_skipped(self):
        b = batch(self.staging, '20261016T205433Z', {GPT: 'g\n'})
        batch(self.staging, '20261016T210000Z', {TCC: 'later\n'})
        orig_sha256 = self.m.sha256

        def vanishing_sha256(path):
            if Path(path) == b / 'SHA256SUMS' and b.exists():
                shutil.rmtree(b)  # the 2604 side deleted the batch after main()'s is_file check
            return orig_sha256(path)

        self.m.sha256 = vanishing_sha256
        self.assertEqual(self.m.main(), 0)
        self.assertEqual(self.written(), [TCC])
        self.assertEqual(self.alerts, [])
        self.assertTrue((self.staging / '20261016T210000Z.ingested').exists())
        self.assertFalse((self.staging / '20261016T205433Z.failed').exists())
        self.assertFalse((self.staging / '20261016T205433Z.refused').exists())
        log_text = (self.coord / '.sync-ingest.log').read_text() if (self.coord / '.sync-ingest.log').exists() else ''
        self.assertNotIn('FAILED', log_text)

    def test_symlinked_batch_directory_is_skipped(self):
        target_root = Path(self.tmp.name) / 'elsewhere'
        target_root.mkdir()
        batch(target_root, '20261016T205433Z', {GPT: 'g\n'})
        os.symlink(target_root / '20261016T205433Z', self.staging / '20261016T205433Z', target_is_directory=True)
        batch(self.staging, '20261016T210000Z', {TCC: 'later\n'})
        self.assertEqual(self.m.main(), 0)
        self.assertEqual(self.written(), [TCC])
        self.assertFalse((self.staging / '20261016T205433Z.ingested').exists())
        self.assertTrue((self.staging / '20261016T210000Z.ingested').exists())

    def test_cc_receipt_lands_and_nested_or_non_md_receipts_refuse(self):
        batch(self.staging, '20261016T225519Z', {RCP: 'closing record\n'})
        self.assertEqual(self.m.main(), 0)
        self.assertEqual(self.written(), [RCP])
        self.assertEqual(os.stat(self.coord / RCP).st_mode & 0o777, 0o444)
        for i, rel in enumerate(('command-center/receipts/sub/x.md', 'command-center/receipts/x.sh', 'command-center/x.md')):
            name = f'20261016T23{i}000Z'
            batch(self.staging, name, {rel: 'x\n'})
            self.assertEqual(self.m.main(), 2, rel)
            os.rename(self.staging / name, Path(self.tmp.name) / f'aside-r{i}')
            (self.staging / f'{name}.refused').unlink()
        self.assertEqual(self.written(), [RCP])


class MissingStagingTests(unittest.TestCase):
    def test_unset_or_empty_staging_exits_3_and_creates_nothing(self):
        saved = {k: os.environ.get(k) for k in ('COORD_SYNC_STAGING', 'COORD_ROOT', 'COORD_SYNC_NO_ALERT')}
        try:
            for value in (None, ''):
                with self.subTest(value=value), tempfile.TemporaryDirectory() as t:
                    root = Path(t)
                    coord = root / 'coord'
                    if value is None:
                        os.environ.pop('COORD_SYNC_STAGING', None)
                    else:
                        os.environ['COORD_SYNC_STAGING'] = value
                    os.environ['COORD_ROOT'] = str(coord)
                    os.environ['COORD_SYNC_NO_ALERT'] = '1'
                    spec = importlib.util.spec_from_file_location('ingest', TOOL)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        self.assertEqual(mod.main(), 3)
                    lines = out.getvalue().strip().splitlines()
                    self.assertEqual(len(lines), 1)
                    self.assertIn('COORD_SYNC_STAGING', lines[0])
                    self.assertFalse(coord.exists())
                    self.assertEqual(list(root.iterdir()), [])
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


    def test_relative_or_placeholder_staging_exits_3_and_creates_nothing(self):
        saved = {k: os.environ.get(k) for k in ('COORD_SYNC_STAGING', 'COORD_ROOT', 'COORD_SYNC_NO_ALERT')}
        cwd = os.getcwd()
        try:
            for label in ('relative', 'placeholder', 'absolute-placeholder'):
                with self.subTest(label=label), tempfile.TemporaryDirectory() as t:
                    root = Path(t)
                    coord = root / 'coord'
                    if label == 'relative':
                        value = 'relative-staging'
                    elif label == 'placeholder':
                        value = '@WINDOWS_TEMP@/nhny-coord-sync'
                    else:
                        value = str(root / '@WINDOWS_TEMP@' / 'nhny-coord-sync')
                    os.environ['COORD_SYNC_STAGING'] = value
                    os.environ['COORD_ROOT'] = str(coord)
                    os.environ['COORD_SYNC_NO_ALERT'] = '1'
                    spec = importlib.util.spec_from_file_location('ingest', TOOL)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    os.chdir(root)
                    try:
                        out = io.StringIO()
                        with contextlib.redirect_stdout(out):
                            rc = mod.main()
                    finally:
                        os.chdir(cwd)
                    self.assertEqual(rc, 3)
                    lines = out.getvalue().strip().splitlines()
                    self.assertEqual(len(lines), 1)
                    self.assertIn('COORD_SYNC_STAGING', lines[0])
                    self.assertFalse(coord.exists())
                    self.assertEqual(list(root.iterdir()), [])
        finally:
            os.chdir(cwd)
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class DocstringAndTemplateTests(unittest.TestCase):
    def test_docstring_documents_invalid_staging_exit_3(self):
        with tempfile.TemporaryDirectory() as t:
            m = load(Path(t) / 'staging', Path(t) / 'coord')
            doc = m.__doc__ or ''
            self.assertIn('COORD_SYNC_STAGING', doc)
            self.assertIn("contains '@'", doc)

    def test_ingest_service_template_quotes_staging_assignment(self):
        text = (ROOT / 'adoption/templates/systemd/nhny-coord-sync-ingest.service').read_text()
        self.assertIn('Environment="COORD_SYNC_STAGING=', text)


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
            saved = {k: os.environ.get(k) for k in ('PATH', 'HOME', 'COORD_SYNC_NO_ALERT')}
            try:
                m = load(home / 'staging', home / 'coord')
                os.environ.update(PATH='/usr/bin:/bin', HOME=str(home))
                os.environ['COORD_SYNC_NO_ALERT'] = '0'
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
