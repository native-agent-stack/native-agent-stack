# Jev harness build evidence — 2026-10-15

The [decision](../../../docs/decisions/2026-10-15-jev-trading-harness-build.md)
and [implementation map](../../../blueprints/native-skill-practice/p1/JEV-TRADING.md)
define the scope. This record contains no scored inference, credentials or
public benchmark text.

| Artifact | Evidence class | Result |
| --- | --- | --- |
| `source-review.json` | source_review | Retained TypeSafe/model sources, private record names/paths and installed implementation sources; zero source network requests |
| `screen-inputs.json` | source_review | finBERT prefix/licence update, external comparison, rejected order-path integrations and proposed T0–T10 readiness inputs |
| `frozen-source-check.json` | local_integration | Five source pins, nine frozen id-list hashes, both nonempty date-subset hashes, counts and cluster diagnostics verified |
| `syn/receipt.json` and its three hashed outputs | SYN | COMPLETE, exit 0, 161 fake calls; both Jev versions, baseline rows, parity, canaries, metrics, cost and latency |
| `guard-mutants.json` | SYN | 108/108 mutants killed by named tests; live source bytes unchanged; initial 106/107, isolated correction and final accounting-delta rerun disclosed |
| `validation.json` | local_integration | Combined-fold fail-first cases, final suites, native SDK MockTransport and repository checks |

The SYN corpus consists entirely of invented bulletins. Its probabilities,
token counts and elapsed times are deterministic fixtures. The costs are
simulated. It proves request/response, scoring, decision and receipt plumbing
only. The native-model factories were exercised with test doubles; actual
weights, paid transports, GPU windows, masking audits and acquisitions were
not invoked.

Frozen public source bytes remain under the coordination root's
`trading-cc/probes/jev-case-sources-20261011/datasets/`. The harness takes
explicit paths and full SHA256 pins and refuses any mismatch. No source text
or full public dataset file is committed here.

`syn-before-final-audit/`, `syn-before-review-fold/`, both historical mutation
files and `validation-before-review-fold.json` retain earlier measurements.
They are superseded by the current `syn/`, mutations and validation. Historical
public projections omit private authority hashes and unsupported failure/source/
mutant hashes; their metadata declares the projection and their receipts hash
the published projection bytes. They are not claims about the current code.
Original provenance is retained privately under
`coordination/ns2604-coop/lanes/jev-harness-private-fold/ea96de7a-evidence-originals/`.
The original public commit is preserved; this normal-push correction does not
rewrite history. Current SYN input hashes resolve to the current source files,
including the adopted SDK transport source at the repository-relative path.

Tests and mutations used bubblewrap with live `/` read-only, a private
`/var/tmp`, fresh `/dev` and `/proc`, and `--unshare-net --die-with-parent`.
Scratch was removed per run. Failed/partial-run fixtures verified that their
journals and receipts existed and that existing artifacts survived before
test scratch was removed. No secret store, environment file or credential
configuration was read by the build.
