# Weekly public-stars maintenance

The weekly user timer calls the repository's existing public-stars builder with
an external state directory and the co-op lane questions file. The builder
refreshes allowlisted public repository fields, preserves recorded dispositions,
and appends `## NEWSTARS <n>` for new disposition work. Its first baseline is the
reviewed `catalogs/convergence-practice/public-starred.json`. Each run compares
live identities with that canonical reviewed catalog and retains unresolved
queue entries until canonical review decisions clear them. The previous valid
external snapshot retains first-observed dates. Refreshing does not commit or push.

Render the units with the actual live clone path. The example uses shell-expanded
home paths; no workstation-specific clone path is stored in either template.

```sh
python3 tools/starred-maintenance/render_units.py \
  --repo "$HOME/code/native-agent-stack-live" \
  --state-dir "$HOME/.local/state/native-agent-stack/public-stars" \
  --questions-file "$HOME/.local/state/native-agent-stack/coordination/ns2604-coop/lanes/g5-stars-gap.questions.md" \
  --output-dir "$HOME/.local/state/native-agent-stack/public-stars-unit-review"
systemd-analyze --user verify \
  "$HOME/.local/state/native-agent-stack/public-stars-unit-review/native-agent-newstars.service" \
  "$HOME/.local/state/native-agent-stack/public-stars-unit-review/native-agent-newstars.timer"
```

The renderer writes only the two staged unit files. Installation and enabling
wait for the CC's cue after landing. There is one failure-sensitive
builder command: a failed refresh cannot continue to a separate notification
step. `Type=oneshot` waits for that command, and `Persistent=true` catches up once
when a weekly calendar tick was missed while the user manager was inactive.
`weekly` means Monday at midnight in the user manager's timezone. The timer's
explicit `Unit=` binds it to the paired service.

Absolute paths are required. Expand `~` in the shell; literal tilde paths and
control characters are rejected. Runtime state and questions must resolve
outside the clone, including symlink destinations. The questions file must also
stay outside the state directory so notification appends cannot overwrite a
snapshot or journal. Spaces, UTF-8, literal dollar
signs, quotes, backslashes and percent signs use systemd's supported quoting;
the command's `:` prefix disables environment substitution and `%%` keeps a
percent sign literal. The builder is checked to exist within the supplied clone.

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

Run `python3 -B -m unittest discover -s tests -p test_starred_maintenance.py`.
The native checks run `systemd-analyze --user verify` against temporary units and
an isolated temporary runtime directory, then inspect systemd's parsed command
line. They verify syntax, supplied paths and argument preservation without
starting a service. Synthetic tests cover invalid paths and symlink escapes.
These checks do not measure a live weekly network refresh or an installed timer;
those operational checks belong to the post-landing CC cue.
