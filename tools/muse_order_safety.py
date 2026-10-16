"""A reviewed SAFE-allowlist gate for shell-capable native Muse roles.

This is a launch-time loopback check, not a network sandbox. It never sends an
application payload or contacts a classified protected service. Linux listener
metadata and CPython socket/file primitives are the existing upstream surfaces.
"""
import datetime
import errno
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import subprocess


SCHEMA = 'muse-native-safe-loopback/1'
DEFAULT_SAFE_ALLOWLIST = Path(__file__).resolve().parent / 'policies/muse_native_safe_loopback.json'
PUBLIC_CLASSES = frozenset({'public-web'})
PROTECTED_CLASSES = frozenset({
    'ibgateway', 'order-gate', 'order-webhook', 'order-mcp',
    'order-capable', 'credential-bearing',
})
PROC_NETWORK_TABLES = ((Path('/proc/net/tcp'), socket.AF_INET),
                       (Path('/proc/net/tcp6'), socket.AF_INET6))


class OrderSafetyRefused(ValueError):
    def __init__(self, receipt):
        super().__init__('order-safety gate refused')
        self.receipt = receipt


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate SAFE policy field')
        result[key] = value
    return result


def _endpoint(value):
    if not isinstance(value, dict) or set(value) != {
            'address', 'port', 'process', 'class', 'purpose', 'source'}:
        raise ValueError('invalid SAFE entry')
    address = ipaddress.ip_address(value['address'])
    if not address.is_loopback or str(address) != value['address']:
        raise ValueError('SAFE endpoint is not canonical loopback')
    if type(value['port']) is not int or not 0 < value['port'] < 65536:
        raise ValueError('invalid SAFE port')
    if value['class'] not in PUBLIC_CLASSES:
        raise ValueError('only reviewed public services may be SAFE')
    if any(not isinstance(value[key], str) or not value[key].strip()
           for key in ('purpose', 'source')):
        raise ValueError('SAFE entries require reason and primary-source reference')
    identity = value['process']
    if not isinstance(identity, dict) or set(identity) != {
            'pid', 'start_ticks', 'uid', 'executable', 'comm', 'boot_id'}:
        raise ValueError('SAFE process identity is incomplete')
    for name in ('pid', 'start_ticks', 'uid'):
        if type(identity[name]) is not int or identity[name] < (0 if name == 'uid' else 1):
            raise ValueError('invalid SAFE process identity')
    for name in ('executable', 'comm', 'boot_id'):
        if not isinstance(identity[name], str) or not identity[name].strip():
            raise ValueError('invalid SAFE process identity')
    if not identity['executable'].startswith('/'):
        raise ValueError('SAFE executable must be absolute')
    return (value['address'], value['port']), value


