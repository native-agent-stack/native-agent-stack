#!/usr/bin/env python3
"""Tests for tools/coord-sync/publish_cc_verdicts.py against temporary roots (stdlib unittest)."""
import contextlib
import hashlib
import importlib.util
import io
import os
import subprocess
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

    def test_staging_failure_alerts_once_removes_incomplete_batch_and_retries(self):
        put(self.src / 'uet131-micro/CC-FULL-6d5c8c00.md', 'VERDICT: PASS at 6d5c8c00\n')
        put(self.src / 'uet131-micro/MICRO-full-6d5c8c00.md', 'micro\n')
        orig_copy2 = self.m.shutil.copy2
        calls = []

        def failing_copy2(src, dst, *args, **kwargs):
            calls.append(src)
            if len(calls) == 1:
                return orig_copy2(src, dst, *args, **kwargs)
            raise OSError('injected staging failure')

        self.m.shutil.copy2 = failing_copy2
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(self.m.main(), 2)
                self.assertEqual(self.m.main(), 2)
        finally:
            self.m.shutil.copy2 = orig_copy2
        self.assertIn('FAILED', out.getvalue())
        self.assertEqual(len(self.alerts), 1)
        self.assertEqual(self.batches(), [])  # the incomplete batch was removed
        self.assertFalse(self.ledger.exists())
        self.assertEqual(self.m.main(), 0)
        self.assertEqual(len(self.batches()), 1)
        self.assertEqual(len(self.ledger.read_text().splitlines()), 2)
        self.assertFalse((self.staging / '.publisher-failed').exists())
        self.assertEqual(len(self.alerts), 1)

    def test_staging_failure_with_per_run_batch_name_alerts_once(self):
        # Each run stages under a fresh STAGING/<UTC>/ name; the dedup key must strip that prefix.
        put(self.src / 'uet131-micro/CC-FULL-6d5c8c00.md', 'VERDICT: PASS at 6d5c8c00\n')
        orig_copy2, orig_utc = self.m.shutil.copy2, self.m.utc
        stamps = iter(['20261017T050000Z', '20261017T050100Z', '20261017T050200Z'])

        def fake_utc(fmt='%Y-%m-%dT%H:%M:%SZ'):
            return next(stamps) if fmt == '%Y%m%dT%H%M%SZ' else '2026-10-17T05:00:00Z'

        def failing_copy2(src, dst, *args, **kwargs):
            e = OSError(28, 'No space left on device', str(src))
            e.filename2 = str(dst)
            raise e

        self.m.utc, self.m.shutil.copy2 = fake_utc, failing_copy2
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc1, rc2 = self.m.main(), self.m.main()
            flag_text = (self.staging / '.publisher-failed').read_text()
            self.m.shutil.copy2 = orig_copy2
            rc3 = self.m.main()
        finally:
            self.m.shutil.copy2, self.m.utc = orig_copy2, orig_utc
        self.assertEqual((rc1, rc2, rc3), (2, 2, 0))
        self.assertIn('FAILED', out.getvalue())
        self.assertEqual(len(self.alerts), 1)
        self.assertNotIn('20261017T050000Z', flag_text)
        self.assertNotIn('20261017T050100Z', flag_text)
        self.assertEqual(len(self.batches()), 1)
        self.assertFalse((self.staging / '.publisher-failed').exists())

    def test_ledger_append_failure_is_labelled_and_batch_stays(self):
        put(self.src / 'uet131-micro/CC-FULL-6d5c8c00.md', 'VERDICT: PASS at 6d5c8c00\n')
        orig_copy2 = self.m.shutil.copy2

        def ledger_blocking_copy2(src, dst, *args, **kwargs):
            result = orig_copy2(src, dst, *args, **kwargs)
            self.ledger.mkdir(exist_ok=True)  # the append then fails after SHA256SUMS is in place
            return result

        self.m.shutil.copy2 = ledger_blocking_copy2
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = self.m.main()
        finally:
            self.m.shutil.copy2 = orig_copy2
        self.assertEqual(rc, 2)
        [b] = self.batches()
        self.assertTrue((b / 'SHA256SUMS').exists())
        self.assertEqual(len(self.alerts), 1)
        self.assertIn('ledger append failed', self.alerts[0])
        self.assertNotIn('staging failed', self.alerts[0])
        self.assertIn('complete', self.alerts[0])
        self.assertIn('ledger append failed', out.getvalue())
        self.ledger.rmdir()
        (self.staging / f'{b.name}.ingested').write_text(
            hashlib.sha256((b / 'SHA256SUMS').read_bytes()).hexdigest() + ' 2026-10-17T05:10:00Z\n')
        self.assertEqual(self.m.main(), 0)
        self.assertEqual(len(self.ledger.read_text().splitlines()), 1)
        self.assertFalse((self.staging / '.publisher-failed').exists())

    def test_truncated_ledger_line_is_ignored_not_refused(self):
        put(self.src / 'a-micro/CC-DELTA-11111111.md', 'one\n')
        self.ledger.write_text('cc-cc-work/a-micro/CC-DELTA-11111111.md\tabc123\t20200101T000000Z\t2020-01-01T00:00:00Z\n')
        self.assertEqual(self.m.main(), 0)
        self.assertEqual(len(self.batches()), 1)
        self.assertEqual(self.alerts, [])
        self.assertEqual(len(self.ledger.read_text().splitlines()), 2)

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


    def test_relative_or_placeholder_staging_exits_3_and_creates_nothing(self):
        saved = {k: os.environ.get(k) for k in ('CC_VERDICT_SRC', 'REVERSE_SYNC_STAGING', 'REVERSE_SYNC_LEDGER', 'REVERSE_SYNC_NO_ALERT')}
        cwd = os.getcwd()
        try:
            for label in ('relative', 'placeholder', 'absolute-placeholder'):
                with self.subTest(label=label), tempfile.TemporaryDirectory() as t:
                    root = Path(t)
                    src, ledger = root / 'src', root / 'ledger.tsv'
                    sealed = src / 'a-micro/CC-DELTA-11111111.md'
                    put(sealed, 'one\n')
                    before = sorted(str(p.relative_to(root)) for p in root.rglob('*'))
                    if label == 'relative':
                        value = 'relative-staging'
                    elif label == 'placeholder':
                        value = '@WINDOWS_TEMP@/nhny-to-2604-sync'
                    else:
                        value = str(root / '@WINDOWS_TEMP@' / 'nhny-to-2604-sync')
                    os.environ['REVERSE_SYNC_STAGING'] = value
                    os.environ.update(CC_VERDICT_SRC=str(src), REVERSE_SYNC_LEDGER=str(ledger), REVERSE_SYNC_NO_ALERT='1')
                    spec = importlib.util.spec_from_file_location('publish', TOOL)
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
                    self.assertIn('REVERSE_SYNC_STAGING', lines[0])
                    self.assertFalse(ledger.exists())
                    self.assertEqual(sorted(str(p.relative_to(root)) for p in root.rglob('*')), before)
                    os.chmod(sealed, 0o600)
        finally:
            os.chdir(cwd)
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


    def test_missing_staging_parent_exits_3_and_creates_nothing(self):
        saved = {k: os.environ.get(k) for k in ('CC_VERDICT_SRC', 'REVERSE_SYNC_STAGING', 'REVERSE_SYNC_LEDGER', 'REVERSE_SYNC_NO_ALERT')}
        try:
            with self.subTest(label='missing-parent'), tempfile.TemporaryDirectory() as t:
                root = Path(t)
                src, ledger = root / 'src', root / 'ledger.tsv'
                sealed = src / 'a-micro/CC-DELTA-11111111.md'
                put(sealed, 'one\n')
                staging = root / 'missing-parent' / 'staging'  # absolute and '@'-free, under a missing parent
                before = sorted(str(p.relative_to(root)) for p in root.rglob('*'))
                mod = load(src, staging, ledger)
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    rc = mod.main()
                self.assertEqual(rc, 3)
                self.assertFalse((root / 'missing-parent').exists())
                self.assertFalse(ledger.exists())
                self.assertEqual(sorted(str(p.relative_to(root)) for p in root.rglob('*')), before)
                os.chmod(sealed, 0o600)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class DocstringTemplateAndReadmeTests(unittest.TestCase):
    def test_docstring_documents_invalid_staging_exit_3(self):
        with tempfile.TemporaryDirectory() as t:
            m = load(Path(t) / 'src', Path(t) / 'staging', Path(t) / 'ledger.tsv')
            doc = m.__doc__ or ''
            self.assertIn('REVERSE_SYNC_STAGING', doc)
            self.assertIn("contains '@'", doc)

    def test_publish_service_template_quotes_staging_assignment(self):
        text = (ROOT / 'adoption/templates/systemd/nhny-cc-verdict-publish.service').read_text()
        self.assertIn('Environment="REVERSE_SYNC_STAGING=', text)

    def test_readme_renders_placeholders_without_sed_replacement_hazards(self):
        text = (ROOT / 'tools/coord-sync/README.md').read_text()
        self.assertNotIn('s#@WINDOWS_TEMP@#$WINDOWS_TEMP', text)
        self.assertIn('python3 -I', text)

    def test_readme_pins_systemd_and_sed_citations(self):
        text = (ROOT / 'tools/coord-sync/README.md').read_text()
        self.assertIn('`systemd.exec(5)` at systemd 259', text)
        self.assertIn('systemd.unit(5)', text)
        self.assertIn('GNU sed 4.9', text)

    def test_readme_renderer_escapes_percent_and_preserves_repository_specifier(self):
        text = (ROOT / 'tools/coord-sync/README.md').read_text()
        render_line = next(l for l in text.splitlines() if l.startswith('render()'))
        cases = (('nhny-coord-sync-ingest.service', 'COORD_SYNC_STAGING', 'nhny-coord-sync'),
                 ('nhny-cc-verdict-publish.service', 'REVERSE_SYNC_STAGING', 'nhny-to-2604-sync'))
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            script = root / 'render.sh'
            script.write_text(render_line + '\nrender "$1" "$2"\n')
            env = dict(os.environ, WINDOWS_TEMP='/tmp/Temp %dir')
            for template, var, suffix in cases:
                with self.subTest(template=template):
                    out = root / (template + '.rendered')
                    subprocess.run(['bash', str(script), str(ROOT / 'adoption/templates/systemd' / template), str(out)],
                                   check=True, env=env, capture_output=True, text=True)
                    rendered = out.read_text()
                    self.assertIn(f'Environment="{var}=/tmp/Temp %%dir/{suffix}"', rendered)
                    self.assertIn('ExecStart=/usr/bin/python3 -I %h/code/native-agent-stack-live/tools/coord-sync/', rendered)
                    self.assertIn('Environment=PATH=%h/.local/bin:', rendered)
                    self.assertNotIn('@WINDOWS_TEMP@', rendered)


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

    def test_alert_logs_nonzero_hcom_exit(self):
        with tempfile.TemporaryDirectory() as t:
            home = Path(t)
            stub = home / '.local/bin/hcom'
            stub.parent.mkdir(parents=True)
            stub.write_text('#!/bin/sh\nexit 7\n')
            stub.chmod(0o755)
            saved = {k: os.environ.get(k) for k in ('PATH', 'HOME', 'REVERSE_SYNC_NO_ALERT')}
            try:
                m = load(home / 'src', home / 'staging', home / 'ledger.tsv')
                os.environ.update(PATH='/usr/bin:/bin', HOME=str(home))
                os.environ['REVERSE_SYNC_NO_ALERT'] = '0'
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    m.alert('probe text')
            finally:
                for k, v in saved.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
            self.assertIn('alert send failed', out.getvalue())
            self.assertIn('7', out.getvalue())

if __name__ == '__main__':
    unittest.main(verbosity=2)
