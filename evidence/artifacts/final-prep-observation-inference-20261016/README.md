# Observation-inference FINAL-wave preparation — 2026-10-16

This packet proposes **Collector Contrib 0.162.0, Prometheus 3.15.0 and Loki 3.7.8** as one reconciled run tuple. It preserves current selections while exposing older verdict pins and missing source identities. It changes no canonical pin, default, host installation, prior PR head or FINAL admission.

Three vendor release archives were extracted only into an owned scratch prefix. **The original Collector verification claim was wrong:** C10 hashed a partial file. The retained archives were subsequently verified by sequential C38 and an explicit all-three digest/timing check; this does not retroactively validate C10. Five fresh offline validations/tests C44–C48 exited zero; original scratch version calls C31–C33 remain unchanged. Their output is retained as **deterministically masked native captures**, with exact command/return-code envelopes. Full live-service E2E, production adoption, macOS execution and comparative A6 remain named gaps.

## Native evidence custody

[capture-index.json](capture-index.json) locates 57 native captures (36 original plus 21 fold captures): release/CI/tag responses, downloads/extractions/checksums, installed-PATH versions, fixtures, offline smokes and custody tests. This is a derived locator count. The actual native output is the 114 stdout/stderr files under [captures/](captures/), accompanied by 57 command envelopes. No generated summary stands in for a run.

- [capture_native.py](capture_native.py) runs exact argv with separate binary stdout/stderr file handles and records cwd, a deliberately minimal environment, timestamps and the actual return code privately. It does not combine, decode, rewrite or invent stream content. A timeout or launch failure is explicitly different from a returned exit code.
- [mask_capture.py](mask_capture.py) performs only explicit literal UTF-8 byte replacements, longest first, with marked placeholders `<CHECKOUT>`, `<SCRATCH>`, `<USER_HOME>`, `<LOCAL_HOST>`. It preserves all nonmatching bytes, including line endings. No line filtering, first-line projection, API-field selection or success template is applied to native output.
- The raw tree and private literal mapping stay outside the repository and are supplied to the co-op by name/path only. Public command envelopes exclude private raw hashes. Their SHA256 fields bind **published masked stream bytes only**.
- [test_capture_mask.py](test_capture_mask.py) supplies synthetic custody controls, not component E2E. The native test output is [17-custody-tests.stderr.txt](captures/17-custody-tests.stderr.txt): byte preservation, longest-match handling, invalid mapping refusal, real nonzero return code, duplicate-capture refusal, deterministic reproduction and tampered-raw refusal are exercised.
- **Private reproduction PASS received 2026-10-16.** The co-op's named MASKED-REPRO CHECK found all 108 derivatives byte-identical, all 72 stream hashes/byte counts matching, all 36 command metadata records matching raw, all 108 locators resolving and all 121 registry entries matching. It independently reran four masking-only tests; it did not rerun the three recorder-invoking tests, whose published log reproduced. This was byte-custody verification of the original 36 captures, not digest equality, timing correctness or two-family claim approval. Original captures, masker, recorder and custody tests remain unchanged. The co-op's expanded FOLD PRIVATE CHECK also passed on 2026-10-16: all 57 raw captures regenerated 171/171 published derivatives byte-identically, with no home/user tokens. Independently of the verifier, the co-op confirmed that C38 matches all three published archive digests and started after C04-C06 downloads finished; C10 still fails that check and its bytes remain preserved. The binding verifier passed for three archives, all five archive-binding tests passed, and all seven custody tests passed. Both private checks are cited by name only. Two-family claim review remains pending.

The earlier draft used real subprocess output but did not retain separate raw custody and had generated installation summaries and selected-line version projections. Those drafts were not committed or opened as a PR. They have been replaced by fresh native captures; no old summary was reconstructed as a raw file. The new claim-index JSON files are explicitly labelled as derived indexes rather than native output.

