# Lane A session flags retain their account journal

The existing README's preferred same-ledger path is blocked by a raw config
file digest even when only session admission flags change. This follow-up
allows the three coordinated PRE/POST flags to change while binding every
other config value. Numeric risk, strategy and account history remain frozen.
It changes no deployed configuration and performs no broker operation.

Sources at NAS main dbe7a8da1bb497570471e2b9d0dcfe56bbdc56e9:
adaptive-paper/README.md:73-91 identifies the raw-hash refusal and preferred
frozen-field comparison; :147-149 prohibits resets to evade risk or orders;
runner.py:2548-2552,2577-2579 are the recovery/start digest refusals;
safety.py:509-511 enforces persisted RiskLimits independently.
The dated series-root ruling is sha256
981d2202da0e50b515a382dc65ff19ba7e1c3b42e28b807f7a2021aba24daebc.

The canonical comparison omits ONLY regular_session_only,
extended_hours_enabled and sessions.extended_hours. The ordinary loader still
validates these in lockstep and validates the actual session at each run.
Feed, universe, exits, duration, order/request/loss/drawdown caps and every
other session policy field remain bound. Rung changes still need their own
fresh-intended series; they cannot change the stored journal limits.

Each completed lane-A trial retains its raw config_sha256 for provenance and
adds frozen_trading_config_sha256 for the next continuity comparison. Legacy
journals lacking the new signature resolve the old raw digest ONLY against
retained nonsymlink shipped config bytes with that exact digest. Unknown
legacy configs stay refused; current RiskLimits alone cannot reconstruct
their old trading settings. This is conservative compatibility, not migration
by overwriting metadata or adopting another root.

Recovery accepts the same frozen envelope and persists the actual supplied
raw digest only through the existing final publication. Explicit lane-B
rotation remains on its existing effective digest/SQLite authority path.
Incomplete trials, cash drift, halt, loss and unresolved-order checks are
unchanged and exercised through the real runner main with synthetic port and
account observations.

Canonical JSON mechanism: official python/cpython v3.13.16 at
cbc944f4bc59639a444dd971c737788ba2283a91, Lib/json/__init__.py dumps
sort_keys/separators contract; SHA256 is the same standard-library primitive
already used by the runner's config provenance. No alternate risk engine,
credential reader or execution library is added.

Fail-before fixtures at the branch base reproduce session-only paper and
recovery refusing the raw config digest. The fixed fixtures preserve original
fee-window/cash baseline and durable request history. Changed risk/rung/stop/
universe still refuse, as do unfinished state, cash drift and a latched halt.
Synthetic fixtures are not paper acceptance or an observed account transition.
Tests/commands/exit codes are recorded in the staged lane report.

Follow-ups:
- A non-shipped legacy config needs its exact retained provenance before a
  changed-session reopen can be admitted; never infer its settings.
- Feed or other non-session changes remain frozen. Any broader comparison
  policy needs its own evidence and regression before admission.
- The dated independent-root series records remain today's operating path;
  this PR does not silently rewrite their sealed bindings.
