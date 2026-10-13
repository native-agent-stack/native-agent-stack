"""Default-off exploratory paper modes through the existing harness seam."""
from pathlib import Path
import sys
import tempfile
import unittest
import json
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'blueprints/us-equities/order-throughput'))
import capacity as c
import capacity_fixture as fx
import alpaca_capacity_port as native
import transport


class ProbeModeTests(unittest.TestCase):
    def run_mode(self,*,place=False,probe=False,broker=None,clock=None,**changes):
        clock=clock or fx.FakeClock()
        broker=broker or fx.FakeBroker(clock,bid='10.00',ask='10.02')
        config=c.CapacityConfig(**dict({'max_duration_seconds':70,'required_windows':1,
            'max_orders':350,'max_open_orders':100,'max_open_notional_usd':'10000',
            'place_only':place,'probe_limit':probe},**changes))
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
            run=c.CapacityRun(broker,config,clock=clock,executor=c.InlineExecutor(),stop_file=Path(temp)/'STOP')
            return run.run(),run,broker

    def test_place_only_uses_one_guarded_cancel_all_and_no_individual_cancels(self):
        receipt,run,broker=self.run_mode(place=True)
        self.assertEqual(receipt['status'],'completed')
        self.assertEqual(broker.cancel_all_calls,1)
        self.assertEqual(receipt['cleanup']['individual_cancels'],0)
        self.assertEqual(receipt['cleanup']['rest_sweep_cancels'],0)
        self.assertTrue(receipt['cleanup']['verified_zero_open'])
        self.assertEqual(receipt['orders']['cancel_requests'],0)
        self.assertFalse(any(row['cancels'] for row in receipt['throughput']['windows']))
        self.assertTrue(receipt['probe_modes']['place_only'])
        self.assertFalse(receipt['acceptance']['passed'])
        self.assertIn('p90_ms',receipt['latency']['submit_rest_ack'])

    def test_probe_limit_hits_first_429_then_restores_safe_cleanup(self):
        receipt,run,broker=self.run_mode(probe=True,configured_cap_per_minute=250)
        self.assertEqual(receipt['stop_reason'],'probe_first_http_429')
        self.assertEqual(receipt['probe_modes']['first_429']['status'],429)
        self.assertEqual(receipt['probe_modes']['first_429']['headers']['x-ratelimit-limit'],'200')
        self.assertIn('x-ratelimit-reset',receipt['probe_modes']['first_429']['headers'])
        self.assertEqual(receipt['probe_modes']['requested_requests_per_minute'],250)
        self.assertTrue(receipt['cleanup']['verified_zero_open'])
        self.assertEqual(receipt['rate']['budget_per_minute'],180)
        self.assertFalse(receipt['acceptance']['passed'])
        self.assertFalse(any(a['t']>receipt['probe_modes']['first_429']['at_monotonic'] and a['kind']=='submit' for a in run.actions))

    def test_native_cancel_all_boundary_is_available_only_for_explicit_place_only(self):
        try:import requests
        except ImportError:self.skipTest('native requests fixture requires the qualified alpaca-py runtime')
        for admitted in (False,True):
            with self.subTest(admitted=admitted):
                session=transport.GuardedSession(origin=transport.PAPER_URL,before_request=lambda *_a,**_k:None,
                    allow_cancel_all=admitted)
                response=requests.Response();response.status_code=207
                with mock.patch.object(session._session,'request',return_value=response) as wire:
                    if admitted:self.assertIs(session.request('DELETE',transport.PAPER_URL+'/v2/orders'),response)
                    else:
                        with self.assertRaises(transport.TransportError):session.request('DELETE',transport.PAPER_URL+'/v2/orders')
                        wire.assert_not_called()
                session.close()
        with mock.patch.object(transport,'data_feed',return_value='iex'):
            port=native.AlpacaCapacityPort('fixture','fixture','SPY',place_only=True)
            self.assertTrue(port.supports_cancel_all)
            port=native.AlpacaCapacityPort('fixture','fixture','SPY')
            self.assertFalse(port.supports_cancel_all)
            with self.assertRaises(transport.TransportError):port.cancel_all()

    def test_place_only_records_no_onset_when_explicit_stock_guard_binds(self):
        clock=fx.FakeClock()
        receipt,run,broker=self.run_mode(place=True,probe=True,clock=clock,
            configured_cap_per_minute=250)
        # The stock guard remains explicit; this fixture's100open cap is too
        # small to cross200. A rung that claims no onset must say why it ended.
        self.assertLessEqual(receipt['orders']['rest_accepted'],100)
        self.assertEqual(broker.cancel_all_calls,1)
        self.assertTrue(receipt['cleanup']['verified_zero_open'])
        self.assertIsNone(receipt['probe_modes']['first_429'])

    def test_foreign_order_blocks_bulk_cancel_and_is_retained(self):
        clock=fx.FakeClock();broker=fx.FakeBroker(clock,bid='10',ask='10.02',foreign_open_orders=1)
        receipt,_,broker=self.run_mode(place=True,broker=broker,clock=clock)
        self.assertEqual(receipt['status'],'refused')
        self.assertEqual(broker.cancel_all_calls,0)
        self.assertEqual(broker.submit_count,0)

    def test_default_modes_and_ordinary_governor_remain_disabled(self):
        args=c.build_parser().parse_args(['offline','--output','/fixture/receipt.json'])
        config=c.config_from_args(args)
        self.assertFalse(config.place_only);self.assertFalse(config.probe_limit)
        self.assertNotIn('place_only',config.public());self.assertNotIn('probe_limit',config.public())
        receipt,_,broker=self.run_mode()
        self.assertEqual(broker.cancel_all_calls,0)
        self.assertGreater(receipt['orders']['cancel_requests'],0)
        self.assertEqual(receipt['rate']['budget_per_minute'],180)
        self.assertNotIn('probe_modes',receipt)

    def test_bad_probe_mode_configuration_is_refused_before_any_order(self):
        for fields in ({'max_duration_seconds':120},{'configured_cap_per_minute':251},{'qty':2}):
            with self.subTest(fields=fields):
                cfg=c.CapacityConfig(**dict({'probe_limit':True,'max_duration_seconds':70},**fields))
                with self.assertRaises(c.HarnessRefusal):cfg.validate()

    def test_place_only_over_header_probe_stops_at_first_429_and_cleans_all(self):
        receipt,run,broker=self.run_mode(place=True,probe=True,configured_cap_per_minute=250,
            max_open_orders=300,max_open_notional_usd='300000')
        self.assertEqual(receipt['stop_reason'],'probe_first_http_429')
        self.assertEqual(broker.cancel_all_calls,1)
        self.assertEqual(receipt['orders']['cancel_requests'],0)
        self.assertTrue(receipt['cleanup']['verified_zero_open'])
        self.assertEqual(receipt['http_429']['total'],1)
        self.assertEqual(receipt['probe_modes']['first_429']['headers']['x-ratelimit-remaining'],'0')
        self.assertFalse(any(a['kind']=='submit' and a['t']>receipt['probe_modes']['first_429']['at_monotonic'] for a in run.actions))

    def test_flagged_journal_retains_latency_samples_for_p90_and_recovery_still_parses(self):
        clock=fx.FakeClock();broker=fx.FakeBroker(clock,bid='10',ask='10.02')
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
            cfg=c.CapacityConfig(place_only=True,probe_limit=True,max_duration_seconds=10,
                required_windows=1,max_open_orders=100)
            journal=Path(temp)/'run.journal.jsonl'
            run=c.CapacityRun(broker,cfg,clock=clock,executor=c.InlineExecutor(),
                stop_file=Path(temp)/'STOP',journal_path=journal)
            receipt=run.run()
            rows=[json.loads(line) for line in journal.read_text().splitlines()]
            samples=[r['submit_rest_ack_ms'] for r in rows if r['type']=='probe_latency' and r['submit_rest_ack_ms'] is not None]
            self.assertEqual(round(c.percentile(samples,90),3),receipt['latency']['submit_rest_ack']['p90_ms'])
            self.assertEqual(len(c.read_journal(journal)['intents']),len(run.probes))
            self.assertTrue(c.read_journal(journal)['end']['verified_zero_open'])
            self.assertTrue(all('id' not in r for r in rows if r['type']=='probe_latency'))

    def test_failed_or_partial_bulk_response_never_falls_back_to_individual_cancel(self):
        class PartialBulk(fx.FakeBroker):
            def cancel_all(self):
                self.cancel_all_calls+=1
                return c.Response(207,{'x-ratelimit-limit':'200'})
        clock=fx.FakeClock();broker=PartialBulk(clock,bid='10',ask='10.02')
        receipt,_,broker=self.run_mode(place=True,broker=broker,clock=clock)
        self.assertEqual(broker.cancel_all_calls,1)
        self.assertFalse(receipt['cleanup']['verified_zero_open'])
        self.assertEqual(receipt['orders']['cancel_requests'],0)
        self.assertEqual(receipt['status'],'needs_attention')

    def test_foreign_order_arriving_after_preflight_blocks_bulk_cancellation(self):
        class ForeignLate(fx.FakeBroker):
            def submit(self,*args):
                result=super().submit(*args)
                if self.submit_count==1:self._create('foreign-after-start','SPY','9')
                return result
        clock=fx.FakeClock();broker=ForeignLate(clock,bid='10',ask='10.02')
        receipt,_,broker=self.run_mode(place=True,broker=broker,clock=clock)
        self.assertEqual(broker.cancel_all_calls,0)
        self.assertEqual(broker.orders['foreign-after-start']['status'],'new')
        self.assertEqual(receipt['cleanup']['cancel_all_decision'],'foreign_open_orders_present')
        self.assertFalse(receipt['cleanup']['verified_zero_open'])

    def test_stop_blocks_submission_while_bulk_cleanup_still_verifies_zero(self):
        clock=fx.FakeClock();broker=fx.FakeBroker(clock,bid='10',ask='10.02')
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temp:
            stop=Path(temp)/'STOP'
            original=broker.submit
            def stop_after_submit(*args):
                result=original(*args);stop.write_text('synthetic stop');return result
            broker.submit=stop_after_submit
            config=c.CapacityConfig(place_only=True,max_duration_seconds=10,required_windows=1)
            receipt=c.CapacityRun(broker,config,clock=clock,executor=c.InlineExecutor(),stop_file=stop).run()
            self.assertEqual(broker.submit_count,1)
            self.assertEqual(broker.cancel_all_calls,1)
            self.assertTrue(receipt['cleanup']['verified_zero_open'])

    def test_recovery_cli_cannot_enable_probe_admission(self):
        for command in ('recover','audit'):
            for flag in ('--place-only','--probe-limit'):
                with self.subTest(command=command,flag=flag):
                    with self.assertRaises(SystemExit) as caught:
                        c.main([command,'--output','/fixture/output.json',flag])
                    self.assertEqual(caught.exception.code,2)

    def test_bulk_capability_rejects_readonly_data_and_live_sessions(self):
        try:import requests
        except ImportError:self.skipTest('native requests fixture requires the qualified alpaca-py runtime')
        for origin,readonly in ((transport.PAPER_URL,True),(transport.DATA_URL,False),('https://api.alpaca.markets',False)):
            with self.subTest(origin=origin,readonly=readonly):
                with self.assertRaises(transport.TransportError):
                    transport.GuardedSession(origin=origin,read_only=readonly,
                        before_request=lambda *_a,**_k:None,allow_cancel_all=True)

    def test_place_only_one_share_flat_and_bounded_stock_constraints_hold(self):
        for values in ({'qty':2},{'acknowledged_positions':1},{'acknowledged_open_orders':1},
                {'max_open_orders':301},{'max_open_notional_usd':'300001'},{'max_duration_seconds':91}):
            with self.subTest(values=values):
                config=c.CapacityConfig(**dict({'place_only':True,'max_duration_seconds':70},**values))
                with self.assertRaises(c.HarnessRefusal):config.validate()

    def test_existing_governor_is_unclamped_only_for_flagged_measurement(self):
        import rate_governor
        clock=fx.FakeClock()
        for flag,budget in ((False,180),(True,250)):
            governor=rate_governor.RateGovernor(250,clock=clock.monotonic,wall=clock.time,probe_limit=flag)
            governor.observe_limit(200)
            self.assertEqual(governor.budget,budget)
            self.assertEqual(governor.observed_limit,200)
            governor.probe_limit=False
            self.assertEqual(governor.budget,180)


if __name__=='__main__':unittest.main()
