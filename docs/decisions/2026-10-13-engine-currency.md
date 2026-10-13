# Engine currency: Nautilus, Lumibot and the official Alpaca MCP

Date: 2026-10-13. Evidence: **source_review** and a local execution of the
existing currency producer. The selected NautilusTrader **2.0.0rc5** remains
unchanged. This record supplies changed-source inputs for the trading lane's
screen and acceptance; it establishes no new engine or broker acceptance.

## Frozen inputs and native result

The [context record](../../evidence/artifacts/engine-currency-20261013/context.json)
binds repository inputs to main `993cc890b3ff3fc95fa7cdba51edd726565f9ace` and
SHA256. They include the trading rules, north star, runtime target, layer
verdict/wave, saturation ledger, historical engine-trial preregistration and
the currency producer. Only repository, release and source metadata was read;
no market data was acquired or replayed.

The latest completed execution-broker and backtesting-engine sweeps are the
October 13 wave-1 returns, consumed at
[#1073, a0491701](https://github.com/native-agent-stack/native-agent-stack/tree/a049170124469c7cdbdff532135ea1fe46401b81/evidence/artifacts).
Their publication/ledger append is pending on this record's base. Context records
their complete survivor lists, relevant vote positions, hashes and reopening
triggers, alongside the older ledger survivors. This currency delta disposes
none of those survivors. In particular, it does not turn the Lumibot refutations
into acceptance or infer that an omitted earlier survivor has been settled.

The existing `github_freshness.py` fetched exactly three repositories, with
zero errors or partial errors. Its bounded release-list path observes rc6 even
though GitHub's stable `releases/latest` still returns Nautilus v1.231.0.
`build_manifest.build_trading_freshness` then computes the
[retained report](../../evidence/artifacts/engine-currency-20261013/trading-freshness.json)
from the [scoped inputs](../../evidence/artifacts/engine-currency-20261013/trading-pins.json)
and [metadata](../../evidence/artifacts/engine-currency-20261013/github-freshness.json).
No currency comparator was added or copied.

| Component | Compared baseline and its meaning | Observed release | Source commit at that release | Native report |
| --- | --- | --- | --- | --- |
| NautilusTrader | 2.0.0rc5, selected destination | v2.0.0rc6, published October 5 | `7b766f8825b2539c5b2ac1375e9d97b41c509edb` | behind |
| Lumibot | 4.6.11, reviewed candidate; no acceptance at that version | v4.6.18, published October 10 | `730d5608f3ee625f0a30dc15e8cc512205dd2a2b` | behind |
| alpaca-mcp-server | 2.3.2, dated official-source review; no adopted runtime pin | v2.4.0, published October 12 | `2a973a046607c42742bf141184b71f1990fa1809` | behind |

There are three release comparisons, not three installed-version mismatches.
The [release record](../../evidence/artifacts/engine-currency-20261013/upstream-releases.json)
retains full notes, exact tag-to-commit resolution, publication times, response
hashes and compare metadata. The [source index](../../evidence/artifacts/engine-currency-20261013/source-index.json)
binds selected files by commit, blob, size and SHA256; [excerpts](../../evidence/artifacts/engine-currency-20261013/source-excerpts.json)
retain the lines behind the material claims below. REST compare responses are
bounded: Nautilus responses reach 300 files, and rc5-to-rc6 returns 250 of 380
commits. They are not complete change inventories.

## Nautilus: keep the release and development paths distinct

The selected rc5 source is `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`.
The rc6 notes name risk-account routing, order modification limits, startup
fill reconciliation, refused/replayed fills and submission recovery changes.
These are relevant to numeric risk, restart and reconciliation, rather than
proof that the existing broker gate passes. At the exact rc6 source,
[live.md:95–103](https://github.com/nautechsystems/nautilus_trader/blob/7b766f8825b2539c5b2ac1375e9d97b41c509edb/docs/concepts/live.md#L95-L103)
documents shutdown errors for unresolved retained submissions;
[live.md:477–481](https://github.com/nautechsystems/nautilus_trader/blob/7b766f8825b2539c5b2ac1375e9d97b41c509edb/docs/concepts/live.md#L477-L481)
requires stream/query/reconciliation evidence to resolve an in-flight command.
A disconnect alone is insufficient.

The IBKR transport port is a separate source delta:

| Source | Rust workspace dependency |
| --- | --- |
| [rc5 Cargo.toml:344](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/Cargo.toml#L344) | `ibapi = "=3.3.0"` |
| [rc6 Cargo.toml:345](https://github.com/nautechsystems/nautilus_trader/blob/7b766f8825b2539c5b2ac1375e9d97b41c509edb/Cargo.toml#L345) | `ibapi = "=3.3.0"` |
| [frozen develop Cargo.toml:347](https://github.com/nautechsystems/nautilus_trader/blob/ca478e42f434d2ce185493f2bb42d112a88d1ffe/Cargo.toml#L347) | `ibapi = "=5.0.0"` |

[PR #5041](https://github.com/nautechsystems/nautilus_trader/pull/5041)
merged as `f81f951776b2868a681364ceebae239fab3eb206` on October 8, after rc6's
publication. Its body describes the transport port, account-code correction,
resubscription, sentinel-price filtering and restart-fill handling. References
to #5041 in rc6's release notes do not establish that the full port is in rc6.
The captured rc6-to-develop comparison is **diverged**, 174 ahead/66 behind;
develop must not be treated as a simple release superset. Also, the frozen
develop [IBKR guide:20](https://github.com/nautechsystems/nautilus_trader/blob/ca478e42f434d2ce185493f2bb42d112a88d1ffe/docs/integrations/interactive_brokers.md#L20)
still names `ibapi 4.0.1`, while its workspace pins 5.0.0. This source/doc
disagreement remains a qualification input, not a verified protocol guarantee.

**Re-pin trigger:** the trading layer screens an exact candidate against its
frozen requirement, resolves the documented transport/protocol disagreement,
then qualifies the artifact and native replay/risk/recovery path at that pin.
Use the vendor's release-wheel or documented source-build path and in-tree
tests. Reproduce required cash/fill semantics on the retained contracts; for an
IBKR pin, independently pass account routing, rejection, reconnect/resubscribe,
restart replay, cancellation and flat-state reconciliation in the authorized
paper lane. If a required fix is only on develop, bind the exact commit and
qualified artifact separately; no floating development install. The upstream
[installation guide:123–145](https://github.com/nautechsystems/nautilus_trader/blob/7b766f8825b2539c5b2ac1375e9d97b41c509edb/docs/getting_started/installation.md#L123-L145)
also distinguishes development wheels and discourages them for live trading.
The source-reviewed [equity adjustment gap](2026-10-10-layer15-nautilus-adjustment-claim.md)
and separate Alpaca boundary remain independent of this version comparison.

## Lumibot: the 4.6.18 lead does not erase the retained failed trial

The [v4.6.18 release](https://github.com/Lumiwealth/lumibot/releases/tag/v4.6.18)
names IBKR history/accounting qualification and exact option-pricing inputs.
The pinned [qualification record](https://github.com/Lumiwealth/lumibot/blob/730d5608f3ee625f0a30dc15e8cc512205dd2a2b/docs/investigations/2026-10-10_ibkr-routed-qualification.md)
describes bounded direct/routed history, completed-session lookbacks,
forming-minute quote/valuation leakage, ex-date dividends and artifact export.
Its lines 41–43 distinguish portable tests from private deployed integration.
These are upstream-reported measurements, not measurements performed here.

The source narrows applicability: the fast quote path in
[backtesting_broker.py:3698–3706,3813–3824](https://github.com/Lumiwealth/lumibot/blob/730d5608f3ee625f0a30dc15e8cc512205dd2a2b/lumibot/backtesting/backtesting_broker.py#L3698-L3706)
is specific to `InteractiveBrokersRESTBacktesting` and substitutes the open for
close-derived bid/ask while a minute forms. Native regression sources include
[the direct/routed 250-session and intraday replay tests](https://github.com/Lumiwealth/lumibot/blob/730d5608f3ee625f0a30dc15e8cc512205dd2a2b/tests/backtest/test_ibkr_frozen_replay.py#L81-L103)
and [the ex-date dividend check](https://github.com/Lumiwealth/lumibot/blob/730d5608f3ee625f0a30dc15e8cc512205dd2a2b/tests/test_stock_split_accounting.py#L487-L498).
Those tests were read, not run.

Our retained [Lumibot 4.6.1 trial](../../blueprints/us-equities/engine-trials/spy-one-zero-20260926/README.md)
failed 6 of the 29 frozen checks: same-decision-bar fills, causality and missing
distribution posting. It is not evidence about 4.6.11 or 4.6.18. The IBKR-specific
4.6.18 corrections do not by themselves prove that this Pandas/end-indexed-bar
failure is repaired. The successful 29-check ml4t comparison and the distinct
136-check Nautilus contract retain their original scopes.

**Re-pin trigger:** the comparator lane screens the release at its exact pin,
uses upstream's isolated install and relevant maintained tests, and reproduces
the demonstrated failure on the same retained bars, decision/submission clocks,
scorer and cash/dividend contract before measuring the candidate. A stronger
provider-specific test is useful alongside that contract, not as a silent
replacement. Historical comparator qualification and broker-specific paper
acceptance remain separate. No replacement of the selected engine follows from
the release's recency, notes or source tests.

## Alpaca MCP: optional interface currency, outside the order writer

[v2.4.0](https://github.com/alpacahq/alpaca-mcp-server/releases/tag/v2.4.0)
updates September/October API specifications and option stop orders. The source
diff from reviewed 2.3.2 changes 13 files across two commits. At the exact pin,
[overrides.py:258–270,337–338](https://github.com/alpacahq/alpaca-mcp-server/blob/2a973a046607c42742bf141184b71f1990fa1809/src/alpaca_mcp_server/overrides.py#L258-L270)
adds and forwards `stop_price`; the vendor's
[mock-transport tests:690–715](https://github.com/alpacahq/alpaca-mcp-server/blob/2a973a046607c42742bf141184b71f1990fa1809/tests/test_server_construction.py#L690-L715)
cover presence/omission with `stop_limit` and `gtc`.
The [README:497–502](https://github.com/alpacahq/alpaca-mcp-server/blob/2a973a046607c42742bf141184b71f1990fa1809/README.md#L497-L502)
explicitly marks locates unavailable in paper trading. This does not establish
our account's options entitlement or authorize an options/locate trial.

**Re-pin/adoption trigger:** a named MCP role must first pass the execution
layer's requirement screen. Use the official server's maintained install and
mock-transport/tool-discovery tests at that pin, explicit paper routing and a
restricted toolset. The vendor's
[tool-filter test:718–725](https://github.com/alpacahq/alpaca-mcp-server/blob/2a973a046607c42742bf141184b71f1990fa1809/tests/test_server_construction.py#L718-L725)
checks that the account toolset omits `place_stock_order`. Restriction needs its
own measured acceptance; paper defaults can be overridden in the
[server:113–118](https://github.com/alpacahq/alpaca-mcp-server/blob/2a973a046607c42742bf141184b71f1990fa1809/src/alpaca_mcp_server/server.py#L113-L118).
Keep broker write authority with the existing deterministic owned writer and
keep research processes free of broker credentials. A newer MCP server is not
a Nautilus Alpaca adapter or a replacement for `alpaca-py` acceptance.

## Verification and limits

The unchanged `tests.test_catalog_freshness_trading` module passes **49 tests**
under the idle CPU scope. Its existing rc6-vs-rc5 fixture, failure/cap handling
and report checks were already green before this evidence addition. No producer
defect was reproduced, so there is no new code correction or claimed new red/green
runtime test. The retained failed Lumibot trial is a future qualification input;
it was not rerun. No candidate package was installed and no upstream engine test,
broker session, paid data or model call ran.

Offline reproduction of the report uses the unchanged native function:

```python
import json
import sys
from pathlib import Path
sys.path.insert(0, "tools/sota-convergence")
import build_manifest
p = Path("evidence/artifacts/engine-currency-20261013")
pins = json.loads((p / "trading-pins.json").read_text())
metadata = json.loads((p / "github-freshness.json").read_text())
result = build_manifest.build_trading_freshness(
    {"taxonomy": {}, "layers": {}}, pins, metadata["repositories"], "2026-10-13")
assert json.dumps(result, indent=1) + "\n" == (p / "trading-freshness.json").read_text()
```

This dated record neither rewrites the current verdict/selection nor promotes a
source watch into adoption. A new upstream change reopens only its documented
delta; measured acceptance at a screened pin is what can justify a re-pin.
