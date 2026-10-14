"""Operator STOP paths are read-only; auto-cleanup owns a private trial marker."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys

VERSION = "private-stage-hook-v2"
MARKER = ".stage-hook-latch"
ISSUER_PYTHON = (3, 12)


def assert_issuer_python():
    if sys.implementation.name != "cpython" or sys.version_info[:2] != ISSUER_PYTHON:
        raise ValueError("issuer_python_3_12_required")


def pending(lane, host, instances):
    try:
        if Path(lane).parent.is_symlink():
            return True
        for path in (lane, host):
            try:
                os.lstat(path)
            except FileNotFoundError:
                continue
            return True
        root = Path(instances)
        try:
            info = os.lstat(root)
        except FileNotFoundError:
            return False
        if not stat.S_ISDIR(info.st_mode):
            return True
        for instance in root.iterdir():
            if not stat.S_ISDIR(os.lstat(instance).st_mode):
                return True
            try:
                os.lstat(instance / MARKER)
            except FileNotFoundError:
                continue
            return True
        return False
    except OSError:
        return True


def identity(info):
    return [info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns, info.st_size]


@contextmanager
def machine_directory(latch, owner):
    latch = Path(latch)
    if latch.name != MARKER or latch.parent.name != owner:
        raise ValueError("private_latch_path_mismatch")
    fd = os.open(latch.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError("private_latch_directory_required")
        yield fd
    finally:
        os.close(fd)


def directory_current(latch, fd):
    try:
        current = Path(latch).parent.stat(follow_symlinks=False)
    except OSError:
        return False
    opened = os.fstat(fd)
    return stat.S_ISDIR(current.st_mode) and (current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino)


def mark(latch, owner):
    body = (json.dumps({"version": VERSION, "trial": owner, "nonce": secrets.token_hex(16)},
                       sort_keys=True) + "\n").encode()
    with machine_directory(latch, owner) as directory:
        try:
            fd = os.open(MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        except FileExistsError:
            return {"version": VERSION, "trial": owner, "created_by_hook": False}
        with os.fdopen(fd, "wb") as stream:
            stream.write(body);stream.flush();os.fsync(stream.fileno())
            info = os.fstat(stream.fileno())
        if not directory_current(latch, directory):
            raise ValueError("private_latch_directory_changed")
        opened = os.fstat(directory)
        return {"version": VERSION, "trial": owner, "created_by_hook": True,
                "identity": identity(info), "directory_identity": [opened.st_dev, opened.st_ino],
                "sha256": hashlib.sha256(body).hexdigest()}


def clear(latch, proof, owner):
    """Clear only our private marker after durable exact-CONFIG flat proof.

    Operators write lane-b/STOP or host STOP; neither pathname is ever a
    cleanup target, including at the final unlink boundary.
    """
    if proof.get("version") != VERSION or proof.get("trial") != owner or proof.get("created_by_hook") is not True:
        return False
    try:
        with machine_directory(latch, owner) as directory:
            opened = os.fstat(directory)
            if proof.get("directory_identity") != [opened.st_dev, opened.st_ino] or not directory_current(latch, directory):
                return False
            fd = os.open(MARKER, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_size > 1024:
                    return False
                body = stream.read(1025)
                if identity(info) != proof.get("identity") or hashlib.sha256(body).hexdigest() != proof.get("sha256"):
                    return False
                current = os.stat(MARKER, dir_fd=directory, follow_symlinks=False)
                if identity(current) != identity(info) or not stat.S_ISREG(current.st_mode) or not directory_current(latch, directory):
                    return False
                # A descriptor-relative, private machine-only basename. No
                # operator-replaceable STOP pathname is unlinked here.
                os.unlink(MARKER, dir_fd=directory)
            return True
    except OSError:
        return False
