"""Cooperate with the managed runtime installer through the native flock API."""
from contextlib import contextmanager
from functools import wraps
import os
from pathlib import Path
import stat
import sys


class RuntimeLockError(RuntimeError):
    """A fixed refusal reason; never includes a private path or provider text."""


@contextmanager
def runtime_read_lock():
    """Hold a shared lock while this process uses the canonical managed venv."""
    project = Path.home() / "projects/us-equities-runtime"
    if Path(sys.prefix).resolve() != (project / ".venv").resolve():
        yield
        return
    import fcntl
    descriptor = None
    try:
        if project.parent.is_symlink() or project.is_symlink():
            raise RuntimeLockError("canonical_runtime_lock_unavailable")
        lock = project.parent / ".us-equities-runtime.lock"
        descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        descriptor_stat = os.fstat(descriptor)
        if not stat.S_ISREG(descriptor_stat.st_mode) or descriptor_stat.st_uid != os.getuid():
            raise RuntimeLockError("canonical_runtime_lock_unavailable")
        fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except (OSError, RuntimeLockError):
        if descriptor is not None:
            os.close(descriptor)
        raise RuntimeLockError("canonical_runtime_lock_unavailable") from None
    try:
        yield
    finally:
        os.close(descriptor)


def runtime_read_locked(function):
    """Protect programmatic paper/recovery entry calls for their full lifetime."""
    @wraps(function)
    def call(*args, **kwargs):
        with runtime_read_lock():
            return function(*args, **kwargs)
    return call
