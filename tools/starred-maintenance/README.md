# Weekly public-stars maintenance

The weekly user timer calls the repository's existing public-stars builder with
an external state directory and the co-op lane questions file. The builder
refreshes allowlisted public repository fields, preserves recorded dispositions,
and appends `## NEWSTARS <n>` for new disposition work. Its first baseline is the
reviewed `catalogs/convergence-practice/public-starred.json`. Each run compares
live identities with that canonical reviewed catalog and retains unresolved
queue entries until canonical review decisions clear them. The previous valid
external snapshot retains first-observed dates. Refreshing does not commit or push.

The journal retains unresolved identities and public observations when they are
absent from a later live response. Each notification also lists those identities.
Canonical dispositions clear work; reopening a review advances its retained
generation, so a previous notification cannot suppress the new review. A retry
reuses the same identity. A previously written snapshot recovers intake if a
process stops before preparing its journal; an append failure replays the prepared
notification before the next acquisition. The latest snapshot remains a record
of the actual live response, while the journal holds unresolved review work.

Render the units with the actual live clone path. The example uses shell-expanded
home paths; set `stars_repo` to the CC's live clone before running it.

```sh
stars_repo="$HOME/code/native-agent-stack-live"
stars_state_root="${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack"
stars_stage="$stars_state_root/public-stars-unit-review"
python3 "$stars_repo/tools/starred-maintenance/render_units.py" \
  --repo "$stars_repo" \
  --state-dir "$stars_state_root/public-stars" \
  --questions-file "$stars_state_root/coordination/ns2604-coop/lanes/g5-stars-gap.questions.md" \
  --output-dir "$stars_stage"
systemd-analyze --user verify \
  "$stars_stage/native-agent-newstars.service" \
  "$stars_stage/native-agent-newstars.timer"
```

The renderer writes only the two staged unit files. Installation and enabling
wait for the CC's cue after landing. There is one failure-sensitive
builder command: a failed refresh cannot continue to a separate notification
step. `Type=oneshot` waits for that command, and `Persistent=true` catches up once
when a weekly calendar tick was missed while the user manager was inactive.
`weekly` means Monday at midnight in the user manager's timezone. The timer's
explicit `Unit=` binds it to the paired service.

The service extends `stack-currency.service`'s explicit `PATH`: the user's
`~/.local/share/codex-ecosystem/bin`, `~/.local/bin` and
`%h/.local/share/mise/shims`, followed by the standard system directories.
systemd expands `%h` for the user; the builder can find `gh`
without an interactive shell. A different host must review the directories that
hold its installed CLI before installation.

Absolute paths are required. Expand `~` in the shell; literal tilde paths and
control characters are rejected. Runtime state and questions must resolve
outside the clone, including symlink destinations. The questions file must also
stay outside the state directory so notification appends cannot overwrite a
snapshot or journal. Spaces, UTF-8, literal dollar
signs, quotes, backslashes and percent signs use systemd's supported quoting;
the command's `:` prefix disables environment substitution and `%%` keeps a
percent sign literal. The builder is checked to exist within the supplied clone.

## Install or update after the CC's post-landing cue

Use the rendered files from the landed live clone. The following commands are
for the CC after its installation cue. Keep `stars_repo`, `stars_state_root` and
`stars_stage` from the render step. Run in a shell with `set -eu` so a failed
check stops the installation. The backup records only relative filenames,
digests and timer state; keep its UTC session name for the inverse steps.

```sh
set -eu
umask 077
stars_units="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
stars_backup="$stars_state_root/public-stars-unit-backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$stars_units" "$(dirname "$stars_backup")"
mkdir "$stars_backup"
systemctl --user list-unit-files --no-legend native-agent-newstars.timer >/dev/null
stars_was_enabled=$(systemctl --user is-enabled native-agent-newstars.timer 2>/dev/null || true)
stars_was_active=$(systemctl --user is-active native-agent-newstars.timer 2>/dev/null || true)
case "$stars_was_enabled" in enabled|disabled|not-found) ;; *) exit 1 ;; esac
case "$stars_was_active" in active|inactive|unknown) ;; *) exit 1 ;; esac
printf '%s\n' "$stars_was_enabled" > "$stars_backup/timer.enabled"
printf '%s\n' "$stars_was_active" > "$stars_backup/timer.active"
for stars_unit in native-agent-newstars.service native-agent-newstars.timer; do
  test ! -L "$stars_units/$stars_unit"
  test -z "$(systemctl --user show --property=DropInPaths --value "$stars_unit")"
  stars_fragment=$(systemctl --user show --property=FragmentPath --value "$stars_unit")
  test -z "$stars_fragment" || test "$stars_fragment" = "$stars_units/$stars_unit"
  if test -e "$stars_units/$stars_unit"; then
    test -f "$stars_units/$stars_unit"
    cp -p "$stars_units/$stars_unit" "$stars_backup/$stars_unit"
    (cd "$stars_backup" && sha256sum "$stars_unit") >> "$stars_backup/original.sha256"
  else
    touch "$stars_backup/$stars_unit.absent"
  fi
done
(cd "$stars_stage" && sha256sum native-agent-newstars.service native-agent-newstars.timer) \
  > "$stars_backup/installed.sha256"
# Recheck both originals before replacing either file.
for stars_unit in native-agent-newstars.service native-agent-newstars.timer; do
  if test -f "$stars_backup/$stars_unit"; then
    cmp "$stars_units/$stars_unit" "$stars_backup/$stars_unit"
  else
    test ! -e "$stars_units/$stars_unit" && test ! -L "$stars_units/$stars_unit"
  fi
done
for stars_unit in native-agent-newstars.service native-agent-newstars.timer; do
  install -m 0600 "$stars_stage/$stars_unit" "$stars_units/$stars_unit"
done
(cd "$stars_units" && sha256sum -c "$stars_backup/installed.sha256")
systemctl --user daemon-reload
systemctl --user enable --now native-agent-newstars.timer
systemctl --user list-timers native-agent-newstars.timer
printf 'Backup session: %s\n' "${stars_backup##*/}"
```

