# IBKR pacing publication boundary

The approved sanitized trading-cc **revision 2** projection is retained unchanged
at the canonical JSON, generator and verifier paths, replacing their revision 1
bytes. Its `revision.supersedes` block names the three superseded hashes;
revision 1 remains available in Git history. Its
`headline_numbers` entries identify the receipt run labels; the handbook cites
those entries and public field paths. Original broker receipts are private and
are not copied or read by this documentation change.

| Approved artifact | SHA256 |
| --- | --- |
| `ibkr-pacing-evidence-20261013.json` (v2 bytes) | `25ef71020a06e1781fac0360aa8b19c564d9d146b65ea3fc6b8cb0ab62ab0c15` |
| `generate_ibkr_pacing_evidence.py` (v2 bytes) | `f44b595a13cf87b4ad555427000c7937cc62452076f0a3380f13338127147619` |
| `verify_ibkr_pacing_evidence.py` (v2 bytes) | `cac1e764f429dc05575dfe8a692e74d4bcc04a8906e174e9e7b0178cf61494e3` |
| `README.md` | `7890700134ce668c24ff1047b8e798157a3ffa3fe996e0bf9dcc4f7af90e7c86` |
| `ADDENDUM-01.txt` | `bbbb4d0096d0cab5577050f1b2ba31348fbc6cf5a1969b251bcb35649963b7f6` |
| `ADDENDUM-02.txt` | `f1de0a311acc5bcd7d7eeddd51e7fef35196dcd76c4f878f1564424f4f834a9c` |
| `ADDENDUM-03.txt` | `4f0a0abb7f644ab148e0cfaeb618a405b3171b41862a75639251eacdd52637b5` |

The generator and verifier require private inputs. They are preserved as producer
methodology, not executed here. This change checks hashes, public-field
consistency and the pinned upstream cancel-path source; those checks do not
independently reproduce the broker measurements. The approved README also
describes producer audit/locator files that are outside this public subset.

## Revision 2 correction and regression evidence

[ADDENDUM-03.txt](ADDENDUM-03.txt) records both failing-first probes: revision 1
passed with a corrupted reconciliation headline and with rewritten missing-order
journals; revision 2 fails each corresponding check. The producer reports
82 passing checks and zero failures on the true revision 2 inputs. Those checks
derive the missing-order kinds from journal events and venue text, compare the
headline with recomputed counters, and check the third broker-count arithmetic.
The internal probe scripts and output are not included in this publication.

The 38 missing orders now split into **35 duplicate-order-ID refusals (103),
one cancel-target-not-found rejection (10147), and two never reaching the
adapter**. The third broker count, 10,313, is transcript-derived and checked
through arithmetic; it is not a new measurement by this documentation change.
Sources: JSON `/reconciliation`, `/revision` and `ADDENDUM-03.txt`.

The unchanged revision 1 README is historical methodology. Its 36-[103]
classification and its statement that the cross-client rule was undocumented
are superseded by revision 2 and [ADDENDUM-02.txt](ADDENDUM-02.txt), respectively.
All measured rates, latencies and test counts remain unchanged.

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
