# Authored survivor source-pin proposals (not run receipts)

Creation-base references are at1b633d861518fa0d299279b1cfaec11d0fb47f82.
The set comes from `catalogs/landscape/final-stack.json:9234-9279` and the
matching committed sweep in `catalogs/saturation/ledger.json:6776`. Source
review line6 identifies each repository, and line7 its reviewed commit.
Each full commit below is a PROPOSAL for that survivor's source snapshot,
not an admitted layer run pin or a winner. Shared proposal reason: preserve
the previously reviewed immutable source until co-op comparison/adjudication.
No current-version, package-to-Git, image-version or installed-version claim
is inferred from a source commit.

| Survivor | Proposed immutable source snapshot | Supporting recorded source value | Upstream reference |
| --- | --- | --- | --- |
| ib-api-reloaded/ib_async | `ab629f34c1823ea4c1542f32f07377208a86bdfd` | `evidence/artifacts/landscape-sweep-20260926/ib-api-reloaded-ib-async.json:6-7` | [primary source at pin](https://github.com/ib-api-reloaded/ib_async/blob/ab629f34c1823ea4c1542f32f07377208a86bdfd/README.md) |
| csingley/ibflex | `dad9fd3c1edf133c4a4394cdc3c57bae82d466a3` | `evidence/artifacts/landscape-sweep-20260926/csingley-ibflex.json:6-7` | [primary source at pin](https://github.com/csingley/ibflex/blob/dad9fd3c1edf133c4a4394cdc3c57bae82d466a3/README.rst) |
| wboayue/rust-ibapi | `be449c84efd1b52e4a296751d3d6edba2ca53552` | `evidence/artifacts/landscape-sweep-20260926/wboayue-rust-ibapi.json:6-7` | [primary source at pin](https://github.com/wboayue/rust-ibapi/blob/be449c84efd1b52e4a296751d3d6edba2ca53552/README.md) |
| nautechsystems/nautilus_ibapi | `0496bf2b66b65661f39e085e4c5c28b6e5ef87a3` | `evidence/artifacts/landscape-sweep-20260926/nautechsystems-nautilus-ibapi.json:6-7` | [primary source at pin](https://github.com/nautechsystems/nautilus_ibapi/blob/0496bf2b66b65661f39e085e4c5c28b6e5ef87a3/README.md) |
| gnzsnz/ib-gateway-docker | `8a22deaa6cab86f9ad5c86ff4f0d6efbef718f10` | `evidence/artifacts/landscape-sweep-20260926/gnzsnz-ib-gateway-docker.json:6-7` | [primary source at pin](https://github.com/gnzsnz/ib-gateway-docker/blob/8a22deaa6cab86f9ad5c86ff4f0d6efbef718f10/README.md) |
| IbcAlpha/IBC | `fc6d917d56715ebf79a39a10b5d77fd7b701d992` | `evidence/artifacts/landscape-sweep-20260926/ibcalpha-ibc.json:6-7` | [primary source at pin](https://github.com/IbcAlpha/IBC/blob/fc6d917d56715ebf79a39a10b5d77fd7b701d992/README.md) |
| extrange/ibkr-docker | `917c4de1d3b024dbea2eb7afcb8a30c8e3ae738c` | `evidence/artifacts/landscape-sweep-20260926/extrange-ibkr-docker.json:6-7` | [primary source at pin](https://github.com/extrange/ibkr-docker/blob/917c4de1d3b024dbea2eb7afcb8a30c8e3ae738c/README.md) |
| nautechsystems/nautilus_trader | `cd417b801942c9753f70024be11f078d940ccf99` | `evidence/artifacts/landscape-sweep-20260926/nautechsystems-nautilus-trader.json:6-7` | [primary source at pin](https://github.com/nautechsystems/nautilus_trader/blob/cd417b801942c9753f70024be11f078d940ccf99/README.md) |
| FALK-BRAUER/kumo-nautilus-alpaca-adapter | `cdc698c2db289c230b7ab3bc9133e78b0d5312e5` | `evidence/artifacts/landscape-sweep-20260926/falk-brauer-kumo-nautilus-alpaca-adapter.json:6-7` | [primary source at pin](https://github.com/FALK-BRAUER/kumo-nautilus-alpaca-adapter/blob/cdc698c2db289c230b7ab3bc9133e78b0d5312e5/README.md) |

All entries remain carried/unresolved. No snapshot is silently advanced.
This is source accounting, not a new survey or a completed comparison.
The dated review's claim fields, limitations and metadata remain dated;
The `abandoned`/`missing_capability` hard-disqualifier rule at
`catalogs/landscape/angles/README.md:46-47` must be adjudicated, not bypassed:
IBC's retirement/archive, nautilus_ibapi's archive, and ibflex's explicitly
non-trading role are DISPUTED hard-disqualifier questions in `angles.md`.
These source proposals do not decide those questions or select a winner.
