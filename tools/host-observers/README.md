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

A command shape (the sampling kit's `storm_snapshot.py` reducer, used by the run-queue observer and the IO sampler) copies text from a command line in three places only: the program's base name, the base name of a script or the module of `-m`, and a word of a fixed vocabulary of subcommands. A process that rewrote its title into one string is named by the kernel's process name, and everything else, option values included, is dropped or replaced by a fixed marker.

## Install and inverse

The units run the tools from `~/.local/share/native-agent-stack/host-observers/` and write below `~/.local/state/native-agent-stack/host-observers/`.

```
install -d ~/.local/share/native-agent-stack/host-observers ~/.local/state/native-agent-stack/host-observers
cp tools/host-observers/*.py ~/.local/share/native-agent-stack/host-observers/
cp observability/host-observers/units/* ~/.config/systemd/user/ && systemctl --user daemon-reload
systemctl --user enable --now native-fsync-canary.timer native-net-probe.timer native-io-attribution.service native-alert-watch.service
```

Adjust the textfile directory in the units (`~/.config/native-agent-stack/monitoring/textfile`) to the node exporter's `--collector.textfile.directory`. Inverse of each unit: `systemctl --user disable --now <unit>`, remove its file, and for the timers remove the `.prom` file they wrote.

Alert rules: add a rule with `python3 tools/host-observers/grafana_rule_add.py add <provisioning file> <spec.json> --backup-dir <dir outside the provisioning directory>`, then restart Grafana (file-provisioned alert rules are read at start; the reload endpoint needs admin rights). `remove` is the inverse.

## Tests

`python3 -m unittest tests.test_host_observers` runs the six self-tests, checks that the rule specs and units agree with the tools, runs the mutation runner's own tests and runs the PromQL tests. They use synthetic data, a fake Prometheus, a fake Grafana and fake DNS and TCP servers on loopback, and a fake `/proc` tree; nothing real is changed. The last checks of the two storm self-tests read the live `/proc` and cgroup files (read-only) and count the machine's processes themselves, so they hold on a small machine; the unittest also runs the run-queue self-test inside a PID namespace that sees three processes (`unshare --user --pid --fork --mount-proc`, skipped where an unprivileged namespace is not allowed).

| Self-test | Checks | Planted faults caught |
|---|---|---|
| `host_observers_selftest.py` (canary, fsync probe, delay sidecar, IO daemon and its sanitized shapes) | 38 | 10 of 10 on 2026-10-14, from a throwaway script that is not kept here |
| `alert_tools_selftest.py` (replay, rule tool, watcher) | 60 | 26 of 26 (`--mutate`) |
| `net_probe_selftest.py` | 18 | 8 of 8 (`--mutate`) |
| `storm_snapshot_selftest.py`, `storm_runq_selftest.py`, `storm_snapshot_summary_selftest.py` | the files' own checks | not run |

`python3 tools/host-observers/<name>_selftest.py --mutate` repeats the fault pass for the two suites that carry one. Both run the suite on the unchanged code first (the control) and give no score when it does not pass, and neither counts a run that did not reach its summary as a caught fault. The PromQL tests (the silence expression and the probe rule) need `promtool` (Prometheus 3.15.0, from `PATH` or the `PROMTOOL` variable); the unittest skips them when the binary is absent.

The storm snapshot self-test's live group check counts the group the way the tool does, with `os.walk`, which ignores a scandir error unless `onerror` is given and so yields nothing for a missing top (python/cpython@v3.13.16, tag commit cbc944f4bc59, `Lib/os.py:321` and `Lib/os.py:368-373`); a machine without the sessions cgroup therefore holds nothing, and the snapshot must hold nothing too.

## Replay of the 2026-10-14 outage

`python3 tools/host-observers/alert_replay.py --rule-file <provisioning file> --uid ns2604-net-silent-crit --start 2026-10-13T18:04:00Z --end 2026-10-14T05:50:00Z --phases 0,15,30,40,45,50 --expect-fire 2026-10-14T05:11:40Z --tolerance 60 --expect-episodes 1` on the 11.7 h of series Prometheus held: 706 evaluations per phase, one firing episode in every phase and no other, no pending run that did not fire, no no-data evaluation; at the group's real phase (:40) it fires 05:11:40Z and resolves 05:21:40Z; across the other phases the first firing is between 05:11:30Z and 05:12:15Z. The outage itself ran from 05:09:30Z to 05:21:15Z (interface receive under 5 KiB/s).

## Limits

The silence rule alone could fire on an idle weekend; the probe-confirmed version cannot while the probe is fresh and reaches a public resolver. The probe tests two public resolvers and the system resolver, not an HTTPS request to the model providers. The tools are written for this host's layout (WSL2, cgroup v2, a node exporter textfile directory, a Grafana with file-provisioned rules); other layouts need the paths and device names changed.