CPython owns the recording/masking primitives: [subprocess.run](https://docs.python.org/3.13/library/subprocess.html#subprocess.run), [bytes.replace](https://docs.python.org/3.13/library/stdtypes.html#bytes.replace) and [hashlib](https://docs.python.org/3.13/library/hashlib.html), official Python 3.13.16 documentation read 2026-10-16. The repository's existing `scripts/host_receipts.py:733-748` at base combines/decodes streams and does not retain private raw files, so it cannot supply this custody form unchanged. The new small wrapper keeps native streams separate; it does not replace candidate tests or a vendor installer.

## Four deliverables

| Deliverable | Status | Evidence |
| --- | --- | --- |
| F1 | PROPOSAL: exact run tuple and drift, each scalar tied to its source line | [F1-run-pin.json](F1-run-pin.json) |
| Upstream install and offline smoke | Native captured commands, scoped to scratch; full service E2E is GAP | [upstream-install-smoke.json](upstream-install-smoke.json), a claim index into native captures |
| F2 invocation | Eight native CLI calls; production workload/adoption is GAP | [F2-invoke.json](F2-invoke.json), a claim index into native captures |
| Six-angle record | Draft only; all ten rows derive INSUFFICIENT | [angle-record-draft.json](angle-record-draft.json) |
| Disputes and missing inputs | Explicit, pending co-op two-family adjudication | [adjudication-gaps.json](adjudication-gaps.json) |

The fresh checkout's base is public main `caa224140a2d04ba5f3d0ca320c487a75f9c9ea1`. The prior screen PR #1192 remains unchanged.

## F1 identity reconciliation

| Component | Canonical winner verdict | Canonical run / installed PATH | Proposed source commit |
| --- | --- | --- | --- |
| Collector Contrib | 0.161.0 | 0.162.0 | `ae8c507510f48f433ab47dd1c6b01a59d6c388b5` |
| Prometheus | 3.14.0 | 3.15.0 | `5241a27fe3c6983549fccc32f6e65917408c63cd` |
| Loki | 3.7.8 | 3.7.8 | `09e6ce2ff1bdc19763a10265b870c86f51c98655` |

F1 cites the exact version and commit fields in current-base final-stack, stack manifest, package qualification and clean-install plan. The installed PATH values come from full captured `--version` outputs ([14](captures/14-path-collector.stdout.txt), [15](captures/15-path-prometheus.stdout.txt), [16](captures/16-path-loki.stdout.txt), line 1 each). They do not establish running-service versions or activation state.

Collector's canonical run source commit is null. The retained package qualification and fresh tag-object response ([34-collector-tag-object.stdout.txt:11](captures/34-collector-tag-object.stdout.txt)) agree on the contrib commit. Distribution and core are distinct repositories: [distribution identity:11](captures/35-distribution-tag-object.stdout.txt) is `f6159a775dad1e21433c49bd8450673dd13ed4d3`; [core identity:11](captures/36-core-tag-object.stdout.txt) is `62cdad2ea133239380b44d20d84eb26e114779b6`. They are not interchangeable.

The plan's layer row at `docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:141` names the winner set, six survivors and two pin drifts; it adds no version. “Last committed package qualification” is scoped to the version-specific evidence referenced by the current stack; it is not an exhaustive claim over every later usage receipt. Existing holds are preserved ([base release-hold record:117](https://github.com/native-agent-stack/native-agent-stack/blob/caa224140a2d04ba5f3d0ca320c487a75f9c9ea1/docs/decisions/2026-10-04-2604-e2e-fix-wave.md#L117)). Prior 0.163.0 screening is cited in F1 at screen commit d4efff9d, row lines 3469–3470 and gap lines 3735–3736. F1 now also records each survivor's identity drift: canonical carry rows 7106–7136 contain no version/commit; the six draft pins come only from unmerged #1192 and are not selected runs.

## Scratch-only native checks

All installs and executions remain in `<SCRATCH>`, an owned throwaway prefix under /var/tmp. This is prefix isolation and a minimal process environment, not a claim of an OS security sandbox. No host-wide package manager, service enable, systemd unit, broker/account action, model call or live endpoint connection occurred.

[upstream-install-smoke.json](upstream-install-smoke.json) binds each official release asset's name, size, public digest and URL to exact captured-response lines. [10-archive-checksums.stdout.txt](captures/10-archive-checksums.stdout.txt):1 records the real **mismatching** partial Collector digest and is preserved as a failed verification attempt. Its command began before C04 completed. Only [38-archive-checksums-sequential.stdout.txt](captures/38-archive-checksums-sequential.stdout.txt):1–3 supports current equality with the vendor digests, checked by [38b verifier stdout](captures/38b-archive-binding-green.stdout.txt):1. Download/extraction command rc and full streams are independently captured; missing output is genuinely an empty native stream, not a generated success message.

| Operation | Native output or rc support | Boundary |
| --- | --- | --- |
| Collector upstream config validation | [44 command](captures/44-collector-upstream-config-bound.json), empty native streams | Upstream DryRun, no Collector run |
| Collector current committed config validation | [45 command](captures/45-collector-repository-config-bound.json), empty native streams | Syntax/component validation only |
| Prometheus shipped config check | [46 stdout](captures/46-prometheus-upstream-config-bound.stdout.txt) | No scrape or service query |
| Prometheus upstream rule fixture | [47 stdout](captures/47-prometheus-rule-test-bound.stdout.txt):1 | Native output says SUCCESS; data is synthetic |
| Loki upstream config check | [48 stderr](captures/48-loki-config-bound.stderr.txt):1 | VerifyConfig exits before server execution |
| Three native scratch versions | [31](captures/31-collector-version.stdout.txt), [32](captures/32-prometheus-version.stdout.txt), [33](captures/33-loki-version.stdout.txt):1 | Complete unfiltered native version output, masked only |

The **source-derived** fixture inventory is 5 groups, 22 PromQL cases and 4 alert cases, counted from [22-fixture-prometheus-tests.stdout.txt](captures/22-fixture-prometheus-tests.stdout.txt): groups start at 8, 100, 112, 123 and 164; case lists at 34, 104, 112, 128, 137 and 171. These are static source counts, **not assertion counts printed by promtool**. They are not an independent simulation of success.

Primary native mechanisms:
- [Collector validation:15-26](https://github.com/open-telemetry/opentelemetry-collector/blob/62cdad2ea133239380b44d20d84eb26e114779b6/otelcol/command_validate.go#L15-L26).
- [Official Collector distribution:35](https://github.com/open-telemetry/opentelemetry-collector-releases/blob/f6159a775dad1e21433c49bd8450673dd13ed4d3/distributions/otelcol-contrib/.goreleaser.yaml#L35).
- [Prometheus binary install:44](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/README.md#L44), [native rule-test command:6-13](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/docs/configuration/unit_testing_rules.md#L6-L13) and [upstream test fixture use:29](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/cmd/promtool/unittest_test.go#L29).
- [Loki binary install:43](https://github.com/grafana/loki/blob/09e6ce2ff1bdc19763a10265b870c86f51c98655/docs/sources/setup/install/local.md#L43), [verify/exit:89-110](https://github.com/grafana/loki/blob/09e6ce2ff1bdc19763a10265b870c86f51c98655/cmd/loki/main.go#L89-L110).

Full upstream build/test suites, filtered live ingestion, native task counters, persistence/restart and failure recovery were not run. Keep those gaps separate from the offline checks.

## Six-angle draft and carry reconciliation

[weight-statement.json](weight-statement.json) retains existing angle-convergence/2 weights stated before fresh assessment: A1 .20, A2 .20, A3 .15, A4 .15, A5 .20, A6 .10. Prior verdicts/screens were visible; this is disclosed re-verification. Published-evaluation availability is null, not false, so no A5 weight moves.

Every scored sign is a **PROPOSAL assessment for review**, not native output or a default. The three incumbents have scoped A1 support and mixed/partial A2; A3/A4/A5 and comparative A6 remain U. The six carried survivors and the supplementary Tempo role remain unscored. All ten rows derive INSUFFICIENT and `final_evidence` is empty.

Fresh source evidence retains disputes:
- [Collector CI:1833/1842](captures/07-collector-ci.stdout.txt) identifies build-and-test/failure at the exact tag; the complete response has 12 workflows, with 11 successes. Static config validation does not refute the failed build/test.
- [Prometheus CI:15/252/489](captures/08-prometheus-ci.stdout.txt) has three successful conclusions, which cover only this bounded engineering signal.
- [Loki CI:6/15 and 234/243](captures/09-loki-ci.stdout.txt) records two failures, LogQL Analyzer and Helm tagged release PR. Failure cause/relevance requires adjudication; status alone is no hard disqualifier.

[public-source-reads.json](public-source-reads.json) is an explicit field index into the **full native curl response captures**, never a replacement for those captures.

The repository's `lane_packets.py` was run on current main with foundation/registered receipts/manifest newcomers. [lane-packet-selection.json](lane-packet-selection.json) is labelled a derived projection of the three incumbents plus six current carried survivors. The generator emits catalog packets and did not include these six survivors in its candidate list; no new survey was dispatched. The packet-generation command's old native output was not retained under the new custody rule, so generation is a historical preparation observation, not a native receipt.

Both 2026-09-29 fit reads explicitly retained Tempo's prior comparison role while refuting its promotion ([returns:10969](https://github.com/native-agent-stack/native-agent-stack/blob/caa224140a2d04ba5f3d0ca320c487a75f9c9ea1/evidence/artifacts/landscape-sweep-20260929/returns.json#L10969), [:10989](https://github.com/native-agent-stack/native-agent-stack/blob/caa224140a2d04ba5f3d0ca320c487a75f9c9ea1/evidence/artifacts/landscape-sweep-20260929/returns.json#L10989)). A supplementary unscored row preserves that carry ambiguity for the co-op. It is not a discovered candidate or admitted comparison arm.

## Corrected archive claim and bound fixture inputs

The CC's named full read of head 5e5d94bb found that byte reproduction preserved a real mistake. [C10 metadata:25](captures/10-archive-checksums.json) starts at 06:22:54.231103Z, before [C04 completion:23](captures/04-download-collector.json) at 06:22:54.434075Z. C10's Collector digest differs from the official [C01 digest:2373](captures/01-collector-release.stdout.txt). A checksum command exiting zero only says it computed a digest.

[C38 metadata:25](captures/38-archive-checksums-sequential.json) records the new checksum start at 08:31:19.577016Z, after all three downloads finished. [verify_bindings.py](verify_bindings.py) compares all three native values with independent release-response digests and checks ordering; it does not trust the recorder's byte-hash match as artifact verification.

The full fail-first regression [C54 stderr:31–33](captures/54-binding-tests-red.stderr.txt) records five tests with one failure against the original C10 claim. The same suite then passes [C55 stderr:11–13](captures/55-binding-tests-green.stderr.txt) after the claim is rebound to C38. Tests also reject individual Collector, Prometheus and Loki checksum mismatches even when capture-envelope hashes are internally consistent, and reject early timing even if the digests match. C37's earlier auxiliary substring-test mistake and C37b's two-test red result remain preserved; C54/C55 are the complete regression evidence. These synthetic mutation controls are not candidate E2E results.

[fixture-bindings.json](fixture-bindings.json) binds the five actual scratch files read by the fresh C44/C45/C47/C48 smokes. Native before-read captures C39–C43 match upstream/repository source captures C21–C25; each published file hash binds its full masked file bytes. Native post-smoke `cmp --silent` C49–C53 confirms the actual files still equal their retained raw before-read bytes. The binding check verifies command identity, rc and source/read/smoke/compare ordering. No private raw-file hash is published.

The original C26/C27/C29/C30 input bytes were not captured at their run time and remain a **historical input-binding GAP**. The new captures support new smokes only; they do not reconstruct that missing history. C46 checks the shipped archive's Prometheus config; it is distinct from the five disputed fixture files.

Survivor licence citations now point to the actual SPDX scalar lines at d4efff9d (824/874/924/979/1259/1304); pin citations point to their commit fields (2252/2565/2889/3185/5045/5351), with separate screen-gap locators. No canonical survivor pin is invented.

## Review and gaps

The co-op checks masked reproduction privately, then dispatches both model families. This packet does not self-dispatch a model review or merge. The common brief, addenda 01–02 and owner addenda 25–26 are named only, without text or private fingerprints.

The task's no-live-service boundary prevents full service E2E and an actual native-runtime adoption window. They remain GAP with required future inputs in [adjudication-gaps.json](adjudication-gaps.json). No synthetic result or placeholder fills them.

Before a PR: validate capture hashes/locators, draft schema/derivation, privacy and scope; register each evidence file with the existing helper; run `python3 scripts/validate.py`; obtain the co-op reproduction PASS. The PR body records actual outcomes. Canonical landscape/angle/run files remain unchanged.
