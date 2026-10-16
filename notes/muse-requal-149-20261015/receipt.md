# Muse fence 1.4.9 requalification receipt

Sanitized public derivative of the private sealed receipt
`sdk-harness-ready.muse-requal-149-receipt-20261015T2125Z.md`.
The private original remains unchanged; this derivative removes the private
coordination commitment and clarifies inherited child-environment behavior.
The cited installer/launcher byte snapshots now reside only in private horizon
at `vendor/muse-code/1.4.9-R6297.1/`; public references below name URLs, dated
source pins and hashes. The later addendum records the launch identity guard.
Recorded 2026-10-15T21:25Z. Result: PASS for the existing reader qualification;
no wider Muse work or default promotion. Authority: private co-op currency brief
`sdk-harness-ready.muse-requal-1.4.9-brief-20261015T2115Z.md`, cited by name only.
Base 8053f14e7e0817d2502dff2bb284bfb7e1b0152f. No production pin changed before qualification.

## Screen

Target: stable `1.4.9-R6297.1`; baseline `1.4.7-R6101.1`.
Source: https://dev.meta.ai/docs/muse-code/changelog, read 2026-10-15T21:17Z.
The complete 1.4.8 and 1.4.9 sections are retained in `release-notes.txt`.
The table cites its one-note-per-line capture, not mutable web line numbers.
The stable channel and versioned manifest were read at 21:19Z and agree on the
target. This screen admits only the already selected fence qualification.

| Note line(s) | Release / surface | Classification | Qualification consequence |
| --- | --- | --- | --- |
| 7 | 1.4.9 headless input tool option | fence-neutral | Optional new flag; preserve the exact CC argv contract. |
| 8 | 1.4.9 MCP call metadata | fence-relevant | Repeat planted MCP negative startup control. |
| 12 | 1.4.9 sandboxed Sapling | fence-neutral | Reader shell remains disabled; OS mount control remains mandatory. |
| 16 | 1.4.9 contributor signal | fence-relevant | Require contributor mode off on native argv. |
| 21 | 1.4.9 hook/MCP environment | fence-relevant | Clean environment plus extension startup controls. |
| 30 | 1.4.8 served permission resume | fence-neutral | No serve/resume qualification or profile changes. |
| 31,36,40 | 1.4.8 journal compatibility | fence-relevant | Use fresh dedicated logs; inverse retains old runtime, without cross-version session resume. |
| 32 | 1.4.8 native local-port bridge | fence-relevant | Retain shared-network limitation; no claim of network confinement. |
| 34 | 1.4.8 empty preset | fence-neutral | No preset selected; existing reader argv unchanged. |
| 38,39 | 1.4.8 plugin cleanup and SessionStart source | fence-relevant | Repeat planted extension controls; do not grant plugin paths. |
| 41,42 | 1.4.8 Auto-review / served sandbox reuse | fence-neutral | Reader-only smoke; no Auto-review or served sessions. |
| 50 | 1.4.8 plugin command size | fence-neutral | No plugins installed or exposed. |
| 55 | 1.4.8 startup trust prompt | fence-neutral | Existing explicit trust-workspace remains matched. |
| 57 | 1.4.8 workflow restart records | fence-neutral | No workflow or restart in qualification. |
| 58,60 | 1.4.8 extension lifetime / managed notices | fence-relevant | Settings allowlist, home masks and native extension controls. |
| 61,62 | 1.4.8 Sapling approval / read-only classification | fence-neutral | Reader shell disabled; OS enforcement remains independent. |
| 67,68 | 1.4.8 child hook startup / prompt hints | fence-relevant | Confirm extension markers absent with installed native echo. |
| 70 | 1.4.8 plan path permissions | fence-relevant | Keep OS worktree/Git metadata and named-write controls. |
| 74 | 1.4.8 exec exit waits for compaction | fence-relevant | Bound deadline and require completed terminal, not exit alone. |
| 76 | 1.4.8 MCP audit notices | fence-relevant | Native startup control rather than absence of notices alone. |
| 79 | 1.4.8 native Bubblewrap selection | fence-relevant | Repeat real OS controls with unchanged outer bwrap pin. |
| 81 | 1.4.8 contributor catalog routing | fence-relevant | Contributor mode off remains mandatory. |
| 82 | 1.4.8 resumed media permissions | fence-neutral | Fresh text-only brief; no resumed sessions/media. |
| 83 | 1.4.8 served provider settings | fence-neutral | No serve; no inherited endpoint overrides. |
| 89,90 | 1.4.8 hook view / concurrent resume | fence-relevant | Observe planted marker absence directly; no resume. |
| 91 | 1.4.8 contributor opt-out including background | fence-relevant | Retain forced-off settings and explicit CLI flag; inspect derived events. |
| 94 | 1.4.8 profile launch refusal | fence-relevant | Run all existing profile/layout regressions; no escape-hatch setting. |

