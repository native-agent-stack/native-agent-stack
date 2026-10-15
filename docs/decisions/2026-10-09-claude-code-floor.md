# Claude Code 2.1.295 minimum and plugin notification decision

Both native bootstrap manifests now select the Claude Code 2.1.295 installer
artifact as their minimum release. Their existing `version_probe.match` is
`minimum`, and both `install_native` functions keep an equal or newer native
launcher. The new-WSL profile also explicitly defines its pin as a floor and
retains the native latest-channel update step. These are minimum-version
schemas; no runtime equality constraint or ceiling is introduced.

The native installer still verifies the selected artifact before installing
it when the launcher is missing, unreadable or below the minimum. A launcher
at 2.1.295 or above is kept without downloading or installing the older
artifact. Functional acceptance runs separately on the resulting version.

## Distribution evidence

The source is Anthropic's native release
[2.1.295 manifest](https://downloads.claude.ai/claude-code-releases/2.1.295/manifest.json)
and [documented integrity/signing procedure](https://code.claude.com/docs/en/setup#binary-integrity-and-code-signing).
The retained cc-native-practice check at **2026-10-09T06:13:50Z** is cited
from `PROPOSAL-guard-fail-closed.md` section B, SHA256
`9ae0a4c2faf71cd93b8aacce931fa4f96b15386e1da62f343d17ba499c096440`.
Its private custody locator is
`$HOME/.local/state/native-agent-stack/coordination/cc-native-practice-20261009/PROPOSAL-guard-fail-closed.md`.

The forwarded check is: manifest **b36d7b37**, **Good signature**, fingerprint
**31DD DE24 … CACE**; linux-x64 **4503bfe1…f358**, **256,113,848 B**.
The source proposal supplies the full values:

| Item | Retained check |
| --- | --- |
| Manifest SHA256 | `b36d7b376c95dd409212ecce0b700cd547266d9ea014ab1f81a1d5bc49cb3cbe` |
| Manifest signature SHA256 | `7cc44851b80b692481cf986699276c4c14b4301b61aabf46682ad9224ab24c32` |
| Release commit | `07e8f67ea3282bf154a9e05673a0942b1b173cef` |
| Build date | `2026-10-08T17:09:12Z` |
| Signing-key fingerprint | `31DD DE24 DDFA B679 F42D 7BD2 BAA9 29FF 1A7E CACE` |
| GPG result | Good signature from “Anthropic Claude Code Release Signing <security@anthropic.com>” |
| linux-x64 SHA256 / size | `4503bfe11a6c7fcc1e0b39b5e0d347c04248f750b03b0977b3ad6b531fe6f358` / 256,113,848 B |
| darwin-arm64 SHA256 / size | `0116ee2e0a513900b633d9951367f18747686478e2b462805b8c31609f047f70` / 239,695,888 B |

This is a retained check performed by cc-native-practice, not a new signature
or artifact verification by currency. The source reports that the host's
installed Linux binary matched the digest and size. It reports no Mac
rehash, execution or `codesign` verification. The macOS row keeps its
`manifest_crosscheck` evidence boundary. Currency did not download the
artifacts, import a key, rerun GPG, inspect credentials or change a client.

## Plugin notification classification

The same 2.1.295 client also carries `plugin_notification`. Its decision is
**quiet**, with `documented=False` in the shared notification decision table.
The primary source is the pinned
[2.1.295 Linux artifact](https://downloads.claude.ai/claude-code-releases/2.1.295/linux-x64/claude)
with the retained digest above. `claude --version` returned
`2.1.295 (Claude Code)`; bounded reads of that installed artifact found the
type in its matcher catalog at zero-based byte offset 207984418 and in its
`$.ui.notify` emitter at 217182500:

```javascript
sI()?.notify?.({message:e.text,title:e.title||n.plugin,notificationType:"plugin_notification"},n.origin)
```

The plugin supplies the text and optional title; otherwise the title is its
name. The enclosing emitter reports the delivery channel, disabled/no-channel
or no-surface status, or a channel-write error. It has no permission or
input-wait predicate. A generic plugin notification therefore does not
establish the needed action that the escalation-only bell policy requires.
The repository bell matcher excludes this quiet type and continues to match
exactly the decision table's ring types. No live settings are applied.

The [official hooks reference](https://code.claude.com/docs/en/hooks#notification)
sample fetched at 2026-10-09T08:53:56Z had zero occurrences of this type,
HTML SHA256 `eed92dc40935f74820bc090b899e529e11574171570e6e1b69d636825a15202b`.
That reference is current documentation, not a version-pinned introduction
claim. The documented-type count remains 12; the enforced decision count
increases from 18 to 19. The pinned-source excerpts, offsets, documentation
sample and evidence limits are retained in
`evidence/artifacts/notification-types-20260929/recorded/f10-2.1.295-source.json`.
No artifact was downloaded or rehashed for this fold.

The installed-client regression case is preserved. At the prior PR head
`d73b1caa1cdba1f94521a34bec5c327e9d35a206`,
`python3 -m unittest tests.test_windows_terminal_defaults` returned 1:
45 tests, with the sole failure reporting `['plugin_notification']` as a
type without a decision. Adding its quiet decision and updating the count
allows the same module to pass. Both native outputs are retained as
`f10-2.1.295-before.txt` and `f10-2.1.295-after.txt` beside the source record.
The public failure traceback replaces its host path with `<repo>`; the raw
before/after outputs are also retained in the lane's private evidence.
This is an installed-client source/consistency check; live plugin delivery
and terminal-bell acceptance were not run.

Ringing for every plugin-authored message would include messages with no
established escalation. The decision should be revisited if a later pinned
client adds an explicit needed-action contract to this type. Removing the
row and restoring the old count reverses the repository classification,
and deliberately restores the fail-closed unknown-type failure on 2.1.295.

## Repository change and verification

The two platform rows receive the new minimum, artifact URLs and manifest
digests. Their component-inventory version mirror and the Mac page's current
artifact table follow those rows. The inventory's existing freshness text
already identifies its version as the bootstrap floor. The new-WSL profile receives the same Linux artifact and updates its
installation example, release source, acceptance prerequisites and receipt
floor. The older host 2.1.287 observation is kept as historical evidence
against the former 2.1.284 floor; it does not satisfy the new minimum.
Destination acceptance stays UNRUN.

The handbook is regenerated with
`python3 scripts/build_new_wsl_handbook.py --write`; its generated Markdown
and JSON are not hand-edited. Its rolling integration receipt refreshes the
profile/output digests and appends this local regeneration while preserving
its earlier validation history. Bootstrap documentation and floor examples
follow the new minimum. The separate historical 2.1.284 compatibility
threshold for the interactive Max-effort wrapper remains unchanged.

The generated new-host grand list receives its current component version
from that inventory, so its JSON and Markdown are refreshed through
`python3 scripts/new_host_grand_list.py --write` and checked with `--check`.
The component evidence matrix remains current without a status change.

The explorer's rolling upstream snapshot also mirrors the current selected
version. Its Claude Code selection is synchronized to 2.1.295, with a dated
local-integration refresh that preserves the September 29 upstream checks
and describes the selected floor as newer than that dated observation.
This repairs the profile generator's freshness-consistency failure; it is
not a new upstream latest-release observation.

Existing floor tests exercise the new exact boundary, a newer release,
versions below the minimum, numeric ordering and invalid version output.
Historical snapshots and measured-client fixtures retain their recorded
versions. The PR records the complete targeted module results and repository
validation. No native install, update, sign-in or model acceptance is run.

The repository inverse restores the previous installer minimum and its
artifact digests. It does not downgrade a newer installed launcher. The
separately recorded search-route build keeps its own source, build and
owner gates. Both
designated reads, required CI, the pre-cue tool and an explicit command-center
cue remain landing gates.

## Addendum (2026-10-14): the floor rises to 2.1.300, and the run pin carries its source commit

On 2026-10-14 the command center asked for the claude-code run pin in `catalogs/landscape/final-stack.json` to name the
client the core lanes run, 2.1.300, with its source commit. `scripts/final_stack.py` takes that run pin from
`adoption/pins-linux-x86_64.json` `tools[].version` and `tools[].commit` (`record_pin`), and the same `version` is this
floor (`version_probe.match: minimum`). So the run pin and the floor move together, and the change mirrors the 2.1.295
raise above.

**Distribution evidence.** cc-native-practice repeated the documented check
(https://code.claude.com/docs/en/setup#binary-integrity-and-code-signing) at 2026-10-14T23:55:04Z:

| Item | Value |
| --- | --- |
| Manifest | https://downloads.claude.ai/claude-code-releases/2.1.300/manifest.json, sha256 `fb62dae2893ff954bbf8caa9f4b9345737b98a210e3a6085bf9feec9ddf5d9ca`; version 2.1.300, build commit `c6733ae1276880507ca0c5b053ae18fb0df090d6`, buildDate 2026-10-14T13:29:53Z |
| Signature | `manifest.json.sig` sha256 `a6ab3967d23a57edc237c2ff9ba9619366fe76f5f3c72b408a89b90026957b85`. The key https://downloads.claude.ai/keys/claude-code.asc (sha256 `bd70a5e4a268002704024ceba7f8446024114e94f3f0bdd11c23a9e592be81c6`) was imported into an empty keyring, fingerprint `31DD DE24 DDFA B679 F42D 7BD2 BAA9 29FF 1A7E CACE`. `gpg --verify` reports a good signature from Anthropic Claude Code Release Signing. |
| linux-x64 | checksum `674deba0bba9aee479f4503c438b49303b6fdd304b9a471b14977aaec5215453`, size 266972344. The installed `~/.local/share/claude/versions/2.1.300` re-hashes to the same digest and size. |
| darwin-arm64 | checksum `475517caa611e3318a2f298fa071287ec98955538df78c58f709ecc01e5ae2d3`, size 249556880 (signed-manifest value only; no Mac re-hash, execution or code-signature check) |

The lane's working record of that check is sha256 `9dea8022c9daa1e615f733549766dd63d8223f670f131d84d11921a6c353cba2`.

**Source commit.** Both pins carry `"commit": "94506ff0d3bd9185f1752da36e968775021fb48f"`. That is the
anthropics/claude-code commit whose `CHANGELOG.md` first carries the `## 2.1.300` section (2026-10-14T18:24:07Z). The
commit before it, `db93774d73e8fdbaf315a6f4c175ae99ad3d515a`, tops at 2.1.299. `version` stays plain `2.1.300`, because
both bootstrap scripts compare `--version`'s first word numerically. The regenerated final-stack.json run reads
`2.1.300` with that commit in `pin_parsed`.

**CHANGELOG delta 2.1.296-2.1.300** (read at 94506ff0):
- 357 entries: 2.1.296 has 79, 2.1.299 has 190 and 2.1.300 has 88; 2.1.297 and 2.1.298 have none.
- None changes the native installer, the auto-update channel, `autoUpdatesChannel` or `minimumVersion`.
- The floor stays a minimum, with latest-channel auto-update as the client-core default.

**Headless roles follow the latest release through a retained copy.**
- The headless review worker (`tools/claude-review-worker/worker.py` `DEFAULT_CLAUDE_BIN`, #1107) and the trading lane's
  private session runner (outside this repository) both pinned `~/.local/share/claude/versions/2.1.299` by path.
  CHANGELOG 2.1.243 records auto-update cleaning up an old version.
- On 2026-10-14 the owner directed (paraphrased, through the command center) that these roles follow the latest Claude
  Code. A pinned role runs a retained copy outside `versions/` (`~/.local/share/claude-retained/<version>/claude`), checks
  its sha256 against the release's signed manifest at launch, and moves to a new release after a function check of its
  exact invocation, not a paired quality run.
- At this addendum both roles move to 2.1.300 this way: the trading runner by its own dated copy, and the worker in #1127.
- Native auto-update is on here. `claude doctor` at 2026-10-15T00:44:57Z prints `Auto-updates: enabled`, channel
  `latest`, last update `2.1.300 (2026-10-14)`. `~/.claude.json` does hold `autoUpdates: false`, but with
  `installMethod: native` and `autoUpdatesProtectedForNative: true`. The native installer writes that triple itself
  when a host leaves another install method ("disabled legacy auto-updater for protection", Claude Code 2.1.300
  binary), and its disabled check counts `autoUpdates: false` only without that protection.
- So the version cleanup runs. It keeps the launcher's version, any version a session on this machine is
  running and the two newest (https://code.claude.com/docs/en/setup, the section on home directories on network
  storage). A path under `versions/` survives a later release only while a session runs it. The retained copy is the
  pinned roles' protection against that cleanup and against a broken release.

**Derived records:**
- **Regenerated through their builders:** the profile, both pins, the stack manifest, the generated handbook (receipt regeneration entry), the grand list and the final-stack catalog.
- **Mirrored as in the 2.1.295 raise:** the upstream snapshot's selected version (a dated local-integration refresh, not a new upstream observation) and the lifecycle audit's version.

**Inverse:** restore the 2.1.295 pins, digests and texts from Git and rerun the builders. That does not downgrade a newer
installed launcher.
