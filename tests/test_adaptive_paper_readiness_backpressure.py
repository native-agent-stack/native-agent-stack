"""Combined #1097 readiness/#1084 handler bound; synthetic, SDK-free."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'blueprints/us-equities/adaptive-paper'
sys.path.insert(0, str(SOURCE))
import runner
import transport


class ReadinessBackpressure(unittest.IsolatedAsyncioTestCase):
    async def test_opted_start30_health5_and_handler8_keep_order_age3(self):
        raw = json.loads((SOURCE / 'config.json').read_text())
        raw.update(regular_session_only=False, extended_hours_enabled=True)
        raw['sessions']['extended_hours'] = True
        raw['extended_hours_start_readiness'] = {
            'window_seconds': 30, 'benchmark_quote_timeout_seconds': 5}
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            config_path = Path(directory) / 'config.json'
            config_path.write_text(json.dumps(raw))
            config, limits, _ = runner.load_config(config_path)
        settings = runner.start_readiness_settings(config, 'paper', 'PRE')
        self.assertEqual(settings, {'window_seconds': 30, 'benchmark_quote_timeout_seconds': 5})
        self.assertEqual(limits.quote_max_age_seconds, 3)

        enums = types.ModuleType('alpaca.data.enums')
        enums.DataFeed = lambda value: value
        stubs = {'alpaca': types.ModuleType('alpaca'),
                 'alpaca.data': types.ModuleType('alpaca.data'), 'alpaca.data.enums': enums}
        with patch.dict(sys.modules, stubs), patch.object(transport, '_sdk_client', return_value=Mock()), \
             patch.object(transport, '_protocol_factory', return_value=None), \
             patch.object(transport, '_stream_classes', return_value=(Mock, Mock)):
            port = transport.AlpacaPaperTransport(
                'fixture-key', 'fixture-secret', ['SPY'], required_quote_symbols=['SPY'],
                before_request=lambda *a, **k: None, before_submit=lambda *a: None,
                sink_observation=lambda *a: None, extended_hours_allowed=True,
                queue_size=1, quote_timeout=3, order_quote_max_age_seconds=3,
                start_timeout=settings['window_seconds'],
                benchmark_quote_timeout_seconds=settings['benchmark_quote_timeout_seconds'])
        port._started = True
        port._auth = {'orders': True, 'quotes': True}
        port._acks = dict(port._auth)
        clock = [0.0]
        epoch = 1_800_000_000
        seen = []
        port._on_quote = seen.append
        quote = {'S': 'SPY', 'bp': '100', 'ap': '100.01', 'bs': 1, 'as': 1,
                 't': datetime.fromtimestamp(epoch - 4.05, timezone.utc)}

        async def advance(seconds):
            clock[0] += seconds

        with patch.object(transport.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(transport.time, 'time_ns', side_effect=lambda: int((epoch + clock[0]) * 1e9)):
            await port._quote_callback(quote)
            consumer = asyncio.create_task(port._consume_events())
            try:
                for _ in range(20):
                    if seen:
                        break
                    await asyncio.sleep(0)
                self.assertEqual(len(seen), 1, 'age4.05 must pass the opted benchmark consumer')
                self.assertTrue(port.health['fresh_quotes'])
                for side in ('buy', 'sell'):
                    with self.subTest(side=side), self.assertRaises(transport.SubmissionNotSent):
                        port._wire_guard({'symbol': 'SPY', 'side': side})
            finally:
                consumer.cancel()
                await asyncio.gather(consumer, return_exceptions=True)

            # The actual SDK callback is held by a full queue. Deterministic
            # time runs the deadline without an eight-second wall-clock wait.
            await port._quote_callback({'first': True})
            with patch.object(transport.asyncio, 'sleep', side_effect=advance):
                await port._order_callback({'received_order': True})
            self.assertAlmostEqual(clock[0], 8.0, places=6)
            self.assertLess(clock[0], 10, 'handler must return below the SDK ping timeout')
            self.assertEqual(port.start_timeout, 30)
            self.assertEqual(port.stream_health()['backpressure_waits'], 1)
            self.assertIn('queue_overflow', port.health['reasons'])
            self.assertFalse(port.ready)
            # Event loss stays irreversible even with a fresh owned sell quote.
            port._quote_values['SPY']['ts_ns'] = int((epoch + clock[0]) * 1e9)
            for side in ('buy', 'sell'):
                with self.subTest(side=side), self.assertRaisesRegex(
                        transport.SubmissionNotSent, 'recovery_observation_integrity_lost'):
                    port._wire_guard({'symbol': 'SPY', 'side': side})


if __name__ == '__main__':
    unittest.main()
