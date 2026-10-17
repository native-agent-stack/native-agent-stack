#!/usr/bin/env python3
"""NativeHorizonNY half of the reverse sync (NativeHorizonNY -> 2604) for the CC's sealed verdict files.

Contract: proposed by the CC (hcom #719 thread), confirmed by nami (#766); nami's 2604 half installs each file at
/var/tmp/cc-cc-work/<pr>-micro/<file> (0400) and writes <batch>.ingested. Two 2604 readers depend on it: the co-op's GPT
read-wave (CC verdicts as priors, cited by name and sha256) and trading-cc's gates and Monday tree manifest (suki #750, #764).

One run:
  1. recover, then cleanup: the published identity proved by each completed staged batch's SHA256SUMS is recovered first and
     any of it missing from the ledger is appended back as whole lines; only then is each staged batch whose <batch>.ingested
     holds the sha256 of that batch's SHA256SUMS deleted, so cleanup can never erase the only record of a cut ledger append;
  2. scan SRC/<pr>-micro/ for CC-*.md and MICRO-*.md that are SEALED (no write bit for anyone), regular files, not symlinks;
  3. a file already published (in the ledger, or recovered from a completed batch) with the same sha256 is done; with a
     different sha256 it is a same-path change to a published record: the run is REFUSED (nothing staged) and the CC and the
     fallback holder are alerted once per distinct refusal while the .publisher-refused flag can be written - the alert goes
     before that flag write, guarded, so a failing write cannot lose it, and the alert repeats each run until the flag can
     be written (corrections ship under a new name);
  4. new sealed files go into ONE batch STAGING/<UTC>/cc-cc-work/<pr>-micro/<file> (mtime kept), with SHA256SUMS written LAST
     by rename; the ledger records each file only after the batch is complete, writing a truncated tail's missing newline
     first so the append's first record is never glued onto the cut line. If staging fails part-way (for example ENOSPC
     while copying), a batch without its SHA256SUMS is removed, the failure is printed FAILED and alerted once per distinct
     normalised fault while the .publisher-failed flag can be written, repeating each run until it can (the flag in the
     staging root holds phase, exception type, errno, the file's position in the attempt and its batch-relative path - copy
     faults are stamped with their file at the call site, for errors with no filename - with the per-run STAGING/<UTC>/
     prefix stripped, removed by the next successful stage), and the next run retries; because a retry restarts the batch,
     the same fault striking at or before the previous attempt's failure point dedupes, while one past it alerts anew.
     If the ledger append fails after SHA256SUMS is in place, the complete batch stays and the failure is reported as a
     ledger-append failure; a ledger line without a whole digest is by itself only a truncated append - it is the completed
     batch behind it (step 1) that decides whether the path was already published, and a change to such a path is refused.
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
    """Tell the CC and the fallback holder over hcom-x; a failed send is printed, never fatal. REVERSE_SYNC_NO_ALERT=1 disables it."""
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


DIGEST = re.compile(r'^[0-9a-f]{64}$')
SUMLINE = re.compile(r'^([0-9a-f]{64}) [ *](.+)$')


def read_ledger():
    done = {}
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            parts = line.split('\t')
            if len(parts) >= 2 and DIGEST.match(parts[1]):
                done[parts[0]] = parts[1]
            # a line without a whole digest is a truncated append, not by itself a published record; a
            # completed staged batch may still prove that record (recovered_published() below)
    return done


def append_ledger(text):
    """Append whole lines to the ledger, first writing the newline a truncated tail is missing, so the
    append's first record is never glued onto the cut line and swallowed by the whole-digest check."""
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    prefix = ''
    if LEDGER.exists() and LEDGER.stat().st_size > 0:
        with open(LEDGER, 'rb') as f:
            f.seek(-1, os.SEEK_END)
            if f.read() != b'\n':
                prefix = '\n'
    with open(LEDGER, 'a') as f:
        f.write(prefix + text)


