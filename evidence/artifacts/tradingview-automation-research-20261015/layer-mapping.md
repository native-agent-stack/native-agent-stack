# Proposed layer mapping

These are proposed crosswalk rows, not catalog changes. No catalog currently owns the complete TradingView automation requirement.

| Requested surface | Existing layer(s) | Role fit and named gap |
| --- | --- | --- |
| Pine strategies running inside TradingView | us-equities/backtesting-engine for simulation; research-factors-ml for strategy hypotheses | Native Pine v6 is the reference runtime. External transpilers are a different role. GAP-TAXONOMY and GAP-APP-CONTROL cover platform orchestration. Emulator state is not broker state. |
| Alerts/webhooks to broker bridge | us-equities/execution-broker; market-data-reference for data rights/provenance | Notification transport exists, but current terms exclude automated order use. No qualified vendor-maintained bridge with a deterministic governor and manifest was established. GAP-RIGHTS, GAP-BRIDGE, GAP-MANIFEST. |
| MCP TradingView control tied to positions | foundation/mcp-surfaces for protocol/client configuration; market-data-reference for reads; execution-broker owns any later authoritative paper state | Official MCP is a narrow attended research surface. Generic mcporter/Inspector acceptance does not qualify any TradingView server. Pine/chart control and positions binding remain GAP-APP-CONTROL and GAP-MANIFEST. |
| Current strategy templates | research-factors-ml for hypotheses; backtesting-engine for native semantic checks | Official v6 examples and visible native built-ins provide source controls. pine-oracle supplies authored recipes but bundles vendor-derived docs; pine-utils has no default-branch change since 2019. No candidate establishes SOTA US-equities alpha. GAP-TEMPLATES. |
| Fine-tuning strategy parameters | research-factors-ml with backtesting-engine validation | Freeze symbol universe, as-known data, cost assumptions and untouched OOS protocol before parameter search. No optimization run or fresh holdout claim. GAP-TUNING. |
| Fine-tuning model weights | research-factors-ml; foundation runtime/model governance only if a specific model task is later admitted | No licensed training corpus, baseline failure, eligible model/recipe or task evaluation is established. General model tuning is not a Pine feature and cannot be placed in numeric/risk/order state. GAP-TUNING. |

Pine `strategy.risk.*` is documented emulator risk logic. It is useful as a native semantic reference, but it cannot govern broker-authoritative positions, reconnect state or external orders. A watchlist is also not a positions manifest.

The observer proposal binds only a read-only projection of a **synthetic** manifest to human-displayed symbol context. Binding real broker state, reconciliation and any deterministic paper risk governor requires independent broker-lane acceptance. No governor code or order payload is created here.
