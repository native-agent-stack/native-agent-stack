#!/usr/bin/env python3
"""NativeHorizonNY half of the Phase 2(b) coordination sync (contract: CC tracker 2026-10-16T20:52:00Z; nami #520, #543).

For each complete batch (SHA256SUMS present) under the staging root, oldest first, that has no matching <batch>.ingested:
  1. verify it whole before writing anything: every listed file's sha256 matches, nothing on disk is unlisted, every path is
     relative with no '..', no symlinks, regular files only, and every path is in scope:
       cc-reads-20261005/<dir>/GPT-*.md       the co-op's GPT-family reads (the landers glob *pr<N>/GPT-VERDICT-<head8>*.md);
       trading-cc/reads/<name>.md              the records trading-cc-read statuses name (uet_land.sh:259-260);
       cc-cc-work/<dir>/CC-*.md or MICRO-*.md  dula's sealed CC records (scope c, nami #543);
       command-center/receipts/<name>.md       CC-lane receipts (dula's closing record via the co-op sync's extra-paths list, #2427);
  2. append-only for every path (dula's ruling, nami #543): an identical file is skipped; a different file at a path that
     already exists REFUSES the batch. Corrections ship under a new versioned name, never as an overwrite;
  3. copy to ~/.local/state/native-agent-stack/coordination/<path> at 0444 with the source mtime, via a temporary file and rename,
     hashing while copying so the bytes renamed into place are the bytes SHA256SUMS lists;
  4. write <batch>.ingested beside the batch: the sha256 of its SHA256SUMS and the UTC time (nami then deletes both).
A refusal writes <batch>.refused (reported and alerted once over hcom, to the CC and the fallback holder) and STOPS the run: later batches wait until
the refused one is resolved and its marker removed; a refusal writes nothing in the run that refuses, though files copied by an earlier run stay.
A failure part-way through a batch (for example ENOSPC while copying, or bytes that changed after SHA256SUMS was written) writes no ingested or
refused marker: it is logged FAILED and stops the run, with a <batch>.failed flag (the SHA256SUMS sha256 and the error) so the same fault is
alerted only once while it lasts; the flag is removed when the batch ingests. Files already copied stay. The next run retries the batch: it
completes once a copy fault clears, but a staged file that still does not match SHA256SUMS is then refused in verification, so that case is
resolved like a refusal. A batch directory that is itself a symlink, and a batch that vanishes before its SHA256SUMS is hashed, are skipped.
One summary line per batch on stdout and in coordination/.sync-ingest.log.
Exit 0 when every pending batch ingests (or none is pending), 2 when a batch is refused or fails part-way, 3 when COORD_SYNC_STAGING is unset,
empty, relative or contains '@', or when the staging root is unreadable.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STAGING = Path(os.environ['COORD_SYNC_STAGING']) if os.environ.get('COORD_SYNC_STAGING') else None
COORD = Path(os.environ.get('COORD_ROOT', str(Path.home() / '.local/state/native-agent-stack/coordination')))
BATCH = re.compile(r'^\d{8}T\d{6}Z$')
SUMLINE = re.compile(r'^([0-9a-f]{64}) [ *](.+)$')
SCOPE = re.compile(r'^(cc-reads-20261005/[^/]+/GPT-[^/]+\.md'
                   r'|trading-cc/reads/[^/]+\.md'
                   r'|cc-cc-work/[^/]+/(CC|MICRO)-[^/]+\.md'
                   r'|command-center/receipts/[^/]+\.md)$')
ALERT_TO = ('@nhny-gino', '@nami')  # the CC and the fallback holder: dula closed (#2427), so the co-op holds it


def utc():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def hcom_bin():
    """hcom by absolute path. A systemd --user unit's PATH has no ~/.local/bin (systemd 259's user manager, measured with
    systemd-run --user), and subprocess resolves a bare name on the child env's PATH, so the 2026-10-16T22:55:43Z refusal's
    alert failed with FileNotFoundError. Fall back to hcom's install path."""
    return shutil.which('hcom') or str(Path.home() / '.local/bin/hcom')


