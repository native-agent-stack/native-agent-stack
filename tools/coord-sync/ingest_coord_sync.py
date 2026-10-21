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
refused marker: it is logged FAILED and stops the run, with a <batch>.failed flag (the SHA256SUMS sha256 and a normalised fault key: exception
type, errno, operation, source-or-destination side and batch-relative path - hashing and copying faults are stamped with their file at the call
site, so a pathless error still keys to it, and per-run temporary names map to their destination) so the same fault is alerted only once while
it lasts and the flag can be written, while a fault on a different file, or on the other side of the same file, still alerts; if the flag
itself cannot be written, the alert repeats on each run until it can. The flag must be removed before the ingested marker is written, so success is
never acknowledged while it stands, and the key it held is kept through the marker attempt so a persistent marker-write fault still alerts only
once; once the marker is written, the summary log is best-effort (even a broken stdout is swallowed) and cannot recreate the flag. Files already
copied stay. The next run retries the batch: it completes once a copy fault clears, but a staged file that still does not match SHA256SUMS is
then refused in verification, so that case is resolved like a refusal. A batch directory that is itself a symlink is skipped, as is a batch
found gone at the run's own checks (its SHA256SUMS missing after listing, its directory gone after a verification error or a FileNotFoundError,
or gone after copying), clearing any earlier failed flag best-effort; a batch whose removal is only part-done, so its directory still exists
at those checks, is judged on what remains and may refuse or fail a run instead.
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


def log_or_print(line):
    """Log a line, falling back to stdout (the journal) when the log file cannot be written. The fallback
    print is guarded too: a broken stdout must not escape and turn a written marker into a false failure."""
    try:
        log(line)
    except OSError:
        try:
            print(line)
        except OSError:
            pass


