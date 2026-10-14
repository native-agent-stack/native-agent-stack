# ccnp 2026-10-14 probe: open ONE self-closing tab in its own window (ccnp-probe), like open-tab.ps1 does for a lane
$al = '-w ccnp-probe new-tab --title ccnp-probe wsl.exe -d NativeStack2604 --exec /bin/sh /var/tmp/ccnp-relaunch-20261014/probes/tab_probe.sh'
$p = Start-Process -FilePath 'wt.exe' -ArgumentList $al -PassThru
Write-Output ("wt_pid={0} session={1}" -f $p.Id, (Get-Process -Id $PID).SessionId)