def recovered_published():
    """{rel: (digest, batch)} proved by completed staged batches (SHA256SUMS in place), earliest batch
    first. A batch is exposed for ingestion the moment its SHA256SUMS lands, before its ledger append,
    so this is the published identity a truncated ledger line cannot be allowed to erase."""
    recovered = {}
    if STAGING is None or not STAGING.exists():
        return recovered
    for b in sorted(p for p in STAGING.iterdir() if p.is_dir() and not p.is_symlink() and BATCH.match(p.name)):
        sums = b / 'SHA256SUMS'
        if not sums.is_file():
            continue
        for line in sums.read_text().splitlines():
            m = SUMLINE.match(line)
            if not m:
                continue
            digest, rel = m.group(1), m.group(2)
            parts = rel.split('/')
            if len(parts) == 3 and parts[0] == 'cc-cc-work' and MICRO_DIR.match(parts[1]) and NAME.match(parts[2]):
                recovered.setdefault(rel, (digest, b.name))
    return recovered


def error_rel(e):
    """The stable path a staging fault belongs to, relative to the batch: the failing file with the per-run
    STAGING/<UTC>/ prefix stripped (the destination for a copy, which names both paths), else relative to SRC."""
    annotated = getattr(e, 'coord_rel', None)
    if annotated:
        return str(annotated)  # stamped at the copy call site, for errors carrying no filename at all
    for attr in ('filename2', 'filename'):
        fn = getattr(e, attr, None)
        if not fn:
            continue
        p = Path(fn)
        try:
            rel = p.relative_to(STAGING)
        except (TypeError, ValueError):
            try:
                return str(p.relative_to(SRC))
            except (TypeError, ValueError):
                return p.name
        parts = rel.parts[1:] if rel.parts and BATCH.match(rel.parts[0]) else rel.parts
        return '/'.join(parts) if parts else '<batch>'
    return '-'


def error_detail(e):
    """The stable part of an error's text: an OSError's strerror (its rendered form carries the per-run batch
    name), else the message with any batch stamp normalised away."""
    s = e.strerror if isinstance(e, OSError) and e.strerror else str(e)
    return re.sub(r'(?<![0-9A-Za-z])\d{8}T\d{6}Z(?![0-9A-Za-z])', '<batch>', s).strip()


def failure_key(e, after_sums):
    """Dedup key for a staging or ledger fault: phase, exception type, errno, the file's position in the
    staging attempt and its batch-relative path, plus the stable detail, so the same fault dedupes across
    runs despite the fresh batch name each run."""
    phase = 'ledger-append' if after_sums else 'staging'
    index = getattr(e, 'coord_index', '-')
    return (f'{phase}: {type(e).__name__}: errno={getattr(e, "errno", None)}: '
            f'{index}:{error_rel(e)}: {error_detail(e)}').strip()


_KEY_RE = re.compile(r'^(staging|ledger-append): ([^:]+): errno=([^:]*): ([^:]*):([^:]*): (.*)$')


def failure_seen(stored, key):
    """True when the .publisher-failed flag already records this fault. Staging retries from scratch (the
    incomplete batch was removed), so the same standing fault striking at or before the previous attempt's
    failure point is the same fault; a fault past that point (the previous file now copies) is a new one."""
    stored, key = stored.strip(), key.strip()
    if stored == key:
        return True
    sm, km = _KEY_RE.match(stored), _KEY_RE.match(key)
    if not sm or not km or sm.group(1) != 'staging' or km.group(1) != 'staging':
        return False
    if (sm.group(2), sm.group(3), sm.group(6)) != (km.group(2), km.group(3), km.group(6)):
        return False
    try:
        return int(km.group(4)) <= int(sm.group(4))
    except ValueError:
        return False


