"""Owned lane B lifecycle latch. The operator host STOP is read-only here."""
import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import stat

VERSION = "lane-b-stage-latch-v1"


def pending(lane, host):
    try:
        if Path(lane).parent.is_symlink():
            return True
        for path in (lane, host):
            try:
                os.lstat(path)
            except FileNotFoundError:
                continue
            return True
        return False
    except OSError:
        return True


def identity(info):
    return [info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns, info.st_size]


def lane_path(lane, host):
    lane, host = Path(lane), Path(host)
    if lane != host.parent / "lane-b/STOP" or lane == host:
        raise ValueError("lane_latch_path_mismatch")
    if lane.parent.is_symlink() or host.parent.is_symlink():
        raise ValueError("lane_latch_directory_symlink")
    return lane


@contextmanager
def lane_directory(lane, host, *, create):
    lane = lane_path(lane, host)
    parent = os.open(Path(host).parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    directory = None
    try:
        if create:
            try:
                os.mkdir("lane-b", 0o700, dir_fd=parent)
            except FileExistsError:
                pass
        directory = os.open("lane-b", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        info = os.fstat(directory)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
            raise ValueError("unsafe_lane_latch_directory")
        yield parent, directory
    finally:
        if directory is not None:
            os.close(directory)
        os.close(parent)


def directory_current(parent, directory):
    try:
        current = os.stat("lane-b", dir_fd=parent, follow_symlinks=False)
    except OSError:
        return False
    opened = os.fstat(directory)
    return stat.S_ISDIR(current.st_mode) and (current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino)


def mark(lane, host, owner):
    body = (json.dumps({"version": VERSION, "trial": owner, "nonce": secrets.token_hex(16)},
                       sort_keys=True) + "\n").encode()
    with lane_directory(lane, host, create=True) as (parent, directory):
        try:
            fd = os.open("STOP", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        except FileExistsError:
            return {"version": VERSION, "trial": owner, "created_by_hook": False}
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
            info = os.fstat(stream.fileno())
        if not directory_current(parent, directory):
            raise ValueError("lane_latch_directory_changed")
        opened = os.fstat(directory)
        return {"version": VERSION, "trial": owner, "created_by_hook": True,
                "identity": identity(info), "directory_identity": [opened.st_dev, opened.st_ino],
                "sha256": hashlib.sha256(body).hexdigest()}


def clear(lane, host, proof, owner):
    """Called only after the exact-CONFIG flat recovery is durably recorded."""
    lane = lane_path(lane, host)
    if (proof.get("version") != VERSION or proof.get("trial") != owner
            or proof.get("created_by_hook") is not True):
        return False
    try:
        with lane_directory(lane, host, create=False) as (parent, directory):
            opened = os.fstat(directory)
            if proof.get("directory_identity") != [opened.st_dev, opened.st_ino] or not directory_current(parent, directory):
                return False
            fd = os.open("STOP", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_size > 1024:
                    return False
                body = stream.read(1025)
                if identity(info) != proof.get("identity") or hashlib.sha256(body).hexdigest() != proof.get("sha256"):
                    return False
                current = os.stat("STOP", dir_fd=directory, follow_symlinks=False)
                if identity(current) != identity(info) or not stat.S_ISREG(current.st_mode) or not directory_current(parent, directory):
                    return False
                os.unlink("STOP", dir_fd=directory)
            return True
    except OSError:
        return False
