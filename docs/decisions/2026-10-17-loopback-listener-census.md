# Decision: a loopback-only listener census on the workstation (2026-10-17)

**Status:** adopted, pending cutover. The script and the unit templates are in this repository.
- NativeHorizonNY runs a shell precursor until the cutover below. It applies the same rule, with the differences listed
  under "What runs live today".
- The cutover is complete once the templates have run under systemd and that run's receipt is recorded.

## Rule

- **Loopback binds only.** Every TCP and UDP listener binds loopback only: 127.0.0.0/8, ::1, or ::ffff:127.0.0.0/104.
- **Alert on any other listener.** A census runs every 5 minutes and alerts on any listener outside loopback.
- **One exception:** WSL's own DNS tunnel at 10.255.255.254:53.
  - It is the nameserver that resolv.conf names on a mirrored WSL host, and WSL manages it.
  - It listens on UDP and TCP 53 here.

## Why

- **The owner's choice.** On 2026-10-17 the owner chose to run dashboards and local services without passwords on this
  single-user PC.
  - Each service uses its upstream's own no-auth or anonymous mode, for example dagu `auth.mode: none`.
  - The credential rails stay strict.
- **The bind is the compensating control.**
- **WSL here runs in mirrored networking.** `wslinfo --networking-mode` printed `mirrored` at 2026-10-17T14:41:21Z.
- **What mirrored mode does.** Microsoft's WSL networking documentation
  (https://learn.microsoft.com/windows/wsl/networking, "Mirrored mode networking", read 2026-10-17) says:
  - it "mirrors" the Windows network interfaces into Linux;
  - one of its listed benefits is "Connect to WSL directly from your local area network (LAN)".
  - So a wildcard or interface bind can reach the LAN, while loopback reaches only this PC's own processes.
- **The command center's rulings.**
  - #17467 (2026-10-17T03:52:50Z), item 5: keep the loopback-only invariant.
  - #28846 (2026-10-17T13:31:27Z), part (b): ship the census and its timer as their own pull request, stating the rule
    exactly as above.

## How

- **`scripts/loopback_census.py`:**
  - It runs `ss -H -l -t -u -n -p` (iproute2 ss(8), 6.19.0 on the workstation) with a 30 s timeout. That lists TCP
    and UDP listening sockets, numerically, with the owning process and no header.
  - It parses each local address, including a `%scope` before or after an IPv6 bracket, and the `*` wildcard.
  - Exit 0 means clean. Exit 1 means a breach.
  - Exit 2 means a census error:
    - ss is missing, cannot start, exits non-zero or hangs;
    - ss writes any diagnostic to stderr, even with exit 0;
    - ss lists no listener, or a line does not parse;
    - the state directory cannot be written;
    - or any other exception, through a final handler. So no failure exits 1, the breach code.
    A real host always has listeners, so an empty enumeration is never a clean pass.
  - **Why a diagnostic counts even with exit 0:** iproute2 6.19.0's `main()` calls each table's dump without checking
    its result, and returns 0 (iproute2 tag `v6.19.0`, commit `dac1bc6021693902b25a961227e289791e429b91`,
    `misc/ss.c:6276-6291` and `:6302`).
    - A failed dump shows only as a diagnostic on stderr, for example `perror("fopen($TCPDIAG_FILE)")` at
      `:4160-4162`, beside the other tables' valid stdout.
    - A normal run on the workstation writes nothing to stderr.
  - It prints one JSON line: `check`, `at`, `listeners` and `violations`, or `error` for a census error.
    - An error report also carries the `violations` found in the other lines, so a parse error never hides a breach.
    - When only the state directory cannot be written, the exit is 2, but stdout holds the normal report.
    - An unexpected exception leaves whatever line was printed before it, or none.
  - With `--state-dir`:
    - It keeps a run's violations as `breaches/<UTC stamp>.json`, which no later run overwrites.
    - A run whose violations equal the previous run's names that run's record instead of writing another.
    - It then replaces `last.json`, which names the record.
  - Its stderr states the breach count or the error before any state is written. Then it names the breach record, or
    says why the state was not kept and adds the report itself.
  - Process names come from ss's users field when ss can see them. argv is never read.
- **`adoption/templates/systemd/loopback-census.service`:**
  - A timer-triggered oneshot with `TimeoutStartSec=60`, so a hung run fails the unit instead of blocking later runs.
    systemd 259 disables the start timeout for `Type=oneshot` by default: `man/systemd.service.xml:619-627` at tag `v259`, commit `9ca433482f2281d71718718705ca8cd3bf562ad6`; the workstation runs 259.5.
  - It runs the script with `--state-dir %S/loopback-census` (`StateDirectory=`), discards stdout, and sends stderr to
    the journal.
  - Either failure starts `OnFailure=stack-alert@%n.service`. That handler sends the command center one named hcom
    message whose journal pointer leads to the stderr lines, and so to the breach record.
  - Its header ships the install, check, cutover and activation steps:
    - the `stack-alert@` LoadState check;
    - `systemctl --user daemon-reload`;
    - disabling the precursor's timer;
    - `systemctl --user enable --now loopback-census.timer`;
    - a timer read-back.
- **`loopback-census.timer`** starts the service every 5 minutes (`OnUnitActiveSec=5min`, systemd.timer(5)) and is
  wanted by `timers.target`.

## What runs live today

NativeHorizonNY has run a shell precursor every 5 minutes since 2026-10-17 04:14-04:15Z:
- the units `nhny-loopback-census.service` and `nhny-loopback-census.timer`;
- the script `~/.local/share/native-agent-stack/loopback-census/loopback_census.sh`.

It applies the same rule, with seven differences.
- **Five come from rows.** On 2026-10-17 the precursor ran unmodified, with a fake `ss` first on PATH, over every
  fixture line in `tests/test_loopback_census.py`, two rows the reads raised, and the failure cases. 11 of 31 rows differ
  from this census, in five ways.
- **Two come from reading the precursor's unit and script.**

The five row differences:
- **v4-mapped loopback:** it flags a `::ffff:127.x` listener, which this census allows.
- **Device-bound ::1:** it flags a `::1` listener bound to a device, and this census allows it.
  - ss 6.19.0 prints that listener as `[::1]%lo:<port>`, sampled on this host.
  - The precursor's loopback patterns are only `127.*`, `[::1]:*` and `::1:*`.
- **The scope-stripped tunnel address:** it flags `10.255.255.254%lo:53`, because its exception is the literal
  `10.255.255.254:53`. This census strips a device scope before the match, as for every address, and allows the row.
  A test pins that.
- **Rows the census cannot parse:** it reads the fifth field as the address.
  - Such a row passes when that field matches a loopback pattern or the literal `10.255.255.254:53`, and is flagged
    otherwise.
  - So `tcp LISTEN 0 4096 [::1]:631`, a short row, and `127.0.0.1` without a port both pass.
  - This census exits 2 on every row it cannot parse.
- **Failures:** it counts an ss failure, a diagnostic on stderr or an empty listing as clean, because ss's errors go
  to /dev/null and an empty violation list exits 0.

The two from reading:
- **Breaches:** it keeps only `last.json`, so the next clean run overwrites a breach's detail.
- **Hangs:** its unit has no start timeout, and systemd 259 disables the start timeout for `Type=oneshot` by default: `man/systemd.service.xml:619-627` at tag `v259`, commit `9ca433482f2281d71718718705ca8cd3bf562ad6`.

**Cutover:**
1. Install and activate the templates by the service header's steps. They disable `nhny-loopback-census.timer`.
2. Let one run complete under systemd.
3. Record the receipt: the unit's journal and `last.json`.

## Residuals

- **Scope.** All WSL 2 distributions share one network namespace (`adoption/platforms/linux-wsl2.md:255-258`).
  - So the census also lists the other distribution's listeners, with process `unknown`, and alerts on them.
  - Container network namespaces and Windows processes are outside it.
  - Sockets owned by other users show no process name.
- **Sampling, not prevention.**
  - A non-loopback listener that persists across a tick is found within about 5.5 minutes (`OnUnitActiveSec=5min`
    plus `AccuracySec=30s` and run time).
  - A bind that opens and closes between ticks can be missed.
  - Each service's own bind setting stays the first control.
- **Repeat alerts.**
  - While a breach persists, every tick fails and alerts again.
  - A run writes a new breach record when its violations differ from the previous run's. A clean run, or an error
    run that found none, has no violations, so the next breach gets a new record.
  - Records are never pruned.
  - The handler throttles only its Windows toast, to one per hour per unit.
- **User manager.** This is a user timer, so no census runs while the user manager is down.
- **The exception is address-based.** 10.255.255.254:53 is allowed for UDP and TCP, by address and port, not by process.
- **Exposure that remains.** Each no-auth service is still reachable by local processes. This rule is that residual's
  control, not its removal.
