# Isolation FINAL preparation from retained native captures

Status: **preparation only**. The layer remains reopened. This record proposes
the existing main run pins and supplies a fresh native capture window for
review; it changes no catalog winner, default, operational angle record or
FINAL-admission policy. The source-main snapshot is
`65d66a370d9a5f129662d14c84f2820e940b3a83`.

The earlier preparation [PR #1207](https://github.com/native-agent-stack/native-agent-stack/pull/1207)
is closed. Its discarded pre-mask streams are not reconstructed or reused.
This new work starts from main and executes a new isolated window through the
committed recorder. The correction is byte custody, not a claim that masking
or a synthetic test input is inherently invalid.

## Capture custody and scope

The [recorder and masking rule](../../blueprints/convergence-practice/isolation-capture-20261016/README.md)
send subprocess stdout/stderr directly into private binary files. Exact
argv/cwd/environment, return code and raw-byte integrity metadata stay private.
The private run is named **isolation-native-recapture-20261016**; public records
identify originals by capture name only. Native stream bytes are preserved
before any decoding or masking.

The [masked directory](../../evidence/artifacts/isolation-native-captures-20261016/masked/)
contains labeled `masked_native_capture` metadata and separate stdout/stderr
byte files. Seven documented literal substitutions replace scratch/worktree/user
paths, the exact disposable Git object/short form, and a vendor CI build path.
Public hashes bind the published bytes. No broad hash filter or summary
replaces native output. The published test checks byte preservation, nonzero
returns, missing/modified originals, stable masking and immutable names.

The [native custody-test output](../../evidence/artifacts/isolation-native-captures-20261016/masked/custody-tests.stderr.txt:2)
reports five tests; [its metadata](../../evidence/artifacts/isolation-native-captures-20261016/masked/custody-tests.json:48)
records exit 0. These are synthetic recorder tests, not product acceptance.
The co-op's private reproduction is a separate required gate before PR opening.

All installations stay in owned `/var/tmp` scratch prefixes. Worktrunk uses
the official unmanaged installer without shell integration, PATH modification
or updater installation. npm uses an explicit prefix/cache and separate empty
scratch configuration paths. Existing host tools are only read with `--version`.
No model, credential, service, VM, account or host-install action is performed.

## F1: exact pin reconciliation

The [authored resolution analysis](../../evidence/artifacts/isolation-native-captures-20261016/resolution-inputs.json)
binds each value to its supporting field line at the source-main snapshot.
It is analysis, not native output. Proposed run pins are:

| Component | Proposed existing run pin | Supporting run fields | Historical verdict fields |
| --- | --- | --- | --- |
| Worktrunk | 0.80.0, `b49ca7eea9b03145791a5b94eccaf9c59412ed37` | `catalogs/landscape/final-stack.json:11393` and `:11395`; `manifests/stack.json:1073` and `:1095` | `catalogs/landscape/foundation.json:1091`, 0.79.0; final-stack `:6284`; drift `:6276` |
| sandbox-runtime | 0.0.79, `d9aac2098351ca17f3743fbaf6ecbd0051b7e00e` | `catalogs/landscape/final-stack.json:11214` and `:11216`; `manifests/stack.json:871` and `:888` | `catalogs/landscape/foundation.json:1112`, 0.0.77; final-stack `:6306`; drift `:6298` |

The clean-install decision row at
`docs/decisions/2026-10-15-new-wsl-clean-install-plan.md:137` names the winner
pair and two pin drifts, but no separate version. Its selected profile values
are `adoption/new-wsl-profile.json:807` and `:750`. The prior direct native
records name 0.80.0 at `worktrunk-0800-qualification-20261003.json:19` and
0.0.79 at `native-sandbox-codex-binding-20261008.json:19`, both under
`evidence/receipts/`. Their limitations remain historical evidence, not fresh
acceptance. The later SRT citation repair explicitly disclaims new native
execution at `evidence/receipts/srt-source-citations-20261008.json:12`.

Fresh installed-version output is
[`host-wt-version.stdout.txt:1`](../../evidence/artifacts/isolation-native-captures-20261016/masked/host-wt-version.stdout.txt:1)
and [`host-srt-version.stdout.txt:1`](../../evidence/artifacts/isolation-native-captures-20261016/masked/host-srt-version.stdout.txt:1).
Each metadata file's `:45` records exit 0. The Worktrunk profile's historical
host-version sentence at `:843` still says 0.79.0. The old SRT filesystem/network
proofs do not transfer versions; `native-sandbox-codex-binding-20261008.json:14`
states that limitation. Pin reconciliation requires reviewed supersession;
historical verdict bytes remain unchanged.

## E2E and F2 evidence

The evidence is the native captures below, with no generated success wrapper.
Commands and marked placeholders are at each metadata file's `argv` field;
the exact originals are retained privately. This is upstream-supported install
and documented CLI smoke, not execution of either full upstream test suite.

| Claim | Native output or return-code field under `masked/` | Limit |
| --- | --- | --- |
| Worktrunk installer completed | `worktrunk-install.json:47`, exit 0; `worktrunk-install.stdout.txt:1` | Official unmanaged scratch install |
| Installed version is 0.80.0 | `worktrunk-version.stdout.txt:1`; rc `worktrunk-version.json:45` | No shell integration |
| Native create/list/remove executes | rc `worktrunk-create.json:51`, `worktrunk-created.json:46`, `worktrunk-remove.json:48`, `worktrunk-after.json:46` | Synthetic owned Git fixture, hooks disabled, no remote |
| Created listing includes main and isolated; after listing includes main | `worktrunk-created.stdout.txt:12` and `:47`; `worktrunk-after.stdout.txt:12` | Any item-count comparison is derived analysis of these native arrays |
| SRT installation and 0.0.79 readback | rc `srt-install.json:54`; `srt-version.stdout.txt:1` and rc `srt-version.json:45` | npm package in a scratch prefix |
| README echo executes | `srt-echo.stdout.txt:1`, rc `srt-echo.json:49` | F2 invoke in this window, not broad policy qualification |
| Additional deny-write control refuses the file | `srt-deny-write.stderr.txt:1`, rc `srt-deny-write.json:50` is 2; `denied-file-absent.json:47` is 0 for native `test ! -e` | Synthetic one-file control through real CLI |

The allowed-write native byte dump is `allowed-bytes.stdout.txt:1`; the
published `policy-input.stdout.txt` is the exact settings input after masking.
Synthetic fixture inputs are explicitly distinguished from the real native
executions. No simulated product response is presented as a run.

These same Worktrunk lifecycle and SRT echo commands are **F2 invoke evidence**
for this window. They do not prove sustained operational use, ecosystem net
usage or universal wrapping of agent commands. Network/TLS/SOCKS/IPv6 policy,
resource/VM enforcement, crash recovery and escape resistance remain gaps.

## Six-angle draft and carried survivors

The [unscored draft](../../evidence/artifacts/isolation-native-captures-20261016/angle-record-draft.json)
is authored analysis for the existing winner pair and two carried survivors.
It supplies no synthetic scores, availability booleans or FINAL-eligibility
measurement. Each arm has explicit A1 capability, A2 engineering, A3 community,
A4 net usage, A5 published evaluation and A6 native-comparison dispositions.
Unknown dimensions remain named gaps rather than copied boilerplate evidence.

The existing lane-packet generator ran against the 2026-09-29 manifest:
[`lane-packet-generation.json:57`](../../evidence/artifacts/isolation-native-captures-20261016/masked/lane-packet-generation.json:57)
records exit 0 and [its native stdout](../../evidence/artifacts/isolation-native-captures-20261016/masked/lane-packet-generation.stdout.txt:1)
records the catalog-wide packet count. The original isolation packet stays
private by the name `foundation__isolation.json`, as a research input. This
does not rerun a survey or make every generated candidate a new comparison arm.

The 2026-09-22 wave reference is at `layer-verdict-waves.json:9`, under
`catalogs/sota-convergence/`. Latest committed covering-sweep survival is
explicit at `catalogs/saturation/ledger.json:8200`, `:8202`, `:8206` for BoxLite,
and `:8212`, `:8214`, `:8218` for microsandbox. Earlier missing votes do not
settle either survivor. The source pins are the `:7` fields of their retained
reviews under `evidence/artifacts/landscape-sweep-20260929/`.

The VM trial prerequisite still fails: native
[`kvm-precondition.stdout.txt:1`](../../evidence/artifacts/isolation-native-captures-20261016/masked/kvm-precondition.stdout.txt:1)
is `False`; metadata `:45` records rc 0. This is a captured read-only access
check, not a product failure. BoxLite's pinned README `:242` requires accessible
KVM; microsandbox's `:110` requires KVM on Linux. Neither is installed or run.
The next input is an authorized eligible isolated host, exact trial-artifact
binding and a reviewed enforcement/resource/cleanup comparison. Both survivors
remain unresolved for the co-op's two-family adjudication.

## Primary sources

Accessed 2026-10-16; source-review claims are distinct from native captures:

- [CPython v3.13.16 subprocess file handles:514](https://github.com/python/cpython/blob/v3.13.16/Doc/library/subprocess.rst#L514),
  [binary mode:666](https://github.com/python/cpython/blob/v3.13.16/Doc/library/subprocess.rst#L666),
  and [wait/return code:794](https://github.com/python/cpython/blob/v3.13.16/Doc/library/subprocess.rst#L794).
- [Worktrunk pinned README:159](https://github.com/max-sixty/worktrunk/blob/b49ca7eea9b03145791a5b94eccaf9c59412ed37/README.md#L159),
  `:166` list and `:183` remove; official [v0.80.0 installer](https://github.com/max-sixty/worktrunk/releases/download/v0.80.0/worktrunk-installer.sh),
  lines 60–63 define unmanaged install without PATH/updater changes.
- [SRT pinned README:14](https://github.com/anthropics/sandbox-runtime/blob/d9aac2098351ca17f3743fbaf6ecbd0051b7e00e/README.md#L14),
  `:168` native echo and `:312` explicit settings.
- [BoxLite pinned README:167](https://github.com/boxlite-ai/boxlite/blob/91655df3f172812c56465f96a9dac79f9b193f9f/README.md#L167)
  states VM/OS sandbox/resource/egress capabilities; `:242` is the Linux prerequisite.
- [microsandbox pinned README:110](https://github.com/superradcompany/microsandbox/blob/2110af1e5cc965c57539815a432d6b055ba6a023/README.md#L110),
  `:177–178` network allowlist and `:235–236` CPU/memory settings.

Vendor claims and retained survivor reviews are not current independent
security clearance. The co-op's review decides disputed dimensions; this
preparation makes no adoption, retirement or FINAL decision.
