# Lane A OVERNIGHT admission: qualify the existing port

Main `04f64a056cade587f804da60f6a94f7852f7624d` refuses an OVERNIGHT stage
even when its configuration opts into the overnight REST port. The existing
#1081 implementation at `ea0a51a6b2a485977d8aaf8e11dc0e93fe820a06` already
supplies the missing preflight branch, configuration validation and reduce-only
exit path. This draft stacks acceptance tests and a retained record on that
implementation; it does not fork or duplicate the owning lane's code.

The positive regression failed against main with
`regular_session_window_unavailable` and passed against the implementation
parent. The exact final positive test was also reproduced in a genuine detached
main worktree (one test, exit 1); its probe worktree was removed cleanly without
force. Negative controls retain refusal without the qualified overnight
flags; the default-policy and ordinary PRE/RTH/POST cases retain their original
preflight behavior. The overnight stage window ends at 04:00 ET, while a DAY
order's vendor expiry is 20:00 ET of the trade date. The must-end-flat rule
and existing configured flatten lead remain in force. Tests use synthetic
observations and the real preflight/configuration helpers.

The retained [validation record](../../evidence/artifacts/lane-a-overnight-acceptance-20261013/validation.json)
distinguishes the initial four-test main probe from the final six-test acceptance
module and lists the existing session, leverage and reduce-only exit controls.
The full session module has 34 optional native-runtime skips. The dispatch exit
control executes the committed method with protocol fixtures; it is not a
native runtime or broker acceptance result.

The [Alpaca 24/5 capture excerpt](../../evidence/artifacts/lane-a-overnight-acceptance-20261013/alpaca-245-trading-excerpt.md)
retains the vendor's LIMIT-only overnight contract, DAY carry to 20:00 ET,
and absence of day-trading buying power with a 2x maximum margin bound.
The CC's 2026-10-13 06:11Z P1-B ruling requires the existing risk-reducing exit
path to remain available after overnight entry admission closes. PRE entries
stay refused by the opted-in port; qualified reduce-only exits at 04:00:01 ET
remain covered by the parent regression, including oversell refusal.

The source mechanism is NautilusTrader 2.0.0rc5 at
`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`: the `TradingState.Reducing`
enum permits eligible reduce-only submissions, and
`crates/risk/src/engine/mod.rs` denies submissions that fail
`is_reducing_submission`. These pinned upstream source files were read directly.
No new dependency or account operation is introduced.

Production source, source-hash manifests, shipped CONTROL/RTH/PRE/POST
configurations and frozen trading bytes are unchanged relative to #1081.
The acceptance pack is invalidated by a change to the parent admission,
configuration or exit contracts and must be rerun after such a change.
An actual paper run remains a separate owning-lane acceptance action after
the parent and this draft have passed review. No deployment, service/unit
change, credential load or broker account call was performed here.
