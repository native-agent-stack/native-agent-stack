<#
.SYNOPSIS
Owner-reviewable elevated OS tuning script for Stationary Workstation Noesis (ADR-0036).
Defaults to -DryRun (prints exact actions without mutating system state). Pass -Apply from an elevated PowerShell prompt to execute.
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$DisableErrorVirtualDisplays
)

$ErrorActionPreference = "Stop"
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)

$defenderPaths = @(
    "C:\sota-workstation",
    "Z:\sota-data",
    "Z:\sota-cache",
    "Z:\WSL",
    (Join-Path $env:LOCALAPPDATA "uv"),
    (Join-Path $env:LOCALAPPDATA "mise"),
    (Join-Path $env:APPDATA "uv")
)

Write-Host ("Mode: " + $(if ($Apply) { "APPLY" } else { "DRY-RUN (pass -Apply to execute)" }) + " | Elevated Admin: $isAdmin")
if ($Apply -and -not $isAdmin) {
    throw "ELEVATION_REQUIRED: Re-run this script from an Administrator PowerShell prompt with -Apply."
}

# 1. Microsoft Defender Exclusions (eliminates MsMpEng scan overhead on .venv / Parquet / git / uv cache)
foreach ($p in $defenderPaths) {
    if ($Apply) {
        try {
            Add-MpPreference -ExclusionPath $p -ErrorAction Stop
            Write-Host "[DEFENDER] Added exclusion: $p"
        } catch {
            Write-Warning "[DEFENDER] Failed to add exclusion ${p}: $($_.Exception.Message)"
        }
    } else {
        Write-Host "[DRY-RUN] Add-MpPreference -ExclusionPath '$p'"
    }
}

# 2. Hardware-Accelerated GPU Scheduling (HAGS = 2)
$gfxKey = "HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
$curHags = (Get-ItemProperty -Path $gfxKey -Name "HwSchMode" -ErrorAction SilentlyContinue).HwSchMode
Write-Host "[GPU HAGS] Current HwSchMode=$curHags (2=Enabled)"
if ($curHags -ne 2) {
    if ($Apply) {
        Set-ItemProperty -Path $gfxKey -Name "HwSchMode" -Value 2 -Type DWord
        Write-Host "[GPU HAGS] Set HwSchMode=2 (takes effect on reboot)"
    } else {
        Write-Host "[DRY-RUN] Set-ItemProperty -Path '$gfxKey' -Name HwSchMode -Value 2 -Type DWord"
    }
}

# 3. Optional Virtual Display Cleanup (reclaims WDDM dwm.exe VRAM bloat)
$vDisplays = Get-PnpDevice -Class Display -ErrorAction SilentlyContinue | Where-Object {
    $_.InstanceId -in @("ROOT\DISPLAY\0000", "ROOT\DISPLAY\0001")
}
foreach ($vd in $vDisplays) {
    Write-Host "[DISPLAY] Candidate: $($vd.FriendlyName) | Status=$($vd.Status) | InstanceId=$($vd.InstanceId)"
    if ($DisableErrorVirtualDisplays -and ($vd.Status -eq "Error" -or $vd.InstanceId -eq "ROOT\DISPLAY\0000")) {
        if ($Apply) {
            Disable-PnpDevice -InstanceId $vd.InstanceId -Confirm:$false -ErrorAction SilentlyContinue
            Write-Host "[DISPLAY] Disabled $($vd.InstanceId)"
        } else {
            Write-Host "[DRY-RUN] Disable-PnpDevice -InstanceId '$($vd.InstanceId)' -Confirm:`$false"
        }
    }
}

# 4. Ultimate Performance Power Plan + Disk Headroom Warning
$scheme = powercfg /getactivescheme 2>&1
Write-Host "[POWER] Active scheme: $scheme"
Get-PSDrive -PSProvider FileSystem | ForEach-Object {
    $freeGB = [math]::Round($_.Free / 1GB, 1)
    if ($freeGB -lt 100) {
        Write-Warning "[DISK] Drive $($_.Name): has only ${freeGB} GB free (< 100 GB recommended)."
    } else {
        Write-Host "[DISK] Drive $($_.Name): ${freeGB} GB free"
    }
}
