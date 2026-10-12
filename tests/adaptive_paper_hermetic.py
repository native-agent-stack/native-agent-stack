"""Hermetic DEFAULT_STOP isolation for adaptive-paper engine tests.

blueprints/us-equities/adaptive-paper/safety.py binds one canonical
live-host kill switch, DEFAULT_STOP =
~/.local/state/native-agent-stack/alpaca-paper/STOP, and derives its default
lock root from it (DEFAULT_STOP.parent / "locks"). runner.py and
native_strategy.py each bind their own DEFAULT_STOP name via
`from safety import ... DEFAULT_STOP`, so any test that omits
stop_file/lock_root to safety.Ledger.reserve_intent/validate_pending,
runner.run_native, or native_strategy.AdaptiveStrategy reads the live file
and its sibling lock directory instead of a fixture -- and fails or errors
whenever that live kill switch happens to exist.

Call patch_default_stop() from a test module's setUpModule and
restore_default_stop() from its tearDownModule to repoint every
already-imported engine module's DEFAULT_STOP at a private path for the
duration of that module's tests. The path sits under a fresh
tempfile.TemporaryDirectory() that is never written to, so `.exists()` is
always False there -- equivalent to "no live STOP" -- and the directory is
removed again in restore_default_stop().

Tests that deliberately exercise a STOP file keep working: they either
create their own file/pass their own stop_file or lock_root explicitly to
the call under test, or patch DEFAULT_STOP themselves for the duration of a
single test (e.g. test_native_faults_min.py's per-test
unittest.mock.patch.object calls), which simply shadows this module-level
value and restores over top of it.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

# Names under which the engine modules this suite cares about are commonly
# already present in sys.modules by the time setUpModule runs: safety.py
# proper, its importlib-loaded copy in test_adaptive_paper_safety.py (loaded
# there as "adaptive_paper_safety"), runner.py, and native_strategy.py (only
# importable, and hence only present, when nautilus_trader is installed).
# recovery.py currently only imports SafetyError from safety and has no
# DEFAULT_STOP attribute of its own; it is listed anyway (and skipped via
# hasattr below) so it is covered automatically if that ever changes.
_DEFAULT_MODULE_NAMES = ("safety", "adaptive_paper_safety", "runner", "native_strategy", "recovery")


def _candidate_modules(extra):
    seen_ids, modules = set(), []
    for name in _DEFAULT_MODULE_NAMES:
        module = sys.modules.get(name)
        if module is not None and id(module) not in seen_ids:
            seen_ids.add(id(module))
            modules.append(module)
    for module in extra:
        if module is not None and id(module) not in seen_ids:
            seen_ids.add(id(module))
            modules.append(module)
    return modules


def patch_default_stop(*extra_modules):
    """Repoint DEFAULT_STOP on every already-imported engine module that has
    one (see _DEFAULT_MODULE_NAMES, plus any module object passed in
    ``extra_modules``) at a private, never-created tmp path, so no test in
    this process reads the live host kill switch or its default lock root
    unless it opts in explicitly. Call once from setUpModule.

    Returns an opaque token; pass it to restore_default_stop() to undo the
    patch and clean up the backing tmp directory.
    """
    tmpdir = tempfile.TemporaryDirectory(prefix="adaptive-paper-hermetic-stop-")
    stop_path = Path(tmpdir.name) / "STOP"
    originals = []
    for module in _candidate_modules(extra_modules):
        if hasattr(module, "DEFAULT_STOP"):
            originals.append((module, module.DEFAULT_STOP))
            module.DEFAULT_STOP = stop_path
    return tmpdir, originals


def restore_default_stop(token):
    """Undo patch_default_stop(), restoring each module's original
    DEFAULT_STOP and cleaning up the tmp directory. Call once from
    tearDownModule with the token patch_default_stop() returned."""
    tmpdir, originals = token
    for module, original in originals:
        module.DEFAULT_STOP = original
    tmpdir.cleanup()


def real_tmp_root(name) -> Path:
    """Path(name), with every symlink in it resolved (os.path.realpath).

    Shared by tests/test_adaptive_market_research.py and
    tests/test_adaptive_paper_credential_race.py for every fixture root a
    `follow_symlinks=False` caller (`market_research.credentials()`) will
    traverse. On Linux, `tempfile`'s default temp root is ordinarily
    already symlink-free and this is a no-op. On macOS it is not: the
    default TMPDIR lives under `/var/folders/...`, and `/var` (like `/tmp`)
    is itself a root-owned symlink to `/private/var` (`/private/tmp`) --
    `credential_guard.open_verified(..., follow_symlinks=False)` correctly
    refuses that symlinked ancestor component with the `symlink` reason
    code, which is the guard behaving exactly as documented (see its module
    docstring and docs/decisions/2026-09-22-broker-credential-handling.md:
    no-follow mode refuses every symlink component, including OS-provided
    ones), not a bug to work around in the guard -- only a fixture that
    must hand it an already-symlink-free path, the same way a real caller's
    documented credential store under `$HOME` (e.g.
    `~/.config/<tool>/paper.env`, `/Users/<name>/.config/...` on macOS)
    contains none.
    """
    return Path(os.path.realpath(name))


# Wednesday 2026-10-07 10:00 ET (RTH), later than every instant the fixtures embed (the mover
# scan day 2026-09-24, the legacy fee window 2026-09-29T20:25:19Z), as the real clock was.
FIXTURE_CLOCK_START = datetime(2026, 10, 7, 14, 0, tzinfo=timezone.utc).timestamp()


class FixtureClock:
    """The wall clock moved to ``start`` (epoch seconds) when constructed.

    runner.Controller._check_overnight_status classifies the controller's own
    clock (sessions.session_at). In the OVERNIGHT session, 20:00 ET on the
    prior civil day to 04:00 ET of an XNYS trade date, it refuses every order
    on an extended-hours port that lacks an Alpaca overnight asset status,
    and no SYN fixture supplies one. A trial on the real clock therefore ended
    completed_no_signals on Sunday to Thursday nights from 20:00 ET.

    The moved clock still advances in real time, and one instance keeps one
    offset, so the successive commands of one test share a timeline.
    ``patched()`` installs it as time.time and time.time_ns and as the
    ``clock=`` default of runner.Controller and mover_strategy.MoverStrategy,
    which bound the time.time builtin at import. The controller's clock cannot
    move alone: the ledger compares it with every quote's timestamp
    (RiskLimits.quote_max_age_seconds). NautilusTrader's own clock and
    time.monotonic stay real; the fixtures pin the native dispatch clock
    separately (native_pre_dispatch).
    """

    def __init__(self, start=FIXTURE_CLOCK_START):
        self._source_ns = time.time_ns
        self.offset_ns = round(start * 1e9) - self._source_ns()

    def time_ns(self):
        return self._source_ns() + self.offset_ns

    def time(self):
        return self.time_ns() / 1e9

    @contextmanager
    def patched(self):
        import mover_strategy
        import runner
        with patch.object(time, "time", self.time), patch.object(time, "time_ns", self.time_ns), \
             patch.dict(runner.Controller.__init__.__kwdefaults__, clock=self.time), \
             patch.dict(mover_strategy.MoverStrategy.__init__.__kwdefaults__, clock=self.time):
            yield self
