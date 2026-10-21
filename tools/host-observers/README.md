# Host observers

Small, read-only, standard-library Python tools and systemd user units that watch the workstation's storage, network and alert path. They write node exporter textfile metrics or journal lines, hold no credential, change nothing on the host, and run in the idle class. They were built on 2026-10-14 for the host-capacity work (disk flush latency, the engine delay budget, the outage of 05:09 to 05:21 UTC) and are put into the repository so the next host starts from them.

## What is here

| Tool | What it does | Unit (in `observability/host-observers/units/`) | Measured cost |
|---|---|---|---|
| `fsync_probe.py` | Open-loop fsync latency probe: appends and atomic replaces on a schedule, p50 to max, slots missed while a call ran | none (used by the canary and by hand) | 3 s runs |
| `fsync_canary.py` | The probe as a textfile (`fsync_probe_latency_seconds{target,pattern,quantile}` and counts) | `native-fsync-canary.{service,timer}`, once a minute | 64 to 88 ms CPU per run, about 0.1% of a core |
| `engine_delay_prom.py` | Renders the tail of the newest `engine-delay-*.csv` (per-stage p99, p99.9, max, share, samples, active flag, logger age, busy cores) as a textfile; the CSV is written by the engine delay logger kept with the E4 kit | `native-engine-delay-prom.{service,timer}`, every 30 s | 39 to 42 ms per run every 30 s, about 0.13 to 0.14% of a core |
| `io_attribution.py`, `io_attribution_daemon.py` | Attributes disk wait without per-task IO accounting (which this kernel lacks): cgroup `io.stat` deltas, `/proc/diskstats`, pressure, and D-state sampling of every thread by wait class; the daemon runs it 03:45 to 20:15 New York time and writes a record and a report per 5-minute window | `native-io-attribution.service` | 1.63% of a core while sampling, about 0.001% outside the window |
| `storm_snapshot.py`, `storm_runq.py`, `storm_snapshot_summary.py` | The process-sampling kit `io_attribution.py` builds on: one snapshot of what runs and from which lane, the run-queue shapes per lane, and the summary of snapshots by episode, area and owner hint | none (libraries and reports) | one snapshot reads every process's stat, about 0.5 s of CPU |
| `net_probe.py` | Active network probe: a direct DNS query and a TCP connect to two public resolvers, and a lookup through the system resolver (the path the lanes use) | `native-net-probe.{service,timer}`, once a minute | 70 ms CPU per run, about 0.12% |
| `alert_watch.py` | One journal line per state change of Grafana alert rules labelled `notify=cc`, for a Monitor task or `journalctl -f` | `native-alert-watch.service` | about 0.01% |
| `alert_replay.py` | Replays a Grafana rule from its deployed provisioning file over the series Prometheus still holds, with Grafana's own pending and firing rules, and says when it would have fired | none | one query per phase |
| `grafana_rule_add.py` | Adds or removes one rule in a Grafana alert provisioning file with a checked shape and a backup | none | none |

Together about 2% of one core while the IO sampler is in its window and about 0.3% outside it.

`observability/host-observers/grafana-rules/` holds the three rule specs as deployed (the eth0 silence rule confirmed by the probe, the probe rule, the stale-probe warning); `observability/host-observers/promtool/` holds the PromQL tests of the silence expression and of the probe rule. The probe rule reads the probe's gauge only while the probe is fresh (a run within the last 300 s, the stale-probe warning's own limit): a stopped probe leaves its last gauge in the textfile, so a stale one reads no data in the probe rule and the warning owns that case.

