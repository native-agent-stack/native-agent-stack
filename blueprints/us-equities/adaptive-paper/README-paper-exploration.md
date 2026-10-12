# Exploratory paper runs

Owner direction, relayed by the CC on 2026-10-10 at 18:39 UTC:
They authorized paper and sim exploration without approval or qualification
prerequisites, covering all factors and leverage modes, including aggressive
presets. The direction is for exploratory paper and simulation runs to cover
every registered preset and the `leverage-schedule-v1-20260922` rungs: 1×, 2×
and 4× intraday, with overnight exposure capped at 2×. That coverage is not in
place yet; [Remaining execution work](#remaining-execution-work) lists what
still blocks it. The frozen qualification trials and their retained records
under `trials/` stay frozen, and `scheduled_trial.sh` still supplies both
proofs. Heavy simulations run one at a time, paced to the host's capacity: none
starts while the host is low on available memory.

`runner.py paper` can start without `--gate-result` and `--snapshot`.
Supplying either argument requests qualification validation, so both must then
be supplied and the existing status, snapshot hash, row count and check
validation applies. The paper receipt's `preflight` block records
`promotion_gate`: `validated` when either argument requested validation and
`not_supplied` when neither was given. This follows the mover runner's existing
optional-proof behavior and marker. The `preflight` and `recover` commands
retain their existing behavior and add no marker.

Startup readiness remains separate from qualification. `validate_preflight`
still checks account readiness, cash/equity, broker margin entitlement,
session/window availability, flat startup, asset tradability and benchmark
freshness. Account locking, reconciliation, request budgets, deterministic risk
limits, fee/cash accounting and durable trial state continue through the same
code paths.

Measured broker-paper acceptance for this change is **NOT_RUN**. CLI tests use
fixture credentials and a synthetic broker observation and stop before native
execution. They establish optional qualification wiring and continued account
readiness checks.

## Remaining execution work

- The explicit configuration pair `paper_lane: "B"` and
  `evidence_class: "exploratory"` selects the same-account exploratory path.
  Use one stable `<state>/exploratory/account-state` root for baseline and mover
  trials; both share its account journal. Finished, flat trials can rotate
  configurations only after fee/cash reconciliation, with effective-config
  namespaces registered in the same ledger. Lane A and recovery stay frozen.
  Broker-paper acceptance for rotation is **NOT_RUN**; focused CLI/journal
  tests are synthetic evidence, not a verified live account alias.
- `exploratory_exit_preset` selects a versioned candidate in
  `exploratory-exit-presets.json`. Mover X1-X4/chain presets are the first paper
  target; their numeric parameters use existing constants, not historical
  selection. Check (d)'s existing RiskLimits ceilings stay enforced. See the
  [rotation and exit decision](../../../docs/decisions/2026-10-12-exploratory-account-rotation-and-exits.md)
  for namespace, labels, state isolation and recovery rules.
- The bounded source review of main at `03a986ed` and T22 at `a9e4eeb7` found
  no production paper dispatch caller for T22's factor/cohort strategies. T22
  documents that it supplies no paper command. Its native synthetic corpus
  receipts measure engineering behavior; broker-paper execution, historical
  performance and empirical preset refits remain unmeasured. Each future refit
  must have appropriate results and a new preset version.

## Sources and regression evidence

Mechanism references are pinned to native-agent-stack main
`03a986ed637349403658f23da694c1833527819d`:

- [mover_runner.py:703](https://github.com/seathatflowsinourveins/native-agent-stack/blob/03a986ed637349403658f23da694c1833527819d/blueprints/us-equities/adaptive-paper/mover_runner.py#L703)
  selects promotion validation only when either optional proof path is supplied;
  [mover_runner.py:704](https://github.com/seathatflowsinourveins/native-agent-stack/blob/03a986ed637349403658f23da694c1833527819d/blueprints/us-equities/adaptive-paper/mover_runner.py#L704)
  records that selection as the preflight summary's `promotion_gate` marker.
- [runner.py:2310](https://github.com/seathatflowsinourveins/native-agent-stack/blob/03a986ed637349403658f23da694c1833527819d/blueprints/us-equities/adaptive-paper/runner.py#L2310)
  shows the prior unconditional paper selection corrected here;
  [runner.py:661](https://github.com/seathatflowsinourveins/native-agent-stack/blob/03a986ed637349403658f23da694c1833527819d/blueprints/us-equities/adaptive-paper/runner.py#L661)
  keeps qualification dispatch separate from ordinary readiness checks.
- [runner.py:2434](https://github.com/seathatflowsinourveins/native-agent-stack/blob/03a986ed637349403658f23da694c1833527819d/blueprints/us-equities/adaptive-paper/runner.py#L2434)
  binds next-trial configuration and the following fee/cash continuity checks.
- [T22 README.md:54](https://github.com/seathatflowsinourveins/native-agent-stack/blob/a9e4eeb7f5ffc4cc1ce67b22746225684a8859ae/blueprints/us-equities/strategies/README.md#L54)
  records the absent paper command at that strategy source pin.

`tests/test_adaptive_paper_runner.py::MainCommandGateWiring` drives the public
CLI. The no-proof test failed first with `promotion_gate_missing`. Its
`promotion_gate` assertions failed first against the previous runner.py, with
`None != 'not_supplied'` for both no-proof tests and `None != 'validated'` for
the valid complete proof. The suite also covers a blocked account without
proof, either proof argument alone, invalid complete proofs and unchanged
recovery and preflight behavior; recovery adds no marker. Run the touched module with the installed combined native
runtime: `python -B -m unittest tests.test_adaptive_paper_runner -v`.
