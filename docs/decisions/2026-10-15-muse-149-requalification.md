# Muse 1.4.9 reader fence requalification

Status: qualification passed; CC option (b) adopted; currency repin proposed for review.
Rebuilt base: `5bab63233ef90260bec4a8ee0cec4f5e4431776c`.
Original qualification base: `8053f14e7e0817d2502dff2bb284bfb7e1b0152f`.

This addendum supersedes only the runtime-version/ELF selection in
[the sealed fence decision](2026-10-14-muse-file-fence.md). That decision's
boundaries and [the toolchain directory policy](2026-10-15-muse-toolchain-directory-grants.md)
remain controlling. Neither sealed decision text is changed. No role, network,
extension, filesystem or accepted-layout grant is widened.

The CC currency brief is retained under the lane coordination directory as
`sdk-harness-ready.muse-requal-1.4.9-brief-20261015T2115Z.md`, cited by name only.
The bounded delta follows the layer-resolution protocol: isolation's retain
verdict, 20260922 wave, latest retained 20260929 sweep and unresolved survivors
are identified in the [screen](../../notes/muse-requal-149-20261015/screen.md).
No layer winner or general default changes.

## Pin and vendor path

Qualified runtime: **Muse Code 1.4.9 (1.4.9-R6297.1)**, Linux x86_64 native ELF,
372586712 bytes, SHA256
`a228010021276e112aa8422eb56ae82c0375405701950f6529bed4c9fe8abe05`.
The vendor installer placed it in a new versioned staging directory, using its
source-observed `MUSE_INSTALL_DIR` and `MUSE_NO_MODIFY_PATH` inputs. The official
docs support the top-level installer path; these two inputs are evidenced only
by the captured installer source, not documented as public settings. Under the CC's
21:26:23Z ruling, a fence-owned retained copy supplies the default exact ELF:
`~/.local/share/native-agent-stack/muse-fence/runtimes/1.4.9-R6297.1/muse-bin`.
It is outside every vendor updater directory and contains no shim. Exact hash
and `--version` inside the fence pass; the CLI selects this file directly.
The previous flat 1.4.7 path remains absent. Its vendor artifact was recovered,
then retained at
`~/.local/share/native-agent-stack/muse-fence/runtimes/1.4.7-R6101.1/muse-bin`,
363518168 bytes, SHA256
`36e3dac91f56c15572b95be55d70ee9fd9685cd9ab49f747bab4746c8d7c2518`.
It was hash verified and never executed. Both retained files have mode 0555;
binary bytes remain outside the repository. Their manifest URLs substitute
the exact version in
`https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=<version>&file=manifest.json`.
The dated root cause and inverse are in the [sanitized public receipt](../../notes/muse-requal-149-20261015/receipt.md).

Primary sources, read 2026-10-15:

