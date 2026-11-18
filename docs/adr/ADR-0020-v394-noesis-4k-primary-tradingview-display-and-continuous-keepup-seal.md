# ADR-0020: `v3.9.4` `Noesis` 4K Primary `TradingView.exe` Display, Orca Focus Routing & Continuous Keep-Up Seal

- **Status:** Accepted
- **Date:** 2026-11-18
- **Layer:** Organization Umbrella, Primary `Noesis` 4K TradingView Display Ownership & 3-Surface Zero-Drift Governance (`L0–L13` × `P0–P5` × `T1–T8`)
- **Evidence Grade:** E4 (`sota-mover-ranker @ fd572c09fee58366b61ab720e3be59bf32daad7b` `92/92` `pytest`, `sota-dynamic-trail-c @ 56121965ef8f8db8f3150294dc4df658ac2ac386` `52/52` `pytest`, `merge_gate.py` & `gitleaks` `0` Leaks)
- **GitHub Evidence:** https://github.com/native-agent-stack/native-agent-stack, https://github.com/native-agent-stack/.github, https://github.com/native-agent-stack/sota-mover-ranker, https://github.com/native-agent-stack/sota-dynamic-trail-c
- **Revisit Trigger:** 2026-12-07

## Context and Problem Statement

After confirming simultaneous Dual Native `TradingView.app` + `TradingView.exe` Alpaca coexistence under `--dual-desktop-coexist`, operational day-to-day usage centers on Stationary `Noesis` (`100.110.115.22`, `3864x2100` 4K main display, Layout `'3'`) as the owner's primary TradingView chart workstation most of the time. Three gaps had to be closed permanently:
1. **`sota-mover-ranker @ fd572c09fee5` (`ADR-0020`, `20` ADRs, `92/92` `pytest` PASS):** Routes `/api/tv/focus` from Mac over Orca WebSocket directly onto `Noesis` `WinSta0` `TradingView.exe`, resolves `orca.exe` on `win32`, declares `primary_tv_display_host = "noesis"`, and keeps `TradingView.exe` open automatically (`SOTA_KEEP_MAIN_TV_OPEN=1`).
2. **`sota-dynamic-trail-c @ 56121965ef8f` (`ADR-0017`, `17` ADRs, `52/52` `pytest` PASS):** Declares `primary_tv_display_host` (`"noesis"` default) and `main_display_layout` in `:8799` `/api/seamless-manifest` alongside `0`-WS `--dual-desktop-coexist`.
3. **Noesis Workstation 15m Auto-Keep-Up Guard:** Removes `Stop-Process TradingView` from `sota-noesis-4k-wall` and continuously ensures `TradingView.exe` stays live on `Noesis` 4K while monitoring Mac `:8799` zero-WS coexistence.

## Decision Outcome

1. **Advance `ECOSYSTEM_CONVERGENCE_LOCK.json` to `schemaVersion = "3.9.4"` (`20` Umbrella ADRs):**
   - Record `v394NoesisMainTradingViewDisplayAndKeepUpSeal` binding `sotaMoverRankerAdr0020Sha = "fd572c09fee58366b61ab720e3be59bf32daad7b"`, `sotaDynamicTrailCAdr0017Sha = "56121965ef8f8db8f3150294dc4df658ac2ac386"`, `primaryTradingViewDisplayHost = "noesis_4k_main_display"`, `autoKeepUpIntervalMinutes = 15`, and `threeSurfaceSyncedCheckouts = 54`.

## Alternatives Considered

1. **Treat `Noesis` as a browser-only wall that kills native `TradingView.exe`:** Rejected — owner explicitly runs main `TradingView.exe` display primarily on Stationary `Noesis`.

## Verification Witness

- `.venv/Scripts/python.exe scripts/merge_gate.py` (`architecture_catalog --check`, `umbrella --check`, `ruff`, `ty`, `pytest`) -> `PASS`.
- `gitleaks` -> `0` leaks.
