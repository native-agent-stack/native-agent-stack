"""Owned lane B lifecycle latch. The operator host STOP is read-only here."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat

VERSION = "lane-b-stage-latch-v1"


def pending(lane, host):
    return any(Path(p).exists() or Path(p).is_symlink() for p in (lane, host))


def identity(info):
    return [info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns, info.st_size]


def lane_path(lane, host):
    lane, host = Path(lane), Path(host)
    if lane != host.parent / "lane-b/STOP" or lane == host:
        raise ValueError("lane_latch_path_mismatch")
    if lane.parent.is_symlink() or host.parent.is_symlink():
        raise ValueError("lane_latch_directory_symlink")
    return lane


def mark(lane, host, owner):
    lane = lane_path(lane, host)
    lane.parent.mkdir(mode=0o700, exist_ok=True)
    directory = lane.parent.stat(follow_symlinks=False)
    if not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.geteuid():
        raise ValueError("unsafe_lane_latch_directory")
    body = (json.dumps({"version": VERSION, "trial": owner, "nonce": secrets.token_hex(16)},
                       sort_keys=True) + "\n").encode()
    try:
        fd = os.open(lane, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        return {"version": VERSION, "trial": owner, "created_by_hook": False}
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
        info = os.fstat(stream.fileno())
    return {"version": VERSION, "trial": owner, "created_by_hook": True,
            "identity": identity(info), "sha256": hashlib.sha256(body).hexdigest()}


def clear(lane, host, proof, owner):
    """Called only after the exact-CONFIG flat recovery is durably recorded."""
    lane = lane_path(lane, host)
    if (proof.get("version") != VERSION or proof.get("trial") != owner
            or proof.get("created_by_hook") is not True):
        return False
    try:
        fd = os.open(lane, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except (FileNotFoundError, OSError):
        return False
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_size > 1024:
            return False
        body = stream.read(1025)
        if identity(info) != proof.get("identity") or hashlib.sha256(body).hexdigest() != proof.get("sha256"):
            return False
        try:
            current = lane.stat(follow_symlinks=False)
        except FileNotFoundError:
            return False
        if identity(current) != identity(info) or not stat.S_ISREG(current.st_mode):
            return False
        lane.unlink()
    return True