def log(line):
    COORD.mkdir(parents=True, exist_ok=True)
    with open(COORD / '.sync-ingest.log', 'a') as f:
        f.write(f'{utc()} {line}\n')
    print(line)


def alert(text):
    """Tell the CC and the fallback holder over hcom-x; a failed send is logged, never fatal. COORD_SYNC_NO_ALERT=1 disables it (tests)."""
    if os.environ.get('COORD_SYNC_NO_ALERT') == '1':
        return
    env = dict(os.environ, HCOM_DIR=os.environ.get('HCOM_DIR', '/mnt/wsl/hcom-x'))
    try:
        r = subprocess.run([hcom_bin(), 'send', *ALERT_TO, '--intent', 'request', '--from', 'coord-sync', '--', text],
                           env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
        if r.returncode != 0:
            log(f'ALERT send failed rc={r.returncode}')
    except (OSError, subprocess.SubprocessError) as e:
        log(f'ALERT send failed ({type(e).__name__})')


def failed_flag(name):
    return STAGING / f'{name}.failed'


def failed_seen(name, sums_sha, err):
    """True when this exact fault (same SHA256SUMS, same error) was already reported."""
    try:
        parts = failed_flag(name).read_text().split(None, 2)
    except OSError:
        return False
    return len(parts) == 3 and parts[0] == (sums_sha or '-') and parts[2].strip() == err


def clear_failed(name):
    try:
        failed_flag(name).unlink()
    except OSError:
        pass


def report_failed(name, sums_sha, e):
    err = f'{type(e).__name__}: {e}'
    if failed_seen(name, sums_sha, err):
        return 2  # already alerted for this fault; reruns retry silently until it clears or changes
    try:
        alert(f'coord-sync FAILED batch {name}: {err}. No ingested marker was written and later batches wait. '
              f'Files already copied stay in the mirror. The next run retries this batch: it completes if the fault '
              f'has cleared, or refuses the batch if a staged file still does not match SHA256SUMS.')
    except OSError:
        pass  # alert() reports a failed send through log(); a failing log must not lose the exit code
    line = (f'FAILED batch {name}: {err}; no ingested marker written; later batches wait; '
            f'the next run retries this batch')
    try:
        log(line)
    except OSError:
        print(line)  # the journal still gets the line when the log file cannot be written
    try:
        failed_flag(name).write_text(f'{sums_sha or "-"} {utc()} {err}\n')
    except OSError:
        pass  # the alert already went out; without the flag the next run may alert again
    return 2


def plan(batch_dir):
    """Return (actions, error). actions: list of (rel, src, dst, kind, digest) with kind new|same."""
    sums = batch_dir / 'SHA256SUMS'
    listed = {}
    for n, raw in enumerate(sums.read_text(encoding='utf-8').splitlines(), 1):
        if not raw.strip():
            continue
        m = SUMLINE.match(raw)
        if not m:
            return None, f'SHA256SUMS line {n} malformed'
        digest, rel = m.group(1), m.group(2)
        if rel.startswith('/') or '..' in Path(rel).parts or rel in listed:
            return None, f'SHA256SUMS line {n}: absolute, parent or duplicate path'
        listed[rel] = digest
    on_disk = set()
    for root, dirs, files in os.walk(batch_dir, followlinks=False):
        for name in dirs + files:
            p = Path(root) / name
            if p.is_symlink():
                return None, f'symlink in batch: {p.relative_to(batch_dir)}'
        for name in files:
            rel = str((Path(root) / name).relative_to(batch_dir))
            if rel != 'SHA256SUMS':
                on_disk.add(rel)
    if on_disk != set(listed):
        extra, missing = sorted(on_disk - set(listed)), sorted(set(listed) - on_disk)
        return None, f'listing mismatch: {len(extra)} unlisted, {len(missing)} missing'
    actions = []
    for rel, digest in sorted(listed.items()):
        src = batch_dir / rel
        if not src.is_file():
            return None, f'not a regular file: {rel}'
        if not SCOPE.match(rel):
            return None, f'out of scope: {rel}'
        if sha256(src) != digest:
            return None, f'sha256 mismatch: {rel}'
        dst = COORD / rel
        if dst.is_symlink():
            return None, f'destination is a symlink: {rel}'
        if not dst.exists():
            actions.append((rel, src, dst, 'new', digest))
        elif sha256(dst) == digest:
            actions.append((rel, src, dst, 'same', digest))
        else:
            return None, f'same-path change to a synced record: {rel}'
    return actions, None


def place(src, dst, expected):
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dst.parent, prefix='.ingest-')
    try:
        h = hashlib.sha256()
        with os.fdopen(fd, 'wb') as out, open(src, 'rb') as inp:
            for chunk in iter(lambda: inp.read(1 << 20), b''):
                h.update(chunk)
                out.write(chunk)
        if h.hexdigest() != expected:
            raise ValueError(f'sha256 mismatch while copying: {src.name} changed after SHA256SUMS was written')
        os.chmod(tmp, 0o444)
        st = src.stat()
        os.utime(tmp, (st.st_atime, st.st_mtime))
        os.replace(tmp, dst)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def ingest(batch_dir):
    name = batch_dir.name
    sums_sha = None
    try:
        try:
            sums_sha = sha256(batch_dir / 'SHA256SUMS')
        except FileNotFoundError:
            return 0  # the batch vanished after main()'s is_file check; skipped like an incomplete batch
        marker = STAGING / f'{name}.ingested'
        if marker.exists() and marker.read_text().split()[:1] == [sums_sha]:
            clear_failed(name)
            return 0
        refused = STAGING / f'{name}.refused'  # reported once; blocks later batches until resolved and removed
        if refused.exists() and refused.read_text().split()[:1] == [sums_sha]:
            return 2
        actions, err = plan(batch_dir)
        if err:
            refused.write_text(f'{sums_sha} {utc()} {err}\n')
            log(f'REFUSED batch {name} (SHA256SUMS {sums_sha[:16]}): {err}; nothing written in this run; later batches wait')
            alert(f'coord-sync REFUSED batch {name} (SHA256SUMS {sums_sha[:16]}): {err}. Nothing was written in this run '
                  f'(files copied by an earlier run stay in the mirror) and later batches wait. Resolve, then remove '
                  f'{name}.refused in the staging root.')
            return 2
        counts = {'new': 0, 'same': 0}
        for rel, src, dst, kind, digest in actions:
            counts[kind] += 1
            if kind == 'new':
                place(src, dst, digest)
        marker.write_text(f'{sums_sha} {utc()}\n')
        clear_failed(name)
        log(f'INGESTED batch {name} (SHA256SUMS {sums_sha[:16]}): {len(actions)} files, '
            f'{counts["new"]} new, {counts["same"]} identical')
        return 0
    except Exception as e:
        return report_failed(name, sums_sha, e)


def main():
    if STAGING is None:
        print('COORD_SYNC_STAGING is not set or empty')
        return 3
    if not STAGING.is_absolute() or '@' in str(STAGING):
        print('COORD_SYNC_STAGING must be an absolute path with no placeholder')
        return 3
    try:
        batches = sorted(p for p in STAGING.iterdir() if p.is_dir() and not p.is_symlink() and BATCH.match(p.name))
    except OSError as e:
        print(f'staging root unreadable ({type(e).__name__})')
        return 3
    for b in batches:
        if not (b / 'SHA256SUMS').is_file():
            continue  # incomplete: SHA256SUMS is written last
        if ingest(b) != 0:
            return 2  # a refusal or failure stops the run (dula's ruling, nami #543)
    return 0


if __name__ == '__main__':
    sys.exit(main())
