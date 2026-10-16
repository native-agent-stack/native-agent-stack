# Review corrections for the token-efficiency preparation

The private review `MICRO-full-f7b24d2a.md` requested one fold. This record maps
each correction to public source and native output. The private record
“#1221 FOLD PRIVATE CHECK PASS, 2026-10-16” confirms all 23 derivatives regenerate
byte-identical, staged captures equal the reviewed files, the RTK digest sequence
meets the required ordering, and all 11 synthetic controls pass. The co-op
released one normal fold commit and push, followed by both families' micro reviews.

| Finding | Correction and evidence |
| --- | --- |
| P1: packet presented as generator output after truncating receipts and renaming `pin` | The [native generator command](captures/lane-packet-generation.typescript):1-5 runs at the captured base commit. [The entire layer output](generator-token-efficiency.json) is retained unchanged, with native `cmp` and published-file hashes at [packet-output-binding](captures/packet-output-binding.typescript):1-5. [project_packet.py](project_packet.py):24 preserves each selected dictionary exactly, including 11/22/27 receipts and `pin`. The regression fails on the earlier packet ([red](captures/packet-regression-before.typescript):22,24), then all 11 projection/masking tests pass ([green](captures/packet-projection-tests.typescript):16,18,20). Producer mechanisms: `tools/sota-convergence/lane_packets.py:299-313,614-644` at `caa224140a2d04ba5f3d0ca320c487a75f9c9ea1`. |
| P2a: exported test sources were not bound to pins | [source-export-bindings](captures/source-export-bindings.typescript):1-12 uses pinned `git archive` plus recursive `diff` to check all RTK/Headroom/ccusage source paths/bytes (607/2573/501), and all copied Headroom test files. The fresh [Headroom test](captures/headroom-ccr-tests.typescript):1, [benchmark](captures/headroom-benchmark.typescript):1 and [ccusage test](captures/ccusage-node-tests.typescript):1 commands bind those sources read-only. ccusage's 34-test target executes the source tree; package verification is limited to its separate version/offline-fixture smokes. |
| P2b: unsupported maintenance-policy exception | Klavis A1 now preserves the historical negative maintenance finding, with `returns.json:7481` and `converged-candidates-only.md:81` at the base commit. Missing fit returns keep adjudication incomplete; they do not authorize a trial or supersede the maintenance rejection. No claim about current upstream maintenance is introduced. |
| P3: host-home scope | README and execution scope name both read-only mise toolchain mounts under `<host-home>`; they no longer claim the mounts contain no host-home paths. Exact mounts remain in each bwrap header. |
| P3: angle placement | New installations, tests and lexical/fixture smokes appear only in A1. A2 has a separate evidence gap. A6 retains historical outcome leads and comparative gaps with no new smoke references, following `angle-records-final-check.md:240-241` at the base commit. |
| P3: placeholder-validation test | `test_mask_capture.py:test_private_prefix_requires_marked_lowercase_placeholder` exercises six invalid prefix/placeholder inputs; the new control passes in [the native 11-test run](captures/packet-projection-tests.typescript):11,16,18. The masker implementation is unchanged. |
| Download digest equality and ordering | The unchanged pinned RTK installer is rerun with `sh -x`. [rtk-install](captures/rtk-install.typescript):47,51 completes the artifact/checksum downloads; :58 shows the published EXPECTED; hashing begins at :61; :63 shows matching ACTUAL; :64 is the equality guard; :90 reports version and :104 records rc 0. Upstream `install.sh:99-128` at `e001f773f80b22b7dc4c7a79521b30e35aaef026` defines that sequence. |

These changes replace the initial RTK installation and three source-test/benchmark
derivatives. Their original raw captures remain private and their previously
published bytes remain in the earlier commit. Five new derivatives retain
generator, output-binding, projection/regression and source-binding custody.
There are 23 current transcripts: 21 rc 0, the deliberate pre-fix regression
rc 1, and the deliberate RTK exit-control rc 7.

The candidate test/benchmark inputs remain **SIMULATION**. These corrections
do not close macOS, production adoption, complete attempt/child accounting,
Headroom native detector/proxy/MCP, or comparative task-quality/provider-use gaps.
They do not change a catalog, an angle record, a default, or FINAL admission.
