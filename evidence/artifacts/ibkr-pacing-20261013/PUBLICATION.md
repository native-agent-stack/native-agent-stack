# IBKR pacing publication boundary

The approved sanitized trading-cc projection is retained unchanged. Its
`headline_numbers` entries identify the receipt run labels; the handbook cites
those entries and public field paths. Original broker receipts are private and
are not copied or read by this documentation change.

| Approved artifact | SHA256 |
| --- | --- |
| `ibkr-pacing-evidence-20261013.json` | `b492f42d335370e22f4349bf43db54f1adf4c77921b36a28300159b08c8e11fa` |
| `generate_ibkr_pacing_evidence.py` | `56463b2622501446a9a1640c6d3065920dbd449a622457ea61f392ce6166c5a1` |
| `verify_ibkr_pacing_evidence.py` | `0e9fb1376a59e34cf1e3b6ba2fea30d89aad5e09db28de0b4d59792a41207468` |
| `README.md` | `7890700134ce668c24ff1047b8e798157a3ffa3fe996e0bf9dcc4f7af90e7c86` |
| `ADDENDUM-01.txt` | `bbbb4d0096d0cab5577050f1b2ba31348fbc6cf5a1969b251bcb35649963b7f6` |

The generator and verifier require private inputs. They are preserved as producer
methodology, not executed here. This change checks hashes, public-field
consistency and the pinned upstream cancel-path source; those checks do not
independently reproduce the broker measurements. The approved README also
describes producer audit/locator files that are outside this public subset.

## Official source captures

These unmodified Markdown responses were checked on 2026-10-13. They are current
vendor documentation, with no version tag advertised in the captured bytes.

| Capture | Official source | SHA256 |
| --- | --- | --- |
| `pacing-introduction.md` | <https://www.interactivebrokers.com/docs/tws-api/doc/pacing-limitations/introduction.md> | `f85d35eccd35c267ff7cba983d057082ddb0936490a988122c93715e00641d2d` |
| `pacing-behavior.md` | <https://www.interactivebrokers.com/docs/tws-api/doc/pacing-limitations/pacing-behavior.md> | `608161d8d9ddfcdfba5d02a931fb5e082ae7c8a821a8d34851bbc4454c506d54` |
| `small-bars.md` | <https://www.interactivebrokers.com/docs/tws-api/doc/market-data-historical/historical-data-limitations/pacing-violations-for-small-bars-30-secs-or-less.md> | `fa12f6d99bd60939f181e451ecd79018ba6bdcdf9b77c26a21ec7cc43d6c27eb` |

The official legacy order-submission page was checked on 2026-10-13 for its
explicit `reqAllOpenOrders` rule: subsequent order IDs must exceed the IDs
returned by that request. It is cited only for that rule, not for current pacing
numbers: <https://interactivebrokers.github.io/tws-api/order_submission.html>.

The measured adapter source is `nautechsystems/nautilus_trader` at
`01ced2a3e7b7d25ae7b2e5c0c077bcc46192eb25`,
`crates/adapters/interactive_brokers/src/execution/core.rs:381,2387,2417,2429,2624,2637`.
It differs from the selected engine's rc5 pin. No engine re-pin, adapter patch,
broker replay or new operational acceptance is made by this publication.