The checks stop for symlinked unit files, drop-ins, a unit loaded from another
location or a nonstandard enablement state. Review those existing configurations
before selecting a different installation path. `enable --now` starts the timer;
its persistent catch-up may immediately trigger the refresh service. For an
update, repeat rendering and installation with a new backup session, preserving
the preceding installed files and enablement state.

## Inverse: restore the previous unit files and timer state

Set `stars_backup` to the installation's UTC session directory. Keep
`stars_units` from the installation step. Verify the installed digests before
stopping anything; a mismatch means the unit has changed since that installation
and must be reviewed before using this inverse. Original backup digests are
checked before restoration.

```sh
set -eu
stars_backup="$stars_state_root/public-stars-unit-backups/<UTC installation timestamp>"
(cd "$stars_units" && sha256sum -c "$stars_backup/installed.sha256")
if test -s "$stars_backup/original.sha256"; then
  (cd "$stars_backup" && sha256sum -c original.sha256)
fi
stars_was_enabled=$(cat "$stars_backup/timer.enabled")
stars_was_active=$(cat "$stars_backup/timer.active")
case "$stars_was_enabled" in enabled|disabled|not-found) ;; *) exit 1 ;; esac
case "$stars_was_active" in active|inactive|unknown) ;; *) exit 1 ;; esac
for stars_unit in native-agent-newstars.service native-agent-newstars.timer; do
  test ! -L "$stars_units/$stars_unit"
  test -f "$stars_backup/$stars_unit" || test -f "$stars_backup/$stars_unit.absent"
done
systemctl --user disable --now native-agent-newstars.timer
systemctl --user stop native-agent-newstars.service
for stars_unit in native-agent-newstars.service native-agent-newstars.timer; do
  if test -f "$stars_backup/$stars_unit"; then
    cp -p "$stars_backup/$stars_unit" "$stars_units/$stars_unit"
  else
    rm -- "$stars_units/$stars_unit"
  fi
done
systemctl --user daemon-reload
if test "$stars_was_enabled" = enabled; then
  systemctl --user enable native-agent-newstars.timer
fi
if test "$stars_was_active" = active; then
  systemctl --user start native-agent-newstars.timer
fi
```

This restores saved files where they existed, removes only the two files created
by that installation where they were absent, and restores the timer's recorded
enablement and active state. Retain the external snapshot and notification
journal as evidence; the inverse leaves them available for the next review.

Source references:

- The existing repository conventions at main `0947b012` are
  `adoption/templates/systemd/stack-currency.service` (explicit Python interpreter,
  oneshot, private umask, bounded timeout) and `stack-currency.timer` (calendar,
  persistent catch-up, timer installation target), plus
  `token-report-refresh.service` (specifier and dollar-expansion explanation).
- Installed primary source measured during development: systemd
  `259.5-0ubuntu3.4`. Upstream `systemd/systemd` tag `v259.5` specifies
  [quoting](https://github.com/systemd/systemd/blob/v259.5/man/systemd.syntax.xml),
  [command lines and the `:` prefix](https://github.com/systemd/systemd/blob/v259.5/man/systemd.service.xml),
  [specifier escaping](https://github.com/systemd/systemd/blob/v259.5/man/systemd.unit.xml),
  [weekly calendars](https://github.com/systemd/systemd/blob/v259.5/man/systemd.time.xml)
  and [persistent timers](https://github.com/systemd/systemd/blob/v259.5/man/systemd.timer.xml).
- The same upstream pin `b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a` documents
  [`Environment=` and specifier expansion](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.exec.xml)
  and [`systemctl` enable/disable, `--now`, state inspection and `daemon-reload`](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemctl.xml).

Run `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -B -m unittest tests.test_starred_maintenance`.
The native checks run `systemd-analyze --user verify` against temporary units and
an isolated temporary runtime directory, then inspect systemd's parsed command
line. They verify syntax, supplied paths and argument preservation without
starting a service. Synthetic tests cover invalid paths and symlink escapes.
The current native PATH check uses the actual user home, parses systemd's
expanded PATH, checks `%h/.local/share/mise/shims`, and runs the installed
`gh --version` with only that parsed PATH and home. It plants no executable.
The earlier fixture `gh` result is historical evidence only: it proved lookup
of a planted executable and did not establish reachability of the installed CLI.
At the pre-fix revision the real installed-CLI check failed because mise shims
were absent. A separate renderer assertion runs even without systemd or gh.
These checks do not measure a live weekly network refresh or an installed timer;
those operational checks belong to the post-landing CC cue.
