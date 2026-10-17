#!/usr/bin/env python3
"""NativeHorizonNY half of the reverse sync (NativeHorizonNY -> 2604) for the CC's sealed verdict files.

Contract: proposed by the CC (hcom #719 thread), confirmed by nami (#766); nami's 2604 half installs each file at
/var/tmp/cc-cc-work/<pr>-micro/<file> (0400) and writes <batch>.ingested. Two 2604 readers depend on it: the co-op's GPT
read-wave (CC verdicts as priors, cited by name and sha256) and trading-cc's gates and Monday tree manifest (suki #750, #764).

One run:
  1. cleanup: delete each staged batch whose <batch>.ingested holds the sha256 of that batch's SHA256SUMS;
  2. scan SRC/<pr>-micro/ for CC-*.md and MICRO-*.md that are SEALED (no write bit for anyone), regular files, not symlinks;
  3. a file already in the ledger with the same sha256 is done; with a different sha256 it is a same-path change to a published
     record: the run is REFUSED (nothing staged) and the CC and the fallback holder are alerted once (corrections ship under a new name);
  4. new sealed files go into ONE batch STAGING/<UTC>/cc-cc-work/<pr>-micro/<file> (mtime kept), with SHA256SUMS written LAST
     by rename; the ledger records each file only after the batch is complete. If staging fails part-way (for example ENOSPC
     while copying), a batch without its SHA256SUMS is removed, the failure is printed FAILED and alerted once per distinct
     error (a .publisher-failed flag in the staging root, removed by the next successful stage), and the next run retries.
Exit 0 (nothing to do, or a batch staged), 2 (refused, or staging failed), 3 (REVERSE_SYNC_STAGING unset, empty, relative or contains '@', or a root unreadable).
"""
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SRC = Path(os.environ.get('CC_VERDICT_SRC', '/var/tmp/cc-cc-work'))
STAGING = Path(os.environ['REVERSE_SYNC_STAGING']) if os.environ.get('REVERSE_SYNC_STAGING') else None
LEDGER = Path(os.environ.get('REVERSE_SYNC_LEDGER', '/var/tmp/cc-cc-work/.reverse-sync-published.tsv'))
NAME = re.compile(r'^(CC|MICRO)-[^/]+\.md$')
MICRO_DIR = re.compile(r'^[^/]+-micro$')
BATCH = re.compile(r'^\d{8}T\d{6}Z$')
ALERT_TO = ('@nhny-gino', '@nami')  # the CC and the fallback holder: dula closed (#2427), so the co-op holds it


def utc(fmt='%Y-%m-%dT%H:%M:%SZ'):
    return datetime.now(timezone.utc).strftime(fmt)


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


def alert(text):
    """Tell the CC and the fallback holder over hcom-x once; a failed send is printed, never fatal. REVERSE_SYNC_NO_ALERT=1 disables it."""
    if os.environ.get('REVERSE_SYNC_NO_ALERT') == '1':
        return
    env = dict(os.environ, HCOM_DIR=os.environ.get('HCOM_DIR', '/mnt/wsl/hcom-x'))
    try:
        r = subprocess.run([hcom_bin(), 'send', *ALERT_TO, '--intent', 'request', '--from', 'cc-reverse-sync', '--', text],
                           env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
        if r.returncode != 0:
            print(f'alert send failed rc={r.returncode}')
    except (OSError, subprocess.SubprocessError) as e:
        print(f'alert send failed ({type(e).__name__})')


def read_ledger():
    done = {}
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            parts = line.split('\t')
            if len(parts) >= 2:
                done[parts[0]] = parts[1]
    return done


def cleanup():
    removed = 0
    for b in sorted(p for p in STAGING.iterdir() if p.is_dir() and BATCH.match(p.name)):
        marker = STAGING / f'{b.name}.ingested'
        sums = b / 'SHA256SUMS'
        if marker.exists() and sums.exists() and marker.read_text().split()[:1] == [sha256(sums)]:
            shutil.rmtree(b)
            marker.unlink()
            removed += 1
    return removed


def scan(done):
    """Return (new, error): new = [(rel, path, sha)] for sealed CC/MICRO files not yet published."""
    new = []
    for d in sorted(p for p in SRC.iterdir() if p.is_dir() and not p.is_symlink() and MICRO_DIR.match(p.name)):
        for f in sorted(d.iterdir()):
            if not NAME.match(f.name) or f.is_symlink() or not f.is_file():
                continue
            if os.stat(f).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
                continue  # not sealed yet
            rel = f'cc-cc-work/{d.name}/{f.name}'
            digest = sha256(f)
            if rel in done:
                if done[rel] != digest:
                    return None, f'same-path change to a published record: {rel} ({done[rel][:16]} -> {digest[:16]})'
                continue
            new.append((rel, f, digest))
    return new, None


def stage(new):
    name = utc('%Y%m%dT%H%M%SZ')
    b = STAGING / name
    b.mkdir(parents=True)
    complete = False
    try:
        for rel, src, _ in new:
            dst = b / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        tmp = b / 'SHA256SUMS.tmp'
        tmp.write_text(''.join(f'{digest}  {rel}\n' for rel, _, digest in new))
        os.replace(tmp, b / 'SHA256SUMS')
        complete = True  # SHA256SUMS is in place: the batch itself is whole from here on
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with open(LEDGER, 'a') as f:
            for rel, _, digest in new:
                f.write(f'{rel}\t{digest}\t{name}\t{utc()}\n')
    except BaseException:
        if not complete:
            shutil.rmtree(b, ignore_errors=True)  # no SHA256SUMS: cleanup() could never retire this batch
        raise
    return name


def main():
    if STAGING is None:
        print('REVERSE_SYNC_STAGING is not set or empty')
        return 3
    if not STAGING.is_absolute() or '@' in str(STAGING):
        print('REVERSE_SYNC_STAGING must be an absolute path with no placeholder')
        return 3
    try:
        STAGING.mkdir(exist_ok=True)
        removed = cleanup()
        new, err = scan(read_ledger())
    except OSError as e:
        print(f'root unreadable ({type(e).__name__})')
        return 3
    if err:
        flag = STAGING / '.publisher-refused'
        if not flag.exists() or flag.read_text().strip() != err:
            flag.write_text(err + '\n')
            alert(f'cc-reverse-sync REFUSED: {err}. Nothing was staged. A correction must ship under a new name.')
        print(f'REFUSED: {err}')
        return 2
    if not new:
        print(f'nothing new ({removed} ingested batches cleaned)')
        return 0
    try:
        name = stage(new)
    except OSError as e:
        err = f'staging failed: {type(e).__name__}: {e}'
        flag = STAGING / '.publisher-failed'
        try:
            seen = flag.read_text().strip() == err
        except OSError:
            seen = False
        if not seen:
            alert(f'cc-reverse-sync FAILED: {err}. The next run retries.')
            try:
                flag.write_text(err + '\n')
            except OSError:
                pass  # the alert already went out; without the flag the next run may alert again
        print(f'FAILED: {err}')
        return 2
    try:
        (STAGING / '.publisher-failed').unlink()
    except OSError:
        pass
    print(f'STAGED batch {name}: {len(new)} files ({removed} ingested batches cleaned)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