- Meta [Muse Code overview, Install](https://dev.meta.ai/docs/muse-code#install),
  official vendor install.sh path; [configuration](https://dev.meta.ai/docs/muse-code/configuration),
  settings schema/flags; [changelog](https://dev.meta.ai/docs/muse-code/changelog),
  headings 1.4.8 and 1.4.9. The full release sections and per-note screen are
  retained beside the receipt, with dated capture locators.
- Private `horizon:vendor/muse-code/1.4.9-R6297.1/install.sh:5-7,178-181,300`, captured
  from https://dev.meta.ai/install.sh, SHA256
  `5196d820127a241211c96cf38f0b2e30cff8506a82e9da9508cd5f826632a0ca`.
- Private `horizon:vendor/muse-code/1.4.9-R6297.1/muse-launcher.sh:929-1010,1080-1086,1091-1098`,
  from https://api.meta.ai/muse-launcher.sh, captured SHA256
  `c6db294799a190ca380da274beb3b9c0e160e0da9681a3d364ce8b0e5fa3a4bc`.
  The private installer and launcher are unchanged vendor-source snapshots.
  Their byte copies are excluded from this public tree; only source URLs,
  dated pin and SHA256 remain here. Private custody PR: horizon#1.
- Versioned vendor `vendor/manifest-149.json`, selected through the captured
  `vendor/stable.json`. The ELF hash/size matches the manifest. The host's
  pre-existing auto-updated 1.4.9 ELF independently matches the same hash/size.
- Bubblewrap remains `v0.11.1` at
  `124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe`, `bwrap.xml`, as cited in the
  controlling fence decisions. No new flag or containment mechanism is added.

## Qualification and evidence

All 39 existing fence controls passed with installed-client and installed-Go
opt-in probes enabled, zero skips. Model-free native echo proved named startup
controls at the candidate version. Before any production source pin changed,
temporary qualification glue selected the candidate ELF/version with unchanged
Fence/native_argv/probe mechanisms. Its initial synthetic fixture mismatch and
successful correction are recorded, without hiding the failed attempts.
At reviewed head `cdc7988db099b4bfbb973edcb68ad9749dc51e1e`, the retained-path
branch passed 40 tests without substitutions, zero
skips. At reviewed head `cdc7988db099b4bfbb973edcb68ad9749dc51e1e`,
`tests/test_muse_runtime_currency.py:16-41` uses the real retained
1.4.9 ELF: it fails at base 8053f14e7 with `ValueError: runtime pin mismatch`,
then passes after the repin. It also explicitly requires the old 1.4.7 pin to
refuse that ELF before echo/live execution. No model request is made by it.
The first final-branch attempt retained an old version string in one synthetic
fixture and failed that fixture; updating all version-only fixtures resolved
it. The private sealed pre-CC receipt remains unchanged; its public derivative
is explicitly sanitized. This addendum records the subsequent source-state result.

One authorized reader smoke passed through the fence: 38 mandatory named
pre-live probe checks, echo exit 0 / 14 events, then native Meta exit 0 /
39 events, `muse-wonder-full-1.0`, one completed terminal and expected reply.
Start 2026-10-15T21:22:49.798525Z; finish 21:24:04.745561Z. CLI effort max;
wire effort and billed cost are not measured. No tool-result event or tracked
clone change. No second live smoke, new Muse work or pool-unpause is authorized.
Raw events remain private; the receipt publishes derived facts only.

## Retention decision and inverse

The vendor's directory-scoped update cleanup is documented by its captured
launcher source above. No documented auto-update-disable/pin setting was found
in the read vendor pages; source-only `MUSE_NO_AUTO_UPDATE` support is not
presented as documented host policy. No setting was changed.

The private receipt's proposal was subsequently ADOPTED by the CC at 21:26:23Z,
relayed in co-op message 183437. Source: command-center/CC-TRACKER-20261014.md:877.
The 10-14 follow-latest rule is cited in that tracker's 19:29:48Z entry at :819;
only the recorded retained-copy/function-check practice is applied here. No
owner quotation is retained. Option (a) is rejected as a default. Vendor updater
settings remain unchanged. The inherited `clean_env()` still supplies
`MUSE_NO_AUTO_UPDATE=1` to the direct retained-ELF child; the external lane also
supplies it for version observation. This PR does not add that behavior or
disable the host vendor updater. Option (b) leaves vendor updates ON.
This PR implements option (b)'s default retained path and records its two
hash-bound files; it does not introduce a retention manager.
Inverse: restore the prior launcher source/pin and explicitly select the retained
1.4.7 ELF, then remove only the new fence-owned 1.4.9 version directory and its
separate staging install if no longer needed. Keep the prior retained copy.
Do not attempt to resume new-version session journals in the old runtime.

Reopen this version decision if the mandatory probes, CLI contract or exact ELF
identity differ, or a new release changes a fence dependency. Stronger roles,
network restrictions and general isolation choices require separate evidence.

## Public provenance

Qualification receipt: `notes/muse-requal-149-20261015/receipt.md` is a sanitized
public derivative, with its current identity in `manifests/evidence.json`.
The private sealed original is cited only by its dated custody name above.
Screen: `screen.md` in the same notes directory, SHA256
`1764797382cc502059e47943ec8afefe5a1456e15a0a44e70f7135edd6890fbe`.
Release notes: `release-notes.txt`, SHA256
`2d42853484171c147b026af7aa7ca137a3d67b21c46eb51d64fd3636dac64b79`.
The receipt records the pre-ruling state: its unadopted option (b) statement is
superseded by this section, without rewriting the private original. The fence remains
fail-closed on main until this PR passes both-family reads and lands.

## Review correction: public derivative and source provenance

Authority: `cc-reads-20261005/full1-pr1186/GPT-VERDICT-cdc7988db.md`,
blocker 1 and follow-ups 2-4, cited by path only. The new publication regression
at reviewed head 48251c58 is `tests/test_muse_runtime_currency.py:15-36`; it failed at both reviewed
Markdown sites before removal. It accepts only published file identities,
the cited public Git identities, URL-pinned vendor source identities and
vendor-manifest artifact checksums.
It embeds no private coordination value or prefix. The private sealed original
is preserved; public receipt bytes and affected evidence rows are refreshed.

Eight fresh anonymous HTTPS requests independently re-fetched the cited Meta
sources after review. `notes/muse-requal-149-20261015/source-captures/http-provenance.json`
records actual UTC reads, HTTP status, selected non-cookie response headers,
requested/effective URLs, capture paths and SHA256 values. All returned 200.
Installer and launcher bytes now reside only in private horizon custody;
their URL/pin/SHA metadata remains here. At capture time these and the stable
channel/versioned manifests matched the earlier vendor snapshots.
All 93 release-note items match the original retained
1.4.8/1.4.9 sections. Fresh overview/configuration text and release-note sections
are retained alongside that provenance. This is a new source fetch independent
of the install, not a second-reviewer attestation. HTML extraction excludes
scripts/styles; the full dated overview and configuration text is retained.
Public source capture identities are recomputed in the evidence registry;
private script identities were checked at their private custody path. Hashes
name the stored, newline-normalized representation, not an unretained transport
byte stream. Full overview/configuration text and scoped release notes are
labelled separately. No model request or host setting change occurs.

The sealed toolchain decision and its historical controls are preserved. The
current locator map below supersedes their unqualified implementation spans
for this source state; historical commit-qualified locators retain their meaning.

| Historical record | Current implementation locator |
| --- | --- |
| `2026-10-15-muse-toolchain-directory-grants.md:34`; `controls.json:6` | `tools/muse_file_fence.py:38-85,279-318,345-346,498-499` |
| Runtime version/default path and CLI selector | `tools/muse_file_fence.py:25-29,493` |
| Runtime identity gate | `tools/muse_file_fence.py:128-140,519` |
| Retained inherited child environment | `tools/muse_file_fence.py:143-150` |
| Publication regression | `tests/test_muse_runtime_currency.py:47-78` |
| Old-pin refusal / current-pin model-free control | `tests/test_muse_runtime_currency.py:81-107` |

## CC full-read correction and rebuilt history

Authority: `pr1186-micro/MICRO-full-48251c58.md`, P1/P2/P3s, and co-op message
187059. The two vendor script byte captures are in PRIVATE horizon PR1 under
the paths above, with unchanged source hashes. The public tree excludes them;
factual versioned manifests and dated URL/hash provenance remain public.

Launch now verifies the runtime's complete SHA256 against the fixed versioned
vendor manifest before argv construction, log creation or executing any runtime
command. The version check remains inside the fence after that gate. There is
no caller-controlled digest argument. CPython 3.13 `hashlib.file_digest` and
`os.open` supply the check; the existing host-administration race limitation
is unchanged. The new fail-first control is
`tests/test_muse_runtime_currency.py:21-43`: it fails at 48251c58 before the guard,
then passes after. Existing synthetic runtime fixtures supply only their own
test-process expected hashes; the production CLI exposes no test override.
All 43 fence/currency controls pass at this rebuilt source state, zero skips
with both installed probes enabled. No additional live Muse invocation occurs.

The fixed tree is rebuilt as one commit on the current main base above, with a
local backup ref for the old head and an exact lease push over that old head.
Residual disclosure inventory by count/class only: one coordination-content
commitment appeared at two historical Markdown sites; two vendor-code file
blobs existed in the prior branch history. Neither class remains in this tree
or this rebuilt branch's new ancestry. Existing GitHub PR refs, caches and local
backup may retain those old objects; no global erasure or history purge is
claimed. No private commitment value or prefix is repeated in this record.
