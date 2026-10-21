# Layer-resolution protocol re-verification

Base: `8053f14e7e0817d2502dff2bb284bfb7e1b0152f`. Branch: `codex/tradingview-automation-research-20261015`. Re-verified on 2026-10-15.

The direction reference supplied by the co-op was checked by SHA256 only: `4dfcb47245607bd3b3fb53bbdd49a561b1b157beccf02f9309623b23ffa2ad82`. No direction text is reproduced. The co-op protocol was read at `~/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/tv-automation.protocol-20261015T1957Z.md`. Its factual assertions are independently checked below, with one cumulative-survivor addition and a bounded qualification of the pending-sweep assertion.

## Step 1 — verdicts, evidence and wave

Read repository/trading rules, the layer-resolution decision, the trading architecture and architecture-source README, the sweep recipe and retained-return contract before discovery. There are 20 foundation layers and 12 us-equities layers; the latter also has four domain rows. Inspection of their identifiers and requirements found no TradingView/charting-platform automation layer. The proposed identifier `tradingview-automation-gap` is an artifact scope only.

The only indexed verdict wave is `20260922`, from `catalogs/sota-convergence/layer-verdict-waves.json`. Its verdict file hash reproduces `2fef6da7468a8e97a319fdc6f75f73374cd34b412bf93de90fd0c2a7504159de`. The relevant catalog rows, embedded evidence references and verdicts agree:

| Catalog/layer | Verdict | Winners | Open gaps |
| --- | --- | --- | ---: |
| us-equities/market-data-reference | recorded | alpaca-py, EdgarTools, exchange_calendars | 19 |
| us-equities/backtesting-engine | recorded | NautilusTrader, LEAN | 12 |
| us-equities/execution-broker | pending_lanes | none | 1 |
| us-equities/research-factors-ml | recorded | skfolio, EdgarTools | 16 |
| foundation/mcp-surfaces | recorded | mcporter, MCP Inspector | 14 |

The market-data row carries atilaahmettaner/tradingview-mcp in alternatives. Catalog selections are not current-host runtime acceptance or an automation permission. Original engine/broker selections remain the trading lane's responsibility.

## Step 2 — latest sweeps and cumulative adjudication

Read all six ledger rows (including two stopped attempts), the completed manifest references, retained discovery/votes/failures, and final-stack survivor summaries. Exact source hashes are in `protocol-inputs.json`.

| Layer | Latest covering sweep / retained returns | Latest survived | Reopen/failure |
| --- | --- | ---: | --- |
| backtesting-engine | landscape-sweep-20261009-pine; evidence/artifacts/landscape-sweep-20261009-pine/returns.json | 7 of 15; 8 refuted | No reopen in this sweep; final-stack reopened |
| market-data-reference | landscape-sweep-20260926; evidence/artifacts/landscape-sweep-20260926/returns.json | 4 | retained_failure |
| execution-broker | landscape-sweep-20260926; same returns | 9 | retained_failure; final-stack no-winner |
| research-factors-ml | landscape-sweep-20260926; same returns | 4 | retained_failure and pin_moved |
| mcp-surfaces | landscape-sweep-20260929; evidence/artifacts/landscape-sweep-20260929/returns.json | 0 of 8 | No reopen in latest row; final-stack remains reopened |

The seven Pine survivors are LuxAlgo/PineTS, pineforge-4pass/pineforge-codegen-oss, PyneSys/pynecore, elbakramer/pynescript, folknor/pine-oracle, s7cret/backtest_engine and arose26/pinescript-langium. Their source reviews were read and their capability/license evidence re-fetched at the retained pins. All seven remain unresolved **for backtesting-engine**. This PR evaluates only the TradingView automation/template role. pine-oracle's current head also moved; that change is named in the proposed row alongside its original pin.

Market-data survivors are databento/databento-python, massive-com/client-python, man-group/arcticdb and hydrosquall/tiingo-python. Execution survivors are ib-api-reloaded/ib_async, csingley/ibflex, wboayue/rust-ibapi, nautechsystems/nautilus_ibapi, gnzsnz/ib-gateway-docker, ibcalpha/ibc, extrange/ibkr-docker, nautechsystems/nautilus_trader and falk-brauer/kumo-nautilus-alpaca-adapter. These remain outside this delta.

**Cumulative correction:** the four latest research-factors survivors (linearmodels, Kronos, Toto and EXAONE-Forecast) do not exhaust that layer. LightGBM survives from 2026-09-23 and is still present in final-stack's cumulative set, making five. RD-Agent has a later substantive fit refutation. The prior MCP survivors mcpc and conformance have later substantive September 29 votes; their omission is not used as an adjudication.

The September 26 failures include capped searches, a critic cap, and missing GPT discovery for research-factors-ml and execution-broker. This review found no missing facts/Claude-fit/GPT-fit member among the retained vote rows of the five touched layers. Missing discovery still limits coverage. The October 3 GPT fit re-vote is retained and read: its nine foundation layers do **not** include these five, and it does not supersede their latest sweeps.

The retained manifests/returns found in this checkout supply no additional completed sweep covering these five layers that awaits ledger append. This verifies repository-visible evidence at the base; it does not assert that unpublished work in other sessions cannot exist. No older row is substituted for a missing newer result.

Carried identity checks:

| Co-op assertion | Re-verified source |
| --- | --- |
| Both MCP repositories are carried public stars | coverage.json /stars/37 and /stars/302 |
| Grand-catalog row 564 carries tradingview-mcp under backtesting-engine | grand-catalog-20261008.json /rows/564, atilaahmettaner identity, PENDING / documentary |
| TradingView-API and TradingView-Screener have cc-starred-absent leads | Corresponding grand-catalog market-data source occurrences; these are discovery provenance, not accepted implementations |
| Screener has an OUT-OF-SCOPE disposition | catalogs/convergence-practice/starred-convergence-20261010.json; metadata_review, financial screening/data-access role; protected KEEP is a retention decision, not adoption |

The grand catalog also contains market-data WATCH rows for the two MCP identities and TradingView-API. Those narrower historical dispositions are preserved rather than silently overwritten.

## Step 3 — bounded next action

Map the five surfaces, adjudicate the four identities and seven Pine survivors for this role, and fill only the missing native/vendor automation evidence. Review public TradingView Pine/alerts/MCP/charting docs, official Alpaca/IBKR sources and narrowly relevant MCP/template alternatives. Do not re-run the engine, data, broker, factor or foundation MCP competitions.

The result is a source-review proposal and a named paired observer comparison. No installs, sign-ins, keyed calls, candidate tests, order path, catalog/ledger/research-state edits or live action were authorized or performed. The layer stays open for a separate Claude-family run; this artifact does not register a terminal state.
