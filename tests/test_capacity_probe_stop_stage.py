"""Run-phase onset and STOP preservation through actual asynchronous lifecycle."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'blueprints/us-equities/order-throughput'))
import capacity as c
import capacity_fixture as fx
from test_order_throughput import LaggedExecutor


class ProbeStopStageTests(unittest.TestCase):
    def execute(self, broker_kind, *, lagged=False):
        clock = fx.FakeClock()
        with tempfile.TemporaryDirectory(dir='/var/tmp') as td:
            stop = Path(td) / 'STOP'
            broker = broker_kind(clock, stop)
            run = c.CapacityRun(broker, c.CapacityConfig(probe_limit=True,
                configured_cap_per_minute=250, max_duration_seconds=10, required_windows=1),
                clock=clock, executor=LaggedExecutor(clock) if lagged else c.InlineExecutor(), stop_file=stop)
            broker.run = run
            receipt = run.run()
        return receipt, run, broker

    def test_stop_then_cleanup_429_is_not_a_run_onset(self):
        class Cleanup429(fx.FakeBroker):
            def __init__(self, clock, stop):
                super().__init__(clock, bid='10', ask='10.02')
                self.stop, self.cleanup_429 = stop, False
            def submit(self, *args):
                response = super().submit(*args)
                if self.submit_count == 2:
                    self.stop.touch()
                return response
            def cancel(self, *args):
                if self.stop.exists() and not self.cleanup_429:
                    self.cleanup_429 = True
                    return c.Response(429, {'x-ratelimit-limit': '200', 'retry-after': '1'})
                return super().cancel(*args)
        receipt, run, broker = self.execute(Cleanup429)
        self.assertTrue(broker.cleanup_429)
        self.assertEqual(receipt['stop_reason'], 'stop_file_present')
        self.assertIsNone(receipt['probe_modes']['first_429'])
        self.assertTrue(receipt['cleanup']['verified_zero_open'])
        self.assertEqual(broker.submit_count, 2)

    def test_lagged_run_429_records_send_phase_and_completion_time_without_overwriting_stop(self):
        class Submit429(fx.FakeBroker):
            def __init__(self, clock, stop):
                super().__init__(clock, bid='10', ask='10.02')
                self.stop, self.response_at = stop, None
            def submit(self, *args):
                response = super().submit(*args)
                if self.submit_count == 2:
                    self.stop.touch()
                    self.response_at = self.clock.monotonic()
                    return c.Response(429, {'x-ratelimit-limit': '200', 'retry-after': '1'})
                return response
        receipt, run, broker = self.execute(Submit429, lagged=True)
        self.assertEqual(receipt['stop_reason'], 'stop_file_present')
        onset = receipt['probe_modes']['first_429']
        self.assertEqual(onset['phase'], 'run')
        self.assertAlmostEqual(onset['seconds_from_start'], broker.response_at - run.t0, places=6)
        self.assertNotIn('at_monotonic', onset)
        self.assertTrue(receipt['cleanup']['verified_zero_open'])

    def test_probe_rate_summary_is_frozen_before_safe_cleanup_switch(self):
        class Plain(fx.FakeBroker):
            def __init__(self, clock, stop): super().__init__(clock, bid='10', ask='10.02')
        receipt, _, _ = self.execute(Plain)
        self.assertEqual(receipt['rate']['budget_per_minute'], 250)
        self.assertEqual(receipt['rate']['effective_limit'], 250)
        self.assertEqual(receipt['rate']['reserve_per_minute'], 0)
        self.assertEqual(receipt['rate']['headroom'], 1.0)
        self.assertEqual(receipt['cleanup_rate']['budget_per_minute'], 180)
        self.assertEqual(receipt['cleanup_rate']['headroom'], 0.9)
        self.assertTrue(receipt['cleanup']['verified_zero_open'])

    def test_signal_during_run_request_remains_the_stop_reason(self):
        class Signalled429(fx.FakeBroker):
            def __init__(self, clock, stop): super().__init__(clock, bid='10', ask='10.02')
            def submit(self, *args):
                response = super().submit(*args)
                if self.submit_count == 2:
                    self.run.request_stop('signal')
                    return c.Response(429, {'x-ratelimit-limit': '200', 'retry-after': '1'})
                return response
        receipt, _, _ = self.execute(Signalled429, lagged=True)
        self.assertEqual(receipt['stop_reason'], 'signal')
        self.assertEqual(receipt['probe_modes']['first_429']['kind'], 'submit')
        self.assertTrue(receipt['cleanup']['verified_zero_open'])


if __name__ == '__main__': unittest.main()
