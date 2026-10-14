#!/usr/bin/env python3
"""Run the native Muse lane argv inside a named-bind bubblewrap filesystem.

Reference: co-op rankedfeeds_fence.sh (2026-10-14); upstream flag semantics:
https://github.com/containers/bubblewrap/blob/v0.11.1/bwrap.xml
See docs/decisions/2026-10-14-muse-file-fence.md for the threat boundary.
No credential contents are opened by this launcher. The sign-in file is only
mounted read-only. Network remains shared; this is a file-access fence.
"""
import argparse
import collections
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


MODEL = "muse-wonder-full-1.0"
VERSION = "1.4.7-R6101.1"
DEFAULT_LANE = Path.home() / ".local/state/native-agent-stack/coordination/command-center/cc-tools/muse_lane.sh"
SYSTEM_FILES = ("/etc/resolv.conf", "/etc/hosts", "/etc/nsswitch.conf",
                "/etc/passwd", "/etc/group", "/etc/localtime")
# Trusting a workspace must not reintroduce project hooks, MCP, or plugins.
PROJECT_MASKS = (".muse", ".mcp.json")


def checked_path(value, *, directory=False):
    path = Path(value).absolute()
    if any(ord(c) < 32 or ord(c) == 127 for c in str(path)):
        raise ValueError("control characters in paths are unsupported")
    if path != path.resolve():
        raise ValueError("symlink or noncanonical path refused")
    if not (path.is_dir() if directory else path.is_file()):
        raise ValueError("required directory/file is absent")
    return path


def sanitized_settings(source):
    """Copy only inert preferences, discarding executable/remote extensions.

    Both mcpServers and legacy mcp_servers, hooks, managed_* and plugins are
    deliberately absent. Unknown future extension keys do not survive.
    """
    doc = json.loads(source.read_text()) if source else {"schema_version": 1}
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        raise ValueError("unsupported Muse settings schema")
    result = {"schema_version": 1, "contributor_mode_enabled": False}
    key = "contributor_mode_disclosure_acknowledged"
    if key in doc:
        if not isinstance(doc[key], bool):
            raise ValueError("invalid disclosure preference")
        result[key] = doc[key]
    return result


def clean_env(home, logdir):
    # No inherited XDG paths, MUSE_AUTH_PATH, transport tracing, API keys,
    # loader variables, proxies, fail-open controls, or user PATH entries.
    return {"HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
            "TERM": "dumb", "NO_COLOR": "1", "MUSE_LOGIN": "0",
            "MUSE_NO_AUTO_UPDATE": "1", "TMPDIR": str(logdir / "tmp"),
            "XDG_DATA_HOME": str(logdir / "data"),
            "XDG_STATE_HOME": str(logdir / "state"),
            "XDG_CACHE_HOME": str(logdir / "cache")}


def native_argv(lane, runtime, worktree, brief, logdir, role, steps):
    """Use the unchanged CC builder; never eval its shell-escaped dry-run."""
    env = clean_env(Path.home(), logdir)
    env.update(MUSE_BIN=str(runtime), MUSE_LANE_MODEL=MODEL,
               MUSE_LANE_MAX_MODEL_STEPS=str(steps))
    plan = subprocess.run(["/bin/bash", str(lane), "--dry-run", "--role", role,
                           str(worktree), str(brief), str(logdir)], env=env,
                          capture_output=True, text=True, check=True)
    lines = [line[10:] for line in plan.stdout.splitlines() if line.startswith("argv     :")]
    if len(lines) != 1 or "$'" in lines[0]:
        raise ValueError("unsupported native argv rendering")
    argv = shlex.split(lines[0])
    expected = [str(runtime), "exec", "--json", "--prompt-file", str(brief),
                "--model", MODEL, "--reasoning-effort", "max", "--trust-workspace",
                "--workspace", str(worktree)]
    roles = {"reader": ["--approval-mode", "never", "--disable-write", "--disable-shell"],
             "reviewer": ["--permission-profile", ":read-only"],
             "builder": ["--approval-mode", "never"]}
    expected += roles[role] + ["--contributor-mode", "off", "--disable-web-tools",
                               "--max-model-steps", str(steps)]
    if argv != expected:
        raise ValueError("native argv changed; review the pinned contract before running")
    return argv


def disjoint(a, b):
    return a != b and a not in b.parents and b not in a.parents