A command shape (the sampling kit's `storm_snapshot.py` reducer, used for the command line of a process by the snapshotter, the run-queue observer and the IO sampler) is the program's base name and nothing else of the command line except: for Python, what CPython itself would run, read with CPython's own option rules (the module of `-m`, the base name of the script, or the marker `-c`; python/cpython@v3.13.16, tag commit cbc944f4bc59, `Python/getopt.c:40-49` and `:75-90`, `Python/initconfig.c:2473-2500` and `:2636-2641`); for a shell, node or perl, the very first argument only, as an inline-code flag or a script file; for npm and uv, a subcommand of the runner's own vocabulary and a well-known tool or script name; for any other program, one word of a fixed subcommand vocabulary; and, behind a wrapper such as `timeout` or `sudo`, the command it runs, read the same way. Every other word, every option and the value it takes, and every word whose role the grammar does not name is dropped or shown as `<arg>`, `<redacted>` or `<proc>`; an option the tables do not know ends the extraction. A process that rewrote its title into one string is named by the kernel's process name.

The boundary is demonstrated at the function, the snapshot record, the run-queue record and the IO window record and report: `storm_snapshot_selftest.py` runs 90 command lines for real against the installed interpreter (the reducer must name exactly what ran), checks 3000 seeded random command lines across the families with the sentinel in 14 shapes, and names the cases one by one; `storm_snapshot_mutants.py` plants 17 faults in the reducer. It covers the command line only: working directories, session names and kinds (`aggregate()`, `session_info()`) and cgroup names and wait symbols (`io_attribution.py`) are copied by their own code and are not reduced by it. The tables are derived from the installed tools' own help, retained with versions in `observability/host-observers/receipts/cli-help-20261014.txt`; on a host whose `timeout`, `env` or `sudo` is another implementation, an option the tables do not list ends the extraction at the wrapper.

## Install and inverse

The units run the tools from `~/.local/share/native-agent-stack/host-observers/` and write below `~/.local/state/native-agent-stack/host-observers/`.

```
install -d ~/.local/share/native-agent-stack/host-observers ~/.local/state/native-agent-stack/host-observers ~/.config/native-agent-stack/monitoring/textfile
cp tools/host-observers/*.py tools/host-observers/README.md ~/.local/share/native-agent-stack/host-observers/
cp observability/host-observers/units/* ~/.config/systemd/user/ && systemctl --user daemon-reload
systemctl --user enable --now native-fsync-canary.timer native-engine-delay-prom.timer native-net-probe.timer native-io-attribution.service native-alert-watch.service
```

The textfile directory must exist before the timers first run (the writers do not create it); adjust it in the units (`~/.config/native-agent-stack/monitoring/textfile`) to the node exporter's `--collector.textfile.directory`. The README copied beside the tools is the one the units' `Documentation=` lines name. The delay sidecar (`native-engine-delay-prom.timer`) reads the engine delay logger's CSV from the E4 kit and writes a logger age of 999999 when there is none, or the age of the newest CSV file when that file holds no complete row. Inverse of each unit: `systemctl --user disable --now <unit>`, remove its file, and for the timers remove the `.prom` file they wrote.

Alert rules: add a rule with `python3 tools/host-observers/grafana_rule_add.py add <provisioning file> <spec.json> --backup-dir <dir outside the provisioning directory>`, then restart Grafana (file-provisioned alert rules are read at start; the reload endpoint needs admin rights). `remove` is the inverse.

## Tests

`python3 -m unittest tests.test_host_observers` runs the six self-tests, checks that the rule specs and units agree with the tools, runs the mutation runner's own tests and runs the PromQL tests. They use synthetic data, a fake Prometheus, a fake Grafana and fake DNS and TCP servers on loopback, and a fake `/proc` tree; nothing real is changed. The last checks of the two storm self-tests read the live `/proc` and cgroup files (read-only) and count the machine's processes themselves, so they hold on a small machine; the unittest also runs the run-queue self-test inside a PID namespace that sees three processes (`unshare --user --pid --fork --mount-proc`, skipped where an unprivileged namespace is not allowed).

| Self-test | Checks | Planted faults caught |
|---|---|---|
| `host_observers_selftest.py` (canary, fsync probe, delay sidecar and its empty-CSV age, IO daemon and its sanitized shapes) | 42 | 10 of 10 on 2026-10-14, from a throwaway script that is not kept here |
| `alert_tools_selftest.py` (replay, rule tool, watcher) | 60 | 26 of 26 (`--mutate`) |
| `net_probe_selftest.py` | 18 | 8 of 8 (`--mutate`) |
| `storm_snapshot_selftest.py` (command shapes, lanes, detector, live snapshot) | 114 | 17 of 17 (`storm_snapshot_mutants.py`) |
| `storm_runq_selftest.py`, `storm_snapshot_summary_selftest.py` | 38, 43 | not run |

`python3 tools/host-observers/<name>_selftest.py --mutate` repeats the fault pass for the two suites that carry one, and `storm_snapshot_mutants.py` does it for the reducer. Each runs the suite on the unchanged code first (the control) and gives no score, and a non-zero exit, when it does not pass (the practice of the mutation-testing workflow in trailofbits/skills, mirrored at HEAD 0f44fe01dcb0, `plugins/mutation-testing/skills/mutation-testing/workflows/configuration.md:134-141`, measured here by `tests.test_host_observers.MutationRunnerTests` and `AlertMutationRunnerTests`). A mutant run that does not reach its summary is not counted as a caught fault, with one supported exception per runner that the code under test caused: `net_probe_selftest.py` counts a run that stopped on an exception raised inside `net_probe.py`, and `alert_tools_selftest.py` counts a group that crashed inside one of the three tools; a crash in the suite's own server or socket setup is BROKEN in both. The PromQL tests (the silence expression and the probe rule) need `promtool` (Prometheus 3.15.0, from `PATH` or the `PROMTOOL` variable); the unittest skips them when the binary is absent, as hosted CI does: the engine-checked result for the probe rule's freshness filter is an author-run result (receipt `observability/host-observers/receipts/fix-round-2-20261014.md`), reproducible with promtool 3.15.0.

The storm snapshot self-test's live group check counts the group the way the tool does, with `os.walk`, which ignores a scandir error unless `onerror` is given and so yields nothing for a missing top (python/cpython@v3.13.16, tag commit cbc944f4bc59, `Lib/os.py:321` and `Lib/os.py:368-373`); a machine without the sessions cgroup therefore holds nothing, and the snapshot must hold nothing too.

## Replay of the 2026-10-14 outage

`python3 tools/host-observers/alert_replay.py --rule-file <provisioning file> --uid ns2604-net-silent-crit --start 2026-10-13T18:04:00Z --end 2026-10-14T05:50:00Z --phases 0,15,30,40,45,50 --expect-fire 2026-10-14T05:11:40Z --tolerance 60 --expect-episodes 1` on the 11.7 h of series Prometheus held: 706 evaluations per phase, one firing episode in every phase and no other, no pending run that did not fire, no no-data evaluation; at the group's real phase (:40) it fires 05:11:40Z and resolves 05:21:40Z; across the other phases the first firing is between 05:11:30Z and 05:12:15Z. The outage itself ran from 05:09:30Z to 05:21:15Z (interface receive under 5 KiB/s).

## Limits

The silence rule alone could fire on an idle weekend; the probe-confirmed version cannot while the probe is fresh and reaches a public resolver. The probe tests two public resolvers and the system resolver, not an HTTPS request to the model providers. The tools are written for this host's layout (WSL2, cgroup v2, a node exporter textfile directory, a Grafana with file-provisioned rules); other layouts need the paths and device names changed.
