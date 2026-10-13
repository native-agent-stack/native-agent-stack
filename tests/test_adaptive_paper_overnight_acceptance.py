"""Lane A stage-start acceptance using hermetic clocks and existing port guards.

No account, credentials, sockets, units or deployment. The real main preflight
refuses the positive OVERNIGHT case; the existing #1081 port supplies its fix.
"""
import unittest

from tests import test_adaptive_paper_sessions as fixtures

ny, sess = fixtures.ny, fixtures.sess
validate_preflight, SafetyError = fixtures.validate_preflight, fixtures.SafetyError


class OvernightStartAcceptance(fixtures._PreflightClockFixture, unittest.TestCase):
    observation_at = fixtures.SessionAwareRequireOpenTests.observation_at
    config = fixtures.SessionAwareRequireOpenTests.config

    def overnight_config(self):
        return {**self.config(), "regular_session_only": False,
                "extended_hours_enabled": True, "feed": "boats", "quote_source": "boats_rest",
                "overnight": {"enabled": True, "flatten_minutes_before_pre": 10},
                "sessions": {"extended_hours": True, "overnight_holds": False}}

    def test_overnight_stage_start_is_admitted_only_with_qualified_flags(self):
        config = self.overnight_config()
        policy = sess.validate_session_policy(config)
        moment = ny(2026, 3, 9, 21, 0)
        observation = self.observation_at(moment, is_open=False)
        close = validate_preflight(observation, config, require_open=True, session_policy=policy)
        # Stage safety ends at the overnight boundary, not the later DAY expiry.
        self.assertEqual(close, ny(2026, 3, 10, 4, 0).timestamp())
        self.assertTrue(sess.order_extended_hours_flag(moment, policy))
        self.assertEqual(sess.extended_session_close(moment), ny(2026, 3, 10, 20, 0))
        self.assertTrue(sess.must_end_flat(policy, is_final_boundary=False))
        self.assertTrue(sess.must_end_flat(policy, is_final_boundary=True))

    def test_extended_hours_alone_does_not_arm_overnight(self):
        config = self.overnight_config()
        config.pop("overnight")
        config.pop("quote_source")
        policy = sess.validate_session_policy(config)
        observation = self.observation_at(ny(2026, 3, 9, 21, 0), is_open=False)
        with self.assertRaisesRegex(SafetyError, "regular_session_window_unavailable"):
            validate_preflight(observation, config, require_open=True, session_policy=policy)

    def test_overnight_opt_in_requires_all_existing_port_flags(self):
        for field, value in (("feed", "iex"), ("quote_source", "stream"),
                             ("extended_hours_enabled", False), ("regular_session_only", True),
                             ("overnight", {"enabled": False}),
                             ("sessions", {"extended_hours": True, "overnight_holds": True})):
            with self.subTest(field=field):
                config = self.overnight_config()
                config[field] = value
                with self.assertRaises(ValueError):
                    sess.validate_session_policy(config)

    def test_overnight_venue_uses_limit_day_with_extended_hours(self):
        from overnight import check_overnight_order
        from transport import normalize_intent
        order = {"symbol": "SPY", "side": "buy", "qty": "1", "limit_price": "100",
                 "client_order_id": "fixture-overnight", "extended_hours": True,
                 "type": "limit", "time_in_force": "day"}
        check_overnight_order(order)
        normalized = normalize_intent(order, ("SPY",), allow_extended_hours=True, overnight_allowed=True)
        self.assertIs(normalized["extended_hours"], True)
        for kind in ("market", "stop", "stop_limit"):
            with self.subTest(order_type=kind), self.assertRaisesRegex(ValueError, "overnight_order_contract_refused"):
                check_overnight_order({**order, "type": kind})

    def test_overnight_stage_does_not_use_the_later_day_expiry_to_bypass_cleanup(self):
        config = self.overnight_config()
        policy = sess.validate_session_policy(config)
        observation = self.observation_at(ny(2026, 3, 10, 3, 57), is_open=False)
        # A generous broker/RTH close cannot supply the missing eight-minute stage window.
        observation["clock"]["next_close_ns"] = int(ny(2026, 3, 10, 20, 0).timestamp() * 1e9)
        with self.assertRaisesRegex(SafetyError, "regular_session_window_unavailable"):
            validate_preflight(observation, config, require_open=True, session_policy=policy)

    def test_control_and_ordinary_pre_rth_post_admission_are_unchanged(self):
        for hour, extended, broker_open, admitted in (
                (7, False, False, False), (12, False, True, True), (18, False, False, False),
                (7, True, False, True), (12, True, True, True), (18, True, False, True),
                (21, False, False, False), (21, True, False, False)):
            with self.subTest(hour=hour, extended=extended):
                config = {**self.config(), "regular_session_only": not extended,
                          "extended_hours_enabled": extended,
                          "sessions": {"extended_hours": extended, "overnight_holds": False}}
                policy = sess.validate_session_policy(config)
                observation = self.observation_at(ny(2026, 3, 10, hour, 0), is_open=broker_open)
                if admitted:
                    close = validate_preflight(observation, config, require_open=True, session_policy=policy)
                    expected = (ny(2026, 3, 10, 20, 0).timestamp() if extended
                                else observation["clock"]["next_close_ns"] / 1e9)
                    self.assertEqual(close, expected)
                else:
                    with self.assertRaisesRegex(SafetyError, "regular_session_window_unavailable"):
                        validate_preflight(observation, config, require_open=True, session_policy=policy)