def report_failure(e, after_sums):
    """Report a staging or ledger-append fault: alert once per distinct fault while the flag can be written
    (see failure_seen()), record the key in .publisher-failed after alerting, print FAILED and return exit 2."""
    if after_sums:
        err = f'ledger append failed after SHA256SUMS was staged: {type(e).__name__}: {e}'
        alert_text = (f'cc-reverse-sync FAILED: {err}. The staged batch is complete and will be ingested; '
                      f'the next run retries the ledger append, recovering the published identity from the '
                      f'staged batch until it succeeds.')
    else:
        err = f'staging failed: {type(e).__name__}: {e}'
        alert_text = f'cc-reverse-sync FAILED: {err}. The next run retries.'
    key = failure_key(e, after_sums)
    flag = STAGING / '.publisher-failed'
    try:
        seen = failure_seen(flag.read_text(), key)
    except OSError:
        seen = False
    if not seen:
        alert(alert_text)
        try:
            flag.write_text(key + '\n')
        except OSError:
            pass  # the alert already went out; without the flag the next run may alert again
    print(f'FAILED: {err}')
    return 2


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
        for index, (rel, src, _) in enumerate(new):
            dst = b / rel
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            except BaseException as e:
                try:  # copy2 can forward a pathless read/write error: name the file and its position
                    e.coord_rel, e.coord_index = rel, index
                except Exception:
                    pass
                raise
        tmp = b / 'SHA256SUMS.tmp'
        tmp.write_text(''.join(f'{digest}  {rel}\n' for rel, _, digest in new))
        os.replace(tmp, b / 'SHA256SUMS')
        complete = True  # SHA256SUMS is in place: the batch itself is whole from here on
        append_ledger(''.join(f'{rel}\t{digest}\t{name}\t{utc()}\n' for rel, _, digest in new))
    except BaseException as e:
        try:
            e.coord_after_sums = complete  # main() labels a post-SHA256SUMS fault as the ledger append it is
        except Exception:
            pass
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
        done = read_ledger()
        # Recover before cleanup() can delete an acknowledged batch and before scan() judges: a completed
        # batch's SHA256SUMS proves the digest a truncated ledger append lost. Repairing the ledger here
        # (appending the whole recovered lines) makes that identity survive the cleanup that follows, so
        # a same-name edit is refused on this and every later run, never staged as new.
        missing = [(rel, digest, batch) for rel, (digest, batch) in sorted(recovered_published().items())
                   if rel not in done]
        if missing:
            try:
                append_ledger(''.join(f'{rel}\t{digest}\t{batch}\t{utc()}\n' for rel, digest, batch in missing))
            except OSError as e:
                return report_failure(e, True)  # the batches stay staged; nothing is cleaned or scanned
            for rel, digest, _ in missing:
                done[rel] = digest
            try:  # the ledger-append fault this repair clears is no longer standing
                if (STAGING / '.publisher-failed').read_text().startswith('ledger-append:'):
                    (STAGING / '.publisher-failed').unlink()
            except OSError:
                pass
        removed = cleanup()
        new, err = scan(done)
    except OSError as e:
        print(f'root unreadable ({type(e).__name__})')
        return 3
    if err:
        flag = STAGING / '.publisher-refused'
        try:
            seen = flag.read_text().strip() == err
        except OSError:
            seen = False
        if not seen:
            alert(f'cc-reverse-sync REFUSED: {err}. Nothing was staged. A correction must ship under a new name.')
            try:
                flag.write_text(err + '\n')
            except OSError:
                pass  # the alert already went out; without the flag the next run may alert again
        print(f'REFUSED: {err}')
        return 2
    if not new:
        print(f'nothing new ({removed} ingested batches cleaned)')
        return 0
    try:
        name = stage(new)
    except OSError as e:
        return report_failure(e, getattr(e, 'coord_after_sums', False))
    try:
        (STAGING / '.publisher-failed').unlink()
    except OSError:
        pass
    print(f'STAGED batch {name}: {len(new)} files ({removed} ingested batches cleaned)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
