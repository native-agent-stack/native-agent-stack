# Authored scope notes for native offline upstream captures

This document is not a receipt. Exact native command/cwd/rc/streams/times are
the masked derivatives under `masked/fold1/`, paired in `CAPTURES.md` with
named private captures. The tests are unchanged upstream suites using
synthetic/offline inputs, executed natively at the indicated source pins.
They are partial E2E evidence, not paper trading, role invocation or FINAL.

## ibflex — partial offline E2E

Pin: `dad9fd3c1edf133c4a4394cdc3c57bae82d466a3`, supported by retained
`evidence/artifacts/landscape-sweep-20260926/csingley-ibflex.json:7` and
the native `masked/fold1/ibflex-source-pin/stdout.txt:1`.
The vendor route is [Makefile:4,12](https://github.com/csingley/ibflex/blob/dad9fd3c1edf133c4a4394cdc3c57bae82d466a3/Makefile#L4)
and [.github/workflows/commit-ibflex.yml:21-28](https://github.com/csingley/ibflex/blob/dad9fd3c1edf133c4a4394cdc3c57bae82d466a3/.github/workflows/commit-ibflex.yml#L21-L28):
editable installation with web dependencies, development test tools, and pytest.

The corrected venv setup, installation and unchanged full pytest execution
have native rc0 at each corresponding `rc.txt:1`. The upstream result is
`64 passed` at `masked/fold1/ibflex-offline-tests/stdout.txt:2`; interpreter
version is separately native at `ibflex-python-version/stdout.txt:1`.
The parser suite does not settle the DISPUTED missing-execution-capability
question; its upstream README explicitly distinguishes report parsing from
programmatic trading (retained source review line32).

## Kumo — partial offline E2E

Pin: `cdc698c2db289c230b7ab3bc9133e78b0d5312e5`, supported by retained
`evidence/artifacts/landscape-sweep-20260926/falk-brauer-kumo-nautilus-alpaca-adapter.json:7`
and native `masked/fold1/kumo-source-pin/stdout.txt:1`.
The vendor route is [README.md:20-28](https://github.com/FALK-BRAUER/kumo-nautilus-alpaca-adapter/blob/cdc698c2db289c230b7ab3bc9133e78b0d5312e5/README.md#L20-L28):
`uv sync --all-extras` and `uv run pytest -q`. Captured commands add the
supported lock/offline flags without editing upstream sources or tests.
Those flags are verified against the installed tool at the captured0.12.22
pin: `masked/fold1/uv-sync-help/stdout.txt:10,46,182` and
`masked/fold1/uv-run-help/stdout.txt:53,204`. These are native CLI-help
source captures, not an assumption about an unavailable generated web page.
The source's [pyproject.toml:11-16](https://github.com/FALK-BRAUER/kumo-nautilus-alpaca-adapter/blob/cdc698c2db289c230b7ab3bc9133e78b0d5312e5/pyproject.toml#L11-L16)
requires Python3.13 and Nautilus1.229.0; this is not the recorded rc5 runtime.

Corrected native sync and unchanged full pytest execution have rc0 in
their `rc.txt:1`. Upstream result: `234 passed` at
`masked/fold1/kumo-offline-tests/stdout.txt:5`; interpreter and uv versions
are native outputs in `kumo-python-version/stdout.txt:1` and
`scratch-uv-version/stdout.txt:1`. Tests block INET socket connections in
[tests/conftest.py:9-19](https://github.com/FALK-BRAUER/kumo-nautilus-alpaca-adapter/blob/cdc698c2db289c230b7ab3bc9133e78b0d5312e5/tests/conftest.py#L9-L19).
Independent paper-account smoke remains absent; offline synthetic tests do
not supply it (the pinned README:15-17 states that boundary).

## Isolation and preserved failed setup

Both installs use only throwaway prefixes under the marked `<FOLD_SCRATCH>`.
Native argv shows `env -i` with scratch HOME/cache/tmp and no credential
variables. Test argv adds a fresh network namespace via
`unshare --user --map-current-user --net`. The installed util-linux2.41.3
`unshare(1)` (`--net`) creates a separate network namespace; the installed
Linux man-pages6.17 `network_namespaces(7)` DESCRIPTION documents isolated
network devices, protocol stacks and routing tables. See
[util-linux v2.41.3 unshare(1)](https://github.com/util-linux/util-linux/blob/v2.41.3/sys-utils/unshare.1.adoc)
and [Linux man-pages6.17 network_namespaces(7)](https://git.kernel.org/pub/scm/docs/man-pages/man-pages.git/tree/man/man7/network_namespaces.7?h=man-pages-6.17).
These captures run in that isolated namespace without a configured gateway.
ibflex at `dad9fd3c` has no suite-level network guard; its Flex client is only
mocked at [tests/test_client.py:61,96](https://github.com/csingley/ibflex/blob/dad9fd3c1edf133c4a4394cdc3c57bae82d466a3/tests/test_client.py#L61).
The external namespace supplies the network boundary for that suite.
All suite/setup/install jobs use idle-class systemd scope. No unit is enabled.
The existing closed trading runtime is not used for either suite.

`ibflex-venv` first selected an unavailable venv setup through the sanitized
PATH (rc1); `kumo-sync` first named an unavailable uv executable (rc127).
Those native failed command/stream captures are retained and published as
failed setup, not tests or passes. Corrected captures use the actual installed
Python/uv executables with scratch prefixes. No original raw byte was edited.
No host package or tool installation was performed.

## Named remaining suite gaps (author dispositions, not failed measurements)

| Survivor | Offline suite status / reason not run here | Named prerequisite, independent of paper windows |
| --- | --- | --- |
| ib_async | GAP-SAFE-OFFLINE-ENTRY: existing tests request a connection, account summary or what-if order; none run | Identify a supported bounded suite excluding those actions, or a separate authorized paper phase. Sources at pinab629f34: [conftest.py:16](https://github.com/ib-api-reloaded/ib_async/blob/ab629f34c1823ea4c1542f32f07377208a86bdfd/tests/conftest.py#L16), [test_requests.py:11,17,22](https://github.com/ib-api-reloaded/ib_async/blob/ab629f34c1823ea4c1542f32f07377208a86bdfd/tests/test_requests.py#L11), [test_contract.py:10](https://github.com/ib-api-reloaded/ib_async/blob/ab629f34c1823ea4c1542f32f07377208a86bdfd/tests/test_contract.py#L10). CI's separate static-analysis route is not represented as E2E |
| rust-ibapi | GAP-BOUNDED-BUILD: vendor cargo tests are known, but a fresh Rust/dependency build and review excluding live integration were not performed in this cheap Python-suite round | Separately budget a scratch Rust toolchain/dependency build and safe test target review. At pinbe449c84, [README.md:37-44](https://github.com/wboayue/rust-ibapi/blob/be449c84efd1b52e4a296751d3d6edba2ca53552/README.md#L37-L44) lists cargo tests; [Cargo.toml:2](https://github.com/wboayue/rust-ibapi/blob/be449c84efd1b52e4a296751d3d6edba2ca53552/Cargo.toml#L2) includes integration workspaces. No claim that offline tests need credentials |
| NautilusTrader | GAP-BOUNDED-BUILD: fresh full engine/Rust/Python suite at the carried develop snapshot was not performed in this round | Budget the pinned upstream build/test stack and a broker-free target review; do not borrow rc5 results for a different source commit. Retained source review `nautechsystems-nautilus-trader.json:7,13` records this survivor pin and the historical unexecuted comparison |
| nautilus_ibapi | GAP-ENTRYPOINT/ROLE: no independently reviewed bounded offline suite for the archived mirror was established here | Co-op resolves the DISPUTED abandoned/role question and names a vendor-supported offline target before a scratch run. Retained source review `nautechsystems-nautilus-ibapi.json:17,23,31` supplies archive and installation-guide context, not a suite result |
| IBC | GAP-ENTRYPOINT/ROLE: no safe bounded upstream unit target identified in the supplied retirement-source record | Resolve DISPUTED abandoned status and identify an offline target; do not substitute GUI/login automation. Retained source review `ibcalpha-ibc.json:17,23,31` supplies archive/retirement context |
| gnzsnz/ib-gateway-docker | GAP-SERVICE-START: reviewed vendor acceptance route is container startup/login, not an established cheap offline suite | Identify a supported credential-free static/unit target or separately authorize service acceptance. October1 layer review `execution-broker.json:732` records no adopted image pin; no container was started |
| extrange/ibkr-docker | GAP-SERVICE-START: source advertises containerized Gateway/TWS/auto-login, not a reviewed offline suite | Identify a credential-free upstream static/unit target or separately authorize service acceptance; no Docker or gateway start. Retained source review `extrange-ibkr-docker.json:27` supplies the role claim |

Short retained source-review names in the last table mean files under
`evidence/artifacts/landscape-sweep-20260926/`; the October1 layer-review
name means `evidence/artifacts/new-wsl-layer-reviews-20261001/execution-broker.json`.
Every NOT_RUN/GAP row is a scope decision with a reason, not a fabricated
suite result or proof that no offline suite exists. There is no paper-window
dependency for an actual offline target. No new comparison or winner follows.