def alert(text):
    """Tell the CC and the fallback holder over hcom-x; a failed send is logged or printed, never fatal. COORD_SYNC_NO_ALERT=1 disables it (tests)."""
    if os.environ.get('COORD_SYNC_NO_ALERT') == '1':
        return
    env = dict(os.environ, HCOM_DIR=os.environ.get('HCOM_DIR', '/mnt/wsl/hcom-x'))
    try:
        r = subprocess.run([hcom_bin(), 'send', *ALERT_TO, '--intent', 'request', '--from', 'coord-sync', '--', text],
                           env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
        if r.returncode != 0:
            log_or_print(f'ALERT send failed rc={r.returncode}')
    except (OSError, subprocess.SubprocessError) as e:
        log_or_print(f'ALERT send failed ({type(e).__name__})')


def failed_flag(name):
    return STAGING / f'{name}.failed'


def dst_rel(dst):
    """The coordination-relative path of a mirror destination (the batch-relative path of its source)."""
    try:
        return str(Path(dst).relative_to(COORD))
    except ValueError:
        return Path(dst).name


def annotate_fault(e, rel, side):
    """Stamp the batch-relative file and side ('source' or 'destination') a fault belongs to at its call site,
    so a pathless descriptor error still keys to its file and a staged source never keys as its mirror copy."""
    try:
        e.coord_rel, e.coord_side = rel, side
    except Exception:
        pass


def error_rel(e, batch_dir, rel_hint):
    """The stable batch-relative path a fault belongs to: the destination place() was installing (a temp file in the
    destination directory maps to that destination), else the failing file relative to the batch, mirror or staging root."""
    annotated = getattr(e, 'coord_rel', None)
    if annotated:
        return str(annotated)
    if rel_hint:
        return rel_hint
    for attr in ('filename2', 'filename'):
        fn = getattr(e, attr, None)
        if not fn:
            continue
        p = Path(fn)
        if p.name.startswith('.ingest-'):
            try:
                return str(p.parent.relative_to(COORD) / '.ingest-<tmp>')
            except ValueError:
                return '.ingest-<tmp>'
        for base in (batch_dir, COORD, STAGING):
            if base is None:
                continue
            try:
                return str(p.relative_to(base))
            except ValueError:
                continue
        return p.name
    return '-'


def error_side(e, batch_dir):
    """Which side of a record a fault belongs to: the call site's stamp, else inferred from the failing path
    (in the batch a staged source, in the mirror its destination)."""
    annotated = getattr(e, 'coord_side', None)
    if annotated:
        return str(annotated)
    for attr in ('filename2', 'filename'):
        fn = getattr(e, attr, None)
        if not fn:
            continue
        p = Path(fn)
        if p.name.startswith('.ingest-'):
            return 'destination'
        for base, side in ((batch_dir, 'source'), (COORD, 'destination')):
            if base is None:
                continue
            try:
                p.relative_to(base)
                return side
            except ValueError:
                continue
        return '-'
    return '-'


def error_detail(e):
    """The stable part of an error's text: an OSError's strerror (its rendered form carries per-run file names),
    else the message with any random temp-file name normalised away."""
    s = e.strerror if isinstance(e, OSError) and e.strerror else str(e)
    return re.sub(r'\.ingest-[A-Za-z0-9_\-]+', '.ingest-<tmp>', s).strip()


def failure_key(e, batch_dir=None, op='-', rel_hint=None):
    """Dedup key for a part-way fault: exception type, errno, operation, source-or-destination side and
    batch-relative path, plus the stable detail, so the same fault dedupes across runs while a fault on a
    different file (or on the other side of the same file) still alerts."""
    return (f'{type(e).__name__}: errno={getattr(e, "errno", None)}: {op}: '
            f'{error_side(e, batch_dir)}:{error_rel(e, batch_dir, rel_hint)}: {error_detail(e)}').strip()


def failed_key_stored(name, sums_sha):
    """The normalised key a batch's failed flag records for this SHA256SUMS, or None."""
    try:
        parts = failed_flag(name).read_text().split(None, 2)
    except OSError:
        return None
    return parts[2].strip() if len(parts) == 3 and parts[0] == (sums_sha or '-') else None


def failed_seen(name, sums_sha, key):
    """True when this exact fault (same SHA256SUMS, same normalised key) was already reported."""
    return failed_key_stored(name, sums_sha) == key.strip()


def clear_failed(name):
    """Remove a batch's failed flag. A flag that is already gone is fine; any other failure propagates, so a
    successful ingest is never acknowledged while its failed flag still stands."""
    try:
        failed_flag(name).unlink()
    except FileNotFoundError:
        pass


def clear_failed_quietly(name):
    """Best-effort flag removal for a batch found vanished: nothing is owed for it, so a removal failure is silent."""
    try:
        clear_failed(name)
    except OSError:
        pass


def batch_dir_for(name):
    return STAGING / name if STAGING is not None else Path(name)


def report_failed(name, sums_sha, e, op='-', rel_hint=None, prior_key=None):
    err = f'{type(e).__name__}: {e}'
    key = failure_key(e, batch_dir_for(name), op, rel_hint)
    if failed_seen(name, sums_sha, key) or (prior_key is not None and prior_key.strip() == key.strip()):
        # Already alerted for this fault. The prior key is the one the flag held before clear_failed()
        # removed it ahead of the marker write, so a persistent marker-write fault still dedupes; put
        # the flag back (it was cleared) so the next run dedupes from disk as well.
        if not failed_flag(name).exists():
            try:
                failed_flag(name).write_text(f'{sums_sha or "-"} {utc()} {key}\n')
            except OSError:
                pass
        return 2  # reruns retry silently until the fault clears or changes
    try:
        alert(f'coord-sync FAILED batch {name}: {err}. No ingested marker was written and later batches wait. '
              f'Files already copied stay in the mirror. The next run retries this batch: it completes if the fault '
              f'has cleared, or refuses the batch if a staged file still does not match SHA256SUMS.')
    except OSError:
        pass  # alert() reports a failed send through log_or_print(); a failing log must not lose the exit code
    log_or_print(f'FAILED batch {name}: {err}; no ingested marker written; later batches wait; '
                 f'the next run retries this batch')
    try:
        failed_flag(name).write_text(f'{sums_sha or "-"} {utc()} {key}\n')
    except OSError:
        pass  # the alert already went out; without the flag the next run may alert again
    return 2


def report_cleanup_failed(name, sums_sha, e):
    """A matching ingested marker stands but its stale failed flag could not be removed: report that, once per
    distinct fault, without claiming the (already written) marker is missing."""
    err = f'{type(e).__name__}: {e}'
    key = failure_key(e, batch_dir_for(name), 'clear-failed')
    if failed_seen(name, sums_sha, key):
        return 2
    try:
        alert(f'coord-sync FAILED batch {name}: the batch is already ingested, but its stale {name}.failed flag '
              f'could not be removed ({err}). Later batches wait; remove the flag in the staging root once the '
              f'fault has cleared.')
    except OSError:
        pass
    log_or_print(f'FAILED batch {name}: already ingested but its stale failed flag could not be removed: {err}; '
                 f'later batches wait')
    try:
        failed_flag(name).write_text(f'{sums_sha or "-"} {utc()} {key}\n')
    except OSError:
        pass
    return 2


def marker_matches(path, sums_sha):
    try:
        return path.read_text().split()[:1] == [sums_sha]
    except FileNotFoundError:
        return False  # the marker vanished between listing and reading; treat it as absent


def plan(batch_dir):
    """Return (actions, error). actions: list of (rel, src, dst, kind, digest) with kind new|same."""
    if not batch_dir.is_dir():
        raise FileNotFoundError(f'batch vanished: {batch_dir.name}')  # ingest() skips it like an incomplete batch
    sums = batch_dir / 'SHA256SUMS'
    listed = {}
    try:
        sum_lines = sums.read_text(encoding='utf-8').splitlines()
    except Exception as e:
        annotate_fault(e, 'SHA256SUMS', 'source')
        raise
    for n, raw in enumerate(sum_lines, 1):
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
        try:
            src_matches = sha256(src) == digest
        except Exception as e:
            annotate_fault(e, rel, 'source')  # a pathless read error still keys to this staged file
            raise
        if not src_matches:
            return None, f'sha256 mismatch: {rel}'
        dst = COORD / rel
        if dst.is_symlink():
            return None, f'destination is a symlink: {rel}'
        if not dst.exists():
            actions.append((rel, src, dst, 'new', digest))
            continue
        try:
            dst_matches = sha256(dst) == digest
        except Exception as e:
            annotate_fault(e, rel, 'destination')  # the mirror copy of the same record, not its source
            raise
        if dst_matches:
            actions.append((rel, src, dst, 'same', digest))
        else:
            return None, f'same-path change to a synced record: {rel}'
    return actions, None


def place(src, dst, expected):
    tmp = None
    side = 'destination'
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dst.parent, prefix='.ingest-')
        h = hashlib.sha256()
        with os.fdopen(fd, 'wb') as out:
            side = 'source'
            with open(src, 'rb') as inp:
                while True:
                    side = 'source'
                    chunk = inp.read(1 << 20)
                    if not chunk:
                        break
                    h.update(chunk)
                    side = 'destination'
                    out.write(chunk)
        side = 'source'  # the bytes read from the staged file are what a mismatch indicts
        if h.hexdigest() != expected:
            raise ValueError(f'sha256 mismatch while copying: {dst_rel(dst)} changed after SHA256SUMS was written')
        side = 'destination'
        os.chmod(tmp, 0o444)
        side = 'source'
        st = src.stat()
        side = 'destination'
        os.utime(tmp, (st.st_atime, st.st_mtime))
        os.replace(tmp, dst)
    except BaseException as e:
        # Map the random temp path to its destination for the dedup key, keeping the side that faulted.
        if not getattr(e, 'coord_rel', None):
            annotate_fault(e, dst_rel(dst), getattr(e, 'coord_side', None) or side)
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
        raise


