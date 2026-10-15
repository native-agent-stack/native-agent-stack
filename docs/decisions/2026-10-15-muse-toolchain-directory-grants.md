# Named Muse toolchain directory grants

Status: implemented; isolation review by two model families requested before use.
Base: `ec15c903751cf2f6ed906a6ad10df8c61f04f1c7` (#1120).

This bounded extension implements the CC record
`ruling-f1-meta-fence-dirbind-20261015.md:9-18`, SHA256
`9ba078028c1762f71a78791a24ea02949944d870df376cee6d7d402b78745ec3`,
under `~/.local/state/native-agent-stack/coordination/command-center/research-cc-role-20261008/`.
The record supersedes the co-op copy. Isolation findings remain in their sealed
files; this decision cites implementation and test locations.

## Choice and primary sources

Use the existing bubblewrap launcher with repeatable `--toolchain-dir` selection
from a fixed, reviewed inventory. The initial inventory contains only the
installed Go 1.25.12 root. `--input` retains its regular-file contract. The
unchanged CC argv builder, roles, Muse flags and shared network policy continue
to apply. F1 remains held for this capability's review and landing.

- containers/bubblewrap `v0.11.1`, commit
  `124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe`:
  [bwrap.xml:251-259,293-318](https://github.com/containers/bubblewrap/blob/124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe/bwrap.xml#L251),
  [bubblewrap.c:1237-1254,1610-1639](https://github.com/containers/bubblewrap/blob/124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe/bubblewrap.c#L1237),
  [bind-mount.c:378-406,461-486](https://github.com/containers/bubblewrap/blob/124c4cdf4321f63ef17a1cb0ce8f9dd45bd7adbe/bind-mount.c#L378).
  The added flag is ordinary recursive `--ro-bind SRC DEST`; no new remount or
  namespace flag is introduced. The original decision documents existing flags.
- openai/codex `rust-v0.162.1`, commit
  `092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`,
  [codex-rs/linux-sandbox/src/bwrap.rs:411-425,717-743,1445-1485](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/linux-sandbox/src/bwrap.rs#L411).
  The root inventory and store exclusions implement CC policy; they are not
  attributed to Codex or bubblewrap.

Implementation: `tools/muse_file_fence.py:35-82,261-300,326-327,479-480`.
The CLI names each root; native receipts retain the selected directory list.
The model-free probe adds a named read-only check per selected directory.

## Evidence and scope

Derived results are retained in
`notes/muse-toolchain-directory-grants-20261015/controls.json`.
The 13 new controls are in `tests/test_muse_toolchain_dirs.py:39-199`.
They include fail-first fixture checks and the installed Go control, which
executes `go version` and verifies an exclusive temporary write is refused.
Native Muse echo startup also completes with the directory selected. All 26
landed fence controls continue to pass: 39 tests total, no skips with both
explicit probe environment switches enabled. No Meta model request is part of
this change.

The first allowlist test failed against the landed API because the parameter
was absent. Later guard tests failed as assertions against the intermediate
implementation before each corresponding guard was added. These are synthetic
development observations, distinct from the actual installed-toolchain OS
measurement. Neither proves arbitrary credential-content recognition.

The trusted host installation and launcher policy remain outside the fenced
process's write authority. Metadata-only reserved store-root checks supplement
the fixed inventory; they do not classify arbitrary file contents or promise
protection against concurrent malicious host administration. The launcher
refuses whole roots and creates no filtered copy. No credential contents are
opened, copied, hashed or logged by the extension.

## Alternatives and supersession

Per-file grants were measured as exceeding host argument limits in the CC
record's lines 5-7. A prebuilt-binary alternative requires a new CC ruling
(lines 16-18). No toolchain installation or host `/usr` change is needed.
Evidence that the named root is unsuitable, upstream changes to bind semantics,
or a review finding against the cited controls would overturn this choice.
Additional toolchain versions require a reviewed inventory change.

This decision amends only the regular-file-only directory statement in
`2026-10-14-muse-file-fence.md`; the remainder of that decision and its dated
native reader smoke remain historical evidence.
