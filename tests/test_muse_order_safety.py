"""Only owned loopback fixtures are contacted; no broker protocol or payload."""
import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from tools import muse_file_fence as fence_module
from tools import muse_order_safety as guard


class MuseOrderSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='muse-order-safety-', dir='/var/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.policy = self.root / 'safe-allowlist.json'
        self.listener = {'address': '127.0.0.1', 'port': 34567, 'inode': 76543}
        self.inventory = {('127.0.0.1', 34567): dict(self.listener)}
        self.process = {'pid': 999, 'start_ticks': 321, 'uid': 1000,
                        'executable': '/usr/bin/public-fixture', 'comm': 'public-fixture',
                        'boot_id': 'synthetic-boot-id'}
        self.write_policy()

    def entry(self, **changes):
        value = {'address': '127.0.0.1', 'port': 34567, 'process': self.process,
                 'class': 'public-web', 'purpose': 'Owned public qualification fixture',
                 'source': 'tests/test_muse_order_safety.py:test_public_web_positive_sends_no_payload'}
        value.update(changes)
        return value

    def write_policy(self, entries=None, **changes):
        value = {'schema': guard.SCHEMA, 'listeners': entries if entries is not None else []}
        value.update(changes)
        self.policy.write_text(json.dumps(value))
        self.policy.chmod(0o600)

    def names(self, inventory):
        return {key: 'public-fixture' for key in inventory}

    def refuse(self, path=None, inventory=None):
        with mock.patch.object(guard, 'kernel_loopback_listeners',
                               return_value=self.inventory if inventory is None else inventory), \
                mock.patch.object(guard, 'listener_process_names', side_effect=self.names), \
                mock.patch.object(guard, 'process_identity', return_value=dict(self.process)), \
                mock.patch.object(guard.socket, 'socket') as contacted:
            with self.assertRaises(guard.OrderSafetyRefused) as failure:
                guard.check_order_safety(path if path is not None else self.policy)
            contacted.assert_not_called()
        self.assertFalse(failure.exception.receipt['pass'])
        return failure.exception.receipt

    def test_missing_inaccessible_or_symlink_policy_refused(self):
        self.refuse(self.root / 'missing.json')
        with mock.patch.object(guard.os, 'open', side_effect=PermissionError('fixture denial')):
            self.refuse()
        link = self.root / 'policy-alias.json'
        link.symlink_to(self.policy)
        self.refuse(link)
        self.policy.chmod(0o666)
        self.refuse()

    def test_invalid_incomplete_and_duplicate_policy_refused(self):
        for changes in ({'schema': 'unknown'}, {'listeners': [{}]},
                        {'listeners': 'not-a-list'}, {'unexpected': 'field'}):
            with self.subTest(changes=changes):
                self.write_policy(**changes)
                self.refuse()
        self.policy.write_text('{')
        self.refuse()
        self.policy.write_text('{"schema": "first", "schema": "second"}')
        self.refuse()
        for entry in (self.entry(source=''), self.entry(purpose=''),
                      self.entry(process={'comm': 'name-is-not-identity'})):
            self.write_policy([entry])
            self.refuse()
        self.write_policy([self.entry(), self.entry()])
        self.refuse()

    def test_inventory_unknown_or_inaccessible_refused(self):
        with mock.patch.object(guard, 'kernel_loopback_listeners',
                               side_effect=PermissionError('fixture metadata refusal')), \
                mock.patch.object(guard.socket, 'socket') as contacted:
            with self.assertRaises(guard.OrderSafetyRefused):
                guard.check_order_safety(self.policy)
            contacted.assert_not_called()
        receipt = self.refuse()
        self.assertEqual(receipt['checks'], [{'port': 34567, 'process': 'public-fixture',
                                             'decision': 'REFUSED-unclassified'}])
        self.write_policy([self.entry()])
        self.refuse(inventory={('127.0.0.1', 34568): {**self.listener, 'port': 34568}})
        with mock.patch.object(guard, 'listener_process_names', side_effect=OSError('fixture')):
            with self.assertRaises(guard.OrderSafetyRefused):
                guard.check_order_safety(self.policy)

    def test_each_protected_endpoint_class_cannot_be_safe(self):
        for classification in sorted(guard.PROTECTED_CLASSES | {'unknown-service'}):
            with self.subTest(classification=classification):
                self.write_policy([self.entry(**{'class': classification})])
                self.refuse()

    def test_empty_policy_refuses_protected_listener_fixtures(self):
        fixtures = [(4002, 'rootlesskit')]
        fixtures += [(35000 + i, name) for i, name in enumerate(sorted(guard.PROTECTED_CLASSES))]
        for port, name in fixtures:
            with self.subTest(process=name):
                endpoint = {**self.listener, 'port': port}
                inventory = {('127.0.0.1', port): endpoint}
                with mock.patch.object(guard, 'kernel_loopback_listeners', return_value=inventory), \
                        mock.patch.object(guard, 'listener_process_names',
                                          return_value={('127.0.0.1', port): name}), \
                        mock.patch.object(guard.socket, 'socket') as contacted:
                    with self.assertRaises(guard.OrderSafetyRefused) as failure:
                        guard.check_order_safety(self.policy)
                    contacted.assert_not_called()
                self.assertEqual(failure.exception.receipt['checks'], [
                    {'port': port, 'process': name, 'decision': 'REFUSED-unclassified'}])

    def test_policy_within_fenced_writable_tree_refused(self):
        with mock.patch.object(guard, 'kernel_loopback_listeners', return_value={}), \
                mock.patch.object(guard, 'listener_process_names', return_value={}):
            with self.assertRaises(guard.OrderSafetyRefused):
                guard.check_order_safety(self.policy, writable_roots=(self.root,))

    def test_process_identity_change_refused_without_contact(self):
        for field, value in (('pid', 998), ('start_ticks', 322), ('uid', 1001),
                             ('executable', '/usr/bin/different'), ('comm', 'different'),
                             ('boot_id', 'different-boot')):
            with self.subTest(field=field):
                self.write_policy([self.entry(process={**self.process, field: value})])
                self.refuse()

    def test_public_web_positive_sends_no_payload(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            listener.settimeout(2)
            port = listener.getsockname()[1]
            actual = guard.kernel_loopback_listeners()[('127.0.0.1', port)]
            self.assertEqual(actual['inode'], os.fstat(listener.fileno()).st_ino)
            identity = guard.process_identity(os.getpid(), actual['inode'])
            self.write_policy([self.entry(port=port, process=identity)])
            with mock.patch.object(guard, 'kernel_loopback_listeners',
                                   return_value={('127.0.0.1', port): actual}):
                receipt = guard.check_order_safety(self.policy)
            self.assertTrue(receipt['pass'])
            self.assertEqual(receipt['checks'][0]['decision'], 'SAFE-public-loopback-reachable')
            self.assertEqual(set(receipt['checks'][0]), {'port', 'process', 'decision'})
            with listener.accept()[0] as connection:
                connection.settimeout(2)
                self.assertEqual(connection.recv(1), b'')

    def test_empty_inventory_positive_and_changing_inventory_refusal(self):
        with mock.patch.object(guard, 'kernel_loopback_listeners', return_value={}), \
                mock.patch.object(guard, 'listener_process_names', return_value={}):
            self.assertTrue(guard.check_order_safety(self.policy)['pass'])
        with mock.patch.object(guard, 'kernel_loopback_listeners', side_effect=[{}, self.inventory]), \
                mock.patch.object(guard, 'listener_process_names', return_value={}):
            with self.assertRaises(guard.OrderSafetyRefused):
                guard.check_order_safety(self.policy)

    def test_kernel_inventory_ipv4_ipv6_mapped_and_wildcards(self):
        def table(name, rows):
            path = self.root / name
            path.write_text('sl local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n'
                            + '\n'.join(rows) + '\n')
            return path
        ipv4 = table('tcp', [
            '0: 0100007F:1234 00000000:0000 0A 0:0 0:0 0 1000 0 123',
            '1: 00000000:1235 00000000:0000 0A 0:0 0:0 0 1000 0 124',
            '2: 0100000A:1236 00000000:0000 0A 0:0 0:0 0 1000 0 125',
        ])
        ipv6 = table('tcp6', [
            '0: 00000000000000000000000001000000:1237 0000:0000 0A 0:0 0:0 0 1000 0 126',
            '1: 00000000000000000000000000000000:1238 0000:0000 0A 0:0 0:0 0 1000 0 127',
            '2: 0000000000000000FFFF00000100007F:1239 0000:0000 0A 0:0 0:0 0 1000 0 128',
        ])
        with mock.patch.object(guard, 'PROC_NETWORK_TABLES',
                               ((ipv4, socket.AF_INET), (ipv6, socket.AF_INET6))):
            inventory = guard.kernel_loopback_listeners()
            self.assertEqual(set(inventory), {('127.0.0.1', 0x1234), ('127.0.0.1', 0x1235),
                                             ('::1', 0x1237), ('::1', 0x1238),
                                             ('127.0.0.1', 0x1239)})
            ipv4.write_text('unknown kernel format\n')
            with self.assertRaises(ValueError):
                guard.kernel_loopback_listeners()

    def launcher_fixture(self, role):
        runtime = self.root / (role + '-synthetic-runtime')
        runtime.write_text('#!/usr/bin/python3\nraise RuntimeError("must not start")\n')
        runtime.chmod(0o700)
        auth = self.root / 'synthetic-sign-in.json'
        auth.write_text('{}\n')
        settings = self.root / 'synthetic-settings.json'
        settings.write_text('{"schema_version": 1}\n')
        brief = self.root / 'brief.md'
        brief.write_text('Synthetic launch-gate control.\n')
        digest = hashlib.sha256(runtime.read_bytes()).hexdigest()
        work = self.root / (role + '-work')
        work.mkdir()
        logs = self.root / (role + '-logs')
        argv = ['muse-file-fence', '--role', role, '--runtime', str(runtime),
                '--auth', str(auth), '--settings', str(settings),
                str(work), str(brief), str(logs)]
        return argv, logs, digest

    def test_both_roles_refuse_before_any_runtime_start(self):
        for role in ('builder', 'reviewer'):
            with self.subTest(role=role):
                argv, logs, digest = self.launcher_fixture(role)
                with mock.patch('sys.argv', argv), \
                        mock.patch.object(fence_module, 'RUNTIME_SHA256', digest), \
                        mock.patch.object(guard, 'DEFAULT_SAFE_ALLOWLIST', self.root / 'missing.json'), \
                        mock.patch.object(fence_module, 'native_argv', side_effect=AssertionError(
                            'native argv requested before SAFE acceptance')) as argv_builder:
                    with self.assertRaises(guard.OrderSafetyRefused):
                        fence_module.main()
                    argv_builder.assert_not_called()
                receipt = json.loads((logs / 'fence-probe.json').read_text())
                self.assertFalse(receipt['pass'])
                self.assertFalse(receipt['order_safety'][0]['pass'])

    def test_new_listener_during_offline_probe_refuses_live_start(self):
        for role in ('builder', 'reviewer'):
            with self.subTest(role=role):
                argv, logs, digest = self.launcher_fixture(role)
                observed = {}
                def offline_probe(*args):
                    observed.update(self.inventory)
                    return {'pass': True, 'checks': {'offline-fixture': True}}
                with mock.patch('sys.argv', argv), \
                        mock.patch.object(fence_module, 'RUNTIME_SHA256', digest), \
                        mock.patch.object(guard, 'DEFAULT_SAFE_ALLOWLIST', self.policy), \
                        mock.patch.object(guard, 'kernel_loopback_listeners', side_effect=lambda: dict(observed)), \
                        mock.patch.object(guard, 'listener_process_names', side_effect=self.names), \
                        mock.patch.object(fence_module, 'native_argv', return_value=['synthetic-runtime']), \
                        mock.patch.object(fence_module.subprocess, 'run', return_value=mock.Mock(
                            stdout='Muse Code (' + fence_module.VERSION + ')')), \
                        mock.patch.object(fence_module, 'probe', side_effect=offline_probe), \
                        mock.patch.object(fence_module, 'run_bounded_fence', side_effect=AssertionError(
                            'live execution followed a newly unlisted listener')) as live:
                    with self.assertRaises(guard.OrderSafetyRefused):
                        fence_module.main()
                    live.assert_not_called()
                receipt = json.loads((logs / 'fence-probe.json').read_text())
                self.assertTrue(receipt['order_safety'][0]['pass'])
                self.assertFalse(receipt['order_safety'][1]['pass'])

    def test_empty_inventory_allows_bounded_synthetic_role_run(self):
        argv, logs, digest = self.launcher_fixture('builder')
        with mock.patch('sys.argv', argv), \
                mock.patch.object(fence_module, 'RUNTIME_SHA256', digest), \
                mock.patch.object(guard, 'DEFAULT_SAFE_ALLOWLIST', self.policy), \
                mock.patch.object(guard, 'kernel_loopback_listeners', return_value={}), \
                mock.patch.object(guard, 'listener_process_names', return_value={}), \
                mock.patch.object(fence_module, 'native_argv', return_value=['synthetic-runtime']), \
                mock.patch.object(fence_module.subprocess, 'run', return_value=mock.Mock(
                    stdout='Muse Code (' + fence_module.VERSION + ')')), \
                mock.patch.object(fence_module, 'probe', return_value={'pass': True}), \
                mock.patch.object(fence_module, 'run_bounded_fence', return_value=0) as live:
            self.assertEqual(fence_module.main(), 0)
            live.assert_called_once()
        receipt = json.loads((logs / 'receipt.json').read_text())
        self.assertEqual(len(receipt['order_safety']), 2)
        self.assertTrue(all(item['pass'] for item in receipt['order_safety']))

    def test_published_canary_has_only_sanitized_listener_metadata(self):
        root = Path(__file__).resolve().parents[1]
        def check(value):
            if isinstance(value, dict):
                self.assertFalse(set(value) & {'pid', 'uid', 'host', 'hostname', 'account',
                                               'address', 'inode', 'boot_id', 'auth'})
                for item in value.values():
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)
        for name in ('first-canary.json', 'second-canary.json'):
            with self.subTest(receipt=name):
                receipt = json.loads((root / 'notes/muse-native-roles-20261016' / name).read_text())
                self.assertEqual(receipt['decision'], 'REFUSED')
                self.assertEqual(receipt['tcp_contacts'], 0)
                self.assertEqual(receipt['model_requests'], 0)
                self.assertEqual(receipt['listener_count'], len(receipt['listener_set']))
                self.assertEqual({lane['name'] for lane in receipt['lanes']},
                                 {'muse-wonder-builder', 'muse-wonder-reviewer'})
                for lane in receipt['lanes']:
                    self.assertEqual(lane['state'], 'CLOSED')
                    self.assertEqual(lane['first_receipt'], 'REFUSED')
                for listener in receipt['listener_set']:
                    self.assertEqual(set(listener), {'port', 'process'})
                    self.assertIs(type(listener['port']), int)
                    self.assertIsInstance(listener['process'], str)
                check(receipt)


if __name__ == '__main__':
    unittest.main()
