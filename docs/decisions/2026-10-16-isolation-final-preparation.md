# Foundation/isolation: FINAL preparation, with named gaps

Status: **preparation only**. The layer stays reopened and FINAL admission stays
closed. This record prepares the existing winner pair and the two carried
survivors for independent review; it changes no catalog, default or gate.
The source inventory is main at
`caa224140a2d04ba5f3d0ca320c487a75f9c9ea1`, accessed 2026-10-16.

The four deliverables are retained in
[`preparation.json`](../../evidence/artifacts/final-prep-isolation-20261016/preparation.json):
F1 pin reconciliation, an upstream-install/CLI-smoke receipt for each proposed
run pin, F2 native command/output evidence, and a schema-valid six-angle draft.
The draft remains outside the operational angle-record directory.

## F1: reconcile the existing run pins

Propose **Worktrunk 0.80.0 at `b49ca7eea9b03145791a5b94eccaf9c59412ed37`**
and **sandbox-runtime 0.0.79 at `d9aac2098351ca17f3743fbaf6ecbd0051b7e00e`**.
These are the existing main run pins and match fresh installed-version reads.
This is a reconciliation proposal, not a newer-release survey or a rewrite of
sealed historical verdicts.

The public release/tag reads resolve the stated commits. The
[`distribution readback`](../../evidence/artifacts/final-prep-isolation-20261016/distribution-readback.json)
also verifies the npm tarball against its public SHA-512 integrity value and
confirms that the vendor-installed Worktrunk binary matches the separately
checksum-verified release binary. npm metadata provides no `gitHead`; release
version/tag agreement is not an independent source-to-build attestation.

All file:line locators below refer to the source commit above. The machine
record retains their values, historical receipt commit IDs and drift notes.

| Pin source | Worktrunk | sandbox-runtime |
| --- | --- | --- |
| `catalogs/landscape/final-stack.json` run rows | `:11392`, 0.80.0 + source commit | `:11213`, 0.0.79 + source commit |
| Same file, isolation verdict rows | `:6263`, 0.79.0; `pin_drift: differs` | `:6286`, 0.0.77; `pin_drift: differs` |
| `manifests/stack.json` run-pin records | `:1071`, version; `:1095`, source commit | `:869`, version; `:888`, source commit |
| `catalogs/landscape/foundation.json` winners | `:1089`, historical 0.79.0 | `:1110`, historical 0.0.77 |
| `docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:137` | Shared layer row records two drifts and the winner pair; it contains no separate version pin | Same row |
| `adoption/new-wsl-profile.json` selected release | `:807`, 0.80.0 | `:750`, 0.0.79 |
| Last direct native receipt | `evidence/receipts/worktrunk-0800-qualification-20261003.json:19`, 0.80.0, previously list-only | `evidence/receipts/native-sandbox-codex-binding-20261008.json:19`, 0.0.79, imported echo/version binding |
| Fresh read-only installed version | `wt --version`: `wt v0.80.0`, exit 0 | `srt --version`: `0.0.79`, exit 0 |

Additional drift remains explicit. The Worktrunk new-install profile's
historical observed-host sentence at `:843` still names 0.79.0 and does not
qualify its unrun cargo suite. The older sandbox filesystem receipt has no
version; the network receipt names 0.0.77. Neither becomes 0.0.79 evidence by
updating a pin. The later `srt-source-citations-20261008.json` is a reference
repair, not a newer native execution. These historical records retain their
bytes and scopes.

## E2E and F2: fresh native execution at the proposed pins

Both installations used owned scratch prefixes under `/var/tmp`. Worktrunk's
official v0.80.0 release installer ran in its supported
`WORKTRUNK_UNMANAGED_INSTALL` mode, which disables PATH modification and updater
installation. sandbox-runtime used upstream's npm global-install form with an
explicit owned prefix/cache and separate empty scratch configuration paths.
No host-wide install, shell integration, credential, service or account change
was performed.

| Native operation | Measured result | Evidence boundary |
| --- | --- | --- |
| Worktrunk release install and version | Both exit 0; `wt v0.80.0` | Vendor installer, followed by the supported CLI |
| Worktrunk create/list/remove | All exit 0; 1 → 2 → 1 worktrees; final Git status clean | One-commit owned Git fixture, hooks disabled, no remote |
| sandbox-runtime npm install and version | Both exit 0; `0.0.79` | Vendor npm package in an isolated prefix |
| sandbox-runtime documented CLI echo | Exit 0; `isolation-native-smoke` | Native invocation through explicit settings |
| Additional permitted-write control | Exit 0; seven bytes written | Synthetic one-file control through the real CLI |
| Additional denied-write control | Exit 2, permission denied; no file created | Expected negative control, separate from the upstream smoke |

The first measurement harness reused `/dev/null` as both npm configuration
paths; npm refused that configuration with exit 1 before installation. Two
distinct scratch paths corrected the harness. The failed configuration and
the complete subsequent run are retained; it is not a sandbox-runtime failure.

[`worktrunk-e2e.json`](../../evidence/artifacts/final-prep-isolation-20261016/worktrunk-e2e.json)
and [`sandbox-runtime-e2e.json`](../../evidence/artifacts/final-prep-isolation-20261016/sandbox-runtime-e2e.json)
bind supported install/smoke commands to their upstream source pins.
[`native-receipt.json`](../../evidence/artifacts/final-prep-isolation-20261016/native-receipt.json)
and [`vendor-installer.json`](../../evidence/artifacts/final-prep-isolation-20261016/vendor-installer.json)
retain command vectors, exit codes, times, counts and output strings. Every
output hash covers the UTF-8 bytes of its published string after explicit
scratch-path and disposable-Git-object substitution. No digest of unpublished
raw output is retained.