def read_allowlist(path):
    """Read only the PR-owned policy. The launcher has no caller override."""
    path = Path(path).absolute()
    if path.resolve() != path:
        raise ValueError('noncanonical SAFE policy path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, 'r', encoding='utf-8') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise ValueError('SAFE policy is not an owned protected regular file')
        raw = stream.read(131073)
    if len(raw) > 131072:
        raise ValueError('SAFE policy exceeds metadata bound')
    data = json.loads(raw, object_pairs_hook=_unique_object)
    if not isinstance(data, dict) or set(data) != {'schema', 'listeners'}:
        raise ValueError('unsupported SAFE policy fields')
    if data['schema'] != SCHEMA:
        raise ValueError('SAFE policy schema mismatch')
    if not isinstance(data['listeners'], list):
        raise ValueError('invalid SAFE listeners')
    endpoints = {}
    for item in data['listeners']:
        key, endpoint = _endpoint(item)
        if key in endpoints:
            raise ValueError('ambiguous SAFE listener')
        endpoints[key] = endpoint
    return endpoints


def process_identity(pid, socket_inode):
    """Metadata only: no command line, environment, auth or application data."""
    root = Path('/proc') / str(pid)
    info = root.stat()
    process_stat = (root / 'stat').read_text(encoding='ascii')
    # comm in stat is parenthesized and may itself contain spaces/parentheses.
    fields = process_stat[process_stat.rindex(')') + 2:].split()
    identity = {'pid': pid, 'uid': info.st_uid, 'start_ticks': int(fields[19]),
                'comm': (root / 'comm').read_text(encoding='utf-8').rstrip('\n'),
                'executable': os.readlink(root / 'exe'),
                'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    expected = 'socket:[' + str(socket_inode) + ']'
    for fd in (root / 'fd').iterdir():
        try:
            if os.readlink(fd) == expected:
                return identity
        except FileNotFoundError:
            continue  # An unrelated descriptor may close while inspecting it.
    raise ValueError('SAFE process does not own this listener')


def kernel_loopback_listeners():
    """Read Linux TCP LISTEN metadata; no port scan or process contents."""
    result = {}
    for path, family in PROC_NETWORK_TABLES:
        lines = path.read_text(encoding='ascii').splitlines()
        if not lines or not {'local_address', 'st'} <= set(lines[0].split()):
            raise ValueError('unknown kernel listener table')
        for line in lines[1:]:
            fields = line.split()
            if len(fields) < 10:
                raise ValueError('incomplete kernel listener entry')
            if fields[3] != '0A':
                continue
            host, port_hex = fields[1].split(':')
            if family == socket.AF_INET:
                if len(host) != 8:
                    raise ValueError('unknown IPv4 listener address')
                packed = struct.pack('=I', int(host, 16))
            else:
                if len(host) != 32:
                    raise ValueError('unknown IPv6 listener address')
                packed = struct.pack('=4I', *(int(host[i:i + 8], 16) for i in range(0, 32, 8)))
            address = ipaddress.ip_address(socket.inet_ntop(family, packed))
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
                address = address.ipv4_mapped
            if address.is_unspecified:
                address = ipaddress.ip_address('127.0.0.1' if address.version == 4 else '::1')
            if not address.is_loopback:
                continue
            port, inode = int(port_hex, 16), int(fields[9])
            if not 0 < port < 65536 or inode <= 0:
                raise ValueError('unknown listener identity')
            key = (str(address), port)
            if key in result:
                raise ValueError('ambiguous kernel listener identity')
            result[key] = {'address': key[0], 'port': port, 'inode': inode}
    return result


def listener_process_names(listeners):
    """Use ss's listener metadata only; no process command lines or payloads."""
    result = subprocess.run(['/usr/bin/ss', '-ltnpeH'], check=True,
                            env={'PATH': '/usr/bin:/bin', 'LANG': 'C'},
                            capture_output=True, text=True, timeout=5)
    inodes = {}
    for line in result.stdout.splitlines():
        inode = re.search(r'\bino:(\d+)\b', line)
        if inode:
            names = re.findall(r'\("([^"\n]+)",pid=\d+,fd=\d+\)', line)
            inodes[int(inode.group(1))] = ','.join(sorted(set(names))) or 'unknown'
    return {key: inodes.get(listener['inode'], 'unknown') for key, listener in listeners.items()}


def check_order_safety(allowlist_path=None, *, writable_roots=()):
    """Refuse unknown/protected listeners before any socket is contacted.

    Safe, identity-matched public listeners get a bounded TCP-connect canary
    with no application payload. Classification comes only from the explicit
    reviewed SAFE file. Everything else is conservatively refused from metadata.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    allowlist_path = (Path(allowlist_path) if allowlist_path is not None
                      else DEFAULT_SAFE_ALLOWLIST).absolute()
    receipt = {'schema': 'muse-native-order-safety/1', 'checked_utc': now.isoformat(),
               'safe_allowlist': str(allowlist_path),
               'network': 'shared host network; launch-time loopback check only',
               'checks': [], 'pass': False}
    try:
        if any(Path(root) == allowlist_path or Path(root) in allowlist_path.parents
               for root in writable_roots):
            raise ValueError('SAFE policy overlaps fenced writable paths')
        allowlist = read_allowlist(allowlist_path)
        listeners = kernel_loopback_listeners()
        observations = {key: {'port': item['port'], 'process': 'unknown',
                              'decision': 'REFUSED-unclassified'}
                        for key, item in sorted(listeners.items())}
        receipt['checks'] = list(observations.values())
        process_names = listener_process_names(listeners)
        refused = False
        for key, listener in sorted(listeners.items()):
            observation = observations[key]
            observation['process'] = process_names[key]
            entry = allowlist.get(key)
            if entry is None:
                refused = True
                continue
            identity = process_identity(entry['process']['pid'], listener['inode'])
            if entry['process'] != identity:
                observation['decision'] = 'REFUSED-process-changed'
                refused = True
                continue
            observation['decision'] = 'classified-SAFE'
        if refused:
            raise ValueError('listener inventory not safe')
        # Classify the entire inventory before making even a safe connection.
        for key, listener in sorted(listeners.items()):
            observation = observations[key]
            family = socket.AF_INET6 if ':' in listener['address'] else socket.AF_INET
            with socket.socket(family, socket.SOCK_STREAM) as connection:
                connection.settimeout(0.25)
                result = connection.connect_ex((listener['address'], listener['port']))
            if result == 0:
                observation['decision'] = 'SAFE-public-loopback-reachable'
            elif result == errno.ECONNREFUSED:
                observation['decision'] = 'SAFE-listener-closed-before-connect'
            else:
                raise ValueError('indeterminate listener reachability')
        # A changing inventory cannot inherit the initial classification.
        if kernel_loopback_listeners() != listeners:
            raise ValueError('listener inventory changed during check')
        for key, listener in sorted(listeners.items()):
            entry = allowlist[key]
            if process_identity(entry['process']['pid'], listener['inode']) != entry['process']:
                raise ValueError('SAFE process changed during check')
    except (OSError, ValueError, TypeError, KeyError, IndexError, OverflowError, RecursionError,
            subprocess.SubprocessError) as exc:
        receipt['refusal_class'] = type(exc).__name__
        raise OrderSafetyRefused(receipt) from None
    receipt['pass'] = True
    return receipt