No release note in these two sections announces a change to `--disable-web-tools`,
ELF packaging, installer/update behaviour, or telemetry controls. Absence from
notes is not a compatibility measurement. Installer source, installed CLI help,
model-free probes and the single reader smoke supply the bounded checks.
Other notes concern UI/session history/performance and do not change a fence
dependency; all are retained for inspection. No model request or candidate
execution occurred during this screen.

Protocol inputs: `docs/decisions/2026-10-11-layer-resolution-protocol.md`;
`catalogs/landscape/foundation.json` isolation retain verdict and evidence;
`catalogs/sota-convergence/layer-verdict-waves.json` and its 20260922 wave;
`catalogs/saturation/ledger.json`, isolation's latest retained sweep
`landscape-sweep-20260929`, its manifest/returns. Boxlite and microsandbox remain
unresolved survivors; earlier missing votes are not adjudications. This item
tests only the changed native Muse mechanism at its pin. No general layer
winner/default, comparison or saturation verdict changes.

Screen result: PASS for bounded trial. Installed-contract compatibility and
live qualification remain unmeasured until the subsequent receipt.


## Vendor installation and inverse recovery

Supported installer source: https://dev.meta.ai/install.sh, read 2026-10-15T21:17Z;
SHA256 5196d820127a241211c96cf38f0b2e30cff8506a82e9da9508cd5f826632a0ca.
Installer command (after saving and screening vendor script):

```text
env -i HOME=/var/tmp/sdk-muse-requal-149-20261015/install-home PATH=/usr/bin:/bin MUSE_INSTALL_DIR=~/.local/bin/muse-1.4.9-R6297.1 MUSE_NO_MODIFY_PATH=1 MUSE_LOGIN=0 MUSE_AUTH_PATH=/var/tmp/sdk-muse-requal-149-20261015/install-home/no-sign-in.json bash /var/tmp/sdk-muse-requal-149-20261015/install.sh
```

The actual MUSE_INSTALL_DIR argument was the absolute expansion of the shown
home-relative path. Exit 0. No shell profile, existing shim or existing install
was changed. HOME and auth selection referred only to new empty task locations.
Vendor launcher source https://api.meta.ai/muse-launcher.sh, read 21:18Z,
SHA256 c6db294799a190ca380da274beb3b9c0e160e0da9681a3d364ce8b0e5fa3a4bc;
installer lines 5,178-181,300 and launcher lines 929-1010 evidence the
source-observed separate install and manifest/size/checksum interfaces. The
official documentation supports invoking the installer; it does not document
those environment inputs as public settings.

Stable channel: https://api.meta.ai/muse-code/channels/muse-stable.
Versioned manifest: https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=manifest.json.
Downloaded x86_linux artifact and installed ELF: 372586712 bytes, SHA256
**a228010021276e112aa8422eb56ae82c0375405701950f6529bed4c9fe8abe05**,
matching the versioned manifest. Artifact URL substitutes file=muse-x86-linux.
Installed ELF: ~/.local/bin/muse-1.4.9-R6297.1/muse-bin-1.4.9-R6297.1.
The pre-existing auto-updater ELF ~/.local/bin/muse-bin-1.4.9-R6297.1 is also
372586712 bytes and has exactly that manifest hash. Both compared first-hand.
Version function check: Muse Code 1.4.9 (1.4.9-R6297.1).

Root cause: the old flat 1.4.7 ELF was absent before qualification. The co-op's
first-hand 21:21Z relay attributes replacement to the vendor shim's ~19:18Z
update; this lane independently confirmed absence and the current flat 1.4.9
artifact hash. This is consistent with vendor launcher:1006-1010. The exact-pin
fence therefore failed closed. The new separate installer did not delete it.

Inverse recovered through the vendor's same versioned manifest/artifact URLs,
substituting version=1.4.7-R6101.1. HTTP success (curl rc 0). Retained at
~/.local/bin/muse-1.4.7-R6101.1/muse-bin-1.4.7-R6101.1, 363518168 bytes, SHA256
**36e3dac91f56c15572b95be55d70ee9fd9685cd9ab49f747bab4746c8d7c2518**,
matching both vendor manifest and the sealed fence acceptance pin. Not executed.
Inverse after a candidate repin: restore the 1.4.7 launcher source/pin, select
this retained ELF explicitly, and remove only the new 1.4.9 install directory.
No old-version session resume is promised. No inverse action was applied.

