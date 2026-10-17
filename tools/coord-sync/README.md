# Coordination sync between 2604 and NativeHorizonNY

The NativeHorizonNY (command center) halves of the two coordination syncs with the 2604 host. Both directions are
append-only and verified whole before anything is written, and both run every 60 s as systemd `--user` oneshots
(timer templates in `adoption/templates/systemd/`). The scripts are stdlib-only; their one subprocess is the hcom
refusal alert.

| File | What it is |
| --- | --- |
| `ingest_coord_sync.py` | Forward sync, 2604 to NativeHorizonNY: verify each staged batch whole, copy it into the coordination mirror, mark it ingested. |
| `publish_cc_verdicts.py` | Reverse sync, NativeHorizonNY to 2604: stage newly sealed CC and MICRO verdict files for the 2604 side to install. |
| `adoption/templates/systemd/nhny-coord-sync-ingest.{service,timer}` | Runs the ingest every 60 s. |
| `adoption/templates/systemd/nhny-cc-verdict-publish.{service,timer}` | Runs the publish every 60 s. |

The 2604 halves (the forward stager and the reverse installer) live on 2604, not in this directory. The contract each
half here keeps is in its docstring: the forward contract is the CC tracker of 2026-10-16T20:52:00Z (nami #520, #543);
the reverse contract was proposed by the CC (hcom #719 thread) and confirmed by nami (#766).

## Forward: 2604 to NativeHorizonNY (`ingest_coord_sync.py`)

The 2604 side stages batches under the staging root: one directory per batch, named by UTC stamp
(`YYYYMMDDTHHMMSSZ`), holding the payload files under their coordination-relative paths and a `SHA256SUMS` file that
is written last, so its presence means the batch is complete. Each run takes the complete batches oldest first and,
for each one that is not already marked ingested:

1. **Verifies the batch whole before writing anything.** Every listed file's sha256 must match `SHA256SUMS`; nothing
   on disk may be unlisted and nothing listed may be missing; every path must be relative with no `..` and no
   duplicates; there must be no symlinks and only regular files (a batch directory that is itself a symlink is
   skipped); and every path must be in scope:

   | Path | What it carries |
   | --- | --- |
   | `cc-reads-20261005/<dir>/GPT-*.md` | The co-op's GPT-family reads (the landers glob `*pr<N>/GPT-VERDICT-<head8>*.md`). |
   | `trading-cc/reads/<name>.md` | The records trading-cc-read statuses name (`uet_land.sh`). |
   | `cc-cc-work/<dir>/CC-*.md`, `MICRO-*.md` | Dula's sealed CC records (scope c). |
   | `command-center/receipts/<name>.md` | CC-lane receipts (dula's closing record via the co-op sync's extra-paths list, #2427). One level only: a nested receipt path or a non-`.md` receipt is out of scope. |

2. **Applies the append-only rule to every path** (dula's ruling, nami #543). A path that does not exist in the
   mirror is new; a path whose mirror copy is byte-identical is skipped; a different file at a path that already
   exists refuses the whole batch. Corrections ship under a new versioned name, never as an overwrite. A destination
   that is a symlink also refuses the batch.
3. **Copies each new file** into the coordination mirror at mode 0444 with the source mtime, through a temporary file
   in the destination directory renamed into place, so readers see the old state or the new file whole. The copy is
   hashed as it is written and checked against `SHA256SUMS` before the rename, so the bytes installed are the bytes
   verified even if a staged file changed after `SHA256SUMS` was written; on a mismatch the temporary file is removed
   and nothing is renamed into place for that file.
4. **Writes `<batch>.ingested`** beside the batch, holding the sha256 of its `SHA256SUMS` and the UTC time. The 2604
   side then deletes the batch and the marker. A later run that finds a marker matching the batch's `SHA256SUMS`
   does nothing for that batch.

A refusal writes **`<batch>.refused`** (the `SHA256SUMS` sha256, the UTC time and the reason), logs one `REFUSED`
line, alerts once (see below) and **stops the run**: later batches wait until the refused one is resolved and its
marker removed. While the marker matches the batch's `SHA256SUMS`, reruns return the refusal without re-verifying,
re-logging or re-alerting; a batch whose `SHA256SUMS` changed is verified again. A refusal writes nothing in the run
that refuses, because verification happens first; files copied into the mirror by an earlier run stay there (each
matched `SHA256SUMS` when it was copied). A failure part-way through a batch (for example `ENOSPC` while copying, or
a copy whose hash no longer matches `SHA256SUMS`) writes no ingested or refused marker: instead it writes
**`<batch>.failed`** (the `SHA256SUMS` sha256, the UTC time and the error), logs one `FAILED` line, alerts once and
stops the run with exit 2. While the same `SHA256SUMS` and the same error last, reruns retry the batch but do not
re-log or re-alert; a different error, or a changed `SHA256SUMS`, is reported again, and the flag is removed when
the batch ingests. Files already copied stay in the mirror. For a copy fault (for example `ENOSPC`) recovery needs
no manual step beyond clearing the fault, because the next run retries the same batch, sees the copied files as
identical and completes it. A copy whose hash no longer matches `SHA256SUMS` is different: the mismatched file is
never installed, and unless the staged bytes again match `SHA256SUMS` before the next run, that run refuses the batch
in verification, so it is then resolved like a refusal. One summary line per batch goes to stdout (the journal) and
to `.sync-ingest.log` in the coordination mirror. Exit 0 when every pending batch ingests or none is pending, 2 when
a batch is refused or fails part-way, 3 when the staging root is unreadable or when `COORD_SYNC_STAGING` is unset,
empty, relative or contains `@` (one line naming the variable, before anything is touched). An incomplete batch (no
`SHA256SUMS` yet), a batch directory that is itself a symlink, and a batch that vanishes before its `SHA256SUMS` is
hashed are skipped silently.

## Reverse: NativeHorizonNY to 2604 (`publish_cc_verdicts.py`)

Two 2604 readers depend on this direction: the co-op's GPT read-wave, which cites CC verdicts as priors by name and
sha256, and trading-cc's gates and Monday tree manifest (suki #750, #764). The 2604 half installs each staged file
at `/var/tmp/cc-cc-work/<pr>-micro/<file>` at 0400 and writes `<batch>.ingested`. One run here:

1. **Cleans up**: deletes each staged batch (and its marker) whose `<batch>.ingested` holds the sha256 of that
   batch's `SHA256SUMS`. A marker that does not match deletes nothing.
2. **Scans** the source root's `<name>-micro/` directories for `CC-*.md` and `MICRO-*.md` files that are sealed (no
   write bit for anyone), regular files and not symlinks. Unsealed drafts, other names (such as `BRIEF-*.md`),
   symlinks and files outside a `-micro` directory are ignored.
3. **Checks the ledger** (a tab-separated record of everything already published: relative path, sha256, batch, UTC
   time). A sealed file already in the ledger with the same sha256 is done. One with a different sha256 is a
   same-path change to a published record: the run is refused, nothing is staged, a `.publisher-refused` flag is
   written in the staging root and one alert is sent (once per distinct refusal). A correction must ship under a new
   name, as in the forward direction.
4. **Stages one batch** with every new sealed file under `cc-cc-work/<pr>-micro/<file>` (mtime kept), writes
   `SHA256SUMS` last by rename from `SHA256SUMS.tmp`, and only then appends the files to the ledger, so the ledger
   never claims a file whose batch is incomplete. If staging fails before `SHA256SUMS` is renamed into place, the
   incomplete batch directory is removed (cleanup could never retire it) and the ledger is not appended; the run
   prints one `FAILED` line, alerts once per distinct error (a `.publisher-failed` flag in the staging root, removed
   by the next successful stage) and the next run retries.

Exit 0 when there is nothing to do or a batch was staged, 2 when refused or staging fails, 3 when a root is unreadable or when
`REVERSE_SYNC_STAGING` is unset, empty, relative or contains `@` (one line naming the variable, before anything is
touched). The staging root itself is created only when its parent already exists; a missing parent is refused with
exit 3 rather than created, so a mis-rendered value can never grow a shadow staging tree under the working directory.

## Refusal alerts

Both scripts alert the same two holders over hcom (`ALERT_TO` in each script): the CC and the fallback holder (dula
closed, #2427, so the co-op holds the fallback). An alert is sent once per refusal and once per distinct part-way
failure, with `--intent request`, through
the hcom-x directory named by `HCOM_DIR` (default `/mnt/wsl/hcom-x`, also set by the units). A failed send is logged
or printed, never fatal: the refusal itself, its marker and the nonzero exit already hold the sync still.
`COORD_SYNC_NO_ALERT=1` (ingest) and `REVERSE_SYNC_NO_ALERT=1` (publish) disable alerts; the tests set them.

## The 2026-10-16 fixes

- **The `command-center/receipts` scope.** Dula's closing record reached the forward sync through the co-op sync's
  extra-paths list (#2427), so `command-center/receipts/<name>.md` became the fourth ingest scope. It is deliberately
  narrow: one directory level, Markdown only. A nested receipt, a non-Markdown receipt or anything else under
  `command-center/` still refuses the batch (covered by tests).
- **hcom resolved by absolute path.** A systemd `--user` unit's PATH has no `~/.local/bin` (systemd 259's user
  manager, measured with `systemd-run --user`), and `subprocess` resolves a bare name on the child environment's
  PATH, so the 2026-10-16T22:55:43Z refusal's alert failed with `FileNotFoundError`. Both scripts now resolve hcom
  with `shutil.which` and fall back to its install path under `~/.local/bin` (`hcom_bin()`), and both units also put
  `%h/.local/bin` on PATH. The tests prove the alert reaches a stub hcom that exists only off PATH.

## Paths and environment

Every other root has the default below. The two staging roots have no default: each script takes its staging
directory only from its environment variable and, unless that value is an absolute path containing no `@`, prints one
line naming the variable and exits 3 before touching anything. That refuses an unset or empty variable, a relative
value, and an unrendered placeholder such as a literal `@WINDOWS_TEMP@` left by a renderer that substituted only
`@REPOSITORY@`. The units set both variables through the install-time placeholder `@WINDOWS_TEMP@`, the WSL path of
the Windows TEMP folder (see Install); the repository holds only the placeholder and the directory names below, never
the rendered value. Both units quote the whole staging `Environment=` assignment, as `systemd.exec(5)` at systemd 259
(259.5-0ubuntu3.4, the host's version) advises for values that may hold whitespace. The same manual notes that
specifier expansion is still performed on the assignment, and `systemd.unit(5)` at systemd 259 (Specifiers) gives
`%%` as a single literal percent sign, so the renderer escapes every literal `%` in the rendered staging value as
`%%` (see Install); the units' intentional `%h` specifiers stay single.

| Variable | Default | Read by |
| --- | --- | --- |
| `COORD_SYNC_STAGING` | none; required (unit: `@WINDOWS_TEMP@/nhny-coord-sync`) | ingest: where 2604 stages forward batches |
| `COORD_ROOT` | `~/.local/state/native-agent-stack/coordination` | ingest: the coordination mirror (also holds `.sync-ingest.log`) |
| `COORD_SYNC_NO_ALERT` | unset; `1` disables alerts | ingest |
| `CC_VERDICT_SRC` | `/var/tmp/cc-cc-work` | publish: scanned for `<name>-micro/` verdict directories |
| `REVERSE_SYNC_STAGING` | none; required (unit: `@WINDOWS_TEMP@/nhny-to-2604-sync`) | publish: where reverse batches are staged |
| `REVERSE_SYNC_LEDGER` | `/var/tmp/cc-cc-work/.reverse-sync-published.tsv` | publish: the published-files ledger |
| `REVERSE_SYNC_NO_ALERT` | unset; `1` disables alerts | publish |
| `HCOM_DIR` | `/mnt/wsl/hcom-x` (set by both units) | both: the hcom-x directory for alerts |

## Install (the command center's act)

The units already run on NativeHorizonNY from the command center's own copies; installing from these templates
repoints the same unit names at the repository copies. Rendered on the host, `@WINDOWS_TEMP@` plus the same
directory names gives the staging roots already in use, and every other default is unchanged, so the
coordination mirror and the ledger carry over as they are. Install from the live clone (the `@REPOSITORY@`
value in the templates' headers), rendering `@WINDOWS_TEMP@` on the host as below, then verify before enabling.
The first line sets `WINDOWS_TEMP` to the WSL path of the Windows TEMP folder: `cmd.exe` prints the folder
Windows names with `%TEMP%` and `wslpath -u` rewrites that Windows path in WSL form. Run it on the host at
install time and keep the result out of the repository. Render the placeholders with `python3`, not `sed`: in a
`sed` `s` replacement an unescaped `&` references the whole matched text, and the chosen delimiter can appear in the
replacement only escaped (GNU sed 4.9, the sed manual's section 3.3, "The `s` Command"), so a Windows TEMP path
containing either character would silently corrupt the rendered unit; Python's `str.replace` has no metacharacters.
The renderer also escapes every literal `%` in `WINDOWS_TEMP` as `%%`, because systemd performs specifier expansion
even inside a quoted `Environment=` assignment (`systemd.exec(5)` and `systemd.unit(5)` at systemd 259, as above),
while the intentional `%h` in the `@REPOSITORY@` replacement stays single. Any `@...@` placeholder still left in a
staging value is refused by both scripts with exit 3 in any case:

```bash
WINDOWS_TEMP="$(wslpath -u "$(/mnt/c/Windows/System32/cmd.exe /d /c 'echo %TEMP%' | tr -d '\r')")"
render() { WINDOWS_TEMP="$WINDOWS_TEMP" python3 -I -c 'import os,sys; s=open(sys.argv[1]).read().replace("@REPOSITORY@","%h/code/native-agent-stack-live").replace("@WINDOWS_TEMP@",os.environ["WINDOWS_TEMP"].replace("%","%%")); open(sys.argv[2],"w").write(s)' "$1" "$2"; }
render adoption/templates/systemd/nhny-coord-sync-ingest.service ~/.config/systemd/user/nhny-coord-sync-ingest.service
render adoption/templates/systemd/nhny-cc-verdict-publish.service ~/.config/systemd/user/nhny-cc-verdict-publish.service
cp adoption/templates/systemd/nhny-coord-sync-ingest.timer adoption/templates/systemd/nhny-cc-verdict-publish.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemd-analyze --user verify ~/.config/systemd/user/nhny-coord-sync-ingest.service ~/.config/systemd/user/nhny-coord-sync-ingest.timer ~/.config/systemd/user/nhny-cc-verdict-publish.service ~/.config/systemd/user/nhny-cc-verdict-publish.timer
systemctl --user enable --now nhny-coord-sync-ingest.timer nhny-cc-verdict-publish.timer
```

Check one cycle later: `systemctl --user list-timers nhny-coord-sync-ingest.timer nhny-cc-verdict-publish.timer`
shows each next run 60 s after the last, and
`journalctl --user -u nhny-coord-sync-ingest.service -u nhny-cc-verdict-publish.service -n 20` shows the usual
`INGESTED` / `STAGED` / `nothing new` lines (or none, when there is nothing to ingest).

Inverse: `systemctl --user disable --now nhny-coord-sync-ingest.timer nhny-cc-verdict-publish.timer`, remove the
four unit files from `~/.config/systemd/user/`, then `systemctl --user daemon-reload`. That stops both syncs and
nothing else: the coordination mirror, the ledger and both staging roots keep every record and marker they hold, so
reinstalling (these templates, or the command center's earlier unit files) resumes from the same state.

## Tests

`python3 -m unittest tests.test_coord_sync_ingest tests.test_coord_sync_publish` (35 tests, stdlib only). Each test
runs a script against temporary roots through its environment overrides: all four scopes landing read-only, tampered,
unlisted, symlinked and out-of-scope batches refusing with nothing written in that run, same-path changes refusing in
every scope, a refused batch blocking later batches and alerting exactly once, a mid-batch failure logging `FAILED`,
alerting once and completing on the next run, a persistent mid-batch failure still alerting exactly once until a
successful run clears its `<batch>.failed` flag, a `FAILED` alert and exit 2 surviving a failing log write, a file
changed between verification and copying never being installed and then refusing on the next run while the file
copied before it stays, a symlinked batch directory and a batch vanishing before its hash being skipped, each script
refusing with exit 3 and creating nothing when its staging variable is unset, empty, relative or still holds a
placeholder, the publish staging root under a missing parent also exiting 3 and creating nothing, sealed-only
staging with `SHA256SUMS` written last, a staging failure removing the incomplete batch, alerting once and staging
on the next run, cleanup only on a matching marker, the README renderer escaping a literal `%` (and keeping a space)
in the staging value while preserving the intentional `%h`, a nonzero hcom exit being reported by the publish alert,
and the alert reaching an off-PATH stub hcom addressed to the CC and the fallback holder.