class Fence:
    def __init__(self, worktree, brief, logdir, runtime, auth, settings=None, inputs=()):
        self.home = Path.home().resolve()
        self.worktree = checked_path(worktree, directory=True)
        self.brief = checked_path(brief)
        self.runtime = checked_path(runtime)
        # Metadata only: do not read/hash/copy auth, including in receipts.
        self.auth = checked_path(auth)
        self.settings = checked_path(settings) if settings else None
        self.inputs = [checked_path(p) for p in inputs]
        self.logdir = Path(logdir).absolute()
        if self.logdir != self.logdir.resolve() or any(ord(c) < 32 for c in str(self.logdir)):
            raise ValueError("noncanonical log path")
        # Writable host trees must be dedicated /var/tmp children, never home,
        # the co-op, /etc, or an ancestor of read-only runtime/sign-in inputs.
        for p in (self.worktree, self.logdir):
            if Path('/var/tmp') not in p.parents or p == Path('/var/tmp'):
                raise ValueError("worktree and logs must be dedicated /var/tmp directories")
        if not disjoint(self.worktree, self.logdir):
            raise ValueError("worktree and log directory must be disjoint")
        for p in (self.runtime, self.auth, *self.inputs):
            if not all(disjoint(p, rw) for rw in (self.worktree, self.logdir)):
                raise ValueError("read-only dependency overlaps writable tree")
        for p in (self.brief, *self.inputs):
            if not disjoint(p, self.logdir):
                raise ValueError("brief/inputs must be outside the log directory")
            if p == self.auth or p == self.settings:
                raise ValueError("credential/config cannot be a brief input")
            protected = ('.ssh', '.codex', '.claude', '.config', '.hcom', '.aws',
                         '.azure', '.gnupg', '.kube', '.local/state',
                         '.netrc', '.npmrc', '.git-credentials')
            if p == self.home or any(p == self.home / n or (self.home / n) in p.parents
                                     for n in protected):
                raise ValueError("protected home input refused")
            if any(x in p.parts for x in PROJECT_MASKS):
                raise ValueError("input would reopen project tool discovery")

    @contextlib.contextmanager
    def prepared(self):
        # Host-only staging is outside every visible bind. No auth copy.
        with tempfile.TemporaryDirectory(prefix="muse-fence-control-", dir="/var/tmp") as tmp:
            stage = Path(tmp)
            home = stage / 'home'
            (home / '.config/muse').mkdir(parents=True)
            config = home / '.config/muse/settings.json'
            config.write_text(json.dumps(sanitized_settings(self.settings)) + '\n')
            config.chmod(0o400)
            (home / '.config/muse/auth.json').touch(mode=0o400)
            for path in (self.runtime, self.brief, *self.inputs):
                if self.home in path.parents:
                    target = home / path.relative_to(self.home)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.touch(mode=0o400)
            empty = stage / 'empty'
            empty.mkdir()
            blank = stage / 'blank'
            blank.write_text('{}\n')
            yield self.command(stage, home, empty, blank)

    def command(self, stage, home, empty, blank):
        # Empty root, rather than exposing host / and subtracting known secrets.
        args = ["bwrap", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
                "--die-with-parent", "--new-session", "--cap-drop", "ALL",
                "--clearenv", "--ro-bind", "/usr", "/usr"]
        for name in ('bin', 'sbin', 'lib', 'lib64'):
            target = Path('/') / name
            if target.exists():
                if target.is_symlink():
                    args += ['--symlink', os.readlink(target), str(target)]
                else:
                    args += ['--ro-bind', str(target), str(target)]
        for name in SYSTEM_FILES:
            if Path(name).exists():
                args += ['--ro-bind', name, name]
        args += ['--ro-bind', '/etc/ssl/certs', '/etc/ssl/certs',
                 '--proc', '/proc', '--dev', '/dev',
                 '--ro-bind', str(home), str(self.home),
                 '--ro-bind', str(self.runtime), str(self.runtime),
                 '--ro-bind', str(self.auth), str(self.home / '.config/muse/auth.json'),
                 '--bind', str(self.worktree), str(self.worktree),
                 '--bind', str(self.logdir), str(self.logdir)]
        for path in dict.fromkeys([self.brief, *self.inputs]):
            args += ['--ro-bind', str(path), str(path)]
        for name in PROJECT_MASKS:
            path = self.worktree / name
            # Mountpoints cannot follow a workspace symlink outside its tree.
            if path.is_symlink():
                raise ValueError("symlink project configuration refused")
            args += ['--ro-bind', str(empty if name == '.muse' else blank), str(path)]
        # tmp/runtime/state are aliases INTO the sole writable log tree.
        args += ['--symlink', str(self.logdir / 'tmp'), '/tmp']
        for key, value in clean_env(self.home, self.logdir).items():
            args += ['--setenv', key, value]
        # bwrap's initial tmpfs root is writable unless explicitly sealed.
        # Per bwrap.xml, this leaves nested work/log bind mounts writable.
        return args + ['--remount-ro', '/', '--chdir', str(self.worktree), '--']


