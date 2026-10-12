"""Registered exploratory selectors use existing exits; synthetic inputs only."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from decimal import Decimal

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
import runner
import mover
from exploration import config_digest
from safety import RiskLimits, SafetyError
from exits import ExitContext, DEFAULT_PLAN


class ExploratoryExitPresets(unittest.TestCase):
    def load(self, name, *, preset, exploratory=True, **updates):
        data=json.loads((SOURCE/name).read_text())
        if exploratory:
            data.update(paper_lane="B",evidence_class="exploratory")
        data["exploratory_exit_preset"]={"version":"paper-exits-v1-20261012","name":preset}
        data.update(updates)
        with tempfile.TemporaryDirectory(dir="/var/tmp") as root:
            path=Path(root)/"config.json";path.write_text(json.dumps(data))
            return (mover.load_mover_config if name=="config-mover.json" else runner.load_config)(path)

    def test_partial_take_profit_preset_reaches_the_actual_exit_rule(self):
        _, _, policy=self.load("config.json",preset="partial-take-profit")
        context=ExitContext(now=1000,entered_at=990,pnl_bps=50,trail_bps=0,quote_fresh=True,
                            risk_off=False,force_exit=False,force_exit_reason="trial_end",volatility_bps=None)
        self.assertEqual(DEFAULT_PLAN.evaluate(context,policy).fraction,.5)

    def test_time_decay_preset_tightens_the_actual_stop(self):
        _,_,policy=self.load("config.json",preset="time-decay",stop_bps=100,max_hold_seconds=100)
        context=ExitContext(now=975,entered_at=900,pnl_bps=-70,trail_bps=0,quote_fresh=True,
                            risk_off=False,force_exit=False,force_exit_reason="trial_end",volatility_bps=None)
        decision=DEFAULT_PLAN.evaluate(context,policy)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.reason,"stop_loss")
        self.assertEqual(policy.max_hold_seconds,100)

    def test_mover_x3_preset_selects_existing_trailing_rule(self):
        _,_,settings=self.load("config-mover.json",preset="X3")
        self.assertEqual(settings.exit_rule,"X3")
        self.assertEqual(str(settings.x3_trail_fraction),"0.85")

    def test_preset_on_lane_a_is_refused(self):
        with self.assertRaisesRegex(ValueError,"exploratory_preset_requires_lane_b"):
            self.load("config.json",preset="partial-take-profit",exploratory=False)

    def test_unknown_preset_is_refused(self):
        with self.assertRaisesRegex(ValueError,"unregistered_exploratory_exit_preset"):
            self.load("config.json",preset="unregistered-stop")

    def test_registered_preset_does_not_raise_risk_ceiling(self):
        with self.assertRaises(SafetyError):
            self.load("config.json",preset="baseline",max_gross_loss_usd="1001")

    def test_selector_version_and_resolved_config_bytes_bind_namespace(self):
        config,limits,_=self.load("config.json",preset="baseline")
        raw=b'unchanged input bytes'
        original=config_digest(config,raw,limits=limits)
        config['resolved_exploratory_exit_preset']['registry_sha256']='f'*64
        self.assertNotEqual(config_digest(config,raw,limits=limits),original)

    def test_live_manifest_paths_are_refused_for_exploration(self):
        from exploration import validate_exploratory_paths
        config={'paper_lane':'B','evidence_class':'exploratory'}
        with self.assertRaisesRegex(ValueError,'exploratory_live_diagnostics_not_registered'):
            validate_exploratory_paths(config,'/var/tmp/exploratory/state','/var/tmp/exploratory/out.json',
                                       live_dir='/var/tmp/exploratory/live')
