"""Production strategy cancel methods on protocol owners; visible without SDKs."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]

def production_method(filename, classname, method):
    source = ROOT / 'blueprints/us-equities/adaptive-paper' / filename
    tree = ast.parse(source.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == classname)
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method)
    scope = {'ClientOrderId': str, 'Action': lambda kind, cid: (kind, cid)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(source), 'exec'), scope)
    return scope[method]

class OvernightCancelMarks(unittest.TestCase):
    def test_adaptive_background_failure_allows_timeout_and_kill_switch_retry(self):
        method = production_method('native_strategy.py', 'AdaptiveStrategy', 'cancel_expired')
        for all_entries in (False, True):
            with self.subTest(all_entries=all_entries):
                pending, canceled = {'entry'}, []
                info = {'side': 'buy', 'symbol': 'SPY', 'created': 0, 'cancel_requested': False}
                owner = SimpleNamespace(pending={'entry': info},
                    transport=SimpleNamespace(overnight_cancel_pending=pending),
                    _halted=lambda symbol: False, cancel_order=canceled.append)
                method(owner, 10, 60)
                self.assertTrue(info['cancel_requested'])
                pending.clear()  # The actual operation resolved/refused.
                method(owner, 130, 60, all_entries=all_entries)
                self.assertEqual(canceled, ['entry'], 'resolved background cancel must not strand an entry')

    def test_adaptive_resolution_clears_only_its_background_mark(self):
        method = production_method('native_strategy.py', 'AdaptiveStrategy', 'cancel_expired')
        for engine_pending in (False, True):
            with self.subTest(engine_pending=engine_pending):
                pending, canceled = {'entry'}, []
                info = {'side': 'buy', 'symbol': 'SPY', 'created': 0, 'cancel_requested': engine_pending}
                owner = SimpleNamespace(pending={'entry': info},
                    transport=SimpleNamespace(overnight_cancel_pending=pending),
                    _halted=lambda symbol: False, cancel_order=canceled.append)
                method(owner, 1, 60)
                pending.clear()
                method(owner, 2, 60)
                self.assertEqual(info['cancel_requested'], engine_pending)
                self.assertEqual(canceled, [])

    def test_mover_background_failure_allows_entry_timeout_retry(self):
        method = production_method('mover.py', 'MoverBook', '_cancels')
        pending = {'entry'}
        record = SimpleNamespace(client_id='entry', side='buy', created=0,
            cancel_requested=False, overnight_cancel_requested=False, cancel_reason=None)
        owner = SimpleNamespace(open_orders=lambda symbol: [record], _halted=lambda symbol: False,
            _cancel_pending=pending.__contains__, events=lambda event: None,
            plan=SimpleNamespace(timing=SimpleNamespace(entry_timeout_seconds=60, exit_timeout_seconds=60)))
        leg = SimpleNamespace(exit_reason=None)
        self.assertEqual(method(owner, leg, 'SPY', 10, None), [])
        self.assertTrue(record.cancel_requested)
        pending.clear()
        self.assertEqual(method(owner, leg, 'SPY', 130, None), [('cancel', 'entry')])

    def test_mover_resolution_preserves_an_engine_cancel_mark(self):
        method = production_method('mover.py', 'MoverBook', '_cancels')
        pending = {'entry'}
        record = SimpleNamespace(client_id='entry', side='buy', created=0,
            cancel_requested=True, overnight_cancel_requested=False, cancel_reason=None)
        owner = SimpleNamespace(open_orders=lambda symbol: [record], _halted=lambda symbol: False,
            _cancel_pending=pending.__contains__, events=lambda event: None,
            plan=SimpleNamespace(timing=SimpleNamespace(entry_timeout_seconds=60, exit_timeout_seconds=60)))
        leg = SimpleNamespace(exit_reason=None)
        self.assertEqual(method(owner, leg, 'SPY', 1, None), [])
        pending.clear()
        self.assertEqual(method(owner, leg, 'SPY', 130, None), [])
        self.assertTrue(record.cancel_requested)