def event_receipt(path, rc):
    counts = collections.Counter()
    models = set()
    terminals = collections.Counter()
    invalid = 0
    with path.open() as fh:
        for line in fh:
            try:
                event = json.loads(line)
            except ValueError:
                invalid += 1
                continue
            kind = event.get('payload_type', '<unknown>')
            counts[kind] += 1
            payload = event.get('payload') or {}
            if kind == 'run.model.configured':
                models.add(payload.get('model_id', '<unknown>'))
            if kind.startswith('run.terminal.'):
                terminals[kind] += 1
    return {'exit_code': rc, 'event_count': sum(counts.values()),
            'event_counts': dict(counts), 'invalid_lines': invalid,
            'models': sorted(models), 'terminal_counts': dict(terminals)}


def probe(fence, command, argv):
    """Model-free positive control, named OS masks and native echo startup.

    The caller must run this successfully before the first live invocation.
    Neither the payload nor receipt reads auth contents.
    """
    with tempfile.TemporaryDirectory(prefix='muse-outside-canary-', dir='/var/tmp') as tmp:
        canary = Path(tmp) / 'planted-public-file'
        canary.write_text('public fence positive control\n')
        read = 'from pathlib import Path; Path(' + repr(str(canary)) + ').read_bytes()'
        before = subprocess.run(['/usr/bin/python3', '-I', '-c', read],
                                capture_output=True, timeout=20)
        after = subprocess.run(command + ['/usr/bin/python3', '-I', '-c', read],
                               env={}, capture_output=True, timeout=20)
        facts = {'unfenced-canary-readable': before.returncode == 0,
                 'fenced-canary-denied': after.returncode != 0 and b'FileNotFoundError' in after.stderr}
    masks = {name: str(fence.home / name) for name in (
        '.ssh', '.codex', '.claude', '.hcom', '.local/state',
        '.local/state/native-agent-stack/coordination/ns2604-coop',
        '.local/state/native-agent-stack/coordination/command-center')}
    masks.update({'host-runtime': '/run/user', 'host-mounts': '/mnt'})
    script = f'''
import json, os
from pathlib import Path
facts = {{name + '-masked': not Path(p).exists() for name, p in {masks!r}.items()}}
for name in ['code', 'projects']:
    root = Path({str(fence.home)!r}) / name
    expected = {{Path(p) for p in {[str(p) for p in (fence.brief, *fence.inputs)]!r} if root in Path(p).parents}}
    found = {{p for p in root.rglob('*') if not p.is_dir()}} if root.exists() else set()
    facts[name + '-other-files-masked'] = found == expected
for name, p in {{'worktree': {str(fence.worktree)!r}, 'logdir': {str(fence.logdir)!r}}}.items():
    marker = Path(p) / '.muse-fence-probe-marker'
    marker.write_text('public'); facts[name + '-rw'] = marker.read_text() == 'public'; marker.unlink()
for name, p in {{'brief': {str(fence.brief)!r}, 'runtime': {str(fence.runtime)!r},
                 'settings': {str(fence.home/'.config/muse/settings.json')!r},
                 'sign-in': {str(fence.home/'.config/muse/auth.json')!r}}}.items():
    facts[name + '-ro'] = Path(p).is_file() and not os.access(p, os.W_OK)
facts['project-hooks-masked'] = not list(Path({str(fence.worktree/'.muse')!r}).iterdir())
facts['project-config-ro'] = not os.access({str(fence.worktree/'.muse')!r}, os.W_OK)
cfg = json.loads(Path({str(fence.home/'.config/muse/settings.json')!r}).read_text())
facts['mcp-hooks-plugins-removed'] = set(cfg) <= {{'schema_version', 'contributor_mode_enabled', 'contributor_mode_disclosure_acknowledged'}}
for p in ['/', '/etc', {str(fence.home)!r}]:
    try:
        (Path(p)/'.muse-fence-probe-marker').write_text('public'); facts[p + '-readonly'] = False
    except OSError:
        facts[p + '-readonly'] = True
print(json.dumps(facts))
'''
    check = subprocess.run(command + ['/usr/bin/python3', '-I', '-c', script],
                           env={}, capture_output=True, text=True, timeout=30, check=True)
    facts.update(json.loads(check.stdout))
    if not all(facts.values()):
        raise ValueError('model-free filesystem probe failed')
    # Echo provider is the installed upstream's offline execution path. It
    # exercises startup/config/hooks/MCP discovery with no Meta model request.
    echo_path = fence.logdir / 'probe-echo.jsonl'
    echo_argv = list(argv)
    # The upstream echo provider refuses a Meta model selection. This change
    # applies to the offline startup probe only; live argv stays byte-for-byte.
    for flag in ('--model', '--reasoning-effort'):
        index = echo_argv.index(flag)
        del echo_argv[index:index + 2]
    with echo_path.open('x') as out, (fence.logdir / 'probe-echo.stderr.log').open('x') as err:
        echo = subprocess.run(command + echo_argv + ['--provider', 'echo', '--disable-reminders'],
                              env={}, stdin=subprocess.DEVNULL, stdout=out, stderr=err, timeout=45)
    echo_receipt = event_receipt(echo_path, echo.returncode)
    facts['native-echo-exit-zero'] = echo.returncode == 0
    facts['native-echo-terminal'] = echo_receipt['terminal_counts'].get('run.terminal.completed', 0) == 1
    for name in ('mcp-fired', 'user-hook-fired', 'project-hook-fired', 'managed-hook-fired'):
        facts[name + '-absent'] = not (fence.logdir / name).exists()
    result = {'schema': 'muse-file-fence-probe/1', 'checks': facts,
              'pass': all(facts.values()), 'echo': echo_receipt}
    (fence.logdir / 'fence-probe.json').write_text(json.dumps(result, indent=2) + '\n')
    if not result['pass']:
        raise ValueError('native model-free probe failed')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lane', type=Path, default=DEFAULT_LANE)
    parser.add_argument('--runtime', type=Path, default=Path.home() / f'.local/bin/muse-bin-{VERSION}')
    parser.add_argument('--auth', type=Path, default=Path.home() / '.config/muse/auth.json')
    parser.add_argument('--settings', type=Path, default=Path.home() / '.config/muse/settings.json')
    parser.add_argument('--input', action='append', default=[], type=Path)
    parser.add_argument('--role', choices=['reader', 'reviewer', 'builder'], default='reader')
    parser.add_argument('--max-model-steps', type=int, default=2)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--probe-only', action='store_true', help='OS and native echo only; no model call')
    parser.add_argument('worktree', type=Path)
    parser.add_argument('brief', type=Path)
    parser.add_argument('logdir', type=Path)
    options = parser.parse_args()
    if options.max_model_steps < 1 or options.timeout < 1:
        parser.error('positive bounds required')
    fence = Fence(options.worktree, options.brief, options.logdir, options.runtime,
                  options.auth, options.settings, options.input)
    lane = checked_path(options.lane)
    argv = native_argv(lane, fence.runtime, fence.worktree, fence.brief,
                       fence.logdir, options.role, options.max_model_steps)
    fence.logdir.mkdir(mode=0o700)  # exclusive fresh log dir; never overwrite a run
    for name in ('tmp', 'data', 'state', 'cache'):
        (fence.logdir / name).mkdir(mode=0o700)
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with fence.prepared() as command:
        version = subprocess.run(command + [str(fence.runtime), '--version'],
                                 env={}, capture_output=True, text=True, timeout=20, check=True)
        if f'({VERSION})' not in version.stdout:
            raise ValueError('runtime pin mismatch')
        probe(fence, command, argv)
        if options.probe_only:
            print('muse-file-fence: model-free probe PASS')
            return 0
        with (fence.logdir / 'muse-exec.jsonl').open('x') as out, \
                (fence.logdir / 'muse-exec.stderr.log').open('x') as err:
            # timeout's process group receives TERM then KILL; bwrap dies with
            # its parent and its PID namespace cannot leave child processes.
            result = subprocess.run(['/usr/bin/timeout', '-k', '10', str(options.timeout)] +
                                    command + argv, env={}, stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=err)
    receipt = event_receipt(fence.logdir / 'muse-exec.jsonl', result.returncode)
    receipt.update(schema='muse-file-fence/1', role=options.role, requested_model=MODEL,
                   runtime_version=version.stdout.strip(), started_utc=start,
                   finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   network='shared host network; no egress allowlist',
                   argv=argv, lane_sha256=hashlib.sha256(lane.read_bytes()).hexdigest())
    (fence.logdir / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ('exit_code', 'event_count', 'models', 'terminal_counts')}))
    return result.returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        # Do not serialize environment/config/payloads from exceptions.
        print('muse-file-fence: refused (' + type(exc).__name__ + ')', file=__import__('sys').stderr)
        raise SystemExit(1)