def ingest(batch_dir):
    name = batch_dir.name
    sums_sha = None
    op, rel_hint = 'hash-sums', None
    prior_key = None  # the failed flag's key before clear_failed(); kept through the marker attempt (GPT 1)
    try:
        try:
            sums_sha = sha256(batch_dir / 'SHA256SUMS')
        except FileNotFoundError:
            if not batch_dir.exists():
                clear_failed_quietly(name)
            return 0  # the batch vanished after main()'s is_file check; skipped like an incomplete batch
        except Exception as e:
            annotate_fault(e, 'SHA256SUMS', 'source')
            raise
        op = 'check-markers'
        marker = STAGING / f'{name}.ingested'
        if marker_matches(marker, sums_sha):
            try:
                clear_failed(name)
            except OSError as e:
                return report_cleanup_failed(name, sums_sha, e)
            return 0
        refused = STAGING / f'{name}.refused'  # reported once; blocks later batches until resolved and removed
        if marker_matches(refused, sums_sha):
            return 2
        op = 'plan'
        actions, err = plan(batch_dir)
        if err:
            if not batch_dir.exists():
                clear_failed_quietly(name)
                return 0  # the batch vanished during verification; skipped like an incomplete batch
            refused.write_text(f'{sums_sha} {utc()} {err}\n')
            try:
                clear_failed(name)  # the refusal supersedes an earlier part-way failure of this batch
            except OSError:
                pass  # the alert below names the failed flag for removal as well
            try:
                alert(f'coord-sync REFUSED batch {name} (SHA256SUMS {sums_sha[:16]}): {err}. Nothing was written in this run '
                      f'(files copied by an earlier run stay in the mirror) and later batches wait. Resolve, then remove '
                      f'{name}.refused in the staging root (and {name}.failed if it remains).')
            except OSError:
                pass  # alert() reports a failed send itself; the refusal and its exit code stand regardless
            log_or_print(f'REFUSED batch {name} (SHA256SUMS {sums_sha[:16]}): {err}; nothing written in this run; later batches wait')
            return 2
        counts = {'new': 0, 'same': 0}
        op = 'copy'
        for rel, src, dst, kind, digest in actions:
            counts[kind] += 1
            if kind == 'new':
                rel_hint = rel
                place(src, dst, digest)
        rel_hint = None
        if not batch_dir.exists():
            clear_failed_quietly(name)
            return 0  # the batch vanished during copying; files already copied stay, no marker is owed
        op = 'clear-failed'
        prior_key = failed_key_stored(name, sums_sha)  # keep it: clearing must not restart marker-fault alerts
        clear_failed(name)  # before the marker: success is not acknowledged while the failed flag stands
        op = 'write-marker'
        marker.write_text(f'{sums_sha} {utc()}\n')
        # Post-commit: the summary log is best-effort and must not recreate failed-batch state.
        log_or_print(f'INGESTED batch {name} (SHA256SUMS {sums_sha[:16]}): {len(actions)} files, '
                     f'{counts["new"]} new, {counts["same"]} identical')
        return 0
    except FileNotFoundError as e:
        if not batch_dir.exists():
            clear_failed_quietly(name)
            return 0  # the batch vanished mid-run; skipped like an incomplete batch, later batches proceed
        return report_failed(name, sums_sha, e, op, rel_hint, prior_key)
    except Exception as e:
        return report_failed(name, sums_sha, e, op, rel_hint, prior_key)


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