## Existing qualification

The landed fence's Fence/native_argv/probe/run_bounded_fence/event_receipt code
was used unchanged. Private candidate test glue varied only runtime/version
selectors, including the synthetic version fixture; current repository pin
remained 1.4.7 during qualification. All 39 existing controls passed with both
native switches enabled, zero skips (6.952 seconds). This includes named OS
masks, planted unfenced/fenced canary, startup MCP/hooks controls, Git metadata,
artifact custody, child lifetime and installed Go directory read-only control.
Command: systemd-run --user --scope -p CPUWeight=idle --quiet -- python3 -B
/var/tmp/sdk-muse-requal-149-20261015/qualify-tests.py.

Initial candidate-glue attempts were not successful qualification: a context
subprocess orchestration attempt returned rc 1 before a usable test result;
the first two direct suites each failed the synthetic lifetime fixture because
its subprocess retained the on-disk 1.4.7 pin while the temporary fixture
advertised 1.4.9. The glue preserved the fixture's on-disk version, then 39/39
passed. No fence policy was changed to make these pass. Logs remain private.

One reader-role smoke, own full clone, mandatory flags --contributor-mode off,
--disable-web-tools, --disable-write and --disable-shell. Same unchanged CC
argv builder and model/effort contract. No new role, workflow or research run.
Mandatory pre-live probe: PASS, 38 named checks; native echo rc 0,
14 events, one completed terminal. One Meta invocation:

- Start: 2026-10-15T21:22:49.798525+00:00
- Finish: 2026-10-15T21:24:04.745561+00:00
- Exit: 0; events: 39; invalid lines: 0.
- Model: muse-wonder-full-1.0; CLI effort max (wire effort not asserted).
- Terminal: one run.terminal.completed; expected trivial reply present: true.
- Tool-result events: 0; four task streams include the main task and reminders.
- Tracked clone files unchanged. Shared host networking remains; no egress claim.

Raw native streams and session/account fields stay private. No run-content
hashes are published. Private custody is the task/time reference
sdk-muse-requal-149-20261015, reader-logs; derived facts above only.
No sign-in contents were opened, copied, hashed or logged by the wrapper or
qualification tooling; the existing native read-only mount exception applies.

## Auto-update proposal for CC decision only

Option (a): no documented disable/pin setting was found in the official overview
https://dev.meta.ai/docs/muse-code (Install), configuration
https://dev.meta.ai/docs/muse-code/configuration (settings-file/flags), or 1.4.8/
1.4.9 changelog, read 2026-10-15 at 21:17Z/21:22Z. These are dated live-doc
captures, not immutable release documentation. The captured vendor launcher
source exposes MUSE_NO_AUTO_UPDATE at lines 1091,1098, but source support is not
a documented host setting. Do not turn it into an approved global default.
No host shim setting or shell profile was changed. The unchanged fence
`clean_env()` already supplies `MUSE_NO_AUTO_UPDATE=1` to its direct retained-ELF
child, and the external lane supplies it for its version observation. That
inherited child environment is separate from the host vendor updater policy:
option (b) leaves the vendor updater ON.

Option (b), DEFAULT PROPOSAL for CC read: retain each qualified vendor ELF as a
fence-owned copy outside any directory containing the vendor updater. Continue
following stable releases through vendor install.sh into separate versioned
staging; retain its manifest/hash, then place the qualified exact bytes under
~/.local/share/native-agent-stack/muse-fence/runtimes/<version>/muse-bin.
This follows the official overview's native install path and the vendor
launcher's manifest/checksum path at the captured source pin above, while
avoiding its directory-scoped old-binary cleanup at lines 1006-1010. Function
check the retained copy's exact hash and --version inside the existing fence;
no second live smoke is proposed. Inverse: select the prior retained qualified
ELF and prior launcher pin, then remove only the new fence-owned version dir.
This is the CC's recorded follow-latest retention practice, not a vendor claim
that copies are managed by the shim. The proposal has NOT been applied or
approved; no fence-owned retained copy has yet been created.

## Disposition

Qualification PASS permits preparation of one superseding currency PR, preserving
sealed decisions. Re-pin remains a proposed repository change subject to review;
no F1 launch or pool-unpause is inferred. Auto-update proposal awaits the CC.
