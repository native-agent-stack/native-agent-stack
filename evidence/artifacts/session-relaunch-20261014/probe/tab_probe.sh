#!/bin/sh
# ccnp 2026-10-14 tab probe: proves a tab opened from a systemd --user unit starts a process back in the distro; writes one line and exits 0
printf '%s tab-probe boot=%s ppid_comm=%s\n' "$(date -u +%FT%TZ)" "$(cat /proc/sys/kernel/random/boot_id)" "$(cat /proc/$PPID/comm)" >> /var/tmp/ccnp-relaunch-20261014/probes/tab-probe.out
