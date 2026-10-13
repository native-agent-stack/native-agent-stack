# Receipts for the daily skill-invoke record (two halves, 2026-10-12)

Value-free captures behind the measurements of [the decision record](../../../docs/decisions/2026-10-12-skill-invoke-rate-timer.md) (command lines, exit codes, wall and CPU seconds, peak memory, counts), taken on the first host with
systemd 259.5 and Claude Code 2.1.296. Nothing here holds an account name, a host name, a home path (written `~`), a key, a skill name or a transcript. They were added after the first full read of the change found the
decision's tables had no receipts in the repository; what has none is listed at the end.

| File | What it shows |
| --- | --- |
| `receipts/unsandboxed-single-unit-1200s.txt` | the first version's one unit (three commands at 1,200 s): 23 min 57 s, 26 min 55 s of CPU, 12.5 GB peak (page cache included), exit 1 |
| `receipts/unsandboxed-per-command.txt` | each command of the daily run on its own as a transient user unit: the `/skill-doctor` capture (19.9 s), the Claude lanes sweep (2 min 17.9 s), the host report's Codex scan (1 min 10.5 s) and the Codex lanes scan (25 min 47.1 s), with CPU and peak memory |
| `receipts/unsandboxed-live-clone-refusal.txt` | the unmodified script run from the live clone: the refusal line before anything was collected |
| `receipts/capture-timings/` | the `/skill-doctor` capture, 8 quiet runs (17.2 to 20.1 s) in the unit's environment and the interactive one, and 2 at three runnable threads per CPU (61.9 s, 57.7 s) |
| `receipts/unsandboxed-halves-end-to-end.txt` | the rendered units of the split, one after the other, before the sandbox: Claude 2 min 43.9 s, Codex 28 min 3.6 s, both exit 0 |
| `receipts/sandboxed-halves-end-to-end.txt` | the same units with the sandbox of decision 7, from a scratch live clone: Claude 3 min 7.5 s, Codex 33 min 58.1 s (the host was loaded by other work), both exit 0; the records they wrote (modes, `measured`, counts) and the untouched clone |
| `receipts/sandbox-probe.json` | the probe of `NativeManagerTests` (round 3 rebuilt the runtime tests; the manager of this host applies the directives) and of `StubManagerTests` (a stand-in that accepts every property and applies none), for both services and for the control without the directives: writes to the clone, a sibling directory and the home are `EROFS` under the directives through this host's manager and `written` without them or through the stand-in; the record directory is written; bytecode appears only in the control; `check_exit` is the program's own check (`require_confined`): 0 accepted under the applied directives, 3 refused in every other case |
| `receipts/analyze-security.txt` | `systemd-analyze security --offline=yes --user --json=short` rows for `ProtectSystem=`, `ProtectHome=`, `PrivateTmp=` and `PrivateUsers=` of the rendered services, on the sources of `6c4bbd0db`, after round 2, and after round 3 (which adds `PrivateUsers=true`) |
| `receipts/mutants-split-34.txt` | the 34 mutants of the split, run on the code and tests of round 2 (the anchors that round 2 rewrote were moved to the new code): 34 of 34 killed |
| `receipts/mutants-round2-26.txt` | the 26 mutants of round 2 (the other half's record, the refresh lock, the unit templates): 26 of 26 killed (a mutant that hangs counts as killed) |
| `receipts/fail-before-round2.txt` | the round-2 test file against the sources of `6c4bbd0db`: `FAILED (failures=25, errors=9)` of 41 tests |
| `receipts/ci-runner-unconfined-20261013.txt` | round 3: the failed shard of the pull request at `68d4f4343` on a GitHub-hosted runner (run 38325995828, job 115064673607): the manager accepted the rendered directives and the probe wrote to the clone, a sibling directory and the home directory; the runner image and the systemd version it lists |
| `receipts/fail-before-round3.txt` | the round-3 test file against the sources of `68d4f4343`: `FAILED (failures=11, errors=39)` of 59 tests, in 20 tests |
| `receipts/mutants-round3-35.txt` | the 35 mutants of round 3 (the native-report shapes, the confinement check and its option, the unit templates): 35 of 35 killed |
| `receipts/fail-before-round4.txt` | the round-4 test file against the sources of `9caafa601`: the stand-in manager's two-root regression fails (`0 != 3`: the process got past the check) and so do the lanes-report tests |
| `receipts/mutants-round4-24.txt` | the 24 mutants of round 4 (only `EROFS` is confinement; a lanes report with a container of the wrong shape is not measured, publishes no lane and says why): 24 of 24 killed |

The mutation driver of round 3 (`daily_mutants_r3.py`) and the receipts builder are scripts of the author's private record; the mutants are listed in `receipts/mutants-round3-35.txt` by label, one change each.

## Claims of the decision record without a receipt here

- **The 13 quiet captures and the capture with hooks disabled (16.2 s)**: 8 quiet runs are in `capture-timings/`; the other 5 and the hooks-disabled run were not kept as files.
- **The load by UTC hour (281 five-minute samples of `node_load1` from the local Prometheus)** and the three load figures quoted from it (175 at the failed capture, 111 at the 95th percentile, 201 at the maximum): the query results were not kept. The schedule's hour is
  provisional for that reason and is revised when a week of samples exists.
- **The neighbour sweeps over the modules that name a changed file** and **the first run of the 34 mutants (one survivor, later covered)**: the counts are in the pull request's description; the mutants were run again for `receipts/mutants-split-34.txt`.
- **The zero-turn, zero-cost result of every capture**: the `num_turns` and `total_cost_usd` columns of `capture-timings/` show it for the 8 retained runs; the others are author-reported. The live clone's refusal of the unmodified script is in
  `receipts/unsandboxed-live-clone-refusal.txt` (the message; the exit status is the script's documented one for it).

The measurements are the author's, taken from transient user units on one host; nothing here is a measurement by an independent party.