These commands also supply **F2 invocation evidence for this measured window**.
They do not establish continuing operational use, ecosystem net usage, a
universal wrapper, or execution of either complete upstream test suite.
The filesystem controls are not upstream tests. Network enforcement at 0.0.79,
TLS, SOCKS, IPv6, DNS rebinding, resource limits and escape resistance remain
unqualified here.

## Delta-only six-angle draft and carried survivors

The resolution inputs are the isolation catalog, the 2026-09-22 verdict wave,
and every committed covering sweep. The latest is 2026-09-29. The stopped or
unretained 2026-09-23 returns do not settle candidates. The missing-fit cases
from 2026-09-26 carry forward; BoxLite and microsandbox both survive facts and
both fit reads in the retained 2026-09-29 returns.

The native `tools/sota-convergence/lane_packets.py` command succeeds using that
manifest, `--registered-receipts` and `--manifest-newcomers`. It exposes only a
catalog selector, so it generates 20 foundation packets in scratch; the
committed [`lane-packet.json`](../../evidence/artifacts/final-prep-isolation-20261016/lane-packet.json)
is an explicitly labeled projection of **only isolation and its four relevant
arms**. It preserves the generator's historical winner pins. Other historical
alternatives are listed as omitted from this delta, not re-adjudicated.

The [`angle-record-draft.json`](../../evidence/artifacts/final-prep-isolation-20261016/angle-record-draft.json)
uses the existing `angle-convergence/2` schema and weights. The weights are
recorded after the smokes, with no claim of preregistration. Every arm remains
**INSUFFICIENT**, provisional and ineligible for FINAL in this draft.

| Angle | Evidence retained | Disputed or missing dimension |
| --- | --- | --- |
| A1, capability at the pin | Pinned vendor sources; fresh winner installs/smokes and narrow filesystem controls | Worktrunk's bounded edit-ownership screen passes; full sandbox policy and both VM host screens remain incomplete |
| A2, upstream engineering quality | Pinned source/distribution/test instructions; retained survivor source reviews | Full-suite results, independent engineering assessment and carried advisory/cleanup resolution |
| A3, community consensus | Historical internal two-family agreement/survival is context | Independent role/pin-relevant community evidence; internal agreement is not substituted for it |
| A4, net usage | Actual native invocations in this window | Independent net usage and continued operational integration; installation counts are insufficient |
| A5, published evaluations | Pinned vendor claims are clearly source review | No independent matched evaluation is retained in this bounded input set; no claim that none exists |
| A6, our measured comparisons | Native receipts remain available for A1/F2 | No matched four-arm comparison; install/smoke passes do not count as comparative A6 |

BoxLite stays a targeted carried candidate at source
`91655df3f172812c56465f96a9dac79f9b193f9f`; microsandbox stays keep-but-compare
at `2110af1e5cc965c57539815a432d6b055ba6a023`. Their source reviews do not bind
the discussed release artifacts (v0.10.4/v0.7.4) into a new trial. A future
trial must reconcile those artifacts first. Prior survival is not current
security clearance; the retained advisory and teardown questions remain.

The native comparison has a named blocker: at 2026-10-16 05:15:26Z,
`python3 -c 'import os; print(os.access("/dev/kvm", os.R_OK | os.W_OK))'`
returns **exit 0, `False`**. Both pinned upstream Linux paths require KVM.
No VM installation/run, group change, service action or account mutation was
attempted. The next input is an authorized eligible isolated host and a
reviewed launch/cleanup context. This is a host-precondition gap, not a
refutation of either survivor.

## Primary sources and review boundary

Accessed 2026-10-16:

- [Worktrunk README at b49ca7ee, create/list/remove](https://github.com/max-sixty/worktrunk/blob/b49ca7eea9b03145791a5b94eccaf9c59412ed37/README.md#L159),
  plus the official [v0.80.0 release](https://github.com/max-sixty/worktrunk/releases/tag/v0.80.0)
  and [unmanaged installer](https://github.com/max-sixty/worktrunk/releases/download/v0.80.0/worktrunk-installer.sh).
- [sandbox-runtime README at d9aac209, npm installation](https://github.com/anthropics/sandbox-runtime/blob/d9aac2098351ca17f3743fbaf6ecbd0051b7e00e/README.md#L14),
  [native echo](https://github.com/anthropics/sandbox-runtime/blob/d9aac2098351ca17f3743fbaf6ecbd0051b7e00e/README.md#L168),
  [explicit settings](https://github.com/anthropics/sandbox-runtime/blob/d9aac2098351ca17f3743fbaf6ecbd0051b7e00e/README.md#L312),
  and [package test commands](https://github.com/anthropics/sandbox-runtime/blob/d9aac2098351ca17f3743fbaf6ecbd0051b7e00e/package.json).
- [BoxLite README at the carried source pin](https://github.com/boxlite-ai/boxlite/blob/91655df3f172812c56465f96a9dac79f9b193f9f/README.md)
  and [microsandbox README at its carried source pin](https://github.com/superradcompany/microsandbox/blob/2110af1e5cc965c57539815a432d6b055ba6a023/README.md):
  documented VM/resource capabilities and Linux KVM prerequisites, without execution.
- [Existing layer-resolution protocol](2026-10-11-layer-resolution-protocol.md)
  and [angle-record contract](2026-10-12-angle-records-final-check.md), both at
  the recorded main base. The draft uses the existing schema without installing
  it as an operational catalog record.

The co-op owns two-family adjudication of the disputed dimensions. This PR
neither dispatches those reads nor admits FINAL. Review can accept the bounded
receipts and proposed run pins while leaving the named gaps open.
